import unittest
from unittest.mock import patch
from types import SimpleNamespace

from nba_gm_data import transactions as tx
from nba_gm_data.transactions import player_trade_value_components


class TradePresentationTests(unittest.TestCase):
    def test_meter_uses_the_actual_deal_threshold_not_the_generic_threshold(self):
        from nba_gm_data.schema import TradeEvaluation
        evaluation = TradeEvaluation('e', 'p', 'a', True, 'accept', 12, 10, 1.0, 'legal', [], {'total': -1}, '',
                                     acceptance_threshold=.8)
        with patch.object(tx, 'acceptance_threshold', return_value=2), \
             patch.object(tx, 'team_by_id', return_value={'abbrev': 'A'}):
            result = tx.trade_evaluation_payload({}, evaluation, {})
        self.assertEqual(result['acceptance_threshold'], .8)
        self.assertGreater(result['acceptance_score'], 50)

    def test_package_explanation_matches_engine_including_health_retention_and_outgoing_roles(self):
        data = {'players': [{'id': 'p', 'team_id': 'b', 'name': 'P'}, {'id': 'old', 'team_id': 'a'}],
                'player_asset_valuations': [{'player_id': 'p', 'player_value': 80, 'on_court_value': 70,
                                            'age_curve': 7, 'contract_surplus': 8, 'health_risk': 20}],
                'team_strategic_states': [{'team_id': 'a', 'phase': 'developing'}]}
        assets = [{'kind': 'player', 'id': 'p'}]
        outgoing = [{'kind': 'player', 'id': 'old'}]
        with patch.object(tx, 'market_trade_target_value', return_value=80), \
             patch.object(tx, 'team_fit_for_player', return_value=3), \
             patch.object(tx, 'destination_role_multipliers', return_value={'p': .7}) as roles, \
             patch.object(tx, 'recently_acquired_player_premium', return_value=4):
            engine = tx.package_value_for_team(data, assets, 'a', outgoing)
            shown = tx.package_value_breakdown(data, assets, 'a', outgoing)
        self.assertEqual(roles.call_args.args[-1], outgoing)
        self.assertAlmostEqual(shown['total'], engine, places=2)
        asset = shown['asset_details'][0]
        self.assertAlmostEqual(sum(asset['components'].values()), asset['adjusted_value'], places=1)
        self.assertEqual(asset['listed_value'], 80)

    def test_player_components_reconcile_to_destination_value(self):
        player_value = 82.0
        fit = 4.0
        multiplier = 1.08
        components = player_trade_value_components(
            {
                "on_court_value": 72.0,
                "age_curve": 5.0,
                "development_upside": 4.0,
                "contract_surplus": 7.0,
                "role_scarcity": 3.0,
                "playoff_value": 60.0,
                "health_risk": 6.0,
            },
            player_value,
            fit,
            multiplier,
        )

        self.assertAlmostEqual(sum(components.values()), (player_value + fit) * multiplier, places=1)
        self.assertLess(components["health"], 0.0)
        self.assertGreater(components["fit"], 0.0)


if __name__ == "__main__":
    unittest.main()
