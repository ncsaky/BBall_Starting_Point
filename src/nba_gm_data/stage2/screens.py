"""Stage 2 pick-and-roll: ball screens, the defense's coverage, and switching (S2-COACH, part 2).

The possession loop already decides who ends a possession and what he tries (usage and the shot menu, both fitted to
real 2025-26 data). This layer adds where that shot came from, without moving those fits:
- A scorer's self-created half-court shot (a drive, a floater, a pull-up or short jumper) comes off a ball screen with
  the league share below; the screener is a teammate chosen by how often and how well he screens (box_rates'
  screen-assist fit: screen execution S27, screen-action reads S28, screen and roll habits T11, body mass P04; out-of-
  fold r .85 with Basketball Index screen assists), leaning toward the teammate whose defender the offense wants in the
  action (the weakest on-ball defender: the "hunt", OKC bringing Haliburton into Gilgeous-Alexander's screens).
- A big's finish off a teammate's pass (rim_finish) is a roll or slip in the share his habits give it (T11 roll and
  slip against cutting T09, the same split the shot menu uses); the handler is a teammate chosen by usage.
- The defense's coverage of that screen, from the two defenders involved (the screener's defender and the ball's):
  * switch: likelier when the two defenders are of a size, when the screener's defender can stay in front (the
    containment index: S33, S34, S41, P07), and on guard-guard screens. The intercept is FITTED to the league switch
    share of ball screens (25.9%, 2025-26 tracking; docs/agents/tasks/defensive-scheme-evidence.md);
  * drop: likelier with a rim-protecting, less mobile screener's defender, less likely against a pull-up shooter
    (S02 and the pull-up habit T03) - the reason teams do not drop against elite pull-up shooters;
  * blitz (trap): rare, and mostly for the night's highest-usage scorers ("stars meet help");
  * show or at-level otherwise.
- What the coverage does (make, foul and turnover log-odds):
  * switch: the shot is played against the screener's defender: every matchup term (contest, containment, foul control,
    post defense, height and length) is that defender's, so a star switched onto a slow big gets past him more often and
    a switch onto a long wing contests his jumper better. A roll after a switch is finished over the smaller defender.
  * drop: the ball's defender is caught on the screen (the screen edge: screen quality S27, strength P08, balance P09
    and body mass P04 against screen navigation S35, lateral quickness P07, anticipation S41 and attention S44 - the
    inputs screen_navigation.resolve_screen turns into a navigation delay), so part of his contest is lost; the drive
    meets the screener's defender waiting at the rim; the roller is contained by his own big.
  * show / at-level: two defenders on the ball: harder pull-ups and drives, a few more turnovers; the roller is open
    unless the five rotates (rotation recognition S38, off-ball positioning S39).
  * blitz: more turnovers and a harder shot if he keeps it.
The exact physics piece (screen_navigation.resolve_screen) is the reference for the screen edge; it needs speed
measurements (P06, P07 in m/s) the league input bridge does not convert yet, so the fast rule is a documented stand-in
built from the same inputs. The coverage mix beyond the switch share and the effect sizes are stand-ins too (no public
team-level coverage frequencies; defensive-scheme-evidence.md section 5), checked only through the league numbers and
the betting test. No player rating is moved here (AGENTS.md rule 1).

Screen assists: when the handler scores directly off the screen the screener is credited with this share, FITTED to
the league's 7.29 screen assists per 100 possessions (2025-26 NBA hustle data).
"""
from __future__ import annotations

import math

VERSION = "stage2_screens_v1_2026_11_24"

SCREENS = {
    # Share of self-created half-court shots (drives, floaters, pull-ups, short jumpers) that come off a ball screen.
    # Stand-in from 2025-26 play types: pick-and-roll ball-handler endings 29.4 per 100 possessions against isolation
    # 7.4 and handoffs 4.5 (about 0.7 of self-created endings).
    "p_handler": .70,
    # The offense's hunt: screener weight x exp(k_hunt x how poor his defender is at staying in front).
    "k_hunt": .5,
    # Coverage choice (log-odds). switch0 is FITTED to the league switch share (25.9%; replayed 2025-26 games give 25.6%
    # with -0.85, the mix then drop 43%, show or at-level 28%, trap 3%); the rest are stand-ins.
    "switch0": -.83, "k_sim": .9, "k_mob": .8, "k_small": .9,
    "drop0": .35, "k_drop_rim": 1.0, "k_drop_mob": .8, "k_drop_threat": .9,
    "blitz0": -3.2, "k_blitz_star": 2.0,
    # Effects (make log-odds unless noted). Stand-ins checked through the league numbers.
    "drop_nav": .45, "k_edge": .25,     # share of the ball defender's contest lost on a drop, and per unit of screen edge
    "drop_open": .25,                    # ... and the openness that share is worth on a pull-up (a typical contest)
    "drop_help": .5,                     # weight of the screener's defender's rim protection on drives against a drop
    "k_drop_roll": .20,                  # the roller against his own dropping big (per rim-protection unit)
    "show_contest": .12, "show_beat": .5, "show_to": .10,
    "k_open_roll": .15,                  # the roller against a show or a trap, less the five's rotation
    "blitz_to": .45, "blitz_contest": .20,
    "k_mismatch": .10,                   # a roll finished over a smaller switched defender, per 10 cm of height
    # Screen assists: credited on this share of the handler's made shots off a screen. FITTED to 7.29 per 100
    # possessions (.93 gave 7.44 in replayed games). Off-ball screens for shooters are not played, so their share of the
    # league's screen assists is folded into the ball screens (stand-in).
    "p_screen_assist": .91,
}

SWITCH, DROP, SHOW, BLITZ = 1, 2, 3, 4
COVERAGE_NAMES = {SWITCH: "switch", DROP: "drop", SHOW: "show", BLITZ: "blitz"}


def _sig(z: float) -> float:
    if z < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def coverage_probabilities(handler, screener_def, ball_def, screener_is_big: bool, s: dict | None = None,
                           star: float = 0.0) -> tuple[float, float, float, float]:
    """(switch, drop, show, blitz) chances for one ball screen.
    handler: the ball handler's card; screener_def / ball_def: the cards of the screener's and the ball's defenders."""
    s = SCREENS if s is None else s
    sim = -abs(screener_def.height - ball_def.height) / 10.0
    mob = screener_def.contain_d
    p_switch = _sig(s["switch0"] + s["k_sim"] * sim + s["k_mob"] * mob + (0.0 if screener_is_big else s["k_small"]))
    threat = handler.pull_threat
    p_drop = _sig(s["drop0"] + s["k_drop_rim"] * screener_def.rim_d - s["k_drop_mob"] * mob - s["k_drop_threat"] * threat)
    p_blitz = _sig(s["blitz0"] + s["k_blitz_star"] * star)
    rest = 1.0 - p_switch
    drop = rest * p_drop
    blitz = rest * (1.0 - p_drop) * p_blitz
    return p_switch, drop, rest - drop - blitz, blitz


def choose(u: float, probs: tuple[float, float, float, float]) -> int:
    acc = 0.0
    for code, p in zip((SWITCH, DROP, SHOW, BLITZ), probs):
        acc += p
        if u <= acc:
            return code
    return SHOW


def screen_edge(screener, navigator) -> float:
    """How much the screen frees the ball (index units): screen quality and body against navigation (stand-in for
    screen_navigation.resolve_screen's navigation delay, built from the same inputs)."""
    return screener.screen_q - navigator.nav
