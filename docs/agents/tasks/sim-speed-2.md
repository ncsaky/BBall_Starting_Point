# SIM-SPEED-2

Progress: 7/7 - done, ready for review

## Objective
Make a month of regular-season simulation (AI front offices included) fit the 10-20 s budget, or get as close as
possible, with identical seeded results (`scripts/season_month_probe.py --compare`). No cuts to the number or quality
of AI trade offers or extension decisions; the AI must not think less.

## Boundaries
Engine, save, transactions and AI front-office code as needed, tests, the probe, this file.
Not `src/nba_gm_data/gui/`, `src/nba_gm_data/stage2/`, ratings, or `docs/agents/BOARD.md`. One commit, not pushed.

## Steps (M = 7)
1. Read rules, prior task file (`season-speed-floor.md`), probe
2. Profile November (Nov 1 -> Nov 30) at season 1 and season 3 starts
3. Game engine per-player feature work
4. AI extension passes and AI trade search
5. Remaining full league rebuilds
6. Measure seasons 1-4 old vs new side by side; equality proof
7. Focused tests, full suite (`--workers 2`), report, commit

## Working data
- `output/ss2/base_code`: copy of HEAD 29e205a7 (plus the probe's new `--from`).
- `output/ss2/run/phase_saves/`: season 2-4 starts (rollover saves), copied from the SSF run.

## Resume state
- Probe got `--from MM-DD` (timed window start); seconds per 30 days now uses the real day count.
- Profile, November (Nov 1-30), cProfile (about 2x real time): s1 50.8 s, s3 62.0 s. Real time, old code: s1 22.6,
  s3 34.5-37.9 s per 30 days (machine load varies; always compare side by side with `output/ss2/run_ab.sh`).
- Step 3 done (sim.py, spatial.py): player features split into a remembered minutes-free part and a per-minutes part;
  the league playmaking baseline left out of the key (the vector never reads it); team zone grids for the sim built
  from lean player profiles (`sim.team_zone_grids`, `spatial.team_zone_grids`, shared `_team_zone_grids`).
  Proof: `scratchpad/vec_dump.py` old vs new equal on s1 and s3 leagues incl. 3 rounds of minute changes; probe
  compare identical s1 and s3. Timing s3 Nov 34.5 -> 26.9; s1 Nov 22.6 -> 21.1 (before the team-grid step).
- Step 4/5 (exact only): rotation refresh gets each team's roster and the health index from its caller instead of
  rescanning the league 30 times (save.py `team_rotation_projection(_roster=, _health_by_player=)`); health
  `parse_date` remembers parsed days; the AI's trade fit check reads lean zone grids (spatial `with_spatial_fit_context`,
  `spatial_fit_delta` via sim `team_zone_grids` / `player_zone_grids_for`, keyed by the whole record).
  Timing r3 (side by side): s1 Nov 25.2 -> 19.9, s3 Nov 32.1 -> 26.6, all identical.
- Audit run (NBA_GM_RUNTIME_AUDIT=1, s3 Nov 1-8) passes. vec_dump now also checks team grids and trade fit values.
- Not done, and why: (a) the daily refresh's table copies (~21 ms each in s3, ~1.8 s a month, growing) can only be
  made incremental by trusting that nothing edits the copies; (b) the rotation cache key (~12 ms per refresh) could
  only be cheapened with identity-based keys; (c) the dashboard reload after an advance feeds the GUI's later reads,
  and reusing the in-memory save is not exact (JSON round trip changes types). (d) released-FA and team-plan passes
  would need large cross-day keys.

## Report

**TL;DR**
- **A regular-season month is 17-21% faster, with identical results.** November, old vs new side by side, seconds
  per 30 days: season 1 22.1 -> 17.5, season 2 31.9 -> 26.6, season 3 30.5 -> 25.2, season 4 31.5 -> 26.0. Every
  season's end-of-month save is identical to the old code's.
- **Season 1 is now inside the 10-20 s budget** (November and the busier Oct 20-Nov 30 window). **Seasons 2-4 are
  not:** they sit at about 25-27 s for a November. Reaching 20 there needs changes I could not prove exact (below).
- No change to AI trade offers, extension decisions, or how much the AI evaluates: every change computes the same
  values with less repeated work.

