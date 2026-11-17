"""Measure a versioned roster candidate using isolated saves and fixed models."""
import argparse
from collections import defaultdict
from copy import deepcopy
import gc
import gzip
import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"output/roster-alignment-2026-10-23"
sys.path.insert(0,str(ROOT/"scripts"))
from league_health_audit import census, career_action, regular_complete, add_probe_staff
from ten_season_soak import SoakRunner, distribution
from verify_simulation_consistency import business_state, digest, differences
from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.health import advance_development
from nba_gm_data.history_store import hydrate_save_history, load_history_records
from nba_gm_data.ingest import build_universe
from nba_gm_data.roster_alignment import STARTING_DATA_VERSION
from nba_gm_data.save import (apply_development_events_to_traits, canonical_with_save, load_save,
                              player_display_attribute_summary, presentation_rating_value,
                              set_save_date_phase, write_save)
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.schema import to_plain
from nba_gm_data.storage import write_outputs, load_universe_json


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")


def frozen():
    return {name:sha(ROOT/"src/nba_gm_data"/name) for name in
            ("health.py","draft.py","save.py","pick_presentation.py","roster_alignment.py","ingest.py")}


def protection():
    return {str(p):sha(p) for p in (ROOT/"saves").rglob("*")
            if p.is_file() and p.suffix in {".json",".sqlite3",".sqlite"}}


def quality(snapshot, membership=None):
    rows = [p for p in snapshot["players"] if p["id"] in membership] if membership is not None else [p for p in snapshot["players"] if p["rostered"]]
    grouped = defaultdict(list)
    for p in rows:
        grouped[str(p.get("draft_year"))].append(presentation_rating_value(p["fixed24_engine"]))
    values = [presentation_rating_value(p["fixed24_engine"]) for p in rows]
    return {"overall":distribution(values),"below70":sum(v<70 for v in values),"90_plus":sum(v>=90 for v in values),
            "by_draft_year":{year:distribution(v) for year,v in sorted(grouped.items())},
            "health_missing":snapshot["rostered"]["health_profile_missing"]}


def survey(args):
    OUT.mkdir(parents=True,exist_ok=True)
    protected, fingerprints = protection(),frozen()
    before_path = ROOT/"data/canonical/baselines/2026-10-20-rookies-v1.json.gz"
    archive_hash = sha(before_path)
    with gzip.open(before_path,"rt") as handle:
        before = json.load(handle)
    universe = build_universe(ROOT)
    after = to_plain(universe)
    paths = write_outputs(universe,OUT/"candidate")
    snapshots,save_paths = {},{}
    for label,canonical in (("before",before),("after",after)):
        directory = OUT/"survey"/label
        directory.mkdir(parents=True,exist_ok=True)
        if list(directory.glob("*.json")):
            raise FileExistsError("Use a fresh output directory; survey saves are never overwritten")
        result = dispatch_app_action("create_save",{"team":"GSW","seed":17,"save_name":"alignment"},
                                     root=ROOT,save_dir=directory,canonical=deepcopy(canonical))
        path = result["save_path"]
        saved = load_save(path)
        snap = census(canonical_with_save(deepcopy(canonical),saved),saved)
        write(OUT/f"census-{label}.json",snap)
        snapshots[label],save_paths[label] = snap,path
    membership = {p["id"] for p in snapshots["before"]["players"] if p["rostered"]}
    controlled = []
    recent = {p["id"] for p in before["players"] if p["id"] in membership and 2022<=int(p.get("draft_year") or 0)<=2025}
    for seed in (17,29):
        for label,canonical in (("before",before),("after",after)):
            context = {"players":[{**p,"minutes_projection":24} for p in canonical["players"] if p["id"] in recent],
                       "traits":[dict(t) for t in canonical["traits"] if t["player_id"] in recent],"_allow_internal_caches":True}
            initial_ages = {p["id"]:p["age"] for p in context["players"]}
            add_probe_staff(context,60)
            for month in range(61):
                for p in context["players"]:
                    p["age"] = initial_ages[p["id"]]+month//12
                if month in (0,12,36,60):
                    grades = [player_display_attribute_summary(context,p["id"])["overall"] for p in context["players"]]
                    controlled.append({"seed":seed,"variant":label,"months":month,"ratings":distribution(grades),
                                       "90_plus":sum(v>=90 for v in grades),"95_plus":sum(v>=95 for v in grades)})
                if month<60:
                    year,m = divmod(2026*12+7+month,12)
                    events = advance_development(context,f"{year}-{m+1:02}",seed=seed)
                    apply_development_events_to_traits(context,events["events"])
    # Replay one old-version week through both canonical entry points.
    old = load_save(save_paths["before"])
    set_save_date_phase(old,"2026-11-14")
    write_save(save_paths["before"],old)
    export = create_export(save_paths["before"])
    states = {}
    for label,canonical in (("before",before),("after",after)):
        path = OUT/"replay"/label/"career.json"
        path.parent.mkdir(parents=True,exist_ok=True)
        restore_export(path,export)
        dispatch_app_action("advance_save",{"save_path":str(path),"days":7,"seed":17},
                            root=ROOT,save_dir=path.parent,canonical=deepcopy(canonical))
        saved = hydrate_save_history(path,load_save(path))
        assert saved["state"]["current_date"] == "2026-11-21"
        states[label] = business_state(saved)
    diffs = differences(states["before"],states["after"])
    assert not diffs,diffs
    assert protection()==protected and frozen()==fingerprints and sha(before_path)==archive_hash
    report = {"status":"passed","version":STARTING_DATA_VERSION,"source_hashes":fingerprints,
              "protected":protected,"playable_hashes_unchanged":True,"old_archive_unchanged":True,
              "fresh_rosters":{k:quality(s) for k,s in snapshots.items()},
              "same_initial_membership":{k:quality(s,membership) for k,s in snapshots.items()},
              "controlled_recent_players":{"scope":"Same 152 starting-roster identities, healthy 24 MPG and neutral staff. No games, exits or ordinary injuries: not an outcome-rate forecast.","checkpoints":controlled},
              "old_save_week_parity":{"equal":True,"before":digest(states["before"]),"after":digest(states["after"]),"diffs":diffs},
              "alignment_report":universe.meta["roster_alignment_report"],
              "candidate":str(paths["json"])}
    report["candidate_sha256"] = sha(paths["json"])
    write(OUT/"survey.json",report)
    print(json.dumps({"status":"passed","fresh_rosters":report["fresh_rosters"],
                      "same_initial_membership":report["same_initial_membership"],
                      "controlled_recent_players":report["controlled_recent_players"],
                      "old_save_week_parity":report["old_save_week_parity"]},indent=2),flush=True)
    if args.publish:
        publish()


