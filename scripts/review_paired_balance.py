"""Read-only review of the frozen paired balance batch; never advance saves."""
import argparse
import ast
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

from nba_gm_data.health import prospect_development_realization
from review_completed_market_health import career, fixed_display, metrics, draft_band
from ten_season_soak import distribution

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BATCH = Path.home()/".cache/nba-gm-audits/paired-balance-2026-10-26"


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def read(path):
    with gzip.open(path,"rt") as handle:
        return json.load(handle)


def verify_runtime(runtime, manifest, arm):
    snapshot = json.loads((runtime/"snapshot.json").read_text())
    assert snapshot["status"] == "verified"
    assert all(sha(runtime/name) == row["sha256"] for name,row in snapshot["files"].items())
    changes = {name for name,old in manifest["source_hashes"].items() if sha(runtime/name) != old}
    assert changes == ({"src/nba_gm_data/health.py","src/nba_gm_data/draft.py"} if arm=="control" else set()), changes
    # The analysis must not silently use a newly changed rating transform or
    # seeded realization function against the historical observations.
    for name, functions in (("save",("presentation_rating_value",)),("health",("prospect_development_realization",))):
        frozen = ast.parse((runtime/f"src/nba_gm_data/{name}.py").read_text())
        current = ast.parse((ROOT/f"src/nba_gm_data/{name}.py").read_text())
        for function in functions:
            a = next(n for n in frozen.body if isinstance(n,ast.FunctionDef) and n.name==function)
            b = next(n for n in current.body if isinstance(n,ast.FunctionDef) and n.name==function)
            assert ast.dump(a) == ast.dump(b), f"Analysis helper changed: {function}"
    return {"all_frozen_hashes_match":True,"changed_vs_source":sorted(changes)}


def detail(out, seed):
    directory = out/f"career-{seed}"
    run = json.loads((directory/"run.json").read_text())
    saved = json.loads(Path(run["save_path"]).read_text())
    histories = defaultdict(list)
    rotations = defaultdict(set)
    annual = []
    initial = None
    latest = None
    for path in sorted((directory/"observations").glob("*.json.gz")):
        snap = read(path)
        initial = initial or snap
        latest = snap
        if snap["date"].endswith("-10-01"):
            roster = [p for p in snap["players"] if p["rostered"]]
            annual.append({"date":snap["date"],"active_pool":metrics(snap["players"]),
                "by_age":{label:metrics(p for p in roster if check(float(p.get("age") or 0)))
                    for label,check in (("under_23",lambda a:a<23),("23_27",lambda a:23<=a<28),
                        ("28_31",lambda a:28<=a<32),("32_plus",lambda a:a>=32))},
                "baseline_rostered":metrics(p for p in roster if int(p.get("draft_year") or 0)<2027),
                "generated_rostered":metrics(p for p in roster if int(p.get("draft_year") or 0)>=2027)})
        complete = snap["phase"]=="regular_season" and snap["date"].endswith("-04-12")
        for p in snap["players"]:
            if int(p.get("draft_year") or 0)<2027:
                continue
            histories[p["id"]].append((snap["date"],p))
            if complete and p.get("games",0)>=20 and p.get("mpg",0)>=16:
                rotations[p["id"]].add(snap["season"])
    endpoint = {p["id"]:p for p in latest["players"]}
    inactive = set(saved.get("retired_player_ids") or [])
    exited = set(saved.get("league_exit_player_ids") or [])
    # The legacy inactive flag deliberately includes league exits. Count true
    # retirement separately, as the runtime census and retirement reports do.
    retired = inactive - exited
    cohorts = []
    for p in saved.get("generated_players",[]):
        year = int(p.get("draft_year") or 0)
        if year<2027:
            continue
        observations = histories[p["id"]]
        values = [fixed_display(r) for stamp,r in observations]
        end = endpoint.get(p["id"],{})
        star = next(((stamp,r) for stamp,r in observations if fixed_display(r)>=90),None)
        cohorts.append({"id":p["id"],"name":p["name"],"year":year,"pick":p["overall_pick"],
            "potential":p["potential"],"ability":p["current_ability"],
            "realization":prospect_development_realization(p,seed),
            "first_observed_rating":values[0] if values else None,"sampled_peak":max(values) if values else None,
            "rotation_seasons":sorted(rotations[p["id"]]),"still_rostered":bool(end.get("rostered")),
            "retired":p["id"] in retired,"league_exit":p["id"] in exited,
            "last_observed_date":observations[-1][0] if observations else None,
            "last_mpg":end.get("mpg"),"last_projected_minutes":end.get("minutes"),
            "last_salary_millions":end.get("salary_millions",[]),
            "first_90_date":star[0] if star else None,"first_90_age":star[1]["age"] if star else None})
    mature = [p for p in cohorts if p["year"]<=2030]
    successful_high = [p for p in mature if p["potential"]>=80 and p["realization"]>=1]
    return {"annual_age_and_pool":annual,"cohorts":cohorts,
        "mature_successful_high_potential":{"count":len(successful_high),
            "ever_rotation":sum(bool(p["rotation_seasons"]) for p in successful_high),
            "sampled_peak_90_plus":sum((p["sampled_peak"] or 0)>=90 for p in successful_high),
            "still_rostered":sum(p["still_rostered"] for p in successful_high),
            "below_85_examples":[p for p in successful_high if (p["sampled_peak"] or 0)<85]},
        "all_generated_record_count":len(cohorts),"unobserved_generated_ids":[p["id"] for p in cohorts if p["sampled_peak"] is None],
        "generated_retired":sum(p["retired"] for p in cohorts),"generated_exits":sum(p["league_exit"] for p in cohorts),
        "legacy_inactive_exit_overlap":len(inactive & exited)}


