# National TV games, games played and older players' back-to-backs (OVERNIGHT-REST-GAMES, 2026-11-20)

## TL;DR

- Every generated season now has a national TV slate (about 246 games, 20%, picked the way the league picks them: strong rosters, stars, big markets), shown as a small "TV" tag on the calendar. Real 2025-26 regulars sat about a quarter less often in national TV games, and coaches now do the same.
- Seasons now open with some players already hurt, as real seasons do (offseason surgeries, training-camp injuries and, in a new career, injuries left over from last season). Heavy-minute players' median games played is now 68 across two test seasons (69 and 67; real 68, was 69-69.5).
- Players 30 and over now rest more on back-to-backs (either night) and players under 27 a little less, which the real data showed and the old straight-line age rule missed. Real-stat scorecard still 18/18.

## 1. National TV games

### The real 2025-26 slate

ESPN's public scoreboard lists each game's national broadcasts (`site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`). I fetched every date of the 2025-26 regular season (`scripts/research/national_tv.py`, saved to `data/research/national_tv_2025_26.json`; no PDFs needed).

- 311 of 1,235 games had a national broadcast:
  - 246 on ESPN, ABC, NBC, Peacock or Prime Video (2025-26 was the first year of the new TV deal, so no TNT);
  - 63 on NBA TV only.
- Team counts are very uneven: New York 35, Oklahoma City 34, Lakers 34, San Antonio 32, Golden State 32 ... New Orleans 0, Brooklyn 1, Utah and Washington 2, Indiana 3.
  - The top ten teams got 63% of all national slots and the bottom ten 7%.
- What drives it:
  - last season and the roster (Oklahoma City, Cleveland, Houston, Denver);
  - star power (San Antonio: 34 wins the season before, 32 national games);
  - market (New York, the Lakers, Golden State, Boston; Philadelphia got 18 after 24 wins).
- Month by month: October 16, November 32, December 33 (all five Christmas games), January 48, February 44, March 55, April 18.
- Usually two national games a night.
- The league keeps them off second nights of back-to-backs where it can: 12.4% of national team-games were second nights, against 19.5% of the others.

### What it does to rest (real box scores)

Same measure as the smart-rest work: single-game absences of regulars (25+ minutes a game) between two games played. Data: 10,895 chances and 414 absences.

| | National (ESPN/ABC/NBC/Peacock/Prime) | NBA TV only | Local |
|---|---|---|---|
| All regulars | 2.7% (2,319) | 5.2% (582) | 4.0% (7,994) |
| Stars (top 45) | 3.2% (653) | 8.1% (160) | 4.7% (2,050) |
| Other regulars | 2.5% (1,666) | 4.0% (422) | 3.8% (5,944) |

In the fitted model, with every other factor held fixed (back-to-backs, opponent, age, race and so on):
- A national game multiplies the odds of sitting by **x0.73**. Strength -2.1, which counts as solid.
- Stars are not affected more than other regulars: the extra star effect is x0.98, strength -0.1.
  - The league's participation policy names stars, but real teams rest everyone a little less on national TV.
- NBA TV-only games show no drop. If anything there was more rest (x1.49, strength 1.9). So they are not counted as national.

### In the game

