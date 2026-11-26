const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

test('the pop-up sheet is loaded by the page', () => {
  assert.match(read('index.html'), /href="\/popups\.css\?v=[^"]+"/);
});

test('every rule in the pop-up sheet starts from #modalRoot, so pages are untouched', () => {
  const css = read('popups.css').replace(/\/\*[\s\S]*?\*\//g, '');
  const selectors = [];
  // A selector list is everything before a "{" that is not an at-rule line.
  for (const match of css.matchAll(/([^{}]+)\{/g)) {
    const text = match[1].trim();
    if (!text || text.startsWith('@')) continue;
    // The steps of a @keyframes block ("0%, 36%", "from", "to") are not selectors.
    selectors.push(...text.split(',').map((s) => s.trim()).filter((s) => s && !/^(\d+(\.\d+)?%|from|to)$/.test(s)));
  }
  assert.ok(selectors.length > 20, 'the sheet has rules');
  for (const selector of selectors) assert.match(selector, /#modalRoot/, selector.slice(0, 120));
});

test('the pop-up sheet reads the shared values: no literal sizes, numeric weights or italic', () => {
  const css = read('popups.css').replace(/\/\*[\s\S]*?\*\//g, '').replace(/rgba?\([^)]*\)/g, '');
  assert.doesNotMatch(css, /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d/);
  assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, 'no hex colours');
});
