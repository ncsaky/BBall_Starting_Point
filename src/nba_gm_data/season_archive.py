"""Finished seasons moved out of the live save (SEASON-ARCHIVE, 2026-11-26).

The live save is read and rewritten every simulated day, so detail from long-finished seasons made every day slower
and the file larger each season. The latest finished season stays whole in the save: the engine reads it (last
season's minutes for option decisions, last season's stats for the award baselines and the preseason outlook, the
staff review, waiver priority). Seasons older than that move, at the first save write after the rollover, to one
compressed file per season beside the save:

    <save stem>.season-<label>.<content hash>.json.gz

Files are written once and named by their content, so a retried or interrupted write can never change a file an
earlier manifest points to. The save keeps a small manifest (``season_archive``) and everything the live game reads:

- ``season_history``: each archived season keeps its standings, awards, Finals MVP, draft result and counts; its
  player season and playoff stats, playoff bracket, draft order and recap move.
- ``season_schedules``: an archived season keeps its schedule's metadata and its first and last regular-season games
  (the season-window and opening-night helpers read only those dates); the other games move.
- ``season_slideshows.outlooks``, ``award_preseason_baselines``: the archived season's entry moves.
- ``game_result_summaries``: the archived season's score lines move (lookups are by game id, and only games of the
  current and previous seasons are reachable from the live schedule, playoffs and player game logs).
- ``injury_events``: finished injuries of an archived season keep a compact row with every field the engine reads
  (dates, body part, severity, sources, expected games); the full row (diagnosis, notes, context) moves.

History views read the archives on demand (``load_season_archive``, with a small cache). Normal play never opens one:
a missing or damaged archive only leaves a history view without the archived detail.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
import tempfile
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)

ARCHIVE_KEY = "season_archive"
ARCHIVE_FORMAT = "nba-gm-season-archive"
ARCHIVE_VERSION = 1
# Finished seasons kept whole in the live save; older ones are archived.
FINISHED_SEASONS_KEPT = 1
HISTORY_DETAIL_KEYS = ("player_season_stats", "playoff_player_stats", "playoff_state", "draft_order", "recap")
# Fields of an archived injury event that stay in the save: every field the engine reads for a finished injury
# (injury-model history: player, date, body part, sources; availability by date; season counts; the AI's games out).
INJURY_LIVE_FIELDS = (
    "id", "player_id", "team_id", "start_date", "return_date", "status", "severity", "body_part", "body_area",
    "source_ids", "expected_games_missed", "plays_injury_game",
)
INJURY_MARKER = "detail_archived"
SCHEDULE_MARKER = "archived_games"
_NAME = re.compile(r"^[^/\\:\0]+\.season-\d{4}-\d{2}\.[0-9a-f]{12}\.json\.gz$")
_LABEL = re.compile(r"^(\d{4})-(\d{2})$")
_PLAYOFF_ID = re.compile(r"^playoff_game_(\d{4})")
_SEASON_IN_ID = re.compile(r"(?<!\d)(\d{4})-(\d{2})(?!\d)")
_CACHE: "OrderedDict[tuple[str, str], dict[str, Any]]" = OrderedDict()
_CACHE_LIMIT = 6


# ------------------------------------------------------------------------------------------------ season labels


def season_label(start_year: int) -> str:
    return f"{int(start_year)}-{str(int(start_year) + 1)[-2:]}"


def season_start(label: Any) -> int | None:
    match = _LABEL.match(str(label or ""))
    return int(match.group(1)) if match else None


def season_of_date(value: Any) -> str | None:
    """The season a date belongs to (seasons run July 1 - June 30)."""
    text = str(value or "")[:10]
    if len(text) < 7 or not text[:4].isdigit() or not text[5:7].isdigit():
        return None
    year, month = int(text[:4]), int(text[5:7])
    return season_label(year if month >= 7 else year - 1)


def season_of_game_id(game_id: Any) -> str | None:
    """The season in a game id: play-in and playoff ids carry the playoff year, generated regular-season ids the
    season label."""
    text = str(game_id or "")
    match = _PLAYOFF_ID.match(text)
    if match:
        return season_label(int(match.group(1)) - 1)
    match = _SEASON_IN_ID.search(text)
    if match and int(match.group(2)) == (int(match.group(1)) + 1) % 100:
        return season_label(int(match.group(1)))
    return None


def last_archived_start(save: dict[str, Any]) -> int | None:
    """Start year of the newest season that belongs in the archive (None: nothing does yet)."""
    current = season_start((save.get("meta") or {}).get("season"))
    if current is None:
        return None
    return current - 1 - FINISHED_SEASONS_KEPT


# ------------------------------------------------------------------------------------------------ the split


def split_finished_seasons(save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Take every archived season's detail out of ``save`` (in place); returns {season label: tables moved}."""
    last = last_archived_start(save)
    if last is None:
        return {}
    payloads: dict[str, dict[str, Any]] = {}

    def eligible(label: str | None) -> bool:
        start = season_start(label)
        return start is not None and start <= last

    def bucket(label: str) -> dict[str, Any]:
        return payloads.setdefault(label, {})

    for entry in save.get("season_history") or []:
        label = str(entry.get("season") or "")
        if not eligible(label):
            continue
        moved = {key: entry.pop(key) for key in HISTORY_DETAIL_KEYS if key in entry}
        if moved:
            bucket(label)["season_history"] = moved

    for label, schedule in list((save.get("season_schedules") or {}).items()):
        if not eligible(label) or not isinstance(schedule, dict) or SCHEDULE_MARKER in schedule:
            continue
        games = list(schedule.get("games") or [])
        kept = _window_games(games)
        bucket(label)["schedule_games"] = games
        save["season_schedules"][label] = {**{k: v for k, v in schedule.items() if k != "games"},
                                           "games": kept, SCHEDULE_MARKER: len(games)}

    outlooks = (save.get("season_slideshows") or {}).get("outlooks") or {}
    for label in [label for label in outlooks if eligible(label)]:
        bucket(label)["outlook"] = outlooks.pop(label)

    baselines = save.get("award_preseason_baselines") or {}
    for label in [label for label in baselines if eligible(label)]:
        bucket(label)["award_preseason_baselines"] = baselines.pop(label)

    # Every save write runs this, so rows are first screened by plain string comparison (ISO dates sort as text).
    cutoff = f"{last + 1}-07-01"
    newest_playoffs = str(last + 1)

    def old_date(value: Any) -> bool:
        return bool(value) and str(value)[:10] < cutoff and eligible(season_of_date(value))

    def old_game(game_id: Any) -> bool:
        text = str(game_id or "")
        if text.startswith("playoff_game_") and text[13:17].isdigit():
            return text[13:17] <= newest_playoffs
        return eligible(season_of_game_id(text))

    summaries = save.get("game_result_summaries")
    if summaries:
        kept_rows = []
        for row in summaries:
            date_value = row.get("date")
            if not (old_date(date_value) if date_value else old_game(row.get("game_id"))):
                kept_rows.append(row)
                continue
            label = season_of_date(date_value) or season_of_game_id(row.get("game_id"))
            if eligible(label):
                bucket(label).setdefault("game_result_summaries", []).append(row)
            else:
                kept_rows.append(row)
        if len(kept_rows) != len(summaries):
            save["game_result_summaries"] = kept_rows

    events = save.get("injury_events") or []
    candidates = [index for index, event in enumerate(events)
                  if INJURY_MARKER not in event and old_date(event.get("start_date"))]
    if candidates:
        open_ids = _open_injury_ids(save)
        for index in candidates:
            event = events[index]
            label = season_of_date(event.get("start_date"))
            floor = f"{season_start(label) + 1}-07-01"
            if event.get("id") in open_ids or not event.get("return_date") or str(event["return_date"])[:10] >= floor:
                continue   # still running, or never closed: stays whole
            bucket(label).setdefault("injury_events", []).append(event)
            events[index] = {**{key: event[key] for key in INJURY_LIVE_FIELDS if key in event}, INJURY_MARKER: label}
    return payloads


