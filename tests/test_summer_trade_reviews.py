from contextlib import ExitStack
import unittest
from unittest.mock import patch

from nba_gm_data import play, transactions as tx


class SummerTradeReviewTests(unittest.TestCase):
    def candidate(self, name, kind='general_market_trade'):
        return {'accepted_by_all': True, 'legality': {'status': 'legal'},
                'proposal': {'id': name, 'from_team_id': 'a', 'to_team_id': 'b',
                             'from_assets': [], 'to_assets': []}, 'free_agency_context': {'kind': kind}}

    def run_review(self, slots=2, fallback=None, general=None):
        saved = {'meta': {'user_team_id': 'human'}, 'state': {'current_date': '2027-07-04'},
                 'free_agency_state': {'season': '2026-27', 'day': 4, 'ai_general_trade_count': 3}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(play, 'queue_summer_trade_offers'))
            stack.enter_context(patch.object(play, 'resolve_team', return_value={'id': 'human'}))
            stack.enter_context(patch.object(play, 'free_agency_fallback_trade_candidates', return_value=fallback or []))
            # TRADE-VOLUME-2: AI-to-AI trades on free-agency days have their own slots (up to six a day).
            stack.enter_context(patch('nba_gm_data.trade_calendar.free_agency_trade_slots', return_value=slots))
            generate = stack.enter_context(patch.object(play, 'free_agency_general_trade_candidates',
                return_value=general or [self.candidate('g1'), self.candidate('g2')]))
            apply = stack.enter_context(patch.object(play, 'apply_trade_to_state', return_value={'status': 'applied'}))
            stack.enter_context(patch.object(play, 'trade_headline_from_payload', return_value='Trade'))
            first = play.maybe_run_free_agency_ai_trades_state({}, saved, {}, 'HUMAN', 17, phase='post_resolution')
            second = play.maybe_run_free_agency_ai_trades_state({}, saved, {}, 'HUMAN', 17, phase='post_resolution')
            return first, second, generate.call_count, apply.call_count, saved

    def test_three_old_general_deals_do_not_close_the_summer_market(self):
        first, second, generated, applied, saved = self.run_review()
        self.assertEqual(first['applied_count'], 2)
        self.assertEqual(second['applied_count'], 0)
        self.assertEqual((generated, applied), (1, 2))
        self.assertEqual(saved['free_agency_state']['ai_general_trade_count'], 5)

    def test_quiet_calendar_day_does_not_force_general_activity(self):
        first, _, generated, applied, _ = self.run_review(slots=0)
        self.assertEqual((first['applied_count'], generated, applied), (0, 0, 0))

    def test_target_fallback_keeps_priority_and_daily_capacity_is_bounded(self):
        from nba_gm_data.trade_calendar import FREE_AGENCY_TRADES_PER_DAY
        fallback = self.candidate('fallback', 'missed_target_fallback')
        first, _, _, applied, _ = self.run_review(fallback=[fallback])
        self.assertEqual((first['applied_count'], applied), (3, 3))  # the fallback, then the day's two slots
        many = [self.candidate(f'f{i}', 'missed_target_fallback') for i in range(FREE_AGENCY_TRADES_PER_DAY + 2)]
        first, _, generated, applied, _ = self.run_review(fallback=many)
        self.assertEqual((first['applied_count'], generated, applied),
                         (FREE_AGENCY_TRADES_PER_DAY, 0, FREE_AGENCY_TRADES_PER_DAY))

    def test_rejected_or_human_deals_are_not_executed(self):
        refused, human = self.candidate('refused'), self.candidate('human')
        refused['accepted_by_all'] = False
        human['proposal']['to_team_id'] = 'human'
        first, _, _, applied, _ = self.run_review(general=[refused, human])
        self.assertEqual((first['applied_count'], applied), (0, 0))

    def test_general_search_reserves_assets_and_respects_requested_capacity(self):
        candidates = [self.candidate(str(i)) for i in range(4)]
        with patch.object(tx, 'simulate_ai_trades', return_value={'proposals': candidates}) as search:
            result = play.free_agency_general_trade_candidates({}, {'state': {'current_date': '2027-07-01'}},
                'human', 17, max_results=2)
        self.assertEqual(len(result), 2)
        self.assertTrue(search.call_args.kwargs['reserve_assets'])


if __name__ == '__main__':
    unittest.main()
