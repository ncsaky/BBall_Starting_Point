# Trade market follow-ups (TRADE-FOLLOWUPS)

_Claude (Opus agent), branch `worktree-agent-a005c209a28cf9621` (from dab88e7). Status: **review** (committed on the
branch, not pushed or merged)._

## TL;DR
- A sale an AI team agrees to now happens that day or is called off with a stated reason: repeated "agreements" went from 10 to 0.
- Young rotation players on rising teams stay off the market. Other teams' pages show your assistant GM's read on their front office.
- Summer talks now carry over from day to day. No hidden front-office number affects trades any more. Trade volume is about the same (101 vs 107 trades; the run-to-run spread is wider than that).

## Objective
The five follow-ups from TRADE-MARKET (`trade-market.md`, "What's left"; plan `trade-market-personality-plan.md`).
Textbook acceptance rules unchanged (user decision); no random rolls; every TRADE-DEADLINE and TRADE-MARKET guard and
LeBron's fixed exception kept.

## The fixes, with evidence

### 1. An agreed sale is executed once, or cancelled with its reason
**Why Josh Hart was "sold" seven times.** The base run of this branch showed the same pattern: Donte DiVincenzo was
"sold" from Minnesota to Washington on 6 market days, and Dejounte Murray from New Orleans to Minnesota on 5. Three
things let an agreed sale slip:
- **The day's room.** A single-bidder sale kept its place in the search order. When the day had fewer trade slots
  than agreed deals, the review cut it. The ledger still recorded it as agreed. This is what happened to DiVincenzo:
  on the replayed 2027 deadline week, the sale now goes first and completes on 2027-01-30, the first day it is
  agreed. In the base run it was "agreed" on 01-30, 02-02 and 02-03 and only executed on 02-05.
- **The end of the search.** Bidding wars are settled after every other pairing. If the search limit was already
  reached, or the winner's package overlapped a deal already made that day, the code skipped the trade. The war was
  still marked "sold".
- **The final check.** Once a deal was marked agreed, the final check before execution stopped counting the
  concession that had closed the talks. A buyer that agreed thanks to that concession could then fail the check.

**What happens now** (`trade_market.py`, `transactions.py`, and the trade-market hooks in `save.py` and `play.py`):
- Market deals go first in the day's deals: shopped players' sales and the end of multi-day talks. They are tagged so
  the rest of the day can follow them.
- The review records as agreed only the deals it will execute today. A sale it has no room for stays on the market
  with the reason "no room for another trade today; the seller decides again on the next market day". It is never
  recorded as a sale. A war winner whose package overlaps another deal is held the same way.
- The final check still sees the concession the two sides agreed with.
- The step that applies a trade now records its answer in the ledger:
  - If the trade goes through, the sale is marked sold.
  - If the final check refuses it, the sale is cancelled with the check's reason in plain words, for example "a team
    reconsidered the deal against its current roster (BOS: Draft-asset overpayment is not justified by this roster's
    benefits.)". That negotiation ends, and the buyer walks away for 30 days. It can come back only on a real change,
    as before. Other teams can still bid for the player.
  - An agreement still open the next market day is cancelled as "not completed".

**Results (two-season test, base run versus final run):**

| | Base | Final |
|---|---:|---:|
| Repeated agreements (same buyer, same sale) | 10 | **0** |
| Agreed sales never executed | 14 | **0** |
| Agreed deals cancelled at the final check | (not recorded) | 1 |

The one cancellation: Boston's deadline-day deal for Jay Huff. Boston's roster had changed with an earlier deal that
day, so its pick-spending check refused.

### 2. The young-starter guard covers young players in a real rotation role
Rising Memphis sold Javon Small for two seconds. On this branch's 2027 deadline save he is 23, plays 20 projected
minutes, is Memphis's second-best player on the court and has a trade value of 81. He was under both old bars: 24
minutes and 65 on-court value.

The new rule (`trade_targets.young_rotation_piece`) keeps a player off the market when he is 25 or younger and passes
two tests:
- **Role:** 15 or more projected minutes, or among his team's 8 players with the most minutes (with at least 10).
- **Value:** one of his team's 6 best players on the court, or a trade value of 70 or more (age and upside included).
  On a rising team, whose young rotation is its timeline, the bar is one of its 8 best or a trade value of 65.

As before, the team can still move him with a reason of its own (a listing, a blocked prospect, stalled contract
talks), or as part of its own offer for a target. Money reasons alone never expose him. The tax term that refuses
to sell young pieces for tax savings uses the same rule.

