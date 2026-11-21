"""Foul and free-throw kernel (Stage 2): shooting fouls, and-ones, non-shooting fouls and the bonus.

Built from the approved inputs (docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md, C15 foul creation, C29 discipline):
- the shooter: foul-drawing craft (S24), contact seeking (T18), contact finishing (S15) and strength (P08);
- the defender who contests: foul control (S45), contest technique (S37) and how often he jumps at shots (T16 jump);
  rim and short-paint attempts are often contested by the rim protector instead of the man's own defender (the help
  defender is the other defender with the best interior positioning, S36);
- non-shooting fouls: drawn by the players who handle and attack (involvement T08, S24, T18), committed by their
  defender (foul control S45, steal gambling T14); a share of them fall in the bonus and give two free throws;
- offensive fouls (attackers and screeners: T18, T11 screen share) and loose-ball fouls (whoever is in the rebound
  fight) count as personal fouls but give no free throws to the shooter here.

A shooting foul on a make is an and-one (one free throw); on a miss, two free throws (three on a three) and no field-goal
attempt is recorded. The kernel's own conversion numbers live in FoulCoefficients. Ratings are never adjusted here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace
from typing import Mapping, Sequence

VERSION = "stage2_foul_kernel_v1_2026_11_21"
ZONES = ("rim", "short", "mid", "three")


def _logit(p: float) -> float:
    p = min(max(float(p), 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


@dataclass(frozen=True)
class FoulProfile:
    player_id: str
    craft: float          # S24
    seek: float           # logit T18
    contact_finish: float # S15
    strength: float       # P08
    involvement: float    # T08
    screen: float         # T11 screen share
    control: float        # S45
    contest: float        # S37
    jump: float           # logit T16 jump share
    gamble: float         # logit T14
    interior: float       # S36 (who helps at the rim)
    height_cm: float      # P01 (matching)
    drive: float = -1.5   # logit T01 drive share: rim and short-paint attempts he creates off the dribble


def profile_from_flat(player_id: str, flat: Mapping[str, float]) -> FoulProfile:
    return FoulProfile(player_id, float(flat["S24"]), _logit(flat["T18"]), float(flat["S15"]), float(flat["P08"]),
                       float(flat["T08"]), float(flat.get("T11.screen", .3)), float(flat["S45"]), float(flat["S37"]),
                       _logit(flat.get("T16.jump", .3)), _logit(flat["T14"]), float(flat["S36"]), float(flat["P01"]),
                       _logit(flat.get("T01.drive", .2)))


@dataclass(frozen=True)
class FoulCoefficients:
    # Shooting-foul log-odds by zone at a reference shooter and defender (rim, short, mid, three).
    base: tuple = (-1.75, -2.35, -3.6, -4.6)
    # Shooter (per 25 grade points; per unit of log-odds for T18).
    k_craft: float = .35
    k_seek: float = .35
    k_finish: float = .10
    k_strength: float = .10
    k_drive: float = 0.0       # rim/short-paint only: self-created drives draw more contact than catch finishes
    # Contesting defender (per 25 points; per unit log-odds of jump share).
    k_control: float = .35
    k_contest: float = .10
    k_jump: float = .15
    # Share of rim / short-paint attempts contested by the help (rim-protecting) defender.
    help_share: tuple = (.40, .25, 0.0, 0.0)
    # Probability a shooting foul comes on a make (and-one), by zone; the and-one rises with contact finishing.
    and_one: tuple = (.30, .20, .06, .03)
    k_and_one_finish: float = .25
    # Non-shooting fouls per possession (team), split by drawer weight and defender multiplier; bonus share.
    nonshooting_per_poss: float = .068
    k_ns_involvement: float = 1.0   # power on T08
    k_ns_craft: float = .20
    k_ns_seek: float = .20
    k_ns_control: float = .30
    k_ns_gamble: float = .30
    bonus_share: float = .24
    # Offensive fouls per possession (team), weight: involvement^p * exp(k*T18 logit) + screen share.
    offensive_per_poss: float = .0115
    k_off_seek: float = .3
    k_off_screen: float = 1.0
    # Loose-ball fouls per rebound chance (all ten players, shared by rebound probability).
    loose_ball_per_chance: float = .032
    k_lb: float = 1.0          # scale on each player's loose-ball share (his rebound share)
    # Other free throws per possession not credited above (technicals, flagrants, clear-path, loose-ball in bonus).
    other_fta_per_poss: float = .010

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def shooting_foul_probability(shooter: FoulProfile, defender: FoulProfile, zone: int, c: FoulCoefficients) -> float:
    z = (c.base[zone]
         + c.k_craft * (shooter.craft - 50.0) / 25.0 + c.k_seek * shooter.seek
         + c.k_finish * (shooter.contact_finish - 50.0) / 25.0 + c.k_strength * (shooter.strength - 50.0) / 25.0
         + (c.k_drive * shooter.drive if zone < 2 else 0.0)
         - c.k_control * (defender.control - 50.0) / 25.0 + c.k_contest * (defender.contest - 50.0) / 25.0
         + c.k_jump * defender.jump)
    return 1.0 / (1.0 + math.exp(-z))


def and_one_probability(shooter: FoulProfile, zone: int, c: FoulCoefficients) -> float:
    return min(.9, c.and_one[zone] * math.exp(c.k_and_one_finish * (shooter.contact_finish - 50.0) / 25.0))


def help_defender(defense: Sequence[FoulProfile], primary: int) -> int:
    best, best_v = primary, -1.0
    for j, d in enumerate(defense):
        if j != primary and d.interior > best_v:
            best, best_v = j, d.interior
    return best


def shot_outcome(shooter: FoulProfile, defense: Sequence[FoulProfile], primary: int, zone: int,
                 c: FoulCoefficients) -> dict:
    """One shot attempt: chance of a shooting foul, who commits it, and the free throws and recorded attempts it
    implies (expected values)."""
    help_j = help_defender(defense, primary)
    h = c.help_share[zone] if help_j != primary else 0.0
    p_primary = shooting_foul_probability(shooter, defense[primary], zone, c)
    p_help = shooting_foul_probability(shooter, defense[help_j], zone, c) if h else 0.0
    foul = (1 - h) * p_primary + h * p_help
    and_one = and_one_probability(shooter, zone, c)
    free_throws = foul * (and_one * 1 + (1 - and_one) * (3 if zone == 3 else 2))
    return {"foul": foul, "by": {primary: (1 - h) * p_primary, help_j: h * p_help} if h else {primary: foul},
            "and_one": foul * and_one, "fta": free_throws, "fga": 1.0 - foul * (1 - and_one)}


def nonshooting_weights(offense: Sequence[FoulProfile], c: FoulCoefficients) -> list[float]:
    """Each offensive player's share of the non-shooting fouls his team draws (sums to 1 over the five)."""
    w = [max(1e-3, p.involvement) ** c.k_ns_involvement * math.exp(c.k_ns_craft * (p.craft - 50.0) / 25.0 + c.k_ns_seek * p.seek)
         for p in offense]
    total = sum(w)
    return [x / total for x in w]


