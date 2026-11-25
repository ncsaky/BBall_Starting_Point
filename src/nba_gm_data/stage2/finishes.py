"""How teams play the last five minutes of the 4th quarter and overtime (S2-FINISHES).

Real teams change how they play late in a game, by the score and the clock:
- leaders and tied teams slow down (with 2-5 minutes left, 17-18 seconds a possession against 14-16 for trailing teams);
- trailing teams hurry in the last two minutes (8-9 seconds a possession when down 4-10 with under a minute left) and
  shoot more threes (about half their possessions end in one);
- free throws rise late (the bonus, physical defense, deliberate fouls), and the trailing side scores a little more
  efficiently.
Before this piece Stage 2 played the last five minutes like any other stretch (about 14.3 seconds a possession for
everyone), so its margins spread out where real ones tighten: within three points with a minute left 16.5% of games
against a real 19.3%, which kept close finishes and overtime low.

The table (stage2.finishes_table, written by scripts/research/s2_finishes_fit.py) gives four numbers for each situation
(time left: 2-5 minutes, 1-2 minutes, 24-60 seconds, the last 24 seconds; the offense's margin in nine bands):
- len: multiplier on the half-court possession length (the part above its floor);
- three: log-odds tilt toward the three-point shots on the scorer's menu;
- foul: shooting-foul log-odds shift;
- make: make log-odds shift on every shot (what the situation does to shot quality: a leader's late-clock isolations,
  a trailing team's urgency, a last shot against a set defense);
- make3: an extra make log-odds shift on threes (S2-LAST-POSSESSION: one shift for every shot fitted points per
  possession, but left a trailing team's late threes far too accurate, 36-43% against a real 25-30%, and its twos too
  inaccurate, so ties and close finishes came out wrong; twos and threes are now fitted to their own real percentages);
- tov: turnover log-odds shift (late pressure, a leader's shot-clock run-downs, hurried trailing possessions).
Each is fitted to the real play-by-play of the rotation study's fit seasons (2023-24 and 2024-25 regular seasons,
public archive github.com/ramirobentes/nba_data), per possession: seconds, threes, free throws and points. 2025-26 is
the check season. Only the league-level behaviour is fitted: who takes the shots, how well they make them and how
often they draw fouls stay the players' own ratings.
"""
from __future__ import annotations

from .finishes_table import CELLS as _CELLS, TAKE_LATE, UP_THREE
from .finishes_table import EXACT as _EXACT

T_BANDS = ("0_24", "24_60", "60_120", "120_300")
M_BANDS = ("-11", "-10_-7", "-6_-4", "-3_-1", "0", "1_3", "4_6", "7_10", "11+")
NEUTRAL = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
TAKE_KEYS = ("1", "2", "3", "4", "5", "6", "7_10", "11_plus")


def t_band(t_left: float) -> int:
    return 0 if t_left <= 24.0 else 1 if t_left <= 60.0 else 2 if t_left <= 120.0 else 3 if t_left <= 300.0 else -1


def m_band(m: int) -> int:
    if m <= -11:
        return 0
    if m <= -7:
        return 1
    if m <= -4:
        return 2
    if m <= -1:
        return 3
    if m == 0:
        return 4
    if m <= 3:
        return 5
    if m <= 6:
        return 6
    if m <= 10:
        return 7
    return 8


def _pad(v) -> tuple:
    v = tuple(v)
    return v + NEUTRAL[len(v):]


def _grid(cells: dict) -> list[list[tuple]]:
    return [[_pad(cells.get(f"{tb}|{mb}", NEUTRAL)) for mb in M_BANDS] for tb in T_BANDS]


def _exact(grid, exact: dict) -> dict:
    """In the last minute a team down 1, 2 or 3 is playing to tie or to win: its band's (-3_-1) terms plus fitted
    adjustments for the exact deficit: the three-point tilt (real: threes on 24% / 42% / 51% of possessions in the
    last 24 seconds when down 1 / 2 / 3), the two-point make shift and the turnover shift (S2-LAST-POSSESSION: a team
    up three guards the line and gives up twos, real teams down three make about 64% of their late twos; down two
    they turn it over about 5% of the time). An entry is a number (the tilt alone) or (tilt, twos, turnovers); the
    twos' shift leaves threes as they were."""
    out = {}
    for tb in (0, 1):
        for m in (-1, -2, -3):
            ln, th, fo, mk, mk3, tv = grid[tb][3]
            v = exact.get(f"{T_BANDS[tb]}|{m}", 0.0)
            et, e2, eo = (v, 0.0, 0.0) if isinstance(v, (int, float)) else tuple(v)
            out[tb, m] = (ln, th + et, fo, mk + e2, mk3 - e2, tv + eo)
    return out


GRID = _grid(_CELLS)
GRID_X = _exact(GRID, _EXACT)


def install(cells: dict, exact: dict | None = None) -> None:
    """Research: replace the table (scripts/research/s2_finishes_fit.py)."""
    global GRID, GRID_X
    GRID = _grid(cells)
    GRID_X = _exact(GRID, exact or {})


def take_key(lead: int) -> str:
    return str(lead) if lead <= 6 else "7_10" if lead <= 10 else "11_plus"


def cell(t_left: float, margin: int) -> tuple | None:
    tb = t_band(t_left)
    if tb < 0:
        return None
    if tb <= 1 and -3 <= margin <= -1:
        return GRID_X[tb, margin]
    return GRID[tb][m_band(margin)]


__all__ = ["cell", "install", "t_band", "m_band", "take_key", "T_BANDS", "M_BANDS", "NEUTRAL", "TAKE_KEYS", "TAKE_LATE",
           "UP_THREE"]
