"""Stars keep their box-score identity: turnovers, assists, steals and free throws follow each player's own rate.

2026-11-18: high-usage ball handlers simulated ~2 turnovers per 36 (real 3.6-4.1), rim attackers about half their
free throws, Jokic 6.5 assists per 36 (real 11.1). Causes: per-player formulas with little spread, rounding noise
that gave every bench player a near-fixed extra event, and team totals pulled back to the league average. The
rates now come from fits to real 2025-26 per-36 rates (nba_gm_data.box_rates) and the counts are unbiased Poisson
draws from the same random numbers as before, so game scores are unchanged.
"""
import json
import random
import statistics
import unittest
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import box_rates
from nba_gm_data.sim import normalize_secondary_box_score_totals

ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    try:
        from nba_gm_data.ratings_model import load_league_inputs
        return load_league_inputs(ROOT)
    except FileNotFoundError:
        return None


class FittedRateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = _inputs()
        if cls.inputs is None:
            raise unittest.SkipTest("player inputs file not available")

    def rate(self, fn, player_id):
        value = fn(self.inputs[player_id])
        self.assertIsNotNone(value, player_id)
        return value

    def test_ball_handlers_turn_it_over_more_than_bigs_and_shooters(self):
        tov = box_rates.turnovers_per36_from_inputs
        for handler in ("player_lal-luka-doncic", "player_det-cade-cunningham", "player_chi-josh-giddey"):
            self.assertGreater(self.rate(tov, handler), 2.7, handler)  # real 3.9-4.1; the old formula gave ~2
        for low in ("player_min-rudy-gobert",):
            self.assertLess(self.rate(tov, low), 1.8, low)

    def test_jokic_is_an_elite_passer_again(self):
        ast = box_rates.assists_per36_from_inputs
        jokic = self.rate(ast, "player_den-nikola-jokic")
        self.assertGreater(jokic, 9.5)          # real 2025-26: 11.1 per 36 (the old fit gave 7.1)
        self.assertGreater(jokic, 4 * self.rate(ast, "player_min-rudy-gobert"))

    def test_free_throws_per_point_follow_contact_seeking(self):
        ftpp = box_rates.fta_per_point_from_inputs
        self.assertGreater(self.rate(ftpp, "player_min-rudy-gobert"), 0.30)
        self.assertGreater(self.rate(ftpp, "player_por-deni-avdija"), 0.26)
        self.assertLess(self.rate(ftpp, "player_bos-payton-pritchard"), 0.14)

    def test_steal_specialists_stand_out(self):
        stl = box_rates.steals_per36_from_inputs
        self.assertGreater(self.rate(stl, "player_atl-dyson-daniels"), 1.8)
        self.assertGreater(self.rate(stl, "player_atl-dyson-daniels"), self.rate(stl, "player_min-rudy-gobert") + 0.6)

    def test_scorers_and_role_players_are_far_apart(self):
        pts = box_rates.points_per36_from_inputs
        # Real 2025-26 per 36: Wembanyama 30.8, Gilgeous-Alexander 33.8, Porter Jr. 26.8, Siakam 26.0;
        # Dort 11.2, Sion James 8.6. The old scoring weights gave ~20 vs ~17.
        for scorer in ("player_sas-victor-wembanyama", "player_okc-shai-gilgeous-alexander",
                       "player_bkn-michael-porter-jr", "player_ind-pascal-siakam"):
            self.assertGreater(self.rate(pts, scorer), 24.0, scorer)
        for role in ("player_atl-luguentz-dort", "player_cha-sion-james"):
            self.assertLess(self.rate(pts, role), 13.5, role)

    def test_rates_are_bounded_for_every_player(self):
        for player_id, inputs in self.inputs.items():
            for fn, low, high in ((box_rates.turnovers_per36_from_inputs, .4, 7.0), (box_rates.points_per36_from_inputs, 3.0, 40.0),
                                  (box_rates.assists_per36_from_inputs, .5, 16.0),
                                  (box_rates.steals_per36_from_inputs, .2, 4.0),
                                  (box_rates.fta_per_point_from_inputs, .03, .75)):
                value = fn(inputs)
                if value is not None:
                    self.assertTrue(low <= value <= high, (player_id, fn.__name__, value))

    def test_old_ratings_fallback_orders_creators_above_role_players(self):
        creator = {"passing_reads": 92, "rim_pressure": 88, "scheme_iq": 70, "shooting_range": 70,
                   "defensive_effort": 60, "screen_navigation": 60, "rim_deterrence": 40}
        role = {"passing_reads": 45, "rim_pressure": 45, "scheme_iq": 70, "shooting_range": 80,
                "defensive_effort": 60, "screen_navigation": 60, "rim_deterrence": 40}
        self.assertGreater(box_rates.turnovers_per36_from_traits(creator), box_rates.turnovers_per36_from_traits(role) + 1.0)
        self.assertGreater(box_rates.fta_per_point_from_traits(creator), box_rates.fta_per_point_from_traits(role) * 1.5)
        # Missing traits fall back to 50s, never an error.
        self.assertGreater(box_rates.steals_per36_from_traits({}), 0.2)


