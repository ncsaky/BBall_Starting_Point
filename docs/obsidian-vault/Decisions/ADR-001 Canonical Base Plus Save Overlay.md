---
type: adr
status: accepted
decision: canonical-base-plus-save-overlay
reviewed: 2026-07-10
tags:
  - decision/state
  - architecture/canonical
---

# ADR-001: Canonical Base Plus Save Overlay

## Context

The project needs a reproducible real-player baseline and many independent multi-season saves. Public data corrections should reach an old save when that save has not explicitly changed the field, while trades, generated rookies, development, injuries, contracts, and staff changes must remain save-specific.

## Decision

Build a mostly immutable `CanonicalUniverse`, then store mutable gameplay state as a league-save overlay. Construct a disposable save-aware canonical view when domain services need the active world.

## Why

- Independent saves cannot contaminate one another.
- Canonical data can be rebuilt and audited separately.
- Old saves can inherit new baseline corrections where no explicit save override exists.
- Generated entities can be added without rewriting baseline files.
- Bugs can be reproduced from canonical version + save + seed.

## Alternatives

### Full Universe Snapshot Per Save

Simpler reads, but large files, heavier migrations, duplicated data, and no natural path for baseline corrections.

### Directly Mutate A Global Canonical Dictionary

Initially easy, but process order and multiple saves become unsafe, and tests leak state.

### Event-Sourced League

Excellent audit/replay properties, but every state transition would need complete immutable events and deterministic replay from genesis. This was too much infrastructure for the project's stage.

### Relational Database As Sole Runtime State

Better transactions and queries, but greater schema/migration and mapping burden during rapid domain discovery.

## Consequences

Positive:

- clear baseline/save truth distinction;
- reproducibility;
- compact conceptual save diffs;
- compatible with CLI, GUI, and future clients.

Negative:

- save-aware enrichment can be expensive;
- precedence and merge semantics must be explicit;
- derived caches require careful invalidation;
- nested save dictionaries are less typed than canonical records.

## Evidence

[canonical_with_save](../../../src/nba_gm_data/save.py) applies generated players, ages, rosters, picks, contracts, staff, health, development, and rotations to a copied canonical dictionary. Tests cover idempotent effective age, current contract preservation, generated rookies, ownership, and save-backed views.

## Revisit When

- save files or enrichment dominate measured latency after safe caching;
- public release demands robust schema migration and transactional writes;
- event audit/replay becomes a product requirement;
- multiple concurrent users/processes need shared state.

## Related

- [[Architecture/Canonical Universe and Save Overlay]]
- [[Architecture/Persistence and Mutation Safety]]

