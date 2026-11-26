// Pages layout (branch sidebar-pages): every board card has a page, the pages stylesheet loads last, and the layout
// choice is a remembered preference.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

function load(stored = {}) {
  const storage = new Map(Object.entries(stored));
  const html = {dataset: {}};
  const context = {
    window: {}, structuredClone, document: {documentElement: html},
    localStorage: {getItem: (key) => storage.has(key) ? storage.get(key) : null, setItem: (key, value) => storage.set(key, String(value))},
  };
  vm.createContext(context);
  vm.runInContext(read('card-pages.js'), context);
  return {pages: context.window.CardPages, html, storage};
}

test('every card the board can float has a page', () => {
  const source = read('card-board.js');
  const block = (name) => source.match(new RegExp(`const ${name} = \\[([\\s\\S]*?)\\n  \\];`))[1];
  const ids = [...`${block('CARDS')}${block('ASSET_CARDS')}`.matchAll(/\["([a-z-]+)", "/g)].map((match) => match[1]);
  assert.ok(ids.length >= 26, 'the board card lists were found');
  const {pages} = load();
  for (const id of ids) assert.ok(pages.PAGE_CARD_IDS.has(id), `${id} is on a page`);
  for (const id of ['phase-cutdown-decision', 'phase-set_roster-checklist', 'phase-playoffs-bracket', 'phase-draft-board', 'phase-free_agency-market', 'phase-fantasy_draft-board']) {
    assert.ok(pages.PAGE_CARD_IDS.has(id), `${id} is on a page`);
  }
});

test('pages have unique ids, a sidebar group and a label', () => {
  const {pages} = load();
  const ids = pages.PAGES.map((page) => page.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const page of pages.PAGES) {
    assert.ok(['now', 'home', 'team', 'office', 'league'].includes(page.group), page.id);
    assert.ok(page.label, page.id);
    assert.ok(page.layout || page.slideshow, page.id);
  }
  for (const id of ['home', 'roster', 'contracts', 'trades', 'standings', 'schedule', 'outlook']) assert.ok(ids.includes(id), id);
});

test('pages are the default layout and the choice is remembered', () => {
  let {pages, html} = load();
  assert.equal(pages.enabled(), true);
  assert.equal(html.dataset.layout, 'pages');
  pages.setMode('board');
  assert.equal(html.dataset.layout, 'board');
  assert.equal(pages.enabled(), false);
  ({pages, html} = load({nbaGmLayoutMode: 'board'}));
  assert.equal(pages.enabled(), false);
  assert.equal(html.dataset.layout, 'board');
});

test('the pages stylesheet loads last and the module right after the board', () => {
  const html = read('index.html');
  const sheets = [...html.matchAll(/href="\/([^"?]+\.css)/g)].map((match) => match[1]);
  assert.equal(sheets.at(-1), 'card-pages.css');
  const scripts = [...html.matchAll(/src="\/([^"?]+\.js)/g)].map((match) => match[1]);
  assert.equal(scripts.indexOf('card-pages.js'), scripts.indexOf('card-board.js') + 1);
});

test('the board keeps its pop-ups inside the page area and hands page cards to the pages', () => {
  const board = read('card-board.js');
  assert.match(board, /const canvasScale = \(\) => \(window\.CardPages\?\.enabled\?\.\(\) \? 1 : CANVAS_SCALE\);/);
  assert.match(board, /if \(pages\?\.owns\(id\)\) return pages\.paint\(id\);/);
  assert.match(board, /if \(pages\?\.owns\(id\)\) \{ pages\.show\(id\); return; \}/);
  assert.match(board, /nbaGmCardBoard:v1:\$\{pagesMode \? "pages:" : ""\}/);
});

test('step screens stay out of the sidebar and the footer sits outside the page', () => {
  const {pages} = load();
  const steps = pages.PAGES.filter((page) => page.step).map((page) => page.id);
  assert.equal(steps.slice(-2).join(), 'roster-moves,set-roster', 'the preseason ends on Set The Roster');
  for (const id of ['draft-room', 'free-agency', 'free-agency-checklist']) assert.ok(steps.includes(id), id);
  const source = read('card-pages.js');
  assert.doesNotMatch(source, /\["now", ""\]/);
  assert.match(source, /<\/div>\n\s*<footer class="pages-foot">/);
});

