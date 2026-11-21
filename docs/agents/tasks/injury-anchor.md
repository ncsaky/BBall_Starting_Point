# INJURY-ANCHOR: the injury model anchored to the complete public records (2026-11-21)

Branch: `worktree-agent-af5fe5f212784fb07`. Scratch and harness: `output/injury-anchor/` (git-ignored).

## TL;DR
- The game's injury level now comes from the three complete public seasons (every injury and illness that cost a game in 2023-24, 2024-25 and 2025-26), not the tracker. Injury lengths now follow those records too: the tracker missed mostly short injuries, so the game's injuries ran long.
- Result: 43.3-43.6 injuries a team that cost a game (real 40.5-45.6), lengths 48 / 32 / 10 / 5 / 4.5% (real 47 / 33 / 9 / 6 / 4%), and stars play closer to real: heavy-minute median 68 / 66 games (real 68; was 65 / 65), top-30 median 67.5 / 63 (real 64.5-65.5; was 63.5 / 59.5).
- Illness stays out of a player's injury history. It predicts the next illness better, but counted in the game it feeds on itself (illness 7.7 to 12.5 a team over four seasons).

## 1. What the complete records say
Source: Codex's `data/research/injury_history_{2023_24,2024_25,2025_26}.json`. Script: `scripts/research/injury_anchor_measure.py` (log `output/injury-anchor/measure_final.log`).

**Injury and illness stretches costing a regular-season game, per team** (all players):

| Season | All | Without injury management | Without opener carry-overs | Without both (Codex) | **One per absence (the anchor)** | Illness share |
|---|---:|---:|---:|---:|---:|---:|
| 2023-24 | 45.5 | 44.1 | 44.0 | 42.6 | **40.5** | 14% |
| 2024-25 | 56.2 | 50.5 | 54.5 | 48.8 | **45.6** | 15% |
| 2025-26 | 56.1 | 46.2 | 53.9 | 44.1 | **41.8** | 13% |
| Pooled | 52.6 | 47.0 | 50.8 | 45.2 | **42.6** | 14% |

- **Codex's choices, kept.** Injury-management-only stretches are planned games off for a known condition (the rest model covers those). Stretches already underway at the team's first game are offseason, preseason or carried-over injuries (the season-start injuries cover those).
- **Two more, so each real absence counts once, as the game draws it:**
  - the second half of an injury split by a trade;
  - a stretch that directly continues another medical stretch with no game played between (about 5%): the report changed the body part or side, or an injured player fell ill. The game can't draw an injury while a player is out.
- **Season-to-season variation:** 40.5 to 45.6 a team (about ±6%). 2024-25 was the high year, as in the tracker.

**Length of each absence** (regular-season games, a continued absence counted whole):

| | 1 | 2-5 | 6-10 | 11-20 | 21+ | Games lost per team |
|---|---:|---:|---:|---:|---:|---:|
| 2023-24 | 48.8% | 31.9% | 8.8% | 6.6% | 4.0% | 180 |
| 2024-25 | 46.8% | 34.6% | 9.3% | 5.4% | 3.8% | 195 |
| 2025-26 | 46.7% | 33.1% | 9.6% | 6.8% | 3.7% | 187 |
| Tracker 2021-25 | 40% | 35% | 11% | 7% | 6.5% | |

- Injuries alone are a little longer (43-45% one game); illness is 66-72% one game.
- The tracker under-logs short absences much more than long ones.

**By minutes and age** (the game's real players, 10+ games, new injuries and illnesses per 82 games played, pooled over the three seasons; tracker's game-costing entries for the same players in brackets):
- Minutes: under 10: 3.17 (1.81); 10-20: 2.94 (1.87); 20-30: 4.00 (2.39); 30+: 4.95 (3.19).
- Age: under 23: 3.32 (2.04); 23-25: 3.74 (2.37); 26-28: 4.25 (2.67); 29-31: 5.11 (3.06); 32+: 4.32 (2.73).
- The tracker caught about 60% of what cost a game for these players.

## 2. What changed

