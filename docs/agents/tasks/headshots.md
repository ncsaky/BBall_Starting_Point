# HEADSHOTS: staff and prospect faces

Owner: Claude (Opus agent), branch `worktree-agent-abab0f5b961e89d94`. Board row: HEADSHOTS.

## Objective
- Real coaches and real prospects show their real public headshots (stored locally, with a manifest).
- Generated staff and generated prospects get faces from a large, openly licensed, gender-tagged library;
  nobody repeats within a league; a staff member's name and face always share a gender.
- Much larger staff name lists (male and female), realistic share of women by role.
- Wired into the staff window, coach cards, draft board, prospect cards.

## Boundaries
May touch: `staff.py` / `staff_lifecycle.py` name and face code, `save.py` only where staff are generated,
`draft.py` / `real_prospects.py` / `prospect_cards.py` face fields, `schema.py` (one optional face field on
DraftProspect), `gui/app.js` face helpers, new `gui/assets/headshots/`, new `faces.py`, `scripts/`, tests.
Keep away from free agency, offseason, trades, Trade Market.

## Resume state
- [x] Board row added, worktree symlinks done.
- [x] Audit (see below, being filled in).
- [ ] Face tooling (DiceBear in output/headshots/tooling), sample sheet options.html
- [ ] Real coach photos, real prospect photos + manifest
- [ ] Generated library + faces.py + staff identity (gender, names)
- [ ] Prospect face fields in draft.py
- [ ] GUI wiring, screenshots
- [ ] Tests, report
