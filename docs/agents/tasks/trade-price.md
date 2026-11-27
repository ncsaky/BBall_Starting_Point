# TRADE-PRICE: cheap star sales and the Brunson trade

Progress: 9/9 - both rules built and tested; one follow-up fix waits for your OK

Owner: Claude (side session, worktree `festive-chaplygin-aacfb6`, branch `claude/festive-chaplygin-aacfb6`).

## Report

**TL;DR**
- Both rules are built (your OK, 2026-11-27). A computer team now needs a real return for a star, and will not add a
  pick to get rid of a core player. The Brunson deal is refused.
- Two fresh two-season test runs made 201 trades against 188 without the rules: no drop in volume. The full test
  suite passes (2,763 tests, 0 failures, 80 skipped).
- One gap showed up: a much lesser player can count as "comparable" for a young star. A fix needs your OK (section 5).

Everything here was measured on `main`. The earlier branch (`claude/vigilant-cori-6ae562`: injury rule and champion
promise) is not merged yet; this branch merges with it without conflicts, but the two have not been tested together.

## 1. Offer tests: what is believable

The test: on July 1 (2027 and 2028, two saved test runs) the user's Brooklyn asks each computer team for its three best
players. Teams under an injury review are left out.

I first repeated the earlier test (182 of 282 sold; it reported 181), then fixed two flaws in it:
- In 41 of those sales the "matching salary" was a Brooklyn rookie the seller valued above the pick itself. I now add
  the cheapest salary that makes the trade legal.
- Many two- and three-pick offers broke the back-to-back first-round pick rule, so higher prices were never tried.

**Corrected result: 175 of 282 sold, 145 for one pick and 30 for two.**

