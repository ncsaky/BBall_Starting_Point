from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from nba_gm_data import release_planning as rp, save as sv, waivers as w, transactions as tx
import test_waivers


class ReleasePlanningTests(unittest.TestCase):
    def fixture(self, stamp='2036-07-01', salary=20_000_000):
        data, saved, player = test_waivers.WaiverTests().fixture()
        saved['state']['current_date'] = stamp
        saved['meta']['human_team_ids'] = ['ai', 'human']
        contract = next(c for c in data['contracts'] if c['player_id'] == player['id'])
        for row in contract['seasons']:
            row.update(salary=salary, guaranteed_salary=salary)
        entry = w.request_waiver(data, saved, player, 'human', stamp)
        saved['state']['current_date'] = entry['clearance_date']
        w.process_waivers(data, saved, entry['clearance_date'])
        return data, saved, player, entry

    def test_two_remaining_years_stretch_over_five_and_preserve_total(self):
        data, saved, player, entry = self.fixture()
        quote = rp.elect_stretch(sv.canonical_with_save(data, saved), saved, entry['id'], '2036-07-03')
        self.assertTrue(quote['ok'], quote)
        self.assertEqual(quote['years'], 5)
        self.assertEqual([r['salary'] for r in quote['cap_charges']], [8_000_000]*5)
        self.assertEqual(sum(r['salary'] for r in quote['cap_charges']), 40_000_000)
        self.assertEqual(saved['waived_salary_obligations'][0]['pre_stretch_seasons'][0]['salary'], 20_000_000)
        self.assertEqual(sv.team_cap_summary(sv.canonical_with_save(data, saved), saved, 'human')['waived_salary_millions'], 8)
        before = deepcopy(saved)
        self.assertFalse(rp.elect_stretch(data, saved, entry['id'], '2036-07-03')['ok'])
        self.assertEqual(saved, before)

    def test_inseason_election_keeps_current_salary_and_only_stretches_future(self):
        data, saved, _, entry = self.fixture('2036-12-01')
        quote = rp.stretch_quote(data, saved, entry['id'], '2036-12-03')
        self.assertTrue(quote['ok'], quote)
        self.assertEqual(quote['years'], 3)
        self.assertEqual(quote['cap_charges'][0]['salary'], 20_000_000)
        self.assertEqual(quote['cap_charges'][1]['season'], '2037-38')
        self.assertAlmostEqual(sum(r['salary'] for r in quote['cap_charges']), 40_000_000)

    def test_final_season_deadline_and_unknown_protection_are_not_ignored(self):
        data, saved, _, entry = self.fixture()
        self.assertFalse(rp.stretch_quote(data, saved, entry['id'], '2037-09-01')['ok'])
        self.assertFalse(rp.stretch_quote(data, saved, entry['id'], '2038-07-01')['ok'])
        saved['waived_salary_obligations'][0]['unverified'] = True
        self.assertFalse(rp.stretch_quote(data, saved, entry['id'], '2036-07-03')['ok'])

    def test_aggregate_fifteen_percent_limit_and_rounding(self):
        data, saved, _, entry = self.fixture(salary=20_000_001)
        quote = rp.stretch_quote(data, saved, entry['id'], '2036-07-03')
        self.assertEqual(sum(r['salary'] for r in quote['cap_charges']), 40_000_002)
        saved['waived_salary_obligations'].append({'id': 'other', 'team_id': 'human',
            'seasons': [{'season': '2038-39', 'salary': 200_000_000}]})
        self.assertFalse(rp.stretch_quote(data, saved, entry['id'], '2036-07-03')['ok'])

    def test_claimed_or_pending_contract_is_not_stretched(self):
        data, saved, _, entry = self.fixture()
        for status in ('pending', 'claimed'):
            entry['status'] = status
            self.assertFalse(rp.stretch_quote(data, saved, entry['id'], '2036-07-03')['ok'])

    def test_reacquisition_guard_survives_reload_and_expires_on_original_end(self):
        data, saved, player, entry = self.fixture()
        rp.elect_stretch(data, saved, entry['id'], '2036-07-03')
        saved = json.loads(json.dumps(saved))
        self.assertTrue(rp.reacquisition_blocked(saved, 'human', player['id'], '2038-06-30'))
        self.assertFalse(rp.reacquisition_blocked(saved, 'human', player['id'], '2038-07-01'))
        self.assertFalse(rp.reacquisition_blocked(saved, 'ai', player['id'], '2037-01-01'))
        proposal = {'from_team_id': 'ai', 'to_team_id': 'human', 'from_assets': [{'kind': 'player', 'id': player['id']}], 'to_assets': []}
        self.assertTrue(any('stretched' in r for r in tx.trade_live_validation_issues(saved, proposal, '2037-01-01')))

    def test_minimum_exception_uses_original_term_and_all_years(self):
        data, saved, player = test_waivers.WaiverTests().fixture()
        c = next(c for c in data['contracts'] if c['player_id'] == player['id'])
        for row in c['seasons']:
            row.update(salary=1_900_000, guaranteed_salary=1_900_000)
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01')
        for contract in data['contracts']:
            if contract['team_id'] == 'ai':
                for row in contract['seasons']:
                    row['salary'] = 30_000_000
        active = sv.canonical_with_save(data, saved)
        self.assertTrue(w.claim_plan(active, saved, entry, 'ai', cut_id='ai14')['ok'])
        entry['contract']['seasons'][1]['salary'] = 15_000_000
        self.assertFalse(w.claim_plan(active, saved, entry, 'ai', cut_id='ai14')['ok'])
        entry['contract']['seasons'][1]['salary'] = 1_900_000
        entry['contract']['seasons'].insert(0, {'season': '2035-36', 'salary': 1_900_000})
        self.assertFalse(w.minimum_claim_contract(entry['contract']))

    def test_actual_minimum_signature_not_any_cheap_contract(self):
        self.assertTrue(w.minimum_claim_contract({'seasons': [{'season': '2025-26', 'salary': 3_634_153}]}))
        self.assertFalse(w.minimum_claim_contract({'seasons': [{'season': '2025-26', 'salary': 3_500_000}]}))
        self.assertTrue(w.minimum_claim_contract({'seasons': [{'season': '2025-26', 'salary': 1_272_870},
                                                            {'season': '2026-27', 'salary': 2_150_917}]}))

    def test_ai_claim_prices_expensive_future_year_despite_cheap_first_year(self):
        data, saved, player = test_waivers.WaiverTests().fixture()
        saved['meta']['human_team_ids'] = ['human']
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01')
        active = sv.canonical_with_save(data, saved)
        self.assertTrue(w.claim_plan(active, saved, entry, 'ai', ai=True)['ok'])
        entry['contract']['seasons'][1]['salary'] = 100_000_000
        result = w.claim_plan(active, saved, entry, 'ai', ai=True)
        self.assertFalse(result['ok'])
        self.assertIn('Remaining contract', result['reason'])
        self.assertEqual(result['contract_cost']['remaining_salary_millions'], 102)
        entry['contract']['seasons'][1]['option_type'] = 'team_option'
        self.assertTrue(w.claim_plan(active, saved, entry, 'ai', ai=True)['ok'])

    def ai_fixture(self):
        data, saved, _ = test_waivers.WaiverTests().fixture()
        saved['state'] = {'current_date': '2037-02-07', 'phase': 'regular_season'}
        saved['meta']['human_team_ids'] = ['human']
        for p in data['players']:
            p['age_base_start_year'] = 2036
        player = next(p for p in data['players'] if p['id'] == 'ai14')
        player.update(age=33, minutes_projection=0)
        for c in data['contracts']:
            c['seasons'] = [c['seasons'][0]]
        return data, saved, player

    def test_buyout_review_is_date_driven_excludes_humans_and_replays_once(self):
        data, saved, player = self.ai_fixture()
        with patch.object(sv, 'released_free_agent_destination', return_value={'team': {'id': 'human'}}):
            result = rp.review_ai_releases(data, saved, '2037-02-07', 17)
            self.assertEqual(result, ['ai'])
            self.assertTrue(saved['waiver_wire'][0]['buyout'])
            before = deepcopy(saved)
            self.assertEqual(rp.review_ai_releases(data, saved, '2037-02-07', 17), [])
            self.assertEqual(saved, before)

    def test_buyouts_do_not_release_core_injured_young_or_no_destination(self):
        for condition in ('core', 'injured', 'young', 'no_destination', 'future_guarantee', 'human'):
            data, saved, player = self.ai_fixture()
            if condition == 'core':
                saved['team_plans'] = {'ai': {'core_ids': [player['id']]}}
            elif condition == 'injured':
                saved['health_states'] = [{'player_id': player['id'], 'availability_status': 'out'}]
            elif condition == 'young':
                player['age'] = 23
            elif condition == 'future_guarantee':
                next(c for c in data['contracts'] if c['player_id'] == player['id'])['seasons'].append({'season': '2037-38', 'salary': 2_000_000, 'guaranteed_salary': 2_000_000})
            elif condition == 'human':
                saved['meta']['human_team_ids'] = ['human', 'ai']
            with patch.object(sv, 'released_free_agent_destination', return_value=None if condition == 'no_destination' else {'team': {'id': 'human'}}):
                self.assertEqual(rp.review_ai_releases(data, saved, '2037-02-07', 17), [], condition)

    def test_post_deadline_available_free_agents_are_still_considered(self):
        data, saved, player = self.ai_fixture()
        saved['released_free_agents'] = {player['id']: {'status': 'available'}}
        saved['free_agent_player_ids'] = [player['id']]
        player['team_id'] = None
        with patch.object(sv, 'released_free_agent_is_meaningful', return_value=True), \
             patch.object(sv, 'released_free_agent_destination', return_value=None) as destination:
            sv.process_inseason_released_free_agent_signings(data, saved, 17, '2037-02-07')
            destination.assert_called_once()

    def test_observed_buyout_interest_reaches_signing_review_despite_old_zero_minute_role(self):
        data, saved, player = self.ai_fixture()
        saved['released_free_agents'] = {player['id']: {'status': 'available',
            'buyout_market_interest': {'team_id': 'human', 'date': '2037-02-07'}}}
        saved['free_agent_player_ids'] = [player['id']]
        player['team_id'] = None
        with patch.object(sv, 'released_free_agent_is_meaningful', return_value=False), \
             patch.object(sv, 'released_free_agent_destination', return_value=None) as destination:
            sv.process_inseason_released_free_agent_signings(data, saved, 17, '2037-02-09')
            destination.assert_called_once()

    def test_ai_stretch_requires_a_real_funding_need_and_submits_the_target_bid(self):
        from nba_gm_data import play
        data, saved, _, entry = self.fixture()
        saved['meta'].update(user_team_id='ai', human_team_ids=['ai'])
        saved['team_plans'] = {'human': {'window_phase': 'peak'}}
        data['players'].append({'id': 'target', 'name': 'Target', 'team_id': None})
        saved['free_agent_player_ids'].append('target')
        saved['free_agency_state'] = {'day': 3, 'roster_space_targets': {
            'human': {'team_id': 'human', 'player_id': 'target', 'day': 3,
                      'aav_millions': 10, 'years': 2, 'upgrade': 15}}}
        def bid(canonical, trial, target, seed):
            trial.setdefault('free_agent_offers', []).append({'id': 'funded', 'player_id': 'target',
                'team_id': 'human', 'status': 'active', 'interest_score': 99})
            return True
        sv.canonical_with_save(data, saved)
        before = deepcopy(saved)
        with patch.object(play, 'signing_cap_check', return_value={'ok': True}):
            self.assertEqual(rp.review_ai_stretches(data, saved, '2036-07-03'), [])
        self.assertEqual(saved, before)
        with patch.object(play, 'signing_cap_check', return_value={'ok': False}), \
             patch('nba_gm_data.roster_space.activate_target', side_effect=bid):
            self.assertEqual(rp.review_ai_stretches(data, saved, '2036-07-03'), ['human'])
        self.assertEqual(saved['free_agent_offers'][0]['id'], 'funded')
        self.assertTrue(saved['waived_salary_obligations'][0]['stretch'])
        self.assertEqual(sum(r['salary'] for r in saved['waived_salary_obligations'][0]['seasons']), 40_000_000)


if __name__ == '__main__':
    unittest.main()
