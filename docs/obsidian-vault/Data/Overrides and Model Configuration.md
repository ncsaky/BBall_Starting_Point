---
type: data
status: current
reviewed: 2026-07-10
tags:
  - data/overrides
  - data/configuration
  - project/nba-gm
---

# Overrides And Model Configuration

## Two Different Kinds Of Files

### Data Overrides

These correct or intentionally replace facts/ratings for named entities:

- physical details such as height;
- contract seasons and salary;
- health/startup injury information;
- trait corrections;
- staff records;
- front-office profiles;
- pick-obligation cleanup.

### Model Configuration

These define generalized behavior:

- transaction weights, thresholds, and value curves;
- contract-market cap and role assumptions;
- draft generation/scouting/lottery/rookie-scale settings;
- injury frequency, severity, fatigue, recovery, and development.

Conflating the two makes calibration difficult. “Player X is 6'6” is a fact correction. “Top-five picks use this steepness” is a model decision.

## Important Files

| File | Purpose |
|---|---|
| `trait_overrides.json` | Deliberate final trait corrections |
| `league_trait_ratings_2026_06_20.csv` | Human full-health league prior |
| `player_physical_overrides.json` | Height/physical corrections |
| `contract_overrides.json` | Contract corrections and uncertainty |
| `health_overrides.json` | Durability/startup health corrections |
| `staff_overrides.json` | Staff evidence/corrections |
| `gameplay_staff_seed.json` | Fictional gameplay staff setup |
| `front_office_overrides.json` | Team strategy/personality context |
| `pick_obligations_overrides.json` | Startup protections/swaps |
| `transaction_model_config.json` | Asset, legality, and AI trade tuning |
| `contract_market_config.json` | Market and practical cap tuning |
| `draft_model_config.json` | Class, scouting, lottery, and rookie tuning |
| `injury_model_config.json` | Injury, fatigue, and development tuning |

All live under [data/overrides](../../../data/overrides).

## Why Versioned Configuration?

Hardcoding every coefficient inside Python obscures calibration history and makes review difficult. Versioned JSON lets a maintainer:

- compare tuning changes;
- run controlled experiments;
- distinguish formula implementation from parameter choice;
- preserve save/build compatibility;
- document intentional simplifications.

The code still needs defaults and schema validation because malformed config should not crash halfway through a season.

## Explicit Simplifications

The v1 transaction and contract configs consciously defer deep CBA fidelity. This is not an accidental omission; it is a scope decision. The project models enough cap, hard-cap, salary, roster, timing, and pick constraints to produce meaningful GM choices, then records where full legal fidelity is missing.

## Override Precedence

A defensible precedence order is:

1. normalized public/cached evidence;
2. inferred model output;
3. broad human calibration prior;
4. named manual canonical override;
5. explicit save-specific override.

The later layer must not silently erase unrelated earlier fields. This is why extension contract overrides append future seasons rather than replace entire tables.

## Documentation Standard For New Overrides

Every substantial manual override should answer:

- What entity and field changed?
- Is this factual or gameplay calibration?
- What source/playtest exposed it?
- Why is the general model not being changed instead?
- When should the override be reviewed or removed?

## Risks

- Too many named overrides can hide a weak general model.
- Old overrides can supersede newer evidence indefinitely.
- A configuration change can alter old saves unless model version is captured.
- JSON structure is only as safe as its validators and tests.

## Related Notes

- [[Data/Data Provenance and Trust]]
- [[Systems/Ratings and Traits]]
- [[Quality/Risk Register and Technical Debt]]
