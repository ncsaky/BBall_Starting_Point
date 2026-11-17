"""Checkpoint real V4 app-action careers, one major action per disposable worker."""
import argparse
from collections import defaultdict
import cProfile
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import pstats
import shutil
import signal
import subprocess
import sys
import time

try:
    import resource
except ImportError:
    resource = None

from league_health_audit import census, career_action, regular_complete
from ten_season_soak import SoakRunner, distribution
from verify_talent_balance import scarcity_snapshot
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import canonical_with_save, load_save, presentation_rating_value, team_cap_summary
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.talent import SOURCE_ID

ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = ROOT / "output/league-health-longrun-2026-10-23"
OUT = AUDIT_ROOT / "corrected"
SOURCE = ROOT / "output/talent-balance-2026-10-23"
BASELINE = ROOT / "data/canonical/baselines/2026-10-23-talent-v4.json.gz"
INPUTS = [ROOT / "data/overrides" / name for name in (
    "injury_model_config.json", "draft_model_config.json", "contract_market_config.json", "transaction_model_config.json")]
INPUTS += [ROOT / "data/research/shot_chart_model.json", ROOT / "NBA Schedule/schedule_v2025_2026.json",
           ROOT / "scripts/league_health_audit.py", ROOT / "scripts/ten_season_soak.py"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(temporary, path)


def fingerprints():
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted((ROOT / "src/nba_gm_data").glob("*.py"))}


def protected_files():
    paths = [p for p in (ROOT / "saves").rglob("*") if p.is_file() and p.suffix in {".json", ".sqlite", ".sqlite3"}]
    paths += list((ROOT / "data/canonical/baselines").glob("*.json.gz"))
    for seed in (17, 29):
        paths += [p for p in (SOURCE / f"career-{seed}").rglob("*") if p.is_file() and p.suffix in {".json", ".sqlite", ".sqlite3"}]
    for seed in (17, 29, 913):
        paths += [p for p in (AUDIT_ROOT / f"career-{seed}").rglob("*") if p.is_file() and p.suffix in {".json", ".sqlite", ".sqlite3"}]
    return {str(p): sha(p) for p in paths}


def check_protection():
    record = json.loads((OUT / "protection.json").read_text())
    assert all(sha(path) == digest for path, digest in record.items()), "Protected file changed"


def freeze_inputs():
    target = OUT / "input-hashes.json"
    if target.exists():
        check_inputs()
        return
    began = (OUT / "lineage.json").stat().st_mtime_ns
    assert all(path.stat().st_mtime_ns <= began for path in INPUTS), "A model input changed after audit preparation"
    write(target, {str(path): sha(path) for path in INPUTS})


def check_inputs():
    target = OUT / "input-hashes.json"
    if target.exists():
        assert all(sha(path) == digest for path, digest in json.loads(target.read_text()).items()), "Model input or decision policy changed"


def canonical():
    with gzip.open(BASELINE, "rt") as handle:
        value = json.load(handle)
    value.update(_allow_internal_caches=True, _baseline_directory=str(BASELINE.parent))
    return value


def prepare_fresh():
    if (OUT / "protection.json").exists():
        raise FileExistsError("Corrected audit already exists")
    write(OUT / "protection.json", protected_files())
    write(OUT / "lineage.json", {"reason": "Restart from fresh V4 careers after the stale draft-year gate allowed later classes to enter at rollover instead of draft night.",
                               "source_hashes": fingerprints(), "rejected_root": str(AUDIT_ROOT),
                               "model_changes": "None. Data-copy optimization and draft chronology fix only."})
    freeze_inputs()
    check_protection()
    print("Fresh corrected audit prepared", flush=True)


