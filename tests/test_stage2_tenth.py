"""S2-TENTH: assists by who is passing, block and steal levels, the waiting switches (off), the short-paint finish,
empty spots for short-handed teams, in-game injury exits by the game clock, the inputs-file unpacking guard.

Stage 2 stays off in normal gameplay; these tests drive it directly."""
import gzip
import os
import tempfile
import time
import types
import unittest
from pathlib import Path

from nba_gm_data import sim
from nba_gm_data.stage2 import cards as C
from nba_gm_data.stage2 import coach as CO
from nba_gm_data.stage2 import engine as E
from nba_gm_data.stage2 import game as G
from nba_gm_data.stage2 import league_inputs as LI
from nba_gm_data.stage2.game_contexts import GENERIC, league_flat_inputs

ROOT = Path(__file__).resolve().parents[1]


class Stage2TenthDefaultsTest(unittest.TestCase):
    def test_kept_and_waiting_switches(self):
        # Kept on (fitted): assists by the teammates' passing, block and steal levels.
        self.assertEqual(G.LOOP["k_ast_team"], 2.0)
        self.assertEqual(G.LOOP["k_blk_level"], .8)
        self.assertEqual(G.LOOP["k_steal_level"], .5)
        # Built and measured, kept off: per-player season stats did not improve beyond seed noise (task file).
        for key in ("k_trans_speed", "k_trans_pace", "k_putback_reach", "mix_hold"):
            self.assertEqual(G.LOOP[key], 0.0, key)
        self.assertEqual(C.MENU["roll_screen"], 0.0)
        self.assertEqual(C.MENU["short_fin"], 0.0)
        for key in ("drive_pow", "cut_pow", "roll_pow", "post_pow"):
            self.assertEqual(C.MENU[key], 1.0, key)
        self.assertEqual(CO.COACH["injury_clock"], 1.0)


