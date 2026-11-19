# Trade step 4: three-team (and larger) trades at real rates (plan)

_Plan written 2026-11-19 by Claude (coordinator). Not started. It starts after TRADE-2B (rebuild sales, tax value, phase labels, draft-night pricing) merges, because it builds on the tax-savings value and the target search. Steps 3 (counter-targets) and 5 (personality) stay separate. See `docs/agents/TRADE_AI_DIRECTION.md`._

## TL;DR
- In two simulated seasons the AI made only 2 three-team trades out of 47. Both were small salary-routing deals. Real: about 8 trades with 3+ teams per season since 2019-20, which is roughly 10–15% of all trades and about a quarter of deadline deals.
- In real trades a third team joins for one of a few clear reasons: it **absorbs salary for picks**, it **supplies or receives a piece** that one of the main teams needs, or it **turns a pick-for-pick draft-night swap into a chain**. The plan builds those reasons into the target search from step 2. It does not glue random teams onto deals.
- Every team in a multi-team trade must state its reason and pass its own acceptance check, just as in two-team trades.

## What real multi-team trades look like (our 2025-27 list, `data/research/real_trades/trades_2025_2027.json`)
Seven real 3- and 4-team trades with full detail (the two very large 10- and 16-team entries are deadline roundups, not single deals):

| Trade | Why each team joined | Kind |
|---|---|---|
| DAL / WAS / CHA, 2026 deadline (Anthony Davis) | DAL sells and gets under the tax; WAS adds a star; CHA sends Tyus Jones and takes Branham to make the salaries work | Star trade + salary routing |
| CLE / SAC / CHI, 2026 deadline | CLE saves about $40M in tax; SAC takes salary at a low point; CHI absorbs Saric with a trade exception and collects seconds | Tax move + salary absorption for picks |
| DET / CHI / MIN, 2026 deadline | MIN saves over $20M in tax; CHI turns Huerter into the younger Ivey; DET adds depth and a pick upgrade | Tax move + young-player swap |
| MIN / BKN / CHI, 2026 draft | MIN escapes Randle's contract for a small pick slide; BKN gets a driver; CHI adds rim protection | Salary dump routed through a needy team |
| MEM / DET / OKC, 2026 draft | MEM slides down for five seconds; OKC and DET each get the prospect they wanted | Draft-night chain |
| LAL / NYK / DAL / PHX, 2026 draft | NYK trades down for seconds; three teams each get their fit | Draft-night chain |
| OKC / ATL / DAL, 2026 offseason | OKC gets under the second apron; ATL adds a defender; DAL buys low on a former #1 pick | Apron move + buy-low |
| CLE / DEN / LAC / WAS, 2026 offseason | DEN can't keep Watson under the second apron (sign-and-trade); CLE pays a first; LAC and WAS take the leftover salary and players | Apron forced sale |

Patterns:
1. **Tax and apron pressure** drives most of them: a team needs to shed salary, and a team with room or a trade exception takes it for picks.
2. **Salary matching** for a player one main team wants.
3. **Draft-night chains:** one team trades down and two or three teams each get the prospect they target.
4. Every team has a stated reason. Nobody joins just because the value adds up.

Real rates (`multi_team_rates` in the same file): about 4.5 trades per season with 3+ teams in 2009–2019, and about 8 per season since 2019-20. In 2024-25 more than a third of in-season trades had 3+ teams. Draft-night chains are common.

## How it works in the game today
- `multi_team_trades.py` has a "facilitator" path: when a two-team deal fails only on salary matching, it tries routing one player through a third team that wants him (`facilitator_candidates`, at most 64 tries a day). After step 2 it produced 2 deals in two seasons.
- Nothing yet:
  - brings in a third team for **tax relief with picks**;
  - assembles a **star trade that needs a third team's piece**;
  - builds **draft-night chains**.

## Design
Multi-team assembly is a second stage of the step-2 target search. When a buyer and seller agree in principle but the deal fails on salary, roster spots, or "the seller wants something the buyer doesn't have", look for a third team whose own targets or needs complete it.

1. **Salary absorber.** Each team publishes, as part of its trade wants, whether it has room under the tax or the apron, or a trade exception. A team with room takes the salary and gets paid in picks, using step 2b's tax-savings value: the team shedding salary values the money saved; the absorber values the picks and judges the player's fit or his salary-filler role. Rebuilding teams and teams under the cap are the natural absorbers, as Chicago twice was in 2026.
2. **Missing piece.** If the seller wants a type of player or a young asset the buyer lacks, find a third team that has it and would move it (step 2's willing-seller list) for something the buyer can give. Every team's own targets must be met: the third team must want what it gets.
3. **Draft-night chains.** A team trading down can split its pick among teams that each target a prospect at nearby slots. Build on step 2's draft-night trades, which have both teams accept; step 2b fixes their pricing. This needs the draft-boards work only for the targets, and step 2 already has each team's target prospect.
4. **Four or more teams:** allow at most 4 at first, and only when each added team fixes a remaining problem.
5. **Explanations:** each team's reason in plain words, as in two-team trades. Examples: "CHI absorbs Saric's salary with room under the tax and collects two seconds" or "CLE saves $40M in tax".
6. **Speed:** this stage only runs on near-misses from the target search, with a small cap per day. The deadline's evaluation count must stay far below the old brute-force search; step 2 got the deadline down from ~99,000 evaluations to ~4,700.

## Measurement
- Two-season probe (seed 17, GSW hands-off) before and after:
  - share of trades with 3+ teams, overall and in deadline week, against real (about 8 a season; 10–15% overall; about a quarter at the deadline; draft-night chains present);
  - each multi-team trade read in plain words: does every team have a reason?
  - total trades, and that the step 1–2b gains hold: few hot potatoes, no rebuilders buying expensive veterans unless paid to;
  - deadline evaluations and CPU.
- Tests:
  - focused tests: absorber for picks, missing piece, draft chain, every team accepts, explanations;
  - the existing multi-team tests (`tests/test_multi_team_trades.py`);
  - the trade, market and foundation modules;
  - core tests.
- Both scorecards are byte-identical (the trade logic doesn't touch game results).

## Files
`multi_team_trades.py`, `trade_targets.py`, `transactions.py` (search stage and evaluation), `trade_wants.py` (publishing room and exceptions), `play.py` (draft-night chains), config overrides and tests. The user's own trade finder and the human team's evaluations are unchanged.

## User decision (2026-11-19)
- The user's team can be offered a role as a third team, for example "Team X will pay you two seconds to absorb this contract". These arrive as **incoming offers** that the user accepts or declines in the existing offers flow. They are never executed automatically.
