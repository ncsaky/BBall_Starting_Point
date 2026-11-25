"""Stage 2 team ball-screen schemes (S2-SCHEMES): each coaching staff's habit on top of its personnel.

The coverage call (stage2.screens) follows the two defenders in the action. Real staffs also differ: Jordi Fernandez's
Nets pressure ball screens far more than their bigs alone suggest, Joe Mazzulla's Celtics and Chris Finch's Wolves sit
back. A staff's scheme is two log-odds tilts on the coverage call:
- aggression: drop less and trap more (show / at-level take the rest), from Basketball Index's ball-screen coverage
  aggression;
- switching: switch more, from the NBA matchup share of guards' time spent on centers.
Both are FITTED (scripts/research/s2_scheme_fit.py) as what is left of the team's 2025-26 measure after its personnel
(the engine's own coverage call on its replayed screens), times a reliability of .55 for the habit carrying over. The
table (scheme_table.py) is keyed by head coach. A coach who has moved to another team brings half his habit (the study
could not measure how far a coach's habits travel: one example); a coach with no 2025-26 record (new hires, interims)
has none, so his team's coverages follow its personnel. Old saves and other seasons work the same way: the head coach
on the save decides. No rating is moved here (AGENTS.md rule 1).
"""
from __future__ import annotations

import unicodedata

VERSION = "stage2_schemes_v1_2026_11_24"
ENABLED = True          # research switch (s2_scheme_fit.py measures the personnel-only call with it off)
MOVED_SHARE = .5        # share of his habit a coach brings to a new team (stand-in)
_TABLE: dict | None = None


def _norm(name: str) -> str:
    return unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower().strip()


def table() -> dict:
    global _TABLE
    if _TABLE is None:
        from .scheme_table import COACHES
        _TABLE = COACHES
    return _TABLE


def scheme_for(coach, team_abbrev: str) -> tuple[float, float]:
    """(aggression, switching) log-odds tilts for this head coach (a sim CoachRating or None) on this team."""
    if not ENABLED or coach is None:
        return 0.0, 0.0
    row = table().get(_norm(getattr(coach, "coach_name", "") or ""))
    if not row:
        return 0.0, 0.0
    share = 1.0 if row.get("team") == team_abbrev else MOVED_SHARE
    return share * float(row.get("aggression", 0.0)), share * float(row.get("switching", 0.0))
