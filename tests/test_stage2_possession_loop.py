"""S2-POSSESSION-LOOP: the Stage 2 whole-game loop (cards, possessions, clock, rotation, box score).

Covers box-score accounting, the clock and overtime, fouls and foul-outs, determinism, the player cards (shot menu,
make chances, hook and dunk rules), that both scorecards can read Stage 2 games, and a loose speed bound. The default
engine is covered by tests/test_stage2_seam.py (unchanged, never selected by gameplay)."""
import time
import unittest
from pathlib import Path

from nba_gm_data import sim
from nba_gm_data.calibration_targets import aggregate_from_results
from nba_gm_data.schema import to_plain
from nba_gm_data.stage2 import cards as C
from nba_gm_data.stage2.game_contexts import GENERIC, league_flat_inputs

ROOT = Path(__file__).resolve().parents[1]


class Stage2GamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        ids = sim.validation_game_ids(cls.context, None, False)
        cls.ids = ids[:: max(1, len(ids) // 24)][:24]
        cls.results = []
        for mode in ("replay-real-minutes", "sandbox-sim"):
            for gid in cls.ids[:12]:
                cls.results.append(to_plain(sim.sim_game_with_context(cls.context, gid, mode=mode, seed=3, engine="stage2")))

    def test_box_score_adds_up(self):
        for res in self.results:
            margin = res["home_score"] - res["away_score"]
            self.assertNotEqual(margin, 0)
            periods = None
            for tl, score in zip(res["team_lines"], (res["home_score"], res["away_score"])):
                lines = [l for l in res["player_lines"] if l["team_id"] == tl["team_id"]]
                self.assertEqual(tl["points"], score)
                self.assertEqual(sum(l["points"] for l in lines), score)
                minutes = sum(l["minutes"] for l in lines)
                ot = round((minutes - 240.0) / 25.0)
                self.assertGreaterEqual(ot, 0)
                self.assertAlmostEqual(minutes, 240.0 + 25.0 * ot, delta=.2)
                periods = ot if periods is None else periods
                self.assertEqual(periods, ot)    # both teams played the same overtimes
                for l in lines:
                    self.assertEqual(l["points"], 2 * l["fgm"] + l["fg3m"] + l["ftm"], l["player_name"])
                    self.assertLessEqual(l["fgm"], l["fga"])
                    self.assertLessEqual(l["fg3m"], l["fg3a"])
                    self.assertLessEqual(l["fg3a"], l["fga"])
                    self.assertLessEqual(l["ftm"], l["fta"])
                    self.assertEqual(l["rebounds"], l["offensive_rebounds"] + l["defensive_rebounds"])
                    self.assertLessEqual(l["personal_fouls"], 6)
                    self.assertEqual(l["plus_minus"], l["on_court_points_for"] - l["on_court_points_against"])
                sign = 1 if tl["team_id"] == res["home_team_id"] else -1
                self.assertEqual(sum(l["plus_minus"] for l in lines), 5 * sign * margin)
                self.assertGreater(tl["possessions"], 80)
                self.assertLess(tl["possessions"], 130)
                self.assertEqual(sum(1 for l in lines if l["starter"]), 5)
            # Steals are the opponent's turnovers.
            home, away = res["team_lines"]
            self.assertLessEqual(home["steals"], away["turnovers"])
            self.assertLessEqual(away["steals"], home["turnovers"])

    def test_deterministic_for_a_seed(self):
        gid = self.ids[0]
        a = to_plain(sim.sim_game_with_context(self.context, gid, mode="replay-real-minutes", seed=3, engine="stage2"))
        self.assertEqual(a, self.results[0])
        b = to_plain(sim.sim_game_with_context(self.context, gid, mode="replay-real-minutes", seed=4, engine="stage2"))
        self.assertNotEqual(a["player_lines"], b["player_lines"])

    def test_minutes_follow_the_plan(self):
        # Replayed games: the coach's live rotation lands near each player's real minutes that night.
        diffs = []
        for res in self.results[:12]:
            actual = {}
            for side in ("home_team_id", "away_team_id"):
                team = next(t for t in self.context["canonical"]["teams"] if t["id"] == res[side])
                for item in sim.game_player_pool(self.context, res["game_id"], team, "replay-real-minutes"):
                    actual[item["player"]["id"]] = float(item["minutes"])
            for l in res["player_lines"]:
                if l["player_id"] in actual:
                    diffs.append(abs(l["minutes"] - actual[l["player_id"]]))
        self.assertLess(sum(diffs) / len(diffs), 3.0)

    def test_scorecards_read_stage2_games(self):
        agg = aggregate_from_results(self.results)
        league = agg["league_totals"]
        for key in ("pace", "off_rating", "efg_pct", "ft_rate", "tov_per100", "orb_pct", "ast_rate", "stl_per100",
                    "blk_per100", "pf_per100"):
            self.assertIsNotNone(league.get(key), key)
        self.assertTrue(90 < league["pace"] < 115)
        self.assertTrue(.45 < league["efg_pct"] < .65)
        game_id = next(g for g in self.ids if g in self.context["odds"])
        report = sim.validate_game_probabilities_with_context(self.context, game_id, runs=4, seed=2, engine="stage2")
        self.assertTrue(0.0 <= report["sim"]["home_win_probability"] <= 1.0)

    def test_speed_budget(self):
        start = time.perf_counter()
        for gid in self.ids:
            sim.sim_game_with_context(self.context, gid, mode="replay-real-minutes", seed=9, engine="stage2")
        per_game = (time.perf_counter() - start) / len(self.ids)
        self.assertLess(per_game, .15)   # target ~.02-.04 s; loose bound for a busy machine


class CardsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flats = league_flat_inputs(ROOT)
        cls.means = C.means_for(ROOT)

    def test_menu_and_makes(self):
        for pid in list(self.flats)[:60]:
            flat = self.flats[pid]
            menu = C.shot_menu(flat)
            self.assertAlmostEqual(sum(menu), 1.0, places=9)
            self.assertTrue(all(m >= 0 for m in menu))
            # Short paint and midrange keep his own habit's proportion (T02).
            short = sum(menu[C.KIND_INDEX[k]] for k in ("floater", "hook", "short_jumper"))
            mid = sum(menu[C.KIND_INDEX[k]] for k in ("mid_catch", "mid_pull"))
            if flat["T02.midrange"] > .01:
                self.assertAlmostEqual(short / mid, flat["T02.short_paint"] / flat["T02.midrange"], places=6)
            table = C.make_table(pid, flat)
            self.assertTrue(all(0.0 < p < 1.0 for p in table))
            self.assertLess(table[C.KIND_INDEX["three_pull"]], table[C.KIND_INDEX["three_corner"]] + .05)
            self.assertAlmostEqual(sum(C.transition_menu(flat)), 1.0, places=9)

    def test_hook_and_dunk_rules_follow_the_inputs(self):
        base = dict(self.flats[GENERIC])
        better = dict(base, S23=base["S23"] + 20)
        hook = C.KIND_INDEX["hook"]
        self.assertGreater(C.make_table("x", better)[hook], C.make_table("x", base)[hook])
        short = dict(base, P03=240.0, P10=60.0)
        self.assertEqual(C.dunk_share(short), 0.0)
        tall = dict(base, P03=280.0, P10=80.0)
        self.assertGreater(C.dunk_share(tall), C.dunk_share(dict(tall, S12=tall["S12"] - 20)))

    def test_usage_and_turnovers_follow_tendencies(self):
        base = dict(self.flats[GENERIC])
        lo = C.build_card("a", "a", base, self.means)
        hi = C.build_card("b", "b", dict(base, T08=min(.95, base["T08"] * 1.5)), self.means)
        self.assertGreater(hi.usage, lo.usage)
        careful = C.build_card("c", "c", dict(base, S17=base["S17"] + 20), self.means)
        self.assertLess(careful.to_logit, lo.to_logit)


if __name__ == "__main__":
    unittest.main()
