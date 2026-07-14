---
type: learning
status: current
reviewed: 2026-07-10
tags:
  - learning/code-tour
  - project/nba-gm
---

# Guided Code Tour

This is a hands-on curriculum. Do not try to read the repository top to bottom. Follow one piece of state through its lifecycle.

## Lab 0: Establish The Baseline

```bash
git status --short
git log --oneline --decorate -20
find src/nba_gm_data -maxdepth 1 -type f -name '*.py' -print
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Questions:

- Which changes are already in the working tree?
- What is the current package entrypoint?
- How long does the suite take on this machine?
- Which five tests are slowest?

Read [[Architecture/Module Map]] before opening the largest files.

## Lab 1: Build One Canonical Player

Read in order:

1. [schema.py](../../../src/nba_gm_data/schema.py): `Player`, `PlayerTrait`, `Contract`, `RosterAssignment`, `CanonicalUniverse`, `to_plain`.
2. [ingest.py](../../../src/nba_gm_data/ingest.py): find the main build function and each stage.
3. [data/overrides](../../../data/overrides): identify the ratings prior, trait, physical, contract, and health overrides.
4. [audit.py](../../../src/nba_gm_data/audit.py): see which referential and coverage failures are reported.

Exercise:

- Choose one player.
- Trace name/ID, team, height, traits, contract, health, and source IDs into canonical JSON.
- Label each value as source fact, inferred value, calibrated prior, manual override, or derived composite.

You should be able to explain [[Data/Canonical Build Pipeline]] without looking at the note.

## Lab 2: Create And Enrich A Save

Read:

1. `create_league_save` in [save.py](../../../src/nba_gm_data/save.py).
2. `ensure_league_save_defaults`.
3. `canonical_with_save`.

Exercise:

- Create a save in a temporary directory.
- Print top-level keys and identify which are season-local, historical, settings, or overrides.
- Enrich canonical data twice and prove the baseline input did not change.
- Manually inspect how a roster or contract override appears in the active view.

Explain why this is an overlay and not a full event-sourced system. Use [[Decisions/ADR-001 Canonical Base Plus Save Overlay]].

## Lab 3: Follow One Simulated Game

Read:

1. `sim_game` and `sim_game_with_context` in [sim.py](../../../src/nba_gm_data/sim.py).
2. Player-pool and minute helpers.
3. Player/team feature construction.
4. Score and player-line distribution.
5. Health adjustment in [health.py](../../../src/nba_gm_data/health.py).

Exercise:

- Simulate one game twice with the same seed and compare serialized results.
- Change one rotation or injury input and compare feature breakdown/outcome.
- Verify every player line belongs to one of the two active rosters.

Be prepared to explain why the engine is probabilistic but deterministic. See [[Architecture/Determinism and Identity]].

## Lab 4: Follow A Date Advance

Read `advance_save` in [save.py](../../../src/nba_gm_data/save.py) slowly. Write down every mutation in order.

Exercise:

- Advance across a monthly development checkpoint.
- Compare health events, game results, player stats, team records, development events, AI actions, offers, and events before/after.
- Explain what would break if AI trades ran only after the whole target range.

This lab is the practical version of [[Architecture/Season State Machine]].

## Lab 5: Value And Apply One Trade

Read:

1. `with_transaction_context` in [transactions.py](../../../src/nba_gm_data/transactions.py).
2. player/pick valuation helpers;
3. `evaluate_trade` and `evaluate_trade_for_team`;
4. legality helpers;
5. `apply_trade_to_save`.

Exercise:

- Compare one player's owner-context asset value and receiver-context package value.
- Make an illegal trade and identify which check rejects it.
- Make a legal accepted trade and list every save collection that changes.
- Attempt to apply a stored rejected proposal and verify refusal.

Explain why legality, AI consent, user consent, and advisor recommendation are four different concepts.

## Lab 6: Track A Protected Pick

Read:

1. `validate_pick_obligation_term` and term application in `transactions.py`;
2. pick-label helpers;
3. `resolve_pick_obligations_for_year` in `save.py`;
4. live draft order synchronization.

Exercise:

- Create a valid top-N protection with a later same-round fallback.
- Retrade the right.
- Resolve one seed where it conveys and one where it is protected.
- Check assets, labels, lottery reveal, draft order, and unlocked collateral.

State all invariants in [[Systems/Pick Obligations and Swaps]].

## Lab 7: Follow A Contract

Read [contract_ai.py](../../../src/nba_gm_data/contract_ai.py): market profiles, role tiers, comps, preference, legality, offer, and application.

Exercise:

- Inspect ask and comps for a star, starter, and fringe player.
- Change years and salary and observe interest/cap legality.
- Cancel and compare save hashes.
- Apply an extension and verify current salary plus future years in dashboard and trade context.

## Lab 8: Draft And Develop A Rookie

Read [draft.py](../../../src/nba_gm_data/draft.py): class generation, scouted views, board, selection score, rookie contract, onboarding.

Exercise:

- Compare true and team-scouted values.
- Generate two classes with the same seed and a third with another seed.
- Draft one player and follow them into roster, contract, rotation baseline, traits, and later development.

## Lab 9: Inspect Staff And Health Feedback

Read [staff.py](../../../src/nba_gm_data/staff.py) and [health.py](../../../src/nba_gm_data/health.py).

Exercise:

- Compare two performance leads' role-specific effects.
- Simulate a high-injury team and inspect firing blame reduction.
- Fire a role, inspect interim review, hire a candidate, and verify budget.

## Lab 10: Treat The LLM As Untrusted

Read [narrative.py](../../../src/nba_gm_data/narrative.py) in this order:

1. provider protocol/settings;
2. context packets;
3. prompts;
4. context hash/cache key;
5. validators;
6. hydrate/cache/fallback.

Exercise:

- Print one extension packet.
- Inject an output with an unsupported former team/player and see validation fail.
- Call twice and prove cache reuse.
- disable Ollama and verify gameplay/social fallback.

## Lab 11: Trace A GUI Action

Read:

1. [app_server.py](../../../src/nba_gm_data/app_server.py);
2. dispatcher/action in [app_actions.py](../../../src/nba_gm_data/app_actions.py);
3. request and render path in [app.js](../../../src/nba_gm_data/gui/app.js);
4. relevant CSS in [styles.css](../../../src/nba_gm_data/gui/styles.css).

Exercise:

- Choose one action such as setting a starting five or reviewing trade offers.
- Trace click -> payload -> action -> mutation -> response -> rerender.
- Prove the JavaScript does not decide game legality.

## Lab 12: Season Rollover

Read `complete_offseason_and_rollover` and its helper calls. Use a temporary save and let the long test finish.

Create a before/after table for:

- active season/date/phase;
- history and awards;
- ages/retirements;
- roster/contracts;
- rookies/draft state;
- stats/restrictions/offers;
- schedule IDs.

If you can explain this transition clearly, you understand the system's integration core.

## Graduation Exercise

Pick one failure from [[History/Failure Museum]]. Without reading its solution, answer:

1. What was authoritative state?
2. Which duplicate/derived state disagreed?
3. Where should validation have lived?
4. What is the smallest behavior-preserving repair?
5. What lifecycle test prevents recurrence?

