---
type: roadmap
status: current
reviewed: 2026-07-10
tags:
  - roadmap/release
  - quality/checklist
  - project/nba-gm
---

# Release Readiness

## Private Friends Beta Gates

### Installation

- [ ] Clean Python 3.11+ install path verified.
- [ ] One command/launcher starts the GUI.
- [ ] Missing optional ffmpeg/Ollama produces clear nonblocking status.
- [ ] Loading asset archive installs with checksum/version verification.
- [ ] Team logos and required static assets are packaged.

### Saves

- [ ] Explicit schema version and migration tests.
- [ ] Atomic writes and automatic backup.
- [ ] Import/export from GUI.
- [ ] Corrupt save produces recovery guidance rather than stack trace.
- [ ] Save filename/team/random creation behavior is clear.

### Gameplay

- [ ] Create and play a new save through one full season and rollover.
- [ ] Trades, contracts, draft, free agency, staff, playoffs, health, and events pass smoke scripts.
- [ ] No blocker in every phase transition.
- [ ] AI activity distributions are reviewed over multiple seeds/seasons.
- [ ] No duplicate IDs, ghost stats, stale roster references, or owner mismatches in soak tests.

### GUI

- [ ] All core CLI actions have GUI parity or are clearly marked unavailable.
- [ ] Back/Cancel never mutates.
- [ ] Disabled actions explain why.
- [ ] No overlap/overflow at supported Mac viewports and zoom levels.
- [ ] Keyboard and basic screen-reader semantics checked.
- [ ] Loading/progress and error states are present for long actions.

### Tests And Performance

- [ ] Full suite passes on clean checkout.
- [ ] Per-operation benchmark is recorded.
- [ ] No test is terminated solely for duration.
- [ ] Month, deadline, draft, free agency, and rollover wait times are acceptable on target friend hardware.

### Documentation

- [ ] README first-run path tested by someone who did not build the project.
- [ ] Rules/simplifications explain cap, trades, picks, ratings, and save phases.
- [ ] Known issues and diagnostics instructions are visible.
- [ ] This vault is reviewed against current code.

## Public Beta Additional Gates

- [ ] Asset and data licensing audit.
- [ ] Privacy/security review and no accidental remote server exposure.
- [ ] Release versioning/changelog/support policy.
- [ ] Reproducible signed/notarized macOS packaging.
- [ ] Crash diagnostics and consent policy.
- [ ] Accessibility and responsive design target.
- [ ] Upgrade compatibility across release versions.
- [ ] More focused documentation than a developer README.

## iPhone Gates

- [ ] Embedded Python prototype on physical device.
- [ ] App-sandbox save storage and document import/export.
- [ ] Startup, memory, thermals, battery, and long-sim measurements.
- [ ] Touch-first layouts rather than desktop dashboard shrinkage.
- [ ] Offline narrative strategy that does not assume desktop Ollama.
- [ ] TestFlight/signing workflow for friends.

## Known-Issue Standard

A known issue should include:

- user-visible symptom;
- affected phase/saves;
- workaround;
- data-loss risk;
- issue/test reference;
- whether a fix changes simulation behavior.

## Beta Feedback Package

Make it easy for a friend to send:

- app version/API version;
- save copy;
- current date/phase/team;
- last actions;
- logs/error message;
- screenshot;
- optional deterministic seed.

This turns “something weird happened” into a reproducible scenario.

## Related Notes

- [[Roadmap/Current State Assessment]]
- [[Quality/Security and Privacy Boundaries]]
- [[Quality/Testing Strategy]]

