# Browser interface tests

All 29 Node test files exit successfully. They report 246 passing checks and one expected failure for a startup video bug. All five Python GUI guards pass.

- `first_hour_ui` — The test loaded the minutes and save functions without their rust and team-signal helpers. Loading those helpers restored the saved-minute, lock, and error checks.
- `gui_simulation_motion` — The final score moved into an animated banner, and live calendar updates now merge with the dates already loaded. The test checks the banner and verifies that a February score replaces its scheduled entry while January games stay available.
- `player_pages` — The test slice picked up a browser click listener, and its old page layout predated the injury map. The test now checks the Injury risk label, body maps, paging, latest five games, 15-game score chart, and four-year payroll. In `app.js` the initial page count still says `1/2` for a regular three-page card. The paging handler corrects it to `1/3` when attached.
- `postseason_ui` — The tests pinned old cache-busting values. They now check that the correct stylesheets and script are loaded with a version parameter, along with the existing controls, confetti, and reduced-motion checks.
- `seasonal_clipboard` — Markers, markup, and test browser stand-ins fell behind the current workspace. The tests now check the origin badges, gallery icons, injury ticker, minutes and development rows, calendar, and window behavior as rendered today. The coach card test waits for the request and verifies that the card uses the same portrait as the staff row.
- `starter_workspace` — The old expectations opened Calendar at its full monthly size. The tests now check the compact Calendar, readable starter widths, and non-overlapping windows across screen sizes.
- `startup_video` — The fake browser lacked the second video element and the playback promise used to switch the backdrop. The tests now cover playback, pausing, cleanup, and photo fallback. A corrupt or missing default video still retries on each click because `startup-video.js` records the failure but ignores it for the default channel. The no-retry check still runs as an expected failure.
- `ui_product_audit` — The extension schedule now calls a helper to build its four payroll seasons. The test loads that helper and verifies that the offered salary only applies from the server-provided start season for the selected term.

Verified with `for f in tests/*.test.cjs; do node "$f" || echo FAIL "$f"; done` and `PYTHONPATH=src .venv/bin/python -m unittest tests.test_gui_concept71`.
