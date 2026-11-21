#!/usr/bin/env python3
"""Live, human-readable progress of a job running on the Azure worker (see scripts/azure_worker.py).

  .venv/bin/python scripts/watch_azure_run.py                 # the ten-season run
  .venv/bin/python scripts/watch_azure_run.py --job ten-season --first-season 2026 --seasons 10

Prints one plain line per step as the career advances, and reconnects by itself if the network drops. Ctrl-C stops
watching; the job keeps running on the worker.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "output" / "azure_worker_config.json"


def season_of(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def describe(line: str, first: int, seasons: int) -> str | None:
    try:
        row = json.loads(line)
    except ValueError:
        text = line.strip()
        return f"  (worker) {text}" if text else None
    if "date" not in row:
        return None
    day = date.fromisoformat(str(row["date"])[:10])
    start = season_of(day)
    number = start - first + 1
    part = ("offseason" if 7 <= day.month <= 9 else "preseason" if day.month == 10 and day.day < 21
            else "playoffs" if (day.month == 4 and day.day > 17) or day.month in (5, 6) else "regular season")
    done = max(0.0, min(1.0, ((day - date(first, 10, 1)).days / 365.25) / seasons))
    bar = "#" * int(done * 30) + "-" * (30 - int(done * 30))
    secs = row.get("seconds")
    step = f"step took {float(secs):.0f}s" if secs is not None else ""
    return (f"{datetime.now():%H:%M}  [{bar}] {done*100:4.1f}%  season {number} of {seasons} "
            f"({start}-{str(start + 1)[2:]}), {part}, game date {day:%b %d %Y}  {step}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--job", default="ten-season")
    parser.add_argument("--first-season", type=int, default=2026)
    parser.add_argument("--seasons", type=int, default=10)
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text())
    key = str(Path(cfg["key"]).expanduser())
    target = f"{cfg['user']}@{cfg['host']}"
    print(f"Watching '{args.job}' on the Azure worker. Ctrl-C stops watching (the job keeps running).", flush=True)
    while True:
        cmd = ["ssh", "-i", key, "-o", "ConnectTimeout=30", "-o", "ServerAliveInterval=30", target,
               f"if [ -f ~/runs/{args.job}/EXIT_CODE ]; then tail -n 3 ~/runs/{args.job}/run.log; "
               f"echo FINISHED $(cat ~/runs/{args.job}/EXIT_CODE); else tail -n 5 -F ~/runs/{args.job}/run.log; fi"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            for line in proc.stdout:
                if line.startswith("FINISHED"):
                    code = line.split()[-1]
                    print(f"{datetime.now():%H:%M}  Finished (exit code {code}). Results get copied back and the "
                          f"machine switches off automatically.", flush=True)
                    return 0
                text = describe(line, args.first_season, args.seasons)
                if text:
                    print(text, flush=True)
            proc.wait()
        except KeyboardInterrupt:
            return 0
        print(f"{datetime.now():%H:%M}  (connection dropped or machine off; retrying in 60s)", flush=True)
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