def bootstrap(args):
    directory = OUT / f"career-{args.seed}"
    if (directory / "run.json").exists():
        raise FileExistsError("Career already exists")
    check_protection()
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(directory), seed=args.seed, team="GSW"))
    runner.canonical = canonical()
    lineage = "Independent fresh V4 career; same model and hands-off user policy."
    if args.resume_first_year:
        old_run = json.loads((AUDIT_ROOT / f"career-{args.seed}/run.json").read_text())
        previous = load_save(old_run["save_path"])
        stamp = previous["state"]["current_date"]
        assert "2027-07-01" <= stamp <= "2027-09-30" and not previous["season_history"]
        regular_complete(previous)
        cohort = [r for r in previous["incoming_rookies"] if str(r["draft_year"]) == "2027"]
        assert len(cohort) == len({r["player_id"] for r in cohort}) == 60
        months = defaultdict(set)
        events = load_history_records(old_run["save_path"], previous, "development_events") + previous.get("development_events", [])
        for event in events:
            months[event["player_id"]].add(event["month"])
        elapsed = {f"2027-{month:02}" for month in range(7, min(9, int(stamp[5:7])) + 1)}
        assert all(elapsed <= months[r["player_id"]] for r in cohort)
        path = str(directory / "saves/career.json")
        restore_export(path, create_export(old_run["save_path"]))
        for source in (AUDIT_ROOT / f"career-{args.seed}").glob("census-*.json"):
            shutil.copyfile(source, directory / source.name)
        lineage = f"Forked a verified clean first year before first rollover at {stamp}: 1230 regular games, 60 unique 2027 rookies and every elapsed first-summer development month {sorted(elapsed)} present. Future summer months remain to be simulated and validated. No stale-year draft bypass has occurred."
    else:
        result = runner.action("create_save", team="GSW", seed=args.seed, save_name=f"health_{args.seed}")
        path = result["save_path"]
    saved = load_save(path)
    snap = census(canonical_with_save(runner.canonical, saved), saved)
    write(directory / f"census-{snap['date']}.json", snap)
    write(directory / "run.json", {"seed": args.seed, "save_path": path, "status": "running",
          "source_hashes": fingerprints(), "baseline_sha256": sha(BASELINE),
          "starting_date": snap["date"], "actions": [], "endpoint": snap["date"], "complete_seasons": 0,
          "lineage_note": lineage})
    check_protection()
    print(json.dumps({"seed": args.seed, "created": path}), flush=True)


def validate_current_rookie_summer(saved, year):
    cohort = [r for r in saved.get("incoming_rookies", []) if str(r["draft_year"]) == str(year)]
    planned = ((saved.get("draft_orders") or {}).get(str(year)) or {}).get("draft_order") or []
    assert planned and len(cohort) == len(planned)
    assert len({r["player_id"] for r in cohort}) == len(cohort)
    assert {r["overall_pick"] for r in cohort} == {r["overall_pick"] for r in planned}
    months = defaultdict(set)
    for event in saved.get("development_events", []):
        months[event["player_id"]].add(event["month"])
    summer = {f"{year}-{month:02}" for month in (7, 8, 9)}
    signed = [r for r in cohort if r.get("roster_status") == "signed_rookie"]
    for rookie in signed:
        assert summer <= months[rookie["player_id"]], (rookie["player_id"], summer - months[rookie["player_id"]])
    return {"year": str(year), "eligible_picks": len(planned), "unique_rookies": len(cohort),
            "signed_rookies_with_full_first_summer": len(signed), "months": sorted(summer), "status": "passed"}


