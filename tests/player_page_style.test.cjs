/* A player's page in the pages layout: the page sheet is loaded, scoped to the page version of the card, and reads
   the shared style values. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const strip = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');

test('the player page sheet is loaded by the page', () => {
  assert.match(read('index.html'), /href="\/player-page\.css\?v=[^"]+"/);
});

test('every rule in the player page sheet is scoped to .is-detail-card, so the small floating card is untouched', () => {
  const css = strip(read('player-page.css'));
  const selectors = [];
  for (const match of css.matchAll(/([^{}]+)\{/g)) {
    const text = match[1].trim();
    if (!text || text.startsWith('@')) continue;
    selectors.push(...text.split(',').map((s) => s.trim()).filter((s) => s && !/^(\d+(\.\d+)?%|from|to)$/.test(s)));
  }
  assert.ok(selectors.length > 40, 'the sheet has rules');
  for (const selector of selectors) assert.match(selector, /\.is-detail-card/, selector.slice(0, 120));
});

test('the player page sheet reads the shared values: no literal sizes, numeric weights, italic or hex colours', () => {
  const css = strip(read('player-page.css')).replace(/rgba?\([^)]*\)/g, '');
  assert.doesNotMatch(css, /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d/);
  assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, 'no hex colours');
});
