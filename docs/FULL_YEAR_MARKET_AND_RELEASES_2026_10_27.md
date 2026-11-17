# Full-Year Market And Release Decisions

## Scope And Status

This is a backend pass. No player ratings, heatmaps, UI layout, playable saves or release packages were changed. All careers used for verification live under `output/trade-year-2026-10-27/`.

Completed: short minimum-contract waiver claims above the cap; all-years claim cost assessment; date-driven AI buyout reviews; a separate salary-cap stretch quote/election and conservative AI funding route; in-season released-player pursuit after the trade deadline; incoming-offer calendar weighting; deadline search breadth and same-day asset reservation; private inquiries about unlisted non-core rotation players; full-year audit instrumentation.

**Not complete:** calibrated whole-year transaction frequency, comprehensive NBA exception accounting, a buyout bargaining UI, and natural-frequency validation of AI stretch usage. Broader deadline search is not evidence that the final annual market is calibrated.

## Immediate Replacement Versus A Summer Bet

The July roster-space sale still requires a currently available, identified free-agent target. It cannot sell January depth on the assumption that a summer signing is certain. The existing in-season signing route can waive weaker depth for an available released player after financial and roster-upgrade checks; the trade deadline no longer incorrectly disables this route.

This preserves the rare useful in-season free agent without introducing speculative months-long roster holes. Selling first for an in-season target, rather than cutting, remains a separate extension; it is not falsely described as implemented here. A future summer-target liquidation route must price intervening games, injury cover, contention and target uncertainty.

## Full-Year Reference

The existing pinned NBA tracker snapshot now aggregates by January-December, rather than treating a regular season as a complete trade year.

| Calendar Year | Jan | Feb | Mar-May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 3 | 19 | 0 | 15 | 11 | 0 | 0 | 1 | 0 | 3 | 52 |
| 2025 | 2 | 22 | 0 | 13 | 13 | 1 | 1 | 0 | 0 | 0 | 52 |

These are dated tracker blocks, not a reconciled census of legal transactions. Multi-team grouping, omitted entries and report/approval dates can differ. The coincident totals are not a proposal to mandate 52 trades. An external AP deadline cross-check already differs from the official tracker sample.

Sources and original entries: `data/research/trade_calendar_2023_2026.json` and `scripts/research_trade_calendar.py`. Official trackers: https://www.nba.com/news/2023-24-nba-trade-tracker , https://www.nba.com/news/2024-25-nba-trade-tracker , https://www.nba.com/news/2025-26-nba-trade-tracker , and the 2024/2025 offseason trackers at https://www.nba.com/news/2024-offseason-trade-tracker and https://www.nba.com/news/2025-offseason-trade-tracker .

## Saved-Career Findings

The seed-29 full-year pilot completed through December 31, 2027. Reading both the archive and live transaction tail gives:

| Month | Player-Involved Trades | Pick-Only Trades |
| --- | ---: | ---: |
| January | 5 | 0 |
| February | 5 | 0 |
| June | 0 | 5 |
| July | 3 | 0 |
| December | 3 | 0 |
| Calendar-Year Total | 16 | 5 |

Other months had no trades. October/November 2026 add three earlier trades but must not be counted toward calendar 2027. This pilot remains well below the recent reference sample. The draft's five pick trades are not hiding an overly active year; offseason player trading is particularly sparse.

Draft AI has a five-trade budget and only searches on-clock picks 1-25. July has separate cap-clearing, roster-space, lost-target and general-trade routes; the general route has a three-deal limit. Those mechanisms are not interchangeable with a regular-season slot count. Their caps/search scope need a dedicated follow-up, not a blanket acceptance discount or forced draft-trade count.

The initial audit counted only the live transaction tail and lost older events after archival. Its final inbox also could not represent offers cleared at rollover. The corrected harness merges archived/live transaction IDs and accumulates observed offers across steps. Archive/rollover counting has regression tests. The legacy pilot's final inbox is NOT presented as a complete annual offer history; the preserved summer-start snapshot contains the January/February offers, and a separate summer replay records that interval.

The full-year pilot resumed at the explicit postseason/lottery handoff after the harness initially repeated a confirmation stop. It did not skip draft decisions or modify playable saves. Source hashes at the start/resume are retained. This is a development pilot, not a pristine before/after benchmark of the final patch.

## Search And Incoming Offers

Previously the search shuffled interested buyers and checked just six, evaluated only five packages per buyer, targeted only trade-block players and could propose several deals using the same player/pick before the queue discarded conflicts.

The revised search keeps the strongest fits, explores more packages during the final week, considers pick payment when a buyer has absorption room, and can continue to a different package after a same-day reservation conflict. Final-week private inquiries consider at most two eligible unlisted rotation players per team, never a protected core or an inactive/deep-bench player. These inquiries do not put the player on the public block.

Existing financial, ownership, valuation and core-commitment checks remain. Bounded AI discretion can no longer override the separate ordinary-return refusal of a committed core player. Exceptional returns remain possible under the existing commitment policy.

On the December 31 saved career, the listed-only candidate probe found 28 approved packages in 17.47 seconds; enabling private inquiries found 35 in 21.97 seconds, including seven additional private targets. These are unexecuted candidate searches, not 35 actual trades or an annual estimate. The wider search is restricted to the deadline period to bound its cost.

Incoming regular-season offers now use the same seasonal intensity curve as league completions, with their own date-seeded opportunity draw. July incoming inquiries peak early in the market and are delivered to the inbox, never auto-accepted. Repeated calls do not create duplicate offers. The availability of a sensible package still matters, so one human franchise is not guaranteed an offer quota.

A later regular-season pilot before the final private-inquiry addition completed all 1,230 games in 429 seconds, with 14 trades and no deadline-day completions. That result is explicitly insufficient. After adding private inquiries, real-action short deadline tests validate the new route separately; do not relabel that older full season as a final whole-year calibration.

