"""S2-FINISHES: the last five minutes of the 4th quarter and overtime by time left and score.

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
        for key, (ln, th, fo, mk) in FT.CELLS.items():
            tb, mb = key.split("|")
            self.assertIn(tb, FIN.T_BANDS)
            self.assertIn(mb, FIN.M_BANDS)
            self.assertTrue(.25 <= ln <= 2.5, key)
            self.assertTrue(abs(th) <= 2.5 and abs(fo) <= 1.5 and abs(mk) <= 1.0, key)
        self.assertEqual(set(FT.TAKE_24_60), set(G.TAKE_FOUL))
        self.assertTrue(all(0.0 <= v <= .9 for v in FT.TAKE_24_60.values()))
        # Situations the fit leaves to the rules: a leader's last 24 seconds.
        for mb in ("1_3", "4_6", "7_10", "11+"):
            self.assertEqual(FIN.cell(10.0, int(mb.split("_")[0].rstrip("+")))[:3], (1.0, 0.0, 0.0), mb)

    def test_real_patterns(self):
        # Real: with 2-5 minutes left leaders play slower than trailing teams; in the last minute a team down 4-10
        # hurries and shoots more threes than a team up 4-10.
        self.assertGreater(FIN.cell(200.0, 5)[0], FIN.cell(200.0, -8)[0])
        self.assertLess(FIN.cell(40.0, -5)[0], FIN.cell(200.0, -5)[0])
        self.assertGreater(FIN.cell(40.0, -5)[1], FIN.cell(40.0, 5)[1])
        # More deliberate fouls with 24-60 seconds left than the tagged take-foul fit counted.
        self.assertGreater(FT.TAKE_24_60["4_6"], G.TAKE_FOUL["4_6"][2])


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
        saved, take = FIN.GRID, FIN.TAKE_24_60
        FIN.install({})
        FIN.TAKE_24_60 = None
        try:
            # A neutral table and the late rules off: the same games as with the finishes off.
            neutral = self._games({"end_last_shot_behind": G.LOOP["end_last_shot"], "late_runout": 0.0,
                                   "late_concede": 0.0, "late_press_tov": 0.0})
        finally:
            FIN.GRID, FIN.TAKE_24_60 = saved, take
        self.assertEqual(off, neutral)

    def test_on_plays_full_games(self):
        on = self._games()
        self.assertTrue(all(p >= 4 and h != a for h, a, p in on))
        self.assertNotEqual(on, self._games({"finishes": 0.0}))


if __name__ == "__main__":
    unittest.main()
