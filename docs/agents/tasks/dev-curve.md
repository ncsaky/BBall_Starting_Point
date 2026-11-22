# DEV-CURVE: player development and aging fitted to real NBA evidence

_Owner: Claude (Opus agent, worktree branch `worktree-agent-a1caf3189f4cf1a6f`). 2026-11-21/22. User approved. Status: review._

## TL;DR
- **Young stars keep growing now, and the league keeps its superstars.** The game used to slow any rating near the top to
  a crawl, so the best young players stopped at 22-23 and the top of the league shrank. That slowdown is gone for the new
  ratings. In five played seasons Wembanyama goes 7.6 → 8.7 by 26 (before: flat at 7.3), Cooper Flagg 2.8 → 6.2 by 22
  (before: 3.9), and the top-five average holds at about 7.3-7.5 instead of falling to 6.9.
- **Physical ratings stop over-reacting.** Seasons where a player's stamina jumps or drops 10+ points fall from about 4%
  to under 1%. Each of the 94 inputs now moves by the same share of its own league spread.
- **Both scorecards are unchanged** (18/18; betting test identical to main), because they replay opening-day ratings.
  Still short of the real curve: growth at 23-24 in played seasons (about +0.06 a season vs +0.17 real), and the
  box-score peak lands at 24 rather than 26.

## What changed (plain language)
1. **No slowdown for good players** (the new ratings only; the older ratings keep their rules). Before, a hidden rating at
   50 grew at full speed, one at 71 at half speed and one at 88+ at 8%, and a rating at 84+ got a third less practice
   focus. The real evidence says this is wrong: when a player's level is measured one season *before* the change (so a
   lucky season doesn't make him look better than he is), real top-third young players improve as much as the bottom
   third (ages 21-22: top +0.88, bottom +0.76 box plus-minus points a season). The "stars improve less" pattern in raw
   numbers is mostly a lucky season followed by a normal one.
2. **A new age curve**, fitted to Basketball Index LEBRON (the engine's player value is fitted to LEBRON): about +1.0 a
   season at 19, +0.8 at 20, +0.5 at 21, +0.3 at 22, +0.2 at 23-24, flat at 25-27, then -0.1 at 28-29, -0.2 at 30-32,
   -0.5 at 33-35 and -0.6 at 36+.
3. **Prospect "upside" counts for less.** Without the old slowdown, the full upside multipliers (up to 3.8 times normal
   growth) turned most top-20 picks into stars. They are narrowed (fourth root; the order is kept, busts and breakouts
   still happen). Made-up draftees, which have their own learning runway, keep the smaller growth at 21-24, so their
   year-four results stay where they were (real-evidence test `test_prospect_realism` passes: 18% of made-up top-10 picks
   are top-25 players by year four, main 17%, real classes 1-20%).
4. **Minutes matter a bit less.** 30% of growth no longer depends on playing time (18% of real age-20 players under
   1,000 minutes later made the top 50).
5. **Physical inputs move by their own spread.** Conditioning, recovery, agility and speed vary a third to two-thirds as
   much across the league as a typical skill grade, so the same grade-point step moved them much further relative to
   other players. Each input now moves by the same share of its own league spread
   (`data/canonical/development_input_spread.json`), and physical ratings keep the older, gentler youth curve.
6. **No clipping at 100** on developed input grades (rule 3). Grades keep a floor at 0.

Files: `health.py` (development functions and the constants at the top), `development_outlook.py` (passes the right
curve), `ratings_model.py` (routing by spread, no clamp at 100), `data/canonical/development_input_spread.json`, research
scripts `scripts/research/dev_curve_{box,talent,report,spread}.py` plus `data/research/dev_curve_box_bpm.json`, tests
`tests/test_dev_curve.py` and updates to `test_ratings_model`, `test_rating_ceiling`, `test_unused_ratings_2`. Not
touched: `trait_adapter.py`, `impact_value.py`, `stage2/`, `sim.py`, injuries, `talent.py`.

## How it was measured
- **Real evidence**: `data/research/development_evidence.json` (2004-05 to 2025-26): box plus-minus (BPM) change for
  players with 1,000+ minutes in both seasons, by age and starting third among same-age players.
- **Like with like**: `dev_curve_box.py` fits real BPM on the box-score fields the game keeps (minutes, points,
  rebounds, assists, steals, blocks, turnovers, shooting) over 2,323 real seasons of today's players (weighted R-squared
  0.87) and applies the same formula to each simulated season, same 1,000-minute filter and thirds. On real players its
  season-to-season changes track real BPM closely (about 0.1-0.2 higher at 22-29). In the simulated seasons one point of
  engine value is worth 1.33-1.42 box points, the same ratio as real BPM to LEBRON spreads (2.75 / 1.9).
