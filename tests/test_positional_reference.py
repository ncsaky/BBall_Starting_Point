import unittest
from pathlib import Path

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import display_rating_averages, display_rating_averages_by_position, positional_rating_reference

ROOT = Path(__file__).resolve().parents[1]


class PositionalReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_app_canonical(ROOT)

    def test_positions_differ_where_basketball_says_they_should(self):
        by_position = display_rating_averages_by_position(self.canonical)
        self.assertEqual(set(by_position), {"PG", "SG", "SF", "PF", "C"})
        self.assertGreater(by_position["C"]["rim_deterrence"], by_position["PG"]["rim_deterrence"])
        self.assertGreater(by_position["PG"]["passing"], by_position["C"]["passing"])

    def test_multi_position_is_the_mean_of_listed_positions(self):
        by_position = display_rating_averages_by_position(self.canonical)
        averages, label = positional_rating_reference(self.canonical, "SF/PF")
        self.assertEqual(label, "SF/PF average")
        expected = round((by_position["SF"]["shooting"] + by_position["PF"]["shooting"]) / 2, 1)
        self.assertAlmostEqual(averages["shooting"], expected, places=1)

    def test_unknown_position_falls_back_to_league_mean(self):
        averages, label = positional_rating_reference(self.canonical, "")
        self.assertEqual(label, "League average")
        self.assertEqual(averages, display_rating_averages(self.canonical))


if __name__ == "__main__":
    unittest.main()
