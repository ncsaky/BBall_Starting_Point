"""Compare real app advances from identical isolated league snapshots."""

from __future__ import annotations

import argparse
import cProfile
from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import time

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save import create_league_save, load_save, set_save_date_phase, write_save
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.utils import clear_utility_caches


ROOT = Path(__file__).resolve().parents[1]
INCIDENTAL = {"created_at", "updated_at", "timestamp", "save", "save_path"}


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k not in INCIDENTAL}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def business_state(saved):
    result = clean(saved)
    result.pop("history_store", None)
    for key in ("save_revision", "save_snapshot_id"):
        result.get("meta", {}).pop(key, None)
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def differences(left, right, prefix="", limit=8):
    if type(left) is not type(right):
        return [{"path": prefix, "left": str(left)[:120], "right": str(right)[:120]}]
    if isinstance(left, dict):
        out = []
        for key in sorted(left.keys() | right.keys()):
            out.extend(differences(left.get(key), right.get(key), f"{prefix}.{key}", limit))
            if len(out) >= limit:
                break
        return out[:limit]
    if isinstance(left, list):
        out = [] if len(left) == len(right) else [{"path": prefix + ".length", "left": len(left), "right": len(right)}]
        for idx, (a, b) in enumerate(zip(left, right)):
            out.extend(differences(a, b, f"{prefix}[{idx}]", limit))
            if len(out) >= limit:
                break
        return out[:limit]
    return [] if left == right else [{"path": prefix, "left": left, "right": right}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--seeds", default="17")
    parser.add_argument("--scenarios", default="week")
    parser.add_argument("--modes", default="daily,weekly,bulk,next_event")
    parser.add_argument("--days", type=int)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "output/simulation-consistency")
    args = parser.parse_args()
    if args.days is not None and args.days < 1:
        parser.error("--days must be positive")
    output = args.output / args.label
    output.mkdir(parents=True, exist_ok=True)
    canonical = load_app_canonical(ROOT)
    scenarios = {"week": ("2026-11-14", "2026-11-21"),
                 "month": ("2026-10-28", "2026-11-30"),
                 "deadline": ("2027-01-31", "2027-02-07")}
    report = {"label": args.label, "source_hashes": {name: hashlib.sha256((ROOT / "src/nba_gm_data" / name).read_bytes()).hexdigest()
                                                     for name in ["save.py", "app_actions.py", "pick_presentation.py"]}, "cases": []}
    for scenario in args.scenarios.split(","):
        start, target = scenarios[scenario]
        if args.days is not None:
            target = (date.fromisoformat(start) + timedelta(days=args.days)).isoformat()
        for seed in map(int, args.seeds.split(",")):
            case_dir = output / f"{scenario}-{seed}"
            case_dir.mkdir()
            base_path = case_dir / "baseline.json"
            create_league_save(ROOT, canonical, "GSW", base_path, seed=seed)
            base = load_save(base_path)
            set_save_date_phase(base, start)
            write_save(base_path, base)
            archive = create_export(base_path)
            case = {"scenario": scenario, "seed": seed, "from": start, "target": target, "runs": {}}
            snapshots = {}
            for mode in args.modes.split(","):
                path = case_dir / (mode + ".json")
                restore_export(path, archive)
                current = start
                calls = []
                started = time.perf_counter()
                while current < target:
                    if mode == "daily":
                        payload = {"days": 1}
                    elif mode == "weekly":
                        payload = {"days": min(7, (date.fromisoformat(target) - date.fromisoformat(current)).days)}
                    elif mode == "next_event":
                        payload = {"next_event": True}
                        # A final partial interval must reach the same endpoint.
                        from nba_gm_data.save import next_event_date
                        if (next_event_date(ROOT, canonical, load_save(path)) or target) > target:
                            payload = {"to_date": target}
                    else:
                        payload = {"to_date": target, "checkpoint_days": 31}
                    payload.update(save_path=str(path), seed=seed)
                    from nba_gm_data.save import trade_deadline_date, season_start_year_from_date
                    if current == trade_deadline_date(season_start_year_from_date(current)):
                        payload["trade_deadline_confirmed"] = current
                    if args.profile:
                        profiler = cProfile.Profile()
                        result = profiler.runcall(dispatch_app_action, "advance_save", payload, root=ROOT, save_dir=case_dir, canonical=canonical)
                        profiler.dump_stats(str(case_dir / f"{mode}-{len(calls)}.prof"))
                    else:
                        result = dispatch_app_action("advance_save", payload, root=ROOT, save_dir=case_dir, canonical=canonical)
                    updated = load_save(path)
                    reached = updated["state"]["current_date"]
                    calls.append({"from": current, "through": reached, "status": result["status"]})
                    if reached <= current:
                        raise AssertionError(f"Advance made no progress: {calls[-1]}")
                    current = reached
                saved = load_save(path, include_history=True)
                snapshot = business_state(saved)
                snapshots[mode] = snapshot
                (case_dir / (mode + "-business.json")).write_text(json.dumps(snapshot, sort_keys=True, indent=2) + "\n")
                row = {"seconds": round(time.perf_counter() - started, 3), "calls": calls, "date": current,
                       "offers": len(snapshot["user_trade_offers"] or []),
                       "transactions": dict(Counter(x.get("transaction_type") for x in snapshot["transaction_logs"] or [])),
                       "games": len((snapshot["schedule_state"] or {}).get("simulated_game_ids", [])),
                       "digests": {key: digest(value) for key, value in snapshot.items()}}
                case["runs"][mode] = row
                print(json.dumps({"scenario": scenario, "seed": seed, "mode": mode, **{k: v for k, v in row.items() if k not in {"digests", "calls"}}}), flush=True)
                clear_utility_caches()
            reference = next(iter(snapshots))
            case["comparisons"] = {mode: {"equal": snapshots[mode] == snapshots[reference],
                "different_fields": [key for key in sorted(snapshots[mode].keys() | snapshots[reference].keys())
                                     if snapshots[mode].get(key) != snapshots[reference].get(key)],
                "sample": differences(snapshots[reference], snapshots[mode])}
                for mode in snapshots if mode != reference}
            report["cases"].append(case)
            (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({"scenario": scenario, "seed": seed, "comparisons": case["comparisons"]}), flush=True)
    report["consistent"] = all(c["equal"] for case in report["cases"] for c in case["comparisons"].values())
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
