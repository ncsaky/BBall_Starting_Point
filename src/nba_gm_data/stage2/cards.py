"""Player cards for the Stage 2 possession loop: every number the loop needs about one player, computed once.

A card is built from the player's 94 inputs (flattened, `box_rates.flatten_inputs`) and holds:
- who he is on the floor: usage weight (how often he ends a possession), turnover log-odds, the shots he takes
  (an action-and-shot menu that reproduces his shot-location habit T02 exactly), his make chance on each shot at the
  league reference defense, free-throw percentage, foul-drawing numbers (stage2.fouls), passing weight;
- on defense: perimeter contest, rim protection and ball-pressure indices, steal / block / foul weights, the rebound
  profile (stage2.rebounding).

Shooting uses the per-family conversion fitted in S2-SEAM-SHOOTING (each jumper family, layups, floaters and dunks its
own floor and slope) and adds a post/hook family (S23 post finish) and a dunk-share rule from reach + vertical + dunk
skill. Every coefficient is a conversion of the engine's own (fitted to real 2025-26 data where marked FITTED, or a
documented stand-in otherwise); no rating is ever moved here.

Cards are cached by (player id, inputs signature), so a season of games builds each card once (~0.1 ms each).
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Mapping

from ..box_rates import ASSISTS_INPUTS, STEALS_INPUTS, flatten_inputs
from ..offense_response import OffenseCoefficients, OffensiveProfile, finishing_response, shooting_response
from . import fouls as F
from . import rebounding as R

VERSION = "stage2_cards_v1_2026_11_21"

# ---- shot kinds ------------------------------------------------------------------------------------------------
# (name, action, foul zone 0 rim / 1 short / 2 mid / 3 three, rebound miss type, points)
KINDS = (
    ("rim_drive", "drive", 0, "rim", 2),       # self-created drive to the rim (layup, contact layup, dunk)
    ("rim_finish", "roll_cut", 0, "rim", 2),   # finish off a pass: roll, cut, lob, dump-off
    ("floater", "drive", 1, "short", 2),       # drive that ends in a floater / runner
    ("hook", "post", 1, "short", 2),           # post-up hook / post finish
    ("short_jumper", "jumper", 1, "short", 2), # 4-14 ft jumper (turnaround, short pull-up, catch)
    ("mid_catch", "jumper", 2, "mid", 2),      # catch-and-shoot / movement midrange
    ("mid_pull", "pull_up", 2, "mid", 2),      # pull-up midrange
    ("three_corner", "jumper", 3, "three", 3), # corner catch-and-shoot three
    ("three_catch", "jumper", 3, "three", 3),  # above-the-break catch / movement three
    ("three_pull", "pull_up", 3, "three", 3),  # pull-up three
    ("putback", "putback", 0, "rim", 2),       # tip / putback right after an offensive rebound
    ("trans_rim", "transition", 0, "rim", 2),  # transition finish
    ("trans_three", "transition", 3, "three", 3),  # transition / early-offense three
    ("heave", "heave", 3, "three", 3),         # end-of-quarter heave
)
KIND_INDEX = {k[0]: i for i, k in enumerate(KINDS)}
N_KINDS = len(KINDS)
HALFCOURT_KINDS = tuple(range(10))
ACTIONS = ("drive", "roll_cut", "post", "jumper", "pull_up", "putback", "transition")

# ---- shooting conversion ---------------------------------------------------------------------------------------
# FITTED (S2-SEAM-SHOOTING, shooting_check.refit_families, held-out half within ~1 pt on every shot type).
FAMILY = {"catch3": (.2713, .2062), "pull3": (.215, .2187), "catch2": (.3213, .1012), "pull2": (.1425, .385),
          "layup": (.4125, .4525), "floater": (.1737, .4913), "dunk": (.6187, .2112)}
RANGE_PENALTY_PER_M = .0288
CONTACT_PENALTY = 0.0
CORNER_M, ATB_M, LONG_MID_M, MID_PULLUP_M, SHORT_JUMPER_M = 6.7, 7.5, 5.5, 5.0, 4.3
# Post/hook family (new here): floor + span x S23 post finish x (.9 + .1 balance) + reach above 270 cm.
# FITTED (stage2.loop_fit.fit_hook) on Basketball Index short-midrange make rates, fit half; held-out half corr .61 ->
# .65; post-heavy players' bias -3.1 -> +0.8 points.
HOOK = {"floor": .3219, "span": .275, "k_reach": .0131}
# Dunk share of rim attempts: logistic in (reach + vertical - 330 cm) per 10 cm and dunk skill (S12) per 25 points.
# FITTED (loop_fit.fit_dunk_share) to Basketball-Reference dunk shares of attempts within 3 ft (2025-26); held-out
# corr .90.
DUNK = {"base": -2.256, "k_height": .506, "k_skill": 1.031, "min_reach_cm": 310.0}
# How the dunk share varies by how the rim attempt was made (drives are mostly layups; rolls, cuts, lobs, putbacks and
# transition finishes are dunked more). Stand-in proportions; the league rim make rate is checked against real.
DUNK_BY_KIND = {"rim_drive": .65, "rim_finish": 1.2, "putback": 1.0, "trans_rim": 1.2}
TRANSITION_MAKE_LOGIT = .15   # transition shots are more open (stand-in; checked against league rim FG% and eFG)
HEAVE_MAKE = .04

# ---- the shot menu -------------------------------------------------------------------------------------------
# Within each shot region (T02) the action comes from his tendencies:
# rim: drive (T01 drive) vs finishing a teammate's pass (cutting T09, rolling/slipping T11) vs post (T01 post);
# short paint: floater (T01 drive) vs hook (T01 post) vs short jumper (T01 shoot);
# midrange: pull-up share (T03 pull-up) vs catch; three: pull-up share (T03) vs catch, a quarter of catch threes in the
# corner (league share; the inputs carry no corner habit). Stand-in weights (MENU); T02 is reproduced exactly.
MENU = {"rim_cut": .55, "rim_roll": .65, "rim_post": .9, "short_post": 2.4, "short_shoot": .55,
        "corner_share": .25,
        # T02 is measured on ALL his shots, so its rim share already holds his putbacks and transition finishes, which
        # the loop plays as their own possessions; the half-court menu keeps this share of the rim habit.
        "rim_halfcourt": .70,
        # ...and its three share holds his transition threes (the loop's transition menu): FITTED to the league
        # three-point attempt rate (.415).
        "three_halfcourt": .92}
# Transition menu: rim vs three by his rim / three habit (T02).
TRANS = {"rim_base": .45, "three_scale": .6}

# ---- usage, turnovers, defense ---------------------------------------------------------------------------------
# Usage weight (his share of the possessions his lineup ends): log-linear in tendencies. FITTED to real 2025-26
# usage (FGA + .44 FTA + TOV per possession on the floor) of rotation players (loop_fit.fit_all); held-out corr .95.
USAGE = {"constant": 0.19605, "log T08": 1.0104, "log T01.shoot": 0.30632, "log T01.drive": 0.01825,
         "log T01.pass": -0.20109, "log T01.post": 0.04171, "log T04": 0.12839, "log T06": 0.01686, "S16": -0.00234,
         "S19": -0.00059, "S.three_mode": -0.00036, "S10": 0.00166}
# Turnover log-odds per possession he ends. FITTED to real 2025-26 turnovers per used possession; held-out corr .74.
# The league level is then set by the loop's ball-pressure term and checked against turnovers per 100.
TURNOVER = {"constant": -1.09677, "log T07": 0.00619, "log T01.pass": 0.2983, "log T01.drive": -0.14972,
            "log T06": 0.25803, "log T08": 0.21238, "S16": 0.00304, "S17": -0.02037, "F.execution": 0.03124,
            "S20": -0.01673}
# Blocks: log-linear weight in contest technique, interior positioning, reach, jump-contest habit, vertical and help
# commitment. FITTED to real 2025-26 blocks per 36 (targets file); held-out corr .88. It shares the team's blocks; the
# level is the loop's.
BLOCKS = {"constant": 1.24321, "S37": 0.02144, "S36": 0.0011, "P03": 0.0002, "log T16.jump": 1.4901, "P10": -0.00225,
          "log T15": 1.1563}
# Defensive indices: (grade - league mean) / 25 on the named skills (league means over the inputs file).
PERIMETER_D = ("S33", "S37", "S40", "S35")
RIM_D = ("S36", "S37")
PRESSURE_D = ("S41", "S42", "S43")
# Offensive lineup indices: creation (dribble manipulation, separation, attack recognition, passing delivery) and
# spacing (three-point shooting as he shoots it, times how often he is out there: T02 three).
CREATION = ("S16", "S18", "S20", "F.execution")

_CARD_CACHE: dict[tuple, "Card"] = {}
_LEAGUE: dict[str, Any] = {}


def _logit(p: float) -> float:
    p = min(max(float(p), 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _sig(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def log_linear(model: Mapping[str, float], flat: Mapping[str, float], default: float = 0.0) -> float:
    total = model.get("constant", 0.0)
    for key, coef in model.items():
        if key == "constant" or not coef:
            continue
        if key.startswith("log "):
            total += coef * math.log(max(1e-3, float(flat.get(key[4:], default or .2))))
        else:
            total += coef * float(flat.get(key, 50.0))
    return total


def _conversions() -> dict[str, OffenseCoefficients]:
    key = ("conv", tuple(sorted(FAMILY.items())), RANGE_PENALTY_PER_M)
    if key not in _LEAGUE:
        base = OffenseCoefficients()
        conv = {}
        for fam in ("catch3", "pull3", "catch2", "pull2"):
            conv[fam] = replace(base, shooting_floor=FAMILY[fam][0], shooting_skill_span=FAMILY[fam][1],
                                range_penalty_per_m=RANGE_PENALTY_PER_M)
        for fam in ("layup", "floater"):
            conv[fam] = replace(base, finish_floor=FAMILY[fam][0], finish_skill_span=FAMILY[fam][1],
                                contact_penalty=CONTACT_PENALTY)
        _LEAGUE[key] = conv
    return _LEAGUE[key]


def offense_profile(pid: str, flat: Mapping[str, float]) -> OffensiveProfile:
    """The shooting kernel's profile straight from flattened inputs (same numbers the shared reader compiles:
    technique grade/100, capacities grade/100, reach and vertical in cm, FT proxy /100)."""
    skills = tuple(float(flat[f"S{i:02d}"]) / 100.0 for i in range(1, 16))
    regions = [max(0.0, float(flat.get(f"T02.{r}", .25))) for r in ("rim", "short_paint", "midrange", "three")]
    tot = sum(regions) or 1.0
    locations = (regions[0] / tot, (regions[1] + regions[2]) / tot, regions[3] / tot)
    modes = tuple(float(flat.get(f"T03.{m}", 1 / 3)) for m in ("catch", "pull_up", "movement"))
    return OffensiveProfile(None, pid, skills, float(flat.get("T01.shoot", .25)), locations, modes,
                            float(flat["P03"]), float(flat["P10"]), float(flat["P08"]) / 100.0,
                            float(flat["P09"]) / 100.0, OffenseCoefficients(), VERSION, float(flat["S07"]) / 100.0,
                            "stage2_flat_inputs")


def _jumper(p: OffensiveProfile, family: str, mode: str, distance: float) -> float:
    q = replace(p, coefficients=_conversions()[family])
    return shooting_response(q, mode=mode, distance_m=distance)["make_probability"]


def _finish(p: OffensiveProfile, kind: str) -> float:
    family = "floater" if kind == "floater" else "layup"
    q = replace(p, coefficients=_conversions()[family])
    return finishing_response(q, kind, contact=1.0 if kind == "contact_layup" else 0.0, delivery_quality=.95)["make_probability"]


def dunk_share(flat: Mapping[str, float]) -> float:
    """Share of his rim attempts he dunks (before the by-kind factor): zero below the reach + vertical needed."""
    height = float(flat["P03"]) + float(flat["P10"])
    if height < DUNK["min_reach_cm"]:
        return 0.0
    return _sig(DUNK["base"] + DUNK["k_height"] * (height - 330.0) / 10.0 + DUNK["k_skill"] * (float(flat["S12"]) - 50.0) / 25.0)


def make_table(pid: str, flat: Mapping[str, float]) -> list[float]:
    """Make probability for every shot kind at the league reference defense."""
    p = offense_profile(pid, flat)
    catch, pull, move = (max(1e-6, float(flat.get(f"T03.{m}", 1 / 3))) for m in ("catch", "pull_up", "movement"))
    cm = catch + move
    layup = _finish(p, "layup")
    contact = _finish(p, "contact_layup")
    layup_mix = (2 * layup + contact) / 3.0
    dunk_line = min(.98, FAMILY["dunk"][0] + FAMILY["dunk"][1] * p.skill(12))
    ds = dunk_share(flat)

    def rim(kind: str) -> float:
        d = min(.92, ds * DUNK_BY_KIND[kind])
        return d * dunk_line + (1 - d) * layup_mix

    catch3_atb = (catch * _jumper(p, "catch3", "catch", ATB_M) + move * _jumper(p, "catch3", "movement", ATB_M)) / cm
    catch2_mid = (catch * _jumper(p, "catch2", "catch", LONG_MID_M) + move * _jumper(p, "catch2", "movement", LONG_MID_M)) / cm
    pull_share = pull / (pull + cm)
    short_j = (1 - pull_share) * _jumper(p, "catch2", "catch", SHORT_JUMPER_M) + pull_share * _jumper(p, "pull2", "pull_up", SHORT_JUMPER_M)
    hook = HOOK["floor"] + HOOK["span"] * float(flat["S23"]) / 100.0 * (.9 + .1 * p.balance) \
        + HOOK["k_reach"] * (float(flat["P03"]) - 270.0) / 10.0
    table = [0.0] * N_KINDS
    table[KIND_INDEX["rim_drive"]] = rim("rim_drive")
    table[KIND_INDEX["rim_finish"]] = rim("rim_finish")
    table[KIND_INDEX["floater"]] = _finish(p, "floater")
    table[KIND_INDEX["hook"]] = min(.85, max(.15, hook))
    table[KIND_INDEX["short_jumper"]] = short_j
    table[KIND_INDEX["mid_catch"]] = catch2_mid
    table[KIND_INDEX["mid_pull"]] = _jumper(p, "pull2", "pull_up", MID_PULLUP_M)
    table[KIND_INDEX["three_corner"]] = _jumper(p, "catch3", "catch", CORNER_M)
    table[KIND_INDEX["three_catch"]] = catch3_atb
    table[KIND_INDEX["three_pull"]] = _jumper(p, "pull3", "pull_up", ATB_M)
    table[KIND_INDEX["putback"]] = rim("putback")
    table[KIND_INDEX["trans_rim"]] = _sig(_logit(rim("trans_rim")) + TRANSITION_MAKE_LOGIT)
    table[KIND_INDEX["trans_three"]] = _sig(_logit(catch3_atb) + TRANSITION_MAKE_LOGIT * .5)
    table[KIND_INDEX["heave"]] = HEAVE_MAKE
    return table


def shot_menu(flat: Mapping[str, float]) -> list[float]:
    """Probability of each half-court shot kind given he shoots (sums to 1). Reproduces T02 apart from the rim share,
    which leaves room for his putbacks and transition finishes (MENU rim_halfcourt)."""
    regions = [max(0.0, float(flat.get(f"T02.{r}", .25))) for r in ("rim", "short_paint", "midrange", "three")]
    regions[0] *= MENU["rim_halfcourt"]
    regions[3] *= MENU["three_halfcourt"]
    tot = sum(regions) or 1.0
    rim, short, mid, three = (r / tot for r in regions)
    drive = max(1e-3, float(flat.get("T01.drive", .15)))
    post = max(1e-3, float(flat.get("T01.post", .03)))
    shoot = max(1e-3, float(flat.get("T01.shoot", .25)))
    cut = float(flat.get("T09", .3))
    roll = float(flat.get("T11.roll", .2)) + float(flat.get("T11.slip", .1))
    w_rim = (drive, MENU["rim_cut"] * cut * .5 + MENU["rim_roll"] * roll * .5, MENU["rim_post"] * post)
    s = sum(w_rim)
    w_short = (drive, MENU["short_post"] * post, MENU["short_shoot"] * shoot)
    ss = sum(w_short)
    catch, pull, move = (max(1e-6, float(flat.get(f"T03.{m}", 1 / 3))) for m in ("catch", "pull_up", "movement"))
    pull_share = pull / (catch + pull + move)
    menu = [0.0] * N_KINDS
    menu[KIND_INDEX["rim_drive"]] = rim * w_rim[0] / s
    menu[KIND_INDEX["rim_finish"]] = rim * w_rim[1] / s
    # A post finish at the rim is a short post-up; it is resolved as a hook-zone post finish at the rim's make rate.
    menu[KIND_INDEX["rim_drive"]] += rim * w_rim[2] / s * .5
    menu[KIND_INDEX["rim_finish"]] += rim * w_rim[2] / s * .5
    menu[KIND_INDEX["floater"]] = short * w_short[0] / ss
    menu[KIND_INDEX["hook"]] = short * w_short[1] / ss
    menu[KIND_INDEX["short_jumper"]] = short * w_short[2] / ss
    menu[KIND_INDEX["mid_pull"]] = mid * pull_share
    menu[KIND_INDEX["mid_catch"]] = mid * (1 - pull_share)
    menu[KIND_INDEX["three_pull"]] = three * pull_share
    menu[KIND_INDEX["three_corner"]] = three * (1 - pull_share) * MENU["corner_share"]
    menu[KIND_INDEX["three_catch"]] = three * (1 - pull_share) * (1 - MENU["corner_share"])
    return menu


def transition_menu(flat: Mapping[str, float]) -> list[float]:
    regions = [max(0.0, float(flat.get(f"T02.{r}", .25))) for r in ("rim", "short_paint", "midrange", "three")]
    tot = sum(regions) or 1.0
    rim = TRANS["rim_base"] + regions[0] / tot + .5 * regions[1] / tot
    three = TRANS["three_scale"] * regions[3] / tot
    mid = .3 * regions[2] / tot
    s = rim + three + mid
    menu = [0.0] * N_KINDS
    menu[KIND_INDEX["trans_rim"]] = rim / s
    menu[KIND_INDEX["trans_three"]] = three / s
    menu[KIND_INDEX["mid_pull"]] = mid / s
    return menu


def league_means(flats: Mapping[str, Mapping[str, float]]) -> dict[str, float]:
    keys = set(PERIMETER_D) | set(RIM_D) | set(PRESSURE_D) | set(CREATION) | {"P03"}
    out = {}
    for k in keys:
        vals = [float(f[k]) for f in flats.values() if k in f]
        out[k] = sum(vals) / len(vals) if vals else 50.0
    return out


def _index(flat: Mapping[str, float], keys: tuple, means: Mapping[str, float]) -> float:
    return sum((float(flat.get(k, means.get(k, 50.0))) - means.get(k, 50.0)) for k in keys) / (25.0 * len(keys))


class Card:
    """Precomputed numbers for one player (plain attributes; the loop reads them in tight code)."""
    __slots__ = ("pid", "name", "group", "height", "usage", "to_logit", "menu", "menu_cum", "trans_cum", "make_logit",
                 "ft", "ast_w", "foul", "foul_s", "and1", "ns_draw", "off_foul_w", "d_foul", "ns_mult", "stl_w",
                 "blk_w", "perim_d", "rim_d", "press_d", "reb", "pace", "trans_pref", "penalty", "flat", "create",
                 "space")

    def actions(self) -> dict[str, float]:
        out = {a: 0.0 for a in ACTIONS}
        for i, w in enumerate(self.menu):
            out[KINDS[i][1]] = out.get(KINDS[i][1], 0.0) + w
        return out


def _cum(weights: list[float]) -> list[float]:
    out, acc = [], 0.0
    total = sum(weights) or 1.0
    for w in weights:
        acc += w / total
        out.append(acc)
    out[-1] = 1.0
    return out


def build_card(pid: str, name: str, flat: Mapping[str, float], means: Mapping[str, float], group: str = "wing",
               penalty: float = 0.0) -> Card:
    c = Card()
    c.pid, c.name, c.group, c.flat = pid, name, group, flat
    c.height = float(flat.get("P01", 200.0))
    c.penalty = penalty
    c.usage = math.exp(log_linear(USAGE, flat)) * (1.0 - .01 * penalty)
    c.to_logit = log_linear(TURNOVER, flat) + .01 * penalty
    c.menu = shot_menu(flat)
    c.menu_cum = _cum(c.menu)
    c.trans_cum = _cum(transition_menu(flat))
    # Tonight's tired legs or rust (health penalty points, as today's engine computes them) cost a little touch.
    c.make_logit = [_logit(p) - .03 * penalty for p in make_table(pid, flat)]
    c.ft = min(.98, max(.2, float(flat["S07"]) / 100.0))
    c.ast_w = math.exp(log_linear(ASSISTS_INPUTS, flat))
    prof = F.profile_from_flat(pid, flat)
    c.foul = prof
    fc = F.FITTED
    c.foul_s = (fc.k_craft * (prof.craft - 50) / 25 + fc.k_seek * prof.seek + fc.k_finish * (prof.contact_finish - 50) / 25
                + fc.k_strength * (prof.strength - 50) / 25)
    c.and1 = [F.and_one_probability(prof, z, fc) for z in range(4)]
    c.ns_draw = max(1e-3, prof.involvement) ** fc.k_ns_involvement * math.exp(fc.k_ns_craft * (prof.craft - 50) / 25 + fc.k_ns_seek * prof.seek)
    c.off_foul_w = max(1e-3, prof.involvement) * math.exp(fc.k_off_seek * prof.seek) + fc.k_off_screen * prof.screen * .2
    c.d_foul = -fc.k_control * (prof.control - 50) / 25 + fc.k_contest * (prof.contest - 50) / 25 + fc.k_jump * prof.jump
    c.ns_mult = F.defender_nonshooting_multiplier(prof, fc)
    c.stl_w = math.exp(log_linear(STEALS_INPUTS, flat))
    c.blk_w = math.exp(log_linear(BLOCKS, flat))
    c.perim_d = _index(flat, PERIMETER_D, means)
    c.rim_d = _index(flat, RIM_D, means) + .5 * (float(flat["P03"]) - means.get("P03", 265.0)) / 25.0
    c.press_d = _index(flat, PRESSURE_D, means) + .3 * (_logit(float(flat.get("T14", .3))) - _logit(.3))
    c.reb = R.prepare(R.profile_from_flat(pid, flat), R.FITTED)
    c.pace = float(flat.get("T05", .5))
    c.trans_pref = float(flat.get("T17.transition", .2))
    c.create = _index(flat, CREATION, means)
    c.space = float(flat.get("T02.three", .4)) * float(flat.get("S.three_mode", 50.0)) / 100.0
    return c


def card_for(pid: str, name: str, flat: Mapping[str, float], means: Mapping[str, float], group: str = "wing",
             penalty: float = 0.0) -> Card:
    key = (pid, id(flat), round(penalty, 2), _settings_key())
    card = _CARD_CACHE.get(key)
    if card is None:
        if len(_CARD_CACHE) > 20000:
            _CARD_CACHE.clear()
        card = build_card(pid, name, flat, means, group, penalty)
        _CARD_CACHE[key] = card
    return card


def _settings_key() -> tuple:
    """Cards depend on the module's conversion settings; research fits change them, so the cache keys on them."""
    return (tuple(sorted(USAGE.items())), tuple(sorted(TURNOVER.items())), tuple(sorted(HOOK.items())),
            tuple(sorted(DUNK.items())), tuple(sorted(MENU.items())), tuple(sorted(BLOCKS.items())),
            tuple(sorted(DUNK_BY_KIND.items())), TRANSITION_MAKE_LOGIT)


