#!/usr/bin/env python3
"""Sanity read of real college prospects in the game: does a college shooter come out a shooter, a shot-blocker a
rim protector, a high-usage creator a creator?

    PYTHONPATH=src .venv/bin/python scripts/research/real_prospects_check.py [--year 2027] [--seed 2027] [--top 15]

Builds the class as a new save would (94-input ratings, talent model), signs every prospect as if drafted at his
board slot, and prints the entry 94-input skills next to the college numbers they should reflect, plus the
correlation across all real prospects in the class (college rate vs entry skill).
"""
from __future__ import annotations

import argparse
import statistics
from types import SimpleNamespace

from nba_gm_data import draft
from nba_gm_data.input_estimator import _generated_player_inputs, scalar_value
from nba_gm_data.schema import to_plain

CHECKS = (  # (college rate in projected_profile, entry input(s), label)
    ("ft_pct", ("S07",), "free throws"),
    ("three_pct", ("S01", "S03"), "three-point shooting"),
    ("blk_pct", ("S37", "S36"), "rim protection"),
    ("usg", ("S16", "S18", "S19"), "shot creation"),
    ("ast_pct", tuple(f"F0{i}.{p}" for i in range(1, 10) for p in ("recognition", "execution")), "passing"),
    ("tov_pct", ("S17",), "ball security (college turnovers: expect negative)"),
    ("orb_pct", ("S29",), "offensive rebounding"),
    ("drb_pct", ("S30", "S31"), "defensive rebounding"),
    ("stl_pct", ("S42", "S43"), "steals / hands"),
    ("ftr", ("S24",), "foul drawing"),
)


def entry_inputs(year: str, seed: int):
    cls = to_plain(draft.generate_draft_class_records(year, seed, talent_model=True, real_prospects=True))
    traits = {}
    for row in cls["draft_prospect_traits"]:
        traits.setdefault(row["prospect_id"], []).append(row)
    out = []
    for prospect in sorted(cls["draft_prospects"], key=lambda p: p["rank"]):
        onboarding = {"draft_year": year, "name": prospect["name"], "overall_pick": prospect["rank"]}
        player = draft.rookie_player_record(onboarding, prospect, {"id": "team_check", "abbrev": "CHK"}, SimpleNamespace(id="c"))
        nba = {t["trait_key"]: t["value"] for t in draft.rookie_trait_records(player, prospect, traits[prospect["id"]])}
        inputs = _generated_player_inputs(player, nba).to_dict()["inputs"]
        out.append((prospect, {iid: scalar_value(rec) for iid, rec in inputs.items()}))
    return out


def coverage(seeds: int) -> None:
    """How many real players each class holds across save seeds (top 10 / 30 / 60 of the public board)."""
    from nba_gm_data import real_prospects as rp
    print(f"Coverage across seeds 1-{seeds} (median, min-max):")
    for year in sorted(rp.draft_years()):
        counts = {10: [], 30: [], 60: []}
        kinds = []
        for seed in range(1, seeds + 1):
            cls = to_plain(draft.generate_draft_class_records(year, seed, talent_model=True, real_prospects=True))
            real = [p for p in cls["draft_prospects"] if p["league"] != "generated"]
            for n in counts:
                counts[n].append(sum(1 for p in real if p["rank"] <= n))
            kinds.append(len(real))
        print(f"  {year}: " + ", ".join(f"top {n}: {statistics.median(v):.0f} ({min(v)}-{max(v)})" for n, v in counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default="2027")
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--coverage", type=int, default=0, help="summarize real players per class across this many seeds")
    args = parser.parse_args()
    if args.coverage:
        coverage(args.coverage)
        return
    rows = entry_inputs(args.year, args.seed)
    real = [(p, v) for p, v in rows if (p.get("public_stats") or {}).get("college")]
    gen = [(p, v) for p, v in rows if p["league"] == "generated"]
    others = [(p, v) for p, v in rows if p["league"] != "generated" and (p, v) not in real]
    print(f"{args.year} class (seed {args.seed}): {len(real)} real college, {len(others)} real high-school / international /"
          f" no-stats, {len(gen)} generated\n")
    print("Board (rank, name, where, age, now / public upside, scouting rank)")
    for prospect, _ in rows[: args.top]:
        scouting = (prospect.get("public_stats") or {}).get("scouting") or {}
        rank = (f"consensus #{scouting['consensus_rank']}" if scouting.get("consensus_rank") else
                f"247 #{min(scouting['recruit_ranks'].values())}" if scouting.get("recruit_ranks") else "")
        print(f"  #{prospect['rank']:>2} {prospect['name'][:24]:<24} {prospect['league'][:13]:<13} {str(prospect.get('source_team'))[:20]:<20}"
              f" age {prospect['age']} | now {prospect['current_ability']:.0f} pot "
              f"{(prospect.get('scouting_prior') or {}).get('potential', prospect['potential']):.0f} | {rank}")
    print()
    print("Real top of the board (entry 94-input grades; college numbers from the projected final season)")
    for prospect, v in real[: args.top]:
        college = prospect["public_stats"]["college"]
        prof = college["profile"]
        f_mean = statistics.fmean(v[i] for i in v if i.startswith("F0"))
        print(f"  #{prospect['rank']:>2} {prospect['name'][:22]:<22} {prospect['position']:<6} {college['team'][:13]:<13} age {prospect['age']}"
              f" | now {prospect['current_ability']:.0f} pot {(prospect.get('scouting_prior') or {}).get('potential', prospect['potential']):.0f}"
              f" | FT {prof['ft_pct']:.2f}->{v['S07']:.0f}  3P {prof['three_pct']:.3f}->{v['S01']:.0f}"
              f"  usg {prof['usg']:.0f}->{statistics.fmean(v[i] for i in ('S16','S18','S19')):.0f}"
              f"  ast {prof['ast_pct']:.0f}->{f_mean:.0f}  blk {prof['blk_pct']:.1f}->{v['S37']:.0f}"
              f"  orb {prof['orb_pct']:.1f}->{v['S29']:.0f}  stl {prof['stl_pct']:.1f}->{v['S42']:.0f}")
    print("\nDirection across all real prospects in the class (correlation of college rate with entry skill):")
    for key, ids, label in CHECKS:
        xs = [p["public_stats"]["college"]["profile"].get(key) for p, _ in real]
        ys = [statistics.fmean(v[i] for i in ids) for _, v in real]
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None]
        r = statistics.correlation([x for x, _ in pairs], [y for _, y in pairs]) if len(pairs) > 3 else float("nan")
        print(f"  {label:<48} r = {r:+.2f}")
    for label, group in (("real", real), ("generated", gen)):
        means = {k: statistics.fmean(statistics.fmean(v[i] for i in ids) for _, v in group) for _, ids, k in CHECKS[:5]}
        print(f"  mean entry grades, {label}: " + ", ".join(f"{k} {m:.1f}" for k, m in means.items()))


if __name__ == "__main__":
    main()
