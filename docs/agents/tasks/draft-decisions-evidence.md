# How NBA teams draft

**TL;DR.** NBA teams drifted much farther from the public board after the top five. The game’s typical second-round pick was three spots away in generated classes, versus nine to ten in the NBA.\
Turning off the reach penalty was the closest of the tested settings, but it recovered only part of the missing variation. Treat zero as a trial setting.\
Contenders’ age and experience preferences changed direction between periods, and the roster-need pattern changed too. Keep those weights for now.

## How often teams depart from the board

The study covers 833 picks. I set the comparison targets using the 600 picks from 2012–2021 and checked them on the 233 picks from 2022–2025. The public comparison combines two or three pre-draft rankings per year. Where one publication lists fewer players, a missing name cannot rank above that publication’s cutoff in the average. Fifty-five picks were absent from every source, mostly in the second round. They count as reaches where the board depth proves the threshold, and the usual gap uses ranked picks only. The included source list gives the date, link, and coverage for each board. Some NBA Scouting Live rankings already combine multiple sources, so independent agreement between every underlying evaluator is unknown. [Public board sources](../../../data/research/draft_boards/cache/public_boards.json)

Each cell shows the **typical absolute gap in spots**, then the share **reaching at least five / ten spots**. A reach means choosing someone earlier than the board ranks him. A slide is the reverse.

| Pick range | NBA 2012–2021 | NBA 2022–2025 | Game 2026 | Game generated classes |
|---|---:|---:|---:|---:|
| 1–5 | 1 · 12% / 0% | 0.5 · 0% / 0% | 1 · 0% / 0% | 0 · 14% / 0% |
| 6–14 | 3 · 29% / 21% | 3 · 28% / 14% | 2 · 11% / 11% | 2 · 8% / 0% |
| 15–30 | 6 · 37% / 25% | 6.5 · 36% / 23% | 2 · 19% / 6% | 4 · 17% / 0% |
| Second round | 10 · 44% / 32% | 9 · 42% / 29% | 2 · 13% / 0% | 3 · 12% / 3% |

In the NBA, 14 of 100 top-ten prospects fell at least five spots in the fitting years, and 7 of 40 did in the later years. Nine and four fell out of the lottery. Across the four game drafts, 5 of 40 fell at least five spots and one fell out of the lottery. The game produced no ten-spot slides among its top ten, versus six in the 14 NBA drafts.

