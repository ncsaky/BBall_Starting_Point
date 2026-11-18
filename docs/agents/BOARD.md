# Agent coordination board

Single source of truth for who is doing what. Rules are in `/AGENTS.md`. Coordinator: **Claude Code**. Worker: **Codex** (limited usage). Update your row when you start, finish, or get blocked.

_Last updated: 2026-11-19 by Claude Code (overnight session)._

## Where things stand (handover snapshot, 2026-11-16)

- **Playable game:** private friends beta. GUI files have **not changed since Oct 30**. Nearly all of the user's Oct 29 wishlist (`docs/MINIMUM_COMPLETION_BACKLOG_2026_10_29.md`) is open. See the status table below.
- **Player model (track B):** the 94-input model is approved, and its schema/persistence are implemented (Nov 12–13). Ratings evidence research is extensive (`docs/ratings-evidence-2026-10-29/`), but **no rating changes have been applied to game data**.
- **Experimental possession engine (track C):** Codex milestones 2–16 (Nov 13–16): interior defense, creation/passing, screens, pick-and-pop, pass recovery, then four performance passes on the recovery evaluator. All **default OFF**. The last coordinator recommendation was perimeter contests/closeouts next (not dispatched). Open problem: the recovery-enabled engine costs ~6–7x the old pass model per possession.
- **Git:** last commit 2026-09-30. ~2,000 files changed since, including almost all tests and scripts. Blocked on the Xcode license until the user runs `sudo xcodebuild -license accept`.

## Direction (user decision, 2026-11-16)

Two stages (`docs/agents/ENGINE_ROADMAP.md`):
- **Stage 1 (now):** the 94-input ratings drive the current engine, with a new player card and new front-office valuations. Design: `docs/agents/STAGE1_DESIGN.md`.
- **Stage 2:** the possession engine becomes the real engine.

GUI wishlist work is parked.

## In flight

