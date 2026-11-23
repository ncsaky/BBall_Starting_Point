const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;');
function runtime() {
  const context = {
    escapeHtml: escape, escapeAttr: escape,
    clampNumber: (value, min, max) => Math.min(max, Math.max(min, value)),
    draftMetric: value => value == null ? '—' : Number(value).toFixed(1),
    performanceBarStyle: value => `--fill:${value}%`, playerRatingBarStyle: value => `--fill:${value}%`,
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('const PC4_SEG'), source.indexOf('function approvedPlayerCardBody(')), context);
  vm.runInContext(source.slice(source.indexOf('function playerSummaryRatings('), source.indexOf('function tradeAssetContract(')), context);
  return context;
}

const grade = (id, name, value, evidence = 'player') => ({ id, name, kind: 'grade', evidence, value, interval: [value - 5, value + 5], pos_avg: 50, pct: 70 });
const profile = {
  position: 'SF',
  header: { ovr: 80.5, off: 72.3, def: 77.1, scale_note: 'Provisional note' },
  coach: { position: 'SF', primary_off_role: 'Shot Creator', secondary_off_role: null, primary_def_role: 'Hidden', rotation_priority: 'core_rotation', minutes_projection: 33.3, weight_lbs: 220 },
  layers: [
    { key: 'technique', title: 'Technique & Recognition', subtitle: 'sub', total: 3, from_player_data: 2, groups: [
      { name: 'Shooting', column: 0, entries: [grade('S01', 'Catch-and-shoot', 81), grade('S02', 'Pull-up', 60, 'prior')] },
      { name: 'Passing', column: 1, pairs: [{ id: 'F01', name: 'Drive and kick', read: grade('F01.recognition', 'Read', 70), delivery: grade('F01.execution', 'Delivery', 64) }] },
    ] },
    { key: 'physical', title: 'Physical Tools', subtitle: 'sub', total: 2, from_player_data: 1, groups: [{ name: 'Body', entries: [
      { id: 'P01', name: 'Height', kind: 'measure', evidence: 'player', value: 203, unit: 'cm', pct: 80, pos_avg_pct: 60, interval_pct: [78, 82] },
      grade('P02', 'Wingspan', 55, 'prior')] }] },
    { key: 'tendencies', title: 'Tendencies', subtitle: 'sub', total: 2, from_player_data: 1, groups: [
      { name: 'Choices and style', note: 'how often', entries: [{ id: 'T04', name: 'Shot hunting', kind: 'propensity', evidence: 'player', value: 0.4, pos_avg: 0.3, interval: [0.3, 0.5] }] },
      { name: 'Mixes', entries: [{ id: 'T01', name: 'Shot mix', kind: 'distribution', evidence: 'prior', value: { shoot: 0.6, drive: 0.4 }, outcomes: ['shoot', 'drive'], pos_avg: { shoot: 0.5, drive: 0.5 } }] },
    ] },
  ],
};

test('layered ratings page shows four layers, evidence styling and plain labels', () => {
  const html = runtime().inputsProfilePage(profile);
  for (const text of ['1 · Technique &amp; Recognition', '2 · Physical Tools', '3 · Tendencies', '4 · Coach Usage', 'Catch-and-shoot', 'Drive and kick', 'Shot hunting', 'Shot mix', 'Provisional note', 'Core rotation', '33.3 per game', 'Not yet revealed']) assert.ok(html.includes(text), text);
  assert.ok(html.includes('pc4-fill prior'), 'prior estimates are hatched');
  assert.ok(html.includes('pc4-band'), 'likely range band drawn');
  assert.ok(html.includes('2 of 3 from player data'));
  assert.ok(html.includes('title="S01 · Catch-and-shoot'), 'internal ids only in tooltips');
  assert.ok(!/<span class="pc4-l">S01/.test(html));
});

test('summary OVR/OFF/DEF bars use the profile header when present, legacy values otherwise', () => {
  const c = runtime();
  const withProfile = c.playerSummaryRatings({ inputs_profile: profile, ratings: { overall: 61, offense: 60, defense: 59 } });
  for (const value of ['80.5', '72.3', '77.1']) assert.ok(withProfile.includes(value), value);
  assert.ok(!withProfile.includes('61.0'));
  const legacy = c.playerSummaryRatings({ ratings: { overall: 61, offense: 60, defense: 59 } });
  assert.ok(legacy.includes('61.0') && !legacy.includes('80.5'));
});
