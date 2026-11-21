# S2-REBOUND-FOULS (Stage 2, second piece): checkpoint

_Owner: Claude (Opus agent, worktree branch `worktree-agent-aad4424d8db3ab016`). Started 2026-11-21. Light job._

## Objective
Rebound kernel (S29-S32, reach/strength/jump, T12/T13, floor position, miss type) and foul/free-throw kernel (S24, T18,
S15, P08 vs S45, S37, T16, T14), each spot-checked per player and league-wide against real 2025-26 data and today's
engine, with held-out checks. Kernel conversion refits only; no ratings touched.

## Boundaries
May touch: `src/nba_gm_data/stage2/` (new modules), `scripts/research/` (new), `experimental_inputs.py` (small marked
additions only), tests, this file. Not sim.py/save.py/play.py/trait_adapter.py/ratings_model.py/trade/FA/offseason/gui.

## Resume state
- [x] Worktree links + inputs unzipped.
- [x] Survey: today's engine rebounds = per-player per-36 fit (box_rates.REBOUNDS_INPUTS) + team ORB% formula;
  fouls = per-36 fit (FOULS_INPUTS); FTA = per-point fit. Inputs include 2023-24..2025-26 BBI + Crafted 2025-26
  evidence (in sample). Held-out season: ESPN raw 2022-23 (OR, DR, PF, FTA, FGA per season).
- [ ] Rebound kernel + check.
- [ ] Foul kernel + check.
- [ ] Timing, tests, report, board.
