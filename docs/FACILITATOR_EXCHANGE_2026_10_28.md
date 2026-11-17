# Facilitator Exchanges, October 28, 2026

## Actual Offer

Read-only inspection of `saves/bos_1395542256.json` confirms the January 17 and January 18 pending Boston/San Antonio/Detroit offers. Detroit receives Julian Champagnie and a second-round pick but sends no asset. This is a generator/validation defect, not a new player-price judgment.

The compensated salary-absorption branch appended the unwanted salary and the compensation pick to the third team's incoming package, without adding a return leg. Graph validation required connectivity but did not require each participant to both send and receive.

## Repair

- Shared multi-team legality now requires an incoming and outgoing asset for every participant, derived from actual transfer legs rather than the declared team list. This does not require every pair of teams to trade directly with each other.
- The salary-absorption generator considers small existing swap rights, new second-round swap options backed by both teams' real available same-year picks, expendable non-core players and a cheap second-round pick. An ordinary second is not mandatory. No token asset is manufactured, and a return player cannot eliminate the actual salary absorption. The nominal asset must cost less than the received compensation before the full GM evaluations; expensive returned players and unwanted salary can still cause rejection.
- New swap options use the existing compiler, ownership/collateral checks and eventual resolution logic. Comparison picks already used in the package cannot be reused. The generator considers up to three low-cost return choices, with 24 evaluations per near-miss and the existing global 64-evaluation limit. Existing routes where the facilitator pays for a wanted player remain unchanged.
- Every party still evaluates the complete package. No prices, acceptance tolerances, player ratings or trade-frequency parameters changed.
- Saved malformed offers are marked illegal in the read-only incoming-offer payload, which disables the existing acceptance button. They cannot execute even if their stored legality and approval flags say otherwise. Existing saved offers are not silently rewritten or removed.

## Verification

The final nominal-return implementation passes 190 focused Python tests (79.683 seconds). Nominal-return coverage adds a backed swap that is priced below a full second, checks compiled obligation ownership, and confirms that expendable players remain options without available picks. Other tests cover receive-only/send-only teams, forged historical approval and failure-atomic execution, real owned return rights in generated compensation routes, skipping compensation when no eligible counter-asset exists, and presenting an old malformed offer as illegal without mutating it.

The actual January 17 offer now reports `DET must send at least one asset in a multi-team trade.` Trying to apply it to an in-memory copy leaves that copy unchanged.

Adding Detroit's existing `pick_det-2033-2` as a return to San Antonio makes the package structurally legal. Both AI participants approve against the current saved roster. With explicit test-only Boston consent, settlement succeeds on a disposable in-memory copy: Champagnie and the original Spurs second go to Detroit, and Detroit's second goes to San Antonio. The real source save remains byte-identical. This test is not an accepted trade in the playable career.

Evidence: `output/facilitator-exchange-2026-10-28/actual-offer.json`. Scoped whitespace checks and compilation pass. No UI styling, valuation tuning, long simulation or release packaging was performed.

## Nominal Return Follow-Up

The actual Boston/San Antonio/Detroit offer also works structurally with Detroit granting San Antonio a 2033 second-round swap option instead of sending its entire second. That option is priced at 2.42 neutral value points rather than the whole pick. Detroit and San Antonio both approve. A disposable execution creates the actual swap obligation, rather than transferring the underlying pick outright. An equivalent 2032 swap also passes; returning Duncan Robinson is rejected by the existing future-salary legality checks. Source-save bytes remain unchanged. Evidence: `output/facilitator-exchange-2026-10-28/nominal-returns.json`.

No new no-fallback/expiring-protection type was invented here. Existing protected-pick rules require actual fallback collateral, whose value must not be silently ignored to call a right nominal. Small backed swaps and fringe assets solve this route without changing draft resolution rules.

Port 8776 was restarted after the user explicitly authorized interrupting its simulation. The new process responds successfully and uses the current source. Existing malformed offers remain in the saved history, but their refreshed presentation is illegal and execution is blocked; they were not silently replaced by a different offer.
