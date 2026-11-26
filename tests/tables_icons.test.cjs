// House table system (shared sort comparator, headers, minutes sorting) and the window icon set.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const {loadHouseTables} = require('./house_table_helpers.cjs');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');

const houseScope = (extra = {}) => {
  const scope = {state: {rotationDraft: {}, tableSorts: {}, dashboardOpponentSort: {key: 'overall', direction: 'desc'}}, ...extra};
  vm.createContext(scope);
  loadHouseTables(scope);
  return scope;
};

const entry = (value, order, type = 'number') => ({...houseScope().HouseTable.sortValue(value, type), order});

test('comparator: numbers sort numerically, not as text', () => {
  const {HouseTable} = houseScope();
  const values = ['9', '10', '2.5', '-1', '100'];
  const asc = HouseTable.order(values, {direction: 'asc', valueOf: (v) => v});
  assert.deepEqual(Array.from(asc), ['-1', '2.5', '9', '10', '100']);
  const desc = HouseTable.order(values, {direction: 'desc', valueOf: (v) => v});
  assert.deepEqual(Array.from(desc), ['100', '10', '9', '2.5', '-1']);
});

test('comparator: text ignores case and accents, and numbers inside names sort naturally', () => {
  const {HouseTable} = houseScope();
  const names = ['luka Garza', 'Hugo González', 'Hugo Gonzalez Jr.', 'Álvaro Pérez', 'Player 10', 'Player 2'];
  const asc = Array.from(HouseTable.order(names, {direction: 'asc', type: 'text', valueOf: (v) => v}));
  assert.deepEqual(asc, ['Álvaro Pérez', 'Hugo González', 'Hugo Gonzalez Jr.', 'luka Garza', 'Player 2', 'Player 10']);
});

test('comparator: missing values (blank, dash, not a number) sort last in both directions', () => {
  const {HouseTable} = houseScope();
  const rows = [{id: 'a', v: ''}, {id: 'b', v: 5}, {id: 'c', v: '—'}, {id: 'd', v: 1}, {id: 'e', v: null}, {id: 'f', v: 'n/a'}];
  const asc = HouseTable.order(rows, {direction: 'asc', valueOf: (r) => r.v}).map((r) => r.id);
  const desc = HouseTable.order(rows, {direction: 'desc', valueOf: (r) => r.v}).map((r) => r.id);
  assert.deepEqual(Array.from(asc), ['d', 'b', 'a', 'c', 'e', 'f']);
  assert.deepEqual(Array.from(desc), ['b', 'd', 'a', 'c', 'e', 'f']);
  // Zero is a real value, not missing.
  assert.equal(HouseTable.sortValue(0).missing, false);
  assert.equal(HouseTable.sortValue('0').missing, false);
  const text = HouseTable.order([{n: ''}, {n: 'Bo'}, {n: 'Al'}], {direction: 'desc', type: 'text', valueOf: (r) => r.n}).map((r) => r.n);
  assert.deepEqual(Array.from(text), ['Bo', 'Al', '']);
});

test('comparator: ties keep the table order in both directions, so sorting is deterministic', () => {
  const {HouseTable} = houseScope();
  const rows = [{id: 'x', v: 3, o: 2}, {id: 'y', v: 3, o: 0}, {id: 'z', v: 1, o: 1}, {id: 'w', v: 3, o: 1}];
  const run = (direction) => HouseTable.order(rows, {direction, valueOf: (r) => r.v, orderOf: (r) => r.o}).map((r) => r.id).join('');
  assert.equal(run('desc'), 'ywxz');
  assert.equal(run('asc'), 'zywx');
  for (let i = 0; i < 5; i += 1) assert.equal(run('desc'), 'ywxz');
  assert.equal(HouseTable.compare(entry(3, 0), entry(3, 1), 'desc') < 0, true);
});

