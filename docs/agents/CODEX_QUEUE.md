# Codex task queue

Paste one prompt into a **fresh** Codex chat. One task per chat keeps it from drifting after context compaction. Each prompt is self-contained. Claude reviews the result and updates `BOARD.md`.

Current priority (2026-11-19, evening): ROT-OUTLIERS first, then BLOWOUT-MINUTES. GUI tasks are parked at the bottom.

---

## Ready now (2026-11-19, evening): ROT-OUTLIERS, then BLOWOUT-MINUTES, one fresh chat each

ROT-SHAPE and JS-TESTS are done and merged. These two build on ROT-SHAPE (`docs/agents/tasks/rot-shape.md`).

### ROT-OUTLIERS: deep-bench players still get starter-like minutes

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task ROT-OUTLIERS. Add a board row and mark it "in progress (Codex)".

Context: ROT-SHAPE (docs/agents/tasks/rot-shape.md, merged 2026-11-19) fixed the league-wide rotation shape: role-group
minutes now land within about 1 mpg of Basketball Index healthy-rotation minutes. Individual outliers remain because
their starting minutes_projection is far too high: Bruce Brown NYK (game target 25.1, plays ~19.9, Basketball Index 4.5)
and Luke Kennard PHX (21.1, plays 17.4, BBI 5.0); Jordan Poole NOP (24.5 -> 10.2 after ROT-SHAPE, BBI 8.2) shows the
coach can correct when the inputs allow it.

Step 1 (measure, read-only): over 2 seeds of one headless regular season (AI coaches, canonical 2026-27 rosters), list
the 25 players whose played minutes exceed Basketball Index healthy_rotation_mpg the most, and the 25 who fall shortest
(data/research/bbi/tools/minutes_players.json, local only, never commit). For each, find why: the starting
minutes_projection, the depth/role builder (save.py around the role builder ROT-SHAPE changed), position slotting (a
backup slot forced onto a weak player), or the coach's game model. Give file:line references.
Step 2 (fix): make the depth chart follow each team's real talent order and positional needs, so a clearly weaker
player is not handed rotation minutes because he fills a position slot. Do not copy Basketball Index minutes into the
game and do not change any player ratings; the coach model must produce the minutes. Keep the user's rough minutes
targets driving their own team (AGENTS.md rule 8) and keep ROT-SHAPE's role-group results.

Files you may touch: save.py rotation/depth/role code, the coach minutes helpers in sim.py (another agent may edit
sim.py for player value; keep your edits contained to minutes/rotation functions), tests, docs/agents/tasks/rot-outliers.md.
Do not touch transactions.py, trade_*.py, draft.py, real_prospects.py, impact_value.py.
Acceptance: the outlier lists before/after (Brown and Kennard within about 5 mpg of their reference unless you show the
coach has a sound reason), ROT-SHAPE's role-group table still within 1.5 mpg, focused tests, both scorecards
(calibration_report.py replay-real-minutes in inputs mode 18/18; validate-season-probabilities --runs 100 with
NBA_GM_RATINGS_MODEL=inputs_v1: Brier and log loss not worse than 0.1945 / 0.5750) and bash scripts/run_core_tests.sh.
Leave changes uncommitted; write the report and set the board row to review.
```

### BLOWOUT-MINUTES: the coach should rest players in blowouts and react to foul trouble

**Absorbed by HEAVY-MINUTES (Claude, 2026-11-19); do not dispatch.** See `docs/agents/tasks/heavy-minutes.md`.

Suggested settings: GPT-6.2 Sol, Medium, fresh chat. Start only after ROT-OUTLIERS is reviewed.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task BLOWOUT-MINUTES. Add a board row and mark it "in progress (Codex)".

Goal (AGENTS.md rule 8): the modeled coach decides actual playing time game by game and in-game: foul trouble, fatigue,
hot or cold hands, blowouts, matchups. ROT-SHAPE found that the current game path has no blowout substitution step and
that personal fouls are assigned after minutes and scoring are decided (docs/agents/tasks/rot-shape.md, "Where the
flatness came from": sim.py:550, sim.py:616, sim.py:1006).

Step 1 (measure): from real 2025-26 data the repo already has (box scores under data/research, see
docs/obsidian-vault or grep for boxscore loaders), measure how starters' minutes fall with the final margin (e.g. by
margin buckets 0-5, 6-10, 11-20, 21+) and how foul counts relate to minutes. Report the real curves.
Step 2 (fix): add a blowout-rest effect and a foul-trouble effect to the coach's in-game minutes, fitted to those real
curves, keeping each team's total at 240 (overtime aside) and keeping game-to-game variation realistic. Bench players
gain the minutes starters lose. Keep it deterministic under the seed and cheap (speed budget AGENTS.md rule 10).

Files you may touch: the coach/minutes code in sim.py (keep edits contained; another agent may edit sim.py for player
value), tests, docs/agents/tasks/blowout-minutes.md. Do not change player ratings.
Acceptance: before/after starter-minutes-by-margin table vs real, both scorecards (as in ROT-OUTLIERS: 18/18;
Brier/log loss not worse than 0.1945 / 0.5750), bash scripts/run_core_tests.sh. Leave changes uncommitted; report; board row to review.
```

