# PICK-REFIT: trade side of the 3-2-1 lottery

Progress: 6/8 - waiting on the after-change season runs and the full suite

Owner: Claude (side session, worktree `reverent-brattain-6d2232`, branch `claude/reverent-brattain-6d2232`).
Go-ahead from the coordinator 2026-11-26.

## Report (interim: NOT ready to merge until the two checks under "Left to do" are in)

**TL;DR**
- New trades can no longer protect a first-round pick top-12 through top-15.
- From the 2027 draft on, computer teams price a future pick by the new lottery odds. A worst team's pick is no longer
  worth much more than the seventh-worst's.
- 641 focused tests and the browser-script tests pass. Trade-volume comparison and the full suite are still running.

**Protection rule** (NBA announcement and official rules sheet, 2026-05-28): "unable to attach top-12 through top-15
protections to newly traded draft picks". The announcement says nothing separate about existing protections; the word
"newly" is why existing ones are kept (including the one real 2027 top-14 protected first at career start).
- Judgement call: any range *ending* at 12-15 is refused (so "picks 2-14" too). First round only.
- Enforced in the trade room (also shown under the condition), the command-line prompt, and when a trade is applied.
  The AI only ever offered top-4 and top-10, so its offers are unchanged.

**Pick values** (`pick_lottery_value.py`). The finish forecast is unchanged; from 2027 it is turned into a value using
each lottery group's odds, uncertainty about the finish (wider further out), the repeat-top-pick limits, the new
second-round order, and lottery draws for "best of" pick rights.

Mid-season save (3 Feb 2027), 2027 first-round picks:

| From (record) | Before | After |
|---|---|---|
| Sacramento (11-40, worst) | 108.0 | 94.5 |
| Brooklyn (11-38) | 103.5 | 94.7 |
| Charlotte (17-34) | 90.0 | 94.1 |
| Memphis (20-28) | 84.0 | 92.0 |
| Golden State (25-26) | 74.6 | 84.0 |
| Toronto (28-23) | 56.0 | 59.8 |
| Philadelphia (37-13) | 40.5 | 40.9 |

- First-round picks in one draft add up to about 4-9% more than before (mid-range picks now carry lottery chances).
- Far-off picks from good teams rose most: the cheapest unconditional 2031 first went 40 to 48, 2033 33 to 45.
- Recalculating pick values takes 2.6 ms instead of 1.9 ms. No player ratings change.
- Not changed: the flat discount for protected picks and the swap-right formula still ignore the new odds. Draft room
  screens untouched.

## Left to do
1. Compare trades. Before: seed 20261126 had 49 trades (30 with a pick, 17 firsts and 47 seconds moved); seed 20261127
   had 56 (41, 21, 52). After runs write to `output/pick-refit/after-26` and `after-27`; run
   `python3 output/pick-refit/season_summary.py <run dir> --list` on all four.
2. Full suite: `output/pick-refit/suite.log` and `output/pick-refit/suite/`.
3. Add both to this report in plain language, then mark the board row for review.

## Cleanup
Remove the baseline checkout: `git worktree remove --force <session scratchpad>/base` (its results are copied to
`output/pick-refit/`).
