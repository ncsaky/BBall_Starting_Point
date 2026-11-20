# Season slideshows: outlines for approval (B01, B02, B03)

_Draft written 2026-11-19 by Claude (coordinator), for the user's approval before building. Every slide below uses data the game already has, or says exactly what has to be saved first._

## How they appear
- **Year-end recap:** opens once when the playoffs end (the champion screen leads into it), before the draft lottery. Dates in the game: Finals end by Jun 21, lottery Jun 22.
- **Preseason outlook:** opens once at the start of the new season (Oct 1, "preseason"), right after the offseason rollover.
- Both are presented by your assistant GM, using the existing page-arrow style from player cards and box scores: ‹ › arrows, "3 / 9", keyboard arrows, Esc to close. They can be reopened from a menu, and every slide can be skipped. With reduced motion turned on there are no animations.
- **One build fix is needed first:** today awards are only created at the Sep 30 rollover, after the draft. The recap needs them at the end of the playoffs, so award generation moves to playoff end. It already refuses to run twice, so this is safe.

## B01: Year-end recap (about 9 slides)
1. **Champion.** Champion, Finals result, Finals MVP. A Finals MVP doesn't exist yet: either add it (the best player on the champion by playoff game score) or skip this item. Decision 1.
2. **Final standings.** Both conferences, seeds, play-in results, your team highlighted.
3. **Awards.** MVP, DPOY, Rookie of the Year with stat lines. Only these three exist today. Decision 2 asks whether to add Sixth Man, Most Improved, Coach of the Year and All-NBA teams.
4. **League leaders.** Points, rebounds, assists, steals, blocks, three-pointers and screen assists, top 5 each, using the 65-game rule for qualifying, the same as the awards.
5. **Your season.** Record, seed, how far you went, team stats against league rank, and the team MVP. Team MVP is chosen as the player with the best on-court value × minutes on your team, with a sentence of why.
6. **Biggest trade of the year.** Chosen by the size of the value swing on both sides (the trade logs store each team's evaluation), with a tie-break for star involvement. Shows each team's reasons in plain words, plus a short "how it played out" line: the players' stats after the trade.
7. **Biggest coaching change.** The highest-importance hire or firing of the year (these are already logged with importance scores), with the new coach's grade and "ride the stars" style.
8. **Top upcoming free agents.** Top 10 players with expiring contracts, worked out the same way the re-signing step does, ranked by the AI's market value. Shows age, position and whether their team holds rights.
9. **Looking ahead.** Your lottery odds or draft position, the top 5 consensus prospects, and your cap position for the summer.

**What must be saved** (it's all live until the rollover): the recap is built at playoff end and stored in the season-history record, so it can be reopened later. One fix: player stats aren't split by team for traded players. The leaders slide uses season totals, which is fine; per-team splits are only needed for B03.

## B02: Preseason outlook (about 7 slides)
1. **Power rankings.** All 30 teams, ranked by the game's own team strength (Team Signals' overall: a minutes-weighted top-8 plus depth). Shows each team's change from last season's finish and a one-line note, e.g. "Added Lauri Markkanen", "Lost two starters".
2. **Continuity** (the B03 graphic, below).
3. **Last season's leaders, revisited.** Where last year's scoring, rebounding and assists leaders and award winners play now, with their age and expected role.
4. **Your team at a glance.** Your projected rotation and minutes, team strengths and weaknesses (from Team Signals), and your cap position against the tax and aprons, including the new tax-payout share.
5. **Contracts to watch.** Your extension-eligible players before the Jan 15 deadline, and the league's biggest expiring deals (next summer's free agents).
6. **Prospect watch.** The consensus top 10 for the coming draft, your scouts' board, and how much you've scouted each, plus where your own pick projects.
7. **Storylines.** Three or four short items picked by rule: biggest offseason move, a star on a new team, a rebuilding team with the most young talent, a coach on the hot seat (a losing record plus an owner-pressure signal, if the front-office data has one).

Optional slides to choose from (decision 3):
- training-camp battles (the closest rotation spots on your team);
- injury report heading in;
- schedule notes (toughest stretch, back-to-back count).

## B03: Minutes-weighted continuity graphic
- **What it shows:** for each team, a horizontal bar of last season's minutes, split into **green** (players still on the team) and **red** (players who left). A thin grey segment marks players who were on the team but are injured or out for the season. New arrivals appear as a separate light tick beside the bar, so you see "kept 78% of last year's minutes, added two rotation players".
- **Sorted by continuity,** highest first, with your team highlighted. Hovering a bar lists the names.
- **Counting rules:**
  - Last season's minutes are counted **per team stint**: a player traded mid-season counts for each team by the minutes he played there. This needs the game logs, which exist for the current and previous season, so it works at the start of every new season.
  - Ownership is checked at the moment the outlook opens (Oct 1).
- **Honest edge cases:**
  - In a brand-new save there is no simulated last season, so the graphic uses the real 2025-26 minutes and says so.
  - Rookies have no prior minutes; they appear only as new arrivals.
  - Two-way and released players count by where they played.

## Decisions for you
1. Add a Finals MVP? (Recommended: yes, it's small.)
2. Add more awards: Sixth Man, Most Improved, Coach of the Year, All-NBA? (Recommended: Sixth Man, Most Improved and All-NBA now; Coach of the Year once coaches have more history.)
3. Which optional preseason slides (camp battles, injury report, schedule notes), if any?
4. Anything to add or drop from either outline?
