# Taste deck round 2: what to build

Progress: 0/5 - waiting for the user's go-ahead

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
- Guide written. No code changed yet. Board rows TASTE-R2-1 … 5 added as queued.
