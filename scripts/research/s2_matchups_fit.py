#!/usr/bin/env python3
"""Stage 2 matchups: fit who-guards-whom weights to Basketball Index's per-defender assignment data (2025-26).

Real five-on-five lineups drawn from the 2025-26 box scores (stage2.game_contexts, minutes-weighted). For each lineup
pair the assignment rule (stage2.matchups.assign) picks who guards whom; each defender's average assignment (height of
the man he guards, and that man's real usage) is compared with Basketball Index's "Avg Height Guarded" and "Guarded
USG%" for that defender (players with 500+ minutes). The weights are chosen on the fit half of defenders (the same
fixed hash as the other Stage 2 checks) and scored on the held-out half. The old rule (tallest guards tallest) is the
baseline. Light: no game simulation.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_matchups_fit.py [--per 2]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.stage2 import cards as C  # noqa: E402
from nba_gm_data.stage2 import matchups as M  # noqa: E402
from nba_gm_data.stage2.game_contexts import GENERIC, build_contexts, league_flat_inputs, load_games, split_half  # noqa: E402
from nba_gm_data.stage2.loop_fit import usage_target  # noqa: E402
from nba_gm_data.stage2.shooting_check import _bbi_table  # noqa: E402


def _corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def load(per: int):
    flats = league_flat_inputs(ROOT)
    means = C.means_for(ROOT)
    targets = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    cards = {pid: C.build_card(pid, pid, f, means) for pid, f in flats.items()}
    usage = {pid: usage_target(row) or 0.0 for pid, row in targets.items()}
    gen_usage = statistics.fmean(v for v in usage.values() if v > 0)
    ctxs = build_contexts(load_games(ROOT), per)
    table = _bbi_table(ROOT)
    real = {}
    for pid in flats:
        h = table.get(("2025-26", "Avg Height Guarded"), {}).get(pid)
        u = table.get(("2025-26", "Guarded USG%"), {}).get(pid)
        if h and u and h[1] >= 500:
            real[pid] = (h[0], u[0], h[1])
    return cards, usage, gen_usage, ctxs, real


def tally(cards, usage, gen_usage, ctxs, rule):
    acc = defaultdict(lambda: [0.0, 0.0, 0.0])
    for c in ctxs:
        off = [cards.get(p) or cards[GENERIC] for p in c["offense"]]
        de = [cards.get(p) or cards[GENERIC] for p in c["defense"]]
        d_of = rule(off, de)
        for i, j in enumerate(d_of):
            pid = c["defense"][j]
            if pid == GENERIC:
                continue
            a = acc[pid]
            a[0] += 1
            a[1] += off[i].height
            a[2] += usage.get(c["offense"][i]) or gen_usage
    return {pid: (a[1] / a[0], a[2] / a[0], a[0]) for pid, a in acc.items() if a[0] >= 20}


def score(sim, real, half):
    pids = [p for p in real if p in sim and (half is None or split_half(p) == half)]
    out = {"players": len(pids)}
    for k, name in ((0, "height"), (1, "usage")):
        out[name + "_corr"] = round(_corr([sim[p][k] for p in pids], [real[p][k] for p in pids]), 3)
    return out


def height_rule(off, de):
    o = sorted(range(5), key=lambda i: -off[i].height)
    d = sorted(range(5), key=lambda j: -de[j].height)
    out = [0] * 5
    for oi, dj in zip(o, d):
        out[oi] = dj
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=2)
    args = ap.parse_args()
    cards, usage, gen_usage, ctxs, real = load(args.per)
    print(f"{len(ctxs)} lineups, {len(real)} defenders with Basketball Index data")
    res = {"baseline_height_order": {h: score(tally(cards, usage, gen_usage, ctxs, height_rule), real, hv)
                                     for h, hv in (("fit", 0), ("held", 1))}}
    print("tallest-guards-tallest:", res["baseline_height_order"])
    grid = []
    for ws, wt, wh in itertools.product((1.0,), (0.0, 1.0, 2.0, 4.0, 6.0, 8.0), (0.0, 0.5)):
        w = {"w_size": ws, "w_star": wt, "w_hide": wh}
        sim = tally(cards, usage, gen_usage, ctxs, lambda o, d: M.assign(o, d, 1.0, w))
        f, h = score(sim, real, 0), score(sim, real, 1)
        grid.append({"w": w, "fit": f, "held": h})
        print(w, "fit", f, "held", h, flush=True)
    best = max(grid, key=lambda r: r["fit"]["height_corr"] + r["fit"]["usage_corr"])
    res["grid"] = grid
    res["best"] = best
    print("best on the fit half:", best)
    out = ROOT / "output" / "stage2" / "matchups_fit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
