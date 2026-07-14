---
type: adr
status: accepted
decision: deterministic-seeded-simulation
reviewed: 2026-07-10
tags:
  - decision/determinism
  - gameplay/simulation
---

# ADR-002: Deterministic Seeded Simulation

## Context

Games, injuries, development, draft classes, lottery, AI choices, and market behavior need variation. The project also needs to reproduce a failure reported after minutes or seasons of simulation.

## Decision

Use deterministic pseudo-random generators seeded from save seed plus stable domain context such as game ID, mode, team, date, or class year. Interactive new saves may use fresh entropy when no seed is supplied; explicit seeds remain reproducible.

## Why

- A playtest failure can be replayed.
- Calibration comparisons can hold the scenario constant.
- Tests can assert exact transitions.
- Save outcomes remain stable across reopen/retry when inputs are unchanged.
- Different domains can isolate randomness so unrelated changes cause less global drift.

## Alternatives

### System Randomness Everywhere

Maximizes surprise but makes failures and tuning comparisons difficult to reproduce.

### One Global Random Stream

Reproducible but fragile: one additional draw in an unrelated feature changes every later outcome.

### Precompute Full Seasons

Fast later playback but invalid once the user changes rosters, rotations, staff, health, or morale.

### Cryptographic Randomness

Unnecessary for a private simulation and counterproductive for replay.

## Consequences

Positive:

- excellent debugability;
- stable regression tests;
- controlled multi-seed calibration;
- deterministic generated future content.

Negative:

- iteration ordering and IDs become part of behavior;
- accidental seed reuse can create unwanted correlation;
- changing a seed formula can alter old saves;
- reproducibility can be mistaken for lack of variety if every new save uses the same default seed.

## Evidence

`sim_game_with_context` seeds by stable game context. Draft generation, health, staff, and other systems accept seeds. Tests cover deterministic rebuilds, simulations, AI trades, generated classes, lotteries, and explicit-seed random-team selection.

## Revisit When

- cross-version exact replay is promised to users, requiring stored algorithm versions;
- concurrency changes result application order;
- a subsystem demonstrates correlated outcomes caused by poor seed partitioning.

## Related

- [[Architecture/Determinism and Identity]]
- [[Systems/Simulation Engine]]

