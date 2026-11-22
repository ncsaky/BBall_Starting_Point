#!/usr/bin/env python3
"""Time one simulated month through the GUI's advance action and check that results are unchanged.

The month runs through ``dispatch_app_action("advance_save", ...)``, the same call the browser GUI makes
(save load, AI front office, games, lifecycle, history archive, save write and the dashboard refresh).

Typical use (from the repo root, PYTHONPATH=src:scripts):

    # 1. Build the starting saves once (fresh BOS saves advanced to the scenario start date).
    python scripts/check_month_parity.py prepare
    # 2. Run the month with the code in this checkout ...
    python scripts/check_month_parity.py run --label after
    # ... and with an older commit's engine (its src/ is extracted under output/month-speed/code/<ref>).
    python scripts/check_month_parity.py run --label before --ref bba9a83
    # 3. Compare saved JSON (only wall-clock / random snapshot ids removed) and history database rows.
    python scripts/check_month_parity.py compare before after

Add ``--profile`` to ``run`` to write a cProfile dump next to the result. Scenarios: see ``SCENARIOS``.
Outputs live in output/month-speed/ (git-ignored).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "month-speed"

# name -> how to build the starting save and which advance actions make up "the month".
SCENARIOS: dict[str, dict] = {
    # Early regular season, default (legacy) ratings model, the GUI's default.
    "nov-legacy": {"team": "BOS", "seed": 55, "model": "legacy_traits", "start": "2026-11-01",
                   "steps": [{"to_date": "2026-12-01"}]},
    # Same month, new input-derived ratings, a different seed and team.
    "nov-inputs": {"team": "LAL", "seed": 7, "model": "inputs_v1", "start": "2026-11-01",
                   "steps": [{"to_date": "2026-12-01"}]},
    # Trade-deadline month: the GUI stops at the deadline (Feb 5), the user confirms, then the month finishes.
    "deadline-legacy": {"team": "BOS", "seed": 55, "model": "legacy_traits", "start": "2027-01-10",
                        "base": "nov-legacy",
                        "steps": [{"to_date": "2027-02-10"},
                                  {"to_date": "2027-02-10", "trade_deadline_confirmed": "2027-02-05"}]},
    # MONTH-SPEED-2 (2026-11-22): the GUI default is now the 94-input ratings, so the second seed and the
    # deadline month run on them too.
    # Boston has rookie-scale options to decide: the GUI stops on the Nov 2 deadline and the user clicks on.
    "nov-inputs-b": {"team": "BOS", "seed": 55, "model": "inputs_v1", "start": "2026-11-01",
                     "steps": [{"to_date": "2026-12-01"}, {"to_date": "2026-12-01"}]},
    "deadline-inputs": {"team": "BOS", "seed": 55, "model": "inputs_v1", "start": "2027-01-10",
                        "base": "nov-inputs-b",
                        "steps": [{"to_date": "2027-02-10"},
                                  {"to_date": "2027-02-10", "trade_deadline_confirmed": "2027-02-05"}]},
}
DEFAULT_SCENARIOS = ["nov-legacy", "nov-inputs"]


def _dispatch(action: str, save_dir: Path, canonical: dict, **payload):
    from nba_gm_data.app_actions import dispatch_app_action
    return dispatch_app_action(action, payload, root=ROOT, save_dir=save_dir, canonical=canonical)


def _canonical():
    from nba_gm_data.app_actions import load_app_canonical
    return load_app_canonical(ROOT)


def _save_files(folder: Path, stem: str = "month") -> list[Path]:
    return sorted(p for p in folder.glob(f"{stem}*") if not p.name.endswith(".lock"))


def prepare(names: list[str]) -> None:
    """Create each scenario's starting save with the current checkout's code."""
    canonical = _canonical()
    for name in names:
        spec = SCENARIOS[name]
        folder = OUT / "seeds" / name
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        base = spec.get("base")
        if base:
            for path in _save_files(OUT / "seeds" / base):
                shutil.copy2(path, folder / path.name)
        else:
            _dispatch("create_save", folder, canonical, team=spec["team"], seed=spec["seed"], save_name="month",
                      ratings_model=spec["model"])
        save_path = folder / "month.json"
        started = time.perf_counter()
        while True:
            saved = json.loads(save_path.read_text())
            current = saved["state"]["current_date"]
            if current >= spec["start"]:
                break
            deadline = f"{int(current[:4]) + (0 if current[5:7] < '07' else 1)}-02-05"
            payload = {"to_date": spec["start"], "save_path": str(save_path)}
            if current == deadline:
                payload["trade_deadline_confirmed"] = deadline
            _dispatch("advance_save", folder, canonical, **payload)
        assert saved["state"]["current_date"] == spec["start"], saved["state"]
        print(json.dumps({"scenario": name, "state": saved["state"], "seconds": round(time.perf_counter() - started, 1)}),
              flush=True)


def _history_digest(db: Path) -> dict:
    """Row-level digest of every history table; random snapshot ids in history_commits are left out."""
    if not db.exists():
        return {}
    digests = {}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            columns = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
            kept = [c for c in columns if not (table == "history_commits" and c == "snapshot_id")]
            rows = conn.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in kept)} FROM "{table}"').fetchall()
            h = hashlib.sha256()
            for row in sorted(rows, key=repr):
                h.update(repr(row).encode())
            digests[table] = {"rows": len(rows), "sha256": h.hexdigest()}
    return digests


# Absolute paths (the work folder differs per label) and the dashboard's cache revision (the save file's
# modification time and size) are wall-clock artifacts, not results.
VOLATILE_RESULT_KEYS = {"save", "save_path", "path", "revision"}


def _scrub(value):
    """Drop wall-clock artifacts from action results."""
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in VOLATILE_RESULT_KEYS}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _warm(canonical: dict, save_path: Path) -> None:
    """MONTH_SPEED_WARM=1: build the save's league once, untimed and unsaved, before the timed action. The GUI's
    server has already done this (the dashboard) when the user clicks, so module-level caches are warm."""
    if os.environ.get("MONTH_SPEED_WARM") != "1":
        return
    from nba_gm_data.save import canonical_with_save, ensure_league_save_defaults, load_save
    canonical_with_save(canonical, ensure_league_save_defaults(load_save(save_path), canonical))


def run(names: list[str], label: str, profile: bool) -> None:
    canonical = _canonical()
    for name in names:
        spec = SCENARIOS[name]
        work = OUT / "work" / label / name
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        for path in _save_files(OUT / "seeds" / name):
            shutil.copy2(path, work / path.name)
        save_path = work / "month.json"
        _warm(canonical, save_path)
        results = []
        profiler = None
        if profile:
            import cProfile
            profiler = cProfile.Profile()
        started = time.perf_counter()
        cpu_started = time.process_time()
        step_seconds = []
        for step in spec["steps"]:
            t0 = time.perf_counter()
            if profiler:
                profiler.enable()
            results.append(_dispatch("advance_save", work, canonical, save_path=str(save_path), **step))
            if profiler:
                profiler.disable()
            step_seconds.append(round(time.perf_counter() - t0, 2))
        seconds = time.perf_counter() - started
        cpu_seconds = time.process_time() - cpu_started
        dest = OUT / "runs" / f"{label}-{name}"
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        saved = json.loads(save_path.read_text())
        db = work / ((saved.get("history_store") or {}).get("path") or "month.history.sqlite3")
        shutil.copy2(save_path, dest / "month.json")
        if profiler:
            profiler.dump_stats(str(dest / "profile.prof"))
        info = {"scenario": name, "label": label, "seconds": round(seconds, 2), "cpu_seconds": round(cpu_seconds, 2), "step_seconds": step_seconds,
                "through": saved["state"]["current_date"], "history": _history_digest(db),
                "results_sha256": hashlib.sha256(json.dumps(_scrub(results), sort_keys=True, default=str).encode()).hexdigest(),
                "ai_applied": [((r.get("result") or {}).get("ai_applied_count")) for r in results],
                "games": [((r.get("result") or {}).get("games_simulated")) for r in results]}
        (dest / "result.json").write_text(json.dumps(info, indent=2) + "\n")
        (dest / "results.json").write_text(json.dumps(_scrub(results), indent=1, sort_keys=True, default=str) + "\n")
        shutil.rmtree(work)
        print(json.dumps({k: info[k] for k in ("scenario", "label", "seconds", "cpu_seconds", "step_seconds", "through", "ai_applied", "games")}),
              flush=True)


def normalized_save(path: Path) -> dict:
    """The save with only per-write random ids and the history file name removed."""
    packed = path.with_name(path.name + ".gz")
    save = json.loads(gzip.decompress(packed.read_bytes()) if not path.exists() and packed.exists() else path.read_text())
    save.get("meta", {}).pop("save_snapshot_id", None)
    for key in ("snapshot_id", "path"):
        (save.get("history_store") or {}).pop(key, None)
    return save


def _first_difference(a, b, where="$"):
    if type(a) is not type(b):
        return f"{where}: type {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        for key in sorted(a.keys() | b.keys(), key=str):
            if key not in a or key not in b:
                return f"{where}.{key}: present only in {'second' if key not in a else 'first'}"
            found = _first_difference(a[key], b[key], f"{where}.{key}")
            if found:
                return found
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{where}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            found = _first_difference(x, y, f"{where}[{i}]")
            if found:
                return found
        return None
    if a != b or repr(a) != repr(b):
        return f"{where}: {a!r} != {b!r}"
    return None


def compare(first: str, second: str, names: list[str]) -> int:
    failures = 0
    for name in names:
        a_dir, b_dir = OUT / "runs" / f"{first}-{name}", OUT / "runs" / f"{second}-{name}"
        a_info, b_info = (json.loads((d / "result.json").read_text()) for d in (a_dir, b_dir))
        problems = []
        a_save, b_save = normalized_save(a_dir / "month.json"), normalized_save(b_dir / "month.json")
        if a_save != b_save or json.dumps(a_save, sort_keys=True) != json.dumps(b_save, sort_keys=True):
            problems.append("save JSON differs: " + str(_first_difference(a_save, b_save)))
        if a_info["history"] != b_info["history"]:
            problems.append(f"history database differs: {a_info['history']} vs {b_info['history']}")
        if a_info["results_sha256"] != b_info["results_sha256"]:
            a_res = _scrub(json.loads((a_dir / "results.json").read_text()))
            b_res = _scrub(json.loads((b_dir / "results.json").read_text()))
            if a_res != b_res:
                problems.append("GUI action response differs: " + str(_first_difference(a_res, b_res)))
        status = "IDENTICAL" if not problems else "DIFFERENT"
        failures += bool(problems)
        print(json.dumps({"scenario": name, "status": status, f"{first}_seconds": a_info["seconds"],
                          f"{second}_seconds": b_info["seconds"],
                          f"{first}_cpu": a_info.get("cpu_seconds"), f"{second}_cpu": b_info.get("cpu_seconds"), "problems": problems}), flush=True)
    return 1 if failures else 0


def _code_tree(ref: str) -> Path:
    """Extract ``src/`` at a git ref next to links to this checkout's data, so resources resolve the same way."""
    target = OUT / "code" / ref
    frozen = ROOT / "speedbase" / ref / "src"   # a pre-extracted copy (remote workers have no .git)
    if not (target / "src").exists() and frozen.exists():
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(frozen, target / "src")
        for entry in ROOT.iterdir():
            if entry.name not in {"src", "output", ".git", "speedbase"} and not (target / entry.name).exists():
                (target / entry.name).symlink_to(entry)
    if not (target / "src").exists():
        target.mkdir(parents=True, exist_ok=True)
        archive = subprocess.run(["git", "-C", str(ROOT), "archive", ref, "src"], check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(target)], input=archive, check=True)
        for entry in ROOT.iterdir():
            if entry.name not in {"src", "output", ".git"} and not (target / entry.name).exists():
                (target / entry.name).symlink_to(entry)
    return target


