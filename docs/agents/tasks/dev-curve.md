# DEV-CURVE: player development and aging fitted to real NBA evidence

_Owner: Claude (Opus agent, worktree branch `worktree-agent-a1caf3189f4cf1a6f`). Started 2026-11-21. User approved._

## TL;DR
- **Young stars keep growing now.** Real players improve about as fast whether they start good or ordinary; the game used
  to slow any rating near the top to a crawl, so the best young players stopped at 22-23. That slowdown is gone for the
  new ratings, young players grow into their mid-20s, and the peak is at 25-26 like the real league.
- **Physical ratings stop over-reacting.** Development now moves each of the 94 inputs by the same share of its own
  league spread, and the extra youth growth goes to skills, not conditioning. Seasons where a player's stamina jumps or
  drops 10+ points fall from about 4% of players to under 1%.
- **Both scorecards are unchanged** (they replay opening-day ratings): real-stat scorecard 18/18, betting test identical.
  AFTER_RUN_LINE

## What changed (plain language)
1. **No slowdown for good players** (the new ratings only; the older ratings keep their rules). Before, a hidden rating
   at 50 grew at full speed, one at 71 at half speed and one at 88+ at 8%, and a rating at 84+ also got a third less
   practice focus. The real evidence says this is wrong: when you measure a player's level one season *before* the change
   (so a lucky season doesn't make him look better than he is), real top-third young players improve as much as the
   bottom third (ages 21-22: top +0.88, bottom +0.76 points of box plus-minus a season). The apparent "stars improve
   less" pattern in raw numbers is mostly a lucky season being followed by a normal one.
2. **A new age curve**, fitted to Basketball Index LEBRON (the engine's player value is fitted to LEBRON): about +1.0 a
   season at 19, +0.8 at 20, +0.5 at 21, +0.3 at 22, +0.2 at 23-24, flat at 25-27, then -0.1 at 28-29, -0.2 at 30-32,
   -0.5 at 33-35 and -0.6 at 36+. Decline starts a little earlier and is a little steeper than before.
3. **Prospect "upside" counts for less.** Without the old slowdown, the full upside multipliers (up to 3.8 times normal
   growth) turned most top-20 picks into stars. They are now narrowed (fourth root; the order is kept, busts and
   breakouts still happen).
4. **Minutes matter a bit less.** 30% of growth no longer depends on playing time: real young players outside the
   rotation still improve (18% of age-20 players under 1,000 minutes later made the top 50).
5. **Physical inputs move by their own spread.** Conditioning, recovery, agility and speed vary about a third as much
   across the league as a typical skill grade, so the same grade-point step moved them three times as far relative to
   other players. Each input now moves by the same share of its own league spread (table:
   `data/canonical/development_input_spread.json`). Physical ratings also keep the older, gentler youth curve.
6. **No clipping at 100** on developed input grades (rule 3). Grades keep a floor at 0.

Files: `health.py` (development functions: `monthly_trait_delta`, `development_age_factor`, `development_trait_focus`,
`advance_development`, constants at the top), `development_outlook.py` (passes the right curve),
`ratings_model.py` (routing by spread, no clamp at 100), `data/canonical/development_input_spread.json`, research
scripts `scripts/research/dev_curve_*.py`, tests `tests/test_dev_curve.py` (+ updates to `test_ratings_model`,
`test_rating_ceiling`, `test_unused_ratings_2`). Not touched: `trait_adapter.py`, `impact_value.py`, `stage2/`, `sim.py`,
injuries, `talent.py`.

## How it was measured
- **Real evidence**: Codex's panel (`data/research/development_evidence.json`): 2004-05 to 2025-26, box plus-minus (BPM)
  change for players with 1,000+ minutes in both seasons, by age and starting third among same-age players.
- **The game, like with like**: `scripts/research/dev_curve_box.py` fits real BPM on the box-score fields the game keeps
  (minutes, points, rebounds, assists, steals, blocks, turnovers, shooting), using 2,323 real seasons of today's players
  (ESPN totals matched to the BPM panel): weighted R-squared 0.87. The same formula is applied to each simulated season,
  with the same 1,000-minute filter and thirds. On real players, the estimate's season-to-season changes track real BPM
  changes closely (it runs about 0.1-0.2 higher at 22-29).
- **Fast tuning probe**: `scripts/research/dev_curve_talent.py` develops the opening league plus two made-up draft
  classes month by month for seven seasons (no games), recording the engine's player value. About a minute a run.
- **Five-season runs**: `scripts/league_health_audit.py advance --career --seasons 5` (seed 17, Golden State hands-off)
  on the Azure worker, before (commit 7b05da8) and after; `scripts/research/dev_curve_report.py compare` builds the tables.

AFTER_RUN_TABLES

## Development-only probe: seven seasons, two seeds (engine value, LEBRON units)
Change per season by age, all players with 12+ minutes in both seasons (before = commit 7b05da8, after = final constants):

| Ages | Real LEBRON | Before | After |
|---|---:|---:|---:|
| 19-20 | +0.85 | +0.40 | +0.71 |
| 21-22 | +0.39 | +0.28 | +0.50 |
| 23-24 | +0.17 | +0.14 | +0.21 |
| 25-27 | -0.02 | +0.02 | +0.00 |
| 28-29 | -0.11 | -0.07 | -0.07 |
| 30-32 | -0.22 | -0.15 | -0.19 |
| 33-35 | -0.47 | -0.36 | -0.41 |
| 36-39 | -0.62 | -0.51 | -0.59 |

Peak age: real 26, before 27, after 26. By starting third (after), ages 21-22: bottom +0.37, middle +0.56, top +0.57
(real, level taken from the season before: +0.76 / +0.64 / +0.88 BPM: no penalty for being good). The probe runs a bit
above the real curve at 21-24 on purpose: played seasons grow about a third less (see the five-season tables).

**Where stars come from** (players aged 19-23 at the start, reaching today's top-10 / top-25 / top-50 level within seven
seasons; real = players 19-23 in 2005-2019, reaching that league rank within seven seasons):

| Starting level | Real | Before | After |
|---|---|---|---|
| Top third | 16% / 37% / 62% | 8% / 31% / 50% | 24% / 42% / 64% |
| Middle third | 5% / 17% / 36% | 1% / 5% / 11% | 10% / 18% / 28% |
| Bottom third | 3% / 6% / 14% | 0% / 1% / 4% | 2% / 4% / 7% |
| Below the minutes cut | 0.5% / 3.5% / 9% | 0% / 0% / 1% | 0% / 1% / 6% |

By draft slot (this year's real draftees plus two made-up classes; small samples): picks 1-3 real 20% / 42% / 60%,
before 8% / 33% / 42%, after 17% / 42% / 42%; picks 4-10 real 9% / 15% / 34%, before 18% / 32% / 46%, after 25% / 36% /
54%; picks 11-30 real 3% / 9% / 20%, before 8% / 11% / 19%, after 9% / 14% / 20%; second round real 1% / 3% / 6%,
before 0 / 0 / 1%, after 0 / 0 / 2%. Picks 4-30 already produced too many stars before this task (made-up classes enter
strong); see "What's left".

**Top of the league** (engine value): first-time top-five players per season, before 0.8, after 1.0 (real 1.0); new or
returning top-five players 0.9 → 1.1 (real 1.9 in box plus-minus, which adds season-to-season noise the probe lacks).
Top-five average after seven seasons: before 7.12 → 6.64 (the league loses its superstars), after 7.12 → 7.87. Tenth
best: 5.11 → 5.26 before, → 6.50 after. The probe has no new draft classes after 2027 and no injuries; in the played
five-season run the top stays flat (tables above).

**Physical over-reaction**: stamina changes of 5+ points in a season: 10.7% → 6.4% of player-seasons; 10+ points: 3.8%
→ 0.6% (under 1% for players 22 and under). Yearly physical-grade changes in league standard deviations (90th
percentile): agility 0.36 → 0.16, speed 0.40 → 0.18, strength 0.35 → 0.23, balance 0.57 → 0.28, conditioning 0.17 →
0.14, recovery 0.30 → 0.14.

**Older stars**: top-25 the season before vs others (engine value): 33-35 before -0.41 / -0.35, after -0.49 / -0.41
(real LEBRON -0.11 / -0.54). The game's stars still age a little faster than other players at 33-35, unlike the real
league (see "What's left").

## Named examples (probe, average of two seeds: engine value at the start, then after each season)
- **Wembanyama** (22): before 7.1 → 7.4 → 7.6 → 7.7 → 7.9 → 7.3 → 7.6 → 7.5; after 7.1 → 7.9 → 8.5 → 8.8 → 9.0 (26) →
  8.3 → 8.8 → 8.6.
- **Flagg** (19): before 2.3 → 4.9 by 25; after 2.3 → 3.7 → 5.0 → 5.6 → 6.6 → 6.9 → 7.7 (25) → 7.5.
- **Dybantsa** (19): before 0.4 → 2.6 by 26; after 0.4 → 0.7 → 1.5 → 2.2 → 3.5 → 3.6 → 4.1 → 4.8.
- **Darryn Peterson** (19): before peaks 5.4 at 23; after 7.9 at 24. **Cameron Boozer**: before 3.3, after 5.6 by 26.
- **Best made-up prospects** (after): seed 1 Samir Onyeka (pick 10) 8.1 at 24, Kobe Bouanga (pick 12) 6.9, Jonas Lemaire
  (pick 23) 6.8 at 23; seed 2 Bouanga 7.7, Dante Barrett Foster (pick 13) 7.0, Onyeka 6.8.
- Veterans keep their shape: Jokić 8.0 → 5.3 by 38, Gilgeous-Alexander 7.7 → 6.1 by 35, Giannis 6.3 → 2.6 by 38.

## Scorecards
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**; the JSON output is
  byte-identical to the pre-change code's.
- Betting test, 20 runs: seed 1001 Brier 0.2041, log loss 0.5975, spread error 4.097, totals error 5.513; seed 2001
  0.1972 / 0.5808 / 3.923 / 5.545. Identical to before (both replay opening-day ratings; development does not run).
- Tests: `tests.test_dev_curve` (new), `test_ratings_model`, `test_rating_ceiling`, `test_prospect_learning`,
  `test_development_outlook`, `test_unused_ratings_2` pass. Full suite (2 workers): 2,369 tests, 1 failure + 19 errors,
  all unrelated: missing git-ignored reference files in this worktree (experimental engine, packaging inventory, the
  uncompressed inputs file present for tests), and `test_neutral_coordinators` fails the same way on the main checkout.

## Judgement calls
- **Talent target in LEBRON units, box target in BPM units.** The engine's player value is fitted to LEBRON, and in the
  simulated seasons one point of engine value is worth 1.42 points of the box-score estimate, the same ratio as real
  BPM to LEBRON spreads (2.75 / 1.9). So matching LEBRON in talent should match BPM in box scores.
- **Growth is set a bit below the raw real averages at 19-20.** Matching them fully inflated the top of the league
  (the tenth-best player rose from 5.1 to 7.3 in seven seasons) because the real averages only count players who keep
  1,000+ minutes (the ones who developed) and the game's value scale is narrower than real LEBRON (spread 1.57 vs 1.9).
- **Laptop rule**: the free-swap reading stayed under 2 GB all afternoon because macOS shrinks its swap file to fit;
  I ran the light jobs (one at a time, `nice`) once the load was under 20 and free memory was 40-50%.

## What's left
1. **Made-up draft classes produce too many stars from picks 4-30** (before and after this task): 25% of picks 4-10
   reach today's top-10 level in seven seasons vs 9% real. Their entry level and potential come from the draft
   generator (`draft.py` / `talent.py`), not development. Worth its own task.
2. **Old stars age a bit faster than old role players** (real: slower at 33-35). Partly because involvement falls with
   skill, which costs stars more value. A blanket "stars age slower" rule is not supported by the evidence (they decline
   faster at 30-32), so left as is.
3. `talent._trait_ceiling` still caps a made-up draftee's skill capacity at 97 (latent clip; not checked as binding here).
4. `physical_evidence` (offline input build) calls `monthly_trait_delta` without a curve, so it keeps the older curve;
   that keeps opening ratings reproducible if the inputs are rebuilt.
5. The full ten-season check should be re-run on main once this merges.

## Resume state
Merged main (27aa06b) at 748a35b; final code 5d81feb. Five-season runs on the Azure pool, seed 17, GSW hands-off:
`output/dev-curve/mainbase` (main, the before) and `output/dev-curve/final2run` (final code; the scratchpad copy of
azure_worker.py with a fix for the pool's missing `monthly_hour_cap` lookup was used to start it). Earlier runs on the
pre-merge base: `before`, `after` (first constants), `after2` (more 21-24 growth). When both finish:
`dev_curve_report.py game` on each, `compare mainbase final2run probe-old probe-new`, fill the tables, board row to
review, commit.
