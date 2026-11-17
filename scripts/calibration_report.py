#!/usr/bin/env python3
"""Run N regular-season games on the live engine (sandbox-sim) and compare with real 2025-26 targets."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.calibration_targets import aggregate_from_results, compare, format_report, load_targets  # noqa: E402
from nba_gm_data.schema import to_plain  # noqa: E402
from nba_gm_data.sim import build_sim_indices, load_sim_context, sim_game_with_context  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--targets", default=str(ROOT / "data/calibration/nba_2025_26_targets.json"))
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--mode", default="sandbox-sim", choices=["sandbox-sim", "replay-real-minutes"],
                    help="sandbox-sim: projected rotations, every team healthy (default). replay-real-minutes: each "
                         "game's real availability and minutes (injuries and absences included), like the odds test.")
    args = ap.parse_args()
    targets = load_targets(args.targets)
    context = load_sim_context(ROOT)
    context["indices"] = build_sim_indices(context)
    games = [g for g in context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")]
    games = sorted(games, key=lambda g: str(g.get("externalGameId")))
    step = max(1, len(games) // args.games)
    picked = games[::step][: args.games]
    t0 = time.time()
    results = [to_plain(sim_game_with_context(context, str(g["externalGameId"]), mode=args.mode, seed=args.seed)) for g in picked]
    elapsed = time.time() - t0
    agg = aggregate_from_results(results)
    report = compare(agg["league_totals"], agg["player_lines"], targets, min_sim_games=3)
    print(f"{len(results)} games in {elapsed:.1f}s (seed {args.seed}, mode {args.mode})")
    print(format_report(report))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
