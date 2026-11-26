# UI style guide

Distilled from the user's taste deck: round 1 (2026-11-23 night, 49 cards), round 2 (2026-11-23 day, 22 priority questions plus references) and round 3 (2026-11-23 evening, 19 questions on the five batches) and round 4 (2026-11-23 late, 19 questions on the glass look) and round 5 (2026-11-24, 20 questions on the clear glass). The answers live in the deck artifact's `answers` collection; round 2 ids start with `q2-`. Also draws on the playtest notes in `docs/agents/tasks/playtest-notes-2026-11-22.md`. Every agent doing GUI work follows this. When a rule here conflicts with older docs, this file wins. Where round 2 changed a round 1 rule, the rule below already says the new thing.

## What the user wants overall

- A league with its own look: crisp headshots, colour used on purpose, graphs and pictures, not just tables.
- Minimal text. Graphics carry the meaning. No kicker lines, no captions repeating the header, one short subtext at most. Instructions like "Build a deal, then ask" are clutter: cut them.
- Clean, consistent and polished. Small gaps, double borders, uneven borders and off-centre headers are noticed and disliked strongly.
- "Clean but boring" is not done. A window that is only a plain table needs a graphic or a takeaway. Equally, a window that is mostly empty space is "too bare bones".
- Narrative matters: the preseason outlook (power rankings, continuity) is the favourite part of the game.

## References (what to borrow)

- **JFresh's NHL GM game player cards** (the best style reference): a frosted-glass card over a blurred, team-tinted background; white text; thin dividers; bold section titles; a big overall number with a coloured underline; each attribute value with a small coloured mark beside it. Borrow the background, the colour, the organisation and the polish, not his exact fonts or bubbles. Screenshots: `docs/ui-references/jfresh-player-card-full.webp` (the whole card) and `jfresh-player-card-top-half.webp` (the same layout, cropped).
  - **The background behind the glass is a blurred arena, not a flat colour** (user, 2026-11-24; their top complaint while playing). Behind his card you can make out championship banners, part of a logo and brown wood. It is the team's main colour overall, but real shapes and light show through the blur, so the transparency is noticeable. Each team's should be at least slightly its own (its colours, logo and banners). It must look like a real place: a generated colour glow read as "AI" in round 9.
    - **In the game since 2026-11-24:** the user picked one picture per team (28 in the photo tint, Cleveland in the game look; Charlotte has no photo and shows the built arena). Files and credits: `gui/assets/arenas/`; tools: `output/ui-workbench/arena/make_final.py`. Over an arena the page glass blurs 7px, not 28px.
    - **One treatment for every arena** (user, 2026-11-24): arenas must not differ much from one another. Same blur, same strong team-colour grade, same flattened colour, so it reads as one game and not one camera roll.
    - **Game-like, not photoreal** (user, 2026-11-24): JFresh's picture shows real things such as championship banners but looks like a video game, not a real-life photo. There will probably be a couple of options per arena photo to choose from.
- **Taylor Wyman / Taylor Metrics** (the best graph reference): graphs picked to tell a story. Examples the user likes:
  - stacked-dot distribution columns: one column per season, every player a dot at his rating height, dots that tie sit side by side so the column takes the league's shape, and a dotted line tracking one player across seasons (his Giannis "finishing talent" graph);
  - his shot chart: zones shaded by above or below league average (blue to red), hexagons sized by attempts, a small labelled box per zone ("+35.9% (8)"), a colour legend, and a small zone table underneath. This is the polished version of our heat maps;
  - the Wyman diagram (team fit as shapes filling a box) is admired but not something to copy.
- **Shams Charania / ESPN news graphics** for big news (trades, signings, injuries): one large player photo with a bold, condensed caps banner over the bottom ("DEVELOPING STORY"), one line under it. An eye-grab in one glance.
- **Apple Sports**: clean and polished.
- **Anti-reference: Basketball GM.** Clicking between plain tables, a player page that is a scroll of tables, no players or game feel. Never ship anything that looks like it.

