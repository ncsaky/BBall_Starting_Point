const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');
const scope = {escapeHtml: String, decimalNumber: String, signedNumber: n => n >= 0 ? `+${n}` : String(n)};
vm.createContext(scope);
vm.runInContext(app.slice(app.indexOf('function boxScorePlayerTable('), app.indexOf('async function openBoxScore(')), scope);

test('missing legacy plus-minus is unavailable, not a fabricated zero', () => {
  for (const row of [{minutes: 30}, {minutes: 30, plus_minus: null}]) {
    const html = scope.boxScorePlayerTable([row]);
    assert.match(html, /Not tracked for this game">—<\/td>/);
    assert.doesNotMatch(html, />\+0<\/td>/);
  }
});

test('real zero and both signs display and DNP remains separate', () => {
  const html = scope.boxScorePlayerTable([
    {minutes: 30, plus_minus: 0}, {minutes: 20, plus_minus: 15}, {minutes: 10, plus_minus: -8}, {minutes: 0},
  ]);
  for (const value of ['+0', '+15', '-8']) assert.ok(html.includes(`>${value}</td>`));
  assert.match(html, /modeled five-player scoring stints/);
  assert.match(html, /class="box-score-dnp"/);
});
