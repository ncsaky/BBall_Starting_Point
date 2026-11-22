#!/usr/bin/env python3
"""Stage 2 game totals: fit the loop's pace and scoring-level numbers on the first half of 2025-26, check the second.

The games are the betting test's (replayed with real availability and minutes), sorted by date and split in half.
For a setting of the loop's numbers (stage2.game.LOOP), every game is played R times and scored on:
- pace: the slope of the engine's possessions per 48 minutes on the two lineups' pace habit (T05, minute-weighted over
  real minutes, both teams summed) against the real slope; game- and team-level correlation with real pace;
- totals: correlation, bias and mean miss of the engine's expected total against the market total.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_totals_fit.py scan --key k_pace --values 1.2,2,3 [--runs 2]
    PYTHONPATH=src .venv/bin/python scripts/research/s2_totals_fit.py check --set k_pace=2.5,k_pace_def=2.5 [--runs 4]

`--tie k_pace,k_pace_def` sets several keys to the scanned value. Nothing here changes a player's ratings.
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
from nba_gm_data.stage2.game_contexts import GENERIC, league_flat_inputs, load_games  # noqa: E402

_CTX: dict = {}


def setup() -> dict:
    if _CTX:
        return _CTX
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    sched = {str(s.get("externalGameId")): s for s in ctx["schedule"]}
    ids = sorted(ids, key=lambda g: (sched.get(str(g), {}).get("gameDate") or "", g))
    flats = league_flat_inputs(ROOT)
    gen = flats[GENERIC]
    real = {}
    for g in load_games(ROOT):
        ts = list(g["teams"].values())
        poss = [t["fga"] - t["oreb"] + t["tov"] + .44 * t["fta"] for t in ts]
        gm = max(t["game_minutes"] for t in ts)
        hab = 0.0
        for t in ts:
            tot = sum(p["minutes"] for p in t["players"])
            hab += sum(p["minutes"] * float((flats.get(p["pid"]) or gen)["T05"]) for p in t["players"]) / tot
        real[str(g["game_id"])] = {"pace48": statistics.fmean(poss) * 48 / gm, "t05": hab}
    half = len(ids) // 2
    _CTX.update(ctx=ctx, ids=ids, first=ids[:half], second=ids[half:], real=real)
    return _CTX


def _corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def _slope(y, x):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((a - mx) ** 2 for a in x)


def play(ids: list[str], runs: int, seed: int = 1001) -> list[dict]:
    S = setup()
    ctx = S["ctx"]
    out = []
    for gid in ids:
        tot, poss, ot, hs, as_ = [], [], [], [], []
        res = None
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine="stage2")
            tot.append(res.home_score + res.away_score)
            hs.append(res.home_score)
            as_.append(res.away_score)
            hm = sum(float(ln.get("minutes") or 0) for ln in res.player_lines if ln.get("team_id") == res.home_team_id)
            ot.append(max(0.0, hm / 5.0 - 48.0))
            poss.append(float(res.possessions) * 48.0 / (48.0 + ot[-1]))
        odds = ctx["odds"].get(str(gid)) or {}
        out.append({"game_id": gid, "home": res.home_team_id, "away": res.away_team_id, "total": statistics.fmean(tot),
                    "sd": statistics.pstdev(tot) if runs > 1 else None, "pace48": statistics.fmean(poss),
                    "home_pts": statistics.fmean(hs), "away_pts": statistics.fmean(as_),
                    "ot": statistics.fmean(1.0 if o > 0.5 else 0.0 for o in ot),
                    "market": (odds.get("total") or {}).get("line"), "spread": (odds.get("spread") or {}).get("home_line")})
    return out


def score(rows: list[dict]) -> dict:
    S = setup()
    real = S["real"]
    rr = [r for r in rows if r["game_id"] in real]
    x = [real[r["game_id"]]["t05"] for r in rr]
    out = {"games": len(rows),
           "pace_sim": round(statistics.fmean(r["pace48"] for r in rr), 2),
           "pace_real": round(statistics.fmean(real[r["game_id"]]["pace48"] for r in rr), 2),
           "pace_slope_sim": round(_slope([r["pace48"] for r in rr], x), 1),
           "pace_slope_real": round(_slope([real[r["game_id"]]["pace48"] for r in rr], x), 1),
           "pace_corr_game": round(_corr([r["pace48"] for r in rr], [real[r["game_id"]]["pace48"] for r in rr]), 3)}
    sp, rp = defaultdict(list), defaultdict(list)
    for r in rr:
        for t in (r["home"], r["away"]):
            sp[t].append(r["pace48"])
            rp[t].append(real[r["game_id"]]["pace48"])
    teams = sorted(sp)
    out["pace_corr_team"] = round(_corr([statistics.fmean(sp[t]) for t in teams], [statistics.fmean(rp[t]) for t in teams]), 3)
    out["pace_sd_team_sim"] = round(statistics.pstdev([statistics.fmean(sp[t]) for t in teams]), 2)
    out["pace_sd_team_real"] = round(statistics.pstdev([statistics.fmean(rp[t]) for t in teams]), 2)
    mk = [r for r in rows if r["market"] is not None]
    e = [r["total"] - float(r["market"]) for r in mk]
    out.update({"total_bias": round(statistics.fmean(e), 2), "total_mae": round(statistics.fmean(abs(v) for v in e), 3),
                "total_corr": round(_corr([r["total"] for r in mk], [float(r["market"]) for r in mk]), 3),
                "ot_rate": round(statistics.fmean(r["ot"] for r in rows), 4)})
    sds = [r["sd"] for r in rows if r["sd"] is not None]
    if sds:
        out["total_sd_in_game"] = round(statistics.fmean(sds), 2)
    sm = [r for r in rows if r["spread"] is not None]
    out["spread_mae"] = round(statistics.fmean(abs(r["home_pts"] - r["away_pts"] + float(r["spread"])) for r in sm), 3)
    return out


def apply(settings: dict) -> None:
    G.LOOP.update(settings)


def parse_set(text: str) -> dict:
    out = {}
    for part in filter(None, (text or "").split(",")):
        k, v = part.split("=")
        out[k.strip()] = float(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("scan", "check"))
    ap.add_argument("--key", default="k_pace")
    ap.add_argument("--tie", default="")
    ap.add_argument("--values", default="")
    ap.add_argument("--set", default="")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--half", choices=("first", "second", "both"), default="first")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    S = setup()
    base = parse_set(args.set)
    apply(base)
    halves = ("first", "second") if args.half == "both" else (args.half,)
    results = []
    t0 = time.time()
    if args.cmd == "scan":
        keys = [args.key] + [k for k in args.tie.split(",") if k]
        for v in (float(x) for x in args.values.split(",")):
            apply({k: v for k in keys})
            for h in halves:
                sc = score(play(S[h], args.runs))
                results.append({"setting": {**base, **{k: v for k in keys}}, "half": h, **sc})
                print(json.dumps(results[-1]), f"{time.time() - t0:.0f}s", flush=True)
    else:
        for h in halves:
            sc = score(play(S[h], args.runs))
            results.append({"setting": base, "half": h, **sc})
            print(json.dumps(results[-1]), f"{time.time() - t0:.0f}s", flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
