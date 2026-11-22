#!/usr/bin/env python3
"""Fit staff turnover from the dated observations in the evidence JSON.

Season numbers are end years. The trailing offseason belongs to the season
that just ended. This script uses only the standard library and no network.
"""

import argparse
import json
from math import comb
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from tempfile import NamedTemporaryFile
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


def head_coach_fit(rows, office_changed_by_regular_end):
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
            "front_office_change": "recorded" if (y, row["team"]) in office_changed_by_regular_end else "none_recorded",
        })
    rules = {
        "win_record": ("record",),
        "wins_vs_expectation": ("expectation",),
        "tenure": ("tenure",),
        "playoffs": ("playoffs",),
        "expectation_and_tenure": ("expectation", "tenure"),
        "expectation_and_playoffs": ("expectation", "playoffs"),
        "recorded_front_office_change": ("front_office_change",),
        "expectation_and_front_office_change": ("expectation", "front_office_change"),
    }
    return {
        "smoothing_cases": PRIOR_CASES,
        "offseason_strict": binary_checks(season_end, "fired", rules),
        "offseason_with_nonrenewal": binary_checks(season_end, "fired_or_nonrenewed", rules),
        "in_season_opening_coach": binary_checks(season_open, "fired", {"tenure": ("tenure",)}),
    }


def average(values):
    return round(mean(values), 6) if values else None


def assistant_stats(rows):
    return {
        "team_summers": len(rows),
        "average_prior_staff": average([r["prior_count"] for r in rows]),
        "average_departed_or_changed_role": average([r["departed"] for r in rows]),
        "average_added": average([r["added"] for r in rows]),
        "mean_team_departure_share": average([r["departure_share"] for r in rows]),
        "at_least_one_left": bin_rate([r["departed"] > 0 for r in rows]),
        "majority_of_old_staff_left": bin_rate([r["departure_share"] > 0.5 for r in rows]),
        "whole_old_staff_left": bin_rate([r["departure_share"] == 1 for r in rows]),
    }


