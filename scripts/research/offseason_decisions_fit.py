#!/usr/bin/env python3
"""Print leave-one-offseason-out results from the checked-in NBA evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from math import log1p
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data/research/offseason_decisions_2023_2026.json"
SUMMERS = (2023, 2024, 2025, 2026)


def balanced_accuracy(actual, predicted):
    rates = [
        mean(p == a for a, p in zip(actual, predicted) if a == label)
        for label in sorted(set(actual))
    ]
    return mean(rates)


def validation(rows, feature, label, rules):
    """Choose rules on the other three summers, then show held-out counts."""
    results = {}
    for summer in SUMMERS:
        training = [r for r in rows if r["summer"] != summer]
        test = [r for r in rows if r["summer"] == summer]
        if not training or not test:
            results[summer] = {"n": len(test), "status": "no held-out rows"}
            continue
        training_labels = [label(r) for r in training]
        test_labels = [label(r) for r in test]
        prepared_train = [feature(r, summer) for r in training]
        prepared_test = [feature(r, summer) for r in test]
        name, rule = max(rules, key=lambda item: balanced_accuracy(
            training_labels, [item[1](r) for r in prepared_train]
        ))
        guesses = [rule(r) for r in prepared_test]
        baseline = Counter(training_labels).most_common(1)[0][0]
        results[summer] = {
            "rule": name,
            "correct": sum(a == p for a, p in zip(test_labels, guesses)),
            "n": len(test),
            "positives": sum(test_labels),
            "predicted_positives": sum(guesses),
            "majority_correct": sum(a == baseline for a in test_labels),
            "balanced_accuracy": round(balanced_accuracy(test_labels, guesses), 3),
        }
    return results


def season_features(row):
    stats = row.get("prior_season_box_value") or {}
    age = row.get("age_on_june_29") or stats.get("season_age") or row.get("tracker_age_snapshot") or 27
    games = stats.get("games", 0)
    return age, games, stats.get("minutes", 0), stats.get("vorp") or 0, stats.get("bpm") or 0


def comparable_vector(row):
    age, games, minutes, vorp, bpm = season_features(row)
    # Shrink a small sample's per-possession box score towards replacement level.
    reliable_bpm = (bpm + 2) * minutes / (minutes + 500) - 2
    return ((age - 27) / 8, games / 82, log1p(minutes / 250), vorp / 2, reliable_bpm / 4)


def estimated_salary(row, comparables, caps, held_out):
    vector = comparable_vector(row)
    ranking = []
    for comp in comparables:
        if comp["summer"] in (held_out, row["summer"]) or comp["player_key"] == row["player_key"]:
            continue
        distance = sum((x - y) ** 2 for x, y in zip(vector, comp["vector"]))
        ranking.append((distance, comp["annual_salary_share"]))
    closest = sorted(ranking)[:9]
    return round(median(share for _, share in closest) * caps[str(row["summer"])])


def fit_player_options(evidence):
    rows = evidence["decisions"]["player_options"]
    caps = evidence["cap_by_start_year"]
    comps = [{
        **row,
        "vector": comparable_vector(row),
        "annual_salary_share": row["reported_total"] / row["new_deal_years"] / caps[str(row["summer"])],
    } for row in evidence["salary_comparables"]]
    rules = []
    for multiplier in (1.0, 0.8, 0.9, 1.1, 1.25, 1.5):
        rules.append((f"expected annual salary >= {multiplier:g} × option",
                      lambda f, ratio=multiplier: f["ratio"] >= ratio))
        rules.append((f"expected annual salary >= {multiplier:g} × option or age 30+ and >= {multiplier*.7:.2f} × option",
                      lambda f, ratio=multiplier: f["ratio"] >= ratio or (f["age"] >= 30 and f["ratio"] >= ratio * .7)))

    def features(row, held_out):
        return {
            "age": season_features(row)[0],
            "ratio": estimated_salary(row, comps, caps, held_out) / row["option_salary"],
        }

    return validation(rows, features, lambda r: r["decision"] == "opted_out", rules)


def fit_qualifying_offers(evidence):
    results = {}
    for contract in ("standard", "two_way"):
        rows = [
            r for r in evidence["decisions"]["qualifying_offers"]
            if r["prior_contract"] == contract and r["eligibility"] == "reported_eligible"
        ]
        rules = []
        for floor in (500, 1000, 1500, 250, 0, 50, 100, 2500):
            rules.append((f"prior minutes >= {floor}", lambda f, m=floor: f["minutes"] >= m))
            if contract == "standard":
                rules.extend([
                    (f"prior minutes >= {floor}; add 350 minutes for offers above 4% of cap",
                     lambda f, m=floor: f["minutes"] >= m + 350 * (f["offer_share"] > .04)),
                    (f"prior minutes >= {floor}; add 350 minutes if prior payroll exceeded 110% of cap",
                     lambda f, m=floor: f["minutes"] >= m + 350 * (f["payroll_share"] > 1.1)),
                    (f"prior minutes >= {floor} or at least 0.7 above replacement",
                     lambda f, m=floor: f["minutes"] >= m or f["vorp"] >= .7),
                ])

        def features(row, _held_out):
            _, _, minutes, vorp, _ = season_features(row)
            cap = evidence["cap_by_start_year"][str(row["summer"])]
            return {
                "minutes": minutes,
                "vorp": vorp,
                "offer_share": (row["qo_amount"] or 0) / cap,
                "payroll_share": (row["prior_team_active_payroll"] or 0) / row["prior_season_cap"],
            }

        results[contract] = validation(rows, features, lambda r: r["tendered"], rules)
        if contract == "two_way":
            # The 2023 non-tenders cannot be distinguished from ineligible players.
            results[contract][2023] = {"status": "held-out eligibility incomplete"}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    results = {"player_options": fit_player_options(evidence)}
    if "qualifying_offers" in evidence["decisions"]:
        results["qualifying_offers"] = fit_qualifying_offers(evidence)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
