const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');
const slice = (from, to) => app.slice(app.indexOf(from), app.indexOf(to));

test('there is one signing page, opened as the player page, and no side builder', () => {
  assert.doesNotMatch(app, /freeAgencyOfferBuilderPanel/);
  assert.doesNotMatch(read('card-pages.js'), /phase-free_agency-selected/);
  assert.match(app, /player-card-page player-card-page--extension player-card-page--signing/);
  assert.match(app, /kind: "signing", context,/);
  assert.match(app, /data-offseason-negotiate\]"\)\.forEach\(\(button\) => button\.addEventListener\("click", \(\) => openFreeAgentNegotiation/);
});

test('a signing that goes through closes his page, whichever way it went through', () => {
  for (const [from, to] of [
    ['async function submitFreeAgentOffer(', 'state.freeAgentOfferResults[`'],
    ['async function freeAgencyRosterEdgeSign(', '// FA-REAL slice 3: the offer-sheet terms'],
    ['async function freeAgencySignAndTrade(', 'async function freeAgencyRosterEdgeSign('],
  ]) assert.match(slice(from, to), /closeSigningCards\(player\.id\)/, from);
});

test('the salary slider only offers salaries that can really be paid', () => {
  const context = {state: {data: {freeagency: {}}}, freeAgencyMinimum: () => 1.2, freeAgencyMaxOffer: () => 0};
  vm.createContext(context);
  vm.runInContext(slice('function freeAgencyPlayerMinimum(', '// "Fits our room"'), context);
  const player = {legal: {min_millions: 2.725, most_you_can_pay_millions: 6.27}};
  assert.equal(context.freeAgencyPlayerMinimum(player, {}), 2.8);
  assert.equal(context.freeAgencyPlayerMaximum(player, {}), 6.2);
  const round = {legal: {min_millions: 3.0, most_you_can_pay_millions: 15.6}};
  assert.equal(context.freeAgencyPlayerMinimum(round, {}), 3);
  assert.equal(context.freeAgencyPlayerMaximum(round, {}), 15.6);
});

test('a reason the offer sheet already gives is not printed a second time', () => {
  const context = {escapeHtml: String, escapeAttr: String, money: String};
  vm.createContext(context);
  vm.runInContext(slice('function freeAgencyPayMarkup(', '// FA-REAL: your books as the cap ledger sees them'), context);
  const preview = {quote: {ok: false, message: 'Not yet.', routes: []}};
  assert.match(context.freeAgencyPayMarkup(preview), /Not yet\./);
  assert.doesNotMatch(context.freeAgencyPayMarkup(preview, 'Not yet.'), /Not yet\./);
});

test('no legal way to pay: each reason is printed once', () => {
  const context = {escapeHtml: String, escapeAttr: String, money: String};
  vm.createContext(context);
  vm.runInContext(slice('function freeAgencyPayMarkup(', '// FA-REAL: your books as the cap ledger sees them'), context);
  const routes = [{route: 'cap_room', short: 'Cap room', reason: 'Not enough cap room.', ok: false}, {route: 'minimum', short: 'Minimum', reason: 'At most 2 years.', ok: false}];
  const markup = context.freeAgencyPayMarkup({quote: {ok: false, message: 'BOS has no legal way to pay this. Cap room: Not enough cap room.', routes}});
  assert.match(markup, /<p class="fa-pay-blocked">BOS has no legal way to pay this\.<\/p>/);
  assert.equal(markup.split('Not enough cap room.').length, 2);
});

test('the wire has one row height and no dots; the pinned button survives a short window', () => {
  const full = read('full-pages.css');
  assert.match(full, /\.fa-wire-row \{ height: 64px; \}/);
  assert.match(full, /\.fa-wire-row > div > span \{[^}]*text-overflow: clip !important/);
  const sheet = read('extension-window.css');
  const short = sheet.slice(sheet.indexOf('/* A short window: whether he signs'));
  assert.match(short, /@media \(max-height: 860px\)/);
  assert.match(short, /\.fa-builder-scroll \{ flex: 1 1 0 !important;[^}]*overflow-y: auto !important/);
  assert.match(short, /\.signing-view \{ flex: 0 0 auto !important; overflow: visible !important; \}/);
});

test('the free-agent list only offers the Trade Room while trading is open', () => {
  assert.match(app, /\$\{tradingOpen\(\) \? `<button type="button" class="ui-command" data-fa-open-trade>Trade Room<\/button>` : ""\}/);
});
