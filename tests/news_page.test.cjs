// League › News as a page and League › Awards with ten candidates (UI polish pass, 2026-11-26).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

test('news kinds fall into the filters, and a kind reads as a plain label', () => {
  const context = {window: {}};
  vm.createContext(context);
  vm.runInContext(read('news-page.js'), context);
  const news = context.window.NewsPage;
  assert.equal(news.groupOf('trade'), 'trade');
  assert.equal(news.groupOf('extension'), 'contract');
  assert.equal(news.groupOf('option_decision'), 'contract');
  assert.equal(news.groupOf('staff_fire'), 'staff');
  assert.equal(news.groupOf('injury'), 'other');
  assert.equal(news.kindLabel('option_decision'), 'Option');
  assert.equal(news.kindLabel('draft_pick'), 'Draft pick');
});

test('the headline list is built from the same events as the posts, and a headline leads to its post', () => {
  const source = read('news-page.js');
  assert.match(source, /st\?\.home\?\.league_events\?\.events/);
  assert.match(source, /normalizeLeagueEvent\(event\)/);
  assert.match(source, /post\.scrollIntoView\(\{block: "start", behavior: "smooth"\}\)/);
  assert.match(source, /post\.hidden = filter !== "all" && !keep\.has\(post\.dataset\.leagueEventId \|\| ""\)/, 'a filter narrows the feed too');
  assert.match(read('index.html'), /<script src="\/news-page\.js\?v=[^"]+" defer><\/script>/);
  assert.match(read('index.html'), /href="\/news-awards\.css\?v=/);
});

test('the News and Awards sheet touches only full-size pages and reads the shared values', () => {
  const css = read('news-awards.css');
  for (const rule of css.split('\n').filter((line) => /\{/.test(line) && !/^\s*(\/\*|@|--|[a-z-]+:)/.test(line) && !line.startsWith(' '))) {
    assert.match(rule, /\.is-full/, rule.slice(0, 90));
  }
  assert.doesNotMatch(css.replace(/rgba?\([^)]*\)/g, ''), /font-size\s*:\s*\d|font:\s*[^;]*\b\d+px|font-style\s*:\s*italic|font-weight\s*:\s*\d/);
});

test('an award race lists ten candidates on a page and four in a board window', () => {
  assert.match(read('app.js'), /leaders\.slice\(0, globalThis\.CardPages\?\.enabled\?\.\(\) \? 10 : 4\)/);
});
