"""Outcome accounting uses committed market statuses and neutral ratings."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_completed_market_health import market_summary, metrics


class CompletedMarketReviewTests(unittest.TestCase):
    def test_accepted_offer_is_a_signing_not_a_cleanup_or_missing_player(self):
        player = {"id": "premium", "overall": 85}
        opening = {"day": 1, "status": "active", "players": [player], "offers": []}
        completed = {"day": 5, "status": "completed", "players": [], "offers": [
            {"player_id": "premium", "team_id": "one", "status": "accepted", "aav_millions": 20},
            {"player_id": "premium", "team_id": "two", "status": "rejected_player_chose_other_offer", "aav_millions": 18},
        ]}
        row = market_summary([("first", opening), ("last", completed)])
        self.assertEqual(row["opening_80_plus_signed_via_offers"], 1)
        self.assertEqual(row["opening_80_plus_multiple_suitors"], 1)
        self.assertEqual(row["total_signed_offers"], 1)
        self.assertEqual(row["opening_80_plus_no_longer_free_without_signed_offer"], [])
        self.assertEqual(row["opening_80_plus_signed_at_5m_or_less"], [])

    def test_missing_final_or_no_offer_does_not_claim_a_market_signing(self):
        opening = {"day": 1, "status": "active", "players": [{"id": "premium", "overall": 85}], "offers": []}
        self.assertFalse(market_summary([("first", opening)])["complete"])
        final = {"day": 5, "status": "completed", "players": [], "offers": []}
        result = market_summary([("first", opening), ("last", final)])
        self.assertEqual(result["opening_80_plus_signed_via_offers"], 0)
        self.assertEqual(result["opening_80_plus_no_longer_free_without_signed_offer"], ["premium"])

    def test_fixed_minute_counts_do_not_use_role_dependent_display(self):
        result = metrics([{"fixed24_engine": 85, "display": 95, "age": 21}])  # display grade is now the model grade itself (no inflation)
        self.assertEqual(result["fixed24_display_at_least"]["80"], 1)
        self.assertEqual(result["fixed24_display_at_least"]["90"], 0)


if __name__ == "__main__":
    unittest.main()
