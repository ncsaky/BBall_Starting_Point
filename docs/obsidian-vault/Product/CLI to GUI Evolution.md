---
type: product
status: current
reviewed: 2026-07-10
tags:
  - product/history
  - cli
  - gui
  - project/nba-gm
---

# CLI To GUI Evolution

## Why The CLI Came First

The project began as a data and simulation foundation. A numbered terminal interface made it possible to exercise new domain flows immediately without first building a component system. That enabled rapid development of:

- save creation and advancement;
- dashboards and inspection views;
- trade builder/finder;
- contract and staff negotiation;
- draft, lottery, free agency, playoffs, and rollover;
- social, events, morale, loading animation, and settings.

The CLI became a living product specification. It reveals exactly what information and decisions each workflow requires.

## What The CLI Does Well

- Complete linear workflows with explicit prompts.
- Easy debug output and deterministic reproduction.
- Low dependency and packaging burden.
- Natural support for long text explanations.
- Broadest feature parity at this snapshot.

## What The CLI Does Poorly

- Repeated navigation between related information.
- Comparing many players/contracts/picks at once.
- Editing sliders, filters, lineups, and multi-asset trades.
- Discoverability for nontechnical friends.
- Visualizing brackets, development, standings trends, and cap structure.
- Keeping context on screen during a negotiation.

## GUI Goal

The GUI should put a visual shell over the same engine, not become a second game implementation. It can consolidate information naturally:

- player ratings, stats, minutes, and contracts in one table;
- standings, calendar, development, league events, staff, and free agents in connected cards;
- modal trade inspection and asset selection;
- clickable team navigation;
- dropdown filters and sliders instead of numbered prompts;
- bracket visualization rather than series text.

## The Application-Service Gap

Some CLI flows still combine user prompting, validation, domain action, save writing, and output formatting in `play.py`. GUI work exposes this coupling. The correct migration is:

1. characterize the CLI behavior with tests;
2. extract a structured action into `app_actions.py` or a domain service;
3. make both CLI and GUI call the action;
4. render their own presentation;
5. delete duplicated orchestration only after parity.

## Current GUI Reality

The implemented GUI uses vanilla JavaScript and CSS, not React. It is served locally by Python and calls JSON actions. Rapid visual iteration has produced a sophisticated dense dashboard, but also layout debt and some feature gaps. See [[Product/Dashboard Design]].

## Press Conferences

Forced press conferences are temporarily disabled by default because they slow repeated testing. This is a feature flag, not a deletion. The GUI should eventually reintroduce them as a deliberate modal mini-game when narrative quality and pacing justify it.

## Standalone Apple Direction

The proposed end state is a standalone macOS and iPhone app with embedded Python, preserving the engine. That requires a platform-neutral action layer, app-storage APIs, save import/export, and packaging validation. It does not exist merely because the local web GUI exists.

## Parity Definition

A GUI room is complete only if it supports:

- all legal entry conditions;
- every required intermediate choice;
- back/cancel without mutation;
- validation and explanatory errors;
- apply/confirm exactly once;
- save persistence;
- refresh of every dependent view;
- keyboard/touch-accessible controls;
- tests against the same domain action as CLI.

## Related Notes

- [[Architecture/Action Boundary and Local GUI]]
- [[Roadmap/Next Development Phases]]
- [[Quality/Testing Strategy]]

