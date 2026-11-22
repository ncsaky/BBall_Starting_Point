# CONTRACT-TERMS: contract history, salary paths and options, option decisions

_Claude (Opus agent), worktree branch `worktree-agent-a467c2ea2e59eaa25`. Status: **in progress** (measurement)._

## TL;DR
- **The Podziemski bug is fixed at the source.** The salary tables the league is built from list only the years a
  contract still has left, so 497 real contracts looked like fresh one- or two-year deals and the extension rules
  refused them. Each real contract's signing season and length is now rebuilt from evidence (the draft, reported
  signings, last season's salary table); where nothing says when a deal was signed, the length is stored as unknown
  and the screen says so. League-wide, players who can extend on day one went from **4 to 116**.
- **Extensions follow the league's rules:** rookie-scale deals in the summer before year four (until the day before
  opening night); other deals of three or more seasons from the second anniversary (third for five- and six-year
  deals), five seasons at most including the current one, first year at most 140% of his salary or the average
  salary. The Set The Roster list and the extension screen now use one rule, so a listed player is never refused.
- **Offers have a shape:** free-agent offers, re-signings and extensions pick a salary path (rising, flat, declining)
  and an option on the last season (none, player, team). Salaries are saved year by year; players value earlier money
  and player options, and the "Will he sign?" box says how the shape changes his answer. AI deals use the real shares.
- **Option decisions are visible:** an Option Decisions card in the offseason checklist (the player's own choice with
  his reason; your team options with Keep / Decline), phone messages, and notable decisions on the league wire.

(Results of the two-season probe and the scorecards: see "Measurements"; filled in when the runs finish.)

## Resume state
- Committed on the branch: part 1 (eb15bb6), parts 2-3 (d34ec3b), browser tests + probe (f82edf6), AI extension
  guards (03ecaec).
- Running on the Azure worker (one at a time): `contract-terms-branch` (two-season probe of this branch,
  output/ct-probe-branch), `contract-terms-base` (same probe on main 5c5f19a from output/contract-terms/basetree,
  output/ct-probe-base), `contract-terms-scorecards` (real-stat 1,230-game replay and odds 20 runs x seeds 1001/2001,
  output/ct-scorecards). Logs in output/contract-terms/azure_*.log.
- GUI server for screenshots: port 8771 from this worktree (save dir output/contract-terms/gui_saves).
- Left: parallel focused tests (waiting for swap), metrics into this report, FA builder and option-card screenshots
  from the probe's copies, board row to review.

## Measurements (2026-11-21 evening)
| Measure | Before (main 5c5f19a probe) | After, first branch probe | After the fix (season passes on the probe's preseason saves) | Real |
|---|---:|---:|---:|---:|
| Rookie-scale extensions 2027-28 | 14* | 5 | 8 | 7-14 a year |
| Veteran extensions 2027-28 | 15 | 7 | 23 | 17-27 a league year |
| Rookie-scale extensions 2028-29 | 11* | 6 | 6 (threshold since lowered 60 -> 55; Demin next at 57.8) | 7-14 |
| Veteran extensions 2028-29 | 13 | 2 | 18 | 17-27 |
| Player options kept (both summers) | 29 of 50 | 29 of 53 | rule replaced (evidence), re-probe pending | 93 of 177 (53%) |
| Veteran team options kept | 31 of 39 | 30 of 42 | rule replaced (evidence), re-probe pending | 89 of 186 (48%) |
| Rookie-scale options kept | 117 of 128 | 142 of 153 | unchanged | 421 of 471 (89%) |
| Real-stat scorecard | 18/18 | 18/18 | - | |
| Betting odds, Brier (seeds 1001 / 2001) | .2041 / .1972 | .2041 / .1972 | - | |

\* main counted "rookie-scale" as any extension of a player 25 or younger.

Cause of the collapse (funnel on the 2027 preseason save, 100 eligible veterans): the pay-cut guard stopped 23 (the
contract model prices players under contract about 1.45x below their real deals, so teams never met a star's bar);
33 decisions due in January fell after the last monthly pass (an old timing gap, also on main); rookie-scale players
with priority under 78 had no later checkpoint before the October deadline. Fixes: teams meet the bar when it is within
1.45x the model price; each monthly pass handles what is due before the next; rookie-scale appetite 55 (about 40% of
eligible players, real 41 of 96); ceilings per kind at the top of the real range (14 and 27). CBA rules unchanged.

Option rules and AI shapes now from CONTRACT-STRUCTURE-EVIDENCE: player opts out after 1,000+ minutes (held-out 28 of
41); team keeps at 130% of the option or 105% for a 500-minute player (54 of 85); AI shapes by kind of deal (exception,
Bird, max, extension, two-year minimum). The player's option weights (1.2 / 0.6) stay assumptions: the evidence counts
options, it does not price them.

Pending: branch probe 2 on the Azure worker (`contract-terms-branch2`, output/ct-probe-branch), then the focused tests
and core suite when the laptop has room. Screenshots: output/contract-terms/screens (stop 1 option card + offer builder
with flat path and player option; extension page with rising path and team option; Podziemski).

## Measurements, round 3 (2026-11-21 night)
Second branch probe (`contract-terms-branch2`) against main and real, then the fixes in 9b6f9d8 measured by replaying
each season's extension passes and option decisions on that probe's own saves (a third probe is queued):

| Measure | Main | Probe 2 | After 9b6f9d8 (on probe 2's saves) | Real |
|---|---:|---:|---:|---:|
| Rookie-scale extensions 2027-28 / 2028-29 | 14* / 11* | 10 / 8 | 9 / 8 | 7-14 |
| Veteran extensions 2027-28 / 2028-29 | 15 / 13 | 27 / 8 | 27 (ceiling) / 18 | 17-27 |
| Player options declined (both summers) | 21 of 50 | 45 of 59 (76%) | 26 of 59 (44%) | 84 of 177 (47%) |
| AI team options kept (both summers) | 31 of 39 | 31 of 38 (82%) | 19 of 38 (50%) | 89 of 186 (48%) |
| Rookie-scale options kept | 117 of 128 | 137 of 147 | unchanged | 421 of 471 (89%) |

Causes and fixes: the 2028-29 veteran drop came from AI negotiations that start at the model's low price (Mobley
offered $30-34M against a $57.5M salary, so he walks); such talks now end with the team offering his ask or his
no-pay-cut bar when that is within 1.45x his model price, and the veteran appetite threshold is 50 (was 78). The
1,000-minute opt-out rule alone fires for nearly every option holder (they are mostly regulars), so it now also needs a
market at least 0.8x the option. The evidence's 130%/105% team rule kept nearly everything because the game's market
price for fringe players starts near $5M, far above cheap options; teams now keep a 1,000-minute player worth at least
the option (minutes alone: 49 of 85 right on the evidence's held-out 2025-26 seasons).
