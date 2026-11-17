const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const functions = app.slice(app.indexOf('function spatialEfficiencyColor'), app.indexOf('function spatialHeatmapMarkup'));
const context = vm.createContext({escapeHtml: value => String(value), escapeAttr: value => String(value)});
vm.runInContext(functions, context);
const colors = [-20, -5, 0, 5, 20].map(delta => context.spatialEfficiencyColor(delta));
assert.equal(new Set(colors).size, 5);
const profile = {shot_chart: {regions: [{id: 1, label: 'Rim', delta_pp: 5, suppression_delta_pp: -10, fg_pct: 65, league_fg_pct: 60}],
  cells: [0.1, 0.4, 1, 2, 4].map((ratio, i) => [52.5 + i * 22, 250, 1, ratio * .002, ratio * .002, .002])}};
const offense = context.spatialHeatmapRegions(profile, 'offense');
assert.equal((offense.match(new RegExp(`fill="${context.spatialEfficiencyColor(5)}"`, 'g')) || []).length, 5);
const defense = context.spatialHeatmapRegions(profile, 'defense');
assert.equal((defense.match(/fill="#bd4b58"/g) || []).length, 5);
assert.equal(offense, context.spatialHeatmapRegions(profile, 'offense'));
const polygons = [...offense.matchAll(/points="([^"]+)"/g)].map(match => match[1].split(' ').map(point => point.split(',').map(Number)));
assert.equal(polygons.length, 5);
for (const polygon of polygons) {
  const lengths = polygon.map((point, i) => Math.hypot(point[0] - polygon[(i+1)%6][0], point[1] - polygon[(i+1)%6][1]));
  assert.ok(Math.max(...lengths) - Math.min(...lengths) < .15);
}
assert.equal(context.spatialHeatmapRegions({}, 'offense'), '');
console.log('Continuous colors, regular hex geometry, deterministic sizes and region color consistency: passed.');
