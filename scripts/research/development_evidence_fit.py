#!/usr/bin/env python3
"""Rebuild the NBA development targets from the frozen public panel or cached HTML."""

import argparse
import csv
import gzip
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from statistics import fmean, median

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "data/research/development_evidence.json"
BBI = ROOT / "data/research/bbi"
FIRST, LAST = 2005, 2026
LOOKBACK = 1996
DRAFT_FIRST, DRAFT_LAST = 1995, 2019
MINUTES = 1000
HORIZON = 7
YOUNG_AGES = range(19, 24)
AGE_BANDS = ((19, 21), (22, 24), (25, 27), (28, 30), (31, 33), (34, 36), (37, 45))
LEVELS = ("bottom", "middle", "top")
DRAFT_GROUPS = ("1–3", "4–10", "11–30", "second round", "undrafted")
BREF = "https://www.basketball-reference.com"
SOURCES = {
    "advanced": {
        "publisher": "Basketball Reference",
        "pages": f"{BREF}/leagues/NBA_{{season_end}}_advanced.html",
        "season_ends": [LOOKBACK, LAST],
        "analysis_season_ends": [FIRST, LAST],
        "accessed": "2026-11-21",
        "methodology": f"{BREF}/about/bpm2.html",
    },
    "draft": {
        "publisher": "Basketball Reference",
        "pages": f"{BREF}/draft/NBA_{{draft_year}}.html",
        "draft_years": [DRAFT_FIRST, DRAFT_LAST],
        "analysis_draft_years": [FIRST, DRAFT_LAST],
        "accessed": "2026-11-21",
    },
    "lebron": {
        "publisher": "Basketball Index",
        "url": "https://fanspo.com/bbi-role-explorer/lebron",
        "methodology": "https://www.bball-index.com/lebron-introduction/",
        "cache": "captures/fanspo_tools/lebron/lebron_separate-seasons_raw_all-2010-2026.csv",
    },
    "progression": {
        "publisher": "Basketball Index",
        "url": "https://www.bball-index.com/data-tools-package/",
        "cache": "tools/progression_player_seasons.csv.gz",
    },
}


@dataclass(frozen=True)
class Season:
    year: int
    player: str
    name: str
    age: int
    minutes: int
    bpm: float | None
    vorp: float | None


@dataclass(frozen=True)
class DraftPick:
    year: int
    pick: int
    player: str | None
    name: str


@dataclass(frozen=True)
class Change:
    start: Season
    end: Season
    level: str
    previous_star: bool | None


class StatTable(HTMLParser):
    def __init__(self, table_id):
        super().__init__()
        self.table_id = table_id
        self.active = False
        self.rows = []
        self.row = self.cell = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "table" and attrs.get("id") == self.table_id:
            self.active = True
        if not self.active:
            return
        if tag == "tr":
            self.row = {}
        if tag in ("td", "th") and self.row is not None and "data-stat" in attrs:
            self.cell = attrs
            self.cell["text"] = ""
        if tag == "a" and self.cell is not None:
            self.cell["href"] = attrs.get("href", "")

    def handle_endtag(self, tag):
        if not self.active:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.cell["text"] = self.cell["text"].strip()
            self.row[self.cell["data-stat"]] = self.cell
            self.cell = None
        if tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = None
        if tag == "table":
            self.active = False

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data


def tables(path, table_id):
    parser = StatTable(table_id)
    html = path.read_text(encoding="utf-8")
    # Some Sports Reference tables are delivered inside an HTML comment.
    parser.feed(html.replace("<!--", "").replace("-->", ""))
    if not parser.rows:
        raise ValueError(f"No {table_id} rows in {path}")
    return parser.rows


def number(cell):
    if not cell["text"]:
        return None
    return round(float(cell.get("csk", cell["text"])), 6)


def read_advanced(cache, year):
    grouped = defaultdict(list)
    for row in tables(cache / f"NBA_{year}_advanced.html", "advanced"):
        player = row.get("name_display", row.get("player", {}))
        key = player.get("data-append-csv")
        if not key:
            continue
        season = Season(year, key, player["text"], int(row["age"]["text"]),
                        int(row["mp"]["text"]), number(row["bpm"]), number(row["vorp"]))
        team = row.get("team_name_abbr", row.get("team_id", {}))["text"]
        grouped[key].append((team, season))
    if len(grouped) < 350:
        raise ValueError(f"Incomplete advanced table for {year}: {len(grouped)} players")
    for key, entries in sorted(grouped.items()):
        if len(entries) == 1:
            yield entries[0][1]
            continue
        total, = [season for team, season in entries if team == "TOT" or re.fullmatch(r"\d+TM", team)]
        if total.minutes != sum(season.minutes for _, season in entries if season is not total):
            raise ValueError(f"Inconsistent total minutes: {year} {key}")
        yield total


