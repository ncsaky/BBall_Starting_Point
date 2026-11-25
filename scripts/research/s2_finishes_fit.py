#!/usr/bin/env python3
"""Fit Stage 2's late-game table (S2-FINISHES; stage2.finishes) to real play-by-play.

SUPERSEDED by scripts/research/s2_lastposs_fit.py (S2-LAST-POSSESSION: six numbers per situation, deliberate fouls by
exact lead). Kept for the record; don't run it with --write, its table format is the old one.

Targets: per possession in the last five minutes of the 4th quarter, by time left and the offense's margin, the real
seconds, threes, free throws and points of the rotation study's fit seasons (2023-24 and 2024-25 regular seasons;
output/s2finishes/endgame_pbp_real.json from s2_endgame_pbp.py). Stage 2 replays 2025-26 (real availability and
minutes) and each iteration moves every situation's numbers toward its targets:
- len (possession length) by the ratio of the seconds above a 4-second floor;
- three (tilt toward threes) by the log-odds gap of threes per possession;
- foul (shooting-foul log-odds) by the log gap of free throws per possession; for a leader with 24-60 seconds left
  the deliberate-foul chance instead (each deliberate foul is about 1.75 free throws more than a played possession);
- make (shot quality) by the points gap (about 0.55 points per possession per unit of make log-odds);
- the chance a team down 1-3 in the last 24 seconds holds for the last shot, by the seconds gap.
Rules-driven situations are left alone: a leader in the last 24 seconds (the rotation study's deliberate-foul rates
and running out the clock) and the length of a tied team's last possession (holds for the last shot).

    PYTHONPATH=src .venv/bin/python scripts/research/s2_finishes_fit.py --iters 6 --runs 4 [--start table.json] [--write]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
OUT = ROOT / "output" / "s2finishes"

T_BANDS = ("0_24", "24_60", "60_120", "120_300")
M_BANDS = ("-11", "-10_-7", "-6_-4", "-3_-1", "0", "1_3", "4_6", "7_10", "11+")
LEADER = ("1_3", "4_6", "7_10", "11+")
TAKE_KEYS = {"1_3": ("1", "2_3"), "4_6": ("4_6",), "7_10": ("7_10",)}


def logit(p: float) -> float:
    p = min(.95, max(.01, p))
    return math.log(p / (1 - p))


def clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def update(table: dict, real: dict, sim: dict, step: float, min_n: int) -> dict:
    cells = table["cells"]
    report = {}
    for tb in T_BANDS:
        for mb in M_BANDS:
            k = f"{tb}|{mb}"
            r, s = real.get(k), sim.get(k)
            if not r or not s or r["n"] < min_n or s["n"] < min_n * .6:
                continue
            ln, th, fo, mk = cells.get(k, (1.0, 0.0, 0.0, 0.0))
            leader_last = tb == "0_24" and mb in LEADER
            blowout = tb in ("0_24", "24_60") and mb in ("-11", "11+")
            if blowout:
                # Run-outs and concessions (game.LOOP late_runout / late_concede) carry these; length only.
                if tb == "24_60":
                    ln = clip(ln * ((max(.5, r["secs"] - 4.0)) / max(.5, s["secs"] - 4.0)) ** step, .25, 2.5)
                    table["late_runout"] = round(clip(table["late_runout"] + step * (s["pts"] - r["pts"]) / 1.1, 0.0, .9), 4)
                elif mb == "-11":
                    table["late_concede"] = round(clip(table["late_concede"] + step * (s["pts"] - r["pts"]) / .9, 0.0, .95), 4)
                cells[k] = (round(ln, 4), 0.0, 0.0, 0.0)
                report[k] = {q: (r[q], s[q]) for q in ("secs", "pts", "fg3a", "fta")}
                continue
            if not leader_last and not (tb == "0_24" and mb in ("0", "-3_-1")):
                ln = clip(ln * ((max(.5, r["secs"] - 4.0)) / max(.5, s["secs"] - 4.0)) ** step, .25, 2.5)
            if not leader_last:
                th = clip(th + step * (logit(r["fg3a"]) - logit(s["fg3a"])), -2.5, 2.5)
            if tb == "24_60" and mb in TAKE_KEYS:
                for key in TAKE_KEYS[mb]:
                    table["take_24_60"][key] = clip(table["take_24_60"][key] + step * (r["fta"] - s["fta"]) / 1.75, 0.0, .9)
            elif not leader_last:
                fo = clip(fo + step * math.log(max(.02, r["fta"]) / max(.02, s["fta"])), -1.5, 1.5)
            mk = clip(mk + step * (r["pts"] - s["pts"]) / .55, -1.0, 1.0)
            cells[k] = (round(ln, 4), round(th, 4), round(fo, 4), round(mk, 4))
            report[k] = {q: (r[q], s[q]) for q in ("secs", "pts", "fg3a", "fta")}
    exact = table.setdefault("exact", {})
    for tb in ("0_24", "24_60"):
        for m in (-1, -2, -3):
            r, s = real.get(f"x{tb}|{m}"), sim.get(f"x{tb}|{m}")
            if r and s and r["n"] >= min_n:
                k = f"{tb}|{m}"
                exact[k] = round(clip(exact.get(k, 0.0) + step * (logit(r["fg3a"]) - logit(s["fg3a"])), -2.5, 2.5), 4)
    r, s = real.get("0_24|-3_-1"), sim.get("0_24|-3_-1")
    if r and s:
        table["end_last_shot_behind"] = round(clip(table["end_last_shot_behind"] + step * (r["secs"] - s["secs"]) / 7.0,
                                                   0.0, 1.0), 4)
    return report


def gap(real: dict, sim: dict, min_n: int) -> dict:  # noqa: C901
    """Possession-weighted mean absolute gaps over the fitted situations."""
    tot = {q: 0.0 for q in ("secs", "pts", "fg3a", "fta")}
    w = 0
    for k, r in real.items():
        s = sim.get(k)
        if not s or r["n"] < min_n or k.split("|")[0] == "0_24" and k.split("|")[1] in LEADER:
            continue
        for q in tot:
            tot[q] += r["n"] * abs(r[q] - s[q])
        w += r["n"]
    return {q: round(v / max(1, w), 3) for q, v in tot.items()}


def write_table(table: dict) -> None:
    lines = ['"""Late-game behaviour by situation (S2-FINISHES): the last five minutes of the 4th quarter and overtime.',
             "Fitted by scripts/research/s2_finishes_fit.py --write on real play-by-play (the rotation study's fit seasons,",
             "2023-24 and 2024-25 regular seasons; public archive github.com/ramirobentes/nba_data) with Stage 2 replaying",
             '2025-26. stage2.finishes reads it."""', "",
             '# "time left|offense margin": (len, three, foul, make). Time bands: the last 24 s, 24-60 s, 1-2 min, 2-5 min.',
             "CELLS: dict[str, tuple[float, float, float, float]] = {"]
    for k in sorted(table["cells"]):
        lines.append(f'    "{k}": {tuple(table["cells"][k])},')
    lines += ["}", "",
              "# Chance the trailing team fouls on purpose per possession of the leader with 24-60 seconds left, by lead.",
              "# FITTED to the real free throws per possession there (the tagged take-foul fit in game.TAKE_FOUL counts only",
              "# fouls the feed labels as take fouls, about half of them).",
              f"TAKE_24_60: dict[str, float] | None = {json.dumps(table['take_24_60'])}", "",
              "# Three-point tilt added for an exact deficit of 1, 2 or 3 in the last minute (\"time band|deficit\").",
              f"EXACT: dict[str, float] = {json.dumps(table.get('exact', {}))}", ""]
    (ROOT / "src" / "nba_gm_data" / "stage2" / "finishes_table.py").write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=3001)
    ap.add_argument("--step", type=float, default=.8)
    ap.add_argument("--min-n", type=int, default=150)
    ap.add_argument("--start", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default=str(OUT / "finishes_fit.json"))
    args = ap.parse_args()
    import s2_endgame_states as P
    from nba_gm_data.sim import load_sim_context, validation_game_ids
    from nba_gm_data.stage2 import game as G
    real_all = json.loads((OUT / "endgame_pbp_real.json").read_text())
    real = real_all["late_possessions_fit"]
    if args.start:
        table = json.loads(Path(args.start).read_text())
    else:
        table = {"cells": {}, "take_24_60": {k: v[2] for k, v in G.TAKE_FOUL.items()},
                 "end_last_shot_behind": G.LOOP["end_last_shot"]}
    table.setdefault("late_runout", G.LOOP["late_runout"])
    table.setdefault("late_concede", G.LOOP["late_concede"])
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    history = []
    for it in range(args.iters + 1):
        P.install_table(table)
        t0 = time.time()
        sim = P.measure(ctx, ids, args.runs, args.seed + 10 * it)
        g = gap(real, sim["late_possessions"], args.min_n)
        row = {"iter": it, "seconds": round(time.time() - t0, 1), "gap": g, "regulation_margin": sim["regulation_margin"],
               "within_3_at_60": sim["within_at_60"]["3"], "hold_behind": table["end_last_shot_behind"]}
        history.append(row)
        print(json.dumps(row), flush=True)
        if it == args.iters:
            break
        update(table, real, sim["late_possessions"], args.step, args.min_n)
        Path(args.out).write_text(json.dumps({"table": table, "history": history}, indent=1))
    Path(args.out).write_text(json.dumps({"table": table, "history": history, "last_sim": sim}, indent=1))
    if args.write:
        write_table(table)
        print("set in game.LOOP:", {k: table[k] for k in ("end_last_shot_behind", "late_runout", "late_concede")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
