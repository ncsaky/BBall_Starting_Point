#!/usr/bin/env python3
"""Stage 2 shooting fouls by teammates of the shot's defender (S2-SCHEMES, part 3).

The loop gives every shooting foul to the shot's defender (his man, or the switched defender), so a stopper assigned to
a high-usage scorer, or a big who switches onto guards, collects the fouls of every shot he is charged with. Real fouls
also come from the help: the rim protector, the low man, a late rotation or closeout. This replays the 2025-26 games
once, records every shooting-foul chance (game.FOUL_TRACE: zone, drive or not, the foul chance, the shot's defender,
the help defender and all five defenders' foul terms), and recomputes each player's expected personal fouls when a
share of the shooting fouls (by zone) is committed by a teammate instead:
- "rim protector" variant: the help defender (best rim protection) takes the share (fouls.FoulCoefficients.help_share);
- "team" variant: one of the other four, weighted by his own foul terms (foul control, contest habits, foul trouble).
The league's shooting-foul total is held fixed (free throws do not move). Fit on half the rotation players (800+ real
and simulated minutes), checked on the other half, against real 2025-26 fouls per 36. Also reports the exposure check:
each defender's shooting-foul chances per minute, and how expected fouls fit if they followed minutes instead.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_foul_help_fit.py --runs 2 [--mode replay-real-minutes]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output" / "s2schemes"


def _sig(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--mode", default="replay-real-minutes")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="")
    args, rest = ap.parse_known_args()
    from nba_gm_data.stage2 import coach as C, game as G, screens as S
    for a in rest:
        key, value = a.split("=", 1)
        table, name = key.split(".", 1)
        {"loop": G.LOOP, "coach": C.COACH, "screens": S.SCREENS}[table][name] = float(value)
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids
    G.FOUL_TRACE = trace = []
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    if args.limit:
        ids = ids[:: max(1, len(ids) // args.limit)][:args.limit]
    box = {str(g.get("game_id")): g for g in ctx["boxscores"]}
    sim_min, sim_pf, name_of = defaultdict(float), defaultdict(float), {}
    real_min, real_pf = defaultdict(float), defaultdict(float)
    t0 = time.time()
    for gid in ids:
        g = box.get(str(gid))
        if g:
            for p in g.get("players", []):
                m = float(p.get("minutes") or 0)
                if m > 0:
                    real_min[p.get("player_name")] += m
                    real_pf[p.get("player_name")] += float(p.get("pf") or 0)
        for r in range(args.runs):
            res = sim_game_with_context(ctx, gid, mode=args.mode, seed=args.seed + r, engine="stage2")
            for ln in res.player_lines:
                m = float(ln.get("minutes") or 0)
                pid = ln.get("player_id") or ln.get("player_name")
                name_of[pid] = ln.get("player_name")
                if m > 0:
                    sim_min[pid] += m / args.runs
                    sim_pf[pid] += float(ln.get("personal_fouls") or 0) / args.runs
    G.FOUL_TRACE = None
    print(f"{len(trace)} shooting-foul chances in {time.time() - t0:.0f}s")
    R = args.runs
    cur = defaultdict(float)
    chances = defaultdict(float)
    for zone, drive, p, j, hj, pids, df, cz in trace:
        cur[pids[j]] += p / R
        chances[pids[j]] += 1.0 / R
    players = [pid for pid in sim_min if sim_min[pid] >= 800 and real_min.get(name_of.get(pid), 0) >= 800]
    other = {pid: sim_pf[pid] - cur.get(pid, 0.0) for pid in players}
    real36 = {pid: 36 * real_pf[name_of[pid]] / real_min[name_of[pid]] for pid in players}
    half = {pid: int(hashlib.md5(str(pid).encode()).hexdigest(), 16) % 2 for pid in players}
    total_cur = sum(t[2] for t in trace)
    lg_rate = sum(chances[p] for p in players) / sum(sim_min[p] for p in players)
    expo = {p: (chances[p] / sim_min[p]) / lg_rate for p in chances if sim_min.get(p, 0) > 0}

    def predict(h: tuple, variant: str = "team", a: float = 0.0) -> dict:
        """h: share of shooting fouls by a teammate, per zone (rim, short, mid, three)."""
        exp = defaultdict(float)
        tot = 0.0
        for zone, drive, p, j, hj, pids, df, cz in trace:
            if a:
                p = p * expo.get(pids[j], 1.0) ** (-a)
            share = h[zone]
            if share <= 0 or (variant == "rim" and hj == j):
                exp[pids[j]] += p
                tot += p
                continue
            z0 = _logit(p) - df[j] - cz[j]
            exp[pids[j]] += (1 - share) * p
            tot += (1 - share) * p
            if variant == "rim":
                q = _sig(z0 + df[hj] + cz[hj])
                exp[pids[hj]] += share * q
                tot += share * q
            else:
                # One of the other four, each with his own foul chance on this shot; the foul is his with weight
                # proportional to that chance.
                qs = [(k, _sig(z0 + df[k] + cz[k])) for k in range(5) if k != j]
                qm = sum(q for _, q in qs) / 4.0
                for k, q in qs:
                    exp[pids[k]] += share * q / 4.0
                tot += share * qm
        scale = total_cur / tot
        return {pid: 36 * (other[pid] + scale * exp.get(pid, 0.0) / R) / sim_min[pid] for pid in players}

    def score(pred: dict, which: int | None) -> dict:
        ps = [pid for pid in players if which is None or half[pid] == which]
        e = [pred[p] - real36[p] for p in ps]
        xs, ys = [pred[p] for p in ps], [real36[p] for p in ps]
        return {"mae": round(st.fmean(abs(v) for v in e), 4), "bias": round(st.fmean(e), 3),
                "corr": round(st.correlation(xs, ys), 3), "sd_sim": round(st.pstdev(xs), 3),
                "sd_real": round(st.pstdev(ys), 3), "n_4_5": sum(1 for v in xs if v >= 4.5),
                "n_4_5_real": sum(1 for v in ys if v >= 4.5), "players": len(ps)}

    base = predict((0, 0, 0, 0))
    res = {"base": {"fit": score(base, 0), "check": score(base, 1), "all": score(base, None)}}
    res["exposure"] = {"sd": round(st.pstdev([expo.get(p, 1.0) for p in players]), 3),
                       "corr_with_over": round(st.correlation([expo.get(p, 1.0) for p in players],
                                                              [base[p] - real36[p] for p in players]), 3)}
    for a_ in (.5, 1.0):
        pr = predict((0, 0, 0, 0), a=a_)
        res[f"fouls_follow_minutes_{a_}"] = {"fit": score(pr, 0), "check": score(pr, 1)}
    grid = []
    for variant in ("team", "rim"):
        g_r = (0.0, .15, .3, .45, .6, .75, .9) if variant == "team" else (0.0, .15, .3)
        g_s = (0.0, .3, .45, .6, .75, .9) if variant == "team" else (0.0, .15, .3)
        g_j = (0.0, .3, .45, .6, .75) if variant == "team" else (0.0,)
        for hr in g_r:
            for hs in g_s:
                for hj in g_j:
                    pr = predict((hr, hs, hj, hj), variant)
                    grid.append(((variant, hr, hs, hj), score(pr, 0)["mae"]))
    grid.sort(key=lambda x: x[1])
    res["grid_top"] = [{"variant": k[0], "rim": k[1], "short": k[2], "jumpers": k[3], "fit_mae": m} for k, m in grid[:8]]
    for variant in ("team", "rim"):
        k, m = next(x for x in grid if x[0][0] == variant)
        pr = predict((k[1], k[2], k[3], k[3]), variant)
        res[f"best_{variant}"] = {"share": {"rim": k[1], "short": k[2], "jumpers": k[3]}, "fit": score(pr, 0),
                                  "check": score(pr, 1), "all": score(pr, None)}
        if variant == "team":
            top = sorted(players, key=lambda p: -pr[p])[:20]
            res["top_after_team"] = [{"name": name_of[p], "before": round(base[p], 2), "after": round(pr[p], 2),
                                      "real": round(real36[p], 2)} for p in top]
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("top_after")}, indent=1))
    for r in res.get("top_after_team", []):
        print(f"  {r['name']:26s} before {r['before']:.2f} after {r['after']:.2f} real {r['real']:.2f}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"foul_help_fit_{args.mode}{'_' + args.tag if args.tag else ''}.json").write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
