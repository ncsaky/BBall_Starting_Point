#!/usr/bin/env python3
"""Compare the game's overall / offense / defense with a multi-metric consensus of real impact (ratings audit).

Consensus (Basketball Index Leaderboards "Values", local-only data): for each season 2023-24..2025-26 and each impact
metric, a z-score among that season's 500+ minute players; metrics: LEBRON, DPM, DRIP, RAPTOR, luck-adjusted RAPM and
time-decay luck-adjusted RAPM (offense and defense halves separately). The metrics' z-scores are averaged per season,
then seasons are blended with weights 1.0 / 0.6 / 0.35 times minutes (the same recency weights as bbi_evidence).
Overall = offense + defense consensus (each re-standardized among the compared players).

Game values: save.player_attribute_summary (the card's OVR / OFF / DEF) under the legacy ratings and the new
(inputs) ratings. The game's summary scale is rank-mapped (only order carries meaning), so a disagreement is measured
in league-percentile points among the compared players: game percentile minus consensus percentile (+ = the game
rates him higher than the evidence).

The consensus is a diagnostic only: nothing is tuned toward it (ratings-first rule).
Writes output/ratings-audit/consensus_vs_game.json and prints the biggest disagreements.

    PYTHONPATH=src .venv/bin/python scripts/research/consensus_impact_audit.py [--top 30] [--min-minutes 1000]
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.bbi_evidence import SEASON_WEIGHTS, collect_values  # noqa: E402
from nba_gm_data.ratings_model import install_inputs_model  # noqa: E402
from nba_gm_data.save import player_attribute_summary, trait_values_by_player  # noqa: E402

PAIRS = {
    "LEBRON": ("O-LEBRON", "D-LEBRON"),
    "DPM": ("O-DPM", "D-DPM"),
    "DRIP": ("O-DRIP", "D-DRIP"),
    "RAPTOR": ("Offensive RAPTOR", "Defensive RAPTOR"),
    "LA-RAPM": ("Luck-Adjusted ORAPM", "Luck-Adjusted DRAPM"),
    "TD LA-RAPM": ("Time Decay LA-ORAPM", "Time Decay LA-DRAPM"),
}
BOX_FAMILY = ("LEBRON", "DPM", "DRIP", "RAPTOR")      # box-score / tracking informed (with on/off priors)
RAPM_FAMILY = ("LA-RAPM", "TD LA-RAPM")               # on/off regression only
POOL_MINUTES = 500
OUT = ROOT / "output/ratings-audit/consensus_vs_game.json"


def season_z(table, metric, season):
    rows = table.get((season, metric)) or {}
    pool = [v for v, m, _ in rows.values() if m >= POOL_MINUTES]
    if len(pool) < 30:
        return {}, {}
    mu, sd = statistics.fmean(pool), statistics.pstdev(pool) or 1.0
    return ({cid: (v - mu) / sd for v, m, cid in rows.values() if cid},
            {cid: m for v, m, cid in rows.values() if cid})


def consensus(root=ROOT):
    metrics = {m for pair in PAIRS.values() for m in pair}
    table = collect_values(root, metrics)
    out = {}
    detail = {}
    for side, index in (("offense", 0), ("defense", 1)):
        acc = {}
        for season, sw in SEASON_WEIGHTS.items():
            per_metric = {}
            minutes = {}
            for name, pair in PAIRS.items():
                z, mins = season_z(table, pair[index], season)
                per_metric[name] = z
                for cid, m in mins.items():
                    minutes[cid] = max(minutes.get(cid, 0.0), m)
            for cid, m in minutes.items():
                values = [per_metric[name][cid] for name in PAIRS if cid in per_metric[name]]
                if len(values) < 3 or m <= 0:
                    continue
                a = acc.setdefault(cid, [0.0, 0.0, 0.0])
                a[0] += sw * m * statistics.fmean(values)
                a[1] += sw * m
                if season == "2025-26":
                    a[2] = m
                d = detail.setdefault(cid, {}).setdefault(side, {})
                for name in PAIRS:
                    if cid in per_metric[name]:
                        x = d.setdefault(name, [0.0, 0.0])
                        x[0] += sw * m * per_metric[name][cid]
                        x[1] += sw * m
        out[side] = {cid: (a[0] / a[1], a[2]) for cid, a in acc.items()}
    detail = {cid: {side: {k: round(v[0] / v[1], 2) for k, v in d.items()} for side, d in sides.items()}
              for cid, sides in detail.items()}
    return out, detail


def percentiles(values):
    order = sorted(values, key=lambda k: values[k])
    n = len(order)
    return {k: 100.0 * (i + 0.5) / n for i, k in enumerate(order)}


def zscores(values):
    mu, sd = statistics.fmean(values.values()), statistics.pstdev(values.values()) or 1.0
    return {k: (v - mu) / sd for k, v in values.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--min-minutes", type=float, default=1000.0)
    ap.add_argument("--by-legacy", action="store_true", help="sort the printed list by the legacy ratings' gap")
    args = ap.parse_args()
    cons, detail = consensus()
    base = load_app_canonical(ROOT)
    legacy = copy.deepcopy(base)
    install_inputs_model(base, ROOT)
    games = {"legacy": legacy, "new": base}
    players = {p["id"]: p for p in base["players"] if p.get("team_id")}
    ids = [pid for pid in players if pid in cons["offense"] and pid in cons["defense"]
           and cons["offense"][pid][1] >= args.min_minutes]
    z_off = zscores({pid: cons["offense"][pid][0] for pid in ids})
    z_def = zscores({pid: cons["defense"][pid][0] for pid in ids})
    c_off, c_def = percentiles(z_off), percentiles(z_def)
    c_all = percentiles({pid: z_off[pid] + z_def[pid] for pid in ids})
    game = {}
    for label, canonical in games.items():
        summ = {pid: player_attribute_summary(canonical, pid) for pid in ids}
        game[label] = {key: percentiles({pid: float(summ[pid].get(key) or 0.0) for pid in ids}) for key in ("overall", "offense", "defense")}
        game[label]["raw"] = summ
    traits = {label: trait_values_by_player(canonical) for label, canonical in games.items()}
    rank = lambda d: {pid: i + 1 for i, pid in enumerate(sorted(d, key=lambda k: -d[k]))}
    c_rank = rank(c_all)
    # Split view for diagnosis: box-score-informed metrics vs pure on/off regression (RAPM), overall = O + D.
    def family(names):
        out = {}
        for pid in ids:
            sides = detail.get(pid) or {}
            vals = [statistics.fmean([sides[s][n] for n in names if n in sides.get(s, {})] or [0.0]) for s in ("offense", "defense")]
            out[pid] = sum(vals)
        return rank(out)
    box_rank, rapm_rank = family(BOX_FAMILY), family(RAPM_FAMILY)
    rows = []
    for pid in ids:
        row = {"id": pid, "name": players[pid]["name"], "minutes_2025_26": round(cons["offense"][pid][1]),
               "consensus": {"overall": round(c_all[pid], 1), "offense": round(c_off[pid], 1), "defense": round(c_def[pid], 1),
                             "z": {"offense": round(z_off[pid], 2), "defense": round(z_def[pid], 2)},
                             "rank": c_rank[pid], "box_rank": box_rank[pid], "rapm_rank": rapm_rank[pid], "metrics": detail.get(pid)}}
        for label in games:
            g = game[label]
            r = rank(g["overall"])
            row[label] = {"overall": round(g["overall"][pid], 1), "offense": round(g["offense"][pid], 1),
                          "defense": round(g["defense"][pid], 1), "rank": r[pid],
                          "card": {k: game[label]["raw"][pid].get(k) for k in ("overall", "offense", "defense")},
                          "traits": {k: round(v, 1) for k, v in traits[label].get(pid, {}).items()},
                          "gap": {k: round(g[k][pid] - {"overall": c_all, "offense": c_off, "defense": c_def}[k][pid], 1)
                                  for k in ("overall", "offense", "defense")}}
        rows.append(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"players": rows, "pairs": PAIRS, "min_minutes": args.min_minutes}, indent=1, default=str))
    print(f"{len(rows)} players with {args.min_minutes:.0f}+ minutes in 2025-26 and a consensus; wrote {OUT.relative_to(ROOT)}")
    for label in games:
        corr = statistics.correlation([game[label]["overall"][p] for p in ids], [c_all[p] for p in ids])
        corr_o = statistics.correlation([game[label]["offense"][p] for p in ids], [c_off[p] for p in ids])
        corr_d = statistics.correlation([game[label]["defense"][p] for p in ids], [c_def[p] for p in ids])
        mad = statistics.fmean(abs(game[label]["overall"][p] - c_all[p]) for p in ids)
        print(f"{label:6} ratings vs consensus (rank correlation): overall {corr:.3f}, offense {corr_o:.3f}, defense {corr_d:.3f}; "
              f"mean absolute overall gap {mad:.1f} percentile points")
    sort_by = "legacy" if "--by-legacy" in sys.argv else "new"
    key = lambda r: -abs(r[sort_by]["gap"]["overall"])
    print(f"\nsorted by the {sort_by} ratings' overall gap (percentile points; + = game rates him higher than the evidence)")
    print(f"{'player':24} {'min':>5} {'cons#':>5} {'box#':>5} {'rapm#':>5} {'new#':>5} {'leg#':>5} | gap new O/D/OVR | gap legacy O/D/OVR")
    for r in sorted(rows, key=key)[: args.top]:
        gn, gl = r["new"]["gap"], r["legacy"]["gap"]
        print(f"{r['name'][:24]:24} {r['minutes_2025_26']:5d} {r['consensus']['rank']:5d} {r['consensus']['box_rank']:5d} {r['consensus']['rapm_rank']:5d} {r['new']['rank']:5d} {r['legacy']['rank']:5d} | "
              f"{gn['offense']:+6.1f} {gn['defense']:+6.1f} {gn['overall']:+6.1f} | {gl['offense']:+6.1f} {gl['defense']:+6.1f} {gl['overall']:+6.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
