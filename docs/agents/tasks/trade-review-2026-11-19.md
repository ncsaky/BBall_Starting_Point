# Human-style review of the AI's trades (2026-11-19)

Sample: every AI trade from two full AI-run seasons (seed 17, GSW hands-off, 2026-10-20 to 2028-11-01), from the
INPUTS-READINESS probe: 88 trades on the 94-input ratings, 87 on the older ratings. Lists:
`output/inputs-readiness/trades_<set>.{json,md}` (local). Compared against 43 real trades from 2025-26 to 2026-27
(`data/research/real_trades/trades_2025_2027.json`) and the framework in `docs/agents/TRADE_AI_DIRECTION.md`.
Trade search funnel from `docs/agents/tasks/deadline-speed.md`.

## TL;DR
- **Volume and timing look right**: ~44 trades a season (real: ~55-60), clustered at the deadline, draft night and
  early July, with the right mix of salary moves, veteran swaps and pick deals.
- **The motives often don't**: players bounce around (31 players traded 2+ times in two seasons, 7 of them 3+ times),
  rebuilding teams take on 30-something veterans on big multi-year deals, franchise stars get swapped for other
  franchise stars on value alone (Jokic for Doncic straight up), and young starters get sold for seconds by teams
  that are not rebuilding.
- **One systematic cause stands out**: a team values the players it sends out well below what the receiving team
  values the same players (median 16% lower, a quarter of trades 47%+ lower). Both sides "win" by a lot in 21 of 88
  trades. Real front offices do the opposite: they overvalue their own players.
- **No multi-team trades at all** (0 of 175; the three-team search tried 64 deals a day and agreed none). Real: about
  a quarter of deadline deals, roughly 10-15% of all trades.
- **No memory of investment or tenure**: recent acquisitions are flipped within months; a franchise player of 12
  seasons is treated like any asset.

## What looks right (keep)
- **Volume and calendar**: 88 trades in two seasons, mostly deadline week, draft night (5 per draft, all pick-for-pick
  moves up and down, which is realistic) and the first days of free agency.
- **Contender upgrades with expiring money**: e.g. SAS (peak) taking Dillon Brooks for 34-year-old Tobias Harris;
  DEN (exiting) turning Aaron Gordon's five-year deal into Jrue Holiday's expiring contract.
- **Rebuilders collecting young players or picks**: LAC (rebuilding) getting Paolo Banchero (25) for Beal and
  Hachimura; CHI (rebuilding) getting Peyton Watson (24) for Nic Claxton plus a swap.
- **Draft-night trade-ups and trade-downs** with pick sweeteners.
- **No young-player hoarding** after today's cheap-contract change: young players moved 10 times in each run.

## What doesn't (with examples)
1. **Hot-potato players.** Banchero, Beal, Myles Turner, Trae Young, Luke Kornet, Julius Randle and OG Anunoby were
   each traded three or more times in two seasons (31 players traded twice or more). Randle went BKN -> MIL -> CLE
   -> NOP. Real NBA: being traded twice in a season is rare and is usually a salary-matching journeyman. Cause:
   only a 60-day "recently traded" block; nothing about tenure, investment or "we just traded for him".
2. **Phase-incoherent buyers.** Rebuilding teams took on seven 30-plus players on $15M+ multi-year deals (LAC: Sabonis
   31 $45M x2, then Beal 34 $26M x3 and Brooks 31 $23M x3; WAS: Anunoby 30 $45M x2, VanVleet 34; MIL: Beal 35). A
   real rebuilder does this only when paid to (a salary dump with picks attached), which these weren't.
3. **Value-only star swaps with no reason.** Jokic (DEN, 12 seasons with the team) for Doncic straight up; Booker
   (PHX, a six-year deal) for 33-year-old Siakam's expiring contract, then Booker again a year later; Durant (38) for
   Jaylen Brown; Donovan Mitchell (CLE, "entering") for Banchero plus a first. Each is close on value, but neither side
   had a stated target or a context reason; real trades of this size come from a team that wants out, a contender
   pushing in, or a star asking out.
