"""Native Windows x64 portable beta builder. No cross-compilation."""

from __future__ import annotations

import argparse
import ast
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
APP_NAME = "NBA GM Sandbox"
REQUIRED = (
    "data/canonical/universe_2026_27_offseason.json",
    "src/nba_gm_data/gui/index.html",
    "src/nba_gm_data/gui/assets/startup/video/front-office.mp4",
    "packaging/assets/app-icon.ico",
    "packaging/assets/app-icon.png",
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(repo=REPO):
    missing = [name for name in REQUIRED if not (repo / name).is_file() or not (repo / name).stat().st_size]
    if missing:
        raise RuntimeError("Required local release assets missing (copy them from the complete working tree): " + ", ".join(missing))
    files = list((repo / "src/nba_gm_data").rglob("*.py"))
    files += list((repo / "src/nba_gm_data/gui").rglob("*"))
    for folder in ("data", "NBA Schedule", "Pre-Season manifestos"):
        files += [p for p in (repo / folder).rglob("*") if p.suffix in {".json", ".csv", ".txt", ".gz"}]
    files += list((repo / "packaging/windows").glob("*"))
    files += [repo / "pyproject.toml", repo / "packaging/assets/app-icon.ico", repo / "packaging/assets/app-icon.png"]
    files = sorted({p for p in files if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"})
    imports = set()
    for path in (repo / "src/nba_gm_data").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                imports.add(node.module.split(".")[0])
    external = sorted(imports - sys.stdlib_module_names - {"nba_gm_data"})
    if external:
        raise RuntimeError(f"Review new runtime dependencies before packaging: {external}")
    return files, {"input_sha256": {p.relative_to(repo).as_posix(): digest(p) for p in files},
                   "input_bytes": sum(p.stat().st_size for p in files),
                   "game_python_dependencies": external,
                   "os_dependencies": ["Windows 11 x64", "installed default web browser"],
                   "not_required_on_friend_pc": ["Python", "Git", "Node.js", "ffmpeg", "administrator access"]}


def audit_binaries(app):
    count = 0
    for path in app.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Unexpected symlink in portable Windows bundle: {path}")
        if not path.is_file() or path.suffix.lower() not in {".exe", ".dll", ".pyd"}:
            continue
        with path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise RuntimeError(f"Invalid Windows binary: {path}")
            stream.seek(0x3c)
            offset = stream.read(4)
            if len(offset) != 4:
                raise RuntimeError(f"Truncated Windows binary: {path}")
            stream.seek(struct.unpack("<I", offset)[0])
            header = stream.read(6)
            if len(header) != 6 or header[:4] != b"PE\0\0" or struct.unpack("<H", header[4:])[0] != 0x8664:
                raise RuntimeError(f"Expected Windows AMD64 PE binary: {path}")
        count += 1
    if not count:
        raise RuntimeError("No Windows binaries in bundle")
    return {"pe_count": count, "architecture": "x86_64"}


def audit_resources(app, manifest):
    internal = app / "_internal"
    checked = 0
    for name, expected in manifest["input_sha256"].items():
        if name.startswith("src/nba_gm_data/gui/"):
            bundled = internal / name.removeprefix("src/")
        elif name.startswith(("data/", "NBA Schedule/", "Pre-Season manifestos/")) or name == "pyproject.toml":
            bundled = internal / "game" / name
        elif name == "packaging/assets/app-icon.png":
            bundled = internal / "game/app-icon.png"
        else:
            continue
        if not bundled.is_file() or digest(bundled) != expected:
            raise RuntimeError(f"Missing or altered bundled resource: {name}")
        checked += 1
    if not (internal / "_tcl_data/init.tcl").is_file() or not (internal / "_tk_data/tk.tcl").is_file():
        raise RuntimeError("Native control-window Tcl/Tk runtime is missing")
    return {"byte_identical_resources": checked, "tcl_tk_present": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="0.1.0-beta.8")
    parser.add_argument("--output", type=Path, default=REPO / "dist/windows")
    parser.add_argument("--check-inputs", action="store_true", help="Read-only source preflight, also works on Mac/Linux")
    args = parser.parse_args()
    if args.check_inputs:
        _, manifest = inventory()
        print(json.dumps({"input_files": len(manifest["input_sha256"]), "input_bytes": manifest["input_bytes"]}, indent=2))
        return
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"} or struct.calcsize("P") != 8:
        parser.error("Build on Windows using x64 Python. This recipe cannot cross-compile on a Mac.")
    if sys.version_info[:3] != (3, 13, 16):
        parser.error("Use the pinned official CPython 3.13.16 x64 installer (including Tcl/Tk).")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", args.version):
        parser.error("Start the ASCII version with a letter or digit; only letters, digits, dots and hyphens are allowed.")
    output = args.output.resolve()
    archive_base = output / f"NBA-GM-Sandbox-{args.version}-Windows-x86_64"
    if Path(str(archive_base) + ".zip").exists():
        parser.error("Archive already exists; choose a new version or output directory.")
    _, manifest = inventory()
    manifest.update({"version": args.version, "python": platform.python_version(), "architecture": "x86_64",
                     "build_windows": platform.version(), "target_windows": "Windows 11 x64; clean-machine testing required",
                     "signing": "unsigned private beta; no Authenticode certificate",
                     "build_packages": {name: metadata.version(name) for name in
                         ("pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "packaging", "pefile", "pywin32-ctypes", "setuptools")}})
    work = REPO / ".cache/windows-beta-build" / args.version
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = work / "build-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    env = {**os.environ, "NBA_GM_BUILD_MANIFEST": str(manifest_path), "PYTHONHASHSEED": "0"}
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(work / "frozen"),
                    "--workpath", str(work / "pyinstaller"), str(REPO / "packaging/windows/NBA GM Sandbox.spec")], cwd=REPO, env=env, check=True)
    app = work / "frozen" / APP_NAME
    manifest["binary_audit"] = audit_binaries(app)
    manifest["resource_audit"] = audit_resources(app, manifest)
    release_name = f"NBA GM Sandbox {args.version} Windows x86_64"
    release = work / "release" / release_name
    if release.exists():
        shutil.rmtree(release)
    release.mkdir(parents=True)
    shutil.copytree(app, release / APP_NAME)
    (release / "START HERE.txt").write_text((REPO / "packaging/windows/START HERE.txt").read_text(encoding="utf-8").replace("@VERSION@", args.version), encoding="utf-8")
    (release / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    archive = Path(shutil.make_archive(str(archive_base), "zip", root_dir=release.parent, base_dir=release.name))
    (output / (archive.name + ".sha256")).write_text(f"{digest(archive)}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "archive_bytes": archive.stat().st_size,
                      "binary_audit": manifest["binary_audit"], "resource_audit": manifest["resource_audit"]}, indent=2))


if __name__ == "__main__":
    main()
