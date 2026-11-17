"""Wants reads share revision-owned projections, preserving ownership boundaries."""
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import gc
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data import app_actions as aa, trade_wants as wants, transactions as tx
import test_trade_wants as wants_tests


class Active(dict):
    pass


class TeamWantsReadContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'a.json'
        self.canonical = wants_tests.TradeWantsTests.fixture(self)
        self.canonical['_baseline_identity'] = 'test-wants-read'
        self.saved = {'meta': {'user_team_id': 'a', 'user_team_abbrev': 'A'},
                      'state': {'current_date': '2027-01-31'},
                      'team_trade_wants': {'a': {'revision': 1, 'entries': [
                          {'id': 'range', 'kind': 'player', 'positions': [],
                           'conditions': [{'field': 'range', 'op': '>=', 'value': 90}]}]}}}
        self.store(self.path, self.saved)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(aa._READ_CACHE, {}, clear=True))
        self.stack.enter_context(patch.object(aa, 'load_save', side_effect=lambda p: json.loads(p.read_text())))
        self.stack.enter_context(patch.object(aa, 'ensure_league_save_defaults', side_effect=lambda s,c:s))
        self.validate = self.stack.enter_context(patch.object(aa, 'validate_save_components'))
        self.overlay = self.stack.enter_context(patch.object(aa, 'canonical_with_save', side_effect=self.active))
        self.project = self.stack.enter_context(patch.object(aa, 'with_transaction_context', side_effect=lambda c:c))
        self.facts = self.stack.enter_context(patch.object(wants, 'player_facts', return_value={'range': 91, 'overall': 85}))
        self.stack.enter_context(patch.object(tx, 'tradeable_picks_for_team', return_value=[]))
        self.stack.enter_context(patch.object(aa, 'write_save', side_effect=lambda p,s:self.store(p,s)))

    def store(self, path, saved):
        path.write_text(json.dumps(saved))

    def active(self, canonical, saved):
        data = Active(deepcopy(canonical))
        data.update(_allow_internal_caches=True, team_trade_wants=deepcopy(saved['team_trade_wants']))
        data['meta']['current_date'] = saved['state']['current_date']
        for player in data['players']:
            player['team_id'] = saved.get('roster_overrides', {}).get(player['id'], player['team_id'])
        return data

    def read(self, path=None, **payload):
        return aa.team_wants_action(self.canonical, path or self.path, payload)

    def test_warm_reads_reuse_projection_and_do_not_leak_matches_to_callers(self):
        assets = [{'kind': 'player', 'id': 'p'}]
        first = self.read(assets=assets)
        self.assertTrue(first['matches']['p'])
        expected = deepcopy(first)
        first['matches']['p'][0]['reasons'].append('corrupted by caller')
        first['entries'][0]['conditions'].clear()
        first['suggestions'].clear()
        first['teams'].clear()
        self.assertEqual(self.read(assets=assets), expected)
        self.assertEqual(self.overlay.call_count, 1)
        self.assertEqual(self.project.call_count, 1)
        self.assertEqual(self.validate.call_count, 1)
        self.assertEqual(json.loads(self.path.read_text()), self.saved)

    def test_saved_revision_replaces_context_and_changes_stale_upgrade_ownership(self):
        self.saved['team_trade_wants']['a']['entries'] = [
            {'id': 'up', 'kind': 'upgrade', 'target_player_id': 'old', 'positions': [], 'conditions': [],
             'target_snapshot': {'facts': {'overall': 75}, 'positions': ['SF']}}]
        self.store(self.path, self.saved)
        self.assertTrue(self.read()['entries'][0]['active'])
        previous = aa.dashboard_read_context(self.canonical, self.path)
        self.saved['roster_overrides'] = {'old': 'b'}
        self.store(self.path, self.saved)
        self.assertFalse(self.read()['entries'][0]['active'])
        self.assertIsNot(previous, aa.dashboard_read_context(self.canonical, self.path))
        self.assertEqual(self.project.call_count, 2)

    def test_edit_and_ack_use_fresh_owned_context_and_revision_checks(self):
        self.read()
        cache = aa.dashboard_read_context(self.canonical, self.path)
        self.read()['entries'].clear()
        with patch.object(aa, 'dashboard_read_context', side_effect=AssertionError('edit reused read view')):
            changed = aa.team_wants_action(self.canonical, self.path,
                {'revision': 1, 'entries': []}, 'set_team_wants')
        self.assertEqual(changed['revision'], 2)
        self.assertEqual(self.read()['entries'], [])
        self.assertIsNot(cache, aa.dashboard_read_context(self.canonical, self.path))
        with self.assertRaises(aa.AppActionError):
            aa.team_wants_action(self.canonical, self.path, {'team': 'B', 'entries': []}, 'set_team_wants')
        with self.assertRaises(aa.AppActionError):
            aa.team_wants_action(self.canonical, self.path, {'revision': 1, 'entries': []}, 'set_team_wants')
        with self.assertRaises(aa.AppActionError):
            aa.team_wants_action(self.canonical, self.path, {'reminder_token': 'old'}, 'acknowledge_team_wants')

    def test_alternating_careers_baseline_identity_and_eviction_release(self):
        self.read()
        reference = weakref.ref(aa.dashboard_read_context(self.canonical, self.path)['active'])
        for i in range(2):
            path = Path(self.directory.name) / f'other{i}.json'
            saved = deepcopy(self.saved)
            saved['team_trade_wants']['a']['entries'] = []
            self.store(path, saved)
            self.assertEqual(self.read(path)['entries'], [])
        # Mock call histories own their arguments; discard those diagnostic references.
        self.project.reset_mock()
        self.facts.reset_mock()
        gc.collect()
        self.assertEqual(len(aa._READ_CACHE), 2)
        self.assertIsNone(reference())
        self.read()
        old = aa.dashboard_read_context(self.canonical, self.path)
        other = {**self.canonical, '_baseline_identity': 'different-source'}
        aa.team_wants_action(other, self.path, {})
        self.assertIsNot(old, aa.dashboard_read_context(other, self.path))

    def test_dispatch_serializes_wants_read_with_mutations(self):
        lock_depth = []
        @contextmanager
        def locked(path):
            lock_depth.append(path)
            try:
                yield
            finally:
                lock_depth.pop()
        def dispatch(*args):
            self.assertEqual(lock_depth, [self.path.resolve()])
            return {'locked': True}
        with patch.object(aa, 'save_lock', locked), patch.object(aa, 'dispatch_save_action', side_effect=dispatch):
            result = aa.dispatch_app_action('team_wants', {'save_path': str(self.path)},
                root=self.directory.name, save_dir=self.directory.name, canonical=self.canonical)
        self.assertEqual(result, {'locked': True})
        self.assertEqual(lock_depth, [])
