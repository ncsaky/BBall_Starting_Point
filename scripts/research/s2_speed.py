#!/usr/bin/env python3
"""S2-TENTH: Stage 2 milliseconds per game (replayed and generated), best of three, with optional loop overrides.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_speed.py [--games 400] [LOOP.key=v COACH.key=v ...]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=400)
    args, rest = ap.parse_known_args()
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids
    from nba_gm_data.stage2 import coach as CO, game as G
    for a in rest:
        k, v = a.split("=", 1)
        table, name = k.split(".", 1)
        (G.LOOP if table == "LOOP" else CO.COACH)[name] = float(v)
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    ids = ids[:: max(1, len(ids) // args.games)][: args.games]
    for gid in ids[:20]:
        sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=1, engine="stage2")
        sim_game_with_context(ctx, gid, mode="sandbox-sim", seed=1, engine="stage2")
    out = {}
    for mode in ("replay-real-minutes", "sandbox-sim"):
        best = 1e9
        for rep in range(3):
            t0 = time.perf_counter()
            for gid in ids:
                sim_game_with_context(ctx, gid, mode=mode, seed=7 + rep, engine="stage2")
            best = min(best, (time.perf_counter() - t0) / len(ids))
        out[mode] = round(1000 * best, 2)
    print("ms per game", out, "overrides", rest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
