// UI polish pass (2026-11-21): dialog layering, bracket fit, dialog icons, start-screen labels, league wire dates.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');

function zIndexOf(css, selector) {
  const start = css.indexOf(`${selector} {`);
  assert.ok(start >= 0, `${selector} rule exists`);
  const block = css.slice(start, css.indexOf('}', start));
  return Number(/z-index:\s*(\d+)/.exec(block)?.[1]);
}

test('dialogs and messages sit above every board window', () => {
  const styles = read('styles.css');
  // Board windows are stacked 1..N by how recently they were raised; N is the number of windows in the layout.
  const board = read('card-board.js');
  assert.match(board, /layout\[key\]\.z = index \+ 1;/, 'windows are restacked from 1');
  const windowsInLayout = 120; // generous: season, assets, phase and player-card windows together
  assert.ok(zIndexOf(styles, '.modal-root') > windowsInLayout, 'dialogs above windows');
  assert.ok(zIndexOf(styles, '.toast') > zIndexOf(styles, '.modal-root'), 'messages above dialogs');
  assert.ok(zIndexOf(styles, '.toast') < 20000, 'messages stay below the tutorial and slideshow layers');
});

test('the local server keeps a long enough waiting line for a full page load', () => {
  const server = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/app_server.py'), 'utf8');
  const size = Number(/class GuiThreadingHTTPServer[\s\S]*?request_queue_size = (\d+)/.exec(server)?.[1]);
  assert.ok(size >= 64, `request queue ${size}`);
});

test('polish files load after the shared styles and scripts', () => {
  const index = read('index.html');
  assert.ok(index.indexOf('ui-polish.css') > index.indexOf('house-table.css'));
  assert.ok(index.indexOf('ui-polish.js') > index.indexOf('/app.js'));
});

function bracketHarness({shellWidth, shellHeight, bracketWidth, bracketHeight}) {
  const hostStyle = new Map();
  const host = {style: {getPropertyValue: (k) => hostStyle.get(k) || '', setProperty: (k, v) => hostStyle.set(k, v)}};
  const bracket = {offsetWidth: bracketWidth, offsetHeight: bracketHeight};
  const shell = {
    isConnected: true, clientWidth: shellWidth, clientHeight: shellHeight,
    classList: {add() {}}, getClientRects: () => [1],
    querySelector: () => bracket, closest: () => host,
  };
  const context = {
    document: {readyState: 'complete', body: {}, querySelectorAll: () => [shell]},
    window: {addEventListener() {}},
    getComputedStyle: () => ({paddingLeft: '6', paddingRight: '6', paddingTop: '6', paddingBottom: '6'}),
    requestAnimationFrame: (fn) => fn(),
    MutationObserver: class { observe() {} },
    ResizeObserver: class { observe() {} },
  };
  vm.createContext(context);
  vm.runInContext(read('ui-polish.js'), context);
  context.window.UiPolish.fitBrackets();
  return {fit: Number(hostStyle.get('--bracket-fit')), shift: parseFloat(hostStyle.get('--bracket-shift'))};
}

test('the playoff bracket scales down to its window and never up', () => {
  const narrow = bracketHarness({shellWidth: 1000, shellHeight: 600, bracketWidth: 1398, bracketHeight: 456});
  assert.ok(Math.abs(narrow.fit - 988 / 1398) < 1e-3, `fit ${narrow.fit}`);
  assert.ok(narrow.shift < 1, 'a width-limited bracket starts at the left edge');
  const short = bracketHarness({shellWidth: 1500, shellHeight: 312, bracketWidth: 1488, bracketHeight: 456});
  assert.ok(Math.abs(short.fit - 300 / 456) < 1e-3, 'height limits too');
  assert.ok(short.shift > 0, 'a height-limited bracket is centred');
  const roomy = bracketHarness({shellWidth: 1600, shellHeight: 700, bracketWidth: 1588, bracketHeight: 456});
  assert.equal(roomy.fit, 1);
});

test('bracket placeholders stay quiet and in their box', () => {
  const css = read('ui-polish.css');
  assert.match(css, /\.series-team:not\(:has\(img\)\) strong \{[^}]*white-space: nowrap;/);
  assert.match(css, /\.series-team:not\(:has\(img\)\) span \{ visibility: hidden; \}/);
});

test('dialogs with a window title bar get their own icon; trade dialogs keep the plain mark', () => {
  const scope = {window: {}};
  vm.createContext(scope);
  vm.runInContext(read('window-icons.js'), scope);
  const {WindowIcons} = scope.window;
  for (const kind of ['boxScore', 'playoffBoxScore', 'leagueLeaders', 'playerFinder', 'dashboardSettings', 'issueReport', 'champion', 'standings']) {
    assert.notEqual(WindowIcons.entry(`modal:${kind}`).glyph, 'window', `${kind} has an icon`);
  }
  const mark = new Function('window', `${app.slice(app.indexOf('function modalWindowMark('), app.indexOf('function playerHeadshotMarkup('))}; return modalWindowMark;`)(scope.window);
  assert.match(mark('boxScore'), /has-window-icon[\s\S]*data-window-icon="versus"/);
  assert.doesNotMatch(mark('tradeRoom'), /has-window-icon/);
  assert.match(app, /\$\{hasClipboardTitlebar \? modalWindowMark\(state\.modal\.kind\) : ""\}/);
});

test('league wire and full standings show written dates, not raw ISO dates', () => {
  const wire = app.slice(app.indexOf('function seasonLeagueWire('), app.indexOf('function setLeagueWireCardExpanded('));
  assert.doesNotMatch(wire, /escapeHtml\(normalized\.date\)/);
  // The activity list writes the short date; the ticker adds the year to last summer's moves.
  assert.equal((wire.match(/formatDashboardShortDate\(normalized\.date\)/g) || []).length, 1);
  assert.match(wire, /escapeHtml\(wireTickerDate\(normalized\.date, /);
  const standings = app.slice(app.indexOf('function openStandingsModal('), app.indexOf('function dashboardMonthCalendar('));
  assert.match(standings, /formatWrittenDate\(state\.home\?\.save\?\.current_date\)/);
  assert.match(standings, /logos: true/);
});

test('shortcut tooltips do not repeat the key ("Close (Esc) (Esc)")', () => {
  const ui = read('interface.js');
  assert.match(ui, /name\.endsWith\(`\(\$\{keys\}\)`\) \? name : `\$\{name\} \(\$\{keys\}\)`/);
});

test('creating a save says it is working and always restores the button', async () => {
  const body = app.slice(app.indexOf('async function createSave()'), app.indexOf('async function createMultiplayerLobby()'));
  const button = {textContent: 'Create New Save', attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }};
  let seen = '';
  const context = {
    els: {teamSelect: {value: 'BOS'}, gameModeSelect: {value: 'standard'}, saveName: {value: ''}, createSave: button},
    action: async () => { seen = `${button.textContent}|${button.attrs['aria-busy']}`; throw new Error('server down'); },
  };
  vm.createContext(context);
  vm.runInContext(`${body}; this.createSave = createSave;`, context);
  await assert.rejects(context.createSave(), /server down/);
  assert.equal(seen, 'Building your league…|true');
  assert.equal(button.textContent, 'Create New Save');
  assert.equal(button.attrs['aria-busy'], undefined);
});
