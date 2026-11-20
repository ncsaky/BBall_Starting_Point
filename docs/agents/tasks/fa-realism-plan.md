# Realistic free agency: plan

_Plan written 2026-11-20 by Claude (coordinator) from `fa-realism-research.md` (Codex research, merged). Not started. Starts after TRADE-DEADLINE merges: both touch the offseason flow and team payroll checks._

## TL;DR
- **Goal (user, 2026-11-20).** Complete realism that is still easy to understand: Bird rights and restricted free agency made explicit, with offer sheets and matching, played through clear phases in order.
- **The blocker.** The game has no single answer to "what can this team legally do with its money right now?" It has no cap holds, no mid-level exception, and no hard caps triggered by specific moves; it uses a tax-room shortcut instead. Every realistic feature depends on that answer, so it comes first.
- **Built in four slices, each playable on its own:**
  1. the money rules;
  2. the calendar and the four offseason stops, with options and qualifying offers;
  3. restricted free agency: offer sheets and matching;
  4. finishing the roster: two-ways, camp deals and sign-and-trades.

## The offseason the user plays (four stops)
The real calendar, with each stop pausing for the user's decisions only:
1. **Decide who to keep** (Finals end to June 29, with the draft on June 23–24 in the middle).
   - One checklist sorted by deadline: player and team options, qualifying offers for young players, talks with your own free agents (Bird rights shown openly: what you can pay, for how long, with what raises), cap holds, and whether to renounce one to open room.
   - The draft lottery moves to May, during the playoffs, as in real life.
2. **Make offers** (June 30 onward). Negotiate with anyone. A deal is official as soon as both sides agree.
   - Pick how you pay: cap room, the mid-level, the minimum or Bird rights. The screen shows which ones you have and what each locks you into (e.g. "using this hard-caps you at the first apron").
   - Sign other teams' restricted free agents to offer sheets.
3. **Finalize and match** (July 6–7, then the first wave).
   - If a rival signs one of your restricted free agents to an offer sheet, you get a clear countdown: the terms year by year, and what matching does to your cap, then Match or Pass.
   - AI teams face the same decision.
4. **Set the roster** (camp to October 19).
   - Go from up to 21 players to 15 plus up to 3 two-way players.
   - Rookie-scale extensions close on October 19, and rookie options come due in early November.
- **Late summer is background by default.** The game only stops for a real decision, such as an offer sheet, a waiver claim or a deadline.

## Slice 1: the money rules (foundation)
- **One calculator** that answers, for any team and any move: is it legal, how is it paid for, what does it lock in? The offer builder, AI bids, trades, waivers and the save all ask the same calculator.
- **What the calculator covers:**
  - **Cap lines:** the exact 2026-27 cap, tax and both aprons (unrounded), plus the salary floor.
  - **Cap holds:** for each free agent you still hold rights to, renouncing a hold, and holds for unsigned first-round picks and empty roster spots.
  - **Exceptions as real budgets:** the full, taxpayer and room mid-level; the bi-annual; the minimum. Each has an amount, a length limit, and rules for who may use it.
  - **Hard caps triggered by specific moves:** each move records the ceiling it creates for the rest of the year. Bird rights can't break a ceiling already triggered.
  - **Max and min salaries:** the true max (25/30/35% or 105% of prior salary) and the minimum by years of service, including the league's reimbursement of veteran minimums.
  - **Legal raises:** the 8% or 5% raise schedules, calculated off the first year and saved year by year. Early Bird's two-year minimum.
- **Trade dates for new signings:** December 15, January 15 or three months, kept separate from the AI's re-trade hold.
- **Done means:** the research's scenario list passes. Examples:
  - a $19M hold kept, the player re-signed for less, then the freed room used;
  - a team already hard-capped can't match even with Bird rights;
  - a taxpayer team can use its $6.064M taxpayer mid-level.

