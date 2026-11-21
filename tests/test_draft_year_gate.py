from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from league_health_audit import career_action
from nba_gm_data import save as engine
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical

ROOT = Path(__file__).resolve().parents[1]


class DraftYearGateTests(unittest.TestCase):
    def fixture(self):
        return {"meta": {"season": "2028-29", "seed": 17},
                # FA-REAL slice 2: the 2029 draft is June 26-27; stop 1 resumes June 28.
                "state": {"current_date": "2029-06-26", "phase": "draft"},
                "draft_state": {"year": "2027", "completed_year": "2028", "status": "completed"},
                "pending_draft_selections": []}

    def test_prior_year_completion_cannot_pass_this_year_gate_or_mutate_a_day(self):
        saved = self.fixture()
        before = deepcopy(saved)
        with patch.object(engine, "advance_save_day") as day:
            with self.assertRaisesRegex(ValueError, "draft is active"):
                engine.advance_save(ROOT, {}, "unused.json", to_date="2029-06-28", prepared_save=saved, persist=False)
            day.assert_not_called()
        self.assertEqual(saved, before)

    def test_current_year_completion_remains_valid_and_pending_picks_still_block(self):
        saved = self.fixture()
        saved["draft_state"]["completed_year"] = "2029"
        engine.guard_required_phase_actions(saved, "2029-06-26", "2029-06-28")
        saved["pending_draft_selections"] = [{"id": "pending"}]
        with self.assertRaisesRegex(ValueError, "draft is active"):
            engine.guard_required_phase_actions(saved, "2029-06-26", "2029-06-28")

    def test_runner_selects_new_draft_not_rollover_for_stale_completed_state(self):
        saved = self.fixture()
        self.assertEqual(career_action(saved, 31, "GSW"), ("draft_sim_all", {"year": "2029", "team": "GSW"}))
        saved["draft_state"] = {"year": "2029", "status": "completed"}
        self.assertEqual(career_action(saved, 31, "GSW"), ("advance_save", {"to_date": "2029-06-28"}))

    def test_legacy_auto_draft_completion_records_its_year_on_repeat(self):
        saved = {"incoming_rookies": [{"draft_year": "2029", "roster_status": "signed_rookie"}],
                 "draft_state": {"year": "2027", "status": "completed"}}
        engine.ensure_draft_processed({}, saved, "2029", 17)
        self.assertTrue(engine.draft_completed_for_year(saved, "2029"))
        self.assertFalse(engine.draft_completed_for_year(saved, "2030"))

    def test_real_app_draft_handles_later_year_and_all_rookies_get_first_summer_month(self):
        canonical = load_app_canonical(ROOT)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "draft.json"
            saved = engine.create_league_save(ROOT, canonical, "GSW", path, seed=17)
            # A focused phase fixture, not a claim that three seasons were played.
            saved["meta"]["season"] = "2028-29"
            engine.set_save_date_phase(saved, "2029-06-26")
            saved["lifecycle_state"] = {"through_date": "2029-06-26", "health_game_ids": []}
            saved["draft_state"] = {"year": "2027", "status": "completed", "current_index": 60}
            engine.write_save(path, saved)
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "draft is active"):
                dispatch_app_action("advance_save", {"save_path": str(path), "to_date": "2029-06-28", "seed": 17},
                                    root=ROOT, save_dir=Path(directory), canonical=canonical)
            self.assertEqual(path.read_bytes(), original)
            engine.run_draft_lottery(canonical, path, year="2029", seed=913)
            result = dispatch_app_action("draft_sim_all", {"save_path": str(path), "year": "2029", "team": "GSW", "seed": 17},
                                         root=ROOT, save_dir=Path(directory), canonical=canonical)
            self.assertEqual(result["status"], "simulated")
            actual = engine.load_save(path)
            cohort = {r["player_id"] for r in actual["incoming_rookies"] if str(r["draft_year"]) == "2029"}
            selections = actual["draft_state"]["draft"]["selections"]
            self.assertEqual(len(cohort), len(selections))
            self.assertGreater(len(cohort), 50)
            self.assertEqual({r["overall_pick"] for r in actual["incoming_rookies"] if r["draft_year"] == "2029"},
                             {r["overall_pick"] for r in actual["draft_orders"]["2029"]["draft_order"]})
            forfeited = {p["id"] for p in canonical["draft_picks"]
                         if str(p["season"]) == "2029" and p.get("status") == "forfeited"}
            self.assertFalse(forfeited.intersection(r["pick_id"] for r in selections))
            self.assertTrue(engine.draft_completed_for_year(actual, "2029"))
            engine.advance_lifecycle_to(canonical, actual, "2029-07-01", 17, ROOT)
            july = [r for r in actual["development_events"] if r["month"] == "2029-07" and r["player_id"] in cohort]
            self.assertEqual(len(july), len(cohort))
            self.assertEqual({r["player_id"] for r in july}, cohort)
            before = deepcopy(actual)
            engine.advance_lifecycle_to(canonical, actual, "2029-07-01", 17, ROOT)
            self.assertEqual(actual, before)
