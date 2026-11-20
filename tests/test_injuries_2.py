"""INJURIES-2: real opening-night injuries for a new career, injury lengths counted in games the way Basketball Index
counts them, and the research measures behind them."""
from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
import zlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/research"))

from nba_gm_data import health, injury_model as im  # noqa: E402
from nba_gm_data import save as sv  # noqa: E402

import injury_lengths as il  # noqa: E402
import opening_night_injuries as oni  # noqa: E402

LIST = json.loads((ROOT / "data/canonical/opening_night_injuries_2026_27.json").read_text())


class OpeningNightListTests(unittest.TestCase):
    def test_list_shape_and_sources(self):
        self.assertEqual(LIST["season"], "2026-27")
        rows = LIST["injuries"]
        self.assertGreater(len(rows), 30)
        for row in rows:
            self.assertGreaterEqual(row["games_missed"], 1, row["name"])
            self.assertLessEqual(row["games_missed"], 82, row["name"])
            self.assertTrue(row["sources"], row["name"])
            self.assertTrue(str(row["opener_reason"]).startswith("Injury/Illness"), row["name"])
            self.assertIn(row["body_part"], im.PART_LABELS, row["name"])
            if row["apply"]:
                self.assertTrue(row["player_id"], row["name"])
            else:
                self.assertTrue(row["skip_reason"], row["name"])
        # Rest, G League and personal reasons are kept apart and never applied.
        self.assertTrue(all(not oni.official_injury({"status": "Out", "reason": r["opener_reason"]})
                            or r["opener_status"] == "Available" for r in LIST["not_injuries"]))

    def test_reason_parsing(self):
        self.assertTrue(oni.official_injury({"status": "Out", "reason": "Injury/Illness - Left Calf; Strain"}))
        self.assertFalse(oni.official_injury({"status": "Available", "reason": "-"}))
        self.assertFalse(oni.official_injury({"status": "Out", "reason": "G League - Two-Way"}))
        self.assertFalse(oni.official_injury({"status": "Out", "reason": "Personal Reasons"}))
        self.assertEqual(oni.part_of("Right Soleus Strain"), "calf")
        self.assertEqual(oni.part_of("Right ACL Repair / Surgery"), "knee")
        self.assertEqual(oni.part_of("Right Achilles Tendon Rupture / Tear"), "achilles")
        self.assertEqual(oni.part_of("Gastrointestinal Illness"), "illness")
        self.assertEqual(oni.part_of("Right Lisfranc Surgery"), "foot")

    def test_official_report_pdf_rows(self):
        def cell(x, y, text):
            words = " ".join(f"({w}) Tj" for w in text.split())
            return f"{x} {y} 50 20 re\nW* n\nBT\n/F0 -10 Tf\n{words}\nET\n"
        content = (cell(19.1, 100.4, "Game Date") + cell(421.0, 100.4, "Player Name")
                   + cell(19.1, 121.7, "10/20/2026") + cell(260.2, 121.7, "Boston Celtics")
                   + cell(421.0, 121.7, "Carter, Devin") + cell(581.7, 121.7, "Out")
                   + cell(662.1, 121.7, "Injury/Illness - Illness")
                   + cell(421.0, 144.8, "Walsh, Jordan") + cell(581.7, 144.8, "Available") + cell(662.1, 144.8, "-"))
        body = zlib.compress(content.encode("latin-1"))
        pdf = b"%PDF-1.4\n1 0 obj\n<</Length " + str(len(body)).encode() + b"/Filter/FlateDecode>>\nstream\n" + body + b"\nendstream\nendobj\n"
        rows = oni.report_rows(pdf)
        self.assertEqual([(r["date"], r["team"], r["player"], r["status"]) for r in rows],
                         [("2026-10-20", "Boston Celtics", "Carter, Devin", "Out"),
                          ("2026-10-20", "Boston Celtics", "Walsh, Jordan", "Available")])
        self.assertTrue(oni.official_injury(rows[0]))
        self.assertFalse(oni.official_injury(rows[1]))


class NewCareerOpeningNightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from nba_gm_data.app_actions import load_app_canonical
        cls.canonical = load_app_canonical(ROOT)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.save = sv.create_league_save(ROOT, cls.canonical, "BOS", Path(cls.tmp.name) / "career.json", seed=11)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_list_applied_exactly(self):
        save = self.save
        schedule = save["season_schedules"]["2026-27"]["games"] if "season_schedules" in save else sv.schedule_for_save(ROOT, save)
        espn_to_team = health.espn_team_id_map_from_canonical(self.canonical)
        team_days = health._team_game_dates(schedule, espn_to_team)
        teams = {t["abbrev"]: t["id"] for t in self.canonical["teams"]}
        states = {s["player_id"]: s for s in save["health_states"]}
        events = {e["id"]: e for e in save["injury_events"]}
        applied = [r for r in LIST["injuries"] if r["apply"]]
        self.assertEqual(save["meta"]["opening_night_injuries"]["applied"], len(applied))
        for row in applied:
            state = states[row["player_id"]]
            self.assertEqual(state["availability_status"], "out", row["name"])
            days = team_days[teams[row["team"]]]
            games = min(row["games_missed"], len(days))
            expected = "2027-06-30" if games >= len(days) or row["season_ending"] else days[games]
            self.assertEqual(state["return_date"], expected, row["name"])
            # Out for exactly that many of his team's games.
            if expected != "2027-06-30":
                self.assertEqual(sum(1 for d in days if d < state["return_date"]), row["games_missed"], row["name"])
            event = events[state["current_injury_id"]]
            self.assertEqual(event["diagnosis"], row["diagnosis"])
            self.assertEqual(event["body_part"], row["body_part"])
            self.assertEqual(event["season_start"], "opening_night")
        skipped = {s["name"] for s in save["meta"]["opening_night_injuries"]["skipped"]}
        self.assertEqual(skipped, {r["name"] for r in LIST["injuries"] if not r["apply"]})

    def test_nobody_else_starts_hurt(self):
        hurt = {s["player_id"] for s in self.save["health_states"] if s.get("current_injury_id")
                or s.get("availability_status", "active") != "active"}
        self.assertEqual(hurt, {r["player_id"] for r in LIST["injuries"] if r["apply"]})
        names = {p["id"]: p["name"] for p in self.canonical["players"]}
        for star in ("Jayson Tatum", "Tyrese Haliburton"):      # both played on the real opening night
            pid = next(pid for pid, name in names.items() if name == star)
            self.assertNotIn(pid, hurt)

    def test_random_model_kept_for_later_seasons(self):
        self.assertIsNone(health.load_opening_night_list(ROOT, "2027-28"))
        schedule = sv.generate_future_schedule(ROOT, "2027-28", 2027)
        probe = {"health_states": [], "injury_events": [], "meta": {}}
        self.assertFalse(sv.apply_opening_night_injuries(ROOT, self.canonical, probe, schedule))
        self.assertEqual(probe["injury_events"], [])
        # The rollover still draws random offseason injuries (carried=False), unchanged.
        source = (ROOT / "src/nba_gm_data/save.py").read_text()
        self.assertIn("apply_season_start_injuries(root, canonical_with_save(canonical, save), save, generated, seed, carried=False)", source)