4. **Young starters sold cheaply by non-rebuilders.** TOR ("entering") sent Davis Fogle (22, 29 projected minutes,
   62.4 overall) for a two-minute rookie and three seconds; POR ("entering") sent Deni Avdija (26.5, 33 minutes) for
   Jordan Miller and seconds. These look like the Nique Clifford trade, but without the context that made Sacramento's
   move understandable (rebuild, tax, end of the rotation). Here TOR and POR valued their own player at roughly half
   of what the buyer did.
5. **Everybody wins.** In 21 of 88 trades both teams' net value is above +5; in several both are above +15 (Bridges for
   Coby White: CHA +49.7, PHX -4.7 but PHX values White at 69 vs CHA's 15). The cause is the asymmetry below.
6. **No three-team trades.** The only three-team path exists to repair salary matching, and it never agreed a deal.
   Real three-team deals mostly route salary through a team with room (paid in seconds) or bring a third team in to
   supply the pieces a star trade needs.
7. **Odd filler.** Kevin Love (39) and Klay Thompson (37) as salary ballast to rebuilding teams is realistic; but
   several trades send three end-of-bench players for one, forcing waivers the receiving team didn't need.

## The systematic cause: teams undervalue their own players
For the same assets, the receiving team's value is a median **1.16x** the sending team's value (quartiles 1.02 /
1.16 / 1.47; the older ratings: 1.18, up to 1.52). Reading `package_value_components` (transactions.py): each team
values a package through its own `destination_role_multipliers` (minutes the player would get on *this* team) and
`team_fit_for_player` (needs and excesses on *this* roster). For its own players, the player already counts in the
team's depth (so his position shows as an "excess" and his minutes as "replaceable"), and rebuilding/phase terms
push his value down further. Marginal-value thinking is defensible, but with no endowment effect, no tenure and no
investment memory it makes almost every team a willing seller, and it is why the search finds ~26 mutually
acceptable deals on a day with one trade slot. Real front offices are loss-averse about their own players.

## Mapping to the framework
| Framework piece | Today | Review finding |
|---|---|---|
| Value | one number per player; picks by slot and year | broadly sensible; pick prices not yet checked against real 2025-27 deals |
| Fit both sides | points table; giver's loss indirect | givers undervalue own players (above) |
| Role / future | rank -> minutes multiplier | young starters sold as if replaceable |
| Succession | star-only | not visible in any trade reason |
| Tenure / investment | 60-day block, small recent-trade premium | hot potatoes; franchise stars swapped |
| Phase | window labels exist | rebuilders buying expensive veterans |
| Targets | none; brute force on value | no trade has a stated motive |
| Personality | small noise, difficulty unused | not visible; every deal is value-led |
| Multi-team | salary repair only, never succeeds | zero three-team trades vs ~10-15% real |

## Recommended order (for the redesign plan)
1. **Own-player valuation**: an explicit "what we lose" from the giver's side (endowment/loss aversion), plus tenure
   and investment (recent first-round pick, traded up for him, recently acquired, recently extended), so teams stop
   being willing sellers of everything.
2. **Targets**: each front office sets a few targets per window from its phase and needs (specific players, or a
   profile and price range: "starting wing who shoots, under $25M"), and sellers list who they'd move and why
   (rebuild sell, tax, surplus position, player wants out). Search only pairs a target with a willing seller.
3. **Counter-targets**: the seller answers from its own targets on the buyer's roster, or asks for more raw value.
4. **Multi-team assembly**: when two teams agree in principle but salary or pieces don't fit, invite a third team
   that has a matching target or cap room (paid in picks); measure the rate against real deals.
5. **Personality**: savvy and player opinions as small deviations once the above is right.
6. **Measure with this review**: rerun the two-season probe after each step and track hot-potato count, rebuilder
   veteran buys, both-sides-win share, three-team share, and the number of evaluations (speed).