def compare(control, tuned):
    first,last = control["annual"][0],control["annual"][-1]
    tfirst,tlast = tuned["annual"][0],tuned["annual"][-1]
    assert first == tfirst, "Paired first preseason populations differ"
    return {"date":last["date"],"starting_90_plus":first["fixed24_display_at_least"]["90"],
        "control_90_plus":last["fixed24_display_at_least"]["90"],"tuned_90_plus":tlast["fixed24_display_at_least"]["90"],
        "control_generated_90_plus":last["generated_90_plus"],"tuned_generated_90_plus":tlast["generated_90_plus"],
        "control_rating_distribution":last["fixed24_display"],"tuned_rating_distribution":tlast["fixed24_display"],
        "control_floor_p10_gain":round(last["fixed24_display"]["p10"]-first["fixed24_display"]["p10"],3),
        "tuned_floor_p10_gain":round(tlast["fixed24_display"]["p10"]-tfirst["fixed24_display"]["p10"],3),
        "tuned_minus_control_mean":round(tlast["fixed24_display"]["mean"]-last["fixed24_display"]["mean"],3),
        "tuned_minus_control_p10":round(tlast["fixed24_display"]["p10"]-last["fixed24_display"]["p10"],3),
        "control_departure_share_of_mean_rise":round(control["floor_accounting_same_october_dates"]["departure_composition_component"]/control["floor_accounting_same_october_dates"]["mean_change"],4),
        "tuned_departure_share_of_mean_rise":round(tuned["floor_accounting_same_october_dates"]["departure_composition_component"]/tuned["floor_accounting_same_october_dates"]["mean_change"],4)}


def main(args):
    status = json.loads((args.batch/"status.json").read_text())
    manifest = json.loads((args.batch/"manifest.json").read_text())
    assert status["status"] == "completed"
    if args.output.exists():
        raise FileExistsError("Review already exists; preserve evidence")
    result = {"scope":"Read-only review of two paired seeds. Combined learning and rare-upside/scouting changes versus their pre-tuning settings, all other frozen fixes and V5 starting data identical. AI decisions may diverge downstream. Only two league-level pairs: no precise population-rate or statistical-significance claims. Ratings use fixed-24-minute presentation OVR; first observed rookie ratings can already include development and are not exact draft-entry values.",
              "source":str(args.batch),"batch_status":status,"manifest":manifest,"arms":{},"pairs":{}}
    for arm in manifest["arms"]:
        runtime = args.batch/arm/"runtime"
        integrity = verify_runtime(runtime,manifest,arm)
        out = runtime/"output/balance"
        result["arms"][arm] = {"integrity":integrity,"careers":{}}
        for seed in manifest["seeds"]:
            run = career(out,seed,status["jobs"][f"{arm}:{seed}"])
            assert run["complete_seasons"] == manifest["seasons"]
            v = run["validation"]
            assert len(v["archived_seasons"]) == 8 and all(s["teams"]==30 and s["games"]==1230 and s["all_82_games"] for s in v["archived_seasons"])
            assert v["drafted_players"] == v["unique_drafted_players"] and v["draft_slots_match_saved_orders"]
            assert not v["missing_signed_rookie_summer_records"] and not v["repeated_observation_development_keys"]
            assert v["retirement_ids_unique"] and v["retirement_count_matches_census"]
            run["detail"] = detail(out,seed)
            assert not run["detail"]["unobserved_generated_ids"]
            result["arms"][arm]["careers"][str(seed)] = run
            print(arm,seed,"validated",flush=True)
    for seed in manifest["seeds"]:
        result["pairs"][str(seed)] = compare(result["arms"]["control"]["careers"][str(seed)],result["arms"]["tuned"]["careers"][str(seed)])
    result["verified_seasons"] = sum(c["complete_seasons"] for arm in result["arms"].values() for c in arm["careers"].values())
    result["verified_regular_league_games"] = result["verified_seasons"]*1230
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"verified_seasons":result["verified_seasons"],"pairs":result["pairs"]}),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch",type=Path,default=DEFAULT_BATCH)
    parser.add_argument("--output",type=Path,default=ROOT/"output/paired-balance-review-2026-10-26/review.json")
    main(parser.parse_args())
