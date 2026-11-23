#!/usr/bin/env python3
"""INPUT-DATA-FIXES (2026-11-23): re-check each input data audit finding against the raw capture, and record the
repeatability screen before and after tied values share their rank.

    PYTHONPATH=src .venv/bin/python scripts/research/input_data_fixes.py

Reads the Basketball Index Values cache for the three build seasons (bbi_evidence._recent_values), both Crafted NBA
snapshots and the evidence mapping. Writes only the aggregate data/research/input_data_fixes.json (no player rows from
the paid capture; player names appear only for the handful of impossible values and percent-unit rows).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from statistics import correlation, mean

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data import bbi_evidence as be  # noqa: E402
from nba_gm_data import input_estimator as ie  # noqa: E402

OUT = ROOT / "data/research/input_data_fixes.json"
SEASONS = ("2023-24", "2024-25", "2025-26")
PAINT_PULLUP = ["Shooting Talent", "Shot Making Efficiency", "Shot Quality", "Shot Creation", "Shot Making",
                "Openness Rating"]
PAIRS = [("Stable Defensive FG% at Rim", "Stable Rim dFG% vs. Expected"),
         ("Rim dFG% vs Expected", "Stable Rim dFG% vs. Expected"),
         ("Average Dribbles Per Touch", "Average Seconds Per Touch"),
         ("Movement Distance Rating", "Movement Speed Rating")]
RATE_RANGE = ["Adjusted Offensive Rebounding Success Rate", "Adjusted Defensive Rebounding Success Rate",
              "Percentage of Offensive Rebounds Contested", "Percentage of Defensive Rebounds Contested"]


def _pair(table, a: str, b: str) -> dict:
    out = {}
    for s in SEASONS:
        x, y = table.get((s, a), {}), table.get((s, b), {})
        keys = [k for k in x if k in y]
        same = sum(1 for k in keys if abs(x[k][0] - y[k][0]) < 1e-9)
        try:
            r = correlation([x[k][0] for k in keys], [y[k][0] for k in keys])
        except ValueError:
            r = None
        out[s] = {"paired": len(keys), "identical": same, "pearson": None if r is None else round(r, 4)}
    return out


def _untied_rank_correlation(x, y):
    """The screen before this task: tied values got distinct ranks in sort order."""
    ids = [k for k in x if k in y]
    if len(ids) < 40:
        return None
    rx = {k: i for i, k in enumerate(sorted(ids, key=lambda k: x[k]))}
    ry = {k: i for i, k in enumerate(sorted(ids, key=lambda k: y[k]))}
    try:
        return correlation([rx[k] for k in ids], [ry[k] for k in ids])
    except ValueError:
        return None


REMOVED = [("T17", {"metric": "Movement Distance Rating", "direction": 1, "strength": "supporting"})]


def repeatability(table, mapping) -> list[dict]:
    """Every mapped metric (plus the removed Movement Distance Rating): the screen's repeatability with tied values
    ranked in sort order (before) and sharing their average rank (now), and the resulting weight factors."""
    rows, seen = [], {}
    seasons = sorted(be.SEASON_WEIGHTS)
    entries = [(iid, m) for iid, spec in mapping["inputs"].items() if not spec.get("measured_by")
               for m in spec.get("metrics", [])] + REMOVED
    for iid, m in entries:
        key = (m["metric"], be._exposure_names(m))
        if key in seen:
            seen[key]["inputs"].append(iid)
            continue
        by = {s: {cid: v for v, mins, cid in be._metric_values(table, s, m).values()
                  if cid and mins >= be.RELIABILITY_MINUTES} for s in seasons}
        old = [r for a, b in zip(seasons, seasons[1:]) if (r := _untied_rank_correlation(by[a], by[b])) is not None]
        new = [r for a, b in zip(seasons, seasons[1:]) if (r := be._rank_correlation(by[a], by[b])) is not None]
        o = mean(old) if old else None
        n = mean(new) if new else None
        row = {"metric": m["metric"], "exposure": list(be._exposure_names(m)), "inputs": [iid],
               "r_untied": None if o is None else round(o, 4), "r_tied": None if n is None else round(n, 4),
               "factor_untied": round(be.reliability_factor(o), 4), "factor_tied": round(be.reliability_factor(n), 4)}
        seen[key] = row
        rows.append(row)
    rows.sort(key=lambda r: -abs(r["factor_tied"] - r["factor_untied"]))
    return rows


def _lead(value):
    """(impact, percentile) from a Crafted cell: a number, or text such as '-1.4 27%'."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), None
    if isinstance(value, str):
        hit = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*(?:(\d+(?:\.\d+)?)%)?\s*", value)
        if hit:
            return float(hit.group(1)), (float(hit.group(2)) if hit.group(2) else None)
    return None, None


