"""RATING-CEILING (2026-11-21): development has no hidden top in the 94-input ratings."""
import unittest

from nba_gm_data import health


class DevelopmentTopTests(unittest.TestCase):
    PLAYER = {"id": "player_test_young_star", "age": 22, "minutes_projection": 32}

    def gain(self, current, **kwargs):
        return health.monthly_trait_delta(self.PLAYER, "rim_deterrence", current, 22.0, 32.0, {}, 0.0, 17, "2026-12",
                                          1.0, None, expected=True, **kwargs)

    def test_a_hidden_rating_above_100_still_grows_in_the_new_ratings(self):
        # The best rim protectors already sit above 100 on this hidden rating; the older ratings' taper toward their
        # stored 0-100 bound stopped them from ever growing it.
        self.assertGreater(self.gain(105.0), 0.0)
        self.assertGreater(self.gain(95.0), self.gain(105.0) * 0.99)

    def test_gains_still_shrink_with_level_in_the_older_ratings(self):
        # DEV-CURVE (2026-11-21): the 94-input ratings grow at the same rate at every level (tests/test_dev_curve.py).
        values = [self.gain(level, curve=health.LEGACY_CURVE) for level in (50.0, 70.0, 85.0, 105.0)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_older_ratings_keep_their_stored_bound(self):
        self.assertEqual(self.gain(100.0, stored_bound=100.0), 0.0)
        self.assertAlmostEqual(self.gain(85.0, stored_bound=100.0), self.gain(85.0))


if __name__ == "__main__":
    unittest.main()
