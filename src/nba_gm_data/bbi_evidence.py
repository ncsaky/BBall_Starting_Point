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
   weak 0.25), converted to a normal score. A metric for a secondary shot type (pull-up, off-screen, deep) carries a
   "volume" entry: its weight is also multiplied by attempts / (attempts + half) of that shot type that season, so a
   percentage on a dozen attempts no longer outweighs the player's shooting as a whole (2026-11-19).
   Each metric's weight is also multiplied by its measured repeatability (analyst-first task, 2026-11-19): the
   season-to-season rank correlation of that metric among players with 1,000+ minutes in both seasons, divided by
   RELIABILITY_REF and capped at 1. A metric that barely repeats from one season to the next (help effectiveness,
   isolation turnover rate, and-one conversion: r 0.1-0.25) mostly measures small samples and context, so it can no
   longer decide an input on its own; repeatable metrics (r >= 0.6) keep their full weight.
3. Across seasons: weights 2025-26 1.0, 2024-25 0.6, 2023-24 0.35, each times minutes/(minutes+800), times the
   strength of the strongest mapped metric available (1 primary, 0.5 supporting, 0.25 weak). A metric with
   "per" in the mapping (per-75 counts such as turnovers) is first divided by that exposure metric (touches); a
   metric with "per_sum" is divided by the sum of several exposure metrics (e.g. plays used or created = true shot
   attempts + turnovers + potential assists, the classic turnover-percentage denominator).
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
VERSION = "bbi_evidence_overlay_v4_2026_11_19"
# Metrics that repeat at least this well from season to season (rank correlation, 1,000+ minutes both seasons) keep
# their full mapped weight; noisier metrics are scaled down in proportion. 0.6 is about the repeatability of a stable
# per-possession rate in this data (rim FG%, role-adjusted potential assists per pass, steals per possession).
RELIABILITY_REF = 0.6
RELIABILITY_MINUTES = 1000
# Team possessions per player minute (about 99 per 48 minutes): turns a per-75-possession rate into a season count.
POSSESSIONS_PER_MINUTE = 99.0 / 48.0
OVERLAY_KINDS = ("grade", "propensity", "physical")
# Shot-region mix is already built from observed shot locations; BBI would only repeat that data.
SKIP_DISTRIBUTIONS = {"T02", "T01"}  # T01 is set from measured per-touch rates (apply_measured_tendencies)
MEASURED_INPUTS = {"T01", "T08"}      # measured on their own scale, not re-ranked (apply_measured_tendencies)
# Free-throw execution is stored as a real free-throw percentage (the estimator's sample-weighted FT% from the same
# box-score data BBI's "Stable FT%" uses). Blending a 0-100 percentile grade into it mixed two units: until 2026-11-19 a
# 78% shooter (Amen Thompson, 2025-26) showed 42 and Giannis 24 (ratings-consensus task). Grades on this scale are skipped.
NATIVE_PERCENT_SCALES = {"research_FT_conversion_percent_proxy_v1"}
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


RECENT_CACHE = "values_recent.json.gz"


def _recent_values(root: Path) -> dict[tuple[str, str], dict[str, tuple[float, float, str | None]]]:
    """Every metric's Values rows for the recent seasons, from a compact cache rebuilt whenever the imported data
    changes (reading the full normalized store scans millions of rows)."""
    import gzip
    folder = Path(root) / CACHE_DIR
    source = folder / "normalized.json"
    stamp = f"{source.stat().st_size}:{int(source.stat().st_mtime)}"
    cache = folder / RECENT_CACHE
    if cache.exists():
        try:
            data = json.loads(gzip.decompress(cache.read_bytes()))
            if data.get("stamp") == stamp:
                return {tuple(k.split("|", 1)): {pk: tuple(v) for pk, v in rows.items()} for k, rows in data["table"].items()}
        except (OSError, ValueError):
            pass
    table = _collect_from_store(root, None)
    payload = {"stamp": stamp, "table": {f"{s}|{m}": rows for (s, m), rows in table.items()}}
    cache.write_bytes(gzip.compress(json.dumps(payload).encode(), compresslevel=6))
    return table


