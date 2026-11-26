"""S2-MULTISEASON: the research switch that lets a save's season loop play its games with Stage 2.

Normal play (switch unset) must call the game sim exactly as before; the bridge only touches other engines' results."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from nba_gm_data import save as save_module
from nba_gm_data.sim import DEFAULT_ENGINE, SAVE_ENGINE_ENV, save_game_engine


def _line(pid: str, team: str, minutes: float) -> dict:
    return {"player_id": pid, "team_id": team, "minutes": minutes, "points": 0}


class SaveEngineSwitchTest(unittest.TestCase):
    def test_default_is_todays_engine(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SAVE_ENGINE_ENV, None)
            self.assertEqual(save_game_engine(), DEFAULT_ENGINE)
        with mock.patch.dict(os.environ, {SAVE_ENGINE_ENV: "  "}):
            self.assertEqual(save_game_engine(), DEFAULT_ENGINE)

    def test_switch_selects_stage2_and_rejects_unknown(self) -> None:
        with mock.patch.dict(os.environ, {SAVE_ENGINE_ENV: "stage2"}):
            self.assertEqual(save_game_engine(), "stage2")
        with mock.patch.dict(os.environ, {SAVE_ENGINE_ENV: "nope"}):
            with self.assertRaises(ValueError):
                save_game_engine()

    def test_normal_play_calls_the_sim_unchanged(self) -> None:
        sentinel = {"game_id": "g", "player_lines": [_line("a", "T1", 0.0)], "team_lines": []}
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SAVE_ENGINE_ENV, None)
            with mock.patch.object(save_module, "sim_game_with_context", return_value=sentinel) as sim, \
                    mock.patch.object(save_module, "to_plain", side_effect=lambda value: value):
                result = save_module.play_save_game({"ctx": 1}, "g", 7)
        sim.assert_called_once_with({"ctx": 1}, "g", mode="sandbox-sim", seed=7)
        self.assertIs(result, sentinel)
        self.assertEqual(len(result["player_lines"]), 1)   # no bridge on today's engine

    def test_stage2_results_are_bridged(self) -> None:
        raw = {"game_id": "g", "player_lines": [_line("a", "T1", 0.0)], "team_lines": []}
        with mock.patch.dict(os.environ, {SAVE_ENGINE_ENV: "stage2"}):
            with mock.patch.object(save_module, "sim_game_with_context", return_value=raw) as sim, \
                    mock.patch.object(save_module, "to_plain", side_effect=lambda value: value):
                result = save_module.play_save_game({}, "g", 7)
        sim.assert_called_once_with({}, "g", mode="sandbox-sim", seed=7, engine="stage2")
        self.assertEqual(result["player_lines"], [])

    def test_bridge_drops_zero_minute_lines_and_records_overtime(self) -> None:
        # Double overtime: 240 + 2 * 25 = 290 minutes a team.
        lines = [_line("a", "T1", 48.0), _line("b", "T1", 0.0)] + [_line(f"x{i}", "T1", 242.0 / 4) for i in range(4)]
        lines += [_line(f"y{i}", "T2", 290.0 / 5) for i in range(5)]
        result = save_module.bridge_engine_result(
            {"player_lines": lines, "team_lines": [{"team_id": "T1"}, {"team_id": "T2"}]})
        self.assertNotIn("b", [line["player_id"] for line in result["player_lines"]])
        self.assertEqual([line["overtime_periods"] for line in result["team_lines"]], [2, 2])

    def test_bridge_leaves_regulation_games_without_overtime(self) -> None:
        lines = [_line(f"x{i}", "T1", 48.0) for i in range(5)] + [_line(f"y{i}", "T2", 48.0) for i in range(5)]
        result = save_module.bridge_engine_result({"player_lines": lines, "team_lines": [{"team_id": "T1"}]})
        self.assertNotIn("overtime_periods", result["team_lines"][0])


class ShortHandedRecallTest(unittest.TestCase):
    """Stage 2 path only: a team left with fewer than five players recalls healthy rested players, never injured ones."""

    def _context(self) -> dict:
        players = [{"id": f"p{i}", "name": f"P{i}", "team_id": "T", "minutes_projection": 20.0, "current_ability": 50 + i}
                   for i in range(8)]
        states = [{"player_id": f"p{i}", "availability_status": "active",
                   "rest_shutdown": {"team_id": "T", "since": "2028-03-01", "reason": "shut down"}} for i in range(4, 7)]
        states.append({"player_id": "p7", "availability_status": "out", "return_date": "2028-05-01"})
        return {"canonical": {"players": players, "player_health_states": states, "injury_events": []}}

    def test_recalls_best_rested_player_to_field_five(self) -> None:
        from nba_gm_data.sim import short_handed_recall
        context = self._context()
        pool = [{"player": context["canonical"]["players"][i], "minutes": 48.0} for i in range(4)]
        out = short_handed_recall(context, {"id": "T"}, pool, "2028-04-10")
        self.assertEqual(len(out), 5)
        recalled = [item for item in out if item.get("short_handed_recall")]
        self.assertEqual([item["player"]["id"] for item in recalled], ["p6"])   # best healthy, not injured p7
        self.assertAlmostEqual(sum(item["minutes"] for item in out), 240.0, places=6)

    def test_full_pool_is_untouched(self) -> None:
        from nba_gm_data.sim import short_handed_recall
        context = self._context()
        pool = [{"player": context["canonical"]["players"][i], "minutes": 48.0} for i in range(5)]
        self.assertIs(short_handed_recall(context, {"id": "T"}, pool, "2028-04-10"), pool)


if __name__ == "__main__":
    unittest.main()
