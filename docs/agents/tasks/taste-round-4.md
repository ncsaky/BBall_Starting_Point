# Taste deck round 4 pass

Progress: 7/7 - done (round 4 pass committed)

Owner: Claude (coordinator). GUI only, plus small display helpers in `app_actions.py` / `season_slides.py` if needed.
Testing: UI-light (check in the running game, contrast audit, `node --test tests/*.cjs`). No full Python suite.

## The user's round 4 notes (ids `q4-…` in the deck's `answers` collection)
- Glass strength: the lighter frame, more colour through. Six cards say the same thing: the tables and charts are a white
  table sitting on the glass; the content itself must be glass.
- Font: yes to a modern font, with a Settings choice to switch between options and see the change.
- Trade tiles: the side's total value needs a bar; with several assets, each gets its own colour and the total is a
  segmented bar of them.
- Trade payroll: proportions still off. Must keep the payroll chart's own proportions exactly; add the payroll table under it.
- Trade picking list: name column much narrower; value numbers line up in one column; OFF and DEF bold; bigger text and
  rows; names bold (picks are bold, names weren't).
- Your Team depth chart: entries line up (left aligned, not centred); headshots centred on the name; no subtext, use
  separate fields; "Starting five", not "Projected".
- Team Profile: more categories on the strength radars. Rated +1.
- MVP: beautiful, no notes (+2).
- Development graph: lower y-axis floor; darker range fill; a background grid.
- Four Factors: the card is too small and the graphics are cut off.
- Team Identity tabs: Offense / Defense labels above the three options, centred, so they don't look like an option.
- Minutes: header cell and row cells of Minutes not the same width (sorted fill misaligned on the right); fatigue not centred.
- Next Opponent: a 1px gap under the top of the sorted column's header; a 1px gap between the header line and the first
  row; the header line cuts into the header text.
- Opening roster: cost to release as "$23.1M × 3". Keep this table (great for contract management).
- Set The Roster: white space under the table (taller rows everywhere maybe later).
- Roster: gap between the table and the card's edge; roles truncated with "…".
- Player cards: range bars (middle half of the league, with his dot) for every rating, like the Four Factors ones.

## Steps
1. Glass content: content surfaces translucent and tinted (the glass shows through), lighter frame; contrast audit on
   every window, slide and pop-up. Keep the old light frosted look as a Settings option.
2. Font: Settings > Font (modern system sans default; Tahoma, Avenir Next, Helvetica Neue).
3. Table fixes: Next Opponent header gaps, Minutes alignment, Roster edge gap and truncation, Four Factors size.
4. Trade room: total value bar (segmented), payroll chart proportions plus table, picking list.
5. Slides and cards: depth chart fields, more radar categories, Development graph, Identity labels, release cost format.
6. Player card ratings page: range bars for every rating.
7. Check in the game, browser tests, report.

## Resume state
- Step 1 done: `gui/glass-clear.css` (Settings > Glass > Clear, default; `html[data-glass]`), JFresh-faithful: content straight
  on the glass, hairlines, one spacing system (corner 10/6px, 1px edge, 28px title bar, 10px padding). Blanket white-text
  rule with :is(#modalRoot) id weight; accents re-added in light tints; ratings light stops in `ratingInkColor` and the
  slideshow `RATING_STOPS_CLEAR`; trade room palette via `--tr-*`; courts dark (Taylor Wyman style); radars light.
  Checked by script (scratchpad `audit.js`: `__check()` = contrast + light surfaces + lost accents) on all 27 board
  windows, trade room (pick and deal), Settings, all 9 slides, player card: clean.
- Step 2 done: `gui/fonts.css` + Settings > Font (Modern SF Pro default, Rounded, Avenir Next, Helvetica Neue, Classic).
- Test helpers: scratchpad `setup.js` (`__load()`, `__open(pos)`, `__sweep(i)`, `__css(name)`, `__slides()`), served by
  `python3 -m http.server 8797` in the scratchpad; inject with a script tag.
- Noticed, not fixed: the Settings page behind the Settings pop-up is still the old light page; start screen "Enter Save"
  is grey on grey.
- Steps 3-6 done 2026-11-23:
  - Tables: house headers drawn with one border (the inset shadow cut the text), no 1px gap above the first row, no
    banner line above the sorted fill; sorted fill placed from the grid track so header and rows match (Minutes);
    Roster edge to edge, columns sized to content (roles never cut), wider default; Four Factors and Minutes wider;
    new layouts never open Roster, Minutes or Four Factors narrower than their tables (`CARD_MIN_DEFAULT_WIDTHS`).
  - Trade room: side totals as segmented bars (one colour per asset, shared scale); payroll chart drawn at its own
    190 × 256 shape and scaled evenly, with a Season | Now | After | Change table under it; picking list with a narrow
    name column, roles as coloured text, bold names and OFF/DEF, values in one column; deal tiles show full names;
    changes read "+$14.7M".
  - Slides: depth chart Player | OVR | Min | Pos per group, group labels centred, names left-aligned, "Starting five";
    Team Profile radars 8 + 8 (new identity metrics: ball handling, basketball IQ, steals, shot blocking,
    switchability, team defense; `OUTLOOK_FORMAT = 4`).
  - Development graph floor at 60 or lower, grid, darker band; light line colours on clear glass.
  - Team Identity: Offense / Defense labels above their tabs (identity window 7% taller).
  - Opening roster: cost to release "$X × N" from the engine's per-season charges.
  - Player card ratings: every rating a range bar (league min, middle half, median, position average, his dot by
    percentile, hollow when estimated); league spreads from `player_profile.league_reference` (`row["league"]`).
- Tests: JS 345/345; Python focused 56 (player_profile, season_slides, simulation_progress, overall_scale, spatial).
- Not done: Set The Roster white space (user unsure); the Settings page behind the Settings pop-up and the start screen
  are still the old light look.