| Task | Owner | Status | Files it may touch |
|---|---|---|---|
| LINEUP-FIT Lineup chemistry from real lineups | Claude (overnight agent, branch `claude/lineup-fit`) | **done** (merged 2026-11-19 via overnight-integration; creator x shooter term stays off): fitted to Basketball Index xPoints lineups 2025-26 with each player's own effect held fixed. Three effects added (shooters next to a creator, fifth shooter, non-shooter pile-ups on defense); creator overlap and lead playmaker already matched. Report: `docs/agents/tasks/lineup-fit.md`. | `src/nba_gm_data/lineup_fit.py`, `sim.py` (team features + `mean_off_rating`), `scripts/fit_lineup_fit.py`, `data/canonical/lineup_fit.json`, `tests/test_lineup_fit.py` |
| BODYMAP Injury body map on the player card | Claude | **done** (2026-11-19): mini figure in the evidence row; new "Health & Injury Outlook" card page with front/back hotspots from the sim's per-body-part model; current injury flagged (older saves via the event's area). | `src/nba_gm_data/injury_model.py`, `app_actions.py`, `gui/app.js`, `gui/interface.css`, `tests/test_injury_model.py` |
| OVERNIGHT branches (2026-11-19, Claude + Opus agents) | Claude | **done**: all merged into main 2026-11-19 (overnight-integration, ratings-audit, prospect-realism). | branches only |
| PROSPECT-REALISM Generated draft classes and 94-input development size | Claude (overnight agent, branch `claude/prospect-realism`) | **done** (merged 2026-11-19 as built, per the user's push toward the 94-input ratings). Combined check: 334 core + 154 draft/development/prospect tests OK; scorecards unchanged; two-season AI league (94-input): stars unchanged (7 at 72+ both), best generated draftee 55.6 -> 66.5, 2 draftees in top 100 (was 0). Known: older ratings now make too many young stars from picks 4-30 (accepted); top-3 picks become stars less often than real (follow-up, ideally with NCAA data). | `ratings_model.py`, `draft.py`, `health.py`, `input_estimator.py`, tests |
| NCAA-BT College data from Barttorvik | Claude | **data captured 2026-11-19**: player tables 2008-2027 (2027 = current season, early), team ratings and four factors 2008-2027 (`raw/teams/`), head coach per team-season for 278 programs 2008-2027 (`raw/coaches.json`, 5,465 rows). All local only in `data/research/barttorvik/raw/`. Loader `scripts/research/barttorvik.py`. Also available, not captured: player game logs, play-by-play shot splits, schedules. Task file `docs/agents/tasks/ncaa-barttorvik.md`. | `scripts/research/barttorvik.py`, `data/research/barttorvik/` (git-ignored), task file |
| REAL-PROSPECTS Real college players in the 2027-2029 drafts | Claude (Opus agent) | **done** (merged 2026-11-19): 2027 class has 47 real college players (8 of the top 10), 2028 has 11, 2029 has 6; generated prospects fill the rest; 2030+ unchanged. Skills follow each player's college profile; prospect card shows college team, coach and a College Profile strip. Checks: 334 core + 70 draft/prospect tests OK; card verified in fresh saves (both rating sets). Refresh later in the college season with `scripts/research/real_prospects.py --apply-universe`. Open: 2028/29 top ends are generated (no high-school or international data); early-season order is shaky (4-6 games). Report: `docs/agents/tasks/real-prospects.md`. | `draft.py`, `real_prospects.py`, `input_estimator.py`, `data/canonical/real_prospects.json`, card files, tests |
| REAL-PROSPECTS-2 Scouts lead 2027; real recruits and internationals in 2028-29; declaration timing by save | Claude (Opus agent, worktree branch) | **review** (2026-11-18): 2027 order follows eight public boards (college model weight = games / (games + 20)); 247Sports top recruits and international prospects join 2028/2029; each save draws when every real player declares (returners come back a year older and developed). Across 20 seeds: real players fill 10/10 of the 2027 top 10, 8 of 2028's, 7 of 2029's; after review: board top-17 returners median 3 (1-4), generated No. 1 in 4% (2028) / 10% (2029) of saves. 2030+ unchanged. Card shows consensus or recruiting rank and the scouts' strengths/concerns. Report: `docs/agents/tasks/real-prospects.md`. | `scripts/research/real_prospects.py`, `real_prospects.py`, `draft.py`, `save.py` (one hook in `canonical_with_save`), `spatial.py` (board build cache), card files, `data/research/prospect_scouting/`, bundle + universe, tests |
| RATINGS-AUDIT Rim protection, blocks, value model | Claude (overnight agent, branch `claude/ratings-audit`) | **done** (merged 2026-11-19 after a combined check: 334 core OK, 18/18 both rating sets, odds new ratings Brier 0.1939 / log loss 0.5738 / spread 4.66 / totals 5.54; older ratings unchanged at 0.2140). Open questions for the user in `docs/agents/tasks/ratings-audit.md` (energy bigs, Ingram/Vucevic, contest-jump evidence, attack-recognition evidence, totals). | `defense.py`, `trait_adapter.py`, `impact_value.py`, `sim.py`, `save.py`, fit scripts and data |
| HEATMAPS Playmaking / on-ball D / help D court charts | Claude | **done** (2026-11-19, user-approved route A): Court Influence toggles Scoring/Playmaking and Overall/On his man/Help. Playmaking fitted to Basketball Index teammate eFG impact (out-of-fold r 0.59) and used by team zone profiles; defense charts split the existing zone defense. Scorecards unchanged (18/18; Brier 0.1955, log loss 0.5786). | `court_influence.py`, `spatial.py`, `shot_chart.py`, `scripts/fit_court_influence.py`, `gui/app.js`, `gui/interface.css`, tests |
| ROT-SHAPE AI coach rotation shape vs Basketball Index minutes | Codex | **done** (committed by coordinator in the overnight merge 2026-11-19; identical to Codex's working edits). Open follow-up: Bruce Brown still about 20 mpg vs 4.5. | Minutes and rotation code, focused tests, `docs/agents/tasks/rot-shape.md` |
| JS-TESTS Eight stale browser-interface tests | Codex | **done** (reviewed and committed 2026-11-19): all 29 Node test files pass (246 checks; one expected failure documents a startup-video retry bug). Real bugs found: player card page count starts at 1/2 on a three-page card; a missing default startup video retries on every click. | `tests/*.test.cjs` |
| STAFF-LIFE Staff lifecycle | Codex | **done** (reviewed and committed 2026-11-18): staff age, experience, rating drift, retirement, reputation, refilled pool. Rating effects unchanged (coaching overhaul next). | `src/nba_gm_data/staff_lifecycle.py`, `src/nba_gm_data/staff.py`, `src/nba_gm_data/save.py` (`age_staff_contracts` hook only), `tests/test_staff_lifecycle.py`, `docs/agents/tasks/staff-life.md` |
| INJ Injuries and return to play vs Basketball Index | Codex | **review**. Two complete 82-game runs hit 565 injuries by early February. Median absence was 3 days vs 6, and 95.7% returned with zero rust. Report includes role and age comparisons, repeat injuries, and parameter trials. Research only. | `docs/agents/tasks/inj-injuries-vs-bbi.md`, `output/inj-injuries-vs-bbi/` |
| DEV Player growth, aging and staff effects vs Basketball Index | Codex | **review**. Both rating sets decline later and vary less than Basketball Index. Report includes age-by-minutes tables, coach comparisons and in-memory tuning trials. 15 focused tests passed. Research only. | `docs/agents/tasks/dev-growth-vs-bbi.md`, `output/dev-growth-vs-bbi/` |
| DEV-TUNE Development curve and season-to-season spread | Codex + Claude | **done** (reviewed 2026-11-19): aging curve, youth boost and fading season draw accepted; season draw set to two-thirds of Basketball Index spread per the user (0.47 for 94-input ratings, 0.36 for older ratings; measured). Review fixed the head-coach calibration that re-ran on every save load. Code first reached main inside 5b6812c by mistake. | `src/nba_gm_data/health.py`, `src/nba_gm_data/staff.py`, `docs/agents/tasks/dev-growth-vs-bbi.md` |
| BBX Basketball Index saved tool extraction | Codex | **done** (reviewed and committed 2026-11-18). Growth Curve, Injury Tracker and 2026-27 Minutes/Talent extracted to data/research/bbi/tools/ (25 MB, reproducible); Role Labs pages held no player rows. | `scripts/bbi_extract_tools.py`, `data/research/bbi/tools/`, `docs/agents/tasks/bbx-tool-extract.md` |
| BBX-2 Basketball Index captured tables | Codex | **done** (reviewed and committed 2026-11-18). | `scripts/bbi_extract_captures.py`, `data/research/bbi/tools/`, `docs/agents/tasks/bbx-tool-extract.md` |
| PRO-2 Rookie technique for real 2026 entrants | Codex | **done** (reviewed and committed 2026-11-18). Peterson 15th -> 83rd, Boozer 64th -> 255th; replay 18/18; odds mixed (spread error 5.22 -> 5.03, Brier 0.1950 -> 0.1954). Involvement shift still open. | `scripts/build_player_inputs.py`, `data/canonical/player_inputs_2026_27.json(.gz)`, `tests/test_build_player_inputs.py`, `docs/agents/tasks/pro-prospect-inputs.md` |
| SAV Career save size | Codex + Claude | **done** (2026-11-18): user chose not to keep box scores past their season; Claude implemented retention in history_store (623 -> 215 MB at 10 seasons). | `docs/agents/tasks/sav-save-size.md`, `scripts/research/save_size_audit.py` |
| PRO Prospect input calibration | Codex | **done** (reviewed 2026-11-18); fix approved as PRO-2. | `docs/agents/tasks/pro-prospect-inputs.md`, `scripts/research/prospect_input_audit.py` |
| PLY Playoff translation evidence | Codex | **review**. Collected 2,963 regular-season and 1,401 playoff player-seasons across the 679-player career cohort. 398 played playoff minutes. Five Basketball Reference checks matched. | `scripts/import_player_playoff_stats.py`, `data/research/player_playoff_stats.json`, `output/ply/`, `docs/agents/tasks/ply-playoff-data.md` |
| BUG-B Missing measurements, staff budget, draft recommendations, social evidence | Codex | **done** (reviewed and committed 2026-11-17). Two historical snapshot tests now allow only the filled measurements. | `docs/agents/tasks/bug-b-data-staff.md` |
| BUG-A Pick protections and pick-swap trades | Codex + Claude | **done** (committed 2026-11-17). Claude marked the reviewed pick terms valid for data versions v6-v11 (Codex confirmed the same 420 picks), added a guard test, and gave the protected-pick test a full draft order. New saves now load all 85 terms; real 2027/2028 lotteries resolve them. | `docs/agents/tasks/bug-a-picks.md` |
| E2c Generated-player inputs | Codex | **accepted 2026-11-17** with E2b (134 focused + 329 core tests rerun OK). 134 focused tests pass; copied-save top-five median OVR 57.9 vs real 61.1, lottery minimum 37.0; deterministic, 0 card/engine mismatches. Full-suite diagnostic interrupted with failures; see report. No commits. | `src/nba_gm_data/input_estimator.py`, `tests/test_input_estimator.py`, `tests/test_ratings_model.py` (one user-authorized assertion), `docs/agents/tasks/e2c-generated-players.md`, `output/e2c/` |
| S1-E-inv Old-scale rating threshold inventory | Codex | **accepted 2026-11-16**. Report: `docs/agents/tasks/s1e-threshold-inventory.md` | `docs/agents/tasks/s1e-threshold-inventory.md`, `output/s1e/` |
| E3 Calibration targets and comparison tool | Claude (subagent) | **done** (5/5 tests verified). Report: `docs/agents/tasks/e3-calibration-targets.md` | `data/calibration/*`, `src/nba_gm_data/calibration_targets.py`, `scripts/build_calibration_targets.py`, `scripts/calibration_report.py`, `tests/test_calibration_targets.py` |
| BBI-CAP Basketball Index capture | Claude | **Goal (user, 2026-11-17): extract as much as possible; trim later.**<br>**Leaderboards Tool** (`bball-index.shinyapps.io/SoulYOLO3Lose/`, 664 metrics, every player-season 2013-14 to 2025-26): Values pass running in the pane (tab-1); Season Percentile, Season Grade, Season Value+ and Database Value+ passes chained to follow automatically. Files go to ~/Downloads as `bbi_leaderboard_<mode>_chunksNN-MM.json`. Import with `scripts/bbi_import_leaderboard.py`. The pane's downloads work, about 1 minute late. No playoff data in this tool.<br>**Fanspo-hosted BBI tools** (LEBRON, game LEBRON incl. 2026-27, shot/shooting talent, lineups, team stats, progression, xPoints play-by-play, playoff shooting): subagent exporting via their Export CSV controls to `data/research/bbi/captures/fanspo_tools/` with `manifest.jsonl`.<br>**Saved tool files:** Talent Age Growth Curve, Injury Tracker, 2026-27 Minutes/Talent, Role Labs (`captures/tools/`).<br>**Captured 2026-11-18 (signed-in, via each tool's own data request, saved as gzip downloads):** Playoff Talent Grades (3-year playoff windows, 4,344 player-windows x 386 measures, 2013-16 .. 2023-26) in `captures/fanspo_tools/playoff_talent/`; Lineup Explorer (61,037 real five-man lineups 2013-14 .. 2025-26: minutes, ORtg/DRtg/net, role mix, 24 talent grades such as spacing and rim protection) in `captures/fanspo_tools/lineup_explorer/`; Player Progression (165 measures incl. EPM, RAPM variants, DRIP, DPM, estimated RAPTOR, BPM per player-season 2013-14 .. 2025-26) in progress.<br>**Still to do:** xPoints suite (lineups, WOWY, play-by-play), Rotation Minutes-by-game app (coach rotations), NCAA section (check membership coverage); Skills, Similarity and Career Trends apps (mostly duplicates). Fanspo report-card crawl stopped (27 players kept for definitions). | `scripts/bbi_capture_leaderboard.js`, `scripts/bbi_import_leaderboard.py`, `scripts/bbi_capture_browser.js`, `scripts/bbi_import_fanspo.py`, `data/research/bbi/captures/` (git-ignored) |
| BBI Basketball Index capture plan and importer | Codex | **accepted 2026-11-16** (75 tests rerun OK) — 75 focused tests pass; absent/demo cache byte parity verified; report: `docs/agents/tasks/bbi-capture-plan.md` | `src/nba_gm_data/bbi_import.py`, `src/nba_gm_data/input_estimator.py`, `tests/test_bbi_import.py`, `data/research/bbi/`, `docs/agents/tasks/bbi-*.md` |
| E2 League-wide input estimator | Codex | **accepted 2026-11-16** by Claude (91 tests rerun OK; output tracked as `player_inputs_2026_27.json.gz`). Report: `docs/agents/tasks/e2-input-estimator.md` | `src/nba_gm_data/input_estimator.py`, `scripts/build_player_inputs.py`, `data/canonical/player_inputs_2026_27.json`, `tests/test_input_estimator.py` |
| E2b Hierarchical family priors | Codex | **accepted 2026-11-17** (coordinator decision, odds gain outweighs small real-stat regressions). 124 tests pass; spread/ranking gates pass; full game-odds errors improve. **Real-stat gate FAILS (assists/3PA); not accepted for activation.** Report: `docs/agents/tasks/e2b-elite-priors.md`.<br>**Coordinator view (2026-11-17):** recommend accepting. Odds Brier 0.2114 to 0.2029 (market 0.1962), log loss 0.6177 to 0.5975; real-stat regressions are small (assists +5%, 3PA flat) and points, FGA, rebounds and blocks improve. The top-50 mean on-court gap is still open. To be reviewed and committed together with E2c, which edits the same files. | `src/nba_gm_data/input_estimator.py`, `tests/test_input_estimator.py`, `data/canonical/player_inputs_2026_27.json`, `data/canonical/player_inputs_2026_27.json.gz`, `docs/agents/tasks/e2b-elite-priors.md` |
| Q1 Three small GUI fixes (next opponent after result, S-prefix shortcut, lottery grid order) | Claude (subagent) | **review**. 5 new JS tests pass; no browser check yet. Report: `docs/agents/tasks/q1-gui-small-fixes.md` | `src/nba_gm_data/gui/app.js`, `src/nba_gm_data/gui/interface.js`, `tests/gui_small_fixes.test.cjs` |
| PO01 Playoff Stats card (replaces playoff leaders list) | Claude (subagent) | **review**. Sortable all-player playoff table (points per game default). 6 JS + 3 Python new tests pass; core 329 OK; no browser check yet. Report: `docs/agents/tasks/po01-playoff-stats.md` | `src/nba_gm_data/gui/app.js`, `src/nba_gm_data/gui/card-board.css`, `src/nba_gm_data/gui/index.html`, `src/nba_gm_data/save.py` (`playoff_leaders` view only), `tests/playoff_stats_table.test.cjs`, `tests/test_playoff_stats_view.py` |
| T1 Make tests trustworthy | Claude (subagent) | **review**. Core suite `scripts/run_core_tests.sh`: 329 tests in about 160 s, passing. Full-suite leftovers listed below. | `tests/`, `scripts/run_core_tests.sh` |
| S1-B Adapter: inputs to the 15 hidden ratings | Claude | **done** (9 tests) | `src/nba_gm_data/trait_adapter.py`, `tests/test_trait_adapter.py` |
| S1-C Opt-in inputs model; development writes inputs | Claude | **done** (8 tests). Saves opt in with `meta.ratings_model = "inputs_v1"`; save-less tools with `NBA_GM_RATINGS_MODEL=inputs_v1`. Default stays legacy. | `src/nba_gm_data/ratings_model.py`, hooks in `save.py` and `sim.py`, `tests/test_ratings_model.py` |

## Overnight plan (2026-11-17, user asleep; nothing may require the user)

- **Rule learned:** never click Fanspo "Export CSV/Download" buttons. They open macOS save dialogs. Save only via page-generated Blob downloads, which land silently in ~/Downloads.
- Leaderboards: Values pass, then Season Percentile, Season Grade, Season Value+ and Database Value+ (pane tab-1, chained).
- Auto-importer (7 h background loop): moves `bbi_leaderboard_*.json` from ~/Downloads, archives, imports. Log: `data/research/bbi/captures/leaderboard/auto_import.log`.
- Subagent: remaining Fanspo BBI tables via DOM read (pane tab "seed").
- Subagent: GUI Q1 small fixes (code and tests only; visual check by Claude later).
- Claude: S1-E front office on the new scale; rebuild inputs with BBI evidence once Values are imported, then rerun scorecards.
- 06:15 Leaderboard stall fixed: the Run Query click sometimes re-ran the previous query. The script now waits for Shiny to register the new metrics, matches every metric in the header, and re-clicks Run once a minute if nothing renders. Restarted at Values chunk 15.
- BBI overlay v2 (`bbi_evidence.py`): it now also covers single-number tendencies and unmeasured physical grades, kept on the estimator's own scale (BBI re-ranks; units and spread stay). Evidence weight is scaled by the strongest metric available, so weak-proxy inputs move less. `build_player_inputs.py` applies the overlay by default (`--no-bbi` to skip). Multi-way tendencies (shot-region mix, action mix, catch/pull-up mix) are not overlaid yet. The current estimates look wrong for some players (Gobert shows a 34% pull-up share, Jokić a 19% post share), so this is the next ratings item.
- Subagents (sonnet), started 06:25: **Q2** draft falling-prospect diagnosis, read-only, report to `docs/agents/tasks/q2-draft-falling-prospects.md`; **D06** prospect injury history on the draft board (app.js/css/app_actions payload only).
- 06:30 Auto-importer fix: in this shell `find` is replaced by a variant that rejects `-mmin +0.5`, so the first loop silently matched nothing. Restarted with `/usr/bin/find -mmin +1`.
- Ratings converter: legacy placeholder traits (exactly 50.0 with no source data, ~1,090 cells) are excluded from the adapter's target distribution. They formed a fake plateau that tied Jokić, Cade and Wembanyama on shooting range. See `ratings_model.is_placeholder_trait`.
- **D06 done** (subagent; reviewed): draft boards show prospect injury history, current injury (only while not yet healed by the save date) and projected risk, from the engine's existing generated medical profiles. Real/imported prospects show "—" (none invented). Visual check pending.
- **S1-E finding:** the trade/contract market reads its own feature-based on-court value, not the summary OVR. See `docs/agents/tasks/s1e-quality-sources-2026-11-17.md` (companion to Codex's inventory).
- **Experiment (skill-only view):** giving the summary OVR/OFF/DEF traits derived from skill and physical inputs only (no tendency/volume terms) moves Jokić OFF from #72 to #20, SGA to #1 overall and Wembanyama DEF from #22 to #7. It does not fix Gobert (#165), Sabonis (#148), Tatum (#54) or Giannis (#48). For reference, the legacy hand-calibrated top 5 is Wembanyama, SGA, Cade, Edwards, Kawhi. Script: `output/overnight-2026-11-17/quality_view_experiment.py`. Rerun after the BBI rebuild before deciding.
- **U06 done** (Claude): draft-prospect card rating bars mark the average for the prospect's position (multi-position prospects get the mean of the listed positions; positions with fewer than 20 players, or unknown, fall back to a labeled league average). Previously prospect cards drew a made-up 50 "league average"; now no marker appears without real data. The D06 prospects card shows the injury marker only when notable.
- **Q2 done** (subagent report `docs/agents/tasks/q2-draft-falling-prospects.md`, reviewed). Findings: the board "rank" is creation order, not a rating; AI picks stack three layers of randomness; AI draft trades don't let the buyer re-choose; the hidden-upside potential was shown to the user.
  - **Fixed tonight:** prospect cards and boards now show the same public potential and ceiling the AI drafts on, never the hidden upside tail (rule 4). Test: `tests/test_prospect_public_potential.py`.
  - **Fixed tonight (crash):** a sim day could crash in AI trades ("Every draft condition must refer to one selected pick") when a three-team offer carried a pick-swap condition. `prepare_ai_trade_candidate` now restores the swapped pick, like the apply path. Test: `tests/test_multi_team_pick_swap_revalidation.py`. Verified: the crashed seed-103 season now runs through the Feb 15 trade deadline (99 transactions).
  - **For the user to decide:** (a) make the public rank a real public grade; (b) how much draft-night randomness to keep (target, e.g., consensus top 3 fall past pick 10 under 5%); (c) let a team that trades up re-choose the prospect (changes seeded draft results).
- **BBI importer:** blank header text (background-tab redraw) broke one file; the importer now rebuilds names only when the row layout matches exactly; the capture script reads titles from the table settings.
- **Fanspo DOM capture (subagent) stopped 06:55.** Saved under `data/research/bbi/captures/fanspo_tools/` (manifest.jsonl): Value Trends 2025-26 (10/30/50-day and season windows, 582 players); Shooting Talent daily projections with 50/80/95% ranges for 908 players (list positions 0 to ~1,283 of 1,930; the rest not captured). Not captured: Player Trends (one player at a time, ~582×3), shot maps, lineups and play-by-play tools. Page timers stall unless its tab is the active one.
- **Scoring efficiency 2026-11-17 (user: must fix):** the sim scored ~116 per 100 possessions (NBA 112.75) at low pace, with TS .60-.61. Three causes, all in the box-score split (game scores were right on average): (1) `offense.shooting_line` added a made free throw with no attempt whenever the point remainder was odd (league FT% 90%; now flips one FT outcome using the shooter's FT%, no extra RNG draw, scores unchanged); (2) `box_variation` only ever removed two-point misses (one-sided cap at possessions + 8), never added them, pushing 2P% to ~59% vs players' own ~54% (now moves misses 70% of the way to the game's real possessions in both directions, `MISS_FILL`; team FG% spread ~.05 like the NBA); (3) base pace/efficiency 99.5/110.5 -> 101.3/107.9 (`sim.BASE_POSSESSIONS`/`BASE_OFF_RATING`, changes seeded scores). Also `PLAYER_REBOUND_SHARE` 0.92 (team rebounds credited to no player). Real-minutes replay, new ratings: pace 102.6, 112.2/100, TS .580, 115.5 ppg, 18/18 in band; old ratings 18/18. Player errors per 36: points 2.64 -> 2.61, TS bias +.021 -> -.004, rebounds 1.19 -> 1.18. Odds (new ratings, 100 runs): Brier 0.1957 -> 0.1955, log loss 0.5797 -> 0.5791, totals error 5.57 -> 5.49, spread error 5.09 -> 5.22. Healthy-roster sandbox still scores higher (~115/100), as expected without absences.
- **Save size (user decision 2026-11-18: box scores are not kept past their season):** `history_store.SEASONS_KEPT` keeps box scores and team game logs for the current season only and player game logs for the current + previous season (player card's last-30 chart). Everything else is kept (season totals, awards, standings, score summaries, transactions, development). Removals are staged as tombstones at the rollover save (invisible to the previous manifest, so an interrupted save stays recoverable) and physically deleted + VACUUMed on the next save. Measured on the 10-season 2036 career: history file 623 -> 215 MB (whole save ~255 MB, under the 512 MB export cap); a normal save 18 s -> 7.5 s; the two rollover saves take ~25-29 s once a season. Codex's SAV report: `docs/agents/tasks/sav-save-size.md` (still open: duplicate transaction versions ~58 MB; full previous-backup copy on every save).
- **Decline watch 2026-11-17 (user's pick):** veterans (27+) with no growth runway show ↓ the expected average change of their hidden ratings over the next 12 months if healthy, split athletic vs skill in the tooltip (dev card slot and player card ring). `development_outlook.expected_rating_changes` runs the season's own `health.monthly_trait_delta` (new `expected=True` drops only the monthly noise) with the same staff, focus and ceiling inputs. Validated on a simulated season: 115 players 30+, projected vs actual 4-month change r = 0.99, both −0.20. Shown in hidden-rating terms, not OVR: the new-ratings value fit gives athletic ratings ~0 weight (monotone fit), so an OVR readout would miss most aging; the trade AI applies age through its own age curve. 15 veterans take ~66 ms.
  - **Value fit made monotone:** every developable rating's weight ≥ 0, so better skills never lower value (body measurements and involvement can take either sign). Out-of-fold r 0.86 (was 0.88 unconstrained). Top 12: Jokić, Wembanyama, SGA, Luka, Kawhi, Giannis, LeBron, Cade, Embiid, Mitchell, Tatum, Porziņģis; Gobert #73 (DEF #3). Trade-off: defense-poor scorers fall (Trae #268, Brunson #163), because "shooters defend worse" can no longer enter as a negative weight.
- **M03 labels applied 2026-11-17 (user chose "development labels"):** player "Upside / OVR remaining" → **Growth runway** ("x / 5", tooltip: room to improve from age, role and level, not a rating prediction); prospect ring → **Prospect upside** (lock kept); development card "Net growth" → **Rating change** (tooltip: real engine change, Oct–Jun and latest month); chart subtitle "Overall change this season (Oct-Jun)"; trade bar "Age + upside" → **Age and growth value**; Player Finder and trade ledger column → **Runway**; draft table Pot/Now tooltips (scouted, not hidden ratings). Two JS tests updated for the renamed ledger text. Open user questions from the audit: a veteran "decline watch" number? Show a scouted potential for your own players?
- **M03 audit done** (subagent, `docs/agents/tasks/m03-development-definitions.md`): three different "growth/upside" ideas share words. Player "Upside remaining" is a 0–5 market index (0 for everyone 27+), not potential; prospect "Upside" uses a different formula; "potential" means three things. Proposed label set (labels and tooltips only) awaits the user.
  - **Fixed tonight (rule 4):** the development "Net growth" chart and the Season/Month bars showed a capped estimate (sum of changes × 0.75, ±0.65/month) running ~4× the real rating change. They now show the engine's real OVR path (today's ratings walked back through the saved monthly changes, the same OVR formula the card uses, minutes held fixed). The chart axis fits the data (±1/2/3/5…), and the bars use a ±2 season / ±0.5 month scale. Checked on a mid-season save: young riser +0.6 real vs +2.6 old estimate.
- **Pre-BBI baselines (inputs mode, after placeholder fix):** real-stat scorecard 13/18 league metrics in band; per-36 mean abs errors: points 3.107, FGA 2.323, 3PA 0.504, FTA 1.667, REB 1.240, AST 1.077, TOV 0.615, STL 0.655, BLK 0.628, TS .036. Odds: Brier 0.2038, log loss 0.6007, spread error 5.46, total error 6.12 (market 0.1962 / 0.574). Files in `output/overnight-2026-11-17/`.
- **BBI Values pass complete (07:30):** all 664 metrics × 6,804 player-seasons imported. The last six files came through the app as hidden temp files (`~/Downloads/.Q6L2SF6YDW.com.anthropic.claudefordesktop.*`); recovered from the page's memory as one combined file. The optional derived-display passes were stopped to avoid stuck downloads or save prompts.
- **Ratings rebuild with BBI (inputs mode only, opt-in):** ~37,000 cells changed for 567 players. Fixes made during the rebuild:
  - turnover counts per 75 are now divided by touches (`per` in the mapping, as the mapping notes required);
  - pass execution is not overlaid (every available signal measures risk and volume, and ranked Trae, CP3 and Harden below Gobert);
  - attack recognition drops half-court shot quality (location-driven);
  - screen recognition is weak;
  - adapter `scheme_iq` is rebalanced to half offensive / half defensive, matching the legacy definition (BBallIQ + passer rating + CraftedDPM).
  - **Real-stat scorecard:** 14/18 in band (was 13). Points 2.92 (3.11), FGA 2.21 (2.32), FTA 1.61 (1.67), TS .034 (.036), TOV 0.61 (0.62) better; **assists 1.26 (1.08) worse**; rebounds 1.30 (1.24) and steals 0.68 (0.66) slightly worse.
  - **Betting-odds scorecard: Brier 0.1957 vs market 0.1962 (sim now edges the market)**, log loss 0.5795 (market 0.574), spread error 5.08 (was 5.46), total error 6.11 (6.12). Pre-BBI inputs: 0.2038; legacy traits: 0.2144.
  - **Assists cause:** `sim.assist_rate_for_player` / `assist_rate_from_features` have steep hand-set thresholds tuned to legacy values (big-man cap unless passing ≥ 88, a Luka-specific line). Jokić's passing feature went 89.9 → 86.4, so he hit the cap (rate 0.27 → 0.175). Engine retune needed (rule 1: tune the engine, not the ratings).
  - **Sniff test:** top 12 now SGA, Cade, D. White, J. Williams, Haliburton, Luka, Reaves, Curry, Mitchell, Jokić, Murray, Kawhi. **Big men badly underrated:** Gobert #324 overall, Sabonis #212, Giannis #52. Cause: summary DEF = 60% perimeter activity (effort, lateral, screen navigation) + 40% rim, and OVR gives no weight to rebounding. Legacy hand-set ratings inflated bigs' perimeter traits to compensate. Formula decision for the user.
- **Engine bug fixed (both rating modes): box-score leftovers always went to the same players.** `sim.redistribute_integer_stat` (also used by `box_variation.py`) rescales raw steals, blocks, assists and rebounds to team totals and handed leftover units out in a fixed reversed player-id order. Most players tie, so the same players won every tie all season, and 17 players with ids sorting early (first names A–D) simulated 0 steals and ~0 blocks. The tie-break is now a per-game hash (deterministic, no RNG consumed). Real-stat errors: inputs mode steals 0.68 → 0.27, blocks 0.63 → 0.33; legacy steals 0.65 → 0.30, blocks 0.59 → 0.28. Test: `tests/test_box_stat_tiebreak.py`. Seeded box scores change (intended); scores and minutes do not.
- **Speed check (rule 10):** one headless month (Feb 15 → Mar 15, legacy save, AI on) takes ~31.5 s, the same before and after tonight's changes (31.4 s with start-of-night engine files). It's over the 10–20 s budget for reasons that predate tonight. Profile: `canonical_with_save` (a full league rebuild, ~0.37 s) runs ~3× per sim day = 43% of the month. Daily callers: `advance_lifecycle_to`, `ensure_roster_minimums` (rebuilds just to count roster sizes), and `process_inseason_released_free_agent_signings`. Player summaries take 17% and deep copies ~20%. Added an exact early exit for the signing check (identical month result verified). **Then reused the day's lifecycle state** for the roster-minimum count and for the in-season signing check (same rule the code already uses for `ai_canonical`: no roster, contract or free-agent change and no new development): **mid-season month 31.5 → 20.6 s**, early-season month 59.6 → 54.8 s. Results identical apart from snapshot ids (verified on both). Remaining big cost: the AI-phase rebuild and `role_active` rebuild in `advance_save_day`.
- **Adapter `passing_reads` now includes passing volume** (T01 pass share 0.15 + T08 involvement 0.15), matching the legacy definition (passer rating + assists per 75 + box creation + IQ). Assists per-36 error 1.24 → 1.19; odds Brier 0.1961 (was 0.1957, within noise), log loss 0.5795 (same), spread error 5.00 (5.08).
- **2026-11-17 (user decisions: "fit to real impact" + "read playmaking inputs"):**
  - **Assists:** in inputs mode, assist allocation reads the playmaking inputs (`sim.playmaking_assists_per36`): pass recognition, T01 pass share, T08 involvement. Log-linear fit to real 2025-26 assists, out-of-fold r = 0.87 (trait formula 0.62). Legacy mode keeps its formula with the step cutoffs smoothed into ramps that end at the old cutoffs (old qualifiers unchanged). Assists per-36 error: inputs 1.19 → 0.88, legacy 1.107 → 1.096. Box only. Mapping: T01 pass now uses Passing Creation Volume (primary) and Potential Assists per 75 (supporting), with Drive Passout Rate weak. Known limit: T01's pass-share scale is narrow (inherited from the estimator), so Jokić stays at ~5 per 36 (real 11). Next: rebuild T01 from measured frequencies.
  - **Player value:** `impact_value.py` + `scripts/fit_impact_value.py` → `data/canonical/impact_value_fit.json`. Weighted ridge regression of BBI multi-year O-/D-LEBRON on the 15 hidden ratings, height and the engine's shooting profile (3PA/36, 3P%, 2P%, FT%). Out-of-fold r: offense 0.82, defense 0.84, overall 0.80 (old summary 0.64). In inputs mode, the summary overall/offense/defense and the trade market's on-court value are the fitted values placed on the EXISTING scales by league rank, so every cutoff keeps its meaning. Card top 10: Jokić, SGA, Wembanyama, Luka, Kawhi, LeBron, D. White, Giannis, Cade, J. Williams. Gobert 46th overall, #3 defense. Market: Giannis #56 → #17, Jokić #15 → #7. Known misses (inputs understate their offense): Brunson #283, Trae #344, Sabonis #168. Jokić's market value is held back by the superstar floor's playoff gate (playoff_translation). The game sim never reads these values; odds Brier 0.1965 / log loss 0.581 (market 0.1962 / 0.574).
- **2026-11-17 (user: "fix inputs"):**
  - **Action mix (T01) now measured:** shoot / drive / shot-creating pass / other pass per touch from BBI (FGA, drives, potential assists, passes = potential assists ÷ potential assists per 100 passes, touches), season-weighted and blended with the estimate by evidence weight; post share keeps its estimate (`bbi_evidence.apply_measured_action_mix`). The old pass-share spread was 0.27–0.38 for everyone; now Gobert 0.09, Jokić 0.18, Trae 0.25, and SGA's drive share 0.26 vs Jokić 0.05.
  - **Involvement (T08) evidence:** true usage is primary and touches supporting; on-ball-only action counts are weak (they made hub passers look uninvolved).
  - **BBI lookup cache:** `bbi_evidence` keeps `data/research/bbi/values_recent.json.gz` (rebuilt when normalized.json changes). Lookups dropped from 10+ min to under 1 s; the input build is back to ~2 min.
  - **Assist model refit:** out-of-fold r 0.91; sim assists per-36 error 0.85 (was 1.19 this morning). Jokić is still ~5.6 (real 11.1): the involvement input tops out ~0.62 for every star (an estimator scale ceiling). Next: set T08 from measured true usage on its own scale, as was done for T01.
  - **Odds after these input fixes:** Brier 0.1961 (market 0.1962), log loss 0.5813 (was 0.5808), spread error 5.10 (5.04), **total error 6.43 (was 6.08)**. Cause: measured T01 lowers a few derived traits (fewer drives for non-drivers), and simulated totals fell ~0.8 points per game in the replay, widening the existing under-prediction vs market totals. Real-stat scorecard unaffected (18/18). Follow-up: engine-side scoring-level calibration for the replay/game path (don't bend ratings).
  - **Value fit with input groups:** predictors now add mean technique grade per group (shooting, finishing, creation, post, off-ball, rebounding, defense, pass reading) and involvement. Out-of-fold r with real impact 0.87 (was 0.80). Card top 10: Jokić, Luka, Wembanyama, Kawhi, SGA, Giannis, LeBron, Curry, Davis, Embiid. Gobert #37 overall, #2 defense. Brunson #21 offense but #153 overall: BBI rates his defense near the bottom. Watch: Mitchell Robinson #19 looks high. Market top: LeBron (fixed), SGA, Luka, Jokić, D. White, Cade, Flagg, Edwards, Wembanyama.
- **Measured involvement + consistent tendency scales (2026-11-17, user: "measured involvement"):**
  - T08 involvement = BBI true usage (possessions finished plus created for teammates, as a share). Jokić 0.48, Luka 0.52, Trae 0.51, Murray 0.43, Gobert 0.17. T08 is no longer rank-overlaid.
  - **Bug fixed while doing it:** the measured T01 mix covered only players with BBI data. Unmeasured veterans (127) and every generated rookie kept the estimator's scale (pass share ~0.30, above Trae's measured 0.25), so the new assist model gave drafted rookies the 14-per-36 cap. Now every estimate is first placed on the measured scale by rank (`bbi_evidence.apply_measured_tendencies` → `data/canonical/tendency_scale_map.json`; `ratings_model._install_generated_players` applies the same map to rookies), then measurements blend in. Rookie assists are now 3.8–7.6 per 36. Rank-based hidden ratings are unaffected.
  - **Refits:** assist model out-of-fold r 0.91 (MAE 0.66); value fit r 0.88. Replay-mode scorecard 18/18; per-36 errors: assists 0.70, points 2.64, rebounds 1.19. Jokić 6.4 assists per 36 (real 11.1; touch volume is not an input).
  - **Odds:** Brier 0.1957 (market 0.1962), log loss 0.5797, spread error 5.09, total error 5.57.
  - **Known:** prospect-path involvement estimates run high (Flagg and Bailey map to ~0.55, star level). This is a prospect estimator issue; hidden ratings only use ranks.
- **Scoring level (2026-11-17, user: "fix scoring"):** the base constants were tuned on fully healthy projected rotations. With real availability, new-ratings mode scored 113.2 points per team in the season replay (NBA 115.6), and a real new-ratings save averaged 113.7 through Dec 15. Added `sim.INPUTS_OFFENSE_CALIBRATION` = +2.45 points per 100 possessions on the base offensive rating (new-ratings mode only; both teams, so margins are unchanged).
  - **Results:** replay 115.5; in-save 116.2 (387 games); healthy check 118.2.
  - **Odds:** total error 6.43 → **5.46** (best ever; legacy 6.45); Brier 0.1962 (= market); log loss 0.5811; spread error 5.15.
  - **Real-stat scorecard:** now has `--mode replay-real-minutes` (real availability and minutes, like the odds test): **18/18**, points 115.4; per-36 errors points 2.74, assists 0.75, rebounds 1.19, TS .029. The default healthy mode shows 17/18 (TS .606 vs .581), since it never has injured players.
  - **Open:** sim pace is ~99.4 vs real 102.0, with efficiency correspondingly high; in band, but the composition could be recalibrated later. Legacy mode is unchanged (replay 114.9).
- **Draft fixes (2026-11-17, user picked "draft fixes first"; Claude's suggested choices):**
  - **Board rank = public grade:** `draft.apply_public_ranks` numbers every generated class (the stored 2027 class on load, 2028+ at generation) by `generated_bpa_grade`: public potential and ceiling, current, floor, volatility, medicals. Rookie-contract values follow the new slot.
  - **Top-3 protection works for every class:** `prospect_priority_tier` comes from rank (1: top 3, 2: top 6), not three hard-coded 2026 names. The generated path got the same protection.
  - **Less stacked randomness:** a team's read of a prospect is stable across picks (it was re-rolled per pick) and about half as large; the final draw's swing is ±18% (was ±45% after pick 5); early-pick temperatures are 3.0 / 5.5 (was 4.8 / 8.5). Team scouting noise is unchanged.
  - **Draft-day trades:** `play.rechoose_pending_draft_pick`. A team that acquires a not-yet-made pick chooses from the unpicked prospects with its own board; the chosen prospect swaps into the slot (same swap as user picks).
  - **Pick explanations** compare against prospects still available ("bpa_gap_too_large" now marks real reaches, mostly from pick 9 on).
  - **Measured over 60 drafts each:** consensus top-3 past pick 10: 0% (2027) / 0% (2028+). Top-5 past 10: 3.3% / 6.3% (was ~27%). #1 goes first 77% / 53%, always top 3. Script: `output/draft-fixes/measure_falls.py`. Tests: `tests/test_draft_fixes.py`. The parity test now drafts the rank-1 prospect.
- **Assists analysis (for daytime):** the sim's assist formula (`sim.assist_rate_from_features` / `assist_rate_for_player`) has two cliffs that dominate star assists. (1) Big-man cap at 0.175/min unless passing ≥ 88: Jokić's new passing is 86.4 → held to 6.3/36 (real 11.1). (2) A +0.095 bonus when passing ≥ 80, usage ≥ 86 and creation ≥ 78: Murray and Derrick White cross it → 10–12/36 (real 7.3/5.7). Also a Luka-specific line and a Curry off-ball multiplier. Fitted linear or log models on the 15-trait features reach r ≈ 0.79–0.81 but still can't separate Jokić or Giddey (the features are too coarse). Proposal: smooth the cliffs, and in inputs mode let assists read the playmaking inputs directly.
- **Rebound allocation uses height:** `sim.rebound_rate_per_minute`, a 4-parameter fit to real 2025-26 rebounds per 36 (offensive-rebounding feature + height). Correlation with real 0.74 → 0.82. Per-36 rebound error: inputs 1.35 → 1.21, legacy 1.42 → 1.20. Box only (team totals still rescaled); scores unchanged. Caveat: evaluated on the fitting players (150; 4 parameters).
- **Personal fouls calibrated:** league rate 2.7 → 2.95 per 36 (2025-26 NBA 19.4 per 100 possessions at the sim's pace). Separate RNG, box column only. **Inputs mode now 18/18 league metrics in band**; legacy 17/18 (only TS% .607 vs .581 is out).
- **Engine fix: free-throw excess in box scores.** `offense.shooting_line` used round(points×rate + U(0,1.8)), adding ~0.9 FTA to every player line (34 FTA/100 vs NBA 23). It now uses unbiased rounding with the same number of RNG draws, so **game scores are identical** (verified on 40 seeded games; points per game unchanged at 116.062). League metrics in band: inputs mode 14 → **17/18**, legacy 12 → **16/18**. FT rate .263 vs .264, FGA/100 85.8 vs 86.9. Per-36 FTA error 1.61 → 1.19, 3PA 0.52 → 0.44. Remaining miss: personal fouls/100 (17.8 vs 19.4). Test: `tests/test_free_throw_split.py`.
- **M01 done 2026-11-17 (user chose the rust marker):** players back from injury show a small red ↓ with the exact current in-game penalty (`sim.rust_penalty_points`: rust × 0.08, capped at 4, the same function the sim uses). The tooltip says it fades in about N days. Shown wherever the injury cross appears: the shared name helper (finder, roster and dashboard rows, next opponent, trade ledger, FA table), the Minutes + Availability table, and the player card's availability note ("Rusty after injury · in-game ratings −X · fades in about N days"). Payloads: `health_label` / `player_health_label` add rust, rust_penalty and rust_days for active players. Visual check passed with a sample marker; no player in the user's save is rusty at Nov 15.
- **M01 finding (injury rating display):** injuries do NOT lower any stored or displayed rating today. OVR/OFF/DEF everywhere are full-health values. The only temporary effect is an in-game penalty from rust (after a return) and fatigue, applied to per-game features inside the sim (`sim.health_adjusted_player_features`). An "injury-adjusted OVR" would therefore need a new, defined derivation of that penalty. **User decision for the morning:** show a small red "rust" marker (games or percentage penalty) on returning players, versus deriving an effective OVR.

## Decided (2026-11-17)

- **Value fit stays monotone** (user, 2026-11-17): improving any skill rating can never lower a player's overall or trade value. Accepted trade-off: defense-poor high scorers rank lower (Trae, Brunson), and the out-of-fold fit is r 0.86 instead of 0.88.

## Decided (2026-11-16)

- Two-stage plan approved: Stage 1 puts the new ratings into the current engine, with a new player card and new trade/contract valuations. Stage 2 is the new engine.
- Commit and push approved.
- **Basketball Index subscribed 2026-11-16** ($5/month, auto-renews **Dec 16, 2026**; whether to cancel is the user's decision). The capture window runs through Dec 16. Per BBI's order email, Player Profiles have full access at bball-index.com/player-profiles/ during their site transition; other premium tools are on the site's normal pages.

## Waiting on the user

1. Turn off iCloud "Optimize Mac Storage", or move the repo out of iCloud-synced Documents. Otherwise files get offloaded again when the disk fills.

## Stage 1 queue (see `STAGE1_DESIGN.md`)

| ID | Task | Owner |
|---|---|---|
| E2 / S1-A | Input estimator: all 691 players plus prospects | Codex (**accepted**) |
| S1-B | Adapter: inputs to the 15 hidden ratings | Claude |
| S1-C | Development writes to inputs | Claude |
| S1-D | New player card (four layers) plus derived OVR/OFF/DEF without clipping; rewrite rating-pin tests | Claude. **Card done**: mockup approved by user; live in inputs-model saves (`player_profile.py`, `gui/player-card-layers.css`). New saves via `new-save --ratings-model inputs_v1`. Open: rating-pin test rewrite. (Injured players now show 'Out (injured) · expected back DATE'.) |
| S1-E | Front-office AI (trades, contracts, FA, draft) reads new ratings | Claude, Codex for bounded parts |
| S1-F | Prospects generated with inputs | Claude: plumbing **done**. A new-ratings save carried through the 2027 draft and rollover gives all 60 rookies 94 inputs, with 0 card/engine mismatches. Values are wrong (top picks OVR 3–31) because the prospect path ignores the generator's definition; fix queued as **E2c** for Codex. |
| BBI | Basketball Index capture plan and importer | Codex (**accepted**). Subscribed 2026-11-16; capture under way (BBI-CAP). |
| T2 | **Mostly done 2026-11-17 (subagent, reviewed):** `tests/fixtures/trade_year_seed17.nbagm.zip` (3.8 MB, CLE seed 17 save at 2027-02-03) and `context_builds_seed17.json.xz` (1.1 MB) restore the trade-year and context-build tests (28 run, 1 skip). Still missing: `mature2036.json` (a 10-season build, ~2 h; generator `scripts/prepare_roster_forecast_fixture.py` needs a new source). The balance/offense career-29 paths were never fixtures. Note: several tests need `PYTHONPATH=src:scripts`. `scripts/ten_season_soak.py` is stale (it dies at the draft-lottery phase). Original task: regenerate test fixtures lost in the 2026-11-16 cleanup into `tests/fixtures/` (tracked, gzipped): `pick-investment-2026-10-28/stable17/saves/trade_year.json`, `roster-forecast-pass/fixtures/mature2036.json`, `balance/career-29/run.json`, `offense-season/career-29/run.json`, `context-demand-pass/attribution-before/context-builds.json` | Codex or subagent |
| T3 | Investigate likely real front-office bugs (below) | Claude / Codex |
| SPD | Fewer league rebuilds per sim day; byte-identical results (save.py only) | **accepted 2026-11-17** (Claude re-verified: mid-season month 30.0 → 18.5 s, identical save; 329 core tests). Codex review notes: All 3 month comparisons exact; medians 22.8→16.9 s / 63.1→58.4 s / 88.8→60.3 s; 18 focused + 329 core tests pass (3 skips). Full diagnostic non-green: 57 failures / 5 errors. Report: `docs/agents/tasks/spd-sim-speed.md`. Uncommitted. |
| T2b | Fix 10-season driver; rebuild the 2036 fixture (scripts + tests/fixtures) | done (Codex + Claude, committed 2026-11-17): tests/fixtures/mature2036_seed17.json.xz, 867 KB, 595 generated players; the 2036 roster-forecast test runs again |
| TST | Full-suite stale-test triage (tests/ only) | done: 1,746 tests green, 56 quarantined with reasons (committed) |

## Full-suite leftovers after T1 (2026-11-16)

- **Rating pins (rewrite in S1-D):** `test_imported_rookie_ratings` (6), `test_player_tuning` (2), `test_roster_alignment` (3), `test_rotation_profile_calibration` (2), `test_long_term_health` (1), `test_contract_import_separation` (1).
- **T3 diagnosis (2026-11-16, subagent; real-save evidence):**
  - Stale tests, not bugs:
    - AI trades: 8 trades Oct 20–Dec 31 in a real save. The trade calendar is now seeded, so tests need a forced slot.
    - Roster cutdown: now goes through waivers; all 30 teams reach 14–15 players.
    - Expiring players through the draft: the test picks a player who was already cut.
    - FA day market: new `screening` key.
    - Future pick values: SAC owns no second-round picks.
    - Staff fire/interim: one change per season is now enforced.
  - Unclear: `test_staff_queue_keeps_live_strategy`, which may be a budget-guard issue.
  - **REAL BUG, front-office valuation:**
    - `player_value` clips at 99, so a dozen players tie: Flagg, Ausar Thompson, Clingan and Castle sit level with SGA and Wembanyama.
    - Giannis 85.1 (rank 85) and Luka 82.8 (rank 107) fall below Herro 91.3.
    - Causes: the superstar floor needs on_court >= 79 (`transactions.py:2849-2878`), which Giannis (78.6) and Luka (72.5) miss; and contract surplus (+34 cap, `transactions.py:354-360`) lifts cheap players above stars.
    - **Partly fixed 2026-11-16** (formula side): surplus scaled by player quality, soft ceilings instead of hard caps (top ties 15 to 1), stronger superstar-floor age discount.
    - Market top 5 is now Wembanyama, Jaren Jackson Jr., Jokić, SGA, then LeBron (GOAT exception, **kept by user decision 2026-11-16**: never traded in regular sims).
    - Remaining Giannis/Luka underrating is on the ratings side: on-court values 78.6 and 72.5. That is what the fantasy-draft test failure reflects.
    - Tool: `scripts/market_sanity_report.py`.
  - **Inputs mode is NOT ready for the front office:** stars are compressed. On-court values are Jokić 73.9, Wembanyama 72.4, Giannis 68.8, giving market ranks #28/#40/#66. Prior-heavy technique inputs average away elite distinctions. Next: estimator follow-up for elite players (E2b) and Basketball Index data.
- **Previously suspected real bugs, superseded by the T3 diagnosis above:**
  - AI trades applied count is 0, with `not_applied_stale_assets`.
  - AI roster cutdown frees nobody.
  - Expiring players are dropped during the draft.
  - Giannis trade value 86.87 sits below Herro's 92.43.
  - Luka goes 45th in the fantasy draft.
  - Staff fire/interim and staff queue events.
  - Future pick value and recommendations.
  - Free-agency day market; team strategy phase pressure.
- **Stale (fix with current data):** the Curry extension tests (his contract now runs through 2028-29) and several others listed in the T1 report.
- **Data gap:** 11 rostered players have no height (DeVries, Fricks, Sellers, Agee, Cooper, Dix, Tilly, Holifield, Nkrumah, Burnett, Wague).
- **Pre-existing JS failure:** `tests/player_pages.test.cjs` fails all 5 tests on HEAD too (a `document` reference in its function slice). Not in the core suite.
- **Borderline:** `test_box_variation` FG% shift 0.0264 vs a 0.025 limit. A possible timing flake in the atomic-save test.

## Parked GUI queue (prompts in `CODEX_QUEUE.md`)

| ID | Task | Suggested owner | Depends on |
|---|---|---|---|
| Q1 | Small GUI behavior fixes: Next Opponent after W/L, S-prefix sim shortcut, lottery grid order (U03/U04/U05) | Codex | none |
| Q2 | Draft "falling prospect" diagnosis plus consensus-vs-scouting board design (D04/D05), read-only report | Codex | none |
| Q3 | Shared table system rollout (T01–T05) across the five named tables | Claude | user approves one sample table |
| Q4 | Playoff Stats table plus playoff auto-open layout (PO01/PO02) | Claude or Codex | Q3 |
| Q5 | Injury-adjusted rating deltas in the GUI (M01) | Claude | none |
| Q6 | Apply approved rating corrections (R02–R06) to game data | Claude plus user review | E2 |

## Oct 29 backlog status (audited 2026-11-16, code read only, no tests)

- **Partial:** T01, T02, T04, T05 (sorting and hover exist only on some tables) and M03.
- **Research done, not applied:** R01–R06.
- **Not started or unverified:** U01–U06, M01, M02, M04, M05, PO01–PO03, D01–D06, FA01, FA02, B01–B03.

## Calibration baseline: current (old) engine vs real 2025-26 NBA

Run: `PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230` (about 14 s).

- **12 of 18** league metrics are within band.
- **Too many free throws:** FT rate .429 vs .264.
- **Too few field-goal attempts:** 80 vs 87 per 100 possessions.
- **Offense slightly hot:** true shooting .617 vs .581; offensive rating 117.5 vs 112.7.
- Pace, three-point rate, eFG, offensive rebounding, assists, steals and blocks are in band.

The new engine must beat this.

## Test suite health (2026-11-16)

The full suite (`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`) has **1,599 tests: 259 fail** (247 failures, 12 errors) and the run takes **37 minutes**. Codex only ran the ~367 engine-focused tests.

- **By file:** `test_roster_forecast_performance` 179, `test_foundation` 49, smaller clusters elsewhere.
- **Import errors:** two files import helpers from `scripts/` that aren't on the path.
- **Triage (static, not yet rerun):** mostly **outdated tests**, not broken code.
  - 179 failures: one frozen reference fixture (`tests/fixtures/*_stage_b.py`, Oct 29) that predates later strategy and model changes. Refreshing it should clear all 179.
  - About 40 failures: `test_foundation` pins players and teams changed by the Oct 13 roster refresh (Seth Curry, Kuminga, Saunders).
  - About 18 failures: pinned rating values from the ratings refresh. **Flag:** top rookie OVRs dropped from about 79 to 64. Verify that was intended before loosening those tests.
  - About 8 failures: GUI tests checking for old function names.
  - 2 import errors: need `PYTHONPATH=src:scripts`.
  - 2 failures: a new `staff_season_changes` save field.
  - Unclear singles: `test_api_security` stream (400 vs 200), `test_completed_market_review`, `test_fantasy_draft`.
- **Before Stage 1 changes ratings:** get the suite green, or explicitly quarantined, plus a fast core subset.

## Stage 1 scorecard: new inputs vs old traits (real-stats targets, 1,230 games, seed 1)

Average error per 36 minutes across 150 high-minute players:

| | Old traits | New inputs (accepted E2 + adapter v2) |
|---|---|---|
| League metrics in band | 12/18 | **13/18** |
| 3PA | 0.524 | **0.504** |
| True shooting % | 0.040 | **0.032** |
| Rebounds | 1.346 | **1.286** |
| Assists | 1.114 | **1.018** |
| Points | **2.887** | 3.187 |
| FGA | **1.955** | 2.369 |
| FTA | **1.627** | 1.664 |
| Blocks | **0.586** | 0.656 |
| Steals | **0.647** | 0.659 |
| Turnovers | **0.589** | 0.607 |

Adapter v2 changes:
- Recombines skill with usage tendencies the way the legacy traits mixed them (three-point share, involvement, difficult-shot appetite).
- Re-anchors the offense model's observed-stat profiles to the input-derived baseline, so a model switch isn't read as instant development. That re-anchoring fixed 3PA, which went from 1.58 to 0.50.

Remaining gaps are scoring volume and blocks, driven mainly by the prior-heavy usage and defense inputs. Basketball Index is the next lever.

Rerun with:

```
NBA_GM_RATINGS_MODEL=inputs_v1 PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230
```

## Betting-odds scorecard, full season (2026-11-16)

`validate-season-probabilities --runs 100`: 1,018 games with market odds, replay with real minutes.

| | Old traits | New inputs | Market |
|---|---|---|---|
| Brier | 0.2144 | **0.2114** | 0.1962 |
| Log loss | 0.6324 | **0.6177** | 0.5740 |
| Spread error vs market | 6.63 | **5.25** | — |
| Total error vs market | 6.45 | **6.21** | — |

New inputs win on all four. Weakness: heavy favorites are under-confident. The heavy-away-favorite bucket is sim 0.167 against market 0.140 and actual 0.096, consistent with star compression (E2b).

## Speed baseline: old engine, headless CLI, fresh BOS save, seed 7 (2026-11-16)

| Advance | Time |
|---|---|
| New save | 5 s |
| Offseason start to Oct 31 | 37 s |
| November | 87 s |
| December | 82 s |

User target: **10–20 s per month** in the GUI. Game simulation is only about 2–3 s of a month (about 220 games at about 0.01 s each). The rest is AI front office (trade market), daily lifecycle and saving. Meeting the target is mostly a front-office speed project. It also leaves the new engine about 0.02 s per game, roughly 75x faster than its current per-possession cost.

## Done log

- 2026-11-16: Disk freed from 6.6 GB to 38 GB free. Deleted 100 old untracked `output/` run folders and the old beta build cache. Re-downloaded 7,602 iCloud-offloaded repo files.
- 2026-11-16: Checkpoint commit `5e40fef` pushed to `origin/codex/immersive-franchise-journey`.
  - Unpushed history was cleaned of 10-season soak saves over 100 MB that had blocked every push since September.
  - Pre-cleanup refs are kept locally as `backup/pre-history-cleanup-2026-11-16` and `backup/main-pre-history-cleanup-2026-11-16`.

- 2026-11-16: E3 calibration targets built: 18 league metrics, 386 players matched (100%). Old-engine baseline recorded above.

- 2026-11-16: Codex milestone 16 (compact recovery baseline) reviewed by Codex coordinator, 367 tests pass. Report: `docs/COMPACT_BASELINE_NATIVE_REPAIR_REVIEW_2026_11_16.md`.
- 2026-11-16: Claude handover. Added `AGENTS.md`, `CLAUDE.md`, this board, `CODEX_QUEUE.md`, and `output/` to `.gitignore`.
