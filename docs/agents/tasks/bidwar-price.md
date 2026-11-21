# Bidding-war price floor and rare lower winners (BIDWAR-PRICE)

_Claude (Opus agent), branch `worktree-agent-a8228294602623cc8` (from 9e493aa). Status: **review** (committed on the
branch, not pushed or merged)._

## TL;DR
- A bidding war's winner now always pays at least what the second-best offer was worth to the seller. Losing bidders can add a pick or a young player of their own to stay in, up to their own limit.
- A slightly lower offer can win only for a strong, lasting reason the seller states. It never happened in two simulated seasons (0 of 6 wars), so it is very rare.
- Base run: 2 of 11 war winners paid less than the runner-up. Now 0 of 6. Trades 98 -> 99, and both teams state their reasons on every trade.

## User decision (2026-11-21)
"The winner should pay at least what the second best bid was worth. Although sometimes it might be interesting if a
slightly lower offer wins. Not sure if that happens in real life... Could be interesting every once in a while. But
rarely."

## The rule (`trade_market.py`)
1. **What a bid is worth.** A bid's price is the seller's textbook value of the deal, measured above its acceptance
   line (`evaluation_price`). The seller's personality terms are taken out: its opinions, its habits and the ground
   it gives in long talks. Before this change, wars were compared on the seller's full evaluation. So a seller
   giving ground to one bidder after days of talks could sell to that bidder over a better offer.
2. **The war is fought on that price.** In each round, every bidder except the leader tries to beat the leader by a
   point.
   - First, as before, the bidder tries its own other built packages.
   - New: if none of them is enough, it adds one more asset of its own to its current offer (`raise_to_floor`). These
     are the same additions a counter-offer can ask for: a pick, a young player, or a player the seller targets.
   - It picks the smallest addition that gets there, and never one that jumps far past it (a first where a second
     would do). The step limit is the same as for counters.
   - The buyer's own full check must accept the raised offer: its value of the player plus its personality premium.
     Otherwise it drops out.
   - This is a real auction: the price climbs until only one bidder is willing to pay. In the base run, rivals could
     raise only with packages built for the seller's asking price. No base war went past its first round: each war
     was in effect one sealed offer per team. That left the 5-team Dash Daniels war ending at about a second-round pick.
3. **The decision** (`SearchMarket.decide`). The best price wins, so the winner pays at least the second-best bid. The
   seller may prefer another bid for a stated, lasting reason (below). In that case:
   - The preferred bidder must first raise its offer to the best price, with the same additions and within its own
     limit. If it can, it wins at that price ("matched").
   - If it cannot, its offer still wins only when it is **slightly lower** and the reason is **strong**:
     - at most 5 points below the best price (about half a second-round pick);
     - one stated reason worth 2 or more points;
     - all its stated reasons together worth at least the gap plus 1 point.
   - Otherwise the seller takes the best price and says whom it passed over and why.
4. **No dice.** Every step is a fixed function of the offers, the seller's traits and its phase.
5. **No textbook acceptance rule changed.** Every bid still passes both teams' unchanged checks.

## The reasons a lower bid can win, with evidence
Each reason is a lasting trait or situation of the seller, never a roll (`seller_preferences`):