### What changed
1. **Player features split into a minutes-free part and a minutes part** (`sim.py`). The game engine's per-player
   feature set was recomputed whenever a player's projected minutes changed (every day for most players), and its
   cache key also held the league playmaking baseline, which the feature set never reads. Only three things in it
   depend on tonight's minutes: usage, scoring usage, and the court-zone numbers. Those are now redone on top of a
   remembered minutes-free part, with the same arithmetic in the same order and the same key order and rounding.
2. **Court-zone numbers split the same way** (`spatial.py`: `_zone_static`, `_zone_grids`). The full player
   profile still uses them, so there is one copy of the formulas.
3. **Lean team court-zone grids for the engine and the AI's trade fit check** (`sim.team_zone_grids`,
   `spatial.team_zone_grids`, `spatial_fit_delta`). The game and the trade fit check read only a team's and a
   player's zone grids, but the full profiles also build display-only parts (shot-chart pockets, signature hashes)
   for every player. Same aggregation code (`_team_zone_grids`), keyed by the whole player record.
4. **Rotation refresh gets each team's roster and the health index from its caller** (`save.py`). Each refresh
   used to rescan the league's player list and rebuild the health index once per team (30 times).
5. **Parsed dates remembered** in the health pass (`health.parse_date`, ~120,000 parses a month).

### Speed (laptop, old and new run at the same time, seconds per 30 days, `output/ss2/final.summary`)

| Season start | Nov old | Nov new | Oct 20-Nov 30 old | Oct 20-Nov 30 new |
|---|---|---|---|---|
| 2026 | 22.1 | 17.5 | 25.5 | 19.6 |
| 2027 | 31.9 | 26.6 | 34.3 | 28.8 |
| 2028 | 30.5 | 25.2 | 39.4 | 33.1 |
| 2029 | 31.5 | 26.0 | 34.5 | 28.7 |

All eight pairs: `--compare` identical. The probe does not attach the GUI's live progress listener, which adds a
small per-day cost in the real app (rotation and opponent cards).

### Where a season-3 November goes now (real time, 29 days, 24 s)
Daily AI lifecycle ~6.9 s (team-plan refreshes 2.0, released-free-agent signing checks 1.9, AI trade search 1.7,
roster minimums 1.0); daily league refreshes ~4.3 s (86 a month: rotation projection 2.4, table copies ~1.8); games
~4.2 s; end-of-advance dashboard 2.3 s; save loads and writes ~3.5 s; full rebuilds ~1.7 s. The October extension
passes are not in November; late October in season 3 is dominated by two AI trade-market days.

### Not done, and why (each would need the coordinator's OK because it cannot be proved exact cheaply)
- **Daily refresh table copies** (transaction log, injury history, waiver wire...: ~21 ms per refresh in season 3,
  growing every season). Copying only what changed means trusting that nothing edits the league view's copies.
- **Rotation cache key** (~12 ms per refresh): only cheaper with identity-based keys (trusting no in-place edits).
- **Dashboard after an advance** reloads the written save and rebuilds the league; it feeds the GUI's later reads,
  and reusing the in-memory save is not exact (the JSON round trip changes some types).
- **Released-free-agent and team-plan passes** repeat similar work daily, but reuse would need large cross-day keys.

### Evidence
- Probe equality: 8 of 8 side-by-side runs identical (plus 4 earlier rounds).
- Direct equality (`vec_dump.py` in the session scratchpad): every player's features (with and without zones),
  every team's zone grids (default and explicit lineups) and trade fit values for hypothetical records, old code vs
  new, on season-1 and season-3 leagues through three rounds of minute changes: identical, key order included.
- Audit mode (`NBA_GM_RUNTIME_AUDIT=1`, recomputes every remembered value): season 3 Nov 1-8 passes.
- New tests: `tests/test_sim_speed_2.py` (7). Updated `tests/test_transaction_feature_demand.py` to watch the new
  zone function instead of the old full profile (same intent: the full reference prepares zones, the lean context
  doesn't).
- Full suite (`run_tests_parallel.py --all --workers 2`): 2,599 tests, 17 failures; all 17 fail the same way on the
  old code (missing output files in a worktree, ratings/pilot fixtures, Windows packaging, two GUI concept checks,
  one asset-valuation health-risk check).
