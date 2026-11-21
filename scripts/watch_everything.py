#!/usr/bin/env python3
"""Live, human-readable view of everything running on this project: the laptop's load, the heavy jobs, Claude's
agents (with their latest note), Codex's work, the Azure worker and the board. Refreshes every 15 seconds.

  .venv/bin/python scripts/watch_everything.py            # Ctrl-C to stop watching (nothing else stops)
  .venv/bin/python scripts/watch_everything.py --once     # print one snapshot

Read-only: it never starts, stops or changes anything. Standard library only.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "docs" / "agents" / "BOARD.md"
LEDGER = ROOT / "output" / "azure_ledger.json"
TASK_GLOB = "/private/tmp/claude-*/*" + str(ROOT).replace("/", "-").replace("_", "-") + "*/*/tasks/*.output"
WIDTH = 118


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def ago(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 90:
        return f"{seconds}s ago"
    if seconds < 5400:
        return f"{seconds // 60} min ago"
    return f"{seconds / 3600:.1f} h ago"


def clip(text: str, width: int = WIDTH - 6) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


# ---- laptop ----------------------------------------------------------------------------------------------------------
def laptop() -> list[str]:
    load1, load5, _ = os.getloadavg()
    cores = os.cpu_count() or 1
    page = 16384
    stats = {}
    for line in run(["vm_stat"]).splitlines():
        match = re.match(r'"?([^:"]+)"?:\s+(\d+)', line)
        if match:
            stats[match.group(1)] = int(match.group(2))
    page_match = re.search(r"page size of (\d+)", run(["vm_stat"]))
    page = int(page_match.group(1)) if page_match else page
    free_gb = (stats.get("Pages free", 0) + stats.get("Pages inactive", 0) + stats.get("Pages speculative", 0)) * page / 1e9
    swap = re.search(r"used = ([\d.]+)M", run(["sysctl", "-n", "vm.swapusage"]))
    disk = shutil.disk_usage(str(ROOT))
    busy = "BUSY" if load1 > cores * 0.9 else "ok"
    return [f"Laptop: load {load1:.1f} (5-min {load5:.1f}) on {cores} cores [{busy}] · memory free ~{free_gb:.1f} GB"
            f" · swap used {float(swap.group(1)) / 1024 if swap else 0:.1f} GB · disk free {disk.free / 1e9:.0f} GB"]


# ---- heavy jobs (python processes) ------------------------------------------------------------------------------------
def where(pid: str) -> str:
    out = run(["lsof", "-a", "-d", "cwd", "-p", pid, "-Fn"])
    path = next((line[1:] for line in out.splitlines() if line.startswith("n")), "")
    if "/.claude/worktrees/agent-" in path:
        return "agent " + path.split("/.claude/worktrees/agent-")[1][:8]
    if "BBall_codex_" in path:
        return "Codex " + path.split("BBall_codex_")[1].split("/")[0]
    if path.startswith(str(ROOT)):
        return "main checkout"
    if "/scratchpad/" in path:
        return "coordinator scratch"
    return Path(path).name or "?"


def describe_command(cmd: str) -> str:
    if "app_server" in cmd:
        return "the game (browser GUI)"
    if "run_tests_parallel" in cmd or "unittest" in cmd:
        return "test run"
    if "azure_worker.py" in cmd:
        name = re.search(r"--name\s+(\S+)", cmd)
        return f"Azure job '{name.group(1)}' (waiting on the cloud machine)" if name else "Azure worker command"
    script = re.search(r"((?:scripts|src)/\S+\.py|-m \S+)", cmd)
    rest = cmd.split(script.group(1), 1)[1] if script else ""
    return clip(f"{script.group(1) if script else cmd[:60]} {rest.strip()[:70]}", 90)


def jobs() -> list[str]:
    rows = []
    for line in run(["ps", "-axo", "pid=,etime=,pcpu=,command="]).splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, etime, cpu, cmd = parts
        if "Python" not in cmd and "python" not in cmd:
            continue
        if "watch_everything" in cmd or ("BBall" not in cmd and "scripts/" not in cmd and "nba_gm_data" not in cmd
                                         and "unittest" not in cmd):
            continue
        rows.append((float(cpu), etime, where(pid), describe_command(cmd)))
    merged: dict[tuple, tuple] = {}
    for cpu, etime, place, what in rows:                 # a job's helper processes share its line
        key = (place, what)
        merged[key] = (max(cpu, merged.get(key, (0.0,))[0]), max(etime, merged.get(key, (0, ""))[1], key=len))
    rows = [(cpu, f"  {etime:>11}  {cpu:>5.0f}% cpu  {place:<20} {what}") for (place, what), (cpu, etime) in merged.items()]
    heavy = sum(1 for cpu, _ in rows if cpu > 40)
    head = f"Jobs on the laptop: {len(rows)} ({heavy} using a full core; the safe limit is 2 heavy jobs)"
    return [head] + [text for _, text in sorted(rows, reverse=True)] if rows else ["Jobs on the laptop: none"]


# ---- Claude agents and background commands ------------------------------------------------------------------------------
def board_rows() -> list[str]:
    try:
        return [line for line in BOARD.read_text().splitlines() if line.startswith("| ") and not line.startswith("| ---")]
    except OSError:
        return []


def task_name_for(agent_dir: str, rows: list[str]) -> str:
    key = agent_dir.split("agent-")[-1][:17]
    for row in rows:
        if key and key in row:
            return row[2:].split(" ", 1)[0]
    return "agent " + key[:8]


def first_task_id(path: str) -> str:
    """The board task ID named in the agent's brief (the first CAPS-WITH-DASHES word)."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(60_000).decode("utf-8", "replace")
    except OSError:
        return ""
    match = re.search(r"\b([A-Z][A-Z0-9]+(?:-[A-Z0-9]+){1,4})\b", head.split('"content"', 1)[-1])
    return match.group(1) if match else ""


