"""Delete obsolete experiment saves only; preserve reports, assets and live saves."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
REPORT = OUTPUT / "save-cleanup-2026-10-25/manifest.json"
PRESERVED_FIXTURE = OUTPUT / "free-agency-bids-2026-10-25/original-day5.nbagm.zip"


def live_save_directories():
    rows = subprocess.check_output(["ps", "-axo", "args="], text=True)
    paths = []
    for row in rows.splitlines():
        if "-m nba_gm_data.app_server" not in row:
            continue
        match = re.search(r"--save-dir (.+?)(?: --[a-z-]+|$)", row)
        if match:
            paths.append(Path(match.group(1)).resolve())
    return paths


def protected(path, live):
    resolved = path.resolve()
    live = [item.resolve() for item in live]
    return (not resolved.is_relative_to(OUTPUT.resolve()) or path.is_symlink()
            or resolved == PRESERVED_FIXTURE.resolve()
            or any(resolved == item or resolved.is_relative_to(item) or item.is_relative_to(resolved) for item in live))


def size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink())


def candidates():
    live = live_save_directories()
    selected = []
    for directory, dirs, files in os.walk(OUTPUT, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            path = parent / name
            if name in {"saves", "phase_saves", "disposable-saves"}:
                if not protected(path, live):
                    selected.append(path)
                dirs.remove(name)
            elif path.is_symlink():
                dirs.remove(name)
        for name in files:
            path = parent / name
            history = ".history.sqlite3" in name
            backup = name.endswith(".nbagm.zip")
            manifest = name in {"disposable.json", "league_save.json", "career.json"}
            if (history or backup or manifest) and not protected(path, live):
                if manifest:
                    try:
                        if json.loads(path.read_text()).get("version") != "league_save_v1":
                            continue
                    except (ValueError, OSError):
                        continue
                selected.append(path)
    return sorted(selected), live


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    paths, live = candidates()
    rows = [{"path": str(path), "bytes": size(path), "kind": "directory" if path.is_dir() else "file"} for path in paths]
    report = {"mode": "apply" if args.apply else "preview", "free_before_bytes": shutil.disk_usage(ROOT).free,
              "preserved_live_save_directories": [str(path) for path in live],
              "preserved_regression_fixture": str(PRESERVED_FIXTURE), "targets": rows,
              "target_bytes": sum(row["bytes"] for row in rows)}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if args.apply and REPORT.exists():
        previous = json.loads(REPORT.read_text())
        if previous.get("mode") == "apply":
            raise RuntimeError("Cleanup already applied; inspect the manifest rather than repeat")
    REPORT.write_text(json.dumps(report, indent=2))
    if args.apply:
        for row in rows:
            path = Path(row["path"])
            if protected(path, live_save_directories()):
                raise RuntimeError(f"Target became live/protected; not removed: {path}")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            row["removed"] = True
            REPORT.write_text(json.dumps(report, indent=2))
    report["free_after_bytes"] = shutil.disk_usage(ROOT).free
    REPORT.write_text(json.dumps(report, indent=2))
    print(json.dumps({"mode": report["mode"], "targets": len(rows),
                      "target_gib": round(report["target_bytes"] / 1024**3, 2),
                      "free_before_gib": round(report["free_before_bytes"] / 1024**3, 2),
                      "free_after_gib": round(report["free_after_bytes"] / 1024**3, 2),
                      "manifest": str(REPORT)}, indent=2))


if __name__ == "__main__":
    main()