- **The slate.** `src/nba_gm_data/national_tv.py` builds it when a season's schedule is made: at a new career and at every rollover (`save.mark_national_tv_safely`).
  - Each team gets an appeal score from three things: roster strength (its best eight players; at a rollover, half of it is last season's record), star power (its best two players) and market.
  - The market bonus is a judgment call. It goes to New York, the Lakers, Golden State and Boston, with smaller amounts for Philadelphia, the Clippers, Chicago, Miami and Dallas.
  - The most appealing team gets the largest real count (35), the next the next largest, down to 0. That way the spread across teams matches 2025-26.
  - Games are then chosen to fill those counts, within each month's real count and two games a night (three at most).
  - About half of the games on a second night of a back-to-back are skipped.
  - Every Christmas game is national.
  - Each chosen game gets `national_tv: true` in the schedule.
- **Generated 2026-27 slate against real 2025-26:**
  - 245 games;
  - top ten teams 64% and bottom ten 7% of slots (real 63% and 7%);
  - correlation with the real team counts 0.71;
  - second nights 12.9% against 19.2% (real 12.4% and 19.5%);
  - the months match.
  - Oklahoma City, Boston, Golden State, Philadelphia, San Antonio and the Lakers lead. Sacramento, Chicago and Milwaukee get almost none on their 2026-27 rosters.
- **Rest.** `rest_model.py` has the new national TV factor (x0.73). The AI coaches and your zZ suggestion both read it from the game.
- **Calendar.** National games show a small "TV" tag next to the opponent. The hover says "National TV game: stars are expected to play". The change is one line in `gui/app.js` plus one CSS rule, and the calendar data now carries the flag.
- **Not done:** the NBA Cup, which the policy also covers. The game has no Cup games.

## 2. Games played: season-start injuries

### What was wrong

I split heavy-minute players' missed games (30+ minutes a game) by where they happen, real against the previous code:

| Missed games per player | Real 2025-26 | Before (2 seasons) |
|---|---|---|
| Before his first game (season start) | **3.95** | **0.05 / 0.00** |
| Single games | 2.40 | 2.68 / 2.48 |
| 2-10 game absences | 5.60 | 4.05 / 4.02 |
| 11+ game absences | 4.02 | 5.64 / 5.37 |

In-season absences add up about right: 12.0 real against 12.4 and 11.9 simulated. The gap was almost entirely the season start. Nobody in the game ever started a season hurt:
- **A new career started with nobody injured.** The 2026-27 universe has no current injuries.
- **Nothing happens between seasons.** There are no offseason surgeries and no training-camp injuries.
- **Injuries left over from a simulated season do carry over correctly.**
  - Return dates skip July-September, the same way Basketball Index counts days.
  - Playoff games run the injury model too.
  - In one simulated season, 1.9% of regulars were still hurt on next season's opening night from regular-season injuries alone. Real data: 1.8% from the previous regular season and 0.9% from the playoffs.

### Real season-start absences

`scripts/research/season_start_absences.py` uses the Basketball Index injury tracker (local only) and the 2025-26 box scores.
- Population: the previous season's regulars (40+ games, about 25+ minutes).
- I counted every injury spell that began before opening night and was still running on it.

| | Out on opening night | Games missed at the start, per regular |
|---|---|---|
| 2025-26, exact (box scores give the first game) | 12 of 152 (7.9%) | 4.03 |
| ... from the offseason or training camp | 3.3% | |
| ... left over from last season or the playoffs | 4.6% | |
| 2016-17 to 2024-25, pooled (lower bound*) | 38 of 785 (4.8%) | 0.84 |

\*The tracker often leaves a spell open at the end of a season. Outside 2025-26 those spells are left out. In 2025-26 that rule caught only 6 of the 12 real cases, so the pooled rates (2.7% + 2.7%) fit 3.3% + 4.6%.

Examples from 2025-26:
- whole season: Haliburton, Irving, Lillard, VanVleet;
- most of it: Tatum 62 games, Strus 67, Finney-Smith 64;
- part of it: George 39, Herro 17, Fox 8.

Lengths when out, pooled over 50 cases:
- 1-5 games 26%;
- 6-20 games 32%;
- 21-40 games 16%;
- 41-81 games 18%;
- the whole season 8%.

### The fix

`health.season_start_injuries` runs once per season, when the career starts and at each rollover:
- **Who.** Every rostered player has a chance, seeded per season and player. The rates come from `data/canonical/season_start_injuries.json`, which holds derived numbers only:
  - 3.3% for regulars from the offseason and camp, every season;
  - plus 4.6% left over from last season, for a new career only (later seasons carry their own).
- **Who is more likely.** The chance is scaled two ways:
  - by the player's own injury risk under the injury model (age, body, style, history), from 0.4x to 2.5x;
  - by his minutes, so bench players are exposed less.
- **How long.** One of the 50 real cases' games-missed and body part. He misses exactly that many of his team's games.
  - The injury has a start date (August to October, or late last season), a diagnosis that fits the length, and counts as injury history for later risk.
  - The 65-game rule and the return-to-play minutes limit treat it like any other injury.
- **Effect.**
  - Over 20 seeds, 13 of 179 regulars a season start out hurt (7.3%). That costs 1.9 games per regular. Real 2025-26 lost 4.0, with four season-long injuries, an unusual year.
  - At a rollover only the offseason part applies, about 0.7 games per regular. The game's own late-season and playoff injuries add the rest.
- **The injury model's rates are unchanged.**
  - Injuries per game, recovery lengths and the Basketball Index match are the same.
  - This only adds the injuries that happen when no games are played.

### Before and after

Two full seasons (seeds 17 and 29, fixed opening rosters, all teams AI-coached). "Before" is current main (`output/smart-rest/final_*`), "after" is this branch (`output/overnight-tv/new2_*`).

| | Before s17 / s29 | After s17 / s29 | Real 2025-26 |
|---|---|---|---|
| 30+ minute players: median games | 69.5 / 69 | 69 / 67 (68 average) | 68 |
| ... mean games | 64.9 / 64.9 | 64.9 / 61.4 | 61.7 |
| ... missed at season start, per player | 0.05 / 0.00 | 0.19 / 2.83 | 3.95 |
| ... out at season start | 2 / 0 | 4 / 6 | 10 |
| 30 best-rated players: median / mean games | 66.5-69.5 / 62-68 (injury-rest report) | 68.5 / 66.7, 69 / 59.4 | 64.5 / 55.4 |

- Season-start injuries are lumpy. Seed 17 drew mostly bench players, while seed 29 lost Sengun and Jalen Green for the season and Curry for 62 games.
- **Still open: the 30 best-rated players' median stays about 4 games high** (68.5-69 against 64.5).
  - Their missed games differ in shape, not total. The game has fewer 2-10 game absences than real (3.9-4.1 per player against 5.6) and more 11+ game ones (5.1-6.0 against 4.0).
  - That comes from the injury model's recovery lengths, which are matched to Basketball Index. I left them alone.
  - The injury-rest report saw the same thing ("2-game and 6-10-game absences are a bit rarer than real").

## 3. Older players on back-to-backs

On the real data, the fitted model itself under-predicted:
- age 30-33 on second nights: 10.7% fitted against 13.3% real;
- under-25s: 3.4% against 2.7%.

The straight "x1.10 per year from 27 to 34" line was the wrong shape. Two terms replace it (strength about 3.5 each, and the fit's likelihood improves by 10):
- **age 30+ on either night of a back-to-back: x1.77**;
- **per year under 27 (down to 21): x0.91**.

On ordinary nights rest is flat after 27 (the old age term adds nothing once these are in: x0.99). Fitted against real, by age band, all within about half a point:
- 30-33 second nights 13.8% (real 13.3);
- 34+ 13.9% (13.5);
- under 25 6.2% (6.0).

Simulated (before s17 / s29, after s17 / s29, real):

| | Before | After | Real |
|---|---|---|---|
| Age 30-33, either back-to-back night | 7.2 / 6.1% | 9.4 / 7.7% | 10.0% |
| Age 30-33, second nights | 11.2 / 7.4% | 15.1 / 8.7% | 13.3% |
| Age 34+, either back-to-back night | 7.5 / 8.4% | 7.7 / 8.6% | 10.6% |
| Under 25, all | 3.0 / 3.8% | 2.6 / 3.3% | 2.7% |
| All regulars | 3.7 / 4.0% | 3.7 / 4.0% | 3.8% |
| National TV games / others | none | 3.4 / 3.8%, 3.1 / 4.2% | 2.7 / 4.1% |

- 34+ players on ordinary nights came out low in seed 17 (1.6% against real 2.9%, 622 chances). Seed 29 was 3.0%.
  - The fitted model matches real for 34+ (5.4% against 5.6%), so the gap is about who the old players are and the league rules.
  - For example, the 65-game rule stops rest once a player has missed 14 games, and older players miss more to injury. The model itself is not the problem.
- Every other factor was refitted along with these: back-to-back nights, stars, opponents, the race, road trips and returns. Their sizes barely moved (see `output/overnight-tv/real_fit.txt`).

## Other effects

- **Minutes shape.** 36+ minute players went from 3-4 to 7 a season and the top average from 36.5 to 37.8 (real 3 and 38.0).
  - When a starter misses the opening weeks, his teammates play more, and several players sit just under 36.
  - 30+ minute players are 65 and 63, against 63 and 62 before (real 70).
- **Final two games** are unchanged within their small samples.
- **Speed.**
  - Season simulation: 49.3-49.7 s wall and 30.3-30.7 s of game processor time, against 50.6-51.3 s and 31.1-31.3 s before (machine shared with other agents).
  - Building the TV slate takes about 1.6 s, once per new career and once per rollover.
  - Season-start injuries take a fraction of a second, once a season.
  - The daily path is unchanged.

## Scorecards and tests

- **Real-stat targets** (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**. Replays use real minutes and availability, so these changes do not touch them.
- **Betting-odds test:** not rerun. It replays real games with real minutes and does not use the rest, schedule or season-start paths, as the smart-rest and injury-rest reports showed.
- **New `tests/test_overnight_tv_rest.py`** (14 tests):
  - the national TV factor and its source in the schedule;
  - no TV in the reason;
  - the age shape;
  - the slate (size, spread, nights, Christmas, determinism);
  - team appeal (roster, market, record);
  - the calendar flag;
  - season-start injuries (exact games, whole season, carried only for a new career, seeded, already-injured players left alone, the rates file).
- **New check in `tests/seasonal_clipboard.test.cjs`:** the TV tag (59 pass).
- `tests.test_smart_rest`, `tests.test_injury_rest`, `tests.test_fatigue_rest`: 49 OK.
- **Core suite** `scripts/run_core_tests.sh`: 337 run, with one failure, now fixed.
  - `test_new_career_start` checked that a new save's injury list equals the source data exactly. It now allows the opening night's season-start injuries and checks they never touch players already out.
  - That module was rerun on its own: 8 OK.
- **Other health tests:** injury model, long-term health, league health, prospect injuries, minutes, absence fill, AI roles, playoff injuries card, slides, rollover: 120 OK.
  - The "preseason outlook failed: KeyError 'teams'" lines in the rollover tests also appear on main (a stub league in those tests). They are not caused by this change.
  - The preseason outlook's "long injuries" slide will now show season-start injuries.

## Sources

- ESPN public scoreboard API, national-market broadcasts, every 2025-26 regular-season date (fetched 2026-11-20): `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`. Saved: `data/research/national_tv_2025_26.json`.
- ESPN game summaries, 2025-26 box scores: `data/research/game_boxscores_2025_26.json`.
- Basketball Index Injury Tracker export (local only, not committed): `data/research/bbi/tools/injury_player_history.json`, `injury_player_seasons.json`. Derived numbers only in `data/canonical/season_start_injuries.json`.
- Player participation policy, national TV and NBA Cup games:
  - NBA.com, 2023-09-13: https://www.nba.com/news/nba-board-of-governors-approves-new-player-participation-policy
  - Hoops Rumors glossary, 2024-11-26: https://hoopsrumors.com/2024/11/hoops-rumors-glossary-player-participation-policy.html
  - Neither source says which networks count as "national". I measured NBA TV separately, and it shows no effect.

## Files

- **New:**
  - `src/nba_gm_data/national_tv.py`
  - `data/research/national_tv_2025_26.json`
  - `data/canonical/season_start_injuries.json`
  - `scripts/research/national_tv.py`
  - `scripts/research/season_start_absences.py`
  - `tests/test_overnight_tv_rest.py`
- **Changed:**
  - `rest_model.py`: refit, national TV and age shape;
  - `health.py`: the game context flag and season-start injuries;
  - `save.py`: slate and season-start hooks at a new career and at rollover, and the calendar flag;
  - `gui/app.js` and `gui/card-board.css`: the TV tag;
  - `scripts/research/rest_patterns.py` and `fit_rest_model.py`: national TV rows and new terms;
  - `tests/seasonal_clipboard.test.cjs`.
- **Harness** (git-ignored, `output/overnight-tv/`):
  - `sim_season.py` (`--no-tv`, `--no-start-injuries`);
  - `gp.py` (games played by source);
  - `compare_smart.py` (rest tables, with `sr_` labels for the smart-rest runs);
  - `tv_slate_check.py`, `carry_check.py`, `heavy36.py`, `insample.py`.
- **Coordinator:** copy `output/overnight-tv/` to main's `output/` before removing the worktree.
