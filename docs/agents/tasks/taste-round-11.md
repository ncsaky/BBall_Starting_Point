# Taste deck round 11 pass

Progress: 8/8 - done (round 11 pass committed)

Objective: build the user's round 11 answers (cards `q11-...`). GUI only; test on the gui-preview copy.

## What the user said (2026-11-24)
1. Card header (+1 / 0): right idea and font at last. Contract as "$40.8M × 5" (no "seasons", no "through"); labels
   "Offensive role" / "Defensive role"; the space between the rating bars and the facts still looks off.
2. Roster (-2): the header cells must reach the card edges while the rows stay indented; my last fix did not do it.
3. Opening roster (+2).
4. Conditions pop-up (0): button spacing broken (in the deck); the remove X white; the card more see-through.
5. Deal (+1): space under the payroll box inside its card; payroll box more see-through; swap icons: no arrows, just
   the two (or three) logos centred.
6. Team identity (0): the other team's abbreviation is black (washes out); keep overall team offense / defense only.
7. Value (+1): "OKC sends" + logo, no "valued by"; swap arrows as above.
8. Next: the board background should be the team's main colour plus a vignette (check JFresh again); home-page cards
   not see-through enough; Trade Finder's segmented contract bar has broken proportions (follow the four-year cap
   chart) and some boxes / text overlap.

## Resume state
- Done 2026-11-24 (GUI only; JS 344/344; checked at 1650 x 930 on the test copy):
  - Board table headers: the edge pieces were clipped by the header cells' hidden overflow; the first and last header
    cells now show them (checked with a red marker: both edges painted). The earlier fix had never been visible.
  - Card header: contract "$40.8M × 5"; "Offensive role" / "Defensive role"; headshot, name, bars (360-560px) and the
    facts spread with even gaps across the header.
  - Trade room: conditions pop-up more see-through (.58), white X in a ring, even button row; payroll box more
    see-through with 10px under it inside its card; swap / connected picks show only their logos, centred; Team
    identity labels always light (unselected logo at .62); Value headings "OKC sends" + logo (who values it in the
    hover); no conditions link in the Finder.
  - Board: the user's team colour (58% mixed toward near-black) with a dark edge vignette and the faint grid; window
    glass .14. Small red rating drops lightened for contrast on the blue.
  - Trade Finder: the strip of flat bars replaced by the deal's four-season payroll chart (same proportions and scale)
    beside its now / after table; "Found trades" no longer squeezed into a 34px box.
