// One table look across the game (user playtest 2026-11-22): no hover bar, flush two-tone header line,
// bold headers, shaded and bold sorted column.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = name => fs.readFileSync(path.join(gui, name), 'utf8');

test('table style sheet loads after every other style sheet', () => {
  const html = read('index.html');
  const links = [...html.matchAll(/href="\/([^"?]+\.css)/g)].map(m => m[1]);
  assert.equal(links.at(-1), 'table-style.css');
});

test('rows have no left bar on hover', () => {
  assert.doesNotMatch(read('styles.css'), /tbody tr:hover \{[^}]*border-left-color/);
  assert.match(read('table-style.css'), /table tbody tr \{ border-left: 0 !important; \}/);
});

test('header line is two flush bars, headers and sorted values are bold, sorted cells are shaded', () => {
  const css = read('table-style.css');
  assert.match(css, /inset 0 -1px var\(--table-row-bar\), inset 0 -3px var\(--table-head-bar\)/);
  assert.match(css, /font-weight: 700 !important/);
  assert.match(css, /background-image: linear-gradient\(var\(--table-sorted-cell\)/);
  assert.match(css, /\.ss-sorted, \.is-sorted, \.is-sorted-value/);
});
