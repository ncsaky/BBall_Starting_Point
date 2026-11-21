"""The offseason calendar (FA-REAL slice 2): one place for every offseason date, computed for each season.

The real 2026 calendar (``docs/agents/tasks/fa-realism-research.md``, NBA key dates and the 2023 CBA):
- the draft lottery on Sunday May 10, during the playoffs;
- the Finals end mid-June (June 13 in 2026), then teams may talk to their own free agents;
- the draft on June 23-24;
- June 29: the last day to decide player and team options and to send qualifying offers;
- June 30 (6 p.m.): talks with other teams' free agents open; July 1: the new league year;
- July 13: the last day to pull a qualifying offer and keep the player's Bird rights;
- October 1: the last day a restricted free agent may accept his qualifying offer;
- the day before opening night (October 19 in 2026): opening rosters (15 standard players) and the rookie-scale
  extension deadline;
- October 31, or the next business day (November 2 in 2026): rookie-scale team options for the following season.

The game's own schedule decides two things:
- its Finals start June 4 with games every other day, so they end June 10-16; the offseason opens on June 17, the day
  after the latest possible Finals game, in every season;
- its regular seasons open on the date of the generated schedule (October 21), so its roster and rookie-extension
  deadline is that day minus one (October 20). The rule is the same as the league's: the day before opening night.

**One date switches the contract season for everything** (``contract_season``): from the day the offseason opens
(June 17) rosters, payrolls, cap holds, signings, extensions and trades all count the next season. Before, the save
switched on June 22, the signing helper by phase name, and the season label at the October rollover. The July 1 league
year only starts the empty-roster charges (cap room) and the market for other teams' free agents opens the day before.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

OFFSEASON_OPENS_MONTH_DAY = (6, 17)   # the day after the game's latest possible Finals game (June 16)
LATEST_FINALS_MONTH_DAY = (6, 16)
DECISIONS_DEADLINE_MONTH_DAY = (6, 29)  # options and qualifying offers (CBA Art. XI §4, Art. XII)
MARKET_OPENS_MONTH_DAY = (6, 30)        # talks with other teams' free agents (6 p.m.)
LEAGUE_YEAR_MONTH_DAY = (7, 1)
QO_WITHDRAW_MONTH_DAY = (7, 13)         # pull a qualifying offer and keep Bird rights (Art. XI §4(c))
QO_EXPIRES_MONTH_DAY = (10, 1)          # last day to accept a qualifying offer (Art. XI §4(c))
LATE_SUMMER_PASS_MONTH_DAY = (8, 1)
CAMP_MONTH_DAY = (9, 1)                 # the game's training-camp phase (real camps open late September)
DEFAULT_OPENING_MONTH_DAY = (10, 21)    # the generated schedules' opening night
MARKET_DAYS = 5                         # the first wave: market days June 30 - July 4


def _d(year: int, month_day: tuple[int, int]) -> date:
    return date(int(year), month_day[0], month_day[1])


def lottery_date(end_year: int) -> date:
    """The Sunday between May 8 and May 14 (May 10 in 2026; the real lotteries were May 10-16)."""
    day = date(int(end_year), 5, 8)
    return day + timedelta(days=(6 - day.weekday()) % 7)


def draft_dates(end_year: int) -> tuple[date, date]:
    """Round one on the first Tuesday on or after June 22 (June 23 in 2026), round two the next day."""
    day = date(int(end_year), 6, 22)
    first = day + timedelta(days=(1 - day.weekday()) % 7)
    return first, first + timedelta(days=1)


def next_business_day(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def rookie_option_deadline(season_start_year: int) -> date:
    """October 31 of the season's start year, or the next weekday (November 2 in 2026)."""
    return next_business_day(date(int(season_start_year), 10, 31))


def opening_night(season_start_year: int, save: dict[str, Any] | None = None) -> date:
    """The first regular-season game of the season that starts in ``season_start_year`` (the save's schedule when it
    has one, else the generated schedules' October 21)."""
    label = f"{int(season_start_year)}-{str(int(season_start_year) + 1)[-2:]}"
    games = (((save or {}).get("season_schedules") or {}).get(label) or {}).get("games") or []
    dates = [str(g.get("gameDate") or "") for g in games if g.get("phase") == "regular" and g.get("gameDate")]
    if dates:
        return date.fromisoformat(min(dates)[:10])
    return _d(season_start_year, DEFAULT_OPENING_MONTH_DAY)


