"""No-change evaluations are calendar evidence, not extra growth or staff blame."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nba_gm_data import health, save as sv, staff
from nba_gm_data.history_store import archive_save_history, load_history_records


class DevelopmentCoverageTests(unittest.TestCase):
    def fixture(self):
        row = json.loads((Path(__file__).parent / "fixtures/development_no_change.json").read_text())
        return row, {"players": [row["player"]], "traits": row["traits"]}

    def context(self, fixture):
        stack = ExitStack()
        stack.enter_context(patch.object(health, "coach_development_by_team", return_value={}))
        stack.enter_context(patch.object(health, "development_staff_modifiers", return_value=fixture["staff"]))
        return stack

    def test_seed71_july_is_evaluated_but_has_no_reportable_movement(self):
        row, active = self.fixture()
        original = deepcopy(active)
        with self.context(row):
            result = health.advance_development(active, row["month"], row["seed"])
            repeated = health.advance_development(json.loads(json.dumps(active)), row["month"], row["seed"])
        self.assertEqual(result, repeated)
        self.assertEqual(result["event_count"], 1)
        event = result["events"][0]
        self.assertEqual(event["player_id"], row["player"]["id"])
        self.assertEqual(event["month"], "2027-07")
        self.assertEqual(event["trait_deltas"], {})
        self.assertIn("no reportable", event["notes"])
        sv.apply_development_events_to_traits(active, result["events"])
        self.assertEqual(active, original)

    def test_threshold_and_player_eligibility_are_unchanged(self):
        row, active = self.fixture()
        active["players"].append({**row["player"], "id": "inactive", "_inactive_player": True})
        with self.context(row), patch.object(health, "monthly_trait_delta", return_value=.014):
            events = health.advance_development(active, "2027-07", 71)["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["trait_deltas"], {})
        with self.context(row), patch.object(health, "monthly_trait_delta", return_value=.015):
            events = health.advance_development(active, "2027-07", 71)["events"]
        self.assertEqual(set(events[0]["trait_deltas"].values()), {.015})

    def test_repeat_and_reload_do_not_duplicate_a_zero_change_month(self):
        row, active = self.fixture()
        saved = {"development_events": [], "applied_development_months": [], "news_items": []}
        with self.context(row):
            first = sv.process_development_months(active, saved, "2027-06-30", "2027-07-01", 71)
            saved = json.loads(json.dumps(saved))
            second = sv.process_development_months(active, saved, "2027-06-30", "2027-07-01", 71)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(len(saved["development_events"]), 1)
        self.assertEqual(saved["applied_development_months"], ["2027-07"])

    def test_zero_change_records_do_not_change_staff_evaluation(self):
        changed = [{"team_id": "team", "trait_deltas": {"shooting_range": .2}} for _ in range(12)]
        neutral = [{"team_id": "team", "trait_deltas": {}} for _ in range(100)]
        for evaluate in (staff.staff_development_signal, sv.team_development_gain):
            before = evaluate({"development_events": changed}, "team")
            after = evaluate({"development_events": changed + neutral}, "team")
            self.assertEqual(before, after)

    def test_no_change_evidence_survives_archiving_without_trait_growth(self):
        row, active = self.fixture()
        with self.context(row):
            events = health.advance_development(active, "2027-07", 71)["events"]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "disposable.json"
            saved = {"state": {"current_date": "2028-10-01"}, "meta": {"season": "2028-29"},
                     "development_events": events, "_history_to_archive": {"development_events": events}}
            archive_save_history(path, saved, 1)
            saved = json.loads(json.dumps(saved))
            archived = load_history_records(path, saved, "development_events")
            self.assertEqual(archived, events)
            self.assertEqual(saved["development_events"], [])
            self.assertFalse(any(saved.get("development_trait_totals", {}).values()))


if __name__ == "__main__":
    unittest.main()
