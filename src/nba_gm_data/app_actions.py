from __future__ import annotations

import random
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .contract_ai import apply_contract_to_save, free_agents_report
from .draft import draft_board_report
from .ingest import build_universe
from .save import (
    advance_save,
    box_score_view,
    calendar_view,
    canonical_with_save,
    create_league_save,
    display_minutes_projection,
    ensure_game_settings,
    ensure_league_save_defaults,
    league_events_view,
    league_leaders,
    league_standings,
    load_save,
    morale_report,
    narrative_settings_view,
    pending_actions_view,
    player_attribute_summary,
    playoff_picture,
    press_conferences_enabled,
    process_ai_actions,
    save_legal_actions_for_date,
    save_status,
    simulate_next_playoff_game,
    simulate_playoff_round,
    starting_lineup_slots,
    social_feed_view,
    team_cap_summary,
    team_dashboard,
    team_rotation_projection,
    write_save,
)
from .schema import CANONICAL_START_DATE, to_plain
from .staff import (
    fire_staff_from_save,
    hire_staff_from_save,
    negotiate_staff_hire,
    staff_budget_snapshot,
    staff_grade,
    staff_market_report,
    staff_team_report,
)
from .storage import JSON_FILENAME, load_universe_json
from .transactions import (
    apply_trade_to_save,
    contract_for_player,
    evaluate_trade,
    fallback_asset_valuation,
    find_trade,
    find_trade_for_assets,
    market_trade_target_value,
    pick_asset_value,
    pick_display_label,
    pick_swap_asset_value,
    pick_swap_display_label,
    resolve_team,
    team_by_id,
    trade_candidate_with_current_asset_labels,
    trade_headline_from_payload,
    tradeable_pick_swaps_for_team,
    tradeable_picks_for_team,
    with_transaction_context,
)
from .utils import stable_id


APP_ACTION_PROTOCOL_VERSION = "app_actions_v1"
DEFAULT_SAVE_DIR = "saves"
_SAVE_LOCKS: dict[str, threading.RLock] = {}
_SAVE_LOCKS_GUARD = threading.Lock()


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
    root_path = Path(root)
    payload = dict(payload or {})
    data = canonical or load_app_canonical(root_path)
    saves = Path(save_dir) if save_dir is not None else root_path / DEFAULT_SAVE_DIR
    saves.mkdir(parents=True, exist_ok=True)

    if action == "runtime_status":
        return runtime_status(root_path, saves)
    if action == "teams":
        return teams_payload(data)
    if action == "list_saves":
        return list_saves(saves)
    if action == "create_save":
        return create_save_action(root_path, data, saves, payload)

    save_path = resolve_app_save_path(saves, payload)
    if action in MUTATING_ACTIONS:
        with save_lock(save_path):
            return dispatch_save_action(action, payload, root_path, data, save_path)
    return dispatch_save_action(action, payload, root_path, data, save_path)


