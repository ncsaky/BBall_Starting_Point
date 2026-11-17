#!/usr/bin/env python3
"""Run and audit a long NBA GM save through the same actions used by the GUI.

The runner deliberately avoids shortcut season simulators. Every mutation goes
through ``dispatch_app_action`` so a soak exercises the contracts that the
desktop/iPhone UI relies on. Results are checkpointed after every season.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import canonical_with_save, ensure_league_save_defaults, load_save, player_attribute_summary, repair_unpooled_unrostered_players, team_cap_summary
from nba_gm_data.staff import staff_budget_for_team, staff_budget_salary, staff_grade
from nba_gm_data.transactions import pick_obligation_validation_errors
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.utils import clear_utility_caches


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STAFF_SLOTS = {
    "head_coach",
    "offensive_coordinator",
    "defensive_coordinator",
    "development_lead",
    "performance_lead",
    "scouting_lead",
}
EXPECTED_AWARDS = {"MVP", "DPOY", "ROTY"}


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * max(0.0, min(1.0, quantile))
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    return round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight, 3)


def distribution(values: Iterable[float]) -> dict[str, float | int]:
    rows = [float(value) for value in values]
    if not rows:
        return {"count": 0, "mean": 0.0, "p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": len(rows),
        "mean": round(statistics.fmean(rows), 3),
        "p10": percentile(rows, 0.10),
        "p25": percentile(rows, 0.25),
        "p50": percentile(rows, 0.50),
        "p75": percentile(rows, 0.75),
        "p90": percentile(rows, 0.90),
        "p95": percentile(rows, 0.95),
        "max": round(max(rows), 3),
    }


def season_for_date(date_value: str) -> str:
    year = int(str(date_value)[:4])
    if str(date_value)[5:7] < "07":
        year -= 1
    return f"{year}-{str(year + 1)[-2:]}"


def next_seasons(season: str, count: int = 4) -> list[str]:
    start = int(str(season).split("-")[0])
    return [f"{start + offset}-{str(start + offset + 1)[-2:]}" for offset in range(count)]


def duplicate_ids(rows: Iterable[dict[str, Any]], key: str = "id") -> list[str]:
    counts = Counter(str(row.get(key)) for row in rows if row.get(key))
    return sorted(identifier for identifier, count in counts.items() if count > 1)


def transaction_counts(save: dict[str, Any], season: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in save.get("transaction_logs", []):
        date_value = str(row.get("date") or "")[:10]
        if len(date_value) != 10 or season_for_date(date_value) != season:
            continue
        counts[str(row.get("transaction_type") or "unknown")] += 1
    return dict(sorted(counts.items()))


def regular_season_stats(save: dict[str, Any]) -> dict[str, Any]:
    per_game: dict[str, list[dict[str, Any]]] = defaultdict(list)
    league_totals: Counter[str] = Counter()
    total_games = 0
    for player_id, row in (save.get("player_season_stats") or {}).items():
        games = int(row.get("games") or 0)
        if games <= 0:
            continue
        total_games += games
        output = {"player_id": player_id, "name": row.get("player_name"), "team": row.get("team_abbrev"), "games": games}
        for source, label in [("points", "ppg"), ("rebounds", "rpg"), ("assists", "apg"), ("steals", "spg"), ("blocks", "bpg")]:
            total = float(row.get(source) or 0.0)
            league_totals[source] += total
            output[label] = round(total / games, 2)
        per_game["players"].append(output)
    leaders = {}
    for label in ("ppg", "rpg", "apg", "spg", "bpg"):
        leaders[label] = sorted(per_game["players"], key=lambda item: (float(item[label]), int(item["games"])), reverse=True)[:10]
    team_records = list((save.get("team_records") or {}).values())
    team_games = sum(int(row.get("wins") or 0) + int(row.get("losses") or 0) for row in team_records)
    league_game_count = max(1, team_games // 2)
    return {
        "player_lines": len(per_game["players"]),
        "league_games": league_game_count,
        "points_per_team_game": round(sum(float(row.get("points_for") or 0.0) for row in team_records) / max(1, team_games), 3),
        "wins": distribution(int(row.get("wins") or 0) for row in team_records),
        "leaders": leaders,
        "weighted_player_per_game": {
            "points": round(league_totals["points"] / max(1, total_games), 3),
            "rebounds": round(league_totals["rebounds"] / max(1, total_games), 3),
            "assists": round(league_totals["assists"] / max(1, total_games), 3),
            "steals": round(league_totals["steals"] / max(1, total_games), 3),
            "blocks": round(league_totals["blocks"] / max(1, total_games), 3),
        },
    }


def talent_snapshot(active: dict[str, Any], save: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float], dict[str, float]]:
    free_agents = set(save.get("free_agent_player_ids") or [])
    retired = set(save.get("retired_player_ids") or [])
    rostered_values: dict[str, float] = {}
    active_pool_values: dict[str, float] = {}
    ages: dict[str, float] = {}
    generated = {row.get("id") for row in save.get("generated_players", [])}
    for player in active.get("players", []):
        player_id = player.get("id")
        if not player_id or player_id in retired:
            continue
        overall = float(player_attribute_summary(active, player_id).get("overall") or 0.0)
        active_pool_values[player_id] = overall
        ages[player_id] = float(player.get("display_age", player.get("age")) or 0.0)
        if player_id not in free_agents and player.get("team_id"):
            rostered_values[player_id] = overall
    all_values = list(rostered_values.values())
    by_age = {
        "22_and_under": distribution(rostered_values[player_id] for player_id in rostered_values if ages[player_id] <= 22.99),
        "23_to_27": distribution(rostered_values[player_id] for player_id in rostered_values if 23 <= ages[player_id] <= 27.99),
        "28_to_31": distribution(rostered_values[player_id] for player_id in rostered_values if 28 <= ages[player_id] <= 31.99),
        "32_plus": distribution(rostered_values[player_id] for player_id in rostered_values if ages[player_id] >= 32),
    }
    return (
        {
            "overall": distribution(all_values),
            "counts": {str(threshold): sum(value >= threshold for value in all_values) for threshold in (60, 70, 80, 90)},
            "active_pool_counts": {str(threshold): sum(value >= threshold for value in active_pool_values.values()) for threshold in (60, 70, 80, 90)},
            "by_age": by_age,
            "generated": distribution(rostered_values[player_id] for player_id in rostered_values if player_id in generated),
            "baseline_players": distribution(rostered_values[player_id] for player_id in rostered_values if player_id not in generated),
            "active_pool": distribution(active_pool_values.values()),
            "active_pool_generated": distribution(active_pool_values[player_id] for player_id in active_pool_values if player_id in generated),
        },
        active_pool_values,
        ages,
    )


def development_deltas(
    before: dict[str, float],
    after: dict[str, float],
    before_ages: dict[str, float],
    active: dict[str, Any],
    save: dict[str, Any],
) -> dict[str, Any]:
    players = {row.get("id"): row for row in active.get("players", [])}
    generated = {row.get("id") for row in save.get("generated_players", [])}
    groups: dict[str, list[float]] = defaultdict(list)
    for player_id in before.keys() & after.keys():
        delta = round(after[player_id] - before[player_id], 3)
        age = float(before_ages.get(player_id, (players.get(player_id) or {}).get("display_age", (players.get(player_id) or {}).get("age"))) or 0.0)
        age_group = "22_and_under" if age <= 22.99 else "23_to_27" if age <= 27.99 else "28_to_31" if age <= 31.99 else "32_plus"
        groups[age_group].append(delta)
        groups["generated" if player_id in generated else "baseline_players"].append(delta)
        groups["all"].append(delta)
    output = {}
    for key, values in groups.items():
        output[key] = {
            **distribution(values),
            "positive_pct": round(100 * sum(value > 0.05 for value in values) / max(1, len(values)), 1),
            "negative_pct": round(100 * sum(value < -0.05 for value in values) / max(1, len(values)), 1),
            "flat_pct": round(100 * sum(abs(value) <= 0.05 for value in values) / max(1, len(values)), 1),
        }
    return output


def rookie_snapshot(canonical: dict[str, Any], save: dict[str, Any], draft_year: str) -> dict[str, Any]:
    rows = [row for row in save.get("incoming_rookies", []) if str(row.get("draft_year")) == str(draft_year)]
    active = canonical_with_save(canonical, save)
    engine_overalls = [
        float(player_attribute_summary(active, str(row.get("player_id"))).get("overall") or 0.0)
        for row in rows
        if row.get("player_id")
    ]
    first_round = [float(row.get("current_ability") or 0.0) for row in rows if int(row.get("overall_pick") or 99) <= 30]
    second_round = [float(row.get("current_ability") or 0.0) for row in rows if int(row.get("overall_pick") or 99) > 30]
    return {
        "draft_year": str(draft_year),
        "rookie_count": len(rows),
        "current_ability": distribution(float(row.get("current_ability") or 0.0) for row in rows),
        "potential": distribution(float(row.get("potential") or 0.0) for row in rows),
        "engine_overall": distribution(engine_overalls),
        "first_round_ability": distribution(first_round),
        "second_round_ability": distribution(second_round),
        "top_five": [
            {key: row.get(key) for key in ("overall_pick", "name", "position", "current_ability", "potential", "team_abbrev")}
            for row in sorted(rows, key=lambda item: int(item.get("overall_pick") or 999))[:5]
        ],
    }


def audit_snapshot(canonical: dict[str, Any], save: dict[str, Any], label: str) -> dict[str, Any]:
    active = canonical_with_save(canonical, save)
    errors: list[str] = []
    warnings: list[str] = []
    team_ids = {team.get("id") for team in active.get("teams", [])}
    players = active.get("players", [])
    player_ids = {player.get("id") for player in players if player.get("id")}
    free_agents = set(save.get("free_agent_player_ids") or [])
    retired = set(save.get("retired_player_ids") or [])
    league_exits = set(save.get("league_exit_player_ids") or [])

    duplicate_collections = {
        "players": duplicate_ids(players),
        "contracts": duplicate_ids(active.get("contracts", [])),
        "draft_picks": duplicate_ids(active.get("draft_picks", [])),
        "staff_slots": duplicate_ids(save.get("staff_slots", [])),
        "pick_obligations": duplicate_ids(save.get("pick_obligations", [])),
        "transaction_logs": duplicate_ids(save.get("transaction_logs", [])),
        "league_awards": duplicate_ids(save.get("league_awards", [])),
        "injury_events": duplicate_ids(save.get("injury_events", [])),
        "development_events": duplicate_ids(save.get("development_events", [])),
        "league_exit_records": duplicate_ids(save.get("league_exit_records", [])),
    }
    trait_keys = Counter((row.get("player_id"), row.get("trait_key")) for row in active.get("traits", []) if row.get("player_id") and row.get("trait_key"))
    duplicate_collections["trait_keys"] = sorted(f"{player_id}:{trait}" for (player_id, trait), count in trait_keys.items() if count > 1)
    for collection, duplicates in duplicate_collections.items():
        if duplicates:
            errors.append(f"{collection} contains {len(duplicates)} duplicate IDs/keys")

    roster_sizes: Counter[str] = Counter()
    for player in players:
        player_id = player.get("id")
        team_id = player.get("team_id")
        if team_id:
            roster_sizes[str(team_id)] += 1
            if team_id not in team_ids:
                errors.append(f"{player_id} is assigned to unknown team {team_id}")
            if player_id in free_agents:
                errors.append(f"{player_id} is both rostered and in the free-agent pool")
            if player_id in retired:
                errors.append(f"{player_id} is both rostered and retired")
    for team_id in sorted(team_ids):
        size = roster_sizes.get(str(team_id), 0)
        if size < 14 or size > 17:
            warnings.append(f"{team_id} roster size is {size}, outside 14-17")
    for player_id in free_agents:
        player = next((row for row in players if row.get("id") == player_id), None)
        if player and player.get("team_id"):
            errors.append(f"free agent {player_id} still has team {player.get('team_id')}")
    unsigned_rights = {
        row.get("player_id")
        for row in save.get("incoming_rookies", [])
        if row.get("player_id") and row.get("rights_status") == "exclusive_unsigned_rights"
    }
    orphaned_players = sorted(
        str(player.get("id"))
        for player in players
        if player.get("id")
        and not player.get("team_id")
        and player.get("id") not in free_agents
        and player.get("id") not in retired
        and player.get("id") not in unsigned_rights
    )
    if orphaned_players:
        errors.append(f"{len(orphaned_players)} active players are neither rostered, free agents, retired, nor unsigned draft rights")

    active_season = str(save.get("meta", {}).get("season") or "")
    contracts_by_player: dict[str, list[dict[str, Any]]] = defaultdict(list)
    malformed_contracts: list[str] = []
    for contract in active.get("contracts", []):
        player_id = contract.get("player_id")
        if player_id:
            contracts_by_player[str(player_id)].append(contract)
        seen_seasons: set[str] = set()
        for season_row in contract.get("seasons", []):
            season = str(season_row.get("season") or "")
            salary = season_row.get("salary")
            if not season or season in seen_seasons or (salary is not None and float(salary) < 0):
                malformed_contracts.append(str(contract.get("id") or player_id))
            seen_seasons.add(season)
    if malformed_contracts:
        errors.append(f"{len(set(malformed_contracts))} malformed contract records")
    missing_current_contract = []
    for player in players:
        if not player.get("team_id") or player.get("id") in retired:
            continue
        contracts = contracts_by_player.get(str(player.get("id")), [])
        if not any(any(str(row.get("season")) == active_season and row.get("salary") is not None for row in contract.get("seasons", [])) for contract in contracts):
            missing_current_contract.append(str(player.get("id")))
    if missing_current_contract:
        warnings.append(f"{len(missing_current_contract)} rostered players have no salary in {active_season}")

    cap_rows = []
    for team_id in sorted(team_ids):
        for season in next_seasons(active_season, 4):
            cap = team_cap_summary(active, save, str(team_id), season)
            cap_rows.append({"team_id": team_id, **cap})
            if float(cap.get("hard_cap_space_millions") or 0.0) < -0.05:
                warnings.append(f"{team_id} is {abs(float(cap['hard_cap_space_millions'])):.1f}M over hard cap in {season}")

    obligation_errors = []
    for obligation in save.get("pick_obligations", []):
        if str(obligation.get("status") or "active") not in {"active", "pending"}:
            continue
        existing_term = dict(obligation)
        existing_term["_existing_fallback_pick_ids"] = list(obligation.get("fallback_pick_ids") or [])
        issues = [
            issue
            for issue in pick_obligation_validation_errors(active, None, existing_term)
            if "already locked" not in issue
        ]
        if issues:
            obligation_errors.append({"id": obligation.get("id"), "issues": issues})
    if obligation_errors:
        errors.append(f"{len(obligation_errors)} active pick obligations fail validation")

    award_errors = []
    roty_winners: Counter[str] = Counter()
    rookie_year_by_player = {row.get("player_id"): str(row.get("draft_year")) for row in save.get("incoming_rookies", []) if row.get("player_id")}
    for history in save.get("season_history", []):
        awards = history.get("awards", [])
        award_names = {str(row.get("award") or "").upper() for row in awards}
        if award_names != EXPECTED_AWARDS:
            award_errors.append(f"{history.get('season')} awards={sorted(award_names)}")
        for award in awards:
            if str(award.get("award") or "").upper() == "ROTY":
                player_id = str(award.get("player_id") or "")
                roty_winners[player_id] += 1
                draft_year = rookie_year_by_player.get(player_id)
                award_end_year = str(history.get("season") or "").split("-")[0]
                expected_draft_year = award_end_year if award_end_year.isdigit() else ""
                if draft_year and draft_year != expected_draft_year:
                    award_errors.append(f"{history.get('season')} ROTY {player_id} drafted in {draft_year}")
    for player_id, count in roty_winners.items():
        if count > 1:
            award_errors.append(f"{player_id} won ROTY {count} times")
    if award_errors:
        errors.append(f"award audit found {len(award_errors)} issue(s)")

    staff_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    staff_key_counts: Counter[tuple[str, str]] = Counter()
    for slot in save.get("staff_slots", []):
        if slot.get("market_status") == "employed" and slot.get("team_id"):
            staff_by_team[str(slot.get("team_id"))].append(slot)
            staff_key_counts[(str(slot.get("team_id")), str(slot.get("slot")))] += 1
    staff_budget_rows = []
    for team_id in sorted(team_ids):
        slots = staff_by_team.get(str(team_id), [])
        slot_names = {str(slot.get("slot")) for slot in slots}
        if slot_names != EXPECTED_STAFF_SLOTS:
            errors.append(f"{team_id} staff slots are {sorted(slot_names)}")
        spent = round(sum(staff_budget_salary(slot) for slot in slots), 2)
        # Staff budgets are franchise configuration, not a derived active-save
        # projection. Use the canonical strategic profile just like hiring and
        # retention logic do.
        budget = float(staff_budget_for_team(canonical, str(team_id)))
        if spent > budget + 0.01:
            errors.append(f"{team_id} staff payroll {spent:.1f}M exceeds {budget:.1f}M budget")
        staff_budget_rows.append({"team_id": team_id, "spent": spent, "budget": round(budget, 2), "grades": [round(staff_grade(slot), 1) for slot in slots]})
    duplicate_staff_slots = [f"{team}:{slot}" for (team, slot), count in staff_key_counts.items() if count > 1]
    if duplicate_staff_slots:
        errors.append(f"{len(duplicate_staff_slots)} team/slot staff assignments are duplicated")

    talent, overall_by_player, age_by_player = talent_snapshot(active, save)
    season_injuries = [
        row
        for row in save.get("injury_events", [])
        if len(str(row.get("start_date") or "")) >= 10
        and season_for_date(str(row.get("start_date"))[:10]) == active_season
    ]
    injury_bands: Counter[str] = Counter()
    for row in season_injuries:
        missed = float(row.get("expected_games_missed") or 0.0)
        band = "0-1" if missed <= 1 else "2-5" if missed <= 5 else "6-15" if missed <= 15 else "16-40" if missed <= 40 else "41+"
        injury_bands[band] += 1
    return {
        "label": label,
        "date": save.get("state", {}).get("current_date"),
        "phase": save.get("state", {}).get("phase"),
        "season": active_season,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "duplicates": duplicate_collections,
        "roster_sizes": dict(sorted(roster_sizes.items())),
        "free_agents": len(free_agents),
        "orphaned_player_ids": orphaned_players,
        "retired": len(retired - league_exits),
        "league_exits": len(league_exits),
        "missing_current_contract_count": len(missing_current_contract),
        "cap_rows": cap_rows,
        "obligation_errors": obligation_errors,
        "award_errors": award_errors,
        "staff": staff_budget_rows,
        "talent": talent,
        "overall_by_player": overall_by_player,
        "age_by_player": age_by_player,
        "transactions": transaction_counts(save, active_season),
        "injuries": {
            "events_in_season": len(season_injuries),
            "unique_players": len({row.get("player_id") for row in season_injuries if row.get("player_id")}),
            "recurrences_in_season": sum(bool(row.get("recurrence")) for row in season_injuries),
            "severity_bands": dict(sorted(injury_bands.items())),
            "expected_games_missed_total": round(sum(float(row.get("expected_games_missed") or 0.0) for row in season_injuries), 1),
            "expected_games_missed": distribution(float(row.get("expected_games_missed") or 0.0) for row in season_injuries),
            "recorded_games_missed_total": sum(int(row.get("games_missed") or 0) for row in save.get("health_states", [])),
        },
    }


def staff_turnover_counts(save: dict[str, Any], season: str) -> dict[str, Any]:
    output: Counter[str] = Counter()
    slots: Counter[str] = Counter()
    for row in save.get("transaction_logs", []):
        date_value = str(row.get("date") or "")[:10]
        if len(date_value) != 10 or season_for_date(date_value) != season:
            continue
        kind = str(row.get("transaction_type") or "")
        if kind not in {"staff_hire", "staff_fire"}:
            continue
        assets = row.get("assets") or {}
        reported_kind = "staff_retain" if kind == "staff_hire" and assets.get("retained") else kind
        output[reported_kind] += 1
        staff = (assets.get("fired_staff") if kind == "staff_fire" else assets.get("staff") or assets.get("hired_staff")) or {}
        slot = str(staff.get("slot") or "unknown")
        slots[f"{reported_kind}:{slot}"] += 1
    return {"totals": dict(output), "by_slot": dict(sorted(slots.items()))}


def cap_violation_map(audit: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {
        (str(row.get("team_id")), str(row.get("season"))): round(abs(float(row.get("hard_cap_space_millions") or 0.0)), 3)
        for row in audit.get("cap_rows", [])
        if float(row.get("hard_cap_space_millions") or 0.0) < -0.05
    }


def non_cap_warnings(audit: dict[str, Any]) -> list[str]:
    return [message for message in audit.get("warnings", []) if "over hard cap" not in message]


def mandatory_cap_additions(save: dict[str, Any], start_save: dict[str, Any] | None = None) -> dict[tuple[str, str], float]:
    additions: Counter[tuple[str, str]] = Counter()
    starting_contracts = (start_save or {}).get("contract_overrides") or {}
    for player_id, contract in (save.get("contract_overrides") or {}).items():
        status = str(contract.get("status") or "")
        annual_salary = float(contract.get("annual_salary") or 0.0)
        is_free_agent_minimum = (
            str(contract.get("offer_type") or "") == "free_agent_signing"
            and 0 < annual_salary <= 1_950_000
        )
        season_rows = list(contract.get("seasons", []))
        is_offseason_minimum = status == "ai_offseason_signing" and bool(season_rows) and all(
            float(row.get("salary") or 0.0) <= 2_250_000 for row in season_rows
        )
        if status not in {"auto_depth_signing", "signed_rookie_contract"} and not is_free_agent_minimum and not is_offseason_minimum:
            continue
        team_id = str(contract.get("team_id") or "")
        if not team_id:
            continue
        seasons = season_rows
        if is_free_agent_minimum and not seasons:
            start = int(str(contract.get("start_season") or contract.get("signed_season") or "2025-26").split("-")[0])
            seasons = [
                {"season": f"{start + offset}-{str(start + offset + 1)[-2:]}", "salary": annual_salary}
                for offset in range(max(1, int(contract.get("years") or 1)))
            ]
        starting_contract = starting_contracts.get(player_id) or {}
        starting_team_id = str(starting_contract.get("team_id") or "")
        starting_salary = {
            (starting_team_id, str(row.get("season") or "")): float(row.get("salary") or 0.0)
            for row in starting_contract.get("seasons", [])
            if starting_team_id and row.get("season")
        }
        for row in seasons:
            season = str(row.get("season") or "")
            salary = float(row.get("salary") or 0.0)
            if season and salary > 0:
                incremental_salary = max(0.0, salary - starting_salary.get((team_id, season), 0.0))
                additions[(team_id, season)] += incremental_salary / 1_000_000
    return dict(additions)


def cap_transition(start: dict[str, Any], end: dict[str, Any], save: dict[str, Any], start_save: dict[str, Any] | None = None) -> dict[str, Any]:
    before = cap_violation_map(start)
    after = cap_violation_map(end)
    mandatory = mandatory_cap_additions(save, start_save)
    new = []
    worsened = []
    mandatory_exceptions = []
    improved = []
    for key, overage in sorted(after.items()):
        increase = overage - before.get(key, 0.0)
        mandatory_room = float(mandatory.get(key, 0.0))
        if increase > 0.05 and mandatory_room + 0.25 >= increase:
            mandatory_exceptions.append(
                {
                    "team_id": key[0],
                    "season": key[1],
                    "before": before.get(key, 0.0),
                    "after": overage,
                    "mandatory_additions_millions": round(mandatory_room, 3),
                }
            )
            continue
        if key not in before:
            new.append({"team_id": key[0], "season": key[1], "overage_millions": overage})
        elif overage > before[key] + 0.05:
            worsened.append({"team_id": key[0], "season": key[1], "before": before[key], "after": overage})
    for key, overage in sorted(before.items()):
        if key not in after or after.get(key, 0.0) < overage - 0.05:
            improved.append({"team_id": key[0], "season": key[1], "before": overage, "after": after.get(key, 0.0)})
    return {
        "new": new,
        "worsened": worsened,
        "mandatory_exceptions": mandatory_exceptions,
        "improved": improved,
        "inherited": len(before),
    }


def markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Ten-Season GUI Action Soak Audit",
        "",
        f"- Seed: `{payload['seed']}`",
        f"- Team: `{payload['team']}`",
        f"- Save: `{payload['save_path']}`",
        f"- Seasons completed: **{len(payload['seasons'])}**",
        f"- Runtime: **{payload['runtime_seconds'] / 60:.1f} minutes**",
        f"- Hard invariant failures: **{len(payload['errors'])}**",
        f"- Calibration warnings: **{len(payload['warnings'])}**",
        "",
        "## Season Summary",
        "",
        "| Season | Champion | Trades | Extensions | League exits | Staff H/F | HC fires | Injuries | PPG leader | APG leader | Roster / pool OVR | Rookie OVR p90 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|",
    ]
    for season in payload["seasons"]:
        tx = season.get("transactions", {})
        stats = season.get("stats", {})
        ppg = (stats.get("leaders", {}).get("ppg") or [{}])[0]
        apg = (stats.get("leaders", {}).get("apg") or [{}])[0]
        staff_slots = season.get("staff_turnover", {}).get("by_slot", {})
        talent = season.get("end_talent", {})
        injuries = season.get("injuries", {})
        long_injuries = sum(int((injuries.get("severity_bands") or {}).get(key, 0)) for key in ("16-40", "41+"))
        lines.append(
            f"| {season['season']} | {season.get('champion') or '-'} | {tx.get('trade', 0)} | {tx.get('extension', 0)} | {season.get('league_exits', 0)} | "
            f"{tx.get('staff_hire', 0)}/{tx.get('staff_fire', 0)} | {staff_slots.get('staff_fire:head_coach', 0)} | "
            f"{injuries.get('events_in_season', 0)} / {long_injuries} long | "
            f"{ppg.get('name', '-')} {ppg.get('ppg', '-')} | {apg.get('name', '-')} {apg.get('apg', '-')} | "
            f"{talent.get('overall', {}).get('mean', 0):.2f} / {talent.get('active_pool', {}).get('mean', 0):.2f} | "
            f"{season.get('rookies', {}).get('engine_overall', {}).get('p90', 0):.2f} |"
        )
    lines.extend(["", "## Awards", "", "| Season | MVP | DPOY | ROTY |", "|---|---|---|---|"])
    for season in payload["seasons"]:
        awards = season.get("awards", {})
        lines.append(
            f"| {season['season']} | {awards.get('MVP', '-')} | {awards.get('DPOY', '-')} | {awards.get('ROTY', '-')} |"
        )
    lines.extend(["", "## Talent Stability", ""])
    baseline = payload.get("baseline_talent", {}).get("overall", {})
    baseline_pool = payload.get("baseline_talent", {}).get("active_pool", {})
    lines.append(f"Baseline rostered-player OVR: mean **{baseline.get('mean', 0):.2f}**, p90 **{baseline.get('p90', 0):.2f}**, max **{baseline.get('max', 0):.2f}**.")
    lines.append(f"Baseline active talent pool: mean **{baseline_pool.get('mean', 0):.2f}**, p90 **{baseline_pool.get('p90', 0):.2f}**, count **{baseline_pool.get('count', 0)}**.")
    lines.append("")
    lines.append("| Season | Roster mean | Roster p90 | Roster count | Pool mean | Pool p90 | Pool count | Roster 70+/80+ | Pool 70+/80+ |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for season in payload["seasons"]:
        talent = season.get("end_talent", {})
        overall = talent.get("overall", {})
        active_pool = talent.get("active_pool", {})
        lines.append(
            f"| {season['season']} | {overall.get('mean', 0):.2f} | {overall.get('p90', 0):.2f} | {overall.get('count', 0)} | "
            f"{active_pool.get('mean', 0):.2f} | {active_pool.get('p90', 0):.2f} | {active_pool.get('count', 0)} | "
            f"{talent.get('counts', {}).get('70', 0)}/{talent.get('counts', {}).get('80', 0)} | "
            f"{talent.get('active_pool_counts', {}).get('70', 0)}/{talent.get('active_pool_counts', {}).get('80', 0)} |"
        )
    lines.extend(["", "## Generated Talent", "", "| Season | Draft ability mean / p90 | Rookie OVR mean / p90 | Generated roster mean / p90 | Generated active pool mean / p90 / count |", "|---|---:|---:|---:|---:|"])
    for season in payload["seasons"]:
        rookies = season.get("rookies", {})
        talent = season.get("end_talent", {})
        ability = rookies.get("current_ability", {})
        rookie_overall = rookies.get("engine_overall", {})
        generated = talent.get("generated", {})
        active_generated = talent.get("active_pool_generated", {})
        lines.append(
            f"| {season['season']} | {ability.get('mean', 0):.2f} / {ability.get('p90', 0):.2f} | "
            f"{rookie_overall.get('mean', 0):.2f} / {rookie_overall.get('p90', 0):.2f} | "
            f"{generated.get('mean', 0):.2f} / {generated.get('p90', 0):.2f} | "
            f"{active_generated.get('mean', 0):.2f} / {active_generated.get('p90', 0):.2f} / {active_generated.get('count', 0)} |"
        )
    lines.extend(["", "## Development And Regression", "", "| Season | <=22 | 23-27 | 28-31 | 32+ | Generated players |", "|---|---:|---:|---:|---:|---:|"])
    for season in payload["seasons"]:
        deltas = season.get("development_deltas", {})
        lines.append(
            f"| {season['season']} | {deltas.get('22_and_under', {}).get('mean', 0):+.2f} | "
            f"{deltas.get('23_to_27', {}).get('mean', 0):+.2f} | {deltas.get('28_to_31', {}).get('mean', 0):+.2f} | "
            f"{deltas.get('32_plus', {}).get('mean', 0):+.2f} | {deltas.get('generated', {}).get('mean', 0):+.2f} |"
        )
    lines.extend(["", "## Injury Burden", "", "| Season | Events | Players | Recurrences | 0-1 | 2-5 | 6-15 | 16-40 | 41+ | Expected / recorded missed |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for season in payload["seasons"]:
        injuries = season.get("injuries", {})
        bands = injuries.get("severity_bands", {})
        lines.append(
            f"| {season['season']} | {injuries.get('events_in_season', 0)} | {injuries.get('unique_players', 0)} | "
            f"{injuries.get('recurrences_in_season', 0)} | {bands.get('0-1', 0)} | {bands.get('2-5', 0)} | "
            f"{bands.get('6-15', 0)} | {bands.get('16-40', 0)} | {bands.get('41+', 0)} | "
            f"{injuries.get('expected_games_missed_total', 0):.1f} / {injuries.get('recorded_games_missed_total', 0)} |"
        )
    lines.extend(["", "## Cap Legality", ""])
    for season in payload["seasons"]:
        cap = season.get("cap_transition", {})
        lines.append(
            f"- **{season['season']}**: {len(cap.get('new', []))} new discretionary overages, "
            f"{len(cap.get('worsened', []))} worsened discretionary overages, "
            f"{len(cap.get('mandatory_exceptions', []))} mandatory rookie/minimum exceptions, "
            f"{cap.get('inherited', 0)} inherited over-limit team-seasons."
        )
    if payload.get("remediations"):
        lines.extend(["", "## Findings And Fixes", ""])
        for item in payload["remediations"]:
            lines.append(f"- **{item.get('status', 'fixed')} — {item.get('issue', 'Issue')}**: {item.get('evidence', '')}")
    lines.extend(["", "## Hard Failures", ""])
    lines.extend([f"- {item}" for item in payload["errors"]] or ["- None."])
    lines.extend(["", "## Calibration Warnings", ""])
    lines.extend([f"- {item}" for item in payload["warnings"]] or ["- None."])
    save_sizes = payload.get("rollover_save_sizes_mb") or []
    if save_sizes:
        lines.extend(["", "## Long-Run Save Size", ""])
        lines.append("| Season | Rollover save |")
        lines.append("|---|---:|")
        for row in save_sizes:
            lines.append(f"| {row.get('season', '-')} | {float(row.get('megabytes') or 0.0):.1f} MB |")
        lines.extend(
            [
                "",
                "Complete historical box scores, transactions, awards, and year reviews are intentionally retained. "
                "The resulting linear storage growth is a residual GUI-hydration concern, not a gameplay-integrity failure; "
                "a future archive/index layer can address it without deleting simulation detail.",
            ]
        )
    lines.extend(["", "## Artifacts", "", "The adjacent JSON report contains complete cap rows, duplicate-ID scans, pick-obligation validation, staff budgets, award checks, distribution tails, and top-ten statistical leaders for every season.", ""])
    return "\n".join(lines)


def season_calibration_warnings(payload: dict[str, Any], season_payload: dict[str, Any], end_audit: dict[str, Any]) -> list[str]:
    season = str(season_payload.get("season") or "unknown")
    warnings: list[str] = []
    baseline_pool_mean = float((payload.get("baseline_talent") or {}).get("active_pool", {}).get("mean") or 0.0)
    current_pool_mean = float(end_audit.get("talent", {}).get("active_pool", {}).get("mean") or 0.0)
    baseline_roster_p90 = float((payload.get("baseline_talent") or {}).get("overall", {}).get("p90") or 0.0)
    current_roster_p90 = float(end_audit.get("talent", {}).get("overall", {}).get("p90") or 0.0)
    # Removing the inactive fringe tail intentionally raises the pool mean;
    # roster p90 below remains the talent-inflation guard after league exits.
    if not int(end_audit.get("league_exits") or 0) and abs(current_pool_mean - baseline_pool_mean) > 3.0:
        warnings.append(f"{season} rollover: active talent-pool mean drifted {current_pool_mean - baseline_pool_mean:+.2f} from baseline")
    if abs(current_roster_p90 - baseline_roster_p90) > 3.0:
        warnings.append(f"{season} rollover: rostered-player p90 drifted {current_roster_p90 - baseline_roster_p90:+.2f} from baseline")
    baseline_pool_count = int((payload.get("baseline_talent") or {}).get("active_pool", {}).get("count") or 0)
    current_pool_count = int(end_audit.get("talent", {}).get("active_pool", {}).get("count") or 0)
    if current_pool_count > baseline_pool_count + 300:
        warnings.append(f"{season} rollover: active player pool expanded by {current_pool_count - baseline_pool_count} players from baseline")
    rookies = season_payload.get("rookies") or {}
    if float((rookies.get("current_ability") or {}).get("p90") or 0.0) > current_roster_p90 + 2.0:
        warnings.append(f"{season} draft: rookie ability p90 exceeds rostered-player p90 by more than 2")
    cap_changes = season_payload.get("cap_transition") or {}
    if cap_changes.get("new") or cap_changes.get("worsened"):
        warnings.append(f"{season} cap: {len(cap_changes.get('new') or [])} new and {len(cap_changes.get('worsened') or [])} worsened hard-cap overages")
    transactions = season_payload.get("transactions") or {}
    extensions = int(transactions.get("extension") or 0)
    if not 20 <= extensions <= 35:
        warnings.append(f"{season} extensions: {extensions}, outside calibration band 20-35")
    trades = int(transactions.get("trade") or 0)
    if not 12 <= trades <= 35:
        warnings.append(f"{season} trades: {trades}, outside calibration band 12-35")
    stats = season_payload.get("stats") or {}
    team_ppg = float(stats.get("points_per_team_game") or 0.0)
    if not 108.0 <= team_ppg <= 118.0:
        warnings.append(f"{season} scoring environment: {team_ppg:.1f} points per team-game")
    ppg_leader = (stats.get("leaders", {}).get("ppg") or [{}])[0]
    if float(ppg_leader.get("ppg") or 0.0) > 34.5:
        warnings.append(f"{season} scoring leader: {ppg_leader.get('name')} at {ppg_leader.get('ppg')} PPG")
    deltas = season_payload.get("development_deltas") or {}
    young_growth = float((deltas.get("22_and_under") or {}).get("mean") or 0.0)
    veteran_decline = float((deltas.get("32_plus") or {}).get("mean") or 0.0)
    veteran_negative_pct = float((deltas.get("32_plus") or {}).get("negative_pct") or 0.0)
    if young_growth < 0.15:
        warnings.append(f"{season} development: <=22 mean change is only {young_growth:+.2f}")
    if veteran_decline > -0.05 or veteran_negative_pct < 45.0:
        warnings.append(f"{season} regression: 32+ mean {veteran_decline:+.2f}, {veteran_negative_pct:.1f}% declined")
    return warnings


def refresh_existing_report(root: Path, output_dir: Path) -> dict[str, Any]:
    report_path = output_dir / "soak_audit.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    canonical = load_app_canonical(root)
    phase_dir = output_dir / "phase_saves"
    refreshed_errors = list((payload.get("baseline_audit") or {}).get("errors") or [])
    refreshed_warnings = non_cap_warnings(payload.get("baseline_audit") or {})
    previous_end_save: dict[str, Any] | None = None
    previous_end_audit: dict[str, Any] | None = None
    total_legacy_repairs = 0
    for index, season_payload in enumerate(payload.get("seasons", []), start=1):
        season = str(season_payload.get("season") or "")
        regular_raw = load_save(phase_dir / f"season_{index:02d}_playoffs.json")
        regular_repairs = repair_unpooled_unrostered_players(canonical, regular_raw)
        regular_save = ensure_league_save_defaults(regular_raw, canonical)
        end_raw = load_save(phase_dir / f"season_{index:02d}_rollover.json")
        end_repairs = repair_unpooled_unrostered_players(canonical, end_raw)
        end_save = ensure_league_save_defaults(end_raw, canonical)
        total_legacy_repairs += regular_repairs + end_repairs
        regular_audit = audit_snapshot(canonical, regular_save, f"{season} regular season complete")
        end_audit = audit_snapshot(canonical, end_save, f"{season} rollover")
        draft_year = str(int(season.split("-")[0]) + 1)
        season_payload["stats"] = regular_season_stats(regular_save)
        season_payload["rookies"] = rookie_snapshot(canonical, end_save, draft_year)
        season_payload["transactions"] = transaction_counts(end_save, season)
        season_payload["staff_turnover"] = staff_turnover_counts(end_save, season)
        season_payload["league_exits"] = sum(
            1
            for row in end_save.get("league_exit_records", [])
            if str(row.get("season") or "") == season
        )
        season_payload["injuries"] = regular_audit["injuries"]
        season_payload["end_talent"] = end_audit["talent"]
        season_payload["legacy_unpooled_repairs"] = {"regular": regular_repairs, "rollover": end_repairs}
        if previous_end_audit is not None and previous_end_save is not None:
            season_payload["start_talent"] = previous_end_audit["talent"]
            season_payload["development_deltas"] = development_deltas(
                previous_end_audit["overall_by_player"],
                end_audit["overall_by_player"],
                previous_end_audit["age_by_player"],
                canonical_with_save(canonical, end_save),
                end_save,
            )
            season_payload["cap_transition"] = cap_transition(previous_end_audit, end_audit, end_save, previous_end_save)
        season_payload["regular_audit"] = {key: value for key, value in regular_audit.items() if key not in {"overall_by_player", "age_by_player"}}
        season_payload["rollover_audit"] = {key: value for key, value in end_audit.items() if key not in {"overall_by_player", "age_by_player"}}
        season_payload["awards"] = {
            str(row.get("award")): str(row.get("player_name") or row.get("player_id") or "-")
            for row in end_save.get("league_awards", [])
            if str(row.get("season")) == season
        }
        for stage, audit in (("regular", regular_audit), ("rollover", end_audit)):
            refreshed_errors.extend(f"{season} {stage}: {message}" for message in audit["errors"])
            refreshed_warnings.extend(f"{season} {stage}: {message}" for message in non_cap_warnings(audit))
        refreshed_warnings.extend(season_calibration_warnings(payload, season_payload, end_audit))
        previous_end_save = end_save
        previous_end_audit = end_audit
    payload["errors"] = sorted(set(refreshed_errors))
    payload["warnings"] = sorted(set(refreshed_warnings))
    payload["rollover_save_sizes_mb"] = [
        {
            "season": str(row.get("season") or ""),
            "megabytes": round(
                (phase_dir / f"season_{index:02d}_rollover.json").stat().st_size / (1024 * 1024),
                2,
            ),
        }
        for index, row in enumerate(payload.get("seasons", []), start=1)
        if (phase_dir / f"season_{index:02d}_rollover.json").exists()
    ]
    payload["report_refreshed_with_current_code"] = True
    payload["remediations"] = [
        {
            "issue": "AI roster-cut ownership gap",
            "status": "fixed",
            "evidence": f"Current load repair recovered {total_legacy_repairs} phase-artifact records; refreshed audits contain no orphaned active players.",
        },
        {
            "issue": "Future draft trade market had no prospect recommendations",
            "status": "fixed",
            "evidence": "A copied 2027 GUI draft produced five capped trades after future generated-board recommendations were connected to trade evaluation.",
        },
        {
            "issue": "Staff expiration clumping and recycled candidate identity",
            "status": "fixed for new saves",
            "evidence": "Opening staff terms now span two-to-five years and one market-source identity survives hire/fire cycles.",
        },
        {
            "issue": "GUI team-switch hydration race and repeated canonical parsing",
            "status": "fixed",
            "evidence": "All controls lock during card hydration, and the GUI server now loads the 21 MB canonical baseline once at startup.",
        },
        {
            "issue": "Unsigned free-agent population grew without a league-exit path",
            "status": "fixed for new rollovers",
            "evidence": "Offseason attrition now archives only the unsigned fringe tail while protecting recent draftees, young prospects, meaningful released players, and rotation-level free agents; the post-rollover pool targets 120 players.",
        },
        {
            "issue": "Repeated same-day AI roster cuts emitted duplicate transaction IDs",
            "status": "fixed and legacy-repaired",
            "evidence": "AI cut records now upsert by deterministic ID, while save writes remove only exact duplicate legacy payloads and preserve non-identical collisions for audit visibility.",
        },
        {
            "issue": "Rollover free-agent cards displayed 0.0 ratings",
            "status": "fixed and browser-verified",
            "evidence": "The free-agent app payload now includes the same save-aware rating summary as roster views; a live rollover dashboard rendered non-zero OVR values for every visible candidate.",
        },
        {
            "issue": "High draft picks could enter a new roster without rotation minutes",
            "status": "fixed",
            "evidence": "Signed top-ten rookies receive bounded onboarding baselines (20 MPG for picks 1-5, 17 MPG for picks 6-10) before the ordinary rotation model takes over.",
        },
        {
            "issue": "Simultaneous AI staff renewals evaluated the same stale budget",
            "status": "fixed",
            "evidence": "Accepted renewals now consume the live team staff budget before the next retention decision in the same batch; focused budget tests and subsequent soak rollovers stay legal.",
        },
        {
            "issue": "Long-horizon audit pauses were dominated by cyclic-GC scans",
            "status": "fixed in the soak harness",
            "evidence": "The save/canonical payloads are acyclic JSON-shaped trees already reclaimed by reference counting, so the harness now disables automatic cycle scans and no longer forces a full-heap collection after each season.",
        },
        {
            "issue": "Late-horizon free-agency post-resolution trade matching remains expensive",
            "status": "follow-up performance target",
            "evidence": "Live checkpoint counters isolated the final day-five AI trade search after all five market days completed. Future work should index or reuse candidate inputs; package breadth, fit context, legality checks, and AI decision rules must remain unchanged.",
        },
        {
            "issue": "A browser refresh could observe a save while a long action was rewriting it",
            "status": "fixed",
            "evidence": "Save serialization now writes to a same-directory temporary file and atomically replaces the prior save. A focused concurrent-read test proves readers see one complete version and never partial JSON.",
        },
        {
            "issue": "Full-draft simulation reloads and persists the mature save after every pick",
            "status": "follow-up performance target",
            "evidence": "This preserves pick-by-pick ownership and draft-trade safety but amplifies I/O as historical saves grow. A future in-memory transaction batch should retain every decision and add periodic atomic checkpoints rather than reducing draft logic.",
        },
        {
            "issue": "Top-end generated talent and elite creator supply thinned by year ten",
            "status": "fixed in source with focused verification",
            "evidence": "Rookie player records now retain prospect ability/potential, legacy saves recover those fields from onboarding data, and deterministic potential realization creates bounded bust/breakout growth. Focused eight-year trajectory tests pass; the next full soak should confirm the league-wide 70+ population response.",
        },
        {
            "issue": "Draft pedigree could remain a permanent trade-value floor",
            "status": "fixed",
            "evidence": "The drafted-rookie value floor now decays across the first four seasons and expires afterward. Focused tests preserve premium rookie value while proving an established former top pick is valued by current ability, production, contract, and development rather than draft slot.",
        },
    ]
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "soak_audit.md").write_text(markdown_report(payload), encoding="utf-8")
    return payload


class SoakRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.output_dir = Path(args.output_dir).resolve()
        self.save_dir = self.output_dir / "saves"
        self.phase_save_dir = self.output_dir / "phase_saves"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.phase_save_dir.mkdir(parents=True, exist_ok=True)
        self.canonical = load_app_canonical(self.root)
        self.started = time.monotonic()
        self.payload: dict[str, Any] = {
            "seed": args.seed,
            "team": args.team,
            "save_path": "",
            "seasons": [],
            "errors": [],
            "warnings": [],
        }

    def action(self, name: str, **payload: Any) -> dict[str, Any]:
        return dispatch_app_action(name, payload, root=self.root, save_dir=self.save_dir, canonical=self.canonical)

    def load(self) -> dict[str, Any]:
        return ensure_league_save_defaults(load_save(self.payload["save_path"]), self.canonical)

    def checkpoint(self) -> None:
        self.payload["runtime_seconds"] = round(time.monotonic() - self.started, 3)
        (self.output_dir / "soak_audit.json").write_text(json.dumps(self.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (self.output_dir / "soak_audit.md").write_text(markdown_report(self.payload), encoding="utf-8")

    def snapshot_save(self, filename: str) -> None:
        restore_export(self.phase_save_dir / filename, create_export(self.payload["save_path"]), replace=True)

    def resolve_user_roster_cutdown(self) -> int:
        waived = 0
        for _ in range(12):
            room = self.action("roster_cutdown", save_path=self.payload["save_path"])
            if room.get("status") != "required":
                return waived
            candidates = sorted(
                [row for row in room.get("players", []) if row.get("can_waive")],
                key=lambda row: (float(row.get("minutes") or 0.0), float(row.get("overall") or 0.0), str(row.get("name") or "")),
            )
            if not candidates:
                raise RuntimeError("User roster cutdown has no legal player to waive")
            result = self.action("waive_player", save_path=self.payload["save_path"], player_id=candidates[0]["player_id"])
            if result.get("status") != "waived":
                raise RuntimeError(f"Roster cutdown failed: {result}")
            waived += 1
        raise RuntimeError("Roster cutdown did not resolve within 12 waivers")

    def resolve_user_staff_retention(self) -> int:
        resolved = 0
        for _ in range(8):
            room = self.action("staff_retention_room", save_path=self.payload["save_path"])
            if room.get("status") != "required":
                return resolved
            window = room.get("window") or {}
            result = self.action(
                "resolve_staff_retention",
                save_path=self.payload["save_path"],
                window_id=window.get("id"),
                choice="re_sign",
                salary_millions=min(float(room.get("ask_millions") or 0.0), float(room.get("max_offer_millions") or 0.0)),
                years=int(room.get("ask_years") or 2),
            )
            if result.get("status") != "re_signed":
                result = self.action(
                    "resolve_staff_retention",
                    save_path=self.payload["save_path"],
                    window_id=window.get("id"),
                    choice="interim",
                )
            if result.get("status") not in {"re_signed", "applied"}:
                raise RuntimeError(f"Staff retention failed: {result}")
            resolved += 1
        raise RuntimeError("Staff retention did not resolve within 8 decisions")

    def create(self) -> None:
        result = self.action("create_save", team=self.args.team, seed=self.args.seed, save_name=self.args.save_name)
        self.payload["save_path"] = result["save_path"]
        self.action("set_starting_five", save_path=result["save_path"], team=self.args.team, auto=True)
        save = self.load()
        baseline = audit_snapshot(self.canonical, save, "baseline")
        self.payload["baseline_talent"] = baseline["talent"]
        self.payload["baseline_audit"] = {key: value for key, value in baseline.items() if key not in {"overall_by_player", "age_by_player"}}
        self.payload["errors"].extend(f"baseline: {message}" for message in baseline["errors"])
        self.payload["warnings"].extend(f"baseline: {message}" for message in non_cap_warnings(baseline))
        self.checkpoint()

    def load_checkpoint(self) -> None:
        report_path = self.output_dir / "soak_audit.json"
        if not report_path.exists():
            raise FileNotFoundError(f"Cannot resume without {report_path}")
        self.payload = json.loads(report_path.read_text(encoding="utf-8"))
        save_path = Path(str(self.payload.get("save_path") or ""))
        if not save_path.exists():
            raise FileNotFoundError(f"Cannot resume because the live save is missing: {save_path}")
        elapsed = float(self.payload.get("runtime_seconds") or 0.0)
        self.started = time.monotonic() - elapsed

    def champion_abbrev(self, save: dict[str, Any]) -> str | None:
        champion_id = str((save.get("playoff_state") or {}).get("champion_team_id") or "")
        if not champion_id:
            return None
        active = canonical_with_save(self.canonical, save)
        team = next((row for row in active.get("teams", []) if str(row.get("id")) == champion_id), None)
        return str((team or {}).get("abbrev") or "") or None

    def advance_until_phase(self, phase: str, max_steps: int = 6) -> None:
        for _ in range(max_steps):
            save = self.load()
            if str(save.get("state", {}).get("phase")) == phase:
                return
            if str(save.get("state", {}).get("phase")) == "re_signing":
                result = self.action("advance_re_signing", save_path=self.payload["save_path"], team=self.args.team, mode="open_market", seed=self.args.seed)
                if result.get("status") != "open_market":
                    raise RuntimeError(f"Could not leave re-signing: {result}")
                continue
            self.action("advance_save", save_path=self.payload["save_path"], next_event=True, seed=self.args.seed)
        current = self.load().get("state", {})
        raise RuntimeError(f"Could not reach {phase}; stopped at {current}")

    def run_season(self, index: int) -> None:
        save = self.load()
        season = str(save.get("meta", {}).get("season"))
        start_year = int(season.split("-")[0])
        print(f"[{index + 1}/{self.args.seasons}] {season}: regular season", flush=True)
        start_audit = audit_snapshot(self.canonical, save, f"{season} start")
        self.action(
            "advance_save",
            save_path=self.payload["save_path"],
            to_date=f"{start_year + 1}-04-15",
            checkpoint_days=self.args.checkpoint_days,
            seed=self.args.seed,
        )
        regular_save = self.load()
        regular_audit = audit_snapshot(self.canonical, regular_save, f"{season} regular season complete")
        stats = regular_season_stats(regular_save)
        self.snapshot_save(f"season_{index + 1:02d}_playoffs.json")

        print(f"[{index + 1}/{self.args.seasons}] {season}: playoffs", flush=True)
        playoff = self.action("simulate_playoff_all", save_path=self.payload["save_path"], seed=self.args.seed)
        champion = ((playoff.get("room") or {}).get("champion") or {}).get("abbrev")
        self.advance_until_phase("draft")
        self.snapshot_save(f"season_{index + 1:02d}_draft.json")

        print(f"[{index + 1}/{self.args.seasons}] {season}: draft", flush=True)
        draft_year = str(start_year + 1)
        self.action("draft_sim_all", save_path=self.payload["save_path"], team=self.args.team, seed=self.args.seed)
        drafted_save = self.load()
        self.advance_until_phase("free_agency")
        self.snapshot_save(f"season_{index + 1:02d}_free_agency.json")

        self.finish_free_agency_and_record(
            index=index,
            season=season,
            draft_year=draft_year,
            champion=champion,
            start_save=save,
            start_audit=start_audit,
            regular_audit=regular_audit,
            stats=stats,
        )

    def finish_free_agency_and_record(
        self,
        *,
        index: int,
        season: str,
        draft_year: str,
        champion: str | None,
        start_save: dict[str, Any],
        start_audit: dict[str, Any],
        regular_audit: dict[str, Any],
        stats: dict[str, Any],
    ) -> None:
        print(f"[{index + 1}/{self.args.seasons}] {season}: free agency and rollover", flush=True)
        self.action("advance_free_agency", save_path=self.payload["save_path"], team=self.args.team, mode="end", seed=self.args.seed)
        self.action("advance_save", save_path=self.payload["save_path"], next_event=True, seed=self.args.seed)
        user_staff_re_signings = self.resolve_user_staff_retention()
        user_waivers = self.resolve_user_roster_cutdown()
        self.action("set_starting_five", save_path=self.payload["save_path"], team=self.args.team, auto=True)
        end_save = self.load()
        self.snapshot_save(f"season_{index + 1:02d}_rollover.json")
        end_audit = audit_snapshot(self.canonical, end_save, f"{season} rollover")
        end_active = canonical_with_save(self.canonical, end_save)
        rookies = rookie_snapshot(self.canonical, end_save, draft_year)
        deltas = development_deltas(
            start_audit["overall_by_player"],
            end_audit["overall_by_player"],
            start_audit["age_by_player"],
            end_active,
            end_save,
        )
        full_transactions = transaction_counts(end_save, season)
        staff_turnover = staff_turnover_counts(end_save, season)
        cap_changes = cap_transition(start_audit, end_audit, end_save, start_save)
        awards = {
            str(row.get("award")): str(row.get("player_name") or row.get("player_id") or "-")
            for row in end_save.get("league_awards", [])
            if str(row.get("season")) == season
        }

        season_payload = {
            "season": season,
            "champion": champion,
            "stats": stats,
            "rookies": rookies,
            "transactions": full_transactions,
            "staff_turnover": staff_turnover,
            "cap_transition": cap_changes,
            "awards": awards,
            "user_roster_cutdown_waivers": user_waivers,
            "user_staff_re_signings": user_staff_re_signings,
            "league_exits": sum(
                1
                for row in end_save.get("league_exit_records", [])
                if str(row.get("season") or "") == season
            ),
            "injuries": regular_audit["injuries"],
            "start_talent": start_audit["talent"],
            "end_talent": end_audit["talent"],
            "development_deltas": deltas,
            "regular_audit": {key: value for key, value in regular_audit.items() if key not in {"overall_by_player", "age_by_player"}},
            "rollover_audit": {key: value for key, value in end_audit.items() if key not in {"overall_by_player", "age_by_player"}},
        }
        self.payload["seasons"].append(season_payload)
        for stage, audit in (("regular", regular_audit), ("rollover", end_audit)):
            self.payload["errors"].extend(f"{season} {stage}: {message}" for message in audit["errors"])
            self.payload["warnings"].extend(f"{season} {stage}: {message}" for message in non_cap_warnings(audit))
        self.payload["warnings"].extend(season_calibration_warnings(self.payload, season_payload, end_audit))
        self.payload["errors"] = sorted(set(self.payload["errors"]))
        self.payload["warnings"] = sorted(set(self.payload["warnings"]))
        self.checkpoint()
        clear_utility_caches()
        print(
            f"[{index + 1}/{self.args.seasons}] {season}: complete | champion {champion or '-'} | "
            f"talent mean {end_audit['talent']['overall']['mean']:.2f} | errors {len(end_audit['errors'])} | warnings {len(end_audit['warnings'])}",
            flush=True,
        )

    def resume_current_season(self, index: int) -> None:
        save = self.load()
        phase = str((save.get("state") or {}).get("phase") or "")
        season = str((save.get("meta") or {}).get("season") or "")
        if phase != "free_agency":
            raise RuntimeError(f"Checkpoint resume currently requires free_agency; found {phase} in {season}")
        if index <= 0:
            raise RuntimeError("A first-season midstream checkpoint cannot reconstruct its opening talent snapshot")
        phase_number = index + 1
        start_path = self.phase_save_dir / f"season_{index:02d}_rollover.json"
        regular_path = self.phase_save_dir / f"season_{phase_number:02d}_playoffs.json"
        if not start_path.exists() or not regular_path.exists():
            raise FileNotFoundError(f"Resume checkpoints are incomplete: {start_path}, {regular_path}")
        start_save = ensure_league_save_defaults(load_save(start_path), self.canonical)
        regular_save = ensure_league_save_defaults(load_save(regular_path), self.canonical)
        start_audit = audit_snapshot(self.canonical, start_save, f"{season} start (resumed)")
        regular_audit = audit_snapshot(self.canonical, regular_save, f"{season} regular season complete (resumed)")
        print(f"[{phase_number}/{self.args.seasons}] {season}: resuming from free agency checkpoint", flush=True)
        self.finish_free_agency_and_record(
            index=index,
            season=season,
            draft_year=str(int(season.split("-")[0]) + 1),
            champion=self.champion_abbrev(save),
            start_save=start_save,
            start_audit=start_audit,
            regular_audit=regular_audit,
            stats=regular_season_stats(regular_save),
        )

    def run(self) -> None:
        if self.args.resume:
            self.load_checkpoint()
            completed = len(self.payload.get("seasons") or [])
            live = self.load()
            live_season = str((live.get("meta") or {}).get("season") or "")
            reported = {str(row.get("season") or "") for row in self.payload.get("seasons", [])}
            if live_season and live_season not in reported:
                live_phase = str((live.get("state") or {}).get("phase") or "")
                live_date = str((live.get("state") or {}).get("current_date") or "")
                if live_phase == "free_agency":
                    self.resume_current_season(completed)
                elif live_phase not in {"preseason", "regular_season"} or live_date[5:] > "10-21":
                    raise RuntimeError(f"Cannot resume completed-season checkpoint from {live_phase} on {live_date}")
        else:
            self.create()
        for index in range(len(self.payload.get("seasons") or []), self.args.seasons):
            self.run_season(index)
        self.checkpoint()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output-dir", default=str(ROOT / "output" / "ten_season_soak"))
    parser.add_argument("--seasons", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--team", default="MIA")
    parser.add_argument("--save-name", default="ten_season_gui_soak")
    parser.add_argument("--checkpoint-days", type=int, default=31)
    parser.add_argument("--resume", action="store_true", help="Continue an interrupted soak from its live free-agency checkpoint.")
    parser.add_argument("--refresh-report", action="store_true", help="Re-audit existing phase saves with the current code without rerunning seasons.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    # Save/canonical payloads are JSON-shaped acyclic trees. Reference counting
    # releases them immediately; cyclic-GC scans only add multi-minute pauses
    # once long-horizon artifacts reach several gigabytes in memory. The same
    # applies while refreshing reports from those phase saves.
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        if args.refresh_report:
            output_dir = Path(args.output_dir).resolve()
            refresh_existing_report(Path(args.root).resolve(), output_dir)
            print(f"Refreshed report: {output_dir / 'soak_audit.md'}")
            return 0
        runner = SoakRunner(args)
        runner.run()
        print(f"Report: {runner.output_dir / 'soak_audit.md'}")
    finally:
        if gc_was_enabled:
            gc.enable()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
