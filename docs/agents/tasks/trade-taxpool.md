# Trade tax pool: the luxury-tax payout, draft-night chains, draft trades across the whole draft (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a3d8cfba64b8f8e2f` (fast-forwarded to `codex/immersive-franchise-journey`
at 9f17e77, step 4 merged). Follows `trade-step4-multi-team.md` (user decision: the tax-pool payout is the way to win
back trade volume)._

## TL;DR
- **Built**: AI teams now count their share of the luxury-tax payout (half the tax, split among teams under the line)
  when a deal moves them across the line; the payout is recorded every season and shown in the Cap position panel.
  Draft night now has three-team chains (4 of 10 draft trades) spread over the whole draft (picks 11-35, was 11-16);
  recent draft picks are no longer dumped for tax money; offers to your team show their reason.
- **Volume did not come back**: trades 62 -> 60 and deadline weeks 14/10 -> 12/10 (real ~23). In this league the
  payout is only $2.0M and $4.3M a team (real $5-14M), because the trade AI's tax line is $7M above the real one, so
  about half the real taxpayers are not taxpayers to it. Three-team trades 0 -> 5 (real ~8 a season).
- **Decision for you**: the trade AI's tax line (one line of code) disagrees with the line the screens show. Fixing it
  alone gave the best first deadline yet (16 trades, 14 -> 10 taxpayers; real 14 -> 7) but broke year two (21 of 30
  teams in the tax, a 6-trade deadline), because free agency lets payrolls run past the real line. Both need fixing
  together; details below.

## The real rule and its sources
- **Who pays**: a team whose salary on the last day of the regular season is over the tax line pays the tax (the bill
  is fixed by end-of-season salary, so a deadline deal saves a full year of tax). Playoff bonuses can change it a
  little afterwards.
- **Where the money goes**: the agreement lets up to half of the tax collected go to the teams that did not pay tax,
  in equal shares; the league has distributed exactly half in recent seasons and kept the other half "for league
  purposes" (it funds revenue sharing).
- **When**: bills are invoiced after the season and the shares are paid in July (ESPN 2013: payments due July 24,
  distributions by July 29).
- **How big**: 2024-25: 10 taxpayers paid $461.2M, each of the 20 other teams got $11.5M. 2025-26: before the
  February 2026 deadline 14 teams were projected to pay and the share was about $13.8M; after it, 7 taxpayers
  ($223M) and a share of about $4.9M, because **Boston, Denver, Phoenix, Dallas, Philadelphia, Orlando and Toronto all
  got under the line with deadline moves** (and Cleveland cut its bill from about $164M to $69M). The real deadline
  moves in `data/research/real_trades/trades_2025_2027.json` tagged "tax move" are of that kind: Dallas (Anthony Davis
  deal), Boston (Simons for Vucevic, plus three small dumps), Philadelphia (McCain), Cleveland and Minnesota (Saric,
  Conley legs of three-team deals), and the grouped minor deals (Orlando, Denver, Toronto, Phoenix).