- **Tuning probe**: `dev_curve_talent.py` develops the opening league plus two made-up draft classes month by month for
  seven seasons (no games), two seeds. About a minute a run.
- **Five-season runs** on the Azure pool (seed 17, Golden State hands-off), both on the merged base (main 27aa06b):
  before = main, after = this branch (5d81feb). Tables: `dev_curve_report.py compare`.

## Five played seasons: main vs this branch (2026-27 to 2030-31)

### Engine player value (LEBRON units), change per season

| Ages | Real LEBRON | Before | After | Probe before | Probe after |
|---|---:|---:|---:|---:|---:|
| 19-20 | +0.85 | +0.45 | +0.68 | +0.40 | +0.73 |
| 21-22 | +0.39 | +0.27 | +0.38 | +0.28 | +0.50 |
| 23-24 | +0.17 | +0.07 | +0.06 | +0.14 | +0.20 |
| 25-27 | -0.02 | -0.01 | -0.00 | +0.02 | +0.00 |
| 28-29 | -0.11 | -0.04 | -0.04 | -0.06 | -0.07 |
| 30-32 | -0.22 | -0.17 | -0.22 | -0.15 | -0.20 |
| 33-35 | -0.47 | -0.42 | -0.53 | -0.36 | -0.43 |
| 36-39 | -0.62 | -0.57 | -0.62 | -0.52 | -0.61 |

### Simulated box-score impact (BPM scale), change per season, 1,000+ minutes both seasons, by starting third

| Ages | Real all | Real bottom / middle / top | Before all | Before bottom / middle / top | After all | After bottom / middle / top |
|---|---:|---|---:|---|---:|---|
| 19-20 | +1.18 | +1.65 / +1.16 / +0.66 | +0.34 (96) | +0.93 / +0.24 / -0.10 | +0.68 (105) | +1.19 / +0.43 / +0.39 |
| 21-22 | +0.65 | +1.12 / +0.61 / +0.30 | +0.36 (116) | +0.84 / -0.02 / +0.30 | +0.51 (131) | +0.99 / +0.41 / +0.12 |
| 23-24 | +0.28 | +0.98 / +0.22 / -0.24 | +0.01 (94) | +0.41 / +0.01 / -0.27 | -0.15 (107) | -0.23 / -0.15 / -0.10 |
| 25-27 | -0.10 | +0.52 / -0.20 / -0.51 | -0.30 (183) | +0.58 / -0.34 / -0.75 | -0.17 (175) | +0.34 / -0.41 / -0.34 |
| 28-29 | -0.26 | +0.49 / -0.38 / -0.75 | -0.03 (111) | +0.52 / -0.07 / -0.42 | -0.32 (107) | +0.38 / -0.56 / -0.63 |
| 30-32 | -0.44 | +0.14 / -0.29 / -1.02 | -0.46 (115) | +0.03 / -0.59 / -0.62 | -0.49 (99) | -0.22 / -0.42 / -0.67 |
| 33-35 | -0.46 | +0.15 / -0.54 / -0.86 | -0.56 (41) | -0.13 / -0.77 / -0.65 | -0.47 (31) | -0.11 / -0.73 / -0.49 |
| 36-39 | -0.85 | -0.44 / -1.24 / -0.93 | -0.93 (15) | -1.42 / -0.52 / -0.44 | -0.74 (17) | -1.08 / -0.67 / -0.46 |

Pair counts in brackets; one seed, so single cells move by a few tenths. Peak age by the running sum: real 26, before 24,
after 24 (box); engine value 26 before, 27 after. The same-season thirds show the expected regression to the mean in
both the real league and the game (bottom thirds gain most).

