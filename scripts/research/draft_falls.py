"""Seeded draft outcome check (no saves, no trades): how far the consensus top 3 / top 10 fall, how far teams
reach, and the median gap between consensus rank and pick, for the next class (2027, real players; a different
save seed each draft) and a generated class (2030). Compare with real drafts:
data/research/draft_boards/real_board_vs_pick_2015_2025.csv (see docs/agents/tasks/draft-boards.md).

usage: PYTHONPATH=src python scripts/research/draft_falls.py [drafts] [label]
Tuning (outcome checks only, never randomness): DS_<NAME>=value overrides a draft_scouting constant, DG_<NAME>
a draft constant (DG_GM_NEED_WEIGHTS=a,b,c,d for picks 1-5, 6-14, 15-30, 31-60). KINDS=2027,2030 picks classes.
"""
import json
import os
import statistics
import sys
import time
from pathlib import Path

from nba_gm_data import draft as D
from nba_gm_data import draft_scouting as S
from nba_gm_data.app_actions import load_app_canonical

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
LABEL = sys.argv[2] if len(sys.argv) > 2 else "run"
base = load_app_canonical(Path("."))
for key, value in os.environ.items():
    if key.startswith("DS_"):
        setattr(S, key[3:], float(value))
    if key.startswith("DG_"):
        setattr(D, key[3:], tuple(zip((5, 14, 30, 60), map(float, value.split(",")))) if "," in value else float(value))
KINDS = os.environ.get("KINDS", "2027,2030").split(",")


def measure(kind):
    rows = []
    started = time.time()
    for seed in range(1, N + 1):
        if kind == "2027":
            canonical = D.with_draft_context(D.draft_class_for_save(base, seed))
        else:
            canonical = D.with_draft_context(base)
            canonical = {**canonical, "meta": {**canonical["meta"], "draft_class_seed": seed}}
        result = D.simulate_draft(canonical, kind, seed=seed)
        # Consensus at draft time: the June board (median of the 30 teams' final reports).
        ranks = {pid: row["rank"] for pid, row in S.class_scouting(canonical, kind, S.DRAFT_MONTH)["consensus"].items()}
        picks = {s["prospect_id"]: int(s["overall_pick"]) for s in result["selections"]}
        rows += [(seed, rank, picks.get(pid, 61)) for pid, rank in ranks.items()]
    top3 = [r for r in rows if r[1] <= 3]
    top10 = [r for r in rows if r[1] <= 10]
    gap = lambda lo, hi: statistics.median(abs(p - r) for _, r, p in rows if lo <= r <= hi and p <= 60)
    return {
        "kind": kind, "drafts": N, "seconds": round(time.time() - started, 1),
        "no1_taken_first": sum(1 for _, r, p in rows if r == 1 and p == 1),
        "top3_n": len(top3), "top3_past_5": sum(p > 5 for _, _, p in top3), "top3_past_10": sum(p > 10 for _, _, p in top3),
        "top10_n": len(top10), "top10_past_14": sum(p > 14 for _, _, p in top10), "top10_past_20": sum(p > 20 for _, _, p in top10),
        "picks1_5_from_past_14": sum(1 for _, r, p in rows if p <= 5 and r > 14),
        "picks1_10_from_past_20": sum(1 for _, r, p in rows if p <= 10 and r > 20),
        "median_gap_1_3/4_10/11_20/21_30": [gap(1, 3), gap(4, 10), gap(11, 20), gap(21, 30)],
        "worst_top10 (pick, seed, consensus)": sorted(((p, s, r) for s, r, p in top10), reverse=True)[:5],
    }


for kind in KINDS:
    print(LABEL, json.dumps(measure(kind)))
