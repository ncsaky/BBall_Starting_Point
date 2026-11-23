# Playtest notes (started 2026-11-22)

Running list of what the user flags while playing. Screens and layout first, then game experience.
Game runs from the browser pane: launch entry `game` (port 8766, normal `saves/` folder).

## Game experience

- **Spurs auto starting five (coach logic, not ratings).** The coach now starts Castle, Vassell, Champagnie,
  Wembanyama at power forward and Kornet at center, with Fox and Harper on the bench. The user finds Wemby at
  power forward and two true centers "weird, not atrocious". They'd expect the best players to start: Fox, Castle,
  Harper and Wembanyama at center, plus Champagnie or Vassell, while noting that three-guard lineups have spacing
  problems around Wemby. The cause: slot scores in `save.py` `starting_slot_score` / `auto_starting_five`. Fox is
  listed only as a point guard, so he scores low at shooting guard, and Castle won the point-guard spot by 0.2.
  Possible fix later: make the starting five favour the best players first, then fit spots. Don't sit two
  playmakers who are among the team's best. Low priority; the user said "I don't hate it".

## Screens and layout

- **Tables, round 1 (done 2026-11-22, `gui/table-style.css`).** Light bar on the left of a row on hover, in every
  table: removed (the source was an invisible left border on all rows in `styles.css`). Power rankings sorted by
  Overall showed no shading in that column: fixed for every table (the old shading was a box shadow, and the
  interface turns all shadows off). Gap between the header and the first row: now two flush bars, the header's
  darker. Header text bold, one size and colour, no capitals. Values in the sorted column bold.
- **Sortable headers (done 2026-11-22).** Every season slideshow table (preseason outlook, year-end recap) sorts
  by any header on click; click again to flip. Power rankings' two halves sort as one list of 30. The user expects
  this everywhere. Other tables that still can't sort need a sweep.
- **Slideshow text (done 2026-11-22).** The user wants less text: let graphics speak. Removed the "01 · kicker"
  line on every slide; each slide's footnote now sits right under the title as subtext. Power rankings subtext:
  "Change compares with each team's 2025-26 record finish." Card corners match the board windows (3px top).
- **Power-ranking notes (done 2026-11-22).** Rookies at rotation level (value 56.5+) are always named
  ("drafted Cameron Boozer"). Chosen by rating, not draft slot.
- **Tables, still open:** the user wants consistent row height and header centering across all tables. Not done
  yet: tables with headshots need taller rows, so decide per table type.
