# S2-SCHEMES (Stage 2, sixth piece): team defensive schemes, end-of-game plays, the heavy-fouler tail, the scoring level

_Owner: Claude (Opus session), worktree branch `claude/xenodochial-germain-52f3f7`. 2026-11-24. Status: **review**._

Progress: 7/7 - report written; committed on the branch (not merged, not pushed)

## TL;DR
- **The "replayed games score 3 points too high" puzzle is solved, and it was mostly turnovers.** On the same 1,231
  real games, Stage 2 turned the ball over 13.4 times per 100 possessions against a real 14.1. That number had drifted
  since its last fit (the turnover ratings follow-up, the coach, screens). Generated games were high too, not only
  replays (+1.1 points per team against +1.3), so it was not a replay quirk. Refitting the turnover level and the
  possession length to the real games brings both modes to the real level (115.3 and 115.4 points per team against a
  real 115.6), without touching the general scoring knob.
- **Heavy foulers are fixed at the source.** The engine charged every shooting foul to the shot's own defender, so a
  stopper on a star or a switching big collected every foul of every shot he was "on". Now a fitted share goes to a
  teammate (the help, a rotation, a closeout). Players fouling 4.5+ times per 36 went from 29 to 14 in replays (real
  11) and from 21 to 9 in a generated season. Foul-outs now match real (1.51% against 1.55%).
- **Each coaching staff now has a ball-screen scheme**, fitted to the scheme study. Brooklyn presses screens, Miami and
  Memphis sit back, on top of what their personnel already decide. The league mix stays at the real 26% switching.
- **End of games:** two-for-ones and late timeouts that advance the ball now happen at the real rates. Overtime did
  not move (about 3.3% in replays against a real 4.4%). The reason is elsewhere: Stage 2 has too few games decided by
  1-3 points (10.5% against 12.7%) and too many by 4-5. That needs real play-by-play to fit (below).
