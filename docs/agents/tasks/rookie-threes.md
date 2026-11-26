# ROOKIE-THREES: drafted and generated players shoot and turn it over like real players of their type

Progress: 8/8 - done; ready for the coordinator's review

Owner: Claude (side session, worktree `rookie-threes-d319c7`, branch `claude/rookie-threes-d319c7`).

## TL;DR
- **Cause:** drafted and generated players took every habit except involvement from fixed hand-set guesses (three
  share .38 for any guard or wing; low ball-holding unless labelled a "creator"), while their skills come from the
  real players most like them. Generated guards and wings took 4-5 points fewer threes than real players of their type
  and, in Stage 2, turned it over about 16% less (real rookies turn it over MORE than veterans).
- **Fix (by rule, no real player touched):** every habit now comes from the 24 real players nearest him in ability,
  playing profile and position, like his skills. Season 1 is identical; both scorecards for today's engine unchanged.
- **Result:** today's engine no longer slides on threes (43.2 -> 43.9% vs 43.2 -> 42.9% before) but carries ~0.4 more
  turnovers and ~0.8 more points per 100 by season 4. Stage 2: turnovers and scoring now steady and at real levels
  (14.0 and 112.6 vs real 14.1 and 112.7); its three-point slide shrinks only by a fifth (cause below, outside scope).

## Four seasons, same seed (20261125, Miami), same code with and without the fix

| | Today's engine before | Today's engine after | Stage 2 before | Stage 2 after | Real |
|---|---|---|---|---|---|
| Share of shots from three, seasons 1-4 | .432 .442 .439 .429 | .432 .445 .440 .439 | .405 .401 .392 .385 | .405 .402 .397 .389 | .415 |
| Turnovers per 100 | 14.5 14.8 14.8 14.6 | 14.5 15.0 15.0 15.0 | 13.9 13.7 13.6 13.1 | 13.9 14.0 13.7 14.0 | 14.1 |
| Points per 100 | 115.5 115.3 115.3 115.5 | 115.5 115.4 115.9 116.3 | 112.9 113.4 113.4 114.0 | 112.9 113.0 113.0 112.6 | 112.7 |

Generated players against opening-day players, season 4 (share of shots from three / turnovers per play):
today's engine after .429 vs .444 / .131 vs .134; Stage 2 before .355 vs .394 / .105 vs .127; Stage 2 after
.377 vs .394 / .123 vs .127. By position (season 4, after) generated players match opening-day players within a
point or two except shooting guards (today .468 vs .504; Stage 2 .421 vs .469). By age, today's engine 19-22 year
olds: generated .434, opening-day .458 (5 players); 23-24: .438 vs .447.

Scorecards, today's engine (opening-day league unchanged by construction: no generated players until the first
rollover; Stage 2 season 1 checked identical across all 1,318 games): betting test (20 runs, 1,231 games, 1,018 with
odds) Brier .2016, log loss .5906, spread 4.03, totals 5.85, unchanged; real-stat targets 18/18.

## For the coordinator
1. **Today's engine turnovers +0.4 per 100 (15.0 vs real 14.1) and points +0.8 by season 4.** Generated players now
   turn it over like the players they replace, which is realistic, but today's engine was already above real. Worth a
   look at today's turnover level once a fuller league is generated, rather than holding rookies below real.
2. **Stage 2's remaining three-point slide is not generated players' habits.** Opening-day players' shot-weighted
   habit falls .396 -> .384 over four seasons (aging shooters lose shots; same in the baseline), which sits in Stage 2's
   usage and minutes code (`src/nba_gm_data/stage2/`, not touched). Generated players also skew to centers (23% of
   generated players, 24% of their minutes, vs ~16% in recent real drafts), mostly the real college prospects' listed
   positions (25% centers, 13% small forwards); worth about 0.4 points of league three share.
3. Generated bigs drive more than ability-matched real bigs because the draft generator gives them more rim pressure;
   the new rule follows that profile.
4. Display: generated shooters now show slightly higher shooting-range and release grades (the trait adapter reads the
   three share), the same mapping real players use.

## Tests
- New `tests/test_rookie_threes.py` (5 tests). Focused modules (input estimator, inputs evidence, five inputs, caches,
  ratings model, generated upside, prospects, rookie season/fit, rating parity, talent balance, hidden upside): pass.
- Full suite (`run_tests_parallel.py --all --workers 2`): 2,604 tests, 5 failures and 12 errors, the same set as on the
  unchanged code (missing reference files kept only in the main checkout's `output/`, interface tests, experimental
  engine tests, the known health-risk ranking test).
- Speed: about 18 ms per generated player, once per player; ~1.6 s one-time reference load per process.

