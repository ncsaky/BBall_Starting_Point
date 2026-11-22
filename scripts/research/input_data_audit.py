#!/usr/bin/env python3
"""Read local player-input evidence and write aggregate diagnostics, without running the builder.

Run with PYTHONPATH=src. The ignored Basketball Index normalized shards and
recent cache must be present to reproduce the published audit.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
import gzip
from itertools import chain, combinations, pairwise
import json
import math
from pathlib import Path
import re
import statistics

from nba_gm_data import analyst_evidence as analysts
from nba_gm_data import bbi_evidence as bbi
from nba_gm_data import input_estimator as estimator
from nba_gm_data import physical_evidence as physical
from nba_gm_data import public_shot_evidence as shooting

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = "data/research/input_data_audit.json"
BBI = "Basketball Index Leaderboards Values"
MINUTES = 1000
MIN_PAIRS = 40
LOW_REPEAT = .30
DUPLICATE = .98
SPARSE = .80
NEGATIVE = -.20
CALIBRATION = "data/calibration/nba_2025_26_targets.json"


@dataclass
class Table:
    # Columns share a population even when a column omits some player rows.
    populations: dict = field(default_factory=lambda: defaultdict(set))
    columns: dict = field(default_factory=lambda: defaultdict(dict))
    minutes: dict = field(default_factory=lambda: defaultdict(dict))
    links: dict = field(default_factory=lambda: defaultdict(list))
    ranges: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)

    def add(self, season, player, values, minutes=None):
        self.populations[season].add(player)
        if minutes is not None:
            self.minutes[season][player] = max(minutes, self.minutes[season].get(player, 0))
        for column, value in values.items():
            self.columns[(season, column)][player] = estimator._number(value)


def read_json(root, name):
    with (root / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def json_array(stream):
    """Stream the normalized importer's compact top-level JSON arrays."""
    decoder = json.JSONDecoder()
    buffer = stream.read(1 << 20)
    if not buffer.startswith("["):
        raise ValueError("Expected a normalized JSON array")
    pos = 1
    while True:
        if len(buffer) - pos < 4096:
            buffer, pos = buffer[pos:] + stream.read(1 << 20), 0
        while pos < len(buffer) and buffer[pos] in ", \t\r\n":
            pos += 1
        if pos < len(buffer) and buffer[pos] == "]":
            return
        try:
            item, pos = decoder.raw_decode(buffer, pos)
        except json.JSONDecodeError:
            extra = stream.read(1 << 20)
            if not extra:
                raise
            buffer, pos = buffer[pos:] + extra, 0
            item, pos = decoder.raw_decode(buffer)
        yield item


def bbi_links(mapping):
    links = defaultdict(list)
    for iid, spec in mapping["inputs"].items():
        for metric in spec["metrics"]:
            name = metric["metric"]
            reason = ""
            if iid in bbi.MEASURED_INPUTS:
                reason = "uses measured formula instead"
            elif iid in bbi.SKIP_DISTRIBUTIONS:
                reason = "uses observed shot-location evidence instead"
            elif iid in {"P01", "P04"}:
                reason = "overlay skips native physical measurements"
            elif iid == "S07":
                reason = "overlay skips native free-throw percentage"
            elif spec["kind"] == "distribution" and not metric.get("outcome"):
                reason = "distribution metric has no mapped outcome"
            direct = {"input": iid, "route": "mapped overlay", "active": not reason,
                      "outcome": metric.get("outcome"), "direction": metric.get("direction", 1),
                      "strength": metric["strength"], "base_weight": bbi.STRENGTH[metric["strength"]]}
            if reason:
                direct["skip_reason"] = reason
            direct["exposure"] = list(bbi._exposure_names(metric))
            direct["volume"] = metric.get("volume")
            links[name].append(direct)
            for other in direct["exposure"]:
                links[other].append({**direct, "route": "exposure divisor", "of_metric": name})
            for other in (metric.get("volume") or {}).values():
                if isinstance(other, str):
                    links[other].append({**direct, "route": "sample-volume modifier", "of_metric": name})
    for name in bbi.T01_MEASURES:
        links[name].append({"input": "T01", "route": "measured per-touch formula", "active": True,
                            "base_weight": None, "weight_rule": "season weight × minutes / (minutes + 800)"})
    links["Stable True Usage%"].append({"input": "T08", "route": "measured involvement formula", "active": True,
                                       "base_weight": None, "weight_rule": "season weight × minutes / (minutes + 800)"})
    for name in physical.BBI_METRICS.values():
        links[name].append({"input": "P08", "route": "strength proxy candidate", "active": False,
                            "base_weight": 0, "skip_reason": "strength proxy fit is disabled by the builder"})
    for name, inputs in estimator.BBI_METRIC_INPUTS.items():
        for iid in inputs:
            links[name].append({"input": iid, "route": "confirmed-percentile estimator", "active": False,
                                "base_weight": None, "skip_reason": "retained Values display lacks confirmed percentile metadata"})
    return links


def percentage_range(name, definition):
    """Use only bounded measures implied by the label and provider gloss.

    Rates per attempt can exceed one in some domains. Keep FT/FGA and modeled
    deltas/ratings out. An upper bound does not establish the multiplier.
    """
    label = name.casefold()
    gloss = definition.casefold()
    if "%" in label and not any(x in label for x in ("vs", "difference", "plus", "true usage", "impact")):
        if not label.endswith("pct."):
            return (0, 100, "label suggests a bounded percentage; confirm display scale")
    if gloss.startswith(("percentage of ", "the percentage of ", "the percentage a player ", "the win percentage ", "the proportion of ")):
        if not any(x in label for x in ("impact", "relative", "above expected", "vs")):
            return (0, 100, "local metric glossary describes a bounded share")
    if name == "Height":
        return (60, 96, "plausibility screen in inches")
    if name == "Weight":
        return (120, 400, "plausibility screen in pounds")
    if name in bbi.T01_MEASURES or name == "Stable True Usage%":
        if name == "Potential Assists Per 100 Passes" or name == "Stable True Usage%":
            return (0, 100, "bounded share expected by measured formula")
    return None


