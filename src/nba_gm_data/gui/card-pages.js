/* Pages layout (branch sidebar-pages, 2026-11-24).

   The free-floating card board becomes an app: a sidebar of pages on the left, one page at a time filling the rest of the
   screen. Every card the board used to float is "dissolved" onto a page: the same card element, the same size and
   contents, just without its window frame, under a plain section title. A page is rows and columns of cards at their own
   sizes; the whole page scales as one piece to fit the screen, so nothing is ever stretched and the text size matches
   across the cards on a page. List-like cards (the prospect board, the calendar, the league wire feed) may grow into spare
   height or width: they show more rows, never bigger ones.

   Fixed places for controls: the sidebar holds the team, the date and phase, Player Finder, the pages and Settings; a
   page's own controls sit at the right of its title; the one obvious next step is always at the bottom right of the
   footer, which is one piece with the sidebar (the league wire ticker beside it).

   The sidebar is the game's spine (user, 2026-11-26): the phase, the to-do list (progress.js), then only a few pages
   (the year strip runs across the top of every page): Home, Team, Front Office, League. Each of those is a short row of tabs at its title, and a tab shows one
   thing (or a couple that belong together) at full size, instead of many cards forced onto one page. The bottom-right
   button only moves time; when a job blocks it, it names the job and opens it.

   Step screens (the opening roster, Set The Roster, the draft, free agency...) are not listed in the sidebar (user,
   2026-11-24): they open from Home's to-do list and lead back to it.

   card-board.js still builds every window frame and keeps the pop-ups (player cards, extension cards) as windows; this
   module only takes the frames of the cards that belong on pages. Pop-ups that are modals (box scores, the trade room,
   Settings, Player Finder) are untouched. */