- Sources: Hoops Rumors glossary "Luxury Tax Penalties" (Nov 2024, quoting Larry Coon's CBA FAQ); Hoops Rumors
  "Projected NBA taxpayers for 2025/26" (Feb 2026 and Apr 2026, from Bobby Marks and Eric Pincus); ESPN (2013) on
  payment dates; NBA.com 2026-27 cap release (tax line $200.428M).

## What changed

### 1. The tax payout counts in AI trade decisions (`trade_tax.py`)
- **Expected share**: half of the tax every other team is on course to pay this season (today's payrolls, repeat
  taxpayers at their rates), split among the teams on course to stay under, the team itself included. The projection
  shrinks as other teams get under, as the real one did in February 2026.
- **When it counts**: only when a deal moves the team's end-of-season payroll across the line. Getting under earns
  the share; going over loses it. So a team just over the line has a strong reason to shed a contract, and a team just
  under has a reason not to absorb one. The team's end-of-season payroll includes the minimum contracts it must sign
  to reach 14 players (a 2-for-1 dump that leaves 13 players needs a fill).
- **Only the open season** counts (the current one until the regular season ends). AI teams only; the human team's
  own evaluations never change.
- It is part of the tax money term, so it reaches everything that uses it: the acceptance check, the target search's
  quick price, the seller's asking price, the salary-dump search, the tax-relief legs of three-team deals, and the
  rule that tax savings justify paying picks.
- **Reasons and notes** say so in plain words: *"PHI (retooling) moved Dean Wade ($9.0M) to get under the luxury tax
  line (about $4.2M of tax saved, plus its share of the tax payout to teams under the line, about $2.6M), paying 1
  second-round pick; NOP (rebuilding) had room under the tax and took him for the picks."* The evaluation note adds
  "including its share of the tax payout for ending under the line (about $XM)".

### 2. The payout is recorded in the save, and shown with the team's finances
- New additive save field `luxury_tax_payouts` ({season: total tax, half distributed, half kept by the league, share
  per team, taxpayers, recipients, each team's bill and payout, assessed date, July payment date}). It is written once,
  at the same moment as step 4's payroll history (when the postseason starts, which is the real assessment date: the
  last day of the regular season). Paid "July 15" of that year.
- `save.team_cap_summary` returns the team's latest record (`tax_payout`), and the free-agency **Cap position** panel
  shows it as a fourth box: "Tax payout 26-27 +$2.0M" (or "Tax bill -$X" for a taxpayer), with the rule in the
  hover text. That is the only place the game shows team finances.

### 3. Draft-night chains (`play.best_ai_draft_chain`, `multi_team_trades.draft_chain_accept`)
- The real shape (June 2026): Memphis on the clock at 16 sent 16 to Oklahoma City (Stirtz) and 17 to Detroit
  (Okorie) and moved down to 21 with five seconds; New York shuffled 24, 25 and 30 among three teams for seconds.
- Here: when a team trades up to the pick on the clock and pays with its own lower pick, that lower pick can go
  straight on to a third team that targets a prospect there and pays the team on the clock with a still-lower pick of
  its own plus seconds. The team on the clock trades down twice in one deal.
- Each buyer's target comes from its own scouts' board and GM choice (`draft.preferred_prospect_for_pick`, the same
  call the live draft makes), with the first buyer's target and the prospects the draft has going in between removed.
  A buyer trades up only for a prospect it ranks above that pick, at the same prices as a plain trade-up.
- Acceptance: the team trading down accepts on its own evaluation and clears the pick's floor; each buyer's net plus
  what its target is worth to it clears its threshold (the plain trade-up rule). The settlement re-checks the deal
  under the same rule. A chain is chosen only when the team trading down does at least as well as in the best plain
  trade-up.
- Every team's reason is stored on the trade: *"Three-team draft-night trade: IND traded up to pick 12 for Braylon
  Mullins, number 7 on its draft board; PHX traded up to pick 22 for Flory Bidunga, number 10 on its draft board (the
  pick IND gave up); ORL traded down from 12 to 24 and collected 4 picks in all."*

### 4. Draft-night trades across the whole draft (`play.maybe_run_ai_draft_trades_before_pick_state`)
- Cause: the five-trade budget was spent first-come in pick order, and a "quiet market" rule loosened the floors from
  pick 11 until five trades had happened, so all five landed at 11-18.
- Now each part of the draft has its own share: top 10, 11-20, 21-30 and round two, at most two trades each, five in
  all. The floors loosen only inside a part that has had no trade by its middle pick (never in the top 10).
- **Round two is open** (picks 31-60): a team moves up with its own lower second plus future seconds, or buys a
  second-round pick with future seconds; never a first for a second. From pick 21, a team may move up with an early
  second (real 2026: #35 to #26, #34 to #29).
- No dice: the same deterministic search as before.

### 5. Recent draft picks are protected by years in the league (`trade_targets.recent_draft_pick`)
- **Why step 1 did not protect Stirtz**: the investment memory (draft slot, traded up) is a share of the player's
  *current* value to his team (`trade_ownership.own_player_premium`: 5% + 4% for trading up, then x0.75 because the
  team is over the tax). For a bench rookie that value is small, so the premium was a point or two against a tax
  saving worth 20+. The dump search's only other guard was an age floor (24), and Stirtz was 24.
- **Now**: the salary-dump search and the tax-relief leg of three-team deals skip any player drafted in the last three
  drafts (his first three NBA seasons), whatever his age; undrafted players keep the age-24 floor. He can still be
  traded in a real deal for value. In the before run Oklahoma City again dumped Stirtz for tax savings (Feb 2028); in
  the after run nobody dumped a recent pick.

### 6. Offers to the user's team
- **Reason shown**: the offers panel now prints the offer's reason under the package ("Why: ..."), for every offer
  that has one (absorber offers, target-search offers). One line in `offerCard`.
- **Why no absorber offer reached the user in step 4**: the two AI teams in the deal had to accept *outright*, while
  the AI-only three-team deals built from the same near-misses use the bounded negotiation rule (each main team at
  most 9 short, the two together at least -2). A near-miss is by definition a deal one team is short on, and the
  payment picks leave one side, so outright acceptance almost never held. Now the offer uses the same bounded rule
  for the two AI teams, and the settlement re-check after the user accepts uses it too (`bounded_ai_acceptance`).
- A second limit remains: the absorber must stay under the tax line after taking the contract, and in the test the
  user's team is Golden State, a taxpayer all run, so it can never be offered one there.

## Before and after against real
Two-season probe, seed 17, GSW hands-off, 94-input ratings, 2026-10-20 to 2028-11-01, run one at a time on the same
base. **Before** = 9f17e77 (step 4 merged with the unused-ratings work; this differs from step 4's own "after" run,
57 trades, because the unused-ratings merge changed the league). **After** = this branch (checkpoint d574a2b; later
commits change no behaviour). **Experiment** = after plus the real tax line in the trade AI (not kept, see decision 1).

| Measure | Before | After | Experiment (real tax line) | Real |
|---|---:|---:|---:|---:|
| Trades, whole run (2026-27 / 2027-28 / summer 2028) | 62 (25/28/9) | **60** (23/27/10) | 59 (28/22/9) | ~110 |
| ... deadline week, per season | 14 / 10 | **12 / 10** | 16 / 6 | ~23 |
| ... draft night, per draft | 5 / 5 | 5 / 5 | 5 / 5 | ~5 |
| ... draft-night picks traded (top pick of each deal) | all 11-16 | **11-20: 4, 21-30: 4, 31: 2** | same split | 2026: 16-17, 21-30, 34-56 |
| Three-team trades | 0 | **5** (4 draft chains, 1 tax-relief leg) | 7 (5 chains, 1 absorber, 1 missing piece) | ~8 a season |
| Teams over the line entering deadline week -> at season end, 2027 | 10 -> 7 | 10 -> 6 | 14 -> 10 | 14 -> 7 (2026) |
| ... 2028 | 13 -> 12 | 11 -> 11 | 21 -> 21 | |
| Teams that got under in deadline week (2027 / 2028) | 4 / 2 | 4 / 1 | 4 / 1 | 7 (2026) |
| Tax payout per team under the line (2026-27 / 2027-28) | not modelled | $2.0M / $4.3M | $4.4M / $26.2M | $11.5M (2024-25), $4.9M (2025-26) |
| Tax moves (tax money in a team's decision) | 30 | 28 | 35 | 12 of 43 real trades |
| Two-team salary dumps (with a pick) | 14 (5) | 14 (**8**) | 13 (5) | real dumps usually carried 1-3 seconds |
| Recent draft picks dumped for tax money | 1 (Stirtz, Feb 2028) | **0** | 0 | ~0 |
| Players traded 2+ / 3+ times | 10 / 1 | 7 / 2 | 11 / 0 | rare |
| Rebuild sales | 12 | 14 | 11 | the most common real trade |
| Young starters moved | 0 | 1 (a fair-value target-search deal) | 1 | |
| Rebuilding team takes a 30+ player on $15M+ for 2+ years | 1 | 1 | 0 | ~0 |
| Trades with every team's reason | 58 of 62 | 59 of 60 | 56 of 59 | |
| Odd phase labels at the deadline | 1 | 0 | 0 | |
| Absorber offers that reached the user's team | 0 | 0 (GSW is over the tax all run; see 6) | 0 | |
| Trade-search evaluations, whole run | 8,848 | 4,186 | 5,475 | |
| CPU seconds, whole run | 1,266 | 1,293 (+2%) | 1,330 | |
| ... deadline 2027 (1 step) / 2028 (2 steps) | 60.2 / 110.6 | 56.7 / 101.9 | 64.1 / 92.4 | |
| Draft night, 2027 draft on the same save (lab) | 33.9 s | 31.7 s | | |

How to read it:
- **The step 1-4 gains hold**: reasons on almost every trade, no odd labels, dumps more often carry a pick (8 of 14),
  rebuild sales steady, no Stirtz-type dumps, speed unchanged. Players traded twice 10 -> 7 is within one seed's noise.
- **The payout works at the margin**: dumps now say "to get under the luxury tax line (about $2.6M of tax saved, plus
  its share of the tax payout, about $2.7M)" (Miami, Philadelphia, Atlanta), and teams just under no longer absorb
  salary that would push them over. But the in-game payout is small, so it changes few decisions, and the volume is
  the same within noise.
- **Why the payout is small**: the game's tax-line constant is the real 2026-27 line ($200.4M), and the screens, free
  agency and waivers use it (`save.cap_lines_for_season`). The trade code (`transactions.cap_lines_for_season`) counts
  cap growth from 2025-26 instead, so the trade AI's 2026-27 line is $207.4M (and its hard cap $229.4M). The seven to
  ten teams between the two lines are taxpayers on screen but not in trade decisions, so the pool is about a third of
  the real one and fewer teams have a reason to duck. The new payout record follows the trade AI's line, so a team the
  Cap position panel shows slightly over the line can still show a payout; decision 1 removes that mismatch.
- **Teams that duck can slip back over**: Atlanta shed Bones Hyland at the 2028 deadline "to get under the line" and
  claimed Chris Paul off waivers two days later, ending $0.5M over. Waiver claims and roster fills (`waivers.py`,
  `save.py`) do not consider the tax line or the payout.
- **Draft night**: before, all ten draft trades were at picks 11-16; after, four at 11-20, four at 21-30, two at 31.
  No top-10 trade in either draft (none in the real 2026 draft either). Every draft trade passes every team's own
  evaluation (buyers with what their target is worth to them), as before.

## The new trades, read like a person
**Draft-night chains** (after run):
1. **2027, picks 12 / 22 / 24.** Orlando was on the clock at 12. Indiana moved up to 12 for Braylon Mullins (7th on
   its board) with its own 22 and two seconds; Phoenix took that 22 for Flory Bidunga (10th on its board), paying
   Orlando the 24 (Minnesota's pick) and a 2034 second. Orlando slid from 12 to 24 and collected four picks.
   **Textbook** in shape (Memphis's 16/17/21); Orlando's slide (12 slots) is longer than Memphis's (5). Both buyers
   drafted their targets.
2. **2028, picks 11 / 16 / 24.** Utah on the clock at 11; Memphis moved up for Emanuel Klein Stojanovic (1st on its
   board) with its 16 and a second; New York took 16 for Kager Knueppel (5th) and paid Utah its 24 and two seconds.
   **Mostly**: Sacramento then traded up to 12 in the next chain and took Knueppel, so New York drafted Alonzo DaSilva
   Jr. at 16. That happens in real drafts, but New York's stated reason no longer matched its pick.
3. **2028, picks 12 / 20 / 23.** Portland on the clock at 12; Sacramento up for Knueppel (5th) with its 20 (Detroit's)
   and two seconds; Denver took 20 for DaSilva (5th) and paid Portland its 23 and a second. DaSilva was gone at 16, so
   Denver drafted Malachi Moreno.
4. **2028, picks 21 / 22 / 26.** Philadelphia on the clock at 21; Charlotte up for Darius Wabbington (5th) with its
   22 (Minnesota's) and a second; Boston took 22 for Jordan Page (14th) and paid its 26 and a second. **Textbook**, a
   small slide like the real one; both drafted their targets.

12 of the 14 draft-night buyers drafted the prospect they traded up for; the two misses were the 2028 cascade above.

**Other draft trades**: Cleveland to 11 for Dylan Mingo (1st on its board), Dallas to 21 for Cameron Williams (1st),
Utah to 23 for Tyler Tanner (5th), Phoenix to 25 for Najai Hines (14th), and two moves to pick 31, the first pick of
round two (Milwaukee for Toni Bryant with its 35; Houston for Tobias Griffin-Ogunleye), priced in seconds.

**Three-team tax relief (Jan 2, 2028, MIA / PHI / MEM)**: Miami (retooling) gets Anfernee Simons (expiring) from
Philadelphia (rebuilding) for Gary Harris and Miami's 2028 first, and adds Dru Smith ($2.9M) with a 2034 second to
Memphis, which has room but a full roster, so it sends back its least-used minimum player (Scotty Pippen Jr.).
**Textbook in shape** (Cleveland's Saric leg); Pippen back is a roster necessity, not value.

**Tax moves at the deadline** (after run): Miami (Klay Thompson, $5.8M, with a second) and Philadelphia (Dean Wade,
$9.0M, with a second) got under the line for the tax and the payout; Atlanta (Bones Hyland) got under, then went back
over through a waiver claim; San Antonio (Terry Rozier with a second), Toronto (Malachi Smith with a second), the Lakers
(Dalton Knecht) and Minnesota (Terrence Shannon Jr.) cut their bills and stayed over. These match the real deadline
patterns (Boston's small dumps, Philadelphia's McCain move, Cleveland's Saric leg).

## Decisions for the user
1. **The trade AI's tax line.** The trade code's lines are $7M above what the screens show. The fix is one line in
   `transactions.cap_lines_for_season` (count growth from 2026-27, as `save.py` does). In the experiment it gave the
   most realistic first deadline so far (16 trades; 14 teams over entering the deadline, 10 at the end; real 14 -> 7),
   but in year two 21 of 30 teams were in the tax (median payroll $211M against a $207M line), the payout was $26M a
   team, few teams had room to absorb salary, and the deadline had 6 trades. It also changes the user's trade finder
   (its hard-cap check uses the same function; two foundation tests then found no candidates), which this task must
   not touch. So it is **not** in this branch. Recommended: fix the line together with payroll discipline in free
   agency, re-signing and waiver claims (a team under the line should not sign or claim its way over it after the
   deadline). That is `save.py` / `waivers.py` work, and the user's trade finder needs a check at the same time.
2. **Chain slides**: the team trading down can fall 12-13 slots (Orlando 12 -> 24); real chains moved 5-8. Limiting
   the second buyer's pick to within about 6 slots of the first would bring them closer, at some cost in chain count.

## What is still wrong / left
- Deadline volume is still about half of real (12/10 vs ~23); the payout cannot fix that alone at this tax line.
- Teams get back over the line after the deadline through waiver claims and roster fills (Atlanta 2028).
- Chains are built pick by pick, so a later trade-up can take an earlier chain buyer's target (2 of 14 buyers).
- No top-10 draft trades in either test draft (the top-10 floors are unchanged and strict).
- Absorber offers still never reach the user in the test, because Golden State is a taxpayer all run (an absorber must
  stay under the line). The acceptance cause is fixed and tested.
- Repeat taxpayers still need three seasons of history; getting under to reset the repeater clock is not valued.

## Tests and checks
- New `tests/test_trade_taxpool.py` (14 tests): the share (half of the others' tax, split among teams under, own bill
  excluded); getting under earns it, going over loses it; a short roster must be filled before it counts as under; AI
  teams only; the evaluation note; the payout record (equal shares, paid in July, written once) and the finance
  summary; recent draft picks protected by years in the league, and the dump search skips them; bounded acceptance for
  absorber offers; the draft budget by part of the draft; round-two offers never include a first; pick destinations
  for multi-team deals; chain acceptance. New `tests/trade_offer_reason.test.cjs` (the offers panel shows the reason).
- `test_trade_step4`, `test_trade_2b`, `test_trade_targets`, `test_multi_team_trades`, `test_draft_boards`: OK. The
  trade, market, contract, salary, pick, draft and team-planning modules plus `test_foundation` and
  `test_deadline_speed_exact` (625 tests): the only failures came from the tax-line experiment (two trade-finder tests;
  reverted) and the draft-night hook test (fixed: the hook calls the patchable plain-candidate function); all three
  pass on the final branch. `scripts/run_core_tests.sh`: **337 OK** (2 skips).
- Scorecards (`calibration_report.py --games 20`, `validate-season-probabilities --runs 5 --limit 20`), base vs after:
  **identical output**. Nothing here touches the game simulation.

## Files
- `trade_tax.py`: the payout share in `tax_saved` (`tax_pool`, `pool_share_if_under`, `pool_change`), wording
  (`saving_words`, `tax_note`), the payout record (`season_tax_payout`, written by `record_season_payrolls`) and
  `team_tax_payout_summary`.
- `trade_targets.py`: recent-draft-pick protection in the dump search; dump reasons use the payout wording.
- `multi_team_trades.py`: draft-chain acceptance and its settlement re-check; bounded acceptance for absorber offers
  to the user (search and settlement); tax-relief reasons mention the payout; recent picks protected in tax-relief legs.
- `play.py` (draft-night trade path only): budget by part of the draft, round two open, early seconds from pick 21,
  chains, multi-team headlines and pick ownership.
- `save.py`: one additive key in `team_cap_summary` (`tax_payout`).
- `gui/app.js`: the offer's reason in `offerCard`; the payout box in the free-agency Cap position panel.
- `scripts/trade_probe_metrics.py`: draft-night slots and parts, teams over the line around the deadline, payouts.
- Tests: `tests/test_trade_taxpool.py`, `tests/trade_offer_reason.test.cjs`.

## Resume state
Done: code, tests, three two-season probes (before, after, tax-line experiment), metrics, trade read, scorecards, core
tests, report, board row, commits on this branch (not pushed or merged). Local outputs: `output/taxpool/results/`
(metrics and trade lists: `before`, `after`, `final` = the experiment), `output/taxpool/{base-src,after-src,exp-src}/
output/*_inputs_v1/` (probe saves), `output/taxpool/scorecards/`, `output/taxpool/lab/` (draft-day save `draft2027`,
lab scripts). Next: decision 1.