## The look: glass (round 3)
- **JFresh look (merged 2026-11-24, `gui/jfresh.css`, loaded last; styling only):** the board is the team colour muted
  the way JFresh's teal / red are, with soft same-colour depth and dark edges; cards and pop-ups a faint frosted lift with
  one hairline edge and 16px corners; tables with no fills or stripes (bold white headers over one hairline, hairlines
  between rows; this replaces the alternating-shading rule); SF system font, bold labels with regular values; primary
  buttons and the chosen long-pill option are frosted light pills with bold white text (not solid blue).
- **Round 11: the board is the team's main colour** (toned down) with a dark vignette at the edges (still never a
  two-colour gradient). Swap picks show only their team logos, no arrow. Verify visual claims on screen (a marker
  colour), not only in computed styles: the header-edge fix was "applied" for two rounds but clipped.
- **Round 10:** a team is always its logo with its abbreviation (never the abbreviation alone). Header facts are set
  exactly like the rows beside them (same font, size, colour, row spacing). Settings' long pills are the model for
  every long pill. Optional extras (pick conditions) open in a pop-up when they become relevant, not as a standing bar.
  Bars compare like with like: single assets against the largest single asset, totals on their own scale.
- **Round 9: the board is a flat colour** (no team-colour glow anywhere; it read as "AI"). JFresh puts cards on a plain background.
- **Round 8: much more see-through** (back to the JFresh reference): windows about 20% tint, title bars about 12%, pop-ups and slides about 30%. The board's colour shows through; text stays readable through the blur.
- **JFresh-style glass, game-wide** (`gui/glass.css`): windows and pop-ups are frosted, slightly see-through panels with rounded corners and depth; title bars and the top bar are dark glass tinted with the user's team colour, with white text; the board behind is lit by soft team-colour light. Content stays light frosted with near-black text so dense tables read easily.
- **Pop-ups are glass too:** dark tinted glass frames with team-colour light; every chart, table and tile inside sits on a light frosted card. Text turns white only where it sits directly on the frame.
- **Content is glass too (round 4, said on six cards):** a white table or chart sitting on the glass is not the look. Tables, charts and tiles are themselves translucent, tinted surfaces with the team light showing through. The frame is the lighter one (more colour through). Contrast still rules: every colour is re-checked on the real glass.
- **One look only (round 5):** the clear glass. The light Frosted option is gone.
- **Font:** Helvetica Neue by default (round 5 pick), with a Settings choice to switch fonts.
- **No gradients on windows:** flat tinted glass; a gradient across a window "feels too AI". The board behind keeps its soft team light.
- **The player card ratings page is the reference** (round 5: "take this style to the rest of the game"): its spacing, bar widths, borders and hairlines.
- **Depth charts:** columns are position groups (Guards, Wings, Bigs), never single positions; one player per row.
- **Cards are page prototypes.** The user expects to move to a fixed page layout later; making each card right now is how each page gets designed.

