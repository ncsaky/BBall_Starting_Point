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
3. Across seasons: weights 2025-26 1.0, 2024-25 0.6, 2023-24 0.35, each times minutes/(minutes+800), times the
   strength of the strongest mapped metric available (1 primary, 0.5 supporting, 0.25 weak). A metric with
   "per" in the mapping (per-75 counts such as turnovers) is first divided by that exposure metric (touches).
4. The combined score becomes a grade on the model's anchors (50 functional, 75 strong ~80th pct, 90 exceptional
   ~97th pct): grade = 100 * logistic(1.31 * z). Smooth, bounded, never clipped.
5. The grade is blended with the estimator's existing value by evidence weight: w_bbi / (w_bbi + PRIOR_WEIGHT).
   A rotation player with several recent seasons is mostly BBI; a deep-bench player stays near the estimate.
6. Tendencies with a single probability (propensity kind) and unmeasured physical grades get the same evidence,
   but keep the estimator's own scale: the existing value is turned into a league rank (normal score), blended
   with the BBI score by the same share, and mapped back through the league's existing distribution of that
   input. BBI decides who is above whom; the estimator's units and spread stay.
7. Multi-way tendencies (distribution kind, e.g. shoot/drive/pass/post/reset) are handled one choice at a time
   the same way, then the mix is rescaled to sum to 1 (choices without BBI evidence keep their relative size).
   The shot-region mix (T02) is skipped because it is already built from observed shot locations.
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
VERSION = "bbi_evidence_overlay_v2_2026_11_17"
OVERLAY_KINDS = ("grade", "propensity", "physical")
# Shot-region mix is already built from observed shot locations; BBI would only repeat that data.
SKIP_DISTRIBUTIONS = {"T02"}
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


def _per_exposure(values: dict[str, tuple[float, float, str | None]],
                  exposure: dict[str, tuple[float, float, str | None]]) -> dict[str, tuple[float, float, str | None]]:
    """A per-75 count divided by the player's exposure per 75 (e.g. turnovers per touch), same season.

    The mapping marks such metrics with "per": counts per 75 possessions mostly measure how often a player has
    the ball, so without this a high-usage creator looks careless. Players without exposure data are dropped."""
    out = {}
    for key, (value, minutes, cid) in values.items():
        den = exposure.get(key)
        if den and den[0] > 0:
            out[key] = (value / den[0], minutes, cid)
    return out


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
    specs: dict[str, dict[str, Any]] = {}
    for iid, spec in mapping["inputs"].items():
        if not spec.get("metrics"):
            continue
        if spec.get("kind") in OVERLAY_KINDS:
            specs[iid] = spec
        elif spec.get("kind") == "distribution" and iid not in SKIP_DISTRIBUTIONS:
            # One target per choice in the mix ("T01:drive"), from the metrics labelled with that choice.
            by_outcome: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for m in spec["metrics"]:
                if m.get("outcome"):
                    by_outcome[m["outcome"]].append(m)
            for outcome, items in by_outcome.items():
                specs[f"{iid}:{outcome}"] = {"metrics": items}
    metrics = {m["metric"] for spec in specs.values() for m in spec["metrics"]}
    metrics |= {m["per"] for spec in specs.values() for m in spec["metrics"] if m.get("per")}
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
                num = den = top = 0.0
                used = []
                for m in spec["metrics"]:
                    key = (season, m["metric"], int(m.get("direction", 1)), m.get("per"))
                    if key not in pct_cache:
                        values = table.get((season, m["metric"]), {})
                        if m.get("per"):
                            values = _per_exposure(values, table.get((season, m["per"]), {}))
                        pct_cache[key] = _percentiles(values, int(m.get("direction", 1)))
                    p = pct_cache[key].get(cid)
                    if p is None:
                        continue
                    w = STRENGTH.get(m.get("strength", "supporting"), 0.5)
                    num += w * _ND.inv_cdf(p)
                    den += w
                    top = max(top, w)
                    used.append(m["metric"])
                if not den:
                    continue
                z = num / den
                # Evidence weight also scales with the strongest metric used: an input known only from weak
                # proxies moves less than one with a direct measure.
                weight = SEASON_WEIGHTS[season] * minutes / (minutes + MINUTES_HALF) * top
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


def _value_slot(record: Mapping[str, Any]) -> tuple[str, str] | None:
    """Where the overlay writes: ("grade", key) for grades, ("probability", key) for single-number tendencies,
    ("display_grade", key) for unmeasured physical grades. None when the record is not overlaid."""
    value = record.get("value")
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("grade"), (int, float)):
        return ("grade", "grade")
    if isinstance(value.get("probability"), (int, float)):
        return ("rank", "probability")
    display = value.get("display_grade")
    if isinstance(display, dict) and isinstance(display.get("grade"), (int, float)) and not value.get("measurements"):
        return ("rank", "display_grade")
    return None


def _mix(record: Mapping[str, Any] | None) -> dict[str, float] | None:
    """The single reference mix of a distribution tendency, or None (several conditions are not overlaid)."""
    value = (record or {}).get("value")
    rows = value.get("rows") if isinstance(value, dict) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0].get("probabilities"), dict):
        return None
    return rows[0]["probabilities"]


def _read(record: Mapping[str, Any], key: str) -> float:
    value = record["value"]
    return float(value["display_grade"]["grade"] if key == "display_grade" else value[key])