MUTATING_ACTIONS = {
    "advance_save",
    "advance_free_agency",
    "apply_contract",
    "apply_trade",
    "apply_trade_candidate",
    "draft_apply_current",
    "draft_sim_all",
    "draft_sim_to_user",
    "fire_staff",
    "hire_staff",
    "negotiate_staff",
    "process_ai_actions",
    "respond_user_trade_offer",
    "set_rotation_minutes",
    "set_starting_five",
    "simulate_playoff_game",
    "simulate_playoff_round",
    "submit_free_agent_offer",
    "update_game_settings",
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
                "teams",
                "list_saves",
                "create_save",
                "home",
                "save_status",
                "team_dashboard",
                "team_assets",
                "standings",
                "league_leaders",
                "league_traits",
                "league_events",
                "social_feed",
                "calendar",
                "box_score",
                "morale",
                "free_agents",
                "free_agency_room",
                "submit_free_agent_offer",
                "advance_free_agency",
                "staff_market",
                "staff_room",
                "negotiate_staff",
                "hire_staff",
                "fire_staff",
                "draft_board",
                "draft_room",
                "draft_apply_current",
                "draft_sim_to_user",
                "draft_sim_all",
                "playoff_room",
                "simulate_playoff_game",
                "simulate_playoff_round",
                "evaluate_trade",
                "find_trade",
                "find_trade_for_assets",
                "apply_trade_candidate",
                "user_trade_offers",
                "respond_user_trade_offer",
                "set_rotation_minutes",
                "set_starting_five",
                "apply_contract",
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
        return load_universe_json(json_path)
    return to_plain(build_universe(root))


def list_saves(save_dir: Path) -> dict[str, Any]:
    saves = []
    for path in sorted(save_dir.glob("*.json")):
        try:
            save = load_save(path)
            save = ensure_league_save_defaults(save)
        except Exception as exc:
            saves.append({"path": str(path), "name": path.stem, "status": "unreadable", "error": str(exc)})
            continue
        saves.append(
            {
                "path": str(path),
                "name": path.stem,
                "status": "ok",
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
    save_path = resolve_app_save_path(save_dir, {"save_path": str(save_dir / f"{safe_filename(str(save_name))}.json")})
    save = create_league_save(
        root,
        canonical,
        team["abbrev"],
        save_path,
        seed=seed_int,
        ai_difficulty=str(payload.get("ai_difficulty") or "normal"),
    )
    ensure_game_settings(save)
    save["state"]["legal_actions"] = save_legal_actions_for_date(save, save["state"]["current_date"])
    write_save(save_path, save)
    return {
        "status": "created",
        "save_path": str(save_path),
        "save": save_status(root, canonical, save_path),
        "game_settings": save.get("game_settings", {}),
    }


def dispatch_save_action(action: str, payload: dict[str, Any], root: Path, canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    if action == "save_status":
        return {"save": save_status(root, canonical, save_path), "game_settings": current_game_settings(canonical, save_path)}
    if action == "home":
        return home_payload(root, canonical, save_path)
    if action == "team_dashboard":
        team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
        return team_dashboard(root, canonical, save_path, team)
    if action == "team_assets":
        return team_assets_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    if action == "standings":
        return league_standings(canonical, save_path)
    if action == "league_leaders":
        return league_leaders(canonical, save_path, stat=str(payload.get("stat") or "points"), limit=int(payload.get("limit") or 20))
    if action == "league_traits":
        return league_traits_payload(canonical, save_path, trait=str(payload.get("trait") or "overall"), limit=int(payload.get("limit") or 80))
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
        return free_agents_report(active, team_query=payload.get("team"), position=payload.get("position"), limit=payload.get("limit"))
    if action == "free_agency_room":
        return free_agency_room_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)), int(payload.get("seed") or 1))
    if action == "submit_free_agent_offer":
        return submit_free_agent_offer_action(canonical, save_path, payload)
    if action == "advance_free_agency":
        return advance_free_agency_action(canonical, save_path, payload, root)
    if action == "staff_market":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        return staff_market_report(canonical, save, slot=payload.get("slot"), limit=payload.get("limit"))
    if action == "staff_room":
        return staff_room_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)), slot=payload.get("slot"), limit=payload.get("limit"))
    if action == "negotiate_staff":
        return negotiate_staff_action(canonical, save_path, payload)
    if action == "hire_staff":
        return hire_staff_action(canonical, save_path, str(payload["negotiation_id"]))
    if action == "fire_staff":
        return fire_staff_action(canonical, save_path, payload)
    if action == "draft_board":
        team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
        return draft_board_report(canonical, team, str(payload.get("year") or "2026"), limit=payload.get("limit"))
    if action == "draft_room":
        return draft_room_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)), str(payload.get("year") or current_draft_year(load_save(save_path))), int(payload.get("seed") or 1))
    if action == "draft_apply_current":
        return draft_apply_current_action(canonical, save_path, payload)
    if action == "draft_sim_to_user":
        return draft_sim_action(canonical, save_path, payload, mode="to_user")
    if action == "draft_sim_all":
        return draft_sim_action(canonical, save_path, payload, mode="all")
    if action == "playoff_room":
        return playoff_room_payload(canonical, save_path)
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
        report = find_trade_for_assets(
            active,
            str(payload.get("seller_team") or user_team_abbrev(canonical, save_path)),
            payload.get("assets") or [],
            limit=int(payload.get("limit") or 10),
            seed=int(payload.get("seed") or 1),
        )
        return enhance_trade_finder_report(active, report, save_path)
    if action == "evaluate_trade":
        active = active_canonical(canonical, save_path)
        return evaluate_trade(
            active,
            str(payload["from_team"]),
            str(payload["to_team"]),
            payload.get("from_assets") or [],
            payload.get("to_assets") or [],
            seed=int(payload.get("seed") or 1),
            date=payload.get("date") or load_save(save_path).get("state", {}).get("current_date") or CANONICAL_START_DATE,
            context_ready=True,
        )
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
    if action == "narrative_settings":
        return narrative_settings_view(save_path, test_connection=bool(payload.get("test_connection", False)))
    if action == "advance_save":
        return advance_action(root, canonical, save_path, payload)
    if action == "process_ai_actions":
        return process_ai_actions(canonical, save_path, seed=int(payload.get("seed") or 1), execute=bool(payload.get("execute", True)), limit=int(payload.get("limit") or 30))
    if action == "apply_trade":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        date_value = payload.get("date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        return apply_trade_to_save(save_path, str(payload["proposal_id"]), date=str(date_value))
    if action == "apply_contract":
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        date_value = payload.get("date") or save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        return apply_contract_to_save(save_path, str(payload["negotiation_id"]), date=str(date_value))
    if action == "update_game_settings":
        return update_game_settings_action(canonical, save_path, payload.get("settings") or {})
    raise AppActionError(f"Unknown app action {action!r}")


def home_payload(root: Path, canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    return {
        "save": save_status(root, canonical, save_path),
        "pending": pending_actions_view(canonical, save_path),
        "league_events": league_events_view(canonical, save_path, limit=8, kind="transactions"),
        "game_settings": current_game_settings(canonical, save_path),
    }


def team_assets_payload(canonical: dict[str, Any], save_path: Path, team_query: str) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = with_transaction_context(canonical_with_save(canonical, save))
    team = resolve_team(active, team_query)
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
        attrs = player_attribute_summary(active, player["id"])
        totals = stats.get(player["id"], {})
        games = max(1, int(totals.get("games") or 0))
        salary = contract_summary(contract_for_player(active, player["id"]))
        players.append(
            {
                "kind": "player",
                "id": player["id"],
                "value": player["name"],
                "name": player.get("name"),
                "label": player.get("name"),
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
                "ratings": attrs,
                "trade_value": round(market_trade_target_value(player, valuation), 2),
            }
        )
    players.sort(key=lambda item: (float(item.get("trade_value") or 0), float(item.get("mpg") or 0), item.get("name") or ""), reverse=True)
    used_picks = {pick_id for pick_id, owner in (save.get("draft_pick_overrides") or {}).items() if owner == "used_draft_pick"}
    picks = []
    for pick in tradeable_picks_for_team(active, team["id"]):
        if pick.get("id") in used_picks:
            continue
        picks.append(
            {
                "kind": "pick",
                "id": pick.get("id"),
                "value": pick.get("id"),
                "label": pick_display_label(active, pick),
                "season": pick.get("season"),
                "round": pick.get("round"),
                "trade_value": round(pick_asset_value(pick, phase), 2),
            }
        )
    picks.sort(key=lambda item: (float(item.get("trade_value") or 0), str(item.get("season") or ""), -int(item.get("round") or 9)), reverse=True)
    swaps = []
    for swap in tradeable_pick_swaps_for_team(active, team["id"]):
        swaps.append(
            {
                "kind": "pick_swap",
                "id": swap.get("id"),
                "value": swap.get("id"),
                "label": swap.get("label") or pick_swap_display_label(active, swap),
                "season": swap.get("season"),
                "round": swap.get("round"),
                "trade_value": round(pick_swap_asset_value(active, swap, phase), 2),
            }
        )
    swaps.sort(key=lambda item: (float(item.get("trade_value") or 0), str(item.get("season") or "")), reverse=True)
    return {
        "team": team,
        "cap": team_cap_summary(active, save, team["id"]),
        "players": players,
        "picks": picks,
        "pick_swaps": swaps,
        "assets": [*players, *picks, *swaps],
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
        attrs = player_attribute_summary(active, player["id"])
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
            "contract": contract_summary(contract_for_player(active, player["id"])),
            "ratings": attrs,
            "overall": attrs.get("overall"),
            "offense": composite_rating(attrs, ["shooting", "creation", "passing", "rim_pressure"], [0.3, 0.3, 0.2, 0.2]),
            "defense": attrs.get("defense"),
            "spacing": composite_rating(attrs, ["shooting", "range", "release", "versatility"], [0.36, 0.36, 0.14, 0.14]),
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
        "rating_scale": "dashboard_display",
    }


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
    cleaned: dict[str, int] = {}
    for player_id, value in raw_minutes.items():
        player_id = str(player_id)
        if player_id not in roster:
            raise AppActionError(f"Player {player_id!r} is not on {team['abbrev']}.")
        minutes = int(round(float(value)))
        if minutes < 0 or minutes > 48:
            raise AppActionError("Each player must be between 0 and 48 minutes.")
        cleaned[player_id] = minutes
    total = sum(cleaned.values())
    if total != 240:
        return {"status": "blocked", "reason": "Rotation minutes must total exactly 240.", "total_minutes": total, "remaining_minutes": 240 - total}
    from .play import coach_minutes_buy_in

    head = next((slot for slot in save.get("staff_slots", []) if slot.get("team_id") == team["id"] and slot.get("slot") == "head_coach"), {})
    current_projection = team_rotation_projection(active, save, team["id"], integer=False)
    recommendations = save.setdefault("rotation_recommendations", {})
    for player_id in roster:
        if player_id not in cleaned:
            recommendations.pop(player_id, None)
            continue
        current = float(current_projection.get(player_id, display_minutes_projection(roster[player_id])))
        target = int(cleaned[player_id])
        buy_in = coach_minutes_buy_in(active, save, roster[player_id], head, current, target)
        recommendations[player_id] = {
            "player_id": player_id,
            "team_id": team["id"],
            "target_minutes": target,
            "previous_projection": round(current, 1),
            "coach_commitment": round(float(buy_in.get("commitment") or 0.0), 3),
            "coach_buy_in_factors": list(buy_in.get("factors") or []),
            "date": save.get("state", {}).get("current_date"),
            "status": "active",
            "notes": "GUI rotation target. The head coach blends this target into the rotation and normalizes total team minutes.",
        }
    write_save(save_path, save)
    return {
        "status": "updated",
        "total_minutes": total,
        "dashboard": team_dashboard(root, canonical, save_path, team["abbrev"]),
    }


def free_agency_room_payload(canonical: dict[str, Any], save_path: Path, team_query: str, seed: int = 1) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    phase = str((save.get("state") or {}).get("phase") or "")
    if phase == "free_agency" or (save.get("free_agency_state") or {}).get("status") == "active":
        from .play import initialize_free_agency_market

        save = ensure_league_save_defaults(initialize_free_agency_market(canonical, save_path, team_query, seed), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, team_query)
    report_by_id = {
        item.get("player_id") or item.get("id"): item
        for item in free_agents_report(active, team_query=team["abbrev"]).get("candidates", [])
    }
    stats = save.get("player_season_stats", {})
    players_by_id = {player["id"]: player for player in active.get("players", [])}
    pool_ids = list(save.get("free_agent_player_ids") or report_by_id.keys())
    candidates = []
    for player_id in pool_ids:
        player = players_by_id.get(player_id)
        if not player:
            continue
        market = report_by_id.get(player_id) or {}
        attrs = player_attribute_summary(active, player_id)
        totals = stats.get(player_id, {})
        games = max(1, int(totals.get("games") or 0))
        ask = round(max(2.0, float(market.get("projected_aav_millions") or 0.0) or display_minutes_projection(player) * 0.45), 1)
        candidates.append(
            {
                "id": player_id,
                "player_id": player_id,
                "name": player.get("name"),
                "position": compact_position(player.get("position")),
                "age": player.get("display_age", player.get("age")),
                "height": height_label(player),
                "mpg": display_minutes_projection(player),
                "ppg": round(float(totals.get("points") or 0.0) / games, 1) if totals else 0.0,
                "rpg": round(float(totals.get("rebounds") or 0.0) / games, 1) if totals else 0.0,
                "apg": round(float(totals.get("assists") or 0.0) / games, 1) if totals else 0.0,
                "ask_millions": ask,
                "team_fit_score": market.get("team_fit_score"),
                "ratings": attrs,
                "snapshot": top_trait_snapshot(attrs),
            }
        )
    candidates.sort(key=lambda item: (float(item.get("mpg") or 0), float((item.get("ratings") or {}).get("overall") or 0), float(item.get("ask_millions") or 0)), reverse=True)
    from .play import contract_start_season_for_signing, free_agency_bidding_wars

    state = save.get("free_agency_state") or {}
    active_offers = [offer for offer in save.get("free_agent_offers", []) if offer.get("status") == "active"]
    return {
        "team": team,
        "phase": phase,
        "state": state,
        "cap": team_cap_summary(active, save, team["id"], season=contract_start_season_for_signing(save)),
        "candidates": candidates[:80],
        "active_offers": active_offers,
        "user_offers": [offer for offer in active_offers if offer.get("source") == "user"],
        "bidding_wars": free_agency_bidding_wars(canonical, save, limit=6),
    }


def submit_free_agent_offer_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from .play import manual_save_pool_signing, signing_cap_check

    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team_query = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    player_id = str(payload.get("player_id") or payload.get("id"))
    player = next((item for item in active.get("players", []) if item.get("id") == player_id), None)
    if not player:
        raise AppActionError(f"No free agent found with id {player_id!r}.")
    years = max(1, min(5, int(payload.get("years") or 1)))
    aav = float(payload.get("aav_millions") or payload.get("aav") or 0.0)
    cap = signing_cap_check(active, save, team_query, aav, allow_tax_exceed=bool(payload.get("allow_tax_exceed", False)))
    if not cap.get("ok"):
        return {"status": "blocked", "cap_check": cap}
    negotiation = manual_save_pool_signing(active, save_path, player, team_query, years, aav, int(payload.get("seed") or 1))
    result = {"status": "offered", "cap_check": cap, "negotiation": negotiation}
    if negotiation.get("accepted") and bool(payload.get("auto_apply", False)):
        applied = apply_contract_to_save(save_path, negotiation["negotiation"]["id"], date=save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
        result["apply_result"] = applied
    return result


def advance_free_agency_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], root: Path) -> dict[str, Any]:
    del root
    from .play import advance_free_agency_day, finish_free_agency_phase, initialize_free_agency_market, simulate_free_agency_to_end

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    seed = int(payload.get("seed") or 1)
    mode = str(payload.get("mode") or "day")
    initialize_free_agency_market(canonical, save_path, team, seed)
    if mode == "end":
        result = simulate_free_agency_to_end(canonical, save_path, team, seed)
        finish_free_agency_phase(canonical, save_path)
    else:
        result = advance_free_agency_day(canonical, save_path, team, seed)
    return {"status": "advanced", "result": result, "room": free_agency_room_payload(canonical, save_path, team, seed)}


def staff_room_payload(canonical: dict[str, Any], save_path: Path, team_query: str, slot: str | None = None, limit: int | None = None) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team_report = staff_team_report(canonical, save, team_query)
    market = staff_market_report(canonical, save, slot=slot, limit=limit or 30)
    return {"team_report": team_report, "market": market}


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
    return {"status": "negotiated", "negotiation": negotiation, "room": staff_room_payload(canonical, save_path, str(payload.get("team") or user_team_abbrev(canonical, save_path)), slot=payload.get("slot"))}


def hire_staff_action(canonical: dict[str, Any], save_path: Path, negotiation_id: str) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    result = hire_staff_from_save(save, negotiation_id)
    write_save(save_path, save)
    return {"status": result.get("status"), "result": result, "room": staff_room_payload(canonical, save_path, user_team_abbrev(canonical, save_path))}


def fire_staff_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_team(canonical, str(payload.get("team") or user_team_abbrev(canonical, save_path)))
    result = fire_staff_from_save(save, team["id"], str(payload["slot"]), reason=payload.get("reason") or "user decision")
    write_save(save_path, save)
    return {"status": result.get("status"), "result": result, "room": staff_room_payload(canonical, save_path, team["abbrev"])}


def draft_room_payload(canonical: dict[str, Any], save_path: Path, team_query: str, year: str, seed: int = 1) -> dict[str, Any]:
    from .play import current_draft_selection, ensure_live_draft_state

    save = ensure_league_save_defaults(load_save(save_path), canonical)
    phase = str((save.get("state") or {}).get("phase") or "")
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, team_query)
    existing_state = save.get("draft_state") or {}
    if phase != "draft" and existing_state.get("status") not in {"in_progress", "completed"}:
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
            "upcoming": [],
            "draft_board": draft_board_report(active, team["abbrev"], str(year), limit=24),
            "trade_news": [],
            "notes": "Draft-night controls unlock when the save reaches the draft phase.",
        }
    state = ensure_live_draft_state(canonical, save_path, str(year), seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, team_query)
    current = current_draft_selection(state)
    pending = (state.get("draft") or {}).get("pending_draft_selections") or []
    index = int(state.get("current_index") or 0)
    next_user = next(
        (
            item
            for item in pending[index:]
            if (item.get("selection") or {}).get("team_id") == team["id"]
        ),
        None,
    )
    board_team = team_by_id(active, (current.get("selection") or {}).get("team_id"))["abbrev"] if current else team["abbrev"]
    return {
        "year": str(year),
        "team": team,
        "state": {
            "status": state.get("status"),
            "current_index": index,
            "total_picks": len(pending),
            "applied_selection_ids": state.get("applied_selection_ids") or [],
        },
        "current_selection": current,
        "next_user_selection": next_user,
        "upcoming": pending[index:index + 18],
        "draft_board": draft_board_report(active, board_team, str(year), limit=18),
        "trade_news": list(state.get("ai_draft_trade_news_queue") or []),
    }