test('headers are buttons inside column headers with aria-sort, and clicks flip or start in the natural direction', () => {
  const {HouseTable} = houseScope();
  const columns = {name: {type: 'text'}, age: {first: 'asc'}, grade: {}};
  assert.deepEqual({...HouseTable.nextSort({key: 'grade', direction: 'desc'}, 'grade', columns)}, {key: 'grade', direction: 'asc'});
  assert.deepEqual({...HouseTable.nextSort({key: 'grade', direction: 'desc'}, 'name', columns)}, {key: 'name', direction: 'asc'});
  assert.deepEqual({...HouseTable.nextSort({key: 'name', direction: 'asc'}, 'age', columns)}, {key: 'age', direction: 'asc'});
  assert.deepEqual({...HouseTable.nextSort({key: 'name', direction: 'asc'}, 'grade', columns)}, {key: 'grade', direction: 'desc'});
  const active = HouseTable.headerCell({key: 'grade', label: 'Grade', sort: {key: 'grade', direction: 'desc'}});
  assert.match(active, /role="columnheader"[^>]*aria-sort="descending"/);
  assert.match(active, /<button type="button" class="house-sort is-active" data-house-sort="grade"/);
  const idle = HouseTable.headerCell({key: 'age', label: 'Age', sort: {key: 'grade', direction: 'desc'}});
  assert.match(idle, /aria-sort="none"/);
  const shared = HouseTable.headerCell({key: 'movement', label: 'Change', sort: {key: 'month', direction: 'asc'}, keys: [['movement', 'Change'], ['season', 'Season'], ['month', 'Nov']]});
  assert.match(shared, /data-house-header="movement season month" aria-sort="ascending"/);
  assert.equal((shared.match(/data-house-sort=/g) || []).length, 3);
});

test('the five tables declare their sortable columns, defaults and shaded column', () => {
  const scope = houseScope();
  for (const id of ['minutes', 'development', 'staff', 'staff-market', 'standings', 'opponent']) {
    const sort = scope.houseSort(id);
    assert.ok(scope.houseColumns(id)[sort.key], `${id} default sort is a real column`);
  }
  assert.deepEqual({...scope.houseSort('minutes')}, {key: 'minutes', direction: 'desc'});
  assert.deepEqual({...scope.houseSort('standings')}, {key: 'seed', direction: 'asc'});
  // Invalid saved state falls back to the default.
  scope.state.tableSorts.minutes = {key: 'nonsense', direction: 'asc'};
  assert.equal(scope.houseSort('minutes').key, 'minutes');
  assert.equal(scope.housePositionRank('PG'), 1);
  assert.equal(scope.housePositionRank('C'), 5);
  assert.equal(scope.housePositionRank('G-F'), 2.5);
  assert.equal(scope.housePositionRank('—'), '');
  assert.equal(scope.houseHeightInches("6'10\""), 82);
  assert.equal(scope.houseHeightInches('—'), '');
});

// A small stand-in for the minutes table DOM: rows with data attributes, a slider value and a fatigue cell.
function fakeMinutesTable(players) {
  const attrs = new Map();
  const rows = players.map((player, index) => {
    const input = {value: String(player.minutes)};
    const row = {
      dataset: {minuteRow: player.id, houseOrder: String(index), sortPlayer: player.name, sortPosition: String(player.position), sortHeight: String(player.height)},
      style: {gridRow: ''}, hidden: false, alt: false,
      classList: {contains: (name) => (player.injured && name === 'injured') || false},
      matches: (selector) => selector === '[data-house-row]',
      querySelector: (selector) => selector === '.season-fatigue' ? {dataset: {fatigueValue: String(player.fatigue)}} : selector === '[data-minute-player]' ? input : null,
      toggleAttribute(name, on) { if (name === 'data-house-alt') this.alt = on; },
      getBoundingClientRect: () => ({top: 0}),
      input,
    };
    return row;
  });
  const table = {
    rows: [...rows], dataset: {houseTable: 'minutes'}, style: {setProperty() {}, removeProperty() {}},
    querySelectorAll(selector) {
      if (selector === ':scope > .season-minute-row' || selector === ':scope > [data-house-row]') return [...this.rows];
      return [];
    },
    querySelector: () => null,
    append(row) { this.rows = this.rows.filter((r) => r !== row).concat(row); },
    contains: () => false,
    attrs,
  };
  return table;
}

