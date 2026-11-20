// TRADE-TAXPOOL: the offers panel shows why the AI teams made an offer (trade_reasons.text).
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

function offerCardIn() {
  const context = {
    teamLabel: (team) => String(team || '').toUpperCase(),
    escapeHtml: (value) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    tradeLegalityBadge: () => '', tradeLegalityIssues: () => '', tradeCandidateInsights: () => '',
    incomingOfferPackage: () => '<div class="package"></div>', tradeReceipts: () => [],
  };
  vm.createContext(context);
  vm.runInContext(`${extract('offerCard')}; this.offerCard = offerCard;`, context);
  return context.offerCard;
}

test('an offer with reasons shows them; one without shows nothing extra', () => {
  const offerCard = offerCardIn();
  const offer = {proposal: {id: 'x', from_team_id: 'a', to_team_id: 'b'}, legality: {status: 'legal'},
    trade_reasons: {text: 'DEN moved Zeke Nnaji ($7.5M) to cut its luxury tax <by about $8.8M>'}};
  const html = offerCard(offer, 0);
  assert.match(html, /class="incoming-offer-reason"/);
  assert.match(html, /DEN moved Zeke Nnaji/);
  assert.match(html, /&lt;by about \$8\.8M&gt;/);
  const plain = offerCard({proposal: {id: 'y'}, legality: {status: 'legal'}}, 1);
  assert.doesNotMatch(plain, /incoming-offer-reason/);
});
