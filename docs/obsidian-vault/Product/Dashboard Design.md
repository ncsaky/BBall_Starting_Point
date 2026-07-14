---
type: product
status: current
reviewed: 2026-07-10
tags:
  - product/gui
  - design/dashboard
  - project/nba-gm
---

# Dashboard Design

## Design Intent

This is an operational sports-management surface, not a marketing landing page. The user repeatedly scans, compares, filters, and acts. The visual system therefore favors:

- dark high-contrast workspace;
- compact serif/sans hierarchy consistent with the current style;
- aligned tables and restrained borders;
- green for positive/active/healthy context, red for injury/negative risk, yellow for thresholds/dividers/new state;
- square or lightly rounded cards;
- direct controls next to the data they affect;
- stable card dimensions that do not jump as content rotates.

## Primary Dashboard Regions

### Team Context Column

- selectable team identity and league ranks;
- front-office buttons;
- starting five;
- staff and budget visualization.

When another team is selected, that team's data loads while user-only controls are disabled. The selected team is highlighted in standings.

### Player Summary

The primary table combines player identity, position, height, age, ratings, games missed, rotation slider/minutes, season box score, and four contract years. It intentionally replaces duplicate full-roster cards.

Important rules:

- up to 17 roster rows remain stable, with placeholder rows for shorter rosters;
- injured player names appear red;
- rating colors are consistent with other views;
- rotation values align within each row;
- yellow dividers visually separate ratings, stats/rotation, and contracts;
- contracts show white values under light-gray year labels.

### Schedule And Trends

- calendar with written date, passed-day X marks, game results, and phase-specific footer actions;
- player development chart with fixed season x-axis and +/-5 net overall y-axis;
- standings-position chart with fixed season x-axis and rank 1-30 y-axis;
- conference standings and league leaders.

### League And Market

- recent league events;
- rotating available staff and free-agent lists;
- contract payroll chart;
- four-year draft-pick logo table.

## Rotating Cards

League leaders, available staff, free agents, and recent events use synchronized progress bars. Hover pauses both rotation and bar animation. Dropdowns allow explicit category/position selection.

Rotating content must not be the only path to information. Full views or modals should expose complete searchable lists.

## Visualizations

### Contract Chart

Four segmented payroll columns represent player contracts by year with tax and hard-cap reference lines, year headers above bars, and payroll footers below. The bar extends slightly past the hard cap so the line is not pinned to the top edge.

### Staff Budget

A segmented bar shares the full height of the staff list. The header summarizes `used / max budget`; redundant labels around the bar are removed.

### Development

Up to five user-selectable players appear as lines, with a horizontal footer legend supporting replace/remove/add. After monthly development, the default set can reset to largest absolute movers and show a temporary `NEW` badge.

## Layout Lessons From Iteration

The recent GUI history repeatedly adjusted individual card widths and offsets. Screenshots exposed overlap, empty gaps, and one viewport fix breaking another. The lesson is not “be more careful with pixels.” It is to encode layout relationships directly:

- use CSS Grid tracks for columns;
- place adjacent cards in the same grid container;
- use `minmax(0, ...)` so contents can shrink without overflow;
- define shared row heights and named areas;
- avoid transforms/negative margins for structural placement;
- use `box-sizing: border-box` globally;
- visually test at multiple desktop and mobile widths.

MDN's [CSS Grid basic concepts](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Basic_concepts) is the relevant primary reference.

## Interaction Rules

- Use icons for familiar actions when available; tooltips explain uncommon ones.
- Use dropdowns for finite category sets.
- Use sliders for minutes only when value and total constraints remain visible.
- Use modals for focused, reversible multi-step actions such as trade builder/finder and offer review.
- Disable controls with a visible reason when inspecting another team or an illegal phase.
- Do not navigate away when a lightweight modal preserves useful dashboard context.

## Accessibility And Responsiveness Debt

The current dashboard is optimized around a very wide desktop viewport. Before broad release it needs:

- keyboard focus order and visible focus states;
- semantic table headings and button labels;
- contrast audit;
- zoom/text-size testing;
- touch target sizing;
- responsive composition rather than merely shrinking the wide board;
- reduced-motion support for rotating cards and animations.

## Source Anchors

- [GUI JavaScript](../../../src/nba_gm_data/gui/app.js)
- [GUI styles](../../../src/nba_gm_data/gui/styles.css)
- [GUI shell](../../../src/nba_gm_data/gui/index.html)

## Related Notes

- [[Architecture/Action Boundary and Local GUI]]
- [[Quality/Risk Register and Technical Debt]]
- [[Roadmap/Release Readiness]]

