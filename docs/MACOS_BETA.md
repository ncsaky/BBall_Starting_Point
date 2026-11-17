# Private macOS beta

The current recipe produces separate Apple Silicon (`arm64`) and Intel
(`x86_64`) downloads at `dist/macos/NBA-GM-Sandbox-0.1.0-beta.10-macOS-<arch>.zip`.
Each contains `NBA GM Sandbox.app`, processor-specific `START HERE.txt`, and
an input/dependency manifest. The original beta.1 Apple Silicon ZIP remains
unchanged. The staged app remains in `~/Library/Caches/NBA GM Sandbox Builds/`
under its version and architecture.

Both variants have a **macOS 11.0** deployment minimum. The builder audits every bundled Mach-O binary's architecture,
minimum OS, and library paths. Testing was performed on **macOS 27.0.1
(26A434), arm64**. Older macOS versions and a clean friend's Mac have not been
verified. Intel builds run under Rosetta 2 on this Apple Silicon builder;
this is not evidence of testing on a physical Intel Mac. There is no
universal build or Windows download yet.

## Beta.10 acceptance — October 4, 2026

**READY FOR ONE FRIEND TEST.** Both downloadable ZIPs passed the existing
extracted-app harness with isolated data. Apple Silicon was tested natively;
Intel was tested under Rosetta on the same Apple Silicon Mac. A physical Intel
Mac, clean-machine installation, download quarantine and older macOS remain
unverified. These builds are ad-hoc signed and unnotarized.

| Download | Bytes | SHA-256 |
| --- | ---: | --- |
| [Apple Silicon](../dist/macos/NBA-GM-Sandbox-0.1.0-beta.10-macOS-arm64.zip) | 349541291 | `4c793b884fdda328b1cb096e4339f0be82cb7d297938949bb81f35034394ceea` |
| [Intel](../dist/macos/NBA-GM-Sandbox-0.1.0-beta.10-macOS-x86_64.zip) | 349528296 | `747930fb1702750595ee3b849972c508556fe4952cddd272d680d53e746863d5` |

Only the two obsolete foundation fixtures were repaired: the deterministic
trade now uses a supported league save and checks ownership, durable ledger
and replay; the free-agency test checks the intended 25 display ratings and
league 25th/50th/75th-percentile cutoffs. Both pass, as do the previously
selected 53 Python regressions and all 117 JavaScript tests. Production
validation and gameplay were not changed for this release. All pre-existing
working-tree changes and 17 older top-level ZIPs were preserved.

Both bundles match all 490 build input hashes and all 399 GUI file hashes,
including the current UI, five-card defaults, transaction/salary and duplicate
draft fixes. The approved full movie is unchanged: 188,378,704 bytes,
SHA-256 `1251699223efd061d9ea15553fd8cd9546a762c74c15a0db5a5372d8cb4b7a57`.
Offline Chrome playback visibly advanced with full opacity and no blank
frames in the sampled selector view. Return-to-selector, reduced motion,
missing-movie photo fallback, range and HEAD delivery passed. No uncaught
browser errors or failed local resources were recorded.

Save creation/resume, the first game and historical box score, API/browser
backup/restore, authentication, occupied-port fallback, duplicate launch,
restart and byte-preserving replacement passed on both architectures. A short
HTTP replay of the existing POR/Micah Potter finder case applied a legal trade,
preserved ownership and one ledger row through restart, and rejected replay
without changing saved bytes. Both native launchers passed Open Browser,
Show Saves, Stop Server & Quit, window-close and Command-Q checks. Each quit
exited successfully, removed runtime state and closed its own listening port.

Full evidence and limitations: [beta.10 acceptance report](../output/macos-beta.10/FINAL.md).
Harness reports: `dist/macos/verification-0.1.0-beta.10-{arm64,x86_64}.json`.
This pass did not repeat a full season, broad transaction/media audit or
cross-viewport layout audit; the source integration evidence remains at
`output/integration-checkpoint/FINAL.md`.

