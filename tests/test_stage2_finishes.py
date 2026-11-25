"""S2-FINISHES and S2-LAST-POSSESSION: the last five minutes of the 4th quarter and overtime by time left and score.

Light: table checks plus a dozen replayed games. Normal gameplay never selects Stage 2."""
import unittest
from pathlib import Path

from nba_gm_data import sim
from nba_gm_data.stage2 import engine as E
from nba_gm_data.stage2 import finishes as FIN
from nba_gm_data.stage2 import finishes_table as FT
from nba_gm_data.stage2 import game as G

ROOT = Path(__file__).resolve().parents[1]


class BandsTest(unittest.TestCase):
    def test_time_bands(self):
        self.assertEqual([FIN.t_band(t) for t in (0.0, 24.0, 24.1, 60.0, 61.0, 120.0, 121.0, 300.0, 300.1, 720.0)],
                         [0, 0, 1, 1, 2, 2, 3, 3, -1, -1])
        self.assertIsNone(FIN.cell(301.0, 0))

    def test_margin_bands(self):
        self.assertEqual([FIN.m_band(m) for m in (-30, -11, -10, -7, -6, -4, -3, -1, 0, 1, 3, 4, 6, 7, 10, 11, 40)],
                         [0, 0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7, 8, 8])


class TableTest(unittest.TestCase):
    def test_keys_and_ranges(self):
        for key, cell in FT.CELLS.items():
            self.assertEqual(len(cell), 6, key)
            ln, th, fo, mk, mk3, tv = cell
            tb, mb = key.split("|")
            self.assertIn(tb, FIN.T_BANDS)
            self.assertIn(mb, FIN.M_BANDS)
            self.assertTrue(.25 <= ln <= 2.5, key)
            self.assertTrue(abs(th) <= 4.0 and abs(fo) <= 1.5 and abs(mk) <= 1.5 and abs(mk + mk3) <= 2.0
                            and abs(tv) <= 2.0, key)
        self.assertEqual(set(FT.TAKE_LATE), {"0", "1", "2"})
        for band in FT.TAKE_LATE.values():
            self.assertEqual(set(band), set(FIN.TAKE_KEYS))
            self.assertTrue(all(0.0 <= v <= .97 for v in band.values()))
        self.assertTrue(all(0.0 <= v <= .9 for v in FT.UP_THREE))
        # Situations the fit leaves to the rules: a leader's possession length and fouls drawn in the last 24 seconds.
        for lead in (2, 5, 8, 15):
            ln, _, fo = FIN.cell(10.0, lead)[:3]
            self.assertEqual((ln, fo), (1.0, 0.0), lead)

    def test_exact_deficit_terms(self):
        # A number (the old three-point tilt alone) or (tilt, twos, turnovers); the twos' shift leaves threes alone.
        saved = FIN.GRID, FIN.GRID_X
        try:
            FIN.install({"0_24|-3_-1": (1.0, .2, .1, .3, -.5, .05)}, {"0_24|-3": [1.0, .4, -.2], "0_24|-1": -1.0})
            ln, th, fo, mk, mk3, tv = FIN.cell(12.0, -3)
            self.assertAlmostEqual(th, 1.2)
            self.assertAlmostEqual(mk, .7)
            self.assertAlmostEqual(mk + mk3, -.2)
            self.assertAlmostEqual(tv, -.15)
            self.assertAlmostEqual(FIN.cell(12.0, -1)[1], -.8)
            self.assertEqual(FIN.cell(12.0, -2)[1:], (.2, .1, .3, -.5, .05))
        finally:
            FIN.GRID, FIN.GRID_X = saved

    def test_real_patterns(self):
        # Real: with 2-5 minutes left leaders play slower than trailing teams; in the last minute a team down 4-10
        # hurries and shoots more threes than a team up 4-10.
        self.assertGreater(FIN.cell(200.0, 5)[0], FIN.cell(200.0, -8)[0])
        self.assertLess(FIN.cell(40.0, -5)[0], FIN.cell(200.0, -5)[0])
        self.assertGreater(FIN.cell(40.0, -5)[1], FIN.cell(40.0, 5)[1])
        # Real (S2-LAST-POSSESSION): a trailing team's last-minute threes go in less often than its twos are shifted
        # (one shift for both left late threes 36-43% against a real 25-30%); a team up three gives up twos.
        for t, m in ((40.0, -5), (40.0, -2), (12.0, -5)):
            self.assertLess(FIN.cell(t, m)[4], 0.0, (t, m))
        self.assertGreater(FIN.cell(12.0, -3)[3], FIN.cell(12.0, -2)[3])
        # With 10-24 seconds left a leader is fouled on purpose on most possessions (real: about once a possession).
        self.assertTrue(all(FT.TAKE_LATE["1"][k] > .8 for k in ("1", "2", "3", "4")))
        self.assertGreater(FT.TAKE_LATE["2"]["4"], G.TAKE_FOUL["4_6"][2])


class GamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        cls.context["indices"] = sim.build_sim_indices(cls.context)
        games = [g for g in cls.context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")]
        cls.ids = [str(g["externalGameId"]) for g in sorted(games, key=lambda g: str(g["externalGameId"]))][::97][:12]

    def _games(self, loop=None):
        out = []
        sched, teams = self.context["indices"]["schedule_by_game_id"], self.context["indices"]["teams_by_espn_id"]
        for gid in self.ids:
            game = sched[gid]
            home, away = teams[str(game["homeTeamId"])], teams[str(game["awayTeamId"])]
            pools = [sim.game_player_pool(self.context, gid, t, "replay-real-minutes", game_date=game.get("gameDate"))
                     for t in (home, away)]
            g, _ = E.play_stage2_game(self.context, game, home, away, *pools, game_id=gid, mode="replay-real-minutes",
                                      seed=2, loop=loop)
            out.append((g.home.points, g.away.points, g.period))
        return out

    def test_off_matches_a_neutral_table(self):
        off = self._games({"finishes": 0.0})
        saved = FIN.GRID, FIN.GRID_X, FIN.TAKE_LATE, FIN.UP_THREE
        FIN.install({})
        FIN.TAKE_LATE, FIN.UP_THREE = None, G.UP_THREE_FOUL
        try:
            # A neutral table and the late rules off: the same games as with the finishes off.
            neutral = self._games({"end_last_shot_behind": G.LOOP["end_last_shot"], "late_runout": 0.0,
                                   "late_concede": 0.0, "late_press_tov": 0.0})
        finally:
            FIN.GRID, FIN.GRID_X, FIN.TAKE_LATE, FIN.UP_THREE = saved
        self.assertEqual(off, neutral)

    def test_on_plays_full_games(self):
        on = self._games()
        self.assertTrue(all(p >= 4 and h != a for h, a, p in on))
        self.assertNotEqual(on, self._games({"finishes": 0.0}))


if __name__ == "__main__":
    unittest.main()