def read_draft(cache, year):
    picks = []
    for row in tables(cache / f"NBA_{year}.html", "stats"):
        pick = row.get("pick_overall", {}).get("text", "")
        if not pick.isdigit():
            continue
        player = row["player"]
        link = re.search(r"/players/./([^/]+)\.html", player.get("href", ""))
        picks.append(DraftPick(year, int(pick), link[1] if link else None, player["text"]))
    if len(picks) < 55 or len({p.pick for p in picks}) != len(picks):
        raise ValueError(f"Incomplete or duplicate draft picks for {year}")
    return picks


def frozen_inputs(cache, prior):
    if cache:
        return {
            "season_columns": list(Season.__dataclass_fields__),
            "draft_columns": list(DraftPick.__dataclass_fields__),
            "seasons": [list(row.__dict__.values()) for year in range(LOOKBACK, LAST + 1)
                        for row in read_advanced(cache, year)],
            "draft": [list(row.__dict__.values()) for year in range(DRAFT_FIRST, DRAFT_LAST + 1)
                      for row in read_draft(cache, year)],
        }
    return prior["public_inputs"]


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def spread(values):
    values = list(values)
    if not values:
        return {"n": 0, "mean": None, "p10": None, "median": None, "p90": None}
    return {
        "n": len(values),
        "mean": round(fmean(values), 4),
        "p10": round(percentile(values, .1), 4),
        "median": round(median(values), 4),
        "p90": round(percentile(values, .9), 4),
    }


def shorten(year):
    # Fraction of an 82-game schedule. The NBA's bubble schedule varied slightly by team.
    return {1999: 50 / 82, 2012: 66 / 82, 2020: 72 / 82, 2021: 72 / 82}.get(year, 1)


def eligible(row, minutes=MINUTES):
    return row.bpm is not None and row.minutes >= minutes * shorten(row.year)


class Panel:
    def __init__(self, seasons, minutes=MINUTES):
        self.seasons = seasons
        self.minutes = minutes
        self.by_player = defaultdict(dict)
        self.by_year = defaultdict(list)
        same_age = defaultdict(list)
        for row in seasons:
            self.by_player[row.player][row.year] = row
            self.by_year[row.year].append(row)
            if eligible(row, minutes):
                same_age[row.year, row.age].append(row)
        if sum(map(len, self.by_player.values())) != len(seasons):
            raise ValueError("Duplicate player-season")
        self.levels = {}
        for peers in same_age.values():
            peers.sort(key=lambda row: (row.bpm, row.minutes, row.player))
            for index, row in enumerate(peers):
                # Use the center of each rank. Lone qualifiers fall in the middle.
                self.levels[row.player, row.year] = LEVELS[int(3 * (index + .5) / len(peers))]
        self.ranks = self.make_ranks("bpm")
        self.vorp_ranks = self.make_ranks("vorp")

    def make_ranks(self, metric):
        ranks = {}
        for year, rows in self.by_year.items():
            qualified = (row for row in rows if eligible(row, self.minutes)
                         and getattr(row, metric) is not None)
            ranked = sorted(qualified, key=lambda row: (-getattr(row, metric), -row.minutes, row.player))
            ranks[year] = {row.player: rank for rank, row in enumerate(ranked, 1)}
        return ranks

    def rank(self, player, year):
        return self.ranks[year].get(player, math.inf)

    def changes(self):
        for row in self.seasons:
            if row.year < FIRST or not eligible(row, self.minutes):
                continue
            career = self.by_player[row.player]
            following = career.get(row.year + 1)
            if not following or not eligible(following, self.minutes):
                continue
            if following.age != row.age + 1:
                raise ValueError(f"Age changes by more than one year: {row} -> {following}")
            previous = career.get(row.year - 1)
            star = None
            if previous and eligible(previous, self.minutes):
                star = self.vorp_ranks[previous.year][row.player] <= 25
            yield Change(row, following, self.levels[row.player, row.year], star)


