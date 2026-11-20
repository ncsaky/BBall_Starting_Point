# Trade volume: one shared tax line, AI payroll discipline, your free-agent offers judged like rival bids (2026-11-20)

_Claude (Opus agent), branch `worktree-agent-a1979caf8ef6289da` (from main at 6dba361). Follows `trade-taxpool.md`
(its decision 1) and `fa-redesign.md` (its question 1). Status: **review** (committed on the branch, not pushed or
merged)._

## TL;DR
- **Payrolls now behave like the real league.** One tax line everywhere ($200.4M in 2026-27), and AI teams plan
  around it in re-signing, free agency and waiver claims. Year two had 21 teams over the line entering the deadline
  (23 at season end); now 9 and 8 (real: 7-14 at the deadline, 6-8 at season end). The Atlanta-style waiver claim
  back over the line is gone.
- **Your free-agent offers now compete with rival bids** under the same rule: you pay about his market price (more on
  day 1, when everyone's bar is high) and can lose him to a better bid. Brandon Miller's $13.6M deal is no longer possible.
- **Trade volume did not come back: 63 trades in two seasons (real about 110), deadline weeks 16 and 10 (real about
  23).** Payroll realism helped the deadline a little (26 deadline trades either way, now spread 16/10 instead of
  12/14), but the shortfall is in the trade AI itself; see "What's left".

## What changed

### 1. One tax line for the whole game (`cap_rules.py`)
- New module with the real 2026-27 numbers (NBA announcement, pr.nba.com "NBA sets Salary Cap for 2026-27 season at
  $164.961 million"; aprons as reported by Bleacher Report from the league's figures): salary cap $164.961M, tax line
  $200.428M, first apron $209.015M, second apron $221.686M (the game's hard cap), growing 3.5% a year from 2026-27.
- The trade code, the screens and free agency, the news text, waivers and the stretch rule all call it. Before, the
  trade code counted growth from 2025-26: its 2026-27 tax line was $207.4M and its hard cap $229.4M while everything
  else used $200.4M / $221.7M. Waiver claims and the stretch limit used the 2025-26 salary cap ($154.6M); they now use
  the 2026-27 cap ($165.0M).
- **Your trade finder still works.** It now sees the real lines, so two of its tests had to change player: Dailyn
  Swain's only acceptable offer came from Detroit at $199.6M, which taking his salary would now push into the tax, so
  Detroit (correctly) declines. The tests now shop Patrick Williams, who has several offers under the real line.
  Nothing else in the finder changed; your own team's evaluations never count the tax.

### 2. AI payroll discipline (`payroll_plan.py`)
AI front offices now plan their end-of-season payroll before they re-sign, sign, claim or pick up a released player:
- **Projected payroll** = this season's salary plus dead money plus the minimum contracts still needed to reach 14
  players (a signing that fills one of those spots replaces a minimum deal the team must sign anyway).
- **What going over costs**: the tax bill it adds (real rates; repeat taxpayers at theirs) plus, when it crosses the
  line, the payout share it gives up. The share is the last recorded payout per team, or $8M before any season is
  recorded (between the real $4.9M for 2025-26 and $11.5M for 2024-25).
- **What the owner will pay** for one player: $30M of tax plus lost payout for a team at its peak, $10M on the rise,
  $4M retooling, nothing rebuilding; divided by the owner's money factor (the trade code's financial discipline,
  0.7-1.4) and scaled by how much the player matters (nothing under 12 minutes, full at 28, up to 1.5x for a star;
  1.5x more for keeping your own free agent).
- **Room by phase**: a team that is not contending keeps payroll room below the line when it adds a player in free
  agency or re-signing: $3M on the rise, $8M retooling, $20M rebuilding; half that for a player 25 or younger, half
  again for re-signing a starter. Without it, every team with room spent to the line (first test: 18 of 30 teams
  ended 2027-28 within $5M under it, one had real room, so nobody could take a salary dump).
- **After the trade deadline** a team under the line never adds salary that puts it over (a trade can no longer fix
  it). This is the Atlanta case: in the tax-pool run Atlanta shed Bones Hyland to get under at the 2028 deadline and
  claimed Chris Paul off waivers two days later.
- Where it applies: AI re-signing (both offseason passes, with earlier re-signings in the same pass counted), AI
  free-agent bids and their acceptance at the end of the day, the offseason "strategic" signings, in-season signings
  of released players, and waiver claims. Required minimum roster fills are unchanged. Your team is never restricted.

### 3. Your free-agent offers follow the rival bids' rule (`play.py`, `app_actions.py`, `gui/app.js`)
- Before, a free agent took your offer if it reached his projected minutes x $0.45M, whatever his market: Brandon
  Miller (ask $28.8M, rival bid $30.4M) signed with you for $13.6M.
- Now your offer gets the same interest score rival bids get (salary against his market ask, years against the years
  he wants, your team's role, fit, winning, market and security), and he signs only if it reaches **today's bar** (the
  bar drops each day of free agency) and **beats the best rival bid** (higher interest, or equal interest and more
  money: the order he settles bids in at the end of the day). Rival bids for the day are placed before you can act,
  so answering at once gives the same result as waiting for the end of the day. He also never signs for less than 90%
  of his current ask (the lowest share any AI team bids), so a star cannot be had for half his price on day 5.
  A non-guaranteed offer counts as a smaller salary, as before.
- Outside the open market (your exclusive re-signing window, or a free agent during the season) there are no rival
  bids and the bar is his market ask for the years he wants from an average team.
- **The room shows the real rule.** "Signs with you from" is now computed by that rule for the length you pick (the
  payload has the price for every length and guarantee, `accept_floor_by_years`, plus the bar and the best rival
  bid, `offer_rule`), or "Not today" when no salary beats the leading bid. "Market ask" is now the ask the engine
  judges against (it was a slightly different fallback). The wording on the market and rival-bid panels says your
  offer faces the same rule. A turned-down offer records why ("a rival bid interests him more" or "below today's bar")
  and what he needed.
- Checked on a real day-1 free-agency save (2027, the test league), offering as Golden State:

| Free agent | Market ask | Old price from you | Now (4 years, guaranteed, day 1) | Best rival bid |
|---|---:|---:|---:|---|
| Jimmy Butler III | $33.6M | $14.0M | $40.9M | MEM $36.0M |
| Cameron Johnson | $25.0M | $13.5M | $30.3M | MIL $24.7M |
| Donte DiVincenzo | $23.9M | $13.5M | $29.4M | MEM $26.6M |
| Bilal Coulibaly | $23.0M | $10.8M | $25.2M | none |

  Day 1's bar is high for everyone (no rival bid cleared it either); by day 3 the same players cost about their ask
  unless a rival has bid more. Offers at the old price and at the ask were turned down; the shown price was accepted.

## Before and after against real
Two-season probe, seed 17, Golden State hands-off, 94-input ratings, 2026-10-20 to 2028-11-01, one run at a time.
**Before** = main at 6dba361. **First fix** = the shared line plus the tax plan, without room by phase (checkpoint
f59fb3c). **After** = this branch (3a9da59 + aa3fe3f; later commits change no behaviour). Taxpayers are counted at
the real line in every column (the before run's save recorded the trade code's $207.4M / $214.7M lines).

| Measure | Before | First fix | After | Real |
|---|---:|---:|---:|---:|
| Trades, whole run (2026-27 / 2027-28 / summer 2028) | 68 (23/31/14) | 61 (28/23/10) | **63** (28/27/8) | ~110 |
| ... deadline week, per season | 12 / 14 | 16 / 6 | **16 / 10** | ~23 |
| ... draft night, per draft | 5 / 5 | 5 / 5 | 5 / 5 | ~5 |
| ... in-season (not deadline week) / offseason | 12 / 20 | 12 / 17 | 13 / 14 | |
| Three-team trades | 5 | 7 | **8** (6 draft chains, 1 absorber, 1 tax relief) | ~8 a season |
| Teams over the line entering deadline week -> season end, 2027 | 13 -> 15 | 14 -> 10 | **14 -> 10** | 14 -> 7 (2026) |
| ... 2028 | 21 -> 23 | 11 -> 11 | **9 -> 8** | 7-14 -> 6-8 |
| Teams that got under the line in deadline week (2027 / 2028) | 4 / 0 | 4 / 0 | 4 / **2** | 7 (2026) |
| Tax payout per team under the line (2026-27 / 2027-28) | $8.2M / $32.2M at the real line ($2.0M / $5.6M recorded at the trade code's line) | $4.4M / $5.1M | **$4.4M / $3.2M** | $11.5M (2024-25), $4.9M (2025-26) |
| Median payroll against the line, end of 2027-28 | +$7.1M | -$0.1M | -$2.7M | |
| Teams $8M+ under the line, end of 2027-28 | 1 | 1 | 5 (9 in January) | |
| Two-team salary dumps (with a pick) | 15 (8) | 16 (11) | 15 (8) | real dumps usually carried 1-3 seconds |
| Players traded 2+ / 3+ times | 10 / 2 | 5 / 1 | 8 / 1 | rare |
| Rebuild sales | 13 | 10 | 11 | the most common real trade |
| Young starters moved | 2 | 0 | 0 | |
| Rebuilding team takes a 30+ player on $15M+ for 2+ years | 0 | 0 | 0 | ~0 |
| Trades with every team's reason | 63 of 68 | 59 of 61 | 62 of 63 | |
| Odd phase labels at the deadline | 0 | 0 | 1 | |
| 2028 free agency: market signings / re-signings / waiver claims | 106 / 37 / 7 | 107 / 37 / 3 | 106 / 39 / 17 | |
| 2028 market signings: salary as a share of his ask (median, middle half) | 1.10 (1.02-1.16) | 1.07 (1.00-1.14) | 1.09 (1.03-1.13) | |
| CPU seconds, whole run (2028 deadline, 2 steps) | 1,283 (102) | 1,250 (91) | 1,175 (97) | |

How to read it:
- **Taxpayers are realistic in both years.** The first fix alone (shared line plus the tax plan) stopped the runaway
  (21 -> 11 teams over in year two) but left 18 of 30 teams parked within $5M under the line, with only one team that
  had real room, so nobody could take a salary dump and the 2028 deadline had 6 trades. Room by phase gave 5-9 teams
  real room again, and the 2028 deadline went back to 10 trades, with two teams getting under (Toronto, Phoenix).
- **The payout is small** ($3-4M) because few teams are deep in the tax; real seasons range from $4.9M to $11.5M. It
  follows the league, as the real one does.
- **The step 1-4 gains hold**: reasons on 62 of 63 trades, no young starters moved, no rebuilding team taking a big
  veteran contract, dumps still carry picks about half the time, three-team trades up to 8 (all with stated reasons).
- **Waiver claims went from 7 to 17 in the 2028 offseason**: claims need room under the salary cap unless the contract
  is a minimum, and the cap is now the real $165.0M instead of the old $154.6M (2025-26) figure. Real claims run
  10-20 a season, but this is worth watching.
- **Free agency**: the same number of signings; AI teams pay about 1.09x the ask, as before. Your offers now face the
  same bar (see section 3).
- **Speed**: unchanged or slightly faster (the free-agency room payload adds about 0.5 seconds for the price table).
- **Game results are untouched**: nothing here touches the game simulation (odds check below).

## The biggest trades and signings, read like a person (after run)
1. **Summer 2028, Milwaukee / Charlotte.** Rising Charlotte gets Tyler Herro (28, $26.4M for two seasons) for Naz Reid
   ($26.7M), T.J. McConnell (36, expiring), Hannes Steinbach (22) and a first. Rebuilding Milwaukee turns a
   28-year-old into youth and picks. **Textbook.**
2. **Summer 2027, Orlando / Cleveland.** Retooling Cleveland gets Jalen Suggs (26) as James Harden's successor for
   Jarrett Allen ($30.2M, 29) and two seconds; rebuilding Orlando takes the older, shorter contract. **Mostly
   textbook**: a rebuild taking Allen rather than picks is a stretch.
3. **Deadline 2027, New Orleans / San Antonio.** Contending San Antonio gets Trey Murphy III (26, $27M) for Kornet,
   Champagnie, Carter Bryant (21) and a first. **Textbook** contender buy.
4. **December 2027, Milwaukee / Minnesota.** Contending Minnesota gets Cameron Johnson (31) for Rudy Gobert's expiring
   $38M plus two seconds: rebuilding Milwaukee sells a veteran for an expiring contract and picks. **Textbook.**
5. **Deadline 2028, Atlanta / New York.** Retooling New York gets Onyeka Okongwu (27) for Josh Hart (32, expiring) and
   two seconds. **Textbook** retool.
6. **Deadline 2028 tax moves**: Cleveland moved Sam Merrill ($9.8M) to New Orleans and cut its tax bill by about
   $38M; Oklahoma City moved Jared McCain with a second to Memphis; Boston moved Baylor Scheierman to Orlando;
   Washington moved Khris Middleton with a second "to get under the luxury tax line (about $4.7M of tax saved, plus
   its share of the payout, about $3.7M)". The same shapes as the real February 2026 moves.

Signings (2028 market): Jimmy Butler III to the Clippers for one year at $36.0M (ask $33.6M), Zach LaVine to Memphis
($22.9M x 3), Bilal Coulibaly to the Clippers ($20.2M x 4), Nikola Jokic re-signed by Denver at $19.8M x 3 (ask
$17.8M; see "What's left": star asks in later seasons are too low). The rebuilding Clippers signed three free agents
for about $74M; they had cap room, so the room-by-phase rule allowed it.

## What's left
- **Trade volume is the trade AI's, not the payroll's.** With realistic payrolls and real absorbers, the run still makes
  63 trades against about 110, and deadline weeks of 16 and 10 against about 23. The tax moves now look right; what
  is short is ordinary trades outside the deadline (13 in-season and 14 offseason trades in two seasons). Next levers,
  in the trade AI: more teams searching on a normal day, more target kinds (backup-quality role players, expiring
  contracts for contenders), and the daily trade-slot limits.
- **Star free agents are priced from minutes after the first summer.** The market ask comes from precomputed market
  research only for the 2026 and 2027 classes; later free agents ask minutes x $0.48M (Nikola Jokic asked $17.8M in
  2028, Kevin Durant $14.4M), and the AI's own re-signing terms are capped at $32M. Everyone, you included, now pays
  about the ask, so the ask itself needs a real model (contract_ai has one) before the third season looks right.
- **Rebuilding teams with cap room still sign veterans** (the Clippers spent about $74M in 2028, including Jimmy Butler
  at 38 on a one-year deal). Room by phase limits how close to the tax they get, not what they buy.
- Waiver claims rose to 17 in the 2028 offseason with the real salary cap; worth a look if the wire feels busy.
- The payout is small ($3-4M) because few teams are deep in the tax; it follows the league.

## Tests and checks
__TESTS__

## Files
- `cap_rules.py` (new): the real cap lines, one function for every part of the game.
- `payroll_plan.py` (new): projected payroll, tax and payout cost, owner budget, room by phase, the deadline rule.
- `transactions.py`, `save.py`, `narrative.py`: `cap_lines_for_season` / `cap_lines_for_narrative` call `cap_rules`;
  the old constants are imported from it.
- `save.py`: AI re-signing (`ai_re_signing_fits_payroll_plan`, `ai_re_signing_allowed`, both offseason passes),
  strategic offseason signings, in-season released-player signings.
- `play.py`: AI free-agency bids and their end-of-day acceptance; the user offer rule (`user_offer_market_terms`,
  `user_offer_contexts`, `user_offer_interest`, `user_offer_verdict`, `user_offer_floor`, `user_offer_decision`) used
  by `manual_save_pool_signing`; the free-agency context score also returns its raw value.
- `waivers.py`: AI claims check the tax plan; claims and `release_planning.py`'s stretch limit use the real cap.
- `app_actions.py`: free-agency payload (`free_agent_offer_floors`; `accept_floor_millions`,
  `accept_floor_offer_millions`, new `accept_floor_by_years`, `offer_rule`; `ask_millions` is the engine's ask).
- `gui/app.js`: the offer builder's price for the chosen length, "Not today" when no salary wins, and the rule's wording.
- `scripts/trade_probe_metrics.py`: taxpayers and payout at the real line, free-agency signings by kind and share of ask.
- Tests: new `tests/test_trade_volume.py`; updated `tests/test_free_agency_room_payload.py`,
  `tests/free_agency_room.test.cjs`, `tests/test_foundation.py` (trade-finder player), `tests/test_trade_taxpool.py`
  (a payroll set for the real line).

## Resume state
Done: code, tests, three two-season probes (before, first fix, after; a fourth with veterans-only room was stopped
midway and replaced), metrics, trade read, report, board row, commits on this branch (not pushed or merged).
Local outputs (git-ignored): `output/tradevol/results/` (metrics and trade lists: `before`, `after1` = first fix,
`after3` = final), probe saves under `output/tradevol/{base,after1,after3}-src/output/*_inputs_v1/`, a day-1
free-agency save (`output/tradevol/lab/fa2027.pristine/`) and a resume checkpoint at the 2027 draft
(`output/tradevol/lab/resume_2027_06_25/`: copy into a probe's output folder to rerun only year two's offseason and
season). Next: the trade AI's volume and the free-agent ask model (above).


