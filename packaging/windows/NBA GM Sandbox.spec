import os
from pathlib import Path

repo = Path(SPECPATH).resolve().parents[1]
datas = [(str(repo / "src/nba_gm_data/gui"), "nba_gm_data/gui")]
for directory in ("data", "NBA Schedule", "Pre-Season manifestos"):
    for path in sorted((repo / directory).rglob("*")):
        if path.is_file() and path.suffix in {".json", ".csv", ".txt", ".gz"}:
            datas.append((str(path), str(Path("game") / path.relative_to(repo).parent)))
datas += [(str(repo / "pyproject.toml"), "game"),
          (str(repo / "packaging/assets/app-icon.png"), "game"),
          (os.environ["NBA_GM_BUILD_MANIFEST"], "game")]

a = Analysis([str(repo / "packaging/windows/launcher.py")],
             pathex=[str(repo / "src")], datas=datas,
             hiddenimports=["tkinter", "tkinter.ttk"],
             excludes=["pytest", "pip", "setuptools", "AppKit", "Foundation", "objc"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="NBA GM Sandbox", console=False,
          icon=str(repo / "packaging/assets/app-icon.ico"))
collect = COLLECT(exe, a.binaries, a.datas, name="NBA GM Sandbox")
