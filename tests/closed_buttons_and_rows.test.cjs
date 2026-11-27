const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');
const pages = read('card-pages.js');
const helpers = app.slice(app.indexOf('function clipboardLegalActions('), app.indexOf('if (typeof document !== "undefined" && document.addEventListener) document.addEventListener("gm:pagechange"'));

function scope(legal, status) {
  const context = {state: {home: {save: {legal_actions: legal}}, data: {freeagency: {state: {status}}}, clipboardPlayerCards: []}, escapeAttr: String, escapeHtml: String, CSS: {escape: String}};
  vm.createContext(context);
  vm.runInContext(helpers, context);
  return context;
}

test('trading and signings are open only while the game lists them', () => {
  assert.equal(scope(['trades']).tradingOpen(), true);
  assert.equal(scope(['draft_trades']).tradingOpen(), true);
  assert.equal(scope(['advance']).tradingOpen(), false);
  assert.equal(scope(['free_agent_signings']).signingsOpen(), true);
  assert.equal(scope(['free_agent_signings'], 'completed').signingsOpen(), false);
  assert.equal(scope(['trades']).signingsOpen(), false);
});

test('closed: no trade buttons, no Find column, no free agency tab', () => {
  assert.match(pages, /id: "trades", [^\n]*when: \(\) => typeof tradingOpen !== "function" \|\| tradingOpen\(\)/);
  assert.match(pages, /controlsEl\.innerHTML = tradingClosed \|\| options\.toolbarActions\?\.tradeDisabled \? lockNote : `<button/);
  assert.match(pages, /id: "free-agency", [^\n]*when: \(\) => typeof signingsOpen !== "function" \|\| signingsOpen\(\)/);
  assert.match(app, /\["find","Find",58\]\]\.filter\(\(\[key\]\)=>key!=="find" \|\| typeof tradingOpen!=="function" \|\| tradingOpen\(\)\);/);
  assert.match(read('card-pages.css'), /\.pages-slot\.is-locked :is\(\.block-find-trade, \[data-want-add\][^{]*\{ visibility: hidden !important; \}/);
  assert.match(read('home-front.js'), /open \? `<button type="button" data-front-market>Trade talk<\/button>` : "<span>Trade talk<\/span>"/);
});

test('leaving a page closes a coach card, and a pinned one stays', () => {
  const context = scope([]);
  const closed = [];
  context.state.clipboardPlayerCards = [{id: 'a', kind: 'coach'}, {id: 'b', kind: 'coach'}, {id: 'c', kind: 'player'}];
  context.document = {querySelector: (selector) => {
    const id = selector.match(/"([a-z])"/)[1];
    return {click: () => closed.push(id), closest: () => ({classList: {contains: () => id === 'b'}})};
  }};
  context.closeCoachCards();
  assert.deepEqual(closed, ['a']);
  assert.deepEqual(context.state.clipboardPlayerCards.map((card) => card.id), ['b', 'c']);
  assert.match(pages, /new CustomEvent\("gm:pagechange"/);
});

test('explaining lines sit behind an i', () => {
  assert.match(app, /<h3>\$\{escapeHtml\(title\)\}\$\{pageInfoMark\(note\)\}<\/h3>/);
  assert.doesNotMatch(app, /<p class="draft-board-note">/);
  assert.match(app, /\$\{pageInfoMark\(`Consensus: the median of all 30 teams' scouting\./);
});
