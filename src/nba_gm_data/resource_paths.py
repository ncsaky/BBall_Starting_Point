"""Locate read-only game resources without depending on the working directory."""

from functools import lru_cache
from pathlib import Path
import sys


@lru_cache(maxsize=1)
def game_resource_root() -> Path:
    # Fixed for the life of the process (frozen bundle or source checkout); resolved once.
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "game"
    return Path(__file__).resolve().parents[2]
