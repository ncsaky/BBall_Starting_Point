"""Defensive abilities shared by cards, game features and court-zone profiles.

Rim deterrence estimates effective ability, including the size/block/impact
evidence used in trait inference. It is not size-neutral technique to which
another height or position bonus should be added. Activity describes perimeter
mobility/events; neither channel is a complete matchup or team-defense model.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, NamedTuple

from .utils import clamp

# Cache identity only, not an existing-career compatibility/migration gate.
COMPONENT_VERSION = "defensive_components_2026_11_18"
RESPONSE_FIT_FILE = "data/canonical/rim_response_fit.json"


def legacy_rim_response(value: float) -> float:
    """The pre-2026-11-18 response: kept as the low/mid part of rim_response and for the fit script.

    It hit 99 near raw 92 and its Hermite shoulder (value and slope matched at raw 80, 99 at raw 100 with slope .25)
    squeezed every trait value above ~90 into 95-99, so the top ~30 rim protectors were nearly tied.
    """
    raw = clamp(float(value), 1.0, 100.0)
    if raw <= 80.0:
        return raw + max(0.0, raw - 68.0) ** 1.18 * .18
    start = 80.0 + 12.0 ** 1.18 * .18
    slope = 1.0 + .18 * 1.18 * 12.0 ** .18
    t = (raw - 80.0) / 20.0
    return ((2*t**3 - 3*t**2 + 1)*start
            + (t**3 - 2*t**2 + t)*20.0*slope
            + (-2*t**3 + 3*t**2)*99.0
            + (t**3 - t**2)*20.0*.25)


@lru_cache(maxsize=2)
def _response_fit(path: str) -> tuple[tuple[float, float], ...] | None:
    file = Path(path)
    if not file.exists():
        return None
    knots = json.loads(file.read_text()).get("knots") or []
    return tuple((float(x), float(y)) for x, y in knots) if len(knots) >= 2 else None


def response_knots() -> tuple[tuple[float, float], ...] | None:
    from .resource_paths import game_resource_root
    return _response_fit(str(game_resource_root() / RESPONSE_FIT_FILE))


def rim_response(value: float) -> float:
    """Effective rim protection from the rim_deterrence trait, shaped by real rim evidence at the top.

    Up to the 75th league percentile of the trait (raw ~74) this is the long-standing response, which already
    matched the real spread of opponents' rim FG% against expectation. Above it, the trait's league rank is mapped
    onto the real distribution of that measure (Basketball Index, sample-size shrunk; scripts/fit_rim_protection.py),
    at the exchange rate fitted on the bulk. The old shoulder flattened every value above ~90 into 95-99; the real
    distribution keeps spreading, so elite protectors are now distinct. Monotone, never clipped at the top: past the
    last knot it continues on the last segment's slope (rescale, don't clip).
    """
    raw = max(float(value), 1.0)
    knots = response_knots()
    if not knots or raw <= knots[0][0]:
        return legacy_rim_response(raw)
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if raw <= x1:
            return y0 + (y1 - y0) * (raw - x0) / (x1 - x0)
    (x0, y0), (x1, y1) = knots[-2], knots[-1]
    return y1 + (y1 - y0) * (raw - x1) / (x1 - x0)


class DefensiveComponents(NamedTuple):
    activity: float
    rim: float
    skill: float


def defensive_components(get: Callable[[str], float]) -> DefensiveComponents:
    """Use the same activity/rim abilities and 60/40 blend as matchup grading.

    Skill excludes minutes, reputation, offensive impact and the neutral
    weak-link targeting value. Scheme IQ still affects spatial help/contests,
    passing and IQ; it is not an extra independent event-creation observation.
    """
    activity = (get('defensive_effort')*.42
                + get('foot_speed_lateral_agility')*.36
                + get('screen_navigation')*.22)
    rim = rim_response(get('rim_deterrence'))
    return DefensiveComponents(activity, rim, clamp(activity*.6 + rim*.4, 1, 99))


def zone_defense(get: Callable[[str], float]) -> dict[str, tuple[float, float]]:
    """Untextured (suppression, contest) abilities on the existing zone scale.

    Existing perimeter/help coefficients are retained. Rim uses the same
    effective response as game features, without a second physical-size bonus.
    Court texture, opponent shot diet, health and minutes belong to callers.
    """
    effort = get('defensive_effort')
    scheme = get('scheme_iq')
    lateral = get('foot_speed_lateral_agility')
    navigation = get('screen_navigation')
    rim = rim_response(get('rim_deterrence'))
    return {
        'rim': (22 + rim*.58 + scheme*.12, 20 + rim*.55 + effort*.14),
        'midrange': (24 + scheme*.30 + lateral*.18 + effort*.14,
                     22 + scheme*.27 + lateral*.23 + effort*.14),
        'perimeter': (20 + navigation*.30 + lateral*.23 + effort*.15 + scheme*.08,
                      18 + navigation*.32 + lateral*.25 + effort*.15),
    }


def contest_jump_share(inputs: Mapping[str, Any] | None) -> float | None:
    """The player's chosen share of contests where he leaves his feet (T16 "jump"), new-ratings mode only."""
    try:
        rows = inputs["T16"]["value"]["rows"]
        return sum(float(row["probabilities"].get("jump", 0.0)) for row in rows) / len(rows)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def block_rate_per36(rim: float, jump: float | None = None) -> float:
    """Expected blocks per 36 minutes from effective rim protection and, when known, the contest-jump choice.

    Fitted to real 2025-26 blocks per 36 (377 players with 500+ minutes; scripts/fit_block_rate.py, log-linear,
    minutes-weighted, mean matched). Rim only (legacy ratings, with a squared term: --quadratic): weighted r 0.77. With the T16 jump share (new
    ratings): r 0.86. Blocks are skill times choice: a positional defender who stays down (Jokic) blocks few shots.
    """
    if jump is None:
        return max(0.02, math.exp(-1.373334 + 0.010133 * rim + 0.96891 * (rim / 100.0) ** 2) - 0.05)
    return max(0.02, math.exp(-2.65164 + 0.013747 * rim + 5.956339 * jump) - 0.05)


def poisson_count(u: float, mean: float) -> int:
    """Inverse-CDF Poisson draw from one uniform number (keeps the box score's one draw per player)."""
    if mean <= 0:
        return 0
    k, p = 0, math.exp(-mean)
    cumulative = p
    while u > cumulative and k < 30:
        k += 1
        p *= mean / k
        cumulative += p
    return k
