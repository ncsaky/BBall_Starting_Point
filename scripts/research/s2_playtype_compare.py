#!/usr/bin/env python3
"""Stage 2's actions against real 2025-26 play types (NBA.com / Synergy; data/research/nba_playtypes_2025_26.json).

Reads a breakdown file from s2_usage_breakdown.py (each player's shot tries by kind per 36) and compares per 36 minutes:
transition (trans_rim + trans_three tries) vs real transition possessions; cuts + rolls (rim_finish tries) vs real cut +
roll-man possessions; putbacks vs real putback possessions; post-ups (hook tries) vs real post-ups; self-created
(drives, floaters, pull-ups) vs isolation + pick-and-roll handler + handoff; catch jumpers vs spot-up + off-screen.
Real possessions include free-throw trips and turnovers; Stage 2 tries include shooting-foul trips but not turnovers, so
compare spread and correlation more than level.

    PYTHONPATH=src .venv/bin/python scripts/research/s2_playtype_compare.py output/s2usage/breakdown_base.json
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUPS = {
    "transition": (("trans_rim", "trans_three"), ("transition",)),
    "cut_roll": (("rim_finish",), ("cut", "roll_man")),
    "putback": (("putback",), ("putbacks",)),
    "post": (("hook",), ("post_up",)),
    "self_created": (("rim_drive", "floater", "short_jumper", "mid_pull", "three_pull"), ("isolation", "ball_handler", "handoff")),
    "catch": (("mid_catch", "three_corner", "three_catch"), ("spot_up", "off_screen")),
}


def corr(x, y):
    mx, my = statistics.fmean(x), statistics.fmean(y)
    vx, vy = sum((a - mx) ** 2 for a in x), sum((b - my) ** 2 for b in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy) if vx > 0 and vy > 0 else float("nan")


def compare(path: str, names: list[str] | None = None) -> dict:
    rows = json.loads(Path(path).read_text())["rows"]
    pt = json.loads((ROOT / "data/research/nba_playtypes_2025_26.json").read_text())["players"]
    out, table = {}, {}
    for g, (kinds, types) in GROUPS.items():
        pairs = []
        for pid, r in rows.items():
            p = pt.get(pid)
            k = r["stage2"].get("kinds")
            if not p or not k:
                continue
            real = sum((p["playtypes"].get(t) or {}).get("poss") or 0.0 for t in types) * 36.0 / r["minutes"]
            eng = sum(k[x][0] for x in kinds)
            pairs.append((eng, real, r["minutes"], pid))
            table.setdefault(pid, {"name": r["name"]})[g] = (round(eng, 2), round(real, 2))
        w = sum(p[2] for p in pairs)
        out[g] = {"players": len(pairs), "stage2": round(sum(p[0] * p[2] for p in pairs) / w, 3),
                  "real": round(sum(p[1] * p[2] for p in pairs) / w, 3),
                  "corr": round(corr([p[0] for p in pairs], [p[1] for p in pairs]), 3),
                  "sd_stage2": round(statistics.pstdev([p[0] for p in pairs]), 3),
                  "sd_real": round(statistics.pstdev([p[1] for p in pairs]), 3)}
    if names:
        out["players"] = {v["name"]: {g: v.get(g) for g in GROUPS} for v in table.values()
                          if any(n.lower() in v["name"].lower() for n in names)}
    return out


if __name__ == "__main__":
    names = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    print(json.dumps(compare(sys.argv[1], names), indent=1))
