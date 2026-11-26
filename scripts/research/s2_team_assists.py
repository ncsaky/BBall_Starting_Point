#!/usr/bin/env python3
"""S2-TENTH: each team's assisted share of made shots (AST / FGM), Stage 2 replays against the real 2025-26 boxes
(research only). Optional loop overrides: LOOP.key=value ...

    PYTHONPATH=src .venv/bin/python scripts/research/s2_team_assists.py [--runs 2] [LOOP.k_ast_team=1 ...]
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--seed", type=int, default=5001)
    args, rest = ap.parse_known_args()
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids
    from s2_usage_fit import apply
    apply({k: float(v) for k, v in (a.split("=", 1) for a in rest)})
    ctx = load_sim_context(ROOT)
    box = {str(g["game_id"]): g for g in ctx["boxscores"]}
    gids = [g for g in validation_game_ids(ctx, None, False) if g in box]
    eng = defaultdict(lambda: [0.0, 0.0])
    real = defaultdict(lambda: [0.0, 0.0])
    for gid in gids:
        for r in range(args.runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=args.seed + r, engine="stage2")
            for tl in res.team_lines:
                e = eng[tl["team_abbrev"]]
                e[0] += tl["assists"]
                e[1] += tl["fgm"]
        g = box[gid]
        for tl in g.get("teams") or []:
            st = tl.get("stats") or {}
            try:
                ast, fgm = float(st["assists"]), float(st["fieldGoalsMade-fieldGoalsAttempted"].split("-")[0])
            except (KeyError, ValueError):
                continue
            real[tl["team_abbrev"]][0] += ast
            real[tl["team_abbrev"]][1] += fgm
    teams = sorted(t for t in eng if t in real and real[t][1])
    if not teams:
        print("no real team lines found; keys:", list(next(iter(box.values())).keys()))
        return 1
    xe = [eng[t][0] / eng[t][1] for t in teams]
    xr = [real[t][0] / real[t][1] for t in teams]
    mx, my = statistics.fmean(xe), statistics.fmean(xr)
    c = sum((a - mx) * (b - my) for a, b in zip(xe, xr)) / math.sqrt(sum((a - mx) ** 2 for a in xe) * sum((b - my) ** 2 for b in xr))
    print(f"assisted share of makes: Stage 2 mean {mx:.3f} sd {statistics.pstdev(xe):.3f} | real {my:.3f} sd {statistics.pstdev(xr):.3f} | corr {c:.3f}")
    for t, a, b in sorted(zip(teams, xe, xr), key=lambda z: -z[2]):
        print(f"  {t} {a:.3f} {b:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
