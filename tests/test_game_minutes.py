"""The coach's in-game minutes (foul trouble, blowout rest) and who absorbs an absent player's minutes."""
import random
import unittest
from statistics import mean

from nba_gm_data import game_minutes as gm
from nba_gm_data import save as sv

TARGETS = [36, 33, 31, 29, 27, 24, 21, 16, 12, 8, 3]  # 240


def pool(targets=TARGETS):
    return [{"player": {"id": f"p{i}"}, "minutes": float(m)} for i, m in enumerate(targets)]


def reserves(n=3):
    return [{"player": {"id": f"r{i}"}, "minutes": 0.0} for i in range(n)]


def run(margin, game, targets=TARGETS, extra=3):
    return gm.manage_game_minutes(pool(targets), reserves(extra), margin, random.Random(f"g{game}"),
                                  random.Random(f"f{game}"))


class GarbageTimeTests(unittest.TestCase):
    def test_garbage_time_grows_with_the_margin(self):
        self.assertEqual(gm.garbage_minutes(0), 0.0)
        self.assertEqual(gm.garbage_minutes(-5), 0.0)
        values = [gm.garbage_minutes(m) for m in range(0, 50)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(gm.garbage_minutes(30), gm.garbage_minutes(-30))

    def test_every_game_keeps_240_minutes(self):
        for game in range(200):
            for margin in (0, 8, 17, 35):
                managed, fouls, out = run(margin, game)
                self.assertEqual(sum(round(item["minutes"] * 100) for item in managed), 24000)
                self.assertTrue(all(0 <= item["minutes"] <= 42.0 for item in managed))
                self.assertTrue(out <= set(fouls))

    def test_blowouts_rest_regulars_and_play_the_deep_bench(self):
        close = [run(2, game)[0] for game in range(300)]
        blowout = [run(32, game)[0] for game in range(300)]

        def avg(games, pid):
            return mean(next((i["minutes"] for i in g if i["player"]["id"] == pid), 0.0) for g in games)

        # A 36-minute star sits for most of a 30-point game's garbage time; the end of the bench plays.
        self.assertGreater(avg(close, "p0") - avg(blowout, "p0"), 4.0)
        self.assertLess(avg(close, "p0") - avg(blowout, "p0"), 9.0)
        self.assertGreater(avg(blowout, "p10") - avg(close, "p10"), 3.0)
        self.assertGreater(avg(blowout, "r0"), 2.0)
        self.assertEqual(avg(close, "r0"), 0.0)
        # A close game plays the plan apart from foul trouble.
        self.assertLess(abs(avg(close, "p0") - 36.0), 1.0)

    def test_same_game_same_minutes(self):
        self.assertEqual(run(25, 7), run(25, 7))


class FoulTroubleTests(unittest.TestCase):
    def test_fouling_out_ends_the_game_late_and_records_six(self):
        minutes, out = gm.foul_trouble_minutes(34.0, [5, 12, 18, 24, 26, 28])
        self.assertTrue(out)
        self.assertLess(minutes, 34.0)
        self.assertGreater(minutes, 28.0)
        lines = [{"player_id": "a", "minutes": minutes}, {"player_id": "b", "minutes": 20.0}]
        gm.fouls_from_times(lines, {"a": [5, 12, 18, 24, 26, 28], "b": [3, 19.5, 25]}, {"a"})
        self.assertEqual([line["personal_fouls"] for line in lines], [6, 2])

    def test_early_fouls_cost_minutes(self):
        quiet, _ = gm.foul_trouble_minutes(32.0, [20.0, 30.0])
        early, _ = gm.foul_trouble_minutes(32.0, [2.0, 4.0, 9.0])
        self.assertEqual(quiet, 32.0)
        self.assertLess(early, 32.0)

    def test_regulars_rarely_foul_out(self):
        rng = random.Random(5)
        outs = [gm.foul_trouble_minutes(32.0, gm.draw_foul_times(rng, 1.0))[1] for _ in range(20000)]
        # Real 2025-26: regulars fouled out in 1.6% of games (a plain six-foul count would give about 5%).
        self.assertLess(mean(outs), 0.025)
        self.assertGreater(mean(outs), 0.008)


class AbsenceShareTests(unittest.TestCase):
    def rows(self, targets):
        return [{"player_id": f"p{i}", "desired": float(m), "minimum": 0.0, "maximum": max(40.0, float(m))}
                for i, m in enumerate(targets)]

    def test_healthy_rotation_is_untouched(self):
        rows = self.rows(TARGETS)
        sv.spread_vacated_minutes(rows)
        self.assertEqual([row["desired"] for row in rows], [float(m) for m in TARGETS])

    def test_missing_star_minutes_go_mostly_to_the_bench(self):
        rows = self.rows(TARGETS[1:])  # the 36-minute star is out
        sv.spread_vacated_minutes(rows)
        gains = [row["desired"] - m for row, m in zip(rows, TARGETS[1:])]
        self.assertAlmostEqual(sum(row["desired"] for row in rows), 240.0, places=6)
        # Real 2025-26: the other starters played about 1.2 more minutes each.
        self.assertLess(mean(gains[:3]), 2.0)
        self.assertGreater(mean(gains[-4:]), 2 * mean(gains[:3]))
        allocation = sv.bounded_minutes_allocation(rows, 240.0)
        self.assertAlmostEqual(sum(allocation.values()), 240.0, places=1)
        self.assertLess(max(allocation.values()), 35.0)


class SandboxGameMinutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        from nba_gm_data.sim import load_sim_context
        cls.context = load_sim_context(Path(__file__).resolve().parents[1])

    def test_generated_games_keep_minutes_and_fouls_consistent(self):
        from nba_gm_data import sim
        from nba_gm_data.schema import to_plain
        ids = [str(g["externalGameId"]) for g in self.context["schedule"] if g.get("phase") == "regular"][:40]
        for gid in ids:
            result = to_plain(sim.sim_game_with_context(self.context, gid, mode="sandbox-sim", seed=11))
            ot = int(result["team_lines"][0].get("overtime_periods") or 0)
            for team in (result["home_team_id"], result["away_team_id"]):
                lines = [line for line in result["player_lines"] if line["team_id"] == team]
                self.assertAlmostEqual(sum(line["minutes"] for line in lines), 240 + 25 * ot, places=1)
                self.assertTrue(all(0 <= line["personal_fouls"] <= 6 for line in lines))
                self.assertTrue(all(line["personal_fouls"] == 0 for line in lines if line["minutes"] <= 0))
            again = to_plain(sim.sim_game_with_context(self.context, gid, mode="sandbox-sim", seed=11))
            self.assertEqual(result["player_lines"], again["player_lines"])


if __name__ == "__main__":
    unittest.main()
