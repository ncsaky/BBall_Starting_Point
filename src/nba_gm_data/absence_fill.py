"""The coach's decision about who plays a missing player's minutes (SMART-MINUTES, 2026-11-19).

When a player is out, his healthy minutes belong to the spot he played (point guard through center; a player who
slides between spots spreads them). The coach hands those minutes out in two parts:

* The other starters pick up a modest share, about a sixth when a solid backup plays that spot and about a quarter
  when the backup is thin or missing (real coaches added 1.1 and 1.8 minutes to each other starter). A coach who
  rides his stars (star workload trait) leans on them a little more, one who limits stars a little less.
* The bench takes the rest. Each bench player's claim is his fit at that spot (position, height and the skills the
  starting-lineup scoring uses: handling and passing at the point, shooting and defense on the wing, rebounding and
  rim protection up front), times the coach's value of him (his overall rating against the team's), times his role
  (players who already play a lot can only stretch so far; a player outside the rotation is the last resort, and
  the coach calls up at most two of them). Part of each spot's minutes is position-free, a larger part on the wings
  (shooting guard to power forward are largely interchangeable) than at point guard or center (specialist jobs), so
  a team with no real backup goes smaller or bigger instead of forcing a third-string center into 30 minutes.
* Small judgment calls on top: a like-for-like role (ball handler for ball handler, rim protector for rim protector)
  adds a little; a rebuilding team leans toward its young players and a team at its peak toward proven ones; and in a
  game the fill-in minutes lean toward size against a big front line and toward guards against a guard-led team.

Nobody passes 42 minutes; a short-handed team's extra minutes go to whoever still has room.

Fitted (output/smart-minutes/fit_fill.py, docs/agents/tasks/smart-minutes.md) to real 2025-26 games with one starter
out, applied to the game's own rosters and healthy AI plans: the starters' share and its depth boost, positional
sharpness, the position-free shares, the role curve and the value weight. Judgment calls: role likeness, team phase,
the star-workload tilt and the opponent lean.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from .utils import clamp

SLOTS = 5
# Positional fit: slot-score points per e-fold drop from a player's best slot (starting_slot_score scale), for a
# player taking minutes, and for how widely a missing player's own minutes spread over the slots he covers.
FIT_TEMPERATURE = 2.0
ABSENT_TEMPERATURE = 0.5
# Share of each spot's minutes the coach treats as position-free: point guard and center, and the wing spots (2-4).
POSITION_FREE = 0.11
POSITION_FREE_WING = 0.54
# The other starters' share of the missing minutes with a solid backup (16+ healthy minutes at that spot), raised by
# DEPTH_BOOST x the missing depth when the backup is thin or absent.
STARTER_SHARE = 0.14
DEPTH_BOOST = 0.6
SOLID_BACKUP_MINUTES = 16.0
# With several starters out the coach goes deeper: the remaining starters' share of each absence is divided by the
# number of starters out to the power 0.75 (real 2025-26: each other starter +1.5 minutes with one starter out,
# +2.25 with two).
# A bench player's role: weight = exp(-healthy minutes / ROLE_SCALE), at least ROLE_FLOOR; a player outside the
# rotation (no healthy minutes) weighs UNUSED_WEIGHT, and the coach calls up at most DEEP_CALLUPS of them.
ROLE_SCALE = 18.0
ROLE_FLOOR = 0.1
UNUSED_WEIGHT = 1.0
DEEP_CALLUPS = 2
# The coach's value of a player: exp(VALUE_WEIGHT * (overall - team average) / 10).
VALUE_WEIGHT = 0.65
# Role likeness (judgment): a same-family offensive or defensive role adds this share to a player's claim. The real
# data shows no effect beyond position (its best fit is zero), so it stays small.
ROLE_MATCH = 0.2
# Team context (judgment, small).
PHASE_YOUNG_AGE = 23.0
PHASE_VETERAN_MINUTES = 20.0
PHASE_FACTORS = {
    "rebuilding": {"young": 1.3, "proven": 0.9},
    "entering": {"young": 1.1, "proven": 1.0},
    "peak": {"young": 0.8, "proven": 1.15},
    "exiting": {"young": 0.95, "proven": 1.05},
}
# Star workload (judgment): the starters' share scales by 1 + this x the coach's star workload (minutes).
STAR_TILT = 0.06
# Opponent lean (judgment): fill-in minutes shift by up to this share toward size or toward guards in a game.
OPPONENT_LEAN = 0.35
OPPONENT_MAX_SHIFT = 3.0
MAX_MINUTES = 42.0
# The coach stretches a player past this only when the team cannot place the minutes otherwise (judgment; real
# 2025-26: in games with two starters out, someone passed 42 minutes in about 1% of them).
FILL_SOFT_CAP = 39.0
STARTERS = 5

OFF_FAMILY = {
    "Primary Ball Handler": "handler", "Secondary Ball Handler": "handler", "Movement Ball Handler": "handler",
    "Spot Up Shooter": "wing", "Movement Shooter": "wing", "Connector": "wing",
    "Rollman": "big", "Versatile Big": "big",
}
DEF_FAMILY = {
    "On-Ball Guard": "guard", "Disruptor": "guard",
    "Versatile Stopper": "wing", "Mobile Forward": "wing", "Hidden": "wing",
    "Rim Protector": "big",
}


@dataclass
class FillPlayer:
    pid: str
    healthy: float
    gaps: tuple[float | None, ...]  # slot score minus his best slot's, slots 1-5 (None: cannot play it)
    value: float = 50.0
    age: float = 27.0
    off_family: str = ""
    def_family: str = ""
    starter: bool = False
    cap: float = MAX_MINUTES

    def fit(self, temperature: float | None = None) -> tuple[float, ...]:
        """Relative fit at slots 1-5: 1.0 at his best slot."""
        t = FIT_TEMPERATURE if temperature is None else temperature
        return tuple(math.exp(g / t) if g is not None else 0.0 for g in self.gaps)

    @property
    def size(self) -> float:
        """-1 for a pure point guard, +1 for a pure center (centre of his positional fit)."""
        fit = self.fit(7.0)
        total = sum(fit) or 1.0
        return (sum((slot + 1) * f for slot, f in enumerate(fit)) / total - 3.0) / 2.0


def slot_gaps(scores: Iterable[float]) -> tuple[float | None, ...]:
    scores = [float(s) for s in scores]
    valid = [s for s in scores if s > -5_000]
    if not valid:
        return (0.0,) * SLOTS
    best = max(valid)
    return tuple(s - best if s > -5_000 else None for s in scores)


UNKNOWN_GAPS = (-6.0, -6.0, 0.0, -6.0, -6.0)


def role_weight(healthy: float) -> float:
    if healthy <= 0:
        return UNUSED_WEIGHT
    return max(ROLE_FLOOR, math.exp(-healthy / ROLE_SCALE))


def role_match(a: FillPlayer, b: FillPlayer) -> float:
    match = 0.0
    if a.off_family and a.off_family == b.off_family:
        match += 0.5
    if a.def_family and a.def_family == b.def_family:
        match += 0.5
    return match


def phase_factor(player: FillPlayer, phase: str | None) -> float:
    factors = PHASE_FACTORS.get(phase or "")
    if not factors:
        return 1.0
    if player.age <= PHASE_YOUNG_AGE:
        return factors["young"]
    if player.healthy >= PHASE_VETERAN_MINUTES or player.age >= 28:
        return factors["proven"]
    return 1.0


def mark_starters(players: list[FillPlayer], absent: list[FillPlayer]) -> None:
    """The healthy plan's five biggest minute-getters are its starters."""
    everyone = sorted(players + absent, key=lambda p: (-p.healthy, p.pid))
    top = {p.pid for p in everyone[:STARTERS] if p.healthy > 0}
    for p in players + absent:
        p.starter = p.pid in top