def finished(path: str) -> bool:
    """True when the agent's last action was sending its final report."""
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - 60_000))
            tail = handle.read().decode("utf-8", "replace")
    except OSError:
        return False
    last_tool = re.findall(r'"type":\s*"tool_use",\s*"id":\s*"[^"]+",\s*"name":\s*"([^"]+)"', tail)
    return bool(last_tool) and last_tool[-1] == "SubagentHandback"


def last_note(path: str) -> tuple[str, str]:
    """The agent's latest written note and its folder, from the end of its log."""
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - 200_000))
            lines = handle.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return "", ""
    note, cwd = "", ""
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        cwd = cwd or str(row.get("cwd") or "")
        message = row.get("message") or {}
        if not note and row.get("type") == "assistant" and isinstance(message.get("content"), list):
            texts = [part.get("text") for part in message["content"] if isinstance(part, dict) and part.get("type") == "text"]
            if texts and texts[-1].strip():
                note = texts[-1]
        if note and cwd:
            break
    return note, cwd


def agents() -> list[str]:
    rows, now, out = board_rows(), time.time(), []
    files = [f for f in glob.glob(TASK_GLOB) if now - os.path.getmtime(f) < 3 * 3600]
    for path in sorted(files, key=os.path.getmtime, reverse=True):
        name = Path(path).stem
        age = now - os.path.getmtime(path)
        if name.startswith("a"):          # a Claude agent
            note, cwd = last_note(path)
            label = task_name_for(cwd, rows) if "agent-" in cwd else "agent " + name[:8]
            if label.startswith("agent "):
                label = first_task_id(path) or label
            if finished(path):
                state = "finished (report sent)"
            else:
                state = "working" if age < 180 else "waiting on its own run" if age < 7200 else "quiet"
            out.append(f"  {label:<26} {state:<24} last active {ago(age)}")
            if note:
                out.append(f"      “{clip(note, WIDTH - 10)}”")
        elif age < 300 or (age < 1800 and "exited with code" not in Path(path).read_text(errors="replace")[-200:]):
            try:
                tail = [line for line in Path(path).read_text(errors="replace").splitlines() if line.strip()][-1:]
            except OSError:
                tail = []
            out.append(f"  background command {name[:9]:<11} updated {ago(age):<12} {clip(tail[0] if tail else '', 70)}")
    return ["Claude's agents (last 3 hours) and background commands:"] + (out or ["  none in the last 3 hours"])


