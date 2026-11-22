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
    PLAYER = {"id": "player_test_rookie", "age": 19, "minutes_projection": 28, "draft_year": 2026}

    def year(self, age=19.5, trait="handle_pressure", start=2026):
        months = [f"{start + (m < 7)}-{m:02d}" for m in (7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6)]
        return {m: health.monthly_trait_delta(self.PLAYER, trait, 60.0, age, 28.0, {}, 0.0, 17, m, 1.0, None,
                                              expected=True, curve=health.INPUTS_CURVE) for m in months}

    def test_weights_keep_the_yearly_total(self):
        for player in (None, self.PLAYER, {"draft_year": 2020}):
            months = [f"{2026 + (m < 7)}-{m:02d}" for m in range(1, 13)]
            self.assertAlmostEqual(sum(health.development_month_weight(m, player) for m in months), 12.0)

    def test_in_season_share_by_nba_year_and_the_year_is_unchanged(self):
        for start, nba_year in ((2026, 1), (2027, 2)):
            year = self.year(start=start)
            in_season = sum(v for m, v in year.items() if int(m[5:]) in health.IN_SEASON_EVENT_MONTHS)
            total = sum(year.values())
            self.assertGreater(total, 0.0)
            share = health.INPUTS_IN_SEASON_SHARE_BY_NBA_YEAR.get(nba_year, health.INPUTS_IN_SEASON_SHARE)
            self.assertAlmostEqual(in_season / total, share, places=6)
            saved = (health.INPUTS_IN_SEASON_SHARE, health.INPUTS_IN_SEASON_SHARE_BY_NBA_YEAR)
            try:
                health.INPUTS_IN_SEASON_SHARE, health.INPUTS_IN_SEASON_SHARE_BY_NBA_YEAR = 0.5, {}
                even = sum(self.year(start=start).values())
            finally:
                health.INPUTS_IN_SEASON_SHARE, health.INPUTS_IN_SEASON_SHARE_BY_NBA_YEAR = saved
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


class DevelopmentMinutes(unittest.TestCase):
    def priority(self, phase="rebuilding", pick=5, draft_year=2026, season=2026, **extra):
        from nba_gm_data.save import development_minutes_priority
        return development_minutes_priority({"draft_position": pick, "draft_year": draft_year, **extra}, phase, season,
                                            2026)

    def test_only_rebuilding_teams_lean_on_young_first_rounders(self):
        self.assertGreater(self.priority(), 0.0)
        for phase in ("peak", "entering", "exiting", None):
            self.assertEqual(self.priority(phase=phase), 0.0)

    def test_fades_with_seasons_and_draft_slot(self):
        from nba_gm_data.save import DEVELOPMENT_PRIORITY_REBUILDING as table
        generated = {"source_kind": "generated_rookie"}
        years = [self.priority(draft_year=2027, season=2027 + k, **generated) for k in range(4)]
        self.assertEqual(years, [table[1], table[2], table[3], 0.0])
        self.assertLess(self.priority(pick=25), self.priority(pick=15))
        self.assertEqual(self.priority(pick=31), 0.0)
        self.assertEqual(self.priority(pick=None), 0.0)

    def test_a_real_players_own_minutes_already_carry_his_coachs_choice(self):
        # Drafted before the save began: his opening workload is his real NBA minutes with this roster's coach.
        self.assertEqual(self.priority(draft_year=2025, season=2026), 0.0)
        self.assertGreater(self.priority(draft_year=2025, season=2027), 0.0)


if __name__ == "__main__":
    unittest.main()