How the rule was set:
- On the 2027 deadline save, the first version newly protected 9 players: Javon Small, Jaylin Williams, Kyle
  Filipowski, Cam Whitmore and others.
- The first branch run still had rising Utah sell Filipowski (23, 16 minutes, trade value just under 70) for one
  second. That is why rising teams got the wider bar.

Results:
- Young players sold by a team that "had no plan to move him": 7 in the base run, 2 in the final run. Both were
  bench players with about 13 projected minutes (Dylan Faulkner, Tre Donaldson), below the role bar.
- Young starters (24+ minutes) moved: 0.

### 3. Front-office hints on team pages
- Another team's page (its dashboard) now has a **Front Office** button next to My Team. It opens your assistant GM's
  read on that office.
- The words come from the same source as the trade window and the Trade Market board (`office_hints`):
  - with no dealings, only its widely held reputation;
  - after a first dealing, a rough read of every trait;
  - after three, the full description.
- No numbers are shown. The button's tooltip shows the read's first line.
- Rule 4: the words now also cover the two new uses of the traits:
  - urgency: "...and goes after playoff-level starters";
  - patience: "patient in negotiations and with its core".
  The money habits now mention the owner.
- Checked in the running app at 1024 wide, on San Antonio's page:
  `output/trade-followups/screens/team_page_front_office_sas.jpg`.
- The read reaches the page through both routes that build a team page: the dashboard snapshot (normal play) and
  the plain team dashboard.

### 4. Multi-day talks on summer market days
- The free-agency days, the late-summer market and the September camp markets now keep the same negotiation ledger as
  the season (`trade_market.begin_market_day`):
  - stale records are closed;
  - the day's talks, shopping and bids are recorded;
  - deals agreed but not tried are released back into talks (`release_agreements`).
- A seller whose decision day falls between two summer market days decides at the next one, instead of letting the
  sale lapse.
- Two hooks in `play.py` call it: `free_agency_general_trade_candidates` and `run_summer_ai_market`.
- Result: summer trades closed after two or more days of talks went from 0 to 6 of 28. Summer volume is unchanged:
  July 6 and 11 trades in both runs, August to October 4 and 7. The July slots, not the talks, set how many trades
  happen.
- **Draft night is not included.** Draft-night trades are pick trades decided during the draft by a separate engine.
  They happen over one evening, so there is no next day to continue talks on.

### 5. Hidden front-office fields retired from trade decisions (rule 4)
The old profile fields were flavour values: six hand-set teams marked "not real personnel claims", plus offsets
from a hash of each team's name. None of them was ever shown. What they did, and what happens now:

