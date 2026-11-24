# Sidebar pages layout (branch `sidebar-pages`)

Progress: 1/7 - building the page shell

Asked 2026-11-24 night: on a branch, replace the free-floating card board with a sidebar of pages. Each sidebar item
opens a page that fills the screen; the cards are "dissolved" onto the pages (no window frames), several per page or one
per page, kept at their own proportions (scaled as a whole, never stretched). Consistent places for controls, one obvious
next step at the bottom right, the preseason outlook as a full page. Player cards, box scores and the other pop-ups stay
pop-ups. Don't break anything inside the cards.

## Boundaries
- Worktree `/Users/noahtyler/Developer/BBall_data/BBall_pages`, branch `sidebar-pages` (not merged; main untouched).
- Preview: launch.json `pages-preview` (port 8767, saves copied to scratchpad `pages_saves/`).
- Files: `gui/card-pages.js` and `gui/card-pages.css` (new), small hooks in `gui/card-board.js`, `gui/app.js`
  (layout setting), `gui/index.html`.

## Design
- Pages mode is on by default on this branch (`<html data-layout="pages">`); Settings can switch back to the board.
- card-board.js still builds every card frame; in pages mode the page module moves the frames into page slots and the
  board canvas stays only as the layer for pop-up windows (player cards, extension cards).
- A page is rows and columns of cards at their natural sizes; the whole page scales to fit the screen (one scale per
  page so text sizes match across a page). List-like cards can grow into spare height.
- Sidebar = the old top bar turned on its side: team, date and phase, Player Finder, the page list, Settings.
- Footer of every page: league wire ticker on the left, the next step on the right (Sim / phase buttons).

## Resume state
- (update as work proceeds)