def _window_games(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The regular-season games that fix a schedule's first and last dates, for both date readers (``gameDate`` and
    ``gameDate or date``)."""
    regular = [game for game in games if isinstance(game, dict) and game.get("phase") == "regular"]
    keep: list[int] = []
    for pick in (lambda g: g.get("gameDate") or g.get("date"), lambda g: g.get("gameDate")):
        dated = [(str(pick(game))[:10], index) for index, game in enumerate(regular) if pick(game)]
        if dated:
            keep += [min(dated)[1], max(dated)[1]]
    return [deepcopy(regular[index]) for index in sorted(set(keep))]


def _open_injury_ids(save: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for state in save.get("health_states") or []:
        if not isinstance(state, dict):
            continue
        for key in ("current_injury_id", "injury_id"):
            if state.get(key):
                ids.add(str(state[key]))
        pending = state.get("pending_injury")
        if isinstance(pending, dict) and pending.get("id"):
            ids.add(str(pending["id"]))
    return ids


# ------------------------------------------------------------------------------------------------ writing


def archive_finished_seasons(save_path: str | Path, save: dict[str, Any]) -> dict[str, int]:
    """Move archived seasons' detail out of ``save`` into their files (the caller holds the save lock and writes the
    manifest afterwards). Returns {season: archive bytes} for the files written."""
    payloads = split_finished_seasons(save)
    if not payloads:
        return {}
    target = Path(save_path)
    manifest = save.setdefault(ARCHIVE_KEY, {"version": ARCHIVE_VERSION, "seasons": {}})
    manifest["version"] = ARCHIVE_VERSION
    seasons = manifest.setdefault("seasons", {})
    written: dict[str, int] = {}
    for label in sorted(payloads):
        tables = payloads[label]
        previous = seasons.get(label)
        if previous:
            existing = load_season_archive(target, save, label)
            if existing is None:
                raise OSError(f"season archive for {label} is missing or damaged; cannot add to it")
            tables, changed = _merge_tables(existing.get("tables") or {}, tables)
            if not changed:
                continue   # rows rebuilt from the history database that the archive already holds
        document = {"format": ARCHIVE_FORMAT, "version": ARCHIVE_VERSION, "season": label, "tables": tables}
        raw = json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        packed = gzip.compress(raw, compresslevel=6, mtime=0)
        digest = hashlib.sha256(packed).hexdigest()
        name = f"{target.stem}.season-{label}.{digest[:12]}.json.gz"
        path = target.parent / name
        if not (path.is_file() and path.stat().st_size == len(packed)):
            _atomic_write(path, packed)
        seasons[label] = {"file": name, "sha256": digest, "bytes": len(packed), "json_bytes": len(raw),
                          "contents": {key: _count(value) for key, value in sorted(tables.items())},
                          "recap": bool((tables.get("season_history") or {}).get("recap"))}
        _CACHE[(str(path), digest)] = document
        _trim_cache()
        written[label] = len(packed)
    return written


# Rows of an archived season that can reach the live save again: a view that loads the whole history database
# (``load_save(include_history=True)``) and then writes rebuilds the score lines of the old box scores it still holds
# (history_store.materialize_game_summaries). They replace the archived row with the same key, as they replaced the
# live row before the archive existed.
_ROW_KEYS = {"game_result_summaries": "game_id", "injury_events": "id", "schedule_games": "externalGameId"}


def _merge_tables(old: dict[str, Any], new: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """``old`` with ``new`` added (same-key rows replaced); also whether anything changed. ``old`` is not modified."""
    merged = dict(old)
    changed = False
    for key, value in new.items():
        if key not in merged:
            merged[key], changed = value, True
        elif key in _ROW_KEYS:
            field = _ROW_KEYS[key]
            rows = list(merged[key])
            index = {row.get(field): position for position, row in enumerate(rows)}
            for row in value:
                position = index.get(row.get(field))
                if position is None:
                    index[row.get(field)] = len(rows)
                    rows.append(row)
                    changed = True
                elif rows[position] != row:
                    rows[position] = row
                    changed = True
            merged[key] = rows
        elif isinstance(value, dict):
            updated = {**merged[key], **value}
            changed = changed or updated != merged[key]
            merged[key] = updated
        elif isinstance(value, list):
            merged[key], changed = [*merged[key], *value], True
        elif merged[key] != value:
            merged[key], changed = value, True
    return merged, changed


def _count(value: Any) -> int:
    return len(value) if isinstance(value, (list, dict)) else 1


def _atomic_write(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


# ------------------------------------------------------------------------------------------------ reading


def archive_entries(save: dict[str, Any]) -> dict[str, dict[str, Any]]:
    manifest = save.get(ARCHIVE_KEY) or {}
    seasons = manifest.get("seasons") if isinstance(manifest, dict) else None
    return seasons if isinstance(seasons, dict) else {}


def archive_file_path(save_path: str | Path, entry: dict[str, Any]) -> Path | None:
    name = str((entry or {}).get("file") or "")
    if not _NAME.match(name):
        return None
    return Path(save_path).parent / name


def load_season_archive(save_path: str | Path | None, save: dict[str, Any], label: str) -> dict[str, Any] | None:
    """One archived season ({"tables": ...}), or None when the save has none for it or it cannot be read."""
    entry = archive_entries(save).get(str(label))
    if not entry or save_path is None:
        return None
    path = archive_file_path(save_path, entry)
    if path is None:
        LOG.warning("season archive for %s has an unsafe file name", label)
        return None
    key = (str(path), str(entry.get("sha256") or ""))
    cached = _CACHE.get(key)
    if cached is not None:
        _CACHE.move_to_end(key)
        return cached
    try:
        packed = path.read_bytes()
        if hashlib.sha256(packed).hexdigest() != entry.get("sha256"):
            raise ValueError("checksum mismatch")
        document = json.loads(gzip.decompress(packed))
        if document.get("format") != ARCHIVE_FORMAT or document.get("season") != label:
            raise ValueError("not this season's archive")
    except (OSError, ValueError, EOFError) as exc:
        LOG.warning("season archive %s unreadable: %s", path.name, exc)
        return None
    _CACHE[key] = document
    _trim_cache()
    return document


def _trim_cache() -> None:
    while len(_CACHE) > _CACHE_LIMIT:
        _CACHE.popitem(last=False)


def archived_tables(save_path: str | Path | None, save: dict[str, Any], label: str) -> dict[str, Any]:
    document = load_season_archive(save_path, save, label)
    return (document or {}).get("tables") or {}


def archive_holds(save: dict[str, Any], label: str, table: str) -> bool:
    """True when ``label``'s archive holds ``table`` (manifest only; no file read)."""
    return table in ((archive_entries(save).get(str(label)) or {}).get("contents") or {})


