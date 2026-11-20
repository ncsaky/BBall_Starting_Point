#!/usr/bin/env python3
"""Drive a scratch career through real app actions to the season moments the slideshows use.

Run: PYTHONPATH=src:scripts .venv/bin/python -u scripts/research/slideshow_scratch_save.py --stop <stop> [--from <checkpoint>]

Stops:
  postseason  - the regular season is over and the postseason is about to begin
  champion    - the Finals are over (the year-end recap moment, before the lottery)
  preseason   - the next season's Oct 1 (the preseason outlook moment)

Each stop copies the save folder (save + history database) to output/slideshows/checkpoints/<stop>/.
"""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from overnight_market_health import marker, select_action  # noqa: E402
from ten_season_soak import SoakRunner  # noqa: E402
from nba_gm_data.save import postseason_exit_required  # noqa: E402
from nba_gm_data.utils import clear_utility_caches  # noqa: E402

OUT = ROOT / "output/slideshows"
SAVE_NAME = "slides17"


def reached(stop: str, save: dict, start_date: str) -> bool:
    phase = save["state"]["phase"]
    if stop == "postseason":
        return phase in {"play_in", "playoffs"}
    if stop == "champion":
        return postseason_exit_required(save)
    if stop == "preseason":
        return phase == "preseason" and save["state"]["current_date"] > start_date and bool(
            (save.get("season_history") or [{}])[-1].get("player_season_stats"))
    raise ValueError(stop)


def copy_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", required=True, choices=["postseason", "champion", "preseason"])
    parser.add_argument("--from", dest="source", default="")
    args = parser.parse_args()
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(OUT / "run"), seed=17, team="GSW"))
    save_dir = OUT / "run/saves"
    if args.source:
        copy_dir(OUT / "checkpoints" / args.source, save_dir)
    live = save_dir / f"{SAVE_NAME}.json"
    runner.payload["save_path"] = str(live)
    if not live.exists():
        runner.action("create_save", team="GSW", seed=17, save_name=SAVE_NAME)
    saved = runner.load()
    start_date = saved["state"]["current_date"]
    while not reached(args.stop, saved, start_date):
        started = time.monotonic()
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        before = runner.load()
        target = f"{int(before['meta']['season'][:4]) + 1}-10-01"
        action, payload = select_action(before, target)
        result = runner.action(action, save_path=str(live), seed=17, **payload)
        saved = runner.load()
        print(json.dumps({"from": before["state"]["current_date"], "to": saved["state"]["current_date"],
                          "phase": saved["state"]["phase"], "action": action, "status": result.get("status"),
                          "seconds": round(time.monotonic() - started, 1)}), flush=True)
        first = OUT / "checkpoints/first_preseason"
        if saved["state"]["phase"] == "preseason" and not saved.get("season_history") and not first.exists():
            copy_dir(save_dir, first)  # a new save's first Oct 1: the outlook uses the real 2025-26 season
            print("Checkpoint first_preseason", flush=True)
        if marker(before) == marker(saved):
            raise RuntimeError(f"No progress: {action} {payload}")
        del before, result
        clear_utility_caches()
        gc.collect()
    copy_dir(save_dir, OUT / "checkpoints" / args.stop)
    print(f"Checkpoint {args.stop} at {saved['state']['current_date']}", flush=True)


if __name__ == "__main__":
    main()
