#!/usr/bin/env python3
"""Refit Stage 2's late-game table on real possessions, with twos, threes and turnovers apart (S2-LAST-POSSESSION).

S2-FINISHES fitted one make shift per situation to points per possession. That matched the points but not how they
come: a trailing team's late threes went in 36-43% of the time against a real 25-30%, its twos too rarely, and a leader
was fouled on purpose too rarely with 10-24 seconds left. Points per possession can be right while ties and 1-3 point
finishes are wrong. This fit moves, per situation (stage2.finishes: time band x the offense's margin band):
- len by the seconds above a 4-second floor; three by the threes-per-possession gap; foul by the free-throw gap;
- make (twos) by the two-point percentage gap, make3 (the extra on threes) by the three-point percentage gap,
  tov by the turnover gap (log-odds);
and, by time band (the last 10 s, 10-24 s, 24-60 s) and the exact lead, the chance the trailing team fouls on purpose
(stage2.finishes_table.TAKE_LATE) by the leader's free throws per possession; the chance a team up three fouls rather
than allow a tying three (UP_THREE) by the trailing team's free throws at exactly -3; the exact-deficit three tilt
(EXACT); and the blowout run-out / concede chances.
Targets: the fit seasons (2023-24 and 2024-25) of output/s2last/lastposs_real.json (s2_lastposs_pbp.py), every
possession starting in the last five minutes of the 4th quarter or an overtime. Stage 2 replays 2025-26 (real
availability and minutes). 2025-26's real possessions are the check season.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_lastposs_fit.py --iters 8 --runs 4 [--start fit.json] [--write]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
OUT = ROOT / "output" / "s2last"
LEADER = ("1_3", "4_6", "7_10", "11+")
FIT_SEASONS = {2024, 2025}


def logit(p: float, lo: float = .01, hi: float = .95) -> float:
    p = min(hi, max(lo, p))
    return math.log(p / (1 - p))


def clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def aggregate(cols, poss, seasons=None):
    """Per situation (time band|margin band), per exact lead in the last minute (b|lead), per exact deficit."""
    from nba_gm_data.stage2 import finishes as FIN
    cells = defaultdict(Counter)
    for row in poss:
        r = dict(zip(cols, row))
        if seasons and r["season"] not in seasons:
            continue
        if r["period"] < 4 or r["t"] > 300:
            continue
        t, m = r["t"], r["m"]
        keys = [f"{FIN.T_BANDS[FIN.t_band(t)]}|{FIN.M_BANDS[FIN.m_band(m)]}"]
        if t <= 60:
            b = 0 if t <= 10 else 1 if t <= 24 else 2
            if m > 0:
                keys.append(f"take{b}|{FIN.take_key(m)}")
            elif m == -3 and b < 2:
                keys.append(f"up3|{b}")
            if -3 <= m <= -1:
                keys.append(f"x{'0_24' if t <= 24 else '24_60'}|{m}")
        for k in keys:
            c = cells[k]
            c["n"] += 1
            for q in ("secs", "pts", "fga", "fgm", "f3a", "f3m", "fta", "ftm", "tov", "take"):
                c[q] += r[q]
    out = {}
    for k, c in cells.items():
        n = c["n"]
        f2a = c["fga"] - c["f3a"]
        out[k] = {"n": n, "secs": c["secs"] / n, "pts": c["pts"] / n, "f3a": c["f3a"] / n, "fta": c["fta"] / n,
                  "tov": c["tov"] / n, "take": c["take"] / n, "f2a_n": f2a, "f3a_n": c["f3a"],
                  "p2": (c["fgm"] - c["f3m"]) / f2a if f2a else None, "p3": c["f3m"] / c["f3a"] if c["f3a"] else None}
    return out


def update(table: dict, real: dict, sim: dict, step: float, min_n: int, min_shots: int) -> None:
    from nba_gm_data.stage2 import finishes as FIN
    cells = table["cells"]
    for tb in FIN.T_BANDS:
        for mb in FIN.M_BANDS:
            k = f"{tb}|{mb}"
            r, s = real.get(k), sim.get(k)
            if not r or not s or r["n"] < min_n:
                continue
            v = list(cells.get(k, FIN.NEUTRAL))
            ln, th, fo, m2, m3x, tv = v + list(FIN.NEUTRAL[len(v):])
            m3 = m2 + m3x
            last_min = tb in ("0_24", "24_60")
            leader_last = tb == "0_24" and mb in LEADER
            if last_min and mb in ("-11", "11+"):
                # Run-outs and concessions (game.LOOP late_runout / late_concede) carry these; length only.
                if tb == "24_60":
                    ln = clip(ln * ((max(.5, r["secs"] - 4.0)) / max(.5, s["secs"] - 4.0)) ** step, .25, 2.5)
                    if mb == "11+":
                        table["late_runout"] = round(clip(table["late_runout"] + step * (s["pts"] - r["pts"]) / 1.1, 0.0, .9), 4)
                elif mb == "-11":
                    table["late_concede"] = round(clip(table["late_concede"] + step * (s["pts"] - r["pts"]) / .9, 0.0, .95), 4)
                cells[k] = (round(ln, 4), 0.0, 0.0, 0.0, 0.0, 0.0)
                continue
            if not leader_last and not (tb == "0_24" and mb == "0"):
                ln = clip(ln * ((max(.5, r["secs"] - 4.0)) / max(.5, s["secs"] - 4.0)) ** step, .25, 2.5)
            th = clip(th + step * (logit(r["f3a"], .002) - logit(s["f3a"], .002)), -4.0, 2.5)
            if not (last_min and mb in LEADER):
                # A leader's free throws in the last minute come from deliberate fouls (TAKE_LATE below).
                fo = clip(fo + step * math.log(max(.02, r["fta"]) / max(.02, s["fta"])), -1.5, 1.5)
            if not leader_last:
                # Includes a leader's shot-clock run-downs with 24-60 s left (real: .15-.26 turnovers a possession up 4-10).
                tv = clip(tv + step * (logit(r["tov"], .005, .6) - logit(s["tov"], .005, .6)), -1.5, 2.0)
            if r["p2"] is not None and s["p2"] is not None and r["f2a_n"] >= min_shots:
                m2 = clip(m2 + step * (logit(r["p2"], .03) - logit(s["p2"], .03)), -1.5, 1.5)
            if r["p3"] is not None and s["p3"] is not None and r["f3a_n"] >= min_shots:
                m3 = clip(m3 + step * (logit(r["p3"], .03) - logit(s["p3"], .03)), -2.0, 1.5)
            elif r["f3a_n"] < min_shots:
                m3 = m2          # too few real threes to fit: the twos' shift
            cells[k] = (round(ln, 4), round(th, 4), round(fo, 4), round(m2, 4), round(m3 - m2, 4), round(tv, 4))
    for b in ("0", "1", "2"):
        for key in FIN.TAKE_KEYS:
            r, s = real.get(f"take{b}|{key}"), sim.get(f"take{b}|{key}")
            if r and s and r["n"] >= 40:
                p = table["take_late"][b][key]
                table["take_late"][b][key] = round(clip(p + step * (r["fta"] - s["fta"]) / 1.75, 0.0, .97), 4)
    for b in (0, 1):
        r, s = real.get(f"up3|{b}"), sim.get(f"up3|{b}")
        if r and s and r["n"] >= 40:
            table["up_three"][b] = round(clip(table["up_three"][b] + step * (r["fta"] - s["fta"]) / 1.75, 0.0, .9), 4)
    exact = table.setdefault("exact", {})
    for tb in ("0_24", "24_60"):
        for m in (-1, -2, -3):
            r, s = real.get(f"x{tb}|{m}"), sim.get(f"x{tb}|{m}")
            if r and s and r["n"] >= min_n:
                k = f"{tb}|{m}"
                v = exact.get(k, 0.0)
                et, e2, eo = (v, 0.0, 0.0) if isinstance(v, (int, float)) else v
                et = clip(et + step * (logit(r["f3a"]) - logit(s["f3a"])), -2.5, 2.5)
                if r["p2"] is not None and s["p2"] is not None and r["f2a_n"] >= 40:
                    e2 = clip(e2 + step * (logit(r["p2"], .03) - logit(s["p2"], .03)), -1.5, 1.5)
                eo = clip(eo + step * (logit(r["tov"], .005, .6) - logit(s["tov"], .005, .6)), -1.5, 1.5)
                exact[k] = [round(et, 4), round(e2, 4), round(eo, 4)]


def gap(real: dict, sim: dict, min_n: int) -> dict:
    """Possession-weighted mean absolute gaps over the situations."""
    tot = Counter()
    w = Counter()
    for k, r in real.items():
        s = sim.get(k)
        if not s or "|" not in k or k.startswith(("take", "up3", "x")) or r["n"] < min_n:
            continue
        for q in ("secs", "pts", "f3a", "fta", "tov"):
            tot[q] += r["n"] * abs(r[q] - s[q])
            w[q] += r["n"]
        for q, nq in (("p2", "f2a_n"), ("p3", "f3a_n")):
            if r[q] is not None and s[q] is not None and r[nq] >= 40:
                tot[q] += r[nq] * abs(r[q] - s[q])
                w[q] += r[nq]
    return {q: round(tot[q] / max(1, w[q]), 4) for q in tot}


def install(table: dict) -> None:
    from nba_gm_data.stage2 import finishes as FIN, game as G
    FIN.install({k: tuple(v) for k, v in table["cells"].items()}, table.get("exact", {}))
    FIN.TAKE_LATE = table["take_late"]
    FIN.UP_THREE = tuple(table["up_three"])
    for key in ("late_runout", "late_concede"):
        G.LOOP[key] = table[key]


def current_table() -> dict:
    from nba_gm_data.stage2 import finishes_table as FT, game as G
    return {"cells": {k: list(v) for k, v in FT.CELLS.items()}, "exact": dict(FT.EXACT),
            "take_late": json.loads(json.dumps(FT.TAKE_LATE)), "up_three": list(FT.UP_THREE),
            "late_runout": G.LOOP["late_runout"], "late_concede": G.LOOP["late_concede"]}


def write_table(table: dict) -> None:
    lines = ['"""Late-game behaviour by situation: the last five minutes of the 4th quarter and overtime (stage2.finishes).',
             "S2-FINISHES fitted it; S2-LAST-POSSESSION refitted it with twos, threes and turnovers apart",
             "(scripts/research/s2_lastposs_fit.py --write) on real play-by-play: the rotation study's fit seasons, 2023-24",
             "and 2024-25 regular seasons (public archive github.com/ramirobentes/nba_data), every possession starting in",
             'the last five minutes of the 4th quarter or an overtime, with Stage 2 replaying 2025-26."""', "",
             '# "time left|offense margin": (len, three, foul, make, make3, tov). Time bands: the last 24 s, 24-60 s, 1-2 min,',
             "# 2-5 min. make applies to every shot, make3 is the extra on threes.",
             "CELLS: dict[str, tuple[float, ...]] = {"]
    for k in sorted(table["cells"]):
        lines.append(f'    "{k}": {tuple(table["cells"][k])},')
    lines += ["}", "",
              "# Chance the trailing team fouls on purpose per possession of the leader, by time band (\"0\" the last 10 s, \"1\" 10-24 s,",
              "# \"2\" 24-60 s) and the exact lead (1-6, 7-10, 11+). FITTED to the leader's real free throws per possession.",
              f"TAKE_LATE: dict[str, dict[str, float]] = {json.dumps(table['take_late'])}", "",
              "# Chance a team up three fouls rather than allow a tying three (the last 10 s, 10-24 s). FITTED to the trailing",
              "# team's real free throws per possession at exactly three down.",
              f"UP_THREE: tuple[float, float] = {tuple(table['up_three'])}", "",
              "# An exact deficit of 1, 2 or 3 in the last minute (\"time band|deficit\"): (three-point tilt, two-point make shift,",
              "# turnover shift) added to its band's terms (stage2.finishes._exact).",
              f"EXACT: dict[str, float | list[float]] = {json.dumps(table.get('exact', {}))}", ""]
    (ROOT / "src" / "nba_gm_data" / "stage2" / "finishes_table.py").write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=8)
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=5001)
    ap.add_argument("--step", type=float, default=.7)
    ap.add_argument("--min-n", type=int, default=150)
    ap.add_argument("--min-shots", type=int, default=60)
    ap.add_argument("--start", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default=str(OUT / "lastposs_fit.json"))
    args = ap.parse_args()
    import s2_lastposs_sim as P
    from nba_gm_data.sim import load_sim_context, validation_game_ids
    real_d = json.loads((OUT / "lastposs_real.json").read_text())
    real = aggregate(real_d["cols"], real_d["poss"], FIT_SEASONS)
    table = json.loads(Path(args.start).read_text())["table"] if args.start else current_table()
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    history = []
    cols = real_d["cols"]
    for it in range(args.iters + 1):
        install(table)
        t0 = time.time()
        poss, _, games, _ = P.measure(ctx, ids, args.runs, args.seed + 10 * it, "replay-real-minutes")
        sim = aggregate(cols, poss)
        ot = sum(1 for g in games if g[3] > 4) / len(games)
        close = sum(1 for g in games if 1 <= abs(g[1]) <= 3) / len(games)
        row = {"iter": it, "seconds": round(time.time() - t0, 1), "gap": gap(real, sim, args.min_n),
               "overtime": round(ot, 4), "reg_1_3": round(close, 4)}
        history.append(row)
        print(json.dumps(row), flush=True)
        Path(args.out).write_text(json.dumps({"table": table, "history": history}, indent=1))
        if it == args.iters:
            break
        update(table, real, sim, args.step, args.min_n, args.min_shots)
    Path(args.out).write_text(json.dumps({"table": table, "history": history}, indent=1))
    if args.write:
        write_table(table)
        print("set in game.LOOP:", {k: table[k] for k in ("late_runout", "late_concede")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
