---
type: moc
status: current
tags:
  - map/architecture
  - project/nba-gm
---

# Architecture MOC

The architecture is best understood as a sequence of boundaries: evidence becomes canonical data, canonical data plus a save becomes the active world, ordered services mutate that save, and interfaces request actions without owning rules.

## System Shape

- [[Architecture/System Context]] - actors, runtime boundaries, and the full system diagram.
- [[Architecture/Module Map]] - what each large module owns and where coupling has accumulated.
- [[Architecture/Core Logic and Code]] - function-level entry points and request/state flows.
- [[Architecture/Canonical Universe and Save Overlay]] - the central state model.
- [[Architecture/Season State Machine]] - dates, phases, legal actions, advancement, and rollover.
- [[Architecture/Determinism and Identity]] - seeds, IDs, ordering, and reproducibility.
- [[Architecture/Action Boundary and Local GUI]] - CLI, GUI, action dispatcher, and server.
- [[Architecture/Persistence and Mutation Safety]] - save writes, locks, migration, derived caches, and transaction integrity.

## Defining Decisions

- [[Decisions/ADR-001 Canonical Base Plus Save Overlay]]
- [[Decisions/ADR-002 Deterministic Seeded Simulation]]
- [[Decisions/ADR-003 Python Engine Is Authoritative]]
- [[Decisions/ADR-004 Dependency-Light Standard Library Runtime]]
- [[Decisions/ADR-007 Sequential Advancement With Checkpoints]]

## Architecture Tensions

| Tension | Current answer | Cost |
|---|---|---|
| Reproducibility vs surprise | Seeded pseudo-random domains | Seed and ordering become API contracts |
| Rich mutable league vs stable source data | Canonical base plus save overlay | Enrichment and invalidation are complex |
| Multiple interfaces vs one rules engine | JSON action boundary | CLI still contains orchestration that must move inward |
| Speed vs behavior preservation | Cache repeated context first | Some long simulations remain slow |
| Friend-friendly install vs deep native packaging | Dependency-light Python and local web GUI | Standalone iOS is not yet shipped |

## Read Next

For implementation details, continue to [[Maps/Gameplay Systems MOC]]. For the arguments behind the boundaries, use [[Maps/Decisions MOC]]. For known structural risks, use [[Quality/Risk Register and Technical Debt]].
