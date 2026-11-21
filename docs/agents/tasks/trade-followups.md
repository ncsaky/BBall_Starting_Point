# Trade market follow-ups (TRADE-FOLLOWUPS)

_Claude (Opus agent), branch `worktree-agent-a005c209a28cf9621` (from dab88e7). Status: **in progress**._

## Objective
The five follow-ups from TRADE-MARKET (`trade-market.md`, "What's left"; plan `trade-market-personality-plan.md`):
1. Agreed market sales applied once (the Josh Hart repeat): executed the day they are agreed or cancelled with a reason.
2. Young-starter guard: young players in a real rotation role, judged by role and value (Javon Small).
3. Front-office hints on team pages (same words, sharpening with dealings).
4. Multi-day negotiations on summer market days (free agency, late summer, camp).
5. Retire the hidden old front-office profile fields that nudge trade decisions (rule 4).

## Boundaries
- Files: `trade_market.py`, `front_office.py`, `transactions.py`, `trade_targets.py`, `trade_tax.py`,
  `payroll_plan.py` (owner factor only), `team_planning.py` (patience read), `app_actions.py` (team-page read),
  `gui/app.js`, `trade-workspace.css`, `index.html` (cache keys), `play.py` (two summer market hooks only),
  `save.py` (trade-market hook functions only: `queue_ai_recommendations` market part, `late_deadline_trade_pass`),
  scripts, tests.
- Not the offseason calendar or phases, the free-agency room, or `cap_ledger.py` (FA-REAL slice 2).
- Textbook acceptance rules unchanged; no random rolls; all guards kept; LeBron untouched.

## Resume state
- Base probe (branch start, dab88e7): `output/trade-followups/base-src/output/probe` (copy of src/scripts; data and
  gui symlinked). Log `output/trade-followups/base.log`. Snapshots under `.../probe/snapshots/`.
- Disk was full once (1.7 GB free on the laptop); base probe crashed at 2027-04 and was resumed from its checkpoint.
- Code for all five fixes written; new `tests/test_trade_followups.py` (16 tests) passes.
- Laptop crashed (overload) during the base probe; resumed from its checkpoint with `nice -n 10`. Load rule: two heavy
  jobs at once on the laptop (this task and FA-REAL slice 2); mine run one at a time.
- Next: replay the 2027 deadline week from the base snapshot with the new code, then the full probe of the branch.
