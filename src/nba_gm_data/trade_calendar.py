"""Seeded market opportunities by date; never a quota of forced accepted trades."""
from datetime import date
import math
import random


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


def market_day(stamp, seed, season_start, deadline):
    today, end = date.fromisoformat(stamp), date.fromisoformat(deadline)
    if today > end or today < date(season_start, 10, 1):
        return {'review': False, 'slots': 0}
    remaining = (end - today).days
    # Recent official trackers show quiet autumns, a January ramp, and most
    # in-season activity concentrated in the final week (see research report).
    peak = {0: 15., 1: 4., 2: 2.5, 3: 1.8, 4: 1.2, 5: .8, 6: .6}
    mean = peak.get(remaining, {10: .025, 11: .025, 12: .07, 1: .17, 2: .17}.get(today.month, 0))
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
