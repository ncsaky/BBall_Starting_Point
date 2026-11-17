"""Paired prospective role/development windows on isolated old-career copies."""
import argparse
from collections import defaultdict
from contextlib import nullcontext
from contextlib import closing
from datetime import date, timedelta
import json
from pathlib import Path
import shutil
import sqlite3
import time
from unittest.mock import patch

from audit_roster_floor import rating
from league_health_audit import census
from long_term_health import OUT, canonical, check_inputs, check_protection, fingerprints, sha, write
from nba_gm_data import save as sv
from nba_gm_data.history_store import history_sidecar_path
from nba_gm_data.save_recovery import previous_backup_path, recover_previous_save
from ten_season_soak import SoakRunner, distribution

DEST = Path(__file__).resolve().parents[1] / "output/ai-role-reassessment-2026-10-24"


def group(player):
    if player.get("origin") == "generated_rookie":
        pick = int(player.get("overall_pick") or 999)
        return "top3" if pick <= 3 else "lottery" if pick <= 14 else "later_first" if pick <= 30 else "second_round"
    return "veteran35" if player["age"] >= 35 else "other_baseline"


def snapshot(active, saved):
    snap = census(active, saved)
    pools = defaultdict(list)
    for row in snap["players"]:
        if row["rostered"]:
            pools[group(row)].append(row)
    return {"date": snap["date"], "pools": {key: {"count": len(pool),
            "projected_minutes": distribution(p["minutes"] for p in pool),
            "fixed24_overall": distribution(rating(p) for p in pool)} for key, pool in sorted(pools.items())},
            "players": snap["players"]}


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--seed", type=int, required=True)
    args.add_argument("--arm", choices=("legacy", "reassessed"), required=True)
    args.add_argument("--days", type=int, default=93)
    args.add_argument("--resume-initial", action="store_true")
    args.add_argument("--prepared-backup", type=Path)
    options = args.parse_args()
    check_inputs()
    check_protection()
    original = json.loads((OUT / f"career-{options.seed}/run.json").read_text())["save_path"]
    original_hash = sha(original)
    directory = DEST / "paired" / f"{options.seed}-{options.arm}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "disposable.json"
    if path.exists() and not options.resume_initial:
        raise FileExistsError("Keep completed/partial evidence; use another output directory before rerunning")
    if not path.exists():
        if options.prepared_backup:
            shutil.copy2(options.prepared_backup, previous_backup_path(path))
            recover_previous_save(path)
        else:
            raw = json.loads(Path(original).read_text())
            if raw.get("history_store"):
                database = history_sidecar_path(original, raw)
                with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as source_db, \
                        closing(sqlite3.connect(directory / database.name)) as destination_db:
                    source_db.backup(destination_db)
            shutil.copy2(original, path)
    elif options.resume_initial:
        partial = json.loads((directory / "report.json").read_text())
        assert not partial["checkpoints"], "Only an unadvanced initial copy can be retried"
    saved = sv.load_save(path)
    source = canonical()
    waivers, staff_resolved = 0, 0
    if not options.prepared_backup:
        runner = SoakRunner(argparse.Namespace(root=str(Path(__file__).resolve().parents[1]), output_dir=str(directory), seed=options.seed, team="GSW"))
        runner.canonical, runner.save_dir = source, directory
        runner.payload["save_path"] = str(path)
        waivers = runner.resolve_user_roster_cutdown()
        staff_resolved = runner.resolve_user_staff_retention()
        saved = runner.load()
    start = saved["state"]["current_date"]
    target = (date.fromisoformat(start) + timedelta(days=options.days)).isoformat()
    assert target < "2037-02-01", "This bounded study avoids deadline and offseason decision-policy changes"
    before = snapshot(sv.canonical_with_save(source, saved), saved)
    human_overrides = json.loads(json.dumps(saved.get("rotation_overrides", {})))
    user = saved["meta"]["user_team_id"]
    user_ids = {p["id"] for p in before["players"] if p["team_id"] == user}
    user_priors = {pid: saved["rotation_baselines"][pid] for pid in user_ids}
    report = {"seed": options.seed, "arm": options.arm, "from": start, "target": target,
              "scope": "Real regular-season calendar, games, health, AI transactions and development, from identical year-ten copies. No growth/retirement parameters changed. Not a fresh ten-season equilibrium test.",
              "source_save": original, "source_hash": original_hash, "runtime_hashes": fingerprints(),
              "decision_policy": "Existing soak runner: waive lowest-minutes/OVR legal cutdown candidate; re-sign required user staff at bounded ask.",
              "initial_user_waivers": waivers, "initial_staff_resolutions": staff_resolved,
              "prepared_backup": str(options.prepared_backup) if options.prepared_backup else None,
              "before": before, "checkpoints": [], "status": "running"}
    write(directory / "report.json", report)
    began = time.monotonic()
    mode = patch.object(sv, "reassess_ai_roles", return_value=[]) if options.arm == "legacy" else nullcontext()
    with mode:
        while saved["state"]["current_date"] < target:
            current = saved["state"]["current_date"]
            through = min(target, (date.fromisoformat(current) + timedelta(days=31)).isoformat())
            started = time.monotonic()
            sv.advance_save(Path(__file__).resolve().parents[1], source, path, to_date=through,
                            seed=options.seed, prepared_save=saved)
            assert saved["state"]["current_date"] == through
            assert saved.get("rotation_overrides", {}) == human_overrides
            assert all(saved["rotation_baselines"][pid] == value for pid, value in user_priors.items())
            row = {"date": through, "seconds": round(time.monotonic() - started, 3),
                   "games": len(saved["schedule_state"]["simulated_game_ids"]),
                   "role_teams": len(saved.get("ai_role_state", {}))}
            report["checkpoints"].append(row)
            print(options.seed, options.arm, json.dumps(row), flush=True)
            write(directory / "report.json", report)
    after = snapshot(sv.canonical_with_save(source, saved), saved)
    initial = {p["id"]: p for p in before["players"]}
    stats = saved.get("player_season_stats", {})
    pools = defaultdict(list)
    for row in after["players"]:
        if row["id"] not in initial:
            continue
        prior = initial[row["id"]]
        line = stats.get(row["id"], {})
        games = int(line.get("games") or 0)
        minutes = float(line.get("minutes") or 0)
        pools[group(prior)].append({"id": row["id"], "name": row["name"], "games": games,
                                   "mpg": minutes / games if games else 0, "fixed24_gain": rating(row) - rating(prior),
                                   "rostered": row["rostered"]})
    report.update(after=after, outcomes={key: {"count": len(rows), "played": sum(r["games"] > 0 for r in rows),
                  "rotation": sum(r["games"] >= 10 and r["mpg"] >= 12 for r in rows),
                  "mpg": distribution(r["mpg"] for r in rows), "fixed24_gain": distribution(r["fixed24_gain"] for r in rows),
                  "players": rows} for key, rows in sorted(pools.items())},
                  status="passed", seconds=round(time.monotonic() - began, 3),
                  human_overrides_preserved=True, user_role_priors_preserved=True)
    assert sha(original) == original_hash
    check_protection()
    write(directory / "report.json", report)
    print(options.seed, options.arm, "completed", report["seconds"], flush=True)


if __name__ == "__main__":
    main()
