# Trade market: front-office personality, negotiations, shopping, bidding wars (TRADE-MARKET)

_Claude (Opus agent), branch `worktree-agent-a8b7bf33bc84c43b3` (from 02ee3d1). Status: **review** (committed on the
branch, not pushed or merged)._

## TL;DR
- Each front office now has a lasting personality from its real reputation (sources recorded); no more dice.
- Talks last days, sellers shop players to several bidders, impatient teams make final offers; you see it on a board.
- Two seasons: 104 trades (was 101); first deadline week 29 (was 22, real 23-28), second 18 (was 21); 18/18.

## Objective
Plan and user decisions: `trade-market-personality-plan.md`. Volume from personality and the market, never by
loosening the textbook acceptance rules. Every personality effect bounded, explained and stated in the trade's
reasons; no dice.

## What changed

### 1. Front-office traits (new `front_office.py`; data in `data/overrides/front_office_overrides.json`)
- Every AI front office has four lasting traits (0-100, 50 = league middle) plus habits:
  - **savvy**: how well it judges value. At 65 or more it makes no systematic mistakes. Below that it misjudges in
    its own lasting direction (its habits: overpays for veterans, spends picks freely, overrates its own players,
    chases star names), more strongly the lower it is (full size at 20).
  - **urgency**: how much extra it pays for real help now (a rotation-level player better than any it sends) while
    its window is open (contenders fully, rising teams 60%, retooling and rebuilding teams not at all). A team in no
    hurry pays a little less.
  - **patience**: how many market days it keeps talking (2 to 7), how much ground it gives as talks drag on, how
    long a seller waits for offers, and how many counters it makes to you before its final one.
  - **loyalty**: scales step 1's tenure premium for players who have been with it for years.
  - Preferences that are not mistakes: prizes draft picks, works to stay under the tax, pays the tax to win.
  - **Player opinions**: each office's scouting lead has a lasting taste (the same taste behind its draft board).
    Read on NBA players' ratings, the few players at the two ends of that taste (about 7 high and 7 low per office)
    carry an opinion worth 2.5-5 value points. Documented real connections count too (the Knicks' Villanova players).
- **Real reputations first.** A research pass collected public reputations for all 30 offices
  (`data/research/front_office_reputations_2026_11.json`, 20 sources). Only views it marked widely held (two or more
  outlets, or a ranking with corroboration) set a trait: 24 offices have at least one, from 15 sources (CBS Sports'
  2025 and 2026 front-office rankings, The Athletic's executive poll, ESPN's Future Power Rankings, SI, Defector,
  Hoops Rumors and the analyst grades in the repo's real-trades file). Every documented trait, habit and connection
  names its sources. `scripts/build_front_office_traits.py` rebuilds the section from the research file.
- **Everything else is drawn** from the measured spread, seeded by the save: centred on 50 with 60% of the reputed
  offices' spread (reputations exist mostly for extreme offices, so an office without one is likelier to be
  ordinary). New regimes (Chicago, Dallas, Philadelphia, Toronto) keep only what is documented about the current
  regime. A documented misjudging habit caps a drawn savvy at 50, so the habit really shows.
- Traits are stored in the save when it is created and drift a little each season (seeded, about 2.5 points).
- **No dice.** The old personality term was a random roll per proposal (up to about plus or minus 2.5) plus constant
  offsets. It is gone. Each personality term is a fixed function of the traits and the assets, capped per term (3-6
  points) and in total (10 points; a future second is worth about 9.5, a future first about 43), with plain words
  that are stored on the evaluation and added to the trade's reasons ("Personality: PHX spends draft picks freely
  (+5.3)"). The search's quick price screens use the same terms, so the search and the full check agree.
- An urgent contender, or an office that spends picks freely, may spend a little more draft value on a player who
  would not start for it (up to about two seconds' worth), and a conceding buyer its concession; the evaluation
  notes say so.

### 2. Negotiations that last (new `trade_market.py`; `save['trade_market']`)
- When a pursuit ends a market day close but apart, the negotiation is kept: teams, player, each day's offer, both
  sides' distance from their price. On later market days the same pairing meets again first, and each side gives a
  little ground as its patience runs out: up to 6 points for a fully impatient office, 30% of that for a fully
  patient one, growing with the days of talks and in deadline week.
- **Only a side with its own reason to deal gives ground**: every player it sends is one it means to move (a stated
  reason, or salary it would move). A team "with no plan to move him" never concedes, whatever it gets back.
- When a side's patience runs out it makes a final, take-it-or-leave-it offer (its full concession). If that is
  refused the negotiation dies and the buyer walks away for 30 days. A dead negotiation comes back only after the
  cooldown, when the buyer is high on the player (or he is its first target and it is urgent) and the seller's
  situation has changed (its window or its reasons to sell); otherwise the pairing is not tried again.
- **Deadline day**: there is no tomorrow, so every motivated side makes its final offer.

### 3. Shopping and bidding wars
- A good player (trade value 45+) whose team has a stated reason to move him is shopped when two or more teams are
  interested. The seller gets a decision day (2-6 days by patience, never after the deadline).
- Agreed offers for a shopped player go into the seller's comparison instead of closing at once. Bidders raise in
  rounds (each offers its next package that is better for the seller and still acceptable to itself), up to 4
  rounds; the best offer wins and goes first in the day's deals. A patient seller waits for its decision day unless
  an offer clearly beats its price; an impatient one takes a good offer early.
- **No harassment**: players on teams with no reason to sell are never shopped. An unsolicited offer for a
  contender's star (about the top 60 players) needs a buyer that is high on him and urgent, at most once per buyer
  per season, and a patient owner refuses to engage. Every attempt is counted.
- **Interest from opinions**: an office may pursue an available player its scouts have always liked even if he is
  not on its target list, if he would play 14+ minutes for it and the prices can meet (2 per office; rebuilding and
  retooling offices do not chase players over 29). They come after every target pairing in the search order.

### 4. The calendar's last two days (`trade_calendar.py`)
- Before deadline day the day's trade slots bound the market (in the 2027 deadline week the market found more deals
  than slots every day); on deadline day the supply bound. With deadline-day final offers the supply filled the day,
  so the last two days now follow the real 2026 deadline: 5 slots expected the day before (was 4) and 18 on the day
  (was 15). Slots are room for deals, never a quota.

### 5. Your side
- **Assistant GM texts** (at most 2 a day): "MEM is shopping Ty Jerome; 4 teams interested; decision by
  2027-02-05.", bidding wars, final offers waiting for you, and a decision-day reminder when your offer is in the
  running. They open the Trade Market board.
- **Trade Market board** (Trades menu > Trade Market, or the new tab in the Trade Room): players on the market, why
  each is available, how many teams are interested (names on hover), the stage (taking offers, bidding war, deal
  agreed, sold), the decision day and your offer's standing (leads, outbid); final offers waiting for you; your
  assistant GM's read on the selected partner. House table style (double rule under a small bold header, alternating
  rows, whole-row hover, shaded sorted header, headshots bottom-aligned).
