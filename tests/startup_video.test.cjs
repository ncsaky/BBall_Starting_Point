const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const crypto = require('node:crypto');

const gui = path.join(__dirname, '../src/nba_gm_data/gui');
const app = fs.readFileSync(path.join(gui, 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(gui, 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(gui, 'startup.css'), 'utf8');
const player = fs.readFileSync(path.join(gui, 'startup-video.js'), 'utf8');

function fixture({hidden = false, reduced = false} = {}) {
  const events = () => ({listeners: {}, addEventListener(type, handler) {this.listeners[type] = handler;},
    emit(type) {this.listeners[type]?.();}});
  const makeVideo = () => {
    const classes = new Set();
    return {...events(), classes, dataset:{}, plays:0, pauses:0, loads:0,
      classList:{add:name => classes.add(name), remove:name => classes.delete(name)},
      hasAttribute(name) {return name === 'src' && Boolean(this.src);},
      removeAttribute(name) {if (name === 'src') this.src = '';},
      load() {this.loads++;}, pause() {this.pauses++;},
      play() {this.plays++; return this.reject ? Promise.reject(this.reject) : Promise.resolve();},
      cloneNode() {return makeVideo();},
      after(node) {this.nextSibling = node;},
    };
  };
  const video = makeVideo();
  const screen = {...events(), hidden, dataset:{},
    querySelector:selector => selector === 'video[data-startup-video]' ? video : null};
  const motion = {...events(), matches:reduced};
  const document = {...events(), visibilityState:'visible',
    getElementById:id => id === 'startupScreen' ? screen : null};
  const window = {};
  vm.runInNewContext(player, {
    window, document, matchMedia:() => motion, setTimeout, clearTimeout,
    MutationObserver:class { observe() {} },
    fetch:async () => ({ok:true, json:async () => ({teams:{}})}),
  });
  return {document, screen, video, standby:video.nextSibling, motion, sync:window.StartupVideoBackdrop.sync};
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('startup movie is bundled, silent, and alternates real action and draft rooms', () => {
  const assets = path.join(gui, 'assets/startup/video');
  const manifest = JSON.parse(fs.readFileSync(path.join(assets, 'manifest.json')));
  const movie = fs.readFileSync(path.join(assets, 'front-office.mp4'));
  assert.equal(crypto.createHash('sha256').update(movie).digest('hex'), manifest.sha256);
  assert.equal(movie.length, manifest.bytes);
  const credits = fs.readFileSync(path.join(gui, 'assets/startup/VIDEO_SOURCES.md'), 'utf8');
  assert.ok(credits.includes(manifest.duration_seconds.toFixed(3) + '-second'));
  for (const source of Object.values(manifest.sources)) assert.ok(credits.includes(source.id));
  assert.match(credits, /variable ink-dot area/);
  assert.equal(manifest.logical_clip_count, 11);
  assert.equal(manifest.segments.filter(s => s.kind === 'basketball').length, 6);
  assert.ok(manifest.segments.filter(s => s.kind === 'front-office').length >= 5);
  assert.equal(manifest.frames, manifest.segments.reduce((n,s) => n + s.frames, 0) + manifest.transitions.reduce((n,t) => n + t.frames, 0));
  assert.equal(manifest.duration_seconds, manifest.frames / 30);
  assert.equal(new Set(Object.values(manifest.sources).map(s => s.id)).size, 3);
  assert.match(manifest.treatment.method, /tone changes.*ink-dot area/i);
  assert.ok(Object.values(manifest.sources).every(s => s.full_decode === 'passed'));
  assert.ok(manifest.transitions.some(t => t.boundary_kind === 'internal_source_cut'));
  assert.equal(manifest.transitions.filter(t => t.loop_boundary).length, 1);
  for (const segment of manifest.segments.filter(s => s.kind === 'basketball')) {
    assert.ok(segment.payoff_source_seconds > segment.source_start);
    assert.ok(segment.payoff_source_seconds < segment.source_end_exclusive - .5, segment.id + ' payoff precedes distortion buildup');
  }
  assert.match(html, /<video class="startup-video-player" data-startup-video muted loop playsinline/);
  assert.match(html, /preload="none"/);
  assert.doesNotMatch(html, /youtube.*embed|data-video-deck|startup-video-fallback-player/);
  assert.doesNotMatch(player, /youtube|iframe|window\.YT|createElement\("script"\)/i);
  assert.match(app, /window\.StartupVideoBackdrop\?\.sync\(\)/);
});

test('playing activates the connected video; hidden selectors release it and can return', async () => {
  const f = fixture({hidden:true});
  let playbackStarted;
  const pendingPlayback = new Promise(resolve => {playbackStarted = resolve;});
  f.video.play = () => pendingPlayback;
  f.screen.hidden = false;
  f.sync();
  assert.equal(f.video.src, '/assets/startup/video/front-office.mp4');
  assert.equal(f.video.muted, true);
  assert.equal(f.video.loop, true);
  assert.equal(f.screen.dataset.startupVideo, undefined);
  playbackStarted();
  await settle();
  assert.equal(f.screen.dataset.startupVideo, 'playing');
  assert.ok(f.video.classes.has('is-active'));
  f.screen.hidden = true;
  f.sync();
  assert.equal(f.video.src, '');
  assert.equal(f.standby.hasAttribute('src'), false);
  assert.equal(f.screen.dataset.startupVideo, undefined);
  f.screen.hidden = false;
  f.sync();
  await settle();
  assert.equal(f.screen.dataset.startupVideo, 'playing');
});

test('reduced motion prevents downloads and background tabs stop playback', async () => {
  const f = fixture({reduced: true});
  assert.equal(f.video.plays, 0);
  assert.equal(f.video.src, undefined);
  f.motion.matches = false;
  f.motion.emit('change');
  await settle();
  const pausesBeforeHide = f.video.pauses;
  const playsBeforeHide = f.video.plays;
  f.document.visibilityState = 'hidden';
  f.document.emit('visibilitychange');
  assert.equal(f.screen.dataset.startupVideo, 'playing');
  assert.ok(f.video.pauses > pausesBeforeHide);
  f.document.visibilityState = 'visible';
  f.document.emit('visibilitychange');
  await settle();
  assert.equal(f.video.plays, playsBeforeHide + 1);
});

test('autoplay denial leaves photos visible and a user gesture resumes', async () => {
  const f = fixture({hidden: true});
  f.video.reject = {name: 'NotAllowedError'};
  f.screen.hidden = false;
  f.sync();
  await settle();
  assert.equal(f.screen.dataset.startupVideo, undefined);
  f.video.reject = null;
  f.screen.emit('pointerdown');
  await settle();
  assert.equal(f.screen.dataset.startupVideo, 'playing');
});

test('missing or corrupt movie releases the failed source and leaves the photos visible', async () => {
  const f = fixture({hidden:true});
  f.video.reject = {name:'NotSupportedError'};
  f.screen.hidden = false;
  f.sync();
  await settle();
  assert.equal(f.video.src, '');
  assert.equal(f.video.plays, 1);
  assert.equal(f.screen.dataset.startupVideo, undefined);
  assert.equal(f.video.classes.has('is-active'), false);
});

test('missing or corrupt movie does not retry on every click', {todo:'The default channel ignores its recorded playback failure'}, async () => {
  const f = fixture({hidden:true});
  f.video.reject = {name:'NotSupportedError'};
  f.screen.hidden = false;
  f.sync();
  await settle();
  f.screen.emit('pointerdown');
  await settle();
  f.screen.emit('pointerdown');
  await settle();
  assert.equal(f.video.plays, 1);
});

test('late rejected playback cannot break a later selector visit', async () => {
  const f = fixture({hidden: true});
  let reject;
  f.video.play = () => new Promise((resolve, fail) => {reject = fail;});
  f.screen.hidden = false;
  f.sync();
  f.screen.hidden = true;
  f.sync();
  reject({name: 'NotSupportedError'});
  await settle();
  f.video.play = () => Promise.resolve();
  f.screen.hidden = false;
  f.sync();
  await settle();
  assert.equal(f.screen.dataset.startupVideo, 'playing');
});

test('baked dot footage preserves its color glitches and full framing without a runtime dot overlay', () => {
  assert.match(css, /\.startup-video-dots\s*\{[^}]*display:\s*none/s);
  assert.match(css, /\.startup-video-player\s*\{[^}]*filter:\s*none/s);
  assert.match(css, /\.startup-video-player\s*\{[^}]*object-fit:\s*contain/s);
  assert.match(css, /\.startup-screen\[data-startup-video="playing"\]:has\(\.startup-video-player\.is-active\) \.startup-photo-rail \{ opacity: 0; \}/);
  assert.match(css, /prefers-reduced-motion/);
});

test('save selector uses three independent cards without the oversized brand bar', () => {
  assert.match(html, /<div class="startup-content">/);
  assert.match(html, /<section class="startup-pane startup-load-pane" data-startup-pane="load">/);
  assert.match(html, /<section class="startup-pane startup-new-pane" data-startup-pane="new">/);
  assert.match(html, /<section class="startup-pane multiplayer-start-card" data-startup-pane="multiplayer">/);
  assert.doesNotMatch(html, /startup-window-bar|FRONT OFFICE TERMINAL/);
  assert.match(css, /\.startup-grid > \.startup-pane\s*\{[^}]*box-shadow:/s);
  assert.match(css, /#startupRefreshSaves\s*\{[^}]*min-height:/s);
});

test('team wheel shows logos without square tiles and keeps a legible random mark', () => {
  assert.match(css, /\.startup-grid > \.startup-pane \.startup-team-option\s*\{[^}]*background:\s*transparent/s);
  assert.match(css, /\.startup-grid > \.startup-pane \.startup-team-option\.is-locked\s*\{[^}]*box-shadow:\s*none/s);
  assert.match(css, /\.startup-team-option:focus-visible \.startup-team-logo\s*\{[^}]*filter:/s);
  assert.match(css, /\.startup-wheel-random-mark\s*\{[^}]*color:\s*#17212a/);
});
