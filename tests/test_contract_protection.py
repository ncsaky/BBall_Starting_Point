"""Salary protection survives cuts, new employers, reloads and roster planning."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nba_gm_data import contract_protection as cp, save as sv, transactions as tx
from nba_gm_data.contract_ai import merge_extension_offer_with_existing_contract
import test_ai_roles


class ContractProtectionTests(unittest.TestCase):
    def fixture(self, guaranteed=10_000_000):
        player = {'id': 'p', 'name': 'Player', 'team_id': 'a'}
        data = {'meta': {'active_season': '2026-27'}, 'players': [player], 'contracts': [
            {'id': 'c', 'player_id': 'p', 'team_id': 'a', 'seasons': [
                {'season': '2026-27', 'salary': 10_000_000, 'guaranteed_salary': guaranteed},
                {'season': '2027-28', 'salary': 10_000_000, 'guaranteed_salary': guaranteed}]}]}
        saved = {'meta': {'season': '2026-27'}, 'state': {'current_date': '2026-09-01'},
                 'contract_protection': {'version': 1}, 'season_schedules': {'2026-27': {'games': [
                     {'phase': 'regular', 'gameDate': '2026-10-01'},
                     {'phase': 'regular', 'gameDate': '2027-04-18'}]}}}
        return data, saved, player

    def test_cut_keeps_guaranteed_salary_and_does_not_double_count(self):
        data, saved, player = self.fixture()
        before = sv.team_cap_summary(data, saved, 'a')['salary_total']
        first = cp.record_waiver(data, saved, player, 'a', '2026-09-01')
        self.assertEqual(first['remaining_cost_millions'], 20)
        saved = json.loads(json.dumps(saved))
        cp.record_waiver(data, saved, player, 'a', '2026-09-01')
        self.assertEqual(len(saved['waived_salary_obligations']), 1)
        player['team_id'] = None
        data['waived_salary_obligations'] = saved['waived_salary_obligations']
        self.assertEqual(sv.team_cap_summary(data, saved, 'a')['salary_total'], before)
        self.assertEqual(tx.team_current_salary_total(data, 'a'), before)
        self.assertEqual(tx.team_salary_total_for_season(data, 'a', '2027-28'), before)
        self.assertEqual(tx.salary_posture(data, 'a')['salary_total'], before)

    def test_new_employer_does_not_overwrite_old_debt(self):
        data, saved, player = self.fixture()
        debt = deepcopy(cp.record_waiver(data, saved, player, 'a', '2026-09-01'))
        player['team_id'] = 'b'
        data['contracts'][0]['seasons'][0]['salary'] = 3_000_000
        data['waived_salary_obligations'] = saved['waived_salary_obligations']
        self.assertEqual(saved['waived_salary_obligations'][0], debt)
        self.assertEqual(tx.team_current_salary_total(data, 'a'), 10_000_000)
        self.assertEqual(tx.team_current_salary_total(data, 'b'), 3_000_000)

    def test_distinct_same_day_agreements_do_not_merge_obligations(self):
        data, saved, player = self.fixture()
        data['contracts'][0]['agreement_id'] = 'first'
        cp.record_waiver(data, saved, player, 'a', '2026-09-01')
        data['contracts'][0]['agreement_id'] = 'second'
        cp.record_waiver(data, saved, player, 'a', '2026-09-01')
        self.assertEqual(len(saved['waived_salary_obligations']), 2)

    def test_non_guaranteed_camp_cut_and_partial_protection(self):
        data, saved, player = self.fixture(0)
        self.assertEqual(cp.waiver_projection(data, saved, player, 'a')['remaining_cost_millions'], 0)
        data['contracts'][0]['seasons'][0]['guaranteed_salary'] = 2_000_000
        self.assertEqual(cp.waiver_projection(data, saved, player, 'a')['remaining_cost_millions'], 2)

    def test_unknown_terms_are_disclosed_reserves_not_verified_guarantees(self):
        data, saved, player = self.fixture(None)
        result = cp.record_waiver(data, saved, player, 'a', '2026-09-01')
        self.assertTrue(result['unverified'])
        self.assertIsNone(result['seasons'][0]['protected_salary'])
        self.assertEqual(sv.team_cap_summary({'players': [], 'contracts': []}, saved, 'a')['unverified_waived_reserve_millions'], 10)

    def test_earned_salary_and_guarantee_activation(self):
        data, saved, player = self.fixture(0)
        row = data['contracts'][0]['seasons'][0]
        row['guarantee_date'] = '2027-01-10'
        saved['state']['current_date'] = '2026-11-01'
        projection = cp.waiver_projection(data, saved, player, 'a')
        self.assertGreater(projection['seasons'][0]['salary'], 0)
        self.assertLess(projection['seasons'][0]['salary'], 10_000_000)
        self.assertGreater(projection['remaining_cost_millions'], 0)
        self.assertGreater(projection['seasons'][0]['waiver_clearance_salary'], 0)
        saved['state']['current_date'] = '2027-01-08'
        self.assertEqual(cp.waiver_projection(data, saved, player, 'a')['seasons'][0]['salary'], 10_000_000)
        saved['state']['current_date'] = '2027-01-10'
        self.assertEqual(cp.waiver_projection(data, saved, player, 'a')['seasons'][0]['salary'], 10_000_000)

    def test_unexercised_future_team_option_is_not_debt(self):
        data, saved, player = self.fixture()
        data['contracts'][0]['seasons'][1].update(option_type='team_option', option_exercised=False)
        self.assertEqual(cp.waiver_projection(data, saved, player, 'a')['remaining_cost_millions'], 10)

    def test_non_guaranteed_does_not_erase_unverified_injury_protection(self):
        data, saved, player = self.fixture(0)
        saved['health_states'] = [{'player_id': 'p', 'availability_status': 'out', 'return_date': '2026-12-01'}]
        result = cp.waiver_projection(data, saved, player, 'a')
        self.assertTrue(result['unverified'])
        self.assertEqual(result['remaining_cost_millions'], 10)
        self.assertTrue(result['seasons'][0]['injury_protection_requires_review'])

    def test_expired_obligations_do_not_charge_future_years(self):
        data, saved, player = self.fixture()
        cp.record_waiver(data, saved, player, 'a', '2026-09-01')
        self.assertEqual(cp.waived_total(saved, 'a', '2028-29'), 0)

    def test_unknown_salary_is_not_displayed_as_a_free_waiver(self):
        data, saved, player = self.fixture(None)
        data['contracts'][0]['seasons'][0]['salary'] = None
        entry = cp.record_waiver(data, saved, player, 'a', '2026-09-01')
        self.assertTrue(entry['unquantified'])
        player['team_id'] = None
        self.assertEqual(sv.team_cap_summary(data, saved, 'a')['unresolved_waived_contract_count'], 1)

    def test_extension_preserves_inherited_guarantees_and_options(self):
        original = [{'season': '2026-27', 'salary': 2_000_000, 'guaranteed_salary': 500_000}]
        offer = {'annual_salary': 3_000_000, 'years': 2, 'start_season': '2027-28', 'guaranteed': False}
        result = merge_extension_offer_with_existing_contract(offer, {'current_contract_seasons': original})
        self.assertEqual(result['seasons'][0], original[0])
        self.assertEqual([s['guaranteed_salary'] for s in result['seasons'][1:]], [0, 0])
        self.assertEqual(sv.offer_to_contract_seasons(offer)[0]['guarantee_date'], '2028-01-10')
        legacy = sv.offer_to_contract_seasons({k: v for k, v in offer.items() if k != 'guaranteed'})
        self.assertNotIn('guaranteed_salary', legacy[0])

    def test_strict_boolean_and_interest_security_preference(self):
        with self.assertRaises(ValueError): cp.guarantee_choice('false')
        self.assertGreater(cp.security_penalty({'minutes_projection': 28}, False), 0)
        self.assertEqual(cp.security_penalty({}, True), 0)

    def test_imported_evidence_requires_identity_salary_and_asof_match(self):
        data, saved, player = self.fixture()
        saved.pop('contract_protection')
        proof = {'source': {'retrieved_at': '2026-10-27', 'url': 'example'}, 'contracts': [
            {'normalized_name': 'player', 'candidate_player_id': 'p', 'seasons': [
                {'season': year, 'salary': 10_000_000, 'guaranteed_salary': 10_000_000,
                 'protection_evidence': 'aggregate_equals_remaining_salary'} for year in ('2026-27', '2027-28')]}]}
        for row in data['contracts'][0]['seasons']: row.pop('guaranteed_salary')
        with patch.object(cp, 'research_snapshot', return_value=proof): cp.initialize_protection(saved, data)
        cp.apply_imported_protection(data, saved)
        self.assertNotIn('guaranteed_salary', data['contracts'][0]['seasons'][0])
        saved['state']['current_date'] = '2026-10-27'
        cp.apply_imported_protection(data, saved)
        self.assertEqual(data['contracts'][0]['seasons'][0]['guaranteed_salary'], 10_000_000)
        data['contracts'][0]['seasons'][0].pop('guaranteed_salary')
        saved['contract_overrides'] = {'p': {'annual_salary': 10_000_000}}
        cp.apply_imported_protection(data, saved)
        self.assertNotIn('guaranteed_salary', data['contracts'][0]['seasons'][0])

    def test_real_role_projection_and_pending_bids_are_pure(self):
        data, saved = test_ai_roles.AiRoleTests().fixture()
        saved['state']['current_date'] = '2036-09-01'
        data['contracts'] = [{'player_id': p['id'], 'seasons': [{'season': '2036-37', 'salary': 2_000_000, 'guaranteed_salary': 2_000_000}]} for p in data['players']]
        incoming = dict(data['players'][6], id='incoming', team_id=None, age=22, potential=95, current_ability=65)
        data['players'].append(incoming)
        data['traits'].extend(dict(t, player_id='incoming') for t in list(data['traits']) if t['player_id'] == 'ai06')
        before = deepcopy((data, saved))
        result = cp.roster_signing_plan(data, saved, incoming, 'ai', 8, 3)
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(result['cuts']), 1)
        self.assertGreater(result['projected_minutes'], 20)
        self.assertEqual((data, saved), before)
        reloaded = json.loads(json.dumps(saved))
        self.assertEqual(cp.roster_signing_plan(data, reloaded, incoming, 'ai', 8, 3), result)
        saved['roster_overrides'] = {'ai14': None}
        self.assertEqual(cp.roster_signing_plan(data, saved, incoming, 'ai', 8, 3)['cuts'], [])
        saved['roster_overrides']['human06'] = 'ai'
        self.assertEqual(len(cp.roster_signing_plan(data, saved, incoming, 'ai', 8, 3)['cuts']), 1)

    def test_marginal_upgrade_is_blocked_by_replacement_cost_not_star_tax(self):
        data, saved = test_ai_roles.AiRoleTests().fixture()
        saved['state']['current_date'] = '2036-09-01'
        incoming = dict(data['players'][10], id='incoming', team_id=None)
        data['players'].append(incoming)
        data['traits'].extend(dict(t, player_id='incoming', value=51) for t in list(data['traits']) if t['player_id'] == 'ai10')
        for p in data['players']:
            if p['team_id'] == 'ai': data['contracts'].append({'player_id': p['id'], 'seasons': [
                {'season': '2036-37', 'salary': 80_000_000, 'guaranteed_salary': 80_000_000}]})
        result = cp.roster_signing_plan(data, saved, incoming, 'ai', 2, 1)
        self.assertFalse(result['ok'], result)

    def test_non_guaranteed_outgoing_salary_does_not_supply_matching_credit(self):
        data, saved, player = self.fixture(0)
        self.assertEqual(tx.package_salary(data, [{'kind': 'player', 'id': 'p'}]), 10_000_000)
        self.assertEqual(tx.package_matching_credit(data, [{'kind': 'player', 'id': 'p'}]), 0)
        data['contracts'][0]['seasons'][0].update(guarantee_date='2027-01-10')
        data['meta']['current_date'] = '2027-01-10'
        self.assertEqual(tx.package_matching_credit(data, [{'kind': 'player', 'id': 'p'}]), 10_000_000)


class ContractProtectionActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from nba_gm_data.app_actions import load_app_canonical
        cls.root = Path(__file__).resolve().parents[1]
        cls.canonical = load_app_canonical(cls.root)

    def test_negotiation_cut_reload_and_duplicate_action_use_real_boundaries(self):
        from nba_gm_data.app_actions import dispatch_app_action, AppActionError
        from nba_gm_data.play import manual_save_pool_signing
        from nba_gm_data.contract_ai import apply_contract_to_save
        for seed, guaranteed in ((17, True), (29, False)):
            with self.subTest(seed=seed), TemporaryDirectory() as folder:
                path = Path(folder)/'disposable.json'
                sv.create_league_save(self.root, self.canonical, 'TOR', path, seed=seed)
                saved = sv.load_save(path)
                initial_debt = deepcopy(saved.get('waived_salary_obligations', []))
                sv.set_save_date_phase(saved, '2027-07-01')
                sv.write_save(path, saved)
                active = sv.canonical_with_save(self.canonical, saved)
                player = next(p for p in active['players'] if p['id'] in saved['free_agent_player_ids']
                              and float(p.get('minutes_projection') or 0) <= 4)
                team_id = saved['meta']['user_team_id']
                cap_before = sv.team_cap_summary(active, saved, team_id, '2027-28')['salary_total']
                def action(name, **payload):
                    return dispatch_app_action(name, {'save_path': str(path), **payload}, root=self.root,
                                               save_dir=folder, canonical=self.canonical)
                offered = action('submit_free_agent_offer', player_id=player['id'], years=2,
                                 aav_millions=2.25, guaranteed=guaranteed, auto_apply=True, seed=seed)
                self.assertEqual(offered.get('apply_result', {}).get('status'), 'applied', offered)
                with patch('nba_gm_data.app_actions.home_payload', return_value={}):
                    waived = action('waive_player', player_id=player['id'])
                self.assertEqual(waived['waiver']['remaining_cost_millions'], 4.5 if guaranteed else 0)
                saved = sv.load_save(path)
                active = sv.canonical_with_save(self.canonical, saved)
                self.assertEqual(len(saved['waived_salary_obligations']), len(initial_debt) + 1)
                self.assertEqual([r for r in saved['waived_salary_obligations'] if r.get('player_id') != player['id']], initial_debt)
                self.assertIsNone(next(p for p in active['players'] if p['id'] == player['id'])['team_id'])
                expected = cap_before + (2_250_000 if guaranteed else 0)
                self.assertEqual(sv.team_cap_summary(active, saved, team_id, '2027-28')['salary_total'], expected)
                from nba_gm_data.save_recovery import create_export, restore_export
                debt = deepcopy(saved['waived_salary_obligations'])
                restored = Path(folder)/'restored.json'
                restore_export(restored, create_export(path))
                self.assertEqual(sv.load_save(restored)['waived_salary_obligations'], debt)
                with self.assertRaises(AppActionError): action('waive_player', player_id=player['id'])
                self.assertEqual(sv.load_save(path)['waived_salary_obligations'], debt)
                deal = manual_save_pool_signing(active, path, player, 'BOS', 1, 3, seed, guaranteed=True)
                applied = apply_contract_to_save(path, deal['negotiation']['id'], date='2027-07-01')
                self.assertNotEqual(applied['status'], 'applied')
                from nba_gm_data.waivers import process_waivers
                saved = sv.load_save(path)
                saved['meta']['human_team_ids'] = [t['id'] for t in active['teams']]
                sv.set_save_date_phase(saved, '2027-07-03')
                process_waivers(self.canonical, saved, '2027-07-03')
                sv.write_save(path, saved)
                active = sv.canonical_with_save(self.canonical, saved)
                deal = manual_save_pool_signing(active, path, player, 'BOS', 1, 3, seed, guaranteed=True)
                applied = apply_contract_to_save(path, deal['negotiation']['id'], date='2027-07-03')
                self.assertEqual(applied['status'], 'applied')
                saved = sv.load_save(path)
                self.assertEqual(saved['waived_salary_obligations'], debt)
                active = sv.canonical_with_save(self.canonical, saved)
                self.assertEqual(sv.team_cap_summary(active, saved, team_id, '2027-28')['salary_total'], expected)


if __name__ == '__main__': unittest.main()