def publish():
    report = json.loads((OUT/"survey.json").read_text())
    assert report["status"]=="passed" and report["source_hashes"]==frozen()
    candidate_hash = sha(report["candidate"])
    if report.get("candidate_sha256"):
        assert candidate_hash==report["candidate_sha256"]
    assert protection()==report["protected"]
    universe = build_universe(ROOT)
    candidate = load_universe_json(report["candidate"])
    assert to_plain(universe)==candidate,"Candidate changed since verification"
    report["candidate_sha256"] = candidate_hash
    write(OUT/"survey.json",report)
    archive_candidate(candidate)
    write_outputs(universe,ROOT/"data/canonical")
    print(f"Published {STARTING_DATA_VERSION}",flush=True)


def archive_candidate(candidate):
    target = ROOT/"data/canonical/baselines"/f"{STARTING_DATA_VERSION}.json.gz"
    payload = json.dumps(candidate,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    if target.exists():
        with gzip.open(target,"rt") as handle:
            assert json.load(handle)==candidate,"Never overwrite a different published baseline"
    else:
        temporary = target.with_suffix(".gz.tmp")
        with temporary.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw,mode="wb",filename="",mtime=0) as handle:
                handle.write(payload)
        os.replace(temporary,target)


def career(args):
    directory = OUT/f"career-{args.seed}"
    runner = SoakRunner(argparse.Namespace(root=str(ROOT),output_dir=str(directory),seed=args.seed,team="GSW"))
    runner.canonical = load_universe_json(OUT/"candidate/universe_2026_27_offseason.json")
    runner.canonical.update(_allow_internal_caches=True,_baseline_directory=str(ROOT/"data/canonical/baselines"))
    manifest = directory/"run.json"
    fingerprints = frozen()
    if manifest.exists():
        if not args.resume:
            raise FileExistsError("Resume explicitly; careers are never overwritten")
        report = json.loads(manifest.read_text())
        assert report["source_hashes"]==fingerprints and report["seed"]==args.seed
        runner.payload["save_path"] = report["save_path"]
    else:
        result = runner.action("create_save",team="GSW",seed=args.seed,save_name="roster_alignment")
        runner.payload["save_path"] = result["save_path"]
        report = {"status":"running","seed":args.seed,"source_hashes":fingerprints,
                  "save_path":result["save_path"],"protected":protection(),"actions":[],"snapshots":[]}
    initial_season = int(runner.load()["meta"]["season"][:4])
    started = time.monotonic()
    try:
        for _ in range(150):
            runner.resolve_user_staff_retention()
            runner.resolve_user_roster_cutdown()
            saved = runner.load()
            season = int(saved["meta"]["season"][:4])
            if not report["snapshots"] or report["snapshots"][-1]["season"]!=saved["meta"]["season"]:
                for history in saved.get("season_history",[]):
                    regular_complete({"team_records":history["team_records"]})
                snap = census(canonical_with_save(runner.canonical,saved),saved)
                assert snap["rostered"]["health_profile_missing"]==0
                write(directory/f"census-{snap['date']}.json",snap)
                summary = {"date":snap["date"],"season":saved["meta"]["season"],**quality(snap)}
                report["snapshots"].append(summary)
                print(json.dumps({"seed":args.seed,"census":{k:summary[k] for k in ("date","overall","90_plus","below70")}}),flush=True)
            if season>=2026+args.seasons:
                events = {r["id"]:r for r in load_history_records(runner.payload["save_path"],saved,"development_events")}
                events.update({r["id"]:r for r in saved.get("development_events",[])})
                assert len(events)==len({(r["player_id"],r["month"]) for r in events.values()})
                report.update(status="passed",endpoint=saved["state"]["current_date"],
                              completed_seasons=len(saved["season_history"]),development_months=len({r["month"] for r in events.values()}))
                break
            if season>=initial_season+1:
                break
            action,payload = career_action(saved,31,"GSW")
            tick = time.monotonic()
            runner.action(action,save_path=runner.payload["save_path"],seed=args.seed,**payload)
            after = runner.load()
            row = {"action":action,"from":saved["state"]["current_date"],"to":after["state"]["current_date"],
                   "seconds":round(time.monotonic()-tick,3)}
            report["actions"].append(row)
            write(manifest,report)
            print(json.dumps({"seed":args.seed,**row}),flush=True)
        else:
            raise RuntimeError("Career action budget exhausted")
        assert frozen()==fingerprints and all(sha(p)==h for p,h in report["protected"].items())
        report["playable_hashes_unchanged"] = True
    except Exception as exc:
        report.update(status="needs_attention",error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["segment_seconds"] = round(time.monotonic()-started,3)
        write(manifest,report)
    sys.stdout.flush()
    os._exit(0)


def soak(args):
    for _ in range(args.seasons+2):
        manifest = OUT/f"career-{args.seed}/run.json"
        if manifest.exists() and json.loads(manifest.read_text())["status"]=="passed":
            return
        subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"career","--seed",str(args.seed),
                        "--seasons",str(args.seasons),"--resume"],check=True)
    raise RuntimeError("Segment budget exhausted")


