"""Indexed append-only history storage for mature league saves.

The JSON manifest remains the authoritative hot state. SQLite rows carry the
same revision and are visible only when that revision has reached the manifest,
so an interrupted write cannot expose history from an uncommitted save.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any


HISTORY_VERSION = 2
ALWAYS_ARCHIVED = {"game_results", "player_game_logs"}
COLD_ARCHIVED = {
    "transaction_logs",
    "news_items",
    "social_feed",
    "league_events",
    "development_events",
    "team_game_logs",
}
HISTORY_KEYS = tuple(sorted(ALWAYS_ARCHIVED | COLD_ARCHIVED))
HOT_TAIL_LIMITS = {
    # A handful of recent full box scores keeps common post-game reads cheap
    # without allowing the multi-season manifest to grow without bound.
    "game_results": 10,
    # Recent transaction and narrative rows are small, frequently inspected,
    # and still participate in live rules such as recently-traded eligibility.
    **{kind: 100 for kind in COLD_ARCHIVED},
}


class SaveValidationError(ValueError):
    """A save component is absent, damaged, or unsupported."""


def history_sidecar_path(save_path: str | Path, save: dict[str, Any] | None = None) -> Path:
    path = Path(save_path)
    name = ((save or {}).get("history_store") or {}).get("path")
    if name is None:
        name = path.with_suffix(".history.sqlite3").name
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or "/" in name or "\\" in name or ":" in name or "\0" in name
            or not name.endswith(".sqlite3")):
        raise SaveValidationError("The save has an unsafe history filename. Restore a complete save export.")
    database = path.parent / name
    if database.is_symlink():
        raise SaveValidationError("The history component is a symbolic link. Restore a complete save export.")
    return database


def migration_backup_path(save_path: str | Path) -> Path:
    path = Path(save_path)
    return path.with_name(f"{path.name}.pre-history-v1.bak")


def _read_connection(path: Path) -> sqlite3.Connection:
    # mode=ro never creates a missing sidecar or changes its journal/schema.
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=30.0)


def _versioned(connection: sqlite3.Connection) -> bool:
    columns = connection.execute("PRAGMA table_info(history_records)").fetchall()
    required = {"kind", "record_id", "event_date", "season", "revision", "game_id", "player_id", "team_id", "payload_json"}
    if not required.issubset({row[1] for row in columns}):
        raise SaveValidationError("The history database has an incompatible schema. Restore a complete save export.")
    primary = {row[1] for row in columns if row[5]}
    if primary not in ({"kind", "record_id"}, {"kind", "record_id", "revision"}):
        raise SaveValidationError("The history database has an unsupported record format. Restore a complete save export.")
    return "revision" in primary


def _visible_sql(versioned: bool, alias: str = "h") -> str:
    if not versioned:
        return ""
    return f""" AND {alias}.revision = (SELECT MAX(v.revision) FROM history_records v
        WHERE v.kind={alias}.kind AND v.record_id={alias}.record_id AND v.revision<=?)"""


def _visible_counts(connection: sqlite3.Connection, revision: int, versioned: bool = True) -> dict[str, int]:
    if versioned:
        # Inventory needs one key per visible record, not its newest payload.
        # Group the covering primary-key index once instead of a MAX lookup
        # for every historical version. NULL keys cannot match the old lookup.
        sql = """SELECT kind, COUNT(*) FROM (
            SELECT kind, record_id FROM history_records
            WHERE revision<=? AND kind IS NOT NULL AND record_id IS NOT NULL
            GROUP BY kind, record_id
        ) GROUP BY kind"""
    else:
        sql = "SELECT kind, COUNT(*) FROM history_records WHERE revision<=? GROUP BY kind"
    return dict(connection.execute(sql, [revision]).fetchall())


# History files that passed the full check, keyed by path, with the file state and the JSON metadata they
# passed with. The integrity scan reads the whole database (hundreds of MB after several seasons) and an
# advance validates many times, so an unchanged file that already passed is not rescanned.
_VALIDATED: dict[str, tuple] = {}


def _file_state(path: Path) -> tuple:
    out = []
    for candidate in (path, path.with_name(path.name + "-wal")):
        try:
            stat = candidate.stat()
            out.append((stat.st_ino, stat.st_size, stat.st_mtime_ns))
        except OSError:
            out.append(None)
    return tuple(out)


def validate_save_components(save_path: str | Path, save: dict[str, Any]) -> None:
    """Validate required history without creating, repairing, or migrating it."""
    store = save.get("history_store")
    if store is None:
        return  # Older saves keep their complete history in the JSON document.
    if not isinstance(store, dict):
        raise SaveValidationError("The save's history metadata is malformed. Restore a complete save export.")
    version = store.get("version")
    if type(version) is not int or version not in (1, HISTORY_VERSION):
        raise SaveValidationError(f"Unsupported history format {version!r}. Use a compatible app version or restore a supported export.")
    revision = store.get("revision")
    if type(revision) is not int or revision <= 0 or revision != save.get("meta", {}).get("save_revision"):
        raise SaveValidationError("The JSON and history revisions do not match. Restore a complete save export.")
    declared_counts = store.get("archived_counts")
    if not isinstance(declared_counts, dict) or any(
        not isinstance(kind, str) or type(count) is not int or count < 0
        for kind, count in declared_counts.items()
    ):
        raise SaveValidationError("The save's archived history inventory is malformed. Restore a complete save export.")
    database = history_sidecar_path(save_path, save)
    if not database.is_file():
        raise SaveValidationError(f"Required history file '{database.name}' is missing. Keep the JSON and history together, or restore a complete save export.")
    fingerprint = (version, revision, store.get("snapshot_id"), json.dumps(declared_counts, sort_keys=True), _file_state(database))
    if _VALIDATED.get(str(database)) == fingerprint:
        return
    try:
        with closing(_read_connection(database)) as connection:
            # A transaction gives all integrity/checkpoint checks one DB snapshot.
            connection.execute("BEGIN")
            db_version = connection.execute("PRAGMA user_version").fetchone()[0]
            if db_version not in (0, 1, HISTORY_VERSION):
                raise SaveValidationError(f"Unsupported history database format {db_version}. Use a compatible app version.")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise SaveValidationError("The history database is corrupt. Restore a complete save export.")
            versioned = _versioned(connection)
            counts = _visible_counts(connection, revision, versioned)
            if version == HISTORY_VERSION:
                if not versioned or not isinstance(store.get("snapshot_id"), str):
                    raise SaveValidationError("The history checkpoint is incompatible. Restore a complete save export.")
                checkpoint = connection.execute("SELECT snapshot_id, counts_json FROM history_commits WHERE revision=?", (revision,)).fetchone()
                if (checkpoint is None or checkpoint[0] != store["snapshot_id"]
                        or json.loads(checkpoint[1]) != counts or declared_counts != counts):
                    raise SaveValidationError("The JSON and history components are incomplete or belong to different snapshots. Restore a complete save export.")
            elif any(count > declared_counts.get(kind, 0) for kind, count in counts.items()) or any(
                count > 0 and counts.get(kind, 0) == 0 for kind, count in declared_counts.items()
            ):
                # The v1 writer counted repeated UPSERTs, so its inventory may
                # overestimate rows. Still reject entirely missing categories.
                raise SaveValidationError("The legacy history component is incomplete. Restore a complete save export.")
            bad = connection.execute("SELECT 1 FROM history_records WHERE revision<=? AND (NOT json_valid(payload_json) OR json_type(payload_json) != 'object') LIMIT 1", (revision,)).fetchone()
            if bad:
                raise SaveValidationError("A historical record is corrupt. Restore a complete save export.")
        if _file_state(database) == fingerprint[-1]:
            _VALIDATED[str(database)] = fingerprint
    except SaveValidationError:
        raise
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        raise SaveValidationError(f"Cannot read history file '{database.name}': {exc}. Restore a complete save export.") from exc


def connect_history(path: Path) -> sqlite3.Connection:
    """Open the writer; schema changes are transactional, preserving old reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30.0)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='history_records'").fetchone()
        legacy = bool(exists and not _versioned(connection))
        if legacy:
            connection.execute("ALTER TABLE history_records RENAME TO history_records_legacy")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS history_records (
                kind TEXT NOT NULL, record_id TEXT NOT NULL, event_date TEXT,
                season TEXT, revision INTEGER NOT NULL, game_id TEXT,
                player_id TEXT, team_id TEXT, payload_json TEXT NOT NULL,
                PRIMARY KEY (kind, record_id, revision)
            )
        """)
        if legacy:
            connection.execute("INSERT INTO history_records SELECT kind, record_id, event_date, season, revision, game_id, player_id, team_id, payload_json FROM history_records_legacy")
            connection.execute("DROP TABLE history_records_legacy")
        connection.execute("CREATE TABLE IF NOT EXISTS history_commits (revision INTEGER PRIMARY KEY, snapshot_id TEXT NOT NULL, counts_json TEXT NOT NULL)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_history_kind_date ON history_records(kind, event_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_history_player_date ON history_records(kind, player_id, event_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_history_game ON history_records(kind, game_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_history_revision ON history_records(revision)")
        connection.execute(f"PRAGMA user_version={HISTORY_VERSION}")
        return connection
    except BaseException:
        connection.close()
        raise


def archive_save_history(save_path: str | Path, save: dict[str, Any], revision: int) -> dict[str, int]:
    """Stage versioned history before publishing the corresponding JSON manifest.

    The caller holds save_lock. Rows from an interrupted newer revision are
    discarded before a retry, while prior versions stay readable until publish.
    """
    path = Path(save_path)
    current_floor = active_season_floor(save)
    moved: dict[str, list[dict[str, Any]]] = {}
    retained: dict[str, list[dict[str, Any]]] = {}
    forced = save.pop("_history_to_archive", {})
    for kind in HISTORY_KEYS:
        rows = [row for row in save.get(kind, []) if isinstance(row, dict)]
        if kind in ALWAYS_ARCHIVED:
            eligible = rows
        else:
            eligible = [row for row in rows if record_date(row) and record_date(row) < current_floor]
        hot_limit = max(0, int(HOT_TAIL_LIMITS.get(kind) or 0))
        hot_ids = {
            record_id(kind, row)
            for row in sorted(eligible, key=lambda row: (record_date(row), record_id(kind, row)))[-hot_limit:]
        } if hot_limit else set()
        forced_rows = [row for row in forced.get(kind, []) if isinstance(row, dict)]
        combined = {record_id(kind, row): row for row in eligible if record_id(kind, row) not in hot_ids}
        combined.update({record_id(kind, row): row for row in forced_rows})
        moved[kind] = list(combined.values())
        moved_ids = set(combined)
        retained[kind] = [row for row in rows if record_id(kind, row) not in moved_ids]
    counts = {kind: len(rows) for kind, rows in moved.items() if rows}
    if not counts and not save.get("history_store"):
        save.setdefault("meta", {})["save_revision"] = int(revision)
        return {}

    if path.exists() and not (save.get("history_store") or {}).get("version"):
        backup = migration_backup_path(path)
        if not backup.exists():
            shutil.copy2(path, backup)

    database = history_sidecar_path(path, save)
    if not save.get("history_store") and database.exists():
        # An unreferenced DB may belong to an older restored save, or to an
        # interrupted first migration. Never adopt its rows into this manifest.
        database = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.history.sqlite3")
    snapshot_id = uuid.uuid4().hex
    with closing(connect_history(database)) as connection, connection:
        # `revision` is allocated from the on-disk manifest while holding lock.
        connection.execute("DELETE FROM history_records WHERE revision>=?", (revision,))
        connection.execute("DELETE FROM history_commits WHERE revision>=?", (revision,))
        for kind, rows in moved.items():
            for row in rows:
                connection.execute("""
                    INSERT INTO history_records
                        (kind, record_id, event_date, season, revision, game_id, player_id, team_id, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    kind, record_id(kind, row), record_date(row), record_season(row), int(revision),
                    string_or_none(row.get("game_id") or row.get("externalGameId")),
                    string_or_none(row.get("player_id")), string_or_none(row.get("team_id")),
                    json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                ))
        archived_counts = _visible_counts(connection, revision)
        connection.execute("INSERT INTO history_commits VALUES (?, ?, ?)", (revision, snapshot_id, json.dumps(archived_counts, sort_keys=True)))

    for kind, rows in retained.items():
        save[kind] = rows
    materialize_game_summaries(save, moved.get("game_results", []), moved.get("team_game_logs", []))
    materialize_development_totals(save, moved.get("development_events", []))
    save["history_store"] = {
        "version": HISTORY_VERSION, "path": database.name, "revision": int(revision),
        "snapshot_id": snapshot_id, "archived_counts": archived_counts,
    }
    save.setdefault("meta", {})["save_revision"] = int(revision)
    return counts


