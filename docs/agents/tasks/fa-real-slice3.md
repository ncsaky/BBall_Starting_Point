# FA-REAL slice 3: restricted free agency, offer sheets and matching

_Claude (Opus agent), branch `worktree-agent-aad20417c535ae44b` (from main at 5da7b81). Status: **review** (slice 3).
Committed on the branch only; not pushed or merged._

## TL;DR
- Other teams can now sign your young restricted free agents (players you sent a qualifying offer) to an **offer
  sheet**: a signed contract you have one day to **match** (keep him on exactly those terms) or let go. You can do the
  same to theirs from the free-agency room.
- The game stops for your Match or Pass with a countdown, the salary year by year, what matching does to your cap and
  any hard cap (a payroll ceiling you can't pass) that blocks it; your assistant GM texts you and gives his advice.
- AI teams bid rarely and for real reasons, and match unless they legally can't or the player is a pricey reserve:
  1 sheet in two replayed summers (matched); players taking the one-year qualifying offer fell from 7 and 4 to 3 and 0.

## How offer sheets and matching work (`src/nba_gm_data/offer_sheets.py`, new)
- **Who**: a restricted free agent is one his team sent a qualifying offer (slice 2). Another team can sign him only to
  an offer sheet; ordinary contracts stay blocked (`offseason_decisions.blocked_for_team`). Sheets open on July 1, the
  new league year (market day 2), like the real ones, and run until the October 1 qualifying-offer deadline.
- **Legal terms** (`sheet_terms`, CBA Art. XI §5):
  - 2 to 4 seasons; at least 3 if his team also made the maximum qualifying offer;
  - raises up to 5% of year one; fully guaranteed, no options and no bonuses (the game's contracts have none), so
    the CBA's bonus and option limits are met by construction;
  - the **Arenas rule** for players with 1-2 years in the league: year one at most the full mid-level ($15.044M in
    2026-27), year two at most 5% more; a "back-loaded" sheet may jump in year three to his maximum plus two 5% raises
    (year four +4.5%). The bidder counts the average every year and needs cap room for it; his own team counts the real
    salaries. The 2026-27 research example comes out exactly ($15.044M / $15.796M / $45.364M, test). No real sheet in
    2023-26 used the jump, so AI bidders never do; the user can ("Year-3 jump" in the builder).
- **How the bidder pays** (`bidder_quote`): cap room, the room mid-level, the full or taxpayer mid-level, the
  bi-annual, or a minimum contract for a minimum-salary sheet (all six real sheets used one of these: Dallas and
  Memphis the full mid-level, Utah the room mid-level, Oklahoma City the taxpayer mid-level, Atlanta and New York the
  minimum). Never Bird rights. The payment stays **reserved** until his team decides: `cap_ledger.reservations` now
  counts pending sheets, so the same room can't be promised twice (test: a $45M signing that fits without the sheet is
  refused while it waits). One sheet per player at a time.
- **The deadline**: real sheets delivered before noon are due the next night, at or after noon two days later; sheets
  in the July 1-6 moratorium are due July 7. The game has no clock and, by the user's decision, no moratorium (deals
  are official on agreement), so every sheet counts as delivered in the morning: **his team decides by the end of the
  next day**. AI teams decide on that day; a user's sheet waits for the user (below).
- **Matching** (`incumbent_quote`): the first-year salary must fit his team's Bird rights (full or Early Bird up to his
  maximum, Non-Bird its 120% limit), cap room or an exception, never past a hard cap the team already triggered (test:
  a hard-capped team with Bird rights can't match). If matched, his team signs him on the sheet's salaries year by year
  and he **can't be traded for a year**: the contract's trade date is set a year out, which the trade code already
  reads (`transactions.recently_signed_player_ids`), so no trade-file hook was needed. The game has no player-consent
  step, so the year's block covers both "not without his consent" and "never to the bidder". If his team passes (or
  time runs out), the bidder signs him on all terms with the reserved payment.
