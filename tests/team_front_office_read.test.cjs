// TRADE-FOLLOWUPS: another team's page (its dashboard header) has a Front Office button that opens your assistant
// GM's read on that front office: the same words as the trade window and the Trade Market board, no numbers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../src/nba_gm_data/gui/app.js'), 'utf8');

function extract(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} not found`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next);
}

const read = {abbrev: 'MEM', precision: 'sharp', lines: [
  {trait: 'patience', text: 'Very impatient: it wants deals done fast.'},
  {trait: 'habit', text: 'From your dealings: it overrates its own players.'}]};

function context() {
  const ctx = {
    state: {data: {dashboard: {team: 'MEM', front_office_read: read}}, dashboardTeam: 'MEM', modal: null},
    teamLabel: (team) => String(team || '').toUpperCase(),
    dashboardTeamName: () => 'Memphis Grizzlies',
    textValue: (value) => String(value ?? ''),
    escapeHtml: (value) => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    escapeAttr: (value) => String(value).replace(/"/g, '&quot;'),
    renderModal: () => { ctx.rendered = true; },
  };
  vm.createContext(ctx);
  vm.runInContext(`${extract('teamFrontOfficeButton')}\n${extract('openTeamFrontOfficeRead')}\n${extract('frontOfficeReadMarkup')}
this.teamFrontOfficeButton = teamFrontOfficeButton; this.openTeamFrontOfficeRead = openTeamFrontOfficeRead;`, ctx);
  return ctx;
}

test('the team page button opens the same read as the trade window', () => {
  const ctx = context();
  const button = ctx.teamFrontOfficeButton(read);
  assert.match(button, /data-team-front-office/);
  assert.match(button, /title="Very impatient: it wants deals done fast\."/);
  ctx.openTeamFrontOfficeRead();
  assert.equal(ctx.rendered, true);
  assert.equal(ctx.state.modal.kind, 'teamFrontOffice');
  assert.match(ctx.state.modal.title, /MEM Front Office/);
  assert.match(ctx.state.modal.body, /class="front-office-read"/);
  assert.match(ctx.state.modal.body, /Very impatient: it wants deals done fast\./);
  assert.match(ctx.state.modal.body, /from several dealings/);
  assert.doesNotMatch(ctx.state.modal.body.replace(/<[^>]+>/g, ''), /\d/);
});

test('the button shows only on another team page and is wired', () => {
  assert.match(app, /viewedTeam !== userTeam\(\) && dash\.front_office_read \? teamFrontOfficeButton\(dash\.front_office_read\)/);
  assert.match(app, /querySelectorAll\("\[data-team-front-office\]"\)/);
});
