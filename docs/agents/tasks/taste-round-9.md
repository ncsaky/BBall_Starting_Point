# Taste deck round 9 pass

Progress: 8/8 - done (round 9 pass committed)

Owner: Claude. GUI only. UI-light testing (gui-preview copy, real screenshots, contrast script, JS tests).

## The user's round 9 notes (ids `q9-…`)
- Glass amount right (+2). Gallery fine. Settings (+2) but the chosen pill should slide on every click.
- Player card overview (-1, "a downgrade in polish"): Recent Games panel runs past its last row; Offense / Defense
  labels too small; pill options not split evenly / not centred; add "Overall" offensive impact to the offense heat
  map; larger legend; header: team logo (no name) ~60% of the headshot, as a badge at the headshot's lower corner;
  drop Size (it's in the subtext); show contract and roles more clearly.
- Ratings (+1): Tendencies' mix bars wider, fill the page with less blank space.
- Trade list: pick logos aligned with the headshots; the Builder / Finder / Market band indented like the sections
  below it and its controls vertically centred.
- Deal / Value: the lower tab pill pokes past the card's top corners (make it the card's top); "Add or change
  players" more prominent, in the top bar on the right next to Add a team; the room much more transparent.
- Opening roster: two-way Release as a text link (underline on hover, no box); Guaranteed empty for two-way places;
  no Clear button; Apply becomes "Set roster" when there are no changes.

## Resume state
- Done 2026-11-24 (GUI plus one app_actions fix; JS 345/345; focused Python 22; checked at 1650 x 930 with real
  screenshots and real clicks):
  - Board flat (user, mid-pass: the team-colour glow "looks AI"; JFresh uses a flat background): grid only; no glow
    on pop-ups or slides either.
  - Player card overview: team logo badge on the headshot's corner (60%); contract (salary, seasons, through when)
    and roles by side in the header, Size and team name gone; Recent Games ends at its last row; larger Offense /
    Defense labels and key; Overall offense view for players (his shooting plus his lift on teammates).
  - Long pills: equal options with centred labels everywhere; the slide also works for two pills with the same
    labels (Off / On).
  - Ratings: Tendencies as Choices and style plus a two-column Mixes block (no blank third column).
  - Trade room: top band indented and centred; "Add or change players" a blue pill in the top band beside Add a team;
    pick logos start where the headshots start; the lower tab pill inset in its card; Value tab blocks share the
    width (the second team's rows overlapped); the room more see-through (.26).
  - Opening roster: two-way actions as text links; Guaranteed empty for two-ways (games used in the row's hover);
    no Clear; one button: Apply N moves, Set roster, or a greyed Roster set.
  - Bug fixed: a player back from injury with no rust left but a minutes limit (Hartenstein, Topić) made his player
    card fail ("rust_penalty"), which also broke the trade room's Team identity tab.
- Round 10 deck published 2026-11-24 (version 13, 10 questions `q10-…`): flat board, card overview, ratings, even pills, deal band, picking list, Value, Team identity, opening roster, which card next.
