from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import transactions as tx
from nba_gm_data.multi_team_trades import evaluate_multi_team_trade, facilitator_candidates
from nba_gm_data.save import load_save, write_save


def fixture(teams='abc'):
    data = {'meta': {'active_season': '2026-27', 'current_date': '2027-01-31'},
            'teams': [{'id': t, 'abbrev': t.upper(), 'name': t.upper()} for t in teams],
            'players': [], 'contracts': [], 'traits': [], 'draft_picks': [], 'pick_obligations': [],
            'front_office_profiles': [{'team_id': t} for t in teams], 'trade_block_entries': [],
            'team_strategic_states': [{'team_id': t, 'phase': 'rebuilding', 'window_phase': 'rebuilding',
                'needs': ['playoff_rotation'], 'excesses': [], 'pressure': 50, 'core_age': 27, 'youth_pipeline': 20} for t in teams],
            'player_asset_valuations': [], '_strategy_model_version': tx.STRATEGY_MODEL_VERSION}
    for tid in teams:
        for i in range(13):
            pid = tid+str(i)
            quality, price, salary, minutes = (25, 15, 1_000_000, 18) if tid == 'c' else (50, 30, 1_000_000, 18)
            if tid == 'a':
                salary = 16_250_000
            if pid == 'a0':
                quality, price, salary, minutes = 76, 90, 10_000_000, 32
            if pid == 'b0':
                quality, price, salary, minutes = 74, 76, 15_000_000, 30
            if pid == 'b1':
                quality, price, salary, minutes = 32, 35, 15_000_000, 6
            data['players'].append({'id': pid, 'name': pid, 'normalized_name': pid, 'team_id': tid, 'age': 27,
                'position': ('PG', 'SG', 'SF', 'PF', 'C')[i % 5], 'minutes_projection': minutes,
                'overall': max(70, quality), 'current_ability': max(70, quality)})
            data['contracts'].append({'player_id': pid, 'team_id': tid, '_active_season': '2026-27',
                'seasons': [{'season': '2026-27', 'salary': salary}]})
            data['player_asset_valuations'].append({'player_id': pid, 'team_id': tid,
                'on_court_value': quality, 'player_value': price, 'playoff_value': 75,
                'contract_surplus': 0, 'development_upside': 0, 'health_risk': 0, 'role_scarcity': 0})
            # Settlement fixtures need real skill differences too: otherwise
            # the planner correctly sees no benefit in spending picks on them.
            data['traits'].extend({'player_id': pid, 'trait_key': key, 'value': quality} for key in (
                'shooting_range', 'shot_versatility', 'handle_pressure', 'rim_pressure', 'passing_reads',
                'defensive_effort', 'rim_deterrence', 'scheme_iq', 'portability', 'playoff_translation',
                'stamina_cardio', 'foot_speed_lateral_agility', 'screen_navigation', 'release_speed',
                'offensive_rebounding'))
    for tid in teams:
        for year, rnd in ((2028, 1), (2030, 1), (2032, 1), (2029, 2)):
            data['draft_picks'].append({'id': f'{tid}{year}r{rnd}', 'season': str(year), 'round': rnd,
                'current_owner_team_id': tid, 'original_team_id': tid, 'projected_pick_slot': 60 if rnd == 2 else 20,
                'status': 'future', 'protection_summary': 'unprotected'})
    return data


def settled_fixture():
    """The three-team fixture with a deal all three teams accept. Team A used to clear its threshold only through a
    flat +7 for receiving C's 2029 second; that pick now adds a share of its value (trade step 2), so A's departing
    player is made a little weaker instead (his skill inputs 74 instead of 76)."""
    data = fixture()
    for trait in data['traits']:
        if trait['player_id'] == 'a0':
            trait['value'] = 74
    return data


def legs():
    return [{'from_team_id': 'a', 'to_team_id': 'b', 'assets': [{'kind': 'player', 'value': 'a0'}]},
            {'from_team_id': 'b', 'to_team_id': 'a', 'assets': [{'kind': 'player', 'value': 'b0'}]},
            {'from_team_id': 'b', 'to_team_id': 'c', 'assets': [{'kind': 'player', 'value': 'b1'}]},
            {'from_team_id': 'c', 'to_team_id': 'a', 'assets': [{'kind': 'pick', 'value': 'c2029r2'}]}]


