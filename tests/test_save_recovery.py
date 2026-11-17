"""All persistence fixtures live in TemporaryDirectory; never use repository saves."""

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing
from copy import deepcopy
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
from urllib import request, error

from nba_gm_data import app_actions
from nba_gm_data.history_store import SaveValidationError, history_sidecar_path
from nba_gm_data.save import load_save, write_save
from nba_gm_data.save_recovery import (
    BACKUP_FORMAT, SaveRecoveryError, create_export, previous_backup_path,
    pending_restore_path, recover_previous_save, restore_export,
)


def fixture(marker="original", count=15):
    return {
        "version": "league_save_v1",
        "meta": {"id": "fixture", "season": "2026-27", "user_team_abbrev": "GSW"},
        "state": {"current_date": "2026-10-01", "phase": "preseason"},
        "marker": marker,
        "game_results": [{"game_id": f"g{i:03}", "home_score": 100 + i, "team_lines": []} for i in range(count)],
        "player_game_logs": [{"game_id": f"g{i:03}", "player_id": "p1", "points": i, "date": "2026-01-01"} for i in range(count)],
        "team_game_logs": [{"game_id": f"g{i:03}", "team_id": "t1", "date": "2026-01-01"} for i in range(count)],
    }


def fake_create(root, canonical, team, path, **kwargs):
    time.sleep(0.025)  # Widen the collision window for threads and processes.
    save = fixture(str(kwargs["seed"]), count=0)
    write_save(path, save)
    return save


def create_worker(directory, name, seed, ready=None, start=None, results=None, *, patch_creation=True):
    if ready is not None:
        ready.put(True)
        start.wait(10)
    try:
        with ExitStack() as stack:
            if patch_creation:
                stack.enter_context(patch.object(app_actions, "create_league_save", side_effect=fake_create))
                stack.enter_context(patch.object(app_actions, "save_status", return_value={}))
            app_actions.create_save_action(Path(directory), {"teams": [{"id": "t1", "abbrev": "GSW", "name": "Warriors"}]}, Path(directory), {"save_name": name, "team": "GSW", "seed": seed})
        result = ("created", seed)
    except SaveRecoveryError:
        result = ("collision", seed)
    if results is not None:
        results.put(result)
    return result


