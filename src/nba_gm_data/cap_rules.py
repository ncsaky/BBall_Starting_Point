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
Later seasons grow 3.5% a year (the game's long-standing assumption), rounded to $0.1M.
"""
from __future__ import annotations

from .schema import CANONICAL_SEASON

BASE_SEASON = CANONICAL_SEASON          # "2026-27": the season the figures below are for
SALARY_CAP = 164_961_000
TAX_LINE = 200_428_000
FIRST_APRON = 209_015_000
SECOND_APRON = 221_686_000
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
    return round(value / 100_000) * 100_000


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


def max_salary(season: str | None, years_of_service: int) -> float:
    """The largest first-year salary (dollars) a player with this much service can sign for in ``season``."""
    return cap_lines_for_season(season)["salary_cap"] * max_salary_share(years_of_service)
