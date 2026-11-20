#!/usr/bin/env node
/* Click through a season slideshow in headless Chrome with the keyboard and save a screenshot of every slide.
   Usage: node scripts/research/slideshow_capture.cjs <base-url> <save-path> <out-dir> <label> <width> <height> <mode> [reduce]
   mode: auto    - load the save and let the due slideshow open by itself (after the champion screen, if any)
         reopen:<kind> - open an existing slideshow from the Settings window
   Prints one JSON line per check. Needs Google Chrome; uses the DevTools protocol over Node's WebSocket. */
"use strict";
const {spawn} = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const [base, savePath, outDir, label, width, height, mode, reduce] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const port = 9300 + Math.floor(Math.random() * 500);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (row) => console.log(JSON.stringify(row));

async function main() {
  fs.mkdirSync(outDir, {recursive: true});
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "ss-chrome-"));
  const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run",
    "--disable-gpu", `--window-size=${width},${height}`, "about:blank"], {stdio: "ignore"});
  try {
    let targets;
    for (let i = 0; i < 50; i++) {
      try { targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); break; } catch { await sleep(200); }
    }
    const page = targets.find((t) => t.type === "page");
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((r) => ws.addEventListener("open", r, {once: true}));
    let id = 0;
    const pending = new Map();
    ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    });
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const n = ++id;
      pending.set(n, (msg) => (msg.error ? reject(new Error(`${method}: ${msg.error.message}`)) : resolve(msg.result)));
      ws.send(JSON.stringify({id: n, method, params}));
    });
    const evaluate = async (expression) => {
      const out = await send("Runtime.evaluate", {expression, awaitPromise: true, returnByValue: true});
      if (out.exceptionDetails) throw new Error(out.exceptionDetails.exception?.description || "eval failed");
      return out.result.value;
    };
    const waitFor = async (expression, ms = 60000) => {
      const end = Date.now() + ms;
      while (Date.now() < end) { if (await evaluate(expression).catch(() => false)) return true; await sleep(250); }
      throw new Error(`timeout waiting for ${expression}`);
    };
    const key = async (name) => {
      const codes = {ArrowRight: 39, ArrowLeft: 37, Enter: 13, Escape: 27};
      const common = {key: name, code: name, windowsVirtualKeyCode: codes[name], nativeVirtualKeyCode: codes[name]};
      await send("Input.dispatchKeyEvent", name === "Enter" ? {type: "keyDown", text: "\r", unmodifiedText: "\r", ...common} : {type: "rawKeyDown", ...common});
      await send("Input.dispatchKeyEvent", {type: "keyUp", ...common});
    };
    const shot = async (name) => {
      const out = await send("Page.captureScreenshot", {format: "png"});
      const file = path.join(outDir, `${label}-${name}.png`);
      fs.writeFileSync(file, Buffer.from(out.data, "base64"));
      return file;
    };

    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", {width: Number(width), height: Number(height), deviceScaleFactor: 1, mobile: false});
    if (reduce === "reduce") await send("Emulation.setEmulatedMedia", {features: [{name: "prefers-reduced-motion", value: "reduce"}]});
    await send("Page.navigate", {url: base});
    await waitFor("document.readyState === 'complete'");
    await evaluate(`localStorage.setItem("nbaGmFirstRunTutorialCompleted", "1"); localStorage.setItem("nbaGmLastSave", ${JSON.stringify(savePath)}); true`);
    await send("Page.navigate", {url: base});
    const ready = "typeof state !== 'undefined' && state.currentSave && state.home && !state.hydrating";
    try { await waitFor(ready, 60000); } catch {  // a slow first load: reload once
      log({label, step: "reload-after-slow-load"});
      await send("Page.reload", {ignoreCache: true});
      await waitFor(ready, 120000);
    }
    log({label, step: "loaded", reducedMotion: await evaluate("window.GameSimulation?.reducedMotion?.() || false")});

    if (mode === "auto") {
      await sleep(1500);
      if (await evaluate("state.modal?.kind === 'champion'")) {
        await shot("00-champion-screen");
        await key("Escape");
      }
      await waitFor("window.SeasonSlideshow.isOpen()", 90000);
    } else {
      const kind = mode.split(":")[1];
      await evaluate("closeAllModals(); openSettingsModal(); true");
      await waitFor(`!!document.querySelector('[data-season-slideshow="${kind}"]')`);
      await evaluate(`document.querySelector('[data-season-slideshow="${kind}"]').click(); true`);
      try { await waitFor("window.SeasonSlideshow.isOpen()", 90000); } catch (error) {
        log({label, step: "reopen-failed", diagnostics: await evaluate("({modal: state.modal?.kind || null, busy: state.busy, opening: !!state.slideshowOpening, toast: els.toast?.hidden ? null : els.toast?.textContent, tutorial: !!state.tutorial, sim: !!state.simulationRunning})")});
        throw error;
      }
    }
    const info = await evaluate("({kind: SeasonSlideshow.current().kind, season: SeasonSlideshow.current().season, count: document.querySelectorAll('.ss-dots i').length, inert: document.getElementById('app').inert || document.getElementById('app').hasAttribute('inert')})");
    log({label, step: "open", ...info});
    for (let i = 0; i < info.count; i++) {
      await sleep(reduce === "reduce" ? 150 : 400);
      const state = await evaluate(`(() => { const c = document.querySelector('.ss-card'); const b = document.querySelector('.ss-body'); const r = c.getBoundingClientRect();
        return {key: c.dataset.slide, index: SeasonSlideshow.current().index, animation: getComputedStyle(c).animationName,
                cardFits: r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight,
                pageScrollsSideways: document.documentElement.scrollWidth > innerWidth,
                bodyOverflowX: b.scrollWidth > b.clientWidth + 1, bodyScrolls: b.scrollHeight > b.clientHeight + 1,
                unavailable: !!document.querySelector('.ss-empty') && document.querySelector('.ss-empty').textContent }; })()`);
      const file = await shot(`${String(i + 1).padStart(2, "0")}-${state.key}`);
      log({label, step: "slide", file, ...state});
      await key(i % 2 ? "Enter" : "ArrowRight");
    }
    await sleep(500);
    log({label, step: "closed", open: await evaluate("SeasonSlideshow.isOpen()"), inert: await evaluate("document.getElementById('app').hasAttribute('inert')"),
         pending: await evaluate("JSON.stringify(state.home.save.season_slideshow?.pending || null)")});
    if (mode === "auto") {
      await send("Page.reload", {ignoreCache: true});
      await sleep(2000);
      await waitFor("typeof state !== 'undefined' && state.currentSave && state.home && !state.hydrating", 120000);
      await sleep(4000);
      if (await evaluate("state.modal?.kind === 'champion'")) await key("Escape");
      await sleep(3000);
      log({label, step: "reload-opens-again", open: await evaluate("SeasonSlideshow.isOpen()")});
    }
    ws.close();
  } finally {
    chrome.kill("SIGTERM");
  }
}

main().catch((error) => { console.error(error.stack || String(error)); process.exit(1); });
