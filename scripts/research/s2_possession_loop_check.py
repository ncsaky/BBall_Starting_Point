#!/usr/bin/env python3
"""Stage 2 possession loop: fits, per-player spot-check (turnovers and steals first) and speed, next to today's engine.

Light by default (about a minute): the rule fits (stage2.loop_fit, no game simulation), then N replayed 2025-26 games
(real availability and minutes) on both engines with the same seeds, scored per player against real 2025-26 per-36
rates (data/calibration/nba_2025_26_targets.json), split into the fit half and the held-out half of players (the same
fixed hash as the shooting and rebound checks). Output: output/stage2/possession_loop_check.json.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_possession_loop_check.py [--games 600] [--skip-fits]
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

from nba_gm_data.calibration_targets import aggregate_from_results, compare, load_targets  # noqa: E402
from nba_gm_data.schema import to_plain  # noqa: E402
from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids  # noqa: E402
from nba_gm_data.stage2 import engine as E  # noqa: E402
from nba_gm_data.stage2 import loop_fit as LF  # noqa: E402
from nba_gm_data.stage2.cards import KINDS, N_KINDS  # noqa: E402
from nba_gm_data.stage2.game_contexts import split_half  # noqa: E402

STATS = ("points", "fga", "fg3a", "fta", "rebounds", "assists", "turnovers", "steals", "blocks")
MIN_SIM_MINUTES = 250.0
REAL_ZONES = {"rim": (.281, .674), "short": (.208, .448), "mid": (.097, .417), "three": (.414, .361)}


def per_player(results: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for r in results:
        for line in r["player_lines"]:
            m = float(line.get("minutes") or 0)
            if m <= 0:
                continue
            rec = out[str(line["player_id"])]
            rec["minutes"] += m
            for s in STATS + ("ftm", "fgm"):
                rec[s] += float(line.get(s) or 0)
    return out


def score(sim: dict, real: dict, stat: str, half: int | None) -> dict | None:
    pairs = []
    for pid, rec in sim.items():
        row = real.get(pid)
        if row is None or rec["minutes"] < MIN_SIM_MINUTES or (half is not None and split_half(pid) != half):
            continue
        if stat == "ts_pct":
            den = 2 * (rec["fga"] + .44 * rec["fta"])
            if den <= 0 or row.get("ts_pct") is None:
                continue
            pairs.append((rec["points"] / den, float(row["ts_pct"]), rec["minutes"]))
        else:
            pairs.append((36 * rec[stat] / rec["minutes"], float(row[f"{stat}_per36"]), rec["minutes"]))
    if len(pairs) < 5:
        return None
    w = sum(p[2] for p in pairs)
    mp = sum(p[2] * p[0] for p in pairs) / w
    mr = sum(p[2] * p[1] for p in pairs) / w
    cov = sum(p[2] * (p[0] - mp) * (p[1] - mr) for p in pairs) / w
    vp = sum(p[2] * (p[0] - mp) ** 2 for p in pairs) / w
    vr = sum(p[2] * (p[1] - mr) ** 2 for p in pairs) / w
    mse = sum(p[2] * (p[0] - p[1]) ** 2 for p in pairs) / w
    return {"players": len(pairs), "real": round(mr, 3), "sim": round(mp, 3), "bias": round(mp - mr, 3),
            "rmse": round(math.sqrt(mse), 3), "corr": round(cov / math.sqrt(vp * vr), 3) if vp > 0 and vr > 0 else None}


def misses(sim: dict, real: dict, stat: str, n: int = 12) -> dict:
    rows = []
    for pid, rec in sim.items():
        row = real.get(pid)
        if row is None or rec["minutes"] < MIN_SIM_MINUTES:
            continue
        rows.append((36 * rec[stat] / rec["minutes"] - float(row[f"{stat}_per36"]), row.get("name"),
                     round(36 * rec[stat] / rec["minutes"], 2), round(float(row[f"{stat}_per36"]), 2)))
    rows.sort()
    return {"over": [r[1:] for r in rows[::-1][:n]], "under": [r[1:] for r in rows[:n]]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=600)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--skip-fits", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "output/stage2/possession_loop_check.json"))
    args = ap.parse_args()
    report: dict = {}
    t0 = time.time()
    if not args.skip_fits:
        fits = LF.fit_all(ROOT)
        report["fits"] = {k: {"model": v["model"], "halves": v["halves"]} for k, v in fits.items()}
        report["fits"]["dunk_share"] = LF.fit_dunk_share(ROOT)
        report["fits"]["hook"] = LF.fit_hook(ROOT)
        report["fits"]["fouls_by_action_analytic"] = {k: v for k, v in LF.fit_fouls(ROOT).items() if k not in ("under", "over")}
        print(f"fits done {time.time() - t0:.1f}s", flush=True)
    context = load_sim_context(ROOT)
    ids = validation_game_ids(context, None, False)
    ids = ids[:: max(1, len(ids) // args.games)][: args.games]
    real = load_targets(ROOT / "data/calibration/nba_2025_26_targets.json")["players"]
    captured = []
    original = E.play_stage2_game

    def capture(*a, **k):
        g, extra = original(*a, **k)
        captured.append(g)
        return g, extra

    E.play_stage2_game = capture
    engines = {}
    for engine in ("stage2", "current"):
        sim_game_with_context(context, ids[0], mode="replay-real-minutes", seed=args.seed, engine=engine)  # warm caches
        captured.clear()
        start = time.perf_counter()
        results = [to_plain(sim_game_with_context(context, gid, mode="replay-real-minutes", seed=args.seed, engine=engine))
                   for gid in ids]
        seconds = time.perf_counter() - start
        poss = sum(r["possessions"] * 2 for r in results)
        agg = aggregate_from_results(results)
        targets = load_targets(ROOT / "data/calibration/nba_2025_26_targets.json")
        league = compare(agg["league_totals"], agg["player_lines"], targets, min_sim_games=3)
        sim = per_player(results)
        engines[engine] = {
            "games": len(results), "seconds": round(seconds, 2), "ms_per_game": round(1000 * seconds / len(results), 2),
            "ms_per_possession": round(1000 * seconds / poss, 4) if engine == "stage2" else None,
            "league": {m["metric"]: {"sim": m["sim"], "target": m["target"], "in_band": m["within_band"]} for m in league["league"]},
            "league_in_band": league["league_summary"],
            "players": {stat: {"all": score(sim, real, stat, None), "fit_half": score(sim, real, stat, 0),
                               "held_half": score(sim, real, stat, 1)} for stat in STATS + ("ts_pct",)},
            "misses": {stat: misses(sim, real, stat) for stat in ("turnovers", "steals", "fta", "points")},
        }
        if engine == "stage2":
            d = [0] * (N_KINDS * 3)
            for g in captured:
                for i, v in enumerate(g.diag):
                    d[i] += v
            tot = sum(d[3 * k] for k in range(N_KINDS)) or 1
            kinds = {KINDS[k][0]: {"share": round(d[3 * k] / tot, 4), "fg": round(d[3 * k + 1] / max(1, d[3 * k]), 4),
                                   "shooting_fouls_per_try": round(d[3 * k + 2] / max(1, d[3 * k] + d[3 * k + 2]), 4)}
                     for k in range(N_KINDS)}
            zones = defaultdict(lambda: [0, 0])
            for k in range(N_KINDS):
                z = ("rim", "short", "mid", "three")[KINDS[k][2]]
                zones[z][0] += d[3 * k]
                zones[z][1] += d[3 * k + 1]
            engines[engine]["shot_kinds"] = kinds
            engines[engine]["zones"] = {z: {"share": round(a / tot, 4), "fg": round(m / max(1, a), 4),
                                            "real_share": REAL_ZONES[z][0], "real_fg": REAL_ZONES[z][1]}
                                        for z, (a, m) in zones.items()}
            mins = []
            for g in captured:
                for t in (g.home, g.away):
                    mins += [(t.target_s[i] / 60, t.secs[i] / 60) for i in range(len(t.cards))]
            engines[engine]["minutes_vs_plan"] = {
                "mean_abs_diff": round(statistics.fmean(abs(b - a) for a, b in mins), 2),
                "sd_diff": round(statistics.pstdev([b - a for a, b in mins]), 2)}
        print(f"{engine}: {len(results)} games {seconds:.1f}s", flush=True)
    E.play_stage2_game = original
    report["replay"] = engines
    report["seconds"] = round(time.time() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1, default=str))
    for stat in STATS + ("ts_pct",):
        row = []
        for engine in ("stage2", "current"):
            h = engines[engine]["players"][stat]["held_half"] or {}
            a = engines[engine]["players"][stat]["all"] or {}
            row.append(f"{engine} all {a.get('bias')}/{a.get('rmse')}/{a.get('corr')} held {h.get('bias')}/{h.get('rmse')}/{h.get('corr')}")
        print(f"{stat:10s} | " + " | ".join(row))
    print(json.dumps({e: engines[e]["league_in_band"] for e in engines}))
    print(f"stage2 {engines['stage2']['ms_per_game']} ms/game, {engines['stage2']['ms_per_possession']} ms/possession;"
          f" current {engines['current']['ms_per_game']} ms/game")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
