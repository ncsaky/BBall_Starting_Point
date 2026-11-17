from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import unittest

from nba_gm_data import trade_wants as wants, transactions as tx, trade_roster as tr


class TradeWantsTests(unittest.TestCase):
    def fixture(self):
        return {'meta': {'current_date': '2027-01-31'}, 'teams': [{'id': 'a', 'abbrev': 'A'}, {'id': 'b', 'abbrev': 'B'}],
            'players': [{'id': 'p', 'team_id': 'b', 'name': 'Player', 'position': 'SG/SF', 'age': 23, 'height_inches': 79},
                        {'id': 'old', 'team_id': 'a', 'name': 'Incumbent', 'position': 'SF', 'age': 29}],
            'contracts': [], 'draft_picks': [], 'traits': [], '_human_team_ids': ['a'],
            'team_strategic_states': [{'team_id': 'a', 'phase': 'contending', 'window_phase': 'peak', 'needs': []},
                                      {'team_id': 'b', 'phase': 'rebuilding', 'window_phase': 'rebuilding', 'needs': []}],
            'player_asset_valuations': [{'player_id': 'p', 'player_value': 80, 'on_court_value': 80, 'development_upside': 12}],
            'team_trade_wants': {'a': {'revision': 1, 'entries': []}},
            '_trade_planning_save': {'state': {'current_date': '2027-01-31'}, 'health_states': []}}

    def player_want(self, **kwargs):
        return {'id': 'w', 'kind': 'player', 'positions': ['SF'],
                'conditions': [{'field': 'range', 'op': '>=', 'value': 90}], **kwargs}

    def match(self, data, row=None, facts=None, asset=None):
        with patch.object(wants, 'player_facts', return_value=facts or {'range': 91, 'overall': 80}):
            return wants.match_want(data, 'a', row or self.player_want(), asset or {'kind': 'player', 'id': 'p'})

    def test_normalize_bounds_and_serialization(self):
        rows = wants.normalize_wants([self.player_want(), {'kind': 'picks', 'id': 'pick'}], {'old'})
        self.assertEqual(json.loads(json.dumps(rows)), rows)
        for rows in ([self.player_want()]*7, [self.player_want(conditions=[{'field': 'name', 'op': '=', 'value': 1}])],
                     [self.player_want(positions=['X'])], [self.player_want(conditions=[{'field': 'age', 'op': '>=', 'value': float('nan')}])]):
            with self.assertRaises(ValueError):
                wants.normalize_wants(rows, {'old'})

    def test_positions_are_or_conditions_are_and_and_missing_is_unknown(self):
        data = self.fixture()
        self.assertEqual(self.match(data)['status'], 'exact')
        self.assertEqual(self.match(data, self.player_want(positions=['PG']))['status'], 'none')
        row = self.player_want(conditions=[{'field': 'range', 'op': '>=', 'value': 90}, {'field': 'age', 'op': '<', 'value': 24}])
        self.assertEqual(self.match(data, row, {'range': 91, 'age': 23})['status'], 'exact')
        self.assertEqual(self.match(data, row, {'range': 91})['status'], 'none')

    def test_near_matches_are_labeled_not_silently_exact(self):
        self.assertEqual(self.match(self.fixture(), facts={'range': 89})['status'], 'near')
        self.assertEqual(self.match(self.fixture(), facts={'range': 80})['status'], 'none')

    def test_upgrade_target_must_still_belong_and_role_must_match(self):
        data = self.fixture()
        row = {'id': 'up', 'kind': 'upgrade', 'target_player_id': 'old', 'positions': [], 'conditions': []}
        with patch.object(wants, 'player_facts', side_effect=lambda c, p: {'overall': 85 if p['id'] == 'p' else 80}):
            self.assertEqual(wants.match_want(data, 'a', row, {'kind': 'player', 'id': 'p'})['status'], 'exact')
            data['players'][1]['team_id'] = 'b'
            self.assertEqual(wants.match_want(data, 'a', row, {'kind': 'player', 'id': 'p'})['status'], 'none')

    def test_user_starts_empty_ai_suggestions_never_publish_user_preferences(self):
        data = self.fixture(); data['team_trade_wants'] = {}
        before = deepcopy(data)
        self.assertEqual(wants.wants_for_team(data, 'a'), [])
        self.assertTrue(wants.suggested_wants(data, 'a'))
        self.assertEqual(data, before)

    def test_ai_phases_have_distinct_bounded_priorities(self):
        data = self.fixture()
        lists = {}
        for phase in ('rebuilding', 'entering', 'peak', 'exiting'):
            data['team_strategic_states'][1]['window_phase'] = phase
            rows = wants.suggested_wants(data, 'b')
            lists[phase] = rows
            self.assertLessEqual(len(rows), 3)
            self.assertNotIn('p', [r.get('target_player_id') for r in rows if 'p' in data.get('team_plans', {}).get('b', {}).get('core_ids', [])])
        self.assertNotEqual(lists['rebuilding'], lists['peak'])

    def test_pick_horizon_rolls_and_protected_and_swaps_cannot_be_unprotected(self):
        data = self.fixture()
        data['draft_picks'] = [{'id': 'first', 'season': '2027', 'round': 1, 'current_owner_team_id': 'b', 'original_team_id': 'b', 'protections': 'unprotected'}]
        row = {'id': 'pick', 'kind': 'picks', 'round': 1, 'from': 1, 'through': 1, 'protection': 'unprotected', 'quality': 'any'}
        asset = {'kind': 'pick', 'id': 'first'}
        self.assertEqual(wants.match_want(data, 'a', row, asset)['status'], 'exact')
        data['draft_picks'][0]['protections'] = 'top-10 protected'
        self.assertEqual(wants.match_want(data, 'a', row, asset)['status'], 'none')
        self.assertEqual(wants.match_want(data, 'a', row, {'kind': 'pick_swap', 'id': 'first'})['status'], 'none')
        data['meta']['current_date'] = '2027-07-01'
        self.assertEqual(wants.match_want(data, 'a', row, asset)['status'], 'none')

    def test_package_premium_is_once_bounded_and_offsets_existing_fit(self):
        data = self.fixture()
        data['team_trade_wants']['a']['entries'] = [self.player_want(), self.player_want(id='dup')]
        asset = {'kind': 'player', 'id': 'p'}
        with patch.object(wants, 'player_facts', return_value={'range': 91}), \
             patch.object(tx, 'market_trade_target_value', return_value=100), \
             patch.object(tx, 'team_fit_for_player', return_value=0):
            result = wants.package_preference(data, 'a', [asset, asset])
        self.assertEqual(result['adjustment'], 4)
        self.assertEqual(len(result['matches']), 1)
        with patch.object(wants, 'player_facts', return_value={'range': 91}), \
             patch.object(tx, 'market_trade_target_value', return_value=80), \
             patch.object(tx, 'team_fit_for_player', return_value=3):
            self.assertEqual(wants.package_preference(data, 'a', [asset])['adjustment'], 1)

    def test_rejected_roster_upgrade_cannot_get_bonus_from_headline_ovr(self):
        data = self.fixture()
        data['team_trade_wants']['a']['entries'] = [{'id': 'up', 'kind': 'upgrade', 'target_player_id': 'old', 'conditions': [], 'positions': []}]
        with patch.object(wants, 'player_facts', side_effect=lambda c,p: {'overall': 90 if p['id'] == 'p' else 80}), \
             patch.object(tr, 'roster_projection', return_value={'strength': 70, 'rotation': {'p': 30}}), \
             patch.object(tx, 'team_fit_for_player', return_value=0):
            self.assertEqual(wants.package_preference(data, 'a', [{'kind': 'player', 'id': 'p'}])['adjustment'], 0)

    def test_existing_contender_and_rebuilder_bonuses_are_not_counted_twice(self):
        data = self.fixture()
        data['player_asset_valuations'][0]['playoff_value'] = 80
        data['team_trade_wants']['a']['entries'] = [self.player_want()]
        with patch.object(wants, 'player_facts', return_value={'range': 91}), \
             patch.object(tx, 'market_trade_target_value', return_value=80), \
             patch.object(tx, 'team_fit_for_player', return_value=0):
            self.assertEqual(wants.package_preference(data, 'a', [{'kind':'player','id':'p'}])['adjustment'],0)
            custom = {'decision': {'contender_need_bonus': 1}}
            self.assertEqual(wants.package_preference(data, 'a', [{'kind':'player','id':'p'}], config=custom)['adjustment'],3)

    def test_cache_is_bounded_and_invalidated(self):
        data = self.fixture(); data['_allow_internal_caches'] = True
        data['team_trade_wants']['a']['entries'] = [self.player_want()]
        with patch.object(wants, 'player_facts', return_value={'range': 91}):
            self.assertTrue(wants.asset_matches(data, 'a', {'kind': 'player', 'id': 'p'}))
        wants.clear_wants_cache(data)
        self.assertNotIn('_trade_wants_match_cache', data)

    def test_reminder_is_deduplicated_persistent_and_does_not_remove_want(self):
        data = self.fixture(); data['players'][0]['team_id'] = 'a'
        data['team_trade_wants']['a'].update(entries=[self.player_want()], reminder_seen=['player:old'])
        saved = {'team_trade_wants': deepcopy(data['team_trade_wants'])}
        with patch.object(wants, 'player_facts', return_value={'range': 91}), patch.object(tx, 'tradeable_picks_for_team', return_value=[]):
            first = wants.wants_payload(data, saved, 'a')
            second = wants.wants_payload(data, json.loads(json.dumps(saved)), 'a')
            self.assertEqual(first, second)
            self.assertEqual(len(first['reminder']), 1)
            self.assertEqual(len(saved['team_trade_wants']['a']['entries']), 1)
            saved['team_trade_wants']['a']['reminder_seen'].append('player:p')
            self.assertEqual(wants.wants_payload(data, saved, 'a')['reminder'], [])

    def test_departed_upgrade_target_can_remind_but_never_keep_matching_market(self):
        data = self.fixture(); data['players'][1]['team_id'] = 'b'
        row = {'id': 'up', 'kind': 'upgrade', 'target_player_id': 'old', 'positions': [], 'conditions': [],
               'target_snapshot': {'positions': ['SF'], 'facts': {'overall': 75}}}
        with patch.object(wants, 'player_facts', return_value={'overall': 85}):
            self.assertEqual(wants.match_want(data, 'a', row, {'kind': 'player', 'id': 'p'})['status'], 'none')
            self.assertEqual(wants.match_want(data, 'a', row, {'kind': 'player', 'id': 'p'}, acquired=True)['status'], 'exact')

    def test_actions_authorize_validate_revision_and_do_not_mutate_on_read(self):
        from nba_gm_data import app_actions as app
        data = self.fixture()
        saved = {'meta': {'user_team_id': 'a'}, 'team_trade_wants': data['team_trade_wants']}
        with patch.object(app, 'load_save', return_value=saved), \
             patch.object(app, 'dashboard_read_context', return_value={'save': saved, 'active': data}), \
             patch.object(app, 'ensure_league_save_defaults', side_effect=lambda s,c:s), \
             patch.object(app, 'canonical_with_save', return_value=data), \
             patch.object(app, 'with_transaction_context', side_effect=lambda c:c), \
             patch.object(app, 'resolve_team', side_effect=lambda c,q: next(t for t in c['teams'] if t['abbrev']==q)), \
             patch.object(app, 'write_save') as write, \
             patch.object(tx, 'tradeable_picks_for_team', return_value=[]):
            read = app.team_wants_action({}, Path('unused'), {'team': 'A'})
            self.assertTrue(read['editable']);write.assert_not_called()
            for payload in ({'team':'B','entries':[]}, {'team':'A','entries':[], 'revision':9},
                            {'team':'A','entries':[self.player_want(positions=['BAD'])]}):
                with self.assertRaises(app.AppActionError):
                    app.team_wants_action({}, Path('unused'), payload, 'set_team_wants')
            write.assert_not_called()
            result=app.team_wants_action({}, Path('unused'), {'team':'A','entries':[self.player_want()],'revision':1}, 'set_team_wants')
            self.assertEqual(result['revision'],2)
            self.assertEqual(len(result['entries']),1)
            self.assertEqual(write.call_count,1)

    def test_redundant_centers_differ_from_replacement_and_injury_cover(self):
        data = self.fixture()
        data['players'] = [{'id': 'gobert', 'team_id': 'b', 'position': 'C'}, {'id': 'zubac', 'team_id': 'a', 'position': 'C'}, {'id': 'guard', 'team_id': 'a', 'position': 'PG'}]
        before = {'strength': 75, 'retained_ids': ['zubac', 'guard'], 'rotation': {'zubac': 32, 'guard': 30}}
        after = {'strength': 75.1, 'retained_ids': ['zubac', 'gobert'], 'rotation': {'zubac': 24, 'gobert': 24}}
        with patch.object(wants, 'player_facts', return_value={'overall': 85, 'spacing': 25}):
            redundant = tr.role_opportunity_outlook(data, 'a', {'gobert'}, {'guard'}, before, after)
            self.assertLess(redundant['adjustment'], 0)
            self.assertTrue(redundant['conflicts'])
            replacement = tr.role_opportunity_outlook(data, 'a', {'gobert'}, {'zubac'}, before, after)
            self.assertEqual(replacement['adjustment'], 0)
            data['_trade_planning_save']['health_states'] = [{'player_id': 'zubac', 'availability_status': 'out', 'return_date': '2027-05-01'}]
            self.assertEqual(tr.role_opportunity_outlook(data, 'a', {'gobert'}, {'guard'}, before, after)['adjustment'], 0)

    def test_forecast_centers_share_48_minutes_without_touching_real_rotations(self):
        data = self.fixture()
        rows = [{'id': 'c1', 'position': 'C', 'minutes_projection': 40}, {'id': 'c2', 'position': 'C', 'minutes_projection': 36}]
        rows += [{'id': f'g{i}', 'position': 'SG', 'minutes_projection': 32.8} for i in range(5)]
        rotation = {'players': rows, 'traits': []}
        original = deepcopy(rotation)
        with patch.object(wants, 'player_facts', return_value={'spacing': 50}):
            result = tr.constrain_center_opportunity(data, rotation)
        self.assertEqual(rotation, original)
        self.assertAlmostEqual(sum(p['minutes_projection'] for p in result['players'] if p['position']=='C'), 48)
        self.assertAlmostEqual(sum(p['minutes_projection'] for p in result['players']), 240)

    def test_multi_team_matching_follows_the_actual_recipient_not_leg_order(self):
        from test_multi_team_trades import fixture, legs
        from nba_gm_data.multi_team_trades import evaluate_multi_team_trade
        data = fixture()
        data['team_trade_wants'] = {'a': {'entries': [self.player_want(positions=[], conditions=[])]},
                                   'b': {'entries': []}, 'c': {'entries': []}}
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c,config=None:c):
            result = evaluate_multi_team_trade(data, legs(), seed=17, date='2027-01-31')
        matches = {(m['team_id'], m['asset_id']) for m in result['wants_matches']}
        self.assertIn(('a', 'b0'), matches)
        self.assertNotIn(('a', 'b1'), matches)
        self.assertNotIn(('b', 'b0'), matches)


if __name__ == '__main__':
    unittest.main()
