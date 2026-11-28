"""CORE-RENEW: a champion promises to keep its core through the next season."""
from types import SimpleNamespace as Row
import unittest
from unittest.mock import patch

from nba_gm_data import team_planning as tp, transactions as tx

CORE = ('star', 'guard', 'big', 'wing')
TITLE = tp.TITLE_ROUNDS


class ChampionCoreTests(unittest.TestCase):
    def team(self, phase='entering', trend=0):
        data = {'players': [{'id': pid, 'team_id': 'a', 'age': 33 if pid == 'star' else 27} for pid in CORE],
                'meta': {'current_date': '2026-07-28'}, 'transaction_logs': [],
                'team_strategic_states': [{'team_id': 'a', 'window_phase': phase, 'core_candidates': list(CORE),
                                           'league_rank': 3, 'contender_index': 9, 'window_trend': trend}],
                'player_asset_valuations': [{'player_id': pid, 'on_court_value': 80 if pid == 'star' else 75,
                                             'player_value': 80} for pid in CORE]}
        saved = {}
        self.review(data, saved, '2026-07-28')  # the career's first promise: to June 30, 2027
        return data, saved

    def review(self, data, saved, stamp):
        data['meta']['current_date'] = stamp
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c: c):
            tp.refresh_team_plans(data, saved, stamp)
        data['team_plans'] = saved['team_plans']

    def playoffs(self, data, saved, year, rounds):
        saved['playoff_state'] = {'status': 'completed', 'year': str(year),
                                  'series': [{'winner_team_id': 'a'}] * rounds}
        self.review(data, saved, f'{year}-06-17')

    def promised(self, data, day, pid='guard'):
        data['meta']['current_date'] = day
        return tp.core_commitment(data, 'a', pid)

    def test_a_champion_keeps_its_core_through_the_next_season(self):
        data, saved = self.team()
        self.playoffs(data, saved, 2027, TITLE)
        self.assertEqual(saved['team_plans']['a']['title_commit_until'], '2028-06-30')
        for day in ('2027-06-30', '2027-07-01', '2027-09-15', '2028-02-01', '2028-06-30'):
            self.assertTrue(self.promised(data, day), day)
        self.assertFalse(self.promised(data, '2028-07-01'))
        self.assertFalse(self.promised(data, '2027-07-01', 'bench_player'))

    def test_anything_short_of_a_title_renews_nothing(self):
        for rounds in range(TITLE):
            data, saved = self.team()
            self.playoffs(data, saved, 2027, rounds)
            self.assertNotIn('title_commit_until', saved['team_plans']['a'])
            self.assertTrue(self.promised(data, '2027-06-30'))
            self.assertFalse(self.promised(data, '2027-07-01'), rounds)

    def test_a_repeat_renews_and_a_new_champion_ends_it(self):
        data, saved = self.team()
        self.playoffs(data, saved, 2027, TITLE)
        self.playoffs(data, saved, 2028, TITLE)
        self.assertTrue(self.promised(data, '2029-01-15'))
        self.playoffs(data, saved, 2029, TITLE - 1)
        self.assertNotIn('title_commit_until', saved['team_plans']['a'])
        self.assertFalse(self.promised(data, '2029-06-20'))

    def test_a_later_review_keeps_the_promise_after_one_departure(self):
        data, saved = self.team()
        self.playoffs(data, saved, 2027, TITLE)
        saved['playoff_state'] = {}  # the season rollover clears the bracket
        data['players'][3]['team_id'] = 'b'
        self.review(data, saved, '2027-10-02')
        self.assertEqual(saved['team_plans']['a']['title_commit_until'], '2028-06-30')
        self.assertTrue(self.promised(data, '2027-10-02'))

    def test_the_promise_ends_when_most_of_the_title_core_has_left(self):
        data, saved = self.team()
        self.playoffs(data, saved, 2027, TITLE)
        for player in data['players'][1:]:
            player['team_id'] = 'b'
        self.review(data, saved, '2027-07-08')
        self.assertNotIn('title_commit_until', saved['team_plans']['a'])
        self.assertFalse(self.promised(data, '2027-07-08', 'star'))

    def test_injury_and_trade_talk_reviews_still_lift_the_promise(self):
        data, saved = self.team()
        saved['health_states'] = [{'player_id': 'star', 'availability_status': 'out', 'return_date': '2028-03-01'}]
        self.playoffs(data, saved, 2027, TITLE)
        self.assertEqual(saved['team_plans']['a']['injury_review_ids'], ['star'])
        self.assertFalse(self.promised(data, '2027-07-01', 'star'))
        self.assertTrue(self.promised(data, '2027-07-01', 'guard'))
        data, saved = self.team()
        saved['ai_trade_pressure_player_ids'] = ['star']
        self.playoffs(data, saved, 2027, TITLE)
        self.assertFalse(self.promised(data, '2027-07-01', 'guard'))

    def test_a_champion_marks_no_player_to_move(self):
        for rounds, marked in ((0, 'star'), (TITLE, None)):
            data, saved = self.team('exiting', -3)
            self.playoffs(data, saved, 2027, rounds)
            saved['playoff_state'] = {}
            self.review(data, saved, '2027-07-02')
            self.assertEqual(saved['team_plans']['a']['retool_candidate_id'], marked, rounds)

    def test_the_users_own_team_is_never_bound(self):
        data, saved = self.team()
        self.playoffs(data, saved, 2027, TITLE)
        data['_human_team_ids'] = ['a']
        self.assertFalse(self.promised(data, '2027-07-01'))

    def test_the_refusal_says_they_are_champions(self):
        proposal = Row(id='trade')
        outgoing, incoming = [{'kind': 'player', 'id': 'guard'}], [{'kind': 'player', 'id': 'new'}]
        for rounds, day, words in ((TITLE, '2027-07-05', 'as champions'), (0, '2027-02-05', 'trial window')):
            data, saved = self.team()
            self.playoffs(data, saved, 2027, rounds)
            data['meta']['current_date'] = day
            with patch.object(tx, 'strategic_fit_adjustment', return_value=0), \
                 patch.object(tx, 'personality_trade_adjustment', return_value={'total': 0}), \
                 patch.object(tx, 'contextual_acceptance_threshold', return_value=1), \
                 patch.object(tx, 'evaluation_notes', return_value=''), \
                 patch.object(tx, 'package_value_for_team', side_effect=[55, 50]):
                result = tx.evaluate_trade_for_team(data, proposal, 'a', incoming, outgoing,
                                                    {'status': 'legal', 'issues': []}, 17, {},
                                                    include_presentation=False)
            self.assertFalse(result.accepted)
            reason = next(r for r in result.decision_reasons if r.startswith('Core commitment:'))
            self.assertIn(words, reason)


if __name__ == '__main__':
    unittest.main()
