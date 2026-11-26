# SHOOTING-SPLITS: players' 2-point, 3-point and free-throw percentages match their ratings

Progress: 8/8 - done; ready for the coordinator's review

Owner: Claude (side session, worktree `shooting-splits-603e9b`, branch `claude/shooting-splits-603e9b`).

## TL;DR
- **Threes and free throws now follow each player's own ratings.** In a hands-off season the league shoots 35.8% from
  three (the players' own 35.6%, real 36.0%; was 32.5%) and 77.5% at the line (own 78.2%, real 78.3%; was 81.4%).
  Markkanen .348 against his own .351 (was .261).
- **Big nights and box-score tails look real.** 40-point games 38 → 95 a season (real 133), six-steal games 70 → 24
  (real 27), ten-turnover games 17 → 4 (real 3). Game scores are untouched: the betting test is identical on both seeds.
- **Left over:** two-point shooting is still high (57.4%, real 55.0%) because the game's scores are about 1 point of
  true shooting more efficient than real, and twos absorb that. Players used per team-game (12.7 vs 10.8) is the
  coach's rotation, a different system. Both listed below for follow-ups.

## What was wrong and what changed
A player's points are set first, then his shots are made up to fit them. Four things bent the shooting:

1. **Threes scaled by tonight's points over unshared points per 36.** Teammates' points per 36 add up to more than a
   team scores, so players averaged ~95% of "usual" and shot threes ~2.5 points low all season. Fixed twice over: the
   scaling now uses his share of tonight's team points, and, more importantly, **every player's threes are now drawn
   first at his own volume and percentage** (this already existed for pure shooters; `THREES_FIRST_MIN_SHARE` 0.70 → 0).
   Even with a correct scaling, a 1- or 2-point night can't hold a three, which cost another ~1.2 points league-wide.
   Drawing threes first gives exactly his own percentage; his scoring night leans on his three-point luck.
   (`sim.py` distribute_player_lines; `offense.py` comments.)
2. **Odd point totals were settled with a made free throw.** About half of all lines have an odd number of points
   left after free throws and threes; the old rule added a made free throw whenever he had none, so free throws ran
   high in count and percentage. Now odd lines are paired within the team: one gains a point, the other loses one
   (coin flip, team total unchanged); if the team has an odd count, one player's free throws change by a made
   attempt up or down, half the time each. (`offense.settle_odd_lines`; `shooting_line(defer_parity=True)`.)
   A player's points can now move by a point or two when only his free throws change; scores never do.
3. **Two-point shooting** is set so the team's points and possessions add up (the box score adds or removes
   two-point misses). That machinery is fine; it was carrying the three-point shortfall. With threes and free throws
   right, it dropped 59.2% → 57.4% in the season. What remains is the team scoring level (season true shooting .592 vs
   real .581, same before and after): every extra point lands on twos.
4. **Nearby, same machinery:**
   - **Points spread.** Every scoring tier's game-to-game spread was 68-87% of real (replaying 2025-26 with real
     minutes: top-30 scorers sd 6.2 vs 8.1). Scoring nights now spread like counts of baskets (variance ≈ 2 × expected
     points on top of the role's swing; `SCORING_COUNT_SPREAD`). Every tier now 92-107% of real.
   - **Steals.** Team steal totals were shared by scaling players' draws, so 3 steals on a quiet team became 6-7.
     Now missing steals are handed out one at a time by each player's own rate, extra ones taken from drawn steals at
     random (`sim.reshare_by_rates`; also blocks in `box_variation`). Team steals' spread was also too small (sd 2.1 vs
     real 3.2; `STEAL_GAME_SIGMA` 2.0 → 3.1).
   - **Turnovers.** Drawn as Poisson with a shared team-day factor: player spread 1.12x the mean (real 0.93), team sd
     4.5 (real 4.05). Now a binomial-like draw (`TURNOVER_CHANCE` .19, `TURNOVER_DAY_SCALE` .8): both match real.

Random streams: game scores and minutes are unchanged by construction (scores are drawn before the box score; new
choices use side generators). Player lines (points split, shots, steals, turnovers) do change.

## Scorecards
**Betting test** (20 runs, 1,231 games, 1,018 with odds), before → after:
seed 1001 Brier .2047 → .2047, log loss .5999 → .5999, spread 4.132 → 4.132, totals 5.684 → 5.684;
seed 2001 .1979 → .1979, .5832 → .5832, 3.987 → 3.987, 5.827 → 5.827. Identical (scores untouched).
**Player points props** (`s2_props.py`, 40 games of market lines, 200 runs): Brier .2150 → .2125, log loss .6167 →
.6100, average gap to the market's over chance .21 → .145 (better on all three). Every-game check (8 runs a game):
points expected-vs-actual error 4.09 → 4.28, because wider real-like spread makes an 8-run average noisier;
threes 0.909 → 0.914, rebounds and assists unchanged.

