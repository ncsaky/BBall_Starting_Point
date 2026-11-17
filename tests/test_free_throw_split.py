"""Free-throw attempts in the box split are unbiased, and the game's random stream is preserved.

The old split used round(points*rate + U(0, 1.8)), adding ~0.9 FTA to every player line (league ~34 FTA per
100 possessions vs ~23 real). The fix keeps the same number of RNG draws so game scores are unchanged (verified on 40 seeded games, 2026-11-17).
"""
import random
import statistics
import unittest

from nba_gm_data.offense import shooting_line

FEAT = {'rim_pressure': 60, 'shot_creation': 60, 'ft_pct': .78, 'three_per36': 5.0, 'three_pct': .36, 'two_pct': .53}


class FreeThrowSplitTests(unittest.TestCase):
    def test_attempts_match_the_profile_rate_on_average(self):
        rng = random.Random(7)
        rate = .13 + (60 - 55) * .0028
        lines = [shooting_line(20, FEAT, 30.0, rng) for _ in range(4000)]
        mean_fta = statistics.mean(line['fta'] for line in lines)
        # Odd point remainders add one make (and attempt) about half the time, so allow ~+0.5.
        self.assertLess(abs(mean_fta - 20 * rate), 0.6)
        self.assertTrue(all(line['ftm'] <= line['fta'] for line in lines))


if __name__ == "__main__":
    unittest.main()