# ---- Codex -----------------------------------------------------------------------------------------------------------
def codex() -> list[str]:
    out, now = [], time.time()
    for folder in sorted(glob.glob(str(ROOT.parent / "BBall_codex_*"))):
        branch = run(["git", "-C", folder, "branch", "--show-current"]).strip()
        log = run(["git", "-C", folder, "log", "-1", "--format=%ct|%s"]).strip()
        if not log:
            continue
        stamp, subject = log.split("|", 1)
        age = now - int(stamp)
        if age > 6 * 3600 and not run(["git", "-C", folder, "status", "--porcelain"]).strip():
            continue                       # finished and idle for hours: skip
        changed = len([l for l in run(["git", "-C", folder, "status", "--porcelain"]).splitlines() if l.strip()])
        extra = ""
        images = glob.glob(f"{folder}/output/headshots-gen-library/game/*/*.jpg")
        if images and "headshot" in branch:
            people = len({(Path(p).parent.name, Path(p).name.split("-")[0]) for p in images})
            newest = max(os.path.getmtime(p) for p in images)
            extra = f" · {len(images)} portraits for {people} people so far (newest {ago(now - newest)})"
        out.append(f"  {branch:<34} last commit {ago(age):<12} {changed} uncommitted files{extra}")
        out.append(f"      “{clip(subject, WIDTH - 10)}”")
    return ["Codex:"] + (out or ["  no active Codex worktree"])


# ---- Azure -----------------------------------------------------------------------------------------------------------
def azure() -> list[str]:
    try:
        intervals = json.loads(LEDGER.read_text()).get("intervals") or []
    except (OSError, ValueError):
        return ["Azure worker: not set up"]
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    hours = 0.0
    for interval in intervals:
        start = datetime.fromisoformat(interval["start"])
        stop = datetime.fromisoformat(interval["stop"]) if interval.get("stop") else datetime.now(start.tzinfo)
        if start.strftime("%Y-%m") == month:
            hours += (stop - start).total_seconds() / 3600
    on = bool(intervals) and not intervals[-1].get("stop")
    state = f"ON since {intervals[-1]['start'][11:16]} UTC" if on else "off (not billing for the machine)"
    return [f"Azure worker: {state} · this month {hours:.1f} machine-hours (about US${hours * 0.147:.2f})"]


# ---- board -----------------------------------------------------------------------------------------------------------
def board() -> list[str]:
    out = []
    for row in board_rows():
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 3:
            continue
        status = cells[2]
        bold = re.search(r"\*\*([^*]+)\*\*", status)
        word = (bold.group(1) if bold else status).lower()
        if any(key in word for key in ("in progress", "queued", "review", "running", "ready")):
            task = cells[0].split(" ", 1)[0]
            owner = cells[1].split("(")[0].strip()
            out.append(f"  {task:<26} {clip(bold.group(1) if bold else status, 34):<34} {clip(owner, 50)}")
    return ["Board (open tasks):"] + (out or ["  nothing open"])


# ---- progress bars ---------------------------------------------------------------------------------------------------
GREEN, YELLOW, RED, DIM, BOLD, RESET = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
BAR = 34
_cache: dict[str, tuple[float, object]] = {}


def bar(fraction: float | None, label: str, detail: str, colour: str = GREEN) -> str:
    if fraction is None:                                   # no way to measure: a moving pulse instead of a bar
        spot = int(time.time() / 2) % BAR
        body = DIM + "".join("▓" if abs(i - spot) < 3 else "░" for i in range(BAR)) + RESET
        pct = "  …  "
    else:
        fraction = max(0.0, min(1.0, fraction))
        filled = int(round(fraction * BAR))
        body = colour + "█" * filled + RESET + DIM + "░" * (BAR - filled) + RESET
        pct = f"{fraction * 100:4.0f}%"
    return f"  {label:<30} {body} {BOLD}{pct}{RESET}  {detail}"


