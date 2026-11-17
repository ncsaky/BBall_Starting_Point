const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const playerCode = source.slice(source.indexOf('function playerCardRatingGroups('), source.indexOf('function clipboardPlayerCardWindows('));
const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
function runtime() {
  const context = {
    escapeHtml:escape, escapeAttr:escape,
    clampNumber:(value, min, max) => Math.min(max, Math.max(min, value)),
    draftMetric:value => value == null ? '—' : Number(value).toFixed(1),
    decimalNumber:value => Number(value).toFixed(1),
    performanceBarStyle:value => `--fill:${value}%`, ratingTone:() => 'average',
    money:value => `$${Number(value).toFixed(1)}M`, shortSeasonLabel:value => value,
    playerHeadshotMarkup:detail => `<span class="player-headshot-frame"><img alt="${escape(detail.name)}" src="headshot"></span>`,
    teamLogoSrc:abbrev => abbrev ? `/logos/${abbrev}.png` : '',
    spatialHeatmapMarkup:profile => `<div data-court="${escape(profile?.id || 'none')}">Court map</div>`,
    salaryHorizonChart:options => `<div class="salary-horizon-chart">${Object.entries(options.rows[0].salary_by_year).map(([season, salary]) => `${season}:${salary}`).join('|')}</div>`,
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function fantasyPlayerRadar('), source.indexOf('function fantasyPlayerContractChart(')), context);
  vm.runInContext(source.slice(source.indexOf('function playerSummaryRatings('),source.indexOf('function tradeAssetContract(')), context);
  vm.runInContext(playerCode, context);
  return context;
}

test('three player pages retain ratings, evidence, season, chart, payroll, and all available games', () => {
  const c = runtime();
  const ratings = Object.fromEntries(['overall','shooting','release','range','versatility','spacing','creation','handle','passing','rim_pressure','defense','def_effort','screen_nav','steal','block','rim_deterrence','rebounding','oreb','athleticism','lateral_agility','stamina','iq','scheme_iq','portability','playoff'].map((key,index) => [key, 60 + index]));
  const detail = {
    player_id:'p1', name:'Player One', position:'SF', age:22, height:'6\'8"', ratings,
    health_risk:2.2, upside_remaining:3.4, trade_value:66.7, spatial_profile:{id:'own-court'},
    season:{games:30,mpg:31.4,ppg:22.1,rpg:6.2,apg:4.3,spg:1.4,bpg:.8,topg:2.1,fta_per_game:5.5,ft_pct:81.2},
    salary_seasons:Array.from({length:6}, (_,index) => ({season:`202${index}-2${index + 1}`,salary_millions:10 + index})),
    recent_games:Array.from({length:30}, (_,index) => ({date:`2027-01-${String(index + 1).padStart(2,'0')}`,opponent_abbrev:'BOS',minutes:32,points:index + 10,rebounds:6,assists:4,steals:1,blocks:2,turnovers:3,game_score:index + 9.7})),
  };
  const html = c.approvedPlayerCardBody(detail);
  assert.equal((html.match(/data-player-page="/g) || []).length,3);
  for (const group of c.playerCardRatingGroups(ratings,false)) {
    assert.ok(html.includes(group.label));
    for (const [label,value] of group.rows) {
      assert.ok(html.includes(label), label);
      assert.ok(html.includes(value.toFixed(1)), label);
    }
  }
  for (const field of ['Health risk','Upside','Trade Value','3.4','66.7','Offensive shape','Defense / physical','own-court','Most Recent Season','Last 30 Games · Game Score','Four-Year Payroll Share','Contract by Season']) assert.ok(html.includes(field), field);
  for (const value of Object.values(detail.season)) assert.ok(html.includes(value.toFixed(1)), `Season ${value}`);
  assert.equal((html.match(/<span class="player-page-opponent"/g) || []).length,30);
  const log = html.slice(html.indexOf('player-page-game-log'));
  assert.ok(log.indexOf('01-30') < log.indexOf('01-01'), 'Latest game appears first');
  assert.ok(html.includes('2025-26'), 'Sixth contract year remains available');
  assert.ok(html.includes('2027-01-30') === false, 'Game dates use the existing short label');
});

test('empty history and incomplete ratings have explicit empty states and never invent radar values', () => {
  const html = runtime().approvedPlayerCardBody({name:'New Player',ratings:{overall:60},season:{games:0}});
  assert.ok(html.includes('No recent games yet.'));
  assert.ok(html.includes('No game-score history yet.'));
  assert.ok(html.includes('Offensive shape profile unavailable.'));
  assert.ok(html.includes('Defense / physical profile unavailable.'));
  assert.equal((html.match(/class="player-radar-shape"/g) || []).length,0);
  assert.ok(!html.includes('NaN'));
});

function pageFixture(page) {
  const c = runtime();
  let redraws = 0;
  c.wirePlayerGameScoreCharts = () => redraws++;
  const pages = ['Ratings & Court','Season & Game Score','Games & Contract'].map(pageTitle => ({dataset:{pageTitle},hidden:false,scrollTop:80}));
  const title = {}, count = {}, root = {
    dataset:{}, querySelectorAll:() => pages,
    querySelector:selector => selector.includes('title') ? title : count,
    contains:button => button.belongsToCard !== false,
  };
  let listener;
  const card = {querySelector:() => root, addEventListener:(_name, fn) => {listener = fn;}, style:{width:'1530px',height:'900px'}};
  const entry = {page, width:1530, height:900};
  c.wirePlayerCardPages(card, entry);
  return {c, card, root, pages, entry, title, count, redraws:() => redraws,
    click:step => listener({target:{closest:() => ({dataset:{playerPageStep:String(step)}})},preventDefault:() => {}}),
  };
}

test('page arrows wrap and update only the current card, preserving DOM, scroll, and window size', () => {
  const f = pageFixture();
  assert.deepEqual(f.pages.map(page => page.hidden), [false,true,true]);
  f.click(-1);
  assert.equal(f.entry.page,2);
  assert.equal(f.title.textContent,'Games & Contract');
  assert.equal(f.count.textContent,'3/3');
  assert.deepEqual(f.pages.map(page => page.hidden), [true,true,false]);
  f.click(1);
  assert.equal(f.entry.page,0);
  f.click(1);
  assert.equal(f.entry.page,1);
  assert.equal(f.root.dataset.page,'1');
  assert.deepEqual(f.card.style,{width:'1530px',height:'900px'});
  assert.ok(f.pages.every(page => page.scrollTop === 80));
  assert.equal(f.redraws(),3);
});

test('each player remembers its own page after rebuilding workspace windows', () => {
  const first = pageFixture(2), second = pageFixture(1);
  assert.equal(first.title.textContent,'Games & Contract');
  assert.equal(second.title.textContent,'Season & Game Score');
  first.click(1);
  assert.equal(first.entry.page,0);
  assert.equal(second.entry.page,1);
  const rebuilt = pageFixture(second.entry.page);
  assert.deepEqual(rebuilt.pages.map(page => page.hidden), [true,false,true]);
});

test('opening a player from a trade retains a return context while ordinary player cards do not', async () => {
  const c = runtime();
  let opened;
  Object.assign(c, {
    state:{tradeTab:'finder',modal:{kind:'tradeRoom',body:'Current trade'},data:{dashboard:{}}},
    rosterRows:() => [],
    loadPlayerCardDetail:async () => ({player_id:'p1',name:'Player One',ratings:{overall:75}}),
    openPlayerCardOnClipboard:async options => {opened = options;},
  });
  vm.runInContext(source.slice(source.indexOf('async function dashboardPlayerCard('), source.indexOf('async function freeAgentPlayerCard(')), c);
  await c.dashboardPlayerCard('p1');
  assert.equal(opened.context.tradeReturn.kind,'tradeRoom');
  assert.equal(opened.context.tradeReturn.activeTab,'finder');
  assert.equal(opened.context.tradeReturn.body,'Current trade');
  assert.ok(opened.body.includes('Back to Trade Finder'));
  c.state.modal = {kind:'tradeOffers',offers:[{id:'offer'}]};
  await c.dashboardPlayerCard('p1');
  assert.ok(opened.body.includes('Back to Offers'));
  assert.equal(opened.context.tradeReturn.offers[0].id,'offer');
  c.state.modal = null;
  await c.dashboardPlayerCard('p1');
  assert.equal(opened.context,null);
  assert.ok(!opened.body.includes('data-player-return-trade'));
});
