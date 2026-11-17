"""Fast paired development probes using the actual expensive audit's entry data."""
from collections import defaultdict
from copy import deepcopy
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import time
from types import FunctionType
from unittest.mock import patch

from nba_gm_data import health
from nba_gm_data.save import apply_development_events_to_traits, player_display_attribute_summary, presentation_rating_value
from nba_gm_data.talent import trait_ceiling
from ten_season_soak import distribution

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / ".cache/nba-gm-audits/market-lifecycle-2026-10-25/runtime/output/market-lifecycle-2026-10-25-r2"
OUT = ROOT / "output/league-health-tuning-2026-10-26"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def band(pick):
    return "1-3" if pick <= 3 else "4-14" if pick <= 14 else "15-30" if pick <= 30 else "31+"


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[band(row["pick"])].append(row)
    return {key: {"count": len(pool), "entry": distribution(p["entry"] for p in pool),
        "peak": distribution(p["peak"] for p in pool),
        "peak_gain": distribution(p["peak"] - p["entry"] for p in pool),
        "peak_85_plus": sum(p["peak"] >= 85 for p in pool),
        "peak_90_plus": sum(p["peak"] >= 90 for p in pool),
        "peak_95_plus": sum(p["peak"] >= 95 for p in pool),
        "first_90_month": distribution(p["first_90_month"] for p in pool if p["first_90_month"] is not None)}
        for key, pool in sorted(groups.items())}


def prepare(args):
    path = OUT / f"{args.dataset}.json.gz"
    if path.exists():
        raise FileExistsError("Entry dataset already frozen")
    review = json.loads((SOURCE / "review.json").read_text())
    data = {"scope": f"Actual entry players and traits, with original team-derived IDs and save seeds; {args.first_year}-{args.last_year} cohorts from completed careers. Later entry classes are held-out mechanism tests, not mature observed outcomes. No prospect rerolls.", "cohorts": []}
    for seed in map(int, args.seeds.split(",")):
        run = json.loads((SOURCE / f"career-{seed}/run.json").read_text())
        raw_path = Path(run["save_path"])
        raw = json.loads(raw_path.read_text())
        actual = {p["id"]: p for p in review["careers"][str(seed)]["generated_careers"]}
        for year in range(args.first_year, args.last_year + 1):
            players = [p for p in raw["generated_players"] if int(p["draft_year"]) == year]
            ids = {p["id"] for p in players}
            traits = [t for t in raw["generated_traits"] if t["player_id"] in ids]
            context = {"meta": {"talent_model_version": 2}, "players": deepcopy(players), "traits": deepcopy(traits)}
            for p in context["players"]:
                p["minutes_projection"] = 24
            ceiling_context = deepcopy(context)
            by_id = {p["id"]: p for p in players}
            for t in ceiling_context["traits"]:
                if t["trait_key"] not in health.DEVELOPMENT_TRAITS:
                    continue
                p = by_id[t["player_id"]]
                ceiling = trait_ceiling(p, t["trait_key"], t["components"]["career_capacity"], health.prospect_development_realization(p, seed), seed)
                t["value"] = ceiling
            rows = []
            for p in players:
                rows.append({"id": p["id"], "name": p["name"], "seed": seed, "year": year,
                    "pick": int(p["overall_pick"]), "potential": p["potential"], "ability": p["current_ability"],
                    "entry_age": p["age"], "realization": health.prospect_development_realization(p, seed),
                    "entry": player_display_attribute_summary(context, p["id"])["overall"],
                    "actual_sampled_peak": presentation_rating_value(actual[p["id"]]["sampled_peak_engine"]),
                    "all_developable_traits_at_capacity": player_display_attribute_summary(ceiling_context, p["id"])["overall"]})
            data["cohorts"].append({"seed":seed, "year":year, "players":players, "traits":traits, "rows":rows})
        print(f"Prepared seed {seed}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", compresslevel=3) as handle:
        json.dump(data, handle, separators=(",", ":"))
    rows = [r for cohort in data["cohorts"] for r in cohort["rows"]]
    diagnostic = {"scope": data["scope"], "capacity_warning": "All-traits-at-ceiling is an optimistic mechanical capacity diagnostic, not an attainable forecast or a claim that weaknesses should fill in.", "rows":rows}
    for name, predicate in (("high_potential_successful", lambda p: p["potential"] >= 80 and p["realization"] >= 1),
                            ("late_high_potential_successful", lambda p: p["pick"] >= 15 and p["potential"] >= 75 and p["realization"] >= 1),
                            ("low_realization", lambda p: p["realization"] <= .8)):
        pool = [p for p in rows if predicate(p)]
        diagnostic[name] = {"count":len(pool), "actual_90_plus":sum(p["actual_sampled_peak"] >= 90 for p in pool),
            "capacity_90_plus":sum(p["all_developable_traits_at_capacity"] >= 90 for p in pool),
            "actual_peak":distribution(p["actual_sampled_peak"] for p in pool),
            "capacity":distribution(p["all_developable_traits_at_capacity"] for p in pool)}
        print(name, json.dumps(diagnostic[name]), flush=True)
    write(OUT / f"{args.dataset}-capacity-diagnosis.json", diagnostic)


