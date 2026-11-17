from __future__ import annotations

import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib import request as urlrequest

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.app_server import make_gui_server
from nba_gm_data.multiplayer import (
    LOBBY_CODE_ALPHABET,
    MultiplayerAuthenticationError,
    MultiplayerAuthorizationError,
    MultiplayerConflictError,
    MultiplayerService,
    MultiplayerStore,
    dynasty_result,
    record_multiplayer_champion,
)
from nba_gm_data.save import human_controlled_team_ids, load_save


ROOT = Path(__file__).resolve().parents[1]


class MultiplayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = load_app_canonical(ROOT)

    def test_lobby_claims_are_atomic_and_sessions_are_authenticated(self):
        with TemporaryDirectory() as tmp:
            store = MultiplayerStore(Path(tmp) / "multiplayer.sqlite3")
            host = store.create_lobby("Friday League", "Host")
            guest = store.join_lobby(host["league"]["code"], "Guest")
            self.assertEqual(len(host["league"]["code"]), 6)
            self.assertTrue(set(host["league"]["code"]).issubset(set(LOBBY_CODE_ALPHABET)))

            host_claim = store.claim_team(
                host["league"]["id"],
                host["manager_id"],
                host["session_token"],
                "team_gsw",
                guest["league"]["revision"],
            )
            with self.assertRaises(MultiplayerConflictError):
                store.claim_team(
                    host["league"]["id"],
                    guest["manager_id"],
                    guest["session_token"],
                    "team_gsw",
                    host_claim["revision"],
                )
            with self.assertRaises(MultiplayerAuthenticationError):
                store.league_state(host["league"]["id"], host["manager_id"], "wrong-token")

    def test_polling_state_is_read_only_and_does_not_create_writer_contention(self):
        with TemporaryDirectory() as tmp:
            store = MultiplayerStore(Path(tmp) / "multiplayer.sqlite3")
            host = store.create_lobby("Polling League", "Host")
            manager_before = host["league"]["managers"][0]
            time.sleep(0.01)
            for _ in range(5):
                state = store.league_state(
                    host["league"]["id"],
                    host["manager_id"],
                    host["session_token"],
                )
                self.assertEqual(state["revision"], host["league"]["revision"])
            manager_after = state["managers"][0]
            self.assertEqual(manager_after["last_seen"], manager_before["last_seen"])

    def test_thirty_manager_claim_soak_has_unique_teams_and_revision_history(self):
        with TemporaryDirectory() as tmp:
            store = MultiplayerStore(Path(tmp) / "multiplayer.sqlite3")
            teams = [f"team_{index:02d}" for index in range(30)]
            sessions = [store.create_lobby("Full League", "GM 1")]
            for index in range(1, 30):
                sessions.append(store.join_lobby(sessions[0]["league"]["code"], f"GM {index + 1}"))
            revision = sessions[-1]["league"]["revision"]
            for session, team_id in zip(sessions, teams):
                state = store.claim_team(
                    sessions[0]["league"]["id"],
                    session["manager_id"],
                    session["session_token"],
                    team_id,
                    revision,
                )
                revision = state["revision"]
            self.assertEqual(len({manager["team_id"] for manager in state["managers"]}), 30)
            events = store.events(
                sessions[0]["league"]["id"],
                sessions[0]["manager_id"],
                sessions[0]["session_token"],
                limit=100,
            )
            self.assertEqual(sum(event["kind"] == "team_claimed" for event in events["events"]), 30)

    def test_real_two_manager_save_uses_team_specific_reads_and_idempotent_mutations(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            service = MultiplayerService(
                MultiplayerStore(base / "multiplayer.sqlite3"),
                root=ROOT,
                save_dir=base / "saves",
                canonical=self.canonical,
                dispatcher=dispatch_app_action,
            )
            host = service.dispatch("create_lobby", {"name": "Rivals", "display_name": "Host"})
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
            state = service.dispatch(
                "claim_team",
                {**host_session, "team_id": "team_gsw", "expected_revision": guest["league"]["revision"]},
            )
            state = service.dispatch(
                "claim_team",
                {**guest_session, "team_id": "team_bos", "expected_revision": state["revision"]},
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
            with self.assertRaises(MultiplayerAuthorizationError):
                service.dispatch(
                    "game_action",
                    {
                        **guest_session,
                        "game_action": "advance_save",
                        "action_payload": {"days": 1},
                    },
                )
            with self.assertRaises(MultiplayerAuthorizationError):
                service.dispatch(
                    "game_action",
                    {
                        **guest_session,
                        "game_action": "update_game_settings",
                        "action_payload": {"settings": {"press_conferences_enabled": True}},
                        "expected_revision": state["revision"],
                        "idempotency_key": "guest-global-settings",
                    },
                )
            snapshot = service.dispatch("snapshot", guest_session)
            self.assertEqual(snapshot["home"]["save"]["user_team"]["abbrev"], "BOS")

            dashboard = service.dispatch(
                "game_action",
                {**guest_session, "game_action": "team_dashboard", "action_payload": {}},
            )["result"]
            self.assertEqual(dashboard["team"]["abbrev"], "BOS")
            cutdown = service.dispatch(
                "game_action",
                {**guest_session, "game_action": "roster_cutdown", "action_payload": {}},
            )["result"]
            self.assertEqual(cutdown["team"]["abbrev"], "BOS")
            slots = {str(index): row["id"] for index, row in enumerate(dashboard["rotation"][:5], start=1)}
            mutation = {
                **guest_session,
                "game_action": "set_starting_five",
                "action_payload": {"slots": slots},
                "expected_revision": state["revision"],
                "idempotency_key": "guest-lineup-1",
            }
            first = service.dispatch("game_action", mutation)
            replay = service.dispatch("game_action", mutation)
            self.assertEqual(first, replay)
            self.assertEqual(first["status"], "committed")
            with self.assertRaises(MultiplayerConflictError):
                service.dispatch(
                    "game_action",
                    {
                        **host_session,
                        "game_action": "set_starting_five",
                        "action_payload": {"slots": slots},
                        "expected_revision": state["revision"],
                        "idempotency_key": "stale-host-lineup",
                    },
                )
            host_assets = service.dispatch(
                "game_action",
                {**host_session, "game_action": "team_assets", "action_payload": {}},
            )["result"]["assets"]
            guest_assets = service.dispatch(
                "game_action",
                {**guest_session, "game_action": "team_assets", "action_payload": {}},
            )["result"]["assets"]
            host_pick = next(asset for asset in host_assets if asset["kind"] == "pick" and int(asset.get("round") or 0) == 2)
            guest_pick = next(asset for asset in guest_assets if asset["kind"] == "pick" and int(asset.get("round") or 0) == 2)
            candidate = service.dispatch(
                "game_action",
                {
                    **host_session,
                    "game_action": "evaluate_trade",
                    "action_payload": {
                        "from_team": "GSW",
                        "to_team": "BOS",
                        "from_assets": [{"kind": "pick", "value": host_pick.get("value") or host_pick["id"]}],
                        "to_assets": [{"kind": "pick", "value": guest_pick.get("value") or guest_pick["id"]}],
                    },
                },
            )["result"]
            proposed = service.dispatch(
                "game_action",
                {
                    **host_session,
                    "game_action": "apply_trade_candidate",
                    "action_payload": {"candidate": candidate, "source": "builder"},
                    "expected_revision": first["revision"],
                    "idempotency_key": "human-pick-swap-offer",
                },
            )
            self.assertEqual(proposed["status"], "pending_human_acceptance")
            inbox = service.dispatch("human_trade_offers", guest_session)
            self.assertEqual(inbox["offer_count"], 1)
            rejected = service.dispatch(
                "respond_human_trade",
                {
                    **guest_session,
                    "offer_id": proposed["offer_id"],
                    "decision": "reject",
                    "expected_revision": proposed["revision"],
                    "idempotency_key": "reject-human-pick-swap",
                },
            )
            self.assertEqual(rejected["status"], "rejected")
            save = load_save(state["save_path"])
            self.assertEqual(human_controlled_team_ids(save), {"team_gsw", "team_bos"})

    def test_lobby_rejects_a_thirty_first_manager(self):
        with TemporaryDirectory() as tmp:
            store = MultiplayerStore(Path(tmp) / "multiplayer.sqlite3")
            host = store.create_lobby("Capacity League", "GM 1")
            for index in range(1, 30):
                store.join_lobby(host["league"]["code"], f"GM {index + 1}")
            with self.assertRaisesRegex(ValueError, "maximum of 30"):
                store.join_lobby(host["league"]["code"], "GM 31")

    def test_http_multiplayer_endpoint_creates_and_joins_lobby(self):
        with TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "saves"
            server = make_gui_server(root=ROOT, save_dir=save_dir, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            with urlrequest.urlopen(f"{base_url}/api/session", timeout=5) as response:
                token = json.load(response)["token"]

            def post(action: str, payload: dict) -> dict:
                body = json.dumps({"action": action, "payload": payload}).encode("utf-8")
                req = urlrequest.Request(
                    f"{base_url}/api/multiplayer",
                    data=body,
                    headers={"Content-Type": "application/json", "X-NBA-GM-Token": token},
                    method="POST",
                )
                with urlrequest.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                self.assertTrue(result["ok"], result)
                return result["result"]

            try:
                host = post("create_lobby", {"name": "HTTP League", "display_name": "Host"})
                guest = post("join_lobby", {"code": host["league"]["code"], "display_name": "Guest"})
                self.assertEqual(host["league"]["id"], guest["league"]["id"])
                self.assertEqual(len(guest["league"]["managers"]), 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=30)

    def test_dynasty_result_is_championship_first(self):
        save = {
            "meta": {"season": "2027-28"},
            "playoff_state": {
                "status": "completed",
                "champion_team_id": "team_bos",
            },
            "team_records": {
                "team_bos": {"wins": 45, "losses": 37},
                "team_gsw": {"wins": 70, "losses": 12},
            },
            "season_history": [],
            "multiplayer_state": {},
        }
        ledger = record_multiplayer_champion(save)
        managers = [
            {"id": "manager_bos", "display_name": "Boston GM", "team_id": "team_bos"},
            {"id": "manager_gsw", "display_name": "Golden State GM", "team_id": "team_gsw"},
        ]
        result = dynasty_result(save, managers, ledger)
        self.assertEqual(result["winner"]["team_id"], "team_bos")
        self.assertGreater(result["winner"]["score"], result["standings"][1]["score"])


if __name__ == "__main__":
    unittest.main()
