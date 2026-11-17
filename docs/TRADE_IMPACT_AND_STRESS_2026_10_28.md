# Roster Impact And Trade Search Under Pressure

## Scope

This pass repairs the demonstrated return problems and tests increased market pressure now, rather than postponing it until every quality issue is resolved. Stress is an audit-only multiplier on date-based opportunities, not a production quota or permission to force agreement. Ratings, development, game-result formulas, user rotations and visuals are unchanged. Existing playable saves and prior annual careers were not edited.

Evidence lives in `output/trade-impact-stress-2026-10-28/`. The `before17` and `before29` runs capture the original problem contexts before production edits. The `impact-after.json` report reprices those exact packages and applies isolated ownership changes for before/after roster forecasts.

## Roster Forecast Repair

The old contention estimate used `team_feature_vector` directly on a roster carrying each player's old minutes. Adding a player could force him into the weighted average without reducing anyone else's minutes. Even unused reserves had a minimum weight. This could make an additional available player appear to weaken the team before a coach changed the rotation.

Strategic forecasts now use an isolated, workload-neutral copy, the existing position-aware two-deep role planner, and a choice of eight-, nine- or ten-player rotations. Minutes total 240 and inactive players are excluded. This is only a forecast; it does not write rotation baselines, recommendations or user sliders, and it does not change the simulation's game calculations. Core age now follows the strongest current players rather than the highest contract/upside asset prices.

In the frozen Hield case, Toronto's old estimate fell 0.83 and its window flipped entering to exiting. The corrected isolated comparison is 73.23 to 73.26, with Toronto entering before and after. No Toronto-specific rule or phase hard-code was added.

Limits: this remains a healthy-roster planning estimate, not calibrated championship odds or an exhaustive search of every lineup. The role planner uses a basketball-fit scoring approximation. For example, the same frozen case still estimates a small Chicago improvement after losing Hield; universal monotonicity under every optional reserve addition/removal is not established. Temporary health and actual user decisions still belong to the separate simulation/health systems. Do not equate these forecast deltas with measured changes in title probability.

## Return Rules

Premium current contributors require a replacement within four on-court points and eight playoff-value points, rather than accepting any player within six current-impact points with a generic playoff floor. Credible young centerpieces and substantive draft compensation for actual sellers remain alternatives. Bad contracts and high health risk retain their separate treatment.

Competitive teams also protect valuable current starters: at least 68 on-court value and a meaningful rotation role, with acceptable contract/health context. An entering team cannot treat much weaker depth plus a late first as sufficient replacement just because the pieces add up to a positive price. Rebuilding teams can still trade useful starters for future assets; a review exception can still justify a different direction. Human-controlled sellers remain free to decide.

- Frozen Jokic-for-Siakam/Fofana: Denver now returns `reject_premium_return`; automatic execution is blocked. The current-impact drop is still visible rather than hidden by a changed rating.
- Frozen McDaniels-for-Green/Trent/Cross/first: entering Minnesota now returns `reject_premium_return`; automatic execution is blocked.
- Both previously captured Kawhi packages remain blocked. The complete Siakam/Turner/Powell/two-first package remains blocked by Miami's corrected price. The contract-sensitive Trae package remains eligible for bounded discretion.

These are first-pass return boundaries, not proof that every permitted trade is fair. There are no player-name/team-name exceptions. Repeated copies of one first no longer add up to substantive compensation in this guard; ordinary legality also rejects duplicate assets.

## Incoming Search And Creative Rights

The old incoming-offer route filtered a league-wide candidate list after search. That search stops after an accepted buyer for each target and has a global result cap. AI buyers could consume the useful results before the human team was considered. Merely increasing notification capacity would not fix that.

Incoming offers now have a dedicated `involving_team_ids` search in both regular-season and summer paths. Unrelated buyers cannot consume that search budget. Ordinary date-based offer capacity, financial legality, acceptance and explicit human response remain in place. General AI trading keeps its own search. A third search-depth tier allows stress runs to inspect up to 18 buyers and 24 package options per target with a 12-player candidate pool; normal depth-one/two budgets are unchanged.

