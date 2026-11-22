"""Stage 2 player-on-player matchups: who guards whom, and the defender's own skills on each shot, foul and turnover.

Who guards whom (`assign`): each time either five changes, the defense picks the assignment (one of the 120 ways to
pair five defenders with five scorers) that maximises
    sum over pairs of  - w_size * ((his height - the scorer's height) / 8.4 cm)^2
                       + w_star * (the scorer's threat) * (the defender's on-ball stopping index)
                       + w_hide * (the defender's rim-protection index) * (how little the scorer spaces the floor)
- size: like guards like (height, P01);
- threat: the scorer's usage weight (log, centred on his five): the coach puts his best on-ball stopper on the
  scorer who ends the most possessions; the head coach's matchup rating scales it (a stand-in: the coach inputs hold no
  switching or scheme habit);
- hide: the rim protector guards the scorer who spaces the floor least, so he can stay near the rim.
The weights are FITTED (scripts/research/s2_matchups_fit.py) so each defender's average assignment follows Basketball
Index's 2025-26 "Avg Height Guarded" and "Guarded USG%" for that defender (fit half of the players, checked on the
other half).

The defender's skills on each action (`PairTerms`), all as make / foul / turnover log-odds, computed once per
pairing and read by the loop:
- catch-and-shoot jumpers: the shooter's own defender's closeout (closeout technique S40, lateral quickness P07,
  attention S44) and the five's rotation (rotation recognition S38, off-ball positioning S39);
- pull-ups and short jumpers: the on-ball contest (containment S33, contest technique S37, length P02 against the
  shooter's height);
- drives: the chance he gets past his man (burst P05, dribble manipulation S16, separation S19 against containment S33,
  contact leverage S34, anticipation S41, lateral quickness P07). A driver who is past his man meets the help (the
  five's rim protection and rotation); one who is not, finishes over his own man. Getting past him also draws more
  fouls (a defender recovering from behind, a late helper) and his foul control (S45) decides how many;
- post-ups: his post defense (contact leverage S34, strength P08, height);
- turnovers: his own ball pressure (anticipation S41, on-ball steal technique S42, gambling habit T14) and the five's
  passing-lane defense (interception technique S43, anticipation).
The exact physics pieces (creation_passing.containment_response and helper_response, the closeout parts of
shot_geometry) are the references these fast rules stand in for. No rating is moved here (AGENTS.md rule 1).
"""
from __future__ import annotations

import itertools
import math

PERMS = tuple(itertools.permutations(range(5)))
HEIGHT_SD_CM = 8.4

# Assignment weights. FITTED (s2_matchups_fit.py, fit half of defenders; see the report for the held-out check).
ASSIGN = {"w_size": 1.0, "w_star": 6.0, "w_hide": 0.5}


def assign(off: list, de: list, coach_scale: float = 1.0, w: dict | None = None) -> list[int]:
    """offensive slot -> defensive slot guarding him."""
    w = ASSIGN if w is None else w
    ws, wt, wh = w["w_size"], w["w_star"] * coach_scale, w["w_hide"]
    lu = [math.log(max(1e-3, c.usage)) for c in off]
    mu = sum(lu) / 5.0
    threat = [x - mu for x in lu]
    st = [c.contain_d for c in de]
    ms = sum(st) / 5.0
    rp = [c.rim_d for c in de]
    mr = sum(rp) / 5.0
    sp = [c.space for c in off]
    msp = sum(sp) / 5.0
    score = [[0.0] * 5 for _ in range(5)]   # score[j][i]: defender j on scorer i
    for j in range(5):
        hj = de[j].height
        sj = st[j] - ms
        rj = rp[j] - mr
        row = score[j]
        for i in range(5):
            d = (hj - off[i].height) / HEIGHT_SD_CM
            row[i] = -ws * d * d + wt * threat[i] * sj + wh * rj * (msp - sp[i]) * 4.0
    best, best_p = -1e18, PERMS[0]
    s0, s1, s2, s3, s4 = score
    for p in PERMS:
        v = s0[p[0]] + s1[p[1]] + s2[p[2]] + s3[p[3]] + s4[p[4]]
        if v > best:
            best, best_p = v, p
    out = [0] * 5
    for j, i in enumerate(best_p):
        out[i] = j
    return out
