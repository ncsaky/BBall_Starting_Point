# FA-REAL slice 2: the calendar and the four stops, options and qualifying offers

_Claude (Opus agent), branch `worktree-agent-a246e3c04237da68c` (from main at eab27ac). Status: **in progress**._

## Objective
Slice 2 of `fa-realism-plan.md`: the real offseason calendar with one contract-season switch date, the four stops
(decide who to keep, make offers, finalize and match, set the roster), player/team options and early terminations,
qualifying offers with exact eligibility and amounts (replacing the "keep young regulars" shortcut), the interim
restricted rule (no offer sheets until slice 3), the thin AI market fix, rookie-scale extension and rookie-option
deadlines.

## Boundaries
- May touch: `save.py`, `play.py`, `cap_ledger.py`, `cap_rules.py`, `contract_ai.py`, `payroll_plan.py`, `draft.py`
  (lottery/draft dates only), `waivers.py`, `app_actions.py`, `multiplayer.py`, `gui/app.js`, `gui/free-agency.css`,
  a new offseason CSS file, `gui/index.html`, tests, this file. New modules: `offseason_calendar.py`,
  `offseason_decisions.py`. Measurement script `scripts/overnight_market_health.py` (`select_action`) follows the new
  calendar so the probe runs.
- Read-only: `transactions.py`, `trade_*.py`, `front_office.py`, `trade_market.py`.
- Commit on the branch only; never push.

## Design (decided)
- **Calendar** (`offseason_calendar.py`, ending year Y): lottery the Sunday in May 8-14 (background, during the
  playoffs); playoffs to June 16 (the game's Finals end June 10-16); offseason opens June 17 = the one contract-season
  switch; draft the first Tuesday on/after June 22 and the next day; options and qualifying offers due June 29; talks
  with other teams' free agents June 30; league year July 1 (empty-roster charges start); qualifying offer withdrawal
  keeps Bird rights through July 13; qualifying offers expire October 1; roster and rookie-scale extension deadline the
  day before opening night; rookie options October 31 or the next weekday.
- **Phases** keep their names: `re_signing` = stop 1 (before and after the draft), `draft`, `free_agency` = stop 2
  (market days from June 30), stop 3 = the market's completed state (signing-day recap), `offseason` late summer,
  `training_camp` September, `preseason` = stop 4. No `draft_lottery` date range any more.
- **Options** read from the contract data (`contract_protection` evidence from the Basketball-Reference contract table,
  plus generated rookie deals), written onto contracts. Rules in one labeled block in `offseason_decisions.py`.
- **Qualifying offers**: CBA formulas; AI tenders valuable eligible players; interim restricted rule (own team only;
  accept the qualifying offer or wait to October 1).

## Resume state
- Baseline probe on main code: `output/fa-real-slice2/basecode` (copy of src+scripts at eab27ac), run in
  `output/fa-real-slice2/basecode/output/base_probe` (log `output/fa-real-slice2/base_probe.log`, pid file next to it).
- Next: calendar module and phase map.
