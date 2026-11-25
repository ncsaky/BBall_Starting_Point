"""S2-SCHEMES: team ball-screen schemes, who is charged with a shooting foul, two-for-ones and late timeouts.

Light: rule-level checks plus a dozen replayed and generated games. Normal gameplay never selects Stage 2."""
import random
import unittest
from pathlib import Path
from types import SimpleNamespace

from nba_gm_data import sim
from nba_gm_data.stage2 import engine as E
from nba_gm_data.stage2 import game as G
from nba_gm_data.stage2 import schemes as SCH
from nba_gm_data.stage2 import screens as SC

ROOT = Path(__file__).resolve().parents[1]


class SchemeTableTest(unittest.TestCase):
    def test_table_covers_the_league_with_modest_tilts(self):
        rows = SCH.table()
        self.assertGreaterEqual(len({r["team"] for r in rows.values()}), 30)
        for r in rows.values():
            self.assertLess(abs(r["aggression"]), 1.0)
            self.assertLess(abs(r["switching"]), 1.0)
        # The study's named contrast: Fernandez's Nets pressure screens more than Mazzulla's Celtics.
        self.assertGreater(rows["jordi fernandez"]["aggression"], rows["joe mazzulla"]["aggression"])

    def test_lookup(self):
        coach = SimpleNamespace(coach_name="Jordi Fernández")      # accents do not matter
        row = SCH.table()["jordi fernandez"]
        self.assertEqual(SCH.scheme_for(coach, "BKN"), (row["aggression"], row["switching"]))
        moved = SCH.scheme_for(coach, "BOS")                          # a coach on a new team brings half his habit
        self.assertAlmostEqual(moved[0], SCH.MOVED_SHARE * row["aggression"])
        self.assertEqual(SCH.scheme_for(SimpleNamespace(coach_name="Nobody Atall"), "BKN"), (0.0, 0.0))
        self.assertEqual(SCH.scheme_for(None, "BKN"), (0.0, 0.0))
        SCH.ENABLED = False
        try:
            self.assertEqual(SCH.scheme_for(coach, "BKN"), (0.0, 0.0))
        finally:
            SCH.ENABLED = True

    def test_tilts_move_the_coverage_mix(self):
        z = (-1.0, .3, -3.0)
        base = SC.probabilities_from_logits(*z)
        self.assertAlmostEqual(sum(base), 1.0, places=9)
        aggressive = SC.probabilities_from_logits(*z, (.5, 0.0))
        self.assertLess(aggressive[1], base[1])           # fewer drops
        self.assertGreater(aggressive[3], base[3])        # more traps
        self.assertAlmostEqual(aggressive[0], base[0])    # switching untouched
        switching = SC.probabilities_from_logits(*z, (0.0, .5))
        self.assertGreater(switching[0], base[0])
        self.assertAlmostEqual(sum(switching), 1.0, places=9)


class FoulChargeTest(unittest.TestCase):
    def _game(self, shares):
        g = G.Game.__new__(G.Game)
        g.rng = random.Random(3)
        g.team_foul_share = shares
        g.caution_z = (0.0,) * 8
        card = lambda d: SimpleNamespace(d_foul=d)  # noqa: E731
        de = SimpleNamespace(on=[0, 1, 2, 3, 4], cards=[card(0.0), card(0.0), card(2.0), card(0.0), card(0.0)],
                             stats=[[0] * len(G.STAT_KEYS) for _ in range(5)])
        return g, de

    def test_shot_defender_or_teammate(self):
        g, de = self._game((0.0, 0.0, 0.0, 0.0))
        self.assertTrue(all(g._shooting_fouler(de, 1, 0) == 1 for _ in range(200)))
        g, de = self._game((1.0, 1.0, 1.0, 1.0))
        picks = [g._shooting_fouler(de, 1, 0) for _ in range(2000)]
        self.assertNotIn(1, picks)
        # The teammate with the worst foul terms (slot 2) is charged most often.
        self.assertGreater(picks.count(2), 2 * picks.count(0))

    def test_fitted_shares(self):
        self.assertEqual((G.LOOP["foul_team_rim"], G.LOOP["foul_team_short"], G.LOOP["foul_team_jump"]), (.6, .6, .45))


class EndOfPeriodGamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        cls.context["indices"] = sim.build_sim_indices(cls.context)
        games = [g for g in cls.context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")]
        cls.ids = [str(g["externalGameId"]) for g in sorted(games, key=lambda g: str(g["externalGameId"]))][::97][:12]

    def _games(self, mode, loop=None):
        out = []
        sched, teams = self.context["indices"]["schedule_by_game_id"], self.context["indices"]["teams_by_espn_id"]
        for gid in self.ids:
            game = sched[gid]
            home, away = teams[str(game["homeTeamId"])], teams[str(game["awayTeamId"])]
            pools = [sim.game_player_pool(self.context, gid, t, mode, game_date=game.get("gameDate")) for t in (home, away)]
            g, _ = E.play_stage2_game(self.context, game, home, away, *pools, game_id=gid, mode=mode, seed=2, loop=loop)
            out.append(g)
        return out

    def test_late_timeouts_and_two_for_ones(self):
        games = self._games("replay-real-minutes")
        self.assertTrue(all(g.late_timeouts <= 4 * (1 + max(0, g.period - 4)) for g in games))
        self.assertTrue(all(g.home.late_to >= 0 and g.away.late_to >= 0 for g in games))
        self.assertGreater(sum(g.late_timeouts for g in games), 0)
        forced = self._games("replay-real-minutes", loop={"two4one_30": 1.0, "two4one_35": 1.0, "two4one_39": 1.0})
        self.assertGreater(sum(g.two_for_one for g in forced), 0)   # about .13 a game at the fitted chances
        off = self._games("replay-real-minutes", loop={"to_behind": 0.0, "to_tied": 0.0, "to_ahead": 0.0,
                                                       "two4one_30": 0.0, "two4one_35": 0.0, "two4one_39": 0.0})
        self.assertEqual(sum(g.late_timeouts + g.two_for_one for g in off), 0)

    def test_schemes_reach_the_teams(self):
        games = self._games("sandbox-sim")
        self.assertTrue(any(g.home.scheme != (0.0, 0.0) or g.away.scheme != (0.0, 0.0) for g in games))


if __name__ == "__main__":
    unittest.main()