def collect_values(root: Path, metrics: set[str]) -> dict[tuple[str, str], dict[str, tuple[float, float, str | None]]]:
    """(season, metric) -> {player_key: (value, minutes, canonical_id)} from Values captures, recent seasons only."""
    table = _recent_values(root)
    return {key: rows for key, rows in table.items() if key[1] in metrics}


def _collect_from_store(root: Path, metrics: set[str] | None) -> dict[tuple[str, str], dict[str, tuple[float, float, str | None]]]:
    from .bbi_import import iter_records
    folder = Path(root) / CACHE_DIR
    index = json.loads((folder / "normalized.json").read_text())
    keep = _values_batches(index)
    table: dict[tuple[str, str], dict[str, tuple[float, float, str | None]]] = defaultdict(dict)
    for row in iter_records(index, folder):
        if row.get("batch_id") not in keep or row.get("season") not in SEASON_WEIGHTS:
            continue
        metric = row.get("metric_name")
        if metrics is not None and metric not in metrics:
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


def _exposure_names(m: Mapping[str, Any]) -> tuple[str, ...]:
    """Exposure metric(s) a mapped metric is divided by: "per" (one metric) or "per_sum" (their sum)."""
    if m.get("per_sum"):
        return tuple(m["per_sum"])
    return (m["per"],) if m.get("per") else ()


def _summed_exposure(table: Mapping[tuple[str, str], dict[str, tuple[float, float, str | None]]], season: str,
                     names: tuple[str, ...]) -> dict[str, tuple[float, float, str | None]]:
    """Season exposure per player: one metric, or the sum of several (players missing any part are dropped)."""
    parts = [table.get((season, name), {}) for name in names]
    if len(parts) == 1:
        return parts[0]
    out = {}
    for key, first in parts[0].items():
        if all(key in part for part in parts[1:]):
            out[key] = (sum(part[key][0] for part in parts), first[1], first[2])
    return out


def _metric_values(table: Mapping[tuple[str, str], dict[str, tuple[float, float, str | None]]], season: str,
                   m: Mapping[str, Any]) -> dict[str, tuple[float, float, str | None]]:
    values = table.get((season, m["metric"]), {})
    names = _exposure_names(m)
    return _per_exposure(values, _summed_exposure(table, season, names)) if names else values


def _rank_correlation(x: Mapping[str, float], y: Mapping[str, float]) -> float | None:
    ids = [k for k in x if k in y]
    if len(ids) < 40:
        return None
    rx = {k: i for i, k in enumerate(sorted(ids, key=lambda k: x[k]))}
    ry = {k: i for i, k in enumerate(sorted(ids, key=lambda k: y[k]))}
    from statistics import correlation
    try:
        return correlation([rx[k] for k in ids], [ry[k] for k in ids])
    except ValueError:
        return None


def metric_reliability(table: Mapping[tuple[str, str], dict[str, tuple[float, float, str | None]]],
                       m: Mapping[str, Any]) -> float | None:
    """Mean season-to-season rank correlation of a mapped metric (after any exposure division) among players with
    RELIABILITY_MINUTES+ in both seasons, over the consecutive season pairs available. None when unmeasurable."""
    seasons = sorted(SEASON_WEIGHTS)
    by_season = {}
    for season in seasons:
        by_season[season] = {cid: v for v, minutes, cid in _metric_values(table, season, m).values()
                             if cid and minutes >= RELIABILITY_MINUTES}
    values = [r for a, b in zip(seasons, seasons[1:])
              if (r := _rank_correlation(by_season[a], by_season[b])) is not None]
    return sum(values) / len(values) if values else None


def reliability_factor(r: float | None) -> float:
    """Weight multiplier from repeatability: r / RELIABILITY_REF, capped at 1 (1 when unmeasurable)."""
    if r is None:
        return 1.0
    return min(1.0, max(0.0, r) / RELIABILITY_REF)