def roster_deadline(season_start_year: int, save: dict[str, Any] | None = None) -> date:
    """Opening rosters and the rookie-scale extension deadline: the day before opening night."""
    return opening_night(season_start_year, save) - timedelta(days=1)


def offseason_dates(end_year: int, save: dict[str, Any] | None = None) -> dict[str, str]:
    """Every offseason date for the summer after the season that ends in ``end_year`` (ISO strings)."""
    y = int(end_year)
    draft_one, draft_two = draft_dates(y)
    return {
        "lottery": lottery_date(y).isoformat(),
        "finals_latest": _d(y, LATEST_FINALS_MONTH_DAY).isoformat(),
        "offseason_opens": _d(y, OFFSEASON_OPENS_MONTH_DAY).isoformat(),
        "draft_round_one": draft_one.isoformat(),
        "draft_round_two": draft_two.isoformat(),
        "after_draft": (draft_two + timedelta(days=1)).isoformat(),
        "decisions_deadline": _d(y, DECISIONS_DEADLINE_MONTH_DAY).isoformat(),
        "market_opens": _d(y, MARKET_OPENS_MONTH_DAY).isoformat(),
        "league_year": _d(y, LEAGUE_YEAR_MONTH_DAY).isoformat(),
        "market_wave_ends": (_d(y, MARKET_OPENS_MONTH_DAY) + timedelta(days=MARKET_DAYS - 1)).isoformat(),
        "qualifying_offer_withdrawal": _d(y, QO_WITHDRAW_MONTH_DAY).isoformat(),
        "late_summer_pass": _d(y, LATE_SUMMER_PASS_MONTH_DAY).isoformat(),
        "camp": _d(y, CAMP_MONTH_DAY).isoformat(),
        "qualifying_offers_expire": _d(y, QO_EXPIRES_MONTH_DAY).isoformat(),
        "roster_deadline": roster_deadline(y, save).isoformat(),
        "rookie_extension_deadline": roster_deadline(y, save).isoformat(),
        "opening_night": opening_night(y, save).isoformat(),
        "rookie_option_deadline": rookie_option_deadline(y).isoformat(),
    }


def end_year_of_date(value: str) -> int:
    """The ending year of the season a date belongs to for offseason purposes (July onward is the next season)."""
    day = date.fromisoformat(str(value)[:10])
    return day.year + 1 if day.month >= 7 else day.year


def offseason_has_opened(value: str) -> bool:
    """Whether ``value`` is on or after the offseason opening (June 17) of its season's ending year."""
    day = date.fromisoformat(str(value)[:10])
    return day.month <= 6 and (day.month, day.day) >= OFFSEASON_OPENS_MONTH_DAY


def season_label(start_year: int) -> str:
    return f"{int(start_year)}-{str(int(start_year) + 1)[-2:]}"


def contract_season(save: dict[str, Any], today: str | None = None) -> str:
    """The contract season everything counts in on ``today`` (the one switch date; see the module notes).

    The save's season label (``meta.season``) changes at the October rollover; from the day the offseason opens until
    then, the contract season is the next one."""
    meta = str((save.get("meta") or {}).get("season") or "2026-27")
    start = int(meta[:4])
    current = str(today or (save.get("state") or {}).get("current_date") or "")
    if current and current >= _d(start + 1, OFFSEASON_OPENS_MONTH_DAY).isoformat():
        return season_label(start + 1)
    return meta


def phase_for_month_day(value: str) -> str | None:
    """The offseason phase for a date between the playoffs and preseason (None for other dates).

    - ``playoffs`` through June 16;
    - ``re_signing``: stop 1, deciding who to keep, from June 17 to June 29 except the two draft days;
    - ``draft``: the two draft days;
    - ``free_agency``: stop 2, the market, from June 30 through July 15 (the first wave runs June 30 - July 4; the
      phase keeps its July 15 end so late first-wave days and the signing-day recap stay in it);
    - ``offseason``: late summer (July 16 - August 31), in the background;
    - ``training_camp``: September."""
    day = date.fromisoformat(str(value)[:10])
    md = (day.month, day.day)
    if (4, 18) <= md <= LATEST_FINALS_MONTH_DAY:
        return "playoffs"
    if OFFSEASON_OPENS_MONTH_DAY <= md <= DECISIONS_DEADLINE_MONTH_DAY:
        one, two = draft_dates(day.year)
        return "draft" if one <= day <= two else "re_signing"
    if MARKET_OPENS_MONTH_DAY <= md <= (7, 15):
        return "free_agency"
    if (7, 16) <= md <= (8, 31):
        return "offseason"
    if day.month == 9:
        return "training_camp"
    return None