def draft_apply_current_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from .play import apply_current_draft_selection, current_draft_selection, ensure_live_draft_state

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    year = str(payload.get("year") or current_draft_year(save))
    seed = int(payload.get("seed") or 1)
    if str((save.get("state") or {}).get("phase") or "") != "draft" and (save.get("draft_state") or {}).get("status") not in {"in_progress", "completed"}:
        return {"status": "blocked", "notes": "Draft controls unlock during the draft phase.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    state = ensure_live_draft_state(canonical, save_path, year, seed)
    current = current_draft_selection(state)
    if not current:
        return {"status": "completed", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    result = apply_current_draft_selection(save_path, current, canonical=canonical, user_team=team, seed=seed)
    return {"status": result.get("status"), "result": result, "room": draft_room_payload(canonical, save_path, team, year, seed)}


def draft_sim_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], mode: str) -> dict[str, Any]:
    from .play import ensure_live_draft_state, sim_entire_draft, sim_to_next_user_pick

    team = str(payload.get("team") or user_team_abbrev(canonical, save_path))
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    year = str(payload.get("year") or current_draft_year(save))
    seed = int(payload.get("seed") or 1)
    if str((save.get("state") or {}).get("phase") or "") != "draft" and (save.get("draft_state") or {}).get("status") not in {"in_progress", "completed"}:
        return {"status": "blocked", "notes": "Draft controls unlock during the draft phase.", "room": draft_room_payload(canonical, save_path, team, year, seed)}
    ensure_live_draft_state(canonical, save_path, year, seed)
    result = sim_entire_draft(save_path, canonical=canonical, user_team=team, seed=seed) if mode == "all" else sim_to_next_user_pick(canonical, save_path, team, seed=seed)
    return {"status": "simulated", "result": result, "room": draft_room_payload(canonical, save_path, team, year, seed)}