def run(args):
    target = OUT / f"{args.label}-{args.minutes:g}mpg.json"
    if target.exists():
        raise FileExistsError("Never overwrite paired probe evidence")
    source = OUT / f"{args.dataset}.json.gz"
    with gzip.open(source, "rt") as handle:
        data = json.load(handle)
    result = {"status":"running", "label":args.label, "minutes":args.minutes, "months":args.months,
        "scope":"Controlled healthy career mechanisms, not new league seasons or a causal league forecast. Fixed opportunity, neutral staff, no injuries, cutdowns or retirements. Includes busts and all mature picks, not only survivors.",
        "dataset_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "health_sha256":hashlib.sha256((ROOT / "src/nba_gm_data/health.py").read_bytes()).hexdigest(), "rows":[]}
    if args.reference_health:
        result["reference_health_sha256"] = hashlib.sha256(args.reference_health.read_bytes()).hexdigest()
        result["reference_scope"] = "Exact old monthly function with AST-verified unchanged local helper functions."
    started = time.monotonic()
    for cohort in data["cohorts"]:
        probe = {"meta":{"talent_model_version":2}, "players":deepcopy(cohort["players"]), "traits":deepcopy(cohort["traits"]), "_allow_internal_caches":True}
        rows = deepcopy(cohort["rows"])
        ages = {p["id"]:p["age"] for p in probe["players"]}
        for p in probe["players"]:
            p["minutes_projection"] = args.minutes
            p["rotation_priority"] = "fringe" if args.minutes < 16 else "core_rotation"
        for row in rows:
            row.update(peak=-1, peak_month=0, first_90_month=None, checkpoints={})
        for month in range(args.months + 1):
            for p, row in zip(probe["players"], rows, strict=True):
                p["age"] = ages[p["id"]] + month // 12
                # Rate opportunity varies; headline ratings always use 24 minutes.
                p["minutes_projection"] = 24
                score = player_display_attribute_summary(probe, p["id"])["overall"]
                p["minutes_projection"] = args.minutes
                if score > row["peak"]:
                    row["peak"], row["peak_month"] = score, month
                if score >= 90 and row["first_90_month"] is None:
                    row["first_90_month"] = month
                if month % 12 == 0:
                    row["checkpoints"][str(month)] = score
            if month == args.months:
                break
            stamp = (cohort["year"] * 12 + 6 + month)
            year, index = divmod(stamp, 12)
            events = health.advance_development(probe, f"{year}-{index + 1:02}", seed=cohort["seed"])
            apply_development_events_to_traits(probe, events["events"])
        result["rows"].extend(rows)
        result["by_pick"] = summarize(result["rows"])
        write(target, result)
        print(args.label, args.minutes, cohort["seed"], cohort["year"], "stars",sum(p["peak"] >= 90 for p in rows), flush=True)
    result.update(status="completed", seconds=round(time.monotonic() - started, 2))
    write(target, result)
    print(json.dumps({"seconds":result["seconds"], "by_pick":result["by_pick"]}), flush=True)


def compare():
    report = {"scope":"Paired controlled learning checks, not ten-season league equilibrium verification.","pairs":{}}
    current_hash = hashlib.sha256((ROOT / "src/nba_gm_data/health.py").read_bytes()).hexdigest()
    for before_name, after_name in (("before-24mpg", "final-24mpg"), ("before-8mpg", "final-8mpg"),
                                    ("opportunity-before-32mpg", "final-32mpg"),
                                    ("holdout-before-24mpg", "holdout-final-24mpg")):
        before = json.loads((OUT / f"{before_name}.json").read_text())
        after = json.loads((OUT / f"{after_name}.json").read_text())
        assert before["status"] == after["status"] == "completed"
        assert before["dataset_sha256"] == after["dataset_sha256"]
        assert after["health_sha256"] == current_hash
        left = {(p["seed"],p["id"]):p for p in before["rows"]}
        right = {(p["seed"],p["id"]):p for p in after["rows"]}
        assert left.keys() == right.keys()
        assert all(left[k]["entry"] == right[k]["entry"] for k in left)
        controls = [k for k,p in right.items() if p["potential"] <= 70 or p["realization"] <= .8]
        assert all(left[k]["checkpoints"] == right[k]["checkpoints"] for k in controls)
        assert all(p["peak"] <= p["all_developable_traits_at_capacity"] + .1 for p in right.values())
        distribution_before = distribution(p["peak"] for p in left.values())
        distribution_after = distribution(p["peak"] for p in right.values())
        assert all(distribution_before[k] == distribution_after[k] for k in ("p10","p25","p50"))
        row = {"players":len(right), "unchanged_control_careers":len(controls),
            "affected_sampled_peaks":sum(left[k]["peak"] != right[k]["peak"] for k in left),
            "initial_ratings_preserved":True, "controls_preserved":True,
            "peak_distribution_before":distribution_before, "peak_distribution_after":distribution_after,
            "90_plus_before":sum(p["peak"] >= 90 for p in left.values()),
            "90_plus_after":sum(p["peak"] >= 90 for p in right.values()),
            "late_85_plus_before":sum(p["pick"] >= 15 and p["peak"] >= 85 for p in left.values()),
            "late_85_plus_after":sum(p["pick"] >= 15 and p["peak"] >= 85 for p in right.values()),
            "late_90_plus_before":sum(p["pick"] >= 15 and p["peak"] >= 90 for p in left.values()),
            "late_90_plus_after":sum(p["pick"] >= 15 and p["peak"] >= 90 for p in right.values()),
            "first_90_age_after":distribution(p["entry_age"] + p["first_90_month"]/12 for p in right.values() if p["first_90_month"] is not None),
            "seconds_before":before["seconds"], "seconds_after":after["seconds"]}
        report["pairs"][after_name] = row
        print(after_name,json.dumps(row),flush=True)
    report.update(status="passed",health_sha256=current_hash)
    write(OUT / "verification.json",report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run", "compare"))
    parser.add_argument("--label", default="before")
    parser.add_argument("--minutes", type=float, default=24)
    parser.add_argument("--months", type=int, default=120)
    parser.add_argument("--dataset", default="entry-cohorts")
    parser.add_argument("--first-year", type=int, default=2027)
    parser.add_argument("--last-year", type=int, default=2030)
    parser.add_argument("--seeds", default="29,913,42")
    parser.add_argument("--reference-health", type=Path)
    args = parser.parse_args()
    if not 0 <= args.minutes <= 48 or not 1 <= args.months <= 180:
        parser.error("Minutes must be in 0..48 and months in 1..180")
    if args.mode == "compare":
        compare()
    elif args.mode == "prepare":
        prepare(args)
    elif args.reference_health:
        original = args.reference_health.read_text()
        before = {n.name:n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef)}
        after = {n.name:n for n in ast.parse((ROOT / "src/nba_gm_data/health.py").read_text()).body if isinstance(n, ast.FunctionDef)}
        assert before.keys() == after.keys()
        assert all(ast.dump(before[k]) == ast.dump(after[k]) for k in before if k != "monthly_trait_delta")
        namespace = dict(health.__dict__)
        exec(compile(ast.get_source_segment(original, before["monthly_trait_delta"]), str(args.reference_health), "exec"), namespace)
        fn = namespace["monthly_trait_delta"]
        reference = FunctionType(fn.__code__, health.__dict__, fn.__name__, fn.__defaults__)
        with patch.object(health, "monthly_trait_delta", reference):
            run(args)
    else:
        run(args)
