"""Small allowlisted runtime metadata for a manually shared issue report."""

from pathlib import Path
import json
import platform
import sys
import tomllib


def diagnostic_runtime(root: Path) -> dict:
    frozen = bool(getattr(sys, "frozen", False))
    version = "unknown"
    try:
        if frozen:
            with (root / "build-manifest.json").open("r", encoding="utf-8") as stream:
                value = json.load(stream).get("version")
        else:
            with (root / "pyproject.toml").open("rb") as stream:
                value = tomllib.load(stream).get("project", {}).get("version")
        if isinstance(value, str) and len(value) <= 64 and all(c.isalnum() or c in ".-" for c in value):
            version = value
    except (OSError, ValueError, AttributeError):
        pass
    return {
        "version": version,
        "packaged": frozen,
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "protocol": "app_actions_v1",
    }
