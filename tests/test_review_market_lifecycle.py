import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_market_lifecycle import floor_accounting, valid_observations


class MarketLifecycleReviewTests(unittest.TestCase):
    def test_missed_rollover_excludes_all_subsequent_results(self):
        snapshots = [
            {"date": "2027-09-01", "season": "2026-27"},
            {"date": "2027-10-01", "season": "2026-27"},
            {"date": "2028-04-12", "season": "2026-27"},
            {"date": "2028-10-01", "season": "2028-29"},
        ]
        valid, invalid_at = valid_observations(snapshots)
        self.assertEqual(valid, snapshots[:1])
        self.assertEqual(invalid_at, "2027-10-01")
        valid, invalid_at = valid_observations([
            {"date": "2027-09-01", "season": "2026-27"},
            {"date": "2027-10-01", "season": "2027-28"},
        ])
        self.assertEqual(len(valid), 2)
        self.assertIsNone(invalid_at)

    def snapshot(self, stamp, values):
        return {"date": stamp, "players": [{"id": pid, "fixed24_engine": value, "rostered": True}
                                           for pid, value in values.items()]}

    def test_floor_change_separates_growth_entries_and_exits_with_different_pool_sizes(self):
        first = self.snapshot("2026-10-01", {"veteran": 60, "young": 50, "fringe": 30})
        last = self.snapshot("2027-10-01", {"veteran": 59, "young": 54, "rookie": 55, "signing": 53})
        row = floor_accounting(first, last)
        self.assertEqual(row["retained"], 2)
        self.assertEqual(row["entrants"], 2)
        self.assertEqual(row["departures"], 1)
        self.assertAlmostEqual(row["retained_player_rating_component"], .75)
        self.assertAlmostEqual(sum(row[key] for key in (
            "retained_player_rating_component", "entry_composition_component", "departure_composition_component")),
            row["mean_change"], places=3)

    def test_removing_weak_players_can_raise_floor_without_any_growth(self):
        first = self.snapshot("2026-10-01", {"a": 60, "b": 20})
        last = self.snapshot("2027-10-01", {"a": 60})
        row = floor_accounting(first, last)
        self.assertEqual(row["mean_change"], 20)
        self.assertEqual(row["retained_player_rating_component"], 0)
        self.assertEqual(row["entry_composition_component"], 0)
        self.assertEqual(row["departure_composition_component"], 20)


if __name__ == "__main__":
    unittest.main()
