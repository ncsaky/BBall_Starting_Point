"""Measure a copied career. Prototype databases are temporary and cannot be loaded by the game."""
import argparse
import json
import re
import sqlite3
import tempfile
import time
import zipfile
import zlib
from collections import Counter, defaultdict
from contextlib import ExitStack, closing
from pathlib import Path

from nba_gm_data.history_store import validate_save_components
from nba_gm_data.save_recovery import create_export, SaveRecoveryError


BOX_KINDS = {"game_results", "player_game_logs", "team_game_logs"}
SEASON = re.compile(r"^(\d{4})-\d{2}$")
DATE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])(?:-\d{2})?$")
PLAYOFF = re.compile(r"^playoff_game_(\d{4})-")
DRAFT_COLLECTIONS = {"draft_orders", "draft_rights", "generated_players",
                     "incoming_rookies", "rookie_contracts", "prospect_preseason_ranks"}
ROOKIE_COLLECTIONS = {"generated_traits", "generated_health_profiles"}
LIVE_COLLECTIONS = {"player_season_stats", "team_records",
                    "playoff_state", "league_awards", "finals_mvp", "schedule_state",
                    "lifecycle_state"}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def dated(value):
    match = DATE.fullmatch(str(value or "")[:10])
    if match:
        year, month = map(int, match.groups())
        return year - (month < 7)
    return None


def season_label(value):
    match = SEASON.fullmatch(str(value or ""))
    if match:
        year = int(match[1])
        if int(value[-2:]) == (year + 1) % 100:
            return year
    return None


def game_year(game_id, summary_years):
    if game_id in summary_years:
        return summary_years[game_id]
    playoff = PLAYOFF.match(game_id or "")
    return int(playoff[1]) - 1 if playoff else None


def record_year(kind, key, row, summaries, rookie_years):
    if kind in DRAFT_COLLECTIONS:
        draft = row.get("draft_year") if isinstance(row, dict) else None
        if kind in {"draft_orders", "prospect_preseason_ranks"}:
            draft = str(key).split(":")[-1]
        return int(draft) - 1 if draft and str(draft).isdigit() else None
    if kind in ROOKIE_COLLECTIONS:
        return rookie_years.get(row.get("player_id") if kind == "generated_traits" else key)
    if not isinstance(row, dict):
        return None
    year = season_label(row.get("season"))
    if year is not None:
        return year
    year = game_year(row.get("game_id"), summaries)
    if year is not None:
        return year
    for field in ("date", "start_date", "month", "created_date", "generated_date"):
        year = dated(row.get(field))
        if year is not None:
            return year
    return None


def json_inventory(save, summaries, active):
    rookie_years = {r["id"]: int(r["draft_year"]) - 1 for r in save["generated_players"]}
    sizes = defaultdict(Counter)
    nested_season_history = defaultdict(Counter)
    for kind, value in save.items():
        sizes[kind]["total"] = len(encoded(kind)) + len(encoded(value)) + 2
        if kind == "playoff_player_stats":
            # These counters are cumulative in this checkpoint. Only the game
            # ID lists have a season for each item.
            for totals in value.values():
                for game_id in totals.get("game_ids", []):
                    year = game_year(game_id, summaries)
                    sizes[kind][year if year is not None else "undated"] += len(encoded(game_id)) + 1
            continue
        if kind in LIVE_COLLECTIONS:
            sizes[kind][active] = sizes[kind]["total"]
            continue
        parts = enumerate(value) if isinstance(value, list) else value.items() if isinstance(value, dict) else ()
        for key, row in parts:
            year = season_label(key)
            if year is None:
                year = record_year(kind, key, row, summaries, rookie_years)
            length = len(encoded(row)) + 1
            if isinstance(value, dict):
                length += len(encoded(key)) + 1
            sizes[kind][year if year is not None else "undated"] += length
            if kind == "season_history":
                for field, item in row.items():
                    nested_season_history[field][year] += len(encoded(item))
    return sizes, nested_season_history


def zip_size(members, destination):
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in members.items():
            archive.write(path, name)
    return destination.stat().st_size