### Older players (box), top-25 the season before vs others
Real: 28-29 -0.38 / -0.21, 30-32 -0.64 / -0.41, 33-35 -0.02 / -0.52. Before: +0.21 / -0.13, -0.34 / -0.47, -0.16 /
-0.72. After: -0.29 / -0.25, -0.54 / -0.73, -0.55 / -0.55 (5-14 stars per cell). In engine value (probe, larger
samples) stars at 33-35 decline about as fast as others (-0.45 / -0.43); in the real league they decline less.

### Star formation and top-five turnover (box-score top five among 1,000-minute players)
| | Real (22 seasons) | Before | After |
|---|---|---|---|
| First-time top-five players a season | 1.0 | 1.25 (Jalen Williams; Edwards, Barnes; Touray; Ngongba) | 0.5 (Edwards; Erick Dampier Jr.) |
| New or returning top-five players a season | 1.9 | 2.0 | 1.5 |
| Top-five average (box) | 8.9 | 8.6 → 8.3 | 8.6 → 8.4 |
| Top-five average (engine value), first → fifth February | | 7.21 → 6.87 | 7.27 → 7.45 |
| Tenth-best / 50th / 150th (engine value), fifth February | | 4.73 / 3.23 / 2.03 | 5.50 / 3.47 / 2.17 |

Five seasons is short for first-timers (the after run's young stars, Flagg 6.2 and Peterson 7.3 engine value, are top-15
but not yet top-five by box score). In the seven-season probe, first-time top-five players arrive at 1.0 a season after
the change (0.8 before), almost all 20-25-year-olds (Flagg, Peterson, Acuff, Okorie, Wagler, Bouanga, Onyeka).

### Named examples (five played seasons, engine value each February, before → after)
- **Wembanyama** (22 → 26): before 7.3, 7.2, 6.8, 7.1, 7.3; after 7.6, 8.0, 7.9, 8.3, 8.7.
- **Cooper Flagg** (19 → 23): before 2.5, 3.4, 4.0, 3.9, 3.4; after 2.8, 4.6, 5.9, 6.2, 5.9.
- **AJ Dybantsa** (19 → 23): before 0.8, 1.5, 2.0, 2.4, 2.7; after 1.0, 2.3, 3.2, 3.9, 4.2.
- **Darryn Peterson**: before peaks 5.1; after 2.8 → 7.3 at 22. **Cameron Boozer**: before 3.0, after 5.5 by 23.
- **Best made-up prospects** (after): Reese Alston (pick 13) 3.4 → 5.5 by 21; AJ Williams (pick 7) 1.8 → 4.4; Cayden
  Daughtry (pick 10) 3.0 → 4.2; Quentin Coleman (pick 3) 2.3 → 4.1 by 22. Before, the best was Coleman at 4.0.
- Veterans keep their shape: Jokić 8.0 → 6.4 by 35 (before 6.8), Gilgeous-Alexander 8.3 at 32 in both.
- In the seven-season probe: Wembanyama peaks 9.0 at 26 (before 7.9), Flagg 8.0 at 25 (before 5.0), Dybantsa 5.1
  (before 2.9).

## Development-only probe (seven seasons, two seeds), merged base
**Where stars come from** (players aged 19-23 at the start, reaching today's top-10 / top-25 / top-50 level within seven
seasons; real = players 19-23 in 2005-2019, reaching that league rank within seven seasons):

| Starting level | Real | Before | After |
|---|---|---|---|
| Top third | 16% / 37% / 62% | 12% / 32% / 56% | 24% / 43% / 69% |
| Middle third | 5% / 17% / 36% | 1% / 6% / 12% | 11% / 18% / 30% |
| Bottom third | 3% / 6% / 14% | 0% / 1% / 4% | 2% / 5% / 6% |
| Below the minutes cut | 0.5% / 3.5% / 9% | 0% / 0% / 2% | 0.5% / 3% / 8% |

