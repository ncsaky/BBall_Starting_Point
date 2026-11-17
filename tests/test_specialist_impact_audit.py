"""Audit integrity, not permanent assertions that existing balance is correct."""
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest

from audit_specialist_impact import make_lineup, observed_samples, per36, probe
from nba_gm_data.sim import distribute_player_lines

ROOT = Path(__file__).resolve().parents[1]


class SpecialistImpactAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT/'data/canonical/universe_2026_27_offseason.json').open() as handle:
            cls.canonical = json.load(handle)

    def test_fixed_rotations_are_unique_complete_and_health_neutral(self):
        for target, guard in (('Zach Edey', False), ('Jamal Shead', True)):
            local, pool = make_lineup(self.canonical, target, guard=guard)
            self.assertEqual(sum(i['minutes'] for i in pool), 240)
            self.assertEqual(pool[0]['minutes'], 30)
            self.assertEqual(len({i['player']['id'] for i in pool}), len(pool))
            self.assertTrue(all(i['player']['age'] == 27 for i in pool))
            self.assertEqual(local['player_health_states'], [])
            self.assertTrue(all(i['player']['team_id'] == 'audit_home' for i in pool))

    def test_minutes_move_only_between_centers_without_changing_total(self):
        for minutes in (12, 18, 24, 30, 36):
            _, pool = make_lineup(self.canonical, 'Deandre Ayton', target_minutes=minutes)
            self.assertEqual(sum(i['minutes'] for i in pool), 240)
            self.assertEqual(pool[0]['minutes'], minutes)
            self.assertEqual(pool[-1]['minutes'], 48-minutes)
            self.assertEqual(pool[0]['player']['minutes_projection'], minutes)
        with self.assertRaises(ValueError):
            make_lineup(self.canonical, 'Deandre Ayton', target_minutes=48)

    def test_trait_intervention_is_local_and_has_exactly_one_change(self):
        local, _ = make_lineup(self.canonical, 'Zach Edey')
        before = deepcopy(local)
        changed, _ = make_lineup(self.canonical, 'Zach Edey',
                                  overrides={'Zach Edey': {'offensive_rebounding': 20}})
        changes = [(a, b) for a, b in zip(local['traits'], changed['traits'], strict=True) if a != b]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0][1]['value'], 20)
        self.assertEqual(changes[0][0]['trait_key'], 'offensive_rebounding')
        self.assertEqual(local, before)
        original = next(t for t in self.canonical['traits'] if t['id'] == changes[0][0]['id'])
        self.assertEqual(original, changes[0][0])

    def test_repeat_probe_is_deterministic_and_does_not_mutate_inputs(self):
        before = json.dumps(self.canonical, sort_keys=True)
        first = probe(self.canonical, 'Zach Edey', 4)
        self.assertEqual(first, probe(self.canonical, 'Zach Edey', 4))
        self.assertEqual(first['minutes'], 30)
        self.assertEqual(first['trials'], 4)
        self.assertEqual(before, json.dumps(self.canonical, sort_keys=True))
        with self.assertRaises(ValueError):
            probe(self.canonical, 'Zach Edey', 1)

    def test_real_scoring_path_preserves_totals_and_shooting_identity(self):
        local, pool = make_lineup(self.canonical, 'Zach Edey')
        for seed in range(8):
            lines = distribute_player_lines(local, {'id': 'audit_home', 'abbrev': 'AUH'},
                                            pool, 114, 100, random.Random(seed))
            self.assertEqual(sum(row['minutes'] for row in lines), 240)
            self.assertEqual(sum(row['points'] for row in lines), 114)
            for row in lines:
                self.assertEqual(row['points'], 2*row['fgm']+row['fg3m']+row['ftm'])
                self.assertLessEqual(row['fg3m'], row['fg3a'])
                self.assertLessEqual(row['fgm'], row['fga'])

    def test_per36_uses_minutes_not_games_and_missing_minutes_are_not_zero_skill(self):
        row = per36({'minutes': 180, 'games': 99, 'points': 50, 'assists': 10})
        self.assertEqual(row['points'], 10)
        self.assertEqual(row['assists'], 2)
        self.assertIsNone(row['fg3a'])
        self.assertIsNone(per36({'minutes': 0, 'points': 0}))

    def test_observed_identity_and_source_are_checked(self):
        with (ROOT/'data/research/player_career_stats.json').open() as handle:
            careers = json.load(handle)
        with (ROOT/'Player Stats/player_skill_input_2025_26.json').open() as handle:
            raw = json.load(handle)
        rows = observed_samples(self.canonical, careers, raw)
        edey = next(r for r in rows if r['name'] == 'Zach Edey')
        self.assertEqual({r['season'] for r in edey['nba_seasons']}, {'2024-25', '2025-26'})
        careers['players']['4600663']['espn_player_id'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            observed_samples(self.canonical, careers, raw)


if __name__ == '__main__':
    unittest.main()
