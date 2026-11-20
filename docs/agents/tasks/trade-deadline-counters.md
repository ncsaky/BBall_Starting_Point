# Trade deadline and counter-offers (TRADE-DEADLINE)

_Claude (Opus agent), branch `worktree-agent-aeffeb94cdbe260e6` (from main at 7cef425). Status: **in progress**._

## Objective
- Deadline week toward about 23 trades a season (real 23-28); two-season total toward 100-110 (was about 80).
- AI teams counter near-miss offers (each other's and the user's), the textbook way: one or two rounds, legal, close
  to the asking side's price, explained in plain words.

## Levers (in order; measure after each, stop once targets are met)
1. Salary filler a buyer would rather move (its own "salary I'd move" list) instead of rotation players.
2. Counter-asks (trade step 3) for near-misses only; also for the user's offers in the trade window.
3. A late second market pass on deadline day.

## Boundaries
- Files: `trade_targets.py`, `transactions.py` (target search, package builder), new `trade_counters.py`,
  `app_actions.py` (evaluate_trade counter), `gui/app.js` (trade response area only), scripts, tests.
- Not step 5 (front-office personality). Experimental engine untouched. Scorecards must not move.

## Resume state (updated as I go)
- Baseline probe done: 83 trades, deadline weeks 17 / 15; metrics in `output/trade-deadline/results/*_base.*`.
- Code so far (uncommitted until the after-probe is read): `trade_counters.py` (new), filler in
  `trade_targets.salary_filler` + `transactions.buyer_offer_packages_for_value`, quick capital limit aligned with the
  full check (`trade_targets.quick_capital_limit`), counters hooked into `transactions.target_driven_ai_trades`,
  late deadline-day pass `save.late_deadline_trade_pass` (focus_team_ids), user counter in `app_actions` evaluate_trade
  and `gui/app.js` (`tradeCounterOffer`). Tests: `tests/test_trade_counters.py`, `tests/trade_counter_offer.test.cjs`.
- Deadline-day funnel (2027 snapshot, no slot limit): 11 deals -> 15 (4 after counters).
- After-probe 1 running: `output/trade-deadline/after1-src`, PID in `output/trade-deadline/after1.pid`.

## Earlier notes
- Baseline probe: `output/trade-deadline/base-src` (copy of sources at 7cef425), log `output/trade-deadline/base.log`,
  PID in `output/trade-deadline/base.pid`. Snapshots under `base-src/output/probe/snapshots/`.
- Scratch diagnostic: `output/trade-deadline/diag_packages.py` (run from a sources dir with PYTHONPATH=src).