- **The player's choice** (`player_takes_sheet`): he signs a sheet when its first-year salary reaches what he will take
  now (his price plus his belief in himself, fading over the summer: slice 2's `rfa_reservation`) and at least his
  qualifying offer. Otherwise he waits, negotiates with his team, or signs the qualifying offer.
- **His price as a restricted player** (`leverage_price`, new): from the market's opening his price is no more than the
  most any other team could actually pay him in a sheet today (its cap room after reservations, or its biggest
  available exception). Above that he has no outside leverage, so he settles for less with his own team, as real
  restricted players did (Kuminga and Giddey in 2025, Duren in 2026). This is the main reason fewer players take the
  one-year offer.
- **Apron counts qualifying offers** (`cap_ledger.team_payroll`): apron salary now includes outstanding qualifying
  offers (CBA Art. VII §2(e)). A team can't use the mid-level in a way that hard-caps it below the cost of keeping a
  player it tendered. Before, Orlando, Utah and Washington used the mid-level, became hard-capped, and then lost their
  tendered starters to the one-year offer (and the accepted offer took them past the hard cap: 3 of main's 4 breaches
  in 2027).

### The AI (every decision states its reason; no dice)
- **Incumbents** (`incumbent_choice`) follow the evidence's rule, "match unless a hard cap prevents it" (5 of 6 right
  in 2023-26): a regular (18+ minutes) is always matched when legal; a near-minimum sheet is matched; a reserve is
  matched if the tax is within what the owner pays for him, else passed ("an expensive reserve ... Golden State passed
  on Quinten Post for the same reason"). The same rule is the assistant GM's advice to the user.
- **Bidders** (`ai_sheet_pass`, each market day from July 1 and once on July 15): for each unsigned restricted player
  25 or younger, every AI team with a legal way to pay, a role for him (its projected minutes) and an owner who accepts
  the cost (the slice-2 payroll plan) gets an appeal score: his value x how likely his team is not to match (can't:
  1.0, expensive reserve: 0.75, likely match: 0.30, +0.10 if his team is rebuilding) x role x front-office urgency
  (TRADE-MARKET trait, +/-40%). The best bidder signs a sheet when a hash of (save, season, day, player, team) falls
  under appeal x 0.16. That rate was set on the 2027 market (expected about 1.4 sheets, about two in three matched).
  Price: a little over his price (5%, up to 15% for an urgent office), capped at what the team can fund.
- **Planning**: an AI team holding an unsigned restricted regular doesn't use an exception that would hard-cap it below
  his price (`play.restricted_keep_cost`); and a team weighs re-signing him against the qualifying offer it would pay
  anyway if he signed it (only the salary above it is new money for the owner).
- **Random streams**: none added or moved. Bids use deterministic hashes; the rest are fixed rules.

## The user's side
- **Match or Pass** (offseason checklist window, top): "Offer sheet · BKN · signed Jul 2", a countdown ("1 day left" /
  red "Decide today"), salary by year, a table of payroll now / if matched / cap room / tax room / first-apron room by
  season, how he'd be paid (or "You can't match: hard-capped at the first apron ..."), the tax it adds, what matching
  and passing mean, the assistant GM's advice, and Match / Pass (with a confirmation). The room opens on this window
  when a sheet is waiting.
- **The game stops for it**: "Next Market Day" and "Finish First Wave" won't end the deadline day while your sheet is
  undecided ("Match or pass first: ..."), and "Continue To Late Summer" waits for any pending sheet (sheets signed on
  the last market day or in the July 15 pass). A multiplayer round timer lets it expire (he leaves: the real rule).
  Hands-off probes take the assistant's advice (`follow_advice`; one line in `scripts/overnight_market_health.py`).
- **Signing day "Still open"**: your decisions, your own pending sheets (with the payment still reserved) and the
  summer's settled sheets.
- **Offer sheets from the room**: pick another team's restricted free agent; the builder switches to offer-sheet mode
  (2-4 years, guaranteed, the legal payment routes only, "Year-3 jump" when he is in the Arenas band, his qualifying
  offer and "He signs a sheet from $X a year today"), the quote shows "Reserved until BOS decides", and the button
  says "Sign Offer Sheet". The market's bids column shows "Restricted · BOS" and "Sheet · MEM" when one is pending.
- **Assistant GM text** (one new type, target "offer-sheet"): "Cam Thomas signed an offer sheet with BKN: 3 years,
  $39.7M. We have until the end of 2027-07-03 to match." Tapping it opens the Match or Pass window.
- **Text room** (`play.py`): the free-agency room asks Match / Pass first when a sheet is waiting.
- **Rule 4 (screen = save)**: the room's quote, the sheet record and the contract written all come from the same
  `sheet_terms` / `bidder_quote` / `incumbent_quote` calls. Test: a $12.0M x 3 sheet quoted $12.0M / $12.6M / $13.2M
  and the contract saved after the decision is exactly that; in the replay the one settled sheet's contract equals its
  sheet (Sensabaugh, $15.10M / $15.86M / $16.61M).

## Measures: two summers from a fresh save, main against this branch
Seed 17, Golden State hands-off, `output/fa-real-slice3/lean_probe.py` (slice 2's harness plus the Match or Pass step),
main at 5da7b81 (`base`) against this branch at 9c327eb (`run`; later commits are the hands-off advice option and
screen polish). Metrics: `offseason_metrics.py` (finals copy to preseason copy).

| Measure | 2027 main | 2027 branch | 2028 main | 2028 branch | Real |
|---|---:|---:|---:|---:|---:|
| Offer sheets (matched) | 0 | **1 (1)** | 0 | **0** | 0-3 a summer, about 2/3 matched |
| Players who took the one-year qualifying offer | 7 | **3** | 4 | **0** | 0-2 |
| Qualifying offers sent (of eligible) | 14 of 31 | 14 of 31 | 14 of 25 | 14 of 25 | 10-13 of ~25 |
| Restricted players re-signed or matched by their team | 7 | 11 | 10 | 14 | most |
| Return to own team (all / AI teams) | 57% / 61% | 57% / 61% | 58% / 63% | **64% / 70%** | 45-55% |
| Teams using a mid-level | 17 | 17 | 20 | 21 | 18-23 |
| Hard caps triggered (first / second apron) | 15 / 1 | 13 / 1 | 18 / 1 | 18 / 2 | |
| Teams over a triggered hard cap on opening day | 4 | 1 | 0 | 2 | 0 |
| Teams over the tax / first apron, opening | 16 / 9 | 18 / 7 | 9 / 7 | 10 / 9 | 7-14 |
| Unsigned expiring players on opening day | 45 | 44 | 36 | 24 | |
| Offseason actions by the automated GM (stops) | 13 | 13 | 13 | 13 | |
| Offseason seconds (Finals to Oct 1) | 246 | 216 | 343 | 334 | |

How to read it:
- **The sheet**: July 2, 2027, Charlotte signed Utah's Brice Sensabaugh (21 minutes) to 3 years, $15.1M rising 5%, with
  the full mid-level: "a young player it wants, even if UTA is likely to match; it sees about 28 minutes for him".
  Utah matched the next day: "he is a regular (21 minutes) and teams keep their young regulars (paid with full Bird
  rights; it costs about $7.7M in tax)". 2028 had none. One sheet in two summers is inside the real 0-3 but on the
  low side of the real average (1.5); the matched share can't be judged from one sheet. The calibration replay of the
  2027 first wave (`calib.py`, before the last two planning fixes) also produced one sheet: Orlando, hard-capped after
  using its mid-level, could not match Charlotte's sheet for Anthony Black, the Dante case. That case can no longer
  arise from the AI's own mid-level use (the apron counts the qualifying offer now).
- **Qualifying offers taken** fell from 7 and 4 to 3 and 0, for stated reasons. The 2027 three: Noah Clowney and Jaime
  Jaquez Jr., whose qualifying offer ($13.9M, the starter-criteria amount) was at or above anything the market would
  pay (Cam Thomas 2025 is the real example), and Devin Carter, a Boston reserve his team wouldn't pay. Main's 2027
  seven were mostly teams that hard-capped themselves with the mid-level and then couldn't pay (Black, Coulibaly,
  Sensabaugh) or owners who wouldn't pay a price no other team could reach (Walker, Henderson).
