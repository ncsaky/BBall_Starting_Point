"""One OVR / OFF / DEF display scale everywhere (OVERALL-SCALE, user decision 2026-11-21).

The card, the tables and every list show the same number for a player: a straight line in the engine's fitted impact
(the value the AI orders players by), with 90+ rare, most rotation players in the 70s and 80s and the end of the bench
in the high 60s. The AI keeps reading its own summary; this is display only.
"""
import json
import unittest
from pathlib import Path

from nba_gm_data import player_profile as pp
from nba_gm_data import ratings_model as rm
from nba_gm_data.impact_value import DISPLAY_LINES
from nba_gm_data.save import (display_rating_from_summary, display_rating_to_summary, player_attribute_summary,
                              player_display_attribute_summary, player_engine_attribute_summary,
                              presentation_rating_value)

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / rm.INPUTS_FILE
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
NAMED = ("Nikola Jokić", "Shai Gilgeous-Alexander", "Victor Wembanyama", "Luka Dončić", "Giannis Antetokounmpo",
         "Stephen Curry", "Rudy Gobert", "Anthony Edwards", "Derrick White", "Jalen Brunson")


def bands(values):
    out = {"90+": 0, "80-89": 0, "70-79": 0, "60-69": 0, "<60": 0}
    for v in values:
        out["90+" if v >= 90 else "80-89" if v >= 80 else "70-79" if v >= 70 else "60-69" if v >= 60 else "<60"] += 1
    return out


@unittest.skipUnless((INPUTS.exists() or INPUTS.with_name(INPUTS.name + ".gz").exists()) and UNIVERSE.exists(),
                     "player inputs file not built yet")
class OverallScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.active = json.loads(UNIVERSE.read_text())
        rm.install_inputs_model(cls.active, ROOT)
        cls.active["_allow_internal_caches"] = True
        cls.players = [p for p in cls.active["players"] if rm.effective_inputs(cls.active, p["id"]) is not None]
        cls.shown = {p["id"]: player_display_attribute_summary(cls.active, p["id"]) for p in cls.players}
        cls.summary = {p["id"]: player_attribute_summary(cls.active, p["id"]) for p in cls.players}
        cls.by_name = {p["name"]: p["id"] for p in cls.players}
        by_team = {}
        for p in cls.players:
            by_team.setdefault(p.get("team_id"), []).append(p)
        cls.rotation = [p["id"] for team in by_team.values()
                        for p in sorted(team, key=lambda p: -float(p.get("minutes_projection") or 0))[:9]]

    def test_card_and_tables_show_the_same_numbers(self):
        sample = [self.by_name[n] for n in NAMED] + [p["id"] for p in self.players[::37]]
        for pid in sample:
            header = pp.player_profile(self.active, pid)["header"]
            shown = self.shown[pid]
            self.assertEqual((header["ovr"], header["off"], header["def"]),
                             (shown["overall"], shown["offense"], shown["defense"]), pid)

    def test_scale_is_a_straight_line_in_the_engines_value(self):
        """Equal value gaps give equal rating gaps, anywhere on the scale (both numbers are rounded)."""
        heads = {pid: pp.engine_header(self.active, pid) for pid in [p["id"] for p in self.players[::11]]}
        for key, side in (("ovr", "overall"), ("off", "offense"), ("def", "defense")):
            a, b = DISPLAY_LINES[side]
            pairs = sorted((h["impact"][key], h[key]) for h in heads.values())
            for (x0, y0), (x1, y1) in zip(pairs, pairs[1:]):
                self.assertAlmostEqual(y1 - y0, b * (x1 - x0), delta=0.11 + 0.01 * b, msg=side)

    def test_order_matches_the_ai(self):
        """The AI's summary is a rank mapping of the same value, so a player it rates higher never shows lower."""
        for key in ("overall", "offense", "defense"):
            rows = sorted(self.players, key=lambda p: self.summary[p["id"]][key])
            for lo, hi in zip(rows, rows[1:]):
                if self.summary[hi["id"]][key] > self.summary[lo["id"]][key] + 1e-9:
                    self.assertGreaterEqual(self.shown[hi["id"]][key], self.shown[lo["id"]][key], key)

    def test_bands_match_the_users_scale(self):
        overall = [s["overall"] for s in self.shown.values()]
        everyone, rotation = bands(overall), bands(self.shown[pid]["overall"] for pid in self.rotation)
        self.assertTrue(3 <= everyone["90+"] <= 8, everyone)                       # a handful, MVP tier
        self.assertEqual(everyone["<60"], 0, everyone)                             # the tail stops in the 60s
        self.assertGreater(everyone["60-69"], 0, everyone)
        in_70s_80s = rotation["70-79"] + rotation["80-89"]
        self.assertGreaterEqual(in_70s_80s / len(self.rotation), 0.85, rotation)   # most rotation players
        self.assertGreaterEqual(rotation["80-89"] / len(self.rotation), 0.12, rotation)
        self.assertLessEqual(rotation["60-69"] / len(self.rotation), 0.08, rotation)  # only a little into the 60s
        self.assertLess(max(overall), 100)
        for side in ("offense", "defense"):
            values = [s[side] for s in self.shown.values()]
            side_rotation = bands(self.shown[pid][side] for pid in self.rotation)
            self.assertTrue(2 <= bands(values)["90+"] <= 12, (side, bands(values)))
            self.assertGreaterEqual((side_rotation["70-79"] + side_rotation["80-89"]) / len(self.rotation), 0.8, side)

    def test_ninety_plus_is_the_analysts_top_tier(self):
        elite = {pid for pid, s in self.shown.items() if s["overall"] >= 90}
        for name in ("Nikola Jokić", "Shai Gilgeous-Alexander", "Victor Wembanyama", "Luka Dončić"):
            self.assertIn(self.by_name[name], elite, name)

    def test_overall_is_offense_plus_half_defense(self):
        """Overall value is offensive plus defensive value; the DEF line is twice as steep, so OVR = OFF + DEF/2 - c."""
        (ao, bo), (af, bf), (ad, bd) = DISPLAY_LINES["overall"], DISPLAY_LINES["offense"], DISPLAY_LINES["defense"]
        constant = ao - af * bo / bf - ad * bo / bd
        for s in self.shown.values():
            self.assertAlmostEqual(s["overall"], s["offense"] * bo / bf + s["defense"] * bo / bd + constant, delta=0.16)

    def test_summary_scale_numbers_convert_onto_the_same_scale(self):
        """Potentials and ceilings exist only on the AI's scale: they convert through the same value, monotonically,
        without a cap, and a typed display threshold converts back."""
        jokic = self.by_name["Nikola Jokić"]
        self.assertAlmostEqual(display_rating_from_summary(self.active, "overall", self.summary[jokic]["overall"]),
                               self.shown[jokic]["overall"], delta=0.2)
        ladder = [display_rating_from_summary(self.active, "overall", v) for v in range(30, 101, 5)]
        self.assertEqual(ladder, sorted(ladder))
        self.assertGreater(ladder[-1], 100)                                        # no clipping at the top
        for value in (65.0, 72.5, 80.0, 91.0):
            back = display_rating_from_summary(self.active, "overall", display_rating_to_summary(self.active, "overall", value))
            self.assertAlmostEqual(back, value, delta=0.11)

    def test_ai_matching_keeps_the_ai_scale(self):
        from nba_gm_data.trade_wants import player_facts
        pid = self.by_name["Stephen Curry"]
        player = next(p for p in self.players if p["id"] == pid)
        facts = player_facts(self.active, player)
        self.assertEqual(facts["overall"], presentation_rating_value(self.summary[pid]["overall"]))
        self.assertEqual(player_engine_attribute_summary(self.active, pid)["defense"],
                         presentation_rating_value(self.summary[pid]["defense"]))

    def test_trade_want_thresholds_show_on_the_display_scale(self):
        from nba_gm_data.app_actions import wants_for_display, wants_from_display
        stored = {"entries": [{"id": "w", "kind": "player", "positions": [],
                               "conditions": [{"field": "overall", "op": ">=", "value": 56.0},
                                              {"field": "age", "op": "<=", "value": 24}]}], "suggestions": []}
        shown = wants_for_display(self.active, stored)
        self.assertEqual(stored["entries"][0]["conditions"][0]["value"], 56.0)   # a copy; the stored want is untouched
        typed = shown["entries"][0]["conditions"][0]["value"]
        self.assertEqual(typed, display_rating_from_summary(self.active, "overall", 56.0))
        self.assertEqual(shown["entries"][0]["conditions"][1]["value"], 24)
        # Re-saving an unchanged threshold keeps the stored value exactly; a new one converts back closely.
        self.assertEqual(wants_from_display(self.active, shown["entries"], stored["entries"])[0]["conditions"][0]["value"], 56.0)
        back = wants_from_display(self.active, shown["entries"])[0]["conditions"][0]["value"]
        self.assertAlmostEqual(back, 56.0, delta=0.25)


if __name__ == "__main__":
    unittest.main()
