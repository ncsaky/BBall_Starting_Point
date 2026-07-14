---
type: adr
status: accepted
decision: dependency-light-runtime
reviewed: 2026-07-10
tags:
  - decision/dependencies
  - python
  - packaging
---

# ADR-004: Dependency-Light Standard Library Runtime

## Context

The game should be easy for nontechnical friends to install, portable across macOS and future iOS packaging, and maintainable as a learning project. Many core needs can be served by Python and browser standard libraries.

## Decision

Keep required Python runtime dependencies at zero where practical. Use standard-library JSON, CSV, dataclasses, SQLite, HTTP, URL, threading, subprocess, and unittest. Isolate optional external tools such as ffmpeg and Ollama behind fallbacks.

## Why

- simpler `git clone` + Python setup;
- fewer binary wheels and packaging incompatibilities;
- lower supply-chain surface;
- direct understanding of runtime behavior;
- optional enhancements cannot block the game.

## Alternatives

### Web Framework And Validation Stack

FastAPI/Pydantic/SQLAlchemy could provide routing, schema validation, docs, and persistence patterns. They also add dependencies and iOS packaging questions. As the action surface grows, selected pure-Python dependencies may become justified.

### React/Node Toolchain

Would improve component structure and frontend testing ecosystem, but adds build tooling and distribution complexity. The current vanilla client was faster to bootstrap.

### Scientific Stack

NumPy/Pandas could accelerate/clarify some data operations, but binary packaging on iOS and conversion overhead need evidence. Current domain loops are mostly Python dictionaries and evolving logic.

## Consequences

Positive:

- straightforward runtime;
- good portability;
- graceful optional features;
- no dependency installation for tests/core play.

Negative:

- custom validation, routing, migration, and UI code;
- large vanilla JS/CSS files;
- fewer optimized numerical primitives;
- standard `http.server` is local-development only.

## Evidence

[pyproject.toml](../../../pyproject.toml) declares no dependencies. Ollama uses standard-library HTTP; ffmpeg is invoked externally; the GUI uses native Fetch/DOM/CSS.

## Revisit When

- custom infrastructure costs more than a well-supported package;
- a selected library has proven Apple packaging support;
- security/public hosting requires production framework capabilities;
- profiling proves a numerical dependency offers a material win.

## Related

- [[Product/External Software and Packages]]
- [[Quality/Security and Privacy Boundaries]]

