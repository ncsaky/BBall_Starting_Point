"""How big is one development point in each rating set?

For real players (every 4th player by id), apply +1 to every developable hidden rating and measure the change in the
card overall (neutral 24 minutes) in the legacy ratings and in the new 94-input ratings. Also prints how much of a
one-point gain reaches each derived rating in the new ratings. Used to set
ratings_model.GRADE_POINTS_PER_TRAIT_POINT (the new ratings should develop at the size the growth model was tuned
for in legacy units).

    PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/prospect_realism_routing.py
"""
from __future__ import annotations

import copy
import statistics as st

import prospect_realism as pr
from nba_gm_data import health, ratings_model


def main() -> None:
    inputs_league = pr.load_league("inputs")
    legacy_league = pr.load_league("legacy")
    players = sorted((p for p in inputs_league["players"] if p.get("team_id")), key=lambda p: p["id"])[::4]
    traits = health.DEVELOPMENT_TRAITS
    by_age = {"19-23": ([], []), "24-29": ([], []), "30+": ([], [])}
    reach = {t: [] for t in traits}
    model = inputs_league[ratings_model.MODEL_KEY]
    new_sorted = pr.league_thresholds(inputs_league)["overall_sorted"]
    old_sorted = pr.league_thresholds(legacy_league)["overall_sorted"]
    pct = {"new": [], "old": []}

    def pct_gain(table, before, after):
        return 100 * (pr.rank_in_league(table, before) - pr.rank_in_league(table, after)) / len(table)

    legacy_rows = {}
    for t in legacy_league["traits"]:
        legacy_rows.setdefault(t["player_id"], []).append(t)
    for p in players:
        pid = p["id"]
        age = float(p.get("age") or 27)
        bucket = "19-23" if age < 24 else "24-29" if age < 30 else "30+"
        before = {t["trait_key"]: t["value"] for t in inputs_league["traits"] if t["player_id"] == pid}
        c0 = pr.card(inputs_league, pid)["overall"]
        saved = copy.deepcopy(model["input_deltas"])
        ratings_model.apply_development(inputs_league, {pid: {t: 1.0 for t in traits}}, None)
        after = {t["trait_key"]: t["value"] for t in inputs_league["traits"] if t["player_id"] == pid}
        c1 = pr.card(inputs_league, pid)["overall"]
        by_age[bucket][0].append(c1 - c0)
        pct["new"].append(pct_gain(new_sorted, c0, c1))
        for t in traits:
            if t in before and t in after:
                reach[t].append(after[t] - before[t])
        model["input_deltas"] = saved
        ratings_model._rederive(inputs_league, [pid])
        l0 = pr.card(legacy_league, pid)["overall"]
        for row in legacy_rows.get(pid, []):
            if row["trait_key"] in traits:
                row["value"] = float(row["value"]) + 1
        legacy_league.pop("_trait_values_by_player", None)
        l1 = pr.card(legacy_league, pid)["overall"]
        by_age[bucket][1].append(l1 - l0)
        pct["old"].append(pct_gain(old_sorted, l0, l1))
        for row in legacy_rows.get(pid, []):
            if row["trait_key"] in traits:
                row["value"] = float(row["value"]) - 1
        legacy_league.pop("_trait_values_by_player", None)
    print("GRADE_POINTS_PER_TRAIT_POINT =", ratings_model.GRADE_POINTS_PER_TRAIT_POINT)
    for bucket, (new, old) in by_age.items():
        print(f"ages {bucket}: n={len(new)}  card overall per +1 on every rating: new ratings {st.median(new):+.2f}"
              f"  legacy {st.median(old):+.2f}")
    allnew = [x for new, _ in by_age.values() for x in new]
    allold = [x for _, old in by_age.values() for x in old]
    print(f"all: new {st.median(allnew):+.2f} (mean {st.mean(allnew):+.2f})  legacy {st.median(allold):+.2f} (mean {st.mean(allold):+.2f})")
    print(f"league percentile points per +1 on every rating: new {st.mean(pct['new']):+.2f}  legacy {st.mean(pct['old']):+.2f} (means)")
    print("reach of a one-point gain into each derived rating (median):")
    print({t: round(st.median(v), 2) for t, v in reach.items() if v})


if __name__ == "__main__":
    main()
