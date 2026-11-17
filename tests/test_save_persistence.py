"""Save reliability checks use only disposable JSON and SQLite fixtures."""

from __future__ import annotations

import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import save as save_module
from nba_gm_data.history_store import (
    SaveValidationError,
    history_sidecar_path,
    load_history_records,
    migration_backup_path,
)
from nba_gm_data.save import load_save, write_save
from nba_gm_data.save_recovery import create_export, restore_export


def fixture() -> dict:
    return {
        "version": "league_save_v1",
        "meta": {"id": "fixture", "season": "2025-26"},
        "game_results": [{"game_id": f"game_{i:02d}", "home_score": i} for i in range(15)],
        "player_game_logs": [{"id": "log_1", "game_id": "game_00", "player_id": "p1", "points": 12, "date": "2025-11-01"}],
    }


class SavePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fixture.json"

    def seed(self) -> dict:
        save = fixture()
        write_save(self.path, save)
        return save

    def test_missing_required_history_is_an_actionable_error_and_not_recreated(self):
        save = self.seed()
        database = history_sidecar_path(self.path, save)
        database.unlink()
        before = self.path.read_bytes()
        for read in (lambda: load_save(self.path), lambda: load_history_records(self.path, save, "game_results")):
            with self.assertRaisesRegex(SaveValidationError, "missing.*restore"):
                read()
        with self.assertRaises(SaveValidationError):
            write_save(self.path, save)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(database.exists())

    def test_corrupt_history_is_an_actionable_error(self):
        save = self.seed()
        database = history_sidecar_path(self.path, save)
        database.write_bytes(b"not a SQLite file")
        with self.assertRaisesRegex(SaveValidationError, "Cannot read history.*Restore"):
            load_save(self.path)
        self.assertEqual(database.read_bytes(), b"not a SQLite file")

    def test_missing_checkpoint_or_wrong_database_is_rejected(self):
        save = self.seed()
        with sqlite3.connect(history_sidecar_path(self.path, save)) as connection:
            connection.execute("UPDATE history_commits SET snapshot_id='other-save'")
        with self.assertRaisesRegex(SaveValidationError, "different snapshots"):
            load_save(self.path)

    def test_bad_historical_json_is_rejected(self):
        save = self.seed()
        with sqlite3.connect(history_sidecar_path(self.path, save)) as connection:
            connection.execute("UPDATE history_records SET payload_json='broken' WHERE kind='player_game_logs'")
        with self.assertRaises(SaveValidationError):
            load_save(self.path)

    def test_unsupported_future_manifest_history_and_database_formats_rejected(self):
        save = self.seed()
        original = self.path.read_bytes()
        for transform in (
            lambda row: row.update(version="league_save_v999"),
            lambda row: row["history_store"].update(version=999),
        ):
            future = copy.deepcopy(save)
            transform(future)
            self.path.write_text(json.dumps(future))
            with self.assertRaisesRegex(SaveValidationError, "Unsupported"):
                load_save(self.path)
        self.path.write_bytes(original)
        with sqlite3.connect(history_sidecar_path(self.path, save)) as connection:
            connection.execute("PRAGMA user_version=999")
        with self.assertRaisesRegex(SaveValidationError, "Unsupported history database"):
            load_save(self.path)

    def test_unsafe_manifest_history_path_rejected(self):
        save = self.seed()
        for name in ("../outside.sqlite3", "/tmp/outside.sqlite3", "..\\outside.sqlite3", "C:outside.sqlite3"):
            save["history_store"]["path"] = name
            self.path.write_text(json.dumps(save))
            with self.assertRaisesRegex(SaveValidationError, "unsafe"):
                load_save(self.path)

    def test_malformed_core_manifest_sections_are_rejected(self):
        for key, value in (("meta", []), ("state", []), ("schedule_state", []), ("season_schedules", []), ("game_results", {}), ("player_game_logs", [42]), ("state", {"current_date": "not-a-date"})):
            manifest = {"version": "league_save_v1", key: value}
            self.path.write_text(json.dumps(manifest))
            with self.subTest(key=key, value=value), self.assertRaisesRegex(SaveValidationError, "malformed"):
                load_save(self.path)

    def test_interrupted_update_preserves_old_row_and_retry_discards_failed_rows(self):
        self.seed()
        before = self.path.read_bytes()
        changed = load_save(self.path)
        changed["player_game_logs"] = [
            {"id": "log_1", "player_id": "p1", "points": 99, "date": "2025-11-01"},
            {"id": "failed_only", "player_id": "p2", "points": 50, "date": "2025-11-02"},
        ]
        input_before = copy.deepcopy(changed)
        with patch.object(save_module.json, "dump", side_effect=OSError("injected manifest failure")):
            with self.assertRaisesRegex(OSError, "injected"):
                write_save(self.path, changed)
        self.assertEqual(changed, input_before)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(load_save(self.path, include_history=True)["player_game_logs"][0]["points"], 12)
        retry = load_save(self.path)
        retry["player_game_logs"] = [{"id": "log_1", "player_id": "p1", "points": 23, "date": "2025-11-01"}]
        write_save(self.path, retry)
        rows = load_save(self.path, include_history=True)["player_game_logs"]
        self.assertEqual([(row["id"], row["points"]) for row in rows], [("log_1", 23)])
        self.assertEqual(retry["history_store"]["archived_counts"]["player_game_logs"], 1)

    def test_actual_process_exit_between_history_and_manifest_is_recoverable(self):
        self.seed()
        code = '''
import os, sys
from nba_gm_data import save as module
path = sys.argv[1]
save = module.load_save(path)
save['player_game_logs'] = [{'id': 'crashed', 'points': 88}]
module.json.dump = lambda *args, **kwargs: os._exit(71)
module.write_save(path, save)
'''
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        result = subprocess.run([sys.executable, "-c", code, str(self.path)], env=environment, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 71, result.stderr.decode())
        save = load_save(self.path, include_history=True)
        self.assertEqual([row["id"] for row in save["player_game_logs"]], ["log_1"])
        write_save(self.path, load_save(self.path))
        self.assertEqual([row["id"] for row in load_save(self.path, include_history=True)["player_game_logs"]], ["log_1"])

    def test_interruption_before_sqlite_commit_rolls_back_history(self):
        save = self.seed()
        before = self.path.read_bytes()
        changed = load_save(self.path)
        changed["player_game_logs"] = [{"id": "new", "bad": {1, 2}}]
        with self.assertRaises(TypeError):
            write_save(self.path, changed)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(load_save(self.path, include_history=True)["player_game_logs"][0]["points"], 12)
        with sqlite3.connect(history_sidecar_path(self.path, save)) as connection:
            self.assertEqual(connection.execute("SELECT MAX(revision) FROM history_commits").fetchone()[0], 1)

    def test_legacy_embedded_history_migrates_without_loss_and_keeps_original(self):
        legacy = fixture()
        self.path.write_text(json.dumps(legacy))
        original = self.path.read_bytes()
        self.assertEqual(load_save(self.path), {**legacy, "staff_season_changes": {}})  # Load normalization adds staff_season_changes.
        write_save(self.path, legacy)
        self.assertEqual(migration_backup_path(self.path).read_bytes(), original)
        hydrated = load_save(self.path, include_history=True)
        self.assertEqual(len(hydrated["game_results"]), 15)
        self.assertEqual(hydrated["player_game_logs"][0]["points"], 12)

    def test_v1_history_schema_migrates_and_interrupted_migration_stays_readable(self):
        database = history_sidecar_path(self.path)
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE history_records(kind TEXT NOT NULL, record_id TEXT NOT NULL, event_date TEXT, season TEXT, revision INTEGER NOT NULL, game_id TEXT, player_id TEXT, team_id TEXT, payload_json TEXT NOT NULL, PRIMARY KEY(kind, record_id))")
            connection.execute("INSERT INTO history_records VALUES ('player_game_logs', 'legacy', '2025-11-01', '2025-26', 1, 'g', 'p', NULL, ?)", (json.dumps({"id": "legacy", "points": 17}),))
        save = {"version": "league_save_v1", "meta": {"save_revision": 1}, "history_store": {"version": 1, "path": database.name, "revision": 1, "archived_counts": {"player_game_logs": 1}}}
        self.path.write_text(json.dumps(save))
        self.assertEqual(load_save(self.path, include_history=True)["player_game_logs"][0]["points"], 17)
        with patch.object(save_module.json, "dump", side_effect=OSError("migration interrupted")):
            with self.assertRaises(OSError):
                write_save(self.path, save)
        self.assertEqual(load_save(self.path, include_history=True)["player_game_logs"][0]["points"], 17)
        write_save(self.path, save)
        self.assertEqual(load_save(self.path)["history_store"]["version"], 2)
        self.assertEqual(load_save(self.path, include_history=True)["player_game_logs"][0]["points"], 17)

    def test_v1_history_empty_required_category_is_rejected(self):
        save = self.seed()
        save["history_store"]["version"] = 1
        self.path.write_text(json.dumps(save))
        with sqlite3.connect(history_sidecar_path(self.path, save)) as connection:
            connection.execute("DELETE FROM history_records WHERE kind='player_game_logs'")
        with self.assertRaisesRegex(SaveValidationError, "legacy history component is incomplete"):
            load_save(self.path)

    def test_v1_historical_upsert_overcounts_remain_compatible(self):
        save = self.seed()
        save["history_store"]["version"] = 1
        save["history_store"]["archived_counts"]["player_game_logs"] += 100
        self.path.write_text(json.dumps(save))
        self.assertEqual(len(load_save(self.path, include_history=True)["player_game_logs"]), 1)
        write_save(self.path, load_save(self.path))
        self.assertEqual(load_save(self.path)["history_store"]["archived_counts"]["player_game_logs"], 1)

    def test_stale_writer_cannot_overwrite_a_newer_committed_save(self):
        self.seed()
        first = load_save(self.path)
        second = load_save(self.path)
        write_save(self.path, first)
        with self.assertRaisesRegex(SaveValidationError, "changed while"):
            write_save(self.path, second)

    def test_restore_of_same_revision_rejects_an_older_open_history_save(self):
        self.seed()
        stale = load_save(self.path)
        archive = create_export(self.path)
        restore_export(self.path, archive, replace=True)
        previous_bytes = self.path.read_bytes()
        stale["marker"] = "must not replace restored state"
        with self.assertRaisesRegex(SaveValidationError, "restored or changed|history component changed"):
            write_save(self.path, stale)
        self.assertEqual(self.path.read_bytes(), previous_bytes)

    def test_restore_of_same_revision_rejects_an_older_open_json_only_save(self):
        save = {"version": "league_save_v1", "meta": {"id": "early_save"}}
        write_save(self.path, save)
        stale = load_save(self.path)
        archive = create_export(self.path)
        restore_export(self.path, archive, replace=True)
        previous_bytes = self.path.read_bytes()
        with self.assertRaisesRegex(SaveValidationError, "restored or changed"):
            write_save(self.path, stale)
        self.assertEqual(self.path.read_bytes(), previous_bytes)

    def test_restore_of_legacy_without_revision_rejects_an_older_open_save(self):
        self.path.write_text(json.dumps({"version": "league_save_v1", "meta": {"id": "legacy"}}))
        stale = load_save(self.path)
        restore_export(self.path, create_export(self.path), replace=True)
        with self.assertRaisesRegex(SaveValidationError, "restored or changed"):
            write_save(self.path, stale)

    def test_identityless_legacy_restore_rejects_an_older_open_save(self):
        for metadata in ({"meta": {}}, {}):
            with self.subTest(metadata=metadata):
                self.path.write_text(json.dumps({"version": "league_save_v1", "marker": "B", **metadata}))
                stale = load_save(self.path)
                restore_export(self.path, create_export(self.path), replace=True)
                restored = self.path.read_bytes()
                stale["marker"] = "must not overwrite B"
                with self.assertRaisesRegex(SaveValidationError, "restored or changed"):
                    write_save(self.path, stale)
                self.assertEqual(self.path.read_bytes(), restored)

    def test_identityless_legacy_first_write_remains_supported_and_rejects_stale_copy(self):
        legacy = {"version": "league_save_v1", "meta": {}, "marker": "legacy"}
        self.path.write_text(json.dumps(legacy))
        first, stale = load_save(self.path), load_save(self.path)
        self.assertEqual(first, {**legacy, "staff_season_changes": {}})  # Reading does not silently migrate metadata (staff_season_changes is a normalization default).
        first["marker"] = "updated"
        write_save(self.path, first)
        self.assertNotIn("id", first["meta"])
        self.assertTrue(first["meta"]["save_snapshot_id"])
        with self.assertRaisesRegex(SaveValidationError, "restored or changed"):
            write_save(self.path, stale)
        fresh = load_save(self.path)
        fresh["marker"] = "updated again"
        write_save(self.path, fresh)
        self.assertEqual(load_save(self.path)["marker"], "updated again")

    def test_normally_generated_save_restore_rejects_an_older_open_save(self):
        from nba_gm_data.app_actions import load_app_canonical

        root = Path(__file__).resolve().parents[1]
        canonical = load_app_canonical(root)
        save_module.create_league_save(root, canonical, "GSW", self.path, seed=913)
        stale = load_save(self.path)
        self.assertTrue(stale["meta"]["id"])
        restore_export(self.path, create_export(self.path), replace=True)
        restored = self.path.read_bytes()
        with self.assertRaisesRegex(SaveValidationError, "restored or changed"):
            write_save(self.path, stale)
        self.assertEqual(self.path.read_bytes(), restored)

    def test_manifest_and_database_bytes_unchanged_by_validation(self):
        save = self.seed()
        database = history_sidecar_path(self.path, save)
        manifest_bytes, database_bytes = self.path.read_bytes(), database.read_bytes()
        load_save(self.path, include_history=True)
        self.assertEqual(self.path.read_bytes(), manifest_bytes)
        self.assertEqual(database.read_bytes(), database_bytes)


if __name__ == "__main__":
    unittest.main()