(() => {
  "use strict";

  const MODE_KEY = "nbaGmLayoutMode";
  const GAP = 28;            // design pixels between cards
  const MAX_SCALE = 1.22;    // a sparse page may grow this much
  const MIN_SCALE = .7;      // below this the page scrolls instead of shrinking further
  const FULL_MAX_SCALE = 1.25;   // a full-size page on a large screen grows this much, no further
  const lastTab = new Map();         // per save and sidebar page: the tab last open on it
  const lastPage = new Map();        // per save, this session only: a save always opens on Home
  const lastBlocking = new Map();    // per save: the jobs that were blocking the clock at the last render
  let homeCalled = false;            // the game stopped by itself (deadline day, season end): the next render lands on Home
  let attached = null;
  const DETAIL = "@player";          // the page a player's card fills
  const openDetails = new Map();     // per save: the player pages opened on top of each other

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
  // Full-size pages (UI polish pass, Stage C): the page is laid out at real sizes (13px rows, 11px table headings)
  // and its sections share the page's width and height, instead of fixed-size cards scaled down as one picture. A
  // layout marked full: {fits, roomy} is drawn at scale 1 on any page area between those two sizes; a smaller area
  // shrinks the whole page, a larger one grows it a little. Its rows and columns take options:
  //   basis  fixed width (in a row) or height (in a column), in pixels
  //   fill   takes what is left
  // and a section that is a picture (the payroll chart, the draft-assets grid) keeps its proportions:
  //   natural  "fit": drawn at its own size, enlarged as one piece to fit the room it is given
  //            "width": enlarged to the section's width; its height follows
  //   size     [w, h]: the picture's own size, when the board's default (which moves with the window) would change it
  const rowOf = (options, ...items) => ({type: "row", items, ...options});
  const colOf = (options, ...items) => ({type: "col", items, ...options});

  // app.js keeps its state in a top-level binding (not a window property).
  const appState = () => (typeof state !== "undefined" ? state : null);

  // The sidebar's pages. A page here is a tab of one of them. The "now" group (step screens and slideshows) has no
  // place in the sidebar: step screens open from the to-do list.
  const GROUPS = [
    ["home", "Home"],
    ["team", "Team"],
    ["office", "Front Office"],
    ["league", "League"],
  ];

  const PAGES = [
    // The step screens, in the order they follow one another.
    {id: "staff-retention", group: "now", step: true, label: "Staff Retention", layout: () => ({full: {fits: [1220, 600], roomy: [1500, 900]}, ...row(card("phase-staff_retention-decision", {bare: true, fill: true}))})},
    // The draft, the offseason checklist, free agency and the playoffs take over Home while they are on (user,
    // 2026-11-26): each is a Home tab, listed first, and it is where Home lands (phaseHome).
    {id: "draft-room", group: "home", phaseHome: true, label: "Draft", layout: draftRoomLayout},
    {id: "free-agency-checklist", group: "home", phaseHome: true, label: "Checklist", layout: () => ({full: {fits: [1220, 660], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("phase-free_agency-checklist", {bare: true, fill: true})))})},
    {id: "free-agency", group: "home", phaseHome: true, label: "Free Agency", when: () => typeof signingsOpen !== "function" || signingsOpen(), layout: () => ({full: {fits: [1220, 660], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("phase-free_agency-market", {fill: true})),
      colOf({basis: 308}, card("phase-free_agency-wire", {fill: true})))})},
    {id: "fantasy-draft", group: "now", step: true, label: "Fantasy Draft", layout: () => col("phase-fantasy_draft-control", row(card("phase-fantasy_draft-board", {grow: "h"}), card("phase-fantasy_draft-roster", {grow: "h"}), card("phase-fantasy_draft-ticker", {grow: "h"})))},
    {id: "roster-moves", group: "now", step: true, label: () => rosterMovesLabel(), layout: () => ({full: {fits: [1220, 640], roomy: [1500, 900]}, ...row(card("phase-cutdown-decision", {bare: true, fill: true}))})},
    {id: "set-roster", group: "now", step: true, label: "Set The Roster", layout: () => ({full: {fits: [1220, 600], roomy: [1500, 900]}, ...row(card("phase-set_roster-checklist", {bare: true, fill: true}))})},
    // Slideshows open by themselves when they are due (and from Settings).
    {id: "outlook", group: "now", label: "Preseason Outlook", slideshow: "outlook"},
    {id: "recap", group: "now", label: "Year-End Recap", slideshow: "recap"},

    // Home: what is happening. Its tabs: today (the front page: home-front.js), your minutes with the next
    // opponent beside them (while games are played), and the calendar.
    {id: "home-playoffs", group: "home", phaseHome: true, label: "Playoffs", when: () => ["play_in", "playoffs"].includes(String(appState()?.home?.save?.phase || "")), layout: () => ({full: {fits: [1100, 480], roomy: [1500, 900]}, ...row(card("phase-playoffs-bracket", {bare: true, fill: true, natural: "fit", size: [1424, 484]}))})},
    {id: "home", group: "home", label: "Today", layout: homeLayout},
    {id: "minutes", group: "home", label: "Minutes", when: () => phaseHasGames(), layout: () => ({full: {fits: [1100, 660], roomy: [1500, 880]}, ...row(
      colOf({fill: true}, card("minutes", {fill: true})),
      colOf({basis: 420}, card("opponent", {fill: true})))})},
    {id: "schedule", group: "home", label: "Schedule", layout: () => ({full: {fits: [900, 560], roomy: [1500, 900]}, ...row(card("week", {expanded: true, bare: true, fill: true}))})},

    // Team. Roster and Stats are full-size tables; the rest are still the older cards, one main thing a tab.
    {id: "roster", group: "team", label: "Roster", layout: () => ({full: {fits: [1220, 560], roomy: [1500, 900]}, ...row(card("roster", {bare: true, fill: true}))})},
    {id: "stats", group: "team", label: "Stats", layout: () => ({full: {fits: [900, 560], roomy: [1500, 900]}, ...row(card("stats", {bare: true, fill: true}))})},
    {id: "development", group: "team", label: "Development", layout: () => ({full: {fits: [1120, 620], roomy: [1500, 900]}, ...row(card("development", {expanded: true, bare: true, fill: true}))})},
    {id: "staff", group: "team", label: "Staff", layout: () => ({full: {fits: [1120, 560], roomy: [1500, 900]}, ...row(card("staff", {expanded: true, bare: true, fill: true}))})},
    {id: "identity", group: "team", label: "Identity", layout: () => ({full: {fits: [1120, 640], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("identity", {title: "Heat Maps", fill: true, natural: "fit", size: [529, 370]})),
      colOf({basis: 340}, "signals", "morale"))})},
    {id: "profile", group: "team", label: "Profile", layout: () => ({full: {fits: [1120, 640], roomy: [1500, 900]}, ...row(
      colOf({fill: true},
        rowOf({fill: true}, card("offense", {fill: true, natural: "fit", size: [291, 239]}), card("defense", {fill: true, natural: "fit", size: [291, 239]})),
        rowOf({fill: true}, card("factors", {fill: true, natural: "fit", size: [360, 158]}))),
      colOf({basis: 520}, card("efficiency", {fill: true, natural: "fit", size: [279, 312]})))})},

    // Front office. Contracts: the table at full size with the draft assets under it; the payroll chart, enlarged in
    // its own proportions, down the right. Trades: the league's targets the height of the page, your block and what
    // teams want beside them.
    {id: "contracts", group: "office", label: "Contracts", layout: () => ({full: {fits: [1200, 640], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("contracts", {fill: true}), card("picks", {natural: "width"})),
      colOf({basis: 430}, card("payroll", {fill: true, natural: "fit"})))})},
    {id: "trades", group: "office", label: "Trades", controls: "trades", when: () => typeof tradingOpen !== "function" || tradingOpen(), layout: () => ({full: {fits: [1200, 620], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("league-block", {fill: true})),
      colOf({basis: 470}, "team-block", card("team-wants", {fill: true})))})},
    {id: "scouting", group: "office", label: "Draft", layout: () => ({full: {fits: [1120, 640], roomy: [1500, 900]}, ...col(
      rowOf({fill: true}, card("prospects", {expanded: true, fill: true})),
      rowOf({basis: 290}, card("picks", {fill: true, natural: "fit"})))})},

    // League. The playoff tabs are listed while the playoffs are on. The bracket gets a tab of its own (it is as wide
    // as the screen). Both playoff tables are wider than their board windows were: the page gives them their width.
    {id: "standings", group: "league", label: "Standings", layout: () => ({full: {fits: [980, 580], roomy: [1500, 900]}, ...row(card("standings", {expanded: true, bare: true, fill: true}))})},
    // News: the league's feed as a page (news-page.js adds the headline list and the filters beside the posts).
    {id: "news", group: "league", label: "News", layout: () => ({full: {fits: [1180, 620], roomy: [1500, 900]}, ...row(card("league-wire", {expanded: true, bare: true, fill: true}))})},
    // Storylines: every thread the game is following, and the whole history of the one you pick (home-front.js).
    {id: "storylines", group: "league", label: "Storylines", layout: () => ({full: {fits: [1100, 600], roomy: [1500, 900]}, ...row(card("storylines", {bare: true, fill: true}))})},
    {id: "awards", group: "league", label: "Awards", controls: "awards", layout: () => ({full: {fits: [1120, 560], roomy: [1500, 900]}, ...row(
      // Each race lists its ten candidates on a page (four in a board window), so the cards are taller here.
      card("award-mvp", {fill: true, natural: "fit", size: [396, 590]}), card("award-dpoy", {fill: true, natural: "fit", size: [396, 590]}), card("award-roty", {fill: true, natural: "fit", size: [396, 590]}))})},
    {id: "playoffs", group: "league", label: "Playoffs", layout: () => ({full: {fits: [1100, 480], roomy: [1500, 900]}, ...row(card("phase-playoffs-bracket", {bare: true, fill: true, natural: "fit", size: [1424, 484]}))})},
    {id: "playoff-stats", group: "league", label: "Playoff Stats", layout: () => ({full: {fits: [1220, 580], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("phase-playoffs-leaders", {fill: true})),
      colOf({basis: 540}, card("phase-playoffs-injuries", {fill: true})))})},
  ];

  const phaseHasGames = () => {
    const phase = String(appState()?.home?.save?.phase || "");
    return !(phase && typeof window !== "undefined" && window.GameProgress?.PHASES?.[phase]?.games === false);
  };

  // Home's Today tab is the front page all year (home-front.js; user, 2026-11-26): while games are played it leads
  // with your results, from the lottery to training camp with the payroll and the roster. Contracts, the payroll
  // chart and your picks are one click away under Front Office.
  function homeLayout() {
    return {full: {fits: [1180, 660], roomy: [1500, 900]}, ...row(card("front", {bare: true, fill: true}))};
  }

  // The draft room, by state: the lottery (a picture, enlarged), draft night (the prospect board and the order of
  // picks), and the results (every selection, the draft-night trades). All three are full-size pages.
  function draftRoomLayout(ctx) {
    const has = (id) => ctx.available(id);
    if (has("phase-draft-lottery")) return {full: {fits: [900, 520], roomy: [1500, 900]}, ...row(card("phase-draft-lottery", {bare: true, fill: true, natural: "fit", size: [700, 454]}))};
    if (has("phase-draft-summary")) return {full: {fits: [1100, 560], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("phase-draft-summary", {fill: true, quiet: true})),
      colOf({basis: 340}, card("phase-draft-trades", {fill: true, quiet: true})))};
    return {full: {fits: [1220, 600], roomy: [1500, 900]}, ...row(
      colOf({fill: true}, card("phase-draft-board", {fill: true})),
      colOf({basis: 260}, card("phase-draft-order", {fill: true, quiet: true})))};
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

    let detailStack = [];
    let returnPage = null;
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
    const normalize = (item) => typeof item === "string" ? card(item) : item.items ? {...item, items: item.items.map(normalize)} : item;
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
      if (page.when && !page.when()) return false;
      const ids = layoutIds(pageLayout(page));
      return ids.some(available);
    };
    const pageLabel = (page) => typeof page.label === "function" ? page.label() : page.label;
    // During the season the roster-moves screen (two-way places) is a page to visit, not a step.
    const inSeason = () => String(appState()?.home?.save?.phase || "") === "regular_season";
    const isStep = (page) => Boolean(page.step) && !(page.id === "roster-moves" && inSeason());
    const groupOf = (page) => !page || isStep(page) ? null : page.id === "roster-moves" ? "team" : page.group;
    const groupPages = (group) => visiblePages().filter(page => groupOf(page) === group);
    const groupLabel = (group) => GROUPS.find(([id]) => id === group)?.[1] || "";
    const stepPages = () => visiblePages().filter(isStep);

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
    }
    // The phase, the year and the to-do list (progress.js), then the pages, then the search field.
    const progressEl = document.createElement("section");
    progressEl.className = "pages-progress";
    progressEl.innerHTML = `<header class="progress-top"></header><aside class="progress-rail"></aside>`;
    club.after(progressEl);
    progressEl.after(nav);
    if (finder) nav.after(finder);
    if (settings) {
      settings.classList.add("pages-settings");
      settings.innerHTML = `<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 5.6a2.4 2.4 0 1 0 0 4.8 2.4 2.4 0 0 0 0-4.8Zm5.6 3.3-.1-1.8 1.3-1-1.3-2.3-1.6.5-1.5-.9L10 1.8H7.4L6.9 3.4l-1.5.9-1.6-.5L2.5 6.1l1.3 1-.1 1.8-1.2 1 1.3 2.3 1.6-.5 1.5.9.5 1.6H10l.4-1.6 1.5-.9 1.6.5 1.3-2.3Z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg><span>Settings</span>`;
    }

    // ---- The page area: a title row with the page's own controls, the pages, and the footer (ticker + next step).
    const shell = document.createElement("section");
    shell.className = "pages-shell";
    shell.innerHTML = `<div class="pages-sheet">
        <div class="pages-year"></div>
        <header class="pages-head"><h1 class="pages-title"></h1><div class="pages-tabs" role="tablist"></div><div class="pages-controls"></div></header>
        <div class="pages-viewport"></div>
      </div>
      <footer class="pages-foot"><div class="pages-ticker"></div></footer>
      <div class="pages-holding" hidden></div>`;
    header.after(shell);
    const titleEl = shell.querySelector(".pages-title");
    const controlsEl = shell.querySelector(".pages-controls");
    const tabsEl = shell.querySelector(".pages-tabs");
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
    // The one button (progress.js): the main button is the last in the row, so it sits at the far right; the quieter
    // ones (a week, a month, finish the draft) stand to its left. The deadline-day button is gone: the main button
    // says "Sim past the deadline" and Home's list carries the warning.
    const phaseActions = toolbar.querySelector(".card-board-phase-actions");
    (phaseActions?.querySelector(".progress-go") || phaseActions?.querySelector("button"))?.classList.add("is-primary");
    if (deadline) (phaseActions?.querySelector(".progress-go") ? deadline.remove() : toolbar.prepend(deadline));
    foot.append(toolbar);

    // ---- Pages.
    const pageEls = new Map();
    const slotsByPage = new Map();
    const visiblePages = () => PAGES.filter(pageAvailable);

    // In a full-size page a section or a column takes a fixed share (basis) or what is left (fill).
    const share = (el, item, full) => {
      if (!full) return;
      if (item.basis) el.style.flex = `0 0 ${item.basis}px`;
      else if (item.fill) el.classList.add("is-fill");
    };

    function buildNode(item, parent, page, full = false) {
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
          // What the section is for sits behind a small "i" (the tips the first-run tour used to read out).
          const tip = typeof PAGE_SECTION_TIPS !== "undefined" ? PAGE_SECTION_TIPS[item.id] : "";
          const info = tip ? `<span class="ss-info pages-slot-info"><i class="g-info" tabindex="0" aria-label="${esc(tip)}">i</i><span class="ss-info-tip" aria-hidden="true">${esc(tip)}</span></span>` : "";
          head.innerHTML = `<span class="pages-slot-name">${item.link
            ? `<button type="button" class="pages-slot-link" data-pages-go="${esc(item.link)}">${title}<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>`
            : `<h2>${title}</h2>`}${info}</span>`;
          slot.append(head);
        }
        const body = document.createElement("div");
        body.className = "pages-slot-body";
        slot.append(body);
        slot.dataset.grow = item.grow || "";
        if (full && item.natural) slot.classList.add("is-natural");
        slot.pagesItem = item;
        share(slot, item, full);
        parent.append(slot);
        slotsByPage.get(page.id).push(slot);
        return {grow: item.grow || ""};
      }
      const box = document.createElement("div");
      box.className = item.type === "row" ? "pages-row" : "pages-col";
      let growH = false, growW = false;
      for (const child of item.items) {
        const result = buildNode(child, box, page, full);
        if (!result) continue;
        if (/h|both/.test(result.grow)) growH = true;
        if (/w|both/.test(result.grow)) growW = true;
      }
      if (!box.childElementCount) return null;
      const grow = growH && growW ? "both" : growH ? "h" : growW ? "w" : "";
      box.dataset.grow = grow;
      share(box, item, full);
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
          const tree = pageLayout(page);
          const full = tree?.full || null;
          if (full) {
            stage.pagesFull = full;
            stage.classList.add("is-full");
            el.classList.add("is-full");
            el.innerHTML = `<div class="pages-full-holder"></div>`;
            el.firstElementChild.append(stage);
          } else el.append(stage);
          slotsByPage.set(page.id, []);
          const result = buildNode(tree, stage, page, Boolean(full));
          el.dataset.grow = result?.grow || "";
        } else {
          el.classList.add("is-slideshow");
          slotsByPage.set(page.id, []);
        }
        viewport.append(el);
        pageEls.set(page.id, el);
      }
      const detail = document.createElement("div");
      detail.className = "pages-page pages-detail";
      detail.dataset.pagesPage = DETAIL;
      detail.hidden = true;
      detail.innerHTML = `<div class="pages-stage"></div>`;
      viewport.append(detail);
      pageEls.set(DETAIL, detail);
      // Every owned frame lives somewhere in the page area (refreshes find cards by their window id); a card not on any
      // listed page waits in a hidden holding area.
      for (const id of owned) {
        const frame = frames.get(id);
        frame.classList.add("is-page-card");
        const home = id === "league-wire" ? null : firstSlot(id);
        (home ? home.querySelector(".pages-slot-body") : holding).append(frame);
      }
      if (owned.has("league-wire")) placeTicker();
      renderProgress();
      renderNav();
    }

    // The sidebar's phase, year strip and to-do list, drawn by progress.js from the save.
    const progress = () => (typeof window !== "undefined" ? window.GameProgress : null);
    function renderProgress() {
      if (!progress()) { progressEl.hidden = true; return; }
      progressEl.querySelector(".progress-top").innerHTML = progress().topMarkup();
      // The year strip runs across the top of the page (user, 2026-11-26), not in the sidebar.
      shell.querySelector(".pages-year").innerHTML = progress().yearMarkup();
      progressEl.querySelector(".progress-rail").innerHTML = progress().listMarkup((pageId) => pageEls.has(pageId));
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
      // zoom: a full-size page may have enlarged this card as a picture; at a set size it is back to its own.
      Object.assign(frame.style, {width: `${w}px`, height: `${h}px`, left: "", top: "", zIndex: "", zoom: ""});
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

    // A full-size page: its sections share the page area; the frames follow their sections (the stylesheet sizes
    // them), so no pixel sizes are written. One scale for the page, 1 unless the area is smaller than the layout
    // fits in or larger than roomy.
    function clearFrame(id) {
      const frame = frames.get(id), entry = node(id);
      if (!frame || !entry) return;
      Object.assign(frame.style, {width: "", height: "", left: "", top: "", zIndex: "", zoom: ""});
      Object.assign(frame.querySelector(".card-board-body").style, {left: "", top: "", width: "", height: "", transform: ""});
      Object.assign(entry.card.style, {width: "", height: ""});
    }
    function layoutFull(el, stage, slots) {
      el.classList.remove("is-growing", "is-scrolling");
      // The bracket: the series your team plays in carries a mark the style can pick out.
      const mine = appState()?.home?.save?.user_team;
      const mineId = String(mine?.id ?? mine?.team_id ?? mine ?? "");
      for (const card of stage.querySelectorAll(".series-card")) {
        const yours = Boolean(mineId) && [...card.querySelectorAll(".series-team[data-team-id]")].some(row => row.dataset.teamId === mineId);
        if (yours) card.dataset.yours = "true"; else delete card.dataset.yours;
      }
      for (const slot of slots) {
        const body = slot.querySelector(".pages-slot-body");
        Object.assign(body.style, {minWidth: "", minHeight: "", height: ""});
        if (slot.pagesItem.natural) continue;
        clearFrame(slot.dataset.pagesSlot);
        // A table stretches its rows to share the height, up to the lone-table row height: it needs its row count.
        for (const table of slot.querySelectorAll("table")) {
          table.style.setProperty("--full-rows", String(table.tBodies[0]?.rows.length || 1));
          table.style.removeProperty("--full-row-px");
        }
      }
      const holder = stage.parentElement, area = holder.parentElement;
      holder.style.width = holder.style.height = "";
      let width = area.clientWidth, height = area.clientHeight;
      if (area === el) {
        const style = getComputedStyle(viewport);
        width = viewport.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
        height = viewport.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
      }
      width = Math.max(200, width);
      height = Math.max(200, height);
      const {fits, roomy} = stage.pagesFull;
      const small = Math.min(width / fits[0], height / fits[1]);
      const large = Math.min(width / roomy[0], height / roomy[1]);
      const scale = Math.max(MIN_SCALE, Math.min(FULL_MAX_SCALE, small < 1 ? small : large > 1 ? large : 1));
      stage.style.width = `${Math.floor(width / scale)}px`;
      stage.style.height = `${Math.floor(height / scale)}px`;
      stage.style.transform = scale === 1 ? "none" : `scale(${scale})`;
      holder.style.width = `${width}px`;
      holder.style.height = `${height}px`;
      el.style.setProperty("--pages-scale", String(scale));
      dashboard.style.setProperty("--pages-scale", String(scale));
      // Pictures keep their proportions: each is drawn at its own size and enlarged as one piece. Those that follow
      // their width first (their height then moves the sections around them), then those that fit a given room.
      for (const mode of ["width", "fit"]) for (const slot of slots) {
        if (slot.pagesItem.natural !== mode || slot.hidden) continue;
        const id = slot.dataset.pagesSlot, frame = frames.get(id), body = slot.querySelector(".pages-slot-body");
        const size = slot.pagesItem.size ? {width: slot.pagesItem.size[0], height: slot.pagesItem.size[1]} : naturalSize(id, Boolean(slot.pagesItem.expanded));
        sizeFrame(id, size.width, size.height);
        if (FIT_HEIGHT.has(id)) { const fitted = contentHeight(id); if (fitted > 60) { size.height = fitted; sizeFrame(id, size.width, fitted); } }
        const zoom = Math.min(slot.pagesItem.maxZoom || 2, mode === "width" ? body.clientWidth / size.width : Math.min(body.clientWidth / size.width, body.clientHeight / size.height));
        if (mode === "width") body.style.height = `${Math.round(size.height * zoom)}px`;
        frame.style.zoom = String(Math.max(.5, zoom));
      }
      // Headshots fill their row: they need the height the rows came out at.
      for (const slot of slots) for (const table of slot.querySelectorAll("table")) {
        const rowHeight = table.tBodies[0]?.rows[0]?.offsetHeight;
        if (rowHeight) table.style.setProperty("--full-row-px", `${rowHeight}px`);
      }
      // The prospect board is a long list that scrolls: its rows are as many as fit, each 34px to 42px, so the last
      // visible row is not cut.
      for (const list of stage.querySelectorAll(".season-prospect-list-expanded, .draft-prospect-scroll, .draft-summary-scroll, .fa-market-scroll")) {
        const table = list.querySelector("table");
        const legend = list.querySelector(".season-prospect-legend");
        if (!table || !list.clientHeight) continue;
        const room = list.clientHeight - 26 - (legend ? legend.offsetHeight : 0);
        const count = Math.max(1, Math.floor(room / 34));
        const rowPx = Math.min(42, room / count);
        table.style.setProperty("--prospect-row", `${rowPx.toFixed(2)}px`);
        table.style.setProperty("--full-row-px", `${rowPx.toFixed(2)}px`);
      }
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

    // Anything floating over a page (a coach card) hears that the page changed.
    function announcePage(pageId) {
      if (typeof CustomEvent === "function") document.dispatchEvent?.(new CustomEvent("gm:pagechange", {detail: {page: pageId}}));
    }

    // ---- Player pages: the player's card fills the page, scaled as one piece; Back returns to where you were.
    function layoutDetail() {
      const id = detailStack.at(-1), el = pageEls.get(DETAIL), stage = el?.querySelector(".pages-stage");
      if (!id || !stage || !frames.get(id)) return;
      const item = layout[id] || {};
      const width = item.width || 2100, height = item.height || 1270;
      sizeFrame(id, width, height);
      const style = getComputedStyle(viewport);
      const availableWidth = Math.max(200, viewport.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight));
      const availableHeight = Math.max(200, viewport.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom));
      const scale = Math.min(1, availableWidth / width, availableHeight / height);
      stage.style.transform = `scale(${scale})`;
      el.style.width = `${Math.floor(width * scale)}px`;
      el.style.height = `${Math.floor(height * scale)}px`;
      el.style.margin = "0 auto";
      dashboard.style.setProperty("--pages-scale", String(scale));
    }

    function showDetail(id) {
      const frame = frames.get(id);
      if (!frame) return false;
      // A slideshow that stepped aside for this player (its "Back to" button is up) keeps its place.
      const suspended = document.getElementById("ssReturn");
      if (!suspended) closeSlideshowFor();
      if (currentPage !== DETAIL) { returnPage = currentPage; announcePage(DETAIL); }
      detailStack = [...detailStack.filter(other => other !== id && layout[other]?.visible), id];
      openDetails.set(saveKey, [...detailStack]);
      currentPage = DETAIL;
      owned.add(id);
      frame.classList.add("is-page-card", "is-detail-card");
      for (const [pageId, el] of pageEls) el.hidden = pageId !== DETAIL;
      const stage = pageEls.get(DETAIL).querySelector(".pages-stage");
      for (const other of [...stage.children]) if (other !== frame) holding.append(other);
      stage.append(frame);
      paint(id);
      shell.classList.add("is-detail");
      renderDetailHead(frame);
      detailWatch.disconnect();
      detailWatch.observe(frame, {childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"]});
      controlsEl.innerHTML = `<button type="button" class="pages-control pages-detail-back" data-pages-detail-back><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5 4 6l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>${suspended ? esc(suspended.textContent.replace(/^\W+/, "")) : "Back"}</button>`;
      foot.classList.toggle("has-ticker", owned.has("league-wire"));
      if (owned.has("league-wire")) placeTicker();
      layoutDetail();
      viewport.scrollTo?.(0, 0);
      renderNav();
      return true;
    }

    // A player's page is headed like every other page: his name is the title, and his card's own pages (Season,
    // Ratings, Health) are the tabs. Before this the header kept the tabs of the page you came from.
    function renderDetailHead(frame) {
      const pages = [...(frame?.querySelectorAll("[data-player-pages] [data-player-page]") || [])];
      titleEl.textContent = (frame?.querySelector(".approved-profile-name h3") || frame?.querySelector(".approved-profile-name"))?.textContent.trim() || "";
      tabsEl.hidden = pages.length < 2;
      tabsEl.setAttribute("aria-label", "Player pages");
      const short = (title) => String(title || "").split(/[,&]/)[0].trim();
      const markup = pages.length < 2 ? "" : pages.map((page, index) => `<button type="button" role="tab" data-pages-card-page="${index}" aria-selected="${!page.hidden}">${esc(short(page.dataset.pageTitle))}</button>`).join("");
      if (tabsEl.innerHTML !== markup) tabsEl.innerHTML = markup;
    }
    // The card fills in after it opens (its details are fetched) and changes page: keep the header in step.
    let detailFrame = 0;
    const detailWatch = new MutationObserver(() => {
      cancelAnimationFrame(detailFrame);
      detailFrame = requestAnimationFrame(() => { if (currentPage === DETAIL) renderDetailHead(frames.get(detailStack.at(-1))); });
    });

    // Back (or the card's own close): the player under this one, else the page you came from.
    function closeDetail(id) {
      const wasShown = currentPage === DETAIL && detailStack.at(-1) === id;
      detailStack = detailStack.filter(other => other !== id);
      openDetails.set(saveKey, [...detailStack]);
      if (frames.get(id)) holding.append(frames.get(id));
      if (!wasShown) return;
      if (detailStack.length) { showDetail(detailStack.at(-1)); return; }
      const slideshow = document.getElementById("ssReturn");
      if (slideshow) { leaveDetails(); currentPage = null; slideshow.click(); }
      showPage(PAGES.some(page => page.id === returnPage) ? returnPage : "home", {keepSlideshow: Boolean(slideshow)});
    }

    // Moving to a sidebar page leaves every player page.
    function leaveDetails() {
      const leaving = detailStack;
      detailStack = [];
      openDetails.delete(saveKey);
      shell.classList.remove("is-detail");
      for (const id of leaving) {
        if (frames.get(id)) holding.append(frames.get(id));
        ctx.hideDetail?.(id);
      }
    }

    // Lay the current page out: natural sizes first, one scale for the whole page, then growing cards fill.
    function layoutPage() {
      if (!currentPage) return;
      if (currentPage === DETAIL) return layoutDetail();
      const el = pageEls.get(currentPage);
      const stage = el?.querySelector(".pages-stage");
      if (!stage) return;
      const slots = slotsByPage.get(currentPage) || [];
      if (stage.pagesFull) return layoutFull(el, stage, slots);
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
      const holder = el;
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
      holder.style.width = `${Math.ceil(width)}px`;
      holder.style.height = `${Math.ceil(height)}px`;
      el.classList.toggle("is-scrolling", height > availableHeight + 2 || width > availableWidth + 2);
      dashboard.style.setProperty("--pages-scale", String(scale));
    }

    // The sidebar lists the few pages; each opens on the tab last used there. The tabs sit at the page's title.
    const tabKey = (group) => `${saveKey}:${group}`;
    function renderNav() {
      const shown = groupOf(PAGES.find(page => page.id === shownPageId()));
      nav.innerHTML = GROUPS.map(([group, label]) => {
        const items = groupPages(group);
        if (!items.length) return "";
        const remembered = lastTab.get(tabKey(group));
        const target = items.find(page => page.id === remembered) || items[0];
        const current = shown === group;
        return `<button type="button" class="pages-nav-item${current ? " is-current" : ""}" data-pages-group="${group}" data-pages-go="${target.id}"${current ? ' aria-current="page"' : ""}><span>${esc(label)}</span>${items.map(badgeFor).find(Boolean) || ""}</button>`;
      }).join("");
    }
    function renderTabs(page) {
      const group = groupOf(page);
      const items = group ? groupPages(group) : [];
      tabsEl.hidden = items.length < 2;
      tabsEl.setAttribute("aria-label", `${groupLabel(group)} tabs`);
      tabsEl.innerHTML = items.length < 2 ? "" : items.map(item => `<button type="button" role="tab" data-pages-go="${item.id}" aria-selected="${item.id === page.id}">${esc(pageLabel(item))}${item.id === "trades" && offerCount ? ` <em class="pages-nav-badge">${offerCount}</em>` : ""}</button>`).join("");
    }

    // The page the sidebar marks: an open slideshow counts as its page (it can open by itself at the start of a season).
    function shownPageId() {
      const show = window.SeasonSlideshow?.isOpen?.() ? window.SeasonSlideshow.current?.() : null;
      if (show) {
        // A slideshow can become available after the pages were built (a new season's outlook): no page element needed.
        const page = PAGES.find(item => item.slideshow === show.kind);
        if (page) return page.id;
      }
      return currentPage;
    }

    function badgeFor(page) {
      if (page.id === "trades" && offerCount) return `<em class="pages-nav-badge" title="${offerCount} incoming offer${offerCount === 1 ? "" : "s"}">${offerCount}</em>`;
      const required = layoutIds(pageLayout(page)).some(id => node(id)?.required && available(id));
      if (required) return `<em class="pages-nav-badge is-alert" title="A decision is required">!</em>`;
      return "";
    }

    function renderControls(page) {
      controlsEl.replaceChildren();
      // Every card on the page locked (trading closed, no staff changes now): say so where the page's controls live.
      const pageIds = page?.layout ? layoutIds(pageLayout(page)).filter(available) : [];
      const allLocked = pageIds.length > 0 && pageIds.every(isLocked);
      const legal = typeof clipboardLegalActions === "function" ? clipboardLegalActions() : null;
      const tradingClosed = page?.id === "trades" && legal && !["trades", "draft_trades"].some(action => legal.has(action));
      const lockNote = tradingClosed ? `<span class="pages-note">Trading is closed right now</span>`
        : allLocked ? `<span class="pages-note">Not available right now</span>` : "";
      if (page?.controls === "awards" && typeof openLeagueLeadersModal === "function") {
        controlsEl.innerHTML = `<button type="button" class="pages-control" data-pages-leaders>League Leaders</button>`;
      }
      if (lockNote && page?.controls !== "trades") controlsEl.insertAdjacentHTML("afterbegin", lockNote);
      // A step screen opened from Home's list leads back to it.
      if (page && isStep(page) && pageEls.has("home")) controlsEl.insertAdjacentHTML("afterbegin", `<button type="button" class="pages-control pages-step-home" data-pages-go="home"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5 4 6l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Home</button>`);
      if (page?.controls === "trades") {
        // Closed: the buttons that open the trade room are not shown at all (user, 2026-11-27).
        const disabled = "";
        controlsEl.innerHTML = tradingClosed || options.toolbarActions?.tradeDisabled ? lockNote : `<button type="button" class="pages-control" data-pages-trade="finder"${disabled}>Trade Finder</button><button type="button" class="pages-control" data-pages-trade="builder"${disabled}>Trade Builder</button><button type="button" class="pages-control" data-pages-trade="offers"${disabled}>Incoming Offers${offerCount ? ` <em class="pages-nav-badge">${offerCount}</em>` : ""}</button><button type="button" class="pages-control" data-pages-trade="market"${disabled}>Trade Market</button>`;
      }
    }

    function showPage(pageId, {focus = false, fromNav = false, keepSlideshow = false} = {}) {
      const page = PAGES.find(item => item.id === pageId);
      if (page?.slideshow) {
        openSlideshow(page);
        return true;
      }
      if (!page || !pageEls.has(pageId)) return false;
      if (!keepSlideshow) closeSlideshowFor();
      if (currentPage === DETAIL) leaveDetails();
      const previous = currentPage;
      currentPage = pageId;
      if (previous !== pageId) announcePage(pageId);
      // While a save is still loading only Home exists: don't let that overwrite the page you were on.
      if (options.phaseContext != null) lastPage.set(saveKey, pageId);
      for (const [id, el] of pageEls) el.hidden = id !== pageId;
      const group = groupOf(page);
      if (group && options.phaseContext != null) lastTab.set(tabKey(group), pageId);
      titleEl.textContent = groupLabel(group) || page.title || pageLabel(page);
      renderTabs(page);
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
    // A finished (or skipped) slideshow leaves you where you were: Home, with its list.
    const onSlideshowClosed = () => {
      if (disposed) return;
      renderNav();
    };
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
      if (event.target.closest("[data-pages-detail-back]")) {
        event.preventDefault();
        ctx.closeDetail?.(detailStack.at(-1));
        return;
      }
      const cardTab = event.target.closest("[data-pages-card-page]");
      if (cardTab && currentPage === DETAIL) {
        const frame = frames.get(detailStack.at(-1));
        const holder = frame && [frame, ...frame.querySelectorAll("*")].find(el => typeof el._showPlayerCardPage === "function");
        holder?._showPlayerCardPage(Number(cardTab.dataset.pagesCardPage));
        renderDetailHead(frame);
        return;
      }
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
      if (event.key === "Escape" && currentPage === DETAIL) { event.preventDefault(); ctx.closeDetail?.(detailStack.at(-1)); return; }
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
    // A full-size page sizes itself from its contents (how many rows a table has): when a section's contents arrive
    // or change, lay the page out again.
    let fullFrame = 0;
    const fullWatch = new MutationObserver(() => {
      cancelAnimationFrame(fullFrame);
      fullFrame = requestAnimationFrame(() => { if (!disposed && pageEls.get(currentPage)?.classList.contains("is-full")) layoutPage(); });
    });

    buildPages();
    for (const el of pageEls.values()) if (el.classList.contains("is-full")) fullWatch.observe(el.querySelector(".pages-stage"), {childList: true, subtree: true});

    // ---- Which page opens. Home is where you land: when a save loads, when a new phase begins, and whenever a job
    // starts to block the clock (Stage A decision 1). Otherwise you stay on the page you were on, so a sim run from
    // Schedule or a pick made in the draft room does not throw you out of it. A step screen that is still there after a
    // phase change (the draft room, from the lottery to the board to the results) keeps you too.
    // Where Home lands: the phase's own tab while one is on (the draft, the checklist, free agency, the playoffs),
    // Today otherwise.
    const homeId = () => visiblePages().find(page => page.phaseHome && groupOf(page) === "home")?.id || "home";
    function landingPage() {
      const listed = visiblePages().filter(page => !page.slideshow);
      const remembered = lastPage.get(saveKey);
      const stays = remembered && listed.some(page => page.id === remembered);
      const blocking = progress()?.blockingKey?.() || "";
      const newlyBlocked = blocking && blocking !== (lastBlocking.get(saveKey) || "");
      lastBlocking.set(saveKey, blocking);
      if (newlyBlocked && lastPage.has(saveKey)) window.GameSound?.play("must");
      const called = homeCalled;
      homeCalled = false;
      if (!listed.some(page => page.id === "home")) return stays ? remembered : listed[0]?.id || "home";
      if (!stays || newlyBlocked || called) return homeId();
      if (ctx.entering && !isStep(listed.find(page => page.id === remembered))) return homeId();
      return remembered;
    }

    const api = {
      homeId,
      owns: (id) => owned.has(id),
      showDetail,
      closeDetail,
      paint,
      show,
      showPage,
      isShown: (id) => (currentPage === DETAIL && detailStack.at(-1) === id) || Boolean(currentPage && slotOn(currentPage, id)) || (id === "league-wire" && foot.classList.contains("has-ticker")),
      fitContent: (id) => { if (currentPage && slotOn(currentPage, id)) layoutPage(); },
      updateOfferCount(count) {
        offerCount = count;
        renderNav();
        const page = PAGES.find(item => item.id === currentPage);
        if (page) { renderTabs(page); renderControls(page); }
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
        // A player page open before a refresh (or restored with the save) opens again over its page.
        const open = [...nodes.keys()].filter(id => id.startsWith("player-card-") && layout[id]?.visible && !node(id).card.classList.contains("clipboard-player-card--coach"));
        const remembered = (openDetails.get(saveKey) || []).filter(id => open.includes(id));
        showPage(landingPage());
        for (const id of [...open.filter(id => !remembered.includes(id)), ...remembered]) showDetail(id);
      },
      dispose() {
        disposed = true;
        if (attached === api) attached = null;
        observer.disconnect();
        fullWatch.disconnect();
        cancelAnimationFrame(fullFrame);
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
    attached = api;
    return api;
  }

  // The game stopped by itself: show Home now, and keep it through the render that follows.
  function landHome() {
    homeCalled = true;
    try { attached?.showPage(attached.homeId?.() || "home"); } catch { /* the next render lands there */ }
  }

  // Open a tab by its id (the to-do list's jobs, scripts).
  const go = (pageId) => Boolean(attached?.showPage(pageId));

  window.CardPages = Object.freeze({enabled, setMode, attach, landHome, go, PAGES, GROUPS, PAGE_CARD_IDS});
  enabled();
})();
