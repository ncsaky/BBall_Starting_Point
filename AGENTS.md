# NBA GM Sandbox: agent rules

This file is the shared rulebook for every coding agent on this repo: **Claude Code** (lead/coordinator) and **Codex/ChatGPT** (worker on a limited $20 plan). Read it fully at the start of every task and again after any context compaction.

## 1. What this project is

A deterministic, multi-season NBA general-manager simulator. One Python engine (`src/nba_gm_data/`) drives a CLI (`nba-gm-data play`) and a browser GUI (`nba-gm-data-gui`, static files in `src/nba_gm_data/gui/`, HTTP layer in `app_server.py` / `app_actions.py`). New saves start in the 2026 offseason. Status: private friends-and-family beta (macOS ZIPs built via `scripts/build_macos_beta.sh`).

Three work tracks exist. Know which one your task belongs to:

| Track | What | Where |
|---|---|---|
| **A. Playable game** | GUI, workflows, saves, AI GM behavior, packaging | `gui/`, `app_*.py`, `play.py`, `save.py`, `transactions.py`, `draft.py`, ... |
| **B. Player model and ratings** | Approved 94-input player model (64 skills, 12 physical families, 18 tendency families, roles), evidence-based ratings | `player_model*.py`, `docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md`, `docs/ratings-evidence-2026-10-29/` |
| **C. Experimental possession engine** | Event-level basketball sim (screens, passing, recovery, interior defense). **Default OFF; not used by normal gameplay** | `action_choice.py`, `creation_passing.py`, `pass_recovery.py`, `compact_recovery.py`, `interior_*.py`, `offense_response.py`, `screen_navigation.py`, `shot_geometry.py`, `experiments/` |

## 2. Non-negotiable product rules (from the user)

1. **Ratings first.** Player abilities must be grounded in evidence. Tune the engine around realistic ratings. Never lower or raise a player's rating to hide an engine defect or hit a target outcome. A rating correction needs independent evidence and its own attribution.
2. **Do not drop approved player-model dimensions.** All 64 skills, 12 physical families, 18 tendency families and the approved roles stay.
3. **No clipping ratings at 100.** Rescale ranges instead of clamping, so elite players stay distinguishable.
4. **What the user sees must match what the engine uses.** Don't display a rating that the sim ignores or computes differently.
5. **Old saves don't matter.** The game is in development. New saves get the improved model. Don't build or maintain legacy compatibility for existing careers unless asked.
6. **Experimental engine stays default OFF** until a task explicitly authorizes activation in normal gameplay.
7. **The point of the player model is distinguishing players.** Keep four layers separate and visible: raw technique skill, raw physical tools, tendencies (what they choose to do), and coach usage/deployment. The user's basketball taste follows Nerd Sesh, Basketball Index and analysts like Taylor Metrics. Judge "does this rating look right" by that standard.
8. **Minutes:** the user sets rough minutes for their team; the modeled coach decides actual playing time game by game and in-game (foul trouble, fatigue, hot or cold hands, blowouts, matchups), so minutes vary realistically around those targets.
9. **Two scorecards judge any engine change:** the betting-odds probability test (`validate-season-probabilities`; no-vig market odds, Brier score and log loss, player props) and the real-stat targets (`scripts/calibration_report.py`, weighted by sample size, usage and role). Don't regress either one silently.
10. **Speed budget:** simulating one month in the GUI, including AI front-office activity, should take about 10–20 seconds.
11. **LeBron James is a deliberate one-of-one exception** (`transactions.py` `goat_exception_player`). He must never be traded in regular sims, and his fixed trade value stays. Don't "fix" it.
12. **Table style** (all GUI tables): one solid dark line under the header (the user rejected the double rule on 2026-11-23: it read as a white gap), small bold header text, alternating row shading, whole-row hover highlight, sorted-column shading, headshots bottom-aligned filling row height. Match existing tables. The full look and contrast rules are in `docs/UI_STYLE_GUIDE.md`.

## 3. Writing for the user

The user reads your summaries. They have asked for **plain, everyday language**: no compressed jargon, no undefined acronyms or internal IDs (say "perimeter contests," not "C37"). Lead with what changed and what it means for the game, then the details. A summary longer than about 15 lines should start with a 3-line TL;DR.

