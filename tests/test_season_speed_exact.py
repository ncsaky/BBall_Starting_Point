"""Exactness checks for the season-speed caches (docs/agents/tasks/season-speed.md)."""
from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from nba_gm_data import save as sv
from nba_gm_data import transactions as tx
from nba_gm_data.roster_forecast import ForecastSnapshot


class SaveEncodingTests(unittest.TestCase):
    def test_encoder_matches_streaming_json_dump(self):
        value = {"b": [1, 2.5, None, True, "é"], "a": {"z": -0.0, "y": 1e-7, "x": [{"k": "v"}]}, "c": 10**20}
        streamed = io.StringIO()
        json.dump(value, streamed, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        self.assertEqual(sv.encode_save_json(value), streamed.getvalue())


class ParsedSaveCacheTests(unittest.TestCase):
    def test_returns_private_copies_and_follows_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "s.json"
            path.write_text(json.dumps({"n": 1, "rows": [{"x": 1}]}))
            first = sv._parse_save_file(path)
            first["rows"][0]["x"] = 99
            second = sv._parse_save_file(path)
            self.assertEqual(second, {"n": 1, "rows": [{"x": 1}]})
            self.assertIsNot(first, second)
            # Saves are replaced by rename: a new inode and modification time.
            temporary = Path(folder) / "t.json"
            temporary.write_text(json.dumps({"n": 2, "rows": []}))
            os.replace(temporary, path)
            self.assertEqual(sv._parse_save_file(path), {"n": 2, "rows": []})

    def test_in_place_rewrite_is_noticed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "s.json"
            path.write_text(json.dumps({"n": 1}))
            self.assertEqual(sv._parse_save_file(path), {"n": 1})
            time.sleep(0.01)
            path.write_text(json.dumps({"n": 22}))
            self.assertEqual(sv._parse_save_file(path), {"n": 22})


class ActionRuntimeScopeTests(unittest.TestCase):
    def test_scope_is_shared_by_nested_advance_state_and_released(self):
        self.assertIsNone(sv._ADVANCE_RUNTIME_STATE.get())
        with sv.action_runtime_scope() as outer:
            with sv.action_runtime_scope() as again:
                self.assertIs(again, outer)
            inner = sv._AdvanceRuntimeState(parent=outer)
            self.assertIs(inner.attribute_summaries, outer.attribute_summaries)
            source = {"players": [{"id": "p"}], "_private": object()}
            copy = inner.baseline_copy(source)
            self.assertEqual(copy, {"players": [{"id": "p"}]})
            self.assertIsNot(outer.baseline_copy(source)["players"], copy["players"])
            self.assertIsNone(inner.active)
        self.assertIsNone(sv._ADVANCE_RUNTIME_STATE.get())

    def test_standalone_advance_state_keeps_private_caches(self):
        a, b = sv._AdvanceRuntimeState(), sv._AdvanceRuntimeState()
        self.assertIsNot(a.attribute_summaries, b.attribute_summaries)


def _league():
    players = [{"id": f"p{i}", "team_id": "t1", "name": f"P {i}", "position": pos, "height_inches": 78,
                "weight_lbs": 215, "age": 25, "minutes_projection": 20, "_save_stats": {"games": i}}
               for i, pos in enumerate(["PG", "SG", "SF", "PF", "C", "PG", "SF", "C"])]
    traits = [{"player_id": p["id"], "trait_key": key, "value": 50.0 + i}
              for i, p in enumerate(players) for key in ("shooting_range", "rim_pressure", "passing_reads")]
    return {"meta": {"current_date": "2026-11-01"}, "teams": [{"id": "t1", "abbrev": "ONE"}],
            "players": players, "traits": traits, "contracts": []}


class ContentionMemoTests(unittest.TestCase):
    def setUp(self):
        tx._CONTENTION_MEMO.clear()

    def key(self, league):
        view = {**league, "_roster_forecast_snapshot": ForecastSnapshot(league)}
        return tx._contention_memo_key(view, league["teams"][0])

    def test_key_follows_inputs_and_ignores_unread_fields(self):
        league = _league()
        base = self.key(league)
        self.assertIsNotNone(base)
        unread = _league()
        unread["meta"]["current_date"] = "2026-12-01"
        for p in unread["players"]:
            p["_save_stats"] = {"games": 50}
            p["minutes_projection"] = 31
        self.assertEqual(self.key(unread), base)
        changed_trait = _league()
        changed_trait["traits"][0]["value"] = 77.0
        self.assertNotEqual(self.key(changed_trait), base)
        changed_player = _league()
        changed_player["players"][0]["position"] = "C"
        self.assertNotEqual(self.key(changed_player), base)
        changed_roster = _league()
        changed_roster["players"][0]["team_id"] = "t2"
        self.assertNotEqual(self.key(changed_roster), base)

    def test_no_memo_without_forecast(self):
        league = _league()
        self.assertIsNone(tx._contention_memo_key(league, league["teams"][0]))

    def test_memoized_value_matches_fresh_computation(self):
        league = _league()
        view = {**league, "_roster_forecast_snapshot": ForecastSnapshot(league)}
        first = tx.contention_ceiling(view, league["teams"][0], [])
        tx._CONTENTION_MEMO.clear()
        fresh_view = {**_league()}
        fresh_view["_roster_forecast_snapshot"] = ForecastSnapshot(fresh_view)
        self.assertEqual(tx.contention_ceiling(fresh_view, fresh_view["teams"][0], []), first)
        self.assertEqual(tx.contention_ceiling(view, league["teams"][0], []), first)


if __name__ == "__main__":
    unittest.main()
