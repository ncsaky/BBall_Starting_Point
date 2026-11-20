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
- rebounds (2026-11-19): defensive rebound positioning (S30), box-out (S31), rebound control (S32), the crash
  tendency (T12), pursue vs box-out (T13), height and wingspan (P01, P02).
- personal fouls (2026-11-19): foul control (S45), steal gambling (T14), contest technique (S37), jump-contest share (T16).
- screen assists (2026-11-19): screen execution (S27), screen-action recognition (S28), screen and roll shares (T11),
  body mass (P04); also the player's screening rating (offense.offensive_profile).
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
# Steal gambling (T14) was tested here (2026-11-19): at the same steal technique it adds nothing (r 0.915 -> 0.922 with a
# negative sign; the technique grades are built from the same steal record), so gambling shows up as fouls
# (FOULS_INPUTS), not extra steals. No team-defence penalty either: teams that gamble more defended better in 2025-26
# (r -0.69 with defensive rating), so the data cannot separate a gambling cost from the skill behind it.
FTA_PER_POINT_INPUTS = {"constant": -0.78847, "log T18": 2.35318, "S24": 0.00939, "log T08": -0.56596}  # r 0.87

# Points per 36: involvement (T08), shoot-first vs pass-first choices (T01 shoot +, pass -), close-range touch (S10)
# and contact seeking (T18, free throws). Sets each player's share of the team's points (sim.distribute_player_lines).
# 2026-11-19 (unused-ratings 2): plus three-point shooting as he shoots it (S.three_mode: the S01-S03 grades weighted by
# his shooting-mode habit T03) and the cutting habit (T09: cutters score more off the ball at the same involvement).
# Without the shooting term, pure shooters were handed fewer points than their own made threes add up to (AJ Green 11.4
# per 36 vs 12.8 real). Out-of-fold r 0.933 -> 0.940, mean abs error 1.45 -> 1.35 (shooting alone: 0.938 / 1.37).
POINTS_INPUTS = {"constant": 3.95082, "log T08": 0.88387, "log T01.pass": -0.27562, "log T01.shoot": 0.2955,
                 "S10": 0.00345, "log T18": 0.33929, "S.three_mode": 0.0024, "log T09": 0.13677}  # r 0.94
# Fallback for new-ratings players without inputs (generated draftees, unmatched box-score names).
POINTS_TRAITS = {"constant": 1.71917, "handle_pressure": 0.0082, "shot_versatility": 0.00591, "rim_pressure": 0.00507,
                 "shooting_range": 0.00155}  # r 0.78

# Rebounds per 36 (2026-11-19): defensive rebound positioning (S30), box-out technique (S31), rebound control (S32), the
# offensive crash tendency (T12), defensive pursuit vs box-out emphasis (T13 pursue), height and wingspan (P01, P02, cm).
# Out-of-fold r 0.94 with real 2025-26 rebounds per 36 (377 players); the height + offensive-rebounding formula the
# engine used is the fallback for players without inputs. Sets each player's share of his team's rebounds.
# Refit 2026-11-20 (overnight ratings review) after defensive-rebound positioning (S30) stopped leaning on Basketball
# Index's crashing skill, which is measured against a position baseline (it ranked Jokic, Gobert and Zubac in the bottom
# 10% and the Thompson twins in the top 3%). The positioning grade now carries real weight (0.0047 -> 0.0072 per point)
# and the pursue habit drops to about nothing. Out-of-fold r 0.94 -> 0.951, mean miss 0.62 rebounds per 36.
REBOUNDS_INPUTS = {"constant": -0.39495, "S30": 0.00723, "S31": 0.00609, "S32": 0.00238, "log T12": 0.42883,
                   "log T13.pursue": -0.01995, "P01": 0.00675, "P02": 0.0026}  # r 0.95
# Screen assists per 36 (scripts/fit_screen_assists.py, 2026-11-19): screens that directly lead to a teammate's made
# shot, Basketball Index 2023-24..2025-26 (471 players). Screen execution (S27) and screen-action recognition (S28) set
# how productive each screen is; the screen and roll shares (T11) how often he screens; body mass (P04, kg) how much a
# screen frees the handler. Out-of-fold r 0.85. A +15 screen-execution grade is ~+26% screen assists.
SCREEN_ASSISTS_INPUTS = {"constant": -3.73464, "S27": 0.01536, "S28": 0.02713, "log T11.screen": 1.00312,
                         "log T11.roll": 0.73724, "P04": 0.03457}  # r 0.85

# Personal fouls per 36 (2026-11-19, unused-ratings 2): foul-control technique (S45) lowers them; steal / disruption
# gambling (T14) and jumping at contests (T16 jump share) raise them; so does contest technique (S37: the players who
# contest the most shots, mostly rim protectors, foul more). Real 2025-26 box-score fouls of 377 rotation players
# (data/research/game_boxscores_2025_26.json). Out-of-fold r 0.84 (foul control alone 0.64). Height, strength (P08) and
# jump capacity (P10) add nothing once these are in. Sets each player's foul rate, and so his foul trouble.
FOULS_INPUTS = {"constant": 2.78982, "S45": -0.01693, "log T14": 0.6912, "S37": 0.00385, "log T16.jump": 0.22592}  # r 0.84

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
    # Three-point shooting as he actually shoots it: the catch-and-shoot, pull-up and movement three grades (S01-S03)
    # weighted by how often he takes each kind (shooting-mode habit, T03).
    modes = (("catch", "S01"), ("pull_up", "S02"), ("movement", "S03"))
    if all(f"T03.{mode}" in out and grade in out for mode, grade in modes):
        total = sum(out[f"T03.{mode}"] for mode, _ in modes)
        if total > 0:
            out["S.three_mode"] = sum(out[f"T03.{mode}"] * out[grade] for mode, grade in modes) / total
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


