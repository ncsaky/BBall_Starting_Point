const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const board = fs.readFileSync(path.join(gui, 'card-board.js'), 'utf8');
const html = fs.readFileSync(path.join(gui, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(gui, 'tutorial.css'), 'utf8');

test('first-run tour explains the dashboard model and anchors to real windows', () => {
  const start = app.indexOf('const GAME_TUTORIAL_STEPS = [');
  const end = app.indexOf('\n];', start);
  assert.ok(start >= 0 && end > start);
  const steps = app.slice(start, end);
  for (const phrase of [
    'lineup fit, morale, fatigue, injuries and coaching',
    'Minutes are one of your most direct coaching decisions',
    'Weekly Efficiency compares your offense and defense',
    'finder suggests packages to evaluate; it does not execute them',
  ]) assert.ok(steps.includes(phrase), phrase);

  for (const id of ['minutes', 'signals', 'development', 'staff', 'week', 'efficiency']) {
    assert.ok(board.includes(`"${id}"`), `missing card-board target: ${id}`);
    assert.ok(steps.includes(`[data-board-window="${id}"]`), `tour does not target ${id}`);
  }
});

test('tour supports skip, arrow navigation, Escape, focus trapping, and blocks app actions', () => {
  assert.match(app, /data-tutorial-action="skip">Skip tutorial/);
  assert.match(app, /data-tutorial-action="previous"/);
  assert.match(app, /data-tutorial-action="next"/);
  assert.match(app, /event\.key === "Escape"[\s\S]*?finishGameTutorial\(\)/);
  assert.match(app, /document\.getElementById\("app"\)\.inert = true/);
  assert.match(app, /if \(state\.tutorial\) throw new Error\("Finish the tutorial before using game actions\."\)/);
  assert.match(app, /localStorage\.setItem\(TUTORIAL_COMPLETED_KEY, "1"\)/);
});

test('tour has a replay entry, an accessible dialog, and the 2000s modal-card styling', () => {
  assert.match(html, /id="gameTutorial" class="game-tutorial"/);
  assert.match(html, /href="\/tutorial\.css/);
  assert.match(app, /id="replayGameTutorial">Replay Tutorial/);
  assert.match(app, /role="dialog" aria-modal="true" aria-labelledby="gameTutorialTitle"/);
  assert.match(css, /\.game-tutorial-titlebar/);
  assert.match(css, /\.game-tutorial-arrow/);
  assert.match(css, /prefers-reduced-motion/);
});
