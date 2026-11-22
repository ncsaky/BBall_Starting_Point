# ROOKIE-SEASON: rookies in the simulated season

_Owner: Claude (Opus agent, worktree branch `worktree-agent-a9faafaa376e62df1`). 2026-11-22. Status: **review**._

Progress: 8/8 - report written, in review

**TL;DR**
- **Top rookies now score at real rates per minute** (Acuff 21.4 per 36, was 17.7, real 24.8; Wilson 19.3, was 15.5,
  real 22.1). The cause was an engine bug: rookies had no NBA shooting record, so the game gave them 2-3 three-point
  tries per 36 and then cut their points to fit. **But it uncovers a data problem I could not fix here:** role-player
  rookies' "wants the ball" tendency is set too high from college usage, so the class as a whole now over-scores.
- **Rebuilding teams now give young first-round picks development minutes** (measured on 11 real seasons: about +6 a
  game in year one, +3 in year two). Contenders barely change. Rookies on rebuilding teams play 2-3 more minutes a game.
- **Rookies now do most of their first-year growth during the season** (75%, from real game logs, was 50%); yearly
  growth is unchanged. Most of the real first-half-to-second-half jump, though, is more shots and a league-wide
  second-half pattern, not skill. Gates: scorecard 18/18, core tests pass, betting test a hair worse (see below).

## 1. In-season growth

### What real players do (ESPN game logs, regular seasons 2015-16 to 2025-26)
Basketball Reference blocks game logs and splits for robots, so the logs come from ESPN's public stats API (1,672
player-seasons, 3 seconds apart): every first-, second- and third-year player with 400+ minutes, plus 25 veterans aged
26-30 a season as a comparison group. Each season is split at its middle date. Players with 300+ minutes in both halves.

First half to second half (per 36 minutes; "skill" is the box-score impact formula DEV-CURVE fitted on real box
plus-minus, holding both minutes and shot volume fixed, so only how well he plays counts):

| Group | Players | Points | (from more shots) | (from better shooting) | Assists | Turnovers | Minutes a game | Skill |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| First year | 250 | +1.13 | +0.81 | +0.31 | +0.28 | -0.07 | +2.5 | +0.64 |
| ... on teams under .400 | 118 | +1.77 | +1.32 | +0.44 | +0.31 | +0.06 | +3.5 | +0.57 |
| ... on other teams | 132 | +0.55 | +0.36 | +0.19 | +0.25 | -0.18 | +1.6 | +0.70 |
| Second year | 303 | +0.63 | +0.40 | +0.23 | +0.22 | -0.06 | +1.5 | +0.39 |
| Third year | 283 | +0.63 | +0.41 | +0.22 | +0.20 | -0.09 | +1.1 | +0.53 |
| Veterans 26-30 | 310 | 0.00 | -0.07 | +0.07 | +0.15 | -0.13 | -0.1 | +0.35 |

