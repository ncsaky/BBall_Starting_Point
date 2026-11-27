"""TRADE-PRICE: stars need a star's return, and no pick is added to get rid of a core player."""
from types import SimpleNamespace as Row
import unittest

from nba_gm_data import trade_stars as ts, transactions as tx


def player(pid, team, age, court, price=None, *, upside=0, surplus=0, health=0, playoff=70):
    return ({'id': pid, 'name': pid, 'team_id': team, 'age': age, 'position': 'SF', 'minutes_projection': 30,
             'overall': court, 'potential': court + upside},
            {'player_id': pid, 'on_court_value': court, 'development_upside': upside,
             'player_value': court if price is None else price, 'playoff_value': playoff,
             'contract_surplus': surplus, 'health_risk': health})


def league(*rows, phase='rebuilding'):
    """Team a (the seller) and b hold the given players. Thirty players rated 72 elsewhere (and a crowd of reserves)
    put the league's thirty-best bar at 72."""
    rows = [*rows,
            *(player(f'elite{i}', 'c', 27, 72) for i in range(30)),
            *(player(f'crowd{i}', 'c', 27, 55) for i in range(40))]
    picks = [{'id': f'first{i}', 'round': 1, 'season': str(2029 + i), 'current_owner_team_id': 'b',
              'projected_pick_slot': 8, '_active_season': '2027-28'} for i in range(4)]
    picks += [{'id': 'second', 'round': 2, 'season': '2029', 'current_owner_team_id': 'a', '_active_season': '2027-28'},
              {'id': 'own_first', 'round': 1, 'season': '2031', 'current_owner_team_id': 'a', 'projected_pick_slot': 20,
               '_active_season': '2027-28'}]
    return {'players': [p for p, _ in rows], 'player_asset_valuations': [v for _, v in rows], 'draft_picks': picks,
            'team_strategic_states': [{'team_id': 'a', 'window_phase': phase, 'phase': 'rebuilding'}], 'team_plans': {}}


def ids(*names):
    return [{'kind': 'pick' if n.startswith(('first', 'second', 'own_first')) else 'player', 'id': n} for n in names]


class StarReturnTests(unittest.TestCase):
    def issue(self, data, sends, gets):
        return ts.return_issue(data, 'a', ids(*gets), ids(*sends))

    def test_a_star_needs_three_firsts(self):
        data = league(player('star', 'a', 27, 82), player('reserve', 'b', 28, 55))
        self.assertIn('star is a star', self.issue(data, ['star'], ['first0', 'reserve']))
        self.assertIsNotNone(self.issue(data, ['star'], ['first0', 'first1']))
        self.assertIsNone(self.issue(data, ['star'], ['first0', 'first1', 'first2']))

    def test_the_same_pick_or_a_pick_worth_nearly_nothing_does_not_count(self):
        data = league(player('star', 'a', 27, 82))
        self.assertIsNotNone(self.issue(data, ['star'], ['first0', 'first0', 'first1']))
        data['draft_picks'][2]['_protection_value_factor'] = .05
        self.assertIsNotNone(self.issue(data, ['star'], ['first0', 'first1', 'first2']))
        self.assertIsNone(self.issue(data, ['star'], ['first0', 'first1', 'first3']))

    def test_a_comparable_or_top_young_player_is_a_return(self):
        data = league(player('star', 'a', 27, 82, playoff=80), player('peer', 'b', 28, 79, playoff=75),
                      player('prospect', 'b', 21, 68, 75, upside=15))
        self.assertIsNone(self.issue(data, ['star'], ['peer']))
        self.assertIsNone(self.issue(data, ['star'], ['prospect']))

    def test_a_comparable_player_must_also_be_priced_near_the_star(self):
        data = league(player('star', 'a', 22, 74, 90), player('reserve', 'b', 30, 72, 71),
                      player('peer', 'b', 30, 72, 72), player('prospect', 'b', 21, 66, 60, upside=15))
        self.assertIn('is a star', self.issue(data, ['star'], ['reserve', 'first0']))
        self.assertIsNone(self.issue(data, ['star'], ['peer']))
        # A top young player keeps his own, lower, price bar; three firsts still do it.
        self.assertIsNone(self.issue(data, ['star'], ['prospect']))
        self.assertIsNone(self.issue(data, ['star'], ['reserve', 'first0', 'first1', 'first2']))

    def test_each_departing_star_needs_a_return_of_his_own(self):
        data = league(player('star', 'a', 27, 82), player('other_star', 'a', 27, 81), player('peer', 'b', 28, 80),
                      player('other', 'b', 28, 79))
        self.assertIsNotNone(self.issue(data, ['star', 'other_star'], ['peer']))
        self.assertIsNone(self.issue(data, ['star', 'other_star'], ['peer', 'other']))
        self.assertIsNone(self.issue(data, ['star', 'other_star'], ['peer', 'first0', 'first1', 'first2']))

    def test_a_young_player_priced_as_a_cornerstone_is_a_star_before_he_plays_like_one(self):
        data = league(player('young', 'a', 21, 64, 90, upside=20), player('plain', 'a', 21, 64, 45, upside=4))
        self.assertTrue(ts.is_star(data, data['players'][0]))
        self.assertFalse(ts.is_star(data, data['players'][1]))
        self.assertIsNotNone(self.issue(data, ['young'], ['first0', 'first1']))

    def test_old_costly_or_fragile_stars_and_ordinary_starters_are_not_covered(self):
        for row in (player('p', 'a', 34, 82), player('p', 'a', 27, 82, surplus=-20),
                    player('p', 'a', 27, 82, health=31), player('p', 'a', 27, 69)):
            self.assertIsNone(self.issue(league(row), ['p'], ['first0']))

    def test_the_bar_follows_new_valuations(self):
        data = league(player('p', 'a', 27, 74))
        self.assertTrue(ts.is_star(data, data['players'][0]))
        data['player_asset_valuations'] = [dict(v, on_court_value=75) if v['player_id'].startswith('crowd') else v
                                           for v in data['player_asset_valuations']]
        data.pop('_player_asset_values_by_id', None)
        self.assertFalse(ts.is_star(data, data['players'][0]))

    def test_a_thin_league_does_not_make_reserves_stars(self):
        rows = [player('low', 'a', 27, 55), *(player(f'filler{i}', 'c', 27, 40) for i in range(35))]
        data = {'players': [p for p, _ in rows], 'player_asset_valuations': [v for _, v in rows]}
        self.assertFalse(ts.is_star(data, data['players'][0]))

    def test_a_league_without_a_top_thirty_has_no_stars_by_rank(self):
        row = player('p', 'a', 27, 90)
        self.assertFalse(ts.is_star({'players': [row[0]], 'player_asset_valuations': [row[1]]}, row[0]))


