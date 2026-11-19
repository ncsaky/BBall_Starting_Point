#!/usr/bin/env python3
"""Run a seed-17 GSW league through real, AI-enabled app actions for two seasons in either rating set.

Measurement only: same action selection as scripts/build_mature_fixture.py, but the rating set is a flag and
no test fixture is written. The live save and its history sidecar are kept under --output-dir/saves for
analysis; per-action checkpoints are kept only until the run finishes (pass --keep-checkpoint to keep them).

  PYTHONPATH=src:scripts .venv/bin/python -u scripts/two_season_league_probe.py --model inputs_v1 \
      --output-dir output/inputs-readiness/inputs_v1
"""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import shutil
import time

import build_mature_fixture as fixture
from overnight_market_health import marker, select_action
from ten_season_soak import SoakRunner
from nba_gm_data.utils import clear_utility_caches

ROOT = Path(__file__).resolve().parents[1]


def run(out: Path, model: str, target: str, seed: int, team: str, keep_checkpoint: bool) -> None:
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=seed, team=team))
    checkpoint = out / "checkpoint"
    live = out / "saves/league.json"
    runner.payload["save_path"] = str(live)
    if (checkpoint / "current/manifest.json").exists():
        fixture.restore_checkpoint(checkpoint, live)
        print("Resumed last completed checkpoint", flush=True)
    else:
        if live.exists():
            raise RuntimeError("Live save exists without checkpoint; inspect before replacing")
        runner.action("create_save", team=team, seed=seed, save_name="league", ratings_model=model)
        fixture.save_checkpoint(checkpoint, live)
    saved = runner.load()
    if saved["meta"].get("ratings_model", "legacy_traits") != model:
        raise RuntimeError(f"Save is on {saved['meta'].get('ratings_model')}, expected {model}")
    while saved["state"]["current_date"] < target:
        started = time.monotonic()
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        before = runner.load()
        action, payload = select_action(before, target)
        row = {"from": before["state"]["current_date"], "phase": before["state"]["phase"],
               "action": action, "payload": payload}
        print(json.dumps(row), flush=True)
        result = runner.action(action, save_path=str(live), seed=seed, **payload)
        saved = runner.load()
        if marker(before) == marker(saved):
            raise RuntimeError(f"No calendar/phase progress: {action}: {result.get('status')}")
        if saved["state"]["current_date"] > target:
            raise RuntimeError("Passed target date")
        fixture.save_checkpoint(checkpoint, live)
        row.update(to=saved["state"]["current_date"], next_phase=saved["state"]["phase"],
                   seconds=round(time.monotonic() - started, 2),
                   seasons=len(saved.get("season_history", [])),
                   generated_players=len(saved.get("generated_players", [])))
        with (out / "progress.jsonl").open("a") as handle:
            handle.write(json.dumps(row) + "\n")
        fixture.write_json(out / "status.json", row)
        print(json.dumps(row), flush=True)
        del before, result
        clear_utility_caches()
        gc.collect()
    fixture.write_json(out / "done.json", {"model": model, "date": saved["state"]["current_date"], "seed": seed, "team": team})
    if not keep_checkpoint and checkpoint.exists():
        shutil.rmtree(checkpoint)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["legacy_traits", "inputs_v1"], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", default="2028-11-01")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--team", default="GSW")
    parser.add_argument("--keep-checkpoint", action="store_true")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if not out.is_relative_to(ROOT / "output"):
        parser.error("Output directory must be below output/")
    out.mkdir(parents=True, exist_ok=True)
    run(out, args.model, args.target, args.seed, args.team, args.keep_checkpoint)


if __name__ == "__main__":
    main()
