---
type: data
status: current
reviewed: 2026-07-10
tags:
  - data/schema
  - architecture/domain
  - project/nba-gm
---

# Domain Schema

## Role Of `schema.py`

[schema.py](../../../src/nba_gm_data/schema.py) defines frozen dataclasses for canonical records and a `CanonicalUniverse` aggregate. The records document the vocabulary shared across ingestion, simulation, transaction, draft, health, staff, validation, and storage code.

Representative concepts include:

- source evidence and coverage issues;
- team and player identity;
- player traits and composite context;
- roster assignments and contracts;
- draft picks, prospects, scouting reports, boards, rights, and selections;
- gameplay staff and effects;
- health profiles, states, and injury/development events;
- front-office and strategic profiles;
- trade proposals, assets, evaluations, and legality;
- contract offers and negotiation results;
- simulation results and validation reports.

## Why Frozen Dataclasses?

Frozen dataclasses provide:

- explicit named fields;
- readable constructor/type signatures;
- value-like semantics;
- resistance to accidental baseline mutation;
- standard-library implementation with no runtime dependency;
- easy conversion to plain JSON-compatible dictionaries through `to_plain`.

Python's official dataclass documentation is at [dataclasses](https://docs.python.org/3/library/dataclasses.html).

## Schema Versus Save Shape

The canonical schema is much more explicit than the save schema. Save files are evolving nested dictionaries with opportunistic defaults and migrations. That mismatch made rapid iteration easy, but it is a long-term risk.

A useful future direction is typed save submodels or validation schemas for high-risk domains:

- pick obligations;
- draft state;
- playoff state;
- contract overrides;
- roster/starting lineup state;
- narrative cache.

This does not require adopting a third-party library immediately; `TypedDict`, dataclasses, or explicit validators could improve contracts incrementally.

## Identity Over Labels

Schema design should prefer stable IDs for joins and labels only for display. Repeated bugs around pick ownership and similarly named/current-year picks reinforce this. See [[Architecture/Determinism and Identity]].

## Serialization

`to_plain` recursively converts dataclasses and nested collections to JSON-compatible values. This keeps the canonical build typed internally while allowing simple JSON and SQLite export.

The boundary is lossy in one sense: a plain dictionary no longer enforces frozen type contracts. Runtime services must validate assumptions or use constructors/helpers rather than blindly accepting arbitrary nested state.

## Schema Evolution Principles

1. Add fields with explicit defaults or migration behavior.
2. Keep identity stable across renamed display fields.
3. Separate source fact from inferred/tuned values.
4. Version behavioral configuration independently from record shape.
5. Test serialization round trips for high-risk records.
6. Avoid storing the same fact authoritatively in multiple collections.

## Questions For Every New Record

- Is this canonical baseline, mutable save state, derived view, or audit event?
- What owns its ID?
- Can it be regenerated?
- What invalidates it?
- Does it need provenance?
- How does an old save get the new field?

## Related Notes

- [[Architecture/Canonical Universe and Save Overlay]]
- [[Data/Canonical Build Pipeline]]
- [[Architecture/Persistence and Mutation Safety]]

