"""The league's salary-cap lines, one source for every part of the game (TRADE-VOLUME).

Before this module the trade code counted a year of cap growth from 2025-26 while the screens, free agency and
waivers counted it from 2026-27, so the trade AI's 2026-27 tax line was $207.4M against the real $200.4M (and its hard
cap $229.4M against $221.7M). Every caller now asks ``cap_lines_for_season``.

Real 2026-27 figures (NBA announcement, pr.nba.com "NBA sets Salary Cap for 2026-27 season at $164.961 million";
aprons as reported from the league's numbers by Bleacher Report, July 2026):
- salary cap $164.961M
- luxury tax line $200.428M
- first apron $209.015M
- second apron $221.686M (the game's hard cap for trades and signings)
- salary floor $148.465M (90% of the cap)
FA-REAL slice 1: the lines are exact (no rounding; before they were rounded to $0.1M, so the 2026-27 cap read
$165.0M). Later seasons grow 3.5% a year (the game's long-standing assumption), to the dollar. The real cap grows with
league revenue, at most 10% a year (CBA Art. VII §2); no better documented projection exists in the repo.
"""
from __future__ import annotations

from .schema import CANONICAL_SEASON

BASE_SEASON = CANONICAL_SEASON          # "2026-27": the season the figures below are for
SALARY_CAP = 164_961_000
TAX_LINE = 200_428_000
FIRST_APRON = 209_015_000
SECOND_APRON = 221_686_000
SALARY_FLOOR = 148_465_000
ANNUAL_CAP_GROWTH_RATE = 0.035


def season_start(season: str | None) -> int:
    try:
        return int(str(season or BASE_SEASON).split("-")[0])
    except (TypeError, ValueError):
        return int(BASE_SEASON[:4])


def growth_factor(season: str | None) -> float:
    elapsed = max(0, season_start(season) - season_start(BASE_SEASON))
    return (1.0 + ANNUAL_CAP_GROWTH_RATE) ** elapsed


def _round(value: float) -> float:
    """To the dollar (FA-REAL: the lines are exact; they used to be rounded to $0.1M)."""
    return float(round(value))


_CACHE: dict[str, dict[str, float]] = {}


def cap_lines_for_season(season: str | None) -> dict[str, float]:
    """Salary cap, tax line, aprons and hard cap (dollars) for a season, plus the growth factor from 2026-27.

    Returns a fresh dict each call (callers may annotate it)."""
    key = str(season or BASE_SEASON)
    lines = _CACHE.get(key)
    if lines is None:
        factor = growth_factor(key)
        lines = {
            "salary_cap": _round(SALARY_CAP * factor),
            "tax_line": _round(TAX_LINE * factor),
            "first_apron": _round(FIRST_APRON * factor),
            "second_apron": _round(SECOND_APRON * factor),
            "hard_cap": _round(SECOND_APRON * factor),
            "salary_floor": _round(SALARY_FLOOR * factor),
            "growth_factor": round(factor, 5),
        }
        _CACHE[key] = lines
    return dict(lines)


# Maximum salaries (TRADE-VOLUME-2): a player's first-year salary on a new contract is at most a share of that season's
# salary cap by his years in the league: 25% with 0-6 years of service, 30% with 7-9, 35% with 10 or more (the CBA's
# maximum-salary rule as summarised by RealGM and Hoops Rumors; data/research/free_agent_contracts_2025_2026.json).
MAX_SALARY_SHARES = ((10, 0.35), (7, 0.30), (0, 0.25))


def max_salary_share(years_of_service: int) -> float:
    return next(share for years, share in MAX_SALARY_SHARES if int(years_of_service) >= years)


def max_salary(season: str | None, years_of_service: int, previous_salary: float = 0.0) -> float:
    """The largest first-year salary (dollars) a player with this much service can sign for in ``season``: his share
    of the cap, or 105% of his previous salary if that is higher (CBA Art. II §7; FA-REAL)."""
    share = cap_lines_for_season(season)["salary_cap"] * max_salary_share(years_of_service)
    return max(share, 1.05 * max(0.0, float(previous_salary or 0.0)))


# Bird rights (KEEP-STARS): a team may go over the salary cap, the tax line and the aprons to re-sign its own free
# agent, within a salary limit set by how long he has been with the team. Real rules (2023 CBA, as summarised by Hoops
# Rumors' glossary entries "Bird Rights" (March 2026) and "Early Bird Rights" (March 2026), and Larry Coon's CBA FAQ):
# - full Bird: three seasons with the team without being waived or changing teams as a free agent (a trade keeps the
#   clock running; a partial first season counts). Any salary up to his maximum, up to five years, 8% raises.
# - Early Bird: two such seasons. The greater of 175% of his previous salary or 105% of the league's average salary
#   (never above the max), two to four years, 8% raises.
# - Non-Bird: one season or less. 120% of his previous salary (or 120% of the minimum), up to four years, 5% raises.
# - Every other team (no Bird rights) offers at most four years with 5% raises.
# - Re-signing with Bird rights never triggers a hard cap, so it may take a team past the second apron (the game's
#   hard cap for trades and outside signings).
FULL_BIRD_SEASONS = 3
EARLY_BIRD_SEASONS = 2
BIRD_MAX_YEARS = {"full": 5, "early": 4, "non": 4}
OUTSIDE_MAX_YEARS = 4
BIRD_RAISE = {"full": 0.08, "early": 0.08, "non": 0.05}
OUTSIDE_RAISE = 0.05
EARLY_BIRD_PREVIOUS_SHARE = 1.75
EARLY_BIRD_AVERAGE_SHARE = 1.05
NON_BIRD_PREVIOUS_SHARE = 1.20
LEAGUE_MINIMUM = 1_900_000            # play.league_minimum_aav_millions
# The league's average salary as a share of the cap. An estimate (uncertain): about $12.5M against the $154.6M
# 2025-26 cap in public reporting. It only matters for Early Bird players on small salaries.
AVERAGE_SALARY_CAP_SHARE = 0.08


def bird_level(seasons_with_team: int) -> str:
    """'full', 'early' or 'non' for a free agent who has spent this many seasons with his team."""
    if int(seasons_with_team) >= FULL_BIRD_SEASONS:
        return "full"
    if int(seasons_with_team) >= EARLY_BIRD_SEASONS:
        return "early"
    return "non"


def bird_salary_limit(level: str, previous_salary: float, season: str | None, years_of_service: int) -> float:
    """The largest first-year salary (dollars) his own team may pay him over the cap with this Bird level."""
    previous = max(0.0, float(previous_salary or 0.0))
    ceiling = max_salary(season, years_of_service, previous)
    if level == "full":
        return ceiling
    if level == "early":
        average = cap_lines_for_season(season)["salary_cap"] * AVERAGE_SALARY_CAP_SHARE
        return min(ceiling, max(EARLY_BIRD_PREVIOUS_SHARE * previous, EARLY_BIRD_AVERAGE_SHARE * average))
    # Non-Bird: 120% of his previous salary or of his own minimum (by years of service; FA-REAL).
    from .cap_ledger import minimum_salary
    minimum = minimum_salary(season, years_of_service)
    return min(ceiling, max(NON_BIRD_PREVIOUS_SHARE * previous, NON_BIRD_PREVIOUS_SHARE * minimum))


def bird_max_years(level: str | None) -> int:
    return BIRD_MAX_YEARS.get(str(level), OUTSIDE_MAX_YEARS) if level else OUTSIDE_MAX_YEARS


def bird_raise(level: str | None) -> float:
    return BIRD_RAISE.get(str(level), OUTSIDE_RAISE) if level else OUTSIDE_RAISE