Stress uncovered another mechanical bug: `candidate_from_evaluation` dropped `pick_obligation_terms`. The generator could propose a new swap but the saved candidate lost the instructions needed to create it. Candidates now preserve those terms and the associated display metadata. The new regression demonstrates that the swap fails live validation without its grant and passes with it.

New swap grants reserve both underlying subject picks. An offer is marked stale when a subject moves; application checks changed ownership, locked collateral and an already-active grant over the same pair. A swap is not permission to create duplicate entitlements over unavailable assets. Existing transferable swap rights are distinct from newly granted rights.

## What The Search Actually Supports

| Route | Current Capability | Important Limit |
| --- | --- | --- |
| Player packages | One target player; buyer can bundle multiple players and picks | Seller-side multi-player counterpackages are not a general search primitive |
| Draft assets | Firsts, seconds, existing protected/conditional rights, existing swaps, newly granted swaps | Automatic search does not broadly invent protection/fallback structures; structured authoring support is not the same as AI search |
| Three-plus teams | None in the transaction settlement backend | UI participant support does not provide atomic multi-team legality, consent or application |
| Salary relief | Pick-only absorption, targeted cap dumps and roster-space sales | Salary-matching failures do not currently trigger a general facilitator-team search |
| Roster cuts/waivers | Date-driven cutdowns, claims and retained obligations | Not a general hypothetical cut-then-trade search branch |
| Buyouts | Date-driven AI reviews and later destinations | Not guaranteed or forced to increase transaction count |
| Stretch | Eligible existing debt can fund a concrete competitive summer bid | Rare; no natural stretch was observed in these stress samples |

This answers the creativity question: the engine does use varied two-team bundles and draft rights, but it is not yet a general multi-team dealmaker. More opportunities alone cannot supply missing transaction structures.

## Stress Method

`scripts/audit_trade_stress.py` restores a disposable export and runs real app actions. It multiplies existing market opportunity capacities by three and broadens search; it does not change consent, salary rules, retirement, ratings or development. Quiet/non-review dates remain quiet. Summer retains its production maximum of two applications per phase. This deliberately distinguishes bigger candidate load from unlimited settlement capacity.

Every evaluated package is counted by shape and decision/legality reason. Completed observations are joined by proposal ID to the durable ledger, filtering to the tested interval so old trades in a restored career are not double-counted. User offers are counted by unique delivered proposal ID, including stale/expired states. The source save hash and Python engine fingerprints are checked.

### Final Stress Results

| Final Production Code | Deadline Seed 17 | Summer Seed 29 |
| --- | ---: | ---: |
| Interval | Jan 31-Feb 10, 2027 | July 1-Sept 1, 2027 |
| Evaluated packages | 37,053 | 24,740 |
| Packages containing swap rights | 9,005 | 5,754 |
| Committed trades | 35 | 8 |
| Delivered user offers | 51 | 5 |
| Swap-right assets in completed trades | 6 | 1 |
| Newly created swap grants committed | 5 | 1 |
| Existing protected-pick transfers | 2 | 2 |
| Roster cuts | 20 | 0 |
| Waiver claims | 4 | 0 |
| Initiated buyouts | 4 | 0 |
| Salary stretches | 0 | 0 |
| Runtime, seconds | 340.82 | 294.23 |

Both runs reached their endpoints, with unchanged engine fingerprints and unchanged source-save hashes. Durable trade/observation coverage is complete (35/35 and 8/8). Every committed swap has its defining saved obligation, obligation IDs are unique, and observed claimed releases zero their original obligations. These are bounded stressed windows, not annual trade targets.

At the deadline, 23 delivered offers became stale after assets moved and 28 expired after the deadline; there were no duplicate delivered proposal IDs. In summer, four remained pending and one became stale. Expired/stale notification state is not a missing generated offer or an extra completed trade. Users were not made to accept any offer.

