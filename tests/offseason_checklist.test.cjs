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
    playerHeadshotMarkup: (row) => (row.headshot_url ? `<span class="player-headshot-frame"><img src="${row.headshot_url}"></span>` : ''),
    compactRatingBar: (value) => `<span class="player-rating-bar">${value}</span>`,
    teamLogoSrc: (abbrev) => (abbrev ? `/${abbrev}.png` : ''),
  };
  vm.createContext(ctx);
  const names = ['shortDate', 'offseasonStopTimeline', 'offseasonItemStatus', 'offseasonItemMoney', 'offseasonItemActions',
    'offseasonChecklistTable', 'signingDayRecap', 'offseasonChecklistPanel', 'offerSheetStillOpen', 'offerSheetStatusWords',
    'offerSheetDecisionMarkup', 'shortSeasonLabel', 'optionDecisionWords', 'optionDecisionWho', 'optionDecisionsMarkup', 'offseasonPlayerCell'];
  vm.runInContext(`${extract('OFFSEASON_STOPS', 'const')}\n${extract('OFFSEASON_ITEM_LABELS', 'const')}\n${extract('OPTION_ITEM_KINDS', 'const')}\n${extract('OFFSEASON_COLUMNS', 'const')}\n${names.map((n) => extract(n)).join('\n')}
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
  // Playtest 2026-11-22: no title or paragraph; one short date per stop, finer dates and rules on hover, and a badge
  // on the current stop counting the decisions waiting.
  assert.doesNotMatch(html, /Decide Who To Keep<\/h3>/);
  assert.match(html, /aria-current="step" title="Draft Jun 22–23\. Teams may talk to their own free agents now[^"]*"><b>1<\/b><span>Decide who to keep <em class="offseason-waiting" title="2 decisions waiting">2<\/em><\/span><small>Jun 17–29<\/small>/);
  assert.match(html, /<span>Make offers<\/span><small>From Jun 30/);
  assert.match(html, /By Oct 20/);
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
  const html = context().offseasonChecklistPanel({...room, stop: 'finalize',
    offseason_checklist: {...room.offseason_checklist, departed: [{player_id: 'd', name: 'Own Guy', team_abbrev: 'BOS'}]}, league_moves: [
    {kind: 'free_agent_signing', team_ids: ['gsw'], headline: 'GSW signs New Guy.', aav_millions: 12, years: 3, player_id: 'n'},
    {kind: 'free_agent_signing', team_ids: ['bos'], headline: 'BOS signs Own Guy.', aav_millions: 20, years: 4, player_id: 'd'}]});
  assert.match(html, /Signing day/);
  assert.match(html, /Your signings<\/h4><ul><li>GSW signs New Guy\./);
  assert.match(html, /Your free agents who left<\/h4><ul><li>Own Guy signed with BOS\./);
  // FA-REAL slice 3 (rule changed): offer sheets exist now; with none this summer the box says what can still happen.
  assert.match(html, /No offer sheets this summer yet/);
});

// FA-REAL slice 3: a rival's offer sheet for one of your restricted free agents: a Match or Pass countdown with the
// terms year by year, what matching does to your cap, and any hard cap it would break.
const sheet = {
  id: 'offer_sheet:2027-28:b:team_mem:2027-07-02', player_id: 'b', name: 'Young Wing', status: 'pending',
  bidder_abbrev: 'MEM', rights_abbrev: 'GSW', signed_date: '2027-07-02', match_deadline: '2027-07-03', days_left: 1,
  total_millions: 37.8, years: [{season: '2027-28', salary_millions: 12.0}, {season: '2028-29', salary_millions: 12.6},
    {season: '2029-30', salary_millions: 13.2}],
  cap_effect: [{season: '2027-28', payroll_millions: 190.0, adds_millions: 12.0, after_millions: 202.0, cap_room_after_millions: -37.3,
    tax_room_after_millions: -1.6, first_apron_room_after_millions: 7.0}],
  can_match: true, match_route: 'full Bird rights', tax_cost_millions: 2.4, hard_cap: null,
  advice: {match: true, reason: 'GSW matches: he is a regular (26 minutes).'},
  if_matched: "He stays on these salaries year by year and can't be traded for a year.", if_passed: 'He joins MEM on these terms.',
};

test('match or pass: countdown, terms by year, cap effect and both buttons', () => {
  const html = context().offseasonChecklistPanel({...room, stop: 'make_offers', offer_sheets: {for_you: [sheet], yours: [], league: [sheet]}});
  assert.match(html, /Offer sheet · MEM · signed Jul 2/);
  assert.match(html, /1 day left<\/strong><small>by the end of Jul 3/);
  assert.match(html, /\$12\.0M[\s\S]*\$12\.6M/);
  assert.match(html, /\$202\.0M/, 'payroll if matched');
  assert.match(html, /Paid with <strong>full Bird rights<\/strong>\. No hard cap this season\./);
  assert.match(html, /About \$2\.4M more this season if you match/);
  assert.match(html, /data-offer-sheet-match="offer_sheet:2027-28:b:team_mem:2027-07-02"/);
  assert.match(html, /data-offer-sheet-pass=/);
  assert.match(html, /Assistant GM<\/dt><dd>GSW matches/);
});

test('a hard cap that blocks the match disables Match and says why', () => {
  const blocked = {...sheet, can_match: false, match_route: null, days_left: 0,
    match_blocked: 'GSW is hard-capped at the first apron ($216.3M) after using the full mid-level exception.'};
  const html = context().offseasonChecklistPanel({...room, stop: 'make_offers', offer_sheets: {for_you: [blocked], yours: [], league: []}});
  assert.match(html, /Decide today/);
  assert.match(html, /You can't match:<\/strong> GSW is hard-capped at the first apron/);
  assert.match(html, /data-offer-sheet-match="[^"]+" disabled/);
});

test('signing day still-open box lists decided sheets and your own pending sheets', () => {
  const matched = {...sheet, id: 's2', name: 'Other Guy', status: 'matched', bidder_abbrev: 'NYK', rights_abbrev: 'DAL'};
  const mine = {...sheet, id: 's3', name: 'Target', status: 'pending', bidder_abbrev: 'GSW', rights_abbrev: 'OKC', paid_with: 'the full mid-level exception'};
  const html = context().offseasonChecklistPanel({...room, stop: 'finalize', offer_sheets: {for_you: [], yours: [mine], league: [matched, mine]}});
  assert.match(html, /Your sheets:<\/b> Target \(OKC decides by Jul 3; your the full mid-level exception stays reserved\)/);
  assert.match(html, /Other Guy <small>NYK sheet · \$37\.8M over 3 years · DAL matched/);
});

// CONTRACT-TERMS part 3: the Option Decisions card: the player's own choice with his reason, your team options with
// Keep/Decline, and the notable decisions around the league; the main table no longer repeats the option rows.
test('option decisions card: who decides, the decision, why, and your buttons', () => {
  const view = {season: '2027-28', counts: {player_opted_out: 7, player_opted_in: 9, team_kept: 5, team_declined: 6},
    yours: [
      {player_id: 'a', name: 'Option Guy', kind: 'team_option', kind_words: 'team option', salary_millions: 9.5, season: '2027-28',
       status: 'pending', decided_by: 'user', deadline: '2027-06-29', reason: 'Your decision.'},
      {player_id: 'c', name: 'Vet', kind: 'player_option', kind_words: 'player option', salary_millions: 20, season: '2027-28',
       status: 'declined', decided_by: 'player', reason: 'He becomes a free agent: as a 27-year-old starter he expects about $24.0M.'}],
    league: [{player_id: 'z', name: 'Big Star', team_abbrev: 'LAL', kind: 'player_option', kind_words: 'player option',
      salary_millions: 48, status: 'exercised', decided_by: 'player', reason: 'He keeps his $48.0M option.'}]};
  const html = context().offseasonChecklistPanel({...room, offseason_checklist: {...room.offseason_checklist, option_decisions: view}});
  assert.match(html, /Options · 27-28/);
  assert.match(html, /is-declined" title="[^"]*">Opted out/);
  assert.match(html, /as a 27-year-old starter/);
  assert.match(html, /data-offseason-option="exercise" data-player-id="a">Keep him/);
  assert.match(html, /Big Star[\s\S]*LAL[\s\S]*Opted in/);
  assert.match(html, /<h4>Around the league<\/h4>/);
  assert.equal((html.match(/data-player-id="a">Keep him/g) || []).length, 1, 'the option is not repeated in the main table');
});
