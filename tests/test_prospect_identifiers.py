"""Draft-board identifiers and saved preseason ranks use real prospect IDs."""

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data.app_actions import enrich_draft_board_scouting
from nba_gm_data.draft import draft_board_report
from nba_gm_data.ingest import build_universe
from nba_gm_data.save import (
    canonical_with_save,
    create_league_save,
    ensure_league_save_defaults,
    load_save,
    write_save,
)
from nba_gm_data.schema import to_plain


ROOT = Path(__file__).resolve().parents[1]


class ProspectIdentifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = to_plain(build_universe(ROOT))

    def test_actual_board_payload_seeds_and_persists_real_prospect_rank_keys(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "league.json"
            save = create_league_save(ROOT, self.canonical, "GSW", path, seed=913)
            team_id = save["meta"]["user_team_id"]
            year = str(int(save["meta"]["season"][:4]) + 1)
            board_key = f"{team_id}:{year}"
            active = canonical_with_save(self.canonical, save)
            board = draft_board_report(active, team_id, year)
            # The saved baseline is the team's scouts' board in the season's first month.
            expected = {entry["prospect_id"]: entry["board_rank"] for entry in board["entries"]}
            self.assertTrue(expected)  # Exercise board_entry_payload, not the generated fallback.
            self.assertEqual(len(board["entries"]), len(expected))
            real_ids = {prospect["id"] for prospect in active["draft_prospects"]}
            self.assertLessEqual(set(expected), real_ids)

            ensure_league_save_defaults(save, self.canonical)
            self.assertEqual(save["prospect_preseason_ranks"][board_key], expected)
            for entry in board["entries"]:
                self.assertEqual(entry["prospect"]["id"], entry["prospect_id"])
                self.assertEqual(entry["prospect"]["prospect_id"], entry["prospect_id"])
            write_save(path, save)
            stored = load_save(path)
            self.assertEqual(stored["prospect_preseason_ranks"][board_key], expected)
            ensure_league_save_defaults(stored, self.canonical)
            self.assertEqual(stored["prospect_preseason_ranks"][board_key], expected)

    def test_existing_baseline_is_preserved_and_used_by_rank_display(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "league.json"
            save = create_league_save(ROOT, self.canonical, "GSW", path, seed=913)
            team_id = save["meta"]["user_team_id"]
            year = str(int(save["meta"]["season"][:4]) + 1)
            board_key = f"{team_id}:{year}"
            active = canonical_with_save(self.canonical, save)
            board = draft_board_report(active, team_id, year)
            expected = {
                entry["prospect"]["prospect_id"]: int(entry["board_rank"]) + 4
                for entry in board["entries"]
            }
            save["prospect_preseason_ranks"] = {board_key: expected, "team_other:2026": {"historical_prospect": 7}}
            original = deepcopy(save["prospect_preseason_ranks"])
            write_save(path, save)
            stored = ensure_league_save_defaults(load_save(path), self.canonical)
            self.assertEqual(stored["prospect_preseason_ranks"], original)
            enriched = enrich_draft_board_scouting(active, stored, team_id, board)
            for entry in enriched["entries"]:
                self.assertEqual(entry["season_start_rank"], expected[entry["prospect"]["prospect_id"]])
                self.assertEqual(entry["rank_change"], 4)
            write_save(path, stored)
            self.assertEqual(load_save(path)["prospect_preseason_ranks"], original)


if __name__ == "__main__":
    unittest.main()