test('sorting the minutes table only reorders rows: nobody\'s minutes change', () => {
  const source = app.slice(app.indexOf('function minutesRowsInSortOrder('), app.indexOf('\nfunction showRowMovement('));
  const scope = houseScope({showRowMovement() {}, animateRowFromPreviousPosition() {}});
  vm.runInContext(source, scope);
  const players = [
    {id: 'a', name: 'Derrick White', position: 1, height: 76, minutes: 27, fatigue: 20},
    {id: 'b', name: 'Luka Garza', position: 5, height: 82, minutes: 0, fatigue: 0, injured: true},
    {id: 'c', name: 'Jayson Tatum', position: 3, height: 80, minutes: 25, fatigue: 45},
    {id: 'd', name: 'Ron Harper Jr.', position: 3, height: 77, minutes: 2, fatigue: 5},
  ];
  scope.state.rotationDraft = {a: 27, b: 18, c: 25, d: 2};
  scope.state.rotationLockedPlayerIds = new Set(['c']);
  const before = JSON.stringify(scope.state.rotationDraft);
  const table = fakeMinutesTable(players);
  const ids = () => table.rows.map((row) => row.dataset.minuteRow).join('');
  const sliders = () => table.rows.map((row) => `${row.dataset.minuteRow}:${row.input.value}`).sort().join(',');
  const slidersBefore = sliders();

  scope.normalizeMinutesDomOrder(table);
  assert.equal(ids(), 'acdb', 'minutes high to low; the injured player counts as 0 (what his slider shows)');
  for (const [key, direction, expected] of [
    ['height', 'desc', 'bcda'], ['height', 'asc', 'adcb'], ['player', 'asc', 'acbd'],
    ['position', 'asc', 'acdb'], ['fatigue', 'desc', 'cadb'], ['minutes', 'asc', 'bdca'],
  ]) {
    scope.state.tableSorts.minutes = {key, direction};
    scope.normalizeMinutesDomOrder(table);
    assert.equal(ids(), expected, `${key} ${direction}`);
    assert.equal(JSON.stringify(scope.state.rotationDraft), before, `${key} ${direction} leaves every minutes target alone`);
    assert.equal(sliders(), slidersBefore, 'slider values unchanged');
    assert.deepEqual([...scope.state.rotationLockedPlayerIds], ['c'], 'user-locked minutes stay locked');
  }
  scope.state.tableSorts.minutes = {key: 'player', direction: 'asc'};
  scope.normalizeMinutesDomOrder(table);
  assert.equal(table.rows.map((row) => row.dataset.sortPlayer).join('|'), 'Derrick White|Jayson Tatum|Luka Garza|Ron Harper Jr.');
  assert.deepEqual(table.rows.map((row) => row.alt), [false, true, false, true], 'stripes follow the on-screen order');
  assert.equal(table.dataset.houseCol, '1');
  assert.equal(table.dataset.houseKey, 'player');
});

test('rows hold still while a minutes slider is dragged and re-sort on release', () => {
  const source = app.slice(app.indexOf('function minutesRowsInSortOrder('), app.indexOf('\nfunction showRowMovement('));
  const scope = houseScope({showRowMovement() {}, animateRowFromPreviousPosition() {}});
  vm.runInContext(source, scope);
  const table = fakeMinutesTable([
    {id: 'a', name: 'A', position: 1, height: 76, minutes: 10, fatigue: 0},
    {id: 'b', name: 'B', position: 2, height: 77, minutes: 20, fatigue: 0},
  ]);
  scope.state.rotationDraft = {a: 30, b: 20};
  table.dataset.houseDragging = 'true';
  scope.reorderMinutesTable(table);
  assert.deepEqual(table.rows.map((row) => row.style.gridRow), ['', ''], 'no row moves mid-drag');
  delete table.dataset.houseDragging;
  scope.reorderMinutesTable(table);
  assert.deepEqual(table.rows.map((row) => row.style.gridRow), ['2', '3'], 'after release the 30-minute player is first');
  assert.match(app, /addEventListener\("pointerdown", \(\) => \{ if \(table && !input\.disabled\) table\.dataset\.houseDragging = "true"; \}\)/);
});

test('standings sort by any column but # always shows the real seed and the lines show only in seed order', () => {
  const scope = houseScope();
  const cell = (text) => ({textContent: text});
  const row = (seed, team, record, pct, gb) => ({
    dataset: {houseOrder: String(seed - 1)},
    querySelectorAll: () => [cell(String(seed)), cell(''), cell(record), cell(pct), cell(gb)],
    querySelector: () => cell(team),
  });
  const rows = [row(1, 'PHI', '4-0', '1.000', '—'), row(2, 'CLE', '4-1', '.800', '.5'), row(3, 'ATL', '3-2', '.600', '1.5'), row(4, 'BOS', '3-2', '.600', '1.5')];
  const order = (key, direction) => scope.houseOrderedRows('standings', rows, {key, direction}).map((r) => r.querySelectorAll()[0].textContent).join('');
  assert.equal(order('seed', 'asc'), '1234');
  assert.equal(order('team', 'asc'), '3421');
  assert.equal(order('gb', 'asc'), '1234', 'the leader (—) is 0 games back; ties keep seed order');
  assert.equal(order('pct', 'asc'), '3421');
  assert.equal(order('record', 'desc'), '1234');
  const css = fs.readFileSync(path.join(gui, 'house-table.css'), 'utf8');
  assert.match(css, /\[data-house-table="standings"\]:not\(\[data-house-key="seed"\]\) > \[data-house-row\]:is\(\.playoff-line, \.play-in-line\)/);
  const standings = app.slice(app.indexOf('function seasonStandingsCard('), app.indexOf('\nfunction setStandingsCardExpanded'));
  assert.match(standings, /<span>\$\{index \+ 1\}<\/span>/, '# is printed from the seed, never from the sorted position');
});

