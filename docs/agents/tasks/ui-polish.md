# UI-POLISH: overnight visual and UX polish pass

_Claude Opus agent, own worktree branch `worktree-agent-abbc1f6f658d21d15`, 2026-11-21 (overnight). Status: **review**
(committed on the branch, not pushed or merged)._

**TL;DR**
- **Pop-up windows and messages now always appear on top.** Before, Settings, box scores, League Leaders, Full Standings
  and the little "saved" messages could open *behind* the board's windows (even in the default layout).
- **The playoff bracket fits its window** (at 1024 px wide the whole East half used to be missing), plus 11 smaller
  fixes: clearer start screen, "Building your league…" feedback, readable dates, a Full Standings table in the house style.

## Resume state
- Done: audit, 13 fixes, tests, before/after screenshots, this report, board row (`review`). Committed on the branch.
- Scratch material in `output/ui-polish/` (git-ignored): `shoot.cjs` + `steps/*.cjs` (Playwright, run with
  `NODE_PATH=~/.hermes/hermes-agent/node_modules`), `run_pairs.sh`, `saves/` (copies of earlier agents' regular-season and
  playoff saves, plus two fresh careers), `base/src` (the branch's starting code, used for the "before" shots),
  `shots/audit/` (all audit screenshots). Servers were stopped at the end.

## What I looked at
Ran the game from this branch on a fresh career (created through the start screen; no simulation) and on copies of
earlier agents' saves (Boston on Oct 29 with a week of games played; Boston in the first playoff round), so nothing had
to be simulated. Screenshots at 1440×900 and 1024×768. The app has only a light theme, so there is no dark-mode set.
Screens: start screen (Load Save, New Save, career creation), the season board (all 16 season windows), player card
(all three pages), team pages (own and another team's: roster, stats, contracts, picks), staff room, box score,
League Leaders, Full Standings, Settings, playoff bracket, Playoff Stats, Playoff Injuries, preseason-outlook slideshow.

## Audit list
| # | Problem | Status |
|---|---|---|
| 1 | Dialogs (Settings, box score, League Leaders, Full Standings, Player Finder) open **behind** board windows. Windows are stacked 1, 2, 3… by how recently they were raised, and dialogs sat at level 30, so any window past the 30th level covered them. Happens in the default layout too: the Minutes window covers part of Settings. | **Fixed** |
| 2 | Short messages ("toasts", bottom-right) hide behind any window in that corner (level 20). | **Fixed** |
| 3 | On a busy Mac, some of the page's ~60 files (stylesheets, scripts, logos) fail with "connection reset", so the game shows up half-styled or with missing logos. The local server only let 5 connections wait. Seen three times tonight while the laptop was loaded (once it broke a whole page load). | **Fixed** |
| 4 | Playoff bracket cut off at the window edge: at 1024 px the East half is missing; at 1440 px the right-hand play-in column is clipped. | **Fixed** |
| 5 | Play-in placeholders ("9/10 WINNER", "7/8 LOSER") wrap onto two lines and spill out of their boxes; empty series show a made-up "0 – 0". | **Fixed** |
| 6 | Dialog title bars show an empty grey square that looks like an unticked checkbox. | **Fixed** |
| 7 | Start screen: the main action of each panel (Enter Save, Create New Save, Create Lobby) looks exactly like the secondary buttons. | **Fixed** |
| 8 | Creating a career gives no feedback: the screen just dims for a minute or more. | **Fixed** |
| 9 | Saved-league list reads "tables_check \| BOS \| 2026-10-29". | **Fixed** |
| 10 | League Wire shows raw dates ("2026-10-21") while the rest of the game says "Oct 29". | **Fixed** |
| 11 | Full Standings dialog breaks the table style (rule 12): no logos, columns spread across the page, a big "Close" text button unlike other dialogs, raw date in the title. | **Fixed** |
| 12 | Four Factors labels (eFG%, TOV%, OREB%, FTR) are unexplained short names. | **Fixed** (hover explanations) |
| 13 | Close buttons' hover text reads "Close (Esc) (Esc)". | **Fixed** |
| 14 | Player headshots are blank until the remote picture arrives (and stay blank offline). | Left: a placeholder touches out-of-scope screens (trade room, free agency) and risks a flicker on every redraw. Better fix: keep headshots locally (see "What's left"). |
| 15 | "League Leaders" actually lists players by rating (OVR), not stat leaders. | Left: content decision, not look. |
| 16 | League Wire wording repeats itself ("leave extension talks unresolved: extension talks remain unresolved"). | Left: message wording is another agent's area. |
| 17 | Opening several windows piles them on top of each other (each new window lands in the same spot). | Left: layout-engine change; worth a decision. |
| 18 | Team-page Roster/Stats tables use 9-10 px text and short headers (Shot, Cre, Rim, Ath). | Left: readable, but a bigger type pass is a design decision. |
| 19 | Team Identity court charts: the colour legend sits on the court's baseline in the small window. | Left: minor. |
| 20 | At 1024 px the fitted bracket is about 68% size (small text). | Left: the window can be enlarged; a compact small-screen bracket is an idea below. |
| 21 | Title bar shows a dark focus outline when a window is opened from the keyboard. | Left on purpose: it is the keyboard-focus marker (accessibility). |
| 22 | Draft room / draft boards: the saved draft-night career had already moved on to free agency, so only Upcoming Prospects was checked (looks fine). Assistant GM phone: no texts were waiting in these saves, so it was not seen. | Not audited visually |

Screens that looked fine and were left alone: Minutes + Availability, Player Development, Coaching Staff, Standings and
Next Opponent windows (already in the house table style), Calendar, Team Signals, Morale, Offense/Defense radars,
Weekly Efficiency, MVP, box score, player card pages, Playoff Stats, Playoff Injuries, preseason-outlook slideshow.

## The fixes (before / after screenshots in `output/ui-polish/`)
Nothing here changes a number or where one comes from (rule 4).
1. **Dialogs above windows** (`styles.css`: dialog layer 30 → 1500, the level the trade window already used).
   `01_dialogs_before.png` / `01_dialogs_after.png` (Settings after windows were used), and
   `06_dialog_icon_before.png` (default layout: the Minutes window covers Settings).
2. **Messages above everything except the tutorial and slideshows** (`styles.css`: 20 → 16000).
   `02_messages_before.png` / `02_messages_after.png` (a window in the bottom-right corner hides the message before).
3. **Server waiting line 5 → 128** (`app_server.py`, one line; the standard library default was 5).
   `03_server_before.txt` (the 29 failed loads logged before the fix) / `03_server_after.txt` (no failures since, in every
   run).
4. **Bracket fits its window** (`ui-polish.js` measures the bracket and scales it as one picture; logo flights still land
   correctly because they use screen positions). `04_bracket_1024_before.png` / `04_bracket_1024_after.png`.
5. **Quiet placeholders** (`ui-polish.css`: grey italic, one line; empty series no longer show 0). Real teams always have a
   logo, so only empty slots change. `05_bracket_placeholders_before.png` / `05_bracket_placeholders_after.png`.
6. **Dialog icons**: box score, playoff box score, League Leaders, Player Finder, Settings, Report an Issue, Champion and
   Full Standings get coloured icons from the window icon set (`window-icons.js` "modal:" entries, `modalWindowMark` in
   `app.js`). Trade dialogs keep their old mark (other agents' area). `06_dialog_icon_before.png` / `06_dialog_icon_after.png`
   (the old grey square is also visible top-left in `shots/audit/m_boxscore_1440.png`).
7. **Start-screen main buttons in blue** (`ui-polish.css`). `07_start_buttons_before.png` / `07_start_buttons_after.png`.
8. **"Building your league…"** on the Create button while the league is built; always restored, also on errors
   (`createSave` in `app.js`). `08_new_save_feedback_before.png` / `08_new_save_feedback_after.png`.
9. **Saved-league list** now reads "name · BOS · October 29, 2026". `09_save_list_before.png` / `09_save_list_after.png`.
10. **League Wire dates** "Oct 21" (the exact date stays in the page for screen readers).
    `10_league_wire_before.png` / `10_league_wire_after.png`.
11. **Full Standings in the house table style**: window title bar with icon and "October 29, 2026", small bold headers over
    a double rule, alternating rows, whole-row hover, team logos, your team marked, a dashed line above the play-in
    places, small × close like every other dialog. `11_full_standings_before.png` / `11_full_standings_after.png`.
12. **Four Factors hover text**, e.g. "Turnover %: share of possessions that end in a turnover. Lower is better. League
    average 12.9. Rank #2 of 30." (before: "League average 12.9"). Native tooltips do not show in screenshots:
    `12_four_factors_before.txt` / `12_four_factors_after.txt`.
13. **Close tooltip** no longer repeats "(Esc)" (`interface.js`). Text-only change.

New files: `gui/ui-polish.css` (loaded last; each block names its fix) and `gui/ui-polish.js` (bracket fit only).

## Tests
- `for f in tests/*.test.cjs; do node "$f"; done`: **all 41 files pass**, including the new `tests/ui_polish.test.cjs`
  (9 checks: layering numbers, server waiting line, load order, bracket-fit arithmetic, placeholders, dialog icons, dates,
  create-button feedback restored on error, tooltip). Two existing tests updated for the new code, no behaviour loosened:
  `save_recovery_ui.test.cjs` now loads the date formatter the save list uses; `postseason_ui.test.cjs` accepts the
  standings dialog in the shared title-bar selector.
- `test_gui_concept*`: 17 OK.
- `scripts/run_core_tests.sh`: **338 tests OK** (2 skipped, as on main).

## What's left (bigger ideas for your decision)
1. **Keep player headshots on disk** (download once, serve locally): pictures appear instantly and work offline; today
   every headshot comes from a remote image service.
2. **Open new windows in free space** (or a "tidy" button that tiles open windows): opening several windows currently
   stacks them on the same spot.
3. **A real League Leaders page** by stat (points, rebounds, assists, efficiency) next to the current ratings list.
4. **A type scale**: window text ranges from 9 px to 16 px with no shared rule; three sizes (11 / 12 / 14) would make the
   board feel more finished, starting with the team-page Roster and Stats tables.
5. **Compact bracket for small screens** (one conference at a time with a toggle) instead of shrinking the whole bracket.
6. **Dark theme**: none exists; the colour tokens in `production-skin.css` would make one feasible.

## Merge notes for the coordinator
- `index.html` cache-busting versions changed for `styles.css`, `card-board.css`, `interface.js`, `window-icons.js` and
  `app.js` (all `ui-polish-1`): an easy one-line conflict if another branch bumped the same file tonight.
- `card-board.css`: `.modal-standings` added to the eleven shared `:is(.modal-box-score,.modal-settings, …)` title-bar
  selectors (one `sed`-style change).
- `app.js` touches only: `createSave`, the saved-league list line in `loadSaves`, `seasonLeagueWire` dates,
  `seasonFactorBar`, `openStandingsModal` / `dashboardStandingsTable` (opt-in logos), `renderModal` (class, title-bar list,
  icon) and the new `modalWindowMark`. No free-agency, offseason or trade code.
