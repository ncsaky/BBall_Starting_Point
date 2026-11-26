# TRADE-CORE: a team just off a playoff run does not sell a core player cheaply

Progress: 5/7 - focused tests and the two before/after test seasons running

Owner: Claude (side session, worktree `great-taussig-7876fd`, branch `claude/great-taussig-7876fd`).

## Objective
Computer teams that just made a playoff run could still trade a core player for a role player as a "close call"
(Cleveland, one series won, Jarrett Allen and a pick swap for Cam Spencer). Fix it if a fan would not believe it.
Keep LeBron's exception, textbook trade rules, trade volume and every player rating unchanged.

## Boundaries
`team_planning.py`, `trade_tax.py`, `transactions.py` (acceptance check only), `tests/test_trade_core.py`, this file.

## Resume state
- Branch holds `main` + PICK-REFIT up to `c2af00d4` (not yet in main when this started) + this fix (`5a4f8931`).
- Cloud runs: `output/trade-core/{before,after}-{26,27}` are fetched into frozen code copies in the session
  scratchpad (`before/`, `after/`); move them into this worktree's `output/trade-core/` when done.
