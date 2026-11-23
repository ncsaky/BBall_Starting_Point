const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const source = fs.readFileSync(path.join(gui, 'season-slideshow.js'), 'utf8');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const css = fs.readFileSync(path.join(gui, 'season-slideshow.css'), 'utf8');
const html = fs.readFileSync(path.join(gui, 'index.html'), 'utf8');

function load({reduced = false} = {}) {
  const window = {matchMedia: () => ({matches: reduced}), addEventListener() {}, dispatchEvent() {}};
  const document = {readyState: 'complete', getElementById: () => null, addEventListener() {}, body: {classList: {add() {}, remove() {}}}};
  const context = vm.createContext({window, document, requestAnimationFrame: (fn) => fn(), CustomEvent: class {}});
  vm.runInContext(source, context);
  return window.SeasonSlideshow;
}

const team = (abbrev) => ({id: `team_${abbrev.toLowerCase()}`, abbrev, name: `${abbrev} Team`});
const player = (name) => ({id: name, name, overall: 70.1, position: 'G', headshot_url: '', age: 25});

test('every recap and outlook slide renders its data', () => {
  const {RENDER} = load();
  const slides = {
    champion: {champion: team('OKC'), runner_up: team('TOR'), series_result: '4-2', regular_season_record: '65-17', path: [{round: 'finals', opponent: team('TOR'), result: '4-2'}],
               finals_mvp: {...player('Hero'), team_abbrev: 'OKC', finals_line: {pts: 30, reb: 5, ast: 7, gp: 6}, why: 'Highest total Game Score'}},
    standings: {conferences: {East: [{rank: 1, team: team('BOS'), wins: 60, losses: 22, result_label: 'Won the title', is_user: true}], West: []}},
    awards: {awards: [{label: 'Sixth Man of the Year', criteria: 'Came off the bench', player: player('Bench Scorer'), detail: 'Off the bench in 60 games'}],
             all_nba: [{label: 'All-NBA First Team', players: [{...player('Star'), team_abbrev: 'DEN'}]}]},
    leaders: {categories: [{label: 'Screen assists', rows: [{name: 'Screener', team_abbrev: 'MEM', per_game: 5.3}]}]},
    your_season: {team: team('GSW'), record: '35-47', result_label: 'Missed the playoffs', conference_rank: 13, conference: 'West', stats: [{label: 'Wins', value: 35, rank: 23}],
                  team_mvp: player('Leader'), team_mvp_why: 'The most on-court value times minutes'},
    trades: {trades: [{date: '2027-02-04', value_involved: 71.2, value_swing: 41.7, ranked_by: 'value swing', reasons: 'MIL targeted a young big',
                       sides: [{team: team('MIL'), phase: 'rebuilding', received: [{kind: 'player', label: 'Big Man', played_out: {games: 29, minutes: 32.8, points: 11.2, rebounds: 7.9, assists: 4.3}}]}]}]},
    coaching: {changes: [{team: team('BKN'), job: 'Head Coach', out: {name: 'Old Coach', grade: 65, reason: 'losing'}, in: {name: 'New Coach', grade: 81, style: 'Rides his stars'}, date: '2026-12-01'}]},
    free_agents: {players: [{...player('Free Agent'), team: team('CHA'), market_value_millions: 23.9, current_salary_millions: 15.1}]},
    look_ahead: {draft: {status: 'lottery', lottery_position: 8, odds_first_pick: 6.0, pick_owner: 'Utah Jazz'}, prospects: [{consensus_rank: 1, name: 'Top Prospect', your_rank: 2}], cap: {season: '2027-28', payroll_millions: 116.5}},
    power: {rows: [{rank: 1, team: team('OKC'), overall: 63, last_finish: 3, change: 2, note: 'Added Somebody', is_user: false}]},
    continuity: {note: 'A new league: these are the real 2025-26 NBA minutes', legend: {kept: 'Still on the team'},
                 rows: [{team: team('BOS'), kept_pct: 70, injured_pct: 5, gone_pct: 25, continuity_pct: 75, arrivals_pct: 12,
                         kept: [{name: 'Keeper', minutes: 2000}], injured: [{name: 'Hurt', minutes: 300}], gone: [{name: 'Leaver', minutes: 900}],
                         arrivals: [{name: 'Newcomer', minutes_last_season: 1500, rookie: false}, {name: 'Rookie', minutes_last_season: 0, rookie: true}], is_user: true}]},
    leaders_revisited: {categories: [{label: 'Points', rows: [{name: 'Scorer', team_abbrev: 'DAL', per_game: 27.5, moved: true, now: {team: team('LAL'), status: 'Expected starter, about 34 minutes'}}]}],
                        award_winners: [{label: 'Most Valuable Player', name: 'MVP Guy', then: 'DEN', now: {team: team('DEN'), status: 'Injured (foot fracture)'}}]},
    your_team: {rotation: [{...player('Starter'), minutes: 34, off_role: 'Connector', def_role: 'Rim Protector'}], overall_rank: 27},
    team_profile: {radar: [{key: 'spacing', label: 'Spacing', side: 'offense', rank: 6}, {key: 'defense', label: 'Defense', side: 'defense', rank: 30}],
                   cap: {payroll_millions: 152.1}, tax_payout: {payout_millions: 9.8, season: '2026-27', paid_on: '2027-07-15'}},
    contracts: {extensions: [{...player('Extend Me'), salary_millions: 2.5, projected_millions: 10.4}], expiring: [{...player('Big Deal'), team: team('DEN'), salary_millions: 62.8}]},
    prospects: {prospects: [{consensus_rank: 1, name: 'Prospect One', your_rank: 3, scouted_pct: 85.8}], projected_pick: 4},
    storylines: {items: [{title: 'Youth movement', text: 'Spurs have the best young group.'}]},
    injuries: {players: [{...player('Hurt Star'), team: team('HOU'), injury: 'ankle sprain', games: 35, return_date: '2028-01-11'}]},
  };
  const expected = {champion: 'Finals MVP', standings: 'Won the title', awards: 'Off the bench in 60 games', leaders: 'Screener', your_season: '13th in the West',
                    trades: 'After the trade: 29 G', coaching: 'Rides his stars', free_agents: '$23.9M', look_ahead: 'belongs to Utah Jazz', power: '▲2',
                    continuity: 'Newcomer (1500)', leaders_revisited: 'aria-label="moved to"', your_team: 'Rim Protector', team_profile: '$9.8M', contracts: 'Extend Me',
                    prospects: 'No. 4', storylines: 'Youth movement', injuries: 'about 35 games'};
  for (const [key, slide] of Object.entries(slides)) {
    const markup = RENDER[key]({key, ...slide});
    assert.ok(markup.includes(expected[key]), `${key} is missing ${expected[key]}`);
  }
  assert.match(RENDER.continuity({rows: slides.continuity.rows, legend: {}}), /ss-kept" style="width:70%"[\s\S]*ss-injured" style="width:5%"[\s\S]*ss-gone" style="width:25%"/);
  // The bar speaks for itself: no "% kept · +N new" text and no repeated source line (playtest 2026-11-22).
  assert.doesNotMatch(RENDER.continuity({rows: slides.continuity.rows, legend: {}, note: 'Source'}), /kept ·|had no NBA minutes|ss-source/);
  assert.match(RENDER.trades({trades: []}), /No trades this season/);
  assert.match(RENDER.injuries({players: []}), /more than 20 games/);
});

test('the slideshow is a large tutorial-style card with Previous, Next, Skip and keyboard control', () => {
  assert.match(source, /class="game-tutorial-titlebar ss-titlebar"/);
  assert.match(source, /data-ss-action="skip"/);
  assert.match(source, /data-ss-action="previous"/);
  assert.match(source, /data-ss-action="next"/);
  assert.match(source, /event\.key === "Escape"[\s\S]*?close\(\)/);
  assert.match(source, /event\.key === "ArrowRight"[\s\S]*?move\(1\)/);
  assert.match(source, /event\.key === "ArrowLeft"[\s\S]*?move\(-1\)/);
  assert.match(source, /event\.key === "Enter"/);
  assert.match(source, /setAttribute\("inert", ""\)/);
  assert.match(source, /reducedMotion\(\) \|\| !direction \? ""/);
  assert.match(css, /prefers-reduced-motion: reduce[\s\S]*animation: none/);
  assert.match(css, /\.ss-backdrop[\s\S]*position: fixed;[\s\S]*inset: 0;/);
  assert.match(css, /\.ss-table th \{\n  border-bottom: 3px solid/);  // one thick dark header line (UI style guide)
  assert.match(html, /id="seasonSlideshow"/);
  assert.match(html, /season-slideshow\.js/);
  assert.match(html, /season-slideshow\.css/);
});

test('a due slideshow opens once: it is marked seen as it opens, after the champion screen, before the tour', () => {
  assert.match(app, /openSeasonSlideshow\(pending\.kind, pending\.season, \{auto:true\}\)/);
  assert.match(app, /if \(shown && auto\) \{[\s\S]*?action\("season_slideshow_seen"/);
  assert.match(app, /if \(auto\) \{ state\.seasonSlideshowAutoKeys\?\.delete/);
  assert.match(app, /if \(state\.modal \|\| state\.tutorial \|\| state\.simulationRunning \|\| state\.hydrating \|\| state\.multiplayer\?\.session\) return;/);
  assert.match(app, /maybeCelebrateChampion\(\);\s*maybeOpenSeasonSlideshow\(\);\s*queueFirstRunTutorial\(\);/);
  assert.match(app, /if \(!state\.modal\) maybeOpenSeasonSlideshow\(\);/);
  assert.match(app, /if \(state\.slideshowOpening \|\| window\.SeasonSlideshow\?\.isOpen\(\)\) return;/);
  assert.match(app, /data-season-slideshow=/);
  assert.match(app, /label:"Year-end recap"/);
});

test('preseason outlook taste pass: projected ranks, rows that fall in, your team as tiles, contracts as bars', () => {
  const {RENDER} = load();
  // Preseason ranks say "Projected".
  assert.match(source, /`Projected \$\{ordinalRank\(slide\.overall_rank\)\} of /);
  assert.doesNotMatch(source, /in the league`/);

  // Power rankings and continuity: bordered, rows fall into place on entry (not under reduced motion).
  const power = RENDER.power({rows: [{rank: 1, team: team('OKC'), overall: 63, last_finish: 3, change: 2, note: 'Added Somebody'}]});
  assert.match(power, /class="ss-boxed ss-rows-in"><div class="ss-two ss-compact" data-ss-split>/);
  assert.match(power, /<tr class="" style="--i:0">/);
  const continuity = RENDER.continuity({legend: {}, rows: [1, 2, 3].map((n) => ({team: team(`T${n}`), kept_pct: 50, injured_pct: 0, gone_pct: 50, continuity_pct: 50, kept: [], injured: [], gone: [], arrivals: []}))});
  assert.equal((continuity.match(/<ol class="ss-continuity"/g) || []).length, 2);
  assert.match(continuity, /ss-continuity-cols ss-rows-in/);
  assert.doesNotMatch(load({reduced: true}).RENDER.power({rows: []}), /ss-rows-in/);
  assert.match(css, /@keyframes ss-row-fall/);
  assert.match(css, /prefers-reduced-motion: reduce\) \{\n  \.ss-rows-in[^}]*animation: none/);
  assert.match(source, /closest\("\.ss-rows-in"\)\?\.classList\.remove\("ss-rows-in"\)/);  // a sort does not replay it

  // Last season's leaders: each mini table has a titled header.
  const leaders = RENDER.leaders_revisited({categories: [{stat: 'points', label: 'Points', rows: [{name: 'Scorer', team_abbrev: 'DAL', per_game: 27.5, now: {team: team('DAL')}}]}]});
  assert.match(leaders, /<h4 class="ss-panel-title">Points<\/h4>/);

  // Your team: starting five tiles with a role pair, bench tiles, three numbers; no roster table.
  const starter = (n, extra = {}) => ({...player(`Starter ${n}`), id: `s${n}`, minutes: 30 - n, off_role: 'Primary Ball Handler', def_role: 'Versatile Stopper', ...extra});
  const rotation = [1, 2, 3, 4, 5].map((n) => starter(n)).concat([starter(6, {minutes: 15}), starter(7, {minutes: 0, injury: {games: 30, label: 'Knee'}})]);
  const yours = RENDER.your_team({rotation, starters: ['s5', 's1', 's2', 's3', 's4'],
    takeaways: {teams: 30, age: {value: 25.5, rank: 8}, shape: {label: 'Top-heavy', top_rank: 2, depth_rank: 18}, payroll: {value: 216.9, rank: 5}}});
  assert.doesNotMatch(yours, /<table/);
  assert.equal((yours.match(/ss-tile-starter/g) || []).length, 5);
  assert.equal((yours.match(/ss-tile-bench/g) || []).length, 2);
  assert.ok(yours.indexOf('Starter 5') < yours.indexOf('Starter 1'), 'starters follow the lineup slots');
  assert.match(yours, /<span class="ss-role-pair">Primary Ball HandlerVersatile Stopper<\/span>/);
  assert.match(yours, /8th youngest of 30/);
  assert.match(yours, /Top-heavy/);
  assert.match(yours, /\$216\.9M/);
  assert.match(yours, /✚ 30/);
  assert.match(yours, /class="ss-rating" style="color:#[0-9a-f]{6}">70\.1</);
  // An outlook stored before this change (no starters) still shows five starters: the most minutes.
  assert.equal((RENDER.your_team({rotation}).match(/ss-tile-starter/g) || []).length, 5);

  // Team profile: two titled panels; the cap numbers sit under the payroll chart.
  const profile = RENDER.team_profile({radar: [{key: 'defense', label: 'Defense', side: 'defense', rank: 3}], cap: {payroll_millions: 152.1}});
  assert.match(profile, /Strengths by league rank[\s\S]*Payroll, next four seasons[\s\S]*ss-cap-table/);

  // Contracts: never a bare salary; bar charts; players who could be on the move grouped by reason.
  const contracts = RENDER.contracts({
    extensions: [{...player('Extend Me'), salary_millions: 7.8, years_left: 2, projected_millions: 18.5, projected_years: 4}],
    movers: [{...player('Pricey Vet'), team: team('SAC'), overall: 77.5, salary_millions: 45.5, years_left: 2, reason: 'Paid above his value'},
             {...player('Old Hand'), team: team('GSW'), overall: 75.9, salary_millions: 27.7, years_left: 1, reason: "Older than his team's timeline"}],
  });
  assert.match(contracts, /\$7\.8M × 2[\s\S]*\$18\.5M × 4/);
  assert.match(contracts, /Could be on the move/);
  assert.match(contracts, /<h5>Paid above his value<\/h5>[\s\S]*Pricey Vet[\s\S]*\$45\.5M × 2/);
  assert.equal((contracts.match(/\$[\d.]+M(?! ×)/g) || []).length, 0, 'every contract reads salary × years');
  assert.doesNotMatch(contracts, /<table/);
  // An outlook stored before this change (no trade block) falls back to the biggest expiring deals.
  assert.match(RENDER.contracts({extensions: [], expiring: [{...player('Big Deal'), team: team('DEN'), salary_millions: 62.8}]}), /Biggest expiring deals[\s\S]*\$62\.8M/);
});
