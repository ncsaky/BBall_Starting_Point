# Smart rest and fatigue from minutes played (SMART-REST, 2026-11-19)

## TL;DR

- Coaches now decide rest the way real teams did in 2025-26: mostly on back-to-backs (either night, more on the road), more for older players and stars, more against weak teams **and** against the league's very best, much more once a seed is locked, less deep into a road trip. Travel distance and time zones turned out not to matter once you know whether the team is on the road.
- Every rest decision now has a plain-words reason (for example "second night of a back-to-back on the road, opponent 12-40, age 33"), logged for AI teams and shown on your zZ note, which uses the same rule.
- Fatigue is now added from the minutes a player actually played (overtime counts, blowout rest and foul trouble don't), not from the coach's plan. Both scorecards are unchanged.

## What the real data says

**Data.** The 2025-26 regular-season box scores (`data/research/game_boxscores_2025_26.json`, ESPN game summaries, 1,235 games). A "single-game absence" is a game a regular (25+ minutes a game over 20+ games) missed while playing his team's games before and after, and not a coach's-decision DNP. That is how a rest night looks in a box score. Multi-game absences (injuries) are not counted as chances to rest. That gives 170 regulars, 10,895 chances and 414 single-game absences (3.8%).

**Are rest and injury told apart?** Mostly not. ESPN lists inactive players only sometimes: of the 414 absences, 293 have no reason listed, 89 name an injury, 11 say "rest", 8 illness, 6 suspension, 4 "injury management" and 3 personal reasons. So the model is fitted to all single-game absences, and the injury model's own one-game absences are accounted for in the calibration (see below).

**What predicts a healthy regular sitting.** Logistic model (`scripts/research/fit_rest_model.py`; rows from `scripts/research/rest_patterns.py`). Each factor multiplies the odds, holding the others fixed. "Strength" is the z-score (estimate / standard error); about 2 or more is solid.

| Factor | Odds multiplier | Strength | Raw rates |
|---|---|---|---|
| Second night of a back-to-back | x2.58 | 6.1 | 8.6% vs 2.4% on other nights |
| ... and that second night is on the road | x1.73 more | 3.2 | road 10.0%, home 7.2% |
| First night of a back-to-back | x1.63 | 3.5 | 4.0% |
| Age, per year over 27 (up to 34) | x1.10 a year | 4.6 | under 25: 2.7%, 25-29: 3.9%, 30-33: 5.7%, 34+: 5.6%; second nights 6.0 / 8.8 / 13.3 / 13.5% |
| Star (top 45 by game score; the league counted 45 policy stars in 2025-26) | x1.61 | 3.2 | 4.6% vs 3.5% |
| Minutes a game, per 5 over 30 | x0.77 | -2.3 | (raw rates flat at 3.8% because stars play more) |
| Opponent weaker, per .100 of winning % below .500 | x1.32 | 5.8 | opponent under .350: 5.6%; .500-.650: 2.9% |
| Opponent among the very best, per .100 above .600 | x2.65 | 5.7 | opponent .650+: 4.8% (holds with Oklahoma City left out: x2.2) |
| Season progress, opening night to last game | x1.97 | 3.5 | October 1.6% rising to April 7.0% |
| Last 20 games, seed locked | x2.35 | 2.4 | 11.6% (stars 4 of 15) vs 4.9% still racing |
| Last 20 games, out of the race | x1.41 | 1.1 | 6.3% (single games; shutdowns are separate) |
| Third game or later of a road trip | x0.58 | -3.2 | teams rest early in a trip, not late |
| Back-to-back within 5 games of returning from an absence | x2.26 | 4.0 | 16.1% vs 7.5% |

Tested and left out because they predicted nothing once the factors above were in:
- **Travel distance** (per 1,000 miles: x0.96, strength -0.4; on back-to-backs x0.70, -1.4). Raw rates by miles since the last game: 0 miles 4.2%, under 500 4.0%, 500-1,000 3.7%, 1,000-1,500 2.7%, 1,500+ 3.5%.
- **Time zones crossed** (x0.94, -0.8), in either direction.
- **The team's own record** (x0.96 per .100, -0.8). The race matters (locked seed), the record itself does not.
- **Home games on other nights** (x1.10, 0.7).
- **Stars against weak teams in particular** (star x weak-opponent: x0.96, -0.5). Stars do rest more against weak teams, but by the same proportion as everyone else.
- **Stars resting less while racing**: the late-season race itself does not lower rest (x1.01); a locked seed raises it.
- **Games in the last 4 or 6 days** (beyond back-to-backs): nothing.

**Your question, "good players get rested against bad teams".** Yes, and it is one of the strongest effects, but there's more:
- Stars: 5.8% against teams under .400, 4.0% against .400-.600 teams, 4.7% against .600+ teams.
- The least rest comes against good playoff-level opponents (.550-.650), the games that decide seeding and tiebreaks. Rest rises again against the league's very best (Oklahoma City's opponents sat a regular 6.7% of the time). Coaches seem to write off a likely loss, especially on a back-to-back.

