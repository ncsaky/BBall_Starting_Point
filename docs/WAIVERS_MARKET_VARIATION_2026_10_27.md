# Waivers, Market Evidence And Box-Score Variation

Follow-up: [Trade timing and release rules](TRADE_CALENDAR_AND_RELEASE_RULES_2026_10_27.md) adds a completed regular-season pilot, replaces the old 28-trade scheduling ceiling, restricts speculative sale timing and clarifies stretch versus buyout. Earlier frequency limits below describe the initial pass.

## Cuts And Buyouts

All four live cut routes (GUI, CLI, AI camp cutdown and in-season replacement) now start a two-day waiver period. Pending players cannot sign free-agent contracts, even through stale negotiations or old pool-repair code. Old saves' completed cuts are not retroactively reopened.

Claims transfer the existing contract, including salary seasons, options and protection. Eligibility and any selected incumbent cut are rechecked at award. Worse records receive priority; between seasons through November 30, prior-season records are used when available. Record ties use a stable seed. The releasing team cannot claim its own player. The recently traded-player reacquisition restriction is checked. Human claims never automatically choose someone to cut. Losing claims do not cut anyone. A winning claimant's replacement cut starts a NEW two-day period, preventing instant recursive waiver churn.

The daily lifecycle resolves claims before that date's games. Successful claims release the old team's cap responsibility with a recorded adjustment, not deletion of the historical obligation. Unclaimed players become free agents and leave protected obligations behind. Claimed players receive a 30-day trade restriction; the offseason clock uses the game's October 1 boundary.

The Waiver Wire is accessible from free-agent workspaces. Its release section and roster cutdown offer Waive/Buyout. Confirmation lists cap charges and the clearance date. No negotiation minigame was added.

**Explicit game convention, not an NBA rule:** buyout surrenders 10% of verified, unearned protected salary, only if waivers clear. Earned money, clearance-period pay and unknown protection are not discounted. A claimant takes the original contract, not the buyout discount. Remaining charges stay in their original seasons. This implements the requested simple yes/no agreement; it does not claim every real player would accept that concession.

## Natural Trade Evidence

The old search tried the earliest three second-round picks and a few team IDs. Those picks were often too expensive for the unwanted player. It also overlooked saleable surplus depth when the absolute worst projected cut had no buyer.

The bounded search now checks projected cuts and non-core depth projected below eight healthy minutes after the signing. It prioritizes useful buyers and cheaper picks, with small bundles also available. Both teams must accept normally; existing 70%/85% real-return floors remain. The seller must be able to fund and retain its concrete target after the sale. No transaction quota or forced buyer was added. A separate missed-target fallback also no longer overwrites refusal after checking only legality.

Evidence: `output/waiver-market-2026-10-27/final-camp-evidence.json`. In an ordinary seed-913 market, on July 3 Charlotte sold Grayson Allen to Denver for Sacramento's 2032 second. Both evaluations explicitly accepted; legality was legal. Charlotte then bid $13.3M annually for two years on Max Strus. Strus accepted. Target intent is recorded on the trade. The market had seven trades, 44 market signings and 79 offers. Camp subsequently produced four cuts that cleared on October 3 with four retained obligations. No buyer or opportunity was mocked or hand-placed.

`final-market.json` verifies exact complete-state daily/bulk equality for that market. Earlier seed-17/29 markets also matched, but used an intermediate search version and are not the final frequency estimate.

## Trade Activity And Timing

`trade-activity/trade-activity/report.json` covers seven-day regular-season and deadline replays for seeds 17 and 29. Both regular-season windows produced four applied trades; seed 29 also generated one incoming user offer. Deadline windows produced five and four trades. Daily/bulk state matched, including offers, contracts, rosters, health, development and games. Required deadline confirmation was honored under the same policy.

`final-source/final-source/report.json` repeats the deadline test on the final source for seed 17: exact daily/bulk equality, five trades and a natural waiver claim. Phoenix waived Simone Fontecchio February 3; Memphis claimed him February 5 with his existing $2,449,421 salary. The claim was not forced.