def playoff_room_payload(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    picture = playoff_picture(canonical, save_path)
    teams = {team["id"]: team for team in canonical.get("teams", [])}

    def team_ref(team_id: str | None) -> dict[str, Any] | None:
        if not team_id:
            return None
        team = teams.get(team_id)
        return {"id": team_id, "abbrev": team.get("abbrev", team_id) if team else team_id, "name": team.get("name") if team else team_id}

    state = dict(save.get("playoff_state") or picture.get("playoff_state") or {})
    series_rows = []
    for series in state.get("series", []) or []:
        team_ids = list(series.get("team_ids") or [])
        wins = series.get("wins") or {}
        series_rows.append(
            {
                **series,
                "teams": [team_ref(team_id) for team_id in team_ids],
                "score": [int(wins.get(team_id, 0)) for team_id in team_ids],
                "winner": team_ref(series.get("winner_team_id")),
            }
        )
    return {
        "current_date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "status": state.get("status") or "picture",
        "round": state.get("round") or "picture",
        "champion": team_ref(state.get("champion_team_id")),
        "picture": picture.get("picture", {}),
        "playoff_state": state,
        "series": series_rows,
        "games": state.get("games") or [],
    }


def simulate_playoff_action(canonical: dict[str, Any], save_path: Path, root: Path, seed: int, mode: str) -> dict[str, Any]:
    result = (
        simulate_playoff_round(canonical, save_path, seed=seed, root=root)
        if mode == "round"
        else simulate_next_playoff_game(canonical, save_path, seed=seed, root=root)
    )
    return {"status": result.get("status") or "simulated", "result": result, "room": playoff_room_payload(canonical, save_path)}


def enhance_trade_finder_report(canonical: dict[str, Any], report: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    user_team_id = save.get("meta", {}).get("user_team_id")
    candidates = []
    for candidate in report.get("candidates", []):
        candidate = trade_candidate_with_current_asset_labels(canonical, candidate)
        candidate["headline"] = trade_headline_from_payload(candidate.get("proposal") or {})
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
    write_save(save_path, save)
    date_value = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    result = apply_trade_to_save(save_path, proposal_id, date=str(date_value))
    return {"status": result.get("status"), "result": result, "home": home_payload(Path("."), canonical, save_path)}


def user_trade_offers_payload(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = active_canonical(canonical, save_path)
    offers = []
    for offer in save.get("user_trade_offers", []):
        context = offer.get("offer_context") or {}
        if context.get("status") != "pending_user_review":
            continue
        item = trade_candidate_with_current_asset_labels(active, offer)
        item["headline"] = trade_headline_from_payload(item.get("proposal") or {})
        offers.append(item)
    return {"offer_count": len(offers), "offers": offers}


def respond_user_trade_offer_action(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    proposal_id = str(payload.get("proposal_id") or "")
    if not proposal_id:
        raise AppActionError("Action requires proposal_id.")
    offer = next(
        (
            item for item in save.get("user_trade_offers", [])
            if ((item.get("proposal") or {}).get("id") or item.get("id")) == proposal_id
        ),
        None,
    )
    if not offer:
        return {"status": "not_found", "proposal_id": proposal_id}
    decision = str(payload.get("decision") or "reject")
    if decision == "accept":
        save.setdefault("pending_trade_proposals", []).append(offer)
        write_save(save_path, save)
        result = apply_trade_to_save(save_path, proposal_id, date=save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        mark_user_offer_status(save, proposal_id, "accepted_executed" if result.get("status") == "applied" else "stale_asset_moved")
        write_save(save_path, save)
        return {"status": result.get("status"), "result": result, "offers": user_trade_offers_payload(canonical, save_path)}
    mark_user_offer_status(save, proposal_id, "rejected_by_user")
    write_save(save_path, save)
    return {"status": "rejected", "offers": user_trade_offers_payload(canonical, save_path)}


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


def advance_action(root: Path, canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    seed = int(payload.get("seed") or 1)
    if payload.get("days") is not None:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
        target = add_days(current, int(payload["days"]))
        result = advance_with_checkpoints(root, canonical, save_path, target, seed, int(payload.get("checkpoint_days") or 31))
    else:
        result = advance_save(
            root,
            canonical,
            save_path,
            to_date=payload.get("to_date"),
            next_event=bool(payload.get("next_event", False)),
            seed=seed,
        )
    if bool(payload.get("process_ai", True)):
        result = {**result, "ai_processing": process_ai_actions(canonical, save_path, seed=seed, execute=True, limit=int(payload.get("ai_limit") or 30))}
    return {"status": "advanced", "result": result, "home": home_payload(root, canonical, save_path)}


def advance_with_checkpoints(root: Path, canonical: dict[str, Any], save_path: Path, target: str, seed: int, checkpoint_days: int) -> dict[str, Any]:
    result: dict[str, Any] | None = None
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    checkpoint_days = max(1, int(checkpoint_days))
    while current < target:
        step = min(add_days(current, checkpoint_days), target)
        result = advance_save(root, canonical, save_path, to_date=step, seed=seed)
        process_ai_actions(canonical, save_path, seed=seed, execute=True, limit=30)
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        current = save.get("state", {}).get("current_date") or step
    return result or advance_save(root, canonical, save_path, to_date=target, seed=seed)


def update_game_settings_action(canonical: dict[str, Any], save_path: Path, settings: dict[str, Any]) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    game_settings = ensure_game_settings(save)
    if "press_conferences_enabled" in settings:
        game_settings["press_conferences_enabled"] = bool(settings.get("press_conferences_enabled"))
    current = save.get("state", {}).get("current_date")
    if current:
        save["state"]["legal_actions"] = save_legal_actions_for_date(save, current)
    write_save(save_path, save)
    return {"status": "updated", "game_settings": game_settings, "press_conferences_enabled": press_conferences_enabled(save)}


def current_game_settings(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    return ensure_game_settings(save)


def active_canonical(canonical: dict[str, Any], save_path: Path) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    return with_transaction_context(canonical_with_save(canonical, save))


def resolve_app_save_path(save_dir: Path, payload: dict[str, Any]) -> Path:
    raw = payload.get("save_path") or payload.get("path")
    if raw:
        path = Path(raw)
        if path.is_absolute():
            return path
        if path.parts and path.parts[0] == save_dir.name:
            return save_dir.parent / path
        return save_dir / path
    save_name = payload.get("save_name") or payload.get("save_id")
    if save_name:
        name = str(save_name)
        return save_dir / (name if name.endswith(".json") else f"{name}.json")
    raise AppActionError("Action requires save_path, path, save_name, or save_id.")


def save_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _SAVE_LOCKS_GUARD:
        lock = _SAVE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _SAVE_LOCKS[key] = lock
        return lock


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
    season = str((save.get("meta") or {}).get("season") or "2025-26")
    start = int(season.split("-")[0])
    if phase in {"draft_lottery", "draft", "free_agency", "offseason"}:
        start += 1
    return str(start + 1 if phase not in {"draft_lottery", "draft", "free_agency", "offseason"} else start)


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
    del current_date
    if not state:
        return {"status": "healthy", "label": "Healthy"}
    status = str(state.get("availability_status") or "active")
    if status == "active":
        return {"status": "healthy", "label": "Healthy", "games_missed": int(state.get("games_missed") or 0)}
    severity = state.get("injury_severity") or state.get("current_injury_severity") or "out"
    return {
        "status": status,
        "label": str(severity).replace("_", " "),
        "return_date": state.get("return_date"),
        "games_missed": int(state.get("games_missed") or 0),
    }


def contract_summary(contract: dict[str, Any] | None) -> str:
    if not contract:
        return ""
    pieces = []
    for season in (contract.get("seasons") or [])[:4]:
        salary = season.get("salary")
        if salary is None:
            continue
        pieces.append(f"{season.get('season')} ${float(salary) / 1_000_000:.1f}M")
    return " / ".join(pieces)


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