def defender_nonshooting_multiplier(d: FoulProfile, c: FoulCoefficients) -> float:
    return math.exp(-c.k_ns_control * (d.control - 50.0) / 25.0 + c.k_ns_gamble * d.gamble)


def offensive_foul_weights(offense: Sequence[FoulProfile], c: FoulCoefficients) -> list[float]:
    w = [max(1e-3, p.involvement) * math.exp(c.k_off_seek * p.seek) + c.k_off_screen * p.screen * .2 for p in offense]
    total = sum(w)
    return [x / total for x in w]


def with_values(c: FoulCoefficients, values: Mapping[str, float]) -> FoulCoefficients:
    changes: dict = {}
    for key, value in values.items():
        if "[" in key:
            name, idx = key[:-1].split("[")
            current = list(changes.get(name, getattr(c, name)))
            current[int(idx)] = value
            changes[name] = tuple(current)
        else:
            changes[key] = value
    return replace(c, **changes)


def bonus_share_from_rule(team_fouls_per_quarter: float, steps: int = 240) -> float:
    """Share of a team's fouls committed while the opponent is in the bonus, under the NBA rule (from the team's 5th
    foul of a quarter; or from its 2nd foul inside the last two minutes), with fouls arriving at a steady rate (Poisson).
    Used to sanity-check the kernel's fitted bonus share; the possession loop will track real team-foul counts."""
    lam = max(1e-9, float(team_fouls_per_quarter))
    late = 2.0 / 12.0
    total = 0.0
    for k in range(steps):
        u = (k + .5) / steps
        m = lam * u                               # expected earlier fouls this quarter
        p_lt4 = sum(math.exp(-m) * m ** n / math.factorial(n) for n in range(4))
        in_bonus = 1.0 - p_lt4
        if u > 1.0 - late:
            # not yet at five: in the bonus if at least one earlier foul came inside the last two minutes
            m_late = lam * (u - (1.0 - late))
            in_bonus += p_lt4 * (1.0 - math.exp(-m_late))
        total += in_bonus
    return total / steps


FITTED = FoulCoefficients()  # placeholder, replaced by the conversion refit below
