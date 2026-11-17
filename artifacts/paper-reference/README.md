# Paper Reference: September 14, 2026

The user's edited player card is the visual authority for this pass. The assets
frame is a provisional layout, not a replacement specification for the dashboard.
The original Paper artboards were read only and were not modified.

## Captured References

- `player-card-2026-09-14.jsx`: player-card export, node L28-0.
- `assets-2026-09-14.jsx`: assets export, frame JC3-0.
- Paper file: https://app.paper.design/file/01M0F1FREF1G779MGJRWGY9EGM/1-0

## Shared Presentation

- Salary panels share a 274 x 397 pixel footprint. Year columns use the same
  geometry and ordering; the player card highlights only the selected player.
- Assets and free agency use three table groups backed by one sorted row list.
  Player names appear once; row selection, hover, and vertical scrolling remain
  aligned across groups.
- The assets page provides six editable player trade-block slots. Ownership and
  roster membership are validated on the server. AI-managed blocks retain their
  existing behavior unless a manual block is present.
- Production reference overrides live in `gui/paper-fidelity.css`.

## Verification

`scripts/verify_paper_fidelity.cjs` checks linked sorting and selection, block
controls with a mocked mutation, player-card navigation, and salary dimensions.
It captures player, assets, free-agency, and staff-retention screens at 1280x720,
1440x900, 1682x963, and 1920x1080. These are read-only UI fixtures, not live-save
simulation tests. The backend block tests independently cover persisted state and
invalid requests.

At compact viewport heights, tables and the free-agency sidebar scroll internally
to preserve the reference chart dimensions. This is not a claim that all sidebar
content is simultaneously visible at 720 pixels high.