def flat_for_player(canonical: Mapping[str, Any], player: Mapping[str, Any]) -> dict[str, float] | None:
    """The player's flattened inputs as the engine currently uses them (development included), or None."""
    pid = player.get("id")
    key = ("flat", id(canonical), pid)
    if key in _LEAGUE:
        return _LEAGUE[key]
    from ..ratings_model import effective_inputs
    inputs = effective_inputs(canonical, pid) if pid else None
    flat = flatten_inputs(inputs) if inputs else None
    if flat is not None and not all(k in flat for k in ("S01", "S23", "S45", "P03", "P10", "T08", "T02.rim")):
        flat = None
    _LEAGUE[key] = flat
    return flat


def generic_flat(root) -> dict[str, float]:
    """League-median inputs (stand-in for players with no inputs, e.g. replayed players who left the league)."""
    key = ("generic", str(root))
    if key not in _LEAGUE:
        from .game_contexts import GENERIC, league_flat_inputs
        flats = league_flat_inputs(root)
        _LEAGUE[key] = flats[GENERIC]
        _LEAGUE[("means", str(root))] = league_means({k: v for k, v in flats.items() if k != GENERIC})
    return _LEAGUE[key]


def means_for(root) -> dict[str, float]:
    generic_flat(root)
    return _LEAGUE[("means", str(root))]