def _percentiles(values: dict[str, tuple[float, float, str | None]], direction: int) -> dict[str, float]:
    pool = sorted(v * direction for v, m, _ in values.values() if m >= MIN_POOL_MINUTES)
    if len(pool) < 30 or pool[0] == pool[-1]:
        # A column with one value for everyone (a broken export: shooting fouls drawn is all zeros) ranks nobody.
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
        if not spec.get("metrics") or spec.get("measured_by"):
            # measured_by: the input is measured elsewhere from the same data (e.g. foul_security_evidence).
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
    metrics |= {name for spec in specs.values() for m in spec["metrics"] for name in _exposure_names(m)}
    metrics |= {name for spec in specs.values() for m in spec["metrics"] if m.get("volume")
                for name in (m["volume"]["per75"], m["volume"].get("minus")) if name}
    table = collect_values(root, metrics)
    by_cid: dict[tuple[str, str], dict[str, float]] = {}

    def volume_factor(m: Mapping[str, Any], season: str, cid: str, minutes: float) -> float:
        """Sample-size weight for a shot-type metric: attempts of that type / (attempts + half). 1 when unknown."""
        vol = m.get("volume")
        if not vol:
            return 1.0
        values = []
        for name in (vol["per75"], vol.get("minus")):
            if not name:
                continue
            if (season, name) not in by_cid:
                by_cid[(season, name)] = {c: v for v, _, c in table.get((season, name), {}).values() if c}
            values.append(by_cid[(season, name)].get(cid))
        if values[0] is None:
            return 1.0
        minus = (values[1] or 0.0) if len(values) > 1 else 0.0
        per75 = max(0.0, values[0] - minus)
        attempts = per75 / 75.0 * minutes * POSSESSIONS_PER_MINUTE
        return attempts / (attempts + float(vol.get("half", 40)))

    pct_cache: dict[tuple[str, str, int], dict[str, float]] = {}
    reliability: dict[tuple[str, tuple[str, ...]], float] = {}

    def reliability_of(m: Mapping[str, Any]) -> float:
        key = (m["metric"], _exposure_names(m))
        if key not in reliability:
            reliability[key] = reliability_factor(metric_reliability(table, m))
        return reliability[key]

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
                    key = (season, m["metric"], int(m.get("direction", 1)), _exposure_names(m))
                    if key not in pct_cache:
                        pct_cache[key] = _percentiles(_metric_values(table, season, m), int(m.get("direction", 1)))
                    p = pct_cache[key].get(cid)
                    if p is None:
                        continue
                    w = (STRENGTH.get(m.get("strength", "supporting"), 0.5) * volume_factor(m, season, cid, minutes)
                         * reliability_of(m))
                    if w <= 0:
                        continue
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
            if not slot or iid in MEASURED_INPUTS:
                continue
            mode, key = slot
            if mode == "grade" and record["value"].get("scale") in NATIVE_PERCENT_SCALES:
                continue
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


# Measured per-touch action rates for T01 (shoot / drive / pass / reset; post keeps the estimate).
T01_MEASURES = ("Touches Per 75", "Stable FGA Per 75", "Drives Per 75 Possessions",
                "Potential Assists Per 75 Possessions", "Potential Assists Per 100 Passes")


def measured_action_mix(root: Path) -> dict[str, dict[str, Any]]:
    """canonical_id -> {"mix": {shoot, drive, pass, reset} per touch (season-weighted), "weight": evidence weight}.

    pass = passes that create a shot (potential assists) per touch; reset = other passes per touch;
    shoot = field-goal attempts per touch; drive = drives per touch. Shares, not counts, so a hub big who
    touches the ball constantly and a guard who creates on most touches are both visible."""
    table = collect_values(root, set(T01_MEASURES))
    acc: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for season, season_weight in SEASON_WEIGHTS.items():
        touches = table.get((season, "Touches Per 75"), {})
        for key, (touch, minutes, cid) in touches.items():
            if not cid or touch <= 0:
                continue
            get = lambda m: (table.get((season, m), {}).get(key) or (None,))[0]
            fga, drives, pa, pa100 = (get(m) for m in T01_MEASURES[1:])
            if None in (fga, drives, pa, pa100) or pa100 <= 0:
                continue
            passes = pa / (pa100 / 100.0)
            rates = {"shoot": fga / touch, "drive": drives / touch, "pass": pa / touch,
                     "reset": max(0.0, passes - pa) / touch}
            w = season_weight * minutes / (minutes + MINUTES_HALF)
            for k, v in rates.items():
                acc[cid][k] += w * v
            acc[cid]["_w"] += w
    out = {}
    for cid, sums in acc.items():
        w = sums.pop("_w")
        if w > 0:
            out[cid] = {"mix": {k: v / w for k, v in sums.items()}, "weight": w}
    return out


