"""What an undrawn pick is worth under the NBA's "3-2-1" lottery, used from the 2027 draft (PICK-REFIT).

The trade code first projects where a pick's original team will finish (``transactions.future_adjusted_pick_slot``:
1 = worst record). Under the old lottery that finish stood in for the draft position. It no longer can: the three
worst records draft 8th on average, behind the seven teams just above them, and every team outside the playoffs, plus
the 7-vs-8 play-in losers, has a real chance at No. 1. So a pick is priced from the finish: which lottery group it puts
the team in, and that group's odds. A finish is only a forecast, more so for later drafts, so nearby finishes count too.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

# Chance of first-round picks 1-16 by lottery group, from the game's own draw (draft.draw_321_lottery, 600,000 draws,
# no team barred). It matches the league's published odds sheet within its rounding (tests/test_pick_lottery_value.py).
SLOT_ODDS = {
    "relegated": (0.054, 0.0549, 0.0556, 0.0567, 0.0579, 0.0595, 0.0602, 0.062, 0.0631, 0.0809, 0.1442, 0.2509,
                  0.0, 0.0, 0.0, 0.0),
    "outside_play_in": (0.081, 0.0799, 0.0785, 0.0771, 0.0754, 0.0737, 0.0718, 0.0695, 0.067, 0.0604, 0.0436, 0.0183,
                        0.07, 0.061, 0.0471, 0.0255),
    "play_in_9_10": (0.054, 0.0548, 0.0561, 0.0568, 0.058, 0.059, 0.0604, 0.0618, 0.0634, 0.0613, 0.0473, 0.0212,
                     0.0879, 0.0924, 0.0927, 0.073),
    "seven_eight_loser": (0.0273, 0.0285, 0.0296, 0.0313, 0.0331, 0.0348, 0.0376, 0.04, 0.044, 0.0446, 0.0365, 0.017,
                          0.0793, 0.1017, 0.1498, 0.265),
}
# League finish (1 = worst record) to lottery group, for two even conferences: worst three, the other seven who miss
# the play-in, the four 9th and 10th seeds, then the two 7-vs-8 losers. Finishes 17-30 pick in record order.
GROUP_BY_FINISH = (("relegated",) * 3 + ("outside_play_in",) * 7 + ("play_in_9_10",) * 4 + ("seven_eight_loser",) * 2)
LOTTERY_PICKS = len(GROUP_BY_FINISH)
TEAMS = 30


@lru_cache(maxsize=1)
def lottery_rules() -> dict[str, Any]:
    from .draft import default_draft_model_config

    return default_draft_model_config()["lottery_321"]


def lottery_applies(draft_year: int) -> bool:
    return int(draft_year) >= int(lottery_rules()["first_draft_year"])


def highest_pick_allowed(canonical: dict[str, Any], team_id: str, draft_year: int) -> int:
    """The league's limits on repeat top picks, from the drafts already held (only the nearest drafts are affected)."""
    from .draft import highest_allowed_pick

    rules = lottery_rules()
    history = {int(year): slots for year, slots in (rules.get("real_own_pick_slots") or {}).items()}
    history.update({int(year): slots for year, slots in (canonical.get("save_own_pick_history") or {}).items()})
    return highest_allowed_pick(history, team_id, int(draft_year), rules)


@lru_cache(maxsize=64)
def _table_value(slot: int) -> float:
    """The trade value of a known first-round draft position."""
    if slot == 1:
        value = 126.0
    elif slot == 2:
        value = 118.0
    elif slot == 3:
        value = 112.0
    elif slot <= 5:
        value = 108.0 - (slot - 4) * 4.5
    elif slot <= 10:
        value = 96.0 - (slot - 6) * 3.0
    elif slot <= 20:
        value = 87.0 - (slot - 10) * 3.1
    else:
        value = 54.0 - (slot - 20) * 2.25
    return min(128.0, max(28.0, value))


def first_round_slot_value(slot: float) -> float:
    """Value of a first-round position; a projection can fall between two positions."""
    low = int(slot)
    share = slot - low
    if share <= 0:
        return _table_value(low)
    return _table_value(low) + (_table_value(low + 1) - _table_value(low)) * share