## 4. Coordination protocol (how Claude and Codex share this repo)

- **The board is the single source of truth:** `docs/agents/BOARD.md`. It lists in-flight tasks, owners, the files each task may touch, and the queue.
- **Before starting:** read the board. Only work on a task assigned to you there (or one the user gives you directly; add it to the board). Do not edit files listed under another agent's in-flight task.
- **Task checkpoint file:** for any task longer than one sitting, keep `docs/agents/tasks/<task-slug>.md` with the objective, boundaries, and a short "resume state" section updated as you go. Reread it after context compaction. Older tasks used `docs/*_ACTIVE_TASK.md`; those are historical.
- **Progress line (the user watches it live):** near the top of your task file, keep one line `Progress: N/M - what you are doing now` (for example `Progress: 3/7 - season simulation before the change`). Set M when you plan the task, and update the line each time you start a step. The live tracker (`scripts/watch_everything.py`) turns it into your progress bar.
- **When done:** write a short report (plain-language summary first), update your task's row on the board to `review`, and stop. The coordinator reviews, runs tests, and commits.
- **Git:** only the coordinator (Claude Code) commits, and only with the user's approval. Workers leave changes uncommitted. Never run destructive git commands (`reset --hard`, `checkout -- .`, `clean`, force push).
- **Don't revert other agents' work.** If you find something that looks wrong in a file you don't own, note it in your report.

## 5. Engineering norms

- **Python 3.11+** (the local `.venv` is 3.14). Dependency-light standard-library runtime (see ADR-004 in `docs/obsidian-vault/Decisions/`); don't add packages without asking.
- **Determinism:** simulation is seeded. Preserve RNG streams unless a change is meant to alter outcomes, and say so when it is.
- **Tests:** full suite `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests`. A single module: `PYTHONPATH=src .venv/bin/python -m unittest tests.test_<name>`. Run the focused tests for what you touched; run the full suite before handing back anything that touches shared engine/save code.
- **Big test runs go in parallel:** `.venv/bin/python scripts/run_tests_parallel.py --all` (or `--match "trade|free_agen"`, or module names; add `--js` for browser tests and `--calibration` for the real-stat scorecard). It splits modules across workers (default 3, at lower priority) using each module's last run time. **Laptop load limit:** at most two heavy jobs at once (an agent's probe, replay or big test run each count). Use `--workers 2` while other heavy jobs run. The machine has crashed under more.
- **Long runs go to the Azure worker pool** (multi-season probes, offseason replays, betting-test runs): `.venv/bin/python scripts/azure_worker.py run --name <job> --dir <checkout or worktree> --fetch <output path> -- env PYTHONPATH=src <command>`. Four machines (Canada, Canada 2, West US 2, Sweden) run jobs side by side; each job claims an idle one and it switches off afterwards. `azure_worker.py status` shows them. Prefer this to running long jobs on the laptop.
- **Proportional verification.** Match the depth of verification to the risk. Exact-parity, RNG, and accounting checks belong on engine changes. Hash manifests, sealed held-out campaigns and 1e-9 numerical gates are not the default. Use them only when a task asks for them.
- **Large outputs** go in `output/` (git-ignored, already ~19 GB). Don't write large artifacts into `docs/` or `src/`.
- **Performance budget:** a busy sim day currently takes ~15 s (mostly the AI trade market). Don't make normal-gameplay paths materially slower without saying so up front.

## 6. Key references

- Approved player model: `docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md`
- Player-model milestone log (Codex coordinator, Nov 12–16): `docs/PLAYER_MODEL_IMPLEMENTATION_STATUS_2026_11_12.md`
- User's UI/gameplay wishlist: `docs/USER_COMPLETION_NOTES_2026_10_29.txt` and `docs/MINIMUM_COMPLETION_BACKLOG_2026_10_29.md`
- GUI conventions: `docs/UI_INTERACTION_GUIDE.md`, `docs/gui_architecture.md`
- Architecture notes: `docs/obsidian-vault/` (written July; partly stale)
