"""Expose the Python game engine as JSON-compatible application actions.

This is an interface boundary, not a second rules engine. CLI, browser, and
future native clients should share these domain mutations; per-save locks
serialize cooperating local processes as well as requests in this process.
"""

from __future__ import annotations

import base64
import binascii
import random
import threading
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .contract_ai import (
    apply_contract_to_save,
    extension_candidates_report,
    extension_contract_window,
    free_agents_report,
    negotiate_extension,
    projected_retirement_start_year,
    with_contract_context,
    with_extension_context,
)
from .draft import draft_board_report, generate_draft_order, whole_prospect_age
from .diagnostics import diagnostic_runtime
from .extension_analysis import extension_analysis_payload
from .fantasy_draft import (
    apply_fantasy_draft_pick,
    fantasy_draft_room,
    resolve_fantasy_team,
    simulate_fantasy_draft_all,
    simulate_fantasy_draft_one,
    simulate_fantasy_draft_until_human,
    toggle_fantasy_draft_watchlist,
)
from .ingest import build_universe, enrich_player_external_metadata, load_player_external_metadata
from .history_store import active_season_floor, load_history_records, validate_save_components
from .save_locking import save_lock
from .simulation_progress import simulation_stop_requested
from .save_recovery import (
    MAX_ARCHIVE_BYTES, create_export, ensure_new_save_path, previous_backup_path,
    recover_previous_save, restore_export,
)
from .save import (
    ROSTER_SEASON_MAXIMUM,
    decline_watch_value,
    advance_save,
    add_news,
    annotate_lottery_odds_context,
    box_score_view,
    calendar_view,
    canonical_with_save,
    advance_lifecycle_to,
    create_league_save,
    display_minutes_projection,
    display_rating_averages,
    display_rating_tertiles,
    ensure_game_settings,
    ensure_league_save_defaults,
    extension_deadline_date,
    extension_start_season_from_date_save,
    is_rookie_for_awards,
    league_events_view,
    league_leaders,
    league_standings,
    load_save,
    morale_report,
    next_event_date,
    narrative_settings_view,
    per_game_stat,
    player_attribute_summary,
    player_display_attribute_summary,
    RATING_SCALE,
    player_health_label,
    player_salary_table,
    player_unavailable_for_rotation,
    playoff_leaders,
    playoff_picture,
    postseason_exit_required,
    initialize_postseason,
    repair_unplayed_playoff_round,
    press_conferences_enabled,
    process_ai_actions,
    recent_rookie_protected_player_ids,
    refresh_roster_cutdowns,
    save_legal_actions_for_date,
    save_active_contract_season,
    save_standings_for_draft,
    save_status,
    season_start_year_from_date,
    simulate_next_playoff_game,
    simulate_playoff_round,
    starting_lineup_slots,
    social_feed_view,
    run_draft_lottery,
    set_save_date_phase,
    team_cap_summary,
    team_dashboard,
    team_identity_report,
    team_id_to_abbrev,
    team_rotation_projection,
    trade_deadline_date,
    write_save,
)
from .schema import CANONICAL_SEASON, CANONICAL_START_DATE, to_plain
from .spatial import player_spatial_profile
from .staff import (
    fire_staff_from_save,
    hire_staff_from_save,
    negotiate_staff_hire,
    resolve_staff_retention_re_sign,
    staff_budget_snapshot,
    staff_grade,
    staff_market_report,
    staff_retention_snapshot,
    staff_team_report,
)
from .storage import JSON_FILENAME, load_universe_json
from .transactions import (
    apply_trade_to_save,
    canonical_with_pending_pick_terms,
    contract_for_player,
    clean_pick_protection_summary,
    current_salary,
    evaluate_trade,
    fallback_asset_valuation,
    find_trade,
    find_trade_for_assets,
    market_trade_target_value,
    pick_by_id,
    pick_asset_value,
    pick_display_label,
    pick_obligation_context_note,
    pick_obligation_label,
    pick_swap_asset_value,
    pick_swap_by_id,
    pick_swap_display_label,
    prune_trade_offers_touching_assets,
    resolve_team,
    team_by_id,
    trade_candidate_with_current_asset_labels,
    trade_headline_from_payload,
    trade_offer_fingerprint,
    tradeable_pick_swaps_for_team,
    tradeable_picks_for_team,
    with_transaction_context,
)
from .pick_presentation import draft_assets_display, pick_presentation, swap_presentation
from .utils import copy_plain, stable_id


PROSPECT_SCOUT_TRAIT_ORDER = (
    "shooting", "shot_creation", "defense", "athleticism", "passing", "rim_pressure",
    "rebounding", "rim_protection", "feel", "size", "motor", "nba_readiness",
)
PROSPECT_CARD_RATING_DEPENDENCIES = {
    "shooting": {"shooting"}, "release": {"shooting", "nba_readiness", "motor"},
    "range": {"shooting", "shot_creation", "feel"}, "versatility": {"shooting", "shot_creation", "feel"},
    "spacing": {"shooting", "shot_creation", "feel"}, "creation": {"shot_creation"},
    "handle": {"shot_creation", "passing", "athleticism", "feel"},
    "passing": {"passing", "feel", "nba_readiness"},
    "rim_pressure": {"rim_pressure", "athleticism", "size"}, "defense": {"defense"},
    "def_effort": {"defense", "motor", "athleticism", "nba_readiness"},
    "screen_nav": {"defense", "athleticism", "feel", "motor"},
    "steal": {"defense", "athleticism"}, "block": {"rim_protection"},
    "rim_deterrence": {"rim_protection", "size", "defense", "athleticism"},
    "rebounding": {"rebounding"}, "oreb": {"rebounding", "size", "motor"},
    "athleticism": {"athleticism"}, "lateral_agility": {"athleticism", "defense", "motor"},
    "stamina": {"motor", "nba_readiness", "athleticism"}, "iq": {"feel"},
    "scheme_iq": {"feel", "defense", "nba_readiness", "passing"},
    "portability": {"shooting", "defense", "feel", "nba_readiness", "athleticism", "size"},
    "playoff": {"feel", "nba_readiness", "shot_creation"},
}


