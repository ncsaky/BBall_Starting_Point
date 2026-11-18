"""Playmaking and on-ball / help defense by court zone (2026-11-19).

Three per-player effects behind the player card's extra court charts:

* Playmaking: how much better (or worse) his teammates shoot, by zone, while he is on the court. Its overall size
  is fitted to Basketball Index's "Offensive eFG% Impact on Teammates" from the game's own ratings
  (scripts/fit_court_influence.py; out-of-fold r 0.59). Where it lands follows the mechanism: passing reads feed
  the rim (lobs, cuts) and the corners, drives collapse the defense and kick out to the corners and wings, shooting
  gravity opens the paint, a pick-and-roll handle feeds the roller and the wings. The sim uses this: team profiles
  add each player's playmaking for his teammates' shots (spatial.team_spatial_profile).
* On-ball and help defense: a split of the engine's existing zone suppression (defense.zone_defense), not a new
  effect. Help gets most of the rim-deterrence and scheme-IQ terms; on-ball gets most of lateral quickness and
  screen navigation. On-ball + help equals the displayed overall defense exactly.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping

from .resource_paths import game_resource_root
from .utils import clamp

FIT_FILE = "data/canonical/court_influence_fit.json"
GROUPS = ("rim", "midrange", "corner_three", "above_break_three")
# League shot share by zone group (2025-26 NBA, shot_chart_model league zones).
LEAGUE_GROUP_FREQUENCY = {"rim": 0.465, "midrange": 0.115, "corner_three": 0.106, "above_break_three": 0.314}
# Where each rating's benefit to teammates lands (shares of its effect by zone group).
MECHANISM_ZONES = {
    "passing_reads": {"rim": 0.40, "midrange": 0.10, "corner_three": 0.30, "above_break_three": 0.20},
    "rim_pressure": {"rim": 0.15, "midrange": 0.10, "corner_three": 0.45, "above_break_three": 0.30},
    "shooting_range": {"rim": 0.60, "midrange": 0.20, "corner_three": 0.05, "above_break_three": 0.15},
    "handle_pressure": {"rim": 0.35, "midrange": 0.15, "corner_three": 0.15, "above_break_three": 0.35},
    "shot_versatility": {"rim": 0.30, "midrange": 0.20, "corner_three": 0.20, "above_break_three": 0.30},
    "height": dict(LEAGUE_GROUP_FREQUENCY),
}
TEAMMATE_SHOT_SHARE = 0.8      # share of the team's shots taken by his teammates while he is on the court
PP_PER_GRADE = 0.35            # zone grade point -> FG percentage points (same scale as the shot chart)
MAX_ZONE_LIFT = 8.0

# Help share of each term in defense.zone_defense (the rest is on-ball). Rim protection and scheme reads are mostly
# rotations; lateral quickness and screen navigation are mostly about the man he guards.
HELP_SHARE = {"rim": 0.70, "scheme": 0.70, "effort": 0.40, "lateral": 0.15, "navigation": 0.10}
# Coefficients of each term per zone group, mirroring defense.zone_defense.
DEFENSE_TERMS = {
    "rim": {"rim": 0.58, "scheme": 0.12},
    "midrange": {"scheme": 0.30, "lateral": 0.18, "effort": 0.14},
    "perimeter": {"navigation": 0.30, "lateral": 0.23, "effort": 0.15, "scheme": 0.08},
}
# Typical rotation player's defensive terms (2026-27 rosters, inputs ratings), the zero point of the split.
LEAGUE_DEFENSE_MEANS = {"rim": 59.0, "scheme": 61.8, "effort": 64.2, "lateral": 63.3, "navigation": 61.6}   # minutes-weighted, both rating sets averaged


@lru_cache(maxsize=2)
def _fit(path: str) -> dict[str, Any] | None:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else None


def load_fit() -> dict[str, Any] | None:
    return _fit(str(game_resource_root() / FIT_FILE))


def zone_group(zone_key: str) -> str:
    if zone_key in ("restricted_area", "paint_non_ra"):
        return "rim"
    if zone_key.startswith("corner_three"):
        return "corner_three"
    if zone_key.startswith("above_break"):
        return "above_break_three"
    return "midrange"


def playmaking_by_group(get: Callable[[str], float], height: float) -> dict[str, float]:
    """Teammates' FG% change (percentage points, vs a typical player) by zone group while he is on the court."""
    fit = load_fit()
    if not fit:
        return {group: 0.0 for group in GROUPS}
    lift = {group: 0.0 for group in GROUPS}
    for key, spec in fit["features"].items():
        value = height if key == "height" else get(key)
        contribution = spec["pp_per_sd"] * (value - spec["mean"]) / (spec["sd"] or 1.0)
        for group, share in MECHANISM_ZONES[key].items():
            lift[group] += contribution * share / LEAGUE_GROUP_FREQUENCY[group]
    return {group: round(clamp(value, -MAX_ZONE_LIFT, MAX_ZONE_LIFT), 3) for group, value in lift.items()}


def overall_playmaking(by_group: Mapping[str, float]) -> float:
    """Shot-weighted overall change in teammates' FG% (percentage points)."""
    return round(sum(LEAGUE_GROUP_FREQUENCY[g] * float(by_group.get(g, 0.0)) for g in GROUPS), 3)


def team_playmaking_grade(weighted_lifts: list[tuple[Mapping[str, float], float]], total_weight: float, group: str) -> float:
    """Zone-grade points added to a team's shooting in one zone group by its players' playmaking.

    Each player's lift applies to his teammates' shots while he plays: sum over players of (minutes / 48) x lift x
    teammates' share of shots. With rotation minutes as weights (about 240 a game), that is 5 x the weighted mean."""
    if total_weight <= 0:
        return 0.0
    mean = sum(float(lifts.get(group, 0.0)) * weight for lifts, weight in weighted_lifts) / total_weight
    return 5.0 * mean * TEAMMATE_SHOT_SHARE / PP_PER_GRADE


def help_suppression_delta(get: Callable[[str], float]) -> dict[str, float]:
    """Help part of the player's zone defense, as FG percentage points held below league (positive = better)."""
    from .defense import rim_response
    values = {
        "rim": rim_response(get("rim_deterrence")), "scheme": get("scheme_iq"), "effort": get("defensive_effort"),
        "lateral": get("foot_speed_lateral_agility"), "navigation": get("screen_navigation"),
    }
    out = {}
    for group, terms in DEFENSE_TERMS.items():
        grade = sum(coef * HELP_SHARE[name] * (values[name] - LEAGUE_DEFENSE_MEANS[name]) for name, coef in terms.items())
        out[group] = round(grade * PP_PER_GRADE, 3)
    return out


def defense_group(zone_key: str) -> str:
    group = zone_group(zone_key)
    return "perimeter" if group in ("corner_three", "above_break_three") else group


def reweight(density: list[float], factors: list[float]) -> list[float]:
    values = [max(0.0, d) * f for d, f in zip(density, factors)]
    total = sum(values) or 1.0
    return [v / total for v in values]


def damped(delta_pp: float, per_pp: float) -> float:
    return math.exp(clamp(per_pp * delta_pp, -0.6, 0.6))
