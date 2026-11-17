# Full-Year Trade Market Review

## Evidence And Scope

Two disposable careers, seeds 17 and 29, advanced through real app actions from October 1, 2026 to December 31, 2027. Only calendar 2027 is counted below. Both completed with identical Python engine fingerprints at start and finish. Runtime was 1,231.53 and 1,317.83 seconds, respectively, running concurrently. Required decisions were resolved consistently: hands-off GSW, ignored incoming trade offers, automatic user drafting, required roster cuts and staff retention. These are two samples, not a league-wide frequency calibration.

Each completed transaction was joined by proposal ID to its durable archived/live ledger and read-only trade-time roster observations. Coverage is 35/35 and 36/36 trades. The observer's tests compare actual application with and without observation and ensure snapshot normalization cannot mutate the save. Offers were accumulated across rollover, not inferred from the final inbox. Release destinations are joined to durable signings within each waiver spell; a later cut cannot erase an earlier successful signing.

Evidence: `output/full-year-market-2026-10-27/analysis.json`, the two `seed*/trade-year.json` files, `market-events.jsonl`, preserved summer checkpoints and disposable saves. The completed annual results below PRECEDE this review's two production changes. They are not claimed as post-change annual results.

## Timing

| Calendar 2027 | Seed 17 Trades | Seed 29 Trades | Seed 17 GSW Offers | Seed 29 GSW Offers |
| --- | ---: | ---: | ---: | ---: |
| January | 3 | 5 | 1 | 3 |
| February | 18 | 19 | 5 | 10 |
| March-May | 0 | 0 | 0 | 0 |
| June | 5 | 5 | 0 | 0 |
| July | 5 | 4 | 0 | 0 |
| August-October | 0 | 0 | 0 | 0 |
| November | 2 | 0 | 0 | 0 |
| December | 2 | 3 | 1 | 0 |
| Total | 35 | 36 | 7 | 13 |

All ten June deals were pick-only draft trades. The other deals involved players. Incoming offers show the same winter concentration, but neither GSW career received a July offer. Date-based opportunities do not guarantee that a particular human roster has an acceptable package. This absence remains a summer inbox validation gap, not proof of a broken schedule or a reason to force an offer.

The pinned official NBA tracker snapshot contains 52 dated tracker entries in both calendar 2024 and 2025, with 19/22 in February, 15/13 in June and 11/13 in July. These are tracker-entry counts, with grouping/report-date limitations, not a mandatory transaction quota. See `data/research/trade_calendar_2023_2026.json` and `docs/FULL_YEAR_MARKET_AND_RELEASES_2026_10_27.md` for primary links and counting caveats.

Conclusion: the revised winter market is no longer the main volume gap in these samples. Summer player trading remains thin. Increasing draft-only swaps would conceal rather than address that gap.

## Quality And Team Direction

| Highest Actual Displayed OVR In Deal | Seed 17 | Seed 29 |
| --- | ---: | ---: |
| 90+ | 3 | 1 |
| 80-89.9 | 15 | 9 |
| Below 80 | 12 | 21 |
| Picks only | 5 | 5 |

These tiers are descriptive, not an independent definition of stardom. Actual trade-time displayed ratings and neutral-role ratings are both retained; the latter are not substituted to inflate the quality count.

Examples from the completed careers:

- Seed 29, July 2: Boston sends Paul George (88.3), Baylor Scheierman (76.2), a first and a second to Toronto for Kawhi Leonard (94.9). Boston moves from ninth to third in the roster-strength ranking, exiting to peak, spending future picks to reopen contention. Toronto becomes weaker now, receives future picks and replaces a two-year $115M obligation with shorter commitments. This is not a younger-core rebuild: George is older than Leonard. Toronto's actual pick quality, not merely two pick rights, needs to justify that decision.
- Seed 17, July 3: San Antonio acquires Trae Young (85.6) for Jerami Grant (80.4), Steven Adams (70.1) and a second. Its rank improves fourth to third and it stays peak. Washington receives a future pick, remains rebuilding and loses current strength. This is an expensive veteran exit rather than a star-for-young-core trade.
- Seed 17, December 18: Detroit acquires Leonard for Miles Bridges (79.5), Donte DiVincenzo (83.8), Isaiah Joe (82.3) and Miami's 2028 second-round pick. Detroit remains peak and its strength rises. Toronto moves exiting to rebuilding, exchanging its best player for depth rather than a clear new championship foundation. That return deserves further quality review even though both valuations approve it; phase labels alone do not prove a sound teardown.
- Seed 17, November 19: Miami adds Pascal Siakam (91.9) for Myles Turner (72.9), Norman Powell (85.6) and Miami's 2028 and 2030 first-round picks, remaining peak and improving measured current strength. Indiana remains exiting. The Durant/George swap on the same date is another substantial veteran deal, not a pick-only transaction. The two firsts were omitted from the initial prose summary; that omission materially understated Indiana's return.

