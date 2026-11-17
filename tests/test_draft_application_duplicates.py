"""Draft consumption is independent of pending ids; all saves are disposable."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.draft import apply_draft_selection_to_save, apply_draft_selection_to_save_state
from nba_gm_data.play import apply_current_draft_selection, apply_current_draft_selection_state, select_current_draft_prospect, sim_entire_draft, sim_to_next_user_pick
from nba_gm_data.save import load_save, write_save

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'output' / 'transaction-realism-audit'


class DraftApplicationDuplicateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_app_canonical(ROOT)
        if not (EVIDENCE / 'fixed-scenarios/fixture-inputs.json').exists():  # captured audit output removed by cleanup
            raise unittest.SkipTest(f'{EVIDENCE} fixtures are missing; regenerate the transaction-realism audit')
        cls.base = json.loads((EVIDENCE / 'fixed-scenarios/fixture-inputs.json').read_text())['base']
        cls.draft = next(row['result'] for row in json.loads((EVIDENCE / 'fixed-scenarios/scenarios.json').read_text()) if row['id'] == 'D1-draft')
        cls.first = cls.draft['pending_draft_selections'][0]
        cls.other = cls.draft['pending_draft_selections'][1]

    def fixture(self):
        save = deepcopy(self.base)
        save['state'].update(current_date='2027-06-24', phase='draft')
        save['pending_draft_selections'] = [deepcopy(self.first), deepcopy(self.other)]
        save['draft_state'] = {}
        return save

    def selected(self):
        save = self.fixture()
        result = apply_draft_selection_to_save_state(save, self.first['selection']['id'], '2027-06-24', True)
        self.assertEqual(result['status'], 'applied')
        return save

    def variants(self):
        same = deepcopy(self.first)
        renamed = deepcopy(same); renamed['selection']['id'] += '-duplicate'  # exact supplemental shape: outer id stays old
        both_renamed = deepcopy(renamed); both_renamed['id'] = both_renamed['selection']['id']
        other_prospect = deepcopy(self.other)
        other_prospect['id'] = other_prospect['selection']['id'] = 'consumed-pick-new-prospect'
        other_prospect['selection']['pick_id'] = same['selection']['pick_id']
        other_prospect['selection']['team_id'] = same['selection']['team_id']
        other_prospect['pick'] = deepcopy(same['pick'])
        other_pick = deepcopy(same)
        other_pick['selection'].update(id='another-pick', pick_id=self.other['selection']['pick_id'], overall_pick=2)
        other_pick['pick'] = deepcopy(self.other['pick']); other_pick['id'] = 'another-pick'
        return [same, renamed, other_prospect, other_pick, both_renamed]

    def assert_rejected(self, save, candidate, live=False):
        save['pending_draft_selections'].append(deepcopy(candidate))
        before = deepcopy(save)
        result = (apply_current_draft_selection_state(save, candidate) if live else
                  apply_draft_selection_to_save_state(save, candidate['selection']['id'], '2027-06-24', True))
        self.assertEqual(result['status'], 'not_applied', result)
        self.assertEqual(save, before)
        self.assertIn(self.other, save['pending_draft_selections'])
        return result

    def test_supplemental_replay_and_pick_prospect_collisions_are_atomic(self):
        for candidate in self.variants():
            with self.subTest(id=candidate['selection']['id']):
                self.assert_rejected(self.selected(), candidate)

    def test_live_state_rejection_does_not_stage_a_pending_selection(self):
        for candidate in self.variants():
            save = self.selected(); before = deepcopy(save)
            result = apply_current_draft_selection_state(save, candidate)
            self.assertEqual(result['status'], 'not_applied')
            self.assertEqual(save, before)

    def test_authoritative_record_fallbacks(self):
        selected = self.selected()
        for key in ['draft_rights', 'rookie_contracts', 'incoming_rookies', 'transaction_logs', 'draft_pick_overrides', 'draft_state']:
            with self.subTest(record=key):
                save = self.fixture(); save[key] = deepcopy(selected[key])
                self.assert_rejected(save, self.variants()[1])

    def test_bulk_onboarding_resolves_consumed_pick_from_saved_order(self):
        save = self.fixture(); save['incoming_rookies'] = deepcopy(self.selected()['incoming_rookies'])
        save['draft_orders'] = {'2027': {'draft_order': deepcopy(self.draft['draft_order'])}}
        self.assert_rejected(save, self.variants()[2])
        save = self.fixture(); save['draft_state'] = {'completed_year': '2027', 'status': 'completed'}
        self.assert_rejected(save, self.variants()[2])

    def test_only_applied_queue_entries_are_consumed(self):
        save = self.fixture()
        save['draft_state'] = {'year': '2027', 'current_index': 0, 'draft': {'pending_draft_selections': [deepcopy(self.first), deepcopy(self.other)]}}
        self.assertEqual(apply_current_draft_selection_state(save, deepcopy(self.first))['status'], 'applied')
        for clock in [{'current_index': 1}, {'current_index': 0, 'applied_selection_ids': [self.first['selection']['id']]}]:
            save = self.fixture(); save['draft_state'] = {'year': '2027', 'draft': {'pending_draft_selections': [deepcopy(self.first), deepcopy(self.other)]}, **clock}
            self.assert_rejected(save, self.variants()[2])
        save = self.fixture(); save['draft_state'] = {'selections': [deepcopy(self.first['selection'])]}
        self.assert_rejected(save, self.variants()[2])

    def test_later_year_and_flat_legacy_payload_remain_supported(self):
        save = self.selected()
        later = deepcopy(self.first)
        later['selection'].update(id='later-year', draft_year='2028', pick_id='pick_2028_1')
        later['id'] = 'later-year'; later['pick']['id'] = 'pick_2028_1'
        save['pending_draft_selections'].append(later)
        self.assertEqual(apply_draft_selection_to_save_state(save, 'later-year', '2028-06-24', True)['status'], 'applied')
        save = {'version': 'save_transaction_ledger_v1', 'pending_draft_selections': [deepcopy(self.first['selection'])]}
        self.assertEqual(apply_draft_selection_to_save_state(save, self.first['selection']['id'])['status'], 'applied')
        save['pending_draft_selections'] = [deepcopy(self.variants()[1]['selection'])]
        before = deepcopy(save)
        self.assertEqual(apply_draft_selection_to_save_state(save, save['pending_draft_selections'][0]['id'])['status'], 'not_applied')
        self.assertEqual(save, before)

    def test_mismatched_nested_identity_cannot_overwrite_a_rookie(self):
        save = self.selected(); candidate = deepcopy(self.other); candidate['prospect'] = deepcopy(self.first['prospect'])
        candidate['id'] = candidate['selection']['id'] = 'mismatched-prospect'
        self.assert_rejected(save, candidate)

    def assert_persisted(self, save):
        for key in ['draft_rights', 'rookie_contracts', 'incoming_rookies', 'generated_players']:
            rows = [row for row in save[key] if str(row.get('draft_year')) == '2027']
            self.assertEqual(len(rows), 1, key)
        logs = [row for row in save['transaction_logs'] if row.get('transaction_type') == 'draft_selection']
        self.assertEqual(len(logs), 1)
        rookie = save['incoming_rookies'][0]; player_id = rookie['player_id']
        self.assertEqual(save['roster_overrides'][player_id], self.first['selection']['team_id'])
        contract = save['contract_overrides'][player_id]
        self.assertEqual(contract['status'], 'signed_rookie_contract')
        self.assertEqual(contract['seasons'], save['rookie_contracts'][0]['seasons'])
        self.assertEqual(contract['seasons'][0]['season'], '2027-28')
        self.assertEqual(contract['seasons'][0]['salary'], 12_700_000)
        self.assertEqual(len(contract['seasons']), 4)

    def assert_file_unchanged(self, path, operation):
        before = load_save(path, include_history=True)
        # SQLite's read-only reader can touch its transient shared-memory lock
        # file. The manifest and durable database must remain byte-for-byte.
        def files():
            return {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in path.parent.rglob('*')
                    if p.is_file() and not p.name.endswith('-shm')}
        before_files = files()
        result = operation()
        self.assertEqual(result['status'], 'not_applied', result)
        self.assertEqual(load_save(path, include_history=True), before)
        self.assertEqual(files(), before_files)

    def test_file_wrappers_persist_once_and_reject_all_duplicate_forms(self):
        with tempfile.TemporaryDirectory(prefix='draft-duplicates-') as td:
            for route in ['ledger', 'live']:
                path = Path(td) / f'{route}.json'; write_save(path, self.fixture())
                apply = lambda candidate: (apply_draft_selection_to_save(path, candidate['selection']['id'], '2027-06-24', True)
                                           if route == 'ledger' else apply_current_draft_selection(path, candidate))
                self.assertEqual(apply(deepcopy(self.first))['status'], 'applied')
                self.assert_persisted(load_save(path, include_history=True))
                for candidate in self.variants():
                    save = load_save(path); save['pending_draft_selections'].append(deepcopy(candidate)); write_save(path, save)
                    self.assert_file_unchanged(path, lambda: apply(candidate))

    def test_archived_draft_log_is_checked_by_file_wrapper(self):
        save = self.fixture(); save['transaction_logs'] = deepcopy(self.selected()['transaction_logs'])
        save['meta']['season'] = '2029-30'
        save['state']['current_date'] = '2029-10-01'
        save['transaction_logs'] += [{'id': f'filler-{i}', 'date': '2028-01-01', 'transaction_type': 'other'} for i in range(120)]
        candidate = self.variants()[2]; save['pending_draft_selections'] = [candidate, deepcopy(self.other)]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'save.json'; write_save(path, save)
            self.assertFalse(any(row.get('transaction_type') == 'draft_selection' for row in load_save(path)['transaction_logs']))
            self.assert_file_unchanged(path, lambda: apply_draft_selection_to_save(path, candidate['selection']['id'], sign_rookie=True))
            save = load_save(path); self.live_fixture(save, candidate); write_save(path, save)
            self.assert_file_unchanged(path, lambda: apply_current_draft_selection(path, candidate))

    def live_fixture(self, save, candidate):
        draft = deepcopy(self.draft); draft['pending_draft_selections'] = [deepcopy(candidate), deepcopy(self.other)]
        save['draft_state'] = {'year': '2027', 'status': 'in_progress', 'current_index': 0, 'draft': draft, 'applied_selection_ids': []}
        return save

    def app(self, path, action, candidate):
        team = 'CHA' if action == 'draft_apply_current' else 'GSW'
        return dispatch_app_action(action, {'save_path': str(path), 'team': team, 'year': '2027', 'seed': 17,
                                           'prospect_id': candidate['selection']['prospect_id']}, root=ROOT, save_dir=path.parent, canonical=self.canonical)

    def test_user_and_ai_app_actions_apply_once_and_reject_stale_clock(self):
        with tempfile.TemporaryDirectory(prefix='draft-app-') as td, patch('nba_gm_data.play.maybe_run_ai_draft_trades_before_pick_state') as trades:
            for action in ['draft_apply_current', 'draft_sim_current']:
                with self.subTest(action=action):
                    path = Path(td) / f'{action}.json'; write_save(path, self.live_fixture(self.fixture(), self.first))
                    result = self.app(path, action, self.first)
                    self.assertEqual(result['status'], 'applied', result.get('result'))
                    self.assert_persisted(load_save(path, include_history=True))
                    for candidate in self.variants():
                        save = self.live_fixture(load_save(path), candidate); write_save(path, save)
                        trades.reset_mock()
                        self.assert_file_unchanged(path, lambda: self.app(path, action, candidate))
                        trades.assert_not_called()

    def test_direct_prospect_swap_and_sim_all_cannot_write_a_consumed_pick(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'save.json'; write_save(path, self.live_fixture(self.selected(), self.variants()[1]))
            save = load_save(path); save['draft_state']['ai_draft_trade_news_queue'] = [{'headline': 'Unrelated retained news'}]; write_save(path, save)
            before = path.read_bytes()
            self.assertIsNone(select_current_draft_prospect(path, self.other['selection']['prospect_id']))
            self.assertEqual(path.read_bytes(), before)
            result = sim_entire_draft(path)
            self.assertEqual(result['applied_count'], 0)
            self.assertEqual(path.read_bytes(), before)
            for mode in ['draft_sim_all', 'draft_sim_to_user']:
                self.assert_file_unchanged(path, lambda: self.app(path, mode, self.variants()[1]))

    def test_sim_all_returns_ordered_pick_reveal_events_without_reapplying_picks(self):
        save = self.fixture()
        save['draft_state'] = {
            'year': '2027', 'status': 'in_progress', 'current_index': 0,
            'draft': {'pending_draft_selections': [deepcopy(self.first), deepcopy(self.other)]},
            'applied_selection_ids': [],
        }
        with tempfile.TemporaryDirectory(prefix='draft-playback-') as td:
            path = Path(td) / 'save.json'; write_save(path, save)
            result = sim_entire_draft(path)
            events = result['presentation_events']
            self.assertEqual([event['type'] for event in events], ['pick', 'pick'])
            self.assertEqual([event['overall_pick'] for event in events], [1, 2])
            self.assertEqual([event['prospect']['id'] for event in events], [
                self.first['selection']['prospect_id'], self.other['selection']['prospect_id']
            ])
            saved = load_save(path, include_history=True)
            logs = [row for row in saved['transaction_logs'] if row.get('transaction_type') == 'draft_selection']
            self.assertEqual(len(logs), 2)
            replay = sim_entire_draft(path)
            self.assertEqual(replay['applied_count'], 0)
            self.assertEqual(replay['presentation_events'], [])
            self.assertEqual(len([row for row in load_save(path)['transaction_logs'] if row.get('transaction_type') == 'draft_selection']), 2)

    def test_sim_to_user_stops_at_the_controlled_pick_after_ordered_reveal(self):
        save = self.fixture()
        user_team_id = save['meta']['user_team_id']
        user_team = next(team for team in self.canonical['teams'] if team['id'] == user_team_id)
        ai_team_id = next(team['id'] for team in self.canonical['teams'] if team['id'] != user_team_id)
        pending = [deepcopy(self.first), deepcopy(self.other)]
        for item, team_id in zip(pending, [ai_team_id, user_team_id]):
            item['selection']['team_id'] = team_id
            item['team'] = {'id':team_id, 'abbrev':next(team['abbrev'] for team in self.canonical['teams'] if team['id'] == team_id)}
        save['pending_draft_selections'] = deepcopy(pending)
        save['draft_state'] = {
            'year':'2027', 'status':'in_progress', 'current_index':0,
            'draft':{'pending_draft_selections':deepcopy(pending)}, 'applied_selection_ids':[],
        }
        with tempfile.TemporaryDirectory(prefix='draft-to-user-playback-') as td:
            path=Path(td)/'save.json'; write_save(path,save)
            def trade_notice(_canonical, live_save, _active, _user_team, _seed):
                live_save['draft_state'].setdefault('ai_draft_trade_news_queue',[]).append({
                    'id':'trade-before-pick-1','date':'2027-06-24','overall_pick':1,
                    'headline':'Trade completed before pick #1.',
                    'social_post':{'handle':'@league_wire','text':'Trade chatter is heating up.'},
                })
                return {'applied_count':1,'trades':[{}]}
            with patch('nba_gm_data.play.materialize_draft_order_pick_assets'), \
                 patch('nba_gm_data.play.sync_live_draft_state_to_saved_order'), \
                 patch('nba_gm_data.play.refresh_live_draft_state_ownership'), \
                 patch('nba_gm_data.play.maybe_run_ai_draft_trades_before_pick_state',side_effect=trade_notice):
                result=sim_to_next_user_pick(self.canonical,path,user_team['abbrev'],seed=19)
            self.assertEqual([event['type'] for event in result['presentation_events']],['trade','pick'])
            self.assertEqual(result['presentation_events'][1]['overall_pick'],1)
            self.assertEqual(result['presentation_events'][0]['social_post']['handle'],'@league_wire')
            self.assertEqual(result['current_selection']['selection']['team_id'],user_team_id)
            saved=load_save(path,include_history=True)
            self.assertEqual(saved['draft_state']['current_index'],1)
            self.assertEqual(len([row for row in saved['transaction_logs'] if row.get('transaction_type')=='draft_selection']),1)


if __name__ == '__main__':
    unittest.main()