def group_by(rows, key):
    grouped = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return grouped


def delta(change):
    return change.end.bpm - change.start.bpm


def age_band(age):
    for low, high in AGE_BANDS:
        if low <= age <= high:
            return f"{low}–{high}"
    return "other"


def change_table(changes, measure=delta):
    by_age = group_by(changes, lambda change: change.start.age)
    return {age: {
        label: spread(measure(c) for c in rows if label == "all" or c.level == label)
        for label in ("all", *LEVELS)
    } for age, rows in sorted(by_age.items())}


def older_table(changes, measure=delta):
    return {
        f"{low}–{high}": {
            label: spread(measure(c) for c in changes if low <= c.start.age <= high
                          and (label == "all" or c.previous_star is star))
            for label, star in (("all", None), ("prior_top_25_vorp", True),
                                ("other_prior_qualifiers", False))
        }
        for low, high in ((28, 29), (30, 32), (33, 35), (36, 39), (40, 45))
    }


def peak_index(changes, measure=delta):
    by_age = group_by(changes, lambda change: change.start.age)
    index = {19: 0.0}
    for age in range(19, 40):
        index[age + 1] = index[age] + fmean(measure(row) for row in by_age[age])
    smoothed = {age: fmean(index[a] for a in (age - 1, age, age + 1))
                for age in range(20, 40)}
    peak = max(smoothed, key=smoothed.get)
    return {"peak_age": peak, "index_from_age_19": {a: round(v, 4) for a, v in index.items()},
            "three_age_average": {a: round(v, 4) for a, v in smoothed.items()}}


def change_fit(train, test):
    age_only = {key: spread(map(delta, rows))
                for key, rows in group_by(train, lambda c: age_band(c.start.age)).items()}
    by_level = {key: spread(map(delta, rows)) for key, rows in
                group_by(train, lambda c: (age_band(c.start.age), c.level)).items()}
    errors = defaultdict(list)
    interval_hits = []
    cohort_errors = defaultdict(list)
    for c in test:
        band = age_band(c.start.age)
        actual = delta(c)
        fitted = by_level.get((band, c.level), age_only[band])
        errors["no_change"].append(actual)
        errors["age_band"].append(actual - age_only[band]["mean"])
        errors["age_band_and_level"].append(actual - fitted["mean"])
        interval_hits.append(fitted["p10"] <= actual <= fitted["p90"])
        cohort_errors[band, c.level].append(actual - fitted["mean"])
    return {
        "n": len(test),
        "mean_absolute_error": {key: round(fmean(map(abs, vals)), 4) for key, vals in errors.items()},
        "age_level_middle_80_coverage": round(fmean(interval_hits), 4),
        "age_level_mean_absolute_group_bias": round(fmean(abs(fmean(v))
                                                         for v in cohort_errors.values()), 4),
        "age_band_fit": age_only,
        "age_band_level_fit": {band: {level: by_level[band, level] for level in LEVELS}
                               for band in age_only},
    }


def development(panel):
    changes = list(panel.changes())
    trained = [c for c in changes if c.end.year <= 2020]
    held_out = [c for c in changes if c.start.year >= 2020]
    exits = {}
    for age in range(19, 41):
        starts = [row for row in panel.seasons if FIRST <= row.year < LAST and row.age == age
                  and eligible(row, panel.minutes)]
        exited = sum(row.year + 1 not in panel.by_player[row.player] for row in starts)
        kept = sum(eligible(panel.by_player[row.player][row.year + 1], panel.minutes)
                   for row in starts if row.year + 1 in panel.by_player[row.player])
        exits[age] = {"starting_qualifiers": len(starts), "next_season_qualified": kept,
                      "next_season_nba_below_cut": len(starts) - exited - kept,
                      "next_season_no_nba_minutes": exited}
    return {
        "by_start_age": change_table(changes),
        "older_by_prior_star_status": older_table(changes),
        "peak": peak_index(changes),
        "next_year_availability_by_start_age": exits,
        "holdout": {"train_target_years": [2006, 2020], "test_target_years": [2021, 2026],
                    "overall": change_fit(trained, held_out),
                    "test_by_start_age": change_table(held_out),
                    "training_peak": peak_index(trained)},
    }


@dataclass(frozen=True)
class Opportunity:
    player: str | None
    baseline: int
    group: str
    first_hits: dict


