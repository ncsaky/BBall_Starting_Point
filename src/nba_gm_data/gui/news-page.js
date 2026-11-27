/* League › News as a page (UI polish pass, 2026-11-26; user: "I like the scrollable social media as a concept ...
   the objective is to keep the user engaged and informed on the season they are in").

   The league wire's posts stay as they are drawn (app.js, seasonLeagueWire): this module only adds, beside the feed,
   a list of every headline (date, kind, teams, one line) with filters. Choosing a headline scrolls the feed to its
   post; a filter narrows both. Everything shown comes from the same events the posts are built from
   (state.home.league_events): nothing is invented here. */
(() => {
  "use strict";
  const FILTERS = [["all", "All"], ["mine", "Your team"], ["trade", "Trades"], ["contract", "Contracts"], ["staff", "Staff"], ["other", "Other"]];
  const KIND_LABEL = {trade: "Trade", extension: "Extension", option_decision: "Option", signing: "Signing", staff_fire: "Staff", staff_hire: "Staff"};
  let filter = "all";

  const app = () => (typeof state !== "undefined" ? state : null);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

  // Which filter a kind of event belongs to.
  function groupOf(kind) {
    const value = String(kind || "").toLowerCase();
    if (value.includes("trade")) return "trade";
    if (/staff|coach/.test(value)) return "staff";
    if (/extension|option|sign|contract|waive|release|buyout|qualifying/.test(value)) return "contract";
    return "other";
  }
  const kindLabel = (kind) => KIND_LABEL[kind] || String(kind || "News").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

  function rows() {
    const st = app();
    const mine = String(st?.home?.save?.user_team?.abbrev || (typeof userTeam === "function" ? userTeam() : "") || "");
    return (st?.home?.league_events?.events || []).map((event) => {
      const normal = typeof normalizeLeagueEvent === "function" ? normalizeLeagueEvent(event) : {date: event.date, kind: event.kind, text: event.headline, teams: []};
      return {
        id: String(event.id || ""),
        date: normal.date || "",
        kind: normal.kind || "",
        group: groupOf(normal.kind),
        teams: normal.teams || [],
        mine: Boolean(mine) && (normal.teams || []).includes(mine),
        text: String(event.activity_headline || normal.text || event.headline || "").replace(/\.\.$/, "."),
      };
    });
  }
  const shows = (row) => filter === "all" || (filter === "mine" ? row.mine : row.group === filter);

  function build() {
    const page = document.querySelector('.pages-page[data-pages-page="news"]');
    const body = page?.querySelector(".pages-slot-body"), list = page?.querySelector(".season-wire-activity-list");
    if (!body || !list) return;
    let index = body.querySelector(":scope > .news-index");
    if (!index) {
      index = document.createElement("aside");
      index.className = "news-index";
      index.setAttribute("aria-label", "Headlines");
      body.prepend(index);
    }
    const all = rows();
    const key = `${all.length}:${all[0]?.id || ""}:${filter}:${list.childElementCount}`;
    if (index.dataset.key === key) return;
    index.dataset.key = key;
    const groups = new Set(all.map((row) => row.group));
    if (filter !== "all" && filter !== "mine" && !groups.has(filter)) filter = "all";
    const filters = FILTERS.filter(([id]) => id === "all" || (id === "mine" ? all.some((row) => row.mine) : groups.has(id)));
    const date = (value) => (typeof formatDashboardShortDate === "function" && formatDashboardShortDate(value)) || value;
    const logo = (team) => (typeof teamLogoSrc === "function" && teamLogoSrc(team)) || "";
    const visible = all.filter(shows);
    index.innerHTML = `<h2>Headlines</h2>
      <div class="news-filters" role="tablist" aria-label="Kind of news">${filters.map(([id, label]) => `<button type="button" role="tab" data-news-filter="${id}" aria-selected="${id === filter}">${label}</button>`).join("")}</div>
      <div class="news-rows">${visible.map((row) => `<button type="button" class="news-row${row.mine ? " is-mine" : ""}" data-news-go="${esc(row.id)}">
        <time>${esc(date(row.date))}</time><span class="news-kind">${esc(kindLabel(row.kind))}</span>
        <span class="news-logos">${row.teams.slice(0, 3).map((team) => logo(team) ? `<img src="${esc(logo(team))}" alt="${esc(team)}">` : esc(team)).join("")}</span>
        <b>${esc(row.text)}</b></button>`).join("") || `<p class="news-none">Nothing of this kind yet.</p>`}</div>`;
    // The feed shows the same selection.
    const keep = new Set(visible.map((row) => row.id));
    for (const post of list.querySelectorAll(".season-wire-post")) post.hidden = filter !== "all" && !keep.has(post.dataset.leagueEventId || "");
  }

  if (typeof document !== "undefined") {
    document.addEventListener("click", (event) => {
      const pick = event.target.closest?.("[data-news-filter]");
      if (pick) { filter = pick.dataset.newsFilter; build(); return; }
      const go = event.target.closest?.("[data-news-go]");
      if (!go) return;
      const post = [...document.querySelectorAll('.pages-page[data-pages-page="news"] .season-wire-post')].find((item) => item.dataset.leagueEventId === go.dataset.newsGo);
      if (!post) return;
      post.scrollIntoView({block: "start", behavior: "smooth"});
      post.classList.remove("is-chosen");
      void post.offsetWidth;
      post.classList.add("is-chosen");
    });
    // The pages are rebuilt on every render: keep the list beside the feed whenever the feed is there.
    let frame = 0;
    const watch = new MutationObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(build); });
    const start = () => watch.observe(document.body, {childList: true, subtree: true});
    if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
  }

  if (typeof window !== "undefined") window.NewsPage = Object.freeze({build, groupOf, kindLabel});
})();
