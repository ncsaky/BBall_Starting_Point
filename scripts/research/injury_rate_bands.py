#!/usr/bin/env python3
"""Compare the tracker and fixed-roster simulations by age and workload.

Pass paths to simulation runs from output/injuries-2/sim_season.py without their .json suffix.
Rates count injuries and illness that cost at least one game, per 82 games actually played.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_injury_model import TRACKER_ANCHOR_SEASONS as RATE_ANCHOR_SEASONS, rows, season_start
from injury_lengths import sim_event_spells, sim_source
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.injury_model import POSSESSIONS_PER_MINUTE

MINUTES = ((10, "under 10"), (20, "10–under 20"), (30, "20–under 30"), (float("inf"), "30+"))
AGES = ((23, "under 23"), (26, "23–25"), (29, "26–28"), (32, "29–31"), (float("inf"), "32+"))


def aggregate(player_seasons, bands):
    games, injuries = Counter(), Counter()
    for value, played, spells in player_seasons:
        if value is None or played < 10:
            continue
        band = next(label for upper, label in bands if value < upper)
        games[band] += played
        injuries[band] += spells
    return {label: {"games": games[label], "injuries": injuries[label],
                    "per_82": round(82 * injuries[label] / games[label], 3) if games[label] else None}
            for _, label in bands}


def tracker_bands():
    canonical = load_app_canonical(ROOT)
    birthdates = {}
    for player in canonical["players"]:
        birth = player.get("birthdate") or player.get("birth_date")
        if birth:
            birthdates[player["id"]] = date.fromisoformat(str(birth)[:10])
    counts = Counter(
        (row.get("player_id") or row.get("player_key"), row["season"])
        for row in rows("injury_player_history.json")
        if row["season"] in RATE_ANCHOR_SEASONS and int(row.get("games") or 0) >= 1
        and row.get("cat") in ("injury", "illness")
    )
    minutes, ages = [], []
    for row in rows("injury_player_seasons.json"):
        season, gp = row["season"], row.get("gp") or 0
        if season not in RATE_ANCHOR_SEASONS or gp < 10:
            continue
        pid = row.get("player_id")
        count = counts[(pid or row.get("player_key"), season)]
        minutes.append(((row.get("poss") or 0) / gp / POSSESSIONS_PER_MINUTE, gp, count))
        if pid in birthdates:
            ages.append(((season_start(season) - birthdates[pid]).days / 365.25, gp, count))
    return {"minutes": aggregate(minutes, MINUTES), "age": aggregate(ages, AGES)}


def public_bands():
    """Real 2025-26 from the public stretches (data/research/injury_history_2025_26.json, complete for absences that cost
    a game): injury and illness stretches costing a regular-season game, not already underway at the team's opener and
    not injury management only (STAR-INJURIES). Games played and minutes from the box scores; age at opening night."""
    canonical = load_app_canonical(ROOT)
    players = {p["id"]: p for p in canonical["players"]}
    by_espn = {str(p.get("espn_player_id")): p["id"] for p in canonical["players"] if p.get("espn_player_id")}
    doc = json.loads((ROOT / "data/research/injury_history_2025_26.json").read_text())
    counts = Counter(s["player_id"] for s in doc["stretches"]
                     if s["reason_category"] in ("injury", "illness") and s["regular_season_games_missed"] >= 1
                     and not s["at_team_season_start"] and not s["injury_management_only"])
    gp, minutes = Counter(), defaultdict(float)
    for game in json.loads((ROOT / "data/research/game_boxscores_2025_26.json").read_text())["games"]:
        if game.get("phase") != "regular":
            continue
        for line in game["players"]:
            pid = by_espn.get(str(line.get("espn_player_id")))
            if pid and float(line.get("minutes") or 0) > 0:
                gp[pid] += 1
                minutes[pid] += float(line["minutes"])
    opener = date(2025, 10, 21)

    def age(pid):
        birth = players[pid].get("birthdate") or players[pid].get("birth_date")
        return (opener - date.fromisoformat(str(birth)[:10])).days / 365.25 if birth else None

    return {"minutes": aggregate(((minutes[pid] / gp[pid], gp[pid], counts[pid]) for pid in gp), MINUTES),
            "age": aggregate(((age(pid), gp[pid], counts[pid]) for pid in gp), AGES)}


def sim_bands(prefix):
    team_games, events, _, _ = sim_source(prefix)
    player_meta = json.loads(Path(f"{prefix}_players.json").read_text())["meta"]
    counts = Counter(spell["pid"] for spell in sim_event_spells(team_games, events))
    gp, minutes = Counter(), defaultdict(float)
    for game in team_games:
        for player_id, played in game["players"]:
            gp[player_id] += 1
            minutes[player_id] += played
    return {
        "minutes": aggregate(((minutes[pid] / gp[pid], gp[pid], counts[pid]) for pid in gp), MINUTES),
        "age": aggregate(((player_meta[pid].get("age"), gp[pid], counts[pid]) for pid in gp if pid in player_meta), AGES),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    args = parser.parse_args()
    results = {"tracker": tracker_bands(), "public_2025_26": public_bands()}
    results.update({Path(prefix).name: sim_bands(prefix) for prefix in args.runs})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
