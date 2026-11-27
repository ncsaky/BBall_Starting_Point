// Background music (UI polish pass, 2026-11-26): six approved tracks (four CC0, two CC BY 4.0), off until switched on.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const read = (name) => fs.readFileSync(path.join(gui, name), 'utf8');

function load() {
  const made = [], listeners = {};
  class FakeAudio {
    constructor() { made.push(this); this.paused = true; this.volume = 1; this.duration = 200; this.currentTime = 0; this.events = {}; }
    addEventListener(type, fn) { this.events[type] = fn; }
    play() { this.paused = false; return Promise.resolve(); }
    pause() { this.paused = true; }
  }
  const list = JSON.parse(read('assets/music/tracks.json'));
  const context = {
    Audio: FakeAudio, Math, JSON, Number, Array, Promise, Set, Boolean,
    document: {hidden: false, addEventListener: (type, fn) => { listeners[type] = fn; }},
    localStorage: {getItem: () => null, setItem() {}},
    fetch: () => Promise.resolve({ok: true, json: () => Promise.resolve(list)}),
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(read('music.js'), context);
  return {music: context.window.GameMusic, made, listeners, list};
}

test('every track is a file in the game, under a licence the user approved, with its source', () => {
  const list = JSON.parse(read('assets/music/tracks.json'));
  assert.equal(list.tracks.length, 6);
  assert.equal(list.tracks.filter((track) => track.licence === 'CC0').length, 4);
  for (const track of list.tracks) {
    assert.ok(fs.existsSync(path.join(gui, 'assets/music', track.file)), track.file);
    // CC0 needs no credit; CC BY 4.0 needs the title, artist, source and licence link this list carries.
    assert.ok(['CC0', 'CC BY 4.0'].includes(track.licence), `${track.title}: ${track.licence} was not approved`);
    assert.ok(track.licence_url.startsWith('https://creativecommons.org/'), track.title);
    assert.ok(track.source_url.startsWith('https://opengameart.org/'), track.title);
    assert.ok(track.artist && track.edited, track.title);
  }
});

test('music is off by default, waits for a click, then plays, fades in, skips and stops', async () => {
  const {music, made, listeners} = load();
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.deepEqual({...music.settings()}, {on: false, volume: 35});
  assert.equal(music.tracks().length, 6);
  listeners.pointerdown();
  assert.equal(made.length, 0, 'nothing plays while it is off');
  music.set({on: true});
  assert.equal(made.length, 1);
  assert.equal(made[0].paused, false);
  assert.match(made[0].src, /^\/assets\/music\/.+\.mp3$/);
  made[0].events.timeupdate();
  assert.equal(made[0].volume, 0, 'a track starts silent');
  made[0].currentTime = 10;
  made[0].events.timeupdate();
  assert.ok(made[0].volume > 0 && made[0].volume <= .35 * .6 + 1e-9, 'and comes up to the music volume');
  const first = made[0].src;
  music.skip();
  assert.notEqual(made[0].src, first, 'Next track moves on');
  music.set({on: false});
  assert.equal(made[0].paused, true);
});

test('Settings > Sound has the music switch, its volume and Next track; the credits list names the tracks', () => {
  const app = read('app.js');
  for (const hook of ['data-music-choice', 'data-music-volume', 'data-music-skip', 'data-music-track']) assert.ok(app.includes(hook), hook);
  assert.match(app, /fetch\("\/assets\/music\/tracks\.json"/);
  assert.match(app, />Photo and music credits<\/button>/);
  assert.match(read('index.html'), /<script src="\/music\.js\?v=[^"]+" defer><\/script>/);
});
