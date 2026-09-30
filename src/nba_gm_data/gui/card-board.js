/* Window placement is a browser preference, never a basketball save mutation. */
(() => {
  "use strict";

  const TITLE_HEIGHT = 24;
  const LIMIT = 20000;
  const CARDS = [
    ["identity", ".season-identity-panel", "Team Identity"],
    ["signals", ".season-signal-card:nth-child(1)", "Team Signals"],
    ["morale", ".season-signal-card:nth-child(2)", "Morale"],
    ["factors", ".season-signal-card:nth-child(3)", "Four Factors"],
    ["offense", ".season-radar-card:nth-child(1)", "Offense"],
    ["defense", ".season-radar-card:nth-child(2)", "Defense"],
    ["standings", ".season-standings-panel", "Standings"],
    ["week", ".season-week-panel", "This Week"],
    ["opponent", ".season-opponent-panel", "Next Opponent"],
    ["minutes", ".season-minutes-panel", "Minutes + Availability"],
    ["efficiency", ".season-efficiency-panel", "Weekly Efficiency"],
    ["prospects", ".season-prospects-panel", "Upcoming Prospects"],
    ["award-mvp", ".season-awards-grid > section:nth-child(1)", "MVP"],
    ["award-dpoy", ".season-awards-grid > section:nth-child(2)", "DPOY"],
    ["award-roty", ".season-awards-grid > section:nth-child(3)", "ROTY"],
    ["staff", ".season-staff-panel", "Coaching Staff"],
    ["league-wire", ".season-league-wire", "League Wire"],
  ];
  const ASSET_CARDS = [
    ["roster", ".assets-roster", "Roster + Contracts"],
    ["payroll", ".assets-payroll", "Four-Year Payroll Share"],
    ["picks", ".assets-picks", "Draft Assets"],
    ["league-block", ".assets-block", "League Block"],
    ["team-block", ".assets-team-block", "Team Block"],
    ["trade-builder", '[data-assets-trade="builder"]', "Trade Builder"],
    ["trade-finder", '[data-assets-trade="finder"]', "Trade Finder"],
  ];
  const memory = new Map();
  let active = null;

  const bounded = (number, min, max) => Math.min(max, Math.max(min, number));
  const icon = (name) => `<img src="/assets/window-icons/${name}.svg" alt="" aria-hidden="true">`;

  function defaultLayout(measurements) {
    const result = {};
    const ordered = [...measurements].sort((a, b) => a.y - b.y || a.x - b.x);
    for (const card of ordered) {
      let y = card.y;
      for (const previous of ordered) {
        if (!result[previous.id]) continue;
        const overlaps = previous.x < card.x + card.width - 1 && card.x < previous.x + previous.width - 1;
        if (overlaps && previous.y + previous.height <= card.y + 1) {
          y = Math.max(y, result[previous.id].y + previous.height + TITLE_HEIGHT + 4);
        }
      }
      result[card.id] = { x: card.x, y, width: card.width, height: card.height, visible: true, pinned: false, minimized: false, z: Object.keys(result).length + 1 };
    }
    const wire = result["league-wire"];
    if (wire) {
      wire.x = 0;
      wire.y = Math.max(...Object.entries(result).filter(([id]) => id !== "league-wire").map(([, card]) => card.y + card.height + TITLE_HEIGHT + 4));
    }
    return result;
  }

  function restoreLayout(raw, defaults) {
    let saved;
    try { saved = JSON.parse(raw); } catch { return structuredClone(defaults); }
    if (saved?.version !== 1 || !saved.cards || typeof saved.cards !== "object") return structuredClone(defaults);
    const result = structuredClone(defaults);
    for (const id of Object.keys(result)) {
      const card = saved.cards[id];
      if (!card || typeof card !== "object") continue;
      for (const [field, min, max] of [["x", 0, LIMIT], ["y", 0, LIMIT], ["width", 100, 4000], ["height", 40, 4000], ["z", 1, 1000]]) {
        if (Number.isFinite(card[field])) result[id][field] = bounded(card[field], min, max);
      }
      if (typeof card.visible === "boolean") result[id].visible = card.visible;
      if (typeof card.pinned === "boolean") result[id].pinned = card.pinned;
      if (typeof card.minimized === "boolean") result[id].minimized = card.minimized;
    }
    return result;
  }

  function unmount() {
    active?.dispose();
    active = null;
  }

  function mount(root, options = {}) {
    unmount();
    const dashboard = root.querySelector(".season-command-dashboard:not(.assets-desktop)");
    const board = dashboard?.querySelector(".season-command-grid");
    if (!board) return;
    const offset = (element) => {
      let x = 0, y = 0;
      for (let node = element; node; node = node.offsetParent) { x += node.offsetLeft; y += node.offsetTop; }
      return { x, y };
    };
    const origin = offset(board);
    const nodes = new Map();
    const measurements = [];
    for (const [id, selector, title] of CARDS) {
      const card = id === "league-wire" ? dashboard.querySelector(selector) : board.querySelector(selector);
      if (!card) continue;
      const position = offset(card), style = getComputedStyle(card);
      const width = parseFloat(style.width), height = parseFloat(style.height);
      if (width < 1 || height < 1) continue;
      nodes.set(id, { card, title });
      measurements.push({ id, x: position.x - origin.x, y: position.y - origin.y, width, height });
    }
    if (!nodes.size) return;
    const defaults = defaultLayout(measurements);
    for (const [id, selector, title] of ASSET_CARDS) {
      const card = options.assetsRoot?.querySelector(selector);
      if (!card) continue;
      const style = getComputedStyle(card);
      nodes.set(id, {card, title, assets: true});
      defaults[id] = {x:16, y:16, width:Math.max(100,parseFloat(style.width)), height:Math.max(40,parseFloat(style.height)), visible:false, pinned:false, minimized:false, z:nodes.size};
    }
    const key = `nbaGmCardBoard:v1:${options.save || "preview"}`;
    let raw = memory.get(key);
    try { raw = localStorage.getItem(key) || raw; } catch { /* Private browsing can deny preference storage. */ }
    let layout = restoreLayout(raw, defaults);
    let drag = null;
    let galleryOpen = false;

    const canvas = document.createElement("div");
    canvas.className = "card-board-canvas";
    canvas.setAttribute("aria-label", "Card workspace");
    const gallery = document.createElement("aside");
    gallery.className = "card-board-gallery";
    gallery.hidden = true;
    gallery.id = "seasonCardGallery";
    gallery.setAttribute("aria-label", "Card gallery");
    gallery.innerHTML = `<header class="card-board-gallery-head"><h2>Cards</h2><button type="button" class="card-board-control" data-board-gallery-close aria-label="Close card gallery" title="Close card gallery">${icon("x")}</button></header><div class="card-board-gallery-list"></div>`;
    const galleryList = gallery.querySelector(".card-board-gallery-list");
    const toolbar = document.createElement("div");
    toolbar.className = "card-board-tools";
    toolbar.innerHTML = `<button type="button" class="card-board-gallery-toggle" aria-controls="seasonCardGallery" aria-expanded="false" title="Card gallery">${icon("panels-top-left")}<span>Cards</span></button><button type="button" class="card-board-control" data-board-reset aria-label="Restore original card layout" title="Restore original card layout">${icon("rotate-ccw")}</button>`;
    dashboard.querySelector(".season-command-actions").prepend(toolbar);
    const toggle = toolbar.querySelector(".card-board-gallery-toggle");
    const status = document.createElement("div");
    status.className = "card-board-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");

    const frames = new Map();
    for (const [id, { card, title, assets }] of nodes) {
      const frame = document.createElement("section");
      frame.className = "card-board-window";
      frame.dataset.boardWindow = id;
      frame.setAttribute("aria-label", `${title} window`);
      frame.innerHTML = `<header class="card-board-titlebar"><button type="button" class="card-board-move" data-board-move="${id}" aria-label="Move ${title}" title="Move ${title}"><span class="card-board-window-mark" aria-hidden="true"></span><span>${title}</span></button><div class="card-board-window-controls"><button type="button" class="card-board-control" data-board-pin="${id}" aria-label="Pin ${title}" title="Pin ${title}" aria-pressed="false">${icon("pin")}</button><button type="button" class="card-board-control" data-board-minimize="${id}" aria-label="Minimize ${title}" title="Minimize ${title}" aria-expanded="true">${icon("minus")}</button><button type="button" class="card-board-control card-board-close" data-board-close="${id}" aria-label="Close ${title}" title="Close ${title}">${icon("x")}</button></div><div class="card-board-actions" hidden></div></header>`;
      const body = document.createElement("div");
      body.className = `card-board-body${card.matches(".season-radar-card") ? " season-radars-stack" : ""}${assets ? " assets-desktop" : ""}${card.matches("[data-assets-trade]") ? " assets-trade-tools" : ""}`;
      body.append(card);
      frame.append(body);
      canvas.append(frame);
      frames.set(id, frame);
    }
    board.replaceChildren(canvas);
    options.assetsRoot?.remove();
    board.classList.add("card-board-scroll");
    dashboard.classList.add("has-card-board");
    board.parentElement.append(gallery, status);

    const announce = (message) => { status.textContent = message; };
    const save = () => {
      const value = JSON.stringify({ version: 1, cards: layout });
      memory.set(key, value);
      try { localStorage.setItem(key, value); } catch { /* The in-memory board still works. */ }
    };
    const sizeCanvas = () => {
      const visible = Object.entries(layout).filter(([,card]) => card.visible);
      canvas.style.width = `${Math.max(board.clientWidth, ...visible.map(([,card]) => card.x + card.width + 12))}px`;
      canvas.style.height = `${Math.max(board.clientHeight, ...visible.map(([id,card]) => card.y + frames.get(id).offsetHeight + 12))}px`;
    };
    const parkedActions = new Map();
    const syncActions = (id) => {
      const frame = frames.get(id), card = nodes.get(id).card;
      const actions = frame.querySelector(".card-board-actions");
      if (layout[id].minimized && !parkedActions.has(id)) {
        const buttons = card.matches("[data-assets-trade]") ? [card] : [
          ...card.querySelectorAll(":scope > .season-panel-header button, :scope > .season-award-head button, .season-sim-actions button, [data-assets-block-nav], [data-assets-retry]"),
          ...(card.matches(".season-league-wire") ? [card.querySelector(":scope > [data-league-panel-view-all]")].filter(Boolean) : []),
        ];
        parkedActions.set(id, buttons.map(button => {
          const marker = document.createComment("window command position");
          button.before(marker);
          actions.append(button);
          return {button, marker};
        }));
      } else if (!layout[id].minimized && parkedActions.has(id)) {
        for (const {button, marker} of parkedActions.get(id)) {
          if (marker.isConnected) marker.replaceWith(button);
          else button.remove();
        }
        parkedActions.delete(id);
      }
      actions.hidden = !layout[id].minimized || !actions.childElementCount;
    };
    const paint = (id) => {
      const item = layout[id];
      const frame = frames.get(id);
      frame.hidden = !item.visible;
      frame.classList.toggle("is-pinned", item.pinned);
      frame.classList.toggle("is-minimized", item.minimized);
      syncActions(id);
      Object.assign(frame.style, { left: `${item.x}px`, top: `${item.y}px`, width: `${item.width}px`, height: item.minimized ? "auto" : `${item.height + TITLE_HEIGHT}px`, zIndex: String(item.z) });
      Object.assign(nodes.get(id).card.style, { width: `${item.width}px`, height: `${item.height}px` });
      const pin = frame.querySelector("[data-board-pin]");
      pin.setAttribute("aria-pressed", String(item.pinned));
      pin.setAttribute("aria-label", `${item.pinned ? "Unpin" : "Pin"} ${nodes.get(id).title}`);
      pin.title = pin.getAttribute("aria-label");
      pin.querySelector("img").src = `/assets/window-icons/${item.pinned ? "pin-off" : "pin"}.svg`;
      frame.querySelector("[data-board-move]").setAttribute("aria-disabled", String(item.pinned));
      const minimize = frame.querySelector("[data-board-minimize]");
      minimize.setAttribute("aria-label", `${item.minimized ? "Restore" : "Minimize"} ${nodes.get(id).title}`);
      minimize.title = minimize.getAttribute("aria-label");
      minimize.setAttribute("aria-expanded", String(!item.minimized));
      minimize.querySelector("img").src = `/assets/window-icons/${item.minimized ? "square" : "minus"}.svg`;
    };
    const raise = (id) => {
      const order = Object.keys(layout).sort((a, b) => layout[a].z - layout[b].z);
      order.filter(key => key !== id).concat(id).forEach((key, index) => {
        layout[key].z = index + 1;
        frames.get(key).style.zIndex = String(index + 1);
        frames.get(key).classList.toggle("is-active", key === id);
      });
    };
    const reveal = (id) => frames.get(id).scrollIntoView({ block: "nearest", inline: "nearest" });

    // A gallery preview is inert and has private SVG IDs, so it cannot become
    // a second game command target or steal a chart's clip-path reference.
    const preview = (id) => {
      const clone = nodes.get(id).card.cloneNode(true);
      const prefix = `gallery-${id}-`;
      const elements = [clone, ...clone.querySelectorAll("*")];
      const ids = new Map(elements.filter(node => node.id).map(node => [node.id, prefix + node.id]));
      for (const node of elements) {
        for (const attr of [...node.attributes]) {
          if (attr.name.startsWith("data-")) node.removeAttribute(attr.name);
          else if (attr.name === "id") node.id = ids.get(attr.value);
          else if (attr.value.includes("url(#")) {
            node.setAttribute(attr.name, attr.value.replace(/url\(#([^)]+)\)/g, (match, ref) => ids.has(ref) ? `url(#${ids.get(ref)})` : match));
          }
        }
        if (node.matches("button,input,select,textarea,a,[tabindex]")) node.setAttribute("tabindex", "-1");
      }
      clone.inert = true;
      clone.setAttribute("aria-hidden", "true");
      clone.classList.add("card-board-preview");
      const scale = Math.min(154 / layout[id].width, 88 / layout[id].height);
      clone.style.transform = `scale(${scale})`;
      return clone;
    };
    const refreshGallery = () => {
      galleryList.replaceChildren();
      for (const [id, { title }] of nodes) {
        const entry = document.createElement("section");
        entry.className = "card-board-gallery-entry";
        entry.dataset.boardGalleryCard = id;
        entry.innerHTML = `<div role="button" tabindex="0" class="card-board-thumbnail" data-board-gallery-drag="${id}" aria-label="${layout[id].visible ? "Show" : "Add"} ${title}" title="${layout[id].visible ? "Show" : "Add"} ${title}"><span class="card-board-thumb-frame${id === "offense" || id === "defense" ? " season-radars-stack" : ""}${nodes.get(id).assets ? " assets-desktop" : ""}${id.startsWith("trade-") ? " assets-trade-tools" : ""}"></span></div><footer><span>${title}</span><button type="button" class="card-board-control" data-board-add="${id}" aria-label="${layout[id].visible ? "Show" : "Add"} ${title}" title="${layout[id].visible ? "Show" : "Add"} ${title}">${icon(layout[id].visible ? "panels-top-left" : "plus")}</button></footer>`;
        entry.querySelector(".card-board-thumb-frame").append(preview(id));
        if (layout[id].visible) entry.classList.add("is-on-board");
        galleryList.append(entry);
      }
    };
    const showGallery = (open) => {
      galleryOpen = open;
      gallery.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      toggle.classList.toggle("is-open", open);
      if (open) { refreshGallery(); gallery.querySelector("[data-board-gallery-close]").focus(); }
      else toggle.focus({ preventScroll: true });
    };
    const add = (id) => {
      const item = layout[id];
      if (!item.visible) {
        const offset = Object.values(layout).filter(card => card.visible).length % 6 * 22;
        item.x = board.scrollLeft + 16 + offset;
        item.y = board.scrollTop + 16 + offset;
        item.visible = true;
        item.minimized = false;
      } else item.minimized = false;
      paint(id);
      raise(id);
      sizeCanvas();
      save();
      showGallery(false);
      reveal(id);
      frames.get(id).querySelector("[data-board-move]").focus({ preventScroll: true });
      announce(`${nodes.get(id).title} opened`);
    };

    dashboard.addEventListener("click", (event) => {
      const button = event.target.closest("button,[data-board-gallery-drag]");
      if (!button) return;
      if (button === toggle) showGallery(!galleryOpen);
      else if (button.matches("[data-board-gallery-close]")) showGallery(false);
      else if (button.dataset.boardAdd || button.dataset.boardGalleryDrag) add(button.dataset.boardAdd || button.dataset.boardGalleryDrag);
      else if (button.dataset.boardClose) {
        const id = button.dataset.boardClose;
        layout[id].visible = false;
        paint(id);
        sizeCanvas();
        save();
        if (galleryOpen) refreshGallery();
        toggle.focus({ preventScroll: true });
        announce(`${nodes.get(id).title} closed`);
      } else if (button.dataset.boardMinimize) {
        const id = button.dataset.boardMinimize;
        layout[id].minimized = !layout[id].minimized;
        paint(id);
        sizeCanvas();
        save();
        announce(`${nodes.get(id).title} ${layout[id].minimized ? "minimized" : "restored"}`);
      } else if (button.dataset.boardPin) {
        const id = button.dataset.boardPin;
        layout[id].pinned = !layout[id].pinned;
        paint(id);
        save();
        announce(`${nodes.get(id).title} ${layout[id].pinned ? "pinned" : "unpinned"}`);
      } else if (button.matches("[data-board-reset]")) {
        layout = structuredClone(defaults);
        for (const id of nodes.keys()) paint(id);
        sizeCanvas();
        board.scrollTo(0, 0);
        save();
        if (galleryOpen) refreshGallery();
        announce("Original card layout restored");
      }
    });

    dashboard.addEventListener("focusin", (event) => {
      const frame = event.target.closest("[data-board-window]");
      if (frame) { raise(frame.dataset.boardWindow); save(); }
    });
    const point = (event) => {
      const rect = board.getBoundingClientRect();
      return { x: event.clientX - rect.left + board.scrollLeft, y: event.clientY - rect.top + board.scrollTop };
    };
    const finishDrag = (cancel = false) => {
      if (!drag) return;
      const ended = drag;
      drag = null;
      if (cancel || !ended.started) layout[ended.id] = ended.original;
      paint(ended.id);
      frames.get(ended.id).classList.remove("is-dragging");
      ended.target.classList.remove("is-drag-source");
      if (ended.target.hasPointerCapture(ended.pointerId)) ended.target.releasePointerCapture(ended.pointerId);
      sizeCanvas();
      if (ended.started) {
        save();
        if (ended.gallery && !cancel) {
          showGallery(false);
          frames.get(ended.id).querySelector("[data-board-move]").focus({ preventScroll: true });
        } else if (galleryOpen) refreshGallery();
        announce(`${nodes.get(ended.id).title} ${cancel ? "move canceled" : "placed"}`);
      }
    };
    dashboard.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || !event.isPrimary) return;
      const frame = event.target.closest("[data-board-window]");
      if (frame) { raise(frame.dataset.boardWindow); save(); }
      const minimizedFrame = frame?.classList.contains("is-minimized") ? frame : null;
      if (minimizedFrame && event.target.closest("button:not([data-board-move])")) return;
      const handle = event.target.closest("[data-board-move], [data-board-gallery-drag]")
        || (minimizedFrame && event.target.closest(".card-board-titlebar") ? minimizedFrame.querySelector("[data-board-move]") : null);
      if (!handle || drag) return;
      const id = handle.dataset.boardMove || handle.dataset.boardGalleryDrag || minimizedFrame?.dataset.boardWindow;
      if (layout[id].pinned) return;
      const start = point(event);
      drag = { id, target: handle, pointerId: event.pointerId, gallery: Boolean(handle.dataset.boardGalleryDrag), start, clientX: event.clientX, clientY: event.clientY, original: { ...layout[id] }, started: false };
      handle.setPointerCapture(event.pointerId);
    });
    dashboard.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      if (!drag.started && Math.hypot(event.clientX - drag.clientX, event.clientY - drag.clientY) < 4) return;
      event.preventDefault();
      const item = layout[drag.id];
      if (!drag.started) {
        drag.started = true;
        item.visible = true;
        raise(drag.id);
        frames.get(drag.id).classList.add("is-dragging");
        drag.target.classList.add("is-drag-source");
      }
      const rect = board.getBoundingClientRect();
      if (event.clientY < rect.top + 28) board.scrollTop = Math.max(0, board.scrollTop - 12);
      else if (event.clientY > rect.bottom - 28) board.scrollTop += 12;
      if (event.clientX < rect.left + 28) board.scrollLeft = Math.max(0, board.scrollLeft - 12);
      else if (event.clientX > rect.right - 28) board.scrollLeft += 12;
      const current = point(event);
      item.x = bounded(drag.gallery ? current.x - Math.min(80, item.width / 2) : drag.original.x + current.x - drag.start.x, 0, LIMIT);
      item.y = bounded(drag.gallery ? current.y - TITLE_HEIGHT / 2 : drag.original.y + current.y - drag.start.y, 0, LIMIT);
      paint(drag.id);
      sizeCanvas();
    });
    dashboard.addEventListener("pointerup", (event) => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      const rect = board.getBoundingClientRect();
      const galleryRect = gallery.getBoundingClientRect();
      const onGallery = galleryOpen && event.clientX >= galleryRect.left && event.clientX <= galleryRect.right && event.clientY >= galleryRect.top && event.clientY <= galleryRect.bottom;
      const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
      if (drag.started) {
        // Suppress only the synthetic click after a drag; ordinary thumbnail
        // clicks and all business controls retain their original behavior.
        drag.target.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); }, { once: true });
      }
      finishDrag(Boolean(drag.gallery && (onGallery || outside)));
    });
    dashboard.addEventListener("pointercancel", () => finishDrag(true));
    dashboard.addEventListener("lostpointercapture", () => finishDrag(true));
    dashboard.addEventListener("keydown", (event) => {
      const thumbnail = event.target.closest("[data-board-gallery-drag]");
      if (thumbnail && ["Enter", " "].includes(event.key)) { event.preventDefault(); add(thumbnail.dataset.boardGalleryDrag); return; }
      if (event.key === "Escape" && drag) { event.preventDefault(); finishDrag(true); return; }
      if (event.key === "Escape" && galleryOpen) { event.preventDefault(); event.stopPropagation(); showGallery(false); return; }
      const handle = event.target.closest("[data-board-move]");
      if (!handle || layout[handle.dataset.boardMove].pinned) return;
      const directions = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      const direction = directions[event.key];
      if (!direction) return;
      event.preventDefault();
      event.stopPropagation();
      const id = handle.dataset.boardMove;
      const step = event.shiftKey ? 40 : 10;
      layout[id].x = bounded(layout[id].x + direction[0] * step, 0, LIMIT);
      layout[id].y = bounded(layout[id].y + direction[1] * step, 0, LIMIT);
      paint(id);
      raise(id);
      sizeCanvas();
      reveal(id);
      save();
    });

    for (const id of nodes.keys()) paint(id);
    const front = Object.keys(layout).filter(id => layout[id].visible).sort((a, b) => layout[b].z - layout[a].z)[0];
    if (front) raise(front);
    sizeCanvas();
    const observer = new ResizeObserver(sizeCanvas);
    observer.observe(board);
    save();
    active = { dispose: () => { finishDrag(true); observer.disconnect(); } };
    active.open = (id) => { if (layout[id]) add(id); };
  }

  window.CardBoard = Object.freeze({ mount, unmount, open: (id) => active?.open(id), defaultLayout, restoreLayout });
})();
