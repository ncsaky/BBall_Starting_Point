/* Pages layout (branch sidebar-pages, 2026-11-24).

   The free-floating card board becomes an app: a sidebar of pages on the left, one page at a time filling the rest of the
   screen. Every card the board used to float is "dissolved" onto a page: the same card element, the same size and
   contents, just without its window frame, under a plain section title. A page is rows and columns of cards at their own
   sizes; the whole page scales as one piece to fit the screen, so nothing is ever stretched and the text size matches
   across the cards on a page. List-like cards (the prospect board, the calendar, the league wire feed) may grow into spare
   height or width: they show more rows, never bigger ones.

   Fixed places for controls: the sidebar holds the team, the date and phase, Player Finder, the pages and Settings; a
   page's own controls sit at the right of its title; the one obvious next step (Sim / the phase's button) is always at the
   bottom right, beside the league wire ticker.

   card-board.js still builds every window frame and keeps the pop-ups (player cards, extension cards) as windows; this
   module only takes the frames of the cards that belong on pages. Pop-ups that are modals (box scores, the trade room,
   Settings, Player Finder) are untouched. */
(() => {
  "use strict";

  const MODE_KEY = "nbaGmLayoutMode";
  const PAGE_KEY = "nbaGmPage:v1";
  const GAP = 28;            // design pixels between cards
  const MAX_SCALE = 1.22;    // a sparse page may grow this much
  const MIN_SCALE = .7;      // below this the page scrolls instead of shrinking further
  const lastPage = new Map();

  const root = () => (typeof document !== "undefined" ? document.documentElement : null);
  const enabled = () => {
    const html = root();
    let mode = html?.dataset.layout;
    if (!mode) {
      try { mode = localStorage.getItem(MODE_KEY) || "pages"; } catch { mode = "pages"; }
      if (html) html.dataset.layout = mode;
    }
    return mode !== "board";
  };
  const setMode = (mode) => {
    const value = mode === "board" ? "board" : "pages";
    const html = root();
    if (html) html.dataset.layout = value;
    try { localStorage.setItem(MODE_KEY, value); } catch { /* preference only */ }
  };

  // ---- Page definitions. Strings are card ids; row() lays cards side by side, col() stacks them. card() options:
  //   expanded  show the card's expanded form (the board's + button) on this page
  //   grow      "h" | "w" | "both": the card takes spare height / width (lists only; text never scales up for it)
  //   link      page id: the section title becomes a link to that page (a summary card on Home)
  //   bare      no section title (the page title already names it)
  //   quiet     the title's space is kept (columns stay level) but its words hidden (the card carries its own title)
  const row = (...items) => ({type: "row", items});
  const col = (...items) => ({type: "col", items});
  const card = (id, options = {}) => ({type: "card", id, ...options});

  const GROUPS = [
    ["now", ""],
    ["team", "Team"],
    ["office", "Front Office"],
    ["league", "League"],
  ];

  const PAGES = [
    // Decisions and phase rooms come first while they are open.
    {id: "staff-retention", group: "now", label: "Staff Retention", layout: () => row(card("phase-staff_retention-decision", {bare: true}))},
    {id: "roster-moves", group: "now", label: () => rosterMovesLabel(), layout: () => row(card("phase-cutdown-decision", {bare: true}))},
    {id: "set-roster", group: "now", label: "Set The Roster", layout: () => row(card("phase-set_roster-checklist", {bare: true}))},
    {id: "outlook", group: "now", label: "Preseason Outlook", slideshow: "outlook"},
    {id: "recap", group: "now", label: "Year-End Recap", slideshow: "recap"},
    // The bracket gets a page of its own (it is as wide as the screen); the playoff stats and injuries sit together.
    {id: "playoffs", group: "now", label: "Playoffs", layout: () => row(card("phase-playoffs-bracket", {bare: true, width: 1100}))},
    {id: "playoff-stats", group: "now", label: "Playoff Stats", layout: () => row("phase-playoffs-leaders", "phase-playoffs-injuries")},
    {id: "draft-room", group: "now", label: "Draft", layout: draftRoomLayout},
    {id: "free-agency-checklist", group: "now", label: "Offseason Checklist", layout: () => row(card("phase-free_agency-checklist", {grow: "h"}), card("phase-free_agency-selected", {grow: "h"}))},
    {id: "free-agency", group: "now", label: "Free Agency", layout: () => row(card("phase-free_agency-market", {grow: "h"}), card("phase-free_agency-selected", {grow: "h"}), card("phase-free_agency-wire", {grow: "h"}))},
    {id: "fantasy-draft", group: "now", label: "Fantasy Draft", layout: () => col("phase-fantasy_draft-control", row(card("phase-fantasy_draft-board", {grow: "h"}), card("phase-fantasy_draft-roster", {grow: "h"}), card("phase-fantasy_draft-ticker", {grow: "h"})))},

    // The team.
    {id: "home", group: "team", label: "Home", layout: () => row(
      col("minutes", card("week", {link: "schedule"}), row(card("signals", {link: "identity"}), "morale")),
      col("opponent", card("standings", {link: "standings"})))},
    {id: "roster", group: "team", label: "Roster", layout: () => col(card("roster", {title: "Ratings"}), "stats")},
    {id: "development", group: "team", label: "Development", layout: () => row(card("development", {expanded: true}), card("staff", {expanded: true}))},
    {id: "identity", group: "team", label: "Team Identity", layout: () => row(
      col(card("identity", {title: "Heat Maps"}), "signals", "morale"),
      col(row("offense", "defense"), row("factors", "efficiency")))},

    {id: "schedule", group: "team", label: "Schedule", layout: () => row(card("week", {expanded: true, grow: "both", bare: true, minHeight: 480}))},

    // The front office.
    {id: "contracts", group: "office", label: "Contracts", title: "Contracts & Payroll", layout: () => row(col("contracts", "picks"), "payroll")},
    {id: "trades", group: "office", label: "Trades", controls: "trades", layout: () => col(row("league-block", "payroll"), row("team-block", "team-wants"))},
    {id: "scouting", group: "office", label: "Scouting", layout: () => col(card("prospects", {expanded: true, grow: "h", minHeight: 400}), "picks")},

    // The league.
    {id: "standings", group: "league", label: "Standings", layout: () => row(card("standings", {expanded: true}), card("league-wire", {expanded: true, height: 600}))},
    {id: "awards", group: "league", label: "Awards", controls: "awards", layout: () => row("award-mvp", "award-dpoy", "award-roty")},

  ];

  function draftRoomLayout(ctx) {
    const has = (id) => ctx.available(id);
    if (has("phase-draft-lottery")) return row(card("phase-draft-lottery", {bare: true}));
    if (has("phase-draft-summary")) return row(card("phase-draft-summary", {grow: "h", quiet: true}), card("phase-draft-trades", {grow: "h", quiet: true}));
    return row(card("phase-draft-board", {grow: "h"}), card("phase-draft-order", {grow: "h", quiet: true}));
  }

  function rosterMovesLabel() {
    const save = appState()?.home?.save;
    const phase = String(save?.phase || "");
    const pending = save?.pending_counts || {};
    if (Number(pending.cutdowns || 0) > 0) return "Roster Cutdown";
    if (Number(pending.roster_minimum || 0) > 0) return "Sign Players";
    return phase === "regular_season" ? "Two-Way Places" : "Opening Roster";
  }

  const layoutIds = (node, out = []) => {
    if (!node) return out;
    if (node.type === "card") out.push(node.id);
    else (node.items || []).forEach(item => layoutIds(typeof item === "string" ? card(item) : item, out));
    return out;
  };
  // Every id any page can show (whatever the phase): these frames belong to the pages, not the board.
  const PAGE_CARD_IDS = new Set(["league-wire", "picks", "phase-draft-lottery", "phase-draft-summary", "phase-draft-trades", "phase-draft-board", "phase-draft-order"]);
  for (const page of PAGES) if (page.layout) layoutIds(page.layout({available: () => false}), []).forEach(id => PAGE_CARD_IDS.add(id));

  // app.js keeps its state in a top-level binding (not a window property).
  const appState = () => (typeof state !== "undefined" ? state : null);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

  function attach(ctx) {
    const {dashboard, board, toolbar, nodes, frames, layout, options} = ctx;
    const saveKey = String(options.save || "preview");
    const owned = new Set([...nodes.keys()].filter(id => PAGE_CARD_IDS.has(id)));
    const expandedNow = new Map();
    const shownCards = new Set();
    let currentPage = null;
    let previewReturn = null;
    let offerCount = Number(options.toolbarActions?.offerCount || 0);
    let resizeFrame = 0;
    let disposed = false;

    const node = (id) => nodes.get(id);
    const isLocked = (id) => Boolean(ctx.locked(id));
    const rosterViewOpen = () => typeof preseasonRosterViewOpen === "function" && preseasonRosterViewOpen();
    const available = (id) => {
      const entry = node(id);
      if (!entry) return false;
      if (id === "phase-cutdown-decision") return Boolean(entry.required) || entry.galleryVisible !== false || rosterViewOpen();
      return entry.galleryVisible !== false;
    };
    const slideshowRow = (kind) => (typeof seasonSlideshowsAvailable === "function" ? seasonSlideshowsAvailable() : []).find(row => row.kind === kind);
    const pageCtx = {available};
    const pageLayout = (page) => page.layout ? normalize(page.layout(pageCtx)) : null;
    const normalize = (item) => typeof item === "string" ? card(item) : item.type === "card" ? item : {...item, items: item.items.map(normalize)};
    // A page is listed when one of its cards is there to show (phase rooms appear and disappear with their phase).
    const SLIDESHOW_PHASES = {
      outlook: ["preseason", "regular_season", "play_in", "playoffs"],
      recap: ["playoffs", "draft_lottery", "draft", "re_signing", "free_agency", "offseason", "training_camp"],
    };
    const pageAvailable = (page) => {
      if (page.slideshow) {
        const phase = String(appState()?.home?.save?.phase || "");
        return Boolean(slideshowRow(page.slideshow)) && (!phase || SLIDESHOW_PHASES[page.slideshow].includes(phase));
      }
      const ids = layoutIds(pageLayout(page));
      return ids.some(available);
    };
    const pageLabel = (page) => typeof page.label === "function" ? page.label() : page.label;

    // ---- The sidebar: the old top bar turned on its side (its buttons keep their wiring).
    const header = dashboard.querySelector(".season-command-header");
    header.classList.add("pages-sidebar");
    const club = header.querySelector(".season-command-club");
    const actions = header.querySelector(".season-command-actions");
    const finder = actions?.querySelector("[data-dashboard-player-finder]");
    const settings = actions?.querySelector("[data-dashboard-settings]");
    const deadline = actions?.querySelector("[data-trade-deadline-open]");
    const nav = document.createElement("nav");
    nav.className = "pages-nav";
    nav.setAttribute("aria-label", "Pages");
    if (finder) {
      finder.classList.add("pages-finder");
      finder.innerHTML = `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10.4 10.4 14 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg><span>Find a player</span>`;
      club.after(finder);
    }
    (finder || club).after(nav);
    if (settings) {
      settings.classList.add("pages-settings");
      settings.innerHTML = `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 5.6a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 0 0 0-4.8Zm5.6 3.3-.1-1.8 1.3-1-1.3-2.3-1.6.5-1.5-.9L10 1.8H7.4L6.9 3.4l-1.5.9-1.6-.5L2.5 6.1l1.3 1-.1 1.8-1.2 1 1.3 2.3 1.6-.5 1.5.9.5 1.6H10l.4-1.6 1.5-.9 1.6.5 1.3-2.3Z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg><span>Settings</span>`;
    }

    // ---- The page area: a title row with the page's own controls, the pages, and the footer (ticker + next step).
    const shell = document.createElement("section");
    shell.className = "pages-shell";
    shell.innerHTML = `<div class="pages-sheet">
        <header class="pages-head"><h1 class="pages-title"></h1><div class="pages-controls"></div></header>
        <div class="pages-viewport"></div>
        <footer class="pages-foot"><div class="pages-ticker"></div></footer>
      </div>
      <div class="pages-holding" hidden></div>`;
    header.after(shell);
    const titleEl = shell.querySelector(".pages-title");
    const controlsEl = shell.querySelector(".pages-controls");
    const viewport = shell.querySelector(".pages-viewport");
    const foot = shell.querySelector(".pages-foot");
    const ticker = shell.querySelector(".pages-ticker");
    const holding = shell.querySelector(".pages-holding");
    dashboard.classList.add("is-pages");

    // ---- The next step, always at the bottom right: the board's own tool bar, cut down to Sim (or the phase's
    // buttons). The gallery, window switcher, layouts and snap belong to the board only.
    for (const selector of [".card-board-gallery-toggle", "[data-window-switcher-open]", ".card-board-layout-control", "[data-board-snap]", "[data-trade-menu]"]) toolbar.querySelector(selector)?.remove();
    toolbar.classList.add("pages-dock");
    const simControl = toolbar.querySelector("[data-sim-menu]");
    if (simControl) {
      const postseason = String(options.phaseContext).includes(":postseason-v2:");
      const disabled = options.toolbarActions?.simulationDisabled ? " disabled" : "";
      const primary = document.createElement("button");
      primary.type = "button";
      primary.className = "pages-next is-primary";
      primary.dataset.advance = "next-event";
      if (disabled) primary.disabled = true;
      primary.innerHTML = `<span>${postseason ? "Sim One Game Per Series" : "Sim To Next Event"}</span>`;
      simControl.before(primary);
      const trigger = simControl.querySelector("[data-sim-menu-trigger]");
      if (trigger) {
        trigger.classList.add("pages-next-more");
        trigger.setAttribute("aria-label", "More ways to sim");
        trigger.title = "More ways to sim";
        trigger.innerHTML = `<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 7.5 6 4.5 9 7.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      }
    }
    const phaseActions = toolbar.querySelector(".card-board-phase-actions");
    phaseActions?.querySelector("button")?.classList.add("is-primary");
    if (deadline) toolbar.prepend(deadline);
    foot.append(toolbar);

    // ---- Pages.
    const pageEls = new Map();
    const slotsByPage = new Map();
    const visiblePages = () => PAGES.filter(pageAvailable);

    function buildNode(item, parent, page) {
      if (item.type === "card") {
        if (!available(item.id)) return null;
        const entry = node(item.id);
        const slot = document.createElement("section");
        slot.className = "pages-slot";
        slot.dataset.pagesSlot = item.id;
        const bare = item.bare || (layoutIds(pageLayout(page)).filter(available).length === 1);
        if (!bare) {
          const head = document.createElement("header");
          head.className = "pages-slot-head";
          const title = esc(item.title || entry.title || item.id);
          // A section named like its page keeps its place (the columns stay level) but not the repeated words.
          if (item.quiet || (item.title || entry.title || "") === (page.title || pageLabel(page))) head.classList.add("is-echo");
          head.innerHTML = item.link
            ? `<button type="button" class="pages-slot-link" data-pages-go="${esc(item.link)}">${title}<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>`
            : `<h2>${title}</h2>`;
          slot.append(head);
        }
        const body = document.createElement("div");
        body.className = "pages-slot-body";
        slot.append(body);
        slot.dataset.grow = item.grow || "";
        slot.pagesItem = item;
        parent.append(slot);
        slotsByPage.get(page.id).push(slot);
        return {grow: item.grow || ""};
      }
      const box = document.createElement("div");
      box.className = item.type === "row" ? "pages-row" : "pages-col";
      let growH = false, growW = false;
      for (const child of item.items) {
        const result = buildNode(child, box, page);
        if (!result) continue;
        if (/h|both/.test(result.grow)) growH = true;
        if (/w|both/.test(result.grow)) growW = true;
      }
      if (!box.childElementCount) return null;
      const grow = growH && growW ? "both" : growH ? "h" : growW ? "w" : "";
      box.dataset.grow = grow;
      parent.append(box);
      return {grow};
    }

    function buildPages() {
      viewport.replaceChildren();
      pageEls.clear();
      slotsByPage.clear();
      for (const page of visiblePages()) {
        const el = document.createElement("div");
        el.className = "pages-page";
        el.dataset.pagesPage = page.id;
        el.hidden = true;
        if (!page.slideshow) {
          const stage = document.createElement("div");
          stage.className = "pages-stage";
          el.append(stage);
          slotsByPage.set(page.id, []);
          const result = buildNode(pageLayout(page), stage, page);
          el.dataset.grow = result?.grow || "";
        } else {
          el.classList.add("is-slideshow");
          slotsByPage.set(page.id, []);
        }
        viewport.append(el);
        pageEls.set(page.id, el);
      }
      // Every owned frame lives somewhere in the page area (refreshes find cards by their window id); a card not on any
      // listed page waits in a hidden holding area.
      for (const id of owned) {
        const frame = frames.get(id);
        frame.classList.add("is-page-card");
        const home = id === "league-wire" ? null : firstSlot(id);
        (home ? home.querySelector(".pages-slot-body") : holding).append(frame);
      }
      if (owned.has("league-wire")) placeTicker();
      renderNav();
    }

    const firstSlot = (id) => {
      for (const slots of slotsByPage.values()) for (const slot of slots) if (slot.dataset.pagesSlot === id) return slot;
      return null;
    };
    const slotOn = (pageId, id) => (slotsByPage.get(pageId) || []).find(slot => slot.dataset.pagesSlot === id) || null;

    // ---- Sizes. A card's natural size is the board's default window size (its expanded size where the page asks).
    function naturalSize(id, expanded) {
      const item = ctx.defaults[id] || layout[id];
      if (!item) return {width: 320, height: 240};
      // The board opens its starter windows (Calendar, Standings...) at least this wide; so does a page.
      const base = {width: Math.max(item.width, ctx.starterMinWidths?.[id] || 0), height: item.height, scale: 1, expanded: false};
      if (expanded && ctx.EXPANDABLE_CARDS.has(id)) {
        const copy = structuredClone(base);
        ctx.toggleWindowExpansion(copy, id);
        return {width: copy.width, height: copy.height};
      }
      return {width: base.width, height: base.height};
    }

    function sizeFrame(id, width, height) {
      const frame = frames.get(id), entry = node(id);
      if (!frame || !entry) return;
      const w = Math.round(width), h = Math.round(height);
      Object.assign(frame.style, {width: `${w}px`, height: `${h}px`, left: "", top: "", zIndex: ""});
      const body = frame.querySelector(".card-board-body");
      Object.assign(body.style, {left: "0px", top: "0px", width: `${w}px`, height: `${h}px`, transform: "none"});
      Object.assign(entry.card.style, {width: `${w}px`, height: `${h}px`});
      if (id === "staff") entry.card.style.setProperty("--staff-compact-height", `${naturalSize("staff", false).height}px`);
    }

    // Cards whose height follows their contents (the board fits these too): Player Development ends at its last row.
    const FIT_HEIGHT = new Set(["development", "team-wants"]);
    function contentHeight(id) {
      const panel = node(id)?.card;
      if (!panel || !panel.isConnected) return 0;
      const before = panel.style.height;
      panel.style.height = "auto";
      const height = panel.offsetHeight;
      panel.style.height = before;
      return height;
    }

    function setExpanded(id, expanded) {
      if (!ctx.EXPANDABLE_CARDS.has(id)) return;
      if ((expandedNow.get(id) || false) === expanded) return;
      expandedNow.set(id, expanded);
      options.onExpandedChange?.(id, expanded, node(id).card);
    }

    function placeTicker() {
      const frame = frames.get("league-wire");
      if (!frame) return;
      if (currentPage && slotOn(currentPage, "league-wire")) return;
      setExpanded("league-wire", false);
      ticker.append(frame);
      ticker.hidden = false;
      const width = Math.max(200, ticker.clientWidth || 600);
      sizeFrame("league-wire", width, 31);
    }

    // Lay the current page out: natural sizes first, one scale for the whole page, then growing cards fill.
    function layoutPage() {
      if (!currentPage) return;
      const el = pageEls.get(currentPage);
      const stage = el?.querySelector(".pages-stage");
      if (!stage) return;
      const slots = slotsByPage.get(currentPage) || [];
      el.classList.remove("is-growing", "is-scrolling");
      stage.style.transform = "none";
      stage.style.width = stage.style.height = "";
      for (const slot of slots) {
        const id = slot.dataset.pagesSlot, item = slot.pagesItem, size = naturalSize(id, Boolean(item.expanded));
        if (item.height) size.height = item.height;
        if (item.width) size.width = item.width;
        if (item.minHeight) size.height = Math.min(size.height, item.minHeight);
        if (item.minWidth) size.width = Math.min(size.width, item.minWidth);
        sizeFrame(id, size.width, size.height);
        if (FIT_HEIGHT.has(id)) {
          const fitted = contentHeight(id);
          if (fitted > 60) { size.height = fitted; sizeFrame(id, size.width, fitted); }
        }
        const body = slot.querySelector(".pages-slot-body");
        body.style.minWidth = `${size.width}px`;
        body.style.minHeight = `${size.height}px`;
      }
      const naturalWidth = stage.offsetWidth, naturalHeight = stage.offsetHeight;
      const style = getComputedStyle(viewport);
      const availableWidth = Math.max(200, viewport.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight));
      const availableHeight = Math.max(200, viewport.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom));
      const grows = el.dataset.grow || "";
      const fit = Math.min(availableWidth / Math.max(1, naturalWidth), availableHeight / Math.max(1, naturalHeight));
      // Growing pages never enlarge their text to fill: they show more instead.
      const scale = Math.max(MIN_SCALE, Math.min(grows ? 1 : MAX_SCALE, fit));
      if (grows) {
        el.classList.add("is-growing");
        stage.style.width = `${/w|both/.test(grows) ? Math.max(naturalWidth, availableWidth / scale) : naturalWidth}px`;
        stage.style.height = `${/h|both/.test(grows) ? Math.max(naturalHeight, availableHeight / scale) : naturalHeight}px`;
        for (const slot of slots) {
          if (!slot.dataset.grow) continue;
          const body = slot.querySelector(".pages-slot-body");
          sizeFrame(slot.dataset.pagesSlot, body.clientWidth, body.clientHeight);
        }
      }
      const width = stage.offsetWidth * scale, height = stage.offsetHeight * scale;
      stage.style.transform = `scale(${scale})`;
      el.style.setProperty("--pages-scale", String(scale));
      const holder = el;
      holder.style.width = `${Math.ceil(width)}px`;
      holder.style.height = `${Math.ceil(height)}px`;
      el.classList.toggle("is-scrolling", height > availableHeight + 2 || width > availableWidth + 2);
      dashboard.style.setProperty("--pages-scale", String(scale));
    }

    function renderNav() {
      const pages = visiblePages();
      const groups = GROUPS.map(([group, label]) => {
        const items = pages.filter(page => page.group === group);
        if (!items.length) return "";
        const heading = group === "now" ? nowHeading() : label;
        return `<section class="pages-nav-group" data-pages-group="${group}">${heading ? `<h3>${esc(heading)}</h3>` : ""}${items.map(page => {
          const badge = badgeFor(page);
          const current = shownPageId() === page.id;
          return `<button type="button" class="pages-nav-item${current ? " is-current" : ""}" data-pages-go="${page.id}"${current ? ' aria-current="page"' : ""}><span>${esc(pageLabel(page))}</span>${badge}</button>`;
        }).join("")}</section>`;
      }).join("");
      nav.innerHTML = groups;
    }

    // The page the sidebar marks: an open slideshow counts as its page (it can open by itself at the start of a season).
    function shownPageId() {
      const show = window.SeasonSlideshow?.isOpen?.() ? window.SeasonSlideshow.current?.() : null;
      if (show) {
        const page = PAGES.find(item => item.slideshow === show.kind);
        if (page && pageEls.has(page.id)) return page.id;
      }
      return currentPage;
    }

    function nowHeading() {
      const phase = String(appState()?.home?.save?.phase || "");
      return ({preseason: "Preseason", regular_season: "This Season", play_in: "Postseason", playoffs: "Postseason", draft_lottery: "Draft", draft: "Draft", re_signing: "Offseason", free_agency: "Offseason", offseason: "Offseason", training_camp: "Offseason", fantasy_draft: "Fantasy Draft"})[phase] || "Now";
    }

    function badgeFor(page) {
      if (page.id === "trades" && offerCount) return `<em class="pages-nav-badge" title="${offerCount} incoming offer${offerCount === 1 ? "" : "s"}">${offerCount}</em>`;
      const required = layoutIds(pageLayout(page)).some(id => node(id)?.required && available(id));
      if (required) return `<em class="pages-nav-badge is-alert" title="A decision is required">!</em>`;
      if (page.id === "set-roster") {
        const waiting = (appState()?.data?.setRoster?.items || []).filter(item => item.status === "pending").length;
        if (waiting) return `<em class="pages-nav-badge" title="${waiting} decision${waiting === 1 ? "" : "s"} waiting">${waiting}</em>`;
      }
      return "";
    }

    function renderControls(page) {
      controlsEl.replaceChildren();
      if (page?.controls === "awards" && typeof openLeagueLeadersModal === "function") {
        controlsEl.innerHTML = `<button type="button" class="pages-control" data-pages-leaders>League Leaders</button>`;
      }
      if (page?.controls === "trades") {
        const disabled = options.toolbarActions?.tradeDisabled ? " disabled" : "";
        controlsEl.innerHTML = `<button type="button" class="pages-control" data-pages-trade="finder"${disabled}>Trade Finder</button><button type="button" class="pages-control" data-pages-trade="builder"${disabled}>Trade Builder</button><button type="button" class="pages-control" data-pages-trade="offers"${disabled}>Incoming Offers${offerCount ? ` <em class="pages-nav-badge">${offerCount}</em>` : ""}</button><button type="button" class="pages-control" data-pages-trade="market"${disabled}>Trade Market</button>`;
      }
    }

    function showPage(pageId, {focus = false, fromNav = false} = {}) {
      const page = PAGES.find(item => item.id === pageId);
      if (!page || !pageEls.has(pageId)) return false;
      if (page.slideshow) {
        openSlideshow(page);
        return true;
      }
      closeSlideshowFor();
      const previous = currentPage;
      currentPage = pageId;
      // While a save is still loading only Home exists: don't let that overwrite the page you were on.
      if (options.phaseContext != null) {
        lastPage.set(saveKey, pageId);
        try { localStorage.setItem(`${PAGE_KEY}:${saveKey}`, pageId); } catch { /* preference only */ }
      }
      for (const [id, el] of pageEls) el.hidden = id !== pageId;
      titleEl.textContent = page.title || pageLabel(page);
      renderControls(page);
      // Move the page's cards in (a card can sit on more than one page), in the form this page wants.
      const slots = slotsByPage.get(pageId) || [];
      for (const slot of slots) {
        const id = slot.dataset.pagesSlot;
        setExpanded(id, Boolean(slot.pagesItem.expanded));
        slot.querySelector(".pages-slot-body").append(frames.get(id));
        paint(id);
      }
      if (owned.has("league-wire") && !slotOn(pageId, "league-wire")) placeTicker();
      foot.classList.toggle("has-ticker", owned.has("league-wire") && !slotOn(pageId, "league-wire"));
      layoutPage();
      // Cards that load on opening (Stats, Contracts, the opening roster) load now.
      const opened = new Set(slots.map(slot => slot.dataset.pagesSlot));
      if (foot.classList.contains("has-ticker")) opened.add("league-wire");
      for (const id of opened) {
        if (!shownCards.has(id) || previous !== pageId) options.onOpen?.(id, node(id).card);
        shownCards.add(id);
      }
      renderNav();
      if (fromNav) viewport.scrollTo?.(0, 0);
      if (focus) titleEl.focus?.({preventScroll: true});
      return true;
    }

    // The slideshow fills the page area; the sidebar stays live so another page closes it.
    let slideshowReturn = null;
    function openSlideshow(page) {
      if (typeof openLatestSeasonSlideshow !== "function") return;
      slideshowReturn = currentPage;
      nav.querySelectorAll(".pages-nav-item").forEach(item => item.classList.toggle("is-current", item.dataset.pagesGo === page.id));
      openLatestSeasonSlideshow(page.slideshow);
    }
    // Opening by itself or from Settings: the sidebar follows the slideshow's open state.
    const slideshowRoot = document.getElementById("seasonSlideshow");
    const slideshowWatch = slideshowRoot ? new MutationObserver(() => { if (!disposed) renderNav(); }) : null;
    slideshowWatch?.observe(slideshowRoot, {attributes: true, attributeFilter: ["hidden"]});
    function closeSlideshowFor() {
      if (window.SeasonSlideshow?.isOpen?.()) window.SeasonSlideshow.close();
    }
    const onSlideshowClosed = () => { if (!disposed) renderNav(); };
    window.addEventListener("season-slideshow-closed", onSlideshowClosed);

    function pageFor(id, {expanded = false} = {}) {
      const pages = visiblePages().filter(page => slotOn(page.id, id));
      if (!pages.length) return null;
      if (currentPage && pages.some(page => page.id === currentPage) && !expanded) return currentPage;
      const wantsExpanded = pages.find(page => (slotOn(page.id, id)?.pagesItem.expanded));
      return (expanded && wantsExpanded ? wantsExpanded : pages[0]).id;
    }

    function show(id, opts = {}) {
      const pageId = pageFor(id, opts);
      if (!pageId) return false;
      const changed = pageId !== currentPage;
      showPage(pageId);
      const slot = slotOn(pageId, id);
      if (slot && (changed || opts.expanded)) {
        slot.classList.remove("is-flash");
        void slot.offsetWidth;
        slot.classList.add("is-flash");
        slot.scrollIntoView?.({block: "nearest", inline: "nearest"});
      }
      return true;
    }

    function paint(id) {
      const frame = frames.get(id), entry = node(id);
      if (!frame || !entry) return;
      frame.hidden = false;
      const lockedNow = isLocked(id);
      frame.classList.toggle("is-phase-locked", lockedNow);
      frame.classList.remove("is-minimized");
      entry.card.inert = lockedNow;
      if (lockedNow) entry.card.querySelectorAll("button, input, select, textarea").forEach(control => control.disabled = true);
      const slot = frame.closest(".pages-slot");
      slot?.classList.toggle("is-locked", lockedNow);
    }

    // ---- Wiring.
    const onClick = (event) => {
      const go = event.target.closest("[data-pages-go]");
      if (go && dashboard.contains(go)) {
        event.preventDefault();
        showPage(go.dataset.pagesGo, {fromNav: true});
        return;
      }
      if (event.target.closest("[data-pages-leaders]") && typeof openLeagueLeadersModal === "function") {
        Promise.resolve(openLeagueLeadersModal()).catch(error => typeof showToast === "function" && showToast(error.message || String(error), true));
        return;
      }
      const trade = event.target.closest("[data-pages-trade]");
      if (trade && !trade.disabled) {
        const action = trade.dataset.pagesTrade;
        if (action === "offers" && typeof openTradeOffersModal === "function") openTradeOffersModal();
        else if (action === "market" && typeof openTradeMarketBoard === "function") openTradeMarketBoard();
        else options.onTradeMenuAction?.(action);
      }
    };
    dashboard.addEventListener("click", onClick);
    // The sidebar stays usable while the slideshow fills the page area.
    const onSlideshowNav = (event) => {
      if (!window.SeasonSlideshow?.isOpen?.()) return;
      const go = event.target.closest?.("[data-pages-go]");
      if (!go || !dashboard.contains(go)) return;
      event.preventDefault();
      event.stopPropagation();
      window.SeasonSlideshow.close();
      showPage(go.dataset.pagesGo, {fromNav: true});
    };
    document.addEventListener("click", onSlideshowNav, true);
    const onKey = (event) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
      if (document.querySelector("#modalRoot [role=dialog]") || window.SeasonSlideshow?.isOpen?.()) return;
      if (event.target.closest?.("input, textarea, select, [contenteditable]")) return;
      // [ and ] step through the pages in sidebar order.
      if (event.key !== "[" && event.key !== "]") return;
      const pages = visiblePages().filter(page => !page.slideshow);
      const index = pages.findIndex(page => page.id === currentPage);
      const next = pages[(index + (event.key === "]" ? 1 : -1) + pages.length) % pages.length];
      if (next) { event.preventDefault(); showPage(next.id, {fromNav: true}); }
    };
    document.addEventListener("keydown", onKey);
    // The Assistant GM's phone keeps clear of the next-step button, however wide the phase's buttons are.
    const dockObserver = new ResizeObserver(() => document.documentElement.style.setProperty("--pages-dock-w", `${Math.ceil(toolbar.offsetWidth || 0)}px`));
    dockObserver.observe(toolbar);
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        if (disposed) return;
        layoutPage();
        if (foot.classList.contains("has-ticker")) sizeFrame("league-wire", Math.max(200, ticker.clientWidth || 600), 31);
      });
    });
    observer.observe(viewport);

    buildPages();

    // ---- Which page opens: a required decision first, then the room of a phase just entered, then the page you were on.
    function landingPage() {
      const required = [...nodes].find(([id, entry]) => entry.required && owned.has(id) && available(id));
      if (required) return pageFor(required[0]);
      if (ctx.entering && ctx.phaseCards.length) {
        const entryFirst = (options.entryLayout?.rows || []).flat().filter(id => owned.has(id) && available(id));
        const phasePage = [...entryFirst, ...ctx.phaseCards].map(id => owned.has(id) && available(id) ? pageFor(id) : null).find(Boolean);
        if (phasePage && phasePage !== "roster-moves" && phasePage !== "set-roster") return phasePage;
      }
      let remembered = lastPage.get(saveKey);
      if (!remembered) { try { remembered = localStorage.getItem(`${PAGE_KEY}:${saveKey}`); } catch { remembered = null; } }
      const listed = visiblePages().filter(page => !page.slideshow);
      if (remembered && listed.some(page => page.id === remembered)) return remembered;
      const phaseRoom = listed.find(page => page.group === "now" && !["roster-moves", "set-roster"].includes(page.id));
      return phaseRoom?.id || "home";
    }

    const api = {
      owns: (id) => owned.has(id),
      paint,
      show,
      showPage,
      isShown: (id) => Boolean(currentPage && slotOn(currentPage, id)) || (id === "league-wire" && foot.classList.contains("has-ticker")),
      fitContent: (id) => { if (currentPage && slotOn(currentPage, id)) layoutPage(); },
      updateOfferCount(count) {
        offerCount = count;
        renderNav();
        if (currentPage) renderControls(PAGES.find(page => page.id === currentPage));
      },
      preview(id) {
        if (!previewReturn) previewReturn = currentPage;
        show(id);
      },
      endPreview() {
        if (previewReturn && previewReturn !== currentPage) showPage(previewReturn);
        previewReturn = null;
      },
      ready() {
        showPage(landingPage());
      },
      dispose() {
        disposed = true;
        observer.disconnect();
        dockObserver.disconnect();
        slideshowWatch?.disconnect();
        cancelAnimationFrame(resizeFrame);
        dashboard.removeEventListener("click", onClick);
        document.removeEventListener("click", onSlideshowNav, true);
        document.removeEventListener("keydown", onKey);
        window.removeEventListener("season-slideshow-closed", onSlideshowClosed);
      },
      current: () => currentPage,
    };
    return api;
  }

  window.CardPages = Object.freeze({enabled, setMode, attach, PAGES, PAGE_CARD_IDS});
  enabled();
})();
