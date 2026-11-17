"""Inventory and streamed reads retain version, ordering and corruption checks."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import random
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nba_gm_data import history_store as hs, save as sv


def reference_counts(connection, revision, versioned=True):
    sql = "SELECT h.kind, COUNT(*) FROM history_records h WHERE h.revision<=?" + hs._visible_sql(versioned) + " GROUP BY h.kind"
    return dict(connection.execute(sql, [revision, revision] if versioned else [revision]).fetchall())


def reference_records(path, saved, kind, **filters):
    with closing(hs._read_connection(hs.history_sidecar_path(path, saved))) as connection:
        versioned = hs._versioned(connection)
        revision = saved["history_store"]["revision"]
        clauses, values = ["h.kind = ?", "h.revision <= ?"], [kind, revision]
        for key in ("player_id", "game_id"):
            if filters.get(key) is not None:
                clauses.append(f"h.{key} = ?")
                values.append(filters[key])
        sql = f"SELECT h.payload_json FROM history_records h WHERE {' AND '.join(clauses)}" + hs._visible_sql(versioned)
        if versioned:
            values.append(revision)
        sql += " ORDER BY h.event_date DESC, h.record_id DESC"
        if filters.get("limit") is not None:
            sql += " LIMIT ?"
            values.append(max(0, filters["limit"]))
        return [json.loads(row[0]) for row in reversed(connection.execute(sql, values).fetchall())]


class HistoryPerformanceTests(unittest.TestCase):
    def fixture(self, directory):
        path = Path(directory) / "disposable.json"
        saved = {"version": "league_save_v1", "meta": {"season": "2025-26"},
                 "player_game_logs": [{"id": f"log{i:02}", "player_id": f"p{i % 3}",
                    "game_id": f"g{i % 4}", "date": None if i == 0 else f"2025-10-{i % 9 + 1:02}", "points": i}
                    for i in range(30)]}
        sv.write_save(path, saved)
        first = deepcopy(saved)
        saved["player_game_logs"] = [{"id": "log01", "player_id": "p2", "game_id": "new-game", "date": "2025-11-02", "points": 99}]
        sv.write_save(path, saved)
        return path, first, saved

    def test_versioned_counts_equal_correlated_reference_across_cutoffs(self):
        rng = random.Random(17)
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE history_records(kind TEXT, record_id TEXT, revision INTEGER, PRIMARY KEY(kind,record_id,revision))")
            connection.executemany("INSERT OR REPLACE INTO history_records VALUES(?,?,?)",
                [(rng.choice(["games", "logs", "events"]), str(rng.randrange(100)), rng.randrange(1, 20)) for _ in range(2000)])
            connection.executemany("INSERT INTO history_records VALUES(?,?,?)", [(None, "null-kind", 1), ("games", None, 1)])
            for revision in range(22):
                self.assertEqual(hs._visible_counts(connection, revision), reference_counts(connection, revision))

    def test_legacy_counts_are_unchanged(self):
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE history_records(kind TEXT, record_id TEXT, revision INTEGER, PRIMARY KEY(kind,record_id))")
            connection.executemany("INSERT INTO history_records VALUES(?,?,?)", [("games", "a", 1), ("games", "b", 3), ("logs", "c", 2)])
            for revision in range(5):
                self.assertEqual(hs._visible_counts(connection, revision, False), reference_counts(connection, revision, False))

    def test_stream_and_limited_reads_match_old_order_filters_and_revisions(self):
        with TemporaryDirectory() as directory:
            path, first, latest = self.fixture(directory)
            for saved in (first, latest):
                for filters in ({}, {"player_id": "p1"}, {"player_id": "p2"}, {"game_id": "g1"},
                                {"limit": 0}, {"limit": -1}, {"limit": 5}, {"limit": 999},
                                {"player_id": "p1", "limit": 5}):
                    with self.subTest(revision=saved["history_store"]["revision"], filters=filters):
                        self.assertEqual(hs.load_history_records(path, saved, "player_game_logs", **filters),
                                         reference_records(path, saved, "player_game_logs", **filters))

    def test_unlimited_reads_do_not_fetch_all_raw_payloads(self):
        with TemporaryDirectory() as directory:
            path, _, saved = self.fixture(directory)
            original = hs._read_connection

            class Connection:
                def __init__(self, database):
                    self.connection = original(database)

                def execute(self, sql, *args):
                    cursor = self.connection.execute(sql, *args)
                    if sql.startswith("SELECT h.payload_json"):
                        class Cursor:
                            def __iter__(self):
                                return iter(cursor)

                            def fetchall(self):
                                raise AssertionError("Full raw payload buffering returned")
                        return Cursor()
                    return cursor

                def close(self):
                    self.connection.close()

            expected = reference_records(path, saved, "player_game_logs")
            with patch.object(hs, "_read_connection", side_effect=Connection):
                self.assertEqual(hs.load_history_records(path, saved, "player_game_logs", _validated=True), expected)

    def test_every_read_still_checks_integrity_and_payload_corruption(self):
        with TemporaryDirectory() as directory:
            path, _, saved = self.fixture(directory)
            statements = []
            original = hs._read_connection

            def traced(database):
                connection = original(database)
                connection.set_trace_callback(statements.append)
                return connection

            with patch.object(hs, "_read_connection", side_effect=traced):
                sv.load_save(path)
                sv.load_save(path)
            self.assertEqual(sum("PRAGMA quick_check" in sql for sql in statements), 2)
            self.assertEqual(sum("NOT json_valid" in sql for sql in statements), 2)
            with sqlite3.connect(hs.history_sidecar_path(path, saved)) as connection:
                connection.execute("UPDATE history_records SET payload_json='broken'")
            with self.assertRaises(hs.SaveValidationError):
                sv.load_save(path)

    def test_validation_keeps_one_sqlite_snapshot_during_concurrent_wal_commit(self):
        with TemporaryDirectory() as directory:
            path, _, saved = self.fixture(directory)
            original = hs._read_connection
            fired = []

            def traced(database):
                connection = original(database)

                def commit_during_counts(sql):
                    if fired or "COUNT(*)" not in sql:
                        return
                    fired.append(True)
                    with sqlite3.connect(database) as writer:
                        writer.execute("INSERT INTO history_records SELECT kind,'foreign-row',event_date,season,revision,game_id,player_id,team_id,payload_json FROM history_records LIMIT 1")

                connection.set_trace_callback(commit_during_counts)
                return connection

            with patch.object(hs, "_read_connection", side_effect=traced):
                hs.validate_save_components(path, saved)
            self.assertTrue(fired)
            with self.assertRaisesRegex(hs.SaveValidationError, "different snapshots"):
                hs.validate_save_components(path, saved)


if __name__ == "__main__":
    unittest.main()
