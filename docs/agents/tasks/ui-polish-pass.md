# UI-POLISH-PASS: from cards to full pages, one clear path through the game, one consistent style

_Owner: a Fable 5.2 session started by the user (2026-11-25), in its own worktree. Coordinator: Claude (main chat)._

Progress: 0/9 - not started

## Why (the user's words, 2026-11-25)
1. "The card content is literally just removed from their cards and pasted exactly the same as they were onto the
   screen. This is lazy. I don't want to change the content being shown, but it all probably needs to be rescaled and
   adjusted to fit the new screens."
2. "Pages and screens and information and actions are not clearly or logically defined or organized. The main thing is
   there should always be one main screen for making progress, so it is simple to always know what the next thing to do
   is. This means every action in our game needs to have a phase under which it can/must be completed. On new save
   startup we start with no tutorial and the first job is not clear what the user should be doing."
3. "There are many small UI/UX tweaks still in terms of borders colors, sizes, indenting, font bold, italics, font
   color, font styles, animation transitions, alignments, hell even sounds in the game don't exist yet. The ethos is
   unity in styling across the game in all the ways we can control."
4. New pages and features to show off the engine come LATER. The priority now is that the game stops feeling
   unpolished.

Summary of intent: the cards established great content. The job now is turning them into full-screen pages that use
the space well, giving the game one obvious path forward, and making every surface share one style system.

## Read first
- `AGENTS.md` (section 2 rules 4 and 12, section 3), `CLAUDE.md`.
- `docs/UI_STYLE_GUIDE.md`: the user's distilled taste from 14 rounds. It wins over older docs. Its "Preserve" and
  "Never do" sections are binding.
- `docs/UI_INTERACTION_GUIDE.md`, `docs/gui_architecture.md`, `docs/agents/tasks/playtest-notes-2026-11-22.md`.
- References in `docs/ui-references/` (JFresh's player cards are the main style reference).
- Recent GUI history: `git log -- src/nba_gm_data/gui` (sidebar pages, phase screens, the player opens as a page).

## Standing UI rules (from the user; not all are written in the repo)
- **Less text.** No kicker lines, no captions repeating a header, at most one short subtext. Graphics carry meaning.
- **Contrast.** Check every text, button, hover and control against its real background. No grey on grey, no black on a
  white fill.
- **Tables.** Side-by-side tables line up exactly. Column order Player, Team, then stats. Every table sorts (small white
  triangle by the sorted heading, no column shading). Headshots bottom-aligned, filling the row height.
- **Don't change what content is shown.** Rescale, reflow and reorganise it for full pages; don't drop or invent
  information. If something seems worth cutting, list it for the user instead.
- **What the user sees must match what the engine uses.** No display-only numbers.
- **Test on copies, never in the user's game** (port 8766, main checkout). Run your own preview server from your
  worktree on a free port, for example 8775, with `--save-dir` pointing at your own copy of the test saves in
  `/Users/noahtyler/Developer/BBall_data/BBall_Starting_Point/output/ui-workbench/gui_saves` (and `pages_saves`, which
  includes a league simmed through a full season for playoff, draft and free-agency pages). Copy them; never edit the
  originals.
- **Light testing for UI work:** check it in the game (screenshots), then run the browser tests
  (`scripts/run_tests_parallel.py --js --workers 2`). No full Python suite unless you touch Python engine code.
  Bump cache versions in `index.html` when you change CSS or JS (the helper is
  `output/ui-workbench/bump.sh` in the main checkout).
- Useful helpers in the main checkout's `output/ui-workbench/`: `pages/shots.mjs` (headless screenshots of every page),
  `audit.js` (`__check()`, contrast and white-surface checker).

## Plan (three stages; stop at each checkpoint for the user)

### Stage A: audit and design plan (checkpoint: the user approves before any building)
1. **Screenshot every page and state** in the test saves: new save start, preseason, regular season, trade deadline,
   playoffs, lottery and draft, re-signing, free agency, training camp; plus player, team, trade, league and settings
   pages and every pop-up.
2. **Phase map.** List every action in the game (sim, set minutes, trades, signings, extensions, draft picks, staff,
   scouting, settings and so on) and the phase where it can or must be done. Mark the required ones. The game already
   has phases (`dashboardPhaseKind`, `applyPhaseRouting` and `phaseCommands` in `gui/app.js`; the save's `phase`).
   Build on them.
3. **The main progress screen.** Design one home screen that always shows what to do next and the one primary action
   ("Continue": sim to the next event, or the required decision of this phase), with this phase's optional actions
   beside it. Show how each phase changes it.
4. **First run.** Design what a brand-new save shows: a short first-run guide that leads into the first real decision.
   It should be skippable and remember that it was seen. Follow the less-text rule; it can be the existing slideshow
   style.
5. **Style system.** Write the design tokens every surface will share: type scale (sizes, weights, when bold, when
   italic, never italic?), text colours, borders and hairlines, corner radii, spacing and indent steps, glass levels,
   motion (durations, easing, which transitions), and a sound plan. Sound plan: what plays when, synthesized in the
   browser (Web Audio) or from files, volume and mute settings, and off or on by default. No sound files are
   downloaded without the coordinator asking the user. Base it on what already exists (`jfresh.css`, `glass.css`,
   `interface.css` and the rest). The aim is one source of truth, not a new look.
6. **Page-by-page conversion list.** For each page now built from pasted card content, say how it should use the full
   screen: rescaled type and graphics, layout, what sits above the fold. Show two or three of the worst ones as
   before/after mockups.

Publish Stage A as one visual page (an Artifact) with the screenshots, the phase map, mockups of the progress screen
and first run, and the token sheet. End with a short list of decisions the user must make. Then stop.

### Stage B: the system and the path (checkpoint after)
7. Put the tokens in one stylesheet and move existing styles onto them, so every page reads from the same values.
   Delete duplicate and dead rules as you go. Build the main progress screen, the phase rules for actions, and the first
   run. Add sounds only as approved in Stage A, behind a mute setting. Show the user screenshots and a short clip or
   step list of a new save's first ten minutes.

### Stage C: the pages (checkpoint after every few pages)
8. Convert pages one at a time from the Stage A list, most-used first. Before and after screenshots for each, with the
   browser tests passing.
9. Final consistency sweep with `audit.js`, plus the screenshots of every page.

## Boundaries
- May touch: `src/nba_gm_data/gui/`, display-only parts of `app_actions.py` / `app_server.py` (data the pages read;
  no game rules), GUI tests (`tests/*.cjs` and GUI test modules), `docs/UI_STYLE_GUIDE.md` (add the token sheet),
  this file.
- Not: the engine (`sim.py`, `stage2/`, `box_rates.py` and so on), `save.py`, `health.py` and the season loop (another
  session is working there on sim speed), ratings, `docs/agents/BOARD.md`.
- Commit on your branch at each checkpoint, not pushed. The coordinator merges with the user's OK.
- Keep this file's Progress line and resume state current; reread it after any context compaction.

## Resume state
- [ ] Stage A
- [ ] Stage B
- [ ] Stage C
