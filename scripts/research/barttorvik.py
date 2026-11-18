"""Barttorvik (T-Rank) college player tables: column map and loader.

Raw files (local only, git-ignored): data/research/barttorvik/raw/players_<season>.csv, one per season, from
https://barttorvik.com/getadvstats.php?year=<season>&csv=1 (season = the spring year, so 2026 = 2025-26).
The CSV has no header row; the names below were matched by hand against the site's player finder
(Bennett Stirtz and Cooper Flagg 2025, Towns/Okafor/Kaminsky 2015, Zion 2019). Columns 72-77 are not yet identified.

Usage:  PYTHONPATH=scripts/research python -c "import barttorvik; print(len(barttorvik.load(2025)))"
"""
from __future__ import annotations

import csv
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "research" / "barttorvik" / "raw"
SEASONS = range(2008, 2027)

COLUMNS = [
    "name", "team", "conf", "games", "min_pct", "ortg", "usg", "efg", "ts", "orb_pct",              # 0-9
    "drb_pct", "ast_pct", "tov_pct", "ftm", "fta", "ft_pct", "two_m", "two_a", "two_pct", "three_m",  # 10-19
    "three_a", "three_pct", "blk_pct", "stl_pct", "ftr", "class_year", "height", "jersey",            # 20-27
    "porpag", "adj_oe", "fouls_committed_per40", "season", "player_id", "hometown",                    # 28-33
    "recruit_rating",        # 34: recruiting composite (about 0-100; blank when unranked)
    "ast_to", "rim_m", "rim_a", "mid_m", "mid_a", "rim_pct", "mid_pct",                                # 35-41  (rim = "close 2", mid = "far 2")
    "dunk_m", "dunk_a", "dunk_pct",                                                                    # 42-44
    "nba_pick",              # 45: eventual NBA draft pick (on every college season of a drafted player; blank/0 = undrafted)
    "drtg", "adj_drtg", "dporpag", "stops",                                                            # 46-49
    "bpm", "obpm", "dbpm", "gbpm", "mpg", "ogbpm", "dgbpm",                                           # 50-56  (site's BPM/OBPM/DBPM = gbpm/ogbpm/dgbpm)
    "oreb_pg", "dreb_pg", "reb_pg", "ast_pg", "stl_pg", "blk_pg", "pts_pg",                            # 57-63
    "role",                  # 64: e.g. "Scoring PG", "Wing F", "Stretch 4", "C" (blank in 2008)
    "three_per100",          # 65
    "birth_date",            # 66: YYYY-MM-DD
    "dunk_ast_pct", "rim_ast_pct", "mid_ast_pct", "two_ast_pct", "three_ast_pct",                      # 67-71  (share of makes assisted)
    "unknown_72", "unknown_73", "unknown_74", "unknown_75", "unknown_76", "unknown_77",
]

TEXT = {"name", "team", "conf", "class_year", "height", "hometown", "role", "birth_date", "player_id", "jersey"}


def _value(key: str, raw: str):
    if key in TEXT:
        return raw
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return raw


def height_inches(height: str) -> float | None:
    try:
        feet, inches = height.split("-")
        return 12 * int(feet) + int(inches)
    except (ValueError, AttributeError):
        return None


def load(season: int, raw_dir: Path = RAW_DIR) -> list[dict]:
    rows = []
    with open(raw_dir / f"players_{season}.csv", newline="", encoding="utf-8") as handle:
        for raw in csv.reader(handle):
            row = {key: _value(key, raw[i]) if i < len(raw) else None for i, key in enumerate(COLUMNS)}
            row["height_in"] = height_inches(row["height"])
            pick = row.get("nba_pick")
            row["nba_pick"] = int(pick) if isinstance(pick, float) and pick > 0 else None
            rows.append(row)
    return rows


def load_all(raw_dir: Path = RAW_DIR) -> list[dict]:
    return [row for season in SEASONS if (raw_dir / f"players_{season}.csv").exists() for row in load(season, raw_dir)]


if __name__ == "__main__":
    total = 0
    for season in SEASONS:
        rows = load(season)
        total += len(rows)
        drafted = sum(1 for r in rows if r["nba_pick"])
        print(f"{season}: {len(rows)} players, {drafted} with an NBA draft pick")
    print("total", total)
