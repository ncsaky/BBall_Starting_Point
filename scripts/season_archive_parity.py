#!/usr/bin/env python3
"""History views before and after the season archive (SEASON-ARCHIVE, 2026-11-26).

``dump`` copies one save (with its history database and any season archive files) into a fresh folder, writes it
once with the code on PYTHONPATH (new code: finished seasons move to their archive files), then records the server's
data responses for every history view: player pages (career tables), team pages (injury timelines), standings,
leaders, awards and league events, the slideshows (every recap and outlook the save can reopen), playoffs, calendar,
box score and the dashboard. Run it once with the old code and once with the new code on the same save, then
``compare`` the two dumps.

  PYTHONPATH=<old>/src python scripts/season_archive_parity.py dump --save S --folder output/sa/parity/old --out old.json
  PYTHONPATH=src       python scripts/season_archive_parity.py dump --save S --folder output/sa/parity/new --out new.json
  python scripts/season_archive_parity.py compare old.json new.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

# Keys whose values name the copy's own files or the moment of the run, not the history shown.
VOLATILE = {"save_path", "save_snapshot_id", "snapshot_id", "history_store", "season_archive", "generated_at",
            "elapsed_seconds", "seconds", "cache", "revision", "save_revision", "path"}


def copy_save(source: Path, folder: Path) -> Path:
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    manifest = json.loads(source.read_text())
    shutil.copy2(source, folder / source.name)
    db = (manifest.get("history_store") or {}).get("path")
    if db:
        shutil.copy2(source.parent / db, folder / db)
    for entry in ((manifest.get("season_archive") or {}).get("seasons") or {}).values():
        shutil.copy2(source.parent / entry["file"], folder / entry["file"])
    return folder / source.name


def sample_players(manifest: dict[str, Any], every: int) -> list[str]:
    """Players with history: every n-th player of the earliest finished season, its retired players, and the
    user's roster of the latest season (chosen from the input file, so both runs ask for the same players)."""
    history = manifest.get("season_history") or []
    if not history:
        return []
    first = sorted((history[0].get("player_season_stats") or {}))
    latest = history[-1].get("player_season_stats") or {}
    retired = [pid for pid in manifest.get("retired_player_ids") or [] if pid in set(first)]
    user = (manifest.get("meta") or {}).get("user_team_id")
    roster = sorted(pid for pid, row in latest.items() if row.get("team_id") == user)
    return list(dict.fromkeys([*first[::every], *retired[:12], *roster]))


def dump(args: argparse.Namespace) -> int:
    from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
    from nba_gm_data.save import load_save, write_save

    root = Path(__file__).resolve().parents[1]
    import nba_gm_data
    code_root = Path(nba_gm_data.__file__).resolve().parents[2]
    source = Path(args.save).resolve()
    players = sample_players(json.loads(source.read_text()), args.every)
    path = copy_save(source, Path(args.folder).resolve())
    started = time.time()
    write_save(path, load_save(path))
    canonical = load_app_canonical(code_root)
    saved = json.loads(path.read_text())
    user = (saved.get("meta") or {}).get("user_team_abbrev") or "MIA"
    teams = [user, *[abbrev for abbrev in args.teams.split(",") if abbrev and abbrev != user]]
    out: dict[str, Any] = {"code_root": str(code_root), "save": str(source), "players": players, "responses": {}}

    def call(key: str, action: str, **payload: Any) -> Any:
        try:
            result = dispatch_app_action(action, {"save_path": str(path), **payload}, root=code_root,
                                         save_dir=path.parent, canonical=canonical)
        except Exception as exc:  # recorded: an error must match too
            result = {"error": f"{type(exc).__name__}: {exc}"}
        out["responses"][key] = json.loads(json.dumps(result, default=str))
        return result

    status = call("save_status", "save_status")
    for action in ("home", "standings", "dashboard_summary_leaders", "league_events", "social_feed", "calendar",
                   "playoff_room", "playoff_leaders", "staff_room", "draft_board"):
        call(action, action, **({"limit": 400} if action == "league_events" else {}))
    for stat in ("points", "rebounds", "assists"):
        call(f"league_leaders:{stat}", "league_leaders", stat=stat, limit=40)
    for team in teams:
        call(f"team_dashboard:{team}", "team_dashboard", team=team)
    call("team_assets", "team_assets", team=user)
    call("dashboard_trends", "dashboard_trends", team=user)
    slideshows = []
    for source_payload in (status, out["responses"].get("home") or {}):
        found = (source_payload.get("season_slideshow") or {}).get("available") if isinstance(source_payload, dict) else None
        if found:
            slideshows = found
            break
    if not slideshows:
        listing = call("season_slideshow:list", "season_slideshow", kind="outlook")
        slideshows = (listing or {}).get("available") or []
    for row in slideshows:
        call(f"season_slideshow:{row['kind']}:{row['season']}", "season_slideshow", kind=row["kind"], season=row["season"])
    for player_id in players:
        call(f"player_card:{player_id}", "player_card", player_id=player_id)
    results = saved.get("game_results") or []
    if results:
        call("box_score", "box_score", game_id=results[-1]["game_id"])
    out["seconds"] = round(time.time() - started, 1)
    out["save_mb"] = round(path.stat().st_size / 1e6, 2)
    Path(args.out).write_text(json.dumps(out, sort_keys=True))
    print(json.dumps({"responses": len(out["responses"]), "players": len(players), "slideshows": len(slideshows),
                      "seconds": out["seconds"], "save_mb": out["save_mb"]}))
    return 0


def normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items() if key not in VOLATILE}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if isinstance(value, str) and "/output/" in value:
        return "<path>"
    return value


def differences(left: Any, right: Any, where: str, found: list[str], limit: int = 20) -> None:
    if len(found) >= limit or left == right:
        return
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            differences(left.get(key), right.get(key), f"{where}.{key}", found, limit)
    elif isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        for index, (a, b) in enumerate(zip(left, right)):
            differences(a, b, f"{where}[{index}]", found, limit)
    else:
        found.append(f"{where}: {json.dumps(left, default=str)[:160]} != {json.dumps(right, default=str)[:160]}")


def compare(args: argparse.Namespace) -> int:
    left, right = (json.loads(Path(p).read_text())["responses"] for p in args.dumps)
    keys = sorted(set(left) | set(right))
    report = {"views": len(keys), "identical": 0, "differing": {}}
    for key in keys:
        found: list[str] = []
        differences(normalized(left.get(key)), normalized(right.get(key)), key, found)
        if found:
            report["differing"][key] = found
        else:
            report["identical"] += 1
    print(json.dumps(report, indent=1))
    return 0 if not report["differing"] else 1


def unsplit(path: Path, save: dict[str, Any]) -> dict[str, Any]:
    """The save as it would be without the archive: every archived row put back where the old code kept it."""
    from nba_gm_data import season_archive as sa

    out = dict(save)
    entries = sa.archive_entries(save)
    if not entries:
        return out
    tables = {label: sa.archived_tables(path, save, label) for label in sorted(entries)}
    missing = [label for label in entries if not tables[label]]
    if missing:
        raise SystemExit(f"archives unreadable: {missing}")
    out["season_history"] = sa.full_season_history(path, save)
    out["injury_events"] = sa.full_injury_events(path, save)
    schedules = dict(save.get("season_schedules") or {})
    for label, table in tables.items():
        if "schedule_games" in table:
            stub = {k: v for k, v in schedules[label].items() if k != sa.SCHEDULE_MARKER}
            schedules[label] = {**stub, "games": table["schedule_games"]}
    out["season_schedules"] = schedules
    slides = dict(save.get("season_slideshows") or {})
    slides["outlooks"] = {**{label: t["outlook"] for label, t in tables.items() if "outlook" in t}, **(slides.get("outlooks") or {})}
    out["season_slideshows"] = slides
    out["award_preseason_baselines"] = {**{label: t["award_preseason_baselines"] for label, t in tables.items()
                                           if "award_preseason_baselines" in t}, **(save.get("award_preseason_baselines") or {})}
    rows = [row for t in tables.values() for row in t.get("game_result_summaries") or []] + list(save.get("game_result_summaries") or [])
    out["game_result_summaries"] = sorted(rows, key=lambda row: (str(row.get("date") or ""), str(row.get("game_id") or "")))
    stats = {pid: dict(row) for pid, row in (save.get("playoff_player_stats") or {}).items()}
    for t in tables.values():
        for pid, ids in (t.get("playoff_game_ids") or {}).items():
            stats[pid]["_old"] = [*stats[pid].get("_old", []), *ids]
    for row in stats.values():
        if "_old" in row:
            row["game_ids"] = [*row.pop("_old"), *row.get("game_ids", [])]
    out["playoff_player_stats"] = stats
    out.pop(sa.ARCHIVE_KEY, None)
    return out


def compare_saves(args: argparse.Namespace) -> int:
    """Two saves of the same moment, old code and new code: identical once the archives are put back?"""
    from nba_gm_data.save import load_save

    volatile = {"history_store", "season_archive"}
    loaded = []
    for name in args.saves:
        path = Path(name)
        save = unsplit(path, load_save(path))
        save = {k: v for k, v in save.items() if k not in volatile}
        save["meta"] = {k: v for k, v in (save.get("meta") or {}).items() if k not in {"save_snapshot_id", "canonical_hash"}}
        loaded.append(save)
    left, right = loaded
    differing = sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))
    detail: list[str] = []
    for key in differing[:5]:
        differences(left.get(key), right.get(key), key, detail, limit=8)
    print(json.dumps({"identical": not differing, "differing": differing, "detail": detail}, indent=1))
    return 0 if not differing else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_dump = sub.add_parser("dump")
    p_dump.add_argument("--save", required=True)
    p_dump.add_argument("--folder", required=True)
    p_dump.add_argument("--out", required=True)
    p_dump.add_argument("--every", type=int, default=12, help="every n-th player of the first finished season")
    p_dump.add_argument("--teams", default="BOS,DEN,LAL,OKC,NYK")
    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("dumps", nargs=2)
    p_saves = sub.add_parser("saves", help="compare two saves of the same moment after putting archives back")
    p_saves.add_argument("saves", nargs=2)
    args = parser.parse_args()
    return {"dump": dump, "compare": compare, "saves": compare_saves}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
