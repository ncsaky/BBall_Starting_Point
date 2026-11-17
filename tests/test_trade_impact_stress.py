from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nba_gm_data import transactions as tx, save as sv, play
from audit_trade_stress import SearchObserver, package_shape


class StrategicRotationTests(unittest.TestCase):
    def fixture(self):
        return {'meta': {}, 'teams': [{'id': 'a', 'abbrev': 'A'}], 'players': [
            {'id': str(i), 'name': str(i), 'team_id': 'a', 'age': 27,
             'position': ('PG', 'SG', 'SF', 'PF', 'C')[i % 5],
             'minutes_projection': 40-i*3} for i in range(12)], 'traits': []}

    def attrs(self, data, pid):
        return {'overall': 90-int(pid)*3, 'defense': 70, 'passing': 70}

    def vector(self, data, team, **kwargs):
        players = data['players']
        quality = sum((90-int(p['id'])*3)*p['minutes_projection'] for p in players)/240
        return SimpleNamespace(features={k: quality for k in ('impact', 'star_power', 'defense_total', 'primary_creator')})

    def test_forecast_does_not_use_old_team_minutes_or_mutate_them(self):
        data = self.fixture()
        before = deepcopy(data)
        with patch.object(sv, 'player_attribute_summary', side_effect=self.attrs), \
             patch('nba_gm_data.sim.team_feature_vector', side_effect=self.vector):
            first = tx.strategic_rotation_view(data, 'a')
            self.assertEqual(data, before)
            for p in data['players']:
                p['minutes_projection'] = 0 if int(p['id']) < 5 else 40
            second = tx.strategic_rotation_view(data, 'a')
        self.assertEqual(first['players'], second['players'])
        self.assertAlmostEqual(sum(p['minutes_projection'] for p in first['players']), 240)
        self.assertTrue(all(p['minutes_projection'] <= 42 for p in first['players']))
        self.assertEqual(before['players'][0]['minutes_projection'], 40)
        self.assertEqual(data['players'][0]['minutes_projection'], 0)

    def test_unused_reserve_and_retired_player_do_not_dilute_the_forecast(self):
        data = self.fixture()
        with patch.object(sv, 'player_attribute_summary', side_effect=self.attrs), \
             patch('nba_gm_data.sim.team_feature_vector', side_effect=self.vector):
            first = tx.contention_ceiling(data, data['teams'][0], [])
            data['players'].append(dict(data['players'][0], id='100', minutes_projection=42))
            data['players'].append(dict(data['players'][0], id='101', _inactive_player=True))
            second = tx.contention_ceiling(data, data['teams'][0], [])
        self.assertEqual(first, second)


class ScopedTradeSearchTests(unittest.TestCase):
    def test_unrelated_buyers_do_not_consume_the_incoming_search_budget(self):
        data = {'players': [{'id': 'p', 'team_id': 'a', 'name': 'P'}],
                'trade_block_entries': [{'player_id': 'p', 'block_score': 90}]}
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c, *_: c), \
             patch.object(tx, 'with_spatial_fit_context', side_effect=lambda c: c), \
             patch.object(tx, 'recently_traded_player_ids', return_value=set()), \
             patch.object(tx, 'team_by_id', side_effect=lambda c, tid: {'id': tid, 'abbrev': tid}), \
             patch.object(tx, 'buyer_teams_for_player', return_value=[{'id': str(i)} for i in range(25)]+[{'id': 'human'}]), \
             patch.object(tx, 'buyer_offer_package_options', return_value=[]) as packages:
            tx.simulate_ai_trades(data, '2027-07-01', '2027-07-01', involving_team_ids={'human'})
        self.assertEqual(packages.call_count, 1)
        self.assertEqual(packages.call_args.args[1]['id'], 'human')

    def test_summer_inbound_search_is_scoped_and_cannot_auto_apply(self):
        saved = {'state': {'current_date': '2027-07-01'}, 'meta': {'user_team_id': 'human'}}
        with patch('nba_gm_data.trade_calendar.summer_offer_slots', return_value=3), \
             patch.object(tx, 'simulate_ai_trades', return_value={'proposals': []}) as search, \
             patch.object(play, 'apply_trade_to_state') as apply:
            self.assertEqual(play.queue_summer_trade_offers({}, saved, 17), 0)
        self.assertEqual(search.call_args.kwargs['involving_team_ids'], {'human'})
        self.assertEqual(search.call_args.kwargs['search_depth'], 2)
        apply.assert_not_called()


class StressHarnessTests(unittest.TestCase):
    def test_pressure_changes_opportunities_not_consent(self):
        with tempfile.TemporaryDirectory() as td:
            observer = SearchObserver(Path(td), pressure=3)
            observer.original_day = lambda *a: {'review': True, 'slots': 12, 'offer_slots': 2}
            self.assertEqual(observer.day(), {'review': True, 'slots': 36, 'offer_slots': 6})
            observer.original_day = lambda *a: {'review': False, 'slots': 0}
            self.assertEqual(observer.day(), {'review': False, 'slots': 0})
            original = {'accepted_by_all': False, 'proposal': {'from_assets': [{'kind': 'player'}],
                        'to_assets': [{'kind': 'pick_swap'}]}, 'legality': {'issues': ['salary']},
                        'evaluations': [{'decision': 'reject'}]}
            observer.original_evaluate = lambda: original
            self.assertIs(observer.evaluate(), original)
            self.assertEqual(observer.swap_packages, 1)
            self.assertEqual(observer.issues['salary'], 1)
            self.assertEqual(package_shape(original), '1 pick_swap+1 player')


if __name__ == '__main__':
    unittest.main()
