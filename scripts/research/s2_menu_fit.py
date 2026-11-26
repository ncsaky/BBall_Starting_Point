#!/usr/bin/env python3
"""S2-TENTH: fit the Stage 2 shot-menu weights (cuts, rolls, post-ups inside the rim and short-paint splits) to NBA.com's
2025-26 play types, offline (research only).

The shot-location habit (T02) fixes each player's rim and short-paint share; the menu only splits them between drives,
finishes off a pass (cuts, rolls) and post-ups. So each player's half-court shot tries (from a replay, s2_tenth_players.py
with per-kind tries) times his menu under a candidate setting predicts his cut + roll finishes and post-ups. Targets:
real cut + roll-man and post-up possessions per 36 (data/research/nba_playtypes_2025_26.json) times CONV (the share of
play-type possessions that end in a shot try rather than a turnover or a non-shooting foul). Fit half of the players
(stage2.game_contexts.split_half), checked on the other half.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_menu_fit.py output/s2t/players_base.json
"""
from __future__ import annotations

import itertools
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
CONV = .92
HALFCOURT = range(10)   # trace rows from before short_finish; see predict()


def corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx, vy = sum((a - mx) ** 2 for a in x), sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy)


def main() -> int:
    from nba_gm_data.sim import load_sim_context
    from nba_gm_data.stage2 import cards as C
    from nba_gm_data.stage2.game_contexts import split_half
    data = json.loads(Path(sys.argv[1]).read_text())["players"]
    ctx = load_sim_context(ROOT)
    canonical = ctx["canonical"]
    byid = {p["id"]: p for p in canonical.get("players", []) if p.get("id")}
    means = C.means_for(ROOT)
    rows = []
    for pid, r in data.items():
        e = r["eng"][0]
        if "kinds" not in e or pid not in byid:
            continue
        flat = C.flat_for_player(canonical, byid[pid])
        if flat is None:
            continue
        hc = sum(e["kinds"][i] for i in HALFCOURT)
        rows.append({"pid": pid, "name": r["name"], "w": r["minutes"], "hc": hc, "flat": flat, "half": split_half(pid),
                     "cr": r["real"]["cutroll"] * CONV, "post": r["real"]["post"] * CONV,
                     "cr0": e["kinds"][C.KIND_INDEX["rim_finish"]], "post0": e["kinds"][C.KIND_INDEX["hook"]]})
    RF, HK, SF = C.KIND_INDEX["rim_finish"], C.KIND_INDEX["hook"], C.KIND_INDEX["short_finish"]

    def predict(setting):
        old = {k: C.MENU[k] for k in setting}
        C.MENU.update(setting)
        out = []
        for row in rows:
            m = C.shot_menu(row["flat"], means)
            out.append((row["hc"] * (m[RF] + m[SF]), row["hc"] * m[HK]))
        C.MENU.update(old)
        return out

    def score(setting, half):
        pr = predict(setting)
        res = {}
        for j, key in ((0, "cr"), (1, "post")):
            sel = [(p[j], row[key], row["w"]) for p, row in zip(pr, rows) if half is None or row["half"] == half]
            W = sum(s[2] for s in sel)
            res[key] = {"mae": sum(abs(a - b) * w for a, b, w in sel) / W, "rmse": math.sqrt(sum((a - b) ** 2 * w for a, b, w in sel) / W), "corr": corr([s[0] for s in sel], [s[1] for s in sel]),
                        "eng": sum(a * w for a, _, w in sel) / W, "real": sum(b * w for _, b, w in sel) / W}
        res["obj"] = (res["cr"]["rmse"] + res["post"]["rmse"] + abs(res["cr"]["eng"] - res["cr"]["real"])
                      + abs(res["post"]["eng"] - res["post"]["real"]))
        return res

    def show(label, setting):
        a, h = score(setting, 0), score(setting, 1)
        print(f"{label:10s} fit {a['obj']:.4f} held {h['obj']:.4f} | cut+roll mae {h['cr']['mae']:.3f} rmse {h['cr']['rmse']:.3f} corr {h['cr']['corr']:.3f} "
              f"lvl {h['cr']['eng']:.2f}/{h['cr']['real']:.2f} | post mae {h['post']['mae']:.3f} rmse {h['post']['rmse']:.3f} corr {h['post']['corr']:.3f} "
              f"lvl {h['post']['eng']:.2f}/{h['post']['real']:.2f}  {json.dumps(setting)}", flush=True)

    base = {}
    show("first", base)
    import random
    rng = random.Random(7)
    bounds = {"rim_cut": (.05, 4.0), "rim_roll": (.05, 6.0), "rim_post": (0.0, 2.0), "short_post": (.1, 4.0),
              "drive_pow": (.3, 2.0), "cut_pow": (.5, 4.0), "roll_pow": (.5, 4.0), "post_pow": (.5, 4.0), "short_fin": (0.0, 8.0)}
    for rs in (0.0, 1.0):
        best = {"roll_screen": rs, **{k: C.MENU[k] for k in bounds}}
        best_score = score(best, 0)["obj"]
        step = .5
        for it in range(1500):
            cand = dict(best)
            for k in rng.sample(list(bounds), rng.randint(1, 3)):
                lo, hi = bounds[k]
                cand[k] = min(hi, max(lo, cand[k] * math.exp(step * rng.gauss(0, 1)) if cand[k] > 0 else rng.uniform(lo, hi) * .2))
            sc = score(cand, 0)["obj"]
            if sc < best_score:
                best, best_score = cand, sc
            if it % 500 == 499:
                step *= .6
        show(f"rs={rs:g}", {"roll_screen": rs})
        show(f"fit rs={rs:g}", {k: round(v, 3) for k, v in best.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
