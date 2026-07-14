---
type: adr
status: accepted
decision: python-engine-authoritative
reviewed: 2026-07-10
tags:
  - decision/architecture
  - python
  - gui
---

# ADR-003: Python Engine Is Authoritative

## Context

The detailed Python engine existed before the GUI. It contains tens of thousands of lines of calibrated game behavior and a large regression suite. The project now targets CLI, local macOS GUI, and eventually a standalone iPhone app.

## Decision

Keep basketball rules, state transitions, AI, simulation, and persistence authoritative in Python. Interfaces exchange JSON-compatible actions and view models. Do not reimplement rules in JavaScript, Swift, or another client language.

## Why

- One source of gameplay truth.
- Existing tests protect all clients.
- GUI work can change presentation without retuning the league.
- CLI remains a useful debugging and fallback interface.
- Future native shells can embed or call the same engine.

## Alternatives

### Rewrite The Engine In Swift For iOS

Could integrate natively and run efficiently, but would duplicate years of behavior, split tests, and likely produce platform divergence.

### Move Rules Into JavaScript/TypeScript

Could simplify a web GUI, but requires a complete port and weakens the existing Python data/science workflow.

### Host A Remote Python Backend

Keeps one engine but violates the standalone iPhone requirement, adds hosting/auth/cost, and makes offline friend testing harder.

### Rewrite Hotspots In Rust/C

This can coexist with the decision if Python remains the authoritative orchestrator and golden behavior is preserved. It is an optimization option, not an application rewrite.

## Consequences

Positive:

- no rule duplication;
- stable domain ownership;
- easier regression testing;
- local/offline possibilities.

Negative:

- iOS packaging is more difficult than a pure Swift app;
- Python object graphs and large JSON data may stress mobile memory/startup;
- UI workflows must be extracted from CLI prompts into application services;
- FFI/native packaging constrains dependencies.

## Evidence

[app_actions.py](../../../src/nba_gm_data/app_actions.py) is the platform-neutral action seam. The local browser GUI already uses it through [app_server.py](../../../src/nba_gm_data/app_server.py).

## Revisit When

- an iOS prototype proves embedded Python cannot meet startup/memory/runtime requirements;
- a small isolated hot kernel is profiled and stable enough for native implementation;
- a remote-service product becomes acceptable to users.

## Related

- [[Architecture/Action Boundary and Local GUI]]
- [[Product/CLI to GUI Evolution]]

