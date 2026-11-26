# S2-MULTISEASON: can Stage 2 run real seasons inside the game?

Progress: 8/8 - done; ready for the coordinator's review

Owner: Claude (side session, worktree `s2-multiseason-c06763`, branch `claude/s2-multiseason-c06763`).

## TL;DR
- **Yes, with one small bridge.** Stage 2 played four full seasons in a real save (regular season, play-in, playoffs,
  lottery, draft, re-signing, free agency, training camp, rollover), starting from the same fresh save as today's
  engine. It crashed once, in a late-season game where a team had only four available players. That cause sits in the
  season loop, and the bridge now fixes it on the Stage 2 path.
- **Stage 2 matches real 2025-26 better on league play**: points per 100 possessions 113.6 (real 112.7, today's engine
  115.5), true shooting .581 (real .581, today .590), overtime 4.1% (real 4.4%, today 2.3%, and today never goes past
  one overtime). Team records spread a little more realistically (wins spread 11.9 vs 10.8; real 13.6).
- **Stage 2's main gaps are player-level**: elite passers get far too few assists (Jokic 6-7 a game vs real 10.7),
  top stealers and shot-blockers run high, and the three-point share slides each season (40.7% to 38.5%; real 41.5%)
  because new players shoot fewer threes. Speed is about the same as today's engine (0-6 s more a month). Every
  season gets slower with either engine (25 s a month in season 1, about 41-48 s by seasons 3-4). The cause is the
  season loop, not the games.

## Objective and boundaries
Let a save's own season loop play its games with Stage 2 (test-only switch, today's engine by default), bridge
whatever Stage 2's result lacks on the season-loop side, run 3-5 seasons with each engine from a fresh save, and
compare them season by season. Not touched: GUI behaviour, ratings, `src/nba_gm_data/stage2/`, `scripts/research/`,
`docs/agents/BOARD.md`. Engine fixes inside Stage 2 are written up below, not made.

## What was built
- **Switch** (research only, invisible in the GUI): environment variable `NBA_GM_SAVE_ENGINE=stage2`
  (`sim.save_game_engine()`). Unset or empty means today's engine. Every game a save plays goes through
  `save.play_save_game` (daily games in `advance_save_day`; play-in and playoffs in `simulate_playoff_game`).
- **Byte-identical proof for normal play**: same seed (11, Miami, 20 Oct to 6 Nov, 121 games) run with the untouched
  last commit and with this change, switch unset. The save file and its game-history database match exactly. The only
  differences are random snapshot ids and a hash that includes the folder path (checked: the canonical data differs
  only in `_baseline_directory`). With the switch unset, `play_save_game` makes exactly the call the code made before.
- **Season-loop bridges** (Stage 2 path only, so normal play is untouched):
  1. `save.bridge_engine_result`: drop zero-minute lines (Stage 2 lists planned bench players who never got in; a line
     counts as a game played for season stats, the 65-game award rule and morale) and record overtime periods on the
     team lines (box score, game lists and history read them there).
  2. `sim.short_handed_recall` (generated games): when a team has fewer than five available players, the coach
     recalls the best healthy players he had rested or shut down, just enough to field five. Injured players stay out.
- **What the rest of the game reads from a result** (both engines now provide all of it): scores and team lines
  (records, standings, team logs, possessions, offensive rating, overtime periods); player lines (minutes, points,
  rebounds, assists, steals, blocks, turnovers, shooting, rim attempts, screen assists, starter flag, fouls,
  plus-minus) for season stats, game logs, awards and the 65-game rule, morale, social game-highs and playoff stats;
  minutes for post-game fatigue (`add_box_score_fatigue`). Injuries and development do not read the result: the health
  pass draws injuries before tip-off (the game only plays the exit), and development reads ratings, age and minutes.
- **Runner**: `scripts/s2_multiseason.py` (`run`, `compare`, `speed`). It drives a hands-off GM through every phase
  with the maintained season driver (`overnight_market_health.select_action`), pins the lottery draw, sets a nine-man
  minutes plan for Miami each season, logs every game and times every step. The old `ten_season_soak.py` loop no
  longer works on its own (it stops at the trade-deadline pause).
- **Tests**: `tests/test_save_engine_switch.py` (8 tests: default and switch, unchanged call for normal play, both
  bridges). Focused existing tests (41 modules touching the season loop, sim and Stage 2): 641 tests, 1 failure and 8
  errors, none from this change. The failure (`test_foundation` health-risk ranking) also fails on the untouched
  commit. The errors are experimental-engine tests that read reference files kept only in the main checkout's
  `output/`.

