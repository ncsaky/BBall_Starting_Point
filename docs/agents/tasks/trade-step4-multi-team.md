# Trade step 4: three- and four-team trades, salary absorbers paid in picks, repeat taxpayers (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a33eaab50ab924182`. Plan: `trade-step4-multi-team-plan.md` (with the
user's decision that the user's team is only ever offered a third-team role). Follows `trade-2b-followups.md`._

## TL;DR
- **Teams with room now charge for taking salary they don't want, and tax teams pay them in picks.** In the
  two-season test, dumps carrying a pick went from 2 of 22 to 5 of 13 (plus two tax legs with picks inside
  three-team deals); the rest went to teams that will play the player. No player was traded twice (9 before).
- **Three-team trades now happen for real reasons, but rarely: 2 in two seasons (real: about 8 a season).** Both are
  the common real shape (a tax team makes its trade and sends a small contract plus a second to a team with room).
  Every team states its reason in plain words. Repeat taxpayers and "take this contract for picks" offers to the
  user's team are built.
- **Cost: fewer trades, 66 to 57, and the deadline fell from 15/12 to 10/8 (real ~23)**, because free salary dumps
  are gone. Speed is unchanged. The main decision for you is how to win that volume back (below).

## What was built

### 1. Taking salary you don't want is a cost (`trade_tax.absorb_cost`)
Before, a team with room valued any bench player a little above zero, so it took tax teams' salary for free and dumps
almost never carried picks. Real absorbers charge when the player is outside their plans (Charlotte took Finney-Smith
with three seconds, Chicago took Saric for two, Milwaukee took LeVert with two, Brooklyn took Randle with the #28 pick)
and pay when he would play for them (Detroit gave two seconds for Isaiah Joe, Atlanta two for Aaron Wiggins).
- **Dead money**: the part of an incoming player's salary that buys no minutes. All of it when he would be out of the
  receiving team's rotation (8 minutes or less by his place on its depth chart), none at 18 minutes or more, linear in
  between. A team far from contending also counts later seasons of a veteran's contract as partly dead (up to half,
  by distance from contending and his age then, 29 to 32). This is the Memphis-takes-Poeltl case.
- The first $2M a season of each player is free (the roster spot costs about a minimum salary anyway).
- Salary the team sends out in the same deal offsets it, season by season, so ordinary salary-matched trades cost
  nothing; the cost bites when a team takes on net money or a longer contract than it sends out.
- Price: 3 points per $1M, the same money rate as the tax (a dollar of salary costs an owner what a dollar of tax
  does), later seasons at half weight (as the tax counts next season), scaled by the owner's spending appetite and
  capped at 60 (about a late first). The tax team saves $1.50 to $3.25 of tax per dollar of salary, so the same rate
  on both sides still leaves a surplus to share. That surplus is what the seconds pay for.
- AI teams only; the human team's own evaluations never change. It enters the acceptance check (with a plain-language
  note, "Absorbed salary: about $XM of it buys no rotation minutes"), the target search's quick price and the dump
  search.
- **First try was too expensive**: at 4.5 points per $1M (fitted to the real pick counts alone) no dump cleared,
  because a second is worth 18-24 points in this game and a $5-8M dump saves only 15-30 points of tax. The same money
  rate as the tax, the half weight on later years and the free $2M brought dumps with picks back.