| Old hidden field | What it moved | Now |
|---|---|---|
| asset discipline, competence, owner pressure | each team's acceptance margin (about +-2 points) | the same margin for every team (1.5) |
| star chasing, owner pressure (through the team's "pressure") | the extra eagerness for an incoming star | visible urgency (above 65); the "chases star names" habit stays its own stated term |
| owner pressure | whether a contender also hunts a playoff-level starter | visible urgency of 75+ ("very aggressive", whose words now say so) |
| financial discipline | the owner money factor, 0.7 to 1.4: tax pricing in trades and the owner's tax budget in free agency | the visible money habits: 1.25 for "works hard to stay under the luxury tax", 0.8 for "will pay the luxury tax to win", 1.0 otherwise |
| old patience | how many failed playoff runs before a team reviews its core | visible patience: 58+ gives three, whose words now say so |

- Taxpayers at season end: 10 and 14 in the base run, 11 and 13 in the final run (real 6 to 8). The problem is
  unchanged, and this change did not worsen it.
- **Still hidden, outside trades:** the free-agency contract AI (competence, aggressiveness, star chasing, financial
  discipline in bids), staff hiring (owner pressure, financial discipline) and team morale (pressure). These are in
  FA-REAL's area (see "What's left").

### Also fixed
Free-agency trades stated their personality twice. They went through `with_market_reasons` in the search and again
in the free-agency hook (15 trades in the base run). They now state it once.

## Before and after by window
Two-season test: `scripts/two_season_league_probe.py`, seed 17, Golden State hands-off, 2026-10-20 to 2028-11-01.
- **Run 4:** the TRADE-MARKET final run, on older code.
- **Base:** this branch's start (dab88e7), with the trade-eligible dates and free-agency slice 1 merged after run 4.
- **Run 1:** this branch before the rising-team widening of the guard and the once-only reasons fix.
- **Final:** this branch.

| Window | Run 4 | Base | Run 1 | **Final** | Real |
|---|---:|---:|---:|---:|---:|
| Deadline week 2027 | 29 | 21 | 19 | **18** | 23-28 |
| ... deadline day | 15 | 7 | 7 | 7 | 18 |
| Deadline week 2028 | 18 | 28 | 25 | **26** | 23-28 |
| ... deadline day | 6 | 15 | 11 | 12 | 18 |
| Draft 2027 / 2028 | 8 / 7 | 9 / 8 | 8 / 7 | 8 / 8 | 8-11 |
| July 2027 / 2028 | 8 / 13 | 6 / 11 | 6 / 11 | 6 / 11 | 16 and 8 |
| August-October 2027 / 2028 | 4 / 5 | 4 / 7 | 4 / 7 | 4 / 7 | about 5 |
| In season, October-January | 12 | 13 | 12 | 13 | about 1 a season |
| **Total** | 104 | 107 | 99 | **101** | 110-140 |

**The deadline did not get busier.** The same code gives very different deadlines on different paths: run 4 had 29
and 18, the base 21 and 28.
- On the replayed 2027 deadline week (the same saved league from 2027-01-21), the branch made 23 trades, exactly as
  many per day as the base: the day's trade slots bound every day but deadline day.
- On the replayed 2028 month (from 2028-01-02), it made 28 against the base's 28.
- So the fixes changed which deals close (sales first, no bad young sales), not how many.
- Deadline day itself is still limited by supply (7 and 12 against a real 18), as TRADE-MARKET found. Summer talks
  could not help it: they end weeks before the deadline.

**Other measures (base, then final):**
- Bidding wars: 1, then 6 (two each in-season and on free-agency days, plus one on July 1 and one on July 2; largest:
  Dash Daniels, 6 bidders).
- Trades closed after a bidding war: 7, then 6.
- Trades closed on a final offer: 22, then 19. Final offers refused: 35, then 42.
- Days of talks per trade: 1 day 85 then 78; 2 days 15 then 17; 3 days 6 then 6; 5 days 1 then 0.
- Grade gaps, with the textbook model as the analyst and 10 points to a letter grade:
  - a full letter or more: 41.5%, then 37.2% (real 59%);
  - 1.5 letters or more: 22.3%, then 20.9% (real 21%).
- Lopsided trades explained by a stated trait: 10 of 21, then 8 of 18.
- Both teams' reasons stated: 107 of 107, then 101 of 101.
- Three-team trades: 13, then 15.
- Players traded twice: 26, then 25. Traded three times: 3, then 0.
- Star-for-star swaps: 0, then 0.
- Rebuilding teams buying a 30+ veteran on $15M+ over 2+ years: 1, then 1 (salary filler, as in TRADE-MARKET).
- LeBron untouched.

## Hand-read trades
I read 22 final-run trades: every multi-day, bidding-war and July trade. Five of them:
1. **Good.** Contending Cleveland gets Donte DiVincenzo from rebuilding Washington at the 2027 deadline. Cleveland
   gives Jaxson Robinson, Thomas Bryant, Nae'Qwan Tomlin and its 2030 first. It beat one other bidder. This is a
   contender buying a proven guard from a seller for youth and a first. In the base run this sale was "agreed" six
   times before going through.
2. **Good.** Contending Minnesota gets Michael Porter Jr. from rebuilding Brooklyn on 2028-02-02 for Jalen Wilson,
   Ayo Dosunmu (salary) and its 2030 first. It came after two days of talks, and Minnesota won a bidding war against
   Dallas. A textbook deadline deal.
3. **Good.** Contending Los Angeles gets Ty Jerome from rebuilding Memphis on July 1, 2027 for Cameron Carr (22) and a
   2028 first. Four teams bid over two rounds; the Lakers "spend draft picks freely" (a stated habit). An analyst would
   grade Memphis's side well.
4. **Borderline.** Rising Memphis sends GG Jackson (22, out of its rotation) to rebuilding New Orleans for a 2032 second
   after three days of talks. Jackson is a blocked prospect, which allows the sale. New Orleans "spends draft picks
   freely". It is a cheap flier both ways.
5. **Questionable.** Contending Oklahoma City sends Dash Daniels (21, 8 minutes) to Miami for a 2034 second in July 2027.
   Six teams bid, but Oklahoma City's price was near zero: it is a taxpayer, so shedding his $3.1M saves tax, and he
   is a blocked young player. With six bidders, a real seller would get more. The war only lets a rival raise when it
   beats the leading offer by a point on the seller's own scale, and nobody could beat a price that low.

The other 17:
- Fine: Max Strus to Utah after three days of talks; Moritz Wagner to the Lakers; Jordan Walsh to Milwaukee (Boston
  under the tax, a stated habit); Robert Williams III to Memphis; Josh Hart to San Antonio on July 1 for Tobias
  Harris's salary and two seconds (New York's Villanova tie stated); Daniel Gafford to Milwaukee; Paul Reed to
  Orlando.
