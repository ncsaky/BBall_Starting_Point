from __future__ import annotations

import json
import sqlite3
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from .schema import CanonicalUniverse, to_plain


JSON_FILENAME = "universe_2025_26_preseason.json"
SQLITE_FILENAME = "universe_2025_26_preseason.sqlite"
COVERAGE_FILENAME = "coverage_report.json"


def write_outputs(universe: CanonicalUniverse, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_FILENAME
    sqlite_path = out / SQLITE_FILENAME
    coverage_path = out / COVERAGE_FILENAME
    write_json(universe, json_path)
    write_json(universe.coverage_report, coverage_path)
    write_sqlite(universe, sqlite_path)
    return {"json": json_path, "sqlite": sqlite_path, "coverage": coverage_path}


def write_json(value: Any, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(to_plain(value), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def load_universe_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_sqlite(universe: CanonicalUniverse, path: Path) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        create_table(conn, "sources", universe.sources)
        create_table(conn, "teams", universe.teams)
        create_table(conn, "players", universe.players)
        create_table(conn, "roster_slots", universe.roster_slots)
        create_table(conn, "traits", universe.traits)
        create_table(conn, "contracts", universe.contracts)
        create_table(conn, "draft_picks", universe.draft_picks)
        create_table(conn, "draft_classes", universe.draft_classes)
        create_table(conn, "draft_prospects", universe.draft_prospects)
        create_table(conn, "draft_prospect_traits", universe.draft_prospect_traits)
        create_table(conn, "scouting_reports", universe.scouting_reports)
        create_table(conn, "draft_board_entries", universe.draft_board_entries)
        create_table(conn, "staff_profiles", universe.staff_profiles)
        create_table(conn, "gameplay_staff_slots", universe.gameplay_staff_slots)
        create_table(conn, "team_profiles", universe.team_profiles)
        create_table(conn, "player_health_profiles", universe.player_health_profiles)
        create_table(conn, "player_health_states", universe.player_health_states)
        create_table(conn, "injury_events", universe.injury_events)
        create_table(conn, "development_events", universe.development_events)
        create_table(conn, "front_office_profiles", universe.front_office_profiles)
        create_table(conn, "team_strategic_states", universe.team_strategic_states)
        create_table(conn, "player_asset_valuations", universe.player_asset_valuations)
        create_table(conn, "player_contract_market_profiles", universe.player_contract_market_profiles)
        create_table(conn, "player_contract_preferences", universe.player_contract_preferences)
        create_table(conn, "extension_candidates", universe.extension_candidates)
        create_table(conn, "free_agent_candidates", universe.free_agent_candidates)
        create_table(conn, "trade_block_entries", universe.trade_block_entries)
        create_table(conn, "coverage_issues", universe.coverage_report.issues)
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        for key, value in sorted(universe.meta.items()):
            conn.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (key, encode_value(value)))
        conn.execute("CREATE TABLE coverage_summary (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        for key, value in sorted(universe.coverage_report.summary.items()):
            conn.execute("INSERT INTO coverage_summary (key, value) VALUES (?, ?)", (key, encode_value(value)))
        conn.commit()
    finally:
        conn.close()


def create_table(conn: sqlite3.Connection, table_name: str, rows: list[Any]) -> None:
    if not rows:
        conn.execute(f"CREATE TABLE {table_name} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        return
    first = rows[0]
    if not is_dataclass(first):
        raise TypeError(f"{table_name} rows must be dataclasses")
    names = [field.name for field in fields(first)]
    columns = ", ".join(f"{name} TEXT" for name in names)
    primary = "PRIMARY KEY(id)" if "id" in names else ""
    ddl = f"CREATE TABLE {table_name} ({columns}{', ' + primary if primary else ''})"
    conn.execute(ddl)
    placeholders = ", ".join("?" for _ in names)
    insert = f"INSERT INTO {table_name} ({', '.join(names)}) VALUES ({placeholders})"
    for row in rows:
        plain = to_plain(row)
        conn.execute(insert, [encode_value(plain.get(name)) for name in names])


def encode_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
