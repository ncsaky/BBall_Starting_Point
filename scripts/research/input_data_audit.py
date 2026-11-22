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
from itertools import combinations, pairwise
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
            for row in chain_first(first, batch):
                if row["dataset_kind"] != "observed" or row["season_type"] != "regular" or row["row_scope"] != "season_total":
                    raise ValueError(f"Unexpected row scope in {path}")
                count += 1
                name = row["metric_name"]
                season = row["season"]
                cid = row["canonical_player_id"]
                key = cid or f"name:{row['player_name_raw']}"
                minutes = row.get("minutes") or 0
                value = row["raw_value"]
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
            records.append({"name": path.name, "rows": count})
    if not records:
        raise ValueError("No observed Basketball Index Values captures found")
    for name in capture.links:
        if bounds := percentage_range(name, definitions.get(name, "")):
            capture.ranges[name] = bounds
    capture.context = {"batches": records, "row_checks": dict(ingest), "glossary_present": bool(definitions)}
    return capture, raw_table


def chain_first(first, rest):
    yield first
    yield from rest


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
        outside = sum(not bounds[0] <= value <= bounds[1] for value in values.values())
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
        sd = statistics.pstdev(vals)
        if not sd:
            return vals, None
        avg = statistics.fmean(vals)
        return vals, tuple((v - avg) / (sd * math.sqrt(len(vals))) for v in vals)

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
                va, za = vector(a, mask)
                vb, zb = vector(b, mask)
                if za is None or zb is None:
                    continue
                r = sum_products(za, zb)
                if r <= DUPLICATE:
                    continue
                exact = va == vb
                slope = statistics.pstdev(vb) / statistics.pstdev(va) * r
                offset = statistics.fmean(vb) - slope * statistics.fmean(va)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    mapping = bbi.load_mapping(args.root)
    capture, _ = capture_values(args.root, mapping)
    report = {"mapping_version": mapping["version"], "sources": {BBI: describe(capture)}}
    output = args.output or args.root / OUTPUT
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
