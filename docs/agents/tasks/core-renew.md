# CORE-RENEW: champions keep their cores, and the injury rule that switched off a team's protections

Progress: 5/5 - done, ready for the coordinator's review

Owner: Claude (side session, worktree `vigilant-cori-6ae562`, branch `claude/vigilant-cori-6ae562`).

## Report

**TL;DR**
- Champions now keep their core through the summer and the next season (user's choice, 2026-11-27). Boston's earlier
  sale of Neemias Queta right after winning is now refused.
- The injury rule is narrowed (user's OK, same day): a hurt reserve can no longer put a team's stars up for picks.
- Your own offers can still buy some champion players with a great draft pick; that is a pricing problem, not these rules.

### The champion promise
A team that wins the title keeps its core promised until the next June 30, or until another champion is crowned.

- It ends early if most of the players who won the title have left.
- The injury and trade-talk exceptions still apply (an injury frees only the injured player).
- A core player can still go in a deal the champion gains a lot from (at least 20% more than it gives up).
- When computer teams search for trades, a champion leaves its core out of what it offers.
- A refused offer says why: "as champions they are keeping this core together".

Two earlier trades judged again on their saved summer:

| Trade | Without the promise | With it |
|---|---|---|
| June 30, 2028: champion Boston gives Neemias Queta for Aaron Gordon and a pick | made | refused |
| July 3, 2027: champion Oklahoma City gives Alex Caruso and two picks for Kristaps Porzingis | made | still accepted, as a large gain; but Oklahoma City would not offer Caruso in its own search |

Offer tests: for the champion in each of 8 test summers, every core player was asked for with the user team's best one
to three first-round picks plus salary. 19 of 56 were sold, both with and without the promise: a very good pick is
priced high enough to clear its bar. Among each champion's three best players, only Queta was sold.

### Two test runs with the champion promise (two seasons each, same seeds as before)
| Trades | First run, injury rule only | First run, with promise | Second run, injury rule only | Second run, with promise |
|---|---|---|---|---|
| 2026-27 season | 18 | 18 | 18 | 18 |
| Summer 2027 | 22 | 22 | 29 | 29 |
| 2027-28 season | 25 | 16 | 23 | 23 |
| Summer 2028 | 26 | 28 | 16 | 16 |
| All | 91 | 84 | 86 | 86 |
| Core players a champion gave up after its title | 1 | 0 | 0 | 0 |

- The second run is the same until June 30, 2028 (80 of 86 trades identical).
- The first run splits on July 1, 2027. Its 2027-28 dip (25 to 16) is among other teams: the champion traded no player
  that season either way. It looks like chance after the histories split, but two runs cannot prove it.
- Over both runs, trades went 188 (before either change), 177 (injury rule), 170 (both): about 10% fewer in all.

### The injury rule
| | Before | Now |
|---|---|---|
| Which injury counts | any core player, 90 days or more from returning | one of the three best players, missing 90 days or more of regular season (about half; summer days count for nothing) |
| What it switches off | for the whole team: the core promise, "picks cannot pay for a star" and "a competing team does not weaken its rotation" | the same three, only for trades of the injured player |
| A stalled trade talk with a core player | frees the whole team | unchanged |

For any given trade it can only refuse more than before, never less. In offer tests on the same saves (every computer
team's five best players, July 1 of 2027 and 2028):

| | Before | Now |
|---|---|---|
| Team-summers under an injury review (of 116) | 22 | 3 |
| Top-three players sold by teams the old rule had under review (of 66 asked) | 50 | 24 |
| Top-three players sold by other teams (of 282 asked) | 181 | 181 |

34 offers are now refused, including ones for Anthony Edwards, Cade Cunningham, Scottie Barnes, Donovan Mitchell and
Victor Wembanyama. The injured star himself can still be bought. In its own two runs this change made 177 trades against
188, mostly fewer in the first season, where far fewer promises are now switched off.

## Background: the original question
Every team promises to keep its core when a career starts (to June 30, 2027); only a big acquisition started another,
so before these changes 6 to 12 of the 29 computer teams held one after the first summer. In the first two runs I saw no
unbelievable computer-to-computer trade from this and recommended no renewal. A later run produced the Queta trade, and
the user chose a champions-only promise. Other playoff teams get no renewal.

## Still open (none started)
- A stalled trade talk with one core player still frees the whole team (3 of 116 team-summers in the offer tests).
- Cheap star sales for great picks, and New York trading Jalen Brunson plus a pick for Cam Spencer: investigated in a
  separate session (branch `claude/festive-chaplygin-aacfb6`, `docs/agents/tasks/trade-price.md`, report only; two
  proposed refusals await the user's decision). That report was measured without the changes on this branch.

## Checks and limits
- `tests/test_core_renew.py` (champion promise, 9 tests) and `tests/test_injury_review.py` (9 tests). Updated two older
  tests and the frozen copy used by the planning speed test for the injury rule.
- Full test suite on a cloud machine, final code: 2,778 tests, 0 failures, 0 errors, 69 skipped. Browser tests were
  not run (no screen code changed).
- Two seeds only. The offer tests use one user team's picks and judge only the selling team. The regular season is
  taken as October 20 to April 12. Nothing was checked in the game's screens.

## Files
`src/nba_gm_data/team_planning.py`, `transactions.py`, `trade_roster.py`, tests, this file, one board row. Run results
and scripts are in this worktree's `output/core-renew/` (git-ignored). About 12 cloud machine-hours in all.
