# Taste deck round 8 pass

Progress: 10/10 - done (round 8 pass committed)

Owner: Claude. GUI only. UI-light testing (gui-preview copy, real clicks where it matters, contrast script, JS tests).

## The user's round 8 notes (ids `q8-…`)
- Roster (+2). Card gallery: "totally broken, feels like a flashbang" (bright, unstyled).
- Long pills (Settings, player card): the unchosen options show their own pill shapes; they shouldn't.
- Player card ratings: larger still (fewer two-line ratings, groups not split across columns, passing range bars as
  long as the rest); drop injury risk, decline watch and trade value from the header, and fill the header well.
- Trade picking list (+2): pick logos without white backgrounds, larger, more room, vertically centred; Player/asset
  header left-aligned; scrolling is fine for this list (pages not needed).
- Deal: Details doesn't open visibly; a wrapped green number misaligns the two payroll charts.
- Three teams (-1): nothing may overlap whatever the assets; the room can be larger.
- Value/deal: no overlapping text columns; team picker and arrows clear of the logo; Add a team / Add centred with the
  tab pill; the gauge needle black (it's white on white).
- Opening roster: no strike-through on a waived name; two-way places show their cost to release.

## Steps
1. Read. 2. Distil. 3. Gallery dark glass. 4. Long pills clean. 5. Trade picking list. 6. Deal (Details, payroll
captions, three teams, room size, header controls, needle). 7. Player card. 8. Opening roster. 9. Check. 10. Commit.

## Resume state
- Done 2026-11-24 (GUI; JS 345/345; contrast and light-surface sweep clean on all 27 windows, Settings, the player
  card, the trade picking list and a three-team deal's three tabs; checked at 1650 x 930 with real screenshots):
  - Much more see-through glass (user, mid-pass: "go back to the JFresh reference"): windows .20, title bars .12,
    pop-ups and slides .30 (the full-screen trade room .44 so its coloured text keeps contrast), lighter header bands.
  - Card gallery in dark glass (preview drawings dimmed).
  - Long pills: unchosen options plain labels (they had the glass buttons' own blur).
  - Trade list: pick logos plain, larger, centred, at most two; "Player / asset" over the headshots; the list scrolls
    again (pages removed, as the user allowed); Add a team / Add on the pill's centre line.
  - Deal: Details lifted out of the clipping tiles (glass-select.js) so it shows; payroll captions on one line; the
    room uses the whole screen; pick logos and the partner logo no longer overlap; dial needle black.
  - Player card: header facts (team, contract, roles, size) replace injury risk, decline watch and trade value; card
    2100 x 1270 at 65%; Technique in four wide columns with whole groups, passing pairs in their own three-column band
    (bars as long as the rest); no page scrolls.
  - Opening roster: no strike-through on a waived name; two-way places show $0 to release (the engine leaves nothing
    on the books; games used moved to the Guaranteed column).
- Round 9 deck published 2026-11-24 (version 11, 12 questions `q9-…`): glass amount, gallery, clean pills, card header and ratings, trade list, Details, deal, three teams, Value, opening roster, which card next.
