from copy import deepcopy
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from nba_gm_data.box_score import (COUNT_FIELDS, missed_shots, opportunity_errors,
                                   reconcile_box_score, reduced_counts)


def fixture(seed=1):
    rng = random.Random(seed)
    players, teams = [], []
    for tid in ('home', 'away'):
        rows = []
        for i in range(8):
            two = rng.randrange(8)
            three = rng.randrange(4)
            ft = rng.randrange(6)
            rows.append({'player_id': f'{tid}-{i}', 'team_id': tid, 'minutes': 30,
                         'points': two*2+three*3+ft, 'fgm': two+three,
                         'fga': two+three+rng.randrange(8), 'fg3m': three,
                         'fg3a': three, 'ftm': ft, 'fta': ft+rng.randrange(3),
                         'rebounds': rng.randrange(20), 'assists': rng.randrange(20),
                         'turnovers': rng.randrange(4), 'steals': rng.randrange(5),
                         'blocks': rng.randrange(5), 'rim_attempts': 99})
        team = {k: sum(p[k] for p in rows) for k in COUNT_FIELDS}
        team.update(team_id=tid, offensive_rebounds=12, defensive_rebounds=team['rebounds']-12)
        players.extend(rows)
        teams.append(team)
    return players, teams


class BoxScoreReconciliationTests(unittest.TestCase):
    def test_assists_cannot_exceed_baskets_or_assist_own_baskets(self):
        players, teams = fixture()
        for row in players:
            row.update(assists=50)
        reconcile_box_score(players, teams)
        self.assertFalse(opportunity_errors(players, teams))
        for team in teams:
            self.assertLessEqual(team['assists'], team['fgm'])
            for row in [p for p in players if p['team_id'] == team['team_id']]:
                self.assertLessEqual(row['assists'], team['fgm']-row['fgm'])

    def test_zero_opponent_events_cannot_generate_steals_blocks_or_rebounds(self):
        players, teams = fixture()
        for row in players:
            row.update(fga=row['fgm'], fta=row['ftm'], turnovers=0)
        reconcile_box_score(players, teams)
        self.assertFalse(opportunity_errors(players, teams))
        for team in teams:
            self.assertEqual(team['steals'], 0)
            self.assertEqual(team['blocks'], 0)
            self.assertEqual(team['rebounds'], 0)

    def test_properties_and_scoring_minutes_preserved_across_seeds(self):
        for seed in range(200):
            players, teams = fixture(seed)
            protected = [{k: p[k] for k in ('points', 'minutes', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta')}
                         for p in players]
            original = deepcopy(players)
            reconcile_box_score(players, teams)
            self.assertFalse(opportunity_errors(players, teams), seed)
            self.assertEqual(protected, [{k: p[k] for k in protected[i]} for i, p in enumerate(players)])
            for before, after in zip(original, players, strict=True):
                for key in ('rebounds', 'assists', 'steals', 'blocks'):
                    self.assertLessEqual(after[key], before[key])
            for team in teams:
                for key in COUNT_FIELDS:
                    self.assertEqual(team[key], sum(p[key] for p in players if p['team_id'] == team['team_id']))
            once = deepcopy((players, teams))
            reconcile_box_score(players, teams)
            self.assertEqual(once, (players, teams))

    def test_consistent_counts_stay_unchanged_and_pair_order_is_irrelevant(self):
        players, teams = fixture()
        reconcile_box_score(players, teams)
        before = deepcopy((players, teams))
        reconcile_box_score(players, list(reversed(teams)))
        self.assertEqual(before, (players, teams))

    def test_largest_remainder_reduces_only_and_preserves_target(self):
        self.assertEqual(reduced_counts([4, 4, 4], 5, ['a', 'b', 'c']), [2, 2, 1])
        self.assertEqual(reduced_counts([0, 0], 5, ['a', 'b']), [0, 0])
        self.assertEqual(reduced_counts([1, 2], 99, ['a', 'b']), [1, 2])

    def test_ft_misses_are_an_upper_bound_not_forced_rebounds(self):
        players, teams = fixture()
        reconcile_box_score(players, teams)
        for team in teams:
            opp = next(t for t in teams if t['team_id'] != team['team_id'])
            self.assertLessEqual(team['offensive_rebounds']+opp['defensive_rebounds'], missed_shots(team))

    def test_dnp_players_receive_no_secondary_events(self):
        players, teams = fixture()
        players[0]['minutes'] = 0
        reconcile_box_score(players, teams)
        for key in ('rebounds', 'assists', 'turnovers', 'steals', 'blocks', 'rim_attempts'):
            self.assertEqual(players[0][key], 0)
        self.assertFalse(opportunity_errors(players, teams))


class LiveBoxScoreIntegrationTests(unittest.TestCase):
    def test_real_sim_hook_preserves_scores_shooting_and_minutes_and_repeats(self):
        from nba_gm_data.sim import load_sim_context, sim_game_with_context
        from nba_gm_data.schema import to_plain
        from audit_basketball_accounting import game_errors

        root = Path(__file__).resolve().parents[1]
        canonical = json.loads((root/'data/canonical/universe_2026_27_offseason.json').read_text())
        context = load_sim_context(root, canonical)
        games = [g for g in context['schedule'] if g.get('phase') == 'regular'][:5]
        self.assertEqual(len(games), 5)
        for seed in (17, 29):
            for game in games:
                gid = str(game['externalGameId'])
                with patch('nba_gm_data.box_score.reconcile_box_score'):
                    before = to_plain(sim_game_with_context(context, gid, mode='sandbox-sim', seed=seed))
                after = to_plain(sim_game_with_context(context, gid, mode='sandbox-sim', seed=seed))
                repeated = to_plain(sim_game_with_context(context, gid, mode='sandbox-sim', seed=seed))
                self.assertEqual(after, repeated)
                self.assertEqual((before['home_score'], before['away_score']), (after['home_score'], after['away_score']))
                for a, b in zip(before['player_lines'], after['player_lines'], strict=True):
                    for key in ('points', 'minutes', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta', 'personal_fouls'):
                        self.assertEqual(a[key], b[key])
                self.assertFalse(game_errors(after))


if __name__ == '__main__':
    unittest.main()
