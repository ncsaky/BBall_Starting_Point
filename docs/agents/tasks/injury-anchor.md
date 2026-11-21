# INJURY-ANCHOR: anchor the injury model to the complete public records (2026-11-21)

Branch: `worktree-agent-af5fe5f212784fb07`. Scratch and harness: `output/injury-anchor/` (git-ignored).

## Objective
Re-anchor the injury model's league-wide base rates to the three complete public seasons (Codex's
`data/research/injury_history_{2023_24,2024_25,2025_26}.json`) instead of the Basketball Index tracker, which misses
many injuries that cost games. Keep the slopes unless the complete data contradict them. Decide whether illness
belongs in a player's history.

## Boundaries
May touch: `scripts/build_injury_model.py`, `injury_model.py`, `health.py` (injury parts only), the model file via the
script, a v4 evidence file (git-ignored), research scripts, tests, this file. Not: `save.py`, `trait_adapter.py`,
`ratings_model.py`, `stage2/`, trade/FA/offseason files, `gui/`, `rest_model.py`.

## Resume state
- Done: builder anchors to complete records (one count per absence), recovery lengths re-weighted to the complete
  records' length mix, illness joins the history (evidence: +31.5 / +5.7 log-likelihood), in-season history in the
  anchor, v4 evidence, tests (`tests/test_injury_anchor.py`, `tests/test_star_injuries.py` updated).
- Runs: `before_s17/s29` (main), `anchor_s17/s29` (rates only, first pass), `new_s17/s29` (full change).
- Next: analyze `new`, multiseason check, health speed, tests, scorecard, report.
