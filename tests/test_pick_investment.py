from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nba_gm_data import trade_roster as tr, transactions as tx


class PickInvestmentTests(unittest.TestCase):
    def fixture(self):
        return {'players': [{'id': 'new', 'team_id': 'b', 'age': 31},
                            {'id': 'old', 'team_id': 'a', 'age': 29}],
                'player_asset_valuations': [], 'meta': {'current_date': '2027-02-03'},
                '_trade_planning_save': {'state': {'current_date': '2027-02-03'}, 'health_states': []}}

    def projection(self, strength=74, retained=('new',), rotation=None):
        return {'strength': strength, 'retained_ids': list(retained), 'cuts': [],
                'rotation': rotation or {}}

    def estimate(self, data=None, *, gain=0, spend=20, salary=(3e6, 3e6), cost=0, after=None):
        incoming = [{'kind': 'player', 'id': 'new'}]
        outgoing = [{'kind': 'player', 'id': 'old'}, {'kind': 'pick', 'id': 'first'}]
        with patch.object(tx, 'package_value_for_team', side_effect=[spend, 0]), \
             patch.object(tx, 'package_salary', side_effect=salary):
            return tr.pick_investment_outlook(data or self.fixture(), 'a', incoming, outgoing,
                self.projection(rotation={'star': 32}), after or self.projection(74+gain), cost)

    def test_marginal_pick_buyer_cannot_use_generic_nine_point_tolerance(self):
        self.assertAlmostEqual(self.estimate(gain=.1354)['loss_limit'], 2.3124)
        self.assertAlmostEqual(self.estimate(gain=.0045)['loss_limit'], 1.527)

    def test_meaningful_upgrade_has_room_for_disagreement_but_not_unlimited_loss(self):
        self.assertGreater(self.estimate(gain=1)['loss_limit'], 6)
        self.assertEqual(self.estimate(gain=3)['loss_limit'], 9)

    def test_retained_young_upside_counts_but_discarded_and_departing_upside_do_not(self):
        data = self.fixture(); data['players'][0]['age'] = 22
        data['player_asset_valuations'] = [{'player_id': 'new', 'development_upside': 20, 'player_value': 60}]
        self.assertEqual(self.estimate(data)['loss_limit'], 5.5)
        self.assertEqual(self.estimate(data, after=self.projection(retained=()))['loss_limit'], 1.5)
        data['players'][1]['age'] = 22
        data['player_asset_valuations'].append({'player_id': 'old', 'development_upside': 20, 'player_value': 60})
        self.assertEqual(self.estimate(data)['loss_limit'], 1.5)

    def test_salary_dump_counts_actual_relief_not_money_still_owed_after_cuts(self):
        self.assertEqual(self.estimate(salary=(20e6, 5e6))['loss_limit'], 5.25)
        self.assertEqual(self.estimate(salary=(20e6, 5e6), cost=15)['loss_limit'], 1.5)
        self.assertEqual(self.estimate(salary=(None, 0))['loss_limit'], 1.5)

    def test_draft_compensation_received_offsets_spending_including_signed_swap_values(self):
        with patch.object(tx, 'package_value_for_team', side_effect=[20, 19]) as price:
            result = tr.pick_investment_outlook(self.fixture(), 'a', [{'kind': 'pick_swap', 'id': 'swap'}],
                [{'kind': 'pick', 'id': 'first'}], self.projection(), self.projection())
        self.assertIsNone(result)
        self.assertEqual(price.call_count, 2)
        self.assertIsNone(self.estimate(spend=0))

    def test_injury_cover_is_measured_not_a_blanket_exception(self):
        data = self.fixture()
        data['_trade_planning_save']['health_states'] = [
            {'player_id': 'star', 'availability_status': 'out', 'return_date': '2027-04-04'}]
        original = deepcopy(data)
        with patch.object(tr, 'roster_projection', side_effect=[self.projection(70), self.projection(71)]) as project:
            result = self.estimate(data)
        self.assertEqual(result['injury_cover_gain'], 1)
        self.assertEqual(result['loss_limit'], 7.5)
        self.assertIn('star', project.call_args_list[1].args[2])
        self.assertEqual(data, original)
        data['_trade_planning_save']['health_states'][0]['return_date'] = '2027-02-05'
        with patch.object(tr, 'roster_projection') as project:
            self.assertEqual(self.estimate(data)['loss_limit'], 1.5)
        project.assert_not_called()

    def test_investment_rejection_cannot_be_overridden_even_by_saved_approval(self):
        candidate = {'accepted_by_all': True, 'legality': {'status': 'legal'},
                     'evaluations': [{'decision': 'reject_pick_investment', 'accepted': True, 'net_value': 100}]}
        self.assertFalse(tx.ai_trade_candidate_accepted({}, candidate))

    def test_verdict_is_used_in_shared_team_evaluation_not_only_ai_search(self):
        data = {'_human_team_ids': []}
        proposal = SimpleNamespace(id='trade')
        outlook = {'adjustment': 0, 'issue': None, 'strength_delta': 0, 'waiver_cost_millions': 0,
                   'pick_investment': {'net_draft_value_spent': 30, 'loss_limit': 1.5,
                                       'incoming_rotation_minutes': 0, 'rotation_gain': 0, 'capital_limit': 8}}
        with patch.object(tx, 'package_value_for_team', side_effect=[20, 25]), \
             patch.object(tx, 'strategic_fit_adjustment', return_value=0), \
             patch('nba_gm_data.roster_space.sale_bonus', return_value=0), \
             patch.object(tx, 'personality_trade_adjustment', return_value={'total': 0}), \
             patch.object(tx, 'contextual_acceptance_threshold', return_value=1), \
             patch.object(tx, 'premium_return_issue', return_value=None), \
             patch.object(tr, 'trade_roster_outlook', return_value=outlook), \
             patch.object(tx, 'evaluation_notes', return_value='Evidence'):
            result = tx.evaluate_trade_for_team(data, proposal, 'a', [], [],
                {'status': 'legal', 'issues': []}, 17, {})
        self.assertEqual(result.decision, 'reject_pick_investment')
        self.assertFalse(result.accepted)
        self.assertIn('Draft investment:', result.notes)

    def test_conditional_terms_and_serialization_keep_the_original_random_identity(self):
        report = {'proposal': {'id': 'original', 'from_team_id': 'a', 'to_team_id': 'b',
                              'from_assets': [], 'to_assets': []},
                  'evaluations': [], 'legality': {'status': 'legal'}, 'accepted_by_all': False,
                  'evaluation_seed': 29, 'evaluation_proposal_id': 'original'}
        with patch.object(tx, 'validate_pick_obligation_term', return_value=True), \
             patch.object(tx, 'proposal_summary', return_value='Summary'), \
             patch.object(tx, 'trade_value_breakdown', return_value={}):
            wrapped = tx.trade_result_with_pick_terms(report, [{'type': 'protected_pick', 'id': 'terms'}])
            candidate = json.loads(json.dumps(tx.candidate_from_evaluation({}, wrapped)))
        self.assertNotEqual(candidate['proposal']['id'], 'original')
        self.assertEqual(candidate['evaluation_proposal_id'], 'original')
        self.assertEqual(candidate['evaluation_seed'], 29)
        self.assertEqual(report['proposal']['id'], 'original')

    def test_positive_price_score_does_not_bypass_excessive_backup_capital_spending(self):
        outlook = {'adjustment': 0, 'issue': 'Excessive capital', 'strength_delta': 0, 'waiver_cost_millions': 0,
                   'pick_investment': {'net_draft_value_spent': 30, 'loss_limit': 1.5,
                                       'incoming_rotation_minutes': 25, 'rotation_gain': 0, 'capital_limit': 8}}
        with patch.object(tx, 'package_value_for_team', side_effect=[30, 25]), \
             patch.object(tx, 'strategic_fit_adjustment', return_value=0), \
             patch('nba_gm_data.roster_space.sale_bonus', return_value=0), \
             patch.object(tx, 'personality_trade_adjustment', return_value={'total': 0}), \
             patch.object(tx, 'contextual_acceptance_threshold', return_value=1), \
             patch.object(tx, 'premium_return_issue', return_value=None), \
             patch.object(tr, 'trade_roster_outlook', return_value=outlook), \
             patch.object(tx, 'evaluation_notes', return_value='Evidence'):
            result = tx.evaluate_trade_for_team({}, SimpleNamespace(id='positive'), 'a', [], [],
                {'status': 'legal', 'issues': []}, 17, {})
        self.assertEqual(result.net_value, 5)
        self.assertEqual(result.decision, 'reject_pick_investment')
        self.assertFalse(result.accepted)

    def test_live_application_checks_ai_budget_using_current_roster_and_original_seed(self):
        data = {'players': [{'id': str(i), 'team_id': 'a'} for i in range(5)],
                'teams': [{'id': 'a', 'abbrev': 'A'}]}
        proposal = {'id': 'wrapped', 'from_team_id': 'a', 'to_team_id': 'b'}
        candidate = {'evaluation_seed': 29, 'evaluation_proposal_id': 'original',
                     'pick_obligation_terms': [{'id': 'terms'}]}
        saved = {'meta': {'user_team_id': 'b'}}
        original = deepcopy(saved)
        with patch('nba_gm_data.save.canonical_with_save', return_value=data), \
             patch.object(tx, 'with_transaction_context', return_value=data), \
             patch.object(tx, 'canonical_with_pending_pick_terms', return_value=data) as terms, \
             patch.object(tx, 'trade_team_flows', return_value=[('a', [], [])]), \
             patch.object(tr, 'trade_roster_outlook', return_value={'issue': None, 'pick_investment': {'loss_limit': 2}}), \
             patch.object(tx, 'evaluate_trade_for_team', return_value=SimpleNamespace(decision='reject_pick_investment')) as evaluate:
            issues = tr.live_roster_issues(data, saved, proposal, candidate=candidate)
        self.assertEqual(len(issues), 1)
        self.assertIn('overpayment', issues[0])
        self.assertEqual(evaluate.call_args.args[1].id, 'original')
        self.assertEqual(evaluate.call_args.args[6], 29)
        self.assertEqual(terms.call_args.args[1], candidate['pick_obligation_terms'])
        self.assertEqual(saved, original)

    def test_backup_capital_budget_rewards_real_depth_without_blanket_first_round_permission(self):
        data = self.fixture()
        data['players'] += [{'id': 'starter', 'team_id': 'a', 'position': 'C'},
                            {'id': 'backup', 'team_id': 'a', 'position': 'C'}]
        data['players'][0]['position'] = 'C'
        data['player_asset_valuations'] = [
            {'player_id': 'starter', 'on_court_value': 80},
            {'player_id': 'backup', 'on_court_value': 40},
            {'player_id': 'new', 'on_court_value': 55}]
        before = self.projection(retained=('starter', 'backup'))
        after = self.projection(retained=('starter', 'backup', 'new'), rotation={'new': 16})
        with patch.object(tx, 'package_value_for_team', side_effect=[30, 0]), \
             patch.object(tx, 'package_salary', return_value=3e6):
            result = tr.pick_investment_outlook(data, 'a', [{'kind': 'player', 'id': 'new'}],
                [{'kind': 'pick', 'id': 'first'}], before, after)
        self.assertEqual(result['backup_quality_gain'], 15)
        self.assertEqual(result['capital_limit'], 17)
        self.assertLess(result['capital_limit'], result['net_draft_value_spent'])
        self.assertGreater(result['capital_limit'], 12)  # A second can still fund genuine insurance.


if __name__ == '__main__':
    unittest.main()