Teams are not rewarded for leaving peak. The audit compares current strength, depth, youth, salary obligations, pick flows and stated route; it does not rank phase changes as automatic successes. Small threshold flips can happen without a large roster improvement. The roster-strength ranking is an estimate used by the game, NOT tested championship probabilities. No core-trial violation was flagged by the captured commitment/exception checks, which is narrower than proving every core decision correct.

### Follow-Up On Seller Value

Implemented follow-up: `docs/PREMIUM_TRADE_RETURNS_2026_10_27.md` records the role-counting and role-quality repairs, mixed-age window correction, premium-return decision check, exact before/after package results, and 201 passing focused tests. The observations below describe the earlier diagnosis, not the current implementation status.

The user's review correctly challenges approval by both current AI evaluations as proof of a fair premium-player return. The historical Boston/Leonard deal involved Baylor Scheierman, not Shai Gilgeous-Alexander. Its first was top-16 protected (with a 2029 first fallback), and its second was protected 31-55; simply calling these "a first and a second" also conceals important quality differences. Toronto initially rejected that package at net -6.792 and only completed it through bounded AI discretion. The subsequent relative-loss fix does not block that large-outgoing-value case.

The Detroit package reveals a valuation asymmetry: Toronto priced its received package at 120.069 while Detroit priced its surrendered package at 23.598. Team-specific roles can explain some difference, but those numbers are not proof of a justified exchange. The role-ranking implementation currently adds package players to the existing roster even when they already belong to that team. Other outgoing package members can therefore appear twice when calculating each player's rank, reducing their assessed role. A three-player synthetic probe demonstrates different multipliers when the same outgoing players are correctly counted once. This follow-up identified the defect; it has not yet changed that logic or recalibrated star trades.

The next quality pass should separate that mechanical ranking defect, cheap-contract valuation, premium-player replacement requirements and override policy. Siakam's complete two-first return must be evaluated separately from a players-only package. Trae's long salary commitment likewise needs separate treatment rather than an unconditional star surcharge. No claim that all four packages are fair is made here.

## A Confirmed Acceptance Problem And Correction

The automatic trade generator could override a refusal if each side lost no more than nine valuation points and the combined deal passed its floor. Nine points can be nearly all of a small asset's value:

- Toronto valued an outgoing pick at 15.360 but accepted net -8.934 for Svi Mykhailiuk (72.6). It lost measured strength, added salary and gained no future asset.
- San Antonio valued Luke Kornet's outgoing package at 7.096 but accepted net -7.234 for Oscar Tshiebwe and Steven Adams, adding salary.
- Charlotte accepted net -5.420 against outgoing value 5.984 for Royce O'Neale's package.

The new discretion-only rule retains the nine-point and combined bounds, but also refuses a loss above half of a positive outgoing valuation, with a 1.5-point small-disagreement allowance. Genuine consent is unchanged. Negative-value liability exchanges retain their existing treatment. Financial legality, core commitments and premium-player protection remain in place.

Applied as a static screen to the recorded evaluations, this rejects six seed-17 and three seed-29 deals. That is NOT a prediction of nine fewer trades in a new career: the search can find alternatives and later rosters change. Tests preserve the captured Garland consolidation and Rollins youth-bet tolerances while rejecting the captured disproportionate losses. Four named bad-package subcases reproduced before the fix.

## July Correction And June Limit

July's general-market route stopped forever after three completed general trades, and did not search when a target-replacement candidate existed. The new route uses the existing date-seeded summer intensity to fill unused post-resolution capacity, prioritizes target replacements, reserves candidate assets and retains a maximum of two applications per phase. The old count remains diagnostic, not a market shutdown switch. No acceptance threshold was loosened.