**Your question, "less rest for good players in a playoff hunt".** The data shows it the other way round. Rest is normal while anything is still in play. It more than doubles once nothing is left to play for:
- Last 20 games: 11.6% with a locked seed against 4.9% still racing.
- Final game: 72% of regulars on locked top-six teams sat it, 50% on other locked teams and 29% on teams still racing.

**Final games** (regulars who had played in the five games before; small samples):

| | Locked, top six | Locked, other | Still racing | Out of the race |
|---|---|---|---|---|
| Last game | 72% (47) | 50% (28) | 29% (45) | 59% (22) |
| Second-to-last | 30% (33) | 27% (11) | 25% (76) | 50% (22) |

**Two or more regulars resting together.** That happened in 56 of 2,388 team games, twice what independent decisions would give (28). One sat in 290. So the old "one rested regular a game" rule was too strict. The league's actual rule is one *star* a game.

**League rules** (sources below):
- The 2023 player participation policy:
  - no more than one star out in the same game;
  - stars available for national TV and NBA Cup games;
  - one-game absences balanced between home and road;
  - no long shutdowns of healthy stars;
  - back-to-back rest pre-approved only for players 35+, or with 34,000 career minutes or 1,000 games.
- Fines: $100K, $250K, then $1M more each time.
- No "same opponent twice" rule exists in any source found. The rules did not change for 2024-25 or 2025-26; Cleveland was fined in November 2025 for resting Mitchell and Mobley together.
- The 65-game award rule (2023 labor deal): 20+ minutes counts as a game, two 15-20 minute games also count, and 62 games is enough after a season-ending injury.
- Real teams rest on the road more often than the policy asks: Sportico found 77% of stars' skipped back-to-back games in 2022-23 were road games; we see 59% for all regulars in 2025-26.

**Not measured: national TV.** The box scores don't record broadcasts. The official list of national games is published only as downloadable PDF schedules, which I did not download. So the national-TV rule is not modeled. The game's schedules carry no TV flag either.

### Sources

- ESPN game summaries, 2025-26 regular season: `data/research/game_boxscores_2025_26.json` (`site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={id}`, fetched 2026-05-23).
- Arena coordinates and time zones: each arena's Wikipedia page and team sites, `data/canonical/arenas.json`.
- NBA.com, "NBA Board of Governors approves new Player Participation Policy", 2023-09-13: https://www.nba.com/news/nba-board-of-governors-approves-new-player-participation-policy
- Hoops Rumors glossary, Player Participation Policy (Luke Adams), 2024-11-26: https://hoopsrumors.com/2024/11/hoops-rumors-glossary-player-participation-policy.html
- Hoops Rumors, "NBA stars affected by Player Participation Policy in 2025-26" (45 stars), 2025-11: https://www.hoopsrumors.com/2025/11/nba-stars-affected-by-player-participation-policy-in-2025-26.html
- NBA.com, Cleveland Cavaliers fined under the policy (2025-26): https://www.nba.com/news/cleveland-cavaliers-fined-player-participation-policy
- Sportico (Lev Akabas) via Yahoo, 2023-10-24, road share of stars' back-to-back absences: https://sports.yahoo.com/nba-load-management-rules-limit-040100843.html
- ABC7/ESPN load-management explainer (2018-19: about two-thirds of rest absences on back-to-backs): https://abc7.com/post/nba-load-management-what-we-know-and-dont-know/5694160/
- NBA.com, league load-management study (no clear link between rest and fewer injuries): https://www.nba.com/news/nba-sends-data-load-management-study
- 65-game rule explainers: CBS Sports https://www.cbssports.com/nba/news/nba-65-game-rule-awards-luka-doncic-anthony-edwards/ and Yahoo https://sports.yahoo.com/explaining-nbas-65-game-rule-030826797.html
- Travel and back-to-back performance (summary only): https://pmc.ncbi.nlm.nih.gov/articles/PMC8636381