def full_history_entry(save_path: str | Path | None, save: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """A season history entry with its archived detail put back (the entry itself when nothing was archived)."""
    label = str(entry.get("season") or "")
    if not archive_holds(save, label, "season_history"):
        return entry
    detail = archived_tables(save_path, save, label).get("season_history") or {}
    return {**entry, **detail} if detail else entry


def full_season_history(save_path: str | Path | None, save: dict[str, Any]) -> list[dict[str, Any]]:
    return [full_history_entry(save_path, save, entry) for entry in save.get("season_history") or []]


def archived_outlook(save_path: str | Path | None, save: dict[str, Any], label: str) -> dict[str, Any] | None:
    if not archive_holds(save, label, "outlook"):
        return None
    return archived_tables(save_path, save, label).get("outlook")


def archived_outlook_seasons(save: dict[str, Any]) -> list[str]:
    return [label for label in archive_entries(save) if archive_holds(save, label, "outlook")]


def archived_recap_seasons(save: dict[str, Any]) -> list[str]:
    """Seasons whose history entry's recap moved to the archive (manifest only)."""
    out = []
    for label, entry in archive_entries(save).items():
        if entry.get("recap") is True:
            out.append(label)
    return out


def full_injury_events(save_path: str | Path | None, save: dict[str, Any]) -> list[dict[str, Any]]:
    """The save's injury events with each archived event's full row in place of its compact row (same order)."""
    events = save.get("injury_events") or []
    labels = sorted({str(event[INJURY_MARKER]) for event in events if INJURY_MARKER in event})
    if not labels:
        return events
    full: dict[str, dict[str, Any]] = {}
    for label in labels:
        for row in archived_tables(save_path, save, label).get("injury_events") or []:
            if row.get("id"):
                full[str(row["id"])] = row
    return [full.get(str(event.get("id")), event) if INJURY_MARKER in event else event for event in events]


def archive_sizes(save_path: str | Path, save: dict[str, Any]) -> dict[str, int]:
    return {label: int(entry.get("bytes") or 0) for label, entry in sorted(archive_entries(save).items())}
