# SEASON-ALMANAC: one full 2026-27 season, a review page, and what looks wrong

Progress: 6/6 - done

Owner: Claude (side session, worktree `season-almanac-a81b87`, branch `claude/season-almanac-a81b87`). Report only:
no game code or ratings were changed.

**Season in Review page (private):** https://claude.ai/artifact/FJTEFUnVqJArfVx9LXPW54

## TL;DR
- Cleveland won the title (59-23, 16-2 in the playoffs, Donovan Mitchell Finals MVP). Oklahoma City went 73-9 and lost
  the West final. Memphis jumped from 25 real wins to 48.
- Worst finds: a playoff team got the No. 4 pick; injury names and lengths don't match (an ACL tear cost Luka Dončić
  4 games); three-point shooting runs about 3 points low while two-point shooting runs high; the champions traded Evan
  Mobley on July 1 to save tax.
- This is one season from one random seed. Items marked **code-confirmed** are traced to the rule that causes them.

## The run
- Today's engine, new career, seed 20261126, run on Azure from this branch's code (base `21c499b6`), regular season
  through playoffs, lottery, draft, free agency, training camp and rollover. No crashes.
- Harness: `scripts/season_almanac_run.py` (the S2-MULTISEASON runner without the typed minutes plan, plus a copy of
  the save at each calendar step).
- **Brooklyn was the empty user chair.** No AI trades are made for it and its free agents walk, so nothing about the
  Nets is counted below.
- Results and page-building scripts: `output/almanac/` in this worktree (not in git).
- "Real" below means the 2025-26 box scores in `data/research/game_boxscores_2025_26.json`.
- The season audit's two "errors" (orphaned players, award list) are the old stale checks S2-MULTISEASON described.

## Oddities, worst first

### Rules that are plainly broken

**1. A playoff team got the No. 4 pick (code-confirmed).**
- What: the Lakers won the play-in for the 8th seed and played in the playoffs, yet sat in the lottery in slot 14 and
  jumped to pick 4. Orlando, knocked out in the play-in, was left out and picked 15th.
- Why wrong: the lottery is for teams that missed the playoffs.
- Where: the lottery takes the 14 teams with the fewest wins and never looks at who made the playoffs
  (`src/nba_gm_data/draft.py:829-838`; wins handed over by `save.py:9886` `save_standings_for_draft`).