def hit_summary(rows, threshold):
    at_risk = [row for row in rows if row.first_hits[threshold] != "already"]
    hits = [row.first_hits[threshold] for row in at_risk
            if row.first_hits[threshold] is not None]
    return {
        "n": len(at_risk),
        "already": len(rows) - len(at_risk),
        "hits": len(hits),
        "rate": round(len(hits) / len(at_risk), 5) if at_risk else None,
        "age_at_first_hit": spread(age for age, _ in hits),
        "seasons_to_first_hit": spread(years for _, years in hits),
        "hit_counts_by_years_after_baseline": dict(sorted(Counter(lag for _, lag in hits).items())),
    }


THRESHOLDS = (10, 25, 50)


def first_hits(panel, player, baseline, exclude_previous):
    career = panel.by_player.get(player, {})
    outcomes = {}
    for threshold in THRESHOLDS:
        if exclude_previous and any(year <= baseline and panel.rank(player, year) <= threshold
                                    for year in career):
            outcomes[threshold] = "already"
            continue
        outcomes[threshold] = next(
            ((career[year].age, year - baseline) for year in range(baseline + 1, baseline + HORIZON + 1)
             if panel.rank(player, year) <= threshold), None)
    return outcomes


def group_summary(rows):
    return {group: {f"top_{k}": hit_summary(group_rows, k) for k in THRESHOLDS}
            for group, group_rows in group_by(rows, lambda row: row.group).items()}


def probability_fit(rows, last_train, compare_age_only=False):
    training = [row for row in rows if row.baseline <= last_train]
    testing = [row for row in rows if row.baseline >= last_train + HORIZON]
    scores = {}
    for k in THRESHOLDS:
        base = hit_summary(training, k)["rate"]
        groups = {key: hit_summary(group, k) for key, group in
                  group_by(training, lambda row: row.group).items()}
        actual = [row for row in testing if row.first_hits[k] != "already"]
        # Pull tiny groups toward the pooled rate with ten equivalent observations.
        chances = {group: (stats["hits"] + 10 * base) / (stats["n"] + 10)
                   for group, stats in groups.items()}
        outcomes = [row.first_hits[k] is not None for row in actual]
        forecasts = [chances.get(row.group, base) for row in actual]
        scores[f"top_{k}"] = {
            "n": len(actual), "hits": sum(outcomes),
            "pooled_train_rate": base,
            "train_group_probabilities": {group: round(p, 5) for group, p in chances.items()},
            "brier_group": round(fmean((p - y) ** 2 for p, y in zip(forecasts, outcomes)), 5),
            "brier_pooled": round(fmean((base - y) ** 2 for y in outcomes), 5),
            "mean_predicted": round(fmean(forecasts), 5),
        }
        if compare_age_only:
            def age(row):
                return row.group.split(" ", 1)[0]

            age_groups = {key: hit_summary(group, k) for key, group in group_by(training, age).items()}
            estimates = {key: (stats["hits"] + 10 * base) / (stats["n"] + 10)
                         for key, stats in age_groups.items()}
            scores[f"top_{k}"]["brier_age_only"] = round(fmean(
                (estimates.get(age(row), base) - y) ** 2 for row, y in zip(actual, outcomes)), 5)
    return {"last_train_baseline": last_train, "first_test_baseline": last_train + HORIZON,
            "last_train_outcome": last_train + HORIZON,
            "first_test_outcome": last_train + HORIZON + 1, "scores": scores,
            "test_by_group": group_summary(testing)}


def pick_group(number):
    if number <= 3:
        return DRAFT_GROUPS[0]
    if number <= 10:
        return DRAFT_GROUPS[1]
    if number <= 30:
        return DRAFT_GROUPS[2]
    return DRAFT_GROUPS[3]


def draft_opportunities(panel, drafts):
    drafted = {pick.player for pick in drafts if pick.player}
    opportunities = []
    for pick in drafts:
        if pick.year < FIRST:
            continue
        group = pick_group(pick.pick)
        hits = first_hits(panel, pick.player, pick.year, exclude_previous=False)
        opportunities.append(Opportunity(pick.player, pick.year, group, hits))
    for player, career in panel.by_player.items():
        debut = min(career)
        if player not in drafted and FIRST < debut <= LAST - HORIZON + 1:
            hits = first_hits(panel, player, debut - 1, exclude_previous=False)
            opportunities.append(Opportunity(player, debut - 1, "undrafted", hits))
    return opportunities


