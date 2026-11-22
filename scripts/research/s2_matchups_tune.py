#!/usr/bin/env python3
"""Stage 2 matchups: in-game fits of the loop's foul / turnover / team-strength numbers, fit half vs held-out half.

Plays replayed 2025-26 games (real availability and minutes) with Stage 2 and scores:
- per player (rotation players, the fixed player hash of the other Stage 2 checks): free throws per field-goal
  attempt and turnovers per 36 against real 2025-26 (targets file), FGA-weighted / minutes-weighted;
- league: free throws and turnovers per 100 possessions against the targets;
- team strength (`--strength`): the engine's expected margin against the market spread, first half of the season by
  date (the fit) and second half (the check), as the loop piece fitted its team-strength numbers.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_matchups_tune.py fouls --keys craft_drive,k_beat_foul [--games 1231]
    PYTHONPATH=src .venv/bin/python scripts/research/s2_matchups_tune.py strength --keys k_close,k_onball,k_rim --runs 3
    PYTHONPATH=src .venv/bin/python scripts/research/s2_matchups_tune.py show --set matchups=1

Coordinate search: each key moves by its step both ways; a move is kept when the loss falls; steps halve each round.
Nothing here changes a player's ratings (AGENTS.md rule 1).
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
from nba_gm_data.stage2.game_contexts import split_half  # noqa: E402

TARGETS = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())
REAL = TARGETS["players"]
LEAGUE = TARGETS["league"]
STEPS = {"craft_drive": .2, "craft_pull_up": .2, "craft_post": .2, "craft_finish": .2, "k_beat_foul": .4,
         "foul_drive": .15, "foul_roll_cut": .15, "foul_putback": .15, "foul_pull_up": .15, "foul_jumper": .15,
         "foul_post": .15, "foul_level": .1, "k_close": .12, "k_onball": .12, "k_rim": .12, "k_beat_make": .2,
         "k_post": .15, "k_press": .15, "k_rot": .1, "k_perim": .12, "k_create": .15, "k_space": .15, "k_beat": .3,
         "k_lanes": .1, "beat0": .3, "to_shift": .05, "k_lead": .002}
_CTX: dict = {}


def setup():
    if not _CTX:
        ctx = load_sim_context(ROOT)
        ids = validation_game_ids(ctx, None, False)
        sched = {str(s.get("externalGameId")): s for s in ctx["schedule"]}
        ids = sorted(ids, key=lambda g: (sched.get(str(g), {}).get("gameDate") or "", g))
        _CTX.update(ctx=ctx, ids=ids)
    return _CTX


def play(ids, runs=1, seed=1):
    ctx = setup()["ctx"]
    agg = defaultdict(lambda: defaultdict(float))
    lg = defaultdict(float)
    margins = {}
    for gid in ids:
        m = 0.0
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine="stage2")
            m += (res.home_score - res.away_score) / runs
            for ln in res.player_lines:
                a = agg[str(ln["player_id"])]
                for k in ("minutes", "fga", "fta", "turnovers", "points", "steals", "fg3a", "assists", "blocks"):
                    a[k] += float(ln.get(k) or 0)
            lg["poss"] += 2 * float(res.possessions)
            for tl in res.team_lines:
                for k in ("fta", "turnovers", "fga", "points", "steals"):
                    lg[k] += float(tl.get(k) or 0)
        margins[gid] = m
    return agg, lg, margins


def _corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def player_scores(agg, half):
    ftr, tov = [], []
    for pid, a in agg.items():
        row = REAL.get(pid)
        if not row or a["minutes"] < 250 or (half is not None and split_half(pid) != half):
            continue
        if a["fga"] >= 40 and float(row.get("fga_per36") or 0) > 0:
            ftr.append((a["fta"] / a["fga"], float(row["fta_per36"]) / float(row["fga_per36"]), a["fga"]))
        tov.append((36 * a["turnovers"] / a["minutes"], float(row["turnovers_per36"]), a["minutes"]))

    def summ(pairs):
        w = sum(p[2] for p in pairs)
        return {"n": len(pairs), "corr": round(_corr([p[0] for p in pairs], [p[1] for p in pairs]), 3),
                "rmse": round(math.sqrt(sum(p[2] * (p[0] - p[1]) ** 2 for p in pairs) / w), 4),
                "bias": round(sum(p[2] * (p[0] - p[1]) for p in pairs) / w, 4)}
    return {"ftr": summ(ftr), "tov36": summ(tov)}


def league_scores(lg):
    p = lg["poss"]   # team possessions, both teams (each game adds 2 x its per-team count)
    return {"fta_per100": round(100 * lg["fta"] / p, 2), "tov_per100": round(100 * lg["turnovers"] / p, 2),
            "pts_per100": round(100 * lg["points"] / p, 2),
            "target_fta": LEAGUE["fta_per100"]["mean"], "target_tov": LEAGUE["tov_per100"]["mean"],
            "target_ortg": LEAGUE["off_rating"]["mean"]}


def strength_scores(margins, ids):
    ctx = setup()["ctx"]
    xs, ys = [], []
    for gid in ids:
        spread = ((ctx["odds"].get(str(gid)) or {}).get("spread") or {}).get("home_line")
        if spread is None:
            continue
        xs.append(margins[gid])
        ys.append(-float(spread))
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    slope = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((b - my) ** 2 for b in ys)
    return {"corr": round(_corr(xs, ys), 4), "slope": round(slope, 3),
            "mae": round(statistics.fmean(abs(a - b) for a, b in zip(xs, ys)), 3), "n": len(xs)}


def foul_loss(agg, lg):
    """FGA-weighted squared error of FT/FGA on the fit half, plus a penalty on the league FT and TO levels."""
    s = player_scores(agg, 0)["ftr"]
    L = league_scores(lg)
    return s["rmse"] ** 2 + ((L["fta_per100"] - L["target_fta"]) / 22.9 * .25) ** 2 + ((L["tov_per100"] - L["target_tov"]) / 14.1 * .25) ** 2


def search(keys, loss_fn, rounds=3):
    best = {k: G.LOOP[k] for k in keys}
    cur, info = loss_fn()
    print("start", json.dumps(best), round(cur, 6), info, flush=True)
    steps = {k: STEPS.get(k, .1) for k in keys}
    for rnd in range(rounds):
        improved = False
        for k in keys:
            for d in (steps[k], -steps[k]):
                trial = dict(best)
                trial[k] = round(best[k] + d, 4)
                G.LOOP.update(trial)
                v, inf = loss_fn()
                if v < cur:
                    best, cur, info, improved = trial, v, inf, True
                    print("  keep", k, trial[k], round(v, 6), inf, flush=True)
                    break
            G.LOOP.update(best)
        for k in steps:
            steps[k] /= 2
    G.LOOP.update(best)
    return best, cur, info


def parse_set(text):
    out = {}
    for part in filter(None, (text or "").split(",")):
        k, v = part.split("=")
        out[k.strip()] = float(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("fouls", "strength", "show"))
    ap.add_argument("--keys", default="")
    ap.add_argument("--set", default="")
    ap.add_argument("--games", type=int, default=1231)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()
    S = setup()
    G.LOOP.update(parse_set(args.set))
    ids = S["ids"]
    t0 = time.time()
    if args.cmd in ("fouls", "show"):
        sub = ids[:: max(1, len(ids) // args.games)][: args.games]

        def loss():
            agg, lg, _ = play(sub, args.runs)
            info = {"fit": player_scores(agg, 0), "held": player_scores(agg, 1), "league": league_scores(lg)}
            return foul_loss(agg, lg), info
        if args.cmd == "show":
            print(json.dumps(loss()[1], indent=1))
        else:
            best, cur, info = search(args.keys.split(","), loss, args.rounds)
            print("best", json.dumps(best), json.dumps(info), f"{time.time() - t0:.0f}s")
    else:
        half = len(ids) // 2
        fit_ids = ids[:half][:: max(1, half // args.games)][: args.games]
        held_ids = ids[half:][:: max(1, (len(ids) - half) // args.games)][: args.games]

        def loss():
            _, lg, m = play(fit_ids, args.runs, seed=1001)
            s = strength_scores(m, fit_ids)
            # Follow the market's spreads: correlation first, and a slope near 1 (not over- or under-spread).
            return -s["corr"] + .1 * abs(math.log(max(.2, s["slope"]))), {"fit": s, "league": league_scores(lg)}
        best, cur, info = search(args.keys.split(","), loss, args.rounds)
        _, lg, m = play(held_ids, args.runs, seed=1001)
        print("best", json.dumps(best), "fit", json.dumps(info), "held", json.dumps(strength_scores(m, held_ids)),
              f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
