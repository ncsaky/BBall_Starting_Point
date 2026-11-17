"""Exact pre-pass comparisons; forecast-only caches must not change decisions."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import gc
import json
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import weakref

from nba_gm_data import transactions as tx, trade_roster as tr, save, sim
from nba_gm_data import contract_protection as protection
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.roster_forecast import ForecastSnapshot
from nba_gm_data.save_recovery import restore_export
from nba_gm_data.trade_review import MarketReview

ROOT = Path(__file__).resolve().parents[1]


def _fresh_search_context(canonical):
    """Search context with no forecast snapshot, memo dictionaries or internal-cache opt-in."""
    plain = {k: v for k, v in canonical.items()
             if k not in ('_allow_internal_caches', '_roster_forecast_snapshot', '_roster_forecast_stats')}
    return {**plain, '_trade_search_roles': {}, '_trade_search_rosters': {},
            '_trade_financial_facts': {}, '_trade_movement_classes': {}}


@contextmanager
def reference():
    """Unoptimized reference path through the *current* code.

    The previous version compared against frozen Oct-29 copies of the functions, which went stale when the
    strategy model, spatial fit and cap rules changed intentionally. The reference now re-evaluates the live
    code with every forecast-only cache disabled: eager full-feature transaction contexts, no forecast
    snapshot, and the uncached attribute summary.
    """
    eager = tx.build_transaction_context
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            tx, 'build_transaction_context',
            lambda canonical, config=None, **_: eager(canonical, config, _full_reference=True)))
        stack.enter_context(patch.object(tx, 'trade_search_context', _fresh_search_context))
        stack.enter_context(patch.object(save, 'player_attribute_summary', save._uncached_player_attribute_summary))
        yield


OLD_ATTRS = save._uncached_player_attribute_summary


class RosterForecastPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = load_app_canonical(ROOT)
        cls.starting = tx.with_transaction_context(deepcopy(cls.base))
        fixture = ROOT / 'tests/fixtures/trade_year_seed17.nbagm.zip'
        # Tests that need the deadline-day save skip explicitly if the tracked fixture is absent;
        # starting-roster tests do not depend on it.
        cls.saved = None
        if fixture.exists():
            folder = tempfile.mkdtemp()
            cls.addClassCleanup(shutil.rmtree, folder, True)
            path = Path(folder) / 'trade_year.json'
            restore_export(path, fixture.read_bytes())
            cls.saved = save.load_save(path)
        cls.mature = (tx.with_transaction_context(save.canonical_with_save(cls.base, deepcopy(cls.saved)))
                      if cls.saved is not None else None)

    def require_mature(self):
        if self.mature is None:
            self.skipTest('tests/fixtures/trade_year_seed17.nbagm.zip is missing; regenerate it')

    def assert_projections(self, source, team_ids, variant_limit=4):
        public = {k: v for k, v in source.items() if not k.startswith('_')}
        original = deepcopy(public)
        active = tx.trade_search_context(source)
        for tid in team_ids:
            own = [p['id'] for p in source['players'] if p.get('team_id') == tid and not p.get('_inactive_player')]
            other = [p['id'] for p in source['players'] if p.get('team_id') not in (None, tid) and not p.get('_inactive_player')]
            variants = [((), ()), (own[:1], ()), ((), other[:2]), (own[:2], other[:3])]
            for outgoing, incoming in variants[:variant_limit]:
                with self.subTest(team=tid, outgoing=outgoing, incoming=incoming):
                    with reference():
                        old = tr.roster_projection(tx.trade_search_context(deepcopy(source)), tid, outgoing, incoming)
                    actual = tr.roster_projection(active, tid, outgoing, incoming)
                    self.assertEqual(actual, old)
                    if actual['cuts']:
                        actual['cuts'][0]['name'] = 'Caller edit'
                        self.assertEqual(tr.roster_projection(active, tid, outgoing, incoming), old)
        self.assertEqual(public, original)

    def test_all_30_starting_rosters_and_incoming_outgoing_combinations_are_exact(self):
        ids = [t['id'] for t in self.starting['teams']]
        self.assertEqual(len(ids), 30)
        self.assert_projections(deepcopy(self.starting), ids)

    def test_mature_injured_oversized_and_center_rosters_are_exact(self):
        self.require_mature()
        source = deepcopy(self.mature)
        ids = [t['id'] for t in source['teams'][:8]]
        hurt = source['players'][0]['id']
        source.setdefault('_trade_planning_save', {})['health_states'] = [
            {'player_id': hurt, 'availability_status': 'out', 'return_date': '2027-05-01'}]
        for p in source['players'][:8]:
            p['position'] = 'C'
        self.assert_projections(source, ids)

    def test_league_relative_fresh_context_is_identical_for_every_starting_and_mature_team(self):
        for source in (self.base, self.mature):
            if source is None:
                continue
            with reference():
                old = tx.build_transaction_context(deepcopy(source))
            self.assertEqual(tx.build_transaction_context(deepcopy(source)), old)

    def test_exact_feature_and_attribute_reuse_keeps_minutes_and_trial_players_independent(self):
        source = deepcopy(self.starting)
        snapshot = ForecastSnapshot(source)
        player = deepcopy(source['players'][0])
        for minutes in (0, 12, 24, 31.25, 42, 12):
            row = dict(deepcopy(player), minutes_projection=minutes, team_id=source['teams'][1]['id'])
            view = snapshot.view(source, [row])
            fresh = {k: v for k, v in view.items() if not k.startswith('_')}
            fresh['_allow_internal_caches'] = True
            self.assertEqual(sim.player_feature_vector(view, row, include_spatial=False),
                             sim.player_feature_vector(fresh, row, include_spatial=False))
            expected = OLD_ATTRS(fresh, row['id'])
            actual = save.player_attribute_summary(view, row['id'])
            self.assertEqual(actual, expected)
            actual['overall'] = -999
            self.assertEqual(save.player_attribute_summary(view, row['id']), expected)
        self.assertGreater(snapshot.stats['features.hits'], 0)
        self.assertGreater(snapshot.stats['attributes.hits'], 0)
        self.assertEqual(source, self.starting)

    def test_oversized_core_injury_insurance_and_pick_investment_outlooks_are_exact(self):
        self.require_mature()
        source = deepcopy(self.mature)
        tid = source['teams'][0]['id']
        own = [p for p in source['players'] if p.get('team_id') == tid]
        others = [p for p in source['players'] if p.get('team_id') not in (None, tid)][:4]
        source.setdefault('team_plans', {})[tid] = {'core_ids': [own[0]['id']], 'commit_until': '2027-06-30'}
        source['_trade_planning_save']['team_plans'] = source['team_plans']
        source['_trade_planning_save']['health_states'] = [
            {'player_id': p['id'], 'availability_status': 'out', 'return_date': '2027-05-01'} for p in own[:3]]
        picks = tx.tradeable_picks_for_team(source, tid)
        incoming = [{'kind': 'player', 'id': p['id']} for p in others]
        outgoing = [{'kind': 'player', 'id': own[-1]['id']}]
        outgoing += [{'kind': 'pick', 'id': p['id']} for p in picks[:2]]
        with reference():
            old = tr.trade_roster_outlook(tx.trade_search_context(deepcopy(source)), tid, incoming, outgoing)
        self.assertEqual(tr.trade_roster_outlook(tx.trade_search_context(source), tid, incoming, outgoing), old)

    def test_review_rebuilds_indexes_after_in_place_health_contract_owner_plan_and_wants_changes(self):
        source = deepcopy(self.starting)
        review = MarketReview()
        active = review.prepare(source)
        first = active['_roster_forecast_snapshot']
        changes = (
            lambda: source['players'][0].update(team_id=source['teams'][1]['id']),
            lambda: source['contracts'][0]['seasons'][0].update(salary=2_000_000),
            lambda: source.update(player_health_states=[{'player_id': source['players'][0]['id'], 'availability_status': 'out'}]),
            lambda: source.setdefault('team_plans', {}).update({source['teams'][0]['id']: {'core_ids': [source['players'][0]['id']]}}),
            lambda: source.setdefault('team_trade_wants', {}).update({source['teams'][0]['id']: {'entries': []}}),
            lambda: source['traits'][0].update(value=12.5),
        )
        for change in changes:
            change()
            active = review.prepare(source)
            self.assertIsNot(active['_roster_forecast_snapshot'], first)
            first = active['_roster_forecast_snapshot']
        review.close()

    def test_fresh_validation_matches_after_sequential_state_changes_and_never_mutates_save(self):
        self.require_mature()
        source = deepcopy(self.base)
        saved = deepcopy(self.saved)
        tid = self.mature['teams'][0]['id']
        own = [p for p in self.mature['players'] if p.get('team_id') == tid]
        other = next(p for p in self.mature['players'] if p.get('team_id') not in (None, tid))
        proposal = {'id': 'fresh-roster-check', 'from_team_id': tid, 'to_team_id': other['team_id'],
                    'from_assets': [{'kind': 'player', 'id': own[0]['id']}],
                    'to_assets': [{'kind': 'player', 'id': other['id']}]}
        mutations = (lambda: None,
            lambda: saved.setdefault('roster_overrides', {}).update({own[1]['id']: other['team_id']}),
            lambda: saved.setdefault('contract_overrides', {}).update({own[0]['id']: {'team_id': tid,
                'seasons': [{'season': '2026-27', 'salary': 42_000_000, 'guaranteed_salary': 42_000_000}]}}),
            lambda: saved.setdefault('health_states', []).append({'player_id': own[0]['id'], 'availability_status': 'out', 'return_date': '2027-06-01'}),
            lambda: saved.setdefault('team_plans', {}).update({tid: {'core_ids': [own[0]['id']], 'commit_until': '2027-06-30'}}),
            lambda: saved.setdefault('rotation_overrides', {}).update({tid: {own[0]['id']: 40}}))
        for mutation in mutations:
            mutation()
            before = deepcopy(saved)
            with reference():
                expected = tr.live_roster_issues(source, saved, proposal)
            self.assertEqual(tr.live_roster_issues(source, saved, proposal), expected)
            self.assertEqual(saved, before)
        self.assertEqual(source, self.base)

    def test_forecast_memos_are_bounded_and_review_graph_is_released(self):
        review = MarketReview()
        active = review.prepare(deepcopy(self.starting))
        snapshot = active['_roster_forecast_snapshot']
        for i in range(8200):
            snapshot.features[i] = i
            snapshot.attributes[i] = {'overall': i}
        self.assertLessEqual(len(snapshot.features), 8192)
        self.assertLessEqual(len(snapshot.attributes), 4096)
        ref = weakref.ref(snapshot)
        review.close()
        del active, snapshot
        gc.collect()
        self.assertIsNone(ref())

    def test_retention_reuses_exact_season_windows_without_editing_schedules_or_save(self):
        self.require_mature()
        source = tx.trade_search_context(deepcopy(self.mature))
        saved = tr.planning_save(source)
        plain = {k: v for k, v in saved.items() if k != '_forecast_season_windows'}
        original = deepcopy(plain)
        player = source['players'][0]
        expected = protection.waiver_projection(source, plain, player, player.get('team_id'))
        with patch.object(protection, '_uncached_season_window', wraps=protection._uncached_season_window) as calculate:
            for _ in range(4):
                self.assertEqual(protection.waiver_projection(source, saved, player, player.get('team_id')), expected)
            # One calculation per distinct season, including absent schedules.
            self.assertEqual(calculate.call_count, len(source['_roster_forecast_snapshot'].season_windows))
        self.assertEqual(plain, original)
        self.assertNotIn('_forecast_season_windows', source['_trade_planning_save'])

    def test_fresh_validation_of_real_pending_protection_and_swap_terms_is_exact(self):
        self.require_mature()
        offers = [o for o in self.saved.get('user_trade_offers', []) if o.get('pick_obligation_terms')]
        self.assertGreaterEqual(len(offers), 2)
        for candidate in offers[:2]:
            saved = deepcopy(self.saved)
            original = deepcopy(saved)
            with reference():
                expected = tr.live_roster_issues(self.base, saved, candidate['proposal'], candidate=candidate)
            self.assertEqual(tr.live_roster_issues(self.base, saved, candidate['proposal'], candidate=candidate), expected)
            self.assertEqual(saved, original)

    def test_archived_2036_generated_and_injured_rosters_without_advancing_the_career(self):
        path = ROOT / 'output/roster-forecast-pass/fixtures/mature2036.json'
        if not path.exists():
            self.skipTest('Run scripts/prepare_roster_forecast_fixture.py for the archived 2036 probe')
        saved = json.loads(path.read_text())
        self.assertEqual(saved['state']['current_date'], '2036-11-01')
        source = tx.with_transaction_context(save.canonical_with_save(self.base, saved))
        self.assertGreater(len(source['players']), len(self.starting['players']))
        source['_trade_planning_save']['health_states'] = [
            *source['_trade_planning_save']['health_states'],
            *({'player_id': p['id'], 'availability_status': 'out', 'return_date': '2037-04-01'}
              for p in source['players'] if p.get('team_id') == source['teams'][0]['id'])]
        self.assert_projections(source, [t['id'] for t in source['teams'][:6]])
