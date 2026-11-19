from datetime import date, timedelta
import statistics
import unittest
from unittest.mock import patch

from nba_gm_data.trade_calendar import market_day, summer_offer_slots
from nba_gm_data import roster_space, save as sv


class TradeCalendarTests(unittest.TestCase):
    def dates(self, start='2026-10-01', end='2027-02-05'):
        current, final = date.fromisoformat(start), date.fromisoformat(end)
        while current <= final:
            yield current.isoformat()
            current += timedelta(days=1)

    def test_calendar_is_date_seeded_variable_and_deadline_weighted(self):
        totals, peaks, autumns = [], [], []
        for seed in range(150):
            rows = [(day, market_day(day, seed, 2026, '2027-02-05')) for day in self.dates()]
            totals.append(sum(r['slots'] for _, r in rows))
            peaks.append(sum(r['slots'] for day, r in rows if day >= '2027-01-30'))
            autumns.append(sum(r['slots'] for day, r in rows if day < '2026-12-01'))
            self.assertEqual(rows, [(day, market_day(day, seed, 2026, '2027-02-05')) for day in self.dates()])
        self.assertGreater(statistics.mean(peaks), .65 * statistics.mean(totals))
        self.assertLess(statistics.mean(autumns), 3)
        self.assertGreater(len(set(totals)), 15)
        self.assertGreater(max(totals), 28)
        self.assertLess(min(totals), 28)

    def test_no_market_after_deadline_and_no_loss_of_inbound_review_on_quiet_days(self):
        self.assertEqual(market_day('2027-02-06', 17, 2026, '2027-02-05'), {'review': False, 'slots': 0})
        quiet = [market_day(day, 17, 2026, '2027-02-05') for day in self.dates() if day < '2026-12-01']
        self.assertTrue(any(r['review'] and not r['slots'] for r in quiet))

    def test_incoming_offer_opportunities_share_deadline_concentration(self):
        quiet, peak = [], []
        for seed in range(100):
            rows = [(day, market_day(day, seed, 2026, '2027-02-05')) for day in self.dates()]
            quiet.append(sum(r['offer_slots'] for day, r in rows if day < '2026-12-01')/61)
            peak.append(sum(r['offer_slots'] for day, r in rows if day >= '2027-01-30')/7)
            self.assertTrue(all(r['review'] for _, r in rows if r['offer_slots']))
        self.assertGreater(statistics.mean(peak), statistics.mean(quiet)*10)

    def test_summer_incoming_opportunities_peak_early_and_stop_outside_window(self):
        early = sum(summer_offer_slots(f'2027-07-{day:02}', seed) for seed in range(100) for day in range(1, 5))
        late = sum(summer_offer_slots(f'2027-07-{day:02}', seed) for seed in range(100) for day in range(12, 16))
        self.assertGreater(early, late*4)
        self.assertEqual(summer_offer_slots('2027-06-30', 17), 0)
        self.assertEqual(summer_offer_slots('2027-07-16', 17), 0)

    def test_summer_offers_reach_inbox_without_executing_or_repeating(self):
        from nba_gm_data import play, transactions as tx
        saved = {'meta': {'user_team_id': 'human'}, 'state': {'current_date': '2027-07-02'}}
        candidate = {'accepted_by_all': True, 'proposal': {'id': 'summer', 'from_team_id': 'a', 'to_team_id': 'human'}}
        with patch('nba_gm_data.trade_calendar.summer_offer_slots', return_value=2), \
             patch.object(tx, 'simulate_ai_trades', return_value={'proposals': [candidate]}), \
             patch.object(tx, 'user_facing_trade_candidate_ok', return_value=True), \
             patch.object(play, 'apply_trade_to_state') as apply:
            self.assertEqual(play.queue_summer_trade_offers({}, saved, 17), 1)
            self.assertEqual(play.queue_summer_trade_offers({}, saved, 17), 0)
            apply.assert_not_called()
        self.assertEqual(len(saved['user_trade_offers']), 1)
        self.assertEqual(saved['user_trade_offers'][0]['offer_context']['created_date'], '2027-07-02')

    def test_quiet_review_does_not_deliver_offers_outside_its_calendar_budget(self):
        from nba_gm_data import transactions as tx
        saved = {'meta': {'user_team_id': 'human'}, 'state': {'phase': 'regular_season'}}
        candidate = {'accepted_by_all': True, 'legality': {'status': 'legal'},
                     'proposal': {'id': 'quiet', 'from_team_id': 'a', 'to_team_id': 'human'}}
        with patch('nba_gm_data.trade_calendar.market_day', return_value={'review': True, 'slots': 0, 'offer_slots': 0}), \
             patch.object(tx, 'simulate_ai_trades', return_value={'proposals': [candidate]}):
            sv.queue_ai_recommendations({}, saved, '2027-01-19', '2027-01-20', 17)
        self.assertFalse(saved.get('user_trade_offers'))

    def test_roster_space_sale_never_liquidates_for_next_summer_during_games(self):
        for stamp, phase in [('2027-01-12', 'regular_season'), ('2027-06-10', 'playoffs'), ('2027-10-12', 'preseason')]:
            saved = {'state': {'current_date': stamp, 'phase': phase}}
            with patch('nba_gm_data.contract_protection.roster_signing_plan') as plan:
                self.assertEqual(roster_space.sale_candidates({}, saved, 'human', 17), [])
                plan.assert_not_called()

    def test_review_repeats_do_not_generate_extra_offers_and_28_old_trades_do_not_close_deadline(self):
        saved = {'meta': {'user_team_id': 'human'}, 'state': {'phase': 'regular_season'},
                 'transaction_logs': [{'transaction_type': 'trade', 'date': '2026-11-01'} for _ in range(28)]}
        proposals = [{'accepted_by_all': True, 'legality': {'status': 'legal'},
                      'proposal': {'id': str(i), 'from_team_id': 'a', 'to_team_id': 'b',
                                   'from_assets': [{'kind': 'player', 'id': f'p{i}'}], 'to_assets': []}} for i in range(20)]
        with patch('nba_gm_data.transactions.simulate_ai_trades', return_value={'proposals': proposals}) as generate:
            sv.queue_ai_recommendations({}, saved, '2027-02-04', '2027-02-05', 17)
            self.assertGreater(len(saved['pending_ai_actions'][0]['payload']['proposals']), 1)
            first = generate.call_count
            sv.queue_ai_recommendations({}, saved, '2027-02-04', '2027-02-05', 17)
            self.assertEqual(generate.call_count, first)

    def test_deeper_search_preserves_best_buyers_and_finds_a_later_package(self):
        from nba_gm_data import transactions as tx
        player = {'id': 'p', 'name': 'Target', 'team_id': 'seller'}
        buyers = [{'id': str(i), 'abbrev': str(i)} for i in range(15)]
        data = {'players': [player], 'trade_block_entries': [{'player_id': 'p', 'block_score': 70}]}
        checked = []
        def evaluate(*args, **kwargs):
            buyer, assets = args[2], args[4]
            checked.append((buyer, assets[0]['value']))
            return {'accepted_by_all': buyer == '0' and assets[0]['value'] == 'package7', 'legality': {'status': 'legal'},
                    'evaluations': [], 'proposal': {'id': buyer, 'from_assets': [], 'to_assets': []}}
        packages = [{'assets': [{'kind': 'pick', 'value': f'package{i}'}]} for i in range(12)]
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c, *a: c), \
             patch.object(tx, 'with_spatial_fit_context', side_effect=lambda c: c), \
             patch.object(tx, 'recently_traded_player_ids', return_value=set()), \
             patch.object(tx, 'team_by_id', return_value={'id': 'seller', 'abbrev': 'SELL'}), \
             patch.object(tx, 'buyer_teams_for_player', return_value=buyers), \
             patch.object(tx, 'buyer_offer_package_options', return_value=packages), \
             patch.object(tx, 'evaluate_trade_decision', side_effect=evaluate), \
             patch.object(tx, 'prepare_ai_trade_candidate', side_effect=lambda c, r, **kw: r):
            # The listed-player search (trade step 2 keeps it for offers to the human team).
            shallow = tx.simulate_ai_trades(data, '2027-02-05', '2027-02-05', seed=17, target_search=False)
            self.assertEqual(shallow['proposal_count'], 0)
            checked.clear()
            deep = tx.simulate_ai_trades(data, '2027-02-05', '2027-02-05', seed=17, search_depth=2, target_search=False)
            self.assertEqual(deep['proposal_count'], 1)
            self.assertEqual(checked[0][0], '0')
            self.assertEqual(deep['search_diagnostics']['packages'], 8)

    def test_execution_search_tries_alternatives_instead_of_reusing_an_asset(self):
        from nba_gm_data import transactions as tx
        players = [{'id': f'p{i}', 'name': f'Target{i}', 'team_id': 'seller'} for i in range(2)]
        data = {'players': players, 'trade_block_entries': [{'player_id': p['id'], 'block_score': 70} for p in players]}
        packages = [{'assets': [{'kind': 'player', 'value': value}]} for value in ('shared', 'alternate')]
        def evaluate(c, seller, buyer, outgoing, incoming, **kwargs):
            return {'accepted_by_all': True, 'legality': {'status': 'legal'}, 'evaluations': [],
                    'proposal': {'id': outgoing[0]['value']+incoming[0]['value'],
                                 'from_team_id': 'seller', 'to_team_id': 'buyer',
                                 'from_assets': [{'kind': 'player', 'id': outgoing[0]['value']}],
                                 'to_assets': [{'kind': 'player', 'id': incoming[0]['value']}]}}
        with patch.object(tx, 'with_transaction_context', side_effect=lambda c, *a: c), \
             patch.object(tx, 'with_spatial_fit_context', side_effect=lambda c: c), \
             patch.object(tx, 'recently_traded_player_ids', return_value=set()), \
             patch.object(tx, 'team_by_id', return_value={'id': 'seller', 'abbrev': 'SELL'}), \
             patch.object(tx, 'buyer_teams_for_player', return_value=[{'id': 'buyer', 'abbrev': 'BUY'}]), \
             patch.object(tx, 'buyer_offer_package_options', return_value=packages), \
             patch.object(tx, 'evaluate_trade_decision', side_effect=evaluate), \
             patch.object(tx, 'prepare_ai_trade_candidate', side_effect=lambda c, r, **kw: r):
            result = tx.simulate_ai_trades(data, '2027-02-05', '2027-02-05', reserve_assets=True, target_search=False)
        self.assertEqual(result['proposal_count'], 2)
        self.assertEqual(result['search_diagnostics']['asset_conflicts'], 1)
        self.assertEqual(result['proposals'][1]['proposal']['to_assets'][0]['id'], 'alternate')

    def test_private_inquiries_do_not_list_core_or_deep_bench_players(self):
        from nba_gm_data import transactions as tx
        players = [{'id': p, 'team_id': 'a', 'minutes_projection': minutes}
                   for p, minutes in [('rotation', 24), ('core', 32), ('bench', 4)]]
        data = {'meta': {'current_date': '2027-02-05'}, 'players': players,
                'player_asset_valuations': [{'player_id': p['id'], 'player_value': 50} for p in players],
                'team_plans': {'a': {'core_ids': ['core'], 'commit_until': '2027-06-30'}}, 'trade_block_entries': []}
        result = tx.private_trade_targets(data, set(), 17, '2027-02-05')
        self.assertEqual([r['player_id'] for r in result], ['rotation'])
        self.assertEqual(data['trade_block_entries'], [])

    def test_bounded_ai_discretion_cannot_bypass_core_commitment(self):
        from nba_gm_data import transactions as tx
        data = {'meta': {'current_date': '2027-02-05'},
                'team_plans': {'a': {'core_ids': ['core'], 'commit_until': '2027-06-30'}}}
        candidate = {'accepted_by_all': False, 'legality': {'status': 'legal'},
                     'proposal': {'from_team_id': 'a', 'to_team_id': 'b',
                                  'from_assets': [{'kind': 'player', 'id': 'core'}], 'to_assets': []},
                     'evaluations': [{'perspective_team_id': 'a', 'net_value': 5, 'outgoing_value': 50}]}
        self.assertFalse(tx.ai_trade_candidate_accepted(data, candidate))


if __name__ == '__main__':
    unittest.main()
