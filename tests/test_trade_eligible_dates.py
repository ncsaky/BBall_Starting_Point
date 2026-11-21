import unittest

from nba_gm_data.transactions import recently_signed_player_ids


def signing_log(player_id: str, day: str) -> dict:
    return {"transaction_type": "free_agent_signing", "status": "applied", "date": day, "player_id": player_id,
            "player_ids": [player_id]}


class TradeEligibleDateTests(unittest.TestCase):
    """FA-REAL hook-up: a contract's recorded trade-eligible date decides when a newly signed player can be traded."""

    def test_recorded_date_replaces_the_december_first_rule(self):
        view = {
            "contracts": [{"player_id": "bird_raise", "trade_eligible_date": "2027-01-15"}],
            "transaction_logs": [signing_log("bird_raise", "2026-07-06")],
        }
        # The old rule unlocked on December 1; the recorded date (a big Bird raise over the cap) holds until January 15.
        self.assertIn("bird_raise", recently_signed_player_ids(view, "2026-12-20"))
        self.assertNotIn("bird_raise", recently_signed_player_ids(view, "2027-01-15"))

    def test_save_overrides_are_read_too(self):
        save = {"contract_overrides": {"p": {"trade_eligible_date": "2026-12-15"}}, "transaction_logs": []}
        self.assertIn("p", recently_signed_player_ids(save, "2026-12-14"))
        self.assertNotIn("p", recently_signed_player_ids(save, "2026-12-15"))

    def test_signings_without_a_recorded_date_keep_the_older_rule(self):
        view = {"contracts": [], "transaction_logs": [signing_log("old", "2026-07-10")]}
        self.assertIn("old", recently_signed_player_ids(view, "2026-11-30"))
        self.assertNotIn("old", recently_signed_player_ids(view, "2026-12-01"))


if __name__ == "__main__":
    unittest.main()
