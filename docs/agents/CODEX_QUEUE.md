# Codex task queue

Paste one prompt into a **fresh** Codex chat. One task per chat keeps it from drifting after context compaction. Each prompt is self-contained. Claude reviews the result and updates `BOARD.md`.

Current priority (2026-11-17): the three "Ready now" tasks below. GUI tasks are parked at the bottom.

---

## Ready now (2026-11-17): three independent tasks, one fresh chat each

Run them in separate chats; they touch different files. Claude is meanwhile working on ratings/value files (`bbi_evidence.py`, `impact_value.py`, `trait_adapter.py`, `ratings_model.py`, `sim.py` assist/rebound functions, `transactions.py` valuation, the BBI mapping and `data/canonical/*`). **Do not edit those.**

### SPD: Fewer full league rebuilds per sim day (exact speedup)

Suggested settings: GPT-6.1 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first (see "Speed check (rule 10)"). You own task SPD; mark it "in progress (Codex)" on the board.

GOAL: make simulating a month faster without changing any result.

FACTS (measured 2026-11-17 by Claude):
- A headless mid-season month (Feb 15 -> Mar 15, AI on) takes ~20.6 s; an early-season month (Oct 20 -> Nov 20, fresh save) ~55 s. Target: 10-20 s.
- A cProfile of the month shows save.canonical_with_save (a full league rebuild, ~0.37 s each) is still called about once per sim day from advance_lifecycle_to (save.py), plus extra rebuilds in advance_save_day for ai_canonical and role_active, and in review_ai_releases when rosters change. The game sim itself (sim_game_with_context) is ~27% and is out of scope.
- Claude already made two exact changes: an early exit in process_inseason_released_free_agent_signings, and reuse of the day's lifecycle state for ensure_roster_minimums and the in-season signing check (same reuse rule the code uses for ai_canonical). Read those diffs (git log -p --follow src/nba_gm_data/save.py | head -300) to see the pattern.

WHAT TO TRY (your design; keep it exact):
- Carry the active league state across consecutive days within one advance_save call when the roster, contract and free-agent inputs did not change (refresh_active_runtime_state exists for health/minutes refreshes). advance_lifecycle_to currently resets `active = None` per call.
- Avoid rebuilding role_active when nothing roster-related changed since ai_canonical.
- Anything else the profile shows, as long as results stay identical.

HARNESS (reuse; scripts are in output/overnight-2026-11-17/):
- speed_month.py advances a copy of a seed-103 legacy save (output/overnight-2026-11-17/crash103/s3.json + its .history.sqlite3*; copy both to a scratch folder first, never edit the originals) to a date and prints seconds.
- fresh_month.py creates a fresh BOS seed-55 save and advances it to 2026-11-20.
- Exactness check: run old code and new code from identical starting files and compare the saved JSON after removing meta.save_snapshot_id and history_store.snapshot_id (and history_store.path if file names differ). They must be EQUAL. Also compare the history sqlite tables' row counts.
- Also verify a new-ratings save (create_league_save(..., ratings_model="inputs_v1")) for one month the same way.

BOUNDARIES: edit only src/nba_gm_data/save.py (and a new test file). Do not change formulas, RNG streams, or any file listed at the top of this queue.

ACCEPTANCE:
1. Byte-identical results (as defined above) on: the mid-season legacy month, the fresh early-season month, and one new-ratings month.
2. Report before/after seconds for each (median of 2 runs).
3. bash scripts/run_core_tests.sh passes (329 tests).
4. A short plain-language report in docs/agents/tasks/spd-sim-speed.md; set the board row to "review". Do not commit.
```

### T2b: Fix the 10-season driver and rebuild the 2036 test fixture

Suggested settings: GPT-6.1 Sol, Medium, fresh chat. Long compute (~2 h); start it early.

```
Read AGENTS.md and docs/agents/BOARD.md (task T2 row) first. You own task T2b; mark it "in progress (Codex)".

GOAL: restore the last missing test fixture, output/roster-forecast-pass/fixtures/mature2036.json, which tests/test_roster_forecast_performance.py::test_archived_2036_generated_and_injured_rosters_without_advancing_the_career needs (it currently skips). The test asserts state.current_date == '2036-11-01' and uses the save's players, health states and generated (drafted) players.

