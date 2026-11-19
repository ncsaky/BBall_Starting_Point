# ROT-OUTLIERS: bench players carried in on last season's minutes

## TL;DR

The AI coach now checks players who changed teams against their new team's talent. Last season's big minutes no longer lift a clearly weaker newcomer into the rotation. Luke Kennard (Phoenix) fell from 17.4 to 2.7 minutes a game, against a Basketball Index forecast of 5.0. Bruce Brown (New York) fell from 18.8 to 10.3, against a forecast of 4.5.
The fit to Basketball Index got slightly better overall in both rating sets. All four role groups stayed within 1.2 minutes of the forecast. Players who stayed with their team keep the same coaching as before.
Position slotting did not cause these outliers. The cause was workload carried over from another team. No player ratings or Basketball Index data entered the game.

## How I measured it

I used the same healthy-season method as ROT-SHAPE. Every game of the 2026–27 regular season was played with all 30 teams under AI coaches, on the canonical rosters, with seeds 17 and 29. Rosters, ratings and health stayed fixed. Players were matched to Basketball Index `healthy_rotation_mpg` by player ID. I ran it in both rating sets: the new 94-input ratings and the older ratings. The harness, its logs and the tables are in `output/rot-outliers/` (local only). Basketball Index minutes are read only for this comparison.

Role-group means count players who appeared, as in ROT-SHAPE. "Mean miss" averages the absolute gap over all 329 matched players, and a player who never appeared counts as zero minutes.

## Before and after

### Role groups (minutes per game played; Basketball Index healthy minutes in brackets)

| Ratings | Star | Starter | Key | Rot | Mean miss | More than 10 over / under |
|---|---:|---:|---:|---:|---:|---:|
| New ratings, before | 33.51 (34.33) | 29.13 (29.30) | 20.75 (21.48) | 9.54 (10.61) | 4.44 | 11 / 27 |
| New ratings, after | 33.53 (34.33) | 29.03 (29.30) | 20.89 (21.48) | 9.49 (10.69) | **4.41** | **9 / 27** |
| Older ratings, before | 33.33 (34.33) | 28.80 (29.30) | 21.39 (21.51) | 10.30 (10.74) | 5.23 | 16 / 35 |
| Older ratings, after | 33.38 (34.33) | 28.86 (29.30) | 21.33 (21.51) | 10.24 (10.60) | **5.13** | **15 / 34** |

The largest group gap after the change is 1.20 minutes, for the new ratings' Rot group (it was 1.07). It stays within the 1.5-minute limit. Every team still played exactly 240 minutes plus 25 per overtime period.

### The named players (new ratings; older ratings in brackets)

| Player | Basketball Index | Starting target | Before | After |
|---|---:|---:|---:|---:|
| Luke Kennard, PHX | 5.0 | 21.1 | 17.4 (17.4) | **2.7** (5.2) |
| Bruce Brown, NYK | 4.5 | 25.1 | 18.8 (19.8) | **10.3** (19.8) |
| Jordan Poole, NOP | 8.2 | 24.5 | 10.2 (19.9) | 10.2 (19.8) |
| Mitchell Robinson, BOS | 4.6 | 19.2 | 5.4 (16.0) | 5.4 (16.0) |

- **Brown, new ratings (+5.7):** he is New York's ninth man, and the ninth spot in the coach's minutes plan gets about 10 minutes. The other bench options behind him have no carried-over role (Pacôme Dadiet, 3.7 minutes in the starting data) or carry the same kind of role from another team. Basketball Index gives that spot to Dadiet (11.9). The gap is the depth of the rotation's tail, not Brown jumping the line.
- **Brown, older ratings (no change):** the older ratings rate him 49.0, above Landry Shamet (48.5). That is only 2.3 points under New York's line of 51.3. The small penalty, 4.6 priority points, does not move him. On those ratings, playing him over Shamet is a defensible call. The new ratings rate him 45.3, 3.6 points under New York's line of 48.9.
- **Poole and Robinson** were already corrected by ROT-SHAPE in the new ratings. In the older ratings the coach plays them because those ratings rank them sixth (Poole, 59.7) and fourth (Robinson, 64.2) on their teams.

