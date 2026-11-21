# CONTRACT-TERMS: contract history, salary paths and options, option decisions

_Claude (Opus agent), worktree branch `worktree-agent-a467c2ea2e59eaa25`. Status: **in progress**._

## Objective (user request 2026-11-21)
1. Rebuild each real contract's original length and signing season from evidence (the salary tables list only the
   seasons left, so Podziemski was listed as extendable and then refused); check extension rules against the CBA.
2. Salary path (flat / rising / declining) and a final-season option (none / player / team) in user offers
   (free agents, re-signings, extensions); AI values them; AI-to-AI deals use realistic shares.
3. Option decisions the user can see (own team options = user decision; player options decided by the player with a
   reason, shown on a screen/card and in a message; notable league-wide decisions on the wire).

## Boundaries
`contract_ai.py`, `cap_rules.py`, contract/extension/free-agent offer/option code in `save.py`, `app_actions.py`,
`play.py`, `free_agency*.py`, offer/extension/option screens in `gui/app.js` (+ CSS, `index.html` cache versions),
contract data normalisation (`contract_history.py`, `storage.py`, the 2026-27 universe JSON contract fields), research
scripts, tests. Not: `health.py`, `ratings_model.py`, `development_outlook.py`, `talent.py`, `stage2/`, `sim.py`,
the input estimator, `player_inputs_2026_27.json`, `faces.py`.

## Resume state
- Part 1 code written: `contract_history.py` (evidence builder + apply on load/build), `scripts/build_contract_history.py`
  -> `data/canonical/contract_history_2026_27.json`; universe JSON contract fields rewritten (same formatting);
  `contract_ai.extension_contract_window(contract, player)` rewritten to the CBA rules; per-player deadlines
  (`extension_deadline_for`, `save.player_extension_deadline`, `extension_window_closed_for_player`); extensions legal
  July 6 to June 16; AI passes July 6 - Jan 15 plus a pass on the opening-roster deadline; AI first-year limit and term.
- Before/after on a new GSW save: eligible 4 -> 116 (98 veteran, 18 rookie scale). Podziemski eligible; Set The Roster
  list == extension screen.
- Next: finish focused tests, commit part 1; then part 2.