FACTS:
- The original generator scripts/prepare_roster_forecast_fixture.py extracted from a 565 MB archived checkpoint that no longer exists.
- scripts/ten_season_soak.py is stale: it dies at the draft-lottery phase (a 2027-06-22 save now needs the `draft_lottery` action). scripts/overnight_market_health.py has a current phase driver you can learn from.
- One simulated month takes ~20-60 s headless, so 10 seasons is roughly 1.5-2.5 h. Run it in the background, check progress, and keep a log.

STEPS:
1. Fix scripts/ten_season_soak.py (or write scripts/build_mature_fixture.py) to drive a fresh seed-17 legacy save through every phase (regular season, playoffs, lottery, draft, re-signing, free agency, preseason) to 2036-11-01, with AI on, saving periodic checkpoints under output/t2b/ so a crash can resume.
2. Produce the fixture. Store it as a tracked, compressed file under tests/fixtures/ (keep only the save fields the test reads, if that is enough; target under 15 MB) and point the test's loader at it, falling back to a skip with a clear message if absent. Do not change any assertion.
3. Report any engine crash with the traceback (don't fix engine code; note it for Claude).

BOUNDARIES: scripts/ten_season_soak.py or a new script, tests/fixtures/, and the fixture-loading lines of tests/test_roster_forecast_performance.py only. Don't edit src/.

ACCEPTANCE: PYTHONPATH=src:scripts:tests .venv/bin/python -m unittest tests.test_roster_forecast_performance runs with 0 skips (or report exactly why not). Short report in docs/agents/tasks/t2b-mature-fixture.md; board row to "review". Do not commit.
```

### TST: Triage and fix stale tests in the full suite (tests only)

Suggested settings: GPT-6.1 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md ("Test suite health" and "Full-suite leftovers" sections) first. You own task TST; mark it "in progress (Codex)".

GOAL: a full test suite that is green or explicitly quarantined, so real regressions are visible.

STEPS:
1. Run the full suite once: PYTHONPATH=src:scripts:tests .venv/bin/python -m unittest discover -s tests 2>&1 | tee output/tst/full_before.log (takes ~40 min; run in background). Note: some tests need scripts/ on the path; plain src fails their imports.
2. Classify every failure: (a) stale pin, where the game changed on purpose (roster refresh, ratings refresh, new save fields, renamed GUI functions); (b) fixture/path problem; (c) likely real bug.
3. Fix (a) and (b) in tests/ only. For each changed assertion, add a one-line comment saying why the new expectation is right, with evidence (commit, data change, board note). NEVER loosen a tolerance or delete an assertion just to pass; if unsure, mark it with unittest.skip("needs review: <reason>") and list it.
4. Do not fix (c); list each with the failing assertion and your diagnosis for Claude.
Known context: rating-pin tests (test_imported_rookie_ratings, test_player_tuning, test_roster_alignment, test_rotation_profile_calibration) pin legacy-mode values. Check whether the legacy values changed deliberately (git log -S) before updating. Today's engine commits changed box-score steals/blocks/rebounds/free throws (scores unchanged), so tests pinning those box stats may need new expectations: verify they are improvements, not regressions.

BOUNDARIES: tests/ only (including tests/fixtures/). Do not edit src/ or scripts/.

ACCEPTANCE: rerun the full suite; report before/after counts (pass/fail/error/skip), the list of quarantined tests with reasons, and the suspected real bugs. Report in docs/agents/tasks/tst-suite-triage.md; board row to "review". Do not commit.
```

---

## E2b: Stop priors from averaging away elite players (DONE, accepted 2026-11-16)

Suggested settings: GPT-6.1 Sol, High, in a fresh chat.

```
Read AGENTS.md, docs/agents/BOARD.md (the "T3 diagnosis" and "Inputs mode is NOT ready" notes), docs/agents/STAGE1_DESIGN.md and your own E2 report docs/agents/tasks/e2-input-estimator.md first. You own task E2b. Mark it "in progress (Codex)" on the board.

PROBLEM (measured 2026-11-16 by the coordinator)
In the new-ratings mode (NBA_GM_RATINGS_MODEL=inputs_v1), the AI's on-court value compresses stars toward ordinary rotation players. On-court value is computed from the 15 legacy traits that trait_adapter.py derives from your inputs:

| Player | Legacy on-court | Inputs-mode on-court | Market rank, legacy -> inputs |
|---|---|---|---|
| Jokić | 83.7 | 73.9 | 3 -> 28 |
| Wembanyama | 87.5 | 72.4 | 1 -> 40 |
| Giannis | 78.6 | 68.8 | 23 -> 66 |

Reproduce with:

    NBA_GM_RATINGS_MODEL=inputs_v1 PYTHONPATH=src .venv/bin/python scripts/market_sanity_report.py

and compare against the same command without the variable.

Cause: about 86% of input cells are priors. Each prior is a position/role mean plus a small, bounded personal residual. For an elite player most technique inputs have no direct evidence, so they sit near the position average, and the elite signal is averaged away.

FIX (statistically principled, evidence-based, NOT fitted to the market report)
Make priors hierarchical. A player's prior for an unobserved skill should be centred on the position/role mean SHIFTED by that player's general talent level in the related family, estimated from his own evidence: his directly estimated inputs in the same family, provider impact metrics already in the data (Crafted DPM/OPM, LEBRON or similar if present, BBallIQ), minutes/usage, and his legacy traits as weak evidence. Skills are positively correlated, so a player who is excellent on every observed skill is more likely above average on an unobserved one.
- Shrink the shift by sample size and uncertainty.
- Keep it labeled `reason: prior` with honest wide bands.
- Do not use simulation outcomes, the market report, or named-player overrides to set coefficients. Declare the correlation and shift assumptions in code comments and the report.

ACCEPTANCE
1. The adapter-derived on-court values (computed by the engine) for the top 50 legacy on-court players retain a spread comparable to legacy: the standard deviation across those 50 is at least 80% of the legacy SD. Report both.
2. The rank correlation between inputs-mode and legacy on-court across rotation players (minutes_projection >= 15) is at least 0.7. Report it; legacy is not ground truth, so also list the 15 biggest movers with a one-line reason each.
3. The real-stats scorecard does not get worse:

       NBA_GM_RATINGS_MODEL=inputs_v1 PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230

   Current per-36 average errors: points 3.19, FGA 2.37, 3PA 0.50, REB 1.29, AST 1.02.
4. Existing estimator, BBI and player-model tests pass, and determinism is preserved.

FILES: src/nba_gm_data/input_estimator.py, tests/test_input_estimator.py, regenerate data/canonical/player_inputs_2026_27.json and .json.gz via scripts/build_player_inputs.py, and docs/agents/tasks/e2b-elite-priors.md (report, TL;DR first, plain language). Do not edit trait_adapter.py, ratings_model.py, transactions.py or the GUI.

Set the board row to "review". Do not commit.
```

---

## E2c: Generated players are defined by the generator, not shrunk to priors (DONE, accepted 2026-11-16)

Suggested settings: GPT-6.1 Sol, High, in a fresh chat or continuing the E2b chat if it still has context.

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/STAGE1_DESIGN.md (section F) and src/nba_gm_data/ratings_model.py (_install_generated_players) first. You own task E2c.

PROBLEM (measured 2026-11-16)
In a new-ratings save, the 2027 draft class got inputs through `InputEstimator().estimate_player_inputs(player, legacy_traits, prospect=True)`, but their derived display ratings are near the league floor. Pick 1 shows OVR 24.0, pick 3 OVR 3.0, pick 5 OVR 31.4, against a league median of 50. The prospect path treats the draft model's current_ability, potential, archetype and generated traits as "not technique evidence". That is correct for REAL people, but wrong for FICTIONAL generated players: for them, the generator's output DEFINES the player.

FIX
For players with source_kind in ("generated_rookie", "generated_prospect", or any other generated kind you find in draft.py/save.py), build the 94 inputs FROM the generator's definition, deterministically from the player id/seed:
- current_ability (talent level now) and potential.
- The archetype (draft.py archetype weights) for the skill shape: shooter, creator, rim protector, and so on.
- The generated 12 draft traits and/or legacy rookie traits for the per-skill profile.
- height/weight for the physicals.
Unobserved detail within an archetype can vary deterministically per player. Calibrate the mapping on REAL players: choose it so that a generated player with current_ability X and archetype A lands where real players of similar overall and role land in the existing input distribution. Real-player input data is the reference. Simulation outcomes are not.
Label these records clearly, e.g. reason "generated", with evidence source "draft_model". This needs a small, coordinated schema decision; if the schema forbids a new reason, use reason "estimated" plus a distinct evidence method, and propose the schema change in your report.

Keep real prospects (the 2026 real class with college stats) on the current evidence path; that one is correct.

ACCEPTANCE
1. In a new-ratings save carried through a draft, the derived OVR of generated rookies tracks their draft model ability: the top-5 picks' median display OVR is roughly in line with real current NBA rookies/second-year players of similar pick slot. Report the comparison.
2. There are no near-zero display ratings for any lottery pick.
3. Tests pass, and output is deterministic.
   - Test save: copy /private/tmp/claude-501/-Users-noahtyler--claude-spares-spare-kEIEMb/aa8ffa3d-9829-4c0d-b448-e9409427c53d/scratchpad/cycle/inputs_save.* (with its sidecar files, original names) into your own scratch dir.
   - Inspect it with ratings_model + player_profile.

Files: src/nba_gm_data/input_estimator.py (prospect/generated path), tests/test_input_estimator.py, docs/agents/tasks/e2c-generated-players.md. Do not edit ratings_model.py or draft.py without noting it in the report.

Set the board row to "review". Do not commit.
```

---

## BBI: Basketball Index capture pipeline (DONE, accepted 2026-11-16)

Suggested settings: GPT-6.1 Sol, High, in a fresh chat.

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/STAGE1_DESIGN.md and docs/ratings-evidence-2026-10-29/BBI_ACQUISITION_PLAN_2026_11_11.md (plus its manifest JSON) first. You own task BBI. Mark it "in progress (Codex)" on the board.

GOAL
The user will buy ONE month of Basketball Index (BBI, $5) and wants to extract every penny of value. That means capturing everything the paid membership legitimately exposes for personal use: all seasons, all metric families, all players, both raw values and percentiles or grades, plus sample sizes where shown. It must stay within the site's terms; no circumventing protections. The subscription has NOT been purchased yet. Your job is to build and test everything BEFORE purchase, so the paid month is spent purely collecting.

DELIVERABLES
1. A capture plan in docs/agents/tasks/bbi-capture-plan.md:
   - Every BBI tool, page and leaderboard that exposes player data (Skills, Leaderboards, LEBRON, Lineups, Rotations, Playtype, Matchup, Shooting, and any others you find).
   - For each: what fields it shows, seasons available, filters, whether it has a CSV/export button, and how many page views or exports a full-league capture needs.
   - Prioritize by value to our 94 inputs, using the existing manifest and docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md.
   - Estimate total capture time.
   - Identify what can only be done through the user's signed-in browser and give the user a step-by-step day-1 checklist. The user (or Claude driving the user's browser) does the signed-in capture; you do not log in or pay.
   Use only public information (free pages, the public glossary, free demo tools).
2. An importer, src/nba_gm_data/bbi_import.py, that ingests captured exports (CSV and/or saved page HTML/JSON) into a normalized local cache: data/research/bbi/ with raw files preserved plus a normalized JSON. It must:
   - Match players to our canonical ids (ESPN id where available, careful name matching otherwise; report unmatched rows).
   - Keep season, metric name, raw value, percentile or grade, sample size and retrieval date separate.
   - Never relabel provider composites as raw technique.
   Test it end-to-end on whatever free BBI data you can legitimately download now (free leaderboards, LEBRON CSV, demo pages), plus small synthetic fixtures shaped like the paid exports.
3. An evidence source plug-in for the estimator. In src/nba_gm_data/input_estimator.py, add BBI as a source that maps specific BBI metrics to specific inputs (follow the manifest's intended mappings), with shared-evidence ids and sample-size weighting, so that once the cache exists, `scripts/build_player_inputs.py` uses it automatically. When the cache is absent, output must be unchanged (byte-identical); test that.
4. Tests in tests/test_bbi_import.py.

FILES YOU MAY TOUCH: the files above, data/research/bbi/ and docs/agents/tasks/bbi-*.md. Do not edit trait_adapter.py, ratings_model.py, player_profile.py, save.py, sim.py or GUI files.

DELIVER: a plain-language report (TL;DR first) in docs/agents/tasks/bbi-capture-plan.md, including the day-1 checklist. Set the board row to "review". Do not commit.
```

---

## S1-E-inv: Front-office threshold inventory (read-only)

Suggested settings: a mid-tier model, medium effort.

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/STAGE1_DESIGN.md section E first. You own task S1-E-inv. This task is READ-ONLY for code. You may only create docs/agents/tasks/s1e-threshold-inventory.md (and scratch files under output/s1e/).

CONTEXT: The AI front office (trades, contracts, extensions, free agency, draft, fantasy draft, waivers, release planning, trade wants) reads player ratings through save.player_attribute_summary / player_display_attribute_summary. That is an OVR/OFF/DEF/subrating formula over the 15 legacy traits, clamped to 1–99, with about 75 call sites. Stage 1 will switch those readers to the new unclipped 50+15z display scale (src/nba_gm_data/player_profile.py). Every hard-coded threshold on the old scale must then be re-expressed, ideally as a league percentile.

PRODUCE a table of EVERY place a rating value from those summaries (or a value computed directly from it) is compared to a constant, or used in a formula with a constant breakpoint. For each row give:
- file:line and function;
- which field (overall, offense, defense, shooting, ...);
- the constant(s) and what decision they drive, in plain language;
- the league percentile that constant corresponds to on the CURRENT old scale. Compute it from data/canonical/universe_2026_27_offseason.json using save.player_display_attribute_summary over all players; report the percentile among rotation players (minutes_projection >= 15) too;
- a suggested replacement expression (e.g. `percentile >= 0.97`).
Also list call sites that only display values (no thresholds), separately.

Group by system (trade valuation, contract/extension, free agency, draft/fantasy, roster/waivers, narrative/UI). End with the 10 thresholds most likely to change AI behavior if mis-converted. Set the board row to "review". Do not commit.
```

---

## E2: League-wide player input estimator v1 (DONE, accepted 2026-11-16)

Suggested settings: your strongest model, high effort. This is the most important task Codex has this month. If usage runs out mid-task, keep the resume state current so a fresh chat can continue.

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/ENGINE_ROADMAP.md and docs/agents/STAGE1_DESIGN.md first. You own task E2: component A in STAGE1_DESIGN. Claude is building the adapter (component B) in parallel against your output format, so keep the output schema stable and documented at the top of your report. Mark it "in progress (Codex)" on the board.

GOAL
Every player in the game needs values for the approved 94-input player model (src/nba_gm_data/player_model.py, player_model_registry.py; design in docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md). Today only 32 players have partial hand-researched inputs (docs/ratings-evidence-2026-10-29/*_INPUTS_*.json packets). Build a deterministic, evidence-based ESTIMATOR that produces inputs for ALL 691 players in data/canonical/universe_2026_27_offseason.json, plus a function for draft prospects.

FILES YOU OWN (create or edit only these)
- src/nba_gm_data/input_estimator.py (new)
- scripts/build_player_inputs.py (new): writes data/canonical/player_inputs_2026_27.json
- tests/test_input_estimator.py (new)
- docs/agents/tasks/e2-input-estimator.md (checkpoint plus final report)
Do NOT edit player_model.py/registry semantics, sim.py, interior_game.py, or any engine module. If the schema needs a change, write the proposal in your report instead.

EVIDENCE SOURCES (local only, no purchases)
- Player Stats/player_skill_input_2025_26.json: Crafted NBA 2025-26, ~526 players. Shooting splits, close-shot efficiency, BLK/STL%, deflections, ORB/DRB%, touches/passes, passer rating, play-type usage and points per possession (P&R handler, roll man, spot-up, iso, post, cut, transition, handoff, off-screen), defended-position shares.
- Player Stats/player_stats.json, Even more stats/*.xlsx, data/research/player_career_stats.json + espn_career_raw/ (ESPN careers, 616 of 691 matched by ESPN id).
- Universe player fields: height_inches, weight_lbs, wingspan_inches (427 present), age, position, roles; the 15 existing traits[] (all 691 players; see src/nba_gm_data/traits.py). Old traits may inform priors but must NOT be relabeled as technique skills.
- docs/ratings-evidence-2026-10-29/PLAYER_MODEL_EVIDENCE_COVERAGE_2026_11_12.md: per-input evidence handles and estimation notes. Follow its "evidence-to-input contract".
- Expert opinion: the Nerd Sesh transcript research in docs/ratings-evidence-2026-10-29/ (claim index, named-player dossiers, rating-change proposals). Treat it as expert evidence that can adjust an estimate, with its own source id. It is not the sole truth, and it is not a reason to override clear stats without saying so.
- Basketball Index data may be added later (BBI_ACQUISITION_PLAN_2026_11_11.md). Design the estimator so a new evidence source can be plugged in per input without rewriting it.
- Known data bug: the historical game-box cache has FGM/FGA = 0 (see HISTORICAL_SHOOTING_DATA_QA_2026_11_13.md). Do not use those fields.

REQUIREMENTS
1. For every player and every one of the 94 inputs, emit a record in the existing PlayerInputs schema: value, uncertainty, status, and source/evidence ids. Statuses must distinguish:
   - "estimated": derived from that player's own evidence.
   - "prior": no player-specific evidence; uses a position/role/physical prior with wide uncertainty.
   The ENGINE needs a usable number for every input, so every input must have a value. "Prior" values must be clearly labeled and must not masquerade as measurements.
2. Method: shrink toward position/role priors, weighted by sample size (minutes, attempts, possessions). Keep passing recognition and execution as separate estimates. Make tendencies conditional on opportunity. Physical families come from measurements where present; otherwise from priors (e.g. wingspan from height by position) with wide uncertainty.
3. Scale: no clipping at 100. Map to the registry's scale by rescaling, so elite players stay distinguishable.
4. Ratings-first: inputs come from evidence only. Never tune estimates toward simulation outcomes. There are no simulation runs in this task.
5. Validation: compare estimator output to the 32 hand-researched players' estimated cells (the packets overlap; use the newest value per cell). Report per-input agreement (mean absolute difference, and how often the hand value falls inside your uncertainty band), plus the 10 biggest disagreements with a one-line explanation each. Hand values are a reference, not ground truth.
6. Prospects: estimate_prospect_inputs(prospect, traits, scouting) for generated and real draft prospects (src/nba_gm_data/draft.py: generate_draft_class_records, prospect_traits_from_row), using the same definitions with wider uncertainty. Don't wire it into draft.py; just provide and test the function.
7. Deterministic: same data gives byte-identical output. Standard library only.
8. Tests: schema validity for all 691 players, determinism, no missing values, no clipping pile-ups at the scale max, prospect function, and a few sanity orderings that are obvious from raw stats (e.g. FT shooting follows FT%). Do not hardcode named-player ranking tests.

DELIVER
Run: PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py, then the new tests. Write the final report (plain language, TL;DR first) in docs/agents/tasks/e2-input-estimator.md. Include coverage counts (estimated vs prior, per input family), the validation table, known weak spots, and runtime. Keep a "Resume state" section updated while you work. Set the board row to "review". Do not commit.
```

---

## Parked (GUI, after the engine month or if Codex has spare usage)

### Q1: Three small GUI behavior fixes

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task Q1. Mark it "in progress (Codex)" on the board.

Fix three small behaviors in the browser GUI (src/nba_gm_data/gui/app.js, plus styles.css only if needed). Don't touch any other file except new or updated tests.

1. Next Opponent card after a game (backlog U03). After the W/L result animation plays, the card must switch to the actual next opponent. Today it stays on the finished game. Handle "no next game" and playback interrupted mid-animation.
2. Sim shortcut prefix (U04). Pressing S, then E, W or M must work no matter how long the pause between the keys. The S prefix stays armed until the user clicks something else, presses Escape, or focus moves to a text input. Never hijack typing in inputs or browser shortcuts. No timers.
3. Draft lottery grid order (U05). Around app.js:4837 the reveal grid lists picks 14 down to 1. The grid must show pick 1 at top-left and 14 at bottom-right. Keep the reveal timing (14 then 13 ... then 1); only the spatial placement changes.

Match the existing code style. Add or extend tests where GUI JS tests already exist (tests/*.test.cjs).

When done: write a 10-line plain-language summary at docs/agents/tasks/q1-gui-small-fixes.md. Set the board row to "review". Do not commit.
```

### Q2: Draft board diagnosis (read-only)

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task Q2. READ-ONLY for code and data; you may only create docs/agents/tasks/q2-draft-diagnosis.md and scratch files under output/q2/.

The user saw the 2nd-ranked prospect (96 POT / 80 NOW) fall to 15th and asked whether the AI or our rankings are wrong, and whether there should be both a consensus big board and a scouting board. With file:line references (draft.py, prospect_cards.py, talent.py, gui/app.js draft board):
1. How the displayed ranking is computed.
2. How AI GMs score prospects at their pick.
3. Reproduce across about 5 seeds headlessly: how far the top-5 fall, and which term drove each pass.
4. Whether "upside" and "potential" overlap or double-count.
5. A proposed (not implemented) design for consensus vs scouting boards.

Lead with a 5-line plain-language answer. Set the board row to "review". Do not commit.
```
