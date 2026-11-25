#!/usr/bin/env python3
"""Stage 2 end of quarters and games (S2-SCHEMES, part 2): overtime, close finishes, two-for-ones, late timeouts.

Replays 2025-26 games (real availability and minutes) and records, per game: the margin with 60 and 24 seconds left in
the 4th quarter, overtime, possessions started in the last 42 seconds of each quarter and whether the first of them
ended with an early shot (the rotation study's two-for-one measure), and the end-of-game timeouts the engine called.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_endgame_check.py --runs 4 [--limit 600] [loop.KEY=V ...]

Real references (data/research/rotation_evidence.json, regular seasons 2023-26 pooled): overtime 4.4% (2025-26),
two-for-one early shot by possession gained at 30-34 / 35-38 / 39-42 seconds: .19 / .53 / .65, and a second
possession after an early shot .91-.97; late timeouts per team in the last two minutes of the 4th: 0.55.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output" / "s2schemes"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--mode", default="replay-real-minutes")
    ap.add_argument("--tag", default="")
    args, rest = ap.parse_known_args()
    from nba_gm_data.stage2 import coach as C, game as G, screens as S
    applied = {}
    for a in rest:
        key, value = a.split("=", 1)
        table, name = key.split(".", 1)
        {"loop": G.LOOP, "coach": C.COACH, "screens": S.SCREENS}[table][name] = float(value)
        applied[key] = float(value)
    from nba_gm_data.sim import load_sim_context, sim_game_with_context, validation_game_ids

    state = {}
    orig = G.Game.possession

    def possession(self, off, de, start):
        rec = state.get(id(self))
        if rec is None:
            rec = state[id(self)] = {"m60": None, "m24": None, "q": defaultdict(list), "game": self}
        p, t = self.period, self.t_left
        if p == 4 and rec["m60"] is None and t <= 60.0:
            rec["m60"] = self.home.points - self.away.points
        if p == 4 and rec["m24"] is None and t <= 24.0:
            rec["m24"] = self.home.points - self.away.points
        t0 = t
        res = orig(self, off, de, start)
        if t0 <= 42.0:
            rec["q"][p].append((t0, t0 - self.t_left, res))
        return res

    G.Game.possession = possession
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    if args.limit:
        ids = ids[:: max(1, len(ids) // args.limit)][:args.limit]
    rows = []
    t0 = time.time()
    box = {str(g.get("game_id")): g for g in ctx["boxscores"]}
    real_final = Counter()
    for gid in ids:
        rg = box.get(str(gid))
        if rg and rg.get("home_score") is not None:
            mins = sum(float(p.get("minutes") or 0) for p in rg.get("players", []))
            real_final["ot" if mins > 490 else min(abs(rg["home_score"] - rg["away_score"]), 30)] += 1
        for r in range(args.runs):
            state.clear()
            res = sim_game_with_context(ctx, gid, mode=args.mode, seed=args.seed + r, engine="stage2")
            rec = next(iter(state.values()), None)
            if rec is None:
                continue
            g = rec["game"]
            rows.append({"ot": 1 if g.period > 4 else 0, "m60": rec["m60"], "m24": rec["m24"],
                         "final": abs(g.home.points - g.away.points),
                         "q": {p: v for p, v in rec["q"].items()},
                         "late_to": getattr(g, "late_timeouts", 0), "adv": getattr(g, "advances", 0),
                         "two4one": getattr(g, "two_for_one", 0)})
    el = time.time() - t0
    n = len(rows)
    out = {"games": n, "seconds": round(el, 1), "overrides": applied,
           "ot_rate": round(sum(r["ot"] for r in rows) / n, 4)}
    nr = sum(real_final.values())
    sim_final = Counter("ot" if r["ot"] else min(r["final"], 30) for r in rows)
    band = lambda c, ks, n: round(sum(c[k] for k in ks) / max(1, n), 4)  # noqa: E731
    out["final_margin"] = {"real": {"1_3": band(real_final, (1, 2, 3), nr), "4_5": band(real_final, (4, 5), nr),
                                    "6_8": band(real_final, (6, 7, 8), nr), "ot": band(real_final, ("ot",), nr)},
                           "sim": {"1_3": band(sim_final, (1, 2, 3), n), "4_5": band(sim_final, (4, 5), n),
                                   "6_8": band(sim_final, (6, 7, 8), n), "ot": band(sim_final, ("ot",), n)}}
    for w in (3, 5):
        close60 = [r for r in rows if r["m60"] is not None and abs(r["m60"]) <= w]
        out[f"share_within_{w}_at_60s"] = round(len(close60) / n, 4)
        out[f"ot_given_within_{w}_at_60s"] = round(sum(r["ot"] for r in close60) / max(1, len(close60)), 4)
        close24 = [r for r in rows if r["m24"] is not None and abs(r["m24"]) <= w]
        out[f"share_within_{w}_at_24s"] = round(len(close24) / n, 4)
        out[f"ot_given_within_{w}_at_24s"] = round(sum(r["ot"] for r in close24) / max(1, len(close24)), 4)
    dist = Counter(r["m24"] for r in rows if r["m24"] is not None and abs(r["m24"]) <= 4)
    out["margin_at_24s_counts"] = {str(k): round(v / n, 4) for k, v in sorted(dist.items())}
    # Two-for-one measure: the first possession that STARTS with 30-42 s left in a quarter (Q1-Q3): did it end with
    # 25+ seconds left? (The study: first FGA with 25+ s left on a possession gained at 30-42 s.)
    bands = {"30_34": (30, 34.99), "35_38": (35, 38.99), "39_42": (39, 42.0)}
    early = defaultdict(list)
    poss_last42 = []
    for r in rows:
        for p, lst in r["q"].items():
            if int(p) > 3:
                continue
            poss_last42.append(len(lst))
            first = next(((t, d, res) for t, d, res in lst if 30.0 <= t <= 42.0), None)
            if first is None:
                continue
            t, d, res = first
            for b, (lo, hi) in bands.items():
                if lo <= t <= hi:
                    early[b].append(1 if t - d >= 25.0 else 0)
    out["two_for_one_early_end"] = {b: round(statistics.fmean(v), 3) if v else None for b, v in early.items()}
    out["two_for_one_n"] = {b: len(v) for b, v in early.items()}
    out["possessions_in_last_42s_q1_q3"] = round(statistics.fmean(poss_last42), 3) if poss_last42 else None
    out["late_timeouts_per_team_game"] = round(sum(r["late_to"] for r in rows) / n / 2, 3)
    out["advances_per_game"] = round(sum(r["adv"] for r in rows) / n, 3)
    out["two_for_ones_per_game"] = round(sum(r["two4one"] for r in rows) / n, 3)
    print(json.dumps(out, indent=1))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"endgame{'_' + args.tag if args.tag else ''}.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
