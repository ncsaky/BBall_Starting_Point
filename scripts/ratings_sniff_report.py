#!/usr/bin/env python3
"""Ratings sniff test: who does the new-ratings model put on top?

Prints the top players by the player-card header (the AI's own overall / offense / defense on the 50+15z display
scale) with the new 94-input ratings installed, plus where a watch list of well-known players lands. Use it
after rebuilding data/canonical/player_inputs_2026_27.json(.gz) to judge "does this look right".

    PYTHONPATH=src .venv/bin/python scripts/ratings_sniff_report.py [--top 25] [--json-out PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.player_profile import engine_header
from nba_gm_data.ratings_model import install_inputs_model

ROOT = Path(__file__).resolve().parents[1]
WATCH = [
    "Nikola Jokić", "Shai Gilgeous-Alexander", "Victor Wembanyama", "Giannis Antetokounmpo", "Luka Dončić",
    "Anthony Edwards", "Jayson Tatum", "Cade Cunningham", "Jalen Brunson", "Stephen Curry", "Kawhi Leonard",
    "Evan Mobley", "Rudy Gobert", "Draymond Green", "Alex Caruso", "Tyrese Haliburton", "Jalen Williams",
    "Chet Holmgren", "Domantas Sabonis", "Trae Young", "Cooper Flagg",
]


def build() -> list[dict]:
    canonical = load_app_canonical(ROOT)
    install_inputs_model(canonical, ROOT)
    rows = []
    for player in canonical["players"]:
        if not player.get("team_abbrev"):
            continue
        head = engine_header(canonical, player["id"])
        if head:
            rows.append({"name": player["name"], "team": player.get("team_abbrev"), "age": player.get("age"),
                         "ovr": head["ovr"], "off": head["off"], "def": head["def"]})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    rows = build()
    ranks = {key: {r["name"]: i for i, r in enumerate(sorted(rows, key=lambda r: -r[key]), 1)} for key in ("ovr", "off", "def")}
    for key, label in (("ovr", "overall"), ("off", "offense"), ("def", "defense")):
        print(f"\nTop {args.top} by {label}:")
        for r in sorted(rows, key=lambda r: -r[key])[:args.top]:
            print(f"  {ranks[key][r['name']]:>3} {r['name'][:24]:24s} {r['team'] or '':4s} {r['age'] or '':>3}  "
                  f"OVR {r['ovr']:5.1f}  OFF {r['off']:5.1f}  DEF {r['def']:5.1f}")
    print("\nWatch list (rank overall / offense / defense):")
    by_name = {r["name"]: r for r in rows}
    for name in WATCH:
        r = by_name.get(name)
        if r:
            print(f"  {name:26s} #{ranks['ovr'][name]:<4} #{ranks['off'][name]:<4} #{ranks['def'][name]:<4} "
                  f"OVR {r['ovr']:5.1f} OFF {r['off']:5.1f} DEF {r['def']:5.1f}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps({"rows": rows, "ranks": ranks}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
