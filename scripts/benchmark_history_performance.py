"""Bounded read and app-advance checks against exact pre-change history code."""
import argparse
from contextlib import ExitStack, closing, nullcontext
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import statistics
import time
from types import FunctionType
from unittest.mock import patch

from nba_gm_data import app_actions as app, history_store as hs, save as sv
from nba_gm_data.save_recovery import previous_backup_path, recover_previous_save
from long_term_health import canonical, check_inputs, check_protection, fingerprints, sha, write
from verify_simulation_consistency import business_state, digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/history-performance-2026-10-24"
SOURCE = ROOT / "output/simulation-memory-2026-10-24/after-final/mature-17/disposable.json"
PREPARED = ROOT / "output/ai-role-reassessment-2026-10-24/prepared/seed17.nbagm.zip"


def reference_implementation():
    reference = OUT / "reference_history_store.py"
    before = json.loads((OUT / "before-runtime.json").read_text())
    assert sha(reference) == before["src/nba_gm_data/history_store.py"]
    spec = importlib.util.spec_from_file_location("reference_history_store", reference)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stack = ExitStack()
    for name in ("_visible_counts", "load_history_records"):
        original = getattr(module, name)
        old = FunctionType(original.__code__, hs.__dict__, name, original.__defaults__)
        old.__kwdefaults__ = original.__kwdefaults__
        stack.enter_context(patch.object(hs, name, old))
        if name == "load_history_records":
            stack.enter_context(patch.object(sv, name, old))
            stack.enter_context(patch.object(app, name, old))
    return stack


def timed(fn):
    started = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("reference", "optimized"))
    parser.add_argument("workload", choices=("reads", "advance", "hydrate"))
    args = parser.parse_args()
    target = OUT / f"{args.mode}-{args.workload}"
    target.mkdir(parents=True, exist_ok=False)
    check_inputs()
    check_protection()
    report = {"mode": args.mode, "workload": args.workload, "runtime_hashes": fingerprints(),
              "reference_scope": "Exact pre-change inventory/read function code; all remaining code and validation safeguards are current and unchanged.",
              "status": "running"}
    with reference_implementation() if args.mode == "reference" else nullcontext():
        if args.workload in {"reads", "hydrate"}:
            source_hash = sha(SOURCE)
            raw = json.loads(SOURCE.read_text())
            database = hs.history_sidecar_path(SOURCE, raw)
            database_hash = sha(database)
            if args.workload == "reads":
                inventory, validation, loads = [], [], []
                with closing(hs._read_connection(database)) as connection:
                    for _ in range(5):
                        counts, duration = timed(lambda: hs._visible_counts(connection, raw["history_store"]["revision"]))
                        assert counts == raw["history_store"]["archived_counts"]
                        inventory.append(duration)
                for _ in range(3):
                    _, duration = timed(lambda: hs.validate_save_components(SOURCE, raw))
                    validation.append(duration)
                    saved, duration = timed(lambda: sv.load_save(SOURCE))
                    loads.append(duration)
                report.update(inventory_seconds=inventory, validation_seconds=validation, load_seconds=loads,
                              medians={"inventory": statistics.median(inventory), "validation": statistics.median(validation),
                                       "load": statistics.median(loads)}, result_digest=digest(business_state(saved)))
            else:
                saved, duration = timed(lambda: sv.load_save(SOURCE, include_history=True))
                report.update(seconds=duration, result_digest=digest(business_state(saved)),
                              history_counts={key: len(saved[key]) for key in hs.HISTORY_KEYS})
            assert sha(SOURCE) == source_hash and sha(database) == database_hash
            report.update(source_unchanged=True, source_hash=source_hash, database_hash=database_hash)
        else:
            path = target / "disposable.json"
            prepared_hash = sha(PREPARED)
            shutil.copy2(PREPARED, previous_backup_path(path))
            recover_previous_save(path)
            initial = sv.load_save(path)
            baseline = json.loads((ROOT / "output/simulation-memory-2026-10-24/after-final/mature-17/report.json").read_text())
            assert digest(business_state(initial)) == baseline["initial_digest"]
            source = canonical()
            result, duration = timed(lambda: app.dispatch_app_action("advance_save",
                {"save_path": str(path), "to_date": "2036-11-01", "checkpoint_days": 31, "seed": 17},
                root=ROOT, save_dir=target, canonical=source))
            saved = sv.load_save(path, include_history=True)
            state = business_state(saved)
            fields = {key: digest(value) for key, value in state.items()}
            assert fields == baseline["field_digests"], [key for key in fields if fields[key] != baseline["field_digests"].get(key)]
            assert sha(PREPARED) == prepared_hash
            report.update(seconds=duration, previous_pass_seconds=baseline["seconds"],
                          date=saved["state"]["current_date"], games=len(saved["schedule_state"]["simulated_game_ids"]),
                          result_digest=digest(state), field_digests=fields, same_initial_and_final_business_state=True,
                          status_from_app=result["status"])
        report.update(status="passed", peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if args.mode == "optimized" and args.workload in {"reads", "hydrate"}:
            prior = json.loads((OUT / f"reference-{args.workload}/report.json").read_text())
            assert report["result_digest"] == prior["result_digest"]
            assert report["source_hash"] == prior["source_hash"] and report["database_hash"] == prior["database_hash"]
            report["exact_reference_match"] = True
        check_inputs()
        check_protection()
        write(target / "report.json", report)
        print(json.dumps({key: value for key, value in report.items() if key not in {"runtime_hashes", "field_digests"}}), flush=True)


if __name__ == "__main__":
    main()
