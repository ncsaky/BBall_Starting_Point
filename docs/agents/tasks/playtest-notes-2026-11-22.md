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
  this everywhere. Sweep done: any table without its own sorting now sorts on a header click (`interface.js`
  `enhanceAutoSort`): box score, conference standings, offseason and option decisions, roster cut-down, draft
  results, injury history, recent games. Year-by-year payroll and trade ledgers are left alone; Actions columns
  aren't clickable.
- **Slideshow text (done 2026-11-22).** The user wants less text: let graphics speak. Removed the "01 · kicker"
  line on every slide; each slide's footnote now sits right under the title as subtext. Power rankings subtext:
  "Change compares with each team's 2025-26 record finish." Card corners match the board windows (3px top).
  Continuity slide: the repeated source line and the "% kept · +N new / N had no NBA minutes" text are gone;
  just the bars (names are still in the hover tooltip). Its subtext no longer says "A new league…"; it reads
  "Last season's minutes, by whether the player is still on the team." The "Skip" button text is no longer underlined.
  Last season's leaders (was "…, revisited", no subtext): a 3 x 3 grid of points, rebounds, assists, steals, blocks,
  threes made, three-point % (3+ tries a game), free-throw % (2+ tries a game) and minutes. Each table: Player | number |
  Team, and a player who changed teams shows old logo → new logo. "View all" opens one sortable table of every
  qualifying player with all nine stats, sorted by that category (Back or Escape returns). Field-goal % isn't
  possible for the real 2025-26 season: the ESPN box scores have no field-goal attempts. Leaders (here and in the
  year-end recap) need 30 games, not the awards' 65. Category titles are bold and larger; View all is small grey
  text, no box. Player names (here and in the recap's leaders) open the player card: the slideshow steps aside and a
  "Back to Preseason Outlook" button returns to the same slide. The move arrow is drawn, so it centres on the logos.
  Tables shown together now line up exactly (fixed column widths, one row height): leaders grid (Player | Team |
  stat), power rankings' halves (notes clamp to two lines, full text on hover), standings, recap leaders.
  Your team slide (was "Your team at a glance"): title is the team name, no subtext. Full-width rotation table
  sorted by overall: headshot + name, Pos, Age, OVR, OFF, DEF, MIN, last season's PTS/REB/AST, Salary, Years.
  Headshots use the game's look (greyscale, a little contrast, crisp pixels, no grey box), flush left, and each row
  ends at the headshot's base. Round 2: header is the logo plus the team's overall and league rank (no
  spelled-out name); injured players join the table with a red "✚ games" marker; rows 31px with smaller headshots;
  strengths/weaknesses lists replaced by one curved radar (offense half blue, defense half orange, user's pick);
  the game's four-season payroll chart sits beside the payroll numbers. Round 3: header is just the logo and
  "1st in the league"; the table sits at its natural width (player column 270px fits the longest names) with the
  radar beside it; OVR/OFF/DEF use the roster's rating bar; contract is one field ("$40.8M × 5").
- **Team slides, round 4 (done 2026-11-22):** split in two so each part has room. "Your team": logo + "Projected
  1st in the league", the rotation table with colour-coded offense and defense role chips (`playerRoleChip` in
  app.js; the player's primary roles). "Team profile": logo + "Strengths and payroll", the large curved radar beside
  the payroll chart (player card proportions) and the cap numbers. Roles could also go on the main roster table.
- **Rating bars (done 2026-11-22):** every player OVR/OFF/DEF bar is one look: 36 x 5px on the house tables' dark
  track, fill and colour spread over 60-98 (`playerRatingBarStyle` in app.js) instead of 0-100, so a 77 and a 94
  differ at a glance (77 fills ~45% amber, 94 ~90% blue). Numbers unchanged. Skill and coach bars keep 0-100.
- **Game-wide rules (user, 2026-11-22):** a contract is always one field, salary × years (`contractLabel` in
  app.js; done for the slideshow, fantasy draft list, staff market). OVR/OFF/DEF always carry the roster's bar
  (`compactRatingBar`). Sweep done 2026-11-22: the only plain numbers left were the free-agent market's OFF/DEF
  (now bars, 60px like OVR); roster table, finder, trade ledger, roster blocks, cut-down, next opponent, playoff
  injuries and the fantasy list already had bars. Roster-block contracts now use "×". The segmented payroll chart keeps the player card's proportions
  (190 x 256, ratio 0.742) wherever it appears; the slideshow locks it with aspect-ratio. Check the Payroll
  window too.
- **Power-ranking notes (done 2026-11-22).** Rookies at rotation level (value 56.5+) are always named
  ("drafted Cameron Boozer"). Chosen by rating, not draft slot.
- **Tables, still open:** the user wants consistent row height and header centering across all tables. Not done
  yet: tables with headshots need taller rows, so decide per table type.
