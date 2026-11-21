# FA-REAL slice 3: restricted free agency, offer sheets and matching

_Claude (Opus agent), branch `worktree-agent-aad20417c535ae44b` (from main at 5da7b81). Status: in progress._

## Objective
Replace slice 2's interim restricted rule (a restricted free agent talks only to his own team) with real offer sheets
and matching: legal sheet terms (2-4 years, 5% raises, the Arenas rule, at least 3 years after a maximum qualifying
offer), the bidder's room or exception reserved until the sheet resolves, one sheet per player, a matching deadline,
the incumbent's match (Bird rights, room or an exception, never past a triggered hard cap), a year's trade block after
a match, the player's choices (sheet, qualifying offer, wait), AI bidders and incumbents with stated reasons, and the
user's Match or Pass countdown plus offer sheets from the free-agency room.

## Boundaries
- May touch: `offseason_decisions.py`, `cap_ledger.py`, `play.py` (free-agency paths), `save.py` (restricted/FA paths,
  signing-day hook), `contract_ai.py`, `payroll_plan.py`, `app_actions.py` (FA actions), `multiplayer.py` (action
  registration), `gui/app.js` (FA room, offseason screens), `gui/free-agency.css`, `gui/offseason.css`,
  `gui/assistant-phone.js` (one text type), tests, this file. New module `offer_sheets.py`.
- Read only: `transactions.py`, `trade_*.py`, `front_office.py`, `trade_market.py`.
- Out of scope: two-ways, Exhibit 10, cutdown, sign-and-trades (slice 4).

## Resume state
- [x] Worktree data symlinked; read plan, research, evidence, slice 1-2 reports.
- [ ] `offer_sheets.py` engine; cap_ledger reservations; offseason_decisions hooks; play.py market-day hooks.
- [ ] app_actions payload/actions, GUI Match or Pass + offer-sheet builder, assistant text.
- [ ] Tests; core + related suites; JS.
- [ ] Replays (main vs branch), probe seed 17, scorecard, screenshots; report.