def archive_members(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def repack(members, *, checksums=True):
    members = dict(members)
    if checksums:
        members["backup.json"] = json.dumps({
            "format": BACKUP_FORMAT,
            "members": {name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in members.items() if name != "backup.json"},
        }).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


class SaveRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nba-recovery-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / "original.json"
        write_save(self.path, fixture())

    def test_duplicate_and_normalized_names_do_not_overwrite(self):
        self.assertEqual(create_worker(self.directory, "A-B", 1)[0], "created")
        before = (self.directory / "a_b.json").read_bytes()
        for name in ("A-B", "A B", "a_b", "A_B"):
            self.assertEqual(create_worker(self.directory, name, 2)[0], "collision")
            self.assertEqual((self.directory / "a_b.json").read_bytes(), before)

    def test_concurrent_creation_threads_has_exactly_one_winner(self):
        # Patches belong to the whole pool. Per-worker overlapping patches can
        # restore another worker's mock and leak fake creation into later tests.
        with patch.object(app_actions, "create_league_save", side_effect=fake_create), patch.object(app_actions, "save_status", return_value={}), ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda i: create_worker(self.directory, "same name" if i % 2 else "Same-Name", i, patch_creation=False), range(6)))
        winners = [seed for result, seed in results if result == "created"]
        self.assertEqual(len(winners), 1)
        self.assertEqual(load_save(self.directory / "same_name.json")["marker"], str(winners[0]))

    def test_concurrent_creation_processes_has_exactly_one_winner(self):
        context = multiprocessing.get_context("spawn")
        ready, results, start = context.Queue(), context.Queue(), context.Event()
        processes = [context.Process(target=create_worker, args=(str(self.directory), name, i, ready, start, results)) for i, name in enumerate(("Race-Name", "Race Name", "race_name"))]
        for process in processes:
            process.start()
        try:
            for _ in processes:
                self.assertTrue(ready.get(timeout=15))
            start.set()
            outcomes = [results.get(timeout=15) for _ in processes]
            self.assertEqual(sum(result == "created" for result, _ in outcomes), 1)
        finally:
            start.set()
            for process in processes:
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join()
                self.assertEqual(process.exitcode, 0)
            ready.close()
            results.close()

    def test_export_restore_round_trip_including_all_history(self):
        before = load_save(self.path, include_history=True)
        exported = create_export(self.path)
        target = self.directory / "portable" / "renamed.json"
        restore_export(target, exported)
        after = load_save(target, include_history=True)
        after["history_store"]["path"] = before["history_store"]["path"]
        after["meta"]["save_snapshot_id"] = before["meta"]["save_snapshot_id"]
        self.assertEqual(after, before)
        self.assertEqual(set(archive_members(exported)), {"backup.json", "save.json", "history.sqlite3"})
        # A portable backup continues to work after the original pair disappears.
        self.path.unlink()
        history_sidecar_path(self.path, before).unlink()
        self.assertEqual(len(load_save(target, include_history=True)["game_results"]), 15)

    def test_export_includes_committed_wal_frames(self):
        save = load_save(self.path)
        database = history_sidecar_path(self.path, save)
        with closing(sqlite3.connect(database)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE wal_fixture (marker TEXT)")
            writer.execute("INSERT INTO wal_fixture VALUES ('committed in WAL')")
            writer.commit()
            self.assertGreater(Path(str(database) + "-wal").stat().st_size, 0)
            backup = archive_members(create_export(self.path))["history.sqlite3"]
            check = self.directory / "wal_snapshot.sqlite3"
            check.write_bytes(backup)
            with closing(sqlite3.connect(check)) as reader:
                self.assertEqual(reader.execute("SELECT marker FROM wal_fixture").fetchone()[0], "committed in WAL")

    def test_export_waits_for_writer_and_captures_one_complete_revision(self):
        from nba_gm_data import save as save_module

        entered, release, export_started, export_done = (threading.Event() for _ in range(4))
        save = load_save(self.path)
        save["marker"] = "new revision"
        save["player_game_logs"] = [{"id": "concurrent", "points": 99}]
        dump = save_module.json.dump

        def blocked_dump(*args, **kwargs):
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test writer not released")
            return dump(*args, **kwargs)

        def export():
            export_started.set()
            data = create_export(self.path)
            export_done.set()
            return data

        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(save_module.json, "dump", side_effect=blocked_dump):
            writer = pool.submit(write_save, self.path, save)
            try:
                self.assertTrue(entered.wait(10))
                exporter = pool.submit(export)
                self.assertTrue(export_started.wait(10))
                self.assertFalse(export_done.wait(0.05))
            finally:
                release.set()
            writer.result(timeout=10)
            archive = exporter.result(timeout=10)
        restored = self.directory / "concurrent_export.json"
        restore_export(restored, archive)
        result = load_save(restored, include_history=True)
        self.assertEqual(result["marker"], "new revision")
        self.assertTrue(any(row.get("id") == "concurrent" for row in result["player_game_logs"]))

    def test_previous_backup_preserves_full_valid_pair_and_recovers_missing_history(self):
        before = load_save(self.path, include_history=True)
        save = load_save(self.path)
        save["marker"] = "updated"
        write_save(self.path, save)
        self.assertTrue(previous_backup_path(self.path).is_file())
        history_sidecar_path(self.path, save).unlink()
        listing = app_actions.list_saves(self.directory)["saves"][0]
        self.assertEqual(listing["status"], "unreadable")
        self.assertTrue(listing["recovery_available"])
        self.assertIn("missing", listing["error"])
        recover_previous_save(self.path)
        after = load_save(self.path, include_history=True)
        after["history_store"]["path"] = before["history_store"]["path"]
        after["meta"]["save_snapshot_id"] = before["meta"]["save_snapshot_id"]
        self.assertEqual(after, before)
        self.assertTrue(list(self.directory.glob("*.unreadable-*.bak")))

    def test_missing_manifest_remains_listed_and_recoverable(self):
        save = load_save(self.path)
        write_save(self.path, save)
        self.path.unlink()
        listing = app_actions.list_saves(self.directory)["saves"]
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]["status"], "unreadable")
        self.assertTrue(listing[0]["recovery_available"])
        recover_previous_save(self.path)
        self.assertEqual(load_save(self.path)["marker"], "original")

    def test_cached_dashboard_does_not_hide_newly_missing_history(self):
        save = load_save(self.path)
        canonical = {"teams": []}
        key = str(self.path.resolve())
        context = {"revision": app_actions.save_file_revision(self.path), "canonical_identity": id(canonical), "save": save}
        with patch.dict(app_actions._READ_CACHE, {key: context}):
            history_sidecar_path(self.path, save).unlink()
            for read in (app_actions.normalized_read_save, app_actions.dashboard_read_context):
                with self.assertRaisesRegex(SaveValidationError, "missing"):
                    read(canonical, self.path)

    def test_restore_preserves_previous_valid_save(self):
        exported = create_export(self.path)
        before = load_save(self.path)
        before["marker"] = "previous valid target"
        write_save(self.path, before)
        restore_export(self.path, exported, replace=True)
        self.assertEqual(load_save(self.path)["marker"], "original")
        previous = self.directory / "check_previous.json"
        restore_export(previous, previous_backup_path(self.path).read_bytes())
        self.assertEqual(load_save(previous)["marker"], "previous valid target")

    def test_restore_interruption_before_manifest_preserves_old_pair(self):
        archive = create_export(self.path)
        before = load_save(self.path)
        before["marker"] = "current target"
        write_save(self.path, before)
        old_json = self.path.read_bytes()
        old_history = load_save(self.path, include_history=True)
        replace = Path.replace

        def fail_manifest(source, target):
            if Path(target) == self.path:
                raise OSError("simulated restore interruption")
            return replace(source, target)

        with patch.object(Path, "replace", fail_manifest):
            with self.assertRaisesRegex(OSError, "interruption"):
                restore_export(self.path, archive, replace=True)
        self.assertEqual(self.path.read_bytes(), old_json)
        self.assertEqual(load_save(self.path, include_history=True), old_history)
        restore_export(self.path, archive, replace=True)
        self.assertEqual(load_save(self.path)["marker"], "original")

    def seed_recovery_pair(self, path):
        write_save(path, fixture("B: intended recovery"))
        intended = load_save(path, include_history=True)
        current = load_save(path)
        current["marker"] = "A: current"
        current["player_game_logs"] = [{"game_id": "A-only", "player_id": "p1", "points": 999}]
        current["game_results"].append({"game_id": "A-only", "home_score": 999, "team_lines": []})
        write_save(path, current)
        return intended, load_save(path, include_history=True)

    def assert_snapshot_matches(self, actual, expected):
        actual = deepcopy(actual)
        actual["meta"]["save_snapshot_id"] = expected["meta"]["save_snapshot_id"]
        if actual.get("history_store"):
            actual["history_store"]["path"] = expected["history_store"]["path"]
        self.assertEqual(actual, expected)

    def assert_archive_matches(self, archive, expected):
        self.assertEqual(json.loads(archive_members(archive)["save.json"])["marker"], expected["marker"])
        # Restore the archive to verify its checkpoint and every SQLite history row.
        with tempfile.TemporaryDirectory(dir=self.directory) as tmp:
            checked = Path(tmp) / "checked.json"
            restore_export(checked, archive)
            self.assert_snapshot_matches(load_save(checked, include_history=True), expected)

    def test_recover_previous_failure_keeps_source_and_retry_restores_its_history(self):
        for boundary in ("history", "manifest"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                path = Path(tmp) / "recovery.json"
                intended, current = self.seed_recovery_pair(path)
                source = previous_backup_path(path).read_bytes()
                replace = Path.replace

                def fail_publication(temporary, destination):
                    destination = Path(destination)
                    if ((boundary == "manifest" and destination == path)
                            or (boundary == "history" and ".restored-" in destination.name)):
                        raise OSError("injected recovery publication failure")
                    return replace(temporary, destination)

                with patch.object(Path, "replace", fail_publication):
                    with self.assertRaisesRegex(OSError, "publication failure"):
                        recover_previous_save(path)
                self.assertEqual(load_save(path, include_history=True), current)
                self.assertEqual(previous_backup_path(path).read_bytes(), source)
                self.assert_archive_matches(source, intended)
                recover_previous_save(path)
                self.assert_snapshot_matches(load_save(path, include_history=True), intended)
                self.assert_archive_matches(previous_backup_path(path).read_bytes(), current)

    def test_recovery_retry_after_backup_promotion_error_finishes_without_undoing_restore(self):
        for boundary in ("before_previous", "after_previous", "before_cleanup"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                path = Path(tmp) / "recovery.json"
                intended, current = self.seed_recovery_pair(path)
                replace, unlink = Path.replace, Path.unlink

                def fail_promotion(temporary, destination):
                    if Path(destination) == previous_backup_path(path):
                        if boundary == "before_previous":
                            raise OSError("injected backup promotion failure")
                        result = replace(temporary, destination)
                        if boundary == "after_previous":
                            raise OSError("injected backup promotion failure")
                        return result
                    return replace(temporary, destination)

                def fail_cleanup(source, *args, **kwargs):
                    if boundary == "before_cleanup" and source == pending_restore_path(path):
                        raise OSError("injected backup promotion failure")
                    return unlink(source, *args, **kwargs)

                with patch.object(Path, "replace", fail_promotion), patch.object(Path, "unlink", fail_cleanup):
                    with self.assertRaisesRegex(OSError, "promotion failure"):
                        recover_previous_save(path)
                self.assert_snapshot_matches(load_save(path, include_history=True), intended)
                self.assert_archive_matches(pending_restore_path(path).read_bytes(), current)
                expected_previous = intended if boundary == "before_previous" else current
                self.assert_archive_matches(previous_backup_path(path).read_bytes(), expected_previous)
                result = recover_previous_save(path)
                self.assertEqual(result["status"], "restored")
                self.assert_snapshot_matches(load_save(path, include_history=True), intended)
                self.assert_archive_matches(previous_backup_path(path).read_bytes(), current)
                self.assertFalse(pending_restore_path(path).exists())

    def interrupt_recovery_process(self, path, boundary):
        # os._exit bypasses exception handling/finally and releases process locks.
        code = '''
import os, sys
from pathlib import Path
from nba_gm_data.save_recovery import recover_previous_save, previous_backup_path, pending_restore_path
target, boundary = Path(sys.argv[1]), sys.argv[2]
replace, unlink = Path.replace, Path.unlink
def interrupted_replace(source, destination):
    destination = Path(destination)
    kind = ('manifest' if destination == target else
            'previous' if destination == previous_backup_path(target) else
            'pending' if destination == pending_restore_path(target) else
            'history' if '.restored-' in destination.name and destination.suffix == '.sqlite3' else '')
    if kind and boundary == 'before_' + kind:
        os._exit(72)
    result = replace(source, destination)
    if kind and boundary == 'after_' + kind:
        os._exit(72)
    return result
def interrupted_unlink(source, *args, **kwargs):
    if source == pending_restore_path(target) and boundary == 'before_cleanup':
        os._exit(72)
    result = unlink(source, *args, **kwargs)
    if source == pending_restore_path(target) and boundary == 'after_cleanup':
        os._exit(72)
    return result
Path.replace, Path.unlink = interrupted_replace, interrupted_unlink
recover_previous_save(target)
'''
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([sys.executable, "-c", code, str(path), boundary],
                                env=environment, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 72, result.stderr.decode())

    def test_process_interruption_at_recovery_publication_boundaries_preserves_both_snapshots(self):
        boundaries = ("before_pending", "after_pending", "before_history", "after_history",
                      "before_manifest", "after_manifest", "before_previous", "after_previous",
                      "before_cleanup", "after_cleanup")
        for boundary in boundaries:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(dir=self.directory) as tmp:
                path = Path(tmp) / "recovery.json"
                intended, current = self.seed_recovery_pair(path)
                source = previous_backup_path(path).read_bytes()
                self.interrupt_recovery_process(path, boundary)
                committed = boundary in boundaries[5:]
                self.assert_snapshot_matches(load_save(path, include_history=True), intended if committed else current)
                promoted = boundary in ("after_previous", "before_cleanup", "after_cleanup")
                self.assert_archive_matches(previous_backup_path(path).read_bytes(), current if promoted else intended)
                if not committed:
                    self.assertEqual(previous_backup_path(path).read_bytes(), source)
                if boundary != "after_cleanup":
                    # Retry in a fresh process so no in-memory state can assist.
                    environment = os.environ.copy()
                    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
                    retried = subprocess.run([sys.executable, "-c",
                        "import sys; from nba_gm_data.save_recovery import recover_previous_save; recover_previous_save(sys.argv[1])",
                        str(path)], env=environment, capture_output=True, timeout=30)
                    self.assertEqual(retried.returncode, 0, retried.stderr.decode())
                # After cleanup the transaction is complete, with B current and
                # A previous. A later new Recover Previous may intentionally undo it.
                self.assert_snapshot_matches(load_save(path, include_history=True), intended)
                self.assert_archive_matches(previous_backup_path(path).read_bytes(), current)
                self.assertFalse(pending_restore_path(path).exists())

    def test_write_after_interrupted_recovery_resolves_pending_backup_before_next_commit(self):
        path = self.directory / "resume.json"
        intended, current = self.seed_recovery_pair(path)
        self.interrupt_recovery_process(path, "after_manifest")
        self.assert_archive_matches(pending_restore_path(path).read_bytes(), current)
        next_save = load_save(path)
        next_save["marker"] = "C: subsequent update"
        write_save(path, next_save)
        self.assertEqual(load_save(path)["marker"], "C: subsequent update")
        self.assert_archive_matches(previous_backup_path(path).read_bytes(), intended)
        self.assertFalse(pending_restore_path(path).exists())

    def test_failed_backup_publication_leaves_both_components_unchanged(self):
        before = self.path.read_bytes()
        history = history_sidecar_path(self.path, load_save(self.path)).read_bytes()
        changed = load_save(self.path)
        changed["marker"] = "should not commit"
        with patch("nba_gm_data.save_recovery._write_archive", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                write_save(self.path, changed)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(history_sidecar_path(self.path, load_save(self.path)).read_bytes(), history)

    def test_export_after_interruption_excludes_abandoned_future_rows(self):
        from nba_gm_data import save as save_module

        changed = load_save(self.path)
        revision = changed["meta"]["save_revision"]
        changed["player_game_logs"] = [{"id": "never_committed", "points": 999}]
        with patch.object(save_module.json, "dump", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                write_save(self.path, changed)
        snapshot = self.directory / "checked_export.sqlite3"
        snapshot.write_bytes(archive_members(create_export(self.path))["history.sqlite3"])
        with closing(sqlite3.connect(snapshot)) as connection:
            self.assertEqual(connection.execute("SELECT MAX(revision) FROM history_commits").fetchone()[0], revision)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM history_records WHERE revision > ?", (revision,)).fetchone()[0], 0)
        with closing(sqlite3.connect(history_sidecar_path(self.path, changed))) as connection:
            self.assertEqual(connection.execute("SELECT MAX(revision) FROM history_commits").fetchone()[0], revision + 1)

    def test_json_only_legacy_export_restore_then_archive_does_not_adopt_old_history(self):
        legacy_path = self.directory / "legacy.json"
        legacy = fixture("legacy", count=0)
        legacy["meta"]["save_revision"] = 20
        legacy_path.write_text(json.dumps(legacy))
        exported = create_export(legacy_path)
        self.assertNotIn("history.sqlite3", archive_members(exported))
        restore_export(self.path, exported, replace=True)
        restored = load_save(self.path)
        restored["player_game_logs"] = [{"game_id": "new_game", "player_id": "new_player", "points": 42}]
        write_save(self.path, restored)
        hydrated = load_save(self.path, include_history=True)
        self.assertEqual(len(hydrated["player_game_logs"]), 1)
        self.assertEqual(hydrated["game_results"], [])

    def test_rejects_malformed_unsafe_and_incomplete_archives_before_replacing(self):
        members = archive_members(create_export(self.path))
        original = self.path.read_bytes()
        cases = [b"not a zip"]
        for name in ("../escape", "/absolute", "C:\\escape", "subdir/save.json", "save.json/extra"):
            cases.append(repack({**members, name: b"bad"}))
        cases.append(repack({key: value for key, value in members.items() if key != "history.sqlite3"}))
        cases.append(repack({**members, "save.json": b"[]"}))
        cases.append(repack({**members, "history.sqlite3": b"not sqlite"}))
        cases.append(repack({**members, "save.json": b"{}"}, checksums=False))
        # zipfile truncates filenames at NUL; the raw original name must be rejected.
        nul_members = {("save.jsonX" if name == "save.json" else name): data for name, data in members.items()}
        cases.append(repack(nul_members).replace(b"save.jsonX", b"save.json\x00"))
        duplicate = io.BytesIO()
        with zipfile.ZipFile(duplicate, "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr("save.json", members["save.json"])
        cases.append(duplicate.getvalue())
        symlink = io.BytesIO()
        with zipfile.ZipFile(symlink, "w") as archive:
            for name, data in members.items():
                info = zipfile.ZipInfo(name)
                if name == "history.sqlite3":
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, data)
        cases.append(symlink.getvalue())
        for archive in cases:
            with self.subTest(size=len(archive)):
                with self.assertRaises((SaveRecoveryError, SaveValidationError)):
                    restore_export(self.path, archive, replace=True)
                self.assertEqual(self.path.read_bytes(), original)

    def test_rejects_future_backup_save_and_history_formats(self):
        members = archive_members(create_export(self.path))
        metadata = json.loads(members["backup.json"])
        metadata["format"] = "nba_gm_backup_v999"
        cases = [repack({**members, "backup.json": json.dumps(metadata).encode()}, checksums=False)]
        for component in ("version", "history_store"):
            save = json.loads(members["save.json"])
            if component == "version":
                save["version"] = "league_save_v999"
            else:
                save["history_store"]["version"] = 999
            cases.append(repack({**members, "save.json": json.dumps(save).encode()}))
        for archive in cases:
            with self.assertRaisesRegex((SaveRecoveryError, SaveValidationError), "Unsupported"):
                restore_export(self.directory / "future.json", archive)
        self.assertFalse((self.directory / "future.json").exists())

    def test_unsafe_history_reference_is_rejected(self):
        members = archive_members(create_export(self.path))
        save = json.loads(members["save.json"])
        save["history_store"]["path"] = "../outside.sqlite3"
        with self.assertRaisesRegex(SaveValidationError, "unsafe"):
            restore_export(self.directory / "unsafe.json", repack({**members, "save.json": json.dumps(save).encode()}))

    def test_expanded_size_limit_is_checked_before_extracting(self):
        members = archive_members(create_export(self.path))
        with patch("nba_gm_data.save_recovery.MAX_EXPANDED_BYTES", 20):
            with self.assertRaisesRegex(SaveRecoveryError, "expanded size limit"):
                restore_export(self.directory / "too_large.json", repack(members))
        self.assertFalse((self.directory / "too_large.json").exists())

    def test_local_autosave_and_recovery_ignore_portable_upload_limits(self):
        from nba_gm_data import save_recovery as recovery

        before = load_save(self.path, include_history=True)
        changed = load_save(self.path)
        changed["marker"] = "large local career"
        with patch.object(recovery, "MAX_EXPANDED_BYTES", 1), patch.object(recovery, "MAX_ARCHIVE_BYTES", 1):
            write_save(self.path, changed)
            with self.assertRaises(SaveRecoveryError):
                create_export(self.path)
            recover_previous_save(self.path)
        self.assert_snapshot_matches(load_save(self.path, include_history=True), before)
        outgoing = self.directory / "outgoing.json"
        restore_export(outgoing, previous_backup_path(self.path).read_bytes())
        self.assertEqual(load_save(outgoing)["marker"], "large local career")

    def test_local_backup_and_recovery_never_buffer_history_or_archive_members(self):
        read_bytes, read_member = Path.read_bytes, zipfile.ZipFile.read

        def guarded_bytes(path):
            if path.suffix == ".sqlite3" or path.name.endswith(".nbagm.zip"):
                self.fail(f"Whole-file allocation for {path.name}")
            return read_bytes(path)

        def guarded_member(archive, name, *args, **kwargs):
            if name == "history.sqlite3":
                self.fail("Whole history-member allocation")
            return read_member(archive, name, *args, **kwargs)

        changed = load_save(self.path)
        changed["marker"] = "streamed"
        with patch.object(Path, "read_bytes", guarded_bytes), patch.object(zipfile.ZipFile, "read", guarded_member):
            write_save(self.path, changed)
            recover_previous_save(self.path)
        self.assertEqual(load_save(self.path)["marker"], "original")

    def test_failed_streamed_backup_publication_keeps_previous_archive(self):
        changed = load_save(self.path)
        write_save(self.path, changed)
        before = self.path.read_bytes()
        archive = previous_backup_path(self.path).read_bytes()
        replace = Path.replace

        def fail_previous(source, target):
            if Path(target) == previous_backup_path(self.path):
                raise OSError("backup publication interrupted")
            return replace(source, target)

        changed["marker"] = "must not commit"
        with patch.object(Path, "replace", fail_previous):
            with self.assertRaisesRegex(OSError, "interrupted"):
                write_save(self.path, changed)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(previous_backup_path(self.path).read_bytes(), archive)
        self.assertFalse(list(self.directory.glob(".*.tmp")))

    def test_local_recovery_remains_bounded_and_checks_disk_space(self):
        from nba_gm_data import save_recovery as recovery

        write_save(self.path, load_save(self.path))
        before = self.path.read_bytes()
        for name, value, message in (("MAX_LOCAL_EXPANDED_BYTES", 1, "expanded size limit"),
                                     ("MAX_LOCAL_ARCHIVE_BYTES", 1, "size limit"),
                                     ("MAX_METADATA_BYTES", 1, "metadata"),
                                     ("MAX_MANIFEST_BYTES", 1, "manifest")):
            with self.subTest(limit=name), patch.object(recovery, name, value):
                with self.assertRaisesRegex(SaveRecoveryError, message):
                    recover_previous_save(self.path)
                self.assertEqual(self.path.read_bytes(), before)
        usage = recovery.shutil.disk_usage(self.directory)
        with patch.object(recovery.shutil, "disk_usage", return_value=usage._replace(free=0)):
            with self.assertRaisesRegex(SaveRecoveryError, "disk space"):
                recover_previous_save(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_local_recovery_rejects_symlink_archive(self):
        archive = self.directory / "real.zip"
        archive.write_bytes(create_export(self.path))
        previous_backup_path(self.path).symlink_to(archive)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(SaveRecoveryError, "unsafe"):
            recover_previous_save(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_restore_api_round_trip_and_collision_error(self):
        canonical = {"teams": [{"id": "t1", "abbrev": "GSW", "name": "Warriors"}]}
        exported = app_actions.dispatch_app_action("export_save", {"save_path": str(self.path)}, root=self.directory, save_dir=self.directory, canonical=canonical)
        payload = {"save_name": "Imported Save", "archive_base64": exported["archive_base64"]}
        restored = app_actions.dispatch_app_action("restore_save", payload, root=self.directory, save_dir=self.directory, canonical=canonical)
        self.assertEqual(Path(restored["save_path"]).name, "imported_save.json")
        self.assertEqual(load_save(restored["save_path"])["marker"], "original")
        with self.assertRaises(SaveRecoveryError):
            app_actions.dispatch_app_action("restore_save", payload, root=self.directory, save_dir=self.directory, canonical=canonical)

    def test_http_recovery_actions_round_trip_and_return_actionable_validation_errors(self):
        from nba_gm_data.app_server import make_gui_server

        canonical = {"teams": [{"id": "t1", "abbrev": "GSW", "name": "Warriors"}]}
        with patch("nba_gm_data.app_server.load_app_canonical", return_value=canonical):
            server = make_gui_server(root=self.directory, save_dir=self.directory, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        with request.urlopen(f"http://127.0.0.1:{server.server_address[1]}/api/session", timeout=5) as response:
            token = json.load(response)["token"]

        def action(name, payload):
            req = request.Request(f"http://127.0.0.1:{server.server_address[1]}/api/action", data=json.dumps({"action": name, "payload": payload}).encode(), headers={"Content-Type": "application/json", "X-NBA-GM-Token": token, "X-NBA-GM-Backup-Upload": "1" if name == "restore_save" else "0"})
            with request.urlopen(req, timeout=10) as response:
                return json.load(response)["result"]

        try:
            exported = action("export_save", {"save_path": str(self.path)})
            restored = action("restore_save", {"save_name": "HTTP Roundtrip", "archive_base64": exported["archive_base64"]})
            self.assertEqual(len(load_save(restored["save_path"], include_history=True)["game_results"]), 15)
            with self.assertRaises(error.HTTPError) as failure:
                action("restore_save", {"save_name": "Malformed", "archive_base64": "bm90LXppcA=="})
            self.assertEqual(failure.exception.code, 400)
            response = json.load(failure.exception)
            failure.exception.close()
            self.assertIn("Choose an intact NBA GM backup", response["error"])
            updated = load_save(self.path)
            updated["marker"] = "updated"
            write_save(self.path, updated)
            history_sidecar_path(self.path, updated).unlink()
            rows = action("list_saves", {})["saves"]
            damaged = next(row for row in rows if Path(row["path"]).resolve() == self.path.resolve())
            self.assertEqual(damaged["status"], "unreadable")
            self.assertTrue(damaged["recovery_available"])
            action("recover_save", {"save_path": str(self.path)})
            self.assertEqual(load_save(self.path)["marker"], "original")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(5)


if __name__ == "__main__":
    unittest.main()
