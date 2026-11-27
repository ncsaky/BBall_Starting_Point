// Faults found by playing a season through the interface (2026-11-27).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');
const full = read('full-pages.css');

test('Sign Players: the list of players has a height', () => {
  assert.match(full, /\.required-clipboard-card:has\(\.cutdown-workspace\) \{[^}]*height: 100% !important/);
  assert.match(full, /\.required-clipboard-card \.cutdown-workspace \{ flex: 1 1 0; \}/);
});

test('Set The Roster: both answers to a decision have room', () => {
  assert.match(full, /\.offseason-checklist\.has-outlook \{ grid-template-columns: minmax\(0, 1fr\) 360px; \}/);
  assert.match(full, /\.offseason-checklist\.has-outlook \.offseason-table \.offseason-actions \{ overflow: visible !important/);
});

test('the next-game button goes to the game it names, and messages write the date out', () => {
  assert.match(app, /if \(mode === "next-game"\) return advance\(\{ to_date: button\.dataset\.advanceDate, next_event: false \}\);/);
  assert.match(read('progress.js'), /toGame \? `data-advance="next-game" data-advance-date=/);
  assert.doesNotMatch(app, /showToast\(`Advanced to \$\{state\.home/);
});

test('Home asks for the market again when a sim has emptied it', () => {
  assert.match(read('home-front.js'), /if \(marketDay === day && \(marketAsking \|\| st\.data\?\.tradeMarket\)\) return;/);
});

test('the footer is redrawn after a draft sim, old news says its year, and long draft names are not cut', () => {
  assert.match(app, /renderDashboard\(\);\n    window\.AssistantGMPhone\?\.setDraftPlaybackActive\?\.\(false\);/);
  const scope = {formatDashboardShortDate: (v) => v.slice(5)};
  require('node:vm').createContext(scope);
  require('node:vm').runInContext(app.slice(app.indexOf('function wireTickerDate('), app.indexOf('function formatDashboardShortDate(')), scope);
  assert.equal(scope.wireTickerDate('2026-07-03', '2027-06-24'), '07-03, 2026');
  assert.equal(scope.wireTickerDate('2027-12-01', '2028-02-01'), '12-01');
  assert.match(full, /\.draft-ledger-row > div > strong \{[^}]*white-space: normal !important/);
});

test('Home: no leaders before a game is played, no "Full" at twelve players, a glass confirm box', () => {
  const home = read('home-front.js');
  assert.match(home, /if \(!top\.length \|\| !\(Number\(top\[0\]\.value\) > 0\)\) return "";/);
  assert.match(home, /roster >= 15 \? "Full" : "of 15 places"/);
  assert.match(read('card-pages.css'), /\.ask-confirm \{ background: var\(--gm-glass-popup\);/);
});

test('Staff Retention takes the page and draft-night trades write the date out', () => {
  assert.match(read('card-pages.js'), /id: "staff-retention",[^\n]*card\("phase-staff_retention-decision", \{bare: true, fill: true\}\)/);
  assert.match(app, /<small>\$\{escapeHtml\(formatWrittenDate\(row\.date\) \|\| row\.date\)\}<\/small>/);
});
