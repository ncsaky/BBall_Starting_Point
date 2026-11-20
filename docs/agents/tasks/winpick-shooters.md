# WINPICK-SHOOTERS: who scores can no longer change who wins; spot-up shooters back to their real efficiency

_Claude (Opus agent), 2026-11-19, branch `worktree-agent-adee91da0ea062141`. Rules 1, 4, 7 and 9 apply. No player rating was changed. The experimental possession engine was not touched._

**TL;DR**
- The small betting-test loss after the last task was not the new points formula picking worse winners: the box score and the away team's score shared one stream of random numbers, so changing who scores handed the away team different dice. Both scores are now drawn first and overtime has its own dice; proven: changing who scores now leaves every score identical.
- The pace habit costs nothing in win-picking once the dice are separated (Brier change -0.00004 and -0.00007, smaller than its own error bar) and still improves game totals. Seeds 1 and 7 share 94 of their 100 runs, so they were not two independent confirmations. **Target not met:** the 100-run test now reads Brier 0.1974 (market 0.1962) on a fresh deal of the dice; about 0.0012 of that is the test's own sampling noise. The real lever is that the engine's game-to-game swings in expected margin are 1.7x the market's (measured, not changed here).
- Spot-up shooters now score at their real efficiency: the group's true shooting .562 -> .581 (real .583); AJ Green .519 -> .642 (real .627), Nicolas Batum .420 -> .609 (.603). Tough-shot creators keep their fix (Ingram .583, real .573). Real-stat scorecard 18/18; speed unchanged.

## Resume state

Done; ready for review. Commits on this branch: a checkpoint (stream fix + shooter changes + tests) and a final commit (strength-scale experiment hook, report, board row). Not pushed or merged. Scratch scripts and outputs: `output/winpick-shooters/` (git-ignored, a real folder in this worktree; copy it to main's `output/` before removing the worktree). Key scripts: `odds_dump.py` (the betting test with per-game output and switches), `compare_odds.py` (paired per-game comparison with error bars), `compare_scores.py` / `order_check.py` (exact-score and draw-order checks), `noise_floor.py` (sampling noise of the test), `margin_decomp.py`, `calib_slope.py`, `standings_spread.py` (where the engine's win chances are too confident), `eval_variants.py` (3-seed replays with per-player tables), `shooter_diag.py`, `stage_diag.py`, `three_diag.py` (where shooters lost efficiency), `fit_shooter_points.py`, `t02_check.py` (the points fit). `head_src/` is a copy of the committed engine for before/after runs and `ctrl_src/` the same with only the away team's dice re-dealt (both need the `data` symlink next to them). `invalid_copied_src/` holds a first batch that ran without game data (discarded; see "What went wrong"). Worktree data symlinks (`.venv`, Barttorvik, sqlite, injury evidence, Basketball Index files, `output/*` links) are untracked and were not committed.

## 1. The mechanism

**How a replayed game was drawn (before).** One random stream per game: the home team's possessions and offensive rating (2 numbers), then the home box score (who scores, shooting lines, rebounds: a varying count of random numbers), then the away team's possessions and rating, then the away box score, then overtime if tied.

So anything that changes how many random numbers the home box score uses (a different points split, a different points total) moves the away team onto different random numbers. That is a reshuffle, not a change in what the engine believes about the teams. Overtime also continued the same stream after both box scores, so a tied game's winner depended on the box scores.

**Proof, controlled runs (same seed, change one thing; 40 games x 20 runs = 800 games):**

| Change | Home score identical | Away score identical | Same winner |
|---|---|---|---|
| Old engine: old points formula vs new | 99.1% (only overtime games differ) | 83.2% | 94.6% |
| Old engine: pace habit on vs off | 22.9% | 22.6% | 97.1% |
| New engine: old points formula vs new | **100%** | **100%** | **100%** |
| New engine: pace habit on vs off | 23.0% | 23.0% | 99.4% |

With the fix, the points formula changes no score at all. The pace habit legitimately changes scores (that is its job), and now flips 0.6% of winners (more or fewer possessions with the same luck) instead of 2.9%.

