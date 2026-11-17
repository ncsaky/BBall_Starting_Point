"""HTTP boundary regressions. Every mutable fixture is temporary."""
import base64
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from nba_gm_data import app_actions, app_server
from nba_gm_data.history_store import history_sidecar_path
from nba_gm_data.multiplayer import MultiplayerAuthorizationError
from nba_gm_data.save import load_save, write_save
from nba_gm_data.save_recovery import create_export, previous_backup_path


CANONICAL = {"teams": [{"id": "t1", "abbrev": "GSW", "name": "Warriors"}]}


def fixture(marker="original"):
    return {
        "version": "league_save_v1",
        "meta": {"id": "security", "season": "2026-27", "user_team_abbrev": "GSW"},
        "state": {"current_date": "2026-10-01", "phase": "preseason"},
        "marker": marker,
        "game_results": [{"game_id": f"g{i}", "home_score": 100 + i} for i in range(15)],
        "player_game_logs": [], "team_game_logs": [],
    }


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="nba-api-security-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.saves = self.root / "saves"
        self.server = self.start_server()
        self.port = self.server.server_address[1]
        status, session, headers = self.request("GET", "/api/session", token=False)
        self.assertEqual(status, 200)
        self.token = session["token"]
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def start_server(self, **options):
        with patch.object(app_server, "load_app_canonical", return_value=CANONICAL):
            server = app_server.make_gui_server(root=self.root, save_dir=self.saves, port=0, **options)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def cleanup():
            server.shutdown()
            server.server_close()
            worker.join(5)
        self.addCleanup(cleanup)
        return server

    def request(self, method="POST", path="/api/action", body=None, headers=(), token=True,
                host=None, server=None, truncated=False):
        server = server or self.server
        address, port = server.server_address[:2]
        if address == "0.0.0.0":
            address = "127.0.0.1"
        connection = http.client.HTTPConnection(address, port, timeout=5)
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        # A None header value suppresses its default; a list permits duplicates.
        supplied = list(headers.items()) if isinstance(headers, dict) else list(headers)
        names = {key.lower() for key, _ in supplied}
        defaults = [("Host", host or f"127.0.0.1:{port}")]
        if token:
            defaults.append((app_server.API_TOKEN_HEADER, self.token))
        if method == "POST":
            body = json.dumps({"action": "teams", "payload": {}}).encode() if body is None else body
            defaults.extend([("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        for key, value in defaults:
            if key.lower() not in names:
                connection.putheader(key, value)
        for key, value in supplied:
            if value is not None:
                connection.putheader(key, value)
        connection.endheaders(body)
        if truncated:
            connection.sock.shutdown(socket.SHUT_WR)
        response = connection.getresponse()
        content = response.read()
        result = json.loads(content) if response.getheader("Content-Type", "").startswith("application/json") else content
        reply = response.status, result, dict(response.getheaders())
        connection.close()
        return reply

    def assert_rejected_before_dispatch(self, expected, **kwargs):
        with patch.object(app_server, "dispatch_app_action") as local, patch.object(self.server.RequestHandlerClass.app_multiplayer, "dispatch") as multiplayer:
            status, _, _ = self.request(**kwargs)
            self.assertEqual(status, expected)
            local.assert_not_called()
            multiplayer.assert_not_called()

    def test_simulation_stream_uses_the_same_auth_and_path_boundary(self):
        body = json.dumps({"action":"advance_save","payload":{"save_name":"fixture","days":1}}).encode()
        self.assert_rejected_before_dispatch(403,path='/api/action/stream',body=body,token=False)
        self.assert_rejected_before_dispatch(403,path='/api/action/stream',body=body,headers={'Origin':'https://attacker.test'})
        escaped = json.dumps({"action":"advance_save","payload":{"save_path":"../outside.json","days":1}}).encode()
        self.assert_rejected_before_dispatch(400,path='/api/action/stream',body=escaped)
        self.assert_rejected_before_dispatch(400,path='/api/action/stream')

    def test_simulation_stream_has_incremental_events_and_terminal_error_or_result(self):
        from nba_gm_data.simulation_progress import emit_progress
        body = json.dumps({"action":"advance_save","payload":{"save_name":"fixture","days":1}}).encode()
        def run(*args,**kwargs):
            emit_progress({'state':{'current_date':'2027-06-01'}},'date')
            return {'saved':True}
        with patch.object(app_server,'dispatch_app_action',side_effect=run):
            status,content,headers = self.request(path='/api/action/stream',body=body)
        self.assertEqual(status,200)
        messages = [json.loads(line) for line in content.splitlines()]
        self.assertEqual([m['type'] for m in messages],['progress','progress','result'])
        self.assertEqual(messages[1]['event']['date'],'2027-06-01')
        self.assertTrue(messages[-1]['result']['saved'])
        self.assertEqual(headers['Cross-Origin-Resource-Policy'],'same-origin')
        with patch.object(app_server,'dispatch_app_action',side_effect=ValueError('Decision required')):
            status,content,_ = self.request(path='/api/action/stream',body=body)
        messages = [json.loads(line) for line in content.splitlines()]
        self.assertEqual([m['type'] for m in messages],['progress','error'])
        self.assertEqual(messages[-1]['error'],'Decision required')

    def test_host_rebinding_missing_duplicate_and_malformed_hosts(self):
        hosts = ["attacker.test", f"attacker.test:{self.port}", "localhost.evil:8765",
                 "127.0.0.1:1", "localhost:65536", "localhost:0", "localhost:",
                 f"user@localhost:{self.port}", f"localhost:{self.port}/", "[::1", "localhost,evil.test", f"[::1]evil:{self.port}", f"localhost:{self.port}?", f"localhost:{self.port}#"]
        for host in hosts:
            with self.subTest(host=host):
                self.assert_rejected_before_dispatch(403, host=host)
                self.assert_rejected_before_dispatch(403, method="GET", path="/api/session", host=host, token=False)
        self.assert_rejected_before_dispatch(403, headers={"Host": None})
        self.assert_rejected_before_dispatch(403, headers=[("Host", f"localhost:{self.port}"), ("Host", f"localhost:{self.port}")])

    def test_origin_must_match_scheme_address_and_port(self):
        for origin in ["null", "https://attacker.test", f"http://localhost:{self.port}",
                       "http://127.0.0.1:1", f"https://127.0.0.1:{self.port}",
                       f"http://127.0.0.1:{self.port}/", f"http://user@127.0.0.1:{self.port}", f"http://127.0.0.1:{self.port}?", f"http://127.0.0.1:{self.port}#"]:
            with self.subTest(origin=origin):
                self.assert_rejected_before_dispatch(403, headers={"Origin": origin})
                self.assert_rejected_before_dispatch(403, method="GET", path="/api/session", token=False, headers={"Origin": origin})
        self.assert_rejected_before_dispatch(403, headers=[("Origin", f"http://127.0.0.1:{self.port}")] * 2)

    def test_fetch_metadata_blocks_cross_site_bootstrap_and_actions(self):
        for site in ("cross-site", "same-site"):
            for method, path in (("GET", "/api/session"), ("POST", "/api/action"), ("POST", "/api/multiplayer")):
                with self.subTest(site=site, path=path):
                    self.assert_rejected_before_dispatch(403, method=method, path=path, headers={"Sec-Fetch-Site": site})
        self.assert_rejected_before_dispatch(403, headers=[("Sec-Fetch-Site", "same-origin")] * 2)

    def test_token_required_for_status_game_export_restore_recovery_and_multiplayer(self):
        for action in ("teams", "diagnostic_runtime", "create_save", "export_save", "restore_save", "recover_save"):
            for bad_token in (None, "wrong", "é"):
                with self.subTest(action=action, token=bad_token):
                    self.assert_rejected_before_dispatch(403, body=json.dumps({"action": action}).encode(), headers={app_server.API_TOKEN_HEADER: bad_token})
        self.assert_rejected_before_dispatch(403, method="GET", path="/api/status", token=False)
        self.assert_rejected_before_dispatch(403, path="/api/multiplayer", token=False)
        self.assert_rejected_before_dispatch(403, headers=[(app_server.API_TOKEN_HEADER, self.token)] * 2)

    def test_token_is_generated_per_server_and_absent_from_static_assets(self):
        other = self.start_server()
        self.assertNotEqual(other.api_token, self.token)
        for path in ("/", "/app.js"):
            status, content, _ = self.request("GET", path, token=False)
            self.assertEqual(status, 200)
            self.assertNotIn(self.token.encode(), content)

    def test_diagnostic_metadata_ignores_private_payload_and_does_not_mutate_saves(self):
        before = sorted(self.saves.rglob("*")) if self.saves.exists() else []
        status, result, _ = self.request(body=b'{"action":"diagnostic_runtime","payload":{"notes":"secret note","session_token":"secret-token"}}')
        self.assertEqual(status, 200)
        report = result["result"]
        self.assertEqual(set(report), {"version", "packaged", "os", "os_release", "architecture", "python", "protocol"})
        self.assertNotIn("secret", json.dumps(report))
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertEqual(before, sorted(self.saves.rglob("*")) if self.saves.exists() else [])

    def test_localhost_ipv4_and_ipv6_host_authorities_and_matching_origins(self):
        for hostname in ("localhost", "LOCALHOST", "127.0.0.1", "127.0.0.2", "[::1]"):
            authority = f"{hostname}:{self.port}"
            status, result, _ = self.request(host=authority, headers={"Origin": f"http://{authority}", "Sec-Fetch-Site": "same-origin"})
            self.assertEqual(status, 200)
            self.assertEqual(result["result"]["teams"][0]["abbrev"], "GSW")
        self.assertEqual(self.request(headers={"Content-Type": "application/json; charset=UTF-8"})[0], 200)

    def test_ipv6_loopback_launch(self):
        try:
            server = self.start_server(host="::1")
        except OSError as exc:
            self.skipTest(f"IPv6 unavailable: {exc}")
        authority = f"[::1]:{server.server_address[1]}"
        status, session, _ = self.request("GET", "/api/session", token=False, host=authority, server=server)
        self.assertEqual(status, 200)
        self.assertEqual(self.request(server=server, host=authority, headers={app_server.API_TOKEN_HEADER: session["token"], "Origin": f"http://{authority}"})[0], 200)

    def test_content_type_and_request_framing_rejected_before_dispatch(self):
        for content_type in (None, "text/plain", "application/x-www-form-urlencoded", "application/json; charset=latin-1"):
            self.assert_rejected_before_dispatch(415, headers={"Content-Type": content_type})
        self.assert_rejected_before_dispatch(415, headers=[("Content-Type", "application/json")] * 2)
        for length in (None, "-1", "1.0", "+10", "nope", "99999999999999999999"):
            self.assert_rejected_before_dispatch(400, headers={"Content-Length": length})
        self.assert_rejected_before_dispatch(400, headers=[("Content-Length", "0")] * 2)
        self.assert_rejected_before_dispatch(400, headers={"Transfer-Encoding": "chunked"})
        self.assert_rejected_before_dispatch(400, headers={"Content-Encoding": "gzip"})

    def test_malformed_non_object_and_truncated_bodies(self):
        for body in (b"", b"{", b"\xff", b"[]", b"null", b"42", b'{"payload": []}', b'{"action":"teams","payload":"bad"}', b'{"action":[]}', b'{"action":"teams","payload":{"x":NaN}}'):
            with self.subTest(body=body):
                self.assert_rejected_before_dispatch(400, body=body)
        self.assert_rejected_before_dispatch(400, body=b"{}", headers={"Content-Length": "8"}, truncated=True)

    def test_body_limits_reject_headers_before_waiting_for_body(self):
        self.assert_rejected_before_dispatch(413, body=b"", headers={"Content-Length": str(app_server.MAX_JSON_BODY_BYTES + 1)})
        self.assert_rejected_before_dispatch(413, body=b"", headers={"Content-Length": str(app_server.MAX_BACKUP_BODY_BYTES + 1), app_server.BACKUP_UPLOAD_HEADER: "1"})
        self.assert_rejected_before_dispatch(413, path="/api/multiplayer", body=b"", headers={"Content-Length": str(app_server.MAX_JSON_BODY_BYTES + 1), app_server.BACKUP_UPLOAD_HEADER: "1"})
        self.assertEqual(app_server.MAX_BACKUP_BODY_BYTES, ((app_server.MAX_ARCHIVE_BYTES + 2) // 3) * 4 + app_server.MAX_JSON_BODY_BYTES)

    def test_large_upload_allowance_cannot_dispatch_an_ordinary_action(self):
        body = json.dumps({"action": "teams", "payload": {"padding": "x" * 500}}).encode()
        with patch.object(app_server, "MAX_JSON_BODY_BYTES", 256):
            self.assert_rejected_before_dispatch(413, body=body)
            self.assert_rejected_before_dispatch(413, body=body, headers={app_server.BACKUP_UPLOAD_HEADER: "1"})

    def test_legitimate_backup_larger_than_ordinary_body_limit_restores(self):
        path = self.saves / "original.json"
        write_save(path, fixture())
        archive = create_export(path)
        body = json.dumps({"action": "restore_save", "payload": {"save_name": "Imported", "archive_base64": base64.b64encode(archive).decode()}}).encode()
        with patch.object(app_server, "MAX_JSON_BODY_BYTES", 256):
            self.assert_rejected_before_dispatch(413, body=body)
            status, response, _ = self.request(body=body, headers={app_server.BACKUP_UPLOAD_HEADER: "1"})
        self.assertEqual(status, 200, response)
        self.assertEqual(load_save(response["result"]["save_path"])["marker"], "original")

    def test_escaped_path_aliases_names_and_symlinks_rejected_before_dispatch(self):
        outside = self.root / "outside.json"
        outside.write_text("external sentinel")
        (self.saves / "escape.json").symlink_to(outside)
        (self.saves / "directory").symlink_to(self.root, target_is_directory=True)
        cases = [{"save_path": str(outside)}, {"path": "../outside.json"},
                 {"save_name": "../outside"}, {"save_id": str(outside)},
                 {"save_path": "escape.json"}, {"save_path": "directory/outside.json"},
                 {"save_path": "../saves-sibling/new.json"},
                 {"save_path": "good.json", "path": str(outside)}]
        for action in ("save_status", "advance_save", "export_save", "recover_save"):
            for payload in cases:
                with self.subTest(action=action, payload=payload):
                    self.assert_rejected_before_dispatch(400, body=json.dumps({"action": action, "payload": payload}).encode())
        for action in ("create_save", "restore_save"):
            self.assert_rejected_before_dispatch(400, body=json.dumps({"action": action, "payload": {"save_path": str(outside)}}).encode())
        self.assertEqual(outside.read_text(), "external sentinel")
        self.assertFalse((self.root / "saves-sibling").exists())

    def test_escaped_recovery_and_lock_companions_rejected_before_dispatch(self):
        outside = self.root / "outside"
        outside.write_bytes(b"sentinel")
        for name in ("broken.json.previous.nbagm.zip", "broken.json.restore-pending.nbagm.zip", ".broken.json.lock", "broken.json.pre-history-v1.bak"):
            companion = self.saves / name
            companion.symlink_to(outside)
            try:
                self.assert_rejected_before_dispatch(400, body=json.dumps({"action": "recover_save", "payload": {"save_path": "broken.json"}}).encode())
            finally:
                companion.unlink()
        self.assertEqual(outside.read_bytes(), b"sentinel")

    def test_direct_action_resolution_is_canonical_and_preserves_supported_path_forms(self):
        target = self.saves / "safe.json"
        for payload in ({"save_path": str(target)}, {"save_path": "safe.json"}, {"path": "saves/safe.json"}, {"save_name": "safe"}, {"save_id": "safe.json"}):
            self.assertEqual(app_actions.resolve_app_save_path(self.saves, payload), target.resolve())
        with patch.object(app_actions, "dispatch_save_action") as dispatch:
            with self.assertRaises(app_actions.AppActionError):
                app_actions.dispatch_app_action("save_status", {"path": "../escape.json"}, root=self.root, save_dir=self.saves, canonical=CANONICAL)
            dispatch.assert_not_called()

    def test_listing_never_reads_external_symlinked_manifests_or_archives(self):
        outside = self.root / "outside.json"
        outside.write_text("sentinel")
        (self.saves / "escaped.json").symlink_to(outside)
        (self.saves / "missing.json.previous.nbagm.zip").symlink_to(outside)
        with patch.object(app_actions, "load_save") as load:
            result = app_actions.list_saves(self.saves)
            self.assertEqual(result["saves"], [])
            load.assert_not_called()

    def test_explicit_network_bind_and_exact_external_origin_boundaries(self):
        network = self.start_server(host="0.0.0.0", public_multiplayer_only=True, allowed_origins=("https://friends.example",))
        status, session, _ = self.request("GET", "/api/session", server=network, host="friends.example", token=False, headers={"Origin": "https://friends.example"})
        self.assertEqual(status, 200)
        self.assertEqual(self.request(server=network, host="friends.example", headers={app_server.API_TOKEN_HEADER: session["token"], "Origin": "https://friends.example"})[0], 200)
        for host, origin in (("evil.example", "https://evil.example"), ("friends.example:444", "https://friends.example:444"), ("friends.example", "http://friends.example")):
            self.assertEqual(self.request("GET", "/api/session", server=network, host=host, token=False, headers={"Origin": origin})[0], 403)
        # Explicitly allowlisted proxy host is not accepted by ordinary local mode.
        self.assert_rejected_before_dispatch(403, host="friends.example", headers={"X-Forwarded-Host": "localhost", "X-Forwarded-Proto": "https"})

    def test_public_mode_blocks_save_management_and_hides_paths_in_both_status_routes(self):
        self.server.RequestHandlerClass.app_public_multiplayer_only = True
        self.assert_rejected_before_dispatch(403, path="/api/action/stream", body=b'{"action":"advance_save","payload":{"save_name":"fixture","days":1}}')
        for name in ("diagnostic_runtime", "create_save", "export_save", "restore_save", "recover_save", "restore-save"):
            self.assert_rejected_before_dispatch(403, body=json.dumps({"action": name, "payload": {}}).encode())
        self.assertEqual(self.request(body=b'{"action":"list_saves"}')[1]["result"], {"save_count": 0, "saves": []})
        get_status = self.request("GET", "/api/status")[1]
        post_status = self.request(body=b'{"action":"runtime-status"}')[1]["result"]
        for status in (get_status, post_status):
            self.assertNotIn("root", status)
            self.assertNotIn("save_dir", status)
            self.assertEqual(status["actions"], ["list_saves", "runtime_status", "teams"])
        for action in ("list_saves", "runtime_status", "diagnostic_runtime", "create_save", "export_save", "restore_save", "recover-save"):
            self.assert_rejected_before_dispatch(403, path="/api/multiplayer", body=json.dumps({"action": "game_action", "payload": {"game_action": action, "action_payload": {}}}).encode())
            with self.assertRaises(MultiplayerAuthorizationError):
                self.server.RequestHandlerClass.app_multiplayer.game_action("", "", "", action, {}, None, "")

    def test_default_launch_stays_loopback_and_cli_preserves_explicit_modes(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        with patch.object(app_server, "run_gui_server") as run:
            app_server.main(["--root", str(self.root)])
            self.assertEqual(run.call_args.args[2], "127.0.0.1")
            app_server.main(["--root", str(self.root), "--host", "0.0.0.0", "--public-multiplayer-only", "--allowed-origin", "https://friends.example"])
            self.assertEqual(run.call_args.args[2], "0.0.0.0")
            self.assertEqual(run.call_args.args[5:], (True, ("https://friends.example",)))
        for origin in ("https://*.example", "https://example/path", "null", "https://user@example", "https://example:0"):
            with self.assertRaises(ValueError):
                app_server.make_gui_server(root=self.root, save_dir=self.saves, port=0, allowed_origins=(origin,))

    @unittest.skipIf(os.name == "nt", "The optional tunnel launcher uses bash.")
    def test_public_test_launcher_pins_only_the_discovered_tunnel_origin(self):
        binary_dir = self.root / "bin"
        binary_dir.mkdir()
        fake_tunnel = binary_dir / "cloudflared"
        fake_tunnel.write_text(f"#!{sys.executable}\nimport signal\nprint('https://fixture.trycloudflare.com', flush=True)\nsignal.pause()\n")
        fake_tunnel.chmod(0o755)
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        output_path = self.root / "launcher.log"
        repository = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PATH=str(binary_dir) + os.pathsep + os.environ["PATH"], NBA_GM_PORT=str(port), NBA_GM_MULTIPLAYER_SAVE_DIR=str(self.root / "launcher-saves"))
        with output_path.open("w") as output:
            process = subprocess.Popen(["bash", str(repository / "scripts/run_public_multiplayer_test.sh")], env=environment, stdout=output, stderr=output, start_new_session=True)
            try:
                deadline = time.monotonic() + 15
                while "Temporary public multiplayer test:" not in output_path.read_text():
                    if process.poll() is not None or time.monotonic() >= deadline:
                        self.fail(output_path.read_text())
                    time.sleep(0.1)
                server = SimpleNamespace(server_address=("127.0.0.1", port))
                status, session, _ = self.request("GET", "/api/session", server=server, host="fixture.trycloudflare.com", token=False, headers={"Origin": "https://fixture.trycloudflare.com"})
                self.assertEqual(status, 200)
                self.assertEqual(self.request("GET", "/api/session", server=server, host="other.trycloudflare.com", token=False)[0], 403)
                self.assertEqual(self.request(server=server, host="fixture.trycloudflare.com", body=b'{"action":"restore_save"}', headers={app_server.API_TOKEN_HEADER: session["token"], "Origin": "https://fixture.trycloudflare.com"})[0], 403)
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