## Four seasons side by side (seed 20261125, Miami; every season in `s2-multiseason-tables.md`)
Averages of the four regular seasons.

| | Today's engine | Stage 2 | Real 2025-26 |
|---|---|---|---|
| Points per team game | 116.7 | 115.5 | 115.6 |
| Pace | 100.8 | 101.1 | 102.0 |
| Points per 100 possessions | 115.5 | 113.6 | 112.7 |
| Share of shots that are threes | .434 (steady) | .398 (.407 falling to .385) | .415 |
| Free-throw tries per shot | .290 | .274 | .264 |
| True shooting | .590 | .581 | .581 |
| Turnovers per 100 | 14.7 | 13.7 (14.1 falling to 13.4) | 14.1 |
| Assists per 100 | 27.1 | 25.8 | 26.1 |
| Steals / blocks per 100 | 8.3 / 4.9 | 8.0 / 5.0 | 8.2 / 4.7 |
| Fouls per 100 | 18.6 | 19.9 | 19.4 |
| Games to overtime | 2.3% (never two overtimes) | 4.1% (21 double, 2 triple, 2 quadruple) | 4.4% |
| Finishes by 1-3 / by 20+ | 17.7% / 19.9% | 17.6% / 16.8% | 14.4% / 22.8% |
| Spread of team wins (std. dev.) | 10.8 | 11.9 | 13.6 |
| Spread of point margin per game | 4.85 | 4.98 | 6.11 |
| Home win share | .560 | .548 | .555 |
| Players at 34+ minutes | 27 | 20 | 19 |
| Players at 30+ minutes | 77 | 108 | 80 |
| Players with 70+ games | 217 | 146 | 117 |
| Champions | TOR, OKC, CLE, OKC | OKC four times | |

Season by season (details in the tables file):
- **Stat leaders.** Assists in Stage 2: the leader averages 6.9-7.6 (Jokic 6.0-7.0); real Jokic 10.7, Cunningham 9.9;
  today's engine 9.1-10.3. Steals leaders 2.5 in Stage 2 vs real 2.0. Blocks: second- to fifth-best 2.3-3.3 in Stage 2
  vs real 1.7-1.9. Points and rebounds look right in both; Stage 2 stars score a bit more.
- **Impossible lines.** None in either engine (no made shots above attempts, points always add up, no seventh foul).
  Extremes: today's engine produces 9-12 steal games several times a season; Stage 2 has fewer, but its
  quadruple-overtime games give players 56-62 minutes.
- **Minutes and games.** Stars play star minutes in both (33-37 a game). Stage 2 has fewer heavy-minute players and
  more in the 30-34 band. Today's engine gives box-score lines to deep-bench players nearly every night (217 players
  with 70+ games vs 117 real). The user's minutes plan is respected about equally: top players within about 2 minutes
  of target in both, and bench players run 3-6 minutes over target in both (the coach model, not the engine).
- **Injuries.** Same counts in both (1,068-1,316 a season, 6,000-8,600 expected games missed), because the health
  model draws them before the game.
- **Development and ratings drift.** Practically identical by age group in both engines every season (22 and under
  about +1.7 to +3.2 a season, 32 and over about -2.5); the league's rating spread stays put.
- **Playoffs.** Complete every season in both; scoring 114-116 a team in Stage 2 vs 115-120 today.
- **Crashes.** Today's engine: none. Stage 2: one (fixed by the bridge, see below). One Azure attempt was killed by the
  machine during season 3, most likely for memory; the laptop rerun used 1.4-3.5 GB and finished.

## Speed (a month of games with AI front offices)
Measured on the same season-start saves, one engine after the other, on a quiet laptop:

| Season start | Today's engine | Stage 2 |
|---|---|---|
| 2026 (fresh save) | 25.6 s per 30 days | 26.8 s |
| 2027 | 35.4 s | 41.6 s |
| 2028 | 48.1 s | 46.2 s |
| 2029 | 40.5 s | 41.0 s |

The engine choice barely matters. The month gets slower each season with both. A profile of a season-3 month:
about 70% of the time goes to rebuilding the league from the save once per simulated day (`canonical_with_save`,
about 1 s a call, mostly re-fitting the ratings model in `install_inputs_model` and re-estimating every player's role
in `assign_estimated_roles`). The games themselves are about 20%. Meanwhile the save keeps growing: injury records
pile up across seasons (1,162 after one season, 5,207 after four), retired players stay in the data (41 to 201), and
the file grows from 12 MB to 28 MB. Even the season-1 month is over the 10-20 s budget on this laptop.

