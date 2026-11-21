# STAR-INJURIES: fuller 2025-26 injury history and the history weight (2026-11-21)

Branch: `worktree-agent-afd1e8831e7215e1d`. Scratch: `output/star-injuries/` (git-ignored).

## Objective
Fold Codex's public 2025-26 stretches (`data/research/injury_history_2025_26.json`) into real players' injury history
through `scripts/build_injury_model.py`, re-check the history weights (real history, the game's own draws) with the
fuller history, and measure the top 30's games played and the other injury scorecards before and after.

## Boundaries
- May touch: `health.py`, `injury_model.py`, `scripts/build_injury_model.py`, `data/canonical/injury_model_v2.json`
  (via its script), the git-ignored `data/canonical/injury_player_evidence_v3.json` (never commit it; never overwrite
  v2, which another agent reads), research scripts, tests, this file.
- Not: `save.py`, `play.py`, `offseason_decisions.py`, `cap_ledger.py`, trade files, `gui/` (FA-REAL slice 3).

## Resume state
- Done: fold-in in the builder (`classify_public_stretches`, `public_history_entries`), evidence script
  `scripts/research/injury_history_foldin_check.py` (logs in `output/star-injuries/foldin_*.log`), engine split weights
  (real 0.75 by out-of-sample evidence; game's own draws to be set by the multiseason check), v3 built at 0.75.
- Baseline full seasons: `output/star-injuries/base_s17/29` (current main engine).
- Next: multiseason check (`output/star-injuries/multiseason.sh`), full seasons for the new setting, tables, tests.
