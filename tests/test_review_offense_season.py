import unittest

from review_offense_season import (distributions, parse_espn_game, player_trace,
                                   retention_difference, summer_signing_cuts, with_percentages)


class CompletedOffenseReviewTests(unittest.TestCase):
    def test_team_differences_are_not_mistaken_for_nightly_variation(self):
        rows = [{'team_id': t, 'rebounds': v} for t, v in (('a', 30), ('b', 50)) for _ in range(20)]
        result = distributions(rows, 'team_id')['rebounds']
        self.assertEqual(result['all_games']['sd'], 10)
        self.assertEqual(result['within_entity_sd']['mean'], 0)

    def test_zero_attempt_percentages_are_missing_not_zero(self):
        row = with_percentages({'fgm': 0, 'fga': 0, 'fg3m': 1, 'fg3a': 4})
        self.assertIsNone(row['fg_pct'])
        self.assertIsNone(row['ft_pct'])
        self.assertEqual(row['three_pct'], 25)

    def test_retention_net_count_does_not_hide_churn(self):
        self.assertEqual(retention_difference(['a', 'b'], ['b', 'c']), {'v8_only': ['a'], 'v9_only': ['c']})

    def test_trace_excludes_second_season_and_merges_offer_updates(self):
        p = {'id': 'p', 'team_id': None, 'rostered': False}
        snapshots = [{'date': '2027-10-01', 'players': [p]}]
        tx = [{'id': 't', 'date': '2027-07-04', 'assets': {'player_id': 'p'}},
              {'id': 'late', 'date': '2028-07-04', 'assets': {'player_id': 'p'}}]
        markets = [{'offers': [{'id': 'o', 'player_id': 'p', 'status': 'active'}]},
                   {'offers': [{'id': 'o', 'player_id': 'p', 'status': 'accepted'}]}]
        trace = player_trace('p', snapshots, tx, markets, '2027-10-01')
        self.assertEqual([t['id'] for t in trace['transactions']], ['t'])
        self.assertEqual(trace['offers'], [{'id': 'o', 'player_id': 'p', 'status': 'accepted'}])

    def test_named_espn_fg_field_and_dnp(self):
        raw = {'boxscore': {'players': []}}
        for tid in ('1', '2'):
            raw['boxscore']['players'].append({'team': {'id': tid}, 'statistics': [{
                'labels': ['MIN', 'PTS', 'FG', '3PT', 'FT', 'REB', 'AST', 'TO', 'STL', 'BLK'],
                'athletes': [{'athlete': {'id': tid, 'displayName': tid},
                              'stats': ['30', '12', '4-9', '2-5', '2-2', '3', '2', '1', '0', '0']},
                             {'didNotPlay': True}]}]})
        rows = parse_espn_game(raw, '2026-01-01', 'game')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['fgm'], 4)
        self.assertEqual(rows[0]['fga'], 9)
        raw['boxscore']['players'][0]['statistics'][0]['athletes'][0]['stats'][1] = '13'
        with self.assertRaises(ValueError):
            parse_espn_game(raw, '2026-01-01', 'game')

    def test_signing_cuts_exclude_second_season_and_preserve_team_context(self):
        def tx(identifier, date, kind, team):
            return {'id': identifier, 'date': date, 'transaction_type': kind,
                    'assets': {'player_id': 'p'}, 'teams': [team]}
        rows = [tx('sign', '2027-07-04', 'free_agent_signing', 'team_a'),
                tx('cut', '2027-10-01', 'roster_cut', 'team_a'),
                tx('later', '2028-07-01', 'free_agent_signing', 'team_b')]
        report = summer_signing_cuts(rows)
        self.assertEqual(report['summer_signings'], 1)
        self.assertEqual(report['signed_then_cut_october_1'], 1)
        self.assertTrue(report['cases'][0]['same_team'])


if __name__ == '__main__':
    unittest.main()
