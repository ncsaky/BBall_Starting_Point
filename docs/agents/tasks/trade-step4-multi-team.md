# Trade step 4: three- and four-team trades, salary absorbers paid in picks, repeat taxpayers (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a33eaab50ab924182`. Plan: `trade-step4-multi-team-plan.md` (with the
user's decision that the user's team is only ever offered a third-team role). Follows `trade-2b-followups.md`._

## TL;DR
- **Teams with room now charge for taking salary they don't want, and tax teams pay them in picks.** Salary dumps
  went from 0 of 20 carrying a pick to RESULT_DUMPS. Rebuilding teams no longer take on long contracts for older
  players to make salaries match.
- **Three-team trades are built, but they are still rare: RESULT_MULTI in two seasons (real: about 8 a season).**
  Every one states each team's reason in plain words. The engine's two-team market leaves few deals that a third team
  can rescue; the reasons and the next lever are below.
- **Total trades fell (74 to RESULT_TRADES) because free salary dumps are gone**; the deadline is RESULT_DEADLINE a
  week (real ~23). Speed is unchanged. The user's team can now receive "take this contract for picks" offers.

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

RESULTS
