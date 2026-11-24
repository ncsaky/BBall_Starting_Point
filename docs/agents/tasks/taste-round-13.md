# Taste deck round 13 pass

Progress: 8/8 - done (round 13 pass committed; body-map image waits for the user)

Objective: the user's round 13 answers: 9 questions (`q13-...`) and about 40 notes on today's captures (`v13-...`).
First deck in the JFresh look; the user says we're "pretty much to the point of all good" on the asked cards.

## What the user said (2026-11-24)
Quick fixes
- Settings: hide scroll bars across the game; the close X a plain, slightly thicker X with no bubble.
- Player card: the Overall / Scoring / Playmaking and Overall / On-ball / Off-ball pills exactly as wide as their heat
  maps; delete the "Court Influence" label.
- Value tab (-2): headings centred, a space between the abbreviation and "sends", the abbreviation bold too.
- Team Wants: the + on the add button white. Payroll window: slightly fainter colours.
- Picking list: a single pick logo is slightly off-centre against the headshots.

Tables: "the modern treatment" everywhere (the Opening Roster is the model: "best table so far")
- Header cells (fill, hover, sorted fill) reach the card edges: Contracts, Development, Minutes, Next Opponent, Staff,
  Standings, Stats (sorted column fill to the left edge), Set The Roster.
- No pixel gap between the window's title bar line and the header (Standings, Staff); Roster: 1px at the bottom.
- Header hover / sort highlight fills the whole header cell (Contracts).
- Row hover must not overreach the borders and should reach the edges; a click anywhere on a player row opens the card
  (Set The Roster).
- Window-specific: Contracts wider (amounts truncated) and no risk / runway meters; Development fits every player;
  League Block value bar and the gap before Contract; Next Opponent's team banner is offset (several px left, 1px
  right); Morale "needs to be improved"; Team Signals bars and labels modernised; Draft Assets larger for many picks;
  DPOY trophy background ugly, the card wider for names; Upcoming Prospects: no pill around names, names / headshots /
  logos vertically centred, a longer scouted bar, a wider card, drop Potential, interquartile range with a legend and
  stronger contrast; Set The Roster payroll scale check.
Trade room
- Three teams: the asset lists need more room; the "to" destination drop-down not as subtext; no abbreviation-only
  labels; team drop-down shows "ATL Atlanta Hawks" (one is enough); a pill only on one team; maybe two dials.
Player card health (-1): the body figure's shape is off; the user suggests finding a body image online and segmenting
  it (needs the user's OK to download); body larger and centred, the table under it.
Slides: Power rankings table restyle (keep fields and animation); slide tables consistent with the game (pixel-level
  borders and spacing); Contracts bars softer; Prospect watch (-2) needs photos, logos, ranges, rank changes;
  Storylines (-1) and Stars on the sidelines (-1) more visual, text breaks out of its box.

## Resume state
- Done 2026-11-24 (JS 344/344; `tests.test_season_slides` 25 OK; checked on the OKC and PHI test copies):
  - Root cause of uneven table edges: card-board.js sizes a window's content to the window's outer width; the content
    now starts 1px left so both sides match (tables 10px from each edge). Header fill / sorted fill / row hover reach
    both edges (edge pieces and side shadows); grid tables' headers reach both edges; no gap above Standings' header.
  - Quick fixes: scroll bars hidden game-wide; pop-up close a plain heavier X; heat-map pills / keys / captions as wide
    as the drawn court (measured in wirePlayerCardPages); "Court Influence" removed; Value headings centred and bold;
    Team Wants + white; payroll colours softer; single pick logos centred on the headshots.
  - Contracts 600px wide, Risk / Runway as plain numbers. Prospects window 760px, no Potential column, plain names,
    centred rows, longer scouted bar, high-contrast range marks with a key. Awards 340px, bare trophy. Team Signals and
    Morale as attribute rows. League / Team Block: value right after the contract, number + thin bar. Draft Assets 760px.
  - Set The Roster: header labels 5px above the line, hover inside the lines, a click anywhere on a player row opens his
    card (offseason name buttons also open own players' cards: freeAgentPlayerCard falls back to dashboardPlayerCard).
  - Three-team deals: a "To" column (logo + abbreviation drop-down), roles hidden for room, partner picker unboxed and
    abbreviation-only. Two dials: not done (asked as an idea).
  - Slides: Prospect watch with photos, school logos, the league-board range and your scouts' difference (new data
    from `season_slides.consensus_top`); Storylines with team logo, player photos and a headline number (new data);
    Stars on the sidelines with logo and games-out number; slideshow backdrop lets the team colour through; contract
    bars softer. Slides are stored per save, so existing saves keep their old outlook until the next preseason.
  - Health page: figures centred and larger, table underneath. A real body image needs the user's OK to download.
