---
type: learning
status: current
reviewed: 2026-07-10
tags:
  - learning/interview
  - project/nba-gm
---

# Interview Defense Guide

## The Two-Minute Story

> I built a deterministic multi-season NBA GM sandbox in Python. It started as a provenance-aware data foundation and evolved into a persistent league engine with game simulation, player traits, injuries and development, contextual trade AI, complex protected picks and swaps, contracts/free agency, staff, draft, playoffs, league events, and optional local-LLM narrative. The engine is exposed through a large CLI and a newer JSON action layer powering a local dashboard GUI. The hardest work has been preserving cross-system invariants over time, so I developed a 176-test regression foundation and turned playtest failures into lifecycle tests. I am now hardening save migrations, GUI parity/layout, performance, and native packaging.

Stop there unless asked to go deeper.

## Architecture Question: “Walk Me Through It”

Answer in four layers:

1. **Build-time data:** evidence + research cache + configuration + overrides -> frozen canonical universe.
2. **Runtime state:** mutable save overlay -> save-aware active canonical view.
3. **Domain services:** simulation, health, transactions, contracts, draft, staff, narrative, coordinated by season lifecycle.
4. **Interfaces:** CLI and JSON-driven local GUI; Python remains authoritative.

Draw [[Architecture/System Context]] if a whiteboard is available.

## Hardest Technical Problem

A strong answer is protected picks or season advancement, not “the CSS was hard.”

### Example: Protected Picks

**Situation:** Imported labels and early trade terms represented conditional picks as prose.

**Task:** Make protections tradeable, valuable, legally locked, retradeable, and correctly resolved after the lottery.

**Action:** Introduced structured obligations with exact primary/fallback IDs, rights holder, protection, status/history; added shared validation/labels; resolved against saved lottery order; locked fallback collateral; wrote lifecycle regression tests.

**Result:** Display and gameplay use one authority, and failures such as self-fallbacks or owner mismatches are testable invariants.

Then candidly state that the module should eventually be extracted into a dedicated state machine.

## Performance Question

Do not say “I would rewrite it in Rust.” Say:

1. established operation and per-test timing;
2. identified repeated transaction-context and canonical enrichment;
3. added reusable simulation context and signature-based transaction cache;
4. preserved output and invalidated on records/season/ownership changes;
5. deferred same-day parallelism until pure immutable game jobs exist.

This demonstrates measurement, risk control, and understanding of causality. See [[Quality/Performance and Optimization]].

## AI/LLM Question

Emphasize separation of concerns:

- deterministic engine creates facts;
- compact save-only packet grounds the model;
- provider returns strict JSON;
- semantic validators reject unsupported names, teams, contract math, cap claims, rank confusion, and trade direction;
- output is cached;
- fallback preserves play;
- simulation never waits for model calls;
- model never chooses game effects.

This is stronger than “I added ChatGPT.”

## Testing Question

Explain the difference among:

- pure formula tests;
- deterministic domain scenarios;
- save lifecycle integration;
- action API parity;
- missing browser visual and multi-season soak layers.

Give one failure-to-test example from [[History/Failure Museum]].

## Data Question

Explain that raw sources are evidence, not truth. The build normalizes identities, infers traits, quantile-maps a human prior into engine distributions, applies manual overrides last, emits coverage audits, and keeps health separate from full-health ratings.

Be ready to define quantile mapping and why aggregate standings can hide player-level rating errors.

## Tradeoff Questions

### “Why Python?”

Fast domain iteration, data handling, deterministic tests, and existing engine investment. Costs: CPU and mobile packaging. Optimize measured hotspots or isolate native kernels before considering a rewrite.

### “Why No Framework?”

Dependency-light setup and Apple packaging direction made standard libraries attractive early. Costs now include custom routing/validation and large vanilla frontend files. A framework may be justified as maintenance evidence grows.

### “Why JSON Saves?”

Transparent, portable, easy to debug during rapid schema discovery. Costs: atomicity, migrations, query performance. Next work is versioned migrations and atomic writes; SQLite remains an option.

### “Why Deterministic?”

Reproducibility and calibration, with fresh entropy only when a user requests an unseeded new save.

## Be Honest About Incompleteness

Good phrasing:

- “The GUI is functional and visually rich, but not at full CLI parity.”
- “The cap model is a documented v1 approximation, not every CBA exception.”
- “Standalone iPhone is an architecture direction awaiting a physical-device feasibility spike.”
- “The test suite is broad but currently monolithic and slow.”
- “The local server is appropriate for loopback use, not public hosting.”

Honesty under pressure signals ownership more than inflated claims.

## Demonstration Script

In 8-10 minutes:

1. Open the dashboard and explain canonical + save state.
2. Inspect player ratings/stats/contracts and team trends.
3. Run a trade finder offer and show contextual value/legal reasons.
4. Open a protected pick label and explain its lifecycle.
5. Advance a week/month and show deterministic updates.
6. Open one grounded social post and explain validation/fallback.
7. Show one relevant regression test.
8. End with current roadmap and one measured performance result.

Do not attempt a season rollover live unless pre-benchmarked.

## Likely Follow-Ups

### “What would you redesign?”

- explicit save schema/migrations;
- extracted application services;
- dedicated pick-obligation module;
- test fixtures split by domain;
- CSS Grid/card primitive refactor;
- benchmark/soak harness.

### “How do you know the sim is realistic?”

Answer at multiple levels: standings, scoring environment, stat/award distributions, archetype leaders, team feature sanity, and multi-seed tails. Admit that realism is iterative and subjective thresholds are documented.

### “What did you learn?”

The deepest lesson: complex software fails where one fact has multiple representations. Naming authority, invalidation, and lifecycle tests matters more than adding another local patch.

## Resume-Ready Bullets

- Built a 50K+ line deterministic NBA franchise simulation spanning game outcomes, transactions, contracts, draft rights, health/development, staff, playoffs, narrative, and multi-season persistence.
- Designed a provenance-aware canonical data pipeline and save-overlay architecture for 30 teams, 500+ players, 7,800+ traits, and generated future league content.
- Developed contextual AI trade/contract/draft decision systems with explainable legality, fit, value, and strategy components, including structured protected picks and retradeable swap rights.
- Integrated optional local Ollama narrative through save-only context packets, strict JSON, semantic validation, deterministic caching, and no-provider fallback.
- Converted extensive playtesting into a 176-test regression foundation and optimized repeated transaction/simulation context without changing behavior.

Adjust numbers after running the current line/test counters before using them externally.