The 2026 probe took AJ Dybantsa first, Cameron Boozer second, Darryn Peterson fourth and Yaxel Lendeborg fifth. The real picks were first, third, second and 11th. Lendeborg was already sixth on the game’s June scouting board. The reach penalty has little leverage when the scouts and the GM already rate a player almost as highly. [NBA 2026 draft archive](https://www.nba.com/news/history-draft?experience=app)

## Readiness and upside

For each turn I compared the selected player with the highest-ranked player still available. Contenders won at least 60% of their previous season’s games and made the playoffs. Rebuilding teams won at most 42% and missed the playoffs. The table compares contenders with rebuilders at the same numbered pick, after subtracting each pick’s board comparison. The public board is a rough stand-in for long-term value and includes some judgment about current ability. College class standing is a rough count of college years. [Standings and career data](https://github.com/sumitrodatta/bball-reference-datasets/tree/3981e43c07e963db539c527beb8a7b4b99ec8716/Data) · [College data](https://barttorvik.com/playerstat.php)

| Contender difference compared with rebuilding teams | NBA 2012–2021 | NBA 2022–2025 | Game generated classes |
|---|---:|---:|---:|
| Age at draft, in years | −0.21 | +0.77 | −0.22 |
| College class, in years | −0.35 | +0.26 | −0.03 |
| College box plus-minus | +0.53 | +0.62 | — |
| College points per game | +0.12 | +1.57 | — |
| Board spots passed over | +1.43 | +3.61 | −1.17 |

The age comparison uses 47 shared slots in the fitting years and 17 in the later years. College production has only seven shared slots in the later years. Grouping nearby picks gives a smaller age difference of −0.11 and +0.11 years across the two periods. The stronger pattern is that contenders bypassed more board spots. Their college prospects also had somewhat better box production in both periods. The evidence supports measuring on-court readiness separately from age.

The 2026 game run has one observation per slot. Comparing wider pick ranges there gives a contender difference of +0.11 years of age, +0.40 college years and −1.74 college box plus-minus, with just seven contender comparisons for the last measure. The generated players have no college box statistics, and their class year follows their generated age. Using the game’s own team labels across all four drafts, contenders gained about 1.16 points of scouts’ estimated current ability relative to rebuilders and the board, comparing within pick ranges.

## Positional need

I grouped players by their listed main position as guards, wings or bigs. For each team I compared its prior-season share of minutes at that position with the league average. Positive values mean the team drafted at a position where it had fewer minutes than it would have with the best player left on the board. A roster can play many minutes at a position and still need an upgrade, so this measures one kind of need. [Basketball Reference player and team data](https://github.com/sumitrodatta/bball-reference-datasets/tree/3981e43c07e963db539c527beb8a7b4b99ec8716/Data)

| Pick range | NBA 2012–2021 | NBA 2022–2025 | Game 2026 | Game generated classes |
|---|---:|---:|---:|---:|
| 1–5 | −0.26 | +0.93 | −0.51 | −3.10 |
| 6–14 | +0.05 | +1.96 | −0.75 | +0.81 |
| 15–30 | −0.18 | +1.92 | +1.84 | −1.35 |
| Second round | +0.43 | −0.20 | +1.37 | −0.18 |

The figures are percentage points of roster minutes. In the fitting years, 93 second-round picks filled the team’s thinnest position versus 77 board choices across 264 comparable turns. The later sample gave 36 actual picks versus 37 board choices. The minutes evidence gives little basis for ramping up the game’s existing need bonuses. The game considers shooting, creation and defense as well as position, and changing the weight on all of those together gave mixed results.

## What happened by year four

In 2012–2021, reaches of five or more spots in every pick range accumulated less four-year value over replacement than picks within four spots. The difference was largest in the top five, with 0.77 versus 4.12, based on six reaches. In the rest of the lottery, reaches averaged 5,133 minutes through year four versus 5,991. Players who slid five or more spots into picks 15–30 averaged 1.48 value over replacement, versus 0.85 for picks near the board. These are comparisons within pick ranges. Minutes also reflect how much opportunity teams give their draft picks. [Basketball Reference’s box plus-minus and value over replacement](https://www.basketball-reference.com/about/bpm2.html)

| Which order better separated outcomes? | Actual order | Public board |
|---|---:|---:|
| 2012–2021, four-year minutes | 74% | 70% |
| 2012–2021, four-year value over replacement | 57% | 56% |
| 2012–2021, year-four box plus-minus among players who played | 55% | 57% |
| 2022, four-year minutes | 76% | 70% |
| 2022, four-year value over replacement | 53% | 49% |
| 2022–2025, rookie-year minutes | 72% | 70% |

These percentages measure how often the earlier player did better in a pair, with half credit for ties. Both orders use the same players, those drafted and ranked. The four-year holdout contains the 2022 draft only. Its reaches had lower four-year value in picks 15–30 and higher value elsewhere, with two reaches in picks 6–14 and none in picks 1–5. The additional rookie-year check includes all four later drafts and puts the two orders within a point on both box impact measures. The public board was a useful check on large reaches. The actual order sorted playing time better.

## Draft-day movement

These counts are unique slots where the pick or its rights changed hands in a documented draft-day deal. Picks exchanged in the same deal each count. Earlier agreements are excluded where the reporting dates distinguish them, even when they closed after the draft. Formal closing dates can lag the agreement. [NBA draft trade tracker](https://www.nba.com/news/2020-nba-draft-trade-tracker) · [2023 results](https://www.nba.com/news/2023-nba-draft-order) · [2024 results](https://www.nba.com/news/2024-nba-draft-order) · [2025 results](https://www.nba.com/news/2025-nba-draft-order)

| Pick range | NBA 2012–2021 | NBA 2022–2025 | Combined |
|---|---:|---:|---:|
| 1–5 | 3 | 0 | 3 |
| 6–14 | 19 | 10 | 29 |
| 15–30 | 52 | 17 | 69 |
| Second round | 114 | 51 | 165 |

## What the game runs cover

The probed game revision was `0e656e4`. The current league starts after the 2026 draft, so I restored the saved pre-draft prospect list and pick ownership in memory. The stock selector used the current starting rosters and team strategy. The three all-fictional classes were 2031, 2032 and 2033. They used seeds 17, 23 and 31, with projected standings and the same starting teams. Each omitted one first-round slot due to a forfeited pick in the game’s ledger. The comparison used the real 2025–26 record and position minutes in all four snapshots. These were selection-only runs, so the historical trade table gives no estimate of the game’s live trade rate.

The reach trial used the 2012–2021 targets and the first two generated classes. I chose the setting closest to their typical gaps and reach rates across the four pick ranges. Then I checked that setting against 2022–2025 and the third class. The stock ranking formula was reproduced at all 237 selections in the four drafts before any trial. Zero reach penalty raised the second-round gap from 3.5 to 5 spots in the two fitting simulations and from 3 to 3.5 in the separate class, still well short of the NBA’s nine to ten. Both the stock and the zero-penalty setting produced one five-spot reach in the top five of the separate class.

The study uses compact cached copies of source table fields, with source links and date judgments in the cache. Full fetched pages are retained locally under the cache’s pages directory. The branch carries the factual extracts used for the offline rebuild. The offline rebuild reproduced the JSON byte for byte and 13 draft tests passed. Run the following from the worktree to regenerate the JSON offline. Add `--refresh-game` to rerun the stock drafts and weight trials at the checked-out game revision. The 2027–2029 scouting notes were useful for choosing years beyond the real prospect pool. They do not supply historical NBA ranks. [Source notes](../../../data/research/draft_boards/cache/sources.json)

```sh
PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py
```

## Suggested values

| Setting | Current | Suggested value | Evidence |
|---|---:|---:|---|
| Rebuilding upside bonus | 0.10 | 0.10 | Rebuilders stayed closer to the board than contenders did, but their relative age and college experience changed direction. The tested bonuses did not give a stable age or upside advantage across the simulated classes. |
| Contender readiness bonus | 0.14 | 0.14 | College box production favors a modest readiness preference. Age and years played are weaker guides, and doubling the bonus had little effect in the separate generated class. |
| Extra contender risk penalty | 0.03 | 0.03 | The public inputs have no consistent pre-draft measure of how unpredictable each player was. The age and college comparisons cannot identify this number. |
| Need weights, picks 1–5 / 6–14 / 15–30 / second round | 0.05 / 0.10 / 0.20 / 0.25 | 0.05 / 0.10 / 0.20 / 0.25 | The real second-round need effect changed direction, and trial weights did not give a steady improvement across the generated classes. |
| Reach penalty | 0.25 | **0.00 in a trial** | This was the closest fit and also improved the separate check. It still left too few large reaches. Keep early-pick and slide rates in the trial’s scorecard. |
| Reach tolerance | 2 slot-value points | 2 | The winning trial sets the penalty to zero, so the tolerance has no effect there. The test did not identify a replacement. |
| Seller-initiated offers to move back | Buyers scout and bid for the pick on the clock. The seller can accept or trade down in a chain. | Test whether a seller can actively shop a pick when its preferred players are still likely to be available later. | Slots changed hands far more often later in real drafts. Compare unique slots moved in the live game before changing deal limits. |
| Explicit age penalty | No separate age adjustment in the GM’s pick score. | Leave it out. | Contenders’ preference for older players reversed between periods. Measure current ability, risk and room to improve directly. |
