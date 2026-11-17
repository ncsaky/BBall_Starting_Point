"""Basketball Index (BBI) evidence overlay for the 94-input player model (Stage 1).

The user bought a month of BBI data specifically so player ratings would rest on it. Codex's original hook
(`input_estimator.load_bbi_evidence`) treats BBI as one weak proxy per player for 32 metrics. This module
turns the full Leaderboards capture (664 metrics, every player-season since 2013-14) into player-specific
evidence for the skill inputs, using a reviewed metric->input mapping (data/research/bbi/bbi_input_mapping.json).

Method (declared, not fitted to simulation outcomes):
1. Raw values only (the Leaderboards "Values" display). For every season and metric, each player's value is
   ranked against that season's players with at least MIN_POOL_MINUTES, in the mapped direction
   (direction -1 flips, e.g. turnover rates). Ranks are mid-rank percentiles in (0, 1).
2. Per player, season and input: weighted mean of the mapped metrics' percentiles (primary 1.0, supporting 0.5,
   weak 0.25), converted to a normal score.
3. Across seasons: weights 2025-26 1.0, 2024-25 0.6, 2023-24 0.35, each times minutes/(minutes+800).
4. The combined score becomes a grade on the model's anchors (50 functional, 75 strong ~80th pct, 90 exceptional
   ~97th pct): grade = 100 * logistic(1.31 * z). Smooth, bounded, never clipped.
5. The grade is blended with the estimator's existing value by evidence weight: w_bbi / (w_bbi + PRIOR_WEIGHT).
   A rotation player with several recent seasons is mostly BBI; a deep-bench player stays near the estimate.
The record keeps its prior/estimate provenance plus a BBI evidence entry, and becomes reason "estimated"
(player-specific evidence) when BBI weight is material.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist
from typing import Any, Mapping

MAPPING_FILE = "data/research/bbi/bbi_input_mapping.json"
CACHE_DIR = "data/research/bbi"
MIN_POOL_MINUTES = 500
SEASON_WEIGHTS = {"2025-26": 1.0, "2024-25": 0.6, "2023-24": 0.35}
STRENGTH = {"primary": 1.0, "supporting": 0.5, "weak": 0.25}
PRIOR_WEIGHT = 0.35
MINUTES_HALF = 800
GRADE_SLOPE = 1.31
VERSION = "bbi_evidence_overlay_v1_2026_11_17"
_ND = NormalDist()


def _grade_from_z(z: float) -> float:
    return 100.0 / (1.0 + math.exp(-GRADE_SLOPE * z))


def load_mapping(root: Path) -> dict[str, Any]:
    return json.loads((Path(root) / MAPPING_FILE).read_text())


def _values_batches(index: Mapping[str, Any]) -> set[str]:
    out = set()
    for batch_id, batch in index.get("batches", {}).items():
        meta = batch.get("metadata") or {}
        if (meta.get("filters") or {}).get("display") == "Values":
            out.add(batch_id)
    return out


def collect_values(root: Path, metrics: set[str]) -> dict[tuple[str, str], dict[str, tuple[float, float, str | None]]]:
    """(season, metric) -> {player_key: (value, minutes, canonical_id)} from Values captures, recent seasons only."""
    from .bbi_import import iter_records
    folder = Path(root) / CACHE_DIR
    index = json.loads((folder / "normalized.json").read_text())
    keep = _values_batches(index)
    table: dict[tuple[str, str], dict[str, tuple[float, float, str | None]]] = defaultdict(dict)
    for row in iter_records(index, folder):
        if row.get("batch_id") not in keep or row.get("season") not in SEASON_WEIGHTS:
            continue
        metric = row.get("metric_name")
        if metric not in metrics:
            continue
        value = row.get("raw_value")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            continue
        key = row.get("canonical_player_id") or f"name:{row.get('player_name_raw')}"
        table[(row["season"], metric)][key] = (float(value), float(row.get("minutes") or 0.0), row.get("canonical_player_id"))
    return table


def _percentiles(values: dict[str, tuple[float, float, str | None]], direction: int) -> dict[str, float]:
    pool = sorted(v * direction for v, m, _ in values.values() if m >= MIN_POOL_MINUTES)
    if len(pool) < 30:
        return {}
    import bisect
    n = len(pool)
    out = {}
    for key, (v, _, _) in values.items():
        x = v * direction
        lo, hi = bisect.bisect_left(pool, x), bisect.bisect_right(pool, x)
        out[key] = min(max(((lo + hi) / 2 + 0.5) / (n + 1), 0.5 / (n + 1)), 1 - 0.5 / (n + 1))
    return out


def player_input_scores(root: Path, mapping: Mapping[str, Any] | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    """canonical_id -> input_id -> {grade, weight, seasons, metrics_used} for grade-kind skill inputs."""
    mapping = mapping or load_mapping(root)
    specs = {iid: spec for iid, spec in mapping["inputs"].items()
             if spec.get("kind") == "grade" and spec.get("metrics")}
    metrics = {m["metric"] for spec in specs.values() for m in spec["metrics"]}
    table = collect_values(root, metrics)
    pct_cache: dict[tuple[str, str, int], dict[str, float]] = {}
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    players_by_season: dict[str, dict[str, float]] = defaultdict(dict)
    for (season, _), vals in table.items():
        for key, (_, minutes, cid) in vals.items():
            if cid:
                players_by_season[season][cid] = max(players_by_season[season].get(cid, 0.0), minutes)
    for iid, spec in specs.items():
        for season, players in players_by_season.items():
            for cid, minutes in players.items():
                num = den = 0.0
                used = []
                for m in spec["metrics"]:
                    key = (season, m["metric"], int(m.get("direction", 1)))
                    if key not in pct_cache:
                        pct_cache[key] = _percentiles(table.get((season, m["metric"]), {}), int(m.get("direction", 1)))
                    p = pct_cache[key].get(cid)
                    if p is None:
                        continue
                    w = STRENGTH.get(m.get("strength", "supporting"), 0.5)
                    num += w * _ND.inv_cdf(p)
                    den += w
                    used.append(m["metric"])
                if not den:
                    continue
                z = num / den
                weight = SEASON_WEIGHTS[season] * minutes / (minutes + MINUTES_HALF)
                cell = out[cid].setdefault(iid, {"z_num": 0.0, "weight": 0.0, "seasons": {}, "metrics_used": set()})
                cell["z_num"] += weight * z
                cell["weight"] += weight
                cell["seasons"][season] = round(minutes)
                cell["metrics_used"].update(used)
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for cid, inputs in out.items():
        result[cid] = {}
        for iid, cell in inputs.items():
            if cell["weight"] <= 0:
                continue
            z = cell["z_num"] / cell["weight"]
            result[cid][iid] = {"grade": round(_grade_from_z(z), 3), "z": round(z, 4), "weight": round(cell["weight"], 4),
                                "seasons": cell["seasons"], "metrics_used": sorted(cell["metrics_used"])}
    return result


def apply_overlay(section: dict[str, Any], root: Path, mapping: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Blend BBI evidence into an estimator input section in place. Returns a summary."""
    scores = player_input_scores(root, mapping)
    changed = players = 0
    for pid, doc in section["players"].items():
        bbi = scores.get(pid)
        if not bbi:
            continue
        players += 1
        for iid, ev in bbi.items():
            record = doc["inputs"].get(iid)
            if not record or not isinstance(record.get("value"), dict) or "grade" not in record["value"]:
                continue
            old = float(record["value"]["grade"])
            share = ev["weight"] / (ev["weight"] + PRIOR_WEIGHT)
            new = round(share * ev["grade"] + (1 - share) * old, 3)
            record["value"] = {**record["value"], "grade": new}
            evidence = list(record.get("evidence") or [])
            evidence.append({
                "source": f"{CACHE_DIR}/normalized.json (Leaderboards Values)",
                "method": (f"{VERSION}: season-percentile of mapped BBI metrics -> grade {ev['grade']} "
                           f"(z {ev['z']}), blended share {share:.2f} with prior/estimate {old}"),
                "shared_evidence_id": f"bbi:{pid}:{iid}",
                "notes": "metrics: " + ", ".join(ev["metrics_used"][:12]) + "; seasons/minutes: " + json.dumps(ev["seasons"]),
            })
            record["evidence"] = evidence
            if share >= 0.5:
                record["status"] = "estimated"
                record["reason"] = "estimated"
            changed += 1
    return {"players_with_bbi": players, "cells_changed": changed, "version": VERSION}
