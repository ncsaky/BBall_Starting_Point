# Premium Trade Returns And Mixed-Age Cores

## Scope

This pass fixes trade-pricing role errors, distinguishes a capable young core from an aging supporting star, and requires a credible reason for an AI team to surrender a premium playoff contributor. No player traits, ratings, development rules, simulation rotations or visual layouts changed. There are no player-name or team-name exceptions in the production changes.

## Confirmed Causes

1. Outgoing package members were added to a roster that already contained them. When ranking one player's role, other package members could therefore count twice, understating their current team's outgoing value.
2. Projected trade roles were ranked by asset value, which includes cheap contracts and future upside. Those are legitimate price considerations but should not demote a better current basketball player behind a less capable prospect. Roles now rank by on-court quality, with a compatibility fallback for legacy fixtures missing that field.
3. The window forecast treated a negative near-term top-five trend as evidence the entire team was exiting. Toronto's young/prime foundation could therefore be labeled exiting because Kawhi was old. An unused veteran's decline also entered that forecast. Ready young support and the presence of a young high-quality anchor now keep a competitive non-peak team entering, while the negative near-term trend remains visible. Healthy zero-minute reserves are excluded from the forecast; unavailable rotation players retain their relevance.
4. Even after those mechanical changes, Toronto's additive valuation preferred depth/picks to retaining Kawhi. A team can believe a package has useful pieces without having a sensible reason to give up its premium contributor. Valuation approval alone did not protect that distinction.

## Return Requirements

The additional check applies to AI sellers of healthy, high-impact playoff contributors under the model's existing high-end quality ranges. It does not make all high-OVR players untouchable.

- A comparable current contributor or a credible young centerpiece can satisfy the structural requirement. Ordinary price, legality and core-commitment checks still apply; satisfying this check does not force acceptance.
- A team that is rebuilding, exiting, or explicitly reviewing its core can instead accept substantive first-round compensation. Its actual pick valuation, including its existing protections/context, matters; a few second-round labels are not automatically enough.
- An entering/peak core is not treated as rebuilding just because a pile of depth and picks adds up to a large number. Serious injury/trade-pressure review exceptions remain available.
- Clearly bad contracts, high health risk and lower two-way/playoff impact are not given an unconditional premium floor. Human managers remain free to control their own assets.
- A structural rejection has an explicit decision code and cannot be reversed by bounded automatic acceptance. Evaluation notes now respect the actual acceptance decision instead of displaying an additive-value acceptance beside a structural rejection.

These are conservative first-pass decision boundaries, not empirically calibrated market prices or championship odds. In particular, cheap-contract contributions and pick valuations still deserve independent calibration.

## Unchanged-Package Evidence

The previous annual observers did not preserve full pre-trade universes. Rather than approximate them using end-of-year rosters, disposable summer checkpoints were replayed with the annual evidence's original summer search policy. Full pre-trade contexts were captured for all four named deals. Before any production change, repricing reproduced both sides' recorded incoming values, outgoing values and net values exactly in every case, including the original evaluation seeds.

Seed 17's bounded capture replay took 510.77 seconds through December 18; seed 29's took 147.44 seconds through the summer. These are capture runs, not new full-year frequency estimates. Both completed with unchanged Python source fingerprints. The original saved careers were not modified.

| Original Package | Before | After |
| --- | --- | --- |
| Kawhi to Boston for George, Scheierman, protected first and second | Executable through discretion; TOR exiting | TOR entering; TOR rejects missing centerpiece; BOS also rejects revised price |
| Kawhi to Detroit for Bridges, DiVincenzo, Joe and second | Both valuations accept | TOR entering; TOR structurally rejects depth-only return; automatic override blocked |
| Siakam to Miami for Turner, Powell and two firsts | Executable through discretion | Not executable: MIA rejects revised package price; IND still accepts the complete return |
| Trae to San Antonio for Grant, Adams and second | Executable through discretion | Still possible; no blanket premium-player prohibition |

Toronto's old Detroit package values were 120.069 received versus Detroit's 23.598 surrendered. Role corrections alone changed those to 148.331 versus 162.386. This demonstrates that a large part of the earlier asymmetry was mechanical, but it did not solve the seller's basketball decision. After updating the window classification, Toronto still had a positive additive net of 24.977; the new structural check correctly refuses that particular return despite the positive sum.

The Siakam result must not be misrepresented: the fix does NOT make Indiana agree the package is inadequate. Its two firsts remain real compensation. Miami now balks at paying the corrected cost. That is different from proving Indiana's return ideal or fully calibrating star value.

Evidence under `output/premium-trade-review-2026-10-27/`: `before.json`, `roles-only.json`, `roles-window.json`, `after.json`, the two `seed*/contexts.json` indexes and compressed contexts. `scripts/review_premium_trade_packages.py` can reprice those unchanged packages without simulating more seasons.

## Real-Life Reference

Official transaction examples informed the distinction, not exact price coefficients:

- Siakam's 2024 trade included three firsts alongside players. [NBA transaction summary](https://www.nba.com/news/raptors-pacers-pascal-siakam-trade)
- Leonard and Green returned DeRozan, Poeltl and a protected first. [NBA transaction summary](https://www.nba.com/news/report-san-antonio-spurs-toronto-raptors-engaged-serious-talks-kawhi-leonard)
- Brooklyn's Durant return combined Bridges, Johnson, four firsts and a swap. [Nets announcement](https://www.nba.com/nets/news/brooklyn-nets-acquire-mikal-bridges-cam-johnson-and-draft-compensation-in-four-team-trade)

These varied outcomes support retaining room for different centerpiece/pick structures and circumstances, not imposing a universal number of picks or a blanket "stars cost more" surcharge.

## Verification

- 163 focused tests passed for salary/application safety, roles, windows, premium returns, market scheduling, releases/claims, core planning and simulation consistency.
- Another 38 passed for trade presentation, finder, picks, contract displays, observer and reporting. One finder fixture had an expired Seth Curry contract; it now uses a current-contract Moody example, with a separate expired-contract rejection test. No legality rule was weakened to manufacture an offer.
- Seed 17, January 31-February 7: daily and bulk saved state matched exactly, excluding incidental metadata. 19 trades, 10 generated user offers, 55 games; 106.471 and 99.938 seconds.
- Seed 29 over the same dates: identical state, 20 trades, nine offers, 55 games; 106.338 and 100.062 seconds.
- Seed 29 from the preserved July 1 checkpoint: daily/save-reload and bulk both reached September 1 with identical meaningful state, five July trades and three general trades. Runtime 145.158 and 132.814 seconds; source fingerprints unchanged. This is not evidence of five trades as a desired quota.

Replays remain active markets; the changes did not obtain parity by disabling activity. The source-version change invalidates stale derived strategy, and the plan-version change causes the next deterministic review to update persisted intent. No long multi-season run or packaging was required. Full-year trade quality/frequency after these changes, June's missing player-trade route, and comprehensive conditional-pick price calibration remain follow-ups.

Full-year follow-up completed: `docs/PREMIUM_MARKET_ANNUAL_VALIDATION_2026_10_27.md`. The two current-engine careers produced 38/39 annual trades with complete observation coverage and natural target-linked sales, but also exposed remaining elite/starter return issues, window-estimate sensitivity, and a separate draft acceptance policy. Those findings do not erase the exact-package repairs above or establish that the whole trade market is now calibrated.
