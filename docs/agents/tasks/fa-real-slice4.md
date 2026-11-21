# FA-REAL slice 4: two-ways, camp deals, the cutdown, sign-and-trades

_Claude (Opus agent), branch `worktree-agent-a705af51286ad1e81` (from main at d93e80d). Status: **in progress**._

## Objective
Two-way contracts, Exhibit 10 camp deals, the 21-to-15 cutdown with proper waivers, sign-and-trades, a thinner late
market, and roster repair that respects hard caps (task brief in the coordinator's prompt; plan
`fa-realism-plan.md`; evidence `roster-edge-evidence.md`).

## Boundaries
- Touch: `offseason_decisions.py`, `offer_sheets.py`, `cap_ledger.py`, `play.py`, `save.py` (roster, waivers, cutdown,
  repair, free agency), `waivers.py`, `contract_ai.py`, `contract_protection.py`, `payroll_plan.py`, `app_actions.py`,
  `multiplayer.py`, `gui/app.js`, `gui/free-agency.css`, `gui/offseason.css`, `gui/window-icons.js`, new modules, tests.
- Minimal and marked only: `transactions.py` / `trade_*.py`. Never: `trade_market.py`, `health.py`, `injury_model.py`,
  `sim.py`.

## Resume state
- New modules: `two_way.py`, `camp.py`, `sign_and_trade.py`; hooks in `save.py` (daily hook in
  `advance_lifecycle_to`, game-day call-ups in `advance_save_day`, box-score filter, cutdown targets, roster repair,
  user roster minimum gate), `play.py` (sign-and-trade pass on market days 2+ and Aug 1), `app_actions.py` (roster view,
  actions), GUI (opening-roster window, builder section), `tests/test_roster_edge.py`.
- Harness: `output/fa-real-slice4/` (`lean_probe.py` with an opening-night copy, `edge_metrics.py`, `codecopy.sh`;
  `base` = main d93e80d two seasons; `os1` = quick offseason replay from base's 2027 Finals copy).
