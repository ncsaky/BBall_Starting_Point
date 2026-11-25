#!/usr/bin/env python3
"""Run a heavy job (a two-season probe, an offseason replay, a test run) on the Azure worker instead of the laptop.

The worker is a small burstable machine (4 ARM cores, about 1.6 cores sustained, 16 GB): one long single-core job at
a time runs at a steady ~1.3-1.5x its laptop time while the laptop stays cool and keeps its disk. It is not faster.

Standard library only. Needs the Azure CLI (``az``, signed in) and the worker's SSH key. Settings live in the
git-ignored ``output/azure_worker_config.json`` (resource group, machine name, address, key, monthly hour cap); the
worker's address is never committed.

  .venv/bin/python scripts/azure_worker.py status
  .venv/bin/python scripts/azure_worker.py run --name probe-x --dir . --fetch output/probe-x -- \\
      .venv/bin/python scripts/two_season_league_probe.py --out output/probe-x
  .venv/bin/python scripts/azure_worker.py stop        # deallocate now (stops billing for the machine)

A pool: ``workers`` in the config lists extra machines (one per region, because the student subscription allows 6
cores per region); each entry has ``name``, ``vm``, ``host`` and optionally ``resource_group``. Each ``run`` claims an
idle machine (a lock file in ``output/azure_claims/``), starting one that is off if none is idle, so several jobs run
side by side; with every machine busy it waits. The original machine is the worker named "canada".

``run`` copies the code from ``--dir`` (a worktree or the main checkout; symlinked data is copied as real files;
files are compared with the worker's base copy by content, not timestamp, so only changed files travel), starts the
command detached on the worker, waits for it (surviving dropped connections), copies ``--fetch`` paths back into
``--dir``, and deallocates the machine unless another job holds it. That also happens when any step fails (starting,
copying, running, fetching) or the local script is interrupted, even with ``--keep-on``. If a fetch fails, the job's
folder stays on the worker's disk. Each machine runs one job at a time; with all busy, the next waits. Every minute
the machine is on is logged to ``output/azure_ledger.json``; ``run``/``start`` refuse to start the machine once the
month's hours reach the cap (default 300 hours, about US$44 at US$0.147/hour).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "output" / "azure_worker_config.json"
LEDGER = ROOT / "output" / "azure_ledger.json"
PRICE_PER_HOUR = 0.147
# Left out of the code copy (git data, local environments, caches, builds, saves and large outputs).
COPY_EXCLUDES = ("/output/", "/.git/", "/.claude/", "/.venv/", "/.cache/", "/dist/", "/build/", "/saves/",
                 "/artifacts/", "/tmp/", "__pycache__/", "*.pyc")


def hour_cap() -> float:
    """Monthly machine-hour budget shared by the whole pool (per-worker entries don't carry it)."""
    return float(config()["monthly_hour_cap"])


def config() -> dict:
    try:
        cfg = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        sys.exit(f"missing {CONFIG.relative_to(ROOT)} (resource_group, vm, host, user, key, monthly_hour_cap)")
    cfg.setdefault("monthly_hour_cap", 300)
    return cfg


CLAIMS = ROOT / "output" / "azure_claims"


def pool(cfg: dict) -> list[dict]:
    """Every worker machine: the original one plus `workers` entries, each with its own vm, host and resource group."""
    base = {"name": "canada", "vm": cfg["vm"], "host": cfg["host"], "resource_group": cfg["resource_group"]}
    out = [base]
    for extra in cfg.get("workers", []):
        out.append({"resource_group": cfg["resource_group"], **extra})
    for worker in out:
        worker.setdefault("user", cfg["user"])
        worker.setdefault("key", cfg["key"])
    return out


def pid_alive(pid: int) -> bool:
    try:
        import os
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def claim(worker: dict, job: str) -> bool:
    """Atomically mark a worker as taken by this job (a stale claim whose process is gone is cleared)."""
    import os
    CLAIMS.mkdir(parents=True, exist_ok=True)
    path = CLAIMS / f"{worker['name']}.json"
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except (OSError, ValueError):
            old = {}
        if old.get("pid") and pid_alive(int(old["pid"])):
            return False
        path.unlink(missing_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as handle:
        json.dump({"job": job, "pid": os.getpid(), "host": worker["host"], "worker": worker["name"], "since": now()}, handle)
    return True


def release(worker: dict) -> None:
    (CLAIMS / f"{worker['name']}.json").unlink(missing_ok=True)


def claim_holder(worker: dict) -> str | None:
    """The job of another live process that has claimed this machine, if any."""
    import os
    try:
        held = json.loads((CLAIMS / f"{worker['name']}.json").read_text())
        pid = int(held["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return str(held.get("job", "?")) if pid != os.getpid() and pid_alive(pid) else None


def sh(args: list[str], check: bool = True, capture: bool = True) -> str:
    result = subprocess.run(args, text=True, capture_output=capture)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:4])}... failed: {(result.stderr or '')[-600:]}")
    return (result.stdout or "").strip()


def ssh_args(cfg: dict) -> list[str]:
    return ["ssh", "-i", str(Path(cfg["key"]).expanduser()), "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
            "-o", "StrictHostKeyChecking=accept-new"]


def ssh(cfg: dict, command: str, check: bool = True) -> str:
    """cfg is a worker (or the config itself, meaning the original machine)."""
    return sh([*ssh_args(cfg), f"{cfg['user']}@{cfg['host']}", command], check=check)


def rsync_shell(cfg: dict) -> str:
    """The ssh command rsync travels over; it gives up on a dead connection instead of hanging. It waits 10 minutes
    of silence first: with several uploads sharing the laptop's connection, 90 seconds cut off a live copy."""
    return shlex.join([*ssh_args(cfg), "-o", "ServerAliveCountMax=20"])


def copy_command(cfg: dict, local: Path, remote: str) -> list[str]:
    """Copy the code to the worker. --checksum compares file contents: a fresh worktree has new timestamps on every
    file, and by timestamp all of it would be uploaded again. Files matching the base copy are taken from it there."""
    return ["rsync", "-aL", "--checksum", "--delete", "--link-dest=../../base", "-e", rsync_shell(cfg),
            *(f"--exclude={pattern}" for pattern in COPY_EXCLUDES),
            f"{local}/", f"{cfg['user']}@{cfg['host']}:{remote}/"]


# ---- the ledger: every interval the machine was on -------------------------------------------------------------------
def ledger() -> dict:
    try:
        return json.loads(LEDGER.read_text())
    except (OSError, ValueError):
        return {"intervals": []}


def save_ledger(data: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(data, indent=1))


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def open_interval(data: dict, vm: str) -> dict | None:
    for interval in reversed(data["intervals"]):
        if interval.get("vm", "bball-worker") == vm and not interval.get("stop"):
            return interval
    return None


def month_hours(data: dict) -> float:
    month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    total = 0.0
    for interval in data["intervals"]:
        start = dt.datetime.fromisoformat(interval["start"])
        stop = dt.datetime.fromisoformat(interval["stop"]) if interval.get("stop") else dt.datetime.now(dt.timezone.utc)
        if start.strftime("%Y-%m") == month:
            total += (stop - start).total_seconds() / 3600
    return total


def power_state(cfg: dict) -> str:
    return sh(["az", "vm", "get-instance-view", "-g", cfg["resource_group"], "-n", cfg["vm"], "--query",
               "instanceView.statuses[?starts_with(code,'PowerState/')].displayStatus | [0]", "-o", "tsv"])


def start(cfg: dict, force_budget: bool = False) -> None:
    data = ledger()
    if power_state(cfg) == "VM running":
        if not open_interval(data, cfg["vm"]):
            data["intervals"].append({"start": now(), "vm": cfg["vm"]})   # running but unlogged (e.g. started in the portal)
            save_ledger(data)
        return
    used = month_hours(data)
    if used >= hour_cap() and not force_budget:
        sys.exit(f"budget: {used:.0f} of {hour_cap()} machine-hours used this month; not starting")
    print("starting the worker...", flush=True)
    sh(["az", "vm", "start", "-g", cfg["resource_group"], "-n", cfg["vm"], "-o", "none"])
    data = ledger()
    data["intervals"].append({"start": now(), "vm": cfg["vm"]})
    save_ledger(data)
    for _ in range(30):                                       # wait for SSH
        if subprocess.run(["ssh", "-i", str(Path(cfg["key"]).expanduser()), "-o", "ConnectTimeout=10",
                           "-o", "StrictHostKeyChecking=accept-new", f"{cfg['user']}@{cfg['host']}", "true"],
                          capture_output=True).returncode == 0:
            return
        time.sleep(10)
    raise RuntimeError("worker started but SSH never answered")


def stop(cfg: dict) -> None:
    print(f"deallocating {cfg.get('name', cfg['vm'])} (billing for the machine stops)...", flush=True)
    sh(["az", "vm", "deallocate", "-g", cfg["resource_group"], "-n", cfg["vm"], "-o", "none"])
    close_interval(cfg)


def close_interval(cfg: dict) -> None:
    data = ledger()
    interval = open_interval(data, cfg["vm"])
    if interval:
        interval["stop"] = now()
        save_ledger(data)


# A RUNNING marker older than the machine's last boot belongs to a job that died with the machine; ignore it.
RUNNING_JOBS = ("boot=$(date -d \"$(uptime -s)\" +%s); for f in ~/runs/*/RUNNING; do "
                "[ -e \"$f\" ] && [ $(stat -c %Y \"$f\") -ge $boot ] && basename $(dirname \"$f\"); done; true")


def active_jobs(cfg: dict) -> list[str] | None:
    """Names of the jobs running on the machine, or None when it can't be asked."""
    try:
        out = ssh(cfg, RUNNING_JOBS)
    except RuntimeError:
        return None
    return [line for line in out.splitlines() if line.strip()]


def switch_off(worker: dict, job: str, attempts: int = 3, pause: float = 20) -> None:
    """`job` is finished with the machine, successfully or not: deallocate it unless another job still holds it."""
    name = worker["name"]
    holder = claim_holder(worker)
    if holder:
        print(f"leaving '{name}' on: job '{holder}' has claimed it", flush=True)
        return
    try:
        state = power_state(worker)
    except RuntimeError:
        state = "unknown"
    if state == "VM deallocated":
        close_interval(worker)
        return
    if state in ("VM running", "unknown"):
        for attempt in range(attempts):
            jobs = active_jobs(worker)
            if jobs is not None or attempt == attempts - 1:
                break
            time.sleep(pause)
        others = [other for other in jobs or [] if other != job]
        if others:
            print(f"leaving '{name}' on: still running {', '.join(others)}", flush=True)
            return
        if jobs is None:
            print(f"'{name}' doesn't answer and no other job has claimed it; switching it off", flush=True)
        elif job in jobs:                           # our job is cut short: don't leave it marked as running
            ssh(worker, f"rm -f runs/{shlex.quote(job)}/RUNNING", check=False)
    for attempt in range(attempts):
        try:
            stop(worker)
            return
        except (RuntimeError, OSError) as exc:
            print(f"switching off '{name}' failed: {exc}", flush=True)
            if attempt < attempts - 1:
                time.sleep(pause)
    print(f"WARNING: '{name}' MAY STILL BE ON. Run: .venv/bin/python scripts/azure_worker.py stop --worker {name}",
          flush=True)


# ---- run a job -------------------------------------------------------------------------------------------------------
def pick_worker(cfg: dict, name: str, force_budget: bool, only: str | None = None) -> dict:
    """Claim an idle worker: one already running with no job first (warm), then one that is off; else wait.
    The caller starts it, so that a failed start is cleaned up like any other failed step."""
    if month_hours(ledger()) >= hour_cap() and not force_budget:
        sys.exit(f"budget: {month_hours(ledger()):.0f} of {hour_cap()} machine-hours used this month")
    workers = [w for w in pool(cfg) if not only or w["name"] == only]
    announced = False
    while True:
        states = {}
        for worker in workers:
            try:
                states[worker["name"]] = power_state(worker)
            except RuntimeError:
                states[worker["name"]] = "unknown"
        order = sorted(workers, key=lambda w: (states[w["name"]] != "VM running", w["name"] != "canada"))
        for worker in order:
            if states[worker["name"]] == "unknown" or not claim(worker, name):
                continue
            if states[worker["name"]] == "VM running":
                jobs = active_jobs(worker)
                if jobs is None or [job for job in jobs if job != name]:
                    release(worker)       # not answering, or busy with a job no live script has claimed
                    continue
            print(f"using worker '{worker['name']}' ({states[worker['name']]})", flush=True)
            return worker
        if not announced:
            print("every worker is busy; waiting for one to free up...", flush=True)
            announced = True
        time.sleep(60)


def run(cfg: dict, args) -> int:
    name = args.name
    local = Path(args.dir).resolve()
    command = " ".join(shlex.quote(part) for part in args.command)
    if not command:
        sys.exit("give the command after --")
    worker = pick_worker(cfg, name, args.force_budget, args.worker)
    exit_on_termination()
    code = None                                               # stays None if any step raises or is interrupted
    try:
        start(worker, args.force_budget)
        code = run_on(worker, args, name, local, command)
    finally:
        try:
            if code != 0 or not args.keep_on:
                ignore_interrupts()                           # a second Ctrl-C must not cut the switch-off short
                switch_off(worker, name)
        finally:
            release(worker)
    print(f"exit code {code} on '{worker['name']}'; {month_hours(ledger()):.1f} machine-hours this month across all "
          f"workers (about US${month_hours(ledger()) * PRICE_PER_HOUR:.2f})")
    return code


def exit_on_termination() -> None:
    """Being killed or losing the terminal should still run the cleanup (under nohup, hang-ups stay ignored)."""
    for sig in (signal.SIGTERM, signal.SIGHUP):
        if signal.getsignal(sig) == signal.SIG_DFL:
            signal.signal(sig, lambda number, _frame: sys.exit(128 + number))


def ignore_interrupts() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, signal.SIG_IGN)


