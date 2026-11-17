"""Search-local memoization must not persist through roster/health/date changes."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from pathlib import Path

from nba_gm_data import transactions as tx, trade_roster as tr


class TradeSearchPerformanceTests(unittest.TestCase):
    def test_candidate_reuses_the_exact_ledger_without_sharing_mutable_chart_data(self):
        report = {'proposal': {}, 'evaluations': [], 'legality': {}, 'accepted_by_all': False,
                  'value_breakdown': {'version': 2, 'example': [10, -3]}}
        with patch.object(tx, 'trade_value_breakdown', side_effect=AssertionError('Ledger recalculated')), \
             patch.object(tx, 'proposal_summary', return_value=''):
            result = tx.candidate_from_evaluation({}, report)
        self.assertEqual(result['value_breakdown'], report['value_breakdown'])
        result['value_breakdown']['example'].append(7)
        self.assertEqual(report['value_breakdown']['example'], [10, -3])

    def test_real_team_forecasts_keep_identical_nonspatial_features_and_rotation_choices(self):
        from nba_gm_data.app_actions import load_app_canonical
        from nba_gm_data import sim
        canonical = load_app_canonical(Path(__file__).resolve().parents[1])
        full = sim.team_feature_vector
        for team in canonical['teams']:
            with self.subTest(team=team['abbrev']):
                quick_rotation = tx.strategic_rotation_view(canonical, team['id'])
                with patch.object(sim, 'team_feature_vector', side_effect=lambda c,t,**kw: full(c,t)):
                    reference_rotation = tx.strategic_rotation_view(canonical, team['id'])
                self.assertEqual(quick_rotation['players'], reference_rotation['players'])
                reference = full(quick_rotation, team).features
                with patch.object(sim, 'player_spatial_profile', side_effect=AssertionError('Unused player heatmap built')), \
                     patch.object(sim, 'team_spatial_profile', side_effect=AssertionError('Unused team heatmap built')):
                    quick = full(quick_rotation, team, include_spatial=False).features
                self.assertEqual(quick, {key: reference[key] for key in quick})
                self.assertEqual(tx.contention_from_features(quick), tx.contention_from_features(reference))
                self.assertFalse(any(key.startswith('sp_') for key in quick))
                self.assertTrue(any(key.startswith('sp_') for key in full(quick_rotation, team).features))

    def fixture(self):
        return {'meta': {'current_date': '2027-02-03'}, 'teams': [{'id': 'a', 'abbrev': 'A'}],
                'players': [{'id': f'p{i}', 'team_id': 'a', 'age': 25, 'position': 'SG', 'name': str(i),
                             'minutes_projection': 25} for i in range(10)],
                'traits': [], 'contracts': [], 'player_asset_valuations': [
                    {'player_id': f'p{i}', 'on_court_value': 80-i, 'player_value': 80-i} for i in range(10)]}

    def test_role_lookup_reuses_only_identical_player_flows_and_returns_independent_results(self):
        source = self.fixture()
        batch = tx.trade_search_context(source)
        assets = [{'kind': 'player', 'id': 'p4'}]
        expected = tx.destination_role_multipliers(source, assets, 'a')
        with patch.object(tx, 'player_asset_values_by_id', wraps=tx.player_asset_values_by_id) as values:
            first = tx.destination_role_multipliers(batch, assets, 'a')
            first['p4'] = -999
            self.assertEqual(tx.destination_role_multipliers(batch, assets, 'a'), expected)
            self.assertEqual(values.call_count, 1)
            changed = tx.destination_role_multipliers(batch, assets, 'a', [{'kind': 'player', 'id': 'p0'}])
            self.assertEqual(values.call_count, 2)
            self.assertEqual(changed, tx.destination_role_multipliers(source, assets, 'a', [{'kind': 'player', 'id': 'p0'}]))
        self.assertNotIn('_trade_search_roles', source)

    def test_forecast_cache_is_local_and_a_new_batch_recomputes_after_settlement(self):
        source = self.fixture()
        pristine = deepcopy(source)
        batch = tx.trade_search_context(source)
        with patch.object(tx, 'strategic_rotation_view', side_effect=lambda c,t:c), \
             patch('nba_gm_data.sim.team_feature_vector', return_value=SimpleNamespace(features={'impact': 70})) as vector:
            first = tr.roster_projection(batch, 'a')
            self.assertEqual(first, tr.roster_projection(batch, 'a'))
            self.assertEqual(vector.call_count, 1)
            tr.roster_projection(batch, 'a', ['p0'])
            self.assertEqual(vector.call_count, 2)
            source['players'][0]['team_id'] = 'b'
            source['traits'].append({'player_id': 'p1', 'trait_key': 'rim_pressure', 'value': 80})
            source['meta']['current_date'] = '2027-02-04'
            later = tx.trade_search_context(source)
            tr.roster_projection(later, 'a')
            self.assertEqual(vector.call_count, 3)
        self.assertEqual(pristine['players'][1:], source['players'][1:])
        self.assertNotIn('_trade_search_rosters', source)

    def test_pick_term_previews_share_player_forecasts_but_new_searches_do_not(self):
        batch = tx.trade_search_context(self.fixture())
        batch['_trade_search_roles']['one'] = {'p0': 1.22}
        # Pick compilation uses a shallow player-context view; no player input changes.
        preview = {**batch, 'pick_obligations': [{'id': 'new-protection'}]}
        self.assertIs(preview['_trade_search_roles'], batch['_trade_search_roles'])
        self.assertEqual(tx.trade_search_context(preview)['_trade_search_roles'], {})


if __name__ == '__main__':
    unittest.main()