**Real-stat scorecard** (new targets: league 2P%, 3P%, FT% and a "box-score texture" section: players used per
team-game, 40- and 50-point games, 20-rebound, 6-steal and 10-turnover games, with bands that allow for both seasons'
sampling noise):

| | before | after |
|---|---|---|
| Standard run (150 games, projected minutes) | 19/21 league, 3/6 texture | **21/21**, 4/6 |
| Whole season replayed with real minutes | 20/21, 2/6 | **21/21, 6/6** |
| Whole season, projected minutes | 18/21 | 20/21 (2P .579 out) |

The projected-minutes harness gives no one more than ~30 minutes and plays 14-18 players, so its players-used and
big-night rows can't pass; the report says so. Replayed with real minutes: 3P .362 (real .360), FT .777 (.783), 2P
.557 (.550), 40-point games 143 a season (133), six-steal 27 (27), ten-turnover 7 (3).

## Hands-off season (seed 20261126, Azure, `scripts/season_almanac_run.py`)
| | before | after | real |
|---|---|---|---|
| 3P% / players' own | .325 / .356 | **.358 / .356** | .360 |
| FT% / own | .814 / .780 | **.775 / .782** | .783 |
| 2P% / own | .592 / .545 | .574 / .545 | .550 |
| 40-pt / 50-pt games | 38 / 2 | 95 / 6 | 133 / 17 |
| 20-rebound games | 9 | 14 | 26 |
| 6-steal / 10-turnover games | 70 / 17 | **24 / 4** | 27 / 3 |
| Players used per team-game | 12.70 | 12.70 | 10.79 |

Per player (150+ threes): sim minus own .021 low → .004 high; average miss .031 → .022; correlation with own .68 →
.77 and with his real 2025-26 percentage .57 → .70 (300+ threes: miss .019, correlation .80 with own). The link
between "scored less than usual" and "shot threes worse" fell .56 → .29.
Top-volume shooters (after): Curry 374/999 (.374, own .392), LaMelo Ball .352 (.359), Maxey .355 (.358), Tatum
.346 (.340), Isaiah Joe .435 (.413), Edwards .362 (.394), Pritchard .407 (.386), Knueppel .424 (.419), Porter Jr.
.378 (.372), Garland .394 (.394). Flagg .371 (.306) and Murray .380 (.419) are the widest season-sample swings.
Full lines: `output/shooting-splits/season_{before,after}.json` (not in git).

**Speed** (a month, `season_month_probe.py`, laptop, Oct 20 - Nov 30): before 22.5 / 22.1 s per 30 days, after 22.6 /
19.9. No change.

**Tests:** new `tests/test_shooting_splits.py` (7); `tests/test_box_star_stats.py` updated (steal shares now need
players' rates; points may move by up to 2 when only free throws change). Full suite on Azure
(`run_tests_parallel.py --all --workers 3 --js`): 2,682 tests, all passed; browser tests passed.

## For follow-ups
1. **Team scoring a little too efficient** (season true shooting .592 vs real .581; projected-minutes sandbox ORtg
   114.4 vs 112.8). Twos absorb it (2P 57.4% vs 55.0%). Lives in the score model (`sim.py` draw_team_score), which the
   betting test is tuned on; worth its own task with both scorecards.
2. **Players used per team-game 12.7 (real 10.8); 52% of team-games use 13+ (real 16%).** The coach's rotation and
   garbage-time extras (`sim.py:1033-1049`, `save.py` team_rotation_projection), not the box score.
3. **Season 40-point games 95 vs 133, 20-rebound 14 vs 26, 40-minute nights 319 vs 509.** With real minutes the box
   score now gets 40-point games right (143), so the season's shortfall is mostly minutes (stars rarely play 40).
4. **Overtime box lines make every shot** (`sim.add_overtime_points`: threes, twos and free throws added as makes
   only). Small (~0.1-0.2 points of FT%), but wrong on the box score.
5. **Players score under their points per 36 in a new season** (Markkanen 23.9 vs his 28.9; Edwards 28.8 vs 31.6):
   teams of scorers share one ball. Not a percentage problem any more; worth a look with the usage model.
6. The projected-minutes calibration harness (`calibration_report.py` default) can't judge minutes-driven targets;
   the texture rows are best read from `--mode replay-real-minutes --games 1230` (10 s).

## Boundaries
Today's engine (`sim.py`, `offense.py`, `box_variation.py`), the real-stat scorecard (`scripts/calibration_report.py`,
`scripts/build_calibration_targets.py`, `src/nba_gm_data/calibration_targets.py`, the targets JSON: only new
entries added; existing targets byte-identical), tests, this file. Not ratings, `stage2/`, trade code, `draft.py`,
`gui/`, or the board.

## Resume state
Done. Probes and run outputs in `output/shooting-splits/` (probe.py, spread.py, teamsd.py, season_check.py,
scorecard_any.py; odds/props/season before and after).
