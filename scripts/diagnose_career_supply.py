"""Read-only attribution and bounded skill trajectories, not a new league sim."""
from collections import Counter, defaultdict
from copy import deepcopy
import gc
import json
from pathlib import Path
from unittest.mock import patch

from analyze_long_term_health import cohort_outcomes
from audit_roster_floor import rating
from long_term_health import OUT, annual_snapshots, canonical, check_inputs, check_protection, fingerprints, sha, write
from nba_gm_data import health
from nba_gm_data.save import (canonical_with_save, contract_has_salary_in_or_after, load_save,
                              player_display_attribute_summary, should_retire)
from nba_gm_data.talent import trait_ceiling
from ten_season_soak import distribution

DEST = Path(__file__).resolve().parents[1] / "output/development-retention-diagnosis-2026-10-24"


def grade(player, traits, minutes=24):
    view = {"players": [{**player, "minutes_projection": minutes}], "traits": traits}
    return player_display_attribute_summary(view, player["id"])["overall"]


def skill_ceiling(player, traits, seed):
    result = []
    for trait in traits:
        capacity = (trait.get("components") or {}).get("career_capacity")
        if not capacity:
            return None
        ceiling = trait_ceiling(player, trait["trait_key"], capacity,
                                health.prospect_development_realization(player, seed), seed)
        if ceiling is None:
            return None
        result.append({**trait, "value": ceiling})
    return grade(player, result)


def controlled_growth(player, traits, seed, minutes, months=84):
    context = {"players": [{**deepcopy(player), "minutes_projection": minutes}], "traits": deepcopy(traits)}
    entry_age = float(player["age"])
    draft_year = int(player["draft_year"])
    start = grade(player, traits)
    peak = start
    changed = 0
    neutral = 0
    for index in range(months):
        absolute = draft_year * 12 + 6 + index
        month = f"{absolute // 12}-{absolute % 12 + 1:02}"
        context["players"][0]["age"] = entry_age + index // 12
        result = health.advance_development(context, month, seed)
        for event in result["events"]:
            changed += bool(event["trait_deltas"])
            neutral += not bool(event["trait_deltas"])
            deltas = event["trait_deltas"]
            for trait in context["traits"]:
                if trait["trait_key"] in deltas:
                    trait["value"] = round(health.clamp(trait["value"] + deltas[trait["trait_key"]], 0, 100), 3)
        if index % 12 == 11:
            peak = max(peak, grade(context["players"][0], context["traits"]))
    final = grade(context["players"][0], context["traits"])
    return {"entry_overall": start, "final_overall": final, "sampled_peak_overall": peak,
            "gain": final - start, "changed_months": changed, "neutral_months": neutral}