### Players who moved by 3 or more minutes a game

New ratings (13 players, 6 closer to Basketball Index, 7 further):

| Player | Basketball Index | Before | After |
|---|---:|---:|---:|
| Luke Kennard, PHX (new team) | 5.0 | 17.4 | 2.7 |
| Cody Williams, MIN (new team) | 4.8 | 9.9 | 0.0 |
| Bruce Brown, NYK (new team) | 4.5 | 18.8 | 10.3 |
| Tim Hardaway Jr., MIA (new team) | 26.7 | 24.0 | 16.2 |
| Bennedict Mathurin, NOP (new team) | 29.6 | 28.9 | 23.7 |
| Zaccharie Risacher, DAL (new team) | 19.5 | 20.0 | 16.5 |
| Dennis Schröder, CHA (new team) | 13.0 | 27.7 | 24.7 |
| Jeremiah Fears, NOP | 23.4 | 23.7 | 27.1 |
| Jose Alvarado, NYK | 14.0 | 14.7 | 18.9 |
| Morez Johnson Jr., DAL | 15.9 | 15.5 | 19.9 |
| Ryan Dunn, PHX | 15.5 | 5.2 | 9.8 |
| Landry Shamet, NYK | 19.5 | 10.3 | 15.8 |
| Oso Ighodaro, PHX | 13.1 | 9.8 | 17.5 |

The new ratings place Hardaway (47.6), Mathurin (45.8) and Risacher (46.8) near the bottom of their new rosters. The coach now follows those ratings, while Basketball Index expects them to start or play heavy minutes. That disagreement is about ratings, not the coach. I list them for a ratings review below.

Older ratings (10 players, 8 closer, 2 further): Kennard 17.4 → 5.2, Jordan Goodwin 9.8 → 17.4 (forecast 23.4), Dylan Harper 19.7 → 25.0 (28.4), Tobias Harris 25.0 → 16.1 (19.5), Tre Johnson 5.5 → 10.3 (13.2), Ryan Dunn 5.2 → 9.8 (15.5), Will Riley 2.2 → 5.5 (8.6), Schröder 33.1 → 30.0 (13.0). Further away: Deandre Ayton 10.3 → 0.0 (15.6) and Harrison Barnes 16.1 → 19.7 (12.2).

### The 25 largest gaps before, with the cause (new ratings)

The "after" column is the new coach. "Team rank" is the player's overall rank on his own roster in the new ratings. Rosters include camp and two-way players.

Over the forecast:

| Player | Team | Basketball Index | Starting target | Before | After | Why he played too much |
|---|---|---:|---:|---:|---:|---|
| Dennis Schröder | CHA | 13.0 | 25.7 | 27.7 | 24.7 | Last season's minutes outrank his rating (new team). Only partly fixed: he is 1.4 points below Charlotte's line, so the penalty is small |
| Bruce Brown | NYK | 4.5 | 25.1 | 18.8 | 10.3 | Last season's minutes outrank his rating (new team) |
| Marcus Smart | HOU | 11.5 | 28.4 | 25.1 | 25.2 | Rated 4th-best on Houston |
| Ja Morant | POR | 19.5 | 28.4 | 32.6 | 32.6 | Rated 5th-best on Portland |
| Luke Kennard | PHX | 5.0 | 21.1 | 17.4 | 2.7 | Last season's minutes outrank his rating (new team) |
| Dejounte Murray | NOP | 19.6 | 25.7 | 31.9 | 31.9 | Rated 2nd-best on New Orleans |
| Kyle Anderson | TOR | 4.9 | 19.8 | 16.2 | 16.2 | Rated 9th-best on Toronto |
| De'Andre Hunter | SAC | 14.2 | 26.1 | 25.0 | 25.0 | Rated 9th-best |
| Peyton Watson | CLE | 19.5 | 30.7 | 30.1 | 30.1 | Rated 10th-best; big carried-over role |
| De'Anthony Melton | GSW | 5.7 | 22.5 | 16.0 | 16.0 | Rated 9th-best |
| Ebuka Okorie | DET | 5.5 | 12.0 | 15.7 | 15.6 | Rookie the game rates 9th-best |
| Isaiah Joe | DET | 19.5 | 22.0 | 28.0 | 28.1 | Rated 6th-best |
| Hannes Steinbach | CHA | 8.4 | 18.0 | 16.0 | 16.0 | Rookie with an 18-minute starting target |
| Aaron Gordon | DEN | 23.3 | 27.7 | 30.9 | 30.9 | Rated 3rd-best |
| Ivica Zubac | IND | 23.3 | 30.9 | 30.1 | 30.1 | Rated 3rd-best |
| Jalen Smith | CHI | 9.6 | 20.6 | 16.3 | 16.3 | Rated 2nd-best on Chicago |
| Kristaps Porziņģis | GSW | 23.4 | 23.7 | 30.0 | 30.0 | Rated 2nd-best |
| De'Aaron Fox | SAS | 30.3 | 31.5 | 36.9 | 36.9 | Rated 2nd-best |
| Brice Sensabaugh | UTA | 13.4 | 22.2 | 20.0 | 20.0 | Last season's minutes on the same team outrank his rating (incumbent, unchanged) |
| Cedric Coward | MEM | 29.1 | 26.1 | 35.7 | 35.7 | Rated 3rd-best |
| Ryan Rollins | MIL | 26.9 | 32.3 | 33.2 | 33.2 | Rated 4th-best |
| Jaren Jackson Jr. | UTA | 30.7 | 30.3 | 36.6 | 36.6 | Rated 2nd-best |
| Collin Sexton | LAL | 23.4 | 22.9 | 29.3 | 29.3 | Newcomer above the Lakers' line (52.5 against 50.5), so his carried-over role stands |
| Tre Jones | CHI | 25.2 | 26.8 | 31.1 | 31.1 | Rated 6th-best |
| Cam Spencer | MEM | 24.9 | 23.9 | 30.8 | 30.8 | Rated 5th-best |

Under the forecast:

| Player | Team | Basketball Index | Starting target | Before | After | Why he played too little |
|---|---|---:|---:|---:|---:|---|
| Sion James | CHA | 23.4 | 23.2 | 1.4 | 1.4 | Rated 20th on Charlotte (47.1) |
| Scotty Pippen Jr. | MEM | 23.4 | 21.2 | 2.1 | 2.1 | Low stamina rating (36) |
| Hugo González | BOS | 19.5 | 15.4 | 0.0 | 0.0 | Rated 13th |
| Keon Ellis | BKN | 23.4 | 18.9 | 4.3 | 4.3 | Edge of the rotation |
| Jahmai Mashack | MEM | 18.9 | 17.5 | 0.0 | 0.0 | Rated 22nd (33.3) |
| Nique Clifford | SAC | 28.1 | 23.1 | 10.3 | 10.3 | Rated 23rd (45.6) |
| Yaxel Lendeborg | GSW | 19.5 | 18.0 | 2.0 | 2.0 | Rated 18th |
| Drake Powell | BKN | 15.1 | 19.3 | 0.0 | 0.0 | Rated 20th |
| Patrick Williams | CHI | 14.8 | 19.5 | 0.0 | 0.0 | Rated 24th (41.4) |
| Trey Lyles | MIN | 14.8 | 1.0 | 0.0 | 1.1 | Starting data gives him 1.0 minute |
| Max Strus | LAC | 17.1 | 15.5 | 2.5 | 2.5 | Edge of the rotation |
| Jusuf Nurkić | UTA | 15.8 | 26.4 | 1.7 | 1.7 | Low stamina rating (34) |
| Gui Santos | GSW | 14.8 | 18.1 | 1.2 | 1.2 | Rated 12th |
| Ronald Holland II | DET | 23.4 | 20.4 | 9.9 | 9.9 | Edge of the rotation |
| Myron Gardner | MIA | 13.5 | 1.0 | 0.0 | 0.0 | Starting data gives him 1.0 minute |
| Danny Wolf | BKN | 17.8 | 20.6 | 4.9 | 4.9 | Rated 11th |
| Taurean Prince | DET | 14.2 | 20.8 | 1.4 | 0.0 | Low stamina rating (25) |
| Dailyn Swain | CHI | 17.5 | 12.0 | 5.5 | 5.5 | Rated 23rd |
| Pacôme Dadiet | NYK | 11.9 | 3.7 | 0.0 | 0.0 | Starting data gives him 3.7 minutes |
| AJ Green | MIL | 28.6 | 29.5 | 17.0 | 17.0 | Rated 25th on Milwaukee (38.3) |
| Yves Missi | NOP | 12.7 | 18.7 | 1.1 | 1.1 | Edge of the rotation |
| Precious Achiuwa | SAC | 16.8 | 22.2 | 5.3 | 5.3 | Rated 11th |
| KJ Simpson | CHA | 11.4 | 14.5 | 0.0 | 0.0 | Rated 22nd |
| Derik Queen | NOP | 27.3 | 25.4 | 16.2 | 17.2 | Edge of the rotation |
| Jordan Walsh | BOS | 12.0 | 17.3 | 1.2 | 1.2 | Rated 14th |

