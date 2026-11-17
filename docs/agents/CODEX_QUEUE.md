# Codex task queue

Paste one prompt into a **fresh** Codex chat. One task per chat keeps it from drifting after context compaction. Each prompt is self-contained. Claude reviews the result and updates `BOARD.md`.

Current priority: the new engine (`docs/agents/ENGINE_ROADMAP.md`). GUI tasks are parked at the bottom.

---

## E2: League-wide player input estimator v1 (TOP PRIORITY)

Suggested settings: your strongest model, high effort. This is the most important task Codex has this month. If usage runs out mid-task, keep the resume state current so a fresh chat can continue.

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/ENGINE_ROADMAP.md and docs/agents/STAGE1_DESIGN.md first. You own task E2: component A in STAGE1_DESIGN. Claude is building the adapter (component B) in parallel against your output format, so keep the output schema stable and documented at the top of your report. Mark it "in progress (Codex)" on the board.

GOAL
Every player in the game needs values for the approved 94-input player model (src/nba_gm_data/player_model.py, player_model_registry.py; design in docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md). Today only 32 players have partial hand-researched inputs (docs/ratings-evidence-2026-10-29/*_INPUTS_*.json packets). Build a deterministic, evidence-based ESTIMATOR that produces inputs for ALL 691 players in data/canonical/universe_2026_27_offseason.json, plus a function for draft prospects.

FILES YOU OWN (create or edit only these)
- src/nba_gm_data/input_estimator.py (new)
- scripts/build_player_inputs.py (new): writes data/canonical/player_inputs_2026_27.json
- tests/test_input_estimator.py (new)
- docs/agents/tasks/e2-input-estimator.md (checkpoint plus final report)
Do NOT edit player_model.py/registry semantics, sim.py, interior_game.py, or any engine module. If the schema needs a change, write the proposal in your report instead.

EVIDENCE SOURCES (local only, no purchases)
- Player Stats/player_skill_input_2025_26.json: Crafted NBA 2025-26, ~526 players. Shooting splits, close-shot efficiency, BLK/STL%, deflections, ORB/DRB%, touches/passes, passer rating, play-type usage and points per possession (P&R handler, roll man, spot-up, iso, post, cut, transition, handoff, off-screen), defended-position shares.
- Player Stats/player_stats.json, Even more stats/*.xlsx, data/research/player_career_stats.json + espn_career_raw/ (ESPN careers, 616 of 691 matched by ESPN id).
- Universe player fields: height_inches, weight_lbs, wingspan_inches (427 present), age, position, roles; the 15 existing traits[] (all 691 players; see src/nba_gm_data/traits.py). Old traits may inform priors but must NOT be relabeled as technique skills.
- docs/ratings-evidence-2026-10-29/PLAYER_MODEL_EVIDENCE_COVERAGE_2026_11_12.md: per-input evidence handles and estimation notes. Follow its "evidence-to-input contract".
- Expert opinion: the Nerd Sesh transcript research in docs/ratings-evidence-2026-10-29/ (claim index, named-player dossiers, rating-change proposals). Treat it as expert evidence that can adjust an estimate, with its own source id. It is not the sole truth, and it is not a reason to override clear stats without saying so.
- Basketball Index data may be added later (BBI_ACQUISITION_PLAN_2026_11_11.md). Design the estimator so a new evidence source can be plugged in per input without rewriting it.
- Known data bug: the historical game-box cache has FGM/FGA = 0 (see HISTORICAL_SHOOTING_DATA_QA_2026_11_13.md). Do not use those fields.

REQUIREMENTS
1. For every player and every one of the 94 inputs, emit a record in the existing PlayerInputs schema: value, uncertainty, status, and source/evidence ids. Statuses must distinguish:
   - "estimated": derived from that player's own evidence.
   - "prior": no player-specific evidence; uses a position/role/physical prior with wide uncertainty.
   The ENGINE needs a usable number for every input, so every input must have a value. "Prior" values must be clearly labeled and must not masquerade as measurements.
2. Method: shrink toward position/role priors, weighted by sample size (minutes, attempts, possessions). Keep passing recognition and execution as separate estimates. Make tendencies conditional on opportunity. Physical families come from measurements where present; otherwise from priors (e.g. wingspan from height by position) with wide uncertainty.
3. Scale: no clipping at 100. Map to the registry's scale by rescaling, so elite players stay distinguishable.
4. Ratings-first: inputs come from evidence only. Never tune estimates toward simulation outcomes. There are no simulation runs in this task.
5. Validation: compare estimator output to the 32 hand-researched players' estimated cells (the packets overlap; use the newest value per cell). Report per-input agreement (mean absolute difference, and how often the hand value falls inside your uncertainty band), plus the 10 biggest disagreements with a one-line explanation each. Hand values are a reference, not ground truth.
6. Prospects: estimate_prospect_inputs(prospect, traits, scouting) for generated and real draft prospects (src/nba_gm_data/draft.py: generate_draft_class_records, prospect_traits_from_row), using the same definitions with wider uncertainty. Don't wire it into draft.py; just provide and test the function.
7. Deterministic: same data gives byte-identical output. Standard library only.
8. Tests: schema validity for all 691 players, determinism, no missing values, no clipping pile-ups at the scale max, prospect function, and a few sanity orderings that are obvious from raw stats (e.g. FT shooting follows FT%). Do not hardcode named-player ranking tests.

DELIVER
Run: PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py, then the new tests. Write the final report (plain language, TL;DR first) in docs/agents/tasks/e2-input-estimator.md. Include coverage counts (estimated vs prior, per input family), the validation table, known weak spots, and runtime. Keep a "Resume state" section updated while you work. Set the board row to "review". Do not commit.
```

---

## Parked (GUI, after the engine month or if Codex has spare usage)

### Q1: Three small GUI behavior fixes

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task Q1. Mark it "in progress (Codex)" on the board.

Fix three small behaviors in the browser GUI (src/nba_gm_data/gui/app.js, plus styles.css only if needed). Don't touch any other file except new or updated tests.

1. Next Opponent card after a game (backlog U03). After the W/L result animation plays, the card must switch to the actual next opponent. Today it stays on the finished game. Handle "no next game" and playback interrupted mid-animation.
2. Sim shortcut prefix (U04). Pressing S, then E, W or M must work no matter how long the pause between the keys. The S prefix stays armed until the user clicks something else, presses Escape, or focus moves to a text input. Never hijack typing in inputs or browser shortcuts. No timers.
3. Draft lottery grid order (U05). Around app.js:4837 the reveal grid lists picks 14 down to 1. The grid must show pick 1 at top-left and 14 at bottom-right. Keep the reveal timing (14 then 13 ... then 1); only the spatial placement changes.

Match the existing code style. Add or extend tests where GUI JS tests already exist (tests/*.test.cjs).

When done: write a 10-line plain-language summary at docs/agents/tasks/q1-gui-small-fixes.md. Set the board row to "review". Do not commit.
```

### Q2: Draft board diagnosis (read-only)

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task Q2. READ-ONLY for code and data; you may only create docs/agents/tasks/q2-draft-diagnosis.md and scratch files under output/q2/.

The user saw the 2nd-ranked prospect (96 POT / 80 NOW) fall to 15th and asked whether the AI or our rankings are wrong, and whether there should be both a consensus big board and a scouting board. With file:line references (draft.py, prospect_cards.py, talent.py, gui/app.js draft board):
1. How the displayed ranking is computed.
2. How AI GMs score prospects at their pick.
3. Reproduce across about 5 seeds headlessly: how far the top-5 fall, and which term drove each pass.
4. Whether "upside" and "potential" overlap or double-count.
5. A proposed (not implemented) design for consensus vs scouting boards.

Lead with a 5-line plain-language answer. Set the board row to "review". Do not commit.
```