### Base rates (`scripts/build_injury_model.py`)
- Each body part's gameplay rate is now set so the real players' 2023-24 to 2025-26 seasons reproduce the complete count of new in-season absences: 3,377 over 69,515 games, **48.6 per 1,000 games**. This replaces the tracker's 2021-25 totals.
  - 39 injuries with no body part are spread over the parts in proportion (+1.4%).
- **Matched to how the game works** (each is something the old anchor did differently from the engine):
  - **Injuries that cost no game.** The game also draws one-day absences that cost no game (4-14% of draws by part, 19% of illnesses). The complete record only sees absences that cost a game, so the anchor counts expected draws times each part's share that cost a game.
  - **History.** A new career's history: the tracker plus the public injuries it lacks, now for all three seasons (v4). The anchor uses the same history for the real seasons, at the 0.75 weight.
  - **Repeat injuries within a season.** The game adds each injury to the player's history the day it happens. The anchor now does the same with the real season (eight stretches per season, real injuries counted as they happen). Without this, the season's repeat injuries were counted twice: once in the base rate, once through the history.
- **Slopes kept** (minutes, age, history weight 0.75). On the three complete seasons the model's predicted rates by minutes and age band agree within the season-to-season spread:
  - the 10-20 minute band runs about 13% below the others relative to prediction;
  - the 29-31 age band runs about 17% above;
  - but each moves a lot between seasons (29-31: 4.06, 5.75, 5.51 per 82; 10-20 vs 20-30: 0.79, 0.84, 0.61 against the model's 0.86).
  - Nothing clearly contradicts the slopes.
- **Effect on the rates:** per part, the new rates move between -0.15 and +0.30 on the log scale (illness +0.26, thumb +0.30, hamstring -0.15, wrist -0.16). The overall level is close to before. The higher real count is offset by the denser starting history and the in-season repeats.

### Injury lengths (`correct_recovery_lengths` in the builder)
- The game's recovery times are the tracker's recorded absences, and the tracker misses short ones far more than long ones. Each body-part group's pool is re-weighted to the complete records' mix of lengths:
  - the length mix is all players' new in-season absences in the three seasons, Kaplan-Meier, so an absence still running at the team's last game counts as at least that long;
  - within a length band the tracker's real durations and diagnoses stay as they are;
  - parts keep their differences inside a group (an Achilles absence stays longer than a calf one);
  - each part's share of draws that cost a game is unchanged.
- Changes (complete / tracker pool, % in 1 / 2-5 / 6-10 / 11-20 / 21+ games):
  - knee: 47/27/9/7/10 against 36/32/10/7/15;
  - ankle/foot/toe: 43/34/11/6/6 against 34/37/12/8/9;
  - hip/groin: 42/37/14/3/3 against 34/40/13/7/7;
  - arm/hand: 42/28/8/9/12 against 34/29/10/14/14;
  - back: 49/30/8/7/6 against 44/36/7/7/6;
  - smaller moves for thigh, calf/Achilles, head and illness.
- **Why this is part of the anchor.** Raising the count alone (first pass, `anchor_s17/s29`) took the game to 51 injuries and 269-301 games lost a team (real 180-195). The top-30 median fell to 64.5 / 51.5.

### Illness in history: tested, stays out
- **The case for it.** Over the three seasons, counting illness in the history predicts the next illness much better (log-likelihood +31.5) and the next injury a little better (+5.7). The slopes were fit with illness counted.
- **Why it stays out.** In the game it feeds on itself.
  - Four health-only seasons back to back (seed 17): illness rose from 7.7 to 12.5 a team (real 5.6-7.0), and all spells from 46.6 to 53.7.
  - Illness history per rotation player doubled (0.42 to 0.98).
  - The illness slopes come from the tracker, which logs few illnesses, so they don't carry over to a complete history.
  - Left out, the rate holds (below).
- **Next step:** refit the slopes on complete records first.

### Code
- `injury_model.py`: evidence file v4 (falls back to v3, then v2). Comments updated. History still excludes illness, with the reason above.
- `health.py`: unchanged at the end.
- `tests/test_injury_anchor.py` (new, 6 tests):
  - which stretches count;
  - absences joined across a change of body part;
  - season-end absences;
  - the Kaplan-Meier band shares;
  - the length correction;
  - the anchored model file.
- `tests/test_star_injuries.py`: v4 names and the fallback chain.

## 3. Before and after
Full regular seasons, all 30 teams AI-coached, fixed rosters, real opening-night injuries, seeds 17 / 29. "Before" is current main rerun today.

| | Real (complete records) | Before | **After** |
|---|---|---|---|
| Injuries costing a game, per team | 40.5-45.6 | 40.1 / 39.9 | **43.3 / 43.6** |
| 1 / 2-5 / 6-10 / 11-20 / 21+ games | 47 / 33 / 9 / 6 / 4% | 40 / 35 / 12 / 7 / 6% | **48 / 32 / 10 / 5 / 4.5%** |
| Games lost per team | 180-195 | 229 / 241 | **203 / 207** |

**Heavy-minute players (30+ minutes; real is 2025-26 box scores)**

| | Real | Before | **After** |
|---|---|---|---|
| Median games | 68 | 65 / 65 | **68 / 66** |
| Mean games | 61.7 | 61.7 / 59.4 | 64.2 / 62.2 |
| Single games missed | 2.4 | 2.5 / 2.7 | 3.1 / 3.1 |
| 2-10 game stretches | 5.6 | 6.2 / 5.4 | 5.4 / 5.7 |
| 11+ game stretches | 4.0 | 5.8 / 8.2 | **4.3 / 6.4** |

**The 30 best-rated players**

| | Real | Before | **After** |
|---|---|---|---|
| Median games | 64.5-65.5 | 63.5 / 59.5 | **67.5 / 63.0** |
| Mean games | 55.4-58.9 | 62.5 / 53.2 | 65.0 / 56.0 |
| Under 60 games | 9-14 | 12 / 15 | 8 / 11 |

**Rates per 82 games played by minutes** (sim actual minutes; real 2025-26 box scores / complete three-season panel):

| | Real | Before | **After** |
|---|---|---|---|
| Under 10 | 2.2 / 3.2 | 1.5 / 1.4 | 1.7 / 1.6 |
| 10-20 | 2.9 / 2.9 | 2.8 / 2.7 | 3.0 / 3.0 |
| 20-30 | 4.7 / 4.0 | 3.9 / 4.2 | 4.3 / 4.4 |
| 30+ | 5.1 / 5.0 | 4.3 / 4.3 | 4.6 / 4.7 |

**By age:**

| | Real | Before | **After** |
|---|---|---|---|
| Under 23 | 3.4 / 3.3 | 2.5 / 2.7 | 2.7 / 2.8 |
| 23-25 | 3.9 / 3.7 | 2.6 / 2.7 | 2.7 / 2.8 |
| 26-28 | 4.2 / 4.3 | 3.5 / 3.5 | 3.8 / 3.9 |
| 29-31 | 5.8 / 5.1 | 3.9 / 3.5 | 4.0 / 3.8 |
| 32+ | 4.2 / 4.3 | 3.4 / 3.5 | 3.7 / 3.7 |

- Every band moved toward real, and every band from 10 minutes up is now within about 10% of the complete records.
- The age bands are still 10-30% low. The game spreads its minutes over more players: about 13 appearances per team game against about 11 real. That puts more of each age band's games at low minutes. The same gap was there before.
- The 20-30 and 30+ minute bands sit 5-15% under real per game. More player-games (about 6%) bring the per-team totals back up.

**League rate over four seasons** (health only, fixed rosters, spells costing a game per team, seeds 17 / 29; `scripts/research/injury_multiseason_check.py`, log `output/injury-anchor/multiseason_final.log`):
- After: 44.9 / 46.1 / 43.6 / 47.1 and 48.4 / 50.7 / 48.4 / 47.3. Steady (±5%, no trend).
- Before (STAR-INJURIES): 41.5 / 41.6 / 39.8 / 41.7 and 42.9 / 44.4 / 44.1 / 42.9.
- This check plays every rostered player at his planned minutes every game, so its level runs above the full season's.

**Fixed-roster health replay** (`scripts/research/injury_season_check.py`; every player exposed every game, zero-game injuries included):
- 57.4 / 59.8 spells a team, against 51.5 / 53.2 before.
- Games missed are down: 7,219 / 7,298 against 7,903 / 8,016.
- The 90th percentile is 24 days, against 31-33.

## 4. Rebuild v4 (coordinator, in main)
```sh
PYTHONPATH=src .venv/bin/python scripts/build_injury_model.py --write
```
- This writes `data/canonical/injury_model_v2.json` (tracked; identical to the one committed here) and the git-ignored `data/canonical/injury_player_evidence_v4.json`.
- It reads the tracker files under `data/research/bbi/tools/` and the three public files, and takes about 15 s.
- `.gitignore` lists v4.
- Until v4 exists the engine falls back to v3: the 2023-25 additions are missing, which is not the tested setting.

## 5. Speed and tests
- **Health simulation:** 2.4-2.6 s per health-only season, about 0.4 s per simulated month (unchanged).
- **Full fixed-roster season:**
  - wall time 56.5 / 57.7 s against 59.0 / 57.9 s before;
  - game simulation 33.6 / 34.2 s against 34.4 / 34.3 s.
- **Determinism:** draws stay seeded and in the same order. Outcomes change because the rates and recovery tables changed.
- Tests: focused injury modules OK (`test_injury_anchor`, `test_star_injuries`, `test_injury_followups`); core `scripts/run_core_tests.sh`: 338 run, OK (2 skipped); `run_tests_parallel.py --workers 2 --match "injur|health|rest_model|fatigue|games_played|new_career|star_injur"`: 1,101 tests, 0 failures, 0 errors (19 skipped). The foundation test's health-replay ceiling (60 a team) still holds (57.4 / 59.8 in the fixed-roster replay; close to it).
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.

## 6. What's left
1. **Single-game absences for regulars rose:** heavy-minute players miss 3.1 single games against 2.4 real (before 2.5-2.7).
   - More of the game's injuries are now one game long, as in the complete records.
   - The rest model's coach-rest share (`rest_model.REST_COACH_SHARE`, 0.78) subtracts the injury model's one-game absences from the real single-game rate. It was set for the old, longer injuries.
   - Recalibrate it (outside this task's files).
2. **The game plays about 13 players a game against about 11 real.** That adds injury exposure at low minutes and pushes the age bands' mix toward bench minutes. This is a rotation question, not an injury one.
3. **Illness in history:** refit the slopes on the complete records (2023-26), then retest. The predictive gain is real.
4. **Refit the slopes on complete records.** The tracker's per-player injury counts are about 60% complete for game-costing injuries. The minutes and age slopes look consistent for now, but the 29-31 age band and the 10-20 minute band are worth a look once there's a fourth complete season.
5. **The top-30 spread between seeds** (67.5 against 63) is mostly a few long injuries. Real 64.5-65.5 sits between the seeds.
6. **Anchor approximation.** Games are spread evenly across each real season when adding in-season history, though injured players don't play while out. This slightly overstates post-injury exposure, so the rate comes out a little low (the sims land in the real range anyway).

## Files
- **Changed:**
  - `scripts/build_injury_model.py`: anchor, length correction, three public files, v4;
  - `src/nba_gm_data/injury_model.py`: v4 with fallbacks, comments;
  - `data/canonical/injury_model_v2.json`: rebuilt;
  - `.gitignore`: v4;
  - `scripts/research/injury_multiseason_check.py`: history density and illness columns;
  - `scripts/research/injury_rate_bands.py`: tracker seasons constant;
  - `tests/test_star_injuries.py`.
- **New:** `scripts/research/injury_anchor_measure.py`, `tests/test_injury_anchor.py`.
- **Harness** (`output/injury-anchor/`):
  - `sim_season.py`, `run2.sh`, `analyze.sh`, `exposure_check.py`, `multiseason_variant.py`, `top30_split.py`;
  - runs `before_`, `anchor_` (rates only), `new_` (with illness in history), `final_` (s17 / s29);
  - model snapshots `injury_model_{before,anchor,new,final}.json`.

## Resume state
Done. Committed on the branch, not pushed; board row set to review. The coordinator rebuilds v4 in main with the command in section 4.
