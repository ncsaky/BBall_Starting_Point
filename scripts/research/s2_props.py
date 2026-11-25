#!/usr/bin/env python3
"""Player props, scored per engine (S2-LAST-POSSESSION, part 3). Research only: sim.py and research.py are untouched.

The betting test (sim.validate_season_probabilities) records each game's player-prop comparison
(sim.player_prop_calibration_metrics) but its summary never scores them, and the odds file holds few props: points
lines for 40 games (2025-10-21 to 2025-10-31, 396 lines, parsed from Fox Sports articles by
research.parse_foxsports_points_props), with the over price only. This script scores both engines two ways:

1. Market props (the 40 games, RUNS runs a game, the test's mode: real availability and minutes). For each line:
   the engine's chance of the over, against the market's (over price, no-vig assumed symmetric: the usual 4.5% overround
   split evenly, since the under price is missing) and against what happened. Brier score and log loss of each against
   the real result, the mean gap to the market, the engine's mean points minus the line, and its median's miss.
2. Every 2025-26 game (--all-runs runs a game): each player's expected points, rebounds, assists and threes against his
   real line in that game (mean absolute error, correlation, the mean bias), for players with real minutes. This is
   the broad stand-in for props where no market line exists.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_props.py --runs 200 --all-runs 8 --out output/s2last/props.json
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
OVERROUND = .045


def implied(american: float) -> float:
    return 100 / (american + 100) if american > 0 else -american / (-american + 100)


def brier(ps, ys):
    return statistics.fmean((p - y) ** 2 for p, y in zip(ps, ys))


def logloss(ps, ys):
    return statistics.fmean(-math.log(min(.99, max(.01, p)) if y else 1 - min(.99, max(.01, p))) for p, y in zip(ps, ys))


def corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy)


def market_props(ctx, engine: str, runs: int, seed: int) -> dict:
    from nba_gm_data.sim import match_prop_player_key, normalize_name, sim_game_with_context
    box = {str(g["game_id"]): g for g in ctx["boxscores"]}
    rows = []
    for gid, odds in ctx["odds"].items():
        props = [p for p in odds.get("player_props") or [] if p.get("market") == "points" and p.get("line") is not None]
        if not props or gid not in box:
            continue
        lines = defaultdict(list)
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine=engine)
            for ln in res.player_lines:
                lines[normalize_name(ln["player_name"])].append(float(ln.get("points") or 0))
        real = {normalize_name(p["player_name"]): p for p in box[gid]["players"]}
        for p in props:
            key = normalize_name(p["player_name"])
            sk = match_prop_player_key(key, lines)
            rk = match_prop_player_key(key, real)
            if sk is None or rk is None or real[rk].get("dnp") or not real[rk].get("minutes"):
                continue
            vals = sorted(lines[sk])
            line = float(p["line"])
            p_over = sum(1 for v in vals if v > line) / len(vals)
            m_over = None
            if p.get("over_american") is not None:
                m_over = min(.97, max(.03, implied(float(p["over_american"])) - OVERROUND / 2))
            rows.append({"game": gid, "player": p["player_name"], "line": line, "sim_mean": statistics.fmean(vals),
                         "sim_median": vals[len(vals) // 2], "sim_over": p_over, "market_over": m_over,
                         "actual": float(real[rk].get("points") or 0)})
    ys = [1 if r["actual"] > r["line"] else 0 for r in rows]
    sp = [min(.99, max(.01, r["sim_over"])) for r in rows]
    mrows = [(r, y) for r, y in zip(rows, ys) if r["market_over"] is not None]
    out = {"props": len(rows), "games": len({r["game"] for r in rows}), "over_rate_real": round(statistics.fmean(ys), 3),
           "sim_over_mean": round(statistics.fmean(sp), 3),
           "sim_brier": round(brier(sp, ys), 4), "sim_logloss": round(logloss(sp, ys), 4),
           "sim_mean_minus_line": round(statistics.fmean(r["sim_mean"] - r["line"] for r in rows), 2),
           "sim_median_miss": round(statistics.fmean(abs(r["sim_median"] - r["line"]) for r in rows), 2),
           "sim_mean_miss": round(statistics.fmean(abs(r["sim_mean"] - r["line"]) for r in rows), 2),
           "corr_sim_mean_line": round(corr([r["sim_mean"] for r in rows], [r["line"] for r in rows]), 3),
           "sim_mean_vs_actual_mae": round(statistics.fmean(abs(r["sim_mean"] - r["actual"]) for r in rows), 2),
           "line_vs_actual_mae": round(statistics.fmean(abs(r["line"] - r["actual"]) for r in rows), 2)}
    if mrows:
        mp = [r["market_over"] for r, _ in mrows]
        my = [y for _, y in mrows]
        msp = [min(.99, max(.01, r["sim_over"])) for r, _ in mrows]
        out.update({"market_brier": round(brier(mp, my), 4), "market_logloss": round(logloss(mp, my), 4),
                    "sim_brier_same_props": round(brier(msp, my), 4),
                    "sim_vs_market_over_gap": round(statistics.fmean(abs(a - b) for a, b in zip(msp, mp)), 3),
                    "sim_vs_market_over_bias": round(statistics.fmean(a - b for a, b in zip(msp, mp)), 3)})
    big = sorted(rows, key=lambda r: -abs(r["sim_mean"] - r["line"]))[:12]
    out["largest_gaps"] = [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k != "game"} for r in big]
    out["rows"] = rows
    return out


def all_games(ctx, engine: str, runs: int, seed: int) -> dict:
    from nba_gm_data.sim import normalize_name, sim_game_with_context, validation_game_ids
    box = {str(g["game_id"]): g for g in ctx["boxscores"]}
    stats = ("points", "rebounds", "assists", "fg3m")
    pairs = {s: [] for s in stats}
    per_player = defaultdict(lambda: {s: [0.0, 0.0] for s in stats})
    for gid in validation_game_ids(ctx, None, False):
        if gid not in box:
            continue
        acc = defaultdict(lambda: {s: 0.0 for s in stats})
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine=engine)
            for ln in res.player_lines:
                a = acc[normalize_name(ln["player_name"])]
                for s in stats:
                    a[s] += float(ln.get(s) or 0) / runs
        for p in box[gid]["players"]:
            if p.get("dnp") or not p.get("minutes") or float(p["minutes"]) < 10:
                continue
            k = normalize_name(p["player_name"])
            if k not in acc:
                continue
            for s in stats:
                pairs[s].append((acc[k][s], float(p.get(s) or 0)))
                per_player[k][s][0] += acc[k][s]
                per_player[k][s][1] += float(p.get(s) or 0)
    out = {}
    for s in stats:
        e, a = zip(*pairs[s])
        out[s] = {"player_games": len(e), "mae": round(statistics.fmean(abs(x - y) for x, y in pairs[s]), 3),
                  "corr": round(corr(e, a), 4), "bias": round(statistics.fmean(x - y for x, y in pairs[s]), 3)}
        # Season totals per player (systematic part: what more runs would not fix).
        tot = [(v[s][0], v[s][1]) for v in per_player.values() if v["points"][1] > 0]
        out[s]["season_total_rel_err"] = round(statistics.fmean(abs(x - y) / max(1.0, y) for x, y in tot if y >= 50), 4)
    # Players whose season points are furthest off (at least 400 real points): engine minus real, per game played.
    rows = []
    for k, v in per_player.items():
        if v["points"][1] >= 400:
            rows.append((k, round(v["points"][0] - v["points"][1]), round(100 * (v["points"][0] / v["points"][1] - 1), 1)))
    rows.sort(key=lambda r: r[2])
    out["points_furthest_under"] = rows[:10]
    out["points_furthest_over"] = rows[-10:][::-1]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="stage2,current")
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--all-runs", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--out", default=None)
    args, rest = ap.parse_known_args()
    from nba_gm_data.stage2 import game as G
    for a in rest:
        key, value = a.split("=", 1)
        G.LOOP[key.split(".", 1)[1]] = float(value)
    from nba_gm_data.sim import load_sim_context
    ctx = load_sim_context(ROOT)
    res = {}
    for eng in args.engines.split(","):
        t0 = time.time()
        res[eng] = {"market": market_props(ctx, eng, args.runs, args.seed)}
        if args.all_runs:
            res[eng]["all_games"] = all_games(ctx, eng, args.all_runs, args.seed)
        res[eng]["seconds"] = round(time.time() - t0, 1)
        show = {k: v for k, v in res[eng]["market"].items() if k not in ("rows", "largest_gaps")}
        print(eng, json.dumps(show), flush=True)
        if args.all_runs:
            print(eng, "all games", json.dumps(res[eng]["all_games"]), flush=True)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
