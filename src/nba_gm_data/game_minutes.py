"""The coach's in-game minutes decisions for a generated (sandbox) game: foul trouble and blowout rest.

The pre-game plan (the coach's rotation, or the GM's rough targets for a human team) is what a player would play in a
close game. Real coaches then react to the game itself. Measured on real 2025-26 regular-season box scores
(docs/agents/tasks/heavy-minutes.md):

* Blowouts. Players averaging 28+ minutes played 1.5 more than their season average in games decided by 0-5 points
  and 3.8 fewer in games decided by 21+ (5.3 fewer than in a close game); deep reserves who otherwise sit get those
  minutes. About one game in five ends 21+ apart.
* Foul trouble. A regular fouls out in 1.6% of his games; with 5 fouls he plays about half a minute less, and a
  foul-out costs about two minutes against a similar game. The coach sits a player whose fouls run ahead of pace, and
  players foul less once they carry four or five.

The game's final score is drawn before this runs, so minutes respond to the margin; points and other box-score
counts are then shared out over the minutes actually played. Every team still plays 240 regulation minutes.
"""
from __future__ import annotations

import math
import random
from typing import Any

from .utils import clamp

# Personal fouls per 36 on-court minutes (same league rate as sim.assign_personal_fouls).
FOUL_RATE_PER_36 = 2.95
# Players foul less once in trouble: rate multiplier for the 5th and 6th foul.
FOUL_CAUTION = {4: 0.7, 5: 0.4}
# The coach sits a player whose k-th foul arrives before this share of his planned minutes...
FOUL_PACE = ((2, 0.2), (3, 0.4), (4, 0.6), (5, 0.8))
# ...for this share of the minutes he is ahead of pace.
FOUL_SIT_SHARE = 0.5
FOUL_HORIZON = 60.0
# Share of his remaining planned minutes a player loses when he fouls out (real foul-outs cost about two minutes).
FOUL_OUT_SHARE = 0.5
FOUL_LIMIT = 6

# Game-clock minutes of garbage time by final margin (piecewise linear), fitted so regulars' minutes by margin match
# real 2025-26 (see module docstring). Each game's coach varies it by +-40%.
GARBAGE_POINTS = ((5.0, 0.0), (10.0, 0.7), (15.0, 1.8), (20.0, 4.0), (30.0, 6.2), (40.0, 8.5))
GARBAGE_SPREAD = 0.4
# Deep reserves enter only once garbage time is long enough to matter.
GARBAGE_EXTRAS_MIN = 2.0
GARBAGE_EXTRAS_LIMIT = 4
MAX_GAME_MINUTES = 42.0
# In-game injuries: the injured player's remaining minutes go to the bench first (foul_gain_weight) and to his own
# position first; a player three or more spots away keeps this share of a same-position player's claim.
INJURY_OTHER_POSITION = 0.35
POSITION_NUMBERS = {"PG": 1.0, "G": 1.5, "SG": 2.0, "GF": 2.5, "SF": 3.0, "F": 3.5, "PF": 4.0, "FC": 4.5, "C": 5.0}


def position_number(player: dict[str, Any]) -> float:
    """Point guard 1 ... center 5 (combo labels in between)."""
    pos = str(player.get("position") or "").upper().replace("-", "").replace("/", "")
    if pos in POSITION_NUMBERS:
        return POSITION_NUMBERS[pos]
    found = [POSITION_NUMBERS[p] for p in ("PG", "SG", "SF", "PF", "C") if p in pos]
    return sum(found) / len(found) if found else 3.0


def garbage_minutes(margin: float) -> float:
    m = abs(float(margin))
    points = GARBAGE_POINTS
    if m <= points[0][0]:
        return 0.0
    for (lo, lo_g), (hi, hi_g) in zip(points, points[1:]):
        if m <= hi:
            return lo_g + (hi_g - lo_g) * (m - lo) / (hi - lo)
    return points[-1][1]


def core_share(minutes: float) -> float:
    """How fully a player sits during garbage time: rotation regulars all the way, bench players not at all."""
    return clamp((minutes - 14.0) / 18.0, 0.0, 1.0)


