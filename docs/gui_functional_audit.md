# GUI Functional Audit

This tracks the GUI against the CLI/source-of-truth views. The GUI should present the same gameplay information more clearly, not remove it.

## Dashboard

CLI/source payload: `team_dashboard(...)`.

Covered in GUI:
- Save date, phase, user team, record, point differential, hard-cap/tax room, pending AI offers.
- Team identity metrics and ranks: overall, offense, defense, spacing, creation, rim protection, depth, timeline.
- Health summary, cap posture, payroll/tax/hard-cap room.
- Recent league events, recent team results, next team games.
- Rotation table with projected minutes, actual minutes, GP, points, rebounds, assists, steals, blocks, shooting splits, ratings, health, and coach recommendation.
- Ratings table with the full exposed trait stack.
- Contracts table with reachable per-season salary columns.
- Staff table with role, grade, morale/security, contract, and archetype.
- Starting 5 table using the engine-provided injury-aware visual lineup.

Known follow-up:
- Add editable Starting 5 controls once the action layer exposes mutation endpoints.

## Trade Room

CLI/source payloads: trade builder/finder, `team_assets(...)`, `evaluate_trade(...)`, `find_trade(...)`.

Covered in GUI:
- Team cap/tax/hard-cap context in both asset columns.
- Tradeable player, pick, and swap assets with value, role/context text, contract, health, and labels.
- Builder package selection, evaluation, legality, acceptance, and apply.
- Finder search with incoming authorized offers.

Known follow-up:
- Add the same protected-pick/pick-swap term modal the CLI uses before shopping a pick.

## Calendar And Box Scores

CLI/source payloads: `calendar_view(...)`, `box_score_view(...)`.

Covered in GUI:
- Calendar rows with date, teams, score/status, and user result when available.
- Simulated games open a modal box score with team lines and player lines.

Known follow-up:
- Add date-range controls and a team filter.

## Draft

CLI/source payloads: draft board/live draft state.

Covered in GUI:
- Full-screen moment screen.
- Locked scouting preview before draft night.
- Draft-night current pick controls, sim-to-user, sim-full, team board, upcoming picks, trade news.

Known follow-up:
- Add prospect-detail modal using the shared modal shell.

## Playoffs

CLI/source payloads: `playoff_picture(...)`, playoff state.

Covered in GUI:
- Full-screen moment screen.
- East/West playoff picture and live bracket/series rows when available.
- Existing engine simulation hooks are exposed through the action layer.

Known follow-up:
- Add visible simulate-game/round controls after a live playoff save is available in manual testing.

## Free Agency

CLI/source payloads: free-agent investigation and free-agency market state.

Covered in GUI:
- Current free-agent/in-season market.
- Offseason day controls only when the save is actually in free agency.
- Candidate details, fit, ask, and offer form.

Known follow-up:
- Expand investigation details with durability flag and competing offers.

## Staff

CLI/source payloads: staff room/team report/staff market.

Covered in GUI:
- Budget/spend/room, current staff, fire controls, staff market, role filter, hire action.

Known follow-up:
- Add deeper staff trait comparison modal.

## League And Social

CLI/source payloads: standings, league events, social feed.

Covered in GUI:
- Standings, recent transaction events, and social timeline.

Known follow-up:
- Add transaction-kind filters and social persona filters.
