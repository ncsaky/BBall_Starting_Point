"""Side effect check: one-year expected rating change for every real player in the new ratings, with the new
level-keeping routing (physical capacities, involvement) versus the old split routing.

    PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/prospect_realism_veterans.py
"""
from __future__ import annotations

import statistics as st
from unittest.mock import patch

import prospect_realism as pr
from nba_gm_data import development_outlook as outlook, ratings_model


def old_route(inputs, trait_deltas):
    """The routing before this branch: each trait delta split across its technique-grade inputs."""
    out = {}
    for trait, delta in trait_deltas.items():
        try:
            weights = ratings_model.trait_input_weights(trait)
        except KeyError:
            continue
        movable = {i: w for i, w in weights.items() if ratings_model._is_grade(inputs.get(i))}
        total = sum(movable.values())
        for input_id, weight in movable.items():
            out[input_id] = out.get(input_id, 0.0) + float(delta) * weight / total
    return out


def main() -> None:
    league = pr.load_league("inputs")
    players = [p for p in league["players"] if p.get("team_id") and p.get("age")]
    bands = ((19, 22), (23, 26), (27, 30), (31, 33), (34, 40))
    new = {p["id"]: outlook.expected_overall_change(league, p, start_month="2026-10") for p in players}
    with patch.object(ratings_model, "route_trait_deltas", old_route):
        old = {p["id"]: outlook.expected_overall_change(league, p, start_month="2026-10") for p in players}
    legacy = pr.load_league("legacy")
    by_id = {p["id"]: p for p in legacy["players"]}
    old_ratings = {p["id"]: outlook.expected_overall_change(legacy, by_id[p["id"]], start_month="2026-10") for p in players}
    print("| Age | Players | Legacy ratings | New ratings, old routing | New ratings, new routing |")
    print("| --- | ---: | --- | --- | --- |")
    for low, high in bands:
        ids = [p["id"] for p in players if low <= float(p["age"]) <= high]
        o, n = pr.q([old[i] for i in ids], .1, .5, .9), pr.q([new[i] for i in ids], .1, .5, .9)
        g = pr.q([old_ratings[i] for i in ids], .1, .5, .9)
        print(f"| {low}–{high} | {len(ids)} | {g[1]:+.1f} ({g[0]:+.1f} to {g[2]:+.1f}) | {o[1]:+.1f} ({o[0]:+.1f} to {o[2]:+.1f}) | {n[1]:+.1f} ({n[0]:+.1f} to {n[2]:+.1f}) |")


if __name__ == "__main__":
    main()