- **Hard caps**: none of the branch's opening-day breaches come from sheets, matching or qualifying offers. Los
  Angeles 2027, Minnesota and Toronto 2028 went over through roster-repair minimum signings in September and one
  Minnesota offseason trade: the slice-1 known gap (roster repair and trades don't check a triggered hard cap yet).
  Main's 2027 breaches at Orlando, Utah and Washington were accepted qualifying offers on hard-capped teams; gone.
- **Return share**: 2027 is the same as main (57%); 2028 is higher (64% against 58%; real 45-55%, main is already
  above). Most of the difference is more Bird re-signings in the market (27 against 15): 4 more restricted players
  kept, and the rest unrestricted players re-signed after the 2027-28 season played out differently on the two
  branches. Not isolated; logged under "What's left".
- **Stars**: every top-30 expiring player whose AI team held his rights stayed in both summers on both branches
  (`stars_*.txt`). Movers: Golden State's (hands-off), Anthony Davis (retired), and in branch 2028 Zach Edey (Memphis
  renounced his rights to open room, which also ends the restriction, then he signed with Charlotte) and Ivica Zubac
  (Toronto hard-capped itself with the mid-level on Julius Randle and couldn't keep him).
- **Stops**: the same 13 offseason actions; no sheet reached Golden State because the hands-off GM sends no qualifying
  offers (its default). The Match or Pass stop was exercised in the tests and in the app (screenshots).
- **Speed**: offseason time 216 s and 334 s against 246 s and 343 s on main (same laptop, one run each): no slower.
  One sheet pass costs about 1-2 s a market day.

### Trades and seasons still flow
- `scripts/two_season_league_probe.py --model inputs_v1 --seed 17` on this branch: two full seasons to 2028-11-01,
  no decision stops, 1,493 s of actions. **96 trades** (2026-27: deadline week 23, draft 9, in season 7; 2027-28:
  deadline week 22, draft 11, in season 5, summer 7; summer 2028: 11). The same summers as the lean replay (one sheet,
  Sensabaugh, matched; 3 and 0 one-year offers taken): the runs are deterministic.
- Main's lean replay (`scripts/trade_probe_metrics.py` on `base`): **98 trades** (23/9/7; 23/12/5/8; 10). The branch's
  lean replay: 96. Slice 2's report had 102-103 on the earlier main.

## Screenshots (`output/fa-real-slice3/screens/`)
- `1440-match-or-pass.jpg`, `1440-match-or-pass-detail.png`: Brooklyn's sheet for Cam Thomas, "1 day left", salary by
  year, cap effect by season, matching paid with full Bird rights, no hard cap, the assistant's advice, Match / Pass.
- `1024-match-or-pass.jpg` (countdown and buttons on the left so they stay visible beside the offer builder at 1024),
  `1024-decide-today.jpg` (the deadline day, after "Next Market Day" was refused for the decision).
- `1440-offer-sheet-builder.jpg`, `1440-offer-sheet-builder-detail.png`: an offer sheet to Boston's Walter Clayton
  Jr.: "He signs the offer sheet ... BOS then has until the end of the next day to match", paid with the full
  mid-level, "Reserved until BOS decides", tradable from December 15.
- `1440-signing-day-sheets.jpg`: signing day's "Still open" box with the two settled sheets (GSW matched Brooklyn's,
  Boston matched ours).
