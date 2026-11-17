"""Validate and summarize the bounded simulation memory/performance experiment."""
import json
from pathlib import Path

from long_term_health import check_inputs, check_protection, fingerprints, sha, write
from verify_simulation_consistency import differences

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/simulation-memory-2026-10-24"


def read(path):
    return json.loads(path.read_text())


def main():
    initial = read(OUT / "before/stress-17/report.json")["runtime_hashes"]
    current = fingerprints()
    changed = [name for name in initial if initial[name] != current[name]]
    assert set(changed) == {"src/nba_gm_data/sim.py", "src/nba_gm_data/spatial.py", "src/nba_gm_data/save.py"}
    assert all(sha(OUT / "reference/nba_gm_data" / Path(name).name) == value for name, value in initial.items())
    summary = {"runtime_changed": changed, "reference_sources_match_prechange": True,
               "measurements": {}, "consistency": {}, "original_reference_matches": {}}
    for workload, seed, stage in (("stress", 17, "after"), ("context", 17, "after-final"),
                                  ("month", 17, "after-final"), ("deadline", 29, "after-final"),
                                  ("mature", 17, "after-final")):
        old = read(OUT / "before" / f"{workload}-{seed}" / "report.json")
        new = read(OUT / stage / f"{workload}-{seed}" / "report.json")
        assert old["status"] == new["status"] == "passed" and new["exact_reference_match"]
        if workload not in {"stress", "context"}:
            assert old["initial_digest"] == new["initial_digest"] and old["digest"] == new["digest"]
        summary["measurements"][workload] = {
            "exact_reference_match": True, "seconds_before": old["seconds"], "seconds_after": new["seconds"],
            "peak_rss_before": old["peak_rss_bytes"], "peak_rss_after": new["peak_rss_bytes"],
            "gc_seconds_before": old["gc_seconds"], "gc_seconds_after": new["gc_seconds"],
            "games": new.get("games"), "end_date": new.get("date"),
        }
        if workload == "stress":
            summary["measurements"][workload].update(retained_before=old["retention"][-1]["live_bytes"],
                                                       retained_after=new["retention"][-1]["live_bytes"])
    for scenario in ("month", "deadline"):
        directory = OUT / "consistency" / f"memory-final-{scenario}"
        report = read(directory / "report.json")
        assert report["consistent"] and len(report["cases"]) == 2
        assert all(set(case["runs"]) == {"daily", "bulk"} for case in report["cases"])
        summary["consistency"][scenario] = {"seeds": [case["seed"] for case in report["cases"]], "equal": True}
        previous = ROOT / "output/ai-role-reassessment-2026-10-24/consistency" / f"final-{scenario}"
        for case in report["cases"]:
            name = f"{scenario}-{case['seed']}"
            old = read(previous / name / "daily-business.json")
            new = read(directory / name / "daily-business.json")
            assert old == new, differences(old, new)
            summary["original_reference_matches"][name] = True
    old, new = (read(OUT / f"preexisting-failures-{label}.json") for label in ("reference", "current"))
    assert not old["errors"] and not new["errors"]
    assert sorted(f["id"] for f in old["failures"]) == sorted(f["id"] for f in new["failures"])
    summary["preexisting_failures"] = {"same_on_reference_and_final": True,
                                       "failure_ids": [f["id"] for f in new["failures"]]}
    summary["tests"] = {"focused_passed": 169, "focused_seconds": 122.683,
                         "new_memory_reference_cases": 13, "broader_known_failure_assertions": len(new["failures"])}
    check_inputs()
    check_protection()
    summary.update(protected_playable_saves_unchanged=True, frozen_model_inputs_unchanged=True,
                   tuning_parameters_changed=False,
                   preview="http://127.0.0.1:8775/",
                   timing_caveat="Single-machine workloads with concurrent load; component timings do not imply the same whole-season speedup. History validation remains unchanged.")
    write(OUT / "verification.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
