# ROOKIE-FIT: 2026 rookies' starting ratings from college evidence

_Claude Opus agent, worktree branch, started 2026-11-21. Status: in progress._

## Objective
Fit how a final college season translates to rookie-year NBA play (drafts 2008-2025, held-out check), then feed
that into the 2026 rookies' 94 inputs through the input estimator's evidence path (college numbers as evidence
entries, overall level from the fit). Rebuild the rookie entries with the builder. No hand edits (user report:
Yaxel Lendeborg under-rated).

## Boundaries
May touch: `input_estimator.py` rookie path, `scripts/build_player_inputs.py`, `real_prospects.py`,
2026 rookie entries in `data/canonical/player_inputs_2026_27.json(.gz)`, `scripts/research/`, tests, this file.
Must not touch: `ratings_model.py`, `health.py`, `development_outlook.py`, `talent.py`, `faces.py`, `gui/`,
`stage2/`, `sim.py`. Veterans' inputs must not change.

## Resume state
- Worktree data symlinked from the main checkout (venv, barttorvik raw, sqlite, injury evidence, bbi files,
  settlement output); inputs JSON unzipped.
- Baseline sniff (display overall) saved to `output/rookie-fit/sniff_before.json`.
- Next: research fit script `scripts/research/rookie_fit.py`.
