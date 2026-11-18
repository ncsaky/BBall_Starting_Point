"""Lineup chemistry fitted to real lineups (src/nba_gm_data/lineup_fit.py, data/canonical/lineup_fit.json)."""
import math
import unittest

from nba_gm_data import lineup_fit
from nba_gm_data.lineup_fit import (expected_terms, fit_coefficients, lineup_fit_effect, player_fit_flags,
                                    poisson_binomial)
from nba_gm_data.sim import mean_off_rating

SHOOTER = {"non_shooter": False, "creator": False}
NON_SHOOTER = {"non_shooter": True, "creator": False}
CREATOR = {"non_shooter": False, "creator": True}

TEST_FIT = {
    "offense": {"creator_x_shooters": 1.0, "five_shooters": -0.5},
    "defense": {"non_shooters_beyond_2": 1.0},
    "league_mean": {"creator_x_shooters": 2.0, "five_shooters": 0.2, "non_shooters_beyond_2": 0.1},
    "rotation_ratio": {"creator_x_shooters": 1.0, "five_shooters": 1.0, "non_shooters_beyond_2": 0.5},
}


def lineup(*flags):
    return [(f, 48.0) for f in flags]


class LineupFitMechanics(unittest.TestCase):
    def test_poisson_binomial_is_a_distribution(self):
        dist = poisson_binomial([0.2, 0.5, 0.9])
        self.assertAlmostEqual(sum(dist), 1.0)
        self.assertAlmostEqual(sum(k * q for k, q in enumerate(dist)), 1.6)

    def test_exact_lineup_counts(self):
        five_non_shooters = expected_terms(lineup(*[NON_SHOOTER] * 5))
        self.assertAlmostEqual(five_non_shooters["non_shooters_beyond_2"], 3.0)
        self.assertAlmostEqual(five_non_shooters["five_shooters"], 0.0)
        self.assertAlmostEqual(five_non_shooters["creator_x_shooters"], 0.0)
        five_out = expected_terms(lineup(CREATOR, *[SHOOTER] * 4))
        self.assertAlmostEqual(five_out["five_shooters"], 1.0)
        self.assertAlmostEqual(five_out["creator_x_shooters"], 5.0)  # the creator counts as one of the five shooters
        no_creator = expected_terms(lineup(*[SHOOTER] * 5))
        self.assertAlmostEqual(no_creator["creator_x_shooters"], 0.0)

    def test_rotation_expectation_matches_enumeration(self):
        # Ten players at 24 minutes each: every player is on the floor half the time.
        entries = [(NON_SHOOTER, 24.0)] * 4 + [(CREATOR, 24.0)] * 2 + [(SHOOTER, 24.0)] * 4
        terms = expected_terms(entries)
        ns = poisson_binomial([0.5] * 4)
        self.assertAlmostEqual(terms["non_shooters_beyond_2"], sum(q * max(0, k - 2) for k, q in enumerate(ns)))
        self.assertAlmostEqual(terms["five_shooters"], 0.5 ** 4)
        # creators: each on with p .5 (always "with a creator" himself); plain shooters: .5 x P(any of 2 creators on).
        self.assertAlmostEqual(terms["creator_x_shooters"], 2 * 0.5 + 4 * 0.5 * (1 - 0.25))

    def test_single_lineup_ignores_rotation_ratio(self):
        exact = lineup_fit_effect(lineup(*[NON_SHOOTER] * 3, *[SHOOTER] * 2), coefficients=TEST_FIT)
        self.assertAlmostEqual(exact["defense"], 1.0 * (1.0 - 0.1))
        rotation = lineup_fit_effect([(NON_SHOOTER, 28.8)] * 5 + [(SHOOTER, 19.2)] * 5, coefficients=TEST_FIT)
        expected_beyond = expected_terms([(NON_SHOOTER, 28.8)] * 5 + [(SHOOTER, 19.2)] * 5)["non_shooters_beyond_2"]
        self.assertAlmostEqual(rotation["defense"], round(1.0 * (expected_beyond * 0.5 - 0.1), 4), places=4)

    def test_creator_term_is_a_slope(self):
        fit = {"offense": {"creator_x_shooters": 1.0}, "defense": {}, "league_mean": {}, "rotation_ratio": {},
               "creator_shooters_mean": 3.5}
        usual = lineup_fit_effect(lineup(CREATOR, *[SHOOTER] * 2, NON_SHOOTER, NON_SHOOTER), coefficients=fit)
        spaced = lineup_fit_effect(lineup(CREATOR, *[SHOOTER] * 4), coefficients=fit)
        no_creator = lineup_fit_effect(lineup(*[SHOOTER] * 5), coefficients=fit)
        self.assertAlmostEqual(usual["offense"], -0.5)
        self.assertAlmostEqual(spaced["offense"], 1.5)
        self.assertAlmostEqual(no_creator["offense"], 0.0)

    def test_league_average_lineup_is_neutral(self):
        fit = {"offense": {"five_shooters": -2.0}, "defense": {}, "league_mean": {"five_shooters": 1.0}, "rotation_ratio": {}}
        self.assertAlmostEqual(lineup_fit_effect(lineup(*[SHOOTER] * 5), coefficients=fit)["offense"], 0.0)

    def test_flags_use_game_ratings(self):
        self.assertTrue(player_fit_flags({"spacing": 10.0, "usage": 60.0})["non_shooter"])
        self.assertFalse(player_fit_flags({"spacing": 80.0, "usage": 60.0})["non_shooter"])
        self.assertTrue(player_fit_flags({"spacing": 80.0, "usage": 80.0})["creator"])

    def test_fit_enters_the_offensive_rating_one_for_one(self):
        base = {"offense_creation": 50, "offense_spacing": 50, "offense_pressure": 50, "offense_possession_extension": 50}
        opp = {"defense_rim": 50, "defense_total": 50}
        zero = {"offense": 0.0, "defense": 0.0}
        kwargs = dict(home_mod=0.0, rest_mod=zero, age_mod=zero, opp_age_mod={"defense_leak": 0.0},
                      availability_mod=zero, opp_availability_mod={"defense_leak": 0.0}, game_env_mod=zero,
                      matchup_total_mod=zero, creator_mod=0.0, spacing_mod=0.0, rest_context=None)
        rating = lambda team, other: mean_off_rating({}, team, other, zero, zero, {"shot_quality_delta": 0.0}, **kwargs)
        plain = rating(base, opp)
        self.assertAlmostEqual(rating({**base, "lineup_fit_offense": -1.5}, opp) - plain, -1.5, places=6)
        self.assertAlmostEqual(rating(base, {**opp, "lineup_fit_defense": 2.0}) - plain, 2.0, places=6)


