from __future__ import annotations

import json
import threading
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib import error as urlerror
from urllib import request as urlrequest

from nba_gm_data.app_actions import AppActionError, dispatch_app_action, load_app_canonical
from nba_gm_data.app_server import make_gui_server
from nba_gm_data.fantasy_draft import (
    FANTASY_ROSTER_SIZE,
    best_fantasy_draft_player,
    fantasy_draft_current_team_id,
    fantasy_draft_candidate_score,
    fantasy_draft_room,
    fantasy_growth_outlook,
    fantasy_roster_fit_score,
    simulate_fantasy_draft_all,
    simulate_fantasy_draft_one,
    toggle_fantasy_draft_watchlist,
)
from nba_gm_data.multiplayer import MultiplayerService, MultiplayerStore
from nba_gm_data.save import (
    create_league_save,
    ensure_league_save_defaults,
    load_save,
    player_attribute_summary,
    player_display_attribute_summary,
    presentation_rating_value,
)


ROOT = Path(__file__).resolve().parents[1]


class FantasyDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = load_app_canonical(ROOT)

    def test_fantasy_save_is_seeded_snake_draft_with_equal_own_picks(self):
        with TemporaryDirectory() as tmp:
            first = create_league_save(
                ROOT,
                self.canonical,
                "GSW",
                Path(tmp) / "first.json",
                seed=4242,
                game_mode="fantasy_draft",
            )
            second = create_league_save(
                ROOT,
                self.canonical,
                "BOS",
                Path(tmp) / "second.json",
                seed=4242,
                game_mode="fantasy_draft",
            )
            state = first["fantasy_draft_state"]
            self.assertEqual(state["team_order"], second["fantasy_draft_state"]["team_order"])
            self.assertEqual(state["pick_team_ids"][:30], state["team_order"])
            self.assertEqual(state["pick_team_ids"][30:60], list(reversed(state["team_order"])))
            self.assertEqual(len(state["available_player_ids"]), 30 * FANTASY_ROSTER_SIZE)
            self.assertEqual(first["state"]["phase"], "fantasy_draft")
            self.assertEqual(first["state"]["legal_actions"], ["fantasy_draft_pick"])
            self.assertEqual(first["pick_obligations"], [])
            self.assertEqual(first["locked_pick_assets"], [])

            active_by_key: dict[tuple[str, str, int], list[str]] = defaultdict(list)
            picks = [*self.canonical.get("draft_picks", []), *first.get("generated_draft_picks", [])]
            for pick in picks:
                owner = first["draft_pick_overrides"].get(pick["id"])
                if owner and owner != "used_draft_pick":
                    active_by_key[(str(pick["season"]), str(pick["original_team_id"]), int(pick["round"]))].append(
                        pick["id"]
                    )
                    self.assertEqual(owner, pick["original_team_id"])
            self.assertTrue(active_by_key)
            self.assertTrue(all(len(ids) == 1 for ids in active_by_key.values()))
            expected = len({key[0] for key in active_by_key}) * 30 * 2
            self.assertEqual(len(active_by_key), expected)
            room = fantasy_draft_room(self.canonical, first, first["meta"]["user_team_id"])
            fit_scores = {row["fit_score"] for row in room["available_players"][:30]}
            self.assertGreater(len(fit_scores), 3)
            self.assertTrue(all(1.0 <= score <= 99.0 for score in fit_scores))

    def test_full_fantasy_draft_replaces_rosters_and_preserves_contracts(self):
        with TemporaryDirectory() as tmp:
            save = create_league_save(
                ROOT,
                self.canonical,
                "GSW",
                Path(tmp) / "fantasy.json",
                seed=1776,
                game_mode="fantasy_draft",
            )
            contract_snapshot = json.dumps(self.canonical.get("contracts", []), sort_keys=True)
            selections = simulate_fantasy_draft_all(self.canonical, save)
            self.assertEqual(len(selections), 450)
            self.assertEqual(save["fantasy_draft_state"]["status"], "completed")
            self.assertEqual(save["state"]["phase"], "preseason")
            self.assertEqual(len({row["player_id"] for row in selections}), 450)
            counts = Counter(row["team_id"] for row in selections)
            self.assertEqual(len(counts), 30)
            self.assertEqual(set(counts.values()), {FANTASY_ROSTER_SIZE})
            first_twelve = {row["player_name"] for row in selections[:12]}
            first_round = {row["player_name"] for row in selections[:30]}
            self.assertTrue({"Victor Wembanyama", "Nikola Jokić"} <= first_twelve)
            self.assertTrue({"Giannis Antetokounmpo", "Luka Dončić"} <= first_round)
            self.assertEqual(save["contract_overrides"], {})
            self.assertEqual(json.dumps(self.canonical.get("contracts", []), sort_keys=True), contract_snapshot)
            self.assertFalse({row["player_id"] for row in selections} & set(save["free_agent_player_ids"]))

    def test_single_player_fantasy_actions_start_before_dashboard_and_advance_explicitly(self):
        with TemporaryDirectory() as tmp:
            result = dispatch_app_action(
                "create_save",
                {"team": "GSW", "game_mode": "fantasy_draft", "seed": 90210},
                root=ROOT,
                save_dir=tmp,
                canonical=self.canonical,
            )
            save_path = result["save_path"]
            save = load_save(save_path)
            self.assertEqual(save["state"]["current_date"], save['meta']['gameplay_start_date'])
            self.assertEqual(save["meta"]["season"], "2026-27")
            self.assertEqual(save["state"]["phase"], "fantasy_draft")
            self.assertEqual(save["fantasy_draft_state"]["selections"], [])

            room = dispatch_app_action(
                "fantasy_draft_sim_to_user",
                {"save_path": save_path, "team": "GSW"},
                root=ROOT,
                save_dir=tmp,
                canonical=self.canonical,
            )["room"]
            self.assertTrue(room["is_viewer_turn"])
            before = len(load_save(save_path)["fantasy_draft_state"]["selections"])
            player_id = room["available_players"][0]["player_id"]
            picked = dispatch_app_action(
                "fantasy_draft_pick",
                {"save_path": save_path, "team": "GSW", "player_id": player_id},
                root=ROOT,
                save_dir=tmp,
                canonical=self.canonical,
            )
            self.assertEqual(picked["ai_picks"], [])
            self.assertEqual(
                len(load_save(save_path)["fantasy_draft_state"]["selections"]),
                before + 1,
            )

            while picked["room"]["is_viewer_turn"]:
                player_id = picked["room"]["available_players"][0]["player_id"]
                picked = dispatch_app_action(
                    "fantasy_draft_pick",
                    {"save_path": save_path, "team": "GSW", "player_id": player_id},
                    root=ROOT,
                    save_dir=tmp,
                    canonical=self.canonical,
                )
            before_one = len(load_save(save_path)["fantasy_draft_state"]["selections"])
            one = dispatch_app_action(
                "fantasy_draft_sim_one",
                {"save_path": save_path, "team": "GSW"},
                root=ROOT,
                save_dir=tmp,
                canonical=self.canonical,
            )
            self.assertEqual(one["applied_count"], 1)
            self.assertEqual(
                len(load_save(save_path)["fantasy_draft_state"]["selections"]),
                before_one + 1,
            )
            with self.assertRaises(AppActionError):
                dispatch_app_action(
                    "advance_save",
                    {"save_path": save_path, "days": 1},
                    root=ROOT,
                    save_dir=tmp,
                    canonical=self.canonical,
                )

    def test_watchlist_removes_player_when_another_team_drafts_them(self):
        with TemporaryDirectory() as tmp:
            save = create_league_save(
                ROOT,
                self.canonical,
                "GSW",
                Path(tmp) / "watchlist.json",
                seed=711,
                game_mode="fantasy_draft",
            )
            current_team_id = fantasy_draft_current_team_id(save)
            viewer_team_id = next(
                team["id"]
                for team in self.canonical["teams"]
                if team["id"] != current_team_id
            )
            player_id = best_fantasy_draft_player(save, current_team_id)
            toggle_fantasy_draft_watchlist(save, viewer_team_id, player_id)
            self.assertIn(
                player_id,
                save["fantasy_draft_state"]["watchlists"][viewer_team_id],
            )
            result = simulate_fantasy_draft_one(
                self.canonical,
                save,
                {viewer_team_id},
            )
            self.assertEqual(result["selection"]["player_id"], player_id)
            self.assertNotIn(
                player_id,
                save["fantasy_draft_state"]["watchlists"][viewer_team_id],
            )

    def test_untouched_malformed_fantasy_save_repairs_to_current_draft(self):
        with TemporaryDirectory() as tmp:
            save = create_league_save(
                ROOT,
                self.canonical,
                "GSW",
                Path(tmp) / "repair.json",
                seed=81,
            )
            save["meta"]["game_mode"] = "fantasy_draft"
            save["meta"]["season"] = "2025-26"
            save["state"]["current_date"] = "2025-10-01"
            save["state"]["phase"] = "preseason"
            save.pop("fantasy_draft_state", None)
            save["game_results"] = []
            save["season_history"] = []
            save["transaction_logs"] = []
            repaired = ensure_league_save_defaults(save, self.canonical)
            self.assertEqual(repaired["meta"]["season"], "2026-27")
            self.assertEqual(repaired["state"]["current_date"], "2025-10-01")
            self.assertEqual(repaired["state"]["phase"], "fantasy_draft")
            self.assertEqual(repaired["fantasy_draft_state"]["status"], "in_progress")

    def test_roster_fit_discourages_a_third_creator_guard(self):
        creator = {
            "position": "PG",
            "features": {"passing": 82, "spacing": 72, "rim_deterrence": 30, "defensive_events": 50},
        }
        roster = [dict(creator), dict(creator)]
        third_guard = {
            "position": "PG",
            "features": {"passing": 80, "spacing": 75, "rim_deterrence": 28, "defensive_events": 48},
        }
        needed_center = {
            "position": "C",
            "features": {
                "passing": 52,
                "spacing": 55,
                "rim_deterrence": 82,
                "defensive_events": 72,
                "offensive_rebounding": 74,
            },
        }
        self.assertGreater(
            fantasy_roster_fit_score(needed_center, roster, round_number=5),
            fantasy_roster_fit_score(third_guard, roster, round_number=5),
        )

    def test_growth_outlook_is_visible_scale_and_rewards_real_runway(self):
        young = fantasy_growth_outlook(
            {
                "age": 20,
                "display_overall": 67,
                "minutes_projection": 28,
                "development_upside": 15,
            }
        )
        veteran = fantasy_growth_outlook(
            {
                "age": 32,
                "display_overall": 67,
                "minutes_projection": 28,
                "development_upside": 0,
            }
        )
        self.assertGreaterEqual(young["high_end_growth"], 3.0)
        self.assertLessEqual(young["high_end_growth"], 5.0)
        self.assertGreater(young["ceiling_overall"], young["likely_growth"] + 67 - 1)
        self.assertEqual(veteran["high_end_growth"], 0.0)
        self.assertEqual(veteran["ceiling_overall"], 67.0)

    def test_fantasy_ai_pays_for_growth_and_career_runway(self):
        common = {
            "position": "SF",
            "ratings_prior_overall": 75,
            "display_overall": 68,
            "impact": 68,
            "on_court_value": 68,
            "player_value": 68,
            "contract_surplus": 0,
            "playoff_value": 50,
            "health_risk": 0,
            "salary_millions": 18,
            "contract_years": 3,
            "minutes_projection": 27,
            "features": {
                "impact": 68,
                "spacing": 68,
                "passing": 58,
                "rim_deterrence": 55,
                "defensive_events": 62,
                "offensive_rebounding": 52,
            },
        }
        young = {**common, "player_id": "young", "name": "Young Wing", "age": 20, "development_upside": 15}
        young["growth_outlook"] = fantasy_growth_outlook(young)
        veteran = {**common, "player_id": "veteran", "name": "Veteran Wing", "age": 31, "development_upside": 0}
        veteran["growth_outlook"] = fantasy_growth_outlook(veteran)
        save = {
            "fantasy_draft_state": {
                "status": "in_progress",
                "seed": 91,
                "current_pick_index": 0,
                "pick_team_ids": ["team_test"],
                "available_player_ids": ["young", "veteran"],
                "player_profiles": {"young": young, "veteran": veteran},
                "selections": [],
            }
        }
        self.assertGreater(
            fantasy_draft_candidate_score(save, "team_test", "young"),
            fantasy_draft_candidate_score(save, "team_test", "veteran") + 8,
        )

    def test_fantasy_room_profiles_include_player_card_data(self):
        with TemporaryDirectory() as tmp:
            save = create_league_save(
                ROOT,
                self.canonical,
                "GSW",
                Path(tmp) / "cards.json",
                seed=2026,
                game_mode="fantasy_draft",
            )
            room = fantasy_draft_room(self.canonical, save, "GSW")
            player = room["available_players"][0]
            self.assertEqual(player["profile_version"], "fantasy_player_card_v2")
            self.assertEqual(len(player["contract_seasons"]), 4)
            self.assertIn("overall", player["ratings"])
            self.assertIn("rim_deterrence", player["ratings"])
            self.assertIn("ceiling_overall", player["growth_outlook"])
            self.assertEqual(player["display_overall"], player["ratings"]["overall"])
            self.assertEqual(player["display_overall"], player["engine_overall"])

    def test_presentation_ratings_are_fixed_monotonic_and_engine_neutral(self):
        self.assertEqual(presentation_rating_value(80), 80.0)
        self.assertEqual(presentation_rating_value(90), 90.0)
        self.assertEqual(presentation_rating_value(99), 99.0)
        self.assertLess(presentation_rating_value(60), presentation_rating_value(70))

        wemby = next(player for player in self.canonical["players"] if player["name"] == "Victor Wembanyama")
        before = player_attribute_summary(self.canonical, wemby["id"])
        displayed = player_display_attribute_summary(self.canonical, wemby["id"])
        after = player_attribute_summary(self.canonical, wemby["id"])
        self.assertEqual(before, after)
        self.assertEqual(displayed, before)

    def test_ja_morant_is_a_star_without_an_elite_two_way_profile(self):
        ja = next(player for player in self.canonical["players"] if player["name"] == "Ja Morant")
        engine = player_attribute_summary(self.canonical, ja["id"])
        displayed = player_display_attribute_summary(self.canonical, ja["id"])
        self.assertLess(engine["overall"], 71.0)
        self.assertLess(engine["defense"], 52.0)
        self.assertGreater(engine["creation"], 80.0)
        self.assertEqual(displayed["overall"], engine["overall"])
        self.assertGreater(displayed["creation"], displayed["defense"])

    def test_multiplayer_fantasy_draft_stops_on_human_turns(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            service = MultiplayerService(
                MultiplayerStore(base / "multiplayer.sqlite3"),
                root=ROOT,
                save_dir=base / "saves",
                canonical=self.canonical,
                dispatcher=dispatch_app_action,
            )
            host = service.dispatch("create_lobby", {"name": "Fantasy Friends", "display_name": "Host"})
            guest = service.dispatch("join_lobby", {"code": host["league"]["code"], "display_name": "Guest"})
            host_session = {
                "league_id": host["league"]["id"],
                "manager_id": host["manager_id"],
                "session_token": host["session_token"],
            }
            guest_session = {
                "league_id": host["league"]["id"],
                "manager_id": guest["manager_id"],
                "session_token": guest["session_token"],
            }
            revision = guest["league"]["revision"]
            state = service.dispatch(
                "claim_team",
                {**host_session, "team_id": "team_gsw", "expected_revision": revision},
            )
            state = service.dispatch(
                "claim_team",
                {**guest_session, "team_id": "team_bos", "expected_revision": state["revision"]},
            )
            state = service.dispatch(
                "update_settings",
                {
                    **host_session,
                    "expected_revision": state["revision"],
                    "settings": {"game_mode": "fantasy_draft", "fantasy_pick_seconds": 45},
                },
            )
            state = service.dispatch(
                "set_ready",
                {**host_session, "ready": True, "expected_revision": state["revision"]},
            )
            state = service.dispatch(
                "set_ready",
                {**guest_session, "ready": True, "expected_revision": state["revision"]},
            )
            state = service.dispatch("start_league", {**host_session, "expected_revision": state["revision"]})
            save = load_save(Path(state["save_path"]))
            current_team_id = fantasy_draft_current_team_id(save)
            self.assertIn(current_team_id, {"team_gsw", "team_bos"})
            self.assertEqual(state["clock"]["kind"], "fantasy_pick")

            manager = next(row for row in state["managers"] if row["team_id"] == current_team_id)
            session = host_session if manager["id"] == host_session["manager_id"] else guest_session
            room = service.dispatch(
                "game_action",
                {**session, "game_action": "fantasy_draft_room", "action_payload": {}},
            )["result"]
            player_id = room["available_players"][0]["player_id"]
            result = service.dispatch(
                "game_action",
                {
                    **session,
                    "game_action": "fantasy_draft_pick",
                    "action_payload": {"player_id": player_id},
                    "expected_revision": state["revision"],
                    "idempotency_key": "fantasy-pick-one",
                },
            )
            self.assertEqual(result["status"], "committed")
            updated = load_save(Path(state["save_path"]))
            selected = next(
                row
                for row in updated["fantasy_draft_state"]["selections"]
                if row["player_id"] == player_id
            )
            self.assertEqual(selected["team_id"], current_team_id)
            self.assertEqual(selected["source"], "human_pick")
            self.assertIn(fantasy_draft_current_team_id(updated), {"team_gsw", "team_bos"})

    def test_public_multiplayer_server_hides_single_player_saves(self):
        with TemporaryDirectory() as tmp:
            server = make_gui_server(
                root=ROOT,
                save_dir=Path(tmp) / "saves",
                host="127.0.0.1",
                port=0,
                public_multiplayer_only=True,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urlrequest.urlopen(f"{base}/api/session", timeout=5) as response:
                    token = json.load(response)["token"]
                status_request = urlrequest.Request(f"{base}/api/status", headers={"X-NBA-GM-Token": token})
                with urlrequest.urlopen(status_request, timeout=5) as response:
                    status = json.load(response)
                self.assertTrue(status["multiplayer"]["public_multiplayer_only"])
                self.assertNotIn("root", status)
                self.assertNotIn("save_dir", status)
                self.assertEqual(status["actions"], ["list_saves", "runtime_status", "teams"])
                request = urlrequest.Request(
                    f"{base}/api/action",
                    data=json.dumps({"action": "list_saves", "payload": {}}).encode(),
                    headers={"Content-Type": "application/json", "X-NBA-GM-Token": token},
                    method="POST",
                )
                saves = json.loads(urlrequest.urlopen(request, timeout=5).read())["result"]
                self.assertEqual(saves, {"save_count": 0, "saves": []})
                blocked = urlrequest.Request(
                    f"{base}/api/action",
                    data=json.dumps({"action": "create_save", "payload": {"team": "GSW"}}).encode(),
                    headers={"Content-Type": "application/json", "X-NBA-GM-Token": token},
                    method="POST",
                )
                with self.assertRaises(urlerror.HTTPError) as context:
                    urlrequest.urlopen(blocked, timeout=5)
                self.assertEqual(context.exception.code, 403)
                context.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
