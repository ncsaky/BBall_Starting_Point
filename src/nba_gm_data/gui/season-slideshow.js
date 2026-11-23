/* Season slideshows: the year-end recap (opens once when the Finals end, before the lottery) and the preseason
   outlook (opens once at the start of a season). A large tutorial-style card over a dimmed full-screen backdrop,
   with Previous / Next, Skip, arrow keys, Enter and Escape. Data comes from the `season_slideshow` action
   (src/nba_gm_data/season_slides.py); nothing here computes a game value. */
(function () {
  "use strict";

  const KIND_LABEL = {recap: "YEAR-END RECAP", outlook: "PRESEASON OUTLOOK"};
  const SKIP_LABEL = {recap: "Skip recap", outlook: "Skip outlook"};
  const show = {open: false, data: null, index: 0, returnFocus: null, root: null};

  const esc = (value) => (typeof escapeHtml === "function" ? escapeHtml(value) : String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])));
  const attr = (value) => (typeof escapeAttr === "function" ? escapeAttr(value) : esc(value));
  const num = (value, digits = 1) => (value === null || value === undefined || value === "" || Number.isNaN(Number(value)) ? "—" : Number(value).toFixed(digits));
  const reducedMotion = () => Boolean(window.GameSimulation?.reducedMotion?.() || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
  const logo = (abbrev, size = "") => {
    const src = typeof teamLogoSrc === "function" ? teamLogoSrc(abbrev) : "";
    return src ? `<img class="ss-logo ${size}" src="${attr(src)}" alt="" aria-hidden="true" loading="lazy" decoding="async" />` : "";
  };
  const headshot = (player) => player?.headshot_url
    ? `<span class="ss-headshot"><img src="${attr(player.headshot_url)}" alt="" aria-hidden="true" loading="lazy" decoding="async" referrerpolicy="no-referrer" /></span>`
    : `<span class="ss-headshot ss-headshot-empty" aria-hidden="true"></span>`;
  const statLine = (line) => line ? [["pts", "PTS"], ["reb", "REB"], ["ast", "AST"]].map(([key, label]) => `${num(line[key])} ${label}`).join(" · ") + (line.gp ? ` · ${line.gp} G` : "") : "";
  const roundWord = {first_round: "First round", conference_semifinals: "Second round", conference_finals: "Conference finals", finals: "NBA Finals"};
  const ordinal = (n) => { const v = Number(n); if (!Number.isFinite(v)) return String(n ?? "—"); const s = ["th", "st", "nd", "rd"], m = v % 100; return v + (s[(m - 20) % 10] || s[m] || s[0]); };
  const capitalize = (text) => String(text || "").replace(/^./, (c) => c.toUpperCase());
  const money = (value) => (value === null || value === undefined ? "—" : `$${Number(value).toFixed(1)}M`);

  function table(columns, rows, {sorted = null, caption = "", rowClass = () => ""} = {}) {
    const head = columns.map((col, index) => `<th scope="col" class="${col.cls || ""}${index === sorted ? " ss-sorted" : ""}" data-ss-sort tabindex="0" title="Sort by ${attr(col.label)}"${index === sorted ? ` aria-sort="${SORT_ASCENDING_FIRST.test(col.label) ? "ascending" : "descending"}"` : ""}>${esc(col.label)}</th>`).join("");
    const body = rows.map((row, r) => `<tr class="${rowClass(row, r)}">${columns.map((col, index) => `<td class="${col.cls || ""}${index === sorted ? " ss-sorted" : ""}">${col.render(row, r)}</td>`).join("")}</tr>`).join("");
    return `<table class="ss-table">${caption ? `<caption>${esc(caption)}</caption>` : ""}<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  }
  // Click (or Enter / Space on) any header to sort by it; click again to flip the order. Ranks, seeds and names
  // start smallest-first; every other column starts biggest-first. Blank cells ("—") always sort last.
  const SORT_ASCENDING_FIRST = /^(#|rank|seed|cons\.?|pick|team|player|your player|prospect|pos|from|note|name|team stat|expected role|your scouts|finish|last finish|league rank|gb|l)$/i;
  function sortValue(cell) {
    const text = (cell?.textContent || "").trim();
    if (!text || text === "—" || text === "-") return null;
    if (text === "=") return 0;
    const arrow = text.match(/^([▲▼↑↓+−-])\s*([\d.]+)/);
    if (arrow) return (/[▼↓−-]/.test(arrow[1]) ? -1 : 1) * Number(arrow[2]);
    const ordinal = text.match(/^#?(\d+(?:\.\d+)?)(?:st|nd|rd|th)?\b(?!-)/);
    const plain = text.replace(/[$,%M]/g, "").replace("−", "-");
    if (/^-?[\d.]+$/.test(plain)) return Number(plain);
    const record = text.match(/^(\d+)-(\d+)$/);
    if (record) return Number(record[1]) / Math.max(1, Number(record[1]) + Number(record[2]));
    if (ordinal) return Number(ordinal[1]);
    return text.toLowerCase();
  }
  function sortTable(th) {
    const table = th.closest("table");
    const row = th.parentElement;
    const index = [...row.children].indexOf(th);
    const current = th.getAttribute("aria-sort");
    const ascending = current ? current !== "ascending" : SORT_ASCENDING_FIRST.test(th.textContent.trim());
    row.querySelectorAll("th").forEach((cell) => { cell.removeAttribute("aria-sort"); cell.classList.remove("ss-sorted"); });
    th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
    th.classList.add("ss-sorted");
    // A long list split into side-by-side halves (power rankings) sorts as one list across both halves.
    const split = table.closest("[data-ss-split]");
    const tables = split ? [...split.querySelectorAll(".ss-table")] : [table];
    const bodies = tables.map((t) => t.tBodies[0]);
    const sizes = bodies.map((b) => b.rows.length);
    tables.forEach((t) => t.tHead.rows[0].querySelectorAll("th").forEach((cell, i) => {
      cell.classList.toggle("ss-sorted", i === index);
      if (i === index) cell.setAttribute("aria-sort", ascending ? "ascending" : "descending"); else cell.removeAttribute("aria-sort");
    }));
    const rows = bodies.flatMap((b) => [...b.rows]);
    rows.forEach((tr) => [...tr.cells].forEach((cell, i) => cell.classList.toggle("ss-sorted", i === index)));
    rows.sort((a, b) => {
      const av = sortValue(a.cells[index]);
      const bv = sortValue(b.cells[index]);
      if (av === null || bv === null) return av === bv ? 0 : (av === null ? 1 : -1);
      const order = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv), undefined, {numeric: true});
      return ascending ? order : -order;
    });
    let start = 0;
    bodies.forEach((b, i) => { b.append(...rows.slice(start, start + sizes[i])); start += sizes[i]; });
  }

  const teamCell = (team) => team ? `<span class="ss-team">${logo(team.abbrev)}<b>${esc(team.abbrev)}</b></span>` : "—";
  const playerCell = (player, extra = "") => `<span class="ss-player">${headshot(player)}<span><b>${esc(player?.name || "—")}</b>${extra ? `<small>${extra}</small>` : ""}</span></span>`;
  const note = (text) => text ? `<p class="ss-note">${esc(text)}</p>` : "";

  // ------------------------------------------------------------------ recap slides
  const RENDER = {
    champion(slide) {
      const c = slide.champion || {};
      const mvp = slide.finals_mvp;
      return `<div class="ss-champion">
        <div class="ss-champion-team">${logo(c.abbrev, "ss-logo-xl")}<div><h3>${esc(c.name)}</h3>
          <p>Beat the ${esc(slide.runner_up?.name)} <b>${esc(slide.series_result)}</b> in the Finals${slide.user_won ? " — your team!" : ""}</p>
          <p class="ss-muted">Regular season ${esc(slide.regular_season_record)}</p></div></div>
        <ol class="ss-path">${(slide.path || []).map((step) => `<li><span>${esc(roundWord[step.round] || step.round)}</span>${teamCell(step.opponent)}<b>${esc(step.result)}</b></li>`).join("")}</ol>
        ${mvp ? `<section class="ss-feature"><h4>Finals MVP</h4>${playerCell(mvp, esc(`${mvp.team_abbrev || ""} · ${statLine(mvp.finals_line)}`))}<p class="ss-muted">${esc(mvp.why)}</p></section>` : ""}
      </div>`;
    },
    standings(slide) {
      const conf = (name) => table([
        {label: "#", render: (r) => r.rank, cls: "ss-num"},
        {label: "Team", render: (r) => teamCell(r.team)},
        {label: "W", render: (r) => r.wins, cls: "ss-num"},
        {label: "L", render: (r) => r.losses, cls: "ss-num"},
        {label: "GB", render: (r) => (r.games_behind ? num(r.games_behind) : "—"), cls: "ss-num"},
        {label: "Seed", render: (r) => r.playoff_seed || "—", cls: "ss-num"},
        {label: "Finish", render: (r) => esc(r.result_label)},
      ], slide.conferences?.[name] || [], {sorted: 0, caption: `${name}ern Conference`, rowClass: (r) => (r.is_user ? "ss-user" : "")});
      return `<div class="ss-two">${conf("East")}${conf("West")}</div>`;
    },
    awards(slide) {
      const cards = (slide.awards || []).map((award) => `<section class="ss-award" title="${attr(award.criteria)}"><h4>${esc(award.label)}</h4>
        ${award.player ? `${playerCell(award.player, esc(`${award.team_abbrev || ""} · ${statLine(award.stat_line)}`))}${award.detail ? `<p class="ss-muted">${esc(award.detail)}</p>` : ""}` : `<p class="ss-muted">${esc(award.detail)}</p>`}
        <p class="ss-criteria">${esc(award.criteria)}</p></section>`).join("");
      const teams = (slide.all_nba || []).map((team) => `<div class="ss-allnba-row"><h5>${esc(team.label)}</h5><ul>${team.players.map((p) => `<li>${headshot(p)}<span><b>${esc(p.name)}</b><small>${esc(p.team_abbrev)}</small></span></li>`).join("")}</ul></div>`).join("");
      return `<div class="ss-awards">${cards}</div><section class="ss-allnba" title="${attr(slide.all_nba_criteria)}">${teams}</section>`;
    },
    leaders(slide) {
      return `<div class="ss-grid">${(slide.categories || []).map((cat) => table([
        {label: "#", render: (r, i) => i + 1, cls: "ss-num"},
        {label: "Player", render: (r) => `<b>${esc(r.name)}</b>`},
        {label: "Team", render: (r) => esc(r.team_abbrev || "—")},
        {label: "Per game", render: (r) => num(r.per_game), cls: "ss-num"},
      ], cat.rows, {sorted: 3, caption: cat.label})).join("")}</div>`;
    },
    your_season(slide) {
      const mvp = slide.team_mvp;
      return `<div class="ss-split"><section><div class="ss-big">${logo(slide.team?.abbrev, "ss-logo-lg")}<div><h3>${esc(slide.record)}</h3>
          <p>${esc(slide.result_label)} · ${esc(ordinal(slide.conference_rank))} in the ${esc(slide.conference)}</p></div></div>
        ${table([{label: "Team stat", render: (r) => esc(r.label)}, {label: "Value", render: (r) => esc(r.value), cls: "ss-num"}, {label: "League rank", render: (r) => `${r.rank} of 30`, cls: "ss-num"}], slide.stats || [], {sorted: 2})}</section>
        ${mvp ? `<section class="ss-feature"><h4>Team MVP</h4>${playerCell(mvp, esc(`${mvp.position || ""} · ${mvp.overall} rating`))}<p>${esc(slide.team_mvp_why)}</p></section>` : ""}</div>`;
    },
    trades(slide) {
      if (!(slide.trades || []).length) return `<p class="ss-empty">No trades this season.</p>`;
      return `<div class="ss-stack">${slide.trades.map((trade) => `<section class="ss-trade"><header><span>${esc(trade.date)}</span><span class="ss-muted">Value exchanged ${num(trade.value_involved)} · value swing ${num(trade.value_swing)} · ranked by ${esc(trade.ranked_by)}</span></header>
        <div class="ss-trade-sides">${trade.sides.map((side) => `<div><div class="ss-side-head">${teamCell(side.team)}<small class="ss-muted">${side.phase ? `(${esc(side.phase)}) ` : ""}received:</small></div>
          <ul>${side.received.map((asset) => `<li>${esc(asset.label)}${asset.played_out ? `<small>After the trade: ${asset.played_out.games} G, ${num(asset.played_out.minutes)} min, ${num(asset.played_out.points)} pts, ${num(asset.played_out.rebounds)} reb, ${num(asset.played_out.assists)} ast</small>` : asset.kind === "player" ? `<small>Did not play for them after the trade.</small>` : ""}</li>`).join("") || "<li>—</li>"}</ul></div>`).join("")}</div>
        ${trade.reasons ? `<p class="ss-reason">${esc(trade.reasons)}</p>` : ""}</section>`).join("")}</div>`;
    },
    coaching(slide) {
      if (!(slide.changes || []).length) return `<p class="ss-empty">No coaching changes this season.</p>`;
      return `<div class="ss-stack">${slide.changes.map((change) => `<section class="ss-coach">${logo(change.team?.abbrev, "ss-logo-lg")}<div><h4>${esc(change.team?.name)} · ${esc(change.job)}</h4>
        <p>${change.out ? `Out: <b>${esc(change.out.name)}</b> (grade ${num(change.out.grade)})${change.out.reason ? ` — ${esc(change.out.reason)}` : ""}` : "Vacancy filled"}</p>
        <p>${change.in ? `In: <b>${esc(change.in.name)}</b> (grade ${num(change.in.grade)})` : "Not yet replaced"}</p>
        ${change.in?.style ? `<p class="ss-muted">${esc(change.in.style)}</p>` : ""}<small class="ss-muted">${esc(change.date)}</small></div></section>`).join("")}</div>`;
    },
    free_agents(slide) {
      return table([
        {label: "Player", render: (p) => playerCell(p, esc(`${p.position || ""} · age ${num(p.age, 0)}`)), cls: "ss-player-col"},
        {label: "Team", render: (p) => teamCell(p.team)},
        {label: "Rating", render: (p) => num(p.overall), cls: "ss-num"},
        {label: "Salary now", render: (p) => money(p.current_salary_millions), cls: "ss-num"},
        {label: "Market value / yr", render: (p) => money(p.market_value_millions), cls: "ss-num"},
      ], slide.players || [], {sorted: 4}) + note("Each one's team can re-sign him in the exclusive window before free agency opens.");
    },
    look_ahead(slide) {
      const d = slide.draft || {};
      const draftText = (d.status === "drawn" ? `Your first pick: No. ${esc(d.pick ?? "—")}`
        : d.status === "lottery" ? `Lottery position ${esc(d.lottery_position)} of 14 · ${num(d.odds_first_pick)}% chance at the No. 1 pick`
        : `Playoff team: projected pick ${esc(d.projected_pick ?? "—")}`) + (d.pick_owner ? `<br><small class="ss-muted">Your own first-round pick belongs to ${esc(d.pick_owner)}${d.protection ? ` (${esc(d.protection)})` : ""}.</small>` : "");
      const cap = slide.cap || {};
      return `<div class="ss-split"><section><h4>The draft</h4><p class="ss-lead">${draftText}</p>
        ${table([{label: "Cons.", render: (p) => p.consensus_rank, cls: "ss-num"}, {label: "Prospect", render: (p) => `<b>${esc(p.name)}</b>`}, {label: "Pos", render: (p) => esc(p.position)}, {label: "From", render: (p) => esc(p.school || "—")}, {label: "Your scouts", render: (p) => (p.your_rank ? `#${p.your_rank}` : "—"), cls: "ss-num"}], slide.prospects || [], {sorted: 0, caption: "Consensus top 5"})}</section>
        <section class="ss-feature"><h4>Your cap for ${esc(cap.season)}</h4><dl class="ss-dl"><dt>Committed payroll</dt><dd>${money(cap.payroll_millions)}</dd><dt>Tax line</dt><dd>${money(cap.tax_line_millions)}</dd><dt>Room under the tax</dt><dd>${money(cap.tax_space_millions)}</dd><dt>Hard cap room</dt><dd>${money(cap.hard_cap_space_millions)}</dd></dl></section></div>`;
    },

    // ---------------------------------------------------------------- outlook slides
    power(slide) {
      const change = (r) => r.change === null || r.change === undefined ? "—" : r.change > 0 ? `<span class="ss-up">▲${r.change}</span>` : r.change < 0 ? `<span class="ss-down">▼${-r.change}</span>` : "=";
      const columns = [
        {label: "#", render: (r) => r.rank, cls: "ss-num"},
        {label: "Team", render: (r) => teamCell(r.team)},
        {label: "Overall", render: (r) => num(r.overall), cls: "ss-num"},
        {label: "Last finish", render: (r) => r.last_finish ?? "—", cls: "ss-num"},
        {label: "Change", render: change, cls: "ss-num"},
        {label: "Note", render: (r) => `<small>${esc(r.note || "")}</small>`},
      ];
      const rows = slide.rows || [];
      const half = Math.ceil(rows.length / 2);
      const options = {sorted: 2, rowClass: (r) => (r.is_user ? "ss-user" : "")};
      return `<div class="ss-two ss-compact" data-ss-split>${table(columns, rows.slice(0, half), options)}${table(columns, rows.slice(half), options)}</div>`;
    },
    continuity(slide) {
      const names = (list, unit = "minutes") => list.map((item) => `${item.name} (${item[unit] ?? 0})`).join(", ");
      const rows = (slide.rows || []).map((row) => {
        const arrivals = row.arrivals || [];
        const tip = [`Kept: ${names(row.kept)}`, row.injured.length ? `Kept, out long: ${names(row.injured)}` : "", `Gone: ${names(row.gone)}`, arrivals.length ? `New: ${names(arrivals, "minutes_last_season")}` : ""].filter(Boolean).join("\n");
        return `<li class="${row.is_user ? "ss-user" : ""}" title="${attr(tip)}" tabindex="0" aria-label="${attr(`${row.team.name}: ${row.continuity_pct}% of last season's minutes kept. ${tip}`)}">
          <span class="ss-team">${logo(row.team.abbrev)}<b>${esc(row.team.abbrev)}</b></span>
          <span class="ss-bar"><i class="ss-kept" style="width:${row.kept_pct}%"></i><i class="ss-injured" style="width:${row.injured_pct}%"></i><i class="ss-gone" style="width:${row.gone_pct}%"></i></span></li>`;
      }).join("");
      const legend = slide.legend || {};
      return `<div class="ss-legend"><span><i class="ss-kept"></i>${esc(legend.kept)}</span><span><i class="ss-injured"></i>${esc(legend.injured)}</span><span><i class="ss-gone"></i>${esc(legend.gone)}</span></div>
        <ol class="ss-continuity">${rows}</ol>`;
    },
    leaders_revisited(slide) {
      // Player, his number, and his team: a player who changed teams shows old logo → new logo (playtest 2026-11-22).
      const where = (then, now) => {
        if (!now?.team) return `<span class="ss-muted">${esc(now?.status || "")}</span>`;
        if (!then || then === now.team.abbrev) return teamCell(now.team);
        return `<span class="ss-team ss-move">${logo(then)}<span class="ss-arrow" aria-label="moved to">→</span>${logo(now.team.abbrev)}<b>${esc(now.team.abbrev)}</b></span>`;
      };
      const cats = (slide.categories || []).map((cat) => table([
        {label: "Player", render: (r) => `<b>${esc(r.name)}</b>`},
        {label: "Per game", render: (r) => num(r.per_game), cls: "ss-num"},
        {label: "Team", render: (r) => where(r.team_abbrev, r.now)},
      ], cat.rows, {sorted: 1, caption: `${cat.label} leaders`})).join("");
      const winners = (slide.award_winners || []).map((w) => `<li><b>${esc(w.label)}</b>: ${esc(w.name)} ${where(w.then, w.now)}</li>`).join("");
      return `<div class="ss-grid ss-grid-3">${cats}</div>${winners ? `<section class="ss-feature"><h4>Award winners</h4><ul class="ss-list">${winners}</ul></section>` : ""}`;
    },
    your_team(slide) {
      const cap = slide.cap || {};
      const payout = slide.tax_payout;
      return `<div class="ss-split"><section>${table([
          {label: "Player", render: (p) => playerCell(p, esc(`${p.position || ""} · ${num(p.overall)}`)), cls: "ss-player-col"},
          {label: "Minutes", render: (p) => p.minutes, cls: "ss-num"},
        ], slide.rotation || [], {sorted: 1, caption: "Projected rotation"})}</section>
        <section><h4>Team Signals: overall rank ${esc(slide.overall_rank ?? "—")} of 30</h4>
          <div class="ss-chips"><span class="ss-chip-head">Strengths</span>${(slide.strengths || []).map((s) => `<span class="ss-chip ss-good">${esc(s.label)} · ${s.rank}</span>`).join("")}</div>
          <div class="ss-chips"><span class="ss-chip-head">Weaknesses</span>${(slide.weaknesses || []).map((s) => `<span class="ss-chip ss-bad">${esc(s.label)} · ${s.rank}</span>`).join("")}</div>
          <dl class="ss-dl"><dt>Payroll</dt><dd>${money(cap.payroll_millions)}</dd><dt>Tax line</dt><dd>${money(cap.tax_line_millions)}</dd><dt>Room under the tax</dt><dd>${money(cap.tax_space_millions)}</dd><dt>Hard cap room</dt><dd>${money(cap.hard_cap_space_millions)}</dd>
          <dt>Tax payout share</dt><dd>${payout ? (payout.payout_millions > 0 ? `${money(payout.payout_millions)} (${esc(payout.season)}, paid ${esc(payout.paid_on)})` : payout.tax_bill_millions > 0 ? `None: paid ${money(payout.tax_bill_millions)} in tax (${esc(payout.season)})` : `None for ${esc(payout.season)}`) : "No payout recorded yet"}</dd></dl>
          </section></div>`;
    },
    contracts(slide) {
      return `<div class="ss-two">${table([
          {label: "Your player", render: (p) => playerCell(p, esc(p.position || "")), cls: "ss-player-col"},
          {label: "Salary", render: (p) => money(p.salary_millions), cls: "ss-num"},
          {label: "Projected", render: (p) => money(p.projected_millions), cls: "ss-num"},
        ], slide.extensions || [], {sorted: 2, caption: "Extension-eligible on your team"})}
        ${table([
          {label: "Player", render: (p) => playerCell(p, esc(p.position || "")), cls: "ss-player-col"},
          {label: "Team", render: (p) => teamCell(p.team)},
          {label: "Salary", render: (p) => money(p.salary_millions), cls: "ss-num"},
        ], slide.expiring || [], {sorted: 2, caption: "Biggest expiring deals"})}</div>
        ${(slide.extensions || []).length ? "" : note("No one on your team is eligible for an extension right now.")}`;
    },
    prospects(slide) {
      return table([
        {label: "Cons.", render: (p) => p.consensus_rank, cls: "ss-num"},
        {label: "Prospect", render: (p) => `<b>${esc(p.name)}</b>`},
        {label: "Pos", render: (p) => esc(p.position)},
        {label: "Age", render: (p) => num(p.age, 0), cls: "ss-num"},
        {label: "From", render: (p) => esc(p.school || "—")},
        {label: "Your scouts", render: (p) => (p.your_rank ? `#${p.your_rank}` : "—"), cls: "ss-num"},
        {label: "Scouted", render: (p) => (p.scouted_pct === null || p.scouted_pct === undefined ? "—" : `${num(p.scouted_pct, 0)}%`), cls: "ss-num"},
      ], slide.prospects || [], {sorted: 0}) + (slide.projected_pick ? `<p class="ss-lead">Your pick projects around No. ${esc(slide.projected_pick)} on current strength.</p>` : "");
    },
    storylines(slide) {
      return `<div class="ss-stories">${(slide.items || []).map((item) => `<section class="ss-story"><h4>${esc(item.title)}</h4><p>${esc(item.text)}</p></section>`).join("") || `<p class="ss-empty">A quiet summer.</p>`}</div>`;
    },
    injuries(slide) {
      if (!(slide.players || []).length) return `<p class="ss-empty">No rated player starts the season with an absence of more than 20 games.</p>`;
      return `<div class="ss-stories">${slide.players.map((p) => `<section class="ss-story ss-injury">${playerCell(p, esc(`${p.team?.abbrev || ""} · ${num(p.overall)} rating`))}
        <p><b>${esc(capitalize(p.injury || "injury"))}</b>${p.part ? ` (${esc(p.part)})` : ""}</p><p>${p.whole_season ? "Expected to miss the whole season" : `Expected to miss about ${esc(p.games)} games`}${p.return_date ? `, back around ${esc(p.return_date)}` : ""}.</p></section>`).join("")}</div>`;
    },
  };

  function slideBody(slide) {
    if (slide.unavailable) return `<p class="ss-empty">${esc(slide.unavailable)}</p>`;
    const render = RENDER[slide.key];
    return render ? render(slide) : `<p class="ss-empty">Nothing to show.</p>`;
  }

  function render(direction = 0) {
    const root = show.root;
    const data = show.data;
    const slides = data.slides || [];
    const index = show.index;
    const slide = slides[index] || {};
    const last = index === slides.length - 1;
    const counter = `${String(index + 1).padStart(2, "0")} / ${String(slides.length).padStart(2, "0")}`;
    root.hidden = false;
    root.innerHTML = `<div class="ss-backdrop" aria-hidden="true"></div>
      <article class="ss-card${reducedMotion() || !direction ? "" : direction > 0 ? " ss-enter-next" : " ss-enter-prev"}" role="dialog" aria-modal="true" aria-labelledby="ssTitle" tabindex="-1" data-slide="${attr(slide.key)}">
        <header class="game-tutorial-titlebar ss-titlebar"><span>${esc(KIND_LABEL[data.kind] || "SEASON")} · ${esc(data.season)}</span><span aria-label="Slide ${index + 1} of ${slides.length}">${counter}</span></header>
        <div class="ss-content" aria-live="polite">
          <h2 id="ssTitle">${esc(slide.title || "")}</h2>
          ${slide.note ? `<p class="ss-subtitle">${esc(slide.note)}</p>` : ""}
          <div class="ss-body">${slideBody(slide)}</div>
        </div>
        <footer class="game-tutorial-actions ss-actions">
          <button type="button" class="game-tutorial-skip" data-ss-action="skip">${esc(SKIP_LABEL[data.kind] || "Skip")}</button>
          <div class="ss-dots" aria-hidden="true">${slides.map((_, i) => `<i class="${i === index ? "on" : ""}"></i>`).join("")}</div>
          <div class="game-tutorial-arrows">
            <button type="button" class="game-tutorial-arrow" data-ss-action="previous" aria-label="Previous slide" title="Previous slide" ${index === 0 ? "disabled" : ""}>←</button>
            <button type="button" class="game-tutorial-arrow" data-ss-action="next" aria-label="${last ? "Finish" : "Next slide"}" title="${last ? "Finish" : "Next slide"}">${last ? "✓" : "→"}</button>
          </div>
        </footer>
      </article>`;
    requestAnimationFrame(() => root.querySelector('[data-ss-action="next"]')?.focus({preventScroll: true}));
  }

  function move(step) {
    if (!show.open) return;
    const next = show.index + step;
    if (next < 0) return;
    if (next >= (show.data.slides || []).length) return close();
    show.index = next;
    render(step);
  }

  function close() {
    if (!show.open) return;
    show.open = false;
    show.root.hidden = true;
    show.root.innerHTML = "";
    document.getElementById("app")?.removeAttribute("inert");
    document.body.classList.remove("season-slideshow-open");
    const focus = show.returnFocus;
    show.returnFocus = null;
    if (focus?.isConnected && !focus.disabled) focus.focus({preventScroll: true});
    window.dispatchEvent(new CustomEvent("season-slideshow-closed"));
  }

  function keydown(event) {
    if (!show.open) return;
    const root = show.root;
    if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); return close(); }
    if (event.key === "ArrowRight") { event.preventDefault(); event.stopImmediatePropagation(); return move(1); }
    if (event.key === "ArrowLeft") { event.preventDefault(); event.stopImmediatePropagation(); return move(-1); }
    const header = event.target?.closest?.(".ss-table th[data-ss-sort]");
    if (header && root.contains(header) && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault(); event.stopImmediatePropagation(); return sortTable(header);
    }
    if (event.key === "Enter") {
      const button = event.target?.closest?.("[data-ss-action]");
      if (button && root.contains(button)) return; // the focused button handles Enter itself
      event.preventDefault(); event.stopImmediatePropagation(); return move(1);
    }
    if (event.key === "Tab") {
      const focusable = [...root.querySelectorAll("button:not(:disabled), [tabindex='0']")];
      const first = focusable[0];
      const lastEl = focusable.at(-1);
      if (event.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) { event.preventDefault(); lastEl?.focus(); }
      else if (!event.shiftKey && (document.activeElement === lastEl || !root.contains(document.activeElement))) { event.preventDefault(); first?.focus(); }
      event.stopImmediatePropagation();
      return;
    }
    if (!root.contains(event.target)) { event.preventDefault(); event.stopImmediatePropagation(); }
  }

  function present(data, {startAt = 0} = {}) {
    show.root ||= document.getElementById("seasonSlideshow");
    if (!show.root || !data || !(data.slides || []).length) return false;
    show.data = data;
    show.index = Math.max(0, Math.min(startAt, data.slides.length - 1));
    show.returnFocus = document.activeElement;
    show.open = true;
    document.getElementById("app")?.setAttribute("inert", "");
    document.body.classList.add("season-slideshow-open");
    render(0);
    return true;
  }

  function wire() {
    show.root = document.getElementById("seasonSlideshow");
    if (!show.root) return;
    show.root.addEventListener("click", (event) => {
      const header = event.target.closest(".ss-table th[data-ss-sort]");
      if (header) return sortTable(header);
      const button = event.target.closest("[data-ss-action]");
      if (!button) return;
      const name = button.dataset.ssAction;
      if (name === "previous") move(-1);
      if (name === "next") move(1);
      if (name === "skip") close();
    });
    document.addEventListener("keydown", keydown, true);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();
  window.SeasonSlideshow = Object.freeze({present, close, move, isOpen: () => show.open, current: () => (show.open ? {kind: show.data?.kind, season: show.data?.season, index: show.index} : null), RENDER});
})();