def formation(panel, drafts):
    young = []
    for row in panel.seasons:
        if FIRST <= row.year <= LAST - HORIZON and row.age in YOUNG_AGES:
            level = panel.levels.get((row.player, row.year), "below minutes cut")
            young.append(Opportunity(row.player, row.year, f"{row.age} {level}",
                                     first_hits(panel, row.player, row.year, exclude_previous=True)))
    draft = draft_opportunities(panel, drafts)
    return {
        "follow_up_seasons": HORIZON,
        "young_by_age_and_level": group_summary(young),
        "draft_by_pick": group_summary(draft),
        "young_holdout": probability_fit(young, last_train=2010, compare_age_only=True),
        "draft_holdout": probability_fit(draft, last_train=2010),
    }


def top_players(panel, rankings, year, count=5):
    return [panel.by_player[player][year] for player, rank in rankings[year].items() if rank <= count]


def superstars(panel):
    top = {year: top_players(panel, panel.ranks, year)
           for year in range(LOOKBACK, LAST + 1)}
    ids = {year: {row.player for row in rows} for year, rows in top.items()}
    firsts = {}
    for year, rows in top.items():
        for row in rows:
            firsts.setdefault(row.player, year)

    cutoff = median(top[year][-1].bpm for year in range(FIRST, 2021))
    years = []
    for year in range(FIRST, LAST + 1):
        current = ids[year]
        previous = ids[year - 1]
        first = [row for row in top[year] if firsts[row.player] == year]
        clear = [row for row in first if min(panel.by_player[row.player]) > LOOKBACK]
        years.append({
            "season_end": year,
            "ranked_top_five": [{"name": row.name, "age": row.age, "bpm": row.bpm}
                                for row in top[year]],
            "top_five_mean_bpm": round(fmean(row.bpm for row in top[year]), 4),
            "fifth_bpm": top[year][-1].bpm,
            "top_five_vorp_overlap": len(current & {row.player for row in
                                                   top_players(panel, panel.vorp_ranks, year)}),
            "at_or_above_fixed_bpm": sum(eligible(row, panel.minutes) and row.bpm >= cutoff
                                         for row in panel.by_year[year]),
            "retained": len(current & previous),
            "new_to_last_years_top_five": len(current - previous),
            "first_observed_top_five": [row.name for row in first],
            "first_top_five_with_full_history": [row.name for row in clear],
        })

    spell_starts = [(year, player) for year in range(FIRST, LAST + 1)
                    for player in sorted(ids[year] - ids[year - 1])]
    survival = {1: {"spells_at_risk": len(spell_starts), "survived_step": len(spell_starts), "share": 1.0}}
    active = spell_starts
    share = 1.0
    for length in range(2, 9):
        at_risk = [(year, player) for year, player in active if year + length - 1 <= LAST]
        active = [(year, player) for year, player in at_risk if player in ids[year + length - 1]]
        share *= len(active) / len(at_risk)
        survival[length] = {"spells_at_risk": len(at_risk), "survived_step": len(active),
                            "share": round(share, 5)}
    mature = [(player, year) for player, year in firsts.items() if FIRST <= year <= LAST - 9
              and min(panel.by_player[player]) > LOOKBACK]
    ten_year_total = spread(sum(player in ids[y] for y in range(year, year + 10))
                            for player, year in mature)

    def summarize(records):
        return {
            "n_seasons": len(records),
            "new_or_returning_slots": spread(row["new_to_last_years_top_five"] for row in records),
            "first_observed_count": spread(len(row["first_observed_top_five"]) for row in records),
            "confirmed_first_count": spread(len(row["first_top_five_with_full_history"])
                                            for row in records),
            "fixed_threshold_count": spread(row["at_or_above_fixed_bpm"] for row in records),
            "top_five_mean_bpm": spread(row["top_five_mean_bpm"] for row in records),
            "fifth_bpm": spread(row["fifth_bpm"] for row in records),
            "vorp_overlap": spread(row["top_five_vorp_overlap"] for row in records),
        }

    training, testing = summarize(years[:16]), summarize(years[16:])
    validation = {}
    for key, values, baseline in (
        ("fixed_threshold_count", [r["at_or_above_fixed_bpm"] for r in years[16:]], 5),
        ("confirmed_first_count", [len(r["first_top_five_with_full_history"]) for r in years[16:]], 1),
        ("new_or_returning_slots", [r["new_to_last_years_top_five"] for r in years[16:]], 2),
    ):
        prediction = training[key]["mean"]
        validation[key] = {
            "training_prediction": prediction,
            "test_observed_mean": testing[key]["mean"],
            "test_mae": round(fmean(abs(prediction - v) for v in values), 4),
            "baseline": baseline, "baseline_test_mae": round(fmean(abs(baseline - v) for v in values), 4),
        }
    return {
        "fixed_bpm_cutoff": cutoff,
        "cutoff_method": "Median fifth-ranked BPM in 2005–2020, frozen for 2021–2026.",
        "by_season": years,
        "all_seasons": summarize(years),
        "consecutive_spell_survival": survival,
        "top_five_seasons_in_ten_years_from_first": ten_year_total,
        "holdout": {"train_seasons": [2005, 2020], "test_seasons": [2021, 2026],
                    "forecasts": validation},
    }


