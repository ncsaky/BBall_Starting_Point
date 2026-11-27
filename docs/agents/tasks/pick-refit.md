# PICK-REFIT: trade side of the 3-2-1 lottery

Progress: 10/10 - done, ready for the coordinator's review

Owner: Claude (side session, worktree `reverent-brattain-6d2232`, branch `claude/reverent-brattain-6d2232`).
Go-ahead from the coordinator 2026-11-26.

## Report

**TL;DR**
- New trades can no longer protect a first-round pick top-12 through top-15. Protections agreed earlier stay.
- From the 2027 draft on, computer teams price a future pick by the new lottery odds. The worst team's pick is no
  longer worth much more than the picks of the teams just above it.
- Trade volume held (105 trades over two test seasons before, 104 after). No player ratings changed.
- Second pass (asked for after the first report): protected picks and swap rights are priced by the odds too. See
  "Second pass" below; trade volume there was 101 before and 99 after.

### The protection rule
The NBA's May 28, 2026 announcement: "Teams will be unable to attach top-12 through top-15 protections to newly traded
draft picks." The official rules sheet says "Can't protect picks top-12 through top-15 in trades." Neither says
anything separate about protections that already exist; "newly traded" is why the game keeps them (a new career still
starts with its one 2027 top-14 protected pick, and it can be traded on with that protection).
- My judgement call: any protected range that *stops* at pick 12-15 is refused, so "picks 2-14" cannot be used as a
  disguised top-14. First-round picks only (second-round picks are numbered 31-60).
- Refused in the trade room (the reason shows under the condition), in the command-line game, and when a trade is
  applied. Computer teams only ever offered top-4 and top-10 protections, so their offers are unchanged.

### How a future pick is priced now
The game still forecasts where the pick's original team will finish. Before, that finish was treated as the draft
position. Now it goes through the new lottery: which group the finish lands in and that group's odds, how unsure the
forecast is (more for later drafts), the limits on repeat top picks, and the new second-round order. Rights to "the
better of two picks" are priced from simulated lottery draws.

Test save on 3 February 2027, 2027 first-round picks (trade value points):

| Pick from (record) | Before | After |
|---|---|---|
| Sacramento (11-40, worst) | 108.0 | 94.5 |
| Brooklyn (11-38) | 103.5 | 94.7 |
| Charlotte (17-34) | 90.0 | 94.1 |
| Memphis (20-28) | 84.0 | 92.0 |
| Golden State (25-26) | 74.6 | 84.0 |
| Toronto (28-23) | 56.0 | 59.8 |
| Philadelphia (37-13) | 40.5 | 40.9 |

- Average first-round value by draft year, same save (unconditional picks): 2027 up 2.0 points (+3%), 2029 up 4.3
  (+7%), 2031 up 4.6 (+8%), 2033 up 5.7 (+11%). Middle picks now carry a lottery chance.
- The rise is largest for far-off picks from good teams, because they might be in the lottery by then: the cheapest
  unconditional 2031 first went from 40 to 48, the cheapest 2033 first from 33 to 45.
- Second-round picks move by under a point on average.

### Trades, one hands-off season per seed
The first changed trade changes the rest of a season, so compare totals, not single deals.

| | Seed 20261126 before | after | Seed 20261127 before | after |
|---|---|---|---|---|
| Computer-team trades | 49 | 49 | 56 | 55 |
| Trades that moved a pick | 30 | 35 | 41 | 40 |
| First-round picks moved | 17 | 18 | 21 | 16 |
| Second-round picks moved | 47 | 51 | 52 | 50 |
| Swap rights moved | 5 | 3 | 4 | 8 |
| Players moved | 91 | 90 | 97 | 93 |
| New protections | none | top-4, top-10 | top-10 | top-4 |
| Season sim time, seconds | 949 | 929 | 900 | 906 |

The odd-trade checker from the recent trade-AI work, both seeds added together. These are broad flags that include
minor players, not confirmed bad trades:

| Flag | Before | After |
|---|---|---|
| First-round right given for a player who then played under 15 minutes | 2 | 2 |
| Player given away for nothing | 1 | 1 |
| Player out 30+ days acquired | 6 | 8 |
| Team that won 2+ playoff rounds sent out any player | 5 | 8 |

Two seasons are too few to say whether the last two rows moved because of the new values or because the seasons
played out differently.

Two deals a fan might question in the "after" seasons:
- Cleveland (out in round two) sent Jarrett Allen and a 2030 first-round swap right for Cam Spencer. The recent
  champion-core rule does not cover a team that won one series. Re-judged on the June 30 save, Cleveland rejects it
  with old values (-14.1) and new ones (-12.9); it passed on July 1, after other moves, as a close call the computer
  teams allow (-2.3, they accept down to -9). The new values make this swap right about 1 point cheaper. This is a
  trade-AI weakness worth its own look.
- Cleveland (two rounds won) sent James Harden, 37, and a swap right to Chicago in a three-team deal for Norman Powell.

