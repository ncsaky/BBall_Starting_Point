---
type: quality
status: current
reviewed: 2026-07-10
tags:
  - quality/invariants
  - architecture/state
  - project/nba-gm
---

# System Invariant Matrix

This matrix is the fastest way to reason about a risky change.

| Domain | Authority | Primary mutations | Derived state to invalidate/refresh | Regression evidence |
|---|---|---|---|---|
| Canonical player data | `CanonicalUniverse` build output | rebuild only | name/trait/contract/player indices | deterministic rebuild, core counts, overrides |
| Active roster | save `roster_overrides` + generated players | trade, sign, cut, retire, draft | rotations, starting five, team features, trade context, stats eligibility | stale rotation, ghost stats, rookie onboarding |
| Contracts | save-aware contract with `contract_overrides` | extension, FA signing, trade, rollover | payroll/cap, asset value, narrative cap, dashboard | current-season preservation, cap legality |
| Player skill | baseline traits + development events + save overrides | monthly development, canonical rebuild | composites, simulation/team features, valuation, display | calibration sanity, idempotent development |
| Health | save health states/events | date advance, game workload, recovery | available pools, effective lineup, value risk, narrative | unavailable exclusion, deterministic quotas |
| Game | schedule `game_id` + saved result/log | simulation once | records, stats, recent context, standings, awards | deterministic game, no duplicate IDs |
| Standings | saved team records/results | record game result | team strategy, lottery odds, narrative, charts | save-backed views, current-context trade AI |
| Trade proposal | stored proposal + origin/acceptance/legality | builder/finder/AI generation | offer counters, pending UI | rejected cannot apply, finder accepted applies |
| Player asset value | transaction context | no direct mutation; recompute | asset lists, package evaluations | injury value, context difference, elite floors |
| Draft pick | canonical/generated pick + exact save owner override | trade, lottery resolve, selection | labels, projected slot/value, draft state | exact pick transfer, uniqueness |
| Pick obligation | structured save obligation | create, transfer, resolve, repair | locked assets, labels, values, final owners | self-fallback, retrade, convey/protect/swap |
| Draft order | saved lottery/live draft state | lottery, obligation resolution, draft trade, selection | summary, reveal, asset owner | all views agree, no duplicate pick IDs |
| Staff slot | save staff slot | hire, fire, expire, interim | effects, budget chart, events | budget, one event, interim review |
| League event | save `league_events` factual record | domain action append-once | dashboard/event filters/social source | major thresholds, recency, deduplication |
| Narrative | cache entry keyed by factual context | lazy view generation/reset | rendered social/press only | no sim calls, validation, cache invalidation |
| GUI state | server action response + client view selection | user interaction | DOM only | action smoke, future browser screenshots |
| Season history | archived save season records | rollover once | career/awards/history views | rollover future schedule, ROTY/awards |

## Conservation Rules

These catch subtle corruption:

- A player is active on zero or one team.
- A player cannot be both active-rostered and in the free-agent or retired set.
- A trade conserves each asset: it leaves one controller and enters one controller exactly once.
- A draft pick has at most one current owner and one exact live slot.
- Protected fallback collateral is unavailable until the obligation resolves.
- A game result increments exactly one win and one loss.
- Player game logs reference a game that exists and a rostered participant on that date.
- Staff budget used equals active staff contract cost, not market candidates.
- A contract year for one player/team has one authoritative salary.

## Temporal Rules

- No save advancement moves backward.
- No event occurs after current date or before its causal prerequisites.
- Trade/signing restrictions expire based on modeled date, not number of UI visits.
- Monthly development applies at most once per month checkpoint.
- Awards and rollover apply once per season.
- Narrative cache may be generated later, but its factual source remains dated to the event.

## UI Consistency Rules

- Dashboard, finder, builder, offer list, and inspection use shared player/pick labels.
- Lottery reveal, draft summary, and current assets use saved final owners.
- Team dashboard and trait browser use the same display-rating transform.
- Disabled controls reflect `legal_actions`, not duplicated frontend date rules.
- Selecting another team changes read-only views but not user-team authority.

## How To Use This Matrix

For a proposed change, select every affected row. For each row, name:

1. the authoritative write;
2. dependent derived data;
3. invalidation/refresh;
4. lifecycle test.

If any answer is “the label probably updates itself,” the design is incomplete.

## Related Notes

- [[Architecture/Persistence and Mutation Safety]]
- [[History/Failure Museum]]
- [[Quality/Testing Strategy]]