def cases(panel, drafts):
    late = []
    age_23 = [row for row in panel.seasons if FIRST <= row.year <= LAST - HORIZON and row.age == 23]
    reached = 0
    for row in age_23:
        career = panel.by_player[row.player]
        first = next((r for y, r in sorted(career.items()) if y <= row.year + HORIZON
                      and panel.rank(row.player, y) <= 25), None)
        if first is None:
            continue
        reached += 1
        if first.age >= 27:
            rank = panel.rank(row.player, row.year)
            late.append({"name": row.name, "age_23_rank": int(rank) if math.isfinite(rank) else None,
                         "age_23_minutes": row.minutes, "first_top_25_age": first.age,
                         "first_top_25_season": first.year, "first_top_25_rank": panel.rank(row.player, first.year)})
    strict = [row for row in late if row["age_23_rank"] is None or row["age_23_rank"] > 100]
    misses = []
    for pick in drafts:
        if pick.year < FIRST or pick.pick > 10:
            continue
        years = range(pick.year + 1, pick.year + HORIZON + 1)
        career = panel.by_player.get(pick.player, {})
        rotation = sum(eligible(career[y], panel.minutes) for y in years if y in career)
        best = min(panel.rank(pick.player, y) for y in years)
        misses.append({"name": pick.name, "draft_year": pick.year, "pick": pick.pick,
                       "qualified_seasons": rotation,
                       "best_rank": int(best) if math.isfinite(best) else None})
    no_top_50 = [row for row in misses if row["best_rank"] is None or row["best_rank"] > 50]
    bust = [row for row in no_top_50 if row["qualified_seasons"] < 3]
    return {
        "age_23_cohort_n": len(age_23), "age_23_cohort_ever_top_25_through_30": reached,
        "late_first_top_25_age_27_to_30": len(late),
        "strict_late_from_outside_top_100_at_age_23": len(strict),
        "late_bloomers": late,
        "top_ten_picks_n": len(misses), "top_ten_no_top_50": len(no_top_50),
        "top_ten_no_top_50_and_fewer_than_3_qualifying_seasons": len(bust),
        "bust_by_pick_group": {group: {"n": sum(pick_group(r["pick"]) == group for r in misses),
                                      "busts": sum(pick_group(r["pick"]) == group for r in bust)}
                               for group in DRAFT_GROUPS[:2]},
        "busts": bust,
    }


def normalized(name):
    folded = name.casefold().replace("ı", "i")
    ascii_name = unicodedata.normalize("NFKD", folded).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name)


def without_suffix(name):
    return normalized(re.sub(r"\s+(?:jr\.?|sr\.?|ii|iii|iv)$", "", name.casefold()))


# The same NBA player uses different spellings between the two publishers.
BBI_ALIASES = {
    "adamabal": "adamaalphabal",
    "camreynolds": "cameronreynolds",
    "eneskanter": "enesfreedom",
    "flipmurray": "ronaldmurray",
    "jefferytaylor": "jefftaylor",
    "matthurt": "matthewhurt",
    "mitchellcreek": "mitchcreek",
    "nenehilario": "nene",
    "nigelhayes": "nigelhayesdavis",
    "patrickmills": "pattymills",
    "louiswilliams": "louwilliams",
    "lucmoute": "lucmbahamoute",
    "ishmaelsmith": "ishsmith",
    "poohjeter": "eugenejeter",
    "ronaldhollandii": "ronholland",
    "trevonscott": "trescott",
    "vincentedwards": "vinceedwards",
    "vincenthunter": "vincehunter",
    "vitorfaverani": "vitorluizfaverani",
}


