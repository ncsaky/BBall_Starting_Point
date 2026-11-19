# Heavy minutes: why the AI coaches overplayed their starters, and the fix

## TL;DR

- Two things caused it. When a player was out, the coach spread his minutes across the team in proportion to how much each player already played, so the other starters climbed toward 38-40 minutes. And nothing in a game reacted to the score: starters played the same minutes in a 30-point blowout as in a one-point game.
- The coach now gives an absent player's minutes mostly to the bench, rests regulars in blowouts, and reacts to foul trouble. All three are fitted to real 2025-26 box scores.
- Over a full season, the count of players averaging 34+ minutes fell from 84-95 to 12-20 (real: 18), and 30+ fell from 145-156 to 64-70 (real: 70). The most minutes per game fell from about 40 to about 36 (real: 38). Both scorecards are unchanged.

## How I measured it

Real data: the 1,235 regular-season 2025-26 box scores in `data/research/game_boxscores_2025_26.json` (minutes, starters, fouls, final score, who did not play). Simulated data: a headless regular season with all 30 teams AI-coached, injuries on, and fixed opening rosters, so trades cannot muddy the comparison. I used seeds 17 and 29 in both rating sets (`output/heavy-minutes/sim_season.py`, about 45 s per season). The same analysis code reads both sources (`output/heavy-minutes/analyze.py`). I also confirmed the result through the real app path, with trades and AI front offices, for one 94-input season (`scripts/two_season_league_probe.py`).

The comparisons use "regulars": players averaging 28+ minutes over 40+ games. That group has 102 players in real 2025-26.

## Answers to the research questions

**1. Minutes per game, games played, or both?** Mostly minutes per game when playing. Both sides have about the same number of players who qualify with 40+ games: 365 real and 359-383 simulated. The simulated stars do play more games than real stars. The 30 highest-rated players played 66-70 games in the sim versus 55 in real life, and the median 30-minute player played 73 games versus 68. That affects season totals, not minutes per game. It belongs to the injury model, which I did not change.

**2. Blowouts.** Real regulars play 1.5 minutes above their own average in games decided by 0-5 points and 3.8 below it in games decided by 21+. That is 5.3 fewer minutes in a blowout than in a close game. Wins and losses look alike. About 1 game in 5 ends 21+ apart. The old sim had no relationship at all: within ±0.3 minutes in every bucket. The sim also produces somewhat more blowouts than real life, 24-27% of games at 21+ versus 21%. That comes from the scoring engine and adds only about 0.2 minutes of extra rest per regular.

**3. When a starter is out.** In real games where one of a team's two biggest minute-getters sat, the other three starters played only **1.2** more minutes each, and the bench took the rest. The old sim gave them **3.3-3.7** more. In the old code, the AI coach's projection scaled every available player up in proportion to his minutes, with caps of 34-40 for the top five (`save.py` `team_rotation_projection` → `bounded_minutes_allocation`, `rotation_rank_cap`). The game's `normalize_minutes` also rescales in proportion. Basketball Index's own minutes model says the same as the real data: stars gain only 0.7 minutes per game over a season from teammates' injuries, while bench players gain 6.

**4. Foul trouble, in-game injuries, fatigue and back-to-backs, overtime.**
- Foul trouble: real regulars foul out in 1.6% of games, and fouling out costs about 2 minutes against a comparable game. The old sim assigned fouls after minutes were decided, so fouls never changed minutes. Regulars also fouled out in **6.6-7.5%** of games, because six fouls came from a plain random count with no coach reacting.
- Injury in the middle of a game: in 0.9% of real regulars' close games, the player leaves with under half his usual minutes. The sim had almost none. The injury model draws an injury from the minutes a player plays in a game, but it then kept him out of that same game and counted it as missed (`health.py` `simulate_health`).
- Back-to-backs: no real effect on minutes when the player plays (+1.4 versus +1.2). Coaches rest a player by sitting him for the whole game, and the sim already does the same.
- Overtime: 4.4% of real games versus 2-3% in the sim. Too rare to matter.

**5. Structure: the code path from depth chart to box score.** `save.py` `reassess_ai_roles` → `ai_coach_workloads` builds a healthy plan from a fixed curve (37, 34, 32, 30, 28, 25, 20, ...) for a player's minutes when the whole roster is healthy. Then `apply_save_rotation_projection` → `team_rotation_projection` gives each game day's available players their minutes; the absence redistribution happened here. In the game, `sim.py` `game_player_pool` takes those minutes, and `sandbox_health_adjusted_pool` removes injured players. Then come `matchup_adjusted_player_pool`, `return_ramped_player_pool`, `game_day_rotation` (±5 minutes of random variation, renormalized to 240), `simulate_team_line` (score, then player lines in proportion to minutes), overtime, and finally fouls. The season totals are a plain sum of the box scores, so nothing went wrong there.

