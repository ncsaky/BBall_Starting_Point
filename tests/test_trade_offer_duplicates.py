"""Repeated trade pitches share one actionable inbox entry."""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data.app_actions import user_trade_offers_payload, respond_user_trade_offer_action
from nba_gm_data.save import queue_user_trade_offers
from nba_gm_data.transactions import trade_offer_fingerprint


def offer(identifier, date="2026-12-01"):
    return {"proposal": {"id": identifier, "from_team_id": "a", "to_team_id": "b",
                         "from_assets": [{"kind": "player", "id": "p"}],
                         "to_assets": [{"kind": "pick", "id": "r"}]},
            "offer_context": {"status": "pending_user_review", "created_date": date}}


class TradeOfferDuplicateTests(unittest.TestCase):
    def test_queue_merges_followups_and_retry_is_idempotent_after_reload(self):
        import json
        save = {}
        with patch("nba_gm_data.save.add_news"):
            queue_user_trade_offers(save, [offer("first"), offer("second")], "2026-12-01")
            queue_user_trade_offers(save, [offer("third")], "2026-12-03")
            save = json.loads(json.dumps(save))
            queue_user_trade_offers(save, [offer("second"), offer("third")], "2026-12-03")
        self.assertEqual(len(save["user_trade_offers"]), 1)
        self.assertEqual(save["user_trade_offers"][0]["repeat_count"], 3)
        self.assertEqual(save["user_trade_offers"][0]["repeat_dates"], ["2026-12-01", "2026-12-03"])

    def test_old_save_duplicates_are_grouped_without_mutating_save(self):
        save = {"user_trade_offers": [offer("one"), offer("two"), offer("three", "2026-12-03")]}
        before = deepcopy(save)
        with patch("nba_gm_data.app_actions.trade_presentation_context", return_value={}), \
             patch("nba_gm_data.app_actions.enhance_trade_candidate", side_effect=lambda _, row, **kw: deepcopy(row)):
            result = user_trade_offers_payload({}, Path("unused"), prepared_save=save, prepared_active={})
        self.assertEqual(result["offer_count"], 1)
        self.assertEqual(result["offers"][0]["repeat_count"], 3)
        self.assertEqual(result["offers"][0]["duplicate_offer_ids"], ["two", "three"])
        self.assertEqual(save, before)

    def test_decline_resolves_entire_group_but_allows_a_later_pitch(self):
        save = {"state": {"current_date": "2026-12-03"},
                "user_trade_offers": [offer("one"), offer("two")]}
        with patch("nba_gm_data.app_actions.load_save", return_value=save), \
             patch("nba_gm_data.app_actions.ensure_league_save_defaults", side_effect=lambda s, c: s), \
             patch("nba_gm_data.app_actions.write_save"):
            result = respond_user_trade_offer_action({}, Path("unused"), {
                "proposal_id": "one", "decision": "reject", "summary_only": True})
        self.assertEqual(result["offer_count"], 0)
        self.assertTrue(all(row["offer_context"]["status"] == "rejected_by_user" for row in save["user_trade_offers"]))
        with patch("nba_gm_data.save.add_news"):
            queue_user_trade_offers(save, [offer("later")], "2026-12-20")
        self.assertEqual(save["user_trade_offers"][-1]["offer_context"]["status"], "pending_user_review")

    def test_asset_and_transfer_order_do_not_create_a_new_trade(self):
        first = offer("one")
        first["proposal"]["from_assets"].append({"kind": "player", "id": "other"})
        second = {"proposal": {"id": "two", "transfers": [
            {"from_team_id": "b", "to_team_id": "a", "assets": first["proposal"]["to_assets"]},
            {"from_team_id": "a", "to_team_id": "b", "assets": list(reversed(first["proposal"]["from_assets"]))}]}}
        self.assertEqual(trade_offer_fingerprint(first), trade_offer_fingerprint(second))

    def test_terms_order_is_ignored_but_different_protections_are_not(self):
        first = offer("one")
        first["pick_obligation_terms"] = [{"type": "protected_pick", "pick_id": "r", "protected_through": 10},
                                          {"type": "pick_swap", "benefit": "better"}]
        second = deepcopy(first)
        second["pick_obligation_terms"].reverse()
        self.assertEqual(trade_offer_fingerprint(first), trade_offer_fingerprint(second))
        second["pick_obligation_terms"][1]["protected_through"] = 14
        self.assertNotEqual(trade_offer_fingerprint(first), trade_offer_fingerprint(second))


if __name__ == "__main__":
    unittest.main()
