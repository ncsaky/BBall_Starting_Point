"""Own mutable league saves, chronological advancement, and season lifecycle.

Canonical data is the reproducible baseline; a save is the evolving overlay.
Functions in this module coordinate domain services in causal order, so their
sequence is gameplay behavior rather than incidental implementation detail.
"""

from __future__ import annotations

import hashlib
import logging
import json
import math
import os
import pickle
import random
import re
import tempfile
import uuid
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import date, timedelta
from itertools import permutations
from pathlib import Path
from typing import Any, Callable, Iterator

from .health import add_box_score_fatigue, advance_development, simulate_health
from .simulation_progress import emit_progress, progress_listener_active, simulation_stop_requested
from .history_store import HISTORY_KEYS, SaveValidationError, archive_save_history, hydrate_save_history, load_history_records, validate_save_components
from .save_locking import fsync_directory, save_lock
from .narrative import (
    NARRATIVE_PROMPT_VERSION,
    NarrativeProvider,
    default_narrative_settings,
    ensure_narrative_state,
    hydrate_social_items,
    narrative_status as narrative_status_payload,
    normalize_narrative_settings,
    provider_from_settings,
    reset_narrative_cache,
)
from .schema import CANONICAL_SEASON, CANONICAL_START_DATE, CoachRating, DevelopmentEvent, to_plain
from .sim import build_sim_indices, espn_team_id_map, invalidate_sim_cache, load_sim_context, load_sim_reference, sim_game_with_context
from .spatial import invalidate_spatial_cache, team_spatial_profile
from .staff import ROLE_LABELS, STAFF_SLOTS, apply_head_coach_reputation, fire_staff_from_save, hire_staff_from_save, initialize_staff_season_changes, initialize_save_staff_slots, interim_staff, is_interim_staff, negotiate_staff_hire, simulate_ai_staff_changes, staff_action_permissions, staff_budget_for_team, staff_budget_salary, staff_contract, staff_grade
from .staff_lifecycle import roll_staff_lifecycle
from .utils import clamp, copy_plain, maybe_float, normalize_name, stable_id
from .baselines import baseline_for_save


SAVE_VERSION = "league_save_v1"
SAVE_REPAIR_VERSION = 2
SCHEDULE_FILE = Path("NBA Schedule/schedule_v2025_2026.json")
SCHEDULE_CORRECTIONS_FILE = Path("data/overrides/schedule_template_corrections.json")
REGULAR_START = "2025-10-21"
REGULAR_END = "2026-04-12"

STAT_FIELDS = [
    "minutes",
    "points",
    "rebounds",
    "assists",
    "turnovers",
    "steals",
    "blocks",
    "fgm",
    "fga",
    "fg3m",
    "fg3a",
    "ftm",
    "fta",
    "rim_attempts",
    "screen_assists",   # new-ratings box scores: screens that directly led to a teammate's basket (screens.py)
]
from .cap_rules import TAX_LINE, SECOND_APRON, ANNUAL_CAP_GROWTH_RATE  # noqa: E402,F401  (one shared source)
ROSTER_MINIMUM = 14
ROSTER_SEASON_MAXIMUM = 15
ROSTER_CUTDOWN_PHASES = frozenset({"training_camp", "preseason", "regular_season", "play_in", "playoffs"})
ROSTER_TEMPORARY_HARD_MAXIMUM = 21
AI_DIFFICULTIES = {"easy", "normal", "hard"}
SOCIAL_INJURY_GAMES_THRESHOLD = 10
MAJOR_FREE_AGENT_AAV_THRESHOLD = 25_000_000
MAJOR_PLAYER_MPG_THRESHOLD = 29.0
MAJOR_INJURY_GAMES_THRESHOLD = 41
MAJOR_STAFF_GRADE_THRESHOLD = 82.0
AI_EXTENSION_BUCKET_LIMIT = 15
OFFSEASON_FREE_AGENT_POOL_TARGET = 120
MAJOR_STAT_LINE_THRESHOLDS = {
    "points": 49,
    "rebounds": 20,
    "assists": 20,
    "steals": 6,
    "blocks": 6,
}


def human_controlled_team_ids(save: dict[str, Any]) -> set[str]:
    """Return every protected human roster, including legacy single-player saves."""
    meta = save.get("meta") or {}
    teams = {str(team_id) for team_id in meta.get("human_team_ids") or [] if team_id}
    if meta.get("user_team_id"):
        teams.add(str(meta["user_team_id"]))
    return teams


def create_league_save(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    team_query: str,
    save_path: str | Path,
    seed: int = 1,
    ai_difficulty: str = "normal",
    game_mode: str = "standard",
    ratings_model: str = "inputs_v1",
) -> dict[str, Any]:
    from .save_recovery import ensure_new_save_path

    with save_lock(save_path):
        ensure_new_save_path(save_path)
        return _create_league_save(root, canonical, team_query, save_path, seed, ai_difficulty, game_mode, ratings_model)


def _create_league_save(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    team_query: str,
    save_path: str | Path,
    seed: int,
    ai_difficulty: str,
    game_mode: str,
    ratings_model: str = "inputs_v1",
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    from .ratings_model import INPUTS_V1, install_inputs_model, ratings_model_for

    ratings_model = ratings_model_for({"meta": {"ratings_model": ratings_model}})
    canonical_hash_value = canonical_hash(canonical)
    if ratings_model == INPUTS_V1:
        # Opening AI plans, valuations and rosters must already see input-derived traits. Work on a copy so
        # the caller's shared canonical universe keeps its baseline traits.
        canonical = {**canonical, "traits": [dict(trait) for trait in canonical.get("traits", [])]}
        install_inputs_model(canonical, Path(root))
    team = resolve_team(canonical, team_query)
    from .fantasy_draft import normalize_game_mode

    normalized_game_mode = normalize_game_mode(game_mode)
    initial_free_agent_ids = sorted(
        slot.get("player_id")
        for slot in canonical.get("roster_slots", [])
        if slot.get("player_id") and slot.get("status") == "free_agent"
    )
    opening_schedule = generate_future_schedule(root, CANONICAL_SEASON, season_start_year(CANONICAL_SEASON))
    start_date = new_career_start_date(opening_schedule)
    save = {
        "version": SAVE_VERSION,
        "meta": {
            "id": stable_id("save", CANONICAL_SEASON, team["abbrev"], seed),
            "season": CANONICAL_SEASON,
            "canonical_universe_id": canonical.get("meta", {}).get("id"),
            "canonical_hash": canonical_hash_value,
            "starting_data_version": canonical.get("meta", {}).get("starting_data_version"),
            "user_team_id": team["id"],
            "user_team_abbrev": team["abbrev"],
            "seed": seed,
            "ai_difficulty": normalize_ai_difficulty(ai_difficulty),
            "game_mode": normalized_game_mode,
            "ratings_model": ratings_model,
            "created_at": start_date,
            "gameplay_start_date": start_date,
            "source_snapshot_date": CANONICAL_START_DATE,
        },
        "state": {
            "current_date": start_date,
            "phase": phase_for_date(start_date),
            "legal_actions": [action for action in legal_actions_for_date(start_date) if action != "press_conferences"],
        },
        "schedule_state": {"simulated_game_ids": []},
        "season_schedules": {CANONICAL_SEASON: opening_schedule},
        "lifecycle_state": {"through_date": start_date, "health_game_ids": []},
        "season_history": [],
        "year_reviews": [],
        "retirement_reports": [],
        "league_awards": [],
        "roster_overrides": {
            player_id: None for player_id in initial_free_agent_ids
        },
        "contract_overrides": {},
        "draft_pick_overrides": {},
        "generated_draft_picks": [],
        "pick_obligations": load_pick_obligation_overrides(root, canonical),
        "locked_pick_assets": [],
        "draft_rights": [],
        "rookie_contracts": [],
        "incoming_rookies": [],
        "generated_players": [],
        "generated_traits": [],
        "free_agent_player_ids": initial_free_agent_ids,
        "startup_free_agents": [],
        "released_free_agents": {},
        "retired_player_ids": [],
        "league_exit_player_ids": [],
        "league_exit_records": [],
        "roster_cutdown_baselines": initial_roster_cutdown_baselines(canonical),
        "staff_slots": initialize_save_staff_slots(canonical, seed),
        "former_staff": [],
        "pending_staff_negotiations": [],
        "staff_market": [],
        "pending_trade_proposals": [],
        "pending_contract_negotiations": [],
        "pending_draft_selections": [],
        "pending_ai_actions": [],
        "user_trade_offers": [],
        "pending_roster_cutdowns": [],
        "staff_firing_history": [],
        "staff_season_changes": {},
        "staff_interim_review_due": {},
        "staff_retention_windows": [],
        "processed_hidden_ai_actions": [],
        "pending_press_events": [],
        "transaction_logs": [],
        "league_events": [],
        "game_results": [],
        "team_records": initial_team_records(canonical),
        "team_morale": initial_team_morale(canonical),
        "player_morale": initial_player_morale(canonical),
        "rotation_recommendations": {},
        "rotation_overrides": {},
        "starting_lineups": {},
        "rotation_baselines": initial_rotation_baselines(canonical),
        "rotation_snapshots": {},
        "fan_confidence": initial_team_metric(canonical, 55.0),
        "owner_confidence": initial_team_metric(canonical, 56.0),
        "team_game_logs": [],
        "player_game_logs": [],
        "player_season_stats": {},
        "playoff_state": {},
        "playoff_player_stats": {},
        "finals_mvp": None,
        "draft_state": {},
        "draft_orders": {},
        "health_states": sorted(deepcopy(canonical.get("player_health_states", [])), key=lambda item: item["player_id"]),
        "injury_events": sorted(deepcopy(canonical.get("injury_events", [])), key=lambda item: item["id"]),
        "development_events": [],
        "applied_development_months": [],
        "news_items": [],
        "social_feed": [],
        "press_conferences": [],
        "game_settings": {
            "press_conferences_enabled": False,
            "coach_rests_players": False,
        },
        "narrative_settings": default_narrative_settings(),
        "narrative_cache": {"version": NARRATIVE_PROMPT_VERSION, "social": {}, "press": {}},
        "inbox_items": [
            {
                "id": stable_id("inbox", "welcome", team["id"]),
                "date": start_date,
                "kind": "save_created",
                "headline": f"{team['abbrev']} GM mode save created.",
                "status": "unread",
            }
        ],
    }
    seed_startup_free_agents(canonical, save, seed)
    normalize_starting_rosters(canonical, save)
    merge_startup_pick_obligations(save, canonical)
    align_real_head_coach_names(canonical, save)
    from .contract_imports import initialize_imported_obligations
    initialize_imported_obligations(save, canonical)
    initialize_new_career_health(save, start_date)
    if normalized_game_mode == "fantasy_draft":
        from .fantasy_draft import initialize_fantasy_draft

        initialize_fantasy_draft(canonical, save, seed)
    else:
        initialize_new_career_runtime(canonical, save, start_date, seed)
    from .trade_ownership import LEDGER_KEY, seed_player_tenure
    save[LEDGER_KEY] = seed_player_tenure(canonical, game_mode=normalized_game_mode, root=root)
    write_save(save_path, save)
    return save


def new_career_start_date(schedule: dict[str, Any]) -> str:
    """Gameplay entry, independent of the historical canonical snapshot date."""
    dates = [game['gameDate'] for game in schedule.get('games', [])
             if game.get('phase') == 'regular' and game.get('externalGameId')]
    if not dates:
        raise ValueError('A new career requires a regular-season schedule.')
    return (date.fromisoformat(min(dates)) - timedelta(days=1)).isoformat()


def initialize_new_career_health(save: dict[str, Any], start_date: str) -> None:
    """Project dated startup availability without replaying offseason games/time.

    Keep injury history/provenance and future return dates. Clearing an already
    elapsed injury does not synthesize games missed, fatigue, rust or development.
    This is called only on creation, never as a loaded-career repair.
    """
    for state in save.get('health_states', []):
        if state.get('current_injury_id') and state.get('return_date') and state['return_date'] <= start_date:
            state.update(current_injury_id=None, availability_status='active', return_date=None)
        state['as_of_date'] = start_date


def initialize_new_career_runtime(canonical, save, start_date, seed):
    """Initialize opening roles and intent once, without executing AI actions."""
    from .contract_protection import initialize_protection
    from .team_planning import refresh_team_plans
    initialize_protection(save, canonical)
    active = canonical_with_save(canonical, save)
    if reassess_ai_roles(active, save, start_date):
        apply_save_rotation_projection(active, save)
    refresh_team_plans(active, save, start_date)
    refresh_roster_cutdowns(canonical, save, apply_ai=False)


def validate_save_document(save: Any) -> None:
    """Reject unsupported or malformed manifests before any save mutation."""
    if not isinstance(save, dict):
        raise SaveValidationError("The save JSON must contain an object. Restore a complete save export.")
    if save.get("version") != SAVE_VERSION:
        raise SaveValidationError(f"Unsupported save format {save.get('version')!r}. Use a compatible app version or restore a supported export.")
    meta = save.get("meta", {})
    if not isinstance(meta, dict):
        raise SaveValidationError("The save metadata is malformed. Restore a complete save export.")
    revision = meta.get("save_revision", 0)
    if type(revision) is not int or revision < 0:
        raise SaveValidationError("The save revision is malformed. Restore a complete save export.")
    if "save_snapshot_id" in meta and (not isinstance(meta["save_snapshot_id"], str) or not meta["save_snapshot_id"]):
        raise SaveValidationError("The save checkpoint is malformed. Restore a complete save export.")
    for key in ("state", "schedule_state", "season_schedules"):
        if key in save and not isinstance(save[key], dict):
            raise SaveValidationError(f"The save's {key} section is malformed. Restore a complete save export.")
    current_date = save.get("state", {}).get("current_date")
    if current_date is not None:
        try:
            if not isinstance(current_date, str) or date.fromisoformat(current_date).isoformat() != current_date:
                raise ValueError("expected YYYY-MM-DD")
        except ValueError as exc:
            raise SaveValidationError("The save's current date is malformed. Restore a complete save export.") from exc
    for key in HISTORY_KEYS:
        if key in save and (not isinstance(save[key], list) or any(not isinstance(row, dict) for row in save[key])):
            raise SaveValidationError(f"The save's {key} records are malformed. Restore a complete save export.")
    if "player_performance_inputs" in save:
        from .player_model import validate_input_section

        try:
            validate_input_section(save["player_performance_inputs"])
        except ValueError as exc:
            raise SaveValidationError(f"Invalid player performance inputs: {exc}") from exc


# Parsed save files by path: (file stamp, pickled parse). One GUI action reads the same manifest many times (7-34
# for an offseason or playoff action, ~0.2 s of JSON parsing each). A save is only ever replaced by a rename, so
# a new version always has a new inode and modification time; the stamp is taken before and after the read.
_PARSED_SAVES: dict[str, tuple[tuple[int, ...], bytes]] = {}


def _file_stamp(path: str) -> tuple[int, ...]:
    st = os.stat(path)
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _parse_save_file(path: str | Path) -> Any:
    key = os.path.abspath(os.fspath(path))
    before = _file_stamp(key)
    cached = _PARSED_SAVES.get(key)
    if cached is not None and cached[0] == before:
        return pickle.loads(cached[1])
    with open(key, "r", encoding="utf-8") as handle:
        save = json.load(handle)
    if _file_stamp(key) == before:
        try:
            blob = pickle.dumps(save, protocol=pickle.HIGHEST_PROTOCOL)
        except (pickle.PicklingError, TypeError, AttributeError, RecursionError):
            return save
        _PARSED_SAVES.pop(key, None)
        while len(_PARSED_SAVES) >= 4:
            _PARSED_SAVES.pop(next(iter(_PARSED_SAVES)))
        _PARSED_SAVES[key] = (before, blob)
    return save


def load_save(path: str | Path, *, include_history: bool = False) -> dict[str, Any]:
    try:
        save = _parse_save_file(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SaveValidationError(f"Cannot read save '{Path(path).name}': {exc}. Restore a complete save export.") from exc
    validate_save_document(save)
    validate_save_components(path, save)
    if include_history:
        hydrate_save_history(path, save, _validated=True)
    if "staff_season_changes" not in save:
        transactions = list(save.get("transaction_logs", []))
        events = list(save.get("league_events", []))
        if not include_history and save.get("history_store"):
            transactions.extend(load_history_records(path, save, "transaction_logs", _validated=True))
            events.extend(load_history_records(path, save, "league_events", _validated=True))
        initialize_staff_season_changes(save, transactions, events)
    return save


def write_save(path: str | Path, save: dict[str, Any]) -> None:
    """Publish history first and its manifest last, preserving the prior save.

    History versions remain visible through the old manifest if publication is
    interrupted. Work on a copy so retrying a failed write keeps every hot row.
    """
    target = Path(path)
    validate_save_document(save)
    with save_lock(target):
        from .save_recovery import finish_pending_restore

        finish_pending_restore(target)
        current = load_save(target) if target.exists() else None
        validate_save_components(target, save)
        if (current or {}).get("history_store") and not save.get("history_store"):
            raise SaveValidationError("This update is missing the save's history metadata. Reload the save before saving again.")
        committed_revision = int((current or {}).get("meta", {}).get("save_revision") or 0)
        supplied_revision = save.get("meta", {}).get("save_revision")
        if current is not None and supplied_revision is not None and supplied_revision != committed_revision:
            raise SaveValidationError("This save changed while it was open. Reload it before saving again.")
        # Legacy manifests may have neither id nor revision. Once a write or
        # restore publishes a checkpoint, every caller must match it.
        if current is not None:
            if save.get("meta", {}).get("save_snapshot_id") != current.get("meta", {}).get("save_snapshot_id"):
                raise SaveValidationError("This save was restored or changed while it was open. Reload it before saving again.")
            if (save.get("history_store") or {}).get("path") != (current.get("history_store") or {}).get("path"):
                raise SaveValidationError("This save's history component changed while it was open. Reload it before saving again.")
        supplied_snapshot = (save.get("history_store") or {}).get("snapshot_id")
        current_snapshot = ((current or {}).get("history_store") or {}).get("snapshot_id")
        if supplied_snapshot and current_snapshot and supplied_snapshot != current_snapshot:
            raise SaveValidationError("This save was restored or changed while it was open. Reload it before saving again.")
        if current is not None:
            from .save_recovery import preserve_previous_save

            preserve_previous_save(target, loaded=current)
        working = copy_plain(save)
        working.setdefault("meta", {})["save_snapshot_id"] = uuid.uuid4().hex
        dedupe_save_event_lists(working)
        # Record team changes and investments from this write's transaction logs before old logs are archived.
        from .trade_ownership import commit_tenure_ledger
        commit_tenure_ledger(working)
        archive_save_history(target, working, committed_revision + 1)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent,
                prefix=f".{target.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(encode_save_json(working))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            # The manifest is the commit point for all referenced history rows.
            temp_path.replace(target)
            fsync_directory(target.parent)
            save.clear()
            save.update(working)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()


def encode_save_json(save: dict[str, Any]) -> str:
    """The save file's text. json.dumps runs the C encoder; json.dump streams the same text through the much
    slower pure-Python encoder (2-3 s for a mature save)."""
    return json.dumps(save, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def dedupe_save_event_lists(save: dict[str, Any]) -> None:
    for key, fields in {
        "news_items": ("kind", "date", "headline"),
        "social_feed": ("kind", "date", "text", "handle"),
        "pending_press_events": ("kind", "date", "headline"),
        "league_events": ("kind", "date", "headline"),
    }.items():
        seen: set[tuple[Any, ...]] = set()
        output = []
        for item in save.get(key, []):
            marker = tuple(item.get(field) for field in fields)
            if marker in seen:
                continue
            seen.add(marker)
            output.append(item)
        save[key] = output
    seen_logs: dict[str, dict[str, Any]] = {}
    transaction_logs = []
    for item in save.get("transaction_logs", []):
        item_id = str(item.get("id") or "")
        if item_id and item_id in seen_logs and item == seen_logs[item_id]:
            continue
        if item_id:
            seen_logs[item_id] = item
        transaction_logs.append(item)
    save["transaction_logs"] = transaction_logs


def load_pick_obligation_overrides(root: str | Path, canonical: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    path = Path(root) / "data" / "overrides" / "pick_obligations_overrides.json"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return []
    if isinstance(payload, dict) and payload.get("starting_data_version") and canonical is not None:
        versions = [payload["starting_data_version"], *(payload.get("compatible_starting_data_versions") or [])]
        if (canonical.get("meta") or {}).get("starting_data_version") not in versions:
            return []
    obligations = payload.get("pick_obligations") if isinstance(payload, dict) else payload
    if not isinstance(obligations, list):
        return []
    output = []
    for item in obligations:
        if not isinstance(item, dict):
            continue
        obligation = deepcopy(item)
        obligation.setdefault("id", stable_id("pick_obligation", obligation.get("type"), obligation.get("season"), obligation.get("primary_pick_id"), obligation.get("receiver_team_id")))
        obligation.setdefault("status", "active")
        obligation.setdefault("source", "data/overrides/pick_obligations_overrides.json")
        output.append(obligation)
    from .pick_rules import ordered_pick_obligations
    return ordered_pick_obligations(output)


def protected_pick_top_n_from_text(text: str) -> int | None:
    compact = " ".join(str(text or "").split()).lower()
    match = re.search(r"\btop[- ]?(\d{1,2})\s+protected\b", compact)
    if match:
        return int(match.group(1))
    match = re.search(r"\bpicks?\s+1\s*-\s*(\d{1,2})\s+protected\b", compact)
    if match:
        return int(match.group(1))
    return None


def startup_gameplay_pick_obligations(canonical: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not canonical:
        return []
    from .transactions import clean_pick_protection_summary

    used_fallback_ids: set[str] = set()
    obligations: list[dict[str, Any]] = []
    picks = list((canonical or {}).get("draft_picks", []))
    for pick in sorted(picks, key=lambda item: (str(item.get("season") or ""), str(item.get("current_owner_team_id") or ""), str(item.get("id") or ""))):
        if int(pick.get("round") or 0) != 1:
            continue
        sender = pick.get("original_team_id")
        receiver = pick.get("current_owner_team_id")
        if not sender or not receiver or sender == receiver:
            continue
        top_n = protected_pick_top_n_from_text(clean_pick_protection_summary(pick))
        if not top_n:
            continue
        fallback = protected_pick_fallback_candidate(canonical, pick, sender, used_fallback_ids)
        if not fallback:
            fallback = create_gameplay_fallback_pick(canonical, pick, sender, used_fallback_ids)
            picks = list(canonical.get("draft_picks", []))
        if not fallback:
            canonical.setdefault("pick_obligation_audit", []).append(
                {
                    "id": stable_id("pick_obligation_audit", pick.get("id"), "missing_fallback"),
                    "primary_pick_id": pick.get("id"),
                    "status": "startup_protection_skipped_missing_fallback",
                    "notes": "No valid same-round same-or-later fallback could be selected or created.",
                }
            )
            continue
        used_fallback_ids.add(fallback["id"])
        obligations.append(
            {
                "id": stable_id("pick_obligation", "startup_gameplay", pick.get("id"), receiver, sender, top_n, fallback.get("id")),
                "type": "protected_pick",
                "season": str(pick.get("season") or ""),
                "primary_pick_id": pick.get("id"),
                "sender_team_id": sender,
                "receiver_team_id": receiver,
                "protected_range": {"from": 1, "through": top_n},
                "protected_top_n": top_n,
                "fallback_pick_ids": [fallback["id"]],
                "label": f"top-{top_n} protected",
                "status": "active",
                "source": "src_gameplay_startup_pick_obligations_v1",
                "notes": (
                    "Gameplay fallback generated for startup protected-pick clarity. If the primary lands in the protected range, "
                    "original team keeps it and the receiver gets the same-round fallback pick."
                ),
            }
        )
    return obligations


def merge_startup_pick_obligations(save: dict[str, Any], canonical: dict[str, Any] | None = None) -> int:
    from .transactions import pick_obligation_validation_errors
    from .pick_rules import protection_bounds

    if canonical is not None and save.get("generated_draft_picks"):
        canonical = deepcopy(canonical)
        existing_pick_ids = {pick.get("id") for pick in canonical.get("draft_picks", [])}
        canonical.setdefault("draft_picks", []).extend(
            deepcopy(pick)
            for pick in save.get("generated_draft_picks", [])
            if pick.get("id") and pick.get("id") not in existing_pick_ids
        )
    obligations = save.setdefault("pick_obligations", [])
    locked = set(save.setdefault("locked_pick_assets", []))
    if canonical:
        valid_obligations = []
        invalid_fallback_ids: set[str] = set()
        used_fallback_ids = {
            fallback_id
            for obligation in obligations
            if obligation.get("type") == "protected_pick"
            for fallback_id in obligation.get("fallback_pick_ids") or []
            if fallback_id
        }
        for obligation in obligations:
            if obligation.get("type") == "protected_pick":
                # An unknown range must never be repaired by dropping the condition.
                protection_bounds(obligation)
                check = {**obligation, "_existing_fallback_pick_ids": obligation.get("fallback_pick_ids") or []}
                errors = pick_obligation_validation_errors(canonical, None, check)
                if errors:
                    repaired = repair_protected_pick_fallback(obligation, canonical, used_fallback_ids)
                    if repaired:
                        check = {**repaired, "_existing_fallback_pick_ids": repaired.get("fallback_pick_ids") or []}
                        errors = pick_obligation_validation_errors(canonical, None, check)
                    if errors:
                        invalid_fallback_ids.update(obligation.get("fallback_pick_ids") or [])
                        save.setdefault("pick_obligation_audit", []).append(
                            {
                                "id": stable_id("pick_obligation_audit", obligation.get("id"), "invalid"),
                                "obligation_id": obligation.get("id"),
                                "primary_pick_id": obligation.get("primary_pick_id"),
                                "status": "removed_invalid_protected_pick",
                                "errors": errors,
                            }
                        )
                        continue
                    obligation = repaired or obligation
            elif obligation.get("type") == "pick_swap":
                errors = pick_obligation_validation_errors(canonical, None, obligation)
                if errors:
                    save.setdefault("pick_obligation_audit", []).append(
                        {
                            "id": stable_id("pick_obligation_audit", obligation.get("id"), "invalid"),
                            "obligation_id": obligation.get("id"),
                            "status": "removed_invalid_pick_swap",
                            "errors": errors,
                        }
                    )
                    continue
            valid_obligations.append(obligation)
        # Repairs can preserve the count while changing collateral. Always write the
        # validated list back so an old self/duplicate fallback cannot survive load.
        obligations[:] = valid_obligations
        locked.difference_update(invalid_fallback_ids)
    existing_primary_ids = {
        item.get("primary_pick_id")
        for item in obligations
        if item.get("type") == "protected_pick" and item.get("primary_pick_id")
    }
    existing_ids = {item.get("id") for item in obligations}
    picks = {pick.get("id"): pick for pick in (canonical or {}).get("draft_picks", [])}
    added = 0
    for obligation in startup_gameplay_pick_obligations(canonical):
        primary_id = obligation.get("primary_pick_id")
        primary = picks.get(primary_id)
        override_owner = (save.get("draft_pick_overrides") or {}).get(primary_id)
        current_owner = override_owner or (primary or {}).get("current_owner_team_id")
        if override_owner == "used_draft_pick" or current_owner == obligation.get("sender_team_id"):
            continue
        if current_owner and current_owner != obligation.get("receiver_team_id"):
            obligation = {**obligation, "receiver_team_id": current_owner}
        if primary_id in existing_primary_ids or obligation.get("id") in existing_ids:
            continue
        errors = pick_obligation_validation_errors(canonical or {}, None, obligation)
        if errors:
            repaired = repair_protected_pick_fallback(obligation, canonical or {}, set())
            obligation = repaired or obligation
            errors = pick_obligation_validation_errors(canonical or {}, None, obligation)
        if errors:
            save.setdefault("pick_obligation_audit", []).append(
                {
                    "id": stable_id("pick_obligation_audit", obligation.get("id"), "startup_invalid"),
                    "obligation_id": obligation.get("id"),
                    "primary_pick_id": primary_id,
                    "status": "startup_protection_skipped_invalid",
                    "errors": errors,
                }
            )
            continue
        obligations.append(obligation)
        existing_primary_ids.add(primary_id)
        existing_ids.add(obligation.get("id"))
        added += 1
    active_fallbacks = {
        fallback_id
        for obligation in obligations
        if obligation.get("type") == "protected_pick" and obligation.get("status", "active") in {"active", "pending_resolution"}
        for fallback_id in obligation.get("fallback_pick_ids") or []
        if fallback_id
    }
    save["locked_pick_assets"] = sorted(active_fallbacks)
    generated_by_id = {
        pick.get("id"): pick
        for pick in save.get("generated_draft_picks", [])
        if pick.get("id")
    }
    for pick in (canonical or {}).get("draft_picks", []):
        if pick.get("status") == "gameplay_fallback_pick" and pick.get("id"):
            generated_by_id[pick["id"]] = deepcopy(pick)
    save["generated_draft_picks"] = [generated_by_id[pick_id] for pick_id in sorted(generated_by_id)]
    return added


def repair_protected_pick_fallback(obligation: dict[str, Any], canonical: dict[str, Any], used_fallback_ids: set[str] | None = None) -> dict[str, Any] | None:
    primary_id = obligation.get("primary_pick_id")
    if not primary_id:
        return None
    primary = next((pick for pick in canonical.get("draft_picks", []) if pick.get("id") == primary_id), None)
    if not primary:
        return None
    sender = obligation.get("sender_team_id") or primary.get("original_team_id")
    used = set(used_fallback_ids or set()) - set(obligation.get("fallback_pick_ids") or [])
    fallback = protected_pick_fallback_candidate(canonical, primary, sender, used)
    if not fallback:
        fallback = create_gameplay_fallback_pick(canonical, primary, sender, used)
    if not fallback:
        return None
    repaired = {**obligation, "fallback_pick_ids": [fallback["id"]]}
    repaired["id"] = stable_id("pick_obligation", repaired.get("type"), repaired.get("primary_pick_id"), repaired.get("receiver_team_id"), fallback["id"])
    repaired["notes"] = f"{repaired.get('notes', '')} Invalid fallback repaired deterministically to {fallback['id']}.".strip()
    if used_fallback_ids is not None:
        used_fallback_ids.add(fallback["id"])
    return repaired


def protected_pick_fallback_candidate(
    canonical: dict[str, Any],
    primary: dict[str, Any],
    sender_team_id: str | None,
    used_fallback_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    from .transactions import protected_pick_fallback_is_distinct

    if not primary or not sender_team_id:
        return None
    primary_id = primary.get("id")
    primary_round = int(primary.get("round") or 0)
    primary_year = pick_season_start_local(primary)
    used = set(used_fallback_ids or set())
    candidates = sorted(
        [
            pick
            for pick in canonical.get("draft_picks", [])
            if pick.get("id")
            and pick.get("id") != primary_id
            and pick.get("id") not in used
            and int(pick.get("round") or 0) == primary_round
            and pick.get("original_team_id") == sender_team_id
            and pick.get("current_owner_team_id") == sender_team_id
            and pick_season_start_local(pick) >= primary_year
            and protected_pick_fallback_is_distinct(primary, pick)
            and not pick.get("_obligation_locked")
        ],
        key=lambda pick: (pick_season_start_local(pick), str(pick.get("id") or "")),
    )
    return candidates[0] if candidates else None


def create_gameplay_fallback_pick(
    canonical: dict[str, Any],
    primary: dict[str, Any],
    sender_team_id: str | None,
    used_fallback_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    if not canonical or not primary or not sender_team_id:
        return None
    primary_round = int(primary.get("round") or 0)
    primary_year = pick_season_start_local(primary)
    if primary_round not in {1, 2} or primary_year <= 0:
        return None
    teams = {team.get("id"): team.get("abbrev") for team in canonical.get("teams", [])}
    abbrev = str(teams.get(sender_team_id) or sender_team_id.replace("team_", "")).lower()
    existing_ids = {pick.get("id") for pick in canonical.get("draft_picks", [])}
    used = set(used_fallback_ids or set())
    for offset in range(1, 9):
        year = primary_year + offset
        pick_id = f"pick_gameplay-fallback-{abbrev}-{year}-{primary_round}-{stable_id(primary.get('id'), sender_team_id, year)[-8:]}"
        if pick_id in existing_ids or pick_id in used:
            continue
        fallback = {
            "id": pick_id,
            "season": str(year),
            "round": primary_round,
            "original_team_id": sender_team_id,
            "current_owner_team_id": sender_team_id,
            "status": "gameplay_fallback_pick",
            "confidence": 0.38,
            "source_ids": ["src_gameplay_startup_pick_obligations_v1"],
            "notes": "Deterministic gameplay fallback created so protected-pick obligations never point to the primary pick.",
        }
        canonical.setdefault("draft_picks", []).append(fallback)
        return fallback
    return None


def pick_season_start_local(pick: dict[str, Any]) -> int:
    try:
        return int(str(pick.get("season") or "0").split("-")[0])
    except (TypeError, ValueError):
        return 0


def seed_startup_free_agents(canonical: dict[str, Any], save: dict[str, Any], seed: int, target_count: int = 30) -> None:
    retired = set(save.get("retired_player_ids", []))
    existing_free = [
        player for player in canonical.get("players", [])
        if not player.get("team_id") and player.get("id") not in retired
    ]
    existing_free = sorted(existing_free, key=lambda player: (display_minutes_projection(player), player.get("name") or ""), reverse=True)
    free_ids = [player["id"] for player in existing_free[:target_count] if player.get("id")]
    save.setdefault("free_agent_player_ids", [])
    for player_id in free_ids:
        if player_id not in save["free_agent_player_ids"]:
            save["free_agent_player_ids"].append(player_id)
    needed = max(0, target_count - len(save["free_agent_player_ids"]))
    if needed:
        rng = random.Random(f"{seed}:{save.get('meta', {}).get('user_team_id')}:startup_free_agents")
        positions = ["PG", "SG", "SF", "PF", "C"]
        firsts = [
            "Andre", "Arman", "Bennett", "Bryce", "Caleb", "Cameron", "Cole", "Darius", "Devin", "Eli",
            "Emmett", "Frank", "Gabe", "Hayes", "Isaiah", "Jalen", "Jonah", "Julian", "Kellan", "Kendrick",
            "Luca", "Malik", "Mason", "Miles", "Nico", "Noel", "Owen", "Quentin", "Reid", "Riley",
            "Silas", "Theo", "Trey", "Vince", "Wesley", "Zion",
        ]
        lasts = [
            "Adams", "Alexander", "Baldwin", "Banks", "Bishop", "Brooks", "Caldwell", "Carter", "Clayton", "Coleman",
            "Daniels", "Dawson", "Ellis", "Foster", "Franklin", "Gaines", "Garrett", "Grant", "Hampton", "Hayes",
            "Holland", "Irving", "Jefferson", "James", "Knight", "Lawson", "Lewis", "Maddox", "Marshall", "Mercer",
            "Morris", "Nolan", "Parker", "Pierce", "Porter", "Price", "Reed", "Reynolds", "Rhodes", "Russell",
            "Sanders", "Shelton", "Simmons", "Spencer", "Stone", "Sullivan", "Taylor", "Turner", "Walker", "Wallace",
            "Warren", "Watkins", "Webster", "West", "Whitaker", "Williams", "Wilson", "Wright", "Young", "Zimmer",
        ]
        used_names = {normalize_name(player.get("name", "")) for player in save.get("generated_players", [])}
        used_lasts: set[str] = set()
        for index in range(needed):
            position = rng.choice(positions)
            last_choices = [last for last in lasts if last not in used_lasts] or lasts
            for attempt in range(200):
                last = rng.choice(last_choices)
                first = rng.choice(firsts)
                name = f"{first} {last}"
                if normalize_name(name) not in used_names:
                    break
                if attempt == 100:
                    last_choices = lasts
            used_names.add(normalize_name(name))
            used_lasts.add(name.split()[-1])
            player_id = stable_id("startup_fa", save.get("meta", {}).get("id"), index, name)
            player = {
                "id": player_id,
                "name": name,
                "normalized_name": normalize_name(name),
                "slug": player_id.replace("startup_fa_", ""),
                "team_id": None,
                "team_abbrev": "FA",
                "position": position,
                "age": round(rng.uniform(22.0, 34.0), 1),
                "age_base_season": save.get("meta", {}).get("season") or CANONICAL_SEASON,
                "age_base_start_year": season_start_year(save.get("meta", {}).get("season") or CANONICAL_SEASON),
                "height_inches": {"PG": 74, "SG": 77, "SF": 80, "PF": 82, "C": 83}[position] + rng.uniform(-1.5, 1.5),
                "weight_lbs": round({"PG": 185, "SG": 200, "SF": 215, "PF": 230, "C": 245}[position] + rng.uniform(-18, 18), 1),
                "minutes_projection": round(rng.uniform(0.0, 6.0), 1),
                "rotation_priority": "startup_free_agent_replacement",
                "market_status": "unsigned_startup_free_agent",
                "asking_salary_millions": round(rng.uniform(1.1, 2.6), 2),
                "asking_years": 1,
                "trade_eligible": False,
                "source_ids": ["src_startup_free_agent_scaffold_v1"],
                "missing_critical_fields": [],
                "critical_field_fallbacks": {},
                "notes": "Generated low-end unsigned replacement player seeded at save creation.",
            }
            save.setdefault("generated_players", []).append(player)
            save.setdefault("generated_traits", []).extend(generated_replacement_traits(player, seed))
            save.setdefault("free_agent_player_ids", []).append(player_id)
    save["free_agent_player_ids"] = sorted(dict.fromkeys(save.get("free_agent_player_ids", [])))
    save["startup_free_agents"] = sorted(dict.fromkeys(save.get("free_agent_player_ids", [])[:target_count]))


def save_season_start_year(save: dict[str, Any]) -> int:
    season = str((save.get("meta") or {}).get("season") or CANONICAL_SEASON)
    try:
        return int(season.split("-")[0])
    except (TypeError, ValueError):
        return season_start_year(CANONICAL_SEASON)


def recent_rookie_protected_player_ids(save: dict[str, Any]) -> set[str]:
    current_start = save_season_start_year(save)
    protected: set[str] = set()
    for player in save.get("generated_players", []):
        try:
            draft_year = int(player.get("draft_year") or 0)
        except (TypeError, ValueError):
            draft_year = 0
        if draft_year and draft_year >= current_start - 1:
            protected.add(player.get("id"))
    for rookie in save.get("incoming_rookies", []):
        try:
            draft_year = int(rookie.get("draft_year") or rookie.get("season") or 0)
        except (TypeError, ValueError):
            draft_year = 0
        if draft_year and draft_year >= current_start - 1:
            protected.add(rookie.get("player_id") or rookie.get("id"))
    return {player_id for player_id in protected if player_id}


def repair_unpooled_unrostered_players(canonical: dict[str, Any], save: dict[str, Any]) -> int:
    """Restore legacy roster cuts that were omitted from the free-agent pool."""
    free_agents = set(save.get("free_agent_player_ids") or [])
    retired = set(save.get("retired_player_ids") or [])
    from .waivers import pending_ids
    retired |= pending_ids(save)
    unsigned_rights = {
        row.get("player_id")
        for row in save.get("incoming_rookies", [])
        if row.get("player_id") and row.get("rights_status") == "exclusive_unsigned_rights"
    }
    players = {
        player.get("id"): player
        for player in [*canonical.get("players", []), *save.get("generated_players", [])]
        if player.get("id")
    }
    date_value = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    repaired = 0
    for player_id, team_id in (save.get("roster_overrides") or {}).items():
        if (
            team_id is not None
            or player_id in free_agents
            or player_id in retired
            or player_id in unsigned_rights
            or player_id not in players
        ):
            continue
        player = players[player_id]
        free_agents.add(player_id)
        save.setdefault("released_free_agents", {}).setdefault(
            player_id,
            {
                "player_id": player_id,
                "player_name": player.get("name"),
                "waived_by_team_id": None,
                "waived_by_team_abbrev": None,
                "release_date": date_value,
                "status": "available",
                "reason": "legacy_unpooled_roster_cut_repair",
            },
        )
        repaired += 1
    if repaired:
        save["free_agent_player_ids"] = sorted(free_agents)
    return repaired


def refresh_roster_cutdowns(canonical: dict[str, Any] | None, save: dict[str, Any], *, apply_ai: bool = True) -> None:
    if canonical is None or not is_league_save(save):
        save.setdefault("pending_roster_cutdowns", [])
        return
    # The 15-man limit binds from training camp through the season. In the offseason (draft night, re-signing, free
    # agency) rosters may run over, as in the NBA; a draft pick that makes 16 must not force a cut-down mid-draft.
    if (save.get("state") or {}).get("phase") not in ROSTER_CUTDOWN_PHASES:
        save["pending_roster_cutdowns"] = []
        return
    active = active_players_for_roster_checks(canonical, save)
    human_team_ids = human_controlled_team_ids(save)
    date_value = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    retention_context = None
    retention_players: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    free_agents = set(save.get("free_agent_player_ids") or [])
    for team in canonical.get("teams", []):
        players = [player for player in active if player.get("team_id") == team.get("id")]
        target_count = roster_cutdown_target(save, team.get("id"))
        if len(players) <= target_count:
            continue
        overflow = len(players) - target_count
        if team.get("id") not in human_team_ids:
            if not apply_ai:
                continue
            if retention_context is None:
                retention_context = roster_retention_context(canonical, save)
                retention_players = {player["id"]: player for player in retention_context.get("players", [])}
            cuttable = sorted(
                (retention_players.get(player["id"], player) for player in players),
                key=lambda player: (
                    ai_roster_retention_score(retention_context, save, player),
                    player.get("name") or "",
                    player["id"],
                ),
            )
            for player in cuttable[:overflow]:
                player_id = player["id"]
                from .waivers import request_waiver
                request_waiver(retention_context, save, player, team['id'], date_value)
                free_agents.discard(player_id)
                save.setdefault("rotation_recommendations", {}).pop(player_id, None)
                save.setdefault("rotation_snapshots", {}).pop(team.get("id"), None)
                save.setdefault("starting_lineups", {}).pop(team.get("id"), None)
                add_news(
                    save,
                    "roster_cut",
                    f"{team.get('abbrev')} waived {player.get('name')} to reach the roster limit.",
                    date_value=date_value,
                )
                upsert_by_id(
                    save,
                    "transaction_logs",
                    {
                        "id": stable_id("transaction_log", "ai_roster_cut", date_value, team.get("id"), player_id),
                        "date": date_value,
                        "transaction_type": "roster_cut",
                        "proposal_id": stable_id("ai_roster_cut", date_value, team.get("id"), player_id),
                        "status": "applied_to_save_ledger",
                        "teams": [team.get("id")],
                        "assets": {"player_id": player_id, "name": player.get("name"), "waived_by_team_id": team.get("id")},
                        "evaluations": [],
                        "source_ids": ["src_contract_market_config_v1"],
                        "notes": "AI preseason roster cut starts the two-day waiver period.",
                    },
                )
            continue
        pending.append(
            {
                "id": stable_id("roster_cutdown", team.get("id"), save.get("meta", {}).get("season"), date_value),
                "team_id": team.get("id"),
                "team_abbrev": team.get("abbrev"),
                "current_count": len(players),
                "target_count": target_count,
                "cut_required": overflow,
                "status": "mandatory_before_regular_season",
                "date": date_value,
                "notes": "Roster overflow is allowed during transactions, but the user must cut to the regular-season limit before advancing into games.",
            }
        )
    save["free_agent_player_ids"] = sorted(free_agents)
    save["pending_roster_cutdowns"] = pending


def initial_roster_cutdown_baselines(canonical: dict[str, Any]) -> dict[str, int]:
    return {
        team.get("id"): ROSTER_SEASON_MAXIMUM
        for team in canonical.get("teams", [])
        if team.get("id")
    }


def normalize_starting_rosters(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    """Trim preseason source rosters to the game's active 15-player limit.

    Source ingestion intentionally keeps every camp/two-way record it can
    verify. A playable save needs one legal opening roster, so the lowest
    rotation-value overflow enters the ordinary free-agent pool before the
    user sees the team. Later user-created overflows still use cutdown prompts.
    """
    active = active_players_for_roster_checks(canonical, save)
    free_agents = set(save.get("free_agent_player_ids") or [])
    for team in canonical.get("teams", []):
        roster = sorted(
            [player for player in active if player.get("team_id") == team.get("id")],
            key=lambda player: (roster_cut_score(canonical, player), player.get("name") or ""),
        )
        overflow = max(0, len(roster) - ROSTER_SEASON_MAXIMUM)
        for player in roster[:overflow]:
            player_id = player.get("id")
            if not player_id:
                continue
            save.setdefault("roster_overrides", {})[player_id] = None
            free_agents.add(player_id)
    save["free_agent_player_ids"] = sorted(free_agents)


def roster_cutdown_target(save: dict[str, Any], team_id: str | None) -> int:
    return ROSTER_SEASON_MAXIMUM


def initial_rotation_baselines(canonical: dict[str, Any]) -> dict[str, float]:
    return {
        player["id"]: display_minutes_projection(player)
        for player in canonical.get("players", [])
        if player.get("id")
    }


def active_players_for_roster_checks(canonical: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    players = copy_plain(canonical.get("players", []))
    retired = set(save.get("retired_player_ids", []))
    existing = {player.get("id") for player in players}
    for player in save.get("generated_players", []):
        if player.get("id") not in existing:
            players.append(copy_plain(player))
            existing.add(player.get("id"))
    teams_by_id = {team.get("id"): team for team in canonical.get("teams", [])}
    overrides = save.get("roster_overrides") or {}
    for player in players:
        if player.get("id") in overrides:
            team_id = overrides.get(player.get("id"))
            player["team_id"] = team_id
            team = teams_by_id.get(team_id)
            player["team_abbrev"] = team.get("abbrev") if team else "FA"
    return [player for player in players if player.get("team_id") and player.get("id") not in retired]


def roster_cut_score(canonical: dict[str, Any], player: dict[str, Any]) -> float:
    attrs = player_attribute_summary(canonical, player.get("id"))
    minutes = display_minutes_projection(player)
    age = float(player.get("display_age", player.get("age")) or 27.0)
    salary = 0.0
    try:
        table = player_salary_table(canonical, player.get("id"))
        salary = float(next((value for _, value in sorted(table.items()) if value is not None), 0.0) or 0.0)
    except (TypeError, ValueError):
        salary = 0.0
    value = float(attrs.get("overall") or 50.0) * 0.72 + minutes * 1.35
    value -= max(0.0, age - 31.0) * 1.1
    value -= max(0.0, salary - 8.0) * 0.12
    if str(player.get("rotation_priority") or "") in {"core_rotation", "starter"}:
        value += 18.0
    return value


def roster_retention_context(
    canonical: dict[str, Any], save: dict[str, Any], *, prepared_active: bool = False,
) -> dict[str, Any]:
    """Evaluate saved talent and a healthy rotation, without changing the save."""
    if prepared_active:
        # Rotation changes player scalars and these two save maps, not history
        # or trait rows. Share the remaining inputs as read-only projections.
        retention_save = {**save, "rotation_baselines": dict(save.get("rotation_baselines") or {}),
                          "rotation_snapshots": {}}
        active = {key: value for key, value in canonical.items() if not str(key).startswith("_")}
        active["players"] = [dict(player) for player in canonical.get("players", [])]
    else:
        retention_save = _copy_runtime_tree(save)
        active = canonical_with_save(canonical, retention_save)
    active["_allow_internal_caches"] = True
    # A short absence must not turn a retained starter into zero-minute depth.
    # Actual injury effects already present in the traits remain in this view.
    retention_save["health_states"] = []
    apply_save_rotation_projection(active, retention_save)
    return active


def ai_roster_retention_score(canonical: dict[str, Any], save: dict[str, Any], player: dict[str, Any]) -> float:
    """Keep current contributors and bounded upside, not draft-class immunity."""
    attrs = player_attribute_summary(canonical, player["id"])
    age = float(player.get("display_age", player.get("age")) or 27.0)
    minutes = display_minutes_projection(player)
    value = float(attrs["overall"]) + min(32.0, minutes) * 0.20
    value -= max(0.0, age - 31.0) * 1.1
    if player.get("rotation_priority") in {"core_rotation", "starter"}:
        value += 2.0
    potential = maybe_float(player.get("potential"))
    ability = maybe_float(player.get("current_ability"))
    if potential is not None and ability is not None:
        youth = clamp((27.0 - age) / 6.0, 0.0, 1.0)
        value += clamp((potential - ability) * 0.15, 0.0, 6.0) * youth
    try:
        seasons_since_draft = season_start_year(save_active_contract_season(save)) - int(player.get("draft_year") or 0)
    except (TypeError, ValueError):
        seasons_since_draft = -1
    if 0 <= seasons_since_draft < 2:
        value += 4.0 - seasons_since_draft * 2.0
    salary = player_salary_table(canonical, player["id"]).get(save_active_contract_season(save))
    if salary is not None:
        # Cheap contracts have value; expensive guaranteed salary is not saved
        # simply by waiving its player, so it is not a reason to cut a star.
        value += clamp((8.0 - salary) * 0.15, 0.0, 1.0)
    from .contract_protection import waiver_projection
    obligation = waiver_projection(canonical, save, player, player.get('team_id'))
    value += min(8.0, obligation['remaining_cost_millions']*.12)
    if player['id'] in save.get('team_plans', {}).get(player.get('team_id'), {}).get('core_ids', []):
        value += 3.0
    return round(value, 6)


def is_league_save(save: dict[str, Any]) -> bool:
    return save.get("version") == SAVE_VERSION


def ensure_league_save_defaults(save: dict[str, Any], canonical: dict[str, Any] | None = None) -> dict[str, Any]:
    if canonical is not None:
        canonical = baseline_for_save(canonical, save)
    if not is_league_save(save):
        return save
    if canonical is not None:
        from .contract_protection import initialize_protection
        initialize_protection(save, canonical)
    save.setdefault("meta", {}).setdefault("ai_difficulty", "normal")
    save["meta"]["ai_difficulty"] = normalize_ai_difficulty(save["meta"].get("ai_difficulty"))
    save.setdefault("schedule_state", {}).setdefault("simulated_game_ids", [])
    save.setdefault("season_schedules", {})
    save.setdefault("season_history", [])
    save.setdefault("year_reviews", [])
    save.setdefault("retirement_reports", [])
    save.setdefault("league_awards", [])
    save.setdefault("roster_overrides", {})
    save.setdefault("team_trade_wants", {})
    save.setdefault("contract_overrides", {})
    save.setdefault("draft_pick_overrides", {})
    save.setdefault("generated_draft_picks", [])
    save.setdefault("pick_obligations", [])
    save.setdefault("locked_pick_assets", [])
    fantasy_mode = str((save.get("meta") or {}).get("game_mode") or "standard") == "fantasy_draft"
    needs_repair = int(save.get("meta", {}).get("repair_version") or 0) < SAVE_REPAIR_VERSION
    if not fantasy_mode and needs_repair:
        merge_startup_pick_obligations(save, canonical)
        repair_reacquired_pick_obligations(save, canonical)
    save.setdefault("draft_rights", [])
    save.setdefault("rookie_contracts", [])
    save.setdefault("incoming_rookies", [])
    save.setdefault("generated_players", [])
    save.setdefault("generated_traits", [])
    save.setdefault("free_agent_player_ids", [])
    save.setdefault("startup_free_agents", [])
    save.setdefault("released_free_agents", {})
    save.setdefault("waiver_wire", [])
    save.setdefault("retired_player_ids", [])
    save.setdefault("league_exit_player_ids", [])
    save.setdefault("league_exit_records", [])
    if "roster_cutdown_baselines" not in save:
        save["roster_cutdown_baselines"] = initial_roster_cutdown_baselines(canonical or {"players": [], "teams": []})
    save.setdefault("pending_trade_proposals", [])
    save.setdefault("pending_contract_negotiations", [])
    save.setdefault("pending_draft_selections", [])
    save.setdefault("pending_staff_negotiations", [])
    save.setdefault("pending_ai_actions", [])
    save.setdefault("user_trade_offers", [])
    save.setdefault("pending_roster_cutdowns", [])
    save.setdefault("staff_firing_history", [])
    save.setdefault("staff_season_changes", {})
    save.setdefault("staff_interim_review_due", {})
    save.setdefault("staff_retention_windows", [])
    save.setdefault("processed_hidden_ai_actions", [])
    save.setdefault("processed_ai_extensions", [])
    save.setdefault("ai_trade_pressure_player_ids", [])
    save.setdefault("pending_press_events", [])
    save.setdefault("transaction_logs", [])
    save.setdefault("league_events", [])
    save.setdefault("game_results", [])
    save.setdefault("game_result_summaries", [])
    if canonical is not None and "player_tenure" not in save:
        from .trade_ownership import LEDGER_KEY, seed_player_tenure
        save[LEDGER_KEY] = seed_player_tenure(canonical, game_mode=str((save.get("meta") or {}).get("game_mode") or "standard"))
    if "team_morale" not in save:
        save["team_morale"] = initial_team_morale(canonical or {"teams": []})
    if "player_morale" not in save:
        save["player_morale"] = initial_player_morale(canonical or {"players": []})
    save.setdefault("rotation_recommendations", {})
    save.setdefault("rotation_overrides", {})
    save.setdefault("starting_lineups", {})
    if "rotation_baselines" not in save:
        save["rotation_baselines"] = initial_rotation_baselines(canonical or {"players": []})
    save.setdefault("rotation_snapshots", {})
    if "fan_confidence" not in save:
        save["fan_confidence"] = initial_team_metric(canonical or {"teams": []}, 55.0)
    if "owner_confidence" not in save:
        save["owner_confidence"] = initial_team_metric(canonical or {"teams": []}, 56.0)
    save.setdefault("playoff_state", {})
    save.setdefault("draft_state", {})
    save.setdefault("draft_orders", {})
    save.setdefault("team_game_logs", [])
    save.setdefault("player_game_logs", [])
    save.setdefault("development_trait_totals", {})
    save.setdefault("player_season_stats", {})
    save.setdefault("playoff_player_stats", {})
    save.setdefault("finals_mvp", None)
    save.setdefault("news_items", [])
    save.setdefault("social_feed", [])
    save.setdefault("press_conferences", [])
    ensure_game_settings(save)
    ensure_narrative_state(save)
    save.setdefault("inbox_items", [])
    save.setdefault("free_agency_prepared_seasons", [])
    fantasy_state = save.get("fantasy_draft_state") or {}
    has_fantasy_progress = bool(
        save.get("game_results")
        or save.get("season_history")
        or save.get("transaction_logs")
        or fantasy_state.get("selections")
    )
    if (
        needs_repair
        and fantasy_mode
        and canonical is not None
        and fantasy_state.get("status") not in {"in_progress", "completed"}
        and not has_fantasy_progress
    ):
        # Early GUI builds could mark a save as fantasy mode without preserving
        # its mandatory setup state. Repair only untouched saves so a malformed
        # launch cannot silently become a standard-roster regular season.
        from .fantasy_draft import initialize_fantasy_draft

        save.setdefault("meta", {})["season"] = CANONICAL_SEASON
        if not save.setdefault('state', {}).get('current_date'):
            save['state']['current_date'] = save['meta'].get('gameplay_start_date') or CANONICAL_START_DATE
        initialize_fantasy_draft(
            canonical,
            save,
            int(save.get("meta", {}).get("seed") or 1),
        )
        fantasy_state = save.get("fantasy_draft_state") or {}
    if fantasy_mode and fantasy_state.get("status") == "in_progress":
        fantasy_state.setdefault("watchlists", {})
        save.setdefault("meta", {})["season"] = CANONICAL_SEASON
        if not save.setdefault('state', {}).get('current_date'):
            save['state']['current_date'] = save['meta'].get('gameplay_start_date') or CANONICAL_START_DATE
    current_date = save.get("state", {}).get("current_date")
    if current_date:
        fantasy_in_progress = fantasy_mode and (save.get("fantasy_draft_state") or {}).get("status") == "in_progress"
        save.setdefault("state", {})["phase"] = "fantasy_draft" if fantasy_in_progress else phase_for_date(current_date)
        save["state"]["legal_actions"] = (
            ["fantasy_draft_pick"]
            if fantasy_in_progress
            else save_legal_actions_for_date(save, current_date)
        )
        if needs_repair:
            expire_user_trade_offers_after_deadline(save, current_date)
    if needs_repair:
        clean_free_agency_state(save, save.get("meta", {}).get("season"))
    if canonical is not None:
        if "team_records" not in save:
            save["team_records"] = initial_team_records(canonical)
        if "health_states" not in save:
            save["health_states"] = sorted(deepcopy(canonical.get("player_health_states", [])), key=lambda item: item["player_id"])
        if "injury_events" not in save:
            save["injury_events"] = sorted(deepcopy(canonical.get("injury_events", [])), key=lambda item: item["id"])
        save.setdefault("development_events", [])
        save.setdefault("applied_development_months", [])
        if not save.get("staff_slots"):
            save["staff_slots"] = initialize_save_staff_slots(canonical, int(save.get("meta", {}).get("seed") or 1))
        if not save.get("startup_free_agents") and not save.get("free_agent_player_ids"):
            seed_startup_free_agents(canonical, save, int(save.get("meta", {}).get("seed") or 1))
        if needs_repair:
            repair_unpooled_unrostered_players(canonical, save)
            align_real_head_coach_names(canonical, save)
            seed_morale_if_flat(canonical, save)
            refresh_roster_cutdowns(canonical, save)
    if needs_repair:
        dedupe_save_event_lists(save)
        sync_social_from_news(save)
        dedupe_save_event_lists(save)
        save.setdefault("meta", {})["repair_version"] = SAVE_REPAIR_VERSION
    season = str((save.get("meta") or {}).get("season") or CANONICAL_SEASON)
    baseline_active = None
    if canonical and season not in save.setdefault("award_preseason_baselines", {}) and (save.get("fantasy_draft_state") or {}).get("status") != "in_progress":
        from .dashboard_metrics import build_award_baselines

        baseline_save = deepcopy(save)
        baseline_save["development_events"] = [event for event in save.get("development_events", []) if str(event.get("month") or event.get("date") or "") < f"{season[:4]}-10"]
        baseline_active = canonical_with_save(canonical, baseline_save)
        save["award_preseason_baselines"][season] = build_award_baselines(baseline_active, baseline_save)
    team_id = (save.get("meta") or {}).get("user_team_id")
    draft_year = str(int(season[:4]) + 1)
    board_key = f"{team_id}:{draft_year}"
    if canonical and team_id and board_key not in save.setdefault("prospect_preseason_ranks", {}):
        from .draft import draft_board_report

        baseline_active = baseline_active or canonical_with_save(canonical, save)
        board = draft_board_report(baseline_active, team_id, draft_year)
        save["prospect_preseason_ranks"][board_key] = {entry["prospect"]["id"]: int(entry.get("board_rank") or 999) for entry in board.get("entries", [])}
    return save


def repair_reacquired_pick_obligations(save: dict[str, Any], canonical: dict[str, Any] | None = None) -> None:
    picks = {pick.get("id"): pick for pick in (canonical or {}).get("draft_picks", [])}
    locked = set(save.setdefault("locked_pick_assets", []))
    overrides = save.setdefault("draft_pick_overrides", {})
    for obligation in save.setdefault("pick_obligations", []):
        if obligation.get("type") != "protected_pick":
            continue
        if obligation.get("status", "active") not in {"active", "pending_resolution"}:
            continue
        pick_id = obligation.get("primary_pick_id")
        sender = obligation.get("sender_team_id")
        if not pick_id or not sender:
            continue
        current_owner = overrides.get(pick_id) or (picks.get(pick_id) or {}).get("current_owner_team_id")
        if current_owner != sender:
            continue
        obligation["status"] = "resolved_reacquired_by_sender"
        obligation.setdefault("resolved_date", (save.get("state") or {}).get("current_date"))
        obligation["notes"] = f"{obligation.get('notes', '')} Sender reacquired protected-pick rights before resolution; fallback unlocked.".strip()
        for fallback_id in obligation.get("fallback_pick_ids") or []:
            locked.discard(fallback_id)
    save["locked_pick_assets"] = sorted(locked)


def prune_rotation_recommendations(save: dict[str, Any], canonical: dict[str, Any] | None = None) -> int:
    recommendations = save.setdefault("rotation_recommendations", {})
    if not recommendations:
        return 0
    players = {
        player.get("id"): player
        for player in [*((canonical or {}).get("players", [])), *save.get("generated_players", [])]
        if player.get("id")
    }
    retired = set(save.get("retired_player_ids") or [])
    free_agents = set(save.get("free_agent_player_ids") or [])
    roster_overrides = save.get("roster_overrides") or {}
    removed = 0
    touched_teams: set[str] = set()
    for player_id, rec in list(recommendations.items()):
        player = players.get(player_id)
        rec_team = rec.get("team_id")
        actual_team = roster_overrides.get(player_id, (player or {}).get("team_id"))
        stale = (
            not player
            or player_id in retired
            or player_id in free_agents
            or not actual_team
            or (rec_team and actual_team != rec_team)
            or rec.get("status") not in {None, "", "active"}
        )
        if not stale:
            continue
        recommendations.pop(player_id, None)
        removed += 1
        if rec_team:
            touched_teams.add(rec_team)
        if actual_team:
            touched_teams.add(actual_team)
    for team_id in touched_teams:
        save.setdefault("rotation_snapshots", {}).pop(team_id, None)
    return removed


def set_save_date_phase(save: dict[str, Any], date_value: str) -> None:
    save["state"] = {
        "current_date": date_value,
        "phase": phase_for_date(date_value),
        "legal_actions": legal_actions_for_date(date_value),
    }


def save_active_contract_season(save: dict[str, Any]) -> str:
    season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    current = str(save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
    end_year = season_end_year(season)
    if current >= f"{end_year}-06-22":
        return season_label_from_start(season_start_year(season) + 1)
    return season


def _copy_runtime_tree(value: Any) -> Any:
    """Copy owned data graphs in C, retaining alias/cycle isolation semantics."""
    # These bytes are produced and consumed here, never read from a save,
    # network or pickle file. On-disk saves remain JSON/SQLite, not pickle.
    try:
        return pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
    except (pickle.PicklingError, TypeError, AttributeError):
        return deepcopy(value)


def canonical_with_save(canonical: dict[str, Any] | Any, save: dict[str, Any]) -> dict[str, Any]:
    """Return a disposable active universe with one save's overrides applied.

    The input canonical universe remains untouched. Derived transaction and
    simulation context is intentionally discarded when save-owned inputs may
    have changed.
    """
    if isinstance(canonical, dict):
        canonical = baseline_for_save(canonical, save)
        if is_league_save(save):
            # Which real prospects declare for the next draft differs by save (cached per seed, same object).
            from .draft import draft_class_for_save
            canonical = draft_class_for_save(canonical, (save.get("meta") or {}).get("seed"))
        # Derived indexes belong to the source object. Copying them bloats the
        # active universe and can omit save-generated players or contracts.
        runtime = _ADVANCE_RUNTIME_STATE.get()
        canonical = (runtime.baseline_copy(canonical) if runtime is not None else
                     _copy_runtime_tree({key: value for key, value in canonical.items() if not str(key).startswith("_")}))
    else:
        canonical = _copy_runtime_tree(baseline_for_save(to_plain(canonical), save))
    canonical["_allow_internal_caches"] = True
    if not is_league_save(save):
        return canonical
    active_season = save_active_contract_season(save)
    canonical.setdefault("meta", {})["active_season"] = active_season
    canonical.setdefault("meta", {})["current_date"] = save.get("state", {}).get("current_date")
    class_seed = save.get("meta", {}).get("seed")
    canonical["meta"]["draft_class_seed"] = int(class_seed if class_seed is not None else 1)
    canonical["save_team_records"] = copy_plain(save.get("team_records", {}))
    canonical["transaction_logs"] = copy_plain(save.get("transaction_logs", []))
    canonical['waived_salary_obligations'] = copy_plain(save.get('waived_salary_obligations', []))
    canonical['waiver_wire'] = copy_plain(save.get('waiver_wire', []))
    canonical['team_plans'] = copy_plain(save.get('team_plans', {}))
    canonical['team_trade_wants'] = copy_plain(save.get('team_trade_wants', {}))
    canonical['team_payroll_history'] = save.get('team_payroll_history') or {}  # read-only: repeat taxpayers (trade step 4)
    from .trade_ownership import LEDGER_KEY, tenure_ledger_view
    canonical[LEDGER_KEY] = tenure_ledger_view(save)  # read-only for trade code; never written back from here
    canonical['_trade_planning_save'] = {
        'meta': {'season': active_season}, 'state': dict(save.get('state') or {}),
        'season_schedules': save.get('season_schedules') or {},
        'team_plans': canonical['team_plans'], 'health_states': save.get('health_states') or [],
    }
    canonical['_human_team_ids'] = sorted(human_controlled_team_ids(save))
    canonical['_coach_rest_team_ids'] = coach_rest_team_ids(save)
    canonical["ai_trade_pressure_player_ids"] = list(save.get("ai_trade_pressure_player_ids", []))
    canonical["team_trade_blocks"] = copy_plain(save.get("team_trade_blocks", {}))
    existing_pick_ids = {pick.get("id") for pick in canonical.get("draft_picks", [])}
    canonical.setdefault("draft_picks", []).extend(
        copy_plain(pick)
        for pick in save.get("generated_draft_picks", [])
        if pick.get("id") and pick.get("id") not in existing_pick_ids
    )
    from .transactions import ensure_future_second_round_scaffolds

    ensure_future_second_round_scaffolds(canonical)
    for contract in canonical.get("contracts", []):
        contract["_active_season"] = active_season
        backfill_contract_metadata(contract, active_season)
    teams_by_id = {team["id"]: team for team in canonical.get("teams", [])}
    if save.get("generated_players"):
        existing = {player["id"] for player in canonical.get("players", [])}
        rookie_context = {
            row.get("player_id"): row
            for row in save.get("incoming_rookies", [])
            if row.get("player_id")
        }
        for player in save.get("generated_players", []):
            if player.get("id") not in existing:
                active_player = copy_plain(player)
                rookie = rookie_context.get(player.get("id")) or {}
                for key in ("current_ability", "potential", "overall_pick", "draft_year"):
                    if active_player.get(key) is None and rookie.get(key) is not None:
                        active_player[key] = copy_plain(rookie[key])
                canonical.setdefault("players", []).append(active_player)
                existing.add(player.get("id"))
    if save.get("generated_traits"):
        existing_traits = {
            (trait.get("player_id"), trait.get("trait_key"))
            for trait in canonical.get("traits", [])
        }
        for trait in save.get("generated_traits", []):
            key = (trait.get("player_id"), trait.get("trait_key"))
            if key not in existing_traits:
                canonical.setdefault("traits", []).append(copy_plain(trait))
                existing_traits.add(key)
    from .health import ensure_generated_player_health

    ensure_generated_player_health(canonical, save)
    apply_effective_player_ages(canonical, save)
    for player in canonical.get("players", []):
        player["_active_season"] = active_season
    inactive_player_ids = set(save.get("retired_player_ids") or [])
    if inactive_player_ids:
        for player in canonical.get("players", []):
            if player.get("id") in inactive_player_ids:
                player["_inactive_player"] = True
    stats_by_player = save.get("player_season_stats") or {}
    if stats_by_player:
        for player in canonical.get("players", []):
            if player.get("id") in stats_by_player:
                player["_save_stats"] = copy_plain(stats_by_player[player["id"]])
    roster_overrides = save.get("roster_overrides", {})
    if roster_overrides:
        for player in canonical.get("players", []):
            if player["id"] not in roster_overrides:
                continue
            team_id = roster_overrides.get(player["id"])
            team = teams_by_id.get(team_id) if team_id else None
            if team is not None:
                player["team_id"] = team["id"]
                player["team_abbrev"] = team["abbrev"]
            else:
                player["team_id"] = None
                player["team_abbrev"] = "FA"
        for slot in canonical.get("roster_slots", []):
            if slot["player_id"] in roster_overrides:
                slot["team_id"] = roster_overrides[slot["player_id"]]
    pick_overrides = save.get("draft_pick_overrides", {})
    for pick in canonical.get("draft_picks", []):
        pick["_allocation_initial_owner_team_id"] = pick.get("current_owner_team_id")
    for pick in canonical.get("draft_picks", []):
        mark_expired_or_used_pick(pick, save, active_season)
        if pick["id"] in pick_overrides:
            override = pick_overrides[pick["id"]]
            pick["current_owner_team_id"] = None if override == "used_draft_pick" else override
            if override == "used_draft_pick":
                pick["status"] = "used_draft_pick"
        apply_saved_draft_order_to_pick(pick, save)
        if str((save.get("meta") or {}).get("game_mode") or "") == "fantasy_draft":
            from .fantasy_draft import strip_fantasy_pick_conditions

            strip_fantasy_pick_conditions(pick)
    canonical["pick_obligations"] = copy_plain(save.get("pick_obligations", []))
    canonical["locked_pick_assets"] = sorted(set(save.get("locked_pick_assets", [])))
    contract_overrides = save.get("contract_overrides", {})
    if contract_overrides:
        contracts_by_player = {contract.get("player_id"): contract for contract in canonical.get("contracts", [])}
        for player_id, override in contract_overrides.items():
            if not override:
                continue
            seasons = override.get("seasons") or offer_to_contract_seasons(override)
            record = {
                "id": stable_id("save_contract", player_id),
                "agreement_id": override.get('id') or override.get('agreement_id'),
                "player_id": player_id,
                "team_id": override.get("team_id") or override.get("accepted_team_id"),
                "seasons": seasons,
                "status": "save_state_contract_override",
                "confidence": 0.45,
                "source_ids": ["src_contract_market_config_v1"],
                "notes": "Mutable save-state contract override.",
                "original_contract_years": int(override.get("original_contract_years") or override.get("years") or override.get("term_years") or len(seasons)),
                "signed_season": override.get("signed_season") or override.get("start_season"),
                "extension_eligibility": dict(override.get("extension_eligibility") or {}),
                "_active_season": active_season,
            }
            backfill_contract_metadata(record, active_season)
            if player_id in contracts_by_player:
                contracts_by_player[player_id].update(record)
            else:
                canonical.setdefault("contracts", []).append(record)
    if save.get("staff_slots"):
        canonical["gameplay_staff_slots"] = copy_plain(save["staff_slots"])
    from .contract_protection import apply_imported_protection
    apply_imported_protection(canonical, save)
    if save.get("health_states"):
        canonical["player_health_states"] = copy_plain(save["health_states"])
    if save.get("injury_events"):
        canonical["injury_events"] = copy_plain(save["injury_events"])
    from .ratings_model import INPUTS_V1, apply_development, install_inputs_model, ratings_model_for
    inputs_model = ratings_model_for(save) == INPUTS_V1
    if inputs_model:
        # Stage 1: traits are derived from the 94 inputs, fitted on these baseline (pre-development) traits.
        install_inputs_model(canonical)
    if save.get("development_trait_totals") or save.get("development_events"):
        canonical["development_events"] = copy_plain(save["development_events"])
        if inputs_model:
            apply_development(canonical, save.get("development_trait_totals") or {}, save.get("development_events") or [])
        else:
            apply_materialized_development_to_traits(
                canonical,
                save.get("development_trait_totals") or {},
                save.get("development_events") or [],
            )
    apply_save_rotation_projection(canonical, save)
    for key in [
        "team_strategic_states",
        "player_asset_valuations",
        "trade_block_entries",
        "player_contract_market_profiles",
        "player_contract_preferences",
        "extension_candidates",
        "free_agent_candidates",
    ]:
        canonical.pop(key, None)
    return canonical


def refresh_active_runtime_state(
    active: dict[str, Any],
    save: dict[str, Any],
    *,
    development_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Refresh save-owned hot fields without rebuilding the active universe."""
    active_season = save_active_contract_season(save)
    active.setdefault("meta", {})["active_season"] = active_season
    active["meta"]["current_date"] = save.get("state", {}).get("current_date")
    active["save_team_records"] = copy_plain(save.get("team_records", {}))
    active["transaction_logs"] = copy_plain(save.get("transaction_logs", []))
    active['waived_salary_obligations'] = copy_plain(save.get('waived_salary_obligations', []))
    active['waiver_wire'] = copy_plain(save.get('waiver_wire', []))
    active['team_plans'] = copy_plain(save.get('team_plans', {}))
    active['team_trade_wants'] = copy_plain(save.get('team_trade_wants', {}))
    from .trade_ownership import LEDGER_KEY, tenure_ledger_view
    active[LEDGER_KEY] = tenure_ledger_view(save)
    from .trade_wants import clear_wants_cache
    clear_wants_cache(active)
    active['_human_team_ids'] = sorted(human_controlled_team_ids(save))
    active['_coach_rest_team_ids'] = coach_rest_team_ids(save)
    active["ai_trade_pressure_player_ids"] = list(save.get("ai_trade_pressure_player_ids", []))
    active["team_trade_blocks"] = copy_plain(save.get("team_trade_blocks", {}))
    active["player_health_states"] = copy_plain(save.get("health_states", []))
    active["injury_events"] = copy_plain(save.get("injury_events", []))
    active["gameplay_staff_slots"] = copy_plain(save.get("staff_slots", []))
    stats_by_player = save.get("player_season_stats") or {}
    for player in active.get("players", []):
        player.pop("_save_stats", None)
        stats = stats_by_player.get(player.get("id"))
        if stats:
            player["_save_stats"] = copy_plain(stats)
    if development_events:
        apply_development_events(active, development_events)
    apply_save_rotation_projection(active, save)
    for key in [
        "team_strategic_states",
        "player_asset_valuations",
        "trade_block_entries",
        "player_contract_market_profiles",
        "player_contract_preferences",
        "extension_candidates",
        "free_agent_candidates",
        "_player_asset_values_by_id",
        "_display_rating_quartiles",
        "_display_rating_averages",
        "_transaction_pick_context_signature",
    ]:
        active.pop(key, None)
    invalidate_sim_cache(active)
    invalidate_spatial_cache(active)
    return active


_ADVANCE_RUNTIME_STATE: ContextVar[_AdvanceRuntimeState | None] = ContextVar("advance_runtime_state", default=None)
_RUNTIME_AUDIT = os.environ.get("NBA_GM_RUNTIME_AUDIT") == "1"


@contextmanager
def action_runtime_scope() -> Iterator[_AdvanceRuntimeState]:
    """Share one action's read-only caches across everything it does.

    Advances already shared these within one call. Playoff, draft, re-signing and free-agency actions rebuild the
    league many times too; inside this scope each rebuild reuses the serialized starting universe, the simulation's
    reference tables and the attribute-summary memo (keyed by every input it reads). Nothing save-dependent is kept.
    """
    existing = _ADVANCE_RUNTIME_STATE.get()
    if existing is not None:
        yield existing
        return
    state = _AdvanceRuntimeState()
    token = _ADVANCE_RUNTIME_STATE.set(state)
    try:
        yield state
    finally:
        _ADVANCE_RUNTIME_STATE.reset(token)


class _AdvanceRuntimeState:
    """One advance call's disposable league, isolated from subsequent AI work."""

    # Inputs materialized by canonical_with_save rather than refreshed by
    # refresh_active_runtime_state. Compare values, including nested edits.
    _INPUT_KEYS = (
        "version", "meta", "roster_overrides", "contract_overrides",
        "free_agent_player_ids", "generated_players", "generated_traits",
        "incoming_rookies", "generated_health_profiles", "retired_player_ids",
        "generated_draft_picks", "draft_pick_overrides", "draft_orders",
        "draft_state", "pending_draft_selections", "pick_obligations",
        "locked_pick_assets", "contract_protection", "development_trait_totals",
        "development_events", "rotation_recommendations",
    )

    def __init__(self, parent: _AdvanceRuntimeState | None = None) -> None:
        self.active: dict[str, Any] | None = None
        self.inputs: Any = None
        # Read-only caches, shared with an enclosing action scope (see action_runtime_scope): the league
        # reuse above stays private to one advance call, these do not depend on the save.
        self._shared: dict[str, Any] = parent._shared if parent is not None else {
            "attribute_summaries": {}, "sim_reference": None, "baseline": None}

    @property
    def attribute_summaries(self) -> dict[bytes, dict[str, float]]:
        return self._shared["attribute_summaries"]

    @property
    def sim_reference(self) -> dict[str, Any] | None:
        return self._shared["sim_reference"]

    @sim_reference.setter
    def sim_reference(self, value: dict[str, Any] | None) -> None:
        self._shared["sim_reference"] = value

    def reference_tables(self, root: str | Path) -> dict[str, Any]:
        """The simulation's read-only reference tables (schedule, box scores, odds), loaded once per scope."""
        cached = self._shared.get("sim_reference_root")
        if self.sim_reference is None or cached != str(Path(root).resolve()):
            self.sim_reference = load_sim_reference(root)
            self._shared["sim_reference_root"] = str(Path(root).resolve())
        return self.sim_reference

    def baseline_copy(self, source: dict[str, Any]) -> dict[str, Any]:
        """canonical_with_save's private copy of the (read-only) starting universe.

        The pickled form is made once per advance call and unpickled for each rebuild, the same result
        as _copy_runtime_tree without serializing the unchanged universe again every time.
        """
        baseline = self._shared["baseline"]
        if baseline is None or baseline[0] is not source:
            public = {key: value for key, value in source.items() if not str(key).startswith("_")}
            try:
                baseline = self._shared["baseline"] = (source, pickle.dumps(public, protocol=pickle.HIGHEST_PROTOCOL))
            except (pickle.PicklingError, TypeError, AttributeError):
                return deepcopy(public)
        elif _RUNTIME_AUDIT:
            # Debug check (NBA_GM_RUNTIME_AUDIT=1): the starting universe must not change while it is cached.
            public = {key: value for key, value in source.items() if not str(key).startswith("_")}
            if pickle.dumps(public, protocol=pickle.HIGHEST_PROTOCOL) != baseline[1]:
                raise AssertionError("The starting universe changed during one action; the cached copy is stale.")
        return pickle.loads(baseline[1])

    def advance_day(self, *args: Any) -> dict[str, Any]:
        # Preserve the day API and isolate concurrent/reentrant advances.
        token = _ADVANCE_RUNTIME_STATE.set(self)
        try:
            return advance_save_day(*args)
        finally:
            _ADVANCE_RUNTIME_STATE.reset(token)

    @classmethod
    def _inputs(cls, save: dict[str, Any]) -> tuple[Any, ...]:
        state = save.get("state") or {}
        stamp = str(state.get("current_date") or "")
        evidence_date = (save.get("contract_protection") or {}).get("evidence_as_of")
        return (state.get("phase"), save_active_contract_season(save),
                bool(evidence_date and stamp >= evidence_date),
                {key: save.get(key) for key in cls._INPUT_KEYS})

    def take(self, save: dict[str, Any], target: str | None = None) -> dict[str, Any] | None:
        comparison = save
        if target is not None:
            comparison = {**save, "state": {**(save.get("state") or {}),
                                           "current_date": target, "phase": phase_for_date(target)}}
        active = self.active if self.inputs == self._inputs(comparison) else None
        self.active = None
        self.inputs = None
        return active

    def remember(self, active: dict[str, Any], save: dict[str, Any], *, isolate: bool = True) -> None:
        if save.get("state", {}).get("phase") not in {"preseason", "regular_season"}:
            self.active = None
            self.inputs = None
            return
        # Drop derived indexes, and isolate the mutable tables before any AI
        # review can normalize them. Never carry those mutations (or cached
        # approvals) into tomorrow's league.
        carried = {
            key: value for key, value in active.items()
            if not str(key).startswith("_") or key in {"_allow_internal_caches", "_ratings_model"}
        }
        # The remaining baseline tables are read-only. Isolate the mutable
        # league graph, rather than copying historical box scores and draft
        # research that neither the daily lifecycle nor AI edits.
        owned_keys = {"meta", "players", "traits", "contracts", "roster_slots",
                      "draft_picks", "pick_obligations", "locked_pick_assets",
                      "player_health_profiles", "_ratings_model"}
        if isolate:
            carried.update(_copy_runtime_tree({key: value for key, value in carried.items() if key in owned_keys}))
        self.active = carried
        self.inputs = _copy_runtime_tree(self._inputs(save))


def advance_save(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    to_date: str | None = None,
    next_event: bool = False,
    seed: int | None = None,
    *,
    prepared_save: dict[str, Any] | None = None,
    persist: bool = True,
    stop_before_postseason_games: bool = False,
    pause_at_champion: bool = False,
) -> dict[str, Any]:
    """Advance through every causal checkpoint up to the requested date.

    A long-range action is still chronological: health and games precede the
    record-sensitive AI and phase work that depends on those outcomes.
    """
    root = Path(root)
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    saved_seed = save.get("meta", {}).get("seed")
    effective_seed = int(seed if seed is not None else (saved_seed if saved_seed is not None else 1))
    if next_event:
        target = next_event_date(root, canonical, save)
    elif to_date:
        target = to_date
    else:
        raise ValueError("advance_save requires to_date or next_event=True")
    if target is None:
        if next_event and current[5:] >= "09-01":
            rollover = complete_offseason_and_rollover(
                root,
                canonical,
                save_path,
                seed=effective_seed,
                prepared_save=save,
            )
            if rollover.get("status") == "stopped":
                return {
                    "status": "stopped",
                    "save": str(save_path),
                    "from_date": current,
                    "through_date": rollover.get("current_date") or save.get("state", {}).get("current_date") or current,
                    "phase": save.get("state", {}).get("phase"),
                    "games_simulated": 0,
                    "total_simulated_games": len(save.get("schedule_state", {}).get("simulated_game_ids", [])),
                    "notes": "Simulation stopped at the last completed offseason date.",
                }
            return {
                "status": "rolled_over",
                "save": str(save_path),
                "from_date": current,
                "through_date": rollover["current_date"],
                "phase": "preseason",
                "games_simulated": 0,
                "total_simulated_games": 0,
                "rollover": rollover,
                "notes": "Season schedule was exhausted, so next-event advancement rolled the save into the next preseason.",
            }
        raise ValueError("No future calendar event is available for this save.")
    if target < current:
        raise ValueError(f"Cannot advance save backward from {current} to {target}")
    if save.get("state", {}).get("phase") in {"play_in", "playoffs"}:
        # A month can finish the postseason, but must hand control back before
        # lottery/draft decisions rather than crossing them and rolling back.
        offseason_gate = f"{season_end_year(save.get('meta', {}).get('season') or CANONICAL_SEASON)}-06-22"
        if current < offseason_gate < target:
            target = offseason_gate
    guard_target = min(target, next_date_str(current, 1)) if save.get("state", {}).get("phase") in {"play_in", "playoffs"} else target
    guard_required_phase_actions(save, current, guard_target)
    if target > current and save.get("state", {}).get("phase") in {"preseason", "regular_season"}:
        refresh_roster_cutdowns(canonical, save)
        guard_required_phase_actions(save, current, guard_target)
    simulated_before = len(save.get("schedule_state", {}).get("simulated_game_ids", []))
    from_date = current
    applied_count = 0
    signing_count = 0
    stopped = False
    if save.get("state", {}).get("phase") in {"play_in", "playoffs"}:
        initialize_postseason(canonical, save, save_path, effective_seed)
        if not stop_before_postseason_games:
            advance_postseason_through(canonical, save, current, effective_seed, root)
        if simulation_stop_requested() and current < target:
            current = str(save.get("state", {}).get("current_date") or current)
            target = current
            stopped = True
    # Button/checkpoint boundaries must never change the simulation calendar.
    # Each day sees the mutations committed by the previous day's decisions.
    runtime_state = _AdvanceRuntimeState(parent=_ADVANCE_RUNTIME_STATE.get())
    while current < target and not stopped:
        if simulation_stop_requested():
            target = current
            stopped = True
            break
        through_date = next_date_str(current, 1)
        guard_required_phase_actions(save, current, through_date)
        if phase_for_date(through_date) in {"play_in", "playoffs"}:
            initialize_postseason(canonical, save, save_path, effective_seed)
            if not stop_before_postseason_games:
                advance_postseason_through(canonical, save, through_date, effective_seed, root)
            if simulation_stop_requested():
                current = str(save.get("state", {}).get("current_date") or current)
                target = current
                stopped = True
                break
            if pause_at_champion and save.get("playoff_state", {}).get("status") == "completed":
                target = save["state"]["current_date"]
                current = target
                break
            advance_lifecycle_to(canonical, save, through_date, effective_seed, root)
            set_save_date_phase(save, through_date)
            day_result = {"ai_applied_count": 0, "inseason_free_agent_signings": 0}
        else:
            day_result = runtime_state.advance_day(root, canonical, save_path, save, current, through_date, effective_seed)
        applied_count += day_result["ai_applied_count"]
        signing_count += day_result["inseason_free_agent_signings"]
        current = through_date
        if simulation_stop_requested() and current < target:
            target = current
            stopped = True
    if (save.get("playoff_state") or {}).get("status") == "completed":
        ensure_year_end_recap_safely(canonical, save, save_path)
    if persist and (target > from_date or save.get("state", {}).get("phase") in {"play_in", "playoffs"}):
        write_save(save_path, save)
    simulated_after = len(save.get("schedule_state", {}).get("simulated_game_ids", []))
    return {
        "status": "stopped" if stopped else "advanced",
        "save": str(save_path),
        "from_date": from_date,
        "through_date": current,
        "phase": save["state"]["phase"],
        "games_simulated": simulated_after - simulated_before,
        "total_simulated_games": simulated_after,
        "development_months_processed": sorted(save.get("applied_development_months", [])),
        "inseason_free_agent_signings": signing_count,
        "ai_applied_count": applied_count,
        "notes": "Sandbox save advancement. Real-minutes replay remains validation-only.",
    }


def process_development_months(active: dict[str, Any], save: dict[str, Any], current: str, target: str, seed: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for month in development_months_between(current, target):
        if month in save.get("applied_development_months", []):
            continue
        month_events = list(advance_development(active, month, seed=seed).get("events", []))
        events.extend(month_events)
        save.setdefault("development_events", []).extend(month_events)
        save.setdefault("applied_development_months", []).append(month)
        save.setdefault("news_items", []).append({
            "id": stable_id("news", "development", month), "date": f"{month}-01",
            "kind": "development", "headline": f"Monthly player development processed for {month}.", "status": "unread",
        })
        add_notable_development_social(save, active, month_events, month)
        apply_development_events(active, month_events)
    return events


def advance_lifecycle_to(
    canonical: dict[str, Any], save: dict[str, Any], target: str, seed: int,
    root: str | Path | None = None, *, games: list[dict[str, Any]] | None = None,
    from_date: str | None = None, development: bool = True,
    active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance player time without resolving phase decisions or running regular AI.

    Legacy saves start at their present date; never backfill old months using
    today's roster. Game IDs protect same-day playoff batches and reloads.
    """
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    clock = save.setdefault("lifecycle_state", {})
    cursor = clock.setdefault("through_date", from_date or save.get("state", {}).get("current_date") or target)
    processed = set(clock.get("health_game_ids") or [])
    pending_games = [g for g in games or [] if str(g["externalGameId"]) not in processed]
    carried_active = active is not None
    events: list[dict[str, Any]] = []
    while cursor < target or (cursor == target and pending_games):
        day = min(next_date_str(cursor, 1), target)
        set_save_date_phase(save, day)
        from .waivers import process_waivers
        if process_waivers(canonical, save, day):
            active = None
        active = canonical_with_save(canonical, save) if active is None else refresh_active_runtime_state(active, save)
        if carried_active:
            # Match the planning view a fresh rebuild would create today.
            active["_trade_planning_save"] = {
                "meta": {"season": save_active_contract_season(save)},
                "state": dict(save.get("state") or {}),
                "season_schedules": save.get("season_schedules") or {},
                "team_plans": active["team_plans"],
                "health_states": save.get("health_states") or [],
            }
            carried_active = False
        todays_games = [g for g in pending_games if g["gameDate"] == day]
        health = simulate_health(root, active, cursor, day, seed=seed, schedule=todays_games,
                                 season_schedule=schedule_for_save(root, save) if todays_games else None,
                                 box_score_fatigue=True)
        merge_health_results(save, health, active)
        attach_rest_suggestions(root, active, save, day, seed)
        refresh_active_runtime_state(active, save)
        if development:
            month_events = process_development_months(active, save, cursor, day, seed)
            events.extend(month_events)
            if month_events:
                active = canonical_with_save(canonical, save)
        if reassess_ai_roles(active, save, day, calendar=development):
            apply_save_rotation_projection(active, save)
        from .team_planning import refresh_team_plans
        refresh_team_plans(active, save, day)
        processed.update(str(g["externalGameId"]) for g in todays_games)
        pending_games = [g for g in pending_games if str(g["externalGameId"]) not in processed]
        cursor = day
        clock["through_date"] = day
        clock["health_game_ids"] = sorted(processed)
        rotation_progress = simulation_rotation_progress(active, save) if progress_listener_active() else None
        live_cards = {}
        if progress_listener_active() and save.get("state", {}).get("phase") == "regular_season":
            try:
                live_cards = simulation_live_card_progress(root, active, save)
            except Exception:
                live_cards = {}
            if day[8:10] == "01":
                try:
                    live_cards["calendar"] = simulation_month_calendar_progress(root, active, save, day)
                except Exception:
                    pass
        emit_progress(save, "date", rotation=rotation_progress, **live_cards)
        if simulation_stop_requested() and cursor < target:
            break
        if cursor == target:
            break
    return {"active": active if active is not None else canonical_with_save(canonical, save), "development_events": events}


def simulation_rotation_progress(active: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    """Small user-roster snapshot for live UI feedback; never persisted."""
    team_id = (save.get("meta") or {}).get("user_team_id")
    roster = [player for player in active.get("players", []) if player.get("team_id") == team_id]
    if not roster:
        return []
    projection = team_rotation_projection(active, save, team_id, integer=True)
    health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
    rotation_override = (save.get("rotation_overrides") or {}).get(team_id, {})
    locked_ids = set((save.get("rotation_locked_player_ids") or {}).get(team_id, list(rotation_override)))
    current_date = save.get("state", {}).get("current_date")
    return [
        {
            "id": player["id"],
            "minutes_projection": float(projection.get(player["id"], display_minutes_projection(player))),
            "rotation_target_minutes": (
                0.0 if player_unavailable_for_rotation(health_by_player.get(player["id"]))
                else float(projection.get(player["id"], display_minutes_projection(player)))
            ),
            "rotation_user_set": (
                not player_unavailable_for_rotation(health_by_player.get(player["id"]))
                and player["id"] in locked_ids
            ),
            "health": player_health_label(health_by_player.get(player["id"]), current_date),
        }
        for player in roster
    ]


def simulation_live_card_progress(root: str | Path, active: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    """Compact, transient identity and opponent-card data for regular-season animation."""
    user_team_id = str((save.get("meta") or {}).get("user_team_id") or "")
    if not user_team_id:
        return {}

    identities = team_identity_report(active, save)
    next_game = (next_team_games(root, active, save, user_team_id, limit=1, include_current=True) or [None])[0]
    opponent_id = str((next_game or {}).get("opponent_team_id") or "")
    opponent_team = next((team for team in active.get("teams", []) if str(team.get("id")) == opponent_id), None)
    if not opponent_team:
        return {"team_signals": identities.get(user_team_id)}

    projection = team_rotation_projection(active, save, opponent_id, integer=True)
    health_by_player = {row.get("player_id"): row for row in save.get("health_states", [])}
    season_stats = save.get("player_season_stats", {})
    roster = sorted(
        (player for player in active.get("players", []) if player.get("team_id") == opponent_id),
        key=lambda player: (-float(projection.get(player.get("id"), display_minutes_projection(player))), player.get("name", "")),
    )[:6]
    rotation = []
    for player in roster:
        player_id = str(player.get("id") or "")
        attributes = player_attribute_summary(active, player_id)
        totals = season_stats.get(player_id, {})
        rotation.append({
            "id": player_id,
            "name": player.get("name", "Unknown"),
            "age": player.get("display_age", player.get("age")),
            "position": player.get("position"),
            "minutes_projection": float(projection.get(player_id, display_minutes_projection(player))),
            "overall": attributes.get("overall"),
            "attributes": attributes,
            # Explicit display values also cover newly acquired/generated
            # players absent from the browser's pre-action Finder cache.
            # This prevents the old browser fallback curve from being applied.
            "display_ratings": {key: presentation_rating_value(value) for key, value in attributes.items()},
            "rating_scale": RATING_SCALE,
            "points_per_game": per_game_stat(totals, "points"),
            "rebounds_per_game": per_game_stat(totals, "rebounds"),
            "assists_per_game": per_game_stat(totals, "assists"),
            "health": player_health_label(health_by_player.get(player_id), save.get("state", {}).get("current_date")),
        })

    logs = sorted(
        (row for row in save.get("team_game_logs", []) if row.get("team_id") == opponent_id),
        key=lambda row: str(row.get("date") or ""),
        reverse=True,
    )[:10]
    record = save.get("team_records", {}).get(opponent_id) or empty_team_record(opponent_team)
    return {
        "team_signals": identities.get(user_team_id),
        "opponent": {
            "team": opponent_team,
            "record": record,
            "last_games": [{"date": row.get("date"), "result": row.get("result")} for row in logs],
            "team_identity": identities.get(opponent_id, {}),
            "rotation": rotation,
            "next_game": next_game,
        },
    }


def simulation_month_calendar_progress(
    root: str | Path,
    active: dict[str, Any],
    save: dict[str, Any],
    current_date: str,
) -> dict[str, Any]:
    """Preload the full schedule for a newly entered month in live progress."""
    month_start = date.fromisoformat(f"{current_date[:7]}-01")
    next_month_start = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month_start - timedelta(days=1)
    return calendar_view(
        root,
        active,
        root,
        from_date=month_start.isoformat(),
        through_date=month_end.isoformat(),
        prepared_save=save,
    )


def advance_save_day(
    root: Path,
    canonical: dict[str, Any],
    save_path: str | Path,
    save: dict[str, Any],
    current: str,
    target: str,
    effective_seed: int,
) -> dict[str, Any]:
    """Run one calendar day's causal work without publishing a partial save."""
    simulated_before = len(save.get("schedule_state", {}).get("simulated_game_ids", []))
    runtime_state = _ADVANCE_RUNTIME_STATE.get()
    runtime_canonical: dict[str, Any] | None = None
    new_development_events: list[dict[str, Any]] = []
    if target > current:
        runtime_canonical = advance_lifecycle_to(
            canonical, save, target, effective_seed, root,
            games=scheduled_games_between(root, save, current, target), from_date=current, development=False,
            active=runtime_state.take(save, target) if runtime_state is not None else None,
        )["active"]
        if runtime_state is not None:
            # The reference tables are only read by the simulation, so one copy serves every day of this advance.
            context = load_sim_context(root, runtime_canonical, reference=runtime_state.reference_tables(root), indices=False)
        else:
            context = load_sim_context(root, runtime_canonical, indices=False)
        context["schedule"] = schedule_for_save(root, save)
        context["indices"] = build_sim_indices(context)
        context["indices"]["coach_by_team"] = save_coach_ratings(runtime_canonical, save)
        simulated_game_ids = set(save.get("schedule_state", {}).get("simulated_game_ids", []))
        for game in scheduled_games_between(root, save, current, target):
            game_id = str(game.get("externalGameId"))
            if game_id in simulated_game_ids:
                continue
            result = to_plain(sim_game_with_context(context, game_id, mode="sandbox-sim", seed=effective_seed))
            record_game_result(save, canonical, game, result)
            add_box_score_fatigue(runtime_canonical, save.setdefault("health_states", []), result, game["gameDate"], root)
            simulated_game_ids.add(game_id)
        show_injuries_from_todays_games(save, target)
        # Tonight's minutes are in: the user's next-game fatigue and rest note follow them.
        attach_rest_suggestions(root, runtime_canonical, save, target, effective_seed)
        new_development_events = process_development_months(runtime_canonical, save, current, target, effective_seed)
        if reassess_ai_roles(runtime_canonical, save, target):
            apply_save_rotation_projection(runtime_canonical, save)
    set_save_date_phase(save, target)
    expire_user_trade_offers_after_deadline(save, target)
    roster_overrides_before = dict(save.get("roster_overrides") or {})
    contract_overrides_before = deepcopy(save.get("contract_overrides") or {})
    free_agents_before = tuple(save.get("free_agent_player_ids") or [])
    if save["state"]["phase"] in {"re_signing", "free_agency"}:
        prepare_free_agency_pool(canonical, save)
    elif save["state"]["phase"] in {"preseason", "regular_season", "training_camp"}:
        # The day's lifecycle state already reflects every roster move so far (games, health and development
        # do not move players), so it can answer "is any roster short?" without a full rebuild.
        ensure_roster_minimums(canonical, save, effective_seed, active=runtime_canonical)
    if save["state"]["phase"] in {"preseason", "regular_season"}:
        refresh_roster_cutdowns(canonical, save)
        from .release_planning import review_ai_releases
        review_ai_releases(canonical, save, target, effective_seed)

    def unchanged_since_lifecycle() -> bool:
        # Same reuse rule as ai_canonical below: no roster, contract or free-agent change and no new development.
        return (runtime_canonical is not None and not new_development_events
                and roster_overrides_before == (save.get("roster_overrides") or {})
                and contract_overrides_before == (save.get("contract_overrides") or {})
                and free_agents_before == tuple(save.get("free_agent_player_ids") or []))
    inseason_fa_signings = process_inseason_released_free_agent_signings(
        canonical, save, effective_seed, target, active=runtime_canonical if unchanged_since_lifecycle() else None)
    roster_changed = (
        roster_overrides_before != (save.get("roster_overrides") or {})
        or contract_overrides_before != (save.get("contract_overrides") or {})
        or free_agents_before != tuple(save.get("free_agent_player_ids") or [])
    )
    if runtime_canonical is None or roster_changed or new_development_events:
        ai_canonical = canonical_with_save(canonical, save)
    else:
        ai_canonical = refresh_active_runtime_state(
            runtime_canonical,
            save,
            development_events=new_development_events,
        )
    if runtime_state is not None:
        from .trade_calendar import market_day
        start_year = season_start_year_from_date(target)
        queued_keys = {action.get("id") for key in ("pending_ai_actions", "processed_hidden_ai_actions")
                       for action in save.get(key, [])}
        # Only skip isolation when every AI review window is closed and no
        # queued decision can run. On review days, isolate even rejected work.
        # A listening day with no trade or offer slots runs no market search
        # (see queue_ai_recommendations), so it needs no isolation either.
        market = market_day(target, effective_seed, start_year, trade_deadline_date(start_year))
        isolate = (
            (target <= extension_deadline_date(start_year)
             and stable_id("ai_action", "extensions", target[:7], effective_seed) not in queued_keys)
            or (market["review"] and bool(market["slots"] or (market["offer_slots"] and human_controlled_team_ids(save))))
            or current[:7] != target[:7] or target.endswith("-02-05")
            or any(action.get("status") not in {"processed", "executed", "rejected", "draft_attention_required"}
                   and str(action.get("date") or "") <= target
                   for action in save.get("pending_ai_actions", []))
        )
        runtime_state.remember(ai_canonical, save, isolate=isolate)
    queue_ai_recommendations(
        ai_canonical,
        save,
        current,
        target,
        effective_seed,
        authoritative_canonical=canonical,
    )
    add_monthly_social_digest(ai_canonical, save, current, target)
    maybe_queue_rare_drama(save, canonical, current, target, effective_seed)
    roles_roster_before = dict(save.get("roster_overrides") or {})
    auto_ai = process_ai_actions_in_memory(
        canonical,
        save,
        seed=effective_seed,
        execute=True,
        limit=len(save.get("pending_ai_actions", [])),
        save_label=str(save_path),
        prepared_active=ai_canonical,
    )
    if save["state"]["phase"] in {"preseason", "regular_season"}:
        refresh_roster_cutdowns(canonical, save)
    if roles_roster_before != (save.get("roster_overrides") or {}):
        role_active = canonical_with_save(canonical, save)
        if reassess_ai_roles(role_active, save, target, calendar=False):
            apply_save_rotation_projection(role_active, save)
    dedupe_save_event_lists(save)
    simulated_after = len(save.get("schedule_state", {}).get("simulated_game_ids", []))
    return {
        "status": "advanced",
        "save": str(save_path),
        "from_date": current,
        "through_date": target,
        "phase": save["state"]["phase"],
        "games_simulated": simulated_after - simulated_before,
        "total_simulated_games": simulated_after,
        "development_months_processed": sorted(save.get("applied_development_months", [])),
        "inseason_free_agent_signings": len(inseason_fa_signings),
        "ai_applied_count": auto_ai.get("applied_count", 0),
        "notes": "Sandbox save advancement. Real-minutes replay remains validation-only.",
    }


def postseason_exit_required(save: dict[str, Any]) -> bool:
    state = save.get("playoff_state") or {}
    year = str(state.get("year") or season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON))
    return (state.get("status") == "completed"
            and save.get("state", {}).get("phase") in {"play_in", "playoffs", "draft_lottery"}
            and str(save.get("postseason_exit_confirmed") or "") != year)


def save_status(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    *,
    prepared_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    refresh_roster_cutdowns(canonical, save, apply_ai=False)
    user_team = team_by_id(canonical, save.get("meta", {}).get("user_team_id"))
    record = save.get("team_records", {}).get(user_team["id"], empty_team_record(user_team))
    season = save.get("meta", {}).get("season")
    visible_floor = f"{season_start_year(season or CANONICAL_SEASON)}-07-01"
    visible_news = [item for item in save.get("news_items", []) if str(item.get("date") or "") >= visible_floor]
    visible_social = [item for item in save.get("social_feed", []) if str(item.get("date") or "") >= visible_floor]
    high_social = sorted(
        [item for item in visible_social if item.get("kind") != "social_digest_marker"],
        key=lambda item: (float(item.get("importance") or 0), item.get("date", ""), item.get("id", "")),
        reverse=True,
    )[:4]
    playoff_state = save.get("playoff_state") or {}
    return {
        "version": save.get("version"),
        "save_id": save.get("meta", {}).get("id"),
        "season": season,
        "ai_difficulty": save.get("meta", {}).get("ai_difficulty", "normal"),
        "user_team": user_team,
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "playoff_status": playoff_state.get("status"),
        "playoff_round": playoff_state.get("round"),
        "playoff_champion_team_id": playoff_state.get("champion_team_id"),
        "postseason_exit_required": postseason_exit_required(save),
        "season_slideshow": season_slideshow_status(save),
        "legal_actions": save.get("state", {}).get("legal_actions", []),
        "next_event_date": next_event_date(root, canonical, save),
        "user_team_record": record,
        "pending_counts": pending_counts(save),
        "recent_transactions": save.get("transaction_logs", [])[-5:],
        "recent_news": visible_news[-5:],
        "recent_social": visible_social[-5:],
        "high_importance_social": high_social,
    }


def season_slideshow_status(save: dict[str, Any]) -> dict[str, Any]:
    from .season_slides import available_slideshows, pending_slideshow
    return {"pending": pending_slideshow(save), "available": available_slideshows(save)}


def pending_actions_view(canonical: dict[str, Any] | Any, save_path: str | Path) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    return {
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "legal_actions": save.get("state", {}).get("legal_actions", []),
        "pending_counts": pending_counts(save),
        "pending_trade_proposals": save.get("pending_trade_proposals", []),
        "pending_contract_negotiations": save.get("pending_contract_negotiations", []),
        "pending_draft_selections": save.get("pending_draft_selections", []),
        "pending_staff_negotiations": save.get("pending_staff_negotiations", []),
        "pending_ai_actions": save.get("pending_ai_actions", []),
        "user_trade_offers": save.get("user_trade_offers", []),
    }


def propose_trade_to_save(
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    from_team: str,
    to_team: str,
    asset_specs: list[str],
    seed: int = 1,
    store: bool = True,
    pick_obligation_terms: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    phase = save.get("state", {}).get("phase")
    if "trades" not in legal_actions_for_date(save.get("state", {}).get("current_date") or CANONICAL_START_DATE):
        raise ValueError(f"Trades are not legal during phase {phase!r}.")
    active = canonical_with_save(canonical, save)
    from .transactions import canonical_with_pending_pick_terms, evaluate_trade, parse_cli_assets, trade_result_with_pick_terms, with_transaction_context

    active = with_transaction_context(active)
    if pick_obligation_terms:
        active = canonical_with_pending_pick_terms(active, pick_obligation_terms)
    from_assets, to_assets = parse_cli_assets(active, from_team, to_team, asset_specs)
    evaluation = evaluate_trade(active, from_team, to_team, from_assets, to_assets, seed=seed, date=save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
    if pick_obligation_terms:
        evaluation = trade_result_with_pick_terms(evaluation, pick_obligation_terms)
    proposal = {
        **evaluation,
        "offer_context": {
            "offered_by_team_id": resolve_team(active, from_team)["id"],
            "user_team_id": save.get("meta", {}).get("user_team_id"),
            "created_date": save.get("state", {}).get("current_date"),
            "status": "accepted_pending_apply" if evaluation.get("accepted_by_all") else "response_recorded",
        },
    }
    if store:
        save.setdefault("pending_trade_proposals", [])
        proposal_id = evaluation.get("proposal", {}).get("id")
        save["pending_trade_proposals"] = [
            item for item in save["pending_trade_proposals"] if (item.get("proposal", {}).get("id") or item.get("id")) != proposal_id
        ]
        save["pending_trade_proposals"].append(proposal)
        add_news(save, "trade_offer", "Trade offer logged in pending actions.")
        write_save(save_path, save)
    return {
        "status": "stored" if store else "evaluated",
        "save": str(save_path),
        "pending_status": proposal["offer_context"]["status"],
        **evaluation,
    }


def process_ai_actions_in_memory(
    canonical: dict[str, Any] | Any,
    save: dict[str, Any],
    seed: int = 1,
    execute: bool = False,
    limit: int = 5,
    *,
    save_label: str = "in_memory",
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Process queued AI decisions without crossing the persistence boundary."""
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    active_dirty = False
    processed: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    pending = [action for action in save.get("pending_ai_actions", [])
               if action.get("status") not in {"processed", "executed", "rejected", "draft_attention_required"}
               and str(action.get("date") or "") <= str(save.get("state", {}).get("current_date") or CANONICAL_START_DATE)]
    for action in pending[: max(0, limit)]:
        outcome = {"id": action.get("id"), "action_type": action.get("action_type"), "status": "reviewed"}
        payload = action.get("payload") or {}
        # Legacy backlogs execute against today's context; their queue records
        # retain the scheduled date without backdating newly applied trades.
        action_date = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        if action.get("action_type") == "free_agency_recommendations" and active_dirty:
            active = canonical_with_save(canonical, save)
            active_dirty = False
        if action.get("action_type") == "trade_recommendations":
            accepted = [
                proposal for proposal in payload.get("proposals", [])
                if proposal.get("accepted_by_all") and proposal.get("legality", {}).get("status") == "legal"
            ]
            outcome["accepted_candidate_count"] = len(accepted)
            if execute and accepted:
                from .transactions import apply_trade_to_state
                applied_in_bundle = 0
                used_assets: set[str] = set()
                for proposal in accepted:
                    asset_keys = trade_asset_identity_keys(proposal)
                    if not asset_keys or used_assets.intersection(asset_keys):
                        applied.append(
                            {
                                "status": "not_applied",
                                "proposal_id": (proposal.get("proposal") or {}).get("id"),
                                "notes": "Skipped because another applied trade in this bundle already used one of these assets.",
                            }
                        )
                        continue
                    if not any((item.get("proposal") or {}).get("id") == proposal["proposal"]["id"]
                               for item in save.get("pending_trade_proposals", [])):
                        save.setdefault("pending_trade_proposals", []).append(proposal)
                    applied_result = apply_trade_to_state(
                        save,
                        proposal["proposal"]["id"],
                        date=action_date,
                        save_label=save_label,
                        canonical=canonical,
                    )
                    if applied_result.get("status") == "applied":
                        applied_in_bundle += 1
                        used_assets.update(asset_keys)
                        active_dirty = True
                    applied.append(applied_result)
                outcome["applied_candidate_count"] = applied_in_bundle
                outcome["status"] = "executed" if applied_in_bundle else "reviewed"
        elif action.get("action_type") == "free_agency_recommendations":
            accepted = [
                item for item in payload.get("negotiations", [])
                if item.get("accepted") and negotiation_player_is_free(active, save, item) and negotiation_has_positive_accepted_offer(item)
            ]
            outcome["accepted_candidate_count"] = len(accepted)
            if execute and accepted:
                save.setdefault("pending_contract_negotiations", []).append(accepted[0])
                from .contract_ai import apply_contract_to_save_state

                applied_result = apply_contract_to_save_state(save, accepted[0]["negotiation"]["id"], date=action_date)
                applied_result["save"] = save_label
                applied.append(applied_result)
                active_dirty = active_dirty or applied_result.get("status") == "applied"
                outcome["status"] = "executed"
        elif action.get("action_type") == "staff_change_recommendations":
            recommendations = payload.get("recommendations", [])
            outcome["accepted_candidate_count"] = len(recommendations)
            if execute and recommendations:
                staff_result = apply_ai_staff_recommendations(canonical, save, payload, seed)
                applied.extend(staff_result.get("applied", []))
                active_dirty = active_dirty or bool(staff_result.get("applied_count", 0))
                outcome["applied_candidate_count"] = staff_result.get("applied_count", 0)
                outcome["status"] = "executed" if staff_result.get("applied_count", 0) else "reviewed"
        elif action.get("action_type") == "draft_window_open":
            outcome["status"] = "draft_attention_required"
        new_status = "processed" if outcome["status"] == "reviewed" else outcome["status"]
        action["status"] = new_status
        for saved_action in save.get("pending_ai_actions", []):
            if saved_action.get("id") == action.get("id"):
                saved_action["status"] = new_status
                break
        processed.append(outcome)
    return {
        "processed_count": len(processed),
        "applied_count": len(applied),
        "execute": execute,
        "processed": processed,
        "applied": applied,
        "notes": "AI action processing is conservative: only legal accepted recommendations execute, and only when --execute is set.",
    }


def process_ai_actions(canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, execute: bool = False, limit: int = 5) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    result = process_ai_actions_in_memory(
        canonical,
        save,
        seed=seed,
        execute=execute,
        limit=limit,
        save_label=str(save_path),
    )
    write_save(save_path, save)
    return result


def trade_asset_identity_keys(proposal: dict[str, Any]) -> set[str]:
    from .transactions import proposal_asset_identity_keys
    return proposal_asset_identity_keys(proposal)


def apply_ai_staff_recommendations(canonical: dict[str, Any], save: dict[str, Any], payload: dict[str, Any], seed: int) -> dict[str, Any]:
    human_team_ids = human_controlled_team_ids(save)
    signed_staff_candidate_ids: set[str] = set()
    applied: list[dict[str, Any]] = []
    date_value = payload.get("through_date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    for recommendation in payload.get("recommendations", []):
        team_id = recommendation.get("team_id")
        slot = recommendation.get("slot")
        if team_id in human_team_ids:
            continue
        action = recommendation.get("action") or "hire_replacement"
        if action in {"fire_then_hire", "fire_only"}:
            reason = recommendation.get("firing_reason")
            fire_result = fire_staff_from_save(save, team_id, slot, reason=reason)
            applied.append(fire_result)
            if fire_result.get("status") == "applied":
                save.setdefault("staff_firing_history", []).append(
                    {
                        "id": stable_id("staff_firing_history", date_value, team_id, slot, (fire_result.get("fired_staff") or {}).get("id")),
                        "date": date_value,
                        "season": save.get("meta", {}).get("season"),
                        "team_id": team_id,
                        "slot": slot,
                        "staff_id": (fire_result.get("fired_staff") or {}).get("id"),
                        "staff_name": (fire_result.get("fired_staff") or {}).get("name"),
                        "reason": reason,
                    }
                )
                try:
                    review_due = (parse_date(date_value) + timedelta(days=24)).isoformat()
                except (TypeError, ValueError):
                    review_due = date_value
                save.setdefault("staff_interim_review_due", {})[f"{team_id}:{slot}"] = review_due
            if action == "fire_only" or not recommendation.get("candidate_id"):
                continue
        if recommendation.get("candidate_id") in signed_staff_candidate_ids:
            applied.append({"status": "not_applied", "recommendation_id": recommendation.get("id"), "notes": "Candidate already accepted another staff job in this bundle."})
            continue
        offer = recommendation.get("recommended_offer") or {}
        try:
            negotiation = negotiate_staff_hire(
                canonical,
                save,
                recommendation["candidate_id"],
                recommendation.get("team_abbrev") or recommendation["team_id"],
                slot,
                seed=seed,
                offer_salary_millions=float(offer.get("annual_salary_millions") or 0),
                offer_years=int(offer.get("years") or 2),
            )
        except ValueError as exc:
            applied.append({"status": "not_applied", "recommendation_id": recommendation.get("id"), "notes": str(exc)})
            continue
        if not negotiation.get("accepted"):
            applied.append({"status": "rejected", "negotiation": negotiation})
            continue
        applied_result = hire_staff_from_save(save, negotiation["id"], canonical=canonical)
        if applied_result.get("status") == "applied":
            signed_staff_candidate_ids.add(recommendation.get("candidate_id"))
            save.setdefault("staff_interim_review_due", {}).pop(f"{team_id}:{slot}", None)
        applied.append(applied_result)
    return {"applied_count": len([item for item in applied if item.get("status") == "applied"]), "applied": applied}


def negotiation_player_is_free(active: dict[str, Any], save: dict[str, Any], item: dict[str, Any]) -> bool:
    player_id = (item.get("negotiation") or {}).get("player_id") or (item.get("decision") or {}).get("player_id")
    player = next((row for row in active.get("players", []) if row.get("id") == player_id), {})
    from .waivers import pending_ids
    if player_id in pending_ids(save):
        return False
    return not player.get("team_id") or player_id in set(save.get("free_agent_player_ids", []))


def negotiation_has_positive_accepted_offer(item: dict[str, Any]) -> bool:
    if not item.get("accepted"):
        return False
    offer = (item.get("decision") or {}).get("accepted_offer") or {}
    if not offer:
        return False
    return float(offer.get("annual_salary") or offer.get("aav") or 0) > 0


def calendar_view(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    from_date: str | None = None,
    through_date: str | None = None,
    *,
    prepared_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    start = from_date or current
    end = through_date or next_date_str(start, 14)
    team_by_espn = espn_team_id_map(canonical)
    simulated = set(save.get("schedule_state", {}).get("simulated_game_ids", []))
    results = {
        str(result.get("game_id")): result
        for result in [*save.get("game_result_summaries", []), *save.get("game_results", [])]
        if result.get("game_id")
    }
    user_team_id = save.get("meta", {}).get("user_team_id")
    games = []
    for game in schedule_for_save(root, save):
        game_date = game.get("gameDate")
        if start <= game_date <= end:
            home = team_by_espn.get(str(game.get("homeTeamId")), {})
            away = team_by_espn.get(str(game.get("awayTeamId")), {})
            game_id = str(game.get("externalGameId"))
            result = results.get(game_id)
            user_result = calendar_user_result(user_team_id, away.get("id"), home.get("id"), result)
            games.append(
                {
                    "game_id": game_id,
                    "date": game_date,
                    "phase": game.get("phase"),
                    "away_team": away.get("abbrev"),
                    "home_team": home.get("abbrev"),
                    "status": "simulated" if game_id in simulated else "scheduled",
                    "away_score": result.get("away_score") if result else None,
                    "home_score": result.get("home_score") if result else None,
                    "user_result": user_result,
                    "overtime_periods": int(result.get("overtime_periods") or max([int(line.get("overtime_periods") or 0) for line in result.get("team_lines", [])], default=0)) if result else 0,
                }
            )
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    for game in (save.get("playoff_state") or {}).get("games", []):
        game_date = game.get("gameDate")
        if not game_date or not (start <= game_date <= end):
            continue
        game_id = str(game.get("externalGameId"))
        result = results.get(game_id)
        user_result = calendar_user_result(user_team_id, game.get("away_team_id"), game.get("home_team_id"), result)
        games.append(
            {
                "game_id": game_id,
                "date": game_date,
                "phase": "playoffs",
                "away_team": teams.get(game.get("away_team_id"), {}).get("abbrev"),
                "home_team": teams.get(game.get("home_team_id"), {}).get("abbrev"),
                "status": "simulated" if result else "scheduled",
                "away_score": result.get("away_score") if result else None,
                "home_score": result.get("home_score") if result else None,
                "user_result": user_result,
                "overtime_periods": int(result.get("overtime_periods") or max([int(line.get("overtime_periods") or 0) for line in result.get("team_lines", [])], default=0)) if result else 0,
            }
        )
    games.sort(key=lambda item: (item["date"], item.get("game_id") or ""))
    return {"from_date": start, "through_date": end, "game_count": len(games), "games": games}


def calendar_user_result(user_team_id: str | None, away_team_id: str | None, home_team_id: str | None, result: dict[str, Any] | None) -> str:
    if not user_team_id or not result or user_team_id not in {away_team_id, home_team_id}:
        return ""
    user_score = result.get("away_score") if user_team_id == away_team_id else result.get("home_score")
    opp_score = result.get("home_score") if user_team_id == away_team_id else result.get("away_score")
    if user_score is None or opp_score is None:
        return ""
    return "W" if int(user_score) > int(opp_score) else "L"


def box_score_view(canonical: dict[str, Any] | Any, save_path: str | Path, game_id: str) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    result = next((item for item in save.get("game_results", []) if str(item.get("game_id")) == str(game_id)), None)
    if not result:
        result = next(iter(load_history_records(save_path, save, "game_results", game_id=str(game_id), limit=1)), None)
    if not result:
        raise ValueError(f"No simulated game result found for {game_id!r}.")
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    player_lines = sorted(
        result.get("player_lines", []),
        key=lambda item: (item.get("team_abbrev", ""), -float(item.get("minutes") or 0), item.get("player_name", "")),
    )
    playoff_game = next(
        (
            item
            for item in save.get("playoff_state", {}).get("games", []) or []
            if str(item.get("externalGameId")) == str(game_id)
        ),
        {},
    )
    game_date = playoff_game.get("gameDate") or next(
        (row.get("date") for row in save.get("game_result_summaries", []) if str(row.get("game_id")) == str(game_id)),
        None,
    )
    away_team_id = result.get("away_team_id")
    home_team_id = result.get("home_team_id")
    away_abbrev = teams.get(away_team_id, {}).get("abbrev", away_team_id)
    home_abbrev = teams.get(home_team_id, {}).get("abbrev", home_team_id)
    away_count = sum(1 for row in player_lines if row.get("team_id") == away_team_id or row.get("team_abbrev") == away_abbrev)
    home_count = sum(1 for row in player_lines if row.get("team_id") == home_team_id or row.get("team_abbrev") == home_abbrev)
    if away_count != home_count:
        shorter_team_id, shorter_abbrev = (
            (away_team_id, away_abbrev) if away_count < home_count else (home_team_id, home_abbrev)
        )
        missing_count = abs(away_count - home_count)
        existing_ids = {
            row.get("player_id")
            for row in player_lines
            if row.get("team_id") == shorter_team_id or row.get("team_abbrev") == shorter_abbrev
        }
        health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
        events_by_player: dict[str, list[dict[str, Any]]] = {}
        for event in save.get("injury_events", []):
            if event.get("player_id"):
                events_by_player.setdefault(event["player_id"], []).append(event)
        roster_overrides = save.get("roster_overrides") or {}
        unavailable_ids = set(save.get("retired_player_ids") or []) | set(save.get("free_agent_player_ids") or [])
        candidates_by_id = {
            player.get("id"): player
            for player in [*canonical.get("players", []), *save.get("generated_players", [])]
            if player.get("id")
        }
        candidates = sorted(
            (
                player
                for player_id, player in candidates_by_id.items()
                if player_id not in existing_ids
                and player_id not in unavailable_ids
                and roster_overrides.get(player_id, player.get("team_id")) == shorter_team_id
                and not box_score_player_injured_on_date(
                    player_id,
                    game_date,
                    events_by_player,
                    health_by_player,
                )
            ),
            key=lambda player: str(player.get("name") or "").casefold(),
        )
        for player in candidates[:missing_count]:
            player_lines.append({
                "player_id": player["id"],
                "player_name": player.get("name") or "Unknown",
                "team_id": shorter_team_id,
                "team_abbrev": shorter_abbrev,
                "minutes": 0,
                "points": 0,
                "rebounds": 0,
                "assists": 0,
                "steals": 0,
                "blocks": 0,
                "turnovers": 0,
                "fgm": 0,
                "fga": 0,
                "fg3m": 0,
                "fg3a": 0,
                "ftm": 0,
                "fta": 0,
                "personal_fouls": 0,
                "plus_minus": 0,
            })
    return {
        "game_id": result.get("game_id"),
        "game_date": game_date,
        "mode": result.get("mode"),
        "seed": result.get("seed"),
        "away_team": teams.get(result.get("away_team_id"), {"abbrev": result.get("away_team_id")}),
        "home_team": teams.get(result.get("home_team_id"), {"abbrev": result.get("home_team_id")}),
        "away_score": result.get("away_score"),
        "home_score": result.get("home_score"),
        "possessions": result.get("possessions"),
        "overtime_periods": max([int(line.get("overtime_periods") or 0) for line in result.get("team_lines", [])], default=0),
        "team_lines": result.get("team_lines", []),
        "player_lines": player_lines,
        "plus_minus_tracking": result.get('plus_minus_tracking'),
        "notes": result.get("notes"),
    }


def box_score_player_injured_on_date(
    player_id: str,
    game_date: str | None,
    events_by_player: dict[str, list[dict[str, Any]]],
    health_by_player: dict[str, dict[str, Any]],
) -> bool:
    events = events_by_player.get(player_id, [])
    if game_date:
        for event in events:
            start_date = event.get("start_date")
            return_date = event.get("return_date")
            if start_date and str(start_date) <= game_date and (not return_date or game_date < str(return_date)):
                return True
        if events:
            return False
        state = health_by_player.get(player_id)
        if state:
            status = str(state.get("availability_status") or "active").lower()
            if status in {"", "active", "healthy"} and not state.get("current_injury_id"):
                return False
            return_date = state.get("return_date")
            return not return_date or game_date < str(return_date)
        return False
    return player_unavailable_for_rotation(health_by_player.get(player_id))


def league_standings(
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    *,
    prepared_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    rows = []
    for team_id, record in save.get("team_records", {}).items():
        team = teams.get(team_id)
        if not team:
            continue
        games = int(record.get("wins", 0)) + int(record.get("losses", 0))
        rows.append(
            {
                **record,
                "team": team,
                "games": games,
                "win_pct": round(record.get("wins", 0) / games, 3) if games else 0.0,
                "point_diff": round(float(record.get("points_for", 0)) - float(record.get("points_against", 0)), 2),
            }
        )
    rows.sort(key=lambda item: (item["team"].get("conference") or "", -item["win_pct"], -item["point_diff"], item["team"]["abbrev"]))
    return {"standings": rows, "team_count": len(rows), "as_of_date": save.get("state", {}).get("current_date")}


def league_leaders(canonical: dict[str, Any] | Any, save_path: str | Path, stat: str = "points", limit: int = 10) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    stat_key = {"pts": "points", "reb": "rebounds", "ast": "assists", "stl": "steals", "blk": "blocks"}.get(stat, stat)
    if stat_key in {"overall", "shooting", "spacing", "creation", "defense", "athleticism", "iq", "rim_pressure", "rebounding", "disruption", "rim_protection"}:
        raise ValueError("League leaders only supports box-score stats. Use the player traits browser for ratings.")
    players = {player["id"]: player for player in canonical.get("players", [])}
    rows = []
    team_games = {
        team_id: int(record.get("wins", 0)) + int(record.get("losses", 0))
        for team_id, record in save.get("team_records", {}).items()
    }
    for player_id, totals in save.get("player_season_stats", {}).items():
        player = players.get(player_id, {"id": player_id, "name": totals.get("player_name"), "position": None})
        games = max(1, int(totals.get("games", 0)))
        required_games = max(1, min(10, int(round(team_games.get(totals.get("team_id"), games) * 0.22))))
        if int(totals.get("games", 0)) < required_games:
            continue
        rows.append(
            {
                "player": player,
                "team_id": totals.get("team_id"),
                "team_abbrev": totals.get("team_abbrev"),
                "games": totals.get("games", 0),
                stat_key: round(float(totals.get(stat_key, 0)), 2),
                f"{stat_key}_per_game": round(float(totals.get(stat_key, 0)) / games, 2),
            }
        )
    rows.sort(key=lambda item: (-float(item.get(f"{stat_key}_per_game", 0)), -float(item.get(stat_key, 0)), item["player"].get("name") or ""))
    return {"stat": stat_key, "leaders": rows[:limit], "as_of_date": save.get("state", {}).get("current_date")}


def playoff_leaders(canonical: dict[str, Any] | Any, save_path: str | Path, stat: str = "points", limit: int = 10) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    stat_key = {"pts": "points", "reb": "rebounds", "ast": "assists", "stl": "steals", "blk": "blocks", "3pm": "fg3m"}.get(stat, stat)
    players = {player["id"]: player for player in canonical.get("players", [])}
    rows = []
    for player_id, totals in save.get("playoff_player_stats", {}).items():
        games = max(1, int(totals.get("games") or 1))
        player = players.get(player_id, {"id": player_id, "name": totals.get("player_name")})
        row = {
            "player": player,
            "player_id": player_id,
            "player_name": player.get("name") or totals.get("player_name"),
            "headshot_url": player.get("headshot_url"),
            "team_id": totals.get("team_id"),
            "team_abbrev": totals.get("team_abbrev"),
            "games": totals.get("games", 0),
        }
        # Every box-score field as a playoff total and a per-playoff-game average.
        # Denominators are playoff games only; regular-season games never enter.
        for field in STAT_FIELDS:
            row[field] = round(float(totals.get(field) or 0), 2)
            row[f"{field}_per_game"] = round(float(totals.get(field) or 0) / games, 2)
        row["fg_pct"] = percentage_stat(totals, "fgm", "fga")
        row["fg3_pct"] = percentage_stat(totals, "fg3m", "fg3a")
        row["ft_pct"] = percentage_stat(totals, "ftm", "fta")
        row[stat_key] = round(float(totals.get(stat_key, 0)), 2)
        row[f"{stat_key}_per_game"] = round(float(totals.get(stat_key, 0)) / games, 2)
        rows.append(row)
    rows.sort(key=lambda item: (-float(item.get(f"{stat_key}_per_game", 0)), -float(item.get(stat_key, 0)), item["player"].get("name") or ""))
    return {
        "stat": stat_key,
        "leaders": rows[:limit],
        "as_of_date": save.get("state", {}).get("current_date"),
        "finals_mvp": save.get("finals_mvp"),
    }


STARTING_FIVE_SLOT_FITS = {
    "1": {"PG": 12.0, "SG": 6.0},
    "2": {"SG": 12.0, "PG": 9.5, "SF": 4.0},
    "3": {"SF": 12.0, "SG": 5.0, "PF": 4.0},
    "4": {"PF": 12.0, "SF": 5.0, "C": 4.0},
    "5": {"C": 12.0, "PF": 5.0},
}


def player_position_tokens(player: dict[str, Any]) -> list[str]:
    raw = str(player.get("position") or "").upper().replace("/", "-")
    return [part.strip() for part in raw.split("-") if part.strip()] or ["G"]


def starting_slot_score(player: dict[str, Any], slot: str, minutes: float, attrs: dict[str, float]) -> float:
    slot = str(slot)
    height = player_height_inches(player)
    tokens = player_position_tokens(player)
    fits = STARTING_FIVE_SLOT_FITS.get(slot, {})
    position_fit = max([fits.get(token, 0.0) for token in tokens] or [0.0])
    overall = float(attrs.get("overall") or 50.0)
    creation = float(attrs.get("creation") or attrs.get("create") or 50.0)
    passing = float(attrs.get("passing") or 50.0)
    spacing = float(attrs.get("spacing") or attrs.get("shooting") or 50.0)
    defense = float(attrs.get("defense") or 50.0)
    rebound = float(attrs.get("rebounding") or attrs.get("rebound") or 50.0)
    rim = float(attrs.get("rim_protection") or attrs.get("rim_deterrence") or 50.0)
    if starting_slot_hard_violation(slot, height, tokens):
        return -10_000.0
    score = minutes * 1.15 + overall * 0.34 + position_fit
    if slot == "1":
        score += creation * 0.18 + passing * 0.16 - max(0.0, height - 81.0) * 2.6
    elif slot == "2":
        score += spacing * 0.16 + creation * 0.10 + defense * 0.08
        score -= max(0.0, height - 82.0) * 1.2
    elif slot == "3":
        score += spacing * 0.11 + defense * 0.12 + max(0.0, min(height, 82.0) - 76.0) * 1.3
        score -= max(0.0, 75.5 - height) * 4.0
    elif slot == "4":
        score += rebound * 0.12 + rim * 0.08 + spacing * 0.08 + max(0.0, height - 79.0) * 2.0
        score -= max(0.0, 78.5 - height) * 8.0
    else:
        score += rebound * 0.18 + rim * 0.18 + max(0.0, height - 80.0) * 2.8
        score -= spacing * 0.03
        score -= max(0.0, 80.0 - height) * 9.0
    if height >= 84.0 and slot in {"4", "5"}:
        score += 12.0
    if height >= 84.0 and slot in {"1", "2", "3"} and "SF" not in tokens:
        score -= 35.0
    return score


def player_height_inches(player: dict[str, Any]) -> float:
    try:
        return float(player.get("height_inches") or player.get("height") or 78.0)
    except (TypeError, ValueError):
        return 78.0


def starting_slot_hard_violation(slot: str, height: float, tokens: list[str]) -> bool:
    if slot in {"4", "5"} and height < 76.5 and not any(token in {"PF", "C"} for token in tokens):
        return True
    if slot == "5" and height < 78.0 and "C" not in tokens:
        return True
    if slot in {"1", "2", "3"} and height >= 84.0 and "PG" not in tokens and "SG" not in tokens and "SF" not in tokens:
        return True
    if slot in {"1", "2"} and "C" in tokens and "PF" not in tokens and height >= 82.0:
        return True
    return False


def auto_starting_five(canonical: dict[str, Any], save: dict[str, Any], team_id: str) -> dict[str, str]:
    projection = team_rotation_projection(canonical, save, team_id, integer=False)
    unavailable_ids = unavailable_player_ids_for_starting_five(save)
    roster = [
        player for player in canonical.get("players", [])
        if player.get("team_id") == team_id and player.get("id") not in unavailable_ids
    ]
    if not roster:
        return {}
    candidate_rows = []
    for player in roster:
        player_id = player.get("id")
        minutes = float(projection.get(player_id, display_minutes_projection(player)))
        attrs = player_attribute_summary(canonical, player_id)
        base = minutes * 1.3 + float(attrs.get("overall") or 50.0) * 0.5
        candidate_rows.append((base, minutes, player.get("name") or "", player, attrs))
    candidate_rows = sorted(candidate_rows, key=lambda item: (item[0], item[1], item[2]), reverse=True)[:9]
    slots = ["1", "2", "3", "4", "5"][: min(5, len(candidate_rows))]
    # Scores depend on the player and slot, not the other four assignments.
    scores = [
        [starting_slot_score(row[3], slot, row[1], row[4]) for row in candidate_rows]
        for slot in slots
    ]
    best_score = -1_000_000.0
    best_assignment: tuple[int, ...] | None = None
    for assignment in permutations(range(len(candidate_rows)), len(slots)):
        total = 0.0
        for slot_index, player_index in enumerate(assignment):
            total += scores[slot_index][player_index]
        if total > best_score:
            best_score = total
            best_assignment = assignment
    if not best_assignment:
        return {}
    return {
        slot: candidate_rows[player_index][3]["id"]
        for slot, player_index in zip(slots, best_assignment, strict=False)
        if candidate_rows[player_index][3].get("id")
    }


def unavailable_player_ids_for_starting_five(save: dict[str, Any]) -> set[str]:
    return {
        state.get("player_id")
        for state in save.get("health_states", [])
        if state.get("player_id") and player_unavailable_for_rotation(state)
    }


def starting_lineup_slots(canonical: dict[str, Any], save: dict[str, Any], team_id: str, persist: bool = True) -> dict[str, str]:
    save.setdefault("starting_lineups", {})
    roster_ids = {player.get("id") for player in canonical.get("players", []) if player.get("team_id") == team_id}
    unavailable_ids = unavailable_player_ids_for_starting_five(save)
    available_roster_ids = roster_ids - unavailable_ids
    stored = save["starting_lineups"].get(team_id) or {}
    raw_slots = stored.get("slots") if isinstance(stored, dict) else {}
    raw_slots = raw_slots if isinstance(raw_slots, dict) else {}
    cleaned_raw_slots: dict[str, str] = {}
    cleaned_used: set[str] = set()
    for slot in ["1", "2", "3", "4", "5"]:
        player_id = raw_slots.get(slot) or raw_slots.get(int(slot))
        if player_id in roster_ids and player_id not in cleaned_used:
            cleaned_raw_slots[slot] = player_id
            cleaned_used.add(player_id)
    slots: dict[str, str] = {}
    used: set[str] = set()
    for slot in ["1", "2", "3", "4", "5"]:
        player_id = cleaned_raw_slots.get(slot)
        if player_id in available_roster_ids and player_id not in used:
            slots[slot] = player_id
            used.add(player_id)
    auto = {} if len(slots) == 5 else auto_starting_five(canonical, save, team_id)
    for slot in ["1", "2", "3", "4", "5"]:
        player_id = auto.get(slot)
        if slot not in slots and player_id in available_roster_ids and player_id not in used:
            slots[slot] = player_id
            used.add(player_id)
    for slot in ["1", "2", "3", "4", "5"]:
        if slot in slots:
            continue
        for player_id in auto.values():
            if player_id in available_roster_ids and player_id not in used:
                slots[slot] = player_id
                used.add(player_id)
                break
    if persist:
        existing = save["starting_lineups"].get(team_id)
        source = (existing or {}).get("source", "auto") if isinstance(existing, dict) else "auto"
        stored_slots = cleaned_raw_slots if source == "user" else slots
        if not existing or (isinstance(existing, dict) and existing.get("slots") != stored_slots):
            save["starting_lineups"][team_id] = {"slots": stored_slots, "source": source}
    return slots


def starting_five_rows(canonical: dict[str, Any], save: dict[str, Any], team_id: str, persist: bool = True) -> list[dict[str, Any]]:
    slots = starting_lineup_slots(canonical, save, team_id, persist=persist)
    players = {player.get("id"): player for player in canonical.get("players", [])}
    return [
        {
            "slot": int(slot),
            "player_id": player_id,
            "player_name": (players.get(player_id) or {}).get("name") or player_id,
            "position": (players.get(player_id) or {}).get("position"),
        }
        for slot, player_id in sorted(slots.items(), key=lambda item: int(item[0]))
    ]


def league_events_view(
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    limit: int = 40,
    kind: str | None = None,
    major_only: bool = False,
    recent_days: int | None = None,
    *,
    prepared_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    archived_events = load_history_records(save_path, save, "league_events")
    event_rows = {
        str(event.get("id") or stable_id("league_event", event.get("date"), event.get("kind"), event.get("headline"))): event
        for event in archived_events
    }
    event_rows.update(
        {
            str(event.get("id") or stable_id("league_event", event.get("date"), event.get("kind"), event.get("headline"))): event
            for event in save.get("league_events", [])
        }
    )
    events = [enriched_league_event(canonical, save, event) for event in event_rows.values()]
    if kind:
        events = [event for event in events if league_event_kind_matches(event, kind)]
    if major_only:
        events = [event for event in events if is_major_league_event(canonical, save, event)]
    if recent_days is not None:
        events = [event for event in events if event_is_recent(event, save.get("state", {}).get("current_date"), recent_days)]
    events = sorted(events, key=lambda item: (item.get("date") or "", item.get("importance") or 0.0, item.get("headline") or ""), reverse=True)
    events = dedupe_trade_events_for_view(events)
    return {"as_of_date": save.get("state", {}).get("current_date"), "events": events[:limit], "event_count": len(events)}


def league_event_kind_matches(event: dict[str, Any], kind: str) -> bool:
    requested = str(kind or "").strip().lower()
    event_kind = str(event.get("kind") or "").strip().lower()
    groups = {
        "transactions": {"trade", "trade_demand", "free_agent_signing", "free_agency_signing", "extension", "staff_hire", "staff_fire"},
        "all_transactions": {"trade", "trade_demand", "free_agent_signing", "free_agency_signing", "extension", "staff_hire", "staff_fire"},
        "trades": {"trade"},
        "trade_demands": {"trade_demand"},
        "extensions": {"extension"},
        "staff_hires": {"staff_hire"},
        "staff_fires": {"staff_fire"},
    }
    if requested in groups:
        return event_kind in groups[requested]
    return event_kind == requested


def dedupe_trade_events_for_view(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen_trades: set[tuple[Any, ...]] = set()
    for event in events:
        if event.get("kind") != "trade":
            output.append(event)
            continue
        details = event.get("details") or {}
        asset_key = (
            tuple(sorted(event_asset_keys(details.get("from_assets") or []))),
            tuple(sorted(event_asset_keys(details.get("to_assets") or []))),
        )
        key = asset_key if any(asset_key) else (event.get("headline"),)
        if key in seen_trades:
            continue
        seen_trades.add(key)
        output.append(event)
    return output


def event_asset_keys(assets: list[dict[str, Any]]) -> list[str]:
    return [
        f"{asset.get('kind')}:{asset.get('id') or asset.get('player_id') or asset.get('pick_id') or asset.get('label')}"
        for asset in assets
        if asset.get("kind")
    ]


def event_is_recent(event: dict[str, Any], as_of_date: str | None, days: int) -> bool:
    if not as_of_date:
        return True
    try:
        event_date = parse_date(str(event.get("date") or as_of_date))
        current = parse_date(as_of_date)
    except (TypeError, ValueError):
        return False
    return current - timedelta(days=max(0, int(days))) <= event_date <= current


def enriched_league_event(canonical: dict[str, Any], save: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    enriched = deepcopy(event)
    details = dict(enriched.get("details") or {})
    kind = str(enriched.get("kind") or "")
    if kind == "trade":
        details = enrich_trade_event_details(canonical, save, enriched, details)
    elif kind in {"free_agent_signing", "free_agency_signing", "free_agency", "extension"}:
        details = enrich_contract_event_details(save, enriched, details)
    elif kind in {"staff_hire", "staff_fire"}:
        details = enrich_staff_event_details(save, enriched, details)
    elif kind == "injury":
        details = enrich_injury_event_details(canonical, enriched, details)
    elif kind == "major_stat_line":
        details = normalize_stat_line_details(details)
    enriched["details"] = details
    return enriched


def enrich_trade_event_details(canonical: dict[str, Any], save: dict[str, Any], event: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    if details.get('transfers'):
        return {**details, 'transfers': [{**leg, 'assets': [enrich_trade_asset_for_event(canonical, a) for a in leg['assets']]}
                                         for leg in details['transfers']]}
    if not (details.get("from_assets") or details.get("to_assets")):
        log = matching_transaction_log(save, event, {"trade"})
        if log:
            details = {**details, **dict(log.get("assets") or {})}
    details["from_assets"] = [enrich_trade_asset_for_event(canonical, asset) for asset in details.get("from_assets", [])]
    details["to_assets"] = [enrich_trade_asset_for_event(canonical, asset) for asset in details.get("to_assets", [])]
    return details


def enrich_trade_asset_for_event(canonical: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(asset or {})
    if enriched.get("kind") == "player":
        player_id = enriched.get("id") or enriched.get("player_id")
        player = next((item for item in canonical.get("players", []) if item.get("id") == player_id), {})
        if player:
            enriched.setdefault("id", player.get("id"))
            enriched.setdefault("label", player.get("name"))
            enriched.setdefault("minutes_projection", display_minutes_projection(player))
    elif enriched.get("kind") == "pick":
        pick_id = enriched.get("id") or enriched.get("pick_id")
        pick = next((item for item in canonical.get("draft_picks", []) if item.get("id") == pick_id), {})
        if pick:
            enriched.setdefault("id", pick.get("id"))
            enriched.setdefault("season", pick.get("season"))
            enriched.setdefault("round", pick.get("round"))
            enriched.setdefault("original_team_id", pick.get("original_team_id"))
            enriched.setdefault("current_owner_team_id", pick.get("current_owner_team_id"))
    return enriched


def enrich_contract_event_details(save: dict[str, Any], event: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    if not details.get("contract"):
        log = matching_transaction_log(save, event, {"extension", "free_agent_signing", "free_agency"})
        if log:
            assets = log.get("assets") or {}
            details.setdefault("player_id", assets.get("player_id"))
            details.setdefault("contract", assets.get("contract"))
    contract = details.get("contract") or {}
    annual = details.get("annual_salary") or contract.get("annual_salary") or contract.get("salary") or details.get("aav")
    if annual is not None:
        details["annual_salary"] = float(annual)
        details["aav_millions"] = round(float(annual) / 1_000_000, 2) if float(annual) > 1_000 else float(annual)
    years = details.get("years") or contract.get("years") or contract.get("original_contract_years") or contract.get("term_years")
    if years is None and isinstance(contract.get("seasons"), list):
        years = len(contract.get("seasons") or [])
    if years is not None:
        try:
            details["years"] = int(years)
        except (TypeError, ValueError):
            pass
    return details


def enrich_staff_event_details(save: dict[str, Any], event: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    if details.get("staff_grade") is not None:
        return details
    log = matching_transaction_log(save, event, {"staff_hire", "staff_fire"})
    assets = (log or {}).get("assets") or {}
    staff = assets.get("staff") or assets.get("fired_staff") or {}
    if staff:
        details.setdefault("staff_id", staff.get("id"))
        details.setdefault("staff_name", staff.get("name"))
        details.setdefault("staff_grade", round(staff_grade(staff), 2))
    return details


def enrich_injury_event_details(canonical: dict[str, Any], event: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    if details.get("player_minutes_projection") is None:
        player_id = details.get("player_id") or next(iter(event.get("player_ids") or []), None)
        player = next((item for item in canonical.get("players", []) if item.get("id") == player_id), {})
        if player:
            details.setdefault("player_id", player.get("id"))
            details.setdefault("player_minutes_projection", display_minutes_projection(player))
    return details


def normalize_stat_line_details(details: dict[str, Any]) -> dict[str, Any]:
    stat = str(details.get("stat") or "").lower()
    aliases = {"pts": "points", "reb": "rebounds", "ast": "assists", "stl": "steals", "blk": "blocks"}
    if stat in aliases:
        details["stat"] = aliases[stat]
    return details


def matching_transaction_log(save: dict[str, Any], event: dict[str, Any], kinds: set[str]) -> dict[str, Any] | None:
    matches = [
        log for log in save.get("transaction_logs", [])
        if log.get("transaction_type") in kinds and str(log.get("date") or "") == str(event.get("date") or "")
    ]
    if len(matches) == 1:
        return matches[0]
    headline = str(event.get("headline") or "")
    for log in matches:
        assets = log.get("assets") or {}
        labels = json.dumps(assets, sort_keys=True)
        if headline and all(token in labels for token in headline.split()[:2]):
            return log
    return None


def is_major_league_event(canonical: dict[str, Any], save: dict[str, Any], event: dict[str, Any]) -> bool:
    kind = str(event.get("kind") or "")
    details = event.get("details") or {}
    if kind in {"game_result", "game"}:
        return False
    if kind == "trade":
        return trade_event_is_major(details)
    if kind == "trade_demand":
        return True
    if kind in {"free_agent_signing", "free_agency_signing", "free_agency", "extension"}:
        return contract_event_is_major(details)
    if kind in {"staff_hire", "staff_fire"}:
        return staff_event_is_major(details)
    if kind == "injury":
        return injury_event_is_major(details)
    if kind == "major_stat_line":
        return stat_line_event_is_major(details)
    return False


def trade_event_is_major(details: dict[str, Any]) -> bool:
    from .transactions import trade_assets
    for asset in trade_assets(details):
        if asset.get("kind") == "pick" and int(asset.get("round") or 0) == 1:
            return True
        if asset.get("kind") == "player" and float(asset.get("minutes_projection") or 0.0) > MAJOR_PLAYER_MPG_THRESHOLD:
            return True
    return False


def contract_event_is_major(details: dict[str, Any]) -> bool:
    annual = details.get("annual_salary")
    if annual is None and details.get("aav_millions") is not None:
        annual = float(details.get("aav_millions") or 0.0) * 1_000_000
    return float(annual or 0.0) > MAJOR_FREE_AGENT_AAV_THRESHOLD


def staff_event_is_major(details: dict[str, Any]) -> bool:
    slot = str(details.get("slot") or "")
    action = str(details.get("action") or "")
    if slot == "head_coach" and action == "fire":
        return True
    return float(details.get("staff_grade") or details.get("candidate_grade") or details.get("fired_staff_grade") or 0.0) > MAJOR_STAFF_GRADE_THRESHOLD


def injury_event_is_major(details: dict[str, Any]) -> bool:
    games = int(details.get("expected_games_missed") or details.get("games_missed") or 0)
    mpg = float(details.get("player_minutes_projection") or details.get("minutes_projection") or 0.0)
    return games > MAJOR_INJURY_GAMES_THRESHOLD and mpg > MAJOR_PLAYER_MPG_THRESHOLD


def stat_line_event_is_major(details: dict[str, Any]) -> bool:
    stat = str(details.get("stat") or "").lower()
    value = float(details.get("value") or 0.0)
    threshold = MAJOR_STAT_LINE_THRESHOLDS.get(stat)
    return threshold is not None and value > threshold


def playoff_picture(canonical: dict[str, Any] | Any, save_path: str | Path, *, prepared_save: dict[str, Any] | None = None) -> dict[str, Any]:
    # Read-only here; deep-copying the whole league each round also defeated the action's cached copy.
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    rows = league_standings(canonical, save_path, prepared_save=save)["standings"]
    by_conference: dict[str, list[dict[str, Any]]] = {"East": [], "West": []}
    for row in rows:
        conference = row["team"].get("conference")
        if conference in by_conference:
            by_conference[conference].append(row)
    picture = {}
    for conference, teams in by_conference.items():
        ranked = sorted(teams, key=lambda item: (-item["win_pct"], -item["point_diff"], item["team"]["abbrev"]))
        picture[conference] = [
            {**row, "seed": idx}
            for idx, row in enumerate(ranked[:10], start=1)
        ]
    return {"as_of_date": save.get("state", {}).get("current_date"), "picture": picture, "playoff_state": save.get("playoff_state", {})}


def start_playoffs(canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, include_play_in: bool = False) -> dict[str, Any]:
    # Read-only here; deep-copying the whole league each round also defeated the action's cached copy.
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = initialize_postseason(canonical, save, save_path, seed, include_play_in=include_play_in)
    write_save(save_path, save)
    return state


def initialize_postseason(canonical: dict[str, Any], save: dict[str, Any], save_path: str | Path, seed: int, *, include_play_in: bool = True) -> dict[str, Any]:
    if save.get("playoff_state"):
        return save["playoff_state"]
    from .trade_tax import record_season_payrolls
    record_season_payrolls(save, canonical)  # each team's final payroll, for repeat-taxpayer rates (trade step 4)
    picture = playoff_picture(canonical, save_path, prepared_save=save)["picture"]
    if not include_play_in:
        series = legacy_first_round_series(canonical, picture)
        save["playoff_state"] = {
            "year": str(season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)),
            "seed": seed,
            "round": "first_round",
            "status": "in_progress",
            "play_in": {},
            "series": series,
            "games": [],
            "champion_team_id": None,
        }
        add_news(save, "playoffs", "Playoff bracket generated from save standings.")
        return save["playoff_state"]
    play_in: dict[str, Any] = {}
    locked_seeds: dict[str, Any] = {}
    for conference, seeded in picture.items():
        by_seed = {row["seed"]: row for row in seeded}
        locked_seeds[conference] = {str(seed_no): by_seed[seed_no]["team_id"] for seed_no in range(1, 7) if seed_no in by_seed}
        play_in[conference] = {
            "status": "scheduled",
            "teams": {str(seed_no): by_seed[seed_no]["team_id"] for seed_no in range(7, 11) if seed_no in by_seed},
            "games": [],
            "seed_7_team_id": None,
            "seed_8_team_id": None,
        }
    save["playoff_state"] = {
        "year": str(season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)),
        "seed": seed,
        "round": "play_in",
        "status": "in_progress",
        "play_in": play_in,
        "locked_seeds": locked_seeds,
        "series": [],
        "games": [],
        "champion_team_id": None,
    }
    add_news(save, "playoffs", "Play-in tournament generated from save standings.")
    return save["playoff_state"]


def legacy_first_round_series(canonical: dict[str, Any], picture: dict[str, Any]) -> list[dict[str, Any]]:
    del canonical
    series: list[dict[str, Any]] = []
    matchups = [(1, 8), (4, 5), (3, 6), (2, 7)]
    for conference, seeded in picture.items():
        by_seed = {row["seed"]: row for row in seeded}
        for slot, (high_seed, low_seed) in enumerate(matchups):
            if high_seed not in by_seed or low_seed not in by_seed:
                continue
            series.append({**playoff_series_record(conference, "first_round", by_seed[high_seed]["team_id"], by_seed[low_seed]["team_id"]), "bracket_slot":slot})
    return series


def simulate_playoff_round(canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, root: str | Path | None = None, *, advance_to_offseason: bool = True) -> dict[str, Any]:
    # Read-only here; deep-copying the whole league each round also defeated the action's cached copy.
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state") or start_playoffs(canonical, save_path, seed=seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state", state)
    current_round = state.get("round")
    if current_round == "play_in":
        completed_play_in = simulate_play_in(canonical, save, seed, root)
        for conference in completed_play_in:
            add_news(save, "playoffs", f"{conference} play-in tournament completed.")
        save["playoff_state"] = state
        update_save_date_to_latest_playoff_game(save)
        write_save(save_path, save)
        return {"completed_play_in": completed_play_in, "playoff_state": state}
    completed: list[dict[str, Any]] = []
    for _ in range(7):
        day = simulate_playoff_day(canonical, save, state, seed, root, advance_to_offseason=advance_to_offseason)
        completed.extend(day["completed_series"])
        if not day["games"] or simulation_stop_requested() or state.get("round") != current_round or state.get("status") == "completed":
            break
    save["playoff_state"] = state
    update_save_date_to_latest_playoff_game(save)
    ensure_year_end_recap_safely(canonical, save, save_path)
    write_save(save_path, save)
    return {"completed_series": completed, "playoff_state": state}


def complete_playoff_champion(canonical: dict[str, Any], save: dict[str, Any], state: dict[str, Any], winner_team_id: str, root: str | Path | None = None, *, advance_to_offseason: bool = True) -> None:
    state["champion_team_id"] = winner_team_id
    state["status"] = "completed"
    state["round"] = "champion"
    emit_progress(save, "postseason")
    add_news(save, "champion", f"{team_by_id(canonical, winner_team_id)['abbrev']} wins the NBA title.")
    award_finals_mvp(save, canonical)
    # Season awards are decided when the playoffs end (the year-end recap shows them before the lottery); the
    # rollover's call later finds them and does nothing.
    generate_league_awards(canonical, save, save.get("meta", {}).get("season") or CANONICAL_SEASON, int(state.get("seed") or 1))
    user_team_id = save.get("meta", {}).get("user_team_id")
    if user_team_id:
        headline = f"Season complete: {team_by_id(canonical, winner_team_id)['abbrev']} wins the NBA title."
        save.setdefault("pending_press_events", []).append(
            {
                "id": stable_id("press_event", "season_end", headline, state.get("year")),
                "date": f"{int(state.get('year') or season_end_year(save.get('meta', {}).get('season') or CANONICAL_SEASON))}-06-22",
                "kind": "season_end",
                "headline": headline,
                "question": "The season is over. What is your honest read on where this organization stands now?",
                "status": "pending",
            }
        )
    if advance_to_offseason:
        advance_lifecycle_to(canonical, save, f"{int(state.get('year') or season_end_year(save.get('meta', {}).get('season') or CANONICAL_SEASON))}-06-22", int(state.get("seed", 1)), root)


def simulate_next_playoff_game(canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, root: str | Path | None = None, *, advance_to_offseason: bool = True) -> dict[str, Any]:
    # Read-only here; deep-copying the whole league each round also defeated the action's cached copy.
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state") or start_playoffs(canonical, save_path, seed=seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state", state)
    current_round = state.get("round")
    if current_round == "play_in":
        completed = simulate_play_in_day(canonical, save, seed, root)
        write_save(save_path, save)
        return {"status": "simulated_game", "completed_play_in": completed, "playoff_state": state}
    result = simulate_playoff_day(canonical, save, state, seed, root, advance_to_offseason=advance_to_offseason)
    save["playoff_state"] = state
    update_save_date_to_latest_playoff_game(save)
    ensure_year_end_recap_safely(canonical, save, save_path)
    write_save(save_path, save)
    return result


def playoff_next_game_date(state: dict[str, Any], series: dict[str, Any]) -> str:
    base = playoff_round_start_date(int(state["year"]), series.get("round"))
    return (base + timedelta(days=int(series.get("calendar_shift_days") or 0) + len(series.get("game_ids") or []) * 2)).isoformat()


def playoff_game_fixture(canonical: dict[str, Any], away: str, home: str, day: str, key: str) -> dict[str, Any]:
    espn_by_team = {team["id"]: espn_id for espn_id, team in espn_team_id_map(canonical).items()}
    return {"externalGameId": stable_id("playoff_game", day[:4], key, away, home), "gameDate": day, "phase": "playoffs",
            "awayTeamId": espn_by_team.get(away, away), "homeTeamId": espn_by_team.get(home, home)}


def simulate_playoff_day(canonical: dict[str, Any], save: dict[str, Any], state: dict[str, Any], seed: int, root: str | Path | None, *, advance_to_offseason: bool = True) -> dict[str, Any]:
    if simulation_stop_requested():
        return {"status": "stopped", "playoff_state": state, "games": [], "completed_series": []}
    repair_unplayed_playoff_round(state)
    current_round = state.get("round")
    open_series = [
        series for series in state.get("series", [])
        if series.get("round") == current_round and series.get("status") != "completed"
    ]
    if not open_series:
        return {"status": "no_open_series", "playoff_state": state, "games": [], "completed_series": []}
    earliest = min(playoff_next_game_date(state, series) for series in open_series)
    current = str(save.get("state", {}).get("current_date") or earliest)
    floor = current
    if all(not series.get("game_ids") for series in open_series) and state.get("games"):
        floor = max(floor, next_date_str(max(g["gameDate"] for g in state["games"]), 2))
    if earliest < floor:
        # Old saves may have advanced the calendar beyond unfinished games.
        # Move the remaining round together instead of simulating in the past.
        shift = (parse_date(floor) - parse_date(earliest)).days
        for series in open_series:
            series["calendar_shift_days"] = int(series.get("calendar_shift_days") or 0) + shift
        earliest = floor
    open_series = [s for s in open_series if playoff_next_game_date(state, s) == earliest]
    games = []
    for series in open_series:
        a, b = series["team_ids"]
        number = len(series.get("game_ids") or []) + 1
        home = a if number in {1, 2, 5, 7} else b
        games.append(playoff_game_fixture(canonical, b if home == a else a, home, earliest, f"{series['id']}:g{number}"))
    advance_lifecycle_to(canonical, save, earliest, seed, root, games=games)
    lifecycle_date = str((save.get("lifecycle_state") or {}).get("through_date") or "")
    if simulation_stop_requested() and lifecycle_date < earliest:
        return {"status": "stopped", "playoff_state": state, "games": [], "completed_series": []}
    results: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    for series in open_series:
        result = simulate_one_series_game(canonical, save, state, series, seed, root)
        results.append(result)
        if max((series.get("wins") or {}).values(), default=0) >= 4:
            winner = max((series.get("wins") or {}).items(), key=lambda item: item[1])[0]
            series["winner_team_id"] = winner
            series["status"] = "completed"
            completed.append(series)
            add_news(save, "playoffs", f"{team_by_id(canonical, winner)['abbrev']} wins {series['round']} series.")
        emit_progress(save, "game", game=result, series_id=series["id"])
    current_series = [item for item in state.get("series", []) if item.get("round") == current_round]
    if current_series and all(item.get("status") == "completed" for item in current_series):
        winners = [item["winner_team_id"] for item in current_series if item.get("winner_team_id")]
        if current_round == "finals" and len(winners) == 1:
            complete_playoff_champion(canonical, save, state, winners[0], root, advance_to_offseason=advance_to_offseason)
        else:
            next_round = next_playoff_round(current_round)
            state["round"] = next_round
            state["series"].extend(next_round_series(canonical, state, winners, next_round))
    emit_progress(save, "postseason")
    return {"status": "simulated_game", "game": results[0] if results else None, "games": results, "completed_series": completed, "playoff_state": state}


def simulate_one_series_game(
    canonical: dict[str, Any],
    save: dict[str, Any],
    state: dict[str, Any],
    series: dict[str, Any],
    seed: int,
    root: str | Path | None,
) -> dict[str, Any]:
    team_a, team_b = series["team_ids"]
    wins = {team_a: 0, team_b: 0, **(series.get("wins") or {})}
    game_no = len(series.get("game_ids") or []) + 1
    home = team_a if game_no in {1, 2, 5, 7} else team_b
    away = team_b if home == team_a else team_a
    year = int(state.get("year") or season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON))
    base = playoff_round_start_date(year, series.get("round")) + timedelta(days=int(series.get("calendar_shift_days") or 0))
    game_date = (base + timedelta(days=(game_no - 1) * 2)).isoformat()
    result = simulate_playoff_game(canonical, save, root, away, home, game_date, seed, f"{series['id']}:g{game_no}")
    winner = game_winner_team_id(result)
    wins[winner] = int(wins.get(winner) or 0) + 1
    series["wins"] = wins
    series.setdefault("game_ids", []).append(result.get("game_id"))
    series["game_ids"] = list(dict.fromkeys(series.get("game_ids", [])))
    return result


def lottery_seed(seed: int | None = None) -> int:
    if seed is not None:
        return int(seed)
    return random.SystemRandom().randrange(1, 2_147_483_647)


def run_draft_lottery(canonical: dict[str, Any] | Any, save_path: str | Path, year: str = "2026", seed: int | None = None, *, advance_to_draft: bool = True) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    from .draft import generate_draft_order

    effective_seed = lottery_seed(seed)
    standings = save_standings_for_draft(canonical, save)
    order = generate_draft_order(canonical_with_save(canonical, save), year, seed=effective_seed, standings=standings)
    annotate_lottery_odds_context(canonical, save, order)
    from .pick_presentation import materialize_nested_inputs
    nested_context = canonical_with_save(canonical, save)
    nested_context["pick_obligations"] = save.get("pick_obligations", [])
    materialize_nested_inputs(nested_context)
    resolve_pick_obligations_for_year(save, order, str(year))
    refresh_draft_order_from_save(order, save)
    materialize_draft_order_pick_assets(canonical, save, order)
    save.setdefault("draft_orders", {})[str(year)] = order
    add_news(save, "draft_lottery", f"{year} draft order generated.")
    current_phase = save.get("state", {}).get("phase")
    if current_phase == "draft_lottery" and advance_to_draft:
        advance_lifecycle_to(canonical, save, f"{year}-06-25", int(save.get("meta", {}).get("seed", 1)))
    write_save(save_path, save)
    return order


def annotate_lottery_odds_context(canonical: dict[str, Any], save: dict[str, Any], order: dict[str, Any]) -> None:
    lottery = order.get("lottery") or {}
    if not lottery.get("odds_by_team"):
        return
    from .transactions import pick_obligation_context_note, with_transaction_context

    active = with_transaction_context(canonical_with_save(canonical, save))
    picks = {pick.get("id"): pick for pick in active.get("draft_picks", [])}
    context: dict[str, str] = {}
    for row in order.get("draft_order") or []:
        if int(row.get("round") or 0) != 1:
            continue
        original = row.get("original_team_id")
        if original not in lottery.get("odds_by_team", {}):
            continue
        pick = picks.get(row.get("id") or row.get("pick_id"))
        if not pick:
            continue
        owner = pick.get("current_owner_team_id")
        parts: list[str] = []
        if owner and owner != original:
            parts.append(f"[owned by {team_id_to_abbrev(owner)}]")
        protection = (
            pick_obligation_context_note(active, pick)
            if lottery_pick_is_primary_protected_pick(save, pick.get("id") or row.get("id") or row.get("pick_id"))
            else ""
        )
        if protection:
            parts.append(f"[{protection}]")
        if parts:
            context[original] = " ".join(parts)
    lottery["odds_context_by_team"] = context
    order["lottery"] = lottery


def lottery_pick_is_primary_protected_pick(save: dict[str, Any], pick_id: str | None) -> bool:
    if not pick_id:
        return False
    return any(
        obligation.get("type") == "protected_pick"
        and obligation.get("status", "active") in {"active", "pending_resolution"}
        and obligation.get("primary_pick_id") == pick_id
        for obligation in save.get("pick_obligations", [])
    )


def refresh_draft_order_from_save(order: dict[str, Any], save: dict[str, Any]) -> None:
    overrides = save.get("draft_pick_overrides") or {}
    for row in order.get("draft_order") or []:
        pick_id = row.get("id") or row.get("pick_id")
        if not pick_id:
            continue
        row["pick_id"] = pick_id
        row["id"] = pick_id
        owner = overrides.get(pick_id) or row.get("current_owner_team_id") or row.get("owner_team_id")
        if owner == "used_draft_pick":
            continue
        if owner:
            row["current_owner_team_id"] = owner
            row["owner_team_id"] = owner
            row["team_abbrev"] = team_id_to_abbrev(owner)


def materialize_draft_order_pick_assets(canonical: dict[str, Any], save: dict[str, Any], order: dict[str, Any]) -> int:
    """Persist modeled slot picks that do not exist in the baseline ledger.

    Real future ledgers occasionally omit a team's own pick because the source
    only described conveyed assets. The lottery still needs one unique pick per
    original team and round. Persisting those modeled rows makes the live slot
    available to draft-night valuation and trade code instead of leaving a
    display-only ID behind.
    """
    existing_ids = {
        pick.get("id")
        for pick in [*canonical.get("draft_picks", []), *save.get("generated_draft_picks", [])]
        if pick.get("id")
    }
    generated = {
        pick.get("id"): pick
        for pick in save.setdefault("generated_draft_picks", [])
        if pick.get("id")
    }
    added = 0
    for row in order.get("draft_order", []) or []:
        pick_id = row.get("id") or row.get("pick_id")
        if not pick_id or pick_id in existing_ids:
            continue
        owner = row.get("current_owner_team_id") or row.get("owner_team_id") or row.get("original_team_id")
        season = str(row.get("draft_year") or row.get("season") or order.get("year") or "")
        round_no = int(row.get("round") or (1 if int(row.get("overall_pick") or 60) <= 30 else 2))
        generated[pick_id] = {
            "id": pick_id,
            "season": season,
            "round": round_no,
            "overall_pick": int(row.get("overall_pick") or 0),
            "projected_pick_slot": int(row.get("overall_pick") or 0),
            "original_team_id": row.get("original_team_id"),
            "current_owner_team_id": owner,
            "team_id": owner,
            "status": "generated_live_draft_pick",
            "source_ids": list(row.get("source_ids") or ["src_draft_model_config_v1"]),
            "notes": "Modeled live-draft pick materialized from the saved lottery/order because no baseline ledger asset existed.",
        }
        existing_ids.add(pick_id)
        added += 1
    save["generated_draft_picks"] = [generated[pick_id] for pick_id in sorted(generated)]
    return added


def resolve_pick_obligations_for_year(save: dict[str, Any], order: dict[str, Any], year: str) -> None:
    from .pick_rules import protection_bounds, ordered_pick_obligations

    for term in save.get("pick_obligations", []):
        if term.get("type") == "protected_pick" and term.get("status") in {"active", "pending_resolution"} and str(term.get("season")) == str(year):
            protection_bounds(term)
    draft_order = order.get("draft_order") or []
    by_pick = {}
    for item in draft_order:
        if item.get("id"):
            by_pick[item.get("id")] = item
        if item.get("pick_id"):
            by_pick[item.get("pick_id")] = item
    locked = set(save.setdefault("locked_pick_assets", []))
    for obligation in ordered_pick_obligations(save.get("pick_obligations", [])):
        if obligation.get("status") not in {"active", "pending_resolution"}:
            continue
        if str(obligation.get("season") or "") != str(year):
            continue
        if obligation.get("type") == "protected_pick":
            pick_id = obligation.get("primary_pick_id")
            row = by_pick.get(pick_id)
            if not row:
                continue
            overall = int(row.get("overall_pick") or 999)
            low, high = protection_bounds(obligation)
            sender = obligation.get("sender_team_id")
            current_holder = save.get("draft_pick_overrides", {}).get(pick_id) or row.get("current_owner_team_id")
            receiver = current_holder if current_holder and current_holder != sender else obligation.get("receiver_team_id")
            if low <= overall <= high and sender:
                row["current_owner_team_id"] = sender
                save.setdefault("draft_pick_overrides", {})[pick_id] = sender
                fallback_id = next((pid for pid in obligation.get("fallback_pick_ids") or [] if pid), None)
                if fallback_id and receiver and receiver != sender:
                    save.setdefault("draft_pick_overrides", {})[fallback_id] = receiver
                    locked.discard(fallback_id)
                    add_league_event(
                        save,
                        "pick_protection",
                        f"Protected pick stayed with {team_id_to_abbrev(sender)}; fallback pick conveys to {team_id_to_abbrev(receiver)}.",
                        date_value=save.get("state", {}).get("current_date"),
                        team_ids=[sender, receiver],
                        importance=0.64,
                        details={"obligation_id": obligation.get("id"), "primary_pick_id": pick_id, "fallback_pick_id": fallback_id},
                    )
                obligation["status"] = "resolved_protected_fallback_conveyed"
            else:
                if receiver:
                    row["current_owner_team_id"] = receiver
                    save.setdefault("draft_pick_overrides", {})[pick_id] = receiver
                for fallback_id in obligation.get("fallback_pick_ids") or []:
                    locked.discard(fallback_id)
                obligation["status"] = "resolved_primary_conveyed"
                add_league_event(
                    save,
                    "pick_protection",
                    f"Protected pick conveys to {team_id_to_abbrev(receiver)}.",
                    date_value=save.get("state", {}).get("current_date"),
                    team_ids=[sender, receiver],
                    importance=0.56,
                    details={"obligation_id": obligation.get("id"), "primary_pick_id": pick_id},
                )
        elif obligation.get("type") == "pick_swap":
            from .transactions import pick_swap_benefit

            slots = obligation.get("allocation_slot_pick_ids") or []
            if obligation.get("allocation_comparison") and slots:
                pool = obligation.get("comparison_pool_pick_ids") or []
                if set(slots) != set(pool) or len(slots) != len(set(slots)) or any(pid not in by_pick for pid in pool):
                    raise ValueError(f"Invalid ranked allocation for {obligation.get('id')}.")
                recipients = [save.get("draft_pick_overrides", {}).get(pid) or by_pick[pid].get("current_owner_team_id") or by_pick[pid].get("owner_team_id") for pid in slots]
                if any(not owner or owner == "used_draft_pick" for owner in recipients):
                    raise ValueError(f"Ranked allocation {obligation.get('id')} has an unavailable recipient.")
                outcomes = sorted(pool, key=lambda pid: (int(by_pick[pid].get("overall_pick") or 999), pid))
                for pid, recipient in zip(outcomes, recipients):
                    by_pick[pid]["current_owner_team_id"] = recipient
                    save.setdefault("draft_pick_overrides", {})[pid] = recipient
                for row in save.get("pick_obligations", []):
                    if row.get("allocation_comparison") and row.get("status") in {"active", "pending_resolution"} and set(row.get("comparison_pool_pick_ids") or []) == set(pool):
                        row["status"] = "resolved_ranked_allocation"
                        row["resolved_date"] = save.get("state", {}).get("current_date")
                        row["resolved_ranked_pick_ids"] = outcomes
                add_league_event(save, "pick_swap", "Ranked pick entitlements resolved to their guaranteed draft positions.",
                                date_value=save.get("state", {}).get("current_date"), team_ids=sorted(set(recipients)),
                                importance=0.5, details={"pool_pick_ids": pool, "ranked_pick_ids": outcomes, "recipient_team_ids": recipients})
                continue
            pick_a_id = obligation.get("team_a_pick_id") or obligation.get("primary_pick_id")
            pick_b_id = obligation.get("team_b_pick_id") or obligation.get("counterparty_pick_id")
            row_a = by_pick.get(pick_a_id)
            row_b = by_pick.get(pick_b_id)
            pool = obligation.get("comparison_pool_pick_ids") or []
            nested_input = obligation.get("nested_input")
            if nested_input:
                # Explicit dependency identity, unaffected by the recipient
                # trading this ONE outcome to a different team.
                def resolve_input(reference):
                    predecessor = reference.get("obligation_id")
                    if not predecessor:
                        return reference.get("pick_id")
                    prior = next((term for term in save.get("pick_obligations", []) if term.get("id") == predecessor), None)
                    field = "resolved_remainder_pick_id" if reference.get("outcome") == "remainder" else "resolved_output_pick_id"
                    output = (prior or {}).get(field)
                    if not output:
                        raise ValueError(f"Nested swap {obligation.get('id')} has no resolved input from {predecessor}.")
                    return output
                pick_a_id = resolve_input(nested_input)
                pick_b_id = resolve_input(obligation.get("nested_other_input") or {"pick_id": obligation.get("nested_other_pick_id")})
                row_a, row_b = by_pick.get(pick_a_id), by_pick.get(pick_b_id)
                if not row_a or not row_b or pick_a_id == pick_b_id:
                    raise ValueError(f"Nested swap {obligation.get('id')} requires two distinct existing picks.")
            elif pool:
                # Source allocations are composed from ordinary two-pick
                # comparisons. Follow the currently held asset after an
                # earlier comparison rather than swapping its old identity.
                from .transactions import pick_swap_benefit
                holder = obligation.get("comparison_holder_team_id")
                other = obligation.get("comparison_counterparty_team_id")
                held = [by_pick[pid] for pid in pool if pid in by_pick and
                    (save.get("draft_pick_overrides", {}).get(pid) or by_pick[pid].get("current_owner_team_id")) == holder]
                opposite = [by_pick[pid] for pid in pool if pid in by_pick and
                    (save.get("draft_pick_overrides", {}).get(pid) or by_pick[pid].get("current_owner_team_id")) == other]
                if not held or not opposite:
                    obligation["status"] = "resolved_swap_subject_unavailable"
                    continue
                better = pick_swap_benefit(obligation) == "better"
                row_a = (max if better else min)(held, key=lambda row: int(row.get("overall_pick") or 999))
                row_b = (min if better else max)(opposite, key=lambda row: int(row.get("overall_pick") or 999))
                pick_a_id = row_a.get("pick_id") or row_a.get("id")
                pick_b_id = row_b.get("pick_id") or row_b.get("id")
            protected_subjects = obligation.get("subject_protected_top_n") or {}
            if any(row and int(row.get("overall_pick") or 999) <= int(protected_subjects.get(pid) or 0)
                   for pid, row in [(pick_a_id, row_a), (pick_b_id, row_b)]):
                obligation["status"] = "resolved_swap_subject_protected"
                continue
            rights_holder = (
                obligation.get("current_rights_holder_team_id")
                or obligation.get("original_rights_holder_team_id")
                or obligation.get("receiver_team_id")
            )
            if not row_a or not row_b or not rights_holder:
                continue
            owner_a = save.get("draft_pick_overrides", {}).get(pick_a_id) or row_a.get("current_owner_team_id") or row_a.get("owner_team_id")
            owner_b = save.get("draft_pick_overrides", {}).get(pick_b_id) or row_b.get("current_owner_team_id") or row_b.get("owner_team_id")
            overall_a = int(row_a.get("overall_pick") or 999)
            overall_b = int(row_b.get("overall_pick") or 999)
            if overall_a <= overall_b:
                better_id, better_row, better_owner = pick_a_id, row_a, owner_a
                worse_id, worse_row, worse_owner = pick_b_id, row_b, owner_b
            else:
                better_id, better_row, better_owner = pick_b_id, row_b, owner_b
                worse_id, worse_row, worse_owner = pick_a_id, row_a, owner_a
            benefit = pick_swap_benefit(obligation)
            target_id, target_row, target_owner = (better_id, better_row, better_owner) if benefit == "better" else (worse_id, worse_row, worse_owner)
            other_id, other_row, other_owner = (worse_id, worse_row, worse_owner) if benefit == "better" else (better_id, better_row, better_owner)
            obligation["resolved_output_pick_id"] = target_id
            obligation["resolved_remainder_pick_id"] = other_id
            if target_owner == rights_holder:
                obligation["status"] = "resolved_swap_not_exercised" if benefit == "better" else "resolved_less_favorable_already_held"
                obligation["resolved_date"] = save.get("state", {}).get("current_date")
                obligation["resolved_better_pick_id"] = better_id
                obligation["resolved_worse_pick_id"] = worse_id
                add_league_event(
                    save,
                    "pick_swap",
                    (
                        f"{team_id_to_abbrev(rights_holder)} keeps the better pick; swap right is not exercised."
                        if benefit == "better"
                        else f"{team_id_to_abbrev(rights_holder)} already holds the less favorable pick from the swap obligation."
                    ),
                    date_value=save.get("state", {}).get("current_date"),
                    team_ids=sorted({rights_holder, owner_a, owner_b} - {None}),
                    importance=0.42,
                    details={
                        "obligation_id": obligation.get("id"),
                        "better_pick_id": better_id,
                        "worse_pick_id": worse_id,
                        "benefit": benefit,
                        "exercised": False,
                    },
                )
                continue
            displaced_owner = target_owner or obligation.get("counterparty_team_id") or other_owner
            if rights_holder:
                save.setdefault("draft_pick_overrides", {})[target_id] = rights_holder
                target_row["current_owner_team_id"] = rights_holder
                target_row["owner_team_id"] = rights_holder
                target_row["team_abbrev"] = team_id_to_abbrev(rights_holder)
            if displaced_owner:
                save.setdefault("draft_pick_overrides", {})[other_id] = displaced_owner
                other_row["current_owner_team_id"] = displaced_owner
                other_row["owner_team_id"] = displaced_owner
                other_row["team_abbrev"] = team_id_to_abbrev(displaced_owner)
            obligation["status"] = "resolved_swap_exercised" if benefit == "better" else "resolved_less_favorable_assigned"
            obligation["resolved_date"] = save.get("state", {}).get("current_date")
            obligation["resolved_better_pick_id"] = better_id
            obligation["resolved_worse_pick_id"] = worse_id
            add_league_event(
                save,
                "pick_swap",
                (
                    f"{team_id_to_abbrev(rights_holder)} exercises pick swap rights and receives the better pick."
                    if benefit == "better"
                    else f"{team_id_to_abbrev(rights_holder)} receives the less favorable pick from a swap obligation."
                ),
                date_value=save.get("state", {}).get("current_date"),
                team_ids=sorted({rights_holder, displaced_owner, owner_a, owner_b} - {None}),
                importance=0.58,
                details={
                    "obligation_id": obligation.get("id"),
                    "better_pick_id": better_id,
                    "worse_pick_id": worse_id,
                    "benefit": benefit,
                    "rights_holder_team_id": rights_holder,
                    "displaced_owner_team_id": displaced_owner,
                    "exercised": True,
                },
            )
    save["locked_pick_assets"] = sorted(locked)


def team_id_to_abbrev(team_id: str | None) -> str:
    return str(team_id or "TEAM").replace("team_", "").upper()


def next_postseason_date(save: dict[str, Any]) -> str | None:
    state = save.get("playoff_state") or {}
    repair_unplayed_playoff_round(state)
    if state.get("status") == "completed":
        return None
    current = save["state"]["current_date"]
    if state.get("round") == "play_in":
        stages = [len(p.get("games") or []) for p in state.get("play_in", {}).values() if p.get("status") != "completed"]
        if not stages:
            return None
        stage = min(stages)
        base = date(int(state["year"]), 4, (13, 14, 16)[min(stage, 2)])
        shift = state.setdefault("play_in_shift_days", max(0, (parse_date(current) - base).days))
        return max(current, (base + timedelta(days=shift)).isoformat())
    series = [s for s in state.get("series", []) if s.get("round") == state.get("round") and s.get("status") != "completed"]
    if not series:
        return None
    earliest = min(playoff_next_game_date(state, s) for s in series)
    floor = current
    if all(not s.get("game_ids") for s in series) and state.get("games"):
        floor = max(floor, next_date_str(max(g["gameDate"] for g in state["games"]), 2))
    return max(floor, earliest)


def advance_postseason_through(canonical: dict[str, Any], save: dict[str, Any], target: str, seed: int, root: str | Path | None) -> None:
    # Process each scheduled batch before advancing the lifecycle beyond it.
    while (day := next_postseason_date(save)) is not None and day <= target:
        if simulation_stop_requested():
            break
        state = save["playoff_state"]
        if state.get("round") == "play_in":
            simulate_play_in_day(canonical, save, seed, root)
        else:
            result = simulate_playoff_day(canonical, save, state, seed, root, advance_to_offseason=False)
            if not result["games"]:
                if simulation_stop_requested():
                    break
                raise ValueError("No postseason game could be scheduled.")
        if simulation_stop_requested():
            break


def simulate_play_in_day(canonical: dict[str, Any], save: dict[str, Any], seed: int, root: str | Path | None) -> list[str]:
    if simulation_stop_requested():
        return []
    state = save.setdefault("playoff_state", {})
    day = next_postseason_date(save)
    if day is None:
        return []
    completed: list[str] = []
    fixtures = []
    # Full box scores may already be archived after the previous advance.
    results = {r["game_id"]: r for r in [*save.get("game_result_summaries", []), *save.get("game_results", [])]}
    for conference, payload in (state.get("play_in") or {}).items():
        if payload.get("status") == "completed":
            continue
        teams = payload.get("teams") or {}
        if not all(str(seed_no) in teams for seed_no in [7, 8, 9, 10]):
            raise ValueError(f"{conference} play-in requires seeds 7 through 10.")
        prior = [results[g] for g in payload.get("games", [])]
        stage = len(prior)
        away, home = (teams["8"], teams["7"]) if stage == 0 else (teams["10"], teams["9"]) if stage == 1 else (game_winner_team_id(prior[1]), game_loser_team_id(prior[0]))
        fixtures.append((conference, payload, away, home, f"{conference}:{('7v8', '9v10', '8seed')[stage]}"))
    advance_lifecycle_to(canonical, save, day, seed, root,
                         games=[playoff_game_fixture(canonical, away, home, day, key) for _, _, away, home, key in fixtures])
    lifecycle_date = str((save.get("lifecycle_state") or {}).get("through_date") or "")
    if simulation_stop_requested() and lifecycle_date < day:
        return []
    for conference, payload, away, home, key in fixtures:
        result = simulate_playoff_game(canonical, save, root, away, home, day, seed, key)
        payload.setdefault("games", []).append(result["game_id"])
        if len(payload["games"]) == 1:
            payload["seed_7_team_id"] = game_winner_team_id(result)
        if len(payload["games"]) == 3:
            payload.update(seed_8_team_id=game_winner_team_id(result), status="completed")
            completed.append(conference)
        emit_progress(save, "game", game=result)
    if all(p.get("status") == "completed" for p in state["play_in"].values()):
        state["series"].extend(first_round_series_from_play_in(canonical, state))
        state["round"] = "first_round"
    emit_progress(save, "postseason")
    return completed


def simulate_play_in(canonical: dict[str, Any], save: dict[str, Any], seed: int, root: str | Path | None) -> list[str]:
    completed = []
    while save["playoff_state"].get("round") == "play_in":
        if simulation_stop_requested():
            break
        completed.extend(simulate_play_in_day(canonical, save, seed, root))
        if simulation_stop_requested():
            break
    return completed


def first_round_series_from_play_in(canonical: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    matchups = [("1", "8"), ("4", "5"), ("3", "6"), ("2", "7")]
    for conference, locked in (state.get("locked_seeds") or {}).items():
        play_in = (state.get("play_in") or {}).get(conference, {})
        seeds = dict(locked)
        if play_in.get("seed_7_team_id"):
            seeds["7"] = play_in["seed_7_team_id"]
        if play_in.get("seed_8_team_id"):
            seeds["8"] = play_in["seed_8_team_id"]
        for slot, (high_seed, low_seed) in enumerate(matchups):
            if high_seed not in seeds or low_seed not in seeds:
                continue
            series.append({**playoff_series_record(conference, "first_round", seeds[high_seed], seeds[low_seed]), "bracket_slot":slot})
    return series


def simulate_series_games(
    canonical: dict[str, Any],
    save: dict[str, Any],
    state: dict[str, Any],
    series: dict[str, Any],
    seed: int,
    root: str | Path | None,
) -> None:
    team_a, team_b = series["team_ids"]
    wins = {team_a: 0, team_b: 0, **(series.get("wins") or {})}
    year = int(state.get("year") or season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON))
    base = playoff_round_start_date(year, series.get("round"))
    for game_no in range(len(series.get("game_ids") or []) + 1, 8):
        if max(wins.values()) >= 4:
            break
        home = team_a if game_no in {1, 2, 5, 7} else team_b
        away = team_b if home == team_a else team_a
        game_date = (base + timedelta(days=(game_no - 1) * 2)).isoformat()
        result = simulate_playoff_game(canonical, save, root, away, home, game_date, seed, f"{series['id']}:g{game_no}")
        winner = game_winner_team_id(result)
        wins[winner] += 1
        series.setdefault("game_ids", []).append(result.get("game_id"))
    series["wins"] = wins


def playoff_round_start_date(year: int, round_name: str | None) -> date:
    starts = {
        "first_round": date(year, 4, 18),
        "conference_semifinals": date(year, 5, 3),
        "conference_finals": date(year, 5, 18),
        "finals": date(year, 6, 4),
    }
    return starts.get(str(round_name), date(year, 4, 18))


def simulate_playoff_game(
    canonical: dict[str, Any],
    save: dict[str, Any],
    root: str | Path | None,
    away_team_id: str,
    home_team_id: str,
    game_date: str,
    seed: int,
    key: str,
) -> dict[str, Any]:
    game = playoff_game_fixture(canonical, away_team_id, home_team_id, game_date, key)
    game_id = game["externalGameId"]
    legacy_id = stable_id("playoff_game", key, away_team_id, home_team_id)
    existing = next((result for result in [*save.get("game_results", []), *save.get("game_result_summaries", [])]
                     if str(result.get("game_id")) in {game_id, legacy_id}), None)
    if existing:
        return existing
    active = advance_lifecycle_to(canonical, save, game_date, seed, root, games=[game])["active"]
    if root is None:
        return deterministic_playoff_game_result(canonical, save, away_team_id, home_team_id, game_id, game_date, seed)
    runtime = _ADVANCE_RUNTIME_STATE.get()
    # Inside an action scope the reference tables are loaded once; the indexes are built once, after the
    # playoff game joins the schedule (the first build in load_sim_context was discarded anyway).
    context = (load_sim_context(root, active, reference=runtime.reference_tables(root), indices=False)
               if runtime is not None else load_sim_context(root, active))
    context["schedule"] = list(context.get("schedule") or []) + [game]
    context["indices"] = build_sim_indices(context)
    context["indices"]["coach_by_team"] = save_coach_ratings(active, save)
    result = to_plain(sim_game_with_context(context, game_id, mode="sandbox-sim", seed=seed))
    record_playoff_game_result(save, game, result)
    add_box_score_fatigue(active, save.setdefault("health_states", []), result, game_date, root)
    return result


def deterministic_playoff_game_result(
    canonical: dict[str, Any],
    save: dict[str, Any],
    away_team_id: str,
    home_team_id: str,
    game_id: str,
    game_date: str,
    seed: int,
) -> dict[str, Any]:
    away_score = int(round(104 + playoff_team_score(save.get("team_records", {}).get(away_team_id, {}), away_team_id, seed) * 0.11))
    home_score = int(round(107 + playoff_team_score(save.get("team_records", {}).get(home_team_id, {}), home_team_id, seed) * 0.11))
    if away_score == home_score:
        home_score += 1
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    result = {
        "game_id": game_id,
        "mode": "playoff-deterministic",
        "seed": seed,
        "away_team_id": away_team_id,
        "home_team_id": home_team_id,
        "away_score": away_score,
        "home_score": home_score,
        "team_lines": [
            {"team_id": away_team_id, "team_abbrev": teams.get(away_team_id, {}).get("abbrev"), "points": away_score, "overtime_periods": 0},
            {"team_id": home_team_id, "team_abbrev": teams.get(home_team_id, {}).get("abbrev"), "points": home_score, "overtime_periods": 0},
        ],
        "player_lines": [],
    }
    record_playoff_game_result(save, {"externalGameId": game_id, "gameDate": game_date}, result)
    return result


def record_playoff_game_result(save: dict[str, Any], game: dict[str, Any], result: dict[str, Any]) -> None:
    game_id = str(result["game_id"])
    if game_id in set(save.get("schedule_state", {}).get("simulated_game_ids", [])):
        return
    save.setdefault("game_results", []).append(result)
    save.setdefault("schedule_state", {}).setdefault("simulated_game_ids", []).append(game_id)
    save["schedule_state"]["simulated_game_ids"] = sorted(set(save["schedule_state"]["simulated_game_ids"]))
    playoff_game = {
        "externalGameId": game_id,
        "gameDate": game.get("gameDate"),
        "phase": "playoffs",
        "away_team_id": result.get("away_team_id"),
        "home_team_id": result.get("home_team_id"),
    }
    save.setdefault("playoff_state", {}).setdefault("games", []).append(playoff_game)
    save["playoff_state"]["games"] = sorted(
        {item["externalGameId"]: item for item in save["playoff_state"].get("games", [])}.values(),
        key=lambda item: (item.get("gameDate", ""), item.get("externalGameId", "")),
    )
    update_playoff_player_stats(save, result, game.get("gameDate"))


def update_playoff_player_stats(save: dict[str, Any], result: dict[str, Any], game_date: str | None) -> None:
    game_id = str(result.get("game_id") or "")
    if not game_id:
        return
    for line in result.get("player_lines", []) or []:
        player_id = line.get("player_id")
        if not player_id:
            continue
        totals = save.setdefault("playoff_player_stats", {}).setdefault(
            player_id,
            {
                "player_id": player_id,
                "player_name": line.get("player_name"),
                "team_id": line.get("team_id"),
                "team_abbrev": line.get("team_abbrev"),
                "games": 0,
                "game_ids": [],
                "finals_games": 0,
                **{field: 0.0 for field in STAT_FIELDS},
            },
        )
        if game_id in totals.setdefault("game_ids", []):
            continue
        totals["game_ids"].append(game_id)
        totals["games"] = int(totals.get("games") or 0) + 1
        totals["team_id"] = line.get("team_id")
        totals["team_abbrev"] = line.get("team_abbrev")
        if "finals" in game_id:
            totals["finals_games"] = int(totals.get("finals_games") or 0) + 1
        for field in STAT_FIELDS:
            totals[field] = round(float(totals.get(field) or 0.0) + float(line.get(field) or 0.0), 3)
        if (save.get("playoff_state") or {}).get("round") == "finals":
            # The NBA Finals alone (game ids of conference finals also contain "finals"), for the Finals MVP.
            finals = totals.setdefault("nba_finals", {"games": 0, **{field: 0.0 for field in STAT_FIELDS}})
            finals["games"] = int(finals.get("games") or 0) + 1
            for field in STAT_FIELDS:
                finals[field] = round(float(finals.get(field) or 0.0) + float(line.get(field) or 0.0), 3)


def award_finals_mvp(save: dict[str, Any], canonical: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Finals MVP: the champion's player with the highest total Game Score across the NBA Finals games."""
    state = save.get("playoff_state") or {}
    champion = state.get("champion_team_id")
    if not champion:
        return None
    rows = [totals for totals in save.get("playoff_player_stats", {}).values() if totals.get("team_id") == champion]
    finals_rows = [row for row in rows if int((row.get("nba_finals") or {}).get("games") or 0) > 0]
    if finals_rows:
        winner = max(finals_rows, key=lambda row: (finals_game_score(row["nba_finals"]), float(row["nba_finals"].get("points") or 0), str(row.get("player_id"))))
        finals = winner["nba_finals"]
        games = max(1, int(finals.get("games") or 1))
        score = finals_game_score(finals)
        line = {"pts": round(float(finals.get("points") or 0) / games, 1), "reb": round(float(finals.get("rebounds") or 0) / games, 1),
                "ast": round(float(finals.get("assists") or 0) / games, 1), "stl": round(float(finals.get("steals") or 0) / games, 1),
                "blk": round(float(finals.get("blocks") or 0) / games, 1), "gp": int(finals.get("games") or 0)}
        source = "nba_finals_game_score"
    else:
        # Postseasons recorded before the Finals were kept separately: the old whole-playoff rating.
        if not rows:
            return None

        def legacy(row: dict[str, Any]) -> float:
            games = max(1, int(row.get("games") or 1))
            return (float(row.get("points") or 0) + 1.15 * float(row.get("rebounds") or 0) + 1.35 * float(row.get("assists") or 0)
                    + 2.6 * float(row.get("steals") or 0) + 2.6 * float(row.get("blocks") or 0) - 1.1 * float(row.get("turnovers") or 0)) / games
        winner = max(rows, key=legacy)
        score, line, source = legacy(winner), None, "save_playoff_player_stats"
    award = {
        "player_id": winner.get("player_id"),
        "player_name": winner.get("player_name"),
        "team_id": winner.get("team_id"),
        "team_abbrev": winner.get("team_abbrev"),
        "season": save.get("meta", {}).get("season") or CANONICAL_SEASON,
        "impact_score": round(score, 3),
        "finals_line": line,
        "source": source,
    }
    save["finals_mvp"] = award
    date_value = save.get("state", {}).get("current_date") or None
    add_news(save, "finals_mvp", f"{award['player_name']} wins Finals MVP for {award.get('team_abbrev')}.", date_value=date_value)
    return award


def game_winner_team_id(result: dict[str, Any]) -> str:
    return result["home_team_id"] if int(result.get("home_score") or 0) > int(result.get("away_score") or 0) else result["away_team_id"]


def game_loser_team_id(result: dict[str, Any]) -> str:
    return result["away_team_id"] if game_winner_team_id(result) == result["home_team_id"] else result["home_team_id"]


def update_save_date_to_latest_playoff_game(save: dict[str, Any]) -> None:
    if (save.get("playoff_state") or {}).get("status") == "completed":
        return
    dates = [game.get("gameDate") for game in (save.get("playoff_state") or {}).get("games", []) if game.get("gameDate")]
    if not dates:
        return
    latest = max(dates)
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    if latest > current:
        save.setdefault("state", {})["current_date"] = latest
        save["state"]["phase"] = phase_for_date(latest)
        save["state"]["legal_actions"] = legal_actions_for_date(latest)


def offseason_status(canonical: dict[str, Any] | Any, save_path: str | Path) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    return {
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "legal_actions": save.get("state", {}).get("legal_actions", []),
        "playoff_state": save.get("playoff_state", {}),
        "draft_orders": save.get("draft_orders", {}),
        "free_agent_pending_count": len(save.get("pending_contract_negotiations", [])),
        "staff_pending_count": len(save.get("pending_staff_negotiations", [])),
        "notes": "Offseason V1 status: lottery/order, draft, free agency, staff changes, and training camp are scaffolded through save-state commands.",
    }


def ensure_year_end_recap_safely(canonical: dict[str, Any], save: dict[str, Any], save_path: str | Path | None) -> dict[str, Any] | None:
    """The year-end recap, built once the Finals are over (season_slides). A failure is logged, never raised: the
    slideshow is a presentation of results and must not block the calendar."""
    from .season_slides import ensure_year_end_recap
    try:
        return ensure_year_end_recap(canonical if isinstance(canonical, dict) else to_plain(canonical), save, save_path)
    except Exception:  # pragma: no cover - logged
        logging.getLogger(__name__).exception("year-end recap failed")
        return None


def ensure_preseason_outlook_safely(canonical: dict[str, Any], save: dict[str, Any], save_path: str | Path | None) -> dict[str, Any] | None:
    from .season_slides import ensure_preseason_outlook
    try:
        return ensure_preseason_outlook(canonical if isinstance(canonical, dict) else to_plain(canonical), save, save_path)
    except Exception:  # pragma: no cover - logged
        logging.getLogger(__name__).exception("preseason outlook failed")
        return None


def complete_offseason_and_rollover(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    seed: int = 1,
    *,
    prepared_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    current_season = save.get("meta", {}).get("season") or CANONICAL_SEASON
    next_start = season_start_year(current_season) + 1
    # TRADE-VOLUME-2: September's trade chances (trade_calendar.market_day) for the days this jump skips, in one market
    # on the way; a September advanced day by day already ran its own.
    from .trade_calendar import market_day
    today = str(save.get("state", {}).get("current_date") or "")
    september = [f"{next_start}-09-{d:02}" for d in range(1, 31)]
    slots = sum(market_day(day, seed, next_start, trade_deadline_date(next_start))["slots"] for day in september if day > today)
    if slots:
        if today < f"{next_start}-09-15":
            advance_lifecycle_to(canonical, save, f"{next_start}-09-15", seed, root)
        from .play import run_summer_ai_market
        run_summer_ai_market(canonical, save, seed, slots, seed + 1931)
    advance_lifecycle_to(canonical, save, f"{next_start}-09-30", seed, root)
    if simulation_stop_requested():
        write_save(save_path, save)
        return {"status": "stopped", "current_date": save.get("state", {}).get("current_date")}
    draft_result = ensure_draft_processed(canonical, save, str(season_end_year(current_season)), seed)
    awards = generate_league_awards(canonical, save, current_season, seed)
    from .season_slides import slideshow_store
    recap = ensure_year_end_recap_safely(canonical, save, save_path)
    slideshow_store(save)["recaps"].pop(current_season, None)
    history_entry = {
        "season": current_season,
        "completed_on": save.get("state", {}).get("current_date"),
        "team_records": deepcopy(save.get("team_records", {})),
        "player_season_stats": deepcopy(save.get("player_season_stats", {})),
        "playoff_state": deepcopy(save.get("playoff_state", {})),
        "draft_order": deepcopy((save.get("draft_orders") or {}).get(str(season_end_year(current_season)), {})),
        "draft_result": deepcopy(draft_result),
        "awards": deepcopy(awards),
        "recap": recap,
        "transaction_count": len(save.get("transaction_logs", [])),
        "development_months": sorted(save.get("applied_development_months", [])),
    }
    save.setdefault("season_history", []).append(history_entry)
    review = build_year_in_review(canonical, save, save.get("meta", {}).get("user_team_id"), current_season)
    if review:
        upsert_by_id(save, "year_reviews", review)
    next_start = season_start_year(current_season) + 1
    next_label = season_label_from_start(next_start)
    offseason_changes = apply_offseason_roster_transitions(canonical, save, current_season, next_label, seed)
    generated = generate_future_schedule(root, next_label, next_start)
    save.setdefault("season_schedules", {})[next_label] = generated
    save["meta"]["season"] = next_label
    save["meta"]["season_index"] = int(save["meta"].get("season_index") or len(save.get("season_history", []))) + 1
    save["meta"]["season_start_year"] = next_start
    save["state"] = {
        "current_date": f"{next_start}-10-01",
        "phase": "preseason",
        "legal_actions": legal_actions_for_date(f"{next_start}-10-01"),
    }
    save["schedule_state"] = {"simulated_game_ids": []}
    save["team_records"] = initial_team_records(canonical)
    # The final write archives these rows with the new manifest revision. Keep
    # them available until that commit, while clearing the new season's live
    # logs so dashboard and simulation calculations start from an empty season.
    pending_history = save.setdefault("_history_to_archive", {})
    for kind in ("game_results", "team_game_logs", "player_game_logs"):
        pending_history.setdefault(kind, []).extend(save.get(kind, []))
    save["team_game_logs"] = []
    save["player_game_logs"] = []
    save["player_season_stats"] = {}
    save["game_results"] = []
    save["playoff_state"] = {}
    save["pending_ai_actions"] = []
    save["pending_trade_proposals"] = []
    save["user_trade_offers"] = []
    save["pending_contract_negotiations"] = []
    save["pending_draft_selections"] = []
    save["lifecycle_state"]["health_game_ids"] = []
    save["free_agency_state"] = {}
    clean_free_agency_state(save, next_label)
    refresh_health_for_new_season(save, f"{next_start}-10-01")
    age_staff_contracts(save, canonical, seed=seed)
    advance_lifecycle_to(canonical, save, f"{next_start}-10-01", seed, root)
    save["applied_development_months"] = [m for m in save.get("applied_development_months", []) if m >= f"{next_start}-10"]
    refresh_roster_cutdowns(canonical, save)
    save["pending_offseason_review"] = {
        "season": current_season,
        "generated_date": f"{next_start}-10-01",
        "review_id": review.get("id") if review else None,
        "retirement_report_id": (save.get("retirement_reports") or [{}])[-1].get("id"),
    }
    add_news(save, "season_rollover", f"{next_label} season is ready for training camp.", date_value=f"{next_start}-10-01")
    ensure_preseason_outlook_safely(canonical, save, save_path)
    write_save(save_path, save)
    return {
        "status": "rolled_over",
        "from_season": current_season,
        "to_season": next_label,
        "current_date": save["state"]["current_date"],
        "generated_game_count": len(generated["games"]),
        "offseason_changes": offseason_changes,
        "save": str(save_path),
    }


def advance_through_current_season(root: str | Path, canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, process_ai: bool = True) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    season = save.get("meta", {}).get("season") or CANONICAL_SEASON
    start = season_start_year(season)
    dates = [f"{start}-10-21", trade_deadline_date(start), f"{start + 1}-02-06", f"{start + 1}-04-12"]
    steps = []
    for target in dates:
        if target > (load_save(save_path).get("state", {}).get("current_date") or ""):
            steps.append(advance_save(root, canonical, save_path, to_date=target, seed=seed))
            if process_ai:
                steps.append(process_ai_actions(canonical, save_path, seed=seed, execute=True, limit=5))
    return {"status": "advanced_regular_season", "season": season, "steps": steps, "save": str(save_path)}


def quick_sim_current_season(root: str | Path, canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, rollover: bool = False) -> dict[str, Any]:
    canonical = to_plain(canonical)
    regular = advance_through_current_season(root, canonical, save_path, seed=seed, process_ai=True)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    season = save.get("meta", {}).get("season") or CANONICAL_SEASON
    end_year = season_end_year(season)
    playoff_setup = start_playoffs(canonical, save_path, seed=seed)
    playoff_rounds = []
    for _ in range(4):
        result = simulate_playoff_round(canonical, save_path, seed=seed)
        playoff_rounds.append(result)
        state = result.get("playoff_state", {})
        if state.get("status") == "completed":
            break
    lottery = run_draft_lottery(canonical, save_path, year=str(end_year), seed=seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    draft_result = ensure_draft_processed(canonical, save, str(end_year), seed)
    write_save(save_path, save)
    offseason_steps = []
    offseason_steps.append(advance_save(root, canonical, save_path, to_date=f"{end_year}-06-27", seed=seed))
    re_signing_save = ensure_league_save_defaults(load_save(save_path), canonical)
    re_signing_save.setdefault("free_agency_state", {})["re_signing_status"] = "completed"
    for right in re_signing_save.get("re_signing_rights", []):
        if right.get("status") == "exclusive_review_window":
            right["status"] = "entered_open_market"
    write_save(save_path, re_signing_save)
    offseason_steps.append(advance_save(root, canonical, save_path, to_date=f"{end_year}-07-01", seed=seed))
    offseason_steps.append(process_ai_actions(canonical, save_path, seed=seed, execute=True, limit=5))
    rollover_result = complete_offseason_and_rollover(root, canonical, save_path, seed=seed) if rollover else None
    return {
        "status": "quick_sim_complete",
        "season": season,
        "regular_season": regular,
        "playoff_setup": playoff_setup,
        "playoff_rounds": playoff_rounds,
        "draft_lottery": lottery,
        "draft_result": draft_result,
        "offseason_steps": offseason_steps,
        "rollover": rollover_result,
        "save": str(save_path),
    }


DECLINE_WATCH_MIN_AGE = 27.0


def decline_watch_value(active: dict[str, Any], player: dict[str, Any], development_upside: Any) -> dict[str, float] | None:
    """Expected change of the hidden ratings over the next 12 months (if healthy) for veterans whose growth runway
    is used up: average per rating, and split into athletic vs skill ratings. None when not declining."""
    age = maybe_float(player.get("display_age", player.get("age")))
    if age is None or age < DECLINE_WATCH_MIN_AGE or float(development_upside or 0.0) > 0.0:
        return None
    from .development_outlook import decline_summary, expected_rating_changes
    try:
        summary = decline_summary(expected_rating_changes(active, player, 12, seed=int(active.get("meta", {}).get("seed") or 1)))
    except (KeyError, TypeError, ValueError):
        return None
    return summary if summary and summary["per_year"] <= -0.1 else None


def team_dashboard(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    team_query: str,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
    persist_repairs: bool = True,
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    should_write = bool(prune_rotation_recommendations(save, canonical)) if persist_repairs else False
    if persist_repairs:
        previous_rotation_overrides = deepcopy(save.get("rotation_overrides") or {})
        previous_rotation_locks = deepcopy(save.get("rotation_locked_player_ids") or {})
        normalize_user_rotation_for_injuries(save, canonical)
        should_write = should_write or previous_rotation_overrides != (save.get("rotation_overrides") or {})
        should_write = should_write or previous_rotation_locks != (save.get("rotation_locked_player_ids") or {})
    team = resolve_team(canonical, team_query)
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    # Dashboard snapshots pass an already enriched active universe, but direct
    # dashboard refreshes (including rotation edits) start from canonical_with_save,
    # which intentionally drops derived transaction projections. Rebuild those
    # projections before reading roster valuation fields so upside and health
    # meters don't silently fall back to zero after a dashboard mutation.
    from .transactions import with_transaction_context

    active = with_transaction_context(active)
    rotation_projection = team_rotation_projection(active, save, team["id"], integer=True)
    automatic_save = dict(save)
    automatic_overrides = dict(save.get("rotation_overrides") or {})
    automatic_overrides.pop(team["id"], None)
    automatic_save["rotation_overrides"] = automatic_overrides
    automatic_locks = dict(save.get("rotation_locked_player_ids") or {})
    automatic_locks.pop(team["id"], None)
    automatic_save["rotation_locked_player_ids"] = automatic_locks
    automatic_rotation_projection = team_rotation_projection(active, automatic_save, team["id"], integer=True)
    lineup_before = json.dumps(save.setdefault("starting_lineups", {}).get(team["id"], {}), sort_keys=True)
    starting_slots = starting_lineup_slots(active, save, team["id"], persist=persist_repairs)
    lineup_after = json.dumps(save.setdefault("starting_lineups", {}).get(team["id"], {}), sort_keys=True)
    should_write = should_write or lineup_before != lineup_after
    slot_by_player = {player_id: int(slot) for slot, player_id in starting_slots.items()}
    roster = sorted(
        [player for player in active.get("players", []) if player["team_id"] == team["id"]],
        key=lambda player: (
            0 if player.get("id") in slot_by_player else 1,
            slot_by_player.get(player.get("id"), 99),
            -float(rotation_projection.get(player["id"], 0.0)),
            player.get("name", ""),
        ),
    )
    if should_write and prepared_save is None:
        write_save(save_path, save)
    record = save.get("team_records", {}).get(team["id"], empty_team_record(team))
    logs = [log for log in save.get("team_game_logs", []) if log.get("team_id") == team["id"]]
    health = [
        state for state in save.get("health_states", []) if next((player for player in active.get("players", []) if player["id"] == state["player_id"] and player["team_id"] == team["id"]), None)
    ]
    phase = save.get("state", {}).get("phase")
    use_playoff_stats = phase in {"play_in", "playoffs"}
    season_stats = save.get("playoff_player_stats", {}) if use_playoff_stats else save.get("player_season_stats", {})
    stats_context = {
        "label": "Postseason (play-in + playoffs)" if use_playoff_stats else "Regular season",
        "source": "playoff_player_stats" if use_playoff_stats else "player_season_stats",
    }
    health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
    if use_playoff_stats:
        team_games = max(
            [int(totals.get("games") or 0) for totals in season_stats.values() if totals.get("team_id") == team["id"]]
            or [0]
        )
    else:
        team_games = int(record.get("wins", 0)) + int(record.get("losses", 0))
    recommendations = save.get("rotation_recommendations") or {}
    rotation_override = (save.get("rotation_overrides") or {}).get(team["id"], {})
    from .contract_ai import extension_contract_window

    contracts_by_player = {
        contract.get("player_id"): contract
        for contract in active.get("contracts", [])
        if contract.get("player_id")
    }
    current_date = str(save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
    current_legal_actions = save_legal_actions_for_date(save, current_date)
    extension_window_open = "extensions" in set(current_legal_actions)
    extension_eligible_player_ids = {
        player["id"]
        for player in roster
        if extension_window_open
        and (contract := contracts_by_player.get(player["id"]))
        and extension_contract_window(contract)["eligible"]
    }
    asset_value_by_player = {
        str(item.get("player_id")): item
        for item in active.get("player_asset_valuations", [])
        if item.get("player_id")
    }

    def roster_true_shooting(player_id: str) -> float:
        totals = season_stats.get(player_id, {})
        attempts = float(totals.get("fga") or 0.0) + 0.44 * float(totals.get("fta") or 0.0)
        return round(float(totals.get("points") or 0.0) / (2.0 * attempts) * 100.0, 1) if attempts > 0 else 0.0

    identity_metrics = team_identity_report(active, save)
    active_season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    active_start_year = season_start_year(active_season)
    cap_by_year = {
        season_label_from_start(active_start_year + offset): team_cap_summary(
            active,
            save,
            team["id"],
            season=season_label_from_start(active_start_year + offset),
        )
        for offset in range(6)
    }
    team_staff_slots = sorted(
        [slot for slot in save.get("staff_slots", []) if slot.get("team_id") == team["id"]],
        key=lambda item: item.get("slot") or "",
    )
    staff_budget_max = staff_budget_for_team(canonical, team["id"])
    staff_budget_spend = sum(staff_budget_salary(slot) for slot in team_staff_slots)
    return {
        "team": team,
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "legal_actions": current_legal_actions,
        "extension_window_open": extension_window_open,
        "record": record,
        "rotation": [
            {
                "id": player["id"],
                "name": player["name"],
                "headshot_url": player.get("headshot_url"),
                "position": player.get("position"),
                "age": player.get("display_age", player.get("age")),
                "height": player.get("height"),
                "height_inches": player.get("height_inches"),
                "minutes_projection": float(rotation_projection.get(player["id"], display_minutes_projection(player))),
                "coach_minutes_projection": float(rotation_projection.get(player["id"], display_minutes_projection(player))),
                "automatic_minutes_projection": float(automatic_rotation_projection.get(player["id"], 0.0)),
                "rotation_target_minutes": (
                    0.0
                    if player_unavailable_for_rotation(health_by_player.get(player["id"]))
                    else float(rotation_projection.get(player["id"], display_minutes_projection(player)))
                ),
                "rotation_user_set": (
                    not player_unavailable_for_rotation(health_by_player.get(player["id"]))
                    and player["id"] in save.get("rotation_locked_player_ids", {}).get(team["id"], list(rotation_override))
                ),
                # The minutes target a player the GM is resting returns to (None: the coach's automatic minutes).
                "resting_minutes_target": (
                    rotation_override.get(player["id"]) or None
                    if (health_by_player.get(player["id"]) or {}).get("user_rest") else None
                ),
                "is_starting_five": player["id"] in slot_by_player,
                "starting_slot": slot_by_player.get(player["id"]),
                "season_minutes_per_game": per_game_stat(season_stats.get(player["id"], {}), "minutes"),
                "display_mpg": (
                    per_game_stat(season_stats.get(player["id"], {}), "minutes")
                    if use_playoff_stats or int(season_stats.get(player["id"], {}).get("games") or 0) > 0
                    else float(rotation_projection.get(player["id"], display_minutes_projection(player)))
                ),
                "rotation_priority": player.get("rotation_priority"),
                "games": season_stats.get(player["id"], {}).get("games", 0),
                "team_games": team_games,
                "gp_display": f"{season_stats.get(player['id'], {}).get('games', 0)}/{team_games}",
                "points_per_game": per_game_stat(season_stats.get(player["id"], {}), "points"),
                "rebounds_per_game": per_game_stat(season_stats.get(player["id"], {}), "rebounds"),
                "assists_per_game": per_game_stat(season_stats.get(player["id"], {}), "assists"),
                "steals_per_game": per_game_stat(season_stats.get(player["id"], {}), "steals"),
                "blocks_per_game": per_game_stat(season_stats.get(player["id"], {}), "blocks"),
                "turnovers_per_game": per_game_stat(season_stats.get(player["id"], {}), "turnovers"),
                "fg_pct": percentage_stat(season_stats.get(player["id"], {}), "fgm", "fga"),
                "fg3_pct": percentage_stat(season_stats.get(player["id"], {}), "fg3m", "fg3a"),
                "fga_per_game": per_game_stat(season_stats.get(player["id"], {}), "fga"),
                "fg3a_per_game": per_game_stat(season_stats.get(player["id"], {}), "fg3a"),
                "fta_per_game": per_game_stat(season_stats.get(player["id"], {}), "fta"),
                "ft_pct": percentage_stat(season_stats.get(player["id"], {}), "ftm", "fta"),
                "ts_pct": roster_true_shooting(player["id"]),
                "health_risk": round(float((asset_value_by_player.get(player["id"]) or {}).get("health_risk") or 0.0), 1),
                "upside_remaining": round(max(0.0, min(5.0, float((asset_value_by_player.get(player["id"]) or {}).get("development_upside") or 0.0) / 22.0 * 5.0)), 1),
                "decline_watch": decline_watch_value(active, player, (asset_value_by_player.get(player["id"]) or {}).get("development_upside")),
                "trade_value": round(float((asset_value_by_player.get(player["id"]) or {}).get("player_value") or 0.0), 1),
                "health": player_health_label(health_by_player.get(player["id"]), save.get("state", {}).get("current_date")),
                # Most regular-season games he can still reach (the 65-game award rule), after any rest the GM has set.
                "award_games_max": (None if use_playoff_stats else award_games_max(
                    int(season_stats.get(player["id"], {}).get("games") or 0), team_games, health_by_player.get(player["id"]))),
                "attributes": player_attribute_summary(active, player["id"]),
                "display_ratings": player_display_attribute_summary(active, player["id"]),
                "salary_by_year": player_salary_table(active, player["id"]),
                "extension_eligible": player["id"] in extension_eligible_player_ids,
                "minutes_recommendation": recommendations.get(player["id"]),
            }
            for player in roster
        ],
        "last_games": sorted(logs, key=lambda item: item["date"], reverse=True)[:5],
        "next_games": next_team_games(root, canonical, save, team["id"], limit=5),
        "health_summary": health_summary(health),
        "stats_context": stats_context,
        "starting_five": starting_five_rows(active, save, team["id"], persist=persist_repairs),
        "staff_slots": team_staff_slots,
        "staff_action_permissions": staff_action_permissions(save, team["id"]),
        "staff_budget": {
            "annual_spend_millions": round(staff_budget_spend, 2),
            "annual_budget_millions": round(staff_budget_max, 2),
            "available_millions": round(staff_budget_max - staff_budget_spend, 2),
        },
        "cap_posture": next((state.get("salary_posture") for state in canonical.get("team_strategic_states", []) if state["team_id"] == team["id"]), "unknown"),
        "cap_summary": team_cap_summary(active, save, team["id"], season=save_active_contract_season(save)),
        "cap_by_year": cap_by_year,
        "team_identity": identity_metrics.get(team["id"], {}),
        "spatial_profile": team_spatial_profile(
            active,
            team["id"],
            {player_id: float(value) for player_id, value in rotation_projection.items()},
            health_by_player,
            include_chart=True,
        ),
        "rating_tertiles": display_rating_tertiles(active),
        "pending_counts": pending_counts(save),
    }


def team_identity_report(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    players_by_team: dict[str, list[dict[str, Any]]] = {team_id: [] for team_id in teams}
    for player in canonical.get("players", []):
        if player.get("team_id") in players_by_team:
            players_by_team[player["team_id"]].append(player)
    raw: dict[str, dict[str, float]] = {}
    for team_id, roster in players_by_team.items():
        projection = team_rotation_projection(canonical, save, team_id, integer=False)
        rows: list[tuple[dict[str, Any], dict[str, float], float]] = []
        for player in roster:
            minutes = float(projection.get(player["id"], display_minutes_projection(player)))
            if minutes <= 0:
                continue
            rows.append((player, player_attribute_summary(canonical, player["id"]), minutes))
        rows.sort(key=lambda item: item[2], reverse=True)
        total_minutes = sum(weight for _, _, weight in rows) or 1.0

        def weighted(key: str, default: float = 50.0, subset: list[tuple[dict[str, Any], dict[str, float], float]] | None = None) -> float:
            pool = subset if subset is not None else rows
            denominator = sum(weight for _, _, weight in pool) or 1.0
            return sum(float(attrs.get(key, default) or default) * weight for _, attrs, weight in pool) / denominator

        top_weight = rows[:8]
        depth_pool = rows[5:12] or rows[5:] or rows
        weighted_age = sum(float(player.get("age") or 26.0) * weight for player, _, weight in rows) / total_minutes
        old_minutes_share = sum(weight for player, _, weight in rows if float(player.get("age") or 0.0) >= 34.0) / total_minutes
        very_old_minutes_share = sum(weight for player, _, weight in rows if float(player.get("age") or 0.0) >= 37.0) / total_minutes
        age_drag = old_minutes_share * 7.0 + very_old_minutes_share * 8.0 + max(0.0, weighted_age - 29.0) * 1.05
        top_rotation = rows[:9] or rows
        bottom_defense = sorted(float(attrs.get("defense", 50.0) or 50.0) for _, attrs, _ in top_rotation)[:3]
        bottom_athleticism = sorted(float(attrs.get("athleticism", 50.0) or 50.0) for _, attrs, _ in top_rotation)[:3]
        weak_link_drag = max(0.0, 57.0 - (sum(bottom_defense) / max(1, len(bottom_defense)))) * 0.16
        athletic_weak_link_drag = max(0.0, 58.0 - (sum(bottom_athleticism) / max(1, len(bottom_athleticism)))) * 0.14
        offense = weighted("shooting") * 0.28 + weighted("creation") * 0.30 + weighted("passing") * 0.18 + weighted("rim_pressure") * 0.14 + weighted("iq") * 0.10
        if any('offense' in attrs for _, attrs, _ in rows):
            offense = weighted('offense')
        defense = weighted("defense") * 0.46 + weighted("def_effort") * 0.18 + weighted("screen_nav") * 0.12 + weighted("rim_deterrence") * 0.16 + weighted("portability") * 0.08
        creation = weighted("creation") * 0.48 + weighted("handle") * 0.22 + weighted("passing") * 0.20 + weighted("versatility") * 0.10
        # Minutes-weighted engine spacing, the same aggregation the sim's team features use (rule 4, 2026-11-19).
        spacing = weighted("spacing")
        depth = weighted("overall", subset=depth_pool) * 0.82 + min(14.0, len([row for row in rows if row[2] >= 8.0])) * 1.2
        young_rows = [
            (player, attrs, weight)
            for player, attrs, weight in rows
            if float(player.get("age") or 99.0) <= 24.0
        ]
        young_minutes_share = sum(weight for _, _, weight in young_rows) / total_minutes
        young_quality = (
            sum(
                (
                    float(attrs.get("overall", 50.0) or 50.0)
                    + max(0.0, float(player.get("potential") or attrs.get("overall", 50.0) or 50.0) - float(attrs.get("overall", 50.0) or 50.0)) * 0.65
                )
                * weight
                for player, attrs, weight in young_rows
            )
            / max(1.0, sum(weight for _, _, weight in young_rows))
            if young_rows
            else 42.0
        )
        timeline = clamp(
            68.0
            - max(0.0, weighted_age - 26.0) * 5.5
            + young_minutes_share * 18.0
            + max(0.0, young_quality - 55.0) * 0.62
            - max(0.0, 48.0 - young_quality) * 0.28,
            1,
            99,
        )
        offense = offense - age_drag * 0.65
        defense = defense - age_drag * 1.15 - weak_link_drag
        creation = creation - age_drag * 0.22
        spacing = spacing - old_minutes_share * 1.2 - age_drag * 0.52
        athleticism = weighted("athleticism") - age_drag * 1.55 - athletic_weak_link_drag
        disruption = weighted("def_effort") * 0.38 + weighted("screen_nav") * 0.24 + weighted("defense") * 0.24 + weighted("portability") * 0.14 - age_drag * 1.45 - weak_link_drag * 0.5
        rim_pressure = weighted("rim_pressure") - age_drag * 0.16
        overall = weighted("overall", subset=top_weight) * 0.72 + depth * 0.28 - age_drag * 0.78 - weak_link_drag * 0.35
        raw[team_id] = {
            "overall": round(clamp(overall, 1, 99), 1),
            "offense": round(clamp(offense, 1, 99), 1),
            "defense": round(clamp(defense, 1, 99), 1),
            "spacing": round(clamp(spacing, 1, 99), 1),
            "creation": round(clamp(creation, 1, 99), 1),
            "rim_pressure": round(clamp(rim_pressure, 1, 99), 1),
            "rebounding": round(clamp(weighted("oreb") * 0.58 + weighted("rim_deterrence") * 0.16 + athleticism * 0.26, 1, 99), 1),
            "athleticism": round(clamp(athleticism, 1, 99), 1),
            "defensive_disruption": round(clamp(disruption, 1, 99), 1),
            "rim_protection": round(max(1.0, weighted("rim_deterrence")), 1),
            "depth": round(clamp(depth, 1, 99), 1),
            "age_timeline": round(timeline, 1),
            "average_age": round(weighted_age, 1),
        }
    ranks: dict[str, dict[str, int]] = {team_id: {} for team_id in teams}
    metric_keys = [key for key in next(iter(raw.values()), {}).keys() if key != "average_age"]
    for key in metric_keys:
        ordered = sorted(raw, key=lambda team_id: (raw[team_id].get(key, 0.0), teams.get(team_id, {}).get("abbrev", "")), reverse=True)
        for rank, team_id in enumerate(ordered, start=1):
            ranks[team_id][key] = rank
    return {
        team_id: {
            "metrics": raw.get(team_id, {}),
            "ranks": ranks.get(team_id, {}),
            "league_team_count": len(teams),
        }
        for team_id in teams
    }


def health_availability_weight(state: dict[str, Any] | None) -> float:
    if not state:
        return 1.0
    status = str(state.get("availability_status") or "active").lower()
    if status in {"active", "healthy"}:
        return 1.0
    days_left = float(state.get("days_left") or state.get("expected_days_remaining") or 0.0)
    if days_left >= 45:
        return 0.18
    if days_left >= 14:
        return 0.35
    return 0.72


def phase_for_date(value: str) -> str:
    try:
        month_day = value[5:]
    except IndexError:
        return "offseason"
    if "10-01" <= month_day < "10-21":
        return "preseason"
    if month_day >= "10-21" or month_day <= "02-05":
        return "regular_season"
    if "02-06" <= month_day <= "04-12":
        return "regular_season"
    if "04-13" <= month_day <= "04-17":
        return "play_in"
    if "04-18" <= month_day <= "06-21":
        return "playoffs"
    if "06-22" <= month_day <= "06-24":
        return "draft_lottery"
    if "06-25" <= month_day <= "06-26":
        return "draft"
    if "06-27" <= month_day <= "06-30":
        return "re_signing"
    if "07-01" <= month_day <= "07-15":
        return "free_agency"
    if month_day >= "09-01":
        return "training_camp"
    return "offseason"


def legal_actions_for_phase(phase: str) -> list[str]:
    actions = {
        "preseason": ["trades", "extensions", "staff_changes", "press_conferences", "social_media", "advance"],
        "regular_season": ["trades", "staff_changes", "press_conferences", "social_media", "advance"],
        "play_in": ["staff_changes", "press_conferences", "social_media", "advance"],
        "playoffs": ["staff_changes", "press_conferences", "social_media", "advance"],
        "draft_lottery": ["draft_lottery", "extensions", "staff_changes", "press_conferences", "social_media", "advance"],
        "draft": ["draft_picks", "draft_trades", "trades", "extensions", "staff_changes", "press_conferences", "social_media", "advance"],
        "re_signing": ["free_agent_signings", "trades", "staff_changes", "press_conferences", "social_media", "advance"],
        "free_agency": ["free_agent_signings", "trades", "staff_changes", "press_conferences", "social_media", "advance"],
        # Trades are legal in September (real teams trade during training camp; TRADE-VOLUME-2).
        "training_camp": ["trades", "staff_changes", "press_conferences", "social_media", "advance"],
        "offseason": ["trades", "extensions", "staff_changes", "press_conferences", "social_media", "advance"],
    }
    return actions.get(phase, ["advance"])


def ensure_game_settings(save: dict[str, Any]) -> dict[str, Any]:
    settings = save.setdefault("game_settings", {})
    settings.setdefault("press_conferences_enabled", False)
    # Off by default: the GM sets his own minutes, so his coach only suggests rest (the blue "zZ") unless allowed.
    settings.setdefault("coach_rests_players", False)
    return settings


def coach_rest_team_ids(save: dict[str, Any]) -> list[str]:
    """Human-run teams whose GM lets the coach rest players by the AI coaches' rule (game setting)."""
    if not bool((save.get("game_settings") or {}).get("coach_rests_players")):
        return []
    return sorted(human_controlled_team_ids(save))


def press_conferences_enabled(save: dict[str, Any]) -> bool:
    return bool(ensure_game_settings(save).get("press_conferences_enabled"))


def save_legal_actions_for_date(save: dict[str, Any], value: str) -> list[str]:
    actions = legal_actions_for_date(value)
    if not press_conferences_enabled(save):
        actions = [action for action in actions if action != "press_conferences"]
    return actions


def legal_actions_for_date(value: str) -> list[str]:
    phase = phase_for_date(value)
    actions = list(legal_actions_for_phase(phase))
    start_year = season_start_year_from_date(value)
    if phase in {"preseason", "regular_season"}:
        if value <= extension_deadline_date(start_year) and "extensions" not in actions:
            actions.insert(1 if "trades" in actions else 0, "extensions")
        if value > extension_deadline_date(start_year) and "extensions" in actions:
            actions.remove("extensions")
    if phase in {"preseason", "regular_season"} and "trades" in actions and value > trade_deadline_date(start_year):
        actions.remove("trades")
    return actions


def normalize_ai_difficulty(value: Any) -> str:
    value = str(value or "normal").strip().lower()
    return value if value in AI_DIFFICULTIES else "normal"


def season_start_year_from_date(value: str) -> int:
    parsed = parse_date(value)
    return parsed.year if parsed.month >= 7 else parsed.year - 1


def extension_deadline_date(start_year: int) -> str:
    return f"{start_year + 1}-01-15"


def trade_deadline_date(start_year: int) -> str:
    return f"{start_year + 1}-02-05"


def load_schedule(root: str | Path) -> list[dict[str, Any]]:
    with (Path(root) / SCHEDULE_FILE).open("r", encoding="utf-8") as handle:
        return json.load(handle).get("games", [])


def schedule_for_save(root: str | Path, save: dict[str, Any]) -> list[dict[str, Any]]:
    season = save.get("meta", {}).get("season") or CANONICAL_SEASON
    generated = (save.get("season_schedules") or {}).get(season, {}).get("games")
    return list(generated or load_schedule(root))


def scheduled_games_between(root: str | Path, save: dict[str, Any], current: str, target: str) -> list[dict[str, Any]]:
    games = [
        game
        for game in schedule_for_save(root, save)
        if current < game.get("gameDate", "") <= target and game.get("phase") == "regular" and game.get("externalGameId")
    ]
    return sorted(games, key=lambda item: (item["gameDate"], str(item["externalGameId"])))


def next_event_date(root: str | Path, canonical: dict[str, Any], save: dict[str, Any]) -> str | None:
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    if save.get("state", {}).get("phase") in {"play_in", "playoffs"}:
        initialize_postseason(canonical, save, "", int(save.get("meta", {}).get("seed") or 1))
        postseason_date = next_postseason_date(save)
        if postseason_date:
            return postseason_date
    for game in schedule_for_save(root, save):
        if game.get("gameDate", "") > current and str(game.get("externalGameId")) not in set(save.get("schedule_state", {}).get("simulated_game_ids", [])):
            return game.get("gameDate")
    end_year = season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    for date_value in [f"{end_year}-04-13", f"{end_year}-06-22", f"{end_year}-06-25", f"{end_year}-06-27", f"{end_year}-07-01", f"{end_year}-09-01"]:
        if date_value > current:
            return date_value
    return None


def draft_completed_for_year(save: dict[str, Any], year: str | int) -> bool:
    state = save.get("draft_state") or {}
    completed_year = state.get("completed_year") or state.get("year")
    return (str(completed_year or "") == str(year)
            and state.get("status") in {"completed", "skipped"})


def guard_required_phase_actions(save: dict[str, Any], current: str, target: str) -> None:
    end_year = season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    start_year = season_start_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    regular_start_gate = f"{start_year}-10-21"
    entry = str(save.get('meta', {}).get('gameplay_start_date') or '')
    if entry[:4] == str(start_year):
        regular_start_gate = next_date_str(entry, 1)
    playoff_gate = f"{end_year}-06-22"
    draft_gate = f"{end_year}-06-27"
    free_agency_gate = f"{end_year}-07-01"
    phase = save.get("state", {}).get("phase")
    if target > current and target >= regular_start_gate and phase in {"preseason", "regular_season"} and save.get("pending_roster_cutdowns"):
        team = save.get("pending_roster_cutdowns", [{}])[0]
        raise ValueError(
            f"{team.get('team_abbrev') or 'Your team'} has {team.get('current_count')} players. "
            f"Cut to {team.get('target_count') or ROSTER_SEASON_MAXIMUM} before opening night."
        )
    if current < playoff_gate <= target:
        state = save.get("playoff_state") or {}
        if phase in {"play_in", "playoffs"} and state.get("status") != "completed":
            raise ValueError("The playoffs are active. Use Sim to finish postseason games before advancing to the draft lottery.")
    if current < draft_gate <= target:
        pending = save.get("pending_draft_selections") or []
        if phase == "draft" and (not draft_completed_for_year(save, end_year) or pending):
            raise ValueError("The draft is active. Finish or sim the draft before advancing to re-signing.")
        if target > draft_gate:
            raise ValueError("Advance into the exclusive re-signing window before opening free agency.")
    if current < free_agency_gate <= target:
        re_signing_state = save.get("free_agency_state") or {}
        if phase == "re_signing" and re_signing_state.get("re_signing_status") != "completed":
            raise ValueError("Resolve or leave the exclusive re-signing window before opening free agency.")


def record_game_result(save: dict[str, Any], canonical: dict[str, Any], game: dict[str, Any], result: dict[str, Any]) -> None:
    result = filter_result_to_active_game_rosters(save, canonical, result)
    game_id = result["game_id"]
    simulated = save.setdefault("schedule_state", {}).setdefault("simulated_game_ids", [])
    if game_id in simulated:
        return
    save.setdefault("game_results", []).append(result)
    simulated.append(game_id)
    simulated.sort()
    team_lines = {line["team_id"]: line for line in result.get("team_lines", [])}
    home_id = result["home_team_id"]
    away_id = result["away_team_id"]
    home_points = int(result["home_score"])
    away_points = int(result["away_score"])
    update_team_record(save, canonical, game, home_id, away_id, home_points, away_points, is_home=True)
    update_team_record(save, canonical, game, away_id, home_id, away_points, home_points, is_home=False)
    top_minutes_ids = team_top_minutes_ids(result.get("player_lines", []))
    for line in result.get("player_lines", []):
        update_player_stats(save, line, game, top_minutes_ids)
        team_points = home_points if line.get("team_id") == home_id else away_points
        opp_points = away_points if line.get("team_id") == home_id else home_points
        update_player_game_morale(save, line, team_points > opp_points, abs(team_points - opp_points))
    for team_id, line in team_lines.items():
        opponent_id = away_id if team_id == home_id else home_id
        points = home_points if team_id == home_id else away_points
        opp_points = away_points if team_id == home_id else home_points
        save.setdefault("team_game_logs", []).append(
            {
                "id": stable_id("team_game_log", game_id, team_id),
                "game_id": game_id,
                "date": game.get("gameDate"),
                "team_id": team_id,
                "team_abbrev": line.get("team_abbrev"),
                "opponent_team_id": opponent_id,
                "is_home": team_id == home_id,
                "points": points,
                "opponent_points": opp_points,
                "result": "W" if points > opp_points else "L",
                "possessions": round(float(line.get("possessions") or result.get("possessions") or 0.0), 1),
                "off_rating": round(float(line.get("off_rating") or (points / max(1.0, float(result.get("possessions") or 100.0)) * 100.0)), 2),
                "turnovers": int(line.get("turnovers") or 0),
                "rebounds": int(line.get("rebounds") or 0),
                "offensive_rebounds": int(line.get("offensive_rebounds") or 0),
                "defensive_rebounds": int(line.get("defensive_rebounds") or 0),
                "fga": int(line.get("fga") or 0),
                "fgm": int(line.get("fgm") or 0),
                "fg3m": int(line.get("fg3m") or 0),
                "fta": int(line.get("fta") or 0),
            }
        )
    save.setdefault("news_items", []).append(
        {
            "id": stable_id("news", "game", game_id),
            "date": game.get("gameDate"),
            "kind": "game_result",
            "headline": f"{team_lines.get(away_id, {}).get('team_abbrev', 'AWAY')} {away_points}, {team_lines.get(home_id, {}).get('team_abbrev', 'HOME')} {home_points}",
            "status": "unread",
        }
    )
    update_game_morale(save, home_id, away_id, home_points, away_points)
    add_game_high_social(save, result)
    emit_progress(save, "game", game=result)


def filter_result_to_active_game_rosters(save: dict[str, Any], canonical: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    lines = result.get("player_lines") or []
    if not lines:
        return result
    home_id = result.get("home_team_id")
    away_id = result.get("away_team_id")
    game_teams = {home_id, away_id}
    free_agents = set(save.get("free_agent_player_ids") or [])
    retired = set(save.get("retired_player_ids") or [])
    roster_overrides = save.get("roster_overrides") or {}
    active_team_by_player = {
        player.get("id"): player.get("team_id")
        for player in [*canonical.get("players", []), *save.get("generated_players", [])]
        if player.get("id")
        and player.get("id") not in free_agents
        and player.get("id") not in retired
        and (roster_overrides.get(player.get("id"), player.get("team_id")) in game_teams)
    }
    for player_id, team_id in roster_overrides.items():
        if team_id in game_teams and player_id not in free_agents and player_id not in retired:
            active_team_by_player[player_id] = team_id
    filtered = [
        line for line in lines
        if line.get("player_id")
        and active_team_by_player.get(line.get("player_id")) == line.get("team_id")
    ]
    if len(filtered) == len(lines):
        return result
    return {
        **result,
        "player_lines": filtered,
        "notes": " ".join(
            part for part in [str(result.get("notes") or "").strip(), "Filtered inactive/free-agent player lines before saving stats."]
            if part
        ),
    }


def add_game_high_social(save: dict[str, Any], result: dict[str, Any]) -> None:
    lines = result.get("player_lines") or []
    if not lines:
        return
    checks = [
        ("points", 49, "points"),
        ("rebounds", 20, "rebounds"),
        ("assists", 20, "assists"),
        ("steals", 6, "steals"),
        ("blocks", 6, "blocks"),
    ]
    for stat, threshold, label in checks:
        leader = max(lines, key=lambda item: float(item.get(stat) or 0), default={})
        value = float(leader.get(stat) or 0)
        if value > threshold:
            add_league_event(
                save,
                "major_stat_line",
                f"{leader.get('player_name')} recorded {int(value)} {label} for {leader.get('team_abbrev')}.",
                date_value=save.get("state", {}).get("current_date"),
                team_ids=[leader.get("team_id")] if leader.get("team_id") else [],
                player_ids=[leader.get("player_id")] if leader.get("player_id") else [],
                importance=0.72,
                details={"stat": stat, "value": value, "game_id": result.get("game_id"), "threshold": threshold},
            )
            add_social(
                save,
                "player_high",
                f"{leader.get('player_name')} posted a season-high watch line: {int(value)} {label} for {leader.get('team_abbrev')}.",
                team_ids=[leader.get("team_id")] if leader.get("team_id") else [],
            )
            return


def update_team_record(save: dict[str, Any], canonical: dict[str, Any], game: dict[str, Any], team_id: str, opponent_id: str, points: int, opp_points: int, is_home: bool) -> None:
    team = team_by_id(canonical, team_id)
    record = save.setdefault("team_records", {}).setdefault(team_id, empty_team_record(team))
    if points > opp_points:
        record["wins"] += 1
        record["home_wins" if is_home else "away_wins"] += 1
    else:
        record["losses"] += 1
        record["home_losses" if is_home else "away_losses"] += 1
    record["points_for"] = round(float(record.get("points_for", 0)) + points, 2)
    record["points_against"] = round(float(record.get("points_against", 0)) + opp_points, 2)
    record["last_game_id"] = str(game.get("externalGameId"))


def team_top_minutes_ids(player_lines: list[dict[str, Any]], count: int = 5) -> set[str]:
    """The five players with the most minutes for each team in one game. Box scores do not record who started, so
    the season awards treat a game outside a team's top five in minutes as a game off the bench."""
    by_team: dict[str, list[dict[str, Any]]] = {}
    for line in player_lines or []:
        if line.get("player_id") and float(line.get("minutes") or 0.0) > 0:
            by_team.setdefault(str(line.get("team_id") or ""), []).append(line)
    top: set[str] = set()
    for lines in by_team.values():
        ranked = sorted(lines, key=lambda row: (-float(row.get("minutes") or 0.0), -float(row.get("points") or 0.0), str(row.get("player_id"))))
        top.update(str(row["player_id"]) for row in ranked[:count])
    return top


def count_award_game(totals: dict[str, Any], line: dict[str, Any], top_minutes_ids: set[str] | None) -> None:
    """Season counters for the award rules: games of 20+ minutes and of 15-20 minutes (the league's 65-game rule
    counts both, the second kind at most twice), and games outside the team's top five in minutes (Sixth Man)."""
    minutes = float(line.get("minutes") or 0.0)
    if minutes >= 20.0:
        totals["games_20_min"] = int(totals.get("games_20_min") or 0) + 1
    elif minutes >= 15.0:
        totals["games_15_min"] = int(totals.get("games_15_min") or 0) + 1
    if top_minutes_ids is not None and minutes > 0:
        key = "games_top_minutes" if str(line.get("player_id")) in top_minutes_ids else "games_bench"
        totals[key] = int(totals.get(key) or 0) + 1


def update_player_stats(save: dict[str, Any], line: dict[str, Any], game: dict[str, Any], top_minutes_ids: set[str] | None = None) -> None:
    player_id = line.get("player_id")
    if not player_id:
        return
    game_id = str(game.get("externalGameId"))
    log_id = stable_id("player_game_log", game_id, player_id)
    logs = save.setdefault("player_game_logs", [])
    if log_id not in {item.get("id") for item in logs}:
        logs.append(
            {
                "id": log_id,
                "game_id": game_id,
                "date": game.get("gameDate"),
                **{key: line.get(key) for key in ["player_id", "player_name", "team_id", "team_abbrev", *STAT_FIELDS] if key in line},
            }
        )
    totals = save.setdefault("player_season_stats", {}).setdefault(
        player_id,
        {
            "player_id": player_id,
            "player_name": line.get("player_name"),
            "team_id": line.get("team_id"),
            "team_abbrev": line.get("team_abbrev"),
            "games": 0,
            "game_ids": [],
            **{field: 0.0 for field in STAT_FIELDS},
        },
    )
    played_ids = set(totals.setdefault("game_ids", []))
    totals["team_abbrevs"] = list(dict.fromkeys([
        *totals.get("team_abbrevs", []),
        *([totals["team_abbrev"]] if totals.get("team_abbrev") else []),
        *([line["team_abbrev"]] if line.get("team_abbrev") else []),
    ]))
    if game_id in played_ids:
        totals["team_id"] = line.get("team_id")
        totals["team_abbrev"] = line.get("team_abbrev")
        return
    totals["game_ids"].append(game_id)
    totals["game_ids"] = sorted(set(totals["game_ids"]))
    totals["games"] += 1
    totals["team_id"] = line.get("team_id")
    totals["team_abbrev"] = line.get("team_abbrev")
    for field in STAT_FIELDS:
        totals[field] = round(float(totals.get(field, 0.0)) + float(line.get(field) or 0.0), 2)
    count_award_game(totals, line, top_minutes_ids)


def morale_report(
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    team_query: str | None = None,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical if isinstance(canonical, dict) else to_plain(canonical)
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    if team_query:
        team = resolve_team(canonical, team_query)
        active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
        player_ids = {player["id"] for player in active.get("players", []) if player["team_id"] == team["id"]}
        return {
            "team": team,
            "team_morale": save.get("team_morale", {}).get(team["id"]),
            "fan_confidence": save.get("fan_confidence", {}).get(team["id"]),
            "owner_confidence": save.get("owner_confidence", {}).get(team["id"]),
            "players": sorted(
                [
                    {
                        "player": next((player for player in canonical.get("players", []) if player["id"] == player_id), {"id": player_id}),
                        "morale": morale,
                    }
                    for player_id, morale in save.get("player_morale", {}).items()
                    if player_id in player_ids
                ],
                key=lambda item: (float(item["morale"].get("overall", 50)), item["player"].get("name", "")),
            ),
        }
    return {
        "teams": sorted(
            [
                {
                    "team": team,
                    "team_morale": save.get("team_morale", {}).get(team["id"]),
                    "fan_confidence": save.get("fan_confidence", {}).get(team["id"]),
                    "owner_confidence": save.get("owner_confidence", {}).get(team["id"]),
                }
                for team in canonical.get("teams", [])
            ],
            key=lambda item: item["team"]["abbrev"],
        )
    }


def social_feed_view(
    canonical: dict[str, Any] | Any,
    save_path: str | Path,
    team_query: str | None = None,
    limit: int = 20,
    narrative_provider: NarrativeProvider | None = None,
) -> dict[str, Any]:
    canonical = to_plain(canonical)
    # Social is an explicitly historical view and narrative hydration can
    # update old rows, so use the compatibility loader only on this modal path.
    save = ensure_league_save_defaults(load_save(save_path, include_history=True), canonical)
    team_id = resolve_team(canonical, team_query)["id"] if team_query else None
    if (save.get("narrative_settings") or {}).get("enabled"):
        limit = min(int(limit), int((save.get("narrative_settings") or {}).get("max_posts_per_view") or 12))
    feed = [
        item for item in save.get("social_feed", [])
        if team_id is None or team_id in item.get("team_ids", []) or not item.get("team_ids")
    ]
    feed = sorted(feed, key=lambda item: (item.get("date", ""), item.get("id", "")), reverse=True)[:limit]
    feed, changed = hydrate_social_items(canonical_with_save(canonical, save), save, feed, team_id=team_id, provider=narrative_provider)
    if changed:
        write_save(save_path, save)
    return {"team_id": team_id, "item_count": len(feed), "items": feed}


def narrative_settings_view(save_path: str | Path, test_connection: bool = False) -> dict[str, Any]:
    save = load_save(save_path)
    ensure_narrative_state(save)
    provider = provider_from_settings(save["narrative_settings"]) if test_connection else None
    return narrative_status_payload(save, provider=provider)


def update_narrative_settings(
    save_path: str | Path,
    *,
    enabled: bool | None = None,
    provider: str | None = None,
    ollama_base_url: str | None = None,
    ollama_model: str | None = None,
    timeout_seconds: float | None = None,
    max_posts_per_view: int | None = None,
    reset_cache: bool = False,
    test_connection: bool = False,
) -> dict[str, Any]:
    save = load_save(save_path)
    ensure_narrative_state(save)
    settings = dict(save.get("narrative_settings") or {})
    previous_settings = normalize_narrative_settings(settings)
    if enabled is not None:
        settings["enabled"] = bool(enabled)
    if provider is not None:
        settings["provider"] = provider
    if ollama_base_url is not None:
        settings["ollama_base_url"] = ollama_base_url
    if ollama_model is not None:
        settings["ollama_model"] = ollama_model
    if timeout_seconds is not None:
        settings["timeout_seconds"] = timeout_seconds
    if max_posts_per_view is not None:
        settings["max_posts_per_view"] = max_posts_per_view
    save["narrative_settings"] = normalize_narrative_settings(settings)
    changed_generation_backend = any(
        previous_settings.get(key) != save["narrative_settings"].get(key)
        for key in ["provider", "ollama_base_url", "ollama_model", "max_tokens", "temperature"]
    )
    if reset_cache:
        reset_narrative_cache(save)
    elif changed_generation_backend:
        reset_narrative_cache(save)
    write_save(save_path, save)
    return narrative_settings_view(save_path, test_connection=test_connection)


def hold_press_conference(canonical: dict[str, Any] | Any, save_path: str | Path, team_query: str, topic: str, tone: str, seed: int = 1) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_team(canonical, team_query)
    if tone not in {"accountable", "optimistic", "deflect", "challenge"}:
        raise ValueError("Press tone must be accountable, optimistic, deflect, or challenge.")
    before = {
        "team_morale": float(save.get("team_morale", {}).get(team["id"], {}).get("overall", 55.0)),
        "fan_confidence": float(save.get("fan_confidence", {}).get(team["id"], 55.0)),
        "owner_confidence": float(save.get("owner_confidence", {}).get(team["id"], 56.0)),
    }
    impact = press_impact(topic, tone, seed)
    question = press_question(team["abbrev"], topic, tone, seed)
    answer = press_answer(team["abbrev"], topic, tone)
    apply_team_morale_delta(save, team["id"], impact["team_morale"])
    save.setdefault("fan_confidence", {})[team["id"]] = round(clamp(float(save.get("fan_confidence", {}).get(team["id"], 55.0)) + impact["fan_confidence"], 0, 100), 2)
    save.setdefault("owner_confidence", {})[team["id"]] = round(clamp(float(save.get("owner_confidence", {}).get(team["id"], 56.0)) + impact["owner_confidence"], 0, 100), 2)
    after = {
        "team_morale": float(save.get("team_morale", {}).get(team["id"], {}).get("overall", 55.0)),
        "fan_confidence": float(save.get("fan_confidence", {}).get(team["id"], 55.0)),
        "owner_confidence": float(save.get("owner_confidence", {}).get(team["id"], 56.0)),
    }
    record = {
        "id": stable_id("press", save.get("state", {}).get("current_date"), team["id"], topic, tone, seed),
        "date": save.get("state", {}).get("current_date"),
        "team_id": team["id"],
        "topic": topic,
        "tone": tone,
        "question": question,
        "answer": answer,
        "impact": impact,
        "confidence_metrics": {"before": before, "after": after},
        "notes": "Press conference V1. Tone changes team morale, fan confidence, owner confidence, and social framing in bounded ways.",
    }
    save.setdefault("press_conferences", []).append(record)
    add_news(save, "press_conference", f"{team['abbrev']} GM press conference: {topic} ({tone}).")
    add_social(save, "press_conference", social_reaction_text(team["abbrev"], topic, tone), team_ids=[team["id"]])
    write_save(save_path, save)
    return record


def record_lasting_injury_effect(save: dict[str, Any], event: dict[str, Any]) -> None:
    """Evidence-based permanent physical decline after a major injury (user decision 2026-11-18), stored as a development
    event so it flows through the same rating path as normal growth and aging. At most once per diagnosis per year."""
    from .injury_model import lasting_trait_deltas
    deltas = lasting_trait_deltas(event)
    if not deltas:
        return
    start = str(event.get("start_date") or "")[:10]
    year_ago = f"{int(start[:4]) - 1}{start[4:7]}" if len(start) >= 7 else ""
    for prior in save.get("development_events", []):
        context = prior.get("health_context") or {}
        if (prior.get("player_id") == event.get("player_id") and context.get("lasting_injury")
                and context.get("diagnosis") == event.get("diagnosis") and str(prior.get("month") or "") > year_ago):
            return
    save.setdefault("development_events", []).append(to_plain(DevelopmentEvent(
        id=stable_id("development", "lasting_injury", event.get("id")),
        player_id=event["player_id"], team_id=event.get("team_id") or "", month=start[:7], trait_deltas=deltas,
        age=None, minutes_context=float(event.get("player_minutes_projection") or 0.0), staff_context={},
        health_context={"lasting_injury": True, "injury_id": event.get("id"), "diagnosis": event.get("diagnosis"),
                        "lasting_rapm_change": event.get("lasting_rapm_change")},
        confidence=0.6, source_ids=["src_injury_model_v2", "src_bbi_injury_long_term"],
        notes=f"Lasting decline after {event.get('diagnosis')} (Basketball Index long-term injury evidence).",
    )))


def show_injuries_from_todays_games(save: dict[str, Any], day: str) -> None:
    """Players hurt in (or after) today's games are listed as out as soon as the games are over."""
    from .health import activate_pending_injury
    for state in save.get("health_states", []):
        pending = state.get("pending_injury")
        if pending and str(pending.get("start_date") or "") <= day:
            activate_pending_injury(state)


def attach_rest_suggestions(root: str | Path, active: dict[str, Any], save: dict[str, Any], day: str, seed: int) -> None:
    """The user's coach suggests rest for the team's next game, by the same rule and seeded draw AI coaches act on
    (health.coach_rest_decision), and each player's fatigue at that tip-off is noted. Stored on the health state and
    shown next to the player. Applied only when the GM lets the coach rest players (game setting); the health pass
    then makes the same decision for that game."""
    from .health import (fatigue_on_date, game_rest_context, league_rest_context, normal_fatigue, performance_staff_modifiers,
                         rest_assessment, rest_decision, rest_draw, REST_MIN_MINUTES)
    from .rest_model import cached_league_schedule_context, star_ids
    human = set(human_controlled_team_ids(save))
    states = {state.get("player_id"): state for state in save.get("health_states", [])}
    roster = {player["id"]: player for player in active.get("players", []) if player.get("team_id") in human}
    for player_id in roster:
        (states.get(player_id) or {}).pop("rest_suggestion", None)
        (states.get(player_id) or {}).pop("fatigue_next", None)
    phase = (save.get("state") or {}).get("phase")
    if not human or not active.get("teams") or phase not in (None, "regular_season", "play_in", "playoffs"):
        return
    espn_by_team ={team["id"]: espn for espn, team in espn_team_id_map(active).items()}
    all_games = sorted(schedule_for_save(root, save), key=lambda g: (g.get("gameDate") or "", str(g.get("externalGameId"))))
    staff_by_team = {team_id: performance_staff_modifiers(active, team_id) for team_id in human}
    for team_id in sorted(human):
        # Fatigue at his team's next tip-off (shown in the fatigue bar's tooltip): the value that game will use.
        espn = espn_by_team.get(team_id)
        upcoming = next((g for g in all_games if (g.get("gameDate") or "") > day
                         and espn in (str(g.get("homeTeamId")), str(g.get("awayTeamId")))), None)
        if not upcoming:
            continue
        for player_id, player in roster.items():
            state = states.get(player_id)
            if state and player.get("team_id") == team_id:
                state["fatigue_next"] = {"date": upcoming["gameDate"],
                                         "value": fatigue_on_date(state, upcoming["gameDate"], staff_by_team[team_id])}
    if not save.get("team_records") or (save.get("state") or {}).get("phase") not in (None, "regular_season"):
        return
    stamina = {trait["player_id"]: float(trait.get("value") if trait.get("value") is not None else 50.0)
               for trait in active.get("traits", []) if trait.get("trait_key") == "stamina_cardio" and trait.get("player_id") in roster}
    standings = league_rest_context({"save_team_records": save.get("team_records"), "teams": active.get("teams", [])})
    games = [g for g in all_games if str(g.get("phase") or "regular") == "regular"]
    facts = cached_league_schedule_context(all_games)
    stars = star_ids(active, day[:7])
    team_by_espn = espn_team_id_map(active)
    for team_id in sorted(human):
        espn = espn_by_team.get(team_id)
        mine = sorted((g for g in games if espn in (str(g.get("homeTeamId")), str(g.get("awayTeamId")))),
                      key=lambda g: (g.get("gameDate") or "", str(g.get("externalGameId"))))
        upcoming = next((g for g in mine if (g.get("gameDate") or "") > day), None)
        if not upcoming:
            continue
        previous = max((g["gameDate"] for g in mine if (g.get("gameDate") or "") <= day), default=None)
        back_to_back = bool(previous) and (parse_date(upcoming["gameDate"]) - parse_date(previous)).days == 1
        opponent_espn = str(upcoming.get("homeTeamId") if str(upcoming.get("awayTeamId")) == espn else upcoming.get("awayTeamId"))
        players = sorted((p for p in roster.values() if p.get("team_id") == team_id), key=lambda p: -float(p.get("minutes_projection") or 0))
        # Same context the day's health pass will build for that game: injured regulars, and regulars the GM rests.
        out = sum(1 for p in players if (states.get(p["id"]) or {}).get("availability_status", "active") != "active"
                  and float(p.get("_trade_value_minutes_projection") or p.get("minutes_projection") or 0) >= REST_MIN_MINUTES)
        gm_rested = [p for p in players if (states.get(p["id"]) or {}).get("user_rest")
                     and float(p.get("_trade_value_minutes_projection") or p.get("minutes_projection") or 0) >= REST_MIN_MINUTES]
        context = game_rest_context(standings, facts, upcoming, espn, team_id,
                                    (team_by_espn.get(opponent_espn) or {}).get("id"), back_to_back=back_to_back)
        context.update({"rested_tonight": len(gm_rested), "stars_rested_tonight": sum(p["id"] in stars for p in gm_rested),
                        "regulars_out": out})
        for player in players:
            state = states.get(player["id"])
            minutes = float(player.get("minutes_projection") or 0)
            if (not state or minutes < REST_MIN_MINUTES
                    or player_unavailable_for_rotation(state)):
                continue
            context["fatigue"] = float((state.get("fatigue_next") or {}).get("value") or 0.0)
            context["fatigue_normal"] = normal_fatigue(player, minutes, stamina.get(player["id"], 50.0), staff_by_team[team_id])
            context["star"] = player["id"] in stars
            decision = rest_decision(rest_assessment(player, state, context), rest_draw(seed, upcoming["externalGameId"], player["id"]))
            if decision:
                state["rest_suggestion"] = {"game_id": str(upcoming["externalGameId"]), "date": upcoming["gameDate"],
                                            "kind": decision[0], "reason": decision[1],
                                            # With "Coach rests my players" on, the coach will act on it.
                                            "coach_decides": team_id in coach_rest_team_ids(save)}
                context["rested_tonight"] += 1
                context["stars_rested_tonight"] += int(context["star"])


def record_rest_decisions(save: dict[str, Any], decisions: list[dict[str, Any]]) -> None:
    """Log each coach rest decision with its short reason (this season only): date, game, team, player, reason and
    the chance the model gave."""
    if not decisions:
        return
    log = save.setdefault("rest_log", [])
    season_floor = f"{season_start_year_from_date(str(decisions[0].get('date') or '2000-01-01'))}-07-01"
    if log and str(log[0].get("date") or "") < season_floor:
        log[:] = [row for row in log if str(row.get("date") or "") >= season_floor]
    seen = {(row.get("game_id"), row.get("player_id")) for row in log}
    for row in decisions:
        if (row.get("game_id"), row.get("player_id")) in seen:
            continue
        log.append({key: row[key] for key in ("date", "game_id", "team_id", "player_id", "kind", "reason", "chance") if key in row})


def merge_health_results(save: dict[str, Any], health: dict[str, Any], canonical: dict[str, Any] | None = None) -> None:
    players = {player["id"]: player for player in (canonical or {}).get("players", [])}
    previous_states = {state.get("player_id"): state for state in save.get("health_states", [])}
    save["health_states"] = health.get("final_states", save.get("health_states", []))
    record_rest_decisions(save, health.get("rest_decisions") or [])
    current_states = {state.get("player_id"): state for state in save.get("health_states", [])}
    seen = {event.get("id") for event in save.get("injury_events", [])}
    socialized = set(save.setdefault("socialized_injury_event_ids", []))
    for event in health.get("events", []):
        if event.get("id") not in seen:
            injured_player = players.get(event.get("player_id"), {})
            event.setdefault("player_minutes_projection", display_minutes_projection(injured_player) if injured_player else 0.0)
            event.setdefault("was_starter", event.get("player_id") in save.get("starting_lineups", {}).get(event.get("team_id"), {}).get("slots", {}).values())
            valuation = next((v for v in (canonical or {}).get("player_asset_valuations", []) if v.get("player_id") == event.get("player_id")), {})
            if valuation.get("health_risk") is not None:
                event.setdefault("health_risk", valuation["health_risk"])
            save.setdefault("injury_events", []).append(event)
            seen.add(event.get("id"))
            record_lasting_injury_effect(save, event)
        player = players.get(event.get("player_id"), {})
        player_name = player.get("name") or event.get("player_id") or "A player"
        games = event.get("expected_games_missed") or event.get("expected_days_missed") or "some"
        expected_games = int(event.get("expected_games_missed") or 0)
        player_mpg = display_minutes_projection(player) if player else 0.0
        if expected_games > MAJOR_INJURY_GAMES_THRESHOLD and player_mpg > MAJOR_PLAYER_MPG_THRESHOLD:
            add_league_event(
                save,
                "injury",
                (f"{player_name} is expected to miss about {games} games with a {event['diagnosis']}." if event.get("diagnosis") else f"{player_name} is expected to miss about {games} games with a {event.get('body_area')} issue."),
                date_value=event.get("start_date"),
                team_ids=[player.get("team_id")] if player.get("team_id") else [],
                player_ids=[event.get("player_id")] if event.get("player_id") else [],
                importance=0.74,
                details={
                    "injury_id": event.get("id"),
                    "player_id": event.get("player_id"),
                    "expected_games_missed": expected_games,
                    "player_minutes_projection": player_mpg,
                    "body_area": event.get("body_area"),
                },
            )
        if event.get("id") not in socialized and int(event.get("expected_games_missed") or 0) >= SOCIAL_INJURY_GAMES_THRESHOLD:
            if display_minutes_projection(player) < 20.0:
                socialized.add(event.get("id"))
                continue
            add_news(
                save,
                "injury",
                (f"{player_name} is expected to miss about {games} games with a {event['diagnosis']}." if event.get("diagnosis") else f"{player_name} is expected to miss about {games} games with a {event.get('body_area')} issue."),
                date_value=event.get("start_date"),
            )
            socialized.add(event.get("id"))
    save["socialized_injury_event_ids"] = sorted(item for item in socialized if item)
    add_return_from_injury_social(save, canonical or {}, previous_states, current_states)
    save["injury_events"] = sorted(save.get("injury_events", []), key=lambda item: item.get("id", ""))
    normalize_user_rotation_for_injuries(save, canonical or {})


def normalize_user_rotation_for_injuries(save: dict[str, Any], canonical: dict[str, Any]) -> None:
    """Keep healthy user targets; project temporary injury substitutions separately."""
    overrides_by_team = save.get("rotation_overrides") or {}
    if not overrides_by_team:
        return
    # Dashboard callers may supply the immutable preseason universe. Trades,
    # generated players and retirements must be resolved before saving roles.
    current_players = active_players_for_roster_checks(canonical, save)
    for team_id, override in list(overrides_by_team.items()):
        if not isinstance(override, dict) or not override:
            continue
        roster = [player for player in current_players if player.get("team_id") == team_id]
        if not roster:
            continue
        cleaned = {
            player["id"]: int(round(clamp(float(override[player["id"]] or 0.0), 0.0, 48.0)))
            for player in roster
            if player["id"] in override
        }
        save["rotation_overrides"][team_id] = cleaned
        locked_by_team = save.setdefault("rotation_locked_player_ids", {})
        locked_by_team[team_id] = [
            player_id
            for player_id in locked_by_team.get(team_id, list(override))
            if player_id in cleaned
        ]


def add_return_from_injury_social(
    save: dict[str, Any],
    canonical: dict[str, Any],
    previous_states: dict[str, dict[str, Any]],
    current_states: dict[str, dict[str, Any]],
) -> None:
    events = {event.get("id"): event for event in save.get("injury_events", [])}
    posted = set(save.setdefault("socialized_injury_return_ids", []))
    players = {player["id"]: player for player in canonical.get("players", [])}
    season_stats = save.get("player_season_stats", {})
    for player_id, before in previous_states.items():
        injury_id = before.get("current_injury_id")
        after = current_states.get(player_id, {})
        event = events.get(injury_id, {})
        if not injury_id or injury_id in posted or after.get("availability_status") != "active":
            continue
        if int(event.get("expected_games_missed") or 0) < SOCIAL_INJURY_GAMES_THRESHOLD:
            continue
        player = players.get(player_id, {})
        if display_minutes_projection(player) < 20.0:
            posted.add(injury_id)
            continue
        team_id = player.get("team_id")
        replacement = max(
            (
                teammate for teammate in players.values()
                if teammate.get("team_id") == team_id
                and teammate.get("id") != player_id
                and per_game_stat(season_stats.get(teammate.get("id"), {}), "minutes") >= 18
            ),
            key=lambda teammate: per_game_stat(season_stats.get(teammate.get("id"), {}), "minutes"),
            default=None,
        )
        if not replacement:
            continue
        add_social(
            save,
            "injury_return",
            f"{player.get('name', player_id)} is returning, but {replacement.get('name')} earned a real rotation role during the absence.",
            team_ids=[team_id] if team_id else [],
        )
        posted.add(injury_id)
    save["socialized_injury_return_ids"] = sorted(posted)


def add_notable_development_social(save: dict[str, Any], canonical: dict[str, Any], events: list[dict[str, Any]], month: str) -> None:
    if not events:
        return
    players = {player["id"]: player for player in canonical.get("players", [])}
    best = max(
        events,
        key=lambda event: sum(max(0.0, float(value)) for value in (event.get("trait_deltas") or {}).values()),
        default=None,
    )
    if not best:
        return
    gain = sum(max(0.0, float(value)) for value in (best.get("trait_deltas") or {}).values())
    if gain < 1.25:
        return
    player = players.get(best.get("player_id"), {"name": best.get("player_id")})
    add_social(
        save,
        "player_stretch",
        f"{player.get('name')} has real development buzz after a noticeable {month} skill jump.",
        team_ids=[best.get("team_id")] if best.get("team_id") else [],
        date_value=f"{month}-01",
    )


def maybe_queue_rare_drama(save: dict[str, Any], canonical: dict[str, Any], current: str, target: str, seed: int) -> None:
    user_team_id = save.get("meta", {}).get("user_team_id")
    if not user_team_id or save.get("rare_drama_triggered"):
        return
    if phase_for_date(target) not in {"regular_season", "playoffs"}:
        return
    rng = random.Random(f"{seed}:{save.get('meta', {}).get('id')}:{current}:{target}:rare_drama")
    days = max(1, (parse_date(target) - parse_date(current)).days)
    if rng.random() > min(0.015, days * 0.00065):
        return
    players = [player for player in canonical_with_save(canonical, save).get("players", []) if player.get("team_id") == user_team_id]
    if not players:
        return
    player = sorted(players, key=lambda item: display_minutes_projection(item), reverse=True)[min(len(players) - 1, int(rng.random() * min(8, len(players))))]
    headline = f"{player.get('name')} is trending after a heated online clip from team travel."
    event = {
        "id": stable_id("press_event", "rare_drama", headline, target),
        "date": target,
        "kind": "rare_drama",
        "headline": headline,
        "question": f"{headline} Are you backing the player publicly or making an example internally?",
        "status": "pending",
    }
    save.setdefault("pending_press_events", []).append(event)
    save["rare_drama_triggered"] = True
    add_social(save, "press_conference", headline, team_ids=[user_team_id], date_value=target)


def queue_ai_recommendations(
    canonical: dict[str, Any],
    save: dict[str, Any],
    from_date: str,
    through_date: str,
    seed: int,
    authoritative_canonical: dict[str, Any] | None = None,
) -> None:
    authoritative_canonical = authoritative_canonical or canonical
    phase = save.get("state", {}).get("phase")
    queued_keys = {item.get("id") for item in save.get("pending_ai_actions", [])} | {item.get("id") for item in save.get("processed_hidden_ai_actions", [])}
    if phase in {"preseason", "regular_season"} and through_date <= extension_deadline_date(season_start_year_from_date(through_date)):
        extension_key = stable_id("ai_action", "extensions", through_date[:7], seed)
        if extension_key not in queued_keys:
            extension_result = process_ai_extensions(
                canonical,
                save,
                through_date,
                seed,
                prepared_active=True,
                baseline=authoritative_canonical,
            )
            save.setdefault("processed_hidden_ai_actions", []).append(
                {
                    "id": extension_key,
                    "date": through_date,
                    "action_type": "ai_extensions",
                    "status": "executed" if extension_result.get("applied_count") else "reviewed",
                    "applied_count": extension_result.get("applied_count", 0),
                    "refusal_count": extension_result.get("refusal_count", 0),
                    "notes": "AI extension decisions process quietly from core/depth role, ask, age, performance, and team context.",
                }
            )
    from .trade_calendar import market_day
    start_year = season_start_year_from_date(through_date)
    trade_deadline = trade_deadline_date(start_year)
    market = market_day(through_date, seed, start_year, trade_deadline)
    trade_window_open = phase in {'preseason', 'regular_season', 'training_camp'} and market['review']
    if "trades" in legal_actions_for_date(through_date) and trade_window_open:
        action_id = stable_id("ai_action", "trades", through_date, seed)
        if action_id not in queued_keys and not market['slots'] and not (market['offer_slots'] and human_controlled_team_ids(save)):
            # A listening day with no trade slots and no inbound offer slots: the searches below could only
            # end in this same empty review (zero slots admit no AI-AI deal and no user offer), so skip them.
            save.setdefault('processed_hidden_ai_actions', []).append({
                'id': action_id, 'date': through_date, 'action_type': 'trade_market_review',
                'status': 'reviewed', 'market_slots': market['slots'], 'user_offers_generated': 0})
            return
        if action_id not in queued_keys:
            from .transactions import simulate_ai_trades, proposal_asset_identity_keys, trade_team_ids

            from .trade_review import MarketReview
            review = MarketReview()
            # With no AI-AI trade slot today nothing from this search can be chosen below, so only the
            # inbound (user offer) search runs. That search then starts from a fresh review context
            # instead of one warmed by this search's caches.
            payload = simulate_ai_trades(canonical, through_date, through_date, seed=seed, review=review,
                                         limit=min(35, market["slots"] + 3),  # a few spares for deals the live re-check rejects
                                         reserve_assets=True,
                                         search_depth=2 if (date.fromisoformat(trade_deadline)-date.fromisoformat(through_date)).days <= 6 else 1) if market['slots'] else {'proposals': []}
            human_team_ids = human_controlled_team_ids(save)
            legal_accepted = [
                proposal for proposal in payload.get("proposals", [])
                if proposal.get("accepted_by_all") and proposal.get("legality", {}).get("status") == "legal"
            ]
            # Human proposals get their own search budget: the first accepted
            # AI buyer for each target must not starve the user's inbox.
            inbound = simulate_ai_trades(canonical, through_date, through_date, seed=seed,
                limit=max(12, market['offer_slots']*4), search_depth=2,
                involving_team_ids=human_team_ids, review=review) if human_team_ids and market['offer_slots'] else {'proposals': []}
            review.close()
            user_offers = [
                proposal for proposal in inbound.get('proposals', [])
                if proposal.get('accepted_by_all') and proposal.get('legality', {}).get('status') == 'legal'
                if human_team_ids.intersection(trade_team_ids(proposal))
            ][:market['offer_slots']]
            # Trade step 4: AI teams may offer the user's team picks to take salary in a deal they almost made.
            user_offers += (payload.get('user_absorber_offers') or [])[:max(0, market['offer_slots'] - len(user_offers))]
            if user_offers:
                queue_user_trade_offers(save, user_offers, through_date)
            eligible = [
                proposal for proposal in legal_accepted
                if not human_team_ids.intersection(trade_team_ids(proposal))
            ]
            chosen, reserved_assets = [], set()
            for proposal in eligible:
                bundle = proposal.get('proposal') or {}
                assets = proposal_asset_identity_keys(proposal)
                if assets & reserved_assets or len(chosen) >= market['slots']:
                    continue
                chosen.append(proposal)
                reserved_assets |= assets
            payload["proposals"] = chosen
            payload["proposal_count"] = len(payload["proposals"])
            if not payload["proposals"]:
                save.setdefault('processed_hidden_ai_actions', []).append({
                    'id': action_id, 'date': through_date, 'action_type': 'trade_market_review',
                    'status': 'reviewed', 'market_slots': market['slots'],
                    'user_offers_generated': len(user_offers)})
                return
            save.setdefault("pending_ai_actions", []).append(
                {
                    "id": action_id,
                    "date": through_date,
                    "action_type": "trade_recommendations",
                    "status": "recommendation_pending_review",
                    "payload": payload,
                    "notes": "Conservative AI trade recommendations only; no automatic execution in save-loop V1.",
                }
            )
    if phase == "free_agency":
        action_id = stable_id("ai_action", "free_agency", through_date, seed)
        if action_id not in queued_keys:
            from .contract_ai import simulate_free_agency

            payload = simulate_free_agency(canonical, from_date, through_date, seed=seed, limit=10)
            payload = filter_free_agency_payload_to_available(canonical, save, payload)
            if not payload.get("negotiations"):
                return
            save.setdefault("pending_ai_actions", []).append(
                {
                    "id": action_id,
                    "date": through_date,
                    "action_type": "free_agency_recommendations",
                    "status": "recommendation_pending_review",
                    "payload": payload,
                    "notes": "Conservative AI free-agency recommendations only; accepted contracts still require explicit application.",
                }
            )
    if phase == "draft":
        action_id = stable_id("ai_action", "draft", through_date, seed)
        if action_id not in queued_keys:
            save.setdefault("pending_ai_actions", []).append(
                {
                    "id": action_id,
                    "date": through_date,
                    "action_type": "draft_window_open",
                    "status": "user_or_ai_draft_decisions_pending",
                    "payload": {"draft_year": "2026"},
                    "notes": "Draft window marker. Use simulate-draft or pick-recommendations for explicit draft-night decisions.",
                }
            )
    staff_review_due = (
        from_date[:7] != through_date[:7]
        or phase in {"training_camp", "offseason", "draft_lottery", "draft", "re_signing", "free_agency"}
        or through_date.endswith("-02-05")
    )
    if staff_review_due:
        action_id = stable_id("ai_action", "staff", through_date[:7], phase, seed)
        if action_id not in queued_keys:
            payload = simulate_ai_staff_changes(canonical, save, from_date, through_date, seed=seed, limit=8)
            if payload.get("recommendations"):
                # Staff evaluation should use the live team context above, but
                # the spending ceiling is a stable franchise constraint. Save-
                # enriched strategy states must not silently raise that ceiling.
                result = apply_ai_staff_recommendations(authoritative_canonical, save, payload, seed)
                save.setdefault("processed_hidden_ai_actions", []).append(
                    {
                        "id": action_id,
                        "date": through_date,
                        "action_type": "staff_change_recommendations",
                        "status": "executed" if result.get("applied_count") else "reviewed",
                        "applied_count": result.get("applied_count", 0),
                        "notes": "Leaguewide AI staff changes process quietly; user-team staff moves remain manual.",
                    }
                )


def queue_user_trade_offers(save: dict[str, Any], offers: list[dict[str, Any]], date_value: str) -> None:
    from .transactions import trade_offer_fingerprint

    existing = {
        ((offer.get("proposal") or {}).get("id") or offer.get("id"))
        for offer in save.setdefault("user_trade_offers", [])
    }
    for queued_offer in save["user_trade_offers"]:
        existing.update(queued_offer.get("repeat_proposal_ids") or [])
    pending_by_fingerprint = {}
    for queued_offer in save["user_trade_offers"]:
        if (queued_offer.get("offer_context") or {}).get("status") == "pending_user_review":
            pending_by_fingerprint.setdefault(trade_offer_fingerprint(queued_offer), queued_offer)
    queued = repeated = 0
    for offer in offers:
        proposal_id = (offer.get("proposal") or {}).get("id") or offer.get("id")
        if not proposal_id or proposal_id in existing:
            continue
        fingerprint = trade_offer_fingerprint(offer)
        previous = pending_by_fingerprint.get(fingerprint)
        if previous:
            previous_context = previous.setdefault("offer_context", {})
            previous_count = max(1, int(previous.get("repeat_count") or 1))
            incoming_count = max(1, int(offer.get("repeat_count") or 1))
            previous["repeat_count"] = previous_count + incoming_count
            previous.setdefault("repeat_proposal_ids", []).append(proposal_id)
            dates = list(previous.get("repeat_dates") or [previous_context.get("created_date")])
            dates.extend(offer.get("repeat_dates") or [date_value])
            previous["repeat_dates"] = list(dict.fromkeys(str(item) for item in dates if item))
            previous_context["last_proposed_date"] = date_value
            existing.add(proposal_id)
            repeated += incoming_count
            continue
        save["user_trade_offers"].append(
            {
                **offer,
                "repeat_count": max(1, int(offer.get("repeat_count") or 1)),
                "repeat_dates": list(offer.get("repeat_dates") or [date_value]),
                "offer_context": {
                    **(offer.get("offer_context") or {}),
                    "created_date": date_value,
                    "last_proposed_date": date_value,
                    "status": "pending_user_review",
                    "source": "ai_trade_offer_to_user",
                },
            }
        )
        existing.add(proposal_id)
        pending_by_fingerprint[fingerprint] = save["user_trade_offers"][-1]
        queued += 1
    if queued or repeated:
        if queued and repeated:
            headline = f"{queued} new AI trade offer(s) arrived; {repeated} identical proposal(s) were added to existing offers."
        elif queued:
            headline = f"{queued} AI trade offer(s) arrived for your review."
        else:
            headline = f"An AI team checked in on {repeated} existing trade offer(s)."
        add_news(save, "trade_offer", headline, date_value=date_value)


def expire_user_trade_offers_after_deadline(save: dict[str, Any], current_date: str | None = None) -> int:
    current_date = current_date or save.get("state", {}).get("current_date")
    if not current_date:
        return 0
    try:
        deadline = trade_deadline_date(season_start_year_from_date(str(current_date)))
    except Exception:
        return 0
    if str(current_date) <= deadline:
        return 0
    expired = 0
    for offer in save.get("user_trade_offers", []) or []:
        context = offer.setdefault("offer_context", {})
        if context.get("status") != "pending_user_review":
            continue
        context["status"] = "expired_trade_deadline"
        context["expired_date"] = str(current_date)
        expired += 1
    return expired


def add_monthly_social_digest(canonical: dict[str, Any], save: dict[str, Any], from_date: str, through_date: str) -> None:
    if from_date[:7] == through_date[:7]:
        return
    digest_key = f"{through_date[:7]}:{save.get('meta', {}).get('season')}:social_digest"
    existing = {item.get("id") for item in save.get("social_feed", [])}
    if stable_id("social_digest", digest_key) in existing:
        return
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    recent_logs = [log for log in save.get("team_game_logs", []) if from_date < log.get("date", "") <= through_date]
    by_team: dict[str, list[dict[str, Any]]] = {}
    for log in recent_logs:
        by_team.setdefault(log.get("team_id"), []).append(log)
    streaks = []
    for team_id, logs in by_team.items():
        if len(logs) < 10:
            continue
        wins = sum(1 for log in logs if log.get("result") == "W")
        losses = len(logs) - wins
        win_pct = wins / max(1, len(logs))
        if wins - losses < 8 and win_pct < 0.82:
            continue
        streaks.append((wins - losses, wins, losses, team_id))
    if streaks:
        score, wins, losses, team_id = sorted(streaks, reverse=True)[0]
        team = teams.get(team_id, {"abbrev": str(team_id)})
        add_social(save, "team_stretch", f"{team.get('abbrev')} went {wins}-{losses} over the latest stretch.", team_ids=[team_id])
    stats = save.get("player_season_stats", {})
    if stats:
        leader = max(stats.values(), key=lambda item: float(item.get("points") or 0) / max(1, int(item.get("games") or 1)))
        ppg = float(leader.get("points") or 0) / max(1, int(leader.get("games") or 1))
        role = public_player_role(canonical, leader.get("player_id"), ppg)
        add_social(save, "player_stretch", f"{leader.get('player_name')} is up to {ppg:.1f} PPG on the season for {leader.get('team_abbrev')} as a {role}.", team_ids=[leader.get("team_id")] if leader.get("team_id") else [])
    standings = sorted(
        save.get("team_records", {}).values(),
        key=lambda record: (-(int(record.get("wins") or 0) / max(1, int(record.get("wins") or 0) + int(record.get("losses") or 0))), record.get("team_abbrev")),
    )
    if standings:
        top = standings[0]
        add_social(save, "power_ranking", f"Monthly power check: {top.get('team_abbrev')} sits on top at {top.get('wins')}-{top.get('losses')}.", team_ids=[top.get("team_id")] if top.get("team_id") else [])
    save.setdefault("social_feed", []).append(
        {
            "id": stable_id("social_digest", digest_key),
            "date": through_date,
            "kind": "social_digest_marker",
            "text": "Monthly social digest marker.",
            "author": "System",
            "handle": "@system",
            "persona": "marker",
            "subject": "digest",
            "team_ids": [],
            "sentiment": 0,
            "importance": 0,
        }
    )


def filter_free_agency_payload_to_available(canonical: dict[str, Any], save: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    filtered = [
        item for item in payload.get("negotiations", [])
        if negotiation_player_is_free(canonical, save, item) and negotiation_has_positive_accepted_offer(item)
    ]
    return {**payload, "negotiations": filtered, "negotiation_count": len(filtered)}


def contract_terms_label(contract: dict[str, Any] | None) -> str:
    contract = contract or {}
    annual = contract.get("annual_salary") or contract.get("salary") or contract.get("aav") or contract.get("aav_millions")
    years = contract.get("years") or contract.get("original_contract_years") or contract.get("term_years")
    seasons = contract.get("seasons") or []
    if years is None and isinstance(seasons, list) and seasons:
        years = len(seasons)
    if annual is None and isinstance(seasons, list) and seasons:
        salaries = [float(row.get("salary") or 0.0) for row in seasons if isinstance(row, dict)]
        if salaries:
            annual = sum(salaries) / len(salaries)
    try:
        annual_m = float(annual)
        if annual_m > 1_000:
            annual_m /= 1_000_000
    except (TypeError, ValueError):
        annual_m = 0.0
    try:
        years_i = int(years)
    except (TypeError, ValueError):
        years_i = 0
    if annual_m <= 0.0 or years_i <= 0:
        return ""
    money = f"${annual_m:.0f}M" if abs(annual_m - round(annual_m)) < 0.05 else f"${annual_m:.1f}M"
    return f"{money} x {years_i}"


def extension_headline_with_terms(team_abbrev: str | None, player_name: str | None, contract: dict[str, Any] | None) -> str:
    team_label = team_abbrev or "Team"
    player_label = player_name or "Player"
    terms = contract_terms_label(contract)
    if terms:
        return f"{team_label} extends {player_label} to {terms}."
    return f"{team_label} extends {player_label}."


def process_ai_extensions(
    canonical: dict[str, Any],
    save: dict[str, Any],
    through_date: str,
    seed: int,
    limit: int = 22,
    *,
    prepared_active: bool = False,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # baseline: the league before the save is applied. The hard-cap check rebuilds the league from it; rebuilding from
    # an already-prepared league refits the 94-input ratings model just to read contracts (INPUTS-DEFAULT speed note).
    from .contract_ai import extension_candidates_report, merge_extension_offer_with_existing_contract, negotiate_extension, with_extension_context

    active = with_extension_context(canonical if prepared_active else canonical_with_save(canonical, save))
    report = extension_candidates_report(active)
    human_team_ids = human_controlled_team_ids(save)
    processed = set(save.setdefault("processed_ai_extensions", []))
    applied = 0
    refusals = 0
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    volume_by_season = save.setdefault("ai_extension_volume", {})
    if season not in volume_by_season:
        reconstructed = {"rookie_scale": 0, "veteran": 0}
        season_year = season_start_year(season)
        season_window_start = f"{season_year}-07-01"
        season_window_end = f"{season_year + 1}-06-30"
        for log in save.get("transaction_logs", []):
            log_date = str(log.get("date") or "")
            if log.get("transaction_type") != "extension" or not season_window_start <= log_date <= season_window_end:
                continue
            evaluation = next((row for row in log.get("evaluations", []) if row.get("source") == "ai_extension"), None)
            if not evaluation:
                continue
            player_id = (log.get("assets") or {}).get("player_id")
            player = players.get(player_id, {})
            bucket = evaluation.get("bucket") or (
                "rookie_scale" if float(player.get("display_age", player.get("age")) or 27.0) <= 25.0 else "veteran"
            )
            reconstructed[bucket] = int(reconstructed.get(bucket) or 0) + 1
        volume_by_season[season] = reconstructed
    volume = volume_by_season[season]
    for candidate in report.get("candidates", []):
        player_id = candidate.get("player_id")
        team_id = candidate.get("team_id")
        key = stable_id("ai_extension", save.get("meta", {}).get("season"), team_id, player_id)
        if not player_id or not team_id or key in processed or team_id in human_team_ids:
            continue
        if not candidate.get("eligible") or candidate.get("manual_review_required"):
            continue
        player = players.get(player_id)
        team = teams.get(team_id)
        if not player or not team:
            continue
        priority = ai_extension_priority(save, candidate, player, team_id, seed)
        due_date = ai_extension_due_date(save, candidate, player, priority, seed)
        if through_date < due_date:
            continue
        team_pass = ai_extension_team_pass_outlook(save, candidate, player, team_id, priority)
        if team_pass:
            pressure = set(save.setdefault("ai_trade_pressure_player_ids", []))
            pressure.add(player_id)
            save["ai_trade_pressure_player_ids"] = sorted(pressure)
            refusals += 1
            headline = ai_extension_refusal_headline(team, player, team_pass)
            add_news(save, team_pass["news_kind"], headline, date_value=through_date)
            add_league_event(
                save,
                team_pass["event_kind"],
                headline,
                date_value=through_date,
                team_ids=[team_id],
                player_ids=[player_id],
                importance=team_pass.get("importance"),
                details={
                    "player_id": player_id,
                    "team_id": team_id,
                    "priority": round(priority, 2),
                    "reason": team_pass.get("reason"),
                    "projected_aav_millions": candidate.get("projected_aav_millions"),
                    "minutes_projection": display_minutes_projection(player),
                    "is_trade_demand": False,
                    "team_passed_on_extension": True,
                },
            )
            processed.add(key)
            continue
        bucket = "rookie_scale" if float(player.get("display_age", player.get("age")) or 27.0) <= 25.0 else "veteran"
        if int(volume.get(bucket) or 0) >= AI_EXTENSION_BUCKET_LIMIT:
            processed.add(key)
            continue
        if priority < 78.0:
            # Fringe or bad-fit cases stay live for later checkpoints instead of being
            # burned for the full season before their role/team context has settled.
            continue
        result = negotiate_extension(active, player_id, team_id, seed=seed, max_rounds=3, date=through_date)
        if result.get("accepted") and (result.get("decision") or {}).get("accepted_offer"):
            negotiation = result.get("negotiation") or {}
            offer = dict((result.get("decision") or {}).get("accepted_offer") or {})
            offer.setdefault("team_id", team_id)
            offer.setdefault("start_season", extension_start_season_from_date_save(through_date))
            offer = ai_adjust_extension_offer_for_current_season(save, candidate, player, offer, priority)
            offer = merge_extension_offer_with_existing_contract(offer, negotiation)
            if not extension_offer_fits_hard_cap(baseline if baseline is not None else canonical, save, player_id, offer):
                continue
            from .contract_ai import keep_bird_clock
            keep_bird_clock(save, player, team_id, str(offer.get("signed_season") or ""))   # extensions keep it
            save.setdefault("contract_overrides", {})[player_id] = offer
            save.setdefault("transaction_logs", []).append(
                {
                    "id": stable_id("transaction_log", "ai_extension", key, through_date),
                    "date": through_date,
                    "transaction_type": "extension",
                    "proposal_id": key,
                    "status": "applied_to_save_ledger",
                    "teams": [team_id],
                    "assets": {"player_id": player_id, "name": player.get("name"), "contract": offer},
                    "evaluations": [{"priority": round(priority, 2), "source": "ai_extension", "bucket": bucket}],
                    "source_ids": ["src_contract_market_config_v1"],
                    "notes": "AI team extended an eligible player based on role, production, age, ask, team context, and deterministic negotiation.",
                }
            )
            headline = extension_headline_with_terms(team.get("abbrev"), player.get("name"), offer)
            annual = float(offer.get("annual_salary") or 0.0)
            add_news(save, "extension", headline, date_value=through_date)
            add_league_event(
                save,
                "extension",
                headline,
                date_value=through_date,
                team_ids=[team_id],
                player_ids=[player_id],
                importance=0.74 if annual > MAJOR_FREE_AGENT_AAV_THRESHOLD else None,
                details={
                    "player_id": player_id,
                    "team_id": team_id,
                    "annual_salary": annual,
                    "aav_millions": round(annual / 1_000_000, 2) if annual else 0.0,
                    "contract": offer,
                    "years": int(offer.get("original_contract_years") or offer.get("years") or 0),
                },
            )
            applied += 1
            volume[bucket] = int(volume.get(bucket) or 0) + 1
        else:
            outlook = ai_extension_refusal_outlook(save, candidate, player, team_id, priority)
            if outlook.get("is_trade_demand"):
                pressure = set(save.setdefault("ai_trade_pressure_player_ids", []))
                pressure.add(player_id)
                save["ai_trade_pressure_player_ids"] = sorted(pressure)
            if priority >= 68.0 or outlook.get("should_surface"):
                refusals += 1
                headline = ai_extension_refusal_headline(team, player, outlook)
                add_news(save, outlook["news_kind"], headline, date_value=through_date)
                add_league_event(
                    save,
                    outlook["event_kind"],
                    headline,
                    date_value=through_date,
                    team_ids=[team_id],
                    player_ids=[player_id],
                    importance=outlook.get("importance"),
                    details={
                        "player_id": player_id,
                        "team_id": team_id,
                        "priority": round(priority, 2),
                        "reason": outlook.get("reason"),
                        "projected_aav_millions": candidate.get("projected_aav_millions"),
                        "minutes_projection": display_minutes_projection(player),
                        "is_trade_demand": bool(outlook.get("is_trade_demand")),
                    },
                )
        processed.add(key)
        if applied >= limit:
            break
    save["processed_ai_extensions"] = sorted(processed)
    return {"applied_count": applied, "refusal_count": refusals}


def extension_offer_fits_hard_cap(canonical: dict[str, Any], save: dict[str, Any], player_id: str, offer: dict[str, Any]) -> bool:
    """Check every new extension season against the game's hard cap."""
    trial = _copy_runtime_tree(save)
    trial.setdefault("contract_overrides", {})[player_id] = deepcopy(offer)
    active = canonical_with_save(canonical, trial)
    team_id = offer.get("team_id") or offer.get("accepted_team_id")
    start_season = str(offer.get("start_season") or offer.get("signed_season") or "")
    if not team_id or not start_season:
        return False
    extension_seasons = {
        str(row.get("season"))
        for row in offer.get("seasons", [])
        if row.get("season") and str(row.get("season")) >= start_season
    }
    if not extension_seasons:
        projected = offer_to_contract_seasons({**offer, "season": start_season})
        extension_seasons = {str(row.get("season")) for row in projected if row.get("season")}
    return all(
        float(team_cap_summary(active, trial, str(team_id), season).get("hard_cap_space_millions") or 0.0) >= -0.01
        for season in extension_seasons
    )


def ai_extension_priority(save: dict[str, Any], candidate: dict[str, Any], player: dict[str, Any], team_id: str, seed: int) -> float:
    minutes = display_minutes_projection(player)
    age = float(player.get("display_age", player.get("age")) or 27.0)
    aav = float(candidate.get("projected_aav_millions") or 0.0)
    stats = save.get("player_season_stats", {}).get(player.get("id"), {})
    ppg = per_game_stat(stats, "points")
    record = save.get("team_records", {}).get(team_id, {})
    games = max(1, int(record.get("wins") or 0) + int(record.get("losses") or 0))
    win_pct = float(record.get("wins") or 0) / games
    score = 30.0 + minutes * 1.22 + min(13.0, ppg * 0.38) + min(12.0, aav * 0.25)
    if player.get('id') in save.get('team_plans', {}).get(team_id, {}).get('core_ids', []):
        score += 8.0
    if int(stats.get("games") or 0) >= 10 and minutes >= 16:
        expected_ppg = max(4.0, minutes * 0.48)
        score += clamp((ppg - expected_ppg) * 0.45, -5.0, 5.5)
    if minutes >= 30 or aav >= 25.0:
        score += 17.0
    elif minutes >= 26:
        score += 11.0
    elif minutes >= 22:
        score += 6.0
    elif minutes < 16:
        score -= 20.0
    if age <= 24 and minutes >= 20:
        score += 10.0
    elif age <= 27 and minutes >= 22:
        score += 5.0
    if age >= 29:
        score -= min(10.0, (age - 28.0) * (1.4 if minutes < 30 and aav < 25.0 else 0.8))
    if age >= 33:
        score -= (age - 32.0) * 3.0
    if win_pct >= 0.56:
        score += 5.5
    elif win_pct <= 0.38 and age >= 25:
        score -= 5.0 if age < 30 else 9.0
    roll = int(hashlib.sha256(f"{seed}:{team_id}:{player.get('id')}:ai_extension_roll".encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    score += (roll - 0.5) * 12.0
    return clamp(score, 0.0, 100.0)


def ai_extension_due_date(save: dict[str, Any], candidate: dict[str, Any], player: dict[str, Any], priority: float, seed: int) -> str:
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    start_year = season_start_year_from_date(str(current))
    if priority >= 82.0:
        month_day = "10-01"
    elif priority >= 72.0:
        month_day = "11-10"
    elif priority >= 62.0:
        month_day = "12-05"
    else:
        month_day = "01-05"
    jitter = int(hashlib.sha256(f"{seed}:{player.get('id')}:{candidate.get('team_id')}:extension_due".encode("utf-8")).hexdigest()[:2], 16) % 11
    try:
        due_year = start_year + 1 if month_day.startswith("01-") else start_year
        base = parse_date(f"{due_year}-{month_day}") + timedelta(days=jitter)
        deadline = parse_date(extension_deadline_date(start_year))
        return min(base, deadline).isoformat()
    except (TypeError, ValueError):
        return f"{start_year}-{month_day}"


def ai_adjust_extension_offer_for_current_season(save: dict[str, Any], candidate: dict[str, Any], player: dict[str, Any], offer: dict[str, Any], priority: float) -> dict[str, Any]:
    adjusted = dict(offer or {})
    age = float(player.get("display_age", player.get("age")) or 27.0)
    stats = save.get("player_season_stats", {}).get(player.get("id"), {})
    games = int(stats.get("games") or 0)
    minutes = display_minutes_projection(player)
    if games >= 10 and adjusted.get("annual_salary"):
        ppg = per_game_stat(stats, "points")
        expected_ppg = max(4.0, minutes * 0.48)
        factor = 1.0 + clamp((ppg - expected_ppg) / 120.0, -0.06, 0.08)
        adjusted["annual_salary"] = round(float(adjusted.get("annual_salary") or 0.0) * factor, 2)
    years = int(adjusted.get("years") or adjusted.get("original_contract_years") or 1)
    if age >= 33:
        years = min(years, 1 if priority < 82.0 else 2)
    elif age >= 31:
        years = min(years, 2 if priority < 84.0 else 3)
    elif age >= 29:
        years = min(years, 3 if priority >= 78.0 else 2)
    adjusted["years"] = max(1, years)
    adjusted["original_contract_years"] = adjusted["years"]
    return adjusted


def ai_extension_team_pass_outlook(save: dict[str, Any], candidate: dict[str, Any], player: dict[str, Any], team_id: str, priority: float) -> dict[str, Any] | None:
    age = float(player.get("display_age", player.get("age")) or 27.0)
    minutes = display_minutes_projection(player)
    aav = float(candidate.get("projected_aav_millions") or 0.0)
    stats = save.get("player_season_stats", {}).get(player.get("id"), {})
    games = int(stats.get("games") or 0)
    record = save.get("team_records", {}).get(team_id, {})
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    win_pct = wins / max(1, wins + losses)
    if age < 29 or minutes < 22.0 or aav < 12.0 or priority >= 72.0:
        return None
    ppg = per_game_stat(stats, "points") if games >= 10 else 0.0
    expected_ppg = max(6.0, minutes * 0.48)
    production_shortfall = games >= 10 and ppg + 2.0 < expected_ppg
    bad_direction = wins + losses >= 18 and win_pct <= 0.40
    if not (production_shortfall or bad_direction or (age >= 32 and aav >= 18.0)):
        return None
    reason = "price and age no longer line up"
    if production_shortfall:
        reason = f"production has not matched the projected ${aav:.1f}M ask"
    if bad_direction:
        reason = f"team sits {wins}-{losses} while weighing an older extension"
    return {
        "event_kind": "extension",
        "news_kind": "extension",
        "importance": 0.64,
        "reason": reason,
        "is_trade_demand": False,
        "should_surface": True,
        "team_passed_on_extension": True,
    }


def ai_extension_refusal_outlook(save: dict[str, Any], candidate: dict[str, Any], player: dict[str, Any], team_id: str, priority: float) -> dict[str, Any]:
    age = float(player.get("display_age", player.get("age")) or 27.0)
    minutes = display_minutes_projection(player)
    record = save.get("team_records", {}).get(team_id, {})
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    games = wins + losses
    win_pct = wins / max(1, games)
    bad_direction = games >= 20 and win_pct <= 0.40
    core_player = minutes >= 26.0 or float(candidate.get("projected_aav_millions") or 0.0) >= 20.0
    is_trade_demand = bool(age > 24 and core_player and bad_direction and priority >= 64.0)
    if is_trade_demand:
        return {
            "event_kind": "trade_demand",
            "news_kind": "trade_demand",
            "importance": 0.82,
            "reason": f"extension talks stalled while team sits {wins}-{losses}",
            "is_trade_demand": True,
            "should_surface": True,
        }
    if core_player and priority >= 68.0:
        reason = "rookie extension talks remain unresolved" if age <= 24 else "extension talks remain unresolved"
        if bad_direction:
            reason = f"{reason} amid a {wins}-{losses} start"
        return {
            "event_kind": "extension",
            "news_kind": "extension",
            "importance": 0.62,
            "reason": reason,
            "is_trade_demand": False,
            "should_surface": True,
        }
    return {
        "event_kind": "extension",
        "news_kind": "extension",
        "importance": 0.45,
        "reason": "extension sides remained apart",
        "is_trade_demand": False,
        "should_surface": False,
    }


def ai_extension_refusal_headline(team: dict[str, Any], player: dict[str, Any], outlook: dict[str, Any]) -> str:
    abbrev = team.get("abbrev") or team_id_to_abbrev(team.get("id"))
    name = player.get("name") or "Player"
    reason = str(outlook.get("reason") or "extension talks stalled")
    if outlook.get("is_trade_demand"):
        return f"{name} trade demand surfaces after {abbrev} extension talks stall: {reason}."
    return f"{abbrev} and {name} leave extension talks unresolved: {reason}."


def extension_start_season_from_date_save(date_value: str) -> str:
    try:
        year = int(str(date_value)[:4])
        month = int(str(date_value)[5:7])
    except (TypeError, ValueError):
        year = 2025
        month = 10
    start = year + 1 if month >= 7 else year
    return season_label_from_start(start)


def save_coach_ratings(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, CoachRating]:
    ratings: dict[str, CoachRating] = {}
    for team in canonical.get("teams", []):
        slots = {slot["slot"]: slot for slot in save.get("staff_slots", []) if slot.get("team_id") == team["id"]}
        if not slots:
            continue
        head = slots.get("head_coach", {})
        off = slots.get("offensive_coordinator", {})
        defense = slots.get("defensive_coordinator", {})
        development = slots.get("development_lead", {})
        scouting = slots.get("scouting_lead", {})
        values = {
            "rotation_trust": star_rating([trait_value(head, "rotation_management"), personality_value(head, "communication")]),
            "development": star_rating([trait_value(development, "skill_development"), trait_value(development, "prospect_patience"), trait_value(head, "locker_room")]),
            "offensive_structure": star_rating([trait_value(off, "shot_quality"), trait_value(off, "spacing_design"), trait_value(head, "scheme_balance")]),
            "defensive_structure": star_rating([trait_value(defense, "coverage_design"), trait_value(defense, "discipline"), trait_value(head, "scheme_balance")]),
            "matchup_adjustments": star_rating([trait_value(defense, "matchup_adjustment"), personality_value(head, "adaptability"), trait_value(off, "player_usage")]),
            "player_buy_in": star_rating([trait_value(head, "locker_room"), personality_value(head, "communication"), trait_value(development, "feedback_clarity")]),
            "playoff_preparation": star_rating([trait_value(head, "scheme_balance"), trait_value(defense, "matchup_adjustment"), trait_value(off, "shot_quality")]),
            "experimentation": star_rating([personality_value(head, "adaptability"), trait_value(off, "player_usage"), trait_value(scouting, "risk_modeling")]),
            "hands_on_control": star_rating([trait_value(head, "rotation_management"), personality_value(head, "ambition")]),
            # Coaching overhaul (2026-11-18): one star per rating, each driving its own effect (sim.staff_coach_effect).
            "shot_quality": star_rating([trait_value(off, "shot_quality")]),
            "spacing_design": star_rating([trait_value(off, "spacing_design")]),
            "creator_usage": star_rating([trait_value(off, "player_usage")]),
            "coverage_design": star_rating([trait_value(defense, "coverage_design")]),
            "matchup_scheming": star_rating([trait_value(defense, "matchup_adjustment")]),
            "discipline": star_rating([trait_value(defense, "discipline")]),
            "rotation_management": star_rating([trait_value(head, "rotation_management")]),
            "player_relations": star_rating([trait_value(head, "locker_room"), personality_value(head, "communication")]),
            "game_management": star_rating([trait_value(head, "scheme_balance"), personality_value(head, "adaptability")]),
        }
        ratings[team["id"]] = CoachRating(
            id=stable_id("save_coach_rating", team["id"], head.get("name")),
            team_id=team["id"],
            coach_name=head.get("name") or "Save Staff Head Coach",
            ratings={key: round(value, 2) for key, value in values.items()},
            confidence=0.5,
            source_ids=["src_gameplay_staff_seed_v1"],
            notes="Save-state coach rating from mutable gameplay staff slots.",
        )
    return ratings


def align_real_head_coach_names(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    real_heads = {
        staff["team_id"]: staff["name"]
        for staff in canonical.get("staff_profiles", [])
        if staff.get("role") == "head_coach" and staff.get("name")
    }
    for slot in save.get("staff_slots", []):
        if slot.get("slot") != "head_coach":
            continue
        if not should_align_head_coach_slot(slot):
            continue
        real_name = real_heads.get(slot.get("team_id"))
        if real_name and slot.get("name") != real_name:
            previous = slot.get("name")
            slot["name"] = real_name
            slot["status"] = "real_head_coach_name_gameplay_profile"
            slot["notes"] = (
                f"{slot.get('notes', '')} Display name aligned to real head coach {real_name}; "
                f"gameplay ratings/archetype remain deterministic ({previous})."
            ).strip()
        if real_name:
            apply_head_coach_reputation(slot, real_name)
            from .staff import ensure_star_workload
            ensure_star_workload(slot)


def should_align_head_coach_slot(slot: dict[str, Any]) -> bool:
    if slot.get("market_status") != "employed":
        return False
    if slot.get("team_id") != slot.get("original_team_id"):
        return False
    return str(slot.get("status") or "") in {
        "fictional_gameplay_scaffold",
        "real_head_coach_name_gameplay_profile",
    }


def backfill_contract_metadata(contract: dict[str, Any], active_season: str) -> None:
    if not contract:
        return
    seasons = sorted(
        str(entry.get("season"))
        for entry in contract.get("seasons", [])
        if entry.get("season")
    )
    if not seasons:
        return
    if contract.get("original_contract_years"):
        try:
            contract["original_contract_years"] = int(contract.get("original_contract_years") or 0)
        except (TypeError, ValueError):
            contract["original_contract_years"] = len(seasons)
        return
    active_start = season_start_year(active_season)
    remaining = len([season for season in seasons if season_start_year(season) >= active_start])
    status = str(contract.get("status") or contract.get("contract_type") or "").lower()
    notes = str(contract.get("notes") or "")
    salaries = [
        float(entry.get("salary") or 0.0)
        for entry in contract.get("seasons", [])
        if entry.get("salary") is not None
    ]
    max_salary = max(salaries or [0.0])
    one_year_markers = {"one_year", "minimum", "two_way", "training_camp", "10_day"}
    if any(marker in status for marker in one_year_markers):
        inferred = max(1, len(seasons))
    elif len(seasons) >= 3:
        inferred = len(seasons)
    elif remaining == 2:
        inferred = 3
    elif remaining == 1 and (max_salary >= 8_000_000 or any((entry.get("option_type") for entry in contract.get("seasons", [])))):
        inferred = 3
    else:
        inferred = max(1, len(seasons))
    contract["original_contract_years"] = int(inferred)
    contract.setdefault("extension_eligibility", {})
    if "inferred original term" not in notes.lower():
        contract["notes"] = (
            f"{notes} Inferred original term as {inferred} year(s) for save-state extension eligibility; "
            "low confidence when public signing metadata is unavailable."
        ).strip()


def mark_expired_or_used_pick(pick: dict[str, Any], save: dict[str, Any], active_season: str) -> None:
    if not pick:
        return
    used_ids = {selection.get("pick_id") for selection in save.get("draft_state", {}).get("selections", []) if selection.get("pick_id")}
    used_ids.update(selection.get("pick_id") for selection in save.get("pending_draft_selections", []) if selection.get("pick_id"))
    if pick.get("id") in used_ids:
        pick["status"] = "used_draft_pick"
        pick["current_owner_team_id"] = None
        return
    pick_season = str(pick.get("season") or pick.get("draft_year") or "")
    pick_start = season_start_year(pick_season) if pick_season else None
    active_start = season_start_year(active_season)
    current_date = str(save.get("state", {}).get("current_date") or "")
    past_completed_draft = bool(pick_start and pick_start == active_start and current_date >= f"{pick_start}-07-01")
    if pick_start and (pick_start < active_start or past_completed_draft):
        pick["status"] = "expired_draft_pick"
        pick["current_owner_team_id"] = None


def apply_saved_draft_order_to_pick(pick: dict[str, Any], save: dict[str, Any]) -> None:
    if not pick or pick.get("status") in {"used_draft_pick", "expired_draft_pick"}:
        return
    year = str(pick.get("draft_year") or season_end_year(str(pick.get("season") or save.get("meta", {}).get("season") or CANONICAL_SEASON)))
    order = ((save.get("draft_orders") or {}).get(year) or {}).get("draft_order") or []
    for item in order:
        if (item.get("pick_id") or item.get("id")) != pick.get("id"):
            continue
        pick["overall_pick"] = item.get("overall_pick")
        pick["round"] = item.get("round") or pick.get("round")
        pick["pick_in_round"] = item.get("pick_in_round") or pick.get("pick_in_round")
        pick["lottery_order_team_id"] = item.get("team_id") or item.get("original_team_id")
        owner = item.get("owner_team_id") or item.get("current_owner_team_id")
        if owner:
            pick["current_owner_team_id"] = owner
        return


def apply_effective_player_ages(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    active_season = save_active_contract_season(save)
    try:
        year_delta = max(0, season_start_year(active_season) - season_start_year(CANONICAL_SEASON))
    except (TypeError, ValueError):
        year_delta = int(save.get("meta", {}).get("season_index") or 0)
    if year_delta <= 0:
        for player in canonical.get("players", []):
            try:
                base_age = player.get("age_base_value")
                if base_age is None:
                    base_age = player.get("_base_age")
                if base_age is None:
                    base_age = player.get("age")
                if base_age is not None:
                    player["age_base_value"] = base_age
                    player["_base_age"] = base_age
                player["age"] = base_age
                player["display_age"] = None if float(base_age or 0) <= 0 else base_age
            except (TypeError, ValueError):
                player["display_age"] = None
        return
    for player in canonical.get("players", []):
        base_age = player.get("age_base_value")
        if base_age is None:
            base_age = player.get("_base_age")
        if base_age is None:
            base_age = player.get("age")
        if base_age is None:
            player["display_age"] = None
            continue
        try:
            if float(base_age) <= 0:
                player["display_age"] = None
                continue
            player["age_base_value"] = base_age
            player["_base_age"] = base_age
            base_start = int(player.get("age_base_start_year") or season_start_year(str(player.get("age_base_season") or CANONICAL_SEASON)))
            if player.get("draft_year"):
                base_start = max(base_start, int(player.get("draft_year") or base_start))
            player_delta = max(0, season_start_year(active_season) - base_start)
            player["age"] = round(float(base_age) + player_delta, 1)
            player["display_age"] = player["age"]
        except (TypeError, ValueError):
            player["display_age"] = None


def seed_morale_if_flat(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    team_values = [tuple(sorted((morale or {}).items())) for morale in save.get("team_morale", {}).values()]
    player_values = [tuple(sorted((morale or {}).items())) for morale in save.get("player_morale", {}).values()]
    if len(set(team_values)) <= 2:
        save["team_morale"] = initial_team_morale(canonical)
    if len(set(player_values)) <= 4:
        save["player_morale"] = initial_player_morale(canonical)


def trait_value(staff: dict[str, Any], key: str) -> float:
    return float((staff.get("skill_traits") or {}).get(key) or staff_grade(staff) or 60.0)


def personality_value(staff: dict[str, Any], key: str) -> float:
    return float((staff.get("personality_traits") or {}).get(key) or 60.0)


def star_rating(values: list[float]) -> float:
    clean = [value for value in values if value is not None]
    return clamp(sum(clean) / max(1, len(clean)) / 20.0, 0.0, 5.0)


def initial_team_records(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {team["id"]: empty_team_record(team) for team in canonical.get("teams", [])}


def empty_team_record(team: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_id": team["id"],
        "team_abbrev": team["abbrev"],
        "wins": 0,
        "losses": 0,
        "home_wins": 0,
        "home_losses": 0,
        "away_wins": 0,
        "away_losses": 0,
        "points_for": 0.0,
        "points_against": 0.0,
        "last_game_id": None,
    }


def apply_development_events(canonical: dict[str, Any], events: list[dict[str, Any]]) -> None:
    """Apply development events through whichever ratings model the active universe uses."""
    from .ratings_model import apply_development, uses_inputs_model
    if uses_inputs_model(canonical):
        apply_development(canonical, None, events)
    else:
        apply_development_events_to_traits(canonical, events)


def apply_development_events_to_traits(canonical: dict[str, Any], events: list[dict[str, Any]]) -> None:
    deltas: dict[tuple[str, str], float] = {}
    for event in events:
        for trait_key, delta in (event.get("trait_deltas") or {}).items():
            key = (event.get("player_id"), trait_key)
            deltas[key] = deltas.get(key, 0.0) + float(delta)
    if not deltas:
        return
    for trait in canonical.get("traits", []):
        key = (trait.get("player_id"), trait.get("trait_key"))
        if key in deltas:
            current_value = trait.get("value")
            trait["value"] = round(clamp(float(current_value if current_value is not None else 50.0) + deltas[key], 0, 100), 3)
            trait["notes"] = f"{trait.get('notes', '')} Save-state development deltas applied.".strip()
    canonical.pop("_trait_values_by_player", None)


def apply_development_trait_totals_to_traits(canonical: dict[str, Any], totals: dict[str, dict[str, float]]) -> None:
    """Apply compact prior-season development accumulated by the history store."""
    if not totals:
        return
    for trait in canonical.get("traits", []):
        delta = (totals.get(str(trait.get("player_id"))) or {}).get(str(trait.get("trait_key")))
        if delta is None:
            continue
        current_value = trait.get("value")
        trait["value"] = round(clamp(float(current_value if current_value is not None else 50.0) + float(delta), 0, 100), 3)
        trait["notes"] = f"{trait.get('notes', '')} Materialized save development applied.".strip()
    canonical.pop("_trait_values_by_player", None)


def apply_materialized_development_to_traits(
    canonical: dict[str, Any],
    totals: dict[str, dict[str, float]],
    events: list[dict[str, Any]],
) -> None:
    """Apply archived and hot development as one delta, matching legacy saves."""
    combined = {
        str(player_id): {str(key): float(value or 0.0) for key, value in values.items()}
        for player_id, values in totals.items()
    }
    for event in events:
        player_id = str(event.get("player_id") or "")
        if not player_id:
            continue
        player_totals = combined.setdefault(player_id, {})
        for key, delta in (event.get("trait_deltas") or {}).items():
            player_totals[str(key)] = float(player_totals.get(str(key)) or 0.0) + float(delta or 0.0)
    apply_development_trait_totals_to_traits(canonical, combined)


_SLOT_BITS = tuple((slot, 1 << slot) for slot in range(5))
_SLOT_ROW_FIELDS = ("overall", "creation", "create", "passing", "spacing", "shooting", "defense", "rebounding",
                    "rebound", "rim_protection", "rim_deterrence")
_SLOT_ROWS: dict[tuple[Any, ...], tuple[tuple[float, ...], tuple[bool, ...]]] = {}


def _slot_score_row(player: dict[str, Any], attrs: dict[str, Any]) -> tuple[tuple[float, ...], tuple[bool, ...]]:
    """starting_slot_score(player, slot, 0, attrs) for slots 1-5 and whether the position fits each slot.

    Remembered by every input those two read: position, height fields and the listed summary fields."""
    key = (player.get("position"), player.get("height_inches"), player.get("height"),
           *(attrs.get(field) for field in _SLOT_ROW_FIELDS))
    try:
        row = _SLOT_ROWS.get(key)
    except TypeError:  # an unhashable input: compute without remembering
        key, row = None, None
    if row is None:
        tokens = player_position_tokens(player)
        row = (tuple(starting_slot_score(player, str(slot + 1), 0, attrs) for slot in range(5)),
               tuple(any(token in STARTING_FIVE_SLOT_FITS[str(slot + 1)] for token in tokens) for slot in range(5)))
        if key is not None:
            if len(_SLOT_ROWS) >= 50_000:
                _SLOT_ROWS.clear()
            _SLOT_ROWS[key] = row
    return row


def ai_role_targets(
    canonical: dict[str, Any], roster: list[dict[str, Any]], priors: dict[str, float],
    *, opening_workloads: dict[str, float] | None = None, newcomers: frozenset[str] | set[str] = frozenset(),
    star_workload: float = 0.0,
) -> tuple[dict[str, float], list[str]]:
    """Build a healthy two-deep rotation from current, workload-neutral skills."""
    attrs = {p["id"]: player_attribute_summary(canonical, p["id"]) for p in roster}
    quality = {p["id"]: attrs[p["id"]]["overall"] + min(32, max(0, float(priors.get(p["id"], 0)))) * .05 for p in roster}
    remaining = sorted(roster, key=lambda p: p["id"])
    groups = []
    for _ in range(2):
        # Five-slot assignment is a tiny exact DP, not roster permutations. Masks are kept in the order they
        # were first reached (the order a dict would iterate them), each player extends a snapshot of the
        # states, and a state is replaced only by a strictly better total, so ties resolve as they always have.
        order = [0]
        best_score: list[float | None] = [None] * 32
        best_assignment: list[tuple[str, ...] | None] = [None] * 32
        best_score[0], best_assignment[0] = 0.0, ("",) * 5
        for player in remaining:
            pid = player["id"]
            q = quality[pid] * .66
            base, fits = _slot_score_row(player, attrs[pid])
            scores = [base[slot] + q for slot in range(5)]
            for slot in range(5):
                if not fits[slot]:
                    scores[slot] -= 1_000
            for mask, score, assignment in [(m, best_score[m], best_assignment[m]) for m in order]:
                for slot, bit in _SLOT_BITS:
                    if mask & bit:
                        continue
                    new_mask = mask | bit
                    total = score + scores[slot]
                    previous = best_score[new_mask]
                    if previous is None:
                        order.append(new_mask)
                    elif not total > previous:
                        continue
                    best_score[new_mask] = total
                    best_assignment[new_mask] = assignment[:slot] + (pid,) + assignment[slot + 1:]
        full_mask = max(order, key=lambda mask: (mask.bit_count(), best_score[mask]))
        assignment = best_assignment[full_mask]
        groups.append(assignment)
        chosen = set(assignment) - {""}
        remaining = [p for p in remaining if p["id"] not in chosen]
    selected = [pid for group in groups for pid in group if pid]
    if opening_workloads is not None:
        return ai_coach_workloads(attrs, groups[0], opening_workloads, newcomers, star_workload), selected
    desired = {p["id"]: 0.0 for p in roster}
    for first, second in zip(*groups):
        if first and second:
            lead = clamp(24 + (quality[first] - quality[second]) * .6, 18, 36)
            desired[first], desired[second] = lead, 48 - lead
        elif first or second:
            desired[first or second] = 42
    targets = bounded_minutes_allocation([
        {"player_id": pid, "desired": desired[pid], "minimum": 0, "maximum": 42 if pid in selected else 0}
        for pid in desired
    ], 240)
    return targets, selected


# Newcomer talent line (ROT-OUTLIERS, 2026-11-19): the ninth-best overall among the coach's thirteen leading
# candidates, less a two-point margin; each point a newcomer falls below it costs two priority points. Measured
# against Basketball Index healthy-rotation minutes over two healthy seasons (docs/agents/tasks/rot-outliers.md).
ROTATION_TALENT_POOL = 13
ROTATION_TALENT_LINE_RANK = 9
ROTATION_TALENT_MARGIN = 2.0
ROTATION_TALENT_PENALTY = 2.0


def carried_workload_earned_elsewhere(player: dict[str, Any], team_abbrev: str | None) -> bool:
    """True when a player's carried-over minutes (his season before the game's start) came with other teams."""
    from .career_stats import career_record
    from .research import ESPN_TEAM_ID_TO_ABBREV
    year = season_start_year(CANONICAL_SEASON) - 1
    label = f"{year}-{(year + 1) % 100:02d}"
    for row in career_record(player).get("seasons") or []:
        if row.get("season") == label:
            teams = {ESPN_TEAM_ID_TO_ABBREV.get(str(team)) for team in row.get("team_ids") or []} - {None}
            return bool(teams) and team_abbrev not in teams
    return False


def ai_coach_workloads(
    attrs: dict[str, dict[str, float]], starters: tuple[str, ...], opening_workloads: dict[str, float],
    newcomers: frozenset[str] | set[str] = frozenset(), star_workload: float = 0.0,
) -> dict[str, float]:
    """Plan a team's minutes across positions, with short stints for the tail.

    The head coach's star workload (minutes, staff.coach_star_workload) moves his two best players' plan up or down
    and his third player's by half as much; the next three rotation players give or take the difference."""
    # Workload history supplies role context alongside current quality, creation
    # and stamina. The depth chart supplies positional coverage without setting
    # aside a large block of minutes for a dedicated backup at each position.
    def priority(pid: str) -> float:
        player = attrs[pid]
        return (opening_workloads[pid] + .35 * player["overall"] + .26 * player["creation"]
                + .48 * player["stamina"])

    # A newcomer's carried-over workload was earned behind another team's depth
    # chart. It must not lift him into rotation minutes here when he is clearly
    # weaker than this rotation. Incumbents keep their workload context: their
    # own coach chose that role with much of the same roster.
    candidates = sorted(attrs, key=lambda pid: (-priority(pid), pid))[:ROTATION_TALENT_POOL]
    pool = sorted((attrs[pid]["overall"] for pid in candidates), reverse=True)
    line = pool[min(ROTATION_TALENT_LINE_RANK, len(pool)) - 1] - ROTATION_TALENT_MARGIN if pool else 0.0

    def guarded(pid: str) -> float:
        if pid not in newcomers:
            return priority(pid)
        shortfall = max(0.0, line - attrs[pid]["overall"])
        return priority(pid) - min(opening_workloads[pid], ROTATION_TALENT_PENALTY * shortfall)

    order = sorted(attrs, key=lambda pid: (-guarded(pid), pid))
    curve = star_workload_curve(star_workload)
    desired = dict.fromkeys(order, 0.0)
    desired.update(zip(order, curve))
    for pid in starters:
        if pid:
            desired[pid] = max(4, desired[pid])
    return desired


# An average coach's healthy plan by rotation rank. SMART-MINUTES (2026-11-19) moved 2.3 minutes from the top three to
# ranks 6-8: the old top (37/34/32) was set while absent players' minutes went almost all to the bench; with the
# real share now going to the other starters, the old top put 21-27 players at 34+ minutes (real 2025-26: 18).
AI_ROTATION_CURVE = (36.0, 33.2, 31.5, 30, 28, 26.0, 21.0, 16.3, 10, 5, 2, 1)
# The star-workload shift by rotation rank, and who gives it back (sums to zero), times the coach's star workload
# (minutes) times STAR_WORKLOAD_GAIN. The gain is below 1 because the measured trait is season minutes, which also
# carry the coach's fill-in lean and his players' absences.
STAR_WORKLOAD_SHIFT = (1.0, 1.0, 0.5, 0.0, 0.0, -1.0, -0.9, -0.6)
STAR_WORKLOAD_GAIN = 1.25


def star_workload_curve(star_workload: float = 0.0) -> tuple[float, ...]:
    if not star_workload:
        return AI_ROTATION_CURVE
    shift = STAR_WORKLOAD_SHIFT + (0.0,) * (len(AI_ROTATION_CURVE) - len(STAR_WORKLOAD_SHIFT))
    return tuple(max(0.0, base + STAR_WORKLOAD_GAIN * float(star_workload) * s)
                 for base, s in zip(AI_ROTATION_CURVE, shift))


def team_head_coach(save: dict[str, Any], team_id: str | None) -> dict[str, Any] | None:
    return next((slot for slot in save.get("staff_slots") or []
                 if slot.get("team_id") == team_id and slot.get("slot") == "head_coach"), None)


def reassess_ai_roles(active: dict[str, Any], save: dict[str, Any], stamp: str, *, calendar: bool = True) -> list[str]:
    """Commit roles on simulation dates, never on a read/refresh path."""
    protected = human_controlled_team_ids(save) | {
        team for team, override in (save.get("rotation_overrides") or {}).items() if override
    }
    rosters: dict[str, list[dict[str, Any]]] = {}
    for player in active.get("players", []):
        team = player.get("team_id")
        if team and team not in protected and not player.get("_inactive_player"):
            rosters.setdefault(team, []).append(player)
    clocks = save.get("ai_role_state") or {}
    due = []
    for team, roster in sorted(rosters.items()):
        if len(roster) < 6:
            continue
        signature = hashlib.sha256(json.dumps(sorted((p["id"], p.get("position") or "") for p in roster)).encode()).hexdigest()
        clock = clocks.get(team) or {}
        if clock.get("through_date", "") > stamp:
            continue
        if clock.get("version") != 1 or clock.get("roster_signature") != signature or (calendar and clock.get("period") != stamp[:7]):
            due.append((team, roster, signature))
    if not due:
        return []
    from .ratings_model import MODEL_KEY

    # Workload is part of headline OVR; do not let the old role grade itself.
    # Keep the active ratings model while rebuilding indexes for the neutral view.
    neutral = {key: value for key, value in active.items() if key == MODEL_KEY or not str(key).startswith("_")}
    neutral["players"] = [{**p, "minutes_projection": 24} for p in active["players"]]
    # This local, read-only view can own its indexes. Otherwise every player
    # summary rescans the whole league's traits during a role reassessment.
    neutral["_allow_internal_caches"] = True
    baselines = save.setdefault("rotation_baselines", {})
    clocks = save.setdefault("ai_role_state", {})
    season_year = int(stamp[:4]) - (stamp[5:7] < "07")
    canonical_year = season_start_year(CANONICAL_SEASON)
    abbrevs = {team["id"]: team.get("abbrev") for team in active.get("teams", [])}
    for team, roster, signature in due:
        priors = {p["id"]: max(0, float(baselines.get(p["id"], display_minutes_projection(p)) or 0)) for p in roster}
        workloads = {
            p["id"]: clamp(float(p.get("_rotation_role_prior", display_minutes_projection(p))), 0, 42)
            * clamp(1 - .25 * (season_year - int(p.get("age_base_start_year") or canonical_year)), 0.0, 1.0)
            for p in roster
        }
        newcomers = {p["id"] for p in roster if workloads[p["id"]] > 0
                     and carried_workload_earned_elsewhere(p, abbrevs.get(team))}
        from .staff import coach_star_workload
        targets, selected = ai_role_targets(neutral, roster, priors, opening_workloads=workloads, newcomers=newcomers,
                                            star_workload=coach_star_workload(team_head_coach(save, team)))
        total = sum(priors.values())
        blended = {
            pid: target * .8 + (priors[pid] * 240 / total if total else target) * .2
            for pid, target in targets.items() if target > 0
        }
        allocation = bounded_minutes_allocation([
            {"player_id": pid, "desired": blended.get(pid, 0), "minimum": 0, "maximum": 42 if pid in blended else 0}
            for pid in targets
        ], 240)
        baselines.update(round_minutes_to_total(allocation, 240))
        clocks[team] = {"version": 1, "through_date": stamp, "period": stamp[:7],
                        "roster_signature": signature, "rotation_player_ids": selected}
    return [team for team, _, _ in due]


def apply_save_rotation_projection(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    teams = {team["id"] for team in canonical.get("teams", [])}
    snapshots = save.setdefault("rotation_snapshots", {})
    health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
    baselines = save.setdefault("rotation_baselines", {})
    # OVR includes a workload bonus. Feeding the last projection back into
    # that bonus makes repeated refreshes drift even without a simulated day.
    for player in canonical.get("players", []):
        opening_workload = display_minutes_projection(player)
        player.setdefault("_rotation_role_prior", opening_workload)
        baseline = baselines.setdefault(player["id"], opening_workload)
        player["minutes_projection"] = float(baseline or 0.0)
    for team_id in sorted(teams):
        fills: dict[str, dict[str, float]] = {}
        projection = team_rotation_projection(canonical, save, team_id, integer=False, fill_out=fills)
        if not projection:
            continue
        # The coach's fill-in minutes for absent teammates; a game re-points them for its opponent (absence_fill).
        for player in canonical.get("players", []):
            if player.get("team_id") != team_id:
                continue
            fill = fills.get(player["id"])
            if fill:
                player["_absence_fill"], player["_fill_size"] = round(fill["minutes"], 2), round(fill["size"], 3)
            else:
                player.pop("_absence_fill", None)
                player.pop("_fill_size", None)
        snapshots[team_id] = {
            player_id: round(float(minutes), 2)
            for player_id, minutes in projection.items()
        }
        for player in canonical.get("players", []):
            if player.get("team_id") != team_id:
                continue
            baseline = float(baselines.get(player["id"], display_minutes_projection(player)) or 0.0)
            unavailable = player_unavailable_for_rotation(health_by_player.get(player["id"]))
            player.pop("_trade_value_unavailable", None)
            player.pop("_trade_value_minutes_projection", None)
            if unavailable:
                player["_trade_value_unavailable"] = True
                player["_trade_value_minutes_projection"] = round(clamp(baseline, 0.0, 42.0), 2)
            minutes = float(projection.get(player["id"], 0.0))
            player["minutes_projection"] = round(minutes, 2)
            rec = (save.get("rotation_recommendations") or {}).get(player["id"])
            if rec:
                player["rotation_note"] = (
                    f"GM {float(rec.get('target_minutes') or 0):.0f} MPG; "
                    f"coach rotation {minutes:.0f} MPG."
                )


def team_rotation_projection(canonical: dict[str, Any], save: dict[str, Any], team_id: str | None, integer: bool = False,
                             fill_out: dict[str, dict[str, float]] | None = None) -> dict[str, float]:
    if not team_id:
        return {}
    roster = [player for player in canonical.get("players", []) if player.get("team_id") == team_id]
    if not roster:
        return {}
    health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
    user_override = (save.get("rotation_overrides") or {}).get(team_id)
    if isinstance(user_override, dict) and user_override:
        projection = user_rotation_override_projection(roster, health_by_player, user_override,
                                                       canonical=canonical, save=save, team_id=team_id, fill_out=fill_out)
        return projection if integer else {player_id: float(value) for player_id, value in projection.items()}
    recommendations = save.get("rotation_recommendations") or {}
    baselines = save.get("rotation_baselines") or {}
    ai_role = (save.get("ai_role_state") or {}).get(team_id) if team_id not in human_controlled_team_ids(save) else None
    if ai_role and ai_role.get("version") != 1:
        ai_role = None
    active_season = str((save.get("meta") or {}).get("season") or save_active_contract_season(save))
    try:
        active_start_year = int(active_season[:4])
    except (TypeError, ValueError):
        active_start_year = 0
    rows: list[dict[str, Any]] = []
    for player in roster:
        baseline = float(baselines.get(player["id"], display_minutes_projection(player)) or 0.0)
        baseline = clamp(baseline, 0.0, 42.0)
        attrs = player_attribute_summary(canonical, player["id"])
        overall = float(attrs.get("overall") or 50.0)
        unavailable = player_unavailable_for_rotation(health_by_player.get(player["id"]))
        rec = recommendations.get(player["id"])
        rookie_pick = int(player.get("draft_pick") or 0)
        first_season_rookie = (
            player.get("source_kind") == "generated_rookie"
            and int(player.get("age_base_start_year") or 0) == active_start_year
        )
        raw_score = baseline * 1.35 + overall * 0.46 + max(0.0, float(player.get("age") or 27.0) - 32.0) * -0.7
        rows.append(
            {
                "player": player,
                "attrs": attrs,
                "baseline": baseline,
                "overall": overall,
                "unavailable": unavailable,
                "recommendation": rec,
                "rookie_pick": rookie_pick,
                "first_season_rookie": first_season_rookie,
                "score": raw_score,
            }
        )
    available = [row for row in rows if not row["unavailable"]]
    if not available:
        return {row["player"]["id"]: 0.0 for row in rows}
    if ai_role and len(available) == 5:
        available_ids = {row["player"]["id"] for row in available}
        return {row["player"]["id"]: 48.0 if row["player"]["id"] in available_ids else 0.0 for row in rows}
    available.sort(key=lambda row: (row["score"], row["baseline"], row["overall"], row["player"].get("name", "")), reverse=True)
    desired_count = min(len(available), max(9, min(11, sum(1 for row in available if row["baseline"] >= 8.0))))
    selected_ids = {row["player"]["id"] for row in available[:desired_count]}
    if ai_role:
        selected_ids.update(row["player"]["id"] for row in available if row["baseline"] > 0)
    for row in available:
        rec = row.get("recommendation") or {}
        if float(rec.get("target_minutes") or 0.0) > 0 or (row.get("first_season_rookie") and 0 < int(row.get("rookie_pick") or 0) <= 10):
            selected_ids.add(row["player"]["id"])
    if len(selected_ids) < min(8, len(available)):
        selected_ids.update(row["player"]["id"] for row in available[: min(8, len(available))])
    allocation_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(available, start=1):
        player = row["player"]
        if player["id"] not in selected_ids:
            allocation_rows.append({"player_id": player["id"], "desired": 0.0, "minimum": 0.0, "maximum": 0.0})
            continue
        desired = row["baseline"] ** 1.08 * (0.74 + row["overall"] / 155.0)
        rec = row.get("recommendation") or {}
        if rec:
            requested = clamp(float(rec.get("target_minutes") or row["baseline"]), 0.0, 42.0)
            commitment = clamp(float(rec.get("coach_commitment") or 0.68), 0.0, 1.0)
            coach_adjustment = clamp((row["baseline"] - requested) * (1.0 - commitment), -3.0, 3.0)
            desired = requested + coach_adjustment
        maximum = rotation_rank_cap(rank, row["overall"], bool(rec))
        minimum = rotation_rank_floor(rank, row["baseline"], row["overall"])
        if ai_role and not rec:
            desired = row["baseline"] or (6.0 if len(selected_ids) <= 9 else 0.0)
            maximum = max(maximum, desired)
            minimum = min(minimum, desired)
            if len(available) <= 7:
                maximum = 42
        rookie_pick = int(row.get("rookie_pick") or 0)
        if row.get("first_season_rookie") and 0 < rookie_pick <= 10:
            rookie_floor = 20.0 if rookie_pick <= 5 else 17.0
            rookie_floor = min(row["baseline"], rookie_floor)
            maximum = max(maximum, rookie_floor)
            minimum = max(minimum, rookie_floor)
        if rec:
            minimum = max(0.0, min(minimum, desired - 4.0))
            maximum = max(maximum, desired + 4.0)
        allocation_rows.append(
            {
                "player_id": player["id"],
                "desired": clamp(desired, 0.0, maximum),
                "minimum": clamp(minimum, 0.0, maximum),
                "maximum": maximum,
            }
        )
    if any(row["unavailable"] for row in rows):
        fill_vacated_minutes(canonical, save, team_id, rows, allocation_rows, ai_role=bool(ai_role), fill_out=fill_out)
    allocation = bounded_minutes_allocation(allocation_rows, 240.0)
    row_limits = {row["player_id"]: row for row in allocation_rows}
    recommended_ids = {row["player"]["id"] for row in rows if row.get("recommendation")}
    for row in rows:
        rec = row.get("recommendation") or {}
        if not rec or row["unavailable"]:
            continue
        player_id = row["player"]["id"]
        requested = clamp(float(rec.get("target_minutes") or 0.0), 0.0, 42.0)
        if requested <= 0:
            continue
        floor = min(requested, float(row_limits.get(player_id, {}).get("maximum") or requested))
        deficit = floor - float(allocation.get(player_id) or 0.0)
        if deficit <= 0:
            continue
        donors = sorted(
            [
                (
                    donor_id,
                    max(0.0, float(value) - float(row_limits.get(donor_id, {}).get("minimum") or 0.0)),
                )
                for donor_id, value in allocation.items()
                if donor_id != player_id and donor_id not in recommended_ids
            ],
            key=lambda item: item[1],
            reverse=True,
        )
        for donor_id, available_minutes in donors:
            if deficit <= 0:
                break
            take = min(deficit, available_minutes)
            allocation[donor_id] = float(allocation.get(donor_id) or 0.0) - take
            allocation[player_id] = float(allocation.get(player_id) or 0.0) + take
            deficit -= take
    for row in rows:
        if row["unavailable"]:
            allocation[row["player"]["id"]] = 0.0
        else:
            allocation.setdefault(row["player"]["id"], 0.0)
    return round_minutes_to_total(allocation, 240) if integer else allocation


# Who plays an absent player's minutes (SMART-MINUTES, 2026-11-19; replaces HEAVY-MINUTES' bench-first curve). The
# coach's decision lives in absence_fill.coach_fill: like-for-like backups first (position, height and skills),
# the remaining starters a little, deep reserves when the rotation runs thin, weighed by the coach's value of each
# player, the team's phase and the head coach's star workload. Fitted to real 2025-26 games with a starter out.
def absence_fill_profile(row: dict[str, Any], healthy: float, cap: float = 42.0):
    from .absence_fill import profile_from_attrs
    return profile_from_attrs(row["player"], row.get("attrs") or {"overall": row.get("overall", 50.0)}, healthy,
                              cap=max(cap, healthy))


def fill_vacated_minutes(
    canonical: dict[str, Any], save: dict[str, Any], team_id: str | None, rows: list[dict[str, Any]],
    allocation_rows: list[dict[str, Any]], *, ai_role: bool, fill_out: dict[str, dict[str, float]] | None = None,
) -> None:
    """Raise the available players' desired minutes, in place, to play the minutes of the unavailable ones."""
    from .absence_fill import coach_fill, mark_starters
    from .staff import coach_star_workload
    by_id = {row["player_id"]: row for row in allocation_rows}
    available = [row for row in rows if not row["unavailable"] and row["player"]["id"] in by_id]
    healthy = {row["player"]["id"]: float(by_id[row["player"]["id"]]["desired"] or 0.0)
               if float(by_id[row["player"]["id"]]["maximum"] or 0.0) > 0 else 0.0 for row in available}
    absent_rows = [row for row in rows if row["unavailable"]]
    if ai_role:
        absent_minutes = {row["player"]["id"]: float(row["baseline"]) for row in absent_rows}
        vacated = 240.0 - sum(healthy.values())
    else:
        # The same desired-minutes scale the available players use, before the team total is set to 240.
        absent_minutes = {}
        for row in absent_rows:
            rec = row.get("recommendation") or {}
            if rec and float(rec.get("target_minutes") or 0.0) > 0:
                absent_minutes[row["player"]["id"]] = clamp(float(rec["target_minutes"]), 0.0, 42.0)
            elif row["baseline"] > 0:
                absent_minutes[row["player"]["id"]] = row["baseline"] ** 1.08 * (0.74 + row["overall"] / 155.0)
        vacated = sum(absent_minutes.values())
    absent = [absence_fill_profile(row, absent_minutes.get(row["player"]["id"], 0.0)) for row in absent_rows
              if absent_minutes.get(row["player"]["id"], 0.0) > 0]
    if vacated <= 0.5 or not absent:
        return
    candidates = [absence_fill_profile(row, healthy[row["player"]["id"]]) for row in available]
    mark_starters(candidates, absent)
    phase = ((save.get("team_plans") or {}).get(team_id) or {}).get("window_phase")
    coach = next((slot for slot in save.get("staff_slots") or []
                  if slot.get("team_id") == team_id and slot.get("slot") == "head_coach"), None)
    adds = coach_fill(absent, candidates, vacated, phase=phase, star_workload=coach_star_workload(coach))
    sizes = {p.pid: p.size for p in candidates}
    for pid, add in adds.items():
        if add <= 1e-6:
            continue
        row = by_id[pid]
        row["desired"] = healthy[pid] + add
        row["maximum"] = max(float(row["maximum"] or 0.0), row["desired"])
        row["minimum"] = min(float(row.get("minimum") or 0.0), row["desired"])
        if fill_out is not None and add > 0.05:
            fill_out[pid] = {"minutes": add, "size": sizes[pid]}


# A user who left a player at zero minutes benched him on purpose: the coach plays him only when fewer than this many
# players with minutes are available.
USER_FILL_MIN_ROTATION = 8


def user_rotation_override_projection(
    roster: list[dict[str, Any]],
    health_by_player: dict[str, dict[str, Any]],
    override: dict[str, Any],
    *,
    canonical: dict[str, Any] | None = None,
    save: dict[str, Any] | None = None,
    team_id: str | None = None,
    fill_out: dict[str, dict[str, float]] | None = None,
) -> dict[str, float]:
    """Honor saved user minutes, filling only time freed by unavailable players.

    A healthy player keeps the GM's minutes as his floor. The minutes of unavailable players are placed by the same
    coach decision the AI teams use (absence_fill), among the players the GM gave minutes to."""
    available = [
        player for player in roster
        if not player_unavailable_for_rotation(health_by_player.get(player["id"]))
    ]
    if canonical is not None:
        filled = user_override_coach_fill(canonical, save or {}, team_id, roster, available, override, fill_out)
        if filled is not None:
            return filled
    available_ids = {player["id"] for player in available}
    allocation = {
        player["id"]: (
            float(clamp(float(override.get(player["id"], 0.0) or 0.0), 0.0, 48.0))
            if player["id"] in available_ids
            else 0.0
        )
        for player in roster
    }
    total = sum(allocation.values())
    if total > 240.0:
        scale = 240.0 / total
        scaled = {player_id: int(value * scale) for player_id, value in allocation.items()}
        remaining_scaled = 240 - sum(scaled.values())
        for player_id in sorted(scaled, key=lambda item: allocation[item], reverse=True):
            if remaining_scaled <= 0:
                break
            if scaled[player_id] < 48:
                scaled[player_id] += 1
                remaining_scaled -= 1
        return {player_id: float(value) for player_id, value in scaled.items()}

    remaining = int(round(240.0 - total))
    ranked = sorted(
        available,
        key=lambda player: (
            float(override.get(player["id"], 0.0) or 0.0),
            display_minutes_projection(player),
            player.get("name", ""),
        ),
        reverse=True,
    )
    cursor = 0
    while remaining > 0 and ranked:
        player_id = ranked[cursor % len(ranked)]["id"]
        if allocation[player_id] < 48.0:
            allocation[player_id] += 1.0
            remaining -= 1
        cursor += 1
        if cursor > len(ranked) * 100:
            break
    return {player_id: float(round(value)) for player_id, value in allocation.items()}


def user_override_coach_fill(
    canonical: dict[str, Any], save: dict[str, Any], team_id: str | None, roster: list[dict[str, Any]],
    available: list[dict[str, Any]], override: dict[str, Any], fill_out: dict[str, dict[str, float]] | None,
) -> dict[str, float] | None:
    """Whole-minute plan: GM targets for the healthy players plus the coach's placement of the missing minutes.

    None when nobody the GM gave minutes to is out (the plain override path then applies)."""
    from .absence_fill import coach_fill, mark_starters, profile_from_attrs
    from .staff import coach_star_workload

    def target(player: dict[str, Any]) -> float:
        return float(clamp(float(override.get(player["id"], 0.0) or 0.0), 0.0, 48.0))

    available_ids = {player["id"] for player in available}
    absent_players = [p for p in roster if p["id"] not in available_ids and target(p) > 0]
    base = {p["id"]: target(p) for p in available}
    vacated = 240.0 - sum(base.values())
    if not absent_players or vacated <= 0.5:
        return None
    attrs = {p["id"]: player_attribute_summary(canonical, p["id"]) for p in roster}
    candidates = [profile_from_attrs(p, attrs[p["id"]], base[p["id"]], cap=max(42.0, base[p["id"]])) for p in available]
    absent = [profile_from_attrs(p, attrs[p["id"]], target(p)) for p in absent_players]
    mark_starters(candidates, absent)
    with_minutes = {p.pid for p in candidates if p.healthy > 0}
    eligible = with_minutes if len(with_minutes) >= USER_FILL_MIN_ROTATION else None
    phase = ((save.get("team_plans") or {}).get(team_id) or {}).get("window_phase")
    adds = coach_fill(absent, candidates, vacated, phase=phase, eligible=eligible,
                      star_workload=coach_star_workload(team_head_coach(save, team_id)))
    minutes = {p["id"]: 0.0 for p in roster}
    for pid, value in base.items():
        minutes[pid] = value + adds.get(pid, 0.0)
    if fill_out is not None:
        sizes = {p.pid: p.size for p in candidates}
        fill_out.update({pid: {"minutes": add, "size": sizes[pid]} for pid, add in adds.items() if add > 0.05})
    # Whole minutes summing to 240, never below a healthy player's GM target.
    whole = {pid: math.floor(value + 1e-9) for pid, value in minutes.items()}
    short = 240 - sum(whole.values())
    for pid in sorted(minutes, key=lambda pid: (-(minutes[pid] - whole[pid]), pid)):
        if short <= 0:
            break
        if whole[pid] < 48 and pid in available_ids:
            whole[pid] += 1
            short -= 1
    return {pid: float(value) for pid, value in whole.items()}


def player_unavailable_for_rotation(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    if state.get("rest_shutdown") or state.get("rest_game_id") or state.get("user_rest"):
        return True   # the coach rests him tonight or has shut him down (the day's health pass), or the GM rests him
    status = str(state.get("availability_status") or "active").lower()
    if status in {"", "active", "healthy"} and not state.get("current_injury_id"):
        return False
    days_left = float(state.get("days_left") or state.get("expected_days_remaining") or 0.0)
    return bool(state.get("current_injury_id") or days_left > 0 or status in {"out", "injured", "unavailable"})


def rotation_rank_cap(rank: int, overall: float, recommended: bool = False) -> float:
    if recommended:
        return 42.0
    if rank <= 1:
        return 40.0 if overall >= 75 else 38.0
    if rank <= 2:
        return 38.0
    if rank <= 3:
        return 36.0
    if rank <= 5:
        return 34.0
    if rank <= 7:
        return 28.0
    if rank <= 9:
        return 20.0
    if rank <= 11:
        return 12.0
    return 6.0


def rotation_rank_floor(rank: int, baseline: float, overall: float) -> float:
    if rank <= 2 and (baseline >= 24 or overall >= 68):
        return min(31.0, max(26.0, baseline * 0.78))
    if rank <= 5 and (baseline >= 18 or overall >= 61):
        return min(24.0, max(16.0, baseline * 0.65))
    if rank <= 8 and baseline >= 12:
        return min(14.0, baseline * 0.55)
    return 0.0


def bounded_minutes_allocation(rows: list[dict[str, Any]], total: float) -> dict[str, float]:
    active = [row for row in rows if float(row.get("maximum") or 0.0) > 0.0]
    allocation = {row["player_id"]: 0.0 for row in rows}
    if not active:
        return allocation
    fixed: set[str] = set()
    for _ in range(12):
        remaining_total = total - sum(allocation[player_id] for player_id in fixed)
        flexible = [row for row in active if row["player_id"] not in fixed]
        if not flexible:
            break
        desired_total = sum(max(0.01, float(row.get("desired") or 0.0)) for row in flexible)
        scale = remaining_total / desired_total if desired_total else 0.0
        changed = False
        for row in flexible:
            value = float(row.get("desired") or 0.0) * scale
            clamped = clamp(value, float(row.get("minimum") or 0.0), float(row.get("maximum") or 0.0))
            allocation[row["player_id"]] = clamped
            if abs(clamped - value) > 0.001:
                fixed.add(row["player_id"])
                changed = True
        if not changed:
            break
    current = sum(allocation.values())
    if current > 0:
        diff = total - current
        flexible = [
            row for row in active
            if allocation[row["player_id"]] < float(row.get("maximum") or 0.0) - 0.01
        ]
        if flexible:
            weight_total = sum(max(1.0, allocation[row["player_id"]]) for row in flexible)
            for row in flexible:
                allocation[row["player_id"]] += diff * (max(1.0, allocation[row["player_id"]]) / weight_total)
    return {player_id: round(clamp(minutes, 0.0, 42.0), 2) for player_id, minutes in allocation.items()}


def round_minutes_to_total(minutes_by_player: dict[str, float], total: int = 240) -> dict[str, float]:
    rounded = {player_id: int(round(minutes)) for player_id, minutes in minutes_by_player.items()}
    diff = int(total - sum(rounded.values()))
    if diff == 0:
        return {player_id: float(value) for player_id, value in rounded.items()}
    ordered = sorted(
        minutes_by_player,
        key=lambda player_id: (minutes_by_player[player_id] - int(minutes_by_player[player_id]), minutes_by_player[player_id], player_id),
        reverse=diff > 0,
    )
    idx = 0
    while diff and ordered:
        player_id = ordered[idx % len(ordered)]
        if diff > 0 and rounded[player_id] < 42:
            rounded[player_id] += 1
            diff -= 1
        elif diff < 0 and rounded[player_id] > 0:
            rounded[player_id] -= 1
            diff += 1
        idx += 1
        if idx > len(ordered) * 50:
            break
    return {player_id: float(value) for player_id, value in rounded.items()}


def normalize_team_minutes_after_recommendations(canonical: dict[str, Any], recommendations: dict[str, Any]) -> None:
    # Backward-compatible shim for older callers; the save-aware allocator now handles all teams.
    affected_teams = {
        player.get("team_id")
        for player in canonical.get("players", [])
        if player.get("id") in recommendations and player.get("team_id")
    }
    for team_id in affected_teams:
        roster = [player for player in canonical.get("players", []) if player.get("team_id") == team_id]
        total = sum(display_minutes_projection(player) for player in roster)
        if total <= 0:
            continue
        for player in roster:
            player["minutes_projection"] = round(clamp(display_minutes_projection(player) * 240.0 / total, 0.0, 42.0), 2)


def development_months_between(current: str, target: str) -> list[str]:
    months: list[str] = []
    cursor = parse_date(current).replace(day=1)
    target_day = parse_date(target)
    cursor = add_month(cursor)
    while cursor <= target_day:
        months.append(cursor.strftime("%Y-%m"))
        cursor = add_month(cursor)
    return months


def add_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def pending_counts(save: dict[str, Any]) -> dict[str, int]:
    from .transactions import trade_offer_fingerprint

    pending_user_offers = [
        item for item in save.get("user_trade_offers", [])
        if (item.get("offer_context") or {}).get("status") == "pending_user_review"
    ]
    return {
        "trades": len(save.get("pending_trade_proposals", [])),
        "contracts": len(save.get("pending_contract_negotiations", [])),
        "draft": len(save.get("pending_draft_selections", [])),
        "staff": len([item for item in save.get("staff_retention_windows", []) if item.get("status") == "pending_user_decision"]),
        "user_trade_offers": len({trade_offer_fingerprint(item) for item in pending_user_offers}),
        "cutdowns": len(save.get("pending_roster_cutdowns", [])),
        "ai_actions": len([item for item in save.get("pending_ai_actions", []) if ai_action_is_visible(item)]),
    }


def ai_action_is_visible(action: dict[str, Any]) -> bool:
    if action.get("status") in {"processed", "executed", "rejected"}:
        return False
    payload = action.get("payload") or {}
    if action.get("action_type") == "trade_recommendations":
        return any(
            proposal.get("accepted_by_all") and (proposal.get("legality") or {}).get("status") == "legal"
            for proposal in payload.get("proposals", [])
        )
    if action.get("action_type") == "free_agency_recommendations":
        return any(negotiation_has_positive_accepted_offer(item) for item in payload.get("negotiations", []))
    if action.get("action_type") == "staff_change_recommendations":
        return False
    return True


def next_team_games(
    root: str | Path,
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    limit: int = 5,
    *,
    include_current: bool = False,
) -> list[dict[str, Any]]:
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    team_by_espn = espn_team_id_map(canonical)
    espn_by_team = {team["id"]: espn_id for espn_id, team in team_by_espn.items()}
    team_espn = espn_by_team.get(team_id)
    games = []
    for game in schedule_for_save(root, save):
        if game.get("gameDate", "") < current or (game.get("gameDate", "") == current and not include_current):
            continue
        if str(game.get("homeTeamId")) != team_espn and str(game.get("awayTeamId")) != team_espn:
            continue
        home = team_by_espn.get(str(game.get("homeTeamId")), {})
        away = team_by_espn.get(str(game.get("awayTeamId")), {})
        is_home = str(game.get("homeTeamId")) == team_espn
        opponent = away if is_home else home
        games.append(
            {
                "game_id": str(game.get("externalGameId")),
                "date": game.get("gameDate"),
                "away_team": away.get("abbrev"),
                "home_team": home.get("abbrev"),
                "away_team_id": away.get("id"),
                "home_team_id": home.get("id"),
                "opponent_team_id": opponent.get("id"),
                "opponent_team": opponent.get("abbrev"),
                "is_home": is_home,
            }
        )
        if len(games) >= limit:
            break
    return games


def health_summary(states: list[dict[str, Any]]) -> dict[str, Any]:
    out = [state for state in states if state.get("availability_status") != "active"]
    fatigue_values = [float(state.get("fatigue") or 0.0) for state in states]
    return {
        "player_count": len(states),
        "unavailable_count": len(out),
        "average_fatigue": round(sum(fatigue_values) / max(1, len(fatigue_values)), 2),
        "unavailable_player_ids": [state.get("player_id") for state in out],
    }


def display_minutes_projection(player: dict[str, Any]) -> float:
    minutes = float(player.get("minutes_projection") or 0.0)
    if minutes > 80:
        minutes = minutes / 82.0
    return round(clamp(minutes, 0.0, 42.0), 1)


def per_game_stat(totals: dict[str, Any], stat: str) -> float:
    games = max(1, int(totals.get("games") or 0))
    return round(float(totals.get(stat) or 0.0) / games, 1) if totals else 0.0


def percentage_stat(totals: dict[str, Any], made_key: str, attempt_key: str) -> float | None:
    attempts = float((totals or {}).get(attempt_key) or 0.0)
    if attempts <= 0:
        return None
    return round(float((totals or {}).get(made_key) or 0.0) / attempts * 100.0, 1)


def trait_values_by_player(canonical: dict[str, Any]) -> dict[str, dict[str, float]]:
    cached = canonical.get("_trait_values_by_player")
    if isinstance(cached, dict):
        return cached
    values: dict[str, dict[str, float]] = {}
    for trait in canonical.get("traits", []):
        player_id = trait.get("player_id")
        trait_key = trait.get("trait_key")
        if not player_id or not trait_key:
            continue
        value = trait.get("value")
        values.setdefault(player_id, {})[trait_key] = float(value if value is not None else 50.0)
    if canonical.get("_allow_internal_caches"):
        canonical["_trait_values_by_player"] = values
    return values


def players_by_id_index(canonical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cached = canonical.get("_players_by_id")
    if isinstance(cached, dict):
        return cached
    players = {player.get("id"): player for player in canonical.get("players", []) if player.get("id")}
    if canonical.get("_allow_internal_caches"):
        canonical["_players_by_id"] = players
    return players


PRESENTATION_RATING_ANCHORS = (
    (1.0, 1.0),
    (50.0, 50.0),
    (99.0, 99.0),
)

RATING_SCALE = 'model_skill_1_99'


DISPLAY_KNEE = 99.0
DISPLAY_SCALE = 3.0


def presentation_rating_value(value: float | int | None) -> float:
    """Display the model grade directly, with common anchors for every rating.

    OFF/DEF/OVR and subratings share units, without percentile inflation or
    upper-tail compression. A composite summarizes its named abilities; an 80
    is not 80% success or identical impact in every role. Conversion is
    idempotent, and never changes the abilities used by simulation or pricing.
    """
    value = float(value or 0.0)
    if value <= DISPLAY_KNEE:
        return round(max(1.0, value), 1)
    # Rescale, don't clip (2026-11-18): a few engine values now exceed 99 (elite rim protection, the uncensored top of
    # clipped legacy scales). Above 99 the display approaches 100 smoothly and strictly increases, so elite players
    # stay distinguishable on the card; everything at or below 99 is shown unchanged (idempotent there).
    return round(DISPLAY_KNEE + (100.0 - DISPLAY_KNEE) * (1.0 - math.exp(-(value - DISPLAY_KNEE) / DISPLAY_SCALE)), 1)


def player_display_attribute_summary(canonical: dict[str, Any], player_id: str) -> dict[str, float]:
    """Use the same direct grade scale for OFF, DEF, OVR and subratings."""
    return {
        key: presentation_rating_value(value)
        for key, value in player_attribute_summary(canonical, player_id).items()
    }


DISPLAY_RATING_TERTILE_KEYS = (
    "overall",
    "shooting",
    "release",
    "versatility",
    "spacing",
    "creation",
    "handle",
    "rim_pressure",
    "defense",
    "def_effort",
    "screen_nav",
    "steal",
    "block",
    "range",
    "passing",
    "rebounding",
    "oreb",
    "rim_deterrence",
    "athleticism",
    "lateral_agility",
    "stamina",
    "iq",
    "scheme_iq",
    "portability",
    "playoff",
)


def display_rating_tertiles(canonical: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Return league-wide display quartiles under the legacy payload name.

    The public ``rating_tertiles`` key predates the fourth display tier and is
    retained for save/UI compatibility. These cutoffs are presentation-only;
    engine ratings and every gameplay calculation remain unchanged.
    """
    cached = canonical.get("_display_rating_quartiles")
    if isinstance(cached, dict):
        return cached
    from .offense import FACETS, enabled as offense_enabled
    keys = (*DISPLAY_RATING_TERTILE_KEYS, 'offense', *FACETS) if offense_enabled(canonical) else DISPLAY_RATING_TERTILE_KEYS
    values_by_key: dict[str, list[float]] = {key: [] for key in keys}
    retired_ids = set(canonical.get("retired_player_ids") or [])
    for player in canonical.get("players", []):
        player_id = player.get("id")
        if not player_id or player_id in retired_ids:
            continue
        ratings = player_display_attribute_summary(canonical, player_id)
        for key in keys:
            values_by_key[key].append(float(ratings.get(key) or 0.0))
    thresholds: dict[str, dict[str, float]] = {}
    for key, values in values_by_key.items():
        ordered = sorted(values)
        if not ordered:
            thresholds[key] = {"lower": 0.0, "middle": 0.0, "upper": 0.0}
            continue
        last = len(ordered) - 1
        thresholds[key] = {
            "lower": round(ordered[min(last, round(last * 0.25))], 1),
            "middle": round(ordered[min(last, round(last * 0.50))], 1),
            "upper": round(ordered[min(last, round(last * 0.75))], 1),
        }
    if canonical.get("_allow_internal_caches"):
        canonical["_display_rating_quartiles"] = thresholds
    return thresholds


def display_rating_averages(canonical: dict[str, Any]) -> dict[str, float]:
    """League means for player-card reference markers."""
    cached = canonical.get("_display_rating_averages")
    if isinstance(cached, dict):
        return cached
    retired_ids = set(canonical.get("retired_player_ids") or [])
    from .offense import FACETS, enabled as offense_enabled
    keys = (*DISPLAY_RATING_TERTILE_KEYS, 'offense', *FACETS) if offense_enabled(canonical) else DISPLAY_RATING_TERTILE_KEYS
    values: dict[str, list[float]] = {key: [] for key in keys}
    for player in canonical.get("players", []):
        player_id = player.get("id")
        if not player_id or player_id in retired_ids:
            continue
        ratings = player_display_attribute_summary(canonical, player_id)
        for key in keys:
            values[key].append(float(ratings.get(key) or 0.0))
    averages = {key: round(sum(rows) / len(rows), 1) if rows else 0.0 for key, rows in values.items()}
    if canonical.get("_allow_internal_caches"):
        canonical["_display_rating_averages"] = averages
    return averages


POSITION_AVERAGE_MIN_SAMPLE = 20


def display_rating_averages_by_position(canonical: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Mean display ratings of current league players at each primary position (PG/SG/SF/PF/C).

    Positions with fewer than POSITION_AVERAGE_MIN_SAMPLE players are left out (callers fall back to the
    league mean)."""
    cached = canonical.get("_display_rating_averages_by_position")
    if isinstance(cached, dict):
        return cached
    retired_ids = set(canonical.get("retired_player_ids") or [])
    from .offense import FACETS, enabled as offense_enabled
    keys = (*DISPLAY_RATING_TERTILE_KEYS, 'offense', *FACETS) if offense_enabled(canonical) else DISPLAY_RATING_TERTILE_KEYS
    groups: dict[str, dict[str, list[float]]] = {}
    for player in canonical.get("players", []):
        player_id = player.get("id")
        position = str(player.get("position") or "").upper().split("/")[0].strip()
        if not player_id or player_id in retired_ids or position not in {"PG", "SG", "SF", "PF", "C"}:
            continue
        ratings = player_display_attribute_summary(canonical, player_id)
        bucket = groups.setdefault(position, {key: [] for key in keys})
        for key in keys:
            bucket[key].append(float(ratings.get(key) or 0.0))
    averages = {
        position: {key: round(sum(rows) / len(rows), 1) for key, rows in bucket.items() if rows}
        for position, bucket in groups.items()
        if len(next(iter(bucket.values()), [])) >= POSITION_AVERAGE_MIN_SAMPLE
    }
    if canonical.get("_allow_internal_caches"):
        canonical["_display_rating_averages_by_position"] = averages
    return averages


def positional_rating_reference(canonical: dict[str, Any], position: Any) -> tuple[dict[str, float], str]:
    """Reference averages for a (possibly multi-position, e.g. "SF/PF") player and a label for them.

    Multi-position players get the mean of their listed positions' averages. Unknown or thin positions fall back
    to the league mean, labelled as such."""
    by_position = display_rating_averages_by_position(canonical)
    listed = [part.strip() for part in str(position or "").upper().replace(",", "/").replace("-", "/").split("/")]
    usable = [part for part in dict.fromkeys(listed) if part in by_position]
    if not usable:
        return display_rating_averages(canonical), "League average"
    keys = set.intersection(*(set(by_position[part]) for part in usable))
    averages = {key: round(sum(by_position[part][key] for part in usable) / len(usable), 1) for key in keys}
    return averages, f"{'/'.join(usable)} average"


def player_attribute_summary(canonical: dict[str, Any], player_id: str) -> dict[str, float]:
    # This memo is attached only to immutable hypothetical forecast views.
    # Actual/user rotations keep the existing fresh calculation path.
    memo = canonical.get('_roster_forecast_attributes')
    key = None
    if memo is not None:
        player = players_by_id_index(canonical).get(player_id, {})
        key = (player_id, display_minutes_projection(player))
        cached = memo.get(key)
        if cached is not None:
            return dict(cached)
    runtime = _ADVANCE_RUNTIME_STATE.get()
    if memo is None and runtime is not None and canonical.get("_allow_internal_caches"):
        # Repeated health/minutes refreshes often request exactly the same
        # summary. Key every input read by the summary/offense/impact formulas;
        # workload and development changes must never reuse an old grade.
        player = players_by_id_index(canonical).get(player_id, {})
        meta = canonical.get("meta") or {}
        model = canonical.get("_ratings_model") or {}
        signature = pickle.dumps((
            player_id, trait_values_by_player(canonical).get(player_id, {}),
            tuple(player.get(field) for field in ("position", "height_inches", "weight_lbs")),
            display_minutes_projection(player), meta.get("talent_model_version"), meta.get("offense_model_version"),
            (meta.get("offensive_profiles") or {}).get(player_id),
            tuple(model.get(field) for field in ("mode", "inputs_key", "fitted_key", "impact_tables_key")),
            (model.get("input_deltas") or {}).get(player_id), (model.get("generated") or {}).get(player_id),
        ), protocol=pickle.HIGHEST_PROTOCOL)
        cached = runtime.attribute_summaries.get(signature)
        if cached is not None:
            return dict(cached)
        result = _uncached_player_attribute_summary(canonical, player_id)
        if len(runtime.attribute_summaries) >= 8192:
            runtime.attribute_summaries.clear()
        runtime.attribute_summaries[signature] = dict(result)
        return result
    result = _uncached_player_attribute_summary(canonical, player_id)
    if memo is not None:
        memo[key] = dict(result)
    return result


def _uncached_player_attribute_summary(canonical: dict[str, Any], player_id: str) -> dict[str, float]:
    from .talent import enabled as talent_enabled, role_skill_value
    traits = trait_values_by_player(canonical).get(player_id, {})
    player = players_by_id_index(canonical).get(player_id, {})
    minutes = display_minutes_projection(player)

    def avg(keys: list[str], default: float = 50.0) -> float:
        values = [traits.get(key, default) for key in keys]
        return sum(values) / max(1, len(values))

    shooting = avg(["shooting_range", "shot_versatility", "release_speed"])
    creation = avg(["handle_pressure", "passing_reads", "rim_pressure", "shot_versatility"])
    from .defense import defensive_components
    defense = defensive_components(lambda key: float(traits.get(key, 50.0))).skill
    athleticism = avg(["foot_speed_lateral_agility", "stamina_cardio", "rim_pressure"])
    iq = avg(["scheme_iq", "passing_reads", "portability", "playoff_translation"])
    rebounding = traits.get("offensive_rebounding", 50.0) * 0.66 + traits.get("rim_deterrence", 50.0) * 0.18 + traits.get("stamina_cardio", 50.0) * 0.16
    # The engine's own spacing (sim.player_feature_vector): shooting range with extra credit for elite range. It used
    # to repeat the shooting composite, which the sim never uses for spacing (rule 4, 2026-11-19).
    from .sim import nonlinear_high
    spacing = nonlinear_high(traits.get("shooting_range", 50.0), 65)
    steal = avg(["defensive_effort", "screen_navigation", "foot_speed_lateral_agility", "scheme_iq"])
    block = avg(["rim_deterrence", "foot_speed_lateral_agility", "defensive_effort"])
    overall = shooting * 0.22 + creation * 0.25 + defense * 0.22 + athleticism * 0.13 + iq * 0.12 + min(6.0, minutes / 7.0)
    if talent_enabled(canonical):
        role = role_skill_value((shooting, creation, defense, athleticism, iq, rebounding), player.get("position"))
        overall = .5 * overall + .5 * (role * .94 + min(6.0, minutes / 7.0))
    from .offense import enabled as offense_enabled, offensive_profile, FACETS
    offensive_attrs = {}
    if offense_enabled(canonical):
        profile = offensive_profile(canonical, player, traits)
        offensive_attrs = {key: round(profile[key], 1) for key in FACETS}
        offensive_attrs['offense'] = round(profile['offense_value'], 1)
    from .impact_value import summary_override
    fitted = summary_override(canonical, player, traits, profile if offense_enabled(canonical) else None)
    if fitted:
        # New ratings: value comes from the hidden ratings fitted to real impact, placed on this same scale.
        overall = fitted.get("overall", overall)
        defense = fitted.get("defense", defense)
        if "offense" in offensive_attrs and "offense" in fitted:
            offensive_attrs["offense"] = fitted["offense"]
    return {
        **offensive_attrs,
        "overall": round(clamp(overall, 1, 99), 1),
        "shooting": round(clamp(shooting, 1, 99), 1),
        "spacing": round(clamp(spacing, 1, 99), 1),
        "creation": round(clamp(creation, 1, 99), 1),
        "defense": round(max(1.0, defense), 1),
        "athleticism": round(clamp(athleticism, 1, 99), 1),
        "iq": round(clamp(iq, 1, 99), 1),
        "release": round(clamp(traits.get("release_speed", 50.0), 1, 99), 1),
        "range": round(max(1.0, traits.get("shooting_range", 50.0)), 1),
        "versatility": round(clamp(traits.get("shot_versatility", 50.0), 1, 99), 1),
        "handle": round(clamp(traits.get("handle_pressure", 50.0), 1, 99), 1),
        "rim_pressure": round(clamp(traits.get("rim_pressure", 50.0), 1, 99), 1),
        "passing": round(clamp(traits.get("passing_reads", 50.0), 1, 99), 1),
        "stamina": round(clamp(traits.get("stamina_cardio", 50.0), 1, 99), 1),
        "rebounding": round(max(1.0, rebounding), 1),
        "def_effort": round(clamp(traits.get("defensive_effort", 50.0), 1, 99), 1),
        "screen_nav": round(clamp(traits.get("screen_navigation", 50.0), 1, 99), 1),
        "steal": round(clamp(steal, 1, 99), 1),
        "block": round(max(1.0, block), 1),
        "rim_deterrence": round(max(1.0, traits.get("rim_deterrence", 50.0)), 1),
        "oreb": round(max(1.0, traits.get("offensive_rebounding", 50.0)), 1),
        "lateral_agility": round(clamp(traits.get("foot_speed_lateral_agility", 50.0), 1, 99), 1),
        "scheme_iq": round(clamp(traits.get("scheme_iq", 50.0), 1, 99), 1),
        "portability": round(clamp(traits.get("portability", 50.0), 1, 99), 1),
        "playoff": round(clamp(traits.get("playoff_translation", 50.0), 1, 99), 1),
    }


def player_salary_table(canonical: dict[str, Any], player_id: str) -> dict[str, float | None]:
    from .roster_forecast import first_player_row
    contract = first_player_row(canonical, canonical.get("contracts", []), player_id)
    if not contract:
        return {}
    output: dict[str, float | None] = {}
    for entry in contract.get("seasons", []):
        season = str(entry.get("season") or "")
        if not season:
            continue
        salary = entry.get("salary")
        output[season] = round(float(salary) / 1_000_000, 1) if salary is not None else None
    return dict(sorted(output.items()))


AWARD_MIN_GAMES = 65   # the league's games-played rule for season awards (2023 collective bargaining agreement)


def award_games_max(games_played: int, team_games: int, state: dict[str, Any] | None, extra_rest: int = 0) -> int:
    """Most regular-season games a player can still reach: games played plus his team's games left, minus the games
    the GM is resting him (and `extra_rest` more)."""
    from .health import REGULAR_SEASON_GAMES
    resting = int(((state or {}).get("user_rest") or {}).get("games_left") or 0)
    return int(games_played) + max(0, REGULAR_SEASON_GAMES - int(team_games)) - resting - max(0, int(extra_rest))


def fatigue_display(state: dict[str, Any]) -> dict[str, Any]:
    """What the fatigue bar and the rest controls show, straight from the engine's health state: fatigue at his team's
    next tip-off (the value that game uses), the GM's rest (games left) and how many games he has sat by rest."""
    out: dict[str, Any] = {"games_rested": int(state.get("games_rested") or 0)}
    upcoming = state.get("fatigue_next")
    if upcoming:
        out["fatigue_next"] = round(float(upcoming.get("value") or 0.0), 2)
        out["fatigue_next_date"] = upcoming.get("date")
    rest = state.get("user_rest")
    if rest:
        out["user_rest"] = {"games_left": int(rest.get("games_left") or 0), "games": int(rest.get("games") or 0),
                            "since": rest.get("since")}
    return out


def player_health_label(state: dict[str, Any] | None, current_date: str | None) -> dict[str, Any]:
    if not state:
        return {"status": "ok", "label": "", "games_missed": 0, "fatigue": 0.0}
    status = state.get("availability_status") or "active"
    fatigue = round(float(state.get("fatigue") or 0.0), 2)
    if status == "active":
        from .sim import rust_display
        return {"status": "ok", "label": "", "games_missed": int(state.get("games_missed") or 0), "fatigue": fatigue,
                **fatigue_display(state), **rust_display(state)}
    return_date = state.get("return_date")
    days_left = None
    if return_date and current_date:
        days_left = max(0, (parse_date(return_date) - parse_date(current_date)).days)
    severity = state.get("injury_severity") or state.get("current_injury_severity") or "injured"
    # v2 injuries carry a real diagnosis ("Ankle sprain", "ACL tear"); older saves show the severity band.
    diagnosis = str(state.get("current_injury_label") or "").strip()
    label = diagnosis[:1].upper() + diagnosis[1:] if diagnosis else f"{severity}"
    if days_left is not None:
        label = f"{label} ~{max(1, round(days_left / 2.4))}g"
    return {"status": status, "label": label, "days_left": days_left, "games_missed": int(state.get("games_missed") or 0), "fatigue": fatigue,
            "severity": severity, "body_part": state.get("current_injury_part"), "diagnosis": diagnosis or None}


def cap_lines_for_season(season: str | None) -> dict[str, float]:
    """The league's cap lines for a season (cap_rules: one source for every part of the game)."""
    from .cap_rules import cap_lines_for_season as shared_lines
    return shared_lines(season)


def team_cap_summary(canonical: dict[str, Any], save: dict[str, Any], team_id: str, season: str | None = None) -> dict[str, Any]:
    from .trade_tax import team_tax_payout_summary
    season = season or save.get("meta", {}).get("season") or CANONICAL_SEASON
    lines = cap_lines_for_season(season)
    total = 0.0
    unresolved = 0
    active_player_ids = {player["id"] for player in canonical.get("players", []) if player.get("team_id") == team_id}
    for contract in canonical.get("contracts", []):
        if contract.get("player_id") not in active_player_ids:
            continue
        salary = contract_salary_for_season(contract, season)
        if salary is None:
            unresolved += 1
        else:
            total += salary
    from .contract_protection import waived_total
    dead = waived_total(save, team_id, season)
    active_salary = total
    total += dead
    unresolved_dead = sum(s.get('salary') is None for r in save.get('waived_salary_obligations', [])
                          if r['team_id'] == team_id for s in r['seasons'] if s['season'] == season)
    tax_line = float(lines["tax_line"])
    hard_cap = float(lines["hard_cap"])
    tax_space = tax_line - total
    hard_cap_space = hard_cap - total
    return {
        "season": season,
        "salary_total": round(total, 2),
        "salary_total_millions": round(total / 1_000_000, 2),
        'active_salary_millions': round(active_salary/1_000_000, 2),
        'waived_salary_millions': round(dead/1_000_000, 2),
        'unresolved_waived_contract_count': unresolved_dead,
        'unverified_waived_reserve_millions': round(sum(float(s.get('unverified_reserve') or 0)
            for r in save.get('waived_salary_obligations', []) if r['team_id'] == team_id
            for s in r['seasons'] if s['season'] == season)/1_000_000, 2),
        "tax_line_millions": round(tax_line / 1_000_000, 2),
        "hard_cap_millions": round(hard_cap / 1_000_000, 2),
        "tax_space_millions": round(tax_space / 1_000_000, 2),
        "hard_cap_space_millions": round(hard_cap_space / 1_000_000, 2),
        "tax_space_pct": round(tax_space / tax_line * 100, 1),
        "hard_cap_space_pct": round(hard_cap_space / hard_cap * 100, 1),
        "cap_growth_factor": lines["growth_factor"],
        "unresolved_contract_count": unresolved + unresolved_dead,
        "tax_payout": team_tax_payout_summary(save, team_id),  # TRADE-TAXPOOL: last season's payout or tax bill
    }


def contract_salary_for_season(contract: dict[str, Any], season: str) -> float | None:
    for entry in contract.get("seasons", []):
        if entry.get("season") == season and entry.get("salary") is not None:
            return float(entry.get("salary"))
    return None


def offer_to_contract_seasons(offer: dict[str, Any]) -> list[dict[str, Any]]:
    years = int(offer.get("years") or offer.get("term_years") or 1)
    annual = float(offer.get("annual_salary") or offer.get("aav") or offer.get("annual_salary_millions", 0.0))
    if annual and annual < 1_000_000:
        annual *= 1_000_000
    start = int(str(offer.get("start_season") or offer.get("season") or CANONICAL_SEASON).split("-")[0])
    seasons = []
    for offset in range(max(1, years)):
        seasons.append(
            {
                "season": season_label_from_start(start + offset),
                "salary": int(round(annual)),
                "option_type": None,
                "guarantee_status": "save_state_offer",
            }
        )
    from .contract_protection import negotiated_seasons
    return negotiated_seasons(offer, seasons)


def initial_team_morale(canonical: dict[str, Any]) -> dict[str, dict[str, float]]:
    states = {state["team_id"]: state for state in canonical.get("team_strategic_states", [])}
    output = {}
    for team in canonical.get("teams", []):
        state = states.get(team["id"], {})
        phase = str(state.get("phase") or "")
        ceiling = float(state.get("contention_ceiling") or 55.0)
        pressure = float(state.get("pressure") or 55.0)
        base = 52.0 + (ceiling - 55.0) * 0.16 - max(0.0, pressure - 62.0) * 0.08 + deterministic_small(team["id"], "morale") * 3.5
        if "contending" in phase:
            base += 3.0
        if "rebuilding" in phase:
            base -= 2.2
        output[team["id"]] = {
            "overall": round(clamp(base, 38, 74), 2),
            "chemistry": round(clamp(base + deterministic_small(team["id"], "chemistry") * 4.0, 36, 78), 2),
            "confidence": round(clamp(base + (ceiling - 58.0) * 0.08, 35, 80), 2),
        }
    return output


def initial_player_morale(canonical: dict[str, Any]) -> dict[str, dict[str, float]]:
    team_morale = initial_team_morale(canonical)
    output = {}
    for player in canonical.get("players", []):
        minutes = display_minutes_projection(player)
        team_base = team_morale.get(player.get("team_id"), {}).get("overall", 54.0)
        role = 60.0 if minutes >= 28 else 56.0 if minutes >= 18 else 51.0 if minutes >= 10 else 46.0
        age = float(player.get("age") or 27.0)
        contract = 55.0 + deterministic_small(player["id"], "contract") * 6.0
        if age >= 34 and minutes < 16:
            role -= 2.5
        output[player["id"]] = {
            "overall": round(clamp(team_base * 0.55 + role * 0.35 + 6.0 + deterministic_small(player["id"], "overall") * 3.0, 35, 78), 2),
            "role_satisfaction": round(clamp(role + deterministic_small(player["id"], "role") * 5.5, 30, 82), 2),
            "team_confidence": round(clamp(team_base + deterministic_small(player["id"], "team") * 4.0, 32, 82), 2),
            "contract_satisfaction": round(clamp(contract, 30, 82), 2),
        }
    return output


def initial_team_metric(canonical: dict[str, Any], value: float) -> dict[str, float]:
    return {team["id"]: round(clamp(value + deterministic_small(team["id"], "metric") * 5.0, 35, 80), 2) for team in canonical.get("teams", [])}


def deterministic_small(*parts: object) -> float:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF - 0.5


def update_game_morale(save: dict[str, Any], home_id: str, away_id: str, home_points: int, away_points: int) -> None:
    winner = home_id if home_points > away_points else away_id
    loser = away_id if winner == home_id else home_id
    margin = abs(home_points - away_points)
    win_delta = 1.0 + min(2.5, margin / 18.0)
    loss_delta = -0.8 - min(2.2, margin / 22.0)
    apply_team_morale_delta(save, winner, win_delta)
    apply_team_morale_delta(save, loser, loss_delta)
    save.setdefault("fan_confidence", {})[winner] = round(clamp(float(save.get("fan_confidence", {}).get(winner, 55.0)) + win_delta * 0.45, 0, 100), 2)
    save.setdefault("fan_confidence", {})[loser] = round(clamp(float(save.get("fan_confidence", {}).get(loser, 55.0)) + loss_delta * 0.4, 0, 100), 2)


def apply_team_morale_delta(save: dict[str, Any], team_id: str, delta: float) -> None:
    morale = save.setdefault("team_morale", {}).setdefault(team_id, {"overall": 58.0, "chemistry": 58.0, "confidence": 56.0})
    morale["overall"] = round(clamp(float(morale.get("overall", 58.0)) + delta, 0, 100), 2)
    morale["chemistry"] = round(clamp(float(morale.get("chemistry", 58.0)) + delta * 0.35, 0, 100), 2)
    morale["confidence"] = round(clamp(float(morale.get("confidence", 56.0)) + delta * 0.65, 0, 100), 2)


def update_player_game_morale(save: dict[str, Any], line: dict[str, Any], won: bool, margin: int) -> None:
    player_id = line.get("player_id")
    if not player_id:
        return
    morale = save.setdefault("player_morale", {}).setdefault(
        player_id,
        {"overall": 56.0, "role_satisfaction": 55.0, "team_confidence": 55.0, "contract_satisfaction": 55.0},
    )
    minutes = float(line.get("minutes") or 0.0)
    points = float(line.get("points") or 0.0)
    delta = (0.28 if won else -0.22) + min(0.35, margin / 70.0) * (1 if won else -1)
    role_delta = 0.08 if minutes >= 18 else -0.04 if minutes <= 8 else 0.0
    scoring_delta = clamp((points - minutes * 0.34) / 120.0, -0.12, 0.18)
    morale["overall"] = round(clamp(float(morale.get("overall", 56.0)) + delta + scoring_delta, 0, 100), 2)
    morale["role_satisfaction"] = round(clamp(float(morale.get("role_satisfaction", 55.0)) + role_delta, 0, 100), 2)
    morale["team_confidence"] = round(clamp(float(morale.get("team_confidence", 55.0)) + delta * 0.72, 0, 100), 2)


def add_news(save: dict[str, Any], kind: str, headline: str, date_value: str | None = None) -> dict[str, Any]:
    date_value = date_value or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    item = {
        "id": stable_id("news", kind, date_value, headline),
        "date": date_value,
        "kind": kind,
        "headline": headline,
        "status": "unread",
    }
    existing = {news.get("id") for news in save.setdefault("news_items", [])}
    if item["id"] not in existing:
        save["news_items"].append(item)
        if should_create_league_event_for_news(kind, headline):
            add_league_event(save, kind, headline, date_value=date_value)
        if should_create_social_for_news(kind, headline):
            add_social(save, kind, headline, team_ids=[])
    return item


def should_create_league_event_for_news(kind: str, headline: str) -> bool:
    if kind in {
        "game_result",
        "game",
        "playoffs",
        "playoff_result",
        "press_conference",
        "trade_offer",
        "development",
        "roster_cut",
    }:
        return False
    return True


def should_create_social_for_news(kind: str, headline: str) -> bool:
    if kind in {"game_result", "game", "development", "roster_cut", "draft_lottery"}:
        return False
    if kind in {"trade", "trade_demand", "free_agent_signing", "free_agency_signing", "extension", "finals_mvp", "champion"}:
        return True
    low = str(headline or "").lower()
    if kind in {"injury", "staff_hire", "staff_fire"}:
        return any(token in low for token in ["star", "major", "season-ending", "head coach", "elite"])
    return False


def add_league_event(
    save: dict[str, Any],
    kind: str,
    headline: str,
    date_value: str | None = None,
    team_ids: list[str | None] | None = None,
    player_ids: list[str | None] | None = None,
    importance: float | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    date_value = date_value or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    clean_headline = " ".join(str(headline or "").replace("_", " ").split())
    event = {
        "id": stable_id("league_event", kind, date_value, clean_headline),
        "date": date_value,
        "kind": kind,
        "headline": clean_headline,
        "team_ids": [team for team in (team_ids or []) if team],
        "player_ids": [player for player in (player_ids or []) if player],
        "importance": round(float(importance if importance is not None else event_importance(kind, clean_headline)), 3),
        "details": details or {},
    }
    events = save.setdefault("league_events", [])
    existing = next((item for item in events if item.get("id") == event["id"]), None)
    if existing is not None:
        existing["team_ids"] = sorted({*existing.get("team_ids", []), *event.get("team_ids", [])})
        existing["player_ids"] = sorted({*existing.get("player_ids", []), *event.get("player_ids", [])})
        existing["importance"] = round(max(float(existing.get("importance") or 0.0), float(event.get("importance") or 0.0)), 3)
        existing["details"] = merge_event_details(existing.get("details") or {}, event.get("details") or {})
        return existing
    events.append(event)
    return event


def merge_event_details(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_event_details(merged[key], value)
        elif value not in (None, "", [], {}):
            merged[key] = value
    return merged


def event_importance(kind: str, headline: str) -> float:
    low = f"{kind} {headline}".lower()
    base = {
        "trade": 0.72,
        "free_agent_signing": 0.62,
        "free_agency_signing": 0.62,
        "extension": 0.58,
        "injury": 0.55,
        "draft_lottery": 0.7,
        "draft_pick": 0.48,
        "playoff_result": 0.85,
        "finals_mvp": 0.95,
        "staff_hire": 0.38,
        "staff_fire": 0.42,
    }.get(kind, 0.35)
    if any(token in low for token in ["40", "50", "finals", "champion", "mvp", "season-ending", "star"]):
        base += 0.2
    return clamp(base, 0.0, 1.0)


def queue_aggregated_press_event(
    save: dict[str, Any],
    kind: str,
    headline: str,
    team_ids: list[str | None],
    date_value: str | None = None,
) -> dict[str, Any] | None:
    if kind in {"staff_hire", "staff_fire", "staff_change"} and "head coach" not in str(headline or "").lower():
        return None
    user_team_id = save.get("meta", {}).get("user_team_id") or save.get("state", {}).get("user_team_id")
    if not user_team_id or user_team_id not in set(team_ids):
        return
    date_value = date_value or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    group = press_event_group(kind)
    event_id = stable_id("press_event", group, date_value, user_team_id)
    events = save.setdefault("pending_press_events", [])
    existing = next((item for item in events if item.get("id") == event_id), None)
    if existing:
        headlines = existing.setdefault("headlines", [])
        if headline not in headlines:
            headlines.append(headline)
        existing["headline"] = press_event_headline(group, headlines)
        existing["question"] = press_event_question(group, headlines)
        return existing
    headlines = [headline]
    event = {
        "id": event_id,
        "date": date_value,
        "kind": group,
        "headline": press_event_headline(group, headlines),
        "headlines": headlines,
        "question": press_event_question(group, headlines),
        "status": "pending",
    }
    events.append(event)
    return event


def press_event_group(kind: str) -> str:
    if kind in {"trade", "trade_offer"}:
        return "trades"
    if kind in {"free_agency", "free_agent_signing", "free_agency_signing"}:
        return "free_agency"
    if kind in {"extension", "contract"}:
        return "extensions"
    if kind in {"staff_hire", "staff_fire", "staff_change"}:
        return "staff_moves"
    if kind in {"rare_drama", "drama"}:
        return "rare_drama"
    return kind


def press_event_headline(group: str, headlines: list[str]) -> str:
    if len(headlines) == 1:
        return headlines[0]
    return f"{len(headlines)} {clean_press_group_label(group)} require GM availability."


def press_event_question(group: str, headlines: list[str]) -> str:
    if group == "trades":
        return f"You made {len(headlines)} trade move(s). What is the basketball idea tying the outgoing and incoming assets together?"
    if group == "free_agency":
        return f"Free agency brought {len(headlines)} signing decision(s). What did this market tell you about the roster?"
    if group == "extensions":
        return f"You handled {len(headlines)} extension decision(s). How are you balancing loyalty, price, and future flexibility?"
    if group == "staff_moves":
        return f"You changed the staff room {len(headlines)} time(s). What should look different because of those voices?"
    if group == "rare_drama":
        return "The organization is dealing with a rare off-court distraction. What standard are you setting publicly?"
    return headlines[-1] if headlines else "What is the message to the locker room and fans?"


def clean_press_group_label(group: str) -> str:
    return {
        "trades": "trade moves",
        "free_agency": "free-agent moves",
        "extensions": "extension decisions",
        "staff_moves": "staff moves",
        "rare_drama": "drama items",
    }.get(group, group.replace("_", " "))


def sync_social_from_news(save: dict[str, Any]) -> None:
    social_keys = {(item.get("kind"), item.get("subject")) for item in save.get("social_feed", [])}
    for news in save.get("news_items", [])[-60:]:
        kind = news.get("kind")
        headline = news.get("headline")
        if not should_create_social_for_news(str(kind or ""), str(headline or "")):
            continue
        if not kind or not headline or (kind, headline) in social_keys:
            continue
        add_social(save, kind, headline, team_ids=[], date_value=news.get("date"))
        social_keys.add((kind, headline))


def add_social(save: dict[str, Any], kind: str, text: str, team_ids: list[str] | None = None, date_value: str | None = None) -> dict[str, Any]:
    date_value = date_value or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    post = social_post_for(kind, text, date_value)
    importance = social_importance(kind, post["text"])
    item = {
        "id": stable_id("social", kind, date_value, post["text"], post["handle"]),
        "date": date_value,
        "kind": kind,
        "text": post["text"],
        "author": post["author"],
        "handle": post["handle"],
        "persona": post["persona"],
        "subject": post.get("subject") or text,
        "team_ids": team_ids or [],
        "sentiment": social_sentiment(kind, post["text"]),
        "importance": importance,
    }
    feed = save.setdefault("social_feed", [])
    if kind in {"staff_hire", "staff_fire"} and any(
        existing.get("kind") == kind
        and existing.get("date") == date_value
        and existing.get("subject") == item["subject"]
        for existing in feed
    ):
        return item
    if item["id"] not in {existing.get("id") for existing in feed}:
        feed.append(item)
    return item


def social_importance(kind: str, text: str) -> int:
    low = text.lower()
    base = {
        "trade": 90,
        "trade_offer": 72,
        "free_agency": 82,
        "contract": 76,
        "free_agent_signing": 82,
        "extension": 76,
        "staff_hire": 68,
        "staff_fire": 72,
        "injury": 84,
        "injury_return": 72,
        "draft": 72,
        "draft_selection": 70,
        "draft_lottery": 78,
        "offseason_rosters": 70,
        "player_high": 86,
        "team_stretch": 76,
        "player_stretch": 74,
        "power_ranking": 66,
        "champion": 100,
        "playoffs": 80,
        "game_result": 42,
    }.get(kind, 45)
    if any(word in low for word in ["season high", "career", "trade", "fired", "signed", "wins the nba title"]):
        base += 10
    return int(clamp(base, 0, 100))


def social_post_for(kind: str, text: str, date_value: str) -> dict[str, str]:
    personas = [
        ("Maya Chen", "@maya_hoops", "film analyst"),
        ("Cap Sheet Carl", "@cap_sheet_carl", "salary obsessive"),
        ("The Rotation Doctor", "@rotation_rx", "minutes watcher"),
        ("Sideline Static", "@sideline_static", "fan chaos"),
        ("Jules on Hoops", "@julesonhoops", "measured beat writer"),
        ("League Pass Poet", "@lp_poet", "joke-heavy fan"),
        ("Hoop Sicko", "@rimrunratio", "NBA twitter sicko"),
        ("Zone Breaker", "@zone_breaker", "tactical agitator"),
        ("Bench Mob Burner", "@benchburner", "chaos fan"),
    ]
    subject = social_subject(text)
    templates = {
        "game_result": [
            "{subject} is the whole group chat right now. Rotation ripple watch starts now.",
            "{subject}. Somebody is about to make this about substitutions, and honestly they might be right.",
            "{subject}. The standings math just got a little louder.",
            "{subject}. Box score scouts, report to the timeline.",
            "{subject} and the timeline immediately became a crime scene.",
            "{subject}. Nasty little result for everyone's agenda spreadsheet.",
            "{subject}. This is either a statement win or a disgusting loss, depending on which avi is yelling.",
            "{subject}. Generational agenda food. The takes are going to be completely shameless.",
            "{subject}. Somebody's group chat is in hell right now.",
            "{subject}. I do not want to hear the 'scheduled loss' cope, respectfully.",
        ],
        "trade_offer": [
            "Trade machine smoke: {subject}",
            "{subject}. Front offices are at least picking up the phone.",
            "Not every call becomes a deal, but {lower_subject}",
            "{subject}. Half the league is lying, the other half is leaking.",
            "{subject}. If this is leverage, it is at least entertaining leverage.",
            "{subject}. This is either negotiation or pure sicko theater.",
            "{subject}. Fans have already decided one GM is a genius and the other is unemployed.",
        ],
        "free_agency": [
            "{subject}. The market has entered its annually unreasonable phase.",
            "{subject}. Years matter, role matters, money still talks.",
            "{subject}. Somebody is about to talk themselves into a fourth year.",
            "{subject}. Cap people are sweating; fans are already photoshopping jerseys.",
            "{subject}. That's not a contract, that's a therapy bill for the fanbase.",
            "{subject}. The mid-level exception discourse is about to become everyone's problem.",
        ],
        "free_agent_signing": [
            "{subject}. The market has spoken, whether the timeline likes it or not.",
            "{subject}. Fit, money, years: pick your argument and start yelling.",
            "{subject}. One fanbase just discovered the phrase 'actually he could be sneaky good.'",
        ],
        "contract": [
            "{subject}. Contract season remains the league's most expensive group project.",
            "{subject}. The cap sheet is either fine or on fire, depending on your agenda.",
            "{subject}. Security won the negotiation. Now the basketball has to justify it.",
        ],
        "extension": [
            "{subject}. The extension table got serious.",
            "{subject}. Locking in your own guys is easy until the AAV hits the screen.",
            "{subject}. Future flexibility just had a very adult conversation.",
        ],
        "press_conference": [
            "{subject}. The quote board gets one more push pin.",
            "{subject}. Good answer or not, the room definitely noticed the tone.",
            "{subject}. This is why media training is a front-office skill.",
            "{subject}. That answer is getting aggregated before the mic is even cold.",
            "{subject}. Respectfully, that was either leadership or premium waffle.",
            "{subject}. Incredible amount of 'we'll keep that internal' energy.",
            "{subject}. The man said words. Whether they mean anything is tomorrow's podcast.",
        ],
        "development": [
            "{subject}. Player dev is never linear, but the month-to-month noise is where saves get fun.",
            "{subject}. Somewhere a development coach is quietly updating the spreadsheet.",
            "{subject}. The 'he added something this summer' crowd just got new material.",
        ],
        "trade": [
            "{subject}. My first read: one side got cleaner fit, the other side better hope the pick math saves them.",
            "{subject}. Somebody's value chart just got punched in the mouth and the cap sheet is pretending it is fine.",
            "{subject}. This feels like a GM either reading the room perfectly or talking himself into a podcast apology.",
            "{subject}. If the incoming role is what they think it is, this is sharp. If not, enjoy the discourse funeral.",
        ],
        "injury": [
            "{subject}. This is where depth stops being a buzzword and starts being the whole season.",
            "{subject}. Brutal timing. The rotation math gets ugly fast if the bench cannot cover real minutes.",
            "{subject}. Fans will say next man up; coaches know the shot profile just changed.",
            "{subject}. Not every injury is season-changing, but this one at least forces the front office to look in the mirror.",
        ],
        "injury_return": [
            "{subject}. The return is good news, but somebody is about to lose touches and the rotation politics are real.",
            "{subject}. Reintegration sounds easy until a replacement has earned minutes the hard way.",
            "{subject}. Healthy roster, uncomfortable decisions. That is a better problem, but it is still a problem.",
        ],
        "staff_hire": [
            "{subject}. Staff nerds, this is your moment.",
            "{subject}. Not a jersey-selling move, but these are the margins that can swing a season.",
            "{subject}. The clipboard economy is thriving.",
        ],
        "staff_fire": [
            "{subject}. The vibes meeting apparently did not go well.",
            "{subject}. Front office accountability, or just a human shield? Discuss.",
            "{subject}. Somebody update the job security meter.",
        ],
        "draft": [
            "{subject}. Draft night optimism remains undefeated.",
            "{subject}. The rookie contract math is already doing laps around the timeline.",
            "{subject}. Bookmarking this for the first summer league overreaction.",
        ],
        "draft_selection": [
            "{subject}. Scout departments either high-fiving or quietly deleting notes.",
            "{subject}. The fit discourse starts before the hat is even on.",
            "{subject}. I will be overreacting responsibly.",
        ],
        "draft_lottery": [
            "{subject}. Lottery night: where math becomes trauma.",
            "{subject}. Half the league just changed its five-year plan in public.",
            "{subject}. Ping-pong ball theology is undefeated.",
        ],
        "offseason_rosters": [
            "{subject}. The bottom of the roster churn is where true save sickos live.",
            "{subject}. Some of these moves will matter in February and everyone will pretend they knew.",
            "{subject}. Depth chart spreadsheet season is open.",
        ],
        "player_high": [
            "{subject}. Absurd box-score behavior. The stat watchers are eating.",
            "{subject}. Somebody got cooked so badly the film session needs a waiver.",
            "{subject}. League Pass sickos just found tomorrow's discourse.",
            "{subject}. That's not a heater, that's an HR violation.",
        ],
        "team_stretch": [
            "{subject}. Small sample? Sure. But small samples still pay rent on the timeline.",
            "{subject}. This is the kind of stretch that makes GMs start lying to themselves.",
            "{subject}. Power rankings people are already moving the goalposts.",
        ],
        "player_stretch": [
            "{subject}. Role clarity discourse is officially open, and the box score is making the argument louder.",
            "{subject}. This is the kind of production that changes how every opponent loads up the scouting report.",
            "{subject}. Agenda stock is up and the replies are unbearable.",
        ],
        "power_ranking": [
            "{subject}. Everyone below this is typing through it.",
            "{subject}. The fake-neutral analysts have made their monthly decree.",
            "{subject}. This ranking is either science or slander. Possibly both.",
        ],
        "playoffs": [
            "{subject}. Playoff basketball remains deeply unserious for blood pressure.",
            "{subject}. This is where reputations get cooked or canonized.",
        ],
        "champion": [
            "{subject}. Banner math complete. Agenda math just beginning.",
            "{subject}. Confetti is undefeated content.",
        ],
    }
    digest = hashlib.sha256(f"{date_value}:{kind}:{text}".encode("utf-8")).hexdigest()
    persona = personas[int(digest[:2], 16) % len(personas)]
    choices = templates.get(kind, ["{text}", "{text} File it under: things to monitor."])
    template = choices[int(digest[2:4], 16) % len(choices)]
    rendered = template.format(
        text=text,
        subject=subject,
        lower_text=text[:1].lower() + text[1:] if text else text,
        lower_subject=subject[:1].lower() + subject[1:] if subject else subject,
    )
    return {"author": persona[0], "handle": persona[1], "persona": persona[2], "text": rendered, "subject": subject}


def public_player_role(canonical: dict[str, Any], player_id: str | None, ppg: float = 0.0) -> str:
    player = next((item for item in canonical.get("players", []) if item.get("id") == player_id), {})
    if not player:
        return "rotation story"
    attrs = player_attribute_summary(canonical, player_id)
    overall = float(attrs.get("overall") or 0.0)
    minutes = display_minutes_projection(player)
    if overall >= 82 or ppg >= 27 or minutes >= 32:
        return "franchise-cornerstone level player"
    if overall >= 74 or ppg >= 21 or minutes >= 28:
        return "star-level option"
    if overall >= 64 or minutes >= 20:
        return "starter-level piece"
    return "rotation piece"


def social_subject(text: str) -> str:
    if not text:
        return "League chatter"
    cleaned = text.strip().rstrip(".")
    if cleaned.startswith("Trade completed:"):
        return cleaned if len(cleaned) <= 120 else cleaned[:117].rstrip()
    if len(cleaned) <= 86:
        return cleaned
    for separator in [". ", " | ", " - "]:
        if separator in cleaned:
            first = cleaned.split(separator)[0].strip()
            if 8 <= len(first) <= 86:
                return first
    return cleaned[:86].rstrip()


def social_sentiment(kind: str, text: str) -> float:
    low = text.lower()
    sentiment = 0.0
    if kind in {"champion", "staff_hire"} or "wins" in low or "hired" in low:
        sentiment += 0.35
    if "fired" in low or "loss" in low:
        sentiment -= 0.25
    if "accountable" in low:
        sentiment += 0.12
    if "deflect" in low:
        sentiment -= 0.12
    return round(clamp(sentiment, -1.0, 1.0), 3)


def press_impact(topic: str, tone: str, seed: int = 1) -> dict[str, float]:
    base = {
        "accountable": {"team_morale": 4.4, "fan_confidence": 3.3, "owner_confidence": 3.0},
        "optimistic": {"team_morale": 3.2, "fan_confidence": 4.4, "owner_confidence": 1.7},
        "deflect": {"team_morale": -1.8, "fan_confidence": -4.7, "owner_confidence": -2.8},
        "challenge": {"team_morale": -2.5, "fan_confidence": 3.2, "owner_confidence": 5.1},
    }[tone]
    topic_low = topic.lower()
    multiplier = 1.0
    if any(word in topic_low for word in ["losing", "injury", "trade", "chemistry", "playoffs"]):
        multiplier = 1.25
    if any(word in topic_low for word in ["scandal", "fight", "drama"]) and tone == "accountable":
        multiplier = 1.55
    if any(word in topic_low for word in ["trade", "staff", "signing", "extension"]):
        if tone == "optimistic":
            base = {**base, "fan_confidence": base["fan_confidence"] + 1.25, "team_morale": base["team_morale"] + 0.75}
        if tone == "deflect":
            base = {**base, "team_morale": base["team_morale"] + 1.0, "owner_confidence": base["owner_confidence"] + 0.4}
    if "rumor" in topic_low and tone == "deflect":
        base = {**base, "team_morale": base["team_morale"] + 1.2, "fan_confidence": base["fan_confidence"] + 0.6}
    if "injury" in topic_low and tone == "optimistic":
        base = {**base, "team_morale": base["team_morale"] + 1.15, "owner_confidence": base["owner_confidence"] - 1.0}
    if any(word in topic_low for word in ["losing", "under .500", "expectations"]) and tone == "challenge":
        base = {**base, "fan_confidence": base["fan_confidence"] + 1.35, "team_morale": base["team_morale"] - 1.0}
    rng = random.Random(f"{seed}:{topic}:{tone}:press_impact")
    return {key: round(value * multiplier + rng.uniform(-1.8, 1.8), 3) for key, value in base.items()}


def social_reaction_text(team_abbrev: str, topic: str, tone: str) -> str:
    if tone == "accountable":
        return f"{team_abbrev} front office puts its name on {topic}. Useful honesty, unless the results make it age terribly."
    if tone == "optimistic":
        return f"{team_abbrev} sells the upside on {topic}. Fans will believe it for exactly as long as the next box score allows."
    if tone == "challenge":
        return f"{team_abbrev} sends a sharper message about {topic}. Locker room quote-board potential is officially high."
    return f"{team_abbrev} keeps the real answer private on {topic}. Smart politics or premium dodgeball, depending on your agenda."


def press_question(team_abbrev: str, topic: str, tone: str, seed: int) -> str:
    questions = [
        f"What do you want fans to understand about {topic}?",
        f"How much responsibility does the front office take for {topic}?",
        f"Is {topic} something you expect to solve internally, or does the roster need help?",
        f"What message are you trying to send the locker room about {topic}?",
    ]
    index = int(hashlib.sha256(f"{team_abbrev}:{topic}:{tone}:{seed}".encode("utf-8")).hexdigest()[:2], 16) % len(questions)
    return questions[index]


def press_answer(team_abbrev: str, topic: str, tone: str) -> str:
    if tone == "accountable":
        return f"We have to be honest about {topic}. Our job is to make the next decision clearer than the last one, and that starts with owning what is in front of us."
    if tone == "optimistic":
        return f"We still believe in the group. {topic.capitalize()} is real, but there is enough talent and buy-in here to keep pushing in the right direction."
    if tone == "challenge":
        return f"The standard does not move. {topic.capitalize()} is a test for everyone in the building, and we expect a sharper response."
    return f"We are going to keep most of those conversations internal. {topic.capitalize()} matters, but public noise cannot drive the plan."


def deterministic_series_winner(save: dict[str, Any], series: dict[str, Any], seed: int) -> str:
    records = save.get("team_records", {})
    a, b = series["team_ids"]
    a_score = playoff_team_score(records.get(a, {}), a, seed)
    b_score = playoff_team_score(records.get(b, {}), b, seed)
    return a if a_score >= b_score else b


def playoff_team_score(record: dict[str, Any], team_id: str, seed: int) -> float:
    games = max(1, int(record.get("wins", 0)) + int(record.get("losses", 0)))
    win_pct = float(record.get("wins", 0)) / games
    point_diff = (float(record.get("points_for", 0)) - float(record.get("points_against", 0))) / games
    noise = int(hashlib.sha256(f"{seed}:{team_id}:playoffs".encode("utf-8")).hexdigest()[:4], 16) / 65535.0 - 0.5
    return win_pct * 100 + point_diff * 1.8 + noise * 5.0


def deterministic_loser_wins(save: dict[str, Any], winner: str, loser: str, seed: int) -> int:
    gap = playoff_team_score(save.get("team_records", {}).get(winner, {}), winner, seed) - playoff_team_score(save.get("team_records", {}).get(loser, {}), loser, seed)
    if gap > 16:
        return 0
    if gap > 9:
        return 1
    if gap > 4:
        return 2
    return 3


def next_playoff_round(current_round: str | None) -> str:
    return {
        "first_round": "conference_semifinals",
        "conference_semifinals": "conference_finals",
        "conference_finals": "finals",
        "finals": "champion",
    }.get(str(current_round), "conference_semifinals")


def repair_unplayed_playoff_round(state: dict[str, Any]) -> bool:
    current_round = state.get("round")
    prior_round = {"conference_semifinals":"first_round", "conference_finals":"conference_semifinals", "finals":"conference_finals"}.get(current_round)
    if not prior_round or state.get("status") == "completed":
        return False
    existing = [s for s in state.get("series", []) if s.get("round") == current_round]
    previous = [s for s in state.get("series", []) if s.get("round") == prior_round]
    # Never rewrite a started round, or infer winners of unfinished series.
    if not existing or any(s.get("game_ids") or any(s.get("wins", {}).values()) for s in existing):
        return False
    if not previous or any(not s.get("winner_team_id") or s.get("status") != "completed" for s in previous):
        return False
    round_order = {"first_round":0, "conference_semifinals":1, "conference_finals":2, "finals":3}
    if any(round_order.get(s.get("round"), -1) > round_order[current_round] and s.get("game_ids") for s in state.get("series", [])):
        return False
    planned = next_round_series({}, state, [s["winner_team_id"] for s in previous], current_round)
    if len(planned) != len(existing):
        return False
    existing_by_teams = {frozenset(s["team_ids"]):s for s in existing}
    if set(existing_by_teams) == {frozenset(s["team_ids"]) for s in planned}:
        for series in planned:
            existing_by_teams[frozenset(series["team_ids"])].update(bracket_slot=series["bracket_slot"], source_series_ids=series["source_series_ids"])
        return False
    shift = max(int(s.get("calendar_shift_days") or 0) for s in existing)
    for series in planned:
        if shift:
            series["calendar_shift_days"] = shift
    state["series"] = [s for s in state["series"] if s.get("round") != current_round] + planned
    return True


def next_round_series(canonical: dict[str, Any], state: dict[str, Any], winners: list[str], next_round: str) -> list[dict[str, Any]]:
    if next_round == "champion":
        return []
    del canonical
    source_round = {"conference_semifinals":"first_round", "conference_finals":"conference_semifinals", "finals":"conference_finals"}.get(next_round)
    sources = [s for s in state.get("series", []) if s.get("round") == source_round]
    eligible = set(winners)
    seeds = {}
    for conference in ("East", "West"):
        first = [s for s in state.get("series", []) if s.get("conference") == conference and s.get("round") == "first_round"]
        first_order = {s["id"]:i for i, s in enumerate(first)}
        first.sort(key=lambda s:s.get("bracket_slot", first_order[s["id"]]))
        for series, pair in zip(first, ((1, 8), (4, 5), (3, 6), (2, 7))):
            seeds.update(zip(series.get("team_ids", []), pair))

    def from_feeders(conference, feeders, slot):
        teams = [s.get("winner_team_id") for s in feeders]
        if len(teams) != 2 or any(team not in eligible for team in teams):
            return None
        if conference != "Finals":
            teams.sort(key=lambda team:seeds.get(team, 99))
        return {**playoff_series_record(conference, next_round, *teams), "bracket_slot":slot,
                "source_series_ids":[s["id"] for s in feeders]}

    if next_round == "finals":
        feeders = [s for conference in ("East", "West") for s in sources if s.get("conference") == conference]
        final = from_feeders("Finals", feeders, 0)
        return [final] if final else []
    new_series = []
    for conference in ["East", "West"]:
        feeders = [s for s in sources if s.get("conference") == conference]
        ordered = {s["id"]:i for i, s in enumerate(feeders)}
        feeders.sort(key=lambda s:s.get("bracket_slot", ordered[s["id"]]))
        for index in range(0, len(feeders), 2):
            series = from_feeders(conference, feeders[index:index + 2], index // 2)
            if series:
                new_series.append(series)
    return new_series


def playoff_series_record(conference: str, round_name: str, team_a: str, team_b: str) -> dict[str, Any]:
    return {
        "id": stable_id("playoff_series", "2026", conference, round_name, team_a, team_b),
        "conference": conference,
        "round": round_name,
        "status": "scheduled",
        "higher_seed_team_id": team_a,
        "lower_seed_team_id": team_b,
        "team_ids": [team_a, team_b],
        "wins": {team_a: 0, team_b: 0},
        "winner_team_id": None,
        "notes": "Generated next-round playoff scaffold series.",
    }


def save_standings_for_draft(canonical: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    rows = []
    for team_id, record in save.get("team_records", {}).items():
        team = teams.get(team_id)
        if not team:
            continue
        rows.append({"team_id": team_id, "team_abbrev": team["abbrev"], "wins": record.get("wins", 0), "losses": record.get("losses", 0)})
    return rows


def apply_offseason_roster_transitions(canonical: dict[str, Any], save: dict[str, Any], current_season: str, next_season: str, seed: int) -> dict[str, Any]:
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    contracts = {contract.get("player_id"): contract for contract in active.get("contracts", [])}
    annotate_star_asks(active, contracts, next_season, save)
    free_agents: list[str] = list(save.get("free_agent_player_ids", []))
    retired: list[str] = list(save.get("retired_player_ids", []))
    retired_this_offseason: list[str] = []
    expired: list[str] = []
    re_signing_commitments: dict[tuple[str, str], float] = {}
    for player in re_signing_order(active.get("players", [])):
        player_id = player["id"]
        if not player.get("team_id"):
            continue
        age = float(player.get("display_age", player.get("age")) or 27.0)
        contract = contracts.get(player_id)
        if should_retire(player, age, seed, next_season) and not (age < 42 and contract_has_salary_in_or_after(contract, next_season)):
            save.setdefault("roster_overrides", {})[player_id] = None
            if player_id not in retired:
                retired.append(player_id)
                retired_this_offseason.append(player_id)
            continue
        if contract and contract_last_season(contract) and contract_last_season(contract) < next_season:
            if should_ai_retain_expiring_player(save, player, current_season, seed) and ai_re_signing_allowed(
                canonical,
                save,
                player,
                player.get("team_id"),
                next_season,
                prepared_active=active,
                committed_salary_by_team_season=re_signing_commitments,
            ):
                retain_expiring_player(save, player, player.get("team_id"), current_season, next_season, seed)
                for season_row in ai_re_signing_contract_terms(save, player, next_season)["seasons"]:
                    key = (str(player.get("team_id")), str(season_row["season"]))
                    re_signing_commitments[key] = re_signing_commitments.get(key, 0.0) + float(season_row["salary"])
                players_key = (str(player.get("team_id")), RE_SIGNING_PLAYER_COUNT_KEY)
                re_signing_commitments[players_key] = re_signing_commitments.get(players_key, 0.0) + 1
                continue
            add_re_signing_right(save, current_season, player_id, player.get("team_id"))
            save.setdefault("roster_overrides", {})[player_id] = None
            if player_id not in free_agents:
                free_agents.append(player_id)
            expired.append(player_id)
    save["retired_player_ids"] = sorted(set(retired))
    clean_free_agency_state(save, current_season)
    free_agents = [player_id for player_id in free_agents if player_id not in set(save.get("retired_player_ids", []))]
    strategic_signed = strategic_free_agent_signings(canonical, save, free_agents, next_season, seed)
    signed = auto_fill_rosters(canonical, save, free_agents, next_season, seed)
    signed.update(strategic_signed)
    final_repairs = auto_fill_rosters(canonical, save, [], next_season, seed + 997)
    signed.update(final_repairs)
    save["free_agent_player_ids"] = sorted(pid for pid in set(free_agents) if pid not in signed and pid not in set(save.get("retired_player_ids", [])))
    league_exits = archive_excess_free_agents(canonical, save, current_season, next_season, seed)
    if retired_this_offseason:
        record_offseason_retirements(save, current_season, next_season, players, retired_this_offseason)
    if expired or retired_this_offseason or signed or league_exits:
        add_news(
            save,
            "offseason_rosters",
            f"Offseason roster transitions: {len(expired)} free agents, {len(retired_this_offseason)} retirements, {len(league_exits)} players left the active league pool, {len(strategic_signed)} AI signings, {len(signed) - len(strategic_signed)} depth repairs.",
            date_value=f"{season_start_year(next_season)}-09-01",
        )
    return {
        "expired_free_agents": len(expired),
        "retirements": len(retired_this_offseason),
        "league_exits": len(league_exits),
        "strategic_ai_signings": len(strategic_signed),
        "auto_depth_signings": len(signed) - len(strategic_signed),
        "final_roster_repairs": len(final_repairs),
        "free_agent_pool_count": len(save.get("free_agent_player_ids", [])),
    }


def build_year_in_review(canonical: dict[str, Any], save: dict[str, Any], team_id: str | None, season: str) -> dict[str, Any] | None:
    if not team_id:
        return None
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    roster_ids = {player_id for player_id, player in players.items() if player.get("team_id") == team_id}
    season_start = season_start_year(season)
    months = {f"{year}-{month:02d}" for year, month in [(season_start, 10), (season_start, 11), (season_start, 12), (season_start + 1, 1), (season_start + 1, 2), (season_start + 1, 3), (season_start + 1, 4), (season_start + 1, 5), (season_start + 1, 6), (season_start + 1, 7), (season_start + 1, 8)]}
    events_by_player: dict[str, list[dict[str, Any]]] = {}
    for event in save.get("development_events", []):
        if event.get("player_id") in roster_ids and event.get("month") in months:
            events_by_player.setdefault(event.get("player_id"), []).append(event)
    rows: list[dict[str, Any]] = []
    for player in sorted([row for row in players.values() if row.get("team_id") == team_id], key=display_minutes_projection, reverse=True):
        deltas: dict[str, float] = {}
        for event in events_by_player.get(player["id"], []):
            for trait, delta in (event.get("trait_deltas") or {}).items():
                deltas[trait] = deltas.get(trait, 0.0) + float(delta or 0.0)
        if deltas:
            best_trait, best_delta = max(deltas.items(), key=lambda item: item[1])
            worst_trait, worst_delta = min(deltas.items(), key=lambda item: item[1])
        else:
            best_trait, best_delta, worst_trait, worst_delta = None, 0.0, None, 0.0
        total = sum(deltas.values())
        rows.append(
            {
                "player_id": player["id"],
                "name": player.get("name"),
                "age": next_season_age(player),
                "position": player.get("position"),
                "minutes_projection": display_minutes_projection(player),
                "development_event_count": len(events_by_player.get(player["id"], [])),
                "total_trait_delta": round(total, 3),
                "trait_deltas": {key: round(value, 3) for key, value in sorted(deltas.items())},
                "best_trait": best_trait,
                "best_trait_delta": round(best_delta, 3),
                "worst_trait": worst_trait,
                "worst_trait_delta": round(worst_delta, 3),
            }
        )
    rows.sort(key=lambda item: (abs(float(item["total_trait_delta"])), item["minutes_projection"]), reverse=True)
    return {
        "id": stable_id("year_review", season, team_id),
        "season": season,
        "team_id": team_id,
        "generated_date": f"{season_start + 1}-09-01",
        "players": rows,
        "notes": "Development year-in-review summarizing saved monthly trait deltas before training camp.",
    }


AWARD_LABELS = {
    "MVP": "Most Valuable Player",
    "DPOY": "Defensive Player of the Year",
    "ROTY": "Rookie of the Year",
    "SMOY": "Sixth Man of the Year",
    "MIP": "Most Improved Player",
    "FMVP": "Finals MVP",
    "ALL_NBA_1": "All-NBA First Team",
    "ALL_NBA_2": "All-NBA Second Team",
    "ALL_NBA_3": "All-NBA Third Team",
}
AWARD_CRITERIA = {
    "MVP": "Scoring, playmaking and rebounding per game, the player's on-court value, his team's winning percentage and games played. 65-game rule.",
    "DPOY": "Defensive and rim-protection ratings, defensive effort and screen navigation, blocks and steals per game, team winning. 65-game rule.",
    "ROTY": "First-season players only: points, assists and rebounds per game, on-court value and minutes. The league's 65-game rule does not apply to this award; 35 games and 650 minutes are needed.",
    "SMOY": "Came off the bench in more games than he started (a game outside his team's five highest minutes counts as off the bench, because box scores do not record starters): bench scoring first, then playmaking, rebounding, on-court value and team winning. 65-game rule.",
    "MIP": "The largest rise in production per game (points + 0.4 x rebounds + 0.7 x assists + steals + 0.7 x blocks) over last season, which needs 25+ games last season and 10+ production per game now. 65-game rule.",
    "FMVP": "The champion's player with the highest total Game Score across the NBA Finals (points, shooting efficiency, rebounds, assists, steals, blocks and turnovers; fouls are not recorded).",
    "ALL_NBA": "Fifteen players, no positions (as in the real vote since 2024), ranked by the same score as MVP: First Team 1-5, Second 6-10, Third 11-15. 65-game rule.",
}


def award_qualifying_games(totals: dict[str, Any]) -> int:
    """Games that count toward the league's 65-game award rule: games of 20+ minutes, plus at most two games of
    15-20 minutes. Season totals recorded before these counters existed fall back to games played."""
    if "games_20_min" not in totals and "games_15_min" not in totals:
        return int(totals.get("games") or 0)
    return int(totals.get("games_20_min") or 0) + min(2, int(totals.get("games_15_min") or 0))


def award_production_per_game(totals: dict[str, Any]) -> float:
    """Production per game for Most Improved: points + 0.4 x rebounds + 0.7 x assists + steals + 0.7 x blocks."""
    games = max(1, int(totals.get("games") or 0))
    return (float(totals.get("points") or 0) + 0.4 * float(totals.get("rebounds") or 0) + 0.7 * float(totals.get("assists") or 0)
            + float(totals.get("steals") or 0) + 0.7 * float(totals.get("blocks") or 0)) / games


def finals_game_score(totals: dict[str, Any]) -> float:
    """Hollinger's Game Score from box-score totals. Rebounds count 0.4 each (box scores do not split offensive and
    defensive rebounds; 0.7 and 0.3 at the league's usual split) and fouls are not recorded."""
    get = lambda key: float(totals.get(key) or 0.0)  # noqa: E731
    return (get("points") + 0.4 * get("fgm") - 0.7 * get("fga") - 0.4 * (get("fta") - get("ftm")) + 0.4 * get("rebounds")
            + get("steals") + 0.7 * get("assists") + 0.7 * get("blocks") - get("turnovers"))


def previous_season_totals(canonical: dict[str, Any], save: dict[str, Any], season: str) -> dict[str, dict[str, Any]]:
    """Each player's totals from the season before `season`: the save's own history, or for a new save's first
    season the real 2025-26 box scores (matched by name)."""
    previous = next((item for item in reversed(save.get("season_history", []) or [])
                     if str(item.get("season") or "") < season and item.get("player_season_stats")), None)
    if previous:
        return previous.get("player_season_stats") or {}
    if season != CANONICAL_SEASON:
        return {}
    from .season_slides import real_season_summary

    real = real_season_summary().get("players") or {}
    out: dict[str, dict[str, Any]] = {}
    for player in canonical.get("players", []):
        row = real.get(normalize_name(player.get("name") or ""))
        if row:
            out[player["id"]] = row
    return out


def generate_league_awards(canonical: dict[str, Any], save: dict[str, Any], season: str, seed: int = 1) -> list[dict[str, Any]]:
    existing = [award for award in save.get("league_awards", []) if award.get("season") == season]
    if existing:
        return sorted(existing, key=lambda item: item.get("award", ""))
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    stats = save.get("player_season_stats", {})
    previous = previous_season_totals(active, save, season)
    candidates = []
    for player_id, totals in stats.items():
        player = players.get(player_id)
        if not player:
            continue
        games = int(totals.get("games") or 0)
        minutes_total = float(totals.get("minutes") or 0.0)
        if games < 35 or minutes_total < 650:
            continue
        attrs = player_attribute_summary(active, player_id)
        team_id = totals.get("team_id") or player.get("team_id")
        team_record = save.get("team_records", {}).get(team_id, {})
        team_games = max(1, int(team_record.get("wins", 0)) + int(team_record.get("losses", 0)))
        win_pct = float(team_record.get("wins", 0)) / team_games
        mpg = minutes_total / max(1, games)
        prior = previous.get(player_id) or {}
        qualifying = award_qualifying_games(totals)
        candidates.append(
            {
                "player_id": player_id,
                "player_name": player.get("name"),
                "team_id": team_id,
                "team_abbrev": teams.get(team_id, {}).get("abbrev", totals.get("team_abbrev") or player.get("team_abbrev")),
                "games": games,
                "qualifying_games": qualifying,
                "eligible": qualifying >= AWARD_MIN_GAMES,
                "bench_games": int(totals.get("games_bench") or 0),
                "top_minutes_games": int(totals.get("games_top_minutes") or 0),
                "bench_known": "games_bench" in totals or "games_top_minutes" in totals,
                "minutes_per_game": round(mpg, 1),
                "points_per_game": per_game_stat(totals, "points"),
                "rebounds_per_game": per_game_stat(totals, "rebounds"),
                "assists_per_game": per_game_stat(totals, "assists"),
                "steals_per_game": per_game_stat(totals, "steals"),
                "blocks_per_game": per_game_stat(totals, "blocks"),
                "production": round(award_production_per_game(totals), 2),
                "previous_games": int(prior.get("games") or 0),
                "previous_production": round(award_production_per_game(prior), 2) if prior else None,
                "overall": float(attrs.get("overall") or 50.0),
                "defense": float(attrs.get("defense") or 50.0),
                "rim_deterrence": float(attrs.get("rim_deterrence") or 50.0),
                "def_effort": float(attrs.get("def_effort") or 50.0),
                "screen_nav": float(attrs.get("screen_nav") or 50.0),
                "win_pct": round(win_pct, 3),
                "rookie": is_rookie_for_awards(player, season, save),
            }
        )
    if not candidates:
        return []

    def small_noise(player_id: str, award: str) -> float:
        digest = hashlib.sha256(f"{seed}:{season}:{award}:{player_id}".encode("utf-8")).hexdigest()
        return (int(digest[:8], 16) / 0xFFFFFFFF - 0.5) * 1.8

    def dpoy_score(row: dict[str, Any]) -> float:
        elite_anchor_bonus = max(0.0, row["rim_deterrence"] - 85.0) * 0.85 + max(0.0, row["defense"] - 80.0) * 0.45
        non_elite_penalty = max(0.0, 70.0 - row["rim_deterrence"]) * 0.25 + max(0.0, 70.0 - row["defense"]) * 0.20
        block_value = min(row["blocks_per_game"], 3.8) * 3.2
        steal_value = min(row["steals_per_game"], 2.4) * 2.6
        return (
            row["defense"] * 0.58
            + row["rim_deterrence"] * 0.55
            + row["def_effort"] * 0.20
            + row["screen_nav"] * 0.14
            + block_value
            + steal_value
            + row["win_pct"] * 5.0
            + elite_anchor_bonus
            - non_elite_penalty
            + small_noise(row["player_id"], "DPOY")
        )

    def mvp_score(row: dict[str, Any]) -> float:
        return (row["points_per_game"] * 1.25 + row["assists_per_game"] * 1.08 + row["rebounds_per_game"] * 0.66 + row["overall"] * 0.42
                + row["win_pct"] * 17.0 + min(5.0, row["games"] / 14.0) + small_noise(row["player_id"], "MVP"))

    def sixth_man_score(row: dict[str, Any]) -> float:
        return (row["points_per_game"] * 1.0 + row["assists_per_game"] * 0.5 + row["rebounds_per_game"] * 0.4 + row["overall"] * 0.25
                + row["win_pct"] * 6.0 + small_noise(row["player_id"], "SMOY"))

    def improved_score(row: dict[str, Any]) -> float:
        return row["production"] - float(row["previous_production"] or 0.0) + small_noise(row["player_id"], "MIP") * 0.2

    eligible = [row for row in candidates if row["eligible"]]
    pools = {
        "MVP": (eligible, mvp_score),
        "ROTY": ([row for row in candidates if row["rookie"]],
                 lambda row: row["points_per_game"] * 1.18 + row["assists_per_game"] * 0.92 + row["rebounds_per_game"] * 0.72 + row["overall"] * 0.48 + row["minutes_per_game"] * 0.18 + small_noise(row["player_id"], "ROTY")),
        "DPOY": (eligible, dpoy_score),
        "SMOY": ([row for row in eligible if row["bench_known"] and row["bench_games"] > row["top_minutes_games"]], sixth_man_score),
        "MIP": ([row for row in eligible if row["previous_production"] is not None and row["previous_games"] >= 25 and row["production"] >= 10.0
                 and row["production"] > float(row["previous_production"])], improved_score),
    }
    end_date = save.get("state", {}).get("current_date") or f"{season_end_year(season)}-06-30"

    def record(award_name: str, winner: dict[str, Any], score: float, *, record_id: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        base = award_name if not award_name.startswith("ALL_NBA") else "ALL_NBA"
        return {
            "id": record_id or stable_id("league_award", season, award_name),
            "season": season,
            "award": award_name,
            "label": AWARD_LABELS.get(award_name, award_name),
            "player_id": winner["player_id"],
            "player_name": winner["player_name"],
            "team_id": winner["team_id"],
            "team_abbrev": winner["team_abbrev"],
            "score": round(score, 3),
            "stat_line": {
                "pts": winner["points_per_game"],
                "reb": winner["rebounds_per_game"],
                "ast": winner["assists_per_game"],
                "stl": winner["steals_per_game"],
                "blk": winner["blocks_per_game"],
                "gp": winner["games"],
            },
            "criteria": AWARD_CRITERIA.get(base, ""),
            **(extra or {}),
            "notes": "Award vote proxy from saved season stats, team success, games played (65-game rule) and the player's ratings.",
        }

    awards: list[dict[str, Any]] = []
    for award_name, (pool, score_fn) in pools.items():
        if not pool:
            continue
        winner = max(pool, key=score_fn)
        extra = None
        if award_name == "SMOY":
            extra = {"bench_games": winner["bench_games"], "top_minutes_games": winner["top_minutes_games"]}
        if award_name == "MIP":
            extra = {"production": winner["production"], "previous_production": winner["previous_production"]}
        awards.append(record(award_name, winner, score_fn(winner), extra=extra))
        add_news(save, "award", f"{winner['player_name']} wins {AWARD_LABELS[award_name]} for {season} ({winner['team_abbrev']}).", date_value=end_date)
    for index, row in enumerate(sorted(eligible, key=lambda row: (-mvp_score(row), row["player_id"]))[:15]):
        team_no = index // 5 + 1
        name = f"ALL_NBA_{team_no}"
        awards.append(record(name, row, mvp_score(row), record_id=stable_id("league_award", season, name, row["player_id"]),
                             extra={"vote_rank": index + 1}))
    finals = save.get("finals_mvp") or {}
    if finals.get("player_id") and str(finals.get("season") or season) == season:
        totals = stats.get(finals["player_id"], {})
        awards.append({
            "id": stable_id("league_award", season, "FMVP"), "season": season, "award": "FMVP", "label": AWARD_LABELS["FMVP"],
            "player_id": finals["player_id"], "player_name": finals.get("player_name"), "team_id": finals.get("team_id"),
            "team_abbrev": finals.get("team_abbrev"), "score": finals.get("impact_score"),
            "stat_line": finals.get("finals_line") or {"pts": per_game_stat(totals, "points"), "reb": per_game_stat(totals, "rebounds"),
                                                         "ast": per_game_stat(totals, "assists"), "gp": int(totals.get("games") or 0)},
            "criteria": AWARD_CRITERIA["FMVP"], "notes": "Best Game Score on the champion across the NBA Finals.",
        })
    save.setdefault("league_awards", []).extend(awards)
    save["league_awards"] = sorted(
        {award["id"]: award for award in save["league_awards"]}.values(),
        key=lambda item: (item.get("season", ""), item.get("award", ""), int(item.get("vote_rank") or 0)),
    )
    return awards


def is_rookie_for_awards(player: dict[str, Any], season: str, save: dict[str, Any] | None = None) -> bool:
    draft_year = player.get("draft_year") or rookie_draft_year_from_save(player.get("id"), save)
    if draft_year is not None:
        try:
            return int(draft_year) == season_start_year(season)
        except (TypeError, ValueError):
            return False
    if str(player.get("source_kind") or "").startswith("generated_rookie"):
        return False
    if str(season) != CANONICAL_SEASON:
        return False
    try:
        return float(player.get("display_age", player.get("age")) or 99) <= 21 and float(player.get("minutes_projection") or 0.0) <= 30
    except (TypeError, ValueError):
        return False


def rookie_draft_year_from_save(player_id: str | None, save: dict[str, Any] | None) -> int | None:
    if not player_id or not save:
        return None
    for rookie in save.get("incoming_rookies", []):
        if player_id not in {rookie.get("player_id"), rookie.get("id")}:
            continue
        try:
            return int(rookie.get("draft_year") or rookie.get("season"))
        except (TypeError, ValueError):
            return None
    return None


def next_season_age(player: dict[str, Any]) -> float | None:
    value = player.get("display_age", player.get("age"))
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def prepare_free_agency_pool(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    current_season = save.get("meta", {}).get("season") or CANONICAL_SEASON
    clean_free_agency_state(save, current_season)
    if current_season in set(save.get("free_agency_prepared_seasons", [])):
        return {"status": "already_prepared", "free_agent_pool_count": len(save.get("free_agent_player_ids", []))}
    seed = int(save.get("meta", {}).get("seed") or 1)
    next_season = season_label_from_start(season_start_year(current_season) + 1)
    retirement_count = prepare_offseason_retirements(canonical, save, current_season, next_season, seed)
    active = canonical_with_save(canonical, save)
    contracts = {contract.get("player_id"): contract for contract in active.get("contracts", [])}
    annotate_star_asks(active, contracts, next_season, save)
    free_agents = set(save.get("free_agent_player_ids", []))
    expired: list[str] = []
    re_signing_commitments: dict[tuple[str, str], float] = {}
    for player in re_signing_order(active.get("players", [])):
        player_id = player.get("id")
        if not player_id or not player.get("team_id"):
            continue
        contract = contracts.get(player_id)
        last = contract_last_season(contract) if contract else None
        if last and last <= current_season:
            if should_ai_retain_expiring_player(save, player, current_season, seed) and ai_re_signing_allowed(
                canonical,
                save,
                player,
                player.get("team_id"),
                next_season,
                prepared_active=active,
                committed_salary_by_team_season=re_signing_commitments,
            ):
                retain_expiring_player(save, player, player.get("team_id"), current_season, next_season, seed)
                for season_row in ai_re_signing_contract_terms(save, player, next_season)["seasons"]:
                    key = (str(player.get("team_id")), str(season_row["season"]))
                    re_signing_commitments[key] = re_signing_commitments.get(key, 0.0) + float(season_row["salary"])
                players_key = (str(player.get("team_id")), RE_SIGNING_PLAYER_COUNT_KEY)
                re_signing_commitments[players_key] = re_signing_commitments.get(players_key, 0.0) + 1
                continue
            add_re_signing_right(save, current_season, player_id, player.get("team_id"))
            save.setdefault("roster_overrides", {})[player_id] = None
            free_agents.add(player_id)
            expired.append(player_id)
    save["free_agent_player_ids"] = sorted(pid for pid in free_agents if pid not in set(save.get("retired_player_ids", [])))
    clean_free_agency_state(save, current_season)
    save.setdefault("free_agency_prepared_seasons", []).append(current_season)
    if expired:
        add_news(
            save,
            "free_agency",
            f"The re-signing period opened with {len(expired)} expired contracts entering the offseason player pool.",
            date_value=save.get("state", {}).get("current_date"),
        )
    return {
        "status": "prepared",
        "expired_contracts": len(expired),
        "retirements": retirement_count,
        "free_agent_pool_count": len(save.get("free_agent_player_ids", [])),
    }


def record_offseason_retirements(save: dict[str, Any], current_season: str, next_season: str,
                                players: dict[str, dict[str, Any]], player_ids: list[str]) -> None:
    report_id = stable_id("retirement_report", current_season, next_season)
    rows = {
        row["player_id"]: dict(row)
        for report in save.get("retirement_reports", []) if report.get("id") == report_id
        for row in report.get("retirements", []) if row.get("player_id")
    }
    for player_id in player_ids:
        player = players.get(player_id, {})
        rows.setdefault(player_id, {
            "player_id": player_id, "name": player.get("name"), "position": player.get("position"),
            "age": round(float(player.get("display_age", player.get("age")) or 0.0), 1),
        })
    report = {
        "id": report_id, "season": current_season, "next_season": next_season,
        "date": f"{season_start_year(next_season)}-07-01",
        "retirements": sorted(rows.values(), key=lambda row: (-float(row.get("age") or 0), row.get("name") or "", row["player_id"])),
    }
    upsert_by_id(save, "retirement_reports", report)
    names = ", ".join(row["name"] for row in report["retirements"][:5] if row.get("name"))
    add_news(save, "retirement", f"Retirement report: {names or len(rows)} player(s) retired.", date_value=report["date"])


def prepare_offseason_retirements(canonical: dict[str, Any], save: dict[str, Any], current_season: str, next_season: str, seed: int) -> int:
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    contracts_by_player = {contract.get("player_id"): contract for contract in active.get("contracts", [])}
    retired = set(save.get("retired_player_ids", []))
    retired_this_offseason: list[str] = []
    for player in active.get("players", []):
        player_id = player.get("id")
        if not player_id or player_id in retired or not player.get("team_id"):
            continue
        age = float(player.get("display_age", player.get("age")) or 27.0)
        if not should_retire(player, age, seed, next_season):
            continue
        if age < 42 and contract_has_salary_in_or_after(contracts_by_player.get(player_id), next_season):
            continue
        save.setdefault("roster_overrides", {})[player_id] = None
        retired.add(player_id)
        retired_this_offseason.append(player_id)
    if not retired_this_offseason:
        save["retired_player_ids"] = sorted(retired)
        return 0
    save["retired_player_ids"] = sorted(retired)
    save["free_agent_player_ids"] = [
        player_id for player_id in save.get("free_agent_player_ids", [])
        if player_id not in retired
    ]
    record_offseason_retirements(save, current_season, next_season, players, retired_this_offseason)
    clean_free_agency_state(save, current_season)
    return len(retired_this_offseason)


def archive_excess_free_agents(
    canonical: dict[str, Any],
    save: dict[str, Any],
    current_season: str,
    next_season: str,
    seed: int,
    target: int = OFFSEASON_FREE_AGENT_POOL_TARGET,
) -> list[dict[str, Any]]:
    """Move long-term fringe free agents out of the active league population.

    The NBA adds a draft class every year, so an equally real exit path is
    necessary to keep the playable talent pool stable. Historical players and
    stats stay in the save; only their eligibility for future roster activity
    changes. Recent draftees, young prospects, and rotation-level free agents
    are deliberately protected from this housekeeping pass.
    """
    active = canonical_with_save(canonical, save)
    players = players_by_id_index(active)
    retired = set(save.get("retired_player_ids") or [])
    pool = sorted(
        player_id
        for player_id in set(save.get("free_agent_player_ids") or [])
        if player_id in players and player_id not in retired
    )
    if not pool:
        return []

    current_draft_year = season_end_year(current_season)
    recent_draftees = {
        str(row.get("player_id"))
        for row in save.get("incoming_rookies", [])
        if row.get("player_id")
        and str(row.get("draft_year") or "").isdigit()
        and int(str(row.get("draft_year"))) >= current_draft_year - 1
    }
    released = save.get("released_free_agents") or {}
    rows: list[dict[str, Any]] = []
    protected: set[str] = set()
    forced_exit: set[str] = set()
    for player_id in pool:
        player = players[player_id]
        ratings = player_attribute_summary(active, player_id)
        overall = float(ratings.get("overall") or 0.0)
        minutes = display_minutes_projection(player)
        age = float(player.get("display_age", player.get("age")) or 27.0)
        release = released.get(player_id) or {}
        release_date = str(release.get("release_date") or "")
        recently_released = release.get("status") == "available" and release_date[:4] in {
            str(season_start_year(current_season)),
            str(season_start_year(current_season) + 1),
        }
        if (
            player_id in recent_draftees
            or age <= 21.99
            or overall >= 58.0
            or (overall >= 53.0 and minutes >= 18.0)
            or (recently_released and overall >= 50.0)
        ):
            protected.add(player_id)
        if (age >= 40.0 and overall < 62.0) or (age >= 38.0 and overall < 52.0):
            forced_exit.add(player_id)
        noise = int(
            hashlib.sha256(f"{seed}:{next_season}:{player_id}:league_exit".encode("utf-8")).hexdigest()[:8],
            16,
        ) / 0xFFFFFFFF
        rows.append(
            {
                "player_id": player_id,
                "name": player.get("name"),
                "age": round(age, 1),
                "position": player.get("position"),
                "overall": round(overall, 1),
                "minutes_projection": minutes,
                "retention_score": overall + minutes * 0.24 - max(0.0, age - 31.0) * 0.7 + noise * 0.25,
            }
        )

    exit_ids = set(forced_exit - recent_draftees)
    remaining_count = len(pool) - len(exit_ids)
    excess = max(0, remaining_count - max(0, int(target)))
    if excess:
        eligible = sorted(
            (row for row in rows if row["player_id"] not in protected and row["player_id"] not in exit_ids),
            key=lambda row: (float(row["retention_score"]), -float(row["age"]), str(row["player_id"])),
        )
        exit_ids.update(row["player_id"] for row in eligible[:excess])
    if not exit_ids:
        return []

    exit_rows = []
    by_id = {row["player_id"]: row for row in rows}
    exit_date = f"{season_start_year(next_season)}-09-01"
    for player_id in sorted(exit_ids):
        row = dict(by_id[player_id])
        row.pop("retention_score", None)
        row.update(
            {
                "id": stable_id("league_exit", next_season, player_id),
                "date": exit_date,
                "season": current_season,
                "next_season": next_season,
                "reason": "unsigned_fringe_player_left_active_league_pool",
            }
        )
        exit_rows.append(row)

    save["free_agent_player_ids"] = sorted(set(pool) - exit_ids)
    save["retired_player_ids"] = sorted(retired | exit_ids)
    save["league_exit_player_ids"] = sorted(set(save.get("league_exit_player_ids") or []) | exit_ids)
    records = {row.get("id"): row for row in save.get("league_exit_records", []) if row.get("id")}
    records.update({row["id"]: row for row in exit_rows})
    save["league_exit_records"] = sorted(records.values(), key=lambda row: (row.get("date", ""), row.get("player_id", "")))
    clean_free_agency_state(save, current_season)
    return exit_rows


def add_re_signing_right(save: dict[str, Any], season: str, player_id: str, team_id: str | None) -> None:
    if not player_id or not team_id:
        return
    record = {
        "id": stable_id("re_signing_right", season, team_id, player_id),
        "season": season,
        "player_id": player_id,
        "team_id": team_id,
        "status": "exclusive_review_window",
    }
    existing = [
        item for item in save.setdefault("re_signing_rights", [])
        if item.get("id") != record["id"] and item.get("player_id") != player_id
    ]
    existing.append(record)
    save["re_signing_rights"] = sorted(existing, key=lambda item: (item.get("season", ""), item.get("team_id", ""), item.get("player_id", "")))


def clean_free_agency_state(save: dict[str, Any], current_season: str | None = None) -> None:
    retired = set(save.get("retired_player_ids", []))
    save["free_agent_player_ids"] = sorted(pid for pid in set(save.get("free_agent_player_ids", [])) if pid not in retired)
    rights = []
    for right in save.get("re_signing_rights", []):
        if right.get("player_id") in retired:
            continue
        if current_season and right.get("status") == "exclusive_review_window" and right.get("season") != current_season:
            continue
        rights.append(right)
    save["re_signing_rights"] = sorted(rights, key=lambda item: (item.get("season", ""), item.get("team_id", ""), item.get("player_id", "")))
    fa_state = save.get("free_agency_state")
    if isinstance(fa_state, dict):
        season = str(fa_state.get("season") or current_season or "")
        for key in ["active_offers", "accepted_deals", "rejected_offers", "withdrawn_offers"]:
            filtered = []
            for item in fa_state.get(key, []):
                if item.get("player_id") in retired:
                    continue
                if season and item.get("season") and item.get("season") != season:
                    continue
                filtered.append(item)
            fa_state[key] = filtered
        if isinstance(fa_state.get("player_asks"), dict):
            fa_state["player_asks"] = {
                pid: ask for pid, ask in fa_state["player_asks"].items()
                if pid not in retired
            }


STAR_RETENTION_MAX_AGE = 33.0
# KEEP-STARS: a "franchise star" is one of the league's best FRANCHISE_STAR_RANK players by current on-court value (the
# trade code's valuation). His team keeps him almost always, paying into the tax if needed (payroll_plan), unless it is
# rebuilding and he is FRANCHISE_STAR_REBUILD_AGE or older (a rebuilding team would trade him instead).
FRANCHISE_STAR_RANK = 15
FRANCHISE_STAR_REBUILD_AGE = 31.0


def re_signing_order(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A front office settles its stars' contracts first (TRADE-VOLUME-2): stars by market price, then the rest in
    roster order. Before, players were re-signed in roster order, so a team's cheaper re-signings could use up the
    room its star needed (Denver lost Nikola Jokic that way in the two-season test)."""
    stars = sorted((p for p in players if p.get("_star_ask_millions")),
                   key=lambda p: (-float(p["_star_ask_millions"]), str(p.get("id"))))
    return stars + [p for p in players if not p.get("_star_ask_millions")]


def annotate_star_asks(active: dict[str, Any], contracts: dict[str, dict[str, Any]], next_season: str,
                       save: dict[str, Any] | None = None) -> None:
    """Mark the expiring players on the rows of ``active`` (a working copy) for the AI re-signing pass below.

    - ``_star_ask_millions``: a starter-or-better's market price (TRADE-VOLUME-2, contract_ai.star_market_ask_millions).
    - ``_bird``: his team's Bird rights (KEEP-STARS, contract_ai.bird_rights), when ``save`` is given.
    - ``_star_rank`` / ``_team_phase``: his league rank by on-court value and his team's window phase."""
    from .contract_ai import bird_rights, star_market_ask_millions, years_of_service
    from .transactions import with_transaction_context
    current = season_label_from_start(season_start_year(next_season) - 1)
    expiring_all = [p for p in active.get("players", []) if p.get("team_id")
                    and (contract_last_season(contracts.get(p.get("id"))) or next_season) < next_season]
    if save is not None:
        for player in expiring_all:
            player["_bird"] = bird_rights(save, player, player.get("team_id"), current, contracts.get(player.get("id")))
    expiring = [p for p in expiring_all if display_minutes_projection(p) >= 24.0]
    if not expiring:
        return
    priced = with_transaction_context(active)
    by_id = {p.get("id"): p for p in priced.get("players", [])}
    on_team = {p.get("id") for p in priced.get("players", []) if p.get("team_id")}
    values = sorted(((float(v.get("on_court_value") or 0.0), str(v.get("player_id")))
                     for v in priced.get("player_asset_valuations", []) or [] if v.get("player_id") in on_team),
                    reverse=True)
    rank = {player_id: index + 1 for index, (_, player_id) in enumerate(values)}
    from .payroll_plan import team_phase
    for player in expiring:
        try:
            ask = star_market_ask_millions(priced, by_id.get(player["id"], player), next_season)
        except (KeyError, ValueError, TypeError):
            ask = None
        if ask:
            player["_star_ask_millions"] = ask
            player["_star_rank"] = rank.get(player["id"])
            player["_years_of_service"] = years_of_service(player, next_season)
            if save is not None:
                player["_team_phase"] = team_phase(priced, save, str(player.get("team_id")))


YOUNG_STAR_MAX_SERVICE = 4   # a player coming off his rookie-scale deal (four seasons): a restricted free agent


def is_franchise_star(player: dict[str, Any]) -> bool:
    """A top-15 player, or a starter-or-better coming off his rookie deal with the team (KEEP-STARS).

    The second case stands in for restricted free agency, which the game does not model: real teams match offers
    for their good young players almost without exception (Hoops Rumors glossary, "Restricted free agency")."""
    if not player.get("_star_ask_millions"):
        return False
    if int(player.get("_star_rank") or 999) <= FRANCHISE_STAR_RANK:
        return True
    bird = player.get("_bird") or {}
    return int(bird.get("seasons") or 99) <= YOUNG_STAR_MAX_SERVICE and float(player.get("age") or 99) <= 25.0 \
        and int(player.get("_years_of_service") or 99) <= YOUNG_STAR_MAX_SERVICE


def should_ai_retain_expiring_player(save: dict[str, Any], player: dict[str, Any], season: str, seed: int) -> bool:
    team_id = player.get("team_id")
    if not team_id or team_id in human_controlled_team_ids(save):
        return False
    age = float(player.get("display_age", player.get("age")) or 27.0)
    # KEEP-STARS: a team keeps a top-15 player at any age unless it is rebuilding and he is 31 or older. Real
    # franchise stars almost never leave in free agency: Bird rights let their team pay them over the cap and offer a
    # fifth year (cap_rules), and contenders pay the tax to keep them.
    if is_franchise_star(player):
        return not (player.get("_team_phase") == "rebuilding" and age >= FRANCHISE_STAR_REBUILD_AGE)
    # A team keeps its expiring star (starter-or-better market price, 33 or younger) whenever its cap and payroll
    # plan allow (ai_re_signing_allowed). Before it was a dice roll capped at 72%, and Denver let Nikola Jokic walk in
    # 2028 (he signed with Boston for $18.9M). Real stars re-sign or extend almost without exception.
    if player.get("_star_ask_millions") and age <= STAR_RETENTION_MAX_AGE:
        return True
    minutes = display_minutes_projection(player)
    age = float(player.get("age") or 27.0)
    record = save.get("team_records", {}).get(team_id, {})
    games = max(1, int(record.get("wins", 0)) + int(record.get("losses", 0)))
    win_pct = float(record.get("wins", 0)) / games
    stats = save.get("player_season_stats", {}).get(player.get("id"), {})
    ppg = per_game_stat(stats, "points")
    threshold = 0.08 + min(0.34, minutes / 78.0) + min(0.12, ppg / 260.0)
    threshold += max(0.0, win_pct - 0.5) * 0.22
    threshold -= max(0.0, age - 32.0) * 0.025
    if minutes >= 28:
        threshold += 0.1
    if minutes < 10:
        threshold -= 0.08
    roll = int(hashlib.sha256(f"{seed}:{season}:{player['id']}:ai_retain_expiring".encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return roll < clamp(threshold, 0.02, 0.72)


def star_re_signing_years(age: float, bird_level: str | None, default: int) -> int:
    """Years on a star's re-signing (KEEP-STARS): five for a young star with full Bird rights (only his own team can
    offer the fifth year), four through 30, three through 33, otherwise the usual rule."""
    if age <= 27:
        return 5 if bird_level == "full" else 4
    if age <= 30:
        return 4
    if age <= 33:
        return max(default, 3)
    return default


def ai_re_signing_contract_terms(save: dict[str, Any], player: dict[str, Any], next_season: str) -> dict[str, Any]:
    minutes = display_minutes_projection(player)
    age = float(player.get("age") or 27.0)
    score = minutes * 0.72 + per_game_stat(save.get("player_season_stats", {}).get(player.get("id"), {}), "points") * 0.25
    years = 3 if age <= 29 and minutes >= 24 else 2 if age <= 33 and minutes >= 16 else 1
    salary = int(round(clamp(2_200_000 + minutes * 520_000 + max(0.0, score - 18.0) * 320_000, 2_000_000, 32_000_000)))
    raise_rate = 0.035
    star = float(player.get("_star_ask_millions") or 0.0)
    if star * 1_000_000 > salary:
        # TRADE-VOLUME-2: a starter-or-better re-signs at his market price (annotate_star_asks), not the minutes rule
        # capped at $32M; the price is already within the maximum salary for his years in the league.
        salary = int(round(star * 1_000_000))
        # KEEP-STARS: the years and raises his own team can offer with his Bird rights (8% with full or Early Bird).
        from .cap_rules import bird_raise
        bird_level = (player.get("_bird") or {}).get("level")
        years = star_re_signing_years(age, bird_level, years)
        raise_rate = bird_raise(bird_level)
    seasons = [
        {
            "season": season_label_from_start(season_start_year(next_season) + offset),
            "salary": int(round(salary * ((1.0 + raise_rate) ** offset))),
            "option_type": None,
            "guarantee_status": "ai_re_signing",
            "guaranteed_salary": int(round(salary * ((1.0 + raise_rate) ** offset))),
            "protection_basis": "negotiated",
        }
        for offset in range(years)
    ]
    return {"salary": salary, "years": years, "seasons": seasons, "score": score}


def re_signing_within_bird_rights(player: dict[str, Any], salary: float) -> bool:
    """Whether his own team can pay this first-year salary with his Bird rights, over the cap and the hard cap."""
    bird = player.get("_bird") or {}
    return bool(bird) and float(salary) <= float(bird.get("limit") or 0.0) + 1.0


def ai_re_signing_fits_hard_cap(
    canonical: dict[str, Any],
    save: dict[str, Any],
    player: dict[str, Any],
    team_id: str | None,
    next_season: str,
    *,
    prepared_active: dict[str, Any] | None = None,
    committed_salary_by_team_season: dict[tuple[str, str], float] | None = None,
) -> bool:
    if not team_id:
        return False
    terms = ai_re_signing_contract_terms(save, player, next_season)
    # KEEP-STARS: re-signing your own free agent within his Bird rights never meets the hard cap (real CBA: Bird
    # re-signings do not trigger a hard cap). Above the limit the team needs room like any other signing.
    if re_signing_within_bird_rights(player, terms["salary"]):
        return True
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    commitments = committed_salary_by_team_season or {}
    for season_row in terms["seasons"]:
        season = str(season_row["season"])
        cap = team_cap_summary(active, save, team_id, season)
        available = float(cap.get("hard_cap_space_millions") or 0.0) * 1_000_000
        available -= float(commitments.get((str(team_id), season), 0.0))
        if float(season_row["salary"]) > available + 10_000:
            return False
    return True


RE_SIGNING_PLAYER_COUNT_KEY = "_players"   # commitments[(team_id, this)]: players re-signed earlier in the same pass


def ai_re_signing_fits_payroll_plan(
    canonical: dict[str, Any],
    save: dict[str, Any],
    player: dict[str, Any],
    team_id: str | None,
    next_season: str,
    *,
    prepared_active: dict[str, Any] | None = None,
    committed_salary_by_team_season: dict[tuple[str, str], float] | None = None,
) -> bool:
    """The front office keeps its own free agent only if the tax bill it adds is worth it (payroll_plan, TRADE-VOLUME).
    A franchise star is worth a much larger bill (KEEP-STARS)."""
    if not team_id:
        return False
    from .payroll_plan import payroll_check
    terms = ai_re_signing_contract_terms(save, player, next_season)
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    commitments = committed_salary_by_team_season or {}
    check = payroll_check(
        active, save, str(team_id), next_season, add_salary=float(terms["seasons"][0]["salary"]), roster_delta=1,
        minutes=display_minutes_projection(player), kind="re_signing", age=player.get("display_age", player.get("age")),
        committed=float(commitments.get((str(team_id), str(next_season)), 0.0)),
        committed_players=int(commitments.get((str(team_id), RE_SIGNING_PLAYER_COUNT_KEY), 0)),
        franchise_star=is_franchise_star(player),
    )
    return bool(check["ok"])


def ai_re_signing_allowed(canonical: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team_id: str | None,
                          next_season: str, **kwargs: Any) -> bool:
    return (ai_re_signing_fits_hard_cap(canonical, save, player, team_id, next_season, **kwargs)
            and ai_re_signing_fits_payroll_plan(canonical, save, player, team_id, next_season, **kwargs))


def retain_expiring_player(save: dict[str, Any], player: dict[str, Any], team_id: str | None, current_season: str, next_season: str, seed: int) -> None:
    if not team_id:
        return
    terms = ai_re_signing_contract_terms(save, player, next_season)
    minutes = display_minutes_projection(player)
    salary = int(terms["salary"])
    years = int(terms["years"])
    seasons = terms["seasons"]
    score = float(terms["score"])
    from .contract_ai import keep_bird_clock
    keep_bird_clock(save, player, team_id, next_season)   # a re-signing keeps his Bird clock (KEEP-STARS)
    save.setdefault("contract_overrides", {})[player["id"]] = {
        "team_id": team_id,
        "seasons": seasons,
        "status": "ai_re_signing",
        "original_contract_years": years,
        "signed_season": next_season,
    }
    save.setdefault("transaction_logs", []).append(
        {
            "id": stable_id("transaction_log", "ai_re_signing", current_season, team_id, player["id"]),
            "date": f"{season_start_year(next_season)}-07-01",
            "transaction_type": "ai_re_signing",
            "proposal_id": stable_id("ai_re_signing", next_season, team_id, player["id"]),
            "status": "applied_to_save_ledger",
            "teams": [team_id],
            "assets": {"player_id": player["id"], "name": player["name"], "salary": salary, "years": years},
            "evaluations": [{"minutes": minutes, "score": round(score, 2)}],
            "source_ids": ["src_contract_market_config_v1"],
            "notes": "AI retained an expiring own free agent before the open market based on role, performance, age, team record, and deterministic seed.",
        }
    )
    team = {"id": team_id, "abbrev": str(team_id).replace("team_", "").upper()}
    maybe_add_major_free_agent_news(save, team, player, salary, next_season)


def ensure_draft_processed(canonical: dict[str, Any], save: dict[str, Any], draft_year: str, seed: int) -> dict[str, Any]:
    if any(str(item.get("draft_year")) == str(draft_year) for item in save.get("incoming_rookies", [])):
        signed = sign_unsigned_rookies(save, draft_year)
        save["pending_draft_selections"] = []
        save.setdefault("draft_state", {}).update(status="completed", completed_year=str(draft_year))
        return {"status": "already_present", "rookies_signed": signed}
    from .draft import rookie_player_record, rookie_trait_records, simulate_draft

    draft = simulate_draft(canonical_with_save(canonical, save), str(draft_year), seed=seed)
    save.setdefault("pending_draft_selections", []).extend(draft.get("pending_draft_selections", []))
    for rights in draft.get("draft_rights", []):
        upsert_by_id(save, "draft_rights", rights)
    for contract in draft.get("rookie_contracts", []):
        contract["status"] = "signed"
        upsert_by_id(save, "rookie_contracts", contract)
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    contracts = {contract.get("prospect_id"): contract for contract in draft.get("rookie_contracts", [])}
    traits_by_prospect: dict[str, list[dict[str, Any]]] = {}
    for trait in draft.get("draft_prospect_traits", []):
        traits_by_prospect.setdefault(trait.get("prospect_id"), []).append(trait)
    signed_count = 0
    for rookie in draft.get("incoming_rookies", []):
        team = teams.get(rookie.get("team_id"), {"id": rookie.get("team_id"), "abbrev": rookie.get("team_abbrev")})
        prospect = {
            "id": rookie.get("prospect_id"),
            "name": rookie.get("name"),
            "position": rookie.get("position"),
            "age": rookie.get("age"),
            "height_inches": rookie.get("height_inches"),
            "weight_lbs": rookie.get("weight_lbs"),
            "archetype": rookie.get("archetype"),
            "potential": rookie.get("potential"),
            "current_ability": rookie.get("current_ability"),
            "medical_profile": rookie.get("medical_profile") or {},
            "source_ids": rookie.get("source_ids") or [],
        }
        contract = contracts.get(rookie.get("prospect_id"))
        if not contract:
            continue
        from .schema import RookieContractProjection

        contract_obj = RookieContractProjection(**contract)
        player = rookie_player_record(rookie, prospect, team, contract_obj)
        rookie["player_id"] = player["id"]
        rookie["roster_status"] = "signed_rookie"
        rookie["rights_status"] = "signed_rookie_contract"
        upsert_by_id(save, "incoming_rookies", rookie)
        upsert_by_id(save, "generated_players", player)
        for trait in rookie_trait_records(player, prospect, traits_by_prospect.get(rookie.get("prospect_id"), [])):
            upsert_by_id(save, "generated_traits", trait)
        save.setdefault("roster_overrides", {})[player["id"]] = team.get("id")
        save.setdefault("contract_overrides", {})[player["id"]] = {
            "team_id": team.get("id"),
            "seasons": contract.get("seasons", []),
            "status": "signed_rookie_contract",
            "original_contract_years": len(contract.get("seasons", [])),
            "signed_season": contract.get("seasons", [{}])[0].get("season"),
        }
        save.setdefault("rotation_baselines", {})[player["id"]] = float(player.get("minutes_projection") or 0.0)
        signed_count += 1
    if signed_count:
        add_news(save, "draft", f"{draft_year} AI draft processed and {signed_count} rookies signed.", date_value=f"{draft_year}-06-26")
    save["pending_draft_selections"] = []
    state = save.setdefault("draft_state", {})
    state["status"] = "completed"
    state["current_index"] = max(int(state.get("current_index") or 0), int(draft.get("selection_count") or 0))
    state["completed_year"] = str(draft_year)
    return {"status": "processed_ai_draft", "selection_count": draft.get("selection_count", 0), "rookies_signed": signed_count}


def sign_unsigned_rookies(save: dict[str, Any], draft_year: str) -> int:
    signed = 0
    for rookie in save.get("incoming_rookies", []):
        if str(rookie.get("draft_year")) != str(draft_year) or rookie.get("roster_status") == "signed_rookie":
            continue
        player_id = rookie.get("player_id")
        if not player_id:
            continue
        save.setdefault("roster_overrides", {})[player_id] = rookie.get("team_id")
        player = next((item for item in save.get("generated_players", []) if item.get("id") == player_id), None)
        if player:
            save.setdefault("rotation_baselines", {})[player_id] = float(player.get("minutes_projection") or 0.0)
        rookie["roster_status"] = "signed_rookie"
        rookie["rights_status"] = "signed_rookie_contract"
        signed += 1
    return signed


def upsert_by_id(save: dict[str, Any], collection: str, record: dict[str, Any]) -> None:
    records = [item for item in save.get(collection, []) if item.get("id") != record.get("id")]
    records.append(record)
    save[collection] = records


def should_retire(player: dict[str, Any], age: float, seed: int, next_season: str) -> bool:
    if age < 35:
        return False
    minutes = display_minutes_projection(player)
    if age >= 41:
        threshold = 0.95
    elif age >= 40:
        threshold = 0.74 + max(0.0, 10.0 - minutes) * 0.025
    elif age >= 38:
        threshold = 0.47 + max(0.0, 18.0 - minutes) * 0.026
    elif age >= 36:
        threshold = 0.16 + max(0.0, 14.0 - minutes) * 0.02
    else:
        threshold = 0.06 + max(0.0, 10.0 - minutes) * 0.012 if minutes < 18 else 0.0
    roll = int(hashlib.sha256(f"{seed}:{next_season}:{player['id']}:retire".encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return roll < threshold


def contract_has_salary_in_or_after(contract: dict[str, Any] | None, season: str) -> bool:
    """Honor the game's remaining salary schedule regardless of data source.

    This is a retirement commitment rule, not a legal guarantee classification.
    """
    if not contract:
        return False
    return any(
        (maybe_float(entry.get("salary")) or 0.0) > 0 and str(entry.get("season") or "") >= str(season)
        for entry in contract.get("seasons", [])
    )


def contract_last_season(contract: dict[str, Any]) -> str | None:
    seasons = [str(entry.get("season")) for entry in contract.get("seasons", []) if entry.get("salary") is not None and entry.get("season")]
    return max(seasons) if seasons else None


def strategic_free_agent_signings(canonical: dict[str, Any], save: dict[str, Any], free_agents: list[str], next_season: str, seed: int) -> set[str]:
    from .waivers import pending_ids
    from .release_planning import reacquisition_blocked
    free_agents = list(set(free_agents) - pending_ids(save))
    active = canonical_with_save(canonical, save)
    teams = sorted(canonical.get("teams", []), key=lambda item: item["abbrev"])
    roster_by_team: dict[str, list[dict[str, Any]]] = {
        team["id"]: [player for player in active.get("players", []) if player.get("team_id") == team["id"]]
        for team in teams
    }
    cap_room_by_team: dict[str, dict[str, float]] = {}
    for team in teams:
        cap = team_cap_summary(active, save, team["id"], season=next_season)
        cap_room_by_team[team["id"]] = {
            "tax": float(cap.get("tax_space_millions") or 0.0) * 1_000_000,
            "hard": float(cap.get("hard_cap_space_millions") or 0.0) * 1_000_000,
        }
    candidates = [
        player for player in active.get("players", [])
        if player["id"] in set(free_agents) and player["id"] not in set(save.get("retired_player_ids", []))
    ]
    signed: set[str] = set()
    pass_signed: dict[str, list[float]] = {}
    for team in teams:
        roster = roster_by_team.setdefault(team["id"], [])
        open_slots = max(0, 17 - len(roster))
        if open_slots <= 0:
            continue
        needs = roster_position_needs(roster)
        scored = [
            (free_agent_team_score(player, team, needs, seed, next_season), player)
            for player in candidates
            if player["id"] not in signed
            and not reacquisition_blocked(save, team['id'], player['id'], save['state']['current_date'])
        ]
        for score, player in sorted(scored, key=lambda item: (-item[0], item[1]["name"]))[: min(open_slots, 4)]:
            if score < 8.5:
                continue
            salary = strategic_signing_salary(player, score)
            cap_room = cap_room_by_team.setdefault(team["id"], {"tax": 0.0, "hard": 0.0})
            tax_space = cap_room["tax"]
            hard_space = cap_room["hard"]
            minimum_salary = 2_250_000
            if salary > hard_space:
                if len(roster) < ROSTER_MINIMUM:
                    salary = minimum_salary
                else:
                    continue
            if salary > tax_space and len(roster) >= ROSTER_MINIMUM:
                continue
            if salary > tax_space and len(roster) < ROSTER_MINIMUM:
                salary = minimum_salary
            # Payroll discipline (TRADE-VOLUME): count the minimum contracts still needed and the owner's tax plan.
            from .payroll_plan import payroll_check
            signed_here = pass_signed.setdefault(team["id"], [0.0, 0])
            if not payroll_check(active, save, team["id"], next_season, add_salary=salary,
                                 minutes=display_minutes_projection(player), kind="free_agency", age=player.get("display_age", player.get("age")),
                                 committed=signed_here[0], committed_players=signed_here[1])["ok"]:
                continue
            signed_here[0] += salary
            signed_here[1] += 1
            save.setdefault("roster_overrides", {})[player["id"]] = team["id"]
            save.setdefault("contract_overrides", {})[player["id"]] = {
                "team_id": team["id"],
                "seasons": [
                    {
                        "season": next_season,
                        "salary": salary,
                        "option_type": None,
                        "guarantee_status": "ai_offseason_signing",
                        "guaranteed_salary": salary,
                        "protection_basis": "negotiated",
                    }
                ],
                "status": "ai_offseason_signing",
                "original_contract_years": 1,
                "signed_season": next_season,
            }
            signed.add(player["id"])
            save.setdefault("transaction_logs", []).append(
                {
                    "id": stable_id("transaction_log", "ai_signing", next_season, team["id"], player["id"]),
                    "date": f"{season_start_year(next_season)}-07-03",
                    "transaction_type": "ai_free_agent_signing",
                    "proposal_id": stable_id("ai_signing", next_season, team["id"], player["id"]),
                    "status": "applied_to_save_ledger",
                    "teams": [team["id"]],
                    "assets": {"player_id": player["id"], "name": player["name"], "salary": salary},
                    "evaluations": [{"score": round(score, 2), "needs": needs}],
                    "source_ids": ["src_contract_market_config_v1"],
                    "notes": "AI offseason signing from roster need, player role, salary scale, and deterministic fit noise.",
                }
            )
            cap_room["tax"] -= salary
            cap_room["hard"] -= salary
            roster.append({**player, "team_id": team["id"], "team_abbrev": team.get("abbrev")})
            maybe_add_major_free_agent_news(save, team, player, salary, next_season)
    return signed


def maybe_add_major_free_agent_news(save: dict[str, Any], team: dict[str, Any], player: dict[str, Any], salary: int, next_season: str) -> None:
    marker = f"{next_season}:{player['id']}:{team['id']}"
    posted = set(save.setdefault("major_free_agent_news_ids", []))
    if marker in posted:
        return
    if salary < 9_000_000 and display_minutes_projection(player) < 18:
        return
    season_posted = [item for item in posted if item.startswith(f"{next_season}:")]
    if len(season_posted) >= 5:
        return
    headline = f"{player['name']} signs with {team['abbrev']} for ${salary / 1_000_000:.1f}M."
    add_news(save, "free_agent_signing", headline, date_value=f"{season_start_year(next_season)}-07-03")
    add_league_event(
        save,
        "free_agent_signing",
        headline,
        date_value=f"{season_start_year(next_season)}-07-03",
        team_ids=[team.get("id")],
        player_ids=[player.get("id")],
        importance=0.72 if salary > MAJOR_FREE_AGENT_AAV_THRESHOLD else 0.5,
        details={
            "player_id": player.get("id"),
            "team_id": team.get("id"),
            "annual_salary": salary,
            "aav_millions": round(salary / 1_000_000, 2),
        },
    )
    posted.add(marker)
    save["major_free_agent_news_ids"] = sorted(posted)


def process_inseason_released_free_agent_signings(canonical: dict[str, Any], save: dict[str, Any], seed: int, date_value: str,
                                                  active: dict[str, Any] | None = None) -> set[str]:
    phase = save.get("state", {}).get("phase") or phase_for_date(date_value)
    if phase not in {"preseason", "regular_season"}:
        return set()
    released = save.setdefault("released_free_agents", {})
    if not released:
        return set()
    pool = set(save.get("free_agent_player_ids") or [])
    retired = set(save.get("retired_player_ids") or [])
    # Most days nobody released is still available; skip the full league rebuild then (same result, cheaper).
    if not any(release.get("status") == "available" and player_id in pool and player_id not in retired
               for player_id, release in released.items()):
        return set()
    active = active if active is not None else canonical_with_save(canonical, save)
    players = {player.get("id"): player for player in active.get("players", []) if player.get("id")}
    profiles = {profile.get("player_id"): profile for profile in active.get("player_contract_market_profiles", [])}
    candidates: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for player_id, release in released.items():
        if release.get("status") != "available" or player_id not in pool or player_id in retired:
            continue
        player = players.get(player_id)
        if not player or player.get("team_id"):
            continue
        profile = profiles.get(player_id, {})
        if not released_free_agent_is_meaningful(active, player, profile) and not release.get('buyout_market_interest'):
            continue
        attrs = player_attribute_summary(active, player_id)
        desirability = display_minutes_projection(player) * 1.25 + float(attrs.get("overall") or 0.0) + released_free_agent_salary(player, profile, attrs) / 1_000_000 * 0.12
        candidates.append((desirability, player, release))
    signed: set[str] = set()
    retention_context = None

    def healthy_retention_context() -> dict[str, Any]:
        nonlocal retention_context
        if retention_context is None:
            retention_context = roster_retention_context(active, save, prepared_active=True)
        return retention_context

    for _, player, release in sorted(candidates, key=lambda item: (-item[0], item[1].get("name", "")))[:3]:
        if active is None:
            active = canonical_with_save(canonical, save)
        profile = next((item for item in active.get("player_contract_market_profiles", []) if item.get("player_id") == player["id"]), {})
        attrs = player_attribute_summary(active, player["id"])
        salary = released_free_agent_salary(player, profile, attrs)
        destination = released_free_agent_destination(active, save, player, release, salary, seed, date_value,
                                                       retention_context_factory=healthy_retention_context)
        if not destination:
            continue
        team = destination["team"]
        cut_player = destination.get("cut_player")
        if cut_player:
            waive_ai_depth_player_for_released_free_agent(save, cut_player, team, date_value, player, canonical=active)
        apply_inseason_released_free_agent_signing(save, player, team, salary, date_value, destination["score"])
        signed.add(player["id"])
        active, retention_context = None, None
    return signed


def released_free_agent_is_meaningful(canonical: dict[str, Any], player: dict[str, Any], profile: dict[str, Any]) -> bool:
    if "src_startup_free_agent_scaffold_v1" in set(player.get("source_ids") or []):
        return False
    minutes = display_minutes_projection(player)
    attrs = player_attribute_summary(canonical, player.get("id"))
    role = str(profile.get("role_tier") or "").lower()
    non_depth_role = role and role not in {"depth", "deep_depth", "minimum", "replacement", "fringe", "two_way", "camp_body"}
    return minutes >= 18.0 or float(attrs.get("overall") or 0.0) >= 58.0 or non_depth_role


def released_free_agent_salary(player: dict[str, Any], profile: dict[str, Any], attrs: dict[str, Any]) -> int:
    salary = maybe_float(profile.get("asking_aav") or profile.get("expected_aav") or profile.get("minimum_aav"))
    if salary is None or salary <= 0:
        salary = 2_250_000 + display_minutes_projection(player) * 500_000 + max(0.0, float(attrs.get("overall") or 0.0) - 55.0) * 650_000
    return int(round(clamp(float(salary), 1_900_000, 45_000_000)))


def released_free_agent_rotation_view(context: dict[str, Any], roster: list[dict[str, Any]]) -> dict[str, Any]:
    """Privately forecast healthy destination opportunity from neutral roles."""
    from .roster_forecast import ForecastSnapshot
    snapshot = context.get('_released_fa_forecast')
    if snapshot is None:
        snapshot = context['_released_fa_forecast'] = ForecastSnapshot(context)
    players = [dict(deepcopy(p), minutes_projection=24) for p in roster]
    trial = snapshot.view(context, players)
    targets, _ = ai_role_targets(trial, players, {})
    # Rebuild player indexes, retaining only audited immutable skill memos.
    return snapshot.view(trial, [dict(p, minutes_projection=targets.get(p['id'], 0)) for p in players])


def released_free_agent_destination(
    canonical: dict[str, Any],
    save: dict[str, Any],
    player: dict[str, Any],
    release: dict[str, Any],
    salary: int,
    seed: int,
    date_value: str,
    *,
    retention_context_factory: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    human_team_ids = human_controlled_team_ids(save)
    waived_by = release.get("waived_by_team_id")
    season = save_active_contract_season(save)
    candidates: list[dict[str, Any]] = []
    retention_context = None
    for team in canonical.get("teams", []):
        team_id = team.get("id")
        if team_id in human_team_ids or team_id == waived_by:
            continue
        if not ai_team_can_absorb_released_free_agent(canonical, save, team_id, salary, season):
            continue
        roster = [item for item in canonical.get("players", []) if item.get("team_id") == team_id]
        cut_player = None
        upgrade = 0.0
        if len(roster) >= ROSTER_SEASON_MAXIMUM:
            if retention_context is None:
                retention_context = (retention_context_factory() if retention_context_factory is not None
                                     else roster_retention_context(canonical, save, prepared_active=True))
            # This private owner is shared by at most this batch's candidates,
            # and discarded by the caller after each actual signing/cut.
            before_views = retention_context.setdefault('_released_fa_before_rosters', {})
            if team_id not in before_views:
                before_views[team_id] = released_free_agent_rotation_view(retention_context, roster)
            before = before_views[team_id]
            cuttable = [
                item for item in before['players'] if display_minutes_projection(item) <= 14.0
            ]
            if not cuttable:
                continue
            cut_player = min(cuttable, key=lambda item: (
                ai_roster_retention_score(before, save, item), item.get("name") or "", item["id"],
            ))
            after_roster = [p for p in before['players'] if p['id'] != cut_player['id']]
            after_roster.append(dict(player, team_id=team_id))
            after = released_free_agent_rotation_view(retention_context, after_roster)
            # Price the proposed new agreement, not any old employer's debt.
            after['contracts'] = [c for c in after.get('contracts', []) if c['player_id'] != player['id']] + [{
                'player_id': player['id'], 'team_id': team_id,
                'seasons': [{'season': season, 'salary': salary, 'guaranteed_salary': salary}],
            }]
            incoming = next(p for p in after['players'] if p['id'] == player['id'])
            upgrade = (ai_roster_retention_score(after, save, incoming)
                       - ai_roster_retention_score(before, save, cut_player))
            # Keep the existing material-upgrade and guaranteed-cut-cost gates.
            if upgrade < 8.0:
                continue
            from .contract_protection import waiver_projection
            cost = waiver_projection(canonical, save, cut_player, team_id)['remaining_cost_millions']
            if upgrade < 8.0 + cost*.22:
                continue
        # Payroll discipline (TRADE-VOLUME): minimum deals count too; after the deadline a team under the line stays.
        from .payroll_plan import payroll_check
        if not payroll_check(canonical, save, team_id, season, add_salary=float(salary),
                             roster_delta=0 if cut_player else 1, minutes=display_minutes_projection(player),
                             kind="in_season_signing")["ok"]:
            continue
        needs = roster_position_needs(roster)
        state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == team_id), {})
        record = (save.get("team_records") or {}).get(team_id, {})
        wins = maybe_float(record.get("wins")) or 0.0
        losses = maybe_float(record.get("losses")) or 0.0
        games = wins + losses
        win_pct = wins / games if games else None
        ceiling = maybe_float(state.get("contention_ceiling")) or 52.0
        age = maybe_float(player.get("display_age", player.get("age"))) or 27.0
        timeline = released_free_agent_timeline_fit(age, str(state.get("phase") or "balanced"), ceiling)
        quality = (win_pct * 100.0 if win_pct is not None else ceiling) * 0.16
        cap = team_cap_summary(canonical, save, team_id, season=season)
        cap_room = min(12.0, max(0.0, float(cap.get("tax_space_millions") or 0.0))) * 0.12
        noise = deterministic_small(seed, date_value, team_id, player["id"], "released_fa") * 2.5
        score = free_agent_team_score(player, team, needs, seed, season) + timeline + quality + cap_room + noise
        if cut_player:
            score += min(9.0, upgrade * 0.18)
        candidates.append({"team": team, "score": round(score, 3), "cut_player": cut_player})
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (-float(item["score"]), item["team"].get("abbrev", "")))[0]


def released_free_agent_timeline_fit(age: float, phase: str, ceiling: float) -> float:
    if age <= 24:
        return 6.0 if phase in {"rebuilding", "developing"} else 2.0 if ceiling >= 60 else 4.0
    if age <= 31:
        return 5.0 if ceiling >= 58 else 2.5
    return 5.5 if ceiling >= 62 else -3.0


def ai_team_can_absorb_released_free_agent(canonical: dict[str, Any], save: dict[str, Any], team_id: str | None, salary: int, season: str) -> bool:
    if not team_id:
        return False
    cap = team_cap_summary(canonical, save, team_id, season=season)
    salary_m = salary / 1_000_000
    hard_space = float(cap.get("hard_cap_space_millions") or 0.0)
    tax_space = float(cap.get("tax_space_millions") or 0.0)
    if salary_m <= 1.95:
        return hard_space >= -0.05
    return salary_m <= hard_space + 0.05 and salary_m <= tax_space + 0.05


def waive_ai_depth_player_for_released_free_agent(save: dict[str, Any], cut_player: dict[str, Any], team: dict[str, Any], date_value: str, incoming_player: dict[str, Any], canonical: dict[str, Any] | None = None) -> None:
    player_id = cut_player["id"]
    if canonical is not None:
        from .waivers import request_waiver
        request_waiver(canonical, save, cut_player, team['id'], date_value)
    save.setdefault("roster_overrides", {})[player_id] = None
    save.setdefault("free_agent_player_ids", [])
    if canonical is None and player_id not in save["free_agent_player_ids"]:
        save["free_agent_player_ids"].append(player_id)
        save["free_agent_player_ids"] = sorted(save["free_agent_player_ids"])
    save.setdefault("released_free_agents", {})[player_id] = {
        "player_id": player_id,
        "player_name": cut_player.get("name"),
        "waived_by_team_id": team["id"],
        "waived_by_team_abbrev": team.get("abbrev"),
        "release_date": date_value,
        "status": "on_waivers" if canonical is not None else "available",
        "reason": f"created_roster_spot_for_{incoming_player.get('id')}",
    }
    save.setdefault("rotation_recommendations", {}).pop(player_id, None)
    save.setdefault("rotation_snapshots", {}).pop(team["id"], None)
    save.setdefault("transaction_logs", []).append(
        {
            "id": stable_id("transaction_log", "ai_roster_cut", date_value, team["id"], player_id, incoming_player.get("id")),
            "date": date_value,
            "transaction_type": "roster_cut",
            "proposal_id": stable_id("ai_roster_cut", date_value, team["id"], player_id),
            "status": "applied_to_save_ledger",
            "teams": [team["id"]],
            "assets": {"player_id": player_id, "name": cut_player.get("name"), "waived_by_team_id": team["id"]},
            "evaluations": [],
            "source_ids": ["src_contract_market_config_v1"],
            "notes": f"AI waived a depth player to create a roster spot for {incoming_player.get('name')}.",
        }
    )


def apply_inseason_released_free_agent_signing(save: dict[str, Any], player: dict[str, Any], team: dict[str, Any], salary: int, date_value: str, score: float) -> None:
    season = save_active_contract_season(save)
    player_id = player["id"]
    save.setdefault("roster_overrides", {})[player_id] = team["id"]
    save.setdefault("contract_overrides", {})[player_id] = {
        "team_id": team["id"],
        "seasons": [
            {
                "season": season,
                "salary": salary,
                "option_type": None,
                "guarantee_status": "ai_inseason_released_free_agent_signing",
                "guaranteed_salary": salary,
                "protection_basis": "negotiated",
            }
        ],
        "status": "ai_inseason_released_free_agent_signing",
        "original_contract_years": 1,
        "signed_season": season,
    }
    save["free_agent_player_ids"] = sorted(pid for pid in set(save.get("free_agent_player_ids", [])) if pid != player_id)
    save.setdefault("released_free_agents", {}).setdefault(player_id, {})["status"] = "signed"
    save["released_free_agents"][player_id]["signed_team_id"] = team["id"]
    save["released_free_agents"][player_id]["signed_date"] = date_value
    save.setdefault("rotation_snapshots", {}).pop(team["id"], None)
    save.setdefault("transaction_logs", []).append(
        {
            "id": stable_id("transaction_log", "ai_inseason_released_fa", date_value, team["id"], player_id),
            "date": date_value,
            "transaction_type": "ai_free_agent_signing",
            "proposal_id": stable_id("ai_inseason_released_fa", date_value, team["id"], player_id),
            "status": "applied_to_save_ledger",
            "teams": [team["id"]],
            "assets": {"player_id": player_id, "name": player.get("name"), "salary": salary},
            "evaluations": [{"score": round(float(score), 2), "context": "inseason_released_free_agent"}],
            "source_ids": ["src_contract_market_config_v1"],
            "notes": "AI signed a meaningful player from the in-season released-player pool.",
        }
    )
    if salary >= 9_000_000 or display_minutes_projection(player) >= 18:
        headline = f"{player.get('name')} signs with {team.get('abbrev')} after being released."
        add_news(save, "free_agent_signing", headline, date_value=date_value)
        add_league_event(
            save,
            "free_agent_signing",
            headline,
            date_value=date_value,
            team_ids=[team.get("id")],
            player_ids=[player_id],
            importance=0.58,
            details={
                "player_id": player_id,
                "team_id": team.get("id"),
                "annual_salary": salary,
                "aav_millions": round(salary / 1_000_000, 2),
                "source": "inseason_released_free_agent",
            },
        )


def roster_position_needs(roster: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"guard": 0, "wing": 0, "big": 0}
    for player in roster:
        pos = str(player.get("position") or "").upper()
        if "PG" in pos or "SG" in pos:
            counts["guard"] += 1
        elif "C" in pos or "PF" in pos:
            counts["big"] += 1
        else:
            counts["wing"] += 1
    return {"guard": max(0, 5 - counts["guard"]), "wing": max(0, 5 - counts["wing"]), "big": max(0, 4 - counts["big"])}


def free_agent_team_score(player: dict[str, Any], team: dict[str, Any], needs: dict[str, int], seed: int, season: str) -> float:
    minutes = display_minutes_projection(player)
    age = float(player.get("age") or 27.0)
    pos = str(player.get("position") or "").upper()
    bucket = "guard" if ("PG" in pos or "SG" in pos) else "big" if ("PF" in pos or "C" in pos) else "wing"
    need_bonus = needs.get(bucket, 0) * 3.5
    age_fit = 3.0 if 24 <= age <= 31 else 1.0 if age < 34 else -1.5
    noise = deterministic_small(seed, season, team["id"], player["id"], "fa_fit") * 4.0
    return minutes * 0.62 + need_bonus + age_fit + noise


def strategic_signing_salary(player: dict[str, Any], score: float) -> int:
    minutes = display_minutes_projection(player)
    salary = 2_100_000 + minutes * 420_000 + max(0.0, score - 18.0) * 180_000
    return int(round(clamp(salary, 1_900_000, 18_000_000)))


def auto_fill_rosters(canonical: dict[str, Any], save: dict[str, Any], free_agents: list[str], next_season: str, seed: int) -> set[str]:
    from .waivers import pending_ids
    from .release_planning import reacquisition_blocked
    free_agents = list(set(free_agents) - pending_ids(save))
    active = canonical_with_save(canonical, save)
    teams = sorted(canonical.get("teams", []), key=lambda item: item["abbrev"])
    roster_by_team: dict[str, list[dict[str, Any]]] = {
        team["id"]: [player for player in active.get("players", []) if player.get("team_id") == team["id"]]
        for team in teams
    }
    available = [
        player for player in active.get("players", [])
        if player["id"] in set(free_agents) and player["id"] not in set(save.get("retired_player_ids", []))
    ]
    available.sort(key=lambda player: (-display_minutes_projection(player), player["name"]))
    signed: set[str] = set()
    for team in teams:
        roster = roster_by_team.setdefault(team["id"], [])
        while len(roster) < ROSTER_MINIMUM:
            candidate = next((player for player in available if player["id"] not in signed
                              and not reacquisition_blocked(save, team['id'], player['id'], save['state']['current_date'])), None)
            if candidate is None:
                candidate = create_replacement_player(team, next_season, seed, len(save.get("generated_players", [])))
                save.setdefault("generated_players", []).append(candidate)
                for trait in generated_replacement_traits(candidate, seed):
                    upsert_by_id(save, "generated_traits", trait)
            save.setdefault("roster_overrides", {})[candidate["id"]] = team["id"]
            save.setdefault("contract_overrides", {})[candidate["id"]] = {
                "team_id": team["id"],
                "seasons": [
                    {
                        "season": next_season,
                        "salary": 2_250_000,
                        "option_type": None,
                        "guarantee_status": "minimum_depth_signing",
                        "guaranteed_salary": 2_250_000,
                        "protection_basis": "negotiated",
                    }
                ],
                "status": "auto_depth_signing",
                "original_contract_years": 1,
                "signed_season": next_season,
            }
            signed.add(candidate["id"])
            roster.append(candidate)
            save.setdefault("transaction_logs", []).append(
                {
                    "id": stable_id("transaction_log", "auto_depth", next_season, team["id"], candidate["id"]),
                    "date": f"{season_start_year(next_season)}-09-01",
                    "transaction_type": "auto_depth_signing",
                    "proposal_id": stable_id("auto_depth", next_season, team["id"], candidate["id"]),
                    "status": "applied_to_save_ledger",
                    "teams": [team["id"]],
                    "assets": {"player_id": candidate["id"], "name": candidate["name"]},
                    "evaluations": [],
                    "source_ids": ["src_contract_market_config_v1"],
                    "notes": "Automatic minimum roster repair so a season cannot start with fewer than 14 players.",
                }
            )
    return signed


def ensure_roster_minimums(canonical: dict[str, Any], save: dict[str, Any], seed: int,
                           active: dict[str, Any] | None = None) -> set[str]:
    """Repair rosters below the minimum. `active` may be a current active state for the same save (read only)."""
    season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    active = active if active is not None else canonical_with_save(canonical, save)
    needs_repair = False
    for team in active.get("teams", []):
        count = sum(1 for player in active.get("players", []) if player.get("team_id") == team.get("id"))
        if count < ROSTER_MINIMUM:
            needs_repair = True
            break
    if not needs_repair:
        return set()
    signed = auto_fill_rosters(canonical, save, list(save.get("free_agent_player_ids", [])), season, seed + 2219)
    if signed:
        save["free_agent_player_ids"] = sorted(
            player_id
            for player_id in set(save.get("free_agent_player_ids", []))
            if player_id not in signed
        )
        for player_id in signed:
            released = (save.get("released_free_agents") or {}).get(player_id)
            if released:
                released["status"] = "signed"
                released["signed_team_id"] = (save.get("roster_overrides") or {}).get(player_id)
                released["signed_date"] = save.get("state", {}).get("current_date")
        add_news(
            save,
            "roster_repair",
            f"League roster repair added {len(signed)} minimum-depth signing(s) before games resumed.",
            date_value=save.get("state", {}).get("current_date"),
        )
    return signed


def create_replacement_player(team: dict[str, Any], season: str, seed: int, index: int) -> dict[str, Any]:
    rng = random.Random(f"{seed}:{season}:{team['id']}:{index}:replacement_player")
    first_pool = ["Jalen", "Marcus", "Dorian", "Eli", "Noah", "Cam", "Miles", "Tre", "Isaiah", "Malik", "Amari", "Nolan", "Dante", "Kellan", "Makai", "Julian", "Tariq", "Andre", "Mateo", "Omar"]
    last_pool = [
        "Reed", "Hayes", "Porter", "Ellis", "Cole", "Bennett", "Wallace", "Foster", "Lang", "Sullivan",
        "Vargas", "Bishop", "Mathis", "Gaines", "Lawson", "Cross", "Santos", "Balde", "Moreau", "Hawkins",
        "Whitaker", "Morrison", "Diallo", "Petrovic", "Sato", "Kowalski", "Mensah", "Harrison", "Navarro", "Griffin",
        "Stone", "Camara", "Blackwell", "Rhodes", "Mendez", "Laurent", "Robinson", "Klein", "Turner", "Boateng",
        "Hart", "Walters", "Kimani", "Montgomery", "Hughes", "Bamba", "Carlson", "Rojas", "Ibrahim", "Vaughn",
        "Parker", "Bates", "Grant", "Okoro", "Hendrix", "Adebayo", "Baker", "Shepard", "Morales", "Keita",
    ]
    first = rng.choice(first_pool)
    last = rng.choice(last_pool)
    position = ["PG", "SG", "SF", "PF", "C"][int(rng.random() * 5) % 5]
    name = f"{first} {last}"
    player_id = stable_id("generated_player", season, team["abbrev"], index, name)
    return {
        "id": player_id,
        "name": name,
        "normalized_name": name.lower(),
        "slug": player_id.replace("generated_player_", ""),
        "team_id": team["id"],
        "team_abbrev": team["abbrev"],
        "position": position,
        "age": round(23 + rng.random() * 8, 1),
        "age_base_season": season,
        "age_base_start_year": season_start_year(season),
        "height_inches": {"PG": 75, "SG": 77, "SF": 80, "PF": 82, "C": 83}[position] + rng.uniform(-1.5, 1.5),
        "weight_lbs": 190 + rng.random() * 45,
        "minutes_projection": round(5 + rng.random() * 8, 1),
        "rotation_priority": "replacement_depth",
        "source_ids": ["src_contract_market_config_v1"],
        "missing_critical_fields": [],
        "critical_field_fallbacks": {},
    }


def generated_replacement_traits(player: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    from .draft import NBA_TRAIT_LABELS

    rng = random.Random(f"{seed}:{player['id']}:replacement_traits")
    pos = str(player.get("position") or "").upper()
    base = 43 + display_minutes_projection(player) * 0.35
    values = {key: clamp(base + rng.gauss(0, 4.0), 28, 60) for key in NBA_TRAIT_LABELS}
    if "PG" in pos or "SG" in pos:
        values["handle_pressure"] += 4
        values["passing_reads"] += 3
        values["release_speed"] += 2
    if "SF" in pos:
        values["foot_speed_lateral_agility"] += 3
        values["defensive_effort"] += 2
    if "PF" in pos or "C" in pos:
        values["offensive_rebounding"] += 5
        values["rim_deterrence"] += 4
        values["screen_navigation"] -= 3
    return [
        {
            "id": stable_id("generated_trait", player["id"], trait_key),
            "player_id": player["id"],
            "trait_key": trait_key,
            "label": NBA_TRAIT_LABELS[trait_key],
            "value": round(clamp(value, 25, 62), 2),
            "confidence": 0.34,
            "source_kind": "generated_replacement_depth",
            "source_ids": ["src_contract_market_config_v1"],
            "last_verified": player.get("signed_season") or CANONICAL_START_DATE,
            "notes": "Replacement-level generated depth trait for save-state roster repair.",
            "components": {"position": pos, "minutes_projection": display_minutes_projection(player)},
        }
        for trait_key, value in sorted(values.items())
    ]


def season_start_year(season: str) -> int:
    try:
        return int(str(season).split("-")[0])
    except (TypeError, ValueError):
        return 2025


def season_end_year(season: str) -> int:
    return season_start_year(season) + 1


def season_label_from_start(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def regular_schedule_template(root: str | Path) -> list[dict[str, Any]]:
    games = load_schedule(root)
    with (Path(root) / SCHEDULE_CORRECTIONS_FILE).open("r", encoding="utf-8") as handle:
        corrections = json.load(handle)
    if corrections.get("version") != 1 or corrections.get("template") != str(SCHEDULE_FILE):
        raise ValueError("Unsupported regular-season schedule corrections")
    by_id = {str(game.get("externalGameId")): game for game in games}
    if len(by_id) != len(games):
        raise ValueError("Schedule template has duplicate game IDs")
    excluded = set()
    for correction in corrections["excluded_games"]:
        game_id = str(correction["externalGameId"])
        original = by_id.get(game_id)
        expected = correction["expected"]
        if original is None or any(original.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Schedule correction no longer matches template game {game_id}")
        if correction.get("replacement"):
            replacement = correction["replacement"]
            makeup = by_id.get(str(replacement["externalGameId"]))
            if (makeup is None or makeup.get("gameDate") != replacement["gameDate"]
                    or makeup.get("phase") != "regular"
                    or makeup.get("status") in {"postponed", "cancelled", "canceled"}
                    or any(makeup.get(key) != expected[key] for key in ["homeTeamId", "awayTeamId"])):
                raise ValueError(f"Schedule correction missing valid makeup for game {game_id}")
        excluded.add(game_id)
    regular = [game for game in games if game.get("phase") == "regular"
               and str(game.get("externalGameId")) not in excluded
               and game.get("status") not in {"postponed", "cancelled", "canceled"}]
    validate_regular_season_schedule(regular)
    return regular


def validate_regular_season_schedule(games: list[dict[str, Any]]) -> None:
    counts: Counter[str] = Counter()
    appearances = set()
    game_ids = set()
    # This generator uses the fixed 30-team ESPN template, not expansion leagues.
    team_ids = {str(value) for value in range(1, 31)}
    for game in games:
        game_id = str(game.get("externalGameId") or "")
        if not game_id or game_id in game_ids:
            raise ValueError(f"Regular-season schedule has missing or duplicate game ID: {game_id}")
        game_ids.add(game_id)
        home, away = str(game.get("homeTeamId")), str(game.get("awayTeamId"))
        if home not in team_ids or away not in team_ids or home == away:
            raise ValueError(f"Regular-season schedule has invalid opponents in game {game_id}")
        if game.get("phase") != "regular":
            raise ValueError(f"Non-regular game in regular-season schedule: {game_id}")
        day = parse_date(game["gameDate"]).isoformat()
        for team in [home, away]:
            if (day, team) in appearances:
                raise ValueError(f"Regular-season schedule double-books team {team} on {day}")
            appearances.add((day, team))
            counts[team] += 1
    if len(games) != 1230 or set(counts) != team_ids or any(count != 82 for count in counts.values()):
        raise ValueError(f"Regular-season schedule must have 1230 games and 82 per team: {dict(counts)}")


def generate_future_schedule(root: str | Path, season: str, start_year: int) -> dict[str, Any]:
    schedule_root = Path(root)
    if not (schedule_root / SCHEDULE_FILE).exists():
        schedule_root = Path(__file__).resolve().parents[2]
    template_games = regular_schedule_template(schedule_root)
    randomized = randomize_future_matchups(template_games, season)
    games = []
    for game in randomized:
        if game.get("phase") != "regular":
            continue
        original = parse_date(game["gameDate"])
        year = start_year if original.month >= 10 else start_year + 1
        new_date = date(year, original.month, original.day).isoformat()
        games.append(
            {
                **game,
                "gameDate": new_date,
                "externalGameId": stable_id("sim_game", season, game.get("externalGameId")),
                "status": "scheduled_generated",
                "season": season,
            }
        )
    validate_regular_season_schedule(games)
    return {
        "season": season,
        "template": "NBA Schedule/schedule_v2025_2026.json",
        "template_corrections": str(SCHEDULE_CORRECTIONS_FILE),
        "generation_version": 2,
        "game_count": len(games),
        "games": sorted(games, key=lambda item: (item["gameDate"], str(item["externalGameId"]))),
        "notes": "Generated 82-game regular season from the corrected 2025-26 template with deterministic randomized opponents; excludes Cup final and superseded postponements.",
    }


def randomize_future_matchups(template_games: list[dict[str, Any]], season: str) -> list[dict[str, Any]]:
    rng = random.Random(f"{season}:future_schedule")
    output: list[dict[str, Any]] = []
    games_by_date: dict[str, list[dict[str, Any]]] = {}
    for game in template_games:
        games_by_date.setdefault(str(game.get("gameDate")), []).append(game)
    for date_key in sorted(games_by_date):
        games = sorted(games_by_date[date_key], key=lambda item: str(item.get("externalGameId")))
        away_ids = [game.get("awayTeamId") for game in games]
        rng.shuffle(away_ids)
        # Shuffling only within a valid template date preserves one appearance per
        # team that day while still producing deterministic future opponents.
        output.extend({**game, "awayTeamId": away_id} for game, away_id in zip(games, away_ids))
    return output


def refresh_health_for_new_season(save: dict[str, Any], start_date: str) -> None:
    refreshed = []
    for state in save.get("health_states", []):
        # Rest nights, shutdowns and the counts behind them belong to the season that ended.
        state = {key: value for key, value in state.items()
                 if key not in ("rest_game_id", "rest_date", "rest_reason", "rest_shutdown", "games_rested", "rest_suggestion",
                                "user_rest", "fatigue_game", "fatigue_next")}
        refreshed.append(
            {
                **state,
                "id": stable_id("health_state", state.get("player_id"), start_date),
                "as_of_date": start_date,
                "fatigue": 0.0,
                "fatigue_date": start_date,
                "rust": max(0.0, round(float(state.get("rust") or 0.0) * 0.25, 2)),
                "availability_status": "active" if not state.get("current_injury_id") else state.get("availability_status", "active"),
                "games_missed": 0,
                "notes": "Refreshed for new sandbox season rollover.",
            }
        )
    save["health_states"] = sorted(refreshed, key=lambda item: item.get("player_id", ""))


def age_staff_contracts(save: dict[str, Any], canonical: dict[str, Any] | None = None, seed: int = 1) -> None:
    updated: list[dict[str, Any]] = []
    expired_count = 0
    date_value = save.get("state", {}).get("current_date") or "season_rollover"
    original_slots = list(save.get("staff_slots", []))
    roster_ids_by_team: dict[str, set[str]] = {}
    if canonical is not None:
        staff_active = canonical_with_save(canonical, save)
        for player in staff_active.get("players", []):
            if player.get("team_id") and player.get("id"):
                roster_ids_by_team.setdefault(str(player["team_id"]), set()).add(str(player["id"]))
    for index, staff in enumerate(original_slots):
        staff = deepcopy(staff)
        contract = staff.setdefault("contract", {})
        years = int(contract.get("years_remaining") or 1)
        contract["years_remaining"] = max(0, years - 1)
        # Retentions are resolved as one offseason batch. Expose prior accepted
        # renewals to the next negotiation so simultaneous raises reserve real
        # budget room instead of all pricing against the pre-renewal payroll.
        save["staff_slots"] = [*updated, staff, *original_slots[index + 1 :]]
        if contract["years_remaining"] == 0:
            team_id = staff.get("team_id")
            slot = staff.get("slot")
            if team_id and slot:
                if team_id in human_controlled_team_ids(save) and not is_interim_staff(staff):
                    add_staff_retention_window(save, staff, date_value)
                    staff["market_status"] = "contract_expired_pending_user_decision"
                    staff["job_security"] = min(float(staff.get("job_security") or 50.0), 45.0)
                    updated.append(staff)
                    continue
                retained = ai_staff_retention_contract(
                    canonical,
                    save,
                    staff,
                    seed,
                    date_value,
                    roster_ids_by_team=roster_ids_by_team,
                ) if not is_interim_staff(staff) else None
                if retained:
                    updated.append(retained)
                    continue
                if not is_interim_staff(staff):
                    former = deepcopy(staff)
                    former["market_status"] = "expired_contract"
                    former["team_id"] = None
                    save.setdefault("former_staff", []).append(former)
                    team_abbrev = str(team_id).replace("team_", "").upper()
                    add_news(
                        save,
                        "staff_contract",
                        f"{team_abbrev} {ROLE_LABELS.get(slot, slot)} {staff.get('name')} reached contract expiration; an interim has been appointed.",
                        date_value=date_value,
                    )
                replacement = interim_staff(team_id, slot, date_value, expired_count, staff.get("id"), staff.get("name"))
                updated.append(replacement)
                expired_count += 1
                continue
            staff["job_security"] = min(float(staff.get("job_security") or 50.0), 42.0)
            staff["notes"] = f"{staff.get('notes', '')} Contract expired entering new season.".strip()
        updated.append(staff)
    if updated:
        save["staff_slots"] = sorted(updated, key=lambda item: (item.get("team_id") or "", item.get("slot") or "", item.get("id") or ""))
    roll_staff_lifecycle(save, canonical, staff_active if canonical is not None else None, original_slots, seed)


def ai_staff_retention_contract(
    canonical: dict[str, Any] | None,
    save: dict[str, Any],
    staff: dict[str, Any],
    seed: int,
    date_value: str,
    *,
    roster_ids_by_team: dict[str, set[str]] | None = None,
) -> dict[str, Any] | None:
    if canonical is None:
        return None
    team_id = staff.get("team_id")
    slot = staff.get("slot")
    if not team_id or not slot:
        return None
    grade = staff_grade(staff)
    context = ai_staff_retention_context(canonical, save, staff, roster_ids_by_team=roster_ids_by_team)
    if not context["retain"]:
        return None
    market_contract = staff_contract(slot, grade, seed, f"{staff.get('id')}:retention")
    current_salary = staff_budget_salary(staff)
    ask = max(current_salary * 1.035, float(market_contract.get("annual_salary_millions") or current_salary) * 0.97)
    budget = staff_budget_for_team(canonical, team_id)
    other_spend = sum(
        staff_budget_salary(other)
        for other in save.get("staff_slots", [])
        if other.get("team_id") == team_id and other.get("slot") != slot and other.get("market_status") == "employed"
    )
    available = budget - other_spend
    if ask > available:
        if grade < 88.0 or available < current_salary * 0.96:
            return None
        ask = max(0.8, available)
    retained = deepcopy(staff)
    retained["market_status"] = "employed"
    retained["status"] = retained.get("status") or "fictional_gameplay_staff_retained"
    retained["contract"] = {
        "annual_salary_millions": round(ask, 2),
        "years_remaining": 3 if grade >= 78.0 else 2,
        "guarantee_level": "standard",
    }
    retained["job_security"] = round(clamp(max(float(retained.get("job_security") or 55.0), 58.0 + (grade - 70.0) * 0.35), 35.0, 90.0), 2)
    retained["morale"] = round(clamp(float(retained.get("morale") or 64.0) + 2.0, 0.0, 100.0), 2)
    retained["notes"] = f"{retained.get('notes', '')} AI retained staff at contract expiration: {context['reason']}.".strip()
    if grade >= 89.0:
        team_abbrev = team_id_to_abbrev(team_id)
        add_news(
            save,
            "staff_hire",
            f"{team_abbrev} retains {retained.get('name')} as {ROLE_LABELS.get(slot, slot)}.",
            date_value=date_value,
        )
    return retained


def ai_staff_retention_context(
    canonical: dict[str, Any],
    save: dict[str, Any],
    staff: dict[str, Any],
    *,
    roster_ids_by_team: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    team_id = staff.get("team_id")
    slot = staff.get("slot")
    grade = staff_grade(staff)
    underperforming = team_underperformed_staff_expectation(canonical, save, team_id)
    triggered_failure = staff_slot_failure_signal(
        canonical,
        save,
        team_id,
        slot,
        roster_ids_by_team=roster_ids_by_team,
    )
    threshold = 76.0 if slot in {"head_coach", "offensive_coordinator", "defensive_coordinator"} else 72.0
    if triggered_failure and grade < 82.0:
        return {"retain": False, "reason": triggered_failure}
    if underperforming and slot in {"head_coach", "offensive_coordinator", "defensive_coordinator"} and grade < 88.0:
        return {"retain": False, "reason": "team underperformed expectations"}
    if grade >= threshold:
        return {"retain": True, "reason": "strong staff grade and no unresolved performance trigger"}
    if grade >= 68.0 and not underperforming and not triggered_failure:
        return {"retain": True, "reason": "stable staff fit"}
    return {"retain": False, "reason": "staff contract allowed to expire"}


def team_underperformed_staff_expectation(canonical: dict[str, Any], save: dict[str, Any], team_id: str | None) -> bool:
    if not team_id:
        return False
    record = save.get("team_records", {}).get(team_id, {})
    games = int(record.get("wins") or 0) + int(record.get("losses") or 0)
    if games < 30:
        return False
    win_pct = float(record.get("wins") or 0) / max(1, games)
    state = next((item for item in canonical.get("team_strategic_states", []) if item.get("team_id") == team_id), {})
    expected_pct = clamp(0.25 + float(state.get("contention_ceiling") or 55.0) / 170.0, 0.25, 0.72)
    return win_pct + 0.10 < expected_pct


def staff_slot_failure_signal(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str | None,
    slot: str | None,
    *,
    roster_ids_by_team: dict[str, set[str]] | None = None,
) -> str | None:
    if not team_id or not slot:
        return None
    if slot == "development_lead" and team_development_gain(save, team_id)["failed"]:
        return "team development lagged expectations"
    if slot == "scouting_lead" and team_recent_draft_return(save, team_id)["failed"]:
        return "recent draft return disappointed"
    if slot == "performance_lead" and team_injury_games_missed(
        canonical,
        save,
        team_id,
        roster_ids_by_team=roster_ids_by_team,
    ) >= 170:
        return "team injury burden was too high"
    return None


def team_development_gain(save: dict[str, Any], team_id: str) -> dict[str, Any]:
    # Coverage-only records must not change the existing staff grading sample.
    events = [event for event in save.get("development_events", []) if event.get("team_id") == team_id and event.get("trait_deltas")]
    if len(events) < 12:
        return {"failed": False, "event_count": len(events), "positive_gain": 0.0}
    positive = sum(
        max(0.0, float(delta))
        for event in events
        for delta in (event.get("trait_deltas") or {}).values()
    )
    expected = max(1.2, len(events) * 0.075)
    return {"failed": positive < expected, "event_count": len(events), "positive_gain": round(positive, 3), "expected": round(expected, 3)}


def team_recent_draft_return(save: dict[str, Any], team_id: str) -> dict[str, Any]:
    rookies = [
        rookie for rookie in save.get("incoming_rookies", [])
        if rookie.get("team_id") == team_id and int(rookie.get("overall_pick") or 999) <= 20
    ]
    if not rookies:
        return {"failed": False, "rookie_count": 0}
    poor = [
        rookie for rookie in rookies
        if float(rookie.get("current_ability") or 50.0) < 45.0 and float(rookie.get("potential") or 60.0) < 66.0
    ]
    return {"failed": len(poor) >= max(1, len(rookies)), "rookie_count": len(rookies), "poor_return_count": len(poor)}


def team_injury_games_missed(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    *,
    roster_ids_by_team: dict[str, set[str]] | None = None,
) -> int:
    if roster_ids_by_team is not None:
        team_player_ids = roster_ids_by_team.get(str(team_id), set())
    else:
        active = canonical_with_save(canonical, save)
        team_player_ids = {player.get("id") for player in active.get("players", []) if player.get("team_id") == team_id}
    return sum(
        int(state.get("games_missed") or 0)
        for state in save.get("health_states", [])
        if state.get("player_id") in team_player_ids
    )


def add_staff_retention_window(save: dict[str, Any], staff: dict[str, Any], date_value: str) -> dict[str, Any]:
    slot = staff.get("slot")
    team_id = staff.get("team_id")
    window_id = stable_id("staff_retention", team_id, slot, staff.get("id"), date_value)
    windows = save.setdefault("staff_retention_windows", [])
    existing = next((item for item in windows if item.get("id") == window_id), None)
    if existing:
        return existing
    window = {
        "id": window_id,
        "date": date_value,
        "team_id": team_id,
        "team_abbrev": str(team_id).replace("team_", "").upper() if team_id else None,
        "slot": slot,
        "staff_id": staff.get("id"),
        "staff_name": staff.get("name"),
        "status": "pending_user_decision",
        "choices": ["re_sign", "replace_from_market", "accept_interim"],
        "notes": "Forced user staff-retention checkpoint before this expired contract can be rolled into a new season.",
    }
    windows.append(window)
    add_news(
        save,
        "staff_contract",
        f"{window['team_abbrev']} must resolve {ROLE_LABELS.get(slot, slot)} {staff.get('name')} before advancing.",
        date_value=date_value,
    )
    return window


def canonical_hash(canonical: dict[str, Any]) -> str:
    fingerprintable = {key: value for key, value in canonical.items()
                       if key not in {"_sim_feature_cache", "_spatial_trait_index"}}
    payload = json.dumps(fingerprintable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def resolve_team(canonical: dict[str, Any], query: str) -> dict[str, Any]:
    low = query.strip().lower()
    matches = [team for team in canonical.get("teams", []) if team["abbrev"].lower() == low or team["id"].lower() == low]
    matches = matches or [team for team in canonical.get("teams", []) if low in team["name"].lower()]
    if not matches:
        raise ValueError(f"No team found matching {query!r}")
    return matches[0]


def team_by_id(canonical: dict[str, Any], team_id: str | None) -> dict[str, Any]:
    team = next((team for team in canonical.get("teams", []) if team["id"] == team_id), None)
    if not team:
        raise ValueError(f"No team found with id {team_id!r}")
    return team


def parse_date(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def next_date_str(value: str, days: int) -> str:
    return (parse_date(value) + timedelta(days=days)).isoformat()
