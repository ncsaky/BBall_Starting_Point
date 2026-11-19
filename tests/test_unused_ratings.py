"""Inputs that used to be displayed but ignored by the game: screening, shot difficulty, rebounding (2026-11-19)."""
from __future__ import annotations

import copy
import random
import unittest

from nba_gm_data import box_rates, box_variation, offense, screens
from nba_gm_data.ratings_model import load_league_inputs

QUETA = "player_bos-neemias-queta"
INGRAM = "player_lac-brandon-ingram"


def bumped(inputs, key, delta, field="grade"):
    out = dict(inputs)
    record = copy.deepcopy(out[key])
    record["value"][field] = float(record["value"][field]) + delta
    out[key] = record
    return out


class ScreeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_league_inputs()

    def test_screen_assists_follow_screening_skill_and_role(self):
        queta, ingram = self.inputs[QUETA], self.inputs[INGRAM]
        base = box_rates.screen_assists_per36_from_inputs(queta)
        self.assertGreater(base, 3 * box_rates.screen_assists_per36_from_inputs(ingram))
        for key in ("S27", "S28"):
            self.assertGreater(box_rates.screen_assists_per36_from_inputs(bumped(queta, key, 15)), base * 1.2)

    def test_screening_facet_reads_screen_production(self):
        player = {"id": "x", "height_inches": 80, "weight_lbs": 220, "position": "SF"}
        traits = {"scheme_iq": 60.0, "stamina_cardio": 60.0}
        original = offense._screen_assist_rate
        try:
            offense._screen_assist_rate = lambda canonical, p: None
            legacy = offense.offensive_profile({}, player, traits)["screening"]
            offense._screen_assist_rate = lambda canonical, p: 0.5
            low = offense.offensive_profile({}, player, traits)["screening"]
            offense._screen_assist_rate = lambda canonical, p: 5.0
            high = offense.offensive_profile({}, player, traits)["screening"]
        finally:
            offense._screen_assist_rate = original
        self.assertLess(low, high)
        self.assertNotEqual(legacy, low)

    def test_screen_assists_need_teammate_baskets_and_are_deterministic(self):
        lines = [{"player_id": "a", "minutes": 36, "fgm": 2}, {"player_id": "b", "minutes": 30, "fgm": 1},
                 {"player_id": "c", "minutes": 0, "fgm": 0}]
        features = {"a": {screens.FEATURE: 40.0}, "b": {screens.FEATURE: 40.0}, "c": {screens.FEATURE: 40.0}}
        first = copy.deepcopy(lines)
        screens.add_screen_assists([first], features, "seed")
        second = copy.deepcopy(lines)
        screens.add_screen_assists([second], features, "seed")
        self.assertEqual(first, second)
        self.assertLessEqual(first[0]["screen_assists"], 1)   # teammates made 1
        self.assertLessEqual(first[1]["screen_assists"], 2)
        self.assertEqual(first[2]["screen_assists"], 0)
        untouched = copy.deepcopy(lines)
        screens.add_screen_assists([untouched], {}, "seed")   # old ratings: no column
        self.assertNotIn("screen_assists", untouched[0])


class ShotDifficultyTests(unittest.TestCase):
    def test_tough_shot_takers_absorb_less_of_the_team_swing(self):
        self.assertEqual(box_variation.team_context_share(None), 1.0)
        tough = box_variation.team_context_share(0.38)
        open_ = box_variation.team_context_share(0.22)
        self.assertLess(tough, 1.0)
        self.assertGreater(open_, 1.0)

    def test_removed_by_weight_is_exact_and_bounded(self):
        rng = random.Random(3)
        for _ in range(300):
            values = [rng.randint(0, 9) for _ in range(rng.randint(1, 9))]
            weights = [v * rng.uniform(0.2, 3.0) for v in values]
            remove = rng.randint(0, sum(values))
            ids = [f"p{i}" for i in range(len(values))]
            out = box_variation.removed_by_weight(values, remove, weights, ids)
            self.assertEqual(sum(values) - sum(out), remove)
            self.assertTrue(all(0 <= o <= v for o, v in zip(out, values)))
            self.assertEqual(out, box_variation.removed_by_weight(values, remove, weights, ids))

    def test_low_difficulty_shooter_loses_more_misses_on_an_efficient_team_night(self):
        values = [10, 10]
        shares = [box_variation.team_context_share(0.22), box_variation.team_context_share(0.38)]
        out = box_variation.removed_by_weight(values, 6, [v * s for v, s in zip(values, shares)], ["open", "tough"])
        self.assertLess(out[0], out[1])


class ReboundTests(unittest.TestCase):
    def test_rebounds_follow_rebounding_skills(self):
        queta = load_league_inputs()[QUETA]
        base = box_rates.rebounds_per36_from_inputs(queta)
        self.assertGreater(base, 8.0)
        for key in ("S30", "S31", "S32"):
            self.assertGreater(box_rates.rebounds_per36_from_inputs(bumped(queta, key, 15)), base)


if __name__ == "__main__":
    unittest.main()
