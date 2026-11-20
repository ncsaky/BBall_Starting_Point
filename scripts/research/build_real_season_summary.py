#!/usr/bin/env python3
"""Summarise the real 2025-26 regular season for a new save's preseason outlook.

Reads the real box scores (data/research/game_boxscores_2025_26.json, ESPN) and writes
data/canonical/real_season_summary_2025_26.json:
  - stints: each player's regular-season minutes and games per team (a traded player has one row per team),
  - teams: each team's real win-loss record,
  - players: season totals (games, minutes, points, rebounds, assists, steals, blocks, threes) for the leaders slide.
Screen assists are not in these box scores. The NBA Cup final is left out (it counts in neither standings nor stats).

Run: PYTHONPATH=src .venv/bin/python scripts/research/build_real_season_summary.py
"""
from __future__ import annotations

import json
from pathlib import Path

from nba_gm_data.utils import normalize_name

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/research/game_boxscores_2025_26.json"
TARGET = ROOT / "data/canonical/real_season_summary_2025_26.json"
ESPN_TO_GAME = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
# The NBA Cup final (Dec 16, 2025, Knicks v Spurs) is in the box scores but counts in neither standings nor season stats.
CUP_FINAL_DATE = "2025-12-16"
TOTALS = ("minutes", "points", "rebounds", "assists", "steals", "blocks", "fg3m")


def abbrev(value: str) -> str:
    return ESPN_TO_GAME.get(value, value)


def main() -> None:
    data = json.loads(SOURCE.read_text())
    stints: dict[tuple[str, str], dict] = {}
    players: dict[str, dict] = {}
    records: dict[str, dict[str, int]] = {}
    games = [g for g in data["games"] if g.get("phase") == "regular" and g.get("date") != CUP_FINAL_DATE]
    for game in games:
        lines = [p for p in game.get("players") or [] if not p.get("dnp") and float(p.get("minutes") or 0) > 0]
        score: dict[str, int] = {}
        for line in game.get("players") or []:
            score.setdefault(abbrev(line["team_abbrev"]), 0)
        for line in lines:
            team = abbrev(line["team_abbrev"])
            score[team] = score.get(team, 0) + int(line.get("points") or 0)
            key = normalize_name(line["player_name"])
            stint = stints.setdefault((key, team), {"name": line["player_name"], "team": team, "games": 0, "minutes": 0.0})
            stint["games"] += 1
            stint["minutes"] += float(line.get("minutes") or 0)
            total = players.setdefault(key, {"name": line["player_name"], "games": 0, **{k: 0.0 for k in TOTALS}})
            total["games"] += 1
            for field in TOTALS:
                total[field] += float(line.get(field) or 0)
            total["team"] = team
        if len(score) == 2:
            (a, pa), (b, pb) = score.items()
            if pa != pb:
                winner, loser = (a, b) if pa > pb else (b, a)
                records.setdefault(winner, {"wins": 0, "losses": 0})["wins"] += 1
                records.setdefault(loser, {"wins": 0, "losses": 0})["losses"] += 1
    out = {
        "season": "2025-26",
        "source": "ESPN box scores, regular season (data/research/game_boxscores_2025_26.json)",
        "game_count": len(games),
        "teams": dict(sorted(records.items())),
        "stints": sorted(({"key": k[0], **{**v, "minutes": round(v["minutes"], 1)}} for k, v in stints.items()),
                         key=lambda row: (row["team"], -row["minutes"])),
        "players": {k: {**v, **{f: round(v[f], 1) for f in TOTALS}} for k, v in sorted(players.items())},
    }
    TARGET.write_text(json.dumps(out, separators=(",", ":"), sort_keys=True) + "\n")
    print(f"{TARGET}: {len(out['stints'])} stints, {len(out['players'])} players, {len(records)} teams")


if __name__ == "__main__":
    main()
