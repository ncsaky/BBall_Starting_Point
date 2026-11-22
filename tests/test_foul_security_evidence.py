"""Foul drawing and handle security measured per chance (RATINGS-FT-TOV)."""
import json
import math
import random
import unittest
from pathlib import Path

from nba_gm_data import bbi_evidence as be
from nba_gm_data import foul_security_evidence as fse

ROOT = Path(__file__).resolve().parents[1]
SEASONS = ("2023-24", "2024-25", "2025-26")
FOUL_RATES = {"drives": 0.07, "rim": 0.40, "other_twos": 0.27, "threes": 0.03}


def synthetic_table(players, seed=1):
    """(season, metric) -> {key: (value, minutes, cid)} with known per-chance rates.

    players: {key: dict(minutes, foul_skill, tov_skill, drives, rim, ...)}. Counts are noise-free expectations, so the
    fitted league rates and every player's ratio are known exactly."""
    table = {}
    rng = random.Random(seed)
    for season in SEASONS:
        for key, p in players.items():
            usage = p.get("true_usage", 30.0)
            touches, drives, rim, other, threes = p["touches"], p["drives"], p["rim"], p["other_twos"], p["threes"]
            shots, pa = rim + other + threes + 1.0, p["potential_assists"]
            fta = p["foul_skill"] * sum(FOUL_RATES[k] * p[k] for k in FOUL_RATES)
            tov = p["tov_skill"] * (0.05 * shots + 0.05 * pa + 0.01 * touches) * (usage / 30.0) ** p.get("elastic", 0.0)
            values = {
                "Touches Per 75": touches, "Stable FTA Per 75": fta, "Stable FGA Per 75": rim + other + threes,
                "3PT FGA Per 75 Possessions": threes, "Rim Shot Attempts Per 75 Possessions": rim,
                "Drives Per 75 Possessions": drives, "Paint Touches Per 75 Possessions": p.get("paint", 2.0),
                "True Shot Attempts Per 75 Possessions": shots, "Potential Assists Per 75 Possessions": pa,
                "Potential Assists Per 100 Passes": 15.0, "Turnovers Per 75 Possessions": tov,
                "Stable Non Bad Pass Turnovers Per 75": 0.6 * tov, "Stable Bad Pass Turnovers Per 75": 0.4 * tov,
                "Stable Offensive Fouls Per 75": 0.1 * tov, "Stable True Usage%": usage,
            }
            for metric, value in values.items():
                table.setdefault((season, metric), {})[key] = (value, p["minutes"], key)
    return table


def league(n=80, seed=3):
    rng = random.Random(seed)
    players = {}
    for i in range(n):
        players[f"p{i}"] = dict(minutes=rng.uniform(900, 2600), foul_skill=math.exp(rng.gauss(0, 0.3)),
                                tov_skill=math.exp(rng.gauss(0, 0.2)), touches=rng.uniform(30, 90),
                                drives=rng.uniform(0, 20), rim=rng.uniform(1, 8), other_twos=rng.uniform(1, 8),
                                threes=rng.uniform(0, 9), potential_assists=rng.uniform(1, 14),
                                true_usage=rng.uniform(15, 45))
    return players


class RateFitTests(unittest.TestCase):
    def test_league_rates_per_chance_are_recovered(self):
        players = league()
        for p in players.values():
            p["foul_skill"] = 1.0   # everyone average: the fit must return the true per-chance rates
        rows = fse.season_rows(synthetic_table(players), SEASONS)
        fits = fse.fit_rates(rows, SEASONS)
        for chance, rate in FOUL_RATES.items():
            self.assertAlmostEqual(fits["foul"]["rates"][chance], rate, delta=1e-3)
        self.assertEqual(fits["foul"]["usage_elasticity"], 0.0)

    def test_usage_elasticity_is_found_for_turnovers(self):
        players = league()
        for p in players.values():
            p["tov_skill"], p["elastic"] = 1.0, 0.3
        rows = fse.season_rows(synthetic_table(players), SEASONS)
        fits = fse.fit_rates(rows, SEASONS)
        self.assertAlmostEqual(fits["turnover"]["usage_elasticity"], 0.3, delta=0.05)


