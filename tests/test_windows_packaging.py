"""Portable checks do not substitute for the real Windows EXE acceptance run."""

import errno
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.request

from nba_gm_data import app_server, desktop_runtime


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load("windows_build", "packaging/windows/build.py")
launcher = load("windows_launcher", "packaging/windows/launcher.py")


class WindowsBuildTests(unittest.TestCase):
    def test_source_preflight_is_complete_and_excludes_saves(self):
        _, manifest = build.inventory()
        self.assertFalse(manifest["game_python_dependencies"])
        self.assertTrue(set(build.REQUIRED).issubset(manifest["input_sha256"]))
        self.assertFalse(any(n.startswith(("saves/", ".cache/", "dist/")) for n in manifest["input_sha256"]))

    def test_inventory_ships_compressed_inputs_but_no_private_or_uncompressed_copies(self):
        files, _ = build.inventory()
        shipped = {p.relative_to(ROOT).as_posix() for p in files}
        self.assertIn("data/canonical/player_inputs_2026_27.json.gz", shipped)
        self.assertNotIn("data/canonical/player_inputs_2026_27.json", shipped)
        self.assertFalse([n for n in shipped
                          if any(n == item or n.startswith(item + "/") for item in build.PRIVATE_DATA)])
        for platform_name in ("macos", "windows"):
            spec = (ROOT / f"packaging/{platform_name}/NBA GM Sandbox.spec").read_text()
            for item in build.PRIVATE_DATA + build.BUILD_ONLY_DATA:
                self.assertIn(f'"{item}"', spec, (platform_name, item))

    def test_missing_or_empty_media_fails_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in build.REQUIRED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"asset")
            movie = root / "src/nba_gm_data/gui/assets/startup/video/front-office.mp4"
            for empty in (False, True):
                with self.subTest(empty=empty):
                    if empty:
                        movie.write_bytes(b"")
                    else:
                        movie.unlink()
                    with self.assertRaisesRegex(RuntimeError, "front-office.mp4"):
                        build.inventory(root)

    def test_icon_is_256_pixel_png_backed_ico(self):
        data = (ROOT / "packaging/assets/app-icon.ico").read_bytes()
        self.assertEqual(struct.unpack_from("<HHH", data), (0, 1, 1))
        self.assertEqual(data[6:8], b"\0\0")
        length, offset = struct.unpack_from("<II", data, 14)
        self.assertEqual(offset, 22)
        self.assertEqual(length, len(data) - offset)
        self.assertEqual(data[offset:offset + 8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack_from(">II", data, offset + 16), (256, 256))

    def test_pe_audit_rejects_wrong_architecture_truncation_and_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "No Windows"):
                build.audit_binaries(app)
            data = bytearray(256)
            data[:2] = b"MZ"
            struct.pack_into("<I", data, 0x3c, 128)
            data[128:132] = b"PE\0\0"
            struct.pack_into("<H", data, 132, 0x8664)
            exe = app / "game.exe"
            exe.write_bytes(data)
            self.assertEqual(build.audit_binaries(app)["pe_count"], 1)
            for malformed in (b"MZ", b"not an exe", data[:133]):
                exe.write_bytes(malformed)
                with self.assertRaises(RuntimeError):
                    build.audit_binaries(app)
            for machine in (0x14c, 0xaa64):
                struct.pack_into("<H", data, 132, machine)
                exe.write_bytes(data)
                with self.assertRaisesRegex(RuntimeError, "AMD64"):
                    build.audit_binaries(app)

    def test_resource_audit_detects_changed_media_and_missing_tk(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            internal = app / "_internal"
            movie = internal / "nba_gm_data/gui/assets/startup/video/front-office.mp4"
            movie.parent.mkdir(parents=True)
            movie.write_bytes(b"original")
            manifest = {"input_sha256": {"src/nba_gm_data/gui/assets/startup/video/front-office.mp4": build.digest(movie)}}
            with self.assertRaisesRegex(RuntimeError, "Tcl/Tk"):
                build.audit_resources(app, manifest)
            for name in ("_tcl_data/init.tcl", "_tk_data/tk.tcl"):
                path = internal / name
                path.parent.mkdir(parents=True)
                path.touch()
            self.assertEqual(build.audit_resources(app, manifest)["byte_identical_resources"], 1)
            movie.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "altered bundled"):
                build.audit_resources(app, manifest)

    def test_stable_user_data_location_is_not_install_or_cwd(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": "/isolated/local"}, clear=True):
            self.assertEqual(launcher.default_data_dir(), Path("/isolated/local/NBA GM Sandbox"))
        with patch.dict(os.environ, {"NBA_GM_USER_DATA_DIR": "/test override"}, clear=True):
            self.assertEqual(launcher.default_data_dir(), Path("/test override"))


class InstanceLockTests(unittest.TestCase):
    def test_contention_and_reacquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.lock"
            first, second = desktop_runtime.InstanceLock(path), desktop_runtime.InstanceLock(path)
            try:
                self.assertTrue(first.acquire())
                self.assertFalse(second.acquire())
                first.close()
                first.close()
                self.assertTrue(second.acquire())
            finally:
                first.close()
                second.close()

    def test_windows_uses_one_nonblocking_byte_and_only_owner_unlocks(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = desktop_runtime.InstanceLock(Path(directory) / "server.lock")
            crt = SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=Mock())
            fake_os = SimpleNamespace(name="nt", SEEK_END=os.SEEK_END)
            with patch.object(desktop_runtime, "os", fake_os), patch.dict("sys.modules", {"msvcrt": crt}):
                self.assertTrue(lock.acquire())
                lock.close()
            self.assertEqual([c.args[1:] for c in crt.locking.call_args_list], [(2, 1), (0, 1)])
            self.assertEqual((Path(directory) / "server.lock").read_bytes(), b"\0")

    def test_windows_contention_does_not_unlock_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = desktop_runtime.InstanceLock(Path(directory) / "server.lock")
            crt = SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=Mock(side_effect=OSError(errno.EACCES, "busy")))
            with patch.object(desktop_runtime, "os", SimpleNamespace(name="nt", SEEK_END=os.SEEK_END)), patch.dict("sys.modules", {"msvcrt": crt}):
                self.assertFalse(lock.acquire())
                lock.close()
            self.assertEqual(crt.locking.call_count, 1)

    def test_live_instance_ignores_stored_remote_url_and_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.return_value = b'{"token":"local"}'
            opener = Mock()
            opener.open.return_value = response
            path.write_text('{"port":12345,"url":"https://evil.example"}')
            with patch.object(desktop_runtime.urllib.request, "build_opener", return_value=opener):
                self.assertEqual(desktop_runtime.live_instance(path), "http://127.0.0.1:12345")
                opener.open.assert_called_once_with("http://127.0.0.1:12345/api/session", timeout=1)
            for value in ("{}", "not json", '{"port":99999}'):
                path.write_text(value)
                self.assertIsNone(desktop_runtime.live_instance(path))


class DesktopLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="desktop-runtime-")
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name) / "user data"
        self.data.mkdir()

    def start(self, port=0):
        runtime = desktop_runtime.DesktopRuntime(ROOT, self.data, port)
        self.addCleanup(runtime.stop)
        return runtime

    def test_loopback_duplicate_shutdown_relaunch_and_save_preservation(self):
        runtime = self.start()
        saved = self.data / "saves/sentinel.json"
        saved.write_text("do not touch")
        info = json.loads(runtime.runtime_path.read_text())
        self.assertEqual(set(info), {"pid", "port", "url"})
        self.assertEqual(runtime.server.server_address[0], "127.0.0.1")
        second = self.start()
        self.assertEqual(second.existing_url, runtime.url)
        second.stop()
        self.assertTrue(runtime.runtime_path.exists())
        port = runtime.port
        runtime.stop()
        self.assertFalse(runtime.runtime_path.exists())
        with socket.socket() as probe:
            self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)
        replacement = self.start()
        self.assertTrue(replacement.lock.owned)
        self.assertEqual(saved.read_text(), "do not touch")

    def test_occupied_port_falls_back_without_touching_other_service(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            runtime = self.start(port)
            self.assertNotEqual(runtime.port, port)
            self.assertEqual(occupied.getsockname()[1], port)

    def test_missing_data_releases_lock_and_does_not_create_save_folder(self):
        with self.assertRaisesRegex(RuntimeError, "Bundled league data"):
            desktop_runtime.DesktopRuntime(self.data, self.data, 0)
        self.assertFalse((self.data / "runtime.json").exists())
        self.assertFalse((self.data / "saves").exists())
        self.start()

    def test_permission_bind_error_is_not_mistaken_for_port_collision(self):
        with patch.object(desktop_runtime, "make_gui_server", side_effect=OSError(errno.EACCES, "denied")) as make:
            with self.assertRaises(OSError):
                self.start()
            self.assertEqual(make.call_count, 1)
        self.start()

    def test_shutdown_drains_active_request_before_releasing_lock(self):
        runtime = self.start()
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        result = []
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(runtime.url + "/api/session") as response:
            token = json.load(response)["token"]
        def dispatch(*args, **kwargs):
            entered.set()
            release.wait(5)
            return {"finished": True}
        def request():
            try:
                req = urllib.request.Request(runtime.url + "/api/action", data=b'{"action":"teams","payload":{}}',
                                             headers={"Content-Type": "application/json", "X-NBA-GM-Token": token})
                with opener.open(req, timeout=10) as response:
                    result.append(json.load(response))
            finally:
                done.set()
        with patch.object(app_server, "dispatch_app_action", side_effect=dispatch):
            caller = threading.Thread(target=request)
            caller.start()
            self.assertTrue(entered.wait(5))
            stopper = threading.Thread(target=runtime.stop)
            stopper.start()
            try:
                time.sleep(.7)
                self.assertTrue(stopper.is_alive())
                self.assertTrue(runtime.lock.owned)
            finally:
                release.set()
                caller.join(10)
                stopper.join(10)
        self.assertTrue(done.is_set())
        self.assertEqual(result[0]["result"], {"finished": True})
        self.assertFalse(runtime.lock.owned)
        self.assertFalse(runtime.runtime_path.exists())

    def test_source_launcher_stop_protocol_duplicate_and_exit_status(self):
        command = [sys.executable, "-B", str(ROOT / "packaging/windows/launcher.py"),
                   "--headless", "--no-browser", "--data-dir", str(self.data), "--port", "0"]
        environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        process = subprocess.Popen(command, cwd=self.data, env=environment)
        runtime_path = self.data / "runtime.json"
        try:
            for _ in range(200):
                if process.poll() is not None:
                    self.fail(f"Source launcher exited {process.returncode}")
                if runtime_path.exists():
                    break
                time.sleep(.05)
            else:
                self.fail("Source launcher never became ready")
            info = json.loads(runtime_path.read_text())
            self.assertEqual(info["pid"], process.pid)
            second = subprocess.run(command, cwd=self.data, env=environment, timeout=15)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(json.loads(runtime_path.read_text()), info)
            (self.data / "verification-stop.request").touch()
            self.assertEqual(process.wait(timeout=15), 0)
            self.assertFalse(runtime_path.exists())
            self.assertFalse((self.data / "verification-stop.request").exists())
        finally:
            if process.poll() is None:
                (self.data / "verification-stop.request").touch()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    unittest.main()
