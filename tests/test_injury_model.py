"""Injury model v2: per-body-part risk fitted to Basketball Index evidence (2026-11-18)."""
import random
import unittest
from datetime import date

from nba_gm_data import injury_model as im
from nba_gm_data.save import record_lasting_injury_effect

MODEL = im.load_model()
PLAYER = {"id": "probe", "age": 27, "height_inches": 79, "weight_lbs": 215, "position": "SF"}
TRAITS = {"rim_pressure": 60.0, "offensive_rebounding": 50.0, "stamina_cardio": 60.0}
ON = date(2027, 1, 15)


class InjuryModelTests(unittest.TestCase):
    def hazards(self, player=PLAYER, minutes=30.0, history=()):
        return im.part_hazards(MODEL, player, TRAITS, minutes, list(history), ON)

    def test_recent_same_part_injury_compounds_that_part_most(self):
        base = self.hazards()
        after_knee = self.hazards(history=[(date(2026, 12, 1), "knee")])
        knee_ratio = after_knee["knee"] / base["knee"]
        others = [after_knee[p] / base[p] for p in base if p not in ("knee", "illness")]
        self.assertGreater(knee_ratio, 1.15)
        self.assertGreater(knee_ratio, max(others))
        # ...and it fades: the same injury three years earlier barely matters.
        old_knee = self.hazards(history=[(date(2024, 1, 1), "knee")])
        self.assertLess(old_knee["knee"] / base["knee"], 1.05)

    def test_workload_and_body_type_change_which_injuries_happen(self):
        light, heavy = self.hazards(minutes=12), self.hazards(minutes=36)
        self.assertGreater(sum(heavy.values()), sum(light.values()))
        guard = self.hazards(player=PLAYER | {"position": "PG", "height_inches": 74, "weight_lbs": 190})
        center = self.hazards(player=PLAYER | {"position": "C", "height_inches": 84, "weight_lbs": 250})
        self.assertGreater(guard["hamstring"] / sum(guard.values()), center["hamstring"] / sum(center.values()))

    def test_recovery_comes_from_real_absences_and_skips_the_offseason(self):
        rng = random.Random(3)
        knees = [im.sample_recovery(None, "knee", rng)["days"] for _ in range(400)]
        self.assertGreater(max(knees), 150)            # real long tail (e.g. ACL tears)
        self.assertLessEqual(sorted(knees)[200], 20)   # most knee injuries are short
        self.assertEqual(im.basketball_return_date(date(2027, 5, 20), 60), date(2027, 10, 19))
        self.assertEqual(im.basketball_return_date(date(2027, 1, 10), 5), date(2027, 1, 15))

    def test_lasting_decline_only_for_evidence_backed_major_injuries(self):
        achilles = {"diagnosis": "Achilles tendon rupture", "lasting_rapm_change": im.lasting_effect(MODEL, "Achilles tendon rupture", "achilles"),
                    "expected_days_missed": 300}
        self.assertLess(achilles["lasting_rapm_change"], 0)
        deltas = im.lasting_trait_deltas(achilles)
        self.assertEqual(set(deltas), set(im.LASTING_TRAITS))
        self.assertTrue(all(v < -3 for v in deltas.values()))
        sprain = {"diagnosis": "ankle sprain", "lasting_rapm_change": im.lasting_effect(MODEL, "ankle sprain", "ankle"),
                  "expected_days_missed": 6}
        self.assertEqual(im.lasting_trait_deltas(sprain), {})
        flare = {"diagnosis": "knee inflammation", "lasting_rapm_change": -0.21, "expected_days_missed": 3}
        self.assertEqual(im.lasting_trait_deltas(flare), {})

    def test_lasting_decline_is_recorded_once_per_diagnosis_per_year(self):
        save = {"development_events": []}
        event = {"id": "inj1", "player_id": "probe", "team_id": "t", "start_date": "2027-01-15",
                 "diagnosis": "ACL tear", "lasting_rapm_change": -0.33, "expected_days_missed": 250}
        record_lasting_injury_effect(save, event)
        record_lasting_injury_effect(save, event | {"id": "inj2", "start_date": "2027-06-01"})
        self.assertEqual(len(save["development_events"]), 1)
        self.assertTrue(all(v < 0 for v in save["development_events"][0]["trait_deltas"].values()))


class ReturnRampTests(unittest.TestCase):
    def test_ramp_follows_evidence_and_the_coach(self):
        from nba_gm_data.injury_model import return_minutes_multiplier as ramp
        self.assertEqual(ramp(0, 0), 1.0)
        self.assertAlmostEqual(ramp(8, 0), 1 - 0.162, places=3)           # 6-10 games missed: -16% first game back
        self.assertGreater(ramp(8, 4), ramp(8, 0))                         # eases back
        self.assertEqual(ramp(8, 8), 1.0)                                  # back to normal after 8 games
        self.assertGreater(ramp(25, 0, rotation_star=1.0), ramp(25, 0))    # a poor rotation manager rushes players back
        self.assertLess(ramp(25, 0, rotation_star=5.0), ramp(25, 0))

    def test_sim_pool_applies_the_ramp_and_keeps_240_minutes(self):
        from nba_gm_data.sim import return_ramped_player_pool
        pool = [{"player": {"id": f"p{i}"}, "minutes": 24.0} for i in range(10)]
        pool[0] = pool[0] | {"health_return_absence": 15, "health_games_since_return": 0}
        out = return_ramped_player_pool(pool, None)
        self.assertLess(out[0]["minutes"], out[1]["minutes"])
        self.assertAlmostEqual(sum(item["minutes"] for item in out), 240.0, places=3)


if __name__ == "__main__":
    unittest.main()