def write_variants(source, store, summary_years, active, temporary, json_path):
    indexes = [sql for (sql,) in source.execute(
        "SELECT sql FROM sqlite_schema WHERE type='index' AND sql IS NOT NULL"
    )]
    table, = source.execute("SELECT sql FROM sqlite_schema WHERE name='history_records'").fetchone()
    commits_table, = source.execute("SELECT sql FROM sqlite_schema WHERE name='history_commits'").fetchone()
    revision = store["revision"]
    insert_sql = "INSERT INTO history_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    raw = defaultdict(Counter)
    visible = defaultdict(Counter)
    inventory = Counter()
    game_fields = defaultdict(Counter)
    filtered = Counter()
    cases = ("latest", "deflated", "two_seasons", "portable_split",
             "old_latest", "old_deflated", "old_two_seasons", "old_portable_split")
    paths = {case: temporary / f"{case}.sqlite3" for case in cases}
    with ExitStack() as stack:
        targets = {name: stack.enter_context(closing(sqlite3.connect(path))) for name, path in paths.items()}
        for target in targets.values():
            target.execute(f"PRAGMA page_size={source.execute('PRAGMA page_size').fetchone()[0]}")
            target.execute(table)
            target.execute(commits_table)
        query = """
            WITH latest AS (
                SELECT kind, record_id, MAX(revision) AS revision FROM history_records
                WHERE revision <= ? GROUP BY kind, record_id
            )
            SELECT h.*, latest.revision IS NOT NULL
            FROM history_records h LEFT JOIN latest USING (kind, record_id, revision)
            ORDER BY h.rowid
        """
        for *fields, payload, is_latest in source.execute(query, (revision,)):
            kind, _, date, season, _, game_id, _, _ = fields
            year = season_label(season)
            if year is None:
                year = game_year(game_id, summary_years)
            if year is None:
                year = dated(date)
            if year is None:
                year = "undated"
            data = payload.encode()
            raw[kind][year] += len(data)
            if not is_latest:
                filtered[kind] += 1
                continue
            inventory[kind] += 1
            visible[kind][year] += len(data)
            targets["latest"].execute(insert_sql, (*fields, payload))
            compressed = zlib.compress(data)
            assert zlib.decompress(compressed) == data
            targets["deflated"].execute(insert_sql, (*fields, compressed))
            old = isinstance(year, int) and year < active - 1
            if old:
                targets["old_latest"].execute(insert_sql, (*fields, payload))
                targets["old_deflated"].execute(insert_sql, (*fields, compressed))
            for case, omitted in (("two_seasons", BOX_KINDS),
                                  ("portable_split", BOX_KINDS | {"development_events", "news_items"})):
                if not old or kind not in omitted:
                    targets[case].execute(insert_sql, (*fields, payload))
                    if old:
                        targets["old_" + case].execute(insert_sql, (*fields, payload))
            if kind == "game_results":
                box = json.loads(payload)
                for field, value in box.items():
                    game_fields[field][year] += len(encoded(value))
                for key, value in (box.get("plus_minus_tracking") or {}).items():
                    game_fields["plus_minus_tracking." + key][year] += len(encoded(value))
        assert inventory == Counter(store["archived_counts"])
        for label, target in targets.items():
            counts = dict(target.execute("SELECT kind, COUNT(*) FROM history_records GROUP BY kind"))
            target.execute("INSERT INTO history_commits VALUES (?, ?, ?)",
                           (revision, store["snapshot_id"], json.dumps(counts, sort_keys=True)))
            for index in indexes:
                target.execute(index)
            target.commit()
            assert target.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            if label in {"latest", "deflated"}:
                assert counts == inventory
        return raw, visible, filtered, game_fields, {
            label: {"db_bytes": path.stat().st_size,
                    "zip_bytes": zip_size({"history.sqlite3": path} if label.startswith("old_") else
                                          {"save.json": json_path, "history.sqlite3": path},
                                          temporary / "measure.zip")}
            for label, path in paths.items()
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copied_save", type=Path)
    args = parser.parse_args()
    json_path = args.copied_save.resolve()
    allowed_root = Path("output/sav").resolve()
    if not json_path.is_relative_to(allowed_root):
        parser.error("pass a copied save under output/sav")
    save = json.loads(json_path.read_bytes())
    store = save["history_store"]
    database = (json_path.parent / store["path"]).resolve()
    if not database.is_relative_to(allowed_root):
        parser.error("the copied history must also be under output/sav")
    active = season_label(save["meta"]["season"])
    summaries = {}
    for row in save["game_result_summaries"]:
        year = dated(row.get("date"))
        if year is None:
            year = game_year(row["game_id"], {})
        if year is not None:
            summaries[row["game_id"]] = year

    start = time.perf_counter()
    validate_save_components(json_path, save)
    validation_seconds = time.perf_counter() - start
    try:
        create_export(json_path)
        export_error = None
    except SaveRecoveryError as exc:
        export_error = str(exc)

    with tempfile.TemporaryDirectory(dir=allowed_root) as tmp:
        temporary = Path(tmp)
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:
            pages = dict(source.execute("SELECT name, SUM(pgsize) FROM dbstat GROUP BY name"))
            raw, visible, filtered, game_fields, variants = write_variants(
                source, store, summaries, active, temporary, json_path
            )
        json_zip = zip_size({"save.json": json_path}, temporary / "measure.zip")
        original_zip = zip_size({"save.json": json_path, "history.sqlite3": database}, temporary / "measure.zip")
    kinds, history = json_inventory(save, summaries, active)
    json_bytes = json_path.stat().st_size
    assert sum(row["total"] for row in kinds.values()) + 2 == json_bytes
    print(json.dumps({
        "save": str(json_path), "meta": save["meta"], "state": save["state"], "history_store": store,
        "json_bytes": json_bytes, "db_bytes": database.stat().st_size,
        "db_pages": pages, "original_zip_bytes": original_zip, "json_zip_bytes": json_zip, "export_error": export_error,
        "validation_seconds": validation_seconds, "db_all_payload_bytes": raw,
        "db_visible_payload_bytes": visible, "db_superseded_rows": filtered,
        "game_fields": game_fields, "json_bytes_by_kind": kinds, "season_history_values": history,
        "variants": variants,
    }, indent=2))


if __name__ == "__main__":
    main()
