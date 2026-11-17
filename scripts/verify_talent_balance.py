"""Versioned, disposable talent-balance experiments and real app-action careers."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import verify_roster_alignment as career_audit
from league_health_audit import add_probe_staff, census, converted_class, rank_band
from ten_season_soak import distribution
from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.health import advance_development
from nba_gm_data.ingest import build_universe
from nba_gm_data.save import apply_development_events_to_traits, canonical_with_save, load_save, player_display_attribute_summary
from nba_gm_data.save import set_save_date_phase, write_save, contract_salary_for_season
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.history_store import hydrate_save_history
from verify_simulation_consistency import business_state, digest, differences
from nba_gm_data.schema import to_plain
from nba_gm_data.storage import write_outputs
from nba_gm_data.draft import NBA_TRAIT_LABELS
from nba_gm_data.talent import SOURCE_ID, MODEL_VERSION

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/talent-balance-2026-10-23"
career_audit.OUT = OUT


def fingerprints():
    return {str(path.relative_to(ROOT)): career_audit.sha(path)
            for path in sorted((ROOT / "src/nba_gm_data").glob("*.py"))}


career_audit.frozen = fingerprints


def protected():
    report = json.loads((OUT / "protection.json").read_text())
    for key in ("protected", "archives"):
        assert all(career_audit.sha(path) == value for path, value in report[key].items()), key
    return report


def write(name, value):
    career_audit.write(OUT / name, value)


def survey():
    preservation = protected()
    universe = build_universe(ROOT)
    candidate = to_plain(universe)
    with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-player-tuning-v3.json.gz", "rt") as handle:
        before = json.load(handle)
    for key in ("players", "traits", "contracts", "draft_picks", "player_health_profiles", "player_health_states", "injury_events"):
        assert candidate[key] == before[key], key
    paths = write_outputs(universe, OUT / "candidate")
    # Pin the candidate for disposable-save reloads; do not publish canonical yet.
    career_audit.archive_candidate(candidate)
    snapshots = {}
    for label, canonical in (("before", before), ("after", candidate)):
        directory = OUT / "survey" / label
        if list(directory.glob("*.json")):
            raise FileExistsError("Survey save already exists; never overwrite a career")
        result = dispatch_app_action("create_save", {"team": "GSW", "seed": 17, "save_name": "talent_balance"},
                                     root=ROOT, save_dir=directory, canonical=deepcopy(canonical))
        saved = load_save(result["save_path"])
        snap = census(canonical_with_save(deepcopy(canonical), saved), saved)
        write(f"census-{label}.json", snap)
        snapshots[label] = career_audit.quality(snap)
    report = {"status": "passed", "protected": preservation["protected"],
              "source_hashes": fingerprints(), "candidate": str(paths["json"]),
              "candidate_sha256": career_audit.sha(paths["json"]), "snapshots": snapshots}
    protected()
    write("survey.json", report)
    print(json.dumps(snapshots, indent=2), flush=True)


def grades(context, legacy=False):
    view = {**context, "meta": {}} if legacy else context
    return {p["id"]: player_display_attribute_summary(view, p["id"])["overall"] for p in context["players"]}


def refresh():
    candidate = json.loads((OUT / "candidate/universe_2026_27_offseason.json").read_text())
    assert to_plain(build_universe(ROOT)) == candidate, "Regenerate the candidate when inputs/conversion change"
    report = json.loads((OUT / "survey.json").read_text())
    report["source_hashes"] = fingerprints()
    protected()
    write("survey.json", report)


def prepare_replay():
    with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-player-tuning-v3.json.gz", "rt") as handle:
        before = json.load(handle)
    for label, canonical in (("legacy", before), ("new", json.loads((OUT / "candidate/universe_2026_27_offseason.json").read_text()))):
        tag = hashlib.sha256(json.dumps(fingerprints(), sort_keys=True).encode()).hexdigest()[:12]
        directory = OUT / "replay" / "source" / label / tag
        result = dispatch_app_action("create_save", {"team": "GSW", "seed": 17, "save_name": "replay"},
                                     root=ROOT, save_dir=directory, canonical=canonical)
        path = Path(result["save_path"])
        saved = load_save(path)
        set_save_date_phase(saved, "2026-11-26")
        write_save(path, saved)
        (OUT / "replay" / f"{label}.zip").write_bytes(create_export(path))


def replay(label):
    if label == "before":
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-player-tuning-v3.json.gz", "rt") as handle:
            canonical = json.load(handle)
    else:
        canonical = json.loads((OUT / "candidate/universe_2026_27_offseason.json").read_text())
    path = OUT / "replay" / label / "career.json"
    restore_export(path, (OUT / "replay/legacy.zip").read_bytes())
    started = time.monotonic()
    dispatch_app_action("advance_save", {"save_path": str(path), "days": 7, "seed": 17},
                        root=ROOT, save_dir=path.parent, canonical=canonical)
    saved = hydrate_save_history(path, load_save(path))
    assert saved["state"]["current_date"] == "2026-12-03"
    state = business_state(saved)
    write(f"replay/{label}.json", state)
    # Development-only benchmark: identical input and result, no save writes.
    with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-player-tuning-v3.json.gz", "rt") as handle:
        context = json.load(handle)
    for trait in context["traits"]:
        trait["notes"] = str(trait.get("notes", "")) * 20
    tick = time.monotonic()
    for _ in range(10):
        development = advance_development(context, "2027-01", 17)
    result = {"label": label, "digest": digest(state), "advance_seconds": tick - started,
              "runtime_file": str(sys.modules["nba_gm_data.health"].__file__),
              "development_benchmark_seconds": time.monotonic() - tick,
              "development_digest": digest(development)}
    write(f"replay/{label}-summary.json", result)
    print(json.dumps(result), flush=True)


def partition():
    canonical = json.loads((OUT / "candidate/universe_2026_27_offseason.json").read_text())
    states = {}
    for label, intervals in (("daily", [1] * 7), ("weekly", [7])):
        path = OUT / "partition" / label / "career.json"
        restore_export(path, (OUT / "replay/new.zip").read_bytes())
        for days in intervals:
            dispatch_app_action("advance_save", {"save_path": str(path), "days": days, "seed": 17},
                                root=ROOT, save_dir=path.parent, canonical=deepcopy(canonical))
        saved = hydrate_save_history(path, load_save(path))
        assert saved["state"]["current_date"] == "2026-12-03"
        states[label] = business_state(saved)
    delta = differences(states["daily"], states["weekly"])
    write("partition.json", {"equal": not delta, "diffs": delta,
                             "digests": {key: digest(value) for key, value in states.items()}})
    assert not delta, delta


def probe():
    started = time.monotonic()
    source_hashes = fingerprints()
    canonical = json.loads((OUT / "candidate/universe_2026_27_offseason.json").read_text())
    team = canonical["teams"][0]
    rows = []
    for seed in (17, 29, 913):
        for year in (2027, 2031):
            for variant in ("legacy", "shape_only", "full"):
                generated, context = converted_class(year, seed, team, talent_model=variant != "legacy")
                if variant == "shape_only":
                    for trait in context["traits"]:
                        trait["components"].pop("career_capacity", None)
                add_probe_staff(context, 60)
                ages = {p["id"]: p["age"] for p in context["players"]}
                start, peak, legacy_peak = grades(context), {}, {}
                for month in range(217):
                    if month % 12 == 0:
                        current, old_scale = grades(context), grades(context, legacy=True)
                        for pid in current:
                            peak[pid] = max(peak.get(pid, 0), current[pid])
                            legacy_peak[pid] = max(legacy_peak.get(pid, 0), old_scale[pid])
                    if month in (0, 36, 84, 144, 216):
                        by_band = defaultdict(list)
                        for player in context["players"]:
                            by_band[rank_band(int(player["overall_pick"]))].append(current[player["id"]])
                        rows.append({"seed": seed, "year": year, "variant": variant, "month": month,
                                     "overall": distribution(current.values()), "90_plus": sum(v >= 90 for v in current.values()),
                                     "peak_90_plus": sum(v >= 90 for v in peak.values()),
                                     "legacy_scale_peak_90_plus": sum(v >= 90 for v in legacy_peak.values()),
                                     "below25_traits": sum(t["value"] < 25 for t in context["traits"]),
                                     "bands": {key: distribution(value) for key, value in by_band.items()},
                                     "careers": [{"id": p["id"], "rank": p["overall_pick"], "potential": p["potential"],
                                                  "entry": start[p["id"]], "current": current[p["id"]], "peak": peak[p["id"]],
                                                  "legacy_peak": legacy_peak[p["id"]]} for p in context["players"]]})
                    if month == 216:
                        break
                    for player in context["players"]:
                        player["age"] = ages[player["id"]] + month // 12
                        player["minutes_projection"] = 24
                    development = advance_development(context, f"{year + month // 12}-{month % 12 + 1:02}", seed)
                    apply_development_events_to_traits(context, development["events"])
                print(json.dumps({"seed": seed, "year": year, "variant": variant,
                                  "peak90": sum(v >= 90 for v in peak.values()),
                                  "legacy_peak90": sum(v >= 90 for v in legacy_peak.values())}), flush=True)
                write("controlled-probe.partial.json", rows)
    protected()
    assert fingerprints() == source_hashes, "Model changed while the probe was running"
    write("controlled-probe.json", {"source_hashes": source_hashes, "seconds": time.monotonic() - started,
                                    "scope": "Paired same-identity 18-year healthy 24-MPG mechanism probe. No games, salaries, roster competition, injuries, exits or retirement; not an equilibrium forecast or empirical bust rate.", "rows": rows})


def validate(args):
    career_audit.validate(args)
    candidate = json.loads((OUT / "candidate/universe_2026_27_offseason.json").read_text())
    result = {}
    scarcity = {}
    for seed in (17, 29):
        run = json.loads((OUT / f"career-{seed}/run.json").read_text())
        saved = load_save(run["save_path"])
        active = canonical_with_save(deepcopy(candidate), saved)
        assert active["meta"]["talent_model_version"] == MODEL_VERSION
        rookies = {r["player_id"] for r in saved["incoming_rookies"]
                   if r.get("roster_status") == "signed_rookie"}
        assert rookies, "No signed rookies to validate"
        players = {p["id"]: p for p in saved["generated_players"]}
        original = {(t["player_id"], t["trait_key"]): t for t in saved["generated_traits"]}
        reconstructed = {(t["player_id"], t["trait_key"]): t for t in active["traits"]}
        for pid in rookies:
            assert SOURCE_ID in players[pid]["source_ids"], pid
            assert {key for player_id, key in original if player_id == pid} == set(NBA_TRAIT_LABELS)
            for key in NBA_TRAIT_LABELS:
                trait = original[pid, key]
                profile = trait["components"]["career_capacity"]
                assert SOURCE_ID in trait["source_ids"] and profile["version"] == MODEL_VERSION
                assert reconstructed[pid, key]["components"]["career_capacity"] == profile
        result[str(seed)] = {"status": "passed", "signed_rookies": len(rookies),
                             "capacity_records_preserved": len(rookies) * len(NBA_TRAIT_LABELS)}
        snapshot = json.loads((OUT / f"career-{seed}/census-{saved['state']['current_date']}.json").read_text())
        scarcity[str(seed)] = scarcity_snapshot(active, saved, snapshot)
    protected()
    write("model-propagation.json", result)
    write("scarcity.json", scarcity)
    print(json.dumps(result), flush=True)


def scarcity_snapshot(active, saved, snapshot):
    players = {p["id"]: p for p in active["players"]}
    traits = defaultdict(dict)
    for trait in active["traits"]:
        traits[trait["player_id"]][trait["trait_key"]] = trait["value"]
    season = saved["meta"]["season"]
    previous = saved["season_history"][-1]
    stats = previous["player_season_stats"]
    salary = defaultdict(list)
    for contract in active["contracts"]:
        value = contract_salary_for_season(contract, season)
        if value is not None:
            salary[contract["player_id"]].append(value / 1_000_000)
    rows = []
    for row in snapshot["players"]:
        pid = row["id"]
        values = traits[pid]
        matches = salary[pid]
        line = stats.get(pid, {})
        games = int(line.get("games") or 0)
        rows.append({**row, "position": players[pid].get("position"),
                     "salary_millions": matches[0] if len(matches) == 1 else None,
                     "current_salary_record_count": len(matches),
                     "previous_season_games": games,
                     "previous_season_mpg": float(line["minutes"]) / games if games else None,
                     "shooting_range_below35": values.get("shooting_range", 50) < 35,
                     "screen_navigation_below40": values.get("screen_navigation", 50) < 40,
                     "passing_reads_below40": values.get("passing_reads", 50) < 40,
                     "rim_deterrence_below30": values.get("rim_deterrence", 50) < 30})
    groups = defaultdict(list)
    for row in rows:
        if row["rostered"]:
            groups[str(row["position"])].append(row)
    positions = {position: {"count": len(pool),
                           "salary_millions": distribution(r["salary_millions"] for r in pool if r["salary_millions"] is not None),
                           "salary_missing_or_ambiguous": sum(r["salary_millions"] is None for r in pool),
                           "previous_season_mpg": distribution(r["previous_season_mpg"] for r in pool if r["previous_season_mpg"] is not None),
                           "weakness_counts": {key: sum(r[key] for r in pool) for key in (
                               "shooting_range_below35", "screen_navigation_below40", "passing_reads_below40", "rim_deterrence_below30")}}
                 for position, pool in sorted(groups.items())}
    cohorts = defaultdict(list)
    for rookie in saved["incoming_rookies"]:
        line = stats.get(rookie["player_id"], {})
        games = int(line.get("games") or 0)
        cohorts[str(rookie["draft_year"])].append({"id": rookie["player_id"], "pick": rookie["overall_pick"],
                                                  "games": games, "mpg": float(line["minutes"]) / games if games else None})
    return {"scope": "Descriptive checkpoint, not economic equilibrium or NBA outcome-rate calibration. Salaries are scheduled current-year amounts, not guaranteed money. Archived playing-time totals may include postseason games. All picks remain in rookie cohort denominators, including non-survivors and those with no appearances.",
            "date": snapshot["date"], "salary_season": season, "playing_time_season": previous["season"],
            "positions": positions, "rookie_cohorts": dict(cohorts), "players": rows}


def classify():
    report = json.loads((OUT / "full-suite.json").read_text())
    known = set(json.loads((ROOT / "output/roster-alignment-2026-10-23/failed-test-ids.json").read_text()))
    methods = set(report["failed_methods"])
    gui = "test_gui_concept71.Concept71GuiTests.test_player_cards_show_spatial_maps_and_rating_averages"
    prior_gui = json.loads((OUT / "prior-player-card-recheck.json").read_text())
    assert gui in {row["id"] for row in prior_gui["failures"] + prior_gui["errors"]}
    result = {"source_hashes": fingerprints(), "tests": report["tests"],
              "failure_outcomes": len(report["failures"]), "errors": len(report["errors"]),
              "known_failing_methods": sorted(methods & known),
              "additional_preexisting_methods": [gui],
              "unclassified_methods": sorted(methods - known - {gui}),
              "baseline_comparison_scope": "Known method IDs from the earlier audit, not a claim that every old failure has an identical cause. The additional GUI assertion fails under frozen pre-task Python and unchanged UI assets.",
              "rechecks": {"launcher": "Initial startup timeout; standalone recheck and final sweep case pass.",
                           "concurrent_creation": "Audit runner needed a main-entry guard for spawn; game rules unchanged; final case passes.",
                           "trade_authorization": "Positive market fixture pinned to immutable V3; all authorization and actual transaction-application assertions retained. Correct-resource-root frozen runtime passes. Initial oracle resource-path error is not evidence of an old gameplay failure."}}
    assert report["tests"] >= 605 and not result["unclassified_methods"]
    assert fingerprints() == json.loads((OUT / "survey.json").read_text())["source_hashes"]
    protected()
    write("test-classification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"source_hashes", "known_failing_methods"}}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("survey", "refresh", "probe", "prepare_replay", "replay", "partition", "career", "soak", "validate", "classify", "publish"))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--seasons", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--label", default="after", choices=("before", "after"))
    args = parser.parse_args()
    # Match the existing audit harness: reference counting handles these trees;
    # yearly subprocess exits bound memory without repeated full-heap scans.
    if args.mode in {"career", "soak", "probe"}:
        gc.disable()
    if args.mode == "survey":
        survey()
    elif args.mode == "probe":
        probe()
    elif args.mode == "refresh":
        refresh()
    elif args.mode == "prepare_replay":
        prepare_replay()
    elif args.mode == "replay":
        replay(args.label)
    elif args.mode == "partition":
        partition()
    elif args.mode == "career":
        class ActionCheckpoint(BaseException):
            pass
        original_action = career_audit.SoakRunner.action
        actions_completed = 0
        def bounded_action(runner, name, **payload):
            nonlocal actions_completed
            decision_or_query = name in {"staff_retention_room", "roster_cutdown", "resolve_staff_retention", "waive_player"}
            if actions_completed and not decision_or_query:
                raise ActionCheckpoint()
            result = original_action(runner, name, **payload)
            if not decision_or_query:
                actions_completed += 1
            return result
        career_audit.SoakRunner.action = bounded_action
        source_hashes = fingerprints()
        try:
            career_audit.career(args)
        except ActionCheckpoint:
            assert fingerprints() == source_hashes
            protected()
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0)
    elif args.mode == "soak":
        for _ in range(200):
            manifest = OUT / f"career-{args.seed}/run.json"
            if manifest.exists() and json.loads(manifest.read_text())["status"] == "passed":
                return
            subprocess.run([sys.executable, "-B", __file__, "career", "--seed", str(args.seed),
                            "--seasons", str(args.seasons), "--resume"], check=True)
        raise RuntimeError("Career segment budget exhausted")
    elif args.mode == "validate":
        validate(args)
    elif args.mode == "classify":
        classify()
    else:
        protected()
        probe_report = json.loads((OUT / "controlled-probe.json").read_text())
        assert probe_report["source_hashes"] == fingerprints()
        validation = json.loads((OUT / "career-validation.json").read_text())
        assert set(validation) == {"17", "29"}
        assert all(row["status"] == "passed" and row["complete_seasons"] >= 2 for row in validation.values())
        propagation = json.loads((OUT / "model-propagation.json").read_text())
        assert set(propagation) == {"17", "29"} and all(row["status"] == "passed" for row in propagation.values())
        tests = json.loads((OUT / "test-classification.json").read_text())
        assert tests["source_hashes"] == fingerprints() and not tests["unclassified_methods"]
        before = json.loads((OUT / "replay/before-summary.json").read_text())
        after = json.loads((OUT / "replay/after-summary.json").read_text())
        assert before["digest"] == after["digest"] and before["development_digest"] == after["development_digest"]
        assert json.loads((OUT / "partition.json").read_text())["equal"]
        career_audit.publish()


if __name__ == "__main__":
    main()