class FittedLineupChemistry(unittest.TestCase):
    """The committed fit: the game's non-additive fit now matches the evidence-based targets."""

    @classmethod
    def setUpClass(cls):
        cls.fit = fit_coefficients(lineup_fit.FIT_PATH)
        if cls.fit.get("version") == "none":
            raise unittest.SkipTest("data/canonical/lineup_fit.json missing")
        cls.decisions = cls.fit["decisions"]

    def test_only_adopted_terms_change_the_game(self):
        for key, row in self.decisions.items():
            side, term = key.split(":")
            if row["adopted"]:
                self.assertAlmostEqual(self.fit[side][term], row["target_per_100"] - row["game_before"], places=2)
                self.assertTrue(row["same_sign"] and row["clear_of_noise"])
            else:
                self.assertNotIn(term, self.fit[side])

    def test_five_non_shooters_are_penalized_within_the_evidence(self):
        """Five non-shooters vs two: what the game charges beyond the players' own ratings (its built-in curvature plus
        this fit) sits inside the real-lineup evidence's 95% range, at both ends of the floor."""
        five = lineup_fit_effect(lineup(*[NON_SHOOTER] * 5))
        two = lineup_fit_effect(lineup(*[NON_SHOOTER] * 2, *[SHOOTER] * 3))
        for side in ("offense", "defense"):
            row = self.decisions[f"{side}:non_shooters_beyond_2"]
            added = (five[side] - two[side]) / 3  # per extra non-shooter, from the fit term
            self.assertAlmostEqual(added, self.fit[side].get("non_shooters_beyond_2", 0.0), places=3)
            game_total = row["game_before"] + added  # points per 100 per extra non-shooter, game after the change
            share = self.fit["rule"]["possession_share"]
            low = (row["evidence"] - 2 * row["se"]) * share
            high = (row["evidence"] + 2 * row["se"]) * share
            self.assertTrue(low <= game_total <= high, f"{side}: game {game_total:+.2f} outside evidence {low:+.2f}..{high:+.2f}")

    def test_shooters_matter_more_next_to_a_creator(self):
        row = self.decisions["offense:creator_x_shooters"]
        four_shooters = lineup_fit_effect(lineup(CREATOR, *[SHOOTER] * 3, NON_SHOOTER))
        three_shooters = lineup_fit_effect(lineup(CREATOR, *[SHOOTER] * 2, NON_SHOOTER, NON_SHOOTER))
        if row["adopted"]:
            # One more shooter beside the creator: + the fitted slope (no other fit term changes between these two).
            self.assertAlmostEqual(four_shooters["offense"] - three_shooters["offense"], self.fit["offense"]["creator_x_shooters"], places=3)
            self.assertGreater(self.fit["offense"]["creator_x_shooters"], 0.3)
            # Without a creator the shooters get no slope, and a creator with the usual spacing gets nothing extra.
            no_creator = lineup_fit_effect(lineup(*[SHOOTER] * 3, NON_SHOOTER, NON_SHOOTER))
            self.assertAlmostEqual(no_creator["terms"]["offense:creator_x_shooters"], 0.0, places=4)
            self.assertLess(abs(self.fit["creator_shooters_mean"] - 3.5), 1.0)

    def test_sim_team_features_carry_the_fit(self):
        from nba_gm_data.sim import lineup_fit_features
        bigs = [({"id": f"b{i}", "position": "C"}, {"spacing": 5.0, "usage": 60.0}, 48.0) for i in range(5)]
        spaced = [({"id": "c", "position": "PG"}, {"spacing": 90.0, "usage": 85.0}, 48.0)] + [
            ({"id": f"s{i}", "position": "SF"}, {"spacing": 80.0, "usage": 60.0}, 48.0) for i in range(4)]
        bad, good = lineup_fit_features(bigs), lineup_fit_features(spaced)
        self.assertGreater(bad["lineup_fit_defense"], good["lineup_fit_defense"])  # five non-shooters give up more
        # The all-shooter unit: its fifth shooter adds less than the sum of the players says.
        expected = sum(self.fit["offense"].get(t, 0.0) * ((1.0 if t == "five_shooters" else 5 - self.fit["creator_shooters_mean"])
                                                          - self.fit["league_mean"].get(t, 0.0)) for t in ("five_shooters", "creator_x_shooters"))
        self.assertAlmostEqual(good["lineup_fit_offense"], expected, places=3)

    def test_rotation_ratios_are_measured(self):
        for term, ratio in self.fit["rotation_ratio"].items():
            self.assertTrue(0.2 < ratio < 2.0, term)
            self.assertFalse(math.isnan(ratio))


if __name__ == "__main__":
    unittest.main()
