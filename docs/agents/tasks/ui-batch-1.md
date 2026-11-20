# UI batch 1: draft night, playoffs, roster cut-down, card gallery

_Claude Opus agent, own worktree branch `worktree-agent-ac8d87ae0dbef4471`, 2026-11-19. Status: **review** (committed
on the branch, not pushed or merged). Main (`codex/immersive-franchise-journey`, with smart rest and the prospect-card
relabel) is merged into the branch._

**TL;DR**
- **Draft night looks and behaves like one room:** the prospect board now matches the expanded Upcoming Prospects card
  (bigger, with consensus, your board, scouts' read, scouted bar, fit and injury), and it opens side by side with the
  draft order, centered, once. Every pick gets a short animation exactly once, with a Skip button.
- **Playoffs open with the bracket, Playoff Stats, a new Playoff Injuries card and Minutes + Availability**, once per
  postseason. Reloads no longer rearrange the screen or reopen windows you closed (that was a real loading bug).
- **The roster cut-down is now a proper table:** Keep / Waive / Buy out per player, a live "15 / 15" counter, contract
  and release costs, and one confirmed "Release" button. The card gallery shows drawn previews of each card.

## Resume state
- Done: all seven items, tests, screenshots, this report, board row (`review`). Branch commits: checkpoint `6f3a10f`,
  merge of `codex/immersive-franchise-journey`, final commit. Not pushed or merged.
- Scratch saves and the screenshot driver live in `output/ui-batch-1/` (git-ignored): `saves/` (draft night, playoffs,
  cut-down), `ui_draft_night.pristine.json` (copy it over `saves/ui_draft_night.json` to replay draft night),
  `shot.cjs` + `steps/*.cjs` (Playwright, run with `NODE_PATH=~/.hermes/hermes-agent/node_modules`; the project has
  no Playwright of its own).
- Worktree symlinks (`.venv`, Barttorvik raw, universe SQLite, injury evidence, BBI files, settlement output, and the
  startup movie `gui/assets/startup/video/front-office.mp4`) are untracked/ignored and were not committed; remove them
  before deleting the worktree.

## How I reached each screen (no season was played)
- **Draft night:** a new Charlotte save moved by date to 26 June 2027 and the draft phase (the method the draft-boards
  task used). Five Charlotte players were moved to free agency in that scratch save, otherwise Charlotte's five picks
  take the roster past 15 and the mandatory cut-down blocks the draft (see "Found along the way"). This changes
  Charlotte's "Fit for us" numbers in the screenshots, nothing else.
- **Playoffs:** a new Boston save moved to 19 April 2027 and the bracket started from projected standings, then three
  playoff days simulated through the normal app action (about 30 s). The injuries in the screenshots are real engine
  injuries from those games (Haliburton, Murray, Moody, Gueye, Hauser out; Kessler back on a minutes limit).
- **Cut-down:** a new Knicks save in preseason with two free agents added to the roster (17 of 15).

Screenshots: `output/ui-batch-1/screenshots/` (git-ignored, in this worktree). Desktop = 1440x900; narrow = 1024x768.

## 1. Draft-night prospect board (redesign)
- **What changed:** the board is drawn like the expanded Upcoming Prospects card, enlarged: two-digit consensus rank
  with where most teams rank him, college logo or country flag + name (click for the scouting report), Pos, Age, Ht,
  your scouts' Now → Pot, Your board with the monthly arrow, Scouts' read, a Scouted bar, Fit for us, the injury
  marker (history, current injury, projected risk) and Status. It uses the shared table style (double header rule,
  small bold headings, stripes, whole-row hover, sorted-column shading). Now and Pot sort separately from the same
  heading. The clock ("On the clock · Pick 5 of 60 · BKN"), your pick, the Available/All filter, the latest pick and
  the draft-trade news now sit at the top of the same card (before, they were rendered but belonged to no card).
- **Fixed on the way:** the clock showed your team for every pick (it read the board's point of view); it now shows
  the team that owns the pick. Sorting, filtering and selecting keep the board's scroll position and focus, and the
  draft order keeps its scroll too.
- **Rule check:** only the scouts' estimates and consensus numbers already in the board payload are shown; no hidden
  ratings.
- Screenshots: `d01_d02_draft_night_1440.png`, `d03_draft_selected.png` (your pick highlighted).
- Not checked: the very small "phone" layout (under 700 px), which the app does not really support.

## 2. Draft-night window layout
- **What changed:** entering draft night opens the Prospect Board and Draft Order side by side, centered at the top,
  sized to the window's height, with the other windows stepping aside (pinned windows stay). When the draft ends,
  the Draft Summary and Draft-Night Trades open the same way. This happens once; after that your own arrangement and
  closed windows are kept on every reload. On a narrow screen the row shrinks to the smallest readable size; if it
  still does not fit, the Draft Order sits to the right and the board area scrolls sideways (the page itself never
  scrolls sideways).
- Screenshots: `d01_d02_draft_night_1440.png`, `d02_draft_night_1024_reduced.png` (narrow: the Draft Order sits to the right), `d02_d03_finish_skip_1024_reduced.png` (results cards after Skip)

## 3. Per-selection animation
- **What changed:** each pick, when it first appears, slides in at the top of the board ("Pick #4 · ORL selects
  Caleb Holt", position, age and the GM's reason), the Draft Order row flashes, the prospect stays on the Available
  view for that moment struck through with a stamped "#4 ORL" badge, and the row flashes gold. Your own pick gets the
  same treatment ("Last pick #1"). Bulk reveals (Sim to my pick, Finish Draft) still play in order; the draft-trade
  phone alerts still appear once; your pick still stops the playback. New: **Skip to results** during playback.
  With reduced motion the movement is off (static highlight only) and picks advance faster, as before.
- **Once, checked:** a pick animates the first time it becomes the newest pick on screen, never again (re-renders,
  sorting, reloads and the final room after playback). In the browser: picks 1-10 each animated exactly once (reveal,
  order flash, badge stamp); two re-sorts afterwards started zero animations.
- **Fixed on the way:** playback used to replace the whole draft screen inside the Prospect Board window (so the
  board window briefly contained a second copy of the draft order and the separate Draft Order window did not move).
  Now each frame updates the two windows in place.
- Screenshots: `d03_draft_user_pick.png`, `d03_draft_playback.png`, `d03_draft_after.png`, `d02_d03_finish_skip_1024_reduced_playing.png` (narrow, reduced motion, Skip button). Skip checked in the browser: the button stays clickable while the app is busy, playback stops, the final room loads, and the results cards open together. With reduced motion no animation runs at all (zero animation events)

## 4. Playoff entry layout
- **What changed:** the first time you enter the playoffs, the bracket opens centered at the top and Playoff Stats,
  the new Playoff Injuries card and Minutes + Availability open in a row underneath, all inside the window at
  1440x900 with nothing overlapping. **It happens once per postseason, on entry.** Reloading the page, or coming back
  to the save later, keeps whatever you arranged; a window you closed by hand stays closed (checked: closed Minutes,
  reloaded, it stayed closed and nothing moved). On a small laptop screen (1024x768) the cards shrink to their
  smallest readable size and Minutes sits to the right of Playoff Injuries, partly past the window edge (the board
  area scrolls sideways; the page does not). On an even shorter screen, cards that cannot fit stay closed rather than
  piling on top of each other. The bracket's own content is wider than a 1024 screen (as before this task).
- **Real bug fixed:** while a save was loading, the card board stored a blank phase, so every reload looked like a
  fresh entry and re-ran the entry layout (in the playoffs that hid every window except the bracket, each time). The
  board now ignores the loading pass. This also protects the draft lottery and draft-night layouts.
- Screenshots: `po02_playoff_entry_1440.png`, `po02_playoff_reload_after_closing_minutes.png`,
  `po02_playoff_entry_1024.png`

## 5. Playoff Injuries card (new)
- **What it shows:** players on teams still in the playoffs who are out injured, or back but still rusty or on a
  minutes limit. Columns: player (headshot), team, OVR / OFF / DEF with bars (his usual ratings, the same numbers as
  the roster tables), status (the engine's diagnosis, e.g. "Ankle Sprain", or "Back: rust −1.2, 70% min"), and
  expected back (return date and about how many games, or "Normal in 3g"). Sorted by OVR by default; every column
  sorts. A **Playoff teams / Your team** switch at the top, with "5 out · 1 easing back". Default scope: league-wide.
- **Data:** a new read-only action `playoff_injuries` (in `app_actions.py`, outside the draft/trade/rest code) that
  reads the engine's health state, the same rust and minutes-limit numbers the Minutes card and player card use, and
  the displayed ratings. Teams knocked out (series losers, play-in teams that missed) drop off. No engine change.
- Screenshot: `po03_playoff_injuries_card.png`
- Not checked: a team with many simultaneous injuries late in a long playoff run (only three playoff days were played).

## 6. Mandatory roster cut-down (redesign)
- **What changed:** a header with the rule ("Regular-season rosters hold 15 players. Everyone is kept unless you mark
  him Waive or Buy out") and a live counter ("15 / 15 players after your choices · 17 on the roster · 2 must go · 2
  marked", red until enough are marked, then green). The table (house style, headshots) shows Pos, Age, Ht, MPG, OVR
  bar, Contract (this season, seasons left, every season on hover), **If waived** (salary that stays on your books,
  waiver clearance date) and **If bought out** (payout and savings if he clears), then a Keep / Waive / Buy out
  choice per player (arrow keys move between the three). The footer names who is being released and the salary
  owed; **Release N players** stays disabled until enough are marked, then asks for confirmation (listing each player,
  the cost and buyout cap charges) before anything is sent. The mandatory stop is unchanged.
- **Data:** costs come straight from the engine's waiver and buyout quotes; nothing invented. The payload now also
  sends the player's height (it was blank) and headshot.
- Screenshots: `fa02_cutdown_1440_initial.png`, `fa02_cutdown_1440.png` (one Waive, one Buy out marked), `fa02_cutdown_1024.png` (narrow: header and Release footer stay in view, the table scrolls)
- Not checked in the browser: actually releasing (the confirmation was dismissed in the run, so no save changed).
  The release calls are the same two app actions the old buttons used.

## 7. Card-gallery previews
- **What changed:** every gallery thumbnail is now a small drawing of that card's real layout (title bar, then its
  own table with stripes and bars, radar, bracket, calendar, line chart, payroll bars, lottery grid, player card,
  and so on), inside the existing beveled button. They are static, so they never show half-loaded or clipped content.
  Missing descriptions were fixed ("Team Wants" and the trade tools used to say "Team strengths"; the new injuries
  card says "Injured & returning players").
- Screenshots: `u01_gallery_first_group.png`, `u01_gallery_season_group.png`, `u01_all_previews.png` (every card)

## Checks run
- `node --test tests/*.test.cjs`: 262 pass (10 new in `tests/ui_batch_1.test.cjs`: layout once / centered / no
  overlap / narrow wrap; each pick animates once; Skip; cut-down counter; injuries sort and filter; previews).
  `tests/postseason_ui.test.cjs` needed one helper added to its fake page (the playoff workspace now also draws the
  injuries card).
- Python GUI guards (`tests.test_gui_concept71`, `tests.test_gui_concept74`): OK. New
  `tests/test_playoff_injuries_card.py` (5): OK.
- `bash scripts/run_core_tests.sh` (after merging main): 337 tests OK (2 skipped).
- Running app (port 8783, scratch save folder), headless Chromium: desktop, 1024x768 and reduced motion; keyboard:
  choosing a draft pick with Enter, cut-down choices with arrow keys, gallery group with Enter, injuries scope
  buttons; no sideways page scrolling on any screen (measured 0 px each run).
- Not run: the full suite, the two scorecards (no engine change), a real season into the draft.

## Found along the way (not changed; not mine to change)
- **Draft night can trigger the mandatory cut-down in a normal career.** Rosters are usually 15 at draft time (deals
  expire later), so your first pick makes 16 and the cut-down window blocks the rest of the draft. The cut-down rule
  (`refresh_roster_cutdowns` in `save.py`) applies in every phase. Real NBA rosters only have to be at 15 before the
  regular season. Suggest limiting the cut-down to training camp / preseason / regular season.
  - Related: when that happens during "Finish Draft", the draft playback cannot run (the cut-down blocks draft
    actions) and the board stays empty until the page is reloaded, where the cut-down card appears. With the draft
    entry layout the other windows are already put aside, so the empty board is more noticeable than before. Fixing
    the cut-down timing above removes it.
- The Assistant GM phone overlay can cover the right edge of the Draft Order on smaller screens (existing overlay).

## Questions for you
1. Draft night now clears other windows when it opens (pinned ones stay). Keep that, or leave your season windows
   open behind the draft?
2. On a 1024x768 screen the playoff cards shrink and Minutes + Availability sits partly past the right edge (the board
   scrolls sideways). OK, or would you rather Minutes not auto-open on small screens?
3. Playoff Injuries lists only teams still alive. Should eliminated teams' injuries stay visible (greyed)?
4. The draft board keeps the drafted prospect on the Available view for the moment his pick is announced. Like it, or
   remove him immediately?
5. The gallery previews are generic drawings, not live snapshots. Good enough, or do you want a few signature cards
   (bracket, prospect board) drawn in more detail?
