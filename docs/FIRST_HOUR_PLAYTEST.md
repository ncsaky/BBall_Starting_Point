# First-Hour Playtest: 2026-10-03

## Scope

Played the opening GUI workflow in Chrome at 1440x1000 with isolated save directories: create a Warriors franchise, complete all 12 tutorial steps, edit minutes, reload, inspect player/prospect reports, search the trade market, advance from July to opening night and simulate the first week, then open a played-game box score. Real user saves were not used or modified.

Repeated the workflow against the frozen Apple Silicon beta.3 app with external browser requests blocked. This is a first-hour regression pass, not another full-season acceptance test.

## Reproduced And Fixed

1. **Saved minutes were misrepresented after reload.** Curry had a persisted 31-minute target while the slider showed the coach's 33-minute projection. The current minutes card did not initialize the saved draft/locks. It now uses persisted targets (including zero), restores locks, and removes departed players from the draft before another save. Another player's slider adjustment preserves Curry's target. Basketball simulation rules were not changed.
2. **Failed minute autosaves left an unsaved edit on screen.** A rejected API response now displays an explicit failure and restores the last persisted dashboard values. The browser regression injects this failure and verifies both the reverted player and another player's preserved lock.
3. **Compact prospect rows did nothing.** Their report buttons lacked handlers; only the expanded board was wired. Compact rows now open prospect reports before/after sorting and after collapsing the expanded board. Wiring is idempotent so repeated dashboard setup does not attach duplicate report handlers.
4. **Tutorial replay was missing from the actual Settings dialog.** A replay entry existed in the old standalone settings view, while the dashboard Settings button opened a different dialog. The visible dialog now has a working Replay Tutorial button. It closes the settings dialog before starting the tour. Escape skips the tour and releases the game's inert state.
5. **Trade Finder reported an unsearched market after an empty search.** It now distinguishes an untouched search from a completed search with no legal, AI-approved offers. Changing/removing assets, clearing the market, or changing a finder target invalidates that status. Feedback is in a polite live region.
6. **Radar labels collided.** The SVG had large two-line labels squeezed into a 200x128 viewBox. A roomier 360x280 coordinate layout keeps each label in bounds and away from the plotted polygon. The rank-to-radius formula and proportional window resizing remain unchanged.

The rotation tutorial now explains immediate saving, redistribution to 240 minutes, blue locked targets, and the distinction between targets and actual game minutes.

## Verification

- 89 focused JavaScript tests passed: clipboard/windows, tutorial, first-hour UI, API transport, recovery UI, and startup-video behavior.
- Four static-media Python tests and the trade-presentation Python test passed.
- Four architecture tests and four icon tests passed. The loopback-startup regression passed with a disposable directory when invoked directly; the project environment does not currently have pytest installed.
- `scripts/verify_first_hour_browser.cjs` passed against the frozen Apple Silicon app: nine workflow checks, five simulated Warriors games, real box-score opening, and zero browser page errors. Report: `dist/macos/first-hour-beta.3/report.json`.
- Both beta.3 architectures passed the extracted-ZIP smoke harness: offline startup/video, port collision fallback, GUI save creation, first game, backup/export/restore, restart, duplicate-launch reuse, and app replacement without changing stored data. Reports: `dist/macos/verification-0.1.0-beta.3-{arm64,x86_64}.json`.
- Intel testing uses Rosetta on this Apple Silicon Mac, not a physical Intel Mac. Native controller buttons were not re-tested in this pass; prior beta acceptance covered them.
- `git diff --check` passed.

Screenshots: `dist/macos/first-hour-beta.3/workspace-before.png`, `offense-fixed.png`, and `first-week-box-score.png`.

To repeat the browser regression, start a game server with an empty, disposable save directory and supply its URL and an evidence directory:

```sh
PYTHONPATH=src python -B -m nba_gm_data.app_server --root . --save-dir /tmp/nba-first-hour-new/saves --port 8789
node scripts/verify_first_hour_browser.cjs http://127.0.0.1:8789/ /tmp/nba-first-hour-evidence
```

Playwright and Chrome are test-runner requirements, not player dependencies. The script refuses to start when the server already contains saves. It waits for hydration/API work before interacting with newly rendered controls.

## Remaining Priorities And Limits

- The default-workspace crowding found in beta.3 is addressed by the beta.4 follow-up below. A deliberately crowded custom layout can still exhaust Snap's fixed canvas; the game reports that rather than hiding or shrinking the player's windows.
- Real searches for Melton, Seth Curry, and a second-round pick returned no offers in the test save. The search completed successfully, but an accepted/executed GUI trade was not tested here. Trade-market breadth deserves a separate gameplay pass; zero offers alone is not evidence of an engine bug.
- The older `test_gui_concept74.py` suite has three failures and two errors: it still asserts removed Age/Pos/MPG columns, the old `seasonProspectStock` helper, and an older efficiency-grid source shape. These failures are not caused by the fixes in this pass, but mean the complete test suite is not green. The current clipboard tests cover the intended replacement behavior.
- No physical friend-device installation, Safari/Firefox playback, assistive-technology review, full-season replay, hosted multiplayer, or Windows build was performed in this pass.

## Downloads

- `dist/macos/NBA-GM-Sandbox-0.1.0-beta.8-macOS-arm64.zip`
- `dist/macos/NBA-GM-Sandbox-0.1.0-beta.8-macOS-x86_64.zip`

