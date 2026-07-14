---
type: adr
status: accepted
decision: structured-pick-obligations
reviewed: 2026-07-10
tags:
  - decision/draft-picks
  - gameplay/trades
---

# ADR-005: Structured Pick Obligations

## Context

Startup pick data and trade-created protections/swaps were initially represented partly as prose. That prose could not reliably drive value, lock collateral, transfer rights, resolve lottery outcomes, or keep labels consistent across views.

## Decision

Represent protected picks and pick swaps as structured save-backed obligations with exact pick IDs, teams, rights holder, terms, status, history, and resolution behavior. Generate labels from those records.

## Why

- One source of truth for display and gameplay.
- Validators can reject impossible terms.
- Rights can be retraded.
- Fallback collateral can be locked/unlocked.
- Lottery resolution is deterministic.
- AI and user trades value the same asset semantics.

## Alternatives

### Keep Raw Strings And Parse Them

Flexible for imported data, but ambiguous phrases and partial real-world terms make reliable parsing impossible. Strings should be evidence/input, not runtime authority.

### Remove Conditional Picks Entirely

Much simpler, but discards a strategically important NBA trade mechanism and user-requested depth.

### Approximate Swaps As Small Pick Bonuses

Easier valuation but no actual right transfer or resolution, producing fake depth.

## Consequences

Positive:

- coherent lifecycle;
- precise legality and labels;
- AI can use swaps/protections as real assets;
- repair/audit of startup terms.

Negative:

- many state transitions and edge cases;
- startup real-world terms may be incomplete and require deterministic gameplay fallbacks;
- save migration is more complex;
- exact NBA obligation chains can exceed v1 representation.

## Evidence

[transactions.py](../../../src/nba_gm_data/transactions.py) validates and applies terms; [save.py](../../../src/nba_gm_data/save.py) resolves obligations against lottery/draft order. Regression tests cover self-fallbacks, locks, labels, convey/protect outcomes, retrades, swaps, and ownership.

## Revisit When

- multi-year rolling protections or chained conversions exceed the current schema;
- a dedicated obligation state-machine module is extracted;
- authoritative startup data provides richer real-world terms.

## Related

- [[Systems/Pick Obligations and Swaps]]
- [[History/Failure Museum]]

