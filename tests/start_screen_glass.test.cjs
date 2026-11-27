const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const css = read('startup.css').replace(/\/\*[\s\S]*?\*\//g, '');
const app = read('app.js');

test('the start screen reads the shared values: no literal sizes, numeric weights, italic or old fonts', () => {
  assert.doesNotMatch(css, /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d|Arial|Helvetica/);
});

test('nothing on the start screen is filled white or grey: panels are the dark glass', () => {
  // The old panel fills: white, off-white and the blue-grey bar.
  assert.doesNotMatch(css, /background(-color)?\s*:\s*(#fff(fff)?\b|#f4f5f6|#e5ebf0|#e6eaee|#c5d5e3|white\b)/i);
  assert.match(css, /\.startup-screen \.startup-grid > \.startup-pane \{[^}]*var\(--gm-glass-popup\)/s);
  assert.match(css, /\.multiplayer-lobby \{[^}]*var\(--gm-glass-popup\)/s);
  assert.doesNotMatch(read('ui-polish.css'), /startup-primary-action/);
});

test('the start screen uses the game\'s own menus; the team wheel stays the team control', () => {
  const menus = read('glass-select.js');
  assert.match(menus, /const SCOPE = "[^"]*#startupScreen"/);
  assert.match(menus, /startup-team-select-native"\)\) return;/);
});

test('the lobby is redrawn only when something on it changed', () => {
  const code = app.slice(app.indexOf('function renderStartup()'), app.indexOf('function wireMultiplayerLobby()'));
  let writes = 0, wired = 0, html = '';
  const lobby = {hidden: true, set innerHTML(value) { writes += 1; html = value; }, get innerHTML() { return html; }};
  const grid = {hidden: false};
  const state = {multiplayer: {manager: {id: 'm'}, league: {code: 'ABC123', name: 'League', managers: [], teams: [], settings: {}}}};
  const context = {
    state, escapeHtml: String, escapeAttr: String, updateStartupSaveControls() {}, wireMultiplayerLobby: () => { wired += 1; },
    document: {getElementById: () => null},
    els: {content: {}, multiplayerLobby: lobby, startupScreen: {querySelector: () => grid}},
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  context.renderStartup();
  context.renderStartup();
  assert.equal(writes, 1);
  assert.equal(wired, 1);
  state.multiplayer.league.name = 'Renamed';
  context.renderStartup();
  assert.equal(writes, 2);
  state.multiplayer.league = null;
  context.renderStartup();
  state.multiplayer.league = {code: 'ABC123', name: 'Renamed', managers: [], teams: [], settings: {}};
  context.renderStartup();
  assert.match(html, /Renamed/, 'a lobby left and entered again is drawn again');
});
