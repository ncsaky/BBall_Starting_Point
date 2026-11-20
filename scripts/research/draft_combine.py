#!/usr/bin/env python3
"""Build data/research/draft_combine_2000_2025.json: NBA Draft Combine strength and agility results, 2000-2025.

Source: the NBA.com Draft Combine "Strength & Agility" tables (stats.nba.com draftcombinedrillresults, 2000-01 to
2025-26). stats.nba.com refuses scripted requests from this machine, so the table is read from a public mirror of the
same NBA.com export (github.com/nkal22/combine_score, agility_scores.csv), and cross-checked against a second,
independent NBA.com API pull with NBA player ids (github.com/davidmilitaru/NBA_draft_combine,
nba_draft_combine_2013_2019.csv). The check is printed; disagreements are listed, never silently fixed.

Fields kept per player-year: standing vertical leap and max vertical leap (inches), bench press (reps at 185 lb), lane
agility, shuttle run and three-quarter sprint (seconds). "-" in the source means not tested (players often skip drills;
the NBA export also shows a 0-rep bench as "-", so a missing bench is never read as zero).

Usage: python3 scripts/research/draft_combine.py MIRROR_CSV CHECK_CSV
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/research/draft_combine_2000_2025.json"
FIELDS = {"Standing Vert": "standing_vertical_in", "Max Vert": "max_vertical_in", "Max Bench": "bench_reps_185",
          "Lane Agility": "lane_agility_s", "Shuttle Run": "shuttle_run_s", "Three Quarter Sprint": "three_quarter_sprint_s"}
CHECK = {"STANDING_VERTICAL_LEAP": "standing_vertical_in", "MAX_VERTICAL_LEAP": "max_vertical_in",
         "BENCH_PRESS": "bench_reps_185", "LANE_AGILITY_TIME": "lane_agility_s"}


def number(text: str | None) -> float | None:
    text = (text or "").strip()
    if text in ("", "-", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main() -> int:
    mirror, check = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    with mirror.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            raw = {key.replace("\xa0", " ").strip(): value for key, value in raw.items()}
            row = {"name": raw["PLAYER"].strip(), "position": raw.get("POS", "").strip(), "year": int(raw["Year"])}
            for source, key in FIELDS.items():
                row[key] = number(raw.get(source))
            rows.append(row)
    by_key = {(r["name"], r["year"]): r for r in rows}
    compared = agree = 0
    disagreements = []
    with check.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            name, year = (raw.get("PLAYER_NAME_x") or "").strip(), int(float(raw.get("SEASON_YEAR") or 0) or 0)
            mine = by_key.get((name, year))
            if not mine:
                continue
            for source, key in CHECK.items():
                other = number(raw.get(source))
                if other is None or mine[key] is None:
                    continue
                compared += 1
                if abs(other - mine[key]) < 0.051:
                    agree += 1
                else:
                    disagreements.append({"name": name, "year": year, "field": key, "mirror": mine[key], "check": other})
    print(f"{len(rows)} player-years; cross-check: {agree}/{compared} values agree")
    for d in disagreements[:20]:
        print("  disagreement", d)
    OUT.write_text(json.dumps({
        "version": "draft_combine_2000_2025_v1",
        "source": "NBA.com Draft Combine Strength & Agility (stats.nba.com draftcombinedrillresults), 2000-2025",
        "source_urls": ["https://www.nba.com/stats/draft/combine-strength-agility",
                        "https://github.com/nkal22/combine_score/blob/HEAD/agility_scores.csv (mirror of the NBA.com table)",
                        "https://github.com/davidmilitaru/NBA_draft_combine/blob/HEAD/nba_draft_combine_2013_2019.csv (cross-check)"],
        "cross_check": {"compared": compared, "agree": agree, "disagreements": disagreements},
        "notes": "Missing = not tested. Units: inches, reps at 185 lb, seconds.",
        "players": rows,
    }, indent=0, sort_keys=True) + "\n")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
