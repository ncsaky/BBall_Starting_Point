from copy import deepcopy
from datetime import date
import json
from types import SimpleNamespace as Row
import unittest
from unittest.mock import patch

from nba_gm_data import team_planning as tp, transactions as tx


class TeamPlanningTests(unittest.TestCase):
    def league(self):
        data = {'players': [], 'teams': [], 'meta': {'current_date': '2026-11-01'}}
        states, values = [], []
        for i in range(12):
            tid = f't{i}'
            data['teams'].append({'id': tid})
            states.append(Row(team_id=tid, contention_ceiling=80 if i < 3 else 66 if i < 6 else 52))
            for j in range(5):
                pid = f'{tid}p{j}'
                age = 22 if i == 4 else 34 if i == 3 else 27
                data['players'].append({'id': pid, 'team_id': tid, 'age': age})
                values.append(Row(player_id=pid, team_id=tid, on_court_value=90 if i < 5 else 65,
                                  development_upside=15 if i == 4 else 0, health_risk=0))
        return data, states, values

    def context(self, phase='entering', trend=0):
        data = {'players': [{'id': 'star', 'team_id': 'a', 'age': 33}, {'id': 'young', 'team_id': 'a', 'age': 22}],
                'meta': {'current_date': '2026-11-01'}, 'transaction_logs': [],
                'team_strategic_states': [{'team_id': 'a', 'window_phase': phase, 'core_candidates': ['star', 'young'],
                                           'league_rank': 8, 'contender_index': 4, 'window_trend': trend}],
                'player_asset_valuations': [{'player_id': pid, 'on_court_value': 75, 'player_value': 80} for pid in ('star','young')],
                'front_office_profiles': [{'team_id': 'a', 'patience': 55}]}
        return data, {'state': {'current_date': '2026-11-01'}}

    def review(self, data, saved, stamp):
        data['meta']['current_date'] = stamp
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c:c):
            return tp.refresh_team_plans(data, saved, stamp)

    def test_peak_is_relative_and_exclusive_without_a_fixed_quota(self):
        data, states, values = self.league()
        result = tp.window_assessments(data, states, values)
        self.assertEqual(sum(r['window_phase']=='peak' for r in result.values()), 3)
        for s in states: s.contention_ceiling = 70
        equal = tp.window_assessments(data, states, values)
        self.assertFalse(any(r['window_phase']=='peak' for r in equal.values()))

    def test_aging_and_young_cores_have_different_routes_not_automatic_teardowns(self):
        data, states, values = self.league()
        result = tp.window_assessments(data, states, values)
        self.assertEqual(result['t3']['window_phase'], 'exiting')
        self.assertEqual(result['t4']['window_phase'], 'entering')
        self.assertNotEqual(result['t5']['window_phase'], 'peak')

    def test_one_aging_star_does_not_make_a_ready_young_core_an_exiting_team(self):
        data, states, values = self.league()
        ages = [36, 26, 28, 25, 24]
        for p, age in zip([p for p in data['players'] if p['team_id'] == 't3'], ages):
            p['age'] = age
        result = tp.window_assessments(data, states, values)['t3']
        self.assertLess(result['trend'], 0)
        self.assertEqual(result['window_phase'], 'entering')

    def test_one_young_piece_does_not_hide_an_otherwise_aging_core(self):
        data, states, values = self.league()
        for p, age in zip([p for p in data['players'] if p['team_id'] == 't3'], [36, 26, 34, 35, 33]):
            p['age'] = age
        self.assertEqual(tp.window_assessments(data, states, values)['t3']['window_phase'], 'exiting')

    def test_young_fringe_players_cannot_hide_an_aging_playoff_rotation(self):
        data, states, values = self.league()
        for i in range(8):
            pid = f'fringe{i}'
            data['players'].append({'id': pid, 'team_id': 't3', 'age': 21})
            values.append(Row(player_id=pid, team_id='t3', on_court_value=40,
                              development_upside=25, health_risk=0))
        self.assertEqual(tp.window_assessments(data, states, values)['t3']['window_phase'], 'exiting')

    def test_unused_veteran_is_not_forecast_as_a_current_foundation(self):
        data, states, values = self.league()
        players = [p for p in data['players'] if p['team_id'] == 't3']
        for p in players:
            p['age'] = 26
        players[0].update(age=45, minutes_projection=0)
        self.assertEqual(tp.window_assessments(data, states, values)['t3']['trend'], 0)
        players[0]['_trade_value_unavailable'] = True
        self.assertLess(tp.window_assessments(data, states, values)['t3']['trend'], 0)

    def test_retired_and_free_agent_stars_cannot_distort_the_active_league_baseline(self):
        data,states,values = self.league()
        before = tp.window_assessments(data,states,values)
        for i in range(200):
            pid = f'inactive{i}'
            team = None if i%2 else 't0'
            data['players'].append({'id':pid,'team_id':team,'_inactive_player':True})
            values.append(Row(player_id=pid,team_id=team,on_court_value=99,development_upside=0,health_risk=0))
        self.assertEqual(tp.window_assessments(data,states,values),before)

    def test_reviews_are_idempotent_serializable_and_cannot_backdate(self):
        data, saved = self.context()
        self.assertTrue(self.review(data, saved, '2026-11-01'))
        before = deepcopy(saved)
        saved = json.loads(json.dumps(saved))
        self.assertFalse(self.review(data, saved, '2026-11-02'))
        self.assertFalse(self.review(data, saved, '2026-10-01'))
        self.assertEqual(saved, before)
        self.assertEqual(saved['team_plans']['a']['core_ids'], ['star', 'young'])

    def test_major_acquisition_commits_the_existing_core_too(self):
        data, saved = self.context()
        data['transaction_logs'] = [{'transaction_type': 'trade', 'status': 'applied_to_save_ledger',
            'date': '2026-10-15', 'teams': ['other','a'], 'assets': {
                'from_assets': [{'kind': 'player', 'id': 'star'}], 'to_assets': [{'kind': 'pick', 'id': 'first'}]}}]
        self.review(data, saved, '2026-11-01')
        plan = saved['team_plans']['a']
        self.assertEqual(plan['commit_until'], '2027-10-15')
        self.assertTrue(tp.core_commitment(data, 'a', 'young'))
        data['transaction_logs'] = []
        self.review(data,saved,'2026-12-01')
        self.assertEqual(saved['team_plans']['a']['major_acquisition_date'],'2026-10-15')
        data['_human_team_ids'] = ['a']
        self.assertFalse(tp.core_commitment(data, 'a', 'young'))

    def test_serious_injury_triggers_review_not_a_forced_rebuild(self):
        data, saved = self.context('peak', -2)
        saved['health_states'] = [{'player_id':'star','availability_status':'out','return_date':'2027-04-01'}]
        self.review(data, saved, '2026-11-01')
        plan = saved['team_plans']['a']
        self.assertEqual(plan['window_phase'], 'peak')
        self.assertEqual(plan['review_exception'], 'serious_core_injury_review')
        self.assertFalse(tp.core_commitment(data, 'a', 'star'))

    def test_short_absences_do_not_rebuild_every_teams_strategy(self):
        data,saved = self.context()
        self.review(data,saved,'2026-11-01')
        before = deepcopy(saved['team_plans'])
        saved['health_states'] = [{'player_id':'star','availability_status':'out','return_date':'2026-11-12'}]
        self.assertFalse(self.review(data,saved,'2026-11-02'))
        self.assertEqual(saved['team_plans'],before)

    def test_repeated_early_exits_request_review_only_after_patience_and_trial(self):
        data, saved = self.context()
        saved['playoff_state'] = {'status':'completed','year':'2026','series':[]}
        self.review(data, saved, '2026-11-01')
        self.assertNotIn('review_core', saved['team_plans']['a']['route'])
        saved['playoff_state']['year'] = '2027'
        self.review(data, saved, '2027-07-01')
        self.assertEqual(saved['team_plans']['a']['route'], 'review_core_ceiling_and_retool_alternatives')
        self.assertEqual(saved['team_plans']['a']['window_phase'], 'entering')
        self.assertEqual(saved['team_plans']['a']['retool_candidate_id'], 'star')

    def test_trading_or_retiring_a_core_player_removes_him_from_the_plan(self):
        data, saved = self.context()
        self.review(data, saved, '2026-11-01')
        data['players'][0]['team_id'] = 'b'
        data['team_strategic_states'][0]['core_candidates'] = ['young']
        self.review(data, saved, '2026-11-02')
        self.assertEqual(saved['team_plans']['a']['core_ids'], ['young'])

    def test_commitment_rejects_ordinary_return_but_not_an_exceptional_one(self):
        data, saved = self.context()
        self.review(data, saved, '2026-11-01')
        proposal = Row(id='trade')
        outgoing = [{'kind':'player','id':'star'}]
        incoming = [{'kind':'player','id':'new'}]
        with patch.object(tx,'strategic_fit_adjustment',return_value=0), \
             patch.object(tx,'personality_trade_adjustment',return_value={'total':0}), \
             patch.object(tx,'contextual_acceptance_threshold',return_value=1), \
             patch.object(tx,'evaluation_notes',return_value=''):
            for value, expected in ((55,False),(80,True)):
                with patch.object(tx,'package_value_for_team',side_effect=[value,50]):
                    result = tx.evaluate_trade_for_team(data,proposal,'a',incoming,outgoing,{'status':'legal','issues':[]},17,{})
                self.assertEqual(result.accepted,expected)


if __name__ == '__main__': unittest.main()
