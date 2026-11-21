"""STAR-INJURIES: the public 2025-26 stretches fold into real players' injury history, and the history weights."""
from datetime import date
import json
import math
from pathlib import Path
import tempfile
import unittest

from nba_gm_data import injury_model as im

ROOT = Path(__file__).resolve().parents[1]


def stretch(player, team, first, last, games, part="knee", side="left", category="injury", management=False,
            opener=False, diagnoses=("Sprain",), regular=None):
    return {"player_id": player, "player": player, "team": team, "reason_category": category, "body_part": part,
            "side": side, "reported_body_parts": [], "diagnoses": list(diagnoses), "sources": [],
            "first_game_missed": first, "last_game_missed": last, "games_missed": games,
            "regular_season_games_missed": games if regular is None else regular,
            "at_team_season_start": opener, "injury_management_only": management}


def tracker(player, team, start, part, season="2025-26", side="left", games=2, end="x", censored=0):
    return {"player_id": player, "player": player, "team": team, "start": start, "end": start if end == "x" else end,
            "season": season, "part": part, "side": side, "cat": "injury", "games": games, "days": 2 * games,
            "censored": censored, "label": f"{part} (unspecified)"}


class PublicHistoryFoldInTests(unittest.TestCase):
    def classify(self, stretches, tracker_rows):
        from scripts.build_injury_model import classify_public_stretches, public_history_entries
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "public.json"
            path.write_text(json.dumps({"season": "2025-26", "stretches": stretches}))
            rows, status = classify_public_stretches(tracker_rows, {"BOS": "Boston Celtics", "NYK": "New York Knicks"},
                                                     path)
        return rows, status, public_history_entries(rows, status)

    def test_each_kind_of_stretch(self):
        stretches = [
            stretch("p_new", "BOS", "2025-11-03", "2025-11-07", 3, part="ankle"),
            stretch("p_logged", "BOS", "2025-12-01", "2025-12-04", 2, part="knee"),
            stretch("p_manage", "BOS", "2026-01-10", "2026-01-10", 1, diagnoses=("Injury Management",), management=True),
            stretch("p_ill", "BOS", "2026-01-12", "2026-01-13", 2, part="illness", category="illness"),
            stretch("p_coach", "BOS", "2026-01-12", "2026-01-13", 2, part=None, category="coach_decision"),
            stretch("p_trade", "BOS", "2026-01-20", "2026-02-03", 6, part="calf"),
            stretch("p_trade", "NYK", "2026-02-06", "2026-02-20", 7, part="calf"),
            stretch("p_carry", "BOS", "2025-10-22", "2026-03-01", 60, part="achilles", opener=True),
            stretch("p_preseason", "BOS", "2025-10-22", "2025-11-10", 10, part="hamstring", opener=True),
            stretch("p_old", "NYK", "2025-10-22", "2025-10-25", 2, part="ankle", opener=True),
            stretch("p_nopart", "BOS", "2025-11-03", "2025-11-07", 3, part=None),
        ]
        tracker_rows = [
            tracker("p_logged", "Celtics", "2025-12-01", "knee"),
            # Torn in the previous playoffs: the opening-night stretch continues it.
            tracker("p_carry", "Celtics", "2025-05-12", "achilles", season="2024-25", end=None, censored=1),
            # A sprain in January that healed: the opening-night ankle stretch is a new injury.
            tracker("p_old", "Knicks", "2025-01-15", "ankle", season="2024-25"),
        ]
        rows, status, entries = self.classify(stretches, tracker_rows)
        by_player = {}
        for index, s in enumerate(rows):
            by_player.setdefault(s["player_id"], []).append(status[index])
        self.assertEqual(by_player, {
            "p_new": ["added"], "p_logged": ["tracker"], "p_manage": ["management"], "p_ill": ["illness"],
            "p_coach": ["not_medical"], "p_trade": ["added", "trade_split"], "p_carry": ["carried_in"],
            "p_preseason": ["added"], "p_old": ["added"], "p_nopart": ["no_part"]})
        self.assertEqual(entries["p_new"], [["2025-11-03", "ankle", 6, "ankle sprain"]])
        self.assertEqual([e[0] for e in entries["p_trade"]], ["2026-01-20"])
        self.assertEqual(set(entries), {"p_new", "p_trade", "p_preseason", "p_old"})

    def test_builder_reads_the_public_file_and_writes_v3(self):
        import scripts.build_injury_model as builder
        self.assertTrue(builder.EVIDENCE_OUT.name.endswith("injury_player_evidence_v3.json"))
        self.assertEqual(builder.PUBLIC_HISTORY, ROOT / "data/research/injury_history_2025_26.json")
        self.assertEqual(im.EVIDENCE_FILE, "data/canonical/injury_player_evidence_v3.json")


class HistoryWeightTests(unittest.TestCase):
    def test_weights_and_anchor_agree(self):
        self.assertEqual(im.HISTORY_WEIGHT, 0.75)
        self.assertLess(im.SIMULATED_HISTORY_WEIGHT, im.HISTORY_WEIGHT)
        model = json.loads((ROOT / im.MODEL_FILE).read_text())
        # The model's league rates are anchored with the engine's real-history weight.
        self.assertEqual(model["rate_fit"]["history_weight"], im.HISTORY_WEIGHT)

    def test_game_draws_count_less_than_real_history(self):
        on = date(2027, 1, 1)
        when = date(2026, 1, 1)
        decay = math.exp(-((on - when).days / 365.25) / 1.5)
        real = im.prior_terms([(when, "knee")], on, 1.5)["knee"]
        drawn = im.prior_terms([(when, "knee", True)], on, 1.5)["knee"]
        self.assertAlmostEqual(real, decay)
        self.assertAlmostEqual(drawn, decay * im.SIMULATED_HISTORY_WEIGHT / im.HISTORY_WEIGHT)

    def test_event_sources(self):
        model = {"player_history": {"p": [["2025-05-12", "achilles", 2, "Achilles tendon rupture"]]}}
        events = [
            {"player_id": "p", "start_date": "2026-11-01", "body_part": "ankle", "source_ids": ["src_injury_model_v2"]},
            {"player_id": "p", "start_date": "2026-10-19", "body_part": "knee",
             "source_ids": ["src_opening_night_injuries_2026_27"]},
            {"player_id": "p", "start_date": "2025-10-21", "body_area": "ankle_foot",
             "source_ids": ["src_player_health_overrides_v1"]},
            {"player_id": "p", "start_date": "2026-12-01", "body_part": "illness", "source_ids": []},
        ]
        history = im.player_history(model, "p", events)
        self.assertEqual(history, [(date(2025, 5, 12), "achilles"), (date(2026, 10, 19), "knee"),
                                   (date(2026, 11, 1), "ankle", True)])

    def test_load_model_falls_back_to_v2_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/canonical").mkdir(parents=True)
            (root / im.MODEL_FILE).write_text(json.dumps({"parts": {}}))
            (root / im.FALLBACK_EVIDENCE_FILE).write_text(json.dumps({"version": "v2", "player_history": {"a": []}}))
            self.assertEqual(im.load_model(root)["player_history"], {"a": []})
            (root / im.EVIDENCE_FILE).write_text(json.dumps({"version": "v3", "player_history": {"b": []},
                                                             "public_history_2025_26": {"stretches": {}}}))
            loaded = im.load_model(root)
            self.assertEqual(loaded["player_history"], {"b": []})
            self.assertNotIn("public_history_2025_26", loaded)


if __name__ == "__main__":
    unittest.main()
