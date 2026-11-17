"""Retirement batches share effective ages, contract policy, and one report."""
from contextlib import ExitStack
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from nba_gm_data import save as sv


class RetirementTests(unittest.TestCase):
    def fixture(self, age=34):
        saved = {"meta": {"season": "2026-27"}, "state": {"current_date": "2027-09-30"},
                 "roster_overrides": {}, "retired_player_ids": [], "free_agent_player_ids": []}
        active = {"players": [{"id": pid, "name": pid, "age": age, "team_id": "team_ai",
                                "position": "SG", "minutes_projection": 24} for pid in ("A", "B")],
                  "contracts": []}
        sv.apply_effective_player_ages(active, saved)
        return active, saved

    def context(self, active):
        stack = ExitStack()

        def view(canonical, saved):
            result = deepcopy(active)
            result["players"] = [p for p in result["players"] if p["id"] not in saved["retired_player_ids"]]
            return result

        stack.enter_context(patch.object(sv, "canonical_with_save", side_effect=view))
        stack.enter_context(patch.object(sv, "strategic_free_agent_signings", return_value=set()))
        stack.enter_context(patch.object(sv, "auto_fill_rosters", return_value=set()))
        stack.enter_context(patch.object(sv, "archive_excess_free_agents", return_value=[]))
        return stack

    def test_rollover_does_not_advance_effective_age_a_second_time(self):
        active, saved = self.fixture()
        self.assertEqual(active["players"][0]["age"], 35)
        seed = next(s for s in range(1000) if sv.should_retire(active["players"][0], 36, s, "2027-28"))
        actual = sv.should_retire
        with self.context(active), patch.object(sv, "should_retire", wraps=actual) as predicate:
            sv.prepare_offseason_retirements({}, saved, "2026-27", "2027-28", seed)
            sv.apply_offseason_roster_transitions({}, saved, "2026-27", "2027-28", seed)
        self.assertEqual(saved["retired_player_ids"], [])
        self.assertEqual([call.args[1] for call in predicate.call_args_list], [35] * 4)

    def test_batches_merge_and_serialized_repeats_do_not_duplicate_retirements(self):
        active, saved = self.fixture(35)
        with self.context(active), patch.object(sv, "should_retire", side_effect=lambda p, *args: p["id"] == "A"):
            self.assertEqual(sv.prepare_offseason_retirements({}, saved, "2026-27", "2027-28", 17), 1)
        saved = json.loads(json.dumps(saved))
        with self.context(active), patch.object(sv, "should_retire", return_value=True):
            sv.apply_offseason_roster_transitions({}, saved, "2026-27", "2027-28", 17)
            before = deepcopy(saved)
            sv.prepare_offseason_retirements({}, saved, "2026-27", "2027-28", 17)
            sv.apply_offseason_roster_transitions({}, saved, "2026-27", "2027-28", 17)
        self.assertEqual(saved, before)
        self.assertEqual(saved["retired_player_ids"], ["A", "B"])
        self.assertEqual(len(saved["retirement_reports"]), 1)
        rows = saved["retirement_reports"][0]["retirements"]
        self.assertEqual([r["player_id"] for r in rows], ["A", "B"])
        self.assertEqual([r["age"] for r in rows], [36, 36])

    def test_report_merge_preserves_first_retirement_age_and_separates_seasons(self):
        active, saved = self.fixture(35)
        players = {p["id"]: p for p in active["players"]}
        sv.record_offseason_retirements(saved, "2026-27", "2027-28", players, ["A"])
        players["A"]["display_age"] = 37
        sv.record_offseason_retirements(saved, "2026-27", "2027-28", players, ["B", "A", "B"])
        sv.record_offseason_retirements(saved, "2027-28", "2028-29", players, ["A"])
        reports = {r["season"]: r for r in saved["retirement_reports"]}
        self.assertEqual(len(reports), 2)
        self.assertEqual(len(reports["2026-27"]["retirements"]), 2)
        self.assertEqual(reports["2026-27"]["retirements"][0]["age"], 36)
        self.assertEqual(reports["2027-28"]["retirements"][0]["age"], 37)

    def test_imported_and_save_signed_future_contracts_get_identical_protection(self):
        for status in ("verified_public_salary_table", "reported_total_gameplay_annual_estimate", "save_state_contract_override"):
            with self.subTest(status=status):
                active, saved = self.fixture(35)
                active["contracts"] = [{"player_id": p["id"], "status": status,
                                         "seasons": [{"season": "2027-28", "salary": 1_000_000,
                                                      "guarantee_status": "unknown_from_salary_table"}]} for p in active["players"]]
                with self.context(active), patch.object(sv, "should_retire", return_value=True):
                    sv.prepare_offseason_retirements({}, saved, "2026-27", "2027-28", 17)
                    sv.apply_offseason_roster_transitions({}, saved, "2026-27", "2027-28", 17)
                self.assertEqual(saved["retired_player_ids"], [])

    def test_expired_or_zero_salary_is_not_retirement_protection(self):
        for rows in ([{"season": "2026-27", "salary": 1_000_000}],
                     [{"season": "2027-28", "salary": 0}], [{"season": "2027-28", "salary": None}]):
            self.assertFalse(sv.contract_has_salary_in_or_after({"seasons": rows}, "2027-28"))
        self.assertTrue(sv.contract_has_salary_in_or_after({"seasons": [{"season": "2028-29", "salary": "1000000"}]}, "2027-28"))

    def test_age_42_exception_is_preserved(self):
        active, saved = self.fixture(41)
        active["contracts"] = [{"player_id": p["id"], "status": "save_state_contract_override",
                                 "seasons": [{"season": "2027-28", "salary": 1_000_000}]} for p in active["players"]]
        with self.context(active), patch.object(sv, "should_retire", return_value=True):
            sv.prepare_offseason_retirements({}, saved, "2026-27", "2027-28", 17)
        self.assertEqual(saved["retired_player_ids"], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
