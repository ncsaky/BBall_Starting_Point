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

``run`` copies the code from ``--dir`` (a worktree or the main checkout; symlinked data is copied as real files, and
unchanged files are hard-linked from the worker's base copy, so only changes travel), starts the command detached on
the worker, waits for it (surviving dropped connections), copies ``--fetch`` paths back into ``--dir``, and
deallocates the machine when no other job is running. One job runs at a time; a second waits its turn. Every minute
the machine is on is logged to ``output/azure_ledger.json``; ``run``/``start`` refuse to start the machine once the
month's hours reach the cap (default 300 hours, about US$44 at US$0.147/hour).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "output" / "azure_worker_config.json"
LEDGER = ROOT / "output" / "azure_ledger.json"
PRICE_PER_HOUR = 0.147


def config() -> dict:
    try:
        cfg = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        sys.exit(f"missing {CONFIG.relative_to(ROOT)} (resource_group, vm, host, user, key, monthly_hour_cap)")
    cfg.setdefault("monthly_hour_cap", 300)
    return cfg


def sh(args: list[str], check: bool = True, capture: bool = True) -> str:
    result = subprocess.run(args, text=True, capture_output=capture)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:4])}... failed: {(result.stderr or '')[-600:]}")
    return (result.stdout or "").strip()


def ssh(cfg: dict, command: str, check: bool = True) -> str:
    return sh(["ssh", "-i", str(Path(cfg["key"]).expanduser()), "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30",
               "-o", "StrictHostKeyChecking=accept-new", f"{cfg['user']}@{cfg['host']}", command], check=check)


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
        if not data["intervals"] or data["intervals"][-1].get("stop"):
            data["intervals"].append({"start": now()})      # running but unlogged (e.g. started in the portal)
            save_ledger(data)
        return
    used = month_hours(data)
    if used >= cfg["monthly_hour_cap"] and not force_budget:
        sys.exit(f"budget: {used:.0f} of {cfg['monthly_hour_cap']} machine-hours used this month; not starting")
    print("starting the worker...", flush=True)
    sh(["az", "vm", "start", "-g", cfg["resource_group"], "-n", cfg["vm"], "-o", "none"])
    data["intervals"].append({"start": now()})
    save_ledger(data)
    for _ in range(30):                                       # wait for SSH
        if subprocess.run(["ssh", "-i", str(Path(cfg["key"]).expanduser()), "-o", "ConnectTimeout=10",
                           "-o", "StrictHostKeyChecking=accept-new", f"{cfg['user']}@{cfg['host']}", "true"],
                          capture_output=True).returncode == 0:
            return
        time.sleep(10)
    raise RuntimeError("worker started but SSH never answered")


def stop(cfg: dict) -> None:
    print("deallocating the worker (billing for the machine stops)...", flush=True)
    sh(["az", "vm", "deallocate", "-g", cfg["resource_group"], "-n", cfg["vm"], "-o", "none"])
    data = ledger()
    if data["intervals"] and not data["intervals"][-1].get("stop"):
        data["intervals"][-1]["stop"] = now()
        save_ledger(data)


def active_jobs(cfg: dict) -> list[str]:
    out = ssh(cfg, "for f in ~/runs/*/RUNNING; do [ -e \"$f\" ] && basename $(dirname $f); done; true", check=False)
    return [line for line in out.splitlines() if line.strip()]


