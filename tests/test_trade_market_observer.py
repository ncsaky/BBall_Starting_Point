from copy import deepcopy
import json
import gzip
from pathlib import Path
import tempfile
import unittest

from nba_gm_data import transactions as tx, play
from trade_market_observer import MarketObserver, classify_trade, context_snapshot
import test_transaction_application_audit as fixtures


class MarketObserverTests(unittest.TestCase):
    def fixture(self):
        data = fixtures.payroll_canonical()
        saved = {'version': 'league_save_v1', 'meta': {'user_team_id': 'team_z', 'season': '2026-27'},
                 'state': {'current_date': '2026-10-01', 'phase': 'preseason'},
                 'pending_trade_proposals': [fixtures.trade()], 'transaction_logs': [],
                 'roster_overrides': {}, 'contract_overrides': {}, 'draft_pick_overrides': {}}
        return data, saved

    def test_snapshot_does_not_seed_fields_in_authoritative_save(self):
        data, saved = self.fixture()
        before, original = deepcopy(saved), deepcopy(data)
        row = context_snapshot(data, saved, ['team_a', 'team_b'], [{'kind': 'player', 'id': 'p'}])
        self.assertEqual(saved, before)
        self.assertEqual(data, original)
        self.assertEqual(row['assets'][0]['remaining_salary_millions'], 5)

    def test_observation_preserves_real_application_and_aliases(self):
        data, saved = self.fixture()
        plain, observed = deepcopy(saved), deepcopy(saved)
        original = tx.apply_trade_to_state
        expected = original(plain, 't', date='2026-10-01', canonical=data)
        with tempfile.TemporaryDirectory() as td:
            with MarketObserver(Path('.'), td):
                actual = play.apply_trade_to_state(observed, 't', date='2026-10-01', canonical=data)
            self.assertIs(tx.apply_trade_to_state, original)
            self.assertEqual(actual, expected)
            self.assertEqual(observed, plain)
            events = [json.loads(s) for s in (Path(td)/'market-events.jsonl').read_text().splitlines()]
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['before']['assets'][0]['team_id'], 'team_a')
        self.assertEqual(event['after']['assets'][0]['team_id'], 'team_b')
        self.assertEqual(event['before']['teams']['team_a']['payroll_millions'], 5)
        self.assertEqual(event['after']['teams']['team_a']['payroll_millions'], 0)

    def test_quality_class_and_salary_dump_are_separate(self):
        before = {'assets': [{'kind': 'player', 'neutral_role_overall': 91, 'team_id': 'a', 'contract_surplus': -10}],
                  'teams': {'a': {'payroll_millions': 50}}}
        result = classify_trade(before, {'teams': {'a': {'payroll_millions': 30}}}, {})
        self.assertEqual(result['quality_class'], 'star')
        self.assertEqual(result['salary_dump_candidate_teams'], ['a'])
        before['assets'] = [{'kind': 'pick'}]
        self.assertEqual(classify_trade(before, {'teams': {'a': {'payroll_millions': 50}}}, {})['quality_class'], 'picks_only')

    def test_optional_full_capture_preserves_application_and_pretrade_ownership(self):
        data, saved = self.fixture()
        plain, observed = deepcopy(saved), deepcopy(saved)
        expected = tx.apply_trade_to_state(plain, 't', date='2026-10-01', canonical=data)
        with tempfile.TemporaryDirectory() as td:
            with MarketObserver(Path('.'), td, capture_players={'p'}):
                result = play.apply_trade_to_state(observed, 't', date='2026-10-01', canonical=data)
            files = list(Path(td).glob('context-*.json.gz'))
            self.assertEqual(len(files), 1)
            with gzip.open(files[0], 'rt') as handle:
                frozen = json.load(handle)
        self.assertEqual(result, expected)
        self.assertEqual(observed, plain)
        self.assertEqual(next(p for p in frozen['canonical']['players'] if p['id'] == 'p')['team_id'], 'team_a')
        self.assertEqual(frozen['candidate']['proposal']['id'], 't')


if __name__ == '__main__':
    unittest.main()
