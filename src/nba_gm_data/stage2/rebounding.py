"""Rebound kernel (Stage 2): who gets a missed shot among the ten players on the floor.

Built new from the approved inputs (docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md, C20-C22):
- technique: S29 offensive rebound reading/pursuit, S30 defensive rebound positioning, S31 box-out, S32 rebound control;
- tools: standing reach (P03) plus jump (P10) is the height he can take the ball at; strength (P08) wins box-out fights;
- habits: T12 crash vs retreat after his own team's miss; T13 box-out vs pursue on defense;
- where he is when the shot goes up (offense: his shot-region habit T02 as his working spot, the shooter at the shot;
  defense: between his man and the rim);
- the miss: rim misses land close, long misses from three bounce farther (landing distance and spread per miss type);
  free-throw misses use fixed lane spots.

Each player gets a "pull" = taking part (crash or retreat) x nearness to where the ball lands x ability (technique,
reach) x any box-out seal on him; the defence keeps its inside-position edge. The chance a player gets the rebound is
his pull over everyone's. Only player rebounds are modelled (team rebounds are not credited to players in the box
score, and real per-player rates are measured against player rebounds too).

The kernel's own conversion numbers live in ReboundCoefficients. Ratings are never adjusted here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, fields, replace
from typing import Mapping, Sequence

VERSION = "stage2_rebound_kernel_v1_2026_11_21"
MISS_TYPES = ("rim", "short", "mid", "three", "ft")
# T02 shot regions -> the working spot (metres from the rim) used as where he stands on offence.
REGION_SPOT_M = {"rim": 1.2, "short_paint": 3.0, "midrange": 5.2, "three": 7.3}
# Where the shooter is when he releases, by miss type.
SHOT_SPOT_M = {"rim": 0.9, "short": 3.0, "mid": 5.0, "three": 7.3, "ft": 4.6}


@dataclass(frozen=True)
class ReboundProfile:
    player_id: str
    oskill: float      # S29
    dskill: float      # S30
    boxout: float      # S31
    control: float     # S32
    reach_cm: float    # P03 standing reach
    jump_cm: float     # P10 jump
    strength: float    # P08 grade
    mass_kg: float     # P04
    height_cm: float   # P01 (matching only)
    crash: float       # T12
    box_share: float   # T13 box_out share
    spot_m: float      # offensive working spot from T02
    help: float = .5   # T15 help commitment: how much he plays the paint on defence regardless of his man


def profile_from_flat(player_id: str, flat: Mapping[str, float]) -> ReboundProfile:
    """Rebound profile from one player's flattened inputs (box_rates.flatten_inputs)."""
    regions = {k: flat.get(f"T02.{k}", 0.0) for k in REGION_SPOT_M}
    total = sum(regions.values()) or 1.0
    spot = sum(REGION_SPOT_M[k] * v for k, v in regions.items()) / total
    return ReboundProfile(player_id, float(flat["S29"]), float(flat["S30"]), float(flat["S31"]), float(flat["S32"]),
                          float(flat["P03"]), float(flat["P10"]), float(flat["P08"]), float(flat["P04"]),
                          float(flat["P01"]), float(flat["T12"]), float(flat.get("T13.box_out", .5)), spot,
                          float(flat.get("T15", .5)))


@dataclass(frozen=True)
class ReboundCoefficients:
    """The kernel's conversion numbers (fitted later only on held-out-checked player halves; never ratings)."""
    # Where misses land (metres from the rim) and how widely, by miss type.
    landing_m: tuple = (1.6, 2.4, 3.2, 4.2, 1.4)
    spread_m: tuple = (1.6, 1.8, 2.0, 2.4, 1.0)
    distance_scale: float = 1.0           # multiplies every |spot - landing| / spread
    # Offence: a non-crasher still gets this share of a crasher's taking-part; a crasher closes this share of the gap.
    retreat: float = .12
    crash_closing: float = .55
    # Defence: stands this share of his man's distance from the rim, and keeps this log edge for inside position.
    inside: float = .80
    defense_edge: float = .70
    # Defence: a helper (T15) stands this much nearer the rim than his man's spot implies (0 = with his man).
    anchor: float = 0.0
    # Ability: log pull per 25 grade points of technique / control; per 10 cm of standing reach and of jump.
    k_off_skill: float = .35
    k_def_skill: float = .35
    k_control: float = .20
    k_reach: float = .12
    k_jump: float = .12
    reach_ref_cm: float = 265.0
    jump_ref_cm: float = 75.0
    # Box-out: largest share of a crasher's pull a seal removes; centre and slopes of the seal contest (per 25 points).
    box_max: float = .50
    box_centre: float = 0.0
    k_box_tech: float = .50
    k_box_strength: float = .30
    k_box_mass: float = 0.0               # per 10 kg of body mass over his man
    k_box_pursuit: float = .35
    box_self_cost: float = .35            # a boxing defender gives up this share of his own pull...
    box_keep: float = 0.0                 # ...less this share of it when his seal holds
    # Free-throw lane: offence's two lane players' spot, defence's inside spots, everyone else's taking-part.
    ft_off_spot: float = 2.2
    ft_def_spot: float = 1.3
    ft_other: float = .08

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class _Prepared:
    """Per-player numbers that depend on the coefficients but not on the play (computed once per coefficient set)."""
    off_ability: float
    def_ability: float
    seal_base: float      # defender's side of the box-out contest (technique), before strength and pursuit
    pursuit: float        # crasher's resistance to a seal
    profile: ReboundProfile


