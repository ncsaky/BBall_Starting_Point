---
type: system
status: current
reviewed: 2026-07-10
tags:
  - system/health
  - system/development
  - gameplay
---

# Health Fatigue And Development

## Responsibility

[health.py](../../../src/nba_gm_data/health.py) builds durability profiles, startup injuries, evolving health states, fatigue, rust, injury events, availability-adjusted player pools, and monthly trait development.

Health is intentionally separate from full-health skill ratings. See [[Systems/Ratings and Traits]].

## Health Layers

### Profile

Longer-lived information such as durability, injury risk, body-area tendencies, and startup injury evidence.

### State

Date-specific condition such as healthy, injured, fatigue, recovery, return-to-play, rust, and games since recovery.

### Event

A dated injury with severity, expected duration/games missed, affected body area, and context.

## Simulation

`simulate_health` advances state over a date range using schedule workload, minutes, stamina, rest, player risk, staff effects, and deterministic randomness. League-wide severity and body-area quotas guide distributions so the simulation does not drift into implausible all-minor or all-catastrophic seasons.

This is quota-guided, not quota-forced. Individual risk and context still matter, but league-level targets stabilize a noisy process.

## Availability

Before a game, `sandbox_health_adjusted_pool` filters unavailable players and applies state effects. Rotations are renormalized so the game still allocates plausible minutes. A player not rostered to either team is also excluded, preventing ghost statistics.

Starting five display uses a related but distinct rule: an injured manually selected starter is temporarily replaced by a healthy auto-fill, and the saved manual choice returns when the player becomes healthy. The visual lineup remains engine-neutral.

## Injury And Trade Value

The desired model distinguishes:

- **current one-off injury:** modest temporary value risk, even if the player misses a long stretch;
- **post-recovery rust:** small penalty that decays through healthy games;
- **successive injury before recovery confidence:** resets/increases the penalty;
- **recurring history/durability:** meaningful structural risk.

Startup injuries created an edge case because elite players had zero current minutes and games. Generic low-minute logic capped their value as if they were fringe players. The fix requires valuing established ability and role separately from current-season opportunity.

## Monthly Development

`advance_development` generates trait-level changes at month checkpoints. Inputs include:

- age curve;
- minutes and role;
- current trait and potential room;
- development staff and coach context;
- health drag;
- player-specific deterministic focus;
- bounded random variance.

Young players generally have positive room, prime players are more stable, and older players regress more often. Growth is trait-specific rather than a uniform overall bump. The dashboard reconstructs monthly overall movement from these trait events and displays a bounded seasonal net-change chart.

The UI may highlight the five largest absolute movers after a monthly checkpoint. That is a view choice, not a different development model.

## Reasonable Bounds

The current product expectation treats approximately +5/-5 displayed overall as a rare season ceiling/floor. Most players should move far less. A flat chart can indicate either genuinely small trait changes or a view failing to translate/display event deltas; both need separate tests.

## Staff Effects

- Performance staff affect prevention, conditioning, recovery, and injury burden.
- Development staff affect growth quality and trait focus.
- Coaches can influence development context.

These effects create reasons to manage staff without allowing one rating to dominate the entire health model.

## Invariants

- An unavailable player cannot appear in a new game box score.
- Historical stats remain after injury or release; only new accumulation is blocked.
- Health simulation is deterministic for the same state, dates, and seed.
- Development applies once per crossed monthly checkpoint.
- Trait events change save-aware traits without mutating baseline canonical data.
- Current injury does not permanently erase full-health skill.

## Alternatives

### Independent Per-Game Injury Rolls

Easy to implement but can create unstable league-wide distributions and ignores recovery/fatigue continuity.

### Predetermined Retirement/Injury Timelines

Predictable and easy to guard contracts against, but reduces emergent variation. A hybrid deterministic risk decision is more appropriate for retirement than a fully fixed injury script.

### Uniform Overall Development

Simple for users, but makes players grow identically and weakens archetype evolution. Trait-level events preserve basketball identity.

## Source And Configuration

- [Health module](../../../src/nba_gm_data/health.py)
- [Injury model v1](../../../data/overrides/injury_model_config.json)
- [Health overrides](../../../data/overrides/player_health_overrides.json)