The prepared Apple Silicon download is extracted at
`~/NBA GM Sandbox beta.10 Apple Silicon/` and has not been launched.
An initial Documents extraction acquired Finder metadata and failed strict
signature verification; re-extraction into this local folder passed. The ZIPs
and isolated acceptance copies passed signature checks. Prefer a local
Applications folder for installation.

To install, extract the matching ZIP and move its app to Applications. To
switch versions, finish any simulation, quit the active launcher, then open
the chosen version's app. Export Backup first if you may return to an older
beta; backwards save compatibility was not tested. Keep versioned downloads
separate. The app's Report an Issue identifies `0.1.0-beta.10`; Finder's
generic version remains `0.1.0 (1)` under the established recipe. No running
user app was stopped during preparation, and no real saves were accessed.

## Previous Beta.8 Friend-Feedback Follow-Up

Report an Issue is available from the save screen and Settings. It downloads a local JSON report with tester notes and allowlisted runtime/screen/action/video diagnostics, without uploading anything or attaching saves, names, file paths, credentials or raw logs. Build metadata has a bounded timeout and reports the exact beta version from the bundled build manifest. Notes are included as written; testers should avoid personal information. See `docs/FRIEND_FEEDBACK.md` for privacy boundaries, workflow, verification and limitations.

All 109 JavaScript tests and 53 focused Python tests passed. The dedicated source browser regression passed at desktop/mobile sizes, and the nine-check first-hour workflow passed again. Both final extracted beta.8 ZIPs passed the full packaging smoke harness, including report downloads from both entry points with the correct beta version, offline video/fallback, 82-game calendar schedules, first game, backup/restore, restart, duplicate launch and save preservation after app replacement. Reports: `dist/macos/verification-0.1.0-beta.8-{arm64,x86_64}.json`, both with `checks.complete: true`. Feedback source hashes match both bundle manifests. Earlier gameplay fixes are retained; no new full-season balance claim is made.

Intermediate packages reporting macOS's generic build number are retained under `superseded-beta.8-version-metadata/`; use the top-level ZIPs. An incomplete Apple Silicon crossfade probe is retained separately. Intel verification remains Rosetta-only; both builds remain ad-hoc signed and unnotarized.

## Previous Beta.7 Schedule Integrity Follow-Up

New franchises and newly generated seasons now have 1,230 regular-season games and 82 per team. The generator excludes the Cup championship and four superseded postponed entries, retains their makeup games, and rejects invalid templates explicitly. Existing schedules and played results are not rewritten: an existing 83-game season receives the correction only at its next rollover. A rare 53.01-minute overtime rounding defect is also fixed. See `docs/SCHEDULE_INTEGRITY.md` for evidence and compatibility limits.

Eleven generated seasons passed schedule checks. Three fixed-roster seasons (3,690 games) passed accounting checks; the overtime rounding follow-up preserved all their scores and winners. A complete disposable Miami career reached rollover with zero hard invariant failures; all 1,312 archived games passed independent accounting checks. Shooting calibration, injury-burden interpretation and longer-term career balance remain open.

Both final extracted beta.7 ZIPs passed the complete packaging smoke harness: offline video/fallback, 82-game schedules, first game, backup/restore, restart, duplicate launch and byte-for-byte data preservation after app replacement. Reports: `dist/macos/verification-0.1.0-beta.7-{arm64,x86_64}.json`, both with `checks.complete: true`. Both build manifests match the final simulation, schedule generator and correction data. Intermediate schedule-only packages are retained under `superseded-beta.7-overtime-rounding/`; use the top-level ZIPs. Intel testing remains Rosetta-only; both downloads remain ad-hoc signed and unnotarized.

## Previous Beta.6 Basketball Accounting Follow-Up

