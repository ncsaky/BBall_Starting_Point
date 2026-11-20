// Shared test helper: load the house table system (house-table.js and the app.js house-table block) into a vm scope
// so card markup functions run in isolation.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const houseSource = fs.readFileSync(path.join(gui, 'house-table.js'), 'utf8');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');

function houseBlock() {
  const start = app.indexOf('const SEASON_OPPONENT_SORT_KEYS');
  const end = app.indexOf('\nfunction seasonOpponentSortHeader(', start);
  if (start < 0 || end < 0) throw new Error('missing app.js house-table block');
  return app.slice(start, end);
}

function loadHouseTables(scope, {block = true} = {}) {
  scope.window ||= {};
  if (!scope.state) scope.state = {};
  vm.runInContext(houseSource, scope);
  scope.HouseTable = scope.window.HouseTable;
  if (block) vm.runInContext(houseBlock(), scope);
  return scope.HouseTable;
}

module.exports = {loadHouseTables, houseSource, houseBlock};
