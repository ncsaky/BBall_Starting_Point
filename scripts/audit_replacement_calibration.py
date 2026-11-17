"""Compare frozen imported skills with actual saved rookie entry profiles."""
import argparse
import ast
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics

from nba_gm_data.save import display_minutes_projection, player_attribute_summary, player_display_attribute_summary
from nba_gm_data.sim import player_impact_score
from ten_season_soak import distribution

ROOT = Path(__file__).resolve().parents[1]
BATCH = Path.home()/".cache/nba-gm-audits/paired-balance-2026-10-26"
COMPOSITES = ("shooting","creation","defense","athleticism","iq","rebounding")
PROTECTED = {"manual_calibration","roster_alignment","imported_rookie_prior","league_trait_rating_calibration"}


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def read(path):
    with gzip.open(path,"rt") as handle:
        return json.load(handle)


def stamina_diagnostic(trait):
    """Diagnostic only: isolate a role bonus being averaged as an observation."""
    components = trait.get("components") or {}
    pieces = components.get("components")
    if trait.get("trait_key") != "stamina_cardio" or PROTECTED & components.keys():
        return None
    if not isinstance(pieces,list) or len(pieces)!=3:
        return None
    numbers = [p for p in pieces if p is not None]
    workload = [p for p in pieces[:2] if p is not None]
    if not workload or pieces[2] is None or not all(isinstance(p,(int,float)) and math.isfinite(p) for p in numbers):
        return None
    if abs(float(trait["value"])-statistics.mean(numbers))>.02:
        return None
    return min(100,max(0,statistics.mean(workload)+pieces[2]))


def profile_rows(context):
    # Use identical workload and no health state. Never change the caller's
    # player minutes or persistent entry profiles.
    neutral = {"meta":dict(context["meta"]),"players":[{**p,"minutes_projection":24} for p in context["players"]],
               "traits":context["traits"],"_allow_internal_caches":True}
    traits = defaultdict(dict)
    records = defaultdict(list)
    for trait in context["traits"]:
        traits[trait["player_id"]][trait["trait_key"]] = float(trait["value"])
        records[trait["player_id"]].append(trait)
    rows = []
    for player in context["players"]:
        pid = player["id"]
        values = traits[pid]
        raw = player_attribute_summary(neutral,pid)
        display = player_display_attribute_summary(neutral,pid)
        rows.append({"id":pid,"name":player["name"],"position":str(player.get("position") or "").upper().split("/")[0],
            "age":player.get("age"),"team_id":player.get("team_id"),
            "source_minutes":display_minutes_projection(player),"prior_minutes":player.get("prior_minutes"),
            "draft_year":player.get("draft_year"),"pick":player.get("overall_pick",player.get("draft_position")),
            "overall":display["overall"],"engine_overall":raw["overall"],
            "impact":player_impact_score(lambda k:values.get(k,50),player.get("position"),role_aware=True),
            "raw_composites":{k:raw[k] for k in COMPOSITES},"raw_traits":values,
            "low_trait_count":sum(v<25 for v in values.values()),
            "manual":any("manual_calibration" in (t.get("components") or {}) for t in records[pid]),
            "league_prior":any("league_trait_rating_calibration" in (t.get("components") or {}) for t in records[pid]),
            "fringe_cap":any((t.get("components") or {}).get("league_trait_rating_calibration",{}).get("fringe_role_cap") for t in records[pid]),
            "aligned":any("roster_alignment" in (t.get("components") or {}) for t in records[pid])})
    return rows


def summarize(rows):
    rows = list(rows)
    return {"count":len(rows),"overall":distribution(p["overall"] for p in rows),
        "impact":distribution(p["impact"] for p in rows),"age":distribution(p["age"] for p in rows if p.get("age") is not None),
        "raw_composite_means":{k:round(statistics.mean(p["raw_composites"][k] for p in rows),3) if rows else None for k in COMPOSITES},
        "raw_stamina":distribution(p["raw_traits"].get("stamina_cardio",50) for p in rows),
        "with_severe_hole":sum(p["low_trait_count"]>0 for p in rows),
        "positions":dict(Counter(p["position"] for p in rows)),
        "provenance":{k:sum(bool(p[k]) for p in rows) for k in ("manual","league_prior","fringe_cap","aligned")}}


