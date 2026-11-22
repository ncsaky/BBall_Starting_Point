"""ROOKIE-SEASON (2026-11-22): rookies' shot volume, when in the year young players grow, development minutes."""
import unittest

from nba_gm_data import box_rates, health, offense


def prob(v):
    return {"status": "estimated", "value": {"probability": v}, "evidence": [], "uncertainty": {"notes": "{}"}}


def grade(v):
    return {"status": "estimated", "value": {"grade": v, "scale": "t"}, "evidence": [], "uncertainty": {"notes": "{}"}}


def mix(probabilities):
    return {"status": "estimated", "value": {"rows": [{"probabilities": probabilities}]}, "evidence": [],
            "uncertainty": {"notes": "{}"}}


def guard_inputs(involvement=0.45, three_share=0.40):
    """A scoring guard: the inputs the points fit, the free-throw fit and the shot-location habit read."""
    return {
        "T08": prob(involvement), "T01": mix({"pass": 0.12, "shoot": 0.2, "drive": 0.3, "post": 0.02, "reset": 0.36}),
        "T02": mix({"three": three_share, "mid": 0.2, "rim": 0.8 - three_share}),
        "T03": mix({"catch": 0.4, "pull_up": 0.4, "movement": 0.2}), "T09": prob(0.3), "T18": prob(0.5),
        "S01": grade(50), "S02": grade(50), "S03": grade(50), "S10": grade(50), "S24": grade(50),
    }


class RookieShotVolume(unittest.TestCase):
    PROFILE = {"three_pct": 0.33, "two_pct": 0.52, "ft_pct": 0.78}

    def test_his_shots_add_up_to_his_fitted_points(self):
        inputs = guard_inputs()
        threes = offense.input_three_volume(inputs, self.PROFILE)
        self.assertIsNotNone(threes)
        fit = box_rates.points_per36_from_inputs(inputs)
        share = box_rates.tendency_from_inputs(inputs, "T02.three")
        blended = box_rates.shot_points_blend(fit, share, threes, self.PROFILE["three_pct"], self.PROFILE["two_pct"],
                                              box_rates.fta_per_point_from_inputs(inputs), self.PROFILE["ft_pct"])
        # The shot blend no longer pulls a no-record scorer's points down (Acuff: 24.8 fitted, 20.6 after the blend).
        self.assertAlmostEqual(blended, fit, places=6)

    def test_volume_follows_involvement_and_three_share(self):
        base = offense.input_three_volume(guard_inputs(), self.PROFILE)
        self.assertGreater(offense.input_three_volume(guard_inputs(involvement=0.55), self.PROFILE), base)
        self.assertGreater(offense.input_three_volume(guard_inputs(three_share=0.55), self.PROFILE), base)
        self.assertGreater(base, 5.0)   # a 45%-involvement guard taking 40% threes: real ones take ~6-8 per 36

    def test_no_inputs_keeps_the_old_formula(self):
        self.assertIsNone(offense.input_three_volume(None, self.PROFILE))
        self.assertIsNone(offense.input_three_volume({"T08": prob(0.4)}, self.PROFILE))


class SeasonTiming(unittest.TestCase):
    PLAYER = {"id": "player_test_rookie", "age": 19, "minutes_projection": 28}

    def year(self, age=19.5, trait="handle_pressure"):
        months = [f"{2026 + (m < 7)}-{m:02d}" for m in (7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6)]
        return {m: health.monthly_trait_delta(self.PLAYER, trait, 60.0, age, 28.0, {}, 0.0, 17, m, 1.0, None,
                                              expected=True, curve=health.INPUTS_CURVE) for m in months}

    def test_weights_keep_the_yearly_total(self):
        weights = [health.development_month_weight(f"2027-{m:02d}") for m in range(1, 13)]
        self.assertAlmostEqual(sum(weights), 12.0)

    def test_young_players_grow_mostly_in_season_and_the_year_is_unchanged(self):
        year = self.year()
        in_season = sum(v for m, v in year.items() if int(m[5:]) in health.IN_SEASON_EVENT_MONTHS)
        total = sum(year.values())
        self.assertGreater(total, 0.0)
        self.assertAlmostEqual(in_season / total, health.INPUTS_IN_SEASON_SHARE, places=6)
        saved = health.INPUTS_IN_SEASON_SHARE
        try:
            health.INPUTS_IN_SEASON_SHARE = 0.5
            even = sum(self.year().values())
        finally:
            health.INPUTS_IN_SEASON_SHARE = saved
        self.assertAlmostEqual(total, even, places=6)

    def test_veteran_decline_is_not_reshaped(self):
        year = self.year(age=34.0)
        values = list(year.values())
        self.assertLess(sum(values), 0.0)
        self.assertAlmostEqual(max(values), min(values), places=6)

    def test_older_ratings_unchanged(self):
        legacy = [health.monthly_trait_delta(self.PLAYER, "handle_pressure", 60.0, 19.5, 28.0, {}, 0.0, 17, m, 1.0,
                                             None, expected=True, curve=health.LEGACY_CURVE)
                  for m in ("2026-08", "2027-01")]
        self.assertAlmostEqual(legacy[0], legacy[1])


if __name__ == "__main__":
    unittest.main()