def coach_fill(
    absent: list[FillPlayer],
    available: list[FillPlayer],
    vacated: float,
    *,
    phase: str | None = None,
    star_workload: float = 0.0,
    eligible: set[str] | None = None,
) -> dict[str, float]:
    """Minutes added to each available player so the team's missing minutes are played. Sums to `vacated`."""
    adds = {p.pid: 0.0 for p in available}
    if vacated <= 1e-9 or not available:
        return adds
    pool = [p for p in available if eligible is None or p.pid in eligible] or list(available)
    valued = [p.value for p in pool if p.healthy > 0] or [p.value for p in pool]
    team_value = sum(valued) / len(valued)
    value = {p.pid: math.exp(VALUE_WEIGHT * (p.value - team_value) / 10.0) * phase_factor(p, phase) for p in pool}
    # Where the missing minutes were played: each absent player's minutes across the slots he covers.
    demand: list[tuple[FillPlayer | None, int, float]] = []
    absent_total = sum(max(0.0, x.healthy) for x in absent)
    for x in absent:
        if x.healthy <= 0:
            continue
        share = vacated * x.healthy / absent_total
        spread = x.fit(ABSENT_TEMPERATURE)
        fit_total = sum(spread) or 1.0
        for slot, f in enumerate(spread):
            if f > 0:
                demand.append((x, slot, share * f / fit_total))
    if not demand:  # nobody in the healthy plan is out (a short rotation): position-free
        demand = [(None, -1, vacated)]
    fits = {p.pid: p.fit() for p in pool}
    starters_out = max(1, sum(1 for x in absent if x.starter))
    star_tilt = max(0.2, 1.0 + STAR_TILT * star_workload) / starters_out ** 0.75

    def claim(p: FillPlayer, x: FillPlayer | None, slot: int) -> float:
        fit = fits[p.pid][slot] if slot >= 0 else 1.0
        free = POSITION_FREE_WING if slot in (1, 2, 3) else POSITION_FREE
        likeness = 1.0 + ROLE_MATCH * role_match(p, x) if x is not None else 1.0
        return value[p.pid] * (free + (1.0 - free) * fit) * likeness

    def place(players: list[FillPlayer]) -> dict[str, float]:
        table = {p.pid: 0.0 for p in players}
        starters = [p for p in players if p.starter]
        bench = [p for p in players if not p.starter]
        for x, slot, minutes in demand:
            backup = max((fits[p.pid][slot] * min(1.0, p.healthy / SOLID_BACKUP_MINUTES)
                          for p in bench if p.healthy > 0 and slot >= 0), default=0.0 if slot >= 0 else 1.0)
            share = STARTER_SHARE * (1.0 + DEPTH_BOOST * (1.0 - backup)) * star_tilt if bench else 1.0
            share = 0.0 if not starters else min(share, 0.6) if bench else 1.0
            for group, part in ((starters, minutes * share), (bench, minutes * (1.0 - share))):
                weights = {p.pid: claim(p, x, slot) * role_weight(p.healthy) for p in group}
                total = sum(weights.values())
                if part <= 0 or total <= 0:
                    continue
                for pid, w in weights.items():
                    table[pid] += part * w / total
        return table

    table = place(pool)
    # The coach calls up at most a couple of players from outside the rotation, the ones who fit best.
    deep = sorted((p for p in pool if p.healthy <= 0 and not p.starter), key=lambda p: (-table[p.pid], p.pid))
    if len(deep) > DEEP_CALLUPS:
        skipped = {p.pid for p in deep[DEEP_CALLUPS:]}
        pool = [p for p in pool if p.pid not in skipped]
        table = place(pool)
    return _cap(table, {p.pid: p for p in pool}, adds)


