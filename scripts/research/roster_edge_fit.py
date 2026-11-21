#!/usr/bin/env python3
"""Summarize and test the public roster-edge evidence without network access."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
from statistics import mean, median

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
    promotions = decisions["two_way_promotions"]
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
        "promotions": by_year(promotions, lambda r: r["timing"]),
        "promotion_game_log_coverage": by_year(
            [r for r in promotions if r["nba_before_promotion"]], lambda _: "game_log"),
        "promotion_injury_report_coverage": by_year(
            [r for r in promotions if r["injury_snapshot"]], lambda _: "official_report"),
        "opening_two_way_log_checks": by_year(
            decisions["two_way_active_game_checks"], lambda _: "checked"),
        "opening_two_way_log_unresolved": by_year(
            [r for r in decisions["two_way_active_game_checks"] if r["active_games"] > 50],
            lambda _: "over_fifty_in_log"),
        "confirmed_fifty_active_games": by_year(decisions["two_way_fifty_game_confirmations"], lambda _: "confirmed"),
        "second_round_opening_contract_holdout": binary_holdouts(
            draft, "opening_two_way",
            [(f"draft pick ≥ {cutoff}", lambda r, cutoff=cutoff: r["draft_pick"] >= cutoff)
             for cutoff in (40, 43, 46, 49, 52, 55, 58)],
        ),
    }


def exhibit_10(rows, teams):
    per_team = {
        y: dict.fromkeys(teams, 0) | dict(Counter(r["team"] for r in rows if r["summer"] == y))
        for y in YEARS
    }
    return {
        "deals_by_team": per_team,
        "outcomes": by_year(rows, lambda r: r["outcome"]),
        "signees_on_any_opening_roster": {
            y: len({r["player"] for r in rows if r["summer"] == y and r["opening_team"]})
            for y in YEARS
        },
        "same_affiliate_regular_season_appearance": {
            y: (sum(r["summer"] == y and r["affiliate_regular_season"] is not None for r in rows)
                if y < 2026 else None)
            for y in YEARS
        },
        "publicly_verified_bonus_payments": {
            y: sum(r["summer"] == y and r["affiliate_bonus_paid"] is True for r in rows)
            for y in YEARS
        },
        "conversion_holdout": binary_holdouts(
            rows, "converted_before_open",
            [
                ("drafted", lambda r: r["draft_pick"] is not None),
                ("prior NBA appearance", lambda r: r["prior_nba"] is not None),
                ("prior two-way", lambda r: r["prior_two_way_observed"] is True),
                *[(f"prior G League points/game ≥ {points}",
                   lambda r, points=points: ((r["prior_g_league"] or {}).get("ppg") or 0) >= points)
                  for points in (8, 12, 16, 20)],
            ],
        ),
    }


def camp(decisions):
    checkpoints = decisions["camp_team_rosters"]
    players = decisions["camp_checkpoint_players"]
    cuts = decisions["camp_waivers"]
    return {
        "counts_by_team": {
            y: {r["team"]: r["reconstructed_camp_count"] for r in checkpoints if r["summer"] == y}
            for y in YEARS
        },
        "median_camp_players": {
            y: median(r["reconstructed_camp_count"] for r in checkpoints if r["summer"] == y)
            for y in YEARS
        },
        "teams_starting_with_21": by_year([r for r in checkpoints if r["reconstructed_camp_count"] == 21],
                                         lambda _: "teams"),
        "opening_standard_slots": by_year(checkpoints, lambda r: r["opening_standard"]),
        "waivers": by_year(cuts, lambda r: r["contract_type_at_cut"] or "other_or_unknown"),
        "claims": by_year(decisions["camp_waiver_claims"], lambda _: "claims"),
        "retention_holdout": binary_holdouts(
            players, "retained_by_opening",
            [
                ("keep unless Exhibit 10", lambda r: not r["signed_as_exhibit_10_at_checkpoint"]),
                ("keep contracted two-ways or players with an earlier NBA appearance",
                 lambda r: r["signed_as_two_way_before_checkpoint"] or r["prior_nba"] is not None),
                ("keep recent first-rounders and players with earlier NBA minutes",
                 lambda r: r["guarantee_at_checkpoint"] == "rookie_scale_first_two_years"
                 or ((r["prior_nba"] or {}).get("mpg") or 0) >= 10),
                ("keep a drafted player unless on Exhibit 10",
                 lambda r: r["draft_pick"] is not None and not r["signed_as_exhibit_10_at_checkpoint"]),
            ],
        ),
    }


def first_player_moves(rows):
    first = {}
    for row in sorted(rows, key=lambda r: r["date"]):
        first.setdefault((row["summer"], row["player"]), row)
    return first


def late_market(decisions):
    nba = decisions["veteran_summer_nba_signings"]
    overseas = decisions["veteran_overseas_signings"]
    standard = first_player_moves(r for r in nba if r["contract_group"] == "standard_reported")
    late = {key: row for key, row in standard.items() if row["late"]}
    overseas_people = first_player_moves(overseas)
    recent_nba = {
        key: dict(row, signed_overseas=False) for key, row in late.items()
        if row["prior_nba_season"] == row["summer"]
    }
    recent_overseas = {
        key: dict(row, signed_overseas=True) for key, row in overseas_people.items()
        if row["previous_nba_season_appearance"]
    }
    timing_rules = [
        *[(f"age ≥ {age}", lambda r, age=age: r["season_age"] >= age) for age in (26, 29, 32, 35)],
        *[(f"prior NBA minutes/game < {minutes}",
           lambda r, minutes=minutes: (r["last_nba_profile"]["mpg"] or 0) < minutes)
          for minutes in (8, 14, 20, 24)],
        ("prior NBA season outside regular rotation",
         lambda r: r["prior_role"] in ("limited_minutes", "no_nba_appearance")),
    ]
    return {
        "standard_signers": by_year(standard.values(), lambda r: "after_august_1" if r["late"] else "through_august_1"),
        "late_standard_signers_from_camp": by_year(
            [r for r in late.values() if r["at_or_after_camp"]], lambda _: "signers"),
        "known_camp_deals_after_august_1": by_year(
            [r for r in nba if r["late"] and r["contract_group"] != "standard_reported"],
            lambda r: r["contract_group"]),
        "late_standard_prior_roles": by_year(late.values(), lambda r: r["prior_role"]),
        "late_standard_median_age": {
            y: median(r["season_age"] for r in late.values() if r["summer"] == y) for y in YEARS
        },
        "overseas_prior_roles": by_year(overseas_people.values(), lambda r: r["prior_role"]),
        "overseas_median_age": {
            y: median(r["season_age"] for r in overseas_people.values() if r["summer"] == y) for y in YEARS
        },
        "late_vs_early_standard_holdout": binary_holdouts(list(standard.values()), "late", timing_rules),
        "overseas_vs_late_standard_holdout": binary_holdouts(
            list((recent_nba | recent_overseas).values()), "signed_overseas", timing_rules),
    }


def validate(data):
    for source in data["sources"].values():
        date.fromisoformat(source["date"])
        if not source["url"].startswith(("https://", "http://")):
            raise ValueError(f"Invalid source URL: {source}")
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
    teams = sorted({r["team"] for r in decisions["two_way_roster_snapshots"]})
    result = {
        "two_way": two_way(decisions),
        "exhibit_10": exhibit_10(decisions["exhibit_10_deals"], teams),
        "camp": camp(decisions),
        "sign_and_trades": sign_and_trades(decisions["sign_and_trades"]),
        "late_market": late_market(decisions),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
