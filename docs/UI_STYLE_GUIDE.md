# UI style guide

Distilled from the user's taste deck (2026-11-23, 49 answered cards; answers live in the deck artifact's `answers` collection) plus the playtest notes in `docs/agents/tasks/playtest-notes-2026-11-22.md`. Every agent doing GUI work follows this. When a rule here conflicts with older docs, this file wins.

## What the user wants overall

- A league with its own look: greyscale crisp headshots, colour used on purpose, graphs and pictures, not just tables.
- Minimal text. Graphics carry the meaning. No kicker lines, no captions repeating the header, one short subtext at most.
- Clean, consistent and polished. Small gaps, uneven borders and off-centre headers are noticed and disliked strongly.
- Narrative matters: the preseason outlook (power rankings, continuity) is the favourite part of the game.

## Game-wide rules

### Tables
- **Header line:** one thick dark line under the header row (about 3px). Not two tones, not a hairline.
- **Header text:** 10px bold, sentence case, smaller than the row text.
- **Alignment:** centre everything (numbers and words), with the header centred over its column. Only the first field (player name) is left-aligned.
- **Rows:** medium height (about 30px) or compact. Never roomy. Alternating stripes.
- **Sorted column:** shaded and bold, on every row including the striped ones. Columns hug their content so the shading isn't wider than the text needs.
- **Every header sorts.** The sort arrow is never underlined.
- **Edge to edge:** a table fills its card's width. No inner margin around it, no gap between the card header, any sub-header and the table, and no gap at the bottom border.
- **Hover:** whole-row highlight. Every cell, including the player cell and its links, keeps the highlight. Hovering never underlines icons (the injury cross).
- **Missing values:** an em dash (—). Never blank, never 0.
- **Headshots** sit where rank numbers would otherwise go, left of the name.
- Side-by-side tables line up exactly. Leader tables run Player | Team | stat.

### Ratings
- **Coloured number** (red, low, to blue, high, spread across 60–98) is the default in tables. The bar stays only where there is room for a wide one (player card header).
- If a bar is used: no track behind it. The empty space implies the remainder.
- Colour is the point. Never grey out ratings or make them one colour.

### Marks and chips
- **Injury:** red cross plus red games-out number. One darker red (not pink), one size, everywhere. No chip and no greyed-out row.
- **Status (kept, declined, signed...):** a coloured icon plus plain black text, regular weight. No coloured pill chips.
- **Roles:** coloured chips are right here, because there are few roles. Offense and defense roles sit side by side, read as a pair ("Primary handler / Versatile stopper").

### Text and numbers
- **Contracts:** always "$40.8M × 5". Never a bare salary.
- **Dates:** "Oct 20". Season charts use "Week 1, Week 2", not dates.
- **Percentages in leader tables:** 47.8 (no % sign).
- **Preseason ranks:** always say "Projected" ("Projected 1st of 30"). A plain "1st in the league" before games are played is misleading.
- **Teams:** logo plus abbreviation by default. Logo plus full name sometimes. Logo alone only when space is tight. Never the full name alone.
- **Extra explanation of game content** (contract terms, option details): a Details toggle that drops down. Hover tips or "i" marks are for game instructions and rules only. Never a small line of text under a value.

### Buttons and tabs
- Filled primary button for the main action, plain text buttons for the rest.
- **Hover never turns text white** or inverts the button. Hover only shades the background slightly.
- Selected tabs and toggles are never black with white text. Use a light tint, a darker label and an underline or edge, and keep the controls evenly sized and centred.

### Windows and cards
- **No icon in a window's title bar.** Icons are only for the window switcher. Awards should eventually use a picture of the real trophy.
- Every card has a full border. Pop-ups open centred.
- Cards that are too small to stand alone (Four Factors, Offense, Defense) should be grouped with related content rather than living as tiny cards.
- Board background: cream paper with blue grid for now. The user expects to replace it with something darker and calmer later. Plain white or grey are out.

### Charts
- At least one radar somewhere, curved. Bars everywhere else.
- Axis labels small and at round values (0, 10, 20...), not odd ticks like 8 and 17.
- Distributions are shown with a range or box plot (min, middle half, max) and a coloured dot for us, not a single midpoint bar.
- Each player keeps one colour across all years of the payroll chart.

### Motion
- Slides can animate rows in (falling into place) instead of hard cuts. Keep it quick.

## Preserve (the user's favourites; don't redesign)
- Preseason power rankings and the continuity slide.
- The four-year payroll share chart (only tweaks: consistent player colours, slightly livelier colours).
- The top toolbar.
- The league wire ticker.
- The injury mark (red cross plus number).
- The yellow highlight for extension-eligible players.
- The diverging growth and regression bars on Player Development.

## Never do
- Title-bar icons, AI-drawn decorative SVGs.
- White text on hover. Black-filled selected tabs.
- Coloured pill chips for status.
- Gaps between a header and its table, or tables that don't reach the card edges.
- Headers not centred over their values.
- A roster table dumped into a showcase screen. Showcase screens need a graphic or a takeaway.
- Bare salary without years.
- Rank wording that implies results before games are played.
