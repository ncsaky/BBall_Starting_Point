from copy import deepcopy
import json
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data.save import SAVE_VERSION, age_staff_contracts, load_save, write_save
from nba_gm_data.staff import (
    SLOT_SKILLS,
    STAFF_SLOTS,
    apply_head_coach_reputation,
    generate_staff_market,
    hire_staff_from_save,
    initialize_save_staff_slots,
    staff_candidate_by_id,
)
from nba_gm_data.staff_lifecycle import retirement_probability, staff_person_id


ROOT = Path(__file__).resolve().parents[1]


def make_staff(person_id, age, role="head_coach", team_id="team_bos", status="employed"):
    return {
        "id": person_id,
        "team_id": team_id,
        "slot": role,
        "name": person_id,
        "age": age,
        "years_experience": max(1, age - 29),
        "reputation": 60.0,
        "job_security": 60.0,
        "market_status": status,
        "contract": {"years_remaining": 4, "annual_salary_millions": 4.0},
        "skill_traits": dict.fromkeys(SLOT_SKILLS[role], 65.0),
        "personality_traits": dict.fromkeys(("communication", "adaptability", "ambition"), 65.0),
    }


def rollover_save(staff=(), former=(), *, seed=0, wins=41, playoff_wins=0):
    return {
        "version": SAVE_VERSION,
        "meta": {"id": "staff-lifecycle", "season": "2027-28", "seed": seed, "user_team_id": "team_bos"},
        "state": {"current_date": "2027-10-01"},
        "staff_slots": list(staff),
        "former_staff": list(former),
        "staff_preseason_expectations": {"2026-27": {"team_bos": 0.5}},
        "team_records": {"team_bos": {"wins": 0, "losses": 0}},
        "season_history": [{
            "season": "2026-27",
            "team_records": {"team_bos": {"wins": wins, "losses": 82 - wins}},
            "playoff_state": {"series": [{"winner_team_id": "team_bos"}] * playoff_wins},
        }],
    }


