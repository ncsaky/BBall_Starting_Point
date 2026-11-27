#!/usr/bin/env python3
"""S2-TENTH: how many overtimes Stage 2 games run to, against real 2023-26 regular seasons (research only).

Replays every 2025-26 game RUNS times (real availability and minutes) and counts games by overtime periods, and how
often an overtime period ends tied (the chance of one more). Real (play-by-play, output/rotation-evidence, 2023-24 to
2025-26, 3,690 games): 179 overtime games (4.9%), 20 double overtimes, no triple: 11.2% of overtime periods end tied.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_overtime_check.py --runs 16 [LOOP.key=value ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
REAL = {"games": 3690, "by_ot": {0: 3511, 1: 159, 2: 20}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--mode", default="replay-real-minutes")
    ap.add_argument("--out", default="")
    args, rest = ap.parse_known_args()
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids
    from s2_usage_fit import apply
    apply({k: float(v) for k, v in (a.split("=", 1) for a in rest)})
    ctx = load_sim_context(ROOT)
    gids = validation_game_ids(ctx, None, False)
    by_ot = Counter()
    for r in range(args.runs):
        for gid in gids:
            res = sim_game_with_context(ctx, gid, mode=args.mode, seed=args.seed + r, engine="stage2")
            note = res.notes or ""
            ot = int(note.split("Overtime resolved over ")[1].split(" ")[0]) if "Overtime resolved over" in note else 0
            by_ot[ot] += 1
    n = sum(by_ot.values())

    def summary(c, n):
        ot_games = sum(v for k, v in c.items() if k > 0)
        periods = sum(v * k for k, v in c.items())
        tied_after = sum(v * (k - 1) for k, v in c.items() if k > 1)
        return {"games": n, "by_ot": dict(sorted(c.items())), "ot_share": round(ot_games / n, 4),
                "ot_period_ends_tied": round(tied_after / max(1, periods), 4),
                "per_10000": {k: round(1e4 * v / n, 1) for k, v in sorted(c.items()) if k > 0}}
    out = {"stage2": summary(by_ot, n), "real": summary(Counter(REAL["by_ot"]), REAL["games"])}
    print(json.dumps(out, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