SCALE_MAP_FILE = "data/canonical/tendency_scale_map.json"
MEASURED_T01 = ("shoot", "drive", "pass", "reset")
MIN_MAP_WEIGHT = 0.5   # players whose measured value defines the measured scale (about a season of real minutes)


def measured_involvement(root: Path) -> dict[str, dict[str, Any]]:
    """canonical_id -> {"value": true usage share (0-1, season-weighted), "weight": evidence weight}.

    True usage counts the possessions a player finishes and the ones he creates for teammates, the closest
    measure of offensive involvement for hub bigs and lead guards alike."""
    table = collect_values(root, {"Stable True Usage%"})
    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for season, season_weight in SEASON_WEIGHTS.items():
        for key, (value, minutes, cid) in table.get((season, "Stable True Usage%"), {}).items():
            if cid and value > 0:
                w = season_weight * minutes / (minutes + MINUTES_HALF)
                acc[cid][0] += w * value / 100.0
                acc[cid][1] += w
    return {cid: {"value": v / w, "weight": w} for cid, (v, w) in acc.items() if w > 0}


def _quantile_points(values: list[float], n: int = 201) -> list[float]:
    ordered = sorted(values)
    if not ordered:
        return []
    return [ordered[min(len(ordered) - 1, round(i * (len(ordered) - 1) / (n - 1)))] for i in range(n)]


def map_to_measured(table: Mapping[str, list[float]], x: float) -> float:
    """Place an estimated value on the measured scale by its rank among all estimates (monotone, interpolated)."""
    import bisect
    source, target = table["source"], table["target"]
    if not source or not target:
        return x
    if x <= source[0]:
        return target[0]
    if x >= source[-1]:
        return target[-1]
    i = bisect.bisect_left(source, x)
    lo = max(0, i - 1)
    span = source[i] - source[lo]
    frac = 0.0 if span <= 0 else (x - source[lo]) / span
    pos = lo + frac
    j = min(len(target) - 1, int(pos))
    k = min(len(target) - 1, j + 1)
    return target[j] + (target[k] - target[j]) * (pos - j)


def map_tendency_inputs(inputs: dict[str, Any], scale_map: Mapping[str, Any]) -> dict[str, Any]:
    """Translate estimator-scale T01 (shoot/drive/pass/reset) and T08 onto the measured scales, in place.
    Used for players without measurements, including generated rookies at install time."""
    record = inputs.get("T01")
    mix = _mix(record) if record else None
    if mix and "post" in mix and all(c in mix for c in MEASURED_T01) and all(f"T01:{c}" in scale_map for c in MEASURED_T01):
        mapped = {c: max(1e-4, map_to_measured(scale_map[f"T01:{c}"], float(mix[c]))) for c in MEASURED_T01}
        rest = 1.0 - float(mix["post"])
        total = sum(mapped.values())
        new_mix = {**{c: rest * v / total for c, v in mapped.items()}, "post": float(mix["post"])}
        record["value"] = {**record["value"], "rows": [dict(record["value"]["rows"][0],
                                                              probabilities={k: round(v, 6) for k, v in new_mix.items()})]}
    involvement = inputs.get("T08")
    if involvement and isinstance(involvement.get("value"), dict) and "probability" in involvement["value"] and "T08" in scale_map:
        involvement["value"] = {**involvement["value"], "probability": round(
            map_to_measured(scale_map["T08"], float(involvement["value"]["probability"])), 6)}
    return inputs


def load_scale_map(root: Path) -> dict[str, Any] | None:
    path = Path(root) / SCALE_MAP_FILE
    return json.loads(path.read_text()) if path.exists() else None


