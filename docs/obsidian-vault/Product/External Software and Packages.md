---
type: product
status: current
reviewed: 2026-07-10
tags:
  - architecture/dependencies
  - tooling
  - project/nba-gm
---

# External Software And Packages

## Python Package

The project package is `nba-gm-data-foundation`, requires Python 3.11+, and currently declares no required third-party Python runtime dependencies in [pyproject.toml](../../../pyproject.toml).

Console scripts:

- `nba-gm-data` for build/research/play commands;
- `nba-gm-data-gui` for the local GUI server.

## Standard Library Choices

The runtime relies heavily on:

- `dataclasses` for canonical records;
- `json`, `csv`, `pathlib`, and `sqlite3` for data/storage;
- `random` for deterministic pseudo-random behavior;
- `unittest` for tests;
- `http.server` for the local GUI;
- `urllib` for Ollama HTTP;
- `threading` for action/save locks;
- `subprocess` for optional ffmpeg interaction.

### Why Dependency-Light?

- Friend setup is simpler.
- Cross-platform packaging has fewer binary surprises.
- Embedded Python on iOS is more plausible.
- Long-lived core logic is not tied to a web framework.
- The repository remains inspectable for a learning project.

### Cost

The project owns more parsing, validation, routing, UI state, and migration code than it would with established libraries. “No dependencies” is not automatically simpler at 50,000+ lines.

## Browser Platform

The GUI uses native Fetch and DOM/CSS APIs:

- [Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [CSS Grid](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Basic_concepts)
- [requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/window/requestAnimationFrame)
- [Animation performance](https://developer.mozilla.org/en-US/docs/Web/Performance/Guides/CSS_JavaScript_animation_performance)

No Node/npm build step is required today.

## ffmpeg

Optional ffmpeg decodes video frames for the ASCII loading cache. Gameplay runs without it once caches exist or when loading animation is disabled.

Why ffmpeg instead of writing a video decoder: codecs and containers are complex, performance-critical domains with mature tooling. Reimplementing them would add risk without game value.

## Ollama

Optional Ollama runs a local language model for social and press writing. The game communicates through local HTTP and can use models such as `llama3.1` or a smaller Qwen model when installed. It falls back to deterministic templates when unavailable.

Why Ollama: simple local model management, privacy, no cloud key/cost, and a standard HTTP surface. Cost: separate installation, model downloads, variable hardware performance, and model-specific behavior.

## Git And GitHub

Git tracks source, configuration, small data, and history. Large loading assets are distributed separately because GitHub rejects normal files above 100 MB. Options include GitHub Releases and Git LFS; the project currently favors a friend-friendly install archive/release rather than forcing LFS on every clone.

## SQLite

Python's built-in SQLite support can store/export canonical records for relational inspection. JSON remains the primary gameplay save format. SQLite is a future candidate for analytics, indexed queries, or stronger transactional runtime storage.

## Apple Packaging Direction

BeeWare Briefcase and Python Apple Support have been investigated for embedded CPython on macOS/iOS:

- [Briefcase](https://briefcase.beeware.org/)
- [Python Apple Support](https://github.com/beeware/python-apple-support)

These are architectural options, not current installed runtime dependencies. An iOS package must prove that canonical loading, save writes, long simulations, local storage, and every Python module work inside the embedded runtime.

## Testing

The suite uses `unittest` discovery. Official documentation: [Python unittest](https://docs.python.org/3.11/library/unittest.html).

## Dependency Decision Framework

Before adding a package, ask:

1. Is this a mature non-core problem we should not maintain ourselves?
2. Does it work on intended macOS/iOS packaging targets?
3. Is it pure Python or does it require binary wheels?
4. What is the transitive dependency and security burden?
5. Can we isolate it behind an interface and keep a fallback?
6. Does it measurably reduce complexity or risk?

## Related Decision

[[Decisions/ADR-004 Dependency-Light Standard Library Runtime]].

