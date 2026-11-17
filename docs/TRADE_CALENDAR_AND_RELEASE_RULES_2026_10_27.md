# Trade Timing And Release Rules

Follow-up: [Full-year market and release decisions](FULL_YEAR_MARKET_AND_RELEASES_2026_10_27.md) contains the January-December audit, later candidate search fixes, minimum waiver claims, and separate buyout/stretch backend work. Findings below describe the earlier pass.

## Immediate Depth Loss

The existing roster-space sale route pursues an already available July free agent. It does not currently sell players in January for a hoped-for signing next summer. Added an explicit July/free-agency guard so that later callers cannot accidentally treat months without a useful player as free. Normal in-season trades and immediate released-free-agent signings are unaffected.

A future speculative route should price the intervening games, injury insurance, remaining roster flexibility and the risk of losing the target to another bidder. Contenders should charge more for that loss than rebuilders. Selling a genuine zero-minute surplus player is different from losing the only credible injury replacement. No unsupported win-loss forecast or arbitrary penalty was added to the present summer-only route.

## Research

`scripts/research_trade_calendar.py` extracts dated entry facts from the NBA's three official in-season trackers and three offseason trackers. The pinned result is `data/research/trade_calendar_2023_2026.json`. It stores source URLs, retrieval hashes and dated entry IDs, not article prose. Rescinded transactions are excluded. An undated Kevin Porter Jr. entry is dated from the Clippers' linked official announcement.

These are **tracker entries**, not player transfers or team participations. Tracker omissions, report-versus-approval dates and expanded multi-team deals prevent treating this sample as a perfectly reconciled transaction census. Pure pick deals are included; the current regular-season AI generator principally starts from player targets.

| In-season tracker | Oct | Nov | Dec | Jan | Feb | Listed total | Final seven days | Deadline day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-24 | 0 | 2 | 1 | 3 | 19 | 25 | 18 | 16 |
| 2024-25 | 0 | 0 | 3 | 2 | 22 | 27 | 22 | 15 |
| 2025-26 | 0 | 0 | 0 | 1 | 25 | 26 | 25 | 17 |

March-May have no entries in these in-season trackers. The separate offseason trackers add:

| Offseason | June | July | August | September | October | Listed total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 12 | 16 | 0 | 1 | 1 | 30 |
| 2024 | 15 | 11 | 0 | 0 | 1 | 27 |
| 2025 | 13 | 13 | 1 | 1 | 0 | 28 |

These offseason October transactions should not be mistaken for additional regular-season trades. Draft-rights exchanges and multi-team sign-and-trades matter substantially to the June/July counts. Offseason and draft AI volume was not retuned in this pass.

Cross-check: the AP's 2026 deadline report counts 28 trades in the final week and 18 on deadline day, versus the tracker sample's 25/17. The NBA's historical deadline summary also groups some prior deals differently. Those discrepancies are retained as uncertainty, not silently flattened into fabricated exact counts. The consistent pattern is a quiet autumn and a very concentrated deadline, with another major burst at the draft/free agency.

Sources:
- https://www.nba.com/news/2023-24-nba-trade-tracker
- https://www.nba.com/news/2024-25-nba-trade-tracker
- https://www.nba.com/news/2025-26-nba-trade-tracker
- https://www.nba.com/news/2023-offseason-trade-tracker
- https://www.nba.com/news/2024-offseason-trade-tracker
- https://www.nba.com/news/2025-offseason-trade-tracker
- https://www.nba.com/news/trade-deadline-deals-all-time-history
- https://apnews.com/article/d4122fece6c1115cfdb8733d51e70bb1

## Implemented Calendar

The old model could apply a trade every day from November 15 and during preseason, until it spent a hard 28-trade season allowance. Earlier saved careers consequently had 13-14 October trades and only one February trade. Its one-per-day cap also prevented a genuine deadline burst.

`trade_calendar.market_day` now draws deterministic, date-seeded opportunities with a quiet autumn, a January ramp and a final-week concentration. Each season gets a bounded activity-climate variation. These are opportunities, **not guaranteed trades**. Financial legality, ownership, recent acquisition restrictions, core commitments and buyer/seller approval still apply. There is no mandatory annual count and no 28-trade ceiling to exhaust prematurely.

Normal inbound-offer reviews run twice weekly even on zero-AI-completion days. Late-week reviews occur more frequently. Proposed same-day AI packages do not reserve the same player/pick twice. Repeat calls do not regenerate an already reviewed day's market. Bulk advancement still visits each simulation date, so it uses the same schedule as daily play.