test('a player is a page of the app, not a pop-up window', () => {
  const board = read('card-board.js'), source = read('card-pages.js');
  assert.match(board, /const isPlayerPage = \(id\) => Boolean\(pages\) && String\(id\)\.startsWith\("player-card-"\)/);
  assert.match(board, /pages\.showDetail\(id\);/);
  assert.match(board, /clipboard-player-card--coach/, 'coach cards stay pop-ups');
  assert.match(source, /data-pages-detail-back/);
  assert.match(source, /event\.key === "Escape" && currentPage === DETAIL/);
  assert.match(read('card-pages.css'), /\.pages-shell\.is-detail \.pages-title \{ display: none; \}/);
});

// ---- UI polish pass, Stage B: Home is the progress screen, one button moves time, a four-screen welcome, sounds.
function loadProgress(save, extra = {}) {
  const context = {
    document: {addEventListener() {}},
    state: {home: {save}, data: extra.data || {}, hydrating: false, draftPresentationStage: extra.stage || ''},
    dashboardPhaseKind: () => extra.kind || '', requiredClipboardDecision: () => extra.required || '',
    offseasonCalendar: () => extra.dates || {}, tradeDeadlineDate: () => '2027-02-05',
    teamLabel: (team) => String(team?.abbrev || team || ''), userTeam: () => 'PHI', rosterRows: () => [],
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(read('progress.js'), context);
  return context.window.GameProgress;
}
const baseSave = (patch) => ({phase: 'regular_season', current_date: '2026-12-25', pending_counts: {}, legal_actions: ['trades', 'extensions', 'advance'], user_team_record: {wins: 16, losses: 12}, ...patch});

test('every phase of the save has a step on the year strip', () => {
  const progress = loadProgress(baseSave());
  assert.equal(progress.YEAR.length, 7);
  for (const phase of ['fantasy_draft', 'preseason', 'regular_season', 'play_in', 'playoffs', 'draft_lottery', 'draft', 're_signing', 'free_agency', 'offseason', 'training_camp']) {
    const rule = progress.PHASES[phase];
    assert.ok(rule && rule.title && rule.step >= 0 && rule.step < 7, phase);
  }
});

test('in season the one button sims to the next game, with a week and a month beside it', () => {
  const progress = loadProgress(baseSave(), {data: {dashboard: {next_games: [{date: '2026-12-28', is_home: false, opponent_team: 'OKC'}], extension_window_open: true}}});
  const dock = progress.dock(progress.context());
  assert.equal(dock.main.label, 'Sim to next game');
  assert.equal(dock.main.sub, 'to Dec 28 · at OKC');
  assert.match(dock.main.attrs, /data-advance="next-event"/);
  assert.equal(dock.more.map((button) => button.label).join(), 'Week,Month');
  assert.equal(dock.main.blocked, false);
  const markup = progress.dockMarkup();
  assert.ok(markup.indexOf('progress-more') < markup.indexOf('progress-go'), 'the main button comes last (far right)');
  assert.equal(progress.heading(progress.context()).sub, '16 – 12');
});

test('a job that blocks the clock is first in the list and named by the button', () => {
  const save = baseSave({phase: 'preseason', current_date: '2027-10-20', pending_counts: {roster_minimum: 1}});
  const progress = loadProgress(save, {required: 'cutdown', kind: 'cutdown', data: {cutdown: {short: {count: 13, minimum: 14}}}});
  const context = progress.context();
  const jobs = progress.jobs(context);
  assert.equal(jobs[0].kind, 'must');
  assert.equal(jobs[0].label, 'Sign 1 more player');
  assert.equal(jobs[0].detail, '13 of 14');
  const dock = progress.dock(context);
  assert.equal(dock.main.label, 'Sign 1 more player');
  assert.equal(dock.main.blocked, true);
  assert.match(dock.main.attrs, /data-pages-go="roster-moves"/);
  assert.doesNotMatch(dock.main.attrs, /data-advance|data-phase-command/, 'a blocked button never moves time');
  assert.match(progress.dockMarkup(), /class="ui-command progress-go is-blocked"/);
  assert.equal(progress.blockingKey(), 'Sign 1 more player');
});

test('deadline day: the list warns and the button says what it closes', () => {
  const progress = loadProgress(baseSave({current_date: '2027-02-05'}));
  const context = progress.context();
  assert.equal(progress.heading(context).title, 'Trade deadline');
  assert.equal(progress.jobs(context)[0].kind, 'warn');
  assert.equal(progress.dock(context).main.label, 'Sim past the deadline');
  assert.match(read('app.js'), /if \(firstRunLayout\(\)\) return landHomeForStop\("The sim stopped: today is the trade deadline\."\);/);
});

test('closed actions show as closed rows, from the save\'s own legal actions', () => {
  const progress = loadProgress(baseSave({phase: 'playoffs', current_date: '2027-04-30', legal_actions: ['extensions', 'advance']}), {kind: 'playoffs'});
  const jobs = progress.jobs(progress.context());
  const trades = jobs.find((job) => job.label === 'Trades');
  assert.equal(trades.kind, 'shut');
  assert.equal(trades.go, null);
  assert.equal(jobs.at(-1).kind, 'shut', 'closed rows come last');
  assert.equal(progress.dock(progress.context()).main.label, 'Sim one game per series');
});

test('the sidebar carries the phase and the to-do list; Home lands first, and step screens lead back to it', () => {
  const {pages} = load();
  // Only a few pages in the sidebar (user, 2026-11-26); everything else is a tab of one of them.
  assert.deepEqual(Array.from(pages.GROUPS, ([id]) => id), ['home', 'team', 'office', 'league']);
  const tabs = (group) => Array.from(pages.PAGES).filter((page) => page.group === group).map((page) => page.id);
  assert.deepEqual(tabs('home'), ['home', 'schedule']);
  for (const id of ['roster', 'stats', 'development', 'staff', 'identity', 'profile']) assert.ok(tabs('team').includes(id), id);
  assert.deepEqual(tabs('office'), ['contracts', 'trades', 'scouting']);
  for (const id of ['standings', 'news', 'awards', 'playoffs', 'playoff-stats']) assert.ok(tabs('league').includes(id), id);
  const source = read('card-pages.js');
  assert.match(source, /progressEl\.className = "pages-progress";/);
  assert.match(source, /progressEl\.querySelector\("\.progress-rail"\)\.innerHTML = progress\(\)\.listMarkup\(/, 'the to-do list is in the sidebar, on every page');
  assert.match(source, /class="pages-tabs" role="tablist"/);
  assert.match(source, /if \(!stays \|\| newlyBlocked \|\| called\) return "home";/);
  assert.match(source, /class="pages-control pages-step-home" data-pages-go="home"/);
  assert.doesNotMatch(source, /pages-step-back|Continue: |nbaGmPage:v1|is-progress|progress-area/, 'no step-to-step buttons, no remembered page across loads, no list on the page');
  assert.match(read('assets-desktop.js'), /phaseCommands:\(window\.CardPages\?\.enabled\?\.\(\) && window\.GameProgress\?\.dockMarkup\(\)\) \|\| clipboardPhaseCommands\(\)/);
});

test('the welcome is four screens, skippable, remembered, and goes before the Preseason Outlook', () => {
  const app = read('app.js');
  const steps = app.slice(app.indexOf('const FIRST_RUN_STEPS = ['), app.indexOf('];', app.indexOf('const FIRST_RUN_STEPS = [')));
  assert.equal((steps.match(/\{title:/g) || []).length, 4);
  assert.match(app, /const tutorialSteps = \(\) => \(firstRunLayout\(\) \? FIRST_RUN_STEPS : GAME_TUTORIAL_STEPS\);/);
  assert.match(app, /class="first-run-skip" data-tutorial-action="skip">Skip</);
  assert.match(app, /if \(firstRunDue\(\)\) return;/);
  assert.match(app, /els\.gameTutorial\.classList\.remove\("is-first-run"\);[\s\S]*?maybeOpenSeasonSlideshow\(\);/);
  assert.doesNotMatch(app, /PAGES_TUTORIAL_STEPS/);
  for (const id of ['minutes', 'signals', 'development', 'staff', 'week', 'efficiency']) assert.match(app.slice(app.indexOf('const PAGE_SECTION_TIPS'), app.indexOf('function firstRunTeamSlide')), new RegExp(`\\b${id}: "`), `the ${id} tip is kept behind its i mark`);
  assert.match(read('card-pages.js'), /PAGE_SECTION_TIPS\[item\.id\]/);
});

test('sound is made in the browser, on and quiet by default, clicks off, with switches in Settings', () => {
  const listeners = {};
  const context = {document: {hidden: false, addEventListener: (type, fn) => { listeners[type] = fn; }}, localStorage: {getItem: () => null, setItem() {}}, Date, Math, JSON};
  context.window = context;
  vm.createContext(context);
  vm.runInContext(read('sound.js'), context);
  const sound = context.window.GameSound;
  assert.deepEqual({...sound.settings()}, {on: true, volume: 40, clicks: false});
  for (const name of ['continue', 'win', 'loss', 'must', 'deal', 'pick', 'reveal', 'blocked', 'news', 'champion', 'click']) assert.ok(sound.names().includes(name), name);
  assert.equal(sound.play('win'), false, 'nothing plays before the player has clicked or pressed a key');
  assert.equal(sound.set({volume: 250}).volume, 100);
  assert.equal(sound.set({on: false}).on, false);
  assert.doesNotMatch(read('sound.js'), /new Audio\(|\.mp3|\.wav|\.ogg|fetch\(/, 'no sound files');
  const app = read('app.js');
  for (const hook of ['data-sound-choice', 'data-sound-volume', 'data-sound-clicks']) assert.ok(app.includes(hook), hook);
  assert.match(app, /globalThis\.GameSound\?\.result\(recordBefore, state\.home\?\.save\?\.user_team_record\);/);
});

test('shared style values: one sheet, loaded first, and no italic or stray weights left in the game\'s stylesheets', () => {
  const tokens = read('tokens.css');
  for (const name of ['--gm-size-page', '--gm-size-row', '--gm-size-small', '--gm-weight-regular', '--gm-weight-semibold', '--gm-weight-bold', '--gm-ink', '--gm-must', '--gm-line-strong', '--gm-radius-card', '--gm-space-5', '--gm-glass-page', '--gm-motion-open', '--gm-ease']) assert.ok(tokens.includes(`${name}:`), name);
  assert.match(tokens, /--gm-size-small: 11px;/, 'the floor is 11px');
  assert.match(tokens, /prefers-reduced-motion: reduce/);
  const html = read('index.html');
  const sheets = [...html.matchAll(/href="\/([^"?]+\.css)/g)].map((match) => match[1]);
  assert.equal(sheets[0], 'tokens.css');
  for (const sheet of sheets.filter((name) => name !== 'tokens.css')) {
    const css = read(sheet);
    assert.doesNotMatch(css, /font-style\s*:\s*(italic|oblique)|\bfont\s*:\s*italic/, `${sheet}: no italic`);
    assert.doesNotMatch(css, /font-weight\s*:\s*(\d{3}|bold|bolder|lighter)\b/, `${sheet}: weights come from the shared values`);
  }
  for (const sheet of ['progress.css', 'full-pages.css']) assert.doesNotMatch(read(sheet).replace(/rgba?\([^)]*\)|#ffb0b0/g, ''), /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px/, `${sheet}: sizes come from the shared values`);
});

// ---- Stage C: pages rebuilt at full size.
const walk = (node, out = []) => { if (!node) return out; out.push(node); for (const item of node.items || []) walk(typeof item === 'string' ? {type: 'card', id: item} : item, out); return out; };
const cardsOf = (layout) => walk(layout).filter((node) => node.type === 'card');

test('Home shows two things in season: the rotation with the week under it, and the next game', () => {
  const {pages} = load();
  const layout = pages.PAGES.find((page) => page.id === 'home').layout({available: () => true});
  assert.ok(layout.full, 'laid out at real sizes, not scaled as one picture');
  assert.equal(layout.type, 'row');
  const columns = Array.from(layout.items, (column) => cardsOf(column).map((card) => card.id));
  assert.deepEqual(columns, [['minutes', 'week'], ['opponent']]);
});

test('Roster and Stats are full-size tabs; Contracts keeps the payroll chart and the draft assets in proportion; Trades is a full-size tab', () => {
  const {pages} = load();
  for (const id of ['roster', 'stats', 'trades']) assert.ok(pages.PAGES.find((page) => page.id === id).layout({available: () => true}).full, id);
  assert.deepEqual(cardsOf(pages.PAGES.find((page) => page.id === 'roster').layout({available: () => true})).map((card) => card.id), ['roster']);
  const contracts = pages.PAGES.find((page) => page.id === 'contracts').layout({available: () => true});
  assert.ok(contracts.full);
  const byId = Object.fromEntries(cardsOf(contracts).map((card) => [card.id, card]));
  assert.equal(byId.payroll.natural, 'fit', 'the payroll chart is enlarged as one piece, never stretched');
  assert.equal(byId.picks.natural, 'width');
  assert.equal(byId.contracts.natural, undefined, 'the table is laid out at real sizes');
  assert.deepEqual(cardsOf(pages.PAGES.find((page) => page.id === 'trades').layout({available: () => true})).map((card) => card.id), ['league-block', 'team-block', 'team-wants']);
  assert.match(read('assets-desktop.js'), /function leagueBlockGroupSize\(\) \{ return globalThis\.CardPages\?\.enabled\?\.\(\) \? 16 : 6; \}/, 'a page shows sixteen targets a group');
});

test('a full-size page is sized from its area, re-laid when its contents arrive, and its sheet reads the shared values', () => {
  const source = read('card-pages.js');
  assert.match(source, /if \(stage\.pagesFull\) return layoutFull\(el, stage, slots\);/);
  assert.match(source, /small < 1 \? small : large > 1 \? large : 1/, 'scale 1 between the size it fits in and the roomy size');
  assert.match(source, /new MutationObserver\(/);
  assert.match(source, /frame\.style\.zoom = String\(/, 'a picture keeps its proportions');
  const css = read('full-pages.css');
  assert.match(css, /\.pages-stage\.is-full/);
  for (const rule of css.split('\n').filter((line) => /\{/.test(line) && !/^\s*(\/\*|@|--|[a-z-]+:)/.test(line) && !line.startsWith(' '))) {
    assert.match(rule, /\.is-full|\.pages-tabs/, `only full-size pages and the tabs are touched: ${rule.slice(0, 90)}`);
  }
  assert.doesNotMatch(css, /font-style\s*:\s*italic|font-weight\s*:\s*\d/);
});

test('the year strip runs across the top of the page: segments as long as their part of the year, filled as far as today', () => {
  const context = {window: {}, document: {addEventListener() {}}, state: {home: {save: {phase: 'regular_season', current_date: '2026-12-25'}}, data: {}}};
  vm.createContext(context);
  vm.runInContext(`${read('progress.js')}`, context);
  const progress = context.window.GameProgress;
  const spans = Array.from(progress.yearSpans('2026-12-25'), (span) => ({...span}));
  assert.equal(spans.reduce((sum, span) => sum + span.days, 0), 365);
  assert.equal(Math.max(...spans.map((span) => span.days)), spans[1].days, 'the regular season is the longest segment');
  assert.ok(spans[1].through > .3 && spans[1].through < .45, 'Dec 25 is a bit over a third of the way through the season');
  const source = read('card-pages.js');
  assert.match(source, /<div class="pages-year"><\/div>\n\s*<header class="pages-head">/, 'above the title, in the page, not in the sidebar');
  assert.match(source, /shell\.querySelector\("\.pages-year"\)\.innerHTML = progress\(\)\.yearMarkup\(\);/);
  assert.match(read('progress.js'), /style="flex-grow:\$\{spans\[index\]\.days\}"/);
  assert.match(read('progress.js'), /index < step \? 1 : index > step \? 0 : Math\.max\(\.04, Math\.min\(1, spans\[index\]\.through\)\)/);
});
