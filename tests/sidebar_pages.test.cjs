// Pages layout (branch sidebar-pages): every board card has a page, the pages stylesheet loads last, and the layout
// choice is a remembered preference.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

function load(stored = {}) {
  const storage = new Map(Object.entries(stored));
  const html = {dataset: {}};
  const context = {
    window: {}, structuredClone, document: {documentElement: html},
    localStorage: {getItem: (key) => storage.has(key) ? storage.get(key) : null, setItem: (key, value) => storage.set(key, String(value))},
  };
  vm.createContext(context);
  vm.runInContext(read('card-pages.js'), context);
  return {pages: context.window.CardPages, html, storage};
}

test('every card the board can float has a page', () => {
  const source = read('card-board.js');
  const block = (name) => source.match(new RegExp(`const ${name} = \\[([\\s\\S]*?)\\n  \\];`))[1];
  const ids = [...`${block('CARDS')}${block('ASSET_CARDS')}`.matchAll(/\["([a-z-]+)", "/g)].map((match) => match[1]);
  assert.ok(ids.length >= 26, 'the board card lists were found');
  const {pages} = load();
  for (const id of ids) assert.ok(pages.PAGE_CARD_IDS.has(id), `${id} is on a page`);
  for (const id of ['phase-cutdown-decision', 'phase-set_roster-checklist', 'phase-playoffs-bracket', 'phase-draft-board', 'phase-free_agency-market', 'phase-fantasy_draft-board']) {
    assert.ok(pages.PAGE_CARD_IDS.has(id), `${id} is on a page`);
  }
});

test('pages have unique ids, a sidebar group and a label', () => {
  const {pages} = load();
  const ids = pages.PAGES.map((page) => page.id);
  assert.equal(new Set(ids).size, ids.length);
  for (const page of pages.PAGES) {
    assert.ok(['now', 'team', 'office', 'league'].includes(page.group), page.id);
    assert.ok(page.label, page.id);
    assert.ok(page.layout || page.slideshow, page.id);
  }
  for (const id of ['home', 'roster', 'contracts', 'trades', 'standings', 'schedule', 'outlook']) assert.ok(ids.includes(id), id);
});

test('pages are the default layout and the choice is remembered', () => {
  let {pages, html} = load();
  assert.equal(pages.enabled(), true);
  assert.equal(html.dataset.layout, 'pages');
  pages.setMode('board');
  assert.equal(html.dataset.layout, 'board');
  assert.equal(pages.enabled(), false);
  ({pages, html} = load({nbaGmLayoutMode: 'board'}));
  assert.equal(pages.enabled(), false);
  assert.equal(html.dataset.layout, 'board');
});

test('the pages stylesheet loads last and the module right after the board', () => {
  const html = read('index.html');
  const sheets = [...html.matchAll(/href="\/([^"?]+\.css)/g)].map((match) => match[1]);
  assert.equal(sheets.at(-1), 'card-pages.css');
  const scripts = [...html.matchAll(/src="\/([^"?]+\.js)/g)].map((match) => match[1]);
  assert.equal(scripts.indexOf('card-pages.js'), scripts.indexOf('card-board.js') + 1);
});

test('the board keeps its pop-ups inside the page area and hands page cards to the pages', () => {
  const board = read('card-board.js');
  assert.match(board, /const canvasScale = \(\) => \(window\.CardPages\?\.enabled\?\.\(\) \? 1 : CANVAS_SCALE\);/);
  assert.match(board, /if \(pages\?\.owns\(id\)\) return pages\.paint\(id\);/);
  assert.match(board, /if \(pages\?\.owns\(id\)\) \{ pages\.show\(id\); return; \}/);
  assert.match(board, /nbaGmCardBoard:v1:\$\{pagesMode \? "pages:" : ""\}/);
});