class StaffLifecycleTests(unittest.TestCase):
    def test_source_experience_including_zero_and_seeded_fallbacks(self):
        research = ROOT / "data" / "research"
        canonical = {
            "gameplay_staff_slots": [
                make_staff("gsw", 40, team_id="team_gsw"),
                make_staff("lal", 40, team_id="team_lal"),
                make_staff("atl", 40, team_id="team_atl"),
                make_staff("generated", 40, role="performance_lead"),
            ],
            "staff_profiles": [
                {"team_id": "team_gsw", "role": "head_coach", "name": "Steve Kerr"},
                {"team_id": "team_lal", "role": "head_coach", "name": "JJ Redick"},
                {"team_id": "team_atl", "role": "head_coach", "name": "Source Test"},
            ],
            "sources": [{"id": "src_espn_coaches_2026", "path": str(research / "coaches_espn_2026.json")}],
        }
        for staff in canonical["gameplay_staff_slots"]:
            staff.pop("age")
            staff.pop("years_experience")
        with TemporaryDirectory() as tmp:
            team_page = Path(tmp) / "staff_bref_team_pages_2026.json"
            team_page.write_text(json.dumps({"teams": [{
                "coach": {"name": "Source Test", "age": "39", "experience": 0, "record": "45-37"},
            }]}))
            canonical["sources"].append({"id": "src_bref_team_pages_2026", "path": str(team_page)})
            first = initialize_save_staff_slots(canonical, 17)
            self.assertEqual(first, initialize_save_staff_slots(canonical, 17))
        by_id = {staff["id"]: staff for staff in first}
        self.assertEqual(by_id["gsw"]["years_experience"], 10)
        self.assertEqual(by_id["gsw"]["source_record"], "37-45")
        self.assertEqual(by_id["lal"]["years_experience"], 1)
        self.assertEqual(by_id["atl"]["years_experience"], 0)
        self.assertEqual(by_id["atl"]["age"], 39)
        self.assertEqual(by_id["generated"]["bio_sources"]["age"], "seeded_estimate")
        self.assertLess(by_id["generated"]["years_experience"], by_id["generated"]["age"] - 20)

    def test_younger_staff_gain_older_staff_decline_and_management_learns(self):
        younger, older = [], []
        for seed in range(20):
            for age, target in [(34, younger), (66, older)]:
                save = rollover_save([make_staff("same-id", age)], seed=seed)
                age_staff_contracts(save, seed=999)
                staff = next(staff for staff in save["staff_slots"] + save["retired_staff"] if staff["id"] == "same-id")
                entry = staff["rating_change_log"][0]
                self.assertEqual(staff["age"], age + 1)
                self.assertEqual(staff["years_experience"], age - 28)
                self.assertEqual(entry["season"], "2026-27")
                for group, deltas in entry["rating_deltas"].items():
                    for key, delta in deltas.items():
                        self.assertAlmostEqual(staff[group][key], 65 + delta)
                target.append(entry["rating_deltas"])
        self.assertGreater(mean(row["personality_traits"]["communication"] for row in younger), 0)
        self.assertLess(mean(row["personality_traits"]["communication"] for row in older), 0)
        for key in SLOT_SKILLS["head_coach"]:
            self.assertGreater(mean(row["skill_traits"][key] for row in younger), 0)
            self.assertLess(mean(row["skill_traits"][key] for row in older), 0)
        self.assertGreater(mean(row["skill_traits"]["rotation_management"] - row["skill_traits"]["locker_room"] for row in younger), 0.4)

    def test_ratings_stay_within_scale_and_real_coach_drift_survives_alignment(self):
        staff = make_staff("kerr", 46)
        staff["skill_traits"].update(rotation_management=95.99, locker_room=20.01)
        staff["personality_traits"].update(communication=95.99, ambition=20.01)
        save = rollover_save([staff])
        age_staff_contracts(save)
        current = save["staff_slots"][0]
        for traits in (current["skill_traits"], current["personality_traits"]):
            self.assertTrue(all(20 <= rating <= 96 for rating in traits.values()))
        snapshot = deepcopy(current)
        apply_head_coach_reputation(current, "Steve Kerr")
        self.assertEqual(current, snapshot)

    def test_retirement_vacates_job_blocks_offers_and_does_not_respawn(self):
        self.assertLess(retirement_probability(49, "employed"), retirement_probability(66, "employed"))
        self.assertLess(retirement_probability(66, "employed"), retirement_probability(66, "fired"))
        old = make_staff("old-coach", 79)
        fired = make_staff("old-fired", 79, team_id=None, status="fired")
        save = rollover_save([old], [fired])
        generated = generate_staff_market({}, save, "head_coach")[0]
        source = staff_person_id(generated)
        generated["age"] = 79
        save["staff_market_pool"] = [generated]
        save["pending_staff_negotiations"] = [{
            "id": "stale-offer", "accepted": True, "team_id": "team_bos", "slot": "head_coach",
            "candidate": generated, "team_offer": {"annual_salary_millions": 9, "years": 3},
        }]
        age_staff_contracts(save)
        self.assertEqual({staff_person_id(staff) for staff in save["retired_staff"]}, {"old-coach", "old-fired", source})
        self.assertEqual(save["staff_slots"][0]["status"], "interim_staff_vacancy")
        self.assertEqual(save["staff_slots"][0]["contract"]["years_remaining"], 1)
        self.assertNotIn(source, {staff_person_id(staff) for staff in generate_staff_market({}, save)})
        with self.assertRaises(ValueError):
            staff_candidate_by_id({}, save, generated["id"], "head_coach")
        self.assertEqual(hire_staff_from_save(save, "stale-offer")["status"], "not_applied")

    def test_refill_maintains_depth_promotion_and_grade_spread(self):
        coordinator = make_staff("strong-coordinator", 44, "offensive_coordinator", None, "expired_contract")
        coordinator["skill_traits"] = dict.fromkeys(coordinator["skill_traits"], 73.0)
        save = rollover_save(former=[coordinator], seed=17)
        save["staff_market_pool"] = []
        for year in range(2027, 2039):
            if year > 2027:
                save["season_history"].append({"season": save["meta"]["season"]})
                save["meta"]["season"] = f"{year}-{str(year + 1)[-2:]}"
                save["state"]["current_date"] = f"{year}-10-01"
            age_staff_contracts(save)
            market = generate_staff_market({}, save)
            self.assertEqual(len(market), len({staff_person_id(staff) for staff in market}))
            for role in STAFF_SLOTS:
                candidates = [staff for staff in market if staff["slot"] == role]
                self.assertGreaterEqual(len(candidates), 20 if role == "head_coach" else 16)
                self.assertLess(median(row["grade"] for row in candidates), 74)
                self.assertGreater(candidates[0]["grade"], 83 if role == "head_coach" else 75)
            if year == 2027:
                promoted = next(staff for staff in market if staff_person_id(staff) == "strong-coordinator")
                self.assertEqual(promoted["slot"], "head_coach")
                self.assertEqual(promoted["promoted_from"], "offensive_coordinator")
                self.assertEqual(promoted["age"], 45)
        self.assertTrue(any(staff["age"] <= 37 and staff["slot"] != "head_coach" for staff in market))

    def test_determinism_save_round_trip_and_same_rollover_guard(self):
        original = rollover_save([make_staff("coach", 43)], seed=0)
        first, second = deepcopy(original), deepcopy(original)
        age_staff_contracts(first, seed=11)
        age_staff_contracts(second, seed=444)
        self.assertEqual(first, second)
        changed_seed = deepcopy(original)
        changed_seed["meta"]["seed"] = 1
        age_staff_contracts(changed_seed)
        self.assertNotEqual(first["staff_market_pool"], changed_seed["staff_market_pool"])
        current = first["staff_slots"][0]
        current["contract"]["years_remaining"] = 4
        age_staff_contracts(first)
        self.assertEqual(first["staff_slots"][0]["rating_change_log"], current["rating_change_log"])
        self.assertEqual(len(first["staff_slots"][0]["rating_change_log"]), 1)
        self.assertEqual(first["staff_market_pool"], second["staff_market_pool"])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "staff.json"
            write_save(path, first)
            loaded = load_save(path)
            for field in ("staff_slots", "staff_market_pool", "retired_staff", "staff_preseason_expectations"):
                self.assertEqual(first[field], loaded[field])

    def test_reputation_and_security_follow_expectations_and_playoff_results(self):
        def review(wins, playoff_wins, *, expected=0.5, hired=None):
            staff = make_staff("coach", 43)
            staff["staff_hired_on"] = hired
            save = rollover_save([staff], wins=wins, playoff_wins=playoff_wins)
            save["staff_preseason_expectations"]["2026-27"]["team_bos"] = expected
            age_staff_contracts(save)
            return save["staff_slots"][0]

        bad = review(30, 0)
        good = review(50, 0)
        playoff = review(50, 3)
        high_expectation = review(50, 0, expected=0.72)
        offseason_hire = review(50, 3, hired="2027-08-01")
        for key in ("reputation", "job_security"):
            self.assertLess(bad[key], 60)
            self.assertLess(high_expectation[key], 60)
            self.assertGreater(good[key], 60)
            self.assertGreater(playoff[key], good[key])
            self.assertEqual(offseason_hire[key], 60)
        self.assertEqual(good["rating_change_log"][0]["results"]["expected_wins"], 41)
        self.assertEqual(playoff["rating_change_log"][0]["results"]["playoff_series_wins"], 3)
        self.assertEqual(offseason_hire["years_experience"], 14)

    def test_coach_fired_after_season_review_receives_result_of_previous_team(self):
        dismissed = make_staff("dismissed", 52, team_id=None, status="fired")
        dismissed.update(last_team_id="team_bos", staff_left_on="2027-05-01")
        replacement = make_staff("replacement", 44)
        replacement["staff_hired_on"] = "2027-07-02"
        save = rollover_save([replacement], [dismissed], wins=28)
        age_staff_contracts(save)
        self.assertLess(save["former_staff"][0]["reputation"], 60)
        self.assertEqual(save["staff_slots"][0]["reputation"], 60)
