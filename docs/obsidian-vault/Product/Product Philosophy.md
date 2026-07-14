---
type: product
status: current
reviewed: 2026-07-10
tags:
  - product/philosophy
  - project/nba-gm
---

# Product Philosophy

## Core Fantasy

The player should feel like the general manager of one franchise inside a league that continues to make consequential decisions without waiting for permission. The league should be legible enough to understand, surprising enough to feel alive, and consistent enough that planning matters.

## Product Pillars

### Basketball-Literate Decisions

Choices should depend on more than overall ratings. Position, role, fit, timeline, depth, contract, health, picks, coaching, and future opportunity matter. A good move should be explainable in basketball language.

### Persistent League Causality

Games affect standings; standings affect team strategy; strategy affects trades and staff security; transactions affect rotations and cap; health affects games and value; draft ownership affects future plans. The user is not navigating disconnected mini-games.

### Explainable AI

AI evaluations include reasons, value components, fit, legality, and thresholds. The goal is not to expose every coefficient, but to let users learn why a team reacted.

### User Agency With Guardrails

The user can make unconventional legal choices, including cutting or trading strong players. The engine should model consequences rather than silently prevent all bad ideas. It must still enforce league legality and explicit confirmation.

### Information Density Without Mystery

A management dashboard can be dense because repeated comparison is the work. Dense does not mean cramped or unexplained. Tables should align comparable fields, color should communicate rating/risk, and controls should sit next to the state they change.

### The League Feels Alive

AI-AI trades, extensions, staff drama, injuries, draft movement, free-agent choices, league events, and social commentary make the world independent of the user. Narrative enhances those facts but cannot replace the systems that create them.

## Intended Audience

- The creator and basketball-literate friends during private alpha/beta.
- Players willing to learn a deep franchise simulation.
- Eventually, users who prefer a GUI and may not be comfortable with terminal setup.

The game should remain usable without optional ffmpeg or Ollama. Rich extras cannot become hard dependencies for core play.

## Realism Means Coherence, Not Exact Replay

The initial universe is informed by real-world data, but once a save begins it becomes its own timeline. Realism means decisions and outcomes make sense under the simulated state, not that future events recreate real NBA history.

This distinction is especially important for [[Systems/Narrative Engine]]: a local model's memorized player reputation or team affiliation is invalid unless the current save packet supports it.

## Product Tradeoffs

| Goal | Chosen tradeoff |
|---|---|
| Deep league behavior | Longer simulations and more state complexity |
| Explainable decisions | More verbose view models and tests |
| Real player foundation | Ongoing data provenance and update burden |
| Multi-season play | Generated future data and rollover complexity |
| Local/private narrative | Model installation and validation overhead |
| GUI accessibility | Significant action extraction and layout work |

## What The Product Should Avoid

- Fake depth: lots of displayed numbers that do not affect decisions.
- Hidden contradictions: one screen says a pick/player belongs somewhere another does not.
- Artificial activity quotas that force nonsensical trades or extensions.
- Narrative that sounds informed but uses facts outside the save.
- Marketing screens before a usable management workspace.
- Replacing engine complexity with superficial speed shortcuts.

## Related Notes

- [[Systems/Transactions and Asset Valuation]]
- [[Product/Dashboard Design]]
- [[Roadmap/Release Readiness]]

