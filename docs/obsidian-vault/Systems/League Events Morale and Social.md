---
type: system
status: current
reviewed: 2026-07-10
tags:
  - system/events
  - system/morale
  - gameplay
---

# League Events, Morale, And Social

## Three Related But Distinct Things

### Transaction And Gameplay Facts

Transaction logs, health events, game results, staff moves, contracts, and stat lines are authoritative domain facts.

### League Events

League events are a curated, structured public history used by dashboard and dedicated event views. Interactive defaults show transaction events such as trades, extensions, staff hires, and staff fires. Major-only filtering remains available for strict thresholds.

### Social Posts

Social items are commentary about facts. They may be opinionated, funny, positive, negative, or wrong in judgment, but they cannot be wrong about supplied sim facts. See [[Systems/Narrative Engine]].

## Why Structured Event Details Matter

Importance scores alone cannot answer strict product rules such as:

- Did a trade include a first-round pick or a player over 29 MPG?
- Was a contract over $25M AAV?
- Was a staff grade above the public-event threshold?
- Was an injury over 41 expected missed games for a major-minute player?
- Did a box score exceed a precise stat threshold?

Event creation therefore carries structured details. `league_events_view` can filter by kind, transaction group, recency, limit, and `major_only` using facts rather than prose.

## Dashboard Presentation

The main dashboard should have one “Recent League Events” section rather than duplicate recent news/events lists. Game outcomes and press-conference answers do not belong in this transaction-focused feed. The calendar already presents scores.

## Morale

Morale is save-backed team/player context influenced by user and league actions. Press answers, role promises, trades, staff changes, results, and other events can apply bounded deltas.

Morale should influence behavior through explicit mappings rather than natural-language sentiment. A social post's tone does not change morale merely because a model sounds angry.

## Deduplication

One transaction can legitimately have several representations:

- transaction log for audit;
- league event for public history;
- news item for recaps;
- social source item for commentary;
- optional press event for user interaction.

Those records need linked IDs and `append_once` behavior. They should not appear as repeated identical league events or force multiple conferences for one aggregated staff-resolution window.

## Strict Major Thresholds

The implemented product rules use strict comparisons, not inclusive boundaries. For example, exactly 29 MPG or exactly $25M does not satisfy “more than 29” or “over $25M.” This detail belongs in tests because natural-language requirements often hide off-by-one errors.

## Recency

“Recent” means a save-relative window, commonly 30 in-game days from the active date. Historical events stay on disk and can be viewed without the recent filter.

## Invariants

- Every displayed event date is an in-game date.
- Event filtering uses structured details where available.
- Press answers and routine game scores do not pollute transaction events.
- One underlying transaction does not create duplicate public event rows.
- Social output retains a visible factual subject so readers know what is being discussed.
- Morale effects are bounded and deterministic.

## Source Anchors

- [League event view and filters](../../../src/nba_gm_data/save.py)
- [Narrative and social](../../../src/nba_gm_data/narrative.py)
- [Staff event generation](../../../src/nba_gm_data/staff.py)

## Related Notes

- [[Systems/Staff AI]]
- [[Systems/Contracts and Free Agency]]
- [[Systems/Narrative Engine]]

