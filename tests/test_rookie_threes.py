"""ROOKIE-THREES: generated players take their habits from the real players nearest them, like their skills.

Before, every habit but involvement started from a fixed role guess (three share .38 for any guard or wing), which left
generated guards and wings about five points short of real players of their type on threes, so the league's three
share slid as they replaced the opening-day players."""
from __future__ import annotations

import json
import statistics
import unittest
from pathlib import Path

from nba_gm_data import bbi_evidence
from nba_gm_data.box_rates import flatten_inputs
from nba_gm_data.input_estimator import (UNIVERSE_PATH, InputEstimator, _position, _real_reference_players)

ROOT = Path(__file__).resolve().parents[1]


def fictional(pid='generated_player_rt', position='SG', ability=48.0, **kwargs):
    return dict(id=pid, name=pid, position=position, source_kind='generated_rookie', draft_year='2028',
                current_ability=ability, potential=70, primary_off_role='wing', height_inches=78, weight_lbs=210,
                **kwargs)


class GeneratedHabitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = json.loads((ROOT / UNIVERSE_PATH).read_text())
        cls.legacy_keys = sorted({t['trait_key'] for t in base['traits']})
        cls.real = _real_reference_players(str(ROOT))

    def flat(self, player, traits):
        return flatten_inputs(InputEstimator().estimate_player_inputs(player, traits, prospect=True).to_dict()['inputs'])

    def real_mean(self, key, position, low, high):
        values = [flatten_inputs(inputs).get(key) for _, p, ability, _, inputs in self.real
                  if _position(p) == position and low <= ability < high]
        return statistics.mean(v for v in values if v is not None)

    def typical_traits(self, position, ability):
        """The average legacy profile of real players at this position and about this ability."""
        rows = [traits for _, p, a, traits, _ in self.real if _position(p) == position and abs(a - ability) <= 4]
        return {k: statistics.mean(t.get(k, ability + 7) for t in rows) for k in self.legacy_keys}

    def generated_mean(self, key, position_code, low, high):
        position = _position(dict(position=position_code))
        values = []
        for i, ability in enumerate(range(int(low), int(high))):
            traits = self.typical_traits(position, ability)
            values.append(self.flat(fictional(f'generated_player_rt_{position_code}_{i}', position_code, float(ability)),
                                    traits)[key])
        return statistics.mean(values)

    def test_generated_guards_and_wings_shoot_threes_like_real_players_of_their_type(self):
        # The old role guess gave .38 for every guard or wing; real guards and wings at rookie abilities take about
        # 44% of their shots from three.
        for position, code in (('guard', 'SG'), ('wing', 'SF'), ('big', 'C')):
            real = self.real_mean('T02.three', position, 40, 56)
            generated = self.generated_mean('T02.three', code, 40, 56)
            self.assertLess(abs(generated - real), .04, (position, generated, real))

    def test_turnover_habits_match_real_players_of_their_type(self):
        # Dribble persistence (T06) was .38 for every non-"creator"; real guards hold the ball far longer (about .55).
        for key in ('T06', 'T07', 'T01.pass'):
            real = self.real_mean(key, 'guard', 40, 56)
            generated = self.generated_mean(key, 'SG', 40, 56)
            self.assertLess(abs(generated - real) / real, .12, (key, generated, real))

    def test_shooting_profile_still_separates_generated_players(self):
        traits = {k: 55 for k in self.legacy_keys}
        shooter = self.flat(fictional('generated_player_rt_a'), dict(traits, shooting_range=85))
        slasher = self.flat(fictional('generated_player_rt_b'), dict(traits, shooting_range=30, rim_pressure=80))
        self.assertGreater(shooter['T02.three'], slasher['T02.three'] + .10)
        self.assertGreater(slasher['T02.rim'], shooter['T02.rim'])

    def test_measured_scale_habits_are_not_translated_twice(self):
        traits = {k: 55 for k in self.legacy_keys}
        inputs = InputEstimator().estimate_player_inputs(fictional(), traits, prospect=True).to_dict()['inputs']
        before = json.loads(json.dumps(inputs))
        scale_map = bbi_evidence.load_scale_map(ROOT)
        self.assertIsNotNone(scale_map)
        bbi_evidence.map_tendency_inputs(inputs, scale_map)
        # The action mix and transition share already come from real players' measured habits.
        self.assertEqual(inputs['T01'], before['T01'])
        self.assertEqual(inputs['T17'], before['T17'])
        # Involvement is still built on the estimator's scale and translated.
        self.assertNotEqual(inputs['T08']['value'], before['T08']['value'])

    def test_real_prospect_path_is_untouched(self):
        # A real, non-generated rookie (the 2026 class path) keeps its own estimate and is still translated.
        real_rookie = dict(id='rookie_rt', name='Rookie RT', position='SG', espn_player_id='rookie_rt',
                           source_kind='generated_rookie', draft_year='2026')
        inputs = InputEstimator().estimate_player_inputs(real_rookie, {}, prospect=True).to_dict()['inputs']
        self.assertNotEqual(inputs['T01'].get('reason'), 'generated')
        before = json.loads(json.dumps(inputs['T01']))
        bbi_evidence.map_tendency_inputs(inputs, bbi_evidence.load_scale_map(ROOT))
        self.assertNotEqual(inputs['T01'], before)


if __name__ == '__main__':
    unittest.main()