class PayingToMoveTests(unittest.TestCase):
    def data(self, court=68, age=31, **extra):
        return league(player('guard', 'a', age, court, **extra), player('two', 'a', 27, 67), player('three', 'a', 27, 66),
                      player('fourth', 'a', 27, 65), player('bench', 'b', 27, 61), player('peer', 'b', 28, 66),
                      phase='exiting')

    def issue(self, data, sends, gets):
        return ts.return_issue(data, 'a', ids(*gets), ids(*sends))

    def test_no_pick_is_added_to_send_a_core_player_away_for_a_bench_player(self):
        self.assertIn('will not add a pick', self.issue(self.data(), ['guard', 'second'], ['bench']))
        self.assertIsNotNone(self.issue(self.data(), ['guard', 'own_first'], []))

    def test_without_a_pick_or_with_a_real_return_the_rule_stays_out(self):
        self.assertIsNone(self.issue(self.data(), ['guard'], ['bench']))
        self.assertIsNone(self.issue(self.data(), ['guard', 'second'], ['peer']))
        # The star price bar does not apply here: a much cheaper comparable player still counts.
        cheap = self.data()
        next(v for v in cheap['player_asset_valuations'] if v['player_id'] == 'peer')['player_value'] = 20
        self.assertIsNone(self.issue(cheap, ['guard', 'second'], ['peer']))
        self.assertIsNone(self.issue(self.data(), ['guard', 'second'], ['bench', 'first0']))

    def test_other_players_may_be_moved_with_a_pick(self):
        self.assertIsNone(self.issue(self.data(), ['fourth', 'second'], ['bench']))
        for data in (self.data(age=34), self.data(surplus=-20), self.data(health=31)):
            self.assertIsNone(self.issue(data, ['guard', 'second'], ['bench']))
        low = league(player('guard', 'a', 31, 61), player('bench', 'b', 27, 55), phase='exiting')
        self.assertIsNone(self.issue(low, ['guard', 'second'], ['bench']))


class AcceptanceTests(unittest.TestCase):
    def test_the_refusal_reaches_the_computer_team_and_not_the_user(self):
        data = league(player('star', 'a', 27, 74), player('reserve', 'b', 28, 55))
        incoming, outgoing = ids('first0'), ids('star')
        self.assertIn('is a star', tx.premium_return_issue(data, 'a', incoming, outgoing))
        data['_human_team_ids'] = ['a']
        self.assertIsNone(tx.premium_return_issue(data, 'a', incoming, outgoing))

    def test_a_large_value_surplus_cannot_override_it(self):
        from unittest.mock import patch
        data = league(player('star', 'a', 27, 74))
        incoming, outgoing = ids('first0'), ids('star')
        with patch.object(tx, 'package_value_for_team', side_effect=[200, 100]), \
             patch.object(tx, 'strategic_fit_adjustment', return_value=0), \
             patch.object(tx, 'personality_trade_adjustment', return_value={'total': 0}), \
             patch.object(tx, 'contextual_acceptance_threshold', return_value=1), \
             patch.object(tx, 'evaluation_notes', return_value=''):
            evaluation = tx.evaluate_trade_for_team(data, Row(id='trade'), 'a', incoming, outgoing,
                                                    {'status': 'legal', 'issues': []}, 17, {})
        self.assertFalse(evaluation.accepted)
        self.assertEqual(evaluation.decision, 'reject_premium_return')
        self.assertTrue(any('is a star' in reason for reason in evaluation.decision_reasons))


if __name__ == '__main__':
    unittest.main()
