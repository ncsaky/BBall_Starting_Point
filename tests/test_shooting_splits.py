"""SHOOTING-SPLITS: players shoot their own percentages; box-score tails look like real ones.

Covers the team-level settling of odd point totals (no handed-out free throws), the rate-based steal/block re-share,
the binomial turnover draw, the scorecard's new targets, and a league-level check on replayed games.
"""
import random
import statistics
import unittest
from pathlib import Path

from nba_gm_data import box_variation, offense
from nba_gm_data.calibration_targets import texture_band, texture_from_games
from nba_gm_data.sim import reshare_by_rates

ROOT = Path(__file__).resolve().parents[1]


def consistent(line):
    return line['points'] == 2 * (line['fgm'] - line['fg3m']) + 3 * line['fg3m'] + line['ftm']


class SettleOddLinesTests(unittest.TestCase):
    FEAT = {'rim_pressure': 62, 'shot_creation': 60, 'ft_pct': .78, 'three_per36': 6.0, 'three_pct': .36,
            'two_pct': .53, 'fta_per_point': .22}

    def team(self, seed):
        rng = random.Random(seed)
        lines, feats = [], []
        for _ in range(10):
            points = rng.randint(0, 30)
            feat = dict(self.FEAT, ft_pct=rng.uniform(.6, .92))
            line = {'points': points, **offense.shooting_line(points, feat, 24.0, rng, points + .5, defer_parity=True)}
            lines.append(line)
            feats.append(feat)
        return lines, feats

    def test_lines_add_up_and_the_team_keeps_its_points(self):
        for seed in range(300):
            lines, feats = self.team(seed)
            total = sum(line['points'] for line in lines)
            offense.settle_odd_lines(lines, feats, f'test:{seed}')
            self.assertEqual(sum(line['points'] for line in lines), total)
            for line in lines:
                self.assertTrue(consistent(line), line)
                self.assertNotIn('_odd', line)
                self.assertNotIn('_noise', line)
                self.assertGreaterEqual(line['fgm'] - line['fg3m'], 0)
                self.assertLessEqual(line['ftm'], line['fta'])
                self.assertLessEqual(line['fgm'], line['fga'])

    def test_free_throws_keep_their_percentage(self):
        """Settling never hands out made free throws: league FT% stays at the shooters' own rate."""
        made = attempts = expected = 0.0
        for seed in range(3000):
            lines, feats = self.team(seed)
            offense.settle_odd_lines(lines, feats, f'ft:{seed}')
            for line, feat in zip(lines, feats):
                made += line['ftm']
                attempts += line['fta']
                expected += line['fta'] * feat['ft_pct']
        self.assertAlmostEqual(made / attempts, expected / attempts, delta=.006)

    def test_settling_is_deterministic(self):
        a, fa = self.team(5)
        b, fb = self.team(5)
        offense.settle_odd_lines(a, fa, 'same')
        offense.settle_odd_lines(b, fb, 'same')
        self.assertEqual(a, b)


class ReshareTests(unittest.TestCase):
    def test_total_is_hit_and_shares_follow_rates(self):
        rates = [2.0, 1.2, .8, 1.0, .8, .6]
        rng = random.Random(4)
        totals = [0] * len(rates)
        big = 0
        for game in range(4000):
            lines = [{'player_id': i, 'minutes': 30, 'points': game % 17,
                      'steals': box_variation.poisson(rng, r * .6)} for i, r in enumerate(rates)]
            target = max(0, round(sum(rates) + rng.gauss(0, 3)))
            reshare_by_rates(lines, 'steals', target, rates)
            self.assertEqual(sum(line['steals'] for line in lines), target)
            self.assertTrue(all(line['steals'] >= 0 for line in lines))
            for i, line in enumerate(lines):
                totals[i] += line['steals']
            big += sum(line['steals'] >= 6 for line in lines)
        share = totals[0] / sum(totals)
        self.assertAlmostEqual(share, rates[0] / sum(rates), delta=.02)
        # Scaling the draws used to turn quiet-night draws into six-steal games; adding by rate keeps them rare.
        self.assertLess(big / 4000, .03)


class TurnoverDrawTests(unittest.TestCase):
    def test_binomial_count_mean_and_spread(self):
        rng = random.Random(9)
        for mean in (.5, 3.0, 5.5):
            draws = [box_variation.binomial_count(rng.random(), mean, .19) for _ in range(20000)]
            self.assertAlmostEqual(statistics.fmean(draws), mean, delta=.04 * mean + .02)
            self.assertLess(statistics.pvariance(draws), mean)
        self.assertEqual(box_variation.binomial_count(.7, 0.0, .19), 0)


class TextureTargetTests(unittest.TestCase):
    def test_texture_counts_and_bands(self):
        games = [[{'team_id': 'A', 'minutes': 30, 'points': 41, 'rebounds': 3, 'steals': 0, 'turnovers': 1},
                  {'team_id': 'A', 'minutes': 0, 'points': 0, 'rebounds': 0, 'steals': 0, 'turnovers': 0},
                  {'team_id': 'B', 'minutes': 20, 'points': 4, 'rebounds': 21, 'steals': 6, 'turnovers': 10}]] * 4
        t = texture_from_games(games)
        self.assertEqual(t['games'], 4)
        self.assertEqual(t['players_used'], 1.0)
        self.assertEqual(t['counts']['pts40_per_game'], 4)
        self.assertEqual(t['tov10_per_game'], 1.0)
        low, high = texture_band('pts40_per_game', {'mean': .108, 'games': 1231}, 1230)
        self.assertLess(low, .108)
        self.assertGreater(high, .108)
        self.assertEqual(texture_band('players_used', {'mean': 10.79}, 100), (10.29, 11.29))


class LeagueShootingTests(unittest.TestCase):
    """Replayed games (real minutes): league 3P% and FT% follow the players' own percentages."""

    def test_league_percentages_follow_ratings(self):
        from nba_gm_data.schema import to_plain
        from nba_gm_data.sim import build_sim_indices, load_sim_context, player_feature_vector, sim_game_with_context
        context = load_sim_context(ROOT)
        context['indices'] = build_sim_indices(context)
        canonical = context['canonical']
        players = {p['id']: p for p in canonical['players']}
        games = sorted([g for g in context['schedule'] if str(g.get('phase', 'regular')) in ('regular', 'None', '')],
                       key=lambda g: str(g.get('externalGameId')))[::8][:150]
        t = {k: 0.0 for k in ('fg3a', 'fg3m', 'fta', 'ftm', 'own3', 'ownft')}
        features = {}
        for g in games:
            result = to_plain(sim_game_with_context(context, str(g['externalGameId']), mode='replay-real-minutes', seed=1))
            for line in result['player_lines']:
                player = players.get(line['player_id'])
                if not player or not line.get('minutes'):
                    continue
                if line['player_id'] not in features:
                    features[line['player_id']] = player_feature_vector(canonical, player).features
                f = features[line['player_id']]
                for k in ('fg3a', 'fg3m', 'fta', 'ftm'):
                    t[k] += line[k]
                t['own3'] += line['fg3a'] * f['three_pct']
                t['ownft'] += line['fta'] * f['ft_pct']
        self.assertAlmostEqual(t['fg3m'] / t['fg3a'], t['own3'] / t['fg3a'], delta=.012)
        self.assertAlmostEqual(t['ftm'] / t['fta'], t['ownft'] / t['fta'], delta=.012)


if __name__ == '__main__':
    unittest.main()