- At 1024 the board keeps its window positions (as before, slice 2); the decision stays readable.

## Tests and checks
- New `tests/test_offer_sheets.py` (16): sheet terms (2-4 years, raises cut to 5%, the maximum qualifying offer's 3
  years, the Arenas limit and jump with the research's $45.364M example, the bidder's average vs the incumbent's real
  salaries); the bidder pays with room or an exception, never Bird rights, and its room stays reserved (a second
  signing refused, one sheet per player, nobody else can sign him, he can't take the qualifying offer meanwhile);
  sheets open July 1; apron salary counts the qualifying offer; matching with Bird rights over the cap and the year's
  trade block; a hard-capped team can't match even with Bird rights and the bidder signs him with its reserved
  payment; an expensive reserve over the tax is let go but a regular is matched; the deadline (AI teams wait for their
  day); the user's sheet waits for the user or the clock; the player's choice; on a real league: the offer-sheet quote
  equals the contract the save writes (rule 4), the AI bid frequency knob (none at 0, a sheet with a stated reason at
  full appeal), the Match or Pass payload, the assistant text, the advance refused until the decision, and a match.
- JS: `offseason_checklist.test.cjs` (Match or Pass countdown, terms, cap effect, buttons; a hard cap that blocks the
  match; the signing-day box) and `free_agency_room.test.cjs` (offer-sheet mode: lengths, guarantee, his price, the
  button).
- Updated because a rule changed (each says so): `offseason_checklist.test.cjs` signing-day text (sheets exist now),
  `test_overnight_market_health` (hands-off probes follow the assistant's advice on sheets).
- `bash scripts/run_core_tests.sh`: **338 tests OK** (2 skipped).
- `scripts/run_tests_parallel.py --workers 2 --match "free_agen|offseason|cap_ledger|qualifying|restricted|keep_stars|
  waiver|extension|trade|offer_sheet" --js`: 111 modules, **1,365 tests**; 1 failure (the overnight-harness expectation
  above, updated and rerun OK) and 2 errors from git-ignored data missing in the worktree
  (`output/defensive-scale-comparison-2026-11-10`, `output/offense-interior-interaction-2026-11-13`; linked from main
  and rerun OK). Browser tests: all pass except `startup_video.test.cjs` (needs the ignored movie file, as on main).
- Real-stat scorecard: `calibration_report.py --games 1230 --mode replay-real-minutes`: **18/18** league metrics in band. Game simulation is untouched, so the betting-odds check was not rerun.

## Hooks for slice 4
- Sign-and-trades: an already-matched sheet can't become a sign-and-trade (CBA Art. XI §5(m)); a matched contract
  carries `offer_sheet.outcome == "matched"` and a one-year `trade_eligible_date` to check against.
- Two-way qualifying offers and two-way offer sheets (Dante and Cissé were two-way graduates on minimum sheets): the
  sheet rules accept the minimum route already; two-way eligibility is slice 4's.
- The cutdown: a pending sheet holds a roster spot only through its reserved money; when slice 4 counts the 21-player
  offseason limit, count pending sheets for the bidder.
- `offer_sheets.RULES` holds every number the AI uses, labeled for refitting when more seasons of evidence exist.

## What's left
- **Roster repair and trades past a triggered hard cap** (slice-1 gap, the source of every remaining breach): repair
  should cut or use only what fits; the coordinator's trade hook-up (`trigger_hard_cap`, `hard_cap` checks) is still
  pending.
- **Return share 2028 (64%)** above the real range; main is already a little above (58%). Worth a look at Bird
  re-signings of unrestricted players in the market.
- **Self-inflicted hard caps for unrestricted regulars**: the new planning guard covers restricted regulars only;
  Toronto still hard-capped itself before re-signing Zubac. Real offices re-sign their own regulars first.
- **Sheet frequency**: 1 in two summers (real average 1.5); more replayed summers would show whether `pass_rate` 0.16
  is low. The matched share needs more sheets to measure.
- Not modeled: a sheet's optional physical, likely/unlikely bonuses, the flat-average option for a team matching an
  Arenas sheet, the non-taxpayer mid-level matching route's own tests, the March 1 last sheet date (the game stops at
  October 1), the two-business-day undo of renunciations after a match, and "no amendment for a year" (no amendment
  mechanism exists).
- Multiplayer's "advance_save" path past free agency skips the July 15 pass; pending AI sheets are then settled on
  October 1.

## Resume state
- Done: engine, AI, GUI, CLI, tests, replays (main and branch), screenshots, this report; board row set to review.
- Outputs (git-ignored, `output/fa-real-slice3/`): `base` and `run` (lean replays: copies, progress, metrics), `probe17`
  inside `probecode/output/`, code copies `maincode`/`branchcode`/`probecode`, scripts `lean_probe.py`, `calib.py`,
  `peek.py`, `why.py`, `breach.py`, `stays.py`, `offseason_metrics.py`, `stars.py`, `make_gui_save.py`, `codecopy.sh`.
