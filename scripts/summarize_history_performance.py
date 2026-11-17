"""Check evidence for the bounded, rule-preserving history performance pass."""
import json
from pathlib import Path
import statistics

from long_term_health import check_inputs, check_protection, fingerprints, sha, write
from nba_gm_data.save import load_save
from verify_simulation_consistency import business_state, digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/history-performance-2026-10-24"


def read(path):
    return json.loads(path.read_text())


def main():
    before = read(OUT / "before-runtime.json")
    now = fingerprints()
    assert [name for name in before if before[name] != now[name]] == ["src/nba_gm_data/history_store.py"]
    assert sha(OUT / "reference_history_store.py") == before["src/nba_gm_data/history_store.py"]
    tests = read(OUT / "tests.json")
    known = read(OUT / "reference-known-failures.json")
    assert not tests["errors"] and not known["errors"]
    assert sorted(f["id"] for f in tests["failures"]) == sorted(known["failures"])
    summary = {"changed_runtime_modules": ["src/nba_gm_data/history_store.py"],
               "exact_prechange_reference_verified": True,
               "tests": {"run": tests["tests"], "passed": tests["tests"] - len(tests["failures"]),
                         "preexisting_failure_ids": known["failures"], "errors": []},
               "measurements": {}, "consistency": {}}
    for workload in ("reads", "hydrate"):
        reference, optimized = (read(OUT / f"{mode}-{workload}/report.json") for mode in ("reference", "optimized"))
        assert optimized["exact_reference_match"] and reference["result_digest"] == optimized["result_digest"]
        summary["measurements"][workload] = {"exact_reference_match": True,
            "reference": {k: reference[k] for k in ("seconds", "medians", "peak_rss_bytes") if k in reference},
            "optimized": {k: optimized[k] for k in ("seconds", "medians", "peak_rss_bytes") if k in optimized}}
    pairs = read(OUT / "paired-counts.json")
    assert pairs["equal"]
    summary["measurements"]["paired_counts"] = {mode: statistics.median(row["seconds"] for row in pairs["samples"] if row["name"] == mode)
                                                  for mode in ("reference", "optimized")}
    summary["measurements"]["paired_validation"] = read(OUT / "paired-validation.json")["medians"]
    advance = read(OUT / "optimized-advance/report.json")
    assert advance["status"] == "passed" and advance["same_initial_and_final_business_state"]
    summary["measurements"]["real_app_31_days"] = {key: advance[key] for key in
        ("seconds", "previous_pass_seconds", "games", "date", "result_digest", "same_initial_and_final_business_state")}
    for scenario in ("month", "deadline"):
        folder = OUT / "consistency" / f"history-{scenario}"
        report = read(folder / "report.json")
        assert report["consistent"]
        for case in report["cases"]:
            name = f"{scenario}-{case['seed']}"
            prior_folder = ROOT / "output/simulation-memory-2026-10-24/consistency" / f"memory-final-{scenario}" / name
            current = read(folder / name / "daily-business.json")
            initial = business_state(load_save(folder / name / "baseline.json"))
            if scenario == "deadline":
                # This run starts with seed 29, not a reused universe after 17.
                prior_folder = ROOT / "output/simulation-memory-2026-10-24/after-final/deadline-29"
                prior_report = read(prior_folder / "report.json")
                assert digest(initial) == prior_report["initial_digest"]
                previous = read(prior_folder / "business.json")
            else:
                assert initial == business_state(load_save(prior_folder / "baseline.json"))
                previous = read(prior_folder / "daily-business.json")
            assert current == previous, name
        summary["consistency"][scenario] = {"seeds": [case["seed"] for case in report["cases"]],
                                              "daily_bulk_equal": True, "prechange_business_state_equal": True}
    check_inputs()
    check_protection()
    summary.update(protected_playable_saves_unchanged=True, model_inputs_unchanged=True,
                   persistent_validation_cache_added=False, integrity_checks_skipped=False,
                   schema_changed=False, league_health_runs_started=False,
                   preview="http://127.0.0.1:8776/",
                   timing_caveat="Paired validation/count timings alternate old/new methods on the same database. Separate app/hydration workloads had varying concurrent machine load and are observations, not general speed guarantees.")
    write(OUT / "verification.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