Beta.6 repairs impossible shooting lines and overtime shot/minute totals without changing game scores or winners in a 3,705-game seeded comparison. A complete disposable career and all 1,326 archived games pass the accounting checks through rollover. The soak runner now follows the required re-signing phase and saves self-contained history snapshots. See `docs/BASKETBALL_REALISM_AUDIT.md` for evidence, measured shooting outputs and unresolved balance concerns. Existing historical box scores are not rewritten.

Both extracted beta.6 architecture ZIPs passed the complete packaging smoke harness, including offline video/fallback, first game, backup/restore, restart, duplicate launch and byte-for-byte data preservation after app replacement. Reports: `dist/macos/verification-0.1.0-beta.6-{arm64,x86_64}.json`, both with `checks.complete: true`. Both build manifests match the accepted audit's simulation source hash. Intermediate unverified beta.6 archives are retained only in explicitly named `unverified-shooting-*` subdirectories; use the top-level ZIPs.

The beta.6 template gave ten teams 83 regular-season games; beta.7 corrects newly generated schedules as described above. Shooting-rate calibration and longer career balance are still open. Intel testing remains Rosetta-only, and both downloads remain ad-hoc signed and unnotarized. Beta.5 performance and earlier workflow fixes are retained.

## Previous Beta.5 Performance Follow-Up

Beta.5 retains the first-hour and starter-workspace fixes, precomputes repeated lineup scores without changing results, and defers valuations until an asset window is opened/restored. Failed or stale asset reads have explicit recovery behavior. See `docs/PERFORMANCE_PASS.md` for measured timings, exact-output comparisons and limits. The source first-hour workflow and frozen Apple Silicon asset-loading regression passed. Both extracted architecture ZIPs passed the full packaging smoke harness, including offline video/fallback, first game, backup/restore, restart, duplicate launch and byte-for-byte save preservation after app replacement. Reports are at `dist/macos/verification-0.1.0-beta.5-{arm64,x86_64}.json`, both with `checks.complete: true`. Intel testing remains Rosetta-only; signing and notarization status is unchanged.

## Previous beta.4 Verification

Both architecture ZIPs passed the extracted-app smoke harness: offline local video playback and fallback, save creation and first game, backup/export/restore, quit/relaunch, duplicate launch reuse, and byte-for-byte preservation of stored data after app replacement. Reports: `dist/macos/verification-0.1.0-beta.4-{arm64,x86_64}.json`. The incomplete first attempts, caused by a stale test expecting Team Identity to be initially visible, are retained separately; the final reports both have `checks.complete: true`.

Beta.4 includes the first-hour fixes and a non-overlapping starter workspace for absent browser preferences, without repacking valid existing layouts. The tutorial shows gallery-only teaching targets temporarily and restores the original arrangement. The frozen Apple Silicon app passed the layout/browser regressions at four viewport sizes. See `docs/FIRST_HOUR_PLAYTEST.md` and `dist/macos/starter-workspace-beta.4/` for evidence and remaining limits. Intel execution was verified under Rosetta, not on a physical Intel Mac. These builds remain ad-hoc signed and unnotarized.

## Launch and update

Extract the ZIP, move the app into Applications or another local directory,
and double-click it. The native launcher starts a loopback HTTP server and
opens the default browser. Its window has **Open Browser**, **Show Saves**,
and **Stop Server & Quit** controls. Closing the launcher window or using
Command-Q stops the server. Closing the browser leaves the server running.

The app prefers port 8765. If binding that port returns `EADDRINUSE`, it asks
the OS for a free port and shows the resulting URL. Reopening an already
running app opens the browser again. A per-user advisory lock prevents two
copies from running separate servers against the same data directory.
Startup errors include the error, save location, and rotating log location.

All mutable state goes under:

```text
~/Library/Application Support/NBA GM Sandbox/
  saves/          JSON manifests, history SQLite databases, recovery ZIPs,
                  restore journals, locks, and multiplayer SQLite state
  logs/           launcher.log and rotated previous logs
  server.lock     per-user launcher instance lock
  runtime.json    current process/address information, removed on clean quit
```