## The model in plain words

`src/nba_gm_data/rest_model.py`, used by `health.simulate_health` (AI coaches, and your coach when "Coach rests players" is on) and by the zZ suggestion (`save.attach_rest_suggestions`). Both build the same game facts (`health.game_rest_context`).

For each healthy regular (24+ planned minutes) before each game, the coach looks at:
- **the schedule**: either night of a back-to-back (more on a road second night), how deep into a road trip, how far into the season;
- **the player**: age, whether he's one of the league's 45 best by rating, his minutes, whether he's back from an absence in the last five games;
- **the opponent**: its record (pulled toward .500 early in the season), with more rest against weak teams and against the very best;
- **the race**: in the last 20 games, a locked seed means much more rest and being out of the race a little more;
- **unusual fatigue**: only when his tip-off fatigue is well beyond a typical back-to-back (a GM playing a star 42 minutes through a dense stretch). This is a judgment call. AI teams almost never get there, and real coaches rest before it.

These multiply into a chance, usually 1-3% on ordinary nights and 6-15% on back-to-backs. The game then draws once, seeded per game and player as before. There is no extra randomness beyond that draw.

**Calibration:** the real rates include one-game injuries and illnesses, which the injury model already produces. The league rules take some rests away. In full seasons the two roughly cancel. The model's odds times 1.02 gives the real overall single-game absence rate (3.8%).

**Rules and guards:**
- at most two regulars rested a game (real 2025-26), and at most one star (participation policy);
- no rest nights once a player has missed 14 games (65-game rule);
- none while three regulars are already out;
- **final two games**: chances by the race, from the table above;
- **shutdowns**: the eight worst teams in their last 25 games can still shut regulars down (3% a game), now alongside ordinary rest nights. Before, the shutdown rule replaced them, so bottom teams had almost no single rest nights (0.9% against real 6.3%).

**Reasons.** The reason lists up to three factors that raised the chance most, for example:
- "second night of a back-to-back on the road, opponent 12-40, age 33";
- "first night of a back-to-back, star workload";
- "playoff seed locked: rest before the playoffs".

Each AI decision is written to the save's `rest_log` (this season only) with its date, game, team, player, reason and chance. The zZ tooltip shows the same reason: "Coach suggests resting him on DATE: reason."

**Travel** is computed for every game: miles from the previous game's arena, time zones crossed, road-trip length (`team_schedule_context`). It is logged with each decision. It is not in the reason or the chance, because it predicts nothing. Showing "1,800 miles of travel" as a reason would suggest the coach weighs something he doesn't.

## Before and after against real

Two full seasons per version (seeds 17 and 29; fixed opening rosters, all 30 teams AI-coached, 94-input ratings). "Before" is the current main code; "after" is this branch. Same measure as the real column. Harness and outputs: `output/smart-rest/` (`sim_season.py`, `compare.py`, `prior_def.py`; files `base_*` and `final_*`).

**Single-game absences of regulars** (before s17 / s29, after s17 / s29, real):