class SkillSeparationTests(unittest.TestCase):
    def setUp(self):
        self.players = league()
        # A heavy creator who attacks constantly but is exactly average per chance, and a low-volume player who
        # rarely attacks but earns twice the average per chance.
        self.players["volume"] = dict(minutes=2600, foul_skill=1.0, tov_skill=1.0, touches=95, drives=25, rim=9,
                                      other_twos=8, threes=8, potential_assists=15, true_usage=40)
        self.players["craft"] = dict(minutes=2600, foul_skill=2.0, tov_skill=0.6, touches=35, drives=2, rim=1.5,
                                     other_twos=1.5, threes=4, potential_assists=2, true_usage=16)
        self.model = fse.build(ROOT, None, table=synthetic_table(self.players))

    def test_volume_is_not_skill(self):
        scores = self.model["scores"]
        raw_fta = {k: synthetic_table(self.players)[("2025-26", "Stable FTA Per 75")][k][0] for k in self.players}
        self.assertGreater(raw_fta["volume"], 2 * raw_fta["craft"])  # far more free throws per game...
        self.assertLess(abs(scores["volume"]["S24"]["grade"] - 50), 15)  # ...but an average foul drawer
        self.assertGreater(scores["craft"]["S24"]["grade"], 85)          # fewer chances, far more per chance
        self.assertGreater(scores["craft"]["S17"]["grade"], scores["volume"]["S17"]["grade"])

    def test_grades_are_bounded_smooth_and_never_clipped(self):
        for cid, inputs in self.model["scores"].items():
            for iid, s in inputs.items():
                self.assertGreater(s["grade"], 0.0)
                self.assertLess(s["grade"], 100.0)
        grades = sorted(s["S24"]["grade"] for s in self.model["scores"].values())
        self.assertGreater(len(set(round(g, 6) for g in grades)), len(grades) * 0.9)   # players stay distinct

    def test_small_samples_settle_toward_the_role_average(self):
        players = dict(self.players)
        players["cameo"] = dict(self.players["craft"], minutes=60)
        model = fse.build(ROOT, None, table=synthetic_table(players))
        cameo, craft = model["pooled"]["cameo"]["foul"], model["pooled"]["craft"]["foul"]
        self.assertAlmostEqual(cameo["raw_ratio"], craft["raw_ratio"], places=6)       # same rate per chance...
        self.assertLess(abs(cameo["ratio"] - cameo["prior_ratio"]), abs(craft["ratio"] - craft["prior_ratio"]))
        self.assertLess(model["pooled"]["cameo"]["weight"], fse.SCALE_WEIGHT)          # ...and outside the scale pool


class OverlayTests(unittest.TestCase):
    def test_blend_by_evidence_weight_and_keep_provenance(self):
        players = league()
        table = synthetic_table(players)
        section = {"players": {k: {"inputs": {iid: {"status": "estimated", "reason": "prior", "evidence": [],
                                                     "value": {"grade": 50.0, "scale": "x"}} for iid in ("S24", "S17")}}
                               for k in [*players, "rookie"]}}
        summary = fse.apply_foul_security_evidence(section, ROOT, None, table=table)
        self.assertEqual(summary["foul_security_evidence"]["cells_changed"], 2 * len(players))
        rookie = section["players"]["rookie"]["inputs"]["S24"]
        self.assertEqual(rookie["value"]["grade"], 50.0)          # no NBA chances: estimator value untouched
        self.assertEqual(rookie["reason"], "prior")
        rec = section["players"]["p0"]["inputs"]["S24"]
        self.assertEqual(rec["reason"], "estimated")
        self.assertIn(fse.VERSION, rec["evidence"][-1]["method"])
        self.assertIn("expected", rec["evidence"][-1]["notes"])

    def test_basketball_index_overlay_skips_measured_inputs_and_dead_columns(self):
        mapping = json.loads((ROOT / be.MAPPING_FILE).read_text())
        for iid in fse.MEASURED_INPUTS:
            self.assertEqual(mapping["inputs"][iid]["measured_by"], "foul_security_evidence")
        self.assertNotIn("Stable Shooting Fouls Drawn Per 75", {m["metric"] for m in mapping["inputs"]["T18"]["metrics"]})
        flat = {f"p{i}": (0.0, 1000.0, f"p{i}") for i in range(50)}
        self.assertEqual(be._percentiles(flat, 1), {})              # an all-zero column ranks nobody


if __name__ == "__main__":
    unittest.main()