- **Your offers compete**: an offer for a shopped player is compared with the best AI offer. If it is beaten the
  partner turns it down ("MEM has a better offer for Ty Jerome (3 other teams interested; decision by ...). Beat it
  to get him.") and its counter must beat that offer. Your best accepted offer is recorded, AI bidders must beat it,
  and while it leads the seller waits for you until its decision day.
- **Final offers**: tick "Final offer (no counters)" and the partner answers yes or no. AI partners counter you 1 to
  4 times by patience (on deadline day the next counter is final); the last says "This is MEM's final offer: take it
  or leave it." Impatient offices, and every office in deadline week, make their offers to you final with an
  answer-by day; unanswered ones lapse.
- **Front-office reads** in the trade window and on the board, in words only: with no dealings, only the widely held
  reputation ("Known to be one of the sharpest judges of value in the league."); after a first dealing, a rough level
  for every trait ("Seems impatient in negotiations."); after three, the full description with habits and scouting
  lean. An inert habit (a savvy office's) is never shown (rule 4). Each offer, counter answer or reply to an offer is
  a dealing (at most one a day per team).
- Checked in the running app at 1440 and 1024 wide (screenshots `output/trade-market/screens/`).

## Results

Two-season probe (`scripts/two_season_league_probe.py`, seed 17, Golden State hands-off, 2026-10-20 to 2028-11-01).
"Base" is the branch start (02ee3d1, TRADE-DEADLINE merged). "Final" is run 4 (all of this task's changes except the
two small commits after it: free-agency trades stating their reasons, and one bid per buyer). Runs 2 and 3 used
earlier versions of the motivation rule and show the run-to-run spread.

| Window | Base | Final | Runs 2 / 3 | Real |
|---|---:|---:|---:|---:|
| **Deadline week 2027** | **22** | **29** | 29 / 27 | 23-28 |
| ... of which deadline day | 12 | 15 | 16 / 13 | 18 |
| **Deadline week 2028** | **21** | **18** | 19 / 18 | 23-28 |
| ... of which deadline day | 8 | 6 | 7 / 8 | 18 |
| Draft night 2027 / 2028 | 9 / 9 | 8 / 7 | 9/9, 9/9 | 8-11 |
| July to October 2027 / 2028 | 11 / 17 | 12 / 18 | 11/19, 10/14 | 16 and 8 in July alone |
| October to January (two seasons) | 12 | 11 (+1 Oct 2028) | 12+1, 12 | about 1 a season |
| **Total** | **101** | **104** | 109 / 99 | 110-140 |

- **The first deadline now lands in the real range** (29, 29, 27 in three runs against 22), with the deadline day
  filling its room (15 of 17 slots). **The second deadline did not move** (18-19 against 21): on that day the market
  ran out of deals, not room. In a diagnostic search of the 2028 deadline day with no slot limit, the market found 8 deals;
  1,360 of 1,389 built packages missed the quick price screen by more than any bounded personality term.
- Draft night is 1-2 lower in the final run (8 / 7, real 8-11); runs 2 and 3 had 9 / 9, so this is within the spread.
- **No spirals**: most picks traded away by one team in two seasons: Indiana 12 (base: Milwaukee 12). Players traded
  twice 20 (base 27), three times 2 (base 3). Re-trades inside six months stay blocked (unchanged hold).
- **Guards held**: young starters moved 0 (run 2 had 1, Javon Small, before the motivation fix), star-for-star
  swaps 0, rebuilding teams buying 30+ veterans on $15M+ multi-year deals 0 (runs 1-3 had 1-2,
  all salary filler in sales), LeBron untouched.
- Taxpayers at season end 11 / 9 (base 10 / 9; real 6-8, unchanged problem).
- **Reasons**: 98 of 104 trades stated both teams' reasons in the final run; the 6 without were free-agency
  roster-space and cap-room trades, which now state theirs (fixed after the run). 73 trades carry a personality
  reason (urgency 25, final offer 41, values picks 15, overrates own 18, spends picks freely 14, tax 10, opinions 9,
  concession 10, overpays veterans 2, loyalty 1).

### Grade gaps against real
The analyst is the textbook model: each team's net value with its personality terms taken out. One letter grade is
taken as 10 points of difference between the two teams' textbook nets (about one future second-round pick moved from
one side to the other); 12 and 15 points shown for the spread.

| Two-team trades | Real (29 graded) | Base | Final |
|---|---:|---:|---:|
| A full letter apart or more (10 / 12 / 15 points) | 59% | 39 / 31 / 22% | 40 / 32 / 22% |
| 1.5 letters or more (10 / 12 / 15 points) | 21% | 22 / 19 / 11% | 22 / 16 / 9% |
| Lopsided (1.5+ letters at 10 points), explained by a stated trait of the losing side | | 0 of 20 | **10 of 20** |

- The share of lopsided trades did not grow; what changed is **why**: half of them now come with the losing side's
  stated trait (Sacramento overpaying for a veteran, Phoenix and Toronto spending picks freely, a deadline-day final
  offer). The other half are textbook trades with a big context term the analyst view does not credit: draft-night
  trade-ups (the board's number one at any price) and tax dumps.
- The "full letter" share stays below real at any of these scales. Real analysts also disagree with each other by
  up to a full letter on the same trade, which this measure cannot include.

### Bidding wars
- Final run: 4 trades closed after a bidding war, all on free-agency days; runs 1 and 2 also had in-season wars.
  Single-bidder sales of shopped players: 13 in two seasons. Players shopped: 81 and 67 a season (many are role
  players on teams selling; 2 or more interested teams each).
- **Josh Hart, deadline week 2027 (run 2)**. Retooling New York shops Hart to get under the tax; the Knicks' Villanova
  tie makes them ask about 5 points more for him. On 2027-02-03 the Lakers and San Antonio bid for three rounds: the
  Lakers 9.2 over New York's price, San Antonio raises to 10.6, the Lakers raise to 20.7 and win (the Lakers spend
  picks freely, a documented habit). That agreed deal was not executed (see What's left). On deadline day Portland
  and Houston bid: Portland's Micah Potter and two seconds come to 18.0 over the price against Houston's 13.6, and
  Portland gets Hart.
- **Ignas Stombergas, July 2028 (final run)**. Charlotte shops him; Denver bids 12.2 over the price, New York 11.4,
  Sacramento 10.0. Round 2: New York raises to 15.7 and wins.
- No unsolicited offer reached a contender's star: 3 attempts in two seasons (Memphis, Miami, Charlotte), all refused
  by patient owners.

### Final offers
- 24 trades closed on a final offer; 45 final offers were refused (the buyer walked away for 30 days). Days of talks
  per trade: 1 day 87, 2 days 12, 3 days 2, 4 days 1, 5 days 2.
- **David Jones Garcia, December 2026 to January 2027 (final run)**. Rising Denver wants a guard for its top six;
  talks with San Antonio open on 2026-12-08 and continue on four more market days. On 2027-01-30 Denver's patience
  (36) runs out: its final offer concedes 4.5 points, San Antonio (patience 85) has given 1.6. The deal closes as a
  three-team trade: Denver gets Jones Garcia, Memphis takes Harrison Barnes's salary for a second.
- **Josh Hart, deadline 2027 (final run)**. Houston (rising) and New York talk on 2027-02-04; on deadline day both
  sides' patience runs out (New York +4.6, Houston +3.7). Houston gets Hart for Steven Adams, Oscar Tshiebwe and its
  2027 first (more favourable of HOU/BKN); its textbook view is 7.8 short, its stated reasons are the final offer and
  win-now urgency (+2.1).

### Hand-read trades
Read 30 trades of the final run (the 2027 deadline week and draft night) and the earlier runs' deadline weeks, as an
analyst would. Six here:

1. **Good**: Lakers (contending) get Moritz Wagner from rebuilding Brooklyn for Jarred Vanderbilt, Jaden Hardy and a
   second. A contender buys a backup big with salary it would move. Both sides' textbook nets positive.
2. **Good**: Denver, San Antonio and Memphis (above): a guard for a rising team, a contender trimming salary, a team
   with room paid a second to take it. After five days of talks and Denver's final offer.
3. **Head-scratcher, explained**: rebuilding Sacramento takes Klay Thompson (37, $5.75M for two years) from Miami for
   Daeqwon Plowden. Sacramento's textbook view is 9.2 short. The reason stated: Sacramento tends to overpay for
   veterans (documented: CBS's last-ranked front office, its trade-up overpay) plus its deadline final offer.
4. **Overpay, explained**: retooling Toronto gives Tyreke Key, Kyle Anderson, Jamarion Sharp and its 2027 first for
   Cam Spencer (26, 29 minutes, $2.4M for three years). Toronto "spends draft picks freely" (+6, a drawn habit; its
   regime is too new for a reputation). An analyst would grade Memphis's side well.
5. **Borderline**: Houston's Josh Hart deal above: a fair rental price from a seller with a reason, a little rich for
   Houston, made by deadline-day final offers.
6. **Bad (textbook, not personality)**: rising Memphis sends Javon Small (24, 24 minutes) to New York for Tony
   Bradley, Jordan Clarkson and two seconds. Memphis "had no plan to move him"; its own personality pushed against
   the deal (it overrates its own players, -5), so the textbook value model is what likes the return. Same pattern
   as the young-starter guard's blind spot (his projected minutes are under 24). See What's left.

Others read: Scoot Henderson to rebuilding Phoenix (defensible flier; Phoenix spends picks freely), Jaylin Williams to
Utah for a second (Oklahoma City's tax sale; analysts would grade Utah A), Jock Landale for Grant Williams (fine,
deadline final offers both ways), Kenrich Williams to Orlando (fine), Tari Eason to Charlotte (Houston tax move,
good for Charlotte), Haywood Highsmith to Boston for Ron Harper Jr. and a first (questionable for Boston: a savvy
office overpaying through the deadline concession, not its savvy), Thybulle to Cleveland for Meleek Thomas
(borderline), Tre Jones to Washington for Tre Mann and a first (good rebuild sale), draft-night trade-ups by Cleveland
and Boston for their boards' number one (textbook lopsided, like the real Denver/San Antonio trade-up).

### Front-office traits
Bold: from a widely held reputation. Others drawn from the measured spread (seed 17 shown; they differ by save).
"(drawn)" habits come from low savvy without a documented habit.

| Team | Savvy | Urgency | Patience | Loyalty | Habits | Basis (sources) |
|---|---:|---:|---:|---:|---|---|
| ATL | **55** | 49 | 38 | 50 |  | CBS Sports, ESPN Future Power Rankings |
| BKN | 77 | 72 | **75** | 48 | values picks | CBS Sports, ESPN Future Power Rankings |
| BOS | **80** | 53 | 47 | 61 | tax averse | The Athletic exec poll, CBS Sports 2025 and 2026, ESPN Future Power Rankings |
| CHA | **68** | **64** | 35 | 46 | values picks | CBS Sports, ESPN Future Power Rankings, real-trade grades (repo) |
| CHI | 31 | 36 | 25 | 60 | chases stars (drawn) | regime too new: drawn |
| CLE | **74** | **76** | 49 | 66 | spends tax | The Athletic exec poll, CBS Sports 2025 and 2026, ESPN Future Power Rankings |
| DAL | 59 | 38 | 69 | 43 |  | regime too new: drawn |
| DEN | 50 | 38 | 36 | 49 | overrates own | CBS Sports, ESPN Future Power Rankings |
| DET | 52 | 46 | **78** | 51 | overrates own (drawn) | CBS Sports, ESPN Future Power Rankings |
| GSW | **58** | 61 | 44 | **85** |  | The Athletic exec poll, CBS Sports, ESPN Future Power Rankings, ESPN |
| HOU | **74** | 73 | 54 | 45 |  | The Athletic exec poll, CBS Sports, Roundtable |
| IND | **77** | 20 | 18 | **74** | tax averse | The Athletic exec poll, CBS Sports 2025 and 2026, ESPN Future Power Rankings |
| LAC | 51 | 80 | 35 | 45 | underrates picks (drawn) | drawn from the spread |
| LAL | **35** | 46 | 51 | 42 | underrates picks | CBS Sports, CBS Sports, CBS Sports, ESPN Future Power Rankings, real-trade grades (repo) |
| MEM | 35 | 67 | **30** | 54 | overrates own (drawn) | CBS Sports, ESPN Future Power Rankings |
| MIA | **75** | **80** | **35** | 46 |  | The Athletic exec poll, CBS Sports, CBS Sports, ESPN Future Power Rankings |
| MIL | 61 | 40 | 52 | 58 |  | drawn from the spread |
| MIN | **50** | **80** | 70 | 66 | underrates picks (drawn) | The Athletic exec poll, CBS Sports, ESPN Future Power Rankings, real-trade grades (repo) |
| NOP | **25** | 41 | 37 | 56 | underrates picks | CBS Sports, ESPN Future Power Rankings, Hoops Rumors |
| NYK | **78** | **80** | 33 | 51 | Villanova ties | The Athletic exec poll, CBS Sports, CBS Sports, CBS Sports, Defector, ESPN Future Power Rankings |
| OKC | **95** | 83 | 71 | 50 | values picks | The Athletic exec poll, CBS Sports 2025 and 2026, ESPN Future Power Rankings, real-trade grades (repo) |
| ORL | 55 | **70** | 54 | 35 |  | CBS Sports, ESPN Future Power Rankings |
| PHI | 57 | 27 | 43 | 42 |  | regime too new: drawn |
| PHX | **25** | **88** | 52 | 42 | underrates picks, spends tax | CBS Sports, ESPN Future Power Rankings, Sports Illustrated, Sports Illustrated, real-trade grades (repo) |
| POR | 19 | 68 | 66 | 62 | tax averse | CBS Sports, ESPN Future Power Rankings |
| SAC | **20** | 38 | 42 | 62 | overpays veterans | CBS Sports, real-trade grades (repo) |
| SAS | **86** | 34 | **85** | 35 | values picks | The Athletic exec poll, CBS Sports 2025 and 2026 |
| TOR | 46 | 55 | 83 | 53 | underrates picks (drawn) | regime too new: drawn |
| UTA | **80** | 40 | **85** | 48 | values picks | CBS Sports, ESPN Future Power Rankings, real-trade grades (repo) |
| WAS | 50 | 36 | 80 | 40 | overpays veterans | CBS Sports, ESPN Future Power Rankings |

Measured spread for traits without a reputation: centre 50; spread 15.4 (savvy), 16.7 (urgency), 16.4 (patience),
8.4 (loyalty).

### Speed (CPU seconds)
- Whole two-season run: base 1,468; final 1,364; runs 1-3 1,515 / 1,403 / 1,567 (run 3 shared the machine with the
  core tests). The same normal month varies by about 15% between runs on this shared laptop (for example
  2026-10-20 to 11-20: 35, 33, 35, 34, 40), so **normal days are unchanged within noise**.
- Deadline steps: base 123, final 121 (2027 step 70 to 84, 2028 steps 135 to 92). Deadline days are not slower
  overall; the market skips dead negotiations, which offsets the bidding and raise checks.
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18** (trades do not
  change game results).

## Tests
- New `tests/test_trade_market.py` (27): traits from reputations with sources, seeded generated traits, centred
  spread, drift, save storage; personality terms bounded, plain words, no dice, no traits no personality, reasons
  stated; pick allowance; the ledger across days, patience-scaled concessions, a refused final offer ending talks
  with a cooldown and reopening only on a real change; deadline-day final offers only from motivated sides;
  shopping only with a reason; unsolicited offers for a contender's star; bidding war to the best offer; the user's
  offer beaten by a better bid and leading bids holding off the AI; final offers to the user and their expiry;
  counters ending in a final offer by patience; dealings once a day; hints that match the traits, sharpen with
  dealings, hide inert habits and show no numbers.
- New `tests/trade_market_board.test.cjs` (4): the trade window's market text, final-offer text, the read panel,
  the Trade Market tab, menu and assistant link.
- Trade modules (`test_trade*`, `test_multi_team*`, `test_keep_stars`, plus `test_roster_space`,
  `test_summer_trade_reviews`): 346 OK, 1 skipped. `bash scripts/run_core_tests.sh`: 338 OK, 2 skipped.
  `tests/*.test.cjs`: all pass except `startup_video.test.cjs` (needs the ignored movie file, as on main).
- GUI checked in the running app at 1440 and 1024 wide: `output/trade-market/screens/` (market board and the builder
  with the front-office read and the final-offer box).
- **Determinism**: no random draws in the trade decision any more. The removed per-proposal dice changes outcomes
  by design. New seeded streams: generated traits and their seasonal drift (keyed by save seed, team, trait, season),
  plus the calendar's last two days (same stream, new means).

## What's left
- **The second deadline**: 18-19 against 21 at the start and 23-28 real. On that day the market had too few deals
  within reach (8 with no slot limit). The binding rules are the textbook ones the user asked to keep: buyers'
  draft-spending limit for non-starters and competing sellers keeping their rotation. More volume there needs a
  textbook decision (as TRADE-DEADLINE said) or more targets per team, not more personality.
- **Bidding wars in season are rare** (two or more acceptable offers for the same player on the same day). A shopped
  player's agreed sale sometimes is not executed (crowded out of the day's slots or refused at the apply-time
  re-check) and is re-agreed on later days (the final run's Josh Hart was "sold" to the Lakers on seven market days
  before Houston got him); worth a look at the apply-time re-check of agreed market deals.
- **The young-starter guard misses players whose projected minutes are under 24** (Javon Small, 24 minutes this
  season). A textbook item.
- **Front-office hints on team pages**: done in the trade window and on the board; not on the team page itself.
- **Summer markets** (draft night, free-agency days) use the traits but not the ledger: no multi-day talks or decision
  days there (bidding wars do happen, one day at a time).
- Generated habits (drawn for low-savvy offices with no documented habit) are sometimes strong (Toronto, Chicago,
  Minnesota, Los Angeles Clippers). They are stated and bounded, but the user may prefer no habit without a source.
- The old front-office profile fields (competence, aggressiveness, asset discipline...) still set each team's
  acceptance threshold (plus or minus about 2 points) and feed contract and staff logic. They are not shown to the
  user; the hints describe only the new traits. Folding the threshold into the new traits is a follow-up.
- The real-trades research is secondhand for The Athletic's poll (via Bleacher Report) and ESPN's management ranks
  are partial (`data/research/front_office_reputations_2026_11.json`, "gaps").

## Resume state
- Probes: `output/trade-market/{base,run1,run2,run3,run4}-src/output/probe` (run4 is "final"). Metrics and trade lists:
  `output/trade-market/results/trade_metrics_<label>.json`, `trades_<label>.json`.
- Scratch tools in `output/trade-market/`: `advance_eval.py` (advance a snapshot day by day and summarise; `--slots3`
  widens slots), `refusals.py` (one market day without a slot limit, why deals fail), `grades.py`, `read_trades.py`,
  `market_days.py`, `count_window.py`, `speed.py`, `summarize.py`, `trait_table.py`, `opinions.py`.
