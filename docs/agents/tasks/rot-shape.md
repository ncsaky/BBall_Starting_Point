# AI coach rotation shape

## TL;DR

Stars rose from 28.32 to 33.48 minutes per game. Back-of-rotation players fell from 21.97 to 9.72. All four role averages landed within one minute of Basketball Index across two healthy seasons.  
The old coach reserved a large shift for a dedicated backup at each position. The new coach shares minutes across positions and gives the end of the bench shorter shifts.  
Every team accounted for 240 regulation minutes plus overtime. The player ratings and Basketball Index source data were untouched.

## How I measured it

I ran the regular-season game path headlessly for all 30 AI-controlled teams on the canonical 2026–27 rosters and generated career schedule, using seeds 17 and 29. That is 1,230 games per seed and 82 per team. Rosters and ratings stayed fixed so trades and player development could not change the comparison. The primary runs kept availability healthy to match Basketball Index's healthy-rotation forecast. A separate diagnostic turned the game's injury and return model back on.

I matched the 329 players by canonical player ID, including players whose team abbreviations differed across the two sources, such as PHO and PHX. I averaged each player's minutes over games played, then gave each player and seed equal weight in the role averages. A player with no simulated appearance has no observed minutes per game. The role counts show how often that affected the comparison. The two Basketball Index players labeled Bench are outside the four requested groups.

## Before and after

| Role | Basketball Index healthy minutes | Starting game target | Before, played | After, played | After difference | Players who appeared, before → after |
|---|---:|---:|---:|---:|---:|---:|
| Star | 34.33 | 32.17 | 28.32 | **33.48** | −0.85 | 52 → 58 of 58 |
| Starter | 29.30 | 28.95 | 26.35 | **29.12** | −0.18 | 72 → 85 of 85 |
| Key | 21.42 | 24.18 | 24.69 | **20.68** | −0.74 | 44 → 72 of 74 |
| Rot | 10.16 | 17.58 | 21.97 | **9.72** | −0.44 | 51 → 82 of 110 |

Using only the players who appeared after the change, the largest gap is 0.97 minutes for the Rot group. The mean within-player game-to-game spread rose from 0.51–0.56 to 2.21–2.82 minutes across the four groups, measured as standard deviation. Both seeds passed the role targets individually. On the same-player sample restricted to players who appeared both before and after, all four groups also landed within one minute of their Basketball Index comparison.

| Player | Basketball Index healthy minutes | Starting game target | Before, played | After, played |
|---|---:|---:|---:|---:|
| Bruce Brown, NYK | 4.54 | 25.10 | 0 appearances | 19.92 |
| Mitchell Robinson, BOS | 4.58 | 19.20 | 26.00 | 5.08 |
| Luke Kennard, PHX | 5.02 | 21.10 | 17.42 | 17.42 |
| Jordan Poole, NOP | 8.19 | 24.50 | 25.18 | 10.23 |

Brown and Kennard remain well above the reference. The target is league-wide role shape, and the coach uses the same rule for every player.

## Where the flatness came from

- The starting `minutes_projection` correlated 0.808 with Basketball Index. In the starting data, stars averaged 2.16 fewer minutes and back-of-rotation players 7.42 more than the reference. The coach then amplified the problem for reserves who appeared. The old role builder divided 48 minutes between two assigned players at each of five positions, starting each split at 24–24. It guaranteed the selected backup at least 12 minutes even behind a much stronger starter. Role reassessment blended the result with the previous healthy targets. [save.py:1044](../../../src/nba_gm_data/save.py#L1044), [save.py:6558](../../../src/nba_gm_data/save.py#L6558) and [save.py:6593](../../../src/nba_gm_data/save.py#L6593).
- In the healthy baseline, actual minutes per game were within 0.31 minutes of the coach's average game targets in each role. With injuries enabled, the old coach still averaged 30.14 minutes for stars and 21.42 for the back of the rotation. The large gaps were already present before the game began. The matchup adjustments and overtime accounted for the small remaining differences. [sim.py:585](../../../src/nba_gm_data/sim.py#L585), [sim.py:647](../../../src/nba_gm_data/sim.py#L647) and [sim.py:1835](../../../src/nba_gm_data/sim.py#L1835).
- Injuries remove unavailable players and can briefly reduce a returning player's workload. Fatigue itself changes in-game performance and injury risk. Personal fouls are assigned after minutes and scoring have been decided, and the current game path has no substitution step driven by a blowout. [health.py:547](../../../src/nba_gm_data/health.py#L547), [sim.py:616](../../../src/nba_gm_data/sim.py#L616), [sim.py:1006](../../../src/nba_gm_data/sim.py#L1006) and [sim.py:550](../../../src/nba_gm_data/sim.py#L550).

## What happens when players are out

| Role | Before, injuries enabled | After, injuries enabled | After, healthy |
|---|---:|---:|---:|
| Star | 30.14 | 35.98 | 33.48 |
| Starter | 28.53 | 33.00 | 29.12 |
| Key | 22.90 | 25.42 | 20.68 |
| Rot | 21.42 | 13.91 | 9.72 |

The game redistributes vacated minutes to available teammates. That brings the back of the rotation much closer to the healthy reference even in seasons with injuries, with a remaining 3.75-minute gap. Key players also carry about four additional minutes per appearance compared with the healthy forecast. All teams still accounted for their regulation and overtime minutes. In the older ratings mode, the healthy averages also landed within one minute of the reference for each role.

## What changed

The AI coach ranks the healthy roster using existing workload context, current overall ability, shot creation and stamina. The initial workload matters less as the career moves away from the original roster snapshot. The workload-neutral ratings view now retains the save's active ratings model. The coach uses the two-deep depth chart to keep options at each position and uses a single team-wide minutes schedule to allocate playing time. That gives the lead players full starter workloads, gives regular reserves mid-length shifts and gives the end of the rotation short shifts. The game carries forward a portion of the previous plan when the coach reassesses roles. [Coach workload model](../../../src/nba_gm_data/save.py#L6571) and [rotation projection](../../../src/nba_gm_data/save.py#L6692).

The game varies shift lengths by team, game and seed around the available roster's targets. Those targets still come from the GM's instructions for human teams. The minutes balance to 240 in regulation and add 25 per overtime period. The separate rotation random draw leaves the game random number generator's setup intact. New workloads can change the outcome and box score of a seeded franchise game. The real-minutes replay follows its existing path. [Daily variation](../../../src/nba_gm_data/sim.py#L632).

## Verification

- Focused tests passed (48). Core tests passed (334 run, 2 skipped). The full suite is still running.
- The final inputs-mode real-minutes replay passed 18 of 18 statistical checks across 1,230 games.
- The inputs-mode odds replay ran 100 simulations per game across 1,231 games (1,018 with market odds). Brier was **0.1955** (limit 0.1960) and log loss was **0.5786** (limit 0.5790). The full run started during baseline measurement. On the final code, the first 12 games matched the full run exactly, including player results.
- For a 219-game November headless run with day-by-day cache resets, CPU time was 3.55 seconds before and 3.64 after. This measures game simulation and rotation work.
- The local harness and logs are in `output/rot-shape/`. The harness reads the Basketball Index file only for analysis.
