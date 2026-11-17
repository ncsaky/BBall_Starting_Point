"""Calendar advancement must not depend on how a user divides the interval."""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data import app_actions as aa, save as sv
from nba_gm_data.pick_presentation import pick_presentation, swap_presentation, nested_entitlements


class SimulationCalendarTests(unittest.TestCase):
    def fixture(self, current="2026-11-28"):
        return {"version": sv.SAVE_VERSION, "meta": {"season": "2026-27", "seed": 17},
                "state": {"current_date": current, "phase": "regular_season"},
                "schedule_state": {"simulated_game_ids": []}}

    def advance_day(self, root, canonical, path, save, current, target, seed):
        roster = save.setdefault("roster", {"p": "old"})
        save.setdefault("games", []).append({"date": target, "team": roster["p"], "seed": seed})
        if target.endswith("-30"):
            roster["p"] = "new"
            save.setdefault("trades", []).append(target)
        if current[:7] != target[:7]:
            save.setdefault("growth", []).append(target)
        sv.set_save_date_phase(save, target)
        save["schedule_state"]["simulated_game_ids"].append(target)
        return {"ai_applied_count": int(target.endswith("-30")), "inseason_free_agent_signings": 0}

    def test_partitioning_preserves_causal_order_seed_and_month_boundary(self):
        daily = self.fixture()
        bulk = deepcopy(daily)
        with patch.object(sv, "advance_save_day", side_effect=self.advance_day):
            for target in ["2026-11-29", "2026-11-30", "2026-12-01", "2026-12-02"]:
                sv.advance_save(Path("."), {}, Path("unused.json"), to_date=target, prepared_save=daily, persist=False)
            result = sv.advance_save(Path("."), {}, Path("unused.json"), to_date="2026-12-02", prepared_save=bulk, persist=False)
        self.assertEqual(daily, bulk)
        self.assertEqual(bulk["games"][1]["team"], "old")
        self.assertEqual(bulk["games"][2]["team"], "new")
        self.assertEqual(bulk["growth"], ["2026-12-01"])
        self.assertEqual(result["from_date"], "2026-11-28")
        self.assertEqual(result["games_simulated"], 4)
        self.assertEqual(result["ai_applied_count"], 1)

    def test_same_day_is_a_true_noop_and_long_advance_commits_once(self):
        save = self.fixture()
        with patch.object(sv, "advance_save_day", side_effect=self.advance_day) as day, patch.object(sv, "write_save") as write:
            sv.advance_save(".", {}, "unused.json", to_date="2026-11-28", prepared_save=save)
            day.assert_not_called()
            write.assert_not_called()
            sv.advance_save(".", {}, "unused.json", to_date="2026-12-02", prepared_save=save)
            self.assertEqual(day.call_count, 4)
            write.assert_called_once()

    def test_next_event_runs_intervening_days_and_phase_gate_precedes_mutation(self):
        save = self.fixture()
        with patch.object(sv, "advance_save_day", side_effect=self.advance_day) as day, patch.object(sv, "next_event_date", return_value="2026-11-30"):
            sv.advance_save(".", {}, "unused.json", next_event=True, prepared_save=save, persist=False)
            self.assertEqual(day.call_count, 2)
        draft = self.fixture("2027-06-26")
        draft["state"]["phase"] = "draft"
        draft["draft_state"] = {"status": "in_progress"}
        original = deepcopy(draft)
        with patch.object(sv, "advance_save_day") as day:
            with self.assertRaisesRegex(ValueError, "draft is active"):
                sv.advance_save(".", {}, "unused.json", to_date="2027-06-27", prepared_save=draft, persist=False)
            day.assert_not_called()
        self.assertEqual(draft, original)

    def test_history_does_not_starve_due_actions_or_run_future_actions(self):
        save = self.fixture()
        save["pending_ai_actions"] = [
            {"id": f"old-{i}", "status": "executed", "date": "2026-11-01"} for i in range(40)
        ] + [{"id": "due", "status": "recommendation_pending_review", "date": "2026-11-28"},
             {"id": "future", "status": "recommendation_pending_review", "date": "2026-11-29"}]
        first = sv.process_ai_actions_in_memory({}, save, execute=True, limit=1, prepared_active={})
        self.assertEqual([item["id"] for item in first["processed"]], ["due"])
        second = sv.process_ai_actions_in_memory({}, save, execute=True, limit=1, prepared_active={})
        self.assertEqual(second["processed_count"], 0)
        save["state"]["current_date"] = "2026-11-29"
        third = sv.process_ai_actions_in_memory({}, save, execute=True, limit=1, prepared_active={})
        self.assertEqual([item["id"] for item in third["processed"]], ["future"])

    def test_core_drains_due_backlog_without_archived_prefix_or_duplicate_draft_attention(self):
        save = self.fixture()
        save["pending_ai_actions"] = [{"id": str(i), "status": "pending", "date": "2026-11-28"} for i in range(35)]
        save["pending_ai_actions"].append({"id": "draft", "status": "draft_attention_required", "date": "2026-06-25"})
        result = sv.process_ai_actions_in_memory({}, save, execute=True, limit=len(save["pending_ai_actions"]), prepared_active={})
        self.assertEqual(result["processed_count"], 35)
        self.assertEqual(sv.process_ai_actions_in_memory({}, save, execute=True, limit=50, prepared_active={})["processed_count"], 0)

    def test_legacy_backlog_executes_today_without_rewriting_its_scheduled_date(self):
        save = self.fixture()
        proposal = {"proposal": {"id": "overdue", "from_assets": [{"kind": "player", "id": "p"}], "to_assets": []},
                    "accepted_by_all": True, "legality": {"status": "legal"}}
        save["pending_ai_actions"] = [{"id": "old", "date": "2026-10-01", "status": "pending",
                                       "action_type": "trade_recommendations", "payload": {"proposals": [proposal]}}]
        with patch("nba_gm_data.transactions.apply_trade_to_state", return_value={"status": "applied"}) as apply:
            result = sv.process_ai_actions_in_memory({}, save, execute=True, prepared_active={})
        self.assertEqual(apply.call_args.kwargs["date"], "2026-11-28")
        self.assertEqual(save["pending_ai_actions"][0]["date"], "2026-10-01")
        self.assertEqual(result["processed"][0]["applied_candidate_count"], 1)

    def test_checkpoint_hint_does_not_change_calendar_or_rewrite_same_date(self):
        save = self.fixture()
        with patch.object(aa, "advance_save", return_value={"status": "advanced"}) as core:
            aa.advance_with_checkpoints(Path("."), {}, Path("unused.json"), "2026-12-02", 17, 31, prepared_save=save)
        core.assert_called_once_with(Path("."), {}, Path("unused.json"), to_date="2026-12-02", seed=17, prepared_save=save, pause_at_champion=True)

    def test_app_uses_saved_seed_unless_explicitly_overridden(self):
        for saved_seed, supplied, expected in [(17, None, 17), (0, None, 0), (None, None, 1), (17, 0, 0), (17, 29, 29)]:
            with self.subTest(saved_seed=saved_seed, seed=supplied):
                save = self.fixture()
                save["meta"]["seed"] = saved_seed
                payload = {"to_date": "2026-11-29"}
                if supplied is not None:
                    payload["seed"] = supplied
                with patch.object(Path, "exists", return_value=True), \
                     patch.object(aa, "normalized_read_save", return_value=save), \
                     patch.object(aa, "advance_save", return_value={"status": "advanced"}) as core, \
                     patch.object(aa, "dashboard_snapshot_payload", return_value={"home": {}}):
                    aa.advance_action(Path("."), {}, Path("unused.json"), payload)
                self.assertEqual(core.call_args.kwargs["seed"], expected)

    def test_core_preserves_saved_zero_seed(self):
        save = self.fixture()
        save["meta"]["seed"] = 0
        with patch.object(sv, "advance_save_day", side_effect=self.advance_day):
            sv.advance_save(".", {}, "unused.json", to_date="2026-11-30", prepared_save=save, persist=False)
        self.assertEqual([game["seed"] for game in save["games"]], [0, 0])

    def test_app_deadline_stop_and_confirmation_survive_long_targets(self):
        save = self.fixture("2027-01-31")
        with patch.object(Path, "exists", return_value=True), \
             patch.object(aa, "normalized_read_save", return_value=save), \
             patch.object(aa, "advance_save", return_value={"status": "advanced"}) as core, \
             patch.object(aa, "dashboard_snapshot_payload", return_value={"home": {}}):
            stopped = aa.advance_action(Path("."), {}, Path("unused.json"), {"to_date": "2027-02-07"})
        self.assertEqual(stopped["status"], "trade_deadline")
        self.assertEqual(core.call_args.kwargs["to_date"], "2027-02-05")
        save["state"]["current_date"] = "2027-02-05"
        with patch.object(Path, "exists", return_value=True), \
             patch.object(aa, "normalized_read_save", return_value=save), \
             patch.object(aa, "advance_save", return_value={"status": "advanced"}) as core, \
             patch.object(aa, "dashboard_snapshot_payload", return_value={"home": {}}):
            aa.advance_action(Path("."), {}, Path("unused.json"), {"to_date": "2027-02-07"})
            core.assert_not_called()
            resumed = aa.advance_action(Path("."), {}, Path("unused.json"),
                                        {"to_date": "2027-02-07", "trade_deadline_confirmed": "2027-02-05"})
        self.assertEqual(resumed["status"], "advanced")
        self.assertEqual(core.call_args.kwargs["to_date"], "2027-02-07")


