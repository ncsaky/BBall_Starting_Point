# TABLES-ICONS: one table style for the five season tables, and window icons

_Claude Opus agent, own worktree branch, 2026-11-19. Status: **review** (committed on the branch, not pushed or merged)._

**TL;DR**
- **Minutes + Availability, Player Development, Coaching Staff, Standings and Next Opponent now share one table style**
  (the draft-night board look): double header line, small bold headers, white/grey stripes, whole-row hover, a soft
  shaded sorted column, and the same dark bar style. Every meaningful column sorts by click or keyboard.
- **Sorting only moves rows.** Nobody's minutes change, a dragged minutes slider no longer has rows jumping under it
  (they settle when you let go), Standings always shows each team's real seed, and Next Opponent keeps its sort
  through the between-games animation.
- **Every window type has its own icon** (54 icons in 12 colour groups, plus one fallback) in the window switcher and
  on each window's title bar. All of them are on one sheet for your approval, and any icon is a one-line swap.

## Resume state
- Done: shared table system, the five tables (plus the staff room's two tables), the icon set, tests, browser checks,
  this report, board row (`review`). Committed on the worktree branch; not pushed or merged.
- Scratch material lives in `output/tables-icons/` (git-ignored, in this worktree): `saves/` (Boston, seed 11,
  simmed to 29 Oct 2026; `tables_check.oct29.json` is the pristine copy), `shot.cjs` + `steps/*.cjs` (Playwright,
  run with `NODE_PATH=~/.hermes/hermes-agent/node_modules`), `sheet.cjs` (icon sheet), `app_check.py` (server
  actions). Server: `PYTHONPATH=src .venv/bin/python -m nba_gm_data.app_server --root . --save-dir output/tables-icons/saves --port 8785`.
- Worktree symlinks (`.venv`, Barttorvik raw, universe SQLite, injury evidence, BBI files, settlement output, the
  startup movie) were removed before committing; recreate them (task brief) to run the app or tests here again.

## What changed
- **New shared pieces** (one system, not five copies):
  - `gui/house-table.js`: the one sort comparator (numbers, text without case or accents, missing values last, ties
    in the table's own order), header markup (a real button inside each column header, `aria-sort` set), striping in
    on-screen order, and the sorted-column placement.
  - `gui/house-table.css`: the house style as variables (`--house-row-alt`, `--house-sorted-cell`, `--house-bar-track`,
    `--house-bar-width`, ...), loaded after the older sheets. Tables opt in with `data-house-*` attributes, so their own
    class names and column layouts are unchanged.
  - `app.js`: a short column inventory (`HOUSE_TABLE_COLUMNS`), sort state per table, one click handler for all
    headers, and a re-apply after every redraw (dashboard render, expanded standings, staff room, live sim updates).
- **Minutes + Availability:** sort by Player, Pos, Height, Minutes (default), Fatigue. Rows now hold still while a
  slider is being dragged and re-sort when it is released (before, rows moved under the pointer mid-drag). Keyboard
  focus stays on the control after a re-sort. The minutes value is bold only when Minutes is the sorted column.
  Sliders, the fatigue bar, "Coach rests players", the zZ rest button, rest/injury/rust markers and user-locked
  minutes (blue slider with ×) all checked working after a week of simulation.
- **Player Development:** sort by Player, Age, Growth runway, and Rating change (three ways: "Change" = biggest
  movers up or down, the default and the old order; "Season" and the month = biggest gain first). Fixed on the way:
  the decline arrow was drawn on top of its number ("↓0.4/yr" was unreadable); it now sits beside it.
- **Coaching Staff (card and staff room):** sort by Staff member (role order, head coach first, the default), Grade,
  Contract (salary per season). The staff room's "Available Staff" list sorts the same way (default: grade).
- **Standings:** sort by #, Team, W-L, Win%, GB. # always shows the true seed; the playoff and play-in lines only show
  in seed order. Your team keeps its blue row with a left mark, also on hover and inside the sorted column. Live sim
  updates keep the chosen sort.
- **Next Opponent:** same sorts as before (Player, OVR, OFF, DEF, PTS, REB, AST), now through the shared comparator.
  The old measured "sort band" overlay is gone; the shared column fill replaces it. During a week's sim the result
  banner, the switch to the next opponent and the chosen sort (PTS) all held.
- **Bars:** one unfilled darkness (`#172228`, the draft board / Playoff Injuries / roster convention) and one height
  (5 px) across the five tables; rating bars (opponent OVR/OFF/DEF and header ranks, staff grade) share one width
  (32 px). Scales that mean something keep their shape: minutes 0-48 slider, six-step fatigue with its colours, the
  development bars' centre line (gain right, loss left).
- **Window icons:** `gui/window-icons.js` maps every window type to a group colour and a drawing; the switcher and the
  title-bar tab use it. Player-card windows get the icon of their kind (player, coach, fantasy, prospect, free agent,
  contract extension). Unknown windows get a neutral "window" icon. Preview page: `/window-icons-sheet.html`.
  To swap an icon, change its glyph name in `WINDOWS` (or edit its drawing in `GLYPHS`). The card-gallery previews
  are unchanged.

## Per-column sort inventory
| Table | Column | Sorts by | First click | Notes |
|---|---|---|---|---|
| Minutes + Availability | Player | name (A-Z, accents/case ignored) | A-Z | |
| | Pos | point guard (1) → center (5); combos in between (G-F = 2.5) | PG first | |
| | Height | inches | tallest first | |
| | Minutes | minutes shown on the slider (injured/resting = 0) | most first | **default** |
| | Fatigue | engine fatigue today (0-100) | most tired first | |
| Player Development | Player | name | A-Z | |
| | Age | age | youngest first | |
| | Growth runway | runway 0-5; veterans on decline watch as a negative (their yearly drop) | most room first | steepest decline last |
| | Rating change: Change | size of this season's change, up or down | biggest mover first | **default** (old order) |
| | Rating change: Season / month | signed change | biggest gain first | |
| Coaching Staff (+ staff room) | Staff member | role order (head coach → scouting lead) | head coach first | **default** (staff room list: Grade) |
| | Grade | grade | best first | |
| | Contract / Asking contract | salary per season | highest first | |
| | (Fire / Negotiate) | not sortable | | a button column |
| Standings | # | true seed | 1 first | **default**; # never changes |
| | Team | abbreviation | A-Z | |
| | W-L | wins | most first | ties by seed |
| | Win% | win percentage | best first | |
| | GB | games behind (leader = 0) | fewest first | |
| Next Opponent | Player | name | A-Z | |
| | OVR / OFF / DEF | displayed rating | best first | OVR is the default |
| | PTS / REB / AST | per-game stat | most first | |

Everywhere: missing values (blank, "—") sort last in both directions; equal values keep the table's own order (so a
sort is deterministic and reversing it is clean). Headers are buttons: Tab reaches them, Enter or Space sorts, and the
column header carries `aria-sort`. A small ▲/▼ shows the direction.

## Table style matrix (present after this task)
| | Minutes | Development | Staff | Standings | Next Opponent |
|---|---|---|---|---|---|
| Sorting (T01) | yes | yes | yes | yes (seed kept) | yes (was already) |
| Whole-row hover (T02) | yes; markers, sliders, lock stay visible | yes | yes | yes, also on your team's row | yes |
| White/grey stripes (T03) | yes, in on-screen order | yes | yes | yes | yes |
| Sorted-column fill (T04) | yes | yes | yes | yes, with the active row | yes (replaces the band) |
| One bar style (T05) | slider + fatigue tracks | change bars track | grade bar | no bars (n/a) | rating + header bars |

## Screenshots
`output/tables-icons/screenshots/` (git-ignored, in this worktree; 1440x900 unless noted):
- Before: `before_1440_{minutes,development,staff,standings,opponent}.png`
- After: `after_1440_minutes_sorted_height.png`, `after_1440_minutes_hover_sorted.png` (sorted by fatigue, row
  hovered), `after_1440_development_sorted_age.png`, `after_1440_staff_sorted_grade.png`,
  `after_1440_staff_room_sorted_contract.png`, `after_1440_standings_sorted_team_active_hover.png`,
  `after_1440_standings_seed_order.png`, `after_1440_opponent_sorted_points.png`, `after_1440_board.png`
- Narrow + reduced motion (1024x768): `after_1024_reduced_*.png` (same set)
- Dragging minutes: `sim_minutes_mid_drag.png` (rows hold still), `sim_minutes_after_release.png` (re-sorted)
- After a week's sim: `simweek_opponent_banner.png`, `simweek_final.png` (rest, rust, injury markers, user-locked
  slider, Next Opponent still sorted by PTS)
