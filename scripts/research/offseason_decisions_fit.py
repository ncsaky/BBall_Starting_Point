#!/usr/bin/env python3
"""Print leave-one-offseason-out results from the checked-in NBA evidence."""

from __future__ import annotations

import argparse
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
        baseline = mean(training_labels) > .5
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


def salary_comparables(evidence):
    caps = evidence["cap_by_start_year"]
    return [{
        **row,
        "vector": comparable_vector(row),
        "annual_salary_share": row["reported_total"] / row["new_deal_years"] / caps[str(row["summer"])],
    } for row in evidence["salary_comparables"]]


def fit_player_options(evidence):
    rows = evidence["decisions"]["player_options"]
    caps = evidence["cap_by_start_year"]
    comps = salary_comparables(evidence)
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


def fit_team_options(evidence):
    caps = evidence["cap_by_start_year"]
    comps = salary_comparables(evidence)
    rows = evidence["decisions"]["team_options"]
    veterans = [r for r in rows if r["kind"] == "veteran_team" and r["decision"] in ("exercised", "declined")]
    rookies = [r for r in rows if r["kind"].startswith("rookie_year_")]

    def veteran_features(row, held_out):
        _, _, minutes, _, _ = season_features(row)
        return {
            "minutes": minutes,
            "ratio": estimated_salary(row, comps, caps, held_out) / row["option_salary"],
            "flexible": row["non_full_guarantee_at_exercise"],
        }

    veteran_rules = []
    for cutoff in (500, 250, 1000, 1500):
        veteran_rules.append((f"prior minutes >= {cutoff}", lambda f, m=cutoff: f["minutes"] >= m))
    for multiple in (1.0, 0.8, 1.2, 1.5):
        veteran_rules.append((f"expected market >= {multiple:g} × option",
                             lambda f, ratio=multiple: f["ratio"] >= ratio))
        veteran_rules.append((f"expected market >= {multiple:g} × option or option pay can still be cut",
                             lambda f, ratio=multiple: f["ratio"] >= ratio or f["flexible"]))

    def rookie_features(row, _held_out):
        _, _, minutes, vorp, _ = season_features(row)
        return {
            "third_year": row["kind"] == "rookie_year_3",
            "minutes": minutes,
            "vorp": vorp,
            "salary_share": row["option_salary"] / caps[str(row["summer"])],
        }

    rookie_rules = []
    for cutoff in (350, 250, 500, 700, 900, 1000):
        rookie_rules.extend([
            (f"exercise third years; exercise fourth years at {cutoff}+ prior minutes",
             lambda f, m=cutoff: f["third_year"] or f["minutes"] >= m),
            (f"exercise third years; fourth years at {cutoff}+ minutes plus 250 when salary exceeds 4% of cap",
             lambda f, m=cutoff: f["third_year"] or f["minutes"] >= m + 250 * (f["salary_share"] > .04)),
            (f"exercise third years; fourth years at {cutoff}+ prior minutes and a replacement-level box score",
             lambda f, m=cutoff: f["third_year"] or (f["minutes"] >= m and f["vorp"] >= 0)),
        ])

    def exercised(row):
        return row["decision"] == "exercised"

    return {
        "veteran": validation(veterans, veteran_features, exercised, veteran_rules),
        "rookie": validation(rookies, rookie_features, exercised, rookie_rules),
        "rookie_without_waivers": validation(
            [r for r in rookies if not r["waived_at_decision"]], rookie_features, exercised, rookie_rules
        ),
    }


def fit_rookie_extensions(evidence):
    rows = [r for r in evidence["decisions"]["rookie_scale_extensions"]
            if r["decision"] != "waived_before_deadline"]
    rules = []
    for minutes in (1000, 1400, 1800, 2200):
        rules.extend([
            (f"prior minutes >= {minutes}", lambda f, m=minutes: f["minutes"] >= m),
            (f"prior minutes >= {minutes} and above replacement",
             lambda f, m=minutes: f["minutes"] >= m and f["vorp"] > 0),
            (f"prior minutes >= {minutes} and above replacement, or lottery pick with 1000+ minutes",
             lambda f, m=minutes: (f["minutes"] >= m and f["vorp"] > 0)
             or (f["pick"] <= 14 and f["minutes"] >= 1000)),
        ])
    for value in (.5, 1, 1.5):
        rules.append((f"prior value above replacement >= {value:g}", lambda f, v=value: f["vorp"] >= v))

    def features(row, _held_out):
        _, _, minutes, vorp, _ = season_features(row)
        return {"minutes": minutes, "vorp": vorp, "pick": row["draft_pick"] or 31}

    return validation(rows, features, lambda row: row["decision"] == "extended", rules)


def fit_offer_sheets(evidence):
    season_totals = {r["summer"]: r["signed_offer_sheets"] for r in evidence["offer_sheet_seasons"]}
    rows = evidence["decisions"]["offer_sheets"]
    results = {}
    for summer in SUMMERS:
        expected = mean(n for y, n in season_totals.items() if y != summer)
        feasible_in_training = [
            r for r in rows if r["summer"] != summer
            and not r["incumbent_hard_cap_blocks_match_without_other_moves"]
        ]
        match_if_possible = mean(r["matched"] for r in feasible_in_training) >= .5
        test = [r for r in rows if r["summer"] == summer]
        predicted = [
            match_if_possible and not r["incumbent_hard_cap_blocks_match_without_other_moves"]
            for r in test
        ]
        results[summer] = {
            "actual_sheet_count": season_totals[summer],
            "expected_sheet_count": round(expected, 3),
            "count_absolute_error": round(abs(season_totals[summer] - expected), 3),
            "match_if_possible": match_if_possible,
            "matches_correct": sum(p == r["matched"] for p, r in zip(predicted, test)) if test else None,
            "match_decisions": len(test),
        }
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text())
    results = {"player_options": fit_player_options(evidence)}
    if "qualifying_offers" in evidence["decisions"]:
        results["qualifying_offers"] = fit_qualifying_offers(evidence)
    if "team_options" in evidence["decisions"]:
        results["team_options"] = fit_team_options(evidence)
    if "rookie_scale_extensions" in evidence["decisions"]:
        results["rookie_scale_extensions"] = fit_rookie_extensions(evidence)
    if "offer_sheets" in evidence["decisions"]:
        results["offer_sheets"] = fit_offer_sheets(evidence)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
