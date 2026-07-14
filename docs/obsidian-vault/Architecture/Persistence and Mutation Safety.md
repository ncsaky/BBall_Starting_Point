---
type: architecture
status: current
reviewed: 2026-07-10
tags:
  - architecture/persistence
  - architecture/state
  - project/nba-gm
---

# Persistence And Mutation Safety

## Persistence Model

Canonical output can be written as JSON and SQLite through [storage.py](../../../src/nba_gm_data/storage.py). Active gameplay saves are JSON documents managed primarily through [save.py](../../../src/nba_gm_data/save.py).

JSON was a practical choice for a private evolving project:

- easy to inspect and edit;
- easy to attach to bug reports;
- no database service;
- natural fit for nested phase state and generated entities;
- portable between CLI and GUI.

Its costs include large rewrites, limited transactional guarantees, schema drift, and awkward cross-entity querying.

## Mutation Classes

### Local Field Mutation

Examples: narrative setting, selected team, or a UI preference. Low blast radius, but still should be validated and persisted atomically.

### Domain Transaction

Examples: trade, signing, staff hire, cut, draft selection. These touch multiple collections and must either complete coherently or not apply.

### Temporal Advancement

`advance_save` changes many systems in chronological order and is effectively a batch transaction. It requires checkpoints and idempotency guards because a retry must not duplicate games or events.

### Season Rollover

The largest mutation class. It archives and resets state across almost every domain.

## Derived State And Invalidation

The project intentionally caches expensive derived context, including simulation feature vectors and transaction/pick projections. A cache is safe only if its signature includes every input that can change its answer.

Examples of invalidation inputs:

- active season and date;
- team records and standings;
- roster and contract ownership;
- pick owner, protection, and resolution state;
- player traits, health, and development;
- generated players and staff overrides.

The transaction context now uses signatures to avoid rebuilding identical pick annotations during large AI searches. See [[Quality/Performance and Optimization]].

## Roster Mutation Checklist

Whenever a player changes team or leaves the league:

1. update roster overrides;
2. update contract ownership/state;
3. prune rotation recommendations;
4. prune or temporarily substitute the starting five;
5. remove stale trade offers involving the asset;
6. prevent old-team box-score participation;
7. update free-agent or retirement collections;
8. invalidate team features and transaction context;
9. emit one factual transaction/event record;
10. persist before the UI reports success.

Historical bugs around ghost stats and stale lineups demonstrate why this checklist matters. See [[History/Failure Museum]].

## Pick Mutation Checklist

1. identify the exact `pick_id`;
2. validate that it exists and is currently controlled by the sender;
3. verify it is not locked fallback collateral or already selected;
4. update owner exactly once;
5. transfer any tradeable rights attached to it according to obligation type;
6. refresh live lottery/draft state;
7. clear stale value annotations and rebuild context;
8. ensure labels reflect the same structured obligation used by resolution.

## Write Safety

Per-save locks in [[Architecture/Action Boundary and Local GUI]] prevent overlapping in-process GUI writes. For a broader release, add atomic temp-file-and-rename saves, backups, explicit schema versions, and corruption recovery. A local process crash during a direct JSON rewrite should not be able to destroy the only save.

## Alternatives

- **SQLite runtime:** stronger transactions and queries, but requires migrations and more mapping code.
- **Append-only event log:** excellent history and replay, but every state change needs a complete event schema.
- **Document database:** preserves nested documents but adds a service/runtime dependency without solving all invariant problems.

The right next step is not necessarily a storage rewrite. First isolate domain transactions and add explicit save validation; then measure whether JSON remains the limiting factor.

## Related Notes

- [[Architecture/Canonical Universe and Save Overlay]]
- [[Architecture/Season State Machine]]
- [[Quality/Risk Register and Technical Debt]]
- [[Decisions/ADR-001 Canonical Base Plus Save Overlay]]

