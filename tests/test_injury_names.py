"""INJURY-NAMES: an injury's name and its length agree, and the news reads naturally."""
import json
import random
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from nba_gm_data import health, injury_model as im  # noqa: E402
from nba_gm_data.save import merge_health_results  # noqa: E402
from scripts import build_injury_model as build  # noqa: E402

MODEL = json.loads((ROOT / im.MODEL_FILE).read_text())


def entry(days, label="ankle sprain", censored=0, w=1.0):
    return {"days": days, "label": label, "censored": censored, "w": w}


def diagnosis(part, label):
    return next(d for d in MODEL["recovery_summary"][part]["diagnoses"] if d["label"] == label)


class BuildTests(unittest.TestCase):
    def test_an_absence_cut_off_by_the_season_counts_toward_longer_ones_of_the_same_injury(self):
        pool = [entry(4, censored=1), entry(200), entry(300), entry(6), entry(400, censored=1)]
        out = build.count_season_end_absences(pool)
        self.assertAlmostEqual(sum(e["w"] for e in out), 5.0)
        self.assertNotIn(4, [e["days"] for e in out])
        # The 4-day record's weight goes to the four longer ones equally; the longest has nothing past it and stays.
        self.assertEqual({e["days"]: round(e["w"], 4) for e in out}, {6: 1.25, 200: 1.25, 300: 1.25, 400: 1.25})

    def test_each_diagnosis_keeps_its_share_inside_its_own_limits(self):
        recovery = {"knee": [entry(d, "knee soreness") for d in (2, 3, 4, 150)]
                    + [entry(d, "ACL tear") for d in (200, 260, 300)] + [entry(5, "ACL tear", censored=1)]
                    + [entry(20, "rib soreness")]}
        out = build.diagnosis_recovery(recovery)["knee"]
        by_label = {}
        for e in out:
            by_label.setdefault(e["label"], []).append(e)
        self.assertEqual(set(by_label), {"knee soreness", "ACL tear", "knee injury"})   # a rib record under the knee
        self.assertEqual(sorted(e["days"] for e in by_label["knee soreness"]), [2, 3, 4])
        self.assertEqual(min(e["days"] for e in by_label["ACL tear"]), 200)
        for label, share in (("knee soreness", 4.0), ("ACL tear", 4.0), ("knee injury", 1.0)):
            self.assertAlmostEqual(sum(e["w"] for e in by_label[label]), share, msg=label)

    def test_a_rare_diagnosis_borrows_its_kind_from_the_same_part_of_the_body(self):
        recovery = {"thumb": [entry(400, "thumb surgery recovery", censored=1)],
                    "hand": [entry(d, "hand surgery recovery") for d in (30, 40, 50)],
                    "knee": [entry(d, "knee surgery recovery") for d in (90, 200, 300)]}
        out = build.diagnosis_recovery(recovery)
        self.assertEqual(sorted({e["days"] for e in out["thumb"]}), [30, 40, 50])

    def test_names_read_naturally(self):
        self.assertEqual(build.part_diagnosis("ankle (unspecified)", "ankle"), "ankle injury")
        self.assertEqual(build.part_diagnosis("Achilles tendon (unspecified)", "achilles"), "Achilles injury")
        self.assertEqual(build.part_diagnosis("achilles injury", "achilles"), "Achilles injury")
        self.assertEqual(build.part_diagnosis("illness general", "illness"), "illness")
        self.assertEqual(build.part_diagnosis("labrum tear", "hip"), "labrum tear")


