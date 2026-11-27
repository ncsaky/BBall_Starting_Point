/* Game sounds (UI polish pass, Stage B, 2026-11-25; user decision 7: on, quiet, button clicks off).

   Every sound is made in the browser with Web Audio: a few short tones, no files to download or license. Settings >
   Sound has an on/off switch, a volume slider and a separate switch for button clicks. Nothing can play until the
   player has clicked or pressed a key (a browser rule), and nothing plays while the tab is hidden.

   What plays when:
     continue   the main button moves time
     win, loss  your team's result after a sim (one game: that result; several: the better part of them)
     must       a job starts to block the clock
     deal       a trade goes through; a signing or extension is agreed
     pick       a draft selection is made
     reveal     a lottery envelope opens
     blocked    the game refuses an action (the red message)
     news       a trade offer or draft-night trade alert arrives
     champion   the title is won, once a year
     click      any button (its own switch, off by default) */
(() => {
  "use strict";

  const KEY = "nbaGmSound:v1";
  const DEFAULTS = {on: true, volume: 40, clicks: false};
  let settings = {...DEFAULTS};
  try { settings = {...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY) || "null") || {})}; } catch { /* defaults */ }
  let context = null, master = null, unlocked = false;
  const last = new Map();

  function audio() {
    if (!unlocked) return null;
    if (!context) {
      const Engine = window.AudioContext || window.webkitAudioContext;
      if (!Engine) return null;
      try {
        context = new Engine();
        master = context.createGain();
        master.connect(context.destination);
      } catch { context = null; return null; }
    }
    if (context.state === "suspended") context.resume().catch(() => {});
    master.gain.value = Math.max(0, Math.min(1, Number(settings.volume) / 100));
    return context;
  }

  // One tone: a frequency, when it starts, how long it rings, its shape and loudness, and an optional slide.
  function note(frequency, at, length, type = "sine", volume = .18, slideTo) {
    const start = context.currentTime + at;
    const oscillator = context.createOscillator(), gain = context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, start);
    if (slideTo) oscillator.frequency.exponentialRampToValueAtTime(slideTo, start + length);
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(volume, start + .008);
    gain.gain.exponentialRampToValueAtTime(.0008, start + length);
    oscillator.connect(gain).connect(master);
    oscillator.start(start);
    oscillator.stop(start + length + .05);
  }
  // A soft thump (filtered noise): the stamp under a finished deal.
  function thump(at, length = .09, volume = .3) {
    const source = context.createBufferSource();
    const buffer = context.createBuffer(1, Math.ceil(context.sampleRate * length), context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / data.length, 3);
    source.buffer = buffer;
    const filter = context.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 900;
    const gain = context.createGain();
    gain.gain.value = volume;
    source.connect(filter).connect(gain).connect(master);
    source.start(context.currentTime + at);
  }

  const SOUNDS = {
    continue: () => { note(196, 0, .12, "triangle", .16); note(262, .07, .18, "triangle", .16); },
    win: () => { note(523, 0, .14); note(659, .1, .26); },
    loss: () => { note(330, 0, .16, "sine", .14); note(262, .12, .3, "sine", .14); },
    must: () => { note(820, 0, .07, "sine", .2, 560); note(820, .14, .09, "sine", .16, 560); },
    deal: () => { thump(0); note(110, 0, .16, "sine", .25, 70); note(1319, .1, .5, "sine", .1); },
    pick: () => { note(659, 0, .16); note(784, .11, .16); note(1047, .22, .42); },
    reveal: () => { note(1100, 0, .03, "square", .06); note(1500, .05, .03, "square", .05); },
    blocked: () => { note(140, 0, .09, "square", .07); note(140, .13, .11, "square", .07); },
    news: () => { note(147, 0, .32, "sawtooth", .07); note(220, .05, .38, "sawtooth", .06); note(294, .28, .5, "triangle", .12); },
    champion: () => { [392, 523, 659, 784, 659, 1047].forEach((frequency, i) => note(frequency, i * .16, i === 5 ? .9 : .2, "triangle", .15)); },
    click: () => { note(180, 0, .04, "sine", .14); },
  };

  // force: play although sound is off (the Settings preview). The same sound is not repeated within a moment.
  function play(name, {force = false} = {}) {
    if (!SOUNDS[name] || (!settings.on && !force)) return false;
    if (name === "click" && !settings.clicks && !force) return false;
    if (document.hidden) return false;
    const now = Date.now();
    if (now - (last.get(name) || 0) < (name === "click" ? 40 : 180)) return false;
    if (!audio()) return false;
    last.set(name, now);
    try { SOUNDS[name](); } catch { return false; }
    return true;
  }

  function set(patch) {
    settings = {...settings, ...patch};
    settings.volume = Math.max(0, Math.min(100, Math.round(Number(settings.volume) || 0)));
    try { localStorage.setItem(KEY, JSON.stringify(settings)); } catch { /* this session only */ }
    if (master) master.gain.value = settings.volume / 100;
    return {...settings};
  }

  // Your team's result after a sim, from the record before and after.
  function result(before, after) {
    const wins = Number(after?.wins || 0) - Number(before?.wins || 0);
    const losses = Number(after?.losses || 0) - Number(before?.losses || 0);
    if (wins <= 0 && losses <= 0) return false;
    return play(wins >= losses ? "win" : "loss");
  }

  const unlock = () => { unlocked = true; };
  document.addEventListener("pointerdown", unlock, {capture: true, passive: true});
  document.addEventListener("keydown", unlock, {capture: true, passive: true});
  // The main button moving time, and (when switched on) any button.
  document.addEventListener("click", (event) => {
    const button = event.target.closest?.("button, [role=button]");
    if (!button || button.disabled) return;
    if (button.matches(".progress-go:not(.is-blocked), .pages-next:not(.pages-step), .progress-more[data-advance]")) play("continue");
    else play("click");
  }, true);

  window.GameSound = Object.freeze({play, set, result, settings: () => ({...settings}), names: () => Object.keys(SOUNDS)});
})();