| | Before | After | Real |
|---|---|---|---|
| All | 3.8 / 3.8% | 3.7 / 4.0% | 3.8% |
| First night of a back-to-back | 1.8 / 2.8% | 3.0 / 4.1% | 4.0% |
| Second night | 7.9 / 8.4% | 8.1 / 8.3% | 8.6% |
| Second night, home / road | 7.9 / 7.9%, 7.3 / 9.4% | 6.2 / 10.0%, 6.7 / 9.8% | 7.2 / 10.0% |
| Other nights | 3.2 / 2.8% | 2.7 / 2.7% | 2.4% |
| Road trip game 3+ | 3.9 / 4.2% | 3.1 / 3.7% | 3.0% |
| Travel: 0 / under 1,000 / 1,000+ miles | 3.6 / 3.5 / 4.2%, 3.8 / 3.8 / 3.8% | 3.1 / 3.4 / 4.6%, 4.2 / 3.9 / 3.8% | 4.2 / 3.9 / 3.0% |
| Stars / others | 4.2 / 3.6%, 4.1 / 3.7% | 4.8 / 3.3%, 4.2 / 3.9% | 4.6 / 3.5% |
| Age under 25 / 25-29 / 30-33 / 34+ | 2.8 / 3.9 / 4.8 / 3.9%, 3.2 / 3.2 / 5.2 / 5.3% | 3.0 / 3.7 / 4.6 / 4.5%, 3.8 / 3.2 / 4.7 / 5.7% | 2.7 / 3.9 / 5.7 / 5.6% |
| Opponent under .350 / .350-.500 / .500-.650 / .650+ | 4.3 / 3.4 / 3.9 / 3.7%, 4.5 / 3.7 / 3.7 / 4.0% | 5.2 / 3.8 / 3.4 / 4.7%, 5.7 / 4.0 / 3.4 / 4.9% | 5.6 / 3.8 / 2.9 / 4.8% |
| Stars vs opponents under .400 / .400-.600 / .600+ | 5.2 / 4.1 / 3.7%, 4.2 / 4.0 / 4.1% | 6.2 / 4.4 / 5.3%, 5.2 / 4.1 / 3.4% | 5.8 / 4.0 / 4.7% |
| Last 20 games: locked / racing / out of the race | 2.5 / 5.6 / 0.9%, 13.4 / 4.1 / 0.8% | 6.0 / 4.1 / 7.1%, 12.8 / 3.7 / 4.7% | 11.6 / 4.9 / 6.3% |

In one seed the sim rests a little more after long trips than real (4.6% against 3.0%). Travel itself has no effect in the model: long trips come with road back-to-backs, which do raise rest. Real teams seem to schedule their rest nights after short hops more than the model knows.

**The injury-rest report's measure** (all of a regular's team games; real 3.2 / 7.2 / 2.4%):
- before: 3.3 / 6.9 / 2.5% and 3.3 / 7.2 / 2.4%;
- after: 3.3 / 7.1 / 2.4% and 3.4 / 7.1 / 2.6%.

Back-to-backs by age, after: under 25 6.0 / 8.2%, 25-29 6.0 / 5.7%, 30-33 9.7 / 6.7%, 34+ 9.7 / 11.0%. Real: 5.2 / 7.4 / 10.0 / 11.4%.

**Final two games** (share of recent regulars who sat; small samples, before s17 / s29, after s17 / s29, real):

| | Before | After | Real |
|---|---|---|---|
| Last game, locked top six | 41 / 34% | 61 / 36% | 72% |
| Last game, other locked | 25 / 15% | 33 / 31% | 50% |
| Last game, racing | 22 / 16% | 31 / 42% | 29% |
| Last game, out of the race | 26 / 17% | 36 / 31% | 59% |
| Second-to-last, out of the race | 12 / 17% | 45 / 39% | 50% |

**Season shape** (players with 40+ games):

