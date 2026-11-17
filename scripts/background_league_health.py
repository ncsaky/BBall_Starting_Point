"""Bounded local overnight audit. Never tunes the game or opens playable saves."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from long_term_health import OUT, ROOT, check_inputs, check_protection, fingerprints, sha, write

DIRECTORY = OUT / "overnight"
SEEDS = (17, 29, 913, 42, 71, 2026)
OBSERVERS = ("background_league_health.py", "long_term_health.py", "analyze_long_term_health.py",
             "audit_roster_floor.py", "verify_talent_balance.py")


def now():
    return datetime.now(timezone.utc).isoformat()


def descendants_rss(rows, roots):
    family = set(roots)
    while True:
        added = {pid for pid, parent, rss in rows if parent in family} - family
        if not added:
            return sum(rss for pid, parent, rss in rows if pid in family) / 1024
        family.update(added)


def process_memory(roots):
    result = subprocess.run(["ps", "-axo", "pid=,ppid=,rss="], check=True, capture_output=True, text=True)
    return descendants_rss([tuple(map(int, row.split())) for row in result.stdout.splitlines()], roots)


def stop_reason(elapsed, hours, free_bytes, rss_mib):
    if elapsed >= hours * 3600:
        return "time_limit"
    if free_bytes < 5 * 1024 ** 3:
        return "disk_below_5_gib"
    if rss_mib > 6144:
        return "workers_above_6_gib"
    return None


def progress(seed):
    path = OUT / f"career-{seed}/run.json"
    if not path.exists():
        return {"endpoint": None, "complete_seasons": 0}
    report = json.loads(path.read_text())
    return {key: report[key] for key in ("endpoint", "complete_seasons", "status")}


def work(args):
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    lock = (DIRECTORY / "batch.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    check_inputs()
    check_protection()
    source = fingerprints()
    observers = {str(ROOT / "scripts" / name): sha(ROOT / "scripts" / name) for name in OBSERVERS}
    for seed in SEEDS:
        path = OUT / f"career-{seed}/run.json"
        if path.exists():
            assert json.loads(path.read_text())["source_hashes"] == source, "Runtime changed since checkpoint"
    existing = subprocess.run(["pgrep", "-f", "long_term_health.py (run|step|bootstrap)"], capture_output=True, text=True)
    assert not existing.stdout.strip(), "Another audit worker is already active"
    report = {"pid": os.getpid(), "started_at": now(), "status": "running", "target_seasons_per_career": 10,
              "max_parallel": 2, "max_hours": args.hours, "source_hashes": source, "observer_hashes": observers,
              "jobs": {str(seed): {"status": "queued", **progress(seed)} for seed in SEEDS}}
    # A previously passed three-season checkpoint is still queued for ten.
    for job in report["jobs"].values():
        job["status"] = "queued"
    pending = list(SEEDS)
    active = {}
    requested = None
    requested_at = None
    began = time.monotonic()
    awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def request_stop(signum, frame):
        nonlocal requested
        requested = requested or "user_stop"

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        while pending or active:
            if (DIRECTORY / "STOP").exists():
                requested = requested or "stop_file"
            try:
                check_inputs()
                assert fingerprints() == source, "Runtime changed"
                assert all(sha(path) == value for path, value in observers.items()), "Observer changed"
            except Exception as exc:
                requested = requested or "inputs_changed"
                report["input_error"] = str(exc)
            memory = process_memory([p.pid for p, handle, stage, started in active.values()]) if active else 0
            requested = requested or stop_reason(time.monotonic() - began, args.hours, shutil.disk_usage(OUT).free, memory)
            if any(time.monotonic() - started > 3600 for p, handle, stage, started in active.values() if stage == "bootstrap"):
                requested = requested or "bootstrap_timeout"
            for seed, (process, handle, stage, started) in list(active.items()):
                job = report["jobs"][str(seed)]
                observation = progress(seed)
                marker = observation["endpoint"]
                if marker != job.get("last_progress_date"):
                    job.update(last_progress_date=marker, last_progress_at=now())
                    job["progress_clock"] = time.monotonic()
                if time.monotonic() - job.get("progress_clock", began) > 3600:
                    requested = requested or "no_progress_for_one_hour"
                code = process.poll()
                if code is None:
                    continue
                handle.close()
                del active[seed]
                if code == 0 and stage == "bootstrap" and not requested:
                    pending.insert(0, seed)
                    job["status"] = "queued"
                else:
                    reached = observation.get("endpoint") == "2036-10-01" and observation.get("complete_seasons") == 10
                    job.update(status="completed" if code == 0 and reached else "stopped" if requested else "failed",
                               exit_code=code, finished_at=now())
            if requested:
                if requested_at is None:
                    requested_at = time.monotonic()
                    for process, handle, stage, started in active.values():
                        process.send_signal(signal.SIGTERM)
                if time.monotonic() - requested_at > 1800:
                    for process, handle, stage, started in active.values():
                        if process.poll() is None:
                            os.killpg(process.pid, signal.SIGKILL)
                    report["forced_stop"] = True
                if not active:
                    break
            else:
                while pending and len(active) < 2:
                    seed = pending.pop(0)
                    stage = "run" if (OUT / f"career-{seed}/run.json").exists() else "bootstrap"
                    log = DIRECTORY / f"career-{seed}.log"
                    handle = log.open("a")
                    command = [sys.executable, "-u", "-B", str(ROOT / "scripts/long_term_health.py"), stage,
                               "--seed", str(seed), "--seasons", "10"]
                    process = subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
                    active[seed] = (process, handle, stage, time.monotonic())
                    report["jobs"][str(seed)].update(status="running", stage=stage, pid=process.pid, log=str(log), progress_clock=time.monotonic())
            report.update(updated_at=now(), worker_rss_mib=round(memory, 1), stop_reason=requested)
            for seed, job in report["jobs"].items():
                job.update({k: v for k, v in progress(int(seed)).items() if k != "status"})
            write(DIRECTORY / "status.json", report)
            time.sleep(10)
        report.update(status="stopped" if requested else "completed_with_failures" if any(j["status"] == "failed" for j in report["jobs"].values()) else "completed",
                      finished_at=now(), stop_reason=requested)
        check_protection()
        if report["status"] == "completed":
            for command in ([str(ROOT / "scripts/long_term_health.py"), "validate"],
                            [str(ROOT / "scripts/long_term_health.py"), "summarize"],
                            [str(ROOT / "scripts/analyze_long_term_health.py")]):
                subprocess.run([sys.executable, "-B", *command], cwd=ROOT, check=True, timeout=1800)
            report["final_analysis"] = "passed"
        write(DIRECTORY / "status.json", report)
    except BaseException as exc:
        report.update(status="failed", error=repr(exc), finished_at=now())
        write(DIRECTORY / "status.json", report)
        # Do not leave a competing writer behind after a supervisor failure.
        for process, handle, stage, started in active.values():
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process, handle, stage, started in active.values():
            try:
                process.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            handle.close()
        raise
    finally:
        awake.terminate()
        awake.wait()
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("start", "work", "status", "stop"))
    parser.add_argument("--hours", type=float, default=12)
    args = parser.parse_args()
    assert 0 < args.hours <= 24
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    if args.mode == "start":
        with (DIRECTORY / "supervisor.log").open("a") as log:
            process = subprocess.Popen([sys.executable, "-u", "-B", __file__, "work", "--hours", str(args.hours)],
                                       cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print(json.dumps({"pid": process.pid, "status_file": str(DIRECTORY / "status.json")}))
    elif args.mode == "work":
        work(args)
    elif args.mode == "stop":
        (DIRECTORY / "STOP").touch()
        print("Stop requested; active actions may finish before shutdown.")
    else:
        print((DIRECTORY / "status.json").read_text())


if __name__ == "__main__":
    main()
