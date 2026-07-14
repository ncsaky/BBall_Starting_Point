---
type: system
status: current
reviewed: 2026-07-10
tags:
  - system/staff
  - gameplay/ai
  - project/nba-gm
---

# Staff AI

## Staff Model

Each team has six fictional gameplay staff slots:

1. Head Coach
2. Offensive Coordinator
3. Defensive Coordinator
4. Development Lead
5. Performance Lead
6. Scouting Lead

Real-world public coaching sources help seed context, but fictionalized staff create a sustainable multi-season market and avoid pretending the project has complete real-world data for every specialized role.

## Effects

Staff grades summarize role-specific traits rather than acting as one universal multiplier.

- Head coach: rotation, team context, development, reputation, broad strategy.
- Offensive coordinator: offensive quality and fit.
- Defensive coordinator: defense and scheme support.
- Development lead: monthly player growth quality/focus.
- Performance lead: fatigue, prevention, recovery, rust.
- Scouting lead: draft-board information quality and uncertainty.

The UI should display role-specific effect rows so a user understands why two similarly graded staff members differ.

## Market And Budget

[staff.py](../../../src/nba_gm_data/staff.py) creates candidates, asks, contracts, negotiations, hires, firings, interims, and team reports. Every AI and user hire must stay within the team's staff budget. A team cannot immediately rehire the exact staff member it just fired through the same automatic path.

## AI Retention

When contracts expire, AI teams should attempt to retain strong staff when:

- performance is acceptable;
- the ask fits the budget;
- the role is important and replacement quality is uncertain;
- no major strategic reason demands change.

Staggered contracts and retention prevent an unrealistic wave of every elite staff member entering the market in the same offseason.

## Firings

Firing behavior has different cadence and evidence by role.

### Head Coach

Can be fired in-season during a severe skid/free fall or after a disappointing year. Better coaches receive more job security. Injury burden reduces blame. A good long-tenured coach can become a scapegoat after repeated underperformance. A clearly superior available replacement can increase pressure.

The target product feel is roughly 4-6 head coach changes in a typical season, split between in-season and offseason, with controlled variation rather than a hard quota.

### Coordinators

Offensive or defensive coordinators can be blamed when their side of the ball is the obvious weak link. In extreme cases a bad team can overhaul multiple coaching roles, but one firing per team/slot/season prevents churn loops.

### Support Staff

- Development lead: poor cumulative growth relative to expected age/minutes context.
- Scouting lead: weak draft returns relative to available board alternatives.
- Performance lead: excessive team injury burden after accounting for player risk.

These signals create a plausible route for non-coaching staff to enter the market.

## Interims

A fired role can receive an interim replacement. Interims must have a future review date; otherwise a temporary state silently becomes permanent. AI can hire a market replacement immediately or retain the interim briefly depending on timing and candidate quality.

## Public Events

Notable head coach firings should always surface with a concise factual reason such as a skid or missed expectation. High-grade hires/fires and significant coordinator moves can enter league events. Routine support-staff changes should not force press conferences.

Press conferences are currently disabled by default for smoother testing, and non-head-coach staff moves should not create forced conferences even when the feature returns.

## Invariants

- A team has at most one active staff member per slot.
- Every hire is within budget.
- A slot cannot be fired more than once per season without an explicit lifecycle reason.
- Interim roles are revisited.
- Staff events are deduplicated across transaction log, news, and league event presentation.
- Injury-heavy underperformance does not receive the same coach-blame probability as healthy underperformance.

## Source Anchors

- [Staff system](../../../src/nba_gm_data/staff.py)
- [Staff overrides](../../../data/overrides/staff_overrides.json)
- [Gameplay staff seed](../../../data/overrides/gameplay_staff_seed.json)

## Related Notes

- [[Systems/Health Fatigue and Development]]
- [[Systems/Draft Lottery and Scouting]]
- [[Systems/League Events Morale and Social]]
