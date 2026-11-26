/* The arena behind the glass, alive (UI polish pass, 2026-11-26; user: "a more alive background so it feels less
   static"). One fixed layer behind the whole game holds the team's arena picture:
     - it drifts very slowly (a few percent over a minute and a half, then back);
     - it cross-fades when the picture changes (a new phase of the year shows a different spot of the arena, where
       the team has more than one photo: assets/arenas/phases.json);
     - it leans a little to a different side for each sidebar page, so changing page moves you through the building.
   Settings > Look > Background movement switches the drift and the lean off; so does the computer's own
   reduced-motion setting (the cross-fade then becomes a cut). The tables and text never move. */
(() => {
  "use strict";
  const SEASON = new Set(["fantasy_draft", "preseason", "regular_season"]);
  const PLAYOFFS = new Set(["play_in", "playoffs"]);
  // Where the picture leans for each sidebar page: [x, y] in percent of the screen.
  const LEAN = {home: [0, 0], team: [-1.4, .5], office: [1.4, -.5], league: [0, -1.2]};
  const VERSION = "2";   // bump when the pictures in assets/arenas/ are rebuilt: browsers keep the old ones otherwise
  let phases = null, layer = null, shown = "", front = 0;

  // Which of a team's pictures a phase shows: its playoff or offseason photo when it has one, else the season's.
  function fileFor(team, phase, table = phases) {
    const kind = PLAYOFFS.has(phase) ? "playoffs" : SEASON.has(phase) || !phase ? "" : "offseason";
    return (kind && table?.[team]?.[kind]) || `${team}.jpg`;
  }

  const urlFor = (team, phase) => `/assets/arenas/${fileFor(team, phase)}?v=${VERSION}`;

  function ensure() {
    if (layer || typeof document === "undefined" || !document.body) return layer;
    layer = document.createElement("div");
    layer.id = "arenaBackdrop";
    layer.setAttribute("aria-hidden", "true");
    // Two pictures as <img> (the game's look sheets strip background images from every element).
    layer.innerHTML = `<img class="arena-layer" alt="" decoding="async"><img class="arena-layer" alt="" decoding="async">`;
    document.body.prepend(layer);
    return layer;
  }

  function show(team, phase) {
    if (!ensure() || !team) return;
    const url = urlFor(team, phase);
    place();
    if (url === shown) return;
    shown = url;
    const next = layer.children[1 - front], previous = layer.children[front];
    const swap = () => {
      if (shown !== url) return;                      // a newer picture was asked for meanwhile
      front = 1 - front;
      next.classList.add("is-on");
      previous.classList.remove("is-on");
      document.documentElement.dataset.arenaLive = "1";
    };
    next.onload = swap;
    next.onerror = () => { if (shown === url) shown = ""; };   // keep what is on show; try again at the next render
    next.src = url;
  }

  function hide() {
    shown = "";
    delete document.documentElement.dataset.arenaLive;
    if (layer) for (const item of layer.children) item.classList.remove("is-on");
  }

  // Lean toward the side of the sidebar page that is open.
  function place() {
    if (!layer) return;
    const group = document.querySelector(".pages-nav-item.is-current")?.dataset.pagesGroup || "home";
    const [x, y] = LEAN[group] || LEAN.home;
    layer.style.setProperty("--arena-x", `${x}%`);
    layer.style.setProperty("--arena-y", `${y}%`);
  }

  if (typeof document !== "undefined") {
    const later = () => requestAnimationFrame(place);
    document.addEventListener("click", (event) => { if (event.target.closest?.("[data-pages-go]")) later(); });
    document.addEventListener("keydown", (event) => { if (event.key === "[" || event.key === "]") later(); });
    fetch("/assets/arenas/phases.json", {cache: "no-cache"}).then((response) => response.ok ? response.json() : {}).then((table) => {
      phases = table || {};
      window.dispatchEvent(new Event("arena-phases-ready"));
    }).catch(() => { phases = {}; });
  }

  window.ArenaBackdrop = Object.freeze({show, hide, place, fileFor, urlFor});
})();
