"""Verify the isolated before/after runs for trade presentation deferral."""

from __future__ import annotations

import json
from pathlib import Path
import pstats
from statistics import median

from verify_simulation_consistency import differences


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/trade-presentation-task-1"
PRESENTATION_FUNCTIONS = (
    "trade_value_breakdown",
    "package_value_breakdown",
    "trade_evaluation_payload",
    "candidate_from_evaluation",
    "evaluation_notes",
    "proposal_summary",
    "trade_headline_from_payload",
)


def load_run(name: str) -> tuple[dict, dict]:
    directory = OUTPUT / name
    return (json.loads((directory / "report.json").read_text()),
            json.loads((directory / "business.json").read_text()))


def profile_counts(name: str) -> dict[str, int]:
    stats = pstats.Stats(str(OUTPUT / name / "advance.prof"))
    counts = {}
    for (_file, _line, function), (_primitive, calls, _self, _cumulative, _callers) in stats.stats.items():
        if function in PRESENTATION_FUNCTIONS:
            counts[function] = calls
    return counts


def compare(reference_name: str, after_name: str) -> dict:
    before_report, before_state = load_run(reference_name)
    after_report, after_state = load_run(after_name)
    if before_state != after_state:
        raise AssertionError(f"Meaningful save mismatch ({reference_name} vs {after_name}): "
                             f"{differences(before_state, after_state, limit=30)}")
    if before_report["progress_digest"] != after_report["progress_digest"]:
        raise AssertionError(f"Ordered event mismatch ({reference_name} vs {after_name})")
    for key in ("pending_trade_proposals", "pending_ai_actions", "user_trade_offers",
                "transaction_logs", "processed_hidden_ai_actions"):
        if before_state.get(key) != after_state.get(key):
            raise AssertionError(f"Proposal/decision mismatch at {key} ({reference_name} vs {after_name})")
    if not before_report.get("source_unchanged") or not after_report.get("source_unchanged"):
        raise AssertionError(f"An input save changed ({reference_name} vs {after_name})")
    return {
        "reference": reference_name,
        "after": after_name,
        "from": after_report["from"],
        "through": after_report["through"],
        "reference_seconds": before_report["seconds"],
        "after_seconds": after_report["seconds"],
        "reduction_percent": round((1 - after_report["seconds"] / before_report["seconds"]) * 100, 2),
        "business_state_equal": True,
        "proposals_and_decisions_equal": True,
        "ordered_events_equal": True,
        "progress_frames": after_report["progress_frames"],
        "progress_kinds": after_report["progress_kinds"],
        "progress_digest": after_report["progress_digest"],
    }


def main() -> None:
    cases = [
        compare("reference-seed17-day", "after-seed17-day"),
        compare("reference-seed17-repeat", "after-seed17-repeat"),
        compare("reference-seed29-day", "after-seed29-day"),
        compare("reference-month17", "after-month17"),
    ]
    before_counts = profile_counts("profile-before")
    after_counts = profile_counts("profile-after-verified")
    presentation_calls = {
        name: {"before": before_counts.get(name, 0), "after": after_counts.get(name, 0)}
        for name in PRESENTATION_FUNCTIONS
    }
    profile_before = json.loads((OUTPUT / "profile-before/report.json").read_text())
    profile_after = json.loads((OUTPUT / "profile-after-verified/report.json").read_text())
    if (profile_before["digest"] != profile_after["digest"]
            or profile_before["progress_digest"] != profile_after["progress_digest"]):
        raise AssertionError("The profiled parity pair did not match.")
    report = {
        "cases": cases,
        "unprofiled_seed17_median_before_seconds": round(median(
            row["reference_seconds"] for row in cases[:2]), 3),
        "unprofiled_seed17_median_after_seconds": round(median(
            row["after_seconds"] for row in cases[:2]), 3),
        "profiled_attribution_seconds": {
            "before": profile_before["seconds"],
            "after": profile_after["seconds"],
        },
        "presentation_calls_profiled": presentation_calls,
        "profiled_business_state_equal": True,
        "profiled_ordered_events_equal": True,
        "limits": [
            "Profiled seconds include profiler overhead; compare only with profiled seconds.",
            "The seed-29 input is a disposable copy of the seed-17 February save with meta.seed set to 29.",
            "The October fixture is a disposable republished copy of the archived October 28 seed-17 save.",
            "Each action uses a separate export; source saves were unchanged.",
        ],
    }
    path = OUTPUT / "comparison.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
