# Interface Pass

The existing season-dashboard arrangement remains authoritative. The shared
finish is in `gui/interface.css`, loaded after the legacy stylesheet. It supplies
neutral surfaces, regular-weight typography, consistent commands, underlined
tabs, visible keyboard focus, and dialog sizing without changing simulation logic.

## Keyboard Controls

Press the two keys in order, not simultaneously. The prefix expires after 1.5 seconds.
Navigation and simulation buttons now carry compact visible key hints. Hints
are separate from accessible button names and notification counts; repeated
rendering cannot append duplicate hints. A displayed sequence invokes the same
destination/action as its button (including the dashboard's finder shortcut).

| Keys | Action |
| --- | --- |
| Cmd/Ctrl K | Search global commands and enabled buttons on the current screen |
| ? | Searchable shortcut reference |
| G H | Main dashboard for the current phase |
| Right / Left | Assets / This season (outside dialogs, tables and form controls) |
| G R | Viewed team's Assets desktop and full roster |
| G T / G B / G O | Trade builder / trade finder / offers |
| G F / G P / G A | Player finder / prospects / free agents |
| G L / G C | Standings / calendar |
| G S / G N | Staff / league wire |
| G , | Settings |
| S E | Next event, one draft pick, one playoff game per series, or next FA day |
| S W / S M | Simulate week / month |
| S P / S R / S N | Sim to own pick / finish playoff round / next phase |
| Escape | Close command menu or return to the parent dialog |
| Tab / Shift Tab | Next / previous control |
| Up / Down | Move between table rows |
| Left / Right | Move between row controls or switch tabs |
| Enter / Space | Activate the focused native button |
| / | Focus the current search field when present |

Left/right on minute sliders keeps native slider adjustment. Up/down moves
between players without changing their minutes. Other form controls keep their
native editing behavior. Letter shortcuts do not run while typing, composing
text, holding a key, or while the app is busy. Simulation shortcuts invoke the
existing enabled button for the current phase; they do not bypass legality,
confirmation, multiplayer, or save-action handlers.

`GameInterface` owns keyboard dispatch, dialog focus/history, table navigation,
and in-place generic-table sorting. `gameCommands()` in `app.js` is the registry
of named navigation and simulation commands. New visible buttons also become
searchable in the command menu without assigning another global shortcut.

## Verification

Run the focused clipboard browser test with Playwright available:

```sh
node tests/seasonal_clipboard.test.cjs
```

This is UI regression coverage, not a multi-season engine audit or a substitute
for live multiplayer and transaction testing.

## Compact Surfaces And Assets

The live Assets desktop shares the current dashboard's roster and snapshot.
Its extra valuation/pick payload is read once per save revision and dashboard
context. Flipping back does not hydrate the dashboard again. Trades refresh
the snapshot and invalidate asset details; stale in-flight reads are discarded.
The page uses the existing trade builder/finder and offers dialogs. Final-season
salary amounts are yellow, with an explanatory tooltip, without a separate
expiring-contracts panel. This is not the illustrative trading-block editor in
the live game.

Player dialogs are bounded to 1240 by 660 pixels (and to smaller viewports).
Their radars stack vertically, the court retains its proportions, and game-score
SVGs preserve their aspect ratio. Team-roster radars also stack. Cutdown and
staff-retention workspaces size to their content instead of filling the screen.