def garbage_gain_weight(minutes: float) -> float:
    if minutes < 12.0:
        return 1.0
    if minutes < 20.0:
        return 0.6
    if minutes < 26.0:
        return 0.25
    return 0.0


def foul_gain_weight(minutes: float) -> float:
    return clamp((32.0 - minutes) / 20.0, 0.2, 1.0)


def draw_foul_times(rng: random.Random, rate_multiplier: float) -> list[float]:
    """On-court minutes at which a player commits each of his fouls (at most six)."""
    rate = FOUL_RATE_PER_36 * rate_multiplier / 36.0
    elapsed = 0.0
    times: list[float] = []
    while len(times) < FOUL_LIMIT:
        elapsed += rng.expovariate(rate * FOUL_CAUTION.get(len(times), 1.0))
        if elapsed > FOUL_HORIZON:
            break
        times.append(elapsed)
    return times


def foul_trouble_minutes(planned: float, times: list[float]) -> tuple[float, bool]:
    """Minutes left after the coach reacts to foul trouble, and whether the player fouled out."""
    if planned <= 0:
        return planned, False
    lost = 0.0
    for count, pace in FOUL_PACE:
        if len(times) >= count and times[count - 1] < pace * planned:
            lost = max(lost, FOUL_SIT_SHARE * (pace * planned - times[count - 1]))
    minutes = planned - lost
    if len(times) >= FOUL_LIMIT and times[FOUL_LIMIT - 1] < minutes:
        # He has been held back until late, so fouling out costs part of what was left, not all of it.
        return minutes - FOUL_OUT_SHARE * (minutes - times[FOUL_LIMIT - 1]), True
    return minutes, False


def _hand_out(minutes: list[float], amount: float, weights: list[float], caps: list[float]) -> float:
    """Add `amount` across players by weight without passing each cap; returns what could not be placed."""
    for _ in range(4):
        open_ = [i for i, w in enumerate(weights) if w > 0 and minutes[i] < caps[i] - 1e-9]
        total = sum(weights[i] for i in open_)
        if amount <= 1e-9 or total <= 0:
            break
        placed = 0.0
        for i in open_:
            add = min(amount * weights[i] / total, caps[i] - minutes[i])
            minutes[i] += add
            placed += add
        amount -= placed
    return max(0.0, amount)


