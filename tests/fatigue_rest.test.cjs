// FATIGUE-REST: the fatigue bar shows the engine's value, and the rest controls in Minutes + Availability.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const grab = (name) => app.match(new RegExp(`function ${name}\\([\\s\\S]*?\\n}\\n`))[0];
const constant = (name) => app.match(new RegExp(`const ${name} = [^\\n]+\\n`))[0];

function context(settings = {}) {
  const ctx = {
    escapeHtml: (v) => String(v), escapeAttr: (v) => String(v),
    clampNumber: (v, lo, hi) => Math.min(hi, Math.max(lo, v)),
    state: {home: {game_settings: settings}},
  };
  vm.createContext(ctx);
  vm.runInContext([
    constant('FATIGUE_TIRED'), constant('FATIGUE_VERY_TIRED'),
    ...['isPlayerInjured', 'seasonFatigueTone', 'seasonFatigueTooltip', 'seasonFatigueCell', 'coachRestsPlayers',
      'coachRestToggleMarkup', 'playerIsResting', 'restGamesLabel', 'playerRestButtonMarkup', 'playerRestMarkup'].map(grab),
  ].join('\n'), ctx);
  return ctx;
}

test('fatigue bar shows exactly the engine value, with the next tip-off value in the tooltip', () => {
  const ctx = context();
  for (const fatigue of [0, 12.4, 37.5, 50, 63.2, 91]) {
    const html = ctx.seasonFatigueCell({health: {status: 'ok', label: '', fatigue, fatigue_next: fatigue * 0.62, fatigue_next_date: '2026-12-03'}});
    assert.match(html, new RegExp(`data-fatigue-value="${fatigue.toFixed(1)}"`));
    // One thin bar whose length is the fatigue value (taste deck round 2: no blocks, no dark track).
    assert.match(html, new RegExp(`width:${Math.max(fatigue > 0 ? 3 : 0, fatigue).toFixed(1)}%`));
    assert.match(html, new RegExp(`<em>${fatigue.toFixed(0)}</em>`));
    assert.match(html, new RegExp(`Fatigue ${fatigue.toFixed(0)} / 100 today`));
    assert.match(html, new RegExp(`About ${(fatigue * 0.62).toFixed(0)} at his next tip-off \\(2026-12-03\\)`));
  }
  assert.match(ctx.seasonFatigueCell({health: {fatigue: 20}}), /season-fatigue low/);
  assert.match(ctx.seasonFatigueCell({health: {fatigue: 50}}), /season-fatigue medium/);
  assert.match(ctx.seasonFatigueCell({health: {fatigue: 65}}), /season-fatigue high/);
});

test('rest button: rest for N games, shows resting state, disabled when injured or not editable', () => {
  const ctx = context();
  const healthy = ctx.playerRestButtonMarkup({id: 'p1', name: 'Jalen', health: {status: 'ok', label: ''}}, true);
  assert.match(healthy, /data-minute-rest-player="p1"/);
  assert.match(healthy, /Rest Jalen for his team's next 1 to 5 games/);
  assert.doesNotMatch(healthy, /disabled/);
  const resting = ctx.playerRestButtonMarkup({id: 'p1', name: 'Jalen', health: {status: 'ok', label: '', user_rest: {games_left: 2}}}, true);
  assert.match(resting, /season-minute-rest active/);
  assert.match(resting, /back in 2 games/);
  // Injured players get no zZ at all (taste deck 2026-11-23).
  assert.equal(ctx.playerRestButtonMarkup({id: 'p1', health: {status: 'out', label: 'Ankle sprain ~3g'}}, true), '');
  assert.match(ctx.playerRestButtonMarkup({id: 'p1', health: {status: 'ok', label: ''}}, false), /disabled/);
});

test('resting marker says when he is back and that his minutes are kept; suggestion stays visible', () => {
  const ctx = context();
  const row = {resting_minutes_target: 34, health: {status: 'ok', label: '', user_rest: {games_left: 3, games: 3}}};
  assert.equal(ctx.playerIsResting(row), true);
  const marker = ctx.playerRestMarkup(row);
  assert.match(marker, /player-resting/);
  assert.match(marker, /sits his team's next 3 games, then back to his 34 minutes/);
  assert.match(marker, /<span>3<\/span>/);
  const suggestion = {status: 'ok', label: '', rest_suggestion: {date: '2026-12-03', kind: 'rest', reason: 'heavy recent workload (fatigue 41)'}};
  assert.match(ctx.playerRestMarkup({health: suggestion}), /Coach suggests resting him on 2026-12-03: heavy recent workload/);
  assert.match(ctx.playerRestMarkup({health: suggestion}), /zZ button next to his minutes/);
  const auto = context({coach_rests_players: true});
  assert.match(auto.playerRestMarkup({health: suggestion}), /Coach plans to rest him on 2026-12-03/);
});

test('coach rest toggle reflects the save setting and defaults to off', () => {
  assert.doesNotMatch(context().coachRestToggleMarkup('x'), /checked/);
  assert.match(context().coachRestToggleMarkup('x'), /Off: nobody is rested automatically/);
  const on = context({coach_rests_players: true}).coachRestToggleMarkup('x');
  assert.match(on, /data-coach-rest-toggle checked/);
  assert.match(on, /same rules as the AI coaches/);
});
