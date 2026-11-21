"""Seeded market opportunities by date; never a quota of forced accepted trades.

Real timing (TRADE-VOLUME-2, docs/agents/tasks/trade-volume-2.md; Basketball-Reference NBA_2026 transactions, Hoops
Rumors 2025 offseason and 2025-26 in-season trade lists, ESPN 2026 offseason tracker):
- 2025-26 league year: July 16 trades (14 of them on the two days the July moratorium ended), August 2, September 1,
  October to December 0, January 1, February 28 (Feb 1-5: 2, 0, 2, 6, then 18 on deadline day).
- Draft nights: 8 trades over the 2025 draft's two days, 11 on June 24 2026 (both counting pick-only swaps).
- 2026 offseason after the draft: July 8 (3 on July 1), August 3, September 2.
- Most players signed in the summer cannot be traded until December 15, so in-season trading before the deadline,
  when there is any, comes after mid-December.
"""
from datetime import date
import math
import random


def _poisson(rng, mean):
    product, count = 1., 0
    threshold = math.exp(-mean)
    while product > threshold:
        product *= rng.random()
        count += 1
    return max(0, count - 1)


def summer_offer_slots(stamp, seed):
    """July incoming proposals peak with the opening free-agent market."""
    day = date.fromisoformat(stamp)
    if day.month != 7 or day.day > 15:
        return 0
    mean = {1: 3., 2: 2., 3: 1.5, 4: 1., 5: .7, 6: .6, 7: .5}.get(day.day, .15)
    rng = random.Random(f'{seed}:{stamp}:summer-incoming-v1')
    product, slots = 1., 0
    while product > math.exp(-mean):
        product *= rng.random()
        slots += 1
    return min(4, max(0, slots-1))


# AI-to-AI trades on each free-agency day (the game's free agency is July 1-5). The real busiest July days were the
# two days the moratorium ended in 2025 (8 and 5 trades) and July 1 2026 (3); real Julys had 16 and 8 trades, most
# in the first week. The expected count over the five days is about 9.
FREE_AGENCY_TRADE_MEANS = {1: 3.5, 2: 2.5, 3: 1.5, 4: 1.0, 5: .8}
FREE_AGENCY_TRADES_PER_DAY = 6


def free_agency_trade_slots(stamp, seed, fa_day=None):
    """AI-to-AI trade slots on a free-agency day (TRADE-VOLUME-2; before, at most two trades a day)."""
    day = date.fromisoformat(stamp)
    # FA-REAL slice 2: the market opens June 30 (free-agency day 1), so that day counts too.
    if not (day.month == 7 or (day.month == 6 and day.day >= 30)):
        return 0
    key = int(fa_day or day.day)
    mean = FREE_AGENCY_TRADE_MEANS.get(key, .3)
    rng = random.Random(f'{seed}:{stamp}:{key}:free-agency-trades-v1')
    return min(FREE_AGENCY_TRADES_PER_DAY, _poisson(rng, mean))


# The rest of the summer: the game moves from the end of free agency straight to September 1, so the trades of
# late July and August happen in one market at the end of free agency (real: about 3 in late July and 2-3 in August
# each year); September is simulated day by day.
LATE_SUMMER_TRADE_MEAN = 4.5
LATE_SUMMER_TRADES_MAX = 8
SEPTEMBER_DAILY_MEAN = .06


def late_summer_trade_slots(season_start, seed):
    rng = random.Random(f'{seed}:{season_start}:late-summer-trades-v1')
    return min(LATE_SUMMER_TRADES_MAX, _poisson(rng, LATE_SUMMER_TRADE_MEAN))


def market_day(stamp, seed, season_start, deadline):
    today, end = date.fromisoformat(stamp), date.fromisoformat(deadline)
    if today.month == 9 and today.year == season_start:
        # Training camp (TRADE-VOLUME-2): a few September trades, no inbound offers beyond the usual review days.
        rng = random.Random(f'{seed}:{stamp}:trade-market-day-v1')
        slots = _poisson(rng, SEPTEMBER_DAILY_MEAN)
        return {'review': bool(slots), 'slots': slots, 'offer_slots': 0, 'climate': 1.0,
                'expected_slots': SEPTEMBER_DAILY_MEAN}
    if today > end or today < date(season_start, 10, 1):
        return {'review': False, 'slots': 0}
    remaining = (end - today).days
    # Recent official trackers show quiet autumns, a January ramp, and most
    # in-season activity concentrated in the final week (see research report).
    # December: players signed in the summer become tradable on December 15 (TRADE-VOLUME-2 moved December's
    # opportunities after that date; the month's total is about the same).
    # TRADE-MARKET: the last two days follow the real 2026 deadline (6 trades the day before, 18 on the day); before,
    # 4 and 15. Slots are only room for deals: the market (negotiations, final offers) has to supply them.
    peak = {0: 18., 1: 5., 2: 2.5, 3: 1.8, 4: 1.2, 5: .8, 6: .6}
    december = .03 if today.day < 15 else .12
    mean = peak.get(remaining, {10: .025, 11: .025, 12: december, 1: .17, 2: .17}.get(today.month, 0))
    climate = random.Random(f'{seed}:{season_start}:trade-market-climate-v1').uniform(.8, 1.2)
    rng = random.Random(f'{seed}:{stamp}:trade-market-day-v1')
    product, threshold, slots = 1., math.exp(-mean * climate), 0
    while product > threshold:
        product *= rng.random()
        slots += 1
    slots = min(24, max(0, slots - 1))
    # Listening to proposals is more frequent than completing trades. Inbound
    # user offers therefore do not disappear on zero-AI-transaction days.
    offer_rng = random.Random(f'{seed}:{stamp}:incoming-market-day-v1')
    product, offers = 1., 0
    while product > math.exp(-mean * climate * 2):
        product *= offer_rng.random()
        offers += 1
    offer_slots = min(4, max(0, offers-1))
    return {'review': bool(slots or offer_slots or today.weekday() in (0, 3)), 'slots': slots,
            'offer_slots': offer_slots,
            'climate': round(climate, 4), 'expected_slots': round(mean * climate, 4)}