class InjuryLengthTests(unittest.TestCase):
    DAYS = ["2026-10-21", "2026-10-23", "2026-10-24", "2026-10-27", "2026-10-29", "2026-10-31"]

    def test_days_count_two_per_game_from_the_next_game(self):
        hurt = date(2026, 10, 21)
        self.assertEqual(health.injury_return_date(self.DAYS, hurt, 1), date(2026, 10, 23))   # no game missed
        self.assertEqual(health.injury_return_date(self.DAYS, hurt, 2), date(2026, 10, 24))   # misses 10-23
        self.assertEqual(health.injury_return_date(self.DAYS, hurt, 3), date(2026, 10, 24))
        self.assertEqual(health.injury_return_date(self.DAYS, hurt, 8), date(2026, 10, 31))   # misses four
        # Past the end of the schedule: two days per remaining game.
        self.assertEqual(health.injury_return_date(self.DAYS, hurt, 12), date(2026, 11, 4))   # 5 listed + 1 more
        self.assertEqual(health.injury_return_date([], hurt, 4), date(2026, 10, 27))

    def test_drawn_injury_uses_the_team_schedule(self):
        model = im.load_model(ROOT)
        player = {"id": "p1", "team_id": "team_x", "age": 27, "height_inches": 79, "weight_lbs": 215, "position": "SF"}
        for seed in range(400):
            rng = random.Random(seed)
            event = health.v2_injury_draw(ROOT, model, {"injury_events": []}, player, {}, {}, {}, 34.0,
                                          date(2026, 10, 21), {"injury_risk_multiplier": 40.0}, seed, rng, {}, [],
                                          team_days=self.DAYS)
            if event:
                games = int(event["expected_days_missed"]) // 2
                self.assertEqual(event["expected_games_missed"], games)
                self.assertEqual(event["return_date"],
                                 health.injury_return_date(self.DAYS, date(2026, 10, 21), event["expected_days_missed"]).isoformat())
                return
        self.fail("no injury drawn")

    def test_band_measures(self):
        self.assertEqual([il.band_of(g) for g in (1, 2, 5, 6, 10, 11, 20, 21, 82)],
                         ["1", "2-5", "2-5", "6-10", "6-10", "11-20", "11-20", "21+", "21+"])
        # One regular (30 minutes, 22 games) with a 1-game, a 3-game (rest-labelled games count only when injured)
        # and a 12-game absence between games he played.
        played = [1] * 3 + [0] + [1] * 3 + [0] * 3 + [1] * 3 + [0] * 12 + [1] * 13
        games = []
        for i, on in enumerate(played):
            games.append({"game": f"g{i:02d}", "date": f"2026-11-{i % 28 + 1:02d}" if i < 28 else f"2026-12-{i - 27:02d}",
                          "team": "AAA", "players": [["p", 30.0]] if on else [], "dnp": [],
                          "labels": {} if on else {"p": "INJURY"}})
        runs = il.spells(games, lambda label: True, lambda pid, labels, day: "knee")
        self.assertEqual(sorted(r["games"] for r in runs), [1, 3, 12])
        summary = il.summarize("t", runs, 1)
        self.assertEqual(summary["bands"]["1"], 33.3)
        self.assertEqual(summary["band_games"]["11-20"], 12.0)

    def test_event_view_counts_team_games(self):
        tgs = [{"team": "AAA", "date": d, "game": d, "players": []} for d in self.DAYS]
        events = [{"player_id": "p", "team_id": "team_aaa", "start_date": "2026-10-21", "return_date": "2026-10-29",
                   "body_part": "ankle", "status": "generated_injury_v2"},
                  {"player_id": "q", "team_id": "team_aaa", "start_date": "2026-10-27", "return_date": "2027-06-30",
                   "body_part": "knee", "status": "generated_injury_v2"}]
        runs = il.sim_event_spells(tgs, events)
        self.assertEqual([(r["games"], r["season_ending"]) for r in runs], [(3, False), (2, True)])

    def test_expected_games_use_two_days_per_game(self):
        path = str(ROOT / im.MODEL_FILE)
        quantiles = im.load_model(ROOT)["recovery_summary"]["ankle"]["quantiles"]
        expected = sum(int(round(im._days_at(quantiles, (k + 0.5) / 200.0))) // 2 for k in range(200)) / 200.0
        self.assertAlmostEqual(im._mean_games_out(path, "ankle"), expected)


if __name__ == "__main__":
    unittest.main()
