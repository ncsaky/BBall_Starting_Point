import unittest

from research_contract_guarantees import evidence


def page(total):
    rows = ''.join(f'<tr><td data-stat="player" data-append-csv="p{i}">Player {i}</td>'
                   '<td data-stat="team_id">TOR</td><td data-stat="y1" csk="100">$100</td>'
                   '<td data-stat="y2" csk="110">$110</td>'
                   '<td data-stat="y3" class="right salary-pl" csk="120">$120</td>'
                   f'<td data-stat="remain_gtd" csk="{total}">${total}</td></tr>' for i in range(100))
    return ('<table id="player-contracts"><thead><tr><th data-stat="y1">2026-27</th>'
            '<th data-stat="y2">2027-28</th><th data-stat="y3">2028-29</th></tr></thead><tbody>'+rows+'</tbody></table>')


class GuaranteeResearchTests(unittest.TestCase):
    def test_matching_total_does_not_claim_an_option_is_guaranteed(self):
        row = evidence(page(210))[0]
        self.assertEqual([s['guaranteed_salary'] for s in row['seasons']], [100, 110, None])
        self.assertEqual(row['seasons'][2]['option_type'], 'player_option')

    def test_partial_total_is_not_arbitrarily_allocated_to_years(self):
        row = evidence(page(150))[0]
        self.assertEqual(row['remaining_guaranteed'], 150)
        self.assertTrue(all(s['guaranteed_salary'] is None for s in row['seasons']))

    def test_missing_total_is_unknown_not_non_guaranteed(self):
        row = evidence(page(''))[0]
        self.assertIsNone(row['remaining_guaranteed'])
        self.assertTrue(all(s['guaranteed_salary'] is None for s in row['seasons']))

    def test_incomplete_or_blocked_response_fails_closed(self):
        with self.assertRaises(ValueError):
            evidence('<html>Access denied</html>')


if __name__ == '__main__':
    unittest.main()
