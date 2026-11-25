// The board behind the glass is the team's arena: one picture per team, photos credited.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

test('every team has an arena picture and every photo among them is credited', () => {
  const app = read('app.js');
  const block = app.slice(app.indexOf('const TEAM_BRAND_COLORS = {'));
  const teams = [...block.slice(0, block.indexOf('};')).matchAll(/\b([A-Z]{3}): \[/g)].map((match) => match[1]);
  assert.equal(teams.length, 30);
  for (const team of teams) assert.ok(fs.existsSync(path.join(gui, `assets/arenas/${team}.jpg`)), team);
  const credits = JSON.parse(read('assets/arenas/credits.json'));
  assert.equal(credits.photos.length, 29, 'every team but Charlotte shows a photo');
  for (const photo of credits.photos) {
    assert.ok(photo.author && photo.licence && photo.source_url.startsWith('https://commons.wikimedia.org/'), photo.team);
    assert.ok(photo.edited, 'says it was edited');
  }
});

test('the user\'s team sets the arena, and the board and page glass use it', () => {
  assert.match(read('app.js'), /setProperty\("--arena-image", `url\("\/assets\/arenas\/\$\{team\}\.jpg"\)`\)/);
  assert.match(read('jfresh.css'), /background-image: var\(--arena-image\) !important;/);
  assert.match(read('card-pages.css'), /\[data-arena\] \.pages-sheet::before/);
});
