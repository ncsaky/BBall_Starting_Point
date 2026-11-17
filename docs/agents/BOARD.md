# Agent coordination board

Single source of truth for who is doing what. Rules are in `/AGENTS.md`. Coordinator: **Claude Code**. Worker: **Codex** (limited usage). Update your row when you start, finish, or get blocked.

_Last updated: 2026-11-16 by Claude Code (handover from Codex)._

## Where things stand (handover snapshot, 2026-11-16)

- **Playable game:** private friends beta. GUI files have **not changed since Oct 30**. Nearly all of the user's Oct 29 wishlist (`docs/MINIMUM_COMPLETION_BACKLOG_2026_10_29.md`) is open. See the status table below.
- **Player model (track B):** the 94-input model is approved, and its schema/persistence are implemented (Nov 12–13). Ratings evidence research is extensive (`docs/ratings-evidence-2026-10-29/`), but **no rating changes have been applied to game data**.
- **Experimental possession engine (track C):** Codex milestones 2–16 (Nov 13–16): interior defense, creation/passing, screens, pick-and-pop, pass recovery, then four performance passes on the recovery evaluator. All **default OFF**. The last coordinator recommendation was perimeter contests/closeouts next (not dispatched). Open problem: the recovery-enabled engine costs ~6–7x the old pass model per possession.
- **Git:** last commit 2026-09-30. ~2,000 files changed since, including almost all tests and scripts. Blocked on the Xcode license until the user runs `sudo xcodebuild -license accept`.

## Direction (user decision, 2026-11-16)

**Finish the new engine first.** The plan is in `docs/agents/ENGINE_ROADMAP.md`. GUI wishlist work is parked until the engine is live.

## In flight

| Task | Owner | Status | Files it may touch |
|---|---|---|---|
| E3 Calibration targets and comparison tool | Claude (subagent) | **done** (5/5 tests verified). Report: `docs/agents/tasks/e3-calibration-targets.md` | `data/calibration/*`, `src/nba_gm_data/calibration_targets.py`, `scripts/build_calibration_targets.py`, `scripts/calibration_report.py`, `tests/test_calibration_targets.py` |
| E2 League-wide input estimator | Codex | queued (paste from `CODEX_QUEUE.md`) | `src/nba_gm_data/input_estimator.py`, `scripts/build_player_inputs.py`, `data/canonical/player_inputs_2026_27.json`, `tests/test_input_estimator.py` |
| E1 Whole-game engine shell | Claude | waiting for user go-ahead on the roadmap | `src/nba_gm_data/game_engine.py` (new), engine-selection hook in `sim.py` |

## Decided (2026-11-16)

- Two-stage plan approved: Stage 1 puts the new ratings into the current engine, with a new player card and new trade/contract valuations. Stage 2 is the new engine.
- Commit and push approved.
- Basketball Index: buy when Claude says the importer is ready.

## Waiting on the user

1. Turn off iCloud "Optimize Mac Storage", or move the repo out of iCloud-synced Documents. Otherwise files get offloaded again when the disk fills.
2. Should GitHub's `main` be fast-forwarded to the pushed branch?

## Engine queue

| ID | Task | Owner | Week |
|---|---|---|---|
| E1 | Whole-game shell: clock, lineups, substitutions, possession starts, stand-in actions, plus-minus | Claude | 1 |
| E2 | Input estimator for all 691 players plus prospects | Codex | 1 |
| E3 | Real-NBA calibration targets and comparison report | Claude subagent | 1 |
| E4 | Fast live decision rule fitted to the exact decision model | Claude | 2 |
| E5 | Season calibration runs, then fix the biggest engine errors | Claude, with Codex for bounded fixes | 2–3 |
| E6 | Missing mechanics flagged by calibration (closeouts, rebounds, transition) | Codex for bounded pieces | 3 |
| E7 | Ratings display and AI valuation derived from the 94 inputs | Claude | 3 |
| E8 | Development and aging of inputs; prospects use the estimator | Claude or Codex | 3–4 |
| E9 | Five-season soak, default switch, beta rebuild | Claude | 4 |

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
