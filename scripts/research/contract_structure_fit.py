#!/usr/bin/env python3
"""Fit option decision rules on 2019–2024 and check them on 2025 and 2026."""
import argparse
from collections import Counter
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path
from statistics import median
from typing import Callable

DATA = Path(__file__).resolve().parents[2] / "data/research/contract_structure_evidence.json"
TRAIN = range(2019, 2025)
TEST = (2025, 2026)
MIN_MARKET_COMPARABLES = 9


def features(row):
    age = row.get("age_on_june_29")
    stats = row.get("prior_season_nba_stats") or {}
    length = row.get("prior_team_games") or (72 if row["summer"] in (2020, 2021) else 82)
    games = stats.get("games")
    minutes = stats.get("minutes")
    return {
        "age": age if age is not None else stats.get("season_age"),
        "availability": min(1, games / length) if games is not None else None,
        "minutes_82": minutes * 82 / length if minutes is not None else None,
        "points_per_game": stats.get("points_per_game"),
        "impact": stats.get("pie"),
        "team_win_pct": row.get("prior_team_win_pct"),
        "injury_games": row.get("prior_regular_injury_games"),
        "pick": row.get("draft_pick"),
    }


def market_distance(a, b):
    weights = {"age": 5, "minutes_82": 850, "availability": 0.4,
               "points_per_game": 8, "impact": 0.05}
    deltas = [(a[k] - b[k]) ** 2 / scale ** 2
              for k, scale in weights.items() if a[k] is not None and b[k] is not None]
    return sum(deltas) / len(deltas) if len(deltas) >= 3 else None


def market_estimate(row, target, comps, caps):
    """Training signings only. Exclude the decision year and all the player's deals."""
    candidates = []
    option = row.get("option_salary")
    if not option:
        return None
    for comp, comp_features in comps:
        year = comp["summer"]
        if year == row["summer"] or comp["player_key"] == row["player_key"]:
            continue
        distance = market_distance(target, comp_features)
        if distance is None:
            continue
        price = comp["reported_total"] / comp["new_deal_years"] / caps[year]
        candidates.append((distance, comp["player_key"], year, price))
    if len(candidates) < MIN_MARKET_COMPARABLES:
        return None
    return median(c[-1] for c in sorted(candidates)[:MIN_MARKET_COMPARABLES]) * caps[row["summer"]] / option


def sample(row, comps, caps, positive):
    values = features(row)
    values["market_ratio"] = market_estimate(row, values, comps, caps)
    values["partial"] = row.get("non_full_guarantee_at_exercise", False)
    return row, values, row["decision"] == positive


def counts(actual, predicted):
    pairs = Counter(zip(actual, predicted))
    tp, tn = pairs[True, True], pairs[False, False]
    fp, fn = pairs[False, True], pairs[True, False]
    pos, neg = tp + fn, tn + fp
    return {
        "n": pos + neg, "correct": tp + tn,
        "true_positive": tp, "false_positive": fp,
        "true_negative": tn, "false_negative": fn,
        "balanced_accuracy": (tp / pos + tn / neg) / 2 if pos and neg else None,
    }


@dataclass(frozen=True)
class Rule:
    label: str
    apply: Callable[[dict], bool | None]


def threshold_rule(feature, cutoff, above=True):
    def applies(values):
        val = values[feature]
        if val is None:
            return None
        return val >= cutoff if above else val < cutoff

    op = ">=" if above else "<"
    return Rule(f"{feature} {op} {cutoff:g}", applies)


def context_rules(ratios):
    for key, cutoffs, delta in [
        ("age", (28, 30, 32), (-0.25, 0.25)),
        ("availability", (0.35, 0.65, 0.8), (-0.25, 0.25)),
        ("minutes_82", (500, 1000, 1750), (-0.25, 0.25)),
        ("team_win_pct", (0.4, 0.5, 0.6), (-0.25, 0.25)),
        ("injury_games", (10, 25), (-0.25, 0.25)),
    ]:
        yield f"market plus {key}", [
            market_context_rule(key, cutoff, ratio, amount)
            for cutoff, ratio, amount in product(cutoffs, ratios, delta)
        ]


def market_context_rule(feature, cutoff, ratio, amount):
    def applies(values):
        price, context = values["market_ratio"], values[feature]
        if price is None:
            return None
        return price >= ratio + (amount if context is not None and context >= cutoff else 0)

    label = f"market >= {ratio:g} with {amount:+g} at {feature} >= {cutoff:g}"
    return Rule(label, applies)


