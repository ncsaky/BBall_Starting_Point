"""Local desktop server lifecycle; Windows launcher, POSIX test support."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import threading
import time
import urllib.request

from .app_server import make_gui_server


class InstanceLock:
    def __init__(self, path: Path):
        self.handle = path.open("a+b")
        self.owned = False

    def acquire(self) -> bool:
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0, os.SEEK_END)
                if not self.handle.tell():
                    self.handle.write(b"\0")
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.owned = True
            return True
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                self.close()
                raise
            return False

    def close(self):
        if self.handle.closed:
            return
        try:
            if self.owned:
                if os.name == "nt":
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.owned = False
            self.handle.close()


def live_instance(runtime_path: Path) -> str | None:
    try:
        info = json.loads(runtime_path.read_text())
        port = int(info["port"])
        if not 1 <= port <= 65535:
            return None
        url = f"http://127.0.0.1:{port}"
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url + "/api/session", timeout=1) as response:
            session = json.load(response)
            if isinstance(session, dict) and isinstance(session.get("token"), str):
                return url
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


class DesktopRuntime:
    def __init__(self, root: Path, data_dir: Path, preferred_port: int = 8765):
        self.root, self.data_dir = root, data_dir
        self.runtime_path = data_dir / "runtime.json"
        self.stop_request = data_dir / "verification-stop.request"
        self.server = self.thread = None
        self.stopped = False
        self.existing_url = None
        self.lock = InstanceLock(data_dir / "server.lock")
        if not self.lock.acquire():
            self.lock.close()
            for _ in range(50):
                self.existing_url = live_instance(self.runtime_path)
                if self.existing_url:
                    return
                time.sleep(.1)
            raise RuntimeError("Another copy is starting or busy. Close its control window and try again.")
        try:
            if not (root / "data/canonical/universe_2026_27_offseason.json").is_file():
                raise RuntimeError("Bundled league data is missing. Extract a fresh copy of the game.")
            self.stop_request.unlink(missing_ok=True)
            saves = data_dir / "saves"
            saves.mkdir(parents=True, exist_ok=True)
            try:
                self.server = make_gui_server(root, saves, host="127.0.0.1", port=preferred_port)
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) != 10048:
                    raise
                self.server = make_gui_server(root, saves, host="127.0.0.1", port=0)
            self.server.daemon_threads = False
            self.port = self.server.server_address[1]
            self.url = f"http://127.0.0.1:{self.port}"
            self.server.multiplayer_scheduler.start()
            self.thread = threading.Thread(target=self.server.serve_forever, name="local-game-server")
            self.thread.start()
            temporary = data_dir / "runtime.json.tmp"
            temporary.write_text(json.dumps({"pid": os.getpid(), "port": self.port, "url": self.url}, indent=2))
            temporary.replace(self.runtime_path)
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.stopped or not self.lock.owned:
            return
        self.stopped = True
        try:
            if self.server:
                if self.thread and self.thread.is_alive():
                    self.server.shutdown()
                    self.thread.join()
                self.server.server_close()
            self.runtime_path.unlink(missing_ok=True)
            self.stop_request.unlink(missing_ok=True)
        finally:
            self.lock.close()
