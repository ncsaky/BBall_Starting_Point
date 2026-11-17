"""Windows extracted-artifact acceptance. All state uses a new temporary folder."""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import ctypes
from ctypes import wintypes
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


def close_control_window(pid):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    found = []
    @callback_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows(visit, 0)
    if not found:
        return False
    for hwnd in found:
        if not user32.PostMessageW(hwnd, 0x0010, 0, 0):
            raise ctypes.WinError(ctypes.get_last_error())
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--skip-browser", action="store_true", help="Partial verification only; not release acceptance")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("The actual EXE and native controller must be verified on Windows.")
    archive = args.archive.resolve()
    root = Path(tempfile.mkdtemp(prefix="NBA GM Windows verification "))
    install, cwd = root / "Installed Game With Spaces", root / "Unrelated CWD"
    local_appdata = root / "Isolated Local AppData"
    data = local_appdata / "NBA GM Sandbox"
    cwd.mkdir()
    with zipfile.ZipFile(archive) as source:
        source.extractall(install)
    exe = next(install.rglob("NBA GM Sandbox.exe"))
    manifest = json.loads(next(install.glob("*/build-manifest.json")).read_text(encoding="utf-8"))
    assert f"Sandbox-{manifest['version']}-Windows-x86_64.zip" in archive.name
    report = {"archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(), "test_root": str(root),
              "version": manifest["version"], "checks": {}, "complete": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    def record(name, value):
        report["checks"][name] = value
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(name + ": " + json.dumps(value), flush=True)
    process = None
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "UV_", "NBA_GM_"))}
    env["PATH"] = str(root / "No external executables")
    env["LOCALAPPDATA"] = str(local_appdata)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    info, token = None, None

    def launch(gui=False):
        nonlocal process, info
        command = [str(exe), "--no-browser"]
        if not gui:
            command.append("--headless")
        process = subprocess.Popen(command, cwd=cwd, env=env)
        for _ in range(300):
            if process.poll() is not None:
                raise RuntimeError(f"EXE exited {process.returncode}; inspect {data}/logs/launcher.log")
            runtime = data / "runtime.json"
            if runtime.exists():
                candidate = json.loads(runtime.read_text())
                if candidate["pid"] == process.pid:
                    info = candidate
                    return
            time.sleep(.1)
        raise RuntimeError("Windows EXE never became ready")

    def quit_app(gui=False):
        nonlocal process
        port = info["port"]
        if gui:
            for _ in range(100):
                if close_control_window(process.pid):
                    break
                time.sleep(.1)
            else:
                raise AssertionError("Native Windows controller never appeared")
        else:
            (data / "verification-stop.request").touch()
        process.wait(timeout=60)
        assert process.returncode == 0, process.returncode
        assert not (data / "runtime.json").exists()
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", port)) != 0
        process = None

    def request(path, payload=None, headers=None):
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(info["url"] + path, data=body,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        with opener.open(req, timeout=240) as response:
            raw = response.read()
            return json.loads(raw) if response.headers.get_content_type() == "application/json" else raw

    def action(name, payload=None, backup=False):
        headers = {"X-NBA-GM-Token": token}
        if backup:
            headers["X-NBA-GM-Backup-Upload"] = "1"
        reply = request("/api/action", {"action": name, "payload": payload or {}}, headers)
        assert reply["ok"], reply
        return reply["result"]

    def browser(mode):
        if args.skip_browser:
            return
        path = root / f"browser-{mode}.json"
        subprocess.run(["node", str(REPO / "scripts/verify_macos_beta_browser.cjs"), info["url"], mode, str(path), str(root)], cwd=REPO, check=True)
        record("browser_" + mode, json.loads(path.read_text()))

    try:
        with socket.socket() as occupied:
            # Occupy an ephemeral port, so the test never connects to a friend's game.
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            preferred = occupied.getsockname()[1]
            process = subprocess.Popen([str(exe), "--headless", "--no-browser", "--port", str(preferred)], cwd=cwd, env=env)
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError("Occupied-port launch failed")
                if (data / "runtime.json").exists():
                    info = json.loads((data / "runtime.json").read_text())
                    break
                time.sleep(.1)
            else:
                raise RuntimeError("Occupied-port launch timed out")
            assert info["port"] != preferred
        record("launch_isolation", {"occupied_port_fallback": True, "stripped_path": True, "unrelated_cwd": True,
                                    "default_localappdata_location": True})
        token = request("/api/session")["token"]
        metadata = action("diagnostic_runtime")
        assert metadata["packaged"] and metadata["version"] == manifest["version"]
        assert metadata["os"] == "Windows" and metadata["architecture"].lower() in {"amd64", "x86_64"}
        record("diagnostic_runtime", metadata)
        assert action("list_saves")["save_count"] == 0
        for headers in ({}, {"X-NBA-GM-Token": token, "Origin": "https://evil.example"}, {"X-NBA-GM-Token": token, "Host": "evil.example"}):
            try:
                request("/api/action", {"action": "list_saves"}, headers)
            except urllib.error.HTTPError as exc:
                assert exc.code == 403
            else:
                raise AssertionError("Invalid request accepted")
        try:
            action("home", {"save_path": str(root / "outside.json")})
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        else:
            raise AssertionError("Escaped save path accepted")
        record("local_api_protections", True)
        browser("startup")
        browser("create")
        if args.skip_browser:
            action("create_save", {"team": "GSW", "save_name": "beta_friend_test", "seed": 2301, "game_mode": "standard"})
        save = data / "saves/beta_friend_test.json"
        payload = {"save_path": str(save)}
        status = action("save_status", payload)["save"]
        saved = json.loads(save.read_text())
        games = saved["season_schedules"][saved["meta"]["season"]]["games"]
        counts = Counter(str(t) for g in games for t in (g["homeTeamId"], g["awayTeamId"]))
        assert len(games) == 1230 and counts == {str(t): 82 for t in range(1, 31)}
        record("regular_schedule", {"games": len(games), "games_per_team": 82})
        calendar = action("calendar", {**payload, "from_date": "2026-07-01", "through_date": "2026-12-01"})["games"]
        first = min((g for g in calendar if status["user_team"]["abbrev"] in (g["home_team"], g["away_team"])), key=lambda g: (g["date"], g["game_id"]))
        action("advance_save", {**payload, "to_date": first["date"], "seed": 2301})
        result = action("box_score", {**payload, "game_id": first["game_id"]})
        assert result["home_score"] > 0 and result["away_score"] > 0 and result["player_lines"]
        record("first_game", {"home_score": result["home_score"], "away_score": result["away_score"]})
        (root / "expected-game.json").write_text(json.dumps({"game_id": first["game_id"], "save_path": str(save)}))
        browser("resume")
        exported = action("export_save", payload)
        backup_path = root / exported["filename"]
        backup_path.write_bytes(base64.b64decode(exported["archive_base64"]))
        with zipfile.ZipFile(backup_path) as contents:
            assert any(n.endswith(".sqlite3") for n in contents.namelist())
        action("restore_save", {"save_name": "restored_friend_test", "archive_base64": exported["archive_base64"]}, backup=True)
        assert result == action("box_score", {"save_path": str(data / "saves/restored_friend_test.json"), "game_id": first["game_id"]})
        browser("backup")
        if not args.skip_browser:
            assert result == action("box_score", {"save_path": str(data / "saves/browser_restored_friend_test.json"), "game_id": first["game_id"]})
        record("backup_history_restore", True)
        before = action("save_status", payload)
        old_token = token
        duplicate = subprocess.run([str(exe), "--headless", "--no-browser"], cwd=cwd, env=env, timeout=30)
        assert duplicate.returncode == 0 and json.loads((data / "runtime.json").read_text())["pid"] == process.pid
        record("duplicate_launch", True)
        quit_app()
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (data / "saves").iterdir() if p.is_file()}
        shutil.rmtree(install)
        with zipfile.ZipFile(archive) as source:
            source.extractall(install)
        launch()
        token = request("/api/session")["token"]
        assert token != old_token and before == action("save_status", payload)
        assert result == action("box_score", {**payload, "game_id": first["game_id"]})
        assert all(hashlib.sha256((data / "saves" / name).read_bytes()).hexdigest() == sha for name, sha in hashes.items())
        record("replace_relaunch_resume", True)
        quit_app()
        launch(gui=True)
        token = request("/api/session")["token"]
        assert before == action("save_status", payload)
        quit_app(gui=True)
        record("native_controller_close", True)
        failed = subprocess.run([str(exe), "--headless", "--no-browser", "--data-dir", str(backup_path)], cwd=cwd, env=env, timeout=30)
        assert failed.returncode != 0
        record("startup_error", True)
        report["complete"] = not args.skip_browser
        record("browser_skipped", args.skip_browser)
    except Exception as exc:
        record("failure", str(exc))
        raise
    finally:
        if process and process.poll() is None:
            (data / "verification-stop.request").touch()
            close_control_window(process.pid)
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