def prospect_card_ratings(prospect: dict[str, Any], scout: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Return only player-card ratings supported by this team's revealed scout traits."""
    try:
        coverage = float(scout.get("scouted_pct") or 0)
    except (TypeError, ValueError):
        coverage = 0
    trait_count = 12 if coverage >= 100 else 11 if coverage >= 90 else 9 if coverage >= 75 else 7 if coverage >= 60 else 5 if coverage >= 45 else 3 if coverage >= 20 else 0
    visible = set(PROSPECT_SCOUT_TRAIT_ORDER[:trait_count])
    if not visible:
        return {"ratings": {}, "ratings_revealed": 0, "ratings_total": len(PROSPECT_CARD_RATING_DEPENDENCIES)}

    from .prospect_cards import prospect_rating_projection

    projected = scout.get("ratings")
    if projected is None:
        projected = prospect_rating_projection({}, prospect, report, coverage)["ratings"]
    ratings = {
        key: projected[key]
        for key, dependencies in PROSPECT_CARD_RATING_DEPENDENCIES.items()
        if key in projected and dependencies.issubset(visible)
    }
    return {
        "ratings": ratings,
        "ratings_revealed": len(ratings),
        "ratings_total": len(PROSPECT_CARD_RATING_DEPENDENCIES),
    }


APP_ACTION_PROTOCOL_VERSION = "app_actions_v1"
DEFAULT_SAVE_DIR = "saves"
_READ_CACHE: dict[str, dict[str, Any]] = {}
_READ_CACHE_GUARD = threading.Lock()
# Each entry owns a full save, active universe and rendered read payloads.
# Keep the two most recently used careers, rather than retaining every opened
# path for the server's lifetime. In-flight requests retain their own context.
_READ_CACHE_LIMIT = 2


class AppActionError(ValueError):
    pass


def dispatch_app_action(
    action: str,
    payload: dict[str, Any] | None = None,
    *,
    root: str | Path = ".",
    save_dir: str | Path | None = None,
    canonical: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dispatch one read or mutation and serialize access to an active save."""
    action = str(action or "").replace("-", "_")
    root_path = Path(root)
    payload = dict(payload or {})
    if action == "diagnostic_runtime":
        return diagnostic_runtime(root_path)
    data = canonical or load_app_canonical(root_path)
    saves = Path(save_dir) if save_dir is not None else root_path / DEFAULT_SAVE_DIR
    validate_app_save_paths(saves, payload)
    saves.mkdir(parents=True, exist_ok=True)

    if action == "runtime_status":
        return runtime_status(root_path, saves)
    if action == "teams":
        return teams_payload(data)
    if action == "list_saves":
        return list_saves(saves)
    if action == "create_save":
        return create_save_action(root_path, data, saves, payload)
    if action == "restore_save":
        encoded = payload.get("archive_base64")
        if not isinstance(encoded, str) or len(encoded) > ((MAX_ARCHIVE_BYTES + 2) // 3) * 4:
            raise AppActionError("Choose an NBA GM backup smaller than 128 MB.")
        try:
            archive = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise AppActionError("The backup upload is malformed. Select the exported backup again.") from exc
        name = str(payload.get("save_name") or "restored_save")
        save_path = resolve_app_save_path(saves, {"save_name": safe_filename(name)})
        result = restore_export(save_path, archive)
        invalidate_read_cache(save_path)
        return result

    save_path = resolve_app_save_path(saves, payload)
    if save_path.exists() and action not in {"export_save", "recover_save"}:
        from .baselines import baseline_for_save

        data = baseline_for_save(data, load_save(save_path))
    if action == "export_save":
        return {"filename": f"{safe_filename(save_path.stem)}.nbagm.zip", "archive_base64": base64.b64encode(create_export(save_path)).decode("ascii")}
    if action == "recover_save":
        with save_lock(save_path):
            result = recover_previous_save(save_path)
            invalidate_read_cache(save_path)
            return result
    if action in MUTATING_ACTIONS:
        with save_lock(save_path):
            # A mutating request may build and return the replacement dashboard
            # snapshot itself. Clear the old revision before dispatch so that
            # fresh snapshot remains available to follow-up modal reads.
            invalidate_read_cache(save_path)
            from .save import action_runtime_scope
            with action_runtime_scope():
                result = dispatch_save_action(action, payload, root_path, data, save_path)
            return result
    if action in {"dashboard_snapshot", "team_assets", "player_card", "prospect_card", "coach_card", "free_agency_room", "team_wants"}:
        with save_lock(save_path):
            return dispatch_save_action(action, payload, root_path, data, save_path)
    return dispatch_save_action(action, payload, root_path, data, save_path)


MUTATING_ACTIONS = {
    "advance_save",
    "advance_re_signing",
    "advance_free_agency",
    "apply_contract",
    "submit_extension_offer",
    "apply_trade",
    "apply_trade_candidate",
    "draft_apply_current",
    "draft_reveal_lottery",
    "draft_sim_all",
    "draft_sim_to_user",
    "fantasy_draft_pick",
    "fantasy_draft_sim_one",
    "fantasy_draft_sim_all",
    "fantasy_draft_sim_to_user",
    "fantasy_draft_watchlist",
    "fire_staff",
    "hire_staff",
    "negotiate_staff",
    "process_ai_actions",
    "respond_user_trade_offer",
    "resolve_staff_retention",
    "waive_player",
    "buyout_player",
    "claim_waiver",
    "set_rotation_minutes",
    "set_player_rest",
    "set_team_block",
    "set_team_wants",
    "acknowledge_team_wants",
    "set_starting_five",
    "simulate_playoff_all",
    "simulate_playoff_game",
    "simulate_playoff_round",
    "submit_free_agent_offer",
    "renounce_cap_hold",
    "update_game_settings",
    "season_slideshow",
    "season_slideshow_seen",
}


def runtime_status(root: Path, save_dir: Path) -> dict[str, Any]:
    return {
        "protocol_version": APP_ACTION_PROTOCOL_VERSION,
        "engine": "nba_gm_data",
        "root": str(root),
        "save_dir": str(save_dir),
        "runtime": {
            "python_embeddable": True,
            "macos_standalone_target": True,
            "ios_standalone_target": True,
            "requires_remote_backend": False,
        },
        "actions": sorted(
            {
                "runtime_status",
                "diagnostic_runtime",
                "teams",
                "list_saves",
                "create_save",
                "export_save",
                "restore_save",
                "recover_save",
                "home",
                "dashboard_snapshot",
                "save_status",
                "team_dashboard",
                "team_assets",
                "standings",
                "dashboard-summary-leaders",
                "dashboard_summary_leaders",
                "dashboard_trends",
                "league_leaders",
                "league_traits",
                "league_events",
                "player_finder",
                "team_wants",
                "player_card",
                "prospect_card",
                "coach_card",
                "social_feed",
                "calendar",
                "box_score",
                "morale",
                "free_agents",
                "free_agency_room",
                "submit_free_agent_offer",
                "free_agent_offer_quote",
                "renounce_cap_hold",
                "advance_free_agency",
                "staff_market",
                "staff_room",
                "staff_retention_room",
                "negotiate_staff",
                "hire_staff",
                "fire_staff",
                "resolve_staff_retention",
                "draft_board",
                "draft_room",
                "draft_apply_current",
                "draft_sim_current",
                "draft_sim_to_user",
                "draft_sim_all",
                "fantasy_draft_room",
                "fantasy_draft_pick",
                "fantasy_draft_sim_one",
                "fantasy_draft_sim_to_user",
                "fantasy_draft_sim_all",
                "fantasy_draft_watchlist",
                "playoff_room",
                "playoff_leaders",
                "playoff_injuries",
                "simulate_playoff_all",
                "simulate_playoff_game",
                "simulate_playoff_round",
                "evaluate_trade",
                "find_trade",
                "find_trade_for_assets",
                "apply_trade_candidate",
                "user_trade_offers",
                "respond_user_trade_offer",
                "roster_cutdown",
                "waive_player",
                "buyout_player",
                "claim_waiver",
                "waiver_room",
                "set_rotation_minutes",
                "set_player_rest",
                "set_team_block",
                "set_team_wants",
                "acknowledge_team_wants",
                "set_starting_five",
                "apply_contract",
                "extension_room",
                "submit_extension_offer",
                "narrative_settings",
                "advance_save",
                "apply_trade",
                "process_ai_actions",
                "update_game_settings",
            }
        ),
    }


def teams_payload(canonical: dict[str, Any]) -> dict[str, Any]:
    teams = []
    for team in sorted(canonical.get("teams", []), key=lambda item: str(item.get("abbrev") or "")):
        teams.append(
            {
                "id": team.get("id"),
                "abbrev": team.get("abbrev"),
                "name": team.get("name") or team.get("full_name") or team.get("abbrev"),
                "city": team.get("city"),
            }
        )
    return {"teams": teams}


def load_app_canonical(root: Path) -> dict[str, Any]:
    json_path = root / "data" / "canonical" / JSON_FILENAME
    if json_path.exists():
        canonical = load_universe_json(json_path)
    else:
        canonical = to_plain(build_universe(root))
    enrich_player_external_metadata(canonical.get("players") or [], load_player_external_metadata(root))
    canonical["_allow_internal_caches"] = True
    canonical["_baseline_directory"] = str(root / "data/canonical/baselines")
    return canonical


def list_saves(save_dir: Path) -> dict[str, Any]:
    saves = []
    paths = set(save_dir.glob("*.json"))
    # A lost manifest must remain discoverable through its previous snapshot.
    paths.update(path.with_name(path.name.removesuffix(".previous.nbagm.zip")) for path in save_dir.glob("*.json.previous.nbagm.zip"))
    for path in sorted(paths):
        try:
            path = resolve_app_save_path(save_dir, {"save_path": str(path.absolute())})
        except AppActionError:
            # Never inspect a manifest or recovery archive outside this directory.
            continue
        recovery_available = previous_backup_path(path).is_file()
        try:
            save = load_save(path)
            save = ensure_league_save_defaults(save)
        except Exception as exc:
            saves.append({"path": str(path), "name": path.stem, "status": "unreadable", "error": str(exc), "recovery_available": recovery_available})
            continue
        saves.append(
            {
                "path": str(path),
                "name": path.stem,
                "status": "ok",
                "recovery_available": recovery_available,
                "save_id": save.get("meta", {}).get("id"),
                "team": save.get("meta", {}).get("user_team_abbrev"),
                "season": save.get("meta", {}).get("season"),
                "current_date": save.get("state", {}).get("current_date"),
                "phase": save.get("state", {}).get("phase"),
                "ai_difficulty": save.get("meta", {}).get("ai_difficulty"),
            }
        )
    return {"save_count": len(saves), "saves": saves}


def create_save_action(root: Path, canonical: dict[str, Any], save_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    team_query = str(payload.get("team") or "GSW")
    seed = payload.get("seed")
    if team_query.lower() == "random":
        team_query = random_team_abbrev(canonical, None if seed is None else int(seed))
    seed_int = int(seed if seed is not None else random.SystemRandom().randint(1, 2_147_483_647))
    team = resolve_team(canonical, team_query)
    save_name = payload.get("save_name") or f"{team['abbrev'].lower()}_{seed_int}"
    save_path = resolve_app_save_path(save_dir, {"save_name": safe_filename(str(save_name))})
    with save_lock(save_path):
        ensure_new_save_path(save_path)
        return _create_save_action_at_path(root, canonical, save_path, payload, team, seed_int)


def _create_save_action_at_path(root: Path, canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], team: dict[str, Any], seed_int: int) -> dict[str, Any]:
    save = create_league_save(
        root,
        canonical,
        team["abbrev"],
        save_path,
        seed=seed_int,
        ai_difficulty=str(payload.get("ai_difficulty") or "normal"),
        game_mode=str(payload.get("game_mode") or "standard"),
        ratings_model=str(payload.get("ratings_model") or "inputs_v1"),
    )
    ensure_game_settings(save)
    if (save.get("fantasy_draft_state") or {}).get("status") == "in_progress":
        save["state"]["phase"] = "fantasy_draft"
        save["state"]["legal_actions"] = ["fantasy_draft_pick"]
    else:
        save["state"]["legal_actions"] = save_legal_actions_for_date(save, save["state"]["current_date"])
    write_save(save_path, save)
    return {
        "status": "created",
        "save_path": str(save_path),
        "save": save_status(root, canonical, save_path),
        "game_settings": save.get("game_settings", {}),
    }


def dispatch_save_action(action: str, payload: dict[str, Any], root: Path, canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    if action in MUTATING_ACTIONS:
        gate_save = ensure_league_save_defaults(load_save(save_path), canonical)
        if (gate_save.get("fantasy_draft_state") or {}).get("status") == "in_progress":
            allowed = {
                "fantasy_draft_pick",
                "fantasy_draft_sim_one",
                "fantasy_draft_sim_to_user",
                "fantasy_draft_sim_all",
                "fantasy_draft_watchlist",
                "update_game_settings",
            }
            if action not in allowed:
                raise AppActionError("Complete the fantasy draft before using the rest of the front office.")
    if action == "save_status":
        return {"save": save_status(root, canonical, save_path), "game_settings": current_game_settings(canonical, save_path)}
    if action == "home":
        return home_payload(root, canonical, save_path)
    if action == "dashboard_snapshot":
        return dashboard_snapshot_payload(root, canonical, save_path, payload)
    if action == "team_dashboard":
        team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
        return team_dashboard(root, canonical, save_path, team)
    if action == "fantasy_draft_room":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
        write_save(save_path, save)
        return fantasy_draft_room(canonical, save, team)
    if action == "fantasy_draft_pick":
        return fantasy_draft_pick_action(canonical, save_path, payload)
    if action == "fantasy_draft_sim_one":
        return fantasy_draft_sim_one_action(canonical, save_path, payload)
    if action == "fantasy_draft_sim_to_user":
        return fantasy_draft_sim_to_user_action(canonical, save_path, payload)
    if action == "fantasy_draft_sim_all":
        return fantasy_draft_sim_all_action(canonical, save_path, payload)
    if action == "fantasy_draft_watchlist":
        return fantasy_draft_watchlist_action(canonical, save_path, payload)
    if action == "team_assets":
        return team_assets_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    if action == "set_team_block":
        return set_team_block_action(canonical, save_path, payload)
    if action in {"team_wants", "set_team_wants", "acknowledge_team_wants"}:
        return team_wants_action(canonical, save_path, payload, action)
    if action == "standings":
        return league_standings(canonical, save_path)
    if action in {"dashboard_summary_leaders", "dashboard-summary-leaders"}:
        return dashboard_summary_leaders_payload(canonical, save_path, limit=int(payload.get("limit") or 10))
    if action == "dashboard_trends":
        return dashboard_trends_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    if action == "league_leaders":
        return league_leaders(canonical, save_path, stat=str(payload.get("stat") or "points"), limit=int(payload.get("limit") or 20))
    if action == "league_traits":
        return league_traits_payload(canonical, save_path, trait=str(payload.get("trait") or "overall"), limit=int(payload.get("limit") or 80))
    if action == "player_finder":
        return player_finder_payload(canonical, save_path)
    if action == "player_card":
        return player_card_payload(canonical, save_path, str(payload.get("player_id") or payload.get("id") or ""))
    if action == "prospect_card":
        return prospect_card_payload(canonical, save_path, str(payload.get("prospect_id") or ""), str(payload.get("year") or ""))
    if action == "coach_card":
        context = dashboard_read_context(canonical, save_path)
        from .coach_cards import coach_card_details
        staff = context['save'].get('staff_slots', [])
        coach = next((row for row in staff if str(row.get('id')) == str(payload.get('staff_id') or '')), None)
        if coach is None:
            raise AppActionError('That coach is no longer available.')
        return coach_card_details(coach, staff)
    if action == "league_events":
        return league_events_view(
            canonical,
            save_path,
            limit=int(payload.get("limit") or 25),
            kind=payload.get("kind"),
            major_only=bool(payload.get("major_only", False)),
            recent_days=payload.get("recent_days"),
        )
    if action == "social_feed":
        team = payload.get("team") or user_team_abbrev(canonical, save_path)
        return social_feed_view(canonical, save_path, str(team), limit=int(payload.get("limit") or 12))
    if action == "calendar":
        return calendar_view(root, canonical, save_path, from_date=payload.get("from_date"), through_date=payload.get("through_date"))
    if action == "box_score":
        return box_score_view(canonical, save_path, str(payload["game_id"]))
    if action == "morale":
        return morale_report(canonical, save_path, payload.get("team"))
    if action == "free_agents":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = with_transaction_context(canonical_with_save(canonical, save))
        report = free_agents_report(active, team_query=payload.get("team"), position=payload.get("position"))
        for candidate in report.get("candidates", []):
            player_id = str(candidate.get("player_id") or "")
            if player_id:
                candidate["ratings"] = player_display_attribute_summary(active, player_id)
        if payload.get("include_current"):
            retired_ids = {str(player_id) for player_id in save.get("retired_player_ids", [])}
            free_agent_ids = {str(player_id) for player_id in save.get("free_agent_player_ids", [])}
            players_by_id = {
                str(player.get("id") or ""): player
                for player in active.get("players", [])
                if player.get("id")
            }
            unsigned_ids = free_agent_ids | {
                player_id
                for player_id, player in players_by_id.items()
                if not player.get("team_id")
            }
            report_by_id = {
                str(candidate.get("player_id") or candidate.get("id") or ""): candidate
                for candidate in report.get("candidates", [])
            }
            report["candidates"] = [
                candidate
                for candidate in report.get("candidates", [])
                if str(candidate.get("player_id") or candidate.get("id") or "") not in unsigned_ids
                and players_by_id.get(str(candidate.get("player_id") or candidate.get("id") or ""), {}).get("team_id")
            ]
            report["candidate_count"] = len(report["candidates"])
            current_candidates: list[dict[str, Any]] = []
            for player in active.get("players", []):
                player_id = str(player.get("id") or "")
                if not player_id or player_id in retired_ids:
                    continue
                if player_id not in unsigned_ids:
                    continue
                entry = dict(report_by_id.get(player_id) or {})
                entry.update({
                    "id": player_id,
                    "player_id": player_id,
                    "name": player.get("name") or entry.get("name") or "Unknown",
                    "team_id": None,
                    "team_abbrev": None,
                    "position": player.get("position"),
                    "age": player.get("age"),
                    "minutes_projection": display_minutes_projection(player),
                    "ratings": player_display_attribute_summary(active, player_id),
                    "current_free_agent": True,
                })
                if not entry.get("projected_aav_millions"):
                    entry["projected_aav_millions"] = round(
                        max(1.8, display_minutes_projection(player) * 0.45),
                        2,
                    )
                current_candidates.append(entry)
            current_candidates.sort(
                key=lambda candidate: (
                    float((candidate.get("ratings") or {}).get("overall") or 0.0),
                    float(candidate.get("projected_aav_millions") or 0.0),
                    str(candidate.get("name") or ""),
                ),
                reverse=True,
            )
            report["current_candidates"] = current_candidates
            report["current_candidate_count"] = len(current_candidates)
        limit = payload.get("limit")
        if limit:
            report["candidates"] = report.get("candidates", [])[: int(limit)]
            if "current_candidates" in report:
                report["current_candidates"] = report["current_candidates"][: int(limit)]
        return report
    if action == "free_agency_room":
        team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
        seed = int(payload.get("seed") or 1)
        context = dashboard_read_context(canonical, save_path)
        save = context["save"]
        phase = str((save.get("state") or {}).get("phase") or "")
        market_state = save.get("free_agency_state") or {}
        from .play import free_agency_ai_day_processed

        if phase in {"re_signing", "free_agency"} and (
            market_state.get("season") != save.get("meta", {}).get("season")
            or (
                phase == "free_agency"
                and market_state.get("status") != "completed"
                and not free_agency_ai_day_processed(market_state)
            )
        ):
            from .play import initialize_free_agency_market

            initialize_free_agency_market(canonical, save_path, team, seed)
            invalidate_read_cache(save_path)
            context = dashboard_read_context(canonical, save_path)
        phase_key = ("free_agency_room", team, seed)
        cached = context.setdefault("phase_payloads", {}).get(phase_key)
        if cached is None:
            cached = free_agency_room_payload(
                canonical,
                save_path,
                team,
                seed,
                prepared_save=context["save"],
                prepared_active=context["active"],
            )
            context["phase_payloads"][phase_key] = cached
        return cached
    if action == "extension_room":
        return extension_room_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)), payload.get("player_id"))
    if action == "submit_extension_offer":
        return submit_extension_offer_action(root, canonical, save_path, payload)
    if action == "submit_free_agent_offer":
        return submit_free_agent_offer_action(canonical, save_path, payload)
    if action == "free_agent_offer_quote":
        return free_agent_offer_quote_action(canonical, save_path, payload)
    if action == "renounce_cap_hold":
        return renounce_cap_hold_action(canonical, save_path, payload)
    if action == "advance_re_signing":
        return advance_re_signing_action(canonical, save_path, payload, root)
    if action == "advance_free_agency":
        return advance_free_agency_action(canonical, save_path, payload, root)
    if action == "staff_market":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        return staff_market_report(canonical, save, slot=payload.get("slot"), limit=payload.get("limit"))
    if action == "staff_room":
        return staff_room_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)), slot=payload.get("slot"), limit=payload.get("limit"))
    if action == "staff_retention_room":
        return staff_retention_room_payload(canonical, save_path, payload.get("window_id"))
    if action == "negotiate_staff":
        return negotiate_staff_action(canonical, save_path, payload)
    if action == "hire_staff":
        return hire_staff_action(canonical, save_path, str(payload["negotiation_id"]))
    if action == "fire_staff":
        return fire_staff_action(canonical, save_path, payload)
    if action == "resolve_staff_retention":
        return resolve_staff_retention_action(canonical, save_path, payload)
    if action == "draft_board":
        context = dashboard_read_context(canonical, save_path)
        active, save = context["active"], context["save"]
        team = resolve_team(active, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
        board = draft_board_report(active, team["id"], str(payload.get("year") or current_draft_year(save)), limit=payload.get("limit"))
        return enrich_draft_board_scouting(active, save, team["id"], board)
    if action == "draft_room":
        context = dashboard_read_context(canonical, save_path)
        team = str(payload.get("team") or context["save"].get("meta", {}).get("user_team_abbrev") or "GSW")
        year = str(payload.get("year") or current_draft_year(context["save"]))
        seed = int(payload.get("seed") or 1)
        existing_state = context["save"].get("draft_state") or {}
        phase = str((context["save"].get("state") or {}).get("phase") or "")
        if phase == "draft" and not (
            existing_state.get("year") == year
            and existing_state.get("status") in {"in_progress", "completed"}
            and existing_state.get("draft")
        ):
            from .play import ensure_live_draft_state

            ensure_live_draft_state(canonical, save_path, year, seed)
            invalidate_read_cache(save_path)
            context = dashboard_read_context(canonical, save_path)
        phase_key = ("draft_room", team, year, seed)
        cached = context.setdefault("phase_payloads", {}).get(phase_key)
        if cached is None:
            cached = draft_room_payload(
                canonical,
                save_path,
                team,
                year,
                seed,
                prepared_save=context["save"],
                prepared_active=context["active"],
            )
            context["phase_payloads"][phase_key] = cached
        return cached
    if action == "draft_reveal_lottery":
        return draft_reveal_lottery_action(canonical, save_path, payload)
    if action == "draft_apply_current":
        return draft_apply_current_action(canonical, save_path, payload)
    if action == "draft_sim_current":
        return draft_sim_current_action(canonical, save_path, payload)
    if action == "draft_sim_to_user":
        return draft_sim_action(canonical, save_path, payload, mode="to_user")
    if action == "draft_sim_all":
        return draft_sim_action(canonical, save_path, payload, mode="all")
    if action == "playoff_room":
        return playoff_room_payload(canonical, save_path)
    if action == "playoff_injuries":
        return playoff_injuries_payload(canonical, save_path)
    if action == "playoff_leaders":
        return playoff_leaders(canonical, save_path, stat=str(payload.get("stat") or "points"), limit=int(payload.get("limit") or 10))
    if action == "simulate_playoff_all":
        return simulate_playoff_action(canonical, save_path, root, int(payload.get("seed") or 1), mode="all")
    if action == "simulate_playoff_game":
        return simulate_playoff_action(canonical, save_path, root, int(payload.get("seed") or 1), mode="game")
    if action == "simulate_playoff_round":
        return simulate_playoff_action(canonical, save_path, root, int(payload.get("seed") or 1), mode="round")
    if action == "find_trade":
        active = active_canonical(canonical, save_path)
        report = find_trade(
            active,
            str(payload["player"]),
            str(payload.get("for_team") or user_team_abbrev(canonical, save_path)),
            limit=int(payload.get("limit") or 10),
            seed=int(payload.get("seed") or 1),
        )
        return enhance_trade_finder_report(active, report, save_path)
    if action == "find_trade_for_assets":
        active = active_canonical(canonical, save_path)
        from .trade_pick_terms import compile_pick_rules, attach_compiled_rules
        seller = str(payload.get("seller_team") or user_team_abbrev(canonical, save_path))
        user = str(payload.get("for_team") or user_team_abbrev(canonical, save_path))
        recipient = user if resolve_team(active,seller)['id'] != resolve_team(active,user)['id'] else payload.get('buyer_team')
        rules = payload.get('pick_rules') or []
        active, assets, terms = compile_pick_rules(active,rules,[{'team':seller,'recipient':recipient,'assets':payload.get('assets') or []}])
        report = find_trade_for_assets(
            active,
            seller, assets[0], user,
            limit=int(payload.get("limit") or 10),
            seed=int(payload.get("seed") or 1),
            buyer_team=str(payload["buyer_team"]) if payload.get("buyer_team") else None,
        )
        if terms:
            report['candidates'] = [attach_compiled_rules(c,terms,rules,int(payload.get('seed') or 1)) for c in report.get('candidates',[])]
        return enhance_trade_finder_report(active, report, save_path)
    if action == "evaluate_trade":
        active = active_canonical(canonical, save_path)
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        if payload.get('transfers'):
            from .multi_team_trades import evaluate_multi_team_trade
            candidate = evaluate_multi_team_trade(active, payload['transfers'], pick_rules=payload.get('pick_rules'),
                seed=int(payload.get('seed') or 1), date=save['state']['current_date'])
            return enhance_trade_candidate(active, candidate, save=save)
        from .trade_pick_terms import compile_pick_rules, attach_compiled_rules
        rules = payload.get('pick_rules') or []
        active, assets, terms = compile_pick_rules(active,rules,[
            {'team':payload['from_team'],'recipient':payload['to_team'],'assets':payload.get('from_assets') or []},
            {'team':payload['to_team'],'recipient':payload['from_team'],'assets':payload.get('to_assets') or []}])
        candidate = evaluate_trade(
            active,
            str(payload["from_team"]),
            str(payload["to_team"]),
            assets[0], assets[1],
            seed=int(payload.get("seed") or 1),
            date=payload.get("date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE,
            context_ready=True,
        )
        if terms:
            candidate = attach_compiled_rules(candidate,terms,rules,int(payload.get('seed') or 1))
        result = enhance_trade_candidate(active, candidate, save=save)
        user_team_id = save.get("meta", {}).get("user_team_id")
        if not terms and user_team_id:
            # Trade step 3: a partner that is a little short answers with a counter-offer, the exact deal it would make.
            # The trade window sends the negotiation so far (counter_chain), so the partner never repeats a package
            # and each new counter asks for less than its last one.
            from .trade_counters import user_counter, package_key, COUNTER_ROUNDS
            chain = payload.get("counter_chain") if isinstance(payload.get("counter_chain"), list) else []
            counter = user_counter(active, candidate, user_team_id, seed=int(payload.get("seed") or 1),
                                   date=payload.get("date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE,
                                   chain=chain)
            proposal = candidate.get("proposal") or {}
            result["offer_package"] = package_key(proposal.get("from_assets") or [], proposal.get("to_assets") or [])
            if counter is not None:
                result["counter_offer"] = enhance_trade_candidate(active, counter, save=save)
            elif sum(1 for c in chain if isinstance(c, dict) and c.get("asking_net") is not None) >= COUNTER_ROUNDS:
                result["counter_closed"] = True  # the partner has made its last counter in this negotiation
        return result
    if action == "apply_trade_candidate":
        return apply_trade_candidate_action(canonical, save_path, payload)
    if action == "user_trade_offers":
        return user_trade_offers_payload(canonical, save_path)
    if action == "respond_user_trade_offer":
        return respond_user_trade_offer_action(canonical, save_path, payload)
    if action == "set_starting_five":
        return set_starting_five_action(root, canonical, save_path, payload)
    if action == "set_rotation_minutes":
        return set_rotation_minutes_action(root, canonical, save_path, payload)
    if action == "set_player_rest":
        return set_player_rest_action(root, canonical, save_path, payload)
    if action == "roster_cutdown":
        return roster_cutdown_payload(canonical, save_path)
    if action == "waive_player":
        return waive_player_action(root, canonical, save_path, payload)
    if action == "buyout_player":
        return waive_player_action(root, canonical, save_path, payload, buyout=True)
    if action == "waiver_room":
        return waiver_room_payload(canonical, save_path)
    if action == "claim_waiver":
        from .waivers import submit_claim
        saved = ensure_league_save_defaults(load_save(save_path), canonical)
        try:
            claim = submit_claim(canonical_with_save(canonical, saved), saved, str(payload.get('waiver_id') or ''),
                                 saved['meta']['user_team_id'], cut_id=payload.get('cut_player_id'))
        except ValueError as exc:
            raise AppActionError(str(exc)) from exc
        write_save(save_path, saved)
        return {'status': 'claim_submitted', 'claim': claim, 'room': waiver_room_payload(canonical, save_path)}
    if action == "narrative_settings":
        return narrative_settings_view(save_path, test_connection=bool(payload.get("test_connection", False)))
    if action == "season_slideshow":
        return season_slideshow_action(canonical, save_path, payload)
    if action == "season_slideshow_seen":
        return season_slideshow_seen_action(canonical, save_path, payload)
    if action == "advance_save":
        return advance_action(root, canonical, save_path, payload)
    if action == "process_ai_actions":
        return process_ai_actions(canonical, save_path, seed=int(payload.get("seed") or 1), execute=bool(payload.get("execute", True)), limit=int(payload.get("limit") or 30))
    if action == "apply_trade":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        date_value = payload.get("date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        return apply_trade_to_save(save_path, str(payload["proposal_id"]), date=str(date_value), canonical=canonical)
    if action == "apply_contract":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        date_value = payload.get("date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        return apply_contract_to_save(save_path, str(payload["negotiation_id"]), date=str(date_value))
    if action == "update_game_settings":
        return update_game_settings_action(canonical, save_path, payload.get("settings") or {})
    raise AppActionError(f"Unknown app action {action!r}")


def fantasy_draft_pick_action(
    canonical: dict[str, Any],
    save_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_fantasy_team(canonical, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    result = apply_fantasy_draft_pick(
        canonical,
        save,
        team["id"],
        str(payload.get("player_id") or "") or None,
        auto=bool(payload.get("auto")),
    )
    human_team_ids = {
        str(team_id)
        for team_id in payload.get("human_team_ids") or []
        if team_id
    }
    ai_picks = (
        simulate_fantasy_draft_until_human(canonical, save, human_team_ids)
        if human_team_ids
        else []
    )
    write_save(save_path, save)
    return {
        **result,
        "ai_picks": ai_picks,
        "room": fantasy_draft_room(canonical, save, team["abbrev"]),
    }


def fantasy_draft_sim_one_action(
    canonical: dict[str, Any],
    save_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_fantasy_team(canonical, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    result = simulate_fantasy_draft_one(canonical, save, {team["id"]})
    write_save(save_path, save)
    return {
        **result,
        "applied_count": 1 if result.get("selection") else 0,
        "picks": [result["selection"]] if result.get("selection") else [],
        "room": fantasy_draft_room(canonical, save, team["abbrev"]),
    }


def fantasy_draft_sim_to_user_action(
    canonical: dict[str, Any],
    save_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_fantasy_team(canonical, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    applied = simulate_fantasy_draft_until_human(canonical, save, {team["id"]})
    write_save(save_path, save)
    return {
        "status": (save.get("fantasy_draft_state") or {}).get("status"),
        "applied_count": len(applied),
        "picks": applied,
        "room": fantasy_draft_room(canonical, save, team["abbrev"]),
    }


def fantasy_draft_watchlist_action(
    canonical: dict[str, Any],
    save_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_fantasy_team(canonical, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    result = toggle_fantasy_draft_watchlist(
        save,
        team["id"],
        str(payload.get("player_id") or ""),
    )
    write_save(save_path, save)
    return {
        **result,
        "room": fantasy_draft_room(canonical, save, team["abbrev"]),
    }


def fantasy_draft_sim_all_action(
    canonical: dict[str, Any],
    save_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_fantasy_team(canonical, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    applied = simulate_fantasy_draft_all(canonical, save)
    write_save(save_path, save)
    return {
        "status": (save.get("fantasy_draft_state") or {}).get("status"),
        "applied_count": len(applied),
        "picks": applied,
        "room": fantasy_draft_room(canonical, save, team["abbrev"]),
    }


def league_activity_copy(event: dict[str, Any]) -> tuple[str, list[str]]:
    """Reusable newsroom copy; all facts come from the recorded deal or current profiles."""
    groups = event.get("activity_groups") or []
    people = [p for g in groups for p in g.get("subjects", [])]
    details = event.get("details") or {}
    kind = event.get("kind")
    variant = sum(ord(c) for c in str(event.get("id") or "")) % 2
    comments = []

    def package(subjects):
        if len(subjects) <= 2:
            return " and ".join(p["name"] for p in subjects)
        players = sum(p.get("kind") == "player" for p in subjects)
        picks = len(subjects) - players
        return " and ".join([*([f"{players} players"] if players else []), *([f"{picks} draft pick{'s' if picks != 1 else ''}"] if picks else [])])

    headline = event.get("headline") or "Around the league"
    if len(groups) == 2 and all(g.get("subjects") for g in groups):
        first, second = groups
        incoming, outgoing = package(first["subjects"]), package(second["subjects"])
        headline = (f"Deal done: The {first['team_name']} land {incoming}, sending {outgoing} to the {second['team_name']}." if variant else f"A new chapter: The {first['team_name']} bring in {incoming}, with {outgoing} heading to the {second['team_name']} in return.")
        for group in groups:
            comments.append(f"The full return for the {group['team_name']}: " + ", ".join(p["name"] for p in group["subjects"]) + ".")
    elif len(people) == 1:
        person = people[0]
        team = groups[0].get("team_name") or person.get("team")
        if kind in {"extension", "signing", "free_agent_signing"} and details.get("annual_salary") and details.get("years"):
            years = int(details["years"])
            total = float(details["annual_salary"]) * years / 1_000_000
            deal = "extension" if kind == "extension" else "deal"
            headline = f"{person['name']} {'is staying with' if kind == 'extension' else 'is joining'} the {team} on a {years}-year, ${total:.1f} million {deal}."
            comments.append(f"The agreement pays {person['name']} ${float(details['annual_salary']) / 1_000_000:.1f} million per year across {years} season{'s' if years != 1 else ''}.")
        elif person.get("kind") == "staff":
            role = person.get("role", "staff member").lower()
            headline = f"A change on the sidelines: The {team} part ways with {role} {person['name']}." if kind == "staff_fire" else f"A fresh voice for the {team}: {person['name']} takes over as {role}."
            comments.append(f"{person['name']} carries a {person['grade']:.1f} staff grade as a {role}.")
            replacement = person.get("replacement")
            if replacement:
                comments.append(f"{replacement['label']}: {replacement['name']}, whose staff grade is {replacement['grade']:.1f}.")
    for person in people:
        if person.get("kind") != "player":
            continue
        age = f"At age {float(person['age']):g}, " if person.get("age") is not None else ""
        rating = f"{person['overall']:.1f} overall" if person.get("overall") is not None else "an unrated overall"
        upside = person.get("upside_remaining")
        growth = f", with {upside:.1f} OVR of upside still available" if upside is not None and upside > 0 else ", with no remaining OVR upside projected" if upside == 0 else ""
        comments.append(f"{age}{person['name']} checks in at {rating}{growth}.")
        if person.get("season_games"):
            comments.append(f"{person['name']} is averaging {person['season_points']:.1f} points through {person['season_games']} appearances this season.")
        if person.get("salary_millions") is not None:
            comments.append(f"The current contract for {person['name']} pays ${person['salary_millions']:.1f} million this season, with {person['contract_years_remaining']} season{'s' if person['contract_years_remaining'] != 1 else ''} remaining.")
    return headline, comments


def assistant_gm_messages(active: dict[str, Any], save: dict[str, Any], feed: dict[str, Any]) -> list[dict[str, Any]]:
    """Actionable reminders and recent major events, using existing game rules."""
    today = safe_date((save.get("state") or {}).get("current_date"))
    if not today:
        return []
    user_abbrev = str((save.get("meta") or {}).get("user_team_abbrev") or "")
    team = next((t for t in active.get("teams", []) if t.get("abbrev") == user_abbrev), {})
    contracts = {c.get("player_id"): c for c in active.get("contracts", [])}
    messages = []
    deadline = trade_deadline_date(season_start_year_from_date(today.isoformat()))
    if today.isoformat() == deadline:
        messages.append({"id": f"trade-deadline:{deadline}", "date": deadline, "kind": "trade_deadline", "title": "Trade deadline today", "text": "Trade deadline today. Last chance to make a deal.", "target": "trade-deadline"})
    if "extensions" in set(save_legal_actions_for_date(save, today.isoformat())):
        for player in active.get("players", []):
            if player.get("team_id") != team.get("id") or not extension_contract_window(contracts.get(player.get("id")))["eligible"]:
                continue
            totals = (save.get("player_season_stats") or {}).get(player["id"], {})
            games = int(totals.get("games") or 0)
            minutes = float(totals.get("minutes") or 0) / games if games else display_minutes_projection(player)
            if minutes <= 25:
                continue
            messages.append({"id": f"extension:{save.get('meta', {}).get('season')}:{player['id']}", "date": today.isoformat(), "kind": "extension_eligible", "title": "Time to talk extension", "text": f"{player['name']} is extension eligible.", "target": "contracts", "player_id": player["id"]})
    for event in feed.get("events", []):
        event_day = safe_date(event.get("date"))
        if not event_day or not today - timedelta(days=7) <= event_day <= today:
            continue
        subjects = [p for g in event.get("activity_groups", []) for p in g.get("subjects", [])]
        kind = event.get("kind")
        fired = next((p for p in subjects if p.get("kind") == "staff" and float(p.get("grade") or 0) >= 75), None)
        if kind == "staff_fire" and fired:
            text = f"{fired['name']} ({fired['grade']:.0f}) was fired by {fired['team']}."
            title = "A coach to watch"
        elif kind == "trade" and float(event.get("importance") or 0) >= 0.7:
            trade_teams = list(dict.fromkeys(str(group.get("team")) for group in event.get("activity_groups", []) if group.get("team")))
            text = f"{'–'.join(trade_teams[:2])} just made a trade." if trade_teams else "A major trade just landed."
            title = "A deal just went down"
        elif kind in {"extension", "signing", "free_agent_signing"} and any(float(p.get("overall") or 0) >= 85 for p in subjects):
            star = next(p for p in subjects if float(p.get("overall") or 0) >= 85)
            text = f"{star['name']} signed an extension." if kind == "extension" else f"{star['name']} signed with {star.get('team') or 'a new team'}."
            title = "Big news around the league"
        else:
            continue
        messages.append({"id": f"league:{event['id']}", "date": event_day.isoformat(), "kind": kind, "title": title, "text": text, "target": "league-wire", "event_id": event["id"]})
    return messages[:12]


def league_activity_payload(canonical: dict[str, Any], save_path: Path, prepared_save: dict[str, Any] | None = None, *, prepared_active: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach current display profiles to the recorded transaction headlines."""
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    feed = league_events_view(canonical, save_path, limit=60, kind="transactions", prepared_save=save)
    active = prepared_active if prepared_active is not None else with_transaction_context(canonical_with_save(canonical, save))
    players = {str(p["id"]): p for p in active.get("players", [])}
    teams = {str(t["id"]): t for t in active.get("teams", [])}
    valuations = {str(v.get("player_id")): v for v in active.get("player_asset_valuations", [])}
    profiles = {}

    def team_label(tid):
        return teams.get(str(tid), {}).get("abbrev") or str(tid or "").removeprefix("team_").upper()

    def subject(asset, team_id):
        pid = str(asset.get("id") or asset.get("player_id") or "")
        player = players.get(pid)
        if player:
            if pid not in profiles:
                attrs = player_display_attribute_summary(active, pid)
                totals = (save.get("player_season_stats") or {}).get(pid, {})
                games = int(totals.get("games") or 0)
                salary_table = player_salary_table(active, pid)
                current_season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
                remaining = [season for season, salary in salary_table.items() if season >= current_season and salary is not None]
                profiles[pid] = {
                    "salary_millions": salary_table.get(current_season), "contract_years_remaining": len(remaining),
                    "kind": "player", "id": pid, "name": player.get("name"), "headshot_url": player.get("headshot_url"),
                    "age": player.get("display_age", player.get("age")), "position": player.get("position"),
                    "overall": attrs.get("overall"),
                    "upside_remaining": round(max(0.0, min(5.0, float(valuations.get(pid, {}).get("development_upside") or 0) / 22 * 5)), 1),
                    "season_points": round(float(totals.get("points") or 0) / games, 1) if games else None,
                    "season_games": games,
                }
            return {**profiles[pid], "team": team_label(team_id or player.get("team_id"))}
        return {"kind": "pick", "name": asset.get("label") or "Draft pick", "team": team_label(asset.get("original_team_id") or team_id), "season": asset.get("season"), "round": asset.get("round")}

    for event in feed.get("events", []):
        details = event.get("details") or {}
        groups = []
        if details.get('transfers'):
            from .transactions import trade_team_flows
            for tid, _, incoming in trade_team_flows(details):
                groups.append({'team': team_label(tid), 'team_name': teams.get(str(tid), {}).get('name') or team_label(tid),
                               'label': 'Receives', 'subjects': [subject(a, tid) for a in incoming]})
        elif details.get("from_assets") or details.get("to_assets"):
            for assets_key, receiving_key in [("from_assets", "to_team_id"), ("to_assets", "from_team_id")]:
                tid = details.get(receiving_key)
                groups.append({"team": team_label(tid), "team_name": teams.get(str(tid), {}).get("name") or team_label(tid), "label": "Receives", "subjects": [subject(a, tid) for a in details.get(assets_key, [])]})
        else:
            tids = event.get("team_ids") or []
            tid = details.get("team_id") or (tids[0] if tids else None)
            pids = list(dict.fromkeys([*(event.get("player_ids") or []), *([details["player_id"]] if details.get("player_id") else [])]))
            subjects = [subject({"id": pid}, tid) for pid in pids if str(pid) in players]
            if not subjects and str(event.get("kind") or "").startswith("staff"):
                name = details.get("staff_name") or details.get("name")
                for log in reversed(save.get("transaction_logs", [])):
                    if str(log.get("date") or "")[:10] != str(event.get("date") or "")[:10]:
                        continue
                    assets = log.get("assets") or {}
                    staff = assets.get("fired_staff") if log.get("transaction_type") == "staff_fire" else assets.get("staff")
                    if not staff or not (str(staff.get("id")) == str(details.get("staff_id")) or staff.get("name") == name or str(staff.get("name") or "?") in str(event.get("headline") or "")):
                        continue
                    subjects = [{"kind": "staff", "id": staff.get("id"), "name": staff.get("name"), "role": str(staff.get("slot") or staff.get("role_preference") or "Staff").replace("_", " "), "grade": round(staff_grade(staff), 1), "team": team_label(tid or (log.get("teams") or [None])[0])}]
                    replacement = assets.get("interim_staff") or assets.get("previous_staff")
                    if replacement:
                        subjects[0]["replacement"] = {"name": replacement.get("name"), "grade": round(staff_grade(replacement), 1), "label": "Interim replacement" if assets.get("interim_staff") else "Previous staff member"}
                    break
            groups = [{"team": team_label(tid), "team_name": teams.get(str(tid), {}).get("name") or team_label(tid), "subjects": subjects}]
        event["activity_groups"] = groups
        event["activity_headline"], event["activity_comments"] = league_activity_copy(event)
    feed["assistant_messages"] = assistant_gm_messages(active, save, feed)
    return feed


def home_payload(
    root: Path,
    canonical: dict[str, Any],
    save_path: Path,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = save_status(root, canonical, save_path, prepared_save=prepared_save)
    deadline = trade_deadline_date(season_start_year_from_date(status.get("current_date") or CANONICAL_START_DATE))
    return {
        "save": status,
        "trade_deadline": {"date": deadline, "is_today": status.get("current_date") == deadline},
        # The dashboard only needs counts. Full historical AI bundles can grow to
        # megabytes over long saves and are available through their dedicated views.
        "pending": {
            "current_date": status.get("current_date"),
            "phase": status.get("phase"),
            "pending_counts": dict(status.get("pending_counts") or {}),
        },
        "league_events": league_activity_payload(canonical, save_path, prepared_save, prepared_active=prepared_active),
        "game_settings": current_game_settings(canonical, save_path, prepared_save=prepared_save),
    }


def dashboard_snapshot_payload(
    root: Path,
    canonical: dict[str, Any],
    save_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build the regular-season command surface from one immutable read context."""
    context = dashboard_read_context(canonical, save_path)
    save = context["save"]
    active = context["active"]
    cache_key = (
        str(payload.get("team") or save.get("meta", {}).get("user_team_abbrev") or "GSW"),
        str(payload.get("from_date") or ""),
        str(payload.get("through_date") or ""),
        str(payload.get("draft_year") or ""),
        int(payload.get("leader_limit") or 9),
        int(payload.get("prospect_limit") or 8),
    )
    cached = context["snapshots"].get(cache_key)
    if cached is not None:
        return cached
    active = transaction_read_active(context)
    home = context.get("home")
    if home is None:
        home = home_payload(root, canonical, save_path, prepared_save=save, prepared_active=active)
        context["home"] = home
    phase = str((save.get("state") or {}).get("phase") or "")
    pending = home.get("save", {}).get("pending_counts") or {}
    phase_only = (
        phase in {"fantasy_draft", "play_in", "playoffs", "draft_lottery", "draft", "re_signing", "free_agency"}
        or int(pending.get("staff") or 0) > 0
        or int(pending.get("cutdowns") or 0) > 0
    )
    stat = save_path.stat()
    revision = f"{stat.st_mtime_ns:x}-{stat.st_size:x}"
    if phase_only:
        result = {"revision": revision, "home": home, "phase_only": True}
        context["snapshots"][cache_key] = result
        return result
    team_query = str(payload.get("team") or save.get("meta", {}).get("user_team_abbrev") or "GSW")
    dashboard = team_dashboard(
        root,
        canonical,
        save_path,
        team_query,
        prepared_save=save,
        prepared_active=active,
        persist_repairs=False,
    )
    next_game = (dashboard.get("next_games") or [{}])[0]
    opponent_query = next_game.get("opponent_team_id")
    opponent = (
        team_dashboard(
            root,
            canonical,
            save_path,
            str(opponent_query),
            prepared_save=save,
            prepared_active=active,
            persist_repairs=False,
        )
        if opponent_query
        else None
    )
    current_day = safe_date((save.get("state") or {}).get("current_date")) or date.today()
    week_start = current_day - timedelta(days=current_day.weekday())
    calendar_from = str(payload.get("from_date") or week_start.isoformat())
    calendar_through = str(payload.get("through_date") or (week_start + timedelta(days=6)).isoformat())
    offers = user_trade_offers_payload(
        canonical,
        save_path,
        prepared_save=save,
        prepared_active=(
            with_transaction_context(active)
            if save.get("user_trade_offers")
            else active
        ),
    )
    result = {
        "revision": revision,
        "home": home,
        "dashboard": dashboard,
        "standings": league_standings(canonical, save_path, prepared_save=save),
        "summary_leaders": dashboard_summary_leaders_payload(
            canonical,
            save_path,
            limit=int(payload.get("leader_limit") or 9),
            prepared_save=save,
            prepared_active=active,
        ),
        "trends": dashboard_trends_payload(
            canonical,
            save_path,
            team_query,
            prepared_save=save,
            prepared_active=active,
        ),
        "morale": morale_report(
            canonical,
            save_path,
            team_query,
            prepared_save=save,
            prepared_active=active,
        ),
        "calendar": calendar_view(
            root,
            canonical,
            save_path,
            from_date=calendar_from,
            through_date=calendar_through,
            prepared_save=save,
        ),
        "offers": offers,
        "opponent": opponent,
        "prospects": enrich_draft_board_scouting(active, save, dashboard["team"]["id"], draft_board_report(
            active,
            team_query,
            str(payload.get("draft_year") or current_draft_year(save)),
            limit=None,
        )),
    }
    context["snapshots"][cache_key] = result
    return result


def team_wants_action(canonical, save_path, payload, action="team_wants"):
    from .trade_wants import (VERSION, normalize_wants, ownership_keys, wants_payload,
                              clear_wants_cache, asset_matches)
    assets = payload.get('assets', [])
    if not isinstance(assets, list):
        raise AppActionError('Assets must be a list.')
    if action == 'team_wants':
        # The dashboard already owns these projections for this save revision.
        # Edits below keep their fresh, privately owned validation inputs.
        context = dashboard_read_context(canonical, save_path)
        save = context['save']
        active = transaction_read_active(context)
    else:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = with_transaction_context(canonical_with_save(canonical, save))
    team = resolve_team(active, str(payload.get('team') or save.get('meta', {}).get('user_team_abbrev') or 'GSW'))
    tid = team['id']
    record = save.get('team_trade_wants', {}).get(tid, {})
    if action != 'team_wants':
        if tid != save.get('meta', {}).get('user_team_id'):
            raise AppActionError("Only your team's wants can be edited.")
        if payload.get('revision') is not None and payload['revision'] != record.get('revision', 0):
            raise AppActionError('Wants changed. Refresh before editing them again.')
        if action == 'set_team_wants':
            allowed = {p['id'] for p in active.get('players', []) if p.get('team_id') == tid}
            allowed.update(w.get('target_player_id') for w in record.get('entries', []) if w.get('kind') == 'upgrade')
            try:
                entries = normalize_wants(payload.get('entries'), allowed)
            except ValueError as error:
                raise AppActionError(str(error)) from error
            from .trade_wants import player_facts
            from .save import player_position_tokens
            previous = {w['id']: w for w in record.get('entries', [])}
            for want in entries:
                if want['kind'] == 'upgrade':
                    target = next((p for p in active['players'] if p['id'] == want['target_player_id']), None)
                    if target and target.get('team_id') == tid:
                        want['target_snapshot'] = {'facts': player_facts(active, target), 'positions': player_position_tokens(target)}
                    elif previous.get(want['id'], {}).get('target_player_id') == want['target_player_id']:
                        want['target_snapshot'] = previous[want['id']].get('target_snapshot')
            record = {'version': VERSION, 'entries': entries, 'revision': record.get('revision', 0)+1,
                      'reminder_seen': ownership_keys(active, tid)}
        else:
            current = wants_payload(active, save, tid)
            if payload.get('reminder_token') != current['reminder_token']:
                raise AppActionError('New acquisitions arrived. Review the updated reminder.')
            record = {**record, 'reminder_seen': ownership_keys(active, tid)}
        save.setdefault('team_trade_wants', {})[tid] = record
        write_save(save_path, save)
        active['team_trade_wants'] = deepcopy(save['team_trade_wants'])
        clear_wants_cache(active)
    result = wants_payload(active, save, tid)
    result['teams'] = [{'id': t['id'], 'abbrev': t['abbrev']} for t in active.get('teams', [])]
    result['editable'] = tid == save.get('meta', {}).get('user_team_id')
    result['matches'] = {a['id']: deepcopy(asset_matches(active, tid, a)) for a in assets[:30]
                         if isinstance(a, dict) and a.get('kind') in {'player', 'pick', 'pick_swap'} and isinstance(a.get('id'), str)}
    return result


def set_team_block_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    if team["id"] != save.get("meta", {}).get("user_team_id"):
        raise AppActionError("Only your team's trade block can be edited.")
    ids = payload.get("player_ids")
    pick_ids = payload.get("pick_ids", save.get("team_trade_block_picks", {}).get(team["id"], []))
    for values in (ids, pick_ids):
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values) or len(values) > 6 or len(set(values)) != len(values):
            raise AppActionError("Choose up to six different assets for the trade block.")
    if len(ids) + len(pick_ids) > 6:
        raise AppActionError("Choose up to six assets total for the trade block.")
    roster = {p["id"] for p in active.get("players", []) if p.get("team_id") == team["id"]}
    if any(player_id not in roster for player_id in ids):
        raise AppActionError("Every player on your trade block must belong to your team.")
    eligible_picks = {pick["id"] for pick in tradeable_picks_for_team(active, team["id"])} if pick_ids else set()
    if any(pick_id not in eligible_picks for pick_id in pick_ids):
        raise AppActionError("Every pick on your trade block must be owned by your team and available to trade.")
    save.setdefault("team_trade_blocks", {})[team["id"]] = ids
    save.setdefault("team_trade_block_picks", {})[team["id"]] = pick_ids
    write_save(save_path, save)
    return {"status": "updated", "team_block_player_ids": ids, "team_block_pick_ids": pick_ids}


def draft_asset_pick_payload(active: dict[str, Any], pick: dict[str, Any], phase: str, source_pick: dict[str, Any] | None = None) -> dict[str, Any]:
    from .trade_pick_terms import pick_rule_lock_reason
    teams = {row["id"]: row.get("abbrev") for row in active.get("teams", [])}
    condition = pick_display_label(active, pick) if pick.get("_ranked_entitlement") else pick_obligation_context_note(active, pick)
    protection = clean_pick_protection_summary(pick)
    no_conditions = {"unprotected", "unprotected; no additional conditions", "unprotected. no additional conditions"}
    if protection.lower().strip(". ") in no_conditions:
        protection = ""
    if condition.lower().strip(". ") in no_conditions:
        condition = ""
    if pick.get("_obligation_locked") and not condition:
        notes = []
        for obligation in pick.get("_obligations", []):
            if not obligation.get("_fallback_lock"):
                continue
            primary = pick_by_id(active, obligation.get("primary_pick_id")) or {}
            original = teams.get(primary.get("original_team_id")) or "TBD"
            receiver = teams.get(obligation.get("receiver_team_id")) or "TBD"
            primary_label = f"{primary.get('season', '----')} R{primary.get('round', '?')} {original}"
            protection_label = pick_obligation_label(obligation)
            notes.append(f"Fallback for {primary_label} ({protection_label}); {receiver} receives this pick if the primary lands in its protected range")
        if not notes:
            notes.append('Unavailable: conditional draft obligation requires review')
        condition = "; ".join(notes)
    label = pick_display_label(active, pick)
    if condition and condition not in label:
        label += f"; {condition}"
    return {
        "kind": "pick", "id": pick.get("id"), "value": pick.get("id"),
        "pick_presentation": pick_presentation(active, pick),
        "label": label, "season": pick.get("season"), "round": pick.get("round"),
        "original_team_id": pick.get("original_team_id"),
        "original_team_abbrev": teams.get(pick.get("original_team_id")) or team_id_to_abbrev(pick.get("original_team_id")),
        "current_owner_team_id": pick.get("current_owner_team_id"),
        "current_owner_team_abbrev": teams.get(pick.get("current_owner_team_id")) or team_id_to_abbrev(pick.get("current_owner_team_id")),
        "protection_summary": protection,
        "has_protection": bool(protection or any(term.get("type") == "protected_pick" for term in pick.get("_obligations", []))),
        "condition_summary": condition,
        "has_conditions": bool(condition or protection or pick.get("_obligation_locked")),
        "terms_editable": not bool(pick_rule_lock_reason(pick)),
        "terms_lock_reason": pick_rule_lock_reason(pick),
        "trade_value": round(pick_asset_value(pick, phase), 2),
    }


def team_assets_payload(canonical: dict[str, Any], save_path: Path, team_query: str) -> dict[str, Any]:
    context = dashboard_read_context(canonical, save_path)
    save = context["save"]
    active = transaction_read_active(context)
    team = resolve_team(active, team_query)
    cached = context.setdefault("team_assets", {}).get(team["id"])
    if cached is not None:
        return cached
    values = {item.get("player_id"): item for item in active.get("player_asset_valuations", [])}
    team_state = next((state for state in active.get("team_strategic_states", []) if state.get("team_id") == team["id"]), {})
    phase = str(team_state.get("phase") or "balanced")
    current_date = save.get("state", {}).get("current_date")
    team_games = int((save.get("team_records", {}).get(team["id"]) or {}).get("wins", 0)) + int((save.get("team_records", {}).get(team["id"]) or {}).get("losses", 0))
    stats = save.get("player_season_stats", {})
    health = {state.get("player_id"): state for state in save.get("health_states", [])}
    players = []
    for player in active.get("players", []):
        if player.get("team_id") != team["id"]:
            continue
        valuation = values.get(player.get("id"), fallback_asset_valuation(player))
        attrs = player_display_attribute_summary(active, player["id"])
        offense_parts = [
            float(attrs.get(key))
            for key in ("shooting", "creation", "passing")
            if attrs.get(key) is not None
        ]
        totals = stats.get(player["id"], {})
        games = max(1, int(totals.get("games") or 0))
        salary = contract_summary(contract_for_player(active, player["id"]), str(active.get("meta", {}).get("active_season") or ""))
        players.append(
            {
                "kind": "player",
                "id": player["id"],
                "value": player["name"],
                "name": player.get("name"),
                "label": player.get("name"),
                "headshot_url": player.get("headshot_url"),
                "position": compact_position(player.get("position")),
                "age": player.get("display_age", player.get("age")),
                "height": height_label(player),
                "mpg": display_minutes_projection(player),
                "ppg": round(float(totals.get("points") or 0.0) / games, 1) if totals else 0.0,
                "rpg": round(float(totals.get("rebounds") or 0.0) / games, 1) if totals else 0.0,
                "apg": round(float(totals.get("assists") or 0.0) / games, 1) if totals else 0.0,
                "gp": int(totals.get("games") or 0),
                "team_games": team_games,
                "health": health_label(health.get(player["id"]), current_date),
                "contract": salary,
                "contract_terms": block_contract_terms(contract_for_player(active, player["id"]), str(active.get("meta", {}).get("active_season") or "")),
                "salary_by_year": player_salary_table(active, player["id"]),
                "ratings": attrs,
                "trade_value": round(market_trade_target_value(player, valuation), 2),
                "health_risk": round(float(valuation.get("health_risk") or 0), 1),
                "injury_body": injury_body_compact(active, player, health.get(player["id"])),
                "upside_remaining": round(max(0.0, min(5.0, float(valuation.get("development_upside") or 0) / 22.0 * 5.0)), 1),
            }
        )
    players.sort(key=lambda item: (float(item.get("trade_value") or 0), float(item.get("mpg") or 0), item.get("name") or ""), reverse=True)
    used_picks = {pick_id for pick_id, owner in (save.get("draft_pick_overrides") or {}).items() if owner == "used_draft_pick"}
    source_picks = {pick.get("id"): pick for pick in canonical.get("draft_picks", [])}
    picks = []
    for pick in tradeable_picks_for_team(active, team["id"]):
        if pick.get("id") in used_picks:
            continue
        picks.append(draft_asset_pick_payload(active, pick, phase, source_picks.get(pick.get("id"))))
    picks.sort(key=lambda item: (float(item.get("trade_value") or 0), str(item.get("season") or ""), -int(item.get("round") or 9)), reverse=True)
    swaps = []
    for swap in tradeable_pick_swaps_for_team(active, team["id"]):
        pick_a = pick_by_id(active, swap.get("team_a_pick_id"))
        pick_b = pick_by_id(active, swap.get("team_b_pick_id"))
        swaps.append(
            {
                "kind": "pick_swap",
                "pick_presentation": swap_presentation(active, pick_swap_by_id(active, swap.get("id"))),
                "id": swap.get("id"),
                "value": swap.get("id"),
                "label": pick_swap_display_label(active, pick_swap_by_id(active, swap.get("id"))),
                "season": swap.get("season"),
                "round": swap.get("round"),
                "original_team_ids": [
                    item.get("original_team_id")
                    for item in (pick_a, pick_b)
                    if item and item.get("original_team_id")
                ],
                "original_team_abbrevs": [
                    next(
                        (team_row.get("abbrev") for team_row in active.get("teams", []) if team_row.get("id") == item.get("original_team_id")),
                        team_id_to_abbrev(item.get("original_team_id")),
                    )
                    for item in (pick_a, pick_b)
                    if item and item.get("original_team_id")
                ],
                "condition_summary": pick_swap_display_label(active, pick_swap_by_id(active, swap.get("id"))),
                "current_owner_team_id": swap.get("current_rights_holder_team_id"),
                "current_owner_team_abbrev": team.get("abbrev"),
                "has_conditions": True,
                "trade_value": round(pick_swap_asset_value(active, swap, phase), 2),
            }
        )
    swaps.sort(key=lambda item: (float(item.get("trade_value") or 0), str(item.get("season") or "")), reverse=True)
    compact_pick_ids = {pick["id"] for pick in picks}
    extended_picks = [*picks, *swaps]
    for pick in active.get("draft_picks", []):
        if pick.get("id") in compact_pick_ids or pick.get("id") in used_picks or pick.get("status") in {"used_draft_pick", "expired_draft_pick"}:
            continue
        if pick.get("status") == "forfeited":
            if pick.get("original_team_id") == team["id"]:
                extended_picks.append({
                    "kind": "pick", "id": pick["id"], "status": "forfeited", "is_additional": True,
                    "season": pick.get("season"), "round": pick.get("round"),
                    "original_team_id": pick.get("original_team_id"),
                    "original_team_abbrev": team.get("abbrev"),
                    "current_owner_team_id": None, "current_owner_team_abbrev": None,
                    "label": f"{pick.get('season')} R{pick.get('round')} {team.get('abbrev')} — forfeited; no owner",
                    "trade_value": 0, "pick_presentation": None, "has_protection": False,
                })
            continue
        involved_in_condition = any(team["id"] in {obligation.get(field) for field in ("sender_team_id", "receiver_team_id", "current_rights_holder_team_id", "original_rights_holder_team_id")} for obligation in pick.get("_obligations", []))
        if team["id"] not in {pick.get("original_team_id"), pick.get("current_owner_team_id")} and not involved_in_condition:
            continue
        extended_picks.append({**draft_asset_pick_payload(active, pick, phase, source_picks.get(pick.get("id"))), "is_additional": True})
    current_season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    cap_by_year = {
        season_label_for_app(season_start_year_for_app(current_season) + offset): team_cap_summary(
            active,
            save,
            team["id"],
            season=season_label_for_app(season_start_year_for_app(current_season) + offset),
        )
        for offset in range(4)
    }
    teams_by_id = {item.get("id"): item for item in active.get("teams", [])}
    players_by_id = {item.get("id"): item for item in active.get("players", [])}
    league_block = []
    for entry in sorted(
        active.get("trade_block_entries", []),
        key=lambda item: (float(item.get("block_score") or 0), str(item.get("player_id") or "")),
        reverse=True,
    ):
        player = players_by_id.get(entry.get("player_id"))
        block_team = teams_by_id.get(entry.get("team_id"))
        if not player or not block_team or block_team.get("id") == team.get("id"):
            continue
        attrs = player_display_attribute_summary(active, player["id"])
        offense_parts = [
            float(attrs.get(key))
            for key in ("shooting", "creation", "passing")
            if attrs.get(key) is not None
        ]
        league_block.append(
            {
                "player_id": player.get("id"),
                "name": player.get("name"),
                "headshot_url": player.get("headshot_url"),
                "team_id": block_team.get("id"),
                "team_abbrev": block_team.get("abbrev"),
                "age": player.get("display_age", player.get("age")),
                "height": height_label(player),
                "position": compact_position(player.get("position")),
                "overall": attrs.get("overall"),
                "offense": attrs.get('offense', round(sum(offense_parts) / len(offense_parts), 1) if offense_parts else attrs.get("overall")),
                "defense": attrs.get("defense"),
                "contract": contract_summary(contract_for_player(active, player["id"]), str(active.get("meta", {}).get("active_season") or "")),
                "contract_terms": block_contract_terms(contract_for_player(active, player["id"]), str(active.get("meta", {}).get("active_season") or "")),
                "trade_value": round(market_trade_target_value(player, values.get(player.get("id"), fallback_asset_valuation(player))), 2),
                "block_score": entry.get("block_score"),
                "willingness": entry.get("willingness"),
                "health": health_label(health.get(player["id"]), current_date),
            }
        )
        if len(league_block) >= 60:
            break
    from .trade_wants import wants_payload
    result = {
        "team": team,
        "record": (save.get("team_records") or {}).get(team["id"], {}),
        "cap": team_cap_summary(active, save, team["id"]),
        "cap_by_year": cap_by_year,
        "players": players,
        "picks": picks,
        "pick_swaps": swaps,
        "draft_assets": draft_assets_display(active, [*picks, *swaps], team["id"]),
        "extended_draft_assets": draft_assets_display(active, extended_picks, team["id"]),
        "league_block": league_block,
        "team_block_player_ids": [player_id for player_id in save.get("team_trade_blocks", {}).get(team["id"], []) if any(p["id"] == player_id for p in players)],
        "team_block_pick_ids": [pick_id for pick_id in save.get("team_trade_block_picks", {}).get(team["id"], []) if any(p["id"] == pick_id for p in picks)],
        "wants": wants_payload(active, save, team['id']),
        "assets": [*players, *picks, *swaps],
    }
    context["team_assets"][team["id"]] = result
    return result


def prospect_card_payload(canonical: dict[str, Any], save_path: Path, prospect_id: str, year: str = "") -> dict[str, Any]:
    from .play import prospect_scout_display, scouting_report_for
    from .prospect_cards import college_production
    from .spatial import prospect_spatial_profile

    context = dashboard_read_context(canonical, save_path)
    save = context['save']
    active = transaction_read_active(context)
    team = resolve_team(active, user_team_abbrev(canonical, save_path))
    saved_class = (save.get('draft_state') or {}).get('draft') or {}
    prospect = next((row for row in [*saved_class.get('draft_prospects', []), *active.get('draft_prospects', [])]
                     if str(row.get('id')) == prospect_id), None)
    if prospect is None:
        board = draft_board_report(active, team['abbrev'], year or current_draft_year(save), limit=None)
        prospect = next((row.get('prospect', row) for row in board.get('entries', []) if str(row.get('prospect', row).get('id')) == prospect_id), None)
    if prospect is None:
        raise AppActionError(f'No prospect found with id {prospect_id!r}.')
    scout = prospect_scout_display(active, prospect, team['id'], save)
    report = scouting_report_for(active, prospect_id, team['id'], prospect=prospect)
    visible = prospect_card_ratings(prospect, scout, report)
    boards = prospect_two_boards(active, team, prospect, year or current_draft_year(save))
    from .real_prospects import college_card, real_entry_for, scouting_card
    real = real_entry_for({**prospect, 'draft_year': prospect.get('draft_year') or year or current_draft_year(save)}) or {}
    college = real.get('college')
    if college:
        # Real college player: his actual college seasons (no game logs are kept for real players).
        career, logs = college_card(college)['seasons'], []
        season = career[0] if career else {}
    elif real:
        # Real high-school or international prospect: no college games to show (none are invented).
        season, logs, career = {'college_team': prospect.get('source_team')}, [], []
    else:
        season, logs = college_production(prospect)
        career = [season]
    upside_unlocked = float(scout.get('scouted_pct') or 0) >= 100
    from .save import positional_rating_reference
    reference, reference_label = positional_rating_reference(active, prospect.get('position'))
    return {
        'rating_league_averages': reference, 'rating_average_label': reference_label,
        'is_prospect': True, 'player_id': prospect_id, 'name': prospect.get('name'),
        'position': compact_position(prospect.get('position')), 'age': whole_prospect_age(prospect.get('age')),
        'height': height_label(prospect), 'draft_year': prospect.get('draft_year'),
        'source_team': prospect.get('source_team'), 'overall': scout.get('now'),
        'ratings': visible['ratings'], 'scouting_coverage': scout.get('scouted_pct', 0),
        'upside_unlocked': upside_unlocked,
        'upside_remaining': round(max(0, min(5, (scout.get('potential', 0) - scout.get('now', 0)) / 5)), 1) if upside_unlocked else None,
        'board_rank': boards.get('consensus_rank') or prospect.get('rank'),
        'rank_range': ({'low': boards['consensus_middle'][0], 'high': boards['consensus_middle'][1]} if boards else prospect.get('rank_range') or {}),
        'draft_boards': boards,
        'season': season, 'career_seasons': career,
        'recent_games': logs, 'recent_game_table': logs[-5:],
        'college_profile': college_card(college) if college else None,
        'scouting_profile': scouting_card(real.get('scouting')),
        'spatial_profile': prospect_spatial_profile(active, prospect, include_chart=True),
    }


def prospect_two_boards(active: dict[str, Any], team: dict[str, Any], prospect: dict[str, Any], year: Any) -> dict[str, Any]:
    """The prospect card's two boards: the league consensus (rank and spread) and the user's scouts' board (rank,
    monthly change, now-vs-upside read, coverage), with a plain sentence for any gap between them."""
    from .draft_scouting import class_scouting, previous_month_ranks, where_scouts_differ

    prospect_id = str(prospect.get('id') or prospect.get('prospect_id') or '')
    draft_year = str(prospect.get('draft_year') or year or '')
    try:
        scouting = class_scouting(active, draft_year)
    except (KeyError, ValueError, TypeError):
        return {}
    report = (scouting['reports'].get(team['id']) or {}).get(prospect_id)
    consensus = scouting['consensus'].get(prospect_id)
    if not report or not consensus:
        return {}
    previous = previous_month_ranks(active, draft_year, team['id'], scouting['month']).get(prospect_id) if not scouting['ahead'] else None
    differ = where_scouts_differ(scouting, team['id'], prospect_id)
    gap = int(report['scout_rank']) - int(consensus['rank'])
    if differ and abs(gap) >= 2:
        note = f"Your scouts are {differ}."
    elif abs(gap) >= 3:
        note = f"Your scouts rank him {'lower' if gap > 0 else 'higher'} than the league does."
    else:
        note = "Your scouts and the league see him about the same."
    return {
        'month_label': scouting['month_label'],
        'consensus_rank': consensus['rank'], 'consensus_best': consensus['best'], 'consensus_worst': consensus['worst'],
        'consensus_middle': list(consensus['middle']),
        'scout_rank': report['scout_rank'], 'scout_rank_previous': previous,
        'scout_rank_change': (previous - report['scout_rank']) if previous else None,
        'development': report['development'], 'coverage': report['coverage'],
        'scouts_differ': differ, 'note': note,
    }


def injury_body_map(active: dict[str, Any], player: dict[str, Any], state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Per-body-part injury outlook (player card body map); never blocks the card."""
    from .injury_model import body_risk_map
    try:
        return body_risk_map(active, player, state)
    except (KeyError, TypeError, ValueError):
        return None


def injury_body_compact(active: dict[str, Any], player: dict[str, Any], state: dict[str, Any] | None = None,
                        highlight: str | None = None) -> dict[str, Any] | None:
    """Table-sized body map (injury risk shown as a figure, not a ring)."""
    from .injury_model import compact_body_map
    return compact_body_map(injury_body_map(active, player, state), highlight)


def player_card_payload(canonical: dict[str, Any], save_path: Path, player_id: str) -> dict[str, Any]:
    """Return presentation evidence for a player without creating a second rules path."""
    context = dashboard_read_context(canonical, save_path)
    cached = context.setdefault("player_cards", {}).get(player_id)
    if cached is not None:
        return cached
    save = context["save"]
    active = transaction_read_active(context)
    player = next((item for item in active.get("players", []) if str(item.get("id")) == player_id), None)
    if not player:
        raise AppActionError(f"No player found with id {player_id!r}.")
    player_team_id = str(player.get("team_id") or "")
    team = next((item for item in active.get("teams", []) if str(item.get("id")) == player_team_id), {})
    attrs = player_display_attribute_summary(active, player_id)
    valuation = next(
        (item for item in active.get("player_asset_valuations", []) if str(item.get("player_id")) == player_id),
        fallback_asset_valuation(player),
    )
    totals = (save.get("player_season_stats") or {}).get(player_id, {})
    games = int(totals.get("games") or 0)
    divisor = max(1, games)
    logs = sorted(
        [
            *load_history_records(save_path, save, "player_game_logs", player_id=player_id, limit=30),
            *[row for row in save.get("player_game_logs", []) if str(row.get("player_id")) == player_id],
        ],
        key=lambda row: (str(row.get("date") or ""), str(row.get("game_id") or "")),
    )[-30:]

    def game_score(row: dict[str, Any]) -> float:
        return round(
            float(row.get("points") or 0.0)
            + 1.2 * float(row.get("rebounds") or 0.0)
            + 1.5 * float(row.get("assists") or 0.0)
            + 3.0 * float(row.get("steals") or 0.0)
            + 3.0 * float(row.get("blocks") or 0.0)
            - 1.5 * float(row.get("turnovers") or row.get("tov") or 0.0),
            1,
        )

    results_by_game = {
        str(result.get("game_id")): result
        for result in [*save.get("game_result_summaries", []), *save.get("game_results", [])]
    }
    teams_by_id = {str(item["id"]): item for item in active.get("teams", [])}
    from .save import schedule_for_save
    from .resource_paths import game_resource_root
    schedule_dates = {}
    for game in [*schedule_for_save(game_resource_root(), save), *save.get("playoff_state", {}).get("games", [])]:
        external = game.get("externalGameId")
        for identifier in (external, game.get("id"), stable_id("game", external) if external else None):
            if identifier and game.get("gameDate"):
                schedule_dates[str(identifier)] = game["gameDate"]
    def recent_game_date(row):
        result_row = results_by_game.get(str(row.get("game_id")), {})
        return row.get("date") or row.get("gameDate") or result_row.get("date") or result_row.get("gameDate") or schedule_dates.get(str(row.get("game_id")))

    def recent_opponent(row: dict[str, Any]) -> dict[str, Any]:
        result = results_by_game.get(str(row.get("game_id")), {})
        home_id, away_id = result.get("home_team_id"), result.get("away_team_id")
        row_team_id = row.get("team_id") or next(
            (key for key, item in teams_by_id.items() if item.get("abbrev") == row.get("team_abbrev")),
            player_team_id,
        )
        opponent_id = away_id if row_team_id == home_id else home_id if row_team_id == away_id else None
        opponent = teams_by_id.get(str(opponent_id), {})
        return {"opponent_team_id": opponent_id, "opponent_abbrev": opponent.get("abbrev")}

    recent_games = [
        {
            "game_id": row.get("game_id"),
            "date": recent_game_date(row),
            "team_abbrev": row.get("team_abbrev"),
            **{key: row.get(key, 0) for key in ["minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "fga", "fg3a", "fta", "ftm"]},
            "game_score": game_score(row),
            **recent_opponent(row),
        }
        for row in logs
    ]
    recent_games.sort(key=lambda row: (str(row.get("date") or ""), str(row.get("game_id") or "")))
    # Keep missed completed games in the five-row table, without inventing
    # played-game logs or changing the player's game-score history.
    table_games = {str(row.get("game_id")): row for row in recent_games if row.get("game_id")}
    joined_date = ""
    for transaction in save.get("transaction_logs", []):
        if transaction.get("transaction_type") != "trade":
            continue
        from .transactions import trade_assets
        if any(asset.get("kind") == "player" and asset.get("id") == player_id
               for asset in trade_assets(transaction.get('assets') or {})):
            joined_date = max(joined_date, str(transaction.get("date") or ""))
    for game_id, result_row in results_by_game.items():
        if player_team_id not in {str(result_row.get("home_team_id")), str(result_row.get("away_team_id"))}:
            continue
        if joined_date and str(result_row.get("date") or "") < joined_date:
            continue
        if game_id not in table_games:
            missed = {"game_id": game_id, "date": recent_game_date({"game_id": game_id}), "team_id": player_team_id,
                      **{key: 0 for key in ("minutes", "points", "rebounds", "assists", "steals", "blocks", "turnovers", "game_score")}}
            table_games[game_id] = {**missed, **recent_opponent(missed)}
    recent_game_table = sorted(table_games.values(), key=lambda row: (str(row.get("date") or ""), str(row.get("game_id") or "")))[-5:]
    current_season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    start = season_start_year_for_app(current_season)
    salary_by_year = player_salary_table(active, player_id)
    salary_seasons = [season_label_for_app(start + offset) for offset in range(6)]
    cap_by_year = {
        season: team_cap_summary(active, save, str(player.get("team_id") or ""), season=season)
        for season in salary_seasons[:4]
        if player.get("team_id")
    }
    development_signal = float(valuation.get("development_upside") or 0.0)
    display_upside = max(0.0, min(5.0, development_signal / 22.0 * 5.0))
    result = {
        "player_id": player_id,
        "name": player.get("name"),
        "headshot_url": player.get("headshot_url"),
        "team": team,
        "position": compact_position(player.get("position")),
        "age": player.get("display_age", player.get("age")),
        "height": height_label(player),
        "ratings": attrs,
        "rating_scale": RATING_SCALE,
        "rating_quartiles": display_rating_tertiles(active),
        "rating_league_averages": display_rating_averages(active),
        "spatial_profile": player_spatial_profile(active, player, include_chart=True),
        "health_risk": round(float(valuation.get("health_risk") or 0.0), 1),
        "injury_body_map": injury_body_map(active, player, next((row for row in save.get("health_states", []) if str(row.get("player_id")) == player_id), None)),
        "upside_remaining": round(display_upside, 1),
        "decline_watch": decline_watch_value(active, player, development_signal),
        "trade_value": round(market_trade_target_value(player, valuation), 1),
        "season": {
            "games": games,
            "team_games": sum(int((save.get("team_records", {}).get(player_team_id) or {}).get(key) or 0) for key in ("wins", "losses")),
            "fga_per_game": round(float(totals.get("fga") or 0) / divisor, 1),
            "fg_pct": round(float(totals.get("fgm") or 0) / float(totals["fga"]) * 100, 1) if totals.get("fga") else None,
            "fg3a_per_game": round(float(totals.get("fg3a") or 0) / divisor, 1),
            "fg3m_per_game": round(float(totals.get("fg3m") or 0) / divisor, 1),
            "fg3_pct": round(float(totals.get("fg3m") or 0) / float(totals["fg3a"]) * 100, 1) if totals.get("fg3a") else None,
            "mpg": round(float(totals.get("minutes") or 0.0) / divisor, 1) if totals else 0.0,
            "ppg": round(float(totals.get("points") or 0.0) / divisor, 1) if totals else 0.0,
            "rpg": round(float(totals.get("rebounds") or 0.0) / divisor, 1) if totals else 0.0,
            "apg": round(float(totals.get("assists") or 0.0) / divisor, 1) if totals else 0.0,
            "spg": round(float(totals.get("steals") or 0.0) / divisor, 1) if totals else 0.0,
            "bpg": round(float(totals.get("blocks") or 0.0) / divisor, 1) if totals else 0.0,
            "topg": round(float(totals.get("turnovers") or 0.0) / divisor, 1) if totals else 0.0,
            "fta_per_game": round(float(totals.get("fta") or 0.0) / divisor, 1) if totals else 0.0,
            "ft_pct": round(float(totals.get("ftm") or 0.0) / max(1.0, float(totals.get("fta") or 0.0)) * 100.0, 1) if totals else 0.0,
            # Screen assists (new ratings only; None when the save's box scores do not track them).
            "screen_assists_per_game": (round(float(totals["screen_assists"]) / divisor, 1)
                                        if totals and totals.get("screen_assists") is not None else None),
        },
        "recent_games": recent_games,
        "recent_game_table": recent_game_table,
        "salary_seasons": [{"season": season, "salary_millions": salary_by_year.get(season)} for season in salary_seasons],
        "cap_by_year": cap_by_year,
    }
    from .career_stats import career_record, player_career_seasons
    career = career_record(player)
    rookie = next((row for row in save.get("incoming_rookies", []) if row.get("player_id") == player_id), {})
    result["draft_year"] = player.get("draft_year") or rookie.get("draft_year") or career.get("draft_year")
    result["draft_position"] = player.get("draft_position") or rookie.get("overall_pick") or career.get("draft_position")
    result["draft_status"] = player.get("draft_status") or career.get("draft_status")
    result["season"]["season"] = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    result["season"]["team_abbrevs"] = [team["abbrev"]] if team.get("abbrev") else []
    result["career_seasons"] = player_career_seasons(player, save, result["season"])
    if 'post_creation' in attrs:
        result['offensive_contributions'] = [
            {'key': key, 'label': label, 'rating': attrs[key], 'modeled': True}
            for key, label in (('post_creation', 'Post creation'), ('assisted_finishing', 'Assisted finishing'),
                               ('screening', 'Screening'), ('offensive_rebounding', 'Offensive rebounding'))
        ]
    from . import ratings_model
    if ratings_model.uses_inputs_model(active):
        from .player_profile import player_profile
        inputs_profile = player_profile(active, player_id)
        if inputs_profile:
            inputs_profile["coach"]["minutes_projection"] = display_minutes_projection(player)
            today = str((save.get("state") or {}).get("current_date") or "")
            active_injury = next((
                event for event in save.get("injury_events", [])
                if str(event.get("player_id")) == player_id
                and str(event.get("start_date") or "")[:10] <= today < str(event.get("return_date") or "9999")[:10]
            ), None)
            if active_injury:
                returns = str(active_injury.get("return_date") or "")[:10]
                inputs_profile["coach"]["availability_note"] = f"Out (injured){f' · expected back {returns}' if returns else ''}"
            else:
                from .sim import rust_display
                state_row = next((row for row in save.get("health_states", []) if str(row.get("player_id")) == player_id), None)
                rust = rust_display(state_row)
                if rust:
                    inputs_profile["coach"]["availability_note"] = (
                        f"Rusty after injury · in-game ratings −{rust['rust_penalty']} · fades in about {rust['rust_days']} days")
            result["inputs_profile"] = inputs_profile
    context["player_cards"][player_id] = result
    return result


def player_finder_payload(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    context = dashboard_read_context(canonical, save_path)
    save = context["save"]
    active = transaction_read_active(context)
    teams = {team["id"]: team for team in active.get("teams", [])}
    values = {item.get("player_id"): item for item in active.get("player_asset_valuations", [])}
    stats = save.get("player_season_stats", {})
    health = {state.get("player_id"): state for state in save.get("health_states", [])}
    current_date = save.get("state", {}).get("current_date")
    team_games = {
        team_id: int(record.get("wins") or 0) + int(record.get("losses") or 0)
        for team_id, record in (save.get("team_records") or {}).items()
    }
    rows: list[dict[str, Any]] = []
    salary_seasons: set[str] = set()
    for player in active.get("players", []):
        if player.get("_inactive_player"):
            continue
        team_id = player.get("team_id")
        attrs = player_display_attribute_summary(active, player["id"])
        valuation = values.get(player["id"], {})
        totals = stats.get(player["id"], {})
        games = int(totals.get("games") or 0) if totals else 0
        salary_by_year = player_salary_table(active, player["id"])
        salary_seasons.update(str(season) for season in salary_by_year)
        row = {
            "id": player["id"],
            "name": player.get("name"),
            "headshot_url": player.get("headshot_url"),
            "health_risk": round(float(valuation["health_risk"]), 1) if valuation.get("health_risk") is not None else None,
            "injury_body": injury_body_compact(active, player, health.get(player["id"])),
            "upside_remaining": round(max(0.0, min(5.0, float(valuation["development_upside"]) / 22.0 * 5.0)), 1) if valuation.get("development_upside") is not None else None,
            "team_id": team_id,
            "team_abbrev": teams.get(team_id, {}).get("abbrev", "FA") if team_id else "FA",
            "position": compact_position(player.get("position")),
            "age": player.get("display_age", player.get("age")),
            "height": height_label(player),
            "height_inches": player.get("height_inches"),
            "ratings": attrs,
            "health": player_health_label(health.get(player["id"]), current_date),
            "games": games,
            "team_games": team_games.get(team_id, 0),
            "games_missed": int((player_health_label(health.get(player["id"]), current_date) or {}).get("games_missed") or 0),
            "minutes_projection": display_minutes_projection(player),
            "display_mpg": per_game_stat(totals, "minutes") if games else display_minutes_projection(player),
            "points_per_game": per_game_stat(totals, "points") if totals else 0.0,
            "rebounds_per_game": per_game_stat(totals, "rebounds") if totals else 0.0,
            "assists_per_game": per_game_stat(totals, "assists") if totals else 0.0,
            "steals_per_game": per_game_stat(totals, "steals") if totals else 0.0,
            "blocks_per_game": per_game_stat(totals, "blocks") if totals else 0.0,
            "turnovers_per_game": per_game_stat(totals, "turnovers") if totals else 0.0,
            "salary_by_year": salary_by_year,
        }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            -float((row.get("ratings") or {}).get("overall") or 0.0),
            -float(row.get("display_mpg") or 0.0),
            str(row.get("name") or ""),
        )
    )
    seasons = sorted(salary_seasons)[:5]
    return {
        "as_of_date": save.get("state", {}).get("current_date"),
        "rows": rows,
        "seasons": seasons,
        "default_sort": "overall",
        "rating_scale": RATING_SCALE,
        "filters": ["player", "team", "position", "height", "age", "overall", "offense", "shooting", "creation", "defense", "spacing", "passing", "rebounding", "rim_deterrence", "athleticism", "games_missed", "display_mpg", "points_per_game", "rebounds_per_game", "assists_per_game", "steals_per_game", "blocks_per_game", "turnovers_per_game", *seasons],
    }


def league_traits_payload(canonical: dict[str, Any], save_path: Path, trait: str = "overall", limit: int = 80) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    teams = {team["id"]: team for team in active.get("teams", [])}
    stats = save.get("player_season_stats", {})
    rows = []
    for player in active.get("players", []):
        team_id = player.get("team_id")
        if not team_id:
            continue
        attrs = player_display_attribute_summary(active, player["id"])
        totals = stats.get(player["id"], {})
        games = max(1, int(totals.get("games") or 0))
        row = {
            "player_id": player["id"],
            "player_name": player.get("name"),
            "position": compact_position(player.get("position")),
            "age": player.get("display_age", player.get("age")),
            "height": height_label(player),
            "team_id": team_id,
            "team_abbrev": teams.get(team_id, {}).get("abbrev", team_id),
            "minutes": display_minutes_projection(player),
            "games": int(totals.get("games") or 0),
            "points_per_game": round(float(totals.get("points") or 0.0) / games, 1) if totals else 0.0,
            "rebounds_per_game": round(float(totals.get("rebounds") or 0.0) / games, 1) if totals else 0.0,
            "assists_per_game": round(float(totals.get("assists") or 0.0) / games, 1) if totals else 0.0,
            "contract": contract_summary(contract_for_player(active, player["id"]), str(active.get("meta", {}).get("active_season") or "")),
            "ratings": attrs,
            "overall": attrs.get("overall"),
            "offense": attrs.get('offense', composite_rating(attrs, ["shooting", "creation", "passing", "rim_pressure"], [0.3, 0.3, 0.2, 0.2])),
            "defense": attrs.get("defense"),
            "spacing": attrs.get("spacing") or composite_rating(attrs, ["shooting", "range", "release", "versatility"], [0.36, 0.36, 0.14, 0.14]),
            "creation": attrs.get("creation"),
            "rim_pressure": attrs.get("rim_pressure"),
            "rebounding": attrs.get("rebounding"),
            "athleticism": attrs.get("athleticism"),
            "disruption": composite_rating(attrs, ["def_effort", "screen_nav", "defense", "portability"], [0.34, 0.24, 0.28, 0.14]),
            "rim_protection": attrs.get("rim_deterrence"),
            "passing": attrs.get("passing"),
        }
        rows.append(row)
    trait_key = {
        "rim": "rim_pressure",
        "reb": "rebounding",
        "defensive_disruption": "disruption",
        "rim_deterrence": "rim_protection",
        "play": "passing",
        "ply": "passing",
    }.get(str(trait or "overall"), str(trait or "overall"))
    rows.sort(key=lambda item: (-float(item.get(trait_key) or 0.0), -float(item.get("minutes") or 0.0), item.get("player_name") or ""))
    return {
        "trait": trait_key,
        "leaders": rows[:limit],
        "as_of_date": save.get("state", {}).get("current_date"),
        "rating_scale": RATING_SCALE,
    }


def dashboard_summary_leaders_payload(
    canonical: dict[str, Any],
    save_path: Path,
    limit: int = 10,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .dashboard_metrics import award_watch_payload

    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    teams = {team["id"]: team for team in active.get("teams", [])}
    stats = save.get("player_season_stats", {})
    active_season = save_active_contract_season(save)
    rows: list[dict[str, Any]] = []
    for player in active.get("players", []):
        team_id = player.get("team_id")
        if not team_id:
            continue
        attrs = player_display_attribute_summary(active, player["id"])
        totals = stats.get(player["id"], {})
        games = int(totals.get("games") or 0) if totals else 0
        divisor = max(1, games)
        row = {
            "player_id": player["id"],
            "player_name": player.get("name"),
            "headshot_url": player.get("headshot_url"),
            "position": compact_position(player.get("position")),
            "age": player.get("display_age", player.get("age")),
            "height": height_label(player),
            "team_id": team_id,
            "team_abbrev": teams.get(team_id, {}).get("abbrev", team_id),
            "rookie": is_rookie_for_awards(player, active_season, save),
            "award_ratings": player_attribute_summary(active, player["id"]),
            "values": {
                "overall": attrs.get("overall"),
                "shooting": attrs.get("shooting"),
                "creation": attrs.get("creation"),
                "defense": attrs.get("defense"),
                "spacing": attrs.get("spacing") or composite_rating(attrs, ["shooting", "range", "release", "versatility"], [0.36, 0.36, 0.14, 0.14]),
                "passing": attrs.get("passing"),
                "rebounding": attrs.get("rebounding"),
                "rim_deterrence": attrs.get("rim_deterrence"),
                "athleticism": attrs.get("athleticism"),
                "minutes": round(float(totals.get("minutes") or 0.0) / divisor, 1) if games else display_minutes_projection(player),
                "points": round(float(totals.get("points") or 0.0) / divisor, 1) if totals else 0.0,
                "rebounds": round(float(totals.get("rebounds") or 0.0) / divisor, 1) if totals else 0.0,
                "assists": round(float(totals.get("assists") or 0.0) / divisor, 1) if totals else 0.0,
                "steals": round(float(totals.get("steals") or 0.0) / divisor, 1) if totals else 0.0,
                "blocks": round(float(totals.get("blocks") or 0.0) / divisor, 1) if totals else 0.0,
                "turnovers": round(float(totals.get("turnovers") or 0.0) / divisor, 1) if totals else 0.0,
            },
        }
        rows.append(row)

    rookie_rows = sorted(
        [item for item in rows if item.get("rookie")],
        key=lambda item: (
            -(
                float(item.get("values", {}).get("points") or 0.0) * 1.18
                + float(item.get("values", {}).get("assists") or 0.0) * 0.92
                + float(item.get("values", {}).get("rebounds") or 0.0) * 0.72
                + float(item.get("values", {}).get("overall") or 0.0) * 0.48
                + float(item.get("values", {}).get("minutes") or 0.0) * 0.18
            ),
            item.get("player_name") or "",
        ),
    )

    fields = [
        ("overall", "OVR"),
        ("shooting", "Shot"),
        ("creation", "Create"),
        ("defense", "Def"),
        ("spacing", "Space"),
        ("passing", "Pass"),
        ("rebounding", "Reb"),
        ("rim_deterrence", "Rim"),
        ("athleticism", "Ath"),
        ("minutes", "MPG"),
        ("points", "PTS"),
        ("rebounds", "REB"),
        ("assists", "AST"),
        ("steals", "STL"),
        ("blocks", "BLK"),
        ("turnovers", "TO"),
    ]
    payload_fields = []
    for key, label in fields:
        leaders = []
        ordered = sorted(
            rows,
            key=lambda item: (
                -float(item.get("values", {}).get(key) or 0.0),
                -float(item.get("values", {}).get("minutes") or 0.0),
                item.get("player_name") or "",
            ),
        )
        for item in ordered[: max(1, int(limit))]:
            value = item.get("values", {}).get(key)
            if value is None:
                continue
            leaders.append(
                {
                    "player_id": item.get("player_id"),
                    "player_name": item.get("player_name"),
                    "team_id": item.get("team_id"),
                    "team_abbrev": item.get("team_abbrev"),
                    "position": item.get("position"),
                    "age": item.get("age"),
                    "height": item.get("height"),
                    "value": round(float(value), 1),
                }
            )
        payload_fields.append({"key": key, "label": label, "title": f"{label} Top {max(1, int(limit))}", "leaders": leaders})
    return {
        "as_of_date": save.get("state", {}).get("current_date"),
        "limit": max(1, int(limit)),
        "fields": payload_fields,
        "award_races": award_watch_payload(rows, {
            **save,
            "player_game_logs": [
                *load_history_records(
                    save_path, save, "player_game_logs",
                    event_date_from=active_season_floor(save),
                ),
                *save.get("player_game_logs", []),
            ],
        }),
        "rookies": [
            {
                "player_id": item.get("player_id"),
                "player_name": item.get("player_name"),
                "team_id": item.get("team_id"),
                "team_abbrev": item.get("team_abbrev"),
                "position": item.get("position"),
                "age": item.get("age"),
                "height": item.get("height"),
                "value": round(float(item.get("values", {}).get("overall") or 0.0), 1),
            }
            for item in rookie_rows[: max(1, int(limit))]
        ],
    }


def dashboard_trends_payload(
    canonical: dict[str, Any],
    save_path: Path,
    team_query: str,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    team = resolve_team(active, team_query)
    teams = {item["id"]: item for item in active.get("teams", [])}
    conference_team_ids = {
        item["id"]
        for item in active.get("teams", [])
        if item.get("conference") == team.get("conference")
    }
    standings_points = weekly_standing_rank_points(save, teams, conference_team_ids, team["id"])
    if not standings_points:
        current = league_standings(canonical, save_path).get("standings", [])
        conference_rows = [row for row in current if row.get("team", {}).get("conference") == team.get("conference")]
        rank = next((index + 1 for index, row in enumerate(conference_rows) if row.get("team", {}).get("id") == team["id"]), None)
        if rank:
            standings_points = [{"label": "Now", "value": rank, "record": record_label(save.get("team_records", {}).get(team["id"], {}))}]

    development_lines = player_development_trend_lines(active, save, team["id"])
    efficiency_points = weekly_efficiency_points(save, team["id"])
    identity_by_team = team_identity_report(active, save)
    four_factors = dashboard_four_factors(save, active, team["id"], identity_by_team)
    return {
        "team": {"id": team["id"], "abbrev": team.get("abbrev"), "conference": team.get("conference")},
        "standings": {
            "title": f"{team.get('abbrev')} Weekly Standing",
            "points": standings_points,
            "scale": "conference_rank",
        },
        "development": {
            "title": "Monthly Player Development",
            "lines": development_lines,
            "scale": "estimated_overall",
            "latest_month": latest_development_month_for_team(save, team["id"]),
            "applied_months": sorted(save.get("applied_development_months", [])),
        },
        "efficiency": {
            "title": "Weekly Efficiency",
            "points": efficiency_points,
            "events": weekly_efficiency_events(active, save, save_path, team["id"]),
            "league_average": league_efficiency_average(save),
            "scale": "points_per_100_possessions",
        },
        "four_factors": four_factors,
    }


def league_efficiency_average(save: dict[str, Any]) -> float:
    logs = [row for row in save.get("team_game_logs", []) if float(row.get("possessions") or 0.0) > 0]
    possessions = sum(float(row.get("possessions") or 0.0) for row in logs)
    if possessions <= 0:
        return 112.0
    return round(sum(float(row.get("points") or 0.0) for row in logs) / possessions * 100.0, 1)


def dashboard_four_factors(
    save: dict[str, Any],
    active: dict[str, Any],
    target_team_id: str,
    identity_by_team: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return team Four Factors with league-relative ranks and display fills."""
    all_logs = list(save.get("team_game_logs", []))
    logs_by_team: dict[str, list[dict[str, Any]]] = {}
    logs_by_game: dict[str, list[dict[str, Any]]] = {}
    for row in all_logs:
        team_id = str(row.get("team_id") or "")
        if team_id:
            logs_by_team.setdefault(team_id, []).append(row)
        game_id = str(row.get("game_id") or "")
        if game_id:
            logs_by_game.setdefault(game_id, []).append(row)

    results: dict[str, dict[str, float]] = {}
    for team in active.get("teams", []):
        team_id = str(team.get("id") or "")
        rows = logs_by_team.get(team_id, [])
        fga = sum(float(row.get("fga") or 0.0) for row in rows)
        identity = identity_by_team.get(team_id, {}).get("metrics", {})
        if fga > 0:
            fgm = sum(float(row.get("fgm") or 0.0) for row in rows)
            fg3m = sum(float(row.get("fg3m") or 0.0) for row in rows)
            fta = sum(float(row.get("fta") or 0.0) for row in rows)
            turnovers = sum(float(row.get("turnovers") or 0.0) for row in rows)
            oreb = sum(
                float(row.get("offensive_rebounds") or float(row.get("rebounds") or 0.0) * 0.27)
                for row in rows
            )
            opponent_dreb = 0.0
            for row in rows:
                opponent = next((candidate for candidate in logs_by_game.get(str(row.get("game_id") or ""), []) if candidate.get("team_id") != row.get("team_id")), None)
                if opponent:
                    opponent_dreb += float(
                        opponent.get("defensive_rebounds")
                        or max(0.0, float(opponent.get("rebounds") or 0.0) * 0.73)
                    )
            results[team_id] = {
                "efg": (fgm + 0.5 * fg3m) / max(1.0, fga),
                "tov": turnovers / max(1.0, fga + 0.44 * fta + turnovers),
                "oreb": oreb / max(1.0, oreb + opponent_dreb),
                "ftr": fta / max(1.0, fga),
            }
        else:
            results[team_id] = {
                "efg": 0.515 + (float(identity.get("spacing") or 50.0) - 50.0) * 0.0017,
                "tov": 0.145 - (float(identity.get("creation") or 50.0) - 50.0) * 0.0008,
                "oreb": 0.265 + (float(identity.get("rebounding") or 50.0) - 50.0) * 0.0015,
                "ftr": 0.245 + (float(identity.get("rim_pressure") or 50.0) - 50.0) * 0.0018,
            }

    specs = (("efg", "eFG%", True), ("tov", "TOV%", False), ("oreb", "OREB%", True), ("ftr", "FTR", True))
    payload: list[dict[str, Any]] = []
    team_count = max(1, len(results))
    for key, label, higher_is_better in specs:
        ordered = sorted(results, key=lambda team_id: results[team_id][key], reverse=higher_is_better)
        rank = ordered.index(str(target_team_id)) + 1 if str(target_team_id) in ordered else team_count
        values = [row[key] for row in results.values()]
        value = results.get(str(target_team_id), {}).get(key, 0.0)
        payload.append(
            {
                "key": key,
                "label": label,
                "value": round(value * 100.0, 1),
                "league_average": round((sum(values) / max(1, len(values))) * 100.0, 1),
                "rank": rank,
                "team_count": team_count,
                "score": round(((team_count - rank + 1) / team_count) * 100.0, 1),
            }
        )
    return payload


def weekly_efficiency_events(active: dict[str, Any], save: dict[str, Any], save_path: Path, team_id: str) -> list[dict[str, Any]]:
    """Dated team events with recorded, rather than invented, rotation changes."""
    today = str(save.get("state", {}).get("current_date") or "")
    players = {p["id"]: p for p in active.get("players", [])}
    injuries = [e for e in save.get("injury_events", []) if e.get("team_id") == team_id and str(e.get("start_date") or "") <= today]
    logs = [r for r in [*load_history_records(save_path, save, "player_game_logs"), *save.get("player_game_logs", [])] if r.get("team_id") == team_id] if injuries else []
    logs = list({r.get("id", f"{r.get('game_id')}:{r.get('player_id')}"): r for r in logs}.values())
    days = sorted({str(r.get("date") or "")[:10] for r in logs})
    values = {v.get("player_id"): v for v in with_transaction_context(active).get("player_asset_valuations", [])} if injuries else {}
    events = []
    def averages(selected_days):
        result = {}
        for r in logs:
            if str(r.get("date") or "")[:10] in selected_days:
                pid = r.get("player_id")
                result[pid] = result.get(pid, 0.0) + float(r.get("minutes") or 0)
        return {pid: minutes / len(selected_days) for pid, minutes in result.items()} if selected_days else {}
    for injury in injuries:
        if int(injury.get("expected_games_missed") or 0) <= 5:
            continue
        pid = injury.get("player_id")
        start = str(injury.get("start_date") or "")[:10]
        expected_return = str(injury.get("return_date") or "")[:10]
        before_days = [d for d in days if d < start][-3:]
        before = averages(before_days)
        minutes = float(injury.get("player_minutes_projection") or before.get(pid) or display_minutes_projection(players.get(pid, {})))
        historical_starters = {other for other, amount in sorted(before.items(), key=lambda item: -item[1])[:5] if amount > 0}
        starter = bool(injury["was_starter"]) if "was_starter" in injury else pid in historical_starters if before_days else pid in save.get("starting_lineups", {}).get(team_id, {}).get("slots", {}).values()
        if not starter and minutes <= 25:
            continue
        returns = sorted(str(r.get("date") or "")[:10] for r in logs if r.get("player_id") == pid and expected_return and str(r.get("date") or "")[:10] >= expected_return and float(r.get("minutes") or 0) > 0)
        returned = returns[0] if returns else None
        during_days = [d for d in days if start <= d and (not returned or d < returned)][:3]
        during = averages(during_days)
        distribution = [{"name": players.get(other, {}).get("name", other), "minutes": round(amount - before.get(other, 0), 1)} for other, amount in during.items() if other != pid and amount - before.get(other, 0) >= 0.5] if before_days else []
        risk = injury.get("health_risk")
        risk_source = "At injury"
        if risk is None:
            risk = values.get(pid, {}).get("health_risk")
            risk_source = "Current health risk"
        from .injury_model import event_part
        common = {"player_name": players.get(pid, {}).get("name", pid), "body_area": str(injury.get("body_area") or "injury").replace("_", " "), "expected_games_missed": injury.get("expected_games_missed"), "health_risk": risk, "risk_label": risk_source,
                  "injury_body": injury_body_compact(active, players[pid], None, event_part(injury)) if pid in players else None, "minutes_lost": round(minutes, 1), "distribution": sorted(distribution, key=lambda r: -r["minutes"]), "distribution_note": "Observed average minutes gained in the first games during the absence" if before_days and during_days else "Minute redistribution is not yet available", "injury_date": start}
        events.append({**common, "id": injury["id"], "date": start, "kind": "injury", "color": "red", "title": f"{common['player_name']} injured"})
        if returned and returned <= today:
            events.append({**common, "id": injury["id"] + "-return", "date": returned, "kind": "injury_return", "color": "green", "title": f"{common['player_name']} returned to the lineup"})
    staff_logs = [r for r in save.get("transaction_logs", []) if r.get("transaction_type") in {"staff_fire", "staff_hire"} and team_id in r.get("teams", []) and str(r.get("date") or "") <= today]
    consumed = set()
    def coach(staff, label):
        return {"name": staff.get("name", "Unknown coach"), "grade": round(staff_grade(staff), 1), "label": label, "role": str(staff.get("slot") or staff.get("role_preference") or "coach").replace("_", " ")}
    for log in staff_logs:
        if log.get("id") in consumed:
            continue
        assets = log.get("assets") or {}
        firing = log.get("transaction_type") == "staff_fire"
        old = assets.get("fired_staff") if firing else assets.get("previous_staff")
        new = assets.get("interim_staff") if firing else assets.get("staff")
        paired = next((r for r in staff_logs if firing and r.get("transaction_type") == "staff_hire" and r.get("date") == log.get("date") and ((r.get("assets") or {}).get("staff") or {}).get("slot") == (old or {}).get("slot")), None)
        if paired:
            new = paired.get("assets", {}).get("staff")
            consumed.add(paired.get("id"))
        coaches = ([coach(old, "Fired" if firing else "Previous")] if old else []) + ([coach(new, "Interim replacement" if firing and not paired else "Hired")] if new else [])
        events.append({"id": log.get("id"), "date": str(log.get("date"))[:10], "kind": "staff_replacement" if paired else log.get("transaction_type"), "color": "yellow" if paired else "red" if firing else "green", "title": "Coach replaced" if paired else "Coach fired" if firing else "Coach hired", "coaches": coaches})
    return sorted(events, key=lambda e: (e["date"], e["id"]))


def weekly_efficiency_points(save: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    logs = sorted(
        [
            log for log in save.get("team_game_logs", [])
            if str(log.get("team_id")) == str(team_id) and str(log.get("date") or "")[:10]
        ],
        key=lambda item: str(item.get("date") or ""),
    )
    if not logs:
        return []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for log in logs:
        day = date.fromisoformat(str(log.get("date"))[:10])
        week_start = day - timedelta(days=day.weekday())
        buckets.setdefault(week_start.isoformat(), []).append(log)
    points: list[dict[str, Any]] = []
    for label, rows in sorted(buckets.items()):
        possessions = sum(float(row.get("possessions") or 0.0) for row in rows)
        if possessions <= 0:
            possessions = 100.0 * len(rows)
        offense = sum(float(row.get("points") or 0.0) for row in rows) / possessions * 100.0
        defense = sum(float(row.get("opponent_points") or 0.0) for row in rows) / possessions * 100.0
        points.append(
            {
                "label": label[5:],
                "date": label,
                "offense": round(offense, 1),
                "defense": round(defense, 1),
                "net": round(offense - defense, 1),
                "possessions": possessions,
                "games": len(rows),
            }
        )
    return points


def weekly_standing_rank_points(
    save: dict[str, Any],
    teams: dict[str, dict[str, Any]],
    conference_team_ids: set[str],
    target_team_id: str,
) -> list[dict[str, Any]]:
    logs = sorted(
        [
            log for log in save.get("team_game_logs", [])
            if log.get("team_id") in conference_team_ids and str(log.get("date") or "")[:10]
        ],
        key=lambda item: (str(item.get("date") or ""), str(item.get("team_id") or "")),
    )
    if not logs:
        return []
    records = {team_id: {"wins": 0, "losses": 0, "point_diff": 0} for team_id in conference_team_ids}
    first_day = safe_date(logs[0].get("date"))
    next_cutoff = first_day + timedelta(days=7) if first_day else None
    points: list[dict[str, Any]] = []
    for log in logs:
        log_day = safe_date(log.get("date"))
        while next_cutoff and log_day and log_day >= next_cutoff and records[target_team_id]["wins"] + records[target_team_id]["losses"] > 0:
            points.append(standing_rank_point(next_cutoff.isoformat(), records, teams, target_team_id))
            next_cutoff += timedelta(days=7)
        record = records.setdefault(str(log.get("team_id")), {"wins": 0, "losses": 0, "point_diff": 0})
        if str(log.get("result") or "").upper() == "W":
            record["wins"] += 1
        else:
            record["losses"] += 1
        record["point_diff"] += int(log.get("points") or 0) - int(log.get("opponent_points") or 0)
    final_date = str(logs[-1].get("date") or "")[:10]
    final_point = standing_rank_point(final_date, records, teams, target_team_id)
    if not points or points[-1].get("label") != final_point.get("label"):
        points.append(final_point)
    return points[-16:]


def standing_rank_point(label: str, records: dict[str, dict[str, int]], teams: dict[str, dict[str, Any]], target_team_id: str) -> dict[str, Any]:
    ordered = sorted(
        records.items(),
        key=lambda item: (
            -win_pct_value(item[1]),
            -int(item[1].get("wins") or 0),
            -int(item[1].get("point_diff") or 0),
            teams.get(item[0], {}).get("abbrev") or item[0],
        ),
    )
    rank = next((index + 1 for index, (team_id, _record) in enumerate(ordered) if team_id == target_team_id), len(ordered))
    return {"label": label[5:] if len(label) >= 7 else label, "value": rank, "record": record_label(records.get(target_team_id, {}))}


def win_pct_value(record: dict[str, Any]) -> float:
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    games = wins + losses
    return wins / games if games else 0.0


def record_label(record: dict[str, Any]) -> str:
    return f"{int(record.get('wins') or 0)}-{int(record.get('losses') or 0)}"


def safe_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def development_overall_path(active: dict[str, Any], player: dict[str, Any], deltas_by_month: list[tuple[str, dict[str, float]]]) -> tuple[float, list[float]]:
    """Exact OVR at the start and after each month, from the engine's own summary formula.

    Today's hidden ratings are walked back through the saved monthly development changes, then the same
    player_attribute_summary the card and AI use is evaluated at every month end. Minutes are held at today's
    projection, so the line isolates development (skill change), not role changes. Approximate only in the new
    inputs mode, where development is routed through the 94 inputs before ratings are re-derived."""
    player_id = player["id"]
    from .save import trait_values_by_player
    current = dict(trait_values_by_player(active).get(player_id, {}))
    meta = active.get("meta", {})

    def overall(traits: dict[str, float]) -> float:
        context = {"meta": meta, "players": [player],
                   "traits": [{"player_id": player_id, "trait_key": key, "value": value} for key, value in traits.items()]}
        return float(player_attribute_summary(context, player_id).get("overall") or 0.0)

    states = [current]
    for _month, deltas in reversed(deltas_by_month):
        previous = dict(states[-1])
        for key, delta in deltas.items():
            if key in previous:
                previous[key] = previous[key] - float(delta or 0.0)
        states.append(previous)
    states.reverse()  # start, after month 1, ..., today
    values = [overall(traits) for traits in states]
    return values[0], values[1:]


def player_development_trend_lines(active: dict[str, Any], save: dict[str, Any], team_id: str) -> list[dict[str, Any]]:
    players = {player["id"]: player for player in active.get("players", []) if player.get("team_id") == team_id}
    if not players:
        return []
    season_start = season_start_year_for_app(save_active_contract_season(save))
    first_month = f"{season_start}-10"
    last_month = f"{season_start + 1}-06"
    events_by_player: dict[str, list[dict[str, Any]]] = {}
    for event in save.get("development_events", []):
        player_id = event.get("player_id")
        month = str(event.get("month") or event.get("date") or "")[:7]
        if player_id in players and first_month <= month <= last_month:
            events_by_player.setdefault(str(player_id), []).append(event)
    paths: dict[str, tuple[float, list[tuple[str, float]]]] = {}
    for player_id, events in events_by_player.items():
        by_month: dict[str, dict[str, float]] = {}
        for event in sorted(events, key=lambda item: str(item.get("month") or item.get("date") or "")):
            month = str(event.get("month") or event.get("date") or "")[:7]
            bucket = by_month.setdefault(month, {})
            for key, delta in (event.get("trait_deltas") or {}).items():
                bucket[key] = bucket.get(key, 0.0) + float(delta or 0.0)
        ordered = sorted(by_month.items())
        start, values = development_overall_path(active, players[player_id], ordered)
        paths[player_id] = (start, [(month, value) for (month, _), value in zip(ordered, values)])
    moved_ids = sorted(
        paths,
        key=lambda player_id: (
            -abs((paths[player_id][1][-1][1] if paths[player_id][1] else paths[player_id][0]) - paths[player_id][0]),
            -display_minutes_projection(players[player_id]),
            players[player_id].get("name") or "",
        ),
    )
    minute_ids = [
        player["id"]
        for player in sorted(players.values(), key=display_minutes_projection, reverse=True)
        if player["id"] not in moved_ids
    ]
    top_ids = (moved_ids + minute_ids)[:16]
    lines: list[dict[str, Any]] = []
    for player_id in top_ids:
        if player_id not in paths:
            continue
        start, monthly = paths[player_id]
        points = [{"label": "Start", "season_slot": 0, "value": round(start, 2)}]
        for month, value in monthly:
            year = int(month[:4])
            month_number = int(month[5:7])
            month_index = (year - season_start) * 12 + month_number - 10
            points.append(
                {
                    "label": month[5:] if len(month) >= 7 else month,
                    "season_slot": max(1, min(9, month_index + 1)),
                    "value": round(value, 2),
                }
            )
        lines.append(
            {
                "player_id": player_id,
                "name": players[player_id].get("name"),
                "position": compact_position(players[player_id].get("position")),
                "points": points,
            }
        )
    return lines


def latest_development_month_for_team(save: dict[str, Any], team_id: str) -> str:
    season_start = season_start_year_for_app(save_active_contract_season(save))
    first_month = f"{season_start}-10"
    last_month = f"{season_start + 1}-06"
    months = [
        str(event.get("month") or event.get("date") or "")[:7]
        for event in save.get("development_events", [])
        if event.get("team_id") == team_id
        and first_month <= str(event.get("month") or event.get("date") or "")[:7] <= last_month
    ]
    return max(months) if months else ""


def composite_rating(attrs: dict[str, Any], keys: list[str], weights: list[float]) -> float:
    total = 0.0
    weight_total = 0.0
    for key, weight in zip(keys, weights):
        value = attrs.get(key)
        if value is None:
            continue
        total += float(value) * float(weight)
        weight_total += float(weight)
    return round(total / weight_total, 1) if weight_total else 0.0


def set_starting_five_action(root: Path, canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    if team.get("id") != save.get("meta", {}).get("user_team_id"):
        return {"status": "blocked", "reason": "Only the user team's Starting 5 can be edited."}
    if payload.get("auto"):
        save.setdefault("starting_lineups", {}).pop(team["id"], None)
        starting_lineup_slots(active, save, team["id"], persist=True)
        write_save(save_path, save)
        return {"status": "updated", "dashboard": team_dashboard(root, canonical, save_path, team["abbrev"])}
    roster_ids = {player.get("id") for player in active.get("players", []) if player.get("team_id") == team["id"]}
    raw_slots = payload.get("slots") or {}
    if not isinstance(raw_slots, dict):
        raise AppActionError("Starting 5 slots must be a slot-to-player dictionary.")
    cleaned: dict[str, str] = {}
    used: set[str] = set()
    for slot in ["1", "2", "3", "4", "5"]:
        player_id = raw_slots.get(slot) or raw_slots.get(int(slot))
        if not player_id:
            continue
        player_id = str(player_id)
        if player_id not in roster_ids:
            raise AppActionError(f"Player {player_id!r} is not on {team['abbrev']}.")
        if player_id in used:
            raise AppActionError("A player cannot occupy multiple Starting 5 slots.")
        cleaned[slot] = player_id
        used.add(player_id)
    if len(cleaned) < 5:
        return {"status": "blocked", "reason": "Choose all five starters before saving the Starting 5."}
    save.setdefault("starting_lineups", {})[team["id"]] = {
        "slots": cleaned,
        "source": "user",
        "updated_date": save.get("state", {}).get("current_date"),
    }
    starting_lineup_slots(active, save, team["id"], persist=True)
    write_save(save_path, save)
    return {"status": "updated", "dashboard": team_dashboard(root, canonical, save_path, team["abbrev"])}


def set_rotation_minutes_action(root: Path, canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    if team.get("id") != save.get("meta", {}).get("user_team_id"):
        return {"status": "blocked", "reason": "Only the user team's rotation can be edited."}
    raw_minutes = payload.get("minutes") or {}
    if not isinstance(raw_minutes, dict):
        raise AppActionError("Rotation minutes must be a player-to-minutes dictionary.")
    roster = {player["id"]: player for player in active.get("players", []) if player.get("team_id") == team["id"]}
    health_by_player = {state.get("player_id"): state for state in save.get("health_states", [])}
    injured_ids = {
        player_id
        for player_id in roster
        if player_unavailable_for_rotation(health_by_player.get(player_id))
    }
    # Players the GM is resting keep their minutes target for when they return (set_player_rest).
    previous_override = dict((save.get("rotation_overrides") or {}).get(team["id"]) or {})
    previous_locked = set((save.get("rotation_locked_player_ids") or {}).get(team["id"]) or [])
    gm_rested = {player_id for player_id in roster if (health_by_player.get(player_id) or {}).get("user_rest")}
    cleaned: dict[str, int] = {}
    for player_id, value in raw_minutes.items():
        player_id = str(player_id)
        if player_id not in roster:
            raise AppActionError(f"Player {player_id!r} is not on {team['abbrev']}.")
        minutes = int(round(float(value)))
        if minutes < 0 or minutes > 48:
            raise AppActionError("Each player must be between 0 and 48 minutes.")
        cleaned[player_id] = 0 if player_id in injured_ids else minutes
    submitted_total = sum(int(round(float(value))) for value in raw_minutes.values())
    if submitted_total != 240:
        return {"status": "blocked", "reason": "Rotation minutes must total exactly 240.", "total_minutes": submitted_total, "remaining_minutes": 240 - submitted_total}
    locked_ids = payload.get("locked_player_ids", list(cleaned))
    if not isinstance(locked_ids, list) or any(player_id not in roster for player_id in locked_ids):
        raise AppActionError("Locked minutes must reference players on your team.")
    locked_ids = list(dict.fromkeys(player_id for player_id in locked_ids if player_id not in injured_ids))
    if not locked_ids:
        save.setdefault("rotation_overrides", {}).pop(team["id"], None)
        save.setdefault("rotation_locked_player_ids", {})[team["id"]] = []
        automatic = team_rotation_projection(active, save, team["id"], integer=True)
        automatic_total = sum(int(round(automatic.get(player_id, 0.0))) for player_id in roster)
        if automatic_total != 240:
            return {
                "status": "blocked",
                "reason": "There are not enough healthy players to assign all 240 minutes.",
                "total_minutes": automatic_total,
                "remaining_minutes": 240 - automatic_total,
            }
        write_save(save_path, save)
        return {
            "status": "updated",
            "total_minutes": automatic_total,
            "dashboard": team_dashboard(root, canonical, save_path, team["abbrev"]),
        }
    save.setdefault("rotation_overrides", {})[team["id"]] = {
        player_id: cleaned.get(player_id, 0)
        for player_id in roster
    }
    redistributed = team_rotation_projection(active, save, team["id"], integer=True)
    redistributed_total = sum(int(round(redistributed.get(player_id, 0.0))) for player_id in roster)
    if redistributed_total != 240:
        return {
            "status": "blocked",
            "reason": "There are not enough healthy players to assign all 240 minutes.",
            "total_minutes": redistributed_total,
            "remaining_minutes": 240 - redistributed_total,
        }
    save["rotation_overrides"][team["id"]] = {
        player_id: int(round(redistributed.get(player_id, 0.0)))
        for player_id in roster
    }
    for player_id in gm_rested:
        if previous_override.get(player_id):
            save["rotation_overrides"][team["id"]][player_id] = int(previous_override[player_id])
            if player_id in previous_locked and player_id not in locked_ids:
                locked_ids.append(player_id)
    recommendations = save.setdefault("rotation_recommendations", {})
    save.setdefault("rotation_locked_player_ids", {})[team["id"]] = locked_ids
    for player_id in roster:
        recommendations.pop(player_id, None)
    write_save(save_path, save)
    return {
        "status": "updated",
        "total_minutes": redistributed_total,
        "dashboard": team_dashboard(root, canonical, save_path, team["abbrev"]),
    }


USER_REST_MAX_GAMES = 5


def set_player_rest_action(root: Path, canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Rest one of the GM's players for his team's next N games (1-5), or cancel it (games 0). His minutes target is
    kept; while he sits, the coach places his minutes (absence fill) and he recovers fatigue like any day off."""
    from .health import default_state_dict
    from .save import AWARD_MIN_GAMES, award_games_max
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team_id = str(save.get("meta", {}).get("user_team_id") or "")
    player_id = str(payload.get("player_id") or "")
    active = canonical_with_save(canonical, save)
    player = next((p for p in active.get("players", []) if p.get("id") == player_id), None)
    if not player or player.get("team_id") != team_id:
        raise AppActionError("Only players on your team can be rested.")
    try:
        games = int(payload.get("games") or 0)
    except (TypeError, ValueError) as error:
        raise AppActionError("Rest length must be a number of games.") from error
    if games < 0 or games > USER_REST_MAX_GAMES:
        raise AppActionError(f"Rest a player for 1 to {USER_REST_MAX_GAMES} games (0 cancels).")
    current = str(save.get("state", {}).get("current_date") or "")
    states = save.setdefault("health_states", [])
    state = next((row for row in states if row.get("player_id") == player_id), None)
    if games and state and str(state.get("availability_status") or "active") != "active":
        return {"status": "blocked", "reason": f"{player.get('name')} is injured and already out."}
    if state is None:
        state = default_state_dict(player_id, current or "2026-10-01")
        states.append(state)
    if games:
        state["user_rest"] = {"games_left": games, "games": games, "since": current, "team_id": team_id}
        state.pop("rest_suggestion", None)
    else:
        state.pop("user_rest", None)
    warning = ""
    if games and save.get("state", {}).get("phase") == "regular_season":
        record = (save.get("team_records") or {}).get(team_id, {})
        team_games = int(record.get("wins", 0)) + int(record.get("losses", 0))
        played = int(((save.get("player_season_stats") or {}).get(player_id) or {}).get("games") or 0)
        reach_after = award_games_max(played, team_games, state)
        reach_before = reach_after + games
        if reach_after < AWARD_MIN_GAMES <= reach_before:
            warning = (f"{player.get('name')} can now play at most {reach_after} games this season: below the "
                       f"{AWARD_MIN_GAMES} games needed for season awards.")
        elif reach_after < AWARD_MIN_GAMES:
            warning = f"{player.get('name')} can no longer reach the {AWARD_MIN_GAMES} games needed for season awards."
    write_save(save_path, save)
    return {
        "status": "updated",
        "player_id": player_id,
        "games": games,
        "warning": warning,
        "dashboard": team_dashboard(root, canonical, save_path, team_abbrev_for_id(active, team_id)),
    }


def team_abbrev_for_id(canonical: dict[str, Any], team_id: str) -> str:
    return next((team["abbrev"] for team in canonical.get("teams", []) if team.get("id") == team_id), "")


def extension_room_payload(
    canonical: dict[str, Any],
    save_path: Path,
    team_query: str,
    player_id: Any = None,
) -> dict[str, Any]:
    """Return cap-aware extension choices without creating pending state."""
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, team_query)
    user_team_id = str(save.get("meta", {}).get("user_team_id") or "")
    if str(team.get("id") or "") != user_team_id:
        raise AppActionError("Contract extensions can only be negotiated for the user-controlled team.")

    current = str(save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
    phase = str(save.get("state", {}).get("phase") or "")
    legal = "extensions" in set(save_legal_actions_for_date(save, current))
    # Extension candidates need only the extension projections, not every free agent's suitors (same candidates, faster).
    report = extension_candidates_report(with_extension_context(active), team.get("abbrev"))
    players = {str(player.get("id")): player for player in active.get("players", [])}
    requested_id = str(player_id or "")
    # The seed submit_extension_offer_action uses when the app sends none (the app never does).
    room_seed = int(save.get("meta", {}).get("seed") or 1)
    team_rows: dict[str, dict[str, Any]] = {}
    # One shared cache for the league tax-pool projection (payroll facts per team and season).
    tax_context = dict(active, _trade_financial_facts={})

    def team_cap_rows(season: str) -> dict[str, Any]:
        if season not in team_rows:
            team_rows[season] = extension_team_cap_row(tax_context, save, team["id"], season)
        return dict(team_rows[season])

    candidates: list[dict[str, Any]] = []
    for candidate in report.get("candidates", []):
        candidate_id = str(candidate.get("player_id") or candidate.get("id") or "")
        if requested_id and candidate_id != requested_id:
            continue
        player = players.get(candidate_id)
        if not player:
            continue
        start_season = effective_extension_start_season(active, player, current)
        safe_years = extension_safe_year_limit_for_app(player, start_season, 5)
        max_aav_by_years = {
            str(years): extension_max_legal_aav_for_app(active, save, team["id"], candidate_id, start_season, years)
            for years in range(1, safe_years + 1)
        }
        preferred_years = min(max(1, int(candidate.get("projected_years") or 3)), max(1, safe_years))
        current_year = season_start_year_for_app(save_active_contract_season(save))
        cap_rows = extension_cap_projection(active, save, team["id"], season_label_for_app(current_year), 4)
        eligible = bool(candidate.get("eligible")) and not bool(candidate.get("manual_review_required")) and safe_years > 0 and legal
        contract_seasons = list((contract_for_player(active, candidate_id) or {}).get("seasons") or [])
        # Offer-builder facts (additive), all from the rule submit_extension_offer_action applies:
        # his price from you, the market ask it starts from, and the multi-season cap table with the tax rule.
        candidate_terms = extension_offer_terms(candidate, candidate_id, room_seed)
        last_cap_year = max(current_year + 3, season_start_year_for_app(start_season) + max(1, safe_years) - 1)
        cap_table = [
            {
                **team_cap_rows(season_label_for_app(year)),
                "player_salary_millions": round(sum(
                    float(row.get("salary") or 0.0) for row in contract_seasons if str(row.get("season")) == season_label_for_app(year)
                ) / 1_000_000, 2),
            }
            for year in range(current_year, last_cap_year + 1)
        ]
        candidates.append(
            {
                **candidate,
                **candidate_terms,
                "cap_table": cap_table,
                "eligibility_reason": extension_eligibility_reason(candidate, legal, safe_years),
                "player_id": candidate_id,
                "name": player.get("name") or candidate.get("name"),
                "position": player.get("position") or candidate.get("position"),
                "age": player.get("display_age", player.get("age")),
                "height": player.get("height_display") or player.get("height"),
                "eligible": eligible,
                "start_season": start_season,
                "safe_years": safe_years,
                "preferred_years": preferred_years,
                "max_aav_by_years": max_aav_by_years,
                "cap_projection": cap_rows,
                "current_contract_seasons": contract_seasons,
                "analysis": extension_analysis_payload(active, player, season_label_for_app(current_year), start_season, safe_years),
            }
        )
    candidates.sort(
        key=lambda item: (
            bool(item.get("eligible")),
            float(item.get("projected_aav_millions") or 0.0),
            str(item.get("name") or ""),
        ),
        reverse=True,
    )
    return {
        "status": "open" if legal else "closed",
        "date": current,
        "phase": phase,
        "deadline": extension_deadline_date(int(current[:4]) if current[:4].isdigit() else 2026),
        "team": team,
        "candidate_count": len(candidates),
        "candidates": candidates,
        # The limits submit_extension_offer_action checks (additive).
        "offer_rules": {
            "minimum_aav_millions": EXTENSION_MINIMUM_AAV_MILLIONS,
            "max_years": 5,
            "tax_may_be_exceeded": True,
            "limit": "hard_cap",
            "flat_salary": True,
            "options": False,
            "accept_margin_millions": EXTENSION_ACCEPT_MARGIN_MILLIONS,
        },
    }


EXTENSION_MINIMUM_AAV_MILLIONS = 1.8
EXTENSION_ACCEPT_MARGIN_MILLIONS = 0.001  # submit accepts when offer + 0.001 reaches his price


def extension_offer_terms(candidate: dict[str, Any], player_id: str, seed: int) -> dict[str, Any]:
    """His price for an extension with your team: the rule submit_extension_offer_action applies.

    The price starts from his market ask (the contract model's projected salary). His flexibility with your team
    (38 + 0.18 x team fit, plus a fixed personal swing of -15..+15 from the seed and his id, kept in 8..92) lowers
    it: he takes ``1.02 - flexibility / 260`` of the ask. Without a guarantee the price rises by the same security
    premium free agents ask (contract_protection.security_penalty). He signs when the offer reaches the price.
    """
    from .contract_protection import security_penalty

    ask = float(candidate.get("projected_aav_millions") or 0.0)
    fit = float(candidate.get("team_fit_score") or 50.0)
    flexibility = round(max(8.0, min(92.0, 38.0 + fit * 0.18 + (sum(ord(char) for char in f"{seed}:{player_id}:extension") % 31) - 15)), 1)
    lines: dict[str, float] = {}
    offers: dict[str, float] = {}
    premiums: dict[str, float] = {}
    for key, guaranteed in (("guaranteed", True), ("non_guaranteed", False)):
        security = security_penalty(candidate, guaranteed)
        line = ask * (1.02 - flexibility / 260.0)
        line *= 1 + security / 100
        lines[key] = line
        premiums[key] = security
        offers[key] = max(EXTENSION_MINIMUM_AAV_MILLIONS, smallest_extension_offer_accepted(line))
    return {
        "market_ask_millions": round(ask, 2),
        "flexibility": flexibility,
        "ask_share": round(1.02 - flexibility / 260.0, 4),
        "security_premium_pct": premiums,
        "accept_line_millions": lines,
        "accept_offer_millions": offers,
    }


def extension_offer_accepted(aav_millions: float, line: float) -> bool:
    """The comparison submit_extension_offer_action makes (offer rounded to cents first)."""
    return round(float(aav_millions), 2) + EXTENSION_ACCEPT_MARGIN_MILLIONS >= line


def smallest_offer_at_or_above(value: float, step: float = 0.1) -> float:
    """The smallest offer on the builder's $0.1M steps that is not below `value`."""
    import math

    steps = math.ceil(round(float(value) / step, 9))
    offer = round(steps * step, 1)
    # The engine compares the offer with the unrounded threshold, so never return an offer a hair below it.
    return offer if offer >= float(value) else round(offer + step, 1)


def smallest_extension_offer_accepted(line: float, step: float = 0.1) -> float:
    """The smallest offer on the builder's $0.1M steps that submit accepts for this price."""
    offer = smallest_offer_at_or_above(max(0.0, float(line) - EXTENSION_ACCEPT_MARGIN_MILLIONS), step)
    while not extension_offer_accepted(offer, line):
        offer = round(offer + step, 1)
    while offer - step > 0 and extension_offer_accepted(round(offer - step, 1), line):
        offer = round(offer - step, 1)
    return offer


def extension_team_cap_row(active: dict[str, Any], save: dict[str, Any], team_id: str, season: str) -> dict[str, Any]:
    """One season of the team's cap with the luxury-tax rule the game charges (trade_tax): the tax line, the
    bracket size and rates (repeat taxpayers pay more), and the share of the tax payout the team receives if it
    ends the season under the line, projected from today's league payrolls."""
    from . import trade_tax

    cap = team_cap_summary(active, save, team_id, season=season)
    repeater = trade_tax.is_repeat_taxpayer(active, team_id, season)
    line = float(trade_tax._tx().cap_lines_for_season(season)["tax_line"])
    return {
        "season": season,
        "salary_total_millions": cap.get("salary_total_millions"),
        "tax_line_millions": cap.get("tax_line_millions"),
        "hard_cap_millions": cap.get("hard_cap_millions"),
        "tax_space_millions": cap.get("tax_space_millions"),
        "hard_cap_space_millions": cap.get("hard_cap_space_millions"),
        "unresolved_contract_count": cap.get("unresolved_contract_count"),
        "tax_rule": {
            "line_millions": line / 1_000_000,
            "bracket_millions": line * trade_tax.BRACKET_SHARE_OF_TAX_LINE / 1_000_000,
            "rates": list(trade_tax.REPEATER_RATES if repeater else trade_tax.NON_REPEATER_RATES),
            "step_after": trade_tax.RATE_STEP_AFTER,
            "repeater": repeater,
        },
        "payout_share_if_under_millions": round(trade_tax.pool_share_if_under(active, team_id, season) / 1_000_000, 2),
    }


EXTENSION_STATUS_REASONS = {
    "original_contract_shorter_than_three_years": "Only players whose original contract ran three or more seasons can extend.",
    "not_in_extension_window": "He can extend only in the last two seasons of his contract.",
    "no_salary_seasons_remaining": "His contract has no seasons left to extend.",
    "manual_review_required": "His current contract is not fully known, so the game cannot extend it.",
    "not_extension_eligible": "He is not eligible for an extension.",
}


def extension_eligibility_reason(candidate: dict[str, Any], legal: bool, safe_years: int) -> str | None:
    """Plain words for why submit_extension_offer_action would block him (None when he can be extended)."""
    if not legal:
        return "Extensions are closed until the next window (preseason to January 15)."
    if candidate.get("manual_review_required"):
        return EXTENSION_STATUS_REASONS["manual_review_required"]
    if not candidate.get("eligible"):
        return EXTENSION_STATUS_REASONS.get(str(candidate.get("eligibility_status") or ""), EXTENSION_STATUS_REASONS["not_extension_eligible"])
    if safe_years <= 0:
        return "He plans to retire before an extension would start."
    return None


def submit_extension_offer_action(
    root: Path,
    canonical: dict[str, Any],
    save_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    player_id = str(payload.get("player_id") or "")
    if not player_id:
        raise AppActionError("Choose an extension-eligible player.")
    room = extension_room_payload(canonical, save_path, user_team_abbrev(canonical, save_path), player_id)
    candidate = next((item for item in room.get("candidates", []) if item.get("player_id") == player_id), None)
    if not candidate or not candidate.get("eligible"):
        reason = (candidate or {}).get("eligibility_status") or "The player is not currently extension eligible."
        return {"status": "blocked", "reason": str(reason), "room": room}

    years = int(payload.get("years") or candidate.get("preferred_years") or 1)
    if years < 1 or years > int(candidate.get("safe_years") or 0):
        return {"status": "blocked", "reason": "That term extends beyond the player's safe retirement window.", "room": room}
    aav_millions = round(float(payload.get("aav_millions") or 0.0), 2)
    maximum = float((candidate.get("max_aav_by_years") or {}).get(str(years)) or 0.0)
    if aav_millions < 1.8 or aav_millions > maximum + 0.001:
        return {
            "status": "blocked",
            "reason": f"Offer must be between $1.8M and ${maximum:.1f}M AAV for {years} year(s).",
            "room": room,
        }

    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = room["team"]
    current = str(save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
    seed = int(payload.get("seed") or save.get("meta", {}).get("seed") or 1)
    result = negotiate_extension(active, str(candidate.get("name") or player_id), str(team.get("abbrev")), seed=seed, max_rounds=3, date=current)
    negotiation = dict(result.get("negotiation") or {})
    ask_millions = float(candidate.get("projected_aav_millions") or 0.0)
    from .contract_protection import guarantee_choice
    guaranteed = guarantee_choice(payload.get('guaranteed', True))
    # One rule for the price shown in the extension builder and the decision here (extension_offer_terms).
    terms = extension_offer_terms(candidate, player_id, seed)
    price_key = "guaranteed" if guaranteed else "non_guaranteed"
    security = float(terms["security_premium_pct"][price_key])
    flexibility = float(terms["flexibility"])
    acceptance_line = float(terms["accept_line_millions"][price_key])
    interest = round(max(0.0, min(100.0, 50.0 + (aav_millions / max(ask_millions, 0.1) - 1.0) * 110.0 + flexibility * 0.12)), 1)
    interest = max(0.0, interest-security)
    if not extension_offer_accepted(aav_millions, acceptance_line):
        needed = smallest_extension_offer_accepted(acceptance_line)
        return {
            "status": "rejected",
            "accepted": False,
            "player_id": player_id,
            "player_name": candidate.get("name"),
            "offer": {"aav_millions": aav_millions, "years": years},
            "ask_millions": round(ask_millions, 2),
            "interest": interest,
            "needed_millions": max(EXTENSION_MINIMUM_AAV_MILLIONS, needed),
            "reason": f"He signs an extension with you from ${max(EXTENSION_MINIMUM_AAV_MILLIONS, needed):.1f}M a season{'' if guaranteed else ' without a guarantee'}; this offer is ${max(0.0, needed - aav_millions):.1f}M short.",
            "room": room,
        }

    negotiation_id = negotiation.get("id") or stable_id("contract_negotiation", "extension", current, team["id"], player_id, seed, "gui")
    offer = {
        "id": stable_id("contract_offer", negotiation_id, "gui_user", player_id, years, round(aav_millions * 1_000_000)),
        "negotiation_id": negotiation_id,
        "team_id": team["id"],
        "player_id": player_id,
        "offer_type": "extension",
        "guaranteed": guaranteed,
        "round": 1,
        "years": years,
        "start_season": candidate.get("start_season"),
        "annual_salary": aav_millions * 1_000_000,
        "total_value": aav_millions * 1_000_000 * years,
        "role_promise": "current_team_extension",
        "status": "accepted",
        "notes": "Interactive GUI extension offer.",
    }
    decision = {
        "id": stable_id("signing_decision", negotiation_id, "gui_user_extension"),
        "negotiation_id": negotiation_id,
        "player_id": player_id,
        "team_id": team["id"],
        "accepted": True,
        "decision": "accept",
        "accepted_offer": offer,
        "player_score": interest,
        "team_score": 70.0,
        "reasons": ["interactive_extension_offer_met_player_threshold"],
    }
    negotiation.update(
        {
            "id": negotiation_id,
            "player_name": candidate.get("name"),
            "player_id": player_id,
            "team_id": team["id"],
            "negotiation_type": "extension",
            "date": current,
            "offers": [offer],
            "rounds": 1,
            "status": "agreement",
            "final_decision_id": decision["id"],
            "current_contract_seasons": candidate.get("current_contract_seasons") or [],
        }
    )
    pending = {"negotiation": negotiation, "decision": decision, "accepted": True}
    save.setdefault("pending_contract_negotiations", []).append(pending)
    write_save(save_path, save)
    applied = apply_contract_to_save(save_path, negotiation_id, date=current)
    if applied.get("status") != "applied":
        return {"status": "not_applied", "reason": applied.get("notes") or applied.get("status"), "apply_result": applied}
    return {
        "status": "applied",
        "accepted": True,
        "player_id": player_id,
        "player_name": candidate.get("name"),
        "offer": {"aav_millions": aav_millions, "years": years, "start_season": candidate.get("start_season")},
        "apply_result": applied,
        "dashboard": team_dashboard(root, canonical, save_path, str(team.get("abbrev"))),
    }


def effective_extension_start_season(active: dict[str, Any], player: dict[str, Any], current: str) -> str:
    base = extension_start_season_from_date_save(current)
    start = season_start_year_for_app(base)
    paid_years = [
        season_start_year_for_app(str(row.get("season")))
        for row in (contract_for_player(active, str(player.get("id"))) or {}).get("seasons", [])
        if row.get("season") and float(row.get("salary") or 0.0) > 0
    ]
    if paid_years:
        start = max(start, max(paid_years) + 1)
    return season_label_for_app(start)


def extension_safe_year_limit_for_app(player: dict[str, Any], start_season: str, max_years: int) -> int:
    start = season_start_year_for_app(start_season)
    retirement_start = projected_retirement_start_year(player, start)
    return max_years if retirement_start is None else max(0, min(max_years, retirement_start - start))


def extension_max_legal_aav_for_app(
    active: dict[str, Any], save: dict[str, Any], team_id: str, player_id: str, start_season: str, years: int
) -> float:
    start = season_start_year_for_app(start_season)
    spaces: list[float] = []
    contract = contract_for_player(active, player_id) or {}
    salary_by_season = {str(row.get("season")): float(row.get("salary") or 0.0) / 1_000_000 for row in contract.get("seasons", [])}
    for offset in range(max(1, years)):
        season = season_label_for_app(start + offset)
        cap = team_cap_summary(active, save, team_id, season=season)
        spaces.append(max(0.0, float(cap.get("hard_cap_space_millions") or 0.0) + salary_by_season.get(season, 0.0)))
    return round(min(spaces) if spaces else 0.0, 2)


def extension_cap_projection(active: dict[str, Any], save: dict[str, Any], team_id: str, start_season: str, years: int) -> list[dict[str, Any]]:
    start = season_start_year_for_app(start_season)
    return [
        {
            "season": season_label_for_app(start + offset),
            **team_cap_summary(active, save, team_id, season=season_label_for_app(start + offset)),
        }
        for offset in range(years)
    ]


def season_start_year_for_app(season: str) -> int:
    try:
        return int(str(season).split("-")[0])
    except (TypeError, ValueError):
        return 2026


def season_label_for_app(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def roster_cutdown_payload(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    from .contract_protection import waiver_projection
    from .waivers import buyout_quote
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    refresh_roster_cutdowns(canonical, save, apply_ai=False)
    active = canonical_with_save(canonical, save)
    team_id = save.get("meta", {}).get("user_team_id")
    team = team_by_id(active, str(team_id))
    pending = next((item for item in save.get("pending_roster_cutdowns", []) if item.get("team_id") == team_id), None)
    protected = recent_rookie_protected_player_ids(save)
    health_by_player = {row.get("player_id"): row for row in save.get("health_states", [])}
    rows = []
    for player in active.get("players", []):
        if player.get("team_id") != team_id:
            continue
        attrs = player_display_attribute_summary(active, player["id"])
        rows.append(
            {
                "player_id": player["id"],
                "name": player.get("name"),
                "position": player.get("position"),
                "age": player.get("display_age", player.get("age")),
                "height": player.get("height_display") or player.get("height") or height_label(player),
                "headshot_url": player.get("headshot_url"),
                "minutes": round(display_minutes_projection(player), 1),
                "overall": round(float(attrs.get("overall") or 0.0), 1),
                "health": player_health_label(health_by_player.get(player["id"]), save.get("state", {}).get("current_date")),
                "salary_by_year": player_salary_table(active, player["id"]),
                "can_waive": True,
                "waiver": waiver_projection(active, save, player, team_id),
                "buyout": buyout_quote(active, save, player, team_id),
                "protected_reason": "Recent draftees receive a retention preference in automatic roster cutdowns." if player["id"] in protected else "",
            }
        )
    rows.sort(key=lambda row: (row["can_waive"], float(row["minutes"]), float(row["overall"]), str(row["name"])), reverse=False)
    return {
        "status": "required" if pending else "clear",
        "date": save.get("state", {}).get("current_date"),
        "team": team,
        "pending": pending,
        "current_count": len(rows),
        "target_count": int((pending or {}).get("target_count") or 15),
        "players": rows,
    }


def waive_player_action(root: Path, canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], *, buyout: bool = False) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team_id = save.get("meta", {}).get("user_team_id")
    team = team_by_id(active, str(team_id))
    player_id = str(payload.get("player_id") or "")
    player = next((row for row in active.get("players", []) if row.get("id") == player_id), None)
    if not player or player.get("team_id") != team_id:
        raise AppActionError("That player is not on the user-controlled roster.")
    date_value = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    from .waivers import request_waiver
    obligation = request_waiver(active, save, player, team_id, date_value, buyout=buyout)
    save.setdefault("rotation_recommendations", {}).pop(player_id, None)
    save.setdefault("rotation_snapshots", {}).pop(team_id, None)
    save.setdefault("starting_lineups", {}).pop(team_id, None)
    add_news(save, "roster_cut", f"{team.get('abbrev')} waived {player.get('name')} to reach the roster limit.", date_value=date_value)
    save.setdefault("transaction_logs", []).append(
        {
            "id": stable_id("transaction_log", "roster_cut", date_value, team_id, player_id),
            "date": date_value,
            "transaction_type": "buyout" if buyout else "roster_cut",
            "proposal_id": stable_id("roster_cut", date_value, team_id, player_id),
            "status": "applied_to_save_ledger",
            "teams": [team_id],
            "assets": {"player_id": player_id, "name": player.get("name"), "waived_by_team_id": team_id},
            "evaluations": [],
            "source_ids": ["src_contract_market_config_v1"],
            "notes": "GUI roster cut applied through the shared application-action boundary.",
        }
    )
    prune_trade_offers_touching_assets(save, {f"player:{player_id}"})
    refresh_roster_cutdowns(canonical, save)
    write_save(save_path, save)
    return {
        "status": "waived",
        "waiver": obligation,
        "player_id": player_id,
        "player_name": player.get("name"),
        "room": roster_cutdown_payload(canonical, save_path),
        "home": home_payload(root, canonical, save_path),
    }


def waiver_room_payload(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    from .waivers import claim_plan, priority, buyout_quote
    saved = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, saved)
    tid = saved['meta']['user_team_id']
    roster = [{'id': p['id'], 'name': p['name'], 'buyout': buyout_quote(active, saved, p, tid)}
              for p in active['players'] if p.get('team_id') == tid]
    rows = []
    for entry in saved.get('waiver_wire', []):
        if entry['status'] != 'pending':
            continue
        options = []
        for cut in [None] + [p['id'] for p in roster]:
            plan = claim_plan(active, saved, entry, tid, cut_id=cut)
            if plan['ok']:
                options.append({'cut_player_id': cut, 'cut_cost_millions': plan['cut_cost_millions']})
        rows.append({'id': entry['id'], 'player_name': entry['player_name'], 'clearance_date': entry['clearance_date'],
                     'contract': entry['contract'].get('seasons', []), 'options': options,
                     'claimed': any(c['team_id'] == tid for c in entry['claims'])})
    return {'players': rows, 'roster': roster, 'priority': priority(active, saved, saved['state']['current_date'])}


def free_agent_offer_floors(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any],
                            team: dict[str, Any], safe_years: int) -> dict[str, Any]:
    """The salary your offer must reach today for this free agent to sign it, for each length and guarantee.

    The rule `play.manual_save_pool_signing` applies (TRADE-VOLUME; a test keeps them equal): the same rule as the AI
    teams' bids. His interest in your offer (salary against his market ask, years, your team's context) must reach his
    bar today and beat the best rival bid. None: no salary wins him from you today.
    """
    from .play import user_offer_contexts, user_offer_floor, user_offer_market_terms

    terms = user_offer_market_terms(active, save, player, team)
    contexts = user_offer_contexts(active, save, player, team)
    by_years: dict[str, dict[str, float | None]] = {"guaranteed": {}, "non_guaranteed": {}}
    for years in range(1, 6):
        context = contexts[years]
        for key, guaranteed in (("guaranteed", True), ("non_guaranteed", False)):
            by_years[key][str(years)] = user_offer_floor(player, years, guaranteed, terms, context)
    default_years = str(max(1, min(4, safe_years or 1)))
    best = terms.get("best_rival")
    return {
        "by_years": by_years,
        "default": {key: by_years[key][default_years] for key in by_years},
        "rule": {"mode": terms["mode"], "bar": terms["bar"], "ask_millions": terms["ask_millions"],
                 "preferred_years": terms["preferred_years"],
                 "best_rival": ({**best, "team_abbrev": team_id_to_abbrev(best["team_id"])} if best else None)},
    }


def free_agency_room_payload(
    canonical: dict[str, Any],
    save_path: Path,
    team_query: str,
    seed: int = 1,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    phase = str((save.get("state") or {}).get("phase") or "")
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    team = resolve_team(active, team_query)
    report_by_id = {
        str(item.get("player_id") or item.get("id")): {
            **item,
            "projected_aav_millions": round(float(item.get("projected_aav") or 0.0) / 1_000_000, 2),
        }
        for item in canonical.get("free_agent_candidates", [])
        if item.get("player_id") or item.get("id")
    }
    stats = save.get("player_season_stats", {})
    players_by_id = {player["id"]: player for player in active.get("players", [])}
    teams_by_id = {team["id"]: team for team in active.get("teams", [])}
    valuations_by_id = {
        str(item.get("player_id")): item
        for item in active.get("player_asset_valuations", [])
        if item.get("player_id")
    }
    active_offers = [offer for offer in save.get("free_agent_offers", []) if offer.get("status") == "active"]
    state = save.get("free_agency_state") or {}
    ask_changes = state.get("player_ask_changes_millions") or {}
    offers_by_player: dict[str, list[dict[str, Any]]] = {}
    for offer in active_offers:
        offers_by_player.setdefault(str(offer.get("player_id") or ""), []).append(offer)
    pool_ids = list(save.get("free_agent_player_ids") or report_by_id.keys())
    from .waivers import pending_ids
    pool_ids = [pid for pid in pool_ids if pid not in pending_ids(save)]
    team_rotation = [
        player
        for player in active.get("players", [])
        if player.get("team_id") == team["id"] and display_minutes_projection(player) > 0
    ]
    team_position_counts: dict[str, int] = {}
    for roster_player in team_rotation:
        position = compact_position(roster_player.get("position"))
        team_position_counts[position] = team_position_counts.get(position, 0) + 1
    likely_team_ids_by_player = {
        player_id: {str(team_id) for team_id in market.get("likely_suitors", [])}
        for player_id, market in report_by_id.items()
    }
    from .play import contract_start_season_for_signing, extension_safe_year_limit, free_agency_accept_threshold
    from .release_planning import reacquisition_blocked
    signing_season = contract_start_season_for_signing(save)
    market_day = int(state.get("day") or 1)
    current_date = str((save.get("state") or {}).get("current_date") or "")
    health_by_player = {row.get("player_id"): row for row in save.get("health_states", [])}
    from . import cap_ledger
    ledger_payroll = cap_ledger.team_payroll(active, save, team["id"], signing_season, include_reservations=True)
    candidates = []
    for player_id in pool_ids:
        player = players_by_id.get(player_id)
        if not player:
            continue
        market = report_by_id.get(player_id) or {}
        attrs = player_display_attribute_summary(active, player_id)
        totals = stats.get(player_id, {})
        games = int(totals.get("games") or 0)
        divisor = max(1, games)
        # (the market ask comes from the engine rule below: floors["rule"]["ask_millions"])
        offers = offers_by_player.get(str(player_id), [])
        best_offer = max(
            offers,
            key=lambda item: (float(item.get("interest_score") or 0.0), float(item.get("aav_millions") or 0.0)),
            default=None,
        )
        ratings = dict(attrs)
        # Spacing is the engine's own value (player_attribute_summary), not a separate composite (rule 4).
        ratings["spacing"] = round(float(attrs.get("spacing") or attrs.get("range") or attrs.get("shooting") or 50.0), 1)
        valuation = valuations_by_id.get(str(player_id)) or fallback_asset_valuation(player)
        position = compact_position(player.get("position"))
        overall = float(ratings.get("overall") or 50.0)
        position_depth = team_position_counts.get(position, 0)
        projected_fit = 50.0 + (overall - 60.0) * 0.55 + max(-6.0, min(8.0, (2 - position_depth) * 3.0))
        if team["id"] in likely_team_ids_by_player.get(str(player_id), set()):
            projected_fit += 6.0
        projected_fit = round(max(1.0, min(99.0, projected_fit)), 1)
        best_team = teams_by_id.get((best_offer or {}).get("team_id"), {})
        safe_years = extension_safe_year_limit(player, signing_season, 5)
        floors = free_agent_offer_floors(active, save, player, team, safe_years)
        legal = free_agent_legal_terms(active, save, player, team, ledger_payroll, floors)
        candidates.append(
            {
                "id": player_id,
                "player_id": player_id,
                "name": player.get("name"),
                "position": position,
                "age": player.get("display_age", player.get("age")),
                "height": height_label(player),
                "mpg": display_minutes_projection(player),
                "games": games,
                "previous_mpg": round(float(totals.get("minutes") or 0.0) / divisor, 1) if totals else 0.0,
                "ppg": round(float(totals.get("points") or 0.0) / divisor, 1) if totals else 0.0,
                "rpg": round(float(totals.get("rebounds") or 0.0) / divisor, 1) if totals else 0.0,
                "apg": round(float(totals.get("assists") or 0.0) / divisor, 1) if totals else 0.0,
                "spg": round(float(totals.get("steals") or 0.0) / divisor, 1) if totals else 0.0,
                "bpg": round(float(totals.get("blocks") or 0.0) / divisor, 1) if totals else 0.0,
                "topg": round(float(totals.get("turnovers") or 0.0) / divisor, 1) if totals else 0.0,
                "fta_per_game": round(float(totals.get("fta") or 0.0) / divisor, 1) if totals else 0.0,
                "ft_pct": round(float(totals.get("ftm") or 0.0) / max(1.0, float(totals.get("fta") or 0.0)) * 100.0, 1) if totals else 0.0,
                "health_risk": round(float(valuation.get("health_risk") or 0.0), 1),
                "injury_body": injury_body_compact(active, player),
                "upside_remaining": round(max(0.0, min(5.0, float(valuation.get("development_upside") or 0.0) / 22.0 * 5.0)), 1),
                "trade_value": round(market_trade_target_value(player, valuation), 1),
                "ask_millions": floors["rule"]["ask_millions"],   # the ask rival bids and your offer are judged against
                "ask_change_millions": round(float(ask_changes.get(player_id) or 0.0), 1),
                "team_fit_score": projected_fit,
                "ratings": ratings,
                "snapshot": top_trait_snapshot(ratings),
                "offer_count": len(offers),
                "highest_offer": {
                    "team_id": (best_offer or {}).get("team_id"),
                    "team_abbrev": best_team.get("abbrev") or (team_id_to_abbrev((best_offer or {}).get("team_id")) if best_offer else None),
                    "aav_millions": float((best_offer or {}).get("aav_millions") or 0.0),
                    "years": int((best_offer or {}).get("years") or 0),
                    "interest_score": float((best_offer or {}).get("interest_score") or 0.0),
                    "source": (best_offer or {}).get("source"),
                } if best_offer else None,
                # Offer-builder facts, all from the engine's own signing rules (additive fields):
                "headshot_url": player.get("headshot_url"),
                "health": player_health_label(health_by_player.get(player_id), current_date),
                # What your offer must reach today for him to sign (the rule manual_save_pool_signing applies, the same
                # as the AI bids': today's bar and the best rival bid). The two top fields are for the builder's
                # default length (up to 4 years); accept_floor_by_years has every length. None: no salary wins him.
                "accept_floor_millions": floors["default"],
                "accept_floor_offer_millions": floors["default"],
                "accept_floor_by_years": floors["by_years"],
                "offer_rule": floors["rule"],
                # Longest contract that ends before his projected retirement (longer offers are refused).
                "safe_years": safe_years,
                # Interest a rival bid needs today before he signs it at the end of the day (AI market only).
                "sign_bar_today": float(free_agency_accept_threshold(player, market_day)),
                "signing_blocked_reason": (
                    "Your team released him and stretched the salary; you cannot sign him again yet."
                    if reacquisition_blocked(save, team["id"], player_id, current_date) else None
                ),
                # FA-REAL: his legal salary range and how your team would pay at his price (cap_ledger.quote).
                "legal": legal,
            }
        )
    candidates.sort(key=lambda item: (float(item.get("mpg") or 0), float((item.get("ratings") or {}).get("overall") or 0), float(item.get("ask_millions") or 0)), reverse=True)
    from .play import free_agency_bidding_wars, league_minimum_aav_millions

    re_signing_rights = [
        right for right in save.get("re_signing_rights", [])
        if right.get("team_id") == team["id"]
        and right.get("status") == "exclusive_review_window"
        and right.get("season") == save.get("meta", {}).get("season")
    ]
    right_ids = {str(right.get("player_id") or "") for right in re_signing_rights}
    own_candidates = [candidate for candidate in candidates if candidate["id"] in right_ids]
    # KEEP-STARS: what the team's Bird rights allow for each of its own free agents (re-signing room text).
    from .contract_ai import bird_rights_text
    from .play import incumbent_bird_rights
    for candidate in candidates:
        bird = incumbent_bird_rights(active, save, players_by_id.get(candidate["id"], {"id": candidate["id"]}), team["id"])
        if bird:
            candidate["bird_rights"] = {
                "level": bird["level"], "seasons": bird["seasons"], "max_years": bird["max_years"],
                "raise_pct": round(bird["raise"] * 100), "limit_millions": round(bird["limit"] / 1_000_000, 1),
                "text": bird_rights_text(bird),
            }
    cap = team_cap_summary(active, save, team["id"], season=contract_start_season_for_signing(save))
    # FA-REAL: the largest first-year salary any legal route allows today (room or an exception balance; Bird rights
    # and each player's own limits are on his candidate row: candidate.legal).
    biggest = max([float(ledger_payroll["cap_room"])] + [
        float(v["balance"]) for v in ledger_payroll["exceptions"].values() if v["available"]])
    cap["max_offer_aav_millions"] = round(max(league_minimum_aav_millions(), biggest / 1_000_000), 1)
    active_season = str(save.get("meta", {}).get("season") or CANONICAL_SEASON)
    cap_by_year = {
        season_label_for_app(season_start_year_for_app(active_season) + offset): team_cap_summary(
            active,
            save,
            team["id"],
            season=season_label_for_app(season_start_year_for_app(active_season) + offset),
        )
        for offset in range(6)
    }
    signing_events = league_events_view(
        canonical,
        save_path,
        limit=30,
        kind="transactions",
        prepared_save=save,
    ).get("events", [])
    recent_signings = []
    for source_event in signing_events:
        if str(source_event.get("kind") or "") not in {"free_agent_signing", "free_agency_signing", "free_agency"}:
            continue
        event = dict(source_event)
        details = dict(event.get("details") or {})
        player_id = str(details.get("player_id") or next(iter(event.get("player_ids") or []), ""))
        player = players_by_id.get(player_id, {})
        contract = (save.get("contract_overrides") or {}).get(player_id, {})
        contract_seasons = list(contract.get("seasons") or [])
        details["player_name"] = player.get("name") or details.get("player_name")
        details["years"] = int(details.get("years") or len(contract_seasons) or 1)
        event["details"] = details
        recent_signings.append(event)
        if len(recent_signings) >= 8:
            break
    # League moves for the signing wire: every recorded transaction (signings, trades, releases), newest first.
    league_moves = []
    for source_event in signing_events:
        details = dict(source_event.get("details") or {})
        player_id = str(details.get("player_id") or next(iter(source_event.get("player_ids") or []), ""))
        contract_seasons = list(((save.get("contract_overrides") or {}).get(player_id) or {}).get("seasons") or [])
        kind = str(source_event.get("kind") or "")
        league_moves.append({
            "date": source_event.get("date"),
            "kind": kind,
            "headline": source_event.get("headline"),
            "team_ids": list(source_event.get("team_ids") or []),
            "player_id": player_id or None,
            "player_name": (players_by_id.get(player_id) or {}).get("name") or details.get("player_name"),
            "aav_millions": float(details.get("aav_millions") or 0.0) or None,
            "years": int(details.get("years") or (len(contract_seasons) if kind in {"free_agent_signing", "free_agency_signing", "free_agency"} else 0) or 0) or None,
        })
    user_team_id = team["id"]
    user_offer_history = []
    for item in save.get("pending_contract_negotiations", []) or []:
        negotiation = item.get("negotiation") or {}
        decision = item.get("decision") or {}
        if negotiation.get("team_id") != user_team_id or negotiation.get("negotiation_type") != "free_agent_signing":
            continue
        if str(negotiation.get("date") or "") < f"{season_start_year_for_app(signing_season) - 1}-06-01":
            continue
        offer = next(iter(negotiation.get("offers") or []), {})
        user_offer_history.append({
            "date": negotiation.get("date"),
            "player_id": negotiation.get("player_id"),
            "player_name": negotiation.get("player_name"),
            "aav_millions": round(float(offer.get("annual_salary") or 0.0) / 1_000_000, 2),
            "years": int(offer.get("years") or 0),
            "guaranteed": offer.get("guaranteed", True),
            "accepted": bool(decision.get("accepted")),
            "decision": decision.get("decision"),
            "needed_millions": decision.get("ask_threshold_millions"),
        })
    user_offer_history.sort(key=lambda row: str(row.get("date") or ""), reverse=True)
    roster_count = sum(1 for player in active.get("players", []) if player.get("team_id") == team["id"])
    return {
        "signing_season": signing_season,
        "roster_count": roster_count,
        # The save's date: the signing wire never shows a move as happening after it (HONEST-EXTENSIONS).
        "as_of_date": current_date,
        # The rules submit_free_agent_offer applies (signing_cap_check, manual_save_pool_signing, apply_contract).
        "offer_rules": {
            "minimum_aav_millions": league_minimum_aav_millions(),
            "allow_tax_exceed": phase == "re_signing",
            "max_years": 5,            # with full Bird rights (candidate.bird_rights.max_years)
            "outside_max_years": 4,    # every other free agent (KEEP-STARS)
            "flat_salary": False,      # FA-REAL: raises off year one (5%, or 8% with Bird rights), saved year by year
            "max_raise_pct": 5,
            "bird_max_raise_pct": 8,
            "routes": [{"route": r, "label": cap_ledger.ROUTE_LABELS[r], "short": cap_ledger.ROUTE_SHORT[r]}
                       for r in cap_ledger.ROUTES],
            "options_available": False,
            "non_guaranteed_until": "January 10 of each season",
            # Rosters are cut to this before opening night (save.ROSTER_SEASON_MAXIMUM); "Fits our room" counts it.
            "season_roster_maximum": ROSTER_SEASON_MAXIMUM,
            "blocked_reason": (
                "Waived salary requires review before spending more salary room."
                if cap.get("unresolved_waived_contract_count") else None
            ),
        },
        "league_moves": league_moves[:30],
        "user_offer_history": user_offer_history[:20],
        "team": team,
        "phase": phase,
        "state": state,
        "cap": cap,
        "cap_by_year": cap_by_year,
        # FA-REAL: the money calculator's view of your books (holds, exceptions, hard cap, renounce previews).
        "cap_ledger": free_agency_ledger_view(active, save, team["id"], ledger_payroll),
        "rating_tertiles": display_rating_tertiles(active),
        "candidates": (own_candidates if phase == "re_signing" else candidates)[:80],
        "re_signing": {
            "active": phase == "re_signing" and state.get("re_signing_status") != "completed",
            "day": int(state.get("re_signing_day") or 1),
            "day_count": int(state.get("re_signing_day_count") or 2),
            "status": state.get("re_signing_status") or "active",
            "candidate_count": len(own_candidates),
            "candidate_ids": sorted(right_ids),
        },
        "active_offers": active_offers,
        "user_offers": [offer for offer in active_offers if offer.get("source") == "user"],
        "bidding_wars": free_agency_bidding_wars(canonical, save, limit=6),
        "recent_signings": recent_signings,
    }


def submit_free_agent_offer_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from .play import manual_save_pool_signing, signing_cap_check

    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team_query = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    team = resolve_team(active, team_query)
    player_id = str(payload.get("player_id") or payload.get("id"))
    player = next((item for item in active.get("players", []) if item.get("id") == player_id), None)
    if not player:
        raise AppActionError(f"No free agent found with id {player_id!r}.")
    years = max(1, min(5, int(payload.get("years") or 1)))
    aav = float(payload.get("aav_millions") or payload.get("aav") or 0.0)
    re_signing_phase = str((save.get("state") or {}).get("phase") or "") == "re_signing"
    if re_signing_phase and not any(
        right.get("team_id") == team["id"]
        and right.get("player_id") == player_id
        and right.get("status") == "exclusive_review_window"
        for right in save.get("re_signing_rights", [])
    ):
        return {"status": "blocked", "reason": "Only your own expiring players may negotiate during the exclusive re-signing window."}
    # KEEP-STARS: with Bird rights your own free agent can be re-signed over the cap and the hard cap, and only his
    # own team can offer a fifth year (full Bird rights). Everyone else offers at most four years.
    from .play import incumbent_bird_rights
    bird = incumbent_bird_rights(active, save, player, team["id"])
    max_years = int(bird["max_years"]) if bird else 4
    if years > max_years:
        return {"status": "blocked", "reason": (
            f"Only a team with full Bird rights can offer five years; your limit for {player.get('name')} is {max_years}.")}
    route = payload.get("route") or None
    raise_rate = offer_raise_rate(payload)
    cap = signing_cap_check(active, save, team_query, aav, bird=bird, player=player, years=years, route=route,
                            raise_rate=raise_rate)
    if not cap.get("ok"):
        return {"status": "blocked", "reason": cap.get("message"), "cap_check": quote_view(cap)}
    from .contract_protection import guarantee_choice
    guaranteed = guarantee_choice(payload.get('guaranteed', True))
    negotiation = manual_save_pool_signing(active, save_path, player, team_query, years, aav, int(payload.get("seed") or 1), guaranteed=guaranteed,
                                           route=cap.get("route"), raise_rate=raise_rate)
    result = {"status": "offered", "cap_check": quote_view(cap), "negotiation": negotiation}
    if negotiation.get("accepted") and bool(payload.get("auto_apply", False)):
        applied = apply_contract_to_save(save_path, negotiation["negotiation"]["id"], date=save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
        result["apply_result"] = applied
    return result


def offer_raise_rate(payload: dict[str, Any]) -> float | None:
    """The raise the user picked (percent of year one per year), or None for the largest legal raise."""
    value = payload.get("raise_pct")
    if value is None or value == "":
        return None
    try:
        return max(0.0, float(value)) / 100.0
    except (TypeError, ValueError):
        return None


def quote_view(check: dict[str, Any]) -> dict[str, Any]:
    """A signing quote for the screen (millions, plain words)."""
    quote = check.get("quote") or {}
    payment = quote.get("payment") or {}
    return {
        "ok": bool(check.get("ok")),
        "message": check.get("message") or "",
        "route": payment.get("route"),
        "label": payment.get("label"),
        "locks": quote.get("locks"),
        "schedule": [{"season": row["season"], "salary_millions": round(float(row["salary"]) / 1e6, 3),
                      "cap_charge_millions": round(float(row["cap_charge"]) / 1e6, 3)}
                     for row in payment.get("schedule") or []],
        "total_millions": round(sum(float(row["salary"]) for row in payment.get("schedule") or []) / 1e6, 2),
        "raise_pct": round(float(payment.get("raise_rate") or 0.0) * 100, 1),
        "trade_eligible_date": payment.get("trade_eligible_date"),
        "hard_cap": payment.get("hard_cap"),
        "cap_room_after_millions": round(float(quote["cap_room_after"]) / 1e6, 2) if quote.get("cap_room_after") is not None else None,
        "apron_after_millions": round(float(quote["apron_after"]) / 1e6, 2) if quote.get("apron_after") is not None else None,
        "max_salary_millions": round(float(quote.get("max_salary") or 0.0) / 1e6, 2),
        "min_salary_millions": round(float(quote.get("min_salary") or 0.0) / 1e6, 3),
        "routes": [{"route": r["route"], "label": r["label"], "short": r["short"], "ok": r["ok"], "reason": r["reason"]}
                   for r in quote.get("routes") or []],
    }


def free_agent_legal_terms(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], team: dict[str, Any],
                           payroll: dict[str, Any], floors: dict[str, Any]) -> dict[str, Any]:
    """His legal salary range and the way your team would pay at his price today (FA-REAL)."""
    from . import cap_ledger
    from .play import incumbent_bird_rights
    season = payroll["season"]
    service = cap_ledger.years_of_service(player, season)
    bird = incumbent_bird_rights(active, save, player, team["id"])
    previous = float((bird or {}).get("previous_salary") or 0.0) or cap_ledger.player_previous_salary(active, save, player, season)
    maximum = cap_ledger.true_max_salary(season, service, previous)
    minimum = cap_ledger.minimum_salary(season, service)
    ask = float(floors["rule"]["ask_millions"] or 0.0)
    price = max(float(floors["default"] or 0.0), ask, minimum / 1e6)
    years = 2 if (bird or {}).get("level") == "early" else 1 if price <= minimum / 1e6 + 0.1 else 3
    quote = cap_ledger.quote(active, save, team["id"], player, min(price * 1e6, maximum), years, season=season,
                             bird=bird, payroll=payroll, team_abbrev=team.get("abbrev"))
    room_cap = [float(payroll["cap_room"])] + [float(v["balance"]) for v in payroll["exceptions"].values() if v["available"]]
    reach = max(room_cap + [float((bird or {}).get("limit") or 0.0), float(minimum)])
    return {
        "min_millions": round(minimum / 1e6, 3),
        "max_millions": round(maximum / 1e6, 2),
        "most_you_can_pay_millions": round(min(maximum, reach) / 1e6, 2),
        "years_of_service": service,
        "at_price": {"salary_millions": round(min(price * 1e6, maximum) / 1e6, 2), "years": years,
                     "ok": bool(quote["ok"]), "label": (quote.get("payment") or {}).get("label"),
                     "route": quote.get("route"), "locks": quote.get("locks"), "message": quote.get("message") or ""},
    }


def free_agency_ledger_view(active: dict[str, Any], save: dict[str, Any], team_id: str,
                            payroll: dict[str, Any]) -> dict[str, Any]:
    """Your books as the cap ledger sees them: this cap year's breakdown, the table by year, and for each hold the
    room renouncing it would open."""
    from . import cap_ledger
    current = cap_ledger.summary_millions(payroll)
    for hold in current["holds"]:
        preview = cap_ledger.renounce_preview(active, save, team_id, hold["player_id"], season=payroll["season"])
        hold["renounce"] = preview if preview.get("ok") else None
    return {
        "season": payroll["season"],
        "current": current,
        "by_year": cap_ledger.cap_table(active, save, team_id, years=5),
        "words": {
            "cap_room": "Cap room: the salary cap minus your signed salaries, dead money, cap holds and a charge for "
                        "each empty spot below 12 players. Signing with cap room needs the whole first-year salary "
                        "to fit.",
            "hold": "A cap hold keeps a place on your cap for a free agent whose rights you still hold, so you can "
                    "re-sign him over the cap with Bird rights. Renouncing it frees the room but gives up those rights.",
            "mid_level": "Exceptions are yearly budgets for signing players when you are over the cap. You can split "
                         "one across several players.",
            "hard_cap": "A hard cap is a ceiling you can't pass for the rest of the season once you use certain "
                        "exceptions. Bird rights can take you over the aprons, but never past a hard cap.",
        },
    }


def free_agent_offer_quote_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Preview one offer: legal or not, how it would be paid, what it locks in, and the salary year by year. The same
    calculation submit_free_agent_offer applies, so the screen and the save agree (rule 4)."""
    from .play import signing_cap_check, incumbent_bird_rights
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team_query = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    team = resolve_team(active, team_query)
    player_id = str(payload.get("player_id") or payload.get("id"))
    player = next((item for item in active.get("players", []) if item.get("id") == player_id), None)
    if not player:
        raise AppActionError(f"No free agent found with id {player_id!r}.")
    years = max(1, min(5, int(payload.get("years") or 1)))
    aav = float(payload.get("aav_millions") or payload.get("aav") or 0.0)
    bird = incumbent_bird_rights(active, save, player, team["id"])
    check = signing_cap_check(active, save, team_query, aav, bird=bird, player=player, years=years,
                              route=payload.get("route") or None, raise_rate=offer_raise_rate(payload))
    return {"status": "ok", "player_id": player_id, "years": years, "aav_millions": aav, "quote": quote_view(check)}


def renounce_cap_hold_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Give up a free agent's rights to clear his cap hold (FA-REAL). Returns the before/after room and the room."""
    from . import cap_ledger
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team_query = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    team = resolve_team(active, team_query)
    player_id = str(payload.get("player_id") or "")
    preview = cap_ledger.renounce_preview(active, save, team["id"], player_id)
    if not preview.get("ok"):
        return {"status": "blocked", "reason": preview.get("reason") or "No cap hold to renounce."}
    if not cap_ledger.renounce(save, team["id"], player_id, by="user"):
        return {"status": "blocked", "reason": "You no longer hold his rights."}
    name = preview.get("name") or "the player"
    add_news(save, "free_agency", f"{team.get('abbrev')} renounced its rights to {name}, clearing "
             f"${preview['hold_millions']:.1f}M of cap hold.", date_value=(save.get("state") or {}).get("current_date"))
    write_save(save_path, save)
    seed = int(payload.get("seed") or 1)
    return {"status": "renounced", "preview": preview,
            "room": free_agency_room_payload(canonical, save_path, team_query, seed)}


def advance_re_signing_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    from .play import initialize_free_agency_market

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    seed = int(payload.get("seed") or 1)
    mode = str(payload.get("mode") or "day")
    initialize_free_agency_market(canonical, save_path, team, seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    if str((save.get("state") or {}).get("phase") or "") != "re_signing":
        return {"status": "blocked", "reason": "The exclusive re-signing window is not active.", "room": free_agency_room_payload(canonical, save_path, team, seed)}
    state = save.setdefault("free_agency_state", {})
    day = int(state.get("re_signing_day") or 1)
    day_count = int(state.get("re_signing_day_count") or 2)
    open_market = mode == "open_market" or day >= day_count
    if not open_market:
        state["re_signing_day"] = day + 1
        current = date.fromisoformat(str(save.get("state", {}).get("current_date") or "2026-06-27"))
        advance_lifecycle_to(canonical, save, min(current + timedelta(days=1), date(current.year, 6, 30)).isoformat(), seed, root)
        write_save(save_path, save)
        return {"status": "advanced_day", "room": free_agency_room_payload(canonical, save_path, team, seed)}

    user_team_id = resolve_team(canonical_with_save(canonical, save), team)["id"]
    for right in save.get("re_signing_rights", []):
        if right.get("team_id") == user_team_id and right.get("status") == "exclusive_review_window":
            right["status"] = "entered_open_market"
    state["re_signing_status"] = "completed"
    state["re_signing_day"] = day_count
    end_year = int(str(save.get("meta", {}).get("season") or CANONICAL_SEASON).split("-")[0]) + 1
    advance_lifecycle_to(canonical, save, f"{end_year}-07-01", seed, root)
    write_save(save_path, save)
    initialize_free_agency_market(canonical, save_path, team, seed)
    return {"status": "open_market", "room": free_agency_room_payload(canonical, save_path, team, seed)}


def advance_free_agency_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], root: Path) -> dict[str, Any]:
    from .play import advance_free_agency_day, finish_free_agency_phase, initialize_free_agency_market, simulate_free_agency_to_end

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    seed = int(payload.get("seed") or 1)
    mode = str(payload.get("mode") or "day")
    initialize_free_agency_market(canonical, save_path, team, seed)
    if mode == "end":
        result = simulate_free_agency_to_end(canonical, save_path, team, seed, root=root)
        finish_free_agency_phase(canonical, save_path, root=root)
    else:
        result = advance_free_agency_day(canonical, save_path, team, seed, root=root)
    return {"status": "advanced", "result": result, "room": free_agency_room_payload(canonical, save_path, team, seed)}


def staff_room_payload(canonical: dict[str, Any], save_path: Path, team_query: str, slot: str | None = None, limit: int | None = None) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team_report = staff_team_report(canonical, save, team_query)
    market = staff_market_report(canonical, save, slot=slot, limit=limit or 30)
    return {"team_report": team_report, "market": market}


def staff_retention_room_payload(canonical: dict[str, Any], save_path: Path, window_id: str | None = None) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    snapshot = staff_retention_snapshot(canonical, save, str(window_id) if window_id else None)
    slot = ((snapshot.get("window") or {}).get("slot"))
    snapshot["market"] = staff_market_report(canonical, save, slot=slot, limit=8) if slot else {"candidates": []}
    return snapshot


def resolve_staff_retention_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    window_id = str(payload.get("window_id") or "")
    choice = str(payload.get("choice") or "re_sign")
    snapshot = staff_retention_snapshot(canonical, save, window_id or None)
    if snapshot.get("status") != "required":
        return snapshot
    window = snapshot["window"]
    if choice == "re_sign":
        result = resolve_staff_retention_re_sign(
            canonical,
            save,
            str(window["id"]),
            salary_millions=float(payload["salary_millions"]) if payload.get("salary_millions") not in {None, ""} else None,
            years=int(payload["years"]) if payload.get("years") not in {None, ""} else None,
        )
    elif choice == "interim":
        result = fire_staff_from_save(save, str(window["team_id"]), str(window["slot"]), reason="contract expired; interim accepted")
    else:
        raise AppActionError(f"Unsupported staff-retention choice {choice!r}.")
    write_save(save_path, save)
    return {"status": result.get("status"), "result": result, "room": staff_retention_room_payload(canonical, save_path)}


def negotiate_staff_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    negotiation = negotiate_staff_hire(
        canonical,
        save,
        str(payload["staff_id"]),
        str(payload.get("team") or user_team_abbrev(canonical, save_path)),
        str(payload["slot"]),
        seed=int(payload.get("seed") or 1),
        offer_salary_millions=float(payload["salary_millions"]) if payload.get("salary_millions") not in {None, ""} else None,
        offer_years=int(payload["years"]) if payload.get("years") not in {None, ""} else None,
    )
    write_save(save_path, save)
    return {"status": "season_limit_blocked" if negotiation.get("status") == "season_limit_blocked" else "negotiated", "negotiation": negotiation, "room": staff_room_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)), slot=payload.get("slot"))}


def hire_staff_action(canonical: dict[str, Any], save_path: Path, negotiation_id: str) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    result = hire_staff_from_save(save, negotiation_id, canonical=canonical)
    write_save(save_path, save)
    return {"status": result.get("status"), "result": result, "room": staff_room_payload(canonical, save_path, user_team_abbrev(canonical, save_path))}


def fire_staff_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_team(canonical, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    result = fire_staff_from_save(save, team["id"], str(payload["slot"]), reason=payload.get("reason") or "user decision")
    write_save(save_path, save)
    return {"status": result.get("status"), "result": result, "room": staff_room_payload(canonical, save_path, team["abbrev"])}


def draft_team_ref(teams: dict[str, dict[str, Any]], team_id: str | None) -> dict[str, Any]:
    team = teams.get(str(team_id or "")) or {}
    return {
        "id": team_id,
        "abbrev": team.get("abbrev") or str(team_id or "").removeprefix("team_").upper(),
        "name": team.get("name") or team.get("abbrev") or team_id,
    }


def draft_lottery_view(canonical: dict[str, Any], order: dict[str, Any], year: str, *, revealed: bool) -> dict[str, Any]:
    teams = {team.get("id"): team for team in canonical.get("teams", [])}
    lottery = order.get("lottery") or {}
    pre_order = list(lottery.get("pre_lottery_order") or [])
    odds = lottery.get("odds_by_team") or {}
    context = lottery.get("odds_context_by_team") or {}
    odds_rows = [
        {
            "seed": index,
            "team": draft_team_ref(teams, team_id),
            "odds": float(odds.get(team_id) or 0.0),
            "context": context.get(team_id) or "",
        }
        for index, team_id in enumerate(pre_order, start=1)
    ]
    pre_rank = {team_id: index for index, team_id in enumerate(pre_order, start=1)}
    reveal_rows: list[dict[str, Any]] = []
    if revealed:
        lottery_order = sorted(
            (
                row for row in order.get("draft_order") or []
                if int(row.get("round") or 0) == 1 and int(row.get("overall_pick") or 99) <= 14
            ),
            key=lambda row: int(row.get("overall_pick") or 99),
        )
        for row in lottery_order:
            original_id = row.get("original_team_id") or row.get("team_id")
            owner_id = row.get("current_owner_team_id") or row.get("owner_team_id") or original_id
            pick_no = int(row.get("overall_pick") or 0)
            starting_seed = pre_rank.get(original_id)
            reveal_rows.append(
                {
                    "pick": pick_no,
                    "pick_id": row.get("pick_id") or row.get("id"),
                    "original_team": draft_team_ref(teams, original_id),
                    "owner_team": draft_team_ref(teams, owner_id),
                    "starting_seed": starting_seed,
                    "movement": (starting_seed - pick_no) if starting_seed else 0,
                    "ownership_changed": owner_id != original_id,
                }
            )
    return {
        "year": str(year),
        "seed": lottery.get("seed") if revealed else None,
        "draw_count": int(lottery.get("draw_count") or 0),
        "odds": odds_rows,
        "reveal": reveal_rows,
        "revealed": bool(revealed),
        "notes": lottery.get("notes") or "Lottery odds are based on the saved season standings.",
    }


def clean_draft_order_item(item: dict[str, Any], teams: dict[str, dict[str, Any]], *, include_prospect: bool) -> dict[str, Any]:
    selection = item.get("selection") or {}
    team_id = selection.get("team_id") or (item.get("team") or {}).get("id")
    result = {
        "id": item.get("id") or selection.get("id"),
        "selection": {
            "id": selection.get("id"),
            "pick_id": selection.get("pick_id"),
            "overall_pick": selection.get("overall_pick"),
            "round": selection.get("round") or (item.get("pick") or {}).get("round"),
            "team_id": team_id,
            "prospect_id": selection.get("prospect_id") if include_prospect else None,
        },
        "team": draft_team_ref(teams, team_id),
    }
    if include_prospect:
        result["prospect"] = dict(item.get("prospect") or {})
        result["prospect"]["age"] = whole_prospect_age(result["prospect"].get("age"))
        result["explanation"] = (item.get("decision") or {}).get("notes")
    return result


def completed_draft_trade_recap(save: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return durable draft-night trade headlines after breaking-news queues drain."""
    draft_date = str((save.get("state") or {}).get("current_date") or "")
    candidates = [
        *(state.get("ai_draft_trade_history") or []),
        *(state.get("ai_draft_trade_news_queue") or []),
        *[
            event
            for event in save.get("league_events", [])
            if event.get("kind") == "trade" and str(event.get("date") or "") == draft_date
        ],
    ]
    recap: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        headline = str(item.get("headline") or "").strip()
        if not headline:
            continue
        key = str(item.get("proposal_id") or item.get("id") or headline)
        if key in seen or headline in seen:
            continue
        seen.update({key, headline})
        recap.append(
            {
                "id": item.get("id") or stable_id("draft_trade_recap", draft_date, headline),
                "date": item.get("date") or draft_date,
                "overall_pick": item.get("overall_pick"),
                "headline": headline,
                "proposal_id": item.get("proposal_id"),
            }
        )
    return recap


PROSPECT_INJURY_AREA_LABELS = {
    "ankle_foot": "Ankle/foot", "knee": "Knee", "back_core": "Back/core", "shoulder_arm_hand": "Shoulder/arm/hand",
}


def prospect_medical_lookup(active: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Existing medical profiles keyed by prospect id (generated ones are rebuilt the same way the draft engine does)."""
    from .health import generated_prospect_medical_profile

    seeds = {str(c.get("season")): c.get("seed") or 0 for c in active.get("draft_classes", [])}
    lookup: dict[str, dict[str, Any]] = {}
    for prospect in active.get("draft_prospects", []):
        medical = prospect.get("medical_profile")
        if not medical and prospect.get("league") == "generated":
            medical = generated_prospect_medical_profile(prospect["id"], prospect["draft_year"], seeds.get(prospect["draft_year"], 0))
        if medical:
            lookup[str(prospect["id"])] = {**medical, "_prospect": prospect}
    return lookup


def prospect_injury_report(medical: dict[str, Any] | None, today: str | None = None) -> dict[str, Any]:
    """Split a prospect's medical profile into history, current injury and projected risk.

    Prospects without a medical profile (imported real prospects) report no data; nothing is invented.
    An injury whose return date is before `today` (ISO date) is no longer current; it is listed in history."""
    from .health import prospect_medical_penalty

    if not medical:
        return {"available": False}
    prospect = medical.get("_prospect") or {}
    profile = {key: value for key, value in medical.items() if key != "_prospect"}
    penalty = prospect_medical_penalty({"medical_profile": profile})
    label = "High" if penalty >= 4 else "Moderate" if penalty >= 1.5 else "Low"

    def area(row: dict[str, Any]) -> str:
        return PROSPECT_INJURY_AREA_LABELS.get(str(row.get("body_area") or ""), str(row.get("body_area") or "Unknown").replace("_", " ").title())

    history = [
        {"body_area": area(row), "severity": str(row.get("severity") or ""), "season": str(row.get("season") or ""), "status": str(row.get("status") or "")}
        for row in profile.get("major_prior_injuries") or []
    ]
    current = profile.get("current_injury")
    if current and today and str(current.get("return_date") or "9999") < str(today):
        history.append({"body_area": area(current), "severity": str(current.get("severity") or ""),
                        "season": str(current.get("start_date") or "")[:4], "status": f"returned {current.get('return_date')}"})
        current = None
    return {
        "available": True,
        "history": history,
        "current": ({"body_area": area(current), "severity": str(current.get("severity") or ""), "return_date": str(current.get("return_date") or "")} if current else None),
        "risk_label": label,
        "risk_penalty": penalty,
        "injury_prone": bool(profile.get("injury_prone")),
    }


def enrich_draft_board_scouting(
    active: dict[str, Any],
    save: dict[str, Any],
    team_id: str,
    board: dict[str, Any],
) -> dict[str, Any]:
    """Attach the same save-aware scouting read to every draft UI surface.

    Movement: change since the scouts' last monthly update when the board has one, else since the season's
    first board (prospect_preseason_ranks)."""
    from .play import prospect_scout_display, scouting_report_for

    medical_by_id = prospect_medical_lookup(active)
    today = (save.get("state") or {}).get("current_date")
    baselines = (save.get("prospect_preseason_ranks") or {}).get(f"{team_id}:{board.get('year')}", {})
    for entry in board.get("entries") or []:
        prospect = entry.get("prospect") or entry
        prospect["injury_report"] = prospect_injury_report(medical_by_id.get(str(prospect.get("id") or prospect.get("prospect_id"))), today)
        scout = prospect_scout_display(active, prospect, team_id, save)
        report = scouting_report_for(active, prospect.get("id") or prospect.get("prospect_id"), team_id, prospect=prospect)
        entry["scout_display"] = {**scout, **prospect_card_ratings(prospect, scout, report)}
        baseline_rank = int(baselines.get(prospect.get("id")) or entry.get("season_start_rank") or entry.get("board_rank") or 999)
        entry["season_start_rank"] = baseline_rank
        if entry.get("scout_rank_change") is not None:
            entry["rank_change"] = int(entry["scout_rank_change"])
            entry["rank_change_basis"] = "month"
        else:
            entry["rank_change"] = baseline_rank - int(entry.get("board_rank") or baseline_rank)
            entry["rank_change_basis"] = "season"
    return board


def draft_room_payload(
    canonical: dict[str, Any],
    save_path: Path,
    team_query: str,
    year: str,
    seed: int = 1,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .play import current_draft_selection, ensure_live_draft_state

    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    phase = str((save.get("state") or {}).get("phase") or "")
    active = prepared_active if prepared_active is not None else canonical_with_save(canonical, save)
    team = resolve_team(active, team_query)
    existing_state = save.get("draft_state") or {}
    if phase != "draft" and existing_state.get("status") not in {"in_progress", "completed"}:
        saved_order = (save.get("draft_orders") or {}).get(str(year)) or {}
        preview_order = saved_order or generate_draft_order(
            active,
            str(year),
            seed=int(seed),
            standings=save_standings_for_draft(canonical, save),
        )
        if not saved_order:
            annotate_lottery_odds_context(active, save, preview_order)
        lottery_revealed = bool(saved_order)
        board = enrich_draft_board_scouting(
            active,
            save,
            team["id"],
            draft_board_report(active, team["abbrev"], str(year), limit=None),
        )
        return {
            "year": str(year),
            "team": team,
            "state": {
                "status": "locked_until_draft",
                "current_index": 0,
                "total_picks": 0,
                "phase": phase,
            },
            "current_selection": None,
            "next_user_selection": None,
            "presentation_stage": "reveal" if lottery_revealed else "odds",
            "lottery": draft_lottery_view(active, preview_order, str(year), revealed=lottery_revealed),
            "previous_picks": [],
            "upcoming": [],
            "upcoming_order": [],
            "draft_board": board,
            "board_context_team": team,
            "trade_news": [],
            "notes": "Review the lottery odds, reveal the saved order, then enter draft night.",
        }
    if (
        existing_state.get("year") == str(year)
        and existing_state.get("status") in {"in_progress", "completed"}
        and existing_state.get("draft")
    ):
        state = existing_state
    else:
        state = ensure_live_draft_state(canonical, save_path, str(year), seed)
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = canonical_with_save(canonical, save)
        team = resolve_team(active, team_query)
    current = current_draft_selection(state)
    pending = (state.get("draft") or {}).get("pending_draft_selections") or []
    index = int(state.get("current_index") or 0)
    teams = {item.get("id"): item for item in active.get("teams", [])}
    next_user = next(
        (
            item
            for item in pending[index:]
            if (item.get("selection") or {}).get("team_id") == team["id"]
        ),
        None,
    )
    board_team = team["abbrev"]
    previous_picks = [clean_draft_order_item(item, teams, include_prospect=True) for item in pending[:index]]
    upcoming_order = [clean_draft_order_item(item, teams, include_prospect=False) for item in pending[index:]]
    draft_timeline = []
    for timeline_index, item in enumerate(pending):
        row = clean_draft_order_item(item, teams, include_prospect=timeline_index < index)
        row["draft_status"] = "selected" if timeline_index < index else "current" if timeline_index == index else "upcoming"
        draft_timeline.append(row)
    drafted_by_prospect = {
        str((item.get("selection") or {}).get("prospect_id") or (item.get("prospect") or {}).get("id")): clean_draft_order_item(item, teams, include_prospect=True)
        for item in pending[:index]
        if (item.get("selection") or {}).get("prospect_id") or (item.get("prospect") or {}).get("id")
    }
    board = live_draft_board_report(active, save, team, str(year), state)
    for entry in board.get("entries") or []:
        prospect_id = str((entry.get("prospect") or {}).get("id") or (entry.get("prospect") or {}).get("prospect_id") or entry.get("prospect_id") or "")
        drafted = drafted_by_prospect.get(prospect_id)
        entry["draft_status"] = "drafted" if drafted else "available"
        if drafted:
            entry["selected_pick"] = (drafted.get("selection") or {}).get("overall_pick")
            entry["selected_team"] = drafted.get("team")
    saved_order = (save.get("draft_orders") or {}).get(str(year)) or {}
    draft_complete = state.get("status") == "completed" or index >= len(pending)
    return {
        "year": str(year),
        "team": team,
        "presentation_stage": "draft",
        "lottery": draft_lottery_view(active, saved_order, str(year), revealed=True) if saved_order else None,
        "state": {
            "status": "completed" if draft_complete else state.get("status"),
            "current_index": index,
            "total_picks": len(pending),
            "applied_selection_ids": state.get("applied_selection_ids") or [],
        },
        "current_selection": current,
        "current_pick_is_user_owned": bool(current and (current.get("selection") or {}).get("team_id") == team["id"]),
        "next_user_selection": clean_draft_order_item(next_user, teams, include_prospect=False) if next_user else None,
        "remaining_user_picks": [
            int((item.get("selection") or {}).get("overall_pick") or 0)
            for item in pending[index:]
            if (item.get("selection") or {}).get("team_id") == team["id"]
        ],
        "previous_picks": previous_picks,
        "upcoming": upcoming_order,
        "upcoming_order": upcoming_order,
        "draft_timeline": draft_timeline,
        "draft_board": board,
        "board_context_team": team,
        "trade_news": list(state.get("ai_draft_trade_news_queue") or []),
        "trade_recap": completed_draft_trade_recap(save, state) if draft_complete else [],
    }


def live_draft_board_report(
    active: dict[str, Any],
    save: dict[str, Any],
    team: dict[str, Any],
    year: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """The draft-night board: the user's scouts' final (June) board beside the league consensus, for the prospects
    in this draft. Same rows as before the draft; no hidden ratings, and Fit is the GM's need fit only."""
    from .draft_scouting import DRAFT_MONTH

    pending = ((state.get("draft") or {}).get("pending_draft_selections") or [])
    ids = {str((item.get("prospect") or {}).get("id") or (item.get("selection") or {}).get("prospect_id") or "")
           for item in pending}
    ids.discard("")
    try:
        board = draft_board_report(active, team["abbrev"], str(year), limit=None, month=DRAFT_MONTH)
    except (KeyError, ValueError):
        board = {"entries": []}
    entries = [entry for entry in board.get("entries") or [] if str((entry.get("prospect") or {}).get("id")) in ids]
    entries.sort(key=lambda item: (int(item.get("consensus_rank") or 999), int(item.get("board_rank") or 999)))
    return enrich_draft_board_scouting(
        active,
        save,
        team["id"],
        {"team": team, "year": year, "month": board.get("month"), "month_label": board.get("month_label"),
         "entry_count": len(entries), "entries": entries},
    )


def draft_reveal_lottery_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    year = str(payload.get("year") or current_draft_year(save))
    phase = str((save.get("state") or {}).get("phase") or "")
    saved_order = (save.get("draft_orders") or {}).get(year)
    if phase not in {"draft_lottery", "draft"} and not saved_order:
        return {"status": "blocked", "notes": "The draft lottery is not active."}
    if not saved_order:
        saved_order = run_draft_lottery(canonical, save_path, year=year, seed=None, advance_to_draft=False)
    revealed_save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, revealed_save)
    team = resolve_team(active, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    room = {
        "year": year,
        "team": team,
        "presentation_stage": "reveal",
        "lottery": draft_lottery_view(active, saved_order, year, revealed=True),
        "state": {
            "status": "lottery_revealed",
            "current_index": 0,
            "total_picks": int(saved_order.get("pick_count") or len(saved_order.get("draft_order") or [])),
            "phase": str((revealed_save.get("state") or {}).get("phase") or "draft"),
        },
        "current_selection": None,
        "next_user_selection": None,
        "previous_picks": [],
        "upcoming": [],
        "upcoming_order": [],
        "draft_board": enrich_draft_board_scouting(
            active,
            revealed_save,
            team["id"],
            draft_board_report(active, team["abbrev"], year, limit=None),
        ),
        "board_context_team": team,
        "trade_news": [],
    }
    return {"status": "revealed", "lottery": room["lottery"], "room": room}


def draft_action_rejection(canonical: dict[str, Any], save: dict[str, Any], team: str, year: str, *, prospect_id: str | None = None, user_pick: bool | None = None) -> dict[str, Any] | None:
    """Reject consumed live picks before draft preparation can write a save."""
    from .draft import draft_selection_rejection

    state = save.get("draft_state") or {}
    if str(state.get("year") or "") != year:
        return None
    queue = (state.get("draft") or {}).get("pending_draft_selections") or []
    index = int(state.get("current_index") or 0)
    if index >= len(queue):
        return None
    candidate = deepcopy(queue[index])
    order = ((save.get("draft_orders") or {}).get(year) or {}).get("draft_order") or []
    slots = [int((item.get("selection") or {}).get("overall_pick") or i + 1) for i, item in enumerate(queue)]
    if len(queue) == len(order) and slots != sorted(int(row.get("overall_pick") or 0) for row in order):
        from .play import draft_pick_identity, saved_order_pending_slots

        mapped = saved_order_pending_slots(queue, order, index)
        row = next(row for row in order if mapped.get(int(row.get("overall_pick") or 0)) is queue[index])
        owner = row.get("current_owner_team_id") or row.get("owner_team_id")
        identity = draft_pick_identity(row)
        candidate.setdefault("selection", {}).update(pick_id=identity, overall_pick=int(row["overall_pick"]), team_id=owner)
        candidate.setdefault("pick", {}).update(id=identity, current_owner_team_id=owner)
    selection = candidate.get("selection") or candidate
    is_user_pick = selection.get("team_id") == resolve_team(canonical, team)["id"]
    if user_pick is not None and user_pick != is_user_pick:
        return None
    if prospect_id:
        selection["prospect_id"] = prospect_id
        if candidate.get("selection"):
            candidate["prospect"] = {"id": prospect_id}
    return draft_selection_rejection(save, candidate)


def draft_apply_current_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from .draft import load_draft_application_save
    from .play import apply_current_draft_selection, current_draft_selection, ensure_live_draft_state, select_current_draft_prospect

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    save = ensure_league_save_defaults(load_draft_application_save(save_path), canonical)
    year = str(payload.get("year") or current_draft_year(save))
    seed = int(payload.get("seed") or 1)
    rejection = draft_action_rejection(canonical, save, team, year, prospect_id=str(payload.get("prospect_id") or ""), user_pick=True)
    if rejection:
        return {"status": rejection["status"], "result": rejection, "room": draft_room_payload(canonical, save_path, team, year, seed, prepared_save=save)}
    if str((save.get("state") or {}).get("phase") or "") != "draft" and (save.get("draft_state") or {}).get("status") not in {"in_progress", "completed"}:
        return {"status": "blocked", "notes": "Draft controls unlock during the draft phase.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    state = ensure_live_draft_state(canonical, save_path, year, seed)
    current = current_draft_selection(state)
    if not current:
        return {"status": "completed", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    active = canonical_with_save(canonical, ensure_league_save_defaults(load_save(save_path), canonical))
    user_team = resolve_team(active, team)
    if (current.get("selection") or {}).get("team_id") != user_team["id"]:
        return {"status": "blocked", "notes": "Use Sim Current Pick while an AI team is on the clock.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    prospect_id = str(payload.get("prospect_id") or "")
    if not prospect_id:
        return {"status": "blocked", "notes": "Select an available prospect before making your pick.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    current = select_current_draft_prospect(save_path, prospect_id)
    if not current:
        return {"status": "blocked", "notes": "That prospect is no longer available.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    result = apply_current_draft_selection(save_path, current, canonical=canonical, user_team=team, seed=seed)
    return {"status": result.get("status"), "result": result, "room": draft_room_payload(canonical, save_path, team, year, seed)}


def draft_sim_current_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from .draft import load_draft_application_save
    from .play import apply_current_draft_selection, current_draft_selection, ensure_live_draft_state

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    save = ensure_league_save_defaults(load_draft_application_save(save_path), canonical)
    year = str(payload.get("year") or current_draft_year(save))
    seed = int(payload.get("seed") or 1)
    rejection = draft_action_rejection(canonical, save, team, year, user_pick=False)
    if rejection:
        return {"status": rejection["status"], "result": rejection, "room": draft_room_payload(canonical, save_path, team, year, seed, prepared_save=save)}
    if str((save.get("state") or {}).get("phase") or "") != "draft" and (save.get("draft_state") or {}).get("status") not in {"in_progress", "completed"}:
        return {"status": "blocked", "notes": "Draft controls unlock during the draft phase.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    state = ensure_live_draft_state(canonical, save_path, year, seed)
    current = current_draft_selection(state)
    if not current:
        return {"status": "completed", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    active = canonical_with_save(canonical, ensure_league_save_defaults(load_save(save_path), canonical))
    user_team = resolve_team(active, team)
    if (current.get("selection") or {}).get("team_id") == user_team["id"]:
        return {"status": "blocked", "notes": "Choose a prospect while your team is on the clock.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    result = apply_current_draft_selection(save_path, current, canonical=canonical, user_team=team, seed=seed)
    return {"status": result.get("status"), "result": result, "room": draft_room_payload(canonical, save_path, team, year, seed)}


def draft_sim_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], mode: str) -> dict[str, Any]:
    from .draft import load_draft_application_save
    from .play import ensure_live_draft_state, sim_entire_draft, sim_to_next_user_pick

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    save = ensure_league_save_defaults(load_draft_application_save(save_path), canonical)
    year = str(payload.get("year") or current_draft_year(save))
    seed = int(payload.get("seed") or 1)
    rejection = draft_action_rejection(canonical, save, team, year)
    if rejection:
        return {"status": rejection["status"], "result": rejection, "room": draft_room_payload(canonical, save_path, team, year, seed, prepared_save=save)}
    if str((save.get("state") or {}).get("phase") or "") != "draft" and (save.get("draft_state") or {}).get("status") not in {"in_progress", "completed"}:
        return {"status": "blocked", "notes": "Draft controls unlock during the draft phase.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    ensure_live_draft_state(canonical, save_path, year, seed)
    result = sim_entire_draft(save_path, canonical=canonical, user_team=team, seed=seed) if mode == "all" else sim_to_next_user_pick(canonical, save_path, team, seed=seed)
    return {"status": "simulated", "result": result, "room": draft_room_payload(canonical, save_path, team, year, seed)}


def playoff_room_payload(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    picture = playoff_picture(canonical, save_path, prepared_save=save)
    teams = {team["id"]: team for team in canonical.get("teams", [])}

    def team_ref(team_id: str | None) -> dict[str, Any] | None:
        if not team_id:
            return None
        team = teams.get(team_id)
        return {"id": team_id, "abbrev": team.get("abbrev", team_id) if team else team_id, "name": team.get("name") if team else team_id}

    state = dict(initialize_postseason(canonical, save, save_path, int(save.get("meta", {}).get("seed") or 1)))
    repair_unplayed_playoff_round(state)
    playoff_games = {
        str(game.get("externalGameId") or ""): game
        for game in state.get("games", []) or []
        if game.get("externalGameId")
    }
    game_results = {
        str(result.get("game_id") or ""): result
        for result in [*save.get("game_result_summaries", []), *save.get("game_results", [])]
        if result.get("game_id")
    }

    def series_game_row(game_id: str) -> dict[str, Any]:
        game = playoff_games.get(game_id, {})
        result = game_results.get(game_id, {})
        return {
            "game_id": game_id,
            "date": game.get("gameDate"),
            "away_team": team_ref(result.get("away_team_id") or game.get("away_team_id")),
            "home_team": team_ref(result.get("home_team_id") or game.get("home_team_id")),
            "away_score": result.get("away_score"),
            "home_score": result.get("home_score"),
        }

    series_rows = []
    display_series = list(state.get("series") or [])
    if state.get("round") == "play_in":
        for conference, locked in state.get("locked_seeds", {}).items():
            qualifiers = state.get("play_in", {}).get(conference, {})
            seeds = {**locked, "7": qualifiers.get("seed_7_team_id"), "8": qualifiers.get("seed_8_team_id")}
            for high, low in (("1", "8"), ("4", "5"), ("3", "6"), ("2", "7")):
                display_series.append({"id":f"preview:{conference}:{high}", "conference":conference,
                    "round":"first_round", "team_ids":[seeds.get(high), seeds.get(low)], "wins":{},
                    "pending_seed":low if not seeds.get(low) else None, "game_ids":[]})
    for series in display_series:
        team_ids = list(series.get("team_ids") or [])
        wins = series.get("wins") or {}
        game_ids = list(dict.fromkeys(str(game_id) for game_id in series.get("game_ids", []) or [] if game_id))
        game_ids.sort(key=lambda game_id: (str(playoff_games.get(game_id, {}).get("gameDate") or ""), game_id))
        series_rows.append(
            {
                **series,
                "game_ids": game_ids,
                "games": [series_game_row(game_id) for game_id in game_ids],
                "teams": [team_ref(team_id) for team_id in team_ids],
                "score": [int(wins.get(team_id, 0)) for team_id in team_ids],
                "winner": team_ref(series.get("winner_team_id")),
            }
        )
    display_play_in = state.get("play_in") or {
        conference: {"status":"not_recorded", "teams":{str(row["seed"]):row["team_id"] for row in rows if 7 <= row["seed"] <= 10}, "games":[]}
        for conference, rows in picture.get("picture", {}).items()
    }
    if not state.get("play_in"):
        for conference, payload in display_play_in.items():
            first = [s for s in state.get("series", []) if s.get("conference") == conference and s.get("round") == "first_round"]
            slots = {s.get("bracket_slot", i):s for i, s in enumerate(first)}
            for seed, slot in ((8, 0), (7, 3)):
                source = slots.get(slot, {})
                ids = source.get("team_ids") or []
                qualifier = source.get("lower_seed_team_id") or (ids[1] if len(ids) > 1 else None)
                if qualifier:
                    payload["teams"][str(seed)] = qualifier
                    payload[f"seed_{seed}_team_id"] = qualifier
    return {
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "status": state.get("status") or "picture",
        "round": state.get("round") or "picture",
        "champion": team_ref(state.get("champion_team_id")),
        "picture": picture.get("picture", {}),
        "playoff_state": state,
        "series": series_rows,
        "play_in": {conference: {**payload, "teams": {seed:team_ref(team_id) for seed, team_id in payload.get("teams", {}).items()},
            "games":[series_game_row(str(game_id)) for game_id in payload.get("games", [])]}
            for conference, payload in display_play_in.items()},
        "games": state.get("games") or [],
    }


def postseason_team_ids(state: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Every team in this postseason, and the ones not yet eliminated (series losers and play-in teams that did
    not qualify are out)."""
    teams: set[str] = set()
    eliminated: set[str] = set()
    for series in state.get("series") or []:
        ids = {str(team_id) for team_id in series.get("team_ids") or [] if team_id}
        teams |= ids
        winner = series.get("winner_team_id")
        if winner:
            eliminated |= ids - {str(winner)}
    for seeds in (state.get("locked_seeds") or {}).values():
        teams |= {str(team_id) for team_id in seeds.values() if team_id}
    for play_in in (state.get("play_in") or {}).values():
        entrants = {str(team_id) for team_id in (play_in.get("teams") or {}).values() if team_id}
        teams |= entrants
        if play_in.get("status") == "completed":
            eliminated |= entrants - {str(play_in.get("seed_7_team_id")), str(play_in.get("seed_8_team_id"))}
    champion = state.get("champion_team_id")
    alive = {str(champion)} if champion else teams - eliminated
    return teams, alive


def playoff_injuries_payload(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    """Playoff Injuries card: players on teams still in the postseason who are out injured, or back but still rusty
    or on a minutes limit. Only the engine's own health state (the same fields the Minutes + Availability card and
    the player card show); ratings are the displayed OVR/OFF/DEF."""
    from .sim import rust_display
    context = dashboard_read_context(canonical, save_path)
    save, active = context["save"], context["active"]
    state = save.get("playoff_state") or {}
    current_date = save.get("state", {}).get("current_date")
    user_team_id = save.get("meta", {}).get("user_team_id")
    _teams, alive = postseason_team_ids(state)
    teams = {team["id"]: team for team in active.get("teams", [])}
    health = {row.get("player_id"): row for row in save.get("health_states", [])}
    rows = []
    for player in active.get("players", []):
        team_id = player.get("team_id")
        if team_id not in alive or player["id"] not in health:
            continue
        health_state = health[player["id"]]
        out = str(health_state.get("availability_status") or "active") != "active"
        label = player_health_label(health_state, current_date)
        rust = {} if out else rust_display(health_state)
        returning = not out and (float(rust.get("rust_penalty") or 0) >= 0.1 or float(rust.get("minutes_limit_pct") or 100) < 100)
        if not out and not returning:
            continue
        attrs = player_display_attribute_summary(active, player["id"])
        days_left = label.get("days_left")
        rows.append({
            "player_id": player["id"],
            "name": player.get("name"),
            "headshot_url": player.get("headshot_url"),
            "team_id": team_id,
            "team_abbrev": (teams.get(team_id) or {}).get("abbrev", team_id),
            "position": compact_position(player.get("position")),
            "overall": attrs.get("overall"),
            "offense": attrs.get("offense"),
            "defense": attrs.get("defense"),
            "status": "out" if out else "returning",
            "injury": (label.get("diagnosis") or str(label.get("severity") or "").replace("_", " ")) if out else None,
            "severity": label.get("severity") if out else None,
            "return_date": health_state.get("return_date") if out else None,
            "days_left": days_left if out else None,
            "games_estimate": max(1, round(days_left / 2.4)) if out and days_left is not None else None,
            "games_missed": int(health_state.get("games_missed") or 0),
            "rust_penalty": rust.get("rust_penalty"),
            "rust_games": rust.get("rust_games"),
            "minutes_limit_pct": rust.get("minutes_limit_pct"),
            "minutes_limit_games": rust.get("minutes_limit_games"),
            "user_team": team_id == user_team_id,
        })
    rows.sort(key=lambda row: (-(float(row.get("overall") or 0)), str(row.get("name") or "")))
    return {
        "as_of": current_date,
        "round": state.get("round"),
        "user_team_id": user_team_id,
        "teams_alive": sorted(alive),
        "players": rows,
    }


def simulate_playoff_action(canonical: dict[str, Any], save_path: Path, root: Path, seed: int, mode: str, *, hold_postseason: bool = False) -> dict[str, Any]:
    if mode == "all":
        result: dict[str, Any] = {"status": "not_started"}
        for _ in range(8):
            result = simulate_playoff_round(canonical, save_path, seed=seed, root=root, advance_to_offseason=not hold_postseason)
            playoff_state = result.get("playoff_state") or {}
            if simulation_stop_requested() or playoff_state.get("status") == "completed":
                break
    elif mode == "round":
        result = simulate_playoff_round(canonical, save_path, seed=seed, root=root, advance_to_offseason=not hold_postseason)
    else:
        result = simulate_next_playoff_game(canonical, save_path, seed=seed, root=root, advance_to_offseason=not hold_postseason)
    return {"status": "stopped" if simulation_stop_requested() else result.get("status") or "simulated", "result": result, "room": playoff_room_payload(canonical, save_path)}


def trade_presentation_context(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    """Share inexpensive identity/evidence lookups across an entire offer list."""
    return {
        "players": {str(row["id"]): row for row in canonical.get("players", [])},
        "teams": {str(row["id"]): row for row in canonical.get("teams", [])},
        "valuations": {str(row.get("player_id")): row for row in canonical.get("player_asset_valuations", [])},
        "health": {str(row.get("player_id")): row for row in save.get("health_states", [])},
        "player_evidence": {},
        "team_caps": {},
        "team_phases": {str(row.get("team_id")): str(row.get("phase") or "balanced") for row in canonical.get("team_strategic_states", [])},
    }


def enhance_trade_candidate(
    canonical: dict[str, Any],
    candidate: dict[str, Any],
    *,
    save: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project current player and pick evidence without recalculating a trade."""
    context = context if context is not None else trade_presentation_context(canonical, save)
    pick_context = canonical_with_pending_pick_terms(canonical, candidate.get("pick_trade_terms") or candidate.get("pick_obligation_terms"))
    item = trade_candidate_with_current_asset_labels(pick_context, candidate)
    proposal = item.get("proposal") or {}
    from .transactions import multi_team_participation_issues
    participation = multi_team_participation_issues(canonical, proposal)
    if participation:
        item['legality'] = {**(item.get('legality') or {}), 'status': 'illegal',
                            'issues': list(dict.fromkeys([*(item.get('legality') or {}).get('issues', []), *participation]))}
        item['accepted_by_all'] = False
    active_season = str(save.get("meta", {}).get("season") or canonical.get("meta", {}).get("active_season") or CANONICAL_SEASON)
    from .transactions import trade_transfers, trade_team_flows
    for leg in trade_transfers(proposal):
        for asset in leg['assets']:
            asset_id = str(asset.get("id") or asset.get("value") or "")
            if asset.get("kind") == "player":
                player = context["players"].get(asset_id)
                if not player:
                    continue
                evidence = context["player_evidence"].get(asset_id)
                if evidence is None:
                    valuation = context["valuations"].get(asset_id) or fallback_asset_valuation(player)
                    attrs = player_display_attribute_summary(canonical, asset_id)
                    contract = contract_for_player(canonical, asset_id)
                    salary = current_salary(contract)
                    team = context["teams"].get(str(player.get("team_id")), {})
                    evidence = {
                        "name": player.get("name"), "label": player.get("name"),
                        "headshot_url": player.get("headshot_url"),
                        "team_id": player.get("team_id"), "team_abbrev": team.get("abbrev"),
                        "position": compact_position(player.get("position")),
                        "age": player.get("display_age", player.get("age")), "height": height_label(player),
                        "overall": attrs.get("overall"), "ratings": attrs,
                        "upside_remaining": round(max(0.0, min(5.0, float(valuation.get("development_upside") or 0) / 22.0 * 5.0)), 1),
                        "health_risk": round(float(valuation.get("health_risk") or 0), 1),
                        "injury_body": injury_body_compact(canonical, player, context["health"].get(asset_id)),
                        "health": health_label(context["health"].get(asset_id), save.get("state", {}).get("current_date")),
                        "contract": contract_summary(contract, active_season),
                        "contract_terms": block_contract_terms(contract, active_season),
                        "salary_by_year": player_salary_table(canonical, asset_id),
                        "salary_millions": round(salary / 1_000_000, 2) if salary is not None else None,
                        "trade_value": round(market_trade_target_value(player, valuation), 1),
                    }
                    context["player_evidence"][asset_id] = evidence
                # Returned offers must never share mutable evidence with the cache.
                asset.update(deepcopy(evidence))
            elif asset.get("kind") == "pick":
                pick = pick_by_id(pick_context, asset_id)
                if pick:
                    original = context["teams"].get(str(pick.get("original_team_id")), {})
                    asset.update({"season": pick.get("season"), "round": pick.get("round"),
                                  "original_team_id": pick.get("original_team_id"), "original_team_abbrev": original.get("abbrev"),
                                  "current_owner_team_id": pick.get("current_owner_team_id"),
                                  "pick_presentation": pick_presentation(pick_context, pick),
                                  "condition_summary": pick_obligation_context_note(pick_context, pick),
                                  "trade_value": round(pick_asset_value(pick, context["team_phases"].get(str(pick.get("current_owner_team_id")), "balanced")), 1)})
            elif asset.get("kind") == "pick_swap":
                swap = pick_swap_by_id(pick_context, asset_id)
                if swap:
                    picks = [pick_by_id(pick_context, swap.get(key)) for key in ("team_a_pick_id", "team_b_pick_id")]
                    original_ids = [pick.get("original_team_id") for pick in picks if pick and pick.get("original_team_id")]
                    asset.update({"season": swap.get("season"), "round": swap.get("round"),
                                  "pick_presentation": swap_presentation(pick_context, swap),
                                  "original_team_ids": original_ids,
                                  "original_team_abbrevs": [context["teams"].get(str(team_id), {}).get("abbrev") for team_id in original_ids],
                                  "condition_summary": pick_swap_display_label(pick_context, swap),
                                  "trade_value": round(pick_swap_asset_value(pick_context, swap, context["team_phases"].get(str(swap.get("current_owner_team_id")), "balanced")), 1)})
    finances = {}
    for team_id, outgoing_assets, incoming_assets in trade_team_flows(proposal):
        if not team_id or str(team_id) not in context["teams"]:
            continue
        if team_id not in context["team_caps"]:
            context["team_caps"][team_id] = team_cap_summary(canonical, save, team_id)
        cap = context["team_caps"][team_id]

        def package_salary(assets) -> float | None:
            salaries = [asset.get("salary_millions") for asset in assets if asset.get("kind") == "player"]
            return round(sum(salaries), 2) if all(salary is not None for salary in salaries) else None

        outgoing, incoming = package_salary(outgoing_assets), package_salary(incoming_assets)
        payroll_after = round(cap["salary_total_millions"] + incoming - outgoing, 2) if outgoing is not None and incoming is not None and not cap.get("unresolved_contract_count") else None
        finances[team_id] = {"cap": deepcopy(cap), "outgoing_salary_millions": outgoing,
                             "incoming_salary_millions": incoming, "payroll_after_millions": payroll_after}
    item["team_finances"] = finances
    item["headline"] = trade_headline_from_payload(proposal)
    return item


def enhance_trade_finder_report(canonical: dict[str, Any], report: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    user_team_id = save.get("meta", {}).get("user_team_id")
    context = trade_presentation_context(canonical, save)
    candidates = []
    for candidate in report.get("candidates", []):
        candidate = enhance_trade_candidate(canonical, candidate, save=save, context=context)
        candidate = mark_trade_finder_offer(candidate, user_team_id)
        candidates.append(candidate)
    report = {**report, "candidates": candidates, "candidate_count": len(candidates)}
    return report


def apply_trade_candidate_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = active_canonical(canonical, save_path)
    candidate = trade_candidate_with_current_asset_labels(active, dict(payload.get("candidate") or {}))
    if not candidate.get("proposal"):
        raise AppActionError("Action requires a trade candidate payload.")
    if candidate['proposal'].get('transfers'):
        from .multi_team_trades import evaluate_multi_team_trade, transfers_for_revalidation
        from .transactions import apply_trade_to_state, trade_team_ids
        user = save['meta']['user_team_id']
        if user not in trade_team_ids(candidate):
            raise AppActionError('The controlled team must participate in this trade.')
        fresh = evaluate_multi_team_trade(active, transfers_for_revalidation(candidate), pick_rules=candidate.get('pick_rules'),
            seed=int(candidate.get('evaluation_seed', 1)), date=save['state']['current_date'])
        fresh['offer_context'] = {'status': 'user_override_pending_apply', 'created_by_user': True, 'override_team_id': user}
        pid = fresh['proposal']['id']
        save['pending_trade_proposals'] = [c for c in save.get('pending_trade_proposals', []) if (c.get('proposal') or c).get('id') != pid] + [fresh]
        result = apply_trade_to_state(save, pid, date=save['state']['current_date'], canonical=canonical, save_label=str(save_path))
        if result.get('status') == 'applied':
            write_save(save_path, save)
        return {'status': result['status'], 'result': result, 'home': home_payload(Path('.'), canonical, save_path)}
    if candidate.get('ui_pick_rules'):
        from .trade_pick_terms import compile_pick_rules, attach_compiled_rules, original_specs_for_rules, candidate_pick_rules
        proposal = candidate['proposal']
        rules = candidate_pick_rules(active,candidate)
        evaluation, assets, terms = compile_pick_rules(active,rules,[
            {'team':proposal['from_team_id'],'recipient':proposal['to_team_id'],'assets':original_specs_for_rules(candidate,'from_assets')},
            {'team':proposal['to_team_id'],'recipient':proposal['from_team_id'],'assets':original_specs_for_rules(candidate,'to_assets')}])
        seed = int(candidate.get('ui_pick_rule_seed') or 1)
        fresh = evaluate_trade(evaluation,proposal['from_team_id'],proposal['to_team_id'],assets[0],assets[1],seed=seed,
                               date=save['state']['current_date'],context_ready=True)
        fresh['offer_context'] = candidate.get('offer_context') or {}
        candidate = attach_compiled_rules(fresh,terms,rules,seed)
    user_team_id = save.get("meta", {}).get("user_team_id")
    source = str(payload.get("source") or (candidate.get("offer_context") or {}).get("source") or "builder")
    if source == "trade_finder":
        candidate = accept_trade_finder_offer(candidate, user_team_id)
        if not candidate:
            return {"status": "not_applied_rejected", "notes": "The trade finder candidate is no longer counterparty-approved."}
    elif not candidate.get("accepted_by_all"):
        if not partner_has_accepted(candidate, user_team_id):
            return {"status": "not_applied_rejected", "notes": "The other team rejects this offer."}
        candidate.setdefault("offer_context", {}).update(
            {
                "status": "user_override_pending_apply",
                "created_by_user": True,
                "override_team_id": user_team_id,
            }
        )
    proposal_id = (candidate.get("proposal") or {}).get("id")
    save.setdefault("pending_trade_proposals", [])
    save["pending_trade_proposals"] = [
        item
        for item in save["pending_trade_proposals"]
        if ((item.get("proposal") or {}).get("id") or item.get("id")) != proposal_id
    ]
    save["pending_trade_proposals"].append(candidate)
    date_value = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    from .transactions import apply_trade_to_state

    result = apply_trade_to_state(save, proposal_id, date=str(date_value), canonical=canonical, save_label=str(save_path))
    if result.get("status") == "applied":
        write_save(save_path, save)
    return {"status": result.get("status"), "result": result, "home": home_payload(Path("."), canonical, save_path)}


def user_trade_offers_payload(
    canonical: dict[str, Any],
    save_path: Path,
    *,
    prepared_save: dict[str, Any] | None = None,
    prepared_active: dict[str, Any] | None = None,
) -> dict[str, Any]:
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    pending = [
        offer for offer in save.get("user_trade_offers", [])
        if (offer.get("offer_context") or {}).get("status") == "pending_user_review"
    ]
    if not pending:
        return {"offer_count": 0, "offers": []}
    active = prepared_active if prepared_active is not None else active_canonical(canonical, save_path)
    offers = []
    presentation = trade_presentation_context(active, save)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for offer in pending:
        grouped.setdefault(trade_offer_fingerprint(offer), []).append(offer)
    for group in grouped.values():
        offer = group[0]
        item = enhance_trade_candidate(active, offer, save=save, context=presentation)
        item["repeat_count"] = sum(_trade_offer_repeat_count(row) for row in group)
        item["repeat_dates"] = list(dict.fromkeys(
            str(value)
            for row in group
            for value in (row.get("repeat_dates") or [
                (row.get("offer_context") or {}).get("created_date"),
                (row.get("offer_context") or {}).get("last_proposed_date"),
            ])
            if value
        ))
        item["duplicate_offer_ids"] = [
            str((row.get("proposal") or {}).get("id") or row.get("id"))
            for row in group[1:]
            if (row.get("proposal") or {}).get("id") or row.get("id")
        ]
        offers.append(item)
    return {"offer_count": len(offers), "offers": offers}


def _trade_offer_repeat_count(offer: dict[str, Any]) -> int:
    try:
        return max(1, int(offer.get("repeat_count") or 1))
    except (TypeError, ValueError):
        return 1


def _pending_trade_offer_group_count(save: dict[str, Any]) -> int:
    return len({
        trade_offer_fingerprint(item)
        for item in save.get("user_trade_offers", [])
        if (item.get("offer_context") or {}).get("status") == "pending_user_review"
    })


def respond_user_trade_offer_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    proposal_id = str(payload.get("proposal_id") or "")
    if not proposal_id:
        raise AppActionError("Action requires proposal_id.")
    def decline_response(status: str) -> dict[str, Any]:
        if payload.get("summary_only") is True:
            # Declining changes the inbox only; the client already has each
            # offer's player evidence and does not need league projections.
            pending_ids = [
                (item.get("proposal") or {}).get("id") or item.get("id")
                for item in save.get("user_trade_offers", [])
                if (item.get("offer_context") or {}).get("status") == "pending_user_review"
            ]
            return {"status": status, "proposal_id": proposal_id,
                    "pending_offer_ids": pending_ids, "offer_count": _pending_trade_offer_group_count(save)}
        return {"status": status, "offers": user_trade_offers_payload(canonical, save_path, prepared_save=save)}

    offer = next(
        (
            item for item in save.get("user_trade_offers", [])
            if ((item.get("proposal") or {}).get("id") or item.get("id")) == proposal_id
        ),
        None,
    )
    if not offer:
        if payload.get("summary_only") is True:
            return decline_response("not_found")
        return {"status": "not_found", "proposal_id": proposal_id}
    decision = str(payload.get("decision") or "reject")
    fingerprint = trade_offer_fingerprint(offer)
    if decision == "accept":
        if (offer.get('offer_context') or {}).get('status') != 'pending_user_review':
            return decline_response('not_pending')
        if (offer.get('proposal') or {}).get('transfers'):
            offer = deepcopy(offer)
            offer.setdefault('offer_context', {}).update(status='user_override_pending_apply', created_by_user=True,
                override_team_id=save['meta']['user_team_id'])
        save.setdefault("pending_trade_proposals", []).append(offer)
        from .transactions import apply_trade_to_state

        result = apply_trade_to_state(save, proposal_id, date=save.get("state", {}).get("current_date") or CANONICAL_START_DATE, canonical=canonical, save_label=str(save_path))
        if result.get("status") == "applied":
            mark_user_offer_status(save, proposal_id, "accepted_executed")
            for duplicate in save.get("user_trade_offers", []):
                duplicate_id = (duplicate.get("proposal") or {}).get("id") or duplicate.get("id")
                duplicate_context = duplicate.get("offer_context") or {}
                if duplicate_id != proposal_id and duplicate_context.get("status") == "pending_user_review" and trade_offer_fingerprint(duplicate) == fingerprint:
                    duplicate_context["status"] = "duplicate_offer_accepted"
                    duplicate_context["resolved_by_offer_id"] = proposal_id
            write_save(save_path, save)
        return {"status": result.get("status"), "result": result, "offers": user_trade_offers_payload(canonical, save_path)}
    offer_status = (offer.get("offer_context") or {}).get("status")
    if offer_status != "pending_user_review":
        return decline_response("rejected" if offer_status == "rejected_by_user" else "not_pending")
    for pending_offer in save.get("user_trade_offers", []):
        pending_context = pending_offer.get("offer_context") or {}
        if pending_context.get("status") == "pending_user_review" and trade_offer_fingerprint(pending_offer) == fingerprint:
            pending_context["status"] = "rejected_by_user"
            pending_context["responded_date"] = save.get("state", {}).get("current_date")
    write_save(save_path, save)
    return decline_response("rejected")


def mark_trade_finder_offer(candidate: dict[str, Any], user_team_id: str | None) -> dict[str, Any]:
    partner_id = next(
        (
            evaluation.get("perspective_team_id")
            for evaluation in candidate.get("evaluations", [])
            if evaluation.get("perspective_team_id") != user_team_id and evaluation.get("accepted")
        ),
        None,
    )
    if not partner_id:
        return candidate
    candidate["offer_context"] = {
        **(candidate.get("offer_context") or {}),
        "status": "finder_offer_pending_user_acceptance",
        "source": "trade_finder",
        "finder_partner_team_id": partner_id,
        "finder_partner_accepted": True,
    }
    return candidate


def accept_trade_finder_offer(candidate: dict[str, Any], user_team_id: str | None) -> dict[str, Any] | None:
    candidate = mark_trade_finder_offer(candidate, user_team_id)
    context = candidate.get("offer_context") or {}
    if context.get("status") != "finder_offer_pending_user_acceptance":
        return None
    for evaluation in candidate.get("evaluations", []):
        if evaluation.get("perspective_team_id") == user_team_id:
            evaluation["accepted"] = True
            evaluation["decision"] = "accept_user_selected_finder_offer"
            evaluation.setdefault("reasons", []).append("user_selected_finder_offer")
    candidate["accepted_by_all"] = True
    candidate["offer_context"] = {**context, "status": "finder_offer_user_accepted", "user_team_id": user_team_id}
    return candidate


def partner_has_accepted(candidate: dict[str, Any], user_team_id: str | None) -> bool:
    return any(
        evaluation.get("perspective_team_id") != user_team_id and evaluation.get("accepted")
        for evaluation in candidate.get("evaluations", [])
    )


def mark_user_offer_status(save: dict[str, Any], proposal_id: str, status: str) -> None:
    for offer in save.get("user_trade_offers", []):
        if ((offer.get("proposal") or {}).get("id") or offer.get("id")) == proposal_id:
            offer.setdefault("offer_context", {})["status"] = status


def season_slideshow_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """A season slideshow (year-end recap or preseason outlook). The current season's is built on first request
    when the season-end or season-start hook has not stored it yet (a new career's first outlook)."""
    from .season_slides import (available_slideshows, ensure_preseason_outlook, ensure_year_end_recap, pending_slideshow,
                                stored_outlook, stored_recap)

    save = ensure_league_save_defaults(load_save(save_path), canonical)
    kind = str(payload.get("kind") or "")
    if kind not in {"recap", "outlook"}:
        raise AppActionError("Choose the year-end recap or the preseason outlook.")
    current = str((save.get("meta") or {}).get("season") or "")
    season = str(payload.get("season") or current)
    data = stored_recap(save, season) if kind == "recap" else stored_outlook(save, season)
    if data is None and season == current:
        data = (ensure_year_end_recap(canonical, save, save_path) if kind == "recap"
                else ensure_preseason_outlook(canonical, save, save_path))
        if data is not None:
            write_save(save_path, save)
    if data is None:
        raise AppActionError("That slideshow is not available yet.")
    return {"slideshow": data, "available": available_slideshows(save), "pending": pending_slideshow(save)}


def season_slideshow_seen_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Record that a slideshow has opened, so it opens by itself only once."""
    from .season_slides import available_slideshows, mark_seen, pending_slideshow

    save = ensure_league_save_defaults(load_save(save_path), canonical)
    kind = str(payload.get("kind") or "")
    if kind not in {"recap", "outlook"}:
        raise AppActionError("Choose the year-end recap or the preseason outlook.")
    mark_seen(save, kind, str(payload.get("season") or (save.get("meta") or {}).get("season") or ""))
    write_save(save_path, save)
    return {"status": "seen", "available": available_slideshows(save), "pending": pending_slideshow(save)}


def advance_action(root: Path, canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    prepared_save = copy_plain(normalized_read_save(canonical, save_path)) if save_path.exists() else None
    saved_seed = (prepared_save or {}).get("meta", {}).get("seed")
    seed = int(payload["seed"] if payload.get("seed") is not None else (saved_seed if saved_seed is not None else 1))
    deadline_stop = None
    postseason_stop = None
    if prepared_save is not None:
        current = prepared_save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        if payload.get("postseason_exit"):
            if not postseason_exit_required(prepared_save):
                raise ValueError("The completed postseason is not awaiting a lottery handoff.")
            year = str(prepared_save["playoff_state"].get("year") or int(prepared_save["meta"]["season"][:4]) + 1)
            prepared_save["postseason_exit_confirmed"] = year
            payload = {"to_date":max(current, f"{year}-06-22"), "postseason_exit":True}
            write_save(save_path, prepared_save)
        elif postseason_exit_required(prepared_save):
            snapshot = dashboard_snapshot_payload(root, canonical, save_path, {"leader_limit":9, "prospect_limit":8})
            return {"status":"postseason_complete", "result":{"through_date":current, "games_simulated":0},
                    "home":snapshot["home"], "dashboard_snapshot":snapshot}
        if payload.get("draft_enter"):
            year = str(int(prepared_save["meta"]["season"][:4]) + 1)
            if not prepared_save.get("draft_orders", {}).get(year):
                raise ValueError("Reveal the lottery before entering draft night.")
            payload = {"to_date":max(current, f"{year}-06-25"), "draft_enter":True}
        deadline = trade_deadline_date(season_start_year_from_date(current))
        target = (
            add_days(current, int(payload["days"])) if payload.get("days") is not None
            else next_event_date(root, canonical, prepared_save) if payload.get("next_event") or payload.get("postseason_sim")
            else payload.get("to_date")
        )
        # Approval applies only when resuming from this deadline, never to an
        # earlier date or a future season's deadline.
        approved = current == deadline and payload.get("trade_deadline_confirmed") == deadline
        if target and current <= deadline <= target and not approved:
            deadline_stop = {"date": deadline, "requested_to_date": target}
            payload = {**payload, "to_date": deadline, "next_event": False}
            payload.pop("days", None)
        boundary = f"{int(prepared_save.get('meta', {}).get('season', current[:4])[:4]) + 1}-04-13"
        postseason_approved = prepared_save.get("postseason_entry_confirmed") == boundary
        if prepared_save.get("playoff_state", {}).get("games"):
            # Careers already played under the old playoff controls have
            # crossed this boundary; don't pretend their games haven't begun.
            prepared_save["postseason_entry_confirmed"] = boundary
            postseason_approved = True
        if current >= boundary and payload.get("postseason_confirmed") == boundary:
            prepared_save["postseason_entry_confirmed"] = boundary
            postseason_approved = True
        if not deadline_stop and target and not postseason_approved and (
            current <= boundary <= target
            or prepared_save.get("state", {}).get("phase") in {"play_in", "playoffs"}
        ):
            stop_date = max(current, boundary)
            postseason_stop = {"date": boundary, "requested_to_date": target}
            payload = {**payload, "to_date": stop_date, "next_event": False}
            payload.pop("days", None)
    if deadline_stop and current == deadline:
        result = {"status": "trade_deadline", "through_date": current, "games_simulated": 0}
    elif postseason_stop:
        result = advance_save(root, canonical, save_path, to_date=payload["to_date"], seed=seed,
                              prepared_save=prepared_save, stop_before_postseason_games=True)
    elif payload.get("postseason_sim") is not None:
        mode = payload["postseason_sim"]
        if mode not in {"game", "series", "all"}:
            raise ValueError("Unknown postseason simulation mode.")
        if prepared_save is None or prepared_save.get("state", {}).get("phase") not in {"play_in", "playoffs"}:
            raise ValueError("Postseason simulation is only available during the postseason.")
        if prepared_save.get("playoff_state", {}).get("status") == "completed":
            result = advance_save(root, canonical, save_path, next_event=True, seed=seed, prepared_save=prepared_save)
        else:
            advance_save(root, canonical, save_path, to_date=current, seed=seed,
                         prepared_save=prepared_save, stop_before_postseason_games=True)
            before_games = len(prepared_save.get("schedule_state", {}).get("simulated_game_ids", []))
            simulated = simulate_playoff_action(canonical, save_path, root, seed, mode="round" if mode == "series" else mode, hold_postseason=True)
            after = load_save(save_path)
            result = {**simulated["result"], "status":"stopped" if simulation_stop_requested() else simulated.get("status"),
                      "through_date":after["state"]["current_date"],
                      "games_simulated":len(after.get("schedule_state", {}).get("simulated_game_ids", [])) - before_games}
    elif payload.get("days") is not None:
        current = (prepared_save or {}).get("state", {}).get("current_date") or CANONICAL_START_DATE
        target = add_days(current, int(payload["days"]))
        checkpoint_args = (root, canonical, save_path, target, seed, int(payload.get("checkpoint_days") or 31))
        result = (
            advance_with_checkpoints(*checkpoint_args, prepared_save=prepared_save)
            if prepared_save is not None
            else advance_with_checkpoints(*checkpoint_args)
        )
    elif payload.get("to_date") and payload.get("checkpoint_days") is not None:
        # Milestone buttons still need intermediate AI checkpoints. The user
        # sees one action, but records, injuries, and team needs evolve before
        # the deadline or season-end target is reached.
        checkpoint_args = (
            root,
            canonical,
            save_path,
            str(payload["to_date"]),
            seed,
            int(payload.get("checkpoint_days") or 31),
        )
        result = (
            advance_with_checkpoints(*checkpoint_args, prepared_save=prepared_save)
            if prepared_save is not None
            else advance_with_checkpoints(*checkpoint_args)
        )
    else:
        advance_kwargs = {
            "to_date": payload.get("to_date"),
            "next_event": bool(payload.get("next_event", False)),
            "seed": seed,
            "pause_at_champion":not bool(payload.get("postseason_exit")),
        }
        if prepared_save is not None:
            advance_kwargs["prepared_save"] = prepared_save
        result = advance_save(root, canonical, save_path, **advance_kwargs)
    if bool(payload.get("process_ai", True)):
        # advance_save owns the chronological AI pass after games, health, and
        # development are committed. Re-running it here repeats expensive
        # candidate searches against an unchanged date without adding context.
        result = {
            **result,
            "ai_processing": {
                "status": "processed_during_advance",
                "applied_count": int(result.get("ai_applied_count") or 0),
            },
        }
    if not save_path.exists():
        # Retain the lightweight seam used by callers that supply their own
        # persistence layer or a mocked advancement backend.
        return {"status": "stopped" if result.get("status") == "stopped" else "advanced", "result": result, "home": home_payload(root, canonical, save_path)}
    snapshot = dashboard_snapshot_payload(
        root,
        canonical,
        save_path,
        {"leader_limit": 9, "prospect_limit": 8},
    )
    status = "stopped" if result.get("status") == "stopped" else "trade_deadline" if deadline_stop else "postseason" if postseason_stop else "advanced"
    return {"status": status, "trade_deadline_checkpoint": deadline_stop, "postseason_checkpoint": postseason_stop, "result": result, "home": snapshot["home"], "dashboard_snapshot": snapshot}


def advance_with_checkpoints(
    root: Path,
    canonical: dict[str, Any],
    save_path: Path,
    target: str,
    seed: int,
    checkpoint_days: int,
    *,
    prepared_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    # Keep the legacy argument for callers; core advancement owns daily steps.
    return advance_save(root, canonical, save_path, to_date=target, seed=seed, prepared_save=save, pause_at_champion=True)


def update_game_settings_action(canonical: dict[str, Any], save_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    game_settings = ensure_game_settings(save)
    if "press_conferences_enabled" in settings:
        game_settings["press_conferences_enabled"] = bool(settings.get("press_conferences_enabled"))
    if "coach_rests_players" in settings:
        # Let the head coach rest the GM's players by the AI coaches' rule (back-to-backs, fatigue, age, late season).
        game_settings["coach_rests_players"] = bool(settings.get("coach_rests_players"))
    current = save.get("state", {}).get("current_date")
    if current:
        save["state"]["legal_actions"] = save_legal_actions_for_date(save, current)
    write_save(save_path, save)
    return {"status": "updated", "game_settings": game_settings, "press_conferences_enabled": press_conferences_enabled(save)}


def current_game_settings(
    canonical: dict[str, Any],
    save_path: Path,
    *,
    prepared_save: dict[str, Any] | None = None,
) -> dict[str, Any]:
    save = prepared_save if prepared_save is not None else ensure_league_save_defaults(load_save(save_path), canonical)
    return ensure_game_settings(save)


def active_canonical(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    return with_transaction_context(canonical_with_save(canonical, save))


def resolve_app_save_path(save_dir: Path, payload: dict[str, Any]) -> Path:
    boundary = save_dir.resolve()
    raw = payload.get("save_path") or payload.get("path")
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            if path.parts and path.parts[0] == save_dir.name:
                path = boundary.parent / path
            else:
                path = boundary / path
    else:
        save_name = payload.get("save_name") or payload.get("save_id")
        if not save_name:
            raise AppActionError("Action requires save_path, path, save_name, or save_id.")
        name = str(save_name)
        path = boundary / (name if name.endswith(".json") else f"{name}.json")
    try:
        path = path.resolve()
        path.relative_to(boundary)
        # Recovery and locking also open predictable companion paths. Check
        # these even when the manifest is missing and only recovery remains.
        for companion in (
            previous_backup_path(path), path.with_name(path.name + ".restore-pending.nbagm.zip"),
            path.with_name(f".{path.name}.lock"), path.with_name(path.name + ".pre-history-v1.bak"),
        ):
            companion.resolve().relative_to(boundary)
    except (ValueError, OSError, RuntimeError) as exc:
        raise AppActionError("Save paths must stay inside the configured save directory.") from exc
    return path


def validate_app_save_paths(save_dir: Path, payload: dict[str, Any]) -> None:
    """Preflight both path aliases, including fields ignored by some actions."""
    for key in ("save_path", "path"):
        if payload.get(key):
            resolve_app_save_path(save_dir, {key: payload[key]})


def save_file_revision(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def normalized_read_save(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    """Reuse a dashboard-normalized save without forcing active projections."""
    key = str(save_path.resolve())
    revision = save_file_revision(save_path)
    with _READ_CACHE_GUARD:
        cached = _READ_CACHE.get(key)
        if cached and cached.get("revision") == revision and cached.get("canonical_identity") == canonical.get("_baseline_identity", id(canonical)):
            validate_save_components(save_path, cached["save"])
            _READ_CACHE[key] = _READ_CACHE.pop(key)
            return cached["save"]
    return ensure_league_save_defaults(load_save(save_path), canonical)


def dashboard_read_context(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    key = str(save_path.resolve())
    revision = save_file_revision(save_path)
    canonical_identity = canonical.get("_baseline_identity", id(canonical))
    with _READ_CACHE_GUARD:
        cached = _READ_CACHE.get(key)
        if cached and cached.get("revision") == revision and cached.get("canonical_identity") == canonical_identity:
            validate_save_components(save_path, cached["save"])
            _READ_CACHE[key] = _READ_CACHE.pop(key)
            return cached
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    context = {
        "revision": revision,
        "canonical_identity": canonical_identity,
        "save": save,
        "active": active,
        "snapshots": {},
        "phase_payloads": {},
    }
    with _READ_CACHE_GUARD:
        _READ_CACHE.pop(key, None)
        _READ_CACHE[key] = context
        while len(_READ_CACHE) > _READ_CACHE_LIMIT:
            _READ_CACHE.pop(next(iter(_READ_CACHE)))
    return context


def transaction_read_active(context: dict[str, Any]) -> dict[str, Any]:
    """Share valuations across the dashboard, feed, assets and player cards.

    The owning context is discarded whenever the save revision changes, so
    trades, contracts, health and development still get fresh projections.
    """
    cached = context.get("dashboard_active")
    if cached is None:
        cached = with_transaction_context(context["active"])
        context["dashboard_active"] = cached
    return cached


def contract_read_active(context: dict[str, Any]) -> dict[str, Any]:
    """Lazily build the expensive contract market projection once per revision."""
    cached = context.get("contract_active")
    if isinstance(cached, dict):
        return cached
    active = with_contract_context(context["active"])
    context["contract_active"] = active
    return active


def invalidate_read_cache(save_path: Path) -> None:
    with _READ_CACHE_GUARD:
        _READ_CACHE.pop(str(save_path.resolve()), None)


def user_team_abbrev(canonical: dict[str, Any], save_path: Path) -> str:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    return str(save.get("meta", {}).get("user_team_abbrev") or "GSW")


def random_team_abbrev(canonical: dict[str, Any], seed: int | None) -> str:
    teams = sorted(canonical.get("teams", []), key=lambda item: item.get("abbrev", ""))
    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    return str(rng.choice(teams)["abbrev"]) if teams else "GSW"


def safe_filename(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
    return cleaned or stable_id("save_name", value)


def add_days(value: str, days: int) -> str:
    return (date.fromisoformat(str(value)[:10]) + timedelta(days=int(days))).isoformat()


def current_draft_year(save: dict[str, Any]) -> str:
    phase = str((save.get("state") or {}).get("phase") or "")
    season = str((save.get("meta") or {}).get("season") or CANONICAL_SEASON)
    start = int(season.split("-")[0])
    if phase in {"draft_lottery", "draft", "re_signing", "free_agency", "offseason"}:
        start += 1
    return str(start + 1 if phase not in {"draft_lottery", "draft", "re_signing", "free_agency", "offseason"} else start)


def compact_position(position: Any) -> str:
    text = str(position or "-").upper().replace("POSITION_", "")
    for separator in ["/", ",", "-", " "]:
        if separator in text:
            text = text.split(separator)[0]
            break
    text = text.strip()
    return text if text in {"PG", "SG", "SF", "PF", "C"} else text[:3] or "-"


def height_label(player: dict[str, Any]) -> str:
    inches = player.get("height_inches")
    if inches:
        value = int(round(float(inches)))
        return f"{value // 12}'{value % 12}\""
    return str(player.get("height") or "--")


def health_label(state: dict[str, Any] | None, current_date: str | None = None) -> dict[str, Any]:
    if not state:
        return {"status": "healthy", "label": "Healthy"}
    status = str(state.get("availability_status") or "active")
    if status == "active":
        from .sim import rust_display
        return {"status": "healthy", "label": "Healthy", "games_missed": int(state.get("games_missed") or 0), **rust_display(state)}
    severity = state.get("injury_severity") or state.get("current_injury_severity") or "out"
    display = player_health_label(state, current_date)
    return {
        "status": status,
        "label": display.get("label") or str(severity).replace("_", " "),
        "return_date": state.get("return_date"),
        "days_left": display.get("days_left"),
        "games_missed": int(state.get("games_missed") or 0),
    }


def block_contract_terms(contract: dict[str, Any] | None, active_season: str) -> list[dict[str, Any]]:
    """Summarize remaining deals by actual extension boundaries, not annual raises."""
    contract = contract or {}
    rows = sorted((row for row in contract.get("seasons", [])
                   if str(row.get("season") or "") >= active_season and float(row.get("salary") or 0) > 0),
                  key=lambda row: str(row.get("season") or ""))
    terms = []
    signed = str(contract.get("signed_season") or "")
    previous = None
    for row in rows:
        extension = row.get("guarantee_status") == "extension"
        boundary = previous is not None and (
            extension != (previous.get("guarantee_status") == "extension")
            or (signed and str(previous.get("season")) < signed <= str(row.get("season")))
        )
        if not terms or boundary:
            terms.append({"salary": float(row["salary"]), "years": 1, "start_season": row["season"]})
        else:
            terms[-1]["years"] += 1
        previous = row
    return terms


def contract_summary(contract: dict[str, Any] | None, active_season: str = "") -> str:
    if not contract:
        return ""
    terms = block_contract_terms(contract, active_season or str(contract.get("_active_season") or ""))
    return ", ".join(f"${term['salary'] / 1_000_000:.1f}M x {term['years']}" for term in terms)


def top_trait_snapshot(attrs: dict[str, Any]) -> str:
    labels = [
        ("shooting", "shoot"),
        ("creation", "create"),
        ("defense", "def"),
        ("rim_deterrence", "rim"),
        ("passing", "pass"),
        ("rebounding", "reb"),
    ]
    top = sorted(labels, key=lambda item: float(attrs.get(item[0]) or 0.0), reverse=True)[:3]
    return ", ".join(f"{label} {float(attrs.get(key) or 0):.0f}" for key, label in top)
