from copy import deepcopy
import unittest

from nba_gm_data.transactions import ai_trade_candidate_accepted, mark_ai_trade_accepted


class TradeDiscretionTests(unittest.TestCase):
    def test_negotiated_exception_does_not_relabel_the_gm_who_already_approved(self):
        candidate = self.candidate(20, 3)
        candidate['evaluations'][0].update(accepted=False, decision='reject', notes='A rejects: net -3.',
                                         decision_reasons=['Net value -3.00 is below the required 1.00.'])
        candidate['evaluations'][1].update(accepted=True, decision='accept')
        updated = mark_ai_trade_accepted(candidate)
        self.assertEqual(updated['evaluations'][0]['decision'], 'accept_bounded_ai_discretion')
        self.assertNotIn(' rejects:', updated['evaluations'][0]['notes'])
        self.assertIn('shortfall', updated['evaluations'][0]['decision_reasons'][0])
        self.assertEqual(updated['evaluations'][1]['decision'], 'accept')
        self.assertFalse(candidate['evaluations'][0]['accepted'])

    def candidate(self, outgoing, loss):
        return {'accepted_by_all': False, 'legality': {'status': 'legal'},
                'proposal': {'from_team_id': 'a', 'to_team_id': 'b', 'from_assets': [], 'to_assets': []},
                'evaluations': [{'perspective_team_id': 'a', 'outgoing_value': outgoing, 'net_value': -loss},
                                {'perspective_team_id': 'b', 'outgoing_value': 20, 'net_value': 20}]}

    def test_recorded_large_relative_losses_are_not_small_disagreements(self):
        for name, outgoing, loss in [('Toronto pick for Mykhailiuk', 15.36, 8.934),
                                     ('San Antonio Kornet package', 7.096, 7.234),
                                     ('Charlotte ONeale package', 5.984, 5.42),
                                     ('Washington Middleton package', 5.63, 5.251)]:
            with self.subTest(name=name):
                self.assertFalse(ai_trade_candidate_accepted({}, self.candidate(outgoing, loss)))

    def test_larger_consolidation_and_youth_bets_keep_existing_discretion(self):
        for outgoing, loss in [(19.14, 6.976), (19.63, 7.791), (17.312, 4.629)]:
            self.assertTrue(ai_trade_candidate_accepted({}, self.candidate(outgoing, loss)))

    def test_small_absolute_disagreement_and_liability_swaps_remain_possible(self):
        for outgoing, loss in [(1, 1), (-4, 3), (0, 2)]:
            self.assertTrue(ai_trade_candidate_accepted({}, self.candidate(outgoing, loss)))

    def test_genuine_consent_is_not_replaced_by_override_loss_rules(self):
        candidate = self.candidate(6, 5)
        candidate['accepted_by_all'] = True
        original = deepcopy(candidate)
        self.assertTrue(ai_trade_candidate_accepted({}, candidate))
        self.assertEqual(candidate, original)
        candidate['legality']['status'] = 'illegal'
        self.assertFalse(ai_trade_candidate_accepted({}, candidate))

    def test_absolute_and_combined_limits_still_apply(self):
        self.assertFalse(ai_trade_candidate_accepted({}, self.candidate(100, 9.01)))
        candidate = self.candidate(20, 5)
        candidate['evaluations'][1]['net_value'] = 2
        self.assertFalse(ai_trade_candidate_accepted({}, candidate))

    def test_legacy_evaluations_without_outgoing_value_keep_absolute_bound(self):
        candidate = self.candidate(6, 5)
        candidate['evaluations'][0].pop('outgoing_value')
        self.assertTrue(ai_trade_candidate_accepted({}, candidate))


if __name__ == '__main__':
    unittest.main()