Historical V9 saved careers had 28 and 25 regular-season applied trades. Those careers predate these changes. This is context, NOT proof of the new full-season rate. The existing 28-trade regular-season ceiling was not increased. A new full-season frequency calibration remains outstanding; no long season was launched for this task.

## Box-Score Variation

The scoring engine is unchanged. A separately seeded post-scoring pass samples two-point misses from player skill, shared shooting conditions, individual variation and opposing paint defense. Turnovers depend on usage, passing and opposing disruption, with pressure variation. Disruption also affects assists. Rebounds depend on actual misses on both sides and offensive-rebound strengths. Steals/blocks keep role allocation with more game variation. An approximate possession budget limits piling unlimited misses onto high-turnover games.

Final accounting still enforces shooting/points identities, assists versus made baskets, steals versus opposing turnovers, blocks versus shot opportunities and rebound opportunities. Three-point makes/attempts and free throws are preserved: three-point results already varied substantially.

`box-variation.json`: 240 paired games across eight fixed matchups, zero accounting errors and zero changed scores. Across 480 team-games:

| Statistic | Before mean | After mean | Before standard deviation | After standard deviation |
| --- | ---: | ---: | ---: | ---: |
| Assists | 26.97 | 26.47 | 1.40 | 4.03 |
| Rebounds | 43.49 | 41.86 | 2.18 | 7.04 |
| Turnovers | 15.04 | 16.10 | 1.24 | 4.64 |
| Steals | 8.08 | 8.07 | 0.37 | 2.00 |
| Blocks | 5.27 | 5.17 | 0.54 | 1.73 |
| FG percentage | 45.70% | 48.19% | 3.48 percentage points | 5.31 percentage points |

The shooting mean rises because extreme misses are bounded by available possessions. This is disclosed, not presented as league-wide calibration. Scores, winners, player points/minutes and scoring RNG are identical on the same supplied contexts. Future careers may react to changed statistical histories, so identical long-term standings are NOT claimed. The paired sample runs in about four seconds; context/mock warm-up makes the before/after timer unsuitable for claiming a speedup.

## Tests And Remaining Limits

Focused tests cover real action signing/cut boundaries, debt, claims, competing priority, losing-claim safety, original contract transfer, replacement chains, stale claims, cap capacity, buyouts, unknown protection, reacquisition, repeat/reload safety, partition timing, box accounting, sequence variation and matchup direction. Browser fixtures exercise the real client/CSS, keyboard claims, buyout confirmation, shared window chrome and closing at widths 1647/1024.

Not fully modeled:

- All NBA claiming exceptions, partial claims, stretch elections or subsequent-employment set-off. Claims conservatively require full salary-cap room; this excludes some real-world legal exceptions.
- Exact opening-night start for offseason claimed-player restrictions (October 1 approximation), and head-to-head/lottery tie adjudication (stable seeded tie-break).
- Negotiated, player-specific buyout consent. The fixed 10% agreement is a simplified game policy.
- Validated championship probabilities. The forecast compares roster strength; its percentage is not a proven chance of winning a title.
- Full-season trade-frequency calibration, possession-by-possession statistics or exhaustive spatial-zone interactions. Shared paint/disruption/role features are reused, not a second independent heatmap model.

One broader security test fails because its streaming request omits the required simulation ID. The same failure was reproduced against untouched V9 code. The other 22 security checks pass; authentication/streaming code was not changed to hide the failure. Earlier unrelated trade-salary failures remain outside scope.

Rules consulted: [NBA Constitution and By-Laws, sections 5.03-5.06](https://cms.nba.com/wp-content/uploads/sites/4/2024/06/NBA-Consitution-By-Laws-June-2024.pdf), [NBA CBA 101](https://cms.nba.com/wp-content/uploads/sites/4/2024/11/2024-25-CBA-101.pdf), [NBPA CBA portal](https://www.nbpa.com/cba/). The fixed concession is not sourced as an NBA requirement.

Playable saves were not used for verification. No release package or long-season job was created.