| | Before | After | Real |
|---|---|---|---|
| 30+ / 34+ / 36+ minutes a game | 62 / 14 / 3, 61 / 19 / 4 | 63 / 15 / 3, 62 / 19 / 4 | 70 / 18 / 3 |
| Most minutes a game | 36.5 / 36.5 | 36.5 / 36.6 | 38.0 |
| Games played, 30+ minute players: median / mean | 70 / 65.0, 69 / 64.6 | 69.5 / 64.9, 69 / 64.9 | 68 / 61.7 |
| Rest decisions a season (rest nights / shutdowns) | not logged | 466 / 25, 440 / 27 (about 15 rest nights a team) | |

The games-played median is 69-70 both before and after on today's main. The injury-rest report measured 68-69 on its own base. Rest volume matches real, so the remaining gap is in injuries (a few real season-long injuries that one simulated season rarely produces), not in rest.

## The fatigue fix

**Before:** the day's health pass added each player's fatigue from the coach's planned minutes before the game was played. Overtime, blowout rest, foul trouble and injury exits never counted.

**Now:**
- The health pass still recovers fatigue to game day and records the tip-off value the game uses. It no longer adds planned minutes.
- After each game, the save adds every player's fatigue from his box-score minutes (`health.add_box_score_fatigue`), overtime included. This happens for regular-season and playoff games, and the same game is never added twice.
- Daily recovery and the tip-off use are unchanged.
- Standalone health runs (`simulate-health` command) still use planned minutes, since they have no box scores.
- After the day's games the save refreshes your team's next-game fatigue and rest note, so they include tonight's minutes.
- The one `sim.py` hook was not needed: the save is where the box score and the health records meet. `sim.py` is unchanged.

Fatigue added per game, players averaging 30+ minutes (before s17 / s29, after s17 / s29):

| | Minutes played | Planned | Fatigue added before | Fatigue added after |
|---|---|---|---|---|
| Overtime games | 38.1 / 38.8 (before), 37.8 / 37.5 (after) | 35.3 / 35.2 | 29.6 / 28.2 | 32.9 / 32.4 |
| Blowouts (21+ points) | 29.0 / 29.2 | 35.0 / 35.3 | 29.4 / 29.0 | 24.9 / 24.7 |
| Other games | 33.5 / 33.6 | 34.9 / 35.1 | 29.3 / 29.3 | 28.7 / 28.9 |

The fatigue bar (players at 30+ minutes, every day):

| | Before | After |
|---|---|---|
| Green / yellow / red | 61 / 35 / 4%, 60 / 35 / 4% | 67 / 30 / 3%, 66 / 30 / 3% |
| Median / 90th percentile | 34.9 / 53.7, 35.0 / 53.9 | 32.7 / 51.1, 33.2 / 52.0 |
| Each player's season high: 10th / 50th / 90th percentile | 55 / 61 / 73 | 54-55 / 63 / 73 |
| Median tip-off fatigue | 16.9 / 17.0 | 15.7 / 16.0 |

The bar sits a little lower: heavy-minute players play 1.5 minutes fewer than planned in normal games and 6 fewer in blowouts. The busiest stretches still reach the red, and their peaks went up slightly. The team fatigue effect and injury risk follow the new values automatically.