def slot_for_value(value: float) -> float:
    """The first-round position worth ``value`` (the inverse of first_round_slot_value over picks 1-30)."""
    if value >= _table_value(1):
        return 1.0
    for slot in range(1, TEAMS):
        upper, lower = _table_value(slot), _table_value(slot + 1)
        if value >= lower:
            return slot + (upper - value) / (upper - lower)
    return float(TEAMS)


def finish_spread(distance: int) -> float:
    """How far (in league places) a team's real finish tends to land from its forecast, by years ahead."""
    return min(10.0, 2.0 + 1.3 * distance)


def finish_weights(finish: float, spread: float) -> list[float]:
    """Chance of each league finish 1-30 around the forecast. Mass past either end folds back, so the 30 teams'
    forecasts together don't pile up in the middle of the league."""
    weights = []
    for rank in range(1, TEAMS + 1):
        images = (rank, 1 - rank, 2 * TEAMS + 1 - rank)
        weights.append(sum(math.exp(-0.5 * ((image - finish) / spread) ** 2) for image in images))
    total = sum(weights)
    return [weight / total for weight in weights]


def pick_odds(rank: int, highest: int = 1) -> list[tuple[int, float]]:
    """(draft position, chance) for the team that finishes ``rank``-th worst. A team barred from the top picks takes
    the first position it may hold whenever it is drawn above it."""
    if rank > LOTTERY_PICKS:
        return [(rank, 1.0)]
    odds = list(SLOT_ODDS[GROUP_BY_FINISH[rank - 1]])
    if highest > 1:
        odds[highest - 1] += sum(odds[:highest - 1])
        odds[:highest - 1] = [0.0] * (highest - 1)
    return [(position, chance) for position, chance in enumerate(odds, start=1) if chance > 0]


def second_round_position(rank: int, first: int) -> int:
    """Within the second round: picks 31-46 run opposite to picks 1-16, the playoff teams follow in record order."""
    return LOTTERY_PICKS + 1 - first if rank <= LOTTERY_PICKS else rank


@lru_cache(maxsize=16)
def _first_round_value_by_finish(highest: int) -> tuple[float, ...]:
    out = []
    for rank in range(1, TEAMS + 1):
        odds = pick_odds(rank, highest)
        out.append(sum(chance * _table_value(position) for position, chance in odds) / sum(c for _, c in odds))
    return tuple(out)


@lru_cache(maxsize=1)
def _second_round_position_by_finish() -> tuple[float, ...]:
    out = []
    for rank in range(1, TEAMS + 1):
        odds = pick_odds(rank)
        out.append(sum(chance * second_round_position(rank, position) for position, chance in odds)
                   / sum(c for _, c in odds))
    return tuple(out)


@lru_cache(maxsize=20000)
def lottery_pick_slot(finish: float, distance: int, round_no: int, highest: int = 1) -> float:
    """The projected position (1-30 within the round) to price an undrawn pick at.

    First round: the position whose value equals the pick's average value over finishes and lottery draws (an average
    position would undersell the chance at the very top). Second round: the average position, since value there falls
    evenly from pick to pick.
    """
    weights = finish_weights(finish, finish_spread(distance))
    by_finish = _first_round_value_by_finish(highest) if round_no == 1 else _second_round_position_by_finish()
    expected = sum(weight * value for weight, value in zip(weights, by_finish))
    return round(slot_for_value(expected) if round_no == 1 else expected, 2)


def sample_draft_position(finish: float, deviation: float, quantile: float, round_no: int, highest: int = 1) -> int:
    """One possible position within the round: a finish ``deviation`` places from the forecast, then its lottery."""
    place = finish + deviation
    if place < 0.5:
        place = 1 - place
    elif place > TEAMS + 0.5:
        place = 2 * TEAMS + 1 - place
    rank = int(round(min(TEAMS, max(1, place))))
    odds = pick_odds(rank, highest if round_no == 1 else 1)
    target = quantile * sum(chance for _, chance in odds)
    running = 0.0
    first = odds[-1][0]
    for position, chance in odds:
        running += chance
        if running > target:
            first = position
            break
    return first if round_no == 1 else second_round_position(rank, first)
