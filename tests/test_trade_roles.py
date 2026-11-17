from copy import deepcopy
import unittest

from nba_gm_data import transactions as tx


class TradeRoleTests(unittest.TestCase):
    def fixture(self):
        players = [{'id': p, 'name': p, 'team_id': 'a', 'age': 25, 'position': 'SG', 'minutes_projection': minutes}
                   for p, minutes in [('p', 35), ('q', 32), ('r', 29)]]
        return {'players': players, 'player_asset_valuations': [
            {'player_id': p, 'player_value': value, 'on_court_value': value}
            for p, value in [('p', 90), ('q', 85), ('r', 80)]]}

    def test_owned_package_is_counted_once_when_assessing_current_roles(self):
        data = self.fixture()
        assets = [{'kind': 'player', 'id': p} for p in ('p', 'q', 'r')]
        before = deepcopy(data)
        self.assertEqual(tx.destination_role_multipliers(data, assets, 'a'),
                         tx.destination_role_multipliers(data, assets, 'a', assets))
        self.assertEqual(tx.destination_role_multipliers(data, assets, 'a')['r'],
                         round((29/28)**1.8, 3))
        self.assertEqual(data, before)

    def test_role_uses_basketball_ability_not_cheap_contract_or_future_promise(self):
        data = self.fixture()
        data['players'].append({'id': 'star', 'name': 'Star', 'team_id': 'b', 'age': 32,
                                'position': 'SG', 'minutes_projection': 35})
        data['player_asset_valuations'].append({'player_id': 'star', 'on_court_value': 95, 'player_value': 60})
        assets = [{'kind': 'player', 'id': 'star'}]
        self.assertEqual(tx.destination_role_multipliers(data, assets, 'a')['star'], 1.22)

    def test_incoming_package_replaces_outgoing_players_before_role_ranking(self):
        data = self.fixture()
        data['players'].append({'id': 'new', 'name': 'New', 'team_id': 'b', 'age': 25,
                                'position': 'SG', 'minutes_projection': 29})
        data['player_asset_valuations'].append({'player_id': 'new', 'on_court_value': 82, 'player_value': 82})
        assets = [{'kind': 'player', 'id': 'new'}]
        result = tx.destination_role_multipliers(data, assets, 'a', [{'kind': 'player', 'id': 'p'}])
        self.assertEqual(result['new'], 1.22)

    def test_order_and_missing_legacy_on_court_field_do_not_break_ranking(self):
        data = self.fixture()
        for value in data['player_asset_valuations']:
            value.pop('on_court_value')
        assets = [{'kind': 'player', 'id': p} for p in ('p', 'q', 'r')]
        expected = tx.destination_role_multipliers(data, assets, 'a')
        self.assertEqual(tx.destination_role_multipliers(data, list(reversed(assets)), 'a'), expected)