### 2. Picks paid to cut the tax are not a rotation overpay (`trade_roster.pick_investment_outlook`)
The acceptance check rejected any trade where a team spent more draft value than the rotation gain justified ("Draft
spending exceeds the rotation ... benefits"). A tax team paying a second to shed salary was always rejected by it. The
tax it saves now counts as a purpose: it raises the draft-capital limit by the tax value, and the loss limit by a
quarter of it. AI teams only (the human team's tax value is zero).

### 3. Three- and four-team deals (`multi_team_trades.py`, second half)
Three ways a third team joins, each only for a stated reason:
- **Reroute** (salary absorber): in a deal one team almost made, a contract it would take but doesn't want goes to a
  team with room under the tax instead, paid in seconds by the team that sent it. The absorber sends back a nominal
  second-round swap or its cheapest second (or, with a full roster, its least useful minimum-salary player).
- **Shed** (tax relief): a team over the tax adds one of its own spare contracts (24 or older, $2.5M+, not in its core
  plan, not traded or signed too recently) to a deal, and a team with room takes it for picks. This is used two ways:
  to close a near-miss, and to **grow an agreed deal** when the tax team is clearly better off by its own full
  evaluation (at least +3), the Saric leg of the real Cleveland / Sacramento / Chicago deal.
- **Missing piece**: when the seller in a near-miss wants more than the buyer has, a third team sends the seller a
  player who fits one of the seller's own targets, and the buyer pays the third team in picks. Only players the third
  team would move (not young players it builds around), at its own asking price.
- **Where near-misses come from**: two-team deals the full check declined for price only (no hard rule broken: no
  premium-return, draft-overpay or core-commitment rejection), and packages the quick price screen dropped with one
  side up to 45 points short and the other side happy. At most 10 near-misses a normal market day and 24 at the
  deadline; at most 16 / 48 full multi-team checks a day.
- **Four teams**: when a three-team version is still short but its absorber is happy, a second absorber may join
  (at most 4 teams).
- **Acceptance**: the two main teams under the same bounded negotiation as two-team AI trades; every joining team
  outright (net at or above its own threshold): nobody joins just because the value adds up. The execution step
  re-checks AI-only deals under the same rule. The old salary facilitator now uses the same rule.
- **Order**: deals keep the order the front offices pursued them. A three-team deal completed from a near-miss takes
  that pairing's place; appended last, it was always cut by the day's trade slots (the first two test runs found
  agreed three-team deals and executed none of them).
- **Explanations**: every team's reason in plain words, stored on the trade and its log. Example from the test league:
  *"DEN (on the rise) moved Zeke Nnaji ($7.5M) to cut its luxury tax by about $8.8M, paying 1 second-round pick; CHA
  (on the rise) had room under the tax and took him for the picks; DEN also moved DaRon Holmes II ($3.4M) in the same
  deal, bringing its luxury-tax saving in the whole deal to about $10.4M; MEM (rebuilding) had room under the tax and
  took him for 1 second-round pick."*

### 4. Incoming offers for the user's team (user decision)
When two AI teams almost made a deal and an absorber would complete it, the same route is offered to the user's team:
"X pays you two seconds to absorb this contract". The two AI teams must both accept outright; the user is paid what an
AI team in its place would ask, at least one second. The offer arrives in the existing offers inbox
(`save.queue_ai_recommendations`, one line, within the day's offer slots) and runs only if the user accepts it there
(the existing multi-team consent check). The human team is never an absorber in AI-to-AI deals. The offer carries
`offer_context.kind = "absorb_salary_for_picks"` and its reasons; the offers panel shows it with the standard
multi-team layout (the GUI files belong to another agent, so the reason text is not shown there yet).

### 5. Repeat taxpayers (`trade_tax.record_season_payrolls`, `is_repeat_taxpayer`)
- New additive save field `team_payroll_history` ({season: {team: payroll, tax line, taxed}}), written once when the
  postseason starts (two lines in `save.initialize_postseason`) and read through `canonical_with_save` (one line).
- A team taxed in 3 of the previous 4 recorded seasons pays the repeater rates ($2.50, $2.75, $3.50, $4.25, then +50
  cents per bracket), so its tax savings are worth more. Seasons before the save started count as untaxed, so no
  team can be a repeater until the third season of a career; the two-season probe cannot show an effect.

### 6. Tax weight
Left as is (3 points per $1M, capped at 40). The measurements show no problem with it; the absorb cost uses the same
rate on purpose.

### Draft-night chains: not built (hook only)
The draft-boards work landed during this task. The hook is the same near-miss shape: a pick-for-pick trade-up where
the team trading down wants a second pick from a third team. Also found for the draft-night owner: all five
draft-night trades land at picks 11-18 because the per-draft budget (5 trades) is spent first-come in pick order
(`play.maybe_run_ai_draft_trades_before_pick_state`: the "quiet mid-first market" loosens the floor from pick 11 until five trades
happen). Spreading the budget over the best opportunities in the whole draft would fix it.

## Before and after against real
Two-season probe: seed 17, GSW hands-off, 94-input ratings, 2026-10-20 to 2028-11-01. Both runs on the same base:
"before" is `codex/immersive-franchise-journey` at 0390382 (draft boards, fatigue and smart rest, value refit merged);
"after" is this branch merged with it (9394671). Run one at a time.

| Measure | Before | After | Real |
|---|---:|---:|---:|
| Trades, whole run (2026-27 / 2027-28 / summer 2028) | 66 (27/29/10) | **57** (22/26/9) | ~110 |
| ... deadline week, per season | 15 / 12 | **10 / 8** | ~23 |
| ... draft night, per draft | 5 / 5 | 5 / 5 | ~5 |
| Trades with 3+ teams | 0 | **2** (both at the deadline; 3.5% of trades, 11% of deadline trades) | ~8 a season; 10-15% overall, ~25% at the deadline |
| ... four-team | 0 | 0 | rare |
| Salary dumps (two-team) | 22, **2** with picks | 13, **5** with picks | real dumps usually carried 1-3 seconds |
| ... plus tax-relief legs inside three-team deals | 0 | 2 (each with a second) | |
| Trades where tax money entered a team's decision | 36 | 27 | 12 of 43 real were tax moves |
| Big contracts ($20M+, 2+ years, weak player) moved | 0 | 0 | a few a season, with picks |
| Rebuild sales | 12 | 14 | the most common real trade |
| Rebuilding team takes a 30+ player on $15M+ for 2+ years | 2 | 2 (both summer signings-and-trades, see below) | ~0 unless paid |
| Players traded 2+ / 3+ times | 9 / 0 | **0 / 0** | rare |
| Young starters moved (25 or younger, 24+ mpg) | 1 | 0 | |
| Every team's reason stated | 64 of 66 | 55 of 57 (the 2 without are summer trades from the older free-agency path) | |
| Odd phase labels at the deadline | 0 | 0 | |
| Trade-search evaluations, whole run | 5,077 | 5,724 (+13%) | |
| CPU seconds, whole run | 1,199 | 1,166 (-3%, within noise: three other agents were running) | |
| ... deadline 2027 (1 step) / 2028 (2 steps), CPU s | 54.9 / 93.6 | 55.6 / 84.1 | |
| Incoming absorber offers to the user's team | (none possible) | 0 offered (3 tried; the AI teams never both accepted outright) | |

How to read it:
- **Three-team trades now happen, for real reasons, but at a quarter of the real rate.** Both are the most common
  real shape: a team over the tax makes its trade and adds a small salary leg to a team with room, paid with a
  second.
- **Dumps now usually cost a pick or go to a team that will play the player.** Of the 13 two-team dumps, 5 carried a
  second; the other 8 went to teams where the player takes rotation minutes ("took him as a rotation player"), which
  is the Isaiah Joe / Aaron Wiggins pattern. Before, 20 of 22 dumps were free bench players.
- **The cost is volume.** The 9 free dumps that disappeared were most of the lost trades (66 to 57), and they were
  deadline trades, so the deadline fell from 15/12 to 10/8, further from the real ~23. This is the main decision for
  the user (below).
- **No hot potatoes**: no player was traded twice (9 before). The run is one seed, so treat this as encouraging, not
  proven.
- **The two "rebuilder takes an old long contract" cases** are July trades: Memphis taking Aaron Gordon (31.8, $36M,
  2 years; 5 years in the before run) and Orlando taking Mikal Bridges (30.8, $36M, 3 years). Both are summer trades
  from the target search that the absorbed-salary cost did not stop, because both players would start for those
  teams (the cost only counts future seasons at half weight and half dead).

Earlier runs on the previous base (f348618, before draft boards and smart rest) showed the same direction: before 74
trades / 0 multi-team / 20 free dumps; first version (4.5 points per $1M) 65 / 0 / 12 with 5 picks; with the
tax-rate price 58 / 0 / 7. Those led to the half-weight later seasons, the free $2M and the slot-order fix. A run on
4f1f1d5 (draft boards only) gave 69 -> 67 trades, 16/13 -> 12/13 at the deadline, 0 -> 1 three-team trade, dumps
16 (0 with picks) -> 15 (4 with picks). Results in `output/step4-final/` and `output/step4-final2/` (local).

## The multi-team trades, read like a person
1. **Feb 2, 2028, SAS / UTA / CHA.** San Antonio (contending) gets Lauri Markkanen from Utah for De'Aaron Fox and Pete
   Nance, and sends Tarris Reed Jr. ($3.2M) with a 2034 second to Charlotte; Charlotte's return to San Antonio is a
   2028 first-round pick-swap right (its own pick against Minnesota's). San Antonio's whole deal cuts its tax by about
   $17M. **Reasons**: SAS wanted a playoff-level starter;
   UTA (on the rise) sold a veteran older than its timeline; CHA had room and was paid a second to take Reed.
   **Textbook?** Yes in shape (a contender upgrades and sheds a bench salary at the same time, as Cleveland did with
   Saric). The return Charlotte sends (a first-round swap right on its own pick) is worth more than a nominal asset;
   see "still wrong".
2. **Feb 5, 2028, MIA / TOR / DET.** Miami (retooling) gets RJ Barrett from Toronto as Andrew Wiggins's successor, for
   Bobby Portis, Dru Smith, Ryan Conwell and a 2032 first; Toronto (getting under the tax) also sends Alijah Martin
   ($2.6M) and a 2034 second to Detroit, which sends back its own 2034 second. **Reasons**: MIA's succession target;
   TOR's tax; DET's room. **Textbook?** Mostly: the deal itself is a real retool move. The Detroit leg is close to a
   wash (a second for a second plus a cheap player); it should have been a plain absorb with a nominal return.

## Speed
No measurable change. The multi-team stage only looks at near-misses (at most 24 a deadline day) and runs at most 48
full checks a day (the probe used 9 in two seasons of deadline days that it reached). The whole run used 13% more
trade-search evaluations, mostly dump packages tried one pick at a time; a dump now stops trying more picks once the
seller is out of range (committed after the runs, so not in these numbers).

## Tests and checks
- New `tests/test_trade_step4.py` (20 tests): absorbed salary (outside the rotation, plays, offset by salary sent out,
  human team never charged, rebuilders' later years, evaluation note, saturation); repeat taxpayers (rates, 3 of 4
  seasons, bigger savings, payrolls recorded once); multi-team acceptance (bounds, joiners outright, hard rejections,
  marking, forged joiner lists); routes (near-miss rules, reroute legs, reasons for every team, human team only gets
  offers); picks paid for tax savings raise the draft-capital limit.
- Focused: `test_trade_step4`, `test_multi_team_trades`, `test_trade_2b`, `test_trade_targets`,
  `test_salary_search_stage_b`: 98 OK. The 40 trade, market, contract, salary, pick and team-planning modules plus
  `test_foundation` and `test_deadline_speed_exact`: 574 run, all OK except three that need the repository root as the
  working directory or a local experiment output (two foundation CLI tests pass when rerun from the root;
  `test_pick_and_pop` needs `output/expanded-cohort-action-performance-2026-11-15`, an experimental-engine file not in
  this worktree). `scripts/run_core_tests.sh`: **337 OK** (2 skips), on the branch before the last merge.
- Scorecards: `calibration_report.py --games 20` in both modes and `validate-season-probabilities --runs 5 --limit
  20`, base vs branch: identical output except the timing line. Nothing here touches the game simulation.

## What is still wrong, and decisions for the user
1. **Decision: dumps cost picks now, and the deadline lost volume (15/12 -> 10/8).** Options:
   (a) keep it (realistic prices, fewer trades);
   (b) charge only for contracts that run past this season or exceed about $5M, which brings back most of the free
   small dumps;
   (c) add the real "get under the tax" bonus: teams that end under the line share the tax pool (about $10-15M each in
   recent seasons), which makes teams just over the line pay to get under, as real teams do. (c) is the most realistic
   way to get volume back and is a separate small task. My recommendation: (c), with (a) until then.
2. **Three-team trades are a quarter of the real rate.** The near-misses the target search leaves are mostly price gaps
   (the buyer is short) or are blocked by hard rules (a rotation-weakening sale, too many picks for a marginal player).
   A third team cannot fix those. The next levers, in order: draft-night chains (now unblocked; real drafts have
   several a year), the tax-pool bonus above (more tax-relief legs), and counter-targets (step 3).
3. **Nominal returns**: an absorber should send back a pick swap or nothing of value, not its own second or a
   first-round swap right. Small fix in `absorber_return`.
4. **No absorber offers reached the user's team in the test** (3 tried; the AI teams must both accept outright).
   The path works in the tests; whether it should accept the bounded negotiation like AI-only deals is a question.
   The offers panel does not yet show the offer's reason text (GUI owner).
5. **Big bad contracts still do not move.** The absorber prices them now, but the owning team still values the
   player's minutes above the tax saved. Real moves of this kind (Randle, Davis) were tied to a bigger trade; that
   needs the tax-pool bonus or a "contract the team wants out of" reason.
6. **Prospects as dump filler**: Oklahoma City dumped Bennett Stirtz (a recent first-round pick) for tax savings in
   both runs. The dump search's age floor (24) lets in 24-year-old rookies; it should use years in the league.
7. **Repeat taxpayers** take three seasons of history before any team qualifies; the two-season probe cannot show an
   effect.
8. **Draft night**: all five draft-night trades land at picks 11-18 (see above); and chains are next.
9. Tax weight left at 3 points per $1M (no problem found).

## Files
- Code: `trade_tax.py` (absorbed salary, repeat taxpayers, payroll history), `multi_team_trades.py` (near-misses,
  reroute / shed / missing piece, agreed-deal salary legs, bounded acceptance, reasons, user offers, apply re-check),
  `transactions.py` (evaluation term and note, search stage, pursuit order, dump pick ladder), `trade_targets.py`
  (quick price uses the money term, near-miss packages), `trade_roster.py` (tax savings justify picks),
  `save.py` (three small additive lines: payroll history at the postseason, read through `canonical_with_save`, user
  absorber offers into the inbox).
- Measurement: `scripts/trade_probe_metrics.py` (multi-team share, deadline share, dumps with picks, big contracts,
  multi-team detail), `scripts/inputs_readiness_report.py` (reads multi-team trade logs).
- Tests: `tests/test_trade_step4.py`.

## Resume state
Done: code, tests, three rounds of probes (final pair on 0390382 merged), metrics, trade read, report, board row,
commits on `worktree-agent-a33eaab50ab924182`. Not pushed or merged. Local outputs: `output/step4-final2/` (final
pair), `output/step4-final/` (4f1f1d5 pair, scorecards, test logs), `output/step4-results/` (older base),
`output/step4-lab/` (lab scripts and saves). Next: decision 1, then draft-night chains.
