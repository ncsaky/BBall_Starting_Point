#!/usr/bin/env python3
"""Stage 2 shooting/finishing spot-check (S2-SEAM-SHOOTING): kernel vs today's engine vs real 2025-26.

Light job: no game simulation. Writes output/stage2/shooting_check.json and prints markdown tables.
Also prints the league input bridge's coverage report.
    .venv/bin/python scripts/research/s2_shooting_spot_check.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.stage2.league_inputs import compile_league, coverage_report  # noqa: E402
from nba_gm_data.stage2.shooting_check import LABELS, run  # noqa: E402


def pct(x):
    return "" if x is None else f"{100 * x:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output/stage2/shooting_check.json"))
    ap.add_argument("--refresh-bridge", action="store_true")
    args = ap.parse_args()
    t0 = time.perf_counter()
    compile_league(ROOT, refresh=args.refresh_bridge)
    coverage = coverage_report(ROOT)
    result = run(ROOT)
    result["coverage"] = coverage
    result["seconds"] = round(time.perf_counter() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1, default=str))

    print(f"Bridge: {coverage['players']} players, offense {coverage['offense_compiled']}, interior "
          f"{coverage['interior_compiled']}, errors {len(coverage['errors'])}, compile {coverage['compile_seconds']}s")
    print(f"Rotation players with real shooting: {result['players']}  ({result['seconds']} s)\n")
    print("| Shot type | Attempts | Real | Kernel | Kernel bias | Kernel error beyond noise | Kernel corr | Today | Today bias | Today error beyond noise | Today corr |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for shot, row in result["kernel"].items():
        t = result["today"].get(shot, {})
        print(f"| {LABELS[shot]} | {row['attempts']:,} | {pct(row['real'])} | {pct(row['predicted'])} | {100*row['bias']:+.1f} | "
              f"{pct(row['excess_rmse'])} | {row['corr']} | {pct(t.get('predicted'))} | "
              f"{'' if not t else f'{100*t['bias']:+.1f}'} | {pct(t.get('excess_rmse'))} | {t.get('corr', '')} |")
    print("\nHeld-out half (players the refit never saw):")
    print("| Shot type | Real | Kernel as built | error | Kernel refit | error | Today | error |")
    print("|---|---|---|---|---|---|---|---|")
    for shot, row in result["kernel_held_out"].items():
        r = result["refit_held_out"].get(shot, {})
        t = result["today_held_out"].get(shot, {})
        print(f"| {LABELS[shot]} | {pct(row['real'])} | {pct(row['predicted'])} | {pct(row['excess_rmse'])} | "
              f"{pct(r.get('predicted'))} | {pct(r.get('excess_rmse'))} | {pct(t.get('predicted'))} | {pct(t.get('excess_rmse'))} |")
    print("\nKernel coefficients:", result["kernel_coefficients"])
    print("Refit coefficients:", result["refit_coefficients"], result["refit_history"])
    print("\n| Shot type | Real | Refit (all players) | bias | error beyond noise | corr |")
    print("|---|---|---|---|---|---|")
    for shot, row in result["refit_all"].items():
        print(f"| {LABELS[shot]} | {pct(row['real'])} | {pct(row['predicted'])} | {100*row['bias']:+.1f} | {pct(row['excess_rmse'])} | {row['corr']} |")
    print("\nLeague:", json.dumps(result["league"]), "\nLeague (refit):", json.dumps(result["league_refit"]))
    print("\nKernel rim with the kernel's own finish mix:", json.dumps(result["kernel_kernel_rim_mix"].get("rim")))
    print("\nTiming (microseconds per call):", result["timing_us"])
    for key, side in (("misses", "over"), ("misses", "under"), ("misses_refit", "over"), ("misses_refit", "under")):
        print(f"\n[{key}] Biggest kernel {side}-predictions (season field-goal points on real attempts):")
        print("| Player | Points | per 100 shots | FGA | rim k/r | short k/r | long k/r | corner k/r | ATB k/r |")
        print("|---|---|---|---|---|---|---|---|---|")
        for m in result[key][side]:
            z = m["zones"]
            cell = lambda k: f"{pct(z[k][0])}/{pct(z[k][1])} ({z[k][2]})" if k in z else ""
            print(f"| {m['name']} | {m['points']:+.0f} | {m['per100']:+.1f} | {m['fga']} | {cell('rim')} | {cell('short_mid')} | "
                  f"{cell('long_mid')} | {cell('corner3')} | {cell('atb3')} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
