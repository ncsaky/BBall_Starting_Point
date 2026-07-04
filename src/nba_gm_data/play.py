from __future__ import annotations

import os
import random
import shutil
import sys
import textwrap
from bisect import bisect_left, bisect_right
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

from .animation import loading_screen
from .contract_ai import (
    apply_contract_to_save,
    evaluate_signing,
    extension_candidates_report,
    free_agents_report,
    negotiate_extension,
    projected_retirement_start_year,
    simulate_free_agency,
)
from .draft import apply_draft_selection_to_save, find_draft_trade, pick_recommendations, simulate_draft
from .save import (
    advance_save,
    add_news,
    auto_fill_rosters,
    box_score_view,
    calendar_view,
    canonical_with_save,
    complete_offseason_and_rollover,
    create_league_save,
    ensure_league_save_defaults,
    display_minutes_projection,
    prepare_free_agency_pool,
    prune_rotation_recommendations,
    recent_rookie_protected_player_ids,
    hold_press_conference,
    league_leaders,
    league_events_view,
    league_standings,
    playoff_leaders,
    load_save,
    morale_report,
    pending_actions_view,
    playoff_picture,
    process_ai_actions,
    propose_trade_to_save,
    narrative_settings_view,
    run_draft_lottery,
    save_status,
    set_save_date_phase,
    simulate_next_playoff_game,
    simulate_playoff_round,
    start_playoffs,
    starting_lineup_slots,
    social_feed_view,
    team_cap_summary,
    team_dashboard,
    player_attribute_summary,
    player_salary_table,
    update_narrative_settings,
    ROSTER_SEASON_MAXIMUM,
    trade_deadline_date,
    season_start_year_from_date,
    extension_deadline_date,
    write_save,
)
from .narrative import hydrate_social_items, press_cache_entry
from .staff import ROLE_LABELS, STAFF_SLOTS, fire_staff_from_save, hire_staff_from_save, negotiate_staff_hire, staff_budget_snapshot, staff_effect_summary, staff_market_report, staff_role_effect, staff_team_report
from .schema import CANONICAL_START_DATE
from .traits import TRAIT_LABELS
from .transactions import apply_trade_to_save, canonical_with_pending_pick_terms, candidate_from_evaluation, clean_pick_protection_summary, contract_for_player, current_salary, evaluate_trade, fallback_asset_valuation, find_trade, find_trade_for_assets, market_trade_target_value, pick_asset_value, pick_by_id, pick_display_label, pick_obligation_context_note, pick_season_start, pick_swap_asset_value, pick_swap_display_label, player_by_id, player_health_risk, proposal_asset_identity_keys, protected_pick_fallback_is_distinct, prune_trade_offers_touching_assets, recently_signed_player_ids, recently_traded_player_ids, resolve_team, team_by_id, trade_apply_authorized, trade_candidate_with_current_asset_labels, trade_headline_from_payload, trade_result_with_pick_terms, tradeable_pick_swaps_for_team, tradeable_picks_for_team, with_transaction_context
from .utils import clamp, stable_id


def run_play_session(root: str | Path, canonical: dict[str, Any], save_path: str | Path | None = None, team: str | None = None, seed: int | None = None) -> int:
    root = Path(root)
    save_path = choose_save_path(root, canonical, save_path, team, seed)
    session_seed = int(seed if seed is not None else load_save(save_path).get("meta", {}).get("seed") or 1)
    clear_screen()
    while True:
        forced_result = handle_forced_phase(root, canonical, save_path, session_seed)
        if forced_result == "quit":
            print("Saved. See you next time.")
            return 0
        if forced_result:
            continue
        clear_screen()
        print_home(root, canonical, save_path)
        try:
            choice = input(style("> Pick a number: ", "prompt")).strip()
        except EOFError:
            print("\nSaved. See you next time.")
            return 0
        if choice in {"0", "q", "quit", "exit"}:
            print("Saved. See you next time.")
            return 0
        try:
            handle_choice(root, canonical, save_path, choice, session_seed)
        except (ValueError, FileNotFoundError, KeyError) as exc:
            pause(f"Could not complete action: {exc}")


def choose_save_path(root: Path, canonical: dict[str, Any], save_path: str | Path | None, team: str | None, seed: int | None) -> Path:
    saves_dir = root / "saves"
    saves_dir.mkdir(exist_ok=True)
    if save_path is not None:
        path = Path(save_path)
        if not path.exists():
            save_seed = new_save_seed(seed)
            chosen_team = resolve_chosen_team(canonical, team, save_seed)
            difficulty = choose_difficulty()
            path = unique_save_path(path)
            create_league_save(root, canonical, chosen_team, path, seed=save_seed, ai_difficulty=difficulty)
            pause(f"Created new save: {path}")
        else:
            write_save(path, ensure_league_save_defaults(load_save(path), canonical))
        return path

    existing = sorted(saves_dir.glob("*.json"))
    print_title("NBA GM Sandbox")
    if existing:
        print("Choose a save to load, or create a new one.")
        for idx, path in enumerate(existing, start=1):
            label = path.name
            try:
                save = load_save(path)
                label = f"{path.name}  ({save.get('meta', {}).get('user_team_abbrev')} | {save.get('meta', {}).get('season')} | {save.get('state', {}).get('current_date')})"
            except (OSError, ValueError):
                pass
            print(f"{idx:>2}. {label}")
        print(f"{len(existing) + 1:>2}. Create new save")
        print(f"{len(existing) + 2:>2}. Delete a save")
        print(f"{len(existing) + 3:>2}. Delete all saves")
        choice = pick_number("Save", 1, len(existing) + 3, default=1)
        if choice <= len(existing):
            path = existing[choice - 1]
            write_save(path, ensure_league_save_defaults(load_save(path), canonical))
            return path
        if choice == len(existing) + 2:
            delete_save_prompt(existing)
            return choose_save_path(root, canonical, save_path, team, seed)
        if choice == len(existing) + 3:
            delete_all_saves_prompt(existing)
            return choose_save_path(root, canonical, save_path, team, seed)
    save_seed = new_save_seed(seed)
    chosen_team = resolve_chosen_team(canonical, team, save_seed)
    difficulty = choose_difficulty()
    default_path = saves_dir / f"{chosen_team.lower()}_test.json"
    raw = input(f"Save path [{default_path}]: ").strip()
    path = Path(raw) if raw else unique_save_path(default_path)
    if raw and path.exists():
        path = unique_save_path(path)
        print(f"That save exists. Using {path} instead.")
    create_league_save(root, canonical, chosen_team, path, seed=save_seed, ai_difficulty=difficulty)
    pause(f"Created new save: {path}")
    return path


def unique_save_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix or ".json"
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem}{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def new_save_seed(seed: int | None) -> int:
    if seed is not None:
        return int(seed)
    return random.SystemRandom().randrange(1, 2_147_483_647)


def resolve_chosen_team(canonical: dict[str, Any], team: str | None, seed: int) -> str:
    if team and team.strip().lower() not in {"random", "rand", "random_team"}:
        return team.strip().upper()
    if team and team.strip().lower() in {"random", "rand", "random_team"}:
        return deterministic_random_team(canonical, seed)
    return choose_team(canonical, seed)


def deterministic_random_team(canonical: dict[str, Any], seed: int) -> str:
    teams = sorted(canonical.get("teams", []), key=lambda item: item["abbrev"])
    if not teams:
        raise ValueError("No teams available for random team selection.")
    rng = random.Random(f"{seed}:new_save_random_team")
    return rng.choice(teams)["abbrev"]


def choose_team(canonical: dict[str, Any], seed: int = 1) -> str:
    teams = sorted(canonical.get("teams", []), key=lambda item: item["abbrev"])
    print_title("Choose Team")
    random_abbrev = deterministic_random_team(canonical, seed)
    print(f" 1. Random team ({random_abbrev})")
    for idx, team in enumerate(teams, start=2):
        print(f"{idx:>2}. {team['abbrev']}  {team['name']}")
    choice = pick_number("Team", 1, len(teams) + 1, default=1)
    if choice == 1:
        return random_abbrev
    return teams[choice - 2]["abbrev"]


def choose_difficulty() -> str:
    print_title("AI Difficulty")
    print("1. Normal - balanced negotiation and trade AI")
    print("2. Easy   - slightly friendlier offers and more AI mistakes")
    print("3. Hard   - tighter AI thresholds and fewer giveaways")
    choice = pick_number("Difficulty", 1, 3, default=1)
    return {1: "normal", 2: "easy", 3: "hard"}[choice]


def delete_save_prompt(existing: list[Path]) -> None:
    print_title("Delete Save")
    if not existing:
        pause("No saves to delete.")
        return
    for idx, path in enumerate(existing, start=1):
        print(f"{idx:>2}. {path.name}")
    print(" 0. Back")
    choice = pick_number("Delete", 0, len(existing), default=0)
    if choice == 0:
        return
    target = existing[choice - 1]
    confirmation = input(f"Type DELETE to remove {target.name}: ").strip()
    if confirmation == "DELETE":
        target.unlink(missing_ok=True)
        pause(f"Deleted {target.name}.")
    else:
        pause("Delete cancelled.")


def delete_all_saves_prompt(existing: list[Path]) -> None:
    print_title("Delete All Saves")
    if not existing:
        pause("No saves to delete.")
        return
    for path in existing:
        print(f"  - {path.name}")
    confirmation = input(f"Type DELETE ALL to remove all {len(existing)} save file(s): ").strip()
    if confirmation != "DELETE ALL":
        pause("Delete-all cancelled.")
        return
    for path in existing:
        path.unlink(missing_ok=True)
    pause(f"Deleted {len(existing)} save file(s).")


OFFSEASON_PHASES = {"draft_lottery", "draft", "free_agency", "offseason"}
PLAYOFF_PHASES = {"play_in", "playoffs"}


def handle_forced_phase(root: Path, canonical: dict[str, Any], save_path: Path, seed: int) -> str | None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    phase = save.get("state", {}).get("phase")
    user_team = save.get("meta", {}).get("user_team_abbrev") or "GSW"
    if user_staff_retention_window(save):
        return staff_retention_room(canonical, save_path, user_team, seed, forced=True) or "handled"
    if phase in {"training_camp", "preseason", "regular_season"} and user_roster_cutdown(save):
        return roster_cutdown_room(root, canonical, save_path, user_team, seed, forced=True) or "handled"
    if save.get("pending_press_events"):
        return forced_press_event_room(canonical, save_path, user_team, seed) or "handled"
    if save.get("pending_offseason_review"):
        return forced_offseason_review_room(canonical, save_path, user_team) or "handled"
    if phase in PLAYOFF_PHASES:
        return playoff_room(root, canonical, save_path, seed, forced=True) or "handled"
    if phase == "draft_lottery":
        return forced_lottery_room(canonical, save_path, user_team, seed) or "handled"
    if phase == "draft":
        return draft_room(canonical, save_path, user_team, seed, forced=True) or "handled"
    if phase == "free_agency":
        return free_agency_room(canonical, save_path, user_team, seed, forced=True) or "handled"
    return None


def user_roster_cutdown(save: dict[str, Any]) -> dict[str, Any] | None:
    user_team_id = save.get("meta", {}).get("user_team_id")
    return next((item for item in save.get("pending_roster_cutdowns", []) if item.get("team_id") == user_team_id), None)


def user_staff_retention_window(save: dict[str, Any]) -> dict[str, Any] | None:
    user_team_id = save.get("meta", {}).get("user_team_id")
    return next(
        (
            item for item in save.get("staff_retention_windows", [])
            if item.get("team_id") == user_team_id and item.get("status") == "pending_user_decision"
        ),
        None,
    )


def staff_retention_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, forced: bool = False) -> str:
    while True:
        clear_screen()
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        window = user_staff_retention_window(save)
        if not window:
            clear_screen()
            return "done"
        active = canonical_with_save(canonical, save)
        staff = next((item for item in save.get("staff_slots", []) if item.get("id") == window.get("staff_id")), {})
        print_title("Staff Contract Expiration")
        print(f"{window.get('team_abbrev')} {ROLE_LABELS.get(window.get('slot'), window.get('slot'))}: {window.get('staff_name')}")
        print("You must resolve this role before advancing.")
        current_salary = float((staff.get("contract") or {}).get("annual_salary_millions") or 2.0)
        ask = round(max(0.75, current_salary * 1.08), 2)
        asking_years = int((staff.get("contract") or {}).get("asking_years") or 2)
        budget = staff_budget_snapshot(canonical, save, window["team_id"], window["slot"], 0.0)
        print(
            f"Ask: ${ask:.2f}M/{asking_years}y | "
            f"Available for this role: ${float(budget.get('max_offer_millions') or 0):.2f}M"
        )
        print_staff_effects_for_member(staff)
        print_rule()
        print("1. Re-sign current staff member")
        print("2. Replace from staff market")
        print("3. Accept interim replacement")
        print("4. Staff room / budget")
        print("0. Save and quit" if forced else "0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return "quit" if forced else "back"
        if choice == "1":
            attempt_staff_retention_resign(canonical, save_path, window, seed)
        elif choice == "2":
            negotiate_staff_from_menu(canonical, save_path, user_team, seed, forced_slot=window.get("slot"))
            mark_staff_retention_resolved_if_changed(save_path, window)
        elif choice == "3":
            save = ensure_league_save_defaults(load_save(save_path), canonical)
            result = fire_staff_from_save(save, window["team_id"], window["slot"])
            for item in save.get("staff_retention_windows", []):
                if item.get("id") == window.get("id"):
                    item["status"] = "resolved_interim_accepted"
            write_save(save_path, save)
            pause(f"Interim accepted: {(result.get('interim_staff') or {}).get('name')}")
        elif choice == "4":
            staff_room(canonical, save_path, user_team, seed)


def print_staff_effects_for_member(staff: dict[str, Any]) -> None:
    for row in (staff.get("effect_rows") or [])[:4]:
        print_staff_effect_row(row)
    if not staff.get("effect_rows"):
        from .staff import staff_effect_rows

        for row in staff_effect_rows(staff)[:4]:
            print_staff_effect_row(row)


def attempt_staff_retention_resign(canonical: dict[str, Any], save_path: Path, window: dict[str, Any], seed: int) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    staff = next((item for item in save.get("staff_slots", []) if item.get("id") == window.get("staff_id")), None)
    if not staff:
        pause("That staff member is no longer active.")
        return
    current_salary = float((staff.get("contract") or {}).get("annual_salary_millions") or 2.0)
    ask = round(max(0.75, current_salary * 1.08), 2)
    budget = staff_budget_snapshot(canonical, save, window["team_id"], window["slot"], 0.0)
    max_offer = float(budget.get("max_offer_millions") or 0.0)
    default = min(ask, max_offer)
    print_title("Staff Re-Signing")
    print(f"Ask: ${ask:.2f}M/year | Max legal offer: ${max_offer:.2f}M/year")
    if max_offer <= 0:
        pause("No staff-budget room remains. Replace from market or accept an interim.")
        return
    raw = input(f"Offer annual salary [{default:.2f}]: ").strip()
    try:
        offer = float(raw) if raw else default
    except ValueError:
        offer = default
    offer = round(max(0.1, min(offer, max_offer)), 2)
    years = pick_number("Years", 1, 5, default=2)
    interest = offer_interest_score(offer, ask, years, 2, 58.0 + min(20.0, staff_grade_like(staff) / 4.0))
    print_interest_read(interest, {"money": f"${offer:.2f}M vs ${ask:.2f}M ask", "years": f"{years} offered", "budget room": f"${max_offer:.2f}M max"})
    if interest < 58:
        pause("They are not ready to re-sign at that number.")
        return
    staff.setdefault("contract", {})["annual_salary_millions"] = offer
    staff["contract"]["years_remaining"] = years
    staff["market_status"] = "employed"
    staff["status"] = "active"
    for item in save.get("staff_retention_windows", []):
        if item.get("id") == window.get("id"):
            item["status"] = "resolved_re_signed"
    headline = f"{window.get('team_abbrev')} re-signs {staff.get('name')} as {ROLE_LABELS.get(window.get('slot'), window.get('slot'))}."
    add_news(save, "staff_hire", headline)
    from .save import queue_aggregated_press_event

    queue_aggregated_press_event(save, "staff_hire", headline, [window.get("team_id")])
    write_save(save_path, save)
    pause("Staff contract re-signed.")


def staff_grade_like(staff: dict[str, Any]) -> float:
    values = [float(value) for value in (staff.get("skill_traits") or {}).values()]
    return sum(values) / len(values) if values else 55.0


def mark_staff_retention_resolved_if_changed(save_path: Path, window: dict[str, Any]) -> None:
    save = load_save(save_path)
    current = next((item for item in save.get("staff_slots", []) if item.get("team_id") == window.get("team_id") and item.get("slot") == window.get("slot")), {})
    if current.get("id") == window.get("staff_id"):
        return
    for item in save.get("staff_retention_windows", []):
        if item.get("id") == window.get("id"):
            item["status"] = "resolved_replaced"
    write_save(save_path, save)


def roster_cutdown_room(root: Path, canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, forced: bool = False) -> str:
    while True:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        cutdown = user_roster_cutdown(save)
        if not cutdown:
            clear_screen()
            return "done"
        active = canonical_with_save(canonical, save)
        team = resolve_team(active, user_team)
        roster = sorted(
            [player for player in active.get("players", []) if player.get("team_id") == team["id"]],
            key=display_minutes_projection,
            reverse=True,
        )
        clear_screen()
        print_title(f"Mandatory Roster Cutdown | {team['abbrev']}")
        print(
            f"{team['abbrev']} has {len(roster)} players. "
            f"Cut to {cutdown.get('target_count') or ROSTER_SEASON_MAXIMUM} before opening night."
        )
        print_rule()
        print("1. Cut a player")
        print("2. Team dashboard")
        if "trades" in legal_actions_for_current(save):
            print("3. Trade room")
        print("0. Save and quit" if forced else "0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return "quit" if forced else "back"
        if choice == "1":
            cut_player_from_roster(canonical, save_path, team["abbrev"])
        elif choice == "2":
            print_dashboard(root, canonical, save_path, team["abbrev"], user_team=user_team, seed=seed)
        elif choice == "3" and "trades" in legal_actions_for_current(save):
            trade_room(active, save_path, user_team, seed)


def cut_player_from_roster(canonical: dict[str, Any], save_path: Path, team_abbrev: str) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, team_abbrev)
    roster = sorted(
        [
            player for player in active.get("players", [])
            if player.get("team_id") == team["id"]
            and player.get("id") not in recent_rookie_protected_player_ids(save)
        ],
        key=lambda player: (
            display_minutes_projection(player),
            float((player_attribute_summary(active, player["id"]) or {}).get("overall") or 0.0),
            str(player.get("name") or ""),
        ),
    )
    if not roster:
        pause("No cuttable players are available. Current and prior-year draftees are protected from cutdowns.")
        return
    season = contract_start_season_for_signing(save)
    stats = save.get("player_season_stats", {})
    print_title(f"Cut Player | {team['abbrev']}")
    print(" #  Player                   Pos Age  MPG  PPG  RPG  APG   OVR  Health        Contract")
    for idx, player in enumerate(roster, start=1):
        attrs = player_attribute_summary(active, player["id"])
        totals = stats.get(player["id"], {})
        health = next((state for state in save.get("health_states", []) if state.get("player_id") == player["id"]), {})
        print(
            f"{idx:>2}. {player.get('name', ''):<24} {compact_position(player.get('position')):<3} "
            f"{age_text(player, 3)} {display_minutes_projection(player):>4.0f} "
            f"{per_game_from_totals(totals, 'points'):>4.1f} {per_game_from_totals(totals, 'rebounds'):>4.1f} "
            f"{per_game_from_totals(totals, 'assists'):>4.1f} {float(attrs.get('overall') or 0):>5.1f} "
            f"{trade_health_text(health):<13} {salary_summary(player_salary_table(active, player['id']), season)}"
        )
    print(" 0. Back")
    choice = pick_number("Cut", 0, len(roster), default=0)
    if choice == 0:
        clear_screen()
        return
    player = roster[choice - 1]
    if not yes_no(f"Waive {player['name']} from {team['abbrev']}?"):
        return
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    date_value = save.get("state", {}).get("current_date")
    save.setdefault("roster_overrides", {})[player["id"]] = None
    save.setdefault("free_agent_player_ids", [])
    if player["id"] not in save["free_agent_player_ids"]:
        save["free_agent_player_ids"].append(player["id"])
        save["free_agent_player_ids"] = sorted(save["free_agent_player_ids"])
    save.setdefault("released_free_agents", {})[player["id"]] = {
        "player_id": player["id"],
        "player_name": player.get("name"),
        "waived_by_team_id": team["id"],
        "waived_by_team_abbrev": team.get("abbrev"),
        "release_date": date_value,
        "status": "available",
    }
    save.setdefault("rotation_recommendations", {}).pop(player["id"], None)
    save.setdefault("rotation_snapshots", {}).pop(team["id"], None)
    add_news(
        save,
        "roster_cut",
        f"{team['abbrev']} waived {player['name']} to reach the roster limit.",
        date_value=date_value,
    )
    save.setdefault("transaction_logs", []).append(
        {
            "id": stable_id("transaction_log", "roster_cut", date_value, team["id"], player["id"]),
            "date": date_value,
            "transaction_type": "roster_cut",
            "proposal_id": stable_id("roster_cut", date_value, team["id"], player["id"]),
            "status": "applied_to_save_ledger",
            "teams": [team["id"]],
            "assets": {"player_id": player["id"], "name": player.get("name"), "waived_by_team_id": team["id"]},
            "evaluations": [],
            "source_ids": ["src_contract_market_config_v1"],
            "notes": "User manually waived this player; strong released players can draw AI in-season free-agent interest on the next advancement.",
        }
    )
    save = ensure_league_save_defaults(save, canonical)
    prune_trade_offers_touching_assets(save, {f"player:{player['id']}"})
    write_save(save_path, save)


def forced_press_event_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> str:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    event = (save.get("pending_press_events") or [None])[0]
    if not event:
        return "handled"
    print_title("Mandatory Press Conference")
    print(event.get("headline") or "Reporters are waiting after a major team event.")
    press_room(canonical, save_path, user_team, seed, event=event)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    save["pending_press_events"] = [
        item for item in save.get("pending_press_events", [])
        if item.get("id") != event.get("id")
    ]
    write_save(save_path, save)
    return "handled"


def forced_offseason_review_room(canonical: dict[str, Any], save_path: Path, user_team: str) -> str:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    review = save.get("pending_offseason_review") or {}
    print_title(f"Season Review | {review.get('season') or 'Last season'}")
    print("Before training camp opens, here is the front-office recap.")
    print_offseason_reports(canonical, save_path, user_team)
    wait()
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    save.pop("pending_offseason_review", None)
    write_save(save_path, save)
    return "handled"


def forced_lottery_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> str:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    year = str(int(str(save.get("meta", {}).get("season") or "2025-26").split("-")[0]) + 1)
    print_title("You Are Entering The Draft Lottery")
    print("Lottery odds are based on this save's standings.")
    print("1. Reveal lottery")
    print("0. Save and quit")
    choice = input("> Pick a number: ").strip()
    if choice == "0":
        return "quit"
    order = run_draft_lottery(canonical, save_path, year=year, seed=None)
    print_lottery(order)
    wait()
    return "done"


def print_home(root: Path, canonical: dict[str, Any], save_path: Path) -> None:
    status = save_status(root, canonical, save_path)
    record = status["user_team_record"]
    pending = status["pending_counts"]
    phase = status["phase"]
    legal = set(status.get("legal_actions") or [])
    print_title(f"{icon('🏀', 'NBA')} GM SANDBOX")
    difficulty = status.get("ai_difficulty") or "normal"
    print(f"{style(status['user_team']['abbrev'], 'accent')} | {status['current_date']} | {status['phase']} | {difficulty} AI | Save: {save_path}")
    print(f"Record: {record['wins']}-{record['losses']}   Next event: {status.get('next_event_date') or 'season rollover'}")
    start_year = season_start_year_from_date(status["current_date"])
    deadline = trade_deadline_date(start_year)
    if phase in {"preseason", "regular_season"} and status["current_date"] <= deadline:
        print(style(f"Trade deadline: {deadline} (final day to trade)", "accent"))
    elif phase in {"preseason", "regular_season"}:
        print(style(f"Trade deadline passed: {deadline}", "danger"))
    if status["phase"] in {"draft_lottery", "draft", "free_agency"}:
        print(style(f"STOP: {status['phase']} is active. Review league actions before advancing.", "accent"))
    print(f"Pending: user offers {pending.get('user_trade_offers', 0)}")
    event_view = league_events_view(canonical, save_path, limit=5, kind="transactions")
    if event_view.get("events"):
        print_rule()
        print(style("Recent league events", "accent"))
        for event in event_view["events"][:5]:
            print(f"{event.get('date', '')}  {clean_label(event.get('kind'))}: {event.get('headline', '')}")
    print_rule()
    print(" 1. Advance to next event/day")
    print(" 2. Sim one week")
    print(" 3. Sim one month")
    print(f" 4. {season_stop_label(status)}")
    print(" 5. Team dashboard")
    print(" 6. Standings")
    print(" 7. League leaders / player traits")
    if phase not in {"preseason", "training_camp"}:
        print(" 8. Calendar / box scores")
    if "trades" in legal:
        print(" 9. Trade room")
    if phase in OFFSEASON_PHASES:
        print("10. Offseason room / draft / free agency")
    elif phase in PLAYOFF_PHASES:
        print("10. Playoff bracket / results")
    print("11. Review AI trade offers to you")
    print("12. Staff room")
    print("13. Current free agents")
    print("14. Social feed / morale")
    print("15. League events")
    print("16. Narrative settings")
    print(" 0. Save and quit")


def season_stop_label(status: dict[str, Any]) -> str:
    current = status.get("current_date") or ""
    season = str(status.get("season") or "")
    try:
        start = int(season.split("-")[0]) if season else int(current[:4])
    except ValueError:
        start = 2025
    deadline = trade_deadline_date(start)
    regular_end = f"{start + 1}-04-12"
    if current < deadline:
        return f"Stop at trade deadline ({deadline})"
    if current < regular_end:
        return "Sim to end of regular season"
    return "Advance to next phase"


def handle_choice(root: Path, canonical: dict[str, Any], save_path: Path, choice: str, seed: int) -> None:
    save = load_save(save_path)
    save = ensure_league_save_defaults(save, canonical)
    user_team = save.get("meta", {}).get("user_team_abbrev") or "GSW"
    current = save.get("state", {}).get("current_date") or "2025-10-01"
    if choice == "1":
        with loading_screen(root, "Advancing to next event...", seed=seed):
            result = advance_save(root, canonical, save_path, next_event=True, seed=seed)
            process_ai_actions(canonical, save_path, seed=seed, execute=True, limit=30)
        print(summary_lines("Advanced", result, ["through_date", "phase"]))
    elif choice == "2":
        target = add_days(current, 7)
        with loading_screen(root, "Working through the week...", seed=seed):
            result = advance_save_with_ai_checkpoints(root, canonical, save_path, target, seed, checkpoint_days=7)
        print(summary_lines("Advanced one week", result, ["through_date", "phase"]))
    elif choice == "3":
        target = add_days(current, 31)
        print(style("Simulating the month. This can take a moment...", "accent"))
        with loading_screen(root, "Simulating one month...", seed=seed):
            result = advance_save_with_ai_checkpoints(root, canonical, save_path, target, seed, checkpoint_days=31)
        print(summary_lines("Advanced one month", result, ["through_date", "phase"]))
    elif choice == "4":
        season = save.get("meta", {}).get("season") or "2025-26"
        deadline = trade_deadline_date(int(str(season).split("-")[0]))
        regular_end = f"{int(str(season).split('-')[0]) + 1}-04-12"
        if current < deadline:
            with loading_screen(root, "Simulating to the trade deadline...", seed=seed):
                result = advance_save_with_ai_checkpoints(root, canonical, save_path, deadline, seed)
            print(summary_lines("Stopped at trade deadline", result, ["through_date", "phase"]))
        elif current < regular_end:
            with loading_screen(root, "Simulating to the end of the regular season...", seed=seed):
                result = advance_save_with_ai_checkpoints(root, canonical, save_path, regular_end, seed)
            print(summary_lines("Reached end of regular season", result, ["through_date", "phase"]))
        else:
            with loading_screen(root, "Advancing season...", seed=seed):
                result = advance_save(root, canonical, save_path, next_event=True, seed=seed)
            print(summary_lines("Advanced", result, ["through_date", "phase"]))
    elif choice == "5":
        team = input(f"Team [{user_team}]: ").strip() or user_team
        print_dashboard(root, canonical, save_path, team, user_team=user_team, seed=seed)
    elif choice == "6":
        print_standings(canonical, save_path)
        wait()
    elif choice == "7":
        league_player_browser_room(canonical, save_path)
    elif choice == "8":
        if save.get("state", {}).get("phase") in {"preseason", "training_camp"}:
            pause("Calendar and box scores unlock once games are on the schedule.")
        else:
            calendar_room(root, canonical, save_path)
    elif choice == "9":
        if "trades" not in legal_actions_for_current(save):
            pause("Trade room is closed for this phase.")
        else:
            trade_room(canonical, save_path, user_team, seed)
    elif choice == "10":
        phase = save.get("state", {}).get("phase")
        if phase in OFFSEASON_PHASES:
            offseason_room(canonical, save_path, user_team, seed)
        elif phase in PLAYOFF_PHASES:
            playoff_room(root, canonical, save_path, seed)
        else:
            pause("Offseason rooms unlock when the calendar reaches the offseason.")
    elif choice == "11":
        user_trade_offers_room(canonical, save_path)
    elif choice == "12":
        staff_room(canonical, save_path, user_team, seed)
    elif choice == "13":
        allow_sign = current <= trade_deadline_date(season_start_year_from_date(current)) and save.get("state", {}).get("phase") in {"preseason", "regular_season"}
        current_free_agents_room(canonical, save_path, user_team, seed, allow_sign=allow_sign)
    elif choice == "14":
        team = input(f"Team [{user_team}]: ").strip() or user_team
        print_social_and_morale(canonical, save_path, team)
    elif choice == "15":
        league_events_room(canonical, save_path)
    elif choice == "16":
        narrative_settings_room(save_path)
    else:
        pause("Unknown menu choice.")


def legal_actions_for_current(save: dict[str, Any]) -> set[str]:
    return set(save.get("state", {}).get("legal_actions") or [])


def calendar_room(root: Path, canonical: dict[str, Any], save_path: Path) -> None:
    while True:
        clear_screen()
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        current = save.get("state", {}).get("current_date") or "2025-10-01"
        from_date = add_days(current, -7)
        through_date = add_days(current, 2)
        view = calendar_view(root, canonical, save_path, from_date=from_date, through_date=through_date)
        print_calendar(view)
        print(" 0. Back")
        if not view.get("games"):
            wait()
            return
        choice = pick_number("Game", 0, len(view["games"]), default=0)
        if choice == 0:
            clear_screen()
            return
        game = view["games"][choice - 1]
        if game.get("away_score") is None or game.get("home_score") is None:
            pause("That game has not been played yet, so no box score is available.")
            continue
        clear_screen()
        print_box_score(canonical, save_path, game["game_id"])
        wait()


def league_events_room(canonical: dict[str, Any], save_path: Path) -> None:
    recent_only = False
    filter_options = [
        ("transactions", "All transactions"),
        ("trades", "Trades"),
        ("extensions", "Extensions"),
        ("staff_hires", "Staff hires"),
        ("staff_fires", "Staff fires"),
    ]
    filter_index = 0
    while True:
        clear_screen()
        filter_kind, filter_label = filter_options[filter_index]
        view = league_events_view(canonical, save_path, limit=80, kind=filter_kind, recent_days=30 if recent_only else None)
        print_title(f"League Events | {filter_label}{' | last 30 days' if recent_only else ''}")
        events = view.get("events") or []
        if not events:
            print("No league transactions match this view yet.")
        for event in events[:40]:
            importance = float(event.get("importance") or 0.0)
            color = "good" if importance >= 0.78 else "accent" if importance >= 0.55 else "muted"
            print(f"{event.get('date', '')}  {style(clean_label(event.get('kind')), color):<24} {event.get('headline', '')}")
        print_rule()
        print("1. Recent only: " + ("on" if recent_only else "off"))
        print("2. Filter: " + filter_label)
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return
        if choice == "1":
            recent_only = not recent_only
        elif choice == "2":
            filter_index = (filter_index + 1) % len(filter_options)


def narrative_settings_room(save_path: Path) -> None:
    while True:
        clear_screen()
        status = narrative_settings_view(save_path)
        print_title("Narrative Settings")
        print(f"Status: {'enabled' if status.get('enabled') else 'disabled'}")
        print(f"Provider: {status.get('provider')} | Model: {status.get('ollama_model')}")
        print(f"Ollama URL: {status.get('ollama_base_url')}")
        print(f"Timeout: {float(status.get('timeout_seconds') or 0):.1f}s | Social posts per view: {status.get('max_posts_per_view')}")
        counts = status.get("cache_counts") or {}
        print(f"Cache: social {counts.get('social', 0)} | press {counts.get('press', 0)}")
        print_rule()
        print("1. Toggle enabled")
        print("2. Set Ollama model")
        print("3. Set Ollama URL")
        print("4. Set timeout seconds")
        print("5. Set max social posts per view")
        print("6. Reset narrative cache")
        print("7. Test Ollama connection")
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return
        if choice == "1":
            updated = update_narrative_settings(save_path, enabled=not bool(status.get("enabled")))
            pause(f"Narrative is now {'enabled' if updated.get('enabled') else 'disabled'}.")
        elif choice == "2":
            model = input(f"Model [{status.get('ollama_model') or 'llama3.1'}]: ").strip()
            if model:
                update_narrative_settings(save_path, provider="ollama", ollama_model=model)
        elif choice == "3":
            url = input(f"URL [{status.get('ollama_base_url') or 'http://localhost:11434'}]: ").strip()
            if url:
                update_narrative_settings(save_path, provider="ollama", ollama_base_url=url)
        elif choice == "4":
            raw = input(f"Timeout seconds [{status.get('timeout_seconds')}]: ").strip()
            if raw:
                try:
                    update_narrative_settings(save_path, timeout_seconds=float(raw))
                except ValueError:
                    pause("Timeout must be a number.")
        elif choice == "5":
            raw = input(f"Max posts [{status.get('max_posts_per_view')}]: ").strip()
            if raw:
                try:
                    update_narrative_settings(save_path, max_posts_per_view=int(raw))
                except ValueError:
                    pause("Max posts must be a whole number.")
        elif choice == "6":
            update_narrative_settings(save_path, reset_cache=True)
            pause("Narrative cache reset.")
        elif choice == "7":
            tested = narrative_settings_view(save_path, test_connection=True)
            available = tested.get("available_models") or []
            details = f"Connection: {tested.get('connection', 'not tested')}"
            if available:
                details += "\nAvailable models: " + ", ".join(available)
            pause(details)


def league_player_browser_room(canonical: dict[str, Any], save_path: Path) -> None:
    while True:
        clear_screen()
        print_title("League Player Browser")
        print("1. Stat leaders")
        print("2. Player traits")
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return
        if choice == "1":
            stat_leaders_room(canonical, save_path)
        elif choice == "2":
            save = ensure_league_save_defaults(load_save(save_path), canonical)
            if save.get("state", {}).get("phase") in PLAYOFF_PHASES:
                pause("Player trait browser is available outside the playoffs.")
            else:
                league_traits_room(canonical, save_path)


STAT_LEADER_OPTIONS = [
    ("points", "Points"),
    ("rebounds", "Rebounds"),
    ("assists", "Assists"),
    ("steals", "Steals"),
    ("blocks", "Blocks"),
    ("fg3m", "3PM"),
]


def stat_leaders_room(canonical: dict[str, Any], save_path: Path) -> None:
    while True:
        clear_screen()
        print_title("League Stat Leaders")
        for idx, (_, label) in enumerate(STAT_LEADER_OPTIONS, start=1):
            print(f"{idx}. {label}")
        print("0. Back")
        choice = pick_number("Stat", 0, len(STAT_LEADER_OPTIONS), default=1)
        if choice == 0:
            return
        print_leaders(canonical, save_path, STAT_LEADER_OPTIONS[choice - 1][0])
        wait()


LEAGUE_TRAIT_SORTS = [
    ("overall", "Overall"),
    ("offense", "Offense"),
    ("defense", "Defense"),
    ("spacing", "Spacing"),
    ("creation", "Creation"),
    ("rim_pressure", "Rim pressure"),
    ("rebounding", "Rebounding"),
    ("athleticism", "Athleticism"),
    ("disruption", "Disruption"),
    ("rim_protection", "Rim protection"),
]


def league_traits_room(canonical: dict[str, Any], save_path: Path) -> None:
    sort_key = "overall"
    offset = 0
    page_size = 18
    page_step = page_size // 2
    while True:
        clear_screen()
        rows = league_trait_rows(canonical, save_path, sort_key)
        thresholds = league_trait_rating_thresholds(rows)
        print_title(f"Player Traits | sort: {trait_label(sort_key)}")
        print_league_trait_table(rows[offset:offset + page_size], start=offset + 1, thresholds=thresholds)
        print_rule()
        print("1. Next page")
        print("2. Previous page")
        print("3. Change sort")
        print("4. Ratings guide")
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            return
        if choice == "1":
            if offset + page_size < len(rows):
                offset += page_step
        elif choice == "2":
            offset = max(0, offset - page_step)
        elif choice == "3":
            new_sort = choose_trait_sort(sort_key)
            if new_sort:
                sort_key = new_sort
                offset = 0
        elif choice == "4":
            clear_screen()
            print_ratings_guide(canonical)
            wait()


def choose_trait_sort(default: str) -> str | None:
    clear_screen()
    print_title("Sort Player Traits")
    default_idx = next((idx for idx, (key, _) in enumerate(LEAGUE_TRAIT_SORTS, start=1) if key == default), 1)
    for idx, (_, label) in enumerate(LEAGUE_TRAIT_SORTS, start=1):
        print(f"{idx}. {label}")
    print("0. Back")
    choice = pick_number("Sort", 0, len(LEAGUE_TRAIT_SORTS), default=default_idx)
    if choice == 0:
        return None
    return LEAGUE_TRAIT_SORTS[choice - 1][0]


def league_trait_rows(canonical: dict[str, Any], save_path: Path, sort_key: str) -> list[dict[str, Any]]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    teams = {team["id"]: team for team in active.get("teams", [])}
    stats_by_player = save.get("player_season_stats") or {}
    rows: list[dict[str, Any]] = []
    for player in active.get("players", []):
        if not player.get("team_id") or player.get("id") in set(save.get("free_agent_player_ids") or []):
            continue
        attrs = derived_trait_attributes(player_attribute_summary(active, player["id"]))
        totals = stats_by_player.get(player["id"], {})
        games = int(totals.get("games") or 0)
        stat_games = max(1, games)
        salary = current_salary(contract_for_player(active, player["id"]))
        rows.append(
            {
                "player": player,
                "team": teams.get(player.get("team_id"), {}),
                "attrs": attrs,
                "games": games,
                "minutes": round(float(totals.get("minutes") or 0.0) / stat_games if games else display_minutes_projection(player), 1),
                "points": round(float(totals.get("points") or 0.0) / stat_games, 1) if games else 0.0,
                "rebounds": round(float(totals.get("rebounds") or 0.0) / stat_games, 1) if games else 0.0,
                "assists": round(float(totals.get("assists") or 0.0) / stat_games, 1) if games else 0.0,
                "steals": round(float(totals.get("steals") or 0.0) / stat_games, 1) if games else 0.0,
                "blocks": round(float(totals.get("blocks") or 0.0) / stat_games, 1) if games else 0.0,
                "contract": contract_summary_text(salary),
            }
        )
    rows.sort(key=lambda row: (-float((row["attrs"] or {}).get(sort_key) or 0.0), row["player"].get("name") or ""))
    return rows


def apply_display_rating_scale(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys = sorted({key for row in rows for key in (row.get("attrs") or {}).keys()})
    value_sets = {
        key: sorted(float((row.get("attrs") or {}).get(key) or 0.0) for row in rows)
        for key in keys
    }
    for row in rows:
        raw_attrs = {key: float(value or 0.0) for key, value in (row.get("attrs") or {}).items()}
        row["raw_attrs"] = raw_attrs
        row["attrs"] = {
            key: display_rating_value(value, value_sets.get(key) or [])
            for key, value in raw_attrs.items()
        }


def display_rating_value(value: float, sorted_values: list[float]) -> float:
    if not sorted_values:
        return round(clamp(value, 1, 99), 1)
    left = bisect_left(sorted_values, value)
    right = bisect_right(sorted_values, value)
    percentile = (left + max(1, right - left) * 0.5) / max(1, len(sorted_values))
    display = 35.0 + percentile * 64.0
    return round(clamp(display, 1, 99), 1)


def ratings_guide(canonical: dict[str, Any]) -> dict[str, Any]:
    sample_by_trait: dict[str, dict[str, Any]] = {}
    for trait in canonical.get("traits", []):
        key = trait.get("trait_key")
        if key and key not in sample_by_trait:
            sample_by_trait[key] = trait
    usage = {
        "release_speed": "shooting, spacing, shot profile",
        "shooting_range": "shooting, spacing, playoff translation",
        "shot_versatility": "shooting, creation, scoring usage",
        "rim_pressure": "creation, athleticism, scoring, free throws",
        "handle_pressure": "creation, ball pressure, trade role fit",
        "passing_reads": "creation, IQ, assists, hub value",
        "foot_speed_lateral_agility": "athleticism, defense, matchup fit",
        "stamina_cardio": "athleticism, minutes durability, development",
        "defensive_effort": "defense, disruption, DPOY",
        "scheme_iq": "defense, IQ, team fit, coaching context",
        "rim_deterrence": "defense, rim protection, rebounds, DPOY",
        "screen_navigation": "defense, disruption, guard/wing matchup value",
        "offensive_rebounding": "rebounding, possession value",
        "portability": "IQ, disruption, trade/team fit",
        "playoff_translation": "IQ, playoff/scouting context",
    }
    rows = []
    for key, label in TRAIT_LABELS.items():
        trait = sample_by_trait.get(key) or {}
        components = trait.get("components") or {}
        rows.append(
            {
                "trait": key,
                "label": label,
                "fields": components.get("fields") or [],
                "notes": trait.get("notes") or "",
                "used_in": usage.get(key, "player evaluation"),
            }
        )
    return {
        "rows": rows,
        "display_scale": "Visible ratings use the calibrated 1-99 game scale shown on team dashboards; engine calculations use the same underlying raw trait values.",
        "calibration_stack": "Trait stack: inferred stat model -> full-health 2026 league ratings prior -> manual playtest overrides; health, rust, and injury risk are applied separately.",
        "composites": [
            "Overall: shooting 22%, creation 25%, defense 22%, athleticism 13%, IQ 12%, plus a small minutes role bonus.",
            "Offense: shooting 35%, creation 32%, passing 18%, rim pressure 15%.",
            "Defense: defensive effort, scheme IQ, screen navigation, and rim deterrence.",
            "Rebounding: offensive rebounding 66%, rim deterrence 18%, stamina 16%.",
        ],
    }


def print_ratings_guide(canonical: dict[str, Any]) -> None:
    guide = ratings_guide(canonical)
    print_title("Ratings Guide")
    print(guide["display_scale"])
    print(guide["calibration_stack"])
    print_rule()
    for formula in guide["composites"]:
        print(f"- {formula}")
    print_rule()
    for row in guide["rows"]:
        fields = ", ".join(row["fields"][:5]) or "manual/generated context"
        print(f"{row['label']:<30} uses {fields}")
        print(f"  In game: {row['used_in']}")
        if row["notes"]:
            print(f"  Model: {row['notes']}")


def derived_trait_attributes(attrs: dict[str, Any]) -> dict[str, float]:
    shooting = float(attrs.get("shooting") or 0.0)
    creation = float(attrs.get("creation") or 0.0)
    passing = float(attrs.get("passing") or 0.0)
    rim_pressure = float(attrs.get("rim_pressure") or 0.0)
    defense = float(attrs.get("defense") or 0.0)
    spacing = shooting * 0.45 + float(attrs.get("range") or 0.0) * 0.35 + float(attrs.get("release") or 0.0) * 0.20
    offense = shooting * 0.35 + creation * 0.32 + passing * 0.18 + rim_pressure * 0.15
    disruption = (
        float(attrs.get("def_effort") or 0.0) * 0.40
        + float(attrs.get("screen_nav") or 0.0) * 0.25
        + defense * 0.25
        + float(attrs.get("portability") or 0.0) * 0.10
    )
    return {
        **{key: float(value or 0.0) for key, value in attrs.items()},
        "offense": round(clamp(offense, 1, 99), 1),
        "spacing": round(clamp(spacing, 1, 99), 1),
        "disruption": round(clamp(disruption, 1, 99), 1),
        "rim_protection": round(clamp(float(attrs.get("rim_deterrence") or 0.0), 1, 99), 1),
    }


def print_league_trait_table(rows: list[dict[str, Any]], start: int = 1, thresholds: dict[str, tuple[float, float]] | None = None) -> None:
    rating_keys = [
        "overall",
        "offense",
        "defense",
        "spacing",
        "creation",
        "rim_pressure",
        "rebounding",
        "athleticism",
        "disruption",
        "rim_protection",
    ]
    thresholds = thresholds or {}
    print(
        f" #  {'Player':<22} {'Tm':<3} {'Pos':<3} {'Age':>3} {'Min':>4} "
        f"{'PTS':>4} {'REB':>4} {'AST':>4} {'STL':>4} {'BLK':>4} "
        f"{'OVR':>4} {'OFF':>4} {'DEF':>4} {'SPC':>4} {'CRE':>4} {'RPr':>4} {'REB':>4} {'ATH':>4} {'DIS':>4} {'Rim':>4} {'Contract':>9}"
    )
    for idx, row in enumerate(rows, start=start):
        player = row["player"]
        attrs = row["attrs"]
        print(
            f"{idx:>2}. {str(player.get('name') or '')[:22]:<22} {(row.get('team') or {}).get('abbrev', ''):<3} "
            f"{compact_position(player.get('position')):<3} {age_text(player, 3)} {float(row.get('minutes') or 0):>4.1f} "
            f"{float(row.get('points') or 0):>4.1f} {float(row.get('rebounds') or 0):>4.1f} {float(row.get('assists') or 0):>4.1f} "
            f"{float(row.get('steals') or 0):>4.1f} {float(row.get('blocks') or 0):>4.1f} "
            + " ".join(rating_cell(float(attrs.get(key) or 0), thresholds.get(key, (45.0, 65.0))).strip() for key in rating_keys)
            + f" {row.get('contract', ''):>9}"
        )


def league_trait_rating_thresholds(rows: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    keys = [
        "overall",
        "offense",
        "defense",
        "spacing",
        "creation",
        "rim_pressure",
        "rebounding",
        "athleticism",
        "disruption",
        "rim_protection",
    ]
    thresholds: dict[str, tuple[float, float]] = {}
    for key in keys:
        values = sorted(float((row.get("attrs") or {}).get(key) or 0.0) for row in rows)
        if not values:
            thresholds[key] = (45.0, 65.0)
            continue
        low_index = max(0, min(len(values) - 1, len(values) // 3))
        high_index = max(0, min(len(values) - 1, (len(values) * 2) // 3))
        thresholds[key] = (values[low_index], values[high_index])
    return thresholds


def trait_label(key: str) -> str:
    return next((label for sort_key, label in LEAGUE_TRAIT_SORTS if sort_key == key), clean_label(key))


def contract_summary_text(salary: float | int | None) -> str:
    if salary is None:
        return "FA"
    return f"${float(salary) / 1_000_000:.1f}M"


def minutes_room(canonical: dict[str, Any], save_path: Path, user_team: str) -> None:
    while True:
        clear_screen()
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        if prune_rotation_recommendations(save, canonical):
            write_save(save_path, save)
        active = canonical_with_save(canonical, save)
        team = resolve_team(active, user_team)
        active_recs = [
            rec for rec in (save.get("rotation_recommendations") or {}).values()
            if rec.get("team_id") == team["id"] and rec.get("status") == "active"
        ]
        players = {player["id"]: player for player in active.get("players", [])}
        print_title("Head Coach Conversation")
        print("Active GM minute recommendations")
        if active_recs:
            for idx, rec in enumerate(sorted(active_recs, key=lambda item: players.get(item.get("player_id"), {}).get("name", "")), start=1):
                player = players.get(rec.get("player_id"), {})
                print(
                    f"{idx:>2}. {str(player.get('name') or rec.get('player_id')):<24} "
                    f"target {float(rec.get('target_minutes') or 0):>2.0f} MPG | "
                    f"coach buy-in {float(rec.get('coach_commitment') or 0) * 100:>3.0f}%"
                )
        else:
            print("  None. The coach is using the automatic rotation projection.")
        print_rule()
        print("1. Add or update a player recommendation")
        print("2. Remove one recommendation")
        print("3. Clear all recommendations")
        print("0. Back")
        choice = pick_number("Choice", 0, 3, default=0)
        if choice == 0:
            return
        if choice == 1:
            add_minutes_recommendation(active, save_path, save, user_team)
        elif choice == 2:
            remove_one_minutes_recommendation(save_path, save, active_recs, players)
        elif choice == 3:
            removed = 0
            for rec in active_recs:
                if rec.get("player_id") in save.get("rotation_recommendations", {}):
                    del save["rotation_recommendations"][rec["player_id"]]
                    removed += 1
            write_save(save_path, save)
            pause(f"Cleared {removed} recommendation(s). The coach will restore auto rotation projection.")


def add_minutes_recommendation(active: dict[str, Any], save_path: Path, save: dict[str, Any], user_team: str) -> None:
    player = choose_player_from_team(active, user_team, "Talk to your head coach: minutes recommendation", allow_back=True)
    if not player:
        return
    current = round(display_minutes_projection(player))
    print_title("Head Coach Conversation")
    print(f"{player['name']} is currently projected around {current:.0f} MPG.")
    try:
        target = int(round(float(input(f"Recommended MPG [{current:.0f}]: ").strip() or current)))
    except ValueError:
        target = current
    target = int(max(0, min(42, target)))
    head = next((slot for slot in save.get("staff_slots", []) if slot.get("team_id") == player.get("team_id") and slot.get("slot") == "head_coach"), {})
    buy_in = coach_minutes_buy_in(active, save, player, head, current, target)
    commitment = buy_in["commitment"]
    save.setdefault("rotation_recommendations", {})[player["id"]] = {
        "player_id": player["id"],
        "team_id": player.get("team_id"),
        "target_minutes": target,
        "previous_projection": current,
        "coach_commitment": round(commitment, 3),
        "coach_buy_in_factors": buy_in["factors"],
        "date": save.get("state", {}).get("current_date"),
        "status": "active",
        "notes": "GM recommendation. The head coach blends this target into the rotation and normalizes total team minutes. Buy-in is player/context specific.",
    }
    write_save(save_path, save)
    pause(
        f"Recommendation logged: {player['name']} toward {target:.0f} MPG. "
        f"Coach buy-in: {commitment * 100:.0f}% ({', '.join(buy_in['factors'][:3])}). "
        f"The rotation dashboard now shows your target and the coach-adjusted MPG."
    )


def remove_one_minutes_recommendation(save_path: Path, save: dict[str, Any], active_recs: list[dict[str, Any]], players: dict[str, dict[str, Any]]) -> None:
    if not active_recs:
        pause("There are no active recommendations to remove.")
        return
    print_title("Remove Recommendation")
    ordered = sorted(active_recs, key=lambda item: players.get(item.get("player_id"), {}).get("name", ""))
    for idx, rec in enumerate(ordered, start=1):
        player = players.get(rec.get("player_id"), {})
        print(f"{idx:>2}. {str(player.get('name') or rec.get('player_id')):<24} {float(rec.get('target_minutes') or 0):>2.0f} MPG")
    print(" 0. Back")
    choice = pick_number("Recommendation", 0, len(ordered), default=0)
    if choice == 0:
        return
    rec = ordered[choice - 1]
    save.get("rotation_recommendations", {}).pop(rec.get("player_id"), None)
    write_save(save_path, save)
    pause("Recommendation removed. The coach will recalculate that player from the automatic projection.")


def coach_minutes_buy_in(canonical: dict[str, Any], save: dict[str, Any], player: dict[str, Any], head: dict[str, Any], current: float, target: float) -> dict[str, Any]:
    traits = head.get("skill_traits") or {}
    coach_grade = float(head.get("grade") or 0.0) or float(sum(traits.values()) / max(1, len(traits)) if traits else 62.0)
    attrs = player_attribute_summary(canonical, player["id"])
    request_delta = target - current
    request_size = abs(request_delta)
    minutes = display_minutes_projection(player)
    overall = float(attrs.get("overall") or 50.0)
    age = float(player.get("display_age", player.get("age")) or 27.0)
    position = player.get("position")
    teammates = [
        item for item in canonical.get("players", [])
        if item.get("team_id") == player.get("team_id") and item.get("id") != player.get("id")
    ]
    better_same_position = sum(
        1 for item in teammates
        if item.get("position") == position
        and float(player_attribute_summary(canonical, item.get("id")).get("overall") or 0.0) > overall + 2.5
    )
    top_teammates = sorted(teammates, key=display_minutes_projection, reverse=True)[:7]
    top_attrs = [player_attribute_summary(canonical, item.get("id")) for item in top_teammates]
    avg_shooting = sum(float(item.get("shooting") or 50.0) for item in top_attrs) / max(1, len(top_attrs))
    avg_creation = sum(float(item.get("creation") or 50.0) for item in top_attrs) / max(1, len(top_attrs))
    avg_defense = sum(float(item.get("defense") or 50.0) for item in top_attrs) / max(1, len(top_attrs))
    avg_rebounding = sum(float(item.get("rebounding") or 50.0) for item in top_attrs) / max(1, len(top_attrs))
    lineup_fit = 0.0
    fit_reasons: list[str] = []
    if avg_shooting < 57 and float(attrs.get("shooting") or 50.0) >= 64:
        lineup_fit += 0.09
        fit_reasons.append("adds needed spacing")
    if avg_creation < 56 and float(attrs.get("creation") or 50.0) >= 64:
        lineup_fit += 0.08
        fit_reasons.append("adds needed creation")
    if avg_defense < 56 and float(attrs.get("defense") or 50.0) >= 64:
        lineup_fit += 0.08
        fit_reasons.append("adds needed defense")
    if avg_rebounding < 54 and float(attrs.get("rebounding") or 50.0) >= 62:
        lineup_fit += 0.06
        fit_reasons.append("adds needed rebounding")
    if float(attrs.get("shooting") or 50.0) < 45 and avg_shooting < 55 and target >= 20:
        lineup_fit -= 0.09
        fit_reasons.append("spacing concern")
    if float(attrs.get("defense") or 50.0) < 45 and avg_defense < 55 and target >= 20:
        lineup_fit -= 0.08
        fit_reasons.append("defensive fit concern")
    projected_role = "star" if overall >= 76 else "starter" if overall >= 65 or minutes >= 24 else "rotation" if overall >= 56 or minutes >= 12 else "depth"
    health = next((state for state in save.get("health_states", []) if state.get("player_id") == player.get("id")), {})
    fatigue = float(health.get("fatigue") or 0.0)
    injured = bool(health.get("current_injury_id") or str(health.get("availability_status") or "").lower() not in {"", "active", "healthy"})
    role_target = {"star": 35.0, "starter": 29.0, "rotation": 18.0, "depth": 7.0}.get(projected_role, 12.0)
    appropriateness = 1.0 - min(1.0, abs(target - role_target) / 24.0)
    role_trust = (overall - 60.0) * 0.01 + max(0.0, minutes - 18.0) * 0.006 + (appropriateness - 0.5) * 0.2 + lineup_fit
    coach_trust = (coach_grade - 65.0) * 0.0035
    flexibility = (float(traits.get("rotation_management") or traits.get("player_buy_in") or 62.0) - 62.0) * 0.0025
    communication = (float(traits.get("communication") or traits.get("feedback_clarity") or 62.0) - 62.0) * 0.0018
    request_penalty = request_size * 0.006
    direction_bonus = 0.0
    factors: list[str] = []
    if request_delta > 0:
        if overall >= 72 or minutes >= 28:
            direction_bonus += 0.075
            factors.append("trusted core player")
        elif projected_role == "depth" and target >= 18:
            direction_bonus -= 0.14
            factors.append("coach cautious with deep-bench role")
        if better_same_position >= 2 and target >= 20:
            direction_bonus -= 0.08
            factors.append("position crowding")
    elif request_delta < 0:
        if fatigue >= 28 or injured or age >= 34:
            direction_bonus += 0.055
            factors.append("rest/health case is persuasive")
        elif overall >= 76 and request_size >= 4:
            direction_bonus -= 0.05
            factors.append("coach resists cutting star minutes")
    if request_size <= 2:
        direction_bonus += 0.035
        factors.append("small ask")
    if request_size >= 8:
        factors.append("large rotation change")
    if fatigue >= 35 and request_delta > 0:
        direction_bonus -= 0.06
        factors.append("fatigue concern")
    factors.extend(fit_reasons[:2])
    if target <= role_target + 3 and target >= max(0.0, role_target - 5):
        factors.append(f"{projected_role} minutes fit")
    elif target > role_target + 8:
        factors.append("role stretch")
    deterministic = deterministic_ratio(player.get("id"), save.get("meta", {}).get("id"), head.get("id"), target)
    wobble = (deterministic - 0.5) * 0.18
    commitment = max(0.24, min(0.93, 0.60 + coach_trust + flexibility + communication + role_trust + direction_bonus - request_penalty + wobble))
    if not factors:
        factors.append("coach discretion")
    factors.append(f"{request_delta:+.0f} MPG ask")
    return {"commitment": round(commitment, 3), "factors": factors}


def deterministic_ratio(*parts: Any) -> float:
    text = "|".join(str(part) for part in parts if part is not None)
    if not text:
        return 0.5
    total = sum((idx + 1) * ord(char) for idx, char in enumerate(text))
    return (total % 10000) / 9999.0


def playoff_room(root: Path, canonical: dict[str, Any], save_path: Path, seed: int, forced: bool = False) -> str | None:
    while True:
        clear_screen()
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        state = save.get("playoff_state") or {}
        print_title("Playoffs")
        if not state:
            picture = playoff_picture(canonical, save_path)
            print_playoff_picture(picture)
            print_rule()
            if forced:
                print("The regular season is complete. Playoffs now take over the league calendar.")
                state = start_playoffs(canonical, save_path, seed=seed, include_play_in=True)
                print_playoff_bracket(canonical, state, save_path)
                continue
            print("1. Generate playoff bracket")
            print("0. Back")
            choice = input("> Pick a number: ").strip()
            if choice == "1":
                state = start_playoffs(canonical, save_path, seed=seed, include_play_in=True)
                print_playoff_bracket(canonical, state, save_path)
            else:
                clear_screen()
                return "back"
        else:
            print_playoff_bracket(canonical, state, save_path)
            print_rule()
            if state.get("status") == "completed":
                print("Postseason complete. Press Enter to continue to the draft lottery.")
                wait()
                return "done"
            if state.get("status") != "completed":
                print("1. Sim next playoff game")
                print("2. Sim next playoff round")
                print("3. Sim entire playoffs")
            print("4. View playoff box score")
            print("5. Playoff stat leaders / Finals MVP")
            print("6. Team dashboard")
            if forced:
                print("0. Save and quit")
            else:
                print("0. Back")
            choice = input("> Pick a number: ").strip()
            if choice == "1" and state.get("status") != "completed":
                simulate_next_playoff_game(canonical, save_path, seed=seed, root=root)
                continue
            elif choice == "2" and state.get("status") != "completed":
                simulate_playoff_round(canonical, save_path, seed=seed, root=root)
                continue
            elif choice == "3" and state.get("status") != "completed":
                result: dict[str, Any] = {"playoff_state": state}
                with loading_screen(root, "Simulating the full postseason...", seed=seed):
                    for _ in range(8):
                        result = simulate_playoff_round(canonical, save_path, seed=seed, root=root)
                        state = result.get("playoff_state", {})
                        if state.get("status") == "completed":
                            break
                continue
            elif choice == "4":
                playoff_box_score_picker(canonical, save_path)
            elif choice == "5":
                playoff_leaders_room(canonical, save_path)
            elif choice == "6":
                save = ensure_league_save_defaults(load_save(save_path), canonical)
                user_team = save.get("meta", {}).get("user_team_abbrev")
                if user_team:
                    print_dashboard(root, canonical, save_path, user_team, user_team=user_team, seed=seed)
                else:
                    pause("No user team is attached to this save.")
            else:
                clear_screen()
                return "quit" if forced else "back"


def playoff_rotation_room(canonical: dict[str, Any], save_path: Path) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("playoff_state") or {}
    user_team_id = save.get("meta", {}).get("user_team_id")
    user_team = save.get("meta", {}).get("user_team_abbrev") or team_id_to_abbrev(user_team_id)
    if not user_team_id or not state or state.get("status") == "completed":
        pause("Your team is not active in the playoffs.")
        return
    current_round = state.get("round")
    alive = any(
        user_team_id in (series.get("team_ids") or [])
        and series.get("round") == current_round
        and series.get("status") != "completed"
        for series in state.get("series", [])
    )
    if not alive:
        pause("Your team has been eliminated, so playoff rotation changes are closed.")
        return
    minutes_room(canonical, save_path, user_team)


def playoff_box_score_picker(canonical: dict[str, Any], save_path: Path) -> None:
    save = load_save(save_path)
    user_team_id = save.get("meta", {}).get("user_team_id")
    results = {str(result.get("game_id")): result for result in save.get("game_results", [])}
    games = [
        game for game in (save.get("playoff_state") or {}).get("games", [])
        if str(game.get("externalGameId")) in results
    ]
    print_title("Playoff Box Scores")
    if not games:
        print("No playoff box scores have been simulated yet.")
        wait()
        return
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    for idx, game in enumerate(games, start=1):
        result = results[str(game.get("externalGameId"))]
        away = teams.get(result.get("away_team_id"), {}).get("abbrev", "AWAY")
        home = teams.get(result.get("home_team_id"), {}).get("abbrev", "HOME")
        marker = ""
        if user_team_id in {result.get("away_team_id"), result.get("home_team_id")}:
            user_score = result.get("away_score") if result.get("away_team_id") == user_team_id else result.get("home_score")
            opp_score = result.get("home_score") if result.get("away_team_id") == user_team_id else result.get("away_score")
            marker = style(" W ", "good") if int(user_score or 0) > int(opp_score or 0) else style(" L ", "danger")
        print(f"{idx:>2}. {marker}{game.get('gameDate')}  {away} {result.get('away_score')} at {home} {result.get('home_score')}")
    print(" 0. Back")
    choice = pick_number("Game", 0, len(games), default=0)
    if choice:
        print_box_score(canonical, save_path, games[choice - 1]["externalGameId"])
        wait()


def playoff_leaders_room(canonical: dict[str, Any], save_path: Path) -> None:
    stat_options = [("points", "PPG"), ("rebounds", "RPG"), ("assists", "APG"), ("steals", "SPG"), ("blocks", "BPG"), ("fg3m", "3PM")]
    while True:
        clear_screen()
        save = load_save(save_path)
        print_title("Playoff Leaders")
        if save.get("finals_mvp"):
            mvp = save["finals_mvp"]
            print(style(f"Finals MVP: {mvp.get('player_name')} ({mvp.get('team_abbrev')})", "good"))
            print_rule()
        for idx, (_, label) in enumerate(stat_options, start=1):
            print(f"{idx}. {label}")
        print("0. Back")
        choice = pick_number("Stat", 0, len(stat_options), default=1)
        if choice == 0:
            return
        stat, label = stat_options[choice - 1]
        view = playoff_leaders(canonical, save_path, stat=stat, limit=12)
        clear_screen()
        print_title(f"Playoff Leaders | {label}")
        key = view.get("stat")
        for idx, row in enumerate(view.get("leaders", []), start=1):
            print(f"{idx:>2}. {row['player'].get('name', ''):<28} {row.get('team_abbrev') or '':<3} {row.get(str(key) + '_per_game', 0):>5}/g  GP {row.get('games', 0):>2}")
        wait()


def print_playoff_picture(payload: dict[str, Any]) -> None:
    print(f"As of {payload.get('as_of_date')}")
    for conf, rows in (payload.get("picture") or {}).items():
        print(f"\n{conf}")
        for row in rows[:10]:
            print(f"{row['seed']:>2}. {row['team']['abbrev']} {row['wins']}-{row['losses']} pct {row['win_pct']:.3f}")


def print_playoff_bracket(canonical: dict[str, Any], state: dict[str, Any], save_path: Path | None = None) -> None:
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    result_by_id: dict[str, Any] = {}
    finals_mvp: dict[str, Any] | None = None
    if save_path is not None:
        try:
            save = load_save(save_path)
            result_by_id = {str(item.get("game_id")): item for item in save.get("game_results", [])}
            finals_mvp = save.get("finals_mvp")
        except (OSError, ValueError):
            result_by_id = {}
    print(f"Status: {state.get('status')} | Current round: {clean_label(state.get('round'))}")
    play_in = state.get("play_in") or {}
    if play_in:
        print("\nPlay-In")
        for conference, payload in play_in.items():
            seeds = payload.get("teams") or {}
            seed7_final = teams.get(payload.get("seed_7_team_id"), {}).get("abbrev") or "TBD"
            seed8_final = teams.get(payload.get("seed_8_team_id"), {}).get("abbrev") or "TBD"
            print(f"{conference} Play-In | {clean_label(payload.get('status'))}")
            labels = [
                f"#7 {teams.get(seeds.get('7'), {}).get('abbrev', 'TBD')} vs #8 {teams.get(seeds.get('8'), {}).get('abbrev', 'TBD')}",
                f"#9 {teams.get(seeds.get('9'), {}).get('abbrev', 'TBD')} vs #10 {teams.get(seeds.get('10'), {}).get('abbrev', 'TBD')}",
                "Loser #7/#8 vs Winner #9/#10",
            ]
            for label, game_id in zip(labels, payload.get("games", []), strict=False):
                result = result_by_id.get(str(game_id))
                if not result:
                    print(f"    {label}: scheduled")
                    continue
                away = teams.get(result.get("away_team_id"), {}).get("abbrev", "AWAY")
                home = teams.get(result.get("home_team_id"), {}).get("abbrev", "HOME")
                print(f"    {label}: {away} {result.get('away_score')} at {home} {result.get('home_score')}")
            print(f"    Playoff seeds: #7 {seed7_final}, #8 {seed8_final}")
    for round_name in ["first_round", "conference_semifinals", "conference_finals", "finals"]:
        rows = [series for series in state.get("series", []) if series.get("round") == round_name]
        if not rows:
            continue
        print(f"\n{clean_label(round_name).title()}")
        for series in rows:
            ids = series.get("team_ids") or []
            a = teams.get(ids[0], {"abbrev": ids[0]}) if ids else {"abbrev": "TBD"}
            b = teams.get(ids[1], {"abbrev": ids[1]}) if len(ids) > 1 else {"abbrev": "TBD"}
            wins = series.get("wins") or {}
            winner = teams.get(series.get("winner_team_id"), {}).get("abbrev")
            marker = f" -> {winner}" if winner else ""
            print(f"{a.get('abbrev')} {wins.get(ids[0], 0) if ids else 0} - {b.get('abbrev')} {wins.get(ids[1], 0) if len(ids) > 1 else 0}{marker}")
    if state.get("champion_team_id"):
        print(f"\nChampion: {teams.get(state.get('champion_team_id'), {}).get('abbrev')}")
        if finals_mvp:
            print(f"FMVP: {finals_mvp.get('player_name')} ({finals_mvp.get('team_abbrev')})")


def trade_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    while True:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = canonical_with_save(canonical, save)
        print_title("Trade Room")
        print("1. Build a trade from team asset lists")
        print("2. Trade finder")
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return
        if choice == "1":
            guided_trade_builder(active, save_path, user_team, seed)
        elif choice == "2":
            trade_finder_room(active, save_path, user_team, seed)


def guided_trade_builder(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    while True:
        partner = choose_team_abbrev(canonical, "Trade partner", default=user_team, allow_back=True)
        if not partner:
            return
        if partner == user_team:
            pause("Pick another team as the trade partner.")
            continue
        result: dict[str, Any] | None = None
        apply_allowed = False
        while True:
            save = ensure_league_save_defaults(load_save(save_path), canonical)
            active = canonical_with_save(canonical, save)
            user_team_id = resolve_team(active, user_team)["id"]
            partner_id = resolve_team(active, partner)["id"]
            to_assets = choose_assets(active, save, partner, "Assets you receive from " + partner, save_path=save_path, sender_team_id=partner_id, receiver_team_id=user_team_id, prompt_pick_terms=True)
            if to_assets is None:
                result = None
                break
            from_assets = choose_assets(active, save, user_team, "Assets you send to " + partner, save_path=save_path, sender_team_id=user_team_id, receiver_team_id=partner_id, prompt_pick_terms=True)
            if from_assets is None:
                result = None
                break
            if not from_assets and not to_assets:
                pause("No assets selected.")
                continue
            specs = [f"FROM:{asset['kind']}:{asset['value']}" for asset in from_assets] + [f"TO:{asset['kind']}:{asset['value']}" for asset in to_assets]
            terms = pick_terms_from_selected_assets([*from_assets, *to_assets])
            evaluation_active = canonical_with_pending_pick_terms(active, terms) if terms else active
            result = propose_trade_to_save(evaluation_active, save_path, user_team, partner, specs, seed=seed, store=False, pick_obligation_terms=terms)
            print_trade_result(result)
            if result.get("legality", {}).get("status") == "legal":
                apply_allowed = user_can_apply_trade(canonical, result, user_team)
                if apply_allowed:
                    break
                print("Offer rejected.")
                if yes_no("Reselect assets and re-offer?"):
                    continue
                break
            print_legality_failures(result.get("legality") or {})
            if not yes_no("Reselect assets and re-offer?"):
                break
        if result is None:
            continue
        if apply_allowed and yes_no("Apply legal trade now?"):
            result = attach_pick_terms_to_trade(canonical, save_path, result)
            store_trade_offer(save_path, result)
            applied = apply_trade_to_save(save_path, result["proposal"]["id"], date=load_save(save_path).get("state", {}).get("current_date"))
            print(f"Trade apply result: {applied.get('status')}")
        else:
            print("Offer not applied. Go back and re-select assets if you want to try a different structure.")
        wait()
        return


def user_can_apply_trade(canonical: dict[str, Any], result: dict[str, Any], user_team: str) -> bool:
    if (result.get("legality") or {}).get("status") != "legal":
        return False
    user_team_id = resolve_team(canonical, user_team)["id"]
    if result.get("accepted_by_all"):
        return True
    partner_ok = partner_accepts(result, user_team_id) == "yes"
    user_eval = next((item for item in result.get("evaluations", []) if item.get("perspective_team_id") == user_team_id), {})
    if partner_ok:
        print(style("Advisor warning: your side grades this as a bad-value trade, but you control the team.", "accent"))
        print(f"Your model read: {clean_label(user_eval.get('decision'))} | net {float(user_eval.get('net_value') or 0):+.1f}")
        context = result.setdefault("offer_context", {})
        context["status"] = "user_override_pending_apply"
        context["created_by_user"] = True
        context["override_team_id"] = user_team_id
        return True
    return False


def store_trade_offer(save_path: Path, proposal: dict[str, Any]) -> None:
    save = load_save(save_path)
    proposal_id = (proposal.get("proposal") or {}).get("id") or proposal.get("id")
    save.setdefault("pending_trade_proposals", [])
    save["pending_trade_proposals"] = [
        item for item in save["pending_trade_proposals"]
        if ((item.get("proposal") or {}).get("id") or item.get("id")) != proposal_id
    ]
    context = {
        **(proposal.get("offer_context") or {}),
        "created_date": save.get("state", {}).get("current_date"),
    }
    context.setdefault("status", "accepted_pending_apply" if proposal.get("accepted_by_all") else "response_recorded")
    stored = {
        **proposal,
        "offer_context": context,
    }
    save["pending_trade_proposals"].append(stored)
    write_save(save_path, save)


def attach_pick_terms_to_trade(canonical: dict[str, Any], save_path: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    proposal_payload = proposal.get("proposal") or {}
    context = proposal.get("offer_context") or {}
    if context.get("source") in {"trade_finder", "ai_trade_offer_to_user"}:
        if proposal.get("pick_trade_terms") is not None:
            finalized = finalize_pick_terms_for_proposal(proposal.get("pick_trade_terms") or [], proposal_payload)
            if finalized:
                return trade_result_with_pick_terms({**proposal, "pick_obligation_terms": finalized}, finalized)
            return {**proposal, "pick_obligation_terms_prompted": True, "pick_trade_terms": proposal.get("pick_trade_terms") or []}
        return {**proposal, "pick_obligation_terms_prompted": True, "pick_trade_terms": []}
    if proposal.get("pick_obligation_terms") or proposal.get("pick_obligation_terms_prompted"):
        finalized = finalize_pick_terms_for_proposal(proposal.get("pick_obligation_terms") or [], proposal_payload)
        return trade_result_with_pick_terms({**proposal, "pick_obligation_terms": finalized}, finalized)
    terms: list[dict[str, Any]] = []
    for side, sender_id, receiver_id in [
        ("from_assets", proposal_payload.get("from_team_id"), proposal_payload.get("to_team_id")),
        ("to_assets", proposal_payload.get("to_team_id"), proposal_payload.get("from_team_id")),
    ]:
        for asset in proposal_payload.get(side, []):
            if asset.get("kind") != "pick":
                continue
            term = prompt_pick_trade_terms(canonical, save_path, asset.get("id"), sender_id, receiver_id)
            if term and term.get("type") != "unprotected":
                terms.append(term)
    if terms:
        proposal = trade_result_with_pick_terms(proposal, finalize_pick_terms_for_proposal(terms, proposal_payload))
    return proposal


def prompt_pick_trade_terms(canonical: dict[str, Any], save_path: Path, pick_id: str | None, sender_id: str | None, receiver_id: str | None, allow_open_receiver: bool = False) -> dict[str, Any] | None:
    if not pick_id or not sender_id or (not receiver_id and not allow_open_receiver):
        return None
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = with_transaction_context(canonical_with_save(canonical, save))
    pick = next((item for item in active.get("draft_picks", []) if item.get("id") == pick_id), None)
    if not pick:
        return {"type": "unprotected", "primary_pick_id": pick_id}
    if pick_slot_is_determined_for_trade(save, pick):
        return {"type": "unprotected", "primary_pick_id": pick_id}
    has_active_protection = bool(active_primary_pick_obligation(pick))
    protected_available = int(pick.get("round") or 2) == 1 and not has_active_protection
    swap_candidates = eligible_swap_counterparty_picks(active, receiver_id, pick) if receiver_id else []
    swap_available = bool(swap_candidates)
    if not protected_available and not swap_available:
        return {"type": "unprotected", "primary_pick_id": pick_id}
    print_title("Pick Terms")
    print(f"{clean_pick_label_for_user(active, pick, save)}")
    options: list[tuple[str, str]] = [("unprotected", "Unprotected")]
    if protected_available:
        options.append(("protected", "Protected pick"))
    if swap_available:
        options.append(("pick_swap", "Pick swap"))
    for idx, (_, label) in enumerate(options, start=1):
        print(f"{idx}. {label}")
    print("0. Cancel terms and treat as unprotected")
    choice = pick_number("Terms", 0, len(options), default=1)
    if choice == 0 or options[choice - 1][0] == "unprotected":
        return {"type": "unprotected", "primary_pick_id": pick_id}
    if options[choice - 1][0] == "pick_swap":
        counterparty_pick = choose_pick_for_swap(active, save, swap_candidates)
        if not counterparty_pick:
            return {"type": "unprotected", "primary_pick_id": pick_id}
        print_rule()
        print("Choose the swap direction:")
        print("1. Receiving team may receive the better pick")
        print("2. Receiving team receives the less favorable pick")
        direction_choice = pick_number("Swap direction", 1, 2, default=1)
        benefit = "better" if direction_choice == 1 else "worse"
        term = {
            "id": stable_id("pick_swap", pick_id, counterparty_pick.get("id"), receiver_id, sender_id, benefit),
            "type": "pick_swap",
            "season": pick.get("season"),
            "round": int(pick.get("round") or 0),
            "team_a_pick_id": pick_id,
            "team_b_pick_id": counterparty_pick.get("id"),
            "original_rights_holder_team_id": receiver_id,
            "current_rights_holder_team_id": receiver_id,
            "counterparty_team_id": sender_id,
            "receiver_team_id": receiver_id,
            "sender_team_id": sender_id,
            "benefit": benefit,
            "label": "pick swap right" if benefit == "better" else "less favorable swap obligation",
            "pending_asset_grant": True,
            "notes": "Gameplay V1 pick-swap obligation. Direction controls whether the holder receives the better or less favorable same-season same-round pick at resolution.",
            "transfer_history": [],
        }
        print_rule()
        print(pick_swap_display_label(canonical_with_pending_pick_terms(active, [term]), term))
        if not yes_no("Attach this swap right?"):
            return {"type": "unprotected", "primary_pick_id": pick_id}
        return term
    print_title("Pick Protection")
    print(f"{clean_pick_label_for_user(active, pick, save)}")
    print("1. Top-N protected")
    print("2. Protected range")
    print("0. Cancel protection and treat as unprotected")
    protection_choice = pick_number("Protection", 0, 2, default=1)
    if protection_choice == 0:
        return {"type": "unprotected", "primary_pick_id": pick_id}
    if protection_choice == 1:
        top_n = pick_number("Top protected through pick", 1, 30, default=4)
        protected_range = {"from": 1, "through": top_n}
        label = f"top-{top_n} protected"
    else:
        start = pick_number("Protected from pick", 1, 30, default=1)
        end = pick_number("Protected through pick", start, 30, default=max(start, 14))
        protected_range = {"from": start, "through": end}
        label = f"picks {start}-{end} protected"
    fallback = choose_fallback_pick_for_protection(active, save, sender_id, pick_id)
    if not fallback:
        pause("Protected picks need a fallback asset in this v1 model. This pick will be treated as unprotected.")
        return {"type": "unprotected", "primary_pick_id": pick_id}
    fallback_pick = next((item for item in active.get("draft_picks", []) if item.get("id") == fallback), {})
    return {
        "type": "protected_pick",
        "primary_pick_id": pick_id,
        "primary_round": int(pick.get("round") or 0),
        "sender_team_id": sender_id,
        "receiver_team_id": receiver_id,
        "receiver_pending": receiver_id is None,
        "season": pick.get("season"),
        "protected_range": protected_range,
        "protected_top_n": protected_range.get("through") if protected_range.get("from") == 1 else None,
        "fallback_pick_ids": [fallback],
        "fallback_rounds": [int(fallback_pick.get("round") or 0)] if fallback_pick else [],
        "label": label,
        "notes": "Gameplay V1 protected-pick obligation. Fallback pick is locked until the obligation resolves.",
    }


def eligible_swap_counterparty_picks(canonical: dict[str, Any], receiver_id: str | None, primary_pick: dict[str, Any]) -> list[dict[str, Any]]:
    if not receiver_id or not primary_pick:
        return []
    primary_round = int(primary_pick.get("round") or 0)
    primary_season = str(primary_pick.get("season") or "")
    return sorted(
        [
            pick for pick in tradeable_picks_for_team(canonical, receiver_id)
            if pick.get("id") != primary_pick.get("id")
            and not pick.get("_obligation_locked")
            and str(pick.get("season") or "") == primary_season
            and int(pick.get("round") or 0) == primary_round
        ],
        key=lambda pick: (-pick_asset_value(pick, "neutral"), clean_pick_label_for_user(canonical, pick)),
    )


def choose_pick_for_swap(canonical: dict[str, Any], save: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    print_rule()
    print("Choose the same-year same-round pick used as the other side of the swap:")
    for idx, pick in enumerate(candidates[:18], start=1):
        print(f"{idx:>2}. {clean_pick_label_for_user(canonical, pick, save)}")
    print(" 0. No swap")
    choice = pick_number("Swap pick", 0, min(18, len(candidates)), default=1)
    if choice == 0:
        return None
    return candidates[choice - 1]


def active_primary_pick_obligation(pick: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            obligation for obligation in pick.get("_obligations", [])
            if obligation.get("type") == "protected_pick" and not obligation.get("_fallback_lock")
        ),
        None,
    )


def pick_terms_from_selected_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        asset["pick_obligation_term"]
        for asset in assets
        if asset.get("pick_obligation_term")
    ]


def finalize_pick_terms_for_proposal(terms: list[dict[str, Any]], proposal: dict[str, Any]) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    for term in terms:
        if not term or term.get("type") == "unprotected":
            continue
        item = dict(term)
        if not item.get("receiver_team_id") or item.get("receiver_pending"):
            side = proposal_side_for_pick(proposal, item.get("primary_pick_id"))
            if side == "from_assets":
                item["sender_team_id"] = proposal.get("from_team_id")
                item["receiver_team_id"] = proposal.get("to_team_id")
            elif side == "to_assets":
                item["sender_team_id"] = proposal.get("to_team_id")
                item["receiver_team_id"] = proposal.get("from_team_id")
            item.pop("receiver_pending", None)
        finalized.append(item)
    return finalized


def proposal_side_for_pick(proposal: dict[str, Any], pick_id: str | None) -> str | None:
    for side in ["from_assets", "to_assets"]:
        if any(asset.get("kind") == "pick" and asset.get("id") == pick_id for asset in proposal.get(side, [])):
            return side
    return None


def choose_fallback_pick_for_protection(canonical: dict[str, Any], save: dict[str, Any], team_id: str, primary_pick_id: str) -> str | None:
    team = next((item for item in canonical.get("teams", []) if item.get("id") == team_id), None)
    if not team:
        return None
    primary_pick = next((pick for pick in canonical.get("draft_picks", []) if pick.get("id") == primary_pick_id), {})
    primary_year = pick_season_start(primary_pick) or 0
    primary_round = int(primary_pick.get("round") or 0)
    picks = [
        pick for pick in tradeable_picks_for_team(canonical, team_id)
        if pick.get("id") != primary_pick_id
        and not pick.get("_obligation_locked")
        and int(pick.get("round") or 0) == primary_round
        and (pick_season_start(pick) or 0) >= primary_year
        and protected_pick_fallback_is_distinct(primary_pick, pick)
    ]
    picks = sorted(picks, key=lambda pick: (str(pick.get("season") or ""), int(pick.get("round") or 9), clean_pick_label_for_user(canonical, pick, save)))
    if not picks:
        return None
    print_rule()
    print("Choose fallback asset if the protection does not convey:")
    for idx, pick in enumerate(picks[:18], start=1):
        print(f"{idx:>2}. {clean_pick_label_for_user(canonical, pick, save)}")
    print(" 0. No fallback")
    choice = pick_number("Fallback", 0, min(18, len(picks)), default=1)
    if choice == 0:
        return None
    return picks[choice - 1].get("id")


def trade_finder_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    while True:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = canonical_with_save(canonical, save)
        clear_screen()
        print_title("Trade Finder")
        print("1. Shop my asset(s)")
        print("2. Target another team's asset(s)")
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return
        if choice == "1":
            user_team_id = resolve_team(active, user_team)["id"]
            selected = choose_assets(
                active,
                save,
                user_team,
                f"Shop assets from {user_team}",
                max_select=2,
                save_path=save_path,
                sender_team_id=user_team_id,
                receiver_team_id=None,
                prompt_pick_terms=True,
                allow_open_receiver=True,
            )
            if selected is None:
                continue
            if not selected:
                pause("No assets selected.")
                continue
            report = trade_finder_report_for_selection(active, save, user_team, user_team, selected, seed)
            print_find_trade_report(report)
            if not report.get("candidates"):
                pause("No legal offers came back for that exact asset package. Try adding a pick, targeting a specific team, or shopping a different player.")
                continue
            trade_finder_followup(active, report, save_path)
        elif choice == "2":
            while True:
                target_team = choose_team_abbrev(active, "Choose the team with the asset you want", default=user_team, allow_back=True)
                if not target_team:
                    break
                if target_team == user_team:
                    pause("That is your team. Use 'Shop my asset(s)' for your own roster.")
                    continue
                save = ensure_league_save_defaults(load_save(save_path), canonical)
                active = canonical_with_save(canonical, save)
                target_team_id = resolve_team(active, target_team)["id"]
                user_team_id = resolve_team(active, user_team)["id"]
                selected = choose_assets(
                    active,
                    save,
                    target_team,
                    f"Target assets from {target_team}",
                    max_select=2,
                    save_path=save_path,
                    sender_team_id=target_team_id,
                    receiver_team_id=user_team_id,
                    prompt_pick_terms=True,
                )
                if selected is None:
                    continue
                if not selected:
                    pause("No assets selected.")
                    continue
                report = trade_finder_report_for_selection(active, save, user_team, target_team, selected, seed)
                print_find_trade_report(report)
                if not report.get("candidates"):
                    pause("No legal offers came back for that exact target. Try a smaller target, a second-round pick sweetener, or a different partner.")
                    continue
                trade_finder_followup(active, report, save_path)
        else:
            continue


def trade_finder_report_for_selection(
    canonical: dict[str, Any],
    save: dict[str, Any],
    user_team: str,
    target_team: str,
    selected: list[dict[str, Any]],
    seed: int,
) -> dict[str, Any]:
    specs = [{"kind": asset["kind"], "value": asset["value"]} for asset in selected]
    terms = pick_terms_from_selected_assets(selected)
    search_canonical = canonical_with_pending_pick_terms(canonical, terms) if terms else canonical
    if len(specs) == 1 and specs[0]["kind"] == "player" and not terms:
        report = find_trade(search_canonical, specs[0]["value"], user_team, limit=8, seed=seed)
    else:
        report = find_trade_for_assets(search_canonical, target_team, specs, user_team, limit=8, seed=seed)
    if terms:
        candidates = []
        for candidate in report.get("candidates", []):
            finalized_terms = finalize_pick_terms_for_proposal(terms, candidate.get("proposal") or {})
            candidates.append(trade_result_with_pick_terms(candidate, finalized_terms))
        report["candidates"] = candidates
    user_team_id = resolve_team(search_canonical, user_team)["id"]
    report["candidates"] = [
        mark_trade_finder_offer(candidate, user_team_id)
        for candidate in report.get("candidates", [])
    ]
    report["candidates"] = difficulty_filter_trade_candidates(
        report.get("candidates", []),
        save.get("meta", {}).get("ai_difficulty", "normal"),
        save.get("meta", {}).get("user_team_id"),
    )
    report["candidates"] = remove_inferior_superset_trade_candidates(report["candidates"], save.get("meta", {}).get("user_team_id"))
    report["candidate_count"] = len(report["candidates"])
    return report


def finder_offer_counterparty_team_id(candidate: dict[str, Any], user_team_id: str | None) -> str | None:
    return next(
        (
            evaluation.get("perspective_team_id")
            for evaluation in candidate.get("evaluations", [])
            if evaluation.get("perspective_team_id") != user_team_id and evaluation.get("accepted")
        ),
        None,
    )


def mark_trade_finder_offer(candidate: dict[str, Any], user_team_id: str | None) -> dict[str, Any]:
    """Mark a finder result as an offer the counterparty has already approved."""
    partner_id = finder_offer_counterparty_team_id(candidate, user_team_id)
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
    """Record the user's acceptance of a counterparty-approved finder offer."""
    candidate = mark_trade_finder_offer(candidate, user_team_id)
    context = candidate.get("offer_context") or {}
    if context.get("status") != "finder_offer_pending_user_acceptance":
        return None
    partner_id = context.get("finder_partner_team_id")
    if not partner_id or not context.get("finder_partner_accepted"):
        return None
    for evaluation in candidate.get("evaluations", []):
        if evaluation.get("perspective_team_id") != user_team_id:
            continue
        evaluation["accepted"] = True
        evaluation["decision"] = "accept_user_selected_finder_offer"
        reasons = evaluation.setdefault("reasons", [])
        if "user_selected_finder_offer" not in reasons:
            reasons.append("user_selected_finder_offer")
    candidate["accepted_by_all"] = True
    candidate["offer_context"] = {
        **context,
        "status": "finder_offer_user_accepted",
        "user_team_id": user_team_id,
    }
    return candidate


def extensions_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or "2025-10-01"
    phase = save.get("state", {}).get("phase")
    deadline = extension_deadline_date(season_start_year_from_date(current))
    offseason_window = phase in {"draft_lottery", "draft", "offseason"}
    if current > deadline and not offseason_window:
        pause(f"Extension deadline passed on {deadline}.")
        return
    active = canonical_with_save(canonical, save)
    report = extension_candidates_report(active, user_team)
    roster = report.get("candidates", [])
    print_title(f"Contract Extensions | {'offseason window' if offseason_window else 'deadline ' + deadline}")
    if not roster:
        print("No contracted players are available for extension review.")
        wait()
        return
    print(" #  Player                     Pos  Ask / years       Eligibility")
    for idx, item in enumerate(roster, start=1):
        eligible = item.get("eligible") and not item.get("manual_review_required")
        status = style("eligible", "good") if eligible else style(clean_label(item.get("eligibility_status")), "muted")
        print(
            f"{idx:>2}. {item['name']:<26} {item.get('position') or '-':<3} "
            f"${float(item.get('projected_aav_millions') or 0):>5.1f}M/{item.get('projected_years')}y      {status}"
        )
    print(" 0. Back")
    choice = pick_number("Player", 0, len(roster), default=0)
    if choice == 0:
        wait()
        return
    player = roster[choice - 1]
    if not player.get("eligible") or player.get("manual_review_required"):
        pause(f"{player['name']} cannot negotiate an extension: {clean_label(player.get('eligibility_status'))}.")
        return
    roster_player = next((item for item in active.get("players", []) if item.get("id") == player.get("player_id")), player)
    ask_millions = float(player.get("projected_aav_millions") or 0.0)
    preferred_years = int(player.get("projected_years") or 3)
    start_season = extension_start_season_for_date(current)
    safe_years = extension_safe_year_limit(roster_player, start_season, 5)
    if safe_years < 1:
        pause(f"{player['name']} is projected to retire before an extension season would begin.")
        return
    preferred_years = min(preferred_years, safe_years)
    print_title("Extension Setup")
    print(f"{player['name']} ask: ${ask_millions:.1f}M x {preferred_years}y")
    player_id = player.get("player_id") or player.get("id")
    team_id = resolve_team(active, user_team)["id"]
    print_extension_cap_projection(active, save, team_id, player_id, start_season, max(2, preferred_years))
    max_legal_aav = extension_max_legal_aav(active, save, team_id, player_id, start_season, preferred_years)
    print(style(f"Max legal extension AAV under hard cap: ${max_legal_aav:.1f}M", "accent"))
    if safe_years < 5:
        print(style(f"Retirement risk caps this negotiation at {safe_years} year(s).", "accent"))
    print("0. Back")
    years = pick_number("Years", 0, safe_years, default=preferred_years)
    if years == 0:
        return
    max_legal_aav = extension_max_legal_aav(active, save, team_id, player_id, start_season, years)
    if extension_retirement_blocked(roster_player, start_season, years):
        pause(f"{player['name']} is expected to retire before a {years}-year extension would finish. Offer fewer years.")
        return
    result = negotiate_extension(active, player["name"], user_team, seed=seed, max_rounds=3, date=current)
    negotiation = result.get("negotiation") or {}
    ask = negotiation.get("player_ask") or {}
    walkaway = negotiation.get("team_walkaway") or {}
    ask_millions = float(ask.get("aav_millions") or ask_millions or 0.0)
    flexibility = round(max(8.0, min(92.0, 38.0 + float(player.get("team_fit_score") or 50.0) * 0.18 + (sum(ord(char) for char in f'{seed}:{player_id}:extension') % 31) - 15)), 1)
    final_offer = ask_millions
    accepted_preview = False
    actual_offers: list[dict[str, Any]] = []
    for round_no in range(1, 4):
        print_title(f"Extension Talk | Round {round_no}/3")
        print(f"{player['name']} ask: ${ask_millions:.1f}M x {years}")
        print_extension_cap_projection(active, save, team_id, player_id, start_season, max(2, years))
        max_legal_aav = extension_max_legal_aav(active, save, team_id, player_id, start_season, years)
        print(style(f"Max legal offer: ${max_legal_aav:.1f}M AAV", "accent"))
        suggested = round(max(1.5, ask_millions * (0.93 if flexibility >= 65 else 1.0)), 1)
        suggested = min(suggested, max_legal_aav)
        interest_preview = offer_interest_score(suggested, ask_millions, years, years, flexibility)
        print_interest_read(
            interest_preview,
            {
                "ask": f"${ask_millions:.1f}M x {years}",
                "team fit": f"{float(player.get('team_fit_score') or 50):.1f}/100",
                "agent leverage": f"{flexibility:.0f}/100",
            },
        )
        if walkaway:
            print(
                f"Front-office comfort: up to roughly ${float(walkaway.get('max_annual_salary') or 0)/1_000_000:.1f}M "
                f"| fit {float(walkaway.get('fit_score') or 0):.1f}/100"
            )
        print("Enter 0 to go back without saving this negotiation.")
        final_offer_value = prompt_extension_aav(suggested, max_legal_aav, allow_back=True)
        if final_offer_value is None:
            return
        final_offer = final_offer_value
        actual_interest = offer_interest_score(final_offer, ask_millions, years, years, flexibility)
        accepted_this_round = final_offer >= ask_millions * (1.02 - flexibility / 260.0)
        actual_offers.append(
            {
                "round": round_no,
                "aav_millions": round(final_offer, 2),
                "years": years,
                "interest": round(actual_interest, 2),
                "status": "accepted" if accepted_this_round else "rejected",
            }
        )
        if accepted_this_round:
            accepted_preview = True
            break
        if round_no < 3:
            gap = max(0.0, ask_millions - final_offer)
            ask_millions = round(max(1.5, ask_millions - min(gap * 0.3, ask_millions * flexibility / 440.0)), 1)
            flexibility = round(max(5.0, flexibility - 7.0 + min(6.0, final_offer / max(ask_millions, 1.0) * 3.0)), 1)
            print(f"Agent response: not enough yet. {interest_bar(actual_interest)} Ask moves to about ${ask_millions:.1f}M.")
    decision: dict[str, Any] = {}
    if accepted_preview:
        negotiation_id = negotiation.get("id") or stable_id("contract_negotiation", "extension", current, team_id, player_id, seed, "interactive")
        offer = {
            "id": stable_id("contract_offer", negotiation_id, "user", player_id, len(actual_offers), round(final_offer * 1_000_000)),
            "negotiation_id": negotiation_id,
            "team_id": team_id,
            "player_id": player_id,
            "offer_type": "extension",
            "round": len(actual_offers),
            "years": years,
            "start_season": start_season,
            "annual_salary": final_offer * 1_000_000,
            "total_value": final_offer * 1_000_000 * years,
            "role_promise": "current_team_extension",
            "status": "accepted",
            "notes": "Interactive user extension offer.",
        }
        negotiation["id"] = negotiation_id
        negotiation["offers"] = [offer]
        negotiation["rounds"] = len(actual_offers)
        negotiation["status"] = "agreement"
        decision = {
            "id": stable_id("signing_decision", negotiation["id"], "user_extension"),
            "negotiation_id": negotiation["id"],
            "player_id": player_id,
            "team_id": team_id,
            "accepted": True,
            "decision": "accept",
            "accepted_offer": offer,
            "player_score": 80.0,
            "team_score": 70.0,
            "reasons": ["interactive_extension_offer_met_player_threshold"],
        }
        negotiation["final_decision_id"] = decision["id"]
        result["decision"] = decision
        result["accepted"] = True
        result["actual_user_offers"] = actual_offers
    else:
        result["accepted"] = False
        result["actual_user_offers"] = actual_offers
    if negotiation:
        negotiation["player_name"] = player.get("name")
        negotiation["player_id"] = player_id
        negotiation["team_id"] = team_id
        negotiation["negotiation_type"] = "extension"
        negotiation["date"] = current
        negotiation["current_contract_seasons"] = list((contract_for_player(active, player_id) or {}).get("seasons") or [])
        result["negotiation"] = negotiation
    print_title("Extension Negotiation")
    print(f"{player['name']} | accepted={result.get('accepted')} | status={negotiation.get('status')}")
    print(f"Final ask read: ${ask_millions:.1f}M | Offer: ${final_offer:.1f}M")
    print_interest_read(offer_interest_score(final_offer, ask_millions, years, years, flexibility), {"agent leverage": f"{flexibility:.0f}/100"})
    for offer in actual_offers:
        print(f"Round {offer['round']}: ${offer['aav_millions']:.1f}M x {offer['years']}y | interest {offer['interest']:.1f}/100 | {offer['status']}")
    if decision.get("reasons"):
        print("Reasons: " + ", ".join(decision.get("reasons", [])[:5]))
    if result.get("accepted"):
        print("0. Back without applying")
        if yes_no("Apply extension now?"):
            save = load_save(save_path)
            save.setdefault("pending_contract_negotiations", []).append(result)
            write_save(save_path, save)
            applied = apply_contract_to_save(save_path, negotiation["id"], date=current)
            print(f"Apply result: {applied.get('status')}")
        else:
            print("Extension not applied.")
    wait()


def choose_assets(
    canonical: dict[str, Any],
    save: dict[str, Any],
    team_abbrev: str,
    title: str,
    max_select: int | None = None,
    save_path: Path | None = None,
    sender_team_id: str | None = None,
    receiver_team_id: str | None = None,
    prompt_pick_terms: bool = False,
    allow_open_receiver: bool = False,
) -> list[dict[str, Any]] | None:
    clear_screen()
    canonical = with_transaction_context(canonical)
    team = resolve_team(canonical, team_abbrev)
    values = {value.get("player_id"): value for value in canonical.get("player_asset_valuations", [])}
    team_state = next((state for state in canonical.get("team_strategic_states", []) if state.get("team_id") == team["id"]), {})
    current_date = save.get("state", {}).get("current_date") or "2025-10-01"
    recent_players = recently_traded_player_ids(save, current_date)
    signed_lock_players = recently_signed_player_ids(save, current_date)
    players = sorted(
        [p for p in canonical.get("players", []) if p.get("team_id") == team["id"] and p.get("id") not in recent_players],
        key=lambda player: (
            market_trade_target_value(player, values.get(player.get("id"), fallback_asset_valuation(player))),
            display_minutes_projection(player),
            player.get("name") or "",
        ),
        reverse=True,
    )
    used_picks = used_draft_pick_ids(save)
    picks = sorted(
        [
            p for p in tradeable_picks_for_team(canonical, team["id"])
            if p.get("id") not in used_picks
        ],
        key=lambda item: (
            pick_asset_value(item, team_state.get("phase", "balanced")),
            str(item.get("season")),
            -int(item.get("round") or 9),
            clean_pick_label_for_user(canonical, item, save),
        ),
        reverse=True,
    )
    pick_swaps = sorted(
        tradeable_pick_swaps_for_team(canonical, team["id"]),
        key=lambda item: (pick_swap_asset_value(canonical, item, team_state.get("phase", "balanced")), str(item.get("season") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    assets: list[tuple[str, str, str]] = []
    season = save.get("meta", {}).get("season")
    team_games = int((save.get("team_records", {}).get(team["id"]) or {}).get("wins", 0)) + int((save.get("team_records", {}).get(team["id"]) or {}).get("losses", 0))
    stats = save.get("player_season_stats", {})
    health = {state.get("player_id"): state for state in save.get("health_states", [])}
    for player in players:
        totals = stats.get(player["id"], {})
        attrs = player_attribute_summary(canonical, player["id"])
        trade_value = market_trade_target_value(player, values.get(player["id"], fallback_asset_valuation(player)))
        gp = int(totals.get("games") or 0)
        contract_text = salary_summary(player_salary_table(canonical, player["id"]), season)
        left = (
            f"Value {single_value_bar(trade_value, scale=100, width=10)} {trade_value:>5.1f}  "
            f"{player['name']:<24} {compact_position(player.get('position')):<3} age {age_text(player, 2)} "
            f"{height_text(player):<5} | {display_minutes_projection(player):>2.0f} mpg "
            f"PTS {per_game_from_totals(totals, 'points'):>4.1f} "
            f"REB {per_game_from_totals(totals, 'rebounds'):>4.1f} "
            f"AST {per_game_from_totals(totals, 'assists'):>4.1f} | "
            f"OVR {float(attrs.get('overall') or 0):>4.1f} O {float(attrs.get('offense') or attrs.get('shooting') or 0):>4.1f} D {float(attrs.get('defense') or 0):>4.1f} "
            f"| GP {gp:>2}/{team_games:<2} {trade_health_text(health.get(player['id'], {})):<13}"
        )
        assets.append(("player", player["name"], f"{left:<122} {contract_text}"))
        if player["id"] in signed_lock_players:
            assets[-1] = (
                assets[-1][0],
                assets[-1][1],
                f"{assets[-1][2]} | trade-locked until Dec. 1",
            )
    for pick in picks:
        trade_value = pick_asset_value(pick, team_state.get("phase", "balanced"))
        assets.append(("pick", pick["id"], f"Value {single_value_bar(trade_value, scale=100, width=10)} {trade_value:>5.1f}  {clean_pick_label_for_user(canonical, pick, save)}"))
    for swap in pick_swaps:
        trade_value = pick_swap_asset_value(canonical, swap, team_state.get("phase", "balanced"))
        assets.append(("pick_swap", swap["id"], f"Value {single_value_bar(trade_value, scale=100, width=10)} {trade_value:>5.1f}  {swap.get('label') or pick_swap_display_label(canonical, swap)}"))
    print_title(title)
    print_team_asset_cap_summary(canonical, save, team["id"])
    for idx, (_, _, label) in enumerate(assets, start=1):
        print(f"{idx:>2}. {label}")
    print(" 0. Back")
    limit_text = f" (max {max_select})" if max_select else ""
    raw = input(f"Enter comma-separated numbers{limit_text}, or 0 to go back: ").strip()
    if raw in {"", "0"}:
        clear_screen()
        return None
    selected: list[dict[str, Any]] = []
    for token in [part.strip() for part in raw.split(",") if part.strip()]:
        if token.isdigit() and 1 <= int(token) <= len(assets):
            kind, value, _ = assets[int(token) - 1]
            asset = {"kind": kind, "value": value}
            if kind == "pick" and prompt_pick_terms and save_path is not None:
                term = prompt_pick_trade_terms(
                    canonical,
                    save_path,
                    value,
                    sender_team_id or team["id"],
                    receiver_team_id,
                    allow_open_receiver=allow_open_receiver,
                )
                if term:
                    asset["pick_obligation_term"] = term
                    if term.get("type") == "pick_swap":
                        preview = canonical_with_pending_pick_terms(canonical, [term])
                        asset = {
                            "kind": "pick_swap",
                            "value": term.get("id"),
                            "id": term.get("id"),
                            "label": pick_swap_display_label(preview, term),
                            "pick_obligation_term": term,
                        }
                    elif term.get("type") != "unprotected":
                        preview = canonical_with_pending_pick_terms(canonical, [term])
                        preview_pick = next((item for item in preview.get("draft_picks", []) if item.get("id") == value), None)
                        if preview_pick:
                            asset["label"] = clean_pick_label_for_user(preview, preview_pick, save)
            selected.append(asset)
            if max_select and len(selected) >= max_select:
                break
    return selected


def print_team_asset_cap_summary(canonical: dict[str, Any], save: dict[str, Any], team_id: str) -> None:
    season = save.get("meta", {}).get("season")
    cap = team_cap_summary(canonical, save, team_id, season=season)
    unresolved = int(cap.get("unresolved_contract_count") or 0)
    unresolved_text = f" | unresolved contracts {unresolved}" if unresolved else ""
    print(
        f"Cap: payroll ${float(cap.get('salary_total_millions') or 0):.1f}M | "
        f"tax room ${float(cap.get('tax_space_millions') or 0):+.1f}M | "
        f"hard-cap room ${float(cap.get('hard_cap_space_millions') or 0):+.1f}M{unresolved_text}"
    )
    print_rule()


def staff_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    team = input(f"Team [{user_team}]: ").strip() or user_team
    while True:
        clear_screen()
        print_staff(canonical, save_path, team)
        print_rule()
        print("1. Replace a staff member")
        print("2. View staff market")
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return
        if choice == "1":
            negotiate_staff_from_menu(canonical, save_path, team, seed)
        elif choice == "2":
            slot = choose_staff_market_slot()
            if slot == "__back__":
                continue
            print_staff_market(canonical, save_path, None if slot == "__all__" else slot)
            wait()


def negotiate_staff_from_menu(canonical: dict[str, Any], save_path: Path, team: str, seed: int, forced_slot: str | None = None) -> None:
    slot = forced_slot or choose_staff_slot(allow_back=True)
    if slot is None:
        return
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    market = staff_market_report(canonical, save, slot=slot, limit=20)["candidates"]
    if not market:
        pause("No candidates are currently on the market for that role.")
        return
    print_staff_market(canonical, save_path, slot)
    print(" 0. Back")
    choice = pick_number("Candidate", 0, len(market), default=0)
    if choice == 0:
        clear_screen()
        return
    candidate = market[choice - 1]
    team_record = resolve_team(canonical, team)
    budget_cap = staff_budget_snapshot(canonical, save, team_record["id"], slot, 0.0)
    max_offer = float(budget_cap.get("max_offer_millions") or 0.0)
    ask = float(candidate.get("asking_salary_millions") or 0.0)
    default_offer = round(min(ask or max_offer, max_offer), 2)
    print_rule()
    print(f"Ask: ${ask:.2f}M / {candidate.get('asking_years')} years")
    print(f"Max legal offer for this role: ${max_offer:.2f}M")
    if budget_cap.get("current_slot_is_interim"):
        print(
            f"Interim credit: ${float(budget_cap.get('interim_replacement_credit_millions') or 0):.2f}M "
            "is freed because this hire replaces that exact interim role."
        )
    if max_offer <= 0:
        pause("There is no staff-budget room for this role right now.")
        return
    raw_salary = input(f"Offer annual salary in millions [{default_offer:.2f}, max {max_offer:.2f}]: ").strip()
    try:
        requested_salary = float(raw_salary) if raw_salary else default_offer
    except ValueError:
        requested_salary = default_offer
    salary = round(max(0.1, min(requested_salary, max_offer)), 2)
    if requested_salary > max_offer:
        print(f"Offer capped at ${max_offer:.2f}M by the staff budget.")
    years = pick_number("Offer years", 1, 5, default=int(candidate.get("asking_years") or 2))
    negotiation = negotiate_staff_hire(canonical, save, candidate["id"], team, slot, seed=seed, offer_salary_millions=salary, offer_years=years)
    write_save(save_path, save)
    print_title("Staff Negotiation")
    print(f"{candidate['name']} -> {ROLE_LABELS.get(slot, slot)}")
    print(f"Ask: ${negotiation['staff_ask']['annual_salary_millions']}M/{negotiation['staff_ask']['years']}y")
    print(f"Offer: ${negotiation['team_offer']['annual_salary_millions']}M/{negotiation['team_offer']['years']}y")
    if negotiation.get("offer_capped_by_budget"):
        print(f"Budget cap: ${negotiation.get('max_offer_millions')}M max for this role")
    budget = negotiation.get("budget") or {}
    evaluation = negotiation.get("evaluation") or {}
    print(
        f"Fit/GM read: upgrade {float(evaluation.get('upgrade') or 0):+.1f}, "
        f"context fit {float(evaluation.get('fit_bonus') or 0):+.1f}, "
        f"decision score {float(evaluation.get('decision_score') or 0):+.1f}"
    )
    interest = offer_interest_score(
        float(negotiation["team_offer"].get("annual_salary_millions") or 0),
        float(negotiation["staff_ask"].get("annual_salary_millions") or 0),
        int(negotiation["team_offer"].get("years") or 1),
        int(negotiation["staff_ask"].get("years") or 1),
        50.0 + float(evaluation.get("fit_bonus") or 0) + float(evaluation.get("decision_score") or 0) * 4.0,
    )
    print_interest_read(
        interest,
        {
            "money": f"${float(negotiation['team_offer'].get('annual_salary_millions') or 0):.2f}M vs ${float(negotiation['staff_ask'].get('annual_salary_millions') or 0):.2f}M ask",
            "years": f"{negotiation['team_offer'].get('years')} vs {negotiation['staff_ask'].get('years')} ask",
            "fit": f"{float(evaluation.get('fit_bonus') or 0):+.1f}",
        },
    )
    print(f"Budget after offer: ${budget.get('available_after_offer_millions', 0):+.2f}M")
    print(f"Decision: {negotiation['decision']} | {negotiation['status']}")
    if negotiation.get("accepted"):
        result = hire_staff_from_save(save, negotiation["id"])
        write_save(save_path, save)
        print(f"Hire result: {result['status']}")
    else:
        save["pending_staff_negotiations"] = [
            item for item in save.get("pending_staff_negotiations", []) if item.get("id") != negotiation.get("id")
        ]
        write_save(save_path, save)
    wait()


def hire_pending_staff_from_menu(save_path: Path) -> None:
    save = load_save(save_path)
    pending = [item for item in save.get("pending_staff_negotiations", []) if item.get("accepted")]
    print_title("Pending Staff Deals")
    if not pending:
        print("No accepted staff negotiations are pending.")
        wait()
        return
    for idx, item in enumerate(pending, start=1):
        candidate = item.get("candidate", {})
        print(f"{idx:>2}. {candidate.get('name')} -> {ROLE_LABELS.get(item.get('slot'), item.get('slot'))} | {item.get('status')}")
    choice = pick_number("Hire", 1, len(pending), default=1)
    result = hire_staff_from_save(save, pending[choice - 1]["id"])
    write_save(save_path, save)
    print(f"Hire result: {result['status']}")
    wait()


def fire_staff_from_menu(canonical: dict[str, Any], save_path: Path, team: str) -> None:
    slot = choose_staff_slot()
    team_record = resolve_team(canonical, team)
    if not yes_no(f"Fire {ROLE_LABELS.get(slot, slot)} for {team_record['abbrev']}?"):
        return
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    result = fire_staff_from_save(save, team_record["id"], slot)
    write_save(save_path, save)
    print(f"Fire result: {result['status']}")
    interim = result.get("interim_staff") or {}
    if interim:
        print(f"Interim replacement: {interim.get('name')} (${float((interim.get('contract') or {}).get('annual_salary_millions') or 0):.1f}M)")


def actions_room(canonical: dict[str, Any], save_path: Path, seed: int) -> None:
    print_actions(canonical, save_path)
    save = load_save(save_path)
    trades_legal = "trades" in (save.get("state", {}).get("legal_actions") or [])
    print_rule()
    print("1. Review/apply one AI suggestion")
    print("2. Process bundles automatically")
    print("3. Reject/clear processed suggestions")
    if trades_legal:
        print("4. Review AI trade offers to you")
    print("0. Back")
    choice = input("> Pick a number: ").strip()
    if choice == "1":
        review_ai_suggestions(canonical, save_path)
    elif choice == "2":
        execute = yes_no("Allow legal accepted AI actions to execute?")
        root = save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd()
        with loading_screen(root, "Processing AI bundles...", seed=seed):
            result = process_ai_actions(canonical, save_path, seed=seed, execute=execute, limit=20)
        print_actions_result(result)
    elif choice == "3":
        save = load_save(save_path)
        before = len(save.get("pending_ai_actions", []))
        save["pending_ai_actions"] = [item for item in save.get("pending_ai_actions", []) if item.get("status") not in {"processed", "rejected", "executed"}]
        write_save(save_path, save)
        print(f"Cleared {before - len(save['pending_ai_actions'])} old AI action(s).")
    elif choice == "4" and trades_legal:
        user_trade_offers_room(canonical, save_path)
    wait()


def ai_action_has_visible_content(action: dict[str, Any]) -> bool:
    if action.get("status") in {"processed", "executed", "rejected"}:
        return False
    payload = action.get("payload") or {}
    if action.get("action_type") == "trade_recommendations":
        return any(
            proposal.get("accepted_by_all") and (proposal.get("legality") or {}).get("status") == "legal"
            for proposal in payload.get("proposals", [])
        )
    if action.get("action_type") == "free_agency_recommendations":
        return any(positive_accepted_offer(item) for item in payload.get("negotiations", []))
    if action.get("action_type") == "staff_change_recommendations":
        return False
    return True


def review_ai_suggestions(canonical: dict[str, Any], save_path: Path) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    actions = [item for item in save.get("pending_ai_actions", []) if ai_action_has_visible_content(item)]
    if not actions:
        print("No pending AI suggestions.")
        return
    for idx, action in enumerate(actions, start=1):
        print(f"{idx:>2}. {action.get('action_type')} | {action.get('date')} | {action.get('status')}")
    action = actions[pick_number("Action", 1, len(actions), default=1) - 1]
    payload = action.get("payload") or {}
    if action.get("action_type") == "trade_recommendations":
        proposals = [
            proposal for proposal in payload.get("proposals", [])
            if proposal.get("accepted_by_all") and (proposal.get("legality") or {}).get("status") == "legal"
        ]
        if not proposals:
            print("No accepted legal AI-AI trades in this bundle.")
            return
        for idx, proposal in enumerate(proposals, start=1):
            print(f"{idx:>2}. {proposal_headline(proposal)} | accepted={proposal.get('accepted_by_all')} | {proposal.get('legality', {}).get('status')}")
        if proposals and yes_no("Apply one accepted legal trade?"):
            proposal = proposals[pick_number("Trade", 1, len(proposals), default=1) - 1]
            save.setdefault("pending_trade_proposals", []).append(proposal)
            write_save(save_path, save)
            result = apply_trade_to_save(save_path, proposal["proposal"]["id"], date=save.get("state", {}).get("current_date"))
            print(f"Trade apply result: {result['status']}")
    elif action.get("action_type") == "free_agency_recommendations":
        negotiations = [
            item for item in payload.get("negotiations", [])
            if positive_accepted_offer(item)
        ]
        if not negotiations:
            print("No accepted legal free-agent signings in this bundle.")
            return
        for idx, item in enumerate(negotiations, start=1):
            decision = item.get("decision") or {}
            offer = decision.get("accepted_offer") or {}
            negotiation = item.get("negotiation", {})
            player = players.get(negotiation.get("player_id") or decision.get("player_id"), {})
            team = teams.get(negotiation.get("team_id") or decision.get("team_id"), {})
            print(f"{idx:>2}. {player.get('name') or decision.get('player_id')} -> {team.get('abbrev') or decision.get('team_id')} | accepted={item.get('accepted')} | ${float(offer.get('annual_salary') or 0)/1_000_000:.1f}M")
        if negotiations and yes_no("Apply one accepted signing?"):
            item = negotiations[pick_number("Signing", 1, len(negotiations), default=1) - 1]
            active = canonical_with_save(canonical, save)
            player_id = (item.get("negotiation") or {}).get("player_id") or (item.get("decision") or {}).get("player_id")
            active_player = next((player for player in active.get("players", []) if player.get("id") == player_id), {})
            if active_player.get("team_id") and player_id not in set(save.get("free_agent_player_ids", [])):
                print("Signing blocked: that player is currently under contract in this save.")
                return
            save.setdefault("pending_contract_negotiations", []).append(item)
            write_save(save_path, save)
            result = apply_contract_to_save(save_path, item["negotiation"]["id"], date=save.get("state", {}).get("current_date"))
            print(f"Signing apply result: {result['status']}")
    elif action.get("action_type") == "draft_window_open":
        print("Draft window is open. Use Offseason room -> Draft room.")
    elif action.get("action_type") == "staff_change_recommendations":
        recommendations = payload.get("recommendations", [])
        if not recommendations:
            print("No staff recommendations in this bundle.")
            return
        for idx, item in enumerate(recommendations, start=1):
            current = item.get("current_staff") or {}
            candidate = item.get("candidate") or {}
            offer = item.get("recommended_offer") or {}
            print(
                f"{idx:>2}. {item.get('team_abbrev') or team_id_to_abbrev(item.get('team_id'))} "
                f"{ROLE_LABELS.get(item.get('slot'), item.get('slot'))}: "
                f"{current.get('name', 'current staff')} ({float(current.get('grade') or 0):.1f}) -> "
                f"{candidate.get('name')} ({float(candidate.get('grade') or 0):.1f}) "
                f"| offer ${float(offer.get('annual_salary_millions') or 0):.1f}M/{int(offer.get('years') or 0)}y"
            )
            print(f"    Why: {', '.join(item.get('reasons', [])[:4])}")
        if recommendations and yes_no("Apply one staff recommendation now?"):
            item = recommendations[pick_number("Staff move", 1, len(recommendations), default=1) - 1]
            offer = item.get("recommended_offer") or {}
            try:
                negotiation = negotiate_staff_hire(
                    active,
                    save,
                    item["candidate_id"],
                    item.get("team_abbrev") or item["team_id"],
                    item["slot"],
                    seed=int(save.get("meta", {}).get("seed") or 1),
                    offer_salary_millions=float(offer.get("annual_salary_millions") or 0.0),
                    offer_years=int(offer.get("years") or 2),
                )
            except ValueError as exc:
                print(f"Staff move blocked: {exc}")
                return
            if negotiation.get("accepted"):
                result = hire_staff_from_save(save, negotiation["id"])
                write_save(save_path, save)
                print(f"Staff hire result: {result.get('status')}")
            else:
                write_save(save_path, save)
                print(f"Candidate declined: {negotiation.get('decision')}")
    if yes_no("Mark this AI bundle reviewed?"):
        save = load_save(save_path)
        for item in save.get("pending_ai_actions", []):
            if item.get("id") == action.get("id"):
                item["status"] = "processed"
        write_save(save_path, save)


def saved_trades_room(canonical: dict[str, Any], save_path: Path) -> None:
    save = load_save(save_path)
    trades = save.get("pending_trade_proposals", [])
    print_title("Saved Trade Offers")
    if not trades:
        print("No saved trade offers or counters.")
        return
    for idx, trade in enumerate(trades, start=1):
        print(f"{idx:>2}. {proposal_headline(trade)} | {trade.get('legality', {}).get('status')} | accepted={trade.get('accepted_by_all')}")
    print(" 0. Back")
    choice = pick_number("Trade", 0, len(trades), default=0)
    if choice == 0:
        return
    trade = trades[choice - 1]
    print_title("Saved Trade")
    print(proposal_headline(trade))
    print_value_bars(trade)
    for evaluation in trade.get("evaluations", []):
        print(f"{evaluation.get('team_abbrev') or evaluation.get('perspective_team_id')}: {evaluation.get('decision')} | net {evaluation.get('net_value')} | {', '.join(evaluation.get('reasons', [])[:4])}")
    print_rule()
    print("1. Apply if accepted/legal")
    print("2. Delete saved offer")
    print("0. Back")
    action = pick_number("Action", 0, 2, default=0)
    if action == 1:
        if not trade_apply_authorized(trade):
            print("Only accepted legal trades can be applied from saved offers. Rejected offers need to be rebuilt or countered.")
            return
        result = apply_trade_to_save(save_path, trade["proposal"]["id"], date=save.get("state", {}).get("current_date"))
        print(f"Trade apply result: {result.get('status')}")
    elif action == 2:
        proposal_id = trade.get("proposal", {}).get("id") or trade.get("id")
        save["pending_trade_proposals"] = [
            item for item in trades if (item.get("proposal", {}).get("id") or item.get("id")) != proposal_id
        ]
        write_save(save_path, save)
        print("Saved offer deleted.")


def user_trade_offers_room(canonical: dict[str, Any], save_path: Path) -> None:
    while True:
        save = load_save(save_path)
        offers = [
            offer for offer in save.get("user_trade_offers", [])
            if (offer.get("offer_context") or {}).get("status") == "pending_user_review"
        ]
        clear_screen()
        print_title("AI Trade Offers To You")
        if not offers:
            print("No active AI offers to your team.")
            wait()
            return
        for idx, offer in enumerate(offers, start=1):
            print(f"{idx:>2}. {proposal_headline(offer)} | {clean_label((offer.get('legality') or {}).get('status'))}")
        print(" 0. Back")
        choice = pick_number("Offer", 0, len(offers), default=0)
        if choice == 0:
            return
        offer = offers[choice - 1]
        while True:
            clear_screen()
            print_title("AI Trade Offer")
            print(proposal_headline(offer))
            print_value_bars(offer)
            print_rule()
            print("1. Inspect details")
            print("2. Accept and execute")
            print("3. Save as counter scaffold")
            print("4. Reject")
            print("0. Back")
            action = pick_number("Action", 0, 4, default=0)
            if action == 0:
                break
            if action == 1:
                print_trade_offer_details(canonical, offer, save_path)
                wait()
                continue
            save = load_save(save_path)
            proposal_id = (offer.get("proposal") or {}).get("id") or offer.get("id")
            if action == 2:
                offer = attach_pick_terms_to_trade(canonical_with_save(canonical, ensure_league_save_defaults(save, canonical)), save_path, offer)
                save.setdefault("pending_trade_proposals", []).append(offer)
                write_save(save_path, save)
                result = apply_trade_to_save(save_path, offer["proposal"]["id"], date=save.get("state", {}).get("current_date"))
                save = load_save(save_path)
                mark_user_trade_offer_status(save, proposal_id, "accepted_executed" if result.get("status") == "applied" else "stale_asset_moved")
                write_save(save_path, save)
                pause(f"Trade apply result: {result.get('status')}")
                break
            if action == 3:
                scaffold = {**offer, "offer_context": {"status": "counter_scaffold", "created_date": save.get("state", {}).get("current_date")}}
                save.setdefault("pending_trade_proposals", []).append(scaffold)
                mark_user_trade_offer_status(save, proposal_id, "saved_as_counter")
                write_save(save_path, save)
                pause("Offer saved as a counter scaffold.")
                break
            if action == 4:
                mark_user_trade_offer_status(save, proposal_id, "rejected_by_user")
                write_save(save_path, save)
                pause("Offer rejected.")
                break


def mark_user_trade_offer_status(save: dict[str, Any], proposal_id: str | None, status: str) -> None:
    for offer in save.get("user_trade_offers", []):
        if ((offer.get("proposal") or {}).get("id") or offer.get("id")) == proposal_id:
            offer.setdefault("offer_context", {})["status"] = status


def offseason_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    while True:
        save = load_save(save_path)
        phase = save.get("state", {}).get("phase")
        print_title(f"Offseason Room | {phase}")
        if phase == "draft_lottery":
            print("1. Run/view draft lottery")
        elif phase == "draft":
            print("1. Draft room")
        else:
            print("1. Draft room (locked until draft)")
        if phase == "free_agency":
            print("2. Free agency room")
        else:
            print("2. Free agency room (locked until free agency)")
        print("3. Year review / retirement reports")
        print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return
        if choice == "1":
            if phase == "draft_lottery":
                year = str(int(str(save.get("meta", {}).get("season") or "2025-26").split("-")[0]) + 1)
                print_title("You Are Entering The Draft Lottery")
                print("Lottery odds are based on this save's standings. Press Enter to reveal the order.")
                input()
                order = run_draft_lottery(canonical, save_path, year=year, seed=None)
                print_lottery(order)
                wait()
            elif phase == "draft":
                draft_room(canonical, save_path, user_team, seed)
            else:
                pause("The draft room unlocks when the draft begins.")
        elif choice == "2":
            if phase == "free_agency":
                free_agency_room(canonical, save_path, user_team, seed)
            else:
                pause("Free agency opens after the draft.")
        elif choice == "3":
            print_offseason_reports(canonical, save_path, user_team)
            wait()


def print_offseason_reports(canonical: dict[str, Any], save_path: Path, user_team: str) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team = resolve_team(canonical, user_team)
    print_title("Offseason Reports")
    retirements = sorted(save.get("retirement_reports", []), key=lambda item: item.get("date", ""), reverse=True)
    if retirements:
        report = retirements[0]
        print(style(f"Retirements | {report.get('season')}", "accent"))
        for item in (report.get("retirements") or [])[:15]:
            print(f"  {item.get('name'):<26} age {age_text(item, 4)}  {item.get('position') or '-'}")
    else:
        print("No retirement report has been generated yet.")
    print_rule()
    awards = sorted(
        [item for item in save.get("league_awards", []) if item.get("season")],
        key=lambda item: (item.get("season", ""), item.get("award", "")),
        reverse=True,
    )
    if awards:
        latest_season = awards[0].get("season")
        print(style(f"League Awards | {latest_season}", "accent"))
        for award in [item for item in awards if item.get("season") == latest_season]:
            line = award.get("stat_line") or {}
            print(
                f"  {award.get('award'):<4} {str(award.get('player_name') or '-'):<24} "
                f"{award.get('team_abbrev') or '-':<3}  "
                f"{float(line.get('pts') or 0):>4.1f}p {float(line.get('reb') or 0):>4.1f}r {float(line.get('ast') or 0):>4.1f}a"
            )
    else:
        print("No league awards have been generated yet.")
    print_rule()
    reviews = [
        item for item in save.get("year_reviews", [])
        if item.get("team_id") == team["id"]
    ]
    reviews.sort(key=lambda item: item.get("generated_date", ""), reverse=True)
    if not reviews:
        print("No year-in-review has been generated for your team yet.")
        return
    review = reviews[0]
    print(style(f"{team['abbrev']} Development Year In Review | {review.get('season')}", "accent"))
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    print_development_delta_matrix("Cumulative Trait Movement", review.get("players") or [], players)


def draft_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, forced: bool = False) -> str | None:
    while True:
        clear_screen()
        save = load_save(save_path)
        year = str(int(str(save.get("meta", {}).get("season") or "2025-26").split("-")[0]) + 1)
        state = ensure_live_draft_state(canonical, save_path, year, seed)
        current = current_draft_selection(state)
        print_title(f"Draft Room | {year}")
        print_draft_clock(canonical, state, current, user_team=user_team)
        print_rule()
        if current:
            print("1. Make/sim current pick")
            print("2. Sim to next user pick")
            print("3. Draft board")
            print("4. Full draft summary")
            print("5. Team dashboard")
            print("6. Sim entire draft")
            print("9. Trade room / move draft assets")
        else:
            print("1. Full draft recap")
            print("5. Team dashboard")
            print("9. Trade room / move draft assets")
            print("0. Continue to free agency")
        if current and forced:
            print("0. Save and quit")
        choice = input("> Pick a number: ").strip()
        if choice == "0" and not current:
            root = save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd()
            with loading_screen(root, "Opening free agency...", seed=seed):
                finish_draft_phase(canonical, save_path, year)
            clear_screen()
            return "done"
        if choice == "0":
            if forced:
                clear_screen()
                return "quit"
            print("The draft is active. Finish it, sim to your next pick, or sim the entire draft before leaving.")
            wait()
            continue
        if not current:
            if choice == "1":
                print_live_draft_summary(canonical, save_path, user_team, year, seed)
            elif choice == "5":
                root = save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd()
                print_dashboard(root, canonical, save_path, user_team, user_team=user_team, seed=seed)
            elif choice == "9":
                active = canonical_with_save(canonical, ensure_league_save_defaults(load_save(save_path), canonical))
                trade_room(active, save_path, user_team, seed)
            continue
        if choice == "1":
            if (current.get("selection") or {}).get("team_id") == resolve_team(canonical, user_team)["id"]:
                chosen = choose_user_draft_pick(canonical, save_path, state, current)
                if chosen is None:
                    continue
                current = chosen
            result = apply_current_draft_selection(save_path, current, canonical=canonical, user_team=user_team, seed=seed)
            print_draft_breaking_news(drain_draft_trade_news(save_path))
            print_draft_apply_result(result)
            wait()
        elif choice == "2":
            print(style("Simulating to your next pick...", "accent"))
            with loading_screen(save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd(), "Simulating to your next pick...", seed=seed):
                result = sim_to_next_user_pick(canonical, save_path, user_team, seed=seed)
            news = result.get("draft_trade_news") or []
            print_draft_breaking_news(news)
            print(f"Simulated {result['applied_count']} pick(s).")
            if result.get("current_selection"):
                print("Stopped at your next pick.")
            else:
                print("Draft complete.")
            if news:
                wait()
            continue
        elif choice == "3":
            print_draft_board(canonical, save_path, user_team, limit=60)
        elif choice == "4":
            print_live_draft_summary(canonical, save_path, user_team, year, seed)
        elif choice == "5":
            root = save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd()
            print_dashboard(root, canonical, save_path, user_team, user_team=user_team, seed=seed)
        elif choice == "9":
            active = canonical_with_save(canonical, ensure_league_save_defaults(load_save(save_path), canonical))
            trade_room(active, save_path, user_team, seed)
        elif choice == "6":
            print(style("Simulating the rest of the draft...", "accent"))
            with loading_screen(save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd(), "Simulating the full draft...", seed=seed):
                result = sim_entire_draft(save_path, canonical=canonical, user_team=user_team, seed=seed)
            print_draft_breaking_news(result.get("draft_trade_news") or [])
            print(f"Draft complete. Applied {result['applied_count']} pick(s).")
            print_full_draft_recap(canonical, save_path, year)
            wait()


def finish_draft_phase(canonical: dict[str, Any], save_path: Path, year: str) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("draft_state") or {}
    if state.get("year") == str(year):
        state["status"] = "completed"
    set_save_date_phase(save, f"{year}-06-27")
    prepare_free_agency_pool(canonical, save)
    write_save(save_path, save)


def ensure_live_draft_state(canonical: dict[str, Any], save_path: Path, year: str, seed: int) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("draft_state") or {}
    if state.get("year") == year and state.get("status") in {"in_progress", "completed"} and state.get("draft"):
        changed = sync_live_draft_state_to_saved_order(canonical, save, year)
        changed = refresh_live_draft_state_ownership(canonical, save, year) or changed
        if changed:
            write_save(save_path, save)
        return state
    active = canonical_with_save(canonical, save)
    draft = simulate_draft(active, year, seed=seed)
    draft = apply_saved_draft_order_to_draft(canonical, save, year, draft)
    save["draft_state"] = {
        "year": year,
        "status": "in_progress",
        "current_index": 0,
        "draft": draft,
        "applied_selection_ids": [],
        "ai_draft_traded_pick_ids": [],
        "ai_draft_trade_budget": {"top_10": 0, "picks_11_25": 0, "total": 0},
        "ai_draft_trade_news_queue": [],
    }
    if draft.get("draft_order") or draft.get("lottery"):
        save.setdefault("draft_orders", {})[year] = {"draft_order": draft.get("draft_order", []), "lottery": draft.get("lottery")}
    write_save(save_path, save)
    return save["draft_state"]


def ensure_draft_ai_trade_state(state: dict[str, Any]) -> None:
    state.setdefault("ai_draft_traded_pick_ids", [])
    state.setdefault("ai_draft_trade_budget", {"top_10": 0, "picks_11_25": 0, "total": 0})
    state.setdefault("ai_draft_trade_news_queue", [])


def apply_ai_trade_candidate_to_save(canonical: dict[str, Any], save_path: Path, candidate: dict[str, Any], date_value: str) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    proposal = candidate.get("proposal") or {}
    proposal_id = proposal.get("id")
    if not proposal_id:
        return {"status": "not_applied", "notes": "AI trade candidate had no proposal id."}
    pending = save.setdefault("pending_trade_proposals", [])
    if not any(((item.get("proposal") or {}).get("id") or item.get("id")) == proposal_id for item in pending):
        pending.append({**candidate, "accepted_by_all": True})
    write_save(save_path, save)
    return apply_trade_to_save(save_path, proposal_id, date=date_value)


def maybe_run_ai_draft_trades_before_pick(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, force: bool = False) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.setdefault("draft_state", {})
    ensure_draft_ai_trade_state(state)
    current = current_draft_selection(state)
    if not current:
        write_save(save_path, save)
        return {"applied_count": 0, "trades": []}
    user_team_id = resolve_team(canonical, user_team)["id"]
    selection = current.get("selection") or {}
    seller_team_id = selection.get("team_id")
    pick_id = selection.get("pick_id") or (current.get("pick") or {}).get("id")
    overall = int(selection.get("overall_pick") or 999)
    if not pick_id or seller_team_id == user_team_id or overall > 25:
        write_save(save_path, save)
        return {"applied_count": 0, "trades": []}
    traded_ids = set(state.get("ai_draft_traded_pick_ids") or [])
    used_ids = set(state.get("used_pick_ids") or [])
    if pick_id in traded_ids or pick_id in used_ids:
        write_save(save_path, save)
        return {"applied_count": 0, "trades": []}
    budget = state.setdefault("ai_draft_trade_budget", {"top_10": 0, "picks_11_25": 0, "total": 0})
    if not force:
        if int(budget.get("total") or 0) >= 6:
            write_save(save_path, save)
            return {"applied_count": 0, "trades": []}
        if overall <= 10 and int(budget.get("top_10") or 0) >= 2:
            write_save(save_path, save)
            return {"applied_count": 0, "trades": []}
        if 11 <= overall <= 25 and int(budget.get("picks_11_25") or 0) >= 5:
            write_save(save_path, save)
            return {"applied_count": 0, "trades": []}
    active = with_transaction_context(canonical_with_save(canonical, save))
    candidate = best_ai_draft_trade_candidate(active, save, state, current, user_team_id, seed)
    if not candidate:
        write_save(save_path, save)
        return {"applied_count": 0, "trades": []}
    applied = apply_ai_trade_candidate_to_save(canonical, save_path, candidate, save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
    if applied.get("status") != "applied":
        return {"applied_count": 0, "trades": [], "skipped": applied}
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.setdefault("draft_state", {})
    ensure_draft_ai_trade_state(state)
    proposal = candidate.get("proposal") or {}
    involved_pick_ids = {
        asset.get("id")
        for asset in [*(proposal.get("from_assets") or []), *(proposal.get("to_assets") or [])]
        if asset.get("kind") == "pick" and asset.get("id")
    }
    state["ai_draft_traded_pick_ids"] = sorted(set(state.get("ai_draft_traded_pick_ids") or []) | involved_pick_ids)
    budget = state.setdefault("ai_draft_trade_budget", {"top_10": 0, "picks_11_25": 0, "total": 0})
    budget["total"] = int(budget.get("total") or 0) + 1
    if overall <= 10:
        budget["top_10"] = int(budget.get("top_10") or 0) + 1
    elif overall <= 25:
        budget["picks_11_25"] = int(budget.get("picks_11_25") or 0) + 1
    headline = draft_trade_headline(active, state, proposal)
    state.setdefault("ai_draft_trade_news_queue", []).append(
        {
            "id": stable_id("draft_breaking_news", proposal.get("id"), overall),
            "overall_pick": overall,
            "headline": headline,
            "proposal_id": proposal.get("id"),
        }
    )
    refresh_live_draft_state_ownership(canonical, save, state.get("year"))
    write_save(save_path, save)
    return {"applied_count": 1, "trades": [candidate], "apply_result": applied}


def best_ai_draft_trade_candidate(
    active: dict[str, Any],
    save: dict[str, Any],
    state: dict[str, Any],
    current: dict[str, Any],
    user_team_id: str,
    seed: int,
) -> dict[str, Any] | None:
    selection = current.get("selection") or {}
    pick_id = selection.get("pick_id") or (current.get("pick") or {}).get("id")
    seller_team_id = selection.get("team_id")
    overall = int(selection.get("overall_pick") or 999)
    if not pick_id or not seller_team_id:
        return None
    seller = team_by_id(active, seller_team_id)
    unavailable = taken_draft_prospect_ids(state)
    seller_recs = pick_recommendations(active, seller["abbrev"], pick_id, limit=5, seed=seed, unavailable_prospect_ids=unavailable).get("recommendations") or []
    seller_top = float(((seller_recs[0] or {}).get("entry") or {}).get("risk_adjusted_grade") or 0.0) if seller_recs else 0.0
    seller_second = float(((seller_recs[1] or {}).get("entry") or {}).get("risk_adjusted_grade") or seller_top) if len(seller_recs) > 1 else seller_top
    seller_willingness = max(0.0, 8.0 - max(0.0, seller_top - seller_second))
    candidates: list[tuple[float, dict[str, Any]]] = []
    budget = state.get("ai_draft_trade_budget") or {}
    prior_trade_count = int(budget.get("total") or 0)
    quiet_mid_first_market = overall >= 11 and prior_trade_count < max(1, (overall - 8) // 5)
    for buyer in sorted(active.get("teams", []), key=lambda item: item.get("abbrev", "")):
        if buyer.get("id") in {seller_team_id, user_team_id}:
            continue
        lower_pick = draft_trade_lower_pick_for_buyer(active, state, buyer["id"], overall)
        if not lower_pick and overall <= 10:
            continue
        buyer_recs = pick_recommendations(active, buyer["abbrev"], pick_id, limit=3, seed=seed, unavailable_prospect_ids=unavailable).get("recommendations") or []
        if not buyer_recs:
            continue
        buyer_grade = float(((buyer_recs[0] or {}).get("entry") or {}).get("risk_adjusted_grade") or 0.0)
        buyer_grade_floor = 60.0 if overall <= 10 else 55.0
        if quiet_mid_first_market:
            buyer_grade_floor -= 4.0
        if buyer_grade < buyer_grade_floor:
            continue
        to_assets = draft_trade_offer_assets(active, state, buyer["id"], pick_id, lower_pick, overall)
        if not to_assets:
            continue
        try:
            report = evaluate_trade(active, seller["abbrev"], buyer["abbrev"], [{"kind": "pick", "value": pick_id}], to_assets, seed=seed, date=save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
        except ValueError:
            continue
        candidate = candidate_from_evaluation(active, report)
        if candidate.get("legality", {}).get("status") != "legal":
            continue
        seller_eval = next((item for item in candidate.get("evaluations", []) if item.get("perspective_team_id") == seller_team_id), {})
        buyer_eval = next((item for item in candidate.get("evaluations", []) if item.get("perspective_team_id") == buyer["id"]), {})
        seller_net = float(seller_eval.get("net_value") or -99.0)
        buyer_net = float(buyer_eval.get("net_value") or -99.0)
        seller_state = next((item for item in active.get("team_strategic_states", []) if item.get("team_id") == seller_team_id), {})
        seller_floor = 8.0 if overall == 1 else 4.0 if overall <= 5 else 1.5 if overall <= 10 else -2.0
        if overall <= 8 and seller_state.get("phase") in {"rebuilding", "developing"}:
            seller_floor += 4.0
        buyer_floor = -22.0
        if quiet_mid_first_market:
            seller_floor -= 2.5
            buyer_floor -= 4.0
        if seller_net < seller_floor or buyer_net < buyer_floor:
            continue
        move_down = draft_trade_move_down_distance(state, buyer["id"], overall)
        urgency = buyer_grade - max(0.0, move_down - 5) * 0.55
        score = seller_net * 1.6 + buyer_net * 0.45 + urgency + seller_willingness
        candidate["accepted_by_all"] = True
        candidate["ai_draft_trade_context"] = {
            "overall_pick": overall,
            "buyer_grade": round(buyer_grade, 2),
            "seller_willingness": round(seller_willingness, 2),
            "move_down": move_down,
        }
        candidates.append((score, candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], jsonable_proposal_id(item[1])), reverse=True)
    return candidates[0][1]


def taken_draft_prospect_ids(state: dict[str, Any]) -> set[str]:
    pending = state.get("draft", {}).get("pending_draft_selections", [])
    index = int(state.get("current_index") or 0)
    return {
        (item.get("selection") or {}).get("prospect_id")
        for item in pending[:index]
        if (item.get("selection") or {}).get("prospect_id")
    }


def draft_trade_lower_pick_for_buyer(active: dict[str, Any], state: dict[str, Any], buyer_team_id: str, current_overall: int) -> dict[str, Any] | None:
    traded = set(state.get("ai_draft_traded_pick_ids") or [])
    used = set(state.get("used_pick_ids") or [])
    pending = state.get("draft", {}).get("pending_draft_selections", [])
    max_drop = 8 if current_overall <= 10 else 10
    candidates = []
    for item in pending[int(state.get("current_index") or 0) + 1:]:
        selection = item.get("selection") or {}
        pick = item.get("pick") or {}
        pick_id = selection.get("pick_id") or pick.get("id")
        overall = int(selection.get("overall_pick") or 999)
        if (
            selection.get("team_id") == buyer_team_id
            and int(pick.get("round") or (1 if overall <= 30 else 2)) == 1
            and current_overall < overall <= current_overall + max_drop
            and pick_id not in traded
            and pick_id not in used
        ):
            active_pick = pick_by_id(active, pick_id) or pick
            candidates.append((overall, {**active_pick, "overall_pick": overall}))
    return sorted(candidates, key=lambda item: item[0])[0][1] if candidates else None


def draft_trade_offer_assets(active: dict[str, Any], state: dict[str, Any], buyer_team_id: str, target_pick_id: str, lower_pick: dict[str, Any] | None, overall: int) -> list[dict[str, Any]]:
    traded = set(state.get("ai_draft_traded_pick_ids") or [])
    used = set(state.get("used_pick_ids") or [])
    assets: list[dict[str, Any]] = []
    if lower_pick:
        assets.append({"kind": "pick", "value": lower_pick["id"]})
    target_pick = pick_by_id(active, target_pick_id)
    target_value = pick_asset_value(target_pick, "neutral")
    current_value = sum(pick_asset_value(pick_by_id(active, asset["value"]), "neutral") for asset in assets)
    lower_overall = int((lower_pick or {}).get("overall_pick") or (lower_pick or {}).get("projected_pick_slot") or 999)
    move_down = max(0, lower_overall - overall) if lower_pick else 99
    extras = [
        pick for pick in tradeable_picks_for_team(active, buyer_team_id)
        if pick.get("id") not in {target_pick_id, *(asset["value"] for asset in assets), *traded, *used}
    ]
    firsts = sorted(
        [pick for pick in extras if int(pick.get("round") or 0) == 1 and str(pick.get("season") or "") != str((target_pick or {}).get("season") or "")],
        key=lambda pick: pick_asset_value(pick, "neutral"),
        reverse=True,
    )
    seconds = sorted(
        [pick for pick in extras if int(pick.get("round") or 0) == 2],
        key=lambda pick: pick_asset_value(pick, "neutral"),
        reverse=True,
    )
    if overall == 1:
        required_factor = 1.34
    elif overall <= 3:
        required_factor = 1.28
    elif overall <= 5:
        required_factor = 1.22
    elif overall <= 10:
        required_factor = 1.16
    elif overall <= 18 or move_down >= 5:
        required_factor = 1.08
    else:
        required_factor = 0.96
    need_future_first = (overall <= 18 or move_down >= 5 or not lower_pick) and current_value < target_value * min(1.04, required_factor)
    first_idx = 0
    while first_idx < len(firsts) and (need_future_first or current_value < target_value * 0.86):
        pick = firsts[first_idx]
        assets.append({"kind": "pick", "value": pick["id"]})
        current_value += pick_asset_value(pick, "neutral")
        first_idx += 1
        need_future_first = False
        if current_value >= target_value * required_factor or len(assets) >= 3:
            break
    for pick in seconds[:3]:
        if current_value >= target_value * required_factor and len(assets) > 1:
            break
        if move_down >= 5 and current_value < target_value * 0.95:
            continue
        assets.append({"kind": "pick", "value": pick["id"]})
        current_value += pick_asset_value(pick, "neutral")
    has_future_first = any(
        int((pick_by_id(active, asset["value"]) or {}).get("round") or 0) == 1
        and str((pick_by_id(active, asset["value"]) or {}).get("season") or "") != str((target_pick or {}).get("season") or "")
        for asset in assets
        if asset.get("kind") == "pick"
    )
    if lower_pick and len(assets) == 1:
        return []
    if overall == 1 and lower_pick and move_down >= 2 and not has_future_first:
        return []
    if overall <= 10 and move_down >= 3 and not has_future_first and current_value < target_value * 1.08:
        return []
    if move_down >= 6 and not has_future_first and current_value < target_value:
        return []
    if current_value < target_value * required_factor:
        return []
    return assets[:4]


def draft_trade_headline(active: dict[str, Any], state: dict[str, Any], proposal: dict[str, Any]) -> str:
    from_assets = ", ".join(draft_trade_asset_label(active, state, asset) for asset in proposal.get("from_assets", [])) or "assets"
    to_assets = ", ".join(draft_trade_asset_label(active, state, asset) for asset in proposal.get("to_assets", [])) or "assets"
    return f"Trade completed: {from_assets} for {to_assets}."


def draft_trade_asset_label(active: dict[str, Any], state: dict[str, Any], asset: dict[str, Any]) -> str:
    if asset.get("kind") != "pick":
        return asset.get("label") or asset.get("name") or asset.get("id") or "asset"
    pick_id = asset.get("id") or asset.get("value")
    pending = (state.get("draft") or {}).get("pending_draft_selections") or []
    item = next(
        (
            row for row in pending
            if ((row.get("selection") or {}).get("pick_id") or (row.get("pick") or {}).get("id")) == pick_id
        ),
        None,
    )
    if item:
        selection = item.get("selection") or {}
        pick = item.get("pick") or {}
        owner = selection.get("team_id") or pick.get("current_owner_team_id")
        return f"Pick #{selection.get('overall_pick')} (owned by {team_id_to_abbrev(owner)})"
    pick = pick_by_id(active, pick_id)
    return pick_display_label(active, pick) if pick else asset.get("label") or str(pick_id)


def draft_trade_move_down_distance(state: dict[str, Any], buyer_team_id: str, current_overall: int) -> int:
    pending = state.get("draft", {}).get("pending_draft_selections", [])
    later = [
        int((item.get("selection") or {}).get("overall_pick") or 999)
        for item in pending
        if (item.get("selection") or {}).get("team_id") == buyer_team_id
        and int((item.get("selection") or {}).get("overall_pick") or 999) > current_overall
    ]
    return min(later) - current_overall if later else 12


def jsonable_proposal_id(candidate: dict[str, Any]) -> str:
    return str((candidate.get("proposal") or {}).get("id") or candidate.get("summary") or "")


def draft_pick_identity(row: dict[str, Any]) -> str | None:
    return row.get("pick_id") or row.get("id")


def refresh_live_draft_state_ownership(canonical: dict[str, Any], save: dict[str, Any], year: str | None = None) -> bool:
    state = save.get("draft_state") or {}
    if year and str(state.get("year") or "") != str(year):
        return False
    draft = state.get("draft") or {}
    pending = draft.get("pending_draft_selections") or []
    if not pending:
        return False
    active = canonical_with_save(canonical, save)
    teams = {team.get("id"): team for team in active.get("teams", [])}
    active_picks = {pick.get("id"): pick for pick in active.get("draft_picks", [])}
    order = ((save.get("draft_orders") or {}).get(str(state.get("year") or year or "")) or {}).get("draft_order") or []
    order_by_pick_id: dict[str, dict[str, Any]] = {}
    for pick in order:
        pick_id = draft_pick_identity(pick)
        if pick_id and pick_id not in order_by_pick_id:
            order_by_pick_id[pick_id] = pick
    overrides = save.get("draft_pick_overrides") or {}
    changed = False
    seen_pending_pick_ids: set[str] = set()
    for item in pending:
        selection = item.setdefault("selection", {})
        pick = item.setdefault("pick", {})
        pick_id = selection.get("pick_id") or pick.get("id")
        if not pick_id:
            continue
        if pick_id in seen_pending_pick_ids:
            continue
        seen_pending_pick_ids.add(pick_id)
        override = overrides.get(pick_id)
        if override == "used_draft_pick":
            continue
        owner_id = override or (order_by_pick_id.get(pick_id) or {}).get("current_owner_team_id") or (active_picks.get(pick_id) or {}).get("current_owner_team_id")
        if not owner_id or owner_id == selection.get("team_id"):
            continue
        selection["team_id"] = owner_id
        pick["current_owner_team_id"] = owner_id
        if pick_id in order_by_pick_id:
            order_by_pick_id[pick_id]["current_owner_team_id"] = owner_id
            order_by_pick_id[pick_id]["team_abbrev"] = (teams.get(owner_id) or {}).get("abbrev")
        if item.get("decision"):
            item["decision"]["team_id"] = owner_id
        item["team"] = teams.get(owner_id, {"id": owner_id, "abbrev": team_id_to_abbrev(owner_id)})
        changed = True
    return changed


def current_draft_selection(state: dict[str, Any]) -> dict[str, Any] | None:
    pending = state.get("draft", {}).get("pending_draft_selections", [])
    index = int(state.get("current_index") or 0)
    if index >= len(pending):
        state["status"] = "completed"
        return None
    return pending[index]


def apply_saved_draft_order_to_draft(canonical: dict[str, Any], save: dict[str, Any], year: str, draft: dict[str, Any]) -> dict[str, Any]:
    order = ((save.get("draft_orders") or {}).get(str(year)) or {}).get("draft_order") or []
    pending = draft.get("pending_draft_selections") or []
    if not order or not pending:
        return draft
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    picks_by_overall = {int((item.get("selection") or {}).get("overall_pick") or idx + 1): item for idx, item in enumerate(pending)}
    seen_pick_ids: set[str] = set()
    for pick_order in order:
        overall = int(pick_order.get("overall_pick") or 0)
        item = picks_by_overall.get(overall)
        if not item:
            continue
        team_id = pick_order.get("current_owner_team_id") or pick_order.get("owner_team_id")
        pick_id = draft_pick_identity(pick_order)
        if not team_id:
            continue
        pick_order["current_owner_team_id"] = team_id
        pick_order["owner_team_id"] = team_id
        pick_order["team_abbrev"] = team_id_to_abbrev(team_id)
        selection = item.setdefault("selection", {})
        pick = item.setdefault("pick", {})
        selection["team_id"] = team_id
        if pick_id:
            if pick_id in seen_pick_ids:
                pick_id = selection.get("pick_id") or pick.get("id") or pick_id
                pick_order["id"] = pick_id
                pick_order["pick_id"] = pick_id
            else:
                seen_pick_ids.add(pick_id)
            selection["pick_id"] = pick_id
            pick["id"] = pick_id
            pick["pick_id"] = pick_id
            pick_order["id"] = pick_id
            pick_order["pick_id"] = pick_id
        if pick_order.get("original_team_id"):
            selection["original_team_id"] = pick_order.get("original_team_id")
            pick["original_team_id"] = pick_order.get("original_team_id")
        pick["current_owner_team_id"] = team_id
        pick["owner_team_id"] = team_id
        for key in ("season", "round", "overall_pick", "lottery_slot", "pre_lottery_rank"):
            if pick_order.get(key) is not None:
                pick[key] = pick_order.get(key)
        item["team"] = teams.get(team_id, {"id": team_id, "abbrev": str(team_id).replace("team_", "").upper()})
    draft["pending_draft_selections"] = sorted(pending, key=lambda item: int((item.get("selection") or {}).get("overall_pick") or 999))
    saved_order = ((save.get("draft_orders") or {}).get(str(year)) or {})
    draft["draft_order"] = [deepcopy(row) for row in sorted(order, key=lambda row: int(row.get("overall_pick") or 999))]
    if saved_order.get("lottery"):
        draft["lottery"] = deepcopy(saved_order.get("lottery"))
    return draft


def sync_live_draft_state_to_saved_order(canonical: dict[str, Any], save: dict[str, Any], year: str) -> bool:
    state = save.get("draft_state") or {}
    if str(state.get("year") or "") != str(year):
        return False
    draft = state.get("draft") or {}
    pending = draft.get("pending_draft_selections") or []
    order = ((save.get("draft_orders") or {}).get(str(year)) or {}).get("draft_order") or []
    if not pending or not order:
        return False
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    order_by_overall = {int(row.get("overall_pick") or 0): row for row in order if row.get("overall_pick")}
    seen_order_pick_ids: set[str] = set()
    current_index = int(state.get("current_index") or 0)
    changed = False
    for idx, item in enumerate(pending):
        if idx < current_index:
            continue
        selection = item.setdefault("selection", {})
        overall = int(selection.get("overall_pick") or idx + 1)
        row = order_by_overall.get(overall)
        if not row:
            continue
        pick_id = draft_pick_identity(row)
        owner_id = row.get("current_owner_team_id") or row.get("owner_team_id")
        if not pick_id or not owner_id:
            continue
        pick = item.setdefault("pick", {})
        before = (
            selection.get("pick_id"),
            selection.get("team_id"),
            pick.get("id"),
            pick.get("current_owner_team_id"),
        )
        if pick_id in seen_order_pick_ids:
            pick_id = selection.get("pick_id") or pick.get("id") or pick_id
            row["id"] = pick_id
            row["pick_id"] = pick_id
        else:
            seen_order_pick_ids.add(pick_id)
        selection["pick_id"] = pick_id
        selection["team_id"] = owner_id
        selection["original_team_id"] = row.get("original_team_id")
        pick["id"] = pick_id
        pick["pick_id"] = pick_id
        pick["original_team_id"] = row.get("original_team_id")
        pick["current_owner_team_id"] = owner_id
        pick["owner_team_id"] = owner_id
        for key in ("season", "round", "overall_pick", "lottery_slot", "pre_lottery_rank"):
            if row.get(key) is not None:
                pick[key] = row.get(key)
        item["team"] = teams.get(owner_id, {"id": owner_id, "abbrev": team_id_to_abbrev(owner_id)})
        after = (
            selection.get("pick_id"),
            selection.get("team_id"),
            pick.get("id"),
            pick.get("current_owner_team_id"),
        )
        changed = changed or before != after
    return changed


def print_draft_clock(canonical: dict[str, Any], state: dict[str, Any], current: dict[str, Any] | None, user_team: str | None = None) -> None:
    pending = state.get("draft", {}).get("pending_draft_selections", [])
    index = int(state.get("current_index") or 0)
    print(f"Pick {min(index + 1, len(pending))}/{len(pending)}")
    if user_team:
        user_team_id = resolve_team(canonical, user_team)["id"]
        user_picks = [
            int((item.get("selection") or {}).get("overall_pick") or 0)
            for item in pending[index:]
            if (item.get("selection") or {}).get("team_id") == user_team_id
        ]
        pick_text = ", ".join(f"#{pick}" for pick in sorted(pick for pick in user_picks if pick)) or "none remaining"
        print(f"Your picks: {pick_text}")
        next_user = next(
            (
                item
                for item in pending[index:]
                if (item.get("selection") or {}).get("team_id") == user_team_id
            ),
            None,
        )
        if next_user:
            print(f"Next {user_team} pick: #{(next_user.get('selection') or {}).get('overall_pick')}")
        else:
            print(f"Next {user_team} pick: none remaining")
    if not current:
        print("Draft complete.")
        return
    selection = current.get("selection") or {}
    prospect = current.get("prospect") or {}
    pick = current.get("pick") or {}
    print(
        f"On the clock: #{selection.get('overall_pick')} "
        f"{team_abbrev_for_selection(canonical, current)}"
    )
    if prospect:
        print(f"Board context: {len([item for item in pending if (item.get('prospect') or {}).get('id')])} prospects tracked. Use the draft board to scout options.")


def choose_user_draft_pick(canonical: dict[str, Any], save_path: Path, state: dict[str, Any], current: dict[str, Any]) -> dict[str, Any] | None:
    pending = state.get("draft", {}).get("pending_draft_selections", [])
    index = int(state.get("current_index") or 0)
    taken = {
        (item.get("selection") or {}).get("prospect_id")
        for item in pending[:index]
    }
    board = [item for item in pending[index:index + 12] if (item.get("prospect") or {}).get("id") not in taken]
    print_title("Choose Your Prospect")
    team_id = (current.get("selection") or {}).get("team_id")
    for idx, item in enumerate(board, start=1):
        print_prospect_line(item.get("prospect") or {}, prefix=f"{idx:>2}", team_id=team_id, canonical=canonical, save=load_save(save_path))
    print(" 0. Back")
    choice = pick_number("Prospect", 0, len(board), default=0)
    if choice == 0:
        return None
    chosen = board[choice - 1]
    if chosen is current:
        return current
    old_prospect = current.get("prospect")
    old_prospect_id = (current.get("selection") or {}).get("prospect_id")
    current["prospect"] = chosen.get("prospect")
    current["selection"]["prospect_id"] = chosen.get("selection", {}).get("prospect_id")
    current["selection"]["id"] = stable_id("draft_selection", current["selection"].get("pick_id"), current["selection"].get("prospect_id"), "user")
    current["id"] = current["selection"]["id"]
    chosen["prospect"] = old_prospect
    if chosen.get("selection") and old_prospect_id:
        chosen["selection"]["prospect_id"] = old_prospect_id
    save = load_save(save_path)
    state_save = save.setdefault("draft_state", {})
    pending_save = state_save.get("draft", {}).get("pending_draft_selections", [])
    if index < len(pending_save):
        pending_save[index] = current
    chosen_index = pending.index(chosen) if chosen in pending else None
    if chosen_index is not None and chosen_index < len(pending_save):
        pending_save[chosen_index] = chosen
    write_save(save_path, save)
    return current


def apply_current_draft_selection(
    save_path: Path,
    current: dict[str, Any],
    canonical: dict[str, Any] | None = None,
    user_team: str | None = None,
    seed: int = 1,
) -> dict[str, Any]:
    if canonical is not None and user_team:
        maybe_run_ai_draft_trades_before_pick(canonical, save_path, user_team, seed)
        save_after_trade = load_save(save_path)
        refreshed = current_draft_selection(save_after_trade.get("draft_state") or {})
        if refreshed:
            current = refreshed
    save = load_save(save_path)
    selection_id = current.get("id") or current.get("selection", {}).get("id")
    save.setdefault("pending_draft_selections", [])
    if selection_id not in {item.get("id") or item.get("selection", {}).get("id") for item in save["pending_draft_selections"]}:
        save["pending_draft_selections"].append(current)
    write_save(save_path, save)
    result = apply_draft_selection_to_save(save_path, selection_id, date=save.get("state", {}).get("current_date"), sign_rookie=True)
    save = load_save(save_path)
    state = save.setdefault("draft_state", {})
    pick_id = (current.get("selection") or {}).get("pick_id") or (current.get("pick") or {}).get("id")
    if pick_id:
        save.setdefault("draft_pick_overrides", {})[pick_id] = "used_draft_pick"
    state["current_index"] = int(state.get("current_index") or 0) + 1
    state.setdefault("applied_selection_ids", []).append(selection_id)
    if current_draft_selection(state) is None:
        state["status"] = "completed"
    write_save(save_path, save)
    return result


def sim_to_next_user_pick(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int = 1) -> dict[str, Any]:
    team = resolve_team(canonical, user_team)
    applied = 0
    current_payload = None
    while True:
        save = load_save(save_path)
        state = save.get("draft_state") or {}
        current = current_draft_selection(state)
        if not current:
            current_payload = None
            break
        if (current.get("selection") or {}).get("team_id") == team["id"]:
            current_payload = current
            break
        apply_current_draft_selection(save_path, current, canonical=canonical, user_team=user_team, seed=seed)
        applied += 1
    return {"applied_count": applied, "current_selection": current_payload, "draft_trade_news": drain_draft_trade_news(save_path)}


def sim_entire_draft(save_path: Path, canonical: dict[str, Any] | None = None, user_team: str | None = None, seed: int = 1) -> dict[str, Any]:
    applied = 0
    while True:
        save = load_save(save_path)
        state = save.get("draft_state") or {}
        current = current_draft_selection(state)
        if not current:
            state["status"] = "completed"
            write_save(save_path, save)
            break
        apply_current_draft_selection(save_path, current, canonical=canonical, user_team=user_team, seed=seed)
        applied += 1
    return {"applied_count": applied, "draft_trade_news": drain_draft_trade_news(save_path)}


def drain_draft_trade_news(save_path: Path) -> list[dict[str, Any]]:
    save = load_save(save_path)
    state = save.setdefault("draft_state", {})
    news = list(state.get("ai_draft_trade_news_queue") or [])
    if news:
        state["ai_draft_trade_news_queue"] = []
        write_save(save_path, save)
    return news


def print_draft_breaking_news(news: list[dict[str, Any]]) -> None:
    if not news:
        return
    print_title("Breaking News")
    print("Draft-night trade activity")
    for item in news:
        pick = item.get("overall_pick")
        prefix = f"Pick #{pick}: " if pick else ""
        print(f"  {prefix}{item.get('headline')}")
    print_rule()


def print_draft_apply_result(result: dict[str, Any]) -> None:
    rookie = result.get("incoming_rookie") or {}
    print_title("Draft Selection")
    print(f"Status: {result.get('status')}")
    if rookie:
        print(f"{rookie.get('name')} -> {rookie.get('team_abbrev') or rookie.get('team_id')} | {rookie.get('position')}")


def print_draft_board(canonical: dict[str, Any], save_path: Path, user_team: str, limit: int = 60) -> None:
    while True:
        save = load_save(save_path)
        state = save.get("draft_state") or {}
        pending = state.get("draft", {}).get("pending_draft_selections", [])
        current_index = int(state.get("current_index") or 0)
        team_id = resolve_team(canonical, user_team)["id"]
        clear_screen()
        print_title(f"{user_team} Scouting Board")
        print(" #  Status   Prospect                 Pos Age Ht     Scout  Type                 Now/Pot  Selected")
        rows = pending[:limit]
        for idx, item in enumerate(rows, start=1):
            prospect = item.get("prospect") or {}
            picked = idx - 1 < current_index
            status = "PICKED" if picked else "AVAIL"
            selected_by = team_abbrev_for_selection(canonical, item) if picked else ""
            scout = prospect_scout_display(canonical, prospect, team_id, save)
            line = (
                f"{idx:>2}. {status:<7} {prospect.get('name', ''):<24} {compact_position(prospect.get('position')):<3} "
                f"{prospect_age_text(prospect):>3} {prospect_height(prospect):<6} {scout['scouted_pct']:>5.0f}% "
                f"{clean_label(str(prospect.get('archetype') or 'prospect')):<20} "
                f"{scout['now']:>4.0f}/{scout['potential']:<4.0f} {selected_by}"
            )
            print(style(line, "danger") if picked else line)
        print_rule()
        print("Enter a row number to inspect any prospect, or 0 to go back.")
        choice = pick_number("Prospect row", 0, len(rows), default=0)
        if choice == 0:
            clear_screen()
            return
        print_prospect_inspection(canonical, save, rows[choice - 1].get("prospect") or {}, team_id)
        wait()


def inspect_undrafted_prospect_prompt(canonical: dict[str, Any], save_path: Path, user_team: str) -> None:
    save = load_save(save_path)
    state = save.get("draft_state") or {}
    pending = state.get("draft", {}).get("pending_draft_selections", [])
    current_index = int(state.get("current_index") or 0)
    team_id = resolve_team(canonical, user_team)["id"]
    rows = [item for item in pending[current_index:] if (item.get("prospect") or {}).get("id")]
    if not rows:
        return
    print_rule()
    print("Inspect an undrafted prospect?")
    for idx, item in enumerate(rows[:30], start=1):
        prospect = item.get("prospect") or {}
        scout = prospect_scout_display(canonical, prospect, team_id, save)
        print(
            f"{idx:>2}. {prospect.get('name', ''):<24} {compact_position(prospect.get('position')):<3} "
            f"age {prospect_age_text(prospect)} | {prospect_height(prospect):<6} | {scout['now']:.0f}/{scout['potential']:.0f} | "
            f"{scout['scouted_pct']:.0f}%"
        )
    print(" 0. Skip")
    choice = pick_number("Prospect row", 0, min(30, len(rows)), default=0)
    if choice == 0:
        return
    prospect = rows[choice - 1].get("prospect") or {}
    print_prospect_inspection(canonical, save, prospect, team_id)


def print_prospect_inspection(canonical: dict[str, Any], save: dict[str, Any], prospect: dict[str, Any], team_id: str) -> None:
    prospect_id = prospect.get("id") or prospect.get("prospect_id")
    report = scouting_report_for(canonical, prospect_id, team_id)
    scout = prospect_scout_display(canonical, prospect, team_id, save)
    print_title(f"Prospect Report | {prospect.get('name')}")
    print(
        f"{compact_position(prospect.get('position')):<3} | age {prospect_age_text(prospect)} | {prospect_height(prospect)} | "
        f"{scout['scouted_pct']:.0f}% scouted"
    )
    print(f"Archetype: {clean_label(str(prospect.get('archetype') or 'prospect'))}")
    print(f"Now/Potential: {scout['now']:.0f}/{scout['potential']:.0f}")
    traits = report.get("trait_estimates") or {}
    print("Scout read: bars show your staff's current best estimate.")
    interesting = ["current_ability", "potential", "floor", "ceiling", "shooting", "shot_creation", "passing", "defense", "rim_protection", "athleticism", "feel", "volatility"]
    printed = 0
    for key in interesting:
        if key == "current_ability":
            value = {"mid": scout["now"]}
        elif key == "potential":
            value = {"mid": scout["potential"]}
        elif key == "floor":
            value = {"mid": scout["floor"]}
        elif key == "ceiling":
            value = {"mid": scout["ceiling"]}
        else:
            value = traits.get(key)
        label = "downside floor" if key == "floor" else key
        if isinstance(value, dict) and value.get("mid") is not None:
            print(f"  {clean_label(label):<16} {morale_bar(float(value['mid']), width=12)} {float(value['mid']):>5.1f}")
            printed += 1
        elif prospect.get(key) is not None:
            print(f"  {clean_label(label):<16} {morale_bar(float(prospect[key]), width=12)} {float(prospect[key]):>5.1f}")
            printed += 1
    if printed == 0:
        for key in ["current_ability", "potential", "floor", "ceiling", "volatility"]:
            if prospect.get(key) is not None:
                label = "downside floor" if key == "floor" else key
                print(f"  {clean_label(label):<16} {morale_bar(float(prospect[key]), width=12)} {float(prospect[key]):>5.1f}")


def prospect_scout_display(canonical: dict[str, Any], prospect: dict[str, Any], team_id: str | None, save: dict[str, Any] | None = None) -> dict[str, float]:
    report = scouting_report_for(canonical, prospect.get("id") or prospect.get("prospect_id"), team_id)
    current = (report.get("estimated_current") or {}).get("mid")
    potential = (report.get("estimated_potential") or {}).get("mid")
    now = float(current if current is not None else prospect.get("current_ability") or 0.0)
    pot = float(potential if potential is not None else prospect.get("potential") or 0.0)
    floor = float(prospect.get("floor") if prospect.get("floor") is not None else max(20.0, now - 8.0))
    ceiling = float(prospect.get("ceiling") if prospect.get("ceiling") is not None else max(pot, pot + 7.0))
    pct = prospect_scouted_pct(canonical, prospect.get("id") or prospect.get("prospect_id"), team_id, save)
    return {"now": now, "potential": pot, "floor": floor, "ceiling": ceiling, "scouted_pct": pct}


def prospect_now_pot_for_display(canonical: dict[str, Any], prospect: dict[str, Any], team_id: str) -> tuple[float, float]:
    scout = prospect_scout_display(canonical, prospect, team_id)
    return scout["now"], scout["potential"]


def print_user_draft_recap(canonical: dict[str, Any], save_path: Path, user_team: str, year: str) -> None:
    save = load_save(save_path)
    team = resolve_team(canonical_with_save(canonical, save), user_team)
    rookies = [
        rookie for rookie in save.get("incoming_rookies", [])
        if str(rookie.get("draft_year")) == str(year) and rookie.get("team_id") == team["id"]
    ]
    print_title(f"{user_team} Draft Recap")
    if not rookies:
        print("No user-team selections were made in this draft.")
        return
    for rookie in sorted(rookies, key=lambda item: int(item.get("overall_pick") or 999)):
        print(
            f"#{rookie.get('overall_pick'):<2} {rookie.get('name'):<24} {rookie.get('position') or '-':<3} "
            f"{prospect_height(rookie):<6} now {float(rookie.get('current_ability') or 0):.0f} "
            f"pot {float(rookie.get('potential') or 0):.0f}"
        )


def print_full_draft_recap(canonical: dict[str, Any], save_path: Path, year: str) -> None:
    save = load_save(save_path)
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    selections = sorted(
        [item for item in save.get("incoming_rookies", []) if str(item.get("draft_year")) == str(year)],
        key=lambda item: int(item.get("overall_pick") or 999),
    )
    print_title(f"{year} Draft Recap")
    if not selections:
        print("No completed selections have been signed into this save yet.")
        return
    for rookie in selections[:60]:
        team = teams.get(rookie.get("team_id"), {"abbrev": rookie.get("team_abbrev")})
        print(
            f"#{int(rookie.get('overall_pick') or 0):>2} {team.get('abbrev') or 'TBD':<3} "
            f"{rookie.get('name', ''):<24} {rookie.get('position') or '-':<3} "
            f"{prospect_height(rookie):<6} now {float(rookie.get('current_ability') or 0):.0f} "
            f"pot {float(rookie.get('potential') or 0):.0f}"
        )


def print_live_draft_summary(canonical: dict[str, Any], save_path: Path, user_team: str, year: str, seed: int) -> None:
    while True:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        state = save.get("draft_state") or {}
        pending = (state.get("draft") or {}).get("pending_draft_selections") or []
        current_index = int(state.get("current_index") or 0)
        incoming_by_pick = {
            int(rookie.get("overall_pick") or 0): rookie
            for rookie in save.get("incoming_rookies", [])
            if str(rookie.get("draft_year")) == str(year)
        }
        clear_screen()
        print_title(f"{year} Draft Summary")
        print(" #  Team  Prospect                 Pos Age Ht     Now/Pot")
        rows = pending[:60]
        for idx, item in enumerate(rows, start=1):
            selection = item.get("selection") or {}
            prospect = item.get("prospect") or {}
            overall = int(selection.get("overall_pick") or idx)
            picked = idx - 1 < current_index
            team = team_abbrev_for_selection(canonical, item)
            if not picked:
                print(f"{overall:>2}. {team:<4} {'TBD':<24}")
                continue
            rookie = incoming_by_pick.get(overall) or prospect
            now = float(rookie.get("current_ability") or prospect.get("current_ability") or 0)
            pot = float(rookie.get("potential") or prospect.get("potential") or 0)
            print(
                f"{overall:>2}. {team:<4} {str(rookie.get('name') or prospect.get('name') or ''):<24} "
                f"{compact_position(rookie.get('position') or prospect.get('position')):<3} "
                f"{prospect_age_text(rookie or prospect):>3} {prospect_height(rookie or prospect):<6} {now:>4.0f}/{pot:<4.0f}"
            )
        print_rule()
        print("Enter a pick number to inspect/trade a drafted player, or 0 to go back.")
        choice = pick_number("Pick", 0, min(60, len(rows)), default=0)
        if choice == 0:
            clear_screen()
            return
        item = rows[choice - 1]
        if choice - 1 >= current_index:
            pause("That pick has not been made yet.")
            continue
        selection = item.get("selection") or {}
        prospect = item.get("prospect") or {}
        team_id = selection.get("team_id")
        rookie = incoming_by_pick.get(int(selection.get("overall_pick") or choice), {})
        while True:
            clear_screen()
            print_prospect_inspection(canonical, save, {**prospect, **rookie}, resolve_team(canonical, user_team)["id"])
            print_rule()
            print("1. Trade for this player")
            print("0. Back")
            action = pick_number("Action", 0, 1, default=0)
            if action == 0:
                break
            player_name = rookie.get("name") or prospect.get("name")
            if not player_name or not team_id:
                pause("This drafted player is not available as a save-state trade asset yet.")
                continue
            active = canonical_with_save(canonical, ensure_league_save_defaults(load_save(save_path), canonical))
            target_team = team_id_to_abbrev(team_id)
            report = trade_finder_report_for_selection(active, load_save(save_path), user_team, target_team, [{"kind": "player", "value": player_name}], seed)
            clear_screen()
            print_find_trade_report(report)
            if report.get("candidates"):
                trade_finder_followup(active, report, save_path)
            else:
                pause("No legal offers came back for that drafted player.")
            break


def print_lottery(order: dict[str, Any]) -> None:
    print_title("Draft Lottery / Order")
    lottery = order.get("lottery") or {}
    if lottery:
        print(f"Lottery seed: {lottery.get('seed')} | method: {lottery.get('method')}")
        odds = lottery.get("odds_by_team") or {}
        if odds:
            odds_context = lottery.get("odds_context_by_team") or {}
            print("\nOdds")
            for team_id, pct in sorted(odds.items(), key=lambda item: -float(item[1]))[:14]:
                context = f" {odds_context.get(team_id)}" if odds_context.get(team_id) else ""
                print(f"{str(team_id).replace('team_', '').upper():<4} {float(pct) * 100:>5.1f}%{context}")
            print("\nReveal")
    for idx, pick in enumerate((order.get("draft_order") or [])[:14], start=1):
        owner = pick.get("team_abbrev") or team_id_to_abbrev(pick.get("current_owner_team_id"))
        print(f"{idx:>2}. {owner}  #{pick.get('overall_pick')}")


def team_abbrev_for_selection(canonical: dict[str, Any], item: dict[str, Any]) -> str:
    team_id = (item.get("selection") or {}).get("team_id") or (item.get("pick") or {}).get("current_owner_team_id")
    team = next((team for team in canonical.get("teams", []) if team.get("id") == team_id), {})
    return team.get("abbrev") or str(team_id or "TBD")


def print_prospect_line(prospect: dict[str, Any], prefix: str = "Prospect", team_id: str | None = None, canonical: dict[str, Any] | None = None, save: dict[str, Any] | None = None) -> None:
    if not prospect:
        print(f"{prefix}: unavailable")
        return
    height = prospect_height(prospect)
    traits = prospect_trait_summary(prospect)
    comp = prospect.get("comp") or prospect.get("archetype") or prospect.get("role_archetype") or "scouted prospect"
    confidence = ""
    if team_id and canonical is not None:
        scout = prospect_scout_display(canonical, prospect, team_id, save)
        confidence = f" | {scout['scouted_pct']:.0f}% scouted"
        traits = prospect_trait_summary_from_scout(scout, prospect)
    print(f"{prefix}: {prospect.get('name')} ({prospect.get('position') or '-'}) age {prospect_age_text(prospect)} {height} | {clean_label(comp)}{confidence}")
    if traits:
        print(f"  Traits: {traits}")
    if prospect.get("scouting_notes"):
        print(f"  Note: {str(prospect.get('scouting_notes'))[:110]}")


def prospect_scouted_pct(canonical: dict[str, Any], prospect_id: str | None, team_id: str | None, save: dict[str, Any] | None = None) -> float:
    if not prospect_id or not team_id:
        return 50.0
    if save:
        return save_focused_scouted_pct(canonical, save, prospect_id, team_id)
    report = next(
        (
            item for item in canonical.get("scouting_reports", [])
            if item.get("team_id") == team_id and item.get("prospect_id") == prospect_id
        ),
        None,
    )
    if report:
        base = float(report.get("confidence") or 0.5) * 100
        wobble = ((sum(ord(char) for char in f"{team_id}:{prospect_id}") % 19) - 9) * 0.9
        return max(18.0, min(100.0, base + wobble))
    slot = next((slot for slot in canonical.get("gameplay_staff_slots", []) if slot.get("team_id") == team_id and slot.get("slot") == "scouting_lead"), {})
    traits = slot.get("skill_traits") or {}
    score = (
        float(traits.get("talent_eval") or 60) * 0.58
        + float(traits.get("risk_modeling") or 60) * 0.27
        + float(traits.get("international_coverage") or 60) * 0.15
    )
    return max(38.0, min(96.0, 48.0 + (score - 50.0) * 0.95))


def save_focused_scouted_pct(canonical: dict[str, Any], save: dict[str, Any], prospect_id: str, team_id: str) -> float:
    pending = ((save.get("draft_state") or {}).get("draft") or {}).get("pending_draft_selections") or []
    prospect_rank = next(
        (
            idx
            for idx, item in enumerate(pending, start=1)
            if (item.get("prospect") or {}).get("id") == prospect_id
            or (item.get("selection") or {}).get("prospect_id") == prospect_id
        ),
        None,
    )
    if prospect_rank is None:
        prospect = next((item for item in canonical.get("draft_prospects", []) if item.get("id") == prospect_id), {})
        prospect_rank = int(prospect.get("rank") or prospect.get("consensus_rank") or 45)
    staff = next((slot for slot in canonical.get("gameplay_staff_slots", []) if slot.get("team_id") == team_id and slot.get("slot") == "scouting_lead"), {})
    traits = staff.get("skill_traits") or {}
    staff_score = (
        float(traits.get("talent_eval") or 60) * 0.58
        + float(traits.get("risk_modeling") or 60) * 0.27
        + float(traits.get("international_coverage") or 60) * 0.15
    )
    public_base = 76.0 if prospect_rank <= 5 else 66.0 if prospect_rank <= 14 else 52.0 if prospect_rank <= 30 else 38.0
    owned_picks = [
        int((item.get("selection") or {}).get("overall_pick") or 99)
        for item in pending
        if (item.get("selection") or {}).get("team_id") == team_id
    ]
    if owned_picks:
        distance = min(abs(prospect_rank - pick) for pick in owned_picks)
    else:
        distance = 16
    focus = 0.0
    staff_multiplier = max(0.65, min(1.75, staff_score / 62.0))
    if distance <= 3:
        focus = 27.0 * staff_multiplier
    elif distance <= 8:
        focus = 19.0 * staff_multiplier
    elif distance <= 15:
        focus = 9.0 * staff_multiplier
    elif prospect_rank <= 8:
        focus = 9.0
    staff_bonus = (staff_score - 55.0) * 0.72
    wobble = ((sum(ord(char) for char in f"{team_id}:{prospect_id}:{save.get('meta', {}).get('seed')}") % 17) - 8) * 0.8
    full_report = (distance <= 2 and staff_score >= 68.0) or (prospect_rank <= 3 and staff_score >= 62.0)
    value = public_base + focus + staff_bonus + wobble
    if full_report and value >= 92.0:
        return 100.0
    return round(max(18.0, min(100.0, value)), 1)


def scouting_report_for(canonical: dict[str, Any], prospect_id: str | None, team_id: str | None) -> dict[str, Any]:
    if not prospect_id or not team_id:
        return {}
    return next(
        (
            item for item in canonical.get("scouting_reports", [])
            if item.get("team_id") == team_id and item.get("prospect_id") == prospect_id
        ),
        {},
    )


def prospect_height(prospect: dict[str, Any]) -> str:
    inches = prospect.get("height_inches")
    if inches:
        value = int(round(float(inches)))
        return f"{value // 12}'{value % 12}\""
    return str(prospect.get("height") or "")


def prospect_age_text(prospect: dict[str, Any]) -> str:
    value = prospect.get("age") or prospect.get("draft_age") or prospect.get("age_at_draft")
    if value is None:
        return "--"
    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return "--"


def prospect_trait_summary(prospect: dict[str, Any]) -> str:
    pairs = []
    for key, label in [("current_ability", "now"), ("potential", "pot"), ("floor", "floor"), ("ceiling", "ceil"), ("shooting", "shoot"), ("defense", "def")]:
        if prospect.get(key) is not None:
            pairs.append(f"{label} {float(prospect[key]):.0f}")
    return ", ".join(pairs[:5])


def prospect_trait_summary_from_scout(scout: dict[str, float], prospect: dict[str, Any]) -> str:
    pairs = [
        f"now {float(scout.get('now') or 0):.0f}",
        f"pot {float(scout.get('potential') or 0):.0f}",
        f"floor {float(scout.get('floor') or 0):.0f}",
        f"ceil {float(scout.get('ceiling') or 0):.0f}",
    ]
    for key, label in [("shooting", "shoot"), ("defense", "def")]:
        if prospect.get(key) is not None:
            pairs.append(f"{label} {float(prospect[key]):.0f}")
    return ", ".join(pairs[:5])


def print_draft_trade_report(report: dict[str, Any]) -> None:
    print_title("Draft Trade Ideas")
    candidates = report.get("candidates", [])[:6]
    if not candidates:
        print("No clean draft-night trade ideas for this pick.")
        return
    for idx, item in enumerate(candidates, start=1):
        proposal = item.get("proposal") or {}
        incoming = ", ".join(clean_asset_label(asset) for asset in proposal.get("to_assets", [])) or "none"
        outgoing = ", ".join(clean_asset_label(asset) for asset in proposal.get("from_assets", [])) or "none"
        print(f"{idx:>2}. Trade pick for {incoming} | score {item.get('score')}")
        print(f"    Outgoing: {outgoing}")
        print(f"    Why: {', '.join(item.get('reasons', [])[:4])}")
        print_value_bars(item.get("evaluation") or {})


def clean_asset_label(asset: dict[str, Any]) -> str:
    if asset.get("kind") == "player":
        return asset.get("name") or asset.get("value") or asset.get("id") or "player"
    if asset.get("kind") == "pick":
        pick_id = str(asset.get("id") or asset.get("value") or "pick")
        parts = pick_id.replace("draft_pick_", "").split("_")
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]} R{parts[1]} {parts[2].upper()}"
        return clean_label(pick_id)
    if asset.get("kind") == "pick_swap":
        return asset.get("label") or clean_label(str(asset.get("id") or asset.get("value") or "pick swap"))
    return clean_label(str(asset))


def clean_pick_label_for_user(canonical: dict[str, Any], pick: dict[str, Any], save: dict[str, Any] | None = None) -> str:
    teams = {team["id"]: team["abbrev"] for team in canonical.get("teams", [])}
    if save:
        order_pick = saved_order_pick_for_pick(save, pick)
        if order_pick:
            owner = teams.get(order_pick.get("current_owner_team_id")) or "TBD"
            original = teams.get(order_pick.get("original_team_id")) or "TBD"
            overall = f"#{order_pick.get('overall_pick')}"
            owned_by = f"owned by {owner}" if owner and owner != original else "own pick"
            note = pick_obligation_context_note(canonical, pick)
            suffix = f"; {note}" if note else ""
            return f"{overall} {owner} | R{order_pick.get('round')} {original} ({owned_by}){suffix}"
    label = pick_display_label(canonical, pick)
    if pick.get("overall_pick"):
        return f"{label} #{pick.get('overall_pick')}"
    return label


def pick_context_note(pick: dict[str, Any]) -> str:
    compact = clean_pick_protection_summary(pick)
    if not compact:
        return ""
    return f"; {compact}"


def saved_order_pick_for_pick(save: dict[str, Any], pick: dict[str, Any]) -> dict[str, Any] | None:
    season = str(pick.get("season") or "")
    order = ((save.get("draft_orders") or {}).get(season) or {}).get("draft_order") or []
    return next((item for item in order if item.get("id") == pick.get("id")), None)


def pick_slot_is_determined_for_trade(save: dict[str, Any], pick: dict[str, Any]) -> bool:
    if pick.get("overall_pick") or pick.get("lottery_slot"):
        return True
    order_pick = saved_order_pick_for_pick(save, pick)
    return bool(order_pick and order_pick.get("overall_pick"))


def used_draft_pick_ids(save: dict[str, Any]) -> set[str]:
    state = save.get("draft_state") or {}
    used: set[str] = set(state.get("used_pick_ids") or [])
    used.update(pick_id for pick_id, owner in (save.get("draft_pick_overrides") or {}).items() if owner == "used_draft_pick")
    applied_ids = set(state.get("applied_selection_ids") or [])
    pending = (state.get("draft") or {}).get("pending_draft_selections") or []
    index = int(state.get("current_index") or 0)
    for item in pending[:index]:
        pick_id = (item.get("pick") or {}).get("id") or (item.get("selection") or {}).get("pick_id")
        if pick_id:
            used.add(pick_id)
    for item in pending:
        selection = item.get("selection") or {}
        if selection.get("id") in applied_ids:
            pick_id = (item.get("pick") or {}).get("id") or selection.get("pick_id")
            if pick_id:
                used.add(pick_id)
    return used


def selected_prospect_ids_from_save(save: dict[str, Any]) -> set[str]:
    state = save.get("draft_state") or {}
    selected: set[str] = set()
    index = int(state.get("current_index") or 0)
    pending = (state.get("draft") or {}).get("pending_draft_selections") or []
    for item in pending[:index]:
        prospect_id = (item.get("prospect") or {}).get("id") or (item.get("selection") or {}).get("prospect_id")
        if prospect_id:
            selected.add(prospect_id)
    for collection in ("incoming_rookies", "draft_rights"):
        for item in save.get(collection, []):
            if item.get("prospect_id"):
                selected.add(item["prospect_id"])
    return selected


def print_draft_preview(draft: dict[str, Any]) -> None:
    print(f"Selections generated: {draft.get('selection_count')}")
    prospects = {item.get("id"): item for item in draft.get("draft_prospects", [])}
    pending = draft.get("pending_draft_selections", [])
    for idx, item in enumerate(pending[:20], start=1):
        selection = item.get("selection", {})
        prospect = item.get("prospect") or prospects.get(selection.get("prospect_id"), {})
        pick = item.get("pick", {})
        print(f"{idx:>2}. #{selection.get('overall_pick')} {pick.get('current_owner_team_id') or selection.get('team_id')} selects {prospect.get('name')} ({prospect.get('position')})")


def apply_pending_draft_selection(save_path: Path, sign_rookie: bool, all_items: bool) -> None:
    save = load_save(save_path)
    pending = list(save.get("pending_draft_selections", []))
    if not pending:
        print("No pending draft selections. Generate/watch the draft first.")
        wait()
        return
    selected = pending if all_items else [pending[pick_number("Selection", 1, len(pending), default=1) - 1]]
    applied = []
    for item in selected:
        result = apply_draft_selection_to_save(save_path, item["id"], date=load_save(save_path).get("state", {}).get("current_date"), sign_rookie=sign_rookie)
        applied.append(result)
    print(f"Applied {sum(1 for item in applied if item.get('status') == 'applied')} draft selection(s).")
    wait()


def user_pick_recommendations(canonical: dict[str, Any], save_path: Path, user_team: str, year: str, seed: int, pause_after: bool = True) -> None:
    save = load_save(save_path)
    state_current = current_draft_selection(save.get("draft_state") or {})
    pending = [
        item for item in save.get("pending_draft_selections", [])
        if (item.get("selection") or {}).get("team_id") == resolve_team(canonical, user_team)["id"]
    ]
    if state_current and (state_current.get("selection") or {}).get("team_id") == resolve_team(canonical, user_team)["id"]:
        pending = [state_current]
    if not pending:
        print("No current user-team selection. Use 'Sim to next user pick' first.")
        if pause_after:
            wait()
        return
    pick = pending[0].get("pick") or {"id": pending[0].get("selection", {}).get("pick_id")}
    team_id = resolve_team(canonical, user_team)["id"]
    unavailable = selected_prospect_ids_from_save(save)
    print_title(f"{user_team} Pick Recommendations")
    try:
        recs = pick_recommendations(canonical, user_team, pick["id"], limit=6, seed=seed, unavailable_prospect_ids=unavailable)
    except ValueError as exc:
        active = canonical_with_save(canonical, save)
        if print_generated_pick_recommendations_from_state(active, save, team_id, unavailable, limit=6):
            if pause_after:
                wait()
            return
        print(f"Recommendations unavailable for this generated pick yet: {exc}")
        if pause_after:
            wait()
        return
    for idx, rec in enumerate(recs.get("recommendations", []), start=1):
        prospect = hydrate_prospect(canonical, rec["entry"]["prospect"])
        decision = rec["decision"]
        report = scouting_report_for(canonical, prospect.get("id") or prospect.get("prospect_id"), team_id)
        print(f"{idx:>2}. {prospect['name']} ({prospect['position']}) | age {prospect_age_text(prospect)} | grade {rec['entry']['risk_adjusted_grade']} | {prospect_height(prospect)} | {prospect_scouted_pct(canonical, prospect.get('id') or prospect.get('prospect_id'), team_id, save):.0f}% scouted")
        print(f"    Type: {clean_label(str(prospect.get('archetype') or prospect.get('role_archetype') or 'prospect'))}")
        print(f"    Scout: {prospect_scout_line(prospect, report)}")
        print(f"    Fit: {', '.join(clean_label(reason) for reason in decision['reasons'][:3])}")
    if pause_after:
        wait()


def print_generated_pick_recommendations_from_state(canonical: dict[str, Any], save: dict[str, Any], team_id: str, unavailable: set[str], limit: int = 6) -> bool:
    draft = (save.get("draft_state") or {}).get("draft") or {}
    prospects = [
        prospect for prospect in draft.get("draft_prospects", [])
        if prospect.get("id") not in unavailable
    ]
    if not prospects:
        return False
    prospects.sort(
        key=lambda item: (
            float(item.get("current_ability") or 0) * 0.58
            + float(item.get("potential") or 0) * 0.32
            + float(item.get("rookie_contract_value") or 0) * 0.1,
            -int(item.get("rank") or 999),
        ),
        reverse=True,
    )
    for idx, prospect in enumerate(prospects[:limit], start=1):
        current = float(prospect.get("current_ability") or 0)
        potential = float(prospect.get("potential") or 0)
        print(
            f"{idx:>2}. {prospect.get('name'):<24} {compact_position(prospect.get('position')):<3} "
            f"age {prospect_age_text(prospect)} | {prospect_height(prospect)} | now {current:.0f} upside {potential:.0f} | "
            f"{prospect_scouted_pct(canonical, prospect.get('id'), team_id, save):.0f}% scouted"
        )
        print(f"    Type: {clean_label(str(prospect.get('archetype') or 'prospect'))}")
    return True


def hydrate_prospect(canonical: dict[str, Any], prospect: dict[str, Any]) -> dict[str, Any]:
    prospect_id = prospect.get("id") or prospect.get("prospect_id")
    full = next((item for item in canonical.get("draft_prospects", []) if item.get("id") == prospect_id), None)
    return {**(full or {}), **prospect}


def prospect_scout_line(prospect: dict[str, Any], report: dict[str, Any]) -> str:
    traits = report.get("trait_estimates") or {}
    current = (report.get("estimated_current") or {}).get("mid", prospect.get("current_ability"))
    potential = (report.get("estimated_potential") or {}).get("mid", prospect.get("potential"))

    def trait_mid(*names: str) -> float | None:
        for name in names:
            value = traits.get(name)
            if isinstance(value, dict) and value.get("mid") is not None:
                return float(value["mid"])
            if prospect.get(name) is not None:
                return float(prospect[name])
        return None

    parts = [
        f"now {float(current or 0):.0f}",
        f"upside {float(potential or 0):.0f}",
    ]
    for label, value in [
        ("shoot", trait_mid("shooting", "shot_making", "spacing")),
        ("create", trait_mid("shot_creation", "handle", "passing")),
        ("def", trait_mid("defense", "rim_protection", "point_of_attack_defense")),
        ("ath", trait_mid("athleticism", "burst", "vertical")),
        ("IQ", trait_mid("feel", "processing", "basketball_iq")),
    ]:
        if value is not None:
            parts.append(f"{label} {value:.0f}")
    return ", ".join(parts[:7])


def free_agency_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, forced: bool = False) -> str | None:
    while True:
        initialize_free_agency_market(canonical, save_path, user_team, seed)
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        state = save.get("free_agency_state") or {}
        day = int(state.get("day") or 1)
        status = state.get("status") or "active"
        clear_screen()
        if user_re_signing_window_active(canonical, save, user_team):
            result = own_expiring_re_signing_room(canonical, save_path, user_team, seed, forced=forced)
            if result in {"quit", "back"}:
                return result
            continue
        print_title("Free Agency Room")
        print_free_agency_status(canonical, save, user_team)
        print_rule()
        print("1. View players / make offers")
        print("2. Sim one free-agency day")
        print("3. Sim to end of free agency")
        print("4. View active user bids")
        print("5. Team dashboard")
        print("6. Free agency recap")
        print("8. Withdraw an active bid")
        print("9. Trade room / move assets")
        if forced:
            print("0. Save and quit")
        else:
            print("0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            clear_screen()
            return "quit" if forced else "back"
        if choice == "1":
            free_agency_player_market(canonical, save_path, user_team, seed)
        elif choice == "2":
            root = save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd()
            with loading_screen(root, "Advancing free agency...", seed=seed):
                result = advance_free_agency_day(canonical, save_path, user_team, seed)
            clear_screen()
            print_free_agency_day_recap(canonical, save_path, day, result)
            wait()
            if (load_save(save_path).get("free_agency_state") or {}).get("status") == "completed":
                final_free_agency_roster_repair(canonical, save_path, seed)
                finish_free_agency_phase(canonical, save_path)
                return "done"
        elif choice == "3":
            with loading_screen(save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd(), "Simulating free agency...", seed=seed):
                result = simulate_free_agency_to_end(canonical, save_path, user_team, seed)
            print_free_agency_breaking_news(result.get("ai_trade_news") or [])
            pause(
                f"Free agency completed: {result.get('accepted_count', 0)} signing(s), "
                f"{result.get('auto_fill_count', 0)} roster repair signing(s), "
                f"{result.get('ai_trade_count', 0)} AI trade(s)."
            )
            finish_free_agency_phase(canonical, save_path)
            return "done" if forced else None
        elif choice == "4":
            print_user_active_bids(canonical, save_path, user_team)
            wait()
        elif choice == "5":
            root = save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd()
            print_dashboard(root, canonical, save_path, user_team, user_team=user_team, seed=seed)
        elif choice == "6":
            print_free_agency_recap(canonical, save_path)
            wait()
        elif choice == "8":
            withdraw_user_free_agent_bid(canonical, save_path, user_team)
        elif choice == "9":
            active = canonical_with_save(canonical, ensure_league_save_defaults(load_save(save_path), canonical))
            trade_room(active, save_path, user_team, seed)


def initialize_free_agency_market(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    prepare_free_agency_pool(canonical, save)
    season = save.get("meta", {}).get("season") or "2025-26"
    state = save.get("free_agency_state") or {}
    if state.get("season") != season:
        state = {
            "season": season,
            "day": 1,
            "day_count": 5,
            "status": "active",
            "re_signing_day": 1,
            "re_signing_day_count": 2,
            "re_signing_status": "active",
            "ai_days_processed": [],
            "user_offer_counts": {},
            "player_asks_millions": {},
            "accepted_offer_ids": [],
        }
        save["free_agency_state"] = state
        save["free_agent_offers"] = []
    active = canonical_with_save(canonical, save)
    missing_asks = [
        player_id for player_id in save.get("free_agent_player_ids", [])
        if player_id not in state.setdefault("player_asks_millions", {})
    ]
    report_by_id = {}
    if missing_asks:
        report_by_id = {item.get("player_id") or item.get("id"): item for item in free_agents_report(active).get("candidates", [])}
    for player_id in missing_asks:
        if player_id in state.setdefault("player_asks_millions", {}):
            continue
        player = next((item for item in active.get("players", []) if item.get("id") == player_id), {})
        market = report_by_id.get(player_id) or {}
        state["player_asks_millions"][player_id] = free_agency_initial_ask(player, market)
    write_save(save_path, save)
    if user_re_signing_window_active(canonical, save, user_team):
        return load_save(save_path)
    process_ai_free_agency_offers_for_day(canonical, save_path, user_team, seed)
    return load_save(save_path)


def free_agency_initial_ask(player: dict[str, Any], market: dict[str, Any]) -> float:
    projected = float(market.get("projected_aav_millions") or 0.0)
    minutes = display_minutes_projection(player)
    return round(max(1.8, projected or minutes * 0.48), 1)


def user_re_signing_window_active(canonical: dict[str, Any], save: dict[str, Any], user_team: str) -> bool:
    state = save.get("free_agency_state") or {}
    if state.get("re_signing_status") == "completed":
        return False
    team_id = resolve_team(canonical, user_team)["id"]
    season = save.get("meta", {}).get("season")
    return any(
        right.get("team_id") == team_id
        and right.get("status") == "exclusive_review_window"
        and (not season or right.get("season") == season)
        for right in save.get("re_signing_rights", [])
    )


def own_expiring_re_signing_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, forced: bool = False) -> str | None:
    while True:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = canonical_with_save(canonical, save)
        team = resolve_team(active, user_team)
        state = save.setdefault("free_agency_state", {})
        rights = [
            right for right in save.get("re_signing_rights", [])
            if right.get("team_id") == team["id"]
            and right.get("status") == "exclusive_review_window"
            and right.get("season") == save.get("meta", {}).get("season")
        ]
        if not rights:
            state["re_signing_status"] = "completed"
            write_save(save_path, save)
            return "done"
        players = {player["id"]: player for player in active.get("players", [])}
        day = int(state.get("re_signing_day") or 1)
        day_count = int(state.get("re_signing_day_count") or 2)
        clear_screen()
        print_title("Own Free Agents | Exclusive Re-Signing Window")
        print(f"Day {day}/{day_count}. No outside teams can bid yet. You may go above tax room to retain your own players.")
        print_cap_summary(active, save, team["id"], team_cap_summary(active, save, team["id"], season=contract_start_season_for_signing(save)))
        print_rule()
        print(" #  Player                     Pos Age OVR  MPG   PPG  Ask")
        candidates = [players.get(right["player_id"]) for right in rights if players.get(right["player_id"])]
        candidates.sort(key=lambda player: (display_minutes_projection(player), float(player_attribute_summary(active, player["id"]).get("overall") or 0.0)), reverse=True)
        for idx, player in enumerate(candidates, start=1):
            attrs = player_attribute_summary(active, player["id"])
            stats = active_season_line(save, player["id"], player)
            ask = max(2.0, free_agency_initial_ask(player, {}))
            print(
                f"{idx:>2}. {player.get('name', ''):<26} {compact_position(player.get('position')):<3} {age_text(player, 3)} "
                f"{float(attrs.get('overall') or 0):>3.0f} {display_minutes_projection(player):>4.0f} {stats['ppg']:>5.1f} ${ask:>5.1f}M"
            )
        print_rule()
        print("1. Negotiate with a player")
        print("2. Advance exclusive day")
        print("3. Skip to open free agency")
        print("4. Trade Room")
        print("5. Team dashboard")
        print("0. Save and quit" if forced else "0. Back")
        choice = input("> Pick a number: ").strip()
        if choice == "0":
            return "quit" if forced else "back"
        if choice == "1":
            selected = pick_number("Player", 0, len(candidates), default=0)
            if selected == 0:
                continue
            player = candidates[selected - 1]
            market = next((item for item in free_agents_report(active, team_query=user_team).get("candidates", []) if (item.get("id") or item.get("player_id")) == player["id"]), {})
            ask = max(2.0, free_agency_initial_ask(player, market))
            try:
                aav = float(input(f"Offer AAV in millions [{ask:.1f}]: ").strip() or ask)
            except ValueError:
                aav = ask
            years = pick_number("Years", 1, 5, default=min(3, int(market.get("max_years") or 3)))
            cap_check = signing_cap_check(active, save, user_team, aav, allow_tax_exceed=True)
            if not cap_check.get("ok"):
                pause(cap_check.get("message") or "Offer blocked by hard-cap posture.")
                continue
            negotiation = manual_save_pool_signing(active, save_path, player, user_team, years, aav, seed)
            if negotiation.get("accepted"):
                result = apply_contract_to_save(save_path, negotiation["negotiation"]["id"], date=save.get("state", {}).get("current_date"))
                pause(f"Re-signing result: {result.get('status')}")
            else:
                score = float((negotiation.get("decision") or {}).get("player_score") or 0.0) * 100.0
                print_interest_read(
                    score,
                    {
                        "ask": f"${float((negotiation.get('decision') or {}).get('ask_threshold_millions') or ask):.1f}M",
                        "offer": f"${aav:.1f}M",
                        "years": str(years),
                        "rights": "exclusive window",
                    },
                )
                pause("Player rejected the offer and may test open free agency.")
        elif choice == "2":
            if day >= day_count:
                state["re_signing_status"] = "completed"
            else:
                state["re_signing_day"] = day + 1
            write_save(save_path, save)
            return "done"
        elif choice == "3":
            state["re_signing_status"] = "completed"
            write_save(save_path, save)
            return "done"
        elif choice == "4":
            trade_room(active, save_path, user_team, seed)
        elif choice == "5":
            root = save_path.parent.parent if save_path.parent.name == "saves" else Path.cwd()
            print_dashboard(root, canonical, save_path, user_team, user_team=user_team, seed=seed)


def print_free_agency_status(canonical: dict[str, Any], save: dict[str, Any], user_team: str) -> None:
    state = save.get("free_agency_state") or {}
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, user_team)
    cap_season = contract_start_season_for_signing(save)
    cap = team_cap_summary(active, save, team["id"], season=cap_season)
    day = int(state.get("day") or 1)
    day_count = int(state.get("day_count") or 5)
    limit = free_agency_user_offer_limit(day)
    used = int((state.get("user_offer_counts") or {}).get(str(day), 0))
    remaining = "unlimited" if limit is None else str(max(0, limit - used))
    used_text = f"{used}/{limit}" if limit is not None else f"{used}/unlimited"
    print(f"Day {day}/{day_count} | status {clean_label(state.get('status'))} | user offers remaining today: {remaining} | sent {used_text}")
    print_cap_summary(active, save, team["id"], cap)
    active_offers = [offer for offer in save.get("free_agent_offers", []) if offer.get("status") == "active"]
    user_offers = [offer for offer in active_offers if offer.get("source") == "user"]
    print(f"Market: {len(save.get('free_agent_player_ids', []))} free agent(s), {len(active_offers)} active offer(s), {len(user_offers)} user bid(s)")
    wars = free_agency_bidding_wars(canonical, save, limit=4)
    if wars:
        heading = "Bidding wars" if any(int(row.get("offer_count") or 0) >= 2 for row in wars) else "Top active offers"
        print(style(heading, "accent"))
        for row in wars:
            print(f"  {row['player_name']:<24} {row['offer_count']} offers | best {row['best_team']} ${row['best_aav']:.1f}M | interest {interest_bar(row['best_interest'], width=10)}")
    else:
        print(style("Top active offers", "accent"))
        print("  No active offers yet.")


def free_agency_user_offer_limit(day: int) -> int | None:
    if day <= 1:
        return 3
    if day == 2:
        return 6
    return None


def free_agency_bidding_wars(canonical: dict[str, Any], save: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for offer in save.get("free_agent_offers", []):
        if offer.get("status") == "active":
            grouped.setdefault(offer.get("player_id"), []).append(offer)
    rows = []
    for player_id, offers in grouped.items():
        best = max(offers, key=lambda item: (float(item.get("interest_score") or 0), float(item.get("aav_millions") or 0)))
        rows.append(
            {
                "player_name": players.get(player_id, {}).get("name", player_id),
                "offer_count": len(offers),
                "best_team": teams.get(best.get("team_id"), {}).get("abbrev", team_id_to_abbrev(best.get("team_id"))),
                "best_aav": float(best.get("aav_millions") or 0),
                "best_interest": float(best.get("interest_score") or 0),
            }
        )
    rows.sort(key=lambda item: (-item["offer_count"], -item["best_interest"], item["player_name"]))
    return rows[:limit]


def process_ai_free_agency_offers_for_day(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.setdefault("free_agency_state", {})
    if state.get("status") == "completed":
        return {"created_count": 0}
    day = int(state.get("day") or 1)
    day_key = f"{state.get('season')}:{day}"
    if day_key in set(state.get("ai_days_processed", [])):
        return {"created_count": 0}
    active = canonical_with_save(canonical, save)
    user_team_id = resolve_team(active, user_team)["id"]
    players = {player["id"]: player for player in active.get("players", [])}
    teams = [team for team in active.get("teams", []) if team.get("id") != user_team_id]
    report_by_id = {item.get("player_id") or item.get("id"): item for item in free_agents_report(active).get("candidates", [])}
    pool = [
        players[player_id]
        for player_id in save.get("free_agent_player_ids", [])
        if player_id in players and not player_already_has_accepted_offer(save, player_id)
    ]
    pool.sort(key=lambda player: free_agency_player_priority(active, save, player), reverse=True)
    created = 0
    target_count = min(len(pool), 18 + day * 8)
    for player in pool[:target_count]:
        market = report_by_id.get(player["id"]) or {}
        ask = float((state.get("player_asks_millions") or {}).get(player["id"]) or free_agency_initial_ask(player, market))
        offer_count = desired_ai_offer_count(player, ask, day, seed)
        suitors = ai_free_agency_suitors(active, save, player, teams, market, seed, day)
        for team in suitors[:offer_count]:
            if active_offer_exists(save, player["id"], team["id"]):
                continue
            rng = random.Random(f"{seed}:{state.get('season')}:{day}:{player['id']}:{team['id']}:ai_fa_offer")
            years = int(max(1, min(int(market.get("max_years") or 4), 4 if ask >= 18 else 3 if ask >= 8 else 2)))
            aav = round(max(1.8, ask * rng.uniform(0.9, 1.12 + day * 0.015)), 1)
            reserved = active_bid_commitment(save, team["id"], exclude_player_id=player["id"])
            cap = signing_cap_check(active, save, team["abbrev"], aav, reserved_millions=reserved)
            if not cap.get("ok"):
                continue
            offer = build_free_agency_offer_record(active, save, player, team, years, aav, ask, seed, "ai")
            save.setdefault("free_agent_offers", []).append(offer)
            created += 1
    state.setdefault("ai_days_processed", []).append(day_key)
    write_save(save_path, save)
    return {"created_count": created}


def player_already_has_accepted_offer(save: dict[str, Any], player_id: str) -> bool:
    return any(offer.get("player_id") == player_id and offer.get("status") == "accepted" for offer in save.get("free_agent_offers", []))


def active_offer_exists(save: dict[str, Any], player_id: str, team_id: str) -> bool:
    return any(
        offer.get("player_id") == player_id and offer.get("team_id") == team_id and offer.get("status") == "active"
        for offer in save.get("free_agent_offers", [])
    )


def free_agency_player_priority(canonical: dict[str, Any], save: dict[str, Any], player: dict[str, Any]) -> float:
    attrs = player_attribute_summary(canonical, player.get("id"))
    stats = active_season_line(save, player.get("id"), player)
    return float(attrs.get("overall") or 0) * 1.7 + display_minutes_projection(player) * 0.75 + float(stats.get("ppg") or 0) * 0.65


def desired_ai_offer_count(player: dict[str, Any], ask: float, day: int, seed: int) -> int:
    if ask >= 28 or display_minutes_projection(player) >= 28:
        base = 3 if day <= 2 else 2
    elif ask >= 12 or display_minutes_projection(player) >= 20:
        base = 2 if day <= 3 else 1
    else:
        base = 1 if day >= 2 else 0
    rng = random.Random(f"{seed}:{player.get('id')}:offers:{day}")
    return max(0, min(4, base + (1 if rng.random() > 0.72 else 0)))


def ai_free_agency_suitors(
    canonical: dict[str, Any],
    save: dict[str, Any],
    player: dict[str, Any],
    teams: list[dict[str, Any]],
    market: dict[str, Any],
    seed: int,
    day: int,
) -> list[dict[str, Any]]:
    likely = set(market.get("likely_suitors") or [])
    scored = []
    for team in teams:
        roster = [row for row in canonical.get("players", []) if row.get("team_id") == team["id"]]
        roster_need = max(0, 15 - len(roster)) * 4.0
        fit = float(market.get("team_fit_score") or 50.0) if team["id"] in likely else 48.0 + roster_need
        position_need = 4.0 if sum(1 for row in roster if row.get("position") == player.get("position")) <= 2 else 0.0
        rng = random.Random(f"{seed}:{day}:{team['id']}:{player['id']}:suitor")
        scored.append((fit + position_need + rng.uniform(-6.0, 8.0), team))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [team for _, team in scored]


def free_agency_offer_context_score(
    canonical: dict[str, Any],
    save: dict[str, Any],
    player: dict[str, Any],
    team: dict[str, Any],
    years: int,
    source: str,
) -> dict[str, Any]:
    attrs = player_attribute_summary(canonical, player.get("id"))
    roster = [row for row in canonical.get("players", []) if row.get("team_id") == team.get("id")]
    same_position = [row for row in roster if row.get("position") == player.get("position")]
    stronger_same_position = sum(
        1
        for row in same_position
        if float(player_attribute_summary(canonical, row.get("id")).get("overall") or 0.0) > float(attrs.get("overall") or 0.0) + 2.5
    )
    roster_count = len(roster)
    projected_minutes = clamp(
        display_minutes_projection(player)
        + max(0.0, 4.0 - stronger_same_position) * 2.3
        + max(0.0, 14 - roster_count) * 1.4
        - max(0.0, stronger_same_position - 2) * 2.6,
        4.0,
        34.0,
    )
    role_score = clamp(26.0 + projected_minutes * 2.05, 20.0, 96.0)
    record = save.get("team_records", {}).get(team.get("id"), {})
    games = int(record.get("wins", 0)) + int(record.get("losses", 0))
    win_pct = float(record.get("wins", 0)) / games if games else 0.5
    winning_score = clamp(42.0 + (win_pct - 0.5) * 70.0, 25.0, 92.0)
    position_need = clamp(62.0 + max(0.0, 3 - len(same_position)) * 9.0 - max(0.0, len(same_position) - 5) * 7.0, 25.0, 95.0)
    fit_score = clamp(
        45.0
        + (float(attrs.get("shooting") or 50.0) - 55.0) * 0.12
        + (float(attrs.get("defense") or 50.0) - 55.0) * 0.1
        + (float(attrs.get("creation") or 50.0) - 55.0) * 0.08
        + (position_need - 50.0) * 0.35,
        18.0,
        96.0,
    )
    market_score = clamp(48.0 + deterministic_ratio(team.get("id"), player.get("id"), "fa_market") * 22.0, 42.0, 74.0)
    security_score = clamp(34.0 + max(1, years) * 15.0, 30.0, 92.0)
    loyalty = 8.0 if player.get("previous_team_id") == team.get("id") or player.get("team_id") == team.get("id") else 0.0
    user_bonus = 2.5 if source == "user" and team.get("id") == save.get("meta", {}).get("user_team_id") else 0.0
    context = (
        role_score * 0.28
        + fit_score * 0.22
        + winning_score * 0.2
        + market_score * 0.12
        + security_score * 0.1
        + position_need * 0.08
        + loyalty
        + user_bonus
    )
    return {
        "context_score": round(clamp(context, 0.0, 100.0), 1),
        "projected_minutes": round(projected_minutes, 1),
        "role": round(role_score, 1),
        "fit": round(fit_score, 1),
        "winning": round(winning_score, 1),
        "market": round(market_score, 1),
        "security": round(security_score, 1),
        "position_need": round(position_need, 1),
        "loyalty_bonus": round(loyalty, 1),
    }


def build_free_agency_offer_record(
    canonical: dict[str, Any],
    save: dict[str, Any],
    player: dict[str, Any],
    team: dict[str, Any],
    years: int,
    aav_millions: float,
    ask_millions: float,
    seed: int,
    source: str,
) -> dict[str, Any]:
    day = int((save.get("free_agency_state") or {}).get("day") or 1)
    preferred_years = 4 if ask_millions >= 18 else 3 if ask_millions >= 8 else 2
    context = free_agency_offer_context_score(canonical, save, player, team, years, source)
    interest = offer_interest_score(aav_millions, ask_millions, years, preferred_years, float(context["context_score"]))
    offer_id = stable_id("fa_offer", save.get("free_agency_state", {}).get("season"), day, source, team["id"], player["id"], years, round(aav_millions * 10))
    return {
        "id": offer_id,
        "season": save.get("free_agency_state", {}).get("season"),
        "day": day,
        "source": source,
        "player_id": player["id"],
        "team_id": team["id"],
        "years": years,
        "aav_millions": round(aav_millions, 1),
        "ask_millions": round(ask_millions, 1),
        "interest_score": interest,
        "interest_context": context,
        "status": "active",
        "created_date": save.get("state", {}).get("current_date"),
    }


def free_agency_player_market(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    while True:
        save = initialize_free_agency_market(canonical, save_path, user_team, seed)
        active = canonical_with_save(canonical, save)
        players = free_agency_board_players(active, save)
        clear_screen()
        print_title("Free Agent Market")
        print_free_agency_status(canonical, save, user_team)
        print_rule()
        print(" #  Player                     Pos Age OVR   PPG  Ask       Offers / best interest")
        for idx, player in enumerate(players[:60], start=1):
            attrs = player_attribute_summary(active, player["id"])
            stats = active_season_line(save, player["id"], player)
            ask = float((save.get("free_agency_state", {}).get("player_asks_millions") or {}).get(player["id"]) or 0)
            offers = active_offers_for_player(save, player["id"])
            best = max(offers, key=lambda item: (float(item.get("interest_score") or 0), float(item.get("aav_millions") or 0)), default=None)
            best_text = "none"
            if best:
                best_text = (
                    f"{len(offers)} | {team_id_to_abbrev(best.get('team_id'))} "
                    f"${float(best.get('aav_millions') or 0):.1f}M {interest_bar(best.get('interest_score'), width=10)}"
                )
            print(
                f"{idx:>2}. {player.get('name', ''):<26} {compact_position(player.get('position')):<3} {age_text(player, 3)} "
                f"{float(attrs.get('overall') or 0):>3.0f} {stats['ppg']:>5.1f} ${ask:>5.1f}M  {best_text}"
            )
        print(" 0. Back")
        raw = input("Player row, or comma-separated rows to compare [0]: ").strip() or "0"
        if raw == "0":
            clear_screen()
            return
        choices = []
        for token in [part.strip() for part in raw.split(",") if part.strip()]:
            if token.isdigit() and 1 <= int(token) <= min(60, len(players)):
                choices.append(int(token))
        if not choices:
            continue
        if len(choices) > 1:
            selected_player = compare_free_agents_then_pick(active, save, [players[idx - 1] for idx in choices])
            if not selected_player:
                continue
            inspect_free_agent_and_maybe_offer(canonical, save_path, user_team, selected_player, seed)
        else:
            inspect_free_agent_and_maybe_offer(canonical, save_path, user_team, players[choices[0] - 1], seed)


def compare_free_agents_then_pick(canonical: dict[str, Any], save: dict[str, Any], players: list[dict[str, Any]]) -> dict[str, Any] | None:
    clear_screen()
    print_title("Compare Free Agents")
    print(" #  Player                     Pos Age Ht    Ask       Last yr         OVR Shot Cre Def Rim Pass")
    asks = (save.get("free_agency_state") or {}).get("player_asks_millions") or {}
    for idx, player in enumerate(players, start=1):
        attrs = player_attribute_summary(canonical, player["id"])
        stats = active_season_line(save, player["id"], player)
        ask = float(asks.get(player["id"]) or free_agency_initial_ask(player, {}))
        print(
            f"{idx:>2}. {player.get('name', ''):<26} {compact_position(player.get('position')):<3} "
            f"{age_text(player, 3)} {height_text(player):<5} ${ask:>5.1f}M  "
            f"{stats['ppg']:>4.1f}p/{stats['rpg']:>3.1f}r/{stats['apg']:>3.1f}a  "
            f"{rating_cell(attrs.get('overall')):>3} {rating_cell(attrs.get('shooting')):>4} "
            f"{rating_cell(attrs.get('creation')):>3} {rating_cell(attrs.get('defense')):>3} "
            f"{rating_cell(attrs.get('rim_deterrence')):>3} {rating_cell(attrs.get('passing')):>4}"
        )
    print(" 0. Back")
    choice = pick_number("Negotiate with", 0, len(players), default=0)
    if choice == 0:
        clear_screen()
        return None
    return players[choice - 1]


def free_agency_board_players(canonical: dict[str, Any], save: dict[str, Any]) -> list[dict[str, Any]]:
    players = {player["id"]: player for player in canonical.get("players", [])}
    retired = set(save.get("retired_player_ids", []))
    rows = [players[player_id] for player_id in save.get("free_agent_player_ids", []) if player_id in players and player_id not in retired]
    rows.sort(key=lambda player: free_agency_player_priority(canonical, save, player), reverse=True)
    return rows


def active_offers_for_player(save: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
    season = (save.get("free_agency_state") or {}).get("season")
    return [
        offer for offer in save.get("free_agent_offers", [])
        if offer.get("player_id") == player_id
        and offer.get("status") == "active"
        and (not season or not offer.get("season") or offer.get("season") == season)
    ]


def active_bid_commitment(
    save: dict[str, Any],
    team_id: str | None,
    exclude_player_id: str | None = None,
    source: str | None = None,
) -> float:
    total = 0.0
    for offer in save.get("free_agent_offers", []):
        if offer.get("status") != "active":
            continue
        if source and offer.get("source") != source:
            continue
        if team_id and offer.get("team_id") != team_id:
            continue
        if exclude_player_id and offer.get("player_id") == exclude_player_id:
            continue
        aav = float(offer.get("aav_millions") or 0.0)
        if aav <= league_minimum_aav_millions() + 0.05:
            continue
        total += aav
    return round(total, 2)


def user_active_bid_commitment(save: dict[str, Any], team_id: str | None, exclude_player_id: str | None = None) -> float:
    return active_bid_commitment(save, team_id, exclude_player_id=exclude_player_id, source="user")


def inspect_free_agent_and_maybe_offer(canonical: dict[str, Any], save_path: Path, user_team: str, player: dict[str, Any], seed: int) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    market = next((item for item in free_agents_report(active, team_query=user_team).get("candidates", []) if (item.get("player_id") or item.get("id")) == player["id"]), {})
    print_free_agent_investigation(active, save, player, market, user_team)
    print_existing_free_agent_offers(active, save, player["id"])
    state = save.get("free_agency_state") or {}
    day = int(state.get("day") or 1)
    used = int((state.get("user_offer_counts") or {}).get(str(day), 0))
    limit = free_agency_user_offer_limit(day)
    if limit is not None and used >= limit:
        pause("You have used all of today's free-agent offer slots.")
        return
    team = resolve_team(active, user_team)
    existing_user_offer = next(
        (
            offer for offer in save.get("free_agent_offers", [])
            if offer.get("status") == "active"
            and offer.get("source") == "user"
            and offer.get("player_id") == player["id"]
            and offer.get("team_id") == team["id"]
        ),
        None,
    )
    replacing_offer_id = None
    if existing_user_offer:
        if int(existing_user_offer.get("day") or day) >= day:
            pause("You already made an active offer to this player today. Wait a day or withdraw it from Active User Bids.")
            return
        print_rule()
        print("You already have an older active offer to this player.")
        print("1. Replace it with a new offer")
        print("2. Withdraw the old offer")
        print("0. Back")
        action = pick_number("Action", 0, 2, default=0)
        if action == 0:
            return
        if action == 2:
            existing_user_offer["status"] = "withdrawn_by_user"
            write_save(save_path, save)
            pause("Offer withdrawn.")
            return
        replacing_offer_id = existing_user_offer.get("id")
    print_rule()
    print("1. Make final user offer")
    print("0. Back")
    if pick_number("Action", 0, 1, default=0) == 0:
        return
    ask = float((state.get("player_asks_millions") or {}).get(player["id"]) or free_agency_initial_ask(player, market))
    suggested = round(max(1.8, ask), 1)
    print(f"Type {league_minimum_aav_millions():.1f} for a league-minimum offer.")
    try:
        aav = float(input(f"Offer AAV in millions [{suggested:.1f}]: ").strip() or suggested)
    except ValueError:
        aav = suggested
    years = pick_number("Years", 1, 4, default=min(3, int(market.get("max_years") or 3)))
    reserved = user_active_bid_commitment(save, team["id"], exclude_player_id=player["id"])
    cap_check = signing_cap_check(active, save, user_team, aav, reserved_millions=reserved)
    if not cap_check.get("ok"):
        pause(cap_check["message"])
        return
    offer = build_free_agency_offer_record(active, save, player, team, years, aav, ask, seed, "user")
    save.setdefault("free_agent_offers", [])
    if replacing_offer_id:
        for old_offer in save.get("free_agent_offers", []):
            if old_offer.get("id") == replacing_offer_id:
                old_offer["status"] = "replaced_by_user_offer"
    save["free_agent_offers"].append(offer)
    state.setdefault("user_offer_counts", {})[str(day)] = used + 1
    write_save(save_path, save)
    print_title("Offer Submitted")
    print(f"{player['name']} | {user_team} ${aav:.1f}M x {years}")
    context = offer.get("interest_context") or {}
    print_interest_read(
        float(offer["interest_score"]),
        {
            "ask": f"${ask:.1f}M",
            "role": f"{float(context.get('role') or 0):.0f}/100",
            "fit": f"{float(context.get('fit') or 0):.0f}/100",
            "winning": f"{float(context.get('winning') or 0):.0f}/100",
            "cap": cap_check.get("message") or "legal",
        },
    )
    wait()


def print_existing_free_agent_offers(canonical: dict[str, Any], save: dict[str, Any], player_id: str) -> None:
    offers = active_offers_for_player(save, player_id)
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    print_rule()
    print("Existing offers")
    if not offers:
        print("  No active offers yet.")
        return
    offers.sort(key=lambda item: (float(item.get("interest_score") or 0), float(item.get("aav_millions") or 0)), reverse=True)
    for offer in offers:
        team = teams.get(offer.get("team_id"), {})
        source = "you" if offer.get("source") == "user" else "AI"
        print(
            f"  {team.get('abbrev') or team_id_to_abbrev(offer.get('team_id')):<3} "
            f"${float(offer.get('aav_millions') or 0):>5.1f}M x {offer.get('years')} | {source:<3} | {interest_bar(offer.get('interest_score'), width=12)}"
        )
        context = offer.get("interest_context") or {}
        if context:
            print(
                f"      role {float(context.get('role') or 0):.0f} | fit {float(context.get('fit') or 0):.0f} | "
                f"winning {float(context.get('winning') or 0):.0f} | security {float(context.get('security') or 0):.0f} | "
                f"proj {float(context.get('projected_minutes') or 0):.0f} MPG"
            )


def print_user_active_bids(canonical: dict[str, Any], save_path: Path, user_team: str) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, user_team)
    players = {player["id"]: player for player in active.get("players", [])}
    offers = [
        offer for offer in save.get("free_agent_offers", [])
        if offer.get("status") == "active" and offer.get("source") == "user" and offer.get("team_id") == team["id"]
    ]
    print_title("Active User Bids")
    if not offers:
        print("No active user bids are currently outstanding.")
        return
    for offer in sorted(offers, key=lambda item: (-float(item.get("interest_score") or 0), item.get("player_id", ""))):
        player = players.get(offer.get("player_id"), {})
        best = max(active_offers_for_player(save, offer.get("player_id")), key=lambda item: (float(item.get("interest_score") or 0), float(item.get("aav_millions") or 0)), default=None)
        is_best = best and best.get("id") == offer.get("id")
        best_label = style("BEST OFFER STILL", "good") if is_best else style("NOT BEST OFFER", "danger")
        print(
            f"{player.get('name', offer.get('player_id')):<26} ${float(offer.get('aav_millions') or 0):>5.1f}M x {offer.get('years')} "
            f"| day {offer.get('day')} | {interest_bar(offer.get('interest_score'), width=12)} | {best_label}"
        )
        if best and not is_best:
            print(
                f"    Best: {team_id_to_abbrev(best.get('team_id'))} ${float(best.get('aav_millions') or 0):.1f}M x {best.get('years')} "
                f"{interest_bar(best.get('interest_score'), width=10)}"
            )
        context = offer.get("interest_context") or {}
        if context:
            print(
                f"    role {float(context.get('role') or 0):.0f} | fit {float(context.get('fit') or 0):.0f} | "
                f"winning {float(context.get('winning') or 0):.0f} | projected {float(context.get('projected_minutes') or 0):.0f} MPG"
            )


def withdraw_user_free_agent_bid(canonical: dict[str, Any], save_path: Path, user_team: str) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    team = resolve_team(active, user_team)
    players = {player["id"]: player for player in active.get("players", [])}
    offers = [
        offer for offer in save.get("free_agent_offers", [])
        if offer.get("status") == "active" and offer.get("source") == "user" and offer.get("team_id") == team["id"]
    ]
    clear_screen()
    print_title("Withdraw Active Bid")
    if not offers:
        print("No active user bids are currently outstanding.")
        wait()
        return
    for idx, offer in enumerate(offers, start=1):
        player = players.get(offer.get("player_id"), {})
        print(f"{idx:>2}. {player.get('name', offer.get('player_id')):<26} ${float(offer.get('aav_millions') or 0):.1f}M x {offer.get('years')}")
    print(" 0. Back")
    choice = pick_number("Bid", 0, len(offers), default=0)
    if choice == 0:
        clear_screen()
        return
    offers[choice - 1]["status"] = "withdrawn_by_user"
    write_save(save_path, save)
    pause("Offer withdrawn.")


def print_free_agency_day_recap(canonical: dict[str, Any], save_path: Path, day: int, result: dict[str, Any]) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    print_title(f"Free Agency Day {day} Recap")
    print(f"Accepted signings: {result.get('accepted_count', 0)} | Ask adjustments: {result.get('ask_adjusted_count', 0)}")
    print_rule()
    print(style("Your offers", "accent"))
    user_team_id = save.get("meta", {}).get("user_team_id")
    user_offers = [
        offer for offer in save.get("free_agent_offers", [])
        if offer.get("source") == "user" and offer.get("day") == day and offer.get("team_id") == user_team_id
    ]
    if not user_offers:
        print("  No user offers were resolved from this day.")
    for offer in user_offers:
        player = players.get(offer.get("player_id"), {})
        print(
            f"  {player.get('name', offer.get('player_id')):<26} {clean_label(offer.get('status')):<28} "
            f"${float(offer.get('aav_millions') or 0):.1f}M x {offer.get('years')}"
        )
    print_rule()
    print(style("League movement", "accent"))
    accepted_offers = result.get("accepted_offers") or []
    if not accepted_offers:
        print("  No signings have been applied yet.")
    for offer in accepted_offers[-14:]:
        player = players.get(offer.get("player_id"), {"name": offer.get("player_id")})
        team = teams.get(offer.get("team_id"), {})
        print(f"  {player.get('name')} -> {team.get('abbrev') or 'TEAM'} ${float(offer.get('aav_millions') or 0):.1f}M x {offer.get('years')}")
    trade_news = result.get("ai_trade_news") or []
    if trade_news:
        print_rule()
        print(style("League trades", "accent"))
        for item in trade_news[-8:]:
            print(f"  {item.get('headline')}")


def print_free_agency_breaking_news(news: list[dict[str, Any]]) -> None:
    if not news:
        return
    clear_screen()
    print_title("Breaking News")
    print("Free-agency trade activity")
    for item in news[-10:]:
        print(f"  {item.get('headline')}")
    print_rule()


def advance_free_agency_day(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> dict[str, Any]:
    process_ai_free_agency_offers_for_day(canonical, save_path, user_team, seed)
    pre_trades = maybe_run_free_agency_ai_trades(canonical, save_path, user_team, seed, phase="pre_resolution")
    accepted = resolve_free_agency_day(canonical, save_path, seed)
    post_trades = maybe_run_free_agency_ai_trades(canonical, save_path, user_team, seed, phase="post_resolution")
    adjusted = adjust_free_agent_asks(canonical, save_path, seed)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.setdefault("free_agency_state", {})
    day = int(state.get("day") or 1)
    if day >= int(state.get("day_count") or 5):
        state["status"] = "completed"
    else:
        state["day"] = day + 1
    write_save(save_path, save)
    if state.get("status") != "completed":
        process_ai_free_agency_offers_for_day(canonical, save_path, user_team, seed)
    return {
        "accepted_count": accepted.get("accepted_count", 0),
        "accepted_offers": accepted.get("accepted_offers", []),
        "ask_adjusted_count": adjusted.get("ask_adjusted_count", 0),
        "ai_trade_news": [*(pre_trades.get("news") or []), *(post_trades.get("news") or [])],
    }


def maybe_run_free_agency_ai_trades(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, phase: str) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.setdefault("free_agency_state", {})
    if state.get("status") == "completed":
        return {"applied_count": 0, "news": []}
    day = int(state.get("day") or 1)
    key = f"{state.get('season')}:{day}:{phase}"
    processed = set(state.setdefault("ai_trade_days_processed", []))
    if key in processed:
        return {"applied_count": 0, "news": []}
    state.setdefault("ai_trade_days_processed", []).append(key)
    write_save(save_path, save)
    user_team_id = resolve_team(canonical, user_team)["id"]
    active = with_transaction_context(canonical_with_save(canonical, save))
    candidates = (
        free_agency_cap_dump_candidates(active, save, user_team_id, seed)
        if phase == "pre_resolution"
        else free_agency_fallback_trade_candidates(active, save, user_team_id, seed)
    )
    if not candidates and phase == "post_resolution" and int(state.get("ai_general_trade_count") or 0) < 3:
        candidates = free_agency_general_trade_candidates(active, save, user_team_id, seed)
    news: list[dict[str, Any]] = []
    applied_count = 0
    for candidate in candidates[:2]:
        result = apply_ai_trade_candidate_to_save(canonical, save_path, candidate, save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
        if result.get("status") != "applied":
            continue
        applied_count += 1
        proposal = candidate.get("proposal") or {}
        headline = trade_headline_from_payload(proposal)
        news.append({"headline": headline, "proposal_id": proposal.get("id"), "phase": phase})
        if phase == "pre_resolution":
            upgrade_free_agency_offer_after_dump(canonical, save_path, candidate, user_team_id, seed)
        elif candidate.get("free_agency_context", {}).get("offer_id"):
            saved = ensure_league_save_defaults(load_save(save_path), canonical)
            saved.setdefault("free_agency_state", {}).setdefault("ai_fallback_trade_offer_ids", []).append(candidate["free_agency_context"]["offer_id"])
            write_save(save_path, saved)
        elif (candidate.get("free_agency_context") or {}).get("kind") == "general_market_trade":
            saved = ensure_league_save_defaults(load_save(save_path), canonical)
            saved.setdefault("free_agency_state", {})["ai_general_trade_count"] = int((saved.get("free_agency_state") or {}).get("ai_general_trade_count") or 0) + 1
            write_save(save_path, saved)
    return {"applied_count": applied_count, "news": news}


def free_agency_general_trade_candidates(active: dict[str, Any], save: dict[str, Any], user_team_id: str, seed: int) -> list[dict[str, Any]]:
    from .transactions import simulate_ai_trades

    current = save.get("state", {}).get("current_date") or CANONICAL_START_DATE
    day = int((save.get("free_agency_state") or {}).get("day") or 1)
    payload = simulate_ai_trades(active, current, current, seed=seed + day * 17, limit=12)
    candidates: list[dict[str, Any]] = []
    for candidate in payload.get("proposals", []):
        proposal = candidate.get("proposal") or {}
        if user_team_id in {proposal.get("from_team_id"), proposal.get("to_team_id")}:
            continue
        if not candidate.get("accepted_by_all") or (candidate.get("legality") or {}).get("status") != "legal":
            continue
        candidate["free_agency_context"] = {"kind": "general_market_trade"}
        candidates.append(candidate)
    return candidates[:1]


def free_agency_cap_dump_candidates(active: dict[str, Any], save: dict[str, Any], user_team_id: str, seed: int) -> list[dict[str, Any]]:
    del seed
    players = {player["id"]: player for player in active.get("players", [])}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for offer in save.get("free_agent_offers", []):
        if offer.get("status") == "active":
            grouped.setdefault(offer.get("player_id"), []).append(offer)
    candidates: list[tuple[float, dict[str, Any]]] = []
    for player_id, offers in grouped.items():
        player = players.get(player_id, {})
        if display_minutes_projection(player) < 18 and max(float(offer.get("aav_millions") or 0.0) for offer in offers) < 10:
            continue
        best = max(offers, key=lambda item: (float(item.get("interest_score") or 0.0), float(item.get("aav_millions") or 0.0)))
        for offer in offers:
            team_id = offer.get("team_id")
            if team_id == user_team_id or team_id == best.get("team_id") or offer.get("source") != "ai":
                continue
            if float(best.get("interest_score") or 0.0) - float(offer.get("interest_score") or 0.0) > 16.0:
                continue
            candidate = free_agency_cap_dump_candidate_for_team(active, save, team_id, user_team_id, offer)
            if candidate:
                candidates.append((float(offer.get("interest_score") or 0.0), candidate))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in candidates]


def free_agency_cap_dump_candidate_for_team(active: dict[str, Any], save: dict[str, Any], team_id: str, user_team_id: str, offer: dict[str, Any]) -> dict[str, Any] | None:
    team = team_by_id(active, team_id)
    values = {value["player_id"]: value for value in active.get("player_asset_valuations", [])}
    recent = recently_traded_player_ids(active, save.get("state", {}).get("current_date"))
    signed_lock = recently_signed_player_ids(active, save.get("state", {}).get("current_date"))
    roster = [
        player for player in active.get("players", [])
        if player.get("team_id") == team_id
        and player.get("id") not in recent
        and player.get("id") not in signed_lock
        and not player.get("id", "").startswith("rookie_")
    ]
    dumpable = []
    for player in roster:
        salary = current_salary(contract_for_player(active, player["id"])) or 0.0
        value = float(values.get(player["id"], fallback_asset_valuation(player)).get("player_value") or 0.0)
        if salary >= 3_000_000 and value < 44.0 and display_minutes_projection(player) < 22:
            dumpable.append((value + display_minutes_projection(player) * 0.35, salary, player))
    if not dumpable:
        return None
    _, salary, player = sorted(dumpable, key=lambda item: (item[0], -item[1]))[0]
    recipients = []
    for other in active.get("teams", []):
        if other.get("id") in {team_id, user_team_id}:
            continue
        cap = team_cap_summary(active, save, other["id"])
        if float(cap.get("tax_space_millions") or 0.0) >= salary / 1_000_000 + 1.0:
            recipients.append(other)
    if not recipients:
        return None
    sweetener = next((pick for pick in tradeable_picks_for_team(active, team_id) if int(pick.get("round") or 0) == 2), None)
    from_assets = [{"kind": "player", "value": player["name"]}]
    if sweetener:
        from_assets.append({"kind": "pick", "value": sweetener["id"]})
    for recipient in sorted(recipients, key=lambda item: item.get("abbrev", "")):
        try:
            report = evaluate_trade(active, team["abbrev"], recipient["abbrev"], from_assets, [], seed=1, date=save.get("state", {}).get("current_date") or CANONICAL_START_DATE)
        except ValueError:
            continue
        if report.get("legality", {}).get("status") != "legal":
            continue
        candidate = candidate_from_evaluation(active, report)
        candidate["accepted_by_all"] = True
        candidate["free_agency_context"] = {"kind": "cap_dump", "offer_id": offer.get("id"), "player_id": offer.get("player_id")}
        return candidate
    return None


def upgrade_free_agency_offer_after_dump(canonical: dict[str, Any], save_path: Path, candidate: dict[str, Any], user_team_id: str, seed: int) -> None:
    context = candidate.get("free_agency_context") or {}
    offer_id = context.get("offer_id")
    if not offer_id:
        return
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    offer = next((item for item in save.get("free_agent_offers", []) if item.get("id") == offer_id and item.get("status") == "active"), None)
    if not offer or offer.get("team_id") == user_team_id:
        return
    active = canonical_with_save(canonical, save)
    player = player_by_id(active, offer.get("player_id"))
    team = team_by_id(active, offer.get("team_id"))
    ask = float((save.get("free_agency_state") or {}).get("player_asks_millions", {}).get(offer.get("player_id")) or offer.get("ask_millions") or offer.get("aav_millions") or 0.0)
    bumped = round(min(max(float(offer.get("aav_millions") or 0.0) + 3.0, ask * 1.04), ask * 1.18), 1)
    reserved = active_bid_commitment(save, team["id"], exclude_player_id=offer.get("player_id"))
    if not signing_cap_check(active, save, team["abbrev"], bumped, reserved_millions=reserved).get("ok"):
        return
    offer["aav_millions"] = bumped
    context_score = float((offer.get("interest_context") or {}).get("context_score") or 55.0)
    offer["interest_score"] = offer_interest_score(bumped, ask, int(offer.get("years") or 1), int(offer.get("years") or 1), context_score)
    offer.setdefault("notes", "AI cleared salary and improved this free-agency offer.")
    write_save(save_path, save)


def free_agency_fallback_trade_candidates(active: dict[str, Any], save: dict[str, Any], user_team_id: str, seed: int) -> list[dict[str, Any]]:
    processed = set((save.get("free_agency_state") or {}).get("ai_fallback_trade_offer_ids") or [])
    candidates: list[dict[str, Any]] = []
    for offer in save.get("free_agent_offers", []):
        if offer.get("id") in processed or offer.get("source") != "ai" or offer.get("team_id") == user_team_id:
            continue
        if offer.get("status") != "rejected_player_chose_other_offer":
            continue
        lost_player = player_by_id(active, offer.get("player_id"))
        if not lost_player or (display_minutes_projection(lost_player) < 18 and float(offer.get("aav_millions") or 0.0) < 10):
            continue
        target = similar_trade_target_for_lost_free_agent(active, save, lost_player, offer.get("team_id"), user_team_id)
        if not target:
            continue
        seller = team_by_id(active, target.get("team_id"))
        buyer = team_by_id(active, offer.get("team_id"))
        report = find_trade_for_assets(active, seller["abbrev"], [{"kind": "player", "value": target["name"]}], for_team=buyer["abbrev"], limit=5, seed=seed)
        accepted = next((candidate for candidate in report.get("candidates", []) if candidate.get("legality", {}).get("status") == "legal"), None)
        if not accepted:
            continue
        accepted["accepted_by_all"] = True
        accepted["free_agency_context"] = {"kind": "missed_target_fallback", "offer_id": offer.get("id"), "lost_player_id": lost_player.get("id")}
        candidates.append(accepted)
    return candidates


def similar_trade_target_for_lost_free_agent(active: dict[str, Any], save: dict[str, Any], lost_player: dict[str, Any], buyer_team_id: str, user_team_id: str) -> dict[str, Any] | None:
    values = {value["player_id"]: value for value in active.get("player_asset_valuations", [])}
    lost_attrs = player_attribute_summary(active, lost_player["id"])
    lost_value = float(values.get(lost_player["id"], fallback_asset_valuation(lost_player)).get("player_value") or 0.0)
    recent = recently_traded_player_ids(active, save.get("state", {}).get("current_date"))
    signed_lock = recently_signed_player_ids(active, save.get("state", {}).get("current_date"))
    rows = []
    for player in active.get("players", []):
        if not player.get("team_id") or player.get("team_id") in {buyer_team_id, user_team_id} or player.get("id") in recent or player.get("id") in signed_lock:
            continue
        if player.get("id") in set(save.get("free_agent_player_ids") or []):
            continue
        if player.get("position") != lost_player.get("position"):
            continue
        value = float(values.get(player["id"], fallback_asset_valuation(player)).get("player_value") or 0.0)
        if abs(value - lost_value) > 16.0:
            continue
        attrs = player_attribute_summary(active, player["id"])
        skill_gap = sum(
            abs(float(attrs.get(key) or 50.0) - float(lost_attrs.get(key) or 50.0))
            for key in ["shooting", "creation", "defense", "rim_deterrence", "passing"]
        )
        rows.append((skill_gap + abs(display_minutes_projection(player) - display_minutes_projection(lost_player)) * 1.2, player))
    return sorted(rows, key=lambda item: (item[0], item[1].get("name", "")))[0][1] if rows else None


def resolve_free_agency_day(canonical: dict[str, Any], save_path: Path, seed: int) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.get("free_agency_state") or {}
    day = int(state.get("day") or 1)
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    grouped: dict[str, list[dict[str, Any]]] = {}
    season = state.get("season")
    for offer in save.get("free_agent_offers", []):
        if (
            offer.get("status") == "active"
            and offer.get("player_id") in set(save.get("free_agent_player_ids", []))
            and (not season or not offer.get("season") or offer.get("season") == season)
        ):
            grouped.setdefault(offer.get("player_id"), []).append(offer)
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for player_id, offers in sorted(grouped.items()):
        player = players.get(player_id, {})
        best = max(offers, key=lambda item: (float(item.get("interest_score") or 0), float(item.get("aav_millions") or 0)))
        threshold = free_agency_accept_threshold(player, day)
        if float(best.get("interest_score") or 0) < threshold:
            continue
        priority = (
            (25.0 if best.get("source") == "user" else 0.0)
            + float(best.get("interest_score") or 0) * 0.18
            + float(best.get("aav_millions") or 0) * 0.72
            + int(best.get("years") or 1) * 1.2
        )
        candidates.append((priority, player_id, best))
    accepted_count = 0
    accepted_offers: list[dict[str, Any]] = []
    for _, _, best in sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True):
        result = apply_free_agency_offer(canonical, save_path, best["id"], seed)
        if result.get("status") == "applied":
            accepted_count += 1
            accepted_offers.append(
                {
                    "offer_id": best.get("id"),
                    "player_id": best.get("player_id"),
                    "team_id": best.get("team_id"),
                    "aav_millions": best.get("aav_millions"),
                    "years": best.get("years"),
                    "source": best.get("source"),
                }
            )
    return {"accepted_count": accepted_count, "accepted_offers": accepted_offers}


def free_agency_accept_threshold(player: dict[str, Any], day: int) -> float:
    priority = display_minutes_projection(player)
    if priority >= 28:
        return {1: 88, 2: 80, 3: 72, 4: 62, 5: 48}.get(day, 48)
    if priority >= 18:
        return {1: 82, 2: 73, 3: 64, 4: 54, 5: 42}.get(day, 42)
    return {1: 92, 2: 78, 3: 62, 4: 46, 5: 35}.get(day, 35)


def apply_free_agency_offer(canonical: dict[str, Any], save_path: Path, offer_id: str, seed: int) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    offer = next((item for item in save.get("free_agent_offers", []) if item.get("id") == offer_id), None)
    if not offer or offer.get("status") != "active":
        return {"status": "not_found"}
    active = canonical_with_save(canonical, save)
    players = {player["id"]: player for player in active.get("players", [])}
    teams = {team["id"]: team for team in active.get("teams", [])}
    player = players.get(offer.get("player_id"), {"id": offer.get("player_id"), "name": offer.get("player_id")})
    team = teams.get(offer.get("team_id"), {"id": offer.get("team_id"), "abbrev": team_id_to_abbrev(offer.get("team_id"))})
    if extension_retirement_blocked(player, contract_start_season_for_signing(save), int(offer.get("years") or 1)):
        offer["status"] = "withdrawn_retirement_risk"
        write_save(save_path, save)
        return {"status": "blocked", "notes": f"{player.get('name')} is expected to retire before this contract would finish."}
    # Submission reserves room for active user bids; acceptance is checked against
    # the live cap after any earlier accepted offers have already been applied.
    reserved = 0.0
    cap = signing_cap_check(active, save, team.get("abbrev"), float(offer.get("aav_millions") or 0), reserved_millions=reserved)
    if not cap.get("ok"):
        offer["status"] = "withdrawn_cap_blocked"
        write_save(save_path, save)
        return {"status": "blocked", "notes": cap.get("message")}
    negotiation = negotiation_from_free_agency_offer(save, offer, player, team, seed)
    save.setdefault("pending_contract_negotiations", []).append(negotiation)
    for item in save.get("free_agent_offers", []):
        if item.get("player_id") == offer.get("player_id") and item.get("status") == "active":
            item["status"] = "accepted" if item.get("id") == offer_id else "rejected_player_chose_other_offer"
    write_save(save_path, save)
    return apply_contract_to_save(save_path, negotiation["negotiation"]["id"], date=save.get("state", {}).get("current_date") or "2026-07-01")


def negotiation_from_free_agency_offer(save: dict[str, Any], offer: dict[str, Any], player: dict[str, Any], team: dict[str, Any], seed: int) -> dict[str, Any]:
    annual = float(offer.get("aav_millions") or 0.0) * 1_000_000
    start_season = contract_start_season_for_signing(save)
    negotiation_id = stable_id("contract_negotiation", "fa_day", offer.get("id"), seed)
    contract_offer = {
        "id": stable_id("contract_offer", negotiation_id, offer.get("id")),
        "negotiation_id": negotiation_id,
        "team_id": team["id"],
        "player_id": player["id"],
        "offer_type": "free_agent_signing",
        "round": int(offer.get("day") or 1),
        "years": int(offer.get("years") or 1),
        "start_season": start_season,
        "annual_salary": annual,
        "total_salary": annual * int(offer.get("years") or 1),
        "role_promise": "market_role",
        "status": "accepted",
        "notes": "Accepted free-agency day-market offer.",
    }
    decision = {
        "id": stable_id("signing_decision", negotiation_id, "fa_day"),
        "negotiation_id": negotiation_id,
        "player_id": player["id"],
        "team_id": team["id"],
        "accepted": True,
        "decision": "accept",
        "accepted_offer": contract_offer,
        "player_score": float(offer.get("interest_score") or 0.0),
        "team_score": 60.0,
        "competing_offers": [],
        "reasons": ["best_active_free_agency_market_offer"],
        "source_ids": ["src_contract_market_config_v1"],
        "notes": "Player accepted via the five-day free-agency market.",
    }
    return {
        "negotiation": {
            "id": negotiation_id,
            "negotiation_type": "free_agent_signing",
            "player_id": player["id"],
            "player_name": player.get("name"),
            "team_id": team["id"],
            "date": save.get("state", {}).get("current_date"),
            "seed": seed,
            "rounds": 1,
            "player_ask": {"aav_millions": float(offer.get("ask_millions") or 0.0)},
            "team_walkaway": {"source": "free_agency_day_market"},
            "offers": [contract_offer],
            "final_decision_id": decision["id"],
            "status": "agreement",
            "source_ids": ["src_contract_market_config_v1"],
            "notes": "Five-day free-agency market negotiation.",
        },
        "decision": decision,
        "accepted": True,
    }


def adjust_free_agent_asks(canonical: dict[str, Any], save_path: Path, seed: int) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    state = save.setdefault("free_agency_state", {})
    asks = state.setdefault("player_asks_millions", {})
    adjusted = 0
    for player_id in list(save.get("free_agent_player_ids", [])):
        active_offers = active_offers_for_player(save, player_id)
        if player_id not in asks:
            continue
        current = float(asks[player_id])
        if len(active_offers) >= 3:
            new_value = current * 1.04
        elif len(active_offers) == 0:
            new_value = current * 0.9
        else:
            new_value = current * 0.97
        new_value = round(max(1.6, min(65.0, new_value)), 1)
        if abs(new_value - current) >= 0.05:
            asks[player_id] = new_value
            adjusted += 1
    write_save(save_path, save)
    return {"ask_adjusted_count": adjusted}


def simulate_free_agency_to_end(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> dict[str, Any]:
    total_accepted = 0
    total_ai_trades = 0
    trade_news: list[dict[str, Any]] = []
    for _ in range(6):
        save = initialize_free_agency_market(canonical, save_path, user_team, seed)
        if (save.get("free_agency_state") or {}).get("status") == "completed":
            break
        result = advance_free_agency_day(canonical, save_path, user_team, seed)
        total_accepted += int(result.get("accepted_count") or 0)
        total_ai_trades += len(result.get("ai_trade_news") or [])
        trade_news.extend(result.get("ai_trade_news") or [])
    auto_fill = final_free_agency_roster_repair(canonical, save_path, seed)
    return {"accepted_count": total_accepted, "auto_fill_count": auto_fill.get("signed_count", 0), "ai_trade_count": total_ai_trades, "ai_trade_news": trade_news}


def final_free_agency_roster_repair(canonical: dict[str, Any], save_path: Path, seed: int) -> dict[str, Any]:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    next_start = int(str(save.get("meta", {}).get("season") or "2025-26").split("-")[0]) + 1
    next_season = f"{next_start}-{str(next_start + 1)[-2:]}"
    before_logs = len(save.get("transaction_logs", []))
    signed = auto_fill_rosters(canonical, save, list(save.get("free_agent_player_ids", [])), next_season, seed)
    save["free_agent_player_ids"] = [
        pid for pid in save.get("free_agent_player_ids", []) if pid not in signed and pid not in set(save.get("retired_player_ids", []))
    ]
    write_save(save_path, save)
    return {"signed_count": len(signed), "new_logs": len(save.get("transaction_logs", [])) - before_logs}


def queue_free_agency_suggestions(canonical: dict[str, Any], save_path: Path, seed: int) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or "2026-07-01"
    active = canonical_with_save(canonical, save)
    payload = simulate_free_agency(active, current, current, seed=seed, limit=12)
    save_pool = set(save.get("free_agent_player_ids", []))
    payload["negotiations"] = [
        item for item in payload.get("negotiations", [])
        if ((item.get("negotiation") or {}).get("player_id") in save_pool)
        or not next((p for p in active.get("players", []) if p.get("id") == (item.get("negotiation") or {}).get("player_id")), {}).get("team_id")
    ]
    payload["negotiations"] = [
        item for item in payload["negotiations"]
        if item.get("accepted") and positive_accepted_offer(item)
    ]
    payload["negotiation_count"] = len(payload["negotiations"])
    if not payload["negotiations"]:
        print("No accepted legal free-agent suggestions are available right now.")
        return
    save.setdefault("pending_ai_actions", []).append(
        {
            "id": stable_id("ai_action", "free_agency_manual", current, seed, len(save.get("pending_ai_actions", []))),
            "date": current,
            "action_type": "free_agency_recommendations",
            "status": "recommendation_pending_review",
            "payload": payload,
            "notes": "User-requested AI free-agency suggestion bundle.",
        }
    )
    write_save(save_path, save)
    print(f"Queued {payload.get('negotiation_count')} AI free-agency suggestions.")


def finish_free_agency_phase(canonical: dict[str, Any], save_path: Path) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    end_year = int(str(save.get("meta", {}).get("season") or "2025-26").split("-")[0]) + 1
    set_save_date_phase(save, f"{end_year}-09-01")
    save.setdefault("free_agency_state", {})["status"] = "completed"
    add_news(save, "free_agency", "Free agency period closed. Training camp is next.", date_value=f"{end_year}-09-01")
    write_save(save_path, save)
    print("Free agency complete. Training camp is next.")


def current_free_agents_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, allow_sign: bool) -> None:
    while True:
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = canonical_with_save(canonical, save)
        players = [
            player for player in active.get("players", [])
            if not player.get("team_id") or player.get("id") in set(save.get("free_agent_player_ids", []))
        ]
        retired = set(save.get("retired_player_ids", []))
        players = [player for player in players if player.get("id") not in retired]
        players.sort(
            key=lambda player: (
                float(player_attribute_summary(active, player["id"]).get("overall") or 0.0),
                display_minutes_projection(player),
                player.get("name", ""),
            ),
            reverse=True,
        )
        clear_screen()
        print_title("Current Free Agents")
        print("Signing is open before the trade deadline." if allow_sign else "View-only: free-agent signing is closed after the trade deadline.")
        team = resolve_team(active, user_team)
        print_cap_summary(active, save, team["id"], team_cap_summary(active, save, team["id"]))
        print_rule()
        if not players:
            print("No current free agents are available in this save.")
            wait()
            return
        print(" #  Player                     Pos Age OVR  MPG   PPG  RPG  APG  Ask")
        for idx, player in enumerate(players[:50], start=1):
            attrs = player_attribute_summary(active, player["id"])
            stats = active_season_line(save, player["id"], player)
            ask = max(1.8, display_minutes_projection(player) * 0.45)
            print(
                f"{idx:>2}. {player.get('name', ''):<26} {compact_position(player.get('position')):<3} {age_text(player, 3)} "
                f"{float(attrs.get('overall') or 0):>3.0f} {display_minutes_projection(player):>4.0f} "
                f"{stats['ppg']:>5.1f} {stats['rpg']:>4.1f} {stats['apg']:>4.1f} ${ask:>4.1f}M"
            )
        print(" 0. Back")
        choice = pick_number("Player", 0, min(50, len(players)), default=0)
        if choice == 0:
            clear_screen()
            return
        player = players[choice - 1]
        if not allow_sign:
            pause("Signing is closed after the trade deadline. This list is for scouting only.")
            continue
        years = pick_number("Years", 1, 2, default=1)
        default_aav = round(max(1.8, display_minutes_projection(player) * 0.45), 1)
        try:
            aav = float(input(f"AAV in millions [{default_aav}]: ").strip() or default_aav)
        except ValueError:
            aav = default_aav
        cap_check = signing_cap_check(active, save, user_team, aav)
        if not cap_check.get("ok"):
            pause(cap_check.get("message") or "Signing blocked by cap posture.")
            continue
        negotiation = manual_save_pool_signing(active, save_path, player, user_team, years, aav, seed)
        if negotiation.get("accepted"):
            result = apply_contract_to_save(save_path, negotiation["negotiation"]["id"], date=save.get("state", {}).get("current_date"))
            pause(f"Signing result: {result.get('status')}")
        else:
            pause("Player rejected the offer.")


def user_free_agent_signing(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    active = canonical_with_save(canonical, save)
    report = free_agents_report(active, team_query=user_team)
    save_pool = set(save.get("free_agent_player_ids", []))
    candidates = [
        item for item in report.get("candidates", [])
        if item.get("id") in save_pool or item.get("player_id") in save_pool or not next((p for p in active.get("players", []) if p.get("id") in {item.get("id"), item.get("player_id")}), {}).get("team_id")
    ][:20]
    print_title(f"Free Agents for {user_team}")
    if not candidates:
        print("No free-agent candidates available in the current contract model.")
        wait()
        return
    print(" #  Player                     Pos  OVR   PPG  RPG  APG  Fit   Ask")
    for idx, item in enumerate(candidates, start=1):
        player_id = item.get("id") or item.get("player_id")
        attrs = player_attribute_summary(active, player_id)
        stats = active_season_line(load_save(save_path), player_id)
        projected_aav = max(2.0, float(item.get("projected_aav_millions") or 0))
        print(
            f"{idx:>2}. {item['name']:<26} {item.get('position') or '-':<4} "
            f"{float(attrs.get('overall') or 0):>4.0f} "
            f"{stats['ppg']:>5.1f} {stats['rpg']:>4.1f} {stats['apg']:>4.1f} "
            f"{float(item.get('team_fit_score') or 0):>5.1f} ${projected_aav:>5.1f}M"
        )
    print(" 0. Back")
    choice = pick_number("Player", 0, len(candidates), default=0)
    if choice == 0:
        return
    player = candidates[choice - 1]
    years = pick_number("Years", 1, 5, default=min(3, int(player.get("max_years") or 3)))
    default_aav = max(2.0, float(player.get("projected_aav_millions") or 0))
    aav = float(input(f"AAV in millions [{default_aav}]: ").strip() or default_aav)
    cap_check = signing_cap_check(active, save, user_team, aav)
    if not cap_check["ok"]:
        pause(cap_check["message"])
        return
    evaluation = evaluate_signing(active, player["name"], user_team, years, aav, seed=seed)
    negotiation = user_signing_negotiation_from_evaluation(evaluation, player, user_team, seed)
    save = load_save(save_path)
    save.setdefault("pending_contract_negotiations", []).append(negotiation)
    write_save(save_path, save)
    print_title("Signing Evaluation")
    print(f"Accepted: {evaluation['accepted_by_all']} | Decision: {evaluation['decision']['decision']}")
    print(
        f"Scores: player {float(evaluation.get('decision', {}).get('player_score') or 0):.1f} "
        f"| team {float(evaluation.get('decision', {}).get('team_score') or 0):.1f} "
        f"| legality {evaluation.get('legality', {}).get('status')}"
    )
    print(f"Team fit: {float(player.get('team_fit_score') or 0):.1f} | projected ask ${float(player.get('projected_aav_millions') or 0):.1f}M")
    print(f"Reasons: {', '.join(evaluation['decision'].get('reasons', [])[:5])}")
    if evaluation["accepted_by_all"] and yes_no("Apply signing now?"):
        result = apply_contract_to_save(save_path, negotiation["negotiation"]["id"], date=save.get("state", {}).get("current_date"))
        print(f"Apply result: {result['status']}")
    wait()


def user_signing_negotiation_from_evaluation(evaluation: dict[str, Any], player: dict[str, Any], team_abbrev: str, seed: int) -> dict[str, Any]:
    offer = evaluation["offer"]
    player_id = player.get("id") or player.get("player_id") or offer["player_id"]
    negotiation_id = stable_id("contract_negotiation", "user_free_agent", team_abbrev, player_id, seed, offer["years"], round(float(offer["annual_salary"])))
    offer = {**offer, "id": stable_id("contract_offer", negotiation_id, "user")}
    decision = {**evaluation["decision"], "negotiation_id": negotiation_id, "accepted_offer": offer if evaluation["accepted_by_all"] else None}
    return {
        "negotiation": {
            "id": negotiation_id,
            "negotiation_type": "free_agent_signing",
            "player_id": player_id,
            "player_name": player.get("name"),
            "team_id": offer["team_id"],
            "date": "save_current_date",
            "seed": seed,
            "rounds": 1,
            "player_ask": {"source": "interactive_user_offer"},
            "team_walkaway": {"source": "interactive_user_offer"},
            "offers": [offer],
            "final_decision_id": decision["id"],
            "status": "agreement" if evaluation["accepted_by_all"] else "no_agreement",
            "source_ids": ["src_contract_market_config_v1"],
            "notes": "Interactive user free-agent negotiation.",
        },
        "decision": decision,
        "accepted": evaluation["accepted_by_all"],
    }


def positive_accepted_offer(item: dict[str, Any]) -> bool:
    offer = (item.get("decision") or {}).get("accepted_offer") or {}
    return bool(item.get("accepted")) and float(offer.get("annual_salary") or offer.get("aav") or 0) > 0


def active_season_line(save: dict[str, Any], player_id: str | None, player: dict[str, Any] | None = None) -> dict[str, float]:
    if not player_id:
        return {"ppg": 0.0, "rpg": 0.0, "apg": 0.0}
    stats = (save.get("player_season_stats") or {}).get(player_id, {})
    if not stats and player:
        return {
            "ppg": float(player.get("actual_points") or player.get("points") or 0.0),
            "rpg": float(player.get("actual_rebounds") or player.get("rebounds") or 0.0),
            "apg": float(player.get("actual_assists") or player.get("assists") or 0.0),
        }
    games = max(1, int(stats.get("games") or 0))
    return {
        "ppg": float(stats.get("points") or 0.0) / games,
        "rpg": float(stats.get("rebounds") or 0.0) / games,
        "apg": float(stats.get("assists") or 0.0) / games,
    }


def save_pool_free_agent_signing(
    canonical: dict[str, Any],
    save_path: Path,
    user_team: str,
    seed: int,
    player_filter_ids: set[str] | None = None,
    title: str = "Save Free-Agent Pool",
) -> None:
    players = print_save_free_agents(canonical, save_path, player_filter_ids=player_filter_ids, title=title)
    if not players:
        wait()
        return
    if not yes_no("Negotiate with one of these free agents?"):
        wait()
        return
    choice = pick_number("Player", 1, len(players), default=1)
    player = players[choice - 1]
    active = canonical_with_save(canonical, load_save(save_path))
    market = next((item for item in free_agents_report(active).get("candidates", []) if (item.get("id") or item.get("player_id")) == player.get("id")), {})
    print_free_agent_investigation(active, load_save(save_path), player, market, user_team)
    if not yes_no("Open contract talks?"):
        wait()
        return
    years = pick_number("Years", 1, 4, default=min(3, int(market.get("max_years") or 3)))
    default_aav = round(max(2.0, float(market.get("projected_aav_millions") or 0.0) or display_minutes_projection(player) * 0.45), 1)
    flexibility = free_agent_flexibility_score(active, player, market, user_team, seed)
    ask = default_aav
    final_offer = default_aav
    accepted_preview = False
    for round_no in range(1, 4):
        print_title(f"Free-Agent Negotiation | Round {round_no}/3")
        print(f"{player['name']} ask: ${ask:.1f}M x {years}")
        print(f"Flexibility {morale_bar(flexibility, width=16)}")
        suggested = round(max(1.5, ask * (0.92 if flexibility >= 65 else 0.98 if flexibility >= 40 else 1.03)), 1)
        try:
            final_offer = float(input(f"Offer AAV in millions [{suggested}]: ").strip() or suggested)
        except ValueError:
            final_offer = suggested
        if final_offer >= ask * (1.02 - flexibility / 260.0):
            accepted_preview = True
            break
        if round_no < 3:
            gap = max(0.0, ask - final_offer)
            ask = round(max(1.5, ask - min(gap * 0.35, ask * flexibility / 420.0)), 1)
            flexibility = round(max(5.0, flexibility - 6.0 + min(8.0, final_offer / max(ask, 1.0) * 4.0)), 1)
            print(f"Camp response: they are not there yet. New ask is around ${ask:.1f}M.")
    aav = final_offer
    cap_check = signing_cap_check(canonical_with_save(canonical, load_save(save_path)), load_save(save_path), user_team, aav)
    if not cap_check["ok"]:
        pause(cap_check["message"])
        return
    negotiation = manual_save_pool_signing(canonical, save_path, player, user_team, years, aav, seed)
    if accepted_preview and not negotiation["accepted"]:
        negotiation["accepted"] = True
        negotiation["decision"]["decision"] = "accept"
        negotiation["decision"]["accepted_offer"] = negotiation["negotiation"]["offers"][0]
        negotiation["negotiation"]["status"] = "agreement"
    print_title("Save-Pool Free Agent Negotiation")
    print(f"{player['name']} -> {user_team} | accepted={negotiation['accepted']}")
    print(f"Final ask read: ${ask:.1f}M | Offer: ${aav:.1f}M | Flexibility {flexibility:.0f}/100")
    if negotiation["accepted"] and yes_no("Apply signing now?"):
        result = apply_contract_to_save(save_path, negotiation["negotiation"]["id"], date=load_save(save_path).get("state", {}).get("current_date"))
        print(f"Apply result: {result['status']}")
    wait()


def print_free_agent_investigation(active: dict[str, Any], save: dict[str, Any], player: dict[str, Any], market: dict[str, Any], user_team: str) -> None:
    attrs = player_attribute_summary(active, player.get("id"))
    stats = active_season_line(save, player.get("id"), player)
    projected_aav = round(max(2.0, float(market.get("projected_aav_millions") or 0.0) or display_minutes_projection(player) * 0.45), 1)
    print_title(f"Free-Agent Investigation | {player.get('name')}")
    print(f"{compact_position(player.get('position'))} | age {age_text(player, 2)} | {height_text(player)} | {display_minutes_projection(player):.0f} projected MPG")
    print(f"Recent line: {stats['ppg']:.1f} PPG, {stats['rpg']:.1f} RPG, {stats['apg']:.1f} APG")
    print(f"Ask range: around ${projected_aav:.1f}M AAV | Fit with {user_team}: {float(market.get('team_fit_score') or 0):.1f}/100")
    print(f"Injury/durability flag: {free_agent_durability_flag(active, player)}")
    team = resolve_team(active, user_team)
    cap_season = contract_start_season_for_signing(save)
    print_cap_summary(active, save, team["id"], team_cap_summary(active, save, team["id"], season=cap_season))
    print_rule()
    print(
        f"OVR {rating_cell(float(attrs.get('overall') or 0), (50, 70))} "
        f"Shot {rating_cell(float(attrs.get('shooting') or 0), (50, 70))} "
        f"Create {rating_cell(float(attrs.get('creation') or 0), (50, 70))} "
        f"Def {rating_cell(float(attrs.get('defense') or 0), (50, 70))} "
        f"Reb {rating_cell(float(attrs.get('rebounding') or 0), (50, 70))}"
    )


def free_agent_flexibility_score(active: dict[str, Any], player: dict[str, Any], market: dict[str, Any], user_team: str, seed: int) -> float:
    age = float(player.get("age") or 27.0)
    fit = float(market.get("team_fit_score") or 50.0)
    years_pref = float(market.get("max_years") or 3)
    deterministic = (sum(ord(char) for char in f"{seed}:{user_team}:{player.get('id')}") % 21) - 10
    return round(max(8.0, min(92.0, 44.0 + (fit - 50.0) * 0.28 + max(0.0, age - 31) * 0.9 + years_pref * 2.2 + deterministic)), 1)


def free_agent_durability_flag(active: dict[str, Any], player: dict[str, Any]) -> str:
    player_id = player.get("id")
    profile = next((item for item in active.get("player_health_profiles", []) if item.get("player_id") == player_id), {})
    state = next((item for item in active.get("player_health_states", []) if item.get("player_id") == player_id), {})
    risk = player_health_risk(profile, state)
    durability = float(profile.get("durability") or 62.0)
    risk_ten = int(round(clamp(1.0 + risk / 34.0 * 9.0, 1.0, 10.0)))
    projected_games = int(round(clamp(82.0 - risk * 1.35 - max(0.0, 58.0 - durability) * 0.18, 38.0, 82.0)))
    status = str(state.get("availability_status") or "active").lower()
    current = bool(state.get("current_injury_id") or status not in {"", "active", "healthy"})
    if risk_ten >= 7:
        label = style("High", "danger")
    elif risk_ten >= 4:
        label = style("Medium", "accent")
    else:
        label = style("Low", "good")
    current_note = " | currently out" if current else ""
    if state.get("return_date") and current:
        current_note = f" | out until {state.get('return_date')}"
    return f"{label} ({risk_ten}/10, ~{projected_games} GP/yr{current_note})"


def injury_risk_text(value: float) -> str:
    if value >= 70:
        return style("High", "danger")
    if value >= 40:
        return style("Medium", "accent")
    if value > 0:
        return style("Low", "good")
    return "Unknown"


def print_save_free_agents(
    canonical: dict[str, Any],
    save_path: Path,
    player_filter_ids: set[str] | None = None,
    title: str = "Save Free-Agent Pool",
) -> list[dict[str, Any]]:
    save = load_save(save_path)
    active_canonical = canonical_with_save(canonical, save)
    active = {player["id"]: player for player in active_canonical.get("players", [])}
    report_by_id = {
        item.get("id") or item.get("player_id"): item
        for item in free_agents_report(active_canonical).get("candidates", [])
    }
    print_title(title)
    user_team_id = save.get("meta", {}).get("user_team_id")
    if user_team_id:
        cap = team_cap_summary(active_canonical, save, user_team_id)
        print_cap_summary(active_canonical, save, user_team_id, cap)
        print_rule()
    rows: list[tuple[float, dict[str, Any], dict[str, Any], dict[str, float], float, str]] = []
    player_ids = [
        player_id for player_id in save.get("free_agent_player_ids", [])
        if player_filter_ids is None or player_id in player_filter_ids
    ]
    for player_id in player_ids:
        player = active.get(player_id, {"id": player_id, "name": player_id, "position": "-"})
        attrs = player_attribute_summary(active_canonical, player_id)
        stats = active_season_line(save, player_id, player)
        market = report_by_id.get(player_id) or {}
        ask = round(max(2.0, float(market.get("projected_aav_millions") or 0.0) or display_minutes_projection(player) * 0.45), 1)
        desirability = float(attrs.get("overall") or 0) * 1.4 + float(stats["ppg"]) * 0.6 + display_minutes_projection(player) * 0.45 + ask * 0.25
        rows.append((desirability, player, attrs, stats, ask, player_trait_blurb(attrs)))
    rows.sort(key=lambda item: (-item[0], -item[4], item[1].get("name", "")))
    players = []
    print(" #  Player                     Pos  OVR   PPG  RPG  APG   Ask  Snapshot")
    for idx, (_, player, attrs, stats, ask, snapshot) in enumerate(rows[:50], start=1):
        players.append(player)
        print(
            f"{idx:>2}. {player.get('name', ''):<26} {compact_position(player.get('position')):<4} "
            f"{float(attrs.get('overall') or 0):>4.0f} "
            f"{stats['ppg']:>5.1f} {stats['rpg']:>4.1f} {stats['apg']:>4.1f} ${ask:>5.1f}M  {snapshot}"
        )
    if not players:
        print("No save-state free agents are currently available.")
    return players


def player_trait_blurb(attrs: dict[str, Any]) -> str:
    labels = [
        ("shooting", "shoot"),
        ("creation", "create"),
        ("defense", "def"),
        ("rim_deterrence", "rim"),
        ("passing", "pass"),
    ]
    top = sorted(labels, key=lambda item: float(attrs.get(item[0]) or 0), reverse=True)[:3]
    return ", ".join(f"{label} {float(attrs.get(key) or 0):.0f}" for key, label in top)


def print_free_agency_recap(canonical: dict[str, Any], save_path: Path) -> None:
    save = load_save(save_path)
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    players = {player["id"]: player for player in canonical_with_save(canonical, save).get("players", [])}
    season = str((save.get("free_agency_state") or {}).get("season") or save.get("meta", {}).get("season") or "2025-26")
    start_year = int(season.split("-")[0]) + 1
    offseason_start = f"{start_year}-06-01"
    offseason_end = f"{start_year}-10-01"
    target_start_season = f"{start_year}-{str(start_year + 1)[-2:]}"
    logs = [
        log for log in save.get("transaction_logs", [])
        if log.get("transaction_type") in {"free_agent_signing", "free_agency", "contract"}
        and (
            offseason_start <= str(log.get("date") or "") <= offseason_end
            or ((log.get("assets") or {}).get("contract") or {}).get("start_season") == target_start_season
        )
    ]
    print_title("Free Agency Recap")
    if not logs:
        print("No free-agent signings have been applied in this save yet.")
        return
    for log in logs[-20:]:
        assets = log.get("assets") or {}
        player = players.get(assets.get("player_id"), {"name": assets.get("player_id")})
        contract = assets.get("contract") or {}
        team = teams.get((contract or {}).get("team_id") or log.get("teams", [None])[0], {})
        print(
            f"{player.get('name')} -> {team.get('abbrev') or 'TEAM'} "
            f"${float(contract.get('annual_salary') or contract.get('aav') or 0)/1_000_000:.1f}M x {contract.get('years') or '?'}"
        )


def manual_save_pool_signing(canonical: dict[str, Any], save_path: Path, player: dict[str, Any], team_abbrev: str, years: int, aav_millions: float, seed: int) -> dict[str, Any]:
    team = resolve_team(canonical, team_abbrev)
    save_for_start = load_save(save_path)
    annual = float(aav_millions) * 1_000_000
    ask_threshold = max(1.9, display_minutes_projection(player) * 0.45)
    retirement_blocked = extension_retirement_blocked(player, contract_start_season_for_signing(save_for_start), years)
    accepted = aav_millions >= ask_threshold and not retirement_blocked
    negotiation_id = stable_id("contract_negotiation", "save_pool_fa", team["id"], player["id"], years, round(annual), seed)
    offer = {
        "id": stable_id("contract_offer", negotiation_id, "user"),
        "negotiation_id": negotiation_id,
        "team_id": team["id"],
        "player_id": player["id"],
        "offer_type": "free_agent_signing",
        "round": 1,
        "years": years,
        "start_season": contract_start_season_for_signing(save_for_start),
        "annual_salary": annual,
        "total_salary": annual * years,
        "role_promise": "rotation_compete",
        "status": "accepted" if accepted else "rejected",
        "notes": "Interactive save-pool free-agent offer.",
    }
    decision = {
        "id": stable_id("signing_decision", negotiation_id, player["id"]),
        "negotiation_id": negotiation_id,
        "player_id": player["id"],
        "team_id": team["id"],
        "accepted": accepted,
        "decision": "accept" if accepted else ("retirement_risk" if retirement_blocked else "reject_below_market"),
        "accepted_offer": offer if accepted else None,
        "player_score": round(aav_millions / max(ask_threshold, 0.1), 3),
        "team_score": 0.0,
        "competing_offers": [],
        "reasons": ["meets_save_pool_market" if accepted else ("retirement_before_contract_end" if retirement_blocked else "below_save_pool_market")],
        "ask_threshold_millions": round(ask_threshold, 2),
        "source_ids": ["src_contract_market_config_v1"],
        "notes": "Simplified save-pool free-agent decision for players whose contracts expired inside the save.",
    }
    negotiation = {
        "negotiation": {
            "id": negotiation_id,
            "negotiation_type": "free_agent_signing",
            "player_id": player["id"],
            "player_name": player.get("name"),
            "team_id": team["id"],
            "date": save_for_start.get("state", {}).get("current_date"),
            "seed": seed,
            "rounds": 1,
            "player_ask": {"ask_threshold_millions": round(ask_threshold, 2)},
            "team_walkaway": {"source": "interactive_save_pool_offer"},
            "offers": [offer],
            "final_decision_id": decision["id"],
            "status": "agreement" if accepted else "no_agreement",
            "source_ids": ["src_contract_market_config_v1"],
            "notes": "Interactive save-pool free-agent negotiation.",
        },
        "decision": decision,
        "accepted": accepted,
    }
    save = load_save(save_path)
    save.setdefault("pending_contract_negotiations", []).append(negotiation)
    write_save(save_path, save)
    return negotiation


def signing_cap_check(
    active: dict[str, Any],
    save: dict[str, Any],
    team_abbrev: str,
    aav_millions: float,
    allow_tax_exceed: bool = False,
    reserved_millions: float = 0.0,
) -> dict[str, Any]:
    team = resolve_team(active, team_abbrev)
    cap_season = contract_start_season_for_signing(save)
    cap = team_cap_summary(active, save, team["id"], season=cap_season)
    hard_space = float(cap.get("hard_cap_space_millions") or 0.0) - float(reserved_millions or 0.0)
    tax_space = float(cap.get("tax_space_millions") or 0.0) - float(reserved_millions or 0.0)
    minimum = league_minimum_aav_millions()
    if aav_millions <= minimum + 0.05:
        warning = ""
        if tax_space < aav_millions:
            warning = f" League-minimum exception used; tax room before offer is ${tax_space:.1f}M."
        return {"ok": True, "message": warning}
    if aav_millions > hard_space:
        return {
            "ok": False,
            "message": (
                f"Signing blocked: {team['abbrev']} has about ${hard_space:.1f}M under the hard cap "
                f"after active bids and this offer is ${aav_millions:.1f}M AAV. Clear salary or type {minimum:.1f} for the league minimum."
            ),
        }
    if not allow_tax_exceed and aav_millions > tax_space:
        return {
            "ok": False,
            "message": (
                f"Signing blocked: {team['abbrev']} has about ${tax_space:.1f}M below the tax after active bids, "
                f"and outside free-agent offers cannot exceed that room in this v1 ruleset. Type {minimum:.1f} for the league minimum."
            ),
        }
    warning = ""
    if aav_millions > tax_space:
        warning = f" This would move the team deeper into tax territory ({tax_space:+.1f}M tax room before offer)."
    return {"ok": True, "message": warning}


def league_minimum_aav_millions() -> float:
    return 1.9


def contract_start_season_for_signing(save: dict[str, Any]) -> str:
    season = str(save.get("meta", {}).get("season") or "2025-26")
    phase = str(save.get("state", {}).get("phase") or "")
    start = int(season.split("-")[0])
    if phase in {"draft_lottery", "draft", "free_agency"}:
        start += 1
    return f"{start}-{str(start + 1)[-2:]}"


def press_room(canonical: dict[str, Any], save_path: Path, user_team: str, seed: int, event: dict[str, Any] | None = None) -> None:
    team = user_team if event else (input(f"Team [{user_team}]: ").strip() or user_team)
    print_title("Press Conference")
    prompt = press_prompt(canonical, save_path, team, seed, event=event)
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    if save.get("narrative_settings", {}).get("enabled"):
        before_cache = json_cache_marker(save, "press")
        team_id = resolve_team(canonical, team)["id"]
        entry = press_cache_entry(canonical, save, team_id, event, prompt)
        prompt["reporters"] = [{**entry["reporter"], "answers": entry["answers"], "narrative_entry": entry}]
        prompt["narrative_entry"] = entry
        if json_cache_marker(save, "press") != before_cache:
            write_save(save_path, save)
    if len(prompt["reporters"]) == 1:
        reporter = prompt["reporters"][0]
    else:
        print("Choose a reporter.")
        for idx, reporter in enumerate(prompt["reporters"], start=1):
            print(f"{idx}. {reporter['name']}")
        reporter = prompt["reporters"][pick_number("Reporter", 1, len(prompt["reporters"]), default=1) - 1]
    question = reporter["question"]
    answer_rng = random.Random(f"{prompt.get('answer_seed')}:{reporter.get('name')}:{question}")
    answers = reporter.get("answers") or contextual_press_answers(prompt["topic"], prompt["team_abbrev"], prompt["player_name"], answer_rng, question=question)
    print_rule()
    print(f"{reporter['name']}: {question}")
    print("\nPick your answer.")
    for idx, answer in enumerate(answers, start=1):
        print(f"{idx}. \"{answer['line']}\"")
    answer = answers[pick_number("Answer", 1, len(answers), default=1) - 1]
    impact_seed = seed + int(deterministic_ratio(question, answer["line"], reporter["name"]) * 100000)
    result = hold_press_conference(canonical, save_path, team, prompt["topic"], answer["tone"], seed=impact_seed)
    result["question"] = question
    result["answer"] = answer["line"]
    save = load_save(save_path)
    if save.get("press_conferences"):
        save["press_conferences"][-1]["question"] = question
        save["press_conferences"][-1]["answer"] = answer["line"]
        save["press_conferences"][-1]["reporter"] = reporter
        save["press_conferences"][-1]["answer_choice"] = answer
        if prompt.get("narrative_entry"):
            save["press_conferences"][-1]["narrative"] = {
                "id": prompt["narrative_entry"].get("id"),
                "source": prompt["narrative_entry"].get("source"),
                "quality": answer.get("quality"),
                "rationale": answer.get("rationale"),
            }
        write_save(save_path, save)
    print_title("Press Room")
    print(f"Question: {result['question']}")
    print(f"Answer:   {result['answer']}")
    metrics = result.get("confidence_metrics") or {}
    before = metrics.get("before") or {}
    after = metrics.get("after") or {}
    print("\nReaction")
    print_metric_change("Team morale", before.get("team_morale"), after.get("team_morale"))
    print_metric_change("Fans", before.get("fan_confidence"), after.get("fan_confidence"))
    print_metric_change("Owner", before.get("owner_confidence"), after.get("owner_confidence"))
    wait()


def json_cache_marker(save: dict[str, Any], section: str) -> str:
    return str(hash(tuple(sorted((save.get("narrative_cache", {}).get(section, {}) or {}).keys()))))


def print_metric_change(label: str, before: Any, after: Any) -> None:
    before_value = float(before if before is not None else 50.0)
    after_value = float(after if after is not None else before_value)
    delta = after_value - before_value
    delta_text = style(f"{delta:+.1f}", "good" if delta >= 0 else "danger")
    print(f"{label:<12} {morale_bar(after_value)}  ({delta_text})")


def press_prompt(canonical: dict[str, Any], save_path: Path, team: str, seed: int, event: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = team_dashboard(Path("."), canonical, save_path, team)
    record = payload["record"]
    abbrev = payload["team"]["abbrev"]
    games = int(record.get("wins", 0)) + int(record.get("losses", 0))
    win_pct = float(record.get("wins", 0)) / max(1, games)
    rotation = payload.get("rotation", [])
    top_player = max(rotation, key=lambda item: float(item.get("points_per_game") or 0), default={"name": "your top option", "points_per_game": 0})
    hurt = next((row for row in rotation if row.get("health", {}).get("label")), None)
    pending = pending_actions_view(canonical, save_path)
    save = load_save(save_path)
    if event:
        topic = clean_press_context(event.get("kind") or event.get("headline") or "major team event")
        headline = clean_press_context(event.get("headline") or topic)
        core_question = clean_press_context(event.get("question")) if event.get("question") else contextual_event_question(abbrev, topic, headline)
    elif hurt:
        topic = f"{hurt['name']} injury"
        core_question = f"{hurt['name']} is listed as {hurt['health']['label']}. Are you protecting the player or asking the roster to push through it?"
    elif pending["pending_counts"].get("trades"):
        topic = "trade rumors"
        core_question = f"There are trade talks around the league. Are you committed to this {abbrev} group or still shopping for a shakeup?"
    elif games >= 10 and win_pct < 0.42:
        topic = "team performance"
        core_question = f"{abbrev} is under .500. Is this a patience situation, or have you misread the roster?"
    elif games >= 10 and win_pct > 0.60:
        topic = "playoff expectations"
        core_question = f"{abbrev} looks ahead of schedule. Are you ready to spend assets to chase this?"
    else:
        topic = f"{top_player['name']} role"
        core_question = f"{top_player['name']} is at {float(top_player.get('points_per_game') or 0):.1f} PPG. Is that the role you expected, or does the offense need changing?"
    recent_news = [item for item in save.get("news_items", []) if item.get("kind") not in {"game_result", "development", "press_conference"}][-4:]
    recent_context = headline if event else clean_press_context(recent_news[-1].get("headline")) if recent_news else f"{abbrev}'s current direction"
    press_count = len(save.get("press_conferences", []))
    event_key = (event or {}).get("id") or (event or {}).get("headline") or recent_context
    answer_seed = f"{seed}:{save.get('meta', {}).get('id')}:{abbrev}:{topic}:{event_key}:{press_count}"
    rng = random.Random(f"{answer_seed}:reporters")
    reporters = contextual_reporters(abbrev, topic, core_question, recent_context, top_player["name"], rng)
    return {"topic": topic, "reporters": reporters, "answer_seed": answer_seed, "team_abbrev": abbrev, "player_name": top_player["name"]}


def clean_press_context(value: Any) -> str:
    text = str(value or "").strip().rstrip(".")
    if not text:
        return "the current situation"
    text = text.replace("_", " ")
    text = text.replace("GM press conference:", "")
    text = text.replace("press conference:", "")
    while "(" in text and ")" in text:
        start = text.find("(")
        end = text.find(")", start)
        if end == -1:
            break
        text = (text[:start] + text[end + 1:]).strip()
    text = " ".join(text.split())
    if text.lower().startswith("staff hire"):
        return "the staff hire"
    if text.lower().startswith("staff fire"):
        return "the staff change"
    return text[:96]


def contextual_event_question(abbrev: str, topic: str, headline: str) -> str:
    low = f"{topic} {headline}".lower()
    if "staff" in low:
        return f"{headline}. What should fans expect to look different on the floor because of this staff change?"
    if "trade" in low:
        return f"{headline}. How do you defend the basketball logic if the fit takes time?"
    if "injury" in low:
        return f"{headline}. How aggressive should {abbrev} be in protecting the player versus protecting the standings?"
    if any(word in low for word in ["scandal", "fight", "drama"]):
        return f"{headline}. What line can this organization not allow anyone to cross?"
    if "free agent" in low or "signing" in low:
        return f"{headline}. What did this player choose here that another team could not offer?"
    return f"{headline}. What is the message to the locker room and the fans?"


def varied_reporter_question(reporter: dict[str, str], abbrev: str, topic: str, core_question: str, recent_context: str, player_name: str, rng: random.Random) -> str:
    low = topic.lower()
    beat = reporter.get("beat", "")
    base = reporter.get("question") or core_question
    if "injury" in low:
        variants = [
            base,
            f"What changes first for {abbrev}: the rotation, the style, or the urgency while this injury is unresolved?",
            f"Which player has to absorb the uncomfortable minutes now, and what happens if that player plays well?",
            f"Are you willing to sacrifice a game in November to protect a player you may need in April?",
            f"What is the part of this injury that fans are probably underestimating?",
        ]
    elif "trade" in low:
        variants = [
            base,
            f"Was the point of {recent_context} to raise the playoff ceiling, clean up the rotation, or protect the cap sheet?",
            f"You moved real assets. What did the roster lack badly enough to justify that cost?",
            f"If this deal squeezes someone out of the rotation, who has to adjust first?",
            f"Did you trade for the player, the contract slot, the pick math, or the lineup fit?",
            f"What should fans watch on the floor before they decide whether this trade worked?",
            f"Was this about helping the current core, or admitting the previous version had a ceiling?",
            f"How much did age and timeline drive the outgoing side of the trade?",
            f"You gave up future optionality. Why is the present-day basketball problem more urgent?",
            f"Is this the first move in a larger plan, or should the locker room read it as the move?",
            f"What did your scouts or coaches see in the incoming player that the public numbers might miss?",
            f"How do you keep the players who stayed from hearing this as a warning shot?",
            f"Did salary matching force the shape of the deal, or was every outgoing player part of the basketball logic?",
            f"When you trade a younger player for an older one, what has to happen quickly for that bet to age well?",
            f"When picks leave the building, what gives you confidence the roster can replace cheap depth later?",
            f"If the fit takes a month to settle, what is the non-negotiable standard during that stretch?",
            f"Was there a player you refused to include, and what does that say about the internal hierarchy?",
            f"How did the deadline market change what you thought this roster was worth?",
            f"What is the clearest risk you accepted in the trade, and why are you comfortable owning it?",
            f"If the next move never arrives, is this trade still enough to change the team’s direction?",
            f"What does this move say about the balance between talent, fit, and financial discipline for {abbrev}?",
        ]
    elif any(word in low for word in ["signing", "extension", "staff", "fired", "hired", "free agency"]):
        variants = [
            base,
            f"What has to be true a month from now for {recent_context} to look like the right call?",
            f"Who benefits most from this decision, and who has to adjust without making it a locker-room story?",
            f"Is this a short-window bet, or does it protect the next version of {abbrev}?",
            f"What did the cap sheet, role map, or staff room tell you that fans could not see from the headline?",
        ]
    elif any(word in low for word in ["losing", "performance", "under .500", "expectations"]):
        variants = [
            base,
            f"What is the first thing opponents are exposing against {abbrev}, and why has it not been solved yet?",
            f"Is this a team that needs patience, or a team that needs someone to lose minutes?",
            f"What would have to happen in the next two weeks for you to admit this roster needs a bigger change?",
            f"Who is responsible for the gap between what {abbrev} says it is and what the standings say it is?",
        ]
    else:
        variants = [
            base,
            f"How much of {player_name}'s current role is by design, and how much is the team just surviving possession to possession?",
            f"What is the clearest identity {abbrev} can lean on when the game gets ugly?",
            f"Which part of this roster are you most confident is real, and which part still needs proof?",
            f"If fans only watch the next five games, what should convince them the plan is actually taking shape?",
        ]
    if "cap" in beat:
        variants.append(f"What number on the cap sheet or asset ledger is quietly shaping this decision?")
    if "fan" in beat:
        variants.append(f"What would you say to fans who think the front office is selling patience because it has no better answer?")
    if "film" in beat:
        variants.append(f"What does the film show that the box score is hiding right now?")
    return variants[int(rng.random() * len(variants)) % len(variants)]


def contextual_reporters(abbrev: str, topic: str, core_question: str, recent_context: str, player_name: str, rng: random.Random) -> list[dict[str, str]]:
    low = topic.lower()
    if "injury" in low:
        pool = [
            {"name": "Dana Price", "beat": "locker-room accountability", "question": core_question},
            {"name": "Rhea Santos", "beat": "player roles and development", "question": f"Who absorbs the minutes if {topic} changes the rotation for more than a week?"},
            {"name": "Jules Hart", "beat": "film-room tactics", "question": f"What part of {abbrev}'s scheme becomes hardest to hold together while the injury situation is unresolved?"},
            {"name": "Omar Reed", "beat": "ownership expectations", "question": f"At what point does protecting health matter more than chasing standings position?"},
            {"name": "Tessa Vaughn", "beat": "fan temperature", "question": f"Fans hear 'next man up' constantly. Why should they believe this team has enough?"},
        ]
    elif any(word in low for word in ["trade", "signing", "extension", "staff", "fired", "hired"]):
        pool = [
            {"name": "Dana Price", "beat": "locker-room accountability", "question": core_question},
            {"name": "Miles Kwon", "beat": "transactions and cap pressure", "question": f"After {recent_context}, what is the basketball bet {abbrev} is making that fans may be missing?"},
            {"name": "Nina Calder", "beat": "long-term roster build", "question": f"Does this move protect future flexibility, or is {abbrev} accepting a tighter window?"},
            {"name": "Tessa Vaughn", "beat": "fan temperature", "question": f"Fans will judge the move fast. What should look different before the box score catches up?"},
            {"name": "Malik Rowe", "beat": "locker-room politics", "question": f"Whose role gets squeezed because of this decision, and how do you keep that from becoming a problem?"},
        ]
    elif any(word in low for word in ["losing", "performance", "under .500", "expectations"]):
        pool = [
            {"name": "Dana Price", "beat": "locker-room accountability", "question": core_question},
            {"name": "Omar Reed", "beat": "ownership expectations", "question": f"Ownership wants a clear read. What result would force you to admit the current {abbrev} plan needs to change?"},
            {"name": "Jules Hart", "beat": "film-room tactics", "question": f"When teams prepare for {abbrev}, what weakness are they attacking first?"},
            {"name": "Tessa Vaughn", "beat": "fan temperature", "question": f"Why should fans believe this is a bad stretch and not the real level of the team?"},
            {"name": "Malik Rowe", "beat": "locker-room politics", "question": f"Who inside the room has to sacrifice the most for this {abbrev} plan to work?"},
        ]
    else:
        pool = [
            {"name": "Dana Price", "beat": "locker-room accountability", "question": core_question},
            {"name": "Rhea Santos", "beat": "player roles and development", "question": f"How do you balance winning now with {player_name}'s role and the younger players behind him?"},
            {"name": "Jules Hart", "beat": "film-room tactics", "question": f"When teams prepare for {abbrev}, what are you worried they can take away first?"},
            {"name": "Tessa Vaughn", "beat": "fan temperature", "question": f"Fans hear the public message on {topic}. What should they believe is actually different tomorrow?"},
            {"name": "Nina Calder", "beat": "long-term roster build", "question": f"Are you protecting flexibility, or is this the moment where {abbrev} has to pick a direction?"},
        ]
    used_questions: set[str] = set()
    for reporter in pool:
        question = varied_reporter_question(reporter, abbrev, topic, core_question, recent_context, player_name, rng)
        attempts = 0
        while question in used_questions and attempts < 6:
            question = varied_reporter_question(reporter, abbrev, topic, core_question, recent_context, player_name, rng)
            attempts += 1
        reporter["question"] = question
        used_questions.add(question)
    rng.shuffle(pool)
    return pool[:4]


def contextual_press_answers(topic: str, abbrev: str, player_name: str, rng: random.Random, question: str | None = None) -> list[dict[str, str]]:
    low = topic.lower()
    question_low = (question or "").lower()
    context = f"{low} {question_low}"
    if any(word in context for word in ["injury", "returning", "health", "out"]):
        answers = [
            {"tone": "accountable", "line": f"We are not going to pretend this is business as usual. The first responsibility is protecting {player_name}, then building a rotation the group can trust."},
            {"tone": "accountable", "line": "The timeline got harder. That is not an excuse; it is a demand for cleaner roles and more disciplined minutes."},
            {"tone": "accountable", "line": "We owe the player patience and we owe the team clarity. Both things can be true at the same time."},
            {"tone": "optimistic", "line": "Nobody replaces a real player by committee perfectly, but this is where depth becomes more than a nice word on a whiteboard."},
            {"tone": "optimistic", "line": "The identity does not have to collapse because the rotation changes. The next man up has to simplify his job and win his minutes."},
            {"tone": "optimistic", "line": "There is opportunity here, but we are not turning a medical update into fake bravado. The work has to be patient and sharp."},
            {"tone": "challenge", "line": "These are not sympathy minutes. If someone wants a bigger role, this stretch is where he takes it."},
            {"tone": "challenge", "line": "The veterans have to steady the room now. The league will test us before anyone feels sorry for us."},
            {"tone": "deflect", "line": "The medical details stay with the medical group. Public timelines can do more harm than good."},
            {"tone": "deflect", "line": "I am not naming a replacement from the podium. Practice, film, and the games will tell us who deserves the trust."},
        ]
    elif (
        any(word in context for word in ["role", "minutes", "squeezed", "rotation", "bench", "starting"])
        and not any(word in context for word in ["cap", "staff", "trade", "signing", "extension", "asset", "flexibility"])
    ):
        answers = [
            {"tone": "accountable", "line": "If a role changes, we owe that player honesty before we owe the timeline a quote. The minutes have to match what helps us win."},
            {"tone": "accountable", "line": f"{player_name} deserves clarity, not public guessing. We will tell him exactly what the standard is and why."},
            {"tone": "accountable", "line": "The rotation cannot be political. If the minutes move, it has to be because the lineup data and the film agree."},
            {"tone": "optimistic", "line": "A squeezed role can still be a valuable role if the player knows what he is being asked to solve."},
            {"tone": "optimistic", "line": "This is where a good team turns competition into sharper habits instead of drama."},
            {"tone": "optimistic", "line": "The best version of this is not fewer opportunities; it is cleaner opportunities for the right players."},
            {"tone": "challenge", "line": "Nobody owns minutes because of reputation. Earn them, keep them, or the rotation moves."},
            {"tone": "challenge", "line": "If someone feels squeezed, the answer is to make the decision harder for the coach."},
            {"tone": "deflect", "line": "I am not going to manage the rotation through a microphone. That conversation belongs with the head coach and the player."},
            {"tone": "deflect", "line": "Roles are fluid. Turning that into a headline only makes the work less honest."},
        ]
    elif any(word in context for word in ["trade", "sign", "signing", "extension", "cap", "asset", "flexibility"]):
        answers = [
            {"tone": "accountable", "line": "We made a basketball bet, and the cost is part of the bet. If it fails, that is on us, not on a spreadsheet."},
            {"tone": "accountable", "line": "The cap sheet narrowed the path, but it did not make the decision for us. We chose the player and we own the constraints."},
            {"tone": "accountable", "line": "There is no free version of improving a team. We paid a price because standing still had a price too."},
            {"tone": "optimistic", "line": "This was not about winning the news cycle. It was about giving the roster a cleaner way to play."},
            {"tone": "optimistic", "line": "The fit matters more than the headline. If the role is right, the move should age better than the first reaction."},
            {"tone": "optimistic", "line": "We believe the upside is real, but the standard is not theoretical. It has to show up quickly."},
            {"tone": "challenge", "line": "This is not decorative. The expectation is urgency from the staff, the players, and the front office."},
            {"tone": "challenge", "line": "Any move changes jobs inside the locker room. That should sharpen people, not scare them."},
            {"tone": "deflect", "line": "I am not publishing our asset math. We know the cost, and now the job is making the cost worth it."},
            {"tone": "deflect", "line": "I know everyone wants an instant winner and loser. We care whether the decision still makes sense in May."},
        ]
    elif any(word in context for word in ["staff", "coach", "scheme", "floor", "voice"]):
        answers = [
            {"tone": "accountable", "line": "A staff move only matters if the habits change. The title is less important than what gets cleaned up possession by possession."},
            {"tone": "accountable", "line": "We needed a clearer voice in that seat. Now it is on us to make sure the message actually reaches the floor."},
            {"tone": "accountable", "line": "If the staff changes and the same mistakes stay, then we did not solve anything. That is the bar."},
            {"tone": "optimistic", "line": "This gives the group a more precise teacher, not just a new nameplate. That can matter over a long season."},
            {"tone": "optimistic", "line": "The hire is about fit with this roster. We think the daily work will look more connected."},
            {"tone": "optimistic", "line": "The best staff changes are visible in boring ways: better spacing, better matchups, fewer repeated mistakes."},
            {"tone": "challenge", "line": "A new voice is not a bailout. The players have to meet the work with urgency."},
            {"tone": "challenge", "line": "Nobody gets to hide behind the title on the door. Staff and players are on the same clock."},
            {"tone": "deflect", "line": "I will not compare staff members publicly. We made a decision about what this team needs next."},
            {"tone": "deflect", "line": "The internal review stays internal. The games will tell everyone whether the work changed."},
        ]
    elif any(word in context for word in ["losing", "performance", "under .500", "expectations", "streak", "pressure"]):
        answers = [
            {"tone": "accountable", "line": f"We have to own the record. {abbrev} needs cleaner possessions, clearer roles, and proof that the group can respond this week."},
            {"tone": "accountable", "line": f"The results are below our standard. {abbrev} has to defend harder, finish possessions, and stop asking the offense to solve everything."},
            {"tone": "accountable", "line": "The easy answer is patience. The honest answer is patience with consequences if the details do not improve."},
            {"tone": "optimistic", "line": "The standings are honest, but so is the film. There are fixable things here if the group accepts the details."},
            {"tone": "optimistic", "line": "I still see a path, but nobody is asking fans to grade us on a curve. The next stretch has to look sharper."},
            {"tone": "optimistic", "line": "A bad month does not erase the plan, but it does tell you which parts of the plan need pressure."},
            {"tone": "challenge", "line": "The standard is higher than this. Coaches, players, and the front office all have to respond with more force."},
            {"tone": "challenge", "line": "Minutes, roles, touches, all of it has to be earned. If the response is soft, the plan changes."},
            {"tone": "deflect", "line": "I am not handing out headlines after a bad stretch. The accountability is real, but it belongs in the room."},
            {"tone": "deflect", "line": "Public speculation cannot drive our decisions. The film and the people in the building will."},
        ]
    else:
        answers = [
            {"tone": "accountable", "line": f"We have to own the results. {abbrev} needs cleaner decisions, clearer roles, and a standard that shows up every night."},
            {"tone": "accountable", "line": "The talent is not the issue every night. The consistency is, and that falls on everyone who shapes the environment."},
            {"tone": "accountable", "line": "We can be patient without being vague. The next step needs to be visible, not just discussed internally."},
            {"tone": "optimistic", "line": f"We believe in {player_name} and the room. The answer is not panic; it is better execution and communication."},
            {"tone": "optimistic", "line": "There are real positives, but we are not going to confuse flashes with arrival. The next step is doing it again."},
            {"tone": "optimistic", "line": "This is still a group worth investing in, as long as the details keep catching up to the talent."},
            {"tone": "challenge", "line": "The standard is higher than this. Coaches, players, and the front office all have to respond with more force."},
            {"tone": "challenge", "line": "The league does not pause while you figure yourself out. Our response has to be more urgent than our explanation."},
            {"tone": "deflect", "line": "Those conversations stay inside the building. Public speculation cannot drive our decisions."},
            {"tone": "deflect", "line": "I understand the question, but we are not going to build a crisis out of one snapshot. We will handle the details."},
        ]
    rng.shuffle(answers)
    selected: list[dict[str, str]] = []
    tone_counts: dict[str, int] = {}
    for answer in answers:
        tone = answer.get("tone", "")
        if tone_counts.get(tone, 0) >= 2:
            continue
        selected.append(answer)
        tone_counts[tone] = tone_counts.get(tone, 0) + 1
        if len(selected) == 4:
            break
    if len(selected) < 4:
        for answer in answers:
            if answer not in selected:
                selected.append(answer)
            if len(selected) == 4:
                break
    rng.shuffle(selected)
    return selected[:4]


def print_dashboard(root: Path, canonical: dict[str, Any], save_path: Path, team: str, user_team: str | None = None, seed: int | None = None) -> None:
    while True:
        clear_screen()
        payload = team_dashboard(root, canonical, save_path, team)
        print_title(f"{payload['team']['abbrev']} Dashboard")
        r = payload["record"]
        cap = payload.get("cap_summary", {})
        print(f"{payload['current_date']} | {payload['phase']} | Record: {r['wins']}-{r['losses']}")
        print(
            f"Cap: ${cap.get('salary_total_millions', 0):.1f}M payroll | "
            f"tax room {cap.get('tax_space_pct', 0):+.1f}% (${cap.get('tax_space_millions', 0):+.1f}M) | "
            f"hard-cap room {cap.get('hard_cap_space_pct', 0):+.1f}% (${cap.get('hard_cap_space_millions', 0):+.1f}M)"
        )
        print(f"Health: {payload['health_summary']['unavailable_count']} unavailable | Avg fatigue {payload['health_summary']['average_fatigue']}")
        print_dashboard_overview(canonical, save_path, payload)
        print_rule()
        print("1. Rotation stats")
        print("2. Ratings / traits")
        print("3. Contracts")
        print("4. Development")
        print("5. Starting 5")
        if user_team and payload["team"]["abbrev"] == user_team:
            print("6. Talk rotation with head coach")
        print("0. Back")
        max_choice = 6 if user_team and payload["team"]["abbrev"] == user_team else 5
        choice = pick_number("Tab", 0, max_choice, default=0)
        if choice == 0:
            return
        if choice == 1:
            print_dashboard_rotation(payload)
        elif choice == 2:
            print_dashboard_ratings(payload)
        elif choice == 3:
            print_dashboard_contracts(canonical, save_path, payload, user_team=user_team, seed=seed)
        elif choice == 4:
            print_dashboard_development(canonical, save_path, payload)
        elif choice == 5:
            if user_team and payload["team"]["abbrev"] == user_team:
                starting_five_room(root, canonical, save_path, payload["team"]["abbrev"])
                continue
            print_dashboard_starting_five(payload)
        elif choice == 6 and user_team and payload["team"]["abbrev"] == user_team:
            minutes_room(canonical, save_path, user_team)
            continue
        wait()


def print_dashboard_overview(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> None:
    morale = morale_report(canonical, save_path, payload["team"]["abbrev"])
    print("\nMorale")
    print(f"Team  {morale_bar(morale.get('team_morale', {}).get('overall'))}")
    print(f"Fans  {morale_bar(morale.get('fan_confidence'))}")
    print(f"Owner {morale_bar(morale.get('owner_confidence'))}")
    print_team_identity(payload.get("team_identity") or {})
    if payload.get("starting_five"):
        print("\nStarting 5")
        print("   " + " | ".join(f"{row.get('slot')}. {row.get('player_name')}" for row in payload.get("starting_five", [])))
    print("\nRoster")
    stats_label = (payload.get("stats_context") or {}).get("label") or "Regular season"
    print(f"Stats: {stats_label}")
    print(" #  Player                   Pos Age   GP  Stats  Coach   PPG   RPG   APG  Health / coach")
    for idx, player in enumerate(payload["rotation"], start=1):
        injury = dashboard_health_text(player.get("health") or {})
        rec = player.get("minutes_recommendation")
        coach = f" | GM {float(rec.get('target_minutes') or 0):.0f} -> coach {float(player.get('coach_minutes_projection') or player.get('minutes_projection') or 0):.0f}" if rec else ""
        slot = f"{int(player.get('starting_slot'))}" if player.get("is_starting_five") else ""
        print(
            f"{slot or idx:>2}. {player['name']:<24} {compact_position(player.get('position')):<3} {age_text(player, 3)} {player.get('gp_display', '0/0'):>5} "
            f"{float(player.get('display_mpg') or 0):>6.0f} {float(player.get('coach_minutes_projection') or player.get('minutes_projection') or 0):>5.0f} {float(player.get('points_per_game') or 0):>5.1f} "
            f"{float(player.get('rebounds_per_game') or 0):>5.1f} {float(player.get('assists_per_game') or 0):>5.1f}  {injury}{coach}"
        )


def print_team_identity(identity: dict[str, Any]) -> None:
    metrics = identity.get("metrics") or {}
    ranks = identity.get("ranks") or {}
    league_count = int(identity.get("league_team_count") or 30)
    if not metrics:
        return
    print("\nTeam Identity")
    rows = [
        ("overall", "Overall"),
        ("offense", "Offense"),
        ("defense", "Defense"),
        ("spacing", "Spacing"),
        ("creation", "Creation"),
        ("rim_pressure", "Rim pressure"),
        ("rebounding", "Rebounding"),
        ("athleticism", "Athleticism"),
        ("defensive_disruption", "Disruption"),
        ("rim_protection", "Rim protection"),
        ("depth", "Depth"),
        ("age_timeline", "Age timeline"),
    ]
    for start in range(0, len(rows), 2):
        parts = []
        for key, label in rows[start:start + 2]:
            value = float(metrics.get(key) or 0.0)
            rank = ranks.get(key)
            rank_text = f"#{rank}/{league_count}" if rank else "--"
            parts.append(f"{label:<15} {rating_bar(value, width=12)} {value:>5.1f} {rank_text:<6}")
        print("   ".join(parts))
    if metrics.get("average_age") is not None:
        print(f"Average rotation age: {float(metrics.get('average_age') or 0):.1f}")


def print_dashboard_rotation(payload: dict[str, Any]) -> None:
    print_title("Rotation Stats")
    stats_label = (payload.get("stats_context") or {}).get("label") or "Regular season"
    print(f"Stats: {stats_label}")
    print(" #  Player                   Age   GP  Stats Coach   PPG   RPG   APG  STL  BLK   FG%   3PA   3P%  FTA   FT%  Health / coach")
    for idx, player in enumerate(payload["rotation"], start=1):
        rec = player.get("minutes_recommendation") or {}
        rec_text = f"GM {float(rec.get('target_minutes') or 0):.0f} -> {float(player.get('coach_minutes_projection') or player.get('minutes_projection') or 0):.0f}" if rec else ""
        status = dashboard_health_text(player.get("health") or {})
        slot = f"{int(player.get('starting_slot'))}" if player.get("is_starting_five") else str(idx)
        print(
            f"{slot:>2}. {player['name']:<24} {age_text(player, 3)} {player.get('gp_display', '0/0'):>5} {float(player.get('display_mpg') or 0):>6.0f} {float(player.get('coach_minutes_projection') or player.get('minutes_projection') or 0):>5.0f} "
            f"{float(player.get('points_per_game') or 0):>5.1f} {float(player.get('rebounds_per_game') or 0):>5.1f} "
            f"{float(player.get('assists_per_game') or 0):>5.1f} {float(player.get('steals_per_game') or 0):>4.1f} "
            f"{float(player.get('blocks_per_game') or 0):>4.1f} {pct_text(player.get('fg_pct')):>5} "
            f"{float(player.get('fg3a_per_game') or 0):>5.1f} {pct_text(player.get('fg3_pct')):>5} "
            f"{float(player.get('fta_per_game') or 0):>4.1f} {pct_text(player.get('ft_pct')):>5}  {status}{' | ' + rec_text if rec_text else ''}"
        )


def print_dashboard_starting_five(payload: dict[str, Any]) -> None:
    print_title("Starting 5")
    rows = payload.get("starting_five") or []
    if not rows:
        print("No lineup is available for this roster yet.")
        return
    for row in rows:
        print(f"{int(row.get('slot') or 0):>2}. {row.get('player_name'):<24} {compact_position(row.get('position')):<3}")
    print()
    print("Visualization only: this does not change sim minutes, morale, rotations, or coaching decisions.")


def starting_five_room(root: Path, canonical: dict[str, Any], save_path: Path, team_abbrev: str) -> None:
    while True:
        payload = team_dashboard(root, canonical, save_path, team_abbrev)
        clear_screen()
        print_dashboard_starting_five(payload)
        print_rule()
        print("1. Edit slot 1")
        print("2. Edit slot 2")
        print("3. Edit slot 3")
        print("4. Edit slot 4")
        print("5. Edit slot 5")
        print("6. Auto-fill from roster")
        print("0. Back")
        choice = pick_number("Starting 5", 0, 6, default=0)
        if choice == 0:
            return
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        active = canonical_with_save(canonical, save)
        team = resolve_team(active, team_abbrev)
        if choice == 6:
            save.setdefault("starting_lineups", {}).pop(team["id"], None)
            starting_lineup_slots(active, save, team["id"], persist=True)
            write_save(save_path, save)
            continue
        roster = [
            player for player in payload.get("rotation", [])
            if player.get("id")
        ]
        if not roster:
            pause("No roster players are available.")
            continue
        clear_screen()
        print_title(f"Choose Slot {choice}")
        for idx, player in enumerate(roster, start=1):
            marker = f"slot {player.get('starting_slot')}" if player.get("is_starting_five") else ""
            print(
                f"{idx:>2}. {player['name']:<24} {compact_position(player.get('position')):<3} "
                f"{float(player.get('coach_minutes_projection') or player.get('minutes_projection') or 0):>4.0f} min {marker}"
            )
        print(" 0. Back")
        player_choice = pick_number("Player", 0, len(roster), default=0)
        if player_choice == 0:
            continue
        selected_id = roster[player_choice - 1]["id"]
        lineups = save.setdefault("starting_lineups", {})
        current = lineups.setdefault(team["id"], {"slots": {}, "source": "user"})
        slots = {str(key): value for key, value in (current.get("slots") or {}).items()}
        for slot, player_id in list(slots.items()):
            if player_id == selected_id:
                slots.pop(slot, None)
        slots[str(choice)] = selected_id
        current["slots"] = slots
        current["source"] = "user"
        current["updated_date"] = save.get("state", {}).get("current_date")
        lineups[team["id"]] = current
        starting_lineup_slots(active, save, team["id"], persist=True)
        write_save(save_path, save)


def print_dashboard_ratings(payload: dict[str, Any]) -> None:
    columns = [
        ("overall", "OVR"),
        ("shooting", "Shot"),
        ("range", "Rng"),
        ("creation", "Cre"),
        ("handle", "Hdl"),
        ("rim_pressure", "Rim"),
        ("passing", "Pas"),
        ("rebounding", "Reb"),
        ("oreb", "OReb"),
        ("defense", "Def"),
        ("rim_deterrence", "RDet"),
        ("def_effort", "Eff"),
        ("screen_nav", "Nav"),
        ("iq", "IQ"),
        ("athleticism", "Ath"),
        ("stamina", "Sta"),
        ("portability", "Port"),
        ("playoff", "Ply"),
    ]
    print_title("Ratings / Traits")
    print("Sort by:")
    for idx, (_, label) in enumerate(columns, start=1):
        print(f"{idx}. {label}", end="  ")
        if idx % 9 == 0:
            print()
    print()
    sort_no = pick_number("Sort", 1, len(columns), default=1)
    sort_key = columns[sort_no - 1][0]
    rows = sorted(payload["rotation"], key=lambda player: float((player.get("attributes") or {}).get(sort_key) or 0), reverse=True)
    thresholds = rating_percentile_thresholds(rows, [key for key, _ in columns])
    print_title(f"Ratings / Traits | sort: {columns[sort_no - 1][1]}")
    print(f" #  {'Player':<22} {'Age':>3} {'Ht':<5} " + " ".join(f"{label:>5}" for _, label in columns))
    for idx, player in enumerate(rows, start=1):
        attrs = player.get("attributes") or {}
        print(
            f"{idx:>2}. {player['name']:<22} {age_text(player, 3)} {height_text(player):<5} "
            + " ".join(rating_cell(float(attrs.get(key) or 0), thresholds.get(key, (0.0, 0.0))) for key, _ in columns)
        )


def rating_percentile_thresholds(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, tuple[float, float]]:
    thresholds: dict[str, tuple[float, float]] = {}
    for key in keys:
        values = sorted(float((row.get("attributes") or {}).get(key) or 0.0) for row in rows)
        if not values:
            thresholds[key] = (0.0, 0.0)
            continue
        low_index = max(0, min(len(values) - 1, len(values) // 3))
        high_index = max(0, min(len(values) - 1, (len(values) * 2) // 3))
        thresholds[key] = (values[low_index], values[high_index])
    return thresholds


def rating_cell(value: float | None, thresholds: tuple[float, float] = (45.0, 65.0)) -> str:
    value = float(value or 0.0)
    low, high = thresholds
    kind = "danger" if value <= low else "good" if value >= high else "accent"
    return style(f"{value:>5.0f}", kind)


def print_dashboard_contracts(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any], user_team: str | None = None, seed: int | None = None) -> None:
    print_title("Contracts")
    season = payload.get("cap_summary", {}).get("season")
    seasons = contract_display_seasons(season)
    print(f" #  Player                   Age {seasons[0]:>10} {seasons[1]:>10} {seasons[2]:>10}")
    rows = sorted(payload["rotation"], key=lambda item: first_salary(item.get("salary_by_year") or {}, season), reverse=True)
    for idx, player in enumerate(rows, start=1):
        table = player.get("salary_by_year") or {}
        print(
            f"{idx:>2}. {player['name']:<24} {age_text(player, 3)} "
            f"{salary_cell(table.get(seasons[0])):>10} {salary_cell(table.get(seasons[1])):>10} {salary_cell(table.get(seasons[2])):>10}"
        )
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    team_abbrev = payload["team"]["abbrev"]
    if user_team and team_abbrev == user_team and "extensions" in legal_actions_for_current(save):
        print_rule()
        print("1. Navigate to extension talks")
        print("0. Back")
        choice = pick_number("Contracts", 0, 1, default=0)
        if choice == 1:
            extensions_room(canonical, save_path, team_abbrev, seed or int(save.get("meta", {}).get("seed") or 1))


def contract_display_seasons(current: str | None) -> list[str]:
    if current and "-" in current:
        try:
            start = int(current.split("-")[0])
            return [f"{year}-{str(year + 1)[-2:]}" for year in range(start, start + 3)]
        except ValueError:
            pass
    return ["2025-26", "2026-27", "2027-28"]


def salary_cell(value: Any) -> str:
    if value is None:
        return "-"
    return f"${float(value):.1f}M"


def dashboard_health_text(health: dict[str, Any]) -> str:
    if not health.get("label"):
        return style("Healthy", "good")
    days = float(health.get("days_left") or 0)
    return style(str(health.get("label")), "danger" if days >= 14 else "accent")


def print_dashboard_development(canonical: dict[str, Any], save_path: Path, payload: dict[str, Any]) -> None:
    save = load_save(save_path)
    active = canonical_with_save(canonical, save)
    roster_ids = {player["id"] for player in active.get("players", []) if player.get("team_id") == payload["team"]["id"]}
    players = {player["id"]: player for player in active.get("players", [])}
    events = [event for event in save.get("development_events", []) if event.get("player_id") in roster_ids]
    events.sort(key=lambda item: (item.get("month", item.get("date", "")), item.get("player_id", "")), reverse=True)
    print_title("Monthly Development")
    reviews = [
        item for item in save.get("year_reviews", [])
        if item.get("team_id") == payload["team"]["id"]
    ]
    reviews.sort(key=lambda item: item.get("generated_date", ""), reverse=True)
    if reviews:
        print_development_delta_matrix(f"Latest Year Review | {reviews[0].get('season')}", reviews[0].get("players") or [], players)
        print_rule()
    if not events:
        print("No monthly development events have been processed for this roster yet.")
        return
    latest_month = max(str(event.get("month") or event.get("date") or "")[:7] for event in events)
    latest_events = [event for event in events if str(event.get("month") or event.get("date") or "")[:7] == latest_month]
    print_development_delta_matrix(f"Latest Monthly Movement | {latest_month}", latest_events, players, show_date=True)


DEVELOPMENT_TRAIT_COLUMNS = [
    ("release_speed", "Rel"),
    ("shooting_range", "Rng"),
    ("shot_versatility", "Shot"),
    ("handle_pressure", "Hdl"),
    ("rim_pressure", "Rim"),
    ("passing_reads", "Pass"),
    ("offensive_rebounding", "OReb"),
    ("defensive_effort", "Eff"),
    ("foot_speed_lateral_agility", "Lat"),
    ("screen_navigation", "Nav"),
    ("rim_deterrence", "RDet"),
    ("scheme_iq", "IQ"),
    ("stamina_cardio", "Sta"),
    ("portability", "Port"),
    ("playoff_translation", "Ply"),
]


def print_development_delta_matrix(title: str, rows: list[dict[str, Any]], players: dict[str, dict[str, Any]], show_date: bool = False) -> None:
    if not rows:
        return
    print(style(title, "accent"))
    prefix = f"{'Date':<10} " if show_date else ""
    print(prefix + f"{'Player':<22} {'Age':>3} {'Net':>6} " + " ".join(f"{label:>5}" for _, label in DEVELOPMENT_TRAIT_COLUMNS))
    for row in rows:
        player = players.get(row.get("player_id"), {})
        name = row.get("name") or player.get("name") or row.get("player_id") or "-"
        age_value = row.get("age", player.get("display_age", player.get("age")))
        try:
            age = f"{float(age_value):>3.0f}" if age_value is not None else " --"
        except (TypeError, ValueError):
            age = " --"
        deltas = row.get("trait_deltas") or {}
        net = float(row.get("total_trait_delta") if row.get("total_trait_delta") is not None else sum(float(value or 0) for value in deltas.values()))
        date_text = f"{str(row.get('month') or row.get('date') or ''):<10} " if show_date else ""
        print(
            date_text
            + f"{str(name)[:22]:<22} {age} {delta_cell(net, width=6)} "
            + " ".join(delta_cell(float(deltas.get(key) or 0.0), width=5) for key, _ in DEVELOPMENT_TRAIT_COLUMNS)
        )


def delta_cell(value: float, width: int = 5) -> str:
    if abs(value) < 0.005:
        return style(".".rjust(width), "muted")
    return style(f"{value:+{width}.2f}", "good" if value > 0 else "danger")


def print_dashboard_staff(payload: dict[str, Any]) -> None:
    print_title("Staff")
    for slot in payload.get("staff_slots", []):
        contract = slot.get("contract") or {}
        print(f"{ROLE_LABELS.get(slot.get('slot'), slot.get('slot')):<22} {slot.get('name'):<24} ${float(contract.get('annual_salary_millions') or 0):.1f}M/{int(contract.get('years_remaining') or 0)}y")
        print(f"    {staff_role_effect(slot.get('slot'))}")


def first_salary(table: dict[str, Any], season: str | None) -> float:
    if not table:
        return 0.0
    if season and season in table:
        return float(table[season] or 0.0)
    return float(next((value for _, value in sorted(table.items()) if value is not None), 0.0) or 0.0)


def format_trait_deltas(deltas: dict[str, Any]) -> str:
    parts = []
    for key, value in sorted(deltas.items()):
        amount = float(value or 0)
        sign = "+" if amount >= 0 else ""
        text = f"{clean_label(key)} {sign}{amount:.2f}"
        parts.append(style(text, "good" if amount > 0.01 else "danger" if amount < -0.01 else "muted"))
    return " | ".join(parts[:4])


def pct_text(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.1f}"


def salary_summary(table: dict[str, Any], season: str | None) -> str:
    if not table:
        return "--"
    active_start = season_start_for_label(season)
    future_keys = [
        key for key in sorted(table)
        if active_start is None or season_start_for_label(key) is None or season_start_for_label(key) >= active_start
    ]
    keys = [season] if season and season in table else []
    keys.extend([key for key in future_keys if key not in keys][:2])
    if not keys:
        return "--"
    return " / ".join(f"{key[-5:]} ${float(table[key] or 0):.1f}M" for key in keys[:3])


def season_start_for_label(season: str | None) -> int | None:
    try:
        return int(str(season).split("-")[0])
    except (TypeError, ValueError):
        return None


def print_standings(canonical: dict[str, Any], save_path: Path) -> None:
    payload = league_standings(canonical, save_path)
    print_title(f"Standings as of {payload['as_of_date']}")
    for conf in ["East", "West"]:
        print(f"\n{style(conf, 'accent')}")
        rows = [row for row in payload["standings"] if row["team"].get("conference") == conf]
        rows.sort(key=lambda row: (-row["win_pct"], -row["point_diff"], row["team"]["abbrev"]))
        for idx, row in enumerate(rows, start=1):
            print(f"{idx:>2}. {row['team']['abbrev']:<3} {row['wins']:>2}-{row['losses']:<2}  pct {row['win_pct']:.3f}")


def print_leaders(canonical: dict[str, Any], save_path: Path, stat: str) -> None:
    payload = league_leaders(canonical, save_path, stat=stat, limit=15)
    stat_key = payload["stat"]
    print_title(f"League Leaders: {stat_key} /game")
    for idx, row in enumerate(payload["leaders"], start=1):
        print(f"{idx:>2}. {row['player'].get('name', ''):<28} {row.get('team_abbrev') or '':<3} {row.get(stat_key + '_per_game', 0):>5}/g  GP {row.get('games', 0):>2}  total {row.get(stat_key, 0):>6}")


def print_actions(canonical: dict[str, Any], save_path: Path) -> None:
    payload = pending_actions_view(canonical, save_path)
    players = {player["id"]: player for player in canonical.get("players", [])}
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    print_title(f"Pending Actions | {payload['current_date']} | {payload['phase']}")
    counts = payload.get("pending_counts") or {}
    count_text = " | ".join(
        f"{clean_label(key)} {value}"
        for key, value in counts.items()
        if key != "trades" and int(value or 0) > 0
    )
    print(count_text or "No pending items.")
    visible_actions = [action for action in payload["pending_ai_actions"] if ai_action_has_visible_content(action)]
    for action in visible_actions[:10]:
        print(f"\n{style(clean_label(action.get('action_type')), 'accent')}  {action.get('date')}  {clean_label(action.get('status'))}")
        payload_data = action.get("payload") or {}
        accepted_proposals = [
            proposal for proposal in payload_data.get("proposals", [])
            if proposal.get("accepted_by_all") and (proposal.get("legality") or {}).get("status") == "legal"
        ]
        for proposal in accepted_proposals[:5]:
            print(f"  Trade: {proposal_headline(proposal)}")
        for negotiation in [item for item in payload_data.get("negotiations", []) if positive_accepted_offer(item)][:5]:
            decision = negotiation.get("decision") or {}
            offer = decision.get("accepted_offer") or {}
            negotiation_payload = negotiation.get("negotiation", {})
            player = players.get(negotiation_payload.get("player_id") or decision.get("player_id"), {})
            team = teams.get(negotiation_payload.get("team_id") or decision.get("team_id"), {})
            print(f"  Signing: {player.get('name') or decision.get('player_id')} -> {team.get('abbrev') or decision.get('team_id')} | ${float(offer.get('annual_salary') or offer.get('aav') or 0)/1_000_000:.1f}M")
        for item in payload_data.get("recommendations", [])[:6]:
            current = item.get("current_staff") or {}
            candidate = item.get("candidate") or {}
            print(
                f"  Staff: {item.get('team_abbrev') or team_id_to_abbrev(item.get('team_id'))} "
                f"{ROLE_LABELS.get(item.get('slot'), item.get('slot'))} | "
                f"{current.get('name', 'current')} -> {candidate.get('name')}"
            )
    user_offers = [
        offer for offer in payload.get("user_trade_offers", [])
        if (offer.get("offer_context") or {}).get("status") == "pending_user_review"
    ]
    for offer in user_offers[:6]:
        print(f"\nAI offer: {proposal_headline(offer)} | {clean_label((offer.get('legality') or {}).get('status'))}")


def print_actions_result(result: dict[str, Any]) -> None:
    print_title("AI Processing")
    print(f"Processed: {result.get('processed_count')} | Applied: {result.get('applied_count')} | Execute: {result.get('execute')}")
    for item in result.get("processed", []):
        applied = item.get("applied_candidate_count")
        applied_text = f", {applied} applied" if applied is not None else ""
        print(f"{item.get('action_type')} -> {item.get('status')} ({item.get('accepted_candidate_count', 0)} accepted candidates{applied_text})")


def print_trade_result(result: dict[str, Any]) -> None:
    print_title("Trade Response")
    print(f"Stored: {result['pending_status']} | accepted_by_all={result.get('accepted_by_all')}")
    legality = result.get("legality") or {}
    print(f"Legality: {clean_label(legality.get('status'))}")
    if legality.get("issues"):
        print_legality_failures(legality)
    print_trade_acceptance_bars(result)
    if result.get("value_breakdown"):
        print_value_bars(result)
        print_asset_value_detail_bars(result)
    for evaluation in result.get("evaluations", []):
        print(f"{evaluation.get('team_abbrev') or evaluation.get('perspective_team_id')}: {evaluation.get('decision')} | net {evaluation.get('net_value')} | {', '.join(evaluation.get('reasons', [])[:3])}")


def print_trade_acceptance_bars(result: dict[str, Any]) -> None:
    evaluations = result.get("evaluations") or []
    if not evaluations:
        return
    print(style("Acceptance read", "accent"))
    for evaluation in evaluations:
        score = float(evaluation.get("acceptance_score") or 0.0)
        gap = float(evaluation.get("acceptance_gap") or 0.0)
        threshold = float(evaluation.get("acceptance_threshold") or 0.0)
        label = evaluation.get("team_abbrev") or team_id_to_abbrev(evaluation.get("perspective_team_id"))
        print(f"  {label:<3} {morale_bar(score, width=16)} gap {gap:+.1f} vs threshold {threshold:.1f}")


def print_legality_failures(legality: dict[str, Any]) -> None:
    issues = legality.get("issues") or []
    manual = legality.get("manual_review") or []
    if not issues and not manual:
        return
    print(style("Why this trade is blocked:", "danger"))
    for issue in issues:
        print(f"  - {issue}")
    for note in manual:
        print(f"  - Manual review: {note}")


def print_find_trade_report(report: dict[str, Any]) -> None:
    print_title("Find Trade")
    candidates = report.get("candidates", [])[:8]
    if not candidates:
        print("No legal executable offers came back. That can happen if the market sees the player differently than your team does.")
        return
    for idx, candidate in enumerate(candidates, start=1):
        print(f"{idx:>2}. {proposal_headline(candidate)}")
        print(f"    legality={candidate.get('legality', {}).get('status')} | AI side should accept: {partner_accepts(candidate, report.get('for_team', {}).get('id'))}")
        print_value_bars(candidate)


def trade_finder_followup(canonical: dict[str, Any], report: dict[str, Any], save_path: Path) -> None:
    candidates = report.get("candidates", [])[:8]
    if not candidates:
        return
    print_rule()
    print("Pick an offer to act on, or 0 to go back.")
    choice = pick_number("Offer", 0, len(candidates), default=0)
    if choice == 0:
        return
    candidate = trade_candidate_with_current_asset_labels(canonical, candidates[choice - 1])
    while True:
        clear_screen()
        print_title("Trade Offer")
        print(proposal_headline(candidate))
        print_value_bars(candidate)
        print_rule()
        print("1. Inspect value, contracts, fit, and GM response")
        print("2. Accept and execute")
        print("3. Keep as pending/counter scaffold")
        print("4. Reject")
        print("0. Back")
        action = pick_number("Action", 0, 4, default=0)
        if action == 0:
            clear_screen()
            return
        if action != 1:
            break
        clear_screen()
        print_trade_offer_details(canonical, candidate, save_path)
        wait()
    if action == 2:
        save = load_save(save_path)
        if candidate.get("legality", {}).get("status") != "legal":
            pause("Trade blocked: this offer is not legal anymore.")
            return
        candidate = attach_pick_terms_to_trade(canonical, save_path, candidate)
        candidate = accept_trade_finder_offer(candidate, (report.get("for_team") or {}).get("id"))
        if not candidate:
            pause("Trade blocked: the other team no longer has an active approval for this offer.")
            return
        save.setdefault("pending_trade_proposals", []).append(candidate)
        write_save(save_path, save)
        result = apply_trade_to_save(save_path, candidate["proposal"]["id"], date=save.get("state", {}).get("current_date"))
        print(f"Trade apply result: {result.get('status')}")
    elif action == 3:
        save = load_save(save_path)
        candidate = attach_pick_terms_to_trade(canonical, save_path, candidate)
        scaffold = {**candidate, "offer_context": {"status": "counter_scaffold", "created_date": save.get("state", {}).get("current_date")}}
        save.setdefault("pending_trade_proposals", []).append(scaffold)
        write_save(save_path, save)
        print("Offer saved in pending actions as a counter scaffold.")
    else:
        print("Offer rejected.")


def print_trade_offer_details(canonical: dict[str, Any], candidate: dict[str, Any], save_path: Path | None = None) -> None:
    save = load_save(save_path) if save_path else {}
    if save:
        canonical = canonical_with_save(canonical, ensure_league_save_defaults(save, canonical))
    canonical = with_transaction_context(canonical)
    candidate = trade_candidate_with_current_asset_labels(canonical, candidate)
    proposal = candidate.get("proposal") or {}
    teams = {team["id"]: team for team in canonical.get("teams", [])}
    players = {player["id"]: player for player in canonical.get("players", [])}
    values = {item["player_id"]: item for item in canonical.get("player_asset_valuations", [])}
    season_stats = save.get("player_season_stats", {})
    season = contract_start_season_for_signing(save) if save else None
    print_title("Trade Inspection")
    print(proposal_headline(candidate))
    print_rule()
    print_value_bars(candidate)
    print_asset_value_detail_bars(candidate)
    for team_id, assets in [
        (proposal.get("from_team_id"), proposal.get("to_assets", [])),
        (proposal.get("to_team_id"), proposal.get("from_assets", [])),
    ]:
        abbrev = teams.get(team_id, {}).get("abbrev", team_id)
        print_rule()
        print(style(f"{abbrev} receives", "accent"))
        for asset in assets:
            if asset.get("kind") == "pick":
                print(f"  {style('PICK', 'value_pick'):<8} {asset.get('label') or clean_label(asset.get('id'))}")
                continue
            if asset.get("kind") == "pick_swap":
                print(f"  {style('SWAP', 'value_pick'):<8} {asset.get('label') or clean_label(asset.get('id'))}")
                continue
            player = players.get(asset.get("id"), {})
            value = values.get(asset.get("id"), {})
            attrs = player_attribute_summary(canonical, asset.get("id"))
            totals = season_stats.get(asset.get("id"), {})
            contract_years = salary_summary(player_salary_table(canonical, asset.get("id")), season)
            trade_value = market_trade_target_value(player, value or fallback_asset_valuation(player))
            print(
                f"  {style(player.get('name', asset.get('label')), 'accent'):<24} "
                f"{compact_position(player.get('position')):<3} age {age_text(player, 2)} ht {height_text(player):<5} | "
                f"Value {single_value_bar(trade_value, scale=100, width=12)} {trade_value:>5.1f}"
            )
            print(
                f"      Role: {display_minutes_projection(player):>2.0f} MPG | "
                f"{per_game_from_totals(totals, 'points'):>4.1f} PPG, {per_game_from_totals(totals, 'rebounds'):>4.1f} RPG, "
                f"{per_game_from_totals(totals, 'assists'):>4.1f} APG"
            )
            print(
                f"      Ratings: OVR {float(attrs.get('overall') or 0):>4.0f} | shoot {float(attrs.get('shooting') or 0):>4.0f} | "
                f"create {float(attrs.get('creation') or 0):>4.0f} | defense {float(attrs.get('defense') or 0):>4.0f} | "
                f"rebound {float(attrs.get('rebounding') or 0):>4.0f} | health risk {float(value.get('health_risk') or 0):>4.1f}"
            )
            print(f"      Contract: {contract_years or 'unresolved'}")
    print_rule()
    print(style("GM responses", "accent"))
    for evaluation in candidate.get("evaluations", []):
        team_id = evaluation.get("perspective_team_id")
        abbrev = teams.get(team_id, {}).get("abbrev", team_id)
        acceptance = float(evaluation.get("acceptance_score") or 0.0)
        print(f"  {abbrev:<3} {morale_bar(acceptance, width=14)} {clean_label(evaluation.get('decision'))} | net {float(evaluation.get('net_value') or 0):+.1f}")
        print(f"    {evaluation.get('notes')}")
    legality = candidate.get("legality") or {}
    print_rule()
    print(f"Legality: {clean_label(legality.get('status'))}")
    for issue in legality.get("issues", []):
        print(f"  - {issue}")


def partner_accepts(candidate: dict[str, Any], user_team_id: str | None) -> str:
    for evaluation in candidate.get("evaluations", []):
        if evaluation.get("perspective_team_id") != user_team_id:
            decision = str(evaluation.get("decision") or "").lower()
            return "yes" if evaluation.get("accepted") or decision in {"accept", "accepted", "yes"} else "no"
    return "unknown"


def difficulty_filter_trade_candidates(candidates: list[dict[str, Any]], difficulty: str, user_team_id: str | None) -> list[dict[str, Any]]:
    user_win_limit = {"easy": 34.0, "normal": 26.0, "hard": 12.0}.get(str(difficulty or "normal"), 26.0)
    filtered = []
    for candidate in candidates:
        user_eval = next((item for item in candidate.get("evaluations", []) if item.get("perspective_team_id") == user_team_id), {})
        if float(user_eval.get("net_value") or 0.0) <= user_win_limit:
            filtered.append(candidate)
    return filtered


def remove_inferior_superset_trade_candidates(candidates: list[dict[str, Any]], user_team_id: str | None) -> list[dict[str, Any]]:
    if not user_team_id:
        return candidates
    kept: list[dict[str, Any] | None] = []
    metadata: list[dict[str, Any] | None] = []
    for candidate in candidates:
        proposal = candidate.get("proposal") or {}
        if proposal.get("from_team_id") == user_team_id:
            incoming = proposal.get("to_assets") or []
            outgoing = proposal.get("from_assets") or []
            counterparty = proposal.get("to_team_id")
        elif proposal.get("to_team_id") == user_team_id:
            incoming = proposal.get("from_assets") or []
            outgoing = proposal.get("to_assets") or []
            counterparty = proposal.get("from_team_id")
        else:
            kept.append(candidate)
            metadata.append(None)
            continue
        incoming_keys = frozenset(proposal_asset_identity_keys({"from_assets": incoming}))
        outgoing_keys = frozenset(proposal_asset_identity_keys({"from_assets": outgoing}))
        signature = (counterparty, incoming_keys)
        skip = False
        for idx, item in enumerate(metadata):
            if not item or item["signature"] != signature:
                continue
            existing_outgoing = item["outgoing"]
            if existing_outgoing <= outgoing_keys:
                skip = True
                break
            if outgoing_keys < existing_outgoing:
                kept[idx] = None
                metadata[idx] = None
        if skip:
            continue
        kept.append(candidate)
        metadata.append({"signature": signature, "outgoing": outgoing_keys})
    return [candidate for candidate in kept if candidate is not None]


def print_value_bars(candidate: dict[str, Any]) -> None:
    breakdown = candidate.get("value_breakdown") or {}
    proposal = candidate.get("proposal") or {}
    labels = [
        ("from_team_receives", f"{team_id_to_abbrev(proposal.get('from_team_id'))} receives"),
        ("to_team_receives", f"{team_id_to_abbrev(proposal.get('to_team_id'))} receives"),
    ]
    for key, label in labels:
        pieces = breakdown.get(key) or {}
        total = float(pieces.get("total") or 0)
        print(f"    {label:<15} {segmented_bar(pieces, scale=110)} {total:>5.1f}")
        compact = " | ".join(
            f"{style(short_value_label(name), value_style(name))} {float(value):+.1f}"
            for name, value in pieces.items()
            if name not in {"total", "asset_details"} and isinstance(value, (int, float)) and abs(float(value or 0)) >= 0.4
        )
        if compact:
            print(f"      {compact}")
    has_pick_detail = any(
        str(item.get("expected_role") or "").lower() == "draft_asset"
        or str(item.get("id") or "").startswith("pick_")
        for side in breakdown.values()
        for item in ((side or {}).get("asset_details") or [])
        if isinstance(side, dict)
    )
    if has_pick_detail:
        print("      Pick note: trade response values use the receiving team's package context; asset lists use current-owner context.")


def print_asset_value_detail_bars(candidate: dict[str, Any]) -> None:
    breakdown = candidate.get("value_breakdown") or {}
    proposal = candidate.get("proposal") or {}
    labels = [
        ("from_team_receives", f"{team_id_to_abbrev(proposal.get('from_team_id'))} receives"),
        ("to_team_receives", f"{team_id_to_abbrev(proposal.get('to_team_id'))} receives"),
    ]
    for key, label in labels:
        details = (breakdown.get(key) or {}).get("asset_details") or []
        if not details:
            continue
        print(f"      {label} asset pieces")
        for item in details[:6]:
            adjusted = float(item.get("adjusted_value") or 0.0)
            raw = float(item.get("raw_value") or 0.0)
            multiplier = float(item.get("role_multiplier") or 1.0)
            print(
                f"        {str(item.get('label') or item.get('id')):<24} "
                f"{single_value_bar(adjusted, scale=90, width=14)} {adjusted:>5.1f} "
                f"(raw {raw:.1f}, role {multiplier:.2f}x {clean_label(item.get('expected_role'))})"
            )


def short_value_label(name: str) -> str:
    return {
        "player_quality": "quality",
        "role_value": "role",
        "age_timeline": "age",
        "contract": "contract",
        "lineup_fit": "fit",
        "health": "health",
        "pick_value": "picks",
        "cap_roster": "cap",
        "concentration": "top-end",
        "gm_modifier": "GM",
    }.get(name, clean_label(name))


def value_style(name: str) -> str:
    return {
        "player_quality": "value_quality",
        "role_value": "value_role",
        "age_timeline": "value_age",
        "contract": "value_contract",
        "lineup_fit": "value_fit",
        "health": "value_health",
        "pick_value": "value_pick",
        "cap_roster": "value_cap",
        "concentration": "value_role",
        "gm_modifier": "value_gm",
    }.get(name, "accent")


def segmented_bar(pieces: dict[str, Any], scale: float = 100.0, width: int = 22) -> str:
    order = ["player_quality", "role_value", "age_timeline", "contract", "lineup_fit", "health", "pick_value", "cap_roster", "concentration", "gm_modifier"]
    positives = [(key, max(0.0, float(pieces.get(key) or 0.0))) for key in order]
    positive_total = sum(value for _, value in positives)
    total = max(0.0, float(pieces.get("total") or 0.0))
    ghost_width = min(width, int(round(positive_total / max(scale, 1.0) * width)))
    actual_width = min(ghost_width, int(round(total / max(scale, 1.0) * width)))
    chars: list[str] = []
    used = 0
    for key, value in positives:
        if value <= 0 or used >= actual_width:
            continue
        length = int(round(value / max(positive_total, 1.0) * max(actual_width, 1)))
        length = max(1, min(length, actual_width - used))
        chars.append(style("█" * length, value_style(key)))
        used += length
    if used < actual_width:
        chars.append(style("█" * (actual_width - used), "accent"))
    if ghost_width > actual_width:
        chars.append(style("░" * (ghost_width - actual_width), "muted"))
    empty = "." * (width - max(ghost_width, actual_width))
    return "[" + "".join(chars) + empty + "]"


def single_value_bar(value: float, scale: float = 100.0, width: int = 16) -> str:
    filled = max(0, min(width, int(round(max(0.0, value) / max(scale, 1.0) * width))))
    return "[" + style("█" * filled, "value_quality") + style("." * (width - filled), "muted") + "]"


def bar(value: float, scale: float = 100.0, width: int = 22) -> str:
    value = max(0.0, float(value))
    filled = max(0, min(width, int(round(value / max(scale, 1.0) * width))))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def proposal_headline(candidate: dict[str, Any]) -> str:
    summary = candidate.get("summary")
    if isinstance(summary, dict):
        return str(summary.get("headline") or candidate.get("proposal", {}).get("id") or candidate.get("id") or "Trade idea")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    proposal = candidate.get("proposal") or {}
    return str(proposal.get("id") or candidate.get("id") or "Trade idea")


def team_id_to_abbrev(team_id: str | None) -> str:
    if not team_id:
        return "Team"
    return str(team_id).replace("team_", "").upper()


def print_staff(canonical: dict[str, Any], save_path: Path, team: str) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    report = staff_team_report(canonical, save, team)
    pending_slots = {
        item.get("slot")
        for item in save.get("staff_retention_windows", [])
        if item.get("team_id") == report["team"]["id"] and item.get("status") == "pending_user_decision"
    }
    print_title(f"{report['team']['abbrev']} Staff")
    budget = report.get("budget") or {}
    print(
        f"Staff spend: ${budget.get('annual_spend_millions', 0):.1f}M / "
        f"${budget.get('annual_budget_millions', 0):.1f}M budget "
        f"({budget.get('available_millions', 0):+.1f}M available)"
    )
    print("\nRole                    Name                     Grade  Contract      Archetype")
    for slot in report["gameplay_staff_slots"]:
        label = ROLE_LABELS.get(slot["slot"], slot["slot"])
        if slot.get("slot") in pending_slots:
            print(f"\n{label:<23} {'-- open --':<24} {'--':>5}  {'--':<13} {'pending re-signing'}")
            print(f"    Role: {staff_role_effect(slot['slot'])}")
            continue
        contract = slot.get("contract") or {}
        contract_text = f"${float(contract.get('annual_salary_millions') or 0):.1f}M/{int(contract.get('years_remaining') or 0)}y"
        interim = slot.get("status") == "interim_staff_vacancy" or contract.get("guarantee_level") == "interim"
        name = f"{slot['name']} (interim)" if interim else slot["name"]
        print(f"\n{label:<23} {name:<24} {slot['grade']:>5.1f}  {contract_text:<13} {clean_label(slot['archetype'])}")
        print(f"    Role: {staff_role_effect(slot['slot'])}")
        for row in slot.get("effect_rows") or []:
            print_staff_effect_row(row)


def print_staff_market(canonical: dict[str, Any], save_path: Path, slot: str | None) -> None:
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    report = staff_market_report(canonical, save, slot=slot, limit=20)
    print_title(f"{ROLE_LABELS.get(slot, slot) if slot else 'All Staff'} Market")
    for idx, candidate in enumerate(report["candidates"], start=1):
        print(
            f"{idx:>2}. {ROLE_LABELS.get(candidate['slot'], candidate['slot']):<21} {candidate['name']:<22} grade {candidate['grade']:>5.1f} | "
            f"{clean_label(candidate['archetype'])} | ask ${candidate.get('asking_salary_millions', 0):.1f}M/{candidate.get('asking_years')}y"
        )
    if slot:
        print(f"\nRole effect: {staff_role_effect(slot)}")


def print_staff_effect_row(row: dict[str, Any]) -> None:
    value = float(row.get("value") or 0.0)
    label = str(row.get("label") or "Impact")
    description = str(row.get("description") or "")
    stars = row.get("stars")
    if stars is not None:
        star_text = f"{float(stars):.1f} star eq"
    else:
        star_text = f"{value:.1f}/100"
    print(f"    {label:<20} {rating_bar(value, width=18)} {star_text:>11}  {description}")


def rating_bar(value: float, width: int = 18) -> str:
    value = clamp_to_display(value)
    filled = max(0, min(width, int(round(value / 100.0 * width))))
    style_name = "good" if value >= 72 else "accent" if value >= 48 else "danger"
    return "[" + style("#" * filled, style_name) + style("." * (width - filled), "muted") + "]"


def clamp_to_display(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def print_social_and_morale(canonical: dict[str, Any], save_path: Path, team: str) -> None:
    while True:
        morale = morale_report(canonical, save_path, team)
        team_record = morale["team"]
        clear_screen()
        print_title(f"{team_record['abbrev']} Morale + Social")
        team_morale = morale.get("team_morale") or {}
        print(f"Team morale  {morale_bar(team_morale.get('overall'))}")
        print(f"Chemistry    {morale_bar(team_morale.get('chemistry'))}")
        print(f"Confidence   {morale_bar(team_morale.get('confidence'))}")
        print(f"Fans         {morale_bar(morale.get('fan_confidence'))}")
        print(f"Owner        {morale_bar(morale.get('owner_confidence'))}")
        print("\nLowest player morale")
        for row in morale["players"][:6]:
            m = row.get("morale") or {}
            print(f"{row['player'].get('name', ''):<28} {morale_bar(m.get('overall'))} role {morale_bar(m.get('role_satisfaction'), width=10)}")
        print_rule()
        print("1. Team-related timeline")
        print("2. Biggest league-wide timeline")
        print("0. Back")
        choice = pick_number("Social", 0, 2, default=1)
        if choice == 0:
            clear_screen()
            return
        save = load_save(save_path)
        limit = social_timeline_limit(save)
        if choice == 1:
            items = team_social_items(save, team_record["id"], team_record["abbrev"], limit=limit)
            title = f"{team_record['abbrev']} Timeline"
        else:
            items = league_social_items(save, team_record["id"], limit=limit)
            title = "Biggest League-Wide Timeline"
        items, changed = hydrate_social_items(canonical_with_save(canonical, save), save, items, team_id=team_record["id"])
        if changed:
            write_save(save_path, save)
        clear_screen()
        print_title(title)
        if not items:
            print("No posts match this view yet.")
        for item in items:
            for line in social_timeline_lines(item):
                print(line)
        wait()


def social_timeline_limit(save: dict[str, Any]) -> int:
    settings = save.get("narrative_settings") or {}
    if settings.get("enabled"):
        return int(max(1, min(24, int(settings.get("max_posts_per_view") or 12))))
    return 24


def team_social_items(save: dict[str, Any], team_id: str, abbrev: str, limit: int = 20) -> list[dict[str, Any]]:
    items = []
    for item in save.get("social_feed", []):
        text = f"{item.get('text', '')} {item.get('subject', '')}"
        if team_id in set(item.get("team_ids") or []) or abbrev in text:
            items.append(item)
    return sorted(items, key=lambda item: (item.get("date", ""), float(item.get("importance") or 0), item.get("id", "")), reverse=True)[:limit]


def league_social_items(save: dict[str, Any], user_team_id: str, limit: int = 20) -> list[dict[str, Any]]:
    items = [
        item for item in save.get("social_feed", [])
        if float(item.get("importance") or 0) >= 76
        and item.get("kind") != "social_digest_marker"
        and user_team_id not in set(item.get("team_ids") or [])
    ]
    return sorted(items, key=lambda item: (float(item.get("importance") or 0), item.get("date", ""), item.get("id", "")), reverse=True)[:limit]


def highlight_subject(text: str, subject: str | None) -> str:
    if not subject or subject not in text:
        return text
    return text.replace(subject, style(subject, "subject"), 1)


def social_event_subject(item: dict[str, Any]) -> str:
    narrative = item.get("narrative") or {}
    return str(narrative.get("display_subject") or item.get("subject") or "").strip()


def social_timeline_parts(item: dict[str, Any]) -> tuple[str, str, bool]:
    text = str(item.get("text") or "")
    subject = social_event_subject(item)
    narrative = item.get("narrative") or {}
    canned = str(narrative.get("source") or "").lower() == "fallback" or (not narrative and str(item.get("persona") or "").lower() in {"template", "system"})
    if not subject:
        return "", text, canned
    stripped_subject = subject.rstrip(".")
    stripped_text = text.strip()
    remainder = stripped_text
    if stripped_text.lower().startswith(subject.lower()):
        remainder = stripped_text[len(subject):].lstrip(" .")
    elif stripped_text.lower().startswith(stripped_subject.lower()):
        remainder = stripped_text[len(stripped_subject):].lstrip(" .")
    return subject, remainder, canned


def social_timeline_text(item: dict[str, Any]) -> str:
    subject, remainder, canned = social_timeline_parts(item)
    if not subject:
        return style(remainder, "danger") if canned else remainder
    if not remainder:
        return style(subject, "subject")
    body = style(remainder, "danger") if canned else remainder
    return f"{style(subject, 'subject')}\n  {body}".strip()


def social_timeline_lines(item: dict[str, Any], width: int | None = None) -> list[str]:
    width = int(width or shutil.get_terminal_size((116, 20)).columns)
    subject, remainder, canned = social_timeline_parts(item)
    date_text = str(item.get("date") or "")
    handle_text = style(str(item.get("handle") or "@league"), "accent")
    sentiment_text = f"[{item.get('sentiment', 0):>5}]"
    if subject:
        header = f"{date_text} {handle_text} {sentiment_text} {style(subject, 'subject')}".strip()
    else:
        header = f"{date_text} {handle_text} {sentiment_text}".strip()
    lines = [header]
    body = remainder.strip()
    if not body and not subject:
        body = str(item.get("text") or "").strip()
    if body:
        body_width = max(36, width - 2)
        wrapped = textwrap.wrap(body, width=body_width, break_long_words=False, break_on_hyphens=False) or [body]
        for line in wrapped:
            rendered = style(line, "danger") if canned else line
            lines.append(f"  {rendered}")
    return lines


def morale_bar(value: Any, width: int = 20) -> str:
    value = max(0.0, min(100.0, float(value if value is not None else 50.0)))
    filled = int(round(value / 100.0 * width))
    raw = "[" + "#" * filled + "." * (width - filled) + f"] {value:5.1f}/100"
    if value < 26:
        return style(raw, "danger")
    if value < 76:
        return style(raw, "accent")
    return style(raw, "good")


def interest_bar(value: Any, width: int = 18) -> str:
    return morale_bar(value, width=width)


def offer_interest_score(offer_millions: float, ask_millions: float, years: int, preferred_years: int, context_score: float = 50.0) -> float:
    salary_part = 52.0 * min(1.3, max(0.0, offer_millions) / max(ask_millions, 0.1))
    years_part = 16.0 * min(1.0, max(1, years) / max(1, preferred_years))
    context_part = (max(0.0, min(100.0, context_score)) - 50.0) * 0.42
    return round(max(0.0, min(100.0, salary_part + years_part + context_part)), 1)


def print_interest_read(score: float, pieces: dict[str, Any] | None = None) -> None:
    print(f"Interest {interest_bar(score)}")
    if pieces:
        compact = " | ".join(f"{label}: {value}" for label, value in pieces.items())
        if compact:
            print(f"  {compact}")


def print_calendar(view: dict[str, Any]) -> None:
    print_title(f"Calendar | previous week through two days ahead")
    for idx, game in enumerate(view["games"][:60], start=1):
        print(f"{idx:>2}. {game_label(game)}")


def print_box_score(canonical: dict[str, Any], save_path: Path, game_id: str) -> None:
    payload = box_score_view(canonical, save_path, game_id)
    ot = f" OT{payload['overtime_periods']}" if payload.get("overtime_periods") else ""
    print_title(f"Box Score | {payload['away_team'].get('abbrev')} at {payload['home_team'].get('abbrev')}")
    print(f"{payload['away_team'].get('abbrev')} {payload['away_score']} at {payload['home_team'].get('abbrev')} {payload['home_score']}{ot}")
    for team_line in payload["team_lines"]:
        print(f"\n{team_line.get('team_abbrev')}")
        rows = sorted(
            [line for line in payload["player_lines"] if line.get("team_id") == team_line.get("team_id")],
            key=box_score_influence,
            reverse=True,
        )
        print("Player                       MIN  PTS REB AST STL BLK   FG    3P    FT")
        for line in rows:
            print(
                f"{line.get('player_name', ''):<28} {float(line.get('minutes') or 0):>4.1f} "
                f"{int(line.get('points') or 0):>3} {int(line.get('rebounds') or 0):>3} {int(line.get('assists') or 0):>3} "
                f"{int(line.get('steals') or 0):>3} {int(line.get('blocks') or 0):>3} "
                f"{int(line.get('fgm') or 0):>2}-{int(line.get('fga') or 0):<2} "
                f"{int(line.get('fg3m') or 0):>2}-{int(line.get('fg3a') or 0):<2} "
                f"{int(line.get('ftm') or 0):>2}-{int(line.get('fta') or 0):<2}"
            )
        print_team_totals_row(team_line, rows)


def box_score_influence(line: dict[str, Any]) -> float:
    points = float(line.get("points") or 0.0)
    return (
        points
        + 1.2 * float(line.get("rebounds") or 0.0)
        + 1.5 * float(line.get("assists") or 0.0)
        + 3.0 * float(line.get("steals") or 0.0)
        + 3.0 * float(line.get("blocks") or 0.0)
        - 1.5 * float(line.get("turnovers") or line.get("tov") or 0.0)
    )


def print_team_totals_row(team_line: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    minutes = sum(float(row.get("minutes") or 0) for row in rows)
    totals = {
        "points": sum(int(row.get("points") or 0) for row in rows),
        "rebounds": sum(int(row.get("rebounds") or 0) for row in rows),
        "assists": sum(int(row.get("assists") or 0) for row in rows),
        "steals": sum(int(row.get("steals") or 0) for row in rows),
        "blocks": sum(int(row.get("blocks") or 0) for row in rows),
        "fgm": sum(int(row.get("fgm") or 0) for row in rows),
        "fga": sum(int(row.get("fga") or 0) for row in rows),
        "fg3m": sum(int(row.get("fg3m") or 0) for row in rows),
        "fg3a": sum(int(row.get("fg3a") or 0) for row in rows),
        "ftm": sum(int(row.get("ftm") or 0) for row in rows),
        "fta": sum(int(row.get("fta") or 0) for row in rows),
    }
    warning = ""
    if minutes and not (238 <= minutes <= 242 or 263 <= minutes <= 267 or 288 <= minutes <= 292):
        warning = style("  minutes check", "accent")
    print_rule()
    print(
        f"{'TEAM TOTALS':<28} {minutes:>4.1f} "
        f"{totals['points']:>3} {totals['rebounds']:>3} {totals['assists']:>3} "
        f"{totals['steals']:>3} {totals['blocks']:>3} "
        f"{totals['fgm']:>2}-{totals['fga']:<2} "
        f"{totals['fg3m']:>2}-{totals['fg3a']:<2} "
        f"{totals['ftm']:>2}-{totals['fta']:<2}{warning}"
    )


def game_label(game: dict[str, Any]) -> str:
    score = ""
    if game.get("away_score") is not None and game.get("home_score") is not None:
        score = f"  {game['away_score']}-{game['home_score']}"
        if game.get("overtime_periods"):
            score += f" OT{game['overtime_periods']}"
    marker = ""
    if game.get("user_result") == "W":
        marker = style(" W ", "good")
    elif game.get("user_result") == "L":
        marker = style(" L ", "danger")
    return f"{marker}{game['date']}  {game['away_team']} at {game['home_team']}{score}"


def choose_player_from_team(canonical: dict[str, Any], team_abbrev: str, prompt: str, allow_back: bool = False) -> dict[str, Any] | None:
    team = resolve_team(canonical, team_abbrev)
    players = sorted([p for p in canonical.get("players", []) if p.get("team_id") == team["id"]], key=display_minutes_projection, reverse=True)
    print_title(prompt)
    for idx, player in enumerate(players[:18], start=1):
        print(f"{idx:>2}. {player['name']:<26} {compact_position(player.get('position')):<3} {display_minutes_projection(player):>2.0f} mpg")
    if allow_back:
        print(" 0. Back")
    choice = pick_number("Player", 0 if allow_back else 1, min(18, len(players)), default=0 if allow_back else 1)
    if choice == 0:
        return None
    return players[choice - 1]


def choose_trade_player_from_team(canonical: dict[str, Any], save: dict[str, Any], team_abbrev: str, prompt: str) -> dict[str, Any]:
    team = resolve_team(canonical, team_abbrev)
    players = sorted([p for p in canonical.get("players", []) if p.get("team_id") == team["id"]], key=display_minutes_projection, reverse=True)
    season = contract_start_season_for_signing(save)
    team_games = int((save.get("team_records", {}).get(team["id"]) or {}).get("wins", 0)) + int((save.get("team_records", {}).get(team["id"]) or {}).get("losses", 0))
    stats = save.get("player_season_stats", {})
    health = {state.get("player_id"): state for state in save.get("health_states", [])}
    print_title(prompt)
    print(" #  Player                   Pos Age Ht     MPG  PPG  RPG  APG   OVR  OFF  DEF  GP/Team  Health        Contract years")
    for idx, player in enumerate(players[:18], start=1):
        totals = stats.get(player["id"], {})
        gp = int(totals.get("games") or 0)
        contract = salary_summary(player_salary_table(canonical, player["id"]), season)
        status = trade_health_text(health.get(player["id"], {}))
        attrs = player_attribute_summary(canonical, player["id"])
        print(
            f"{idx:>2}. {player['name']:<24} {compact_position(player.get('position')):<3} "
            f"{age_text(player, 3)} {height_text(player):<5} {display_minutes_projection(player):>4.0f} "
            f"{per_game_from_totals(totals, 'points'):>4.1f} {per_game_from_totals(totals, 'rebounds'):>4.1f} "
            f"{per_game_from_totals(totals, 'assists'):>4.1f} {float(attrs.get('overall') or 0):>5.1f} "
            f"{float(attrs.get('shooting') or 0):>4.1f} {float(attrs.get('defense') or 0):>4.1f} "
            f"{gp:>2}/{team_games:<2}  {status:<13} {contract}"
        )
    choice = pick_number("Player", 1, min(18, len(players)), default=1)
    return players[choice - 1]


def per_game_from_totals(totals: dict[str, Any], key: str) -> float:
    games = max(1, int(totals.get("games") or 0))
    return round(float(totals.get(key) or 0.0) / games, 1) if totals else 0.0


def height_text(player: dict[str, Any]) -> str:
    inches = player.get("height_inches")
    if inches:
        value = int(round(float(inches)))
        return f"{value // 12}'{value % 12}\""
    return str(player.get("height") or "--")


def compact_position(position: Any) -> str:
    text = str(position or "-").upper().replace("POSITION_", "")
    for separator in ["/", ",", "-", " "]:
        if separator in text:
            text = text.split(separator)[0]
            break
    text = text.strip()
    return text if text in {"PG", "SG", "SF", "PF", "C"} else text[:3] or "-"


def age_text(player: dict[str, Any], width: int = 3) -> str:
    value = player.get("display_age", player.get("age"))
    if value is None:
        return "--".rjust(width)
    try:
        return f"{float(value):>{width}.0f}"
    except (TypeError, ValueError):
        return "--".rjust(width)


def extension_start_season_for_date(date_value: str) -> str:
    try:
        year = int(str(date_value)[:4])
        month = int(str(date_value)[5:7])
    except (TypeError, ValueError):
        year = 2025
        month = 10
    start = year + 1 if month >= 7 else year
    return season_label_from_start_year(start)


def season_label_from_start_year(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def season_start_int(season: str) -> int:
    try:
        return int(str(season).split("-")[0])
    except (TypeError, ValueError):
        return 2025


def player_salary_millions_for_season(active: dict[str, Any], player_id: str | None, season: str) -> float:
    if not player_id:
        return 0.0
    contract = contract_for_player(active, player_id)
    if not contract:
        return 0.0
    for row in contract.get("seasons", []):
        if row.get("season") == season and row.get("salary") is not None:
            return float(row.get("salary") or 0.0) / 1_000_000
    return 0.0


def extension_max_legal_aav(active: dict[str, Any], save: dict[str, Any], team_id: str, player_id: str | None, start_season: str, years: int) -> float:
    start = season_start_int(start_season)
    spaces = []
    for offset in range(max(1, years)):
        season = season_label_from_start_year(start + offset)
        cap = team_cap_summary(active, save, team_id, season=season)
        hard_room = float(cap.get("hard_cap_space_millions") or 0.0)
        replaced_salary = player_salary_millions_for_season(active, player_id, season)
        spaces.append(max(0.0, hard_room + replaced_salary))
    return round(min(spaces) if spaces else 0.0, 2)


def print_extension_cap_projection(active: dict[str, Any], save: dict[str, Any], team_id: str, player_id: str | None, start_season: str, years: int) -> None:
    start = season_start_int(start_season)
    team = next((item for item in active.get("teams", []) if item.get("id") == team_id), {"abbrev": team_id_to_abbrev(team_id)})
    print(f"{team.get('abbrev')} projected cap:")
    for offset in range(max(2, min(5, years))):
        season = season_label_from_start_year(start + offset)
        cap = team_cap_summary(active, save, team_id, season=season)
        replaced_salary = player_salary_millions_for_season(active, player_id, season)
        room = float(cap.get("hard_cap_space_millions") or 0.0) + replaced_salary
        print(
            f"  {season}: payroll ${float(cap.get('salary_total_millions') or 0):.1f}M | "
            f"hard-cap room ${float(cap.get('hard_cap_space_millions') or 0):+.1f}M | extension room ${room:.1f}M"
        )


def extension_retirement_blocked(player: dict[str, Any], start_season: str, years: int) -> bool:
    start = season_start_int(start_season)
    retirement_start = projected_retirement_start_year(player, start)
    return retirement_start is not None and retirement_start <= start + max(1, years) - 1


def extension_safe_year_limit(player: dict[str, Any], start_season: str, max_years: int = 5) -> int:
    start = season_start_int(start_season)
    retirement_start = projected_retirement_start_year(player, start)
    if retirement_start is None:
        return max_years
    return max(0, min(max_years, retirement_start - start))


def prompt_extension_aav(default: float, max_legal: float, allow_back: bool = False) -> float | None:
    default = round(max(0.0, min(float(default), float(max_legal))), 1)
    while True:
        back_text = ", 0 to back" if allow_back else ""
        raw = input(f"Offer AAV in millions [{default:.1f}, max {max_legal:.1f}{back_text}]: ").strip()
        if allow_back and raw.lower() in {"0", "b", "back"}:
            return None
        try:
            value = float(raw) if raw else default
        except ValueError:
            value = default
        if value <= max_legal + 0.05:
            return round(max(0.0, value), 2)
        print(f"That offer would exceed the hard-cap limit. Max legal AAV is ${max_legal:.1f}M.")


def print_cap_summary(canonical: dict[str, Any], save: dict[str, Any], team_id: str, cap: dict[str, Any] | None = None) -> None:
    team = next((item for item in canonical.get("teams", []) if item.get("id") == team_id), {"abbrev": team_id_to_abbrev(team_id)})
    cap = cap or team_cap_summary(canonical, save, team_id)
    active_bids = user_active_bid_commitment(save, team_id) if save.get("free_agency_state") else 0.0
    after_payroll = float(cap.get("salary_total_millions") or 0.0) + active_bids
    after_tax = float(cap.get("tax_space_millions") or 0.0) - active_bids
    after_hard = float(cap.get("hard_cap_space_millions") or 0.0) - active_bids
    bid_text = ""
    if active_bids:
        bid_text = f" | after bids payroll ${after_payroll:.1f}M, tax ${after_tax:+.1f}M, hard ${after_hard:+.1f}M"
    print(
        f"{team.get('abbrev')} cap: payroll ${float(cap.get('salary_total_millions') or 0):.1f}M | "
        f"tax room ${float(cap.get('tax_space_millions') or 0):+.1f}M ({float(cap.get('tax_space_pct') or 0):+.1f}%) | "
        f"hard-cap room ${float(cap.get('hard_cap_space_millions') or 0):+.1f}M ({float(cap.get('hard_cap_space_pct') or 0):+.1f}%){bid_text}"
    )


def trade_health_text(state: dict[str, Any]) -> str:
    label = state.get("injury_label") or state.get("availability_status") or "healthy"
    if str(label).lower() in {"active", "healthy"}:
        return style("Healthy", "good")
    days_left = state.get("days_left") or state.get("expected_days_remaining")
    text = f"{clean_label(str(label))}"
    if days_left:
        text += f" ({int(float(days_left))}d)"
    return style(text, "danger" if float(days_left or 0) >= 14 else "accent")


def choose_team_abbrev(canonical: dict[str, Any], prompt: str, default: str | None = None, allow_back: bool = False) -> str | None:
    teams = sorted(canonical.get("teams", []), key=lambda item: item["abbrev"])
    default_idx = next((idx for idx, team in enumerate(teams, start=1) if team["abbrev"] == default), 1)
    print_title(prompt)
    for idx, team in enumerate(teams, start=1):
        print(f"{idx:>2}. {team['abbrev']}  {team['name']}")
    if allow_back:
        print(" 0. Back")
    choice = pick_number("Team", 0 if allow_back else 1, len(teams), default=0 if allow_back else default_idx)
    if choice == 0:
        clear_screen()
        return None
    return teams[choice - 1]["abbrev"]


def choose_staff_slot(allow_all: bool = False, allow_back: bool = False) -> str | None:
    offset = 1
    if allow_back:
        print("0. Back")
    if allow_all:
        print("0. All roles")
        offset = 0
    for idx, slot in enumerate(STAFF_SLOTS, start=1):
        print(f"{idx}. {ROLE_LABELS.get(slot, slot)}")
    low = 0 if (allow_all or allow_back) else 1
    choice = pick_number("Role", low, len(STAFF_SLOTS), default=0 if (allow_all or allow_back) else 1)
    if allow_back and choice == 0:
        return None
    if allow_all and choice == 0:
        return None
    return STAFF_SLOTS[choice - 1]


def choose_staff_market_slot() -> str:
    print_title("Staff Market")
    print("1. All roles")
    for idx, slot in enumerate(STAFF_SLOTS, start=2):
        print(f"{idx}. {ROLE_LABELS.get(slot, slot)}")
    print("0. Back")
    choice = pick_number("Role", 0, len(STAFF_SLOTS) + 1, default=0)
    if choice == 0:
        return "__back__"
    if choice == 1:
        return "__all__"
    return STAFF_SLOTS[choice - 2]


def resolve_team(canonical: dict[str, Any], query: str) -> dict[str, Any]:
    low = query.strip().lower()
    matches = [team for team in canonical.get("teams", []) if team["abbrev"].lower() == low or team["id"].lower() == low]
    matches = matches or [team for team in canonical.get("teams", []) if low in team["name"].lower()]
    if not matches:
        raise ValueError(f"No team found matching {query!r}")
    return matches[0]


def add_days(value: str, days: int) -> str:
    year, month, day = (int(part) for part in value.split("-"))
    from datetime import date

    return (date(year, month, day) + timedelta(days=days)).isoformat()


def advance_save_with_ai_checkpoints(root: Path, canonical: dict[str, Any], save_path: Path, target: str, seed: int, checkpoint_days: int = 31) -> dict[str, Any]:
    result: dict[str, Any] | None = None
    save = ensure_league_save_defaults(load_save(save_path), canonical)
    current = save.get("state", {}).get("current_date") or "2025-10-01"
    while current < target:
        step = min(add_days(current, checkpoint_days), target)
        result = advance_save(root, canonical, save_path, to_date=step, seed=seed)
        process_ai_actions(canonical, save_path, seed=seed, execute=True, limit=30)
        save = ensure_league_save_defaults(load_save(save_path), canonical)
        current = save.get("state", {}).get("current_date") or step
    return result or advance_save(root, canonical, save_path, to_date=target, seed=seed)


def pick_number(label: str, low: int, high: int, default: int) -> int:
    raw = input(f"{label} [{default}]: ").strip()
    if not raw:
        return default
    if raw.isdigit() and low <= int(raw) <= high:
        return int(raw)
    return default


def summary_lines(title: str, payload: dict[str, Any], keys: list[str]) -> str:
    lines = [title]
    for key in keys:
        lines.append(f"  {key}: {payload.get(key)}")
    return "\n".join(lines)


def yes_no(prompt: str) -> bool:
    try:
        return (input(f"{prompt} [y/N]: ").strip().lower() or "n").startswith("y")
    except EOFError:
        return False


def pause(message: str) -> None:
    print("\n" + str(message))
    wait()


def wait() -> None:
    try:
        input("\nPress Enter to continue...")
    except EOFError:
        return
    clear_screen()


def clear_screen() -> None:
    if not os.environ.get("NO_CLEAR"):
        print("\033[2J\033[H", end="")
    else:
        print("\n" * 6)


def print_title(title: str) -> None:
    print("\n" + "=" * 78)
    print(style(title, "title"))
    print("=" * 78)


def print_rule() -> None:
    print("-" * 78)


def style(text: str, kind: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    colors = {
        "title": "1;36",
        "accent": "1;33",
        "prompt": "1;32",
        "subject": "1;35",
        "danger": "1;31",
        "good": "1;32",
        "muted": "2;37",
        "value_quality": "1;31",
        "value_role": "0;33",
        "value_age": "1;34",
        "value_contract": "1;32",
        "value_fit": "1;35",
        "value_health": "1;33",
        "value_pick": "1;36",
        "value_cap": "1;37",
        "value_gm": "0;35",
    }
    return f"\033[{colors.get(kind, '0')}m{text}\033[0m"


def icon(emoji: str, fallback: str) -> str:
    if sys.stdout.isatty() and not os.environ.get("NO_EMOJI"):
        return emoji
    return fallback


def clean_label(value: str | None) -> str:
    return str(value or "").replace("_", " ").replace("-", " ")
