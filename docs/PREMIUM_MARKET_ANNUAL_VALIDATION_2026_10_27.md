# Annual Market Validation After Premium-Return Repairs

## Result

Implemented follow-up: `docs/TRADE_IMPACT_AND_STRESS_2026_10_28.md` documents workload-neutral roster forecasting, stronger Jokic/McDaniels return checks, dedicated incoming-offer searches, preserved swap grants and collateral safety, and immediate high-pressure deadline/summer validation. The user explicitly requested stress testing now; the recommendation below describes the earlier sequencing, not a remaining requirement to defer volume tests.

The market remains active, and target-linked sales now have natural full-year examples with real follow-through. This is not a clean bill of health for trade quality. The most useful next work is better basketball-impact and premium-return decisions, plus an audit of the separate draft acceptance rule. Increasing overall activity is not the immediate priority.

Two disposable careers used the current production engine through real app actions from October 1, 2026 to December 31, 2027. Only calendar 2027 is counted. Seeds 17 and 29 finished in 1,262.03 and 1,323.46 seconds, running concurrently. Both Python engine fingerprints remained unchanged. All 77 annual completed trades match committed live/archived ledger records and trade-time observations. No production code, ratings, development, visuals or playable saves were changed during this pass.

Evidence: `output/premium-market-full-year-2026-10-27/analysis.json`, `seed*/trade-year.json`, `seed*/market-events.jsonl`, disposable saves, and the preserved `phase_saves/summer_before.json` checkpoints. The earlier `interim.json` is a non-atomic live progress sample, not final evidence; use `analysis.json`.

The consistent user policy was hands-off GSW: ignore incoming offers, automatic user drafting, required roster cuts and staff retention, no voluntary user signings. These are two careers with one user-team policy, not population-wide calibration or a controlled single-change A/B experiment.

## Full-Year Timing

| Calendar 2027 | Seed 17 Trades | Seed 29 Trades | Seed 17 User Offers | Seed 29 User Offers |
| --- | ---: | ---: | ---: | ---: |
| January | 2 | 4 | 1 | 2 |
| February | 18 | 21 | 4 | 7 |
| March-May | 0 | 0 | 0 | 0 |
| June | 5 | 5 | 0 | 0 |
| July | 9 | 6 | 0 | 0 |
| August-October | 0 | 0 | 0 | 0 |
| November | 2 | 0 | 0 | 0 |
| December | 2 | 3 | 0 | 0 |
| Total | 38 | 39 | 5 | 9 |

Seed 17 had 33 player-involved deals and five pick-only deals; seed 29 had 34 and five. All June trades were draft-pick exchanges. July's additional activity is actual player trading, not extra draft swaps. The prior annual samples had 35/36 total and 5/4 July deals, but the changed roster paths mean that comparison does not isolate a coefficient's causal effect.

Offers are accumulated across rollover rather than counted from the final inbox. Deadline concentration remains visible. Zero summer offers in both GSW samples is still a gap: it does not establish whether a particular roster had no viable match or whether user delivery/search is inadequate. Do not force acceptance to manufacture offers. June's missing general player-trade route and August-October inactivity also remain unresolved.

The existing pinned historical tracker research is `data/research/trade_calendar_2023_2026.json`. Its 52 entries in each of calendars 2024 and 2025 are tracker blocks with grouping/date limitations, not a required annual quota. These two careers do not justify raising every month's activity rate.

## Quality And Team Direction

| Highest Actual Displayed OVR In Deal | Seed 17 | Seed 29 |
| --- | ---: | ---: |
| 90+ | 2 | 0 |
| 80-89.9 | 14 | 13 |
| Below 80 | 17 | 21 |
| Picks only | 5 | 5 |

Displayed and neutral-role OVR are both retained in the observations. These descriptive bins are not independent definitions of star value. No Kawhi sale occurred in either annual sample. That is narrower than proving every premium-player decision correct.

### Premium Return Still Too Broad

Seed 17, July 5: Denver sends Nikola Jokic (95.0, age 32) for Pascal Siakam (91.8, age 33) and Arjun Fofana (75.0, age 22), with no picks. Denver stays exiting, its measured strength falls 2.09, and Indiana moves exiting to peak with a 2.38 increase. Denver's additive net is only +0.563 and the deal executes through bounded discretion.

The structural guard considers Siakam comparable: his on-court value of 78.55 is within six of Jokic's 83.95. Fofana's upside value is 8.37, below the guard's standalone young-centerpiece requirement. The older Siakam plus that prospect is not convincing evidence of a renewed championship foundation. This is a concrete remaining elite-return problem, even though it is not the earlier depth-only Kawhi error. Tightening all star prices indiscriminately would still mishandle genuine bad-contract/health cases.

Seed 17, November 19: Houston sends Kevin Durant (90.1, age 39) to Toronto for Jakob Poeltl (79.5), Ja'Kobe Walter (69.7) and two pick rights. Toronto stays peak; Houston moves exiting to rebuilding. The extreme age and future-asset return make this a different decision from the Jokic example. Pick rights must be inspected for actual value/protection, not treated as two guaranteed premium firsts. No blanket claim of fairness is made.

### Valuable Starters Still Need A Roster-Level Reason

Seed 17, July 3: entering Minnesota sends Jaden McDaniels (85.4, age 27) for AJ Green (69.7), Gary Trent Jr. (71.9), Zion Cross (63.6) and a pick right. Its measured current strength falls 2.16 while salary increases 0.86M. This passes ordinary additive valuation and is not flagged by the existing report because the pick is counted as a future benefit. That benefit alone does not establish sufficient compensation. The guard's high-end thresholds do not cover every valuable starter.

