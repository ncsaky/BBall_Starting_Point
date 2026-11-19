# Trade steps 3 and 5: counter-asks and front-office personality (plan)

_Plan written 2026-11-19 by Claude (coordinator). Not started. Both build on steps 1, 2, 2b and 4, so they start after TRADE-STEP4 (three-team trades) merges; all of them edit the same trade code. Run step 3 first, then step 5. Background: `docs/agents/TRADE_AI_DIRECTION.md`._

## TL;DR
- **Step 3, counter-asks.** A seller no longer just checks its price. It looks at the buyer's roster for its own targets and asks for them ("we'll do it if Jaden Ivey is in it"). If nothing on that roster fits, it asks for more raw value, usually picks. Wanting a player doesn't guarantee getting him.
- **Step 5, front-office personality.** A small, deliberate layer on top of textbook trades. Each front office gets a few lasting traits: savvy, risk appetite, patience, views on specific players, and loyalty. Real trades then produce winners and losers at about the rate analysts grade them, for reasons we can explain, not dice.
- Neither step may break the textbook model. Every trade still has a stated reason on both sides, and the step 1–4 measures must hold.

## Evidence from real trades (`data/research/real_trades/trades_2025_2027.json`, 41 deals)
- Analysts grade a real two-team trade unevenly in most cases. Across 29 two-team trades with letter grades, the median gap between the teams is a full letter grade (e.g. B+ against C+). 59% are a full grade or more apart, and 21% are 1.5 grades or more apart: clear winners and losers.
- Verdict tags show why. Most trades are textbook (tax move 11, salary dump 8, rebuild sell 5, value-neutral role swap 5). A real minority are not: "head-scratcher" 4, "win-now overpay" 4, "overpay" 2, "front-office loser" 2, "sell low" 1, "investment sunk-cost" 1. Examples:
  - Boston to Philadelphia, July 2026, graded D+/F against A/A+;
  - Sacramento's Nique Clifford trade, graded D+/C against A;
  - Utah's win-now overpay with the Lakers, A+ against C-.
- Counter-asks are visible in the real trades: sellers taking back specific young players they targeted (Chicago turning Huerter into the younger Ivey), and sellers asking for picks when the buyer had nothing they wanted.

## Step 3: counter-asks
1. When a buyer's offer reaches a seller (from the step-2 target search or the step-4 multi-team stage), the seller first checks its own target list (step 2) against the buyer's roster and picks.
   - A **match** (a player the seller targets, or one fitting a profile it wants, such as "young wing" or "expiring salary") goes into a counter-offer. The buyer then decides by its own acceptance check.
   - **No match:** the seller asks for more raw value, preferring picks, then young players, then salary relief, according to its phase.
   - The counter must be legal and must stay close to the seller's asking price. It is not a chance to gouge.
2. One counter round, maybe two. Then the deal dies, or the buyer walks to an alternative target (step 2 already has alternatives).
3. Explanations: "UTA wanted Ivey back. DET agreed, because Ivey doesn't fit their timeline."
4. The user's team:
   - Sellers can counter **your** offers the same way, with their own targets on your roster, in plain words in the trade window.
   - When you're the seller, AI buyers' offers can already include players you'd want, because the step-2 search builds to the seller's price.
   - Your own evaluations are never changed.
5. Measures:
   - the share of trades that include a counter-asked piece;
   - whether sellers end up with players matching their targets;
   - total volume (deadline-week trades should rise toward the real ~23, because near-misses now get a second chance);
   - the step 1–4 measures hold;
   - speed: counters only on near-misses, so the evaluation count stays small.

## Step 5: front-office personality
Each AI front office gets a few **lasting** traits, set when a save starts and drifting slowly over the seasons. They apply on top of the textbook value, as small, bounded adjustments.
- **Savvy (0–100).** How accurate the front office's own value estimates are. A less savvy office misjudges in a consistent direction. For example, it overrates its own players or recent draft picks (the endowment and sunk-cost effects real front offices show), overrates veterans for a playoff push, or underrates picks. These are lasting tendencies, not random rolls. Calibrate the size so simulated trades have about the real rate of lopsided grades (about 59% a full letter grade apart, about 21% 1.5 or more), measured with the same value model acting as the "analyst".
- **Risk appetite and patience.** These set how readily the office chases win-now moves (more overpays when its window is open, plus owner pressure) and how quickly a rebuild sells.
- **Player opinions.** A few players per office it is high or low on, more than the league is. Where possible, base these on scouting history (the draft-board work gives each office scouts with lasting tastes) and on reputation (a former player, or a coach connection, if the data exists). Keep them few and modest. They show up as "BOS has always liked him."
- **Loyalty.** How attached the office is to its own homegrown players, layered on step 1's tenure term.
- **Where the traits come from:**
  - real front offices: base starting traits on public reputations and track records, where those are well documented. Name the sources, and use only public, widely held views, e.g. a front office widely seen as patient or as aggressive;
  - generated or replacement front offices: draw from the measured spread.
- **What stays fixed:** the bounds keep personality a small layer. A front office never accepts a deal its own textbook value calls badly negative, unless one of its stated traits explains it, and the explanation says so ("PHX's win-now push: they paid a premium").
- **The user** can see each front office's tendencies in plain words on a team or front-office page (rule 4: shown traits must be the ones the engine uses).
- **Measures:**
  - the distribution of grade gaps against real;
  - the share of "head-scratcher" or overpay trades (real about 15–20%);
  - every lopsided trade explained by a trait;
  - the step 1–4 measures hold;
  - no front office spirals (e.g. a low-savvy team trading every pick away in two seasons).

## Files
`trade_targets.py`, `transactions.py`, `multi_team_trades.py`, `trade_wants.py`, the front-office data (`data/overrides/front_office_overrides.json`, `team_planning.py`), the user trade-window text in `gui/app.js` (minimal), and tests. Both scorecards should be byte-identical: trades don't change game results.

## User decisions
- 2026-11-19: real front offices start with traits based on their public reputations. Use only widely held views, with each source recorded. Generated or replacement front offices draw their traits from the measured spread.

## Open question for the user (ask when starting step 5)
1. Should you be able to see each front office's tendencies in full, or only hints (e.g. through your assistant GM)?