class PoissonDrawTests(unittest.TestCase):
    def test_mean_and_spread_match_and_draws_are_deterministic(self):
        rng = random.Random(3)
        uniforms = [rng.random() for _ in range(20000)]
        for mean in (0.3, 2.0, 9.5):
            draws = [box_rates.poisson_quantile(mean, u) for u in uniforms]
            self.assertAlmostEqual(statistics.mean(draws), mean, delta=0.05 * mean + 0.02)
            self.assertAlmostEqual(statistics.pvariance(draws), mean, delta=0.08 * mean + 0.03)
        self.assertEqual(box_rates.poisson_quantile(4.0, 0.37), box_rates.poisson_quantile(4.0, 0.37))
        self.assertEqual(box_rates.poisson_quantile(0.0, 0.99), 0)
        self.assertLessEqual(box_rates.poisson_quantile(3.0, 0.2), box_rates.poisson_quantile(3.0, 0.8))
        self.assertAlmostEqual(box_rates.normal_to_uniform(0.0), 0.5)


class TeamShareTests(unittest.TestCase):
    def test_team_rescaling_keeps_the_stars_share(self):
        """Over many games a player's share of team assists/steals matches his share of expected events."""
        rates = {"star": 10.0, "wing": 4.0, "big": 2.0, "bench1": 2.5, "bench2": 1.5, "bench3": 1.0}
        steal_rates = {"star": 2.0, "wing": 1.2, "big": 0.8, "bench1": 1.0, "bench2": 0.8, "bench3": 0.6}
        minutes = {"star": 36, "wing": 34, "big": 30, "bench1": 22, "bench2": 18, "bench3": 12}
        rng = random.Random(11)
        totals = {"assists": {k: 0 for k in rates}, "steals": {k: 0 for k in rates}}
        expected_sums = {"assists": sum(rates[k] * minutes[k] / 36 for k in rates),
                         "steals": sum(steal_rates[k] * minutes[k] / 36 for k in rates)}
        for game in range(1500):
            lines = [{"player_id": k, "minutes": minutes[k], "points": 10 + game % 13,
                      "assists": box_rates.poisson_quantile(rates[k] * minutes[k] / 36, rng.random()),
                      "steals": box_rates.poisson_quantile(steal_rates[k] * minutes[k] / 36, rng.random()),
                      "rebounds": 5, "blocks": 1} for k in rates]
            # Each player's own steal rate (the team total's missing steals are handed out by it, sim.reshare_by_rates).
            features = {k: {"steals_per36": steal_rates[k]} for k in rates}
            normalize_secondary_box_score_totals(lines, features, 114, 100.0, expected={**expected_sums, "assist_model": "inputs"})
            for line in lines:
                for key in totals:
                    totals[key][line["player_id"]] += line[key]
        for key, table in (("assists", rates), ("steals", steal_rates)):
            all_events = sum(totals[key].values())
            share = totals[key]["star"] / all_events
            expected_share = table["star"] * minutes["star"] / 36 / expected_sums[key]
            self.assertAlmostEqual(share, expected_share, delta=0.03, msg=(key, share, expected_share))


class ScoresUnchangedTests(unittest.TestCase):
    """The box-score rates only decide who gets the events: changing them must not move a game's score.

    Free throws can move a player's points by a point or two: a line's points less its free throws and threes must be
    even, and odd lines are settled by moving a point between teammates (offense.settle_odd_lines, SHOOTING-SPLITS)."""

    @classmethod
    def setUpClass(cls):
        from nba_gm_data.sim import load_sim_context
        cls.canonical = json.loads((ROOT / 'data/canonical/universe_2026_27_offseason.json').read_text())
        cls.context = load_sim_context(ROOT, cls.canonical)
        cls.games = [str(g['externalGameId']) for g in cls.context['schedule'] if g.get('phase') == 'regular'][:6]

    def run_games(self):
        from nba_gm_data.schema import to_plain
        from nba_gm_data.sim import invalidate_sim_cache, sim_game_with_context
        invalidate_sim_cache(self.canonical)
        out = []
        for seed, gid in enumerate(self.games):
            out.append(to_plain(sim_game_with_context(self.context, gid, mode='sandbox-sim', seed=seed)))
        invalidate_sim_cache(self.canonical)
        return out

    def test_doubling_the_rates_changes_the_box_but_not_the_score(self):
        base = self.run_games()
        self.assertEqual(base, self.run_games())  # deterministic
        with patch('nba_gm_data.sim.TURNOVER_LEVEL', 2.0), patch('nba_gm_data.sim.STEAL_LEVEL', 2.0), \
                patch('nba_gm_data.offense.FT_LEVEL', 2.0):
            changed = self.run_games()
        self.assertNotEqual([g['player_lines'] for g in base], [g['player_lines'] for g in changed])
        for a, b in zip(base, changed):
            self.assertEqual((a['home_score'], a['away_score']), (b['home_score'], b['away_score']))
            self.assertEqual([(p['player_id'], p['minutes']) for p in a['player_lines']],
                             [(p['player_id'], p['minutes']) for p in b['player_lines']])
            for p, q in zip(a['player_lines'], b['player_lines']):
                self.assertLessEqual(abs(p['points'] - q['points']), 2, (p['player_name'], p['points'], q['points']))
        with patch('nba_gm_data.sim.TURNOVER_LEVEL', 2.0), patch('nba_gm_data.sim.STEAL_LEVEL', 2.0):
            no_free_throw_change = self.run_games()
        for a, b in zip(base, no_free_throw_change):
            self.assertEqual([(p['player_id'], p['points'], p['minutes']) for p in a['player_lines']],
                             [(p['player_id'], p['points'], p['minutes']) for p in b['player_lines']])
        fta = lambda games: sum(t['fta'] for g in games for t in g['team_lines'])
        self.assertGreater(fta(changed), fta(base) * 1.3)


if __name__ == "__main__":
    unittest.main()
