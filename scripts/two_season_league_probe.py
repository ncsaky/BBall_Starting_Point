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
import resource
import shutil
import time

import build_mature_fixture as fixture
from overnight_market_health import marker, select_action
from ten_season_soak import SoakRunner
from nba_gm_data.utils import clear_utility_caches

ROOT = Path(__file__).resolve().parents[1]


def _cpu_seconds() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


def _count_trade_evaluations() -> dict[str, int]:
    """Count AI trade-search package evaluations per action (measurement only; behaviour is unchanged)."""
    from nba_gm_data import transactions

    counter = {"evaluations": 0}
    original = transactions.evaluate_trade_decision

    def counted(*args, **kwargs):
        if kwargs.get("search_only"):
            counter["evaluations"] += 1
        return original(*args, **kwargs)

    transactions.evaluate_trade_decision = counted
    return counter


_CANONICAL = {}


def deadline_phase_snapshot(save: dict) -> list[dict]:
    """Each team's window label at the trade deadline against its record (measurement only, trade 2b).

    Also the label the pre-2b rule would give on the same rosters and records (roster rating plus at most +-3 points
    for the record, no stability band), so labels can be compared on identical league states."""
    from types import SimpleNamespace
    from nba_gm_data import transactions as tx
    from nba_gm_data import team_planning as tp
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.save import canonical_with_save
    if "base" not in _CANONICAL:
        _CANONICAL["base"] = load_app_canonical(ROOT)
    ctx = tx.with_transaction_context(canonical_with_save(_CANONICAL["base"], save))
    records = ctx.get("save_team_records") or {}
    states = ctx.get("team_strategic_states") or []
    valuations = [SimpleNamespace(**v) for v in ctx.get("player_asset_valuations") or []]
    old_states = []
    for s in states:
        r = records.get(s["team_id"]) or {}
        wins, losses = float(r.get("wins") or 0), float(r.get("losses") or 0)
        games = wins + losses
        form = ((wins / games) - .5) * 6 * min(1, games / 40) if games >= 15 else 0
        old_states.append(SimpleNamespace(team_id=s["team_id"], contention_ceiling=s["contention_ceiling"] + form))
    old = tp.window_assessments({**ctx, "save_team_records": {}, "team_plans": {}}, old_states, valuations)
    out = []
    for s in states:
        r = records.get(s["team_id"]) or {}
        out.append({"team": tx.team_by_id(ctx, s["team_id"])["abbrev"], "phase": s.get("window_phase"),
                    "old_rule_phase": old[s["team_id"]]["window_phase"], "rank": s.get("league_rank"),
                    "contend_distance": s.get("contend_distance"), "record": f"{r.get('wins', 0)}-{r.get('losses', 0)}",
                    "margin_per_game": round((float(r.get("points_for") or 0) - float(r.get("points_against") or 0))
                                             / max(1.0, float(r.get("wins") or 0) + float(r.get("losses") or 0)), 2)})
    return sorted(out, key=lambda row: row["rank"] or 99)


def run(out: Path, model: str, target: str, seed: int, team: str, keep_checkpoint: bool) -> None:
    counter = _count_trade_evaluations()
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
        cpu_started = _cpu_seconds()
        counter["evaluations"] = 0
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
                   cpu_seconds=round(_cpu_seconds() - cpu_started, 2),
                   trade_evaluations=counter["evaluations"],
                   seasons=len(saved.get("season_history", [])),
                   generated_players=len(saved.get("generated_players", [])))
        if row["to"][5:] == "02-05":  # the trade deadline (save.trade_deadline_date)
            snapshot_started = _cpu_seconds()
            fixture.write_json(out / f"deadline_phases_{row['to'][:4]}.json", deadline_phase_snapshot(saved))
            row["snapshot_cpu_seconds"] = round(_cpu_seconds() - snapshot_started, 2)  # not part of the step's cost
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
