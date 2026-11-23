# Taste deck round 2: what to build

Progress: 5/5 - done; committed; round 3 deck published

Source: the user's 22 round-2 answers (2026-11-23, deck ids `q2-…`), distilled into `docs/UI_STYLE_GUIDE.md`. This file turns them into work batches. Each batch is display work unless it says otherwise.

## Batch 1: polish and bugs (small, many windows)
- Checkboxes and clicked rows are never black (white box, dark tick; light tint for a selected row). Minutes window and trade room first, then sweep.
- Board background: slate blue with a faint grid by default; warm charcoal and cream paper as a theme setting.
- Headshots in soft colour (instead of greyscale), everywhere.
- Injured players: today's rating with the drop as a small red subtext; tidy the spacing.
- Minutes window: roles get their own column as coloured text (not under the name); the rest mark becomes a small superscript on minutes or fatigue; "coach rests players" moves to the window header beside Reset, and both look like content buttons; neater fatigue and minutes bars.
- Development: the sorted Change column stops a few pixels short of the right edge; replace the circular runway gauge.
- Next Opponent: double border on the sorted column; gaps under the header line and under the last row; spacing between the coloured numbers and their labels in the banner.
- Set The Roster: broken horizontal borders between cells.
- Four Factors: add a small legend; drop the white outline on the dots.
- Team Identity: smaller maximum hexagon size.
- MVP race (and other awards): smaller headshot, centred, name centred below; give the trophy photo a treatment (outline or frame).
- Your Team slide: clicking anywhere in a player box opens his card.
- Team Profile slide: payroll notes become a small 5 × 2 table; radar shapes must be able to overlap (or two radars).
- Contracts: default sort by this season's salary; a changed salary (after an extension) in a different text colour.
- Missing pictures: real players without an NBA photo (Andrew Holifield, Thunder) need a fallback (college photo, then a generated face). Same for any team or college without a logo.

