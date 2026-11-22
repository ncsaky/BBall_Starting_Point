#!/usr/bin/env python3
"""Fit staff turnover from the dated observations in the evidence JSON.

Season numbers are end years. The trailing offseason belongs to the season
that just ended. This script uses only the standard library and no network.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data/research/staff_turnover_evidence.json"
FIRST, LAST_FIT, LAST = 2010, 2022, 2026
TEAMS = 30
PRIOR_CASES = 12


def person_key(name):
    """Ignore accents and punctuation in names across the source guides."""
    normal = unicodedata.normalize("NFKD", name.casefold())
    return "".join(c for c in normal if c.isascii() and c.isalnum())


def rate(events, cases):
    return round(events / cases, 6) if cases else None


def bin_rate(values):
    return {"events": sum(values), "cases": len(values), "rate": rate(sum(values), len(values))}


def histogram(values):
    return dict(sorted(Counter(values).items()))


def tenure_band(games):
    seasons = games / 82
    if seasons < 1.5:
        return "under_1.5_seasons"
    if seasons < 3.5:
        return "1.5_to_under_3.5_seasons"
    return "3.5_plus_seasons"


def win_band(wins_vs_expected):
    if wins_vs_expected < -8:
        return "below_minus_8"
    if wins_vs_expected < -3:
        return "minus_8_to_below_minus_3"
    if wins_vs_expected <= 3:
        return "minus_3_to_plus_3"
    return "above_plus_3"


def record_band(win_pct):
    if win_pct < 0.35:
        return "below_350"
    if win_pct < 0.5:
        return "350_to_below_500"
    return "500_plus"


def playoff_band(row):
    if not row["playoff_losses"] and not row["playoff_wins"]:
        return "missed_playoffs"
    if row["playoff_wins"] < 4:
        return "first_round"
    return "won_series"


def binary_checks(cases, outcome, rule_columns):
    """Fit league and smoothed group rates. Score each rule on the same held-out rows."""
    train = [row for row in cases if row["season"] <= LAST_FIT]
    test = [row for row in cases if row["season"] > LAST_FIT]
    checks = {}
    base_rate = mean(row[outcome] for row in train)
    for name, columns in (("league_rate", ()), *rule_columns.items()):
        groups = defaultdict(list)
        for row in train:
            groups[tuple(row[col] for col in columns)].append(row[outcome])
        group_results = {}
        for key, values in groups.items():
            probability = (sum(values) + PRIOR_CASES * base_rate) / (len(values) + PRIOR_CASES)
            group_results[key] = {**bin_rate(values), "fitted_probability": round(probability, 6)}

        def predict(row):
            key = tuple(row[col] for col in columns)
            return group_results.get(key, {}).get("fitted_probability", base_rate)

        holdout = defaultdict(list)
        by_season = defaultdict(list)
        for row in test:
            holdout[tuple(row[col] for col in columns)].append(row[outcome])
            by_season[row["season"]].append((row[outcome], predict(row)))
        checks[name] = {
            "columns": columns,
            "fit": {" | ".join(k) or "all": v for k, v in sorted(group_results.items())},
            "holdout": {" | ".join(k) or "all": bin_rate(v) for k, v in sorted(holdout.items())},
            "holdout_predicted_events": round(sum(predict(row) for row in test), 3),
            "holdout_brier": round(mean((predict(row) - row[outcome]) ** 2 for row in test), 6),
            "by_holdout_season": {
                str(year): {"actual": sum(label for label, _ in pairs),
                            "predicted": round(sum(p for _, p in pairs), 3), "cases": len(pairs)}
                for year, pairs in sorted(by_season.items())
            },
        }
    return {"fit": bin_rate([row[outcome] for row in train]),
            "holdout": bin_rate([row[outcome] for row in test]), "rules": checks}


def check_head_rows(rows):
    expected = Counter({y: TEAMS for y in range(FIRST, LAST + 1)})
    if Counter(row["season"] for row in rows) != expected:
        raise ValueError("Expected complete coverage of all 30 franchises each season")
    if len({(row["season"], row["team"]) for row in rows}) != len(rows):
        raise ValueError("Duplicate head coaching team-season")
    for row in rows:
        stints = row["coaches"]
        if sum(c["wins"] for c in stints) != row["team_wins"]:
            raise ValueError(f"Unbalanced wins in {row['team']} {row['season']}")
        if sum(c["losses"] for c in stints) != row["team_losses"]:
            raise ValueError(f"Unbalanced losses in {row['team']} {row['season']}")
        recorded_order = [change["coach"] for change in row["changes"] if change["phase"] == "in_season"]
        if recorded_order != [c["coach"] for c in stints[:-1]]:
            raise ValueError(f"Unbalanced in-season changes in {row['team']} {row['season']}")


def head_coach_summary(rows):
    check_head_rows(rows)
    annual = defaultdict(Counter)
    interims = defaultdict(list)
    finished_tenures = defaultdict(list)
    in_season_firing_residuals = defaultdict(list)
    for row in rows:
        year = row["season"]
        sample = "fit" if year <= LAST_FIT else "holdout"
        counts = annual[year]
        counts["team_seasons"] += 1
        by_coach = {c["coach"]: c for c in row["coaches"]}
        for change in row["changes"]:
            phase, kind = change["phase"], change["kind"]
            counts[f"{phase}_changes"] += 1
            counts[f"{phase}_{kind}"] += 1
            st = by_coach[change["coach"]]
            if st["permanent_before_offseason"]:
                finished_tenures[sample].append(st["career_games_with_team"])
            if phase == "in_season" and kind == "fired" and change["coach"] == row["coaches"][0]["coach"]:
                residual = row["opening_coach_wins_vs_expectation_per_82"]
                if residual is not None:
                    in_season_firing_residuals[sample].append(residual)
        for coach in row["coaches"]:
            if coach["started_interim"]:
                counts["interims"] += 1
                kept = person_key(coach["coach"]) == person_key(row["opening_coach_next_year"])
                counts["interims_kept_next_opening"] += kept
                interims[sample].append(kept)
    annual_out = {}
    for year, counts in sorted(annual.items()):
        annual_out[str(year)] = {**counts, **{
            key: counts[key] for key in ("in_season_changes", "offseason_changes", "in_season_fired",
                                        "offseason_fired", "interims", "interims_kept_next_opening")
        }}
    return {
        "per_season": annual_out,
        "interims_still_head_at_next_opening": {sample: bin_rate(values) for sample, values in interims.items()},
        "finished_permanent_spells": {
            sample: {"n": len(values), "median_games": median(values), "median_82_game_seasons": round(median(values) / 82, 3)}
            for sample, values in finished_tenures.items()
        },
        "opening_coach_in_season_firing_pace_vs_expectation": {
            sample: {"n": len(values), "median_wins_per_82": round(median(values), 2)}
            for sample, values in in_season_firing_residuals.items()
        },
    }


def head_coach_fit(rows):
    season_end = []
    season_open = []
    for row in rows:
        y = row["season"]
        first, final = row["coaches"][0], row["coaches"][-1]
        if not first["started_interim"]:
            opening_games = first["career_games_with_team"] - first["wins"] - first["losses"]
            season_open.append({
                "season": y,
                "fired": any(c["phase"] == "in_season" and c["kind"] == "fired" and c["coach"] == first["coach"]
                             for c in row["changes"]),
                "tenure": tenure_band(opening_games),
            })
        residual = row["team_wins_vs_expectation_per_82"]
        if residual is None or not final["permanent_before_offseason"]:
            continue
        label = next((c["kind"] for c in row["changes"] if c["phase"] == "offseason"), "retained")
        season_end.append({
            "season": y,
            "fired": label == "fired",
            "fired_or_nonrenewed": label in {"fired", "nonrenewal"},
            "expectation": win_band(residual),
            "tenure": tenure_band(final["career_games_with_team"]),
            "record": record_band(row["team_wins"] / (row["team_wins"] + row["team_losses"])),
            "playoffs": playoff_band(row),
        })
    rules = {
        "win_record": ("record",),
        "wins_vs_expectation": ("expectation",),
        "tenure": ("tenure",),
        "playoffs": ("playoffs",),
        "expectation_and_tenure": ("expectation", "tenure"),
        "expectation_and_playoffs": ("expectation", "playoffs"),
    }
    return {
        "smoothing_cases": PRIOR_CASES,
        "offseason_strict": binary_checks(season_end, "fired", rules),
        "offseason_with_nonrenewal": binary_checks(season_end, "fired_or_nonrenewed", rules),
        "in_season_opening_coach": binary_checks(season_open, "fired", {"tenure": ("tenure",)}),
    }


def build(evidence):
    rows = evidence["observations"]["head_coach_team_seasons"]
    evidence["head_coaches"] = head_coach_summary(rows)
    evidence["head_coaches"]["checks"] = head_coach_fit(rows)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=EVIDENCE, help="Evidence JSON containing source observations")
    parser.add_argument("--output", type=Path, default=EVIDENCE, help="Destination for the rebuilt evidence JSON")
    args = parser.parse_args()
    evidence = build(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