def bbi_check(panel):
    leb_path = BBI / SOURCES["lebron"]["cache"]
    progression_path = BBI / SOURCES["progression"]["cache"]
    if not leb_path.is_file() or not progression_path.is_file():
        return None
    with leb_path.open(encoding="utf-8-sig", newline="") as file:
        dashboard = list(csv.DictReader(file))
    with gzip.open(progression_path, "rt", encoding="utf-8-sig", newline="") as file:
        progression = list(csv.DictReader(file))
    progression_by_id = {(str(2000 + int(r["season"][-2:])), r["nba_player_id"]): r
                         for r in progression}
    if len(progression_by_id) != len(progression):
        raise ValueError("Duplicate Basketball Index progression season")
    by_name = group_by(panel.seasons, lambda row: (row.year, normalized(row.name)))
    by_short_name = group_by(panel.seasons, lambda row: (row.year, without_suffix(row.name)))
    matched = {}
    unmatched = Counter()
    agreement = []
    age_disagreements = minute_disagreements = 0
    for row in dashboard:
        year = int(row["Season"])
        name = normalized(row["Player"])
        progression_row = progression_by_id.get((row["Season"], row["nba_id"]))
        candidates = (by_name.get((year, name)) or by_name.get((year, BBI_ALIASES.get(name)))
                      or by_short_name.get((year, without_suffix(row["Player"])), []))
        if len(candidates) > 1 and progression_row:
            candidates = [r for r in candidates if r.age == int(progression_row["age"])]
        if not candidates or len(candidates) != 1:
            unmatched[row["Player"]] += 1
            continue
        bref = candidates[0]
        key = bref.player, year
        if key in matched:
            raise ValueError(f"Multiple Basketball Index matches to {key}")
        impact = float(row["LEBRON"])
        matched[key] = impact
        if progression_row:
            agreement.append(impact - float(progression_row["LEBRON"]))
            age_disagreements += int(progression_row["age"]) != bref.age
            minute_disagreements += abs(float(progression_row["minutes"]) - bref.minutes) > 5

    def leb_delta(c):
        return matched[c.end.player, c.end.year] - matched[c.start.player, c.start.year]

    changes = [c for c in panel.changes()
               if (c.start.player, c.start.year) in matched and (c.end.player, c.end.year) in matched]
    overlap = {}
    for year in range(2010, LAST + 1):
        qualified = [r for r in panel.by_year[year]
                     if eligible(r, panel.minutes) and (r.player, year) in matched]
        ranks = sorted(qualified, key=lambda r: (-matched[r.player, year], -r.minutes, r.player))
        bpm_top = {r.player for r in top_players(panel, panel.ranks, year)}
        overlap[year] = {"matched_qualifiers": len(qualified),
                         "public_qualifiers": len(panel.ranks[year]),
                         "common_with_top_five_bpm": len(bpm_top & {r.player for r in ranks[:5]})}
    return {
        "dashboard_season_ends": [2010, LAST],
        "progression_season_ends": [2014, LAST],
        "dashboard_rows": len(dashboard),
        "matched_rows": len(matched),
        "unmatched_player_seasons_by_name": dict(sorted(unmatched.items())),
        "progression_rows": len(progression),
        "progression_comparisons": {
            "dashboard_minus_progression_lebron": spread(agreement),
            "age_disagreements_with_public_panel": age_disagreements,
            "minute_disagreements_over_5_with_public_panel": minute_disagreements,
        },
        "lebron_development_by_bpm_starting_level": change_table(changes, leb_delta),
        "older_lebron_by_prior_vorp": older_table(changes, leb_delta),
        "lebron_peak": peak_index(changes, leb_delta),
        "same_pairs_bpm_peak": peak_index(changes),
        "top_five_overlap_by_season": overlap,
    }


def threshold_sensitivity(seasons):
    result = {}
    for minutes in (750, 1500):
        panel = Panel(seasons, minutes)
        changes = list(panel.changes())
        stars = superstars(panel)["all_seasons"]
        result[minutes] = {
            "development_pairs": len(changes),
            "mean_delta_at_19_to_23": spread(delta(c) for c in changes if 19 <= c.start.age <= 23),
            "peak_age": peak_index(changes)["peak_age"],
            "older_by_prior_star_status": older_table(changes),
            "confirmed_first_top_five_per_season": stars["confirmed_first_count"],
            "new_or_returning_top_five_per_season": stars["new_or_returning_slots"],
        }
    return result


