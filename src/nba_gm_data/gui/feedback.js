(() => {
  const actions = [];
  const errors = [];
  const limit = 40;
  const identifier = value => typeof value === "string" && /^[a-z][a-z0-9_-]{0,63}$/i.test(value) ? value : "unknown";
  const text = value => typeof value === "string" ? value.slice(0, 3000) : "";
  const number = value => Number.isFinite(Number(value)) ? Number(value) : null;
  const keep = (list, item) => { list.push(item); if (list.length > limit) list.shift(); };

  function recordAction(name, elapsed, succeeded) {
    keep(actions, {action: identifier(name), duration_ms: Math.max(0, Math.round(number(elapsed) || 0)), succeeded: Boolean(succeeded)});
  }

  async function runtime(headers) {
    const controller = new AbortController();
    let timer;
    try {
      return await Promise.race([
        (async () => {
          const auth = await headers();
          const response = await fetch("/api/action", {method: "POST", mode: "same-origin", headers: auth, signal: controller.signal, body: JSON.stringify({action: "diagnostic_runtime", payload: {}})});
          const data = await response.json();
          return response.ok && data.ok !== false ? data.result : null;
        })(),
        new Promise(resolve => { timer = setTimeout(() => { controller.abort(); resolve(null); }, 3500); }),
      ]);
    } catch (_) { return null; }
    finally { clearTimeout(timer); }
  }

  function snapshot(state, runtime = null, notes = {}) {
    const save = state.home?.save || {};
    const video = document.querySelector("video[data-startup-video]");
    const browser = (navigator.userAgent || "").match(/(Firefox|Edg|Chrome|Version)\/(\d+)/);
    const runtimeFields = ["version", "os", "os_release", "architecture", "python", "protocol"];
    const safeRuntime = runtime ? Object.fromEntries(runtimeFields.map(key => [key, text(runtime[key]).slice(0, 64)])) : null;
    if (safeRuntime) safeRuntime.packaged = Boolean(runtime.packaged);
    return {
      schema: "nba_gm_issue_v1",
      created_at: new Date().toISOString(),
      notes: Object.fromEntries(["summary", "steps", "expected", "actual"].map(key => [key, text(notes[key])])),
      runtime: safeRuntime,
      runtime_available: Boolean(safeRuntime),
      browser: {family: browser?.[1] === "Version" ? "Safari" : browser?.[1] || "unknown", major: browser?.[2] || null},
      display: {width: window.innerWidth, height: window.innerHeight, pixel_ratio: window.devicePixelRatio, reduced_motion: window.matchMedia("(prefers-reduced-motion: reduce)").matches},
      context: {
        screen: state.currentSave ? "game" : "save_selection",
        view: identifier(state.view),
        modal: state.modal?.kind === "issueReport" ? null : identifier(state.modal?.kind),
        phase: identifier(save.phase),
        date: /^\d{4}-\d{2}-\d{2}$/.test(save.current_date || "") ? save.current_date : null,
        season: /^\d{4}-\d{2}$/.test(save.season || "") ? save.season : null,
        multiplayer: Boolean(state.multiplayer?.session),
        visible_cards: [...document.querySelectorAll("[data-board-window]")].filter(el => !el.hidden && el.getClientRects().length).map(el => ({id: identifier(el.dataset.boardWindow), width: Math.round(el.getBoundingClientRect().width), height: Math.round(el.getBoundingClientRect().height)})).slice(0, 40),
      },
      startup_video: video ? {active: video.classList.contains("is-active"), paused: video.paused, ready_state: video.readyState, error_code: video.error?.code || null, time: number(video.currentTime)} : null,
      recent_actions: actions.map(item => ({...item})),
      browser_errors: errors.map(item => ({...item})),
      excluded: ["save contents", "save names", "file paths", "authentication tokens", "raw error messages", "logs", "screenshots"],
    };
  }

  window.addEventListener("error", () => keep(errors, {type: "javascript_error"}));
  window.addEventListener("unhandledrejection", () => keep(errors, {type: "unhandled_rejection"}));
  window.GameFeedback = {recordAction, snapshot, runtime};
})();
