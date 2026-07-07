from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .app_actions import AppActionError, dispatch_app_action
from .schema import to_plain


GUI_DIR = Path(__file__).with_name("gui")


def run_gui_server(
    root: str | Path = ".",
    save_dir: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
) -> ThreadingHTTPServer:
    server = make_gui_server(root=root, save_dir=save_dir, host=host, port=port)
    url = f"http://{host}:{server.server_address[1]}"
    print(f"NBA GM Sandbox GUI running at {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping GUI server.")
    finally:
        server.server_close()
    return server


def make_gui_server(
    root: str | Path = ".",
    save_dir: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    root_path = Path(root).resolve()
    save_path = Path(save_dir).resolve() if save_dir else None

    class Handler(GuiRequestHandler):
        app_root = root_path
        app_save_dir = save_path

    return ThreadingHTTPServer((host, int(port)), Handler)


class GuiRequestHandler(BaseHTTPRequestHandler):
    app_root: Path = Path(".")
    app_save_dir: Path | None = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.write_json(dispatch_app_action("runtime_status", root=self.app_root, save_dir=self.app_save_dir))
            return
        path = "index.html" if parsed.path in {"", "/"} else parsed.path.lstrip("/")
        static_path = (GUI_DIR / path).resolve()
        try:
            static_path.relative_to(GUI_DIR.resolve())
        except ValueError:
            self.send_error(404)
            return
        if not static_path.exists() or not static_path.is_file():
            self.send_error(404)
            return
        content_type = mimetypes.guess_type(static_path.name)[0] or "application/octet-stream"
        data = static_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/action":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            action = str(payload.get("action") or "")
            if not action:
                raise AppActionError("Missing action.")
            result = dispatch_app_action(
                action,
                payload.get("payload") or {},
                root=self.app_root,
                save_dir=self.app_save_dir,
            )
            self.write_json({"ok": True, "result": result})
        except Exception as exc:
            status = 400 if isinstance(exc, (AppActionError, ValueError, KeyError)) else 500
            self.write_json({"ok": False, "error": str(exc), "error_type": type(exc).__name__}, status=status)

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(to_plain(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local NBA GM Sandbox GUI.")
    parser.add_argument("--root", default=".", help="Project/game root containing data and saves.")
    parser.add_argument("--save-dir", default=None, help="Optional save directory override.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the GUI in the default browser.")
    args = parser.parse_args(argv)
    run_gui_server(args.root, args.save_dir, args.host, args.port, args.open)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
