# CORE-RENEW: should a playoff run renew a computer team's promise to keep its core?

Progress: 6/6 - done, ready for the coordinator's review (no game code changed)

Owner: Claude (side session, worktree `vigilant-cori-6ae562`, branch `claude/vigilant-cori-6ae562`).

## Report

**TL;DR**
- Confirmed: after the first summer only 6 to 12 of the 29 computer teams still promise to keep their core (27 at the
  start). That is how it was built, but nothing renews the promise after a title.
- No renewal rule was added. I saw no unbelievable trade between computer teams caused by this, and the rule would not
  have changed any of 94 test offers from the user's side.
- What does let stars go cheaply: one injured core player, even a reserve, switches off the team's protections. That
  rule was to be kept, so it is unchanged and needs a decision.

### Is it intended?
Mostly yes. The promise reads as a one-season trial: every team gets it when a career starts (to June 30, 2027), and
only a big acquisition starts another. When it ends, a team that keeps going out early may mark a player to move.
Nothing in the code gives a champion a new one.

| Computer teams holding a promise | First run | Second run |
|---|---|---|
| Career start (October 2026) | 27 | 27 |
| June 30, 2027 | 20 | 21 |
| September 1, 2027 | 8 | 6 |
| April 2028 | 9 | 12 |
| October 2028 | 8 | 8 |

### Trades in two two-season test runs (today's game)
There is no "after" column: the game was not changed.

| | First run (seed 20261126) | Second run (seed 20261127) |
|---|---|---|
| All trades | 92 | 96 |
| 2026-27 season / summer 2027 / 2027-28 season / summer 2028 | 20 / 23 / 22 / 27 | 23 / 30 / 22 / 21 |
| Times a computer team gave up a core player, after the first summer | 21 | 16 |
| ... by a team that had just won a series | 5 | 6 |
| ... by a team that had reached at least the conference finals | 2 | 4 |
| Top-three player moved by a team that had just won a series | 0 | 0 |

The six moves by conference finalists and better:

| When | Team gives | Team gets | Verdict |
|---|---|---|---|
| Jul 2027 | Champion Oklahoma City: Alex Caruso, 2 picks | Kristaps Porzingis | Believable upgrade (the one a fan might argue about) |
| Feb 2028 | Cleveland: Tyrese Proctor (reserve), 1 pick | Jalen Wilson | Odd but tiny |
| Jul 2027 | Boston: Jordan Walsh (reserve) | Khris Middleton, 1 pick | Believable bench move |
| Sep 2027 | Boston: Neemias Queta, 2 reserves, 1 pick | Kristaps Porzingis | Believable upgrade |
| Feb 2028 | Oklahoma City: Jaylin Williams (reserve), 1 pick | Precious Achiuwa | Believable bench move |
| Jul 2028 | Charlotte: Liam McNeeley, 1 more prospect, 2 picks | Mark Williams | Believable upgrade |

A renewal after a deep run would have covered five of these (not Boston's July move, because of an injury). The other
core moves came mostly from teams rebuilding or retooling (Golden State, Milwaukee, Orlando, Phoenix and others). A
few look thin (Boston sending Mitchell Robinson for T.J. McConnell; Milwaukee sending Tyler Herro for two reserves and
a pick), but those teams were not coming off a deep run, so a playoff-run rule would not touch them.

### Your own offers
On July 1 of 2027 and 2028, each core player of each conference finalist or better was asked for with the user team's
(Brooklyn's) best one to three first-round picks plus matching salary: 94 players.

- Today's game and the drafted renewal gave the same answer for all 94.
- Teams under the injury rule below have no promise to renew. The others already refused, or valued the pick so far
  above the player (a very good first is about the 6th pick in the first run) that it cleared the promise's bar, a gain
  of at least 20% of what they give.
- Stars are mainly protected by the premium-player rule: a competing team will not trade a star for picks.

### The injury rule is the real gap
If any one core player is 90 days or more from returning when the team is reviewed, the team is treated as reviewing
its roster. That switches off three protections at once: the core promise, the rule that picks cannot pay for a star, and the rule that a
competing team does not weaken its rotation.

- 7 of the 16 conference-finalist-or-better summers had this.
- Toronto's came from Allen Graves, a 21-year-old reserve due back October 3, 2027, before opening night (October 21).
  The user could then buy Scottie Barnes for one first and Julius Randle.
- With Jarrett Allen out until January 2028, Cleveland accepted the same kind of offer for Donovan Mitchell, Evan
  Mobley or James Harden (second run).
- Of 26 offers accepted by teams under this rule, 17 would have been refused without it.
- The computer-only trades in these runs did not make such sales. This is open to the user's offers.

## Decisions for the user
1. Narrow the injury rule (for example: only a top-three player who misses a large part of the coming season, and it
   should not let picks buy the team's other stars). Recommended; not started.
2. Add the renewal anyway, for "champions keep cores" as a stated rule. Not recommended: on the evidence it mostly stops
   believable upgrades. It is drafted in `core-renew-draft.patch` (apply with `git apply`).

## The drafted renewal (not applied)
A team that wins two or more series keeps its core promised until the next June 30, while at least half of the players
who made the run remain; injury and trade-demand exceptions still cancel it; its refusal message names the playoff run.
Its 10 tests passed together with the planning and TRADE-CORE tests (31 tests). It was not run over full seasons, and
the full test suite was not run.

## Limits of the evidence
Two seeds, two seasons each; deep-run core sales are rare, so a bad one could still appear. The offer test used one user
team's picks and judged only the selling team's answer. Nothing was checked in the game's screens.

## Objective
Computer teams promise to keep core players, but the promise is only set at career start or after a major acquisition.
Confirm on finished season runs, judge it, and renew it if a fan would not believe the resulting trades, keeping the
injury and trade-demand exceptions, textbook trade rules, LeBron's exception, ratings and similar trade volume.

## Files
Committed: this file, `core-renew-draft.patch`, one board row. No game code, tests or ratings changed. Run results and
scripts are in this worktree's `output/core-renew/` (git-ignored): `tools/core_renew_run.py` runs seasons from the
checkout root (copy it there), `core_renew_compare.py` reads them, `user_pry_probe4*.py` are the offer tests and
`exception_probe.py` lists the injuries. Two cloud runs, about 3 machine-hours.
