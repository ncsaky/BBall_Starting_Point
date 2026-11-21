#!/usr/bin/env python3
"""Run Python test modules in several processes at once (standard library only).

The suite is single-threaded, so a big run uses one core of the laptop. This splits the modules across workers,
longest first, using each module's time from the last run (saved in output/test_durations.json), and runs each worker
at lower priority (nice) so agents and the app stay responsive. Keep the worker count modest: the laptop has crashed
when too many heavy jobs ran at once (two agents plus three workers is the comfortable ceiling on 16 GB).

Usage (from the repo root):
  .venv/bin/python scripts/run_tests_parallel.py --all                       # every tests/test_*.py
  .venv/bin/python scripts/run_tests_parallel.py --match "trade|free_agen"   # modules whose source matches a regex
  .venv/bin/python scripts/run_tests_parallel.py tests.test_cap_ledger tests.test_keep_stars
Options: --workers N (default 3), --js (also run tests/*.test.cjs with node), --calibration (also run the real-stat
scorecard), --out output/parallel-tests (where each worker's log goes).
Exit code 0 only if every worker passed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DURATIONS = ROOT / "output" / "test_durations.json"
PYTHON = str(ROOT / ".venv" / "bin" / "python")
ENV_PATH = "src:scripts:tests"


# ---- worker: load modules safely (a module that skips itself at import is reported, not fatal) and run them ---------
def run_worker(modules: list[str]) -> int:
    # Like ``python -m unittest`` run from the repo root: the root must be importable (``tests.test_x`` names).
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    import_skips: list[str] = []
    import_errors: list[str] = []
    for name in modules:
        try:
            suite.addTests(loader.loadTestsFromName(name))
        except unittest.SkipTest as exc:
            import_skips.append(f"{name}: {exc}")
        except Exception as exc:  # broken import: report it as a failure of the run
            import_errors.append(f"{name}: {type(exc).__name__}: {exc}")
    timings: dict[str, float] = {}
    clock = {"last": time.perf_counter()}

    class TimedResult(unittest.TextTestResult):
        # Time since the previous test finished, charged to this test's module: that includes the class/module set-up
        # that ran just before it (often the slowest part), so the next run splits the load well.
        def stopTest(self, test):
            now = time.perf_counter()
            module = type(test).__module__
            timings[module] = timings.get(module, 0.0) + now - clock["last"]
            clock["last"] = now
            super().stopTest(test)

    runner = unittest.TextTestRunner(verbosity=1, resultclass=TimedResult, stream=sys.stderr)
    result = runner.run(suite)
    for line in import_skips:
        print(f"SKIPPED AT IMPORT: {line}", file=sys.stderr)
    for line in import_errors:
        print(f"IMPORT ERROR: {line}", file=sys.stderr)
    summary = {
        "ran": result.testsRun, "failures": len(result.failures), "errors": len(result.errors) + len(import_errors),
        "skipped": len(result.skipped), "import_skips": import_skips, "import_errors": import_errors,
        "failed_tests": [str(t) for t, _ in result.failures + result.errors], "timings": timings,
    }
    print("PARALLEL_SUMMARY " + json.dumps(summary), file=sys.stderr)
    return 0 if result.wasSuccessful() and not import_errors else 1


# ---- coordinator ------------------------------------------------------------------------------------------------------
def all_modules() -> list[str]:
    return sorted(f"tests.{p.stem}" for p in (ROOT / "tests").glob("test_*.py"))


def matching_modules(pattern: str) -> list[str]:
    regex = re.compile(pattern)
    return [m for m in all_modules() if regex.search((ROOT / "tests" / f"{m.split('.', 1)[1]}.py").read_text(encoding="utf-8", errors="ignore"))]


def split(modules: list[str], workers: int) -> list[list[str]]:
    try:
        known = json.loads(DURATIONS.read_text())
    except (OSError, ValueError):
        known = {}
    default = (sum(known.values()) / len(known)) if known else 10.0
    weight = {m: float(known.get(m, default)) for m in modules}
    buckets: list[tuple[float, list[str]]] = [(0.0, []) for _ in range(max(1, workers))]
    for module in sorted(modules, key=lambda m: -weight[m]):          # longest first, onto the lightest worker
        i = min(range(len(buckets)), key=lambda k: buckets[k][0])
        total, names = buckets[i]
        buckets[i] = (total + weight[module], names + [module])
    return [names for _, names in buckets if names]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("modules", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--match")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--js", action="store_true")
    parser.add_argument("--calibration", action="store_true")
    parser.add_argument("--out", default="output/parallel-tests")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return run_worker(args.modules)

    modules = list(args.modules)
    if args.all:
        modules += all_modules()
    if args.match:
        modules += matching_modules(args.match)
    modules = sorted(set(modules))
    if not modules and not (args.js or args.calibration):
        parser.error("no test modules selected (use --all, --match or module names)")

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": ENV_PATH, "PYTHONUNBUFFERED": "1"}
    started = time.time()
    procs = []
    for i, names in enumerate(split(modules, args.workers) if modules else []):
        log = open(out / f"worker{i + 1}.log", "w")
        procs.append((i + 1, names, log, subprocess.Popen(
            ["nice", "-n", "10", PYTHON, __file__, "--worker", *names],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)))
    print(f"{len(modules)} modules on {len(procs)} workers; logs in {args.out}/", flush=True)

    ok = True
    totals = {"ran": 0, "failures": 0, "errors": 0, "skipped": 0}
    failed: list[str] = []
    import_errors: list[str] = []
    durations: dict[str, float] = {}
    try:
        durations = json.loads(DURATIONS.read_text())
    except (OSError, ValueError):
        pass
    for number, names, log, proc in procs:
        code = proc.wait()
        log.close()
        text = (out / f"worker{number}.log").read_text(errors="ignore")
        found = re.findall(r"^PARALLEL_SUMMARY (.*)$", text, flags=re.M)
        if not found:
            ok = False
            failed.append(f"worker {number} crashed (exit {code}); see {args.out}/worker{number}.log")
            continue
        summary = json.loads(found[-1])
        for key in totals:
            totals[key] += summary[key]
        failed += summary["failed_tests"]
        import_errors += summary["import_errors"]
        durations.update({m: round(t, 2) for m, t in summary["timings"].items()})
        ok = ok and code == 0
        print(f"  worker {number}: {summary['ran']} tests, {summary['failures']} failures, {summary['errors']} errors "
              f"({len(names)} modules)", flush=True)
    if procs:
        DURATIONS.parent.mkdir(parents=True, exist_ok=True)
        DURATIONS.write_text(json.dumps(dict(sorted(durations.items())), indent=1))
        print(f"Python tests: ran {totals['ran']}, failures {totals['failures']}, errors {totals['errors']}, "
              f"skipped {totals['skipped']} in {time.time() - started:.0f}s")
        for line in failed + import_errors:
            print(f"  FAILED: {line}")

    if args.js:
        js_failed = []
        for path in sorted((ROOT / "tests").glob("*.test.cjs")):
            if subprocess.run(["node", str(path)], cwd=ROOT, capture_output=True).returncode != 0:
                js_failed.append(path.name)
        print(f"Browser tests: {'all passed' if not js_failed else 'FAILED ' + ', '.join(js_failed)}")
        ok = ok and not js_failed

    if args.calibration:
        report = out / "calibration.txt"
        with open(report, "w") as handle:
            subprocess.run(["nice", "-n", "10", PYTHON, "scripts/calibration_report.py", "--games", "1230",
                            "--mode", "replay-real-minutes"], cwd=ROOT, env={**env, "PYTHONPATH": "src"},
                           stdout=handle, stderr=subprocess.STDOUT)
        text = report.read_text(errors="ignore")
        inside, outside = len(re.findall(r" yes$", text, re.M)), len(re.findall(r" no$", text, re.M))
        print(f"Real-stat scorecard: {inside} in range, {outside} out")
        ok = ok and outside == 0 and inside > 0

    print("ALL PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
