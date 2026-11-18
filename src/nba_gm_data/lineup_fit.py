"""Lineup chemistry: the part of a lineup's scoring that is not the sum of its five players.

Fitted to real lineups by scripts/fit_lineup_fit.py (Basketball Index xPoints lineups, 2025-26, every player's own
effect held fixed) and stored in data/canonical/lineup_fit.json. Only the *non-additive* part lives here. What each
player adds on his own (his shooting, his defense) stays in the regular team features. Three effects passed the
fit script's adoption rule (same sign whichever way players are described, clear of noise, and different from what the
game already did):

* creator_x_shooters (offense): each shooter on the floor is worth more when a ball-dominant creator is with him.
  Measured as a change of slope: with a creator on the floor, each shooter above the league's usual number next to a
  creator adds the coefficient and each one below it takes it away. A lineup without a creator gets nothing from this
  term (what a creator is worth on his own belongs to his player ratings, which already carry it).
* five_shooters (offense): the fifth shooter adds less than the fourth (all-shooter lineups get less than the sum).
* non_shooters_beyond_2 (defense): every non-shooter beyond two costs points at the other end too.

The game simulates a team-game from its whole rotation (minutes-weighted), not lineup by lineup. The terms are
therefore *expected* values over the lineups the rotation produces: each player is on the floor for his share of the
game (minutes / 48, renormalized so five are on the floor), independently, and the expectations are exact. A real
five-man lineup (everyone at 48 minutes) gets its exact value. Real coaches stagger non-shooters and creators, so the
fit file carries the measured ratio (actual lineups / independent prediction, 2025-26) that rotations are scaled by.
Everything is centered on the league's average lineup, so league scoring does not move.

Player descriptions use the game's own ratings: spacing (shooting range x three-point volume) and usage.
"""
from __future__ import annotations

import json
import os
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

FIT_PATH = Path(__file__).resolve().parents[2] / "data/canonical/lineup_fit.json"

# Game-rating definitions, chosen to agree with Basketball Index's descriptions of the same 2025-26 players
# (non-shooter 90% possession-weighted agreement, creator 88%; see scripts/fit_lineup_fit.py).
NON_SHOOTER_SPACING = 35.0   # spacing feature (range x three-point volume) below this: defenders can leave him
CREATOR_USAGE = 74.0         # projected usage at or above this: a ball-dominant creator (~25% usage)

EMPTY_FIT: dict[str, Any] = {"version": "none", "offense": {}, "defense": {}, "league_mean": {}, "rotation_ratio": {}}


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return EMPTY_FIT


def fit_coefficients(path: Path | None = None) -> dict[str, Any]:
    if path is None and os.environ.get("NBA_GM_LINEUP_FIT", "").lower() == "off":
        return EMPTY_FIT  # A/B switch for scorecards: the game exactly as it was before the lineup fit
    return _load(str(path or FIT_PATH))


def player_fit_flags(features: dict[str, float], player: dict[str, Any] | None = None) -> dict[str, bool]:
    return {
        "non_shooter": float(features.get("spacing", 50.0)) < NON_SHOOTER_SPACING,
        "creator": float(features.get("usage", 50.0)) >= CREATOR_USAGE,
    }


def poisson_binomial(probabilities: Iterable[float]) -> list[float]:
    dist = [1.0]
    for p in probabilities:
        p = min(1.0, max(0.0, p))
        new = [0.0] * (len(dist) + 1)
        for k, q in enumerate(dist):
            new[k] += q * (1.0 - p)
            new[k + 1] += q * p
        dist = new
    return dist


def on_floor_probabilities(entries: list[tuple[dict[str, bool], float]]) -> list[tuple[dict[str, bool], float]]:
    total = sum(max(0.0, minutes) for _, minutes in entries)
    if total <= 0:
        return []
    scale = 5.0 / total
    return [(flags, min(1.0, max(0.0, minutes) * scale)) for flags, minutes in entries]


def expected_terms(entries: list[tuple[dict[str, bool], float]]) -> dict[str, float]:
    """Expected fit terms for (flags, minutes) when each player is on the floor independently for his share."""
    probs = on_floor_probabilities(entries)
    if not probs:
        return {"non_shooters_beyond_2": 0.0, "five_shooters": 0.0, "creator_x_shooters": 0.0, "creator_on_floor": 0.0}
    non_shooters = poisson_binomial(p for flags, p in probs if flags.get("non_shooter"))
    creator_x_shooters = 0.0
    for j, (flags, p) in enumerate(probs):
        if flags.get("non_shooter") or p <= 0:
            continue
        if flags.get("creator"):
            with_creator = 1.0
        else:
            with_creator = 1.0 - math.prod(1.0 - q for i, (other, q) in enumerate(probs) if i != j and other.get("creator"))
        creator_x_shooters += p * with_creator
    return {
        "non_shooters_beyond_2": sum(q * max(0, k - 2) for k, q in enumerate(non_shooters)),
        "five_shooters": non_shooters[0],
        "creator_x_shooters": creator_x_shooters,  # E[creator on floor x shooters on floor]
        "creator_on_floor": 1.0 - math.prod(1.0 - p for flags, p in probs if flags.get("creator")),
    }


def is_single_lineup(entries: list[tuple[dict[str, bool], float]]) -> bool:
    probs = [p for _, p in on_floor_probabilities(entries)]
    return bool(probs) and all(p < 1e-9 or p > 1 - 1e-9 for p in probs)


def lineup_fit_effect(entries: list[tuple[dict[str, bool], float]], *, coefficients: dict[str, Any] | None = None) -> dict[str, Any]:
    """Non-additive fit for a set of (flags, minutes): a rotation (expected over its lineups) or one five-man lineup.

    offense: points per 100 possessions added to this team's offense. defense: points per 100 possessions added to
    the opponent's offense. Both are centered on the league's average lineup.
    """
    fit = coefficients or fit_coefficients()
    values = expected_terms(entries)
    # Slope, not level: shooters counted relative to the usual number beside a creator, only while a creator plays.
    values["creator_x_shooters"] -= float(fit.get("creator_shooters_mean", 0.0)) * values["creator_on_floor"]
    ratios = {} if is_single_lineup(entries) else fit.get("rotation_ratio", {})
    means = fit.get("league_mean", {})
    result: dict[str, Any] = {"offense": 0.0, "defense": 0.0, "terms": {}}
    for side in ("offense", "defense"):
        for term, coefficient in fit.get(side, {}).items():
            value = values.get(term, 0.0) * float(ratios.get(term, 1.0))
            contribution = float(coefficient) * (value - float(means.get(term, 0.0)))
            result[side] += contribution
            result["terms"][f"{side}:{term}"] = round(contribution, 4)
    result["offense"] = round(result["offense"], 4)
    result["defense"] = round(result["defense"], 4)
    return result
