---
type: learning
status: current
reviewed: 2026-07-10
tags:
  - learning/glossary
  - project/nba-gm
---

# Glossary

## Architecture And Data

**Action boundary** - JSON-compatible application service between interfaces and domain logic, centered in `app_actions.py`.

**Authority / source of truth** - The one state representation whose value other views derive from.

**Canonical universe** - Reproducible baseline league built from evidence, inference, configuration, and overrides.

**Coverage issue** - Explicit record of missing, uncertain, or inconsistent source data.

**Derived state** - Data computed from authoritative state, such as pick projections, team feature vectors, or a display label.

**Enrichment** - Applying a save's mutable state to canonical baseline data to create the active world.

**Idempotent** - Repeating an operation with unchanged input produces the same state without duplicate effects.

**Invariant** - A condition that must remain true across all legal state transitions.

**Migration** - Transformation that updates an older save/schema to a newer supported shape.

**Overlay** - A set of changes layered over a baseline instead of a full duplicated snapshot.

**Provenance** - Evidence describing where a field/record came from and how trustworthy it is.

**Referential integrity** - Every referenced ID points to a valid entity and ownership is coherent.

**State machine** - Model where valid actions and transitions depend on the current phase/state.

**View model** - Structured payload tailored for presentation rather than authoritative storage.

## Simulation And Statistics

**Calibration** - Tuning model outputs to plausible observed or intended distributions without merely fitting one example.

**Composite rating** - Summary derived from several traits, such as Offense or Defense.

**Confidence weighting** - Giving high-evidence observations more influence than sparse/noisy ones.

**Deterministic randomness** - Pseudo-random variation that repeats for the same seed and inputs.

**Distribution** - The range, center, variance, and tail behavior of outcomes across players/games/seasons.

**Feature vector** - Numeric representation of player/team context consumed by the simulation.

**Monte Carlo analysis** - Running many seeded simulations to study outcome distributions rather than one result.

**Quantile mapping** - Mapping ranks/percentiles from one numerical distribution into another distribution's scale.

**Tail behavior** - Frequency and magnitude of extreme outcomes such as 36 PPG seasons or major injuries.

**Variance** - Amount outcomes differ around their expected value.

## Basketball Domain

**AAV** - Average annual value of a contract. In this game, `$25M x 4` means $25M per year for four years, not $25M total.

**Asset value** - Contextual trade value of a player, pick, or right.

**Fallback pick** - Alternative pick transferred if a protected primary does not convey.

**Hard cap** - Modeled maximum payroll boundary used by contract/trade legality. The game does not yet model every NBA apron exception.

**Pick obligation** - Structured conditional future right, including protection or swap lifecycle.

**Pick swap** - Right to exchange same-year/same-round pick position when the other pick is more favorable.

**Protection range** - Slots in which the original team keeps a conditionally traded pick.

**Role tier** - Market/gameplay classification such as franchise anchor, starter, rotation, or depth.

**Stepien rule (modeled)** - Guardrail against trading away own first-round picks in prohibited future-year patterns; the project uses a practical model, not complete legal counsel.

**Timeline fit** - Whether player age/development horizon matches a team's competitive phase.

## AI And Narrative

**Context packet** - Compact structured sim-only facts supplied to a narrative model.

**Fallback** - Deterministic template used when optional model generation is unavailable or invalid.

**Grounding** - Restricting generated claims to supplied authoritative context.

**Hallucination** - Model output asserting unsupported facts, such as an old real-world team relationship.

**Persona** - Fixed voice/style contract for a social account.

**Prompt version** - Version identifier included in narrative cache invalidation.

**Structured output** - Model response required to match a JSON shape rather than arbitrary prose.

## Quality And Performance

**Characterization test** - Test that records existing behavior before refactoring, even when implementation is complex.

**Golden scenario** - Fixed input/seed/save used for behavioral or performance comparison.

**Hot path** - Frequently executed or expensive path where optimization matters.

**Invalidation signature** - Hash/key of all inputs determining whether a cached value is still valid.

**Regression test** - Test added to prevent a previously observed bug from returning.

**Soak test** - Long multi-season run used to reveal state drift and lifecycle failures.

**Write boundary** - Point where derived results become persisted authoritative save state.

## Related

- [[Learning/Guided Code Tour]]
- [[Learning/Self-Test Questions]]

