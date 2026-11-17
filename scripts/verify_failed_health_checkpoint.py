"""Fork the failed ninth-year audit checkpoint; never restart its full career."""
import argparse
import cProfile
import gzip
import hashlib
import json
import os
from pathlib import Path
import pstats
import shutil
import signal
import sys
import time
from unittest.mock import patch

SOURCE = Path.home() / ".cache/nba-gm-audits/market-lifecycle-2026-10-25/runtime"
TARGET = Path.home() / ".cache/nba-gm-audits/health-followup-2026-10-26/runtime"
BATCH = "output/health-followup-2026-10-26"
PARENT = SOURCE / "output/market-lifecycle-2026-10-25-r2"


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def prepare():
    if TARGET.exists():
        raise FileExistsError("Follow-up already prepared; do not overwrite its checkpoint")
    assert shutil.disk_usage(SOURCE).free >= 8 * 1024 ** 3
    status = json.loads((PARENT / "status.json").read_text())
    assert status["jobs"]["17"]["status"] == "failed" and status["status"] != "running"
    shutil.copytree(SOURCE, TARGET, ignore=shutil.ignore_patterns("output", "__pycache__", "snapshot.json", "materialization.json"))
    shutil.copy2(Path(__file__), TARGET / "scripts" / Path(__file__).name)
    out = TARGET / BATCH
    career = out / "career-17"
    run = json.loads((PARENT / "career-17/run.json").read_text())
    source_save = Path(run["save_path"])
    raw = json.loads(source_save.read_text())
    assert raw["state"]["current_date"] == run["endpoint"] == "2035-10-01"
    assert len(raw["season_history"]) == 9 and run["target"] == "2036-10-01"
    assert not raw["schedule_state"]["simulated_game_ids"]
    assert all(not p.get("games") for p in raw.get("player_season_stats", {}).values())
    assert raw["lifecycle_state"]["through_date"] == "2035-10-01"
    db = source_save.parent / raw["history_store"]["path"]
    assert not Path(str(db) + "-wal").exists() or Path(str(db) + "-wal").stat().st_size == 0
    source_hashes = {str(p): sha(p) for p in (source_save, db)}
    destination = career / "saves" / source_save.name
    destination.parent.mkdir(parents=True)
    shutil.copy2(source_save, destination)
    shutil.copy2(db, destination.parent / db.name)
    assert sha(destination) == source_hashes[str(source_save)]
    assert sha(destination.parent / db.name) == source_hashes[str(db)]
    run["parent_save_path"] = str(source_save)
    run["save_path"] = str(destination)
    run["status"] = "running"
    write(career / "run.json", run)
    shutil.copy2(PARENT / "career-17/latest-observation.json.gz", career / "latest-observation.json.gz")
    with gzip.open(PARENT / "canonical.json.gz", "rt") as handle:
        canonical = json.load(handle)
    canonical["_baseline_directory"] = str(TARGET / "data/canonical/baselines")
    with gzip.open(out / "canonical.json.gz", "wt", compresslevel=3) as handle:
        json.dump(canonical, handle, separators=(",", ":"))
    manifest = json.loads((PARENT / "manifest.json").read_text())
    manifest.update(seeds=[17], parallel=1, hours=1.5, result_directory_budget_gib=2,
        scope="One final-season continuation from seed 17's nine-season checkpoint; exact parent gameplay runtime plus stable-ID AI extension repair. Not an unchanged fourth replicate.")
    write(out / "manifest.json", manifest)
    write(out / "lineage.json", {"parent": str(PARENT), "source_hashes": source_hashes,
        "checkpoint": "2035-10-01", "target": "2036-10-01",
        "original_pending_action_retained": True,
        "checkpoint_checks": "No current-season games or future lifecycle dates committed; source contains the legal pre-action user roster cutdowns. Fork only, original pending action and saves untouched."})
    print(f"Prepared isolated final-season fork: {out}", flush=True)


def probe():
    assert Path(__file__).resolve().parents[1] == TARGET
    os.chdir(TARGET)
    sys.path[:0] = [str(TARGET / "src"), str(TARGET / "scripts")]
    import overnight_market_health as audit
    from nba_gm_data import contract_ai, transactions

    out = TARGET / BATCH
    old = (SOURCE / "src/nba_gm_data/save.py").read_text()
    new = (TARGET / "src/nba_gm_data/save.py").read_text()
    before = 'negotiate_extension(active, player.get("name", player_id), team.get("abbrev", team_id),'
    after = 'negotiate_extension(active, player_id, team_id,'
    assert before in old and new == old.replace(before, after, 1)
    inventory = json.loads((SOURCE / "snapshot.json").read_text())["files"]
    inventory[f"scripts/{Path(__file__).name}"] = {}
    write(TARGET / "snapshot.json", {"status": "verified", "files": {name: {"sha256": sha(TARGET / name)} for name in inventory}})
    write(out / "inputs.json", {str(path.relative_to(TARGET)): sha(path) for path in audit.inputs()})
    audit.install_local_read_guard(TARGET)
    audit.check_inputs(out)
    collisions = []
    original = contract_ai.negotiate_extension

    def negotiate(context, query, team, *args, **kwargs):
        expected = transactions.resolve_player(context, query)
        old_match = transactions.resolve_player(context, expected["name"])
        if old_match["id"] != expected["id"]:
            collisions.append({"name": expected["name"], "requested_id": query,
                "intended_team": expected["team_id"], "old_name_match_id": old_match["id"],
                "old_name_match_team": old_match["team_id"]})
        return original(context, query, team, *args, **kwargs)

    profiler = cProfile.Profile()
    started = time.monotonic()
    signal.signal(signal.SIGALRM, lambda *args: (_ for _ in ()).throw(TimeoutError("15-minute verification cap")))
    signal.alarm(900)
    try:
        with patch.object(contract_ai, "negotiate_extension", side_effect=negotiate):
            profiler.runcall(audit.step, argparse.Namespace(output_dir=str(out), seed=17, short_days=0))
    finally:
        signal.alarm(0)
        profiler.dump_stats(str(out / "verification.prof"))
    run = json.loads((out / "career-17/run.json").read_text())
    assert run["endpoint"] == "2035-11-01"
    lineage = json.loads((out / "lineage.json").read_text())
    assert all(sha(Path(path)) == value for path, value in lineage["source_hashes"].items())
    stats = pstats.Stats(profiler)
    functions = [{"function": f"{p[0]}:{p[1]}:{p[2]}", "calls": v[1], "self_seconds": round(v[2], 3), "cumulative_seconds": round(v[3], 3)}
                 for p, v in sorted(stats.stats.items(), key=lambda pair: -pair[1][3])[:35]]
    result = {"status": "passed", "endpoint": run["endpoint"], "seconds_with_profiler": round(time.monotonic() - started, 2),
        "same_failed_app_action_now_completes": True, "observed_name_collisions": collisions,
        "original_save_and_database_unchanged": True, "profile": functions,
        "limit": "Profiled verification timing includes save checks and observation overhead; not an unprofiled speed measurement."}
    write(out / "smoke-result.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "probe"))
    globals()[parser.parse_args().mode]()
