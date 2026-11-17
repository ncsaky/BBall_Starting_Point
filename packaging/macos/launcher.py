"""Private macOS beta entry point. The ordinary server/CLI stay unchanged."""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

from nba_gm_data.app_server import make_gui_server
from nba_gm_data.resource_paths import game_resource_root


APP_NAME = "NBA GM Sandbox"


class LogStream:
    def __init__(self, logger, level):
        self.logger, self.level = logger, level

    def write(self, value):
        if value.strip():
            self.logger.log(self.level, value.rstrip())
        return len(value)

    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()


def configure_logging(data_dir):
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("macos-launcher")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(logs / "launcher.log", maxBytes=2_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    sys.stdout = LogStream(logger, logging.INFO)
    sys.stderr = LogStream(logger, logging.INFO)
    return logger


def live_instance(runtime_path):
    try:
        info = json.loads(runtime_path.read_text())
        port = int(info["port"])
        if not 1 <= port <= 65535:
            return None
        url = f"http://127.0.0.1:{port}"
        # Do not inherit a network proxy for local health checks.
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            url + "/api/session", timeout=1
        ) as response:
            if isinstance(json.load(response).get("token"), str):
                return url
    except (OSError, ValueError, KeyError):
        pass
    return None


class Runtime:
    def __init__(self, root, data_dir, preferred_port):
        self.root, self.data_dir = root, data_dir
        self.runtime_path = data_dir / "runtime.json"
        self.lock_file = (data_dir / "server.lock").open("a+")
        self.server = None
        self.thread = None
        self.stopped = False
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock_file.close()
            self.lock_file = None
            self.existing_url = None
            for _ in range(50):
                self.existing_url = live_instance(self.runtime_path)
                if self.existing_url:
                    break
                time.sleep(0.1)
            if not self.existing_url:
                raise RuntimeError("Another copy is starting or busy. Quit it from its Dock icon and try again.")
            return
        self.existing_url = None
        try:
            # A missing bundled universe is an installation error, never a
            # reason to ingest raw developer files or write into the bundle.
            if not (root / "data/canonical/universe_2026_27_offseason.json").is_file():
                raise RuntimeError("The app's bundled league data is missing. Extract a fresh copy of the beta.")
            saves = data_dir / "saves"
            saves.mkdir(parents=True, exist_ok=True)
            try:
                self.server = make_gui_server(root, saves, host="127.0.0.1", port=preferred_port)
            except OSError as exc:
                if exc.errno != errno.EADDRINUSE:
                    raise
                self.server = make_gui_server(root, saves, host="127.0.0.1", port=0)
            # Let any in-flight save transaction finish when the app quits.
            self.server.daemon_threads = False
            self.port = self.server.server_address[1]
            self.url = f"http://127.0.0.1:{self.port}"
            self.server.multiplayer_scheduler.start()
            self.thread = threading.Thread(target=self.server.serve_forever, name="local-game-server")
            self.thread.start()
            temporary = data_dir / "runtime.json.tmp"
            temporary.write_text(json.dumps({
                "pid": os.getpid(), "port": self.port, "url": self.url,
                "root": str(root), "save_dir": str(saves),
            }, indent=2))
            temporary.replace(self.runtime_path)
            print(f"Server ready: {self.url}; saves: {saves}")
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.stopped or self.lock_file is None:
            return
        self.stopped = True
        if self.server:
            if self.thread and self.thread.is_alive():
                self.server.shutdown()
                self.thread.join()
            self.server.server_close()
        self.runtime_path.unlink(missing_ok=True)
        fcntl.flock(self.lock_file, fcntl.LOCK_UN)
        self.lock_file.close()
        self.lock_file = None
        print("Server stopped; saves retained.")


def show_error(message):
    try:
        from AppKit import NSAlert, NSApplication
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(0)
        app.activateIgnoringOtherApps_(True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"{APP_NAME} could not start")
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.runModal()
    except Exception:
        print(message, file=sys.stderr)


