# Next Opponent restoration review — 2026-10-30

The rejected table prototype has been withdrawn. The only remaining production-style difference identified during read-only review was restored in `src/nba_gm_data/gui/styles.css`: stat cells again clip overflowing text with ellipsis and no wrapping. The current card renderer and all other inspected styles remain unchanged. No table behavior has been implemented.

## Isolated preview

- Preview: `http://127.0.0.1:8791/output/ui-completion-next-opponent/index.html`
- Fixture: `output/ui-completion-next-opponent/index.html`
- The fixture uses the existing card and window-frame styles, with sample Boston data. It is not connected to a save or simulation.
- The current renderer does not include player headshots in this card.
- No pre-edit screenshot was saved, so the screenshot evidence is a restored-state capture only; the original clipboard image cannot be compared side by side.

## Missing table behaviors on this card

| ID | Status | Smallest appearance-preserving change |
| --- | --- | --- |
| T01 Sorting | Missing | Sort the same six rendered rows on activation; keep current order and visuals at rest. |
| T02 Whole-row hover | Missing | Add a row hover fill while keeping injury and link focus/hover cues visible. |
| T03 Alternating rows | Missing | Add a subtle even-row background without changing dimensions or spacing. |
| T04 Sorted-column emphasis | Not applicable until T01 | Once sorting exists, add a subtle active-column fill without changing geometry. |
| T05 Bar width and unfilled darkness | Present | Existing rating tracks and fills are already present; no change identified. |

Approval is required before implementing any of the listed behaviors or propagating styling to other cards.
