# INPUTS-DEFAULT: new saves on the 94-input ratings, and win back the speed

_Claude (Opus agent), 2026-11-19, branch `worktree-agent-a930b7773912140dc`. User approved: (A) new saves default to the 94-input ratings; (B) recover the speed they cost. Brief: `docs/agents/tasks/inputs-default-readiness.md` sections 4-6._

**TL;DR**
- **Every new game (browser, CLI, API) and both scorecards now use the 94-input ratings**; the older ratings stay available from the CLI (`--ratings-model legacy_traits`) and the environment variable. Scorecards without the variable: real stats 18/18, odds Brier 0.1941 / log loss 0.5744 (market 0.1962 / 0.574).
- **Packaging:** the 123 MB uncompressed ratings file and all private research data stay out of the package (the Windows recipe used to ship the private data; fixed). Packaged smoke test: see below.
- **Speed: modest, exact gains.** A month in an aged league: 39.6 -> 37.6 s CPU (warm GUI-like process), identical results; the 94-input set is now ~13% slower than the older set there (was ~19%; the "55%" in the readiness report was measured under heavy parallel load). The biggest remaining 94-input-only cost is in the AI contract-extension check (another agent's area); a 3-line fix is proposed below.

## Resume state

PENDING: full suite (running, `output/inputs-default/full_suite.log`). Packaged build and smoke test done. Commits on the branch: `08c94f6` checkpoint (laptop crash), `5ab65b2` merge of `codex/immersive-franchise-journey` (trade step 1 + heavy minutes, clean), `ed55142` part A, `7a2586b` part B. Scratch: `output/inputs-default/` (probe scripts, seeds, timings, profiles, logs).

## Part A: the default flip

- `save.create_league_save` / `_create_league_save`, the `app_actions` create-save fallback and the CLI `--ratings-model` default are now `inputs_v1`.
- `ratings_model.ratings_model_for`: save-less tools (`save=None`: `calibration_report.py`, `validate-season-probabilities`, fit scripts via `load_sim_context`) default to `inputs_v1`; `NBA_GM_RATINGS_MODEL=legacy_traits` still selects the older set. **A save that records no rating set keeps the older ratings** (every save made since the 94-input model existed records its set, so a field-less save predates it). Flipping that case too broke 41 core tests built on tiny hand-made leagues that cannot fit the 94-input model.
- `scripts/fit_box_stat_rates.py` pinned to the older ratings (that fit reads them).
- Packaging: `BUILD_ONLY_DATA = ("data/canonical/player_inputs_2026_27.json",)` excluded in both build scripts and both specs; the game already reads the `.gz` when the uncompressed file is absent (`ratings_model._inputs_path`, `input_estimator`). **The Windows spec shipped `data/research/bbi/*` and the Barttorvik data** (it had no exclusion); it now uses the same private list as macOS. The build inventory no longer crashes on symlinked data files (worktrees). New test `test_inventory_ships_compressed_inputs_but_no_private_or_uncompressed_copies` checks both specs.

### Tests changed (12 failures from the flip, none a game bug)

| Test | Change |
|---|---|
| `test_forward_tuning` (2), `test_imported_rookie_ratings` (2), `test_imported_tail`, `test_player_tuning`, `test_foundation` zero-traits and Micah Potter trade-finder case | Pinned `ratings_model="legacy_traits"`: they check exact older-ratings values across starting-data versions |
| `test_player_profile` | Now asserts new saves default to `inputs_v1` and an explicit `legacy_traits` save has no 94-input card |
| `test_player_lifecycle` roster cap | Its 18-player made-up league is marked older-ratings (no data to fit on) |
| `test_foundation` random-team filename | Copies the inputs `.gz` into its temporary game root |
| `test_talent_balance` old v3 save | Retired (old saves don't matter) |
| `test_foundation` replay band (found in the extra modules) | Seed 9 lands in the rebound tail on the 94-input set (23 team rebounds). Over 120 seeds of that game both sets have the same spread (94-input mean 43.5, sd 6.5, min 23; older 41.4, 6.8, min 25), so the seeded band stays on the older set and a new default-set check covers determinism and exact team totals. Not re-seeded. |
| `test_ratings_model` default | Rewritten for the new defaults |

Scripts still creating saves without a rating set now follow the default: the soak/market harnesses (intended) and the October one-off proofs `verify_imported_tail.py`, `verify_imported_skills.py`, `verify_offensive_roles.py`, `verify_rotation_profiles.py`, `verify_talent_balance.py`, `verify_roster_alignment.py`, `verify_trade_season.py`, `verify_contract_protection.py`, `verify_simulation_consistency.py`, `verify_postseason_calendar.py`, `verify_player_model_schema.py`. Those compare against older-ratings golden outputs; pin them if they are ever rerun. `build_mature_fixture.py` and `check_month_parity.py` already pin explicitly.

### Tests run

- Core (`scripts/run_core_tests.sh`) + `test_ratings_model`: 352 OK (2 skips).
- 23 save-creating modules (the readiness list plus caches, packaging, game minutes): 400 tests; all pass after the replay-band fix.
- Full suite: see "Full suite" at the bottom.

### Scorecards (no environment variable; merged code)

- Real stats, `calibration_report.py --games 1230 --mode replay-real-minutes`: **18/18**, 115.4 points, TS .583, pace 102.1.
- Odds, `validate-season-probabilities --runs 100`: **Brier 0.1941, log loss 0.5744** (market 0.1962 / 0.574), spread error 4.546, totals error 5.465. Same as the 94-input numbers measured with the variable (older set: 0.2140).

## Part B: speed

### Where the 94-input time went (cProfile, aged league 2028-11 -> 12, merged code)

1. **The AI extension hard-cap check rebuilds the league from an already-rated league** (`save.py:5646` `queue_ai_recommendations` calls `process_ai_extensions(..., prepared_active=True)`; `save.py:6079` passes that active league to `extension_offer_fits_hard_cap`, which calls `canonical_with_save` on it, `save.py:6157`). In 94-input mode that refits the ratings adapter on already-derived ratings and re-estimates every generated player from them (and re-pickles the league-copy cache twice). It is the largest 94-input-only cost in a warm month. The check only reads contracts, so results do not depend on it. **Proposed fix (not applied: AI-queue area):** add `baseline: dict | None = None` to `process_ai_extensions`, pass `baseline=authoritative_canonical` from `queue_ai_recommendations`, and call `extension_offer_fits_hard_cap(baseline if baseline is not None else canonical, ...)`. Tested in a copy (`output/inputs-default/code/exp`): identical saves in all four scenarios.
2. **Generated players re-estimated on rebuilds** because the cache key included the season stats the save attaches after every game; the cache also grew without bound. Fixed (part B).
3. **Per-player reads in games and valuations**: the value model's grouped input features and the box-score rates (whose flattening cache held 8 records). Fixed with identity caches on the shared read-only input records (checkpoint commit).
4. **First rebuild in a process** (adapter fit, value tables, generated players, draft class): one-time per GUI session (~9 s to open an aged save), not per month.
5. What remains on a fresh league (~4-5 s per month) is spread thinly over per-player work (offensive profile read twice per player feature, impact prediction, lineup fit) and different league events; no single hotspot.

### Timings (one month through `advance_save`, the GUI's action; mean of 2 back-to-back runs; CPU seconds, wall in brackets; machine load 25-40 from other agents)

Warm process (save opened first, as in the GUI before pressing Sim):

| League | Before | After (this branch) | After + proposed extension fix |
|---|---:|---:|---:|
| Aged 2028-11, 94-input | 39.6 (41.5) | **37.6 (38.9)** | 36.5 (39.0) |
| Aged 2028-11, older | 33.4 (34.6) | 33.2 (34.5) | 33.7 (35.0) |
| Fresh 2026-11, 94-input | 30.1 (31.0) | **29.4 (30.4)** | 31.1 (33.5) |
| Fresh 2026-11, older | 24.6 (25.2) | 25.9 (27.5) | 25.4 (26.2) |

Cold process (new Python process per month): aged 94-input 41.8 -> 40.8, aged older 32.4 -> 32.6, fresh 94-input 30.4 -> 29.4, fresh older 25.1 -> 25.3.

**Parity:** every variant gives a byte-identical saved league for the same seed in each scenario (save digest, snapshot ids excluded). Run-to-run noise under this load is about ±1.5 s, so the extension fix's gain needs a quieter machine to pin down (one quiet pair: 41.9 -> 34.2 s; its profile share suggests ~2-3 s per month when extensions are processed).

**Budget (rule 10, 10-20 s per GUI month):** neither set meets it on this machine (older 25-34 s, 94-input 29-38 s). The 94-input extra is now ~13-17%.

## Packaged build (macOS, real build; nothing published)

- Built with the repo's recipe and pinned build environment: `packaging/macos/build.py --version 0.1.0-inputs-smoke --output output/inputs-default/dist` (Python 3.12.11 build venv, PyInstaller 6.16), from this branch's final code with the uncompressed inputs file present locally. Signed ad hoc, arm64, minimum macOS 11.
- Smoke test (`output/inputs-default/package_smoke.py`) on the signed release app (the exact folder the ZIP is made from; unpacking the ZIP a second time filled the disk, see below): launched the frozen app `--headless --no-browser` with a temporary data folder and a clean environment, got the session token, `create_save` GSW seed 2301 through the GUI API (7.1 s): **the save is on the 94-input ratings**, Jokić's card carries the four-layer 94-input profile (header 73.3); `advance_save` five days (2026-10-20 -> 10-25, 33 games, 7.9 s); clean exit (code 0).
- Contents: `player_inputs_2026_27.json.gz` ships, the uncompressed `.json` does not, no file under the private research list ships (only the tracked BBI templates/mapping and the non-private research data, as before).
- **Size warning for the next beta ZIP:** the archive is 2.57 GB (app 2.7 GB). 2.3 GB of it is the GUI's startup/team videos (`gui/assets/startup/video/teams/*.mp4`), not game data (142 MB). Earlier betas were 0.16-0.35 GB. Worth deciding before sending a ZIP to friends.
- **Disk:** the Mac had ~2.5 GB free during the test; unpacking the ZIP failed with "No space left on device". The build cache, ZIP and test copies were deleted afterwards (13 GB free).

## Left open

- Apply the extension hard-cap fix above once the trade work in `save.py` lands.
- Card header vs table numbers (Jokić 95.4 vs 77.9): left alone per the user (lowest priority); listed on the board.
- The October `verify_*` proof scripts above now follow the new default.
- Remaining 94-input month cost is diffuse; next candidates are reading each player's offensive profile once per feature build (`sim.player_feature_vector` -> `impact_value.sim_impact`) and memoizing impact predictions.

## Full suite

PENDING.
