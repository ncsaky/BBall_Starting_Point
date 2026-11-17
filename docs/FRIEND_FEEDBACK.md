# Friend Feedback

2026-10-04, private macOS beta.8.

## Reporting A Problem

Choose **Report an Issue** on the save screen, or in the game's **Settings**.
Write a short summary, the steps you took, what you expected and what actually
happened. **Download Issue Report** creates a JSON file to send to the game's
creator. Nothing is uploaded, and no account or internet service is required.

The form opens immediately. Build metadata is fetched from the local server
with a 3.5-second deadline; an unavailable server does not prevent a download.
The diagnostics disclosure lets a tester inspect the included information.
Notes are included as written: do not put passwords or personal information
in them. Escape closes the report or returns to Settings; ordinary dialog
focus trapping and focus restoration apply.

## Included And Excluded

Included: the report timestamp and notes; exact packaged beta version from
the bundled build manifest; OS release, running architecture and Python
version; browser family/major version; viewport, pixel ratio and reduced-motion
preference; screen, phase/date/season and visible card dimensions; video
playback/readiness/error code; up to 40 recent game action names, durations and
success flags; up to 40 generic browser error/rejection markers.

Excluded from automatic diagnostics: saves and their names, player/manager names, file paths, credentials,
authentication/session tokens, action payloads, raw errors or stacks, launcher
logs, screenshots, full user-agent strings and persistent tracking identifiers.
An allowlist builds the report rather than serializing application state.
Action/error history lives only in page memory and resets on reload. Reports
are captured when opened, not a continuously updated recording. Build metadata
can finish loading afterward without replacing typed notes.

The report does **not** reproduce a whole franchise. When a save is necessary,
request a separate **Export Backup** ZIP with the tester's consent. That ZIP
contains the game state/history and is not a privacy-filtered issue report.
Screenshots may also be shared separately after checking their contents.

This is a local download workflow, not an issue tracker, automatic crash
uploader or hosted multiplayer reporting service. It cannot report a native
launcher failure that occurs before the browser opens. Existing launcher
startup-error/log-location behavior remains unchanged. Generic error markers
identify that an error occurred but intentionally omit its detailed message.

## Verification

- Four runtime-metadata unit tests cover developer/frozen versions, ignored
  private payloads, no save/canonical reads, and missing/corrupt metadata.
- API security regressions retain token/Host/Origin checks and block the local
  metadata action on public-only servers and through multiplayer game actions.
  The focused runtime/security/save-recovery/architecture Python run passed
  53 tests. This is not a claim that the full repository test suite is green.
- Seven JavaScript feedback tests cover allowlisted context, bounded history,
  sensitive-error exclusion, offline reporting, local downloads, late-response
  handling and timeouts during session acquisition. All 109 JavaScript tests
  passed.
- `scripts/verify_feedback_browser.cjs` passed the source-browser workflow at
  1440x1000 and 390x844: local downloads from both entry points, no notes sent to
  the API, keyboard focus/Escape, unavailable metadata and unchanged gameplay.
  Screenshots and downloaded fixtures: `output/feedback-2026-10-04/source-browser/`.
- The nine-check first-hour source browser regression passed with external
  requests blocked, including tutorial, minute persistence/failure recovery,
  prospects, trade search, first-week simulation and a played box score.
  Evidence: `output/feedback-2026-10-04/first-hour/report.json`.
- Both final extracted beta.8 architecture ZIPs passed the complete packaging
  smoke harness, including local report downloads from the save screen and
  Settings with version `0.1.0-beta.8`, offline video/fallback, full calendar
  schedules, first game, backup/restore, restart, duplicate launch and
  byte-for-byte save preservation after app replacement. Reports:
  `dist/macos/verification-0.1.0-beta.8-{arm64,x86_64}.json`, both with
  `checks.complete: true`. All feedback source hashes match both manifests.

The first packaged probe revealed that `CFBundleVersion` is the generic macOS
build number `1`, not the beta release. Runtime reporting now reads only the
version field from the already-bundled build manifest. Intermediate packages
and reports are retained separately; final packaging acceptance requires the
reported version to match the archive's release version.

Those intermediate ZIPs/reports are under
`dist/macos/superseded-beta.8-version-metadata/`; use the final top-level ZIPs.
An initial final-source Apple Silicon probe stopped at the photo-opacity check;
the runner now waits up to 30 seconds for the crossfade state before retaining
the same visibility assertions. Its incomplete report is preserved as
`verification-0.1.0-beta.8-arm64-crossfade-attempt.json`. No video or artwork
was changed in this pass.

## Repeat

```sh
PYTHONPATH=src:tests python -B -m unittest test_diagnostics test_api_security
node --test tests/feedback.test.cjs tests/api_transport.test.cjs
PYTHONPATH=src python -B -m nba_gm_data.app_server --root . --save-dir /tmp/nba-feedback-new/saves --port 8791
node scripts/verify_feedback_browser.cjs http://127.0.0.1:8791/ /tmp/nba-feedback-evidence
```

Use an empty, disposable save directory. The browser runner refuses a server
with existing saves. It creates one temporary franchise only for the Settings
entry-point regression. Playwright and Chrome are test requirements, not player
dependencies. Intel packaging verification uses Rosetta on this Apple Silicon
Mac; physical Intel, clean friend-device and assistive-technology testing remain
separate checks. Browser interaction verification used Chrome, not Safari or
Firefox.
