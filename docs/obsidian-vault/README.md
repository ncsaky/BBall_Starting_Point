---
type: vault-guide
status: current
tags:
  - project/nba-gm
  - documentation
  - obsidian
---

# NBA GM Project Knowledge Vault

This folder is an Obsidian-ready knowledge vault for the NBA GM sandbox. It is a technical map, design record, learning path, and candid audit of the software as it exists on 2026-07-10.

## Open It

1. Open Obsidian.
2. Choose **Open folder as vault**.
3. Select `docs/obsidian-vault`.
4. Start with [[00 Home]].
5. Open Graph View to see the links among architecture, gameplay systems, decisions, failures, and future work.

No community plugins are required. The notes use standard Markdown, YAML properties, wiki links, and Mermaid diagrams.

## What This Vault Is

- A guided explanation of the codebase for its creator.
- A record of why important choices were made and what alternatives existed.
- A map from product ideas to implementation modules and tests.
- A failure museum that turns past bugs into reusable engineering lessons.
- A release and technical-debt audit, not a claim that everything is finished.
- An interview preparation system grounded in this specific project.

## What This Vault Is Not

- It is not generated API documentation.
- It does not replace tests or source comments.
- It does not pretend a proposed React/native client already exists. The current GUI is a dependency-free HTML/CSS/JavaScript shell served by a local Python server.
- It does not treat every basketball rule as complete. Several models intentionally use practical v1 approximations rather than the full NBA collective bargaining agreement.

## Suggested Reading Orders

### Thirty-Minute Orientation

1. [[00 Home]]
2. [[Architecture/System Context]]
3. [[Architecture/Module Map]]
4. [[Architecture/Canonical Universe and Save Overlay]]
5. [[History/Iteration Timeline]]
6. [[Quality/Risk Register and Technical Debt]]

### Deep Engineering Walkthrough

1. [[Learning/Guided Code Tour]]
2. [[Data/Canonical Build Pipeline]]
3. [[Architecture/Season State Machine]]
4. [[Systems/Simulation Engine]]
5. [[Systems/Transactions and Asset Valuation]]
6. [[Architecture/Action Boundary and Local GUI]]
7. [[Quality/Testing Strategy]]
8. [[Quality/Performance and Optimization]]

### Interview Preparation

1. [[Learning/Interview Defense Guide]]
2. [[Maps/Decisions MOC]]
3. [[History/Failure Museum]]
4. [[Learning/Self-Test Questions]]
5. [[Roadmap/Current State Assessment]]

## Evidence Rules Used Here

- **Current fact** means it was verified in source, configuration, canonical output, tests, or Git history.
- **Inference** is labeled when rationale is reconstructed from code and evolution rather than explicitly recorded at the time.
- **Proposal** is kept in roadmap notes and is not described as implemented.
- Source links point outside this vault into the repository. They work in Markdown-aware editors even though Obsidian's graph only visualizes links inside the vault.

## Maintenance

Update the `reviewed` property and relevant notes when a system changes materially. New cross-cutting decisions should get an ADR in `Decisions/`. New hard-earned bugs should be added to [[History/Failure Museum]] with the violated invariant and regression test.

