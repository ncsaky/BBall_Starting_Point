"""Replay full mature-save months and compare every hydrated business-state field."""
import argparse
import gc
import json
import sys

import long_term_health as audit
from nba_gm_data.history_store import hydrate_save_history
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import create_export, restore_export
from verify_simulation_consistency import business_state, digest, differences

REFERENCE = audit.AUDIT_ROOT
OUT = REFERENCE / "performance"


def prepare():
    if (OUT / "protection.json").exists():
        raise FileExistsError("Replay already prepared")
    hashes = audit.fingerprints()
    for seed in (17, 29):
        prior = json.loads((REFERENCE / f"career-{seed}/run.json").read_text())
        changed = [path for path, value in prior["source_hashes"].items() if hashes[path] != value]
        assert changed == ["src/nba_gm_data/save.py"], changed
        assert prior["endpoint"] == "2028-11-01"
        source = audit.SOURCE / f"career-{seed}/saves/roster_alignment.json"
        path = OUT / f"career-{seed}/saves/career.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        restore_export(path, create_export(source))
        audit.write(path.parents[1] / "run.json", {"seed": seed, "save_path": str(path), "status": "running",
                    "source_hashes": hashes, "baseline_sha256": audit.sha(audit.BASELINE),
                    "starting_date": "2028-10-01", "actions": [], "reference_save": prior["save_path"]})
    audit.write(OUT / "protection.json", json.loads((REFERENCE / "protection.json").read_text()))


def compare():
    recorded_path = OUT / "parity.json"
    recorded = json.loads(recorded_path.read_text()) if recorded_path.exists() else None
    result = {}
    for seed in (17, 29):
        replay = json.loads((OUT / f"career-{seed}/run.json").read_text())
        prior = json.loads((REFERENCE / f"career-{seed}/run.json").read_text())
        actual = business_state(hydrate_save_history(replay["save_path"], load_save(replay["save_path"])))
        assert actual["state"]["current_date"] == "2028-11-01"
        if prior["endpoint"] == "2028-11-01":
            expected = business_state(hydrate_save_history(prior["save_path"], load_save(prior["save_path"])))
            changes = differences(expected, actual)
            assert not changes, changes
        else:
            # The original continuation moved forward after the two-sided
            # comparison. Preserve that proof; recheck its retained replay.
            assert recorded and replay["source_hashes"] == recorded["source_hashes"]
            assert digest(actual) == recorded["cases"][str(seed)]["digest"]
        result[str(seed)] = {"equal": True, "digest": digest(actual), "before_seconds": prior["actions"][0]["seconds"],
                             "before_profiled": prior["actions"][0]["profiled"], "after_seconds": replay["actions"][0]["seconds"],
                             "scope": "Same mature V4 save, seed and hands-off decisions; October 1 through November 1. All hydrated history and business fields, excluding existing incidental path/revision/timestamp normalization."}
    audit.check_protection()
    if recorded is None:
        audit.write(recorded_path, {"source_hashes": audit.fingerprints(), "cases": result})
    else:
        audit.write(OUT / "retained-replay-recheck.json", {"original_source_hashes": recorded["source_hashes"],
                    "scope": "Recheck of retained historical replay files, not a new execution under current source.", "cases": result})
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "replay", "compare"))
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    gc.disable()
    if args.mode == "prepare":
        prepare()
    elif args.mode == "replay":
        report = json.loads((OUT / f"career-{args.seed}/run.json").read_text())
        if report["actions"]:
            raise FileExistsError("Replay already completed; compare it rather than advance again")
        audit.OUT = OUT
        audit.step(argparse.Namespace(seed=args.seed, seasons=10, profile=False))
    else:
        compare()
    sys.stdout.flush()
