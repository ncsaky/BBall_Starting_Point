"""S2-TOTALS-MATCHUPS: Stage 2 game totals (both fives' pace, recent form, last-shot play) and player-on-player
matchups (who guards whom, the defender's skills on each shot, foul and turnover).

Light: card-level and rule-level checks plus a handful of replayed games. Normal gameplay never selects Stage 2."""
import random
import unittest
from pathlib import Path

from nba_gm_data import sim
from nba_gm_data.schema import to_plain
from nba_gm_data.stage2 import cards as C
from nba_gm_data.stage2 import game as G
from nba_gm_data.stage2 import matchups as M
from nba_gm_data.stage2.game_contexts import GENERIC, league_flat_inputs

ROOT = Path(__file__).resolve().parents[1]


def _card(base, **over):
    flat = dict(base)
    flat.update(over)
    return C.build_card(str(sorted(over.items())), "x", flat, C.means_for(ROOT))


class MatchupRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flats = league_flat_inputs(ROOT)
        cls.base = dict(cls.flats[GENERIC])

    def test_size_matches_size(self):
        off = [_card(self.base, P01=h, P02=h + 8) for h in (185, 193, 201, 208, 213)]
        de = [_card(self.base, P01=h, P02=h + 8) for h in (213, 186, 207, 194, 200)]
        d_of = M.assign(off, de, w={"w_size": 1.0, "w_star": 0.0, "w_hide": 0.0})
        self.assertEqual(sorted(d_of), [0, 1, 2, 3, 4])
        for i, j in enumerate(d_of):
            self.assertLess(abs(off[i].height - de[j].height), 4.0)

    def test_stopper_takes_the_top_scorer(self):
        # Five same-size scorers; one ends far more possessions. Five same-size defenders; one is the best stopper.
        off = [_card(self.base, T08=.75 if i == 2 else .25, **{"T01.shoot": .3 + .01 * i}) for i in range(5)]
        de = [_card(self.base, S33=90 if j == 3 else 45, S34=80 if j == 3 else 50, S41=80 if j == 3 else 50,
                    P07=60 if j == 3 else 52, S44=50 + j * .01) for j in range(5)]
        self.assertGreater(off[2].usage, max(c.usage for k, c in enumerate(off) if k != 2))
        d_of = M.assign(off, de)
        self.assertEqual(d_of[2], 3)
        # A coach who does not match up (scale 0) leaves it to size alone (all equal here: any pairing).
        self.assertEqual(sorted(M.assign(off, de, coach_scale=0.0)), [0, 1, 2, 3, 4])

    def test_defender_indices_follow_skills(self):
        lo = _card(self.base, S40=35, P07=45, S44=40)
        hi = _card(self.base, S40=75, P07=60, S44=70)
        self.assertGreater(hi.closeout_d, lo.closeout_d)
        slow = _card(self.base, P05=45, S16=40, S19=40)
        quick = _card(self.base, P05=60, S16=75, S19=75)
        self.assertGreater(quick.burst, slow.burst)
        self.assertGreater(_card(self.base, P09=62).to_logit, _card(self.base, P09=62).to_logit - 1)  # sanity
        # Balance protects the ball (refit turnover rule).
        self.assertLess(_card(self.base, P09=62).to_logit, _card(self.base, P09=40).to_logit)

    def test_drive_beat_chance_and_fouls(self):
        # In a lineup, a quick driver against a slow container is past his man more often, and that draws fouls.
        L = dict(G.LOOP)
        b0, kb = L["beat0"], L["k_beat"]
        quick = _card(self.base, P05=62, S16=80, S19=80)
        slow_d = _card(self.base, S33=25, S34=30, S41=30, P07=42)
        good_d = _card(self.base, S33=85, S34=75, S41=75, P07=62)
        p_vs_slow = G._sig(b0 + kb * (quick.burst - slow_d.contain_d))
        p_vs_good = G._sig(b0 + kb * (quick.burst - good_d.contain_d))
        self.assertGreater(p_vs_slow, p_vs_good + .2)
        self.assertGreater(L["k_beat_foul"], 0)
        self.assertGreater(L["craft_drive"], L["craft_finish"])
        self.assertGreater(L["foul_drive"], L["foul_roll_cut"])


class TotalsAndMatchupGamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        ids = sim.validation_game_ids(cls.context, None, False)
        cls.ids = ids[:: max(1, len(ids) // 10)][:10]

    def _play(self, gid, seed=5, **loop):
        saved = dict(G.LOOP)
        try:
            G.LOOP.update(loop)
            return to_plain(sim.sim_game_with_context(self.context, gid, mode="replay-real-minutes", seed=seed, engine="stage2"))
        finally:
            G.LOOP.clear()
            G.LOOP.update(saved)

    def test_matchups_on_and_off_both_play(self):
        for gid in self.ids[:4]:
            on = self._play(gid)
            off = self._play(gid, matchups=0.0)
            for res in (on, off):
                self.assertGreater(res["home_score"], 60)
                self.assertNotEqual(res["home_score"], res["away_score"])
            self.assertEqual(self._play(gid), on)    # deterministic

    def test_both_fives_set_the_pace(self):
        # Doubling both pace weights spreads the possession count across games; zero weights narrow it.
        # 2026-11-21 (RATINGS-FT-TOV): each game's possessions are averaged over six seeds before the spread across games
        # is taken. Two seeds per game left the comparison to chance (a new inputs file flipped it: seeds 1-2 gave 4.7
        # vs 8.8, seeds 3-4 4.7 vs 2.7, seeds 1-12 pooled 5.1 vs 5.2); per-game means over six seeds separate cleanly
        # (wide 3.6-3.9 vs narrow 1.7-2.2 on three different seed sets).
        def spread(**loop):
            vals = []
            for gid in self.ids:
                runs = [self._play(gid, seed=s, **loop)["possessions"] for s in range(1, 7)]
                vals.append(sum(runs) / len(runs))
            m = sum(vals) / len(vals)
            return (sum((v - m) ** 2 for v in vals) / len(vals)) ** .5, m
        wide, m_wide = spread(k_pace=4.0, k_pace_def=4.0)
        narrow, m_narrow = spread(k_pace=0.0, k_pace_def=0.0)
        self.assertGreater(wide, narrow)
        self.assertLess(abs(m_wide - m_narrow), 6.0)

    def test_trace_is_off_in_play(self):
        self.assertIsNone(G.TRACE)

    def test_recent_form_is_todays_term(self):
        # The recent-form term is today's engine's own (sim.game_environment_effect) at today's strength.
        self.assertEqual(G.LOOP["k_form_off"], 1.0)
        self.assertEqual(G.LOOP["k_form_pace"], 1.0)
        a = self._play(self.ids[5])
        b = self._play(self.ids[5], k_form_off=0.0, k_form_pace=0.0)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
