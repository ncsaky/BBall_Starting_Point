"""Defensive abilities shared by cards, game features and court-zone profiles.

Rim deterrence estimates effective ability, including the size/block/impact
evidence used in trait inference. It is not size-neutral technique to which
another height or position bonus should be added. Activity describes perimeter
mobility/events; neither channel is a complete matchup or team-defense model.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from .utils import clamp

# Cache identity only, not an existing-career compatibility/migration gate.
COMPONENT_VERSION = "defensive_components_2026_11_10"


def rim_response(value: float) -> float:
    """Keep the established low/mid response; reserve a monotone elite tail.

    The old response hit 99 near raw 92 and flattened all stronger estimates.
    A Hermite shoulder keeps value and slope at raw 80, reaches 99 at raw 100
    with slope .25, and has a strictly positive derivative throughout. Raw 90
    remains a strong protector while 96--100 retain distinct effectiveness.
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
