from copy import deepcopy
import unittest
from unittest.mock import patch

from nba_gm_data import transactions as tx


class LiveTeamStrategyTests(unittest.TestCase):
    def test_imported_timelines_cannot_force_a_phase(self):
        cfg = tx.default_transaction_model_config()
        for timeline in ('research_pending', 'rebuilding', 'contending', 'contending_with_future_upside'):
            profile = {'timeline': timeline}
            self.assertEqual(tx.classify_team_phase(profile, 90, 28, 20, {}, cfg), 'contending')
            self.assertEqual(tx.classify_team_phase(profile, 40, 34, 0, {}, cfg), 'rebuilding')
            self.assertEqual(tx.classify_team_phase(profile, 62, 23, 80, {}, cfg), 'developing')

    def test_young_elite_team_is_not_stuck_developing(self):
        cfg = tx.default_transaction_model_config()
        self.assertEqual(tx.classify_team_phase({}, 66, 23, 85, {}, cfg), 'contending_with_future_upside')
        self.assertEqual(tx.classify_team_phase({}, 62, 31, 10, {}, cfg), 'retooling')

    def test_near_term_picks_follow_the_simulation_date(self):
        canonical = {'meta': {'current_date': '2033-10-01', 'active_season': '2033-34'}}
        picks = [{'season': str(y), 'round': 1} for y in (2027, 2034, 2035, 2036, 2037)]
        with patch.object(tx, 'tradeable_picks_for_team', return_value=picks), patch.object(tx, 'pick_asset_value', return_value=1):
            self.assertEqual(tx.team_pick_inventory(canonical, 't')['near_term_firsts'], 3)
        self.assertEqual(canonical['meta']['current_date'], '2033-10-01')

    def test_legacy_precomputed_strategy_is_rebuilt_once_and_then_cached(self):
        old = {'players': [{'id': 'p', 'team_id': 't'}], 'front_office_profiles': [{'team_id': 't'}],
               'team_strategic_states': [{'team_id': 't', 'phase': 'rebuilding'}],
               'player_asset_valuations': [{'player_id': 'p'}], 'trade_block_entries': []}
        before = deepcopy(old)
        self.assertFalse(tx.transaction_context_is_complete(old))
        new = {**old, '_strategy_model_version': tx.STRATEGY_MODEL_VERSION,
               'team_strategic_states': [{'team_id': 't', 'phase': 'contending'}]}
        with patch.object(tx, 'build_transaction_context', return_value=new) as build, \
             patch.object(tx, 'ensure_future_second_round_scaffolds'), \
             patch.object(tx, 'simplify_unsupported_pick_conditions'), \
             patch.object(tx, 'ensure_pick_value_context'), \
             patch.object(tx, 'annotate_pick_obligation_context'), \
             patch.object(tx, 'mark_pick_value_context_current'), \
             patch.object(tx, 'pick_value_context_current', return_value=True):
            rebuilt = tx.with_transaction_context(old)
            self.assertEqual(rebuilt['team_strategic_states'][0]['phase'], 'contending')
            self.assertIs(tx.with_transaction_context(rebuilt), rebuilt)
            self.assertEqual(build.call_count, 1)
        self.assertEqual(old, before)

    def test_contract_context_cannot_short_circuit_stale_strategy(self):
        from nba_gm_data import contract_ai as ca
        old = {'player_contract_market_profiles': ['stale'], 'player_contract_preferences': ['stale'],
               'extension_candidates': ['stale'], 'free_agent_candidates': ['stale']}
        with patch.object(ca, 'with_transaction_context', return_value={}) as tx_context, \
             patch.object(ca, 'build_contract_ai_context', return_value={'extension_candidates': ['fresh']}):
            result = ca.with_contract_context(old)
        tx_context.assert_called_once()
        self.assertEqual(result['extension_candidates'], ['fresh'])


if __name__ == '__main__':
    unittest.main()
