# Taste deck round 7 pass

Progress: 9/9 - done (round 7 pass committed)

Owner: Claude. GUI only. UI-light testing (gui-preview copy, contrast script, JS tests).

## The user's round 7 notes (ids `q7-…`)
- Loved: Your Team slide (+2), Team Profile (+2), Team Identity key (+2).
- Player card (scrolling answer): make the card wholesale larger, so the ratings page doesn't scroll. On the card: the
  court-view tab picker and the Offense / Defense labels are too small; the text under each heat map isn't centred
  under it; the season drop-down's border overlaps the season-stats separator line.
- Trade picking list (-1): checkboxes still read white; pick terms ("top-5 protected") centred in the row, under
  Roles; the Review deal button looks terrible; Builder / Finder / Market looked terrible (now the long pill).
- Trade deal: each side's header and footer line up across sides (rows line up); Details opens a small drop-down;
  pick terms and roles centred the same way, on one line with each other.
- Three-team deal: cramped and overlapping (the room may get larger); payroll tables under their charts again, not
  beside; "Add or change players" styled like "Add condition"; "Add condition" right next to "Draft Terms" (not far
  right); the verdict panel must not start above the other panels (the Add-or-change bar pushes it). Question: what
  happens when you add a team after three?
- Value tab: the bars are all grey (wants colour); each team's value total lined up at the bottom.

## Steps
1. Read. 2. Distil. 3. Trade room layout (bar, verdict top, headers/footers, three teams, payroll tables under).
4. Trade controls (checkboxes, Review deal, Add or change, Add condition, Details size, terms/roles centred).
5. Value tab colours and totals. 6. Player card larger, its tabs, labels, heat-map captions, season drop-down.
7. Check. 8. Commit. 9. Answer the four-team question.

## Resume state
- Done 2026-11-24 (GUI; JS 345/345; contrast sweep clean on all 27 windows, the three-team deal's three tabs and a
  player card; nothing scrolls):
  - Trade deal: "Add or change players" on its own line across the top (styled like Add condition), so the answer
    panel starts level with the sides; sides share subgrid rows (headers on one top line, payroll footers on one
    bottom line); three or more teams use narrower rows (no contract column, stacked roles, smaller pick logos),
    sides wrap only when out of room; payroll tables back under their charts (scale 1); Draft Terms' Add condition
    beside its label; Details a small drop-down; roles and pick terms centred in one column.
  - Picking list: pick terms centred under Roles; Review deal the solid blue pill; checkboxes a dark well, solid blue
    when checked.
  - Value tab: listed values in each asset's colour (no grey); team totals on one bottom line.
  - Adding a seventh team now says "A trade can include at most six teams" (it was silently ignored).
  - Player card: 1700 x 1080 at 76% (was 1530 x 900 at 70%); ratings page re-laid (Technique across the top in five
    columns; Physical, Coach and Tendencies (three columns) beneath) so no page scrolls; court tabs and Offense /
    Defense labels larger; heat-map captions centred; season drop-down a pill in a taller header.
