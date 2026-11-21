# Trade market: front-office personality, live negotiations and bidding wars (plan)

_Plan written 2026-11-20 by Claude (coordinator). Builds on TRADE-DEADLINE (merged 2026-11-20: counters, salary filler, late deadline pass, fit with the core) and trade step 5 in `trade-steps-3-5-plan.md`. Read both first._

## TL;DR
- **The problem.** The trade deadline stays about half as busy as real (16 and 15 deadline-week trades against 23–28). The textbook check refuses most near-deals: buyers won't spend picks on non-starters, and competing sellers won't lose rotation players.
- **User decision.** Don't loosen the textbook rules. Add the front-office personality layer now, plus a real negotiation market.
- **What changes:**
  - front offices get lasting traits;
  - negotiations run over several days with several teams at once;
  - good players who are really available get shopped, and that can start a bidding war;
  - a front office whose patience runs out makes a final take-it-or-leave-it offer.

## User decisions (2026-11-20)
- More trades come from personality and the market, not from loosening the textbook acceptance rules.
- **Counters:**
  - more back-and-forth rounds;
  - teams may come back to a negotiation later if they're high on a player and it's realistic the other team would move him;
  - no harassment of teams that simply have the best players.
- **Shopping and bidding wars:** when it becomes clear a good player is available and being shopped, interested teams compete.
- **Several negotiations at once.** An AI front office weighs every live offer at once and doesn't get stuck on one team's offers. When its patience runs out, it makes a take-it-or-leave-it offer (final and serious). The receiving team must decide on it against its other live negotiations.
- **Patience** (for counters and bidding wars) is a personality trait.
- **Visibility:**
  - Your assistant GM describes each front office in words, starting from its real reputation ("known to be patient", "tends to overpay for win-now veterans").
  - Descriptions get more precise the more you deal with that team. Exact numbers stay hidden.
  - Rule 4 still holds: the hints describe the traits the engine actually uses.