def run_on(cfg: dict, args, name: str, local: Path, command: str) -> int:
    """Run one job on the claimed, started worker `cfg` (a pool entry). The caller switches the machine off."""
    remote = f"runs/{name}"
    ssh(cfg, f"mkdir -p {remote}")
    print(f"copying code from {local} ...", flush=True)
    sh(copy_command(cfg, local, remote))
    ssh(cfg, f"cd {remote} && ln -sfn ~/venv .venv && mkdir -p output && "
             f"ln -sfn ~/base/output/settlement-materialization-pass output/settlement-materialization-pass && "
             f"rm -f EXIT_CODE run.log && touch RUNNING && "
             f"(nohup bash -c {shlex.quote(f'nice -n 5 {command}; echo $? > EXIT_CODE; rm -f RUNNING')} "
             f"> run.log 2>&1 &)")                             # a failed set-up step raises instead of waiting
    print(f"running on the worker: {command}", flush=True)
    started = time.time()
    misses = 0
    while True:
        time.sleep(30)
        state = ssh(cfg, f"cd {remote} && (cat EXIT_CODE 2>/dev/null || echo running)", check=False)
        if state and state != "running":
            break
        misses = 0 if state else misses + 1
        if misses >= 6:   # three minutes without an answer: is the machine still on?
            try:
                power = power_state(cfg)
            except RuntimeError:
                power = None                                    # Azure didn't answer either; keep waiting
            if power is not None and power != "VM running":
                print(f"the worker stopped ({power}) while '{name}' was running; its folder is kept on the disk "
                      f"so the job can be resumed", flush=True)
                return 1
            misses = 0
        if args.progress and int(time.time() - started) % 300 < 30:
            print(f"  ... {int((time.time() - started) / 60)} min", flush=True)
    code = int(state.splitlines()[-1]) if state.splitlines()[-1].isdigit() else 1
    print(ssh(cfg, f"tail -n {args.tail} {remote}/run.log", check=False))
    missed = []
    for rel in args.fetch:
        target = local / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            sh(["rsync", "-a", "-e", rsync_shell(cfg),
                f"{cfg['user']}@{cfg['host']}:{remote}/{rel}", str(target.parent) + "/"])
            print(f"fetched {rel}", flush=True)
        except RuntimeError as exc:
            missed.append(rel)
            print(f"could not fetch {rel}: {exc}", flush=True)
    sh(["rsync", "-a", "-e", rsync_shell(cfg),
        f"{cfg['user']}@{cfg['host']}:{remote}/run.log", str(local / "output" / f"azure-{name}.log")], check=False)
    if missed:
        print(f"keeping {remote} on '{cfg['name']}' so nothing is lost (start the machine to copy it by hand)",
              flush=True)
        return code or 1
    if not args.keep:
        ssh(cfg, f"rm -rf {remote}", check=False)             # the worker's disk stays small
    return code