test('house table CSS: double header rule, small bold headers, stripes, whole-row hover, sorted fill, one bar style', () => {
  const css = fs.readFileSync(path.join(gui, 'house-table.css'), 'utf8');
  assert.match(css, /\[data-house-head\] \{\s*border-bottom: 2px solid/);
  assert.match(css, /\[data-house-head\] > \* \{[^}]*font-size: 9px !important;[^}]*font-weight: var\(--gm-weight-bold\) !important;/);
  assert.match(css, /\[data-house-row\]\[data-house-alt\] \{ background-color: var\(--house-row-alt\) !important; \}/);
  assert.match(css, /\[data-house-row\]:is\(:hover, :focus-within\) \{ background-color: var\(--house-row-hover\) !important; \}/);
  assert.match(css, /--house-sorted-cell: rgba\(118, 156, 190, \.28\);/);
  assert.match(css, /--house-bar-track: transparent;/, 'no dark track behind table bars (style guide)');
  const index = fs.readFileSync(path.join(gui, 'index.html'), 'utf8');
  assert.ok(index.indexOf('house-table.css') > index.indexOf('card-board.css'), 'house styles load after the card board');
  assert.ok(index.indexOf('house-table.js') < index.indexOf('/app.js'), 'the sort helper loads before app.js');
  for (const id of ['minutes', 'development', 'staff', 'staff-market', 'standings', 'opponent']) {
    assert.ok(app.includes(`data-house-table="${id}"`), `${id} uses the shared table system`);
  }
});

test('window icons: every window type has its own icon, unknown windows share one fallback', () => {
  const scope = {window: {}};
  vm.createContext(scope);
  vm.runInContext(fs.readFileSync(path.join(gui, 'window-icons.js'), 'utf8'), scope);
  const {WindowIcons} = scope.window;
  const board = fs.readFileSync(path.join(gui, 'card-board.js'), 'utf8');
  const boardIds = [...board.matchAll(/^\s+\["([a-z-]+)", "[^"]+", "[^"]+"\],?$/gm)].map((m) => m[1]);
  assert.ok(boardIds.includes('minutes') && boardIds.includes('team-wants'));
  const phaseSections = app.slice(app.indexOf('function seasonalClipboardCards('), app.indexOf('const legal = clipboardLegalActions();', app.indexOf('function seasonalClipboardCards(')));
  const phaseIds = [];
  let phase = '';
  for (const line of phaseSections.split('\n')) {
    phase = /^\s+(\w+): \[/.exec(line)?.[1] || phase;
    for (const [, name] of line.matchAll(/\["(\w+)", "[^"]+", "[^"]+"\]/g)) phaseIds.push(`phase-${phase}-${name}`);
  }
  assert.ok(phaseIds.length >= 15, `found ${phaseIds.length} phase windows`);
  const kinds = ['player', 'coach', 'fantasy', 'prospect', 'freeAgent', 'extension'];
  const glyphs = new Map();
  for (const id of [...boardIds, ...phaseIds]) {
    const {glyph} = WindowIcons.entry(id);
    assert.notEqual(glyph, 'window', `${id} has its own icon`);
    assert.ok(!glyphs.has(glyph), `${id} and ${glyphs.get(glyph)} share ${glyph}`);
    glyphs.set(glyph, id);
  }
  for (const kind of kinds) {
    const {glyph} = WindowIcons.entry('player-card-7', kind);
    assert.ok(!glyphs.has(glyph), `card ${kind} is distinct`);
    glyphs.set(glyph, kind);
  }
  assert.equal(WindowIcons.entry('player-card-3').glyph, 'profile', 'player cards default to the player icon');
  assert.equal(WindowIcons.entry('something-new').glyph, 'window');
  assert.equal(WindowIcons.entry('something-new').group, 'fallback');
  assert.match(WindowIcons.svg('minutes'), /<svg class="window-icon" data-window-icon="stopwatch" viewBox="0 0 32 32"/);
  assert.match(board, /card-board-window-switcher-icon" aria-hidden="true">\$\{windowIcon\(id\) \|\| window\.CardVisuals\.icon\(id\)\}/);
  // Title bars carry no icon (taste deck 2026-11-23); the switcher keeps them.
  assert.match(board, /<span class="card-board-window-mark" aria-hidden="true"><\/span>/);
  assert.match(app, /iconKind:entry\.kind/);
});