## Breaks and oddities
Fixed here (season-loop wiring):
1. Zero-minute box-score lines would have counted as games played (bridge 1).
2. Overtime periods were missing from Stage 2's team lines (bridge 1).
3. A team with four available players crashed Stage 2 (`IndexError` in `stage2/game.py` `_refresh`, SAC v DAL on
   10 Apr 2028; kept in `output/s2ms/stage2_crashed_run1`). Fixed by bridge 2.

For the coordinator, season loop (affects both engines; not changed here because it would change normal play):
4. **No eight-player floor on rest shutdowns.** Late in the season, teams out of the race shut healthy veterans down
   (`health.py`, `rest_shutdown`); with injuries that leaves 4-7 available players. Today's engine played 14
   team-games with 5-7 players in under two seasons, and plays four-man games when it happens. The NBA requires eight.
   Suggested fix: the rest and shutdown decisions keep at least eight healthy players available.
5. **Each season is slower than the last** (see Speed): a full league rebuild every day, plus save data that is never
   pruned (injury events, retired players).
6. **The old soak script** (`ten_season_soak.py` run loop) stops at the trade-deadline pause, and its audit flags stale
   "errors", already at the fresh save: two-way and camp players counted as orphans, and an award list expecting only
   MVP, DPOY and ROTY. `scripts/s2_multiseason.py` uses the maintained driver instead.
7. **New players shoot fewer threes than existing ones** in both engines (Stage 2: 36-37% of their shots vs 40% for
   the original players; today's engine: 41% vs 44%). Today's engine hides it; Stage 2 doesn't, so its league
   three-point share falls every season. Probably how draft and generated players' inputs are built (Track B).
8. **Azure worker:** my failed uploads left two machines on (since fixed by AZURE-WORKER-FIX, `deb76c20`). There is
   still no way to re-attach to a running job after the laptop loses its connection; I used a small script that
   reuses `azure_worker`'s own wait, fetch and switch-off functions.

For the coordinator, Stage 2 engine (`src/nba_gm_data/stage2/`, not touched):
9. **Elite passers' assists are far too low.** Per 36 minutes in season 1: Jokic 6.5 (real 11.1), Cunningham 7.5
   (10.5), Doncic 5.9 (8.3), Giddey 7.4 (10.3), Ball 6.4 (9.2). Today's engine is close to real for all of them. The
   league total is about right (25.8 vs 26.1 per 100), so assists are spread too evenly across teammates.
10. **Top stealers and shot-blockers are too high.** Gilgeous-Alexander 2.4 steals per 36 (real 1.5), Daniels 2.9
    (2.1); the second- to fifth-best blockers average 2.3-3.3 a game vs real 1.7-1.9.
11. **Turnovers drift down** across seasons (14.1 to 13.4 per 100), alongside the three-point slide (item 7).
12. **The lineup code assumes five players**: Stage 2 crashes rather than playing short-handed (bridged here; the
    engine could guard it itself).
13. **In-game injury exits** only trigger once a player reaches the planned share of his minutes
    (`stage2/coach.py`). A player who plays less than planned never leaves the game hurt: about 15% fewer labelled
    exits than today's engine. The injury itself still counts.
14. **Quadruple overtime twice in four seasons** (real: a few per decade). Small sample; worth watching alongside the
    S2-LAST-POSSESSION work.

## Files
- `src/nba_gm_data/sim.py`: `SAVE_ENGINE_ENV`, `save_game_engine()`, `short_handed_recall()` (Stage 2 branch only).
- `src/nba_gm_data/save.py`: `play_save_game()`, `bridge_engine_result()`, the two game calls.
- `scripts/s2_multiseason.py`, `tests/test_save_engine_switch.py`, this file, `s2-multiseason-tables.md`.
- Run outputs (git-ignored): `output/s2ms/current` and `output/s2ms/stage2_local` (the four-season runs),
  `output/s2ms/stage2` (two Azure seasons), `output/s2ms/stage2_crashed_run1`, `output/s2ms/speed/speed.json`.

## Reproduce
```
PYTHONPATH=src:scripts .venv/bin/python scripts/s2_multiseason.py run --engine current --seasons 4 --out output/s2ms/current
PYTHONPATH=src:scripts .venv/bin/python scripts/s2_multiseason.py run --engine stage2 --seasons 4 --out output/s2ms/stage2_local
PYTHONPATH=src:scripts .venv/bin/python scripts/s2_multiseason.py compare output/s2ms/current output/s2ms/stage2_local --out output/s2ms/comparison.md
PYTHONPATH=src:scripts .venv/bin/python scripts/s2_multiseason.py speed output/s2ms/current --out output/s2ms/speed
```
About 60-75 minutes per four-season run on the laptop (one heavy job).