def _cap(table: dict[str, float], players: dict[str, FillPlayer], adds: dict[str, float]) -> dict[str, float]:
    """Nobody past his cap; what does not fit goes to the others in proportion to their share.

    A first pass stops everyone at FILL_SOFT_CAP (or his healthy minutes, if higher); only a team that cannot place
    the minutes that way goes up to the hard cap (42)."""
    want = dict(table)
    placed = dict.fromkeys(want, 0.0)
    leftover = sum(want.values())
    shares = dict(want)
    for soft in (True, False):
        def cap(pid: str) -> float:
            hard = players[pid].cap
            return min(hard, max(FILL_SOFT_CAP, players[pid].healthy)) if soft else hard
        for _ in range(len(want) + 1):
            open_ = [pid for pid in want if players[pid].healthy + placed[pid] < cap(pid) - 1e-9 and shares[pid] > 0]
            total = sum(shares[pid] for pid in open_)
            if leftover <= 1e-9 or total <= 0:
                break
            moved = 0.0
            for pid in open_:
                room = cap(pid) - players[pid].healthy - placed[pid]
                give = min(room, leftover * shares[pid] / total)
                placed[pid] += give
                moved += give
            leftover -= moved
    if leftover > 1e-9:  # everyone capped: spread evenly over whoever has room up to 48
        open_ = [pid for pid in want if players[pid].healthy + placed[pid] < 48.0]
        for pid in open_:
            placed[pid] += leftover / len(open_)
    for pid, value in placed.items():
        adds[pid] = adds.get(pid, 0.0) + value
    return adds


