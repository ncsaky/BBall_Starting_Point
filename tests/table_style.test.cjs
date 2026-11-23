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
  // The glass look loads last (round 3): the light glass, then the clear glass (round 4) and the font choice; the
  // table style sheet just before them.
  assert.deepEqual(links.slice(-4), ['table-style.css', 'glass.css', 'glass-clear.css', 'fonts.css']);
});

test('rows have no left bar on hover', () => {
  assert.doesNotMatch(read('styles.css'), /tbody tr:hover \{[^}]*border-left-color/);
  assert.match(read('table-style.css'), /table tbody tr \{ border-left: 0 !important; \}/);
});

test('header line is one thick dark bar, headers and sorted values are bold, sorted cells are shaded', () => {
  const css = read('table-style.css');
  // Taste deck 2026-11-23: one dark 3px line, not two tones.
  assert.match(css, /box-shadow: inset 0 -3px var\(--table-head-bar\) !important/);
  assert.doesNotMatch(css, /inset 0 -1px var\(--table-row-bar\), inset 0 -3px/);
  assert.match(css, /font-weight: 700 !important/);
  assert.match(css, /background-image: linear-gradient\(var\(--table-sorted-cell\)/);
  assert.match(css, /\.ss-sorted, \.is-sorted, \.is-sorted-value/);
});

test('every slideshow table header sorts on click, and split halves sort as one list', () => {
  const js = read('season-slideshow.js');
  assert.match(js, /<th scope="col"[^`]*data-ss-sort tabindex="0"/);
  assert.match(js, /closest\("\.ss-table th\[data-ss-sort\]"\)/);
  assert.match(js, /class="ss-two ss-compact" data-ss-split/);
  assert.match(js, /closest\("\[data-ss-split\]"\)/);
});

test('tables without their own sorting get click-to-sort; year-by-year ledgers do not', () => {
  const js = read('interface.js');
  assert.match(js, /function enhanceAutoSort\(scope\)/);
  assert.match(js, /enhance\(scope = document\) \{\n    enhanceAutoSort\(scope\);/);
  assert.match(js, /AUTO_SORT_SKIP = '\.ss-table, \.fa-cap-table, \[data-no-sort\]/);
  assert.doesNotMatch(js, /AUTO_SORT_SKIP = [^;]*trade-ledger/, 'the trade asset list sorts too');
  assert.match(js, /\^\(year\|season\)\$/);
});
