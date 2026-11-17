"""Regression: an AI multi-team offer carrying a pick-swap condition must re-evaluate without crashing.

Seed 103 crashed a whole sim day ("Every draft condition must refer to one selected pick") because
prepare_ai_trade_candidate re-evaluated the stored transfers, where the swapped pick had become a pick_swap asset.
"""
import unittest
from unittest.mock import patch

from nba_gm_data import transactions as tx


class PickSwapRevalidationTests(unittest.TestCase):
    def test_prepare_candidate_restores_the_swapped_pick(self):
        candidate = {
            'proposal': {'id': 'p1', 'date': '2026-10-21', 'transfers': [
                {'from_team_id': 'a', 'to_team_id': 'b', 'assets': [{'kind': 'player', 'id': 'x'}]},
                {'from_team_id': 'c', 'to_team_id': 'a', 'assets': [{'kind': 'pick_swap', 'id': 'swap1'}]},
            ]},
            'pick_rules': [{'type': 'pick_swap', 'pick_id': 'pick-c-2028-2', 'other_pick_id': 'pick-a-2028-2'}],
            'pick_obligation_terms': [{'id': 'swap1', 'type': 'pick_swap', 'pending_asset_grant': True,
                                       'primary_pick_id': 'pick-c-2028-2'}],
        }
        seen = {}

        def fake_evaluate(canonical, transfers, **kwargs):
            seen['transfers'] = transfers
            return {'proposal': candidate['proposal'], 'legality': {'status': 'legal'}, 'evaluations': []}

        with patch('nba_gm_data.multi_team_trades.evaluate_multi_team_trade', fake_evaluate):
            try:
                tx.prepare_ai_trade_candidate({}, candidate, seed=103)
            except Exception:
                pass  # presentation details after evaluation are not under test
        assets = [a for leg in seen['transfers'] for a in leg['assets']]
        self.assertIn({'kind': 'pick', 'value': 'pick-c-2028-2'}, assets)
        self.assertNotIn('pick_swap', {a['kind'] for a in assets})


if __name__ == '__main__':
    unittest.main()
