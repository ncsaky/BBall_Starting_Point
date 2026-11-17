from copy import deepcopy
import json
from pathlib import Path
import random
import unittest

from nba_gm_data.offense import (
    FACETS, build_priors, finishing_multiplier, offensive_profile, shooting_line,
    team_contribution, valuation_adjustment,
)
from nba_gm_data.save import player_attribute_summary, player_display_attribute_summary
from nba_gm_data.sim import player_feature_vector, scoring_weight
from nba_gm_data.transactions import player_on_court_value
from nba_gm_data.traits import TRAIT_LABELS

ROOT = Path(__file__).resolve().parents[1]


def fixture(values=None, prior=None):
    player = {'id': 'test', 'position': 'C', 'name': 'Test Center', 'height_inches': 84,
              'weight_lbs': 260, 'age': 25, 'minutes_projection': 30}
    traits = {key: 50 for key in TRAIT_LABELS}
    traits.update(values or {})
    canonical = {'meta': {'offense_model_version': 1, 'talent_model_version': 2,
                          'offensive_profiles': {'test': prior or {}}},
                 'players': [player], 'traits': [{'player_id': 'test', 'trait_key': k, 'value': v}
                                               for k, v in traits.items()], '_allow_internal_caches': True}
    return canonical, player, traits


class OffensiveRolesTests(unittest.TestCase):
    def test_replay_isolation_resolves_sqlite_file_uris(self):
        from verify_offensive_roles import local_read_path
        path = ROOT/'output/a save.history.sqlite3'
        self.assertEqual(local_read_path(path.as_uri()+'?mode=ro'), path.resolve())
        self.assertEqual(local_read_path(str(path)), path.resolve())

    def test_post_and_roll_are_distinct_not_synonyms(self):
        base = {'post_share': .3, 'roll_share': .02, 'post_ppp': 1.3, 'roll_ppp': .8, 'playtype_weight': .35}
        c, p, t = fixture(prior=base)
        post = offensive_profile(c, p, t)
        c['meta']['offensive_profiles']['test'] = {**base, 'post_share': .02, 'roll_share': .3,
                                                  'post_ppp': .8, 'roll_ppp': 1.3}
        roll = offensive_profile(c, p, t)
        self.assertGreater(post['post_creation'], roll['post_creation'])
        self.assertGreater(roll['assisted_finishing'], post['assisted_finishing'])
        self.assertGreater(post['post_share'], roll['post_share'])
        self.assertGreater(roll['roll_share'], post['roll_share'])

    def test_promise_does_not_buy_current_offense_and_growth_is_not_frozen(self):
        c, p, t = fixture(prior={'anchors': {key: 50 for key in TRAIT_LABELS},
                                'two_pct': .6, 'two_weight': .7, 'three_per36': 0, 'volume_weight': .98})
        before = offensive_profile(c, p, t)
        p['potential'] = 99
        self.assertEqual(before, offensive_profile(c, p, t))
        grown = offensive_profile(c, p, {**t, 'rim_pressure': 70, 'shooting_range': 70})
        self.assertGreater(grown['assisted_finishing'], before['assisted_finishing'])
        self.assertGreater(grown['three_per36'], before['three_per36'])
        self.assertGreater(grown['two_pct'], before['two_pct'])

    def test_actual_generated_class_keeps_weaknesses_and_overalls(self):
        from test_talent_balance import converted
        _, canonical = converted(seed=29)
        before = deepcopy(canonical['traits'])
        overalls = {p['id']: player_attribute_summary(canonical, p['id'])['overall']
                    for p in canonical['players']}
        canonical['meta']['offense_model_version'] = 1
        profiles = []
        for player in canonical['players']:
            self.assertEqual(overalls[player['id']], player_attribute_summary(canonical, player['id'])['overall'])
            profiles.append(player_feature_vector(canonical, player).features)
        self.assertEqual(before, canonical['traits'])
        self.assertGreater(sum(p['three_per36'] < .25 for p in profiles), 5)
        self.assertGreater(len({round(p['post_creation']) for p in profiles}), 10)

    def test_offensive_rebounding_and_screening_reach_offense_and_ai(self):
        low, p, t = fixture({'offensive_rebounding': 20, 'scheme_iq': 20})
        high, _, _ = fixture({'offensive_rebounding': 80, 'scheme_iq': 80})
        a = player_feature_vector(low, p).features
        b = player_feature_vector(high, p).features
        self.assertGreater(b['screening'], a['screening'])
        self.assertGreater(player_attribute_summary(high, p['id'])['offense'],
                           player_attribute_summary(low, p['id'])['offense'])
        self.assertGreater(valuation_adjustment(b), valuation_adjustment(a))
        self.assertGreater(player_on_court_value(b, 50), player_on_court_value(a, 50))
        self.assertEqual(team_contribution({'offense_model_version': 1, 'offensive_rebounding': 20}),
                         team_contribution({'offense_model_version': 1, 'offensive_rebounding': 90}))

    def test_feeder_matters_without_changing_the_minute_penalty(self):
        c, p, t = fixture({'rim_pressure': 80})
        feat = player_feature_vector(c, p).features
        self.assertGreater(finishing_multiplier(feat, 85), finishing_multiplier(feat, 35))
        legacy = {k: v for k, v in feat.items() if k != 'offense_model_version'}
        ratio = lambda f: scoring_weight({'player': p, 'minutes': 12}, f)/scoring_weight({'player': p, 'minutes': 30}, f)
        self.assertAlmostEqual(ratio(feat), ratio(legacy))

    def test_generated_nonshooters_do_not_gain_a_three_point_attempt_floor(self):
        c, p, t = fixture({'shooting_range': 10})
        feat = offensive_profile(c, p, t)
        self.assertEqual(feat['three_per36'], 0)
        for seed in range(30):
            line = shooting_line(12, feat, 30, random.Random(seed))
            self.assertEqual(line['fg3a'], 0)
            self.assertEqual(line['fg3m'], 0)

    def test_profile_shooting_preserves_points_and_legal_stat_identities(self):
        c, p, t = fixture({'rim_pressure': 80, 'shooting_range': 80})
        feat = offensive_profile(c, p, t)
        for points in range(56):
            for minutes in (0, 12, 30, 42):
                line = shooting_line(points, feat, minutes, random.Random(f'{points}:{minutes}'))
                self.assertEqual(points, line['fgm']*2+line['fg3m']+line['ftm'])
                self.assertLessEqual(line['fg3m'], line['fg3a'])
                self.assertLessEqual(line['fgm'], line['fga'])
                self.assertLessEqual(line['ftm'], line['fta'])
                self.assertTrue(all(isinstance(v, int) and v >= 0 for v in line.values()))

    def test_facets_share_the_display_transform_but_overall_is_unchanged(self):
        c, p, t = fixture()
        old = deepcopy(c)
        old['meta'].pop('offense_model_version')
        self.assertEqual(player_attribute_summary(c, p['id'])['overall'],
                         player_attribute_summary(old, p['id'])['overall'])
        attrs = player_display_attribute_summary(c, p['id'])
        self.assertTrue(all(1 <= attrs[k] <= 99 for k in (*FACETS, 'offense')))
        self.assertNotIn('post_creation', player_attribute_summary(old, p['id']))

    def test_bad_or_missing_evidence_never_means_confirmed_nonshooter(self):
        p = {'id': 'p', 'espn_player_id': '123', 'name': 'Test'}
        row = {'season': '2025-26', 'games': 40, 'minutes': 900,
               'source_url': 'https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/123/stats'}
        records = {'players': {'123': {'espn_player_id': '123', 'seasons': [row]}}}
        self.assertNotIn('three_per36', build_priors([p], [], records, [])['p'])
        row.update(fg3a=0, fg3m=0)
        profile = build_priors([p], [], records, [])['p']
        self.assertEqual(profile['three_per36'], 0)
        self.assertNotIn('three_pct', profile)
        for updates in ({'fg3a': float('nan')}, {'minutes': float('inf')},
                        {'source_url': 'college'}, {'season': '2026-27'}):
            bad = deepcopy(records)
            bad['players']['123']['seasons'][0].update(updates)
            output = build_priors([p], [], bad, [])
            self.assertTrue('p' not in output or 'three_per36' not in output['p'])


if __name__ == '__main__':
    unittest.main()
