"""Sequence-level variation, matchup direction and unchanged scoring outcomes."""
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from nba_gm_data.sim import load_sim_context, sim_game_with_context, game_team_features
from nba_gm_data.schema import to_plain
from audit_basketball_accounting import game_errors


class BoxVariationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.canonical = json.loads((root / 'data/canonical/universe_2026_27_offseason.json').read_text())
        cls.context = load_sim_context(root, cls.canonical)
        cls.games = [str(g['externalGameId']) for g in cls.context['schedule'] if g.get('phase') == 'regular'][:8]

    def test_sequence_variance_grows_without_changing_scores_minutes_or_makes(self):
        old, new = [], []
        for seed in range(120):
            gid = self.games[seed % len(self.games)]
            with patch('nba_gm_data.box_variation.vary_box_score'):
                before = to_plain(sim_game_with_context(self.context, gid, mode='sandbox-sim', seed=seed))
            after = to_plain(sim_game_with_context(self.context, gid, mode='sandbox-sim', seed=seed))
            self.assertFalse(game_errors(after), (seed, game_errors(after)))
            for a, b in zip(before['player_lines'], after['player_lines']):
                for key in ('points', 'minutes', 'fgm', 'fg3m', 'ftm', 'fg3a', 'fta'):
                    self.assertEqual(a[key], b[key], (seed, key))
            old.extend(before['team_lines'])
            new.extend(after['team_lines'])
        report = {}
        for key in ('assists', 'rebounds', 'turnovers', 'steals', 'blocks'):
            a, b = [r[key] for r in old], [r[key] for r in new]
            report[key] = {'before_mean': statistics.mean(a), 'after_mean': statistics.mean(b),
                           'before_sd': statistics.pstdev(a), 'after_sd': statistics.pstdev(b)}
            self.assertGreater(statistics.pstdev(b), statistics.pstdev(a) * 1.25, report)
            self.assertLess(abs(statistics.mean(a) - statistics.mean(b)), 3, report)
        a = [r['fgm'] / r['fga'] for r in old]
        b = [r['fgm'] / r['fga'] for r in new]
        self.assertGreater(statistics.pstdev(b), statistics.pstdev(a) * 1.1)
        # Team FG% spread close to the NBA's .059 per game (2025-26 xPoints game database, 2,460 team-games).
        self.assertTrue(.050 < statistics.pstdev(b) < .068, statistics.pstdev(b))
        # The pre-variation split ignores possessions (its attempts imply ~6 more possessions than were played), so
        # its FG% is not a reference (2026-11-17). Instead the varied box must stay consistent with the game's real
        # possessions: attempts + 0.44 FTA - offensive rebounds + turnovers close to the engine's count.
        def gap(r):
            return r['fga'] + .44 * r['fta'] - r['offensive_rebounds'] + r['turnovers'] - r['possessions']
        # Misses close 70% of the gap (box_variation.MISS_FILL); team rebounds credited to no player add ~1.
        self.assertLess(abs(statistics.mean(gap(r) for r in new)), abs(statistics.mean(gap(r) for r in old)) * .65)

    def test_repeat_seed_repeats_the_entire_box(self):
        for seed in (17, 29, 913):
            a = to_plain(sim_game_with_context(self.context, self.games[0], mode='sandbox-sim', seed=seed))
            b = to_plain(sim_game_with_context(self.context, self.games[0], mode='sandbox-sim', seed=seed))
            self.assertEqual(a, b)

    def test_pressure_increases_turnovers_and_rim_defense_increases_two_point_misses(self):
        from nba_gm_data.box_variation import vary_box_score
        sample = to_plain(sim_game_with_context(self.context, self.games[0], mode='sandbox-sim', seed=17))
        base_groups = [[p for p in sample['player_lines'] if p['team_id'] == t['team_id']] for t in sample['team_lines']]
        result = {}
        for pressure, rim in ((35, 35), (90, 35), (35, 90)):
            totals = []
            for seed in range(250):
                groups, teams = deepcopy(base_groups), deepcopy(sample['team_lines'])
                for team in teams:
                    team['possessions'] = 120
                features = [{'passing': 65, 'offensive_rebounding': 55, 'defense_rim': 60, 'defensive_events': 60},
                            {'passing': 65, 'offensive_rebounding': 55, 'defense_rim': rim, 'defensive_events': pressure}]
                vary_box_score(self.canonical, groups, teams, features, seed)
                totals.append((teams[0]['turnovers'], teams[0]['fga'], sum(p['assists'] for p in groups[0])))
            result[pressure, rim] = [statistics.mean(row[i] for row in totals) for i in range(3)]
        self.assertGreater(result[90, 35][0], result[35, 35][0] + 2, result)
        self.assertGreater(result[35, 90][1], result[35, 35][1] + 1, result)
        self.assertLess(result[90, 35][2], result[35, 35][2] - 1, result)


if __name__ == '__main__':
    unittest.main()