- Good for the seller: Collin Gillespie to Houston for Quadir Copeland, Steven Adams and two firsts, after three days
  of talks.
- Borderline: Cam Spencer to Toronto (Toronto "spends draft picks freely"); Dylan Faulkner (13 minutes) to
  Washington for Justin Champagnie, below the guard's role bar.
- Questionable: Hugo Gonzalez (21) from Boston to Washington for a second. It is Boston's tax habit plus its scouts'
  low opinion of him, both stated.

## Speed (CPU seconds, whole two-season run; the laptop was shared and crashed once from overload)

| | Base | Run 1 | Final |
|---|---:|---:|---:|
| Whole run | 1,429 | 1,468 | 1,357 |
| Normal season months | 660 | 631 | 601 |
| Deadline steps | 139 | 129 | 117 |
| Free-agency days | 242 | 270 | 241 |
| Draft | 107 | 123 | 117 |

- Normal days are not slower.
- Summer days cost about the same. Run 1's free agency was 12% slower and the final run's was not, which fits the
  noise on this machine.
- The team-page read is built only when you open another team's page.

## Tests
- New `tests/test_trade_followups.py` (19 tests):
  - a sale cancelled at the final check: its reason, the buyer walking away, and no re-agreement the next day while
    other teams can still bid;
  - a completed sale sold once; a sale with no room held, not agreed;
  - a never-completed agreement cancelled the next day;
  - the apply step reporting back; the final check keeping the agreed concession; unused agreements released;
  - summer talks continuing across market days, and summer decision days kept rather than lapsed;
  - the young-rotation guard, including the rising-team bar;
  - the same margin for every team; the money factor from visible habits; star hunting from visible urgency;
  - personality stated once; the team-page read matching the trade-window read.
- New `tests/team_front_office_read.test.cjs` (2 tests): the button, the modal, no numbers.
- `bash scripts/run_core_tests.sh`: 338 OK, 2 skipped.
- Trade modules (`test_trade*`, `test_multi_team*`, `test_keep_stars`, `test_roster_space`,
  `test_summer_trade_reviews`): 367 OK, 1 skipped.
- `tests/*.test.cjs`: 38 of 39 pass. `startup_video.test.cjs` needs the ignored movie file, as on main.
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18** (trades do not
  change game results).
- **Determinism:** no new random draws. Outcomes change by design: sales go first, young rotation players are kept,
  the acceptance margin and money factor come from the visible traits.

## What's left
- **The deadline is still short on deadline day** (7 and 12 against a real 18). Deadline week depends heavily on
  the path a season takes (run 4: 29 and 18; base: 21 and 28; final: 18 and 26). In the replays, the slots bound the
  other days of deadline week and supply bound deadline day. Raising supply needs a textbook decision from the user.
- **Hidden front-office fields outside trades.** The free-agency contract AI still uses the old competence,
  aggressiveness, star-chasing and financial-discipline fields in its bids. Staff hiring and team morale use owner
  pressure. These are in FA-REAL's area, so I did not change them. The free-agency owner budget (`payroll_plan`) now
  uses the visible money habits.
- **Bidding wars on cheap players** (the Dash Daniels case). A war can end at the seller's very low price, because
  rivals only raise to beat the leading offer on the seller's own scale. A rule that a war's winner pays at least the
  second-best bid's value to the buyer would be closer to a real auction. That changes prices, so it is the user's
  call.
- Draft-night pick trades do not use the ledger (one evening, a separate engine).
- `.claude/launch.json` lives in the shared checkout, so the app check ran a server from this worktree by hand on
  port 8773.

## Resume state
- Probes: `output/trade-followups/{base,v1,v2}-src/output/probe` (v2 is final; base and v1 keep snapshots).
- Metrics and trade lists: `output/trade-followups/results/trade_metrics_<label>.json`, `trades_<label>.json`.
  Comparison: `output/trade-followups/compare.py run4 base v1 v2`.
- Replays: `output/trade-followups/advance_eval.py` (`--jump`); summaries `output/trade-followups/work/*_summary.json`.
