"""Locate read-only game resources without depending on the working directory."""

from pathlib import Path
import sys


def game_resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "game"
    return Path(__file__).resolve().parents[2]