class Stage2TenthCardsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flats = {k: v for k, v in league_flat_inputs(ROOT).items() if k != GENERIC}
        cls.means = C.means_for(ROOT)
        cls.league = E.league_constants(ROOT)

    def test_short_finish_only_when_switched_on(self):
        sf = C.KIND_INDEX["short_finish"]
        flat = max(self.flats.values(), key=lambda f: f["T09"] * f["T02.short_paint"])
        self.assertEqual(C.shot_menu(flat, self.means)[sf], 0.0)
        saved = C.MENU["short_fin"]
        C.MENU["short_fin"] = 1.0
        try:
            menu = C.shot_menu(flat, self.means)
        finally:
            C.MENU["short_fin"] = saved
        self.assertGreater(menu[sf], 0.0)
        self.assertAlmostEqual(sum(menu), 1.0, places=9)
        table = C.make_table("x", flat)
        self.assertTrue(0.0 < table[sf] < 1.0)

    def _team(self, cards):
        t = G.TeamState("t", "TT", cards, [30.0] * 5, [0, 1, 2, 3, 4], ["wing"] * 5, 0.0, 0.0, self.league)
        t.on = [0, 1, 2, 3, 4]
        t._refresh()
        return t

    def test_teammates_passing_raises_the_assisted_chance(self):
        pids = sorted(self.flats, key=lambda p: C.log_linear(C.ASSISTS, self.flats[p]))
        mid = pids[len(pids) // 2: len(pids) // 2 + 4]
        top = pids[-1]
        cards = [C.build_card(p, p, self.flats[p], self.means) for p in [top] + mid]
        t = self._team(cards)
        # A scorer playing beside the league's best passer gets a larger assisted chance than the passer himself.
        self.assertGreater(t.ast_team[1], t.ast_team[0])
        flat_mid = self._team([C.build_card(p, p, self.flats[p], self.means) for p in pids[len(pids) // 2: len(pids) // 2 + 5]])
        self.assertGreater(t.ast_team[1], flat_mid.ast_team[1])

    def test_empty_spot_never_acts(self):
        c = C.empty_card(self.flats[next(iter(self.flats))], self.means)
        self.assertLess(c.usage, 1e-6)
        self.assertLess(c.reb.off_ability, 1e-6)
        self.assertLess(c.stl_w + c.blk_w + c.ast_w, 1e-6)


class Stage2TenthGamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        cls.gid = sim.validation_game_ids(cls.context, None, False)[100]

    def test_short_handed_team_plays_with_empty_spots(self):
        ctx = self.context
        sched = ctx["indices"]["boxscores_by_game_id"][str(self.gid)]
        game = {"externalGameId": sched["game_id"], "gameDate": sched["date"], "homeTeamId": sched["home_team_id"],
                "awayTeamId": sched["away_team_id"]}
        teams = ctx["indices"].get("teams_by_espn_id") or sim.espn_team_id_map(ctx["canonical"])
        home, away = teams[str(game["homeTeamId"])], teams[str(game["awayTeamId"])]
        mode = "replay-real-minutes"
        hp = sim.game_player_pool(ctx, self.gid, home, mode, game_date=game["gameDate"])
        ap = sim.game_player_pool(ctx, self.gid, away, mode, game_date=game["gameDate"])
        hp = sorted(hp, key=lambda it: -float(it.get("minutes") or 0))[:4]
        res = E.simulate_stage2_game(ctx, game, home, away, hp, ap, game_id=str(self.gid), mode=mode, seed=3)
        lines = [ln for ln in res.player_lines if ln["team_id"] == home["id"]]
        self.assertEqual(len(lines), 4)
        self.assertFalse(any(str(ln["player_id"]).startswith(C.EMPTY_ID) for ln in res.player_lines))
        self.assertEqual(sum(ln["points"] for ln in lines), res.home_score)
        self.assertGreater(res.away_score, res.home_score - 40)


class Stage2TenthInjuryTest(unittest.TestCase):
    def _coach(self, share):
        team = types.SimpleNamespace(starters=[0, 1, 2, 3, 4], secs=[0.0] * 6, stint=[0.0] * 6, out=set(), on=[0, 1, 2, 3, 4],
                                     groups=["wing"] * 6)
        plan = [2000.0] * 5 + [600.0]
        import random
        return CO.Coach(team, roles=["starter"] * 5 + ["bench"], plan_s=plan, flats=[{}] * 6, fatigue=[0.0] * 6,
                        rust=[False] * 6, injury_exit=[None] * 5 + [share], rng=random.Random(1)), team

    def test_exit_by_game_clock_when_he_plays_less_than_planned(self):
        coach, team = self._coach(.5)
        team.secs[5] = 120.0                      # played 2 of his planned 10 minutes
        self.assertFalse(coach._hurt_now(5, 1000.0))
        self.assertTrue(coach._hurt_now(5, 1440.0))   # half of regulation has passed
        saved = CO.COACH["injury_clock"]
        CO.COACH["injury_clock"] = 0.0
        try:
            old, team2 = self._coach(.5)
            team2.secs[5] = 120.0
            self.assertFalse(old._hurt_now(5, 2000.0))
            team2.secs[5] = 300.0
            self.assertTrue(old._hurt_now(5, 100.0))
        finally:
            CO.COACH["injury_clock"] = saved


class Stage2InputsUnpackTest(unittest.TestCase):
    def test_newer_gz_wins_over_stale_unpacked_copy(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / LI.INPUTS_FILE
            path.parent.mkdir(parents=True)
            path.write_text('{"old": 1}')
            gz = path.with_suffix(path.suffix + ".gz")
            gz.write_bytes(gzip.compress(b'{"new": 1}'))
            now = time.time()
            os.utime(path, (now - 100, now - 100))
            os.utime(gz, (now, now))
            self.assertEqual(LI._load_json(LI._inputs_path(d)), {"new": 1})
            self.assertEqual(path.read_text(), '{"old": 1}')   # the stale copy is left alone, just not read
            # A locally rebuilt unpacked copy (newer than the .gz) is kept.
            path.write_text('{"rebuilt": 1}')
            os.utime(path, (now + 100, now + 100))
            self.assertEqual(LI._load_json(LI._inputs_path(d)), {"rebuilt": 1})


if __name__ == "__main__":
    unittest.main()