def materialize_game_summaries(save: dict[str, Any], rows: list[dict[str, Any]], archived_team_logs: list[dict[str, Any]] | None = None) -> None:
    summaries = {
        str(row.get("game_id")): row
        for row in save.get("game_result_summaries", [])
        if row.get("game_id")
    }
    dates = {
        str(row.get("game_id")): row.get("date")
        for row in [*save.get("team_game_logs", []), *(archived_team_logs or [])]
        if row.get("game_id") and row.get("date")
    }
    for row in rows:
        game_id = str(row.get("game_id") or "")
        if not game_id:
            continue
        summaries[game_id] = {
            "game_id": game_id,
            "date": dates.get(game_id) or summaries.get(game_id, {}).get("date"),
            "away_team_id": row.get("away_team_id"),
            "home_team_id": row.get("home_team_id"),
            "away_score": row.get("away_score"),
            "home_score": row.get("home_score"),
            "overtime_periods": max(
                [int(line.get("overtime_periods") or 0) for line in row.get("team_lines", [])],
                default=0,
            ),
        }
    save["game_result_summaries"] = sorted(summaries.values(), key=lambda row: (str(row.get("date") or ""), str(row.get("game_id") or "")))


def materialize_development_totals(save: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    totals = save.setdefault("development_trait_totals", {})
    for row in rows:
        player_id = row.get("player_id")
        if not player_id:
            continue
        player_totals = totals.setdefault(str(player_id), {})
        for key, delta in (row.get("trait_deltas") or {}).items():
            player_totals[str(key)] = round(float(player_totals.get(str(key)) or 0.0) + float(delta or 0.0), 6)


def load_history_records(
    save_path: str | Path,
    save: dict[str, Any],
    kind: str,
    *,
    player_id: str | None = None,
    game_id: str | None = None,
    limit: int | None = None,
    event_date_from: str | None = None,
    _validated: bool = False,
) -> list[dict[str, Any]]:
    store = save.get("history_store")
    if store is None:
        return []
    if not _validated:
        validate_save_components(save_path, save)
    manifest_revision = int(store["revision"])
    database = history_sidecar_path(save_path, save)
    try:
        with closing(_read_connection(database)) as connection:
            versioned = _versioned(connection)
            clauses = ["h.kind = ?", "h.revision <= ?"]
            values: list[Any] = [kind, manifest_revision]
            if player_id is not None:
                clauses.append("h.player_id = ?")
                values.append(str(player_id))
            if game_id is not None:
                clauses.append("h.game_id = ?")
                values.append(str(game_id))
            if event_date_from is not None:
                clauses.append("h.event_date >= ?")
                values.append(str(event_date_from))
            sql = f"SELECT h.payload_json FROM history_records h WHERE {' AND '.join(clauses)}" + _visible_sql(versioned)
            if versioned:
                values.append(manifest_revision)
            if limit is None:
                # Decode as rows arrive rather than retaining a second full
                # history as raw JSON strings alongside the decoded records.
                sql += " ORDER BY h.event_date ASC, h.record_id ASC"
                return [json.loads(row[0]) for row in connection.execute(sql, values)]
            sql += " ORDER BY h.event_date DESC, h.record_id DESC LIMIT ?"
            values.append(max(0, int(limit)))
            rows = connection.execute(sql, values).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        raise SaveValidationError(f"Cannot read historical records: {exc}. Restore a complete save export.") from exc


def hydrate_save_history(save_path: str | Path, save: dict[str, Any], *, _validated: bool = False) -> dict[str, Any]:
    """Compatibility loader for audits, exports, and historical CLI views."""
    if not _validated:
        validate_save_components(save_path, save)
    for kind in HISTORY_KEYS:
        archived = load_history_records(save_path, save, kind, _validated=True)
        if not archived:
            continue
        combined = {record_id(kind, row): row for row in archived}
        combined.update({record_id(kind, row): row for row in save.get(kind, []) if isinstance(row, dict)})
        save[kind] = sorted(combined.values(), key=lambda row: (record_date(row), record_id(kind, row)))
    return save


def active_season_floor(save: dict[str, Any]) -> str:
    season = str((save.get("meta") or {}).get("season") or "2025-26")
    try:
        year = int(season.split("-")[0])
    except (TypeError, ValueError):
        year = 2025
    return f"{year}-07-01"


def record_date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("start_date") or row.get("month") or "")[:10]


def record_season(row: dict[str, Any]) -> str | None:
    value = row.get("season") or row.get("month") or row.get("date") or row.get("start_date")
    return string_or_none(value)


def record_id(kind: str, row: dict[str, Any]) -> str:
    explicit = row.get("id")
    if explicit:
        return str(explicit)
    pieces = [kind, row.get("game_id"), row.get("player_id"), row.get("team_id"), record_date(row)]
    return ":".join(str(piece or "") for piece in pieces)


def string_or_none(value: Any) -> str | None:
    return str(value) if value not in {None, ""} else None