def crafted() -> dict:
    march = json.loads((ROOT / ie.SKILL_PATH).read_text())["players"]
    april = ie._index(json.loads((ROOT / ie.STATS_PATH).read_text())["rows"])
    out = {}
    for column, alias in (("CraftedOPM", "COPM"), ("CraftedDPM", "CDPM")):
        text = sum(1 for r in march if isinstance(r.get(column), str))
        plain = sum(1 for r in march if ie._number(r.get(column)) is not None)
        lead_err, alias_err, agree = [], [], 0
        for r in march:
            x, _ = _lead(r.get(column))
            c = ie._number(r.get(alias))
            if x is not None and c is not None:
                agree += abs(x - c) < 1e-9
            a = ie._get(april.get(ie._normalize(r.get("name") or ""), {}), column)
            if a is None:
                continue
            if x is not None:
                lead_err.append(abs(x - a))
            if c is not None:
                alias_err.append(abs(c - a))
        out[column] = {"march_rows": len(march), "march_text_cells": text, "march_numeric_cells": plain,
                       "march_alias": alias, "alias_equals_text_value": agree,
                       "text_value_vs_april_mean_abs": round(mean(lead_err), 3),
                       "alias_vs_april_mean_abs": round(mean(alias_err), 3), "april_matches": len(alias_err)}
    stats = ie._index(json.loads((ROOT / ie.STATS_PATH).read_text())["rows"])
    skills = ie._index(march)
    out["march_rows_reached_for_impact"] = sum(
        1 for k, r in skills.items() if (ie._get(stats.get(k, {}), "MP") or 0) <= 0 and (ie._get(r, "MP") or 0) > 0)
    return out


def play_type_units() -> dict:
    out = {}
    for label, path, key in (("march", ie.SKILL_PATH, "players"), ("april", ie.STATS_PATH, "rows")):
        rows = json.loads((ROOT / path).read_text())[key]
        bad = [r for r in rows if any((ie._get(r, k) or 0) > 1 for k in ie.PLAY_TYPE_SHARES)]
        out[label] = {"rows": len(rows), "percent_unit_rows": [
            {"name": r.get("name"), "shares": {k: r.get(k) for k in ie.PLAY_TYPE_SHARES if r.get(k) is not None},
             "after": {k: v for k, v in ie._share_units(r).items() if k in ie.PLAY_TYPE_SHARES and v is not None}}
            for r in bad]}
    return out


def main() -> None:
    mapping = be.load_mapping(ROOT)
    metrics = {f"{side} {x}" for x in PAINT_PULLUP for side in ("Paint", "Pull-Up")}
    metrics |= {m for pair in PAIRS for m in pair} | set(RATE_RANGE)
    for spec in mapping["inputs"].values():
        for m in spec.get("metrics", []):
            metrics.add(m["metric"])
            metrics |= set(be._exposure_names(m))
    table = be.collect_values(ROOT, metrics)
    zeros = {s: {"rows": len(table.get((s, "Movement Distance Rating"), {})),
                 "zero": sum(1 for v in table.get((s, "Movement Distance Rating"), {}).values() if v[0] == 0),
                 "zero_1000_minutes": sum(1 for v in table.get((s, "Movement Distance Rating"), {}).values()
                                          if v[0] == 0 and v[1] >= 1000),
                 "rows_1000_minutes": sum(1 for v in table.get((s, "Movement Distance Rating"), {}).values()
                                          if v[1] >= 1000)} for s in SEASONS}
    impossible = {}
    for name in RATE_RANGE:
        for s in SEASONS:
            for key, (v, mins, _) in table.get((s, name), {}).items():
                if not 0 <= v <= 100:
                    impossible.setdefault(name, []).append({"season": s, "player": key, "value": v, "minutes": round(mins)})
    rep = repeatability(table, mapping)
    payload = {
        "version": "input_data_fixes_v1_2026_11_23",
        "mapping_version": mapping["version"],
        "paint_vs_pull_up": {x: _pair(table, f"Paint {x}", f"Pull-Up {x}") for x in PAINT_PULLUP},
        "near_duplicates": {f"{a} | {b}": _pair(table, a, b) for a, b in PAIRS},
        "movement_distance_zeros": zeros,
        "impossible_rates": impossible,
        "crafted_impact": crafted(),
        "play_type_units": play_type_units(),
        "repeatability": {"changed": [r for r in rep if abs(r["factor_tied"] - r["factor_untied"]) >= 0.005],
                          "metrics": len(rep)},
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(payload['repeatability']['changed'])} of {len(rep)} repeatability "
          f"weights change by 0.005+")


if __name__ == "__main__":
    main()
