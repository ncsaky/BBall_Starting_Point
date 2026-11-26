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

    @staticmethod
    def kept_after_rollover(expected, season_start):
        """Finished-season game detail is not kept (user decision 2026-11-18, history_store.SEASONS_KEPT): box scores
        and team logs only for the current season, player logs for the current and previous season."""
        kept = deepcopy(expected)
        cutoffs = {kind: f"{season_start - (seasons - 1)}-07-01" for kind, seasons in
                   (("game_results", 1), ("team_game_logs", 1), ("player_game_logs", 2))}
        dates = {row["game_id"]: row["date"] for row in expected["team_game_logs"]}
        kept["game_results"] = [row for row in expected["game_results"] if dates[row["game_id"]] >= cutoffs["game_results"]]
        for kind in ("team_game_logs", "player_game_logs"):
            kept[kind] = [row for row in expected[kind] if row["date"] >= cutoffs[kind]]
        return kept

    def assert_history_matches(self, path, expected):
        complete = save_module.load_save(path, include_history=True)
        season_start = int(complete["meta"]["season"][:4])
        all_dates = {row["game_id"]: row["date"] for row in expected["team_game_logs"]}
        expected = self.kept_after_rollover(expected, season_start)
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
        # Score summaries (date and final score) are kept for every game: in the save for the current and last
        # season, in the season archive files for older seasons (SEASON-ARCHIVE).
        from nba_gm_data.season_archive import archive_entries, archived_tables
        archived = [row for label in archive_entries(current)
                    for row in archived_tables(path, current, label).get("game_result_summaries", [])]
        self.assertEqual({row["game_id"]: row["date"] for row in [*current["game_result_summaries"], *archived]}, all_dates)

    def test_rollover_keeps_current_detail_and_drops_finished_season_boxes(self):
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

    def test_history_follows_retention_across_multiple_rollovers(self):
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

    def test_removed_detail_is_physically_deleted_after_the_next_save(self):
        import sqlite3
        from nba_gm_data.history_store import history_sidecar_path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "league.json"
            save_module.write_save(path, self.fixture())
            self.rollover(tmp, path, save_module.load_save(path))
            database = history_sidecar_path(path, save_module.load_save(path))

            def stored(kind):
                with sqlite3.connect(database) as connection:
                    return connection.execute("SELECT COUNT(*) FROM history_records WHERE kind=?", (kind,)).fetchone()[0]

            self.assertGreater(stored("game_results"), 0)        # hidden, but the previous manifest could still need it
            save_module.write_save(path, save_module.load_save(path))
            self.assertEqual(stored("game_results"), 0)           # published removal is reclaimed on the next save
            self.assertEqual(stored("team_game_logs"), 0)
            self.assertEqual(stored("player_game_logs"), 25)      # previous season's player logs stay
            self.assert_history_matches(path, self.fixture())


if __name__ == "__main__":
    unittest.main()