Across 300 cheap calendar-only seeds, mean opportunity count was 34.3, range 17-52; the final week averaged 25.86. Mean reviews fell to 46.46 across 128 dates. These figures describe only the calendar, NOT completed trades or full simulated seasons. Fewer searches are an efficiency benefit, not a measured whole-game speedup.

## Real-Action Verification

`output/trade-calendar-2026-10-27/parity/researched-calendar/report.json`: seeds 17 and 29, daily versus bulk advancement through a November week and a deadline week, with matching user-decision policies. All complete business-state comparisons matched, including games, offers, rosters, health, development and waivers. Deadline-week applied trades were 9 and 13; seed 17 generated four user offers. These are short windows from identical fresh baselines, not mature-season counts.

`output/trade-calendar-2026-10-27/season-29-verified/trade-season.json`: one real-action regular season, hands-off GSW, required cutdowns/staff decisions and deadline confirmation, no discretionary user trades. Started October 1 from the imported roster; this is not a replay of the preceding summer. All 30 teams completed 82 games, with 1,230 wins and 1,230 losses. Runtime was 326.94 seconds, approximately 5.45 minutes.

- Applied trades: 16 (October 2, November 1, December 0, January 4, February 9).
- Final-week trades: 11. Deadline-day trades: 0.
- Generated user offers: 8 (October 2, December 1, January 1, February 4). Four later became stale and four expired at the deadline. Eight is generated-history count, not eight currently actionable offers.

**Remaining calibration issue:** this pilot is quieter than the recent 25-27-entry in-season reference sample and lacks a deadline-day burst. Available calendar slots did not guarantee mutually acceptable, executable packages. Do not increase forced acceptance, discard core protection, or claim that opportunity counts prove actual frequency. A focused candidate-supply/package-search audit is the next step; multiple mature seasons would still be needed before claiming a reliable annual distribution. Public records cannot establish the true frequency of private offers to GMs.

199 focused regression tests passed, including date seeding, season variance, quiet-day inbound review, deadline continuation beyond 28 historical trades, repeat safety, depth-sale season guard, financial/waiver behavior and existing simulation invariants. Verification used audit-owned saves only. No long or overnight job remains running.

## Buyout Versus Stretch

A buyout changes the remaining amount owed by agreement. Our flat 10% concession is explicitly a simplified game convention, not an NBA standard. A stretch is a separate salary-cap allocation election; it is not a new playing contract. Both can be used together, but they are not interchangeable.

For an eligible offseason cap stretch, remaining protected salary is spread over **2N + 1** years. Thus $20M annually for two remaining years means $40M total and an $8M annual cap charge over five years, not $10M over four. In-season timing treats the current season differently. Eligibility, election deadlines, the aggregate 15%-of-cap limit and reacquisition restrictions also matter. Cash payment timing and cap allocation are distinct rules.

The NBA CBA directly distinguishes termination payment schedules from Team Salary stretch elections. No stretch election has been silently added to, or substituted for, the existing buyout action. A future UI should separate Waive, Buyout and Waive-and-Stretch, showing the complete cap schedule before confirmation.

## Actual Waiver Gaps

Our current full-cap-room admission check is more restrictive than real NBA rules. Important missing acquisition routes include the minimum salary exception for eligible one-/two-year minimum contracts, suitable traded-player exceptions, the non-taxpayer/room mid-level and bi-annual exceptions subject to their conditions, and a disabled-player exception for an eligible final-year contract. These do not permit any over-cap team to claim any salary; amount, term, remaining exception balance and apron restrictions still matter.

The highest practical priority is the eligible minimum-contract route: otherwise a team above the salary cap can be blocked from a small claim it could make in real life. Full exception accounting and partial waiver claims are larger work. Other disclosed simplifications remain seeded tied-record priority, an October 1 offseason restriction clock, missing subsequent-employment set-off, and no stretch election. No claim exceptions were added in this pass; the user asked what was missing.

Rules: https://cms.nba.com/wp-content/uploads/sites/4/2024/11/2024-25-CBA-101.pdf (exceptions, pages 3-5; stretch and set-off, pages 17-18); https://www.nbpa.com/cba/ and its current 2023 CBA (Article II termination schedules; Article VII exceptions and stretch elections). Buyout overview: https://www.sportsnet.ca/basketball/nba/nba-contract-buyout-faq-key-dates-salary-cap-impacts/.
