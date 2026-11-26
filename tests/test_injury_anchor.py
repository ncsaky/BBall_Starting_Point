"""INJURY-ANCHOR: the injury model's base rates and recovery lengths come from the complete public records."""
import json
from pathlib import Path
import unittest

from nba_gm_data import injury_model as im

ROOT = Path(__file__).resolve().parents[1]


def stretch(player, team, first, last, games, part="knee", side="left", category="injury", management=False,
            opener=False, regular=None, dates=None):
    return {"player_id": player, "player": player, "team": team, "reason_category": category, "body_part": part,
            "side": side, "reported_body_parts": [], "diagnoses": ["Sprain"],
            "sources": [{"date": d, "phase": "regular"} for d in (dates or [first, last])],
            "first_game_missed": first, "last_game_missed": last, "games_missed": games,
            "regular_season_games_missed": games if regular is None else regular,
            "at_team_season_start": opener, "injury_management_only": management}


# The team's schedule comes from the games its players missed: a G League player is out for all of them.
SCHEDULE = ["2025-10-22", "2025-10-24", "2025-10-26", "2025-10-28", "2025-10-30", "2025-11-01", "2025-11-03"]


class CompleteRecordTests(unittest.TestCase):
    def rows(self):
        return [
            stretch("g", "BOS", SCHEDULE[0], SCHEDULE[-1], 7, part=None, category="g_league", dates=SCHEDULE),
            stretch("g", "NYK", SCHEDULE[0], SCHEDULE[-1], 7, part=None, category="g_league", dates=SCHEDULE),
            stretch("new", "BOS", SCHEDULE[1], SCHEDULE[2], 2, part="ankle"),
            # A knee stretch, then straight into a back stretch with no game played: one absence.
            stretch("chain", "BOS", SCHEDULE[1], SCHEDULE[2], 2, part="knee"),
            stretch("chain", "BOS", SCHEDULE[3], SCHEDULE[4], 2, part="back"),
            # Out again after playing on Oct 30: a new absence, still out at the team's last game.
            stretch("again", "BOS", SCHEDULE[1], SCHEDULE[1], 1, part="hip"),
            stretch("again", "BOS", SCHEDULE[5], SCHEDULE[6], 2, part="hip"),
            stretch("manage", "BOS", SCHEDULE[2], SCHEDULE[2], 1, management=True),
            stretch("opener", "BOS", SCHEDULE[0], SCHEDULE[1], 2, opener=True),
            stretch("traded", "BOS", SCHEDULE[0], SCHEDULE[1], 2, part="calf"),
            stretch("traded", "NYK", SCHEDULE[3], SCHEDULE[4], 2, part="calf"),
            stretch("sick", "NYK", SCHEDULE[2], SCHEDULE[2], 1, part=None, category="illness"),
            stretch("nopart", "NYK", SCHEDULE[2], SCHEDULE[2], 1, part=None),
            stretch("playoffs", "NYK", SCHEDULE[2], SCHEDULE[2], 1, regular=0),
        ]

    def test_new_in_season(self):
        from scripts.build_injury_model import new_in_season
        rows = self.rows()
        new = {(rows[i]["player_id"], rows[i]["first_game_missed"]): part for i, part in new_in_season(rows).items()}
        self.assertEqual(new, {
            ("new", SCHEDULE[1]): "ankle", ("chain", SCHEDULE[1]): "knee", ("again", SCHEDULE[1]): "hip",
            ("again", SCHEDULE[5]): "hip", ("traded", SCHEDULE[0]): "calf", ("sick", SCHEDULE[2]): "illness",
            ("nopart", SCHEDULE[2]): None})

    def test_absence_lengths_join_continuations_and_mark_season_end(self):
        from scripts.build_injury_model import absence_lengths, new_in_season
        rows = self.rows()
        new = new_in_season(rows)
        lengths = {(rows[i]["player_id"], rows[i]["first_game_missed"]): v for i, v in absence_lengths(rows, new).items()}
        self.assertEqual(lengths[("chain", SCHEDULE[1])], (4, 4, False))
        self.assertEqual(lengths[("again", SCHEDULE[1])], (1, 1, False))
        self.assertEqual(lengths[("again", SCHEDULE[5])], (2, 2, True))

    def test_kaplan_meier_counts_a_season_end_absence_as_at_least_that_long(self):
        from scripts.build_injury_model import km_band_shares
        self.assertEqual([round(v, 6) for v in km_band_shares([(1, False), (3, False), (8, False), (30, False)])],
                         [0.25, 0.25, 0.25, 0.0, 0.25])
        # Two absences cut off by the end of the season after 3 games: neither counts as a 2-5 game absence.
        shares = km_band_shares([(1, False), (1, False), (3, True), (3, True)])
        self.assertAlmostEqual(shares[0], 0.5)
        self.assertAlmostEqual(shares[1], 0.0)
        self.assertAlmostEqual(sum(shares), 1.0)

    def test_recovery_correction_matches_the_complete_mix_and_keeps_the_game_share(self):
        from scripts.build_injury_model import correct_recovery_lengths
        pool = {"head": [{"days": 1, "w": 1.0}, {"days": 2, "w": 1.0}, {"days": 4, "w": 1.0}, {"days": 4, "w": 1.0},
                         {"days": 30, "w": 1.0}, {"days": 60, "w": 1.0}]}
        lengths = {"head": [(1, False)] * 6 + [(2, False)] * 2 + [(15, False)] * 1 + [(30, False)] * 1}
        report = correct_recovery_lengths(pool, lengths, {"head": 10})
        costing = [e for e in pool["head"] if e["days"] >= 2]
        total = sum(e["w"] for e in costing)
        self.assertAlmostEqual(total, 5.0, places=4)          # the share of draws costing a game is unchanged
        self.assertEqual(pool["head"][0]["w"], 1.0)          # the one-day (no game) entry is untouched
        one_game = sum(e["w"] for e in costing if e["days"] // 2 == 1) / total
        self.assertAlmostEqual(one_game, 0.6, places=4)
        self.assertEqual(report["head"][0][0], 0.6)


class ModelFileTests(unittest.TestCase):
    def test_model_is_anchored_to_the_complete_records(self):
        model = json.loads((ROOT / im.MODEL_FILE).read_text())
        fit = model["rate_fit"]
        self.assertEqual(fit["anchor_seasons"], ["2023-24", "2024-25", "2025-26"])
        self.assertFalse(fit["illness_in_history"])
        self.assertEqual(fit["history_weight"], im.HISTORY_WEIGHT)
        per_1000 = sum(info["anchor_per_1000_games"] for info in model["parts"].values())
        # 47-49 new in-season injuries and illnesses per 1,000 games in the three seasons (one per absence).
        self.assertTrue(45.0 < per_1000 < 52.0, per_1000)
        for info in model["parts"].values():
            self.assertTrue(0.75 < info["game_share"] <= 1.0)

    def test_drawn_lengths_match_the_complete_records_mix(self):
        from scripts.build_injury_model import RECOVERY_GROUPS, band_index
        model = json.loads((ROOT / im.MODEL_FILE).read_text())
        bands = model["rate_fit"]["recovery_length_bands"]
        for group in ("ankle/foot/toe", "knee"):
            self.assertGreater(bands[group]["complete"][0], bands[group]["tracker_pool"][0])
        # What the engine draws, diagnosis by diagnosis, still has the complete records' mix of absence lengths.
        for group, row in bands.items():
            mix = [0.0] * 5
            parts = [p for p in model["recovery_summary"] if RECOVERY_GROUPS.get(p) == group]
            weights = {p: model["parts"][p]["anchor_per_1000_games"] for p in parts}
            for part in parts:
                costing = [(days, w) for days, w in im.recovery_days(model["recovery_summary"][part]) if days >= 2]
                total = sum(w for _, w in costing)
                for days, w in costing:
                    mix[band_index(days // 2)] += weights[part] / sum(weights.values()) * w / total
            for drawn, complete in zip(mix, row["complete"]):
                self.assertAlmostEqual(drawn, complete, delta=0.025, msg=(group, mix, row["complete"]))


if __name__ == "__main__":
    unittest.main()
