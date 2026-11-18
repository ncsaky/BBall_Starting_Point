"""Selective learning runway does not raise the whole prospect floor."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from nba_gm_data import health
from nba_gm_data.save import apply_development_events_to_traits, process_development_months
from nba_gm_data.talent import trait_ceiling


class ProspectLearningTests(unittest.TestCase):
    def player(self, **changes):
        return {"id":"learning_control", "position":"SG", "age":24, "team_id":"team",
                "minutes_projection":24, "rotation_priority":"core_rotation",
                "potential":90, "current_ability":40, **changes}

    def profile(self, **changes):
        return {"version":2, "entry_value":55, "ability":40, "potential":90, "aptitude":.9, **changes}

    def test_monthly_development_matches_pinned_reference(self):
        # Pinned outputs (seeded noise and season draw included) for busts, late bloomers and veteran decline.
        # Recaptured 2026-11-19 after the DEV-TUNE aging curve and season draw (two-thirds of Basketball Index's
        # year-to-year spread). A deliberate change to the development formula must update these on purpose.
        cases = [
            (65,52,.9,1.12,24,8,"release_speed",2,-0.05268998407811121),
            (90,40,.9,.55,22,24,"release_speed",2,-0.20430386156804337),
            (90,40,.9,.8,26,8,"release_speed",2,-0.06662279322096835),
            (90,40,.9,1.28,31,24,"release_speed",2,-0.3713142289149821),
            (90,40,.9,1.28,36,24,"foot_speed_lateral_agility",2,-0.33304518659022797),
            (90,40,.2,1.28,25,32,"release_speed",2,0.003241281289099507),
            (90,40,.9,1.28,24,24,"release_speed",None,-0.8285984080760114),
            (90,40,.9,1.28,24,24,"release_speed",1,-0.8285984080760114),
        ]
        for potential, ability, aptitude, realization, age, minutes, key, version, expected in cases:
            with self.subTest(potential=potential, realization=realization, age=age, version=version):
                player = self.player(potential=potential,current_ability=ability,age=age,minutes_projection=minutes,
                    rotation_priority="fringe" if minutes<16 else "core_rotation")
                profile = None if version is None else self.profile(version=version,ability=ability,potential=potential,aptitude=aptitude)
                with patch.object(health,"prospect_development_realization",return_value=realization):
                    actual = health.monthly_trait_delta(player,key,65,age,minutes,{},0,17,"2030-01",.8,profile)
                self.assertAlmostEqual(actual,expected,places=12)

    def test_raw_high_upside_learning_is_bounded_and_not_a_draft_slot_bonus(self):
        player = self.player(potential=95,current_ability=30)
        profile = self.profile(potential=95,ability=30,entry_value=40,aptitude=1.15)
        staff = {"development_multiplier":1.2,"patience_multiplier":1.1}
        deltas = []
        with patch.object(health,"prospect_development_realization",return_value=1.28):
            for age in (18,24,28,30,35):
                for minutes in (0,8,24,32):
                    for key in health.DEVELOPMENT_TRAITS:
                        delta = health.monthly_trait_delta(player,key,40,age,minutes,staff,0,17,"2030-01",1.45,profile)
                        injured = health.monthly_trait_delta(player,key,40,age,minutes,staff,2,17,"2030-01",1.45,profile)
                        # Prospects with skill capacities get only a small share of the season draw (x0.16).
                        draw = .16 * health.DEVELOPMENT_SEASON_VOLATILITY * 5
                        self.assertGreaterEqual(delta,-.45 - draw)
                        self.assertLessEqual(delta,.81 + draw)
                        self.assertLessEqual(injured,delta)
                        deltas.append(delta)
            first = health.monthly_trait_delta({**player,"draft_pick":1},"release_speed",40,24,24,{},0,17,"2030-01",1,profile)
            late = health.monthly_trait_delta({**player,"draft_pick":60},"release_speed",40,24,24,{},0,17,"2030-01",1,profile)
        self.assertEqual(first,late)
        self.assertGreater(max(deltas),.36)

    def test_practice_does_not_replace_minutes_staff_or_individual_capacity(self):
        player, profile = self.player(), self.profile()
        # Expected (no season form or monthly noise): prospects who play now get full good and bad years,
        # which would swamp a one-month comparison of the learning runway itself.
        with patch.object(health,"prospect_development_realization",return_value=1.12):
            fringe = health.monthly_trait_delta({**player,"rotation_priority":"fringe"},"release_speed",55,26,8,{},0,17,"2030-01",.2,profile,expected=True)
            rotation = health.monthly_trait_delta(player,"release_speed",55,26,24,{},0,17,"2030-01",.2,profile,expected=True)
            supported = health.monthly_trait_delta(player,"release_speed",55,26,24,{"development_multiplier":1.2},0,17,"2030-01",.2,profile,expected=True)
            ceiling = trait_ceiling(player,"release_speed",profile,1.12,17)
            at_capacity = health.monthly_trait_delta(player,"release_speed",ceiling,26,24,{},0,17,"2030-01",1,profile)
        self.assertGreater(fringe,0)
        self.assertGreater(rotation,fringe)
        self.assertGreaterEqual(supported,rotation)
        self.assertLessEqual(at_capacity,0)
        self.assertEqual(ceiling,trait_ceiling(player,"release_speed",profile,1.12,17))

    def test_even_exceptional_practice_support_is_below_rotation_workload(self):
        player = self.player(potential=95,current_ability=30)
        profile = self.profile(potential=95,ability=30,entry_value=40,aptitude=1.15)
        with patch.object(health,"prospect_development_realization",return_value=1.28):
            bench = health.monthly_trait_delta({**player,"rotation_priority":"fringe"},"release_speed",55,24,0,{},0,17,"2030-01",.2,profile,expected=True)
            rotation = health.monthly_trait_delta(player,"release_speed",55,24,24,{},0,17,"2030-01",.2,profile,expected=True)
        self.assertGreater(rotation,bench)

    def test_new_profile_survives_real_development_events_and_serialized_reload(self):
        player = self.player(age=19)
        context = {"meta":{"talent_model_version":2},"players":[player],"traits":[
            {"player_id":player["id"],"trait_key":key,"value":55,
             "components":{"career_capacity":self.profile(aptitude=.15 if key=="shooting_range" else .9)}}
            for key in health.DEVELOPMENT_TRAITS]}
        left,right = deepcopy(context),deepcopy(context)
        with patch.object(health,"prospect_development_realization",return_value=1.12):
            for month in range(84):
                for probe in (left,right):
                    probe["players"][0]["age"] = 19 + month//12
                    events = health.advance_development(probe,f"{2030+month//12}-{month%12+1:02}",17)
                    apply_development_events_to_traits(probe,events["events"])
                if month%12==0:
                    right = json.loads(json.dumps(right))
        self.assertEqual(left["traits"],right["traits"])
        values = {t["trait_key"]:t["value"] for t in left["traits"]}
        self.assertGreater(values["release_speed"],values["shooting_range"])

    def test_month_batch_and_split_reload_use_the_same_new_learning(self):
        player = self.player(age=20)
        context = {"meta":{"talent_model_version":2},"players":[player],"traits":[
            {"player_id":player["id"],"trait_key":key,"value":55,
             "components":{"career_capacity":self.profile()}}
            for key in health.DEVELOPMENT_TRAITS]}
        bulk,split = deepcopy(context),deepcopy(context)
        saved = {"development_events":[],"applied_development_months":[],"news_items":[]}
        left,right = deepcopy(saved),deepcopy(saved)
        with patch.object(health,"prospect_development_realization",return_value=1.12):
            process_development_months(bulk,left,"2030-06-30","2030-09-01",17)
            for start,end in (("2030-06-30","2030-07-01"),("2030-07-01","2030-08-01"),("2030-08-01","2030-09-01")):
                process_development_months(split,right,start,end,17)
                split,right = json.loads(json.dumps(split)),json.loads(json.dumps(right))
            self.assertEqual(process_development_months(bulk,left,"2030-06-30","2030-09-01",17),[])
        self.assertEqual(bulk["traits"],split["traits"])
        self.assertEqual(left,right)
        self.assertEqual(left["applied_development_months"],["2030-07","2030-08","2030-09"])


if __name__ == "__main__":
    unittest.main()
