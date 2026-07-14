---
type: quality
status: current
reviewed: 2026-07-10
tags:
  - quality/performance
  - architecture/optimization
  - project/nba-gm
---

# Performance And Optimization

## Performance Goal

Reduce waiting in month simulation, trade finder, rollover, draft advancement, and free-agency days without changing decisions, context, statistics, chronological causality, or deterministic outputs.

That last clause is the constraint. A faster answer that knows less about the league is not an optimization; it is a different game.

## Observed Hotspot Classes

### Repeated Canonical Enrichment

Deep-copying and reapplying save overlays is expensive. It should happen at intentional mutation boundaries, not once per candidate or card.

### Transaction Context Rebuilding

Trade search evaluates many packages. Recomputing team strategy, asset lookups, pick projections, and protection annotations for each candidate dominated work that did not change between candidates.

### Game Context Loading

Opening and indexing schedules, box scores, teams, players, coaches, and traits for every game repeats I/O and normalization.

### Long Lifecycle Operations

Season rollover, generated schedules, draft onboarding, awards, retirements, contracts, and roster minimums touch the whole league by design.

### GUI Overfetch/Rerender

Refreshing every dashboard card after a narrow preference change can waste backend and DOM work even if core simulation is not involved.

## Safe Optimizations Already Used

### Reusable Simulation Context

`sim_game_with_context` accepts preloaded indices and caches. A date-range advance builds context once and simulates games against it.

### Idempotent Transaction Context

`with_transaction_context` marks enriched canonical dictionaries and computes a signature from season, records, pick owner/status/protection state, and relevant save inputs. Unchanged calls reuse annotations; changed records/season/ownership invalidate them.

### Prebuilt Lookups

Player/team/trait/contract/asset maps turn repeated linear scans into dictionary access inside hot loops.

### Lazy Narrative

Ollama is never invoked during day/month simulation. Visible posts generate on demand and cache by context.

### Precomputed Loading Frames

ffmpeg work occurs during cache preparation, not every loading screen.

## Optimization Order

1. Measure per-operation and per-test wall time.
2. Profile CPU and count repeated expensive function calls.
3. Remove duplicate I/O and normalization.
4. Build immutable indices once per unchanged context.
5. Cache pure/derived values with complete invalidation signatures.
6. Batch writes and UI refreshes where causally safe.
7. Optimize algorithms/data structures.
8. Only then consider concurrency or native-language kernels.

## Why Same-Day Parallel Simulation Was Deferred

Games between distinct teams on one date appear independent, but the current simulation path reads and writes shared save collections, health/fatigue states, game logs, season totals, context caches, and event queues. Safe parallelism would require:

1. an immutable start-of-day snapshot;
2. pure game jobs that return results without mutating shared state;
3. separate deterministic seeds independent of process order;
4. serialized result application in stable order;
5. proof that no same-day event affects another game;
6. process rather than thread parallelism for CPU-bound Python work, plus serialization cost.

This is possible, but it is an architectural project, not a loop annotation. The current safer win is context reuse.

## Why Speculative Preloading Was Deferred

The CLI and GUI allow many actions that invalidate future simulations: trades, signings, cuts, rotations, morale, health, staff, and development. Preloading a probable next month risks stale state, consumes CPU while the user is inspecting, and requires cancellation/versioning. It becomes attractive only after action state has immutable snapshots and cheap invalidation.

## Native Language Rewrite

Rust/C/C++ could accelerate numerical kernels, but the project first needs evidence that pure numeric loops, not repeated Python-level orchestration and I/O, dominate runtime. Rewriting domain logic creates dual-language debugging, packaging, FFI, and iOS binary complexity.

A justified native candidate would be:

- pure and isolated;
- called many times;
- profiled as CPU dominant;
- covered by golden behavior tests;
- able to exchange compact arrays/structures;
- stable enough not to change weekly.

The current simulation and transaction rules are still evolving, so a rewrite is premature.

## Performance Benchmark Matrix

Capture median and tail times for fixed seeds/state:

| Operation | Scenario |
|---|---|
| Open dashboard | cold and warm save |
| Trade finder | one player, two assets, protected pick |
| Advance day | games and no games |
| Sim week/month | early, pre-deadline, injury-heavy |
| Draft pick | no trade and active trade market |
| Full draft | 60 picks |
| Free-agency day | high offer volume |
| Season rollover | complete realistic season |
| Full tests | per-test timing and total |

Record output hashes/invariants beside timings so an optimization cannot silently change behavior.

## Cache Rule

Every cache needs four documented properties:

1. key/signature;
2. cached value authority;
3. invalidation inputs;
4. test that proves both reuse and invalidation.

Without all four, a speedup becomes a stale-state bug.

## Related Decisions

- [[Decisions/ADR-007 Sequential Advancement With Checkpoints]]
- [[Decisions/ADR-004 Dependency-Light Standard Library Runtime]]