---

## Done (2026-11-19): ROT-SHAPE and JS-TESTS (merged; kept for reference)

### ROT-SHAPE: AI coach rotation shape vs Basketball Index minutes projections

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task ROT-SHAPE. Add a board row and mark it "in progress (Codex)".

Goal: the AI coach's rotations are too flat. Compared with Basketball Index's 2026-27 healthy-rotation minutes
(data/research/bbi/tools/minutes_players.json, local only: never commit it), the game's starting minutes targets
(players' minutes_projection) give stars about 2 fewer minutes per game and back-of-rotation players about 7 more.
Several deep-bench players get about 20 minutes against about 5 (Bruce Brown NYK, Mitchell Robinson BOS, Luke
Kennard PHX, Jordan Poole NOP). Overall correlation is 0.81 over 329 matched players.

Step 1 (measure, read-only): sim one regular season headlessly (canonical 2026-27 rosters, AI coaches for all 30 teams,
2-3 seeds) and compare actual minutes per game played with healthy_rotation_mpg by Basketball Index rotation_role
(Star / Key / Starter / Rot). Find where the flatness comes from: the starting minutes_projection, the coach's
game-by-game minutes model, fatigue or foul handling, or blowout rest. Give file:line references.
Step 2 (fix): tune the rotation shape where the cause lives so the role-group means land within about 1.5 minutes per
game of Basketball Index. Keep the team total at 240 and keep realistic game-to-game variation (project rule 8: the
user's rough targets still drive their own team). Do not change any player ratings. Do not copy Basketball Index
minutes into the game as data; the shape must come from the coach model.

Files you may touch: the minutes and rotation code you identify (likely sim.py and coach/rotation helpers), tests, and
docs/agents/tasks/rot-shape.md. Do not touch health.py, staff.py, injury_model.py, court_influence.py or spatial.py:
the coordinator has uncommitted, under-test changes in health.py, staff.py and three development tests
(test_foundation, test_prospect_development, test_prospect_learning). Leave those files alone.
Acceptance: focused tests, both scorecards (calibration_report.py replay-real-minutes in inputs mode: 18/18 in range;
validate-season-probabilities --runs 100: Brier and log loss not worse than 0.1960 / 0.5790), and the core tests
(bash scripts/run_core_tests.sh). Report the before/after role-group table.

When done: plain-language summary (TL;DR first) in docs/agents/tasks/rot-shape.md. Set the board row to "review". Do
not commit.
```

### JS-TESTS: repair the eight stale browser-interface tests

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task JS-TESTS. Mark its board row "in progress (Codex)".

Goal: eight Node tests under tests/*.test.cjs fail on the committed code. They are not part of the Python suite, so
nobody noticed. They fail for stale reasons, not because the game is broken:
  first_hour_ui (playerRustMarkup / captureTeamSignalBars not defined), gui_simulation_motion (expects
  season-opponent-result-header), player_pages (document is not defined; also expects the text "Health risk", which
  the player card now shows as "Injury risk" plus a body map), postseason_ui (expects an old
  card-board.css?v=... version string in index.html), seasonal_clipboard (origin markers not found; async
  "action is not defined"), starter_workspace (two boolean expectations), startup_video (cloneNode not a function in
  the test's fake DOM), ui_product_audit (extensionCapRows not defined).
Run each with: node tests/<name>.test.cjs

For each test: find why it fails (renamed helper, moved markup, stale version string, incomplete fake DOM, or a real
bug). Update the test so it checks the same user-facing behavior against today's code. Don't delete checks to make
them pass. Don't pin cache-busting version strings; match the pattern instead. If a failure is a real bug in
src/nba_gm_data/gui/app.js, do not fix it: describe it in your report.

Files you may touch: tests/*.test.cjs only (and test helper files they load). No changes to src/.
Acceptance: all tests/*.test.cjs pass (for f in tests/*.test.cjs; do node "$f" || echo FAIL $f; done), and the
Python GUI guards still pass (PYTHONPATH=src .venv/bin/python -m unittest tests.test_gui_concept71).
Report: docs/agents/tasks/js-tests.md, plain language first: one line per test (cause, fix, any real bug found). Set
the board row to "review". Do not commit.
```

---

## Done: (2026-11-18, late night): DEV-TUNE (reviewed 2026-11-19)

### DEV-TUNE: player aging and development curves to match Basketball Index

Suggested settings: GPT-6.2 Sol, Medium (High if it stalls), fresh chat or the DEV chat.

```
Read AGENTS.md, docs/agents/BOARD.md and your own report docs/agents/tasks/dev-growth-vs-bbi.md first. You own DEV-TUNE;
add a board row "in progress (Codex)".

GOAL: retune development so the game's age curve and year-to-year spread match Basketball Index (your report):
growth strongest at 19-22, broad peak ~23-26, decline starting by 27-30 (offense earlier than defense), steeper late
decline; and realistic spread around each player's expected change (BBI overall 80% band ~ -1.1..+0.8 of its scale,
measured relative to starting spread as in your report).

SCOPE: src/nba_gm_data/health.py monthly_trait_delta and its aging/growth/noise constants (and the development config
values they read), plus development_outlook.py if its expected-change helper needs the same constants. Do NOT edit
health.development_staff_modifiers or health.coach_development_by_team (Claude is rewiring coach/staff effects), the
injury functions in health.py (injury model v2 just landed), sim.py, staff.py or staff_lifecycle.py.
RULES: ratings-first (do not change any player's starting ratings); keep both rating sets working (legacy and
inputs_v1); determinism (seeded); no clipping at 100. Spread should come mostly from season-level shocks (role, health,
breakouts), not month-to-month noise that averages out.
CHECKS: re-run your DEV comparison (age-by-band medians and spread bands, both rating sets) and show before/after
tables; tests/test_development_outlook.py, tests/test_prospect_development.py, tests/test_development_coverage.py,
bash scripts/run_core_tests.sh; and the real-stat scorecard is unaffected at season start (development only changes
ratings over time) — say so if you confirm it.
REPORT: append "DEV-TUNE results" to docs/agents/tasks/dev-growth-vs-bbi.md, plain language first. Board row to
"review". Do not commit. Don't poll long runs more than every 20-30 minutes.
```

---

## Done: (2026-11-18, night): STAFF-LIFE and BBX-2, one fresh chat each

Suggested settings: GPT-6.2 Sol, Medium. Claude is rebuilding the injury engine: do NOT edit src/nba_gm_data/health.py,
sim.py, schema.py, or the health/injury functions in save.py, app_actions.py and gui/app.js. Don't poll long runs more
than every 20-30 minutes.

### STAFF-LIFE: staff age, change over time, retire, and a refilled coach pool

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/coaching-overhaul.md (audit + user decisions) first. You own
STAFF-LIFE; add a board row "in progress (Codex)". This is the lifecycle part of the coaching overhaul; Claude will later
rewire the rating EFFECTS, so do not change how ratings affect games, development, injuries or scouting.

BUILD (new module src/nba_gm_data/staff_lifecycle.py; edits to staff.py; one call from the season rollover):
1. Every staff member gets an age and years of experience. Real staff: use experience/records from the existing sources
   (data/research/coaches_espn_2026.json, staff_*_team_pages_2026.json) where present; otherwise seeded plausible values
   by role (deterministic from save seed + person id). Generated staff likewise.
2. Yearly change at season rollover: each skill and personality rating drifts by age and experience (younger staff tend
   to improve, older staff decline; experience grows game-management-type skills), with seeded noise. Keep the 20-96
   scale; no clipping at 100 issues (rule 3). Write the change log per person (season, rating deltas) so the GUI can
   show it later.
3. Retirement: probability rising with age (and after being fired late in a career). Retired staff leave the market.
4. Pool refill each offseason: new generated candidates enter (young assistants, promoted coordinators becoming head
   coach candidates), so the free-agent pool never runs dry and its quality distribution stays realistic (include some
   strong candidates; today's best generated head coach is grade 76 vs top real coaches ~93).
5. Reputation: a stored reputation that moves with results vs expectations (team wins vs pre-season expectation, playoff
   success); job security follows reputation and results instead of staying static.
6. Determinism: all randomness seeded from the save seed + season + person id; same save + seed = same result.

HOOK: call your rollover function from save.age_staff_contracts (the season rollover step that already ages contracts).
Keep that edit to a single call; do not touch other save.py functions.
TESTS: new tests/test_staff_lifecycle.py (aging direction by age, retirement, pool refill keeps a healthy distribution,
determinism, reputation moves with results). Run bash scripts/run_core_tests.sh and the staff tests in tests/test_foundation.py.
REPORT: docs/agents/tasks/staff-life.md, plain language first. Board row to "review". Do not commit.
```

### BBX-2: tidy tables from the new raw Basketball Index captures

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/tasks/bbx-tool-extract.md and docs/agents/tasks/bbi-full-capture.md.
You own BBX-2; add a board row. Data only: do not edit src/ or tests/.

Extend scripts/bbi_extract_tools.py (or add scripts/bbi_extract_captures.py) to turn these raw captures (git-ignored,
under data/research/bbi/captures/) into documented, reproducible tables in data/research/bbi/tools/ (each <= ~5 MB,
gzip larger CSVs), matching players to our ids (report match rates; never guess):
- fanspo_tools/progression/bbi_progression_all.json.gz: per player-season x 164 measures (impact metrics EPM/RAPM/DRIP/
  DPM/RAPTOR/BPM, talent grades, usage...) plus roles, age, minutes; keep the league distributions as a separate file.
- fanspo_tools/playoff_talent/bbi_playoff_talent_3yr.json.gz: 3-year playoff windows x 386 measures.
- fanspo_tools/lineup_explorer/bbi_lineup_explorer_2013_2026.json.gz: 61,037 lineups (players, minutes, ratings, role
  mix, 24 talent grades).
- fanspo_tools/xpoints/bbi_xpoints_lineups_2025_26.json.gz: per-team lineups with exact possessions and expected points.
- tools/role_labs/bbi_role_labs.json.gz: per-player role entries and the model coefficients (document what fields mean
  from the data and the saved Role Lab pages in captures/tools/).
REPORT: append a "BBX-2" section to docs/agents/tasks/bbx-tool-extract.md, plain language first. Board row to "review".
Do not commit.
```

---

## Done: (2026-11-18, evening): two read-only engine-vs-evidence comparisons, one fresh chat each

Suggested settings: GPT-6.2 Sol, Medium. Both READ-ONLY for src/ and data/canonical (Claude is working there). Scripts in
scripts/research/, outputs in output/<task>/. Don't poll long runs more than every 20-30 minutes.

### DEV: Our development and aging vs Basketball Index's growth curve

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/bbx-tool-extract.md first. You own DEV; add a board row.

Evidence: data/research/bbi/tools/growth_*.json / .csv.gz (Basketball Index's talent age-growth model: actual vs
1-year-ahead projection by age and role, forward projections, development vs expectation, per-coach development).
Our engine: player development runs monthly in src/nba_gm_data/health.py (monthly_trait_delta; aging, staff/coach effects,
ceilings); development_outlook.expected_rating_changes gives the expected 12-month change with no noise.

QUESTIONS (plain-language answers with tables):
1. Age curve: for each age 19..36, what is Basketball Index's typical one-year change in offensive, defensive and overall
   talent (median and spread, by minutes band)? What does our engine's expected 12-month change give for the same ages,
   for players of similar level (use expected_rating_changes on the 2026-27 league; both rating sets if practical)?
   Where do the curves disagree (peak age, decline start, decline speed, young growth size)?
2. Spread: how much do real players vary around the typical change (their 50/80/90% bands) vs our engine's variation
   (simulate a season with seeds, or use the monthly noise the engine applies)?
3. Coaches: how big are Basketball Index's per-coach development effects (players' actual minus projected), and how
   big is our staff/coach development effect? Is ours in a realistic range?
4. Propose concrete parameter changes (which constants, by how much) with expected effect. Don't change src/.

REPORT: docs/agents/tasks/dev-growth-vs-bbi.md, plain language first. Board row to "review". Do not commit.
```

### INJ: Our injuries vs Basketball Index's injury tracker

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/bbx-tool-extract.md first. You own INJ; add a board row.

Evidence: data/research/bbi/tools/injury_*.json (time out by diagnosis/body part with return-day percentiles,
recurrence, short- and long-term aftermath, player histories, durability, games missed per 82).
Our engine: injuries are generated in src/nba_gm_data/health.py (injury model config, durations, recurrence, rust).

QUESTIONS (plain-language answers with tables):
1. Simulate one or more full seasons headless (an existing soak or quick-sim script; seeded) and compare our league:
   injuries per team-season, games missed per 82 by role/age, the distribution of days out (25/50/75/90th percentiles)
   overall and for the most common body parts, share of season-ending injuries, recurrence within a season.
2. Short-term aftermath: Basketball Index shows minutes and shooting after return (injury_short_term.json). Compare with
   our rust penalty (sim.rust_penalty_points; ~0.08 per rust point, capped at 4) and how long it lasts.
3. Propose concrete parameter changes with expected effect. Don't change src/.

REPORT: docs/agents/tasks/inj-injuries-vs-bbi.md, plain language first. Board row to "review". Do not commit.
```

---

## Done: (2026-11-18, afternoon): BBX, extract the saved Basketball Index tool pages

### BBX: Turn the saved Growth Curve, Injury Tracker and Minutes/Talent pages into clean tables

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task BBX; add a board row "in progress (Codex)".

Basketball Index tool pages were saved (signed-in, personal-use subscription) as self-contained HTML in
data/research/bbi/captures/tools/ (git-ignored): bbi_tool_growth_curve.html (~7 MB), bbi_tool_injuries.html (~5.5 MB),
bbi_tool_minutes_talent_2026_27.html, bbi_tool_offensive_role_lab.html, bbi_tool_defensive_role_lab.html.
Their data is embedded in the pages (JSON/JS arrays inside <script>). Do NOT fetch anything from the web.

GOAL: extract every embedded table into tidy, documented files under data/research/bbi/tools/ (tracked, compact JSON or
CSV; keep each under ~5 MB, gzip if larger), plus a parser script scripts/bbi_extract_tools.py (standard library only,
reproducible: rerunning gives identical files).
1. Growth Curve (priority): per player x season x talent metric: actual value, the model's 1-year-ahead projection, and
   the 50/80/90% intervals; forward projections; the "development vs expectations" per player; the per-coach table
   (players' actual minus projected under each head coach). Also save the methodology text verbatim (it is short).
2. Injury Tracker: per injury type/body part: typical days missed, the range, recurrence/aftermath and durability fields,
   and any per-player injury history tables it embeds.
3. Minutes/Talent 2026-27: per player projected games missed, MPG, role/talent grid fields; per-team tables.
4. Role Labs: whatever per-player tables they embed (role, estimated impact of role changes).
For each output, document fields, units, row counts and the player identifier used (name/team/ids) in
docs/agents/tasks/bbx-tool-extract.md, and match players to our ids where you can (report the match rate; never guess).

BOUNDARIES: new script, data/research/bbi/tools/, your report. Do not edit src/ or tests/ (Claude is working there).
REPORT: plain language first. Board row to "review". Do not commit. Don't poll long runs more than every 20-30 minutes.
```

---

## Done: (2026-11-18): PRO-2, implement the rookie input fix

### PRO-2: Start real 2026 rookies on the estimator's rookie setting

Suggested settings: GPT-6.2 Sol, Medium, fresh chat (or continue the PRO chat if it still has context).

```
Read AGENTS.md, docs/agents/BOARD.md and your own report docs/agents/tasks/pro-prospect-inputs.md first. You own PRO-2;
add a board row "in progress (Codex)". Claude approved section 3's first step ("rookie technique only").

DO:
1. In scripts/build_player_inputs.py, estimate the real 2026 entrants with no completed NBA season (the 53 players your
   audit identified; derive the set from data, don't hard-code names) with the estimator's existing prospect=True setting.
   Keep eligible evidence overlays and the measured-tendency step exactly as they are. Do NOT apply the involvement
   (usage) shift yet; that needs held-out validation first (separate task).
2. Rebuild data/canonical/player_inputs_2026_27.json (+ .gz) with the script. Confirm only those players' technique inputs
   changed (diff summary: players changed, inputs changed, everything else identical).
3. Run, with NBA_GM_RATINGS_MODEL=inputs_v1:
   - PYTHONPATH=src .venv/bin/python scripts/ratings_sniff_report.py  (report Peterson, Boozer, Flagg, Harper ranks)
   - PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230 --mode replay-real-minutes
   - PYTHONPATH=src .venv/bin/python -m nba_gm_data.cli validate-season-probabilities --runs 100  (~20 min; run in the
     background and check back at most every 20-30 min)
   Compare with the current baseline: replay 18/18 in band, points per-36 mean abs 2.595; odds Brier 0.1950, log loss
   0.5775, spread error 5.223, total error 5.421. Don't regress either scorecard silently; report the numbers.
4. bash scripts/run_core_tests.sh

BOUNDARIES: scripts/build_player_inputs.py, data/canonical/player_inputs_2026_27.json(.gz), new tests, your report.
Claude is editing src/nba_gm_data/history_store.py and save.py (save size) — don't touch src/.
REPORT: append "PRO-2 results" to docs/agents/tasks/pro-prospect-inputs.md, plain language first. Board row to "review". Do not commit.
```

---

## Done: (2026-11-17 night): two read-only research tasks, one fresh chat each

Suggested settings: GPT-6.2 Sol, Medium. Both are READ-ONLY for src/ and data/ (Claude is editing transactions.py,
trait_adapter.py, impact_value fit, sim/box files, and tests). New scripts go in scripts/research/, outputs in output/<task>/.
Don't poll long runs more than every 20-30 minutes.

### PRO: Are draft prospects' estimated inputs inflated? (diagnosis + proposal)

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task PRO; add a board row "in progress (Codex)".

SYMPTOM: under the new ratings (NBA_GM_RATINGS_MODEL=inputs_v1), incoming rookies and generated draftees rank too high.
2026 rookie Darryn Peterson (19) is 15th in the league by overall (scripts/ratings_sniff_report.py), and Cameron Boozer,
Dylan Harper, Aday Mara and Caleb Wilson show up near the top of several input-based ratings. Earlier notes also say
the prospect path's estimated involvement (usage) runs high.

Players without measured input records get inputs from the estimator's prospect path (src/nba_gm_data/input_estimator.py,
called from ratings_model._install_generated_players; tendency inputs are mapped with data/canonical/tendency_scale_map.json).

QUESTIONS:
1. How do prospects' estimated inputs compare with REAL first-season inputs of recent rookies who have measured data
   (e.g. 2023, 2024 and 2025 draftees: their inputs come from Basketball Index evidence)? Compare by draft slot band
   (top 5, 6-14, 15-30, second round) for the skill groups, physical inputs and involvement (T08). Use league percentiles.
2. Which part of the pipeline causes any gap (the estimator's anchors, the scale map, the trait adapter's percentile step,
   or the legacy traits it starts from)? Show the evidence.
3. Propose the smallest fix, with expected effect on where Peterson / Boozer / Flagg (2025 #1, measured) would rank.
   Do NOT implement it in src/ (Claude will); a prototype in scripts/research/ that prints before/after ranks is welcome.

REPORT: docs/agents/tasks/pro-prospect-inputs.md, plain language first, tables for the comparison. Board row to "review". Do not commit.
```

### SAV: Save size after many seasons (analysis + options)

```
Read AGENTS.md and docs/agents/BOARD.md first ("Save size (open, needs user decision)"). You own task SAV; add a board row.

PROBLEM: a career's history database grows ~60 MB per season. At ~8 seasons the save passes the 512 MB portable-export cap
(src/nba_gm_data/save_recovery.py, MAX_EXPANDED_BYTES); local autosaves allow 16 GB, so play continues, but players
can't export/share a long career, and every save step gets slower (validation and backups scale with size).

A real 8-season save exists: output/t2b/checkpoint/current/ (copy it to output/sav/ before reading; a builder is still
writing to output/t2b — never modify anything there).

QUESTIONS:
1. What is stored: break the history SQLite (src/nba_gm_data/history_store.py) and the save JSON down by record kind and
   by season (MB per kind per season). What dominates (box scores? play-by-play? events?)
2. What actually reads each kind: GUI screens, AI, stats pages, awards, records. Which old data is never read after a
   season ends, or only read in summarized form?
3. Options with measured sizes, e.g. compress payloads, store old seasons' box scores as season totals, drop
   play-by-play after N seasons, separate an optional "full archive" from the portable export. For each: projected size at
   10 and 20 seasons, what the player loses, implementation size.
Prototype measurements in scripts/research/ on the copied save are welcome; do not change src/.

REPORT: docs/agents/tasks/sav-save-size.md, plain language first, a short options table for the user. Board row to "review". Do not commit.
```

---

## Done: (2026-11-17 evening)

### PLY: Real playoff performance data (evidence for the "playoff translation" rating)

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task PLY; add a board row "in progress (Codex)".

WHY: the new ratings' hidden "playoff translation" rating is built only from shooting, self-creation and perimeter-defense inputs. It ranks Derrick White 1st, Jokic 101st and Giannis 217th. It feeds the sim's impact number and the AI's superstar trade tier. Claude will refit it to real evidence (ratings-first rule). Your job is ONLY to collect that evidence; do not change ratings, inputs or engine code.

DATA: per-player, per-season regular-season AND playoff box totals for every player in data/research/player_career_stats.json, seasons 2013-14 through 2025-26.
- Reuse scripts/import_player_career_stats.py, which already fetches ESPN's public athlete stats endpoint with seasontype=2 (regular season). Postseason is seasontype=3 on the same endpoint. Write a new script scripts/import_player_playoff_stats.py (standard library only; reuse helpers by import, don't copy-paste large blocks), polite rate limiting (<= 2 requests/second), resumable cache under output/ply/.
- Fields per player-season and season type: games, minutes, points, rebounds (off/def if available), assists, steals, blocks, turnovers, fgm/fga, fg3m/fg3a, ftm/fta, personal fouls if available, team.
- Output: data/research/player_playoff_stats.json (same player keys and style as player_career_stats.json; include source URLs, retrieved_at and coverage counts). Keep it compact: no raw API payloads in data/.

CHECKS: spot-check 5 players against Basketball Reference playoff totals (e.g. Jokic 2023, Giannis 2021, Jamal Murray 2023, Jalen Brunson 2024, SGA 2025) and record the comparison in the report. Report coverage (players with any playoff minutes; player-seasons).

BOUNDARIES: new script, new data file, output/ply/, your report. No other files.
REPORT: docs/agents/tasks/ply-playoff-data.md, plain language first. Board row to "review". Do not commit. Don't poll long runs more than every 20-30 minutes.
```

---

## Done (2026-11-17 afternoon): two bug tasks from the test triage, (BUG-A and BUG-B reviewed)

Suggested settings for both: **GPT-6.2 Sol, Medium**, fresh chat. Do not resume the old TST or T2b chats (TST is committed; Claude finishes T2b).
Rules for both: don't babysit long runs by polling every few minutes (it burns usage). Start long runs in the background, do other work, and check at most every 20-30 minutes. If you can't fix something, say so plainly in the report; never weaken a test to make it pass.
Claude owns: `impact_value.py`, `bbi_evidence.py`, `trait_adapter.py`, `ratings_model.py`, `sim.py`, `offense.py`, trade *valuation* in `transactions.py`, `data/canonical/impact_value_fit.json`, and `scripts/build_mature_fixture.py` / `output/t2b/` (a builder is running; don't touch it). Don't edit those.

### BUG-A: Pick protections and pick-swap trades

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/tst-suite-triage.md first. You own task BUG-A; add a board row "in progress (Codex)".

The test triage quarantined three tests that look like real bugs in draft-pick handling. Each has a unittest.skip("needs review: ...") marker; the report lists the failing check.
1. tests/test_imported_rookie_ratings.py test_pick_protections_are_unchanged_for_both_starting_versions: the current starting version loads ZERO pick protections where the archived data had 85 (e.g. protected first-round picks owed between teams). Find where pick obligations are loaded for a new save (storage/import path) and why they're empty. If real protections are being dropped from new saves, that is the most important fix here.
2. tests/test_foundation.py test_ai_offer_packages_can_create_pick_swap_sweeteners: AI offer packages never include a pick swap. Find which eligibility rule excludes them.
3. tests/test_foundation.py test_trade_evaluation_uses_team_context_and_legality: the decision comes back as something other than accept/reject. Decide whether the test is stale (a newer counteroffer outcome is intended; cite the commit) or the engine is wrong.

For each: find the cause, fix it in src/ if it's an engine bug (smallest change; keep seeded results unchanged unless the fix requires it, and say so), remove the skip marker, and make the test pass with its original assertion. If the test is stale, update it with a one-line comment citing the evidence.

ALLOWED FILES: pick/draft-pick modules (pick_rules.py, pick_presentation.py, pick-related functions in transactions.py and storage.py), trade offer package generation in transactions.py (NOT player valuation), the three tests above.
CHECKS: the three tests, PYTHONPATH=src .venv/bin/python -m unittest tests.test_foundation tests.test_imported_rookie_ratings, and bash scripts/run_core_tests.sh.
REPORT: docs/agents/tasks/bug-a-picks.md, plain language first (what was wrong, what it meant in the game, what changed). Board row to "review". Do not commit.
```

### BUG-B: Missing heights, staff budget, duplicate draft-class work, social-post evidence

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/tst-suite-triage.md first. You own task BUG-B; add a board row "in progress (Codex)".

Four quarantined tests in tests/test_foundation.py look like real bugs (each has a unittest.skip("needs review: ...") marker; the report lists the failing check):
1. test_rostered_players_have_dashboard_core_data: 11 rostered players have no height (e.g. Tucker DeVries, BOS). Fill the real heights (and weight/wingspan if also missing) from a public source (NBA.com, Basketball Reference, team rosters, combine data). Record each value's source in your report. Put them where the game's other player measurements live; find that path first. Don't invent values.
2. test_staff_queue_keeps_live_strategy_from_raising_budget: the AI's live strategy raises a team's staff budget when the test says it must not. Find the guard and fix it, or show the test is stale (cite a commit).
3. test_future_draft_pick_recommendations_use_generated_class: the generated draft class is built twice instead of once (wasted work). Remove the duplicate computation without changing results.
4. test_extension_social_requires_sim_evidence_for_health_money_position_and_conference_claims: a fan post claiming "durability bet" is accepted when the test expects it to be rejected (injury risk 0.0 with 64 missed games). Fix the evidence check so health claims need matching sim evidence.

For each: fix the cause (smallest change), remove the skip marker, and make the test pass with its original assertion; or, if the test is stale, update it with a one-line comment citing evidence.

ALLOWED FILES: player measurement data for the 11 players, staff budget code, the draft recommendation code path, the social-post validator, and tests/test_foundation.py (these four tests only). If a fix needs a file in Claude's list above, stop and describe it instead.
CHECKS: PYTHONPATH=src .venv/bin/python -m unittest tests.test_foundation, bash scripts/run_core_tests.sh.
REPORT: docs/agents/tasks/bug-b-data-staff.md, plain language first. Board row to "review". Do not commit.
```

---

## Earlier (2026-11-17 morning; SPD and TST done, T2b finishing under Claude)

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
