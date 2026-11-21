"""S2-REBOUND-FOULS: the Stage 2 rebound and foul kernels and their spot-check helpers."""
import math
import unittest
from dataclasses import replace
from pathlib import Path

from nba_gm_data.stage2 import fouls as FK
from nba_gm_data.stage2 import game_contexts as G
from nba_gm_data.stage2 import rebounding as RK

ROOT = Path(__file__).resolve().parents[1]
HAVE_DATA = ((ROOT / "data/canonical/player_inputs_2026_27.json").exists() or
             (ROOT / "data/canonical/player_inputs_2026_27.json.gz").exists()) and (ROOT / G.BOX_FILE).exists()


def rp(pid, **kw):
    base = dict(oskill=50.0, dskill=50.0, boxout=50.0, control=50.0, reach_cm=265.0, jump_cm=75.0, strength=50.0,
                mass_kg=100.0, height_cm=200.0, crash=.3, box_share=.5, spot_m=5.0, help=.5)
    base.update(kw)
    return RK.ReboundProfile(pid, **base)


def fp(pid, **kw):
    base = dict(craft=50.0, seek=0.0, contact_finish=50.0, strength=50.0, involvement=.2, screen=.3, control=50.0,
                contest=50.0, jump=-.8, gamble=-.8, interior=50.0, height_cm=200.0)
    base.update(kw)
    return FK.FoulProfile(pid, **base)


class ReboundKernelTest(unittest.TestCase):
    def setUp(self):
        self.c = RK.FITTED
        self.off = [rp(f"o{i}", height_cm=190 + 5 * i, spot_m=7.3 - 1.2 * i) for i in range(5)]
        self.de = [rp(f"d{i}", height_cm=190 + 5 * i) for i in range(5)]

    def probs(self, off=None, de=None, miss="rim", shooter=0, c=None):
        off, de, c = off or self.off, de or self.de, c or self.c
        return RK.rebound_probabilities([RK.prepare(p, c) for p in off], [RK.prepare(p, c) for p in de],
                                        RK.matchups(off, de), miss, shooter, c)

    def test_probabilities_sum_to_one_and_defence_gets_most(self):
        for miss in RK.MISS_TYPES:
            p = self.probs(miss=miss)
            self.assertAlmostEqual(sum(p), 1.0, places=12)
            self.assertGreater(sum(p[5:]), .55)

    def test_matchups_by_height(self):
        g = RK.matchups(self.off, list(reversed(self.de)))
        self.assertEqual(sorted(g), [0, 1, 2, 3, 4])
        self.assertEqual(g[0], 4)  # the tallest defender (now first) guards the tallest attacker

    def test_offensive_technique_and_crash_raise_his_share(self):
        base = self.probs()[3]
        better = list(self.off)
        better[3] = replace(better[3], oskill=80.0)
        self.assertGreater(self.probs(off=better)[3], base)
        crash = list(self.off)
        crash[3] = replace(crash[3], crash=.9)
        self.assertGreater(self.probs(off=crash)[3], base)

    def test_box_out_technique_lowers_his_mans_share(self):
        boxer = list(self.de)
        boxer[4] = replace(boxer[4], boxout=85.0, box_share=.9)
        # defender 4 (tallest) guards attacker 4 (tallest)
        self.assertLess(self.probs(de=boxer)[4], self.probs()[4])

    def test_long_misses_favour_perimeter_players(self):
        self.assertGreater(self.probs(miss="three", shooter=4)[0], self.probs(miss="rim", shooter=4)[0])

    def test_with_values_handles_tuple_entries(self):
        c = RK.with_values(RK.ReboundCoefficients(), {"landing_m[3]": 5.0, "retreat": .2})
        self.assertEqual(c.landing_m[3], 5.0)
        self.assertEqual(c.retreat, .2)


