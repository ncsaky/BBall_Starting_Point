#!/usr/bin/env python3
"""Stage 2: fit the shooting-foul-by-action numbers on expected values from replayed games (fit half vs held half).

Replays every 2025-26 game (real availability and minutes) with Stage 2 and records, for each player and each kind of
shot try (drive, floater, finish of a pass, post-up, jumper, pull-up, putback, transition ...), how many tries he made
and the foul terms that do not depend on the numbers being fitted (the foul kernel's zone base, his drawing terms, his
defender's foul terms, how often he was past his man on drives, his defender's foul control, the and-one share).
Then each player's free throws per field-goal attempt is predicted for any setting of the fitted numbers without
replaying (non-shooting free throws are kept as played), and the numbers are fitted (bounded coordinate search) on the
fit half of players against real 2025-26 FTA/FGA, holding the league's free throws per 100 at the real level, and
scored on the held-out half.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_foul_fit.py [--runs 2] [--set matchups=1]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids  # noqa: E402
from nba_gm_data.stage2 import game as G  # noqa: E402
from nba_gm_data.stage2.cards import KINDS, N_KINDS  # noqa: E402
from nba_gm_data.stage2.game_contexts import split_half  # noqa: E402

TARGETS = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())
REAL = TARGETS["players"]
PARAMS = {  # name: (lower, upper, step)
    "foul_drive": (0.0, 1.5, .2), "foul_roll_cut": (-1.5, 0.5, .2), "foul_post": (-1.0, 1.0, .2),
    "foul_putback": (-1.5, 0.5, .2), "foul_transition": (-1.0, 1.0, .2), "foul_jumper": (-1.5, 0.5, .2),
    "foul_pull_up": (-1.0, 1.0, .2), "foul_level": (-1.0, 1.0, .1), "foul_rim": (-1.0, 1.0, .1),
    "craft_drive": (-0.5, 1.5, .2), "craft_pull_up": (-0.5, 1.5, .2), "craft_post": (-0.5, 1.5, .2),
    "craft_finish": (-1.0, 1.0, .2), "k_beat_foul": (0.0, 3.0, .3)}
ACTION_KEY = {"drive": "drive", "roll_cut": "finish", "putback": "finish", "post": "post", "pull_up": "pull_up"}


def sig(z):
    return 1 / (1 + math.exp(-z)) if z > -30 else 0.0


def collect(runs: int) -> tuple[dict, dict, float]:
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    G.TRACE = {}
    box = defaultdict(lambda: [0.0, 0.0, 0.0])   # minutes, fga, fta
    poss = 0.0
    for gid in ids:
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=1 + r, engine="stage2")
            poss += 2 * float(res.possessions)
            for ln in res.player_lines:
                b = box[str(ln["player_id"])]
                b[0] += float(ln.get("minutes") or 0)
                b[1] += float(ln.get("fga") or 0)
                b[2] += float(ln.get("fta") or 0)
    trace, G.TRACE = G.TRACE, None
    return trace, box, poss


def kind_p(rec_k, theta, k):
    name, action, zone = KINDS[k][0], KINDS[k][1], KINDS[k][2]
    n = rec_k[0]
    fixed = rec_k[1] / n
    beat = rec_k[2] / n
    fctrl = rec_k[3] / n
    z = fixed + theta.get("foul_" + action, 0.0) if action != "heave" else -30
    if zone < 3:
        z += theta["foul_level"]
    if zone == 0:
        z += theta["foul_rim"]
    ck = ACTION_KEY.get(action)
    if ck:
        z += theta["craft_" + ck] * rec_k[5]
    z += theta["k_beat_foul"] * beat - G.LOOP["k_fctrl"] * fctrl
    return sig(z)


def predict(rec, theta):
    """Expected shooting-foul FTA and FGA for one player's tries."""
    fta = fga = 0.0
    for k in range(N_KINDS):
        r = rec[k]
        if r[0] <= 0:
            continue
        p = kind_p(r, theta, k)
        a1 = min(1.0, r[4] / r[0])
        per_foul = a1 + (1 - a1) * (3 if KINDS[k][2] == 3 else 2)
        fta += r[0] * p * per_foul
        fga += r[0] * (1 - p * (1 - a1))
    return fta, fga


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--set", default="matchups=1")
    ap.add_argument("--keys", default=",".join(PARAMS))
    args = ap.parse_args()
    for part in filter(None, args.set.split(",")):
        k, v = part.split("=")
        G.LOOP[k] = float(v)
    t0 = time.time()
    trace, box, poss = collect(args.runs)
    print(f"collected {len(trace)} players in {time.time() - t0:.0f}s", flush=True)
    theta0 = {k: G.LOOP.get(k, 0.0) for k in PARAMS}
    # Non-shooting FTA as played = played FTA - expected shooting FTA at the played setting.
    rows = []
    shoot0 = 0.0
    nonshoot_total = 0.0
    for pid, rec in trace.items():
        b = box.get(pid)
        if not b:
            continue
        f0, g0 = predict(rec, theta0)
        shoot0 += f0
        ns = max(0.0, b[2] - f0)
        nonshoot_total += ns
        row = REAL.get(pid)
        if row and b[0] >= 250 and b[1] >= 40 and float(row.get("fga_per36") or 0) > 0:
            rows.append((pid, rec, ns, float(row["fta_per36"]) / float(row["fga_per36"]), b[1]))
    target_fta = TARGETS["league"]["fta_per100"]["mean"] * poss / 100.0
    all_recs = list(trace.values())

    def league_fta(theta):
        return nonshoot_total + sum(predict(r, theta)[0] for r in all_recs)

    def pred_ftr(theta, r):
        f, g = predict(r[1], theta)
        return (f + r[2]) / max(1.0, g)

    def score(theta, half):
        pairs = [(pred_ftr(theta, r), r[3], r[4]) for r in rows if split_half(r[0]) == half]
        w = sum(p[2] for p in pairs)
        mp = sum(p[2] * p[0] for p in pairs) / w
        mr = sum(p[2] * p[1] for p in pairs) / w
        cov = sum(p[2] * (p[0] - mp) * (p[1] - mr) for p in pairs) / w
        vp = sum(p[2] * (p[0] - mp) ** 2 for p in pairs) / w
        vr = sum(p[2] * (p[1] - mr) ** 2 for p in pairs) / w
        return {"n": len(pairs), "rmse": round(math.sqrt(sum(p[2] * (p[0] - p[1]) ** 2 for p in pairs) / w), 4),
                "corr": round(cov / math.sqrt(vp * vr), 3), "bias": round(mp - mr, 4)}

    def loss(theta):
        s = score(theta, 0)
        lvl = league_fta(theta) / target_fta - 1.0
        return s["rmse"] ** 2 + (lvl * .3) ** 2

    keys = args.keys.split(",")
    theta = dict(theta0)
    cur = loss(theta)
    print("start", {k: theta[k] for k in keys}, "fit", score(theta, 0), "held", score(theta, 1),
          "league FTA vs target", round(league_fta(theta) / target_fta, 3), flush=True)
    steps = {k: PARAMS[k][2] for k in keys}
    for rnd in range(6):
        for k in keys:
            for d in (steps[k], -steps[k]):
                trial = dict(theta)
                trial[k] = round(theta[k] + d, 4)
                lo, hi, _ = PARAMS[k]
                if not lo <= trial[k] <= hi:
                    continue
                v = loss(trial)
                if v < cur:
                    theta, cur = trial, v
                    break
        for k in steps:
            steps[k] /= 2
    print("fitted", json.dumps({k: theta[k] for k in keys}))
    print("fit", score(theta, 0), "held", score(theta, 1), "league FTA vs target", round(league_fta(theta) / target_fta, 3))
    # Largest misses after the fit (season FTA: (pred - real) x FGA).
    out = []
    for r in rows:
        p = pred_ftr(theta, r)
        out.append(((p - r[3]) * r[4], REAL[r[0]].get("name"), round(p, 3), round(r[3], 3), round(pred_ftr(theta0, r), 3)))
    out.sort()
    print("under:", out[:10])
    print("over:", out[-10:][::-1])
    Path(ROOT / "output/stage2/foul_fit.json").write_text(json.dumps({"theta": theta, "start": theta0,
        "fit": score(theta, 0), "held": score(theta, 1), "fit_start": score(theta0, 0), "held_start": score(theta0, 1)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
