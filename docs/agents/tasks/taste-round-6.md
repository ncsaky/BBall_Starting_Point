# Taste deck round 6 pass

Progress: 8/8 - done (round 6 pass committed)

Owner: Claude. GUI only. UI-light testing (game check on the gui-preview copy, contrast script, JS tests).

## The user's round 6 notes (ids `q6-…`)
- Button style: can't decide; make it a Settings choice (glass pill default, solid team-blue pill, rounded-square glass, segmented).
- Indent rule: window title → section header → table header text → row text, each further right. Tables keep a margin
  from the card sides (Roster now looks right). Applies to all tables.
- Opening roster: Keep / Release / Buy out as one long pill, the chosen one a filled pill that slides when changed.
- Roster: player names bold everywhere (consistency).
- Trade room: dislikes the segmented Builder/Finder/Market tabs; dropdowns look bad; checkbox (final offer) white;
  the X button; white rims around the top of window bars (many cards); no scrolling ever (pages/tabs or larger);
  pick details as a Details drop-down not hover; grey value bars; a needless border under the tile list header;
  must hold up with more than two assets; header hover turns the cell white; value numbers line up; injury-risk
  stick figure needs a redesign.
- Player card ratings: every bar needs its dot; never show "estimated" (no hollow dots, no "44 of 64 from player
  data" counts); no numbered headers; no "each bar adds to 100%" / "how often" captions.
- Your Team slide: red injured names game-wide (Minutes too).
- Team Profile: the arrow in the bubble not vertically centred; panel needs more height to show the bottoms.
- Team Identity: more colour steps than five.
- Next Opponent: a few px gap above the team sub-header row; the date / home row touches the card edge.
- Loved: Minutes, Development, Four Factors, Next Opponent overall, Your Team pills. Spacing: "we'll see later".

## Steps
1. Read answers. 2. Distil (style guide + this file). 3. Indent rule, title-bar rims, close button.
4. Button-style setting, sliding choice pill, Builder/Finder/Market tabs, dropdowns, checkboxes.
5. Trade room fixes. 6. Player card, Next Opponent, Identity, Team Profile, red names. 7. Check. 8. Commit.

## Resume state
- Done 2026-11-24 (GUI; JS 345/345; contrast and light-surface sweep clean on all 27 windows, the trade room's pick
  view and its three deal tabs, all 9 slides and a player card):
  - Indent rule: tables sit 10px in from the window sides, first-column text at 23px (title 13px); section rows
    ("Two-way places") at 15px. Roster 1160 and Minutes 760 minimum widths; opening roster 1040.
  - Windows: one faint edge, no white highlight line; the title bar is 28px in the window code too (`TITLE_HEIGHT`
    was 24, so content sat 4px under the bar on every window).
  - Pop-ups: glass X button, no frame around the trade room's title bar.
  - Settings > Buttons: glass pill (default), solid pill (team blue when chosen), rounded square, segmented.
  - Keep / Waive / Buy out: one long pill, the chosen option a filled pill that slides (red for releases).
  - Drop-downs: `gui/glass-select.js` swaps every select in windows, pop-ups and slides for a glass button and menu
    (long lists in columns, no scrolling); the real select keeps the value and events.
  - Trade room: Builder / Finder / Market as underlined tabs; asset list in pages (as many rows as fit, no
    scrolling); value bars red → yellow → green → blue (no grey); value numbers in one column; injury risk as a
    five-step meter; deal page without scrolling (tiles grow; Payroll is now a tab beside Value and Team identity;
    charts with their tables beside them; Value tab's team blocks side by side); pick terms as a field with a Details
    drop-down; no line under each side's header; old white buttons on the Team identity tab made glass.
  - Player card ratings: no numbering, no "N of M from player data", no captions beside group headers, no hollow
    "estimated" dots or hatched bars, no internal ids in tooltips, a dot on every bar.
  - Next Opponent sub-header padding; Team Identity key with 13 steps; Team Profile slide taller (920px max) so
    the radars and payroll table show to the bottom; slideshow arrows drawn as centred icons.
  - Names: bold in every table; red when injured everywhere (Minutes and the slides' depth chart included).
- Bugs found while testing, fixed: the opening roster's Keep / Waive / Buy out did nothing in preseason (only wired
  in the cut-down phase); its "Apply moves" handler (`confirmCutdownReleases`) was lost in the round 2 rewrite,
  which also broke the wiring after it (two-way buttons, Submit roster). Restored from the commit before.
- Not verified by eye: the pane was in the background, so screenshots were stale; checks were by measurement.
- Round 7 deck published 2026-11-24 (version 9, 15 questions `q7-…`): the indent rule, sliding pill, button-style
  default, trade room picking list / deal / pick Details / three-team deal / Value tab, definite ratings, Next
  Opponent spacing, Identity key, Team Profile room, red names, plus "where else do you scroll?" and "which card
  next?". Captured on the gui-preview copies (OKC Dec 25, PHI preseason).