def compare_assistants(snapshots, head_rows):
    teams = {(r["season"], r["team"]): r for r in snapshots}
    if len(teams) != len(snapshots):
        raise ValueError("Duplicate assistant snapshot")
    groups = defaultdict(dict)
    opening_heads = defaultdict(dict)
    for row in snapshots:
        year, team = row["season"], row["team"]
        roster = {person_key(name): name for name in row["assistants"]}
        if not roster or len(roster) != len(row["assistants"]):
            raise ValueError(f"Empty roster or duplicate assistant for {team} {year}")
        groups[year][team] = roster
        opening_heads[year][person_key(row["head_coach"])] = team

    past_season_stints = {
        (row["season"], row["team"]): {person_key(c["coach"]) for c in row["coaches"]}
        for row in head_rows
    }
    comparisons = []
    coverage = defaultdict(dict)
    promotions = []
    support_pairs = defaultdict(list)
    assistant_starts = []
    for (year, team), current in teams.items():
        coverage[year][team] = len(current["assistants"])
        old = teams.get((year - 1, team))
        if old is None:
            continue
        new_names = groups[year][team]
        old_names = groups[year - 1][team]
        new_head = person_key(current["head_coach"])
        incoming_head = new_head != person_key(old["head_coach"])
        left = old_names.keys() - new_names.keys()
        added = new_names.keys() - old_names.keys()
        prior_assistant_team = next(
            (t for t, roster in groups[year - 1].items() if new_head in roster), None
        )
        if incoming_head and prior_assistant_team:
            promotions.append({
                "cycle_ending_with_summer": year - 1, "coach": current["head_coach"],
                "from": prior_assistant_team, "to": team,
                "already_took_over_destination_during_cycle": new_head in past_season_stints[year - 1, team],
                "covered_previous_team_as_interim_during_cycle": (
                    prior_assistant_team != team and new_head in past_season_stints[year - 1, prior_assistant_team]
                ),
            })
        origin = opening_heads[year - 1].get(new_head) or prior_assistant_team
        prior_colleagues = groups[year - 1].get(origin, {})
        brought_colleagues = sorted(new_names[n] for n in added if n in prior_colleagues) if origin != team else []
        comparisons.append({
            "season": year - 1, "team": team, "head_coach": current["head_coach"],
            "head_status": "new" if incoming_head else "returning",
            "prior_count": len(old_names),
            "departed": len(left), "added": len(added), "departure_share": len(left) / len(old_names),
            "departed_names": sorted(old_names[n] for n in left),
            "added_names": sorted(new_names[n] for n in added),
            "head_coach_previous_nba_bench": origin if incoming_head and origin != team else None,
            "arrivals_listed_on_same_prior_bench": brought_colleagues,
        })
        for role, name in current["support_roles"].items():
            if role in old["support_roles"]:
                support_pairs[role].append({
                    "season": year - 1, "team": team, "previous": old["support_roles"][role],
                    "head_changed": incoming_head,
                    "current": name, "same_person": person_key(name) == person_key(old["support_roles"][role]),
                })
        if year == LAST + 1:
            continue
        for new_assistant in added:
            assistant_starts.append((year, team, new_assistant))

    # The newest roster is an association snapshot taken in November. The earlier
    # comparisons are primarily media guides printed near the start of the season.
    fit = [r for r in comparisons if r["season"] <= LAST_FIT]
    holdout = [r for r in comparisons if LAST_FIT < r["season"] < LAST]
    directory_check = [r for r in comparisons if r["season"] == LAST]
    by_head = {}
    for label, sample in (("fit", fit), ("holdout_guides", holdout), ("holdout_2026_association", directory_check)):
        by_head[label] = {g: assistant_stats([r for r in sample if r["head_status"] == g]) for g in ("returning", "new")}
    average_overall = mean(r["departure_share"] for r in fit)
    by_condition = {g: by_head["fit"][g]["mean_team_departure_share"] for g in ("returning", "new")}

    def expected_count(row, conditioned):
        share = by_condition[row["head_status"]] if conditioned else average_overall
        return row["prior_count"] * share

    scorecards = {}
    for label, sample in (("holdout_guides", holdout), ("holdout_2026_association", directory_check)):
        cross_team = [r for r in sample if r["head_coach_previous_nba_bench"]]
        scorecards[label] = {
            "flat_average_absolute_error_in_departures": average([abs(expected_count(r, False) - r["departed"]) for r in sample]),
            "conditioned_average_absolute_error_in_departures": average([abs(expected_count(r, True) - r["departed"]) for r in sample]),
            "incoming_head_from_identified_external_nba_bench": bin_rate([bool(r["arrivals_listed_on_same_prior_bench"]) for r in cross_team]),
        }

    survival = {}
    for horizon in (1, 2, 3):
        for label, select in (
            ("fit", lambda y: y <= LAST_FIT),
            ("holdout_guides", lambda y: LAST_FIT < y < LAST),
        ):
            continuing = []
            for year, team, assistant in assistant_starts:
                end_summer = year + horizon - 1
                if not select(end_summer):
                    continue
                followups = [groups[y].get(team) for y in range(year + 1, year + horizon + 1)]
                if all(roster is not None for roster in followups):
                    continuing.append(all(assistant in roster for roster in followups))
            survival.setdefault(label, {})[str(horizon)] = bin_rate(continuing)

    return {
        "staff_directory_coverage": {str(year): {"teams": len(group), "slots": sum(group.values())} for year, group in sorted(coverage.items())},
        "assistant_changes_by_head_status": by_head,
        "per_summer": {str(y): assistant_stats([r for r in comparisons if r["season"] == y]) for y in sorted({r["season"] for r in comparisons})},
        "departure_model": {"fit_flat_share": round(average_overall, 6), "fit_by_head_status": by_condition,
                            "held_out_checks": scorecards},
        "newly_listed_assistants_still_listed_after_n_summers": survival,
        "same_prior_staff_arrivals_in_fit": bin_rate([
            bool(r["arrivals_listed_on_same_prior_bench"]) for r in fit if r["head_coach_previous_nba_bench"]
        ]),
        "promotions_confirmed_by_consecutive_snapshots": sorted(promotions, key=lambda r: (r["cycle_ending_with_summer"], r["to"])),
        "outside_promotions_per_summer_minimum": {
            str(y): sum(r["cycle_ending_with_summer"] == y and r["from"] != r["to"] for r in promotions)
            for y in sorted({r["season"] for r in comparisons})
        },
        "support_staff_same_name": {
            role: {
                label: bin_rate([r["same_person"] for r in rows if select(r["season"])])
                for label, select in (("fit", lambda y: y <= LAST_FIT), ("holdout_guides", lambda y: y > LAST_FIT))
            }
            for role, rows in sorted(support_pairs.items())
        },
        "support_staff_comparisons": dict(sorted(support_pairs.items())),
        "paired_observations": sorted(comparisons, key=lambda r: (r["season"], r["team"])),
    }


def head_coach_next_jobs(rows, examples, snapshots):
    opening = defaultdict(dict)
    for row in rows:
        opening[row["season"]][person_key(row["opening_coach_next_year"])] = row["team"]
    assistants = defaultdict(dict)
    for snapshot in snapshots:
        for name in snapshot["assistants"]:
            assistants[snapshot["season"] - 1][person_key(name)] = snapshot["team"]
    documented_other_destinations = {
        (r["season"], r["team"], person_key(r["coach"])): r["next_role"]
        for r in examples if r["within_following_opening"]
    }
    head_job = defaultdict(list)
    recent_destinations = defaultdict(Counter)
    for row in rows:
        year, team = row["season"], row["team"]
        cohort = "fit" if year <= LAST_FIT else "holdout"
        for change in row["changes"]:
            if change["kind"] != "fired":
                continue
            coach = person_key(change["coach"])
            next_team = opening[year].get(coach)
            switched = bool(next_team and team != next_team)
            head_job[cohort].append(switched)
            if year < 2020:
                continue
            destination = documented_other_destinations.get((year, team, coach))
            if destination is None:
                if switched:
                    destination = "nba_head_coach"
                elif assistants[year].get(coach):
                    destination = "nba_assistant"
                else:
                    destination = "unverified"
            recent_destinations[cohort][destination] += 1
    return {
        "other_nba_head_job_by_next_opening": {label: bin_rate(values) for label, values in head_job.items()},
        "known_first_roles_or_staff_listing_by_following_opening_since_2020": {
            label: dict(sorted(counts.items())) for label, counts in recent_destinations.items()
        },
    }


