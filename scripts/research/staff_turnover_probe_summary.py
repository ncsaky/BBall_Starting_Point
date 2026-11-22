"""Compare consecutive opening-night staff snapshots from two_season_league_probe.py."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from nba_gm_data.staff import COORDINATOR_SLOTS, STAFF_SLOTS


def summarize(first: dict, following: dict, season: str) -> dict:
    teams = set(first["team_ids"]) - set(first["human_team_ids"])
    old = {(row["team_id"], row["slot"]): row for row in first["slots"]}
    new = {(row["team_id"], row["slot"]): row for row in following["slots"]}

    def changed(team: str, role: str) -> bool:
        return old[team, role]["person_id"] != new[team, role]["person_id"]

    coach_changed = {team for team in teams if changed(team, "head_coach")}
    expiring_neutral = [
        (team, slot) for team in teams for slot in COORDINATOR_SLOTS
        if old[team, slot].get("starting_ratings") == "neutral" and old[team, slot].get("years_remaining") == 1
    ]
    head_fires = [
        row for row in following["firings"]
        if row["season"] == season and row["slot"] == "head_coach" and row["team_id"] in teams
    ]
    regular_cutoff = f"{int(season[:4]) + 1}-04-13"
    in_season = [
        row for row in head_fires if (row.get("review_period") == "in_season")
        or (not row.get("review_period") and row["date"] < regular_cutoff)
    ]

    def bench(cohort: set[str]) -> dict:
        moves = [sum(changed(team, slot) for slot in COORDINATOR_SLOTS) for team in cohort]
        return {
            "teams": len(cohort),
            "changes_per_team": mean(moves) if moves else None,
            "turnover_share": mean(moves) / len(COORDINATOR_SLOTS) if moves else None,
            "teams_by_number_of_changes": [moves.count(n) for n in range(len(COORDINATOR_SLOTS) + 1)],
        }

    return {
        "season": season,
        "snapshots": [first["date"], following["date"]],
        "ai_teams": len(teams),
        "head_fired_in_season": len(in_season),
        "head_fired_in_summer": len(head_fires) - len(in_season),
        "head_changed_opening_to_opening": len(coach_changed),
        "head_firings": head_fires,
        "coordinators_changed": sum(changed(team, slot) for team in teams for slot in COORDINATOR_SLOTS),
        "expiring_neutral_coordinators": {
            "cases": len(expiring_neutral),
            "kept": sum(not changed(team, slot) for team, slot in expiring_neutral),
        },
        "returning_coach_bench": bench(teams - coach_changed),
        "new_coach_bench": bench(coach_changed),
        "support_departures_by_role": {
            role: sum(changed(team, role) for team in teams)
            for role in STAFF_SLOTS if role not in (*COORDINATOR_SLOTS, "head_coach")
        },
        "interims_at_following_opening": sorted(
            f"{team}:{role}" for team in teams for role in STAFF_SLOTS if new[team, role]["interim"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("probe_dir", type=Path)
    args = parser.parse_args()
    files = sorted(args.probe_dir.glob("staff_opening_*.json"))
    if len(files) < 3:
        parser.error("need at least three opening snapshots to report two complete seasons")
    snapshots = [json.loads(path.read_text()) for path in files]
    seasons = [path.stem.removeprefix("staff_opening_") for path in files]
    rows = [summarize(first, following, season) for first, following, season in zip(snapshots, snapshots[1:], seasons)]
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
