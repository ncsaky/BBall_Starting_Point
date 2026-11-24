# Taste deck round 10 pass

Progress: 8/8 - done (round 10 pass committed)

Objective: build the user's round 10 answers (deck https://claude.ai/artifact/LtYd2d15GoXznsLcucoy2k, cards `q10-...`).
Boundaries: GUI files (`src/nba_gm_data/gui/`), GUI tests, `app_actions.py` only if a view needs data. Test on the gui-preview copy.

## What the user said (2026-11-24)
1. Player card overview (-1): the game score chart's proportions are absurd; let the heat maps be the main display of
   that page. Contract and roles in the header don't match the header's style; the header still has blank space.
2. Ratings (+2): great apart from the header (same header fix).
3. Long pills (+2): perfect, the model for every long pill.
4. Trade deal (0): Replay as a text button; drop the draft terms bar, instead a pop-up to add conditions to a pick when it is
   picked from the asset list; the Builder / Finder / Market band must sit at the same inset from the card edge as the two
   sections below it.
5. Team identity (0): before and after for offense and defense stacked one over the other; the three-team choice as
   clickable logos, not pills.
6. Value tab (+1): always logo plus abbreviation; swap picks need a wider cell and vertical centring, arrow on top of the
   swap; the value bars are too close together in scale.
7. Opening roster (0): the header scrolls with the table (not stuck); header cells reach the card edges; a better two-way
   divider (centred, bold); released players' money as contracts ($9M x 4), not totals.
8. Board roster (+1): header cells reach each end of the card.
9. Picking list (+2): no notes. Next card: no answer.

## Resume state
- Done 2026-11-24 (GUI only; JS 344/344; checked at 1650 x 930 on the test copies with real clicks):
  - Player card header: contract and roles as label / value rows in the same font, colours and row spacing as the
    OVR / OFF / DEF rows; the rating bars stretch so the header fills its width. Overview page: season line plus the
    heat maps only (recent games, the game-score chart and the payroll share left the page).
  - Board tables: the header's under-line now runs to the card edges too (the edge pieces had lost it).
  - Opening roster: header scrolls with the rows; the two-way divider is a centred bold band; released players' money
    in contract form ("Dean Wade $9.0M x 4 owed to released players").
  - Trade room: the Draft Terms bar is gone; adding a pick opens a "Conditions for <pick>" pop-up (Add protection,
    Add a swap right, Done), and each editable pick in the deal has a link (its condition, or "Add conditions") that
    reopens it. Replay is a text link. The Builder / Finder / Market band sits at the same inset as the sections below.
  - Team identity: the team choice is a row of logos; before stacked over after (offense and defense columns); team
    logos, inferred minutes and the note in a left column so nothing scrolls.
  - Value tab: logo + abbreviation for teams and pick logos beside pick names; single assets scaled to the largest
    single asset (team totals on their own scale), full-width bars when nothing subtracts value.
  - Swap / connected picks: a wider face column (54px) with the swap arrow above the logos, centred in the row.
