"""Draft fixes (2026-11-17, revised by the draft-boards work 2026-11-19): public board ranks, deterministic GM picks,
trades re-choose."""
import unittest
from copy import deepcopy
from pathlib import Path

from nba_gm_data import draft as D
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.play import rechoose_pending_draft_pick

ROOT = Path(__file__).resolve().parents[1]


class DraftFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = D.with_draft_context(load_app_canonical(ROOT))

    def test_generated_classes_are_ranked_by_public_grade(self):
        for year in ("2028", "2030"):
            ps = sorted(D.generated_class_for_context(self.canonical, year)["draft_prospects"], key=lambda p: p["rank"])
            grades = [D.generated_bpa_grade(p) for p in ps]
            self.assertEqual(grades, sorted(grades, reverse=True), year)
            self.assertEqual([p["rank"] for p in ps], list(range(1, len(ps) + 1)))
        stored = sorted([p for p in self.canonical["draft_prospects"] if str(p.get("draft_year")) == "2027"], key=lambda p: p["rank"])
        grades = [D.generated_bpa_grade(p) for p in stored]
        self.assertEqual(grades, sorted(grades, reverse=True))

    def test_consensus_tier_comes_from_rank_not_names(self):
        self.assertEqual(D.prospect_priority_tier({"name": "Anyone", "rank": 2}), 1)
        self.assertEqual(D.prospect_priority_tier({"name": "AJ Dybantsa", "rank": 9}), 3)
        self.assertEqual(D.prospect_priority_tier({"rank": 5}), 2)

    def test_gm_pick_has_no_dice(self):
        # The draft seed no longer enters the choice: the same team, slot and pool give the same prospect.
        team = self.canonical["teams"][4]["id"]
        pool = [p for p in self.canonical["draft_prospects"] if str(p.get("draft_year")) == "2027"]
        picks = {D.preferred_prospect_for_pick(self.canonical, "2027", team, 7, pool, seed)["id"] for seed in (1, 2, 3, 99)}
        self.assertEqual(len(picks), 1)

    def test_team_that_acquires_a_pick_chooses_for_itself(self):
        result = D.simulate_draft(self.canonical, "2027", seed=5)
        pending = deepcopy(result["pending_draft_selections"])
        before = sorted(p["prospect"]["id"] for p in pending)
        original_team = pending[0]["selection"]["team_id"]
        state = {"year": "2027", "current_index": 0, "draft": {"seed": 5}}
        candidates = [deepcopy(p["prospect"]) for p in pending]
        # A buyer whose GM would take someone else at this slot.
        buyer, expected = next((t["id"], choice) for t in self.canonical["teams"] if t["id"] != original_team
                               for choice in [D.preferred_prospect_for_pick(self.canonical, "2027", t["id"], 1, candidates, 5)]
                               if choice["id"] != pending[0]["prospect"]["id"])
        pending[0]["selection"]["team_id"] = buyer
        rechoose_pending_draft_pick(self.canonical, state, pending, 0)
        self.assertEqual(pending[0]["prospect"]["id"], expected["id"])
        self.assertEqual(pending[0]["selection"]["prospect_id"], expected["id"])
        self.assertEqual(sorted(p["prospect"]["id"] for p in pending), before)   # still one prospect per slot


if __name__ == "__main__":
    unittest.main()
