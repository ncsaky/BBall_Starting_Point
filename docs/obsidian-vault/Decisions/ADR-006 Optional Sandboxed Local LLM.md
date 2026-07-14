---
type: adr
status: accepted
decision: optional-sandboxed-local-llm
reviewed: 2026-07-10
tags:
  - decision/narrative
  - local-llm
---

# ADR-006: Optional Sandboxed Local LLM

## Context

Handwritten social and press templates were repetitive and weak at combining the evolving save's facts. A language model can create varied voices and contextual questions, but its memorized real-world NBA knowledge is stale and often conflicts with the simulated universe.

## Decision

Use optional local Ollama generation as an untrusted narrative renderer. Supply compact save-only context, require structured JSON, validate factual and gameplay constraints, cache by context/prompt/provider, and fall back to deterministic templates. Never call the model during normal simulation.

## Why

- richer and more varied writing;
- local privacy and no API cost;
- model choice for hardware constraints;
- league facts remain deterministic;
- provider failure cannot block play;
- lazy generation contains latency.

## Alternatives

### Expand Templates Only

Reliable and fast but requires combinatorial writing to cover trades, contracts, cap, injuries, team context, and personalities.

### Cloud LLM

Potentially higher quality, but introduces keys, cost, internet reliance, privacy, and release operations.

### Let The LLM Generate League Events

Rejected. It would make unvalidated text authoritative and destroy reproducibility.

### Generate All Posts At Event Time

Preserves exact historical context but makes month simulation wait on many model calls. The save already retains enough event/context evidence for lazy rendering.

## Consequences

Positive:

- narrative quality can improve independently of domain logic;
- game works offline without model;
- safety is testable through validators;
- cache amortizes model latency.

Negative:

- validators have grown complex and domain-specific;
- smaller models may fail JSON or repeat fallback frequently;
- prompts and cache versions require maintenance;
- “grounded” output can still express questionable opinions, by design.

## Evidence

[narrative.py](../../../src/nba_gm_data/narrative.py) contains provider interfaces, packets, prompts, persona/stance selection, semantic validation, cache, fallback, and press effect mapping. Tests mock success, timeout, malformed output, hallucinated names/teams, cap/rank errors, cache reuse, and no sim-time calls.

## Revisit When

- an on-device iPhone model replaces desktop Ollama;
- validation maintenance suggests a constrained fact-to-language grammar;
- a cloud option is added with explicit user consent;
- press conferences are re-enabled and require latency/quality redesign.

## Related

- [[Systems/Narrative Engine]]
- [[Quality/Security and Privacy Boundaries]]