## Buyout Evidence And Policy

The spring veteran market-watch lists explicitly label 10 completed buyouts in 2023, five in 2024 and two in 2025. They also list ordinary waivers and speculative candidates; those were not counted as buyouts. Coverage is selective, cutoff dates differ, and these are not comprehensive annual totals. Factual names/counts and sources are pinned in `data/research/release_market_2023_2025.json`.

References: https://www.hoopsrumors.com/2023/02/2023-nba-buyout-market-watch.html , https://www.hoopsrumors.com/2024/02/2024-nba-buyout-market-watch.html , https://www.hoopsrumors.com/2025/02/2025-nba-buyout-market-watch.html . Primary examples: https://www.nba.com/news/kevin-love-buyout-cavaliers , https://www.nba.com/news/kyle-lowry-philadelphia-76ers , https://www.nba.com/news/ben-simmons-contract-buyout-brooklyn-nets .

AI reviews happen at deterministic weekly milestones after the deadline through March 1. Eligibility is deliberately narrow: an expiring verified obligation, an older healthy non-core player with fewer than eight projected minutes, sufficient healthy same-position cover, a full enough roster, no recent signing commitment, and an actual prospective destination that passes the existing acquisition assessment. The game's fixed concession must be small enough to make potential new earnings plausible. This is a simplified consent model, not a negotiation engine or a claim about how NBA buyout percentages work.

The full-year pilot initiated five buyouts. Two players were claimed on their original contracts; their concessions did not apply. Three cleared with buyout reductions: Jae'Sean Tate, Simone Fontecchio and Larry Nance Jr. No natural stretch completed. These categories must not be conflated.

That pilot also exposed a follow-through bug: a veteran's old zero-minute role could screen him out of released-free-agent review despite the recorded outside interest. The final patch preserves the observed interest through waivers and ensures a fresh destination review after clearance. It does not guarantee the destination or bypass salary/roster checks. Natural signing outcomes from the older pilot are not presented as proof of that later fix.

## Stretch Is Separate

The backend quote/election is a one-time reallocation of remaining cap charges. It preserves the total amount and the pre-stretch schedule. Eligible offseason money is allocated across 2N+1 seasons; an in-season election leaves the current season untouched. Original-term timing, known protection, other waived money's aggregate 15%-of-cap limit, rounding, repeat safety and reacquisition restrictions are checked. Unknown money is not silently treated as verified. Cash obligations are not reduced by electing a cap stretch.

The AI only considers already-cleared debt to fund an identified competitive summer bid that it cannot currently afford, with a substantial roster upgrade in an entering/peak window. It checks the longer debt tail and submits the actual bid in the same committed change. It does not automatically stretch every release, waive a star just to save cap, or copy the Lillard/Beal cases without their context.

Verified examples establish stretch use across years (McGee 2023, Little 2024, Lillard/Beal 2025) but do not establish exact league-wide yearly counts. The game has no forced stretch quota. Natural usage frequency remains unverified; the controlled backend election/funding/rejection tests are separate evidence.

Rules: NBA CBA 101, minimum exception and Exhibit C; stretch section L: https://cms.nba.com/wp-content/uploads/sites/4/2024/11/2024-25-CBA-101.pdf . Full 2023 CBA, Article VII 7(d)(6), via https://www.nbpa.com/cba .

## Waiver Scope

Claims can use the minimum exception for eligible original one-/two-year minimum contracts. The recognizer covers the game's flat minimum frameworks and matching published minimum salary signatures; it does not treat any cheap contract, or the last two years of a longer contract, as eligible. Imported unknown/prorated terms can still require review.

AI acquisition cost uses the actual annual salary schedule, not first-year salary times years. It compares future overpayment with the projected upgrade and declining veteran value; unexercised future team options are not treated as unavoidable debts. The full contract transfers on a claim. Current/future financial checks and the cost of any replacement cut remain distinct.

Trade/MLE/bi-annual/disabled-player exception machinery was intentionally left out. The user's preferred simplified waiver rule is retained without adding extra UI or exception bookkeeping. These simplifications are disclosed, not presented as complete NBA rules.

## Verification And Remaining Work

- 223 focused regression tests passed. Scoped diff whitespace validation passed.
- Final private-inquiry real-action comparisons: seed 17, January 31-February 7, 18 trades and eight generated user offers; seed 29 over the same dates, 26 trades and seven offers. Each daily/bulk pair reached the same date with identical meaningful saved state, including 55 games. These are short mechanism tests starting from disposable near-deadline fixtures, not mature full-season frequency measurements.
- The longer final seed-29 comparison reached February 14 with 90 games, 26 trades, seven offers, three initiated buyouts and one released-player signing. Daily and bulk business states matched. Jock Landale agreed to the Atlanta buyout February 7, cleared February 9 and signed with Detroit on February 9. The other two buyouts were still in their waiver windows at the endpoint; they are not counted as completed clearances.
- Focused tests cover minimum claims, original-term eligibility, expensive future years, option treatment, buyout exclusions and replay, stretch timing/limits/rounding/debt persistence, funded AI bidding, archive counting and calendar-driven offers.
- Real-action daily/bulk comparisons cover two seeds at the deadline, including generated offers, durable trades, rosters, contracts, health and development. A longer clearance case additionally covers post-buyout pursuit.
- The full calendar-year pilot, summer replay and short candidate probe are explicitly separate from a final full-year calibration. Audit saves remain available for follow-up without repeating long careers.
- Next frequency work should distinguish actionable player/pick markets in June/July and use the saved checkpoint to examine package rejections. Do not weaken core protection, financial legality or consent simply to hit a count.
