"""Real claim evaluation, contract transfer, clearance, replay and buyout accounting."""
from copy import deepcopy
import json
import unittest

from nba_gm_data import save as sv, waivers as w, transactions as tx
from nba_gm_data.contract_ai import contract_application_issues
from test_ai_roles import AiRoleTests


class WaiverTests(unittest.TestCase):
    def fixture(self):
        data, saved = AiRoleTests().fixture()
        saved['version'] = 'league_save_v1'
        saved['meta']['seed'] = 17
        data['meta'] = {'active_season': '2036-37'}
        saved['state'] = {'current_date': '2036-12-01', 'phase': 'regular_season'}
        data['contracts'] = [{'id': 'c-' + p['id'], 'player_id': p['id'], 'team_id': p['team_id'],
                              'seasons': [{'season': season, 'salary': 2_000_000, 'guaranteed_salary': 2_000_000}
                                          for season in ('2036-37', '2037-38')]} for p in data['players']]
        saved['free_agent_player_ids'] = []
        saved['contract_protection'] = {'version': 1}
        player = next(p for p in data['players'] if p['id'] == 'human00')
        return data, saved, player

    def test_no_instant_free_agency_and_unclaimed_clearance_is_idempotent(self):
        data, saved, player = self.fixture()
        saved['meta']['human_team_ids'] = ['ai', 'human']
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01')
        self.assertEqual(entry['clearance_date'], '2036-12-03')
        self.assertNotIn(player['id'], saved['free_agent_player_ids'])
        self.assertEqual(w.process_waivers(data, saved, '2036-12-02'), [])
        self.assertEqual(len(w.process_waivers(data, saved, '2036-12-03')), 1)
        self.assertIn(player['id'], saved['free_agent_player_ids'])
        before = deepcopy(saved)
        self.assertEqual(w.process_waivers(data, saved, '2036-12-03'), [])
        self.assertEqual(saved, before)
        self.assertEqual(saved['waived_salary_obligations'][0]['seasons'][0]['salary'], 2_000_000)

    def test_real_ai_claim_transfers_full_contract_and_queues_its_own_cut(self):
        data, saved, player = self.fixture()
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01')
        active = sv.canonical_with_save(data, saved)
        plan = w.claim_plan(active, saved, entry, 'ai', ai=True)
        self.assertTrue(plan['ok'], plan)
        self.assertIsNotNone(plan['cut_player_id'])
        w.process_waivers(data, saved, '2036-12-03')
        self.assertEqual(entry['status'], 'claimed')
        self.assertEqual(saved['roster_overrides'][player['id']], 'ai')
        self.assertEqual(saved['contract_overrides'][player['id']]['seasons'], entry['contract']['seasons'])
        self.assertEqual(saved['waived_salary_obligations'][0]['seasons'][0]['salary'], 0)
        chain = [r for r in saved['waiver_wire'] if r['status'] == 'pending']
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]['clearance_date'], '2036-12-05')
        self.assertNotIn(chain[0]['player_id'], saved['free_agent_player_ids'])
        self.assertIn(player['id'], tx.recently_traded_player_ids(sv.canonical_with_save(data, saved), '2036-12-10'))

    def test_user_claim_is_irrevocable_and_rechecked_at_clearance(self):
        data, saved, player = self.fixture()
        player = next(p for p in data['players'] if p['id'] == 'ai06')
        entry = w.request_waiver(data, saved, player, 'ai', '2036-12-01')
        active = sv.canonical_with_save(data, saved)
        claim = w.submit_claim(active, saved, entry['id'], 'human', cut_id='human14')
        self.assertEqual(w.submit_claim(active, saved, entry['id'], 'human', cut_id='human00'), claim)
        self.assertEqual(len(entry['claims']), 1)
        # Another transaction consumes the intended replacement before the award.
        saved['roster_overrides']['human14'] = 'ai'
        w.process_waivers(data, saved, '2036-12-03')
        self.assertEqual(entry['status'], 'cleared')

    def test_cap_rejects_claim_despite_minimum_signing_exception(self):
        data, saved, player = self.fixture()
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01')
        for row in data['contracts']:
            if row['team_id'] == 'ai':
                row['seasons'][0]['salary'] = 100_000_000
        self.assertFalse(w.claim_plan(sv.canonical_with_save(data, saved), saved, entry, 'ai', cut_id='ai14')['ok'])

    def test_buyout_only_applies_after_clearance_and_never_erases_earned_money(self):
        data, saved, player = self.fixture()
        saved['meta']['human_team_ids'] = ['ai', 'human']
        quote = w.buyout_quote(data, saved, player, 'human')
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01', buyout=True)
        debt = saved['waived_salary_obligations'][0]
        before = deepcopy(debt['seasons'])
        self.assertEqual(debt['seasons'][1]['salary'], 2_000_000)
        w.process_waivers(data, saved, '2036-12-03')
        self.assertEqual(entry['status'], 'cleared')
        for old, new in zip(before, debt['seasons']):
            self.assertEqual(new['salary'], old['salary'] - quote['concessions'][old['season']])
            self.assertGreaterEqual(new['salary'], old['earned_salary'] + old['waiver_clearance_salary'])

    def test_buyout_does_not_reduce_claimants_original_contract(self):
        data, saved, player = self.fixture()
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01', buyout=True)
        w.process_waivers(data, saved, '2036-12-03')
        self.assertEqual(entry['status'], 'claimed')
        self.assertEqual(saved['contract_overrides'][player['id']]['seasons'][0]['salary'], 2_000_000)
        self.assertEqual(saved['waived_salary_obligations'][0]['relief_status'], 'existing_contract_assumed_by_claimant')

    def test_waiver_priority_uses_record_then_deterministic_tie(self):
        data, saved, _ = self.fixture()
        saved['team_records'] = {'ai': {'wins': 10, 'losses': 20}, 'human': {'wins': 20, 'losses': 10}}
        saved['season_history'] = [{'team_records': {'ai': {'wins': 50, 'losses': 32}, 'human': {'wins': 20, 'losses': 62}}}]
        self.assertEqual(w.priority(data, saved, '2036-12-01')[0], 'ai')
        self.assertEqual(w.priority(data, saved, '2036-11-30')[0], 'human')
        self.assertEqual(w.priority(data, saved, '2036-07-01')[0], 'human')

    def test_competing_claims_award_to_worse_record_without_cutting_losing_claimants(self):
        data, saved, player = self.fixture()
        data['teams'].append({'id': 'third', 'abbrev': 'THR'})
        saved['meta']['human_team_ids'] = ['ai', 'human', 'third']
        saved['team_records'] = {'ai': {'wins': 20, 'losses': 10}, 'third': {'wins': 5, 'losses': 25}}
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01')
        active = sv.canonical_with_save(data, saved)
        w.submit_claim(active, saved, entry['id'], 'ai', cut_id='ai14')
        w.submit_claim(active, saved, entry['id'], 'third')
        w.process_waivers(data, saved, '2036-12-03')
        self.assertEqual(entry['claimed_by_team_id'], 'third')
        self.assertNotIn('ai14', saved['roster_overrides'])

    def test_waiver_back_after_trade_is_blocked_and_unknown_protection_not_discounted(self):
        data, saved, player = self.fixture()
        saved['transaction_logs'] = [{'transaction_type': 'trade', 'date': '2036-11-28', 'teams': ['ai', 'human'],
                                    'assets': {'from_assets': [{'kind': 'player', 'id': player['id']}], 'to_assets': []}}]
        entry = w.request_waiver(data, saved, player, 'human', '2036-12-01')
        self.assertIn('traded', w.claim_plan(sv.canonical_with_save(data, saved), saved, entry, 'ai', cut_id='ai14')['reason'])
        contract = next(c for c in data['contracts'] if c['player_id'] == player['id'])
        for row in contract['seasons']:
            row['guaranteed_salary'] = None
        self.assertEqual(w.buyout_quote(data, saved, player, 'human')['savings_millions'], 0)

    def test_daily_bulk_and_reload_resolve_the_same_chain(self):
        data, saved, player = self.fixture()
        w.request_waiver(data, saved, player, 'human', '2036-12-01')
        daily, bulk = deepcopy(saved), deepcopy(saved)
        for stamp in ('2036-12-02', '2036-12-03', '2036-12-04', '2036-12-05'):
            daily['state']['current_date'] = stamp
            w.process_waivers(data, daily, stamp)
            daily = json.loads(json.dumps(daily))
        # Real lifecycle iterates every date even on a bulk advance.
        sv.advance_lifecycle_to(data, bulk, '2036-12-05', 17, development=False)
        for key in ('waiver_wire', 'waived_salary_obligations', 'roster_overrides', 'contract_overrides', 'free_agent_player_ids'):
            self.assertEqual(daily.get(key), bulk.get(key), key)

    def test_legacy_pool_repair_cannot_expose_a_pending_waiver(self):
        data, saved, player = self.fixture()
        w.request_waiver(data, saved, player, 'human', '2036-12-01')
        sv.repair_unpooled_unrostered_players(data, saved)
        self.assertNotIn(player['id'], saved['free_agent_player_ids'])

    def test_signing_guard_is_in_the_spending_path(self):
        from nba_gm_data.play import signing_cap_check
        data, saved, player = self.fixture()
        contract = next(c for c in data['contracts'] if c['player_id'] == player['id'])
        for row in contract['seasons']:
            row['salary'] = None
        w.request_waiver(data, saved, player, 'human', '2036-12-01')
        result = signing_cap_check(sv.canonical_with_save(data, saved), saved, 'HUM', 10)
        self.assertFalse(result['ok'])


if __name__ == '__main__':
    unittest.main()
