"""Elite upside is selective and seeded; it is not a universal rookie boost."""
from copy import deepcopy
import json
import unittest

from nba_gm_data import health
from nba_gm_data.save import apply_development_events_to_traits, player_display_attribute_summary


class ProspectDevelopmentTests(unittest.TestCase):
    def player(self, pid="prospect", **changes):
        return {"id": pid, "name": pid, "team_id": "team", "age": 19,
                "position": "SG", "minutes_projection": 24,
                "current_ability": 58, "potential": 86, **changes}

    def find(self, realization, timing=None):
        for index in range(10000):
            player = self.player(f"prospect_{index}")
            if health.prospect_development_realization(player, 17) != realization:
                continue
            if timing is None or health.development_age_factor(24, player=player, seed=17) == timing:
                return player
        self.fail("Missing seeded career profile")

    def test_ordinary_and_low_realization_rates_remain_unchanged(self):
        for realization in (0.55, 0.80, 1.0, 1.12, 1.28):
            player = self.find(realization)
            for potential, ability in ((65, 28), (60, 48), (50, 45)):
                ordinary = {**player, "potential": potential, "current_ability": ability}
                base = health.clamp(0.75 + max(0, potential - ability) / 18, 0.65, 2.35)
                self.assertEqual(health.development_upside_multiplier(ordinary, 17),
                                 round(health.clamp(base * realization, 0.45, 2.8), 4))
                for age in (19, 24, 27, 30, 35):
                    self.assertEqual(health.development_age_factor(age, player=ordinary, seed=17),
                                     health.development_age_factor(age))
            if realization <= 0.80:
                base = health.clamp(0.75 + (player["potential"] - player["current_ability"]) / 18, 0.65, 2.35)
                self.assertEqual(health.development_upside_multiplier(player, 17),
                                 round(base * realization, 4))
                for age in (19, 24, 27, 30, 35):
                    self.assertEqual(health.development_age_factor(age, player=player, seed=17),
                                     health.development_age_factor(age))

    def test_elite_fulfillment_changes_rates_without_guaranteeing_it(self):
        multipliers = [health.development_upside_multiplier(self.find(r), 17)
                       for r in (0.55, 0.80, 1.0, 1.12, 1.28)]
        self.assertEqual(multipliers, sorted(multipliers))
        self.assertGreater(multipliers[-1], 2 * multipliers[0])
        self.assertLessEqual(multipliers[-1], 3.8)
        player = self.find(1.28)
        # Draft slot must not prevent a later pick from realizing the same upside.
        self.assertEqual(health.development_upside_multiplier({**player, "draft_pick": 1}, 17),
                         health.development_upside_multiplier({**player, "draft_pick": 58}, 17))

    def test_maturation_has_early_standard_and_later_windows(self):
        early, standard, late = [self.find(1.12, value) for value in (0.45 * 1.12, 0.45, 0.88)]
        self.assertGreater(health.development_age_factor(19, player=early, seed=17),
                           health.development_age_factor(19, player=late, seed=17))
        self.assertGreater(health.development_age_factor(26, player=late, seed=17),
                           health.development_age_factor(26, player=early, seed=17))
        for player in (early, standard, late):
            for age in (30, 31, 32, 35, 41):
                self.assertEqual(health.development_age_factor(age, player=player, seed=17),
                                 health.development_age_factor(age))

    def test_missing_upside_metadata_preserves_veteran_behavior(self):
        for fields in ({}, {"potential": 95}, {"current_ability": 60}):
            player = {"id": "veteran", **fields}
            self.assertEqual(health.development_upside_multiplier(player, 17), 1.0)
            for age in (19, 24, 29, 35):
                self.assertEqual(health.development_age_factor(age, player=player, seed=17),
                                 health.development_age_factor(age))

    def test_profile_is_repeatable_but_varies_between_save_seeds(self):
        player = self.player()
        rates = {health.development_upside_multiplier(player, seed) for seed in range(100)}
        self.assertGreater(len(rates), 3)
        self.assertEqual(health.development_upside_multiplier(player, 17),
                         health.development_upside_multiplier(json.loads(json.dumps(player)), 17))

    def test_opportunity_staff_and_injury_still_matter_and_deltas_stay_bounded(self):
        player = self.find(1.28)
        for age in (19, 24, 28, 33, 38):
            for trait in health.DEVELOPMENT_TRAITS:
                args = (player, trait, 65, age)
                normal = health.monthly_trait_delta(*args, 24, {}, 0, 17, "2027-01")
                injured = health.monthly_trait_delta(*args, 24, {}, 2, 17, "2027-01")
                supported = health.monthly_trait_delta(*args, 24, {"development_multiplier": 1.2}, 0, 17, "2027-01")
                fringe = health.monthly_trait_delta(*args, 4, {}, 0, 17, "2027-01")
                self.assertLessEqual(injured, normal)
                self.assertGreaterEqual(supported, normal)
                self.assertLessEqual(fringe, normal)
                for value in (normal, injured, supported, fringe):
                    self.assertGreaterEqual(value, -0.12)
                    self.assertLessEqual(value, 0.36)

    def test_divergent_careers_survive_serialized_reload(self):
        players = [self.find(r) for r in (0.55, 0.80, 1.0, 1.12, 1.28)]
        context = {"players": players, "traits": [
            {"player_id": p["id"], "trait_key": key, "value": 66.0}
            for p in players for key in health.DEVELOPMENT_TRAITS]}
        uninterrupted, reloaded = deepcopy(context), deepcopy(context)
        entry = {p["id"]: player_display_attribute_summary(context, p["id"])["overall"] for p in players}
        for month in range(84):
            for probe in (uninterrupted, reloaded):
                for player in probe["players"]:
                    player["age"] = 19 + month // 12
                events = health.advance_development(probe, f"{2027 + month // 12}-{month % 12 + 1:02}", seed=17)
                apply_development_events_to_traits(probe, events["events"])
            reloaded = json.loads(json.dumps(reloaded))
        self.assertEqual(uninterrupted["traits"], reloaded["traits"])
        gains = [player_display_attribute_summary(uninterrupted, p["id"])["overall"] - entry[p["id"]] for p in players]
        self.assertGreater(max(gains) - min(gains), 4)
        self.assertLess(gains[0], gains[-1])


if __name__ == "__main__":
    unittest.main()
