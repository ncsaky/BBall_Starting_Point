from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import re
import secrets
import socket
import sys
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer
from typing import Any
from urllib.parse import urlparse

from .app_actions import (
    AppActionError, dispatch_app_action, load_app_canonical,
    resolve_app_save_path, safe_filename, validate_app_save_paths,
)
from .save_recovery import MAX_ARCHIVE_BYTES
from .simulation_progress import progress_listener
from .multiplayer import (
    DEFAULT_MULTIPLAYER_DB,
    MULTIPLAYER_PROTOCOL_VERSION,
    MultiplayerAuthenticationError,
    MultiplayerAuthorizationError,
    MultiplayerConflictError,
    MultiplayerError,
    MultiplayerNotFoundError,
    MultiplayerScheduler,
    MultiplayerService,
    MultiplayerStore,
)
from .schema import to_plain


GUI_DIR = Path(__file__).with_name("gui")
MAX_JSON_BODY_BYTES = 1024 * 1024
# Base64 expands the existing compressed archive limit by 4/3. Reserve one
# ordinary request's worth of space for the JSON envelope and save name.
MAX_BACKUP_BODY_BYTES = ((MAX_ARCHIVE_BYTES + 2) // 3) * 4 + MAX_JSON_BODY_BYTES
API_TOKEN_HEADER = "X-NBA-GM-Token"
BACKUP_UPLOAD_HEADER = "X-NBA-GM-Backup-Upload"


class RequestRejected(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def parse_origin(value: str) -> tuple[str, str, int]:
    """Accept an exact HTTP origin, never credentials, paths or wildcard hosts."""
    parsed = urlparse(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.params or parsed.query or parsed.fragment
            or not re.fullmatch(r"https?://[^/?#]+", value, flags=re.IGNORECASE)
            or re.search(r"[\s\\%]", value) or value.endswith(":")):
        raise ValueError("Expected an exact http(s) origin without a path.")
    host = parsed.hostname.lower()
    if ":" in host:
        ipaddress.IPv6Address(host)
        valid_authority = re.fullmatch(r"\[[0-9a-f:.]+\](?::[0-9]+)?", parsed.netloc.lower())
    else:
        valid_authority = re.fullmatch(r"[a-z0-9.-]+(?::[0-9]+)?", parsed.netloc.lower())
    if not valid_authority:
        raise ValueError("Invalid origin host.")
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    if not 1 <= port <= 65535:
        raise ValueError("Invalid origin port.")
    return parsed.scheme, host, port


def run_gui_server(
    root: str | Path = ".",
    save_dir: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
    public_multiplayer_only: bool = False,
    allowed_origins: tuple[str, ...] = (),
) -> ThreadingHTTPServer:
    server = make_gui_server(
        root=root,
        save_dir=save_dir,
        host=host,
        port=port,
        public_multiplayer_only=public_multiplayer_only,
        allowed_origins=allowed_origins,
    )
    server.multiplayer_scheduler.start()
    address = f"[{host}]" if ":" in host else host
    url = f"http://{address}:{server.server_address[1]}"
    print(f"NBA GM Sandbox GUI running at {url}")
    if host not in {"127.0.0.1", "localhost", "::1"} or allowed_origins:
        print("Explicit network test: reachable clients can use multiplayer; use --public-multiplayer-only to isolate local saves.")
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
    public_multiplayer_only: bool = False,
    allowed_origins: tuple[str, ...] = (),
) -> "GuiThreadingHTTPServer":
    root_path = Path(root).resolve()
    save_path = Path(save_dir).resolve() if save_dir else (root_path / "saves").resolve()
    effective_save_path = save_path
    origins = frozenset(parse_origin(value) for value in allowed_origins)
    canonical = load_app_canonical(root_path)
    multiplayer_store = MultiplayerStore(effective_save_path / DEFAULT_MULTIPLAYER_DB)
    multiplayer_service = MultiplayerService(
        multiplayer_store,
        root=root_path,
        save_dir=effective_save_path,
        canonical=canonical,
        dispatcher=dispatch_app_action,
    )

    class Handler(GuiRequestHandler):
        app_root = root_path
        app_save_dir = save_path
        app_canonical = canonical
        app_multiplayer = multiplayer_service
        app_public_multiplayer_only = bool(public_multiplayer_only)

    server_class = GuiThreadingHTTPServer
    if ":" in host:
        class IPv6GuiServer(GuiThreadingHTTPServer):
            address_family = socket.AF_INET6
        server_class = IPv6GuiServer
    server = server_class((host, int(port)), Handler)
    server.api_token = secrets.token_urlsafe(32)
    server.allowed_origins = origins
    server.bind_host = host.lower()
    server.multiplayer_scheduler = MultiplayerScheduler(multiplayer_service)
    server.simulation_control_lock = threading.Lock()
    server.active_simulation = None
    return server


class GuiThreadingHTTPServer(ThreadingHTTPServer):
    multiplayer_scheduler: MultiplayerScheduler
    api_token: str
    allowed_origins: frozenset[tuple[str, str, int]]
    bind_host: str
    simulation_control_lock: threading.Lock
    active_simulation: tuple[str, threading.Event] | None

    def request_simulation_stop(self, simulation_id: str) -> dict[str, str]:
        with self.simulation_control_lock:
            active = self.active_simulation
            if not active or not secrets.compare_digest(active[0], simulation_id):
                return {"status": "not_running"}
            active[1].set()
            return {"status": "stop_requested"}

    def server_bind(self) -> None:
        if self.server_address[0] in {"127.0.0.1", "::1"}:
            # HTTPServer normally calls getfqdn() here. A loopback game must
            # start without a DNS/mDNS round trip, including offline Macs.
            TCPServer.server_bind(self)
            self.server_name = "localhost"
            self.server_port = self.server_address[1]
        else:
            super().server_bind()

    def server_close(self) -> None:
        scheduler = getattr(self, "multiplayer_scheduler", None)
        if scheduler:
            scheduler.stop()
        super().server_close()


class GuiRequestHandler(BaseHTTPRequestHandler):
    app_root: Path = Path(".")
    app_save_dir: Path | None = None
    app_canonical: dict[str, Any] | None = None
    app_multiplayer: MultiplayerService | None = None
    app_public_multiplayer_only: bool = False

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(30)

    def validate_request(self, *, token: bool = False) -> None:
        hosts = self.headers.get_all("Host", [])
        try:
            if len(hosts) != 1:
                raise ValueError("Missing or duplicate Host.")
            authority = parse_origin("http://" + hosts[0])
            _, hostname, port = authority
            local_port = self.server.server_address[1]
            local_address = self.connection.getsockname()[0]
            bind_address = self.server.server_address[0]
            loopback = ipaddress.ip_address(bind_address).is_loopback
            try:
                host_address = ipaddress.ip_address(hostname)
                local_host = host_address.is_loopback if loopback else host_address == ipaddress.ip_address(local_address)
            except ValueError:
                local_host = hostname == "localhost" if loopback else hostname == self.server.bind_host
            direct = local_host and port == local_port
            explicit_port = urlparse("http://" + hosts[0]).port
            external_origins = {
                origin for origin in self.server.allowed_origins
                if hostname == origin[1] and (
                    explicit_port == origin[2] if explicit_port is not None
                    else origin[2] == (443 if origin[0] == "https" else 80)
                )
            }
            external = bool(external_origins)
            if not (direct or external):
                raise ValueError("Host is not an allowed server address.")
        except ValueError as exc:
            raise RequestRejected(403, "Invalid Host header.") from exc

        origins = self.headers.get_all("Origin", [])
        if origins:
            try:
                origin = parse_origin(origins[0])
                if len(origins) != 1 or not (
                    (direct and origin == authority) or origin in external_origins
                ):
                    raise ValueError("Origin does not match this server.")
            except ValueError as exc:
                raise RequestRejected(403, "Invalid Origin header.") from exc
        # Also guard no-Origin resource/navigation requests to the token endpoint.
        sites = self.headers.get_all("Sec-Fetch-Site", [])
        path = urlparse(self.path).path
        top_level_game_navigation = (
            self.command == "GET"
            and not token
            and path in {"/", "/index.html"}
            and sites == ["cross-site"]
            and self.headers.get_all("Sec-Fetch-Mode", []) == ["navigate"]
            and self.headers.get_all("Sec-Fetch-Dest", []) == ["document"]
        )
        if len(sites) > 1 or (
            sites
            and sites[0] not in {"same-origin", "none"}
            and not top_level_game_navigation
        ):
            raise RequestRejected(403, "Cross-site browser requests are not allowed.")
        if token:
            tokens = self.headers.get_all(API_TOKEN_HEADER, [])
            if len(tokens) != 1 or not secrets.compare_digest(tokens[0].encode("utf-8"), self.server.api_token.encode("ascii")):
                raise RequestRejected(403, "The local game session is invalid. Refresh the page to reconnect.")

    def reject(self, exc: RequestRejected) -> None:
        self.close_connection = True
        self.write_json({"ok": False, "error": str(exc), "error_type": type(exc).__name__}, status=exc.status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            self.validate_request(token=parsed.path.startswith("/api/") and parsed.path != "/api/session")
        except RequestRejected as exc:
            self.reject(exc)
            return
        if parsed.path == "/api/session":
            self.write_json({"token": self.server.api_token})
            return
        if parsed.path == "/api/status":
            status = dispatch_app_action("runtime_status", root=self.app_root, save_dir=self.app_save_dir, canonical=self.app_canonical)
            if self.app_public_multiplayer_only:
                status.pop("root", None)
                status.pop("save_dir", None)
                status["actions"] = ["list_saves", "runtime_status", "teams"]
            status["multiplayer"] = {
                "protocol_version": MULTIPLAYER_PROTOCOL_VERSION,
                "available": self.app_multiplayer is not None,
                "transport": "revisioned_http_polling",
                "authoritative_server": True,
                "public_multiplayer_only": self.app_public_multiplayer_only,
            }
            self.write_json(status)
            return
        self.serve_static(parsed.path)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        try:
            self.validate_request(token=parsed.path.startswith("/api/") and parsed.path != "/api/session")
        except RequestRejected as exc:
            self.reject(exc)
            return
        if parsed.path.startswith("/api/"):
            self.send_error(405)
            return
        self.serve_static(parsed.path, head_only=True)

    def serve_static(self, url_path: str, *, head_only: bool = False) -> None:
        path = "index.html" if url_path in {"", "/"} else url_path.lstrip("/")
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
        stat = static_path.stat()
        size = stat.st_size
        etag = f'"{stat.st_mtime_ns:x}-{size:x}"'
        cache_control = "public, max-age=86400" if path.startswith("assets/") else "no-cache"
        if not self.headers.get("Range") and self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", cache_control)
            self.end_headers()
            return
        start, end = 0, size - 1
        partial = False
        media = content_type.startswith(("video/", "audio/"))
        ranges = self.headers.get_all("Range", [])
        if media and ranges:
            match = re.fullmatch(r"bytes=([0-9]{0,20})-([0-9]{0,20})", ranges[0]) if len(ranges) == 1 else None
            try:
                if not match or not any(match.groups()) or not size:
                    raise ValueError("Invalid byte range")
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                else:
                    suffix = int(right)
                    if not suffix:
                        raise ValueError("Empty suffix range")
                    start = max(0, size - suffix)
                if start >= size or end < start:
                    raise ValueError("Unsatisfiable byte range")
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            partial = True
        length = max(0, end - start + 1)
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        self.send_header("ETag", etag)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Length", str(length))
        if media:
            self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if not head_only:
            with static_path.open("rb") as stream:
                stream.seek(start)
                remaining = length
                while remaining:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        # Video range requests are routinely cancelled on navigation.
                        return
                    remaining -= len(chunk)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/action", "/api/action/stream", "/api/multiplayer"}:
            self.send_error(404)
            return
        try:
            self.validate_request(token=True)
            payload, length = self.read_payload()
            action = payload.get("action")
            if not isinstance(action, str) or not action:
                raise AppActionError("Missing action.")
            action = action.replace("-", "_")
            action_payload = payload.get("payload", {})
            if not isinstance(action_payload, dict):
                raise AppActionError("Action payload must be a JSON object.")
            if length > MAX_JSON_BODY_BYTES and not (parsed.path == "/api/action" and action == "restore_save"):
                raise RequestRejected(413, "Only backup restore requests may exceed the ordinary JSON limit.")
            if parsed.path in {"/api/action", "/api/action/stream"}:
                self.validate_save_paths(action, action_payload)
            elif action == "game_action":
                game_action = str(action_payload.get("game_action") or "").replace("-", "_")
                if game_action in {"runtime_status", "diagnostic_runtime", "list_saves", "create_save", "export_save", "restore_save", "recover_save"}:
                    raise MultiplayerAuthorizationError("Local save management is unavailable through multiplayer.")
                nested_payload = action_payload.get("action_payload", {})
                if not isinstance(nested_payload, dict):
                    raise AppActionError("Game action payload must be a JSON object.")
                self.validate_save_paths(game_action, nested_payload)
            if parsed.path == "/api/action/stream":
                if action != "advance_save":
                    raise AppActionError("Only simulation advancement supports progress streaming.")
                if self.app_public_multiplayer_only:
                    raise MultiplayerAuthorizationError("Local simulation is unavailable on this server.")
                self.stream_simulation(action_payload, payload.get("simulation_id"))
                return
            if parsed.path == "/api/action" and action == "cancel_simulation":
                if self.app_public_multiplayer_only:
                    raise MultiplayerAuthorizationError("Local simulation is unavailable on this server.")
                simulation_id = str(action_payload.get("simulation_id") or "")
                if not simulation_id or len(simulation_id) > 128:
                    raise AppActionError("A valid simulation id is required to stop simulation.")
                self.write_json({"ok": True, "result": self.server.request_simulation_stop(simulation_id)})
                return
            if parsed.path == "/api/multiplayer":
                if self.app_multiplayer is None:
                    raise MultiplayerError("Multiplayer service is unavailable.")
                result = self.app_multiplayer.dispatch(action, action_payload)
            else:
                if self.app_public_multiplayer_only and action == "list_saves":
                    result = {"save_count": 0, "saves": []}
                elif self.app_public_multiplayer_only and action not in {"runtime_status", "teams"}:
                    raise MultiplayerAuthorizationError(
                        "This public test server only permits multiplayer leagues."
                    )
                else:
                    result = dispatch_app_action(
                        action,
                        action_payload,
                        root=self.app_root,
                        save_dir=self.app_save_dir,
                        canonical=self.app_canonical,
                    )
                    if self.app_public_multiplayer_only and action == "runtime_status":
                        result.pop("root", None)
                        result.pop("save_dir", None)
                        result["actions"] = ["list_saves", "runtime_status", "teams"]
            self.write_json({"ok": True, "result": result})
        except RequestRejected as exc:
            self.reject(exc)
        except Exception as exc:
            if isinstance(exc, MultiplayerConflictError):
                status = 409
            elif isinstance(exc, MultiplayerAuthenticationError):
                status = 401
            elif isinstance(exc, MultiplayerAuthorizationError):
                status = 403
            elif isinstance(exc, MultiplayerNotFoundError):
                status = 404
            else:
                status = 400 if isinstance(exc, (AppActionError, MultiplayerError, ValueError, KeyError, TypeError, RecursionError)) else 500
            error = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
            if isinstance(exc, MultiplayerConflictError):
                error["current_revision"] = exc.current_revision
            self.write_json(error, status=status)

    def stream_simulation(self, payload: dict[str, Any], simulation_id: Any) -> None:
        simulation_id = str(simulation_id or "")
        if not simulation_id or len(simulation_id) > 128:
            self.write_json({"ok": False, "error": "A valid simulation id is required.", "error_type": "AppActionError"}, status=400)
            return
        stop_event = threading.Event()
        with self.server.simulation_control_lock:
            if self.server.active_simulation is not None:
                self.write_json({"ok": False, "error": "A simulation is already running.", "error_type": "AppActionError"}, status=409)
                return
            self.server.active_simulation = (simulation_id, stop_event)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        connected = True

        def send(message):
            nonlocal connected
            if not connected:
                return
            try:
                self.wfile.write((json.dumps(message, ensure_ascii=True) + "\n").encode("utf-8"))
                self.wfile.flush()
            except (OSError, TimeoutError):
                connected = False

        send({"type":"progress", "event":{"kind":"start"}})
        try:
            with progress_listener(lambda event:send({"type":"progress", "event":event}), stop_event=stop_event):
                result = dispatch_app_action("advance_save", payload, root=self.app_root,
                                             save_dir=self.app_save_dir, canonical=self.app_canonical)
            send({"type":"result", "result":result})
        except Exception as exc:
            send({"type":"error", "error":str(exc), "error_type":type(exc).__name__})
        finally:
            with self.server.simulation_control_lock:
                active = self.server.active_simulation
                if active and active[0] == simulation_id:
                    self.server.active_simulation = None

    def read_payload(self) -> tuple[dict[str, Any], int]:
        if (len(self.headers.get_all("Content-Type", [])) != 1
                or self.headers.get_content_type() != "application/json"
                or self.headers.get_content_charset("utf-8").lower() != "utf-8"):
            raise RequestRejected(415, "Use application/json with UTF-8 encoding.")
        if self.headers.get_all("Transfer-Encoding") or self.headers.get_all("Content-Encoding"):
            raise RequestRejected(400, "Encoded or chunked request bodies are not supported.")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
            raise RequestRejected(400, "Supply one valid Content-Length.")
        length = int(lengths[0])
        backup = self.headers.get_all(BACKUP_UPLOAD_HEADER, []) == ["1"]
        limit = MAX_BACKUP_BODY_BYTES if backup and urlparse(self.path).path == "/api/action" else MAX_JSON_BODY_BYTES
        if length > limit:
            raise RequestRejected(413, "Request body exceeds the allowed size limit.")
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request body.")
            def reject_constant(value: str) -> None:
                raise ValueError(f"Invalid JSON constant: {value}")
            payload = json.loads(body.decode("utf-8"), parse_constant=reject_constant)
            if not isinstance(payload, dict):
                raise ValueError("Request must be a JSON object.")
        except (ValueError, RecursionError, TimeoutError) as exc:
            raise RequestRejected(400, "Malformed, incomplete or timed-out JSON body.") from exc
        return payload, length

    def validate_save_paths(self, action: str, payload: dict[str, Any]) -> None:
        saves = self.app_save_dir or self.app_root / "saves"
        validate_app_save_paths(saves, payload)
        if action in {"create_save", "restore_save"}:
            if payload.get("save_name"):
                resolve_app_save_path(saves, {"save_name": safe_filename(str(payload["save_name"]))})
        elif any(payload.get(key) for key in ("save_path", "path", "save_name", "save_id")):
            resolve_app_save_path(saves, payload)

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(to_plain(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local NBA GM Sandbox GUI.")
    parser.add_argument("--root", default=".", help="Project/game root containing data and saves.")
    parser.add_argument("--save-dir", default=None, help="Optional save directory override.")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback by default; a non-loopback address explicitly enables network testing.")
    parser.add_argument("--allowed-origin", action="append", default=[], help="Exact external http(s) origin for an explicit proxy/tunnel test; repeatable, no wildcards.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the GUI in the default browser.")
    parser.add_argument(
        "--public-multiplayer-only",
        action="store_true",
        help="Expose multiplayer while hiding and blocking local single-player saves.",
    )
    args = parser.parse_args(argv)
    run_gui_server(
        args.root,
        args.save_dir,
        args.host,
        args.port,
        args.open,
        args.public_multiplayer_only,
        tuple(args.allowed_origin),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
