#!/usr/bin/env python3
"""Summarize and test the public roster-edge evidence without network access."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean

YEARS = (2023, 2024, 2025, 2026)
DATA = Path(__file__).resolve().parents[2] / "data/research/roster_edge_2023_2026.json"


def count_holdouts(counts):
    """Predict a year's count with the average of the other three years."""
    return {
        year: {
            "observed": counts[year],
            "prediction": round(mean(counts[other] for other in YEARS if other != year), 2),
        }
        for year in YEARS
    }


def sign_and_trades(rows):
    counts = Counter(row["summer"] for row in rows)
    return {
        "signed_players": dict(counts),
        "receiving_teams": {year: len({r["receiver"] for r in rows if r["summer"] == year}) for year in YEARS},
        "receiver_mechanisms": dict(Counter(row["receiver_mechanism"] for row in rows)),
        "count_holdouts": count_holdouts(counts),
    }


def by_year(rows, value):
    return {
        y: dict(Counter(value(row) for row in rows if row["summer"] == y))
        for y in YEARS
    }


def prediction_scores(rows, label, predict):
    actual = [row[label] for row in rows]
    predicted = [predict(row) for row in rows]
    hits = sum(a == p for a, p in zip(actual, predicted))
    per_class = [
        sum(a == p == value for a, p in zip(actual, predicted)) / actual.count(value)
        for value in (False, True) if value in actual
    ]
    return {"correct": hits, "total": len(actual), "positive": actual.count(True),
            "balanced_accuracy": round(mean(per_class), 4) if len(per_class) == 2 else None}


def binary_holdouts(rows, label, rules):
    """Select a simple rule on three summers using balanced accuracy."""
    samples = [row for row in rows if isinstance(row.get(label), bool)]
    result = {}
    for year in YEARS:
        train = [row for row in samples if row["summer"] != year]
        test = [row for row in samples if row["summer"] == year]
        if not test or len({row[label] for row in train}) != 2:
            continue
        name, rule = max(rules, key=lambda item: prediction_scores(train, label, item[1])["balanced_accuracy"])
        majority = sum(row[label] for row in train) > len(train) / 2
        result[year] = {
            "rule": name, **prediction_scores(test, label, rule),
            "majority_baseline": prediction_scores(test, label, lambda _: majority),
        }
    return result


def two_way(decisions):
    snapshots = decisions["two_way_roster_snapshots"]
    signings = decisions["two_way_signings"]
    draft = decisions["two_way_second_round_candidates"]
    return {
        "signings": by_year(signings, lambda r: r["timing"]),
        "draft_status": by_year(signings, lambda r: r["draft_status"]),
        "prior_two_way": by_year(signings, lambda r: str(r["prior_two_way_observed"])),
        "first_round_picks": dict(Counter(r["summer"] for r in signings if 0 < (r["draft_pick"] or 0) < 31)),
        "signing_season_age_coverage": {
            y: sum(r["summer"] == y and r["season_age"] is not None for r in signings) for y in YEARS
        },
        "typical_signing_season_age": {
            y: round(mean(r["season_age"] for r in signings
                          if r["summer"] == y and r["season_age"] is not None), 1) for y in YEARS
        },
        "prior_g_league": {
            y: sum(r["summer"] == y and r["prior_g_league"] is not None for r in signings) for y in YEARS
        },
        "first_trio_date_known": by_year(
            [r for r in snapshots if r["stage"] == "opening" and r["two_way_count"] == 3],
            lambda r: r["date_opening_trio_completed"][:7] if r["date_opening_trio_completed"] else "unknown",
        ),
        "teams_filling_three": by_year([r for r in snapshots if r["two_way_count"] == 3], lambda r: r["stage"]),
        "promotions": by_year(decisions["two_way_promotions"], lambda r: r["timing"]),
        "confirmed_fifty_active_games": by_year(decisions["two_way_fifty_game_confirmations"], lambda _: "confirmed"),
        "second_round_opening_contract_holdout": binary_holdouts(
            draft, "opening_two_way",
            [(f"draft pick ≥ {cutoff}", lambda r, cutoff=cutoff: r["draft_pick"] >= cutoff)
             for cutoff in (40, 43, 46, 49, 52, 55, 58)],
        ),
    }


def validate(data):
    for section, rows in data["decisions"].items():
        for row in rows:
            if row["summer"] not in YEARS or not row["sources"] or set(row["sources"]) - data["sources"].keys():
                raise ValueError(f"Invalid year or citation in {section}: {row}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    validate(data)
    decisions = data["decisions"]
    result = {"sign_and_trades": sign_and_trades(decisions["sign_and_trades"])}
    if "two_way_signings" in decisions:
        result["two_way"] = two_way(decisions)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