## Slice 2: the calendar and the four stops, with options and qualifying offers
- **Calendar:** the lottery in May, then the Finals, own-team talks from Finals end, the draft June 23–24, the June 29 options and qualifying-offer deadline, talks open June 30 at 6 p.m., the July 1 new league year, and July 6 signings. Contract seasons switch on one date for everything.
- **Options:** player options, team options and early terminations, decided by the player or team with reasons. AI players opt out when the market would pay more.
- **Qualifying offers:** exact eligibility and amounts (rookie scale and starter criteria, 135% of salary, two-way versions). The AI tenders them for valuable eligible players.
- **The keep rule:** the current "keep good young players automatically" shortcut is replaced by the real path: tender a qualifying offer, then negotiate.
- **Deals are official the moment both sides agree** (user decision 2026-11-20). There is no separate "agreed" stage and no reneges. The calendar still controls when talks open.

## Slice 3: restricted free agency
- **Offer sheets.**
  - Legal terms: two to four years, 5% raises, and the backloading rule for players with one or two years of service.
  - The bidding team's room stays reserved while the sheet waits.
  - One sheet per player at a time.
- **Matching.**
  - Exact deadlines (next day or two days, depending on the time of signing).
  - The matching team needs room, Bird rights or an exception, and must not breach a hard cap.
  - A matched player can't be traded for a year, and never to the team that made the offer.
- **Player choices:** accept the qualifying offer (a one-year bet, then unrestricted), wait (deadline October 1, or later if extended), or sign a sheet.
- **AI behavior:** how often sheets happen is calibrated to the real 0–3 per summer, with about two in three matched. AI teams aim sheets at good young players their rivals can't afford to match.

## Slice 4: finishing the roster
- **Two-way contracts:** 3 separate slots, eligibility, a 50-game limit, and conversion to a standard deal.
- **Exhibit 10 camp deals:** a one-click camp invite.
- **The 21-to-15 cutdown:** on the October 19 deadline, with waiver claim timing done properly.
- **Sign-and-trades:** a three-way agreement, the receiving team hard-capped at the first apron, and the salary-counting rule for big raises (base-year compensation).
- **The late market:** gets thinner. Fringe veterans may go overseas with a named reason, and nobody is signed onto the user's roster without a choice.

## Measures (each slice)
- **Real counts per summer:**
  - offer sheets 0–3, about two in three matched;
  - accepted qualifying offers 0–2 standard;
  - sign-and-trades 3–11;
  - 18–23 teams using a mid-level;
  - about 45–55% of tracked free agents returning to their own team.
- **Stars stay where Bird rights and a sensible owner would keep them** (the KEEP-STARS results hold).
- **What the user sees equals what the engine applies** (rule 4): previews, the save and the signing wire all use the same numbers and dates.
- **Speed:** the offseason doesn't get slower to play through. The number of user stops is measured.

## Files
- **New:** `cap_ledger.py` (the money calculator) and `offseason_calendar.py`.
- **Changed:** `cap_rules.py`, `contract_ai.py`, `play.py` free-agency paths, `save.py` re-signing and phase paths, `waivers.py`, `transactions.py` (only the legality check and signing-date rules), `app_actions.py` free-agency actions, `gui/app.js` and `free-agency.css` (the four stops and the match screen), tests.
- **Sequencing:** the work must follow TRADE-DEADLINE, which owns `transactions.py` and trade legality right now.

## User decisions (2026-11-20)
- **Build order:** the money rules first (slice 1), then the calendar with options and qualifying offers, then offer sheets and matching, then two-ways and sign-and-trades.
- **Signing:** deals are official the moment both sides agree. There is no "agreed until July 6" stage and no reneges.
- **Pauses:** always stop at the four offseason stops. Between them, stop only for a decision that's the user's (an offer sheet to match, an option or qualifying offer due, a waiver claim). Everything else runs in the background.
- **Two-way and camp (Exhibit 10) deals:** part of this project, as the last slice.
