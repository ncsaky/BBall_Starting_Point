"""Materialize a verified local audit runtime, then reconcile stopped checkpoints.

No playable saves are opened. The stopped disposable batch is moved, not copied,
and a locator is left behind. Simulation inputs must match the frozen experiment.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SOURCE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_OUT = SOURCE_ROOT / "output/market-lifecycle-2026-10-25-r2"
LOCAL_ROOT = Path.home() / ".cache/nba-gm-audits/market-lifecycle-2026-10-25/runtime"
SCRIPTS = (
    "overnight_market_health.py", "background_league_health.py", "long_term_health.py",
    "league_health_audit.py", "ten_season_soak.py", "verify_talent_balance.py",
    "verify_roster_alignment.py", "verify_simulation_consistency.py",
    "review_market_lifecycle.py", "local_market_audit.py",
)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


COPY_CODE = r'''
import hashlib,json,os,sys
from pathlib import Path
source,target=map(Path,sys.argv[1:3]);expected=sys.argv[3]
before=source.stat();target.parent.mkdir(parents=True,exist_ok=True)
temporary=target.with_name(target.name+'.materializing')
digest=hashlib.sha256();size=0
with source.open('rb') as src,temporary.open('wb') as dst:
    for block in iter(lambda:src.read(1024*1024),b''):
        dst.write(block);digest.update(block);size+=len(block)
    dst.flush();os.fsync(dst.fileno())
after=source.stat();actual=digest.hexdigest()
assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'Source changed during copy'
assert size==before.st_size,'Short source read'
assert not expected or actual==expected,'Frozen input mismatch: '+str(source)
with temporary.open('rb') as handle:assert hashlib.file_digest(handle,'sha256').hexdigest()==actual,'Local copy mismatch'
temporary.replace(target)
print(json.dumps({'sha256':actual,'bytes':size}))
'''


def materialize(source, target, expected=None, *, timeout=45, attempts=2):
    error = None
    for attempt in range(attempts):
        try:
            result = subprocess.run([str(Path(sys.executable).resolve()), "-B", "-c", COPY_CODE,
                                     str(source), str(target), expected or ""], capture_output=True,
                                    text=True, timeout=timeout, check=True)
            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            error = exc
            if isinstance(exc, subprocess.CalledProcessError) and "Frozen input mismatch" in exc.stderr:
                raise RuntimeError(exc.stderr) from exc
            print(f"Read retry {attempt + 1}/{attempts}: {source}", flush=True)
    raise RuntimeError(f"Cannot materialize required file; no workers started: {source}: {error}") from error


def prepare():
    root = LOCAL_ROOT.resolve()
    if root.is_relative_to(Path.home() / "Documents") or root.is_relative_to(SOURCE_ROOT):
        raise ValueError("Local runtime must be outside Documents and the source workspace")
    if (root / "snapshot.json").exists():
        raise FileExistsError("Local runtime already prepared")
    old = json.loads((SOURCE_OUT / "inputs.json").read_text())
    selected = {name: digest for name, digest in old.items() if not name.startswith("scripts/")}
    # Strategy text was previously loaded by simulation but omitted from the
    # audit's input inventory. Freeze it explicitly along with the code helpers.
    selected.update({str(path.relative_to(SOURCE_ROOT)): None
                     for path in (SOURCE_ROOT / "Pre-Season manifestos").glob("*.txt")})
    selected.update({f"scripts/{name}": None for name in SCRIPTS})
    selected["pyproject.toml"] = None
    root.mkdir(parents=True, exist_ok=True)
    report = {"source_root": str(SOURCE_ROOT), "source_batch": str(SOURCE_OUT),
              "python": str(Path(sys.executable).resolve()), "files": {}, "status": "materializing"}
    for name, expected in sorted(selected.items()):
        report["files"][name] = materialize(SOURCE_ROOT / name, root / name, expected)
        write(root / "materialization.json", report)
    report["status"] = "verified"
    write(root / "snapshot.json", report)
    write(root / "local-runtime.json", {"blocked_roots": [str(Path.home() / "Documents")],
          "source_root": str(SOURCE_ROOT), "purpose": "Frozen local market/lifecycle experiment; no cloud reads allowed"})
    print(f"Verified {len(report['files'])} local runtime/input files", flush=True)


def migrate():
    root = LOCAL_ROOT.resolve()
    snapshot = json.loads((root / "snapshot.json").read_text())
    if snapshot["status"] != "verified":
        raise RuntimeError("Materialization has not completed")
    for name, row in snapshot["files"].items():
        if sha(root / name) != row["sha256"]:
            raise RuntimeError(f"Local snapshot changed: {name}")
    target = root / "output" / SOURCE_OUT.name
    if target.exists():
        raise FileExistsError("Migration already started; inspect its report instead of repeating")
    with (SOURCE_OUT / "batch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status = json.loads((SOURCE_OUT / "status.json").read_text())
        if status["status"] == "running":
            raise RuntimeError("Stop the original supervisor before migrating")
        hashes = {str(path.relative_to(SOURCE_OUT)): sha(path) for path in SOURCE_OUT.rglob("*") if path.is_file()}
        target.parent.mkdir(parents=True, exist_ok=True)
        if SOURCE_OUT.stat().st_dev != target.parent.stat().st_dev:
            raise RuntimeError("Refusing a cross-volume move that could duplicate the save data")
        SOURCE_OUT.rename(target)
        assert all(sha(target / name) == digest for name, digest in hashes.items())
        SOURCE_OUT.mkdir()
        write(SOURCE_OUT / "local-audit.json", {"runtime_root": str(root), "output_dir": str(target),
                                               "python": snapshot["python"]})
        write(target / "migration.json", {"from": str(SOURCE_OUT), "to": str(target),
              "method": "same-volume rename; every file hash verified before any metadata rebasing",
              "original_file_hashes": hashes, "source_inputs_verified": True})
    sys.path[:0] = [str(root / "src"), str(root / "scripts")]
    import overnight_market_health as audit

    for seed in audit.SEEDS:
        path = target / f"career-{seed}/run.json"
        report = json.loads(path.read_text())
        old_save = Path(report["save_path"])
        relative = old_save.relative_to(SOURCE_OUT)
        report["save_path"] = str(target / relative)
        write(path, report)
    canonical = audit.read_gzip(target / "canonical.json.gz")
    canonical["_baseline_directory"] = str(root / "data/canonical/baselines")
    audit.write_gzip(target / "canonical.json.gz", canonical)
    (target / "inputs.json").rename(target / "inputs.before-local-migration.json")
    write(target / "inputs.json", {str(path.relative_to(root)): sha(path) for path in audit.inputs()})
    # From here on, any read of the old workspace is a hard error, including
    # accidental save paths or a missed absolute baseline-directory reference.
    os.chdir(root)
    audit.install_local_read_guard(root)
    audit.check_inputs(target)
    print(f"Moved and verified disposable audit: {target}", flush=True)


def reconcile():
    root = LOCAL_ROOT.resolve()
    sys.path[:0] = [str(root / "src"), str(root / "scripts")]
    import overnight_market_health as audit
    from nba_gm_data.save import canonical_with_save, load_save
    from nba_gm_data.save_recovery import restore_export
    from verify_simulation_consistency import business_state, digest, differences
    from tempfile import TemporaryDirectory
    from argparse import Namespace

    os.chdir(root)
    audit.install_local_read_guard(root)
    out = root / "output" / SOURCE_OUT.name
    audit.check_inputs(out)
    results = {}
    for seed in audit.SEEDS:
        directory = out / f"career-{seed}"
        report_path = directory / "run.json"
        report = json.loads(report_path.read_text())
        runner = audit.runner_for(out, seed)
        saved = runner.load()
        audit.validate_season_clock(saved)
        observations = sorted((directory / "observations").glob("*.json.gz"))
        observed = audit.read_gzip(observations[-1])
        current = audit.census(canonical_with_save(runner.canonical, saved), saved)
        for key in ("date", "season", "phase", "regular_games", "roster_counts_by_team", "phase_state"):
            if current[key] != observed[key]:
                raise RuntimeError(f"Seed {seed}: checkpoint observation mismatch: {key}")
        recorded = {row["id"]: row for row in observed["players"]}
        for row in current["players"]:
            for key, value in row.items():
                if recorded[row["id"]][key] != value:
                    raise RuntimeError(f"Seed {seed}: player checkpoint mismatch: {row['id']}/{key}")
        pending = directory / "pending-action.json"
        result = {"save_date": current["date"], "report_date": report["endpoint"],
                  "observation_matches_save": True}
        if pending.exists() and current["date"] != report["endpoint"]:
            # Verify a committed-but-unlogged action by exact deterministic
            # replay from the existing previous-save archive. Never replay it
            # into the actual resumed career or assume it did not execute.
            backup = Path(report["save_path"] + ".previous.nbagm.zip")
            with TemporaryDirectory(prefix="reconcile-", dir=out) as scratch:
                reference_path = Path(scratch) / "saves/reference.json"
                restore_export(reference_path, backup.read_bytes())
                reference = audit.SoakRunner(Namespace(root=str(root), output_dir=scratch, seed=seed, team="GSW"))
                reference.canonical = audit.read_gzip(out / "canonical.json.gz")
                reference.payload["save_path"] = str(reference_path)
                before = reference.load()
                if before["state"]["current_date"] != report["endpoint"]:
                    raise RuntimeError("Recovery archive is not the preceding checkpoint; cannot reconcile safely")
                action, payload = audit.select_action(before, report["target"])
                reference.action(action, save_path=str(reference_path), seed=seed, **payload)
                left = business_state(load_save(report["save_path"], include_history=True))
                right = business_state(load_save(reference_path, include_history=True))
                if left != right:
                    write(directory / "reconciliation-differences.json", differences(left, right))
                    raise RuntimeError(f"Seed {seed}: deterministic replay did not match committed state")
                result.update(replay_digest=digest(left), replay_matches_all_meaningful_state=True,
                              decision="adopt_verified_committed_action_without_resimulating_career")
                report["actions"].append({"action": action, "from": report["endpoint"], "to": current["date"],
                    "phase": current["phase"], "seconds": 0, "timing_unknown": True,
                    "result_status": "reconciled_committed_action",
                    "new_development_months": observed.get("new_development_months", [])})
                report.update(endpoint=current["date"], complete_seasons=len(saved.get("season_history", [])))
        elif pending.exists():
            result["decision"] = "retry_from_unchanged_validated_checkpoint"
        else:
            if report["endpoint"] != current["date"]:
                raise RuntimeError("Unjournaled progress without a pending marker")
            result["decision"] = "resume_validated_checkpoint"
        report["status"] = "running"
        write(report_path, report)
        if pending.exists():
            destination = directory / "reconciled/pending-action.before-local-resume.json"
            destination.parent.mkdir(exist_ok=True)
            pending.replace(destination)
        results[str(seed)] = result
        write(out / "resume-reconciliation.json", results)
        print(json.dumps({"seed": seed, **result}), flush=True)
    audit.check_inputs(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "migrate", "reconcile"))
    args = parser.parse_args()
    globals()[args.mode]()


if __name__ == "__main__":
    main()