There is no runtime API token in `runtime.json`. Tokens remain freshly
generated by the existing server at each start. Host/Origin/fetch-site
validation, token requirements, upload limits, and save-path containment
remain in the original HTTP handler. The app binds only `127.0.0.1` and does
not expose additional shutdown HTTP endpoints or expand hosted multiplayer.
When quitting, it stops scheduling, stops accepting requests, and allows
active request threads to finish their save transactions.

Quit the app before replacing `NBA GM Sandbox.app`. The application-support
directory is stable across versions and does not depend on the install path,
working directory, bundle version, or PyInstaller extraction directory.
Developer and CLI entry points still use their existing roots/save locations;
this launcher does not migrate, inspect, or modify repository saves.

## Runtime inventory and packaging choice

The game's Python modules have **no third-party runtime dependencies**.
They use the standard library, including JSON/CSV, SQLite, hashing, zip/base64,
HTTP, threading, filesystem locks, and optional HTTP narrative providers.
The private native launcher adds `pyobjc-core` and `pyobjc-framework-Cocoa`
11.1 to bridge the system AppKit/Foundation frameworks. A default web browser
is supplied by the player's Mac.

PyInstaller 6.16.0 builds an on-directory `.app` with **CPython 3.12.11**
from uv's corresponding standalone macOS arm64 or x86_64 distribution. It avoids a browser runtime,
Electron, Tk/Tcl, Node, and a separately installed Python. The beta.1 bundle was
about 241 MiB unpacked and its ZIP about 153 MiB. Beta.2 adds a roughly 36 MiB
local startup movie. Media dominates size.
The packaging approach follows [PyInstaller's macOS bundle support](https://pyinstaller.org/en/stable/usage.html).

The bundled read-only resources are:

| Resource | Included content |
| --- | --- |
| Engine | All Python modules required by the server's dependency graph |
| GUI | The entire current GUI tree, including nested photos, source images, dot-press assets, logos, coach artwork, CSS, JavaScript, and media manifests/credits |
| Canonical | Both current and previous canonical JSON universes |
| Configuration | All JSON/CSV overrides, model configuration, staff seeds, and narrative templates |
| Research | All existing research JSON, including metadata, contract/pick sources, betting odds, tracking, box scores, shot zones, and the shot-chart model |
| Schedules | Schedule and real-minutes JSON from `NBA Schedule` |
| Simulation text | All team files in `Pre-Season manifestos` |
| Metadata | `pyproject.toml` and the build input hashes/dependency manifest |

Raw ingestion directories, Git history, developer tools/tests, real saves,
and CLI-only optional ASCII loading-video caches are not runtime inputs for
the browser game and are excluded. Canonical data is required at startup;
a missing canonical snapshot produces an installation error rather than
attempting to rebuild it from missing raw inputs. The shot-chart model now
uses a shared read-only resource locator, preserving the developer path and
finding bundled data when frozen. The server also skips Python's reverse-DNS
lookup for numeric loopback binds, removing a network-dependent startup stall.
Explicit non-loopback developer binds keep their existing behavior.

For beta.1, all 395 GUI files were checked against their source SHA-256 bytes with no
missing or changed files. Existing media is retained for this authorized
private test. No media was replaced or removed, and no public-distribution
provenance clearance is asserted.

## Offline behavior

Packaged core gameplay, local art, and startup footage work without internet.
Beta.2 replaces the YouTube iframe/API player with a bundled silent H.264
montage: six basketball snippets alternate with five team-operations snippets.
Beta.10 includes the approved full 93.933-second montage; it was not rebuilt
during packaging. The local photo rail remains visible until video actually plays, and when
media is missing/corrupt or autoplay is denied. Reduced-motion preferences
prevent loading and playing the video. Leaving the selector releases it;
returning loads it again. Hidden browser tabs pause playback.

The existing fine dot-screen and grayscale treatment is retained. The static
server supports bounded byte-range requests and HEAD for browser media
loading/seeking. These remain subject to existing Host/Origin/fetch-site
checks; authentication and save boundaries are unchanged.

Player headshot URLs and metadata are bundled unchanged. The screens
exercised during verification made no remote headshot requests; no new
headshot downloader or renderer was introduced. Any screen that uses a
remote image still needs internet and keeps its existing local artwork or
placeholder behavior. Optional Ollama narrative generation needs a running
local Ollama service, with the existing deterministic narrative fallback.
Neither ffmpeg nor the optional CLI animation cache is needed by the GUI.

## Build and verification

On a Mac with uv and Apple's Command Line Tools:

```sh
./scripts/build_macos_beta.sh --version 0.1.0-beta.10 --arch arm64
./scripts/build_macos_beta.sh --version 0.1.0-beta.10 --arch x86_64
```

The script resolves its repository path independently of the working
directory, creates `.cache/macos-beta-build/<arch>/venv`, downloads the pinned
architecture-specific standalone Python if necessary, and installs exact build-package versions
from `packaging/macos/build-requirements.txt`. It then inventories inputs,
builds, audits binaries and bundle links, cleans copied Finder/resource-fork
metadata from the generated app only, checks the automatic ad-hoc signature,
and produces the app, ZIP, and SHA-256 file. The recipe is reproducible from
the same inputs; byte-for-byte archive identity is not promised because
Mach-O UUIDs, signatures, and ZIP timestamps can vary. No source media bytes
or system-wide developer settings are changed by the builder. Intel builds
on Apple Silicon require Rosetta 2 to have been installed separately. The
builder does not install Rosetta or accept its license. Run the Intel recipe
natively on an Intel Mac, or through the pinned x86_64 Python under Rosetta.

Build/signing/release staging uses `~/Library/Caches/NBA GM Sandbox Builds/`
instead of Documents/Desktop. Cloud File Provider metadata can reappear on
apps stored in those folders and invalidate signatures. Only the ZIP and
checksum are published to the chosen output directory. Existing versioned
ZIPs are never silently overwritten; use a new version or output directory.

An alternate version/output is supported:

```sh
./scripts/build_macos_beta.sh --arch x86_64 --version 0.1.0-beta.10 --output /absolute/release/path
```

The verification harness requires Playwright available to Node and Chrome
on the build/test Mac, not on a friend's Mac:

```sh
NODE_PATH=/path/to/node_modules .cache/macos-beta-build/x86_64/venv/bin/python \
  scripts/verify_macos_beta.py \
  dist/macos/NBA-GM-Sandbox-0.1.0-beta.10-macOS-x86_64.zip \
  --report dist/macos/verification-0.1.0-beta.10-x86_64.json
```

Set `NBA_GM_TEST_CHROME` to another Chrome executable if needed. The harness
extracts the downloadable ZIP into an unrelated temporary path containing
spaces, uses an isolated data directory, strips Python/uv environment
variables and Python/Git from the launched app's PATH, and never opens real
user saves. It blocks external networking for the app with a child-only
`sandbox-exec` profile and for the browser with request routing. It checks
the selector, standard save creation, first user game/box score, backup
export and restore through both API and browser controls, graceful quit,
fresh tokens on relaunch, duplicate launch, and app replacement with
byte-for-byte state preservation. Test-only data and screenshots remain in
the reported temporary directory for inspection.

For isolated manual native-window testing, pass `--data-dir /temporary/path`
through `open -n -a /path/to/NBA\ GM\ Sandbox.app --args ...`; alternatively
the launcher accepts `NBA_GM_USER_DATA_DIR`. `--headless --no-browser` is
provided for packaged-artifact automation only. Normal double-click launch
uses the native controller and default browser.

This build has PyInstaller's required automatic **ad-hoc** signatures, with
no Developer ID signing, Apple notarization, or Gatekeeper-download approval
claimed. Friends may need the normal macOS **Open Anyway** override described
in `START HERE.txt`. Managed Macs may prohibit that override. Existing
developer multiplayer behavior remains bundled, with no hosted service
added or tested as part of this release.

## Verification results for 0.1.0-beta.2

Both extracted ZIPs passed the isolated packaged-app smoke harness on this
macOS 27.0.1 Apple Silicon host. The Intel executable ran through Rosetta 2.
No real saves were opened or modified. Test apps were stopped at completion.

| Variant | ZIP Bytes | SHA-256 |
| --- | ---: | --- |
| Intel x86_64 | 198714168 | `77f48c186003b92474375f9c7feeb1ac21ffb3d9c01b3698b550867a9e5f0457` |
| Apple Silicon arm64 | 198726786 | `14c739a06e8b4479dfba3bba536078806f8cd1dcc826c6e3f3014aff7f63fce8` |

Verified in each variant: external networking denied for the app, offline
browser startup/video, occupied-port fallback, standard save creation,
first Warriors game (GSW 126 at OKC 140; 22 player box-score lines), browser
and API backup export/restore, restart with fresh authentication, duplicate
launch reuse, application replacement with byte-identical saved state, and
actionable invalid-data-directory failure. The custom bundle icon matches
the source ICNS, and all 398 GUI file hashes match each build manifest.
Every bundled Mach-O was audited and ad-hoc signatures verified.

Chrome 154 rendered the local movie with full computed opacity and advancing
time; canvas samples were nonblank. Browser tests also verified byte ranges
and HEAD, desktop/mobile framing, entering a save and returning to the
selector, reduced motion without loading a movie, and clean photo fallback
when the movie request was deliberately aborted. No startup external hosts
were requested, and there were no uncaught browser or local HTTP errors.
The full movie also decoded through ffmpeg without errors.

The first Intel harness attempt continued before a delayed first-run
tutorial had appeared. The helper now waits for dashboard hydration and
explicitly skips the tutorial rather than swallowing a 2.5-second timeout.
The unchanged Intel ZIP passed on rerun. Gameplay was not modified.
58 focused Python/JavaScript checks passed for icons, architectures, media
delivery, API protection, playback state, tutorial and recovery controls.

Reports: `dist/macos/verification-0.1.0-beta.2-x86_64.json` and the
corresponding `-arm64.json`. Screenshots/browser evidence are retained under
`dist/macos/verification-evidence-0.1.0-beta.2-<arch>/`. The incomplete first
Intel run is preserved separately as `verification-0.1.0-beta.2-x86_64-first-attempt.json`.

Still unverified: a physical Intel Mac, clean-machine/download quarantine
installation, older macOS, Safari/Firefox movie playback, and beta.2 native
controller buttons. Those native controls and one full season through
rollover passed in the separate beta.1 acceptance pass; this turn did not
repeat a full season or change the launcher controls. Next is one friend
installing the matching ZIP, preferably on an Intel Mac.

## Verification results for 0.1.0-beta.1

The extracted archive passed all required game checks: save selector,
standard Warriors save, advance to the first Warriors game (October 21, 2026,
GSW 126 at OKC 140), rendered 22-player box score, export/restore through the
API and the browser's download/upload controls, quit/relaunch/resume, offline
startup with external networking denied, occupied port, duplicate launch,
and replacing the app while preserving saves/history/recovery/multiplayer
state byte for byte. The executable PATH was a nonexistent test directory.
No real saves were inspected or modified. The 53 focused regression tests
passed, and the ordinary CLI help entry point still runs.

A normal LaunchServices app launch started the server, initialized the
native controller, and successfully requested the default browser. Native
termination stopped the server and cleared its runtime file. The Mac was
locked, so computer-use tools could not visually inspect the launcher or
click its buttons; that visual check remains unverified. Browser screenshots
were rendered and inspected separately using the automated test browser.

See `dist/macos/verification-0.1.0-beta.1.json` and
`dist/macos/verification-evidence-0.1.0-beta.1/` for the exact artifact hash,
isolated paths, results, screenshots, and native startup/shutdown log.
