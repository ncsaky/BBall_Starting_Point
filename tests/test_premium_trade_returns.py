from copy import deepcopy
from types import SimpleNamespace as Row
import unittest
from unittest.mock import patch

from nba_gm_data import transactions as tx


class PremiumTradeReturnTests(unittest.TestCase):
    def fixture(self, phase='entering'):
        players, values = [], []
        for pid, tid, age, ability, upside, price in [
            ('star', 'a', 32, 86, 0, 95), ('depth1', 'b', 28, 72, 2, 75),
            ('depth2', 'b', 29, 70, 1, 70), ('peer', 'b', 28, 82, 0, 90),
            ('prospect', 'b', 22, 69, 22, 90)]:
            players.append({'id': pid, 'name': pid, 'team_id': tid, 'age': age,
                            'position': 'SF', 'minutes_projection': 30, 'overall': ability, 'potential': ability+upside})
            values.append({'player_id': pid, 'on_court_value': ability, 'development_upside': upside,
                           'player_value': price, 'playoff_value': 90 if pid == 'star' else 86 if pid == 'peer' else 70,
                           'contract_surplus': 0, 'health_risk': 0})
        return {'players': players, 'player_asset_valuations': values,
                'team_strategic_states': [{'team_id': 'a', 'window_phase': phase, 'phase': 'developing'}],
                'draft_picks': [{'id': f'first{i}', 'round': 1, 'season': '2029', 'current_owner_team_id': 'b',
                                 'projected_pick_slot': 24, '_active_season': '2027-28'} for i in (1, 2)],
                'team_plans': {}}, [{'kind': 'player', 'id': 'star'}]

    def issue(self, data, outgoing, incoming):
        return tx.premium_return_issue(data, 'a', incoming, outgoing)

    def test_competing_seller_rejects_depth_without_a_centerpiece(self):
        data, outgoing = self.fixture()
        incoming = [{'kind': 'player', 'id': p} for p in ('depth1', 'depth2')]
        self.assertIsNotNone(self.issue(data, outgoing, incoming))
        data['team_strategic_states'][0]['window_phase'] = 'peak'
        self.assertIsNotNone(self.issue(data, outgoing, incoming))

    def test_replacement_or_credible_young_centerpiece_is_not_automatically_refused(self):
        data, outgoing = self.fixture()
        for pid in ('peer', 'prospect'):
            self.assertIsNone(self.issue(data, outgoing, [{'kind': 'player', 'id': pid}]))

    def test_valuable_draft_compensation_requires_an_actual_seller_direction(self):
        data, outgoing = self.fixture('exiting')
        picks = [{'kind': 'pick', 'id': f'first{i}'} for i in (1, 2)]
        self.assertIsNone(self.issue(data, outgoing, picks))
        data['team_strategic_states'][0]['window_phase'] = 'entering'
        self.assertIsNotNone(self.issue(data, outgoing, picks))
        data['team_plans']['a'] = {'route': 'review_core_ceiling_and_retool_alternatives'}
        self.assertIsNone(self.issue(data, outgoing, picks))

    def test_protected_low_value_picks_do_not_count_as_substantive_compensation(self):
        data, outgoing = self.fixture('rebuilding')
        for p in data['draft_picks']:
            p['_protection_value_factor'] = .05
        self.assertIsNotNone(self.issue(data, outgoing, [{'kind': 'pick', 'id': p['id']} for p in data['draft_picks']]))

    def test_bad_contract_and_one_way_limitations_are_not_given_a_blanket_star_floor(self):
        data, outgoing = self.fixture()
        before = deepcopy(data)
        data['player_asset_valuations'][0]['contract_surplus'] = -25
        self.assertIsNone(self.issue(data, outgoing, []))
        data = before
        data['player_asset_valuations'][0]['on_court_value'] = 65
        self.assertIsNone(self.issue(data, outgoing, []))

    def test_user_can_control_their_own_assets_and_injury_review_can_pivot(self):
        data, outgoing = self.fixture()
        data['_human_team_ids'] = ['a']
        self.assertIsNone(self.issue(data, outgoing, []))
        data.pop('_human_team_ids')
        data['team_plans']['a'] = {'review_exception': 'serious_core_injury_review',
                                   'injury_review_ids': [a['id'] for a in outgoing]}
        self.assertIsNone(self.issue(data, outgoing, [{'kind': 'pick', 'id': p['id']} for p in data['draft_picks']]))

    def test_positive_additive_value_cannot_override_a_missing_premium_return(self):
        data, outgoing = self.fixture()
        incoming = [{'kind': 'player', 'id': 'depth1'}, {'kind': 'player', 'id': 'depth2'}]
        with patch.object(tx, 'package_value_for_team', side_effect=[200, 100]), \
             patch.object(tx, 'strategic_fit_adjustment', return_value=0), \
             patch.object(tx, 'personality_trade_adjustment', return_value={'total': 0}), \
             patch.object(tx, 'contextual_acceptance_threshold', return_value=1), \
             patch.object(tx, 'evaluation_notes', return_value=''):
            evaluation = tx.evaluate_trade_for_team(data, Row(id='trade'), 'a', incoming, outgoing,
                {'status': 'legal', 'issues': []}, 17, {})
        self.assertFalse(evaluation.accepted)
        self.assertEqual(evaluation.decision, 'reject_premium_return')
        candidate = {'accepted_by_all': False, 'legality': {'status': 'legal'},
                     'proposal': {'from_team_id': 'a', 'to_team_id': 'b', 'from_assets': outgoing, 'to_assets': incoming},
                     'evaluations': [{'decision': evaluation.decision, 'net_value': evaluation.net_value}]}
        self.assertFalse(tx.ai_trade_candidate_accepted(data, candidate))

    def test_guarded_rejection_cannot_be_marked_as_genuine_consent(self):
        candidate = {'accepted_by_all': True, 'legality': {'status': 'legal'},
                     'evaluations': [{'decision': 'reject_premium_return', 'net_value': 100}]}
        self.assertFalse(tx.ai_trade_candidate_accepted({}, candidate))

    def test_nearby_headline_quality_is_not_enough_after_a_large_playoff_drop(self):
        data, outgoing = self.fixture('exiting')
        data['player_asset_valuations'][0].update(on_court_value=83.95, playoff_value=92.01)
        peer = next(v for v in data['player_asset_valuations'] if v['player_id'] == 'peer')
        peer.update(on_court_value=78.55, playoff_value=77.66)
        self.assertIsNotNone(self.issue(data, outgoing, [{'kind': 'player', 'id': 'peer'},
                                                        {'kind': 'player', 'id': 'depth1'}]))
        peer.update(on_court_value=82, playoff_value=88)
        self.assertIsNone(self.issue(data, outgoing, [{'kind': 'player', 'id': 'peer'}]))

    def test_entering_team_cannot_convert_a_prime_starter_into_depth_and_a_late_first(self):
        data, outgoing = self.fixture()
        data['player_asset_valuations'][0].update(on_court_value=68.65, playoff_value=60.56)
        for v in data['player_asset_valuations'][1:]:
            v.update(on_court_value=52, development_upside=3)
        package = [{'kind': 'player', 'id': 'depth1'}, {'kind': 'player', 'id': 'depth2'},
                   {'kind': 'pick', 'id': 'first1'}]
        self.assertIsNotNone(self.issue(data, outgoing, package))
        data['team_strategic_states'][0]['window_phase'] = 'rebuilding'
        self.assertIsNone(self.issue(data, outgoing, package))

    def test_repeating_the_same_pick_does_not_create_substantive_compensation(self):
        data, outgoing = self.fixture('exiting')
        self.assertIsNotNone(self.issue(data, outgoing, [{'kind': 'pick', 'id': 'first1'}]*3))
