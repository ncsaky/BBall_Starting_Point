# S2-SEAM-SHOOTING (Stage 2, first piece)

_Owner: Claude (Opus agent), branch `worktree-agent-af77db31e56e7d239`. Started 2026-11-21. Light job (no season sims)._

## Objective
1. **Seam:** `engine=` choice in `sim_game_with_context` (default = today's engine, unchanged), threaded through `scripts/calibration_report.py --engine` and the betting test (`validate-season-probabilities --engine`). A `stage2` stub that calls today's engine, run end to end through both scorecards. Normal gameplay never selects it.
2. **League input bridge:** all 691 players in `data/canonical/player_inputs_2026_27.json` compiled into the typed profiles the physics pieces read (`InterpretedInputs`, `compile_offense`, `interior_defense.compile_profile`), one documented rule for prior cells, coverage report, cached.
3. **Shooting/finishing spot-check:** kernel make rates by shot type vs real 2025-26 (Basketball Index shooting tables) vs today's engine; league mix/efficiency vs the targets file; timing.

## Boundaries
May touch: `sim.py` (seam only), `scripts/calibration_report.py`, `cli.py` (flags), new `src/nba_gm_data/stage2/`, small marked additions to `experimental_inputs.py` and `offense_response.py`, new `scripts/research/` scripts, tests, this file. Not: `save.py`, `play.py`, trade/FA/offseason files, `gui/`.

## Resume state
- [x] Worktree data symlinks; board row added.
- [x] Before-hash of 40 seeded games (10 games x 2 modes x 2 seeds): `3a3695e2ed3b...` (scratch script).
- [ ] Seam + flags
- [ ] Bridge
- [ ] Spot-check
- [ ] Tests, report
