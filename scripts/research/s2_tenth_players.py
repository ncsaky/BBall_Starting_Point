#!/usr/bin/env python3
"""S2-TENTH: per-player comparison of Stage 2 settings on replayed 2025-26 games (research only).

Replays every 2025-26 game RUNS times under each setting (s2_usage_fit's apply / replay) and writes, per rotation player
(500+ real minutes), per 36 minutes: points, usage, threes made, assists, rebounds, steals, blocks, and his shot tries
by group (transition, cuts + rolls, putbacks, post-ups) and points from them, next to his real numbers (calibration
targets; NBA.com play types). Prints the players whose points miss moved most between the first two settings.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_tenth_players.py --sets '[{}, {"LOOP.k_trans_speed": .4}]' \
        --runs 4 --out output/s2t/players.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
GROUPS = {"trans": ("trans_rim", "trans_three"), "cutroll": ("rim_finish", "short_finish"), "putback": ("putback",), "post": ("hook",),
          "drive": ("rim_drive", "floater")}
STATS = ("points", "fg3m", "assists", "rebounds", "fga", "fta", "turnovers", "steals", "blocks", "minutes")


def replay(ctx, gids, runs, seed):
    from nba_gm_data.sim import sim_game_with_context
    from nba_gm_data.stage2 import game as G
    G.SHOT_TRACE = {}
    tot = defaultdict(lambda: defaultdict(float))
    for gid in gids:
        for r in range(runs):
            res = sim_game_with_context(ctx, gid, mode="replay-real-minutes", seed=seed + r, engine="stage2")
            for ln in res.player_lines:
                a = tot[ln["player_id"]]
                for k in STATS:
                    a[k] += float(ln.get(k) or 0) / runs
    trace = G.SHOT_TRACE
    G.SHOT_TRACE = None
    return tot, {p: [[v / runs for v in row] for row in rows] for p, rows in trace.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="[{}]")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=3001)
    ap.add_argument("--out", default="output/s2t/players.json")
    ap.add_argument("--min-minutes", type=float, default=500)
    args = ap.parse_args()
    from nba_gm_data.sim import load_sim_context, validation_game_ids
    from nba_gm_data.stage2.cards import KIND_INDEX
    from s2_usage_fit import apply
    ctx = load_sim_context(ROOT)
    box = {str(g["game_id"]) for g in ctx["boxscores"]}
    gids = [g for g in validation_game_ids(ctx, None, False) if g in box]
    targets = json.loads((ROOT / "data/calibration/nba_2025_26_targets.json").read_text())["players"]
    pt = json.loads((ROOT / "data/research/nba_playtypes_2025_26.json").read_text())["players"]
    names = {p["id"]: p["name"] for p in ctx["canonical"].get("players", []) if p.get("id")}
    out = {"sets": json.loads(args.sets), "players": {}}
    for si, setting in enumerate(out["sets"]):
        prev = apply(setting)
        tot, shots = replay(ctx, gids, args.runs, args.seed)
        apply(prev)
        for pid, t in targets.items():
            m = float(t.get("minutes") or 0)
            e = tot.get(pid)
            if m < args.min_minutes or not e or e["minutes"] < min(300, args.min_minutes):
                continue
            f = 36.0 / e["minutes"]
            row = out["players"].setdefault(pid, {"name": names.get(pid, pid), "minutes": m, "real": {
                "points": t["points_per36"], "fg3m": 36.0 * float(t.get("fg3m") or 0) / m, "assists": t["assists_per36"],
                "rebounds": t["rebounds_per36"], "usage": t["fga_per36"] + .44 * t["fta_per36"] + t["turnovers_per36"],
                "steals": t["steals_per36"], "blocks": t["blocks_per36"],
                **{g: sum(((pt.get(pid) or {}).get("playtypes", {}).get(x) or {}).get("poss") or 0.0 for x in xs) * 36.0 / m
                   for g, xs in (("trans", ("transition",)), ("cutroll", ("cut", "roll_man")), ("putback", ("putbacks",)),
                                 ("post", ("post_up",)))}}, "eng": []})
            rec = {k: e[k] * f for k in STATS if k != "minutes"}
            rec["usage"] = rec["fga"] + .44 * rec["fta"] + rec["turnovers"]
            rows = shots.get(pid)
            if rows:
                rec["kinds"] = [round(row[0] * f, 4) for row in rows]
                for g, kinds in GROUPS.items():
                    idx = [KIND_INDEX[k] for k in kinds]
                    rec[g] = sum(rows[i][0] for i in idx) * f
                    rec[g + "_pts"] = sum(rows[i][2] * (3 if KINDS3[i] else 2) + rows[i][4] for i in idx) * f
            row["eng"].append(rec)
        print("set", si, "done", flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out))
    rows = [r for r in out["players"].values() if len(r["eng"]) >= 2]
    if rows:
        moved = sorted(rows, key=lambda r: abs(r["eng"][1]["points"] - r["real"]["points"]) - abs(r["eng"][0]["points"] - r["real"]["points"]))
        print("worse with setting 1 (name, real pts, set0, set1, real usage, use0, use1, trans real/0/1, putback real/0/1):")
        for r in moved[-15:][::-1] + [None] + moved[:10]:
            if r is None:
                print("--- better:")
                continue
            a, b, re = r["eng"][0], r["eng"][1], r["real"]
            print(f"{r['name'][:22]:22s} {re['points']:5.1f} {a['points']:5.1f} {b['points']:5.1f} | use {re['usage']:5.1f} "
                  f"{a['usage']:5.1f} {b['usage']:5.1f} | tr {re['trans']:4.1f} {a.get('trans', 0):4.1f} {b.get('trans', 0):4.1f}"
                  f" | pb {re['putback']:4.1f} {a.get('putback', 0):4.1f} {b.get('putback', 0):4.1f}"
                  f" | cr {re['cutroll']:4.1f} {a.get('cutroll', 0):4.1f} {b.get('cutroll', 0):4.1f}")
    return 0


from nba_gm_data.stage2.cards import KINDS  # noqa: E402
KINDS3 = [k[4] == 3 for k in KINDS]

if __name__ == "__main__":
    raise SystemExit(main())
