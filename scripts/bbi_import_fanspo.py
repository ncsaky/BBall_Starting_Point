#!/usr/bin/env python3
"""Import Basketball Index report-card batches captured by scripts/bbi_capture_browser.js.

Each downloaded batch (bbi_<season>[_tag]_batchNN.json) is:
1. archived compressed and unchanged under data/research/bbi/captures/fanspo_profiles/<season>/originals/,
2. converted to the importer's long form (one row per player x stat; section and definition kept), and
3. imported with nba_gm_data.bbi_import into the normalized BBI cache the estimator reads.

    PYTHONPATH=src .venv/bin/python scripts/bbi_import_fanspo.py ~/Downloads/bbi_2025-26_batch00.json [...]
    PYTHONPATH=src .venv/bin/python scripts/bbi_import_fanspo.py --from-downloads   # all bbi_*.json there
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
ARCHIVE = ROOT / "data/research/bbi/captures/fanspo_profiles"
DOWNLOADS = Path.home() / "Downloads"


def convert(batch: dict) -> tuple[dict, dict]:
    season = batch["season"]
    columns = ["Player", "BBI ID", "Season", "metric_name", "raw_value", "percentile", "grade",
               "section", "definition", "profile_context", "profile_url"]
    rows, metrics = [], {}
    for profile in batch["profiles"]:
        for r in profile["rows"]:
            locked = "MEMBERS" in (str(r.get("value")), str(r.get("percentile")))
            rows.append([
                profile["name"], profile.get("nba_id"), season, r["stat"],
                None if locked or r.get("value") in ("—", "") else r.get("value"),
                None if locked or r.get("percentile") in ("—", "") else r.get("percentile"),
                None if locked or r.get("grade") in ("—", "") else r.get("grade"),
                r.get("section"), r.get("definition"), profile.get("meta"), profile.get("url"),
            ])
            metrics.setdefault(r["stat"], {"evidence_kind": "unknown", "units": "as_displayed", "sample_unit": None,
                                           "percentile_higher_is_better": None, "section": r.get("section"),
                                           "definition": r.get("definition")})
    table = {"columns": columns, "rows": rows}
    metadata = {
        "source_url": batch.get("source", "https://fanspo.com") + "/bball-index/player-profiles",
        "retrieved_at_utc": batch.get("captured_at"),
        "provider_as_of": None,
        "season": season,
        "season_type": "regular",
        "dataset_kind": "observed",
        "row_scope": "season_total",
        "representation": "long_form",
        "percentile_scale": "0-100 as displayed",
        "percentile_population": "unknown (Fanspo/BBI player report card)",
        "filters": {"players": "per-player report cards", "display": "Full data"},
        "capture_method": "rendered member-visible report card read in the user's browser (scripts/bbi_capture_browser.js)",
        "displayed_rows": len(rows),
        "pagination": {"page": None, "page_size": None, "total_pages": None, "export_includes_all_pages": "not_applicable"},
        "metrics": metrics,
        "column_map": {},
        "aliases": {},
        "notes": "Locked (members-only) cells are null with the row retained; see the original batch archive.",
    }
    return table, metadata


def import_file(path: Path, cache_dir: Path | None = None) -> dict:
    batch = json.loads(path.read_text())
    if batch.get("kind") != "bbi-fanspo-profiles":
        raise ValueError(f"{path} is not a Fanspo report-card batch")
    season = batch["season"]
    folder = ARCHIVE / season
    (folder / "originals").mkdir(parents=True, exist_ok=True)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()[:16]
    original = folder / "originals" / f"{path.stem}.{digest}.json.gz"
    if not original.exists():
        with gzip.open(original, "wb") as handle:
            handle.write(raw)
    table, metadata = convert(batch)
    long_path = folder / f"{path.stem}.long.json"
    meta_path = folder / f"{path.stem}.metadata.json"
    long_path.write_text(json.dumps(table, ensure_ascii=False))
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=1))
    cmd = [sys.executable, "-m", "nba_gm_data.bbi_import", str(long_path), "--metadata", str(meta_path)]
    if cache_dir:
        cmd += ["--cache-dir", str(cache_dir)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"})
    return {"file": path.name, "season": season, "profiles": len(batch["profiles"]), "rows": len(table["rows"]),
            "archived": str(original.relative_to(ROOT)), "import_exit": result.returncode,
            "import_output": (result.stdout or result.stderr)[-1500:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--from-downloads", action="store_true")
    parser.add_argument("--cache-dir", type=Path, help="Isolated importer cache (for tests); default is the real cache")
    parser.add_argument("--move", action="store_true", help="Move imported downloads into the archive folder")
    args = parser.parse_args()
    files = list(args.files)
    if args.from_downloads:
        files += sorted(DOWNLOADS.glob("bbi_*_batch*.json"))
    for path in files:
        summary = import_file(path, args.cache_dir)
        print(json.dumps({k: v for k, v in summary.items() if k != "import_output"}))
        if summary["import_exit"] != 0:
            print(summary["import_output"])
        elif args.move:
            shutil.move(str(path), str(ARCHIVE / summary["season"] / "originals" / path.name))


if __name__ == "__main__":
    main()
