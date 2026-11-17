import unittest
from unittest.mock import patch
from verify_trade_year import census


class TradeYearAuditTests(unittest.TestCase):
    def test_archived_transactions_are_counted_once_with_hot_tail(self):
        january = {'id': 'jan', 'date': '2027-01-04', 'transaction_type': 'trade', 'assets': {'from_assets': [{'kind': 'player'}]}}
        july = {'id': 'jul', 'date': '2027-07-02', 'transaction_type': 'trade', 'assets': {'from_assets': [{'kind': 'pick'}]}}
        saved = {'state': {'current_date': '2027-12-31'}, 'transaction_logs': [july]}
        with patch('verify_trade_year.load_history_records', return_value=[january, july]):
            result = census(saved, '/disposable.json')
        self.assertEqual(len(result['all_trades']), 2)
        self.assertEqual(result['monthly_player_trades'], {'2027-01': 1})
        self.assertEqual(result['monthly_pick_trades'], {'2027-07': 1})

    def test_offer_counts_survive_rollover_clearing_live_inbox(self):
        offer = {'proposal': {'id': 'offer'}, 'offer_context': {'created_date': '2027-02-05'}}
        previous = census({'state': {'current_date': '2027-07-15'}, 'user_trade_offers': [offer]})
        result = census({'state': {'current_date': '2027-10-01'}, 'user_trade_offers': []}, previous=previous)
        self.assertEqual(result['monthly_offers'], {'2027-02': 1})
        self.assertEqual(len(census({'state': {'current_date': '2027-10-01'}, 'user_trade_offers': [offer]}, previous=result)['all_offers']), 1)


if __name__ == '__main__':
    unittest.main()
