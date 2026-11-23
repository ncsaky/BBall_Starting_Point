// TRADE-MARKET: the trade window shows the market around the user's offer in plain words: a better offer for a
// shopped player, a declined final offer, a final counter, and the assistant GM's read on the partner's front office
// (words only, no numbers, sharpening with dealings).
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

function context() {
  const ctx = {
    state: {home: {save: {user_team: {id: 'gsw'}}}, tradeCounterChain: {partner: 'MEM', rounds: []}},
    teamLabel: (team) => String(team || '').replace('team_', '').toUpperCase(),
    userTeam: () => 'GSW',
    textValue: (value) => String(value ?? ''),
    escapeHtml: (value) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    tradeLegalityBadge: () => '', tradeLegalityIssues: () => '',
  };
  vm.createContext(ctx);
  vm.runInContext(`${extract('tradeReadout')}\n${extract('tradeCounterOffer')}\n${extract('frontOfficeReadMarkup')}
this.tradeReadout = tradeReadout; this.frontOfficeReadMarkup = frontOfficeReadMarkup;`, ctx);
  return ctx;
}

const read = {abbrev: 'MEM', precision: 'rough', lines: [
  {trait: 'savvy', text: 'Seems error-prone at judging value.'},
  {trait: 'patience', text: 'Seems impatient in negotiations.'},
  {trait: 'habit', text: 'From your dealings: it overrates its own players.'}]};

test('a better offer for a shopped player is shown, with the partner read', () => {
  const ctx = context();
  const html = ctx.tradeReadout({legality: {status: 'legal'},
    evaluations: [{perspective_team_id: 'team_mem', accepted: false}],
    market_competition: {beaten: true, text: 'MEM has a better offer for Ty Jerome (3 other teams interested; decision by 2027-02-05). Beat it to get him.'},
    partner_read: read});
  assert.match(html, /Declines|Counters/); // trade-room redo: the answer reads as one word under the dial
  assert.match(html, /class="trade-market-competition is-beaten"/);
  assert.match(html, /MEM has a better offer for Ty Jerome/);
  assert.match(html, /class="front-office-read"/);
  assert.match(html, /Seems impatient in negotiations\./);
  assert.match(html, /from your first dealings/);
});

test('a declined final offer says talks are over; a final counter says take it or leave it', () => {
  const ctx = context();
  const declined = ctx.tradeReadout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_mem', accepted: false}],
    final_declined: 'MEM turned down your final offer. Talks on this deal are over for now.'});
  assert.match(declined, /Final offer declined:/);
  const counter = {proposal: {id: 'c', from_team_id: 'gsw', to_team_id: 'team_mem', from_assets: [{label: 'Buddy Hield'}],
    to_assets: [{label: 'Ty Jerome'}]}, counter: {text: "MEM asked for a 2029 second-round pick as well. This is MEM's final offer: take it or leave it.",
    last_round: true, final_offer: true}};
  const finalCounter = ctx.tradeReadout({legality: {status: 'legal'}, evaluations: [{perspective_team_id: 'team_mem', accepted: false}],
    counter_offer: counter});
  assert.match(finalCounter, /final offer: take it or leave it/);
  assert.doesNotMatch(finalCounter, /This is its last counter/);
});

test('the read has no numbers and says when there is no read yet', () => {
  const ctx = context();
  const html = ctx.frontOfficeReadMarkup(read);
  assert.doesNotMatch(html.replace(/<[^>]+>/g, ''), /\d/);
  assert.match(ctx.frontOfficeReadMarkup({lines: []}), /No clear read yet/);
});

test('the Trade Market tab, board and assistant link are wired', () => {
  assert.match(app, /data-trade-tab="market"/);
  assert.match(app, /action\("trade_market", savePayload\(\)\)/);
  assert.match(app, /message\.target === "trade-market"/);
  assert.match(app, /async function openTradeMarketBoard/);
  assert.match(app, /final_offer: Boolean\(state\.tradeFinalOffer\)/);
  const phone = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/assistant-phone.js'), 'utf8');
  assert.match(phone, /"trade-market"\) return "Trade market"/);
});
