# S2-POSSESSION-LOOP (Stage 2, third piece): checkpoint

_Owner: Claude (Opus agent), branch `worktree-agent-aad27ad88396dd23e`. Started 2026-11-21._

## Objective
The first fast Stage 2 possession loop: whole games from `sim_game_with_context(..., engine="stage2")`, with
action choice (drive, jumper, post-up, roll/cut, putback, transition), turnovers/steals (plus a spot-check against real
2025-26 per-player data), a game clock (quarters, possession length, team fouls, bonus), the shooting fixes
(per-family conversion, hook shots, floaters), and the same box-score outputs as today's engine, so both scorecards
run next to today's engine. Speed target ~0.2-0.4 ms per possession (~0.02-0.04 s per game). Default OFF.

## Boundaries
- May touch: `src/nba_gm_data/stage2/`, the `engine=` branch in `sim.py`, `scripts/calibration_report.py`, the
  probability-test engine flag, `scripts/research/`, new tests, this file, my board row.
- Must not touch: `trait_adapter.py`, `ratings_model.py`, `impact_value.py`, `health.py`, ratings data.
- Default engine scorecards must stay byte-identical. Never tune a rating to fit an outcome.
- Laptop: one heavy job at a time, `nice -n 10`, check `uptime` / `sysctl vm.swapusage` first (load > 20 or free swap
  < 2 GB: wait).

## Resume state
- [x] Worktree set up (symlinks, inputs gunzipped). Board row set to in progress.
- [x] `stage2/cards.py` (per-player numbers), `stage2/game.py` (possession loop, clock, rotation), engine hook.
- [x] Fits: usage, turnover share, hook family, dunk share, blocks (`stage2/loop_fit.py`); team-strength terms
  against market spreads (scratch `output/stage2/scratch/strength_fit.py`); score effects; usage power 1.3.
- [x] Calibration report stage2 sandbox 150 games: 18/18 in band. Replay spot-check script
  `scripts/research/s2_possession_loop_check.py` (600 games, both engines).
- [x] Tests: `tests/test_stage2_possession_loop.py` (new), `tests/test_stage2_seam.py` (stub tests replaced). Pass.
- [ ] Odds runs (20 runs, seeds 1001/2001, both engines): waiting for load < 20 and swap > 2 GB.
- [ ] Core tests, report, board row -> review, final commit.

Notes:
- Load at start was ~240 (other jobs); code work first.
- Today's engine (rating-ceiling report, same code for scores): odds seed 1001 Brier .2041 / log loss .5975; seed 2001
  .1972 / .5808.