All four deadline buyouts cleared and found subsequent destinations: Javonte Green to Atlanta February 9, Jae'Sean Tate to New Orleans February 10, Larry Nance Jr. to San Antonio February 9, and Harrison Barnes to Charlotte February 9. Waiving teams retained their obligations. The summer stress case had no explicit target-linked sale; the earlier annual examples remain the evidence for that route, not events invented in this sample.

The pre-terms-repair stress samples examined 38,822/25,411 packages and completed 26/6 trades. Preserving the terms enabled actual new grants and more settlements without lowering agreement thresholds. The final collateral-reservation reruns are `final-deadline17` and `final-summer29`; earlier `stress-*` directories are diagnostic intermediate versions, not final-code verification.

Salary matching is the dominant illegal-package reason. Roster minimums and recent-signing restrictions also block many summer attempts. High-depth searches took up to approximately 37 seconds each; search time totaled 158.54/133.799 seconds within the stressed runs. The depth-three budget and threefold opportunity multiplier are audit-only, not new production defaults. More opportunity does not guarantee more trades in every career because earlier settlements change later rosters.

### Where Additional Supply Comes From

A read-only comparison on the same preserved seed-29 July checkpoint found 13 accepted non-conflicting candidate proposals using listed targets, versus 23 when private non-core rotation inquiries were included. Ten private-target candidates were found; no transactions were applied by this probe. Runtime was 18.094/21.505 seconds. This demonstrates additional candidate supply, not ten additional completed summer trades. File: `private-supply29.json`.

### Consistency And Tests

- Final code, January 31-February 7: both seeds 17 and 29 produced identical meaningful saved state in daily/save-reload and bulk modes. Seed 17: 22 trades, 17 offers, 55 games; 165.295/151.722 seconds. Seed 29: 26 trades, 18 offers, 55 games; 139.681/131.519 seconds. Required deadline confirmation was preserved. File: `final-collateral/report.json`.
- Final code, the preserved seed-29 summer checkpoint: daily/save-reload and bulk both reached September 1 with identical full meaningful saved state, nine July trades and four general trades. Runtime 160.255/144.699 seconds. Source fingerprint unchanged. File: `final-summer-parity29/report.json`.
- 228 focused tests passed for forecasts, role allocation, premium/starter returns, contracts, salary/application rules, terms, collateral ownership, waivers, cutdown planning, user rotations, deterministic scheduling and audit non-mutation. This is not a claim that the entire repository suite passed.

One additional legacy foundation test, `test_ai_offer_packages_can_create_pick_swap_sweeteners`, fails on its live CLE/NOP/DeAndre Jordan fixture. That fixture currently offers zero permitted swap-grant options; substituting the old contention forecast still produces no swap packages. Increasing its shortlist from 12 to 64 did not help, and that experimental test edit was reverted. No collateral/ownership rule was loosened to force the fixture to work. Controlled term/application tests and six naturally committed new grants provide the current positive coverage; the legacy fixture still needs a stable explicit asset setup.

The summary and underlying events are `final-summary.json` and `final-*/market-events.jsonl`. No new full-year or multi-season careers were needed. All simulation processes from this pass have finished.

## Remaining Priorities

1. Salary-aware package ranking and a facilitator-team prototype. Salary matching dominates failed attempts; relaxing acceptance is the wrong response. Atomic three-team settlement needs to precede real facilitator search.
2. Add seller-side balancing pieces and structured protection/fallback variants to search, with collateral reservations and full application tests.
3. Reconcile draft-specific acceptance with ordinary recorded evaluation. The earlier ten draft overrides are not fixed by these return/search repairs.
4. Integrate a June player market and wider offseason calendar activity. The two stress windows are not a new annual-frequency calibration.
5. Continue checking elite return quality and forecast stability from frozen contexts, without rerunning multi-season balance careers for each small change.
