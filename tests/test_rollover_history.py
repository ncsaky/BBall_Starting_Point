"""Rollover history regressions using isolated saves and actual persistence."""

from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import save as save_module


class RolloverHistoryTests(unittest.TestCase):
    def fixture(self, count=25):
        save = {
            "version": save_module.SAVE_VERSION,
            "meta": {"id": "rollover-fixture", "season": "2025-26", "user_team_id": "home"},
            "state": {"current_date": "2026-09-30", "phase": "offseason"},
            "game_results": [],
            "team_game_logs": [],
            "player_game_logs": [],
        }
        for index in range(count):
            self.append_game(save, index, "2026-04")
        return save

    def append_game(self, save, index, month):
        game_id = f"game-{month}-{index:02d}"
        game_date = f"{month}-{index + 1:02d}"
        save["game_results"].append({
            "game_id": game_id,
            "home_team_id": "home",
            "away_team_id": "away",
            "home_score": 100 + index,
            "away_score": 90,
            "team_lines": [{"team_id": "home", "points": 100 + index}],
            "player_lines": [{"player_id": "player", "points": index}],
        })
        for team_id in ("home", "away"):
            save["team_game_logs"].append({
                "id": f"team-{game_id}-{team_id}", "game_id": game_id,
                "team_id": team_id, "date": game_date, "points": 100 + index,
            })
        save["player_game_logs"].append({
            "id": f"player-{game_id}", "game_id": game_id,
            "player_id": "player", "team_id": "home", "date": game_date,
            "points": index,
        })

    def rollover(self, directory, path, prepared):
        # These services exercise unrelated roster/schedule behavior. The actual
        # rollover resets, history archiving, manifest writes and reads run here.
        replacements = {
            "ensure_draft_processed": {}, "generate_league_awards": {},
            "build_year_in_review": {}, "apply_offseason_roster_transitions": {},
            "generate_future_schedule": {"games": []}, "initial_team_records": {},
            "clean_free_agency_state": None, "refresh_health_for_new_season": None,
            "age_staff_contracts": None,
        }
        with ExitStack() as stack:
            for name, result in replacements.items():
                stack.enter_context(patch.object(save_module, name, return_value=result))
            return save_module.complete_offseason_and_rollover(
                directory, {}, path, prepared_save=prepared,
            )

    def assert_history_matches(self, path, expected):
        complete = save_module.load_save(path, include_history=True)
        for kind in ("game_results", "team_game_logs", "player_game_logs"):
            key = "game_id" if kind == "game_results" else "id"
            self.assertEqual(
                {row[key]: row for row in complete[kind]},
                {row[key]: row for row in expected[kind]},
                kind,
            )
            self.assertEqual(len(complete[kind]), len(expected[kind]), kind)
        current = save_module.load_save(path)
        self.assertEqual(current["game_results"], [])
        self.assertEqual(current["team_game_logs"], [])
        self.assertEqual(current["player_game_logs"], [])
        self.assertNotIn("_history_to_archive", current)
        self.assertEqual(
            {row["game_id"]: row["date"] for row in current["game_result_summaries"]},
            {row["game_id"]: row["date"] for row in expected["team_game_logs"]},
        )

    def test_final_ten_box_scores_and_all_logs_survive_rollover(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "league.json"
            fixture = self.fixture()
            expected = deepcopy(fixture)
            save_module.write_save(path, fixture)
            prepared = save_module.load_save(path)
            self.assertEqual(len(prepared["game_results"]), 10)
            result = self.rollover(tmp, path, prepared)
            self.assertEqual(result["to_season"], "2026-27")
            self.assert_history_matches(path, expected)

    def test_unwritten_box_score_and_logs_are_archived_with_rollover(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "league.json"
            fixture = self.fixture()
            expected = deepcopy(fixture)
            save_module.write_save(path, fixture)
            prepared = save_module.load_save(path)
            self.append_game(prepared, 25, "2026-04")
            self.append_game(expected, 25, "2026-04")
            self.rollover(tmp, path, prepared)
            self.assert_history_matches(path, expected)

    def test_history_survives_multiple_rollovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "league.json"
            fixture = self.fixture()
            expected = deepcopy(fixture)
            save_module.write_save(path, fixture)
            self.rollover(tmp, path, save_module.load_save(path))
            prepared = save_module.load_save(path)
            for index in range(12):
                self.append_game(prepared, index, "2027-04")
                self.append_game(expected, index, "2027-04")
            save_module.write_save(path, prepared)
            self.rollover(tmp, path, save_module.load_save(path))
            self.assert_history_matches(path, expected)

    def test_interrupted_rollover_keeps_previous_history_and_can_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "league.json"
            fixture = self.fixture()
            expected = deepcopy(fixture)
            save_module.write_save(path, fixture)
            before = save_module.load_save(path, include_history=True)
            prepared = save_module.load_save(path)
            self.append_game(prepared, 25, "2026-04")
            self.append_game(expected, 25, "2026-04")
            original_replace = Path.replace

            def interrupt_publication(source, target):
                if Path(target) == path:
                    raise OSError("injected interruption before rollover manifest publication")
                return original_replace(source, target)

            with patch.object(Path, "replace", interrupt_publication):
                with self.assertRaisesRegex(OSError, "injected interruption"):
                    self.rollover(tmp, path, prepared)
            self.assertEqual(save_module.load_save(path, include_history=True), before)
            self.assertEqual(len(prepared["_history_to_archive"]["game_results"]), 11)
            save_module.write_save(path, prepared)
            self.assert_history_matches(path, expected)


if __name__ == "__main__":
    unittest.main()