def analyze(inputs, previous_bbi):
    seasons = [Season(*r) for r in inputs["seasons"]]
    drafts = [DraftPick(*r) for r in inputs["draft"]]
    panel = Panel(seasons)
    check = bbi_check(panel)
    if check is None:
        check = previous_bbi
        print("Basketball Index caches unavailable. Using saved comparison if present.", file=sys.stderr)
    return {
        "schema_version": 1,
        "sources": SOURCES,
        "definitions": {
            "study_season_ends": [FIRST, LAST],
            "season_year": "Calendar year when the regular season ended.",
            "rate_impact": "Basketball Reference BPM per 100 possessions, full precision from the sort key.",
            "total_impact": "Basketball Reference VORP, including playing time.",
            "qualification": "At least the stated minutes in an 82-game season, prorated in shortened seasons.",
            "full_season_minutes_cut": MINUTES,
            "schedule_games_overrides": {1999: 50, 2012: 66, 2020: 72, 2021: 72},
            "starting_level": "BPM thirds among qualifiers of the same age in the same season.",
            "ranks": "League-wide among qualifiers. Break ties by minutes and then Basketball Reference ID.",
            "star_aging": "Prior (age minus one) season league top 25 in VORP among qualifiers.",
            "young_outcome": "First rank attainment within seven subsequent seasons, among those yet to attain it.",
            "draft_outcome": "Any attainment within seven seasons from draft, or from NBA debut for undrafted players.",
            "late_bloomer": "First top-25 season at age 27–30 in the fully followed age-23 NBA cohort.",
            "bust": "Pick 1–10, never top 50 and fewer than three qualifying seasons in the first seven seasons.",
        },
        "coverage": {
            "season_rows_by_year": {year: len(rows) for year, rows in sorted(panel.by_year.items())},
            "qualified_by_year": {year: len(p) for year, p in sorted(panel.ranks.items())},
            "draft_picks_by_year": dict(sorted(Counter(p.year for p in drafts).items())),
            "study_player_seasons": sum(r.year >= FIRST for r in seasons),
            "study_players": len({r.player for r in seasons if r.year >= FIRST}),
        },
        "development": development(panel),
        "star_formation": formation(panel, drafts),
        "superstars": superstars(panel),
        "late_bloomers_and_busts": cases(panel, drafts),
        "minutes_cut_sensitivity": threshold_sensitivity(seasons),
        "basketball_index": check,
        "public_inputs": inputs,
    }


def write_json(path, analysis):
    # Keep the tables readable and store each frozen input row on one line.
    inputs = analysis["public_inputs"]
    summary = {key: value for key, value in analysis.items() if key != "public_inputs"}
    with path.open("w", encoding="utf-8") as file:
        file.write(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False)[:-2])
        file.write(',\n  "public_inputs": {\n')
        for key in ("season_columns", "draft_columns"):
            file.write(f'    "{key}": {json.dumps(inputs[key])},\n')
        for key in ("seasons", "draft"):
            file.write(f'    "{key}": [\n')
            records = (json.dumps(row, ensure_ascii=False, allow_nan=False) for row in inputs[key])
            file.write(",\n".join(f"      {record}" for record in records))
            file.write("\n    ],\n" if key == "seasons" else "\n    ]\n")
        file.write("  }\n}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="Rebuild the public inputs from cached Basketball Reference pages.")
    parser.add_argument("--input", type=Path, default=ARTIFACT, help="Frozen evidence JSON. Defaults to the repo copy.")
    parser.add_argument("--out", type=Path, default=ARTIFACT, help="Write full evidence JSON here.")
    args = parser.parse_args()
    previous = json.loads(args.input.read_text(encoding="utf-8")) if args.input.is_file() else {}
    if not previous and not args.cache:
        parser.error("Provide the existing evidence JSON or --cache.")
    analysis = analyze(frozen_inputs(args.cache, previous), previous.get("basketball_index"))
    write_json(args.out, analysis)
    print(f"Wrote {args.out} with {analysis['coverage']['study_player_seasons']:,} study player-seasons.")


if __name__ == "__main__":
    main()