# ---- run a job -------------------------------------------------------------------------------------------------------
def run(cfg: dict, args) -> int:
    name = args.name
    local = Path(args.dir).resolve()
    command = " ".join(shlex.quote(part) for part in args.command)
    if not command:
        sys.exit("give the command after --")
    start(cfg, args.force_budget)
    while (others := [job for job in active_jobs(cfg) if job != name]):
        print(f"waiting for the worker's current job ({', '.join(others)})...", flush=True)
        time.sleep(60)
    remote = f"runs/{name}"
    ssh(cfg, f"mkdir -p {remote}")
    print(f"copying code from {local} ...", flush=True)
    sh(["rsync", "-aL", "--delete", "--link-dest=../../base", "-e",
        f"ssh -i {Path(cfg['key']).expanduser()} -o StrictHostKeyChecking=accept-new",
        "--exclude=/output/", "--exclude=/.git/", "--exclude=/.claude/", "--exclude=/.venv/", "--exclude=/.cache/",
        "--exclude=/dist/", "--exclude=/build/", "--exclude=/saves/", "--exclude=/artifacts/", "--exclude=/tmp/",
        "--exclude=__pycache__/", "--exclude=*.pyc", f"{local}/", f"{cfg['user']}@{cfg['host']}:{remote}/"])
    ssh(cfg, f"cd {remote} && ln -sfn ~/venv .venv && mkdir -p output && "
             f"ln -sfn ~/base/output/settlement-materialization-pass output/settlement-materialization-pass && "
             f"rm -f EXIT_CODE run.log && touch RUNNING && "
             f"(nohup bash -c {shlex.quote(f'nice -n 5 {command}; echo $? > EXIT_CODE; rm -f RUNNING')} "
             f"> run.log 2>&1 &) ; true")
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
            power = power_state(cfg)
            if power != "VM running":
                print(f"the worker stopped ({power}) while '{name}' was running; its folder is kept on the disk "
                      f"so the job can be resumed", flush=True)
                data = ledger()
                if data["intervals"] and not data["intervals"][-1].get("stop"):
                    data["intervals"][-1]["stop"] = now()
                    save_ledger(data)
                return 1
            misses = 0
        if args.progress and int(time.time() - started) % 300 < 30:
            print(f"  ... {int((time.time() - started) / 60)} min", flush=True)
    code = int(state.splitlines()[-1]) if state.splitlines()[-1].isdigit() else 1
    print(ssh(cfg, f"tail -n {args.tail} {remote}/run.log", check=False))
    for rel in args.fetch:
        target = local / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        sh(["rsync", "-a", "-e", f"ssh -i {Path(cfg['key']).expanduser()}",
            f"{cfg['user']}@{cfg['host']}:{remote}/{rel}", str(target.parent) + "/"], check=False)
        print(f"fetched {rel}", flush=True)
    sh(["rsync", "-a", "-e", f"ssh -i {Path(cfg['key']).expanduser()}",
        f"{cfg['user']}@{cfg['host']}:{remote}/run.log", str(local / "output" / f"azure-{name}.log")], check=False)
    if not args.keep:
        ssh(cfg, f"rm -rf {remote}", check=False)             # the worker's disk stays small
    if not args.keep_on and not active_jobs(cfg):
        stop(cfg)
    print(f"exit code {code}; {month_hours(ledger()):.1f} machine-hours this month "
          f"(about US${month_hours(ledger()) * PRICE_PER_HOUR:.2f})")
    return code


def status(cfg: dict) -> None:
    hours = month_hours(ledger())
    print(f"worker: {power_state(cfg)}; this month {hours:.1f} of {cfg['monthly_hour_cap']} machine-hours "
          f"(about US${hours * PRICE_PER_HOUR:.2f} plus about US$5.28 for the disk)")
    if power_state(cfg) == "VM running":
        print("active jobs:", ", ".join(active_jobs(cfg)) or "none")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("start")
    s.add_argument("--force-budget", action="store_true")
    sub.add_parser("stop")
    r = sub.add_parser("run")
    r.add_argument("--name", required=True, help="a short unique job name (letters, digits, dashes)")
    r.add_argument("--dir", default=".", help="local checkout or worktree to copy (default: here)")
    r.add_argument("--fetch", action="append", default=[], help="path (relative to --dir) to copy back; repeatable")
    r.add_argument("--tail", type=int, default=25)
    r.add_argument("--keep", action="store_true", help="keep the job's folder on the worker")
    r.add_argument("--keep-on", action="store_true", help="leave the machine running afterwards")
    r.add_argument("--progress", action="store_true")
    r.add_argument("--force-budget", action="store_true")
    r.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    cfg = config()
    if args.cmd == "status":
        status(cfg)
    elif args.cmd == "start":
        start(cfg, args.force_budget)
    elif args.cmd == "stop":
        stop(cfg)
    else:
        if args.command and args.command[0] == "--":
            args.command = args.command[1:]
        return run(cfg, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
