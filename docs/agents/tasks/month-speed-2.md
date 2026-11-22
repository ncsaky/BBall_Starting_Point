# Month speed, second pass (MONTH-SPEED, worktree branch `worktree-agent-a1a6b4fa00e03fefa`, 2026-11-22)

## Objective
Get a simulated month in the GUI (including AI front-office activity) as close to 10-20 s as possible
(AGENTS.md rule 10) without changing results. Measure November, the trade-deadline month and one offseason
(draft through opening night) on the Azure pool; profile; cut the biggest costs; identity-check two seeds.

## Boundaries
- Off limits (other agents): `health.py` development functions, `development_outlook.py`, `talent.py`,
  `ratings_model.py` development fit; input estimator and `player_inputs_2026_27.json`; `contract_ai.py`,
  `contract_terms.py`, `contract_history.py`, `cap_ledger.py`, `offseason_decisions.py`; staff decision code in
  `staff.py` / `staff_lifecycle.py`.
- Allowed: profiling scripts, hot paths found by profiling outside those files, tests.

## Method
- Harness: `scripts/check_month_parity.py`. New scenarios `nov-inputs-b` (BOS 55, 94-input ratings) and
  `deadline-inputs` (BOS 55, Jan 10 -> Feb 10 with the deadline stop). `nov-inputs` is LAL 7.
- Baseline engine: commit `27aa06b`, frozen under `speedbase/27aa06b/src` (untracked) because the Azure
  workers have no `.git`.
- Offseason: `season-prepare --model inputs` (GSW 17) and replay the steps from the draft to Nov 1.
- Azure job scripts: `speedbase/job_*.sh` (untracked).

## Resume state
- 2026-11-22: worktree set up; baseline jobs `speed-base-months` and `speed-base-season` started on Azure.
- 2026-11-22 baseline (unprofiled, `27aa06b`): November LAL 74-75 s (canada2, 2 cores; westus 4 cores 74 s),
  November BOS 84 s (westus), deadline month 232-244 s; offseason steps 10-21 (re-signing through Nov 1) 665 s
  on canada. Profiles in `output/month-speed/fetch/` (git-ignored).
- Commit `1de3aea` (feature memo): IDENTICAL on all three month scenarios and with the runtime audit on (westus).
  Nov LAL 74 -> 69, Nov BOS 84 -> 73, deadline 232 -> 220.
- Commits `81086af`, `83682ae`: zone-grid-only shot diet, game-log id set, spatial signature memo, signing
  counterfactual index, backup copy; harness `MONTH_SPEED_WARM=1`. Offseason pair job `speed-off1` running.
- Azure script bug: `start()` reads `monthly_hour_cap` from the worker entry, so a deallocated pool machine can't be
  started (KeyError). Worked around with a patched copy in the scratchpad; not fixed in the repo.
