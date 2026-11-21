# FA-REAL slice 2: the calendar and the four stops, options and qualifying offers

_Claude (Opus agent), branch `worktree-agent-a246e3c04237da68c` (from main at eab27ac). Status: **in progress**._

## TL;DR
- TBD

## Objective
Slice 2 of `fa-realism-plan.md`: the real offseason calendar with one contract-season switch date, the four stops
(decide who to keep, make offers, finalize and match, set the roster), player/team options and early terminations,
qualifying offers with exact eligibility and amounts (replacing the "keep young regulars" shortcut), the interim
restricted rule (no offer sheets until slice 3), the thin AI market fix, rookie-scale extension and rookie-option
deadlines.

## Boundaries
- Touched: `save.py`, `play.py`, `cap_ledger.py`, `contract_ai.py` (two lines), `payroll_plan.py`, `app_actions.py`,
  `multiplayer.py`, `gui/app.js`, `gui/index.html`, new `gui/offseason.css`, tests, this file. New modules
  `offseason_calendar.py` and `offseason_decisions.py` (the plan named the first). Outside the list, kept minimal:
  `gui/window-icons.js` (two icons for the new windows; the icon test requires one per window) and
  `scripts/overnight_market_health.py` (`select_action` follows the new calendar so the probes run).
- Not touched: `transactions.py`, `trade_*.py`, `front_office.py` (read only, for the traits), `trade_market.py`,
  `draft.py` (the lottery and draft dates live in the calendar module; `draft.py` needed no change).

## Resume state
- Probes (disk-light, run from code copies so edits can't leak in): `output/fa-real-slice2/lean_probe.py`,
  `codecopy.sh`; branch run `branchcode/output/run2`, main run `basecode/output/base`; metrics
  `offseason_metrics.py RUNDIR 2027 2028`; tax teams `tax_teams.py`; day-one bid funnel `bid_funnel.py`.
- Load rule (coordinator): one heavy job at a time, `nice -n 10`, wait on own PID.