def _write(record: dict[str, Any], key: str, new: float) -> None:
    if key == "display_grade":
        record["value"] = {**record["value"], "display_grade": {**record["value"]["display_grade"], "grade": new}}
    else:
        record["value"] = {**record["value"], key: new}


def _rank_z(sorted_values: list[float], x: float) -> float:
    import bisect
    n = len(sorted_values)
    lo, hi = bisect.bisect_left(sorted_values, x), bisect.bisect_right(sorted_values, x)
    return _ND.inv_cdf(((lo + hi) / 2 + 0.5) / (n + 1))


def _quantile(sorted_values: list[float], u: float) -> float:
    n = len(sorted_values)
    pos = min(max(u * (n + 1) - 0.5 - 0.5, 0.0), n - 1.0)  # inverse of the mid-rank plotting position
    lo = int(math.floor(pos)); hi = min(lo + 1, n - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def apply_overlay(section: dict[str, Any], root: Path, mapping: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Blend BBI evidence into an estimator input section in place. Returns a summary."""
    scores = player_input_scores(root, mapping)
    # League distributions before any change, for inputs kept on the estimator's own scale.
    league: dict[str, list[float]] = defaultdict(list)
    for doc in section["players"].values():
        for iid, record in doc["inputs"].items():
            slot = _value_slot(record)
            if slot and slot[0] == "rank":
                league[iid].append(_read(record, slot[1]))
            for outcome, prob in (_mix(record) or {}).items():
                league[f"{iid}:{outcome}"].append(float(prob))
    for values in league.values():
        values.sort()
    changed = players = 0
    by_kind: dict[str, int] = defaultdict(int)
    for pid, doc in section["players"].items():
        bbi = scores.get(pid)
        if not bbi:
            continue
        players += 1
        mixes: dict[str, dict[str, tuple[float, dict[str, Any]]]] = defaultdict(dict)
        for target, ev in bbi.items():
            if ":" in target:
                iid, outcome = target.split(":", 1)
                mixes[iid][outcome] = (0.0, ev)
        for iid, parts in mixes.items():
            record = doc["inputs"].get(iid)
            mix = _mix(record) if record else None
            if not mix:
                continue
            new_mix = dict(mix)
            notes = []
            strongest = 0.0
            for outcome, (_, ev) in parts.items():
                pool = league.get(f"{iid}:{outcome}") or []
                if outcome not in mix or len(pool) < 30:
                    continue
                share = ev["weight"] / (ev["weight"] + PRIOR_WEIGHT)
                strongest = max(strongest, share)
                z_new = share * ev["z"] + (1 - share) * _rank_z(pool, float(mix[outcome]))
                new_mix[outcome] = _quantile(pool, _ND.cdf(z_new))
                notes.append(f"{outcome} {round(float(mix[outcome]), 4)}->{round(new_mix[outcome], 4)} (score {ev['z']}, share {share:.2f})")
            if not notes:
                continue
            total = sum(new_mix.values())
            new_mix = {k: round(v / total, 6) for k, v in new_mix.items()}
            rows = [dict(record["value"]["rows"][0], probabilities=new_mix)]
            record["value"] = {**record["value"], "rows": rows}
            evidence = list(record.get("evidence") or [])
            evidence.append({
                "source": f"{CACHE_DIR}/normalized.json (Leaderboards Values)",
                "method": f"{VERSION}: each choice re-ranked by mapped BBI metrics on its own league scale, then the mix rescaled to sum to 1: " + "; ".join(notes),
                "shared_evidence_id": f"bbi:{pid}:{iid}",
                "notes": "metrics: " + ", ".join(sorted({m for _, ev in parts.values() for m in ev["metrics_used"]})[:12]),
            })
            record["evidence"] = evidence
            if strongest >= 0.5:
                record["status"] = "estimated"
                record["reason"] = "estimated"
            changed += 1
            by_kind["mix"] += 1
        for iid, ev in bbi.items():
            if ":" in iid:
                continue
            record = doc["inputs"].get(iid)
            slot = _value_slot(record) if record else None
            if not slot:
                continue
            mode, key = slot
            old = _read(record, key)
            share = ev["weight"] / (ev["weight"] + PRIOR_WEIGHT)
            if mode == "grade":
                new = round(share * ev["grade"] + (1 - share) * old, 3)
                detail = f"grade {ev['grade']} (z {ev['z']})"
            else:
                pool = league.get(iid) or []
                if len(pool) < 30:
                    continue
                z_new = share * ev["z"] + (1 - share) * _rank_z(pool, old)
                new = round(_quantile(pool, _ND.cdf(z_new)), 6 if key == "probability" else 3)
                detail = f"league-rank score {ev['z']} mapped onto the existing {iid} scale"
            _write(record, key, new)
            evidence = list(record.get("evidence") or [])
            evidence.append({
                "source": f"{CACHE_DIR}/normalized.json (Leaderboards Values)",
                "method": (f"{VERSION}: season-percentile of mapped BBI metrics -> {detail}, "
                           f"blended share {share:.2f} with prior/estimate {round(old, 6)}"),
                "shared_evidence_id": f"bbi:{pid}:{iid}",
                "notes": "metrics: " + ", ".join(ev["metrics_used"][:12]) + "; seasons/minutes: " + json.dumps(ev["seasons"]),
            })
            record["evidence"] = evidence
            if share >= 0.5:
                record["status"] = "estimated"
                record["reason"] = "estimated"
            changed += 1
            by_kind[mode] += 1
    return {"players_with_bbi": players, "cells_changed": changed, "by_mode": dict(by_kind), "version": VERSION}