def position_standardized(reference, comparison):
    groups = defaultdict(list)
    for row in comparison:
        groups[row["position"]].append(row)
    matched = [r for r in reference if groups[r["position"]]]
    if not matched:
        return {"reference_count":0}
    means = {pos:statistics.mean(r["overall"] for r in rows) for pos,rows in groups.items()}
    return {"reference_count":len(matched),"unmatched_reference_count":len(reference)-len(matched),
        "reference_mean":round(statistics.mean(r["overall"] for r in matched),3),
        "comparison_mean_at_reference_position_mix":round(statistics.mean(means[r["position"]] for r in matched),3),
        "limit":"Descriptive position standardization only; not age, role, skill or NBA-outcome matching."}


def verify_helpers(runtime):
    for name,functions in (("save",("player_attribute_summary","player_display_attribute_summary","presentation_rating_value","display_minutes_projection")),
                           ("sim",("player_impact_score",)),("talent",("role_weights","role_skill_value"))):
        a = ast.parse((runtime/f"src/nba_gm_data/{name}.py").read_text())
        b = ast.parse((ROOT/f"src/nba_gm_data/{name}.py").read_text())
        for function in functions:
            left = next(n for n in a.body if isinstance(n,ast.FunctionDef) and n.name==function)
            right = next(n for n in b.body if isinstance(n,ast.FunctionDef) and n.name==function)
            assert ast.dump(left)==ast.dump(right),f"Historical comparison helper changed: {function}"


