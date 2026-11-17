"""Saved acceptance must not bypass current salary legality at application."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.baselines import baseline_for_save
from nba_gm_data.save import canonical_with_save, load_save, write_save
from nba_gm_data.transactions import apply_trade_to_save, apply_trade_to_state, evaluate_trade, current_salary, contract_for_player

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'output' / 'transaction-realism-audit'


class TradeSalaryApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (EVIDENCE / 'fixed-scenarios' / 'fixture-inputs.json').exists():  # captured audit output removed by cleanup
            raise unittest.SkipTest(f'{EVIDENCE} fixtures are missing; regenerate the transaction-realism audit')
        cls.base = json.loads((EVIDENCE / 'fixed-scenarios' / 'fixture-inputs.json').read_text())['base']
        cls.canonical = baseline_for_save(load_app_canonical(ROOT), cls.base)
        rows = json.loads((EVIDENCE / 'supplemental-results.json').read_text())
        old = next(row['result'] for row in rows if row['id'] == 'S-stale-payroll-application')
        log = old['transaction_log']
        cls.proposal = {
            'proposal': {
                'id': log['proposal_id'], 'date': log['date'],
                'from_team_id': log['teams'][0], 'to_team_id': log['teams'][1],
                **deepcopy(log['assets']),
            },
            'accepted_by_all': True, 'legality': {'status': 'legal'},
            'evaluations': deepcopy(log['evaluations']),
        }
        outgoing_ids = {asset['id'] for asset in cls.proposal['proposal']['to_assets']}
        cls.teammate = next(player['id'] for player in cls.canonical['players']
                            if player.get('team_id') == log['teams'][1] and player['id'] not in outgoing_ids)

    def fixture(self, stale=False):
        save = deepcopy(self.base)
        save['state']['current_date'] = self.proposal['proposal']['date']
        competing = deepcopy(self.proposal)
        competing['proposal']['id'] += '-competing'
        competing['offer_context'] = {'status': 'pending_user_review'}
        save['pending_trade_proposals'] = [deepcopy(self.proposal), competing]
        offer = deepcopy(self.proposal)
        offer['offer_context'] = {'status': 'pending_user_review'}
        save['user_trade_offers'] = [offer, deepcopy(competing)]
        if stale:
            save['contract_overrides'][self.teammate] = {
                'team_id': self.proposal['proposal']['to_team_id'],
                'seasons': [{'season': '2026-27', 'salary': 500_000_000, 'guarantee_status': 'guaranteed'}],
            }
        return save

    def apply(self, path, route):
        proposal_id = self.proposal['proposal']['id']
        if route == 'file':
            return apply_trade_to_save(path, proposal_id, date=self.proposal['proposal']['date'])
        action = {'app': 'apply_trade', 'candidate': 'apply_trade_candidate', 'offer': 'respond_user_trade_offer'}[route]
        return dispatch_app_action(action, {'save_path': str(path), 'proposal_id': proposal_id,
                                          'candidate': deepcopy(self.proposal), 'decision': 'accept'},
                                   root=ROOT, save_dir=path.parent, canonical=self.canonical)

    def test_decline_persists_without_rebuilding_offers_and_replay_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'decline.json'
            write_save(path, self.fixture())
            before = load_save(path, include_history=True)
            payload = {'save_path': str(path), 'proposal_id': self.proposal['proposal']['id'],
                       'decision': 'reject', 'summary_only': True}
            with patch('nba_gm_data.app_actions.user_trade_offers_payload', side_effect=AssertionError('Decline rebuilt offer evidence')):
                result = dispatch_app_action('respond_user_trade_offer', payload, root=ROOT, save_dir=path.parent, canonical=self.canonical)
                self.assertEqual(result['status'], 'rejected')
                # The competing fixture changes only its ID, so it is the same
                # exchange and must resolve with the grouped inbox entry.
                self.assertEqual(result['pending_offer_ids'], [])
                self.assertEqual(result['offer_count'], 0)
                saved = load_save(path, include_history=True)
                self.assertEqual(saved['user_trade_offers'][0]['offer_context']['status'], 'rejected_by_user')
                self.assertEqual(saved['user_trade_offers'][1]['offer_context']['status'], 'rejected_by_user')
                for field in ['roster_overrides', 'contract_overrides', 'team_records', 'player_season_stats', 'health_states', 'transaction_logs']:
                    self.assertEqual(saved.get(field), before.get(field), field)
                committed = path.read_bytes()
                replay = dispatch_app_action('respond_user_trade_offer', payload, root=ROOT, save_dir=path.parent, canonical=self.canonical)
                self.assertEqual(replay, result)
                self.assertEqual(path.read_bytes(), committed)

    def test_decline_cannot_change_an_already_accepted_offer(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'accepted.json'
            save = self.fixture()
            save['user_trade_offers'][0]['offer_context']['status'] = 'accepted_executed'
            write_save(path, save)
            committed = path.read_bytes()
            result = dispatch_app_action('respond_user_trade_offer', {
                'save_path': str(path), 'proposal_id': self.proposal['proposal']['id'],
                'decision': 'reject', 'summary_only': True,
            }, root=ROOT, save_dir=path.parent, canonical=self.canonical)
            self.assertEqual(result['status'], 'not_pending')
            self.assertEqual(result['offer_count'], 1)
            self.assertEqual(path.read_bytes(), committed)

    def test_saved_stale_payroll_rejects_atomically_through_file_and_app(self):
        save = self.fixture(stale=True)
        p = self.proposal['proposal']
        fresh = evaluate_trade(canonical_with_save(self.canonical, save), p['from_team_id'], p['to_team_id'],
                               [{'kind': a['kind'], 'value': a['id']} for a in p['from_assets']],
                               [{'kind': a['kind'], 'value': a['id']} for a in p['to_assets']],
                               date=p['date'], seed=29)
        self.assertEqual(fresh['legality']['status'], 'illegal')
        self.assertTrue(any('hard-cap' in issue for issue in fresh['legality']['issues']))
        with tempfile.TemporaryDirectory() as td:
            for route in ['file', 'app', 'candidate', 'offer']:
                with self.subTest(route=route):
                    path = Path(td) / f'{route}.json'
                    write_save(path, deepcopy(save))
                    before_bytes, before_mtime = path.read_bytes(), path.stat().st_mtime_ns
                    before = load_save(path, include_history=True)
                    result = self.apply(path, route)
                    self.assertEqual(result['status'], 'not_applied_salary_legality')
                    self.assertEqual(path.read_bytes(), before_bytes)
                    self.assertEqual(path.stat().st_mtime_ns, before_mtime)
                    self.assertEqual(load_save(path, include_history=True), before)

    def test_still_legal_saved_acceptance_persists_and_replay_is_atomic(self):
        with tempfile.TemporaryDirectory() as td:
            for route in ['file', 'app', 'candidate', 'offer']:
                with self.subTest(route=route):
                    path = Path(td) / f'{route}.json'
                    write_save(path, self.fixture())
                    result = self.apply(path, route)
                    self.assertEqual(result['status'], 'applied')
                    saved = load_save(path, include_history=True)
                    p = self.proposal['proposal']
                    for side, owner in [('from_assets', p['to_team_id']), ('to_assets', p['from_team_id'])]:
                        for asset in p[side]:
                            overrides = saved['roster_overrides'] if asset['kind'] == 'player' else saved['draft_pick_overrides']
                            self.assertEqual(overrides[asset['id']], owner)
                    self.assertEqual(saved['transaction_logs'][-1]['evaluations'], self.proposal['evaluations'])
                    self.assertFalse(saved['pending_trade_proposals'])
                    self.assertEqual(saved['user_trade_offers'][-1]['offer_context']['status'], 'stale_asset_moved')
                    before = path.read_bytes()
                    replay = self.apply(path, route)
                    self.assertNotEqual(replay['status'], 'applied')
                    if route in ['file', 'app']:
                        self.assertEqual(replay['status'], 'not_found')
                    self.assertEqual(path.read_bytes(), before)

    def assert_rejected_unchanged(self, save, canonical=None, expected='illegal'):
        save.pop('rotation_snapshots', None)
        before = deepcopy(save)
        result = apply_trade_to_state(save, self.proposal['proposal']['id'],
                                      canonical=self.canonical if canonical is None else canonical)
        self.assertEqual(result['status'], 'not_applied_salary_legality')
        self.assertEqual(result['legality']['status'], expected)
        self.assertEqual(save, before)
        return result

    def test_current_salary_matching_change_is_rechecked(self):
        save = self.fixture()
        player_id = self.proposal['proposal']['from_assets'][0]['id']
        save['contract_overrides'][player_id] = {'team_id': 'team_lac', 'seasons': [{'season': '2026-27', 'salary': 80_000_000}]}
        result = self.assert_rejected_unchanged(save)
        self.assertTrue(any('matching tolerance' in issue for issue in result['issues']))

    def test_each_supported_future_hard_cap_year_is_rechecked(self):
        for season in ['2027-28', '2028-29', '2029-30']:
            with self.subTest(season=season):
                save = self.fixture()
                for player in self.canonical['players']:
                    if player.get('team_id') != 'team_den':
                        continue
                    current = current_salary(contract_for_player(self.canonical, player['id'])) or 0
                    save['contract_overrides'][player['id']] = {
                        'team_id': 'team_den', 'seasons': [{'season': '2026-27', 'salary': current},
                                                         {'season': season, 'salary': 500_000_000 if player['id'] == self.teammate else 0}],
                    }
                incoming = self.proposal['proposal']['from_assets'][0]['id']
                save['contract_overrides'][incoming] = {
                    'team_id': 'team_lac', 'seasons': [{'season': '2026-27', 'salary': 5_000_000},
                                                      {'season': season, 'salary': 10_000_000}],
                }
                result = self.assert_rejected_unchanged(save)
                self.assertTrue(any(f'{season} hard-cap overage' in issue for issue in result['issues']))

    def test_unresolved_traded_salary_requires_manual_review_and_preserves_files(self):
        save = self.fixture()
        player_id = self.proposal['proposal']['from_assets'][0]['id']
        save['contract_overrides'][player_id] = {'team_id': 'team_lac', 'seasons': [{'season': '2026-27', 'salary': None}]}
        result = self.assert_rejected_unchanged(save, expected='manual_review_required')
        self.assertTrue(any('unresolved salary' in reason for reason in result['legality']['manual_review']))
        with tempfile.TemporaryDirectory() as td:
            for route in ['file', 'app']:
                path = Path(td) / f'{route}.json'
                write_save(path, deepcopy(save));before = path.read_bytes()
                self.assertEqual(self.apply(path, route)['status'], 'not_applied_salary_legality')
                self.assertEqual(path.read_bytes(), before)

    def test_missing_contract_or_payroll_context_cannot_bypass_check(self):
        player_id = self.proposal['proposal']['from_assets'][0]['id']
        canonical = deepcopy(self.canonical)
        canonical['contracts'] = [row for row in canonical['contracts'] if row['player_id'] != player_id]
        self.assert_rejected_unchanged(self.fixture(), canonical=canonical)
        self.assert_rejected_unchanged(self.fixture(), canonical={})
        save = self.fixture();before = deepcopy(save)
        with patch('nba_gm_data.storage.load_universe_json', side_effect=FileNotFoundError):
            result = apply_trade_to_state(save, self.proposal['proposal']['id'])
        self.assertEqual(result['legality']['status'], 'manual_review_required')
        self.assertEqual(save, before)

    def test_application_uses_latest_overrides_even_with_prepared_stale_context(self):
        stale_context = canonical_with_save(self.canonical, self.fixture())
        self.assert_rejected_unchanged(self.fixture(stale=True), canonical=stale_context)

    def test_saved_approval_cannot_bypass_current_roster_veto(self):
        with tempfile.TemporaryDirectory() as td:
            for route in ['file', 'app', 'candidate', 'offer']:
                with self.subTest(route=route):
                    path = Path(td) / f'roster-{route}.json'
                    write_save(path, self.fixture())
                    before = path.read_bytes()
                    with patch('nba_gm_data.trade_roster.live_roster_issues',
                               return_value=['AI rotation has materially deteriorated.']) as review:
                        result = self.apply(path, route)
                    self.assertEqual(result['status'], 'not_applied_roster_plan')
                    review.assert_called_once()
                    self.assertEqual(path.read_bytes(), before)

    def test_unknown_future_salary_follows_existing_skip_policy(self):
        save = self.fixture()
        player_id = self.proposal['proposal']['from_assets'][0]['id']
        save['contract_overrides'][player_id] = {
            'team_id': 'team_lac', 'seasons': [{'season': '2026-27', 'salary': 5_000_000},
                                              {'season': '2027-28', 'salary': None}],
        }
        result = apply_trade_to_state(save, self.proposal['proposal']['id'], canonical=self.canonical)
        self.assertEqual(result['status'], 'applied')


if __name__ == '__main__':
    unittest.main()
