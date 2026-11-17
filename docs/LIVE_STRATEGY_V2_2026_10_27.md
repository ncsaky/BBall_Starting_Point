# Live Strategy V2 And Guarantee Research

## Completed

Imported research timelines can no longer force a team to remain contending or
rebuilding. `classify_team_phase` now uses live contention index, core age,
youth and picks for every team. A genuinely elite young roster is not held in
development merely for being young. The public function signature and existing
phase keys remain compatible with trade, draft, signing, staff and UI consumers.
The strategic state's `timeline` now agrees with its actual computed phase;
historical research profiles themselves are not rewritten.

A versioned runtime cache marker invalidates old precomputed strategy and its
dependent contract projections. `with_contract_context` cannot return early
with stale strategy. Rebuilt contexts remain reusable; this is not an expensive
rebuild for every package evaluation. The fix does not change player traits,
prospect outcomes, user rotations or saved canonical baselines.

Near-term draft picks now mean the next three draft years based on the active
simulation date, not literal 2026/2027/2028 years. This repairs a related input
to the live team phase in later careers.

Current starting-roster inspection changed ATL, DAL, GSW, NOP, SAC and WAS phase
labels. Sacramento's prior source-driven contending status no longer overrides
its lower live index. No team is hardcoded into a replacement phase.

## What This Does Not Claim

This is not yet persistent core commitment or championship-window forecasting.
The user's proposed stages -- rebuilding, entering, peak and exiting a
championship window -- are the agreed design direction for that later layer.
They should reflect roster trajectory and evidence, not replace one static label
with another. Existing phases remain in use until that shared plan is implemented.

Existing thresholds classify 22 current rosters as either contending or
contending-with-future-upside. This is the engine's broad roster-strength label,
not a calibrated assertion that 22 teams are serious title favorites. No title
probabilities or threshold tuning were invented in this repair. Relative league
strength and trajectory remain important next calibration inputs.

Temporary-availability effects and phase stability still need the persistent
plan/meaningful-season review layer. This fix removes an unconditional historical
override; it does not certify every future pivot as coherent.

## Verification

131 focused tests passed, including live-strategy/cache tests, AI roles,
extensions, roster retention, free-agency bids, calendar consistency, picks,
transaction application audit, box-score reconciliation and offensive roles.

Real app-action disposable replays cover October 28-November 1. Seeds 17 and 29
match across daily, bulk and next-event advances. After the final contract-cache
guard change, seed 17 was rerun through daily/bulk paths: identical meaningful
saved state, 28 games in each path, normal save/reload boundaries. No real trades
occurred in this short window; it is not a renewed deadline or offseason audit.
No playable saves were advanced and no multi-season runs were started.

Evidence:
`output/live-strategy-2026-10-27/live-strategy-v2/report.json` and
`output/live-strategy-2026-10-27/final-live-strategy-v2/report.json`.

A broader 122-test trade-inclusive run reported seven failures. The same seven
were reproduced against the untouched frozen V9 backend: six salary-application
failure reports and one empty scoped-finder result. These are pre-existing
failure reports, not presented as resolved or all proven gameplay bugs. The
focused passing suite is not a claim that the whole repository passes.

## Guarantees: Research Completed, Feature Not Shipped

The user prefers explicit guarantee negotiation plus researched imported terms,
not a blanket hidden assumption. The proposed offer control is a simple
guaranteed/non-guaranteed choice; the backend must still represent partial
protection and activation dates when imported contracts require them.

Fresh capture:
`data/research/contract_guarantees_2026_10_27.json`.

`scripts/research_contract_guarantees.py` uses a standard HTML parser with named
table fields and preserves option markers. It captured 461 players, 446 with
unique provisional name matches in the canonical roster. Season evidence:

- 584 non-option season amounts whose sum matches the reported remaining
  guarantee total, marked as a derivation rather than individually reported terms.
- 367 option seasons requiring exercise/protection review.
- 177 other season amounts with unresolved protection.

A total guarantee below the listed non-option salary sum is not allocated
arbitrarily across years. Blank amounts are unknown, not zero. Option years are
not silently declared non-guaranteed. Candidate name matching is not final
identity/contract validation. The capture records the URL, retrieval time and
raw-page hash. The source is [Basketball-Reference's contract ledger](https://www.basketball-reference.com/contracts/players.html).

The earlier importer looks for `guaranteed`, while the saved research snapshot
uses `remaining_guaranteed`; that mismatch drops available aggregate evidence.
Merely renaming the key is insufficient: an aggregate total is not a per-year
waiver liability, and later guarantee activations must not be backdated into a
July-start career. This pass therefore does not publish those research rows into
an existing baseline or change payable obligations.

## Next Contract Implementation Boundary

Land these together rather than exposing a cosmetic checkbox:

1. Explicit negotiated protection, persisted through offers, counters, acceptance,
   extensions and AI signings. Existing inherited seasons must keep their terms.
2. Player interest in financial security: fringe players price the chance of
   being cut; stars should not happily accept non-guaranteed deals just because
   a narrow model predicts a low cut probability. Constants require calibration.
3. Supported legal contract structures, per-season protected amounts and
   guarantee activation. A non-guaranteed deal must not remain freely voidable
   forever regardless of service or guarantee dates.
4. A separate immutable-per-waiver obligation ledger, surviving a later signing,
   trade, reload or second waiver of the same player. Do not overwrite former
   team obligations through the current player-keyed contract override map.
5. Shared active-payroll plus waived-obligation totals in cap checks, trade salary
   legality, strategic spending posture, signing budgets and payroll displays.
   Dead salary must never be counted as outgoing trade salary.
6. Roster-plan-aware replacement costs. Retain the 21-player camp allowance;
   keep sensible upgrades and cheap auditions possible. No artificial penalty
   or universal ban on cuts.
7. Versioned, identity-checked imported guarantee data with clear unknowns and
   as-of dates. Partial guarantees, options, waiver claims, set-off and stretch
   must be distinguished; unimplemented relief must not silently erase debt.

No guarantee control, player-interest tuning or dead-salary accounting is enabled
by this pass. Secondary-stat variability is also deliberately deferred while the
higher-priority strategy and financial work is being separated and verified.
