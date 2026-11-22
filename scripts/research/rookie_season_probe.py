#!/usr/bin/env python3
"""ROOKIE-FIT-2: simulate a new save's first season and record what the rookies do (measurement only).

Same hands-off action loop as scripts/two_season_league_probe.py (real app actions, AI front offices on, the user's
team on autopilot). After every step it records each 2026 rookie's card overall / impact and his cumulative season
box totals, so monthly splits and in-season growth can be read afterwards. Writes <output-dir>/rookies.json.

    PYTHONPATH=src:scripts .venv/bin/python -u scripts/research/rookie_season_probe.py \
        --output-dir output/rookie-fit-2/season_after --target 2027-04-13 --seed 17
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import build_mature_fixture as fixture  # noqa: E402
from overnight_market_health import marker, select_action  # noqa: E402
from ten_season_soak import SoakRunner  # noqa: E402
from nba_gm_data.utils import clear_utility_caches  # noqa: E402
from nba_gm_data.save import canonical_with_save  # noqa: E402
from nba_gm_data.player_profile import engine_header  # noqa: E402

STAT_KEYS = ("games", "minutes", "points", "rebounds", "assists", "turnovers", "steals", "blocks", "fgm", "fga", "fg3m",
             "fg3a", "ftm", "fta")


def rookie_state(runner, save) -> dict:
    active = canonical_with_save(runner.canonical, save)
    out = {}
    stats = save.get("player_season_stats", {})
    for p in active.get("players", []):
        if str(p.get("draft_year")) != "2026":
            continue
        head = engine_header(active, p["id"]) or {}
        totals = stats.get(p["id"], {})
        out[p["id"]] = {"name": p.get("name"), "team": p.get("team_abbrev"), "pick": p.get("draft_position"),
                        "ovr": head.get("ovr"), "impact": head.get("impact"),
                        "stats": {k: totals.get(k) for k in STAT_KEYS if totals.get(k) is not None}}
    return out


def league_stats(save) -> dict:
    return {pid: {k: t.get(k) for k in STAT_KEYS if t.get(k) is not None}
            for pid, t in save.get("player_season_stats", {}).items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", default="2027-04-13")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--team", default="GSW")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=args.seed, team=args.team))
    live = out / "saves/league.json"
    runner.payload["save_path"] = str(live)
    if live.exists():
        raise RuntimeError(f"{live} exists; use a fresh output directory")
    runner.action("create_save", team=args.team, seed=args.seed, save_name="league", ratings_model="inputs_v1")
    saved = runner.load()
    timeline = [{"date": saved["state"]["current_date"], "phase": saved["state"]["phase"],
                 "rookies": rookie_state(runner, saved)}]
    started = time.monotonic()
    while saved["state"]["current_date"] < args.target:
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        before = runner.load()
        action, payload = select_action(before, args.target)
        runner.action(action, save_path=str(live), seed=args.seed, **payload)
        saved = runner.load()
        if marker(before) == marker(saved):
            raise RuntimeError(f"No calendar/phase progress: {action}")
        timeline.append({"date": saved["state"]["current_date"], "phase": saved["state"]["phase"],
                         "rookies": rookie_state(runner, saved)})
        print(json.dumps({"to": saved["state"]["current_date"], "phase": saved["state"]["phase"], "action": action,
                          "elapsed": round(time.monotonic() - started, 1)}), flush=True)
        fixture.write_json(out / "rookies.json", {"seed": args.seed, "timeline": timeline,
                                                   "league_stats": league_stats(saved)})
        del before
        clear_utility_caches()
        gc.collect()
    fixture.write_json(out / "rookies.json", {"seed": args.seed, "timeline": timeline, "league_stats": league_stats(saved),
                                               "done": True})


if __name__ == "__main__":
    main()
