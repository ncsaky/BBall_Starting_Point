# Sidebar pages layout (branch `sidebar-pages`)

Progress: 7/7 - done, in review on the branch (not merged)

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
- Built and committed on `sidebar-pages`: `gui/card-pages.js` (page list, layout engine, sidebar, next-step dock),
  `gui/card-pages.css`, hooks in `card-board.js` (pages own their cards; the board keeps pop-ups), Settings > Layout
  (Pages / Board), a pages version of the first-run tour, `tests/sidebar_pages.test.cjs`.
- Tested on the pages-preview copy (port 8767): every regular page, preseason (Opening Roster, Set The Roster,
  Preseason Outlook as a page), a full season cycle (playoffs bracket and stats, champion, year-end recap, offseason
  checklist, draft night and summary, free agency, late summer, next preseason), pop-ups (player card, box score,
  trade room, Player Finder, Settings), viewing another team, the tour, the layout switch, 1280-1728 wide screens.
- Browser tests all pass except startup_video (its 188 MB movie is git-ignored, so the worktree lacks it).
- Screenshots: scratchpad `pages/shots/` (headless Chrome script `pages/shots.mjs`).
- Test-save lesson: copying a save's files by hand shares its history database (the JSON names it); use the app's
  export / restore instead.

## Report (2026-11-24, morning)

**TL;DR.** The board is now an app: a sidebar of pages, each page filling the screen with the board's cards laid onto
it (no window frames, same contents, one scale per page so nothing stretches). Pop-ups stay pop-ups. The next step is
always the big button at the bottom right. Settings > Layout switches back to the board. Report with screenshots:
https://claude.ai/artifact/H888JggK8SswRrGQnSk2Hg (private).

Pages: Team (Home, Roster, Development, Team Identity, Schedule), Front Office (Contracts, Trades, Scouting), League
(Standings, Awards), plus a top group that follows the calendar (Opening Roster, Set The Roster, Preseason Outlook,
Two-Way Places, Playoffs, Playoff Stats, Year-End Recap, Offseason Checklist, Draft, Free Agency, required decisions).

Rules: page = rows and columns of cards at their default board sizes, scaled 70-122% as one piece; lists grow to show
more rows; a page's own buttons sit right of its title; sidebar holds team, date, steps chip, Find a player, pages,
Settings; footer holds the league wire ticker and the next step; pop-ups (player and extension cards) float over the
page area; modals blur the page behind; slideshows fill the page area with the sidebar still live; each save remembers
its page; [ and ] step through pages; Cmd+K lists pages; a pages version of the first-run tour.

Also fixed while here: power-ranking ranks 10+ were cut to "1..." (rank column 30 -> 38px).

Known: fantasy draft and staff retention pages not seen in a real save; at 1280 wide pages shrink to ~75-85%; the
Offer Builder still scrolls inside (as on the board); test_gui_concept74 prospect-bar assertion fails on main too
(stale since round 14).
