"""The career verifier must follow mandatory phases and preserve history."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from nba_gm_data import save as engine


spec = importlib.util.spec_from_file_location("ten_season_soak", Path(__file__).resolve().parents[1]/"scripts/ten_season_soak.py")
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


class SoakRunnerTests(unittest.TestCase):
    def test_phase_driver_uses_open_market_action_instead_of_skipping_resigning(self):
        runner = soak.SoakRunner.__new__(soak.SoakRunner)
        runner.args = SimpleNamespace(team="GSW", seed=7)
        runner.payload = {"save_path":"isolated.json"}
        runner.load = Mock(side_effect=[{"state":{"phase":"re_signing"}}, {"state":{"phase":"free_agency"}}])
        runner.action = Mock(return_value={"status":"open_market"})
        runner.advance_until_phase("free_agency")
        runner.action.assert_called_once_with("advance_re_signing", save_path="isolated.json", team="GSW", mode="open_market", seed=7)

    def test_blocked_open_market_stops_the_driver_with_a_useful_error(self):
        runner = soak.SoakRunner.__new__(soak.SoakRunner)
        runner.args = SimpleNamespace(team="GSW", seed=7)
        runner.payload = {"save_path":"isolated.json"}
        runner.load = Mock(return_value={"state":{"phase":"re_signing"}})
        runner.action = Mock(return_value={"status":"blocked"})
        with self.assertRaisesRegex(RuntimeError,"Could not leave re-signing"):
            runner.advance_until_phase("free_agency")

    def test_phase_snapshot_contains_its_history_and_does_not_mutate_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory/"source.json"
            save = {"version":engine.SAVE_VERSION,"meta":{"id":"test","season":"2026-27"},
                    "state":{"current_date":"2027-04-15"},"game_results":[],"player_game_logs":[],"team_game_logs":[]}
            for i in range(12):
                save["game_results"].append({"game_id":f"game-{i}","home_team_id":"home","away_team_id":"away","home_score":100,"away_score":90})
            engine.write_save(source,save)
            before = source.read_bytes()
            runner = soak.SoakRunner.__new__(soak.SoakRunner)
            runner.payload = {"save_path":str(source)}
            runner.phase_save_dir = directory/"phases"
            runner.phase_save_dir.mkdir()
            runner.snapshot_save("playoffs.json")
            restored = engine.load_save(runner.phase_save_dir/"playoffs.json",include_history=True)
            self.assertEqual(len(restored["game_results"]),12)
            self.assertEqual(source.read_bytes(),before)
            # Replacement snapshots remain valid and self-contained.
            runner.snapshot_save("playoffs.json")
            self.assertEqual(len(engine.load_save(runner.phase_save_dir/"playoffs.json",include_history=True)["game_results"]),12)


if __name__ == "__main__":
    unittest.main()
