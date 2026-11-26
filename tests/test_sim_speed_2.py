"""SIM-SPEED-2: the remembered minutes-free player features, the lean zone grids and the rotation hand-off give exactly
the values the full computations give."""
from copy import deepcopy
import random
import unittest

from nba_gm_data import health, save as save_module, sim, spatial
from test_multi_team_trades import fixture


def source():
    data = fixture('abcd')
    data['meta'].update(offense_model_version=1, talent_model_version=2)
    data['meta']['offensive_profiles'] = {
        'a0': {'anchors': {'rim_pressure': 65, 'shooting_range': 60}, 'three_per36': 3.5,
               'volume_weight': .75, 'two_pct': .58, 'two_weight': .6}}
    for index, player in enumerate(data['players']):
        player.update(height_inches=72 + index % 13, weight_lbs=175 + index % 90, minutes_projection=8 + index % 27)
    return data


def full_fit_delta(canonical, team_id, player, cap=3.0):
    """spatial_fit_delta as it was: from the full team and player profiles."""
    team = spatial.team_spatial_profile(canonical, team_id)
    candidate = spatial.player_spatial_profile(canonical, player)
    pa, ga, aa = spatial._perimeter_average, spatial._group_average, spatial._all_average
    perimeter_need = max(0.0, 58 - pa(team, "offense", "gravity"))
    rim_need = max(0.0, 58 - ga(team, "defense", "suppression", "rim"))
    perimeter_value = pa(candidate, "offense", "gravity") - 50
    rim_value = ga(candidate, "defense", "suppression", "rim") - 50
    value = (perimeter_need * perimeter_value * 0.0045 + rim_need * rim_value * 0.0045
             + max(0.0, 55 - aa(team, "offense", "intensity")) * (aa(candidate, "offense", "intensity") - 50) * 0.0025
             + max(0.0, 55 - aa(team, "defense", "intensity")) * (aa(candidate, "defense", "intensity") - 50) * 0.0025)
    if perimeter_need < 2 and perimeter_value > 18:
        value -= (perimeter_value - 18) * 0.018
    return round(max(-cap, min(cap, value)), 3)


class SimSpeed2Tests(unittest.TestCase):
    def setUp(self):
        sim._FEATURE_MEMO.clear()

    def test_remembered_features_match_a_fresh_computation_as_minutes_change(self):
        data = source()
        rng = random.Random(3)
        for _ in range(4):
            for player in data['players']:
                for include_spatial in (True, False):
                    remembered = sim.player_feature_vector(data, player, include_spatial=include_spatial)
                    fresh = sim._compute_player_feature_vector(data, sim.canonical_sim_cache(data), player, include_spatial)
                    self.assertEqual(remembered, fresh)
                    self.assertEqual(list(remembered.features), list(fresh.features))   # same key order
            for player in data['players']:
                player['minutes_projection'] = round(rng.uniform(0, 40), 2)
            sim.invalidate_sim_cache(data)

    def test_full_profile_grids_equal_the_split_grids(self):
        data = source()
        for player in data['players']:
            profile = spatial.player_spatial_profile(data, player)
            static = spatial.player_zone_static(data, player)
            grids = spatial.player_zone_grids(static, player)
            self.assertEqual(grids['offense'], profile['offense'])
            self.assertEqual(grids['defense'], profile['defense'])
            self.assertEqual(sim.player_zone_grids_for(data, player), grids)

    def test_vector_ignores_the_league_playmaking_baseline(self):
        data = source()
        player = data['players'][0]
        before = sim.player_feature_vector(data, player)
        spatial._PLAYMAKING_MEAN_CACHE.clear()
        for other in data['players'][1:]:
            other['minutes_projection'] = 0   # moves the league baseline
        sim.invalidate_sim_cache(data)
        after = sim.player_feature_vector(data, player)
        self.assertEqual(before, after)
        self.assertEqual(after, sim._compute_player_feature_vector(data, sim.canonical_sim_cache(data), player, True))

    def test_lean_team_grids_equal_the_full_team_profile(self):
        data = source()
        rng = random.Random(5)
        for team in data['teams']:
            roster = [p for p in data['players'] if p['team_id'] == team['id']]
            minutes = {p['id']: round(rng.uniform(4, 38), 2) for p in roster[:8]}
            for args, kw in (((team['id'],), {}), ((team['id'], minutes), {'roster': roster[:8]})):
                full = spatial.team_spatial_profile(data, *args, **kw)
                lean = sim.team_zone_grids(data, *args, **kw)
                self.assertEqual(lean, {'offense': full['offense'], 'defense': full['defense']})

    def test_trade_fit_equals_the_full_profile_fit_for_hypothetical_records(self):
        data = source()
        batch = spatial.with_spatial_fit_context(data)
        for team in data['teams']:
            for player in data['players'][::3]:
                hypothetical = dict(player, team_id=team['id'], minutes_projection=31.5, height_inches=83)
                expected = full_fit_delta(data, team['id'], hypothetical)
                self.assertEqual(spatial.spatial_fit_delta(data, team['id'], hypothetical), expected)
                self.assertEqual(spatial.spatial_fit_delta(batch, team['id'], hypothetical), expected)

    def test_rotation_projection_with_handed_roster_matches_its_own_gathering(self):
        data = source()
        save = {'health_states': [{'player_id': data['players'][1]['id'], 'availability_status': 'out'}],
                'rotation_baselines': {}, 'meta': {'season': '2026-27'}}
        health_by_player = {s.get('player_id'): s for s in save['health_states']}
        for team in data['teams']:
            roster = [p for p in data['players'] if p.get('team_id') == team['id']]
            own = save_module.team_rotation_projection(data, deepcopy(save), team['id'])
            handed = save_module.team_rotation_projection(data, deepcopy(save), team['id'], _roster=roster,
                                                          _health_by_player=health_by_player)
            self.assertEqual(own, handed)

    def test_parse_date_is_remembered_and_unchanged(self):
        self.assertEqual(health.parse_date('2028-11-03T19:30:00'), health.parse_date('2028-11-03'))
        self.assertEqual(health.parse_date('2028-11-03').isoformat(), '2028-11-03')
        with self.assertRaises(ValueError):
            health.parse_date('2028-13-03')


if __name__ == '__main__':
    unittest.main()