def seconds_of(etime: str) -> int:
    days, _, rest = etime.partition("-") if "-" in etime else ("0", "", etime)
    parts = [int(x) for x in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return int(days) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def processes() -> list[tuple[str, int, str]]:
    out = []
    for line in run(["ps", "-axo", "pid=,etime=,command="]).splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and ("Python" in parts[2] or "python" in parts[2]) and "/bin/zsh" not in parts[2]:
            out.append((parts[0], seconds_of(parts[1]), parts[2]))
    return out


def season_fraction(day: str, first_year: int, seasons: int) -> float:
    from datetime import date
    start, now = date(first_year, 10, 1), date.fromisoformat(day[:10])
    return (now - start).days / (365.25 * seasons)


def league_run_bars(procs) -> list[str]:
    """Multi-season runs on the laptop (league_health_audit advance ... --output DIR --seasons N)."""
    out = []
    for pid, elapsed, cmd in procs:
        if "league_health_audit.py" not in cmd or "advance" not in cmd or "azure_worker" in cmd:
            continue
        outdir = re.search(r"--output\s+(\S+)", cmd)
        seasons = int((re.search(r"--seasons\s+(\d+)", cmd) or [0, 1])[1])
        cwd = run(["lsof", "-a", "-d", "cwd", "-p", pid, "-Fn"]).splitlines()
        base = Path(next((l[1:] for l in cwd if l.startswith("n")), str(ROOT)))
        day = None
        for save in glob.glob(str(base / outdir.group(1) / "saves" / "*.json")) if outdir else []:
            try:
                data = Path(save).read_bytes()
            except OSError:
                continue
            found = re.search(rb'"current_date":\s*"(\d{4}-\d{2}-\d{2})"', data)
            day = found.group(1).decode() if found else day
        who = where(pid)
        label = f"{seasons}-season run ({who})"
        if day:
            frac = season_fraction(day, 2026, seasons)
            left = elapsed / frac - elapsed if frac > 0.02 else None
            eta = f", about {left / 3600:.1f} h left" if left else ""
            out.append(bar(frac, label, f"game date {day}, running {elapsed / 3600:.1f} h{eta}"))
        else:
            out.append(bar(None, label, f"running {elapsed / 3600:.1f} h"))
    return out


def azure_bars(procs) -> list[str]:
    out = []
    for pid, elapsed, cmd in procs:
        name = re.search(r"azure_worker\.py run --name\s+(\S+)", cmd)
        if not name:
            continue
        seasons = int((re.search(r"--seasons\s+(\d+)", cmd) or [0, 1])[1])
        key = "azure:" + name.group(1)
        cached = _cache.get(key)
        if not cached or time.time() - cached[0] > 60:      # ask the cloud machine at most once a minute
            try:
                cfg = json.loads((ROOT / "output" / "azure_worker_config.json").read_text())
                tail = run(["ssh", "-i", str(Path(cfg["key"]).expanduser()), "-o", "ConnectTimeout=8", "-o",
                            "BatchMode=yes", f"{cfg['user']}@{cfg['host']}", f"tail -n 40 ~/runs/{name.group(1)}/run.log"])
            except (OSError, ValueError, KeyError):
                tail = ""
            dates = re.findall(r'"date":\s*"(\d{4}-\d{2}-\d{2})', tail) or re.findall(r'"to_date":\s*"(\d{4}-\d{2}-\d{2})', tail)
            _cache[key] = (time.time(), dates[-1] if dates else None)
        day = _cache[key][1]
        label = f"Azure: {name.group(1)}"
        if day:
            out.append(bar(season_fraction(day, 2026, seasons), label, f"game date {day}, running {elapsed / 3600:.1f} h", "\033[36m"))
        else:
            out.append(bar(None, label, f"running {elapsed / 3600:.1f} h (no progress line yet)"))
    return out


def test_bars(procs) -> list[str]:
    try:
        durations = json.loads((ROOT / "output" / "test_durations.json").read_text())
    except (OSError, ValueError):
        durations = {}
    out = []
    for pid, elapsed, cmd in procs:
        if "run_tests_parallel.py" not in cmd or "--worker " in cmd:
            continue
        workers = int((re.search(r"--workers\s+(\d+)", cmd) or [0, 3])[1])
        if "--all" in cmd:
            mods = [k for k in durations if k.startswith("tests.")]
        else:
            mods = ["tests." + m.split(".")[-1] for m in re.findall(r"\b(test_\w+)", cmd)]
        times = [float(durations.get(m, 30)) for m in mods] or [60.0]
        expected = max(max(times), sum(times) / max(1, workers)) * 1.15
        frac = elapsed / expected
        note = f"{len(mods)} test files, running {elapsed // 60} min (usually ~{expected / 60:.0f} min)"
        if frac > 1:
            note += "; slower than usual, the laptop is busy"
        out.append(bar(min(frac, 0.99), f"Test run ({where(pid)})", note, YELLOW if frac > 1 else GREEN))
    return out


CODEX_BATCH_TARGET = 30 * 3 + 12 * 3 + 20 * 4   # HEADSHOT-GEN-LIBRARY batch 1: 206 portraits


def codex_bars() -> list[str]:
    out = []
    for folder in glob.glob(str(ROOT.parent / "BBall_codex_*")):
        images = glob.glob(f"{folder}/output/headshots-gen-library/game/*/*.jpg")
        if "headshot" in folder:
            people = len({(Path(p).parent.name, Path(p).name.split("-")[0]) for p in images})
            recent = max((os.path.getmtime(p) for p in images), default=0)
            note = f"{len(images)} of {CODEX_BATCH_TARGET} portraits, {people} people" + (f", newest {ago(time.time() - recent)}" if recent else ", none yet")
            out.append(bar(len(images) / CODEX_BATCH_TARGET, "Codex: face library batch 1", note, "\033[35m"))
    return out


def agent_bars() -> list[str]:
    """Claude agents active in the last 2 hours and not finished: no percentage exists, so a pulse with time active."""
    rows, now, out = board_rows(), time.time(), []
    busy = {where(pid).split(" ", 1)[1] for pid, _, _ in processes() if where(pid).startswith("agent ")}
    for path in glob.glob(TASK_GLOB):
        name = Path(path).stem
        age = now - os.path.getmtime(path)
        if not name.startswith("a") or finished(path) or not (age < 1200 or name[:8] in busy):
            continue
        note, cwd = last_note(path)
        label = task_name_for(cwd, rows) if "agent-" in cwd else ""
        label = label if label and not label.startswith("agent ") else first_task_id(path) or "agent " + name[:8]
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                stamp = json.loads(handle.readline()).get("timestamp", "")
            started = datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except (OSError, ValueError, AttributeError):
            started = os.path.getmtime(path)
        out.append(bar(None, f"Agent: {label}", f"{(now - started) / 3600:.1f} h in, last active {ago(age)}: {clip(note, 48)}"))
    return out


def gauges() -> list[str]:
    load1, _, _ = os.getloadavg()
    cores = os.cpu_count() or 1
    vm = run(["vm_stat"])
    page = int((re.search(r"page size of (\d+)", vm) or [0, 16384])[1])
    stat = {m.group(1): int(m.group(2)) for m in re.finditer(r'"?([^:"\n]+)"?:\s+(\d+)\.', vm)}
    total = int(run(["sysctl", "-n", "hw.memsize"]).strip() or 1)
    free = (stat.get("Pages free", 0) + stat.get("Pages inactive", 0) + stat.get("Pages speculative", 0)) * page
    swap = re.search(r"used = ([\d.]+)M", run(["sysctl", "-n", "vm.swapusage"]))
    disk = shutil.disk_usage(str(ROOT))

    def colour(f: float) -> str:
        return RED if f > 0.9 else YELLOW if f > 0.7 else GREEN
    cpu = load1 / cores
    mem = 1 - free / total
    return [bar(min(cpu, 1), "Processor", f"load {load1:.1f} on {cores} cores" + (" (overloaded)" if cpu > 1 else ""), colour(cpu)),
            bar(mem, "Memory", f"{(total - free) / 1e9:.1f} of {total / 1e9:.0f} GB, swap {float(swap.group(1)) / 1024 if swap else 0:.1f} GB", colour(mem)),
            bar(disk.used / disk.total, "Disk", f"{disk.free / 1e9:.0f} GB free", colour(disk.used / disk.total))]


def snapshot() -> str:
    procs = processes()
    progress = league_run_bars(procs) + azure_bars(procs) + test_bars(procs) + codex_bars() + agent_bars()
    head = f"{BOLD}NBA GM Sandbox: live progress{RESET} · {datetime.now():%a %H:%M:%S} · refreshes every 15 s · Ctrl-C stops watching"
    sections = [["Progress"] + (progress or ["  nothing running"]), ["Laptop"] + gauges(), jobs(), codex(), azure(), board()]
    return "\n".join([head, ""] + ["\n".join(s) + "\n" for s in sections])


def _old_snapshot() -> str:
    sections = [laptop(), jobs(), agents(), codex(), azure(), board()]
    head = f"NBA GM Sandbox: live status · {datetime.now():%a %H:%M:%S} · refreshes every 15 s · Ctrl-C stops watching"
    return "\n".join([head, "=" * min(WIDTH, len(head))] + ["\n".join(s) + "\n" for s in sections])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--every", type=int, default=15)
    args = parser.parse_args()
    if args.once:
        print(snapshot())
        return 0
    try:
        while True:
            text = snapshot()
            sys.stdout.write("\033[2J\033[H" + text)
            sys.stdout.flush()
            time.sleep(args.every)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
