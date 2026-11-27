# TRADE-CORE: a team just off a playoff run does not sell a core player cheaply

Progress: 7/7 - done, ready for the coordinator's review

Owner: Claude (side session, worktree `great-taussig-7876fd`, branch `claude/great-taussig-7876fd`).

## Report

**TL;DR**
- A computer team that won a playoff series no longer sells one of its three best players because of tax savings or as
  a "close call". That stops the Cleveland deal (Jarrett Allen and a pick swap for Cam Spencer).
- The James Harden deal is believable and is left alone.
- Two test seasons made the same trades before and after (48 and 51): neither produced such a deal on the final pick
  values, so the effect is shown by re-judging the saved one.

**Merge order:** PICK-REFIT first. This branch already contains it up to `569edb7a`, which was not in main when this
finished. After that, this branch adds only the three small code changes and one test file.

### Why Cleveland made the Allen deal
- Without the tax, the deal cost Cleveland about 40 points of trade value. Saving $42M of luxury tax was worth
  +37 to it, which left -6 to -2: inside the shortfall computer teams may accept to get a deal done (up to 9).
- The earlier protection (no credit for tax saved by selling a top-three player) only covered contenders: a "peak"
  label or two series won. Cleveland had won one and was labelled "exiting" because its core is old. Allen was its
  second-best player.
- What changed on July 1 in the original test season: Cleveland's score went from beyond the limit (-12.9) to -2.3,
  mostly because the game rated Spencer about 10 points higher after that day's moves. Memphis's one-season promise to
  keep its core also ran out on June 30. I could not replay that day exactly; this comes from the saved numbers.

### What changed, in game terms
For a team that won at least one series, from June through the first 25 games of the next season:
1. Tax saved by selling one of its three best players counts for nothing. The deal must stand on basketball value.
2. It cannot give one up in a deal it does not itself rate good enough (no "close call"). This second part also covers
   the contenders already protected.
3. Exception: a player the front office has itself marked to move (its planned retool piece) is treated as before. This
   exception is not given to contenders.

It also applies to your offers: prying a top-three player from such a team takes real basketball value, not salary
relief. Bench players, picks, willing sellers, three-team deals' own all-must-agree rule, LeBron's exception, textbook
trade rules and every player rating are unchanged.

### The two examples
| Deal | Before | After |
|---|---|---|
| Allen and a swap to Memphis for Spencer (re-judged: June 30 rosters, July 1, final pick values) | made, Cleveland -6.0 | refused, Cleveland -43.6 |
| Harden and a swap to Chicago for Norman Powell | made | rule does not apply |

Harden verdict: believable. He is 38 and Cleveland's fourth-best player (so no rule applies), Powell is a similar-level
guard four years younger, and the deal saves about $60M of tax. A contender trimming an old star's money is normal.

### Two test seasons (final pick values, before and after)
| | Seed 20261126 | Seed 20261127 |
|---|---|---|
| Computer-team trades, before / after | 48 / 48 | 51 / 51 |
| Summer trades | 25 / 25 | 29 / 29 |
| Players moved | 91 / 91 | 86 / 86 |
| Picks and swap rights moved | 71 / 71 | 55 / 55 |
| Season sim seconds | 882 / 939 | 946 / 920 |

The completed trade lists are identical. In the first season one deal the computer teams weighed on July 3 and never
made did change: the old rules had Cleveland willing to send Allen to Atlanta for Onyeka Okongwu, a weaker center; the
new rules turned that into an offer built around Harden. Season times differ in both directions, so there is no sign of a speed change.

**How often this comes up:** in 14 saved test seasons on disk (about 380 summer trades, many runs close copies of each
other), a team that had won a series gave up a top-three player three times: the Allen deal (now refused), the champions'
Mobley-for-Spencer deal (already fixed by the earlier trade work), and Orlando sending Jalen Suggs for Jakob Poeltl plus
a first and a second (still allowed: Orlando rated it a gain without the tax).

### Judgement calls left as they are
- **First-round exits are not covered.** Both remaining top-three sales in the test seasons were such teams: Denver
  sent Aaron Gordon and picks for Keegan Murray (believable: similar player, five years younger, $16M of tax saved);
  Minnesota sent Jaden McDaniels to San Antonio for a young player, Tobias Harris, a spare wing and a first (debatable:
  tax counted +17, but real cap-strapped teams do make that kind of move). Say if you want them covered too.
- **Core promises are never renewed.** The promise a team makes to keep its core is set when a career starts and ends
  June 30 of that first season; only a major acquisition starts a new one. Not changed here.

### Checks
- New `tests/test_trade_core.py` (7 tests) passes.
- Trade, planning, pick and free-agency modules: 1,716 tests, one failure, which also happened without this change; it
  was a PICK-REFIT test, fixed there in `569edb7a` and passing here. The full suite was not run on this branch.
- One cloud run was killed partway through free agency (probably memory, not confirmed); its rerun finished normally.
- Computer-team decisions change by design wherever the rule applies; nothing else moves.

## Objective
Computer teams that just made a playoff run could still trade a core player for a role player as a "close call". Fix it
if a fan would not believe it. Keep LeBron's exception, textbook trade rules, trade volume and ratings.

## Rules as built
- `team_planning.fresh_off_playoff_run`: `latest_postseason_rounds` >= `PLAYOFF_RUN_ROUNDS` (1), and June-September or
  under `RECORD_GUARD_GAMES` (25) games.
- `trade_tax.contender_core_outgoing`: contender (as before) or fresh off a run; for the latter the plan's
  `retool_candidate_id` is excluded.
- `transactions.short_changed_core_sale`, used by `ai_trade_candidate_accepted`: refused when an AI side that has not
  accepted on its own would send such a player.

## Files
`team_planning.py`, `trade_tax.py`, `transactions.py` (acceptance check only), `tests/test_trade_core.py`, this file,
one board row. Run outputs and comparison scripts: `output/trade-core/` in this worktree (about 1 GB, git-ignored;
`tools/trade_core_run.py` runs a season, `compare_core.py`, `rejudge.py` and `history_scan.py` read the results).
