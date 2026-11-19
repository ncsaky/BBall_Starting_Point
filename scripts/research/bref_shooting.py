#!/usr/bin/env python3
"""Parse Basketball-Reference season shooting + totals pages into a compact per-player table (public data).

Source pages (fetched once by hand with curl, kept in output/ratings-consensus/raw/, never re-fetched here):
  https://www.basketball-reference.com/leagues/NBA_{2024,2025,2026}_shooting.html
  https://www.basketball-reference.com/leagues/NBA_{2024,2025,2026}_totals.html
Season label = the page year's season (NBA_2026 = 2025-26). A player traded mid-season keeps only his combined row.

Fields per player-season: minutes, games, FGA, 3PA, 3PM, share of FGA at 0-3 ft, dunk share of FGA, dunks made (as
Basketball-Reference counts them), share of threes from the corners and corner 3P%.

Writes data/research/bref_shooting_2024_2026.json, read by nba_gm_data.public_shot_evidence.

    python3 scripts/research/bref_shooting.py [--raw output/ratings-consensus/raw]
"""
from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/research/bref_shooting_2024_2026.json"
SEASONS = {2024: "2023-24", 2025: "2024-25", 2026: "2025-26"}
SOURCES = "https://www.basketball-reference.com/leagues/NBA_{year}_{page}.html"


class _Rows(HTMLParser):
    """Collect <tr> rows of the table with the given id as {data-stat: text}, plus the player's BRef id."""

    def __init__(self, table_id: str):
        super().__init__()
        self.table_id, self.in_table, self.depth = table_id, False, 0
        self.rows: list[dict[str, str]] = []
        self.row: dict[str, str] | None = None
        self.cell: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table" and a.get("id") == self.table_id:
            self.in_table, self.depth = True, 0
        if not self.in_table:
            return
        if tag == "table":
            self.depth += 1
        elif tag == "tr":
            self.row = {}
        elif tag in ("td", "th") and self.row is not None:
            self.cell = a.get("data-stat")
            if self.cell == "name_display" and a.get("data-append-csv"):
                self.row["bref_id"] = a["data-append-csv"]
            self.row.setdefault(self.cell, "")

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag in ("td", "th"):
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row.get("name_display") and self.row.get("ranker"):
                self.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.in_table = False

    def handle_data(self, data):
        if self.row is not None and self.cell:
            self.row[self.cell] += data


def _table(path: Path, table_id: str) -> list[dict[str, str]]:
    parser = _Rows(table_id)
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.rows


def _num(text: str | None) -> float | None:
    try:
        return float(str(text).strip()) if str(text or "").strip() else None
    except ValueError:
        return None


def _first_rows(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """BRef lists a traded player's combined row first; keep one row per player id."""
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("bref_id") or row["name_display"]
        out.setdefault(key, row)
    return out


def parse(raw: Path) -> dict:
    players: dict[str, dict] = {}
    for year, season in SEASONS.items():
        shooting = _first_rows(_table(raw / f"bref_shooting_{year}.html", "shooting"))
        totals = _first_rows(_table(raw / f"bref_totals_{year}.html", "totals_stats"))
        for key, row in shooting.items():
            tot = totals.get(key, {})
            fga = _num(tot.get("fga"))
            entry = {
                "minutes": _num(row.get("mp")), "games": _num(row.get("games")), "team": row.get("team_name_abbr"),
                "fga": fga, "fg3a": _num(tot.get("fg3a")), "fg3": _num(tot.get("fg3")),
                "pct_fga_00_03": _num(row.get("pct_fga_00_03")), "fg_pct_00_03": _num(row.get("fg_pct_00_03")),
                "pct_fga_dunk": _num(row.get("pct_fga_dunk")), "dunks": _num(row.get("fg_dunk")),
                "pct_fg3a_corner3": _num(row.get("pct_fg3a_corner3")), "fg_pct_corner3": _num(row.get("fg_pct_corner3")),
            }
            doc = players.setdefault(key, {"name": row["name_display"].strip(), "seasons": {}})
            doc["seasons"][season] = entry
    return {"source": "Basketball-Reference season shooting and totals pages",
            "urls": [SOURCES.format(year=y, page=p) for y in SEASONS for p in ("shooting", "totals")],
            "fetched": "2026-11-19", "players": players}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=ROOT / "output/ratings-consensus/raw")
    args = ap.parse_args()
    data = parse(args.raw)
    OUT.write_text(json.dumps(data, indent=0, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(len(p["seasons"]) for p in data["players"].values())
    print(f"{len(data['players'])} players, {n} player-seasons -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
