---
type: roadmap
status: proposed
reviewed: 2026-07-10
tags:
  - roadmap/future
  - project/nba-gm
---

# Next Development Phases

The safest roadmap finishes foundations before adding more surface area. Each phase has an exit condition.

## Phase 1: Freeze And Measure A Known-Good Engine

### Work

- Create benchmark saves for preseason, deadline, playoffs, draft, free agency, and rollover.
- Add operation timing and output/invariant hashes.
- Split test fixtures from the giant test module without changing assertions.
- Add 5-season soak validation for IDs, rosters, cap, awards, picks, staff, and stale references.
- Record current calibration distributions as golden reports.

### Exit

Every high-value flow has a reproducible fixture, baseline timing, and invariant report.

## Phase 2: Harden Save Integrity

### Work

- Add explicit save schema version.
- Implement ordered idempotent migrations.
- Write saves through temp file + flush + atomic rename.
- Keep rolling backups and provide recovery/validation command.
- Validate high-risk subdocuments: roster ownership, contracts, pick obligations, draft/playoff state.

### Exit

Killing the process during a test save write cannot destroy the last valid save, and real old saves migrate through tested fixtures.

## Phase 3: Complete The Application Action Layer

### Work

- Inventory every CLI workflow and GUI action.
- Extract domain/application services from terminal prompts.
- Define action request/response schemas and error codes.
- Add API/build compatibility version to GUI bootstrap.
- Make CLI call shared actions where practical.

### Exit

The parity matrix shows every core workflow runs through a structured service with no UI-owned game rules.

## Phase 4: Stabilize The GUI System

### Work

- Refactor dashboard into CSS Grid named areas and reusable card primitives.
- Remove structural negative margins and one-off absolute offsets.
- Add browser workflow tests and screenshot baselines.
- Add keyboard, focus, reduced-motion, zoom, contrast, and responsive testing.
- Complete modals for trades, players, prospects, standings, draft, playoffs, free agency, and settings.

### Exit

No overlap at agreed viewports, every legal action is reachable, cancel is mutation-free, and visual regression runs automatically.

## Phase 5: Performance Pass

### Work

- Profile the benchmark matrix.
- Reduce redundant canonical enrichment and JSON reads.
- Cache immutable indices with complete signatures.
- Batch save writes and dashboard refreshes.
- Improve algorithms in trade candidate generation and view projections.
- Prototype pure start-of-day game jobs only if game CPU remains dominant.

### Exit

Target operations have documented before/after timings with identical output/invariants. No sophistication is removed.

## Phase 6: Friends Beta Packaging

### Work

- Create a reproducible macOS package/launcher.
- Add first-run canonical/load-assets/Ollama detection.
- Add save import/export and diagnostics bundle.
- Test clean installation on multiple Macs and user accounts.
- Update README and in-app onboarding.

### Exit

A nontechnical friend can install, create/load a save, play through one season, export a save, and recover from optional-feature absence without developer intervention.

## Phase 7: Standalone iPhone Feasibility Spike

### Work

- Build the smallest embedded-CPython iOS app.
- Load canonical data from app bundle.
- Create, advance, save, close, and reload one league.
- Measure startup, memory, month simulation, rollover, and app-size limits.
- Decide UI shell strategy and how narrative works without desktop Ollama.

### Exit

A simulator and physical-device prototype proves or disproves embedded Python under actual constraints. Only then commit to a full iPhone client.

## Phase 8: Deeper Basketball Fidelity

After foundations stabilize:

- staged CBA/right/exception improvements;
- lineup and matchup depth;
- richer strategic team histories;
- better long-term generated-player calibration;
- trade-demand and extension narratives tied to multi-season context;
- restored press-conference mini-game;
- modding/configuration documentation.

## Explicit Non-Goals For The Immediate Pass

- Rewrite the whole engine in Rust/Swift.
- Add remote multiplayer/hosted accounts.
- Replace every standard-library choice for fashion.
- Add more UI cards before existing workflows are complete.
- Parallelize mutable simulation without immutable job boundaries.

## Related Notes

- [[Quality/Performance and Optimization]]
- [[Roadmap/Release Readiness]]
- [[Architecture/Action Boundary and Local GUI]]

