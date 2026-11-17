import os
from pathlib import Path

repo = Path(SPECPATH).resolve().parents[1]
version = os.environ.get("NBA_GM_BUILD_VERSION", "0.1.0-beta.2")
architecture = os.environ.get("NBA_GM_BUILD_ARCH", "arm64")
datas = [(str(repo / "src/nba_gm_data/gui"), "nba_gm_data/gui")]
for directory in ("data", "NBA Schedule", "Pre-Season manifestos"):
    for path in sorted((repo / directory).rglob("*")):
        if path.is_file() and path.suffix in {".json", ".csv", ".txt", ".gz"}:
            datas.append((str(path), str(Path("game") / path.relative_to(repo).parent)))
datas += [(str(repo / "pyproject.toml"), "game"),
          (os.environ["NBA_GM_BUILD_MANIFEST"], "game")]

a = Analysis([str(repo / "packaging/macos/launcher.py")],
             pathex=[str(repo / "src")], datas=datas,
             hiddenimports=["AppKit", "Foundation", "objc"],
             excludes=["tkinter", "pytest", "pip", "setuptools"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="NBA GM Sandbox", console=False, target_arch=architecture)
collect = COLLECT(exe, a.binaries, a.datas, name="NBA GM Sandbox")
app = BUNDLE(collect, name="NBA GM Sandbox.app",
             icon=str(repo / "packaging/assets/app-icon.icns"),
             bundle_identifier="com.nbagmsandbox.privatebeta",
             version=version,
             info_plist={
                 "CFBundleShortVersionString": "0.1.0",
                 "CFBundleVersion": "1",
                 "LSMinimumSystemVersion": "11.0",
                 "NSHighResolutionCapable": True,
                 "NSHumanReadableCopyright": "Private friends-and-family beta",
             })