The rotation-shape task (ROT-SHAPE) and the as-played numbers disagreed for a simple reason. ROT-SHAPE fitted the healthy plan to Basketball Index's "healthy rotation" minutes. Basketball Index defines those as minutes with everyone healthy and before garbage time, which is what a player plays in a close game. Its own as-played projection is about 2 minutes lower for stars (34.3 healthy versus 32.2 as played). The game never took that step from close-game minutes down to as-played minutes.

**Causes ranked** (94-input ratings, seed 17; 88 players at 34+ before, 18 real, so 70 too many):

| Cause | Players at 34+ explained | Players at 30+ explained (83 too many) |
|---|---:|---:|
| 1. Absent players' minutes spread in proportion to minutes | 55 | 54 |
| 2. No blowout rest | ~14 | ~28 |
| 3. Foul trouble ignored (plus far too many foul-outs) | ~2-6 | ~3-7 |
| 4. Injuries never happen during a game | small (about 0.15 minutes per game) | small |
| 5. More blowouts in the sim's scoring | about 0.2 minutes per game, in the other direction (more rest) | |

## What changed

1. **Absent players' minutes go mostly to the bench** (`save.py` `spread_vacated_minutes`, AI teams only, inside `team_rotation_projection`). Each available player's share of the missing minutes is weighted by his healthy role: a 34+ minute starter gets weight 0.6, a 28-minute player 1.2, a 20-minute player 3.5, and a 14-or-fewer-minute reserve 6. Nobody passes 42. A healthy roster is unchanged.
2. **The coach manages minutes during the game** (new `game_minutes.py`, called from `sim.py` for generated games only). Both final scores are drawn first, and the coach then adjusts the minutes:
   - *Blowout rest:* the final margin sets the length of garbage time: none up to 5 points, 0.7 minutes at 10, 1.8 at 15, 4.0 at 20, 6.2 at 30 and 8.5 at 40, varied ±40% per game. Players who play the most minutes sit for nearly all of it. Bench players and up to four healthy reserves outside the rotation play it. The curve was fitted so regulars' minutes by margin match the real ones.
   - *Foul trouble:* each player's fouls happen at points in his minutes (same league foul rate as before, slightly lower once he has four or five fouls). A player whose 2nd to 5th foul comes ahead of pace sits for part of his remaining minutes. A sixth foul ends his game, and he does not return in overtime. His box-score fouls are the ones he committed in the minutes he actually played.
   - Points and the other box-score counts are then shared out over the minutes actually played, so starters score less in blowouts.
3. Every team still plays exactly 240 regulation minutes, plus 25 per overtime. The GM's rough minutes for a human team still set the plan; the coach varies around them during the game. The experimental possession engine was not touched.
Determinism: everything is seeded. Generated-game results change: scores, box scores, and the order of the two score draws. **The real-minutes replay and the betting-odds replay are byte-identical** (40-game hash check). Both scorecards are therefore unchanged.

## Before and after

**Season minutes** (players with 40+ games):

| Season | 30+ min | 34+ min | 32+ min | Top-30 average | Most | 30 top-rated players' average |
|---|---:|---:|---:|---:|---:|---:|
| Real 2025-26 | 70 | 18 | 43 | 34.6 | 38.0 | 31.8 |
| 94-input, seed 17: before → after | 153 → **64** | 88 → **13** | 125 → 30 | 37.8 → **33.7** | 40.2 → **35.3** | 36.2 → **31.5** |
| 94-input, seed 29 | 145 → **67** | 84 → **15** | 118 → 34 | 37.9 → **34.1** | 39.2 → **36.0** | 35.5 → **31.4** |
| Older ratings, seed 17 | 156 → **68** | 95 → **14** | 128 → 33 | 38.2 → **33.9** | 40.1 → **35.7** | 37.5 → **32.6** |
| Older ratings, seed 29 | 149 → **70** | 87 → **20** | 124 → 37 | 38.3 → **34.3** | 40.1 → **35.9** | 37.2 → **32.6** |
| Full app path, 94-input, 2026-27 (trades on) | 150 → **68** | 84 → **12** | — → 30 | — → **33.7** | 40.5 → **35.6** | |

The real count of 70 comes from this box-score file. The readiness report's 71 used rounded season totals.

**Regulars' minutes by final margin** (difference from their own season average; games without overtime):

| Final margin | Real | Before | After (94-input s17 / s29 / older s17) |
|---|---:|---:|---|
| 0-5 | +1.5 | −0.1 | +2.0 / +1.8 / +2.0 |
| 6-10 | +1.1 | −0.3 | +1.6 / +1.5 / +1.6 |
| 11-15 | +0.3 | +0.1 | +0.6 / +0.6 / +0.9 |
| 16-20 | −1.4 | −0.2 | −0.8 / −1.2 / −0.7 |
| 21+ | −3.8 | 0.0 | −3.5 / −3.4 / −3.5 |
| Close minus blowout | 5.3 | ~0 | 5.5 / 5.2 / 5.5 |
| Share of games 21+ | 21% | 25% | 26% / 24% / 27% |

