from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nba_gm_data import trade_roster as tr, transactions as tx


class TradeRosterTests(unittest.TestCase):
    def fixture(self):
        return {'meta': {'current_date': '2027-02-01', 'active_season': '2026-27'},
                'teams': [{'id': 'a', 'abbrev': 'A'}],
                'players': [{'id': str(i), 'team_id': 'a', 'age': 27, 'position': 'C', 'name': str(i)} for i in range(10)],
                'traits': [], 'contracts': [], 'team_plans': {},
                'team_strategic_states': [{'team_id': 'a', 'phase': 'contending', 'window_phase': 'peak'}],
                'player_asset_valuations': []}

    def forecast(self, data, *, delta=-1.4, cuts=(), baseline_cuts=(), incoming=None, outgoing=None):
        before = {'strength': 74, 'cuts': list(baseline_cuts), 'rotation': {}, 'retained_ids': []}
        after = {'strength': 74+delta, 'cuts': list(cuts), 'rotation': {}, 'retained_ids': []}
        with patch.object(tr, 'roster_projection', side_effect=[before, after]):
            return tr.trade_roster_outlook(data, 'a', incoming or [{'kind': 'player', 'id': 'new'}],
                                          outgoing or [{'kind': 'player', 'id': '0'}])

    def test_competing_rotation_loss_is_not_excused_by_a_positive_asset_sum(self):
        result = self.forecast(self.fixture())
        self.assertIsNotNone(result['issue'])
        self.assertAlmostEqual(result['adjustment'], -5.6)

    def test_small_loss_rebuilder_and_deliberate_retool_are_not_blanket_vetoes(self):
        data = self.fixture()
        self.assertIsNone(self.forecast(data, delta=-.3)['issue'])
        data['team_strategic_states'][0].update(phase='rebuilding', window_phase='rebuilding')
        self.assertIsNone(self.forecast(data)['issue'])
        data = self.fixture(); data['team_plans']['a'] = {'route': 'review_core_ceiling_and_retool_alternatives'}
        self.assertIsNone(self.forecast(data)['issue'])
        data['team_plans']['a'] = {'review_exception': 'serious_core_injury_review'}
        self.assertIsNone(self.forecast(data)['issue'])

    def test_financial_exit_requires_an_actual_costly_contract_and_material_relief(self):
        data = self.fixture(); data['player_asset_valuations'] = [{'player_id': '0', 'contract_surplus': -25}]
        with patch.object(tx, 'package_salary', side_effect=[20_000_000, 10_000_000]):
            self.assertIsNone(self.forecast(data)['issue'])
        with patch.object(tx, 'package_salary', side_effect=[20_000_000, 19_000_000]):
            self.assertIsNotNone(self.forecast(data)['issue'])
        data['player_asset_valuations'].append({'player_id': '1', 'on_court_value': 90})
        with patch.object(tx, 'package_salary', side_effect=[30_000_000, 10_000_000]):
            self.assertIsNotNone(self.forecast(data, outgoing=[{'kind': 'player', 'id': p} for p in ('0', '1')])['issue'])

    def test_entering_team_can_take_a_short_term_step_back_for_a_credible_young_foundation(self):
        data = self.fixture(); data['team_strategic_states'][0]['window_phase'] = 'entering'
        data['players'].append({'id': 'new', 'team_id': 'b', 'age': 22})
        data['player_asset_valuations'] = [{'player_id': '0', 'on_court_value': 80, 'player_value': 90},
            {'player_id': 'new', 'on_court_value': 65, 'player_value': 75, 'development_upside': 18}]
        self.assertIsNone(self.forecast(data)['issue'])
        data['team_strategic_states'][0]['window_phase'] = 'peak'
        self.assertIsNotNone(self.forecast(data)['issue'])

    def test_incoming_player_who_will_be_cut_has_no_retained_asset_credit(self):
        cut = {'id': 'new', 'name': 'New', 'team_id': 'a'}
        debt = {'remaining_cost_millions': 10, 'unquantified': False}
        with patch.object(tx, 'package_value_for_team', side_effect=[30, 0]), \
             patch('nba_gm_data.contract_protection.waiver_projection', return_value=debt):
            result = self.forecast(self.fixture(), delta=0, cuts=[cut])
        self.assertEqual(result['discarded_incoming_ids'], ['new'])
        self.assertEqual(result['lost_asset_credit'], 30)
        self.assertEqual(result['waiver_cost_millions'], 10)
        self.assertAlmostEqual(result['adjustment'], -31.6)

    def test_existing_required_cuts_are_not_charged_again(self):
        cut = {'id': '9', 'name': 'Nine'}
        with patch('nba_gm_data.contract_protection.waiver_projection') as debt:
            result = self.forecast(self.fixture(), delta=0, cuts=[cut], baseline_cuts=[cut])
        debt.assert_not_called()
        self.assertEqual(result['waiver_cost_millions'], 0)

    def test_unquantified_new_cut_fails_closed(self):
        with patch.object(tx, 'package_value_for_team', return_value=1), \
             patch('nba_gm_data.contract_protection.waiver_projection', return_value={'remaining_cost_millions': 0, 'unquantified': True}):
            self.assertIn('unresolved', self.forecast(self.fixture(), delta=0, cuts=[{'id': '9'}])['issue'])

    def test_runtime_cache_is_bounded_and_reacts_to_ownership_and_salary_changes(self):
        data = self.fixture(); data['_allow_internal_caches'] = True
        original = deepcopy(data['players'])
        with patch.object(tx, 'strategic_rotation_view', side_effect=lambda c,t:c), \
             patch('nba_gm_data.sim.team_feature_vector', return_value=SimpleNamespace(features={'impact': 70})) as model:
            tr.roster_projection(data, 'a'); tr.roster_projection(data, 'a')
            self.assertEqual(model.call_count, 1)
            data['contracts'].append({'player_id': '0', 'seasons': [{'season': '2026-27', 'salary': 10}]})
            tr.roster_projection(data, 'a'); self.assertEqual(model.call_count, 2)
            data['players'][0]['team_id'] = 'b'
            tr.roster_projection(data, 'a'); self.assertEqual(model.call_count, 3)
            data['traits'].append({'player_id': '1', 'trait_key': 'rim_deterrence', 'value': 70})
            tr.roster_projection(data, 'a'); self.assertEqual(model.call_count, 4)
            data['traits'][0]['value'] = 80
            tr.roster_projection(data, 'a'); self.assertEqual(model.call_count, 5)
        self.assertEqual(data['players'][1:], original[1:])
        self.assertNotIn('minutes_projection', data['players'][1])

    def test_roster_veto_cannot_be_overridden_by_bounded_discretion_or_forged_consent(self):
        candidate = {'accepted_by_all': True, 'legality': {'status': 'legal'},
                     'evaluations': [{'decision': 'reject_roster_plan', 'accepted': True, 'net_value': 100}]}
        self.assertFalse(tx.ai_trade_candidate_accepted({}, candidate))

    def test_unviable_counterparty_rejection_does_not_run_expensive_forecasts(self):
        flows = [('a', [], []), ('b', [], [])]
        raw = [SimpleNamespace(perspective_team_id='a', net_value=10, decision='accept', notes='', decision_reasons=[]),
               SimpleNamespace(perspective_team_id='b', net_value=-50, decision='reject', notes='', decision_reasons=[])]
        with patch.object(tx, 'trade_team_flows', return_value=flows), \
             patch.object(tx, 'evaluate_trade_for_team', side_effect=raw) as evaluate:
            result = tx.evaluate_trade_participants({}, None, {'status': 'legal'}, 1, {})
        self.assertEqual(result, raw)
        self.assertEqual(evaluate.call_count, 2)
        self.assertTrue(all(call.kwargs.get('plan_roster') is False for call in evaluate.call_args_list))

    def test_every_viable_ai_participant_gets_final_roster_review(self):
        flows = [('a', [], []), ('b', [], []), ('c', [], [])]
        raw = [SimpleNamespace(perspective_team_id=t, net_value=10, decision='accept', notes='', decision_reasons=[]) for t in 'abc']
        planned = [SimpleNamespace(perspective_team_id=t, net_value=8, decision='accept', notes='planned', decision_reasons=[]) for t in 'bc']
        with patch.object(tx, 'trade_team_flows', return_value=flows), \
             patch.object(tx, 'evaluate_trade_for_team', side_effect=raw+planned) as evaluate:
            result = tx.evaluate_trade_participants({'_human_team_ids': ['a']}, None, {'status': 'legal'}, 1, {})
        self.assertEqual(result, [raw[0], *planned])
        self.assertEqual(evaluate.call_count, 5)


if __name__ == '__main__':
    unittest.main()