def apply_measured_tendencies(section: dict[str, Any], root: Path) -> dict[str, Any]:
    """Measured scales for the action mix (T01) and involvement (T08).

    1. Measure per-touch action rates and true usage from BBI (season-weighted, evidence weight by minutes).
    2. Build a rank translation from the estimator's scale to the measured scale (players with >= about a
       season of minutes define the measured scale) and save it for generated players (SCALE_MAP_FILE).
    3. Every player's estimate is translated onto the measured scale; players with measurements then blend in
       their own values by evidence weight. T01's post share keeps its estimate (no per-touch measure)."""
    mix_measured = measured_action_mix(root)
    inv_measured = measured_involvement(root)
    players = section["players"]
    scale_map: dict[str, Any] = {}
    for c in MEASURED_T01:
        source = [float(_mix(d["inputs"].get("T01"))[c]) for d in players.values() if _mix(d["inputs"].get("T01"))]
        target = []
        for ev in mix_measured.values():
            if ev["weight"] >= MIN_MAP_WEIGHT and sum(ev["mix"].values()) > 0:
                target.append(ev["mix"][c] / sum(ev["mix"].values()))
        scale_map[f"T01:{c}"] = {"source": _quantile_points(source), "target": _quantile_points(target)}
    source = [float(d["inputs"]["T08"]["value"]["probability"]) for d in players.values()
              if isinstance((d["inputs"].get("T08") or {}).get("value"), dict)]
    target = [ev["value"] for ev in inv_measured.values() if ev["weight"] >= MIN_MAP_WEIGHT]
    scale_map["T08"] = {"source": _quantile_points(source), "target": _quantile_points(target)}
    counts = {"t01_measured": 0, "t08_measured": 0, "mapped_only": 0}
    for pid, doc in players.items():
        inputs = doc["inputs"]
        map_tendency_inputs(inputs, scale_map)
        measured_any = False
        ev = mix_measured.get(pid)
        record = inputs.get("T01")
        mix = _mix(record) if record else None
        if ev and mix and "post" in mix and sum(ev["mix"].values()) > 0:
            post = float(mix["post"])
            total = sum(ev["mix"].values())
            observed = {k: (1.0 - post) * v / total for k, v in ev["mix"].items()}
            share = ev["weight"] / (ev["weight"] + PRIOR_WEIGHT)
            new_mix = {k: (share * observed[k] + (1 - share) * float(mix[k])) if k in observed else float(mix[k]) for k in mix}
            norm = sum(new_mix.values())
            record["value"] = {**record["value"], "rows": [dict(record["value"]["rows"][0],
                                                                  probabilities={k: round(v / norm, 6) for k, v in new_mix.items()})]}
            record["evidence"] = [*(record.get("evidence") or []), {
                "source": f"{CACHE_DIR}/normalized.json (Leaderboards Values)",
                "method": (f"{VERSION}: estimate placed on the measured per-touch scale by rank, then measured rates "
                           f"(shots, drives, shot-creating passes, other passes per touch) blended at share {share:.2f}; "
                           "post share kept from the estimate"),
                "shared_evidence_id": f"bbi:{pid}:T01",
                "notes": "per touch: " + ", ".join(f"{k} {v:.3f}" for k, v in ev["mix"].items()),
            }]
            if share >= 0.5:
                record["status"], record["reason"] = "estimated", "estimated"
            counts["t01_measured"] += 1
            measured_any = True
        ev = inv_measured.get(pid)
        involvement = inputs.get("T08")
        if ev and involvement and isinstance(involvement.get("value"), dict):
            share = ev["weight"] / (ev["weight"] + PRIOR_WEIGHT)
            old = float(involvement["value"]["probability"])
            involvement["value"] = {**involvement["value"], "probability": round(share * ev["value"] + (1 - share) * old, 6)}
            involvement["evidence"] = [*(involvement.get("evidence") or []), {
                "source": f"{CACHE_DIR}/normalized.json (Leaderboards Values)",
                "method": (f"{VERSION}: estimate placed on the measured true-usage scale by rank, then measured true "
                           f"usage {ev['value']:.3f} blended at share {share:.2f}"),
                "shared_evidence_id": f"bbi:{pid}:T08",
                "notes": "true usage = possessions finished plus created for teammates, share of team possessions",
            }]
            if share >= 0.5:
                involvement["status"], involvement["reason"] = "estimated", "estimated"
            counts["t08_measured"] += 1
            measured_any = True
        if not measured_any:
            counts["mapped_only"] += 1
    (Path(root) / SCALE_MAP_FILE).write_text(json.dumps({"version": VERSION, **scale_map}, indent=0) + "\n")
    return counts
