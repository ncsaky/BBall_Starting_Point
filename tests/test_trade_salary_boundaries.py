"""Salary application checks independent of evolving imported rosters."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import transactions as tx
from nba_gm_data.save import load_save, write_save


class TradeSalaryBoundaryTests(unittest.TestCase):
    def fixture(self):
        canonical = {'meta': {}, 'teams': [{'id': 'a', 'abbrev': 'A'}, {'id': 'b', 'abbrev': 'B'}],
                     'players': [{'id': pid, 'name': pid, 'team_id': tid, 'position': 'C', 'age': 25}
                                 for pid, tid in [('out', 'a'), ('in', 'b'), ('teammate', 'b')]],
                     'contracts': [{'player_id': pid, 'team_id': tid,
                                    'seasons': [{'season': '2026-27', 'salary': salary}]}
                                   for pid, tid, salary in [('out', 'a', 5_000_000), ('in', 'b', 2_000_000),
                                                           ('teammate', 'b', 20_000_000)]],
                     'draft_picks': [], 'traits': []}
        candidate = {'proposal': {'id': 'salary', 'date': '2026-11-29', 'from_team_id': 'a', 'to_team_id': 'b',
                     'from_assets': [{'kind': 'player', 'id': 'out'}], 'to_assets': [{'kind': 'player', 'id': 'in'}]},
                     'accepted_by_all': True, 'legality': {'status': 'legal'}, 'evaluations': []}
        saved = {'version': 'league_save_v1', 'meta': {'season': '2026-27'},
                 'state': {'current_date': '2026-11-29', 'phase': 'regular_season'},
                 'pending_trade_proposals': [candidate], 'roster_overrides': {}, 'contract_overrides': {},
                 'draft_pick_overrides': {}, 'transaction_logs': []}
        return canonical, saved

    def test_high_current_payroll_is_rechecked_without_mutation(self):
        canonical, saved = self.fixture()
        saved['contract_overrides']['teammate'] = {'team_id': 'b', 'seasons': [
            {'season': '2026-27', 'salary': 500_000_000}]}
        before, data = deepcopy(saved), deepcopy(canonical)
        result = tx.apply_trade_to_state(saved, 'salary', canonical=canonical)
        self.assertEqual(result['status'], 'not_applied_salary_legality')
        self.assertIn('hard-cap', result['issues'][0])
        self.assertEqual(saved, before)
        self.assertEqual(canonical, data)

    def test_each_future_payroll_guardrail_is_rechecked(self):
        for season in ('2027-28', '2028-29', '2029-30'):
            with self.subTest(season=season):
                canonical, saved = self.fixture()
                canonical['contracts'][0]['seasons'].append({'season': season, 'salary': 10_000_000})
                canonical['contracts'][2]['seasons'].append({'season': season, 'salary': 500_000_000})
                before = deepcopy(saved)
                result = tx.apply_trade_to_state(saved, 'salary', canonical=canonical)
                self.assertEqual(result['status'], 'not_applied_salary_legality')
                self.assertTrue(any(f'{season} hard-cap overage' in issue for issue in result['issues']))
                self.assertEqual(saved, before)

    def test_missing_or_corrupt_canonical_data_blocks_file_apply_without_writes(self):
        for error in (FileNotFoundError('missing'), ValueError('corrupt JSON')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as td:
                _, saved = self.fixture()
                path = Path(td)/'salary.json'
                write_save(path, saved)
                before, mtime = path.read_bytes(), path.stat().st_mtime_ns
                with patch('nba_gm_data.storage.load_universe_json', side_effect=error):
                    result = tx.apply_trade_to_save(path, 'salary')
                self.assertEqual(result['status'], 'not_applied_salary_legality')
                self.assertEqual(result['legality']['status'], 'manual_review_required')
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(path.stat().st_mtime_ns, mtime)
                self.assertEqual(load_save(path)['pending_trade_proposals'][0]['proposal']['id'], 'salary')

    def test_missing_preserved_roster_blocks_without_mutating_save(self):
        canonical, saved = self.fixture()
        before = deepcopy(saved)
        with patch('nba_gm_data.save.baseline_for_save', side_effect=FileNotFoundError('archive missing')):
            result = tx.apply_trade_to_state(saved, 'salary', canonical=canonical)
        self.assertEqual(result['status'], 'not_applied_salary_legality')
        self.assertEqual(result['legality']['status'], 'manual_review_required')
        self.assertEqual(saved, before)

    def test_salary_reducing_trade_is_not_blocked_merely_for_existing_overage(self):
        canonical, saved = self.fixture()
        canonical['contracts'][0]['seasons'][0]['salary'] = 2_000_000
        canonical['contracts'][1]['seasons'][0]['salary'] = 5_000_000
        canonical['contracts'][2]['seasons'][0]['salary'] = 500_000_000
        result = tx.apply_trade_to_state(saved, 'salary', canonical=canonical)
        self.assertEqual(result['status'], 'applied')

    def test_unresolved_current_traded_salary_stays_blocked(self):
        canonical, saved = self.fixture()
        canonical['contracts'][0]['seasons'][0]['salary'] = None
        before = deepcopy(saved)
        result = tx.apply_trade_to_state(saved, 'salary', canonical=canonical)
        self.assertEqual(result['status'], 'not_applied_salary_legality')
        self.assertEqual(result['legality']['status'], 'manual_review_required')
        self.assertEqual(saved, before)

    def test_legal_trade_still_executes_and_cannot_repeat(self):
        canonical, saved = self.fixture()
        result = tx.apply_trade_to_state(saved, 'salary', canonical=canonical)
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(saved['roster_overrides'], {'out': 'b', 'in': 'a'})
        before = deepcopy(saved)
        self.assertEqual(tx.apply_trade_to_state(saved, 'salary', canonical=canonical)['status'], 'not_found')
        self.assertEqual(saved, before)


if __name__ == '__main__':
    unittest.main()
