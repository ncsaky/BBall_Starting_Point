"""Distinguish consensus rank from real AI selections without simulating seasons."""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from nba_gm_data import draft
from probe_hidden_upside import previous_tail, trajectory
from league_health_audit import converted_class
from nba_gm_data.schema import to_plain
from probe_league_health_tuning import band, write

ROOT = Path(__file__).resolve().parents[1]


def main(args):
    if args.develop_report:
        return develop_report(args.develop_report)
    output = ROOT/f"output/hidden-upside-2026-10-26/{args.label}.json"
    if output.exists():
        raise FileExistsError("Do not overwrite draft-screen evidence")
    baseline = ROOT/"data/canonical/baselines/2026-10-23-talent-v4.json.gz"
    with gzip.open(baseline,"rt") as handle:
        base = json.load(handle)
    result = {"status":"running", "scope":"Real generated-draft ranking, lottery/order, team fit and selection logic on a fixed baseline-team environment, before/after tail only. No played seasons, changing team needs, injuries, survival or actual-career growth. Consensus rank is NOT selection slot.",
              "baseline_sha256":hashlib.sha256(baseline.read_bytes()).hexdigest(),
              "draft_sha256":hashlib.sha256((ROOT/"src/nba_gm_data/draft.py").read_bytes()).hexdigest(),
              "classes_per_group":args.classes,"rows":[],"counts":{}}
    started = time.monotonic()
    counts = Counter()
    for year,start in ((2038,100),(2043,200)):
        for seed in range(start,start+args.classes):
            runs = {}
            for label in ("before","after"):
                canonical = deepcopy(base)
                canonical["meta"]["draft_class_seed"] = seed
                canonical["_allow_internal_caches"] = True
                if label == "before":
                    with patch.object(draft,"generated_prospect_upside",previous_tail):
                        payload = draft.simulate_draft(canonical,str(year),seed=seed)
                else:
                    payload = draft.simulate_draft(canonical,str(year),seed=seed)
                assert payload["selection_count"] == 60
                assert len({s["prospect_id"] for s in payload["selections"]}) == 60
                prospects = {p["id"]:p for p in payload["draft_prospects"]}
                runs[label] = {s["prospect_id"]:{"pick":s["overall_pick"],"team_id":s["team_id"],
                    "potential":prospects[s["prospect_id"]]["potential"],"rank":prospects[s["prospect_id"]]["rank"]}
                    for s in payload["selections"]}
            assert runs["before"].keys() == runs["after"].keys()
            assert all((a["pick"],a["team_id"]) == (runs["after"][pid]["pick"],runs["after"][pid]["team_id"])
                       for pid,a in runs["before"].items())
            for pid,after in runs["after"].items():
                before = runs["before"][pid]
                if after["potential"] == before["potential"]:
                    continue
                result["rows"].append({"year":year,"seed":seed,"prospect_id":pid,"before":before,"after":after})
                counts[f"consensus_{band(after['rank'])}"] += 1
                counts[f"selected_{band(after['pick'])}"] += 1
            result["counts"] = dict(sorted(counts.items()))
            write(output,result)
            print(f"Draft pair {year} seed {seed} complete",flush=True)
    result.update(status="passed",seconds=round(time.monotonic()-started,2))
    write(output,result)
    print(json.dumps({k:v for k,v in result.items() if k!="rows"}),flush=True)


def develop_report(source):
    report = json.loads(source.read_text())
    assert report["status"] == "passed"
    assert report["draft_sha256"] == hashlib.sha256((ROOT/"src/nba_gm_data/draft.py").read_bytes()).hexdigest()
    target = source.with_name(source.stem+"-development.json")
    if target.exists():
        raise FileExistsError("Do not overwrite development evidence")
    result = {"scope":"Paired healthy 24-MPG development of altered profiles using their real AI-selected slots, teams and resulting IDs. No seasons, cuts, finances or injury simulation. Not a population outcome rate.",
              "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
              "health_sha256":hashlib.sha256((ROOT/"src/nba_gm_data/health.py").read_bytes()).hexdigest(),"rows":[]}
    started = time.monotonic()
    for year,seed in sorted({(r["year"],r["seed"]) for r in report["rows"]}):
        entries = [r for r in report["rows"] if r["year"] == year and r["seed"] == seed]
        contexts = {}
        teams = [{"id":tid,"abbrev":tid} for tid in {r["after"]["team_id"] for r in entries}]
        selections = []
        for row in entries:
            assert (row["before"]["pick"],row["before"]["team_id"]) == (row["after"]["pick"],row["after"]["team_id"])
            selections.append({"id":f"probe:{row['prospect_id']}","prospect_id":row["prospect_id"],
                "overall_pick":row["after"]["pick"],"team_id":row["after"]["team_id"],"draft_year":str(year)})
        for label in ("before","after"):
            if label == "before":
                with patch.object(draft,"generated_prospect_upside",previous_tail):
                    generated = to_plain(draft.generate_draft_class_records(str(year),seed,talent_model=True))
            else:
                generated = to_plain(draft.generate_draft_class_records(str(year),seed,talent_model=True))
            generated["selections"] = selections
            _,contexts[label] = converted_class(year,seed,teams[0],drafted=generated,teams=teams,talent_model=True)
        left,right = contexts["before"],contexts["after"]
        ids = {p["id"] for p in right["players"]}
        assert ids == {p["id"] for p in left["players"]}
        before = trajectory(left,ids,year,seed,24)
        after = trajectory(right,ids,year,seed,24)
        assert after == trajectory(right,ids,year,seed,24,reload_midway=True)
        for player in right["players"]:
            result["rows"].append({"id":player["id"],"name":player["name"],"year":year,"seed":seed,
                "pick":player["overall_pick"],"entry_age":player["age"],"before":before[player["id"]],"after":after[player["id"]]})
    result["by_actual_pick"] = {group:{"count":len(pool),**{
        f"{label}_peak{cut}":sum(r[label]["peak"] >= cut for r in pool)
        for label in ("before","after") for cut in (85,90,95)}}
        for group in ("1-3","4-14","15-30","31+") for pool in ([r for r in result["rows"] if band(r["pick"]) == group],)}
    result.update(status="passed",seconds=round(time.monotonic()-started,2))
    write(target,result)
    print(json.dumps({k:v for k,v in result.items() if k!="rows"}),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classes",type=int,default=12)
    parser.add_argument("--label",default="actual-draft-screen")
    parser.add_argument("--develop-report",type=Path)
    args = parser.parse_args()
    if not 1<=args.classes<=100:
        parser.error("classes must be 1..100 per group")
    main(args)
