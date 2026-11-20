"""Authoritative multiplayer coordination above the existing game engine.

The simulation remains a single Python rules engine and a league save remains
the snapshot it already is.  This module owns the distributed concerns that do
not belong in basketball logic: lobby membership, authentication, atomic team
claims, optimistic revisions, idempotent requests, shared clocks, and the
persistent human-action feed.

SQLite is deliberately the first storage backend.  It gives local/LAN testing
real transactions without adding a dependency.  The schema and service API are
kept narrow so a hosted Postgres adapter can replace it without moving game
rules into the client.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from .app_actions import MUTATING_ACTIONS
from .fantasy_draft import (
    fantasy_draft_current_team_id,
    simulate_fantasy_draft_until_human,
)
from .save import ensure_league_save_defaults, human_controlled_team_ids, load_save, season_start_year_from_date, trade_deadline_date, write_save
from .schema import CANONICAL_START_DATE, to_plain


MULTIPLAYER_PROTOCOL_VERSION = "multiplayer_v1"
LOBBY_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
DEFAULT_MULTIPLAYER_DB = ".multiplayer.sqlite3"

DEFAULT_LEAGUE_SETTINGS = {
    "season_count": 3,
    "advance_step": "month",
    "action_window_seconds": 300,
    "draft_pick_seconds": 90,
    "free_agency_round_seconds": 120,
    "fantasy_pick_seconds": 90,
    "game_mode": "standard",
    "ready_up_enabled": True,
}

ADVANCE_STEPS = {"week", "month"}
GLOBAL_CLOCK_ACTIONS = {
    "advance_save",
    "advance_free_agency",
    "draft_sim_all",
    "draft_sim_to_user",
    "process_ai_actions",
    "simulate_playoff_all",
    "simulate_playoff_game",
    "simulate_playoff_round",
}
TEAM_MUTATIONS = {
    "set_team_block",
    "set_team_wants",
    "acknowledge_team_wants",
    "apply_contract",
    "apply_trade",
    "apply_trade_candidate",
    "draft_apply_current",
    "fantasy_draft_pick",
    "fantasy_draft_watchlist",
    "fire_staff",
    "hire_staff",
    "negotiate_staff",
    "respond_user_trade_offer",
    "resolve_staff_retention",
    "set_rotation_minutes",
    "set_starting_five",
    "submit_free_agent_offer",
    "renounce_cap_hold",
    "waive_player",
}
HOST_MUTATIONS = {
    "update_game_settings",
}
TEAM_DEFAULT_ACTIONS = {
    "dashboard_trends",
    "draft_board",
    "fantasy_draft_watchlist",
    "draft_room",
    "fantasy_draft_room",
    "free_agents",
    "free_agency_room",
    "free_agent_offer_quote",
    "morale",
    "social_feed",
    "staff_market",
    "staff_room",
    "team_assets",
    "team_dashboard",
}
LEGACY_ACTOR_READ_ACTIONS = {
    # These reports still infer the viewing team from save.meta.user_team_id.
    # The compatibility wrapper supplies the requesting manager's team while
    # preserving the shared save's canonical host identity afterward.
    "calendar",
    "roster_cutdown",
}


class MultiplayerError(ValueError):
    """Base error returned to multiplayer clients."""


class MultiplayerAuthenticationError(MultiplayerError):
    pass


class MultiplayerAuthorizationError(MultiplayerError):
    pass


class MultiplayerConflictError(MultiplayerError):
    def __init__(self, message: str, current_revision: int):
        super().__init__(message)
        self.current_revision = int(current_revision)


class MultiplayerNotFoundError(MultiplayerError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_timestamp(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def normalize_settings(settings: dict[str, Any] | None, base: dict[str, Any] | None = None) -> dict[str, Any]:
    output = {**DEFAULT_LEAGUE_SETTINGS, **(base or {}), **(settings or {})}
    output["season_count"] = max(1, min(20, int(output["season_count"])))
    output["advance_step"] = str(output["advance_step"]).lower()
    if output["advance_step"] not in ADVANCE_STEPS:
        raise MultiplayerError("advance_step must be 'week' or 'month'.")
    output["action_window_seconds"] = max(5, min(86_400, int(output["action_window_seconds"])))
    output["draft_pick_seconds"] = max(15, min(900, int(output["draft_pick_seconds"])))
    output["free_agency_round_seconds"] = max(15, min(1_800, int(output["free_agency_round_seconds"])))
    output["fantasy_pick_seconds"] = max(15, min(900, int(output["fantasy_pick_seconds"])))
    output["game_mode"] = "fantasy_draft" if str(output.get("game_mode") or "").lower() == "fantasy_draft" else "standard"
    output["ready_up_enabled"] = bool(output["ready_up_enabled"])
    return output


def phase_clock_kind(phase: str | None) -> str:
    phase = str(phase or "")
    if phase == "draft":
        return "draft_pick"
    if phase == "fantasy_draft":
        return "fantasy_pick"
    if phase == "free_agency":
        return "free_agency_round"
    if phase in {"play_in", "playoffs"}:
        return "playoff_game"
    return "action_window"


def clock_duration(settings: dict[str, Any], kind: str) -> int:
    if kind == "draft_pick":
        return int(settings["draft_pick_seconds"])
    if kind == "fantasy_pick":
        return int(settings["fantasy_pick_seconds"])
    if kind == "free_agency_round":
        return int(settings["free_agency_round_seconds"])
    return int(settings["action_window_seconds"])


def make_clock(
    settings: dict[str, Any],
    phase: str | None,
    *,
    now: datetime | None = None,
    sequence: int = 1,
) -> dict[str, Any]:
    now = now or utc_now()
    kind = phase_clock_kind(phase)
    duration = clock_duration(settings, kind)
    return {
        "kind": kind,
        "phase": phase,
        "sequence": int(sequence),
        "opened_at": iso_timestamp(now),
        "deadline_at": iso_timestamp(now + timedelta(seconds=duration)),
        "duration_seconds": duration,
        "paused": False,
        "pause_reason": None,
        "extension_used": False,
    }


class MultiplayerStore:
    """Transactional SQLite persistence for multiplayer coordination state."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._schema_lock = threading.Lock()
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=60.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 60000")
        return connection

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def ensure_schema(self) -> None:
        with self._schema_lock:
            connection = self.connect()
            try:
                # WAL is a database-level setting. Reissuing it on every request
                # attempts a journal-mode write and creates avoidable contention
                # between read polling, user mutations, and the phase scheduler.
                connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS leagues (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    host_manager_id TEXT,
                    save_path TEXT,
                    revision INTEGER NOT NULL DEFAULT 0,
                    settings_json TEXT NOT NULL,
                    clock_json TEXT NOT NULL DEFAULT '{}',
                    winner_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS managers (
                    id TEXT PRIMARY KEY,
                    league_id TEXT NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
                    display_name TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    team_id TEXT,
                    ready INTEGER NOT NULL DEFAULT 0,
                    joined_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS managers_unique_team
                    ON managers(league_id, team_id)
                    WHERE team_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS managers_by_league
                    ON managers(league_id, joined_at);

                CREATE TABLE IF NOT EXISTS league_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    league_id TEXT NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
                    revision INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    actor_manager_id TEXT,
                    actor_team_id TEXT,
                    payload_json TEXT NOT NULL,
                    important INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_by_league_sequence
                    ON league_events(league_id, sequence);

                CREATE TABLE IF NOT EXISTS idempotent_responses (
                    league_id TEXT NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
                    manager_id TEXT NOT NULL REFERENCES managers(id) ON DELETE CASCADE,
                    idempotency_key TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (league_id, manager_id, idempotency_key)
                );

                CREATE TABLE IF NOT EXISTS human_trade_offers (
                    id TEXT PRIMARY KEY,
                    league_id TEXT NOT NULL REFERENCES leagues(id) ON DELETE CASCADE,
                    proposer_manager_id TEXT NOT NULL REFERENCES managers(id) ON DELETE CASCADE,
                    recipient_manager_id TEXT NOT NULL REFERENCES managers(id) ON DELETE CASCADE,
                    proposer_team_id TEXT NOT NULL,
                    recipient_team_id TEXT NOT NULL,
                    candidate_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_revision INTEGER NOT NULL,
                    resolved_revision INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS human_trade_offers_recipient
                    ON human_trade_offers(league_id, recipient_manager_id, status, created_at);
                """
                )
            finally:
                connection.close()

    def create_lobby(
        self,
        name: str,
        host_name: str,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        league_id = f"league_{uuid.uuid4().hex}"
        manager_id = f"manager_{uuid.uuid4().hex}"
        token = secrets.token_urlsafe(32)
        now = iso_timestamp()
        normalized = normalize_settings(settings)
        with self.transaction(immediate=True) as connection:
            code = self._unique_code(connection)
            connection.execute(
                """
                INSERT INTO leagues
                    (id, code, name, status, host_manager_id, revision, settings_json, clock_json, created_at, updated_at)
                VALUES (?, ?, ?, 'lobby', ?, 0, ?, '{}', ?, ?)
                """,
                (
                    league_id,
                    code,
                    clean_label(name, "New Multiplayer League", 64),
                    manager_id,
                    json.dumps(normalized, sort_keys=True),
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO managers
                    (id, league_id, display_name, token_hash, team_id, ready, joined_at, last_seen)
                VALUES (?, ?, ?, ?, NULL, 0, ?, ?)
                """,
                (manager_id, league_id, clean_label(host_name, "Commissioner", 32), token_hash(token), now, now),
            )
            self._insert_event(
                connection,
                league_id,
                0,
                "lobby_created",
                manager_id,
                None,
                {"league_name": clean_label(name, "New Multiplayer League", 64), "code": code},
                important=True,
            )
            state = self._league_state(connection, league_id)
        return {"session_token": token, "manager_id": manager_id, "league": state}

    def join_lobby(self, code: str, display_name: str) -> dict[str, Any]:
        manager_id = f"manager_{uuid.uuid4().hex}"
        token = secrets.token_urlsafe(32)
        now = iso_timestamp()
        with self.transaction(immediate=True) as connection:
            league = self._league_row_by_code(connection, code)
            if league["status"] != "lobby":
                raise MultiplayerError("This league has already started.")
            manager_count = connection.execute(
                "SELECT COUNT(*) AS count FROM managers WHERE league_id = ?",
                (league["id"],),
            ).fetchone()["count"]
            if int(manager_count) >= 30:
                raise MultiplayerError("This league already has the maximum of 30 human managers.")
            revision = int(league["revision"]) + 1
            connection.execute(
                """
                INSERT INTO managers
                    (id, league_id, display_name, token_hash, team_id, ready, joined_at, last_seen)
                VALUES (?, ?, ?, ?, NULL, 0, ?, ?)
                """,
                (manager_id, league["id"], clean_label(display_name, "Guest GM", 32), token_hash(token), now, now),
            )
            self._set_revision(connection, league["id"], revision, now)
            self._insert_event(
                connection,
                league["id"],
                revision,
                "manager_joined",
                manager_id,
                None,
                {"display_name": clean_label(display_name, "Guest GM", 32)},
                important=True,
            )
            state = self._league_state(connection, league["id"])
        return {"session_token": token, "manager_id": manager_id, "league": state}

    def authenticate(
        self,
        connection: sqlite3.Connection,
        league_id: str,
        manager_id: str,
        token: str,
    ) -> sqlite3.Row:
        manager = connection.execute(
            "SELECT * FROM managers WHERE id = ? AND league_id = ?",
            (manager_id, league_id),
        ).fetchone()
        if not manager or not secrets.compare_digest(str(manager["token_hash"]), token_hash(token)):
            raise MultiplayerAuthenticationError("Invalid multiplayer session.")
        # Authentication is also used by high-frequency state/event reads.
        # Keep it read-only so clients can observe a long simulation while the
        # authoritative clock owns the sole write transaction. Presence can be
        # refreshed by explicit manager mutations without turning every poll
        # into a competing SQLite writer.
        return manager

    def league_state(self, league_id: str, manager_id: str, session_token: str) -> dict[str, Any]:
        with self.transaction() as connection:
            manager = self.authenticate(connection, league_id, manager_id, session_token)
            state = self._league_state(connection, league_id)
            state["viewer_manager_id"] = manager["id"]
        return state

    def claim_team(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        team_id: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        with self.transaction(immediate=True) as connection:
            manager = self.authenticate(connection, league_id, manager_id, session_token)
            league = self._league_row(connection, league_id)
            self._require_lobby(league)
            self._require_revision(league, expected_revision)
            try:
                connection.execute(
                    "UPDATE managers SET team_id = ?, ready = 0 WHERE id = ?",
                    (str(team_id), manager_id),
                )
            except sqlite3.IntegrityError as exc:
                raise MultiplayerConflictError("That team was claimed by another manager.", int(league["revision"])) from exc
            revision = int(league["revision"]) + 1
            self._set_revision(connection, league_id, revision)
            self._insert_event(
                connection,
                league_id,
                revision,
                "team_claimed",
                manager_id,
                str(team_id),
                {"team_id": str(team_id), "display_name": manager["display_name"]},
                important=True,
            )
            return self._league_state(connection, league_id)

    def set_ready(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        ready: bool,
        expected_revision: int,
    ) -> dict[str, Any]:
        with self.transaction(immediate=True) as connection:
            manager = self.authenticate(connection, league_id, manager_id, session_token)
            league = self._league_row(connection, league_id)
            self._require_revision(league, expected_revision)
            if not manager["team_id"]:
                raise MultiplayerError("Choose a team before marking ready.")
            connection.execute("UPDATE managers SET ready = ? WHERE id = ?", (1 if ready else 0, manager_id))
            revision = int(league["revision"]) + 1
            self._set_revision(connection, league_id, revision)
            self._insert_event(
                connection,
                league_id,
                revision,
                "manager_ready" if ready else "manager_unready",
                manager_id,
                manager["team_id"],
                {"ready": bool(ready)},
            )
            return self._league_state(connection, league_id)

    def update_settings(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        settings: dict[str, Any],
        expected_revision: int,
    ) -> dict[str, Any]:
        with self.transaction(immediate=True) as connection:
            self.authenticate(connection, league_id, manager_id, session_token)
            league = self._league_row(connection, league_id)
            self._require_host(league, manager_id)
            self._require_lobby(league)
            self._require_revision(league, expected_revision)
            normalized = normalize_settings(settings, json.loads(league["settings_json"]))
            revision = int(league["revision"]) + 1
            connection.execute(
                "UPDATE leagues SET settings_json = ?, revision = ?, updated_at = ? WHERE id = ?",
                (json.dumps(normalized, sort_keys=True), revision, iso_timestamp(), league_id),
            )
            self._insert_event(
                connection,
                league_id,
                revision,
                "settings_updated",
                manager_id,
                None,
                {"settings": normalized},
            )
            return self._league_state(connection, league_id)

    def activate_league(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        expected_revision: int,
        save_path: str,
        phase: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        with self.transaction(immediate=True) as connection:
            self.authenticate(connection, league_id, manager_id, session_token)
            league = self._league_row(connection, league_id)
            self._require_host(league, manager_id)
            self._require_lobby(league)
            self._require_revision(league, expected_revision)
            managers = connection.execute(
                "SELECT * FROM managers WHERE league_id = ? ORDER BY joined_at",
                (league_id,),
            ).fetchall()
            if len(managers) < 2:
                raise MultiplayerError("At least two human managers are required.")
            if any(not row["team_id"] for row in managers):
                raise MultiplayerError("Every manager must choose a team before the league starts.")
            if any(not bool(row["ready"]) for row in managers):
                raise MultiplayerError("Every manager must be ready before the league starts.")
            settings = json.loads(league["settings_json"])
            clock = make_clock(settings, phase, now=now)
            revision = int(league["revision"]) + 1
            connection.execute(
                """
                UPDATE leagues
                SET status = 'active', save_path = ?, revision = ?, clock_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (str(save_path), revision, json.dumps(clock, sort_keys=True), iso_timestamp(now), league_id),
            )
            connection.execute("UPDATE managers SET ready = 0 WHERE league_id = ?", (league_id,))
            self._insert_event(
                connection,
                league_id,
                revision,
                "league_started",
                manager_id,
                next((row["team_id"] for row in managers if row["id"] == manager_id), None),
                {"save_path": str(save_path), "phase": phase, "clock": clock},
                important=True,
            )
            return self._league_state(connection, league_id)

    def events(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            self.authenticate(connection, league_id, manager_id, session_token)
            rows = connection.execute(
                """
                SELECT * FROM league_events
                WHERE league_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (league_id, max(0, int(after_sequence)), max(1, min(250, int(limit)))),
            ).fetchall()
            events = [self._event_payload(row) for row in rows]
            league = self._league_row(connection, league_id)
        return {
            "events": events,
            "last_sequence": events[-1]["sequence"] if events else int(after_sequence),
            "revision": int(league["revision"]),
        }

    def due_league_ids(self, now: datetime | None = None) -> list[str]:
        now = now or utc_now()
        with self.transaction() as connection:
            rows = connection.execute("SELECT id, clock_json FROM leagues WHERE status = 'active'").fetchall()
        due = []
        for row in rows:
            clock = json.loads(row["clock_json"] or "{}")
            deadline = parse_timestamp(clock.get("deadline_at"))
            if deadline and not clock.get("paused") and deadline <= now:
                due.append(str(row["id"]))
        return due

    def _unique_code(self, connection: sqlite3.Connection) -> str:
        for _ in range(100):
            code = "".join(secrets.choice(LOBBY_CODE_ALPHABET) for _ in range(6))
            if not connection.execute("SELECT 1 FROM leagues WHERE code = ?", (code,)).fetchone():
                return code
        raise MultiplayerError("Could not allocate a unique lobby code.")

    def _league_row(self, connection: sqlite3.Connection, league_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM leagues WHERE id = ?", (league_id,)).fetchone()
        if not row:
            raise MultiplayerNotFoundError("Multiplayer league not found.")
        return row

    def _league_row_by_code(self, connection: sqlite3.Connection, code: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM leagues WHERE code = ?",
            (str(code).strip().upper(),),
        ).fetchone()
        if not row:
            raise MultiplayerNotFoundError("Lobby code not found.")
        return row

    def _league_state(self, connection: sqlite3.Connection, league_id: str) -> dict[str, Any]:
        league = self._league_row(connection, league_id)
        managers = connection.execute(
            "SELECT id, display_name, team_id, ready, joined_at, last_seen FROM managers WHERE league_id = ? ORDER BY joined_at, id",
            (league_id,),
        ).fetchall()
        return {
            "id": league["id"],
            "code": league["code"],
            "name": league["name"],
            "status": league["status"],
            "host_manager_id": league["host_manager_id"],
            "save_path": league["save_path"],
            "revision": int(league["revision"]),
            "settings": json.loads(league["settings_json"] or "{}"),
            "clock": json.loads(league["clock_json"] or "{}"),
            "winner": json.loads(league["winner_json"] or "{}"),
            "created_at": league["created_at"],
            "updated_at": league["updated_at"],
            "managers": [
                {
                    "id": row["id"],
                    "display_name": row["display_name"],
                    "team_id": row["team_id"],
                    "ready": bool(row["ready"]),
                    "joined_at": row["joined_at"],
                    "last_seen": row["last_seen"],
                    "is_host": row["id"] == league["host_manager_id"],
                }
                for row in managers
            ],
        }

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        league_id: str,
        revision: int,
        kind: str,
        actor_manager_id: str | None,
        actor_team_id: str | None,
        payload: dict[str, Any],
        *,
        important: bool = False,
    ) -> None:
        connection.execute(
            """
            INSERT INTO league_events
                (id, league_id, revision, kind, actor_manager_id, actor_team_id, payload_json, important, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"mp_event_{uuid.uuid4().hex}",
                league_id,
                int(revision),
                str(kind),
                actor_manager_id,
                actor_team_id,
                json.dumps(to_plain(payload), ensure_ascii=False, sort_keys=True),
                1 if important else 0,
                iso_timestamp(),
            ),
        )

    def _event_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": int(row["sequence"]),
            "id": row["id"],
            "league_id": row["league_id"],
            "revision": int(row["revision"]),
            "kind": row["kind"],
            "actor_manager_id": row["actor_manager_id"],
            "actor_team_id": row["actor_team_id"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "important": bool(row["important"]),
            "created_at": row["created_at"],
        }

    def _set_revision(
        self,
        connection: sqlite3.Connection,
        league_id: str,
        revision: int,
        updated_at: str | None = None,
    ) -> None:
        connection.execute(
            "UPDATE leagues SET revision = ?, updated_at = ? WHERE id = ?",
            (int(revision), updated_at or iso_timestamp(), league_id),
        )

    @staticmethod
    def _require_host(league: sqlite3.Row, manager_id: str) -> None:
        if league["host_manager_id"] != manager_id:
            raise MultiplayerAuthorizationError("Only the league host can do that.")

    @staticmethod
    def _require_lobby(league: sqlite3.Row) -> None:
        if league["status"] != "lobby":
            raise MultiplayerError("This action is only available in the lobby.")

    @staticmethod
    def _require_revision(league: sqlite3.Row, expected_revision: int) -> None:
        current = int(league["revision"])
        if int(expected_revision) != current:
            raise MultiplayerConflictError(
                f"League changed before this action could commit (expected {expected_revision}, current {current}).",
                current,
            )


class MultiplayerService:
    """Application service coordinating the store and existing action layer."""

    def __init__(
        self,
        store: MultiplayerStore,
        *,
        root: str | Path,
        save_dir: str | Path,
        canonical: dict[str, Any],
        dispatcher: Callable[..., dict[str, Any]],
        now_fn: Callable[[], datetime] = utc_now,
    ):
        self.store = store
        self.root = Path(root)
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.canonical = canonical
        self.dispatcher = dispatcher
        self.now_fn = now_fn
        self._league_locks: dict[str, threading.RLock] = {}
        self._league_locks_guard = threading.Lock()

    def dispatch(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(payload or {})
        action = str(action or "").replace("-", "_")
        if action == "create_lobby":
            result = self.store.create_lobby(payload.get("name"), payload.get("display_name"), payload.get("settings"))
            return self._decorate(result)
        if action == "join_lobby":
            return self._decorate(self.store.join_lobby(payload.get("code"), payload.get("display_name")))

        session = self._session(payload)
        if action == "lobby_state":
            return self._decorate(
                self.store.league_state(session["league_id"], session["manager_id"], session["session_token"])
            )
        if action == "claim_team":
            self._validate_team_id(str(payload.get("team_id") or ""))
            return self._decorate(
                self.store.claim_team(
                    **session,
                    team_id=str(payload["team_id"]),
                    expected_revision=int(payload["expected_revision"]),
                )
            )
        if action == "set_ready":
            ready = bool(payload.get("ready", True))
            state = self.store.set_ready(
                **session,
                ready=ready,
                expected_revision=int(payload["expected_revision"]),
            )
            if (
                ready
                and state.get("status") == "active"
                and state.get("settings", {}).get("ready_up_enabled")
                and state.get("managers")
                and all(manager.get("ready") for manager in state["managers"])
            ):
                advanced = self.advance_due_league(session["league_id"], force=True)
                advanced["league"] = self._decorate(
                    self.store.league_state(**session)
                )
                return advanced
            return self._decorate(state)
        if action == "update_settings":
            return self._decorate(
                self.store.update_settings(
                    **session,
                    settings=payload.get("settings") or {},
                    expected_revision=int(payload["expected_revision"]),
                )
            )
        if action == "start_league":
            return self.start_league(**session, expected_revision=int(payload["expected_revision"]))
        if action == "events":
            return self.store.events(
                **session,
                after_sequence=int(payload.get("after_sequence") or 0),
                limit=int(payload.get("limit") or 100),
            )
        if action == "snapshot":
            return self.snapshot(**session)
        if action == "human_trade_offers":
            return self.human_trade_offers(**session)
        if action == "respond_human_trade":
            return self.respond_human_trade(
                **session,
                offer_id=str(payload.get("offer_id") or ""),
                decision=str(payload.get("decision") or "reject"),
                expected_revision=int(payload["expected_revision"]),
                idempotency_key=str(payload.get("idempotency_key") or ""),
            )
        if action == "game_action":
            return self.game_action(
                **session,
                action=str(payload.get("game_action") or ""),
                action_payload=payload.get("action_payload") or {},
                expected_revision=payload.get("expected_revision"),
                idempotency_key=str(payload.get("idempotency_key") or ""),
            )
        if action == "request_clock_extension":
            return self.request_clock_extension(
                **session,
                expected_revision=int(payload["expected_revision"]),
                seconds=int(payload.get("seconds") or 45),
            )
        if action == "tick":
            state = self.store.league_state(**session)
            if state.get("host_manager_id") != session["manager_id"]:
                raise MultiplayerAuthorizationError("Only the league host can force a clock check.")
            return self.advance_due_league(session["league_id"])
        raise MultiplayerError(f"Unknown multiplayer action {action!r}.")

    def start_league(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        with self.league_lock(league_id):
            state = self.store.league_state(league_id, manager_id, session_token)
            if state["revision"] != int(expected_revision):
                raise MultiplayerConflictError("Lobby changed before start.", state["revision"])
            if state["host_manager_id"] != manager_id:
                raise MultiplayerAuthorizationError("Only the league host can start the league.")
            managers = state["managers"]
            if len(managers) < 2 or any(not manager.get("team_id") for manager in managers):
                raise MultiplayerError("At least two managers must choose teams before starting.")
            host = next(manager for manager in managers if manager["id"] == manager_id)
            host_team = self._team(host["team_id"])
            seed = secrets.randbelow(2_147_483_646) + 1
            save_name = f"multiplayer_{state['code'].lower()}_{uuid.uuid4().hex[:8]}"
            created = self.dispatcher(
                "create_save",
                {
                    "team": host_team["abbrev"],
                    "seed": seed,
                    "save_name": save_name,
                    "game_mode": state.get("settings", {}).get("game_mode") or "standard",
                },
                root=self.root,
                save_dir=self.save_dir,
                canonical=self.canonical,
            )
            save_path = Path(created["save_path"])
            try:
                save = ensure_league_save_defaults(load_save(save_path), self.canonical)
                assignments = {
                    manager["id"]: {
                        "display_name": manager["display_name"],
                        "team_id": manager["team_id"],
                    }
                    for manager in managers
                }
                human_team_ids = sorted({manager["team_id"] for manager in managers})
                save.setdefault("meta", {})["human_team_ids"] = human_team_ids
                save["meta"]["multiplayer_league_id"] = league_id
                save["meta"]["multiplayer_protocol_version"] = MULTIPLAYER_PROTOCOL_VERSION
                save["manager_assignments"] = assignments
                save["multiplayer_state"] = {
                    "league_id": league_id,
                    "code": state["code"],
                    "revision": int(expected_revision) + 1,
                    "human_team_ids": human_team_ids,
                }
                if (save.get("fantasy_draft_state") or {}).get("status") == "in_progress":
                    simulate_fantasy_draft_until_human(
                        self.canonical,
                        save,
                        set(human_team_ids),
                    )
                write_save(save_path, save)
                active = self.store.activate_league(
                    league_id,
                    manager_id,
                    session_token,
                    expected_revision,
                    str(save_path),
                    str((save.get("state") or {}).get("phase") or "preseason"),
                    now=self.now_fn(),
                )
            except Exception:
                save_path.unlink(missing_ok=True)
                raise
        return self._decorate(active)

    def snapshot(self, league_id: str, manager_id: str, session_token: str) -> dict[str, Any]:
        state = self.store.league_state(league_id, manager_id, session_token)
        if state["status"] != "active" or not state.get("save_path"):
            return {"league": self._decorate(state), "home": None}
        manager = next(row for row in state["managers"] if row["id"] == manager_id)
        home = self._dispatch_as_manager(
            state,
            manager,
            "home",
            {"save_path": state["save_path"]},
            mutation=False,
        )
        return {
            "league": self._decorate(state),
            "manager": manager,
            "home": home,
            "revision": state["revision"],
        }

    def game_action(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        action: str,
        action_payload: dict[str, Any],
        expected_revision: int | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        action = str(action or "").replace("-", "_")
        if not action:
            raise MultiplayerError("Missing game action.")
        if action in {"runtime_status", "diagnostic_runtime", "list_saves", "create_save", "export_save", "restore_save", "recover_save"}:
            raise MultiplayerAuthorizationError("Local save management is unavailable through multiplayer.")
        mutation = action in MUTATING_ACTIONS
        if action in GLOBAL_CLOCK_ACTIONS:
            raise MultiplayerAuthorizationError("League advancement is controlled by the shared clock.")
        if mutation and (expected_revision is None or not idempotency_key):
            raise MultiplayerError("Mutations require expected_revision and idempotency_key.")
        with self.league_lock(league_id):
            if mutation:
                if action == "apply_trade_candidate":
                    state = self.store.league_state(league_id, manager_id, session_token)
                    manager = next(row for row in state["managers"] if row["id"] == manager_id)
                    recipient = self._human_trade_recipient(state, manager, action_payload)
                    if recipient:
                        return self._submit_human_trade(
                            state,
                            manager,
                            recipient,
                            action_payload,
                            int(expected_revision),
                            idempotency_key,
                            session_token,
                        )
                return self._mutating_game_action(
                    league_id,
                    manager_id,
                    session_token,
                    action,
                    action_payload,
                    int(expected_revision),
                    idempotency_key,
                )
            state = self.store.league_state(league_id, manager_id, session_token)
            self._require_active(state)
            manager = next(row for row in state["managers"] if row["id"] == manager_id)
            if action in MUTATING_ACTIONS:
                raise MultiplayerAuthorizationError(f"Multiplayer mutation {action!r} is not available.")
            result = self._dispatch_as_manager(state, manager, action, action_payload, mutation=False)
            return {"status": "ok", "revision": state["revision"], "result": result}

    def human_trade_offers(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
    ) -> dict[str, Any]:
        with self.store.transaction() as connection:
            self.store.authenticate(connection, league_id, manager_id, session_token)
            league = self.store._league_row(connection, league_id)
            rows = connection.execute(
                """
                SELECT * FROM human_trade_offers
                WHERE league_id = ? AND (recipient_manager_id = ? OR proposer_manager_id = ?)
                  AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (league_id, manager_id, manager_id),
            ).fetchall()
        offers = []
        for row in rows:
            candidate = json.loads(row["candidate_json"])
            offers.append(
                {
                    "id": row["id"],
                    "status": row["status"],
                    "direction": "incoming" if row["recipient_manager_id"] == manager_id else "outgoing",
                    "proposer_team_id": row["proposer_team_id"],
                    "recipient_team_id": row["recipient_team_id"],
                    "candidate": candidate,
                    "headline": candidate.get("headline")
                    or ((candidate.get("proposal") or {}).get("headline"))
                    or "Human manager trade proposal",
                    "created_at": row["created_at"],
                }
            )
        return {"offers": offers, "offer_count": len(offers), "revision": int(league["revision"])}

    def _submit_human_trade(
        self,
        state: dict[str, Any],
        manager: dict[str, Any],
        recipient: dict[str, Any],
        action_payload: dict[str, Any],
        expected_revision: int,
        idempotency_key: str,
        session_token: str,
    ) -> dict[str, Any]:
        league_id = state["id"]
        submitted = dict(action_payload.get("candidate") or {})
        proposal = submitted.get("proposal") or {}
        from_team = self._team(str(proposal.get("from_team_id") or ""))
        to_team = self._team(str(proposal.get("to_team_id") or ""))
        evaluated = self._dispatch_as_manager(
            state,
            manager,
            "evaluate_trade",
            {
                "from_team": from_team["abbrev"],
                "to_team": to_team["abbrev"],
                "from_assets": [trade_asset_spec(asset) for asset in proposal.get("from_assets") or []],
                "to_assets": [trade_asset_spec(asset) for asset in proposal.get("to_assets") or []],
                "seed": int(action_payload.get("seed") or 7),
            },
            mutation=False,
        )
        candidate = to_plain(evaluated)
        if (candidate.get("legality") or {}).get("status") != "legal":
            raise MultiplayerError("Only a currently legal trade can be sent to another human manager.")
        with self.store.transaction(immediate=True) as connection:
            self.store.authenticate(connection, league_id, manager["id"], session_token)
            league = self.store._league_row(connection, league_id)
            existing = self._idempotent_response(connection, league_id, manager["id"], idempotency_key)
            if existing:
                return existing
            self.store._require_revision(league, expected_revision)
            self._validate_mutation_ownership(state, manager, "apply_trade_candidate", action_payload)
            offer_id = f"human_trade_{uuid.uuid4().hex}"
            revision = int(league["revision"]) + 1
            now = iso_timestamp()
            connection.execute(
                """
                INSERT INTO human_trade_offers
                    (id, league_id, proposer_manager_id, recipient_manager_id,
                     proposer_team_id, recipient_team_id, candidate_json, status,
                     created_revision, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    offer_id,
                    league_id,
                    manager["id"],
                    recipient["id"],
                    manager["team_id"],
                    recipient["team_id"],
                    json.dumps(candidate, sort_keys=True),
                    revision,
                    now,
                    now,
                ),
            )
            self.store._set_revision(connection, league_id, revision)
            self.store._insert_event(
                connection,
                league_id,
                revision,
                "human_trade_proposed",
                manager["id"],
                manager["team_id"],
                {
                    "offer_id": offer_id,
                    "recipient_manager_id": recipient["id"],
                    "recipient_team_id": recipient["team_id"],
                    "summary": candidate.get("headline") or "A human manager submitted a trade proposal.",
                },
                important=True,
            )
            response = {
                "status": "pending_human_acceptance",
                "revision": revision,
                "offer_id": offer_id,
                "idempotency_key": idempotency_key,
            }
            self._store_idempotent_response(connection, league_id, manager["id"], idempotency_key, response)
            return response

    def respond_human_trade(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        offer_id: str,
        decision: str,
        expected_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if decision not in {"accept", "reject"}:
            raise MultiplayerError("Trade response must be accept or reject.")
        if not offer_id or not idempotency_key:
            raise MultiplayerError("offer_id and idempotency_key are required.")
        with self.league_lock(league_id), self.store.transaction(immediate=True) as connection:
            manager = self.store.authenticate(connection, league_id, manager_id, session_token)
            league = self.store._league_row(connection, league_id)
            existing = self._idempotent_response(connection, league_id, manager_id, idempotency_key)
            if existing:
                return existing
            self.store._require_revision(league, expected_revision)
            offer = connection.execute(
                "SELECT * FROM human_trade_offers WHERE id = ? AND league_id = ?",
                (offer_id, league_id),
            ).fetchone()
            if not offer or offer["status"] != "pending":
                raise MultiplayerConflictError("That trade offer is no longer pending.", int(league["revision"]))
            if offer["recipient_manager_id"] != manager_id:
                raise MultiplayerAuthorizationError("Only the receiving manager can answer this offer.")
            revision = int(league["revision"]) + 1
            now = iso_timestamp()
            result: dict[str, Any] = {"status": "rejected"}
            if decision == "accept":
                candidate = json.loads(offer["candidate_json"])
                candidate["accepted_by_all"] = True
                for evaluation in candidate.get("evaluations") or []:
                    evaluation["accepted"] = True
                    evaluation["decision"] = "human_manager_accepted"
                candidate.setdefault("offer_context", {}).update(
                    {"source": "multiplayer_human", "status": "both_humans_accepted"}
                )
                save_path = Path(league["save_path"])
                backup = save_path.read_bytes()
                try:
                    state = self.store._league_state(connection, league_id)
                    result = self._dispatch_as_manager(
                        state,
                        dict(manager),
                        "apply_trade_candidate",
                        {"candidate": candidate, "source": "multiplayer_human"},
                        mutation=True,
                    )
                    if result.get("status") != "applied":
                        raise MultiplayerConflictError(
                            "The trade became illegal or an asset moved before acceptance.",
                            int(league["revision"]),
                        )
                    self._update_save_multiplayer_revision(save_path, revision)
                except Exception:
                    restore_bytes_atomic(save_path, backup)
                    raise
            status = "accepted_executed" if decision == "accept" else "rejected"
            connection.execute(
                """
                UPDATE human_trade_offers
                SET status = ?, resolved_revision = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, revision, now, offer_id),
            )
            self.store._set_revision(connection, league_id, revision)
            self.store._insert_event(
                connection,
                league_id,
                revision,
                "human_trade_completed" if decision == "accept" else "human_trade_rejected",
                manager_id,
                manager["team_id"],
                {
                    "offer_id": offer_id,
                    "proposer_team_id": offer["proposer_team_id"],
                    "recipient_team_id": offer["recipient_team_id"],
                    "summary": (
                        "Human managers completed a trade."
                        if decision == "accept"
                        else "A human manager rejected a trade proposal."
                    ),
                },
                important=True,
            )
            response = {
                "status": status,
                "revision": revision,
                "offer_id": offer_id,
                "result": result,
                "idempotency_key": idempotency_key,
            }
            self._store_idempotent_response(connection, league_id, manager_id, idempotency_key, response)
            return response

    def _mutating_game_action(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        action: str,
        action_payload: dict[str, Any],
        expected_revision: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self.store.transaction(immediate=True) as connection:
            manager = self.store.authenticate(connection, league_id, manager_id, session_token)
            league = self.store._league_row(connection, league_id)
            if league["status"] != "active" or not league["save_path"]:
                raise MultiplayerError("League is not active.")
            existing = connection.execute(
                """
                SELECT response_json FROM idempotent_responses
                WHERE league_id = ? AND manager_id = ? AND idempotency_key = ?
                """,
                (league_id, manager_id, idempotency_key),
            ).fetchone()
            if existing:
                return json.loads(existing["response_json"])
            self.store._require_revision(league, expected_revision)
            state = self.store._league_state(connection, league_id)
            save_path = Path(league["save_path"])
            backup = save_path.read_bytes()
            try:
                result = self._dispatch_as_manager(
                    state,
                    dict(manager),
                    action,
                    action_payload,
                    mutation=True,
                )
                revision = int(league["revision"]) + 1
                self._update_save_multiplayer_revision(save_path, revision)
                response = {
                    "status": "committed",
                    "revision": revision,
                    "result": result,
                    "idempotency_key": idempotency_key,
                }
                self.store._set_revision(connection, league_id, revision)
                if action == "fantasy_draft_pick":
                    refreshed_save = ensure_league_save_defaults(load_save(save_path), self.canonical)
                    settings = json.loads(league["settings_json"] or "{}")
                    next_phase = str((refreshed_save.get("state") or {}).get("phase") or "preseason")
                    next_clock = make_clock(
                        settings,
                        next_phase,
                        now=self.now_fn(),
                        sequence=int((json.loads(league["clock_json"] or "{}")).get("sequence") or 0) + 1,
                    )
                    connection.execute(
                        "UPDATE leagues SET clock_json = ? WHERE id = ?",
                        (json.dumps(next_clock, sort_keys=True), league_id),
                    )
                    connection.execute("UPDATE managers SET ready = 0 WHERE league_id = ?", (league_id,))
                self.store._insert_event(
                    connection,
                    league_id,
                    revision,
                    human_action_event_kind(action),
                    manager_id,
                    manager["team_id"],
                    {
                        "action": action,
                        "summary": summarize_game_action(action, action_payload, result),
                    },
                    important=action in {"apply_trade", "apply_trade_candidate", "apply_contract", "waive_player"},
                )
                connection.execute(
                    """
                    INSERT INTO idempotent_responses
                        (league_id, manager_id, idempotency_key, response_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (league_id, manager_id, idempotency_key, json.dumps(to_plain(response), sort_keys=True), iso_timestamp()),
                )
                return response
            except Exception:
                restore_bytes_atomic(save_path, backup)
                raise

    def request_clock_extension(
        self,
        league_id: str,
        manager_id: str,
        session_token: str,
        expected_revision: int,
        seconds: int = 45,
    ) -> dict[str, Any]:
        with self.league_lock(league_id), self.store.transaction(immediate=True) as connection:
            manager = self.store.authenticate(connection, league_id, manager_id, session_token)
            league = self.store._league_row(connection, league_id)
            self.store._require_revision(league, expected_revision)
            clock = json.loads(league["clock_json"] or "{}")
            if clock.get("kind") not in {"draft_pick", "fantasy_pick"}:
                raise MultiplayerError("Clock extensions are only available during the draft.")
            if clock.get("extension_used"):
                raise MultiplayerError("The extension for this pick has already been used.")
            save = ensure_league_save_defaults(load_save(Path(league["save_path"])), self.canonical)
            if clock.get("kind") == "fantasy_pick":
                current_team_id = fantasy_draft_current_team_id(save)
            else:
                draft_state = save.get("draft_state") or {}
                pending = (
                    draft_state.get("pending_draft_selections")
                    or (draft_state.get("draft") or {}).get("pending_draft_selections")
                    or save.get("pending_draft_selections")
                    or []
                )
                current_index = int(draft_state.get("current_index") or 0)
                current = pending[current_index] if current_index < len(pending) else {}
                current_team_id = (current.get("selection") or current).get("team_id")
            if current_team_id and current_team_id != manager["team_id"]:
                raise MultiplayerAuthorizationError("Only the manager currently on the clock can extend this pick.")
            deadline = parse_timestamp(clock.get("deadline_at")) or self.now_fn()
            added = max(10, min(90, int(seconds)))
            clock["deadline_at"] = iso_timestamp(deadline + timedelta(seconds=added))
            clock["extension_used"] = True
            revision = int(league["revision"]) + 1
            connection.execute(
                "UPDATE leagues SET revision = ?, clock_json = ?, updated_at = ? WHERE id = ?",
                (revision, json.dumps(clock, sort_keys=True), iso_timestamp(), league_id),
            )
            self.store._insert_event(
                connection,
                league_id,
                revision,
                "draft_clock_extended",
                manager_id,
                manager["team_id"],
                {"seconds": added, "clock": clock},
                important=True,
            )
            return self._decorate(self.store._league_state(connection, league_id))

    def advance_due_leagues(self) -> list[dict[str, Any]]:
        results = []
        for league_id in self.store.due_league_ids(self.now_fn()):
            try:
                results.append(self.advance_due_league(league_id))
            except MultiplayerConflictError:
                continue
        return results

    def advance_due_league(self, league_id: str, *, force: bool = False) -> dict[str, Any]:
        with self.league_lock(league_id), self.store.transaction(immediate=True) as connection:
            league = self.store._league_row(connection, league_id)
            if league["status"] != "active" or not league["save_path"]:
                return {"status": "not_active"}
            clock = json.loads(league["clock_json"] or "{}")
            deadline = parse_timestamp(clock.get("deadline_at"))
            now = self.now_fn()
            if not force and (not deadline or deadline > now or clock.get("paused")):
                return {"status": "not_due", "clock": clock}
            managers = connection.execute(
                "SELECT * FROM managers WHERE league_id = ? ORDER BY joined_at",
                (league_id,),
            ).fetchall()
            host = next((row for row in managers if row["id"] == league["host_manager_id"]), managers[0])
            save_path = Path(league["save_path"])
            backup = save_path.read_bytes()
            try:
                save = ensure_league_save_defaults(load_save(save_path), self.canonical)
                phase = str((save.get("state") or {}).get("phase") or "")
                settings = json.loads(league["settings_json"])
                action, payload = self._clock_action(save, settings, host)
                current = (save.get("state") or {}).get("current_date") or CANONICAL_START_DATE
                trade_deadline = trade_deadline_date(season_start_year_from_date(current))
                if action == "advance_save" and current == trade_deadline and force and all(manager["ready"] for manager in managers):
                    # The clock pauses at the deadline; all managers must ready
                    # up again before explicitly moving through it together.
                    payload["trade_deadline_confirmed"] = trade_deadline
                    target = str(clock.get("trade_deadline_target") or "")
                    if target > current:
                        payload["to_date"] = target
                        payload.pop("days", None)
                        payload["next_event"] = False
                result = self._dispatch_as_manager(
                    self.store._league_state(connection, league_id),
                    dict(host),
                    action,
                    payload,
                    mutation=True,
                    allow_clock_action=True,
                )
                save = ensure_league_save_defaults(load_save(save_path), self.canonical)
                next_phase = str((save.get("state") or {}).get("phase") or phase)
                championship_ledger = record_multiplayer_champion(save)
                completed = len(championship_ledger) >= int(settings.get("season_count") or 1)
                winner = dynasty_result(save, managers, championship_ledger) if completed else {}
                next_clock = make_clock(
                    settings,
                    next_phase,
                    now=now,
                    sequence=int(clock.get("sequence") or 0) + 1,
                )
                if isinstance(result, dict) and result.get("trade_deadline_checkpoint"):
                    next_clock["paused"] = True
                    next_clock["pause_reason"] = "trade_deadline"
                    next_clock["trade_deadline_target"] = result["trade_deadline_checkpoint"]["requested_to_date"]
                revision = int(league["revision"]) + 1
                save.setdefault("multiplayer_state", {})["revision"] = revision
                write_save(save_path, save)
                connection.execute(
                    """
                    UPDATE leagues
                    SET revision = ?, clock_json = ?, winner_json = ?, status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        revision,
                        json.dumps({} if completed else next_clock, sort_keys=True),
                        json.dumps(winner, sort_keys=True),
                        "completed" if completed else "active",
                        iso_timestamp(now),
                        league_id,
                    ),
                )
                connection.execute("UPDATE managers SET ready = 0 WHERE league_id = ?", (league_id,))
                self.store._insert_event(
                    connection,
                    league_id,
                    revision,
                    "dynasty_completed" if completed else "league_advanced",
                    None,
                    None,
                    {
                        "action": action,
                        "phase_before": phase,
                        "phase_after": next_phase,
                        "clock": next_clock,
                        "result_status": result.get("status") if isinstance(result, dict) else None,
                        "winner": winner,
                    },
                    important=True,
                )
                return {
                    "status": "advanced",
                    "revision": revision,
                    "phase": next_phase,
                    "clock": {} if completed else next_clock,
                    "winner": winner,
                    "result": result,
                }
            except Exception:
                restore_bytes_atomic(save_path, backup)
                raise

    def _clock_action(
        self,
        save: dict[str, Any],
        settings: dict[str, Any],
        host: sqlite3.Row,
    ) -> tuple[str, dict[str, Any]]:
        phase = str((save.get("state") or {}).get("phase") or "")
        team = self._team(host["team_id"])["abbrev"]
        seed = secrets.randbelow(2_147_483_646) + 1
        if phase == "fantasy_draft":
            current_team_id = fantasy_draft_current_team_id(save)
            if not current_team_id:
                return "advance_save", {"next_event": True, "seed": seed}
            current_team = self._team(current_team_id)
            return "fantasy_draft_pick", {
                "team": current_team["abbrev"],
                "auto": True,
                "human_team_ids": list((save.get("meta") or {}).get("human_team_ids") or []),
            }
        if phase == "draft":
            if (save.get("draft_state") or {}).get("status") == "completed":
                return "advance_save", {"next_event": True, "seed": seed}
            return "draft_apply_current", {"team": team, "seed": seed}
        if phase == "free_agency":
            if (save.get("free_agency_state") or {}).get("status") == "completed":
                return "advance_save", {"next_event": True, "seed": seed}
            return "advance_free_agency", {"team": team, "seed": seed, "mode": "day"}
        if phase in {"play_in", "playoffs"}:
            if (save.get("playoff_state") or {}).get("status") == "completed":
                return "advance_save", {"next_event": True, "seed": seed}
            return "simulate_playoff_game", {"seed": seed}
        if phase in {"draft_lottery", "offseason"}:
            return "advance_save", {"next_event": True, "seed": seed}
        days = 7 if settings.get("advance_step") == "week" else 31
        return "advance_save", {"days": days, "seed": seed, "checkpoint_days": min(31, days)}

    def _dispatch_as_manager(
        self,
        league: dict[str, Any],
        manager: dict[str, Any],
        action: str,
        payload: dict[str, Any],
        *,
        mutation: bool,
        allow_clock_action: bool = False,
    ) -> dict[str, Any]:
        if action in GLOBAL_CLOCK_ACTIONS and not allow_clock_action:
            raise MultiplayerAuthorizationError("League advancement is controlled by the shared clock.")
        team_id = str(manager.get("team_id") or "")
        if not team_id:
            raise MultiplayerAuthorizationError("Choose a team first.")
        team = self._team(team_id)
        payload = dict(payload or {})
        payload["save_path"] = league["save_path"]
        if (action in TEAM_DEFAULT_ACTIONS or action in TEAM_MUTATIONS) and not (
            allow_clock_action and action == "fantasy_draft_pick" and payload.get("team")
        ):
            payload["team"] = team["abbrev"]
        if action == "fantasy_draft_pick":
            payload["human_team_ids"] = [
                row["team_id"]
                for row in league.get("managers") or []
                if row.get("team_id")
            ]
        if action == "find_trade":
            payload["for_team"] = team["abbrev"]
        if action == "find_trade_for_assets":
            payload["seller_team"] = team["abbrev"]
            payload["for_team"] = team["abbrev"]
        if mutation:
            if action in HOST_MUTATIONS and manager.get("id") != league.get("host_manager_id"):
                raise MultiplayerAuthorizationError("Only the league host can change league-wide game settings.")
            if action not in TEAM_MUTATIONS | HOST_MUTATIONS:
                raise MultiplayerAuthorizationError(f"Multiplayer mutation {action!r} is not available.")
            if not (allow_clock_action and action == "fantasy_draft_pick"):
                self._validate_mutation_ownership(league, manager, action, payload)
            return self._dispatch_with_actor_compatibility(Path(league["save_path"]), team, action, payload)
        if action in LEGACY_ACTOR_READ_ACTIONS:
            result = self._dispatch_with_actor_compatibility(
                Path(league["save_path"]),
                team,
                action,
                payload,
            )
        else:
            result = self.dispatcher(
                action,
                payload,
                root=self.root,
                save_dir=self.save_dir,
                canonical=self.canonical,
            )
        if action == "home":
            save_status = result.get("save") or {}
            save_status["user_team"] = {
                "id": team.get("id"),
                "abbrev": team.get("abbrev"),
                "name": team.get("name") or team.get("abbrev"),
            }
            save_status["team"] = team.get("abbrev")
            result["save"] = save_status
        if action == "user_trade_offers":
            offers = result.get("offers") or []
            result["offers"] = [
                offer
                for offer in offers
                if team["id"]
                in {
                    ((offer.get("proposal") or {}).get("from_team_id")),
                    ((offer.get("proposal") or {}).get("to_team_id")),
                }
            ]
            if isinstance(result.get("pending_count"), int):
                result["pending_count"] = len(result["offers"])
        return result

    def _dispatch_with_actor_compatibility(
        self,
        save_path: Path,
        team: dict[str, Any],
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        save = ensure_league_save_defaults(load_save(save_path), self.canonical)
        original_id = save.get("meta", {}).get("user_team_id")
        original_abbrev = save.get("meta", {}).get("user_team_abbrev")
        save.setdefault("meta", {})["user_team_id"] = team["id"]
        save["meta"]["user_team_abbrev"] = team["abbrev"]
        write_save(save_path, save)
        try:
            return self.dispatcher(
                action,
                payload,
                root=self.root,
                save_dir=self.save_dir,
                canonical=self.canonical,
            )
        finally:
            restored = ensure_league_save_defaults(load_save(save_path), self.canonical)
            restored.setdefault("meta", {})["user_team_id"] = original_id
            restored["meta"]["user_team_abbrev"] = original_abbrev
            write_save(save_path, restored)

    def _validate_mutation_ownership(
        self,
        league: dict[str, Any],
        manager: dict[str, Any],
        action: str,
        payload: dict[str, Any],
    ) -> None:
        team_id = manager["team_id"]
        human_team_ids = {row["team_id"] for row in league["managers"] if row.get("team_id")}
        if action in {"apply_trade", "apply_trade_candidate"}:
            proposal = payload.get("candidate") or payload.get("proposal") or {}
            proposal = proposal.get("proposal") or proposal
            teams = {proposal.get("from_team_id"), proposal.get("to_team_id")} - {None}
            if team_id not in teams:
                raise MultiplayerAuthorizationError("You can only submit trades involving your team.")
            other_humans = (teams & human_team_ids) - {team_id}
            if other_humans and action == "apply_trade":
                raise MultiplayerAuthorizationError(
                    "Human-to-human trades must use the bilateral candidate-offer flow."
                )
        requested_team = payload.get("team_id")
        if requested_team and requested_team != team_id:
            raise MultiplayerAuthorizationError("You cannot mutate another manager's team.")

    @staticmethod
    def _idempotent_response(
        connection: sqlite3.Connection,
        league_id: str,
        manager_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT response_json FROM idempotent_responses
            WHERE league_id = ? AND manager_id = ? AND idempotency_key = ?
            """,
            (league_id, manager_id, idempotency_key),
        ).fetchone()
        return json.loads(row["response_json"]) if row else None

    @staticmethod
    def _store_idempotent_response(
        connection: sqlite3.Connection,
        league_id: str,
        manager_id: str,
        idempotency_key: str,
        response: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO idempotent_responses
                (league_id, manager_id, idempotency_key, response_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                league_id,
                manager_id,
                idempotency_key,
                json.dumps(to_plain(response), sort_keys=True),
                iso_timestamp(),
            ),
        )

    @staticmethod
    def _human_trade_recipient(
        state: dict[str, Any],
        manager: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidate = payload.get("candidate") or {}
        proposal = candidate.get("proposal") or {}
        teams = {proposal.get("from_team_id"), proposal.get("to_team_id")} - {None}
        if manager.get("team_id") not in teams:
            return None
        return next(
            (
                row
                for row in state.get("managers") or []
                if row.get("id") != manager.get("id") and row.get("team_id") in teams
            ),
            None,
        )

    def _update_save_multiplayer_revision(self, save_path: Path, revision: int) -> None:
        save = ensure_league_save_defaults(load_save(save_path), self.canonical)
        save.setdefault("multiplayer_state", {})["revision"] = int(revision)
        write_save(save_path, save)

    def _decorate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "league" in payload:
            payload = dict(payload)
            payload["league"] = self._decorate(payload["league"])
            return payload
        if not isinstance(payload, dict) or "managers" not in payload:
            return payload
        claimed = {manager.get("team_id") for manager in payload["managers"] if manager.get("team_id")}
        output = dict(payload)
        output["teams"] = [
            {
                "id": team.get("id"),
                "abbrev": team.get("abbrev"),
                "name": team.get("name") or team.get("abbrev"),
                "claimed": team.get("id") in claimed,
            }
            for team in sorted(self.canonical.get("teams", []), key=lambda item: str(item.get("abbrev") or ""))
        ]
        return output

    def _validate_team_id(self, team_id: str) -> None:
        self._team(team_id)

    def _team(self, team_id: str) -> dict[str, Any]:
        team = next((row for row in self.canonical.get("teams", []) if row.get("id") == team_id), None)
        if not team:
            raise MultiplayerError(f"Unknown team id {team_id!r}.")
        return team

    @staticmethod
    def _session(payload: dict[str, Any]) -> dict[str, str]:
        session = {
            "league_id": str(payload.get("league_id") or ""),
            "manager_id": str(payload.get("manager_id") or ""),
            "session_token": str(payload.get("session_token") or ""),
        }
        if not all(session.values()):
            raise MultiplayerAuthenticationError("league_id, manager_id, and session_token are required.")
        return session

    @staticmethod
    def _require_active(state: dict[str, Any]) -> None:
        if state.get("status") != "active" or not state.get("save_path"):
            raise MultiplayerError("League is not active.")

    @contextmanager
    def league_lock(self, league_id: str) -> Iterator[None]:
        with self._league_locks_guard:
            lock = self._league_locks.setdefault(str(league_id), threading.RLock())
        with lock:
            yield


class MultiplayerScheduler:
    """Small daemon scheduler used by the local/hosted single-process server."""

    def __init__(self, service: MultiplayerService, interval_seconds: float = 1.0):
        self.service = service
        self.interval_seconds = max(0.1, float(interval_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="nba-gm-multiplayer-clock", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.service.advance_due_leagues()
            except Exception:
                # One league failure must not terminate clocks for every lobby.
                continue


def clean_label(value: Any, fallback: str, max_length: int) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    return (cleaned or fallback)[:max_length]


def restore_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.restore.", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(payload)
    temp.replace(path)


def human_action_event_kind(action: str) -> str:
    if "trade" in action:
        return "human_trade_action"
    if "staff" in action:
        return "human_staff_action"
    if "contract" in action or "free_agent" in action:
        return "human_contract_action"
    if "draft" in action:
        return "human_draft_action"
    if "rotation" in action or "starting_five" in action:
        return "human_rotation_action"
    return "human_game_action"


def summarize_game_action(action: str, payload: dict[str, Any], result: dict[str, Any]) -> str:
    status = result.get("status") if isinstance(result, dict) else None
    identity = (
        payload.get("proposal_id")
        or payload.get("player_id")
        or payload.get("negotiation_id")
        or payload.get("team")
        or ""
    )
    suffix = f" ({identity})" if identity else ""
    return f"{action}{suffix}: {status or 'completed'}"


def trade_asset_spec(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(asset.get("kind") or ""),
        "value": asset.get("value") or asset.get("id"),
    }


def record_multiplayer_champion(save: dict[str, Any]) -> list[dict[str, Any]]:
    multiplayer = save.setdefault("multiplayer_state", {})
    ledger = list(multiplayer.get("championship_ledger") or [])
    playoff = save.get("playoff_state") or {}
    champion = playoff.get("champion_team_id")
    season = str((save.get("meta") or {}).get("season") or "")
    if (
        playoff.get("status") == "completed"
        and champion
        and season
        and not any(str(row.get("season")) == season for row in ledger)
    ):
        ledger.append({"season": season, "team_id": str(champion)})
    multiplayer["championship_ledger"] = ledger
    return ledger


def dynasty_result(
    save: dict[str, Any],
    managers: list[sqlite3.Row] | list[dict[str, Any]],
    championship_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    historical_records = [
        entry.get("team_records") or {}
        for entry in save.get("season_history") or []
    ]
    historical_records.append(save.get("team_records") or {})
    rows = []
    for manager in managers:
        team_id = str(manager["team_id"])
        titles = sum(1 for title in championship_ledger if str(title.get("team_id")) == team_id)
        wins = sum(int((records.get(team_id) or {}).get("wins") or 0) for records in historical_records)
        losses = sum(int((records.get(team_id) or {}).get("losses") or 0) for records in historical_records)
        rows.append(
            {
                "manager_id": manager["id"],
                "display_name": manager["display_name"],
                "team_id": team_id,
                "championships": titles,
                "regular_season_wins": wins,
                "regular_season_losses": losses,
                "score": titles * 100_000 + wins,
            }
        )
    rows.sort(
        key=lambda row: (
            row["championships"],
            row["regular_season_wins"],
            -row["regular_season_losses"],
            row["display_name"],
        ),
        reverse=True,
    )
    return {
        "method": "championships_then_regular_season_wins",
        "winner": rows[0] if rows else None,
        "standings": rows,
        "championships": championship_ledger,
    }
