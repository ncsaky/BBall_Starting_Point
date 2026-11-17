"""Reproducible recipe for a relocatable private beta (no repository saves)."""

from __future__ import annotations

import argparse
import ast
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from macholib.MachO import MachO
from macholib.mach_o import LC_BUILD_VERSION, LC_VERSION_MIN_MACOSX


REPO = Path(__file__).resolve().parents[2]
APP_NAME = "NBA GM Sandbox"
ARCHITECTURES = {"arm64": 0x0100000c, "x86_64": 0x01000007}
PLATFORMS = {"arm64": "Apple Silicon Macs (M1 or newer)", "x86_64": "Intel Macs"}


def digest(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def inventory():
    files = list((REPO / "src/nba_gm_data").rglob("*.py"))
    files += list((REPO / "src/nba_gm_data/gui").rglob("*"))
    for folder in ("data", "NBA Schedule", "Pre-Season manifestos"):
        files += [p for p in (REPO / folder).rglob("*") if p.suffix in {".json", ".csv", ".txt", ".gz"}]
    files += [REPO / "pyproject.toml", REPO / "packaging/macos/launcher.py",
              REPO / "packaging/macos/NBA GM Sandbox.spec", REPO / "packaging/macos/build-requirements.txt",
              REPO / "packaging/assets/app-icon.icns"]
    files = sorted(set(p for p in files if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"))
    imports = set()
    for path in (REPO / "src/nba_gm_data").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imports.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                imports.add(node.module.split(".")[0])
    external = sorted(imports - sys.stdlib_module_names - {"nba_gm_data"})
    if external:
        raise RuntimeError(f"Review new game runtime dependencies before packaging: {external}")
    return files, {
        "game_python_dependencies": external,
        "game_stdlib_imports": sorted(imports),
        "launcher_python_dependencies": ["pyobjc-core==11.1", "pyobjc-framework-Cocoa==11.1"],
        "os_dependencies": ["macOS AppKit/Foundation", "installed default web browser"],
        "optional_services": ["remote player headshots where referenced", "Ollama narrative provider with deterministic fallback"],
        "not_needed_by_browser_game": ["Git", "installed Python", "Node.js", "ffmpeg", "raw-ingestion input directories", "CLI ASCII animation cache"],
        "input_sha256": {str(p.relative_to(REPO)): digest(p) for p in files},
        "input_bytes": sum(p.stat().st_size for p in files),
    }


def audit_binaries(app, architecture="arm64"):
    expected_cpu = ARCHITECTURES[architecture]
    minimum = 0
    count = 0
    for path in app.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic not in {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe"}:
            continue
        count += 1
        binary = MachO(str(path))
        if {h.header.cputype for h in binary.headers} != {expected_cpu}:
            raise RuntimeError(f"Unexpected non-{architecture} binary: {path}")
        for header in binary.headers:
            for command, value, data in header.commands:
                if command.cmd == LC_BUILD_VERSION:
                    minimum = max(minimum, value.minos)
                elif command.cmd == LC_VERSION_MIN_MACOSX:
                    minimum = max(minimum, value.version)
            for _, _, name in header.walkRelocatables():
                if name.startswith("/") and not name.startswith(("/usr/lib/", "/System/Library/")):
                    raise RuntimeError(f"Unbundled binary dependency: {path}: {name}")
    version = f"{minimum >> 16}.{(minimum >> 8) & 255}.{minimum & 255}"
    if minimum > 0x000b0000:
        raise RuntimeError(f"Binary requires macOS {version}; update the declared target before release.")
    if not count:
        raise RuntimeError("Application contains no Mach-O binaries.")
    return {"mach_o_count": count, "architecture": architecture, "maximum_binary_minimum_macos": version}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="0.1.0-beta.2")
    parser.add_argument("--arch", choices=ARCHITECTURES, default=platform.machine())
    parser.add_argument("--output", type=Path, default=REPO / "dist/macos")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != args.arch:
        parser.error(f"Run using a {args.arch} Python on macOS (Rosetta is supported for Intel builds).")
    if sys.version_info[:3] != (3, 12, 11):
        parser.error("Use the pinned CPython 3.12.11 build environment.")
    if not all(c.isalnum() or c in ".-" for c in args.version):
        parser.error("Use a version consisting of letters, digits, dots and hyphens.")
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"NBA-GM-Sandbox-{args.version}-macOS-{args.arch}.zip"
    if archive.exists():
        parser.error(f"Archive already exists; choose a new version or output directory: {archive}")
    # Documents/Desktop may be File Provider managed; Finder can reattach
    # disallowed metadata after xattr cleanup. Sign and archive in a local cache.
    work = Path.home() / "Library/Caches/NBA GM Sandbox Builds" / args.version / args.arch
    work.mkdir(parents=True, exist_ok=True)
    _, manifest = inventory()
    manifest.update({"version": args.version, "python": platform.python_version(),
                     "build_macos": platform.mac_ver()[0], "minimum_macos": "11.0",
                     "architecture": args.arch, "signing": "PyInstaller automatic ad-hoc only; no Developer ID or notarization",
                     "build_packages": {d: metadata.version(d) for d in
                         ("pyinstaller", "pyinstaller-hooks-contrib", "pyobjc-core", "pyobjc-framework-Cocoa", "altgraph", "macholib", "packaging", "setuptools")}})
    manifest_path = work / "build-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    env = os.environ.copy()
    env.update({"NBA_GM_BUILD_VERSION": args.version, "NBA_GM_BUILD_ARCH": args.arch,
                "NBA_GM_BUILD_MANIFEST": str(manifest_path), "PYTHONHASHSEED": "0"})
    # Prefer the installed standalone Command Line Tools when Xcode's tool
    # selector points at a newly installed IDE. No license acceptance or
    # system-wide developer-directory change is performed by this builder.
    if "DEVELOPER_DIR" not in env and Path("/Library/Developer/CommandLineTools").is_dir():
        env["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(work / "frozen"), "--workpath", str(work / "pyinstaller"),
                    str(REPO / "packaging/macos/NBA GM Sandbox.spec")], cwd=REPO, env=env, check=True)
    app = work / "frozen" / (APP_NAME + ".app")
    audit = audit_binaries(app, args.arch)
    for link in app.rglob("*"):
        if link.is_symlink() and not link.resolve().is_relative_to(app.resolve()):
            raise RuntimeError(f"Bundle symlink escapes application: {link}")
    # Source images can carry Finder/resource-fork metadata. Clean only the
    # newly assembled app, leaving all source files and media bytes intact.
    subprocess.run(["/usr/bin/xattr", "-cr", str(app)], check=True)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    release_name = f"NBA GM Sandbox {args.version} macOS {args.arch}"
    release = work / "release" / release_name
    if release.exists():
        shutil.rmtree(release)
    release.mkdir(parents=True)
    shutil.copytree(app, release / app.name, symlinks=True)
    subprocess.run(["/usr/bin/xattr", "-cr", str(release / app.name)], check=True)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(release / app.name)], check=True)
    instructions = (REPO / "packaging/macos/START HERE.txt").read_text()
    (release / "START HERE.txt").write_text(instructions.replace("@VERSION@", args.version)
                                           .replace("@PLATFORM@", PLATFORMS[args.arch]))
    manifest["binary_audit"] = audit
    (release / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(release), str(archive)], check=True)
    (output / (archive.name + ".sha256")).write_text(f"{digest(archive)}  {archive.name}\n")
    print(json.dumps({"app": str(release / app.name), "archive": str(archive),
                      "archive_bytes": archive.stat().st_size, "binary_audit": audit}, indent=2))


if __name__ == "__main__":
    main()
