// The arena behind the glass as one moving layer (UI polish pass, 2026-11-26): a different photo by phase where the
// team has one, a slow drift, a cross-fade, and a Settings switch.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

function load() {
  const context = {window: {}, Event: class {}, fetch: () => new Promise(() => {})};
  context.window.dispatchEvent = () => {};
  vm.createContext(context);
  vm.runInContext(read('arena.js'), context);
  return context.window.ArenaBackdrop;
}

test('a team shows its playoff or offseason photo in that phase when it has one, else the season photo', () => {
  const arena = load();
  const table = {BOS: {playoffs: 'BOS-playoffs.jpg', offseason: 'BOS-offseason.jpg'}, DAL: {offseason: 'DAL-offseason.jpg'}};
  assert.equal(arena.fileFor('BOS', 'regular_season', table), 'BOS.jpg');
  assert.equal(arena.fileFor('BOS', 'preseason', table), 'BOS.jpg');
  assert.equal(arena.fileFor('BOS', 'playoffs', table), 'BOS-playoffs.jpg');
  assert.equal(arena.fileFor('BOS', 'play_in', table), 'BOS-playoffs.jpg');
  for (const phase of ['draft', 're_signing', 'free_agency', 'offseason', 'training_camp']) assert.equal(arena.fileFor('BOS', phase, table), 'BOS-offseason.jpg', phase);
  assert.equal(arena.fileFor('DAL', 'playoffs', table), 'DAL.jpg', 'one other photo goes to the offseason');
  assert.equal(arena.fileFor('OKC', 'free_agency', table), 'OKC.jpg', 'a team with one photo keeps it all year');
});

test('every picture the phase list names exists and is credited', () => {
  const phases = JSON.parse(read('assets/arenas/phases.json'));
  const credited = new Set(JSON.parse(read('assets/arenas/credits.json')).photos.map((row) => row.file));
  let count = 0;
  for (const [team, kinds] of Object.entries(phases)) for (const [kind, file] of Object.entries(kinds)) {
    assert.ok(['playoffs', 'offseason'].includes(kind), `${team}: ${kind}`);
    assert.ok(fs.existsSync(path.join(gui, 'assets/arenas', file)), file);
    assert.ok(credited.has(`assets/arenas/${file}`), `${file} is credited`);
    count += 1;
  }
  assert.ok(count >= 20, 'most teams with several photos have phase pictures');
});

test('the layer drifts and cross-fades on the shared timings, and stands still when asked', () => {
  const css = read('arena.css');
  assert.match(css, /animation: arena-drift var\(--gm-motion-drift\) ease-in-out infinite alternate;/);
  assert.match(css, /transition: opacity var\(--gm-motion-scene\) ease/);
  assert.match(css, /html\[data-ui-motion="off"\] #arenaBackdrop > \.arena-layer \{ animation: none; transform: none; transition: none; \}/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\) \{ #arenaBackdrop > \.arena-layer \{ animation: none;/);
  const tokens = read('tokens.css');
  assert.match(tokens, /--gm-motion-scene: 1\.2s;/);
  assert.match(tokens, /--gm-motion-drift: 90s;/);
  const app = read('app.js');
  assert.match(app, /motion: \{ key: "nbaGmBackgroundMotion", label: "Background movement", fallback: "on"/);
  assert.match(app, /uiLookMenuMarkup\("motion"\)/);
  assert.match(app, /globalThis\.ArenaBackdrop\?\.show\?\.\(team, phase\);/);
  assert.match(read('arena.js'), /<img class="arena-layer"/, 'pictures are images: the look sheets strip background images');
});
