import unittest
from analyze_trade_market import direction, release_destination


class TradeMarketAnalysisTests(unittest.TestCase):
    def event(self):
        team = {'abbrev': 'A', 'window_phase': 'peak', 'route': 'extend_peak',
                'league_rank': 4, 'contention_strength': 70, 'top8_quality': 500,
                'payroll_millions': 200, 'youth_pipeline': 30, 'owned_core_ids': [],
                'commit_until': '2027-06-30'}
        return {'date': '2027-02-05', 'proposal': {'from_team_id': 'a', 'to_team_id': 'b',
                'from_assets': [], 'to_assets': []}, 'before': {'teams': {'a': team}, 'assets': []},
                'after': {'teams': {'a': dict(team)}}, 'evaluations': []}

    def test_phase_drop_is_not_automatically_a_desire_to_leave_contention(self):
        event = self.event()
        event['after']['teams']['a'].update(window_phase='entering', contention_strength=70.1, top8_quality=502)
        result = direction(event, 'a')
        self.assertEqual(result['stated_route'], 'extend_peak')
        self.assertIn('improves_current_team', result['measured_effects'])
        self.assertEqual(result['review_flags'], [])

    def test_future_assets_are_a_separate_measured_benefit(self):
        event = self.event()
        event['before']['teams']['a']['window_phase'] = 'rebuilding'
        event['proposal']['to_assets'] = [{'kind': 'pick', 'id': 'first'}]
        event['after']['teams']['a'].update(contention_strength=69, top8_quality=495)
        result = direction(event, 'a')
        self.assertEqual(result['net_pick_rights'], 1)
        self.assertIn('adds_future_assets_or_youth', result['measured_effects'])
        self.assertEqual(result['review_flags'], [])

    def test_discretionary_loss_is_reviewed_relative_to_asset_value(self):
        event = self.event()
        event['evaluations'] = [{'perspective_team_id': 'a', 'net_value': -5, 'outgoing_value': 6,
                                 'decision': 'accept_bounded_ai_discretion'}]
        self.assertIn('discretion_accepts_loss_over_quarter_of_outgoing_team_value', direction(event, 'a')['review_flags'])

    def test_later_release_does_not_erase_prior_buyout_destination(self):
        first = {'player_id': 'p', 'date': '2027-02-07', 'clearance_date': '2027-02-09', 'status': 'cleared'}
        later = dict(first, date='2027-06-25', clearance_date='2027-06-27')
        logs = [{'id': 'signed', 'transaction_type': 'ai_free_agent_signing', 'assets': {'player_id': 'p'},
                 'date': '2027-02-09', 'teams': ['uta']}]
        self.assertEqual(release_destination(first, [first, later], logs),
                         {'signed_team': 'uta', 'signed_date': '2027-02-09'})
        self.assertEqual(release_destination(later, [first, later], logs), {})
        self.assertEqual(release_destination(dict(first, status='claimed'), [first], logs), {})

    def test_later_signing_does_not_attach_to_an_earlier_waiver_spell(self):
        first = {'player_id': 'p', 'date': '2027-02-07', 'clearance_date': '2027-02-09', 'status': 'cleared'}
        later = dict(first, date='2027-06-25', clearance_date='2027-06-27')
        logs = [{'id': 'signed', 'transaction_type': 'free_agency', 'assets': {'player_id': 'p'},
                 'date': '2027-07-01', 'teams': ['uta']}]
        self.assertEqual(release_destination(first, [first, later], logs), {})
        self.assertEqual(release_destination(later, [first, later], logs)['signed_team'], 'uta')


if __name__ == '__main__':
    unittest.main()