def run_control_window(runtime, open_browser):
    # Cocoa is supplied by macOS; only the small Python bridge is bundled.
    from AppKit import (
        NSApplication, NSBackingStoreBuffered, NSButton, NSFont, NSMakeRect,
        NSMenu, NSMenuItem, NSObject, NSTextField, NSWindow, NSWorkspace,
        NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
        NSWindowStyleMaskMiniaturizable,
    )
    from Foundation import NSURL, NSTimer

    class Controller(NSObject):
        def checkStop_(self, timer):
            if stop_requested.is_set():
                self.stopServer_(None)

        def openBrowser_(self, sender):
            if not NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(runtime.url)):
                show_error(f"Open this address in your browser: {runtime.url}")
            else:
                print(f"Default browser open requested: {runtime.url}")

        def showSaves_(self, sender):
            NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(str(runtime.data_dir / "saves")))

        def stopServer_(self, sender):
            NSApplication.sharedApplication().terminate_(None)

        def applicationShouldTerminateAfterLastWindowClosed_(self, app):
            return True

        def applicationWillTerminate_(self, notification):
            runtime.stop()

        def applicationShouldHandleReopen_hasVisibleWindows_(self, app, visible):
            self.window.makeKeyAndOrderFront_(None)
            self.openBrowser_(None)
            return True

    app = NSApplication.sharedApplication()
    stop_requested = threading.Event()
    signal.signal(signal.SIGTERM, lambda *args: stop_requested.set())
    signal.signal(signal.SIGINT, lambda *args: stop_requested.set())
    app.setActivationPolicy_(0)
    controller = Controller.alloc().init()
    app.setDelegate_(controller)
    menu = NSMenu.alloc().init()
    app_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(APP_NAME, None, "")
    submenu = NSMenu.alloc().initWithTitle_(APP_NAME)
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Stop Server & Quit", "stopServer:", "q")
    quit_item.setTarget_(controller)
    submenu.addItem_(quit_item)
    app_item.setSubmenu_(submenu)
    menu.addItem_(app_item)
    app.setMainMenu_(menu)
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 560, 250),
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable,
        NSBackingStoreBuffered, False,
    )
    controller.window = window
    window.setTitle_(APP_NAME + " — Private Beta")
    window.setReleasedWhenClosed_(False)
    window.center()
    content = window.contentView()
    for y, height, text, size in (
        (202, 28, "Your local game server is running", 18),
        (172, 24, runtime.url, 14),
        (137, 24, "Play in your browser. Keep this app open while playing.", 13),
        (109, 24, "Wait for simulation to finish before stopping the server.", 13),
        (76, 26, "Saves and backups stay on this Mac when you replace the app.", 12),
    ):
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(24, y, 512, height))
        label.setStringValue_(text)
        label.setEditable_(False)
        label.setSelectable_(True)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setFont_(NSFont.systemFontOfSize_(size))
        content.addSubview_(label)
    for x, width, title, action in (
        (20, 145, "Open Browser", "openBrowser:"),
        (174, 145, "Show Saves", "showSaves:"),
        (328, 210, "Stop Server & Quit", "stopServer:"),
    ):
        button = NSButton.alloc().initWithFrame_(NSMakeRect(x, 24, width, 34))
        button.setTitle_(title)
        button.setBezelStyle_(1)
        button.setTarget_(controller)
        button.setAction_(action)
        content.addSubview_(button)
    window.makeKeyAndOrderFront_(None)
    app.activateIgnoringOtherApps_(True)
    if open_browser:
        controller.openBrowser_(None)
    timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        0.25, controller, "checkStop:", None, True
    )
    print("Native control window ready.")
    app.run()
    timer.invalidate()


def main():
    parser = argparse.ArgumentParser(description="Start the private macOS beta.")
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get(
        "NBA_GM_USER_DATA_DIR", str(Path.home() / "Library/Application Support" / APP_NAME)
    )))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--headless", action="store_true", help="Packaged-artifact verification only.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    data_dir = args.data_dir.expanduser().resolve()
    runtime = None
    logger = None
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        logger = configure_logging(data_dir)
        runtime = Runtime(game_resource_root(), data_dir, args.port)
        if runtime.existing_url:
            if not args.no_browser:
                webbrowser.open(runtime.existing_url)
            return 0
        def interrupted(signum, frame):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        if args.headless:
            if not args.no_browser:
                webbrowser.open(runtime.url)
            while runtime.thread.is_alive():
                time.sleep(0.25)
        else:
            run_control_window(runtime, not args.no_browser)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        if logger:
            logger.error(traceback.format_exc())
        message = f"{exc}\n\nYour saves are in:\n{data_dir / 'saves'}\n\nStartup log:\n{data_dir / 'logs/launcher.log'}"
        if args.headless:
            print(message, file=sys.stderr)
        else:
            show_error(message)
        return 1
    finally:
        if runtime:
            runtime.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
