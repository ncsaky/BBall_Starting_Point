#!/usr/bin/env python3
"""Fit box_variation.SHOT_DIFFICULTY_SHARE to real 2025-26 true shooting (replaying the season with real minutes).

For each candidate k the whole regular season is replayed (same seed; game scores and team totals do not depend on
k, only how a team's two-point misses are shared between its players) and every one of the 150 heaviest-minute
players' simulated true shooting is compared with his real 2025-26 true shooting. Reported: mean absolute error
(all 150, and separately the even- and odd-ranked halves so the choice can be checked out of sample), the mean
signed error of the 15 players with the highest shot difficulty tolerance and of the 25% highest-usage players.
For comparison the same share can be driven by the engine's usage estimate instead (--feature usage) to check
whether shot difficulty adds anything beyond usage.

Usage: PYTHONPATH=src .venv/bin/python scripts/fit_shot_difficulty_share.py [--ks 0,0.25,0.5,0.75,1] [--feature shot_difficulty]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data import box_variation  # noqa: E402
from nba_gm_data.calibration_targets import aggregate_from_results  # noqa: E402
from nba_gm_data.ratings_model import load_league_inputs  # noqa: E402
from nba_gm_data.schema import to_plain  # noqa: E402
from nba_gm_data.sim import build_sim_indices, load_sim_context, sim_game_with_context  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ks", default="0,0.25,0.5,0.75,1.0")
    ap.add_argument("--feature", default="shot_difficulty", choices=["shot_difficulty", "usage"])
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    if args.feature == "usage":
        box_variation.DIFFICULTY_FEATURE, box_variation.DIFFICULTY_REF, box_variation.DIFFICULTY_SD = "usage", 50.0, 12.0
    context = load_sim_context(ROOT)
    context["indices"] = build_sim_indices(context)
    games = sorted([g for g in context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")],
                   key=lambda g: str(g.get("externalGameId")))
    targets = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    ranked = [pid for pid, _ in sorted(targets.items(), key=lambda kv: -(kv[1].get("minutes") or 0))[:150]]
    inputs = load_league_inputs()
    t04 = {pid: inputs[pid]["T04"]["value"]["probability"] for pid in ranked if pid in inputs and "T04" in inputs[pid]}
    top_difficulty = sorted(t04, key=lambda p: -t04[p])[:15]
    by_usage = sorted(ranked, key=lambda p: -(targets[p].get("usage_pct") or 0))
    high_usage = by_usage[: len(by_usage) // 4]
    rows = []
    for k in [float(x) for x in args.ks.split(",")]:
        box_variation.SHOT_DIFFICULTY_SHARE = k
        results = [to_plain(sim_game_with_context(context, str(g["externalGameId"]), mode="replay-real-minutes", seed=args.seed))
                   for g in games]
        lines = aggregate_from_results(results)["player_lines"]
        err = {p: lines[p]["ts_pct"] - targets[p]["ts_pct"] for p in ranked if p in lines and lines[p].get("ts_pct") is not None}
        mean_abs = lambda ps: statistics.fmean(abs(err[p]) for p in ps if p in err)
        mean = lambda ps: statistics.fmean(err[p] for p in ps if p in err)
        row = {"k": k, "mae_all": mean_abs(ranked), "mae_even": mean_abs(ranked[::2]), "mae_odd": mean_abs(ranked[1::2]),
               "top15_difficulty_mean": mean(top_difficulty), "top15_difficulty_mae": mean_abs(top_difficulty),
               "high_usage_mean": mean(high_usage)}
        rows.append(row)
        print(f"k {k:4.2f}  TS mean abs error {row['mae_all']:.4f} (even {row['mae_even']:.4f}, odd {row['mae_odd']:.4f})"
              f"  top-15 shot difficulty: mean {row['top15_difficulty_mean']:+.4f} abs {row['top15_difficulty_mae']:.4f}"
              f"  top-quarter usage mean {row['high_usage_mean']:+.4f}", flush=True)
    out = ROOT / f"output/unused-ratings/shot_difficulty_share_{args.feature}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