def front_office_summary(rows, changes):
    season_counts = {str(y): Counter({"in_season_fired": 0, "offseason_fired": 0,
                                      "in_season_nonrenewal": 0, "offseason_nonrenewal": 0})
                     for y in range(FIRST, LAST + 1)}
    fired_or_not_renewed = defaultdict(set)
    office_changed_by_regular_end = set()
    recognized = {(r["season"], r["team"]) for r in rows}
    for event in changes:
        year, team, phase, kind = (event[k] for k in ("season", "team", "phase", "kind"))
        if (year, team) not in recognized or phase not in {"in_season", "offseason"}:
            raise ValueError(f"Invalid executive change {event}")
        season_counts[str(year)][f"{phase}_{kind}"] += 1
        season_counts[str(year)]["known_lead_changes"] += 1
        if phase == "in_season":
            office_changed_by_regular_end.add((year, team))
        elif year < LAST:
            office_changed_by_regular_end.add((year + 1, team))
        if phase == "offseason" and kind in {"fired", "nonrenewal"}:
            fired_or_not_renewed[year, team].add(kind)

    previous = {(r["season"], r["team"]): r for r in rows}
    outlook = []
    for row in rows:
        y, team = row["season"], row["team"]
        if y <= FIRST or row["team_wins_vs_expectation_per_82"] is None:
            continue
        kinds = fired_or_not_renewed[y, team]
        current_miss = playoff_band(row) == "missed_playoffs"
        previous_miss = playoff_band(previous[y - 1, team]) == "missed_playoffs"
        outlook.append({
            "season": y, "reported_firing": "fired" in kinds, "reported_firing_or_nonrenewal": bool(kinds),
            "result": record_band(row["team_wins"] / (row["team_wins"] + row["team_losses"])),
            "expectation": win_band(row["team_wins_vs_expectation_per_82"]),
            "two_straight_misses": "two_or_more" if current_miss and previous_miss else "other",
        })
    rules = {"win_record": ("result",), "wins_vs_expectation": ("expectation",),
             "two_straight_playoff_misses": ("two_straight_misses",)}
    return {
        "known_case_ledger": True,
        "per_season": {y: dict(counter) for y, counter in season_counts.items()},
        "reported_offseason_dismissal_checks": {
            "strict": binary_checks(outlook, "reported_firing", rules),
            "with_nonrenewal": binary_checks(outlook, "reported_firing_or_nonrenewal", rules),
        },
    }, office_changed_by_regular_end


def two_slot_proxy(comparisons):
    """Draw two distinct names from each old bench and average the turnover odds."""
    by_status = defaultdict(list)
    for row in comparisons:
        sample = "fit" if row["season"] <= LAST_FIT else "holdout"
        old_count, gone = row["prior_count"], row["departed"]
        if old_count < 2 or row["season"] == LAST:
            continue
        options = comb(old_count, 2)
        kept = old_count - gone
        by_status[sample, row["head_status"]].append(
            [comb(kept, 2) / options, kept * gone / options, comb(gone, 2) / options]
        )
    return {
        label: {
            status: dict(zip(("replace_neither", "replace_one", "replace_both"),
                             [round(mean(probs), 5) for probs in zip(*by_status[label, status])]))
            for status in ("returning", "new")
        }
        for label in ("fit", "holdout")
    }


def build(evidence):
    observations = evidence["observations"]
    rows = observations["head_coach_team_seasons"]
    head_coaches = head_coach_summary(rows)
    front_office, front_changes = front_office_summary(rows, observations["front_office_lead_changes"])
    head_coaches["checks"] = head_coach_fit(rows, front_changes)
    snapshots = observations["assistant_staff_snapshots"]
    head_coaches["destinations"] = head_coach_next_jobs(
        rows, observations["head_coach_destination_examples"], snapshots
    )
    assistants = compare_assistants(snapshots, rows)
    assistants["two_slot_assistant_proxy"] = two_slot_proxy(assistants["paired_observations"])
    results = {
        "head_coaches": head_coaches,
        "assistants_and_support_staff": assistants,
        "front_office": front_office,
    }
    inputs = {key: value for key, value in evidence.items() if key not in results}
    return {**inputs, **results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=EVIDENCE, help="Evidence JSON containing source observations")
    parser.add_argument("--output", type=Path, default=EVIDENCE, help="Destination for the rebuilt evidence JSON")
    args = parser.parse_args()
    evidence = build(json.loads(args.input.read_text(encoding="utf-8")))
    formatted = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    with NamedTemporaryFile(mode="w", dir=args.output.parent, encoding="utf-8", delete=False) as output:
        path = Path(output.name)
        try:
            output.write(formatted)
            output.close()
            path.replace(args.output)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
