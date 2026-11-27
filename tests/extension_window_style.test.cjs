const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

test('the extension sheet is loaded by the page', () => {
  assert.match(read('index.html'), /href="\/extension-window\.css\?v=[^"]+"/);
});

test('every rule in the extension sheet starts from the extension section, so the rest of the player page is untouched', () => {
  const css = read('extension-window.css').replace(/\/\*[\s\S]*?\*\//g, '');
  const selectors = [];
  for (const match of css.matchAll(/([^{}]+)\{/g)) {
    const text = match[1].trim();
    if (!text || text.startsWith('@')) continue;
    // Split a selector list at top-level commas only (a comma inside :is( ... ) is not a new selector).
    let depth = 0, start = 0;
    const parts = [];
    for (let i = 0; i < text.length; i++) {
      if (text[i] === '(') depth++;
      else if (text[i] === ')') depth--;
      else if (text[i] === ',' && depth === 0) { parts.push(text.slice(start, i)); start = i + 1; }
    }
    parts.push(text.slice(start));
    selectors.push(...parts.map((s) => s.trim()).filter((s) => s && !/^(\d+(\.\d+)?%|from|to)$/.test(s)));
  }
  assert.ok(selectors.length > 40, 'the sheet has rules');
  for (const selector of selectors) assert.match(selector, /\.player-card-page--extension/, selector.slice(0, 140));
});

test('the extension sheet reads the shared values: no literal sizes, numeric weights, italic or hex colours', () => {
  const css = read('extension-window.css').replace(/\/\*[\s\S]*?\*\//g, '').replace(/rgba?\([^)]*\)/g, '');
  assert.doesNotMatch(css, /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d/);
  assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, 'no hex colours');
});