def checkpoint(directory, active, saved):
    stamp = saved["state"]["current_date"]
    if not stamp.endswith("-10-01"):
        return
    for season in saved.get("season_history", []):
        regular_complete({"team_records": season["team_records"]})
        assert season["draft_result"]["status"] == "already_present", "Draft class was created late at rollover"
    summer = validate_current_rookie_summer(saved, stamp[:4])
    write(directory / f"draft-summer-{stamp[:4]}.json", summer)
    snapshot = census(active, saved)
    assert snapshot["rostered"]["health_profile_missing"] == 0
    assert len(snapshot["roster_counts_by_team"]) == 30
    assert min(snapshot["roster_counts_by_team"].values()) >= 14
    write(directory / f"census-{stamp}.json", snapshot)
    scarcity = scarcity_snapshot(active, saved, snapshot)
    scarcity["team_cap_summaries"] = {team["id"]: team_cap_summary(active, saved, team["id"])
                                     for team in active["teams"]}
    scarcity["above_game_hard_cap"] = {team: row for team, row in scarcity["team_cap_summaries"].items()
                                       if row["hard_cap_space_millions"] < -0.01}
    cap_millions = next(iter(scarcity["team_cap_summaries"].values()))["hard_cap_millions"]
    for row in scarcity["players"]:
        row["salary_pct_of_game_hard_cap"] = (row["salary_millions"] / cap_millions * 100
                                               if row["salary_millions"] is not None else None)
    for position, group in scarcity["positions"].items():
        group["salary_pct_of_game_hard_cap"] = distribution(
            row["salary_pct_of_game_hard_cap"] for row in scarcity["players"]
            if row["rostered"] and row["position"] == position and row["salary_pct_of_game_hard_cap"] is not None)
    scarcity["finance_scope"] = "Scheduled payroll against the game's own hard-cap model. Salary percentages use that season's growing game hard cap, not the NBA salary cap. This is not a certification of NBA CBA legality; pre-existing salary-legality failures remain separate risks."
    write(directory / f"scarcity-{stamp}.json", scarcity)


