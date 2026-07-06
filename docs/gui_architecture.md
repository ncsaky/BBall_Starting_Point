# Standalone GUI Architecture

The GUI should treat the existing Python engine as the source of truth. Native Apple code and any web frontend should call the engine through `nba_gm_data.app_actions.dispatch_app_action(...)`, which accepts plain JSON-like dictionaries and returns plain dictionaries.

## Runtime Direction

- macOS target: package a local app with an embedded Python runtime or local in-process Python service.
- iPhone target: embed CPython in the iOS app through the Apple Python toolchain, then call the same app-action layer locally.
- No remote backend is required for normal play.
- No game rules should move into Swift, React, JavaScript, or a UI shell.

## Action Boundary

`app_actions.py` is intentionally platform-neutral. It exposes core reads and mutations such as:

- save lifecycle: `runtime_status`, `list_saves`, `create_save`
- home/dashboard: `home`, `save_status`, `team_dashboard`, `standings`, `league_events`, `social_feed`
- basketball rooms: `calendar`, `box_score`, `morale`, `free_agents`, `staff_market`, `draft_board`
- transactions: `find_trade`, `find_trade_for_assets`, `evaluate_trade`, `apply_trade`
- advancement/settings: `advance_save`, `process_ai_actions`, `update_game_settings`, `narrative_settings`

Mutating actions are guarded by per-save locks so a GUI cannot apply a trade while a sim advance is still writing the same save.

## Press Conferences

Forced press conferences are disabled by default through `game_settings.press_conferences_enabled = false`. Existing press code, historical records, cached narrative, and pending press events are preserved, but disabled press events do not interrupt the user flow.

## Next GUI Pass

The first runnable GUI pass is a zero-dependency static browser shell served by `nba_gm_data.app_server`. It calls `/api/action`, which forwards directly into `dispatch_app_action(...)`.

Run it locally with:

```bash
nba-gm-data-gui --root . --open
```

This browser shell is a development target for iteration and testing. The eventual packaged macOS/iPhone apps should keep the same action boundary, with native wrappers calling the Python engine locally rather than reimplementing game rules in the frontend.

Future GUI passes should continue replacing terminal flows screen by screen: full trade builder/protection modals, draft night controls, free agency bidding, staff rooms, save import/export, and native Apple packaging smoke tests.