**Other paths checked (none feed back into results):**
- Fouls, box-score texture (misses, rebounds), plus-minus and screen assists each already had their own seeded stream, and none changes the points.
- The final box-score reconciliation recomputes team totals from player lines, but points always sum to the drawn score.
- The betting test replays each game with real minutes, seeded per game and run, so no fatigue or injury carries between games. In normal gameplay, later games read minutes played (fatigue) and injuries, not who scored.
- Did moving the away draw change anything on average? 60 games x 200 runs, old vs new order: average margin difference +0.16 of its error bar (0.13), average within-game margin spread 14.71 vs 14.70. No.

**The fix (`sim.sim_game_with_context`, `sim.draw_both_scores`).** Replayed games now draw both scores first, as generated games already did; the game's first four random numbers set both scores, and the rest of that stream only splits points between players. Overtime has its own stream (`seed:game:mode:overtime`) in both modes. Effect on outcomes (deliberate): replayed games' away scores and every overtime winner are drawn from new numbers; generated games' regulation scores and box scores are unchanged. Tests: `tests/test_winpick_shooters.py` (a box score that uses 17 extra random numbers changes no score in either mode; a different points formula changes no score).

## 2. The betting-odds test: before and after

Short settings throughout (coordinator instruction): 20 runs per game, all 1,230 games, seeds 1 and 7, plus seed 1001 (the only one that shares no runs with the others). "Paired" means the same games and random numbers; the error bar is the standard error of the per-game difference.

**Important about the seeds.** The test runs seeds `seed, seed+1, ..., seed+runs-1`. At 100 runs, seed 1 uses runs 1-100 and seed 7 uses runs 7-106: 94 of 100 are the same. At 20 runs they share 14 of 20. "Confirmed on two seeds" was nearly the same sample twice.

**Sampling noise of the test itself.** A game's win chance is estimated from N runs; the Brier score adds the variance of that estimate. Measured from two independent seeds at 20 runs: 0.0058 (the formula gives 0.0057). At 100 runs that is about **0.0011**; at 400 runs 0.0003. The market has no such noise. The reshuffle of one team's dice (section 1) moves the 100-run Brier by about +-0.0009 (one error bar). The reported cost (+0.0005 and +0.0006) was within one error bar on what was effectively one sample.

| Step (20 runs a game) | Seed 1 Brier / log loss / spread / totals | Seed 7 Brier / log loss / spread / totals |
|---|---|---|
| Before both changes (old points formula, no pace habit) | 0.2013 / 0.5939 / 5.14 / 5.88 | 0.1984 / 0.5887 / 5.13 / 5.84 |
| + new points formula only (old engine) | 0.2015 / 0.5939 / 5.12 / 5.92 (paired +0.0003 +- 0.0009) | 0.1997 / 0.5918 / 5.14 / 5.88 (paired +0.0013 +- 0.0009) |
| + pace habit (= last merge) | 0.2010 / 0.5935 / 5.17 / 5.84 | 0.1994 / 0.5912 / 5.16 / 5.71 |
| New engine, pace habit off | 0.2009 / 0.5911 / 5.32 / 6.01 | 0.2011 / 0.5911 / 5.24 / 6.03 |
| **New engine (final)** | **0.2009 / 0.5911 / 5.34 / 5.92** | **0.2010 / 0.5909 / 5.25 / 5.88** |
| Pace habit's own cost, new engine (paired, same dice) | **-0.00004 +- 0.00011**; totals 6.01 -> 5.92 | **-0.00007 +- 0.00012**; totals 6.03 -> 5.88 |

(Market: Brier 0.1962, log loss 0.574. 20-run numbers sit about 0.005 above 100-run numbers because of the sampling noise above; compare rows, not with the market.)

