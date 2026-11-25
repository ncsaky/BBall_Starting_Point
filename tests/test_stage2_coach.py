"""S2-COACH: the Stage 2 in-game coach (substitutions from the plan, foul trouble, rhythm, blowouts, close finishes, hot
and cold hands, injuries) and pick-and-roll coverages with switching.

Light: rule-level checks plus a few dozen replayed and generated games. Normal gameplay never selects Stage 2."""
import json
import random
import statistics
import unittest
from pathlib import Path

from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.stage2 import cards as C
from nba_gm_data.stage2 import coach as CO
from nba_gm_data.stage2 import engine as E
from nba_gm_data.stage2 import game as G
from nba_gm_data.stage2 import screens as SC
from nba_gm_data.stage2.game_contexts import GENERIC, league_flat_inputs

ROOT = Path(__file__).resolve().parents[1]


def _card(base, **over):
    flat = dict(base)
    flat.update(over)
    return C.build_card(str(sorted(over.items())), "x", flat, C.means_for(ROOT))


class EvidenceTablesTest(unittest.TestCase):
    """The coach's copies of the rotation study's fitted rates match data/research/rotation_evidence.json."""

    @classmethod
    def setUpClass(cls):
        cls.ev = json.loads((ROOT / "data/research/rotation_evidence.json").read_text())

    def test_foul_exit_rates(self):
        groups = self.ev["held_out_fits"]["foul_exit_within_minute"]["groups"]
        for key, by_role in CO.FOUL_EXIT.items():
            for role, value in by_role.items():
                self.assertAlmostEqual(value, groups[f"{key}|{role}"]["prediction"], places=4)

    def test_foul_bench_and_return(self):
        pooled = self.ev["observations"]["pooled"]["regular"]
        for key, by_role in CO.FOUL_BENCH.items():
            for role, (p25, p50, p75) in by_role.items():
                row = pooled["foul_bench_seconds_if_returned"][f"{key}|{role}"]
                self.assertEqual((p25, p50, p75), (row["p25"], row["median"], row["p75"]))
                self.assertAlmostEqual(CO.FOUL_RETURNED[key][role],
                                       pooled["foul_bench_returned"][f"{key}|{role}"]["mean"], delta=.0006)
        for role, value in CO.FOUL_BASE_EXIT.items():   # copied to three decimals
            self.assertAlmostEqual(value, pooled["foul_exit_within_minute"][f"1_Q1_comparison|{role}"]["mean"],
                                   delta=.0006)

    def test_fourth_quarter_exits(self):
        groups = self.ev["held_out_fits"]["Q4_permanent_exit_next_minute"]["groups"]
        for minutes, by_band in CO.Q4_EXIT.items():
            for band, value in by_band.items():
                self.assertAlmostEqual(value, groups[f"{minutes}m|{band}"]["prediction"], places=4)


