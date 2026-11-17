# Ranked pick entitlement valuation

## One outcome, one value

Each recognized same-season, same-round ranked pool assigns one stable rank to each existing asset ID. Trading an asset changes its recipient, not its rank. Draft resolution sorts the physical picks once and distributes them to the owners of those rank assets. A team entitled to two picks has two independently valued outcomes; it does not receive duplicate value for component comparison rights.

Examples:

- 2029 HOU/PHX/DAL: HOU's two assets represent ranks 1 and 2; BKN's asset represents rank 3.
- A three-pick middle entitlement is rank 2, regardless of which original team eventually generates that pick.
- Trading rank 2 to another team transfers that same rank; it does not convert the guarantee into the original leaf pick.

## Projection and timing

Use the existing future roster/record-based projected draft slots. These already adjust for age, development and future regression; the new calculation does not regress them a second time.

For positions not yet determined, use 96 deterministic paired scenarios (48 sets of deviations, each evaluated with both signs). Each team's draft position is perturbed around its projected slot. The standard deviation is `min(10, 2 + 1.3 × years until draft)` positions, bounded to its round's 30 slots. This is a transparent gameplay weighting, not an empirically calibrated probability forecast.

Actual `overall_pick` positions remain fixed. If every pool position is known, valuation uses the exact sorted outcome.

## Existing value curve

For each scenario, sort positions from earliest to latest. Price the selected rank using the existing first/second-round pick curve, distance discount, rebuilding/developing premium, contending discount and applicable protection multiplier.

The existing future random value nudge is disabled within these scenarios: positional uncertainty is already represented by the scenario distribution. No fixed optional-swap premium is added. Best and worst outcomes both remain positive full-pick assets.

Average the scenario values at each rank. The sum of all rank values equals the pool's average total value, apart from rounding. Thus an owner receiving two picks receives the sum of two ranks, not a second copy of all possible leaves.

Cache the complete rank-value vector per pool, projection and team phase so AI package evaluations reuse the same results.

## Conservative boundaries

Only proven ranked allocation networks qualify. Protected pools, mixed better/worse rules, and dependent external comparisons retain their existing treatment until a conditional-outcome model can price their branches honestly. They are not silently interpreted as best-of-all pools.

No new pick IDs or ownership-reset migration is introduced. Rank slot metadata follows the original allocation owners from the save's baseline; current owners determine who receives each outcome.

Verification completed: source review and syntax checks. Automated tests and simulated draft/trade runs were not run.
