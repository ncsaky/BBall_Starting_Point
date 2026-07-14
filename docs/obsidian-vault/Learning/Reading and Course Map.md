---
type: learning
status: current
reviewed: 2026-07-10
tags:
  - learning/resources
  - project/nba-gm
---

# Reading And Course Map

Use resources to answer a concrete project question. Reading without applying it to this repository will not create durable understanding.

## Python Language And Runtime

### Core References

- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) - connect to [[Data/Domain Schema]].
- [Python random](https://docs.python.org/3/library/random.html) - connect to [[Architecture/Determinism and Identity]].
- [Python profiling](https://docs.python.org/3/library/profile.html) - connect to [[Quality/Performance and Optimization]].
- [Python unittest](https://docs.python.org/3.11/library/unittest.html) - connect to [[Quality/Testing Strategy]].
- [Python sqlite3](https://docs.python.org/3/library/sqlite3.html) - compare with JSON saves in [[Architecture/Persistence and Mutation Safety]].
- [Python threading](https://docs.python.org/3/library/threading.html) and [multiprocessing](https://docs.python.org/3/library/multiprocessing.html) - evaluate, do not assume, same-day parallelization.

### Applied Exercise

Profile `advance_save`, then identify one function whose cost is repeated work and one whose cost is necessary domain logic. Explain the difference.

## Probability, Simulation, And Calibration

- [MIT 18.05 Introduction to Probability and Statistics](https://ocw.mit.edu/courses/18-05-introduction-to-probability-and-statistics-spring-2022/) - undergraduate course with readings, exercises, and solutions.
- [MIT 6.041SC Probabilistic Systems Analysis](https://ocw.mit.edu/courses/6-041sc-probabilistic-systems-analysis-and-applied-probability-fall-2013/) - lecture videos and applied probabilistic modeling.
- [MIT Introduction to Probability video/notes resource](https://ocw.mit.edu/courses/res-6-012-introduction-to-probability-spring-2018/pages/) - random variables, inference, and random processes.
- [Wikipedia: Monte Carlo method](https://en.wikipedia.org/wiki/Monte_Carlo_method) - conceptual orientation for multi-seed league calibration.
- [Wikipedia: Quantile function](https://en.wikipedia.org/wiki/Quantile_function) - background for the league-ratings prior mapping.

### Applied Exercise

Run 30 seeded seasons and report mean, standard deviation, and 5th/95th percentile for top PPG, APG, team wins, injuries, trades, extensions, and coach firings. Explain which outputs require distribution tests instead of exact assertions.

## Architecture And State

- [Architecture Decision Records](https://adr.github.io/) - why this vault includes explicit decisions.
- [Martin Fowler: Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html) - compare with the save overlay in [[Decisions/ADR-001 Canonical Base Plus Save Overlay]].
- [Wikipedia: Finite-state machine](https://en.wikipedia.org/wiki/Finite-state_machine) - connect to season phases and legal actions.
- [SQLite Atomic Commit](https://www.sqlite.org/atomiccommit.html) - learn what robust persistence protects, even while JSON remains primary.
- [The Missing Semester](https://missing.csail.mit.edu/) - shell, Git, debugging/profiling, and build tools useful for this repository.

### Applied Exercise

Draw the extension and protected-pick state machines. Identify transitions, terminal states, illegal transitions, and persisted history.

## Web UI

- [MDN Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API) - action request boundary.
- [MDN CSS Grid](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Basic_concepts) - replace independent card offsets with structural tracks.
- [MDN requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/window/requestAnimationFrame) - synchronized rotating-card progress.
- [MDN animation performance](https://developer.mozilla.org/en-US/docs/Web/Performance/Guides/CSS_JavaScript_animation_performance) - smooth UX without needless layout work.
- [WAI-ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/) - keyboard/modal/table/dropdown patterns.

### Applied Exercise

Rebuild one dashboard row with a named CSS Grid, then prove at three viewport widths that cards neither overlap nor leave unintended structural gaps.

## Local LLM Systems

- [Ollama Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs) - JSON response constraints.
- [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) - treat model output and external context as untrusted.
- [Wikipedia: Retrieval-augmented generation](https://en.wikipedia.org/wiki/Retrieval-augmented_generation) - conceptual comparison; this game uses curated state packets rather than general document retrieval.

### Applied Exercise

Construct five malicious or stale narrative responses and explain which parser/validator layer rejects each. Then identify one true but irrelevant statement that should also be rejected for quality.

## Git And Project History

- [Pro Git](https://git-scm.com/book/en/v2) - free complete Git book.
- [GitHub large files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github) - why loading video is external.
- [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage) - alternative asset strategy.

### Applied Exercise

Choose three commits from [[History/Iteration Timeline]], inspect their diffs/tests, and explain how the design evolved rather than merely what lines changed.

## Obsidian Knowledge Graph

- [Obsidian internal links](https://help.obsidian.md/links) - wiki links and aliases.
- [Obsidian Graph View](https://help.obsidian.md/plugins/graph) - inspect clusters and orphan notes.
- [Obsidian properties](https://help.obsidian.md/properties) - use YAML type/status/tags for filtering.

### Applied Exercise

Create a local graph filtered to `#system` and explain which systems are most connected and why. Add one missing relationship you discover while reading source.

## Apple Packaging

- [BeeWare Briefcase](https://briefcase.beeware.org/)
- [Python Apple Support](https://github.com/beeware/python-apple-support)
- [Apple App Sandbox](https://developer.apple.com/documentation/security/app-sandbox)

### Applied Exercise

Build a tiny embedded-Python spike before promising the full game. Measure canonical load, save write, one-day advance, memory, and cold startup on simulator and device.

## Sports Modeling Practice

There is no single course that validates this game's basketball assumptions. Use a reproducible modeling notebook/report mindset:

- define the basketball claim;
- identify observed and latent variables;
- distinguish calibration from validation data;
- compare distributions across seeds;
- inspect positional/archetype subgroups;
- document subjective thresholds;
- test interventions, not only correlations.

Connect this practice to [[Systems/Simulation Engine]], [[Systems/Ratings and Traits]], and [[Systems/Transactions and Asset Valuation]].

