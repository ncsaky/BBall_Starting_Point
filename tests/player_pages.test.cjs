const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const playerStart = source.indexOf('function playerCardRatingGroups(');
const playerEnd = source.indexOf("\ndocument.addEventListener(", source.indexOf('function wirePlayerCardPages('));
assert.ok(playerStart >= 0 && playerEnd > playerStart);
const playerCode = source.slice(playerStart, playerEnd);
const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
function runtime() {
  const context = {
    declineWatchApplies:() => false,
    escapeHtml:escape, escapeAttr:escape,
    clampNumber:(value, min, max) => Math.min(max, Math.max(min, value)),
    draftMetric:value => value == null ? '—' : Number(value).toFixed(1),
    decimalNumber:value => Number(value).toFixed(1),
    performanceBarStyle:value => `--fill:${value}%`, playerRatingBarStyle: value => `--fill:${value}%`, ratingTone:() => 'average',
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

test('three player pages show season stats, recent games, payroll, ratings, and injury outlook', () => {
  const c = runtime();
  const ratings = Object.fromEntries(['overall','shooting','release','range','versatility','spacing','creation','handle','passing','rim_pressure','defense','def_effort','screen_nav','steal','block','rim_deterrence','rebounding','oreb','athleticism','lateral_agility','stamina','iq','scheme_iq','portability','playoff'].map((key,index) => [key, 60 + index]));
  const detail = {
    player_id:'p1', name:'Player One', position:'SF', age:22, height:'6\'8"', ratings,
    health_risk:2.2, injury_body_map:{expected_games_total:8,typical_games_total:6,
      parts:[{part:'knee',label:'Knee',expected_games:4,typical_games:2,relative:2}]},
    upside_remaining:3.4, trade_value:66.7, spatial_profile:{id:'own-court'},
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
  for (const field of ['Injury risk 2.2','Growth runway','Trade Value','3.4','66.7','Offensive shape','Defense / physical','own-court','Select player career season','Recent Games · Last 5','Game Score · Last 15 Games','Four-Year Payroll Share','Health & Injury Outlook']) assert.ok(html.includes(field), field);
  const season = html.slice(html.indexOf('approved-season-line'), html.indexOf('player-page-game-log'));
  assert.match(season, /<small>GP\/All<\/small><strong>30\//);
  for (const [key,value] of Object.entries(detail.season)) {
    if (key !== 'games') assert.ok(season.includes(`>${value.toFixed(1)}<`), `Season ${key}`);
  }
  assert.equal((html.match(/<span class="player-page-opponent"/g) || []).length,5);
  const log = html.slice(html.indexOf('player-page-game-log'), html.indexOf('player-page-score-panel'));
  assert.deepEqual([...log.matchAll(/<td>(01-\d{2})<\/td>/g)].map(match => match[1]),
    ['01-30','01-29','01-28','01-27','01-26']);
  const points = JSON.parse(html.match(/data-game-score-points="([^"]+)"/)[1].replaceAll('&quot;', '"'));
  assert.deepEqual(points, detail.recent_games.slice(-15).map(row => ({label:row.date.slice(5), value:row.game_score})));
  const payroll = html.match(/class="salary-horizon-chart">([^<]+)/)[1];
  assert.equal(payroll, detail.salary_seasons.slice(0,4).map(row => `${row.season}:${row.salary_millions}`).join('|'));
  assert.match(html, /injury-body-figure mini/);
  assert.match(html, /Watch: Knee/);
  for (const view of ['Front','Back']) assert.ok(html.includes(`${view} body map of injury risk`));
  assert.match(html, /data-injury-part="knee"/);
});

test('empty history and incomplete ratings have explicit empty states and never invent radar values', () => {
  const html = runtime().approvedPlayerCardBody({name:'New Player',ratings:{overall:60,shooting:55,defense:52},season:{games:0}});
  assert.equal((html.match(/<tr>(?:<td>—<\/td>){10}<\/tr>/g) || []).length, 5);
  assert.match(html, /Body map unavailable for this player/);
  assert.match(html, /points=""><title>No game-score history yet<\/title>/);
  assert.doesNotMatch(html, /class="chart-node/);
  assert.ok(html.includes('Offensive shape profile unavailable.'));
  assert.ok(html.includes('Defense / physical profile unavailable.'));
  assert.equal((html.match(/class="player-radar-shape"/g) || []).length,0);
  assert.ok(!html.includes('NaN'));
});

function pageFixture(page) {
  const c = runtime();
  let redraws = 0;
  c.wirePlayerGameScoreCharts = () => redraws++;
  const pages = ['Season, Games & Contract','Ratings & Profiles','Health & Injury Outlook'].map(pageTitle => ({dataset:{pageTitle},hidden:false,scrollTop:80}));
  const title = {}, count = {}, root = {
    dataset:{}, querySelectorAll:() => pages,
    querySelector:selector => ({'[data-player-page-title]':title,'[data-player-page-count]':count})[selector] || null,
    addEventListener() {},
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
  assert.equal(f.count.textContent,'1/3');
  f.click(-1);
  assert.equal(f.entry.page,2);
  assert.equal(f.title.textContent,'Health & Injury Outlook');
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
  assert.equal(first.title.textContent,'Health & Injury Outlook');
  assert.equal(second.title.textContent,'Ratings & Profiles');
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
    focusOpenExtensionCard:async () => false,
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
