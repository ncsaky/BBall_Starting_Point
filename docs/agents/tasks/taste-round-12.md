# Taste deck round 12 pass

Progress: 9/9 - done (round 12 pass committed)

Objective: build the user's round 12 answers (`q12-...`; the deck frames were taken before the JFresh merge). GUI only.

## What the user said (2026-11-24)
1. Board (+2, "freaking beautiful"): clean up the pin / minimise / close buttons, JFresh style.
2. Card header (+1): headshot and name close together, the rest spread evenly; the role value coloured by its role;
   the heat-map captions centred under the courts; the season strip's borders (a top line through the vertical lines,
   a line on the last column's right, lines cutting into the season drop-down) look unpolished.
3. Conditions pop-up (+2).
4. Deal (+1) and Value (+1): keep the pick marks (the * for conditions, the mini owner logo) but without white bubbles;
   room for two or three logos; "OKC sends" headings more prominent.
5. Team identity (+1): the partner drop-down showed empty; the verdict dial's marker should be dark; drop the
   "Illustrative minutes..." note; before / after heat maps barely differ.
6. Trade Finder (+1): "OKC payroll" title centred over the chart with the team logo; table under the chart; centred;
   only the shopped players coloured (marked, e.g. red outline with hatching), the rest of the payroll quiet.
7. Next: the Finder's and the top bar's drop-down buttons (Shop my assets, All 29 teams, Sim to...) don't match the
   other buttons; animate the menus dropping down.

## Resume state
- Done 2026-11-24 (GUI only, all in `jfresh.css` plus three app.js touches; JS 344/344; contrast clean on the card):
  - Window controls: plain white glyphs (no boxes), faint round lift on hover.
  - Card header: headshot + name together, bars centred between the name and the facts; role values in their role
    colours; season line with no vertical or outer lines, one hairline under the bold labels; captions centred.
  - Pick marks: the condition * an amber glyph and the owner logo bare (no white bubbles); the face column 72px (66 in
    three-team deals) and the mark's box fits its logos, so two logos sit centred.
  - Value: "OKC sends" a 16px heading with a 26px logo and a hairline under it. Verdict dial marker and needle dark.
  - Team identity: the note moved into the projection label's hover. The partner drop-down shows "ATL Atlanta Hawks"
    in the game (empty only in the deck capture). Before / after heat maps barely differing is the projection itself
    (a two-player trade changes a 240-minute rotation a little); not changed.
  - Finder payroll: title centred with the team logo; chart then table, centred; only the shopped players coloured,
    with a red outline and hatching (green for targets); the rest grey.
  - Menus and drop-down lists: one frosted panel, plain rows, faint shortcut hints, an .18s drop-in animation;
    drop-down buttons match the frosted chips.
- Round 13 deck published 2026-11-24 (version 16, 9 questions `q13-…`): first deck in the JFresh look; adds a Sim menu frame (`menu_sim`).
