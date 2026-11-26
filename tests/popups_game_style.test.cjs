const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

test('popups-game.css is loaded by index.html', () => {
  assert.match(read('index.html'), /popups-game\.css/);
});

test('every rule in popups-game.css is scoped to #modalRoot', () => {
  const css = read('popups-game.css').replace(/\/\*[\s\S]*?\*\//g, '');
  const selectors = [];
  const re = /([^{}]+)\{[^{}]*\}/g;
  let match;
  while ((match = re.exec(css))) {
    const prelude = match[1].trim();
    if (prelude.startsWith('@')) continue;
    let depth = 0, current = '';
    for (const ch of prelude) {
      if (ch === '(') depth++;
      if (ch === ')') depth--;
      if (ch === ',' && depth === 0) { selectors.push(current.trim()); current = ''; } else current += ch;
    }
    selectors.push(current.trim());
  }
  assert.ok(selectors.length > 20);
  for (const selector of selectors) assert.ok(selector.includes('#modalRoot'), `not scoped: ${selector}`);
});

test('popups-game.css has no literal font sizes, numeric weights or italic', () => {
  const css = read('popups-game.css').replace(/\/\*[\s\S]*?\*\//g, '');
  assert.doesNotMatch(css.replace(/rgba?\([^)]*\)/g, ''), /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d/);
});
