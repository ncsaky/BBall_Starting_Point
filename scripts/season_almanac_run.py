#!/usr/bin/env python3
"""SEASON-ALMANAC: hands-off seasons of today's game (one by default), keeping what a "season in review" needs.

Wraps ``s2_multiseason.py run --engine current`` with two changes, both harness-only:

* no typed minutes plan: the coach decides every team's minutes, including the hands-off user team's;
* a small gzipped copy of the save file at every calendar phase change (``<out>/snapshots``), so standings, stats,
  the playoff bracket, the draft and the market can be read before the next phase resets them.

  PYTHONPATH=src .venv/bin/python scripts/season_almanac_run.py --out output/almanac/run [--seasons 2]
"""
from __future__ import annotations

import argparse
import gc
import gzip
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import s2_multiseason as s2  # noqa: E402
import ten_season_soak as soak  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=20261126)
    parser.add_argument("--team", default="BKN", help="the hands-off user team (no AI trades are made for it)")
    parser.add_argument("--seasons", type=int, default=1)
    args = parser.parse_args()
    snapshots = Path(args.out).resolve() / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    original = soak.SoakRunner.action
    last: dict[str, Any] = {"key": None, "count": 0}

    def keep(runner: Any, save: dict[str, Any]) -> None:
        state, season = save["state"], str(save["meta"]["season"])
        key = (season, state["phase"])
        if key == last["key"]:
            return
        last["key"] = key
        last["count"] += 1
        name = f"{last['count']:02d}_{season}_{state['phase']}_{state['current_date']}.json.gz"
        with gzip.open(snapshots / name, "wb", compresslevel=6) as handle:
            handle.write(Path(runner.payload["save_path"]).read_bytes())

    def action(self: Any, name: str, **payload: Any) -> dict[str, Any]:
        if name == "set_rotation_minutes":
            return {"status": "skipped", "reason": "the coach decides minutes in this run"}
        result = original(self, name, **payload)
        # The new save's path is only known to the runner after create_save; the first copy is taken one call later.
        if self.payload.get("save_path") and (name == "set_starting_five" or name.startswith(("advance_", "draft_"))):
            keep(self, self.load())
        return result

    soak.SoakRunner.action = action
    gc.disable()
    return s2.run(argparse.Namespace(engine="current", seasons=args.seasons, seed=args.seed, team=args.team,
                                     checkpoint_days=31, out=args.out))


if __name__ == "__main__":
    raise SystemExit(main())
