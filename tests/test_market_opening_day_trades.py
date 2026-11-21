import unittest

from nba_gm_data.trade_calendar import FREE_AGENCY_TRADE_MEANS, free_agency_trade_slots


class MarketOpeningDayTradeTests(unittest.TestCase):
    """FA-REAL slice 2 moved the market's opening to June 30: that day is free-agency day 1 for AI trades too."""

    def test_june_30_is_a_trading_day_and_june_29_is_not(self):
        days = [free_agency_trade_slots(f"{year}-06-30", seed, 1) for year in range(2027, 2047) for seed in range(5)]
        self.assertGreater(sum(days), 0)
        self.assertAlmostEqual(sum(days) / len(days), FREE_AGENCY_TRADE_MEANS[1], delta=1.0)
        self.assertEqual(free_agency_trade_slots("2027-06-29", 17, None), 0)

    def test_july_still_counts(self):
        self.assertGreaterEqual(free_agency_trade_slots("2027-07-03", 17, 4), 0)
        self.assertEqual(free_agency_trade_slots("2027-08-03", 17, 4), 0)


if __name__ == "__main__":
    unittest.main()