| Who was sold | Asked | Sold | For one pick | Verdict |
|---|---|---|---|---|
| Young cornerstones (25 or younger, priced as a franchise piece) | 55 | 33 | 15 | Not believable |
| Stars in their prime (league's 30 best, up to 33) | 53 | 15 | 10 | Not believable |
| Stars 34 and older | 9 | 5 | 5 | Mostly fair; Curry is not |
| A team's best player, outside the top 30 | 32 | 23 | 22 | Mixed |
| Other second and third options | 133 | 99 | 93 | Mostly fair (a top pick for a good non-star) |

Examples:
- **Cooper Flagg** (20-21) from Dallas: one pick in one summer, two picks in the others.
- **Nikola Jokic** (33) from Denver: two picks.
- **Tyrese Haliburton** (27) from Indiana: one pick in 2027.
- **Giannis Antetokounmpo** (32) from Miami: one pick.
- **Jayson Tatum** (30) from Boston, **Jaren Jackson Jr.** from Utah: one pick.
- **Stephen Curry** (39) from Golden State: one pick; Golden State had itself marked him to move.
- **Anthony Edwards** and **Devin Booker** went for one pick in summers where the game rates them outside the top 30.
  A fan would balk, but that follows their ratings, which stay as they are.

### Why
1. **The price scale.** The pick offered is Brooklyn's own, projected about 6th, worth 95 to 108 points. Typical prices
   for players aged 26 to 32:

   | On-court rating | 64-68 | 68-72 | 72-76 | 76 and up |
   |---|---|---|---|---|
   | Price in points | 67 | 74 | 82 | 95 |

   So one such pick costs as much as a top-handful player. The one pick alone covers 134% of the seller's price in the
   typical one-pick sale.
2. **Rebuilding and rising teams count picks twice over.** They multiply a pick by 1.18 and then add another 14%
   (1.35 times in all: about 127 to 140 points). This includes teams "on the rise", which should want players. It is a
   real flaw but not the main one: without it, 119 of the 145 one-pick sales would still happen.
3. **The seller's attachment is small** (about 7 points in the typical sale, against a surplus of about 60).
4. **The minimum-return rule rarely applies** (`premium_return_issue`). Of the 175 sales:

   | Why the rule did not stop it | Sales |
   |---|---|
   | Team not competitive and player rated under 76.5 | 134 |
   | Competitive team, player rated under 68 | 28 |
   | Rule applied, but a single great pick satisfies it (non-competitive or reviewing teams) | 11 |
   | Player under 24 minutes | 2 |

   Only three or four computer-team players per summer clear 76.5 (with the playoff bar that goes with it), so a
   rebuilding team's young star has no protection at all.

## 2. The Brunson trade: not believable

July 2, 2027: New York sends Jalen Brunson **and a second-round pick** (2034) to Memphis for Cam Spencer. New York said
yes to a version of this deal in three of four test runs, two of them under today's `main` rules. It was completed in
one (a run with the unmerged injury rule).

| Term | What it did |
|---|---|
| Market price | Brunson 71, Spencer about 69-71. Brunson rates 68 on court to Spencer's 61-63, but Spencer earns $2.6M to Brunson's $40.5M, and the cheap contract closes the gap |
| Luxury tax | **Decides it.** The saving was worth +31 points to New York. Without it New York refuses all three versions |
| Retool listing | Puts Brunson up for offers and halves New York's attachment (about 5 points). Not decisive: in two versions another player was the marked one |
| Tax guard for core players | Did not apply: it covers only contenders and teams fresh off a playoff series win |
| Minimum-return rule | Did not apply: New York not competitive, Brunson rated under 76.5 |
| The pick | Memphis only agrees because of it |

The retool listing was the suspected cause. The main cause is the tax saving.

## 3. The two rules (built)

Both rules only refuse trades; neither makes any trade easier. Textbook trade rules, ratings, pick values and LeBron's
exception are untouched. They apply to computer trades and to your offers.

**Rule A: a star needs a real return.** A computer team trades a star only for a comparable player, a strong young
centerpiece, or three first-round picks.
- Star: one of the league's 30 best on court, or 25 or younger and priced 80 or more.
- Not covered: players 34 and older, very costly contracts, high injury risk.
- Offer test: 47 of the 48 sales of young or prime stars now cost three picks (today one or two; the other also brings
  back a young player). One-pick sales fall from 145 to 120.

**Rule B: no paying to get rid of a core player.** A computer team does not add its own pick when it sends away one of
its three best players (rated 62 or better, under 34, not a costly contract or injury risk), unless a comparable player,
a young centerpiece or a first-round pick comes back.
- Refuses all three versions of the Brunson deal. Memphis will not do it without the pick.

### Estimate of the effect on trade volume (made before building)
A look back at 333 completed computer trades in four two-season test runs (32 three-team trades not judged):

| | Trades refused | |
|---|---|---|
| Rule A | 5 | |
| Rule B | 2 | |
| **Both** | **7 (about 2%, one or two per two-season run)** | recommended |

The seven:
- Good to stop: New York's Brunson deal; the Lakers giving up Austin Reaves for three lesser players and one first;
  Indiana giving up 23-year-old Dereck Lively II for a reserve and two seconds.
- Arguable: Denver paying a pick to swap 33-year-old Aaron Gordon for Neemias Queta.
- **Believable deals lost:** three versions of Golden State trading Kristaps Porzingis (32) for one first plus players
  or picks. Starting the age exemption at 32 would free them, but also lets Giannis go for one pick again.

### Options I tested and do not recommend now
| Option | Computer trades refused (of 333) | Why not |
|---|---|---|
| No tax credit when any team's top-three player leaves | 12 | Also stops Brunson, but mostly hits ordinary salary moves |
| Minimum return for every top-three player | 17 | Too broad |
| Rising teams price picks like everyone else | 27 | Raises only 11 of 145 one-pick offers to two; no change for prime stars |
| Drop the second 14% pick bonus | 37 | Raises 17; no change for prime stars |

### As built
`trade_stars.py`, called from `transactions.premium_return_issue`, so computer trades and your offers both go through
it. Four details go slightly beyond the description above:
- Two departing stars each need a return of their own.
- A pick so heavily protected that it is worth almost nothing does not count as a first.
- Nobody rated below 62 is a star by rank. In real leagues the 30th-best rates about 69 to 70, so this only matters in
  tiny test leagues (it fixed 10 failing tests).
- An injured star needs the full return unless his injury risk is high, even where the unmerged injury rule would let
  him go for less.

A refused offer says why: "... is a star: it takes a comparable player, a top young player or three first-round picks."
or "The team will not add a pick to give away ..., one of its three best players."

## 4. After building

### Offer tests and the Brunson deal
The built game gives exactly the prototype's answers on all the offers. All three versions of the Brunson deal are
refused.

### Two fresh two-season test runs (same seeds as the runs without the rules)
| Trades | First run, without | First run, with | Second run, without | Second run, with |
|---|---|---|---|---|
| 2026-27 season | 20 | 23 | 23 | 22 |
| Summer 2027 | 23 | 26 | 30 | 28 |
| 2027-28 season | 22 | 28 | 22 | 23 |
| Summer 2028 | 27 | 30 | 21 | 21 |
| All | 92 | 107 | 96 | 94 |

- The histories split early (November and December 2026), so differences of this size are mostly chance. The runs show
  no loss of volume; they do not show a gain.
- Computer trades sending out a star: 3 without the rules (two Porzingis deals, Dereck Lively II), 1 with them.
- Trades sending out a non-star from a team's top three: more with the rules (28) than without (21). The rules do not
  stop those unless a pick is added; most are modest swaps.
- No crashes. The Brunson-for-Spencer deal did not happen in either new run.

## 5. The gap: what counts as "comparable"
"Comparable" looks only at ratings (within 4 points on court, 8 in the playoffs). A young star is often rated like a
backup but priced far above one.
- In the second new run, Denver sent 23-year-old Alex Condon (a star by price, rated 62) to Minnesota for D'Angelo
  Russell (30, rated 58), a deep reserve, a first and a second. The rule let it through because Russell counts as
  comparable.
- In offer tests, 11 of 207 stars could be bought with one pick plus a player priced under 80% of the star.

**Proposed:** a comparable player must also be priced at least 80% of the star. Not built or measured over seasons.

Also seen, and allowed by design: Denver added two picks to swap Aaron Gordon for Keegan Murray. Gordon's rating
slipped from 63 to 61 that summer, under rule B's floor of 62.

## 6. Still not solved
- Curry, 39 and marked by his own team, still costs one pick. That is a "legends keep jobs" rule of its own.
- Good players rated outside the top 30 still go for one top pick.
- A good player with a low summer minutes projection is priced like a reserve (Donovan Clingan: rated 74, priced 44 with
  21 minutes).

## Limits
- Two seeds only. The look-back estimate counts only lost trades; the season runs are the measure of what the market
  does instead.
- Pick-price options can also allow new trades; the look-back counts only lost ones.
- The offer test judges only the selling team, uses one very good set of picks, and asks for one player at a time.
- "Comparable player" and "young centerpiece" are the definitions the current minimum-return rule already uses.
- Two July summers from two seeds. Later drafts are made-up players. Nothing was checked on screen, and the browser
  tests were not run (no screen code changed; the refusal text uses the existing trade answer line).

## Files
Scripts and results are in this worktree's `output/trade-price/` (git-ignored): `tools/offer_terms_probe.py` (offer
test with every pricing term; `VARIANT=` applies a prototype, on code from before the rules were built),
`compare_runs.py`, `comparable_gap_probe.py`, `analyze_terms.py`, `compare_variants.py`,
`candidate_rules.py` (the prototypes), `trade_log_estimate.py` (volume look-back), `brunson_replay.py`. Saved test
seasons come from `.claude/worktrees/vigilant-cori-6ae562/output/core-renew/`.

Game code: `src/nba_gm_data/trade_stars.py` (new), `transactions.premium_return_issue`,
`tests/test_star_returns.py`. New test runs are in `output/trade-price/run-26` and `run-27`.
