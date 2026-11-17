import unittest

from nba_gm_data.app_actions import prospect_injury_report, prospect_medical_lookup
from nba_gm_data.health import generated_prospect_medical_profile


class ProspectInjuryReportTests(unittest.TestCase):
    def test_missing_profile_reports_unavailable(self):
        self.assertEqual(prospect_injury_report(None), {"available": False})

    def test_history_current_and_risk_are_separate(self):
        medical = {"durability": 40, "injury_prone": True,
                   "major_prior_injuries": [{"body_area": "knee", "severity": "medium", "season": "2025", "status": "recovered"}],
                   "current_injury": {"body_area": "knee", "severity": "medium", "start_date": "2026-06-10", "return_date": "2026-08-01"}}
        report = prospect_injury_report({**medical, "_prospect": {}})
        self.assertTrue(report["available"])
        self.assertEqual(report["history"][0]["body_area"], "Knee")
        self.assertEqual(report["current"]["return_date"], "2026-08-01")
        self.assertEqual(report["risk_label"], "High")

    def test_healed_injury_moves_to_history(self):
        medical = {"major_prior_injuries": [],
                   "current_injury": {"body_area": "knee", "severity": "medium", "start_date": "2026-06-10", "return_date": "2026-08-01"}}
        before = prospect_injury_report({**medical, "_prospect": {}}, "2026-07-01")
        after = prospect_injury_report({**medical, "_prospect": {}}, "2026-09-01")
        self.assertIsNotNone(before["current"])
        self.assertIsNone(after["current"])
        self.assertEqual(after["history"][0]["status"], "returned 2026-08-01")

    def test_lookup_uses_generated_profile_and_skips_real_prospects(self):
        active = {"draft_classes": [{"season": "2026", "seed": 7}], "draft_prospects": [
            {"id": "g1", "league": "generated", "draft_year": "2026"},
            {"id": "r1", "league": "ncaa", "draft_year": "2026"}]}
        lookup = prospect_medical_lookup(active)
        self.assertIn("g1", lookup)
        self.assertNotIn("r1", lookup)
        expected = generated_prospect_medical_profile("g1", "2026", 7)
        self.assertEqual(lookup["g1"]["major_prior_injuries"], expected["major_prior_injuries"])


if __name__ == "__main__":
    unittest.main()