# ---------------------------------------------------------------------------------------------------------------
# Whole season, phase by phase. ``season-prepare`` plays one full season (preseason -> regular season -> playoffs
# -> draft -> re-signing -> free agency -> training camp -> next November) through the same GUI actions the
# fixture builder uses, and keeps a copy of the save right before every action. ``season-run`` replays each
# action from its copy (each in a fresh process, optionally in parallel) so a phase can be timed and compared on
# its own; results go to runs/<label>-season-<model>-<NN>, which ``compare`` understands.
SEASON_MODELS = {"legacy": "legacy_traits", "inputs": "inputs_v1"}
SEASON_TEAM, SEASON_SEED, SEASON_END = "GSW", 17, "2027-11-01"


def _season_dir(model: str) -> Path:
    return OUT / "season" / model


def season_steps(model: str) -> list[dict]:
    seeds = _season_dir(model) / "seeds"
    return [json.loads((d / "action.json").read_text()) for d in sorted(seeds.glob("[0-9]*"))]


def season_prepare(model: str, until: str) -> None:
    """Play one season with this checkout's code, keeping the save before every action."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from overnight_market_health import marker, select_action
    from ten_season_soak import SoakRunner
    base = _season_dir(model)
    if base.exists():
        shutil.rmtree(base)
    live_dir = base / "live"
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(live_dir), seed=SEASON_SEED, team=SEASON_TEAM))
    created = runner.action("create_save", team=SEASON_TEAM, seed=SEASON_SEED, save_name="month",
                            ratings_model=SEASON_MODELS[model])
    runner.payload["save_path"] = created["save_path"]
    live = Path(created["save_path"])
    saved = runner.load()
    index = 0
    while saved["state"]["current_date"] < until:
        runner.resolve_user_staff_retention()
        runner.resolve_user_roster_cutdown()
        before = runner.load()
        action, payload = select_action(before, until)
        payload = {**payload, "seed": SEASON_SEED}
        if "team" in payload:
            payload["team"] = SEASON_TEAM
        step = {"index": index, "name": f"season-{model}-{index:02d}", "action": action, "payload": payload,
                "from": before["state"]["current_date"], "phase": before["state"]["phase"]}
        seed_dir = base / "seeds" / f"{index:02d}"
        seed_dir.mkdir(parents=True)
        for path in _save_files(live.parent):
            if path.name == "month.history.sqlite3":
                # Seeds are kept compressed (a season of them is ~2.5 GB raw); season_step expands them.
                with path.open("rb") as src, gzip.open(seed_dir / (path.name + ".gz"), "wb", compresslevel=3) as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
            elif path.name in {"month.json", "month.history.sqlite3-shm", "month.history.sqlite3-wal"}:
                shutil.copy2(path, seed_dir / path.name)
        (seed_dir / "action.json").write_text(json.dumps(step, indent=2) + "\n")
        t0 = time.perf_counter()
        _dispatch(action, live.parent, runner.canonical, save_path=str(live), **payload)
        saved = runner.load()
        if marker(before) == marker(saved):
            raise RuntimeError(f"No calendar/phase progress: {action}")
        step.update(to=saved["state"]["current_date"], next_phase=saved["state"]["phase"],
                    seconds=round(time.perf_counter() - t0, 2))
        with (base / "prepare.jsonl").open("a") as handle:
            handle.write(json.dumps(step) + "\n")
        print(json.dumps(step), flush=True)
        index += 1


def _copy_seed(seed_dir: Path, work: Path) -> None:
    for path in _save_files(seed_dir):
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as src, (work / path.stem).open("wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
        else:
            shutil.copy2(path, work / path.name)


def season_step(model: str, index: int, label: str, profile: bool) -> None:
    """Replay one season action from its seed copy and store the result like a month run."""
    seed_dir = _season_dir(model) / "seeds" / f"{index:02d}"
    step = json.loads((seed_dir / "action.json").read_text())
    name = step["name"]
    work = OUT / "work" / label / name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    _copy_seed(seed_dir, work)
    save_path = work / "month.json"
    canonical = _canonical()
    # The GUI's lottery reveal draws from system randomness on purpose (seed=None); pin it so the step can be
    # compared between engines. Harness only.
    from nba_gm_data import save as save_module
    save_module.lottery_seed = lambda seed=None: int(seed) if seed is not None else 20270622
    _warm(canonical, save_path)
    profiler = None
    if profile:
        import cProfile
        profiler = cProfile.Profile()
    started, cpu_started = time.perf_counter(), time.process_time()
    if profiler:
        profiler.enable()
    result = _dispatch(step["action"], work, canonical, save_path=str(save_path), **step["payload"])
    if profiler:
        profiler.disable()
    seconds, cpu_seconds = time.perf_counter() - started, time.process_time() - cpu_started
    results = [result]
    dest = OUT / "runs" / f"{label}-{name}"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    saved = json.loads(save_path.read_text())
    db = work / ((saved.get("history_store") or {}).get("path") or "month.history.sqlite3")
    with save_path.open("rb") as src, gzip.open(dest / "month.json.gz", "wb", compresslevel=3) as dst:
        shutil.copyfileobj(src, dst, 1 << 20)
    if profiler:
        profiler.dump_stats(str(dest / "profile.prof"))
    info = {"scenario": name, "label": label, "action": step["action"], "phase": step["phase"], "from": step["from"],
            "seconds": round(seconds, 2), "cpu_seconds": round(cpu_seconds, 2), "step_seconds": [round(seconds, 2)],
            "through": saved["state"]["current_date"], "history": _history_digest(db),
            "results_sha256": hashlib.sha256(json.dumps(_scrub(results), sort_keys=True, default=str).encode()).hexdigest()}
    (dest / "result.json").write_text(json.dumps(info, indent=2) + "\n")
    (dest / "results.json").write_text(json.dumps(_scrub(results), indent=1, sort_keys=True, default=str) + "\n")
    shutil.rmtree(work)
    print(json.dumps({k: info[k] for k in ("scenario", "label", "action", "phase", "from", "seconds", "cpu_seconds", "through")}),
          flush=True)


def season_run(model: str, label: str, indexes: list[int] | None, jobs: int, ref: str | None, profile: bool) -> int:
    steps = season_steps(model)
    chosen = [s["index"] for s in steps if indexes is None or s["index"] in indexes]
    env = dict(os.environ)
    if ref:
        tree = _code_tree(ref)
        env["PYTHONPATH"] = os.pathsep.join([str(tree / "src"), str(ROOT / "scripts")])
    script = str(Path(__file__).resolve())
    pending = list(chosen)
    running: list[subprocess.Popen] = []
    failures = 0
    while pending or running:
        while pending and len(running) < max(1, jobs):
            index = pending.pop(0)
            command = [sys.executable, script, "season-step", "--model", model, "--index", str(index), "--label", label]
            running.append(subprocess.Popen(command + (["--profile"] if profile else []), env=env))
        time.sleep(0.5)
        for proc in list(running):
            if proc.poll() is not None:
                running.remove(proc)
                failures += proc.returncode != 0
    return 1 if failures else 0


def _parse_indexes(text: str | None) -> list[int] | None:
    if not text:
        return None
    out: list[int] = []
    for part in text.split(","):
        lo, _, hi = part.partition("-")
        out.extend(range(int(lo), int(hi or lo) + 1))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_prepare = sub.add_parser("prepare")
    p_run = sub.add_parser("run")
    p_run.add_argument("--label", required=True)
    p_run.add_argument("--ref", help="run an older commit's engine instead of this checkout's src/")
    p_run.add_argument("--profile", action="store_true")
    p_compare = sub.add_parser("compare")
    p_compare.add_argument("first")
    p_compare.add_argument("second")
    for p in (p_prepare, p_run, p_compare):
        p.add_argument("--scenario", action="append", choices=sorted(SCENARIOS))
    p_compare.add_argument("--season", choices=sorted(SEASON_MODELS), action="append",
                           help="compare every season step of this ratings model instead of month scenarios")
    p_compare.add_argument("--steps", help="season step indexes, e.g. 0-5,9")
    s_prepare = sub.add_parser("season-prepare")
    s_prepare.add_argument("--model", choices=sorted(SEASON_MODELS), required=True)
    s_prepare.add_argument("--until", default=SEASON_END)
    s_run = sub.add_parser("season-run")
    s_run.add_argument("--model", choices=sorted(SEASON_MODELS), required=True)
    s_run.add_argument("--label", required=True)
    s_run.add_argument("--steps", help="step indexes, e.g. 0-5,9 (default: all)")
    s_run.add_argument("--jobs", type=int, default=1)
    s_run.add_argument("--ref")
    s_run.add_argument("--profile", action="store_true")
    s_step = sub.add_parser("season-step")
    s_step.add_argument("--model", choices=sorted(SEASON_MODELS), required=True)
    s_step.add_argument("--index", type=int, required=True)
    s_step.add_argument("--label", required=True)
    s_step.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if args.command == "season-prepare":
        season_prepare(args.model, args.until)
        return 0
    if args.command == "season-run":
        return season_run(args.model, args.label, _parse_indexes(args.steps), args.jobs, args.ref, args.profile)
    if args.command == "season-step":
        season_step(args.model, args.index, args.label, args.profile)
        return 0
    if args.command == "compare" and args.season:
        wanted = _parse_indexes(args.steps)
        names = [s["name"] for model in args.season for s in season_steps(model)
                 if wanted is None or s["index"] in wanted]
        return compare(args.first, args.second, names)
    names = args.scenario or DEFAULT_SCENARIOS
    if args.command == "prepare":
        prepare(names)
        return 0
    if args.command == "compare":
        return compare(args.first, args.second, names)
    if args.ref:
        tree = _code_tree(args.ref)
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tree / "src"), str(ROOT / "scripts")])}
        command = [sys.executable, str(Path(__file__).resolve()), "run", "--label", args.label]
        command += [f"--scenario={n}" for n in names] + (["--profile"] if args.profile else [])
        return subprocess.run(command, env=env).returncode
    import nba_gm_data
    print(json.dumps({"engine": str(Path(nba_gm_data.__file__).resolve().parent)}), flush=True)
    run(names, args.label, args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
