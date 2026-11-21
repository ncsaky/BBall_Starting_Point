"""Bounded, checkpointed market/opportunity audit using real app actions.

Only saves below this run's isolated directory may be advanced. Runtime/model
changes stop the batch; no ratings, contracts or decision queues are rewritten.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import date, datetime, timedelta, timezone
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time

from background_league_health import process_memory, stop_reason
from league_health_audit import census, flow, regular_complete, select_advance
from long_term_health import write
from ten_season_soak import SoakRunner, distribution
from nba_gm_data import play
from nba_gm_data.baselines import baseline_for_save
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import canonical_with_save, contract_salary_for_season, load_save, team_cap_summary
from nba_gm_data.save import draft_completed_for_year, postseason_exit_required
from nba_gm_data.save_locking import save_lock
from nba_gm_data.save_recovery import restore_export

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "output/market-lifecycle-2026-10-25-r2"
SEEDS = (17, 29, 913, 42)
GIB = 1024 ** 3


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def output_path(value):
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT / "output") or path == ROOT / "output":
        raise ValueError("Audit directory must be an isolated subdirectory of output")
    return path


def inputs():
    paths = list((ROOT / "src/nba_gm_data").glob("*.py"))
    paths += list((ROOT / "data/overrides").glob("*.json"))
    paths += list((ROOT / "data/research").glob("*.json"))
    paths += list((ROOT / "data/canonical/baselines").glob("*"))
    paths += list((ROOT / "data/canonical").glob("*.json"))
    paths += list((ROOT / "NBA Schedule").glob("*.json"))
    paths += list((ROOT / "Pre-Season manifestos").glob("*.txt"))
    paths += [ROOT / "scripts" / name for name in (
        "overnight_market_health.py", "league_health_audit.py", "ten_season_soak.py",
        "background_league_health.py", "long_term_health.py")]
    paths.append(ROOT / "local-runtime.json")
    return sorted(set(path for path in paths if path.is_file()))


def install_local_read_guard(root):
    marker_path = root / "local-runtime.json"
    if not marker_path.exists():
        return
    blocked = [Path(value).resolve() for value in json.loads(marker_path.read_text())["blocked_roots"]]

    def guard(event, args):
        if event not in {"open", "sqlite3.connect", "os.chdir"} or not args:
            return
        value = args[0]
        if not isinstance(value, (str, bytes, os.PathLike)):
            return
        path = Path(os.path.abspath(os.fsdecode(value))).resolve()
        if any(path == parent or path.is_relative_to(parent) for parent in blocked):
            raise PermissionError(f"Frozen audit refused a cloud-workspace read: {path}")

    sys.addaudithook(guard)


def check_inputs(out):
    recorded = json.loads((out / "inputs.json").read_text())
    actual_paths = {str(path.relative_to(ROOT)) for path in inputs()}
    if actual_paths != set(recorded):
        raise RuntimeError("Runtime/model input inventory changed; do not mix experiments")
    for name, digest in recorded.items():
        if sha(ROOT / name) != digest:
            raise RuntimeError(f"Runtime/model changed: {name}; checkpoint retained")
    snapshot = ROOT / "snapshot.json"
    if (ROOT / "local-runtime.json").exists() and snapshot.exists():
        for name, row in json.loads(snapshot.read_text())["files"].items():
            if name not in recorded and sha(ROOT / name) != row["sha256"]:
                raise RuntimeError(f"Frozen runtime helper changed: {name}; checkpoint retained")


def read_gzip(path):
    with gzip.open(path, "rt") as handle:
        return json.load(handle)


def write_gzip(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with gzip.open(temporary, "wt", compresslevel=3) as handle:
        json.dump(value, handle, separators=(",", ":"))
    os.replace(temporary, path)


def runner_for(out, seed):
    directory = out / f"career-{seed}"
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(directory), seed=seed, team="GSW"))
    runner.canonical = read_gzip(out / "canonical.json.gz")
    report_path = directory / "run.json"
    if report_path.exists():
        runner.payload["save_path"] = json.loads(report_path.read_text())["save_path"]
    return runner


def safe_save_path(out, value):
    path = Path(value).resolve()
    if not path.is_relative_to(out) or "saves" not in path.relative_to(out).parts:
        raise ValueError("Refusing to advance a save outside the disposable audit")
    return path


def select_action(save, endpoint):
    current = save["state"]["current_date"]
    phase = save["state"]["phase"]
    end_year = int(save["meta"]["season"][:4]) + 1
    if postseason_exit_required(save):
        return "advance_save", {"postseason_exit": True}
    if phase in {"play_in", "playoffs"}:
        regular_complete(save)
        return "advance_save", {"postseason_sim": "all", "postseason_confirmed": f"{end_year}-04-13"}
    if phase == "draft_lottery":
        regular_complete(save)
        if save.get("draft_orders", {}).get(str(end_year)):
            return "advance_save", {"draft_enter": True}
        return "draft_reveal_lottery", {"year": str(end_year), "team": "GSW"}
    if phase == "draft":
        if draft_completed_for_year(save, end_year):
            # FA-REAL slice 2: back to the after-draft checklist (stop 1), the day after the draft.
            from nba_gm_data.offseason_calendar import offseason_dates
            return "advance_save", {"to_date": offseason_dates(end_year)["after_draft"]}
        return "draft_sim_all", {"year": str(end_year), "team": "GSW"}
    if phase == "re_signing":
        # Stop 1 (decide who to keep): before the draft this goes to draft night; after it, to the market.
        return "advance_re_signing", {"mode": "open_market", "team": "GSW"}
    if phase == "free_agency":
        mode = "end" if save.get("free_agency_state", {}).get("status") == "completed" else "day"
        return "advance_free_agency", {"mode": mode, "team": "GSW"}
    if phase == "training_camp":
        if current >= f"{end_year}-09-01":
            return "advance_save", {"next_event": True}
        return "advance_save", {"to_date": min(endpoint, f"{current[:4]}-10-01")}
    payload = select_advance(save, 31)
    payload["to_date"] = min(endpoint, payload["to_date"])
    if current == f"{end_year}-04-12":
        regular_complete(save)
        payload["to_date"] = f"{end_year}-04-13"
    return "advance_save", payload


def marker(save):
    market = save.get("free_agency_state") or {}
    draft = save.get("draft_state") or {}
    playoffs = save.get("playoff_state") or {}
    return (save["state"]["current_date"], save["state"]["phase"], market.get("day"),
            market.get("status"), market.get("re_signing_status"), draft.get("current_index"),
            draft.get("status"), draft.get("year"), draft.get("completed_year"),
            len(save.get("incoming_rookies") or []),
            len(playoffs.get("games") or []), playoffs.get("status"),
            save.get("postseason_entry_confirmed"), save.get("postseason_exit_confirmed"),
            tuple(sorted((save.get("draft_orders") or {}).keys())))


def validate_season_clock(saved):
    end_year = int(saved["meta"]["season"][:4]) + 1
    if saved["state"]["current_date"] >= f"{end_year}-10-01":
        raise RuntimeError("Calendar passed the next preseason without a real season rollover; results are invalid")


def validate_rollover(before, after):
    end_year = int(before["meta"]["season"][:4]) + 1
    completed_camp = (before["state"]["phase"] == "training_camp"
                      and before["state"]["current_date"] >= f"{end_year}-09-01")
    if not completed_camp:
        return
    expected = f"{end_year}-{str(end_year + 1)[-2:]}"
    if after["meta"]["season"] != expected or len(after.get("season_history", [])) != len(before.get("season_history", [])) + 1:
        raise RuntimeError("Training-camp advancement did not commit the expected new season")
    regular_complete({"team_records": after["season_history"][-1]["team_records"]})
    if sum(int(row.get("wins") or 0) for row in after["team_records"].values()) != 0:
        raise RuntimeError("Rollover did not reset new-season team records")


def market_snapshot(active, saved, snap):
    state = saved.get("free_agency_state") or {}
    season = play.contract_start_season_for_signing(saved)
    humans = play.human_controlled_team_ids(saved)
    teams = [team for team in active["teams"] if team["id"] not in humans]
    caps = {team["id"]: team_cap_summary(active, saved, team["id"], season=season) for team in teams}
    roster_counts = Counter(row["team_id"] for row in snap["players"] if row["rostered"])
    offers = [offer for offer in saved.get("free_agent_offers", [])
              if not offer.get("season") or offer["season"] == state.get("season")]
    pool = set(saved.get("free_agent_player_ids", []))
    players = {row["id"]: row for row in active["players"]}
    rows = []
    for row in snap["players"]:
        if row["id"] not in pool:
            continue
        ask = float(state.get("player_asks_millions", {}).get(row["id"]) or 0)
        history = [offer for offer in offers if offer["player_id"] == row["id"]]
        bids = [offer for offer in history if offer.get("status") == "active"]
        value = {"id": row["id"], "name": row["name"], "age": row["age"], "overall": row["display"],
                 "fixed24_engine": row["fixed24_engine"], "ask_millions": ask,
                 "active_bids": len(bids), "historical_bids": len(history),
                 "offer_statuses": dict(Counter(offer.get("status") for offer in history))}
        if row["display"] >= 80 and not bids:
            affordable = []
            for team in teams:
                reserved = play.active_bid_commitment(saved, team["id"], exclude_player_id=row["id"])
                pending = {offer["player_id"] for offer in offers
                           if offer.get("status") == "active" and offer.get("team_id") == team["id"]}
                if roster_counts[team["id"]] + len(pending) >= 21:
                    continue
                if play.signing_cap_check(active, saved, team["abbrev"], ask, reserved_millions=reserved).get("ok"):
                    affordable.append(team["id"])
            value["teams_with_room_and_slots_at_ask"] = affordable
            value["safe_year_limit"] = play.extension_safe_year_limit(players[row["id"]], season, 4)
            value["diagnosis"] = (
                "never_bid_on_despite_room_candidate" if affordable and not history
                else "prior_interest_or_rejections" if history else "no_current_room_or_slots")
        rows.append(value)
    return {"date": snap["date"], "season": state.get("season"), "day": state.get("day"),
            "status": state.get("status"), "players": rows, "offers": offers,
            "teams": {team["id"]: {"abbrev": team["abbrev"], "cap": caps[team["id"]],
                       "roster_count": roster_counts[team["id"]],
                       "reserved_bids_millions": play.active_bid_commitment(saved, team["id"])} for team in teams},
            "scope": "Room/slots is a diagnostic screen, not proof of team interest or full NBA CBA legality."}


def observe(runner, out, seed, index, before=None, *, market_only=False):
    saved = runner.load()
    source = baseline_for_save(runner.canonical, saved)
    active = canonical_with_save(source, saved)
    snap = census(active, saved)
    directory = out / f"career-{seed}"
    if market_only:
        write_gzip(directory / f"markets/{index:04}-{snap['date']}-pre-day{saved.get('free_agency_state', {}).get('day')}.json.gz",
                   market_snapshot(active, saved, snap))
        return snap
    salary = {}
    for contract in active.get("contracts", []):
        amount = contract_salary_for_season(contract, saved["meta"]["season"])
        if amount is not None:
            salary.setdefault(contract["player_id"], []).append(amount / 1_000_000)
    players = {row["id"]: row for row in active["players"]}
    last_stats = (saved.get("season_history") or [{}])[-1].get("player_season_stats", {})
    for row in snap["players"]:
        player = players[row["id"]]
        stats = (saved.get("player_season_stats") or {}).get(row["id"], {})
        games = int(stats.get("games") or 0)
        previous = last_stats.get(row["id"], {})
        row.update(position=player.get("position"), role=player.get("rotation_priority"),
                   salary_millions=salary.get(row["id"], []), games=games,
                   mpg=round(float(stats.get("minutes") or 0) / games, 2) if games else 0,
                   previous_games=previous.get("games", 0),
                   previous_minutes=previous.get("minutes", 0))
    # Bounded historical tail covers the last several simulated months; retain
    # only newly evaluated months in each observation, not the entire career.
    prior_months = set(before.get("applied_development_months", [])) if before else set(saved.get("applied_development_months", []))
    new_months = set(saved.get("applied_development_months", [])) - prior_months
    events = []
    if new_months:
        recent = load_history_records(runner.payload["save_path"], saved, "development_events", limit=8000)
        seen = {}
        for event in [*recent, *saved.get("development_events", [])]:
            if event.get("month") in new_months:
                key = (event["player_id"], event["month"])
                if key in seen and seen[key] != event:
                    raise RuntimeError(f"Conflicting development records: {key}")
                seen[key] = event
        events = list(seen.values())
        missing = new_months - {event["month"] for event in events}
        if missing:
            raise RuntimeError(f"New development months have no observable events: {sorted(missing)}")
    snap.update(new_development_months=sorted(new_months), development_events=events,
                retirement_reports=saved.get("retirement_reports", []),
                league_exit_records=saved.get("league_exit_records", []),
                incoming_rookies=saved.get("incoming_rookies", []))
    previous_path = directory / "latest-observation.json.gz"
    if previous_path.exists():
        snap["flow_from_previous"] = flow(read_gzip(previous_path), snap)
    write_gzip(directory / f"observations/{index:04}-{snap['date']}.json.gz", snap)
    write_gzip(previous_path, snap)
    if saved["state"]["phase"] == "free_agency":
        write_gzip(directory / f"markets/{index:04}-{snap['date']}-day{saved.get('free_agency_state', {}).get('day')}.json.gz",
                   market_snapshot(active, saved, snap))
    return snap


def prepare(args):
    out = output_path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "manifest.json").exists():
        raise FileExistsError("Audit already prepared; use status/start instead")
    if shutil.disk_usage(out).free < 6 * GIB:
        raise RuntimeError("Need at least 6 GiB free before preparing careers")
    from nba_gm_data.app_actions import load_app_canonical

    source = load_app_canonical(ROOT)
    write_gzip(out / "canonical.json.gz", source)
    write(out / "inputs.json", {str(path.relative_to(ROOT)): sha(path) for path in inputs()})
    start = source.get("meta", {}).get("start_date") or "2026-10-01"
    write(out / "manifest.json", {"created_at": now(), "seeds": list(SEEDS), "seasons": 10,
          "canonical_version": source.get("meta", {}).get("starting_data_version"),
          "policy": "Hands-off GSW: no discretionary bids/trades/extensions; draft auto; explicit deadline/postseason confirmations; retain staff when affordable, interim otherwise; legal low-role cutdowns. AI teams are the market cohort.",
          "scope": "Current model unchanged; simulation seeds share the canonical draft universe. No causal counterfactual or independent draft-universe claim.",
          "starting_date_hint": start, "hours": args.hours, "parallel": 2,
          "disk_floor_gib": 5, "rss_ceiling_mib": 6144, "result_directory_budget_gib": 6})
    print(f"Prepared isolated audit: {out}", flush=True)


def step(args):
    out = output_path(args.output_dir)
    check_inputs(out)
    directory = out / f"career-{args.seed}"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = directory / "pending-action.json"
        if pending.exists():
            raise RuntimeError("Unfinished prior action needs review; refusing to replay it automatically")
        runner = runner_for(out, args.seed)
        report_path = directory / "run.json"
        if not report_path.exists():
            created = runner.action("create_save", team="GSW", seed=args.seed, save_name=f"audit_{args.seed}")
            runner.payload["save_path"] = str(safe_save_path(out, created["save_path"]))
            saved = runner.load()
            start = saved["state"]["current_date"]
            report = {"seed": args.seed, "save_path": runner.payload["save_path"], "status": "running",
                      "started_at": now(), "starting_date": start,
                      "target": f"{int(start[:4]) + 10}-10-01", "actions": [], "endpoint": start,
                      "complete_seasons": 0}
            observe(runner, out, args.seed, 0)
            write(report_path, report)
            print(json.dumps({"seed": args.seed, "created": start}), flush=True)
            return
        report = json.loads(report_path.read_text())
        safe_save_path(out, report["save_path"])
        if report["endpoint"] >= report["target"]:
            report["status"] = "completed"
            write(report_path, report)
            return
        write(pending, {"began": now(), "endpoint": report["endpoint"]})
        started = time.monotonic()
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        before = runner.load()
        validate_season_clock(before)
        if before["state"]["phase"] == "free_agency" and before.get("free_agency_state", {}).get("status") != "completed":
            runner.action("free_agency_room", save_path=report["save_path"], team="GSW", seed=args.seed)
            observe(runner, out, args.seed, len(report["actions"]), market_only=True)
            before = runner.load()
        endpoint = report["target"]
        if args.short_days:
            endpoint = min(endpoint, (date.fromisoformat(before["state"]["current_date"]) + timedelta(days=args.short_days)).isoformat())
        action, payload = select_action(before, endpoint)
        result = runner.action(action, save_path=report["save_path"], seed=args.seed, **payload)
        after = runner.load()
        validate_season_clock(after)
        validate_rollover(before, after)
        if marker(before) == marker(after):
            raise RuntimeError(f"Action made no phase/calendar progress: {action}, {result.get('status')}")
        if after["state"]["current_date"] > endpoint:
            raise RuntimeError("Simulation passed the audit endpoint")
        snap = observe(runner, out, args.seed, len(report["actions"]) + 1, before)
        if after["meta"]["season"] != before["meta"]["season"]:
            regular_complete({"team_records": after["season_history"][-1]["team_records"]})
        check_inputs(out)
        row = {"action": action, "from": before["state"]["current_date"], "to": snap["date"],
               "phase": snap["phase"], "seconds": round(time.monotonic() - started, 2),
               "result_status": result.get("status"), "new_development_months": snap["new_development_months"]}
        report["actions"].append(row)
        report.update(endpoint=snap["date"], complete_seasons=len(after.get("season_history", [])),
                      updated_at=now(), status="completed" if snap["date"] == report["target"] else "running")
        write(report_path, report)
        pending.unlink()
        print(json.dumps({"seed": args.seed, **row}), flush=True)


def directory_bytes(out):
    total = 0
    for path in out.rglob("*"):
        try:
            info = path.stat()
        except FileNotFoundError:
            # SQLite WAL files and atomic-write temporaries can disappear
            # between directory enumeration and inspection during normal work.
            continue
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total


def work(args):
    out = output_path(args.output_dir)
    with (out / "batch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check_inputs(out)
        manifest = json.loads((out / "manifest.json").read_text())
        report = {"pid": os.getpid(), "status": "running", "started_at": now(),
                  "target_seasons": 10, "jobs": {str(seed): {"status": "queued"} for seed in manifest["seeds"]}}
        queue = deque(manifest["seeds"])
        active = {}
        requested = None
        began = time.monotonic()
        stop_at = None

        def request_stop(signum, frame):
            nonlocal requested
            requested = requested or "user_stop"

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            while queue or active:
                if (out / "STOP").exists():
                    requested = requested or "stop_file"
                try:
                    check_inputs(out)
                except OSError as exc:
                    requested = requested or "runtime_io_error"
                    report["input_error"] = str(exc)
                except Exception as exc:
                    requested = requested or "inputs_changed"
                    report["input_error"] = str(exc)
                memory = process_memory([process.pid for process, handle, started in active.values()]) if active else 0
                used = directory_bytes(out)
                requested = requested or stop_reason(time.monotonic() - began, args.hours, shutil.disk_usage(out).free, memory)
                if used > float(manifest.get("result_directory_budget_gib", 6)) * GIB:
                    requested = requested or "audit_directory_budget_exceeded"
                for seed, (process, handle, started) in list(active.items()):
                    job = report["jobs"][str(seed)]
                    if time.monotonic() - started > 2700:
                        requested = requested or "action_exceeded_45_minutes"
                    code = process.poll()
                    if code is None:
                        continue
                    handle.close()
                    del active[seed]
                    path = out / f"career-{seed}/run.json"
                    state = json.loads(path.read_text()) if path.exists() else {}
                    job.update(endpoint=state.get("endpoint"), complete_seasons=state.get("complete_seasons", 0),
                               actions=len(state.get("actions", [])), exit_code=code, updated_at=now())
                    if code:
                        job["status"] = "failed"
                    elif state.get("status") == "completed":
                        job["status"] = "completed"
                    elif requested:
                        job["status"] = "stopped"
                    else:
                        job["status"] = "queued"
                        queue.append(seed)
                if requested:
                    stop_at = stop_at or time.monotonic()
                    # Normal stops allow the current app action to commit. A
                    # runaway action gets a bounded grace period, then no replay.
                    if time.monotonic() - stop_at > 900:
                        for process, handle, started in active.values():
                            if process.poll() is None:
                                os.killpg(process.pid, signal.SIGTERM)
                    if not active:
                        break
                else:
                    while queue and len(active) < 2:
                        seed = queue.popleft()
                        handle = (out / f"career-{seed}.log").open("a")
                        command = [sys.executable, "-u", "-B", __file__, "step", "--output-dir", str(out), "--seed", str(seed)]
                        process = subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
                        active[seed] = (process, handle, time.monotonic())
                        report["jobs"][str(seed)].update(status="running", pid=process.pid, action_started_at=now())
                report.update(updated_at=now(), stop_reason=requested, worker_rss_mib=round(memory, 1),
                              output_mib=round(used / 1024 ** 2, 1), free_gib=round(shutil.disk_usage(out).free / GIB, 2))
                write(out / "status.json", report)
                time.sleep(5)
            for job in report["jobs"].values():
                if requested and job["status"] == "queued":
                    job["status"] = "not_started_or_checkpointed"
            report.update(status="stopped" if requested else "completed_with_failures" if any(
                job["status"] == "failed" for job in report["jobs"].values()) else "completed",
                finished_at=now(), stop_reason=requested)
            write(out / "status.json", report)
        except BaseException as exc:
            report.update(status="failed", error=repr(exc), finished_at=now())
            write(out / "status.json", report)
            raise
        finally:
            for process, handle, started in active.values():
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                handle.close()
            awake.terminate()
            awake.wait()


def status(args):
    out = output_path(args.output_dir)
    path = out / "status.json"
    value = json.loads(path.read_text()) if path.exists() else {"status": "prepared", "jobs": {}}
    print(f"Audit: {value['status']} | updated {value.get('updated_at', '-')}")
    for seed in SEEDS:
        path = out / f"career-{seed}/run.json"
        run = json.loads(path.read_text()) if path.exists() else {}
        job = value["jobs"].get(str(seed), {})
        print(f"Seed {seed:4}: {job.get('status', 'prepared'):12} | {run.get('endpoint', 'not created')} | "
              f"{run.get('complete_seasons', 0)}/10 seasons | {len(run.get('actions', []))} actions")
    print(f"Free disk: {shutil.disk_usage(out).free / GIB:.1f} GiB | stop reason: {value.get('stop_reason') or 'none'}")


def smoke(args):
    out = output_path(args.output_dir)
    check_inputs(out)
    source = ROOT / "output/free-agency-bids-2026-10-25/original-day5.nbagm.zip"
    directory = out / "smoke"
    directory.mkdir(exist_ok=False)
    path = directory / "saves/day5.json"
    restore_export(path, source.read_bytes())
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(directory), seed=7, team="MEM"))
    runner.payload["save_path"] = str(path)
    before = runner.load()
    runner.action("free_agency_room", save_path=str(path), team="MEM", seed=7)
    snap = observe(runner, out, "smoke", 0)
    saved = runner.load()
    assert saved["state"]["current_date"] == before["state"]["current_date"]
    digest = sha(path)
    runner.action("free_agency_room", save_path=str(path), team="MEM", seed=7)
    assert sha(path) == digest
    runner.action("advance_free_agency", save_path=str(path), team="MEM", seed=7, mode="day")
    observe(runner, out, "smoke", 1, saved)
    result = {"status": "passed", "date": snap["date"], "observed_players": len(snap["players"]),
              "repeat_market_read_identical": True, "real_last_day_settlement": True,
              "scope": "Disposable day-five reproduction; fresh-career short advance checked separately."}
    write(out / "smoke-result.json", result)
    print(json.dumps(result), flush=True)


def main():
    install_local_read_guard(ROOT)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "step", "smoke", "start", "work", "status", "stop"))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--hours", type=float, default=12)
    parser.add_argument("--short-days", type=int, default=0)
    args = parser.parse_args()
    if not 0 < args.hours <= 24 or args.short_days < 0:
        parser.error("Hours must be in (0, 24], short-days must be nonnegative")
    out = output_path(args.output_dir)
    if args.mode == "start":
        check_inputs(out)
        if not (out / "smoke-result.json").exists():
            raise RuntimeError("Run and verify the smoke test before background start")
        with (out / "supervisor.log").open("a") as handle:
            process = subprocess.Popen([sys.executable, "-u", "-B", __file__, "work", "--output-dir", str(out),
                                        "--hours", str(args.hours)], cwd=ROOT, stdout=handle,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        print(f"Started supervisor {process.pid}; progress: {out / 'status.json'}")
    elif args.mode == "stop":
        (out / "STOP").touch()
        print("Stop requested; current actions may finish and checkpoint first.")
    else:
        globals()[args.mode](args)


if __name__ == "__main__":
    main()