def manage_game_minutes(
    pool: list[dict[str, Any]],
    reserves: list[dict[str, Any]],
    margin: float,
    rng: random.Random,
    foul_rng: random.Random,
    foul_rate_multiplier: float = 1.0,
) -> tuple[list[dict[str, Any]], dict[str, list[float]], set[str]]:
    """Apply foul trouble and blowout rest to one team's planned minutes.

    Returns the playing pool (reserves who got in are appended), each player's foul times and who fouled out.
    """
    items = list(pool) + list(reserves)
    planned = [max(0.0, float(item.get("minutes") or 0.0)) for item in items]
    if sum(planned) <= 0 or sum(m > 0 for m in planned) < 5:
        return pool, {}, set()
    in_pool = len(pool)
    fouls = {item["player"]["id"]: draw_foul_times(foul_rng, foul_rate_multiplier) for item in items}
    minutes = list(planned)
    fouled_out: set[str] = set()
    troubled = [False] * len(items)
    for i, item in enumerate(items):
        if planned[i] <= 0:
            continue
        left, out = foul_trouble_minutes(planned[i], fouls[item["player"]["id"]])
        minutes[i] = left
        troubled[i] = left < planned[i] - 1e-9
        if out:
            fouled_out.add(item["player"]["id"])
    foul_freed = sum(planned) - sum(minutes)
    # Hurt during the game: he leaves after his share of the minutes he would have played (health.v2 injury draw).
    injured: set[str] = set()
    injury_freed: list[tuple[int, float]] = []
    for i, item in enumerate(items):
        share = item.get("health_injury_exit")
        if share is None or planned[i] <= 0:
            continue
        left = min(minutes[i], planned[i] * clamp(float(share), 0.0, 1.0))
        injury_freed.append((i, minutes[i] - left))
        minutes[i] = left
        troubled[i] = True
        injured.add(item["player"]["id"])
    caps = [0.0 if troubled[i] else max(MAX_GAME_MINUTES, planned[i]) for i in range(len(items))]
    for i, freed in injury_freed:
        # The coach goes to his bench first, and to players at the injured player's position first.
        spot = position_number(items[i]["player"])
        weights = [foul_gain_weight(planned[j]) * (INJURY_OTHER_POSITION + (1.0 - INJURY_OTHER_POSITION)
                   * math.exp(-abs(position_number(items[j]["player"]) - spot)))
                   if j < in_pool and planned[j] > 0 and not troubled[j] else 0.0 for j in range(len(items))]
        leftover = _hand_out(minutes, freed, weights, caps)
        if leftover > 0:  # nobody else healthy with room: whoever is left plays on
            _hand_out(minutes, leftover, [1.0 if j < in_pool and not troubled[j] else 0.0 for j in range(len(items))],
                      [0.0 if troubled[j] else max(MAX_GAME_MINUTES, planned[j]) + 6.0 for j in range(len(items))])
    if foul_freed > 0:
        weights = [foul_gain_weight(planned[i]) if i < in_pool and planned[i] > 0 else 0.0 for i in range(len(items))]
        leftover = _hand_out(minutes, foul_freed, weights, caps)
        if leftover > 0:  # nobody healthy enough to take them: give them back
            _hand_out(minutes, leftover, [1.0 if i < in_pool and items[i]["player"]["id"] not in injured else 0.0
                                          for i in range(len(items))],
                      [max(MAX_GAME_MINUTES, planned[i]) for i in range(len(items))])
    garbage = garbage_minutes(margin) * rng.uniform(1.0 - GARBAGE_SPREAD, 1.0 + GARBAGE_SPREAD)
    if garbage > 0:
        rested = 0.0
        for i, item in enumerate(items):
            if item["player"]["id"] in fouled_out or item["player"]["id"] in injured:
                continue
            sit = min(minutes[i], garbage * core_share(planned[i]))
            minutes[i] -= sit
            rested += sit
        extras_ok = garbage >= GARBAGE_EXTRAS_MIN
        weights = [garbage_gain_weight(planned[i]) if (i < in_pool and planned[i] > 0) or (i >= in_pool and extras_ok)
                   else 0.0 for i in range(len(items))]
        gain_caps = [0.0 if items[i]["player"]["id"] in fouled_out or items[i]["player"]["id"] in injured
                     else min(caps[i] or MAX_GAME_MINUTES, minutes[i] + garbage) for i in range(len(items))]
        leftover = _hand_out(minutes, rested, weights, gain_caps)
        if leftover > 0:  # a short bench: the regulars finish the game after all
            _hand_out(minutes, leftover, [core_share(planned[i]) if i < in_pool and items[i]["player"]["id"] not in injured
                                          else 0.0 for i in range(len(items))],
                      [max(MAX_GAME_MINUTES, planned[i]) for i in range(len(items))])
    managed = []
    for i, item in enumerate(items):
        if i >= in_pool and minutes[i] <= 0.005:
            continue
        row = {**item, "minutes": minutes[i], "planned_minutes": round(planned[i], 2)}
        if item["player"]["id"] in injured:
            row["left_injured"] = True
        managed.append(row)
    from .sim import normalize_minutes
    return normalize_minutes(managed, exact=True), fouls, fouled_out


def fouls_from_times(lines: list[dict[str, Any]], times: dict[str, list[float]], fouled_out: set[str]) -> None:
    """Personal fouls are the fouls committed within the minutes each player actually played."""
    for line in lines:
        pid = line["player_id"]
        minutes = float(line.get("minutes") or 0.0)
        if pid in fouled_out:
            line["personal_fouls"] = FOUL_LIMIT
            continue
        line["personal_fouls"] = sum(1 for t in times.get(pid, []) if t <= minutes + 1e-6) if minutes > 0 else 0
