# CORE-RENEW: core promises, and the injury rule that switched off a team's protections

Progress: 6/6 - done, ready for the coordinator's review

Owner: Claude (side session, worktree `vigilant-cori-6ae562`, branch `claude/vigilant-cori-6ae562`).

## Report

**TL;DR**
- Narrowed the injury rule (user's OK, 2026-11-27): only a long injury to one of a team's three best players counts, and
  it frees only that player. A hurt reserve can no longer put a team's stars up for picks.
- In offer tests, 34 cheap sales are now refused and none got easier. Two new test runs made 177 trades against 188.
- No renewal rule was added. The new runs produced one champion trade a fan might question, which the unused draft
  would block.

### The injury rule
| | Before | Now |
|---|---|---|
| Which injury counts | any core player, 90 days or more from returning | one of the three best players, missing 90 days or more of regular season (about half; summer days count for nothing) |
| What it switches off | for the whole team: the core promise, "picks cannot pay for a star" and "a competing team does not weaken its rotation" | the same three, only for trades of the injured player |
| A stalled trade talk with a core player | frees the whole team | unchanged |

It applies to computer-to-computer trades and to the user's offers. For any given trade it can only refuse more than
before, never less. LeBron's exception, textbook trade rules and every player rating are unchanged.

### Offer tests
Both original test runs' July 1 saves (2027 and 2028), reviewed by the old rule and by the new one: each computer
team's five best players, asked for with the user team's (Brooklyn's) best one to three first-round picks plus salary.

| | Before | Now |
|---|---|---|
| Team-summers under an injury review (of 116) | 22 | 3 |
| Top-three players sold by teams the old rule had under review (of 66 asked) | 50 | 24 |
| Top-three players sold by other teams (of 282 asked) | 181 | 181 |

- 34 offers are now refused, including ones for Anthony Edwards, Cade Cunningham, Scottie Barnes, Donovan Mitchell and
  Victor Wembanyama. No offer got easier.
- The injured star himself can still be bought (Evan Mobley, out until April 2028, for one very good first and salary).
- The other players still sold would go for the same offer if nobody on their team were hurt.

### Two new test runs (two seasons each, same seeds)
| Trades | First run before | First run now | Second run before | Second run now |
|---|---|---|---|---|
| 2026-27 season | 20 | 18 | 23 | 18 |
| Summer 2027 | 23 | 22 | 30 | 29 |
| 2027-28 season | 22 | 25 | 22 | 23 |
| Summer 2028 | 27 | 26 | 21 | 16 |
| All | 92 | 91 | 96 | 86 |
| Teams holding a promise at the 2027 playoffs | 19 | 28 | 21 | 28 |

Volume is a little lower (6% over both runs), mostly in the first season, where far fewer promises are now switched off.
Later differences are partly chance: after the first changed trade the two histories drift apart.

Two trades in the new runs a fan might question. Neither is caused by the injury change:
- June 30, 2028: champion Boston sends its starting center Neemias Queta to Denver for Aaron Gordon (33) and a pick.
  The champion's promise had lapsed. The drafted renewal would block it.
- July 2, 2027: New York sends Jalen Brunson and a pick to Memphis for Cam Spencer. New York had won no series and had
  marked Brunson to move, so a playoff-run renewal would not block it.

## The renewal question (the original task)
**Confirmed:** every team promises to keep its core when a career starts (to June 30, 2027); only a big acquisition
starts another. Before the injury change, 6 to 12 of the 29 computer teams held a promise after the first summer.
Nothing gives a champion a new one. It reads as designed: a one-season trial.

**Judged on the first two runs:** no unbelievable computer-to-computer trade. Six core players moved from teams that had
reached at least the conference finals, mostly believable upgrades or reserve swaps (champion Oklahoma City's Alex
Caruso and two picks for Kristaps Porzingis is the one a fan might argue about). The drafted renewal changed none of 94
offer tests. So it was not added.

**Since then:** the Queta trade above is the first case I would count in its favor.

## Decisions for the user
1. The renewal, for "champions keep cores". It is drafted in `core-renew-draft.patch` (rebased on the injury change;
   apply with `git apply`). It keeps the core of any team that won two or more series until the next June 30, so it also
   stops believable upgrades. A champions-only version is possible but not built.
2. Follow-ups, none started:
   - A stalled trade talk with one core player still frees the whole team, as the injury rule used to (3 of 116
     team-summers in the offer tests).
   - A team that marks a star to move can accept a weak return (the Brunson trade).
   - A very good pick buys many teams' best players with nobody hurt (the 181 of 282 above).

## Checks and limits
- New `tests/test_injury_review.py` (9 tests). Updated two older tests that relied on the old rule and the frozen copy
  used by the planning speed test.
- The draft's tests pass with the planning, trade-core and injury tests (51 tests); it was not run over full seasons.
- Full test suite on a cloud machine: 2,769 tests, 0 failures, 0 errors, 69 skipped. Browser tests were not run
  (no screen code changed).
- Two seeds only. The offer tests use one user team's picks and judge only the selling team. The regular season is
  taken as October 20 to April 12. Nothing was checked in the game's screens.

## Files
`src/nba_gm_data/team_planning.py`, `transactions.py` (premium-player rule), `trade_roster.py` (rotation rule), tests,
this file, `core-renew-draft.patch`, one board row. Run results and scripts are in this worktree's `output/core-renew/`
(git-ignored). About 7 cloud machine-hours.
