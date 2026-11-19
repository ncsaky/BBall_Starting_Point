"""Per-player box-score rates: turnovers, assists, steals and free-throw attempts.

These decide how a team's box-score events are shared between its players. They never change game scores.

Each rate is a log-linear fit (scripts/fit_box_stat_rates.py, 2026-11-18) to real 2025-26 per-36 rates of the
rotation players in data/calibration/nba_2025_26_targets.json, checked out of fold. New-ratings saves read the
approved player inputs directly; players without inputs (old-ratings saves, generated draftees) use a fit on
the 15 legacy traits. The league-wide level is then set by the box-score code, so these rates mainly decide
who gets the events.

Inputs used (see docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md):
- turnovers: offensive involvement (T08) and passing risk appetite (T07) raise them; dribble manipulation (S16)
  and handle security (S17) lower them at the same involvement.
- assists: pass choice share (T01 pass), involvement (T08), passing delivery (average of the nine passing
  families' execution grades), passing risk appetite (T07) and post-hub decisions (T01 post: passing out of the
  post, e.g. Jokic or Sengun).
- steals: passing-lane interception technique (S43) and on-ball steal technique (S42).
- free-throw attempts per point scored: contact seeking (T18) and foul-drawing craft (S24); high-involvement
  players score relatively more of their points from the field (T08 lowers the per-point rate).
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .utils import clamp

PASS_FAMILIES = tuple(f"F0{i}" for i in range(1, 10))

# log(rate) = constant + sum(coefficient * value); values are 0-100 grades, or logs of tendency probabilities.
# Out-of-fold correlation with real 2025-26 rates (377 players with 500+ minutes) in the comments.
TURNOVERS_INPUTS = {"constant": 3.37798, "log T08": 0.78791, "log T07": 0.92858, "S16": -0.00457, "S17": -0.0111}  # r 0.85
ASSISTS_INPUTS = {"constant": 3.05475, "log T01.pass": 0.7642, "log T08": 0.28271, "F.execution": 0.02663,
                  "log T07": 0.5197, "log T01.post": 0.21179}  # r 0.95 (previous fit 0.91)
STEALS_INPUTS = {"constant": -0.76884, "S43": 0.01181, "S42": 0.00667}  # r 0.92
FTA_PER_POINT_INPUTS = {"constant": -0.78847, "log T18": 2.35318, "S24": 0.00939, "log T08": -0.56596}  # r 0.87

# Points per 36: involvement (T08), shoot-first vs pass-first choices (T01 shoot +, pass -), close-range touch (S10)
# and contact seeking (T18, free throws). Sets each player's share of the team's points (sim.distribute_player_lines).
POINTS_INPUTS = {"constant": 3.86525, "log T08": 0.88789, "log T01.pass": -0.29853, "log T01.shoot": 0.3423,
                 "S10": 0.00396, "log T18": 0.31019}  # r 0.93
# Fallback for new-ratings players without inputs (generated draftees, unmatched box-score names).
POINTS_TRAITS = {"constant": 1.71917, "handle_pressure": 0.0082, "shot_versatility": 0.00591, "rim_pressure": 0.00507,
                 "shooting_range": 0.00155}  # r 0.78

TURNOVERS_TRAITS ={"constant": -0.26686, "passing_reads": 0.01344, "rim_pressure": 0.01062, "scheme_iq": -0.00717}  # r 0.67
# The old traits carry little steal signal (the engine's former defensive-activity formula: r 0.38). Effort and
# screen navigation raise steals; rim protectors (rim_deterrence) stay home and get fewer.
STEALS_TRAITS = {"constant": -0.20996, "defensive_effort": 0.00604, "screen_navigation": 0.00423, "rim_deterrence": -0.00382}  # r 0.44
FTA_PER_POINT_TRAITS = {"constant": -2.16346, "rim_pressure": 0.01898, "shooting_range": -0.00913}  # r 0.55


def flatten_inputs(inputs: Mapping[str, Any]) -> dict[str, float]:
    """One number per input: technique grades, tendency probabilities (with action/shot mixes split out)."""
    out: dict[str, float] = {}
    for key, record in inputs.items():
        value = (record or {}).get("value") or {}
        try:
            if "grade" in value:
                out[key] = float(value["grade"])
            elif "display_grade" in value:
                out[key] = float(value["display_grade"]["grade"])
            elif value.get("measurements"):
                out[key] = float(value["measurements"][0]["value"])
            elif "probability" in value:
                out[key] = float(value["probability"])
            elif value.get("rows"):
                for name, probability in value["rows"][0]["probabilities"].items():
                    out[f"{key}.{name}"] = float(probability)
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    executions = [out[f"{family}.execution"] for family in PASS_FAMILIES if f"{family}.execution" in out]
    if len(executions) == len(PASS_FAMILIES):
        out["F.execution"] = sum(executions) / len(executions)
    return out


def _log_linear(model: Mapping[str, float], values: Mapping[str, float]) -> float | None:
    total = model["constant"]
    for key, coefficient in model.items():
        if key == "constant":
            continue
        name = key[4:] if key.startswith("log ") else key
        if name not in values:
            return None
        value = float(values[name])
        if key.startswith("log "):
            if value <= 0:
                return None
            value = math.log(value)
        total += coefficient * value
    return math.exp(total)


# One player's input records are read by several rate models in a row (points, turnovers, steals, free throws).
# The records handed out by ratings_model are shared, read-only objects, so the flattened numbers are kept for the
# last eight record objects (by identity, holding a reference so the id stays unique).
_FLAT_CACHE: dict[int, tuple[Mapping[str, Any], dict[str, float]]] = {}


def _flat(inputs: Mapping[str, Any]) -> dict[str, float]:
    cached = _FLAT_CACHE.get(id(inputs))
    if cached is not None and cached[0] is inputs:
        return cached[1]
    flat = flatten_inputs(inputs)
    if len(_FLAT_CACHE) >= 8:
        _FLAT_CACHE.pop(next(iter(_FLAT_CACHE)))
    _FLAT_CACHE[id(inputs)] = (inputs, flat)
    return flat


def _from_inputs(model: Mapping[str, float], inputs: Mapping[str, Any] | None, low: float, high: float) -> float | None:
    if not inputs:
        return None
    rate = _log_linear(model, _flat(inputs))
    return None if rate is None else round(clamp(rate, low, high), 4)


def points_per36_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    return _from_inputs(POINTS_INPUTS, inputs, 3.0, 40.0)


def turnovers_per36_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    return _from_inputs(TURNOVERS_INPUTS, inputs, 0.4, 7.0)


def assists_per36_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    return _from_inputs(ASSISTS_INPUTS, inputs, 0.5, 16.0)


def steals_per36_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    return _from_inputs(STEALS_INPUTS, inputs, 0.2, 4.0)


def fta_per_point_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    return _from_inputs(FTA_PER_POINT_INPUTS, inputs, 0.03, 0.75)


def _trait_value(traits: Mapping[str, Any], key: str) -> float:
    value = traits.get(key, 50.0)
    if isinstance(value, Mapping):
        value = value.get("value", 50.0)
    return float(value if value is not None else 50.0)


def _from_traits(model: Mapping[str, float], traits: Mapping[str, Any], low: float, high: float) -> float:
    values = {key: _trait_value(traits, key) for key in model if key != "constant"}
    return round(clamp(_log_linear(model, values) or low, low, high), 4)


def points_per36_from_traits(traits: Mapping[str, Any]) -> float:
    return _from_traits(POINTS_TRAITS, traits, 3.0, 40.0)


def turnovers_per36_from_traits(traits: Mapping[str, Any]) -> float:
    return _from_traits(TURNOVERS_TRAITS, traits, 0.4, 7.0)


def steals_per36_from_traits(traits: Mapping[str, Any]) -> float:
    return _from_traits(STEALS_TRAITS, traits, 0.2, 4.0)


def fta_per_point_from_traits(traits: Mapping[str, Any]) -> float:
    return _from_traits(FTA_PER_POINT_TRAITS, traits, 0.03, 0.75)


def poisson_quantile(mean: float, u: float) -> int:
    """Poisson draw by inverse CDF from one uniform number in [0, 1).

    Lets the box score turn an existing single random draw into a count with the right mean and spread, so the
    game's random stream (and therefore every score) is unchanged.
    """
    mean = max(0.0, float(mean))
    if mean <= 0.0:
        return 0
    u = min(max(float(u), 0.0), 1.0 - 1e-12)
    probability = math.exp(-mean)
    cumulative = probability
    count = 0
    while u >= cumulative and count < 200:
        count += 1
        probability *= mean / count
        cumulative += probability
    return count


def normal_to_uniform(z: float) -> float:
    """Standard-normal draw -> uniform in (0, 1), for code paths whose RNG call is a Gaussian."""
    return 0.5 * (1.0 + math.erf(float(z) / math.sqrt(2.0)))
