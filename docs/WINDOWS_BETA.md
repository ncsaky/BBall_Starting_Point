# Private Windows Beta

## Status

As of October 4, 2026: **recipe and acceptance harness implemented; no Windows
EXE built or tested yet**. Development and portable lifecycle tests were run
on the existing Apple Silicon Mac. Mocked Windows lock tests are not a Windows
launch test. The verified Mac beta.8 downloads remain unchanged.

Initial target: Windows 11 on Intel/AMD x64. Windows 10 and ARM64, antivirus
compatibility, SmartScreen behavior and clean-machine performance are unknown.
A passing hosted Windows Server CI run is useful evidence, not a substitute
for the first clean Windows 11 friend playtest. This is an unsigned private
beta, not a public installer, hosted service or notarized/signed release.

PyInstaller builds must run on the target OS; the Mac cannot produce or validate
this EXE using the Mac packaging environment. See the [official PyInstaller
requirements](https://pyinstaller.org/en/v6.16.0/requirements.html) and
[platform-specific build guidance](https://pyinstaller.org/en/stable/usage.html).
The new Windows recipe pins [official CPython 3.13.16
x64](https://www.python.org/downloads/release/python-31316/), including Tcl/Tk.
It does not change the Mac's pinned Python or Cocoa launcher.

Verified locally on the Mac: 70 focused Python checks (packaging/lifecycle,
diagnostics, API boundaries, static media and recovery), all 109 JavaScript
regressions, and the source-runtime Playwright startup/create flows. The latter
verified offline-browser video progression/fallbacks, decoded images, save
creation, tutorial completion, returning to the selector, and local issue
reports with no browser errors or failed local requests. Reports are under
`output/windows-portable-wm0ppn8_/`. The Mac architecture/icon checks also passed
(23 checks in that earlier combined run). None of this is an actual Windows
binary, native Windows GUI, PowerShell or dispatched CI verification.

A small shared-server fix now treats browser-cancelled video body transfers as
normal disconnects, avoiding tracebacks on selector navigation. Other I/O
failures still surface, and media range/security tests remain intact. This
source fix is not retroactively included in the existing Mac ZIPs.

## Build On Windows

Use a complete private copy of this working tree, including canonical data,
research/overrides, schedule/manifesto inputs, GUI artwork and the local
`src/nba_gm_data/gui/assets/startup/video/front-office.mp4`. **A Git checkout is
currently insufficient:** canonical league data is untracked here and MP4
files are ignored. No files were committed or uploaded during this task.
The preflight fails explicitly when required assets are missing; it does not
replace them with internet embeds or silently remove the movie. Do not copy
the developer's saves, logs, `.cache` or previous builds to the build PC.

Install the pinned Python with the launcher and Tcl/Tk selected. In PowerShell
at the repository root:

```powershell
python packaging/windows/build.py --check-inputs
./scripts/build_windows_beta.ps1 -Version 0.1.0-beta.8
```

The wrapper creates a build-only venv, verifies the exact Python version and
architecture, and installs pinned tools from `packaging/windows/build-requirements.txt`.
The browser game itself has no third-party Python runtime dependencies.
Do not relax machine security settings to run the wrapper; a blocked policy
requires the developer's normal approved tooling route.

Output: `dist/windows/NBA-GM-Sandbox-0.1.0-beta.8-Windows-x86_64.zip`, its
SHA-256 file, and manifests inside the download. The builder refuses to
overwrite an existing archive. It checks all EXE/DLL/PYD PE headers for AMD64,
rejects symlinks, verifies byte-identical data/art/video resources, and requires
the bundled Tcl/Tk controller runtime. This is pinned tooling and an input
inventory, not a promise of bit-for-bit reproducible binaries.

## Acceptance Before Sharing

On the Windows build/test machine, install Node 22 and an ordinary Chrome.
Playwright is verification-only, never included in the friend's download:

```powershell
npm install --prefix .cache/windows-browser --no-save --package-lock=false playwright@1.55.1
$env:NODE_PATH = Join-Path $pwd '.cache/windows-browser/node_modules'
$env:NBA_GM_TEST_CHROME = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
.cache/windows-beta-build/venv/Scripts/python.exe scripts/verify_windows_beta.py dist/windows/NBA-GM-Sandbox-0.1.0-beta.8-Windows-x86_64.zip --report dist/windows/verification.json
```

Adjust only Chrome's path if installed elsewhere. The harness extracts the
download into a new temporary location with spaces, strips external executables
from the game's PATH, changes CWD, and redirects LOCALAPPDATA into isolated test
state. It never reads, changes or stops an existing user's game. Tests cover:

- Occupied-port fallback, packaged version and normal default save location.
- Token, Host/Origin and save-path HTTP boundaries.
- Offline browser media delivery, advancing/nonblank local video, mobile
  coverage, reduced motion and missing-video photo fallback.
- GUI save creation/tutorial completion and a full 1,230-game/82-per-team schedule.
- First simulated game, GUI resume, complete SQLite-backed export/restore.
- Duplicate launch, graceful quit, token renewal and application replacement
  with byte-identical saves/history/recovery archives retained.
- Actual native controller appearance and graceful WM_CLOSE handling.
- An invalid writable data path returning an error without fallback writes.

External requests are blocked **in the test browser**, not by an OS-wide
firewall. Do not describe this as proof the entire game process was
network-sandboxed. The shared browser runner retains its historical
`verify_macos_beta_browser.cjs` name but accepts a Windows Chrome executable.
`--skip-browser` is a partial developer check and cannot mark the report complete.
Evidence/screenshots are retained in the temporary directory named in the report.
Normal headless shutdown uses a local stop-request file in that test data folder,
not forced Windows process termination or a remotely accessible shutdown API.

`.github/workflows/windows-beta.yml` is **manual dispatch only**, with read-only
repository permissions. It builds and runs these checks, uploading a
short-lived workflow artifact only after success; it never publishes a release.
Artifact access follows repository visibility; use a private repository for
friends-only distribution. It has
not been dispatched here. Before it can run, the chosen repository revision
must actually contain all release inputs (including privately managed local
media/LFS). The current untracked/ignored inputs mean a plain checkout would
fail its preflight. Do not add developer saves or credentials to make CI pass.

## Friend Launch And Saves

Extract the entire ZIP, open the `NBA GM Sandbox` folder and double-click
`NBA GM Sandbox.exe`. The native controller opens the local browser and offers
Open Browser, Show Saves, and Stop Server & Quit. Closing it drains active
requests before stopping the server. No Python/Git/Node/ffmpeg/admin access is
needed on the friend's PC. The game binds only to `127.0.0.1`; it does not make
this local package a public multiplayer server.

Saves: `%LOCALAPPDATA%\NBA GM Sandbox\saves`.
Rotating logs: `%LOCALAPPDATA%\NBA GM Sandbox\logs\launcher.log`.
Back up through Save Recovery; copying JSON alone omits history. Replacing the
application folder does not replace saves. See [friend instructions](../packaging/windows/START%20HERE.txt)
and [local issue reports](FRIEND_FEEDBACK.md).

The first friend acceptance gate is still a real Windows 11 machine with no
Python installed: extract, launch, create/load, simulate, export/import, quit,
reopen and replace the download. Record the exact Windows build, browser and
security warnings. Do not tell friends to disable antivirus.
