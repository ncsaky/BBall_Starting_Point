# FA-REAL slice 1: the money rules

_Claude (Opus agent), branch `worktree-agent-afd2d3c7a0ddb24ed` (from main at be73218). Status: **in progress**._

## Objective
One calculator (`src/nba_gm_data/cap_ledger.py`) that answers, for any team and any move: is it legal, how is it paid
for, and what does it lock in. Free agency (offer builder, AI bids, AI re-signing pass, roster repair, waivers) uses
it, so the screen and the save agree. Plan: `fa-realism-plan.md`; rules: `fa-realism-research.md`.

## Boundaries
- May touch: `cap_ledger.py` (new), `cap_rules.py`, `contract_ai.py`, `play.py` (FA, re-signing, repair paths),
  `save.py` (re-signing pass, contract writing, repair, cap summary), `waivers.py`, `contract_protection.py`,
  `app_actions.py` (FA actions), `gui/app.js` (FA room and builder only), `gui/free-agency.css`, tests, this file.
- Do not touch: `transactions.py`, `trade_*.py`, `multi_team_trades.py`, `trade_counters.py`, `team_planning.py`, the
  trade window in `app.js`, `assistant-phone.js`, `health.py`, `injury_model.py`, `rest_model.py`.
- Commit on the branch only; never push.

## Resume state
- Done: `cap_ledger.py` (lines, minimum scale, exceptions, holds, payroll views, quote/commit/reserve/release,
  renounce, hard caps, trade dates, waiver absorb route); `cap_rules.py` exact lines + floor + true max; play.py
  (`signing_cap_check` via ledger, `ai_bid_payment`, AI renounce, acceptance re-quote, user payment);
  contract_ai `apply_contract_to_save_state` writes schedule + commits; save.py retention pass, strategic signings,
  roster repair (true minimums), released FA signings, `team_cap_summary` via ledger; waivers claims via ledger;
  app_actions (legal terms per candidate, ledger view, `free_agent_offer_quote`, `renounce_cap_hold`). Focused tests
  updated (keep_stars, free_agency_bids, room payload floors, contract_protection).
- Baseline replay (main code) done: `output/fa-real-slice1/base/` (draft 2027 -> preseason, 248 s).
- Next: GUI (room + builder + cap table + renounce), `tests/test_cap_ledger.py` scenarios, branch replay + metrics,
  JS cap preview parity test, core tests, calibration, report.
