@AGENTS.md

## Claude Code specifics

- Claude Code is the **coordinator**: keeps `docs/agents/BOARD.md` current, reviews worker output, runs tests, commits (with user approval), and writes Codex task prompts into `docs/agents/CODEX_QUEUE.md`.
- **Codex has limited usage** (ChatGPT $20 plan). Give it well-scoped, self-contained tasks with explicit file boundaries and acceptance checks, so one session can finish them. Good fits: bounded GUI/backlog items, research/evidence passes, isolated features with clear tests.
- **Subagent routing:** use `haiku`/`sonnet` subagents for read-only sweeps, backlog reconciliation and mechanical edits. Keep design-heavy engine work and final review on the main model.
- **Git is currently blocked** by an unaccepted Xcode license (`/usr/bin/git` errors with exit 69). The user must run `sudo xcodebuild -license accept` once.
