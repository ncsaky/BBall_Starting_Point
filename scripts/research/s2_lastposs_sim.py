#!/usr/bin/env python3
"""Stage 2 last possessions, row for row like s2_lastposs_pbp.py (S2-LAST-POSSESSION).

Replays (or generates) 2025-26 games and writes one row per possession that starts with 300 seconds or less left in the
4th quarter or an overtime (the real file's columns), plus the end-of-quarter shots of the 1st-3rd quarters and each
game's regulation margin. `s2_lastposs_compare.py` compares it with the real file.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_lastposs_sim.py --runs 8 --out output/s2last/sim_base.json \
        [--limit 600] [loop.KEY=V ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def measure(ctx, ids, runs: int, seed: int, mode: str):
    from nba_gm_data.sim import sim_game_with_context
    from nba_gm_data.stage2 import game as G
    cur: dict = {}
    poss, heaves, games = [], [], []
    orig_poss, orig_int, orig_shot = G.Game.possession, G.Game._intentional_foul, G.Game._shot

    def tally(team):
        s = [0] * 7
        for st in team.stats:
            s[0] += st[G.S_FGA]; s[1] += st[G.S_FGM]; s[2] += st[G.S_3PA]; s[3] += st[G.S_3PM]
            s[4] += st[G.S_FTA]; s[5] += st[G.S_FTM]; s[6] += st[G.S_TOV]
        return s

    def intentional(self, off, de):
        cur["take"] = cur.get("take", 0) + 1
        return orig_int(self, off, de)

    def shot(self, off, de, slot, kind, **kw):
        if self.period <= 3 and self.t_left <= 3.0 and kw.get("final"):
            before = off.stats[off.on[slot]][G.S_FGM]
            fga0 = off.stats[off.on[slot]][G.S_FGA]
            res = orig_shot(self, off, de, slot, kind, **kw)
            if off.stats[off.on[slot]][G.S_FGA] > fga0:
                heaves.append((self.period, round(self.t_left, 1), G.KINDS[kind][0],
                               int(off.stats[off.on[slot]][G.S_FGM] > before), int(G.KPTS[kind] == 3)))
            return res
        return orig_shot(self, off, de, slot, kind, **kw)

    def possession(self, off, de, start):
        cur["game"] = self
        if self.period < 4 or self.t_left > 300.0:
            res = orig_poss(self, off, de, start)
        else:
            t, m, p0 = self.t_left, off.points - de.points, off.points
            b = tally(off)
            sf0 = sum(self.diag[3 * k + 2] for k in range(G.N_KINDS))
            cur["take"] = 0
            res = orig_poss(self, off, de, start)
            a = tally(off)
            sf = sum(self.diag[3 * k + 2] for k in range(G.N_KINDS)) - sf0
            row = [self.period, round(t, 1), m, round(t - max(0.0, self.t_left), 1), off.points - p0,
                   *[x - y for x, y in zip(a, b)], cur["take"], sf, off is self.home]
            cur.setdefault("rows", []).append(row)
        if self.period >= 4 and (res == "end" or self.t_left <= 0.0):
            cur.setdefault("ends", {})[self.period] = self.home.points - self.away.points
        return res

    G.Game.possession, G.Game._intentional_foul, G.Game._shot = possession, intentional, shot
    t0 = time.time()
    try:
        for gi, gid in enumerate(ids):
            for r in range(runs):
                cur.clear()
                sim_game_with_context(ctx, gid, mode=mode, seed=seed + r, engine="stage2")
                g = cur.get("game")
                if g is None:
                    continue
                ends = cur.get("ends", {})
                key = f"{gid}#{r}"
                for row in cur.get("rows", []):
                    per, home_off = row[0], row[-1]
                    e = ends.get(per, 0)
                    reg = e if home_off else -e
                    poss.append((2026, key, per, *row[1:-1], reg))
                games.append((key, ends.get(4, 0), g.home.points - g.away.points, g.period))
    finally:
        G.Game.possession, G.Game._intentional_foul, G.Game._shot = orig_poss, orig_int, orig_shot
    return poss, heaves, games, time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--mode", default="replay-real-minutes")
    ap.add_argument("--out", required=True)
    args, rest = ap.parse_known_args()
    from nba_gm_data.stage2 import coach as C, game as G, screens as S
    applied = {}
    for a in rest:
        key, value = a.split("=", 1)
        table, name = key.split(".", 1)
        {"loop": G.LOOP, "coach": C.COACH, "screens": S.SCREENS}[table][name] = float(value)
        applied[key] = float(value)
    from nba_gm_data.sim import load_sim_context, validation_game_ids
    ctx = load_sim_context(ROOT)
    ids = validation_game_ids(ctx, None, False)
    if args.limit:
        ids = ids[:: max(1, len(ids) // args.limit)][:args.limit]
    poss, heaves, games, secs = measure(ctx, ids, args.runs, args.seed, args.mode)
    cols = ["season", "game", "period", "t", "m", "secs", "pts", "fga", "fgm", "f3a", "f3m", "fta", "ftm", "tov",
            "take", "sfoul", "reg"]
    out = {"overrides": applied, "runs": args.runs, "mode": args.mode, "seconds": round(secs, 1), "cols": cols,
           "poss": poss, "heave_cols": ["period", "t", "kind", "made", "three"], "heaves": heaves,
           "games": {g[0]: [2026, g[1], g[2], g[3]] for g in games}}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(games)} games, {len(poss)} late possessions, {len(heaves)} end-of-quarter shots, {secs:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
