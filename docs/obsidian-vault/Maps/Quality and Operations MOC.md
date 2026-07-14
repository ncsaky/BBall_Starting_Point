---
type: moc
status: current
tags:
  - map/quality
  - project/nba-gm
---

# Quality and Operations MOC

Quality here means preserving a coherent league over long spans, not merely avoiding exceptions. A function can return successfully while producing duplicate picks, ghost statistics, impossible contracts, stale lineups, or misleading labels.

- [[Quality/Testing Strategy]] - regression suite, deterministic tests, integration boundaries, and missing test layers.
- [[Quality/System Invariant Matrix]] - authority, mutation, invalidation, and evidence across domains.
- [[Quality/Performance and Optimization]] - measured hotspots, safe caches, deferred parallelism, and profiling method.
- [[Quality/Risk Register and Technical Debt]] - ranked architectural and product risks.
- [[Quality/Security and Privacy Boundaries]] - local server assumptions, save files, Ollama, and distribution boundaries.
- [[History/Failure Museum]] - bugs grouped by violated invariant and lesson.
- [[Roadmap/Current State Assessment]] - candid present-tense assessment.
- [[Roadmap/Release Readiness]] - alpha, beta, packaging, migration, and support criteria.

## Quality Heuristic

For every cross-system feature, ask four questions:

1. What is the authoritative state?
2. Which derived views or caches depend on it?
3. What invalidates those derivatives?
4. Which deterministic test proves the lifecycle from creation through resolution?

This heuristic explains why pick obligations, contracts, and roster changes have generated more difficult bugs than isolated stat formulas.
