from copy import deepcopy
import unittest

from nba_gm_data.app_actions import draft_action_rejection
from nba_gm_data.play import apply_saved_draft_order_to_draft, sync_live_draft_state_to_saved_order


class DraftSlotAlignmentTests(unittest.TestCase):
    def fixture(self, consumed=0):
        teams = [{"id": "team_gsw", "abbrev": "GSW", "name": "Golden State Warriors"},
                 {"id": "team_bos", "abbrev": "BOS", "name": "Boston Celtics"}]
        order = [{"id": f"pick_{slot}", "pick_id": f"pick_{slot}", "overall_pick": slot,
                  "current_owner_team_id": "team_bos", "original_team_id": "team_bos", "round": 1}
                 for slot in (1, 3, 4)]
        pending = [{"id": f"entry_{index}", "selection": {
            "id": f"selection_{index}", "draft_year": "2029", "overall_pick": slot,
            "pick_id": f"pick_{slot}", "prospect_id": f"prospect_{index}", "team_id": "team_bos"},
            "pick": {"id": f"pick_{slot}"}, "prospect": {"id": f"prospect_{index}"}}
                   for index, slot in enumerate((1, 2, 4))]
        saved = {"draft_orders": {"2029": {"draft_order": order}},
                 "draft_state": {"year": "2029", "status": "in_progress", "current_index": consumed,
                                 "draft": {"pending_draft_selections": pending}}}
        return {"teams": teams}, saved

    def test_initial_alignment_preserves_every_prospect_and_uses_actual_gap(self):
        canonical, saved = self.fixture()
        draft = saved["draft_state"]["draft"]
        identities = [r["selection"]["prospect_id"] for r in draft["pending_draft_selections"]]
        apply_saved_draft_order_to_draft(canonical, saved, "2029", draft)
        queue = draft["pending_draft_selections"]
        self.assertEqual([r["selection"]["overall_pick"] for r in queue], [1, 3, 4])
        self.assertEqual([r["selection"]["pick_id"] for r in queue], ["pick_1", "pick_3", "pick_4"])
        self.assertEqual([r["selection"]["prospect_id"] for r in queue], identities)

    def test_stalled_suffix_repairs_without_mutating_consumed_prefix(self):
        canonical, saved = self.fixture(consumed=1)
        queue = saved["draft_state"]["draft"]["pending_draft_selections"]
        queue[1]["selection"]["pick_id"] = "pick_1"
        queue[1]["pick"]["id"] = "pick_1"
        saved["draft_pick_overrides"] = {"pick_1": "used_draft_pick"}
        prefix = deepcopy(queue[0])
        untouched = deepcopy(saved)
        self.assertIsNone(draft_action_rejection(canonical, saved, "GSW", "2029"))
        self.assertEqual(saved, untouched)
        self.assertTrue(sync_live_draft_state_to_saved_order(canonical, saved, "2029"))
        self.assertEqual(queue[0], prefix)
        self.assertEqual(queue[1]["selection"]["pick_id"], "pick_3")
        self.assertEqual(queue[1]["selection"]["overall_pick"], 3)
        self.assertFalse(sync_live_draft_state_to_saved_order(canonical, saved, "2029"))

    def test_conflicting_consumed_prefix_is_rejected_without_rewriting_history(self):
        canonical, saved = self.fixture(consumed=2)
        before = deepcopy(saved)
        with self.assertRaisesRegex(ValueError, "already applied picks"):
            sync_live_draft_state_to_saved_order(canonical, saved, "2029")
        self.assertEqual(saved, before)

    def test_mismatched_queue_length_cannot_restore_forfeited_pick_or_drop_a_prospect(self):
        canonical, saved = self.fixture()
        saved["draft_state"]["draft"]["pending_draft_selections"].append({"selection": {"overall_pick": 5}})
        before = deepcopy(saved)
        with self.assertRaisesRegex(ValueError, "different lengths"):
            sync_live_draft_state_to_saved_order(canonical, saved, "2029")
        self.assertEqual(saved, before)
