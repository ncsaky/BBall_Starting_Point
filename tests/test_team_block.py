from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from nba_gm_data.app_actions import AppActionError, set_team_block_action
from nba_gm_data.transactions import build_trade_block_entries


class TeamBlockTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.save = {"meta": {"user_team_id": "team_was"}}
        self.team = {"id": "team_was", "abbrev": "WAS"}
        active = {"players": [{"id": str(i), "team_id": "team_was"} for i in range(7)]}
        for name, value in (("load_save", self.save), ("ensure_league_save_defaults", self.save),
                            ("canonical_with_save", active), ("resolve_team", self.team)):
            self.stack.enter_context(patch(f"nba_gm_data.app_actions.{name}", return_value=value))
        self.write = self.stack.enter_context(patch("nba_gm_data.app_actions.write_save"))

    def test_add_remove_and_clear_are_persisted(self):
        for ids in (["0", "1"], ["1"], []):
            result = set_team_block_action({}, Path("unused.json"), {"team": "WAS", "player_ids": ids})
            self.assertEqual(result["team_block_player_ids"], ids)
            self.assertEqual(self.save["team_trade_blocks"]["team_was"], ids)
        self.assertEqual(self.write.call_count, 3)

    def test_foreign_duplicate_and_oversize_blocks_never_write(self):
        for ids in (["foreign"], ["0", "0"], [str(i) for i in range(7)], [{}]):
            with self.subTest(ids=ids), self.assertRaises(AppActionError):
                set_team_block_action({}, Path("unused.json"), {"team": "WAS", "player_ids": ids})
        self.write.assert_not_called()

    def test_inspected_team_cannot_be_edited(self):
        self.team["id"] = "team_bos"
        with self.assertRaises(AppActionError):
            set_team_block_action({}, Path("unused.json"), {"team": "BOS", "player_ids": []})
        self.write.assert_not_called()

    def test_pick_block_ownership_and_combined_limit(self):
        with patch("nba_gm_data.app_actions.tradeable_picks_for_team", return_value=[{"id": "pick"}]):
            result = set_team_block_action({}, Path("unused.json"), {"team": "WAS", "player_ids": ["0"], "pick_ids": ["pick"]})
            self.assertEqual(result["team_block_pick_ids"], ["pick"])
            self.assertEqual(self.save["team_trade_block_picks"]["team_was"], ["pick"])
            for players, picks in ((["0"], ["foreign"]), ([str(i) for i in range(6)], ["pick"]), ([], ["pick", "pick"])):
                with self.assertRaises(AppActionError):
                    set_team_block_action({}, Path("unused.json"), {"team": "WAS", "player_ids": players, "pick_ids": picks})

    def test_manual_list_is_consumed_by_transaction_model(self):
        players = [{"id": "chosen", "team_id": "was"}, {"id": "omitted", "team_id": "was"}, {"id": "ai", "team_id": "bos"}]
        canonical = {"players": players, "team_trade_blocks": {"was": ["chosen"]}}
        states = [SimpleNamespace(team_id=team) for team in ("was", "bos")]
        values = [SimpleNamespace(player_id=p["id"]) for p in players]
        with patch("nba_gm_data.transactions.trade_block_score", return_value=(40, [], "best_asset")):
            entries = build_trade_block_entries(canonical, states, values)
        self.assertEqual({entry.player_id for entry in entries}, {"chosen", "ai"})
        self.assertIn("gm_listed", next(entry for entry in entries if entry.player_id == "chosen").reasons)
