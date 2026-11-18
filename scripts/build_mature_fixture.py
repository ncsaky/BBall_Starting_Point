#!/usr/bin/env python3
"""Build the seed-17 legacy roster probe through real, AI-enabled app actions.

Run with PYTHONPATH=src:scripts .venv/bin/python -u scripts/build_mature_fixture.py.
Re-running resumes the last completed action from output/t2b/checkpoint.nbagm.zip,
including its history sidecars. A failed action is never used as a checkpoint.
"""
from __future__ import annotations

import argparse
import fcntl
import gc
import hashlib
import json
import lzma
from pathlib import Path
import shutil
import time
import traceback

from overnight_market_health import marker, select_action
from ten_season_soak import SoakRunner
from nba_gm_data.save_recovery import restore_export
from nba_gm_data.utils import clear_utility_caches

ROOT = Path(__file__).resolve().parents[1]
TARGET = "2036-11-01"
# Roster/contract/health/rotation dependencies from the original extractor.
# Keep hot development events intact rather than changing floating-point sums.
FIELDS = set("""version meta state generated_players generated_traits generated_health_profiles
incoming_rookies retired_player_ids roster_overrides draft_pick_overrides generated_draft_picks
draft_orders pick_obligations locked_pick_assets contract_overrides waived_salary_obligations
waiver_wire team_plans team_trade_wants team_trade_blocks team_records ai_trade_pressure_player_ids
player_season_stats staff_slots health_states injury_events development_trait_totals development_events
rotation_baselines rotation_snapshots rotation_overrides rotation_recommendations rotation_starting_fives
season_schedules""".split())


def atomic_bytes(path, content):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2) + "\n").encode())


def save_checkpoint(directory, live):
    """Plain file copy of the save and its history database. Portable exports cap at 512 MB expanded, which a
    career passes after ~8 seasons (2034), so the checkpoint is not an export."""
    from nba_gm_data.history_store import history_sidecar_path
    saved = json.loads(live.read_text())
    sidecar = history_sidecar_path(live, saved)
    directory.mkdir(parents=True, exist_ok=True)
    staging = directory / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    shutil.copy2(live, staging / live.name)
    if sidecar.exists():
        shutil.copy2(sidecar, staging / sidecar.name)
    write_json(staging / "manifest.json", {"save": live.name, "history": sidecar.name if sidecar.exists() else None})
    current = directory / "current"
    previous = directory / "previous"
    if previous.exists():
        shutil.rmtree(previous)
    if current.exists():
        current.rename(previous)
    staging.rename(current)


def restore_checkpoint(directory, live):
    current = directory / "current"
    manifest = json.loads((current / "manifest.json").read_text())
    live.parent.mkdir(parents=True, exist_ok=True)
    if manifest["history"]:
        shutil.copy2(current / manifest["history"], live.parent / manifest["history"])
    shutil.copy2(current / manifest["save"], live)


def build(out, fixture):
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=17, team="GSW"))
    legacy_checkpoint = out / "checkpoint.nbagm.zip"
    checkpoint = out / "checkpoint"
    live = out / "saves/mature17.json"
    runner.payload["save_path"] = str(live)
    if (checkpoint / "current/manifest.json").exists():
        restore_checkpoint(checkpoint, live)
        print("Resumed last completed checkpoint", flush=True)
    elif legacy_checkpoint.exists():
        restore_export(live, legacy_checkpoint.read_bytes(), replace=True)
        save_checkpoint(checkpoint, live)
        print("Resumed last completed export checkpoint", flush=True)
    else:
        if live.exists():
            raise RuntimeError("Live save exists without checkpoint; inspect before replacing")
        runner.action("create_save", team="GSW", seed=17, save_name="mature17", ratings_model="legacy_traits")
        save_checkpoint(checkpoint, live)
    saved = runner.load()
    if saved["meta"].get("ratings_model", "legacy_traits") != "legacy_traits":
        raise RuntimeError("Fixture build requires the legacy model")
    while saved["state"]["current_date"] < TARGET:
        started = time.monotonic()
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        before = runner.load()
        action, payload = select_action(before, TARGET)
        row = {"from": before["state"]["current_date"], "phase": before["state"]["phase"],
               "action": action, "payload": payload}
        write_json(out / "pending-action.json", row)
        print(json.dumps(row), flush=True)
        result = runner.action(action, save_path=str(live), seed=17, **payload)
        saved = runner.load()
        if marker(before) == marker(saved):
            raise RuntimeError(f"No calendar/phase progress: {action}: {result.get('status')}")
        if saved["state"]["current_date"] > TARGET:
            raise RuntimeError("Passed fixture target date")
        save_checkpoint(checkpoint, live)
        row.update(to=saved["state"]["current_date"], next_phase=saved["state"]["phase"],
                   seconds=round(time.monotonic() - started, 2),
                   seasons=len(saved.get("season_history", [])),
                   generated_players=len(saved.get("generated_players", [])))
        with (out / "progress.jsonl").open("a") as handle:
            handle.write(json.dumps(row) + "\n")
        write_json(out / "status.json", row)
        (out / "pending-action.json").unlink()
        print(json.dumps(row), flush=True)
        del before, result
        clear_utility_caches()
        gc.collect()
    assert saved["state"]["current_date"] == TARGET
    reduced = {key: value for key, value in saved.items() if key in FIELDS}
    fixture.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(fixture, lzma.compress(json.dumps(reduced, separators=(",", ":")).encode()))
    report = {"fixture": str(fixture), "bytes": fixture.stat().st_size,
              "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
              "seed": 17, "model": "legacy_traits", "date": TARGET,
              "generated_players": len(saved.get("generated_players", [])),
              "health_states": len(saved.get("health_states", [])), "fields": sorted(reduced)}
    write_json(out / "fixture-source.json", report)
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/t2b")
    parser.add_argument("--fixture", type=Path, default=ROOT / "tests/fixtures/mature2036_seed17.json.xz")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if not out.is_relative_to(ROOT / "output"):
        parser.error("Checkpoint directory must be below output/")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "builder.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            build(out, args.fixture.resolve())
        except BaseException:
            (out / "crash.txt").write_text(traceback.format_exc())
            raise


if __name__ == "__main__":
    main()
