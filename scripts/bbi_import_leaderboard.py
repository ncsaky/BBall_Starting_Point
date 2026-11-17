#!/usr/bin/env python3
"""Import Basketball Index Leaderboards Tool captures made by scripts/bbi_capture_leaderboard.js.

Each downloaded file (bbi_leaderboard_<Display>_chunksNN-MM.json) holds several queries. Each query covers up
to 10 metrics for every player-season (2013-14 onward), with each metric's value and its percentile column.
This script:
1. archives the original file compressed and unchanged under data/research/bbi/captures/leaderboard/originals/,
2. converts every query to the importer's long form (player x season x metric, minutes kept as context), and
3. imports it with nba_gm_data.bbi_import into the normalized BBI cache the estimator reads.

    PYTHONPATH=src .venv/bin/python scripts/bbi_import_leaderboard.py ~/Downloads/bbi_leaderboard_Values_chunks00-04.json
    PYTHONPATH=src .venv/bin/python scripts/bbi_import_leaderboard.py --from-downloads [--move]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Reviewed name aliases (provider spelling -> canonical player id). Only verified same-person pairs.
REVIEWED_ALIASES = {"Jimmy Butler": "player_gsw-jimmy-butler-iii"}
ARCHIVE = ROOT / "data/research/bbi/captures/leaderboard"
DOWNLOADS = Path.home() / "Downloads"
ID_COLUMNS = ("", "Season", "Player", "Age", "Team(s)", "Minutes", "Rotation Role", "Offensive Role", "Defensive Role")


def query_to_long(query: dict) -> list[list]:
    cols = query["columns"]
    index = {c: i for i, c in enumerate(cols)}
    metrics = [c for c in cols if c not in ID_COLUMNS and not c.endswith("_percentile")]
    out = []
    for row in query["rows"]:
        base = [row[index["Player"]], row[index["Season"]], row[index["Team(s)"]], row[index["Minutes"]],
                row[index["Age"]], row[index["Rotation Role"]], row[index["Offensive Role"]], row[index["Defensive Role"]]]
        for metric in metrics:
            pct_col = index.get(metric + "_percentile")
            value = row[index[metric]]
            pct = row[pct_col] if pct_col is not None else None
            out.append([*base, metric, None if value in ("", "NA") else value, None if pct in ("", "NA") else pct])
    return out


def import_file(path: Path, cache_dir: Path | None = None) -> dict:
    data = json.loads(path.read_text())
    if data.get("kind") != "bbi-leaderboard":
        raise ValueError(f"{path} is not a leaderboard capture")
    (ARCHIVE / "originals").mkdir(parents=True, exist_ok=True)
    raw = path.read_bytes()
    original = ARCHIVE / "originals" / f"{path.stem}.{hashlib.sha256(raw).hexdigest()[:16]}.json.gz"
    if not original.exists():
        with gzip.open(original, "wb") as handle:
            handle.write(raw)
    columns = ["Player", "Season", "Team", "Minutes", "Age", "Rotation Role", "Offensive Role", "Defensive Role",
               "metric_name", "raw_value", "percentile"]
    rows: list[list] = []
    metric_meta: dict[str, dict] = {}
    for query in data["queries"]:
        rows.extend(query_to_long(query))
        for metric in query["metrics"]:
            metric_meta[metric.replace(" *", "")] = {"evidence_kind": "unknown", "units": "as_displayed",
                                                    "sample_unit": "minutes", "percentile_higher_is_better": None}
    long_path = ARCHIVE / f"{path.stem}.long.json"
    meta_path = ARCHIVE / f"{path.stem}.metadata.json"
    long_path.write_text(json.dumps({"columns": columns, "rows": rows}, ensure_ascii=False))
    meta_path.write_text(json.dumps({
        "source_url": data.get("tool"), "retrieved_at_utc": data.get("captured_at"), "provider_as_of": None,
        "season": "multi", "season_type": "regular", "dataset_kind": "observed", "row_scope": "season_total",
        "representation": "long_form", "percentile_scale": "0-100 as displayed",
        "percentile_population": "BBI Leaderboards Tool default (Values display; percentile columns as returned)",
        "filters": {"minimum_minutes": 1, "seasons": "2014-2026 (ending year)", "players": "all", "display": data.get("display")},
        "capture_method": "member-visible Leaderboards Tool table, all rows shown, read in the user's browser",
        "displayed_rows": len(rows),
        "pagination": {"page": None, "page_size": None, "total_pages": None, "export_includes_all_pages": "all rows shown"},
        "metrics": metric_meta, "column_map": {}, "aliases": REVIEWED_ALIASES,
    }, ensure_ascii=False, indent=1))
    cmd = [sys.executable, "-m", "nba_gm_data.bbi_import", str(long_path), "--metadata", str(meta_path)]
    if cache_dir:
        cmd += ["--cache-dir", str(cache_dir)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                            env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"})
    if result.returncode == 0:
        long_path.unlink(missing_ok=True)  # the importer keeps its own raw copy; avoid a second large file
    return {"file": path.name, "queries": len(data["queries"]), "metrics": len(metric_meta), "rows": len(rows),
            "archived": str(original.relative_to(ROOT)), "import_exit": result.returncode,
            "import_output": (result.stdout or result.stderr)[-1500:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--from-downloads", action="store_true")
    parser.add_argument("--cache-dir", type=Path, help="Isolated importer cache (for tests); default is the real cache")
    parser.add_argument("--move", action="store_true", help="Move imported downloads into the archive")
    args = parser.parse_args()
    files = list(args.files) + (sorted(DOWNLOADS.glob("bbi_leaderboard_*.json")) if args.from_downloads else [])
    for path in files:
        summary = import_file(path, args.cache_dir)
        print(json.dumps({k: v for k, v in summary.items() if k != "import_output"}))
        if summary["import_exit"] != 0:
            print(summary["import_output"])
        elif args.move:
            shutil.move(str(path), str(ARCHIVE / "originals" / path.name))


if __name__ == "__main__":
    main()
