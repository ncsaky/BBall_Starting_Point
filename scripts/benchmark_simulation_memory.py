"""Measure disposable app advances and temporary-universe retention."""
import argparse
import gc
import json
from pathlib import Path
import resource
import shutil
import time
import tracemalloc

from nba_gm_data import save as sv, sim, spatial
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save_recovery import create_export, previous_backup_path, recover_previous_save, restore_export
from nba_gm_data.schema import to_plain
from long_term_health import canonical as old_canonical, check_inputs, check_protection, fingerprints, sha, write
from verify_simulation_consistency import business_state, digest, differences

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/simulation-memory-2026-10-24"
PREPARED = ROOT / "output/ai-role-reassessment-2026-10-24/prepared/seed17.nbagm.zip"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("before", "after"))
    parser.add_argument("workload", choices=("stress", "context", "month", "deadline", "mature"))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--variant", choices=("final",))
    args = parser.parse_args()
    directory = OUT / (args.stage + ("-" + args.variant if args.variant else "")) / f"{args.workload}-{args.seed}"
    directory.mkdir(parents=True, exist_ok=False)
    report = {"stage": args.stage, "workload": args.workload, "seed": args.seed,
              "runtime_hashes": fingerprints(),
              "loaded_module_hashes": {module.__name__: sha(module.__file__) for module in (sv, sim, spatial)},
              "status": "running"}
    gc_started, gc_seconds, gc_count = {}, 0.0, 0

    def gc_timing(phase, info):
        nonlocal gc_seconds, gc_count
        generation = info["generation"]
        if phase == "start":
            gc_started[generation] = time.perf_counter()
        elif generation in gc_started:
            gc_seconds += time.perf_counter() - gc_started.pop(generation)
            gc_count += 1

    gc.callbacks.append(gc_timing)
    if args.workload == "context":
        source = old_canonical()
        durations = []
        for _ in range(20):
            started = time.perf_counter()
            context = sim.load_sim_context(ROOT, source)
            del context
            durations.append(time.perf_counter() - started)
        context = sim.load_sim_context(ROOT, source)
        report.update(seconds=sum(durations), samples=durations,
                      reference_digest=digest({key: context[key] for key in ("schedule", "real_minutes", "boxscores", "odds", "manifestos")}))
    elif args.workload == "stress":
        source = old_canonical()
        path = ROOT / "output/ai-role-reassessment-2026-10-24/paired/17-legacy/disposable.json"
        source_hash = sha(path)
        saved = sv.load_save(path)
        active = sv.canonical_with_save(source, saved)
        template = {key: value for key, value in active.items() if not str(key).startswith("_")}
        players = [p["id"] for p in active["players"] if p.get("team_id")][:8]
        del active
        tracemalloc.start()
        started = time.perf_counter()
        samples, signatures = [], []
        for index in range(20):
            universe = sv._copy_runtime_tree(template)
            universe["_allow_internal_caches"] = True
            by_id = {p["id"]: p for p in universe["players"]}
            signatures.append(digest([to_plain(sim.player_feature_vector(universe, by_id[pid])) for pid in players]))
            spatial._trait_index(universe)
            del universe, by_id
            if index in (0, 4, 9, 19):
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                samples.append({"universes": index + 1, "live_bytes": current, "peak_bytes": peak,
                                "sim_entries": len(sim._SIM_FEATURE_CACHE),
                                "spatial_entries": len(spatial._SPATIAL_INDEX_CACHE)})
        report.update(seconds=time.perf_counter() - started, retention=samples, signatures=signatures,
                      source_hash=source_hash, trait_rows=len(template["traits"]))
        assert sha(path) == source_hash
        tracemalloc.stop()
    else:
        path = directory / "disposable.json"
        if args.workload == "mature":
            source = old_canonical()
            archive_hash = sha(PREPARED)
            shutil.copy2(PREPARED, previous_backup_path(path))
            recover_previous_save(path)
            saved = sv.load_save(path)
            start, target = "2036-10-01", "2036-11-01"
            assert saved["state"]["current_date"] == start
            report["initial_archive_hash"] = archive_hash
        else:
            source = load_app_canonical(ROOT)
            start, target = (("2026-10-28", "2026-11-05") if args.workload == "month"
                             else ("2027-01-31", "2027-02-07"))
            fixture = OUT / "fixtures" / f"{args.workload}-{args.seed}.nbagm.zip"
            if not fixture.exists():
                assert args.stage == "before", "Run the before workload to prepare identical fixtures"
                fixture.parent.mkdir(parents=True, exist_ok=True)
                base_path = fixture.with_suffix(".json")
                sv.create_league_save(ROOT, source, "GSW", base_path, seed=args.seed)
                saved = sv.load_save(base_path)
                sv.set_save_date_phase(saved, start)
                sv.write_save(base_path, saved)
                fixture.write_bytes(create_export(base_path))
            restore_export(path, fixture.read_bytes())
            report["initial_archive_hash"] = sha(fixture)
        initial = business_state(sv.load_save(path))
        report.update(start=start, target=target, initial_digest=digest(initial))
        started = time.perf_counter()
        current, calls = start, []
        while current < target:
            payload = {"save_path": str(path), "to_date": target, "checkpoint_days": 31, "seed": args.seed}
            deadline = sv.trade_deadline_date(sv.season_start_year_from_date(current))
            if current == deadline:
                payload["trade_deadline_confirmed"] = deadline
            result = dispatch_app_action("advance_save", payload, root=ROOT, save_dir=directory, canonical=source)
            saved = sv.load_save(path)
            reached = saved["state"]["current_date"]
            assert reached > current and reached <= target, result
            calls.append({"from": current, "through": reached, "status": result["status"]})
            print(args.stage, args.workload, args.seed, calls[-1], flush=True)
            current = reached
        report["seconds"] = time.perf_counter() - started
        final = business_state(sv.load_save(path, include_history=True))
        write(directory / "business.json", final)
        report.update(calls=calls, date=current, digest=digest(final),
                      games=len(final["schedule_state"]["simulated_game_ids"]),
                      field_digests={key: digest(value) for key, value in final.items()})
        if args.workload == "mature":
            assert sha(PREPARED) == archive_hash
    report.update(peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  gc_seconds=gc_seconds, gc_count=gc_count,
                  sim_entries=len(sim._SIM_FEATURE_CACHE), spatial_entries=len(spatial._SPATIAL_INDEX_CACHE),
                  status="passed")
    if args.stage == "after":
        before_dir = OUT / "before" / directory.name
        before = json.loads((before_dir / "report.json").read_text())
        if args.workload == "context":
            assert before["reference_digest"] == report["reference_digest"]
        elif args.workload == "stress":
            assert before["signatures"] == report["signatures"]
        else:
            assert before["initial_digest"] == report["initial_digest"]
            assert before["initial_archive_hash"] == report["initial_archive_hash"]
            prior = json.loads((before_dir / "business.json").read_text())
            assert final == prior, differences(prior, final)
        report["exact_reference_match"] = True
    gc.callbacks.remove(gc_timing)
    check_inputs()
    check_protection()
    write(directory / "report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"runtime_hashes", "field_digests", "signatures"}}), flush=True)


if __name__ == "__main__":
    main()