What this says:
- **The real rookie jump is about +1.1 points per 36 over 11 classes** (last season's +2.4 was a high year). About
  three-quarters of it is more shots, and on bad teams it is bigger: that is role (more touches as the season goes),
  not skill. Efficiency and defense change little (true shooting +1 point, rebounds/steals/blocks flat).
- **Everyone looks better in the second half.** Veterans' skill measure rises +0.35 too, and falls back by next
  autumn. So only about +0.3 of the rookies' +0.64 is rookie growth.
- **Timing within the year** (box impact; veterans give the league's second-half swing): first-year players do about
  70-80% of their year's growth during the season (0.68 holding shot volume fixed, 0.83 without; wide ranges, roughly
  0.3-1.1). Second-year players show no clear lean (0.2-0.5). Their yearly growth (+1.1 box points for rookies) matches
  DEV-CURVE's real target (+1.18 at 19-20), so the yearly totals are not too low on this evidence; I did not raise them.

### What changed
- `health.py`: a development month now carries a share of the year by when it falls. Rookies (their draft year's
  season) get 75% of the year's growth in the six in-season months, 25% in the six summer months; everyone else stays
  even. Each July-June year keeps exactly its total (unit-tested; a development-only five-season run gives identical
  June-to-June changes at every age: 19-20 +0.554, 21-22 +0.229, 23-24 +0.080, 25-29 -0.024, 30+ -0.372, before and
  after). Only growth is reshaped; aging decline is not.

### Result (two simulated seasons, seeds 17 and 18, before vs after)
- Rookie card overall rises about 0.17-0.19 a month in season (was 0.12).
- First half to second half, simulated rookies: skill +0.21 (veterans +0.17), points per 36 +0.10, minutes +1.9.
  Before: skill -0.08, points +0.15. The seed-to-seed noise is about +-0.2, so the growth shift is real but small.
- **Gaps that remain (not development):** (1) the game has no league-wide second-half lift (simulated veterans +0.1
  to +0.2 vs real +0.35); (2) simulated rookies do not take more shots as the season goes (real +0.8 per 36, mostly on
  bad teams). Both are role and game-context effects; I did not model them. A natural follow-up: rebuilding teams
  shifting touches to young players after the trade deadline.

## 2. Top rookies' scoring per minute

**Cause found: shot creation in the simulation, not usage, not the coach.** For players with no NBA shooting record
(every rookie) the game set three-point tries from an old formula on the shooting-range rating: Acuff 2.3 per 36 (real
9.3), Peterson 2.4, Wilson 2.5. A later step (built for shooters) blends a player's points with what his own shots can
produce, so those tiny shot totals cut rookies' points 15-20%. The points fit itself was right (Acuff 24.8, real 24.8).

**Fix (engine):** players without a full NBA shooting record take their three-point volume from their own inputs
(`offense.input_three_volume`: shot-location habit x the attempts his fitted points imply). On 396 veterans with a
record it tracks real three-point tries far better than the old formula (correlation 0.97 vs 0.81, average miss 0.55 vs
1.81 per 36). Veterans with a record are untouched.

| Rookie | Real (this season so far) | Before | After |
|---|---:|---:|---:|
| Darius Acuff Jr. | 24.8 per 36, 36.9 min | 17.7, 25.5 min | 21.4, 27.5 min |
| Caleb Wilson | 22.1, 30.8 | 15.5, 30.3 | 19.3, 31.8 |
| Yaxel Lendeborg | 22.4, 31.6 | 14.0, 14.4 | 18.1, 15.6 |
| Darryn Peterson | 19.6, 30.6 | 19.3, 27.7 | 22.0, 28.7 |
| Cameron Boozer | 19.3, 30.9 | 16.3, 30.5 | 18.5, 30.9 |
| AJ Dybantsa | 17.5, 34.1 | 14.9, 27.5 | 17.1, 28.3 |
| Kingston Flemings | 13.0, 21.5 | 16.5, 19.9 | 20.1, 21.3 |
| Aday Mara | 16.1, 22.4 | 18.9, 19.1 | 18.5, 19.9 |

(Simulated: full season, mean of two seeds.)

**The catch (decision needed):** the fix removed a bug that had been hiding another one. Role-player rookies'
involvement tendency (how much they seek the ball), set from college usage by the input builder, is well above
veterans' at the same real NBA usage:

| Real usage this season | Rookies' involvement | Veterans' involvement | Simulated vs real points per 36 (rookies) |
|---|---:|---:|---|
| under 16% | 0.30 | 0.22 | 15.9 vs 13.4 |
| 16-20% | 0.34 | 0.26 | 17.6 vs 14.4 |
| 20-24% | 0.39 | 0.33 | 19.8 vs 18.2 |
| 24-28% | 0.40 | 0.38 | 20.2 vs 20.2 |
| 28%+ | 0.49 | 0.44 | 22.1 vs 24.8 |

So the stars are right and the role players over-score. The whole class now runs hot: points per 36 (500+ minutes)
middle 18.3 vs real 13.7 (before 15.5), and 6-7 rookies a class at 15+ a game vs real 2.5 (before 1). This is the
rookies' ratings (a tendency in the input builder), which I was not allowed to touch. **Recommended:** the input
builder's college-to-involvement mapping for rookies should be put on the veterans' usage scale (the owner of
`scripts/build_player_inputs.py` / `input_estimator.apply_rookie_involvement`). Until then, the coordinator can choose
to merge the fix as is (stars right, role players too high) or hold it.

**Second builder follow-up:** the builder levels each rookie's skills until the game values him at his ROOKIE-FIT-2
target, and it did that against the buggy shot profile. With the fix the game values rookies about +0.3 points per 100
higher (+0.9 card overall on average). Rerunning the builder's level step after this merges restores the targets.

**Other effects:** 23 non-rookies without a full record (few NBA minutes) also get the new shot volume (+0.75 card
overall on average); veterans with a partial record move slightly (+0.04 on average).

## 3. Development minutes

### Real (Basketball Reference 2015-16 to 2025-26; ESPN standings)
Within each team-season, players are ranked by box plus-minus (steadied toward -2 with 400 minutes' weight).
Veterans give the minutes a coach hands each rank and impact on each kind of team; "extra" is a young player's minutes
a game above that. Rebuilding = under .400 that season.

| First-round picks | Year 1: rebuilding / other (extra) | Year 2 | Year 3 |
|---|---|---|---|
| Picks 1-10 | 27.9 / 22.7 mpg (+7.7 / +1.0) | 26.9 / 26.6 (+5.0 / +2.8) | 25.2 / 27.6 (+2.4 / +2.9) |
| Picks 11-20 | 23.6 / 17.4 (+2.1 / -3.3) | 26.7 / 20.2 (+4.5 / -1.8) | 25.6 / 23.2 (+1.0 / -1.3) |
| Picks 21-30 | 20.6 / 14.9 (+1.7 / -4.8) | 19.6 / 19.2 (-1.0 / -2.0) | 23.9 / 20.8 (+1.3 / -2.3) |

The rebuilding lean (rebuilding minus other) is about **+6 minutes in year one for every first-round band, +3 in year
two, +2 in year three**. Top-10 picks by team type: rebuilding 27.5 mpg (+6.8 over a veteran of the same rank and
impact), middle 25.8 (+2.2), contending 22.5 (+1.4). Contenders show no development lean.

### What the game did
The coach's priority ranks players by last season's minutes plus ratings. Rookies start with a draft-slot placeholder
(24 minutes picks 1-5, 18 picks 6-14, 12 picks 15-30) that knows nothing about the team. In two simulated seasons the
rebuilding lean was about +2 in year one (real +6), +1 in year two (real +3), 0 in year three (real +2).

### What changed (`save.py`)
`development_minutes_priority`: on a team whose plan is "rebuilding", first-round picks get extra coach priority by
season in the league (6 / 4 / 2 workload minutes; picks 21-30 half). Only the part of a player's workload that is not
his own NBA minutes counts (players drafted before the save's first season carry their real coach's choice already).
Contending, entering and exiting teams: no change.

### Result (two seeds, both seasons)
- Top-10 picks in years 1-2 on rebuilding teams: 25.4 -> 26.9 mpg in season one, 27.7 -> 30.0 in season two (real
  27.5). Picks 11-20 in year one on rebuilding teams: 15.4 / 22.6 -> 20.9 / 23.8 (real 23.6).
- Rebuilding lean in year one: about +2 -> +3.5 to +5 (real +6). Year two about +1 -> +3 in season two (real +3).
  Small cells (5-18 players each), so these move a few minutes between seeds.
- Contending teams' veterans and young players: within half a minute.
- Examples, season one (mean of seeds): Acuff 25.5 -> 27.5, Dybantsa 27.5 -> 28.3, Peterson 27.7 -> 28.7, Burries
  18.2 -> 26.0. Still short of this season's real 37 / 34 / 31; the real three are above even the historical rebuilding
  average (picks 1-3: 30.6), so I did not push further.

## 4. Rookie class against real classes (season one, two seeds; real: 11 classes 2015-16 to 2025-26)

| | Before | After | Real |
|---|---:|---:|---:|
| Minutes: middle / top tenth | 698 / 1,749 | 818 / 1,807 | 502 / 1,841 |
| Minutes a game if played: middle / top tenth | 11.2 / 26.1 | 14.1 / 27.9 | 15.0 / 27.7 |
| Points a game: middle / top tenth | 4.4 / 11.9 | 6.1 / 15.8 | 4.2 / 12.1 |
| Points per 36 (500+ min): bottom tenth / middle / top tenth | 12.5 / 15.5 / 18.5 | 14.6 / 18.3 / 22.1 | 9.6 / 13.7 / 19.0 |
| True shooting, middle | .572 | .536 | .535 |
| 15+ a game per class | 1, 1 | 7, 6 | 2.5 |
| Share 10+ a game | 14% | 30% | 14% |
| Share 1,500+ minutes | 13% | 23% | 18% |
| Share under 300 minutes | 32% | 33% | 41% |
| Card overall rise a month in season | 0.12 | 0.17-0.19 | - |

Minutes and shooting efficiency moved toward real; scoring volume overshoots (section 2's involvement issue).

## 5. Gates
- **Real-stat scorecard: 18/18** (three-point attempts per 100 35.3 -> 35.7, target 36.1; others within 0.1).
  The growth timing and development minutes do not touch this replay (it plays real minutes with opening ratings).
- **Betting test** (20 runs a game, against the last commit run the same way):

  | | Seed 1001 before | after | Seed 2001 before | after |
  |---|---:|---:|---:|---:|
  | Brier (market .1962) | .2043 | .2045 | .1972 | .1974 |
  | Log loss | .5985 | .5989 | .5813 | .5819 |
  | Spread miss (points) | 4.164 | 4.183 | 3.998 | 4.013 |
  | Total miss (points) | 5.626 | 5.644 | 5.758 | 5.775 |

  Slightly worse, from the few 2025-26 players with little or no NBA shooting record getting the new shot volume.
  Limiting it to players with no record at all left it the same (.2045), so it is not worth special-casing.
- **Core suite** (`run_core_tests.sh`): 341 tests; one setup error from a missing git-ignored reference file
  (`output/settlement-materialization-pass`); linked from the main checkout and rerun: OK.
- **Focused tests** (`run_tests_parallel.py --workers 2 --match "rookie|develop|health|rotation|coach|minutes|offense|dev_curve|prospect"`,
  191 modules, 2,124 tests): 2 failures, both in `test_foundation` and both failing on the base commit too (the
  waiver "claimed" vs "cleared" one ROOKIE-FIT-2 reported, and `test_player_asset_valuation_rewards_portability...`,
  rerun on the base source: fails the same way); 9 errors, all missing git-ignored reference files for the
  experimental engine and input pilots (one linked and rerun: OK). New `tests/test_rookie_season.py`: 10 OK.
- **Speed:** a simulated month is unchanged: season-one regular season 184.5 s before, 186.2 s after (same seed,
  same machine load). Later runs overlapped with test runs and are not comparable.
- **DEV-CURVE drift:** none in yearly totals (section 1).

## 6. Decisions for the user / coordinator
1. **Rookie involvement mapping (section 2).** Merge the shot-volume fix now (top rookies right, role-player rookies
   and the class over-score) or hold it until the input builder puts rookies' college usage on the NBA usage scale?
   I recommend fixing the builder mapping, then re-leveling rookies (one builder run), then merging both together.
2. **Season-long role effects** (more shots for rookies on bad teams as the season goes; a league-wide second-half
   lift) explain most of the visible real rookie jump and are not modeled. Worth a follow-up if you want the box
   scores to show it.
3. Azure: the coordinator's late note allowed it; all runs here were already local and finished.

## 7. Files
- Engine: `src/nba_gm_data/offense.py` (`input_three_volume`, `INPUT_SHOT_VOLUME`), `src/nba_gm_data/health.py`
  (`INPUTS_IN_SEASON_SHARE`, `INPUTS_IN_SEASON_SHARE_BY_NBA_YEAR`, `development_month_weight`),
  `src/nba_gm_data/save.py` (`development_minutes_priority`, `DEVELOPMENT_PRIORITY_REBUILDING`, passed through
  `ai_role_targets` / `ai_coach_workloads`).
- Research: `scripts/research/rookie_halves_fetch.py` (ESPN logs), `rookie_halves.py` (halves, summer, timing; writes
  `data/research/rookie_halves.json`), `rookie_dev_minutes.py` (real; `data/research/rookie_dev_minutes.json`),
  `rookie_dev_minutes_sim.py`, `rookie_scoring_diag.py`, `rookie_shot_volume_check.py`, `rookie_profile_effect.py`;
  `rookie_season_probe.py` now records second/third-year players, veterans and season-end saves, and runs across
  seasons; `rookie_season_compare.py` reads the first season only.
- Outputs: `output/rookie-season/` (before_s17/s18, after_s17/s18, after1_s17 calibration run, odds, scorecards,
  tests, talent probes). `output/rookie-season/base` is the base commit's source for the before runs.

## Resume state
Done; in review. Branch `worktree-agent-a9faafaa376e62df1`. Not pushed. `.venv` and a few `output/` entries are
symlinks to the main checkout (not committed).