### Not changed
- Protected picks and swap rights were still priced the old way after the first pass; the second pass changed that.
- Draft room screens (a separate screen pass). Saved lottery results and drawn picks are valued as before.
- The 2026 draft keeps the old pricing.

### Checks
- 641 focused trade, pick and draft tests and the browser-script tests pass. New: `tests/test_pick_lottery_value.py`,
  three protection tests in `tests/test_trade_pick_terms.py`, one in `tests/trade_pick_terms.test.cjs`.
- One older test used "picks 8-14" as its example of a valid condition; it now uses "picks 8-11".
- Recalculating all pick values takes 2.6 ms instead of 1.9 ms.
- Computer-team decisions change by design, so seeded seasons differ from before.
- Full suite on a cloud machine (`run_tests_parallel.py --all --workers 2`): 2,722 tests, 0 failures, 0 errors,
  70 skipped.

## Second pass: protected picks and swap rights (commit c2af00d4)

**What changed in the game**
- *Protected picks* used to lose a fixed share (top-4: 7%, top-10: 18%, top-20: 36%) whoever's pick it was. Now the
  price follows the chance the pick lands inside the range, and counts the replacement pick that conveys instead. A
  light protection on a strong team's pick is close to free; one that will almost surely keep the pick is priced as
  its replacement.
- *Swap rights* used to be worth much the same whichever side held the better pick. Now a right is worth what the
  other pick can add: a lot when its holder's own pick is likely to be worse, almost nothing the other way round.
  "Less favourable pick" obligations mirror it. Chains of swaps held as one pick are priced the same way.
- Both apply from the 2027 draft on. Drafts before that keep the old formulas.

Mid-season test save (3 February 2027), protected picks:

| Pick and protection | Chance it stays home | Before | After |
|---|---|---|---|
| Dallas 2027, top-2 | 13% | 89.1 | 87.4 |
| Miami 2027, top-14 | 8% | 42.2 | 53.8 |
| Clippers 2028, top-16 | 90% | 61.7 | 76.4 |
| Golden State 2030, top-20 | 87% | 48.2 | 69.1 |

- The twelve protected picks in that save average 61.6 before, 66.5 after. Protected second-rounders in a new career
  roughly double (about 9 to 17), because the game always hands over a replacement second.
- Swap right on a first one draft ahead, example teams: strong team taking a weak team's pick 38.6 to 51.3; the
  reverse 38.6 to 0.5; two middle teams 7.8 to 10.7.
- Unprotected picks are unchanged by this pass.

**Trades, one hands-off season per seed** (before = the first pass plus main's coaches work)

| | Seed 20261126 before | after | Seed 20261127 before | after |
|---|---|---|---|---|
| Computer-team trades | 48 | 48 | 53 | 51 |
| Trades that moved a pick | 33 | 38 | 39 | 32 |
| First-round picks moved | 18 | 18 | 15 | 14 |
| Second-round picks moved | 43 | 49 | 57 | 36 |
| Swap rights moved | 2 | 4 | 5 | 5 |
| Players moved | 84 | 91 | 93 | 86 |
| New protections | none | top-4 | none | none |
| Season sim time, seconds | 888 | 884 | 944 | 939 |

Odd-trade checker, both seeds added (broad flags, not confirmed bad trades):

| Flag | Before | After |
|---|---|---|
| First-round right given for a player who then played under 15 minutes | 2 | 2 |
| Player given away for nothing | 1 | 0 |
| Pick moved again within 90 days | 1 | 1 |
| Player out 30+ days acquired | 8 | 7 |
| Team that won 2+ playoff rounds sent out any player | 4 | 13 |

The last row rose. Most of those are bench players and different teams went deep in the "after" seasons, but two
seasons cannot rule out that the new prices let more such deals through. The separate trade-AI task on playoff teams
(branch `claude/great-taussig-7876fd`) works on exactly these deals and should compare on top of this branch.

**Checks (second pass)**
- 690 focused trade, pick, draft and coaching tests pass. Seven new tests, including a check of the new arithmetic
  against every pair of positions.
- One older test (`test_ai_offer_packages_can_create_pick_swap_sweeteners`) failed, found by the trade-AI session: it
  set its two example picks' positions without their forecast finishes, so one looked far better and no swap was
  worth offering. It now sets both; no game code changed for it.
- Full suite on c2af00d4 on a cloud machine: 2,742 tests, 70 skipped, 1 failure (the test above). That test, rerun
  after its fix with the new pick tests, passes; the fix changed no game code.

### Files
New `src/nba_gm_data/pick_lottery_value.py`; `pick_rules.py`, `transactions.py`, `play.py`, two lines in `save.py`
(past draft results reach the pick values) plus its startup protection check, `gui/trade-pick-terms.js`.
Run outputs and comparison scripts: `output/pick-refit/` and `output/odds2/` in this worktree.