class PickPresentationLookupTests(unittest.TestCase):
    def test_standalone_swap_does_not_scan_irrelevant_dependencies(self):
        canonical = {"draft_picks": [{"id": "a"}, {"id": "b"}], "pick_obligations": [
            {"id": "swap", "type": "pick_swap", "team_a_pick_id": "a", "team_b_pick_id": "b"}]}
        with patch("nba_gm_data.pick_presentation._dependencies", side_effect=AssertionError("Unneeded scan")):
            self.assertEqual(nested_entitlements(canonical), {})

    def test_explicit_chain_keeps_authoritative_inputs_without_dependency_scan(self):
        canonical = {"teams": [{"id": pid, "abbrev": pid.upper()} for pid in "abc"],
                     "draft_picks": [{"id": pid, "season": "2028", "round": 1,
                                      "original_team_id": pid, "current_owner_team_id": pid} for pid in "abc"],
                     "pick_obligations": [
                         {"id": "ab", "type": "pick_swap", "season": "2028", "round": 1,
                          "team_a_pick_id": "a", "team_b_pick_id": "b", "nested_anchor_pick_id": "a",
                          "nested_input": {"pick_id": "a"}, "nested_other_pick_id": "b",
                          "current_rights_holder_team_id": "a"},
                         {"id": "ac", "type": "pick_swap", "season": "2028", "round": 1,
                          "team_a_pick_id": "a", "team_b_pick_id": "c", "nested_anchor_pick_id": "a",
                          "nested_input": {"obligation_id": "ab"}, "nested_other_pick_id": "c",
                          "current_rights_holder_team_id": "a"}]}
        original = deepcopy(canonical)
        with patch("nba_gm_data.pick_presentation._dependencies", side_effect=AssertionError("Explicit inputs are authoritative")):
            result = nested_entitlements(canonical)
        self.assertEqual(result["a"]["underlying_pick_ids"], ["a", "b", "c"])
        self.assertEqual(result["a"]["root_obligation_id"], "ac")
        self.assertEqual(canonical, original)

    def test_presentation_tracks_changed_ownership_terms_and_replacement_lists(self):
        canonical = {"teams": [{"id": "a", "abbrev": "AAA"}, {"id": "b", "abbrev": "BBB"}, {"id": "c", "abbrev": "CCC"}],
                     "draft_picks": [{"id": "pa", "season": "2027", "round": 1, "original_team_id": "a", "current_owner_team_id": "a"},
                                     {"id": "pb", "season": "2027", "round": 1, "original_team_id": "b", "current_owner_team_id": "b"}],
                     "pick_obligations": [{"id": "swap", "type": "pick_swap", "season": "2027", "round": 1,
                                          "status": "active", "team_a_pick_id": "pa", "team_b_pick_id": "pb",
                                          "current_rights_holder_team_id": "a"}]}
        before = deepcopy(canonical)
        first = swap_presentation(canonical, canonical["pick_obligations"][0])
        self.assertEqual(canonical, before)
        self.assertEqual(first["rights_holder_team_id"], "a")
        self.assertIn("AAA receives", first["label"])
        canonical["pick_obligations"][0]["current_rights_holder_team_id"] = "c"
        second = swap_presentation(canonical, canonical["pick_obligations"][0])
        self.assertEqual(second["rights_holder_team_id"], "c")
        self.assertIn("CCC receives", second["label"])
        replacement = {**canonical, "draft_picks": [dict(pick) for pick in canonical["draft_picks"]]}
        replacement["draft_picks"][0]["original_team_id"] = "c"
        self.assertIn("CCC", pick_presentation(replacement, replacement["draft_picks"][0])["team_abbrevs"])
        self.assertNotEqual(replacement["draft_picks"], canonical["draft_picks"])
        canonical["pick_obligations"][0]["status"] = "resolved"
        self.assertIsNone(pick_presentation(canonical, canonical["draft_picks"][0]))


if __name__ == "__main__":
    unittest.main()
