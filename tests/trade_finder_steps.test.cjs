const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const source = read('app.js');
const code = source.slice(source.indexOf('function renderTradeFinder('), source.indexOf('function hydrateTradeSelection('));

function render(overrides = {}) {
  const state = {selectedFrom: [], selectedTo: [], tradeResults: [], tradeSearchCompleted: false, tradePickRules: [], data: {tradeUser: {assets: []}}, ...overrides};
  const body = {innerHTML: '', querySelector: () => ({addEventListener() {}}), querySelectorAll: () => []};
  const context = {
    state, userTeam: () => 'OKC', teamLogoSrc: () => '', teamBrandStyle: () => '', escapeHtml: String, escapeAttr: String,
    tradeCapImpactRows: () => [], tradeCapDeltaChart: () => '', tradeFinderPayrollChart: () => '<div class="payroll"></div>',
    tradeDealTile: (asset) => `<li class="tr-tile">${asset.id}</li>`, tradePickTermsMarkup: () => '<div class="terms"></div>',
    tradePickRuleErrors: () => [], assetColumn: () => '<section class="tr-picker"></section>',
    tradeResultCards: (results) => results.length ? `cards:${results.length}` : 'No matching offers',
    wireTradeAssetControls() {}, wireTradeInsightPagers() {}, wireDashboardPlayerCards() {},
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  context.renderTradeFinder({querySelector: () => body});
  return body.innerHTML;
}

test('the first step holds the list, the chosen assets and the payroll; the trades wait for a search', () => {
  const html = render({selectedFrom: [{kind: 'player', id: 'a'}]});
  assert.match(html, /is-pick/);
  assert.match(html, /tr-picker/);
  assert.match(html, /<li class="tr-tile">a<\/li>/);
  assert.match(html, /payroll/);
  assert.match(html, /data-finder-view="results"[^>]*disabled/);
  assert.match(html, /id="runTrade"[^>]*>Find trades/);
  assert.doesNotMatch(html, /id="tradeResults"/);
});

test('found trades have a page of their own, with their number on the step', () => {
  const html = render({tradeFinderView: 'results', tradeSearchCompleted: true, tradeResults: [{}, {}]});
  assert.match(html, /is-results/);
  assert.match(html, /cards:2/);
  assert.match(html, /Found trades<b class="tr-steps-found">2<\/b>/);
  assert.doesNotMatch(html, /tr-picker|id="runTrade"/);
  assert.match(html, /id="clearTradeMarket"/);
});

test('a search with nothing found says so on the second page', () => {
  assert.match(render({tradeFinderView: 'results', tradeSearchCompleted: true}), /No matching offers/);
});

test('changed assets drop back to the first step; a search for another team stays on the second', () => {
  assert.match(render({tradeFinderView: 'results'}), /is-pick/);
  const searching = render({tradeFinderView: 'results', tradeFinderSearching: true});
  assert.match(searching, /is-results/);
  assert.match(searching, /Finding trades…/);
  assert.doesNotMatch(searching, /No matching offers/);
});

test('pick conditions show only when a pick or a condition is there', () => {
  assert.doesNotMatch(render({selectedFrom: [{kind: 'player', id: 'a'}]}), /class="terms"/);
  assert.match(render({selectedFrom: [{kind: 'pick', id: 'p'}]}), /class="terms"/);
});

test('a ticked box in the trade room is drawn ticked', () => {
  assert.match(read('popups.css'), /modal-trade-room input\[type="checkbox"\]:checked \{[^}]*var\(--gm-pick\) url\(/);
});
