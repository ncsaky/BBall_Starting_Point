"""S2-USAGE: who takes the shots in Stage 2 (assister weights, putbacks by reach, heaves and must-have threes by three
habit, the roll-by-screening switch, the research shot trace).

Stage 2 stays off in normal gameplay; these tests drive it directly."""
import math
import unittest
from pathlib import Path

from nba_gm_data import sim
from nba_gm_data.box_rates import ASSISTS_INPUTS
from nba_gm_data.stage2 import cards as C
from nba_gm_data.stage2 import game as G
from nba_gm_data.stage2.game_contexts import GENERIC, league_flat_inputs

ROOT = Path(__file__).resolve().parents[1]


class Stage2UsageCardsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flats = {k: v for k, v in league_flat_inputs(ROOT).items() if k != GENERIC}
        cls.means = C.means_for(ROOT)

    def test_assist_rule_concentrates_on_playmakers(self):
        # The Stage 2 rule spreads its weights wider than today's per-36 rule (a share among four teammates).
        stage2 = sorted(C.log_linear(C.ASSISTS, f) for f in self.flats.values())
        today = sorted(C.log_linear(ASSISTS_INPUTS, f) for f in self.flats.values())
        q = len(stage2) // 10
        spread = lambda v: sum(v[-q:]) / q - sum(v[:q]) / q  # noqa: E731
        self.assertGreater(spread(stage2), 1.3 * spread(today))
        # ... and ranks players the same way, on the same five inputs.
        self.assertEqual(set(C.ASSISTS), set(ASSISTS_INPUTS))
        self.assertTrue(all(C.ASSISTS[k] > 0 for k in C.ASSISTS if k != "constant"))

    def test_roll_by_screening_switch(self):
        self.assertEqual(C.MENU["roll_screen"], 0.0)   # off: the first menu
        rim_finish = C.KIND_INDEX["rim_finish"]
        scr = {pid: math.exp(C.log_linear(C.SCREEN_ASSISTS_INPUTS, f)) for pid, f in self.flats.items()}
        rare = min(scr, key=scr.get)
        often = max(scr, key=scr.get)
        off = {p: C.shot_menu(self.flats[p], self.means)[rim_finish] for p in (rare, often)}
        self.assertEqual(off[rare], C.shot_menu(self.flats[rare])[rim_finish])
        old = C.MENU["roll_screen"]
        try:
            C.MENU["roll_screen"] = 1.0
            on = {p: C.shot_menu(self.flats[p], self.means)[rim_finish] for p in (rare, often)}
        finally:
            C.MENU["roll_screen"] = old
        self.assertLess(on[rare], off[rare])       # a player who rarely screens gets fewer roll finishes
        self.assertGreater(on[often], off[often])  # a frequent screener more

    def test_card_reach_speed_three(self):
        cards = [C.build_card(p, p, f, self.means) for p, f in list(self.flats.items())[:200]]
        tall = max(cards, key=lambda c: c.flat["P03"])
        short = min(cards, key=lambda c: c.flat["P03"])
        self.assertGreater(tall.reach, 0.0)
        self.assertLess(short.reach, 0.0)
        for c in cards:
            self.assertGreaterEqual(c.three, 0.0)
            self.assertLessEqual(c.three, 1.0)


class Stage2UsageGamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        ids = sim.validation_game_ids(cls.context, None, False)
        cls.ids = ids[:: max(1, len(ids) // 40)][:40]

    def _trace(self, loop: dict) -> tuple[dict, dict]:
        saved = {k: G.LOOP[k] for k in loop}
        G.LOOP.update(loop)
        G.SHOT_TRACE = {}
        orb = {}
        try:
            for gid in self.ids:
                res = sim.sim_game_with_context(self.context, gid, mode="replay-real-minutes", seed=11, engine="stage2")
                for ln in res.player_lines:
                    orb[ln["player_id"]] = orb.get(ln["player_id"], 0) + ln["offensive_rebounds"]
            return G.SHOT_TRACE, orb
        finally:
            G.SHOT_TRACE = None
            G.LOOP.update(saved)

    def test_shot_trace_is_off_in_play(self):
        self.assertIsNone(G.SHOT_TRACE)

    def test_putbacks_go_to_long_rebounders_and_heaves_to_shooters(self):
        flats = league_flat_inputs(ROOT)
        put, heave = C.KIND_INDEX["putback"], C.KIND_INDEX["heave"]

        def stats(trace, orb):
            pb = {"long": [0, 0], "short": [0, 0]}
            hv = [0, 0]   # heaves by low-three players (T02.three < .12), by everyone
            for pid, rows in trace.items():
                f = flats.get(pid)
                if f is None:
                    continue
                group = "long" if f["P03"] >= 275 else "short" if f["P03"] <= 255 else None
                if group:
                    pb[group][0] += rows[put][0]
                    pb[group][1] += orb.get(pid, 0)
                hv[1] += rows[heave][0]
                hv[0] += rows[heave][0] if f["T02.three"] < .12 else 0
            return {g: a / max(1, b) for g, (a, b) in pb.items()}, hv[0] / max(1, hv[1])

        self.assertEqual(G.LOOP["k_putback_reach"], 0.0)   # built but off by default (see the task file)
        self.assertEqual(G.LOOP["three_pick"], 1.0)
        now_pb, now_hv = stats(*self._trace({"k_putback_reach": 0.5}))
        old_pb, old_hv = stats(*self._trace({"k_putback_reach": 0.0, "three_pick": 0.0}))
        # Switched on, long-armed players put back a larger share of their offensive rebounds, short ones a smaller one.
        self.assertGreater(now_pb["long"] - now_pb["short"], old_pb["long"] - old_pb["short"])
        self.assertGreater(now_pb["long"], now_pb["short"])
        # Heaves leave the non-shooters.
        self.assertLessEqual(now_hv, old_hv)


if __name__ == "__main__":
    unittest.main()