class CoachRulesTest(unittest.TestCase):
    def test_situations(self):
        self.assertEqual(CO.stint_key(2, 1), "2_Q1")
        self.assertIsNone(CO.stint_key(2, 2))
        self.assertEqual(CO.stint_key(3, 2), "3_first_half")
        self.assertEqual(CO.stint_key(4, 3), "4_Q1_Q3")
        self.assertEqual(CO.stint_key(5, 5), "5_Q4_OT")
        self.assertEqual(CO.margin_band(3), "close_0_5")
        self.assertEqual(CO.margin_band(-22), "behind_20_24")
        self.assertEqual(CO.margin_band(30), "ahead_25_plus")
        # A 25-point lead with three minutes left: the real per-minute exit chance for that window.
        self.assertAlmostEqual(CO.q4_exit_per_minute(180.0, 25), CO.Q4_EXIT[3]["ahead_25_plus"])
        self.assertAlmostEqual(CO.q4_exit_per_minute(600.0, -2), CO.Q4_EXIT[9]["close_0_5"])

    def test_roles(self):
        roles = CO.roles_for([True, True, True, True, True, False, False, False],
                             [36, 33, 30, 28, 26, 24, 15, 0], [.32, .22, .20, .18, .17, .21, .15, .15],
                             [False] * 7 + [True])
        self.assertEqual(roles, ["star", "starter", "starter", "starter", "starter", "sixth_man", "bench", "reserve"])

    def _coach(self, n=10, plans=None, replay=False):
        team = type("T", (), {})()
        team.secs = [0.0] * n
        team.stint = [0.0] * n
        team.on = list(range(5))
        team.out = set()
        team.starters = list(range(5))
        team.groups = ["guard", "guard", "wing", "wing", "big", "guard", "wing", "wing", "big", "big"][:n]
        team.lineup_dirty = False
        plans = plans or [2160, 2040, 1920, 1800, 1680, 1440, 1200, 900, 600, 0][:n]
        roles = CO.roles_for([i < 5 for i in range(n)], [p / 60 for p in plans], [.3] + [.2] * (n - 1),
                             [p == 0 for p in plans])
        return CO.Coach(team, roles=roles, plan_s=list(plans), flats=[{}] * n, fatigue=[0.0] * n, rust=[False] * n,
                        injury_exit=[None] * n, rng=random.Random(5), replay=replay)

    def test_foul_trouble_pull_rate(self):
        # A starter's second foul in the first quarter: pulled with the excess of the real rate over his normal
        # rotation ((.6772 - .184) / (1 - .184) = .604), and back before halftime's end almost always.
        pulled = 0
        returns = []
        for k in range(4000):
            coach = self._coach()
            coach.rng = random.Random(k)
            coach.on_foul(1, 2, 1, 400.0)
            if coach.benched_until[1] > 0 or coach.done[1]:
                pulled += 1
                if coach.benched_until[1] > 0:
                    returns.append(coach.benched_until[1])
        self.assertAlmostEqual(pulled / 4000, (.6772 - .184) / (1 - .184), delta=.03)
        self.assertGreater(statistics.median(returns), 400.0 + 300.0)
        self.assertLess(statistics.median(returns), 400.0 + 700.0)
        coach = self._coach()
        coach.on_foul(2, 6, 3, 2000.0)
        self.assertTrue(coach.done[2])

    def test_third_foul_before_half_sits_to_halftime(self):
        sat = []
        for k in range(300):
            coach = self._coach()
            coach.rng = random.Random(k)
            coach.on_foul(3, 3, 2, 1100.0)
            if coach.benched_until[3] > 0:
                sat.append(coach.benched_until[3])
        self.assertTrue(sat)
        self.assertTrue(all(t >= 1440.0 for t in sat))      # a starter's typical return: the start of the 3rd

    def test_hot_and_cold_hands_move_the_plan(self):
        coach = self._coach()
        coach.team.secs[0] = 900.0
        base = coach.plan[0]
        coach.heat[0] = -6.0
        cold = coach.plan_now(0)
        coach.heat[0] = 6.0
        hot = coach.plan_now(0)
        self.assertLess(cold, base)
        self.assertGreater(hot, base)
        self.assertGreater(base - cold, hot - base)          # the real response is mostly on the cold side

    def test_spot_players_and_replay_faithful(self):
        generated = self._coach()
        self.assertTrue(generated.spot[9] is False)            # a reserve is not a spot player; a 10-minute man is not
        self.assertTrue(generated.reserve[9])
        tiny = self._coach(plans=[2160, 2040, 1920, 1800, 1680, 1440, 1200, 900, 600, 200])
        self.assertTrue(tiny.spot[9])
        replay = self._coach(plans=[2160, 2040, 1920, 1800, 1680, 1440, 1200, 900, 600, 200], replay=True)
        self.assertFalse(replay.spot[9])                       # replayed games keep every real player's minutes


class CoachGamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        cls.context["indices"] = sim.build_sim_indices(cls.context)
        games = [g for g in cls.context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")]
        cls.ids = [str(g["externalGameId"]) for g in sorted(games, key=lambda g: str(g["externalGameId"]))][::41][:30]

    def _play(self, gid, mode, seed=1):
        return to_plain(sim.sim_game_with_context(self.context, gid, mode=mode, seed=seed, engine="stage2"))

    def test_box_score_accounting(self):
        for mode in ("replay-real-minutes", "sandbox-sim"):
            for gid in self.ids[:12]:
                r = self._play(gid, mode)
                ot = r["notes"].count("Overtime") and int(r["notes"].split("over ")[1].split()[0])
                for team_id in (r["home_team_id"], r["away_team_id"]):
                    lines = [x for x in r["player_lines"] if x["team_id"] == team_id]
                    self.assertAlmostEqual(sum(x["minutes"] for x in lines), 240.0 + 25.0 * ot, delta=.2)
                    self.assertEqual(sum(x["starter"] for x in lines), 5)
                    self.assertTrue(all(x["minutes"] <= 48.0 + 5.0 * ot + 1e-6 for x in lines))
                    self.assertTrue(all(x["personal_fouls"] <= 6 for x in lines))
                    self.assertTrue(all("screen_assists" in x for x in lines))
                    tl = next(t for t in r["team_lines"] if t["team_id"] == team_id)
                    fgm = sum(x["fgm"] for x in lines)
                    self.assertLessEqual(sum(x["screen_assists"] for x in lines), fgm)
                    self.assertEqual(tl["points"], sum(x["points"] for x in lines))

    def test_determinism(self):
        for mode in ("replay-real-minutes", "sandbox-sim"):
            a = self._play(self.ids[3], mode, seed=7)
            b = self._play(self.ids[3], mode, seed=7)
            self.assertEqual(json.dumps(a, sort_keys=True, default=str), json.dumps(b, sort_keys=True, default=str))

    def test_replayed_minutes_follow_the_real_ones(self):
        dev = []
        for gid in self.ids:
            context = self.context
            game = context["indices"]["schedule_by_game_id"][gid]
            r = self._play(gid, "replay-real-minutes")
            if "Overtime" in r["notes"]:
                continue
            for team_key in ("homeTeamId", "awayTeamId"):
                team = context["indices"]["teams_by_espn_id"][str(game[team_key])]
                pool = sim.game_player_pool(context, gid, team, "replay-real-minutes", game_date=game.get("gameDate"))
                plan = {item["player"]["id"]: float(item["minutes"]) for item in pool}
                for x in r["player_lines"]:
                    if x["player_id"] in plan:
                        dev.append(abs(x["minutes"] - plan[x["player_id"]]))
        self.assertLess(statistics.mean(dev), 3.5)

    def test_old_rotation_still_selectable(self):
        game = self.context["indices"]["schedule_by_game_id"][self.ids[0]]
        teams = self.context["indices"]["teams_by_espn_id"]
        home, away = teams[str(game["homeTeamId"])], teams[str(game["awayTeamId"])]
        pools = [sim.game_player_pool(self.context, self.ids[0], t, "replay-real-minutes", game_date=game.get("gameDate"))
                 for t in (home, away)]
        g, _ = E.play_stage2_game(self.context, game, home, away, *pools, game_id=self.ids[0],
                                  mode="replay-real-minutes", seed=1, loop={"coach": 0.0, "screens": 0.0})
        self.assertFalse(g.use_coach)
        self.assertFalse(g.use_screens)
        regulation = 2880.0 * 5 + 300.0 * 5 * max(0, g.period - 4)
        self.assertAlmostEqual(sum(g.home.secs), regulation, delta=1.0)

    def test_switches_happen_at_about_the_league_rate(self):
        counts = [0] * 5
        game_ = self.context["indices"]["schedule_by_game_id"]
        teams = self.context["indices"]["teams_by_espn_id"]
        for gid in self.ids:
            game = game_[gid]
            home, away = teams[str(game["homeTeamId"])], teams[str(game["awayTeamId"])]
            pools = [sim.game_player_pool(self.context, gid, t, "replay-real-minutes", game_date=game.get("gameDate"))
                     for t in (home, away)]
            g, _ = E.play_stage2_game(self.context, game, home, away, *pools, game_id=gid, mode="replay-real-minutes",
                                      seed=1)
            for k in range(5):
                counts[k] += g.cov_count[k]
        total = sum(counts)
        self.assertGreater(total, 30 * 40)
        self.assertGreater(counts[SC.SWITCH] / total, .18)       # real 25.9% of ball screens
        self.assertLess(counts[SC.SWITCH] / total, .34)
        self.assertGreater(counts[SC.DROP] / total, counts[SC.BLITZ] / total)


class ScreenRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = dict(league_flat_inputs(ROOT)[GENERIC])

    def test_coverage_probabilities(self):
        handler = _card(self.base)
        small = _card(self.base, P01=193, P02=201)
        small2 = _card(self.base, P01=196, P02=203)
        big = _card(self.base, P01=213, P02=223, S36=80, S37=75, P03=285, S33=40, P07=40)
        probs = SC.coverage_probabilities(handler, small2, small, screener_is_big=False)
        self.assertAlmostEqual(sum(probs), 1.0, places=9)
        p_switch_small = probs[0]
        p_switch_big = SC.coverage_probabilities(handler, big, small, screener_is_big=True)[0]
        self.assertGreater(p_switch_small, p_switch_big)       # like-sized defenders on a guard screen switch more
        # A slow rim protector drops more than a mobile one; a pull-up shooter sees fewer drops.
        mobile = _card(self.base, P01=211, P02=218, S36=55, S37=55, S33=70, P07=62)
        drop_slow = SC.coverage_probabilities(handler, big, small, True)
        drop_mobile = SC.coverage_probabilities(handler, mobile, small, True)
        self.assertGreater(drop_slow[1] / (1 - drop_slow[0]), drop_mobile[1] / (1 - drop_mobile[0]))
        shooter = _card(self.base, S02=90, **{"T03.pull_up": .6})
        drop_shooter = SC.coverage_probabilities(shooter, big, small, True)
        self.assertLess(drop_shooter[1] / (1 - drop_shooter[0]), drop_slow[1] / (1 - drop_slow[0]))
        # Stars draw more traps.
        self.assertGreater(SC.coverage_probabilities(handler, big, small, True, star=2.0)[3],
                           SC.coverage_probabilities(handler, big, small, True, star=0.0)[3])

    def test_screen_edge_and_cards(self):
        screener = _card(self.base, S27=85, P08=75, P09=70, P04=120)
        weak = _card(self.base, S27=35, P08=40, P09=45, P04=85)
        navigator = _card(self.base, S35=50, P07=50, S41=50, S44=50)
        self.assertGreater(SC.screen_edge(screener, navigator), SC.screen_edge(weak, navigator))
        roller = _card(self.base, **{"T11.roll": .6, "T11.slip": .1, "T09": .1})
        cutter = _card(self.base, **{"T11.roll": .05, "T11.slip": .0, "T09": .6})
        self.assertGreater(roller.roll_share, cutter.roll_share)
        self.assertGreater(screener.scr_w, weak.scr_w)


if __name__ == "__main__":
    unittest.main()
