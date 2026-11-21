// BIDWAR-PRICE: the Trade Market board says why your offer leads or trails (the seller's own comparison) and why a
// sold player went where he did.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');

function extract(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} not found`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next);
}

function render(rows) {
  const body = {innerHTML: '', querySelector: () => null, querySelectorAll: () => []};
  const ctx = {
    state: {data: {tradeMarket: {shopped: rows, final_offers: [], front_offices: {}}}, sorts: {}, tradePartner: null},
    textValue: (value) => String(value ?? ''),
    escapeHtml: (value) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    escapeAttr: (value) => String(value).replace(/"/g, '&quot;'),
    html: (markup) => ({markup}),
    table: (headers, items, cells) => items.map(item => cells(item).map(c => (c && c.markup) || String(c)).join(' | ')).join('\n'),
    playerHeadshotMarkup: () => '',
    frontOfficeReadMarkup: () => '',
  };
  vm.createContext(ctx);
  vm.runInContext(`${extract('renderTradeMarket')}\nthis.renderTradeMarket = renderTradeMarket;`, ctx);
  ctx.renderTradeMarket({querySelector: () => body});
  return body.innerHTML;
}

test('your offer shows why it trails, in the seller\'s terms', () => {
  const markup = render([{player_name: 'Ty Jerome', team: 'MEM', why: [], interested_count: 3, interested: [],
    stage: 'bidding war', rounds: 2, decide_by: '2027-02-05', your_offer: 'outbid', you_interested: true,
    your_offer_note: "HOU's offer was worth more to MEM; you'd need to add about a late first-round pick."}]);
  assert.match(markup, /You have been outbid<small[^>]*>HOU's offer was worth more to MEM; you'd need to add about a late first-round pick\./);
});

test('a sold player carries the seller\'s reason', () => {
  const markup = render([{player_name: 'Ty Jerome', team: 'MEM', why: [], interested_count: 3, interested: [],
    stage: 'sold', sold_to: 'LAL', rounds: 2, decide_by: '2027-02-05', your_offer: null,
    sale_note: "LAL's offer was worth the most to MEM, more than BOS's."}]);
  assert.match(markup, /title="LAL's offer was worth the most to MEM, more than BOS's\.">Sold to LAL/);
});
