from bisect import bisect_right
from collections import Counter
from copy import deepcopy
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data.plus_minus import scoring_snapshot, track_plus_minus


def fixture(minutes=None):
    minutes = minutes or [38, 36, 34, 32, 30, 24, 20, 16, 10]
    rows, teams = [], []
    for side, tid in enumerate(('away', 'home')):
        group = []
        for i, played in enumerate(minutes):
            two, three, ft = (i % 4+2, i % 3, (i+side) % 4) if played else (0, 0, 0)
            group.append({'player_id': f'{tid}-{i}', 'team_id': tid, 'minutes': played,
                          'fgm': two+three, 'fg3m': three, 'ftm': ft,
                          'points': 2*two+3*three+ft})
        rows.extend(group)
        teams.append({'team_id': tid, 'points': sum(r['points'] for r in group), 'overtime_periods': 0})
    return rows, teams


class PlusMinusTests(unittest.TestCase):
    def assert_tracking(self, rows, teams, trace):
        self.assertEqual(trace['status'], 'tracked', trace)
        ids, tids = trace['player_ids'], trace['team_ids']
        by_id = {r['player_id']: r for r in rows}
        minutes, scored, allowed, events = Counter(), Counter(), Counter(), Counter()
        previous = 0
        totals = [0, 0]
        for start, end, first, second, p0, p1 in trace['stints']:
            self.assertEqual(start, previous)
            self.assertGreater(end, start)
            previous = end
            self.assertEqual(len(set(first)), 5)
            self.assertEqual(len(set(second)), 5)
            self.assertFalse(set(first) & set(second))
            totals[0] += p0
            totals[1] += p1
            for side, lineup in enumerate((first, second)):
                for index in lineup:
                    pid = ids[index]
                    self.assertEqual(by_id[pid]['team_id'], tids[side])
                    minutes[pid] += end-start
                    scored[pid] += (p0, p1)[side]
                    allowed[pid] += (p1, p0)[side]
        self.assertEqual(previous, trace['duration_ticks'])
        self.assertEqual(totals, [next(t['points'] for t in teams if t['team_id'] == tid) for tid in tids])
        ends = [s[1] for s in trace['stints']]
        for tick, pid, points, side in trace.get('scoring_events', []):
            stint = trace['stints'][bisect_right(ends, tick)]
            self.assertIn(ids.index(pid), stint[2+side])
            self.assertIn(points, (1, 2, 3))
            events[pid] += points
        for row in rows:
            pid = row['player_id']
            self.assertAlmostEqual(minutes[pid]/100, row['minutes'], delta=.011)
            self.assertEqual(row['plus_minus'], scored[pid]-allowed[pid])
            self.assertEqual(row['on_court_points_for'], scored[pid])
            self.assertEqual(row['on_court_points_against'], allowed[pid])
            if 'scoring_events' in trace:
                self.assertEqual(events[pid], row['points'])
            if not row['minutes']:
                self.assertEqual(row['plus_minus'], 0)
        for team in teams:
            other = next(t for t in teams if t['team_id'] != team['team_id'])
            self.assertEqual(sum(r['plus_minus'] for r in rows if r['team_id'] == team['team_id']),
                             5*(team['points']-other['points']))

    def test_scoring_lineups_minutes_and_team_identities_across_seeds(self):
        for seed in range(100):
            rows, teams = fixture()
            before = deepcopy(rows)
            trace = track_plus_minus(rows, teams, str(seed), include_events=True)
            self.assert_tracking(rows, teams, trace)
            for old, new in zip(before, rows):
                self.assertEqual(old, {key: new[key] for key in old})
        self.assertGreater(len({r['plus_minus'] for r in rows}), 2)

    def test_only_five_players_all_have_the_final_margin_and_dnp_stays_zero(self):
        rows, teams = fixture([48, 48, 48, 48, 48, 0])
        trace = track_plus_minus(rows, teams, 'five', include_events=True)
        self.assert_tracking(rows, teams, trace)
        for row in rows:
            margin = teams[1]['points']-teams[0]['points']
            self.assertEqual(row['plus_minus'], (margin if row['team_id'] == 'home' else -margin) if row['minutes'] else 0)

    def test_repeated_calls_and_input_order_do_not_reroll_or_consume_global_rng(self):
        rows, teams = fixture()
        rng_state = random.getstate()
        first = track_plus_minus(rows, teams, 'repeat')
        before = deepcopy(rows)
        self.assertEqual(first, track_plus_minus(rows, teams, 'repeat'))
        self.assertEqual(rows, before)
        other = deepcopy(list(reversed(rows)))
        self.assertEqual(first, track_plus_minus(other, list(reversed(teams)), 'repeat'))
        self.assertEqual({r['player_id']: r['plus_minus'] for r in rows},
                         {r['player_id']: r['plus_minus'] for r in other})
        self.assertEqual(random.getstate(), rng_state)

    def test_rounded_minutes_and_many_rotation_shapes(self):
        rng = random.Random(29)
        for count in range(5, 16):
            ticks = [24000//count]*count
            ticks[-1] += 24000-sum(ticks)
            for _ in range(80):
                a, b = rng.sample(range(count), 2)
                moved = min(rng.randrange(300), ticks[a]-1, 4800-ticks[b])
                ticks[a] -= moved
                ticks[b] += moved
            rows, teams = fixture([n/100 for n in ticks])
            rows[0]['minutes'] -= .01
            trace = track_plus_minus(rows, teams, f'rotation-{count}', include_events=True)
            self.assert_tracking(rows, teams, trace)

    def test_invalid_boxes_are_unavailable_instead_of_fabricated_zero(self):
        for mode in ('short_roster', 'missing_shots', 'bad_minutes', 'dnp_score', 'bad_points'):
            rows, teams = fixture()
            if mode == 'short_roster':
                rows = rows[:4]+rows[9:13]
            elif mode == 'missing_shots':
                rows[0].pop('fgm')
            elif mode == 'bad_minutes':
                rows[0]['minutes'] = 90
            elif mode == 'dnp_score':
                rows[0]['minutes'] = 0
            else:
                rows[0]['points'] += 1
            result = track_plus_minus(rows, teams, mode)
            self.assertEqual(result['status'], 'unavailable')
            self.assertTrue(all(r['plus_minus'] is None for r in rows))

    def test_overtime_scores_and_minutes_belong_to_the_correct_period(self):
        rows, teams = fixture()
        # Both teams finish regulation tied, then tie the first OT.
        for row in rows:
            row['ftm'] = 0
            row['points'] = 2*row['fgm']+row['fg3m']
        frames = [scoring_snapshot(rows)]
        for period in range(2):
            from nba_gm_data.sim import add_overtime_minutes
            for tid in ('away', 'home'):
                add_overtime_minutes([r for r in rows if r['team_id'] == tid])
            for side, tid in enumerate(('away', 'home')):
                scorer = next(r for r in rows if r['team_id'] == tid)
                twos = 5 if period == 0 else 4+2*side
                scorer['fgm'] += twos
                scorer['points'] += 2*twos
            frames.append(scoring_snapshot(rows))
        for team in teams:
            team.update(points=sum(r['points'] for r in rows if r['team_id'] == team['team_id']), overtime_periods=2)
        trace = track_plus_minus(rows, teams, 'overtime', snapshots=frames, include_events=True)
        self.assert_tracking(rows, teams, trace)
        for boundary in (4800, 5300):
            totals = [sum(s[4+i] for s in trace['stints'] if s[1] <= boundary) for i in (0, 1)]
            self.assertEqual(totals[0], totals[1])
        self.assertEqual(trace['duration_ticks'], 5800)

    def test_actual_overtime_resolver_collects_a_tied_regulation_frame(self):
        from nba_gm_data.sim import resolve_overtime_if_tied
        rows, teams = fixture()
        for row in rows:
            row['ftm'] = 0
            row['points'] = 2*row['fgm']+row['fg3m']
        for team in teams:
            team.update(points=sum(r['points'] for r in rows if r['team_id'] == team['team_id']), possessions=100)
        frames = []
        periods = resolve_overtime_if_tied([r for r in rows if r['team_id'] == 'home'],
            [r for r in rows if r['team_id'] == 'away'], teams[1], teams[0], random.Random(17), tracking_periods=frames)
        self.assertEqual(periods, 1)
        trace = track_plus_minus(rows, teams, 'actual-overtime', snapshots=frames, include_events=True)
        self.assert_tracking(rows, teams, trace)
        self.assertEqual(sum(s[4] for s in trace['stints'] if s[1] <= 4800),
                         sum(s[5] for s in trace['stints'] if s[1] <= 4800))


class PlusMinusIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from nba_gm_data.sim import load_sim_context
        cls.root = Path(__file__).resolve().parents[1]
        cls.context = load_sim_context(cls.root)

    def test_real_games_preserve_every_preexisting_stat_and_are_reproducible(self):
        from nba_gm_data.sim import sim_game_with_context
        from nba_gm_data.schema import to_plain
        games = [g for g in self.context['schedule'] if g.get('phase') == 'regular'][:8]
        cases = []
        for mode in ('sandbox-sim', 'replay-real-minutes'):
            for seed in (17, 29):
                for game in games:
                    gid = str(game['externalGameId'])
                    with patch('nba_gm_data.plus_minus.track_plus_minus', return_value=None):
                        before = to_plain(sim_game_with_context(self.context, gid, mode=mode, seed=seed))
                    after = to_plain(sim_game_with_context(self.context, gid, mode=mode, seed=seed))
                    self.assertEqual(after, to_plain(sim_game_with_context(self.context, gid, mode=mode, seed=seed)))
                    for old, new in zip(before['player_lines'], after['player_lines']):
                        self.assertEqual(old, {key: new[key] for key in old})
                    self.assertEqual(before['team_lines'], after['team_lines'])
                    self.assertEqual((before['home_score'], before['away_score']), (after['home_score'], after['away_score']))
                    self.assertEqual(after['plus_minus_tracking']['status'], 'tracked', (gid, seed, mode, after['plus_minus_tracking']))
                    cases.append(after)
        self.assertEqual(len(cases), 32)

    def test_saved_box_score_retains_tracking_and_legacy_games_stay_missing(self):
        from nba_gm_data.sim import sim_game_with_context
        from nba_gm_data.schema import to_plain
        from nba_gm_data.save import create_league_save, load_save, write_save, box_score_view
        canonical = self.context['canonical']
        game = next(g for g in self.context['schedule'] if g.get('phase') == 'regular')
        result = to_plain(sim_game_with_context(self.context, str(game['externalGameId']), mode='sandbox-sim', seed=17))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'tracking.json'
            create_league_save(self.root, canonical, 'MIN', path, seed=17)
            saved = load_save(path)
            saved['game_results'] = [result]
            write_save(path, saved)
            before = path.read_bytes()
            view = box_score_view(canonical, path, result['game_id'])
            self.assertEqual(view['plus_minus_tracking'], result['plus_minus_tracking'])
            self.assertEqual({r['player_id']: r['plus_minus'] for r in view['player_lines'] if r['minutes']},
                             {r['player_id']: r['plus_minus'] for r in result['player_lines'] if r['minutes']})
            self.assertEqual(path.read_bytes(), before)
            legacy = deepcopy(result)
            legacy.pop('plus_minus_tracking')
            for row in legacy['player_lines']:
                for key in ('plus_minus', 'on_court_points_for', 'on_court_points_against'):
                    row.pop(key, None)
            saved['game_results'] = [legacy]
            write_save(path, saved)
            view = box_score_view(canonical, path, result['game_id'])
            self.assertIsNone(view['plus_minus_tracking'])
            self.assertTrue(all('plus_minus' not in r for r in view['player_lines'] if r['minutes']))

    def test_full_simulation_overtime_keeps_the_preexisting_result(self):
        from nba_gm_data import sim
        from nba_gm_data.schema import to_plain
        original = sim.simulate_team_line

        def tied(*args, **kwargs):
            rows, team = original(*args, **kwargs)
            baskets = sim.normalize_point_values([r['minutes'] for r in rows], 50)
            for row, made in zip(rows, baskets):
                row.update(points=2*made, fgm=made, fga=made+3, fg3m=0, fg3a=0, ftm=0, fta=0)
            team.update(points=100, fgm=50, fga=sum(r['fga'] for r in rows), fg3m=0, fg3a=0, ftm=0, fta=0)
            return rows, team

        gid = str(next(g for g in self.context['schedule'] if g.get('phase') == 'regular')['externalGameId'])
        with patch.object(sim, 'simulate_team_line', side_effect=tied):
            with patch('nba_gm_data.plus_minus.track_plus_minus', return_value=None):
                before = to_plain(sim.sim_game_with_context(self.context, gid, mode='sandbox-sim', seed=17))
            after = to_plain(sim.sim_game_with_context(self.context, gid, mode='sandbox-sim', seed=17))
        trace = after['plus_minus_tracking']
        self.assertEqual(trace['status'], 'tracked', trace)
        self.assertEqual(trace['duration_ticks'], 5300)
        self.assertEqual(sum(s[4] for s in trace['stints'] if s[1] <= 4800), 100)
        self.assertEqual(sum(s[5] for s in trace['stints'] if s[1] <= 4800), 100)
        self.assertEqual(before['team_lines'], after['team_lines'])
        for old, new in zip(before['player_lines'], after['player_lines']):
            self.assertEqual(old, {key: new[key] for key in old})


if __name__ == '__main__':
    unittest.main()
