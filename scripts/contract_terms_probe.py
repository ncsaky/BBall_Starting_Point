#!/usr/bin/env python3
"""CONTRACT-TERMS measurement: a two-season league probe (seed 17, Golden State hands-off, inputs_v1) with the same
app actions and action choice as scripts/two_season_league_probe.py, then the contract metrics:

- extensions per season (rookie-scale and veteran, AI and user), their shapes, and how many leaned on the
  "signing date not on record" fallback rule;
- option decisions per summer (player options kept / declined, veteran team options, rookie-scale options);
- the shapes of AI contracts written in each summer (salary path and option shares by first-year salary band);
- offseason seconds.

Keeps JSON copies of the save at stop 1 (June 17), the market's first day and preseason (for screenshots).

  PYTHONPATH=src:scripts .venv/bin/python -u scripts/contract_terms_probe.py OUTDIR [TARGET=2028-11-01]
  PYTHONPATH=src:scripts .venv/bin/python scripts/contract_terms_probe.py --metrics SAVE.json [OUT.json]
"""
from __future__ import annotations

import argparse
import gc
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def season_of(day: str) -> str:
    year = int(day[:4])
    start = year if day[5:] >= "07-01" else year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def band(salary: float) -> str:
    return ("under $3M" if salary < 3e6 else "$3M-$15M" if salary < 15e6 else "$15M-$35M" if salary < 35e6
            else "$35M and up")


def metrics(save_path: Path) -> dict:
    from nba_gm_data.save import load_save
    save = load_save(save_path, include_history=True)
    history = {}
    try:
        from nba_gm_data.contract_history import load_history
        history = load_history(ROOT)
    except Exception:   # noqa: BLE001 - the baseline code has no contract history
        history = {}
    users = {str((save.get("meta") or {}).get("user_team_id") or "")}
    ext = defaultdict(Counter)
    ext_shapes = defaultdict(Counter)
    for log in save.get("transaction_logs") or []:
        if log.get("transaction_type") != "extension":
            continue
        season = season_of(str(log.get("date") or "2026-10-20"))
        evaluation = next((e for e in log.get("evaluations") or [] if isinstance(e, dict) and e.get("source") == "ai_extension"), {})
        bucket = evaluation.get("bucket") or "user_or_unknown"
        who = "user" if set(log.get("teams") or []) & users else "ai"
        ext[season][f"{who}:{bucket}"] += 1
        ext[season]["total"] += 1
        contract = (log.get("assets") or {}).get("contract") or {}
        ext_shapes[season][f"{contract.get('salary_path') or 'flat'}/{contract.get('option') or 'none'}"] += 1
        pid = (log.get("assets") or {}).get("player_id")
        if (history.get(str(pid)) or {}).get("kind") == "running_since_2025":
            ext[season]["history_unknown_rule"] += 1
    options = defaultdict(Counter)
    for record in ((save.get("offseason_decisions") or {}).get("options") or {}).values():
        key = f"{record.get('kind')}:{record.get('status')}"
        options[str(record.get("season"))][key] += 1
    shapes = defaultdict(lambda: defaultdict(Counter))
    for pid, override in (save.get("contract_overrides") or {}).items():
        status = str(override.get("status") or "")
        signed = str(override.get("signed_season") or "")
        seasons = [s for s in override.get("seasons") or [] if s.get("salary")]
        if not signed or len(seasons) < 2 or status in {"signed_rookie_contract", "two_way", "exhibit_10"}:
            continue
        first = float(seasons[0]["salary"])
        second = float(seasons[1]["salary"])
        path = "rising" if second > first * 1.01 else "declining" if second < first * 0.99 else "flat"
        last = str(seasons[-1].get("option_type") or "")
        option = "player" if last == "player_option" else "team" if last == "team_option" else "none"
        shapes[signed][band(first)][f"path:{path}"] += 1
        shapes[signed][band(first)][f"option:{option}"] += 1
        shapes[signed][band(first)]["contracts"] += 1
    return {"save": str(save_path), "date": (save.get("state") or {}).get("current_date"),
            "extensions": {k: dict(v) for k, v in sorted(ext.items())},
            "extension_shapes": {k: dict(v) for k, v in sorted(ext_shapes.items())},
            "options": {k: dict(v) for k, v in sorted(options.items())},
            "multi_year_contract_shapes_by_signed_season": {s: {b: dict(c) for b, c in rows.items()} for s, rows in sorted(shapes.items())}}


def run(out: Path, target: str) -> None:
    from overnight_market_health import marker, select_action
    from ten_season_soak import SoakRunner
    from nba_gm_data.save import postseason_exit_required
    from nba_gm_data.utils import clear_utility_caches
    out.mkdir(parents=True, exist_ok=True)
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(out), seed=17, team="GSW"))
    live = out / "saves/league.json"
    runner.payload["save_path"] = str(live)
    if not live.exists():
        runner.action("create_save", team="GSW", seed=17, save_name="league", ratings_model="inputs_v1")
    copies = out / "copies"
    copies.mkdir(exist_ok=True)

    def copy(name: str) -> None:
        dest = copies / f"{name}.json"
        if not dest.exists():
            shutil.copy(live, dest)

    saved = runner.load()
    seconds = Counter()
    with (out / "progress.jsonl").open("a") as log:
        while saved["state"]["current_date"] < target:
            runner.resolve_user_staff_retention()
            runner.resolve_user_roster_cutdown()
            before = runner.load()
            day, phase = before["state"]["current_date"], before["state"]["phase"]
            if postseason_exit_required(before):
                copy(f"finals_{day[:4]}")
            if phase == "re_signing":
                copy(f"stop1_{day[:4]}")
            if phase == "free_agency" and int((before.get("free_agency_state") or {}).get("day") or 1) == 1:
                copy(f"market_{day[:4]}")
            if phase == "preseason" and day[5:] == "10-01":
                copy(f"preseason_{day[:4]}")
            action, payload = select_action(before, target)
            started = time.monotonic()
            result = runner.action(action, save_path=str(live), seed=17, **payload)
            saved = runner.load()
            if marker(before) == marker(saved):
                raise RuntimeError(f"No calendar/phase progress: {action}: {result.get('status')}")
            spent = round(time.monotonic() - started, 2)
            if "06-17" <= day[5:] <= "09-30":
                seconds[f"offseason_{day[:4]}"] += spent   # the summer: the June 17 switch to the end of camp
            row = {"from": day, "phase": phase, "action": action, "status": result.get("status"),
                   "to": saved["state"]["current_date"], "next_phase": saved["state"]["phase"], "seconds": spent}
            log.write(json.dumps(row) + "\n")
            log.flush()
            print(json.dumps(row), flush=True)
            del before, result
            clear_utility_caches()
            gc.collect()
    result = metrics(live)
    result["offseason_seconds"] = dict(seconds)
    (out / "metrics.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "--metrics":
        data = metrics(Path(sys.argv[2]))
        text = json.dumps(data, indent=1)
        if len(sys.argv) > 3:
            Path(sys.argv[3]).write_text(text + "\n")
        print(text)
    else:
        run(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 else "2028-11-01")