By draft slot (this year's real draftees plus two made-up classes; small samples), top-10 / top-25 / top-50: picks 1-3
real 20 / 42 / 60%, before 8 / 33 / 42%, after 17 / 33 / 42%; picks 4-10 real 9 / 15 / 34%, before 18 / 36 / 57%, after
25 / 36 / 54%; picks 11-30 real 3 / 9 / 20%, before and after 8 / 15 / 20%. Picks 4-30 already produced too many stars
before this task.

**Physical over-reaction**: stamina changes of 5+ points in a season 10.7% → 6.4% of player-seasons; 10+ points 3.8% →
0.6%. Physical-grade changes per season in league standard deviations (90th percentile): agility 0.36 → 0.16, speed
0.40 → 0.18, strength 0.35 → 0.23, balance 0.57 → 0.28, recovery 0.30 → 0.14.

## Scorecards and tests (merged base)
- Real-stat scorecard: **18/18**, output byte-identical to main's.
- Betting test, 20 runs: seed 1001 Brier 0.2041, log loss 0.5981, spread error 4.15, totals error 5.606; seed 2001
  0.1972 / 0.5814 / 3.98 / 5.632. Identical to main (both replay opening-day ratings; development does not run).
- Focused tests pass (`test_dev_curve`, `test_ratings_model`, `test_rating_ceiling`, `test_prospect_learning`,
  `test_development_outlook`, `test_unused_ratings_2`, `test_prospect_realism`, `test_generated_upside`,
  `test_hidden_upside`, `test_prospect_development`, `test_talent_balance`). Full suite on the merged branch (2 workers):
  2,397 tests; the remaining failures are environmental in this worktree (missing git-ignored reference files for the
  experimental engine, packaging inventory, the uncompressed inputs file) plus `test_neutral_coordinators`, which fails
  the same way on main. `test_prospect_realism` failed once with a uniform 21-24 boost; fixed by the draftee table.

## Judgement calls
- **Talent target in LEBRON units, box target in BPM units** (consistent: 1 engine point ≈ 1.35-1.4 box points).
- **The probe runs above the real curve at 21-24 on purpose**: played seasons (injuries, fatigue, the coach's minutes)
  grow about a third less. A first five-season run with the probe on target gave +0.26 at 21-22; the final gives +0.38.
- **Growth at 19-20 stays below the raw real average.** Matching it fully in the probe inflated the top (tenth-best
  5.1 → 7.3 in seven seasons): the real average only counts players who keep 1,000+ minutes, and the game's value scale
  is narrower than real LEBRON (spread 1.57 vs 1.9).
- **Laptop rule**: the free-swap reading stayed under 2 GB all afternoon (macOS shrinks its swap file to fit); I ran the
  light jobs one at a time with `nice` once load was under about 20 and free memory 40-50%. Multi-season runs were on Azure.

## What's left
1. **Growth at 23-24 in played seasons** is still low (+0.06 vs +0.17 real; box -0.15 vs +0.28), and the box-score
   peak is 24. Raising the 23-25 factors further is the next lever; it needs another five-season run (about 3 hours).
2. **Made-up draft classes produce too many stars from picks 4-30** (before and after): their entry level and potential
   come from the draft generator (`draft.py` / `talent.py`), not development.
3. **Old stars age about as fast as role players** (real: slower at 33-35, faster at 30-32).
4. `talent._trait_ceiling` still caps a made-up draftee's skill capacity at 97 (latent clip; not checked).
5. `physical_evidence` (offline input build) calls `monthly_trait_delta` without a curve, so it keeps the older curve;
   opening ratings stay reproducible if the inputs are rebuilt.
6. **Azure pool bug** (main's `scripts/azure_worker.py`): `start()` and `pick_worker()` read `cfg["monthly_hour_cap"]`
   on the per-worker dicts from `pool()`, which lack it, so starting any deallocated worker crashes with KeyError. I used
   a patched scratch copy (`cfg.get("monthly_hour_cap", 300)`) sharing the real config, ledger and claims.
7. Re-run the ten-season check on main once this merges.

## Resume state
Done; in review. Data in `output/dev-curve/`: `mainbase` and `final2run` (the final comparison), earlier pre-merge runs
`before`, `after`, `after2`; probes `probe-old`, `probe-new`; scorecards in `gates/`.