def main(args):
    if args.output.exists():
        raise FileExistsError("Refuse to overwrite audit evidence")
    result = {"scope":"Read-only saved-career input calibration audit. Imported July-2026 frozen V5 traits vs immutable saved rookie entry traits, not developed endpoint survivors. All profiles evaluated at 24 minutes with the same role-aware formulas and no health context. No new simulations, player boosts, save migration, or opportunity intervention.",
              "cohort_warning":"Two allocation histories, with a shared stored 2027 class; do not treat every selection as an independent prospect. Imported positions/ages/roles differ from incoming classes. The bottom-10% group is selected by rating and cannot alone prove an importer error.",
              "source":str(args.batch),"cases":{}}
    all_sources = {}
    for arm in ("control","tuned"):
        runtime = args.batch/arm/"runtime"
        verify_helpers(runtime)
        out = runtime/"output/balance"
        canonical = read(out/"canonical.json.gz")
        all_sources[str(out/"canonical.json.gz")] = sha(out/"canonical.json.gz")
        for seed in (29,913):
            directory = out/f"career-{seed}"
            run = json.loads((directory/"run.json").read_text())
            save_path = Path(run["save_path"])
            assert save_path.resolve().is_relative_to(out)
            all_sources[str(save_path)] = sha(save_path)
            saved = json.loads(save_path.read_text())
            start = read(next((directory/"observations").glob("*2026-10-01.json.gz")))
            end = read(directory/"latest-observation.json.gz")
            roster_ids = {p["id"] for p in start["players"] if p["rostered"]}
            preseason_teams = {p["id"]:p["team_id"] for p in start["players"] if p["rostered"]}
            baseline = {"meta":canonical["meta"],"players":[{**p,"team_id":preseason_teams[p["id"]]}
                        for p in canonical["players"] if p["id"] in roster_ids],"traits":canonical["traits"]}
            imported = profile_rows(baseline)
            generated = profile_rows({"meta":canonical["meta"],"players":saved["generated_players"],"traits":saved["generated_traits"]})
            # Entry values are also persisted in the capacity record. This
            # detects accidentally analyzing developed values as draft inputs.
            assert all(abs(t["value"]-t["components"]["career_capacity"]["entry_value"])<=.011 for t in saved["generated_traits"])
            groups = {"all_starting_roster":imported,"bottom_10pct":sorted(imported,key=lambda p:p["overall"])[:math.ceil(len(imported)*.1)],
                "projected_8_or_less":[p for p in imported if p["source_minutes"]<=8],
                "projected_8_to_16":[p for p in imported if 8<p["source_minutes"]<=16],
                "age_20_to_23":[p for p in imported if 20<=float(p.get("age") or 0)<=23],
                "prior_900plus_minutes":[p for p in imported if float(p.get("prior_minutes") or 0)>=900]}
            incoming = {"all_entries":generated,"picks_15_30":[p for p in generated if 15<=int(p["pick"])<=30],
                "picks_31plus":[p for p in generated if int(p["pick"])>=31],
                "age_20_to_23":[p for p in generated if 20<=float(p.get("age") or 0)<=23]}
            depth_ids = set()
            teams = defaultdict(list)
            for row in imported:
                teams[row["team_id"]].append(row)
            for team in teams.values():
                depth_ids.update(p["id"] for p in sorted(team,key=lambda p:(p["source_minutes"],p["id"]))[:5])
            groups["bottom5_per_team_by_projected_minutes"] = [p for p in imported if p["id"] in depth_ids]
            scenario = {"meta":canonical["meta"],"players":baseline["players"],"traits":deepcopy(canonical["traits"])}
            changed = {}
            for trait in scenario["traits"]:
                candidate = stamina_diagnostic(trait)
                if trait["player_id"] in roster_ids and candidate is not None and abs(candidate-trait["value"])>.01:
                    changed[trait["player_id"]] = {"before":trait["value"],"after":candidate}
                    trait["value"] = candidate
            diagnostic = {r["id"]:r for r in profile_rows(scenario)}
            original = {r["id"]:r for r in imported}
            for pid,row in changed.items():
                row.update(name=original[pid]["name"],overall_before=original[pid]["overall"],overall_after=diagnostic[pid]["overall"])
            endpoint = {p["id"]:p for p in end["players"] if p["rostered"]}
            for row in imported:
                row["rostered_at_endpoint"] = row["id"] in endpoint
            case = {"baseline_groups":{k:summarize(v) for k,v in groups.items()},"incoming_groups":{k:summarize(v) for k,v in incoming.items()},
                "by_position":{pos:{"bottom_starting":summarize(p for p in groups["bottom_10pct"] if p["position"]==pos),
                    "incoming_31plus":summarize(p for p in incoming["picks_31plus"] if p["position"]==pos)} for pos in ("PG","SG","SF","PF","C")},
                "position_standardized":{k:position_standardized(rows,incoming["picks_31plus"]) for k,rows in groups.items()},
                "same_age_and_position":position_standardized(groups["age_20_to_23"],incoming["age_20_to_23"]),
                "stamina_arithmetic_scenario":{"limit":"Not a published correction. Only untouched direct-inference stamina values matching their components are recomputed as workload mean plus role bonus. Calibrated, aligned and manually reviewed traits excluded. Physiological validity and downstream fatigue effects are untested.",
                    "affected":len(changed),"overall_gain":distribution(v["overall_after"]-v["overall_before"] for v in changed.values()),
                    "original_bottom_group_after":summarize(diagnostic[p["id"]] for p in groups["bottom_10pct"]),"players":changed},
                "bottom_players":groups["bottom_10pct"],"entry_rows":generated}
            result["cases"][f"{arm}:{seed}"] = case
            print(arm,seed,"bottom",case["baseline_groups"]["bottom_10pct"]["overall"]["mean"],
                  "deep bench",case["baseline_groups"]["bottom5_per_team_by_projected_minutes"]["overall"]["mean"],
                  "second round",case["incoming_groups"]["picks_31plus"]["overall"]["mean"],flush=True)
    assert all(sha(path)==value for path,value in all_sources.items()),"Source audit files changed during read-only review"
    result.update(source_hashes=all_sources,source_files_unchanged=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(f"Saved {args.output}; no gameplay inputs changed.",flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch",type=Path,default=BATCH)
    parser.add_argument("--output",type=Path,default=ROOT/"output/replacement-calibration-2026-10-26/audit.json")
    main(parser.parse_args())