def step(args):
    check_inputs()
    directory = OUT / f"career-{args.seed}"
    report = json.loads((directory / "run.json").read_text())
    assert report["source_hashes"] == fingerprints(), "Runtime changed; require a documented parity check before resume"
    assert sha(BASELINE) == report["baseline_sha256"]
    runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(directory), seed=args.seed, team="GSW"))
    runner.canonical = canonical()
    runner.payload["save_path"] = report["save_path"]
    saved = runner.load()
    target = f"{2026 + args.seasons}-10-01"
    assert saved["state"]["current_date"] <= target
    if saved["state"]["current_date"] == target:
        checkpoint(directory, canonical_with_save(runner.canonical, saved), saved)
        report.update(status="passed", endpoint=target, complete_seasons=len(saved["season_history"]))
        write(directory / "run.json", report)
        return
    if saved["state"]["current_date"].endswith("-10-01") and not (directory / f"scarcity-{saved['state']['current_date']}.json").exists():
        checkpoint(directory, canonical_with_save(runner.canonical, saved), saved)
    runner.resolve_user_staff_retention()
    runner.resolve_user_roster_cutdown()
    saved = runner.load()
    action, payload = career_action(saved, 31, "GSW")
    started = time.monotonic()
    profiler = cProfile.Profile() if args.profile else None
    try:
        if profiler:
            profiler.enable()
        result = runner.action(action, save_path=report["save_path"], seed=args.seed, **payload)
    finally:
        if profiler:
            profiler.disable()
            tag = saved["state"]["current_date"]
            profiler.dump_stats(directory / f"profile-{tag}.pstats")
            with (directory / f"profile-{tag}.txt").open("w") as handle:
                pstats.Stats(profiler, stream=handle).strip_dirs().sort_stats("cumulative").print_stats(65)
    after = runner.load()
    if (action == "draft_sim_all" and (after.get("draft_state") or {}).get("status") != "completed"
            and (after.get("draft_state") or {}).get("current_index") == (saved.get("draft_state") or {}).get("current_index")):
        write(directory / "blocked-action.json", {"date": after["state"]["current_date"], "action": action, "result": result})
        raise RuntimeError("Draft action made no progress; checkpoint retained for investigation")
    row = {"action": action, "from": saved["state"]["current_date"], "to": after["state"]["current_date"],
           "seconds": round(time.monotonic() - started, 3), "profiled": bool(profiler)}
    if resource is not None:
        divisor = 1024 ** 2 if sys.platform == "darwin" else 1024
        row["peak_rss_mib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor, 1)
    assert row["to"] <= target
    assert row["to"] != row["from"] or action != "advance_save", "No calendar progress"
    report["actions"].append(row)
    report.update(status="running", endpoint=row["to"], complete_seasons=len(after.get("season_history", [])))
    if row["to"].endswith("-10-01"):
        checkpoint(directory, canonical_with_save(runner.canonical, after), after)
    if row["to"] == target:
        report["status"] = "passed"
    assert report["source_hashes"] == fingerprints()
    check_inputs()
    write(directory / "run.json", report)
    print(json.dumps({"seed": args.seed, **row}), flush=True)


def run(args):
    stop_requested = False

    def request_stop(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    previous = signal.signal(signal.SIGTERM, request_stop)
    try:
        for _ in range(500):
            if stop_requested:
                check_protection()
                return
            report = json.loads((OUT / f"career-{args.seed}/run.json").read_text())
            if report.get("endpoint") == f"{2026 + args.seasons}-10-01" and report["status"] == "passed":
                check_protection()
                return
            subprocess.run([sys.executable, "-B", __file__, "step", "--seed", str(args.seed), "--seasons", str(args.seasons)], check=True)
        raise RuntimeError("Action budget exhausted; checkpoint retained")
    finally:
        signal.signal(signal.SIGTERM, previous)


def adopt_alignment_repair():
    evidence = OUT / "draft-slot-repair-final/verification.json"
    proof = json.loads(evidence.read_text())
    current = fingerprints()
    assert proof["source_hashes"] == current and proof["status"] == "passed"
    assert proof["eligible_selections"] == 59 and proof["newly_applied"] == 35
    assert proof["prefix_preserved"] and proof["repeat_did_not_duplicate_records"]
    assert sha(proof["source"]) == proof["source_save_sha256"]
    for seed in (17, 29, 913):
        path = OUT / f"career-{seed}/run.json"
        report = json.loads(path.read_text())
        changed = {p for p, value in report["source_hashes"].items() if current[p] != value}
        assert changed == {"src/nba_gm_data/play.py", "src/nba_gm_data/app_actions.py"}, changed
        report.setdefault("runtime_epochs", []).append({"from_date": report["endpoint"],
                    "previous_source_hashes": report["source_hashes"], "source_hashes": current,
                    "evidence": str(evidence), "reason": "Align eligible pending draft slots with saved lottery gaps, preserving the consumed prefix and every remaining prospect."})
        report["source_hashes"] = current
        write(path, report)
    check_protection()
    check_inputs()
    print("Verified draft-slot alignment adopted at saved action boundaries", flush=True)


def summarize():
    output = {}
    for directory in sorted(OUT.glob("career-*")):
        seed = int(directory.name.split("-")[-1])
        snapshots = annual_snapshots(directory)
        rows = []
        for snap in snapshots:
            roster = [p for p in snap["players"] if p["rostered"]]
            grades = [presentation_rating_value(p["fixed24_engine"]) for p in roster]
            legacy = [presentation_rating_value(p["legacy_fixed24_engine"]) for p in roster]
            generated = [p for p in roster if int(p.get("draft_year") or 0) >= 2027]
            rows.append({"date": snap["date"], "rostered": len(roster), "overall": distribution(grades),
                         "90_plus": sum(v >= 90 for v in grades), "legacy_90_plus": sum(v >= 90 for v in legacy),
                         "generated_90_plus": sum(presentation_rating_value(p["fixed24_engine"]) >= 90 for p in generated),
                         "actual_retirements": snap["retired_count"], "league_exits": snap["league_exit_count"],
                         "by_age": {age: distribution(presentation_rating_value(p["fixed24_engine"]) for p in roster
                                                      if str(int(float(p["age"]))) == age)
                                    for age in sorted({str(int(float(p["age"]))) for p in roster})}})
        output[str(seed)] = rows
    write(OUT / "summary.json", output)
    print(json.dumps({seed: [{k: r[k] for k in ("date", "rostered", "90_plus", "generated_90_plus", "actual_retirements")} for r in rows]
                      for seed, rows in output.items()}, indent=2))


def annual_snapshots(directory):
    snapshots = [json.loads(path.read_text()) for path in sorted(directory.glob("census-*.json"))]
    return [row for row in snapshots if row["date"] == "2026-07-28" or row["date"].endswith("-10-01")]


def validate():
    output = {}
    for directory in sorted(OUT.glob("career-*")):
        report = json.loads((directory / "run.json").read_text())
        saved = load_save(report["save_path"])
        for history in saved["season_history"]:
            regular_complete({"team_records": history["team_records"]})
            assert history["draft_result"]["status"] == "already_present", "Draft class was created late at rollover"
        years = defaultdict(list)
        for row in saved.get("incoming_rookies", []):
            years[str(row["draft_year"])].append(row)
        expected_years = {str(2027 + offset) for offset in range(len(saved["season_history"]))}
        assert set(years) == expected_years
        for year, rows in years.items():
            planned = (saved.get("draft_orders", {}).get(year) or {}).get("draft_order") or []
            assert planned, f"Missing actual order for {year}"
            assert len(rows) == len({r["player_id"] for r in rows}) == len(planned)
            assert {r["overall_pick"] for r in rows} == {r["overall_pick"] for r in planned}
        events = {r["id"]: r for r in load_history_records(report["save_path"], saved, "development_events")}
        for row in saved.get("development_events", []):
            assert row["id"] not in events or events[row["id"]] == row
            events[row["id"]] = row
        assert len(events) == len({(r["player_id"], r["month"]) for r in events.values()})
        endpoint = saved["state"]["current_date"]
        absolute_end = int(endpoint[:4]) * 12 + int(endpoint[5:7])
        expected = {f"{value // 12}-{value % 12 + 1:02}" for value in range(2026 * 12 + 7, absolute_end)}
        assert {r["month"] for r in events.values()} == expected
        months_by_player = defaultdict(set)
        for event in events.values():
            months_by_player[event["player_id"]].add(event["month"])
        players = {p["id"]: p for p in saved.get("generated_players", [])}
        traits = defaultdict(list)
        for trait in saved.get("generated_traits", []):
            traits[trait["player_id"]].append(trait)
        for rookie in saved.get("incoming_rookies", []):
            if rookie.get("roster_status") != "signed_rookie":
                continue
            pid = rookie["player_id"]
            assert SOURCE_ID in players[pid]["source_ids"]
            assert len(traits[pid]) == len({t["trait_key"] for t in traits[pid]}) == 15
            assert all(t["components"]["career_capacity"]["version"] == 2 for t in traits[pid])
            summer = {f"{rookie['draft_year']}-{month:02}" for month in (7, 8, 9)}
            assert summer <= months_by_player[pid], (pid, "Rookie missed first summer development", summer - months_by_player[pid])
        retired = set(saved.get("retired_player_ids") or []) - set(saved.get("league_exit_player_ids") or [])
        records = [r for report in saved.get("retirement_reports", []) for r in report["retirements"]]
        assert len(records) == len(retired) and {r["player_id"] for r in records} == retired
        output[str(report["seed"])] = {"endpoint": endpoint, "completed_seasons": len(saved["season_history"]),
                                       "regular_games": len(saved["season_history"]) * 1230,
                                       "draft_picks": sum(map(len, years.values())), "development_months": len(expected),
                                       "unique_development_events": len(events), "actual_retirements": len(retired),
                                       "status": "passed"}
    check_protection()
    write(OUT / "validation.json", output)
    print(json.dumps(output, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "prepare-fresh", "freeze-inputs", "adopt-alignment", "bootstrap", "step", "run", "summarize", "validate"))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--seasons", type=int, default=10)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--resume-first-year", action="store_true")
    args = parser.parse_args()
    gc.disable()
    if args.mode in {"prepare", "prepare-fresh"}:
        prepare_fresh()
    elif args.mode == "freeze-inputs":
        freeze_inputs()
    elif args.mode == "adopt-alignment":
        adopt_alignment_repair()
    elif args.mode == "bootstrap":
        bootstrap(args)
    elif args.mode == "step":
        step(args)
    elif args.mode == "run":
        run(args)
    elif args.mode == "validate":
        validate()
    else:
        summarize()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