def capture_values(root, mapping):
    folder = root / bbi.CACHE_DIR
    if not (folder / "normalized.json").is_file():
        raise FileNotFoundError(folder / "normalized.json")
    capture = Table(links=bbi_links(mapping))
    glossary = folder / "captures/bbi_metric_catalog_with_definitions.json"
    definitions = {}
    if glossary.exists():
        definitions = {r["metric"]: r.get("definition") or "" for r in read_json(root, glossary)["metrics"]}
    raw_table = defaultdict(dict)
    ingest = Counter()
    records = []
    for path in sorted((folder / "normalized").glob("*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            batch = json_array(stream)
            first = next(batch)
            if "(Values display;" not in (first.get("percentile_population") or ""):
                continue
            count = 0
            for row in chain((first,), batch):
                if row["dataset_kind"] != "observed" or row["season_type"] != "regular" or row["row_scope"] != "season_total":
                    raise ValueError(f"Unexpected row scope in {path}")
                count += 1
                name = row["metric_name"]
                season = row["season"]
                cid = row["canonical_player_id"]
                key = cid or f"name:{row['player_name_raw']}"
                minutes = row.get("minutes") or 0
                original = row["raw_value"]
                value = estimator._number(original) if isinstance(original, (int, float)) else None
                block = capture.columns[(season, name)]
                if key in block and block[key] != value:
                    ingest["conflicting_overlapping_values"] += 1
                # The builder retains the last finite value among overlapping batches.
                if value is not None or key not in block:
                    block[key] = value
                capture.populations[season].add(key)
                if minutes > capture.minutes[season].get(key, 0):
                    capture.minutes[season][key] = minutes
                if name in capture.links and season in bbi.SEASON_WEIGHTS and value is not None:
                    raw_table[(season, name)][key] = (value, minutes, cid)
                if name in capture.links:
                    source = estimator._number(row["source_text"]["raw_value"])
                    ingest["audited_capture_cells"] += 1
                    ingest["raw_text_value_mismatch"] += source != value
                    ingest["audited_non_numeric_nonblank"] += original is not None and value is None
            records.append({"name": path.name, "rows": count})
    if not records:
        raise ValueError("No observed Basketball Index Values captures found")
    for name in capture.links:
        if bounds := percentage_range(name, definitions.get(name, "")):
            capture.ranges[name] = bounds
    capture.context = {"batches": records, "row_checks": dict(ingest), "glossary_present": bool(definitions)}
    return capture, raw_table


def ranks(values):
    indexes = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(indexes):
        end = start + 1
        while end < len(indexes) and values[indexes[end]] == values[indexes[start]]:
            end += 1
        for i in range(start, end):
            result[indexes[i]] = (start + end - 1) / 2
        start = end
    return result


def correlation(x, y, rank=False):
    if len(x) < MIN_PAIRS or min(len(set(x)), len(set(y))) < 2:
        return None
    return statistics.correlation(ranks(x), ranks(y)) if rank else statistics.correlation(x, y)


def repeatability(table, column, seasons):
    results = []
    for earlier, later in pairwise(seasons):
        if not re.fullmatch(r"\d{4}-\d{2}", earlier) or not re.fullmatch(r"\d{4}-\d{2}", later):
            continue
        if int(later[:4]) != int(earlier[:4]) + 1:
            continue
        a, b = table.columns.get((earlier, column), {}), table.columns.get((later, column), {})
        ids = [key for key in sorted(a.keys() & b.keys()) if a[key] is not None and b[key] is not None
               and table.minutes[earlier].get(key, 0) >= MINUTES and table.minutes[later].get(key, 0) >= MINUTES]
        x, y = [a[key] for key in ids], [b[key] for key in ids]
        rho = correlation(x, y, rank=True)
        status = ("weak" if rho < LOW_REPEAT else "measured") if rho is not None else (
            "constant on matched cohort" if len(ids) >= MIN_PAIRS else "insufficient matched minutes")
        results.append({"seasons": [earlier, later], "paired_players": len(ids),
                        "spearman": rounded(rho), "status": status})
    return results


def rounded(value):
    return round(value, 6) if value is not None else None


def summary(table, season, column):
    pop = table.populations[season]
    values = {key: value for key, value in table.columns.get((season, column), {}).items() if value is not None}
    counts = Counter(values.values())
    n = len(pop)
    zero = counts[0]
    missing = n - len(values)
    common = max(counts.values(), default=0)
    flags = []
    for condition, flag in (
        (not values, "all_missing"),
        (len(counts) == 1, "constant"),
        (bool(values) and zero == len(values), "all_zero_observed"),
        (n and zero / n > SPARSE, "mostly_zero"),
        (n and missing / n > SPARSE, "mostly_missing"),
        (n and (zero + missing) / n > SPARSE, "mostly_zero_or_missing"),
        (n and len(counts) > 1 and common / n > SPARSE, "mostly_same_value"),
    ):
        if condition:
            flags.append(flag)
    outside = 0
    if bounds := table.ranges.get(column):
        outside = sum((bounds[0] is not None and value < bounds[0]) or (bounds[1] is not None and value > bounds[1]) for value in values.values())
        if outside:
            flags.append("outside_expected_range")
    regulars = {key for key in pop if table.minutes[season].get(key, 0) >= MINUTES}
    return {"players": n, "observed": len(values), "missing": missing, "zero": zero, "distinct": len(counts),
            "min": min(counts, default=None), "max": max(counts, default=None), "modal_count": common,
            "outside_expected_range": outside, "flags": flags,
            "rotation_players": len(regulars), "rotation_observed": len(regulars & values.keys()),
            "rotation_zero": sum(values.get(key) == 0 for key in regulars)}


sum_products = getattr(math, "sumprod", None)
if sum_products is None:
    def sum_products(x, y):
        return sum(a * b for a, b in zip(x, y))


def duplicates(table, season):
    """Exact equality or Pearson > .98 on pairwise-complete aligned player rows.

    Match one audited column with every captured numeric column, including
    unconsumed comparison columns. Complete column vectors are centered once
    per overlap so the pair loop can use the standard-library dot product.
    """
    columns = {column: vals for (s, column), vals in table.columns.items() if s == season}
    grouped = defaultdict(list)
    for name, values in columns.items():
        observed = frozenset(key for key, value in values.items() if value is not None)
        if len(observed) >= MIN_PAIRS and len({values[key] for key in observed}) > 1:
            grouped[observed].append(name)
    masks = list(grouped)

    @lru_cache(maxsize=4096)
    def vector(name, mask):
        # Sorting the same key set fixes alignment in both vectors.
        vals = tuple(columns[name][key] for key in sorted(mask))
        avg = statistics.fmean(vals)
        centered = tuple(v - avg for v in vals)
        norm = math.sqrt(sum_products(centered, centered))
        return vals, tuple(v / norm for v in centered) if norm else None, avg, norm

    results = []
    for i, left in enumerate(masks):
        for right in masks[i:]:
            if not any(name in table.links for name in grouped[left] + grouped[right]):
                continue
            mask = left & right
            if len(mask) < MIN_PAIRS:
                continue
            pairs = combinations(grouped[left], 2) if left == right else (
                (a, b) for a in grouped[left] for b in grouped[right])
            for a, b in pairs:
                if a not in table.links and b not in table.links:
                    continue
                va, za, mean_a, norm_a = vector(a, mask)
                vb, zb, mean_b, norm_b = vector(b, mask)
                if za is None or zb is None:
                    continue
                r = sum_products(za, zb)
                if r <= DUPLICATE:
                    continue
                exact = va == vb
                slope = norm_b / norm_a * r
                offset = mean_b - slope * mean_a
                results.append({"columns": [a, b], "paired_players": len(mask), "pearson": rounded(min(r, 1)),
                                "exact_on_overlap": exact, "identical_coverage": left == right,
                                "overlap_fraction": rounded(len(mask) / min(len(left), len(right))),
                                "slope_second_on_first": rounded(slope), "intercept": rounded(offset)})
    return results


def describe(table):
    return {
        "context": table.context,
        "seasons": {season: len(keys) for season, keys in sorted(table.populations.items())},
        "columns": {name: {"links": links, "expected_range": table.ranges.get(name),
                           "unit": table.units.get(name),
                           "seasons": {season: summary(table, season, name) for season in sorted(table.populations)},
                           "repeatability": repeatability(table, name, sorted(table.populations))}
                    for name, links in sorted(table.links.items())},
        "duplicates": {season: duplicates(table, season) for season in sorted(table.populations)},
    }


def link_fields(table, fields, inputs, rule, route="builder evidence"):
    for name in fields.split():
        for iid in sorted(set(inputs)):
            table.links[name].append({"input": iid, "route": route, "active": True,
                                      "base_weight": None, "weight_rule": rule})


def configure_crafted(table):
    # InputEstimator._prior_features aliases and the two prior crosswalks.
    related = {
        "three_volume": "3PAp75", "three_accuracy": "FG3_PCT 3P%",
        "ft_accuracy": "FT_PCT FT%", "close": "LT_06_PCT", "handler": "prbh_pct Prbh%",
        "post": "post_pct Post%", "roller": "pnrr_pct Pnrr%", "cut": "cut_pct Cut%",
        "movement": "offscreen_pct OffScreen% handoff_pct Handoff%", "spot_up": "spotup_pct SpotUp%",
        "transition": "transition_pct Transition%", "creation": "boxCreationEst", "passing": "passerRating",
        "security": "cTOVpct cTOV%", "foul_drawing": "FTr", "oreb": "ORBpct ORB%",
        "dreb": "DRBpct DRB%", "blocks": "BLKpct BLK%", "steals": "STLpct STL%",
        "disruption": "DEFLECTIONS DEFL", "foul_control": "rPF", "usage": "USGpct USG%",
        "workload": "MIN MPG minutes", "guard_assignment": "dPGpct dSGpct dPFpct dCpct",
        "big_assignment": "dPGpct dSGpct dPFpct dCpct",
    }
    prior = dict(estimator._STAT_PRIOR_LINKS)
    prior.update({iid: ("passing", "creation") for iid in estimator.DEFINITIONS if iid.startswith("F")})
    prior.update({iid: tuple({key for _, stat in choices.values() for key in stat})
                  for iid, choices in estimator._DISTRIBUTION_PRIOR_LINKS.items()})
    for feature, aliases in related.items():
        link_fields(table, aliases, [iid for iid, features in prior.items() if feature in features],
                    "0.40 residual budget, averaged over available related features; MP / (MP + 750)",
                    "related-stat prior")
    link_fields(table, "MP", [iid for iid, features in prior.items() if features],
                "MP / (MP + 750), or 0.20 when missing", "prior exposure")
    for family, ids in estimator.FAMILY_TECHNIQUES.items():
        channel, impact, iq, work = estimator.FAMILY_CONTEXT[family]
        if impact:
            names = "CraftedOPM COPM OLEBRON" if channel == "offense" else "CraftedDPM CDPM DLEBRON"
            link_fields(table, names, ids, f"context loading {impact:g}; precision 2 × MP / (MP + 750)",
                        "family context")
        if iq:
            link_fields(table, "BBallIQ", ids, f"context loading {iq:g}; precision 0.5 × MP / (MP + 750)",
                        "family context")
        if work:
            link_fields(table, "MIN MPG USGpct USG%", ids,
                        f"context loading {work:g}; precision 0.15 × MP / (MP + 750)", "family context")
        link_fields(table, "MP", ids, "MP / (MP + 750); requires positive MP", "family exposure")
    for names, targets, weight in (
        ("FG3_PCT 3P% FG3A 3PA GP", ("S01", "S02", "S03"), "0.5 × 3PA/game × GP; 250 prior attempts"),
        ("FT_PCT FT% FTA GP", ("S07",), "0.5 × FTA/game × GP; 100 prior attempts"),
        ("LT_06_PCT MP", ("S10",), "0.035 × MP; 180 prior opportunities"),
        ("prbh_ppp PrbhPPP prbh_pct Prbh% MP", ("S05",), "0.35 × n / (n + 150); n = 0.4 × MP × tag share"),
        ("iso_ppp IsoPPP iso_pct MP", ("S18",), "0.35 × n / (n + 150); n = 0.4 × MP × tag share"),
        ("post_ppp PostPPP post_pct Post% MP", ("S22",), "0.35 × n / (n + 150); n = 0.4 × MP × tag share"),
        ("threePAr 3PAr GP FGA FG3A 3PA FGAp75 3PAp75 MP", ("T02",),
         "estimated attempt exposure/(exposure + 100), fallback to career totals"),
        ("transition_pct Transition% MP", ("T05",), "0.65 × MP / (MP + 750)"),
        ("cut_pct Cut% MP", ("T09",), "0.65 × MP / (MP + 750)"),
        ("offscreen_pct OffScreen% handoff_pct Handoff% MP", ("T10",), "0.65 × MP / (MP + 750)"),
        ("USGpct USG% MP", ("T08",), "0.65 × MP / (MP + 750) before measured involvement"),
        ("ORBpct ORB% MP", ("T12",), "0.40 × MP / (MP + 750)"),
        ("FTr MP", ("T18",), "0.35 × MP / (MP + 750)"),
        ("spotup_pct SpotUp% offscreen_pct OffScreen% handoff_pct Handoff% prbh_pct Prbh% iso_pct Iso% MP",
         ("T01", "T03"), "0.35 or 0.45 × MP / (MP + 750) across available tags"),
        ("post_pct Post% MP", ("T01",), "0.35 or 0.45 × MP / (MP + 750) across available tags"),
        ("pnrr_pct Pnrr% MP", ("T11",), "0.45 × MP / (MP + 750); roll tag conditions involvement"),
    ):
        link_fields(table, names, targets, weight)
    families = {"F01": "", "F03": "prbh_pct Prbh%", "F05": "pnrr_pct Pnrr%",
                "F06": "prbh_pct Prbh%", "F08": "post_pct Post%", "F09": "transition_pct Transition%"}
    for family, gate in families.items():
        link_fields(table, "ASTp75 MP", [f"{family}.recognition"], "0.55 × effective MP / (effective MP + 750)")
        link_fields(table, "passerRating MP", [f"{family}.execution"], "0.55 × effective MP / (effective MP + 750)")
        link_fields(table, gate, [f"{family}.recognition", f"{family}.execution"], "binary eligibility above 0.02")
    for column in table.links:
        if column.endswith("_pct") and column.islower() or column in {
            "FG3_PCT", "FT_PCT", "3P%", "FT%", "Prbh%", "Post%", "Pnrr%", "Cut%", "Transition%", "Iso%", "SpotUp%", "OffScreen%", "Handoff%",
        }:
            table.ranges[column] = (0, 1, "fraction the builder expects")
        elif column in {"ORBpct", "ORB%", "DRBpct", "DRB%", "BLKpct", "BLK%", "STLpct", "STL%",
                        "dPGpct", "dSGpct", "dPFpct", "dCpct", "USGpct", "USG%", "3PAr", "threePAr", "BBallIQ"}:
            table.ranges[column] = (0, 100, "percentage points or IQ scale")
    table.ranges["LT_06_PCT"] = (0, 100, "builder accepts fraction or percentage points")
    table.units.update({"LT_06_PCT": "source-dependent fraction or percent points", "GP": "games",
                        "MP": "minutes in provider window", "FGA": "attempts per game", "FTA": "attempts per game",
                        "FG3A": "attempts per game", "3PA": "attempts per game", "FTr": "FTA/FGA × 100; can exceed 100"})


def career_and_outcomes(root):
    table = Table(context={"type": "ESPN regular-season totals; current universe cohort",
                           "builder_seasons": sorted(bbi.SEASON_WEIGHTS)})
    for columns, targets, weight in (
        ("minutes ftm fta", ("S07",), "season weights 1 / .60 / .36; 100 prior attempts"),
        ("minutes fg3m fg3a", ("S01", "S02", "S03"), "season weights 1 / .60 / .36; 250 prior attempts"),
        ("fga fg3a", ("T02",), "newest valid 3PA/FGA, 1 / .60 / .36 recency; 100 prior attempts"),
        ("minutes games", ("P11", "P12"), "2025-26 workload fallback, 0.40 related-stat residual budget, P12 scaled by .55"),
        ("games", [i for i in estimator.DEFINITIONS
                                                              if estimator.DEFINITIONS[i]["kind"] == "grade"],
         "binary NBA veteran/rookie eligibility for 2026 draft class"),
        ("minutes assists", ("F01.recognition", "F03.recognition", "F05.recognition", "F06.recognition",
                             "F08.recognition", "F09.recognition"), "assist fallback, 0.55 × MP / (MP + 750)"),
    ):
        link_fields(table, columns, targets, weight)
    # The builder reads these into career totals, but the current input estimator
    # does not consume them after accumulation.
    for name in ("fgm", "turnovers"):
        table.links[name] = [{"input": None, "route": "read but unused in current estimate", "active": False,
                              "base_weight": 0}]
    outcomes = defaultdict(dict)
    row_counts = Counter()
    for doc in read_json(root, estimator.CAREER_PATH)["players"].values():
        player = estimator._normalize(doc["name"])
        by_season = defaultdict(list)
        for row in doc["seasons"]:
            by_season[row["season"]].append(row)
        for season, rows in by_season.items():
            if len(rows) != 1:
                row_counts["duplicate_player_seasons_excluded"] += 1
                continue
            row = rows[0]
            table.add(season, player, row, row.get("minutes") or 0)
            for makes, attempts, label, minimum in (
                ("fgm", "fga", "field goal accuracy", 100), ("fg3m", "fg3a", "three-point accuracy", 80),
                ("ftm", "fta", "free-throw accuracy", 40), ("fg3a", "fga", "three-point attempt share", 100),
            ):
                m, n = (estimator._get(row, key) for key in (makes, attempts))
                if m is not None and n is not None and n >= minimum and 0 <= m <= n:
                    outcomes[(season, label)][player] = m / n
                if m is not None and n is not None and not 0 <= m <= n:
                    row_counts[f"{makes}>{attempts} or negative"] += 1
            minutes = row.get("minutes") or 0
            for key, label in (("fta", "free-throw attempts per minute"), ("assists", "assists per minute"),
                               ("blocks", "blocks per minute"), ("steals", "steals per minute"),
                               ("rebounds", "rebounds per minute"), ("turnovers", "turnovers per minute")):
                value = estimator._get(row, key)
                if minutes > 0 and value is not None and value >= 0:
                    outcomes[(season, label)][player] = value / minutes
            fta, fga = estimator._get(row, "fta"), estimator._get(row, "fga")
            if fta is not None and fga is not None and fga >= 100:
                outcomes[(season, "free-throw attempts per field-goal attempt")][player] = fta / fga
            if row.get("games") is not None and row["games"] > 82:
                row_counts["games above 82 (trades can explain)"] += 1
    table.ranges.update({name: (0, math.inf, "nonnegative totals") for name in table.links})
    table.ranges["minutes"] = (0, 4500, "generous NBA season-total minutes screen")
    # Avoid non-finite metadata in the strict JSON.
    table.ranges = {name: (low, None if math.isinf(high) else high, note)
                    for name, (low, high, note) in table.ranges.items()}
    table.context["checks"] = dict(row_counts)
    return table, outcomes


def load_other_sources(root, universe):
    career, outcomes = career_and_outcomes(root)
    sources = {estimator.CAREER_PATH: career}
    for path, key, date in ((estimator.SKILL_PATH, "players", "2026-03-11"),
                            (estimator.STATS_PATH, "rows", "2026-04-05")):
        table = Table(context={"snapshot_date": date, "same-season snapshot; no independent year pair": True})
        configure_crafted(table)
        rows = read_json(root, path)[key]
        names = Counter(estimator._normalize(row.get("name") or row.get("player") or "") for row in rows)
        for row in rows:
            name = estimator._normalize(row.get("name") or row.get("player") or "")
            if name and names[name] == 1:
                table.add("2025-26", name, row, estimator._get(row, "MP"))
        table.context["rows_excluded_for_ambiguous_or_empty_join"] = sum(
            n for name, n in names.items() if not name or n != 1)
        table.context["aliases_absent_from_this_snapshot"] = sorted(set(table.links) - set().union(*(row.keys() for row in rows)))
        sources[path] = table

    bref = Table(context={"row_scope": "Basketball-Reference regular-season player totals"})
    link_fields(bref, "fga pct_fga_00_03 pct_fga_dunk", ("S12", "P10"),
                "S12 weighted close attempts/(close attempts + 60); P10 fitted proxy when it improves combine prediction")
    for name in ("minutes", "dunks"):
        bref.links[name] = [{"input": None, "route": "audit exposure" if name == "minutes" else "provenance only",
                            "active": False, "base_weight": 0}]
    invalid_bref = Counter()
    for doc in read_json(root, shooting.DATA_FILE)["players"].values():
        name = estimator._normalize(doc["name"])
        for season, row in doc["seasons"].items():
            if doc["name"] == "Player":
                invalid_bref["embedded header rows"] += 1
                continue
            bref.add(season, name, row, row.get("minutes"))
            near, dunk = row.get("pct_fga_00_03"), row.get("pct_fga_dunk")
            if near is not None and dunk is not None and dunk > near:
                invalid_bref["dunk attempt share exceeds close share"] += 1
            if row.get("fga") is not None and row["fga"] >= 100 and row.get("fg_pct_00_03") is not None:
                outcomes[(season, "field goal accuracy within 3 feet")][name] = row["fg_pct_00_03"]
    bref.context["checks"] = dict(invalid_bref)
    bref.ranges.update({name: (0, 1, "attempt fraction") for name in ("pct_fga_00_03", "pct_fga_dunk")})
    sources[shooting.DATA_FILE] = bref

    combine = Table(context={"type": "NBA draft cohorts, one test window per player; no season-to-season panel"})
    for field_name, iid in physical.TEST.items():
        link_fields(combine, field_name, [iid], "inverse variance blend based on test noise and time since draft")
    combine.ranges = {"bench_reps_185": (0, 40, "185-lb reps, plausibility screen"),
                      "standing_vertical_in": (12, 50, "inches, plausibility screen")}
    for index, row in enumerate(read_json(root, physical.COMBINE_FILE)["players"]):
        combine.add(str(row["year"]), str(index), row)
    matched = physical.combine_matches(universe, root)
    combine.context["current_universe_combine_matches"] = len(matched)
    combine.context["matched_with_test"] = {
        test: sum(row.get(test) is not None for row in matched.values()) for test in physical.TEST.values()}
    sources[physical.COMBINE_FILE] = combine

    targets = Table(context={"type": "2025-26 calibration player table, 500+ minutes for proxy"})
    link_fields(targets, "blocks_per36 orb_pct minutes", ["P10"],
                "fitted proxy, used only when out-of-fold prediction improves versus size model")
    targets.ranges = {"orb_pct": (0, 100, "percentage points"), "blocks_per36": (0, None, "nonnegative per 36 minutes")}
    for pid, row in read_json(root, CALIBRATION)["players"].items():
        targets.add("2025-26", pid, row, row.get("minutes"))
    sources[CALIBRATION] = targets

    zones = Table(context={"type": "32 hand-picked StatMuse shooting profiles; bin columns are summarized per player",
                           "bin_fields": {"bins.x": "feet from center along x", "bins.y": "feet from center along y",
                                          "bins.zone": "integer 1–15", "bins.count": "attempt count in that bin"}})
    link_fields(zones, "attempts bins.x bins.y bins.zone bins.count", ["T02"],
                "0.6 × valid 2024–25 shot counts; 100 prior attempts")
    data = read_json(root, estimator.SHOT_ZONE_PATH)
    reconciled = 0
    invalid = Counter()
    for doc in data["profiles"]:
        bins = doc.get("bins", [])
        coords = [list(col) for col in zip(*(row[:4] for row in bins if isinstance(row, list) and len(row) >= 4))]
        values = {"attempts": doc.get("attempts")}
        for label, cells in zip(("x", "y", "zone", "count"), coords):
            # A per-player count of present bins, so a containing array is not mistaken for an as-delivered scalar.
            values[f"bins.{label}"] = len(cells)
        if len(coords) == 4 and len(coords[0]) == len(bins):
            for x, y, z, n in zip(*coords):
                if None in (x, y, z, n) or z not in range(1, 16) or n < 0:
                    invalid["invalid_bin_rows"] += 1
            reconciled += sum(coords[3]) == doc.get("attempts")
        zones.add(data["season"], estimator._normalize(doc["name"]), values)
    zones.context.update({"profiles_reconciled": reconciled, "checks": dict(invalid)})
    sources[estimator.SHOT_ZONE_PATH] = zones
    return sources, outcomes


def universe_and_judgments(root, universe):
    table = Table(context={"type": "2026 offseason universe, roles and body measurements; a single roster snapshot"})
    links = dict(estimator._LEGACY_PRIOR_LINKS)
    links.update({iid: ("passing_reads",) for iid in estimator.DEFINITIONS if iid.startswith("F")})
    links.update({iid: tuple({key for legacy, _ in choices.values() for key in legacy})
                  for iid, choices in estimator._DISTRIBUTION_PRIOR_LINKS.items()})
    traits = estimator._trait_index(universe["traits"])
    for field_name in sorted({key for fields in links.values() for key in fields}):
        link_fields(table, f"traits.{field_name}", [iid for iid, keys in links.items() if field_name in keys],
                    "0.60 bounded residual budget averaged across available legacy traits", "legacy prior")
    link_fields(table, "height_inches", ("P01", "P02", "P03", "P08", "P10", "S12"), "native inches × 2.54 and downstream body regressors")
    link_fields(table, "wingspan_inches", ("P02", "P03", "P08", "P10", "S12"), "native inches × 2.54 and downstream body regressors")
    link_fields(table, "weight_lbs", ("P04", "P08", "P10", "S12"), "native pounds × 0.45359237 and downstream body regressors")
    link_fields(table, "height_inches wingspan_inches weight_lbs age",
                ("P05", "P06", "P07", "P08", "P09", "P10", "P11", "P12", "S12", "S13", "S21", "S27", "S29",
                 "S30", "S31", "S32", "S34", "S36", "S37"), "0.25 residual budget; geometry and age condition priors")
    link_fields(table, "birthdate draft_year age", ("P08", "P10"), "combine matching, age correction and time-since-test uncertainty")
    link_fields(table, "position", list(estimator.DEFINITIONS), "position-specific prior or eligibility; no independent scalar weight")
    role_inputs = ("S01", "S02", "S03", "S04", "S05", "S06", "S09", "S16", "S17", "S18", "S19", "S20")
    link_fields(table, "primary_off_role secondary_off_role archetype",
                (*role_inputs, *(key for key in estimator.DEFINITIONS if key.startswith("F"))), "position/role shifts the fixed prior")
    link_fields(table, "primary_def_role", ("S30", "S33", "S35", "S36", "S37", "S38", "S39", "S40", "P07", "T15"),
                "0.20 role residual budget")
    link_fields(table, "draft_year draft_status espn_player_id", list(estimator.DEFINITIONS),
                "identity/rookie branching; no scalar weight", "join or eligibility")
    table.ranges = {"height_inches": (60, 96, "plausibility screen in inches"),
                    "wingspan_inches": (60, 105, "plausibility screen in inches"),
                    "weight_lbs": (120, 400, "plausibility screen in pounds"), "age": (16, 55, "age plausibility screen")}
    categorical = {"birthdate", "position", "primary_off_role", "secondary_off_role", "primary_def_role",
                   "archetype", "draft_status", "espn_player_id"}
    for player in universe["players"]:
        pid = player["id"]
        numeric = {k: v for k, v in player.items() if k not in categorical}
        values = {**numeric, **{f"traits.{k}": v for k, v in traits.get(pid, {}).items()}}
        table.add("2026-27", pid, values)
    table.context["categorical_fields"] = {name: {
        "links": table.links.pop(name),
        "missing": sum(player.get(name) in (None, "") for player in universe["players"]),
        "distinct_nonempty": len({player[name] for player in universe["players"] if player.get(name) not in (None, "")}),
    } for name in sorted(categorical)}
    packet_summary = defaultdict(lambda: defaultdict(set))
    for (pid, iid), record in estimator.load_reference_cells(root).items():
        value = record["record"].get("value", {})
        if "grade" in value and estimator.DEFINITIONS[iid]["kind"] == "grade" and iid != "S07":
            packet_summary[record["packet"]][iid].add(pid)
    claims = defaultdict(dict)
    claim_checks = Counter()
    valid_ids = {p["id"] for p in universe["players"]}
    for claim in analysts.load_claims(root):
        pid = claim.get("player_id")
        eligible = [iid for iid in analysts.claim_inputs(claim) if analysts.applicable_input(iid)]
        if claim.get("not_applied") or pid not in valid_ids or claim.get("level") not in analysts.LEVELS or not eligible:
            claim_checks["recorded_or_invalid"] += 1
            continue
        for iid in eligible:
            claims[iid].setdefault(pid, []).append(analysts.claim_weight(claim))
    return table, {
        "expert_packet_grade": {"weight": .35, "paired_seasons": None,
                                "players_per_input_by_packet": {path: {iid: len(players) for iid, players in cols.items()}
                                                                for path, cols in sorted(packet_summary.items())},
                                "scope": "Newest eligible estimated grade; packet revision dates are not seasons. S07 and non-grade cells skipped."},
        "analyst_claims": {"path": analysts.CLAIMS_FILE, "checks": dict(claim_checks),
                           "paired_seasons": None, "fields": ["level", "support", "context", "episode", "notes",
                                                               "not_applied", "player_id", "inputs"],
                           "by_input": {iid: {"players": len(people), "weights": sorted(w for weights in people.values() for w in weights)}
                                        for iid, people in sorted(claims.items())},
                           "weight": "sum of usable claim weights / (that sum + 0.60 measured or 0.20 prior), if disagreement wins",
                           "scope": "Qualitative judgments; no numeric season panel or independent same-column validation."},
    }


# The outcome is higher for more of the intended input, except security,
# whose validation outcome is turnover frequency and therefore lower is better.
OUTCOME_INPUTS = {
    "S01": ("three-point accuracy", 1, "overall 3P%, overlaps but does not isolate catch-and-shoot"),
    "S02": ("three-point accuracy", 1, "overall 3P%, overlaps but does not isolate pull-ups"),
    "S03": ("three-point accuracy", 1, "overall 3P%, overlaps but does not isolate movement"),
    "S07": ("free-throw accuracy", 1, "direct outcome; may share underlying shots"),
    "S09": ("three-point accuracy", 1, "overall 3P%, role and shot distance confound"),
    "S10": ("field goal accuracy within 3 feet", 1, "raw accuracy mixes dunks, layups and shot quality"),
    "S11": ("field goal accuracy", 1, "broad proxy only; floater attempts not isolated"),
    "S17": ("turnovers per finished box-score play", -1, "includes all box-score turnovers, no live-ball breakdown"),
    "S24": ("free-throw attempts per field-goal attempt", 1, "broad proxy, mixes shot types, bonus and whistle"),
    "S29": ("offensive rebound percentage", 1, "role, body size and team strategy confound"),
    "S30": ("defensive rebound percentage", 1, "role, teammates and scheme confound"),
    "S37": ("blocks per minute", 1, "secondary outcome; low block rate can coexist with good contests"),
    "S42": ("steals per minute", 1, "also reflects gambles and assignment"),
    "S43": ("steals per minute", 1, "passing-lane steals are a subset"),
    "T02": ("three-point attempt share", 1, "direct share when the mapped outcome is three"),
    "T18": ("free-throw attempts per field-goal attempt", 1, "foul outcome is not a contact-opportunity denominator"),
}
# Match the source's exposure and unit when a comparison supports it.
OUTCOME_METRICS = {
    "Free Throw Percentage": ("free-throw accuracy", 1, "direct outcome; may share underlying shots", 100),
    "3PT Attempt Rate": ("three-point attempt share", 1, "direct share", 100),
    "Rim FG%": ("field goal accuracy within 3 feet", 1, "rim definitions may differ", 100),
}


def direction_checks(sources, capture, outcomes, raw_table, universe):
    names = {p["id"]: estimator._normalize(p["name"]) for p in universe["players"]}
    bad_names = {name for name, count in Counter(names.values()).items() if count > 1}
    recent = sorted(bbi.SEASON_WEIGHTS)
    results = []

    @lru_cache(maxsize=None)
    def benchmark_block(season, benchmark):
        return outcomes.get((season, benchmark), {})

    def check(source, metric, iid, rows, season, benchmark, direction, expected, note, multiplier=None):
        target = benchmark_block(season, benchmark)
        matches = [(v, target[player]) for player, v in rows.items() if player in target and player not in bad_names]
        raw, actual = map(list, zip(*matches)) if matches else ([], [])
        signed = direction * expected
        rho = correlation(raw, actual, rank=True)
        status = "insufficient or constant"
        if rho is not None:
            status = "possible direction mismatch" if signed * rho < NEGATIVE else "tested"
        result = {"source": source, "column": metric, "input": iid, "season": season,
                  "benchmark": benchmark, "benchmark_limit": note, "players": len(matches),
                  "spearman_raw": rounded(rho), "spearman_oriented": rounded(None if rho is None else signed * rho),
                  "status": status}
        if multiplier and rho is not None:
            nonzero = [x / y for x, y in matches if y > 0 and x > 0]
            ratio = statistics.median(nonzero) if nonzero else None
            result.update({"expected_multiplier": multiplier, "observed_median_multiplier": rounded(ratio)})
            if rho > .90 and ratio and .85 <= ratio / (multiplier / 100) <= 1.15:
                result["unit_check"] = "suspected fraction in percentage-point field"
            elif rho > .90 and ratio and .85 <= ratio / (multiplier * 100) <= 1.15:
                result["unit_check"] = "suspected percentage points in fraction field"
        results.append(result)

    for metric, links in sorted(capture.links.items()):
        for link in links:
            iid = link["input"]
            if iid not in OUTCOME_INPUTS or link["route"] != "mapped overlay":
                continue
            if iid == "T02" and (link.get("outcome") != "three" or metric not in OUTCOME_METRICS):
                continue
            benchmark, expected, note = OUTCOME_INPUTS[iid]
            multiplier = None
            if metric in OUTCOME_METRICS:
                benchmark, expected, note, multiplier = OUTCOME_METRICS[metric]
            for season in recent:
                values = bbi._metric_values(raw_table, season, {"metric": metric, "per_sum": link["exposure"]})
                block = {names[cid]: value for value, minutes, cid in values.values()
                         if cid in names and minutes >= MINUTES}
                check(BBI, metric, iid, block, season, benchmark, link["direction"], expected, note, multiplier)

    for path in (estimator.STATS_PATH, estimator.SKILL_PATH):
        table = sources[path]
        season = "2025-26"
        for metric, iid, benchmark, multiplier in (
            ("FG3_PCT", "S01", "three-point accuracy", 1), ("3P%", "S01", "three-point accuracy", 1),
            ("FT_PCT", "S07", "free-throw accuracy", 1), ("FT%", "S07", "free-throw accuracy", 1),
            ("threePAr", "T02", "three-point attempt share", 100), ("3PAr", "T02", "three-point attempt share", 100),
            ("FTr", "T18", "free-throw attempts per field-goal attempt", 100),
            ("cTOVpct", "S17", "turnovers per finished box-score play", 100),
            ("passerRating", "F01.execution", "assists per minute", None),
        ):
            block = {pid: v for pid, v in table.columns.get((season, metric), {}).items()
                     if v is not None and table.minutes[season].get(pid, 0) >= MINUTES}
            check(path, metric, iid, block, season, benchmark, 1, 1,
                  "full-season ESPN comparison against an earlier snapshot; turnover and passer models use different definitions",
                  multiplier)
    return results


def add_outcomes(outcomes, universe, root):
    for doc in read_json(root, estimator.CAREER_PATH)["players"].values():
        key = estimator._normalize(doc["name"])
        for row in doc["seasons"]:
            fga, fta, tov = (estimator._get(row, k) for k in ("fga", "fta", "turnovers"))
            if None not in (fga, fta, tov) and fga >= 100:
                outcomes[(row["season"], "turnovers per finished box-score play")][key] = tov / (fga + .44 * fta + tov)
    names = {p["id"]: estimator._normalize(p["name"]) for p in universe["players"]}
    for pid, row in read_json(root, CALIBRATION)["players"].items():
        if pid in names:
            for key, label in (("orb_pct", "offensive rebound percentage"), ("drb_pct", "defensive rebound percentage")):
                if row.get(key) is not None:
                    outcomes[("2025-26", label)][names[pid]] = row[key]


def overlay_impact(capture, raw_table, universe):
    universe_ids = {p["id"] for p in universe["players"]}
    measured_mix = {}
    for season in bbi.SEASON_WEIGHTS:
        fields = [raw_table.get((season, name), {}) for name in bbi.T01_MEASURES]
        measured_mix[season] = {cid for pid, (touch, minutes, cid) in fields[0].items()
                                if cid in universe_ids and touch > 0 and minutes > 0
                                and all(pid in other for other in fields[1:])
                                and fields[-1][pid][0] > 0}
    for name, links in sorted(capture.links.items()):
        for link in links:
            if not link["active"]:
                continue
            route = link["route"]
            by_season = {}
            if route in {"mapped overlay", "exposure divisor", "sample-volume modifier"}:
                spec = {"metric": link.get("of_metric", name), "per_sum": link["exposure"],
                        "direction": link["direction"]}
                r = bbi.metric_reliability(raw_table, spec)
                scale = bbi.reliability_factor(r)
                link["builder_spearman_mean_untied"] = rounded(r)
                link["builder_repeatability_multiplier"] = rounded(scale)
                link["weight_before_player_volume"] = rounded(scale * link["base_weight"])
                for season in bbi.SEASON_WEIGHTS:
                    values = bbi._metric_values(raw_table, season, spec)
                    if scale and bbi._percentiles(values, link["direction"]):
                        by_season[season] = {cid for pid, (_, minutes, cid) in values.items()
                                             if cid in universe_ids and minutes > 0 and
                                             (route == "mapped overlay" or pid in raw_table.get((season, name), {}))}
            else:
                for season in bbi.SEASON_WEIGHTS:
                    if route == "measured per-touch formula":
                        by_season[season] = measured_mix[season]
                    else:
                        by_season[season] = {cid for v, minutes, cid in raw_table.get((season, name), {}).values()
                                             if v > 0 and minutes > 0 and cid in universe_ids}
            link["build_players_by_season"] = {s: len(by_season.get(s, ())) for s in sorted(bbi.SEASON_WEIGHTS)}
            link["unique_build_players"] = len(set().union(*by_season.values()))


def cache_parity(root, raw_table):
    folder = root / bbi.CACHE_DIR
    with gzip.open(folder / bbi.RECENT_CACHE, "rt", encoding="utf-8") as stream:
        cache = json.load(stream)
    source = folder / "normalized.json"
    stamp = f"{source.stat().st_size}:{int(source.stat().st_mtime)}"
    keys = {name for _, name in raw_table}
    packed = {tuple(key.split("|", 1)): {pid: tuple(cell) for pid, cell in block.items()}
              for key, block in cache["table"].items() if key.split("|", 1)[1] in keys}
    mismatches = sorted("|".join(key) for key in raw_table.keys() | packed.keys()
                        if raw_table.get(key) != packed.get(key))
    return {"stamp_matches_builder": stamp == cache["stamp"], "column_seasons_compared": len(packed),
            "mismatching_column_seasons": mismatches}


def pair_scale(item):
    if item["pearson"] < .999:
        return None
    slope = item["slope_second_on_first"]
    scales = {100: "100× fraction/percentage-point scale",
              75: "75× per-possession/per-75 scale", 36: "36× per-minute/per-36 scale",
              4 / 3: "100/75 per-75/per-100 scale", 100 / 36: "100/36 rate conversion",
              2.54: "inches/cm scale", 2.20462262: "kg/lbs scale"}
    if not slope:
        return None
    magnitude = max(slope, 1 / slope)
    for factor, label in scales.items():
        if abs(magnitude / factor - 1) < .015:
            return label
    return None


REMEDIES = {
    "all_missing": "Check capture availability and aliases. Use a verified replacement or retain the input's prior.",
    "constant": "Check the original value and exposure. Give a constant no weight until the source varies meaningfully.",
    "mostly_zero_or_missing": "Check zeros against event exposure and capture precision. Treat missing observations separately and shrink sparse counts.",
    "mostly_same_value": "Check display precision or sentinels. Down-weight until the source distinguishes players with comparable exposure.",
    "outside_expected_range": "Verify the documented units and raw catch. Correct the conversion or exclude invalid observations before grading.",
    "weak_repeatability": "Confirm consistent capture and adequate opportunities. Shrink noisy evidence or replace it with a better tracked measure.",
    "direction": "Verify definition, opportunity mix and expected sign using matched event-level outcomes before changing the mapping.",
    "duplicate": "Check whether both columns are the same underlying evidence. Keep one vote or explicitly share weight for overlapping metrics.",
    "scale": "Reconcile provider units with corresponding denominators before transforming data or changing weights.",
}
SPECIFIC_FIXES = {
    "Drive Foul Rate": "Retain one drive-foul rate. Verify independently counted fouled drives / drives before changing foul-drawing craft.",
    "Stable Shooting Fouls Drawn Per 75": "Check the field against official shooting-foul play-by-play and possession exposure, then restore only if it has valid variation.",
    "Movement Distance Rating": "Get unrounded offensive tracking distance per possession, then adjust for role and pace. Keep the effort-allocation preference prior until measured.",
}


def collect_problems(sources, described, directions):
    """One issue row per source column and type, with affected counts by season."""
    results = []
    for source, audit in described.items():
        table = sources[source]
        for name, col in audit["columns"].items():
            links = col["links"]
            per_type = defaultdict(dict)
            for season, info in col["seasons"].items():
                flags = info["flags"]
                if source in (estimator.SKILL_PATH, estimator.STATS_PATH) and name in table.context["aliases_absent_from_this_snapshot"]:
                    continue
                if "all_missing" in flags:
                    per_type["all_missing"][season] = info["players"]
                elif "constant" in flags:
                    per_type["constant"][season] = info["observed"]
                elif "mostly_zero_or_missing" in flags:
                    per_type["mostly_zero_or_missing"][season] = info["zero"] + info["missing"]
                elif "mostly_same_value" in flags:
                    per_type["mostly_same_value"][season] = info["modal_count"]
                if "outside_expected_range" in flags:
                    per_type["outside_expected_range"][season] = info["outside_expected_range"]
            by_pair = {"/".join(item["seasons"]): item for item in col["repeatability"] if item["status"] == "weak"}
            if by_pair:
                per_type["weak_repeatability"] = {pair: result["paired_players"] for pair, result in by_pair.items()}
            linked = [link for link in links if link["input"] and link["active"]]
            for problem, season_counts in per_type.items():
                result = {"type": problem, "source": source, "columns": [name], "links": links,
                          "affected_rows_by_season_or_pair": season_counts, "suggested_fix": SPECIFIC_FIXES.get(name, REMEDIES[problem])}
                if problem == "weak_repeatability":
                    result["repeatability_by_pair"] = {pair: item["spearman"] for pair, item in by_pair.items()}
                result["impact_score"] = impact_score(result, linked)
                results.append(result)
        duplicate_groups = defaultdict(dict)
        for season, pairs in audit["duplicates"].items():
            for pair in pairs:
                a, b = pair["columns"]
                key = tuple(sorted((a, b)))
                duplicate_groups[key][season] = pair
        for names, seasons in duplicate_groups.items():
            active = [l for name in names for l in table.links.get(name, []) if l["active"] and l["input"]]
            if not active:
                continue
            scales = {season: label for season, item in seasons.items() if (label := pair_scale(item))}
            shared = {l["input"] for l in table.links.get(names[0], []) if l["active"]} & {
                l["input"] for l in table.links.get(names[1], []) if l["active"]}
            result = {"type": "scale" if scales else "duplicate", "source": source, "columns": list(names),
                      "links_by_column": {name: table.links.get(name, []) for name in names},
                      "affected_rows_by_season_or_pair": {s: item["paired_players"] for s, item in seasons.items()},
                      "duplicate_details": seasons, "scale_candidates": scales, "inputs_fed_by_both_columns": sorted(shared),
                      "suggested_fix": next((SPECIFIC_FIXES[name] for name in names if name in SPECIFIC_FIXES), REMEDIES["scale" if scales else "duplicate"])}
            result["impact_score"] = impact_score(result, active) * (1 if shared else .3)
            results.append(result)
    by_direction = defaultdict(dict)
    for result in directions:
        if result["status"] == "possible direction mismatch" or result.get("unit_check"):
            key = result["source"], result["column"], result["input"], ("scale" if result.get("unit_check") else "direction")
            by_direction[key][result["season"]] = result
    for (source, name, iid, problem), seasons in by_direction.items():
        links = [link for link in sources[source].links[name] if link["input"] == iid]
        result = {"type": problem, "source": source, "columns": [name], "links": links,
                  "affected_rows_by_season_or_pair": {s: row["players"] for s, row in seasons.items()},
                  "outcome_checks": seasons, "suggested_fix": REMEDIES[problem]}
        result["impact_score"] = impact_score(result, [link for link in links if link["active"]])
        results.append(result)
    return sorted(results, key=lambda item: (-item["impact_score"], item["type"], item["source"], item["columns"]))


def impact_score(issue, links):
    if not links:
        return 0
    affected = issue["affected_rows_by_season_or_pair"]
    n = max((v for key, v in affected.items() if any(s in key for s in bbi.SEASON_WEIGHTS)), default=0)
    if issue["source"] == BBI:
        n = min(n, max((l.get("unique_build_players", 0) for l in links), default=0)) if issue["type"] != "all_missing" else n
    else:
        n = n or max(affected.values(), default=0)
    weight = max((l["base_weight"] if l.get("base_weight") is not None else .35 for l in links), default=0)
    severity = {"constant": 1, "all_missing": .35, "mostly_zero_or_missing": .8, "mostly_same_value": .65,
                "outside_expected_range": .8, "duplicate": .65, "scale": .55,
                "weak_repeatability": .20, "direction": .25}[issue["type"]]
    return round(n * weight * severity, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    mapping = bbi.load_mapping(args.root)
    universe = read_json(args.root, estimator.UNIVERSE_PATH)
    sources, outcomes = load_other_sources(args.root, universe)
    sources[estimator.UNIVERSE_PATH], judgments = universe_and_judgments(args.root, universe)
    capture, raw_table = capture_values(args.root, mapping)
    sources[BBI] = capture
    capture.context["builder_cache_parity"] = cache_parity(args.root, raw_table)
    overlay_impact(capture, raw_table, universe)
    add_outcomes(outcomes, universe, args.root)
    directions = direction_checks(sources, capture, outcomes, raw_table, universe)
    described = {name: describe(table) for name, table in sources.items()}
    report = {"mapping_version": mapping["version"], "nonpanel_evidence": judgments,
              "settings": {"build_season_weights": bbi.SEASON_WEIGHTS, "minimum_minutes_each_season": MINUTES,
                           "minimum_paired_players": MIN_PAIRS, "weak_repeatability_below": LOW_REPEAT,
                           "sparse_fraction_above": SPARSE, "near_duplicate_pearson_above": DUPLICATE,
                           "direction_flag_oriented_spearman_below": NEGATIVE},
              "inputs": {iid: definition["name"] for iid, definition in estimator.DEFINITIONS.items()},
              "sources": described, "direction_checks": directions,
              "ranked_problems": collect_problems(sources, described, directions)}
    output = args.output or args.root / OUTPUT
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
