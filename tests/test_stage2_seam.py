"""S2-SEAM-SHOOTING: the game sim's engine choice (Stage 2 seam) and its scorecard flags.

The default engine is today's engine, unchanged; "stage2" is an explicit scorecard/research choice (the Stage 2
possession engine since S2-POSSESSION-LOOP); normal gameplay (saves) never passes it."""
import contextlib
import io
import json
import re
import unittest
from pathlib import Path

from nba_gm_data import sim
from nba_gm_data.schema import to_plain

ROOT = Path(__file__).resolve().parents[1]


class EngineChoiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = sim.load_sim_context(ROOT)
        cls.context["indices"] = sim.build_sim_indices(cls.context)
        games = sorted((g for g in cls.context["schedule"] if str(g.get("phase", "regular")) in ("regular", "None", "")),
                       key=lambda g: str(g["externalGameId"]))
        cls.game_ids = [str(games[0]["externalGameId"]), str(games[len(games) // 2]["externalGameId"])]

    def test_default_engine_is_today_and_unchanged(self):
        self.assertEqual(sim.DEFAULT_ENGINE, "current")
        for game_id in self.game_ids:
            for mode in ("sandbox-sim", "replay-real-minutes"):
                default = to_plain(sim.sim_game_with_context(self.context, game_id, mode=mode, seed=11))
                explicit = to_plain(sim.sim_game_with_context(self.context, game_id, mode=mode, seed=11, engine="current"))
                self.assertEqual(default, explicit)
                self.assertNotIn("Stage 2", default["notes"])

    def test_stage2_plays_its_own_game_and_labels_it(self):
        # S2-POSSESSION-LOOP replaced the stub: Stage 2 plays every possession itself, with the same teams and the same
        # box-score format as today's engine; it is deterministic for a seed.
        for game_id in self.game_ids:
            for mode in ("sandbox-sim", "replay-real-minutes"):
                today = to_plain(sim.sim_game_with_context(self.context, game_id, mode=mode, seed=5))
                stage2 = to_plain(sim.sim_game_with_context(self.context, game_id, mode=mode, seed=5, engine="stage2"))
                again = to_plain(sim.sim_game_with_context(self.context, game_id, mode=mode, seed=5, engine="stage2"))
                self.assertTrue(stage2["notes"].startswith("Stage 2 possession engine"))
                self.assertEqual(stage2, again)
                self.assertEqual((today["home_team_id"], today["away_team_id"]),
                                 (stage2["home_team_id"], stage2["away_team_id"]))
                # Every box-score field today's engine writes, except screen assists (no screens in the loop yet).
                self.assertLessEqual(set(today["player_lines"][0]) - set(stage2["player_lines"][0]), {"screen_assists"})

    def test_unknown_engine_is_rejected(self):
        with self.assertRaises(ValueError):
            sim.sim_game_with_context(self.context, self.game_ids[0], engine="possession")

    def test_betting_test_carries_the_engine(self):
        game_id = next(g for g in sim.validation_game_ids(self.context, None, False) if g in self.context["odds"])
        report = sim.validate_game_probabilities_with_context(self.context, game_id, runs=3, seed=2, engine="stage2",
                                                              include_player_stats=False)
        baseline = sim.validate_game_probabilities_with_context(self.context, game_id, runs=3, seed=2,
                                                                include_player_stats=False)
        self.assertEqual(report["engine"], "stage2")
        self.assertEqual(baseline["engine"], "current")
        self.assertIn("brier_score", report["calibration"])


class SeamFlagsTest(unittest.TestCase):
    def test_cli_engine_flag(self):
        from nba_gm_data import cli
        context = sim.load_sim_context(ROOT)
        game_id = next(g for g in sim.validation_game_ids(context, None, False) if g in context["odds"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--root", str(ROOT), "validate-game-probabilities", game_id, "--runs", "2", "--engine", "stage2"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["engine"], "stage2")
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.main(["validate-season-probabilities", "--engine", "possession"])

    def test_calibration_report_has_engine_flag(self):
        text = (ROOT / "scripts/calibration_report.py").read_text()
        self.assertIn('"--engine"', text)
        self.assertIn("engine=args.engine", text)

    def test_normal_gameplay_never_selects_stage2(self):
        # Saves and the app call the game sim without an engine choice, so they always get the default.
        for name in ("save.py", "play.py", "app_actions.py", "app_server.py"):
            path = ROOT / "src/nba_gm_data" / name
            if not path.exists():
                continue
            text = path.read_text()
            for call in re.findall(r"sim_game_with_context\([^\n]*", text):
                self.assertNotIn("engine", call, f"{name}: {call}")
            self.assertNotIn("stage2", text, name)


if __name__ == "__main__":
    unittest.main()
