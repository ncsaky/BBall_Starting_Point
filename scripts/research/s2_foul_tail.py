#!/usr/bin/env python3
"""Stage 2 heavy foulers (S2-SCHEMES, part 3): who fouls 4.5+ times per 36 minutes, and why.

Plays the 2025-26 games in one mode (replayed: real availability and minutes; or generated: the game's own rotation)
and compares each player's personal fouls per 36 minutes with his real 2025-26 fouls per 36 in the same games. Each
simulated foul is tagged by how it happened (shooting foul on a drive / other shot, non-shooting, loose ball,
offensive, intentional) and whether the fouler was guarding the night's highest-usage scorer at the time.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_foul_tail.py --runs 2 [--mode sandbox-sim] [loop.KEY=V ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "output" / "s2schemes"


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

    tags = defaultdict(lambda: defaultdict(float))   # player name -> how -> fouls
    defended = defaultdict(float)                    # player name -> shots he was the shot's defender on
    meta = {}
    cur = {"how": "other"}
    orig_shot, orig_foul = G.Game._shot, G.Game._foul
    orig_int, orig_reb = G.Game._intentional_foul, G.Game._rebound

    def _shot(self, off, de, slot, kind, **kw):
        cur["how"] = "shoot_drive" if kind in G.DRIVE_KINDS else "shoot_other"
        cur["star"] = None
        try:
            # Is the shooter tonight's top-usage player on the floor?
            top = max(range(5), key=lambda s: off.cards[off.on[s]].usage)
            cur["star"] = top == slot
            j = off.defender_of[slot] if kw.get("scr") is None else kw["scr"].def_slot
            dc = de.cards[de.on[j]]
            defended[dc.name] += 1
            if dc.name not in meta:
                meta[dc.name] = {"group": de.groups[de.on[j]], "S45": round(float(dc.flat.get("S45", 50)), 1),
                                 "d_foul": round(dc.d_foul, 3)}
            return orig_shot(self, off, de, slot, kind, **kw)
        finally:
            cur["how"] = "other"
            cur["star"] = None

    def _intentional(self, off, de):
        cur["how"] = "intentional"
        try:
            return orig_int(self, off, de)
        finally:
            cur["how"] = "other"

    def _rebound(self, off, de, miss, shooter):
        prev = cur["how"]
        cur["how"] = "loose_ball"
        try:
            return orig_reb(self, off, de, miss, shooter)
        finally:
            cur["how"] = prev

    def _foul(self, de, slot, *, team_foul=True):
        i = de.on[slot]
        name = de.cards[i].name if hasattr(de.cards[i], "name") else str(de.cards[i].pid)
        how = cur["how"]
        if how.startswith("shoot") and cur.get("star"):
            how += "_vs_star"
        tags[name][how] += 1
        return orig_foul(self, de, slot, team_foul=team_foul)

    G.Game._shot, G.Game._foul, G.Game._intentional_foul, G.Game._rebound = _shot, _foul, _intentional, _rebound
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    if args.limit:
        ids = ids[:: max(1, len(ids) // args.limit)][:args.limit]
    box = {str(g.get("game_id")): g for g in ctx["boxscores"]}
    sim_min, sim_pf = defaultdict(float), defaultdict(float)
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
                if m > 0:
                    sim_min[ln.get("player_name") or ln.get("name")] += m / args.runs
                    sim_pf[ln.get("player_name") or ln.get("name")] += float(ln.get("personal_fouls") or 0) / args.runs
    rows = []
    for name, m in sim_min.items():
        if m < 800 or real_min.get(name, 0) < 800:
            continue
        t = tags.get(name, {})
        n = sum(t.values()) or 1.0
        rows.append({"name": name, "sim_min": round(m), "real_min": round(real_min[name]),
                     "sim_pf36": round(36 * sim_pf[name] / m, 2), "real_pf36": round(36 * real_pf[name] / real_min[name], 2),
                     "defended36": round(36 * defended.get(name, 0.0) / args.runs / m, 2), **meta.get(name, {}),
                     "how": {k: round(v / n, 3) for k, v in sorted(t.items())}})
    rows.sort(key=lambda r: -r["sim_pf36"])
    heavy_sim = [r for r in rows if r["sim_pf36"] >= 4.5]
    heavy_real = [r for r in rows if r["real_pf36"] >= 4.5]
    import statistics as st
    xs, ys = [r["sim_pf36"] for r in rows], [r["real_pf36"] for r in rows]
    mx, my = st.fmean(xs), st.fmean(ys)
    corr = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** .5
    allhow = defaultdict(float)
    for t in tags.values():
        for k, v in t.items():
            allhow[k] += v
    tot = sum(allhow.values())
    out = {"mode": args.mode, "runs": args.runs, "seconds": round(time.time() - t0, 1), "players": len(rows),
           "sim_mean_pf36": round(mx, 3), "real_mean_pf36": round(my, 3), "corr": round(corr, 3),
           "sd_sim": round(st.pstdev(xs), 3), "sd_real": round(st.pstdev(ys), 3),
           "n_sim_4_5": len(heavy_sim), "n_real_4_5": len(heavy_real),
           "league_how": {k: round(v / tot, 4) for k, v in sorted(allhow.items())},
           "all": rows, "top_sim": rows[:25], "top_real": sorted(rows, key=lambda r: -r["real_pf36"])[:15],
           "most_over": sorted(rows, key=lambda r: r["real_pf36"] - r["sim_pf36"])[:15]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"foul_tail_{args.mode}{'_' + args.tag if args.tag else ''}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("all", "top_sim", "top_real", "most_over")}, indent=1))
    for r in rows[:20]:
        print(f"  {r['name']:26s} sim {r['sim_pf36']:.2f} real {r['real_pf36']:.2f}  {r['how']}")
    print("most over real:")
    for r in out["most_over"][:12]:
        print(f"  {r['name']:26s} sim {r['sim_pf36']:.2f} real {r['real_pf36']:.2f}  {r['how']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