This is why phase transitions and summed asset prices should remain diagnostic rather than proof of good roster building. There were no captured core-trial violation flags, but a previously expired commitment or a weaker return outside that rule can still produce a bad deal.

### Strength/Window Signals Need A Sanity Check

The annual report flags two contender-weakening deals per seed and four large proportional discretion losses per seed. These are review candidates, not eight proven trade bugs. For example, Indiana's McConnell-for-Hardaway exchange in seed 29 saves 4.5M now and removes later salary, which the report's 5M immediate-savings threshold misses.

More fundamentally, in seed 29 adding Buddy Hield for a distant second raises Toronto's summed top-eight quality by 2.21, but lowers its contention estimate by 0.83 and moves its rank from 10 to 13. The young-core override stops at rank 12, so the window label flips entering to exiting despite no young core departure. Existing player roles/forecast aggregation and threshold sensitivity need investigation before using those labels as an independent measure of trade impact. Do not respond by hard-coding Toronto's phase.

## Draft Acceptance Is A Separate Path

All ten draft trades include one ordinary evaluation with `accepted: false`, yet execute. `best_ai_draft_trade_candidate` in `src/nba_gm_data/play.py` independently checks seller/buyer floors, then sets `accepted_by_all = True` without updating the rejecting evaluation. Its buyer floor is -22, or -26 in a quiet mid-first market; the current general-market absolute discretion bound is much smaller.

This is existing explicit draft policy, not evidence that the repaired general-market consent check failed. Team-specific prospect preference can legitimately justify a draft premium, but these records do not show a quantified benefit that reconciles the loss. Example: seed 17 Philadelphia's ordinary evaluation is -24.361 against 91.54 outgoing value in an Atlanta pick trade. Audit the desired-prospect benefit, willingness limits and recorded decision together. Do not simply disable draft trades or claim all ten were genuinely approved by ordinary valuations.

## Natural Sales And Free-Agent Pursuit

- Seed 17, July 2: Charlotte sells Grayson Allen to Sacramento for its 2034 second, freeing approximately 19.375M, and signs its intended target Cason Wallace the same day. The target plan was 23.1M annually for four years.
- Seed 17, July 3: Sacramento sends Precious Achiuwa to Denver for no returning asset to clear salary for Jimmy Butler. Sacramento actually bids, but Butler chooses another team's offer. This is a cap dump, not a discounted sale with recovered compensation.
- Seed 29, July 3: Sacramento sells prospect Liam Renard to Denver for Sacramento's 2032 second, then bids for Anthony Black. Black chooses another team. A plausible pursuit is not a guaranteed signing.
- Seed 29, July 5: Chicago sells Buddy Hield to Toronto for Toronto's 2034 second, then signs Miles McBride the same day. The target plan was 11.7M annually for three years.

All four target-linked deals have recorded bids; two sign their intended targets and two lose competitively. This confirms natural route use, not its ideal frequency or every buyer's wisdom. These summer examples do not validate selling useful depth months before an uncertain future target becomes available.

## Buyouts, Claims And Obligations

Calendar 2027 has five initiated buyouts per seed. Eight clear waivers and all eight subsequently sign elsewhere; two seed-29 original contracts are claimed instead. Six total annual waiver claims occur across both careers. No salary stretch completes naturally.

- Seed 17: Detroit buys out Javonte Green February 7; he clears and signs with the Clippers February 9. Detroit retains the reduced old obligation.
- Seed 17: Chicago buys out Harrison Barnes February 28; he joins Charlotte March 2 after clearing. The old salary is not erased by the new signing.
- Seed 29: Boston's Mike Conley and Milwaukee's Caris LeVert are claimed by Memphis February 9, transferring the original contracts. Their buyout concession is not applied; the original teams' corresponding obligations are zeroed with `existing_contract_assumed_by_claimant`.

The audit checks every observed annual claimed release's zeroed original obligation, every cleared buyout's remaining positive obligation and signing destination, and unique asset references/no reported legality issues in observed trades. These checks passed. The raw harness release counts cover its entire October-2026 onward run; the annual counts here filter durable records to 2027. This explains seed 17's raw three claims versus two annual claims.

## Verification And Next Work

Thirty-six focused tests passed for observer non-mutation, archive/inbox counting, reporting, premium returns, projected roles and team planning. Completed traces were then joined to the durable ledger: coverage 38/38 and 39/39. An additional assumption that every applied trade retained two accepting ordinary evaluations failed on all ten draft swaps; that result is reported above, not hidden as a passing acceptance check. No natural salary-stretch frequency or complete financial-rule coverage is claimed.

Both simulations have exited. About 230MB of disposable evidence was retained; no old evidence or playable saves were deleted. No new full-year or multi-season runs were launched after these two.

Recommended order, using these checkpoints rather than immediately repeating annual careers:

1. Verify roster-impact/role calculations and stabilize window classification against small role/rank changes. Otherwise trade-direction decisions inherit a noisy target.
2. Tighten elite replacement quality and meaningful starter consolidation using the captured Jokic and McDaniels counterexamples. Preserve contract, health, future-pick and legitimate retooling exceptions.
3. Reconcile draft-specific willingness with explicit recorded consent, including a measurable prospect-specific reason for any premium.
4. Then integrate June player trading and diagnose summer user-offer delivery. Remeasure volume only after decision quality is credible.