def status(cfg: dict) -> None:
    hours = month_hours(ledger())
    workers = pool(cfg)
    print(f"{len(workers)} workers; this month {hours:.1f} of {cfg['monthly_hour_cap']} machine-hours "
          f"(about US${hours * PRICE_PER_HOUR:.2f} plus about US$5.28 a month per worker disk)")
    for worker in workers:
        state = power_state(worker)
        jobs = ""
        if state == "VM running":
            running = active_jobs(worker)
            jobs = "(not answering)" if running is None else ", ".join(running)
        print(f"  {worker['name']:<8} {state:<16} {('jobs: ' + jobs) if jobs else ''}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("start")
    s.add_argument("--force-budget", action="store_true")
    s.add_argument("--worker", default="canada")
    st = sub.add_parser("stop")
    st.add_argument("--worker", default=None, help="one worker by name (default: every idle worker)")
    r = sub.add_parser("run")
    r.add_argument("--name", required=True, help="a short unique job name (letters, digits, dashes)")
    r.add_argument("--dir", default=".", help="local checkout or worktree to copy (default: here)")
    r.add_argument("--fetch", action="append", default=[], help="path (relative to --dir) to copy back; repeatable")
    r.add_argument("--tail", type=int, default=25)
    r.add_argument("--keep", action="store_true", help="keep the job's folder on the worker")
    r.add_argument("--keep-on", action="store_true", help="leave the machine running afterwards")
    r.add_argument("--progress", action="store_true")
    r.add_argument("--force-budget", action="store_true")
    r.add_argument("--worker", default=None, help="run only on this worker (default: any idle one)")
    r.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cfg = config()
    if args.cmd == "status":
        status(cfg)
    elif args.cmd == "start":
        start(next(w for w in pool(cfg) if w["name"] == args.worker), args.force_budget)
    elif args.cmd == "stop":
        for worker in pool(cfg):
            if args.worker in (None, worker["name"]) and power_state(worker) == "VM running" and \
                    (args.worker or active_jobs(worker) == []):
                stop(worker)
    else:
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        return run(cfg, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
