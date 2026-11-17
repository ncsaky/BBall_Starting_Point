"""AI extension decisions retain stable identity when generated names repeat."""
from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch

from nba_gm_data import contract_ai, save as sv


class AIExtensionIdentityTests(unittest.TestCase):
    def fixture(self, other_team="team_b", other_name="Andre Bennett"):
        players = [
            {"id": "rookie_2029_bennett", "name": other_name,
             "normalized_name": other_name.lower(), "team_id": other_team,
             "minutes_projection": 36, "age": 26},
            {"id": "rookie_2032_bennett", "name": "Andre Bennett",
             "normalized_name": "andre bennett", "team_id": "team_a",
             "minutes_projection": 28, "age": 23},
        ]
        candidates = [{"player_id": player["id"], "team_id": player["team_id"],
                       "eligible": True, "manual_review_required": False}
                      for player in players]
        canonical = {"players": players, "teams": [
            {"id": "team_a", "abbrev": "AAA", "name": "Team A"},
            {"id": "team_b", "abbrev": "BBB", "name": "Team B"},
        ], "extension_candidates": candidates}
        saved = {"meta": {"season": "2035-36", "user_team_id": "human"},
                 "ai_extension_volume": {"2035-36": {"rookie_scale": 0, "veteran": 0}}}
        return canonical, saved, candidates[1]

    def check_identity(self, other_team="team_b", other_name="Andre Bennett"):
        canonical, saved, candidate = self.fixture(other_team, other_name)
        original = deepcopy(canonical)
        negotiated = []

        def negotiate(context, player, team, *args):
            negotiated.append((player["id"], team["id"]))
            return {"accepted": True, "negotiation": {}, "decision": {
                "accepted_offer": {"annual_salary": 15_000_000, "years": 3,
                                   "team_id": team["id"], "start_season": "2036-37"}}}

        with ExitStack() as stack:
            for name in ("with_extension_context", "with_contract_context"):
                stack.enter_context(patch.object(contract_ai, name, side_effect=lambda context, *a: context))
            stack.enter_context(patch.object(contract_ai, "extension_candidates_report", return_value={"candidates": [candidate]}))
            stack.enter_context(patch.object(contract_ai, "negotiate_contract", side_effect=negotiate))
            stack.enter_context(patch.object(contract_ai, "merge_extension_offer_with_existing_contract", side_effect=lambda offer, _: offer))
            for name, value in (("ai_extension_priority", 90), ("ai_extension_due_date", "2035-10-01"),
                                ("ai_extension_team_pass_outlook", None), ("extension_offer_fits_hard_cap", True)):
                stack.enter_context(patch.object(sv, name, return_value=value))
            stack.enter_context(patch.object(sv, "ai_adjust_extension_offer_for_current_season", side_effect=lambda s, c, p, offer, priority: offer))
            stack.enter_context(patch.object(sv, "add_news"))
            stack.enter_context(patch.object(sv, "add_league_event"))
            result = sv.process_ai_extensions(canonical, saved, "2035-10-02", 17, prepared_active=True)
            self.assertEqual(result["applied_count"], 1)
            self.assertEqual(negotiated, [(candidate["player_id"], "team_a")])
            self.assertEqual(set(saved["contract_overrides"]), {candidate["player_id"]})
            self.assertEqual(saved["transaction_logs"][0]["assets"]["player_id"], candidate["player_id"])
            repeated = sv.process_ai_extensions(canonical, saved, "2035-10-02", 17, prepared_active=True)
            self.assertEqual(repeated["applied_count"], 0)
            self.assertEqual(len(negotiated), 1)
            self.assertEqual(len(saved["transaction_logs"]), 1)
        self.assertEqual(canonical, original)

    def test_same_name_on_different_teams_cannot_abort_simulation(self):
        self.check_identity()

    def test_same_name_on_same_team_cannot_negotiate_the_other_contract(self):
        self.check_identity(other_team="team_a")

    def test_longer_name_match_cannot_steal_the_extension(self):
        self.check_identity(other_name="Andre Bennett Jr.")


if __name__ == "__main__":
    unittest.main()
