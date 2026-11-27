const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const gui = path.join(__dirname, '..', 'src', 'nba_gm_data', 'gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');
const app = read('app.js');
const full = read('full-pages.css');

test('a prospect on a page has the court maps on their own tab, never over the college tables', () => {
  assert.match(app, /const prospectCourt = Boolean\(detail\.is_prospect\) && Boolean\(globalThis\.CardPages\?\.enabled\?\.\(\)\);/);
  assert.match(app, /const careerShift = careerFirst \|\| prospectCourt \? 1 : 0;/, 'the later tabs move up one');
  assert.match(app, /\$\{prospectCourt \? "" : court\}/, 'the floating card keeps the maps on its first page');
  assert.match(app, /\$\{prospectCourt \? `<section class="player-card-page player-card-page--overview player-card-page--hotspots"/);
});

test('a closed page stays readable: only its controls dim', () => {
  const css = read('card-pages.css');
  assert.doesNotMatch(css, /\.pages-slot\.is-locked \.pages-slot-body \{ opacity/);
  assert.match(css, /\.pages-slot\.is-locked \.pages-slot-body :is\(button, select, input\)[^{]*\{ opacity: \.55; \}/);
});

test('the faults the sweep found have their rules', () => {
  assert.match(read('free-agency.css'), /#app \.fa-offer-pay \.fa-pay-blocked \{[^}]*background: transparent !important;/);
  assert.match(full, /\.fa-builder \.salary-mark\.is-low i \{[^}]*margin-bottom/);
  assert.match(full, /\.player-name-text,[\s\S]{0,400}white-space: normal !important/);
  assert.match(read('home-front.css'), /\.front-hero \.front-meters \{ min-width: 340px; \}/);
  assert.match(read('popups-game.css'), /\.issue-report-form \{ padding:/);
  assert.match(read('extension-window.css'), /text\.extension-chart-muted \{ transform: translateY\(/);
});

test('the year-end cap lines say "over" instead of writing money below zero', () => {
  const slides = read('season-slideshow.js');
  assert.match(slides, /"Over the tax by" : "Room under the tax"/);
  assert.match(slides, /"Over the hard cap by" : "Hard cap room"/);
});

test('the value bars have a colour key, the season picker sits above its table, close salary marks take two rows', () => {
  assert.match(read('popups.css'), /footer > span\.value-contract::before \{ background: rgb\(/);
  assert.match(read('player-page.css'), /\.approved-season-line > header \{ position: relative !important; z-index: 5 !important; \}/);
  assert.match(app, /const rows = \[-1, -1, -1\];/);
  assert.match(app, /mark\.classList\.toggle\("is-lower", row === 2\);/);
});

test('three salary marks close together take three rows; marks far apart stay on one', () => {
  const code = app.slice(app.indexOf('function positionSalaryMarks('), app.indexOf('function contractLabel('));
  const place = (values) => {
    const marks = values.map((value) => {
      const on = new Set();
      return {on, dataset: {salaryMarkValue: String(value)}, style: {}, classList: {toggle: (name, yes) => (yes ? on.add(name) : on.delete(name))}};
    });
    const track = {clientWidth: 330, querySelector: () => ({min: '0', max: '100'}), querySelectorAll: () => marks};
    const scope = {};
    require('node:vm').runInNewContext(`${code}; this.run = positionSalaryMarks;`, scope);
    scope.run({querySelectorAll: () => [track]});
    return marks.map((mark) => (mark.on.has('is-lower') ? 2 : mark.on.has('is-low') ? 1 : 0));
  };
  assert.deepEqual(place([8, 23, 28]), [0, 1, 2]);
  assert.deepEqual(place([5, 45, 90]), [0, 0, 0]);
});