def prepare(profile: ReboundProfile, c: ReboundCoefficients) -> _Prepared:
    reach = c.k_reach * (profile.reach_cm - c.reach_ref_cm) / 10.0 + c.k_jump * (profile.jump_cm - c.jump_ref_cm) / 10.0
    control = c.k_control * (profile.control - 50.0) / 25.0
    return _Prepared(
        off_ability=math.exp(c.k_off_skill * (profile.oskill - 50.0) / 25.0 + control + reach),
        def_ability=math.exp(c.k_def_skill * (profile.dskill - 50.0) / 25.0 + control + reach + c.defense_edge),
        seal_base=c.k_box_tech * (profile.boxout - 50.0) / 25.0,
        pursuit=c.k_box_pursuit * (profile.oskill - 50.0) / 25.0,
        profile=profile,
    )


def matchups(offense: Sequence[ReboundProfile], defense: Sequence[ReboundProfile]) -> list[int]:
    """defender index -> offensive index he guards: matched by height order (tallest guards tallest)."""
    o = sorted(range(len(offense)), key=lambda i: -offense[i].height_cm)
    d = sorted(range(len(defense)), key=lambda j: -defense[j].height_cm)
    out = [0] * len(defense)
    for oi, dj in zip(o, d):
        out[dj] = oi
    return out


def rebound_probabilities(offense: Sequence[_Prepared], defense: Sequence[_Prepared], guards: Sequence[int],
                          miss: str, shooter: int, c: ReboundCoefficients) -> list[float]:
    """Probability each of the ten players secures the rebound (offence first, then defence); sums to 1."""
    t = MISS_TYPES.index(miss)
    land = c.landing_m[t]
    inv_spread = c.distance_scale / c.spread_m[t]
    pulls = [0.0] * 10
    exp = math.exp
    if miss == "ft":
        # Lane: the offence's two tallest take the outside lane spots; the defence holds the two inside spots.
        tall_o = sorted(range(5), key=lambda i: -offense[i].profile.height_cm)[:2]
        tall_d = sorted(range(5), key=lambda j: -defense[j].profile.height_cm)[:2]
        for i in range(5):
            if i in tall_o:
                pulls[i] = offense[i].off_ability * exp(-abs(c.ft_off_spot - land) * inv_spread)
            else:
                pulls[i] = c.ft_other * offense[i].off_ability * exp(-abs(SHOT_SPOT_M["ft"] - land) * inv_spread)
        for j in range(5):
            spot = c.ft_def_spot if j in tall_d else SHOT_SPOT_M["ft"]
            weight = 1.0 if j in tall_d else c.ft_other * 3
            pulls[5 + j] = weight * defense[j].def_ability * exp(-abs(spot - land) * inv_spread)
        total = sum(pulls)
        return [p / total for p in pulls]
    spots = [0.0] * 5
    for i in range(5):
        p = offense[i].profile
        base = SHOT_SPOT_M[miss] if i == shooter else p.spot_m
        spots[i] = base
        crash = p.crash
        closed = base - (base - land) * c.crash_closing
        near_crash = exp(-abs(closed - land) * inv_spread)
        near_stay = exp(-abs(base - land) * inv_spread)
        pulls[i] = offense[i].off_ability * (crash * near_crash + c.retreat * (1.0 - crash) * near_stay)
    for j in range(5):
        dp = defense[j]
        man = guards[j]
        help_ = c.anchor * dp.profile.help
        spot = (spots[man] * (1.0 - help_) + SHOT_SPOT_M["rim"] * help_) * c.inside
        near = exp(-abs(spot - land) * inv_spread)
        share = dp.profile.box_share
        # The seal on his man: technique, strength and mass against the crasher's pursuit.
        off = offense[man]
        z = (c.box_centre + dp.seal_base + c.k_box_strength * (dp.profile.strength - off.profile.strength) / 25.0
             + c.k_box_mass * (dp.profile.mass_kg - off.profile.mass_kg) / 10.0 - off.pursuit)
        hold = 1.0 / (1.0 + exp(-z))
        pulls[5 + j] = dp.def_ability * near * (1.0 - c.box_self_cost * share * (1.0 - c.box_keep * hold))
        pulls[man] *= (1.0 - c.box_max * share * hold)
    total = sum(pulls)
    return [p / total for p in pulls]


def with_values(c: ReboundCoefficients, values: Mapping[str, float]) -> ReboundCoefficients:
    """A copy with scalar or 'name[i]' tuple entries replaced (used by the refit)."""
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


# Conversion refit (2026-11-21, S2-REBOUND-FOULS): coordinate search on the kernel's own numbers against the offensive and
# defensive rebound percentages of half the 2025-26 rotation players (fixed hash), plus the league offensive-rebound
# percentage; checked on the other half and on 2022-23. No player input was changed. The fit wanted jump capacity and
# body mass slightly NEGATIVE (-.06 per 10 cm, -.04 per 10 kg); both are pinned at zero instead (no physical reading;
# held-out error unchanged to 0.1 point), so standing reach carries the tools. The paint-anchor term fitted to zero.
FITTED = with_values(ReboundCoefficients(), {
    "defense_edge": .56, "k_off_skill": .3175, "k_def_skill": .3093, "k_control": .0627, "k_reach": .1068,
    "k_jump": 0.0, "retreat": .17, "crash_closing": .60, "box_max": .1875, "box_self_cost": .40, "box_keep": .05,
    "k_box_mass": 0.0, "anchor": 0.0, "distance_scale": 1.2, "inside": .80})