| Reason | Where it comes from in the engine | Real evidence |
|---|---|---|
| **A strong opinion about a player in the package** (or a low opinion of one in the rival package) | The seller's player opinions: its scouts' lasting taste and documented connections (the Knicks' Villanova players). Worth 2.5 to 5 points. | 2023: Brooklyn sent Kyrie Irving to Dallas for Spencer Dinwiddie, Dorian Finney-Smith, one first and two seconds. The Lakers' offer had two firsts. ESPN's Wojnarowski reported that the Nets preferred Dallas because it brought a guard and a wing who fit their rotation ([Yahoo/ESPN](https://news.yahoo.com/woj-brooklyn-nets-preferred-dallas-224520408.html), [CBS](https://www.cbssports.com/nba/news/kyrie-irving-trade-nets-declined-strong-offers-from-lakers-clippers-suns-for-all-star-guard-per-reports)). |
| **Tax relief worth more to a tax-averse owner** | The "works hard to stay under the luxury tax" habit, from the office's real reputation. | The same Kyrie deal: the Nets refused to take back Russell Westbrook's $47M salary and the tax that came with it ([RealGM](https://basketball.realgm.com/wiretap-amp/270442/Nets-Were-Unwilling-To-Take-Back-Russell-Westbrook-In-Any-Trade-Scenario-With-Lakers)). In the repo's real-trades file, Boston's 2026 Vucevic deal got C-/C grades, with "tax savings as the main upside" (SI, ESPN). |
| **Prizes draft picks** | The "prizes draft picks" preference. | Repo reputations file (sources listed there). |
| **Fits a rebuilding timeline** (young players and picks) | A rebuilding or retooling seller, scaled by the share of the package that is picks and players 24 or younger (up to 3 points). It counts only between bids, never in an acceptance check. | 2022: Utah sent Donovan Mitchell to Cleveland for unprotected firsts and young players. The Knicks believed their own offer was better ([RealGM](https://basketball.realgm.com/wiretap-amp/268539/Knicks-Believe-Their-Trade-Offer-To-Jazz-For-Donovan-Mitchell-Was-Better-Than-Clevelands), [Hoops Rumors](https://www.hoopsrumors.com/2022/09/details-on-knicks-trade-offers-for-donovan-mitchell.html)). |
| **Won't strengthen a direct conference rival** | A contending or rising seller, with a contending buyer in the same conference (4 points). It counts only between bids. | 2018: San Antonio sent Kawhi Leonard to Toronto, not to the Lakers. Reports said the Spurs preferred the East ([theScore](https://www.thescore.com/nba/news/1561297), [NBC Sports](https://www.nbcsports.com/nba/news/another-report-spurs-will-not-trade-kawhi-leonard-within-west)). Kirk Goldsberry, then a Spurs executive, later said one reason was "we're not here to help our rivals in Los Angeles." |
| A contender's urgency for help now | The visible urgency trait (an existing personality term). | TRADE-MARKET sources. |

A seller's concession in long talks is **not** a reason to prefer a bid. It is about the price, not the package.

## The user's side
- **Trade window.** If your offer for a shopped player is beaten, the seller turns it down in the seller's own terms:
  "HOU's offer for X is worth more to MEM; you'd need to add about a late first-round pick (3 other teams
  interested; decision by ...). Beat it to get him."
  - The gap is put in picks: a little, a second, two seconds, a late first, a first, more than a first. A second is
    about 9.5 points, a late first about 35 and a future first about 43.
  - The same rare exception applies to you: "Your offer is a little below HOU's, but MEM prefers it: MEM has always
    liked Y ...".
  - The partner's counter must reach that price too (`trade_counters.user_counter`).
- **Trade Market board.** The "Your offer" column shows why your offer leads or trails, with the same words. A sold
  player's stage shows the seller's reason on hover ("LAL's offer was worth the most to MEM, more than BOS's.").
- **Rule 4.** The words come from the comparison the seller actually makes (`user_bid_leads`, `user_bid_state`,
  `decision_text`).
- **Trade explanations.** Every war trade's reasons now end with the decision. For example: "BOS won a bidding war
  against OKC (2 rounds). BOS's offer was worth the most to MEM, more than OKC's." Or, for the rare exception: "MEM
  took HOU's offer although DAL's was worth slightly more to it (less than a second-round pick more): MEM has always
  liked ...".

## Before and after
Two-season test: `scripts/two_season_league_probe.py`, seed 17, Golden State hands-off, 2026-10-20 to 2028-11-01.
- **Base:** this branch's start (9e493aa). The only change was recording each bid's price in the war record
  (measurement only).
- **Final:** the new rules (8a7ca9f).
- The last commit (7dc2694) adds the cap on a raise's size. It came after the final run, because the final run had
  Sacramento add a 2034 first where a second would have beaten the leader. I checked the cap on replays of the saved
  league (below). It changes only how big a raise can be.

**Bidding-war prices.** "Price" is the seller's textbook value over its acceptance line.

| | Base | Final |
|---|---:|---:|
| Bidding wars (sold, 2+ bidders) | 11 | 6 |
| Winner paid **less** than the second-best bid | **2** (Ty Jerome: BOS 6.7 vs MIN 8.9; Michael Porter Jr.: MIA -3.8 vs LAL -2.5) | **0** |
| Winner's price over the second-best bid (sorted) | -2.2, -1.4, 0.4, 0.8, 1.4, 3.6, 4.8, 5.1, 6.5, 8.8, 14.0 | 2.3, 3.1, 3.6, 4.2, 16.8, 29.6 |
| Seller's preferred bid matched the best price | n/a | 0 |
| Lower-bid wins | n/a | **0** (also 0 in 8 more wars replayed on 16 saved market days) |
| Wars that went past round 1 (someone raised) | 0 of 11 | 2 of 6 |

- **Why the base winners paid less.** In both cases the winner's offer looked better to the seller only through its
  personality terms. For Porter, the extra came from talks with Miami.
- **Lower-bid wins.** In every war in the final run and the replays, the seller's stated preferences differed between
  bids by at most about 1.4 points. That is below the 2-point "strong reason" bar. The opinion that does reach it
  (Memphis on Mitchell Robinson) was on the winning offer, which also had the best price.
- **Rarity.** The rule exists and is tested, but under these settings it will fire well under 1 war in 10. If you
  want to see it more often, the lever is the size of the slight gap (now 5 points).
- **Fewer wars in the final run (6 against 11).** The two runs are identical through the 2027 deadline: 2 wars each,
  the same 23 deadline-week trades. They diverge after the 2027 draft. The players shopped are about the same (92/143
  base, 92/140 final), so this is path variation, not the rule. A war still ends in a trade either way.

**Trades by window** (per season: 2026-27 / 2027-28 / 2028-29 to November 1):

| Window | Base | Final |
|---|---:|---:|
| Deadline week | 23 / 23 | 23 / 26 |
| Draft | 9 / 12 | 9 / 10 |
| July to October | 8 / 10 | 9 / 9 |
| In season, other | 7 / 5 / 1 | 7 / 5 / 1 |
| **Total** | **98** | **99** |

**Other measures** (base -> final):
- Grade gaps (two-team trades, the textbook model as analyst, 10 points to a letter):
  - a full letter or more: 41.0% -> 43.2% (real 59%);
  - 1.5 letters or more: 30.1% -> 23.9% (real 21%).
  - At 12 points to a letter: 38.6% / 19.3% -> 36.4% / 19.3%.
- Lopsided trades: 25 -> 21; explained by a stated trait: 17 -> 11.
- Both teams' reasons stated: 98 of 98 -> 99 of 99.
- Trades carrying a personality reason: 74 -> 78. Trades on final offers: 20 -> 24.
- Players traded twice: 21 -> 19. Star-for-star swaps: 0 -> 0. Young starters moved: 0 -> 0.
- Most picks traded away by one team: BOS 11 -> IND 11.
- Speed (CPU, whole run): 1,440 s -> 1,378 s. Deadline days: 75 s -> 66 s and 144 s -> 126 s. The asset additions
  are a handful of full checks a war, so they are not visible in speed.

## Three bidding wars (final run)
1. **Ty Jerome, Memphis (rebuilding), 2027-12-18: Boston against Oklahoma City, 2 rounds.**
   - Round 1: Oklahoma City led (price 15.8; Boston 6.7).
   - Round 2: Boston added assets and passed it at 20.0: Mitchell Robinson, Massamba Diop, Baylor Scheierman, the
     Clippers' 2028 first (top-16 protected) and a 2030 second. Oklahoma City could not add more within its limit.
   - Memphis's stated reasons: it has always liked Mitchell Robinson (+4.9), and the package fits its timeline. They
     agree with the price, so no exception was needed. Boston's side: it works hard to stay under the tax.
   - The trade reads: "BOS won a bidding war against OKC (2 rounds). BOS's offer was worth the most to MEM, more than
     OKC's."
   - In the base run, the same player went to Boston at a **lower** price than Minnesota's offer (6.7 against 8.9).
     That is the case the floor now prevents.
2. **Dash Daniels, Oklahoma City (contending, taxpayer), 2027-06-30: five bidders** (Sacramento, Chicago, Charlotte,
   Dallas, Atlanta), 2 rounds.
   - The base run ended in round 1 with Charlotte on top at 22.9, against Dallas's 22.1. That is the "war that ends at
     a second" that TRADE-FOLLOWUPS flagged.
   - Final run: Chicago and Sacramento raised in round 2.
     - Sacramento's raise added its 2034 first to a 2034 second (55.0 against Chicago's 25.4). That is a jump far past
       what it needed, and the reason for the cap in 7dc2694.
     - With the cap (replay of the same day): Milwaukee adds a 2034 second and wins at 28.9, against Chicago's 23.8.
       Oklahoma City gets about two seconds for a 21-year-old playing 6 minutes, instead of one.
   - Oklahoma City's stated reason: it prizes draft picks (+4.0 on the winning package).
3. **Donte DiVincenzo, Washington (rebuilding), 2027 deadline day: Cleveland against San Antonio, 1 round.**
   - Cleveland: Craig Porter Jr., Nae'Qwan Tomlin, Thomas Bryant and its 2028 first (price 0.7). San Antonio: -2.9.
   - Cleveland's reasons: win-now urgency (+4.6), will pay the tax (+4.0), and a final offer after two days of talks.
     Washington's: it overpays for veterans (Bryant, +2.6), and its own final offer.
   - The trade states both, plus "CLE's offer was worth the most to WAS, more than SAS's."
   - This deal is the same in both runs.

The other three final-run wars: Miles Sadler, Toronto to New York (16.9 against Denver's 14.6), Jason Crowe Jr., Utah to
Denver (21.9 against 5.1), and Luke Kornet, Clippers to Cleveland (7.6 against Minnesota's 4.5). Every one states both
teams' reasons and the decision.

## Tests
- New `tests/test_bidwar_price.py` (17 tests):
  - the price leaves out personality and concessions;
  - the best price wins, not a seller's concession;
  - raises are compared on price, and the winner pays at least the second-best bid;
  - a losing bidder adds an asset to stay in, and an overtaken leader that cannot add more loses;
  - a slightly lower bid wins only for a strong reason, and it is stated;
  - a larger gap is never overcome (the seller says whom it passed over);
  - a weak reason is not enough;
  - the preferred bidder raises to the best price when it can;
  - `raise_to_floor` uses the smallest addition, stays within the buyer's own check, and does not jump far past;
  - the rival and timeline reasons;
  - the user's side: beaten-offer words with the pick equivalent, a concession is not price, the same rare exception
    for the user;
  - the trade's explanation; the value words.
- New `tests/trade_market_board_price.test.cjs` (2 tests): the board's "Your offer" note and the sold player's reason.
- `tests/test_trade_market.py`: the beaten-offer wording; one war test now turns off asset additions in its toy league.
- Focused: `test_bidwar_price`, `test_trade_market` and `test_trade_followups`, 62 tests: OK.
- `bash scripts/run_core_tests.sh`: 338 OK, 2 skipped.
- `scripts/run_tests_parallel.py --workers 2 --match "trade|front_office" --js`: 960 ran, 0 failures, 1 error. The error is `test_rating_scale_consistency`, which needs a git-ignored output file (`output/defensive-scale-comparison-2026-11-10/canonical-before.json.gz`) that this worktree does not have. Browser tests: `startup_video.test.cjs` needs the ignored movie file, as on main. Every other JavaScript test passes, including the 2 new ones.
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18** league metrics within band. Trades do not change game results.
- **Determinism:** no random draws. Outcomes change by design, but only in bidding wars: who wins and at what price.

## What's left
- **The lower-bid exception never fired in two seasons.** If you want it "every once in a while", widen the slight gap
  (5 -> 8 points, about a second) or lower the strong-reason bar (2 -> 1.5). Both are one-line constants
  (`SLIGHT_GAP`, `STRONG_REASON`).
- **AI bidders do not raise against your recorded offer.** As before, they compete with each other, and the seller
  waits for you while your offer leads. A rival could add an asset to beat you, as rivals now do in the war.
- **Not in a full run: the cap on raise size (7dc2694).** It was checked on snapshot replays only.
- **The rival and timeline reasons apply only between bids.** They are not in any acceptance check, so a rebuilding
  team's acceptance still uses only the phase-weighted textbook values.
- **Board styling.** The board's note uses inline styling. A class in `trade-workspace.css` (not in this task's files)
  would be cleaner.

## Resume state
- Probe saves and snapshots were deleted to free disk (coordinator request). What remains:
  - progress logs: `output/bidwar-price/{base,final}-probe`;
  - metrics and trade lists: `output/bidwar-price/results/trade_metrics_{base,final}.json` and
    `trades_{base,final}.json`;
  - every war's prices and decision: `output/bidwar-price/wars_{base,final}.json` (`analyze.py`);
  - the snapshot sweep: `output/bidwar-price/sweep.json` (`sweep.py`).
- Tools: `replay.py` (one market day's wars) and `exercise_floor.py` (asset additions on real bids). A new run is
  needed to use them again.
