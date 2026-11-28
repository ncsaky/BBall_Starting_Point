"""INJURY-NARROW: only a long injury to one of a team's three best players opens a review, and it frees only him."""
from types import SimpleNamespace as Row
import unittest
from unittest.mock import patch

from nba_gm_data import team_planning as tp, trade_roster as tr, transactions as tx
from test_premium_trade_returns import PremiumTradeReturnTests

# five core players, best first
CORE = {'star': 85, 'second': 80, 'third': 75, 'fourth': 70, 'reserve': 62}
OPENING_PLUS_HALF = '2028-01-20'  # misses 92 days of the 2027-28 season


class InjuryReviewTests(unittest.TestCase):
    def plan(self, injuries, stamp='2027-07-01', pressure=()):
        data = {'players': [{'id': pid, 'team_id': 'a', 'age': 27} for pid in CORE], 'transaction_logs': [],
                'meta': {'current_date': '2026-07-28'},
                'team_strategic_states': [{'team_id': 'a', 'window_phase': 'peak', 'core_candidates': list(CORE),
                                           'league_rank': 3, 'contender_index': 9, 'window_trend': 0}],
                'player_asset_valuations': [{'player_id': pid, 'on_court_value': v, 'player_value': v}
                                            for pid, v in CORE.items()]}
        saved = {}
        self.review(data, saved, '2026-07-28')
        # a major acquisition keeps the promise running into the next season
        saved['team_plans']['a']['commit_until'] = '2028-06-30'
        saved['health_states'] = [{'player_id': pid, 'availability_status': 'out', 'return_date': back}
                                  for pid, back in injuries.items()]
        saved['ai_trade_pressure_player_ids'] = list(pressure)
        self.review(data, saved, stamp)
        return data, saved['team_plans']['a']

    def review(self, data, saved, stamp):
        data['meta']['current_date'] = stamp
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c: c):
            tp.refresh_team_plans(data, saved, stamp)
        data['team_plans'] = saved['team_plans']

    def promised(self, data):
        return {pid for pid in CORE if tp.core_commitment(data, 'a', pid)}

    def test_only_regular_season_days_count(self):
        self.assertEqual(tp.season_days_missed('2027-07-01', '2027-10-03'), 0)
        self.assertEqual(tp.season_days_missed('2027-07-01', '2027-10-24'), 4)
        self.assertEqual(tp.season_days_missed('2027-07-01', OPENING_PLUS_HALF), 92)
        self.assertEqual(tp.season_days_missed('2027-01-05', '2027-04-30'), 97)
        self.assertEqual(tp.season_days_missed('2027-03-01', '2027-12-01'), 42 + 42)
        self.assertEqual(tp.season_days_missed('2027-07-01', '2028-12-01'), 174 + 1 + 42)

    def test_a_reserve_out_all_season_frees_nobody(self):
        for pid in ('fourth', 'reserve'):
            data, plan = self.plan({pid: '2028-04-30'})
            self.assertIsNone(plan['review_exception'])
            self.assertNotIn('injury_review_ids', plan)
            self.assertEqual(self.promised(data), set(CORE))

    def test_a_star_back_early_in_the_season_frees_nobody(self):
        for back in ('2027-10-03', '2027-11-30', '2028-01-07'):
            data, plan = self.plan({'star': back})
            self.assertIsNone(plan['review_exception'], back)
            self.assertEqual(self.promised(data), set(CORE))

    def test_a_star_missing_half_a_season_frees_only_him(self):
        data, plan = self.plan({'third': OPENING_PLUS_HALF, 'reserve': '2028-04-30'})
        self.assertEqual(plan['review_exception'], tp.INJURY_REVIEW)
        self.assertEqual(plan['injury_review_ids'], ['third'])
        self.assertEqual(self.promised(data), set(CORE) - {'third'})

    def test_an_in_season_injury_counts_the_season_still_to_play(self):
        _, plan = self.plan({'star': '2027-12-01'}, stamp='2027-03-01')  # 84 days across two seasons
        self.assertIsNone(plan['review_exception'])
        _, plan = self.plan({'star': '2028-04-01'}, stamp='2027-11-15')
        self.assertEqual(plan['injury_review_ids'], ['star'])

    def test_a_trade_demand_still_frees_the_whole_team(self):
        data, plan = self.plan({'star': '2028-04-30'}, pressure=['fourth'])
        self.assertEqual(plan['review_exception'], 'core_trade_pressure_review')
        self.assertEqual(self.promised(data), set())
        self.assertTrue(tp.review_frees(plan, ['second', 'third']))

    def test_review_frees_only_trades_made_of_injured_players(self):
        plan = {'review_exception': tp.INJURY_REVIEW, 'injury_review_ids': ['star']}
        self.assertTrue(tp.review_frees(plan, ['star']))
        for ids in ([], ['second'], ['star', 'second']):
            self.assertFalse(tp.review_frees(plan, ids), ids)
        self.assertFalse(tp.review_frees({'review_exception': None}, ['star']))

    def test_picks_cannot_buy_the_healthy_star_of_a_team_with_an_injured_one(self):
        data, _ = PremiumTradeReturnTests().fixture()
        data['players'].append({'id': 'co_star', 'name': 'co_star', 'team_id': 'a', 'age': 27, 'position': 'PG',
                                'minutes_projection': 32, 'overall': 84, 'potential': 84})
        data['player_asset_valuations'].append({'player_id': 'co_star', 'on_court_value': 84, 'development_upside': 0,
            'player_value': 92, 'playoff_value': 88, 'contract_surplus': 0, 'health_risk': 0})
        data['team_plans']['a'] = {'review_exception': tp.INJURY_REVIEW, 'injury_review_ids': ['star']}
        for pick in data['draft_picks']:
            pick['projected_pick_slot'] = 1
        picks = [{'kind': 'pick', 'id': p['id']} for p in data['draft_picks']]
        issue = lambda *ids: tx.premium_return_issue(data, 'a', picks, [{'kind': 'player', 'id': p} for p in ids])
        with patch.object(tx, 'pick_asset_value', return_value=80):
            self.assertIsNone(issue('star'))
            self.assertIsNotNone(issue('co_star'))
            self.assertIsNotNone(issue('star', 'co_star'))

    def test_the_rotation_check_is_waived_only_when_the_injured_player_leaves(self):
        data = {'meta': {'current_date': '2027-02-01', 'active_season': '2026-27'}, 'teams': [{'id': 'a', 'abbrev': 'A'}],
                'players': [{'id': str(i), 'team_id': 'a', 'age': 27, 'position': 'C', 'name': str(i)} for i in range(10)],
                'traits': [], 'contracts': [],
                'team_strategic_states': [{'team_id': 'a', 'phase': 'contending', 'window_phase': 'peak'}],
                'player_asset_valuations': [],
                'team_plans': {'a': {'review_exception': tp.INJURY_REVIEW, 'injury_review_ids': ['0']}}}
        for leaving, refused in (('0', False), ('1', True)):
            before = {'strength': 74, 'cuts': [], 'rotation': {}, 'retained_ids': []}
            after = {**before, 'strength': 72.6}
            with patch.object(tr, 'roster_projection', side_effect=[before, after]):
                result = tr.trade_roster_outlook(data, 'a', [{'kind': 'player', 'id': 'new'}],
                                                 [{'kind': 'player', 'id': leaving}])
            self.assertEqual(result['issue'] is not None, refused, leaving)


if __name__ == '__main__':
    unittest.main()