- Also: the real 2027 draft uses the new 16-team "3-2-1" lottery approved in May 2026
  ([NBA announcement](https://pr.nba.com/nba-board-of-governors-approves-new-draft-lottery-system-to-address-tanking/)).
  The game still runs the old 14-team odds (`data/overrides/draft_model_config.json:31-36`).

**2. Injury names and lengths are unrelated (code-confirmed).**
- What: Dončić "ACL tear", 4 games. Keon Ellis "Achilles tendon rupture", 0 games. Jalen Williams "back contusion",
  144 games. Paul George "ankle (unspecified)", 179 games. Luke Kornet "shin contusion", 48. 11 of the 33 injuries of
  40+ games have minor-sounding names. 18 players are out into next season, including Gilgeous-Alexander (to Feb 2028).
- Why wrong: the first thing a fan reads is the name and the games missed.
- Where: `injury_model.py:199-220` draws a length from the body part's curve, then a name from a broad length bucket.
  The recovery data holds a few ruptures with 1-3 day absences (probably absences cut short by a season's end), and the
  curve's top 2.5% stretches evenly up to the longest absence on record (knee 163 to 601 days). Built in
  `scripts/build_injury_model.py:433-453`; used at `health.py:1028-1043`.
- Also on screen: 16 of 81 injury news items say "(unspecified)", as in "Paul George is expected to miss about 179
  games with a ankle (unspecified)", article error included.

**3. Shooting splits don't match player ratings (3-point cause code-confirmed; product rule 4).**
- What: league 3-point shooting 32.3% (real 36.0%; these players' own ratings average 35.6%). Two-point shooting 59.0%
  (own 54.5%). Free throws 81.2% (real 78.3%). Lauri Markkanen shot 25.5% on 415 threes against a rated 35.1%; Cooper
  Flagg 25.4%, Franz Wagner 26.3%.
- Why wrong: overall scoring efficiency looks right, so it hides, but every shooter's line is off.
- Where: a player's 3-point chance is scaled by tonight's points over his usual points (`offense.py:289-317`,
  `sim.py:2172-2174`). Players average only 95% of their usual points, worse on teams full of scorers, so their
  percentage drops all season (correlation 0.69; players under 85% of usual shot .283 against .348 own). My reading of
  the 2-point side, not tested: the box score then removes two-point misses to keep team shot totals right
  (`box_variation.py:182-207`).
- The real-stat scorecard has no 2-point, 3-point or free-throw percentage target, so nothing flagged it.

### Game and box score realism

**4. Too many players get in every night.** 12.8 per team-game (real 10.8); 54% of team-games use 13 or more (real
16%). Jerami Grant went from 30 real minutes to 9.3 across 80 games on a 48-win team; Kyle Kuzma (9.6) and Tim
Hardaway Jr. (9.7) played all 82. Likely: `sim.py:1033-1049` (top 14 by planned minutes plus late-game extras) and the
coach's plan in `save.py:7964` `team_rotation_projection`.

**5. Big nights are squashed.** 40-point games 47 (real 133), 50-point games 3 (real 17), 20-rebound games 9 (real 26),
40-minute nights 292 (real 509). Likely: the nightly points cap (`sim.py:2621-2662`, `2746-2789`) and the minutes model
(`game_minutes.py`).

**6. Silly steal and turnover nights.** Jarrett Allen had 9 steals; rookie center Tarris Reed Jr. 8 in 21 minutes; the
league news promotes lines like "Rudy Gobert recorded 7 steals". 6+ steal games 52 (real 27). 10+ turnover games 14
(real 3), Deni Avdija had 12. Likely: team steal totals are re-shared in proportion to a handful of random draws
(`box_variation.py:222-228`, `sim.py:2415`) and turnovers are drawn with a long tail (`box_variation.py:162-166`).

**7. Home court nearly vanished this season.** Home teams won 50.3% (real 55.4%), and under half from February on.
An older four-season run of today's engine showed 55-56%, so this may be luck or a recent change. Check with more seeds
before touching `sim.py:1872-1876`.

**8. A record team out of nowhere.** Oklahoma City: 73-9, +15.6 per 100 possessions (better than any real season),
27 straight wins, against a 62.5 betting line. One seed; the older run had them at 62 wins. Worth a spread-of-records
check on several seeds.

**9. Playoff minutes jump oddly.** Alex Caruso went from 25.7 to 39.9 a night for 16 games after Oklahoma City's
injuries. Likely `game_minutes.py` / rotation projection with two stars out.

### Front office eye-rolls

**10. The champions traded Evan Mobley for Cam Spencer (July 1).** Cleveland's own note says the rotation gets worse;
the $61M tax saving outweighed it. Right after winning, the team is labelled "exiting" its window. Likely: tax savings
valued too highly for a champion (`trade_tax.py:70`, `322-330`, and the window label from `team_planning.py`).

**11. First-round picks for end-of-bench players.** Matisse Thybulle (9 minutes a night over the season), Jalen
Slawson (7), Quinten Post (9), Isaiah Stewart (14) and Mitchell Robinson (15) each cost their new team a first-round
pick right (some are "better of two picks" rights). One 2028 right changed hands three times in a month (Washington to
Philadelphia Jan 7, to the Lakers Jan 20, to Indiana Feb 5). Washington paid it for
Adem Bona, then declined his $2.5M option in June and let him sign a two-way deal elsewhere. Likely: the AI's pick
pricing and its allowance for accepting a small loss (`transactions.py:1445-1502`, `trade_market.py`).

**12. San Antonio paid a first for a player who couldn't play.** Kristaps Porziņģis was ruled out through June before
opening night; the Spurs sent a 2027 first, a second and Luke Kornet for him on Jan 30. He then took his $20.5M
option. Likely: long injuries only mark a player as salary filler (`trade_targets.py:457-500`), they don't lower what a
buyer will pay.

**13. A salary dump with nothing attached.** Orlando (41-41, labelled "rebuilding") sent Jonathan Isaac to Memphis for
nothing to save tax. In real life the team shedding salary pays a pick, or gets something for a useful player. Same
code as 11.

**14. The West champions can't fill a roster.** Minnesota starts 2027-28 with 11 players because a hard cap blocks even
a minimum contract, and the game leaves them there (`camp.py:690-705`; the AI should never trigger a hard cap it can't
live under).

**15. Team draft boards are wildly apart.** Miami had consensus No. 23 as the best player in the whole class (took
him 10th), New York had No. 25 first (14th), Portland No. 34 first (16th), and Oklahoma City had No. 49 second. Likely:
the size of each team's scouting error (`draft_scouting.py:389-396` and `team_report`).

### Awards

**16. Defensive Player of the Year is a ratings contest.** Isaiah Hartenstein won with 1.4 blocks over teammate Chet
Holmgren (2.0). About 150 of his 162 voting points come from ratings and about 7 from steals and blocks
(`save.py:10148-10164`). MVP and All-NBA also add the hidden overall rating (`save.py:10166-10172`).

**17. Thin Most Improved winner.** Jose Alvarado, 11.7 points a game. The award is the raw gain in box production
(`save.py:10174`), with no starter or scoring bar.

Not a bug but surprising: Gilgeous-Alexander (63 qualifying games) and Wembanyama (64) missed awards under the real
65-game rule.

### Smaller
- Golden State fired Steve Kerr after a 38-44 season with Porziņģis and Butler hurt.
- Grayson Allen turned down a $19.4M option and was still unsigned on October 1.
- Every player's box score records 0 offensive rebounds (only the team total is filled, `sim.py:2083`). Not shown on
  screen today; anything built on it later would be wrong.

## Suggested order for fixes
1. Lottery membership (item 1), then decide on the 3-2-1 format.
2. Injury names versus lengths (item 2).
3. Three-point scaling (item 3), and add 2P%, 3P%, FT%, players used and 40-point games to the real-stat scorecard.
4. Champion and tax behaviour, pick-for-bench trades, hard-cap rosters (items 10, 11, 14).