def validate(args):
    survey_report = json.loads((OUT/"survey.json").read_text())
    assert protection()==survey_report["protected"]
    assert sha(OUT/"candidate/universe_2026_27_offseason.json")==survey_report["candidate_sha256"]
    result = {}
    for seed in (17,29):
        directory = OUT/f"career-{seed}"
        report = json.loads((directory/"run.json").read_text())
        assert report["status"]=="passed" and report["source_hashes"]==frozen()
        saved = load_save(report["save_path"])
        endpoint = f"{2026+args.seasons}-10-01"
        assert saved["state"]["current_date"]==endpoint and len(saved["season_history"])==args.seasons
        for season in saved["season_history"]:
            regular_complete({"team_records":season["team_records"]})
        classes = defaultdict(list)
        for row in saved["incoming_rookies"]:
            classes[str(row["draft_year"])].append(row)
        assert set(classes)=={str(y) for y in range(2027,2027+args.seasons)}
        for rows in classes.values():
            assert len(rows)==60 and len({r["player_id"] for r in rows})==60
            assert {int(r["overall_pick"]) for r in rows}==set(range(1,61))
        events = {r["id"]:r for r in load_history_records(report["save_path"],saved,"development_events")}
        for row in saved.get("development_events",[]):
            assert row["id"] not in events or events[row["id"]]==row
            events[row["id"]] = row
        assert len(events)==len({(r["player_id"],r["month"]) for r in events.values()})
        expected = set()
        for absolute in range(2026*12+7,(2026+args.seasons)*12+10):
            year,month = divmod(absolute,12)
            expected.add(f"{year}-{month+1:02}")
        assert {r["month"] for r in events.values()}==expected
        retired = set(saved.get("retired_player_ids",[]))-set(saved.get("league_exit_player_ids",[]))
        retirements = [r for report in saved.get("retirement_reports",[]) for r in report["retirements"]]
        assert len(retirements)==len(retired) and {r["player_id"] for r in retirements}==retired
        for path in directory.glob("census-*.json"):
            snap = json.loads(path.read_text())
            assert len(snap["roster_counts_by_team"])==30 and min(snap["roster_counts_by_team"].values())>=14
            assert snap["rostered"]["health_profile_missing"]==0
        result[str(seed)] = {"status":"passed","endpoint":endpoint,"complete_seasons":args.seasons,
                             "regular_games":1230*args.seasons,"draft_selections":60*args.seasons,
                             "development_months":len(expected),"actual_retirements":len(retired),
                             "playable_hashes_unchanged":True,"snapshots":report["snapshots"]}
    write(OUT/"career-validation.json",result)
    print(json.dumps({seed:{k:v for k,v in row.items() if k!="snapshots"} for seed,row in result.items()},indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("survey","career","publish","soak","validate"))
    parser.add_argument("--publish",action="store_true")
    parser.add_argument("--seed",type=int,default=17)
    parser.add_argument("--seasons",type=int,default=2)
    parser.add_argument("--resume",action="store_true")
    args = parser.parse_args()
    gc.disable()
    if args.mode=="publish":
        publish()
    elif args.mode=="survey":
        survey(args)
    elif args.mode=="soak":
        soak(args)
    elif args.mode=="validate":
        validate(args)
    else:
        career(args)


if __name__=="__main__":
    main()
