// FA-REAL slice 2: the offseason checklist window shows the four stops with their dates, one row per decision sorted
// by deadline, plain-word statuses, and the buttons for the user's own decisions only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');

function extract(name, kind = 'function') {
  const marker = kind === 'function' ? `function ${name}(` : `const ${name} =`;
  const start = app.indexOf(marker);
  assert.ok(start >= 0, `${name} not found`);
  const next = app.indexOf('\nfunction ', start + 1);
  const nextConst = app.indexOf('\nconst ', start + 1);
  const end = Math.min(...[next, nextConst].filter((i) => i > start));
  return app.slice(start, end);
}

function context() {
  const ctx = {
    state: {home: {save: {current_date: '2027-06-20'}}, data: {freeagency: {}}},
    escapeHtml: (value) => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    escapeAttr: (value) => String(value ?? '').replace(/"/g, '&quot;'),
    money: (value) => `$${Number(value).toFixed(1)}M`,
    signedMoney: (value) => `${Number(value) < 0 ? '-' : '+'}$${Math.abs(Number(value)).toFixed(1)}M`,
    rowLabel: (value) => String(value || ''),
    FREE_AGENCY_SIGNING_KINDS: new Set(['free_agent_signing']),
  };
  vm.createContext(ctx);
  const names = ['shortDate', 'offseasonStopTimeline', 'offseasonItemStatus', 'offseasonItemMoney', 'offseasonItemActions',
    'offseasonChecklistTable', 'signingDayRecap', 'offseasonChecklistPanel'];
  vm.runInContext(`${extract('OFFSEASON_STOPS', 'const')}\n${extract('OFFSEASON_ITEM_LABELS', 'const')}\n${names.map((n) => extract(n)).join('\n')}
this.offseasonChecklistPanel = offseasonChecklistPanel; this.shortDate = shortDate;`, ctx);
  return ctx;
}

const calendar = {offseason_opens: '2027-06-17', decisions_deadline: '2027-06-29', draft_round_one: '2027-06-22',
  draft_round_two: '2027-06-23', market_opens: '2027-06-30', league_year: '2027-07-01', market_wave_ends: '2027-07-04',
  roster_deadline: '2027-10-20'};

const room = {
  stop: 'decide_who_to_keep', team: {id: 'gsw'}, signing_season: '2027-28',
  offseason_checklist: {season: '2027-28', calendar, cap_room_millions: -12.5, holds_millions: 30.2, items: [
    {kind: 'team_option', player_id: 'a', name: 'Option Guy', deadline: '2027-06-29', salary_millions: 9.5, status: 'pending',
     text: 'Your decision: keep him for next season at this salary, or let him become a free agent.', default: 'Declined if you do nothing.'},
    {kind: 'qualifying_offer', player_id: 'b', name: 'Young Wing', deadline: '2027-06-29', amount_millions: 7.2, max_qo_millions: 43.0,
     status: 'pending', basis: 'his fourth-year salary plus 40% (pick 18)', text: 'Your decision: send the qualifying offer.'},
    {kind: 'player_option_result', player_id: 'c', name: 'Vet', deadline: '2027-06-29', salary_millions: 20, status: 'declined',
     text: 'He becomes a free agent: he expects about $24.0M a year on the market.'},
    {kind: 'own_free_agent', player_id: 'd', name: 'Own Guy', deadline: '2027-06-30', status: 'free_agent', bird_level: 'full',
     hold_millions: 18.0, text: 'Full Bird rights (4 seasons with you).'},
  ]},
};

test('stop 1 shows the four stops with dates and the current one marked', () => {
  const html = context().offseasonChecklistPanel(room);
  assert.match(html, /Decide Who To Keep/);
  assert.match(html, /aria-current="step"><b>1<\/b><span>Decide who to keep<\/span><small>Jun 17 – Jun 29 · draft Jun 22–23<\/small>/);
  assert.match(html, /<span>Make offers<\/span><small>from Jun 30/);
  assert.match(html, /15 players by Oct 20/);
  assert.match(html, /2 decisions waiting/);
});

test('each decision has a plain status and only the user\'s own decisions get buttons', () => {
  const html = context().offseasonChecklistPanel(room);
  assert.match(html, /data-offseason-option="exercise" data-player-id="a">Keep him/);
  assert.match(html, /data-offseason-qo="tender" data-player-id="b">Send offer/);
  assert.match(html, /data-offseason-qo="maximum"/);
  assert.match(html, /Amount: his fourth-year salary plus 40% \(pick 18\)\./);
  assert.match(html, /Declined if you do nothing\./);
  assert.match(html, /<span class="offseason-chip is-declined">Declined<\/span>/);
  assert.doesNotMatch(html, /data-player-id="c"/, 'a player option is the player\'s choice: no button');
  assert.match(html, /Full Bird/);
  assert.match(html, /\$18\.0M<small>cap hold<\/small>/);
  assert.match(html, /data-offseason-negotiate="d"/);
});

test('signing day recaps the first wave and says what is still open', () => {
  const html = context().offseasonChecklistPanel({...room, stop: 'finalize', league_moves: [
    {kind: 'free_agent_signing', team_ids: ['gsw'], headline: 'GSW signs New Guy.', aav_millions: 12, years: 3, player_id: 'n'},
    {kind: 'free_agent_signing', team_ids: ['bos'], headline: 'BOS signs Own Guy.', aav_millions: 20, years: 4, player_id: 'd'}]});
  assert.match(html, /Signing Day/);
  assert.match(html, /Your signings<\/h4><ul><li>GSW signs New Guy\./);
  assert.match(html, /Your free agents who left<\/h4><ul><li>BOS signs Own Guy\./);
  assert.match(html, /a restricted free agent talks only to you/);
});
