# Trade market: front-office personality, negotiations, shopping, bidding wars (TRADE-MARKET)

_Claude (Opus agent), branch `worktree-agent-a8b7bf33bc84c43b3` (from 02ee3d1). Status: **review** (committed on the
branch, not pushed or merged)._

## TL;DR
- Every front office now has a lasting personality (judgement, win-now urgency, patience, loyalty, habits and
  favourite players), taken from real reputations where they are widely held, with sources; it replaces the old dice.
- Talks now last several days, sellers shop players with several bidders, and impatient teams make take-it-or-leave-it
  final offers; deadline day is now a day of final offers. You see it all on a new Trade Market board and in texts.
- Trades over two seasons: RUN3_TOTAL against 101 at the start (the first deadline week RUN3_DL1, the second
  RUN3_DL2; real 23-28); the textbook acceptance rules are unchanged, CPU unchanged, real-stat scorecard 18/18.

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

RESULTS_PLACEHOLDER
