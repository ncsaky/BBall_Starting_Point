# Taste deck round 5 pass

Progress: 6/6 - done (round 5 pass committed)

Owner: Claude. GUI only. UI-light testing (game check, contrast script, JS tests).

## The user's round 5 notes (ids `q5-…`)
- Keep only the clear glass (drop Frosted). Font default: Helvetica Neue.
- Buttons: pill-shaped, like iOS glass buttons, everywhere (tools bars, Keep/Waive/Buy out, slideshow nav, trade room).
  Tab pickers too (trade room Builder/Finder/Market, All/Players/Picks/Swaps, Value/Team identity; Development's
  This season / Next 3 seasons). Team Identity's segmented buttons are loved: use that style.
- Checkboxes: transparent fill, not white.
- The window gradient feels "too AI": flat tinted glass.
- Injured players: the name is red everywhere (not just the cross).
- Player card ratings (+2, "take this style to the rest of the game"): layer subtitles become hover info; group
  headers (Shooting, Rebounding…) more distinct (italic or similar); Physical Tools bars must line up (same length).
- Trade deal: headers over the tile list (OVR etc.), a salary total in each side's footer, left of the status.
- Trade picking list: checkbox fill; pick rows have no "Pick" position and no empty dashes, the pick's notes
  (protection, swap) run across the rest of the row.
- Depth chart (+2): only the slideshow's bottom buttons.
- Team Profile (+2): the payroll chart fills its panel (keeping its shape).
- Development: Season and Month bars on one scale; range bands darker still; the player picker pills look messy;
  the view buttons unpolished; drop the "Projected overall…" text (hover info at most).
- Four Factors: still cut off.
- Team Identity (+2): more colour steps (brighter and darker, middle not washed out); a tiny two-line label per region
  with two numbers.
- Minutes: fatigue meter centred under its header and wider; colour light yellow → dark red as it fills; room for
  the injury mark and names (wider card); tools bar buttons vertically centred.
- Next Opponent: the header lines are still wrong. Rebuild the header from the ground up.
- Opening roster (+2): with Details open, "Two-way places 3 / 3" stays above the text; the text has no black box;
  roles side by side.
- Roster: headers look like buttons; make them like Minutes' headers.
- Not now: taller rows (leave), what next (keep working on these cards), spacing (user testing).

## Resume state
- Done 2026-11-24 (all in GUI; tests JS 345/345; contrast sweep of all 27 windows clean):
  - One look: Settings > Glass gone (clear always); font default Helvetica Neue.
  - Flat glass (no window, title bar or pop-up gradients); pill glass buttons game-wide incl. the top bar; segmented
    tabs (trade Builder/Finder/Market, All/Players/Picks/Swaps, Value/Team identity, Development views); transparent
    checkboxes with a white tick; table header buttons plain (Roster, Stats, Contracts); injured names red.
  - Next Opponent rebuilt: the grid's 15px first row made the 20px header overlap the first player row; three extra
    line layers (head ::after, first row ::before, a separate sort band) removed; one border under the header.
  - Minutes: wider name and OVR columns, wider centred fatigue meter, yellow → orange → dark red; min width 740.
  - Four Factors: min width 360, 12% taller, glass boxes, visible median.
  - Player card ratings: layer explanations behind an "i" mark, footnotes gone, italic small-caps group headers,
    Physical Tools bars one length.
  - Trade room: tile list headers, "Sends $X" in each side's footer, pick rows with notes across the row, selected
    rows tinted on the row (not white cells), strip buttons as pills.
  - Team Profile payroll chart fills its panel at 190 × 256.
  - Development: one scale for Season and Month bars, darker bands, legend-style player picker, "i" for the note.
  - Team Identity: seven colour steps a side computed for the dark court, two-line region labels (FG vs league,
    share of shots).
  - Opening roster: roles side by side, two-way Details text on its own line with no box, Rules as a glass pop-out.
- Testing now runs on a separate copy: `gui-preview` (port 8765) with saves copied into the scratchpad `gui_saves/`;
  the user plays the real playtest save in the main tab, so never drive that tab.

