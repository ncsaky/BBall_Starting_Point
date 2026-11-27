/* A player's first tab (UI polish pass, 2026-11-27; user: "The first section should be the player's career stats.
   Tabs for playoffs and regular season and per36. Then also maybe just a 1 row table for their contract, and a
   projected ovr by age table like we have in the extensions ... I'd put a storylines or narratives or 'things to
   watch' kind of section in there"; reference: docs/ui-references/jfresh-player-card-full.webp).

   One page, read top to bottom: his contract as one row, then his career season by season (regular season or
   playoffs, per game or per 36 minutes) beside what to watch about him and his projected overall by age.
   Everything shown is data the game already holds:
     the player_card payload   career_seasons (per-game lines; a season's playoffs when he played in them),
                               salary_seasons, decline_watch, upside_remaining, injury_body_map
     HomeFront.storylines      the threads about him (talks, demands, injuries: the same ones Home shows)
     the player_outlook action extension_analysis.ability_projection, the scenario model the extension page uses
   Nothing is invented here. */
(() => {
  "use strict";
  const app = () => (typeof state !== "undefined" ? state : null);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const call = (name, ...args) => { try { return typeof globalThis[name] === "function" ? globalThis[name](...args) : undefined; } catch { return undefined; } };
  const logo = (abbrev) => { const src = call("teamLogoSrc", abbrev) || ""; return src ? `<img src="${esc(src)}" alt="" loading="lazy" decoding="async">` : ""; };
  const shortSeason = (season) => String(season || "").replace(/^(\d{2})(\d{2})-(\d{2})$/, "$2-$3");
  const money = (millions) => `$${Number(millions).toFixed(1)}M`;
  const view = {scope: "regular", mode: "game"};   // the tabs' choice, kept while you move between players

  // ---------- Career: one row a season, oldest first, and the career line.
  const COUNTING = [["ppg", "PTS"], ["rpg", "REB"], ["apg", "AST"], ["spg", "STL"], ["bpg", "BLK"], ["topg", "TO"]];
  const SHOOTING = [["fg_pct", "FG%"], ["fg3_pct", "3P%"], ["ft_pct", "FT%"]];

  // A season's line for the chosen scope: his regular season, or that season's playoffs when he played in them.
  function lineOf(season, scope) {
    if (scope !== "playoffs") return season;
    const playoffs = season?.playoffs;
    return playoffs && Number(playoffs.games) > 0 ? {...playoffs, season: season.season, team_abbrevs: playoffs.team_abbrevs || season.team_abbrevs} : null;
  }

  function careerRows(career, scope = "regular", mode = "game") {
    const rows = [...(career || [])].map((season) => lineOf(season, scope)).filter((line) => line && Number(line.games) > 0)
      .sort((a, b) => String(a.season).localeCompare(String(b.season)));
    const per36 = (line, key) => (Number(line.mpg) > 0 ? Number(line[key] || 0) * 36 / Number(line.mpg) : 0);
    const value = (line, key) => (mode === "per36" ? per36(line, key) : Number(line[key] || 0));
    const shaped = rows.map((line) => ({
      season: line.season, teams: line.team_abbrevs || [], games: Number(line.games), mpg: Number(line.mpg || 0),
      counting: COUNTING.map(([key]) => value(line, key)), shooting: SHOOTING.map(([key]) => (line[key] == null ? null : Number(line[key]))),
    }));
    // The career line weights each season by its games (minutes for the per-36 view); shooting needs the attempts
    // the payload does not carry for every split, so it is weighted by games as an approximation of the makes.
    const games = shaped.reduce((sum, row) => sum + row.games, 0);
    const minutes = shaped.reduce((sum, row) => sum + row.games * row.mpg, 0);
    const total = games ? {
      season: "Career", teams: [], games, mpg: minutes / games, career: true,
      counting: COUNTING.map((_, index) => (mode === "per36"
        ? (minutes ? shaped.reduce((sum, row) => sum + row.counting[index] * row.games * row.mpg, 0) / minutes : 0)
        : shaped.reduce((sum, row) => sum + row.counting[index] * row.games, 0) / games)),
      shooting: SHOOTING.map((_, index) => { const seen = shaped.filter((row) => row.shooting[index] != null); const weight = seen.reduce((sum, row) => sum + row.games, 0); return weight ? seen.reduce((sum, row) => sum + row.shooting[index] * row.games, 0) / weight : null; }),
    } : null;
    return {rows: shaped, total};
  }

  function careerTable(career) {
    const {rows, total} = careerRows(career, view.scope, view.mode);
    const one = (value) => (value == null ? "–" : Number(value).toFixed(1));
    const line = (row) => `<tr class="${row.career ? "is-career" : ""}"><th scope="row">${esc(row.career ? "Career" : shortSeason(row.season))}</th>
      <td class="pp-team">${row.career ? "" : row.teams.length > 1 ? `${row.teams.length} teams` : `${logo(row.teams[0])}<span>${esc(row.teams[0] || "")}</span>`}</td>
      <td>${row.games}</td><td>${one(row.mpg)}</td>${row.counting.map((value, index) => `<td class="${index === 0 ? "is-lead" : ""}">${one(value)}</td>`).join("")}${row.shooting.map((value) => `<td>${one(value)}</td>`).join("")}</tr>`;
    const body = rows.length
      ? rows.map(line).join("") + (total && rows.length > 1 ? line(total) : "")
      : `<tr><td class="pp-none" colspan="${4 + COUNTING.length + SHOOTING.length}">${view.scope === "playoffs" ? "No playoff games yet." : "No games yet."}</td></tr>`;
    return `<table class="pp-career-table" data-no-sort aria-label="Career statistics"><thead><tr><th scope="col">Season</th><th scope="col">Team</th><th scope="col">GP</th><th scope="col">MPG</th>${COUNTING.map(([, label]) => `<th scope="col">${label}</th>`).join("")}${SHOOTING.map(([, label]) => `<th scope="col">${label}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`;
  }

  const pick = (group, value, label, current) => `<button type="button" role="tab" data-pp-${group}="${value}" aria-selected="${current === value}">${label}</button>`;
  function careerBlock(career) {
    return `<section class="pp-career" data-pp-career="${esc(JSON.stringify(career || []))}">
      <header><h4>Career stats</h4>
        <div class="pp-tabs" role="tablist" aria-label="Games">${pick("scope", "regular", "Regular season", view.scope)}${pick("scope", "playoffs", "Playoffs", view.scope)}</div>
        <div class="pp-tabs" role="tablist" aria-label="Numbers">${pick("mode", "game", "Per game", view.mode)}${pick("mode", "per36", "Per 36", view.mode)}</div>
      </header>
      <div class="pp-career-scroll">${careerTable(career)}</div></section>`;
  }

  // ---------- Contract: one row, a season a column.
  function contractRow(detail) {
    const seasons = (detail.salary_seasons || []).filter((row) => row && row.season);
    const paid = seasons.filter((row) => row.salary_millions != null && Number.isFinite(Number(row.salary_millions)));
    if (!paid.length) return `<section class="pp-contract"><h4>Contract</h4><p class="pp-none">No contract.</p></section>`;
    const total = paid.reduce((sum, row) => sum + Number(row.salary_millions), 0);
    const cells = seasons.slice(0, paid.length + 1).map((row) => {
      const on = row.salary_millions != null && Number.isFinite(Number(row.salary_millions));
      return `<div class="pp-contract-year${on ? "" : " is-free"}"><small>${esc(shortSeason(row.season))}</small><b>${on ? money(row.salary_millions) : "Free agent"}</b></div>`;
    }).join("");
    return `<section class="pp-contract"><h4>Contract</h4><div class="pp-contract-row">${cells}<div class="pp-contract-year is-total"><small>${paid.length} season${paid.length === 1 ? "" : "s"}</small><b>${money(total)}</b></div></div></section>`;
  }

  // ---------- Things to watch: the storylines about him, then the plain facts that shape his next year.
  function watch(detail) {
    const st = app();
    const id = detail.player_id;
    const today = String(st?.home?.save?.current_date || "");
    const date = (iso) => (call("formatDashboardShortDate", iso) || iso) + (today && iso && iso.slice(0, 4) !== today.slice(0, 4) ? ` ${iso.slice(0, 4)}` : "");
    const items = [];
    const mine = String(st?.home?.save?.user_team?.abbrev || "");
    for (const thread of globalThis.HomeFront?.storylines?.(st, mine) || []) {
      if (thread.kind !== "player" || thread.id !== id) continue;
      for (const step of thread.steps) items.push({tone: thread.closed ? "" : "is-live", when: step.date ? date(step.date) : "Now", text: step.text});
    }
    const paid = (detail.salary_seasons || []).filter((row) => row.salary_millions != null && Number.isFinite(Number(row.salary_millions)));
    if (paid.length === 1) items.push({tone: "is-warn", when: "Contract", text: "In the last season of his contract"});
    const row = (st?.data?.statusDashboard?.rotation || []).find((item) => item.id === id);
    if (row?.extension_eligible) items.push({tone: "is-warn", when: "Contract", text: "Can sign an extension now"});
    const decline = Number(detail.decline_watch?.per_year);
    if (call("declineWatchApplies", detail)) items.push({tone: "is-bad", when: "Aging", text: `Ratings expected to slip about ${Math.abs(decline).toFixed(1)} a year`});
    else if (Number(detail.upside_remaining) > 0) items.push({tone: "is-good", when: "Growth", text: `Room to grow: ${Number(detail.upside_remaining).toFixed(1)} of 5`});
    const body = detail.injury_body_map || {};
    if (body.current_label) items.push({tone: "is-bad", when: "Health", text: `Out: ${body.current_label}`});
    if (Number.isFinite(Number(body.expected_games_total)) && Number.isFinite(Number(body.typical_games_total))) {
      const gap = Number(body.expected_games_total) - Number(body.typical_games_total);
      items.push({tone: gap > 3 ? "is-bad" : gap < -3 ? "is-good" : "", when: "Health", text: `About ${Number(body.expected_games_total).toFixed(0)} games a season lost to injury (a typical player: ${Number(body.typical_games_total).toFixed(0)})`});
    }
    return `<section class="pp-watch"><h4>Things to watch</h4>${items.length
      ? `<ul>${items.map((item) => `<li class="${item.tone}"><time>${esc(item.when)}</time><span>${esc(item.text)}</span></li>`).join("")}</ul>`
      : `<p class="pp-none">Nothing out of the ordinary.</p>`}</section>`;
  }

  // ---------- Projected overall by age: the scenario model's middle line and its range.
  const outlooks = new Map();   // per save, day and player: the action's rows
  const outlookKey = (id) => `${app()?.currentSave || ""}|${app()?.home?.save?.current_date || ""}|${id}`;
  function outlookChart(rows) {
    const points = (rows || []).filter((row) => Number.isFinite(Number(row.overall)));
    if (points.length < 2) return `<p class="pp-none">No projection for this player.</p>`;
    const width = 320, height = 150, left = 30, right = 10, top = 12, bottom = 26;
    const lows = points.map((row) => Number(row.low ?? row.overall)), highs = points.map((row) => Number(row.high ?? row.overall));
    const floor = Math.floor((Math.min(...lows) - 1.5) / 5) * 5, ceiling = Math.ceil((Math.max(...highs) + 1.5) / 5) * 5;
    const x = (index) => left + (width - left - right) * index / (points.length - 1);
    const y = (value) => top + (height - top - bottom) * (1 - (value - floor) / Math.max(1, ceiling - floor));
    const path = (values) => values.map((value, index) => `${index ? "L" : "M"}${x(index).toFixed(1)} ${y(value).toFixed(1)}`).join(" ");
    const band = `${path(highs)} ${lows.map((value, index) => `L${x(lows.length - 1 - index).toFixed(1)} ${y(lows[lows.length - 1 - index]).toFixed(1)}`).join(" ")} Z`;
    const ticks = [];
    for (let value = floor; value <= ceiling; value += 5) ticks.push(value);
    return `<svg class="pp-outlook-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(`Projected overall from ${points[0].overall} at age ${points[0].age} to ${points.at(-1).overall} at age ${points.at(-1).age}`)}">
      ${ticks.map((value) => `<line class="pp-grid" x1="${left}" x2="${width - right}" y1="${y(value).toFixed(1)}" y2="${y(value).toFixed(1)}"></line><text class="pp-axis" x="${left - 6}" y="${(y(value) + 3.5).toFixed(1)}" text-anchor="end">${value}</text>`).join("")}
      <path class="pp-band" d="${band}"></path><path class="pp-line" d="${path(points.map((row) => Number(row.overall)))}"></path>
      ${points.map((row, index) => `<circle class="pp-dot" cx="${x(index).toFixed(1)}" cy="${y(Number(row.overall)).toFixed(1)}" r="2.6"></circle><text class="pp-axis" x="${x(index).toFixed(1)}" y="${height - 8}" text-anchor="middle">${esc(row.age)}</text>`).join("")}
      <text class="pp-value" x="${x(0).toFixed(1)}" y="${(y(Number(points[0].overall)) - 7).toFixed(1)}" text-anchor="start">${Number(points[0].overall).toFixed(1)}</text>
      <text class="pp-value" x="${x(points.length - 1).toFixed(1)}" y="${(y(Number(points.at(-1).overall)) - 7).toFixed(1)}" text-anchor="end">${Number(points.at(-1).overall).toFixed(1)}</text>
    </svg><p class="pp-outlook-key"><i class="pp-key-line"></i>Projected overall<i class="pp-key-band"></i>Scenario range</p>`;
  }
  function outlook(detail) {
    const known = outlooks.get(outlookKey(detail.player_id));
    return `<section class="pp-outlook" data-pp-outlook="${esc(detail.player_id)}"${known ? " data-loaded" : ""}><h4>Projected overall by age</h4><div class="pp-outlook-body">${known ? outlookChart(known) : `<p class="pp-none" role="status">Working it out…</p>`}</div></section>`;
  }
  function loadOutlooks() {
    if (typeof document === "undefined") return;
    for (const node of document.querySelectorAll("[data-pp-outlook]:not([data-loaded]):not([data-loading])")) {
      const id = node.dataset.ppOutlook, key = outlookKey(id);
      node.dataset.loading = "1";
      Promise.resolve(call("action", "player_outlook", {...(call("savePayload") || {}), player_id: id})).then((result) => {
        outlooks.set(key, result?.projection || []);
        for (const target of document.querySelectorAll(`[data-pp-outlook="${CSS.escape(id)}"]`)) {
          target.dataset.loaded = "1"; delete target.dataset.loading;
          target.querySelector(".pp-outlook-body").innerHTML = outlookChart(outlooks.get(key));
        }
      }).catch(() => { delete node.dataset.loading; node.dataset.loaded = "1"; node.querySelector(".pp-outlook-body").innerHTML = `<p class="pp-none">The projection could not be worked out.</p>`; });
    }
  }

  // The whole first tab.
  function page(detail) {
    return `${contractRow(detail)}
      <div class="pp-career-grid">${careerBlock(detail.career_seasons || [])}<aside class="pp-side">${watch(detail)}${outlook(detail)}</aside></div>`;
  }

  if (typeof document !== "undefined") {
    document.addEventListener("click", (event) => {
      const tab = event.target.closest?.("[data-pp-scope], [data-pp-mode]");
      if (!tab) return;
      if (tab.dataset.ppScope) view.scope = tab.dataset.ppScope;
      if (tab.dataset.ppMode) view.mode = tab.dataset.ppMode;
      const block = tab.closest("[data-pp-career]");
      if (!block) return;
      let career = [];
      try { career = JSON.parse(block.dataset.ppCareer || "[]"); } catch { career = []; }
      block.outerHTML = careerBlock(career);
    });
    let frame = 0;
    const watchDom = new MutationObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(loadOutlooks); });
    const start = () => watchDom.observe(document.body, {childList: true, subtree: true});
    if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
  }

  if (typeof window !== "undefined") window.PlayerCareer = Object.freeze({page, careerRows, careerTable, contractRow, watch, outlookChart, view});
})();