Previous beta archives are retained. Signing/notarization status is unchanged; the friend-build Open Anyway instructions still apply.

## Beta.4 Starter-Workspace Follow-Up

Absent or invalid browser layout preferences now get a packed starter workspace: Minutes + Availability and Calendar first, followed by Standings, Next Opponent, Team Signals and Weekly Efficiency as space permits. Other ordinary cards remain available in the gallery. Active seasonal decisions take priority instead of competing with the starter cards. A small-screen Calendar can start minimized, retaining its full-calendar expansion state; restoring it opens that full view.

The legal canvas remains a constant 130% of the workspace viewport. This layout can use its scrollable portion. It does not shrink all card text to accommodate more windows, and fresh small-screen tables receive minimum readable widths. Valid saved preferences, including partial legacy layouts, bypass initialization. Ordinary proportional resizing, window controls and phase enforcement remain unchanged.

The tutorial temporarily reveals and centers the actual card being explained, including gallery-only staff and development cards. Moving between steps restores the original arrangement before showing the next card. Completing or skipping restores the workspace and scroll position, without writing tutorial-only placements to storage or executing gameplay actions.

Verification:

- 94 focused JavaScript tests passed, including five new starter-workspace regressions.
- `scripts/verify_starter_workspace_browser.cjs` passed all five workflow checks: complete tutorial with real targets, Escape skip/replay restoration, four viewport sizes, custom-layout persistence, and gallery access. Viewports: 1024x768, 1280x800, 1440x1000 and 1920x1080. The visible starter cards do not overlap; Snap succeeds; minutes text remains 11px at scale 1. No browser page errors.
- The first-hour browser regression passed again against the source server with external requests blocked: all nine checks, five games and a real box score. Its prospect/radar checks now open those gallery-only cards through the gallery controls.
- The static-media tests passed again. These changes do not add new images, network services or gameplay rules.
- The starter-workspace browser pass also passed against the frozen beta.4 Apple Silicon app. Report and four screenshots: `dist/macos/starter-workspace-beta.4/`. The source first-hour follow-up report is at `dist/macos/first-hour-beta.4/report.json`.
- Both extracted beta.4 ZIPs passed the full packaging smoke harness, including offline video/fallback, save creation, first game, browser and API backup/restore, restart, duplicate launch and app replacement. Reports: `dist/macos/verification-0.1.0-beta.4-{arm64,x86_64}.json`. Intel testing is still Rosetta-only.
- Initial packaging attempts stopped at an obsolete test expectation that Team Identity is open automatically. The smoke runner now opens gallery-only cards through gallery controls; the incomplete reports are retained with `-first-attempt` suffixes. The final reports have `checks.complete: true`.

Both browser runners require an empty, isolated server save directory. To repeat the layout-specific pass:

```sh
PYTHONPATH=src python -B -m nba_gm_data.app_server --root . --save-dir /tmp/nba-starter-new/saves --port 8790
node scripts/verify_starter_workspace_browser.cjs http://127.0.0.1:8790/ /tmp/nba-starter-evidence
```

## Beta.5 Performance Follow-Up

The source first-hour browser workflow passed again with external requests blocked: all nine checks, five Warriors games, a real box score and no browser page errors. Evidence: `dist/macos/first-hour-beta.5/report.json`. Hidden asset windows no longer delay initial dashboard entry; asset data is loaded when needed, with retry and stale-response handling. Lineup scoring is precomputed per player/position while preserving exhaustive search and exact outputs. See `docs/PERFORMANCE_PASS.md` for the benchmark and regression evidence. Earlier verification limits still apply.

## Beta.6 Basketball Accounting Follow-Up

Beta.6 corrected newly simulated shooting lines and overtime shot/minute totals. Both extracted ZIPs passed the packaging/browser smoke harness. The simulation audit covers 3,705 fixed-roster games plus a complete career through rollover; it is separate from the original nine-check first-hour workflow. See `docs/BASKETBALL_REALISM_AUDIT.md` for the historical results and calibration concerns. Intel testing remains Rosetta-only.

## Beta.7 Schedule Integrity Follow-Up

Beta.7 gives new franchises and future rollover schedules 82 regular-season games per team; existing schedules and played results remain unchanged. A rare overtime rounding violation is also repaired. Eleven generated schedules, 3,690 fixed-roster games and a full disposable career through rollover passed the relevant checks, including all 1,312 archived career games. Both final architecture ZIPs passed the extracted-package smoke harness with offline video/fallback and full calendar schedule checks. This does not claim a repeat of all nine original first-hour interactions. See `docs/SCHEDULE_INTEGRITY.md` for evidence, preserved diagnostic failures and remaining limits. Intel verification remains Rosetta-only.

## Beta.8 Friend-Feedback Follow-Up

The latest downloads are beta.8, adding a local Report an Issue download from Settings and the save screen. No report is uploaded and saves are not attached automatically. The nine-check first-hour source browser regression passed again with external requests blocked; evidence: `output/feedback-2026-10-04/first-hour/report.json`. Dedicated desktop/mobile report checks and both final extracted-package smoke harnesses also passed, including correct version metadata, report downloads, offline video/fallback, first game, backup/restore and save preservation. See `docs/FRIEND_FEEDBACK.md` for scope and privacy limits. This does not claim all nine first-hour interactions were repeated against the frozen packages; their packaged checks use the separate smoke harness. Intel testing remains Rosetta-only.
