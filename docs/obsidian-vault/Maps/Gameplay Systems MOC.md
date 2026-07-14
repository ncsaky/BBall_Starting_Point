---
type: moc
status: current
tags:
  - map/gameplay
  - project/nba-gm
---

# Gameplay Systems MOC

Every gameplay system reads the same active league but owns a different kind of decision. The hard engineering problem is not any isolated formula. It is preserving consistency when these systems compose across days and seasons.

## Competitive World

- [[Systems/Simulation Engine]] - possessions, team and player features, minutes, outcomes, and box scores.
- [[Systems/Ratings and Traits]] - engine traits, composites, display scale, and calibration.
- [[Systems/Health Fatigue and Development]] - availability, injuries, fatigue, rust, growth, and regression.
- [[Systems/Playoffs Awards and Rollover]] - postseason state, awards, history, retirement, and next-season setup.

## Front Office World

- [[Systems/Transactions and Asset Valuation]] - players, picks, package context, legality, and AI acceptance.
- [[Systems/Pick Obligations and Swaps]] - protections, fallback collateral, swap rights, labels, and resolution.
- [[Systems/Contracts and Free Agency]] - asks, extensions, cap checks, market behavior, and AI signings.
- [[Systems/Draft Lottery and Scouting]] - draft classes, scouting fog, lottery, pick values, and draft-night trading.
- [[Systems/Staff AI]] - six staff roles, budgets, effects, hiring, firing, and interims.

## Lived League

- [[Systems/Narrative Engine]] - optional local LLM, sandbox packets, validation, cache, and fallback.
- [[Systems/League Events Morale and Social]] - factual event source, visibility, morale, and public presentation.
- [[Systems/Loading Animation]] - video-to-ASCII preprocessing and terminal loading experience.

## Cross-System Contracts

- Player identity must survive roster, contract, health, stats, trade, and narrative views. See [[Architecture/Determinism and Identity]].
- Pick identity must remain one exact asset from lottery through draft and any obligation. See [[Systems/Pick Obligations and Swaps]].
- A roster mutation must invalidate derived rotation, starting lineup, transaction, and simulation context. See [[Architecture/Persistence and Mutation Safety]].
- Narrative may restate facts but never create them. See [[Decisions/ADR-006 Optional Sandboxed Local LLM]].