- **Scorecards.**
  - **Betting test:** the totals miss falls from 6.60 to **6.12** points, closing more than half the gap to today's
    engine (5.78).
  - Winner-picking holds (Brier .1975 against .1977; today's engine .2012). Spreads are about even (4.40 against
    4.35; today's engine 4.03).
- **Real-stat targets:** 18 of 18 in range; the average distance halved (.38 to .19 team spreads). Speed: replays 7.7
  ms a game (was 7.6), generated 10.8 ms (was 10.3); budget 20-40.

## What changed

### 1. The scoring level (part 4 of the task): why replays scored about 3 points high
New tool: `scripts/research/s2_level_gap.py` plays every 2025-26 game in both modes, replayed (real availability and
minutes) and generated (the game's own rotation and injury model), and compares each team's box with the real box of
that same game. Earlier comparisons used the calibration report's 150-game sample, which happened to sit low for
generated games.

Per team-game, all 1,231 games, 4 runs (before this piece):

| | Points | Possessions | Points per 100 | Turnovers per 100 | Effective FG% | Free throws per 100 |
|---|---|---|---|---|---|---|
| Real | 115.61 | 102.54 | 112.75 | 14.13 | .546 | 22.9 |
| Replayed (before) | 116.89 (+1.28) | 103.32 | 113.13 | 13.35 | .543 | 23.1 |
| Generated (before) | 116.71 (+1.10) | 102.64 | 113.71 | 13.37 | .546 | 23.8 |

- **Both modes scored high**, by about the same amount. Replays got it from extra possessions (+0.9 points per team)
  and generated games from efficiency (+1.0).
- **The shared cause:** 0.8 fewer turnovers per 100 in both modes. That means 0.8 more shots per 100, worth about
  0.9 points per team. The turnover level (`to_shift`) is a league constant fitted to the real turnover rate. It had
  drifted since its last fit.
- **The replay-only part:** replays ran 0.7 possessions faster than generated games. Some of that is the lineups on the
  floor (real minutes give quicker lineups relative to the league average than the projected rotations do). The
  recent-form term adds about +0.4 possessions in both modes, because today's engine centers it on a 228-point total
  and 2025-26 averaged 231. That term was already present when the pace was fitted, so it is part of the fitted level,
  not drift.
- **The fix:** refit the two constants to their own real targets over both modes together. The turnover level goes
  .11 → .17 and the half-court possession mean 15.6 → 15.75 seconds.

After (all games, 4 runs, final numbers):

| | Points | Pace per 48 | Turnovers per 100 | Effective FG% |
|---|---|---|---|---|
| Real | 115.61 | 101.98 | 14.13 | .546 |
| Replayed | 115.28 (-0.33) | 102.37 | 14.15 | .544 |
| Generated | 115.37 (-0.24) | 101.75 | 14.11 | .547 |

The general scoring knob (`make_level`) was not touched. What is left is small and has a visible cause: replayed
shooting sits .003 below real while generated shooting is on target. That is the lineup difference again (real
minutes put more weak shooters on the floor than healthy rotations do).

### 2. Who commits a shooting foul (part 3: the stopper foul tail)
- **The probe:** `scripts/research/s2_foul_tail.py` compares each rotation player's fouls per 36 in replays with his
  real 2025-26 fouls in the same games, and tags every foul by how it happened.
  - Before: 29 players at 4.5+ per 36 (real 11); spread across players .95 (real .80); correlation with real .75.
  - The excess followed **exposure**: how many shots a defender was charged with per minute (r .56 with his
    over-fouling). The over-foulers were stoppers on stars (Brooks, Nesmith, Caruso, Vanderbilt: 25-40% of their
    fouls on the star's shots) and switching bigs (Adebayo, Allen, Claxton, Hartenstein).
- **The cause:** the loop charged every shooting foul to the shot's own defender. Real fouls also come from the help,
  the low man, a late rotation or a closeout.
- **The fit:** `scripts/research/s2_foul_help_fit.py` records every shooting-foul chance in replays (487,000) and
  recomputes everyone's fouls for other splits. It holds the league's free throws fixed, fits on half the 311 players
  and checks on the other half.
  - Giving the share to the rim protector alone made bigs worse and was fitted to zero.
  - Giving it to one of the other four (weighted by his own foul control, contest habits and foul trouble) worked:
    held-out error .469 → .376 fouls per 36, correlation .789 → .836.
  - Larger shares fit slightly better still but flatten players below the real spread. I kept rim and short paint
    60% and jumpers 45%, which match the real spread (.77 against .80).
- **In the engine:** the foul chance is still the shot's defender's. Only who is charged changes, so free throws do
  not move.

| | Players 4.5+ per 36 | Spread | Correlation with real |
|---|---|---|---|
| Replays before (311 players) | 29 | .95 | .751 |
| **Replays after** | **14** | .76 | **.792** |
| Real | 11 | .80 | |

Named examples (per 36, replays, before → after, real): Brooks 5.56 → 4.60 (3.87), Nesmith 4.72 → 4.20 (3.35),
Claxton 4.84 → 3.83 (2.96), Adebayo 3.34 → 2.87 (1.86), Jaren Jackson Jr. 5.44 → 4.66 (4.43).

Generated 2026-27 season (all 30 teams AI-coached, seed 17): heavy foulers with 1,000+ minutes 21 → 9. Regulars' foul-
outs 1.73% → **1.51%** (real 1.55%), so the coach's foul-caution numbers stay as fitted. Regulars' fouls per game
2.37 → 2.44 (real 2.29).

### 3. Team ball-screen schemes (part 1; `stage2/schemes.py`, `stage2/scheme_table.py`)
- **What the study's measures mean.** Coverage aggression tracks how high the big plays the screen: drop is low, show
  and trap are high. It rises with mobile bigs (r .68) and falls with tall bigs (-.53). It has nothing to do with
  switching (r -.14 with guards' time on centers). Versatility moves with aggression almost one for one (r .91), so
  they are one axis here. For switching, the study's switching proxy is guards' assigned time against centers.
- **The fit** (`scripts/research/s2_scheme_fit.py`):
  1. Replay 2025-26 and record every ball screen's personnel-only coverage call (156,600 screens over 2 runs).
  2. For each team, compute the engine's own aggression proxy (share of its bigs' screens not dropped) and switching
     proxy. The personnel-only aggression proxy already predicts the real aggression index at r .54; the switching
     proxy predicts the guards-on-centers share only weakly (r .23).
  3. Each team's leftover (real measure minus what its personnel predicts, on a spread-matched scale) is its staff's
     habit. Shrink it by how well the study found a team's history predicts the next season: .53 for aggression
     (teams that kept their coach), .26 for switching.
  4. Convert the shrunk leftover into log-odds tilts on the coverage call: aggression means drop less and trap more;
     switching means switch more.
- **The result is modest on purpose:**
  - Tilts run -0.21 to +0.24 for aggression and -0.10 to +0.13 for switching. Most of the team-to-team difference
    still comes from personnel, as the study found.
  - Most aggressive staffs: Fernandez (Brooklyn drops 38% of screens instead of the 41% its personnel alone gives,
    shows 32% instead of 29%, traps 3.7% instead of 2.8%), Lue, Rivers, Carlisle.
  - Most conservative: Spoelstra (Miami drops 43% instead of 40%), Iisalo (Memphis), Hardy, Adelman.
  - The league mix stays at switch 26.6%, drop 43.3%, show 27.2%, trap 2.9%.
- **Lookup rules:**
  - The table is keyed by head coach.
  - A coach on a new team brings half his habit (a stand-in: the study had one example of a coach moving).
  - New hires and interim coaches have none, so their team follows its personnel.
  - In a save, the save's head coach decides.
- **Not done:** zone, post doubles and help-side choices. The study has no per-team rates for them.

### 4. End of quarters and games (part 2)
New probe: `scripts/research/s2_endgame_check.py` measures overtime, the margin with 60 and 24 seconds left, final
margins, two-for-ones and late timeouts, and compares final margins with the real box scores of the same games.
- **Two-for-ones** (1st-3rd quarters): a team that gets the ball with 30-42 seconds left shoots early enough to get it
  back. The extra chances are fitted to the rotation study's early-shot rates:

  | | 30-34 s | 35-38 s | 39-42 s |
  |---|---|---|---|
  | Real 2025-26 | .19 | .53 | .64 |
  | Before | .17 | .41 | .61 |
  | After | .20 | .51 | .65 |

- **Late timeouts** (last two minutes of the 4th and of overtime, two per team):
  - A team gaining the ball within ten points calls one at a fitted rate for the score: 0.50 per team-game against a
    real 0.51 (before: none).
  - A trailing or tied team advances the ball to the front court and saves the back-court seconds (4 s, stand-in).
  - The coach may change the five.
- **Overtime did not move:** 3.2% with timeouts off and 3.3% on, over 14,800 replayed games each (real 4.4%). In the
  generated season it is 3.6% (was 3.3%).
- **Why overtime stays low.** Final margins on the same games:

  | Final margin | 1-3 | 4-5 | 6-8 | Overtime |
  |---|---|---|---|---|
  | Real | 12.7% | 8.8% | 13.1% | 4.4% |
  | Stage 2 | 10.6% | 10.1% | 15.8% | 3.3% |

  Stage 2 lets one-possession games slip to two possessions in the last minute. I tried hurrying a trailing team
  (shorter possessions, threes when down 4-6), a leader running the shot clock down, going for the tie when down two,
  and shooting earlier when behind. None moved the shape by more than a few tenths, and shooting earlier lowered
  overtime. I removed them rather than keep untested stand-ins. Settling this needs real play-by-play: the state with
  60 and 24 seconds left and what happens next. The rotation study's source files (public GitHub parquet, about
  100 MB a season) have it, but they are not on this machine. I did not download them without asking.

## Scorecards side by side

### Betting test (20 runs a game, 1,231 games, 1,018 with market odds; average of seeds 1001 and 2001)

| | Brier | Log loss | Spread miss (pts) | Total miss (pts) |
|---|---|---|---|---|
| Market | .1962 | .5740 | | |
| Today's engine (coach report's re-run; no change since) | .2012 | .5910 | **4.03** | **5.78** |
| Stage 2 before this piece (re-run, identical to the coach report) | .1977 (.1967 / .1987) | .5832 | 4.35 | 6.60 |
| **Stage 2 final** | **.1975** (.1999 / .1951) | **.5823** | 4.40 (4.37 / 4.42) | **6.12** (6.10 / 6.15) |

- **Plainly:** totals improve by half a point a game, the biggest single step on totals so far. That is the scoring-
  level fix: replayed games no longer run 2.5 points a game above real.
- Winner-picking holds; the seeds swing by .005 each way, so the .0002 change is noise.
- **Spreads** are .04 worse on average. That is about the size of the seed-to-seed difference (.02-.05), so I read it
  as even, but it did not improve.
- Today's engine was not re-run. Nothing it uses changed since the coach report's re-run (only Stage 2 files and GUI
  commits).

### Real-stat targets (`calibration_report.py --engine stage2`, 150 generated games, seed 1)

| | In range | Average distance (team spreads) | Largest |
|---|---|---|---|
| Stage 2 before this piece (re-run) | 18 / 18 | .38 | .94 (turnover rate, low) |
| **Final** | **18 / 18** | **.19** | .70 (fouls per 100, high) |

The re-run baseline differs from the coach report's .36: generated games read today's save data, which has moved
since. In the final run the turnover rate is 14.05 against 14.13, and points 114.7 against 115.6 (z -0.3; over all
1,231 games, generated games score 115.7).

### Speed (laptop, same 400 games, best of three)

| | Replayed | Generated |
|---|---|---|
| Before this piece | 7.5-7.6 ms | 10.3 ms |
| **After** | 7.6-7.7 ms | 10.7-11.0 ms |

A full AI-coached generated season measured 19.9 ms of game-sim CPU a game (17.9 in the coach report's run; that
figure includes today's pre-game steps and varies with laptop load).

## What is still a stand-in, and weak spots
- **Scheme strength.** The tilts are fitted on the engine's own scale (spread-matched), because no public source turns
  the aggression index into coverage percentages. The switching side rests on a weak proxy (r .23) and is heavily
  shrunk.
- **The share a coach carries to a new team** (half) is a stand-in.
- **The back-court seconds a timeout saves** (4) is a stand-in.
- **End-of-game closeness** (1-3 point finishes, overtime) needs real play-by-play (above).
- **Fouls per 100** now sit a little high in generated games (20.0 against 19.4; z 0.7). Teammates who take a share of
  the shooting fouls are more foul-prone on average than the shot's defender. Free throws are unchanged.

## Ratings questions (rule 1)
- **Sabonis** fouls 5.5 times per 36 in the generated season, the clear outlier after the fix. He played little in
  2025-26, so the replay check cannot compare him. It is worth checking his foul control (S45) and contact habits
  against his 2023-25 fouls per 36.
- **Over-foulers that remain in replays:** Kenrich Williams 4.3 (real 2.5), Yves Missi 4.5 (3.1), Baylor Scheierman
  4.0 (2.7). Each is about +1.3-1.8. No engine pattern explains them (different roles), so they are candidates for a
  foul-control check, not a model change.

## Recommended next piece
1. **Fit the end of games on real play-by-play:** the margin and possession state at 60 and 24 seconds and the
   transitions from there. This is the last known source of the overtime and close-finish gap, and it needs the
   rotation study's public files (ask the user before downloading).
2. **Spreads.** Stage 2 still trails today's engine on spreads (4.40 against 4.03). With the level fixed, team scoring
   levels and per-game noise are the main causes, as in the last two reports.

## Files
- **New:**
  - `src/nba_gm_data/stage2/schemes.py`, `src/nba_gm_data/stage2/scheme_table.py`;
  - research scripts `scripts/research/s2_level_gap.py`, `s2_foul_tail.py`, `s2_foul_help_fit.py`,
    `s2_endgame_check.py`, `s2_scheme_fit.py`;
  - `tests/test_stage2_schemes.py` (7 tests).
- **Changed:**
  - `stage2/game.py`: who is charged with shooting fouls, two-for-ones, late timeouts, coverage with the scheme, the
    turnover and pace refit, research hooks (`COVERAGE_TRACE`, `FOUL_TRACE`; None in play);
  - `stage2/screens.py`: the coverage call split into personnel log-odds and the scheme tilt (same numbers at zero
    tilt);
  - `stage2/engine.py`: the coach's scheme on each team;
  - `stage2/__init__.py`: notes.
- **Not changed:** `sim.py`, the GUI, ratings, `docs/agents/BOARD.md`. Today's engine is unchanged (the seam test
  still checks default = explicit "current").
- **Output (git-ignored):** `output/s2schemes/` (betting `odds_*`, scorecard `cal_*`, level gap `level_gap_*`, fouls
  `foul_tail_*` and `foul_help_fit_*`, end of game `endgame_*`, schemes `scheme_fit.json`), generated season
  `output/s2coach/season_stage2_schemes.json`.

## Checks
- Stage 2 tests: the existing 62 OK; new `tests.test_stage2_schemes` 7 OK.
- RNG: Stage 2 game outcomes change by design. Every piece adds or moves draws. Today's engine's streams are untouched.
- Laptop: one local job at a time under `nice`; both betting runs on the Azure pool.

## Resume state
- [x] Baselines (betting pair `s2s-base-*`, scorecard) → level gap → fouls → end of game → schemes → refit → tests.
- [x] Final betting pair (`s2s-final-1001`, `s2s-final-2001`), report, commit on the branch. Board row left to the
  coordinator.