## Contrast (the user's most repeated complaint)
- Check every text, icon and control against what is really behind it, in every state: normal, hover, selected, disabled.
- Text on light glass: near-black (#121d27) or the soft ink (#3b4a57) at the lightest. Never light grey on white, never grey on grey.
- Text on dark glass: white (#f5f8fb) or #d3dde6 at the lightest. Icons drawn white.
- Hover changes the surface a little; it never turns text white on a light grey, or grey on a dark.
- Not too harsh either: no black fills on white (checkboxes, clicked rows).
- Big status text never sits over content.

## Game-wide rules

### Tables
- **Header line:** one solid dark line under the header row (2px). Not two tones, not a hairline, not a double rule. No gap between it and the first row (not even 1px), the line never cuts into the header text, and no gap under the last row.
- **Header text:** 10px bold, sentence case, smaller than the row text.
- **Alignment:** centre everything (numbers and words), with the header centred over its column. Only the first field (player name) is left-aligned. Lists of names (depth charts) are left-aligned so entries line up in both directions; headshots sit vertically centred on the name.
- **Header and cells share widths exactly:** a header cell and the cells under it are the same width. Values in one column line up vertically.
- **No truncation of short fields** like roles ("…"): give the column the room, or wrap.
- **No subtext under a name or value.** A second fact is a second field (column), never small text underneath.
- **Rows:** medium height (about 30px) or compact. Never roomy. Alternating stripes.
- **Sorted field** (user, 2026-11-24, replaces column shading): no shading and no bold on the sorted column, header or cells. Only a small white triangle (▲ or ▼, by direction) just right of the heading text. Columns hug their content.
- **Every header sorts** in data tables (a small fixed list such as an award race's chasers needs no sorting). The sort arrow is never underlined.
- **One border colour per row rule.** The player cell's rule matches the other cells. Every table in a card reaches both edges, and its fields are labelled like the table above it.
- **No subheader strip** between a window's title bar and its table. Deadlines and rules go in a Details drop-down or the footer. Pick a useful default sort (contracts: this season's salary, high to low).
- **Header row (user, 2026-11-24):** the header cells' fill runs to the card's edges, while the rows keep their inset; the first and last labels stay indented, never on the edge. The "Player" label starts exactly where the headshots start.
- **Indent inward with each level (round 6, replaces "edge to edge"):** the window title, then section headers ("Two-way places"), then table header text, then row text each start further right than the level above. Tables keep a margin from the card's sides (the Roster spacing is the model). No gap between the card header and the table's top, and no gap at the bottom border.
- **Hover and click:** whole-row highlight. Every cell, including the player cell and its links, keeps the highlight. Hovering never underlines icons. If a row or box highlights on hover, clicking anywhere in it opens the player. Clicking a row never turns it black.
- **Controls never sit in a table header.** Window-level controls (reset, "coach rests players") go in the window header or a sub-header bar, and must look like buttons for the content, not like window controls.
- **Missing values:** an em dash (—). Never blank, never 0.
- **Headshots** sit where rank numbers would otherwise go, left of the name.
- Side-by-side tables line up exactly. Leader tables run Player | Team | stat.

### Ratings and value
- **Coloured number** (red, low, to blue, high, spread across 60–98) is the default in tables. The bar stays only where there is room for a wide one (player card header).
- If a bar is used: no track behind it. The empty space implies the remainder.
- Colour is the point. Never grey out ratings or make them one colour.
- **Injured players:** show today's rating, with the drop as a small red subtext (for example 84 with "−6" beside it). Spacing and size need care so it reads as one unit.
- **Value bars:** wherever value is shown or sorted (trade lists, Roster), it's a bar with the number right next to it. The bar is the main thing.
- **Totals of several values** (what a side gives in a trade): one segmented bar, each asset its own colour, matching the colour beside each asset.
- **OVR is the coloured number; OFF and DEF** next to it are plain dark and bold, so the eye still goes to OVR by colour.
- **Names are bold** in asset lists (players and picks alike). Lists in pop-ups use readable text and rows, not tiny ones; the name column is narrow.
- **Player card ratings:** every rating as a range bar (the league's middle half with min and max, his dot on it), like Four Factors, not plain bars.
- **Injured players:** the drop shows beside every rating that drops (OVR and the parts), as small red text.
- **Trade value** is never a bare grade number. Show it visually (a bar or something better), and make it the first thing you see on a player in a deal, ahead of roles.

### Marks and chips
- **Injury:** red cross plus red games-out number, and the player's name in red too (round 5), everywhere. No chip and no greyed-out row.
- **No numbered section headers** ("Technique and recognition", not "1. Technique…"), no "each bar adds to 100%" or "how often" captions: implicit things stay unsaid (round 6).
- **Draft pick details** (protections, swaps) open in a Details drop-down, not a hover.
- **Explanations are hover info, not visible text** (round 5): subtitles under section headers and notes like "Projected overall: line is…" become an info mark with hover text.
- **Section headers inside a table or list** (Shooting, Rebounding…) are visibly different from rows: small bold capitals (never italic; user, 2026-11-25).
- **Status (kept, declined, signed...):** a coloured icon plus plain black text, regular weight. No coloured pill chips.
- **Roles:** in tables and tiles, roles get their own column(s) as coloured text, not chips, not under the player's name and not hidden in hover text. Offense and defense roles read as a pair.
- **Small flags** (resting, the "Zz" mark) are a small superscript on the value they qualify (minutes or fatigue), not a column of their own.
- **Changed values** (a new salary after an extension) show in a different text colour. Never a highlight box.

### Text and numbers
- **Contracts:** always "$40.8M × 5". Never a bare salary. Costs that run over years (cost to release) use the same form.
- **Dates:** "Oct 20". Season charts use "Week 1, Week 2", not dates.
- **Percentages in leader tables:** 47.8 (no % sign).
- **Preseason ranks:** always say "Projected" ("Projected 1st of 30"). A plain "1st in the league" before games are played is misleading.
- **Teams:** logo plus abbreviation by default. Logo plus full name sometimes. Logo alone only when space is tight. Never the full name alone.
- **Labels next to coloured numbers** need clear spacing so the number and its label don't blur together (Next Opponent banner).
- **Extra explanation of game content** (contract terms, option details): a Details toggle that drops down. Hover tips or "i" marks are for game instructions and rules only, **and slide explanations**: a slideshow note is a small "i" dot right beside the slide title, shown on hover, never a "Details" drop-down (user, 2026-11-24). Never a small line of text under a value.
- **Short summaries become small tables**, not one cell per fact (the Team Profile payroll notes: a 5 × 2 table).

### Pictures
- **Every person and team has a picture.** No blank headshot or logo anywhere: real players, prospects, made-up players and staff, colleges.
- **Headshots:** trying soft colour (the user picked it over greyscale). Accept that a traded player's photo shows his old jersey.
- **Trophies** need a treatment (outline, frame or similar). A raw photo pasted on the card looks wrong.

### Buttons, tabs and checkboxes
- **Button style is a Settings choice (round 6):** glass pill (default), solid pill with a team-blue chosen state, rounded-square glass, or a segmented tray. The user couldn't pick one.
- **Choice rows (Keep / Release / Buy out):** one long pill with the chosen option as a filled pill inside it that slides to a new choice when clicked. The user's reference (an iOS segmented pill, 2026-11-24): a solid grey tray with no border, equal-width options with light-grey labels, and the chosen option a solid blue pill the full height of the tray, touching its edge, white label (red when the choice is a release).
- **Drop-down menus** are custom glass menus, not the browser's grey select boxes.
- **Card transparency is the player's choice** (user, 2026-11-24: "cards are too transparent"): a Settings > Look slider covers windows, pop-ups and slides. The default is a little more solid than round 8 (60%).
- **A player is a page, not a card** (user, 2026-11-24): clicking a player fills the page area with their page (sidebar and footer stay, Back at the top left, Esc). No window frame. Coach cards, box scores and the trade room stay pop-ups.
- **Screens that follow one another** (user, 2026-11-24): preseason, draft and free-agency steps are not listed in the sidebar. One screen follows the next, moved by the button at the bottom right. The footer holding that button is one piece with the left sidebar, never part of a page card (slides included).
- **Slides fill their space** (user, rounds 14 and 2026-11-24): never a half-empty slide. Add more items (leader rows, story and injury cards) until the card is full, and let the cards stretch to the remaining height.
- **No sharp white borders inside a card** (user, twice on 2026-11-24): no square outline around a table, list or player cell. Separate things with spacing, a hairline between rows, or the soft rounded card edge.
- **A table's column headings sit directly on the section's title bar line**, with no gap (slideshow Depth chart).
- **Pill-shaped glass buttons** (round 5), like iOS glass buttons: fully rounded ends, a translucent light fill, a thin light edge, vertically centred in their bar. Everywhere: tool bars, row actions (Keep / Waive / Buy out), slideshow navigation, trade room.
- **Long pill: only the chosen option has a shape** (round 8); the others are plain labels on the tray.
- **The standard tab picker is the long pill (user, 2026-11-24):** the same control as Keep / Waive / Buy out. A solid grey tray, equal-width options, the chosen one a solid blue pill that slides over when you pick another. Every tab group uses it (trade room Builder / Finder / Market, All / Players / Picks / Swaps, Payroll / Value / Team identity, Development's views, the court views). Labels for a group of tabs sit above it, centred.
- **Checkboxes: transparent fill** with a light edge, never a white box.
- **Table headers are never buttons:** sortable headers look like Minutes' headers (plain bold text, the line under).
- Filled primary button for the main action, plain text buttons for the rest.
- **Hover never turns text white** or inverts the button. Hover only shades the background slightly.
- **Nothing is filled black.** Not selected tabs, not checked checkboxes (white box, dark tick), not clicked rows.
- **Selected tab style: undecided.** The user wants to judge it against the rest of the game. Until then: light tint, darker label and an underline, evenly sized and centred.
- **Phases, not days, in the offseason:** outside the regular season, a phase's one button moves to the next phase. Simulating day by day only matters in the season.
- **One obvious next step.** When a phase's work is done (the roster is set), show one clear button to move on and hide the sim buttons that don't apply.

- **Side-by-side panels line up (round 7):** in the trade room every side's header sits on one top line and every footer (payroll, totals) on one bottom line, whatever each list holds. A side panel (the verdict) never starts higher or lower than the panels beside it.
- **Small text buttons sit next to what they act on** ("Add condition" right after "Draft Terms", not pushed to the far edge). Secondary actions ("Add or change players", "Add condition") share one small style.
- **Charts keep their tables under them** (round 7: the payroll table beside the chart was wrong).
- **Value bars are never grey** (round 7, again on the Value tab).

### Settings
- **One Settings window (user, 2026-11-24: "completely disorganized"):** labelled sections (Game, Look, Season slideshows, Help, Credits), each a row with the label on the left and its control on the right. Choices are the standard long pill; explanations sit behind an "i"; actions are a row of pills; Back to Save Selection sits alone at the bottom. The old separate settings page opens this window.

### Windows and cards
- **No icon in a window's title bar.** Icons are only for the window switcher.
- Every card has a full border. Pop-ups open centred.
- **Opening animation:** the quick zoom (about 0.17 s) stays. No slide-up, no spring.
- Cards that are too small to stand alone (Four Factors, Offense, Defense) should be grouped with related content rather than living as tiny cards.
- **Board background:** slate blue with a faint grid is the default. Keep warm charcoal and cream paper as optional themes. Mid grey is out.
- **Offseason steps** live in one toolbar chip that opens a list, next to the date and phase.
- A window that does a job (picking trade assets) and a window that reviews the result (the deal) can be two views rather than one cramped page.

### Charts
- At least one radar somewhere, curved. If two shapes are overlaid, they must be able to overlap; otherwise use two radars or rearrange.
- Bars everywhere else, plus the reference graphs above where they tell the story better.
- Axis labels small and at round values (0, 10, 20...).
- Distributions use a range or box plot (min, middle half, max) with a coloured dot for us. Add a small legend. Dots have no white outline on the dark card.
- Shape markers (the Team Identity hexagons) stay small; they must not dominate by size.
- **Charts keep their proportions.** Never squash or stretch a chart to fit. The payroll chart keeps exactly the width-to-height shape it has on its own card, wherever it appears (round 4: still off in the trade room). Give it the room it needs, and a table under it where useful.
- **Cards are sized for their graphics:** a card's default size never cuts off its chart (Four Factors).
- **Line graphs:** a light background grid, a y-axis floor low enough for the lowest player, and prominent (darker) range fills.
- **Labels for a group of tabs** sit above the group, centred, so they never look like one of the options (Team Identity: Offense / Defense).
- **Radars:** enough categories to describe a team (round 4: more than four or five per side).
- **Range charts** (Four Factors) use the same width per row, with right always meaning better. Bars in one list all have the same length, whatever the value text beside them.
- **Bars on one card share one scale** (Development's Season and Month bars).
- **Heat maps:** many colour steps (round 6: more than five visible; use a near-continuous scale) so the middle isn't washed out; each region can carry a tiny two-line label (two numbers, about 10 characters).
- **Meters that mean "worse as they fill"** (fatigue) run light yellow to dark red.
- **Payroll is always the four-year segmented payroll chart.** Anything that changes payroll (a trade) shows the chart, with the change animated (plays once, then a replay button).
- Each player keeps one colour across all years of the payroll chart.
- No circular "runway" gauges; the user doesn't find them clear.

### Motion
- Slides can animate rows in (falling into place) instead of hard cuts. Keep it quick.

## Shared style values (the token sheet, 2026-11-25)

One file holds the values every surface shares: `src/nba_gm_data/gui/tokens.css` (loaded first). They are the values
the glass look already used most, named once. The user approved them at the Stage A checkpoint of the UI polish pass
(11px floor, never italic, sound on and quiet). New rules use them; an old rule moves onto them when its page is
rebuilt. Don't add a literal size, colour, corner or timing to a stylesheet when one of these fits.

**Type** (nothing under 11px; digits always line up)

| Use | Size | Weight | Name |
|---|---|---|---|
| A slide's headline (the welcome, season slideshows) | 56px | bold | `--gm-size-display` |
| Page title | 28px | semibold | `--gm-size-page` |
| Section title | 18px | bold | `--gm-size-section` |
| The one number a section leads with | 34px | bold | `--gm-size-lead` |
| Key figure | 20px | bold | `--gm-size-figure` |
| The main button | 16px | bold | `--gm-size-button` |
| Names (semibold), row text and values (regular), controls | 13px | semibold / regular | `--gm-size-row` |
| Table headings (bold), the one subtext (regular) | 11px | bold / regular | `--gm-size-small` |

Three weights only: regular 400, semibold 600, bold 700 (`--gm-weight-*`). Bold for headings, lead numbers and table
headings; semibold for names and labels; regular for values. **No italic anywhere**: emphasis is weight or colour, and
section labels inside a table are small bold capitals. Capitals only for sidebar group labels, section labels inside a
table and news banners; sentence case elsewhere.

**Colours**

| Use | Value | Name |
|---|---|---|
| Text | `#ffffff` | `--gm-ink` |
| Second text | `#d5e1ea` | `--gm-ink-2` |
| Dimmest allowed (about 7:1 on the page glass) | `#a8b9c7` | `--gm-ink-3` |
| Accent, links, "you", the current step | `#7cc0ff` | `--gm-accent` |
| The chosen option in a picker | `#3b82d6` | `--gm-pick` |
| Must do, counts | `#ff5d5d` | `--gm-must` |
| Injury, loss, over the cap | `#ff9a9a` | `--gm-bad` |
| Deadline, tax line, extension-eligible | `#f2c46d` | `--gm-warn` |
| Done, win, growth | `#86e0a2` | `--gm-good` |

The rating colour scale (60 to 98, red to blue) is unchanged and stays where it is defined.

**Lines and corners**: one solid line under a table heading (1.5px, `--gm-line-strong`); one hairline between rows and
around cards (`--gm-line`, `--gm-line-row`); keyboard focus ring `--gm-focus`. Four corner sizes: 0 rows, 8px tiles and
fields, 16px cards, pop-ups and the page, full pills for buttons, pickers and bars (`--gm-radius-*`).

**Spacing**: 4, 8, 12, 16, 24, 32, 48 (`--gm-space-1` to `-7`). 24 between columns, 32 between sections. Each level
starts 8px further right than the one above it: page title, section title, table heading, row. Rows are 34px on a page
(a lone table may stretch its rows to fill, up to 42px) and 30px in a pop-up.

**Glass levels**: the arena picture; the frame (sidebar and footer, `--gm-glass-frame`); the page
(`--gm-glass-page`, driven by Settings > Card transparency); a tile (`--gm-glass-tile`); a pop-up
(`--gm-glass-popup`). One hairline each, no gradients, nothing filled white, cream or black.

**Motion**: four timings and one curve. Quick 0.12s (hover, press, a tick); Open 0.17s (pop-ups and menus: the zoom);
Move 0.24s (a picker's pill sliding, pages cross-fading, rows falling into place); Data 0.45s (bars and charts changing,
once). Easing `cubic-bezier(.2, .8, .2, 1)` (`--gm-ease`). Never slide-ups, bounces or loops. Everything that reads
these values stops when the computer asks for reduced motion.

**Sound** (`gui/sound.js`): made in the browser, no files. On and quiet by default (volume 40%), button clicks off;
Settings > Sound has the switch, the volume and the clicks switch. Continue (the main button moves time), win and loss
(your result after a sim), must do (a job starts to block the clock), deal (a trade, signing or extension goes
through), pick (a draft selection), reveal (a lottery envelope), blocked (the game refuses an action), news (a trade
offer or draft-night trade arrives), champion (once a year), click (every button, own switch).

**Music** (`gui/music.js`, `gui/assets/music/`, 2026-11-26): four public-domain tracks the user approved, off until
switched on in Settings > Sound, with its own volume. Tracks fade in and out and play in a shuffled order. A new track
is a download: list it for the user (title, artist, licence, size, source) and get a yes first; add it to
`tracks.json` so it shows in the credits.

**What has moved onto these values so far** (Stage B): every stylesheet's text weights (12 different, now 3), italic
(16 uses, now none) and transition timings and easing (17 timings and 7 curves, now 4 and 1); the page title, the
sidebar frame's new parts, Home's progress parts, the footer button, the welcome. Still literal in the old
stylesheets, moving page by page in Stage C: text sizes, colours and corner sizes (the cards have fixed layouts, so
these cannot be swapped blind).

## The progress screen and the one button (2026-11-25)

- **Home is the progress screen.** Its top shows the phase and one line under it, with the seven-step year strip
  (Preseason, Season, Playoffs, Who to keep, Free agency, Summer, Camp). Its left column is the to-do list. You land
  on it when a save loads, when a phase begins, and whenever the game stops by itself.
- **The to-do list**: red rows block the clock and come first; a yellow row is a deadline today; then what is open;
  green rows are done; dashed grey rows are closed (from the save's own `legal_actions`, so the list cannot disagree
  with what the game accepts). A row opens its page or step screen; a step screen has a Home button at its title.
- **One button, bottom right, only moves time.** Its label says what happens and its small line says to which date.
  Quieter choices (a week, a month, finish the draft) stand to its left. When a job blocks it, the button turns
  must-do red, carries the job's name and opens the job; it never fails with a message.
- No pause windows for the trade deadline or the end of the regular season: the sim stops on Home with one line
  saying why.
- The logic lives in `gui/progress.js` (one rule table, `PHASES`); `card-pages.js` places it.

## The sidebar and the tabs (user, 2026-11-26)

- **The sidebar is the spine, on every page:** team and date; the phase with one line under it; the to-do list; then
  only a few pages (Home, Team, Front Office, League); the search field; Settings.
- **The year bar runs across the top of every page, not in the sidebar** (user, 2026-11-26). Each of its seven
  segments is as long as its part of the year (the regular season is the longest), and the current one fills only as
  far as today.
- **Everything else is a tab** at the page's title (the standard long pill). More tabs is fine; more sidebar pages is
  not.
- **A tab shows one thing, or a couple that belong together** (the rotation and the next game; a table and its
  chart). Do not force many cards onto one page (user: "one of my biggest current issues").
- Home's first tab is "Today": the rotation, and the next game with your conference's standings under it; from the
  lottery to camp it is contracts, payroll and picks (user's picks). No small copy of another tab on Home: the week
  strip was removed because the Schedule tab is one click away (user, 2026-11-26).
- **Plain words on the welcome screens.** No slogans or paired punchy sentences ("One button moves time", "Red jobs
  come first. The rest can wait."): the user reads them as machine-written. A title is a plain label ("To do",
  "Pages"); a line under it says one concrete thing or is left out.

## The arena behind the glass (2026-11-26)

- **Neutral photos, team colour as accents** (user: the single colour grade over every photo was "kind of
  overpowering ... slapping a color filter over a photo"). Each arena photo keeps its own colours, muted, a little
  more contrast, darker toward the edges, bright floors and screens eased down so white text reads (treatment C, the
  user's pick). Team colour belongs in small places: the year bar, the current page, your row in a table.
- **A different photo by phase** where the team has more than one credited photo: the season, the playoffs, the
  offseason (`gui/assets/arenas/<TEAM>.jpg`, `-playoffs.jpg`, `-offseason.jpg`, `phases.json`; built by
  `output/ui-polish/bg/build_all.py` from the photos in the main checkout's `output/ui-workbench/arena`). Eleven teams
  have one photo and keep it all year. New photos are downloads: ask the user first.
- **It moves, a little** (user: "a more alive background so it feels less static"): one fixed layer behind the game
  (`gui/arena.js`, `gui/arena.css`) drifts slowly (`--gm-motion-drift`, 90s there and back), cross-fades when the
  picture changes and leans a little toward a different side for each sidebar page (`--gm-motion-scene`, 1.2s). This
  is the one exception to "nothing loops". Settings > Look > Background movement turns it off; so does the computer's
  reduced-motion setting. Tables and text never move.
- Rebuilt pictures need a new `VERSION` in `arena.js`, or browsers keep the old ones.

## Full-size pages (2026-11-26)

A page is no longer cards pasted at card size and shrunk as one picture. A rebuilt page is laid out at real sizes and
its sections share the page's width and height. The rules live in `gui/full-pages.css`; the layouts in
`gui/card-pages.js` (a layout marked `full`).

- **Sizes are the shared values, drawn at scale 1**: 13px rows and names, 11px bold table headings, 18px bold section
  titles. A page states the smallest area it fits in and a roomy one; between them nothing is scaled. A smaller window
  shrinks the whole page as one piece; a larger one grows it a little (at most 1.25).
- **Rows share the height.** A table's rows stretch to fill what the section is given, up to the page row height
  (34px), or 42px for a table that is alone on its page. They never scroll and never grow past that: spare room stays
  at the bottom.
- **A headshot fills its row** and stands on the row's line.
- **Heading text and row text start at the same place**, 8px in from the section title; one 1.5px line under the
  headings, one hairline between rows, no fills.
- **Pictures keep their proportions** (the payroll chart, the draft-assets grid): the card is drawn at its own size
  and enlarged as one piece to fit its room. Never restyled, never stretched.
- **The same rows in two tables are two tabs of one page** (Team: Roster | Stats).
- **Nothing is cut to make room.** If a name cannot fit it ends in an ellipsis; a role never does (give the column
  the width). A long to-do job takes a second line.
- **Rebuilt so far:** every tab of the four sidebar pages, and the Opening Roster step (it shares its table with
  Two-Way Places). Not yet: the other step screens (Set The Roster, who to keep, the draft room, free agency). News
  and Awards are enlarged whole and still leave empty room.
- **Lists that may scroll** (the user's exceptions to "nothing scrolls"): available staff; the draft prospect board
  and the playoff tables scrolled before and still do. Their headings stay pinned.

## Preserve (the user's favourites; don't redesign)
- Team Identity heat maps at the current hexagon size (round 3: "looks great"). The tab style there still needs a new try.
- Four Factors range charts (round 3: "maybe one of my favourite things").
- Preseason power rankings and the continuity slide.
- The four-year payroll share chart (only tweaks: consistent player colours, slightly livelier colours).
- The top toolbar.
- The league wire ticker.
- The injury mark (red cross plus number).
- The yellow highlight for extension-eligible players.
- The diverging growth and regression bars on Player Development.
- Four Factors as range charts (round 2: "looks great").
- MVP card as composed in round 3 (round 4: "Beautiful. No notes").
- Opening roster table (round 4: "so good for contract management, please keep it").
- Next Opponent (round 2: "close to done"; only the fixes above).
- Contracts to Watch slide (fine for now).
- The release / buyout / waive buttons on the opening roster window.
- Trade room: the simple payroll line ("takes $10M too much back"), the final-offer checkbox next to Ask.

## Next priorities (round 4)
- Player cards (very high): the ratings page has far too much text; ratings as range bars.
- More Taylor Wyman-style graphs.
- News cards (low).
- Free agency and draft windows: not reviewed yet.

## Never do
- Title-bar icons, AI-drawn decorative SVGs.
- White text on hover. Anything filled black (tabs, checkboxes, clicked rows).
- Coloured pill chips for status.
- Gaps between a header and its table. Double borders. Text at the same indent as the level above it.
- Scrolling inside a card or pop-up (round 6: "I never like scrolling"). Use pages or tabs, or make the card larger. Exception (round 8): the trade room's asset list may scroll.
- Estimated or partial data shown as such on the front end: no hollow dots, no "44 of 64 from player data" counts. Ratings look definite.
- White fills on hover (header cells), white checkbox boxes, white rims on window title bars.
- Headers not centred over their values.
- Controls in a table header.
- A roster table dumped into a showcase screen. Showcase screens need a graphic or a takeaway.
- Bare salary without years. Bare trade value numbers.
- Rank wording that implies results before games are played.
- Walls of explanatory text.
- White tables or cards sitting on the glass.
- Subtext under names or values. "Projected" on a starting five.
- Blank pictures.
- Anything that looks like Basketball GM.
