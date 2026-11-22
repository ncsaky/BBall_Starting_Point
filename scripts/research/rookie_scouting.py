#!/usr/bin/env python3
"""ROOKIE-FIT-2: store the 2026 class's public scouting evidence with attribution.

Input: a JSON gathered from public pages on 2026-11-22 (pre-draft big boards, readiness write-ups, early-season rookie
ladders; see `about` in the output). Output: data/research/rookie_scouting_2026.json with each player's consensus
board rank (geometric mean over the pre-draft boards that list him).

    python3 scripts/research/rookie_scouting.py <gathered.json>
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/research/rookie_scouting_2026.json"


def main() -> None:
    d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for b in d["boards"]:
        b["ranks"] = {k: v for k, v in b["ranks"].items() if v is not None}
    pre = [b for b in d["boards"] if b["kind"] in ("big_board", "consensus_board")]
    consensus = {}
    for name in sorted(d["readiness"]):
        ranks = [b["ranks"][name] for b in pre if name in b["ranks"]]
        if ranks:
            consensus[name] = {"boards": len(ranks), "best": min(ranks), "worst": max(ranks),
                               "geometric_mean_rank": round(math.exp(sum(map(math.log, ranks)) / len(ranks)), 2)}
    out = {
        "version": 1, "retrieved": d["retrieved"],
        "about": ("Public pre-draft big boards, readiness write-ups and early-season rookie ladders for the 2026 "
                  "draft class, gathered 2026-11-22 from the linked public pages (no paywalled content; The Athletic's "
                  "top 10 via a Bleacher Report summary). Ranks are as published. Readiness tiers (ready_now / "
                  "some_readiness / project / unknown) and reasons are short paraphrases of the linked write-ups made "
                  "for this file, not quotes. Spot-checked against ESPN (Woo, 2026-06-23) and the NBA.com Kia Rookie "
                  "Ladder of 2026-11-18."),
        "uses": ("consensus: geometric mean of a player's rank on the pre-draft boards that list him; "
                 "scripts/research/rookie_fit2.py averages it with his draft slot (log scale) as the scouts' view. "
                 "readiness tier: a small labelled nudge to day-one ability. Ladders and readiness lists: checks only."),
        "boards": d["boards"], "consensus": consensus, "readiness": d["readiness"],
        "skipped_sources": d.get("skipped_sources", []),
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    for name in sorted(consensus, key=lambda n: consensus[n]["geometric_mean_rank"]):
        print(f"{name:24s} {consensus[name]}  {d['readiness'][name]['tier']}")


if __name__ == "__main__":
    main()
