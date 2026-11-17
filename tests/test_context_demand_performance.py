"""Demanded strategy outputs and bounded read-context ownership are exact."""
from copy import deepcopy
import gc
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data import app_actions as aa, transactions as tx, team_planning as planning
from nba_gm_data.save import canonical_with_save, load_save

ROOT = Path(__file__).resolve().parents[1]


class ContextDemandPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = aa.load_app_canonical(ROOT)
        path = ROOT / 'output/pick-investment-2026-10-28/stable17/saves/trade_year.json'
        if not path.exists():  # captured output artifact removed by the 2026-11-16 disk cleanup
            raise unittest.SkipTest(f'{path} is missing; regenerate it')
        cls.saved = load_save(path)

    def assert_full_equal(self, source):
        original = deepcopy(source)
        self.assertEqual(tx.build_transaction_context(deepcopy(source)),
                         tx.full_transaction_context_reference(deepcopy(source)))
        self.assertEqual(source, original)

    def test_all_recorded_real_build_inputs_match_the_full_fresh_fallback(self):
        path = ROOT / 'output/context-demand-pass/attribution-before/context-builds.json'
        if not path.exists():
            self.skipTest('Run diagnose_context_builds.py to replay the bounded real caller inputs')
        records = json.loads(path.read_text())['builds']
        self.assertEqual(len(records), 9)
        for record in records:
            with self.subTest(build=record['number']):
                with gzip.open(ROOT / record['input_path'], 'rt') as stream:
                    source = json.load(stream)
                source['_allow_internal_caches'] = True
                self.assert_full_equal(source)

    def test_full_outputs_match_after_contract_health_owner_plans_wants_and_pick_changes(self):
        source = canonical_with_save(self.base, deepcopy(self.saved))
        pid = source['players'][0]['id']
        for change in (
            lambda: None,
            lambda: source['contracts'][0]['seasons'][0].update(salary=42_000_000, guaranteed_salary=40_000_000),
            lambda: source['players'][0].update(team_id=source['teams'][1]['id']),
            lambda: source.setdefault('player_health_states', []).append({'player_id': pid, 'availability_status': 'out', 'return_date': '2027-06-01'}),
            lambda: source.setdefault('team_plans', {}).update({source['teams'][0]['id']: {'core_ids': [pid], 'commit_until': '2027-06-30'}}),
            lambda: source.setdefault('team_trade_wants', {}).update({source['teams'][0]['id']: {'entries': [{'id': 'draft', 'kind': 'picks', 'round': 1, 'from': 1, 'through': 4, 'protection': 'any', 'quality': 'any'}]}}),
            lambda: source['draft_picks'][0].update(current_owner_team_id=source['teams'][2]['id']),
        ):
            change()
            self.assert_full_equal(source)

    def test_external_team_changes_recompute_league_relative_outputs(self):
        source = canonical_with_save(self.base, deepcopy(self.saved))
        before = tx.build_transaction_context(deepcopy(source))
        tid = source['teams'][-1]['id']
        ids = {p['id'] for p in source['players'] if p.get('team_id') == tid}
        for trait in source['traits']:
            if trait['player_id'] in ids:
                trait['value'] = 95
        after = tx.build_transaction_context(deepcopy(source))
        self.assertEqual(after, tx.full_transaction_context_reference(deepcopy(source)))
        ranks_before = {s['team_id']: s.get('league_rank') for s in before['team_strategic_states']}
        ranks_after = {s['team_id']: s.get('league_rank') for s in after['team_strategic_states']}
        self.assertNotEqual(ranks_after, ranks_before)

    def test_small_leagues_keep_their_preliminary_needs(self):
        from test_multi_team_trades import fixture
        for count in (1, 2, 3, 4):
            self.assert_full_equal(fixture('abcd'[:count]))

    def test_window_assessment_does_not_demand_discarded_preliminary_needs(self):
        source = canonical_with_save(self.base, deepcopy(self.saved))
        full = planning.window_assessments
        def assessment(canonical, states, values):
            self.assertTrue(all(s.needs == [] and s.excesses == [] for s in states))
            return full(canonical, states, values)
        with patch.object(planning, 'window_assessments', side_effect=assessment), \
             patch.object(tx, 'team_needs_and_excesses', wraps=tx.team_needs_and_excesses) as needs:
            actual = tx.build_transaction_context(source)
        self.assertEqual(needs.call_count, len(source['teams']))
        self.assertTrue(all(s['needs'] for s in actual['team_strategic_states']))

    def test_planning_intent_reuse_matches_the_old_second_fresh_build(self):
        path = ROOT / 'tests/fixtures/refresh_team_plans_roster_pass.py'
        namespace = dict(vars(planning))
        exec(compile(path.read_text(), str(path), 'exec'), namespace)
        old_refresh = namespace['refresh_team_plans']
        source = canonical_with_save(self.base, deepcopy(self.saved))
        saved = deepcopy(self.saved)
        for change in (lambda: None,
                       lambda: source['players'][0].update(team_id=source['teams'][1]['id']),
                       lambda: source['contracts'][0]['seasons'][0].update(salary=35_000_000),
                       lambda: source.setdefault('player_health_states', []).append({'player_id': source['players'][1]['id'], 'availability_status': 'out', 'return_date': '2028-01-01'}),
                       lambda: saved.setdefault('meta', {}).update(human_team_ids=[source['teams'][0]['id'], source['teams'][1]['id']])):
            change()
            saved.pop('team_plan_review_signature', None)
            saved['team_plan_review_date'] = '2027-02-03'
            left, right, old_save, new_save = deepcopy(source), deepcopy(source), deepcopy(saved), deepcopy(saved)
            self.assertEqual(old_refresh(left, old_save, '2027-02-03'), planning.refresh_team_plans(right, new_save, '2027-02-03'))
            self.assertEqual(old_save, new_save)
            self.assertEqual({k: v for k, v in left.items() if not k.startswith('_')},
                             {k: v for k, v in right.items() if not k.startswith('_')})
            self.assertNotIn('_strategy_model_version', right)

    def test_real_pending_terms_keep_full_context_outputs(self):
        source = canonical_with_save(self.base, deepcopy(self.saved))
        for offer in [o for o in self.saved['user_trade_offers'] if o.get('pick_obligation_terms')][:2]:
            active = tx.with_transaction_context(deepcopy(source))
            active = tx.canonical_with_pending_pick_terms(active, offer['pick_obligation_terms'])
            self.assert_full_equal(active)

    def test_fresh_roster_validation_does_not_consume_trade_block_entries(self):
        from nba_gm_data import trade_roster
        class UnusedBlock(list):
            def __iter__(self):
                raise AssertionError('Fresh roster validation consumed the trade block')
            def __bool__(self):
                raise AssertionError('Fresh roster validation tested the trade block')
        build = tx.build_transaction_context
        def with_unused_block(*a, **kw):
            result = build(*a, **kw)
            result['trade_block_entries'] = UnusedBlock()
            return result
        offers = [o for o in self.saved['user_trade_offers'] if o.get('pick_obligation_terms')][:2]
        self.assertEqual(len(offers), 2)
        for offer in offers:
            expected = trade_roster.live_roster_issues(self.base, deepcopy(self.saved), offer['proposal'], candidate=offer)
            with patch.object(tx, 'build_transaction_context', side_effect=with_unused_block):
                self.assertEqual(trade_roster.live_roster_issues(self.base, deepcopy(self.saved), offer['proposal'], candidate=offer), expected)

    def test_read_cache_is_lru_bounded_and_evicted_graphs_release(self):
        class Active(dict):
            pass
        with tempfile.TemporaryDirectory() as folder, patch.dict(aa._READ_CACHE, {}, clear=True), \
             patch.object(aa, 'load_save', side_effect=lambda p: {'version': 'test'}), \
             patch.object(aa, 'ensure_league_save_defaults', side_effect=lambda s,c:s), \
             patch.object(aa, 'canonical_with_save', side_effect=lambda c,s:Active(players=[])), \
             patch.object(aa, 'validate_save_components'):
            paths = [Path(folder) / f'{i}.json' for i in range(4)]
            canonical = {'_baseline_identity': 'read-cache-test'}
            for p in paths:
                p.write_text('{}')
            a = aa.dashboard_read_context(canonical, paths[0])
            a_ref = weakref.ref(a['active'])
            b = aa.dashboard_read_context(canonical, paths[1])
            b_ref = weakref.ref(b['active'])
            del a, b
            aa.dashboard_read_context(canonical, paths[0])  # The hit makes A newest.
            aa.dashboard_read_context(canonical, paths[2])
            gc.collect()
            self.assertIsNone(b_ref())
            self.assertIsNotNone(a_ref())
            self.assertEqual(len(aa._READ_CACHE), 2)
            # A revision change must replace A, without mutating an in-flight
            # reader that deliberately still owns its old context.
            held = aa.dashboard_read_context(canonical, paths[0])
            paths[0].write_text('{"revision":2}')
            newer = aa.dashboard_read_context(canonical, paths[0])
            self.assertIsNot(held, newer)
            self.assertIsNotNone(a_ref())
            del held
            gc.collect()
            self.assertIsNone(a_ref())