- Icons: `window_icon_sheet.png` (all icons at switcher and tab size), `after_1440_window_switcher.png` (in the app)
- Keyboard and order results: `after_1440_results.json`, `after_1024_reduced_results.json`, `simweek_results.json`

## Checks run
- New `tests/tables_icons.test.cjs` (11): comparator (numbers, text, missing values, ties), headers and `aria-sort`,
  the column inventory, **sorting never changes minutes** (every column, both directions: minutes targets, slider
  values and user locks unchanged), rows still while dragging, standings seeds and lines, CSS rules, and the icon set
  (every board, phase and card window has its own non-fallback icon, no two share one).
- `node --test tests/*.test.cjs`: 273 pass. Updated for the new header buttons: `seasonal_clipboard`,
  `first_hour_ui` (they now load the shared helper via `tests/house_table_helpers.cjs`), `test_gui_concept74`.
- `tests.test_gui_concept71`, `tests.test_gui_concept74`: OK. `bash scripts/run_core_tests.sh`: 337 tests OK (2 skipped).
- Running app (port 8785, scratch saves), headless Chromium, 1440x900 and 1024x768 with reduced motion: keyboard
  sorting on all five tables (focus stays on the header), minutes unchanged after every sort, a mouse drag on a
  slider, a week of simulation with Next Opponent sorted, the staff room, the window switcher. No sideways page
  scrolling (0 px).

## Not checked
- Safari / Firefox (Chromium only). The stripes and sorted fill use plain CSS, nothing browser-specific.
- Player Development with real monthly changes (the save was only a week in; all changes were 0, so the change bars
  were empty). The playoffs' Minutes card (same code as the season card).
- The phone-sized layout (under 700 px), which the app does not really support.
- Other tables (roster, stats, contracts, draft board, ...) were not touched; they already follow the house style or
  are outside this task.

## Questions for you
1. **Icon set:** please look at `window_icon_sheet.png`. Any icons you want swapped (e.g. Next Opponent's crossed
   swords, Team Block's box, the coach whistle)? Colour per group, or would you prefer one colour for all?
2. **Development change bars** now use the same dark track as every other bar. With small changes the card reads
   quite dark. Keep it consistent, or keep that one light?
3. **Header arrows:** I added a small ▲/▼ next to the sorted header (the draft board only underlines). Keep, or match
   the draft board exactly?
4. **Headers are now 9 px bold** like the draft board (Player Development's were 13 px, Minutes' 11 px). OK?
5. Rating change's sort buttons read "Change · Season · Nov". Fine, or would you rather keep the "Rating change"
   wording (it is in the tooltip)?
