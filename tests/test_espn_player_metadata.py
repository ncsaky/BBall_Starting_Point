import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from import_espn_player_metadata import build_import, search_player_athlete, search_player_headshot
from nba_gm_data.ingest import build_players, enrich_player_external_metadata


class EspnPlayerMetadataTests(unittest.TestCase):
    def test_import_maps_espn_identity_headshot_and_overall_draft_pick(self):
        canonical = {
            "players": [
                {"id": "player_lal-lebron-james", "name": "LeBron James", "normalized_name": "lebron james"},
                {"id": "player-bos-payton-pritchard", "name": "Payton Pritchard", "normalized_name": "payton pritchard"},
            ]
        }
        profiles = [
            {
                "id": "1966",
                "displayName": "LeBron James",
                "slug": "lebron-james",
                "headshot": {"href": "https://a.espncdn.com/i/headshots/nba/players/full/1966.png"},
                "links": [{"rel": ["playercard"], "href": "https://www.espn.com/nba/player/_/id/1966/lebron-james"}],
                "draft": {"year": 2003, "round": 1, "selection": 1},
            },
            {
                "id": "4066354",
                "displayName": "Payton Pritchard",
                "headshot": {"href": "https://a.espncdn.com/i/headshots/nba/players/full/4066354.png"},
                "draft": {"year": 2020, "round": 1, "selection": 26},
            },
        ]

        imported = build_import(canonical, profiles, [])
        self.assertEqual(imported["coverage"]["matched_player_count"], 2)
        first, second = imported["players"]
        self.assertEqual(first["espn_player_id"], "1966")
        self.assertEqual(first["draft_position"], 1)
        self.assertEqual(first["headshot_rights_status"], "reference_only_not_cleared")
        self.assertEqual(second["draft_position"], 26)
        self.assertEqual(imported["coverage"]["unmatched_player_count"], 0)

    def test_espn_search_fallback_only_accepts_unique_nba_name_matches(self):
        player = {"name": "Fred VanVleet", "normalized_name": "fred vanvleet"}
        payload = {"results": [{"type": "player", "contents": [
            {"displayName": "Fred VanVleet", "description": "NBA", "sport": "basketball", "uid": "s:40~l:46~a:2991230"},
            {"displayName": "Fred VanVleet", "description": "FIBA", "sport": "basketball", "uid": "s:40~l:53~a:2991232"},
            {"displayName": "Fred VanVleet", "description": "College", "sport": "football", "uid": "s:1~a:123"},
        ]}]}
        with patch("import_espn_player_metadata.fetch_json", return_value=payload):
            self.assertEqual(search_player_athlete(player), ("2991230", None))

        payload["results"][0]["contents"].append(
            {"displayName": "Fred VanVleet", "description": "NBA", "sport": "basketball", "uid": "s:40~l:46~a:2991231"}
        )
        with patch("import_espn_player_metadata.fetch_json", return_value=payload):
            self.assertEqual(search_player_athlete(player), (None, "search_match_count_2"))

    def test_search_fallback_handles_espn_competition_labels_and_diacritics(self):
        player = {"name": "Nikola Đurišić", "normalized_name": "nikola urisic"}
        payload = {"results": [{"type": "player", "contents": [
            {"displayName": "Nikola Durisic", "description": "NBA", "sport": "basketball", "uid": "s:40~l:46~a:5144067"},
            {"displayName": "Nikola Djurisic", "description": "FIBA", "sport": "basketball", "uid": "s:40~l:53~a:5211982"},
        ]}]}
        with patch("import_espn_player_metadata.fetch_json", return_value=payload):
            self.assertEqual(search_player_athlete(player), ("5144067", None))

        player = {"name": "Dario Šarić", "normalized_name": "dario saric"}
        payload["results"][0]["contents"] = [
            {"displayName": "Dario Saric", "description": "FIBA", "sport": "basketball", "uid": "s:40~l:53~a:3032978"}
        ]
        with patch("import_espn_player_metadata.fetch_json", return_value=payload):
            self.assertEqual(search_player_athlete(player), ("3032978", None))

        nikola = {"name": "Nikola Đurišić", "normalized_name": "nikola urisic", "id": "player-atl-nikola-urisic"}
        imported = build_import({"players": [nikola]}, [{
            "id": "5144067",
            "displayName": "Nikola Durisic",
            "headshot": {"href": "https://example.test/nikola.png"},
            "draft": {"year": 2024, "round": 2, "selection": 43},
        }], [])
        self.assertEqual(imported["players"][0]["espn_player_id"], "5144067")

    def test_search_headshot_must_match_exact_espn_id_and_name(self):
        player = {"name": "Eli John Ndiaye", "normalized_name": "eli john ndiaye"}
        payload = {"results": [{"type": "player", "contents": [
            {"displayName": "Eli Ndiaye", "sport": "basketball", "uid": "s:40~l:46~a:5144071", "image": {"default": "https://example.test/wrong.png"}},
            {"displayName": "Eli John Ndiaye", "sport": "basketball", "uid": "s:40~l:46~a:5175648", "image": {"default": "https://example.test/right.png"}},
        ]}]}
        with patch("import_espn_player_metadata.fetch_json", return_value=payload):
            self.assertEqual(search_player_headshot(player, "5175648"), "https://example.test/right.png")
            payload["results"][0]["contents"] = [
                {"displayName": "Eli John Ndiaye", "sport": "basketball", "uid": "s:40~l:41~a:6000001", "image": {"default": "https://example.test/college.png"}}
            ]
            self.assertEqual(search_player_headshot(player, "5175648"), "https://example.test/college.png")

    def test_sidecar_metadata_is_added_to_built_and_loaded_player_rows(self):
        metadata = {
            "players": [{
                "game_player_id": "player_lal-lebron-james",
                "espn_player_id": "1966",
                "espn_profile_url": "https://www.espn.com/nba/player/_/id/1966/lebron-james",
                "headshot_url": "https://a.espncdn.com/i/headshots/nba/players/full/1966.png",
                "headshot_url_source": "espn_core_athlete_profile",
                "headshot_rights_status": "reference_only_not_cleared",
                "headshot_asset_path": None,
                "draft_year": 2003,
                "draft_round": 1,
                "draft_position": 1,
                "draft_status": "drafted",
            }]
        }
        raw = [{"name": "LeBron James", "teamAbbrev": "LAL", "position": "SF", "simEligible": True}]
        player = build_players(raw, espn_player_metadata=metadata)[0]
        self.assertEqual(player.espn_player_id, "1966")
        self.assertEqual(player.draft_position, 1)
        self.assertIn("src_espn_nba_player_profiles", player.source_ids)

        legacy_row = {"id": player.id, "source_ids": []}
        enrich_player_external_metadata([legacy_row], metadata)
        self.assertEqual(legacy_row["draft_year"], 2003)
        self.assertEqual(legacy_row["headshot_url_source"], "espn_core_athlete_profile")
        self.assertIn("src_espn_nba_player_profiles", legacy_row["source_ids"])


if __name__ == "__main__":
    unittest.main()
