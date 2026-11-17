"""Exercise the extracted app with temporary data, never repository/user saves.

Run with the build venv's Python. Browser checks additionally use Playwright
and an installed Chrome; set NODE_PATH to a Playwright installation.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


REPO = Path(__file__).resolve().parents[1]
OFFLINE_PROFILE = '(version 1) (allow default) (deny network*) (allow network-inbound (local ip "localhost:*")) (allow network-outbound (remote ip "localhost:*"))'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args()
    archive = args.archive.resolve()
    test_root = Path(tempfile.mkdtemp(prefix="NBA GM Beta verification "))
    install = test_root / "Installed App With Spaces"
    data_dir = test_root / "Isolated User Data"
    cwd = test_root / "Unrelated Working Directory"
    cwd.mkdir()
    subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), str(install)], check=True)
    app = next(install.rglob("NBA GM Sandbox.app"))
    exe = app / "Contents/MacOS/NBA GM Sandbox"
    report = {"archive": str(archive), "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "test_root": str(test_root), "app": str(app), "data_dir": str(data_dir), "checks": {}}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def record(name, value):
        report["checks"][name] = value
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(name + ": " + json.dumps(value), flush=True)

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    process = None
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "UV_", "NBA_GM_"))}
    env["PATH"] = str(test_root / "No external executables here")

    def launch(offline=False):
        nonlocal process
        command = [str(exe), "--headless", "--no-browser", "--data-dir", str(data_dir)]
        if offline:
            command = ["/usr/bin/sandbox-exec", "-p", OFFLINE_PROFILE, *command]
        process = subprocess.Popen(command, cwd=cwd, env=env)
        for _ in range(300):
            if process.poll() is not None:
                raise RuntimeError(f"Packaged app exited {process.returncode}; see {data_dir}/logs/launcher.log")
            if (data_dir / "runtime.json").exists():
                info = json.loads((data_dir / "runtime.json").read_text())
                if info["pid"] == process.pid:
                    return info
            time.sleep(0.1)
        raise RuntimeError("Packaged app did not become ready")

    def quit_app():
        nonlocal process
        info = json.loads((data_dir / "runtime.json").read_text())
        process.terminate()
        process.wait(timeout=45)
        assert process.returncode == 0, process.returncode
        assert not (data_dir / "runtime.json").exists()
        with socket.socket() as check:
            assert check.connect_ex(("127.0.0.1", info["port"])) != 0
        process = None

    def request(path, payload=None, headers=None):
        body = json.dumps(payload).encode() if payload is not None else None
        hdr = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(info["url"] + path, data=body, headers=hdr)
        with opener.open(req, timeout=240) as response:
            raw = response.read()
            return json.loads(raw) if response.headers.get_content_type() == "application/json" else raw

    def action(name, payload=None, backup=False):
        headers = {"X-NBA-GM-Token": token}
        if backup:
            headers["X-NBA-GM-Backup-Upload"] = "1"
        result = request("/api/action", {"action": name, "payload": payload or {}}, headers)
        assert result["ok"], result
        return result["result"]

    def browser(mode):
        if args.skip_browser:
            return
        path = test_root / f"browser-{mode}.json"
        subprocess.run(["node", str(REPO / "scripts/verify_macos_beta_browser.cjs"),
                        info["url"], mode, str(path), str(test_root)], cwd=cwd, check=True)
        record("browser_" + mode, json.loads(path.read_text()))

    try:
        with socket.socket() as occupied:
            try:
                occupied.bind(("127.0.0.1", 8765))
                occupied.listen()
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
                # An existing game already exercises the occupied-port case; leave it alone.
            info = launch(offline=True)
            assert info["port"] != 8765
            record("offline_start_and_occupied_port", {"port": info["port"], "external_network": "denied for app process by sandbox-exec", "cwd": str(cwd), "path": env["PATH"]})
        token = request("/api/session")["token"]
        bundle_version = json.loads(next(install.rglob("build-manifest.json")).read_text())["version"]
        assert f"Sandbox-{bundle_version}-macOS-" in archive.name
        metadata = action("diagnostic_runtime")
        assert metadata["version"] == bundle_version and metadata["packaged"] is True
        assert set(metadata) == {"version", "packaged", "os", "os_release", "architecture", "python", "protocol"}
        assert str(data_dir) not in json.dumps(metadata)
        record("diagnostic_runtime", metadata)
        assert action("list_saves")["save_count"] == 0
        browser("startup")
        try:
            request("/api/action", {"action": "list_saves"})
            raise AssertionError("Missing runtime token accepted")
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        for headers in ({"X-NBA-GM-Token": token, "Origin": "https://evil.example"},
                        {"X-NBA-GM-Token": token, "Host": "evil.example"}):
            try:
                request("/api/action", {"action": "list_saves"}, headers)
                raise AssertionError("Invalid origin/host accepted")
            except urllib.error.HTTPError as exc:
                assert exc.code == 403
        try:
            action("home", {"save_path": str(test_root / "outside.json")})
            raise AssertionError("Out-of-directory save accepted")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        record("packaged_request_protections", "missing token, invalid Host/Origin and escaped save path rejected")
        # The browser phase creates a save using the actual selector controls.
        browser("create")
        if args.skip_browser:
            action("create_save", {"team": "GSW", "save_name": "beta_friend_test", "seed": 2301, "game_mode": "standard"})
        save_path = data_dir / "saves/beta_friend_test.json"
        status = action("save_status", {"save_path": str(save_path)})["save"]
        record("standard_save", {"save_id": status["save_id"], "date": status["current_date"], "team": status["user_team"]["abbrev"]})
        saved = json.loads(save_path.read_text())
        schedule = saved["season_schedules"][saved["meta"]["season"]]
        counts = Counter(str(team) for game in schedule["games"] for team in [game["homeTeamId"], game["awayTeamId"]])
        assert schedule["game_count"] == len(schedule["games"]) == 1230
        assert counts == {str(team):82 for team in range(1,31)}, counts
        full_calendar = action("calendar", {"save_path": str(save_path), "from_date": "2026-10-01", "through_date": "2027-04-12"})["games"]
        calendar_counts = Counter(team for game in full_calendar for team in [game["home_team"], game["away_team"]])
        assert len(full_calendar) == 1230 and len(calendar_counts) == 30 and set(calendar_counts.values()) == {82}
        record("regular_schedule", {"games":len(full_calendar), "games_per_team":dict(calendar_counts), "generation_version":schedule["generation_version"]})
        games = action("calendar", {"save_path": str(save_path), "from_date": "2026-07-01", "through_date": "2026-12-01"})["games"]
        user_games = [g for g in games if status["user_team"]["abbrev"] in (g["home_team"], g["away_team"])]
        first = min(user_games, key=lambda g: (g["date"], g["game_id"]))
        # One short advance to the first game, never a long season soak.
        advanced = action("advance_save", {"save_path": str(save_path), "to_date": first["date"], "seed": 2301})
        result = action("box_score", {"save_path": str(save_path), "game_id": first["game_id"]})
        assert result["home_score"] > 0 and result["away_score"] > 0 and result["player_lines"]
        record("first_game_result", {"game_id": first["game_id"], "date": first["date"],
                                    "away_team": result["away_team"]["abbrev"], "away_score": result["away_score"],
                                    "home_team": result["home_team"]["abbrev"], "home_score": result["home_score"],
                                    "player_lines": len(result["player_lines"]), "advance_result": advanced["result"]})
        (test_root / "expected-game.json").write_text(json.dumps({"game_id": first["game_id"], "save_path": str(save_path)}))
        browser("resume")
        exported = action("export_save", {"save_path": str(save_path)})
        backup_bytes = base64.b64decode(exported["archive_base64"])
        backup = test_root / exported["filename"]
        backup.write_bytes(backup_bytes)
        with zipfile.ZipFile(backup) as contents:
            names = contents.namelist()
            assert any(n.endswith(".sqlite3") for n in names), names
        restored = action("restore_save", {"save_name": "restored_friend_test", "archive_base64": exported["archive_base64"]}, backup=True)
        restored_path = data_dir / "saves/restored_friend_test.json"
        restored_result = action("box_score", {"save_path": str(restored_path), "game_id": first["game_id"]})
        assert result == restored_result
        record("backup_export_restore", {"archive_members": names, "restored_result_identical": True, "result": restored})
        browser("backup")
        if not args.skip_browser:
            assert result == action("box_score", {"save_path": str(data_dir / "saves/browser_restored_friend_test.json"), "game_id": first["game_id"]})
        saved_before = action("save_status", {"save_path": str(save_path)})
        files = sorted(str(p.relative_to(data_dir)) for p in data_dir.rglob("*") if p.is_file())
        assert any(".history.sqlite3" in p for p in files)
        assert any("previous.nbagm.zip" in p for p in files)
        assert any("multiplayer" in p for p in files)
        record("writable_state_outside_bundle", files)
        old_token = token
        quit_app()
        info = launch()
        token = request("/api/session")["token"]
        assert token != old_token
        assert saved_before == action("save_status", {"save_path": str(save_path)})
        assert result == action("box_score", {"save_path": str(save_path), "game_id": first["game_id"]})
        record("quit_relaunch_resume", {"same_save_and_game_result": True, "fresh_runtime_token": True})
        # A second copy reuses the running instance and does not spawn a server.
        second = subprocess.run([str(exe), "--headless", "--no-browser", "--data-dir", str(data_dir)], cwd=cwd, env=env, timeout=30)
        assert second.returncode == 0
        assert json.loads((data_dir / "runtime.json").read_text())["pid"] == process.pid
        record("duplicate_launch", "existing server reused")
        quit_app()
        save_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (data_dir / "saves").iterdir() if p.is_file()}
        assert app.is_relative_to(test_root)
        shutil.rmtree(app)
        replacement = test_root / "Replacement Download"
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), str(replacement)], check=True)
        shutil.copytree(next(replacement.rglob("NBA GM Sandbox.app")), app, symlinks=True)
        info = launch(offline=True)
        token = request("/api/session")["token"]
        assert saved_before == action("save_status", {"save_path": str(save_path)})
        assert result == action("box_score", {"save_path": str(save_path), "game_id": first["game_id"]})
        assert all(hashlib.sha256((data_dir / "saves" / name).read_bytes()).hexdigest() == sha for name, sha in save_hashes.items())
        browser("resume")
        record("application_replacement", "save manifests, history databases, recovery archives and multiplayer DB preserved byte-for-byte")
        quit_app()
        failed = subprocess.run([str(exe), "--headless", "--no-browser", "--data-dir", str(backup)], cwd=cwd, env=env, timeout=30)
        assert failed.returncode != 0
        record("startup_error", "invalid data directory returned a failure without writing elsewhere")
        record("complete", True)
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=45)


if __name__ == "__main__":
    main()
