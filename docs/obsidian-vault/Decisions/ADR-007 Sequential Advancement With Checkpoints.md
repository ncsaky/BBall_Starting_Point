---
type: adr
status: accepted
decision: sequential-advancement-checkpoints
reviewed: 2026-07-10
tags:
  - decision/performance
  - architecture/time
---

# ADR-007: Sequential Advancement With Checkpoints

## Context

Month and season simulation can be slow. Same-day games appear parallelizable, and UI idle time could theoretically preload future results. However, rosters, injuries, fatigue, records, team needs, trades, staff changes, morale, and phase legality evolve chronologically.

## Decision

Keep league advancement sequential at explicit chronological checkpoints. Optimize repeated context, I/O, lookups, and pure calculations first. Do not introduce same-day parallel mutation or speculative save preloading until simulation jobs can run against immutable snapshots and apply results deterministically.

## Why

- preserves causal league behavior;
- avoids shared-save races;
- keeps seeded ordering reproducible;
- makes intermediate AI trades/staff actions occur on realistic dates;
- focuses optimization on measured duplicate work.

## Alternatives

### Thread Every Same-Day Game

Python threads may not speed CPU-bound work because of the GIL, while shared state writes and caches create race risks.

### Process Pool For Games

Can use multiple cores, but requires serializing large snapshots and making each game pure. It remains a future option after refactoring.

### Sim Directly To Target Then Apply Events

Fast but causally wrong: deadline team needs and standings would ignore earlier trades/injuries.

### Speculative Preloading

Potentially improves perceived latency but requires robust invalidation for every user action and wastes work when the user changes state.

## Consequences

Positive:

- behavior preservation;
- deterministic debugging;
- simpler save integrity;
- chronological AI activity.

Negative:

- long operations remain visibly slow;
- one core cannot exploit independent game computation yet;
- UI needs loading/progress feedback.

## Evidence

`advance_save` processes health, games, development, phase changes, restrictions, AI actions, and events in order. A historical bug where AI trades piled up until the deadline demonstrated why hidden checkpoints matter. Context caches have already produced lower-risk wins.

## Revisit When

- profiling shows pure per-game CPU dominates after context reuse;
- game simulation is refactored into immutable input -> result;
- deterministic result-application order is tested;
- snapshot serialization overhead is measured below the expected gain.

## Related

- [[Architecture/Season State Machine]]
- [[Quality/Performance and Optimization]]