**Other coach behavior:**

| | Real | Before | After |
|---|---:|---:|---:|
| Other starters' gain when a top-two player is out | +1.2 | +3.3 to +3.7 | +0.8 to +1.1 |
| Regulars' foul-out rate | 1.6% | 6.6-7.5% | 1.7-1.8% |
| Regulars' fouls per game | 2.30 | 2.70-2.77 | 2.46-2.49 |
| Game-to-game spread of a regular's minutes (SD) | 5.2 | 3.9 | 3.9 (injuries on); healthy 2.8 → 3.8 |
| Regulars' season average | 31.7 | 34.0-34.3 | 31.0-31.4 |

**Rotation-shape role groups** (Basketball Index groups, 94-input seed 17). The healthy plan is unchanged. Close games now match Basketball Index's healthy minutes, and season averages are near its as-played projection:

| Role | Basketball Index healthy | Basketball Index as-played | Before, played | After, played | After, close games |
|---|---:|---:|---:|---:|---:|
| Star | 34.3 | 32.2 | 36.0 | 31.5 | 33.7 |
| Starter | 29.3 | 29.2 | 32.9 | 28.2 | 29.8 |
| Key | 21.5 | 23.1 | 25.4 | 22.6 | 23.5 |
| Rot | 10.2 | 18.5 | 13.9 | 13.3 | 15.1 |

In a healthy season, close-game minutes moved by at most 0.4 from before (star 33.4 → 33.0, starter 29.0 → 28.8). That 0.4 is foul trouble.

## Scorecards

- Real-minutes replay, 94-input (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**. Identical to before, since replay games are byte-identical.
- Betting-odds test, 94-input, 100 runs (`validate-season-probabilities`): **Brier 0.1941, log loss 0.5744**, spread error 4.546, totals error 5.465 (1,231 games, 1,018 with market odds). Identical to main.

## Speed

Generated games cost about 3.5 ms more each (game-sim CPU 22.5 → 26.3 s per 1,230-game season, mostly from extra players in the box score). That is about 1 extra second of CPU in a simulated month (~220 games) whose total is 30-35 s on main with AI front-office activity. The app-path months in the one-season check took 34-43 s wall while four other jobs ran on the machine.

## Tests

- New `tests/test_game_minutes.py` (10 tests): garbage-time curve, 240-minute totals, regulars resting in blowouts, reserves entering, foul-outs and foul counts, absence shares, and sandbox-game accounting and determinism.
- Rotation/minutes/box modules: `test_rotation_profile_calibration`, `test_coaching_effects`, `test_box_star_stats`, `test_box_variation`, `test_rotation_comparison_*`, `test_narrative_simulation`, `test_forward_tuning`, `test_calibration_targets`: 54 OK. `test_ai_roles` OK; it caught a short-handed-team case that the 42-minute ceiling now handles.
- Core suite `scripts/run_core_tests.sh`: 337 run, OK (2 skipped), on the final code.

## What's left / decisions for the user

1. **The top end is a little compressed.** No player now averages 36+ (real: 3), and the most is about 36 (real: 38). The healthy plan gives every team's top player the same 37 minutes, while real coaches vary (some ride a star for 38-40). A coach-specific "how hard do I ride my stars" trait would fix it. That is a rotation-plan change (ROT-SHAPE territory), not in-game behavior.
2. **The human team's coach** still spreads an absent player's minutes the old way (in proportion to the GM's targets). The in-game blowout and foul behavior already applies to it. **Decision:** should the bench-first absence rule also apply to the user's team, or should the GM's targets be followed literally when someone is out?
3. **Sim stars play more games than real ones** (66-70 versus 55 for the top 30). That belongs to the injury and rest model (for example, real teams rest stars on purpose); it is a separate task.
4. **Injuries never happen during a game.** The injury model draws an injury from the minutes a player plays in a game, but then keeps him out of that same game and counts it as missed. Real regulars leave early in about 0.9% of close games. Letting the hurt player play part of that game would add realism, but changes the minutes total by only about 0.15 per game. It means changing the injury model's game counting (`health.py`), so I left it for a separate small task.
5. Overtime is too rare (2-3% versus 4.4%), and blowouts are slightly too common (25% versus 21% at 21+). Both come from the scoring engine, and the odds scorecard governs them, so I left them alone.

## Resume state

- Done: research, fix, both-seed and both-rating-set seasons, app-path season check, focused tests, replay identity, calibration 18/18, odds test, core suite.
- Final checks rerun one at a time after the machine restart: betting-odds test identical to main; core suite OK. Ready for coordinator review.
- Harness and logs: `output/heavy-minutes/` (`sim_season.py`, `analyze.py`, `roles.py`, `cmp.py`; `base/` is a copy of the pre-change engine for baseline runs).