class ModelFileTests(unittest.TestCase):
    def test_every_diagnosis_stays_inside_the_limits_for_its_kind(self):
        self.assertEqual(set(MODEL["recovery_summary"]), {*build.PARTS, "illness"})
        for part, summary in MODEL["recovery_summary"].items():
            self.assertAlmostEqual(sum(d["share"] for d in summary["diagnoses"]), 1.0, places=3)
            for row in summary["diagnoses"]:
                low, high = build.KIND_DAYS[build.diagnosis_kind(row["label"], part)]
                self.assertGreaterEqual(row["quantiles"][0], low, (part, row["label"]))
                self.assertLessEqual(row["quantiles"][-1], high, (part, row["label"]))
                self.assertNotIn("unspecified", row["label"])

    def test_the_names_the_sim_showed_wrong_now_have_believable_lengths(self):
        games = {key: [days // 2 for days in diagnosis(*key)["quantiles"]]
                 for key in (("knee", "ACL tear"), ("achilles", "Achilles tendon rupture"), ("back", "back contusion"),
                             ("ankle", "ankle injury"), ("calf", "shin contusion"))}
        self.assertGreaterEqual(min(games["knee", "ACL tear"]), 90)
        self.assertGreaterEqual(min(games["achilles", "Achilles tendon rupture"]), 90)
        for key in (("back", "back contusion"), ("ankle", "ankle injury"), ("calf", "shin contusion")):
            self.assertLessEqual(max(games[key]), 20, key)

    def test_every_long_term_effect_still_matches_a_diagnosis(self):
        labels = {d["label"].lower() for s in MODEL["recovery_summary"].values() for d in s["diagnoses"]}
        for row in MODEL["lasting_effects"]:
            if row["level"] == "specific":
                self.assertIn(row["bucket"].lower(), labels)


class DrawTests(unittest.TestCase):
    def test_a_drawn_length_fits_the_drawn_name(self):
        rng = random.Random(11)
        for part, summary in MODEL["recovery_summary"].items():
            ranges = {d["label"]: (d["quantiles"][0], d["quantiles"][-1]) for d in summary["diagnoses"]}
            for _ in range(2000):
                case = im.sample_recovery(ROOT, part, rng)
                low, high = ranges[case["label"]]
                self.assertTrue(low <= case["days"] <= high, (part, case))
                self.assertEqual(case["surgery"], int("surgery" in case["label"]))

    def test_each_draw_uses_two_random_numbers(self):
        a, b = random.Random(5), random.Random(5)
        im.sample_recovery(ROOT, "knee", a)
        b.random()
        b.random()
        self.assertEqual(a.random(), b.random())

    def test_season_start_names_fit_their_length(self):
        model = im.load_model(ROOT)
        self.assertEqual(im.typical_diagnosis(model, "knee", 280), "ACL tear")
        self.assertEqual(im.typical_diagnosis(model, "achilles", 280), "Achilles tendon rupture")
        for part in ("knee", "ankle", "back", "hamstring"):
            for days in (2, 10, 40, 120, 300, 600):
                row = diagnosis(part, im.typical_diagnosis(model, part, days))
                if days <= 300 and any(d["quantiles"][0] <= days <= d["quantiles"][-1]
                                       for d in MODEL["recovery_summary"][part]["diagnoses"]):
                    self.assertTrue(row["quantiles"][0] <= days <= row["quantiles"][-1], (part, days, row["label"]))


class NewsTests(unittest.TestCase):
    def test_phrases(self):
        for label, phrase in (("ankle injury", "with an ankle injury"), ("ACL tear", "with an ACL tear"),
                              ("MCL sprain", "with an MCL sprain"), ("Achilles tendon rupture", "with an Achilles tendon rupture"),
                              ("knee soreness", "with knee soreness"), ("back spasms", "with back spasms"),
                              ("plantar fasciitis", "with plantar fasciitis"), ("concussion", "with a concussion"),
                              ("illness", "with an illness"), ("flu", "with the flu"),
                              ("knee surgery recovery", "recovering from knee surgery"),
                              ("hip flexor strain", "with a hip flexor strain")):
            self.assertEqual(im.injury_phrase(label), phrase)

    def test_the_injury_news_item_uses_the_phrase(self):
        save = {"health_states": [], "injury_events": [], "news": [], "league_events": []}
        canonical = {"players": [{"id": "p", "name": "Paul Example", "team_id": "team_x", "minutes_projection": 34.0}]}
        event = {"id": "e1", "player_id": "p", "team_id": "team_x", "start_date": "2026-11-02", "diagnosis": "ankle injury",
                 "body_area": "ankle_foot", "expected_days_missed": 40, "expected_games_missed": 20}
        merge_health_results(save, {"events": [event], "final_states": []}, canonical)
        self.assertIn("Paul Example is expected to miss about 20 games with an ankle injury.", json.dumps(save))


class GamesReportedTests(unittest.TestCase):
    # An 82-game season: every other day from October 21, 2026.
    DAYS = [(date(2026, 10, 21) + timedelta(days=2 * k)).isoformat() for k in range(82)]

    def reported(self, hurt, days):
        return health.injury_games_missed(self.DAYS, hurt, health.injury_return_date(self.DAYS, hurt, days), days)

    def test_an_absence_inside_the_season_is_days_over_two(self):
        self.assertEqual(self.reported(date(2026, 10, 21), 40), 20)

    def test_a_summer_is_not_counted_as_games(self):
        hurt = date(2027, 1, 15)
        left = sum(day > hurt.isoformat() for day in self.DAYS)
        games = self.reported(hurt, 280)      # 140 two-day "games", back the following winter
        self.assertGreater(games, left)
        self.assertLess(games, 100)

    def test_never_more_than_days_over_two_and_playoff_injuries_keep_it(self):
        self.assertEqual(health.injury_games_missed([], date(2027, 5, 1), date(2027, 5, 13), 10), 5)
        for days in (2, 100, 381):
            for hurt in (date(2026, 10, 21), date(2027, 3, 30)):
                self.assertLessEqual(self.reported(hurt, days), days // 2)


if __name__ == "__main__":
    unittest.main()