def saved(candidate):
    return {'version': 'league_save_v1', 'meta': {'user_team_id': 'human', 'season': '2026-27'},
            'state': {'current_date': '2027-01-31', 'phase': 'regular_season'},
            'pending_trade_proposals': [candidate], 'transaction_logs': [],
            'roster_overrides': {}, 'contract_overrides': {}, 'draft_pick_overrides': {}}


class MultiTeamTradeTests(unittest.TestCase):
    def setUp(self):
        # Hold synthetic scouting values fixed, while still rebuilding live
        # ownership, salaries and every team's actual acceptance calculation.
        original = tx.with_transaction_context
        def prepared(data, config=None):
            data = deepcopy(data)
            reference = fixture(''.join(t['id'] for t in data['teams']))
            for field in ('player_asset_valuations', 'team_strategic_states', 'front_office_profiles', 'trade_block_entries'):
                data[field] = reference[field]
            data['_strategy_model_version'] = tx.STRATEGY_MODEL_VERSION
            return original(data, config)
        self.context_patch = patch.object(tx, 'with_transaction_context', side_effect=prepared)
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)

    def test_combined_salaries_are_legal_when_a_bilateral_intermediate_is_not(self):
        data = fixture()
        direct = tx.evaluate_trade(data, 'A', 'B', [{'kind': 'player', 'value': 'a0'}],
            [{'kind': 'player', 'value': 'b0'}, {'kind': 'player', 'value': 'b1'}], date='2027-01-31')
        self.assertEqual(direct['legality']['status'], 'illegal')
        result = evaluate_multi_team_trade(data, legs(), date='2027-01-31')
        self.assertEqual(result['legality']['status'], 'legal', result['legality'])
        self.assertEqual(len(result['evaluations']), 3)
        self.assertTrue(result['accepted_by_all'], result['evaluations'])

    def test_actual_facilitator_search_finds_an_all_party_approved_solution(self):
        data = fixture()
        direct = tx.evaluate_trade(data, 'A', 'B', [{'kind': 'player', 'value': 'a0'}],
            [{'kind': 'player', 'value': 'b0'}, {'kind': 'player', 'value': 'b1'}], date='2027-01-31')
        diag = {}
        results = facilitator_candidates(tx.with_transaction_context(data), direct, seed=1, date='2027-01-31', diagnostics=diag)
        self.assertTrue(results, diag)
        self.assertTrue(all(c['accepted_by_all'] for c in results))

    def test_facilitator_probes_defer_presentation_until_a_candidate_is_kept(self):
        from nba_gm_data import multi_team_trades as mt
        data = tx.with_transaction_context(fixture())
        direct = tx.evaluate_trade(data, 'A', 'B', [{'kind': 'player', 'value': 'a0'}],
            [{'kind': 'player', 'value': 'b0'}, {'kind': 'player', 'value': 'b1'}], date='2027-01-31')
        with patch.object(tx, 'trade_value_breakdown', side_effect=AssertionError('Chart built during search')), \
             patch.object(tx, 'package_value_breakdown', side_effect=AssertionError('Explanation built during search')), \
             patch.object(tx, 'evaluation_notes', side_effect=AssertionError('Narrative built during search')), \
             patch.object(tx, 'trade_headline_from_payload', side_effect=AssertionError('Summary built during search')):
            compact = mt.facilitator_candidates(data, direct, seed=1, date='2027-01-31', include_presentation=False)
        self.assertTrue(compact)
        candidate = compact[0]
        self.assertTrue(candidate['accepted_by_all'])
        self.assertEqual(candidate['search_route'], 'salary_facilitator')
        self.assertNotIn('value_breakdown', candidate)
        self.assertNotIn('summary', candidate)
        shown = tx.prepare_ai_trade_candidate(data, candidate, seed=1, date='2027-01-31')
        self.assertEqual(shown['search_route'], 'salary_facilitator')
        reference = mt.evaluate_multi_team_trade(data, candidate['proposal']['transfers'],
            pick_rules=candidate.get('pick_rules'), seed=1, date='2027-01-31',
            proposal_id=candidate['proposal']['id'])
        self.assertEqual(shown['value_breakdown'], reference['value_breakdown'])
        self.assertEqual(shown['evaluations'], reference['evaluations'])
        self.assertEqual(shown['wants_matches'], reference['wants_matches'])
        self.assertEqual(shown['summary'], reference['summary'])

    def test_rejected_ai_bilateral_candidate_skips_all_presentation_builders(self):
        data = fixture()
        data['trade_block_entries'] = [{'player_id': 'a0', 'block_score': 100}]
        buyer = next(team for team in data['teams'] if team['id'] == 'b')
        with patch.object(tx, 'with_transaction_context', side_effect=lambda value, config=None: value), \
             patch.object(tx, 'with_spatial_fit_context', side_effect=lambda value: value), \
             patch.object(tx, 'trade_search_context', side_effect=lambda value: {**value, '_trade_search_roles': {}, '_trade_search_rosters': {}}), \
             patch.object(tx, 'recently_traded_player_ids', return_value=set()), \
             patch.object(tx, 'buyer_teams_for_player', return_value=[buyer]), \
             patch.object(tx, 'buyer_offer_package_options', return_value=[{'assets': [{'kind': 'player', 'value': 'b1'}]}]), \
             patch.object(tx, 'trade_value_breakdown', side_effect=AssertionError('Chart built for rejected offer')), \
             patch.object(tx, 'package_value_breakdown', side_effect=AssertionError('Explanation built for rejected offer')), \
             patch.object(tx, 'trade_evaluation_payload', side_effect=AssertionError('Presentation payload built for rejected offer')), \
             patch.object(tx, 'evaluation_notes', side_effect=AssertionError('Narrative built for rejected offer')), \
             patch.object(tx, 'proposal_summary', side_effect=AssertionError('Summary built for rejected offer')), \
             patch.object(tx, 'candidate_from_evaluation', side_effect=AssertionError('Public candidate built for rejected offer')):
            result = tx.simulate_ai_trades(data, '2027-01-31', '2027-01-31', seed=9, limit=1, target_search=False)
        self.assertEqual(result['proposal_count'], 0)
        self.assertEqual(result['search_diagnostics']['packages'], 1)
        self.assertGreaterEqual(result['search_diagnostics']['declined'], 1)

    def test_incoming_offer_search_returns_full_presentation_for_the_retained_offer(self):
        data = fixture()
        data['_human_team_ids'] = ['a']
        data['trade_block_entries'] = [{'player_id': 'b0', 'block_score': 100, 'team_id': 'b'}]
        with patch.object(tx, 'with_transaction_context', side_effect=lambda value, config=None: value), \
             patch.object(tx, 'ai_trade_candidate_accepted', return_value=True):
            result = tx.simulate_ai_trades(data, '2027-01-31', '2027-01-31', seed=9, limit=1,
                                           involving_team_ids={'a'})
        self.assertEqual(result['proposal_count'], 1)
        candidate = result['proposals'][0]
        self.assertEqual(candidate['proposal']['to_team_id'], 'a')
        self.assertIn('value_breakdown', candidate)
        self.assertTrue(candidate['value_breakdown']['from_team_receives']['asset_details'])
        self.assertTrue(all(evaluation['notes'] for evaluation in candidate['evaluations']))
        base_id = candidate.get('evaluation_proposal_id') or candidate['proposal']['id']
        snapshot = tx.trade_search_context(tx.with_spatial_fit_context(data))
        pick_terms = candidate.get('pick_trade_terms') or candidate.get('pick_obligation_terms')
        if pick_terms:
            snapshot = tx.canonical_with_pending_pick_terms(snapshot, pick_terms)
        report = tx._evaluate_trade_snapshot(snapshot, 'B', 'A',
            [{'kind': asset['kind'], 'value': asset['id']} for asset in candidate['proposal']['from_assets']],
            [{'kind': asset['kind'], 'value': asset['id']} for asset in candidate['proposal']['to_assets']],
            seed=9, date='2027-01-31', config=None, context_ready=True,
            include_presentation=True, proposal_id=base_id)
        if pick_terms:
            report = tx.trade_result_with_pick_terms(report, pick_terms)
        expected = tx.candidate_from_evaluation(snapshot, report)
        expected = tx.mark_ai_trade_accepted(expected)
        self.assertEqual(candidate['value_breakdown'], expected['value_breakdown'])
        self.assertEqual(candidate['evaluations'], expected['evaluations'])

    def test_retained_protected_pick_offer_keeps_the_full_snapshot_explanation(self):
        from nba_gm_data.trade_pick_terms import compile_pick_rules
        data = tx.with_transaction_context(fixture())
        rules = [{'type': 'protected_pick', 'pick_id': 'b2028r1', 'from': 1, 'through': 4,
                  'fallback_pick_ids': ['b2030r1']}]
        snapshot, assets, terms = compile_pick_rules(data, rules, [
            {'team': 'a', 'recipient': 'b', 'assets': [{'kind': 'player', 'value': 'a0'}]},
            {'team': 'b', 'recipient': 'a', 'assets': [{'kind': 'pick', 'value': 'b2028r1'}]},
        ])
        expected_report = tx.evaluate_trade(snapshot, 'A', 'B', assets[0], assets[1],
            seed=23, date='2027-01-31', context_ready=True)
        expected_report = tx.trade_result_with_pick_terms(expected_report, terms)
        expected = tx.candidate_from_evaluation(snapshot, expected_report)
        compact_report = tx.evaluate_trade_decision(snapshot, 'A', 'B', assets[0], assets[1],
            seed=23, date='2027-01-31', context_ready=True)
        compact_report = tx.trade_result_with_pick_terms(compact_report, terms)
        compact = tx.candidate_from_decision(compact_report)
        shown = tx.prepare_ai_trade_candidate(snapshot, compact, seed=23, date='2027-01-31')
        self.assertEqual(shown['pick_obligation_terms'], expected['pick_obligation_terms'])
        self.assertEqual(shown['proposal'], expected['proposal'])
        self.assertEqual(shown['evaluations'], expected['evaluations'])
        self.assertEqual(shown['value_breakdown'], expected['value_breakdown'])
        self.assertEqual(shown['wants_matches'], expected['wants_matches'])

    def test_receive_only_and_send_only_participants_are_illegal(self):
        data = fixture()
        receive_only = legs()[:3]+[{'from_team_id': 'b', 'to_team_id': 'c',
                                  'assets': [{'kind': 'pick', 'value': 'b2029r2'}]}]
        send_only = [legs()[0], legs()[1], legs()[3]]
        for package, message in [(receive_only, 'C must send'), (send_only, 'C must receive')]:
            with self.subTest(message=message):
                result = evaluate_multi_team_trade(data, package, date='2027-01-31')
                self.assertEqual(result['legality']['status'], 'illegal')
                self.assertTrue(any(message in issue for issue in result['legality']['issues']))
                self.assertFalse(result['accepted_by_all'])

    def test_old_free_recipient_offer_cannot_execute_with_forged_approval(self):
        data = fixture()
        package = legs()[:3]+[{'from_team_id': 'b', 'to_team_id': 'c',
                              'assets': [{'kind': 'pick', 'value': 'b2029r2'}]}]
        candidate = evaluate_multi_team_trade(data, package, date='2027-01-31')
        candidate.update(accepted_by_all=True, legality={'status': 'legal', 'issues': [], 'manual_review': []})
        for evaluation in candidate['evaluations']:
            evaluation.update(accepted=True, decision='accept')
        self.assertFalse(tx.ai_trade_candidate_accepted(data, candidate))
        state = saved(json.loads(json.dumps(candidate))); before = deepcopy(state)
        result = tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)
        self.assertEqual(result['status'], 'not_applied_salary_legality')
        self.assertTrue(any('C must send' in issue for issue in result['legality']['issues']))
        self.assertEqual(state, before)

    def test_compensated_salary_absorber_returns_a_real_owned_asset(self):
        from nba_gm_data import multi_team_trades as mt
        data = tx.with_transaction_context(fixture())
        direct = tx.evaluate_trade(data, 'A', 'B', [{'kind': 'player', 'value': 'a0'}],
            [{'kind': 'player', 'value': 'b0'}, {'kind': 'player', 'value': 'b1'}], date='2027-01-31')
        original = mt.evaluate_multi_team_trade
        observed = []

        def inspect(context, package, **kwargs):
            for tid, outgoing, incoming in tx.trade_team_flows({'transfers': package}):
                if tid == 'c' and any(a['kind'] == 'player' for a in incoming) and any(a['kind'] == 'pick' for a in incoming):
                    observed.append(deepcopy(outgoing))
            return original(context, package, **kwargs)

        with patch.object(mt, 'evaluate_multi_team_trade', side_effect=inspect):
            mt.facilitator_candidates(data, direct, seed=1, date='2027-01-31', limit=100)
        self.assertTrue(observed)
        for outgoing in observed:
            self.assertEqual(len(outgoing), 1)
            asset = outgoing[0]
            identifier = asset.get('id') or asset['value']
            if asset['kind'] == 'player':
                self.assertEqual(tx.player_by_id(data, identifier)['team_id'], 'c')
            else:
                pick = tx.pick_by_id(data, identifier)
                self.assertEqual(pick['current_owner_team_id'], 'c')
                self.assertEqual(pick['round'], 2)
                self.assertFalse(pick.get('_obligation_locked'))

        observed.clear()
        for player in data['players']:
            if player.get('team_id') == 'c':
                player['_inactive_player'] = True
        tradable = tx.tradeable_picks_for_team
        with patch.object(tx, 'tradeable_picks_for_team', side_effect=lambda c, tid: [p for p in tradable(c, tid)
                if tid != 'c' or p['round'] != 2]), \
             patch.object(mt, 'evaluate_multi_team_trade', side_effect=inspect):
            mt.facilitator_candidates(data, direct, seed=1, date='2027-01-31', limit=100)
        self.assertFalse(observed)

    def test_nominal_swap_return_costs_less_than_a_full_second_and_settles(self):
        from nba_gm_data.multi_team_trades import facilitator_return_options
        data = tx.with_transaction_context(fixture())
        options = facilitator_return_options(data, 'c', 'a', set())
        swap = next(option for option in options if option['rules'])
        primary = tx.pick_by_id(data, swap['asset']['value'])
        self.assertLess(swap['value'], tx.pick_asset_value(primary, 'neutral'))
        package = legs()[:3]+[
            {'from_team_id': 'b', 'to_team_id': 'c', 'assets': [{'kind': 'pick', 'value': 'b2029r2'}]},
            {'from_team_id': 'c', 'to_team_id': 'a', 'assets': [swap['asset']]},
        ]
        candidate = evaluate_multi_team_trade(data, package, pick_rules=swap['rules'], date='2027-01-31')
        self.assertEqual(candidate['legality']['status'], 'legal', candidate['legality'])
        term = candidate['pick_obligation_terms'][0]
        self.assertEqual(term['type'], 'pick_swap')
        self.assertEqual(term['sender_team_id'], 'c')
        self.assertEqual(term['receiver_team_id'], 'a')
        self.assertEqual(term['primary_pick_id'], primary['id'])
        no_picks = fixture()
        no_picks['draft_picks'] = [p for p in no_picks['draft_picks'] if p['current_owner_team_id'] != 'c']
        fringe = facilitator_return_options(no_picks, 'c', 'a', set())
        self.assertTrue(fringe)
        self.assertTrue(all(option['asset']['kind'] == 'player' for option in fringe))

    def test_all_assets_and_one_ledger_record_settle_together_and_replay_does_nothing(self):
        data = settled_fixture()
        candidate = evaluate_multi_team_trade(data, legs(), date='2027-01-31')
        state = saved(candidate)
        original = deepcopy(data)
        result = tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)
        self.assertEqual(result['status'], 'applied', result)
        self.assertEqual({k: state['roster_overrides'][k] for k in ('a0', 'b0', 'b1')}, {'a0': 'b', 'b0': 'a', 'b1': 'c'})
        self.assertEqual(state['draft_pick_overrides']['c2029r2'], 'a')
        self.assertEqual(len(state['transaction_logs']), 1)
        self.assertEqual(state['transaction_logs'][0]['teams'], ['a', 'b', 'c'])
        before = deepcopy(state)
        self.assertEqual(tx.apply_trade_to_state(state, candidate['proposal']['id'], canonical=data)['status'], 'not_found')
        self.assertEqual(state, before)
        self.assertEqual(data['players'], original['players'])

    def test_stale_third_team_assets_and_salary_changes_are_failure_atomic(self):
        for change in ('pick', 'salary', 'refusal'):
            data = fixture()
            candidate = evaluate_multi_team_trade(data, legs(), date='2027-01-31')
            state = saved(candidate)
            if change == 'pick':
                state['draft_pick_overrides']['c2029r2'] = 'b'
            elif change == 'salary':
                state['contract_overrides']['b1'] = {'seasons': [{'season': '2026-27', 'salary': 300_000_000}]}
            else:
                state['roster_overrides']['b1'] = 'a'
            before = deepcopy(state)
            result = tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)
            self.assertNotEqual(result['status'], 'applied')
            self.assertEqual(state, before)

    def test_duplicate_assets_unknown_teams_and_disconnected_packages_fail(self):
        data = fixture()
        duplicate = legs()+[legs()[0]]
        self.assertEqual(evaluate_multi_team_trade(data, duplicate)['legality']['status'], 'illegal')
        with self.assertRaises(ValueError):
            evaluate_multi_team_trade(data, [{'from_team_id': 'a', 'to_team_id': 'unknown', 'assets': [{'kind': 'player', 'value': 'a0'}]}]*3)

    def test_a_forged_accepted_flag_does_not_override_current_ai_refusal(self):
        data = fixture()
        bad = legs(); bad[3]['to_team_id'] = 'b'
        candidate = evaluate_multi_team_trade(data, bad, date='2027-01-31')
        candidate['accepted_by_all'] = True
        state = saved(candidate); before = deepcopy(state)
        result = tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)
        self.assertEqual(result['status'], 'not_applied_rejected')
        self.assertEqual(state, before)

    def test_auto_protections_lock_real_fallbacks_and_change_value(self):
        data = tx.with_transaction_context(fixture())
        buyer, seller = tx.resolve_team(data, 'A'), tx.resolve_team(data, 'B')
        primary = tx.pick_by_id(data, 'a2028r1')
        options = tx.ai_pick_protection_options(data, buyer, seller, primary)
        self.assertEqual(len(options), 2)
        self.assertEqual({o['term']['protected_range']['through'] for o in options}, {4, 10})
        for option in options:
            self.assertEqual(option['term']['fallback_pick_ids'], ['a2030r1'])
            self.assertNotEqual(option['value'], tx.pick_asset_value(primary, 'neutral'))
        primary['protection_summary'] = 'top-5 protected'
        self.assertEqual(tx.ai_pick_protection_options(data, buyer, seller, primary), [])

    def test_human_consent_is_required_and_cannot_hide_behind_forged_participant_ids(self):
        data = fixture()
        candidate = evaluate_multi_team_trade(data, legs(), date='2027-01-31')
        candidate['proposal']['team_ids'] = ['b', 'c']
        state = saved(candidate); state['meta']['user_team_id'] = 'a'
        before = deepcopy(state)
        self.assertEqual(tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)['status'], 'not_applied_rejected')
        self.assertEqual(state, before)
        candidate['offer_context'] = {'status': 'user_override_pending_apply', 'created_by_user': True, 'override_team_id': 'a'}
        result = tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)
        self.assertEqual(result['status'], 'applied', result)
        self.assertEqual(result['transaction_log']['teams'], ['a', 'b', 'c'])

    def test_multi_team_protection_and_new_swap_survive_serialization_and_settlement(self):
        for kind in ('protected_pick', 'pick_swap'):
            data = fixture()
            package = legs()+[{'from_team_id': 'a', 'to_team_id': 'c', 'assets': [{'kind': 'pick', 'value': 'a2028r1'}]}]
            rule = {'type': kind, 'pick_id': 'a2028r1'}
            rule.update({'from': 1, 'through': 4, 'fallback_pick_ids': ['a2030r1']} if kind == 'protected_pick'
                        else {'other_pick_id': 'c2028r1', 'benefit': 'better'})
            candidate = evaluate_multi_team_trade(data, package, pick_rules=[rule], date='2027-01-31')
            candidate['offer_context'] = {'status': 'user_override_pending_apply', 'created_by_user': True, 'override_team_id': 'a'}
            state = json.loads(json.dumps(saved(candidate))); state['meta']['user_team_id'] = 'a'
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'save.json'; write_save(path, state); state = load_save(path)
                result = tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)
            self.assertEqual(result['status'], 'applied', result)
            self.assertEqual(len(state['pick_obligations']), 1)
            self.assertEqual(state['pick_obligations'][0]['type'], kind)
            if kind == 'protected_pick':
                self.assertIn('a2030r1', state['locked_pick_assets'])
                self.assertEqual(state['draft_pick_overrides']['a2028r1'], 'c')
            else:
                self.assertNotIn('a2028r1', state['draft_pick_overrides'])
                self.assertEqual(state['pick_obligations'][0]['current_rights_holder_team_id'], 'c')

    def test_mid_settlement_exception_does_not_leave_any_partial_player_transfers(self):
        data = settled_fixture(); candidate = evaluate_multi_team_trade(data, legs(), date='2027-01-31')
        state = saved(candidate); before = deepcopy(state)
        with patch.object(tx, 'update_retraded_pick_obligation', side_effect=RuntimeError('injected failure')):
            with self.assertRaises(RuntimeError):
                tx.apply_trade_to_state(state, candidate['proposal']['id'], date='2027-01-31', canonical=data)
        self.assertEqual(state, before)

    def test_four_and_six_team_connected_graphs_validate_every_participant(self):
        for teams in ('abcd', 'abcdef'):
            data = fixture(teams)
            package = [{'from_team_id': tid, 'to_team_id': teams[(i+1) % len(teams)],
                        'assets': [{'kind': 'pick', 'value': f'{tid}2029r2'}]} for i, tid in enumerate(teams)]
            result = evaluate_multi_team_trade(data, package, seed=7)
            self.assertEqual(result['legality']['status'], 'legal')
            self.assertEqual({e['perspective_team_id'] for e in result['evaluations']}, set(teams))
            self.assertEqual(result, evaluate_multi_team_trade(data, package, seed=7))
        disconnected = package[:2]+[{'from_team_id': 'c', 'to_team_id': 'd', 'assets': [{'kind': 'pick', 'value': 'c2029r2'}]}]
        # A->B->C->D remains connected; two independent pairs do not.
        disconnected[1]['to_team_id'] = 'a'
        with self.assertRaisesRegex(ValueError, 'connected'):
            evaluate_multi_team_trade(data, disconnected)

    def test_app_action_rechecks_a_serialized_graph_and_commits_only_on_success(self):
        from nba_gm_data import app_actions as aa
        data = fixture(); data['_human_team_ids'] = ['a']
        candidate = evaluate_multi_team_trade(data, legs(), date='2027-01-31')
        state = saved(candidate); state['meta']['user_team_id'] = 'a'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'career.json'; write_save(path, state)
            with patch.object(aa, 'ensure_league_save_defaults', side_effect=lambda s,*_:s), \
                 patch.object(aa, 'active_canonical', return_value=data), \
                 patch.object(aa, 'home_payload', return_value={}):
                result = aa.apply_trade_candidate_action(data, path, {'candidate': json.loads(json.dumps(candidate))})
                self.assertEqual(result['status'], 'applied', result)
                self.assertEqual(len(load_save(path)['transaction_logs']), 1)
                before = path.read_bytes()
                again = aa.apply_trade_candidate_action(data, path, {'candidate': candidate})
                self.assertNotEqual(again['status'], 'applied')
                self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