def player_rules():
    ratios = (0.6, 0.75, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75)
    yield "market only", [threshold_rule("market_ratio", r) for r in ratios]
    yield from context_rules(ratios)
    yield "production only", [
        threshold_rule("minutes_82", m) for m in (500, 750, 1000, 1500, 2000)
    ]


def team_rules():
    ratios = (0.6, 0.75, 0.9, 1, 1.15, 1.3, 1.5, 1.75, 2, 2.5)
    yield "market only", [threshold_rule("market_ratio", r) for r in ratios]
    yield "market or flexible guarantee", [
        Rule(f"market >= {r:g} or flexible guarantee",
             lambda v, cutoff=r: True if v["partial"] else
             None if v["market_ratio"] is None else v["market_ratio"] >= cutoff)
        for r in ratios
    ]
    yield from context_rules(ratios)
    yield "production only", [
        threshold_rule("minutes_82", m) for m in (250, 500, 750, 1000, 1500)
    ]


def rookie_rules():
    minutes = (250, 500, 750, 1000, 1500)
    yield "production only", [threshold_rule("minutes_82", m) for m in minutes]
    yield "production or draft slot", [
        Rule(f"minutes_82 >= {m} or pick <= {p}",
             lambda v, cut=m, pick=p: True if v["pick"] and v["pick"] <= pick else
             None if v["minutes_82"] is None else v["minutes_82"] >= cut)
        for m, p in product(minutes, (5, 10, 14, 20))
    ]


def scores(rows, rule, fallback):
    called = [rule.apply(values) for _, values, _ in rows]
    actual = [truth for _, _, truth in rows]
    result = counts(actual, [fallback if pred is None else pred for pred in called])
    result["has_inputs"] = sum(p is not None for p in called)
    return result


def fit_rules(rows, comps, caps, families, positive):
    split = {y: [sample(r, comps, caps, positive) for r in rows if r["summer"] == y]
             for y in (*TRAIN, *TEST)}
    train = [r for y in TRAIN for r in split[y]]
    fallback = sum(actual for _, _, actual in train) * 2 >= len(train)
    baseline = Rule("train majority", lambda _: fallback)
    out = {}

    def ranking(rule):
        result = scores(train, rule, fallback)
        return result["balanced_accuracy"] or 0, result["correct"]

    for label, rules in (("baseline", [baseline]), *families):
        best = max(rules, key=ranking)
        out[label] = {"rule": best.label, "train": scores(train, best, fallback),
                      "holdouts": {y: scores(split[y], best, fallback) for y in TEST}}
        if label in {"market only", "production only", "market plus team_win_pct", "production or draft slot"}:
            out[label]["examples"] = [
                {"year": y, "player": r["player"], "prediction": best.apply(vals),
                 "actual": truth, "minutes_82": vals["minutes_82"], "pick": vals["pick"],
                 "market_ratio": round(vals["market_ratio"], 3)
                 if vals["market_ratio"] is not None else None}
                for y in TEST for r, vals, truth in split[y]
            ]
    return out


def analyze(data):
    caps = {int(y): v for y, v in data["cap_by_start_year"].items()}
    comps = [(r, features(r)) for r in data["salary_comparables"]
             if r["summer"] in TRAIN and r["reported_total"] / r["new_deal_years"] >= 0.0075 * caps[r["summer"]]]
    decisions = data["decisions"]
    player = decisions["player_options"]
    teams = decisions["team_options"]
    standard = [r for r in teams if r["kind"] == "veteran_team"]
    rookie_four = [r for r in teams if r["kind"] == "rookie_year_4" and not r.get("waived_at_decision")]
    return {
        "training_years": list(TRAIN), "holdout_years": list(TEST),
        "training_comparables": len(comps),
        "player_opt_out": fit_rules(player, comps, caps, player_rules(), "opted_out"),
        "standard_team_exercise": fit_rules(standard, comps, caps, team_rules(), "exercised"),
        "live_rookie_year_four_exercise": fit_rules(rookie_four, [], caps, rookie_rules(), "exercised"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()
    print(json.dumps(analyze(json.loads(args.data.read_text())), indent=2))


if __name__ == "__main__":
    main()