# --- Building profiles from the game's players -------------------------------------------------------------------

def player_profile(canonical: dict[str, Any], player: dict[str, Any], healthy: float, cap: float = MAX_MINUTES) -> FillPlayer:
    from .save import player_attribute_summary
    return profile_from_attrs(player, player_attribute_summary(canonical, player["id"]), healthy, cap=cap)


def profile_from_attrs(player: dict[str, Any], attrs: dict[str, Any], healthy: float, cap: float = MAX_MINUTES) -> FillPlayer:
    from .save import _slot_score_row
    scores, _ = _slot_score_row(player, attrs)
    try:
        age = float(player.get("display_age", player.get("age")) or 27.0)
    except (TypeError, ValueError):
        age = 27.0
    return FillPlayer(
        pid=player["id"], healthy=max(0.0, float(healthy)), gaps=slot_gaps(scores),
        value=float(attrs.get("overall") or 50.0), age=age,
        off_family=OFF_FAMILY.get(str(player.get("primary_off_role") or ""), ""),
        def_family=DEF_FAMILY.get(str(player.get("primary_def_role") or ""), ""),
        cap=cap,
    )


# --- The opponent, in a game ---------------------------------------------------------------------------------------

# League mean and spread of team averages (minutes-weighted) of the sim's player features, over the 2026-27 opening
# rotations of each rating set (output/smart-minutes/opp_scale.py): front-line strength = mean of offensive
# rebounding and rim deterrence; creation strength = shot creation. Used only to say whether an opponent is unusually
# big and physical or unusually built on guards and creators. (front mean, front spread, creation mean, spread)
LEAN_SCALE = {"legacy": (57.5, 4.8, 46.7, 2.35), "inputs": (55.1, 4.3, 45.8, 2.25)}


def opponent_lean(canonical: dict[str, Any], opponent_pool: list[dict[str, Any]]) -> float:
    """+1 against an unusually big, physical front line; -1 against a small team built on guards and creators."""
    from .ratings_model import uses_inputs_model
    from .sim import player_feature_vector
    total = sum(float(item.get("minutes") or 0.0) for item in opponent_pool)
    if total <= 0:
        return 0.0
    FRONT_LINE_MEAN, FRONT_LINE_SD, GUARD_MEAN, GUARD_SD = LEAN_SCALE["inputs" if uses_inputs_model(canonical) else "legacy"]
    front = guard = 0.0
    for item in opponent_pool:
        features = player_feature_vector(canonical, item["player"]).features
        m = float(item.get("minutes") or 0.0) / total
        front += m * (features.get("offensive_rebounding", 50.0) + features.get("rim_deterrence", 50.0)) / 2.0
        guard += m * features.get("shot_creation", 50.0)
    z = (front - FRONT_LINE_MEAN) / FRONT_LINE_SD - (guard - GUARD_MEAN) / GUARD_SD
    return clamp(z / 2.0, -1.0, 1.0)


def opponent_adjusted_pool(canonical: dict[str, Any], pool: list[dict[str, Any]],
                           opponent_pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-point the coach's fill-in minutes for tonight's opponent; the healthy plan is untouched."""
    fills = [(i, float(item["player"].get("_absence_fill") or 0.0)) for i, item in enumerate(pool)]
    fills = [(i, f) for i, f in fills if f > 0.05]
    if len(fills) < 2:
        return pool
    lean = opponent_lean(canonical, opponent_pool)
    if abs(lean) < 0.05:
        return pool
    total = sum(f for _, f in fills)
    tilted = {i: f * max(0.1, 1.0 + OPPONENT_LEAN * lean * float(pool[i]["player"].get("_fill_size") or 0.0))
              for i, f in fills}
    scale = total / (sum(tilted.values()) or 1.0)
    shifts = {i: tilted[i] * scale - f for i, f in fills}
    # A game plan shades minutes; it does not rebuild the rotation (largest single change OPPONENT_MAX_SHIFT).
    largest = max(abs(s) for s in shifts.values())
    damp = min(1.0, OPPONENT_MAX_SHIFT / largest) if largest > 0 else 1.0
    out = list(pool)
    for i, shift in shifts.items():
        item = out[i]
        out[i] = {**item, "minutes": max(0.0, float(item.get("minutes") or 0.0) + shift * damp)}
    return out