The full after-lists for both rating sets, and the older-ratings before-list, are in `output/rot-outliers/report-inputs.md` and `report-legacy.md`.

## Where the outliers come from

1. **Carried-over workload from another team.** This is the cause for Brown, Kennard and Schröder, and it is what this task fixes. The coach ranks players by last season's minutes plus 0.35 × overall + 0.26 × creation + 0.48 × stamina ([save.py:6734](../../../src/nba_gm_data/save.py#L6734)). It then gives out a fixed minutes curve (37, 34, … 2, 1) in that order ([save.py:6754](../../../src/nba_gm_data/save.py#L6754)). Last season's minutes are the starting `minutes_projection`, which is the player's 2025-26 minutes ([save.py:6834](../../../src/nba_gm_data/save.py#L6834), used at [save.py:6803](../../../src/nba_gm_data/save.py#L6803)). A 25-minute role is worth 25 priority points. A ten-point overall gap is worth only 3.5. Brown's 25.1 minutes came behind Denver's thin bench. That was enough to put him seventh in New York's order, ahead of Jose Alvarado (rated 53.5) and Landry Shamet (48.5), though New York's roster ranks him 18th (45.3). Kennard sat in the same spot in Phoenix. On average the game already matches Basketball Index for movers: 19.5 against 19.3 minutes. A flat newcomer discount would have pushed movers as a group too low, so I didn't use one.
2. **Ratings disagree with Basketball Index.** This covers most of the remaining over-list: Smart, Morant, Murray, Gordon, Fox, Porziņģis, Coward. The game rates them among their teams' best players, so the coach plays them. It also covers most of the under-list: Sion James, Clifford, AJ Green, Mashack, Patrick Williams. The new ratings rank these players at or near the bottom of their rosters. The coach follows the ratings. These belong to a ratings review, not to the coach.
3. **Low stamina ratings.** Pippen (36), Nurkić (34) and Prince (25) fall out of the order because stamina carries 0.48 per point.
4. **Missing starting minutes.** Lyles and Gardner have 1.0 minute in the starting data and Dadiet has 3.7. They have no carried-over role at all.
5. **Position slotting is not a cause.** The two-deep chart ([save.py:6664](../../../src/nba_gm_data/save.py#L6664)) now only guarantees each of its five starters 4 minutes ([save.py:6759](../../../src/nba_gm_data/save.py#L6759)). Brown and Kennard are not in either unit of their team's chart at all. Minutes by position already match Basketball Index on a typical team: guards 111 against 104, forwards and centers 78 against 78, centers 37 against 38. A positional penalty fitted the forecast worse in every version I tried.
6. **The coach's game model is not a cause either.** Played minutes track the coach's season plan within about 1–3 minutes. Starters run a little above plan from matchups and overtime ([sim.py:630](../../../src/nba_gm_data/sim.py#L630), stint lengths at [sim.py:683](../../../src/nba_gm_data/sim.py#L683)). Monthly reassessment blends 20% of the previous plan ([save.py:6811](../../../src/nba_gm_data/save.py#L6811)).

## What changed

`src/nba_gm_data/save.py` only (the role builder). `sim.py` is untouched.

- **`carried_workload_earned_elsewhere`** ([save.py:6713](../../../src/nba_gm_data/save.py#L6713)) checks the game's shipped career file (`data/research/player_career_stats.json`). It asks whether the player's carried-over minutes came with a different team. Those minutes are from the season before the game starts. Offseason signings and players traded during a career both count as newcomers. Generated players and rookies never count.
- **The newcomer talent line** in `ai_coach_workloads` ([save.py:6747](../../../src/nba_gm_data/save.py#L6747)) uses the coach's 13 leading candidates. Its line is the ninth-best overall among them, less two points. For each point a newcomer falls below that line, he loses two priority points. He can never lose more than his carried-over workload, so he cannot fall below where his ratings alone would put him. Newcomers above the line and all incumbents are ranked exactly as before.
- `reassess_ai_roles` passes the newcomer set ([save.py:6807](../../../src/nba_gm_data/save.py#L6807)). Human-controlled teams and teams with user rotation overrides are still skipped, so the user's rough minutes still drive their own team.
- Three tests in `tests/test_ai_roles.py`. A clearly weaker newcomer drops behind the regulars while the same player as an incumbent keeps his role. A newcomer within the margin keeps his place. The newcomer check reads the right team.

The constants are fitted to the forecast at the role-ordering level, not copied player by player. I tried a dozen nearby settings, and all of them produced the same pattern. I also tried applying the line to every player, not just newcomers. That fixed Brown and Kennard too, but it moved 44 players and sent 27 of them further from Basketball Index. It also benched real starters the new ratings rate around 38–39 (Bub Carrington, AJ Green, Nolan Traoré). I rejected it.

Determinism: the change alters AI roles, so seeded franchise games and box scores change. The game's random number streams are untouched. Speed: one dictionary lookup per player at each monthly role check. Season run times were unchanged (29–43 s per season on a loaded machine).

## Ratings questions for the coordinator (not changed here)

The coach now follows the ratings more for newcomers. The new ratings put these players far below the role Basketball Index expects:

- **Newcomers:** Bennedict Mathurin (NOP, 45.8, forecast 29.6), Tim Hardaway Jr. (MIA, 47.6, 26.7), Zaccharie Risacher (DAL, 46.8, 19.5).
- **Incumbents:** AJ Green (MIL, 38.3, 28.6), Bub Carrington (WAS, 39.3, 28.8), Nolan Traoré (BKN, 39.4, 19.5), Nique Clifford (SAC, 45.6, 28.1), Sion James (CHA, 47.1, 23.4), Jahmai Mashack (MEM, 33.3, 18.9).
- **Older ratings:** Kevin Porter Jr. (46.3, 31.4), Saddiq Bey (47.6, 32.8) and Brandin Podziemski (49.7, 34.0) look the same way.

If those ratings are right, the coach is right. If they're wrong, they need an evidence-based ratings fix, not a coach patch.

## Verification

- Focused tests: `tests.test_ai_roles` (17, including 3 new), plus the released-free-agent, rotation-comparison, rotation-profile and coaching-effects tests (50 in all). All pass.
- Core tests (`bash scripts/run_core_tests.sh`): 337 run, 2 skipped, all pass on the final code. The full suite was not run.
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): 18/18 in the new ratings and 18/18 in the older ratings, run on the final code. The output is identical to the earlier run: these replays use real minutes and never call the role builder.
- Betting-odds scorecard (`validate-season-probabilities --runs 100`, new ratings): Brier **0.1939**, log loss **0.5738**, spread error 4.655 and totals error 5.535 over 1,231 games (1,018 with market odds). That is identical to main. This tool is save-less and never calls the role builder.