# One player's input records are read by several rate models in a row (points, turnovers, steals, free throws), for
# every player in every game and valuation. The records handed out by ratings_model are shared, read-only objects
# (base records, or one cached record per accumulated development), so each record object's flattened numbers and
# rates are kept by identity, holding a reference so the id stays unique. Bounded: the oldest entry goes first.
_FLAT_CACHE: dict[int, tuple[Mapping[str, Any], dict[str, float], dict[tuple, float | None]]] = {}
_FLAT_CACHE_LIMIT = 4096


def _flat_entry(inputs: Mapping[str, Any]) -> tuple[Mapping[str, Any], dict[str, float], dict[tuple, float | None]]:
    cached = _FLAT_CACHE.get(id(inputs))
    if cached is not None and cached[0] is inputs:
        return cached
    cached = (inputs, flatten_inputs(inputs), {})
    if len(_FLAT_CACHE) >= _FLAT_CACHE_LIMIT:
        _FLAT_CACHE.pop(next(iter(_FLAT_CACHE)))
    _FLAT_CACHE[id(inputs)] = cached
    return cached


def _flat(inputs: Mapping[str, Any]) -> dict[str, float]:
    return _flat_entry(inputs)[1]


def _from_inputs(model: Mapping[str, float], inputs: Mapping[str, Any] | None, low: float, high: float) -> float | None:
    if not inputs:
        return None
    _, flat, rates = _flat_entry(inputs)
    key = (id(model), low, high)   # the rate models are module constants
    if key not in rates:
        rate = _log_linear(model, flat)
        rates[key] = None if rate is None else round(clamp(rate, low, high), 4)
    return rates[key]


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


def rebounds_per36_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    if not REBOUNDS_INPUTS:
        return None
    return _from_inputs(REBOUNDS_INPUTS, inputs, 1.0, 20.0)


def fouls_per36_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    return _from_inputs(FOULS_INPUTS, inputs, 0.8, 8.0)


def screen_assists_per36_from_inputs(inputs: Mapping[str, Any] | None) -> float | None:
    return _from_inputs(SCREEN_ASSISTS_INPUTS, inputs, 0.01, 20.0)


# Shooters' points follow their own shots (2026-11-19, win-pick and shooters task). The points fit above reads
# involvement and shot choices; for a player who takes most of his shots from three it handed out fewer points than his
# own threes make (AJ Green 11.8 per 36 against 12.8 real; his threes alone are 10.7), so his box score ran out of points
# before his made threes and turned them into two-point attempts (true shooting .495 vs .627). The engine already sets
# each player's three-point attempts and percentage (his shooting profile); his shot-location habit (T02 three share,
# r 0.996 with his real share of threes) says how many two-pointers come with them. Those shots, at his own
# percentages, plus the free throws per point, are the points his shots produce. A player's expected points are a
# geometric blend of the fit and his shots, weighted by his three share: none below SHOT_POINTS_RAMP[0], all at
# SHOT_POINTS_RAMP[1] and above. Fitted on 377 rotation players' real 2025-26 points per 36
# (output/winpick-shooters/fit_shooter_points.py): mean error 1.31 -> 1.15; players whose threes make 70%+ of their
# fitted points -0.87 -> +0.27. Box score only (who scores); team scores never read it.
SHOT_POINTS_RAMP = (0.30, 0.75)


def shot_points_blend(fit: float, three_share: float | None, three_per36: float, three_pct: float, two_pct: float,
                      fta_per_point: float | None, ft_pct: float) -> float:
    """Expected points per 36 for the box score: the points fit blended with the points his own shots produce."""
    low, high = SHOT_POINTS_RAMP
    if three_share is None or fit <= 0 or three_share <= low:
        return fit
    share = min(0.95, max(0.05, float(three_share)))
    twos = three_per36 * (1.0 - share) / share
    free = min(0.5, max(0.0, float(fta_per_point or 0.0)) * ft_pct * 0.98)
    shots = (3.0 * three_per36 * three_pct + 2.0 * twos * two_pct) / (1.0 - free)
    if shots <= 0:
        return fit
    weight = min(1.0, (float(three_share) - low) / (high - low))
    return clamp(fit ** (1.0 - weight) * shots ** weight, 3.0, 40.0)


def tendency_from_inputs(inputs: Mapping[str, Any] | None, key: str) -> float | None:
    """One propensity input's probability (e.g. T04 shot difficulty tolerance), or None."""
    if not inputs:
        return None
    return _flat(inputs).get(key)


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
