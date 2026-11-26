"""Scalar-only transaction consumers retain full-feature reference results."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from nba_gm_data import sim, spatial, transactions as tx
from nba_gm_data.roster_forecast import ForecastSnapshot
from nba_gm_data.trade_review import MarketReview
from test_multi_team_trades import fixture


def source():
    data = fixture('abcd')
    data['meta'].update(offense_model_version=1, talent_model_version=2)
    data['meta']['offensive_profiles'] = {
        'a0': {'anchors': {'rim_pressure': 65, 'shooting_range': 60}, 'three_per36': 3.5,
               'volume_weight': .75, 'two_pct': .58, 'two_weight': .6}}
    for index, player in enumerate(data['players']):
        player.update(height_inches=72+index%13, weight_lbs=175+index%90)
    return data


class TransactionFeatureDemandTests(unittest.TestCase):
    def test_valuations_and_needs_skip_unused_spatial_expansion(self):
        data = source()
        expected = tx.build_player_asset_valuations(deepcopy(data), _full_features=True)
        team = data['teams'][0]
        players = [p for p in data['players'] if p['team_id'] == team['id']]
        needs = tx.team_needs_and_excesses(deepcopy(data),team,players,'contending',_full_features=True)
        # SIM-SPEED-2: the game's zone grids come from spatial.player_zone_static (minutes-free part) and the lean team
        # grids; the full profiles are display-only.
        with patch.object(sim,'player_spatial_profile',side_effect=AssertionError('Unused player zones')), \
             patch.object(sim,'team_spatial_profile',side_effect=AssertionError('Unused team zones')), \
             patch.object(spatial,'player_zone_static',side_effect=AssertionError('Unused player zones')), \
             patch.object(spatial,'team_zone_grids',side_effect=AssertionError('Unused team zones')):
            self.assertEqual(tx.build_player_asset_valuations(deepcopy(data)), expected)
            self.assertEqual(tx.team_needs_and_excesses(deepcopy(data),team,players,'contending'), needs)

    def test_full_reference_still_prepares_spatial_features_and_matches_fresh_context(self):
        data = source()
        sim._FEATURE_MEMO.clear()   # earlier tests remember these players' minutes-free features (zones included)
        with patch.object(spatial,'player_zone_static',wraps=spatial.player_zone_static) as spatial_calls:
            expected = tx.full_transaction_context_reference(deepcopy(data))
            self.assertGreater(spatial_calls.call_count,0)
        with patch.object(sim,'player_spatial_profile',side_effect=AssertionError('Unused zones in context')), \
             patch.object(spatial,'player_zone_static',side_effect=AssertionError('Unused zones in context')):
            actual = tx.build_transaction_context(deepcopy(data))
        self.assertEqual(actual,expected)

    def test_minutes_roles_trait_zeroes_and_offensive_profiles_preserve_every_scalar_bit(self):
        data = source()
        for row in data['traits'][:15]: row['value'] = 0 if row['trait_key']=='shooting_range' else row['value']+.333333333333
        original = data['players'][0]
        for minutes in (0,6,12,24,31.25,42,2460):
            for role in ('starter','development_priority','actual_boxscore_unmatched'):
                player = dict(original,minutes_projection=minutes,rotation_priority=role,actual_points=27)
                full = sim.player_feature_vector(deepcopy(data),player).features
                lean = sim.player_feature_vector(deepcopy(data),player,include_spatial=False).features
                self.assertEqual(lean,{k:v for k,v in full.items() if not k.startswith('sp_')})
                self.assertEqual({k:float(v).hex() for k,v in lean.items()},
                                 {k:float(full[k]).hex() for k in lean})
                self.assertTrue(any(k.startswith('sp_') for k in full))

    def test_changed_traits_health_rotations_priors_and_ownership_get_fresh_snapshots(self):
        data = source()
        review = MarketReview()
        current = review.prepare(data)
        previous = current['_roster_forecast_snapshot']
        changes = (
            lambda: data['traits'][0].update(value=11.125),
            lambda: data.update(player_health_states=[{'player_id':'a0','availability_status':'out','rust':20}]),
            lambda: data['players'][0].update(minutes_projection=6,rotation_priority='reserve'),
            lambda: data['meta']['offensive_profiles']['a0'].update(three_per36=7),
            lambda: data['players'][0].update(team_id='b'),
        )
        for change in changes:
            change()
            current = review.prepare(data)
            snapshot = current['_roster_forecast_snapshot']
            self.assertIsNot(snapshot,previous)
            self.assertEqual(tx.build_player_asset_valuations(deepcopy(data)),
                             tx.build_player_asset_valuations(deepcopy(data),_full_features=True))
            self.assertEqual(tx.build_transaction_context(deepcopy(data)),tx.full_transaction_context_reference(deepcopy(data)))
            previous = snapshot
        review.close()

    def test_existing_snapshot_cache_separates_full_and_lean_and_keeps_user_minutes(self):
        data = source()
        snapshot = ForecastSnapshot(data)
        for minutes in (0,12,24,42):
            player = dict(data['players'][0],minutes_projection=minutes)
            view = snapshot.view(data,[player])
            full = sim.player_feature_vector(view,player).features
            lean = sim.player_feature_vector(view,player,include_spatial=False).features
            self.assertEqual(lean,{k:v for k,v in full.items() if not k.startswith('sp_')})
            self.assertEqual(player['minutes_projection'],minutes)
        self.assertEqual(len(snapshot.features),8)
        self.assertEqual(data['players'][0]['minutes_projection'],32)


if __name__=='__main__':unittest.main()
