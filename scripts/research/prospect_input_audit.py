#!/usr/bin/env python3
"""Audit rookie inputs against season-matched Basketball Index evidence.

Run with NBA_GM_RATINGS_MODEL=inputs_v1 PYTHONPATH=src .venv/bin/python
scripts/research/prospect_input_audit.py --save output/e2c/scratch/inputs_save.json
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
from statistics import NormalDist, mean, median
from unittest.mock import patch

from nba_gm_data import bbi_evidence as bbi
from nba_gm_data import input_estimator as ie
from nba_gm_data import ratings_model as ratings
from nba_gm_data import trait_adapter as adapter
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.player_profile import engine_header
from nba_gm_data.save import canonical_with_save

ROOT = Path(__file__).resolve().parents[2]
WATCH = ("Darryn Peterson", "Cameron Boozer", "Dylan Harper", "Aday Mara", "Caleb Wilson", "Cooper Flagg")
MINUTES = 500
SEASONS = {2023: "2023-24", 2024: "2024-25", 2025: "2025-26"}
GROUPS = {
    "Shooting": [f"S{i:02d}" for i in range(1, 10)],
    "Finishing and receiving": [f"S{i:02d}" for i in range(10, 16)],
    "Handling and attack reads": [f"S{i:02d}" for i in range(16, 21)],
    "Post craft": [f"S{i:02d}" for i in range(21, 24)],
    "Foul craft, routes and screens": [f"S{i:02d}" for i in range(24, 29)],
    "Rebounding technique": [f"S{i:02d}" for i in range(29, 33)],
    "Defense technique and reads": [f"S{i:02d}" for i in range(33, 47)],
    "Passing reads": [i for i in ie.DEFINITIONS if i.endswith(".recognition")],
    "Passing execution": [i for i in ie.DEFINITIONS if i.endswith(".execution")],
}
INPUT_IDS = [*sum(GROUPS.values(), []), *(f"P{i:02d}" for i in range(1, 13)), "T08"]
USAGE = "Stable True Usage%"
NORMAL = NormalDist()


def band(player):
    pick = int(player.get("draft_position") or player.get("overall_pick") or 0)
    if not pick or pick > 60:
        return None
    if player.get("draft_round") == 2 or pick > 30:
        return "Second round"
    return "Top 5" if pick <= 5 else "6–14" if pick <= 14 else "15–30"


def is_creator(player):
    return any(token in ie._role(player) for token in ("creator", "handler", "playmaker"))


def season_evidence():
    """Mirror the mapped metric weights, using only a single season per rookie."""
    mapping = bbi.load_mapping(ROOT)["inputs"]
    spec = {iid: mapping[iid]["metrics"] for iid in INPUT_IDS
            if iid in mapping and mapping[iid].get("metrics") and iid != "T08"}
    names = {USAGE} | {term[k] for terms in spec.values() for term in terms
                       for k in ("metric", "per") if term.get(k)}
    values = bbi.collect_values(ROOT, names)
    all_years = {}
    for year, season in SEASONS.items():
        usage = values[season, USAGE]
        minutes = {key: m for key, (_, m, _) in usage.items()}
        data = defaultdict(dict)
        for iid, terms in spec.items():
            total_scores = defaultdict(float)
            weights = defaultdict(float)
            for term in terms:
                records = values.get((season, term["metric"]), {})
                if term.get("per"):
                    records = bbi._per_exposure(records, values.get((season, term["per"]), {}))
                ranks = bbi._percentiles(records, int(term.get("direction", 1)))
                weight = bbi.STRENGTH[term.get("strength", "supporting")]
                for key, pct in ranks.items():
                    total_scores[key] += weight * NORMAL.inv_cdf(pct)
                    weights[key] += weight
            scores = {key: total_scores[key] / w for key, w in weights.items()}
            pool = sorted(value for key, value in scores.items() if minutes.get(key, 0) >= MINUTES)
            for key in scores.keys() & usage.keys():
                raw, exposure, pid = usage[key]
                if pid and exposure >= MINUTES and len(pool) >= 30:
                    data[pid][iid] = adapter._percentile(pool, scores[key])
        usage_pool = sorted(raw for raw, m, _ in usage.values() if m >= MINUTES)
        for raw, m, pid in usage.values():
            if pid and m >= MINUTES:
                data[pid]["T08"] = adapter._percentile(usage_pool, raw)
                data[pid]["usage"] = raw / 100
        all_years[year] = data
    return all_years


def percentiles(records, pools):
    return {iid: adapter._percentile(pool, ie.scalar_value(records[iid]))
            for iid, pool in pools.items()}


def report_cohorts(cohorts, dimensions):
    print("\n| Group | Band | " + " | ".join(cohorts) + " |")
    print("|---|---|" + "---:|" * len(cohorts))
    for label, ids in dimensions.items():
        for slot in ("Top 5", "6–14", "15–30", "Second round"):
            cells = []
            for rows in cohorts.values():
                per_player = [mean(row[iid] for iid in ids if iid in row) for row in rows[slot]
                              if any(iid in row for iid in ids)]
                cells.append(f"{100 * median(per_player):.1f} ({len(per_player)})" if per_player else "—")
            print(f"| {label} | {slot} | " + " | ".join(cells) + " |")


def card_ranks(canonical):
    rows = {p["id"]: engine_header(canonical, p["id"]) for p in canonical["players"] if p.get("team_abbrev")}
    rows = {pid: value for pid, value in rows.items() if value}
    ranks = {key: {pid: n for n, pid in enumerate(sorted(rows, key=lambda p: -rows[p][key]), 1)}
             for key in ("ovr", "off", "def")}
    return rows, ranks


def baseline_changes(canonical, replacements):
    """Keep calibration and display tables fixed and rederive from edited inputs in memory."""
    scenario = {**canonical, "traits": [dict(t) for t in canonical["traits"]]}
    scenario.pop("_cache_context", None)
    key = canonical[ratings.MODEL_KEY]["inputs_key"]
    base = ratings._INPUT_CACHE[key]
    with patch.dict(ratings._INPUT_CACHE, {key: {**base, **replacements}}):
        ratings._rederive(scenario, replacements)
        ratings._rebase_offensive_profile_anchors(scenario, ratings._trait_values(scenario))
        return card_ranks(scenario)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    original = load_app_canonical(ROOT)
    legacy = ratings._trait_values(original)
    canonical = deepcopy(original)
    ratings.install_inputs_model(canonical, ROOT)
    base = ratings.load_league_inputs(ROOT)
    historical = season_evidence()
    incoming = [p for p in original["players"] if p.get("draft_year") == 2026 and band(p)]
    reference = [doc for p in original["players"] if p.get("draft_year") != 2026
                 if (doc := base.get(p["id"]))]
    pools = {iid: sorted(ie.scalar_value(d[iid]) for d in reference) for iid in INPUT_IDS}
    evidence_ids = {iid for year in historical.values() for row in year.values() for iid in row} - {"usage"}
    cohorts = {k: defaultdict(list) for k in ("Observed", "2026 installed", "2026 matched inputs")}
    fictional = []
    if args.save:
        cohorts["2027 fictional"] = defaultdict(list)
        cohorts["2027 matched inputs"] = defaultdict(list)
        saved = json.loads(args.save.read_text())
        active = canonical_with_save(deepcopy(original), saved)
        for p in saved["generated_players"]:
            if p.get("source_kind") == "generated_rookie" and band(p):
                doc = ratings._player_base_inputs(active[ratings.MODEL_KEY], p["id"])
                fictional.append((p, doc))
                row = percentiles(doc, pools)
                cohorts["2027 fictional"][band(p)].append(row)
                cohorts["2027 matched inputs"][band(p)].append({k: row[k] for k in evidence_ids})
    print("Startup rating pool", len(card_ranks(canonical)[0]), "input reference", len(reference))
    for p in original["players"]:
        if p.get("draft_year") in SEASONS and band(p):
            observed = historical[p["draft_year"]].get(p["id"])
            if observed:
                print("Historical", p["draft_year"], band(p), p["name"], observed["usage"])
                cohorts["Observed"][band(p)].append(observed)
    for cohort in (incoming, [p for p in original["players"] if p.get("draft_year") in SEASONS]):
        print("Cohort counts", {year: {slot: sum(p["draft_year"] == year and band(p) == slot for p in cohort)
                                      for slot in ("Top 5", "6–14", "15–30", "Second round")}
                                 for year in sorted({p["draft_year"] for p in cohort})})
    for year, season in historical.items():
        print("First-season usage cohort", year, {
            slot: len([p for p in original["players"] if p.get("draft_year") == year
                       and band(p) == slot and p["id"] in season])
            for slot in ("Top 5", "6–14", "15–30", "Second round")})
    if fictional:
        _, generated_ranks = card_ranks(active)
        ranked = [(generated_ranks["ovr"][p["id"]], p["name"], p["overall_pick"],
                   ie.scalar_value(doc["T08"])) for p, doc in fictional if p["id"] in generated_ranks["ovr"]]
        print("Fictional overall ranks in copied save", len(generated_ranks["ovr"]), sorted(ranked)[:10])
        print("Fictional usage tail", sum(ie.scalar_value(doc["T08"]) >= .50 for _, doc in fictional),
              "of", len(fictional), "at 50% or more vs", sum(
                  row["usage"] >= .50 for rows in cohorts["Observed"].values() for row in rows), "observed")
    for slot, observed in cohorts["Observed"].items():
        print("Usage", slot, "observed", median(r["usage"] for r in observed),
              "installed", median(ie.scalar_value(base[p["id"]]["T08"]) for p in incoming if band(p) == slot),
              "fictional", median(ie.scalar_value(doc["T08"]) for p, doc in fictional if band(p) == slot)
              if fictional else None)
    for p in incoming:
        row = percentiles(base[p["id"]], pools)
        cohorts["2026 installed"][band(p)].append(row)
        cohorts["2026 matched inputs"][band(p)].append({k: row[k] for k in evidence_ids})
    report_cohorts(cohorts, {**GROUPS, **{i: [i] for i in INPUT_IDS if i[0] in "PT"}})
    scale = bbi.load_scale_map(ROOT)
    print("\nScale endpoints and median", {k: [v[0], v[100], v[-1]] for k, v in scale["T08"].items()})
    simple = ie.InputEstimator()
    # No completed NBA season for the 2026 cohort. Skip the older percentile-feed scan.
    with patch.object(ie, "load_bbi_evidence", return_value={}):
        local = ie.InputEstimator.from_local(ROOT)
    base_ranks = card_ranks(canonical)
    fitted = ratings._FITTED_CACHE[tuple(canonical[ratings.MODEL_KEY]["fitted_key"])]
    scenarios = defaultdict(dict)
    for p in original["players"]:
        if p["name"] not in WATCH:
            continue
        pid = p["id"]
        print("\nWatch", p["name"], p["draft_year"], p["position"], p["current_ability"],
              base_ranks[0].get(pid), {k: r.get(pid) for k, r in base_ranks[1].items()},
              "T08", ie.scalar_value(base[pid]["T08"]))
        print("Path matches (grade/physical/T08)")
        for name, estimator, traits, prospect in (
                ("build", local, legacy[pid], False),
                ("fallback", simple, legacy[pid], True),
                ("build neutral traits", local, {}, False),
                ("fallback neutral traits", simple, {}, True)):
            doc = estimator.estimate_player_inputs(p, traits, prospect=prospect).to_dict()["inputs"]
            raw = ie.scalar_value(doc["T08"])
            bbi.map_tendency_inputs(doc, scale)
            counts = {kind: sum(abs(ie.scalar_value(doc[i]) - ie.scalar_value(base[pid][i])) < 1e-6
                                for i in INPUT_IDS if i.startswith(kind)) for kind in "SFPT"}
            print(name, counts, "T08", raw, ie.scalar_value(doc["T08"]),
                  "inputs", {i: ie.scalar_value(doc[i]) for i in ("S01", "S16", "S33", "P05")})
            if p["draft_year"] == 2026:
                scenarios[name][pid] = doc
        print("Legacy", legacy[pid])
        print("Largest input pcts", sorted(percentiles(base[pid], pools).items(), key=lambda kv: -kv[1])[:12])
        print("Derived", ratings._trait_values(canonical)[pid])
        scalars = adapter._scalars_for_player(base[pid], ie.DEFINITIONS)
        for trait in ("handle_pressure", "rim_deterrence", "stamina_cardio"):
            composite = adapter._composite(scalars, fitted.input_tables, trait)
            print("Adapter", p["name"], trait, round(composite, 3),
                  round(adapter._percentile(fitted.composite_tables[trait], composite), 3))
    # Separate use of the draft-grade anchors from the legacy-trait residual and usage map.
    observed_creators = [row["usage"] for p in original["players"] if is_creator(p) and band(p)
                         if (row := historical.get(p.get("draft_year"), {}).get(p["id"]))]
    creators = [p for p in incoming if is_creator(p)]
    current_center = median(ie.scalar_value(base[p["id"]]["T08"]) for p in creators)
    measured_center = median(observed_creators)
    offset = ie._logit(measured_center) - ie._logit(current_center)
    print("Creator usage calibration", len(observed_creators), measured_center, len(creators), current_center)
    for p in incoming:
        pid = p["id"]
        estimated = local.estimate_player_inputs(p, legacy[pid], prospect=True).to_dict()["inputs"]
        bbi.map_tendency_inputs(estimated, scale)
        # Counterfactual swaps only technique values. This isolates the grade anchors
        # from other builder or overlay differences, leaving the baseline scale fixed.
        anchor_only = deepcopy(base[pid])
        for iid in sum(GROUPS.values(), []):
            anchor_only[iid] = estimated[iid]
        scenarios["Rookie anchors"][pid] = anchor_only
        if is_creator(p):
            usage_only = deepcopy(base[pid])
            corrected = ie._probability(ie._logit(ie.scalar_value(usage_only["T08"])) + offset)
            usage_only["T08"]["value"]["probability"] = corrected
            scenarios["Creator involvement"][pid] = usage_only
            combined = deepcopy(anchor_only)
            combined["T08"] = usage_only["T08"]
            scenarios["Both"][pid] = combined
        else:
            scenarios["Both"][pid] = anchor_only
    for label in ("Rookie anchors", "Creator involvement", "Both"):
        replacements = scenarios[label]
        print("Scenario involvement", label, {p["name"]: ie.scalar_value(replacements[p["id"]]["T08"])
                                               for p in incoming if p["id"] in replacements and p["name"] in WATCH})
    corrected_cohort = defaultdict(list)
    for p in incoming:
        row = percentiles(scenarios["Both"][p["id"]], pools)
        corrected_cohort[band(p)].append({k: row[k] for k in evidence_ids})
    report_cohorts({"Observed": cohorts["Observed"], "Both matched inputs": corrected_cohort},
                   {**GROUPS, "Involvement": ["T08"]})
    for label, replacements in scenarios.items():
        rows, ranks = baseline_changes(canonical, replacements)
        for p in original["players"]:
            if p["name"] in WATCH:
                pid = p["id"]
                print(label, p["name"], rows.get(pid), {k: r.get(pid) for k, r in ranks.items()})


if __name__ == "__main__":
    main()
