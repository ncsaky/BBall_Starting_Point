---
type: moc
status: current
tags:
  - map/product
  - map/ux
  - project/nba-gm
---

# Product and UX MOC

The project began as a data foundation and CLI sandbox, then expanded into a multi-season management game and finally a dense dashboard GUI. Product decisions should preserve the depth already proven in the CLI while reducing navigation and interpretation cost.

- [[Product/Product Philosophy]] - audience, fantasy, agency, information density, and what the game is trying to feel like.
- [[Product/CLI to GUI Evolution]] - what the CLI taught, what the GUI changes, and what must remain shared.
- [[Product/Dashboard Design]] - current card system, information hierarchy, interaction patterns, and layout debt.
- [[Product/External Software and Packages]] - Python, browser platform, ffmpeg, Ollama, GitHub releases, and packaging options.
- [[History/Iteration Timeline]] - how the product acquired its present scope.
- [[Roadmap/Release Readiness]] - what friends can test now and what a broader release requires.

## Current UX Boundary

The CLI is still the most complete expression of legal workflows. The GUI is a new client of the action layer and should not duplicate domain rules. A button is only complete when it maps to an engine action, exposes legal intermediate choices, handles errors, refreshes dependent views, and persists the result.

That principle is the practical bridge between [[Architecture/Action Boundary and Local GUI]] and [[Quality/Testing Strategy]].

