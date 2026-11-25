#!/usr/bin/env python3
"""Fit the S2-USAGE loop numbers (who takes the shots) on replayed 2025-26 games.

Each evaluation replays every 2025-26 regular-season game RUNS times with Stage 2 (the betting test's replay mode: real
availability and minutes) under one setting of the loop numbers, and scores each rotation player's per-36 points,
threes made, assists, rebounds and usage against his real 2025-26 numbers (calibration targets file), minutes-weighted,
on two halves of the players (stage2.game_contexts.split_half: the fit half and the held-out half), plus putback points
against Basketball Index and the league levels (points, free throws, assists per 36).

    # score settings (JSON list of {"LOOP.key": value, "MENU.key": value, ...}):
    PYTHONPATH=src .venv/bin/python scripts/research/s2_usage_fit.py eval --sets '[{}, {"LOOP.ast_power": 1.5}]'
    # coordinate search on the fit half:
    PYTHONPATH=src .venv/bin/python scripts/research/s2_usage_fit.py search --params LOOP.ast_power=1,1.5,2 ...

Research only: no rating is changed; the fitted numbers are written into stage2/game.py and cards.py by hand.
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
sys.path.insert(0, str(ROOT / "scripts" / "research"))
STATS = ("points", "fg3m", "assists", "rebounds", "fga", "fta", "turnovers", "offensive_rebounds")


def apply(setting: dict) -> dict:
    """Set the loop and card numbers; returns the previous values."""
    from nba_gm_data.stage2 import cards as C
    from nba_gm_data.stage2 import game as G
    prev = {}
    for key, value in setting.items():
        mod, name = key.split(".", 1)
        table = {"LOOP": G.LOOP, "MENU": C.MENU, "TRANS": C.TRANS, "USAGE": C.USAGE, "ASSISTS": C.ASSISTS}[mod]
        prev[key] = table.get(name)
        table[name] = value
    return prev


def replay(ctx, gids, runs: int, seed: int, shots: bool = False) -> tuple[dict, dict]:
    from nba_gm_data.sim import sim_game_with_context
    from nba_gm_data.stage2 import game as G
    G.SHOT_TRACE = {} if shots else None
    tot: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for gid in gids:
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine="stage2")
            for ln in res.player_lines:
                a = tot[ln["player_id"]]
                a["minutes"] += float(ln.get("minutes") or 0) / runs
                for k in STATS:
                    a[k] += float(ln.get(k) or 0) / runs
    trace = G.SHOT_TRACE or {}
    G.SHOT_TRACE = None
    return {k: dict(v) for k, v in tot.items()}, {p: [[v / runs for v in row] for row in rows] for p, rows in trace.items()}


def real_table(root: Path, min_minutes: float) -> dict[str, dict]:
    from s2_usage_breakdown import bbi_table
    targets = json.loads((root / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    bbi = bbi_table(root)
    out = {}
    for pid, t in targets.items():
        m = float(t.get("minutes") or 0)
        if m < min_minutes:
            continue
        b = bbi.get(pid, {})
        scale = t["points_per36"] / b["pts75"] if b.get("pts75") else None
        out[pid] = {"minutes": m, "points": t["points_per36"], "fg3m": 36.0 * float(t.get("fg3m") or 0) / m,
                    "assists": t["assists_per36"], "rebounds": t["rebounds_per36"], "fga": t["fga_per36"],
                    "fta": t["fta_per36"], "turnovers": t["turnovers_per36"],
                    "putpts": b["putpts75"] * scale if scale and "putpts75" in b else None}
    return out


PLAYTYPES: dict | None = None
PT_GROUPS = {"transition": (("trans_rim", "trans_three"), ("transition",)), "cut_roll": (("rim_finish",), ("cut", "roll_man")),
             "post": (("hook",), ("post_up",)), "putback": (("putback",), ("putbacks",)),
             "self": (("rim_drive", "floater", "short_jumper", "mid_pull", "three_pull"), ("isolation", "ball_handler", "handoff"))}


def playtype_match(eng: dict, shots: dict) -> dict:
    """Stage 2 action tries per 36 against real play-type possessions per 36 (NBA.com, 2025-26): level and correlation."""
    global PLAYTYPES
    from nba_gm_data.stage2.cards import KIND_INDEX
    if PLAYTYPES is None:
        PLAYTYPES = json.loads((ROOT / "data/research/nba_playtypes_2025_26.json").read_text())["players"]
    out = {}
    for g, (kinds, types) in PT_GROUPS.items():
        xs, ys = [], []
        for pid, rows in shots.items():
            e, p = eng.get(pid), PLAYTYPES.get(pid)
            if not e or not p or e["minutes"] < 500 or not any(t in p["playtypes"] for t in types):
                continue
            f = 36.0 / e["minutes"]
            xs.append(sum(rows[KIND_INDEX[k]][0] for k in kinds) * f)
            ys.append(sum((p["playtypes"].get(t) or {}).get("poss") or 0.0 for t in types) * f)
        me, mr = statistics.fmean(xs), statistics.fmean(ys)
        cv = sum((a - me) * (b - mr) for a, b in zip(xs, ys))
        out[g] = {"eng": round(me, 3), "real": round(mr, 3),
                  "corr": round(cv / math.sqrt(sum((a - me) ** 2 for a in xs) * sum((b - mr) ** 2 for b in ys)), 3)}
    return out


def score(eng: dict, shots: dict, real: dict) -> dict:
    from nba_gm_data.stage2.cards import KIND_INDEX
    from nba_gm_data.stage2.game_contexts import split_half
    put = KIND_INDEX["putback"]
    out = {"playtypes": playtype_match(eng, shots)}
    for half in (0, 1, None):
        rows = []
        for pid, r in real.items():
            e = eng.get(pid)
            if e is None or e["minutes"] < 300 or (half is not None and split_half(pid) != half):
                continue
            f = 36.0 / e["minutes"]
            pe = {k: e[k] * f for k in STATS}
            pe["usage"] = pe["fga"] + .44 * pe["fta"] + pe["turnovers"]
            re = dict(r)
            re["usage"] = r["fga"] + .44 * r["fta"] + r["turnovers"]
            if pid in shots:
                sh = shots[pid][put]
                pe["putpts"] = (2 * sh[2] + .75 * sh[4]) * f
            rows.append((pe, re, r["minutes"]))
        w = sum(x[2] for x in rows)
        res = {"players": len(rows)}
        for k in ("points", "fg3m", "assists", "rebounds", "usage", "fta", "putpts"):
            pairs = [(x[0].get(k), x[1].get(k), x[2]) for x in rows if x[0].get(k) is not None and x[1].get(k) is not None]
            ww = sum(p[2] for p in pairs)
            mae = sum(abs(a - b) * c for a, b, c in pairs) / ww
            rel = sum(abs(a - b) / max(.5, b) * c for a, b, c in pairs) / ww
            ea, ra = [p[0] for p in pairs], [p[1] for p in pairs]
            me, mr = statistics.fmean(ea), statistics.fmean(ra)
            cv = sum((a - me) * (b - mr) for a, b in zip(ea, ra))
            corr = cv / math.sqrt(sum((a - me) ** 2 for a in ea) * sum((b - mr) ** 2 for b in ra))
            res[k] = {"mae": round(mae, 4), "rel": round(rel, 4), "corr": round(corr, 4),
                      "eng": round(sum(p[0] * p[2] for p in pairs) / ww, 3), "real": round(sum(p[1] * p[2] for p in pairs) / ww, 3)}
        out["all" if half is None else f"half{half}"] = res
    return out


def objective(sc: dict, half: str) -> float:
    """Relative season misses (the props script's measure) on points, threes and assists, with rebounds; a level
    penalty keeps league points, assists and free throws per 36 at their real levels."""
    h = sc[half]
    a = sc["all"]
    lvl = sum(abs(a[k]["eng"] / a[k]["real"] - 1) for k in ("points", "assists", "fta"))
    return h["points"]["rel"] + .5 * h["fg3m"]["rel"] + .5 * h["assists"]["rel"] + .25 * h["rebounds"]["rel"] + 2 * lvl


def usage_refit(args, run, ctx, gids, real) -> int:
    """Refit the usage rule through the loop: regress log(real usage / loop usage) on the rule's terms (fit half,
    minutes-weighted, ridge toward no change), divide by the loop's usage power, add to the rule, replay, repeat. The
    constant keeps the minutes-weighted average log weight unchanged."""
    from nba_gm_data.stage2 import cards as C
    from nba_gm_data.stage2.game import LOOP
    from nba_gm_data.stage2.game_contexts import league_flat_inputs, split_half
    from nba_gm_data.stage2.loop_fit import _value, solve_wls
    flats = league_flat_inputs(ROOT)
    base = json.loads(args.base)
    RULE = getattr(C, args.rule)
    stat = "usage" if args.rule == "USAGE" else "assists"
    terms = [k for k in RULE if k != "constant"] + [t for t in args.terms.split(",") if t and t not in RULE]
    setting = dict(base)
    for step in range(args.steps + 1):
        prev = apply(setting)
        eng, shots = replay(ctx, gids, args.runs, args.seed + 100 * step, shots=True)
        rec_model = {k: RULE.get(k, 0.0) for k in ["constant"] + terms}
        apply(prev)
        sc = score(eng, shots, real)
        a = sc["all"]
        print("step", step, stat, "mae fit/held", sc["half0"][stat]["mae"], sc["half1"][stat]["mae"], "rel",
              sc["half0"][stat]["rel"], sc["half1"][stat]["rel"], "corr", sc["half0"][stat]["corr"], sc["half1"][stat]["corr"], "| pts rel fit/held", sc["half0"]["points"]["rel"],
              sc["half1"]["points"]["rel"], "3pm", sc["half0"]["fg3m"]["rel"], sc["half1"]["fg3m"]["rel"], "ast",
              sc["half0"]["assists"]["rel"], sc["half1"]["assists"]["rel"], "lvl pts", a["points"]["eng"], flush=True)
        if step == args.steps:
            break
        rows, ys, ws = [], [], []
        for pid, r in real.items():
            e = eng.get(pid)
            if e is None or e["minutes"] < 300 or pid not in flats or split_half(pid) != 0:
                continue
            f = 36.0 / e["minutes"]
            if stat == "usage":
                ue = (e["fga"] + .44 * e["fta"] + e["turnovers"]) * f
                ur = r["fga"] + .44 * r["fta"] + r["turnovers"]
                power = LOOP["usage_power"]
            else:
                ue, ur = e["assists"] * f, r["assists"]
                power = float(setting.get("LOOP.ast_power", LOOP["ast_power"]))
            if ue <= 0 or ur <= 0:
                continue
            rows.append([_value(flats[pid], t) for t in terms])
            ys.append(math.log(ur / ue) / power)
            ws.append(r["minutes"])
        W = sum(ws)
        mx = [sum(w * x[i] for x, w in zip(rows, ws)) / W for i in range(len(terms))]
        sd = [math.sqrt(sum(w * (x[i] - mx[i]) ** 2 for x, w in zip(rows, ws)) / W) or 1.0 for i in range(len(terms))]
        Z = [[1.0] + [(x[i] - mx[i]) / sd[i] for i in range(len(terms))] for x in rows]
        # ridge: append pseudo-rows pulling each standardized coefficient to zero
        lam = args.ridge * W / len(rows)
        Zr = Z + [[0.0] * (i + 1) + [1.0] + [0.0] * (len(terms) - i - 1) for i in range(len(terms))]
        yr = ys + [0.0] * len(terms)
        wr = ws + [lam] * len(terms)
        beta = solve_wls(Zr, yr, wr)
        delta = {t: beta[i + 1] / sd[i] for i, t in enumerate(terms)}
        new = dict(rec_model)
        for t in terms:
            new[t] = new.get(t, 0.0) + delta[t]
        new["constant"] = rec_model["constant"] - sum(delta[t] * mx[i] for i, t in enumerate(terms))
        print("  step", step, "change", json.dumps({k: round(v, 4) for k, v in delta.items()}), flush=True)
        print("  rule", json.dumps({k: round(v, 5) for k, v in new.items()}), flush=True)
        setting = {**base, **{f"{args.rule}.{k}": round(v, 5) for k, v in new.items()}}
    Path(args.out).write_text(json.dumps(setting, indent=1))
    return 0


def install_oracle(kinds: str, root: Path) -> None:
    """Research only (layer decomposition): rebuild cards with one layer replaced by real 2025-26 evidence, for this
    process only: 'usage' = his usage weight set to his real usage per possession (calibration targets; the loop's
    usage power undone), 't02' = his shot-location habit set to his real rim / other-two / three shares (Basketball
    Index; the other twos split between short paint and midrange in his own T02 proportion). No input file is touched."""
    from nba_gm_data.stage2 import cards as C
    from s2_usage_breakdown import bbi_table
    targets = json.loads((root / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    bbi = bbi_table(root)
    orig = C.build_card
    want = set(kinds.split(","))

    def build(pid, name, flat, means, group="wing", penalty=0.0):
        t = targets.get(pid)
        if "t02" in want and pid in bbi and all(k in bbi[pid] for k in ("rim75", "mid75", "three75")):
            b = bbi[pid]
            tot = b["rim75"] + b["mid75"] + b["three75"]
            sp, md = float(flat.get("T02.short_paint", .15)), float(flat.get("T02.midrange", .15))
            other = b["mid75"] / tot
            flat = dict(flat, **{"T02.rim": b["rim75"] / tot, "T02.three": b["three75"] / tot,
                                 "T02.short_paint": other * sp / max(1e-6, sp + md), "T02.midrange": other * md / max(1e-6, sp + md)})
        c = orig(pid, name, flat, means, group, penalty)
        if "usage" in want and t and float(t.get("minutes") or 0) >= 300:
            used = t["fga_per36"] + .44 * t["fta_per36"] + t["turnovers_per36"]
            c.usage = used / 76.5 * (1.0 - .01 * penalty)
        return c

    C.build_card = build
    C._CARD_CACHE.clear()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("eval", "search", "usage"))
    ap.add_argument("--terms", default="", help="usage mode: comma-separated extra usage-rule terms")
    ap.add_argument("--steps", type=int, default=2)
    ap.add_argument("--rule", default="USAGE", choices=("USAGE", "ASSISTS"))
    ap.add_argument("--oracle", default="", help="research only: usage, t02 or both (comma-separated)")
    ap.add_argument("--ridge", type=float, default=1.0)
    ap.add_argument("--sets", default="[{}]")
    ap.add_argument("--params", nargs="*", default=[])
    ap.add_argument("--base", default="{}")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--half", default="half0")
    ap.add_argument("--games", type=int, default=0, help="every n-th game only (0 = all)")
    ap.add_argument("--out", default="output/s2usage/fit.json")
    args = ap.parse_args()
    from nba_gm_data.sim import load_sim_context, validation_game_ids
    ctx = load_sim_context(ROOT)
    box = {str(g["game_id"]) for g in ctx["boxscores"]}
    gids = [g for g in validation_game_ids(ctx, None, False) if g in box]
    if args.games:
        gids = gids[::args.games]
    real = real_table(ROOT, 500)
    if args.oracle:
        install_oracle(args.oracle, ROOT)
    log = []

    def run(setting: dict) -> dict:
        t0 = time.time()
        prev = apply(setting)
        eng, shots = replay(ctx, gids, args.runs, args.seed, shots=True)
        apply(prev)
        sc = score(eng, shots, real)
        rec = {"setting": setting, "score": sc, "obj_fit": round(objective(sc, args.half), 4),
               "obj_held": round(objective(sc, "half1" if args.half == "half0" else "half0"), 4),
               "seconds": round(time.time() - t0)}
        a = sc["all"]
        print(json.dumps(setting), "| obj fit", rec["obj_fit"], "held", rec["obj_held"], "| pts", a["points"]["rel"],
              a["points"]["corr"], "3pm", a["fg3m"]["rel"], "ast", a["assists"]["rel"], a["assists"]["corr"], "reb",
              a["rebounds"]["rel"], "use", a["usage"]["mae"], "put", a["putpts"]["eng"], "/", a["putpts"]["real"],
              "lvl pts", a["points"]["eng"], "/", a["points"]["real"], "ast", a["assists"]["eng"], "fta", a["fta"]["eng"],
              "/", a["fta"]["real"], f"({rec['seconds']}s)", flush=True)
        print("   play types (Stage 2 / real per 36, corr):", " ".join(f"{g} {v['eng']}/{v['real']} {v['corr']}"
                                                                   for g, v in sc["playtypes"].items()), flush=True)
        log.append(rec)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(log, indent=1))
        return rec

    if args.mode == "usage":
        return usage_refit(args, run, ctx, gids, real)
    if args.mode == "eval":
        base = json.loads(args.base)
        for s in json.loads(args.sets):
            run({**base, **s})
        return 0
    base = json.loads(args.base)
    grid = {}
    for p in args.params:
        k, vals = p.split("=", 1)
        grid[k] = [float(v) for v in vals.split(",")]
    best = run(dict(base))
    for _ in range(args.rounds):
        for k, vals in grid.items():
            for v in vals:
                if base.get(k) == v:
                    continue
                rec = run({**base, k: v})
                if rec["obj_fit"] < best["obj_fit"]:
                    best, base = rec, {**base, k: v}
        print("best so far", json.dumps(base), best["obj_fit"], best["obj_held"], flush=True)
    print("BEST", json.dumps(base), best["obj_fit"], best["obj_held"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