June's player-trade gap remains: regular trade scheduling only covers preseason/regular season, the draft route trades picks, and re-signing actions advance directly into July. Adding a coherent date-driven June player market is a separate calendar integration, not achieved by this July correction. The open FA negotiation phase is also only five game days; expanding its calendar representation is not silently included.

## Buyouts, Claims And Follow-Through

- Seed 17: Boston buys out Mike Conley February 7. He clears and signs with Denver February 9. Boston's 2026-27 charge remains $2.362143M after the $0.087278M concession; a new club signing does not erase it.
- Seed 17: Harrison Barnes clears San Antonio's buyout and joins Detroit February 9. The old 2026-27 charge is $7.714943M, down from $8M.
- Seed 29: Thomas Bryant joins New Orleans February 9, Javonte Green joins San Antonio February 9, Jae'Sean Tate joins New Orleans February 10, and Barnes joins Utah February 9, after clearing their respective buyouts. Later cuts do not negate those real signings.
- Seed 17: Milwaukee's February 14 LeVert release is claimed by Memphis. The original contract transfers; Milwaukee's waiver-obligation entry becomes zero with `existing_contract_assumed_by_claimant`. The quoted buyout concession does NOT apply to this claimed contract.

Across the two calendar years: eight initiated buyouts, six clearances with all six subsequently signed, and two original-contract claims instead of buyout clearances. Nine total waiver claims include ordinary waivers. No natural salary stretch completed. Retained charges are attributed to their original season, not incorrectly treated as perpetual current payroll.

Neither annual run completed an explicit target-linked roster-space sale/cap dump. That route's earlier Charlotte/Allen/Strus example is separate evidence, not an event from these runs. A read-only seed-29 July 1 probe found six recorded targets but zero sale candidates: every prospective bid was below the player's day-one interest threshold (69.0-81.0 versus 82), so no trade package was even evaluated. Refusing to liquidate for an uncompetitive target is correct. Whether later target selection and bidding find enough viable opportunities still needs validation; do not lower consent to manufacture a sale.

## Verification

- 123 focused tests pass across new discretion/summer behavior, observer/reporting, trade calendar, roster-space follow-through, releases, claims, team planning, protection and simulation partitioning.
- Before production edits, the broader selection reproduced six failing assertions in existing trade-salary tests, including future hard-cap and stale-context checks. These are separate unresolved failures, not silently reported as fixed by this market pass.
- Post-change seed-17 deadline replay, January 31-February 7: daily and bulk reached the same endpoint with identical meaningful saved state, 16 trades, eight offers and 55 games. Report: `output/full-year-market-2026-10-27/market-discretion-after-v2/report.json`.
- Post-change seed-29 summer replay from the exact preserved July 1 checkpoint: daily (save/reload between each day) and bulk both reached September 1 with identical full meaningful saved state. Six July trades, including five general trades, versus four July trades (three general) in the unchanged-engine baseline. Daily took 150.626 seconds; bulk 139.377 seconds. Report: `output/full-year-market-2026-10-27/summer-after-seed29-v2/report.json`. The additional deals include a second July 1 transaction, not just events added at the final date. This is a local checkpoint comparison, not a new annual-frequency claim.
- Ratings, development, visuals and playable saves were left untouched. No packaging was performed.
- Preview reload was deferred: port 8776's server has an active, unpaused background multiplayer clock. It was left running rather than terminating possible league work. The verified production changes are on disk; that existing process has not been restarted to load them.

## Next Priorities

Follow-up: the reported salary-test failures have now been investigated in `docs/TRADE_SALARY_INVESTIGATION_2026_10_27.md`. All six original assertions pass after correcting their mixed-baseline fixture. A newly exposed missing-data crash was repaired, and 142 focused tests pass. The preview restart deferred during this review was subsequently completed with the user's approval.

1. Salary-failure investigation completed as described above; this does not establish complete NBA financial-rule coverage.
2. Add and test a deterministic June player-trade route across postseason exit, lottery, draft and re-signing boundaries; preserve decisions and daily/bulk equivalence.
3. Review summer package search, target competitiveness and human-offer delivery from the saved checkpoints, then measure again. Do not force star trades or annual totals.
4. Review stronger contender-direction protections only against actual counterexamples; a slightly weaker current team can still reasonably extend its window by getting younger.