**Checked in a real save** (`output/smart-rest/save_check.py`: new Boston save, advanced through the app's own day loop to 25 November):
- every player's fatigue after the last day's games equals his tip-off value plus the gain from his box-score minutes (66 of 66 lines; on the old code 53 of 65 differ);
- the rest log holds 67 AI decisions with reasons, for example "age 37, first night of a back-to-back, star workload";
- the user team's next-game fatigue is refreshed after the games.

## Scorecards

Both scorecards replay real games with real minutes, so they don't run the rest or fatigue paths. Both match main exactly:
- Real-stat targets, 94-input ratings (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.
- Betting-odds test, 100 runs (`validate-season-probabilities`): **Brier 0.1962, log loss 0.5791** (market 0.1962 / 0.5740), spread error 4.53, totals error 5.48, 1,231 games (1,018 with odds).

## Speed

- Game simulation: 31.1 / 31.3 s of processor time per 1,230 games after, against 30.2 / 29.8 s before (about +1 s a season, within this machine's noise).
- Season wall time (headless harness): 50.6-51.3 s against 48.1-48.6 s before, on a machine shared with three other agents.
- App path: the new work (box-score fatigue, the second rest-note pass after the games, star list, standings, schedule facts) profiles at about 1 s per five simulated weeks, so about 0.5 s a month.
  - That figure is under the profiler, after caching the star list per month and roster, and the stamina lookup and config.
  - Wall time to 25 November was 36.6 s on the old code and 37.0-39.6 s on the new, on a machine at load 17-20 from other agents. That difference is mostly noise; the profile is the better guide.

## Tests

- New `tests/test_smart_rest.py` (16 tests):
  - arena data and distances;
  - schedule facts (back-to-back nights, travel, time zones, road trips, density);
  - each fitted factor's direction;
  - travel not changing the chance;
  - the rules (two a game, one star, short-handed, 65-game);
  - final games and shutdowns alongside rest nights;
  - plain-words reasons;
  - the heavy-workload extra;
  - standings situations;
  - fatigue from box-score minutes (overtime, blowout, road, idempotent, recovery into the next tip-off);
  - planned-minutes fallback;
  - the rest log.
- Updated tests that pinned the old rest numbers:
  - `tests/test_injury_rest.py`: two-a-game and one-star rules, final-game chance by race, shutdown through the decision;
  - `tests/test_fatigue_rest.py`: rest follows fatigue only beyond a typical back-to-back.

- Focused modules (`test_smart_rest`, `test_fatigue_rest`, `test_injury_rest`, `test_game_minutes`, `test_absence_fill`, `test_injury_model`): 83 OK.
- All `tests/*.test.cjs`: all pass except `startup_video.test.cjs`. That one fails because the startup video is not in a fresh worktree (git-ignored), and it is unrelated to this task.
- Core suite `scripts/run_core_tests.sh`: 337 run, OK (2 skipped).
  - The first run caught a real bug: the daily health pass loaded the season schedule on days without games, which failed in rollover tests whose folder has no schedule file.
  - It now loads only on game days.

## What's left

1. **National TV games** are not modeled. There is no broadcast data in the box scores or in the game's schedules. Adding it needs the league's national TV schedule (PDF downloads) and a TV flag on generated schedules.
2. **Older players on back-to-backs** are still a little under real in one seed (30-33: 6.7-9.7% against 10%).
3. **Final games on locked and out-of-race teams** are still under real in places (other locked teams 31-33% against 50%; out of the race 31-36% against 59%). The samples are small (11-47 players a cell).
4. **Second-to-last game for teams still racing** shows 45% sitting in one seed and in the base code (real 25%). That comes from rank-based shutdowns on bottom-eight teams that still have a mathematical play-in chance, not from rest.
5. **Games played** stays at a median of 69-70 for heavy-minute players (real 68). Rest volume now matches real, so the gap sits with injuries.
6. **Fatigue-driven rest beyond a back-to-back** is a judgment term (up to 1.5x the odds). Real data cannot show it, because real coaches rest players before they get there.
7. **Not clicked through in the running app.** The zZ tooltip wording is unchanged and was not checked live; the save check above exercises the code path.

## Resume state

- **Done:**
  - real analysis (`scripts/research/rest_patterns.py`, `fit_rest_model.py`; outputs `output/smart-rest/real_patterns.txt`, `real_fit.txt`);
  - model and wiring, fatigue hook, tests;
  - two seasons before and after (`base_s17/29`, `final_s17/29`; `v1`-`v3` were calibration steps);
  - save check.
- **Harness** (in `output/smart-rest/`, git-ignored):
  - `run.sh LABEL SRC SEED ...` (base source extracted to `output/smart-rest/base_src/`);
  - `compare.py real LABEL...`;
  - `prior_def.py LABEL...`;
  - `save_check.py`.
- **Branch:** commits on this worktree branch. Not pushed or merged. **Coordinator:** copy `output/smart-rest/` (git-ignored) to main's `output/` before removing the worktree.
