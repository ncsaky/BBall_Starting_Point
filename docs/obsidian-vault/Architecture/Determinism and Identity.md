---
type: architecture
status: current
reviewed: 2026-07-10
tags:
  - architecture/determinism
  - architecture/identity
  - project/nba-gm
---

# Determinism And Identity

Determinism is the project's debugging superpower. Identity is the condition that makes determinism meaningful.

## Deterministic Randomness

The engine uses pseudo-random generators seeded from stable domain context, often strings such as `seed:game_id:mode`. The same canonical input, save state, seed, and action sequence should produce the same result.

This does **not** mean every new game must feel identical. Interactive creation without an explicit seed can use fresh entropy. It means that once a save owns a seed, behavior can be reproduced for tests and debugging.

See Python's [random module documentation](https://docs.python.org/3/library/random.html) for the distinction between deterministic pseudo-randomness and cryptographic randomness.

## Domain-Scoped Seeds

Good deterministic design avoids one giant random stream. If an unrelated feature consumes one extra random value, it should not necessarily change every later game. Domain-derived seeds make outcomes more local:

- game simulation: save seed + game ID + mode;
- draft generation: season/class seed;
- lottery: save/season seed and weighted order;
- AI choices: action/date/team context;
- narrative cache: event/context/provider/prompt version rather than simulation RNG.

Not every subsystem is perfectly isolated, but this is the intended direction.

## Identity Contracts

### Player IDs

Names are presentation. Player IDs join roster, contracts, health, traits, stats, transactions, draft history, and narrative packets. Name normalization is useful during ingestion, but runtime joins should use IDs.

### Pick IDs

A pick is not merely “2027 R1.” It needs season, round, source team, current owner, and for current drafts, exact slot or overall-pick identity. Earlier bugs transferred or deduplicated multiple similar picks because code inferred identity from owner or label. See [[Systems/Pick Obligations and Swaps]].

### Game IDs

Game IDs make game simulation idempotent and allow box scores, season stats, schedules, and deterministic seeds to refer to the same event.

### Event IDs

League and narrative events need stable IDs so lazy LLM generation can cache one rendition and avoid duplicate social posts.

## Ordering As Part Of Determinism

Stable seeds are insufficient if iteration order changes. Candidate teams, assets, games, or prospects must be sorted by stable keys before random or tie-breaking operations. Dictionary insertion order is deterministic within a run but should not be treated as an intentional domain ranking unless construction order is controlled.

## Tests Worth Defending

- Same-seed simulations produce the same results.
- Generated draft classes are deterministic yet vary across seeds.
- Random-team selection varies without a seed and repeats with an explicit seed.
- Pick resolution changes only the exact pick ID involved.
- Repeated save enrichment is idempotent.

## Alternatives

### Fully Random Runs

Using system randomness everywhere would create variety but make regression failures hard to reproduce and balance tuning noisy.

### Precomputed Outcomes

Generating an entire season in advance would be fast to display but incompatible with roster, injury, trade, rotation, and morale changes along the way.

### Cryptographic RNG

It provides stronger unpredictability but no gameplay benefit here and weakens reproducibility. This is not a security lottery.

## Related Decision

[[Decisions/ADR-002 Deterministic Seeded Simulation]].