## Objective
Newly drafted and generated players shoot fewer threes than the players who started in the league (today's engine 41%
of their shots against 44%; Stage 2 36-37% against 40%), so the league three-point share slides each season, and
turnovers drift down too. Find why, fix it by rule from evidence, and prove the league stays steady over four seasons
with both engines.

## Boundaries
May touch: draft and prospect generation, the generated-player and inputs build code (`input_estimator.py`,
`bbi_evidence.py`, `ratings_model.py` generated-player install), evidence docs, research scripts, tests, this file.
Not: `save.py`, `src/nba_gm_data/gui/`, `src/nba_gm_data/stage2/`, `docs/agents/BOARD.md`. No real player's ratings
change.

## Plan
1. Find where generated players' inputs come from. (done)
2. Compare with real rookie evidence. (done)
3. Fix by rule. (done: `input_estimator._generated_definition_inputs` habits from real neighbours; `bbi_evidence.map_tendency_inputs` skips generated T01/T17; tests `tests/test_rookie_threes.py`)
4. Four-season run, today's engine (Azure, seed 20261125, Miami).
5. Four-season run, Stage 2 (Azure, same seed).
6. Scorecards for today's engine (short betting test, calibration report; opening day should be unchanged).
7. Focused tests, full suite.
8. Report and commit.

## Findings
- Generated players = the draft classes from 2027 on (fictional and real-college prospects both take
  `input_estimator._generated_definition_inputs`). The 2026 class and everyone on opening day have measured inputs.
- Their skills and involvement (T08) come from the 24 nearest real players (ability, linked trait, position). Every
  other habit started from a fixed hand-set guess in `_tendency_inputs` (e.g. three share .38 for any guard or wing,
  .43 for a "shooter", .22 for a big; dribble persistence .38 unless "creator"), then a profile tilt.
- Earlier run (today's engine, season 4 save): generated vs their real neighbours: three share guards .400 vs .437,
  wings .383 vs .433, bigs .195 vs .229; midrange +.04; dribble persistence (T06) guards .478 vs .600.
- Turnovers: Stage 2's turnover rule on generated inputs is -0.18 log-odds below their real neighbours (pass choice,
  drive choice, dribble persistence, passing risk), matching the 17% fewer turnovers per play they commit in the run
  (.101-.107 vs .125-.127). Real young players turn it over MORE than veterans (2025-26: .135 vs .119 per play).
- Real evidence (ESPN career totals, `data/research/player_career_stats.json`): first- and second-year players' three
  share equals the league's (2023-24 .390 vs .389; 2024-25 .437 vs .414; 2025-26 .413 vs .415).

## Runs
- After (this branch): `output/rt/current_after` (laptop, log `output/rt/local_cur_after.log`), `output/rt/stage2_after`
  (Azure job `rt-s2-after`, log `output/rt/azure_s2_after.log`).
- Baseline (HEAD 21c499b6, clean worktree in the session scratchpad `rt-base`): Azure jobs `rt-cur-base`,
  `rt-s2-base`, fetched into that worktree's `output/rt/`; logs in this worktree's `output/rt/azure_*_base.log`.
- Season 1 has no generated players (the first 60 arrive at the first rollover), so season 1 must match the baseline
  exactly, and the opening-day scorecards cannot move.

## Results so far
- Stage 2, same seed, before -> after: turnovers per 100 13.9->13.1 vs 13.9->14.0 (real 14.1); points per 100
  112.9->114.0 vs 112.9->112.6 (real 112.7); three share .405->.385 vs .405->.389 (real .415). Generated players'
  three share season 4 .355 -> .377; their turnovers per play .105 -> .123 (opening-day .127).
- Today's engine after: three share .432/.445/.440/.439 (earlier older-code run .432/.439/.435/.428); turnovers 14.5->15.0.
  Generated vs opening-day by season 4: three share .429 vs .444, turnovers per play .131 vs .134. Same-code baseline
  (Azure job rt-cur-base) still running: needed to judge the small turnover/points creep.
- Season 1 identical with and without the fix (1,318 Stage 2 games). Scorecards (today's engine): betting test Brier
  .2016, log loss .5906, spread 4.03, totals 5.85 (unchanged); real-stat targets 18/18.
- Remaining Stage 2 slide: opening-day players' shot-weighted habit falls .396->.384 (who gets minutes; Stage 2 code),
  and generated classes carry more centers (23% vs ~16% in real drafts; mostly real college prospects' listed positions).

## Resume state
- To finish: read `output/rt/full_tests.log`; fetch `rt-base/output/rt/current_base` and run
  `rookie_threes.py league` on it vs `output/rt/current_after`; amend the report.
- Probes: `output/rt/probe.py` (shot mix by origin from a run's games log), `output/rt/tend_compare.py` (generated vs
  neighbours), `output/rt/real_rookies.py` (real evidence).
- Earlier runs to compare against: `../s2-multiseason-c06763/output/s2ms/current` and `.../stage2_local`.
