// The trade room's Market view (trade-market.js / trade-market.css).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

function load() {
  const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const context = {escapeHtml: esc, escapeAttr: esc, formatDashboardShortDate: () => 'Dec 22', userTeam: () => 'OKC', teamLogoSrc: () => '/logo.png', tradeRatingColor: () => 'gold'};
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(read('trade-market.js'), context);
  return context.window.TradeMarketView;
}

const rows = [
  {player_id: 'a', player_name: 'Sold Guy', team: 'DET', stage: 'sold', sold_to: 'BOS', interested_count: 9},
  {player_id: 'b', player_name: 'Open Guy', team: 'NOP', stage: 'taking offers', interested_count: 3, decide_by: '2026-12-22'},
  {player_id: 'c', player_name: 'War Guy', team: 'DEN', stage: 'bidding war', rounds: 2, interested_count: 1},
];
const order = (html) => [...html.matchAll(/class="tm-name">([^<]*)/g)].map((m) => m[1].trim().replace(/\s+$/, ''));

test('bidding wars sort first and sold players last', () => {
  const html = load().markup({shopped: rows}, {});
  assert.deepEqual(order(html), ['War Guy', 'Open Guy', 'Sold Guy']);
});

test('a sold player and the user\'s own player get no offer button', () => {
  const html = load().markup({shopped: [...rows, {player_id: 'd', player_name: 'Mine', team: 'OKC'}]}, {});
  assert.equal((html.match(/data-market-build=/g) || []).length, 2);
  assert.doesNotMatch(html, /data-market-player="a"/);
  assert.doesNotMatch(html, /data-market-player="d"/);
});

test('data is escaped', () => {
  const html = load().markup({shopped: [{player_id: 'x', player_name: '<b>Evil</b>', team: 'DEN', why: ['<i>x</i>']}]}, {});
  assert.doesNotMatch(html, /<b>Evil|<i>x/);
  assert.match(html, /&lt;b&gt;Evil/);
});

test('dates are short', () => {
  const html = load().markup({shopped: rows}, {});
  assert.match(html, /Decide by Dec 22/);
  assert.doesNotMatch(html, /2026-12-22/);
});

test('a row with only a name and team prints no "undefined"', () => {
  const html = load().markup({shopped: [{player_name: 'Bare', team: 'DEN'}]}, {});
  assert.doesNotMatch(html, /undefined|null|NaN/);
});

test('an empty market shows one calm line', () => {
  assert.match(load().markup({shopped: []}, {}), /tm-empty/);
});

test('the sheet scopes every rule and reads the shared values', () => {
  const raw = read('trade-market.css').replace(/\/\*[\s\S]*?\*\//g, '');
  const css = raw.replace(/rgba?\([^)]*\)/g, '');
  assert.doesNotMatch(css, /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d/);
  assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, 'no hex colours');
  const selectors = [];
  for (const m of raw.replace(/@media[^{]*\{/g, '').matchAll(/([^{}]+)\{/g)) selectors.push(...m[1].split(',').map((s) => s.trim()).filter(Boolean));
  assert.ok(selectors.length > 20);
  for (const s of selectors) {
    assert.match(s, /#modalRoot/, s.slice(0, 100));
    assert.match(s, /\.tm-/, s.slice(0, 100));
  }
});
