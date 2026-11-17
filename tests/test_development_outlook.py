"""Decline watch: expected hidden-rating change from the engine's own monthly development model."""
import unittest
from pathlib import Path

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.development_outlook import decline_summary, expected_rating_changes
from nba_gm_data.health import monthly_trait_delta
from nba_gm_data.save import decline_watch_value

ROOT = Path(__file__).resolve().parents[1]


class DevelopmentOutlookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_app_canonical(ROOT)
        cls.players = {p["name"]: p for p in cls.canonical["players"]}

    def test_expected_month_is_the_engine_month_without_noise(self):
        p = self.players["Paul George"]
        noisy = [monthly_trait_delta(p, "stamina_cardio", 70.0, 36.0, 28.0, {}, 0.0, seed, "2026-11", 0.32) for seed in range(400)]
        expected = monthly_trait_delta(p, "stamina_cardio", 70.0, 36.0, 28.0, {}, 0.0, 1, "2026-11", 0.32, expected=True)
        self.assertAlmostEqual(sum(noisy) / len(noisy), expected, delta=0.01)

    def test_veterans_decline_and_young_players_do_not(self):
        old = decline_summary(expected_rating_changes(self.canonical, self.players["Paul George"], 12, "2026-10"))
        young = decline_summary(expected_rating_changes(self.canonical, self.players["Cooper Flagg"], 12, "2026-10"))
        self.assertLess(old["per_year"], -0.3)
        self.assertLess(old["athletic"], old["skill"])          # athletic ratings fall faster
        self.assertGreater(young["per_year"], 0.0)

    def test_decline_watch_only_for_veterans_without_runway(self):
        self.assertIsNone(decline_watch_value(self.canonical, self.players["Cooper Flagg"], 0.0))
        self.assertIsNone(decline_watch_value(self.canonical, self.players["Paul George"], 5.0))
        self.assertIsNotNone(decline_watch_value(self.canonical, self.players["Paul George"], 0.0))


if __name__ == "__main__":
    unittest.main()