class FoulKernelTest(unittest.TestCase):
    def setUp(self):
        self.c = FK.FITTED

    def test_drawing_craft_and_contact_seeking_raise_fouls_foul_control_lowers_them(self):
        d = fp("d")
        base = FK.shooting_foul_probability(fp("s"), d, 0, self.c)
        self.assertGreater(FK.shooting_foul_probability(fp("s", craft=80.0), d, 0, self.c), base)
        self.assertGreater(FK.shooting_foul_probability(fp("s", seek=1.0), d, 0, self.c), base)
        self.assertLess(FK.shooting_foul_probability(fp("s"), fp("d", control=85.0), 0, self.c), base)
        self.assertGreater(base, FK.shooting_foul_probability(fp("s"), d, 3, self.c))  # rim > three

    def test_shot_outcome_accounting(self):
        defense = [fp(f"d{j}", interior=40.0 + 10 * j) for j in range(5)]
        for zone in range(4):
            out = FK.shot_outcome(fp("s"), defense, 0, zone, self.c)
            and1 = FK.and_one_probability(fp("s"), zone, self.c)
            self.assertAlmostEqual(out["fga"], 1 - out["foul"] * (1 - and1))
            self.assertAlmostEqual(out["fta"], out["foul"] * (and1 + (1 - and1) * (3 if zone == 3 else 2)))
            self.assertAlmostEqual(sum(out["by"].values()), out["foul"])
        # rim attempts: part of the foul risk goes to the help defender (best interior positioning: index 4)
        self.assertIn(4, FK.shot_outcome(fp("s"), defense, 0, 0, self.c)["by"])

    def test_weights_sum_to_one(self):
        off = [fp(f"o{i}", involvement=.1 + .05 * i, seek=-1 + .4 * i) for i in range(5)]
        self.assertAlmostEqual(sum(FK.nonshooting_weights(off, self.c)), 1.0)
        self.assertAlmostEqual(sum(FK.offensive_foul_weights(off, self.c)), 1.0)
        w = FK.nonshooting_weights(off, self.c)
        self.assertGreater(w[4], w[0])


class HelperTest(unittest.TestCase):
    def test_split_half_is_stable(self):
        self.assertEqual(G.split_half("player_den-nikola-jokic"), G.split_half("player_den-nikola-jokic"))
        self.assertIn(G.split_half("x"), (0, 1))

    def test_weighted_errors_removes_noise(self):
        pairs = [(.5, .5 + (.02 if i % 2 else -.02), 100.0, .0004) for i in range(10)]
        out = G.weighted_errors(pairs)
        self.assertAlmostEqual(out["rmse"], .02, places=6)
        self.assertEqual(out["excess_rmse"], 0.0)

    def test_stage2_pieces_stay_out_of_normal_gameplay(self):
        for name in ("sim.py", "save.py", "play.py", "app_actions.py"):
            text = (ROOT / "src/nba_gm_data" / name).read_text()
            for module in ("stage2.rebounding", "stage2.fouls", "stage2.rebound_check", "stage2.foul_check", "stage2.game_contexts"):
                self.assertNotIn(module, text, f"{name} imports {module}")


@unittest.skipUnless(HAVE_DATA, "league inputs or 2025-26 box scores not present")
class SpotCheckSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from nba_gm_data.stage2 import foul_check as F
        from nba_gm_data.stage2 import rebound_check as R
        cls.R, cls.F = R, F
        cls.setup = R.ReboundSetup(ROOT, per_direction=3)

    def test_real_rates_and_environment(self):
        env = self.setup.env
        self.assertAlmostEqual(env["orb_pct"], .26, delta=.005)
        self.assertAlmostEqual(env["fouls_per100"], 19.37, delta=.1)
        self.assertLess(self.setup.missing_minutes, .03)
        adams = self.setup.real.get("player_hou-steven-adams")
        if adams:
            self.assertGreater(adams["oreb"] / adams["oreb_chances"], .18)

    def test_fitted_kernels_hit_league_levels(self):
        res = self.R.evaluate(self.setup, RK.FITTED)
        self.assertAlmostEqual(res["league_orb"], self.setup.env["orb_pct"], delta=.01)
        fs = self.F.FoulSetup(self.setup, rebound_rates=res)
        league = self.F.evaluate(fs, FK.FITTED)["league"]
        self.assertAlmostEqual(league["fouls_per100"], self.setup.env["fouls_per100"], delta=1.0)
        self.assertAlmostEqual(league["fta_per100"], self.setup.env["fta_per100"], delta=1.5)

    def test_contexts_are_deterministic(self):
        again = self.R.ReboundSetup(ROOT, per_direction=3)
        self.assertEqual([c["offense"] for c in again.contexts[:50]], [c["offense"] for c in self.setup.contexts[:50]])
        self.assertEqual([c["miss"] for c in again.contexts[:50]], [c["miss"] for c in self.setup.contexts[:50]])


if __name__ == "__main__":
    unittest.main()
