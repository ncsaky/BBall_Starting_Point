"""Private Windows beta entry point; no changes to CLI or Mac launch behavior."""

import argparse
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import signal
import sys
import threading
import time
import webbrowser

from nba_gm_data.desktop_runtime import DesktopRuntime
from nba_gm_data.resource_paths import game_resource_root


APP_NAME = "NBA GM Sandbox"


def default_data_dir():
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    return Path(os.environ.get("NBA_GM_USER_DATA_DIR") or base / APP_NAME)


class LogStream:
    def __init__(self, logger):
        self.logger = logger

    def write(self, value):
        if value.strip():
            self.logger.info(value.rstrip())
        return len(value)

    def flush(self):
        for handler in self.logger.handlers:
            handler.flush()


def configure_logging(data_dir):
    logs = data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("windows-launcher")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(logs / "launcher.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    sys.stdout = sys.stderr = LogStream(logger)
    return logger


def show_error(message):
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME + " could not start", 0x10)
    else:
        print(message, file=sys.stderr)


def run_control_window(runtime, open_browser, stop_requested):
    import tkinter as tk
    from tkinter import ttk
    window = tk.Tk()
    window.title(APP_NAME + " - Private Beta")
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Your local game is running", font=("Segoe UI", 16)).pack(anchor="w")
    ttk.Label(frame, text=runtime.url, font=("Segoe UI", 11)).pack(anchor="w", pady=(8, 12))
    status = ttk.Label(frame, text="Keep this window open while playing. Saves stay on this PC.")
    status.pack(anchor="w")
    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=(18, 0))
    stopped = threading.Event()
    closing = False

    def open_game():
        if not webbrowser.open(runtime.url):
            show_error("Open this address in your browser:\n" + runtime.url)

    def close():
        nonlocal closing
        if closing:
            return
        closing = True
        status.configure(text="Finishing active save operations before quitting...")
        for button in controls.winfo_children():
            button.configure(state="disabled")
        def shutdown():
            try:
                runtime.stop()
            finally:
                stopped.set()
        threading.Thread(target=shutdown, name="graceful-desktop-quit").start()

    def tick():
        if stopped.is_set():
            window.destroy()
            return
        if stop_requested.is_set():
            close()
        window.after(100, tick)

    for label, command in [("Open Browser", open_game), ("Show Saves", lambda: os.startfile(runtime.data_dir / "saves")), ("Stop Server & Quit", close)]:
        ttk.Button(controls, text=label, command=command).pack(side="left", padx=(0, 8))
    icon = game_resource_root() / "app-icon.png"
    if icon.is_file():
        window._icon = tk.PhotoImage(file=icon)
        window.iconphoto(True, window._icon)
    window.protocol("WM_DELETE_WINDOW", close)
    window.after(100, tick)
    if open_browser:
        window.after(100, open_game)
    window.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Start the private Windows beta.")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--headless", action="store_true", help="Packaged-artifact verification only.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    data_dir = args.data_dir.expanduser().resolve()
    runtime = logger = None
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        logger = configure_logging(data_dir)
        runtime = DesktopRuntime(game_resource_root(), data_dir, args.port)
        if runtime.existing_url:
            if not args.no_browser:
                webbrowser.open(runtime.existing_url)
            return 0
        stop_requested = threading.Event()
        for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), lambda *args: stop_requested.set())
        if args.headless:
            if not args.no_browser:
                webbrowser.open(runtime.url)
            while not stop_requested.is_set() and not runtime.stop_request.exists():
                time.sleep(.1)
        else:
            run_control_window(runtime, not args.no_browser, stop_requested)
    except Exception as exc:
        if logger:
            logger.exception("Launcher failed")
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
