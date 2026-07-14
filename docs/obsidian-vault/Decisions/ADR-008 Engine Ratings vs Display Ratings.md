---
type: adr
status: accepted
decision: separate-engine-and-display-ratings
reviewed: 2026-07-10
tags:
  - decision/ratings
  - gameplay/calibration
---

# ADR-008: Engine Ratings Versus Display Ratings

## Context

The engine was calibrated around trait distributions whose elite overall values often appeared in the 70s. Users expect sports-game stars to appear in the 90s. Directly rescaling stored engine values would alter every simulation, valuation, threshold, and generated-player model.

## Decision

Preserve internal engine trait/composite values for all gameplay math. Translate them through a monotonic bounded display function for user-facing 1-99 ratings. Keep detailed/debug views able to expose raw values when needed.

## Why

- user intuition improves;
- top players visibly separate;
- standings and simulation calibration are not reset;
- one display convention can be used across dashboard, leaders, scouting, and trade inspection;
- internal precision and distribution remain available.

## Alternatives

### Rescale Every Engine Value

Would align storage and display but require retuning thousands of weights/thresholds and rebuilding generated-player distributions.

### Show Percentile Rank

Easy to understand competitively, but a percentile is not a skill magnitude and creates confusing screen-to-screen differences.

### Keep Raw Values And Explain Them

Technically honest but unnecessarily hostile to basic sports-game intuition.

## Consequences

Positive:

- familiar UX without behavior drift;
- stable engine;
- monotonic ranking.

Negative:

- two scales must be clearly named;
- developers can accidentally use display values in gameplay;
- tail transforms can make small raw differences look large;
- prospect/scouting and dashboard displays need intentional distinctions.

## Evidence

The trait browser and team dashboard now share display-scale helpers, while simulation/trade formulas consume raw engine values. Tests verify monotonic display order, elite 90s, and unchanged underlying values.

## Revisit When

- a versioned engine recalibration intentionally adopts a new native 1-99 scale;
- display compression creates user-visible ties or exaggerated differences;
- public modding requires one documented rating schema.

## Related

- [[Systems/Ratings and Traits]]
- [[Product/Dashboard Design]]

