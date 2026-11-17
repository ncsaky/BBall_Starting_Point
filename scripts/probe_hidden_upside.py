"""Paired future-class tail screen; not a league equilibrium simulation."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from nba_gm_data import draft, health
from nba_gm_data.save import apply_development_events_to_traits, player_display_attribute_summary
from league_health_audit import converted_class
from probe_league_health_tuning import band, write

ROOT = Path(__file__).resolve().parents[1]
TAIL = draft.generated_prospect_upside


def previous_tail(potential, rank, quality, year, seed, talent_model=False):
    # The legacy branch preserves the exact pre-calibration probability/draws.
    return TAIL(potential, rank, quality, year, seed, False)


def trajectory(context, ids, year, seed, minutes, reload_midway=False):
    probe = {"meta":dict(context["meta"]), "players":[deepcopy(p) for p in context["players"] if p["id"] in ids],
             "traits":[deepcopy(t) for t in context["traits"] if t["player_id"] in ids], "_allow_internal_caches":True}
    ages = {p["id"]:p["age"] for p in probe["players"]}
    rows = {p["id"]:{"peak":-1, "first_90_month":None, "checkpoints":{}} for p in probe["players"]}
    for month in range(121):
        for p in probe["players"]:
            p["age"] = ages[p["id"]] + month//12
            p["rotation_priority"] = "fringe" if minutes < 16 else "core_rotation"
            p["minutes_projection"] = 24
            score = player_display_attribute_summary(probe,p["id"])["overall"]
            p["minutes_projection"] = minutes
            row = rows[p["id"]]
            row["peak"] = max(score,row["peak"])
            if score >= 90 and row["first_90_month"] is None:
                row["first_90_month"] = month
            if month%12 == 0:
                row["checkpoints"][str(month)] = score
        if month == 120:
            break
        stamp = year*12 + 6 + month
        y,m = divmod(stamp,12)
        events = health.advance_development(probe,f"{y}-{m+1:02}",seed)
        apply_development_events_to_traits(probe,events["events"])
        if reload_midway and month == 59:
            # Runtime indexes contain object aliases; like canonical_with_save,
            # rebuild them from persistent data rather than serializing copies.
            probe = json.loads(json.dumps({k:v for k,v in probe.items() if not k.startswith("_")}))
            probe["_allow_internal_caches"] = True
    return rows


def main(args):
    path = args.output / f"{args.label}-{args.minutes:g}mpg.json"
    if path.exists():
        raise FileExistsError("Do not overwrite paired probe evidence")
    started = time.monotonic()
    result = {"status":"running", "scope":"Future generation counterfactual; NOT observed league careers. All entry players are compared. Only altered upside profiles and one unchanged late control per class are developed for 120 healthy months with neutral staff. Bands refer to consensus rank, NOT an AI-selected draft slot; all are converted on one fixed team. Not a population peak distribution or an empirical NBA star-rate estimate.",
              "year":args.year,"seed_start":args.seed_start,"classes":args.classes,"minutes":args.minutes,
              "source_sha256":{name:hashlib.sha256((ROOT/f"src/nba_gm_data/{name}.py").read_bytes()).hexdigest()
                               for name in ("draft","health","talent")},
              "generation_counts":{},"rows":[],"entry_players_compared":0,"unchanged_profiles":0}
    counts = Counter()
    for seed in range(args.seed_start,args.seed_start+args.classes):
        with patch.object(draft,"generated_prospect_upside",previous_tail):
            old_class,before = converted_class(args.year,seed,{"id":"team_gsw","abbrev":"GSW"},talent_model=True)
        new_class,after = converted_class(args.year,seed,{"id":"team_gsw","abbrev":"GSW"},talent_model=True)
        assert old_class["draft_classes"] == new_class["draft_classes"]
        assert old_class["draft_prospect_traits"] == new_class["draft_prospect_traits"]
        for left,right in zip(before["traits"],after["traits"],strict=True):
            assert left["value"] == right["value"]
            assert left["components"]["career_capacity"]["aptitude"] == right["components"]["career_capacity"]["aptitude"]
        changed, controls, info = set(),set(),{}
        for a,b,left,right in zip(old_class["draft_prospects"],new_class["draft_prospects"],before["players"],after["players"],strict=True):
            excluded = {"potential","ceiling","rookie_contract_value","scouting_prior"}
            assert {k:v for k,v in a.items() if k not in excluded} == {k:v for k,v in b.items() if k not in excluded}
            for p in (left,right):
                p["minutes_projection"] = 24
            entry = player_display_attribute_summary(before,left["id"])["overall"]
            assert entry == player_display_attribute_summary(after,right["id"])["overall"]
            group = band(b["rank"])
            counts[f"{group}:players"] += 1
            for label,p in (("before",a),("after",b)):
                counts[f"{group}:{label}_potential80"] += p["potential"] >= 80
            pid = right["id"]
            info[pid] = {"id":pid,"name":right["name"],"pick":b["rank"],"seed":seed,"year":args.year,
                         "entry":entry,"entry_age":right["age"],"potential_before":a["potential"],
                         "potential_after":b["potential"],"realization":health.prospect_development_realization(right,seed)}
            result["entry_players_compared"] += 1
            if a["potential"] != b["potential"]:
                changed.add(pid)
                counts[f"{group}:altered"] += 1
            else:
                assert left == right
                result["unchanged_profiles"] += 1
                if b["rank"] > 30 and not controls:
                    controls.add(pid)
        # Unaffected stored capacities must match, not just current ratings.
        for a,b in zip(before["traits"],after["traits"],strict=True):
            if b["player_id"] not in changed:
                assert a == b
        ids = changed | controls
        left = trajectory(before,ids,args.year,seed,args.minutes)
        right = trajectory(after,ids,args.year,seed,args.minutes)
        if seed == args.seed_start:
            assert right == trajectory(after,ids,args.year,seed,args.minutes,reload_midway=True)
        for pid in sorted(ids):
            if pid in controls:
                assert left[pid] == right[pid]
            result["rows"].append({**info[pid],"altered":pid in changed,"before":left[pid],"after":right[pid]})
        result["generation_counts"] = dict(sorted(counts.items()))
        if (seed-args.seed_start+1)%10 == 0:
            write(path,result)
            print(f"{args.label}: {seed-args.seed_start+1}/{args.classes} classes checked",flush=True)
    altered = [r for r in result["rows"] if r["altered"]]
    result["altered_outcomes"] = {group:{"count":len(pool),**{
        f"{label}_peak{cut}":sum(r[label]["peak"]>=cut for r in pool)
        for label in ("before","after") for cut in (80,85,90,95)}}
        for group in ("1-3","4-14","15-30","31+")
        for pool in ([r for r in altered if band(r["pick"]) == group],)}
    result.update(status="passed",seconds=round(time.monotonic()-started,2))
    write(path,result)
    print(json.dumps({k:v for k,v in result.items() if k not in {"rows","source_sha256"}}),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classes",type=int,default=100)
    parser.add_argument("--seed-start",type=int,default=100)
    parser.add_argument("--year",type=int,default=2038)
    parser.add_argument("--minutes",type=float,default=24)
    parser.add_argument("--label",default="screen")
    parser.add_argument("--output",type=Path,default=ROOT/"output/hidden-upside-2026-10-26")
    args = parser.parse_args()
    if not 1<=args.classes<=1000 or not 0<=args.minutes<=48 or not 2027<=args.year<=2200:
        parser.error("classes 1..1000, minutes 0..48, year 2027..2200 required")
    main(args)