def main():
    check_protection()
    check_inputs()
    source = canonical()
    batch = json.loads((OUT / "overnight/status.json").read_text())
    report = {"scope": "Completed frozen V4 careers. Current diagnosis code differs only by processed-no-change recording and staff-count compatibility; no growth, capacity, retirement or roster tuning.",
              "controlled_scope": "Selected mature prospects, 84 months, constant 4/24/36 minutes, neutral staff (all modifiers default), no health drag. Fixed-24 OVR measured for all arms. Not a season simulation, salary forecast or prediction. Ceilings assume all traits reach their caps simultaneously, ignoring time and aging.",
              "runtime_hashes": fingerprints(), "careers": {}}
    for seed_string, job in sorted(batch["jobs"].items()):
        if job["status"] != "completed":
            continue
        seed = int(seed_string)
        directory = OUT / f"career-{seed}"
        run = json.loads((directory / "run.json").read_text())
        path = run["save_path"]
        digest = sha(path)
        saved = load_save(path)
        snaps = annual_snapshots(directory)
        final = {p["id"]: p for p in snaps[-1]["players"]}
        initial = {p["id"]: p for p in snaps[0]["players"]}
        active = canonical_with_save(source, saved)
        contracts = {c["player_id"]: c for c in active["contracts"] if c.get("player_id")}
        current_players = {p["id"]: p for p in active["players"]}
        old = [p for p in final.values() if p["rostered"] and p["age"] >= 35]
        veteran_rows = []
        for player in old:
            pid = player["id"]
            contract = contracts.get(pid)
            roll = should_retire(current_players[pid], player["age"], seed, "2037-38")
            protected = contract_has_salary_in_or_after(contract, "2037-38") and player["age"] < 42
            observations = [rating(p) for snap in snaps for p in snap["players"] if p["id"] == pid]
            midpoint = next((p for p in snaps[5]["players"] if p["id"] == pid), None)
            history = [s["player_season_stats"].get(pid, {}) for s in saved["season_history"][-3:]]
            games = sum(float(h.get("games") or 0) for h in history)
            minutes = sum(float(h.get("minutes") or 0) for h in history)
            veteran_rows.append({"id": pid, "name": player["name"], "age": player["age"], "overall": rating(player),
                                 "initial_fixed24_overall": rating(initial[pid]) if pid in initial else None,
                                 "peak_to_end": rating(player) - max(observations),
                                 "last5_change": rating(player) - rating(midpoint) if midpoint else None,
                                 "last3_mpg": minutes / games if games else 0,
                                 "next_retirement_roll": roll, "salary_protected": protected,
                                 "roll_blocked_by_contract": roll and protected})
        traits = defaultdict(list)
        for trait in saved["generated_traits"]:
            traits[trait["player_id"]].append(trait)
        generated = {p["id"]: p for p in saved["generated_players"]}
        grades = {pid: grade(p, traits[pid]) for pid, p in generated.items() if traits[pid]}
        bounds = {pid: skill_ceiling(p, traits[pid], seed) for pid, p in generated.items() if traits[pid]}
        retired = set(saved.get("retired_player_ids", []))
        exited = set(saved.get("league_exit_player_ids", []))
        cohorts = cohort_outcomes(saved["incoming_rookies"], snaps, saved["season_history"], grades, retired, exited, saved["state"]["current_date"])
        mature = [r for r in cohorts["players"] if r["year"] <= 2030]
        for row in mature:
            row["capacity24"] = bounds.get(row["id"])
            row["entry_age"] = generated[row["id"]]["age"]
            row["realization"] = health.prospect_development_realization(generated[row["id"]], seed)
            row["max_season_mpg"] = max((s["mpg"] for s in row["seasons"]), default=0)
        groups = {}
        for key in ("1-3", "4-14", "15-30", "31-60"):
            pool = [r for r in mature if r["band"] == key]
            capacities = [p["capacity24"] for p in pool if p["capacity24"] is not None]
            groups[key] = {"count": len(pool), "entry": distribution(p["entry_overall"] for p in pool),
                           "entry_age": distribution(p["entry_age"] for p in pool),
                           "sampled_peak_gain": distribution(p["sampled_peak_gain"] for p in pool),
                           "capacity24": distribution(capacities), "capacity90_count": sum(c >= 90 for c in capacities),
                           "capacity80_count": sum(c >= 80 for c in capacities),
                           "max_mpg": distribution(p["max_season_mpg"] for p in pool),
                           "realization_counts": dict(Counter(str(p["realization"]) for p in pool))}
        # A deterministic diagnostic sample, not a claim of population outcomes.
        elite = sorted([p for p in mature if p["band"] == "1-3"], key=lambda p: (-float(p["capacity24"] or 0), p["id"]))[:3]
        late = sorted([p for p in mature if p["band"] == "31-60"], key=lambda p: (-float(p["capacity24"] or 0), p["id"]))[:3]
        later_first = sorted([p for p in mature if p["band"] == "15-30"], key=lambda p: (-float(p["capacity24"] or 0), p["id"]))[:2]
        trials = []
        with patch.object(health, "coach_development_by_team", return_value={}), \
                patch.object(health, "development_staff_modifiers", return_value={}):
            for row in elite + later_first + late:
                pid = row["id"]
                trial = {"id": pid, "name": row["name"], "pick": row["pick"], "year": row["year"],
                               "capacity24": row["capacity24"], "realization": row["realization"],
                               "actual_peak": row["sampled_peak_overall"], "actual_max_mpg": row["max_season_mpg"],
                               "arms": {str(minutes): controlled_growth(generated[pid], traits[pid], seed, minutes)
                                        for minutes in (4, 24, 36)}}
                if row["pick"] >= 31:
                    age_curve = health.development_age_factor

                    def extended_window(age, *, player=None, seed=1):
                        normal = age_curve(age, player=player, seed=seed)
                        return max(1.0, normal) if age < 30 else normal

                    with patch.object(health, "development_age_factor", side_effect=extended_window):
                        trial["age_window_probe_36"] = controlled_growth(generated[pid], traits[pid], seed, 36)
                    trial["age_window_probe_scope"] = "Diagnostic only: hold growth age factor at least 1 through age 29; actual age, skill focus and all other rules unchanged. Not a proposed calibration."
                trials.append(trial)
        old_gains = [p["overall"] - p["initial_fixed24_overall"] for p in veteran_rows if p["initial_fixed24_overall"] is not None]
        report["careers"][seed_string] = {
            "veterans": {"count": len(old), "overall": distribution(p["overall"] for p in veteran_rows),
                         "same_player_decade_change": distribution(old_gains), "last3_mpg": distribution(p["last3_mpg"] for p in veteran_rows),
                         "peak_to_end": distribution(p["peak_to_end"] for p in veteran_rows),
                         "last5_change": distribution(p["last5_change"] for p in veteran_rows if p["last5_change"] is not None),
                         "retirement_probe_scope": "Static upcoming-offseason policy probe for 2037-38, holding endpoint age, role and contract schedule constant; not a count of past retirements actually vetoed.",
                         "salary_protected": sum(p["salary_protected"] for p in veteran_rows),
                         "next_roll_true": sum(p["next_retirement_roll"] for p in veteran_rows),
                         "next_roll_blocked": sum(p["roll_blocked_by_contract"] for p in veteran_rows),
                         "rows": veteran_rows},
            "cohort_groups": groups, "mature_cohorts": mature, "controlled_trajectories": trials}
        assert sha(path) == digest
        print(seed, json.dumps({"veterans": {k: v for k, v in report["careers"][seed_string]["veterans"].items() if k != "rows"}, "groups": groups}), flush=True)
        del saved, active, cohorts, mature, generated, traits, snaps
        gc.collect()
    check_protection()
    check_inputs()
    write(DEST / "career-diagnosis.json", report)
    print("Saved career-diagnosis.json", flush=True)


if __name__ == "__main__":
    main()
