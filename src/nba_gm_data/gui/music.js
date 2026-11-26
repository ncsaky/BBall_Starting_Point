/* Background music (UI polish pass, 2026-11-26; the user asked for "free chill beats" and approved these four
   tracks). Four public-domain tracks from OpenGameArt in assets/music/ (tracks.json lists them with their sources).
   Off until the player turns it on in Settings > Sound, with its own volume, apart from the sound effects.

   The tracks play in a shuffled order, each fading in and out, a short track repeating once so the changes are not
   too quick. Nothing plays until the player has clicked or pressed a key (a browser rule), and the music pauses while
   the tab is hidden. */
(() => {
  "use strict";
  const KEY = "nbaGmMusic:v1";
  const DEFAULTS = {on: false, volume: 35};
  const FADE = 1.6;          // seconds a track takes to come in and to go out
  const SHORT = 120;         // a track shorter than this many seconds plays twice
  let settings = {...DEFAULTS};
  try { settings = {...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY) || "null") || {})}; } catch { /* defaults */ }
  let tracks = [], order = [], at = -1, plays = 0, player = null, unlocked = false, wanted = false;
  const listeners = new Set();

  const level = () => Math.max(0, Math.min(1, Number(settings.volume) / 100)) * .6;
  const current = () => (at >= 0 ? tracks[order[at]] : null);
  const tell = () => { for (const listener of listeners) { try { listener(current()); } catch { /* a listener's own problem */ } } };

  // A new shuffled order that does not start with the track that just played.
  function shuffle(last) {
    const next = tracks.map((_, index) => index);
    for (let i = next.length - 1; i > 0; i -= 1) { const j = Math.floor(Math.random() * (i + 1)); [next[i], next[j]] = [next[j], next[i]]; }
    if (next.length > 1 && next[0] === last) next.push(next.shift());
    return next;
  }

  function ensure() {
    if (player || typeof Audio === "undefined") return player;
    player = new Audio();
    player.preload = "auto";
    player.addEventListener("timeupdate", () => {
      // Fade in from the start, fade out before the end.
      const left = (player.duration || 0) - player.currentTime;
      const fade = Math.min(1, player.currentTime / FADE, Number.isFinite(left) && left > 0 ? left / FADE : 1);
      player.volume = Math.max(0, Math.min(1, level() * fade));
    });
    player.addEventListener("ended", () => {
      const track = current();
      plays += 1;
      if (track && Number(player.duration) < SHORT && plays < 2) { player.currentTime = 0; player.play().catch(() => {}); return; }
      advance();
    });
    player.addEventListener("error", () => { if (wanted && tracks.length > 1) advance(); });
    return player;
  }

  function advance() {
    if (!tracks.length || !ensure()) return;
    const last = at >= 0 ? order[at] : -1;
    at += 1;
    if (at >= order.length) { order = shuffle(last); at = 0; }
    plays = 0;
    player.src = `/assets/music/${tracks[order[at]].file}`;
    player.volume = 0;
    tell();
    if (wanted && !document.hidden) player.play().catch(() => {});
  }

  // Start or stop to match the setting, once the browser lets sound play.
  function sync() {
    wanted = Boolean(settings.on) && unlocked && tracks.length > 0;
    if (!wanted) { player?.pause(); return; }
    if (!ensure()) return;
    if (at < 0) { advance(); return; }
    if (player.paused && !document.hidden) player.play().catch(() => {});
  }

  function set(patch) {
    settings = {...settings, ...patch};
    settings.volume = Math.max(0, Math.min(100, Math.round(Number(settings.volume) || 0)));
    settings.on = Boolean(settings.on);
    try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch { /* this session only */ }
    if (player && !player.paused) player.volume = Math.min(player.volume, level()) || level();
    sync();
    return {...settings};
  }

  if (typeof document !== "undefined") {
    const unlock = () => { if (!unlocked) { unlocked = true; sync(); } };
    document.addEventListener("pointerdown", unlock, {capture: true, passive: true});
    document.addEventListener("keydown", unlock, {capture: true, passive: true});
    document.addEventListener("visibilitychange", () => { if (document.hidden) player?.pause(); else sync(); });
    fetch("/assets/music/tracks.json", {cache: "no-cache"}).then((response) => response.ok ? response.json() : {tracks: []}).then((list) => {
      tracks = Array.isArray(list.tracks) ? list.tracks.filter((track) => track && track.file) : [];
      order = shuffle(-1);
      sync();
    }).catch(() => { tracks = []; });
  }

  window.GameMusic = Object.freeze({
    settings: () => ({...settings}),
    set,
    skip: () => { if (wanted) advance(); },
    current: () => { const track = current(); return track ? {title: track.title, artist: track.artist} : null; },
    tracks: () => tracks.map((track) => ({title: track.title, artist: track.artist})),
    onChange: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
  });
})();
