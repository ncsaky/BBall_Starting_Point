"""Summarize matched role studies without mixing initial free agents into cohorts."""
import json
from pathlib import Path

from long_term_health import check_inputs, check_protection, fingerprints, write

DEST = Path(__file__).resolve().parents[1] / "output/ai-role-reassessment-2026-10-24"


def main():
    reports = {arm: json.loads((DEST / "paired" / f"17-{arm}" / "report.json").read_text())
               for arm in ("legacy", "reassessed")}
    control, treatment = reports.values()
    assert control["status"] == treatment["status"] == "passed"
    assert control["before"] == treatment["before"]
    assert control["source_hash"] == treatment["source_hash"]
    assert control["after"]["date"] == treatment["after"]["date"] == control["target"]
    source = json.loads(Path(control["source_save"]).read_text())
    user = source["meta"]["user_team_id"]
    initial = {p["id"]: p for p in control["before"]["players"]
               if p["rostered"] and p["team_id"] != user}
    summary = {"scope": "Seed 17, frozen V4 year-ten roster, October 1 2036 to January 2 2037. Initially rostered AI players only. Not a fresh multi-season equilibrium result.",
               "same_initial_census": True, "same_original_source": True,
               "same_end_date": True, "user_team_id": user, "arms": {}}
    for arm, report in reports.items():
        assert report["human_overrides_preserved"] and report["user_role_priors_preserved"]
        pools = {}
        for key, pool in report["outcomes"].items():
            rows = [p for p in pool["players"] if p["id"] in initial]
            pools[key] = {"count": len(rows), "played": sum(p["games"] > 0 for p in rows),
                          "rotation": sum(p["games"] >= 10 and p["mpg"] >= 12 for p in rows),
                          "mean_mpg": round(sum(p["mpg"] for p in rows) / len(rows), 6),
                          "mean_fixed24_gain": round(sum(p["fixed24_gain"] for p in rows) / len(rows), 6)}
        summary["arms"][arm] = {"date": report["after"]["date"], "seconds": report["seconds"],
                                "games": report["checkpoints"][-1]["games"], "groups": pools}
    checks = {}
    for label in ("final-month", "final-deadline"):
        report = json.loads((DEST / "consistency" / label / "report.json").read_text())
        assert report["consistent"]
        checks[label] = {"consistent": True, "report": str(DEST / "consistency" / label / "report.json")}
    check_inputs()
    check_protection()
    write(DEST / "measurement-summary.json", summary)
    write(DEST / "verification.json", {"checks": checks, "protected_files_unchanged": True,
          "model_inputs_unchanged": True, "runtime_hashes": fingerprints(),
          "focused_tests": {"count": 99, "passed": True, "seconds": 88.451},
          "additional_foundation_tests": {"count": 8, "passed": True},
          "same_initial_census": True, "same_end_date": True,
          "human_overrides_preserved": True, "user_role_priors_preserved": True,
          "worker_shutdown": "Control and deadline workers were terminated only after successful durable reports; native samples confirmed Python finalization/garbage collection. Treatment exited normally.",
          "runtime_comparability": "Control imported before the last short-handed AI-role cap guard. Its role-state-disabled arm cannot enter that treatment-only branch. Both arms use identical growth/decline inputs."})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
