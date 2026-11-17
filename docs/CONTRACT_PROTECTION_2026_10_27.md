# Contract protection and final-roster planning

Follow-up: [Waivers, market evidence and box-score variation](WAIVERS_MARKET_VARIATION_2026_10_27.md) supersedes this initial pass's no-claims/no-buyouts limit.

## Implemented

- Free-agent and extension forms have a native Guaranteed checkbox. New offers default to full salary protection; removing it raises the player's acceptance price. Existing salaries, term controls, card dimensions and desktop layout are retained.
- New AI offers and newly produced direct AI contracts explicitly record protection. Legacy agreements without that information remain unknown, rather than being silently rewritten.
- User GUI cuts, CLI cuts, AI preseason cuts and in-season replacement cuts record a separate save-owned waived-salary obligation before changing ownership. A subsequent contract does not overwrite that obligation. Replays are idempotent, and distinct agreement identities remain separate.
- Payroll, cap projections, signing checks, trade matching and salary-posture calculations include the obligations. They are not outgoing trade assets. Explicitly unprotected outgoing salary does not manufacture matching credit.
- Waiver previews show the estimated remaining obligation before confirmation. Unverified terms are labeled as reserves; unquantified salary is not shown as free cap room. Payroll charts retain their geometry and identify waived salary in the remainder.
- Non-guaranteed salary still includes modeled earnings through the two-day clearance interval and activation at the annual guarantee date. Short-term injury protection is not assumed absent: uncertain injury continuation gets a disclosed current-year reserve.

## AI Decision

Before bidding, and again before accepting, an AI team projects a healthy two-deep rotation and its final 15-player roster. It uses the existing retention valuation, including bounded youth upside and draft-age preference, rather than inventing a second talent scale. Pending bids reserve players as well as money. A prepared day-resolution view is overlaid with earlier same-day signings and cuts before the next decision.

Only cuts newly caused by the proposal are charged to its marginal roster plan. Existing camp overflow is not repeatedly blamed on each new signing. Teams reject a signing expected to be cut, a bid that displaces an outstanding commitment, unquantified replacement obligations, costly zero-role duplication, or an upgrade too small for the dead-salary efficiency loss. Useful young development projects can still qualify without immediate rotation minutes.

Live contending teams tolerate more spending for upgrades; rebuilding teams put more weight on flexibility. This uses the corrected live strategy classification, not imported phase labels. Cost gives a bounded retention preference, not immunity to cuts. The 21-player camp allowance remains intact.

The financial ledger charges protected salary once. It does not levy a fictional fine on top of that salary. The AI's additional dead-money weight is a tunable efficiency preference, not another cash or cap debit. These coefficients are initial tuning, not a demonstrated optimum or a complete championship-window model.

## Imported Evidence

The pinned research snapshot covers 461 source players. Publication into a save requires a unique normalized identity, the expected player ID, and exact equality across every remaining salary year. Older salary years may exist in the baseline but are not invented in the research table. This currently admits 145 contracts and 211 non-option season amounts.

Evidence is captured once per save and cannot activate before its retrieval date. Changed contracts and save-owned overrides do not inherit source terms. Partial aggregate guarantees are not arbitrarily allocated to individual years, and option exercise is not assumed from a headline guaranteed total. Unknown terms reserve nominal known salary; that reserve is not represented as a verified real-life guarantee.

Research source: [Basketball Reference contract table](https://www.basketball-reference.com/contracts/players.html), captured October 27, 2026, including retrieval time and HTML hash in the research JSON.

Rules reference: [NBA CBA 101](https://cms.nba.com/wp-content/uploads/sites/4/2024/11/2024-25-CBA-101.pdf), sections II.J-M and VI.A. Protected waived compensation remains in team salary. The reference separately describes summer contracts, stretch elections, set-off, protected outgoing trade credit and the 48-hour waiver period.

## Verification

- 128 focused Python tests passed, covering contract actions, accounting, protections, research matching, retention, role reassessment, replay boundaries and roster repair.
- 24 focused payroll/trade-workspace JavaScript tests passed.
- Actual free-agent and extension markup, controls, keyboard toggling, submitted booleans and fit verified with Playwright at 1647, 1024 and 390px. A narrow mobile free-agent form correction prevents its controls collapsing; desktop geometry is unchanged.
- Disposable real app-action tests signed and waived both protected and unprotected two-year contracts, reloaded, rejected duplicate cuts, signed the player elsewhere, and checked that the old employer's obligation remained unchanged.
- Two seeded five-day free-agency replays reached September 1 with exactly identical meaningful state under daily versus bulk advancement. Planned runs produced 49 and 57 signings. Bypassing only the roster-plan check produced 54 and 60; all other financial changes were retained in this comparison. This is evidence of selective admission, not proof of long-term roster quality.
- Planned daily/bulk market runs took roughly 37-46 seconds each on this machine, versus roughly 36-38 seconds with the planning check bypassed. No full seasons were simulated for this task.
- Final four-day real-action replay crossed October/November with 28 games and exact daily/bulk/next-event parity. Earlier two-seed checks also matched. This regular-season window generated no trades, so it is not evidence of transaction parity on its own; the free-agency replay supplies that evidence separately.
- Evidence: `output/contract-protection-replay/free-agency-final.json`, `output/contract-protection-replay/contract-protection-final/report.json`, and `output/contract-protection-ui/`.

Broader checks are not all green. Six trade-salary failure reports and an empty-finder assertion are the already documented frozen-backend failures. Two legacy-save persistence assertions also fail identically on the frozen V9 backend because reads add `staff_season_changes`. Five player-page VM tests and one extension-preview VM test fail with missing DOM/helper dependencies; their extracted code is outside this change. These tests were not weakened or represented as fixed.

## Boundaries

- Applies to new waivers; historical missing obligations are not reconstructed from incomplete careers. No playable save was edited during verification.
- No automatic waiver-claim auction, set-off credit, buyout or stretch election. Resigning elsewhere does not currently reduce the old obligation. Ledger entries explicitly record that no such relief was applied.
- Clearance dates affect salary estimates and guarantee activation, but do not add a new interactive 48-hour waiver queue; the existing free-agent availability workflow remains.
- Earnings use the game's actual regular-season calendar, not a complete CBA payroll-day ledger. Missing schedules and injury-continuation terms use conservative reserves where necessary.
- This is not a complete exception/summer-contract system. Existing nominal-salary admission rules and the game's minimum-contract exception remain; the checkbox does not turn a deal into an Exhibit 9/10, qualifying offer, two-way or sign-and-trade contract.
- The four-stage championship-window model and persistent commitment to a recently acquired core remain separate work. No stat-variance, prospect-rating or heatmap changes were made here.
