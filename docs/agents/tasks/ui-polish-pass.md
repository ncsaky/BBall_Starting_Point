# UI-POLISH-PASS: from cards to full pages, one clear path through the game, one consistent style

_Owner: a Fable 5.2 session started by the user (2026-11-25), in its own worktree. Coordinator: Claude (main chat)._

Progress: 8/9 - Stage C, checkpoint 9 published (the Trade Builder in two pages); stopped, waiting for three decisions; the Finder and Market, the rest of Home and the final sweep remain

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
- [x] Stage A: done 2026-11-25, published as one page: https://claude.ai/artifact/5BDfbWFKX68gDLMaKUqKLJ ("Polish Pass Stage A").
      **Waiting on the user's eight decisions** (they save into the page's `decisions` collection; read them with the
      artifact data tool before starting Stage B).
- [x] Stage B: done 2026-11-25, published as one page: https://claude.ai/artifact/T1zGSZJcDDJ5js8ATMqzDc ("Polish Pass
      Stage B"). Built from the user's Stage A answers (all eight as proposed, no notes). **Waiting on four decisions**
      (the page's `decisions` collection): where Stage C starts, landing after an ordinary sim, undecided rookie options
      on opening night, the sounds.
- [ ] Stage C. Built from the user's four Stage B answers (home-first, stay, block, keep: all as proposed).
      - [x] Checkpoint 1 (2026-11-26): Home (in season, preseason, playoffs), Roster, Contracts. Page:
            https://claude.ai/artifact/5KVWHDqgWp3oe2gy5WhTC1 ("Polish Pass Stage C"). **Waiting on three decisions** (the page's `decisions` collection):
            `summer-home` (contracts | roster-small | note), `trades-rows` (more | six), `next-pages`
            (planned | steps | note).
      - [x] Checkpoint 2 (2026-11-26): the sidebar carries the to-do list; four pages with tabs; Trades and summer Home
            rebuilt; welcome text rewritten. Page: https://claude.ai/artifact/TWVA9sPeLM8BA2nz9EZXb5.
      - [x] Checkpoint 3 (2026-11-26): background options as pictures; Standings, Schedule, Development rebuilt;
            Home has standings under the next game and no week strip. Page:
            https://claude.ai/artifact/MEuxkg2VnNosDHY8GG5cES. **Waiting on five decisions.**
      - [x] Checkpoint 4 (2026-11-26): backgrounds rebuilt (treatment C, phase photos, a moving layer); Staff,
            Identity, Profile rebuilt; a music shortlist. Page: https://claude.ai/artifact/J3LFyTZsyd2XSEdJ7dEFXM.
            **Waiting on four decisions**, and a yes in the chat before any music download.
      - [x] Checkpoint 5 (2026-11-26): the last six tabs; music (four CC0 tracks); the staff list scrolls; a
            play-through. Page: https://claude.ai/artifact/Kd86FRvNrWNjY7BvnLiBdZ. **Waiting on four decisions.**
      - [x] Checkpoint 6 (2026-11-26): News and Awards redone; Set The Roster, the offseason checklist, the draft
            room and free agency rebuilt. Page: https://claude.ai/artifact/UjzCSZ8WoXbc3pZxJanq7Q. **Waiting on
            four decisions.**
      - [ ] Next, as the user picks: the pop-ups, draft / playoffs / free agency as Home tabs, more arena photos,
            then step 9 (the final sweep)
            (pattern work: a cheaper model can do it from `docs/UI_STYLE_GUIDE.md` "Full-size pages"), then the step
            screens.

## Stage A report (2026-11-25)

Nothing in `src/` changed. Stage A is the audit and the design.

**What was done**
1. 45 screens captured at 12 points of the game year, from copies of the test saves on a private server (port 8775,
   launch entry `polish-preview`). Not captured: the extension card and the shortcut list (would not open from the
   script), fantasy draft, staff retention, multiplayer (no test save reaches them).
2. Phase map: seven phases, the one button of each, what blocks it, what is open and what is closed.
3. Main progress screen: Home becomes it (year strip, a to-do list with required jobs first, one button that only
   moves time). Mockup with nine phase states.
4. First run: four short screens, then the Preseason Outlook, then Home (today: 9 slides + 11 text cards).
5. Style values: 7 text sizes, 3 weights, 4 corner sizes, about 20 colours, 4 motion timings, 5 glass levels, and a
   sound plan made in the browser (11 draft sounds, playable on the page).
6. Page-by-page list with measurements, and before/after mockups for Home, Roster and Trades.

**Measurements (regular-season save, 1512 x 900; share of page covered by cards / share of text under 11px)**
Home 59% / 86%, Roster 52% / 23%, Trades 43% / 72%, Contracts 57% / 19%, Schedule 94% / 8%, Standings 73% / 1%,
Development 62% / 84%, Team Identity 57% / 28%, Scouting 61% / 71%, Awards 42% / 3%, Two-Way Places 86% / 15%.
Stylesheets today: 24 files, 28,116 lines, 86 text sizes, 21 weights, 44 corner sizes, 1,340 colour values, 60 motion
timings, 4,014 `!important`.

**Findings worth keeping**
- A new save starts on Oct 20 (the day before opening night), in preseason, not in the offseason. Its phase chip reads
  "Step 4 of 4" and the first screen is the keep-or-waive table.
- The footer button means three things (go to another screen, move time, return to a step).
- Home is dead outside the season ("No upcoming game", "No standings yet").
- White or cream fills on glass: trade market header, free-agency cap strip, playoff bracket boxes, the deadline-day
  calendar square, the date strip in the deadline and season-end prompts (text nearly invisible). Black bars in the box
  score. The start screen, first-run guide and command list are still the old grey style.
- Draft night shows three equal buttons; on the path from the offseason checklist the lottery reveal never appeared.
- Rule gaps: minutes, waive/buy out and the trade block have no phase rule; the post-deadline trade block and the
  pending-coach-decision block are enforced only in the browser (engine side is outside this task: for the
  coordinator); the `draft_lottery` phase name is never entered; there is no All-Star break.

**Working files (git-ignored, in this worktree's `output/ui-polish/`)**
`make_stages.py` (builds save copies at each phase; each copy gets its own history file, which a plain file copy
breaks), `shots.mjs` + `scn/*.mjs` (headless screenshots and table scraping), `site/` (the published page:
`src.html` is the source, `index.html` the built file, `shots/`, `faces/`, `img/`).

**Decisions asked of the user**
1. Home becomes the progress screen. 2. What the button does when a job blocks it. 3. First run. 4. Smallest text
(11px floor proposed). 5. Italic (never, proposed). 6. Two tables with the same rows (one table with a picker,
proposed). 7. Sound. 8. Things shown twice.

## Stage B report (2026-11-25)

**What changed, in plain words**
- **Home is the progress screen.** Top: the phase, one line under it, and a seven-step year strip. Left: a to-do list
  (red rows block the clock, yellow is a deadline today, green is done, dashed grey is closed). Beside it: the cards
  that matter in that phase (the season cards while games are on; playoff stats in the playoffs; roster, payroll and
  picks from the lottery to camp). You land on Home when a save loads, when a phase begins and when the game stops by
  itself; an ordinary sim leaves you on the page you were on.
- **One button, bottom right, only moves time.** Label says what happens, small line says to which date; a week, a
  month and the like stand to its left. When a job blocks it the button turns red, carries the job's name and opens the
  job. The "Step N of 4" chip, the Back / Next / Continue step buttons, the deadline-day button and the two pause
  windows (trade deadline, season end) are gone in the pages layout. Step screens open from Home's list and have a
  Home button at their title.
- **First run.** Four short screens drawn from the save (your team, the year, the one button, your pages), then the
  Preseason Outlook, then Home. Skippable, remembered (same key as before), replayable from Settings. The old guide's
  page tips sit behind a small "i" beside those section titles.
- **Sound.** Made in the browser (`gui/sound.js`), on and quiet (40%), clicks off. Settings > Sound: switch, volume,
  clicks. Eleven sounds, each tied to one event.
- **Shared style values.** `gui/tokens.css`, loaded first; the sheet is in `docs/UI_STYLE_GUIDE.md`. Moved onto it in
  all 23 loaded stylesheets: text weights (12 -> 3; the old "medium", 25 places, became semibold), italic (16 -> 0),
  transition timings and easing (17 and 7 -> 4 and 1). The page title, Home's new parts, the footer button and the
  welcome read every value from it. NOT moved: text sizes, colours, corner sizes (cards have fixed layouts; page by
  page in Stage C). The forced-override count is about unchanged.

**Files**
New: `gui/tokens.css`, `gui/progress.js`, `gui/progress.css`, `gui/sound.js`. Changed: `gui/card-pages.js` (Home's
structure and sizing, landing rule, no step buttons, "i" tips), `gui/card-pages.css` (13 dead rules removed, title on
the shared values, pages cross-fade), `gui/app.js` (welcome, sound hooks and settings, stops on Home, no step chip in
the sidebar), `gui/assets-desktop.js` (the footer's buttons come from `GameProgress.dockMarkup()`), `gui/index.html`
(new files, every cache version bumped to `polish-b1`), 23 stylesheets (the weight / italic / transition swap),
`docs/UI_STYLE_GUIDE.md` (token sheet, progress-screen rules), 8 test files (7 updated for the new values, 9 new
tests in `tests/sidebar_pages.test.cjs`).

**Checks**
- Played on copies (port 8775): a brand-new save from the start screen through the welcome, the outlook, a blocking
  job, the season start, two games and a week; a December save simmed to the trade deadline; a deadline-day save
  simmed to the end of the regular season and into the play-in; Home captured at nine points of the year. No page
  errors.
- Every page re-captured after the stylesheet swap and compared with its Stage A picture: about 1% of each changed
  (title, sidebar, footer); nothing moved.
- Browser tests: 48 of 49 files pass. `startup_video.test.cjs` cannot run in this worktree (the start-screen video is
  git-ignored and absent here); it is unrelated to this work.
- Not run: the full Python suite (no engine, save or ratings code touched). Of the Python files that read GUI text,
  `test_gui_concept71` and `test_gui_concept74` each have one old check that fails with and without these changes
  (the Settings "font" check; a prospects-card check); two more error on the same missing video.
- Not exercised (no test save reaches them): fantasy draft (keeps its old controls; the footer falls back to them),
  staff retention, multiplayer, the board layout.

**Known gaps, for Stage C**
- Home's six cards are still the old cards, drawn at 86% scale (about 91% before): 93% of Home's text is under 11px
  (was 86%). Rebuilding them at 13px is Home's page conversion, proposed as the first Stage C page.
- Differences from the Stage A pictures: Standings is beside the minutes (not under the list); the draft board and the
  free-agent market stay on their own screens (not on Home); Home in summer shows roster, payroll and picks.
- Duplicates not yet removed (signals and morale on Team Identity; Two-Way Places as its own page in season).
- The Font row in Settings is a little tight on its last option; white strips and black bars in pop-ups untouched.
- For the coordinator (unchanged from Stage A): trading after the deadline and simming with a coach decision pending
  are stopped only in the browser.

**Working files** (git-ignored, `output/ui-polish/`): `codemod.py` (the stylesheet swap; re-running it finds nothing
left), `scn/home.mjs`, `scn/first.mjs`, `scn/flow.mjs`, `scn/flow2.mjs`, `scn/stops.mjs`, `scn/pages.mjs`,
`scn/measure.mjs`; `siteb/` (the published page).

## Stage C, checkpoint 1 report (2026-11-26)

**What changed, in plain words**
- **A page can now be laid out at real sizes** instead of fixed-size cards shrunk as one picture. A layout in
  `gui/card-pages.js` marked `full: {fits, roomy}` is drawn at scale 1 on any page area between those two sizes (a
  smaller window shrinks the whole page, a much larger one grows it, at most 1.25). Its rows and columns take
  `basis` (a fixed share) or `fill` (what is left); a section that is a picture takes `natural: "fit" | "width"` and
  is enlarged as one piece (CSS zoom) so it keeps its shape; a page with `views` shows one section at a time behind a
  picker at its title. The to-do list is a section of Home's layout (`TODO`). All styling is in the new
  `gui/full-pages.css`, every rule under `.pages-stage.is-full`, every value from `tokens.css`. A page that has not
  been rebuilt takes the old path untouched.
- **Home** (season, preseason): the list with the standings under it, the rotation with the week under it, then the
  next game, signals and morale. 13px rows, 11px bold headings, rows sharing the height (34px for 15 players).
  The next game's header is two lined-up lines; deadline day is a ring and a label, not a cream square; a long job
  name wraps. **Playoffs:** the same without standings and week; the playoff stats table left Home (too wide).
  **Lottery to camp:** unchanged, still the scaled cards (decision asked).
- **Roster**: one table the page's width (42px rows, the same 16 columns), Ratings | Stats behind a picker.
- **Contracts**: the table at 13px, draft assets under it, the payroll chart enlarged 1.57 times in its own shape.

**Measured** (regular-season test save, 1512 x 900; share of text under 11px, before -> after): Home 93% -> 2% (the
sort triangles), Roster 23% -> 0%, Contracts 19% -> 7% (the draft-assets grid's labels). Page area used: Roster 52%
-> 94%, Contracts 57% -> 80%.

**Files**: new `gui/full-pages.css`; `gui/card-pages.js` (full layouts, views, natural sections, re-layout when a
section's contents arrive); `gui/index.html` (new sheet, cache versions `polish-c1`); `docs/UI_STYLE_GUIDE.md`
("Full-size pages"); tests: `tests/sidebar_pages.test.cjs` (3 new), `tests/table_style.test.cjs` (sheet order).

**Checks**: on copies (port 8775): sorting, a minutes change, a sim from Home, a player page and back, the picker,
Home on a new save, on deadline day, in the playoffs, at 1280 x 760 (82%) and 1728 x 1050 (scale 1); every page not
rebuilt captured again and unchanged. A bug found and fixed on the way: the enlarged payroll chart stayed enlarged
on Trades. Browser tests 48 of 49 (the 49th needs the absent start-screen video). Full Python suite not run (no
engine or save code touched).

**Known gaps**
- Windows under 1512 x 900 shrink the page (1280 x 760: 82%, rows about 10.6px).
- Long opponent names end in an ellipsis (as before). Draft-assets labels are still about 10px.
- Two-Way Places is still its own page in season; signals and morale are still also on Team Identity.
- Between playoff rounds Next Opponent has no game to show (pre-existing; now one plain line).
- Trades: the league block shows 6 rows a group by design (`leagueBlockGroups` in `assets-desktop.js`); filling the
  page means showing more, which is a content change: asked.

**Working files** (git-ignored, `output/ui-polish/`): `scn/page.mjs` (one page, optional picker option),
`scn/tour.mjs` (Contracts first, then every page), `sitec/` (the published page).

## Stage C, checkpoint 2 report (2026-11-26)

**The user's Stage C answers** (page 1's `decisions`): summer Home = contracts, payroll and picks; league targets
fill the height; then the other pages in the planned order. Notes, in their words: the to-do list makes more sense in
the sidebar "along with only a few pages"; "a lot of the current pages should be more like tabs on a page from a
shorter selection of pages, but we can have more tabs"; "I don't like the way you force a lot of cards together on
the pages" (these are "some of my biggest current issues"); the backgrounds are "kind of overpowering ... just you
slapping a color filter over a photo ... we need more neutral colors and more accents of the team colors"; and the
welcome text "sounds so much like an AI wrote it".

**What changed**
- **Sidebar** (`card-pages.js`, `progress.css`): the phase and its line, then the to-do list, on every page; four
  pages under it (Home, Team, Front Office, League). 224px wide (was 184).
- **Year bar** (user, mid-turn: "across the main header of the page ... each segment to vary in length depending on
  how long it is ... each segment will only fill as far through it as we are"): a row at the top of every page
  (`.pages-year`, `GameProgress.yearMarkup` / `yearSpans`). Segment lengths are days between the league calendar's
  month-day boundaries; the current segment (from the save's phase) fills by today's date within them.
- **Tabs**: every old sidebar page is a tab of one of the four (`GROUPS`; a page's `group`). The sidebar opens a page
  on the tab last used there. Tabs: Home (Today, Schedule); Team (Two-Way Places in season, Roster, Stats,
  Development, Staff, Identity, Profile); Front Office (Contracts, Trades, Draft); League (Standings, News, Awards,
  Playoffs, Playoff Stats). `CardPages.go(id)` opens a tab by id.
- **Fewer things per screen**: Home is the rotation with the week under it, and the next game. Standings, signals and
  morale left Home (Standings tab; Identity tab). Development and Staff, Heat maps and the radars, Standings and the
  league wire, Trades and the payroll chart no longer share a page.
- **Trades** rebuilt at full size: sixteen league targets a group (was six; `leagueBlockGroupSize`), your block and
  what teams want beside them.
- **Home from the lottery to camp**: contracts, payroll and picks at full size.
- **Welcome text** rewritten as plain labels (team name and "Projected 18th of 30"; "The year"; "To do" with one
  instruction; "Pages" listing the four pages and their tabs).
- Removed: the page-level to-do list and its layout node, the Ratings | Stats picker (they are tabs now).

**Not done**
- The background (the colour filter over the arena photos): not touched. Proposed next: three treatments on two
  arenas for the user to pick from, before changing all thirty.
- Still the older cards inside their tabs (scaled, with empty room beside them): Schedule, Development, Staff,
  Identity, Profile, Draft, Standings, News, Awards, the playoff tabs, Two-Way Places, and every step screen.
- Home's right column is half empty under the next game (six or seven opponent rows).
- Signals and morale are small on the Identity tab. Two-Way Places is still its own tab in season.

**Checks**: every tab captured on the regular-season copy; Home on a new save, in the playoffs, in free agency and in
late summer; the four welcome screens. Browser tests 48 of 49 (the 49th needs the absent video); the page tests were
rewritten for the new structure. Not played end to end again after the restructure (no sim, no step-screen walk).

**Working files**: `scn/home.mjs`, `scn/page.mjs` and `shots.mjs` now open tabs through `CardPages.go`; `sited/` is
the published page.

## Stage C, checkpoint 3 report (2026-11-26)

**The user's checkpoint 2 answers**: the page map is good ("more important to master each of these ... tabs than
... the organization"); later, the draft, the playoffs and free agency should take over Home with a tab of their own
while they are on; backgrounds: natural photos with team colour as accents, and ideas: several pictures per team
(different spots of the arena by page or by phase), slight movement, transitions between places, background music
("free chill beats"); Home's right column: standings, and delete the week strip from Home (a smaller copy of the
Schedule tab); next: backgrounds, then the remaining tabs.

**What changed**
- Home: the week strip is gone; your conference's standings sit under the next game (not in the playoffs).
- Standings, Schedule and Development rebuilt at full size. Done by a Sonnet subagent from a written brief and the
  style guide, reviewed from its pictures; one fix after review (played games' logos kept in colour on Schedule).
- Background options, as pictures only (nothing changed in the game): `output/ui-polish/bg/make.py` makes three
  treatments from the photos already picked and credited in the main checkout's `output/ui-workbench/arena` (read
  only): A natural, B team colour kept (hue-selective saturation), C neutral and darker. Shown behind Home for OKC,
  BOS and DEN, plus Boston's two other photos behind Team and Front Office.

**Waiting on five decisions** (page https://claude.ai/artifact/MEuxkg2VnNosDHY8GG5cES, collection `decisions`):
`bg-treatment` (b | a | c | note), `bg-spots` (by-page | by-phase | one), `bg-motion` (drift-fade | fade | none),
`music` (list | browser | later), `draft-home` (office | team | note).

**Notes for whoever continues**
- Music needs files: the task rule stands (no downloads without the user's yes). The proposal is a list of free
  tracks with licence and size for approval first.
- Movement reverses the style guide's "never anything looping": ask before building (asked).
- Still old cards: Staff, Identity, Profile, Draft, News, Awards, the playoff tabs, Two-Way Places, the step screens.
- Not replayed end to end since the restructure (no sim, no step-screen walk).

## Stage C, checkpoint 4 report (2026-11-26)

**The user's checkpoint 3 answers**: background treatment C (neutral and darker; "very hard to see a difference
between these options"); a different photo by phase; slow drift and cross-fade; bring a list of free music tracks to
approve; the Draft tab stays under Front Office.

**What changed**
- **Backgrounds**: all thirty arenas rebuilt in treatment C; 29 playoff and offseason photos for the 19 teams with
  more than one credited photo (`gui/assets/arenas/*-playoffs.jpg`, `*-offseason.jpg`, `phases.json`, `credits.json`;
  `output/ui-polish/bg/build_all.py`). Charlotte and Cleveland keep their drawn arenas, muted.
- **One moving layer** (`gui/arena.js`, `gui/arena.css`): the picture is an `<img>` on a fixed layer behind the game
  (the look sheets strip background images from every element, and `.dashboard-shell` had a light fill that had to
  go transparent). Slow drift, a lean per sidebar page, a cross-fade on a change of picture; Settings > Look >
  Background movement; off under reduced motion. Picture addresses carry a version so browsers fetch rebuilt ones.
- **Staff, Identity, Profile** rebuilt (Sonnet subagent, reviewed). A card may now pin its own size for `natural`
  sections (`size: [w, h]`), because the board's default window sizes change with the viewport.
- New tokens: `--gm-motion-scene` 1.2s, `--gm-motion-drift` 90s (the arena layer only).

**Music (nothing downloaded)**: a subagent read each track's own OpenGameArt page. Shortlist: "Chill lofi inspired
[loop edit]" (omfgdude / qubodup, CC0, ogg 2.4 MB), "lofi hip hop" (omfgdude, CC0, ogg 1.5 MB), "Sleepy Head"
(Tsorthan Grove, CC0, flac 32.1 MB), "A Day In, Night Out" loop (Tsorthan Grove, CC0, flac 12.3 MB), "Diminishing
Returns" (tcarisland, CC BY 4.0, mp3 7.7 MB), "Downtempo" (biggius, CC BY 4.0, mp3 2.5 MB). Licences are the
uploaders' own statements; nobody listened to them. Downloading needs the user's yes in the chat. `ffmpeg` is
installed for converting the FLACs.

**Waiting on four decisions** (page https://claude.ai/artifact/J3LFyTZsyd2XSEdJ7dEFXM, collection `decisions`):
`music-tracks` (cc0 | all | none), `staff-list` (pages | scroll | as-is), `bg-dark` (good | lighter | note), `next`
(tabs | home-phases | steps).

**Known gaps**
- The drift was not watched moving (captures emulate reduced motion): the layer, the switch and the phase pictures
  were checked from the page's state and still pictures.
- Available staff shows the rows that fit (19 of about 30); the rest need the role picker. Asked.
- Some arenas are close to black (Cleveland, a few offseason photos). Asked.
- Still old cards: Draft, News, Awards, the playoff tabs, Two-Way Places, the step screens.
- Not replayed end to end since the restructure.

## Music added (2026-11-26, after checkpoint 4)

The user approved downloading the four public-domain tracks in the chat ("Yes, those four"). The four checkpoint 4
decisions on the page were still unanswered at that point (`staff-list`, `bg-dark`, `next`; `music-tracks` is
settled by the chat answer).

- Downloaded from OpenGameArt after re-reading each track's page (each states CC0): `chilllofir-loop.ogg`,
  `lofihiphop.ogg`, `sleepy_head_0.flac`, `a_day_in_night_out_loop.flac` (48 MB; originals kept, git-ignored, in
  `output/ui-polish/music/raw/`, with the saved pages in `music/pages/`).
- Converted with ffmpeg to 128 kbps MP3, loudness levelled to -18 LUFS: `gui/assets/music/*.mp3` (8.9 MB in all)
  and `tracks.json` (title, artist, licence, source, what was changed).
- `gui/music.js`: off by default; shuffled order; each track fades in and out; a track under two minutes plays twice;
  waits for a click; pauses while the tab is hidden. Settings > Sound: Music (with the track playing and Next
  track), Music volume. The tracks are listed in Settings > Credits > Photo and music credits.
- Checked in the preview: off by default, switching on fetches and plays a track, Next track changes it, switching
  off pauses. Nobody has listened to the tracks in the game: the level and the fades are untested by ear.
- Tests: `tests/music.test.cjs` (3), `tests/photo_credits.test.cjs` updated for the renamed list. Browser tests 50
  of 51 (the 51st needs the absent start-screen video).

## Stage C, checkpoint 5 report (2026-11-26)

**The user's checkpoint 4 answers**: all six music tracks (on the page; the chat yes covered the four CC0 ones, so
the two CC BY ones still need a yes in the chat); the available staff list scrolls; the arenas' darkness is good; next:
the last five tabs.

**What changed**
- Every tab is now a `full` layout (17 of 17). This round, by two Sonnet subagents from written briefs, reviewed from
  their pictures: Draft (the prospect board at page width, whole rows between 34 and 42px, its sixty rows still
  scrolling inside it as before; draft assets under it), News and Awards (enlarged whole with `natural`; both leave
  empty room), Playoff Stats (two tables at real sizes), Playoffs (the bracket enlarged whole; white boxes replaced
  by glass; the user's series marked through `data-yours`, set in `layoutFull`), Two-Way Places and Opening Roster
  (the same card: real sizes, all rows fit; Details and Rules open as small glass pop-ups).
- Available staff scrolls (user's pick), headings pinned.
- Roster's columns rebalanced after the sidebar widened (role names were cut); a role cell never clips.

**Played through after the restructure** (copies, port 8775): a brand-new Milwaukee save from the start screen (13 s
to build; welcome, Outlook, Home with two red rookie-option jobs and the blocked button); every to-do job on four
saves opens its screen and step screens have their Home button; a sim from Home, a week from Roster (stays), the
year bar and the record move; Front Office reopens on its last tab. Not replayed: the deadline and season-end stops,
the draft itself, a signing. The earlier "new save will not create" scare was the capture script clicking before the
button was enabled.

**Waiting on four decisions** (page https://claude.ai/artifact/Kd86FRvNrWNjY7BvnLiBdZ, collection `decisions`):
`music-two` (yes | no; also needs a chat yes), `news` (feed | two | as-is), `awards` (more-rows | bigger | as-is),
`next` (steps | home-phases | photos).

**Known gaps**: the step screens other than Opening Roster are still scaled cards; News and Awards are thin; names
are cut on Playoff Stats; the bracket uses the top 40% of its page; the cutdown and Sign Players screens (same card as
Opening Roster) were not reachable; nobody has listened to the music or watched the drift.

## Two more tracks (2026-11-26, after checkpoint 5)

The user said yes in the chat ("Yes, add both"). Both pages were re-read first (each states CC-BY 4.0; authors
tcarisland and biggius): `diminishingreturnsinstr_0.mp3` (7.7 MB) and `downtempo_0.mp3` (2.5 MB), re-encoded to
128 kbps MP3 and levelled like the others (`gui/assets/music/diminishing-returns.mp3`, `downtempo.mp3`; the folder is
15 MB with six tracks). `tracks.json` carries the title, artist, source, licence link and what was changed for each,
and the game's credits list shows them, which is what CC BY 4.0 asks for. tcarisland's page asks, without requiring
it, to be told when his music is used (a contact form on tcarisland.no): left to the user. The checkpoint 5 page's
decisions were still unanswered.

## Stage C, checkpoint 6 report (2026-11-26)

**The user's checkpoint 5 answers**: News: "I like the scrollable social media as a concept ... you can reorganize as
much as you like ... The objective is to keep the user engaged and informed on the season they are in"; Awards: more
rows, "feel free to get experimental"; the two CC BY tracks: yes (done); next: the step screens.

**What changed**
- **News** (done on the main model): the feed keeps its posts, drawn two across and scrolling; `gui/news-page.js`
  adds beside it a list of every headline (date, kind, team logos, one line) with filters (All, Your team, Trades,
  Contracts, Staff, Other as present). A headline scrolls the feed to its post; a filter narrows both. Built from
  `state.home.league_events` through `normalizeLeagueEvent`: no new data. Styles in `gui/news-awards.css`.
- **Awards**: ten candidates a race on a page (four in a board window: `seasonAwardsCard`), cards pinned taller.
- **Step screens** (two Sonnet subagents, reviewed from pictures): Set The Roster; the offseason checklist with the
  Offer Builder (`.fa-builder`); the draft room's three arrangements (lottery, draft night, results); the free-agent
  market with its builder and signing wire. All `full` layouts in `card-pages.js`, CSS appended to `full-pages.css`.
  `layoutFull`'s whole-row fitting now also covers the draft board, the draft summary and the market.
- White fills made glass: the free-agency cap strip, the offer salary field, Set The Roster's room boxes, the
  lottery's "moved up" boxes.

**Judgment calls the helpers made, reported to the user**: the checklist's tables are reordered by CSS (the user's
own decisions first, "Around the league" last); the market's ask-change marks are one triangle and the amount.

**Findings for the coordinator (outside this task)**: neither lottery test save opens on the lottery, and a copy
advanced from the Finals went straight to draft night: the lottery phase is not entered (also a Stage A finding). The
lottery card was checked by forcing it to draw.

**Waiting on four decisions** (page https://claude.ai/artifact/UjzCSZ8WoXbc3pZxJanq7Q, collection `decisions`):
`news-ok` (good | change), `awards-ok` (good | change), `checklist-order` (mine-first | as-before), `next`
(popups | home-phases | sweep | photos).

**Known gaps**: pop-ups untouched (trade room, box score, player finder, staff talks); the start screen; draft /
playoffs / free agency as Home tabs; names cut on the free-agent market; the Offer Builder's rules text still stands
in the open; fantasy draft, staff retention, cutdown and Sign Players screens unreachable in the test saves; the
music and the background drift still untried by a person. `saves/st_draft_done.json` (a test copy) has a new
modified time from being loaded during the helper's lottery hunt; it still opens on the finished draft.

## Stage C, checkpoint 7 report (2026-11-26)

**The user's answers to checkpoint 6**: News good. Awards: "the table underneath the leading person ... doesn't have
field headers. It should have field headers and the cell with the leader and their headshot and the award image has
sharp corners and it's a sharp box. It should probably not look like that. Other than that it looks pretty good."
Checklist order stays (own decisions first). Next: the pop-ups.

**What changed**
- **Awards**: a headings row over each race's table on a page (`seasonAwardColumns` in `app.js`: #, Player, Team,
  the award's stats, Change, on the chasers' own column grid); the leader band has the card radius and a hairline;
  the leader's change in rank now sits under its "Change" label (old rules put the labels on grid row 5, so it fell
  to row 1). Cards pinned at 340 by 500. Styles in `gui/news-awards.css`.
- **Trade pop-ups** (Sonnet subagent, reviewed from pictures): Trade Builder (deal, pick, Value and Team identity
  views), Trade Finder, Incoming Offers, Trade Market. All in the new `gui/popups.css`, every rule under `#modalRoot`,
  token values only; test `tests/popups_style.test.cjs`. The Market's white strip and black headings are gone and its
  table sizes its columns to fit so names stay on one line; the Builder's payroll chart is enlarged whole (1.3, or
  1.1 on a short window).
- **Other pop-ups** (second Sonnet subagent): box score (both views), Player Finder, staff talks, League Leaders,
  in the new `gui/popups-game.css`; test `tests/popups_game_style.test.cjs`.
- **Changed after review** (main model): box score comparison bars keep each team's own colour, lifted to a minimum
  lightness (`oklch(from ... max(l, .66) c h)`, with a `color-mix` fallback) instead of grey and accent blue for
  every game; on Incoming Offers, Accept Trade is the one frosted pill and Decline is plain text (they had come out
  as two near-identical pills).

**Checked**: browser tests, 53 of 54 files pass (the start-video one cannot here). Settings and the Trades tab are
pixel-identical with and without `popups.css`. A pick's "Details" panel was opened and looked at. No button that
changes a save was pressed (Ask, Propose, Accept, Decline, Shop).

**Waiting on four decisions** (page https://claude.ai/artifact/SeJrGwfx6mz5vyzR4kMVpA, collection `decisions`):
`awards-ok` (good | change), `popups-ok` (good | change), `accept-button` (frosted | blue), `next`
(home-phases | rest-popups | sweep | photos).

**Known gaps**: the contract extension window and the player card are built outside `#modalRoot`, so neither
pop-up sheet reaches them; at 1280 by 760 the Builder's payroll table is cut at the bottom, the partner picker
overlaps "gives" and long names are cut (all there before; the first slightly worse with the larger chart);
League Leaders is the finder's table, not Player, Team, stat (needs a change to how it is built); the Value tab's
"Roster value" bar is coloured inline; the Market's "Decision by" shows ISO dates; `popups.css` loads early in
`index.html`, so its rules carry extra specificity. Still open from before: Home phase tabs, the start screen, more
arena photos, the final sweep, and nobody has listened to the music or watched the background move.

## Stage C, checkpoint 8 report (2026-11-26)

**The user's answers to checkpoint 7** (their words where quoted): Accept Trade stays a frosted pill. Awards good
"other than the fact that there's names being shortened in their fields". Next: draft, playoffs and free agency as
Home tabs. On the pop-ups, a note that sets the direction for two screens:
- Home: "I don't like that the homepage just shows a couple tables. It should show stuff that would be most
  engaging to a player like the trade market, any ongoing trade rumors, standings, things going against expectation,
  league leaders, winners, the state of your team, injuries, signings, whatever deadlines are coming up".
- Trade room: "too much stuff is spread out"; the Market "isn't centered ... not full"; the heat maps should "fade
  from one to the other instead of having them one on top of the other"; the pop-ups do not "show enough of the
  change that happens after a trade like for example the four factors or the overall, the morale"; so "consolidate
  all of those onto one page and then expand the trade asset selection page": one page "where you pick what assets
  go and you see legality", the next "what would that trade actually entail for your team".

**What changed**
- **Home › Today is a front page** (`gui/home-front.js`, `gui/home-front.css`, card id `front`, panel
  `.season-front-panel` in `seasonCommandDashboardMarkup`): a strip for your team (last result, next game, last
  five, the four moods, who is out), then three columns: headlines and the latest day's scores; your conference
  with "Against expectation"; trade talk (offers waiting, the Market's shopped players, days to the deadline) and
  the PTS / REB / AST leaders. Every line opens what it summarises. Lists show whole rows only (rows that do not fit
  get a 0-height implicit grid row). Before the season and in the playoffs the game loads no standings, scores or
  leaders for a phase screen, so the middle column lists the games ahead or is dropped.
- **Display-only server additions** (`app_actions.py`): `dashboard_trends_payload` returns `roster_ranks` (every
  team's `team_identity_report` overall and rank, already computed there); the summary leaders' rows carry
  `headshot_url`.
- **Home's tabs**: Today, Minutes (the old Home: the rotation with the next opponent; only while games are played),
  Schedule. The draft room, the offseason checklist, free agency and the playoff bracket are Home tabs listed first
  while they are on (`phaseHome`), and Home lands on them (`homeId()`); they are no longer step screens. Pages take
  an optional `when`.
- **Awards**: cards drawn at 396 by 590 so no name is cut (ten of 27 were); the leader's content is centred in its
  band.

**Checked**: browser tests, 54 of 55 files (new `tests/home_front.test.cjs`; `sidebar_pages` and `tables_icons`
updated; the start-video file cannot pass here). Clicked on Home: a score (box score opened), the standings
heading (tab opened), a leader (player card opened). Landings checked on the playoffs, draft, free agency,
re-signing, camp and preseason saves. `tests.test_gui_concept74` has one failure
(`test_rating_and_scouting_bars_use_solid_sampled_color`) that is on the branch without this round's change.

**Trade room: what the code and engine reading found** (plan on the page, nothing built)
- The Builder already has two views (`state.tradeView` "pick" / "deal") and three lower tabs
  (`state.tradeInsightPage` 0 payroll, 1 value, 3 identity). The heat maps are inline SVG built in the browser
  (`trade-projection.js`), before and after as separate sections.
- The engine can compute for a hypothetical roster, with display-only code in `app_actions.py`:
  `team_identity_report` (overall, offence, defence, depth and the other metrics, with ranks) on a copied canonical;
  `spatial.team_spatial_profile` with a roster and minutes (real team heat maps); `trade_roster.roster_projection`
  (rotation strength, minutes, forced cuts); `trade_tax.luxury_tax_bill` / `tax_saved`.
- It cannot: forecast four factors for a roster (Profile's are season results), or project morale or chemistry
  after a trade (morale moves only after games and press answers). Both would be engine work for the coordinator.

**From the coordinator (main 00f5c384, to fold in when those screens come up; data arrives with the next merge)**:
the lottery card's "Four picks drawn" / "14 → 1" text is wrong when `lottery.format` is "3-2-1" (16 picks drawn);
hide the reveal's "jumped into the top four" notice for 3-2-1; 16 rows must fit the lottery card; the year-end
slide's "of 14" should use `lottery_teams`; the player page's season strip needs a playoff line
(`career_seasons[].playoffs`). Details: `docs/agents/tasks/lottery-playoff-stats.md` on main.

**Waiting on four decisions** (page https://claude.ai/artifact/PesnDwmQszkPJQZAicJhb3, collection `decisions`):
`home-ok` (good | change), `phase-tabs` (good | change), `trade-plan` (ratings | ratings-only | wait), `next`
(trade-room | home-more | rest-popups | sweep).

**Known gaps**: Home is thinner before the season and in the playoffs (no league data loaded there); the offseason
Today tab is unchanged (contracts, payroll, picks); the market request was not timed on a slow machine; the trade
room rebuild, the extension window and player card, the start screen, more arena photos and the final sweep
remain; nobody has listened to the music or watched the background move.

## Stage C, checkpoint 9 report (2026-11-26)

**The user's answers to checkpoint 8**: the new Home good; phase tabs good; trade plan = build page 2 with the team
ratings and ask the coordinator for real forecasts of four factors and morale; next = rebuild the trade room in two
pages.

**What changed**
- **The Builder is two pages** (`renderTradeBuilder` in `app.js`; `state.tradeView` keeps its values: "pick" is
  page 1, "deal" page 2; a `.tr-steps` bar switches). Page 1, "The deal" (`.tr-page-deal`): for two teams both
  asset lists side by side (`assetColumn` twice, the partner picker at the head of the partner's list:
  `tradePartnerPicker`), then a dock with each side's tiles and salary check (`tradeDealSide(..., {plain})`) and the
  answer with Ask; three or more teams keep one list at a time with the strip. Page 2, "What it does"
  (`tradeEffectPage`, `.tr-page-effect`): a team switch, then team ratings before and after with league ranks and
  "Who plays" (`tradeEffectRatings`), the heat maps as one pair that fades (`.trade-identity-fade`, switch Before /
  Fade / After in `state.tradeFade`), the value bars, and that team's payroll (`tradePayrollAnimation(participants,
  only)`). The lower tabs are gone; `state.tradeInsightPage` is no longer read by the Builder.
- **New display-only action `trade_team_impact`** (`trade_team_impact_payload` in `app_actions.py`): runs
  `team_identity_report` on the league and on a copy with each traded player's `team_id` swapped (the copy drops the
  `_`-prefixed caches, which index the real rosters), and returns each involved team's metrics and ranks before and
  after plus `team_rotation_projection` minutes before and after. Nothing is saved. About 3.6 s for a four-player
  deal on the test save, 0.4 s with no moves. Loaded when page 2 opens (`loadTradeImpact`, keyed on the moves).
- Styles appended to `gui/popups.css`; tests in `tests/trade_two_pages.test.cjs`; `tests/popups_style.test.cjs`
  now skips `@keyframes` steps when it collects selectors.
- The asset lists scroll, as before: `glass-clear.css` hides the pager on purpose ("Scrolling is fine for the asset
  list (round 8)"), so `fitTradeAssetPages` must not be called on render (it would hide rows with no way to reach
  them; tried and reverted this round).

**Checked in the game** (copies only): ticked two players a side; opened page 2; switched to the partner; held the
maps on Before and After; went back (selection kept); on a throwaway copy pressed Ask (answer drawn) and added a
third team. Accept and Propose were not pressed. Both pages captured at 1512 by 900 and 1280 by 760. Browser tests:
55 of 56 files.

**Engine request sent to the coordinator** (the user's choice): a roster-based four-factors projection and a morale
effect or projection for trades. The coordinator put it up as a task card for the user ("Trade forecasts: four
factors and morale for a proposed deal"; planned functions `project_four_factors(canonical, save, team_id, roster)`
and `project_trade_morale(canonical, save, proposal)`) and will send the function names and shapes when done. Until
then page 2 shows neither.

**Waiting on three decisions** (page https://claude.ai/artifact/FE3fnTECUK7jUyicZbXUAf, collection `decisions`): `deal-page`
(good | change), `effect-page` (good | change), `next` (trade-rest | home-more | rest-popups | sweep).

**Known gaps**: the Finder and the Market are unchanged (the user: the Market "isn't centered ... not full"); the
heat maps are still built in the browser from `trade-projection.js` minutes, not the coach's projection
(`spatial.team_spatial_profile` could replace them); at 1280 by 760 the dock's contract column is cut and page 2's
left and middle columns scroll; `trade_team_impact_payload` has no Python unit test; speed not measured on a slow
machine. Still open from before: Home before the season and in the playoffs, the offseason Home, the extension
window and player card, the start screen, more arena photos, the coordinator's lottery and playoff-line items, the
final sweep.