## Batch 2: flow (what to press next)
- Offseason steps move into one toolbar chip that opens a list, next to the date and phase.
- When the roster is set (or any phase's work is done), show one clear "move on" button and hide the sim buttons that don't apply.

## Batch 3: trade room, second redo
- Two views: (1) pick assets from one team at a time, the list expandable and filling the window; (2) the deal review: payroll as the four-year segmented chart with the trade's change animated (plays once, replay button), value per player shown visually and first, the answer dial next to the Ask button, final-offer checkbox kept.
- Cut "Build a deal, then ask". Keep the simple payroll line ("takes $10M too much back").
- Freed space can hold one more useful graph later.

## Batch 4: opening roster window
- Far less text; contracts in the standard "$X × N" form; keep the release / buyout / waive buttons; less scrolling.
- Bug: something overlaps the footer in the bottom-left corner.
- Two-way contracts: make them clear, and check whether the user can offer one at all (the user can't find a way). Offering two-way deals may be new game work, not just display.

## Batch 5: basketball notes (engine and data, not display)
- Thunder play three centres (Jaylin Williams alongside Holmgren and Hartenstein) in the coach's rotation. Check Jaylin Williams's ratings against evidence and the coach's positional balance; Wallace, Mitchell or Caruso would normally take those minutes. Ratings-first rule applies: fix the coach logic unless the rating evidence is wrong on its own.
- Kristaps Porziņģis: out with an illness, no timeline, possible retirement (user, 2026-11-23). Needs an open-ended absence in the 2026 starting data.

## Later ideas from the references
- Taylor Wyman–style stacked-dot distribution columns (league by season, one player tracked with a dotted line) for a skill on the player card or league pages.
- Shot chart redone like his: zones shaded against league average, hexagons sized by attempts, labelled zone boxes, legend, zone table.
- Big-news cards in the Shams/ESPN style (large photo, bold banner) for trades, signings and major injuries in the league wire.
- JFresh-style player card: frosted glass over a blurred team-tinted background.

## Resume state
- Batch 1 done 2026-11-23 (display only, plus one save-load display step):
  - checkboxes white with a dark tick game-wide; table bar tracks transparent (no near-black tracks);
  - board theme: slate default, charcoal and cream in Settings > Board background (localStorage `nbaGmBoardTheme`);
  - headshots soft colour (`saturate(.45) contrast(1.05)`) everywhere a face shows;
  - Minutes: Player | OVR | Roles | Pos | Height | Minutes | Fatigue; tools bar (coach rests, Reset all minutes) above the table; zZ as a superscript on the minutes number; thin slider and fatigue bar; Reset removed from the title bar;
  - today's OVR with the rust drop in red (Minutes, Next Opponent): `playerOverallToday`, `overallTodayMarkup`;
  - Contracts default sort = this season's salary; new-deal salaries in purple (`asset-contract-new-deal`, >9% jump/drop);
  - Next Opponent: no table padding, no doubled bottom line, banner ranks spaced (number + small label);
  - Development: Outlook bar replaces the ring; sorted fill reaches the edge for first/last columns (house-table.js);
  - Set The Roster: tables edge to edge, one light row rule;
  - Four Factors: legend row, dot without white ring; Team Identity hexes max 0.55 of a cell;
  - award leaders: smaller centred headshot, centred name and team, trophy in a gold-ring medallion;
  - Your Team slide: whole tile opens the card; Team Profile: two radars (offense, defense) and a 5 × 2 payroll table;
  - every player without an NBA photo gets a college photo or a library face at save load (`faces.stage_player_headshots`).
- Not done in batch 1: selected-tab style (user undecided).
- Batch 2 done 2026-11-23: the top bar's phase label is a chip in offseason phases ("Preseason · Set The Roster · Step 4 of 4", red badge = decisions waiting) that opens the four steps with dates (`offseasonStepsChip`); the summer checklist no longer repeats them. Preseason replaces the Sim menu with one blue button: "Finish Set The Roster (N left)" while decisions wait, else "Start The Season (date)" (`preseasonPhaseCommands`). Summer phases already had their own single buttons. Not checked live in summer (save is in preseason).
- Batch 3 done 2026-11-23 (display only): the builder has two views. Picking (`state.tradeView = "pick"`): one team's asset list fills the window, a strip on top shows what each side gives (click a side to switch lists), "Review deal ›". Deal: the sides as tiles (value first as a bar on a 0–120 scale, coloured whole-number OVR, "$X × N"; roles in hover text), one payroll line per side (no tax gauge bars), the four-year payroll chart per team animated now → after (leaving players dashed red, arrivals outlined blue; plays once, Replay), Value and Team identity tabs; the answer dial and Ask together in the right column; no "Build a deal, then ask" text. Not checked: Ask/counter states live (not pressed, to keep the save clean).
- Batch 4 done 2026-11-23: the opening roster window has one short line instead of a paragraph and a compact counter (standard and two-way). Each player shows OVR, roles as coloured text, "$X × N", the guarantee in one word, and what releasing him costs (faded until you pick Waive or Buy out). Keep / Waive / Buy out buttons kept. Two-way places are a small table, and open places list the six best free agents eligible right now with a "Sign two-way" button (new `two_way_candidates_view` in the roster payload, the engine's own eligibility and the AI's preference order; about 0.01 s). Fixed the headshots that stacked over the window's bottom-left corner (`.cutdown-player { position: relative }`). The Sign button was not pressed live (all three places are full in the playtest save); the candidate list was checked on a copy of the save.
- Batch 5 done 2026-11-23 (engine and data):
  - Thunder starting three centres: the coach's slot score gave a 6'9" centre the small-forward height bonus and no penalty, so Jaylin Williams started at the 3 beside Holmgren and Hartenstein. A pure centre now scores −40 in slots 1–3 (`save.starting_slot_score`; soft, so an all-big roster still fields five). League check on the playtest save: only OKC's auto five changes (Wallace replaces Jaylin Williams); no other team had a pure centre on the perimeter. Jaylin Williams's rating (OVR 80, near Caruso 81 and Wallace 78) was left alone: the defect was the coach logic, not the rating. Minutes were not changed (the user's own team; he sets them).
  - Porziņģis: added to the real 2026-27 opening-night list (`data/canonical/opening_night_injuries_2026_27.json`) as an illness, out for the season, sourced to the user's report (the official report said "Not With Team", which the list never applies). New careers only; existing saves keep him healthy (old saves don't matter). He stays on GSW's books.
  - Scorecards: not rerun. The change touches one team's starters and one player's opening-day availability in new careers; the betting test replays real minutes, so it should not move. Worth a short odds run at the next engine checkpoint.