- **Bidding wars reach the user** through the assistant GM's texts ("MEM is shopping X; 3 teams interested; decision by Thursday") and a Trade Market board: shopped players, interested teams, how far talks have gone. The user's offers compete in the same process.
- **Speed:** "whatever it takes" on deadline days. Normal days and the rest of the season must not get slower.
- From earlier (2026-11-19): real front offices start with traits based on their public reputations. Only widely held views count, each with a recorded source. Generated or replacement front offices draw from the measured spread.
- **Fit versus personality** (2026-11-20): fit comes from the hand a team is dealt (its core and its coach's system). Personality is preferences on top of that, showing most when a team rebuilds and picks its core through the draft.

## Design
1. **Front-office traits** (lasting, set at save start, drifting slowly over seasons):
   - **Savvy:** how accurate its value estimates are. A less savvy office misjudges in a consistent direction (overrates its own players or recent picks, overrates veterans when contending, underrates picks). No random rolls.
   - **Risk appetite / urgency:** how readily it pays a premium while its window is open.
   - **Patience:** how many rounds it negotiates, how small its concessions are, how long it waits for a better offer before making a final one.
   - **Player opinions:** a few players per office it's higher or lower on than the league, from its scouts' lasting tastes (draft boards) and real connections where the data exists.
   - **Loyalty:** attachment to its homegrown players.
   - **Sizing:** calibrated so simulated trades show about the real rate of lopsided grades (about 59% of trades a full letter grade apart, about 21% 1.5 or more; `trade-steps-3-5-plan.md`), with the textbook value model as the "analyst". Every lopsided trade must be explained by a stated trait.
2. **A negotiation ledger.** Live negotiations persist across days. Each records:
   - the teams;
   - the player or players involved;
   - each round's offer and reasons;
   - each side's distance from its price;
   - its status (open, paused, final offer, dead) and a cooldown.

   A team may reopen a dead negotiation later (for example at the deadline) only if it's high on the player and the owner's situation has made a sale realistic (phase change, injury, tax, a filled need).
3. **Shopping.** A team with a stated reason to move a good player (rebuild, tax, blocked, unhappy, expiring and won't re-sign) can put him on the market. Interested teams (targets, needs, opinions) send offers over several days. The seller compares all of them each day.
   - **Anti-harassment:** players on teams with no reason to sell are never shopped. Unsolicited offers for them are rare, limited by the buyer's opinion and urgency, and the owner can refuse to engage.
4. **Bidding wars.** When two or more teams want a shopped player, the seller asks each for its best, and buyers raise within their own value plus personality premium. Ends on a set day (always by the deadline), or earlier with an accepted final offer.
5. **Take-it-or-leave-it.**
   - When a side's patience runs out, it makes one final, serious offer with a response day. The receiver compares it with every other live negotiation and decides.
   - If declined, the maker walks away and starts a cooldown.
   - The user can receive final offers and can make them (the AI answers the same way).
6. **The user's side:**
   - assistant GM texts for notable shopped players and bidding wars (with a cap on texts per day);
   - a Trade Market board;
   - the user's offers enter the same comparison;
   - counters and final offers appear in the trade window in plain words;
   - front-office hints on team pages and in the trade window, sharpening with the number of dealings.

## Measures (done means)
- **Deadline week toward 23–28 trades a season and deadline day toward about 18.** Totals over two seasons toward 110–140. Draft, July and late-summer counts not lower.
- **Grade gaps** are near the real distribution (about 59% a full letter apart, about 21% 1.5 or more). Head-scratchers and overpays come to about 15–20% of trades, each explained by a trait.
- **Bidding wars:** a few per season, on genuinely available good players. Report how many teams took part, how many rounds, and the final price against the textbook value.
- **No harassment:** contenders' stars are never shopped, and the count of unsolicited offers for them is reported.
- **No spirals:** no front office trades away every pick in two seasons, and no player is flipped repeatedly (the six-month hold stays).
- **Every trade still states both teams' reasons,** now including the personality reason where one applies.
- **Speed:** normal days unchanged; deadline days may be slower (user: "whatever it takes"), with the cost reported.
- **Real-stat scorecard 18/18** (trades don't change game results).

## Files
`trade_counters.py`, `trade_targets.py`, `transactions.py`, `multi_team_trades.py`, `trade_wants.py`, `trade_roster.py`, `trade_calendar.py`, new `front_office.py` (traits) and `trade_market.py` (the ledger, shopping, bidding), `data/overrides/front_office_overrides.json` (real reputations with sources), `team_planning.py`, `save.py` (market hooks only), `app_actions.py` (trade actions), `gui/app.js` (trade window, Trade Market board, team-page hints), `gui/assistant-phone.js` (texts), CSS, tests, `scripts/trade_probe_metrics.py`.

## Results and follow-ups (merged 2026-11-21; report `trade-market.md`)
- **Built:** front-office traits from real reputations (sources in `data/research/front_office_reputations_2026_11.json`), multi-day negotiations, shopping and bidding wars, final offers, a Trade Market board and assistant texts. There's no random roll in trade decisions now.
- **Two-season probe:** 104 trades (was 101). Deadline week 2027: 29 (real 23–28). 2028: 18, where the market ran out of deals: the two textbook rules the user kept still block the rest. Grade gaps of 1.5+ letters match real (22% against 21%); a full letter or more is 40% (real 59%).
- **Follow-ups:**
  1. Agreed market sales are sometimes not executed and get re-agreed later (Josh Hart was "sold" to the Lakers on 7 market days before Houston got him). Check the re-check that runs when agreed market deals are applied.
  2. The young-starter guard misses players projected under 24 minutes (Memphis sold Javon Small, 24, for two seconds).
  3. Front-office hints show in the trade window and on the board, not yet on team pages.
  4. Summer markets use the traits but not multi-day negotiations.
  5. The old front-office profile fields still nudge each team's acceptance threshold (about ±2 points) and aren't shown; fold them into the traits or retire them (rule 4).
  6. The second deadline is still short (18 against 23–28). The next levers are the multi-day market on summer days, and more bidders for shopped players.