- **Points formula:** in the new engine it cannot move any score (identical results, proven above). In the old engine its "cost" was a reshuffle: +0.0003 and +0.0013 on overlapping 20-run samples, +0.0005/+0.0006 on overlapping 100-run samples, each within about 1.5 error bars.
- **Pace habit:** with separate dice its win-picking effect is zero within error (slightly helpful), and it still improves game totals (6.01 -> 5.92 and 6.03 -> 5.88 at 20 runs; 5.48 -> 5.29 at 100 runs in the last task). Its spread change is +0.02.
- **Old vs new engine (different dice for the away team), Brier, paired, error bars about 0.002:** seed 1 -0.0001, seed 7 +0.0017, and on the three seeds that share no runs: 1001 +0.0043, 2001 +0.0035, 3001 +0.0011. This points one way, so I checked it four ways:
  - the draw-order check (60 games x 200 runs): no change in average margins (+0.16 of the error bar), margin spread (14.71 vs 14.70), totals spread (15.06 vs 15.16) or the home-away score correlation (0.023 vs 0.031);
  - nothing in the home box score changes the away team's expected rating (checked directly in 60 games: zero);
  - **a control: the old engine with the old draw order, only re-dealing the away team's dice** (`ctrl_src`): +0.0047, +0.0018, +0.0012 on the same three seeds, the same as the new order (+0.0043, +0.0035, +0.0011). So the new order is not the cause: any fresh deal of the away dice scores about the same, and the old engine's particular deal scored a little better;
  - do the old deal's away dice lean toward the real results? Correlation of (old minus new expected margin) with the real home win: 0.034, 0.042, -0.006 (error 0.029 each): weak.
  
  In theory the old deal cannot know anything (its random numbers come after the home box score, but each one is still a fresh, independent number). The remaining 2-3 error-bar pattern is either chance or a subtle leak in the old order (the replayed games use the real minutes played, which carry the real result, and the home box score's length depended on them); if it is a leak, it flattered the old numbers. Either way the new order is the honest one: the away team's luck no longer depends on anything in the home box score. Flagged for the coordinator.
- **100-run confirmation (one run, seed 1, the user's original setting):** Brier **0.1974**, log loss **0.5813**, spread error **4.61**, totals error **5.33** (before this task, same seed: 0.1967 / 0.5814 / 4.55 / 5.29; before the last task: 0.1962 / 0.5791 / 4.53 / 5.48). Log loss is unchanged from the last merge; Brier is 0.0007 higher (one reshuffle error bar at 100 runs is about 0.0009); totals keep almost all of the pace habit's gain. Subtracting this run's own sampling noise (0.0012) puts the engine's underlying Brier at about 0.1962, level with the market. **So the target "Brier at or under 0.1962 in the 100-run test" is not met on this sample**, and no box-score change can now move it: getting there needs a real change in how confident the engine is (next item).

**Where real win-picking could still improve (measured, not changed).**
- The engine's win chances are too confident: a logistic recalibration of its probabilities has slope 0.81 (1.0 = right), and its log-odds spread is 1.38 vs the market's 1.07.
- Splitting each game's expected margin into season-long team strength plus a game-specific part (rest, injuries, matchups): engine team strength spread 6.9 points vs the market's 5.2; game-specific swings 7.2 (after removing sampling noise) vs 4.2; the game-specific parts agree in direction (correlation 0.77). So the game-context effects (availability, rest, age/fatigue, matchup terms in `mean_off_rating`) are about 1.7x too strong.
- A blunt fix was tested and **not adopted**: shrinking the gap between the two teams' expected ratings by 15% (`sim.MATCHUP_STRENGTH_SCALE`, left at 1.0) cut the spread error a lot (5.34 -> 4.61, 5.22 -> 4.46) but did not improve Brier (+0.0002, +0.0005, paired) and narrows team records (win% spread .156 -> .141 vs real .166). Next step: find which game-context terms swing too much (a per-term comparison against the market's game-specific part) and refit those, not a global scale.
- Separately, the engine's game totals vary too little (within-game spread 14.9 points vs 18.5 around the market total) because the two teams' possessions are drawn independently; real teams share a game's pace. Sharing most of the possession draw between the teams would widen totals and narrow margins together. Not changed here (it would move every score).

## 3. Spot-up shooters

**What actually went wrong** (`stage_diag.py`, `three_diag.py`; the spot-up group = 39 players, 1,000+ minutes, threes 55%+ of shots, usage 18 or less). On average the group was handed the right number of points (13.4 vs 13.3 real per 36). The efficiency was lost while turning points into shots:
1. **Phantom two-point misses.** A night with no two-point make got 1.3 two-point misses per 36 whoever the player was, on top of the per-make misses that already averaged his own percentage. Pure shooters have no two-point make on most nights: AJ Green carried 2.5 two-point attempts per 36 at .25 (real 1.0 at .47); this step alone cost the group .05 of two-point percentage.
2. **Made threes cut by the points cap.** Points came first, made threes second, capped by the points. A shooter whose points are mostly threes had no room for a hot shooting night: the group made .362 of its threes vs .381 of its own, the cap biting on 73% of their lines, and the lost points became two-point attempts.
3. For the most extreme shooters, the points formula also handed out fewer points than their own threes make (AJ Green 11.8 per 36; his threes alone are 10.7; real 12.8).

**Fixes (box score only; team scores never read them).**
- **Two-point misses at the player's own rate** (`box_variation.two_attempts_per36`). If his two-point attempts arrive at his own rate and go in at his own percentage, the misses on a no-make night are a Poisson count of rate x (1 - percentage), and the per-make misses are thinned by the chance of at least one make, so all nights together average his own percentage. His rate is what his expected points leave after threes and free throws (correlation 0.94 with real two-point attempts per 36). Old-ratings players keep the old rule.
- **Points follow a shooter's own shots** (`box_rates.shot_points_blend`). The engine already sets each player's three-point attempts and percentage; his shot-location habit (three share, correlation 0.996 with his real share) says how many two-pointers come with them. His expected points are a geometric blend of the points formula and the points his shots make, weighted by his three share (none below 30%, all at 75%+). Fitted to 377 rotation players' real 2025-26 points per 36: mean error 1.31 -> 1.15; players whose threes make 70%+ of their points -0.87 -> +0.27. This keeps the shooting-mode and cutting habits in the points formula (rule 4) and adds the shot-location habit.
- **Pure shooters' threes come first** (`offense.draw_threes`, `sim.make_room_for_threes`; players whose habit puts 70%+ of shots from three). Tonight's three-point attempts and makes are drawn at his own volume and percentage before the points split; his hot/cold scoring draw leans on that luck; if his points still cannot hold his made threes, the missing points come from teammates in proportion to their points (the team total never changes), and his free throws give way before his threes. A hot shooter takes points from teammates instead of losing made threes. Applying this to everyone was tested and rejected: it moved the tough-shot creators off their fix (average error .011 -> .014) and the overall true-shooting error up.

**Results** (3 seeds of the full real-minutes season, averaged; "before" = this branch's engine with the three shooter changes switched off):

| | Before | After | Real |
|---|---|---|---|
| Spot-up group true shooting (39 players) | .562 | **.581** | .583 |
| Spot-up group points per 36 | 13.4 | 13.6 | 13.3 |
| True-shooting error, all 279 players with 1,000+ minutes | .0227 | **.0201** | |
| Points per 36 error, same players | 1.25 | **1.15** | |
| 15 highest shot-difficulty players: average error / average absolute error | -.001 / .011 | +.000 / .011 | |
| Usage quarters (lowest to highest) true shooting | .578 / .577 / .583 / .597 | .588 / .577 / .581 / .595 | .595 / .582 / .576 / .590 |

| Shooter | Real | Before | After |
|---|---|---|---|
| AJ Green | .627 | .519 | **.642** |
| Nicolas Batum | .603 | .420 | **.609** |
| Royce O'Neale | .596 | .553 | **.603** |
| Svi Mykhailiuk | .626 | .529 | .580 |
| Sam Hauser | .590 | .573 | .606 |
| Luke Kennard | .689 | .635 | .645 |
| Duncan Robinson | .629 | .602 | .601 |
| Sam Merrill | .644 | .633 | .619 |
| Max Christie | .601 | .589 | .594 |

Full spot-up and top-15 shot-difficulty tables: `output/winpick-shooters/eval_base.json` and `eval_final.json` (`spot_rows`, `tough_rows`).

| Top shot-difficulty players | Real | Before | After |
|---|---|---|---|
| Brandon Ingram | .573 | .578 | .583 |
| DeMar DeRozan | .594 | .581 | .578 |
| Kevin Durant | .640 | .640 | .638 |
| Luka Dončić | .616 | .596 | .599 |
| Jalen Brunson | .580 | .593 | .601 |
| Cade Cunningham | .564 | .553 | .570 |
| James Harden | .610 | .615 | .606 |
| Devin Booker | .585 | .613 | .604 |
| Zion Williamson | .643 | .633 | .631 |
| Kawhi Leonard | .629 | .619 | .630 |
| Nikola Jokić | .670 | .685 | .676 |
| Cooper Flagg | .548 | .549 | .564 |
| LaMelo Ball | .546 | .553 | .547 |
| Keyonte George | .609 | .584 | .579 |
| Shai Gilgeous-Alexander | .665 | .670 | .670 |

**Still short, and why (ratings, not engine; nothing changed per rule 1):** Kennard and Robinson are capped by their own shooting profile, which blends 2024-25 and 2025-26: Kennard .447 from three and .557 inside vs .478 / .601 in 2025-26; Robinson .401 / .558 vs .410 / .605. The engine now delivers their profile; the profile itself is below their 2025-26 season. Worth a look in the next ratings review.

## 4. Scorecards

| | Before (this branch's base) | After |
|---|---|---|
| Real-stat targets, replayed season (`calibration_report.py --games 1230 --mode replay-real-minutes`) | 18/18 | **18/18** (league true shooting .583 vs .581) |
| Real-stat targets, generated games (`--mode sandbox-sim`) | 18/18 (true shooting .597, points per 36 error 1.53) | **18/18** (.600, 1.41) |
| Player points per 36 error (150 players, replay) | 1.13-1.36 depending on seed | 1.17-1.20 |
| Betting test | see section 2 | see section 2 |

## 5. Speed

Full real-minutes season: 12.3 s before, 12.4 s after (3-seed average); generated-game season 14.5 s (15.0 s in the last task's run). The extra work is a few random draws for about 30 pure shooters a night and two expected-rating lookups only when the (off) strength scale is used. A simulated month is unchanged within noise.

## 6. Tests

- New `tests/test_winpick_shooters.py` (9 tests): extra box-score random numbers change no score (replayed and generated games); a different points formula changes no score; the strength scale moves the gap, not the total; the shooters' points blend leaves non-shooters alone and gives a pure shooter his shots' points; two-point attempt rates; misses average the player's own percentage; room for threes keeps the team total and takes from teammates; drawn threes are kept and free throws give way.
- Focused modules (box score, box variation, accounting, plus-minus, game minutes, offensive roles, rotation calibration and comparison, user rotation, both unused-ratings passes, offense audit): 139 run, all pass except one that needs a reference file from main's ignored `output/` folder (`test_offense_interior_interaction`, environment only).
- Core suite (`scripts/run_core_tests.sh`): **337 OK** (2 skips).

## 7. What went wrong along the way

- My first before/after batch ran a copy of the engine from a scratch folder, and the copy looked for the game data next to itself, so it ran without the 94-input ratings. Caught by comparing exact scores with the real engine; those runs were discarded (kept in `invalid_copied_src/` for the record) and rerun with the data linked.
- A first 100-run job was stopped when the coordinator asked for short runs.

## 8. What's left

1. **Game-context effects are too strong** (section 2): find which terms swing the expected margin 1.7x more than the market does and refit them; that is the real win-picking lever. The global strength scale hook is in place for experiments (off).
2. **Possessions shared by both teams** to fix totals spread (engine 14.9 vs 18.5) and margins together; it changes every score, so it needs its own task and both scorecards.
3. **The betting test's noise:** report 400-run numbers for decisions, or use seeds 100 apart; seeds 1 and 7 share 94 of 100 runs.
4. Kennard / Robinson shooting profiles (ratings review).
5. Generated games still score 118.6 points vs 115.6 real (known, unchanged here).

## Files

- `src/nba_gm_data/sim.py`: both scores drawn first (`draw_both_scores`), overtime stream, `draw_team_score` (`rating_shift`, `mean_only`), `MATCHUP_STRENGTH_SCALE` (off), shot-location habit feature and the points blend call, threes-first for pure shooters (`THREES_FIRST`, `make_room_for_threes`).
- `src/nba_gm_data/box_rates.py`: `shot_points_blend`, `SHOT_POINTS_RAMP`.
- `src/nba_gm_data/box_variation.py`: own-rate two-point misses (`two_attempts_per36`, `OWN_RATE_MISSES`).
- `src/nba_gm_data/offense.py`: `draw_threes`, `shooting_line(threes=...)`.
- `tests/test_winpick_shooters.py` (new).
- Not touched: trade code, draft code, GUI, ratings, the value formula, the experimental possession engine.
