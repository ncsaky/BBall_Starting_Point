# UI-POLISH: overnight visual and UX polish pass

_Claude Opus agent, own worktree branch `worktree-agent-abbc1f6f658d21d15`, 2026-11-21 (overnight). Status: **in progress**._

## Objective
Audit the in-scope screens, then fix the 10-15 most valuable, low-risk visual and usability problems. Refine the
existing look; do not redesign it. Never change what a number means (rule 4).

## Boundaries
- In scope: home dashboard and journey view, player card, team pages (not the front-office read), standings,
  schedule and calendar, league leaders, box scores, game logs, injury report, Minutes + Availability, playoff
  bracket, draft room and draft boards, staff/coaching, settings, save menu and new-career flow, the assistant GM
  phone's look, the season slideshows' look.
- Out of scope (other agents tonight): free-agency room, offseason checklist and stops, trade window, Trade Market
  board, and `free-agency.css`, `offseason.css`, `trade-workspace.css`.
- Light job: no season simulations, `nice -n 10` server, own process IDs only.

## Resume state
- Worktree symlinks made (see task brief). Server: `PYTHONPATH=src nice -n 10 .venv/bin/python -m nba_gm_data.app_server
  --root . --save-dir output/ui-polish/saves --port 8791` (pid in `output/ui-polish/server.pid`).
- Saves in `output/ui-polish/saves/` are copies of earlier agents' scratch saves (regular season Oct 29, playoffs,
  draft night), so no simulation is needed.
- Screenshot driver: `output/ui-polish/shoot.cjs` + `steps/*.cjs`, run with
  `NODE_PATH=~/.hermes/hermes-agent/node_modules`.
- Audit done (screenshots in `output/ui-polish/shots/audit/`). Fixes 1-12 written (see report below once
  finished); "before" server runs the base commit's code from `output/ui-polish/base/src` on port 8792
  (pid `server_before.pid`, saves `saves_before/`). Pairs: `run_pairs.sh before|after season playoffs start`
  writes `output/ui-polish/pairs/`.
- Next: check after shots, copy pairs to `output/ui-polish/NN_*_before/after.png`, run tests, write report.
