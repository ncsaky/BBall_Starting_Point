"""SUMMER-EXTENSIONS: AI extension passes run on their summer dates while the game jumps from free agency to camp."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from nba_gm_data import save as sv


class SummerExtensionPassTests(unittest.TestCase):
    def run_passes(self, save, through_date, seed=17):
        calls = []

        def lifecycle(canonical, saved, target, seed, root=None, **kwargs):
            if target > saved["state"]["current_date"]:
                saved["state"]["current_date"] = target

        def extensions(canonical, saved, through, seed, **kwargs):
            calls.append(through)
            return {"applied_count": 2, "refusal_count": 1}

        with patch.object(sv, "advance_lifecycle_to", side_effect=lifecycle), \
                patch.object(sv, "process_ai_extensions", side_effect=extensions):
            applied = sv.run_summer_extension_passes({}, save, through_date, seed)
        return calls, applied

    def test_july_and_august_passes_on_the_way_to_august(self):
        save = {"state": {"current_date": "2027-07-04"}}
        calls, applied = self.run_passes(save, "2027-08-01")
        self.assertEqual(calls, ["2027-07-06", "2027-08-01"])
        self.assertEqual(applied, 4)
        ids = [row["id"] for row in save["processed_hidden_ai_actions"]]
        # The same ids as the day-by-day monthly passes (queue_ai_recommendations), so a month never runs twice.
        self.assertEqual(ids, [sv.stable_id("ai_action", "extensions", "2027-07", 17),
                               sv.stable_id("ai_action", "extensions", "2027-08", 17)])
        calls, _ = self.run_passes(save, "2027-09-01")
        self.assertEqual(calls, ["2027-09-01"])
        calls, applied = self.run_passes(save, "2027-09-30")
        self.assertEqual((calls, applied), ([], 0))

    def test_september_pass_is_the_one_day_by_day_camp_would_run(self):
        save = {"state": {"current_date": "2027-08-01"}}
        self.run_passes(save, "2027-09-01")
        label = sv.ai_extension_pass_label(save, "2027-09-01", "2027-09-02")
        self.assertIn(sv.stable_id("ai_action", "extensions", label, 17),
                      {row["id"] for row in save["processed_hidden_ai_actions"]})

    def test_free_agency_past_the_pass_date_runs_it_on_today(self):
        save = {"state": {"current_date": "2027-07-10"}}
        calls, _ = self.run_passes(save, "2027-08-01")
        self.assertEqual(calls, ["2027-07-10", "2027-08-01"])

    def test_months_already_gone_are_not_backfilled(self):
        save = {"state": {"current_date": "2027-09-01"}}
        calls, _ = self.run_passes(save, "2027-09-30")
        self.assertEqual(calls, ["2027-09-01"])

    def test_nothing_before_the_window_opens(self):
        save = {"state": {"current_date": "2027-07-01"}}
        calls, _ = self.run_passes(save, "2027-07-05")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
