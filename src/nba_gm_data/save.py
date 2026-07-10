"""Own mutable league saves, chronological advancement, and season lifecycle.

Canonical data is the reproducible baseline; a save is the evolving overlay.
Functions in this module coordinate domain services in causal order, so their
sequence is gameplay behavior rather than incidental implementation detail.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from copy import deepcopy
from datetime import date, timedelta
from itertools import permutations
from pathlib import Path
from typing import Any

from .health import advance_development, simulate_health
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
from .schema import CANONICAL_SEASON, CANONICAL_START_DATE, CoachRating, to_plain
from .sim import build_sim_indices, espn_team_id_map, load_sim_context, sim_game_with_context
from .staff import ROLE_LABELS, STAFF_SLOTS, apply_head_coach_reputation, fire_staff_from_save, hire_staff_from_save, initialize_save_staff_slots, interim_staff, is_interim_staff, negotiate_staff_hire, simulate_ai_staff_changes, staff_budget_for_team, staff_budget_salary, staff_contract, staff_grade
from .utils import clamp, maybe_float, normalize_name, stable_id


SAVE_VERSION = "league_save_v1"
SCHEDULE_FILE = Path("NBA Schedule/schedule_v2025_2026.json")
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
]
TAX_LINE = 187_895_000
SECOND_APRON = 207_824_000
ANNUAL_CAP_GROWTH_RATE = 0.035
ROSTER_MINIMUM = 14
ROSTER_SEASON_MAXIMUM = 15
ROSTER_TEMPORARY_HARD_MAXIMUM = 21
AI_DIFFICULTIES = {"easy", "normal", "hard"}
SOCIAL_INJURY_GAMES_THRESHOLD = 10
MAJOR_FREE_AGENT_AAV_THRESHOLD = 25_000_000
MAJOR_PLAYER_MPG_THRESHOLD = 29.0
MAJOR_INJURY_GAMES_THRESHOLD = 41
MAJOR_STAFF_GRADE_THRESHOLD = 82.0
MAJOR_STAT_LINE_THRESHOLDS = {
    "points": 49,
    "rebounds": 20,
    "assists": 20,
    "steals": 6,
    "blocks": 6,
}


def create_league_save(
    root: str | Path,
    canonical: dict[str, Any] | Any,
    team_query: str,
    save_path: str | Path,
    seed: int = 1,
    ai_difficulty: str = "normal",
) -> dict[str, Any]:
    canonical = to_plain(canonical)
    team = resolve_team(canonical, team_query)
    save = {
        "version": SAVE_VERSION,
        "meta": {
            "id": stable_id("save", CANONICAL_SEASON, team["abbrev"], seed),
            "season": CANONICAL_SEASON,
            "canonical_universe_id": canonical.get("meta", {}).get("id"),
            "canonical_hash": canonical_hash(canonical),
            "user_team_id": team["id"],
            "user_team_abbrev": team["abbrev"],
            "seed": seed,
            "ai_difficulty": normalize_ai_difficulty(ai_difficulty),
            "created_at": CANONICAL_START_DATE,
        },
        "state": {
            "current_date": CANONICAL_START_DATE,
            "phase": phase_for_date(CANONICAL_START_DATE),
            "legal_actions": [action for action in legal_actions_for_date(CANONICAL_START_DATE) if action != "press_conferences"],
        },
        "schedule_state": {"simulated_game_ids": []},
        "season_schedules": {},
        "season_history": [],
        "year_reviews": [],
        "retirement_reports": [],
        "league_awards": [],
        "roster_overrides": {},
        "contract_overrides": {},
        "draft_pick_overrides": {},
        "generated_draft_picks": [],
        "pick_obligations": load_pick_obligation_overrides(root),
        "locked_pick_assets": [],
        "draft_rights": [],
        "rookie_contracts": [],
        "incoming_rookies": [],
        "generated_players": [],
        "generated_traits": [],
        "free_agent_player_ids": [],
        "startup_free_agents": [],
        "released_free_agents": {},
        "retired_player_ids": [],
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
        },
        "narrative_settings": default_narrative_settings(),
        "narrative_cache": {"version": NARRATIVE_PROMPT_VERSION, "social": {}, "press": {}},
        "inbox_items": [
            {
                "id": stable_id("inbox", "welcome", team["id"]),
                "date": CANONICAL_START_DATE,
                "kind": "save_created",
                "headline": f"{team['abbrev']} GM mode save created.",
                "status": "unread",
            }
        ],
    }
    seed_startup_free_agents(canonical, save, seed)
    merge_startup_pick_obligations(save, canonical)
    align_real_head_coach_names(canonical, save)
    write_save(save_path, save)
    return save


def load_save(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_save(path: str | Path, save: dict[str, Any]) -> None:
    dedupe_save_event_lists(save)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(save, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


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


def load_pick_obligation_overrides(root: str | Path) -> list[dict[str, Any]]:
    path = Path(root) / "data" / "overrides" / "pick_obligations_overrides.json"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
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
    return sorted(output, key=lambda item: str(item.get("id") or ""))


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


def refresh_roster_cutdowns(canonical: dict[str, Any] | None, save: dict[str, Any]) -> None:
    if canonical is None or not is_league_save(save):
        save.setdefault("pending_roster_cutdowns", [])
        return
    active = active_players_for_roster_checks(canonical, save)
    user_team_id = save.get("meta", {}).get("user_team_id")
    date_value = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    protected_rookies = recent_rookie_protected_player_ids(save)
    pending: list[dict[str, Any]] = []
    for team in canonical.get("teams", []):
        players = sorted(
            [player for player in active if player.get("team_id") == team.get("id")],
            key=lambda player: roster_cut_score(canonical, player),
        )
        target_count = roster_cutdown_target(save, team.get("id"))
        if len(players) <= target_count:
            continue
        overflow = len(players) - target_count
        cuttable = [player for player in players if player.get("id") not in protected_rookies]
        if not cuttable:
            continue
        if team.get("id") != user_team_id:
            for player in cuttable[:overflow]:
                save.setdefault("roster_overrides", {})[player["id"]] = None
                add_news(
                    save,
                    "roster_cut",
                    f"{team.get('abbrev')} waived {player.get('name')} to reach the roster limit.",
                    date_value=date_value,
                )
            continue
        pending.append(
            {
                "id": stable_id("roster_cutdown", team.get("id"), save.get("meta", {}).get("season"), date_value),
                "team_id": team.get("id"),
                "team_abbrev": team.get("abbrev"),
                "current_count": len(players),
                "target_count": target_count,
                "cut_required": min(overflow, len(cuttable)),
                "status": "mandatory_before_regular_season",
                "date": date_value,
                "notes": "Roster overflow is allowed during transactions, but the user must cut to the regular-season limit before advancing into games.",
            }
        )
    save["pending_roster_cutdowns"] = pending


def initial_roster_cutdown_baselines(canonical: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {
        team.get("id"): 0
        for team in canonical.get("teams", [])
        if team.get("id")
    }
    for player in canonical.get("players", []):
        team_id = player.get("team_id")
        if team_id in counts:
            counts[team_id] += 1
    return {team_id: max(ROSTER_SEASON_MAXIMUM, count) for team_id, count in counts.items()}


def roster_cutdown_target(save: dict[str, Any], team_id: str | None) -> int:
    baseline = int((save.get("roster_cutdown_baselines") or {}).get(team_id, ROSTER_SEASON_MAXIMUM))
    return max(ROSTER_SEASON_MAXIMUM, baseline)


def initial_rotation_baselines(canonical: dict[str, Any]) -> dict[str, float]:
    return {
        player["id"]: display_minutes_projection(player)
        for player in canonical.get("players", [])
        if player.get("id")
    }


def active_players_for_roster_checks(canonical: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    players = deepcopy(canonical.get("players", []))
    retired = set(save.get("retired_player_ids", []))
    existing = {player.get("id") for player in players}
    for player in save.get("generated_players", []):
        if player.get("id") not in existing:
            players.append(deepcopy(player))
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


def is_league_save(save: dict[str, Any]) -> bool:
    return save.get("version") == SAVE_VERSION


def ensure_league_save_defaults(save: dict[str, Any], canonical: dict[str, Any] | None = None) -> dict[str, Any]:
    if not is_league_save(save):
        return save
    save.setdefault("meta", {}).setdefault("ai_difficulty", "normal")
    save["meta"]["ai_difficulty"] = normalize_ai_difficulty(save["meta"].get("ai_difficulty"))
    save.setdefault("schedule_state", {}).setdefault("simulated_game_ids", [])
    save.setdefault("season_schedules", {})
    save.setdefault("season_history", [])
    save.setdefault("year_reviews", [])
    save.setdefault("retirement_reports", [])
    save.setdefault("league_awards", [])
    save.setdefault("roster_overrides", {})
    save.setdefault("contract_overrides", {})
    save.setdefault("draft_pick_overrides", {})
    save.setdefault("generated_draft_picks", [])
    save.setdefault("pick_obligations", [])
    save.setdefault("locked_pick_assets", [])
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
    save.setdefault("retired_player_ids", [])
    save.setdefault("roster_cutdown_baselines", initial_roster_cutdown_baselines(canonical or {"players": [], "teams": []}))
    save.setdefault("pending_trade_proposals", [])
    save.setdefault("pending_contract_negotiations", [])
    save.setdefault("pending_draft_selections", [])
    save.setdefault("pending_staff_negotiations", [])
    save.setdefault("pending_ai_actions", [])
    save.setdefault("user_trade_offers", [])
    save.setdefault("pending_roster_cutdowns", [])
    save.setdefault("staff_firing_history", [])
    save.setdefault("staff_interim_review_due", {})
    save.setdefault("staff_retention_windows", [])
    save.setdefault("processed_hidden_ai_actions", [])
    save.setdefault("processed_ai_extensions", [])
    save.setdefault("ai_trade_pressure_player_ids", [])
    save.setdefault("pending_press_events", [])
    save.setdefault("transaction_logs", [])
    save.setdefault("league_events", [])
    save.setdefault("game_results", [])
    save.setdefault("team_morale", initial_team_morale(canonical or {"teams": []}))
    save.setdefault("player_morale", initial_player_morale(canonical or {"players": []}))
    save.setdefault("rotation_recommendations", {})
    save.setdefault("starting_lineups", {})
    save.setdefault("rotation_baselines", initial_rotation_baselines(canonical or {"players": []}))
    save.setdefault("rotation_snapshots", {})
    save.setdefault("fan_confidence", initial_team_metric(canonical or {"teams": []}, 55.0))
    save.setdefault("owner_confidence", initial_team_metric(canonical or {"teams": []}, 56.0))
    save.setdefault("playoff_state", {})
    save.setdefault("draft_state", {})
    save.setdefault("draft_orders", {})
    save.setdefault("team_game_logs", [])
    save.setdefault("player_game_logs", [])
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
    current_date = save.get("state", {}).get("current_date")
    if current_date:
        save.setdefault("state", {})["phase"] = phase_for_date(current_date)
        save["state"]["legal_actions"] = save_legal_actions_for_date(save, current_date)
        expire_user_trade_offers_after_deadline(save, current_date)
    clean_free_agency_state(save, save.get("meta", {}).get("season"))
    if canonical is not None:
        save.setdefault("team_records", initial_team_records(canonical))
        save.setdefault("health_states", sorted(deepcopy(canonical.get("player_health_states", [])), key=lambda item: item["player_id"]))
        save.setdefault("injury_events", sorted(deepcopy(canonical.get("injury_events", [])), key=lambda item: item["id"]))
        save.setdefault("development_events", [])
        save.setdefault("applied_development_months", [])
        if not save.get("staff_slots"):
            save["staff_slots"] = initialize_save_staff_slots(canonical, int(save.get("meta", {}).get("seed") or 1))
        if not save.get("startup_free_agents") and not save.get("free_agent_player_ids"):
            seed_startup_free_agents(canonical, save, int(save.get("meta", {}).get("seed") or 1))
        align_real_head_coach_names(canonical, save)
        seed_morale_if_flat(canonical, save)
        refresh_roster_cutdowns(canonical, save)
    dedupe_save_event_lists(save)
    sync_social_from_news(save)
    dedupe_save_event_lists(save)
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


def canonical_with_save(canonical: dict[str, Any] | Any, save: dict[str, Any]) -> dict[str, Any]:
    """Return a disposable active universe with one save's overrides applied.

    The input canonical universe remains untouched. Derived transaction and
    simulation context is intentionally discarded when save-owned inputs may
    have changed.
    """
    canonical = deepcopy(canonical) if isinstance(canonical, dict) else to_plain(canonical)
    canonical["_allow_internal_caches"] = True
    if not is_league_save(save):
        return canonical
    active_season = save_active_contract_season(save)
    canonical.setdefault("meta", {})["active_season"] = active_season
    canonical.setdefault("meta", {})["current_date"] = save.get("state", {}).get("current_date")
    canonical["save_team_records"] = deepcopy(save.get("team_records", {}))
    canonical["transaction_logs"] = deepcopy(save.get("transaction_logs", []))
    canonical["ai_trade_pressure_player_ids"] = list(save.get("ai_trade_pressure_player_ids", []))
    existing_pick_ids = {pick.get("id") for pick in canonical.get("draft_picks", [])}
    canonical.setdefault("draft_picks", []).extend(
        deepcopy(pick)
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
        for player in save.get("generated_players", []):
            if player.get("id") not in existing:
                canonical.setdefault("players", []).append(deepcopy(player))
                existing.add(player.get("id"))
    if save.get("generated_traits"):
        existing_traits = {
            (trait.get("player_id"), trait.get("trait_key"))
            for trait in canonical.get("traits", [])
        }
        for trait in save.get("generated_traits", []):
            key = (trait.get("player_id"), trait.get("trait_key"))
            if key not in existing_traits:
                canonical.setdefault("traits", []).append(deepcopy(trait))
                existing_traits.add(key)
    apply_effective_player_ages(canonical, save)
    stats_by_player = save.get("player_season_stats") or {}
    if stats_by_player:
        for player in canonical.get("players", []):
            if player.get("id") in stats_by_player:
                player["_save_stats"] = deepcopy(stats_by_player[player["id"]])
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
        mark_expired_or_used_pick(pick, save, active_season)
        if pick["id"] in pick_overrides:
            override = pick_overrides[pick["id"]]
            pick["current_owner_team_id"] = None if override == "used_draft_pick" else override
            if override == "used_draft_pick":
                pick["status"] = "used_draft_pick"
        apply_saved_draft_order_to_pick(pick, save)
    canonical["pick_obligations"] = deepcopy(save.get("pick_obligations", []))
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
        canonical["gameplay_staff_slots"] = deepcopy(save["staff_slots"])
    if save.get("health_states"):
        canonical["player_health_states"] = deepcopy(save["health_states"])
    if save.get("injury_events"):
        canonical["injury_events"] = deepcopy(save["injury_events"])
    if save.get("development_events"):
        canonical["development_events"] = deepcopy(save["development_events"])
        apply_development_events_to_traits(canonical, save["development_events"])
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


def advance_save(root: str | Path, canonical: dict[str, Any] | Any, save_path: str | Path, to_date: str | None = None, next_event: bool = False, seed: int | None = None) -> dict[str, Any]:
    """Advance through every causal checkpoint up to the requested date.

    A long-range action is still chronological: health and games precede the
    record-sensitive AI and phase work that depends on those outcomes.
    """
    root = Path(root)
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    effective_seed = int(seed if seed is not None else save.get("meta", {}).get("seed") or 1)
    if next_event:
        target = next_event_date(root, canonical, save)
    elif to_date:
        target = to_date
    else:
        raise ValueError("advance_save requires to_date or next_event=True")
    if target is None:
        if next_event and current[5:] >= "09-01":
            rollover = complete_offseason_and_rollover(root, canonical, save_path, seed=effective_seed)
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
    guard_required_phase_actions(save, current, target)
    simulated_before = len(save.get("schedule_state", {}).get("simulated_game_ids", []))
    if target > current:
        health_canonical = canonical_with_save(canonical, save)
        health = simulate_health(root, health_canonical, current, target, seed=effective_seed)
        merge_health_results(save, health, health_canonical)
        sim_canonical = canonical_with_save(canonical, save)
        context = load_sim_context(root, sim_canonical)
        context["schedule"] = schedule_for_save(root, save)
        context["indices"] = build_sim_indices(context)
        context["indices"]["coach_by_team"] = save_coach_ratings(sim_canonical, save)
        simulated_game_ids = set(save.get("schedule_state", {}).get("simulated_game_ids", []))
        for game in scheduled_games_between(root, save, current, target):
            game_id = str(game.get("externalGameId"))
            if game_id in simulated_game_ids:
                continue
            result = to_plain(sim_game_with_context(context, game_id, mode="sandbox-sim", seed=effective_seed))
            record_game_result(save, canonical, game, result)
            simulated_game_ids.add(game_id)
        development_canonical = canonical_with_save(canonical, save)
        for month in development_months_between(current, target):
            if month in save.get("applied_development_months", []):
                continue
            development = advance_development(development_canonical, month, seed=effective_seed)
            save.setdefault("development_events", []).extend(development.get("events", []))
            save.setdefault("applied_development_months", []).append(month)
            save.setdefault("news_items", []).append(
                {
                    "id": stable_id("news", "development", month),
                    "date": f"{month}-01",
                    "kind": "development",
                    "headline": f"Monthly player development processed for {month}.",
                    "status": "unread",
                }
            )
            add_notable_development_social(save, development_canonical, development.get("events", []), month)
    set_save_date_phase(save, target)
    expire_user_trade_offers_after_deadline(save, target)
    if save["state"]["phase"] in {"draft_lottery", "draft", "free_agency"}:
        prepare_free_agency_pool(canonical, save)
    elif save["state"]["phase"] in {"preseason", "regular_season", "training_camp"}:
        ensure_roster_minimums(canonical, save, effective_seed)
    inseason_fa_signings = process_inseason_released_free_agent_signings(canonical, save, effective_seed, target)
    queue_ai_recommendations(canonical_with_save(canonical, save), save, current, target, effective_seed)
    add_monthly_social_digest(canonical_with_save(canonical, save), save, current, target)
    maybe_queue_rare_drama(save, canonical, current, target, effective_seed)
    write_save(save_path, save)
    auto_ai = process_ai_actions(canonical, save_path, seed=effective_seed, execute=True, limit=30)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
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


def save_status(root: str | Path, canonical: dict[str, Any] | Any, save_path: str | Path) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
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
    return {
        "version": save.get("version"),
        "save_id": save.get("meta", {}).get("id"),
        "season": season,
        "ai_difficulty": save.get("meta", {}).get("ai_difficulty", "normal"),
        "user_team": user_team,
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "legal_actions": save.get("state", {}).get("legal_actions", []),
        "next_event_date": next_event_date(root, canonical, save),
        "user_team_record": record,
        "pending_counts": pending_counts(save),
        "recent_transactions": save.get("transaction_logs", [])[-5:],
        "recent_news": visible_news[-5:],
        "recent_social": visible_social[-5:],
        "high_importance_social": high_social,
    }


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


def process_ai_actions(canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, execute: bool = False, limit: int = 5) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    processed: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    for action in list(save.get("pending_ai_actions", []))[: max(0, limit)]:
        if action.get("status") in {"processed", "executed", "rejected"}:
            continue
        outcome = {"id": action.get("id"), "action_type": action.get("action_type"), "status": "reviewed"}
        payload = action.get("payload") or {}
        action_date = action.get("date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        if action.get("action_type") == "trade_recommendations":
            accepted = [
                proposal for proposal in payload.get("proposals", [])
                if proposal.get("accepted_by_all") and proposal.get("legality", {}).get("status") == "legal"
            ]
            outcome["accepted_candidate_count"] = len(accepted)
            if execute and accepted:
                from .transactions import apply_trade_to_save
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
                    save.setdefault("pending_trade_proposals", []).append(proposal)
                    write_save(save_path, save)
                    applied_result = apply_trade_to_save(save_path, proposal["proposal"]["id"], date=action_date)
                    save = ensure_league_save_defaults(load_save(save_path), canonical)
                    if applied_result.get("status") == "applied":
                        applied_in_bundle += 1
                        used_assets.update(asset_keys)
                    applied.append(applied_result)
                    active = canonical_with_save(canonical, save)
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
                write_save(save_path, save)
                from .contract_ai import apply_contract_to_save

                applied_result = apply_contract_to_save(save_path, accepted[0]["negotiation"]["id"], date=action_date)
                save = ensure_league_save_defaults(load_save(save_path), canonical)
                applied.append(applied_result)
                outcome["status"] = "executed"
        elif action.get("action_type") == "staff_change_recommendations":
            recommendations = payload.get("recommendations", [])
            outcome["accepted_candidate_count"] = len(recommendations)
            if execute and recommendations:
                staff_result = apply_ai_staff_recommendations(canonical, save, payload, seed)
                applied.extend(staff_result.get("applied", []))
                active = canonical_with_save(canonical, save)
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
        active = canonical_with_save(canonical, save)
    write_save(save_path, save)
    return {
        "processed_count": len(processed),
        "applied_count": len(applied),
        "execute": execute,
        "processed": processed,
        "applied": applied,
        "notes": "AI action processing is conservative: only legal accepted recommendations execute, and only when --execute is set.",
    }


def trade_asset_identity_keys(proposal: dict[str, Any]) -> set[str]:
    payload = proposal.get("proposal") or proposal
    keys: set[str] = set()
    for asset in list(payload.get("from_assets") or []) + list(payload.get("to_assets") or []):
        kind = str(asset.get("kind") or "").lower()
        identifier = asset.get("id") or asset.get("player_id") or asset.get("pick_id") or asset.get("value")
        if kind and identifier:
            keys.add(f"{kind}:{identifier}")
    return keys


def apply_ai_staff_recommendations(canonical: dict[str, Any], save: dict[str, Any], payload: dict[str, Any], seed: int) -> dict[str, Any]:
    active = canonical_with_save(canonical, save)
    user_team_id = save.get("meta", {}).get("user_team_id")
    signed_staff_candidate_ids: set[str] = set()
    applied: list[dict[str, Any]] = []
    date_value = payload.get("through_date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    for recommendation in payload.get("recommendations", []):
        team_id = recommendation.get("team_id")
        slot = recommendation.get("slot")
        if team_id == user_team_id:
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
                active = canonical_with_save(canonical, save)
            if action == "fire_only" or not recommendation.get("candidate_id"):
                continue
        if recommendation.get("candidate_id") in signed_staff_candidate_ids:
            applied.append({"status": "not_applied", "recommendation_id": recommendation.get("id"), "notes": "Candidate already accepted another staff job in this bundle."})
            continue
        offer = recommendation.get("recommended_offer") or {}
        try:
            negotiation = negotiate_staff_hire(
                active,
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
        applied_result = hire_staff_from_save(save, negotiation["id"])
        if applied_result.get("status") == "applied":
            signed_staff_candidate_ids.add(recommendation.get("candidate_id"))
            save.setdefault("staff_interim_review_due", {}).pop(f"{team_id}:{slot}", None)
        applied.append(applied_result)
        active = canonical_with_save(canonical, save)
    return {"applied_count": len([item for item in applied if item.get("status") == "applied"]), "applied": applied}


def negotiation_player_is_free(active: dict[str, Any], save: dict[str, Any], item: dict[str, Any]) -> bool:
    player_id = (item.get("negotiation") or {}).get("player_id") or (item.get("decision") or {}).get("player_id")
    player = next((row for row in active.get("players", []) if row.get("id") == player_id), {})
    return not player.get("team_id") or player_id in set(save.get("free_agent_player_ids", []))


def negotiation_has_positive_accepted_offer(item: dict[str, Any]) -> bool:
    if not item.get("accepted"):
        return False
    offer = (item.get("decision") or {}).get("accepted_offer") or {}
    if not offer:
        return False
    return float(offer.get("annual_salary") or offer.get("aav") or 0) > 0


def calendar_view(root: str | Path, canonical: dict[str, Any] | Any, save_path: str | Path, from_date: str | None = None, through_date: str | None = None) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    start = from_date or current
    end = through_date or next_date_str(start, 14)
    team_by_espn = espn_team_id_map(canonical)
    simulated = set(save.get("schedule_state", {}).get("simulated_game_ids", []))
    results = {str(result.get("game_id")): result for result in save.get("game_results", [])}
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
                    "overtime_periods": max([int(line.get("overtime_periods") or 0) for line in result.get("team_lines", [])], default=0) if result else 0,
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
                "overtime_periods": max([int(line.get("overtime_periods") or 0) for line in result.get("team_lines", [])], default=0) if result else 0,
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
        raise ValueError(f"No simulated game result found for {game_id!r}.")
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    player_lines = sorted(
        result.get("player_lines", []),
        key=lambda item: (item.get("team_abbrev", ""), -float(item.get("minutes") or 0), item.get("player_name", "")),
    )
    return {
        "game_id": result.get("game_id"),
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
        "notes": result.get("notes"),
    }


def league_standings(canonical: dict[str, Any] | Any, save_path: str | Path) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
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
        rows.append(
            {
                "player": players.get(player_id, {"id": player_id, "name": totals.get("player_name")}),
                "team_id": totals.get("team_id"),
                "team_abbrev": totals.get("team_abbrev"),
                "games": totals.get("games", 0),
                stat_key: round(float(totals.get(stat_key, 0)), 2),
                f"{stat_key}_per_game": round(float(totals.get(stat_key, 0)) / games, 2),
            }
        )
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
    best_score = -1_000_000.0
    best_assignment: tuple[tuple[float, float, str, dict[str, Any], dict[str, float]], ...] | None = None
    for assignment in permutations(candidate_rows, len(slots)):
        total = 0.0
        for slot, row in zip(slots, assignment, strict=False):
            _, minutes, _, player, attrs = row
            total += starting_slot_score(player, slot, minutes, attrs)
        if total > best_score:
            best_score = total
            best_assignment = assignment
    if not best_assignment:
        return {}
    return {
        slot: row[3]["id"]
        for slot, row in zip(slots, best_assignment, strict=False)
        if row[3].get("id")
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
    auto = auto_starting_five(canonical, save, team_id)
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


def starting_five_rows(canonical: dict[str, Any], save: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    slots = starting_lineup_slots(canonical, save, team_id, persist=True)
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
) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    events = [enriched_league_event(canonical, save, event) for event in save.get("league_events", [])]
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
    for asset in [*(details.get("from_assets") or []), *(details.get("to_assets") or [])]:
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


def playoff_picture(canonical: dict[str, Any] | Any, save_path: str | Path) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    rows = league_standings(canonical, save_path)["standings"]
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
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    picture = playoff_picture(canonical, save_path)["picture"]
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
        write_save(save_path, save)
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
    write_save(save_path, save)
    return save["playoff_state"]


def legacy_first_round_series(canonical: dict[str, Any], picture: dict[str, Any]) -> list[dict[str, Any]]:
    del canonical
    series: list[dict[str, Any]] = []
    matchups = [(1, 8), (4, 5), (3, 6), (2, 7)]
    for conference, seeded in picture.items():
        by_seed = {row["seed"]: row for row in seeded}
        for high_seed, low_seed in matchups:
            if high_seed not in by_seed or low_seed not in by_seed:
                continue
            series.append(playoff_series_record(conference, "first_round", by_seed[high_seed]["team_id"], by_seed[low_seed]["team_id"]))
    return series


def simulate_playoff_round(canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, root: str | Path | None = None) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state") or start_playoffs(canonical, save_path, seed=seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state", state)
    current_round = state.get("round")
    if current_round == "play_in":
        completed_play_in = simulate_play_in(canonical, save, seed, root)
        first_round = first_round_series_from_play_in(canonical, state)
        state["series"].extend(first_round)
        state["round"] = "first_round"
        for conference in completed_play_in:
            add_news(save, "playoffs", f"{conference} play-in tournament completed.")
        save["playoff_state"] = state
        update_save_date_to_latest_playoff_game(save)
        write_save(save_path, save)
        return {"completed_play_in": completed_play_in, "playoff_state": state}
    open_series = [series for series in state.get("series", []) if series.get("round") == current_round and series.get("status") != "completed"]
    completed: list[dict[str, Any]] = []
    for series in open_series:
        simulate_series_games(canonical, save, state, series, seed, root)
        winner = max((series.get("wins") or {}).items(), key=lambda item: item[1])[0]
        loser = next(team_id for team_id in series["team_ids"] if team_id != winner)
        series["winner_team_id"] = winner
        series["status"] = "completed"
        completed.append(series)
        add_news(save, "playoffs", f"{team_by_id(canonical, winner)['abbrev']} wins {series['round']} series.")
    winners = [series["winner_team_id"] for series in state.get("series", []) if series.get("round") == current_round and series.get("winner_team_id")]
    if current_round == "finals" and len(winners) == 1:
        complete_playoff_champion(canonical, save, state, winners[0])
    elif open_series and all(series.get("status") == "completed" for series in open_series):
        next_round = next_playoff_round(current_round)
        state["round"] = next_round
        state["series"].extend(next_round_series(canonical, state, winners, next_round))
    save["playoff_state"] = state
    update_save_date_to_latest_playoff_game(save)
    write_save(save_path, save)
    return {"completed_series": completed, "playoff_state": state}


def complete_playoff_champion(canonical: dict[str, Any], save: dict[str, Any], state: dict[str, Any], winner_team_id: str) -> None:
    state["champion_team_id"] = winner_team_id
    state["status"] = "completed"
    state["round"] = "champion"
    add_news(save, "champion", f"{team_by_id(canonical, winner_team_id)['abbrev']} wins the NBA title.")
    award_finals_mvp(save, canonical)
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
    set_save_date_phase(save, f"{int(state.get('year') or season_end_year(save.get('meta', {}).get('season') or CANONICAL_SEASON))}-06-22")


def simulate_next_playoff_game(canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1, root: str | Path | None = None) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state") or start_playoffs(canonical, save_path, seed=seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state", state)
    current_round = state.get("round")
    if current_round == "play_in":
        return simulate_playoff_round(canonical, save_path, seed=seed, root=root)
    open_series = [
        series for series in state.get("series", [])
        if series.get("round") == current_round and series.get("status") != "completed"
    ]
    if not open_series:
        return {"status": "no_open_series", "playoff_state": state}
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
    current_series = [item for item in state.get("series", []) if item.get("round") == current_round]
    if current_series and all(item.get("status") == "completed" for item in current_series):
        winners = [item["winner_team_id"] for item in current_series if item.get("winner_team_id")]
        if current_round == "finals" and len(winners) == 1:
            complete_playoff_champion(canonical, save, state, winners[0])
        else:
            next_round = next_playoff_round(current_round)
            state["round"] = next_round
            state["series"].extend(next_round_series(canonical, state, winners, next_round))
    save["playoff_state"] = state
    update_save_date_to_latest_playoff_game(save)
    write_save(save_path, save)
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
    base = playoff_round_start_date(year, series.get("round"))
    game_date = (base + timedelta(days=(game_no - 1) * 2)).isoformat()
    result = simulate_playoff_game(canonical, save, root, away, home, game_date, seed, f"{series['id']}:g{game_no}")
    winner = game_winner_team_id(result)
    wins[winner] = int(wins.get(winner) or 0) + 1
    series["wins"] = wins
    series.setdefault("game_ids", []).append(result.get("game_id"))
    series["game_ids"] = sorted(set(series.get("game_ids", [])))
    return result


def lottery_seed(seed: int | None = None) -> int:
    if seed is not None:
        return int(seed)
    return random.SystemRandom().randrange(1, 2_147_483_647)


def run_draft_lottery(canonical: dict[str, Any] | Any, save_path: str | Path, year: str = "2026", seed: int | None = None) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    from .draft import generate_draft_order

    effective_seed = lottery_seed(seed)
    standings = save_standings_for_draft(canonical, save)
    order = generate_draft_order(canonical_with_save(canonical, save), year, seed=effective_seed, standings=standings)
    annotate_lottery_odds_context(canonical, save, order)
    resolve_pick_obligations_for_year(save, order, str(year))
    refresh_draft_order_from_save(order, save)
    save.setdefault("draft_orders", {})[str(year)] = order
    add_news(save, "draft_lottery", f"{year} draft order generated.")
    current_phase = save.get("state", {}).get("phase")
    if current_phase == "draft_lottery":
        set_save_date_phase(save, f"{year}-06-25")
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


def resolve_pick_obligations_for_year(save: dict[str, Any], order: dict[str, Any], year: str) -> None:
    draft_order = order.get("draft_order") or []
    by_pick = {}
    for item in draft_order:
        if item.get("id"):
            by_pick[item.get("id")] = item
        if item.get("pick_id"):
            by_pick[item.get("pick_id")] = item
    locked = set(save.setdefault("locked_pick_assets", []))
    for obligation in save.get("pick_obligations", []):
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
            protected = obligation.get("protected_range") or {}
            low = int(protected.get("from") or 1)
            high = int(protected.get("through") or obligation.get("protected_top_n") or 0)
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

            pick_a_id = obligation.get("team_a_pick_id") or obligation.get("primary_pick_id")
            pick_b_id = obligation.get("team_b_pick_id") or obligation.get("counterparty_pick_id")
            row_a = by_pick.get(pick_a_id)
            row_b = by_pick.get(pick_b_id)
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


def simulate_play_in(canonical: dict[str, Any], save: dict[str, Any], seed: int, root: str | Path | None) -> list[str]:
    state = save.setdefault("playoff_state", {})
    year = int(state.get("year") or season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON))
    completed: list[str] = []
    for conference, payload in (state.get("play_in") or {}).items():
        if payload.get("status") == "completed":
            completed.append(conference)
            continue
        teams = payload.get("teams") or {}
        if not all(str(seed_no) in teams for seed_no in [7, 8, 9, 10]):
            payload["status"] = "incomplete"
            continue
        game1 = simulate_playoff_game(canonical, save, root, teams["8"], teams["7"], f"{year}-04-13", seed, f"{conference}:7v8")
        game2 = simulate_playoff_game(canonical, save, root, teams["10"], teams["9"], f"{year}-04-14", seed, f"{conference}:9v10")
        seed7 = game_winner_team_id(game1)
        loser78 = game_loser_team_id(game1)
        winner910 = game_winner_team_id(game2)
        game3 = simulate_playoff_game(canonical, save, root, winner910, loser78, f"{year}-04-16", seed, f"{conference}:8seed")
        seed8 = game_winner_team_id(game3)
        payload["seed_7_team_id"] = seed7
        payload["seed_8_team_id"] = seed8
        payload["games"] = [game1.get("game_id"), game2.get("game_id"), game3.get("game_id")]
        payload["status"] = "completed"
        completed.append(conference)
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
        for high_seed, low_seed in matchups:
            if high_seed not in seeds or low_seed not in seeds:
                continue
            series.append(playoff_series_record(conference, "first_round", seeds[high_seed], seeds[low_seed]))
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
    game_id = stable_id("playoff_game", key, away_team_id, home_team_id)
    existing = next((result for result in save.get("game_results", []) if str(result.get("game_id")) == game_id), None)
    if existing:
        return existing
    if root is None:
        return deterministic_playoff_game_result(canonical, save, away_team_id, home_team_id, game_id, game_date, seed)
    active = canonical_with_save(canonical, save)
    context = load_sim_context(root, active)
    espn_by_team = {team["id"]: espn_id for espn_id, team in espn_team_id_map(active).items()}
    game = {
        "externalGameId": game_id,
        "gameDate": game_date,
        "phase": "playoffs",
        "awayTeamId": espn_by_team.get(away_team_id, away_team_id),
        "homeTeamId": espn_by_team.get(home_team_id, home_team_id),
    }
    context["schedule"] = list(context.get("schedule") or []) + [game]
    context["indices"] = build_sim_indices(context)
    context["indices"]["coach_by_team"] = save_coach_ratings(active, save)
    result = to_plain(sim_game_with_context(context, game_id, mode="sandbox-sim", seed=seed))
    record_playoff_game_result(save, game, result)
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
    if any(str(existing.get("game_id")) == game_id for existing in save.get("game_results", [])):
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


def award_finals_mvp(save: dict[str, Any], canonical: dict[str, Any] | None = None) -> dict[str, Any] | None:
    state = save.get("playoff_state") or {}
    champion = state.get("champion_team_id")
    if not champion:
        return None
    candidates = [
        totals for totals in save.get("playoff_player_stats", {}).values()
        if totals.get("team_id") == champion and int(totals.get("finals_games") or 0) > 0
    ]
    if not candidates:
        candidates = [totals for totals in save.get("playoff_player_stats", {}).values() if totals.get("team_id") == champion]
    if not candidates:
        return None
    def score(row: dict[str, Any]) -> float:
        games = max(1, int(row.get("games") or 1))
        finals_boost = 1.25 if int(row.get("finals_games") or 0) else 1.0
        return finals_boost * (
            float(row.get("points") or 0) / games
            + 1.15 * float(row.get("rebounds") or 0) / games
            + 1.35 * float(row.get("assists") or 0) / games
            + 2.6 * float(row.get("steals") or 0) / games
            + 2.6 * float(row.get("blocks") or 0) / games
            - 1.1 * float(row.get("turnovers") or 0) / games
        )
    winner = max(candidates, key=score)
    award = {
        "player_id": winner.get("player_id"),
        "player_name": winner.get("player_name"),
        "team_id": winner.get("team_id"),
        "team_abbrev": winner.get("team_abbrev"),
        "impact_score": round(score(winner), 3),
        "source": "save_playoff_player_stats",
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


def complete_offseason_and_rollover(root: str | Path, canonical: dict[str, Any] | Any, save_path: str | Path, seed: int = 1) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    current_season = save.get("meta", {}).get("season") or CANONICAL_SEASON
    draft_result = ensure_draft_processed(canonical, save, str(season_end_year(current_season)), seed)
    awards = generate_league_awards(canonical, save, current_season, seed)
    history_entry = {
        "season": current_season,
        "completed_on": save.get("state", {}).get("current_date"),
        "team_records": deepcopy(save.get("team_records", {})),
        "player_season_stats": deepcopy(save.get("player_season_stats", {})),
        "playoff_state": deepcopy(save.get("playoff_state", {})),
        "draft_order": deepcopy((save.get("draft_orders") or {}).get(str(season_end_year(current_season)), {})),
        "draft_result": deepcopy(draft_result),
        "awards": deepcopy(awards),
        "transaction_count": len(save.get("transaction_logs", [])),
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
    save["applied_development_months"] = []
    save["free_agency_state"] = {}
    clean_free_agency_state(save, next_label)
    refresh_health_for_new_season(save, f"{next_start}-10-01")
    age_staff_contracts(save, canonical, seed=seed)
    save["pending_offseason_review"] = {
        "season": current_season,
        "generated_date": f"{next_start}-10-01",
        "review_id": review.get("id") if review else None,
        "retirement_report_id": (save.get("retirement_reports") or [{}])[-1].get("id"),
    }
    add_news(save, "season_rollover", f"{next_label} season is ready for training camp.", date_value=f"{next_start}-10-01")
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


def team_dashboard(root: str | Path, canonical: dict[str, Any] | Any, save_path: str | Path, team_query: str) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    should_write = bool(prune_rotation_recommendations(save, canonical))
    team = resolve_team(canonical, team_query)
    active = canonical_with_save(canonical, save)
    rotation_projection = team_rotation_projection(active, save, team["id"], integer=True)
    lineup_before = json.dumps(save.setdefault("starting_lineups", {}).get(team["id"], {}), sort_keys=True)
    starting_slots = starting_lineup_slots(active, save, team["id"], persist=True)
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
    if should_write:
        write_save(save_path, save)
    record = save.get("team_records", {}).get(team["id"], empty_team_record(team))
    logs = [log for log in save.get("team_game_logs", []) if log.get("team_id") == team["id"]]
    health = [
        state for state in save.get("health_states", []) if next((player for player in active.get("players", []) if player["id"] == state["player_id"] and player["team_id"] == team["id"]), None)
    ]
    phase = save.get("state", {}).get("phase")
    use_playoff_stats = phase in {"play_in", "playoffs"} and bool(save.get("playoff_player_stats"))
    season_stats = save.get("playoff_player_stats", {}) if use_playoff_stats else save.get("player_season_stats", {})
    stats_context = {
        "label": "Playoffs" if use_playoff_stats else "Regular season",
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
    identity_metrics = team_identity_report(active, save)
    salary_seasons: set[str] = set()
    for player in roster:
        salary_seasons.update(str(season) for season in player_salary_table(active, player["id"]).keys())
    cap_by_year = {
        season: team_cap_summary(active, save, team["id"], season=season)
        for season in sorted(salary_seasons)[:6]
    }
    return {
        "team": team,
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "record": record,
        "rotation": [
            {
                "id": player["id"],
                "name": player["name"],
                "position": player.get("position"),
                "age": player.get("age"),
                "height": player.get("height"),
                "height_inches": player.get("height_inches"),
                "minutes_projection": float(rotation_projection.get(player["id"], display_minutes_projection(player))),
                "coach_minutes_projection": float(rotation_projection.get(player["id"], display_minutes_projection(player))),
                "is_starting_five": player["id"] in slot_by_player,
                "starting_slot": slot_by_player.get(player["id"]),
                "season_minutes_per_game": per_game_stat(season_stats.get(player["id"], {}), "minutes"),
                "display_mpg": (
                    per_game_stat(season_stats.get(player["id"], {}), "minutes")
                    if int(season_stats.get(player["id"], {}).get("games") or 0) > 0
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
                "fg_pct": percentage_stat(season_stats.get(player["id"], {}), "fgm", "fga"),
                "fg3_pct": percentage_stat(season_stats.get(player["id"], {}), "fg3m", "fg3a"),
                "fg3a_per_game": per_game_stat(season_stats.get(player["id"], {}), "fg3a"),
                "fta_per_game": per_game_stat(season_stats.get(player["id"], {}), "fta"),
                "ft_pct": percentage_stat(season_stats.get(player["id"], {}), "ftm", "fta"),
                "health": player_health_label(health_by_player.get(player["id"]), save.get("state", {}).get("current_date")),
                "attributes": player_attribute_summary(active, player["id"]),
                "salary_by_year": player_salary_table(active, player["id"]),
                "minutes_recommendation": recommendations.get(player["id"]),
            }
            for player in roster
        ],
        "last_games": sorted(logs, key=lambda item: item["date"], reverse=True)[:5],
        "next_games": next_team_games(root, canonical, save, team["id"], limit=5),
        "health_summary": health_summary(health),
        "stats_context": stats_context,
        "starting_five": starting_five_rows(active, save, team["id"]),
        "staff_slots": sorted([slot for slot in save.get("staff_slots", []) if slot.get("team_id") == team["id"]], key=lambda item: item["slot"]),
        "cap_posture": next((state.get("salary_posture") for state in canonical.get("team_strategic_states", []) if state["team_id"] == team["id"]), "unknown"),
        "cap_summary": team_cap_summary(active, save, team["id"], season=save_active_contract_season(save)),
        "cap_by_year": cap_by_year,
        "team_identity": identity_metrics.get(team["id"], {}),
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
        defense = weighted("defense") * 0.46 + weighted("def_effort") * 0.18 + weighted("screen_nav") * 0.12 + weighted("rim_deterrence") * 0.16 + weighted("portability") * 0.08
        creation = weighted("creation") * 0.48 + weighted("handle") * 0.22 + weighted("passing") * 0.20 + weighted("versatility") * 0.10
        spacing = weighted("shooting") * 0.40 + weighted("range") * 0.36 + weighted("release") * 0.12 + weighted("versatility") * 0.12
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
            "rim_protection": round(clamp(weighted("rim_deterrence"), 1, 99), 1),
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
    if "06-27" <= month_day <= "07-15":
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
        "free_agency": ["free_agent_signings", "trades", "staff_changes", "press_conferences", "social_media", "advance"],
        "training_camp": ["staff_changes", "press_conferences", "social_media", "advance"],
        "offseason": ["extensions", "staff_changes", "press_conferences", "social_media", "advance"],
    }
    return actions.get(phase, ["advance"])


def ensure_game_settings(save: dict[str, Any]) -> dict[str, Any]:
    settings = save.setdefault("game_settings", {})
    settings.setdefault("press_conferences_enabled", False)
    return settings


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
    for game in schedule_for_save(root, save):
        if game.get("gameDate", "") > current and str(game.get("externalGameId")) not in set(save.get("schedule_state", {}).get("simulated_game_ids", [])):
            return game.get("gameDate")
    end_year = season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    for date_value in [f"{end_year}-04-13", f"{end_year}-06-22", f"{end_year}-06-25", f"{end_year}-07-01", f"{end_year}-09-01"]:
        if date_value > current:
            return date_value
    return None


def guard_required_phase_actions(save: dict[str, Any], current: str, target: str) -> None:
    end_year = season_end_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    start_year = season_start_year(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    regular_start_gate = f"{start_year}-10-21"
    playoff_gate = f"{end_year}-06-22"
    draft_gate = f"{end_year}-06-27"
    phase = save.get("state", {}).get("phase")
    if current < regular_start_gate <= target and save.get("pending_roster_cutdowns"):
        team = save.get("pending_roster_cutdowns", [{}])[0]
        raise ValueError(
            f"{team.get('team_abbrev') or 'Your team'} has {team.get('current_count')} players. "
            f"Cut to {team.get('target_count') or ROSTER_SEASON_MAXIMUM} before opening night."
        )
    if current < playoff_gate <= target:
        state = save.get("playoff_state") or {}
        if phase in {"play_in", "playoffs"} and state.get("status") != "completed":
            raise ValueError("The playoffs are active. Open the playoff bracket and sim rounds before advancing to the draft lottery.")
    if current < draft_gate <= target:
        draft_state = save.get("draft_state") or {}
        pending = save.get("pending_draft_selections") or []
        if phase == "draft" and (draft_state.get("status") not in {"completed", "skipped"} or pending):
            raise ValueError("The draft is active. Finish or sim the draft before advancing to free agency.")


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
    for line in result.get("player_lines", []):
        update_player_stats(save, line, game)
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


def update_player_stats(save: dict[str, Any], line: dict[str, Any], game: dict[str, Any]) -> None:
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


def morale_report(canonical: dict[str, Any] | Any, save_path: str | Path, team_query: str | None = None) -> dict[str, Any]:
    canonical = to_plain(canonical)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    if team_query:
        team = resolve_team(canonical, team_query)
        player_ids = {player["id"] for player in canonical_with_save(canonical, save).get("players", []) if player["team_id"] == team["id"]}
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
    save = ensure_league_save_defaults(load_save(save_path), canonical)
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


def merge_health_results(save: dict[str, Any], health: dict[str, Any], canonical: dict[str, Any] | None = None) -> None:
    players = {player["id"]: player for player in (canonical or {}).get("players", [])}
    previous_states = {state.get("player_id"): state for state in save.get("health_states", [])}
    save["health_states"] = health.get("final_states", save.get("health_states", []))
    current_states = {state.get("player_id"): state for state in save.get("health_states", [])}
    seen = {event.get("id") for event in save.get("injury_events", [])}
    socialized = set(save.setdefault("socialized_injury_event_ids", []))
    for event in health.get("events", []):
        if event.get("id") not in seen:
            save.setdefault("injury_events", []).append(event)
            seen.add(event.get("id"))
        player = players.get(event.get("player_id"), {})
        player_name = player.get("name") or event.get("player_id") or "A player"
        games = event.get("expected_games_missed") or event.get("expected_days_missed") or "some"
        expected_games = int(event.get("expected_games_missed") or 0)
        player_mpg = display_minutes_projection(player) if player else 0.0
        if expected_games > MAJOR_INJURY_GAMES_THRESHOLD and player_mpg > MAJOR_PLAYER_MPG_THRESHOLD:
            add_league_event(
                save,
                "injury",
                f"{player_name} is expected to miss about {games} games with a {event.get('body_area')} issue.",
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
                f"{player_name} is expected to miss about {games} games with a {event.get('body_area')} issue.",
                date_value=event.get("start_date"),
            )
            socialized.add(event.get("id"))
    save["socialized_injury_event_ids"] = sorted(item for item in socialized if item)
    add_return_from_injury_social(save, canonical or {}, previous_states, current_states)
    save["injury_events"] = sorted(save.get("injury_events", []), key=lambda item: item.get("id", ""))


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


def queue_ai_recommendations(canonical: dict[str, Any], save: dict[str, Any], from_date: str, through_date: str, seed: int) -> None:
    phase = save.get("state", {}).get("phase")
    queued_keys = {item.get("id") for item in save.get("pending_ai_actions", [])} | {item.get("id") for item in save.get("processed_hidden_ai_actions", [])}
    if phase in {"preseason", "regular_season"} and through_date <= extension_deadline_date(season_start_year_from_date(through_date)):
        extension_key = stable_id("ai_action", "extensions", through_date[:7], seed)
        if extension_key not in queued_keys:
            extension_result = process_ai_extensions(canonical, save, through_date, seed)
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
    trade_start = f"{season_start_year_from_date(through_date)}-11-15"
    trade_deadline = trade_deadline_date(season_start_year_from_date(through_date))
    trade_window_open = phase == "preseason" or trade_start <= through_date <= trade_deadline
    if "trades" in legal_actions_for_date(through_date) and trade_window_open:
        action_id = stable_id("ai_action", "trades", through_date, seed)
        if action_id not in queued_keys:
            from .transactions import simulate_ai_trades

            payload = simulate_ai_trades(canonical, from_date, through_date, seed=seed, limit=35)
            user_team_id = save.get("meta", {}).get("user_team_id")
            legal_accepted = [
                proposal for proposal in payload.get("proposals", [])
                if proposal.get("accepted_by_all") and proposal.get("legality", {}).get("status") == "legal"
            ]
            user_offers = [
                proposal for proposal in legal_accepted
                if user_team_id in {
                    (proposal.get("proposal") or {}).get("from_team_id"),
                    (proposal.get("proposal") or {}).get("to_team_id"),
                }
            ][:4]
            if user_offers:
                queue_user_trade_offers(save, user_offers, through_date)
            try:
                window_days = max(1, (parse_date(through_date) - parse_date(from_date)).days)
            except (TypeError, ValueError):
                window_days = 31
            checkpoint_cap = 1 if window_days <= 10 else 3
            season_trade_count = sum(
                1
                for log in save.get("transaction_logs", [])
                if log.get("transaction_type") == "trade"
                and f"{season_start_year_from_date(through_date)}-10-01" <= str(log.get("date") or "") <= trade_deadline
            )
            proposal_cap = max(0, min(checkpoint_cap, 28 - season_trade_count))
            payload["proposals"] = [
                proposal for proposal in legal_accepted
                if user_team_id not in {
                    (proposal.get("proposal") or {}).get("from_team_id"),
                    (proposal.get("proposal") or {}).get("to_team_id"),
                }
            ][:proposal_cap]
            payload["proposal_count"] = len(payload["proposals"])
            if not payload["proposals"]:
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
        or phase in {"training_camp", "offseason", "draft_lottery", "draft", "free_agency"}
        or through_date.endswith("-02-05")
    )
    if staff_review_due:
        action_id = stable_id("ai_action", "staff", through_date[:7], phase, seed)
        if action_id not in queued_keys:
            payload = simulate_ai_staff_changes(canonical, save, from_date, through_date, seed=seed, limit=8)
            if payload.get("recommendations"):
                result = apply_ai_staff_recommendations(canonical, save, payload, seed)
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
    existing = {
        ((offer.get("proposal") or {}).get("id") or offer.get("id"))
        for offer in save.setdefault("user_trade_offers", [])
    }
    queued = 0
    for offer in offers:
        proposal_id = (offer.get("proposal") or {}).get("id") or offer.get("id")
        if not proposal_id or proposal_id in existing:
            continue
        save["user_trade_offers"].append(
            {
                **offer,
                "offer_context": {
                    **(offer.get("offer_context") or {}),
                    "created_date": date_value,
                    "status": "pending_user_review",
                    "source": "ai_trade_offer_to_user",
                },
            }
        )
        existing.add(proposal_id)
        queued += 1
    if queued:
        add_news(save, "trade_offer", f"{queued} AI trade offer(s) arrived for your review.", date_value=date_value)


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


def process_ai_extensions(canonical: dict[str, Any], save: dict[str, Any], through_date: str, seed: int, limit: int = 22) -> dict[str, Any]:
    from .contract_ai import extension_candidates_report, merge_extension_offer_with_existing_contract, negotiate_extension, with_contract_context

    active = with_contract_context(canonical_with_save(canonical, save))
    report = extension_candidates_report(active)
    user_team_id = save.get("meta", {}).get("user_team_id")
    processed = set(save.setdefault("processed_ai_extensions", []))
    applied = 0
    refusals = 0
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    for candidate in report.get("candidates", []):
        player_id = candidate.get("player_id")
        team_id = candidate.get("team_id")
        key = stable_id("ai_extension", save.get("meta", {}).get("season"), team_id, player_id)
        if not player_id or not team_id or key in processed or team_id == user_team_id:
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
        if priority < 50.0:
            # Fringe or bad-fit cases stay live for later checkpoints instead of being
            # burned for the full season before their role/team context has settled.
            continue
        result = negotiate_extension(active, player.get("name", player_id), team.get("abbrev", team_id), seed=seed, max_rounds=3, date=through_date)
        if result.get("accepted") and (result.get("decision") or {}).get("accepted_offer"):
            negotiation = result.get("negotiation") or {}
            offer = dict((result.get("decision") or {}).get("accepted_offer") or {})
            offer.setdefault("team_id", team_id)
            offer.setdefault("start_season", extension_start_season_from_date_save(through_date))
            offer = ai_adjust_extension_offer_for_current_season(save, candidate, player, offer, priority)
            offer = merge_extension_offer_with_existing_contract(offer, negotiation)
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
                    "evaluations": [{"priority": round(priority, 2), "source": "ai_extension"}],
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
            trait["value"] = round(clamp(float(trait.get("value") or 50.0) + deltas[key], 0, 100), 3)
            trait["notes"] = f"{trait.get('notes', '')} Save-state development deltas applied.".strip()
    canonical.pop("_trait_values_by_player", None)


def apply_save_rotation_projection(canonical: dict[str, Any], save: dict[str, Any]) -> None:
    teams = {team["id"] for team in canonical.get("teams", [])}
    snapshots = save.setdefault("rotation_snapshots", {})
    health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
    baselines = save.get("rotation_baselines") or {}
    for team_id in sorted(teams):
        projection = team_rotation_projection(canonical, save, team_id, integer=False)
        if not projection:
            continue
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


def team_rotation_projection(canonical: dict[str, Any], save: dict[str, Any], team_id: str | None, integer: bool = False) -> dict[str, float]:
    if not team_id:
        return {}
    roster = [player for player in canonical.get("players", []) if player.get("team_id") == team_id]
    if not roster:
        return {}
    health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
    recommendations = save.get("rotation_recommendations") or {}
    baselines = save.get("rotation_baselines") or {}
    rows: list[dict[str, Any]] = []
    for player in roster:
        baseline = float(baselines.get(player["id"], display_minutes_projection(player)) or 0.0)
        baseline = clamp(baseline, 0.0, 42.0)
        attrs = player_attribute_summary(canonical, player["id"])
        overall = float(attrs.get("overall") or 50.0)
        unavailable = player_unavailable_for_rotation(health_by_player.get(player["id"]))
        rec = recommendations.get(player["id"])
        raw_score = baseline * 1.35 + overall * 0.46 + max(0.0, float(player.get("age") or 27.0) - 32.0) * -0.7
        rows.append(
            {
                "player": player,
                "baseline": baseline,
                "overall": overall,
                "unavailable": unavailable,
                "recommendation": rec,
                "score": raw_score,
            }
        )
    available = [row for row in rows if not row["unavailable"]]
    if not available:
        return {row["player"]["id"]: 0.0 for row in rows}
    available.sort(key=lambda row: (row["score"], row["baseline"], row["overall"], row["player"].get("name", "")), reverse=True)
    desired_count = min(len(available), max(9, min(11, sum(1 for row in available if row["baseline"] >= 8.0))))
    selected_ids = {row["player"]["id"] for row in available[:desired_count]}
    for row in available:
        rec = row.get("recommendation") or {}
        if float(rec.get("target_minutes") or 0.0) > 0:
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


def player_unavailable_for_rotation(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
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
    return {
        "trades": len(save.get("pending_trade_proposals", [])),
        "contracts": len(save.get("pending_contract_negotiations", [])),
        "draft": len(save.get("pending_draft_selections", [])),
        "staff": len([item for item in save.get("staff_retention_windows", []) if item.get("status") == "pending_user_decision"]),
        "user_trade_offers": len([item for item in save.get("user_trade_offers", []) if (item.get("offer_context") or {}).get("status") == "pending_user_review"]),
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


def next_team_games(root: str | Path, canonical: dict[str, Any], save: dict[str, Any], team_id: str, limit: int = 5) -> list[dict[str, Any]]:
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    team_by_espn = espn_team_id_map(canonical)
    espn_by_team = {team["id"]: espn_id for espn_id, team in team_by_espn.items()}
    team_espn = espn_by_team.get(team_id)
    games = []
    for game in schedule_for_save(root, save):
        if game.get("gameDate", "") <= current:
            continue
        if str(game.get("homeTeamId")) != team_espn and str(game.get("awayTeamId")) != team_espn:
            continue
        home = team_by_espn.get(str(game.get("homeTeamId")), {})
        away = team_by_espn.get(str(game.get("awayTeamId")), {})
        games.append({"game_id": str(game.get("externalGameId")), "date": game.get("gameDate"), "away_team": away.get("abbrev"), "home_team": home.get("abbrev")})
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
        values.setdefault(player_id, {})[trait_key] = float(trait.get("value") or 50.0)
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


def player_attribute_summary(canonical: dict[str, Any], player_id: str) -> dict[str, float]:
    traits = trait_values_by_player(canonical).get(player_id, {})
    player = players_by_id_index(canonical).get(player_id, {})
    minutes = display_minutes_projection(player)

    def avg(keys: list[str], default: float = 50.0) -> float:
        values = [traits.get(key, default) for key in keys]
        return sum(values) / max(1, len(values))

    shooting = avg(["shooting_range", "shot_versatility", "release_speed"])
    creation = avg(["handle_pressure", "passing_reads", "rim_pressure", "shot_versatility"])
    defense = avg(["defensive_effort", "scheme_iq", "screen_navigation", "rim_deterrence"])
    athleticism = avg(["foot_speed_lateral_agility", "stamina_cardio", "rim_pressure"])
    iq = avg(["scheme_iq", "passing_reads", "portability", "playoff_translation"])
    rebounding = traits.get("offensive_rebounding", 50.0) * 0.66 + traits.get("rim_deterrence", 50.0) * 0.18 + traits.get("stamina_cardio", 50.0) * 0.16
    overall = shooting * 0.22 + creation * 0.25 + defense * 0.22 + athleticism * 0.13 + iq * 0.12 + min(6.0, minutes / 7.0)
    return {
        "overall": round(clamp(overall, 1, 99), 1),
        "shooting": round(clamp(shooting, 1, 99), 1),
        "creation": round(clamp(creation, 1, 99), 1),
        "defense": round(clamp(defense, 1, 99), 1),
        "athleticism": round(clamp(athleticism, 1, 99), 1),
        "iq": round(clamp(iq, 1, 99), 1),
        "release": round(clamp(traits.get("release_speed", 50.0), 1, 99), 1),
        "range": round(clamp(traits.get("shooting_range", 50.0), 1, 99), 1),
        "versatility": round(clamp(traits.get("shot_versatility", 50.0), 1, 99), 1),
        "handle": round(clamp(traits.get("handle_pressure", 50.0), 1, 99), 1),
        "rim_pressure": round(clamp(traits.get("rim_pressure", 50.0), 1, 99), 1),
        "passing": round(clamp(traits.get("passing_reads", 50.0), 1, 99), 1),
        "stamina": round(clamp(traits.get("stamina_cardio", 50.0), 1, 99), 1),
        "rebounding": round(clamp(rebounding, 1, 99), 1),
        "def_effort": round(clamp(traits.get("defensive_effort", 50.0), 1, 99), 1),
        "screen_nav": round(clamp(traits.get("screen_navigation", 50.0), 1, 99), 1),
        "rim_deterrence": round(clamp(traits.get("rim_deterrence", 50.0), 1, 99), 1),
        "oreb": round(clamp(traits.get("offensive_rebounding", 50.0), 1, 99), 1),
        "portability": round(clamp(traits.get("portability", 50.0), 1, 99), 1),
        "playoff": round(clamp(traits.get("playoff_translation", 50.0), 1, 99), 1),
    }


def player_salary_table(canonical: dict[str, Any], player_id: str) -> dict[str, float | None]:
    contract = next((item for item in canonical.get("contracts", []) if item.get("player_id") == player_id), None)
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


def player_health_label(state: dict[str, Any] | None, current_date: str | None) -> dict[str, Any]:
    if not state:
        return {"status": "ok", "label": "", "games_missed": 0}
    status = state.get("availability_status") or "active"
    if status == "active":
        return {"status": "ok", "label": "", "games_missed": int(state.get("games_missed") or 0)}
    return_date = state.get("return_date")
    days_left = None
    if return_date and current_date:
        days_left = max(0, (parse_date(return_date) - parse_date(current_date)).days)
    severity = state.get("injury_severity") or state.get("current_injury_severity") or "injured"
    label = f"{severity}"
    if days_left is not None:
        label = f"{label} ~{max(1, round(days_left / 2.4))}g"
    return {"status": status, "label": label, "days_left": days_left, "games_missed": int(state.get("games_missed") or 0)}


def cap_lines_for_season(season: str | None) -> dict[str, float]:
    active = str(season or CANONICAL_SEASON)
    seasons_elapsed = max(0, season_start_year(active) - season_start_year(CANONICAL_SEASON))
    factor = (1.0 + ANNUAL_CAP_GROWTH_RATE) ** seasons_elapsed
    return {
        "tax_line": round(TAX_LINE * factor / 100_000) * 100_000,
        "hard_cap": round(SECOND_APRON * factor / 100_000) * 100_000,
        "growth_factor": round(factor, 5),
    }


def team_cap_summary(canonical: dict[str, Any], save: dict[str, Any], team_id: str, season: str | None = None) -> dict[str, Any]:
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
    tax_line = float(lines["tax_line"])
    hard_cap = float(lines["hard_cap"])
    tax_space = tax_line - total
    hard_cap_space = hard_cap - total
    return {
        "season": season,
        "salary_total": round(total, 2),
        "salary_total_millions": round(total / 1_000_000, 2),
        "tax_line_millions": round(tax_line / 1_000_000, 2),
        "hard_cap_millions": round(hard_cap / 1_000_000, 2),
        "tax_space_millions": round(tax_space / 1_000_000, 2),
        "hard_cap_space_millions": round(hard_cap_space / 1_000_000, 2),
        "tax_space_pct": round(tax_space / tax_line * 100, 1),
        "hard_cap_space_pct": round(hard_cap_space / hard_cap * 100, 1),
        "cap_growth_factor": lines["growth_factor"],
        "unresolved_contract_count": unresolved,
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
    return seasons


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


def next_round_series(canonical: dict[str, Any], state: dict[str, Any], winners: list[str], next_round: str) -> list[dict[str, Any]]:
    if next_round == "champion":
        return []
    teams_by_id = {team["id"]: team for team in canonical.get("teams", [])}
    if next_round == "finals":
        east = [team_id for team_id in winners if teams_by_id.get(team_id, {}).get("conference") == "East"]
        west = [team_id for team_id in winners if teams_by_id.get(team_id, {}).get("conference") == "West"]
        if not east or not west:
            return []
        return [playoff_series_record("Finals", next_round, east[0], west[0])]
    new_series = []
    for conference in ["East", "West"]:
        conf_winners = [team_id for team_id in winners if teams_by_id.get(team_id, {}).get("conference") == conference]
        conf_winners.sort()
        for index in range(0, len(conf_winners), 2):
            if index + 1 < len(conf_winners):
                new_series.append(playoff_series_record(conference, next_round, conf_winners[index], conf_winners[index + 1]))
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
    free_agents: list[str] = list(save.get("free_agent_player_ids", []))
    retired: list[str] = list(save.get("retired_player_ids", []))
    retired_this_offseason: list[str] = []
    expired: list[str] = []
    for player in active.get("players", []):
        player_id = player["id"]
        if not player.get("team_id"):
            continue
        age = float(player.get("age") or 27.0) + 1.0
        contract = contracts.get(player_id)
        if should_retire(player, age, seed, next_season) and not (age < 42 and contract_has_salary_in_or_after(contract, next_season)):
            save.setdefault("roster_overrides", {})[player_id] = None
            if player_id not in retired:
                retired.append(player_id)
                retired_this_offseason.append(player_id)
            continue
        if contract and contract_last_season(contract) and contract_last_season(contract) < next_season:
            if should_ai_retain_expiring_player(save, player, current_season, seed):
                retain_expiring_player(save, player, player.get("team_id"), current_season, next_season, seed)
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
    if retired_this_offseason:
        retirements = [
            {
                "player_id": player_id,
                "name": players.get(player_id, {}).get("name"),
                "age": round(float(players.get(player_id, {}).get("age") or 0.0) + 1.0, 1),
                "position": players.get(player_id, {}).get("position"),
            }
            for player_id in retired_this_offseason
        ]
        report = {
            "id": stable_id("retirement_report", current_season, next_season),
            "season": current_season,
            "next_season": next_season,
            "date": f"{season_start_year(next_season)}-07-01",
            "retirements": sorted(retirements, key=lambda item: (-(float(item.get("age") or 0)), item.get("name") or "")),
        }
        upsert_by_id(save, "retirement_reports", report)
        names = ", ".join(item["name"] for item in report["retirements"][:5] if item.get("name"))
        add_news(save, "retirement", f"Retirement report: {names or len(retired_this_offseason)} player(s) retired.", date_value=report["date"])
    if expired or retired_this_offseason or signed:
        add_news(
            save,
            "offseason_rosters",
            f"Offseason roster transitions: {len(expired)} free agents, {len(retired_this_offseason)} retirements, {len(strategic_signed)} AI signings, {len(signed) - len(strategic_signed)} depth repairs.",
            date_value=f"{season_start_year(next_season)}-09-01",
        )
    return {
        "expired_free_agents": len(expired),
        "retirements": len(retired_this_offseason),
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


def generate_league_awards(canonical: dict[str, Any], save: dict[str, Any], season: str, seed: int = 1) -> list[dict[str, Any]]:
    existing = [award for award in save.get("league_awards", []) if award.get("season") == season]
    if existing:
        return sorted(existing, key=lambda item: item.get("award", ""))
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    stats = save.get("player_season_stats", {})
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
        team_record = save.get("team_records", {}).get(player.get("team_id"), {})
        team_games = max(1, int(team_record.get("wins", 0)) + int(team_record.get("losses", 0)))
        win_pct = float(team_record.get("wins", 0)) / team_games
        ppg = per_game_stat(totals, "points")
        rpg = per_game_stat(totals, "rebounds")
        apg = per_game_stat(totals, "assists")
        spg = per_game_stat(totals, "steals")
        bpg = per_game_stat(totals, "blocks")
        mpg = minutes_total / max(1, games)
        rookie = is_rookie_for_awards(player, season, save)
        candidates.append(
            {
                "player_id": player_id,
                "player_name": player.get("name"),
                "team_id": player.get("team_id"),
                "team_abbrev": teams.get(player.get("team_id"), {}).get("abbrev", player.get("team_abbrev")),
                "games": games,
                "minutes_per_game": round(mpg, 1),
                "points_per_game": ppg,
                "rebounds_per_game": rpg,
                "assists_per_game": apg,
                "steals_per_game": spg,
                "blocks_per_game": bpg,
                "overall": float(attrs.get("overall") or 50.0),
                "defense": float(attrs.get("defense") or 50.0),
                "rim_deterrence": float(attrs.get("rim_deterrence") or 50.0),
                "def_effort": float(attrs.get("def_effort") or 50.0),
                "screen_nav": float(attrs.get("screen_nav") or 50.0),
                "win_pct": round(win_pct, 3),
                "rookie": rookie,
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

    award_specs = {
        "MVP": lambda row: row["points_per_game"] * 1.25 + row["assists_per_game"] * 1.08 + row["rebounds_per_game"] * 0.66 + row["overall"] * 0.42 + row["win_pct"] * 17.0 + min(5.0, row["games"] / 14.0) + small_noise(row["player_id"], "MVP"),
        "ROTY": lambda row: (-999.0 if not row["rookie"] else row["points_per_game"] * 1.18 + row["assists_per_game"] * 0.92 + row["rebounds_per_game"] * 0.72 + row["overall"] * 0.48 + row["minutes_per_game"] * 0.18 + small_noise(row["player_id"], "ROTY")),
        "DPOY": dpoy_score,
    }
    awards: list[dict[str, Any]] = []
    for award_name, score_fn in award_specs.items():
        winner = max(candidates, key=score_fn)
        if score_fn(winner) < -100:
            continue
        record = {
            "id": stable_id("league_award", season, award_name),
            "season": season,
            "award": award_name,
            "player_id": winner["player_id"],
            "player_name": winner["player_name"],
            "team_id": winner["team_id"],
            "team_abbrev": winner["team_abbrev"],
            "score": round(score_fn(winner), 3),
            "stat_line": {
                "pts": winner["points_per_game"],
                "reb": winner["rebounds_per_game"],
                "ast": winner["assists_per_game"],
                "stl": winner["steals_per_game"],
                "blk": winner["blocks_per_game"],
                "gp": winner["games"],
            },
            "notes": "V1 award voting proxy using saved season stats, team success, minutes/games played, and trait-based impact indicators.",
        }
        awards.append(record)
        headline = f"{winner['player_name']} wins {award_name} for {season} ({winner['team_abbrev']})."
        add_news(save, "award", headline, date_value=f"{season_end_year(season)}-06-30")
    save.setdefault("league_awards", []).extend(awards)
    save["league_awards"] = sorted(
        {award["id"]: award for award in save["league_awards"]}.values(),
        key=lambda item: (item.get("season", ""), item.get("award", "")),
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
    free_agents = set(save.get("free_agent_player_ids", []))
    expired: list[str] = []
    for player in active.get("players", []):
        player_id = player.get("id")
        if not player_id or not player.get("team_id"):
            continue
        contract = contracts.get(player_id)
        last = contract_last_season(contract) if contract else None
        if last and last <= current_season:
            if should_ai_retain_expiring_player(save, player, current_season, seed):
                retain_expiring_player(save, player, player.get("team_id"), current_season, next_season, seed)
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
            f"Free agency opened with {len(expired)} expired contracts entering the market.",
            date_value=save.get("state", {}).get("current_date"),
        )
    return {
        "status": "prepared",
        "expired_contracts": len(expired),
        "retirements": retirement_count,
        "free_agent_pool_count": len(save.get("free_agent_player_ids", [])),
    }


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
    retirements = [
        {
            "player_id": player_id,
            "name": players.get(player_id, {}).get("name"),
            "age": round(float(players.get(player_id, {}).get("display_age", players.get(player_id, {}).get("age") or 0.0)), 1),
            "position": players.get(player_id, {}).get("position"),
        }
        for player_id in retired_this_offseason
    ]
    report = {
        "id": stable_id("retirement_report", current_season, next_season),
        "season": current_season,
        "next_season": next_season,
        "date": f"{season_start_year(next_season)}-07-01",
        "retirements": sorted(retirements, key=lambda item: (-(float(item.get("age") or 0)), item.get("name") or "")),
    }
    upsert_by_id(save, "retirement_reports", report)
    names = ", ".join(item["name"] for item in report["retirements"][:5] if item.get("name"))
    add_news(save, "retirement", f"Retirement report: {names or len(retired_this_offseason)} player(s) retired.", date_value=report["date"])
    clean_free_agency_state(save, current_season)
    return len(retired_this_offseason)


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


def should_ai_retain_expiring_player(save: dict[str, Any], player: dict[str, Any], season: str, seed: int) -> bool:
    team_id = player.get("team_id")
    if not team_id or team_id == save.get("meta", {}).get("user_team_id"):
        return False
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


def retain_expiring_player(save: dict[str, Any], player: dict[str, Any], team_id: str | None, current_season: str, next_season: str, seed: int) -> None:
    if not team_id:
        return
    minutes = display_minutes_projection(player)
    age = float(player.get("age") or 27.0)
    score = minutes * 0.72 + per_game_stat(save.get("player_season_stats", {}).get(player.get("id"), {}), "points") * 0.25
    years = 3 if age <= 29 and minutes >= 24 else 2 if age <= 33 and minutes >= 16 else 1
    salary = int(round(clamp(2_200_000 + minutes * 520_000 + max(0.0, score - 18.0) * 320_000, 2_000_000, 32_000_000)))
    seasons = [
        {
            "season": season_label_from_start(season_start_year(next_season) + offset),
            "salary": int(round(salary * (1.035 ** offset))),
            "option_type": None,
            "guarantee_status": "ai_re_signing",
        }
        for offset in range(years)
    ]
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
        save.setdefault("draft_state", {})["status"] = "completed"
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
    if not contract:
        return False
    if contract.get("status") != "save_state_contract_override":
        return False
    return any(
        entry.get("salary") is not None and str(entry.get("season") or "") >= str(season)
        for entry in contract.get("seasons", [])
    )


def contract_last_season(contract: dict[str, Any]) -> str | None:
    seasons = [str(entry.get("season")) for entry in contract.get("seasons", []) if entry.get("salary") is not None and entry.get("season")]
    return max(seasons) if seasons else None


def strategic_free_agent_signings(canonical: dict[str, Any], save: dict[str, Any], free_agents: list[str], next_season: str, seed: int) -> set[str]:
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
            save.setdefault("roster_overrides", {})[player["id"]] = team["id"]
            save.setdefault("contract_overrides", {})[player["id"]] = {
                "team_id": team["id"],
                "seasons": [
                    {
                        "season": next_season,
                        "salary": salary,
                        "option_type": None,
                        "guarantee_status": "ai_offseason_signing",
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


def process_inseason_released_free_agent_signings(canonical: dict[str, Any], save: dict[str, Any], seed: int, date_value: str) -> set[str]:
    phase = save.get("state", {}).get("phase") or phase_for_date(date_value)
    if phase not in {"preseason", "regular_season"}:
        return set()
    if date_value > trade_deadline_date(season_start_year_from_date(date_value)):
        return set()
    released = save.setdefault("released_free_agents", {})
    if not released:
        return set()
    pool = set(save.get("free_agent_player_ids") or [])
    retired = set(save.get("retired_player_ids") or [])
    active = canonical_with_save(canonical, save)
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
        if not released_free_agent_is_meaningful(active, player, profile):
            continue
        attrs = player_attribute_summary(active, player_id)
        desirability = display_minutes_projection(player) * 1.25 + float(attrs.get("overall") or 0.0) + released_free_agent_salary(player, profile, attrs) / 1_000_000 * 0.12
        candidates.append((desirability, player, release))
    signed: set[str] = set()
    for _, player, release in sorted(candidates, key=lambda item: (-item[0], item[1].get("name", "")))[:3]:
        active = canonical_with_save(canonical, save)
        profile = next((item for item in active.get("player_contract_market_profiles", []) if item.get("player_id") == player["id"]), {})
        attrs = player_attribute_summary(active, player["id"])
        salary = released_free_agent_salary(player, profile, attrs)
        destination = released_free_agent_destination(active, save, player, release, salary, seed, date_value)
        if not destination:
            continue
        team = destination["team"]
        cut_player = destination.get("cut_player")
        if cut_player:
            waive_ai_depth_player_for_released_free_agent(save, cut_player, team, date_value, player)
        apply_inseason_released_free_agent_signing(save, player, team, salary, date_value, destination["score"])
        signed.add(player["id"])
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


def released_free_agent_destination(
    canonical: dict[str, Any],
    save: dict[str, Any],
    player: dict[str, Any],
    release: dict[str, Any],
    salary: int,
    seed: int,
    date_value: str,
) -> dict[str, Any] | None:
    user_team_id = save.get("meta", {}).get("user_team_id")
    waived_by = release.get("waived_by_team_id")
    season = save_active_contract_season(save)
    candidates: list[dict[str, Any]] = []
    attrs = player_attribute_summary(canonical, player["id"])
    player_value = float(attrs.get("overall") or 0.0) * 0.72 + display_minutes_projection(player) * 1.35
    protected = recent_rookie_protected_player_ids(save)
    for team in canonical.get("teams", []):
        team_id = team.get("id")
        if team_id in {user_team_id, waived_by}:
            continue
        if not ai_team_can_absorb_released_free_agent(canonical, save, team_id, salary, season):
            continue
        roster = [item for item in canonical.get("players", []) if item.get("team_id") == team_id]
        cut_player = None
        if len(roster) >= ROSTER_SEASON_MAXIMUM:
            cuttable = [
                item for item in roster
                if item.get("id") not in protected and display_minutes_projection(item) <= 14.0
            ]
            if not cuttable:
                continue
            cut_player = sorted(cuttable, key=lambda item: (roster_cut_score(canonical, item), display_minutes_projection(item), item.get("name", "")))[0]
            if player_value - roster_cut_score(canonical, cut_player) < 16.0:
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
            score += min(9.0, max(0.0, player_value - roster_cut_score(canonical, cut_player)) * 0.18)
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


def waive_ai_depth_player_for_released_free_agent(save: dict[str, Any], cut_player: dict[str, Any], team: dict[str, Any], date_value: str, incoming_player: dict[str, Any]) -> None:
    player_id = cut_player["id"]
    save.setdefault("roster_overrides", {})[player_id] = None
    save.setdefault("free_agent_player_ids", [])
    if player_id not in save["free_agent_player_ids"]:
        save["free_agent_player_ids"].append(player_id)
        save["free_agent_player_ids"] = sorted(save["free_agent_player_ids"])
    save.setdefault("released_free_agents", {})[player_id] = {
        "player_id": player_id,
        "player_name": cut_player.get("name"),
        "waived_by_team_id": team["id"],
        "waived_by_team_abbrev": team.get("abbrev"),
        "release_date": date_value,
        "status": "available",
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
            candidate = next((player for player in available if player["id"] not in signed), None)
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


def ensure_roster_minimums(canonical: dict[str, Any], save: dict[str, Any], seed: int) -> set[str]:
    season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    active = canonical_with_save(canonical, save)
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


def generate_future_schedule(root: str | Path, season: str, start_year: int) -> dict[str, Any]:
    template_games = [game for game in load_schedule(root) if game.get("phase") == "regular"]
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
    return {
        "season": season,
        "template": "NBA Schedule/schedule_v2025_2026.json",
        "game_count": len(games),
        "games": sorted(games, key=lambda item: (item["gameDate"], str(item["externalGameId"]))),
        "notes": "Generated future schedule from the 2025-26 date/home-away template with deterministic randomized opponents.",
    }


def randomize_future_matchups(template_games: list[dict[str, Any]], season: str) -> list[dict[str, Any]]:
    rng = random.Random(f"{season}:future_schedule")
    away_pool = [game.get("awayTeamId") for game in template_games]
    rng.shuffle(away_pool)
    output: list[dict[str, Any]] = []
    used_by_date: dict[str, set[str]] = {}
    for game in sorted(template_games, key=lambda item: (item.get("gameDate", ""), str(item.get("externalGameId")))):
        date_key = str(game.get("gameDate"))
        home_id = str(game.get("homeTeamId"))
        used = used_by_date.setdefault(date_key, {home_id})
        selected_index = None
        for idx, candidate in enumerate(away_pool):
            candidate_id = str(candidate)
            if candidate_id != home_id and candidate_id not in used:
                selected_index = idx
                break
        if selected_index is None:
            selected_index = next((idx for idx, candidate in enumerate(away_pool) if str(candidate) != home_id), 0)
        away_id = away_pool.pop(selected_index)
        used.add(str(away_id))
        output.append({**game, "awayTeamId": away_id})
    return output


def refresh_health_for_new_season(save: dict[str, Any], start_date: str) -> None:
    refreshed = []
    for state in save.get("health_states", []):
        refreshed.append(
            {
                **state,
                "id": stable_id("health_state", state.get("player_id"), start_date),
                "as_of_date": start_date,
                "fatigue": 0.0,
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
    for staff in save.get("staff_slots", []):
        staff = deepcopy(staff)
        contract = staff.setdefault("contract", {})
        years = int(contract.get("years_remaining") or 1)
        contract["years_remaining"] = max(0, years - 1)
        if contract["years_remaining"] == 0:
            team_id = staff.get("team_id")
            slot = staff.get("slot")
            if team_id and slot:
                if team_id == save.get("meta", {}).get("user_team_id") and not is_interim_staff(staff):
                    add_staff_retention_window(save, staff, date_value)
                    staff["market_status"] = "contract_expired_pending_user_decision"
                    staff["job_security"] = min(float(staff.get("job_security") or 50.0), 45.0)
                    updated.append(staff)
                    continue
                retained = ai_staff_retention_contract(canonical, save, staff, seed, date_value) if not is_interim_staff(staff) else None
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


def ai_staff_retention_contract(canonical: dict[str, Any] | None, save: dict[str, Any], staff: dict[str, Any], seed: int, date_value: str) -> dict[str, Any] | None:
    if canonical is None:
        return None
    team_id = staff.get("team_id")
    slot = staff.get("slot")
    if not team_id or not slot:
        return None
    grade = staff_grade(staff)
    context = ai_staff_retention_context(canonical, save, staff)
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


def ai_staff_retention_context(canonical: dict[str, Any], save: dict[str, Any], staff: dict[str, Any]) -> dict[str, Any]:
    team_id = staff.get("team_id")
    slot = staff.get("slot")
    grade = staff_grade(staff)
    underperforming = team_underperformed_staff_expectation(canonical, save, team_id)
    triggered_failure = staff_slot_failure_signal(canonical, save, team_id, slot)
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


def staff_slot_failure_signal(canonical: dict[str, Any], save: dict[str, Any], team_id: str | None, slot: str | None) -> str | None:
    if not team_id or not slot:
        return None
    if slot == "development_lead" and team_development_gain(save, team_id)["failed"]:
        return "team development lagged expectations"
    if slot == "scouting_lead" and team_recent_draft_return(save, team_id)["failed"]:
        return "recent draft return disappointed"
    if slot == "performance_lead" and team_injury_games_missed(canonical, save, team_id) >= 170:
        return "team injury burden was too high"
    return None


def team_development_gain(save: dict[str, Any], team_id: str) -> dict[str, Any]:
    events = [event for event in save.get("development_events", []) if event.get("team_id") == team_id]
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


def team_injury_games_missed(canonical: dict[str, Any], save: dict[str, Any], team_id: str) -> int:
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
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
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
