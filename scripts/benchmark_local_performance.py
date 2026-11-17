"""Compare dashboard reads and lineups on a disposable copy of a save."""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import statistics
import tempfile
import time
from unittest.mock import patch

from nba_gm_data import save as engine
from nba_gm_data.app_actions import dispatch_app_action, invalidate_read_cache, load_app_canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Save JSON; its entire directory is copied before use")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    reference = runpy.run_path(str(root / "tests/test_lineup_performance.py"))["reference_auto_starting_five"]
    optimized = engine.auto_starting_five
    started = time.perf_counter()
    canonical = load_app_canonical(root)
    report = {"canonical_load_seconds": time.perf_counter()-started,
              "note": "Unprofiled timings on this machine, not a cross-device guarantee. All operations use temporary copies.",
              "cold_dashboard_seconds": {}, "warm_dashboard_seconds": {}}
    with tempfile.TemporaryDirectory(prefix="nba-performance-") as tmp:
        copied = Path(tmp) / "fixture"
        shutil.copytree(args.fixture.resolve().parent, copied)
        save_path = copied / args.fixture.name
        snapshots = {}
        for name, optimizer in [("reference", reference), ("optimized", optimized)]:
            cold, warm = [], []
            with patch.object(engine, "auto_starting_five", optimizer):
                for _ in range(3):
                    invalidate_read_cache(save_path)
                    started = time.perf_counter()
                    snapshots[name] = dispatch_app_action("dashboard_snapshot", {"save_path": str(save_path)},
                                                         root=root, save_dir=copied, canonical=canonical)
                    cold.append(time.perf_counter()-started)
                    started = time.perf_counter()
                    dispatch_app_action("dashboard_snapshot", {"save_path": str(save_path)},
                                        root=root, save_dir=copied, canonical=canonical)
                    warm.append(time.perf_counter()-started)
            report["cold_dashboard_seconds"][name] = {"samples": cold, "median": statistics.median(cold)}
            report["warm_dashboard_seconds"][name] = {"samples": warm, "median": statistics.median(warm)}
        assert snapshots["reference"] == snapshots["optimized"], "Dashboard output changed"
        report["dashboard_exact_match"] = True
        raw_save = json.loads(save_path.read_text())
        active = engine.canonical_with_save(canonical, raw_save)
        teams = sorted({p["team_id"] for p in active["players"] if p.get("team_id")})
        for team_id in teams:
            assert optimized(active, raw_save, team_id) == reference(active, raw_save, team_id), team_id
        report["real_team_lineups_exact_match"] = len(teams)
        # A week exercises simulation, injuries, AI checkpoints and dashboard refresh.
        results = {}
        for name, optimizer in [("reference", reference), ("optimized", optimized)]:
            directory = Path(tmp) / name
            shutil.copytree(copied, directory)
            path = directory / args.fixture.name
            with patch.object(engine, "auto_starting_five", optimizer):
                started = time.perf_counter()
                dispatch_app_action("advance_save", {"save_path": str(path), "days": 7, "seed": 7},
                                    root=root, save_dir=directory, canonical=canonical)
                report.setdefault("advance_week_seconds", {})[name] = time.perf_counter()-started
            saved = json.loads(path.read_text())
            results[name] = {key: saved[key] for key in ["team_records", "player_season_stats", "health_states", "starting_lineups"] if key in saved}
        assert results["reference"] == results["optimized"], "Seeded week state changed"
        report["seeded_week_compared_fields"] = list(results["optimized"])
        report["seeded_week_exact_match"] = True
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
