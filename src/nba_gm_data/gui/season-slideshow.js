/* Season slideshows: the year-end recap (opens once when the Finals end, before the lottery) and the preseason
   outlook (opens once at the start of a season). A large tutorial-style card over a dimmed full-screen backdrop,
   with Previous / Next, Skip, arrow keys, Enter and Escape. Data comes from the `season_slideshow` action
   (src/nba_gm_data/season_slides.py); nothing here computes a game value. */
(function () {
  "use strict";

  const KIND_LABEL = {recap: "YEAR-END RECAP", outlook: "PRESEASON OUTLOOK"};
  const SKIP_LABEL = {recap: "Skip recap", outlook: "Skip outlook"};
  const KIND_TITLE = {recap: "Year-End Recap", outlook: "Preseason Outlook"};
  const show = {open: false, data: null, index: 0, returnFocus: null, root: null, viewAll: null};

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
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const shortDate = (iso) => { const parts = /^\d{4}-(\d{2})-(\d{2})/.exec(String(iso || "")); return parts ? `${MONTHS[Number(parts[1]) - 1]} ${Number(parts[2])}` : String(iso || ""); };
  const roundWord = {first_round: "First round", conference_semifinals: "Second round", conference_finals: "Conference finals", finals: "NBA Finals"};
  const ordinal = (n) => { const v = Number(n); if (!Number.isFinite(v)) return String(n ?? "—"); const s = ["th", "st", "nd", "rd"], m = v % 100; return v + (s[(m - 20) % 10] || s[m] || s[0]); };
  const capitalize = (text) => String(text || "").replace(/^./, (c) => c.toUpperCase());
  const money = (value) => (value === null || value === undefined ? "—" : `$${Number(value).toFixed(1)}M`);

  // Every column is centred, header over its values; only the first field (player or team name) and prose sit left
  // (UI style guide). `--i` is the row's place, used by the rows-falling-in entry animation.
  function table(columns, rows, {sorted = null, caption = "", rowClass = () => ""} = {}) {
    const head = columns.map((col, index) => `<th scope="col" class="${col.cls || ""}${index === sorted ? " ss-sorted" : ""}" data-ss-sort tabindex="0" title="Sort by ${attr(col.label)}"${index === sorted ? ` aria-sort="${SORT_ASCENDING_FIRST.test(col.label) ? "ascending" : "descending"}"` : ""}><span class="sort-label">${esc(col.label)}</span></th>`).join("");
    const body = rows.map((row, r) => `<tr class="${rowClass(row, r)}" style="--i:${r}">${columns.map((col, index) => `<td class="${col.cls || ""}${index === sorted ? " ss-sorted" : ""}">${col.render(row, r)}</td>`).join("")}</tr>`).join("");
    // Columns with a set width make a fixed layout: tables shown side by side then line up exactly (same column
    // widths, row heights and alignment), whatever their contents (playtest 2026-11-22).
    const fixed = columns.some((col) => col.width);
    const cols = fixed ? `<colgroup>${columns.map((col) => `<col${col.width ? ` style="width:${col.width}"` : ""}>`).join("")}</colgroup>` : "";
    const total = fixed && columns.every((col) => col.width) ? columns.reduce((sum, col) => sum + parseFloat(col.width), 0) : 0;
    return `<table class="ss-table${fixed ? " ss-fixed" : ""}"${total ? ` style="width:${total}px"` : ""}>${caption ? `<caption>${esc(caption)}</caption>` : ""}${cols}<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
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
    // Rows moved by a sort must not replay the entry animation.
    th.closest(".ss-rows-in")?.classList.remove("ss-rows-in");
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

  const ordinalRank = (n) => { const v = Number(n); if (!Number.isFinite(v) || !v) return "—"; const s = ["th", "st", "nd", "rd"], m = v % 100; return v + (s[(m - 20) % 10] || s[m] || s[0]); };
  // Team slides lead with the logo and the team's overall instead of spelling out the name (playtest 2026-11-22).
  // Preseason ranks are projections, and say so ("Projected 1st of 30"; UI style guide).
  const titleTeam = (slide) => `${logo(slide.logo, "ss-title-logo")}<span class="ss-title-stat"><b>${slide.key === "team_profile" ? "Team profile" : slide.overall_rank ? `Projected ${ordinalRank(slide.overall_rank)} of ${esc(slide.league_teams || 30)}` : ""}</b></span>`;
  const roleChip = (role) => (typeof playerRoleChip === "function" ? playerRoleChip(role) : esc(role || "—"));
  // Ratings are a coloured number: red (low) to blue (high) across the player display range 60-98, the same range
  // and hues as the game's rating bars (app.js playerRatingBarStyle / performanceBarColor), a shade darker so the
  // middle (yellow) stays readable as text.
  const RATING_FLOOR = 60, RATING_CEILING = 98;
  // Same text-safe stops as app.js ratingInkColor (round 3 contrast check: at least 5:1 on the light cards).
  const RATING_STOPS_LIGHT = [[0, [158, 32, 46]], [0.34, [152, 66, 20]], [0.52, [112, 86, 8]], [0.74, [30, 94, 150]], [1, [20, 64, 158]]];
  // Clear (dark) glass: the same scale in light tints (app.js ratingInkColor).
  const RATING_STOPS_CLEAR = [[0, [255, 128, 128]], [0.34, [255, 180, 118]], [0.52, [244, 216, 118]], [0.74, [150, 208, 255]], [1, [182, 198, 255]]];
  function ratingColor(value) {
    const RATING_STOPS = globalThis.document?.documentElement?.dataset?.glass === "clear" ? RATING_STOPS_CLEAR : RATING_STOPS_LIGHT;
    const share = Math.min(1, Math.max(0, (Number(value) - RATING_FLOOR) / (RATING_CEILING - RATING_FLOOR)));
    const upper = Math.max(1, RATING_STOPS.findIndex(([stop]) => share <= stop));
    const [lowStop, low] = RATING_STOPS[upper - 1];
    const [highStop, high] = RATING_STOPS[upper];
    const t = highStop === lowStop ? 0 : (share - lowStop) / (highStop - lowStop);
    return `#${low.map((c, i) => Math.round(c + (high[i] - c) * t).toString(16).padStart(2, "0")).join("")}`;
  }
  const ratingNumber = (v, cls = "") => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? "—"
    : `<b class="ss-rating${cls ? ` ${cls}` : ""}" style="color:${ratingColor(v)}">${num(v)}</b>`);
  // A contract is always one field: salary × years (playtest 2026-11-22).
  const contract = (salary, years) => (typeof contractLabel === "function" ? contractLabel(salary, years)
    : Number(salary) > 0 ? `${money(salary)}${Number(years) > 0 ? ` × ${Number(years)}` : ""}` : "—");
  // Panel title: small capitals with a rule under it, distinct from row text (taste deck 2026-11-23).
  const panelTitle = (text, extra = "") => `<header class="ss-panel-head"><h4 class="ss-panel-title">${esc(text)}</h4>${extra}</header>`;
  // Wraps a slide's rows so they fall into place on entry (skipped under reduced motion; a sort switches it off).
  const rowsIn = () => (reducedMotion() ? "" : " ss-rows-in");

  // One radar, offense on one half and defense on the other, with smooth (Catmull-Rom) curves. Values are league
  // percentiles from Team Signals ranks.
  function curvedRadar(axes, teams = 30) {
    const size = 230, c = size / 2, r = 72;
    const n = axes.length || 1;
    const angle = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const pct = (rank) => Math.max(6, ((teams - Math.min(teams, Math.max(1, Number(rank) || teams)) + 0.5) / teams) * 100);
    const at = (i, value) => [c + Math.cos(angle(i)) * r * value / 100, c + Math.sin(angle(i)) * r * value / 100];
    const smooth = (pts) => {
      let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
      for (let i = 0; i < pts.length - 1; i += 1) {
        const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
        const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
        const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
        d += ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
      }
      return d + " Z";
    };
    const sides = new Set(axes.map((a) => a.side));
    // Closed smooth curve through every point (wrapping round), for a radar that covers one side's axes only.
    const smoothClosed = (pts) => {
      const m = pts.length;
      let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
      for (let i = 0; i < m; i += 1) {
        const p0 = pts[(i - 1 + m) % m], p1 = pts[i], p2 = pts[(i + 1) % m], p3 = pts[(i + 2) % m];
        const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
        const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
        d += ` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
      }
      return d + " Z";
    };
    const layer = (side) => {
      const idx = axes.map((a, i) => (a.side === side ? i : -1)).filter((i) => i >= 0);
      if (!idx.length) return "";
      if (sides.size === 1 && idx.length >= 3) return `<path class="ss-radar-${side}" d="${smoothClosed(idx.map((i) => at(i, pct(axes[i].rank))))}"></path>`;
      return `<path class="ss-radar-${side}" d="${smooth([[c, c], ...idx.map((i) => at(i, pct(axes[i].rank))), [c, c]])}"></path>`;
    };
    const rings = [25, 50, 75, 100].map((v) => `<circle class="ss-radar-ring" cx="${c}" cy="${c}" r="${(r * v / 100).toFixed(1)}"></circle>`).join("");
    const spokes = axes.map((_, i) => { const [x, y] = at(i, 100); return `<line class="ss-radar-spoke" x1="${c}" y1="${c}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"></line>`; }).join("");
    const labels = axes.map((a, i) => {
      const [x, y] = at(i, 128);
      const anchor = Math.abs(x - c) < 6 ? "middle" : x < c ? "end" : "start";
      return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="${anchor}" class="ss-radar-label"><tspan>${esc(a.label)}</tspan><tspan class="ss-radar-rank" dx="4">${ordinalRank(a.rank)}</tspan></text>`;
    }).join("");
    const only = sides.size === 1 ? [...sides][0] : "";
    const caption = only ? `<span class="ss-key ss-key-${only}">${only === "offense" ? "Offense" : "Defense"}</span>` : `<span class="ss-key ss-key-offense">Offense</span><span class="ss-key ss-key-defense">Defense</span>`;
    return `<figure class="ss-radar${only ? ` ss-radar-single ss-radar-only-${only}` : ""}"><svg viewBox="-112 -16 ${size + 224} ${size + 32}" role="img" aria-label="Team Signals: ${only || "offense and defense"} league ranks">${rings}${spokes}${layer("offense")}${layer("defense")}${labels}</svg>
      <figcaption>${caption}</figcaption></figure>`;
  }

  // The leader, storyline and injury slides get more rows than a small screen holds: show what the height takes.
  const bySize = (short, medium, tall) => { const h = window.innerHeight || 900; return h >= 1100 ? tall : h >= 950 ? medium : short; };

  // A name opens that player's card (players who left the league have no card).
  const name = (r) => (r.player_id && !String(r.player_id).startsWith("real:") && r.now?.status !== "No longer in the league"
    ? `<button type="button" class="ss-player-link" data-ss-player="${attr(r.player_id)}">${esc(r.name)}</button>` : `<b>${esc(r.name)}</b>`);
  const teamCell = (team) => team?.abbrev ? `<span class="ss-team">${logo(team.abbrev)}<b>${esc(team.abbrev)}</b></span>` : "—";
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
        {label: "#", render: (r) => r.rank, cls: "ss-num", width: "42px"},
        {label: "Team", render: (r) => teamCell(r.team), cls: "ss-left", width: "78px"},
        {label: "W", render: (r) => r.wins, cls: "ss-num", width: "36px"},
        {label: "L", render: (r) => r.losses, cls: "ss-num", width: "36px"},
        {label: "GB", render: (r) => (r.games_behind ? num(r.games_behind) : "—"), cls: "ss-num", width: "42px"},
        {label: "Seed", render: (r) => r.playoff_seed || "—", cls: "ss-num", width: "42px"},
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
        {label: "#", render: (r, i) => i + 1, cls: "ss-num", width: "42px"},
        {label: "Player", render: name, cls: "ss-left"},
        {label: "Team", render: (r) => teamCell({abbrev: r.team_abbrev}), width: "64px"},
        {label: "Per game", render: (r) => num(r.per_game), cls: "ss-num", width: "84px"},
      ], cat.rows, {sorted: 3, caption: cat.label})).join("")}</div>`;
    },
    your_season(slide) {
      const mvp = slide.team_mvp;
      return `<div class="ss-split"><section><div class="ss-big">${logo(slide.team?.abbrev, "ss-logo-lg")}<div><h3>${esc(slide.record)}</h3>
          <p>${esc(slide.result_label)} · ${esc(ordinal(slide.conference_rank))} in the ${esc(slide.conference)}</p></div></div>
        ${table([{label: "Team stat", render: (r) => esc(r.label), cls: "ss-left"}, {label: "Value", render: (r) => esc(r.value), cls: "ss-num"}, {label: "League rank", render: (r) => `${r.rank} of 30`, cls: "ss-num"}], slide.stats || [], {sorted: 2})}</section>
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
        {label: "Rating", render: (p) => ratingNumber(p.overall), cls: "ss-num"},
        {label: "Contract", render: (p) => contract(p.current_salary_millions, 1), cls: "ss-num"},
        {label: "Market value / yr", render: (p) => money(p.market_value_millions), cls: "ss-num"},
      ], slide.players || [], {sorted: 4}) + note("Each one's team can re-sign him in the exclusive window before free agency opens.");
    },
    look_ahead(slide) {
      const d = slide.draft || {};
      const draftText = (d.status === "drawn" ? `Your first pick: No. ${esc(d.pick ?? "—")}`
        : d.status === "lottery" ? `Lottery position ${esc(d.lottery_position)} of ${esc(d.lottery_teams ?? 14)} · ${num(d.odds_first_pick)}% chance at the No. 1 pick`
        : `Playoff team: projected pick ${esc(d.projected_pick ?? "—")}`) + (d.pick_owner ? `<br><small class="ss-muted">Your own first-round pick belongs to ${esc(d.pick_owner)}${d.protection ? ` (${esc(d.protection)})` : ""}.</small>` : "");
      const cap = slide.cap || {};
      return `<div class="ss-split"><section><h4>The draft</h4><p class="ss-lead">${draftText}</p>
        ${table([{label: "Cons.", render: (p) => p.consensus_rank, cls: "ss-num"}, {label: "Prospect", render: (p) => `<b>${esc(p.name)}</b>`, cls: "ss-left"}, {label: "Pos", render: (p) => esc(p.position)}, {label: "From", render: (p) => esc(p.school || "—")}, {label: "Your scouts", render: (p) => (p.your_rank ? `#${p.your_rank}` : "—"), cls: "ss-num"}], slide.prospects || [], {sorted: 0, caption: "Consensus top 5"})}</section>
        <section class="ss-feature"><h4>Your cap for ${esc(cap.season)}</h4><dl class="ss-dl"><dt>Committed payroll</dt><dd>${money(cap.payroll_millions)}</dd><dt>Tax line</dt><dd>${money(cap.tax_line_millions)}</dd><dt>Room under the tax</dt><dd>${money(cap.tax_space_millions)}</dd><dt>Hard cap room</dt><dd>${money(cap.hard_cap_space_millions)}</dd></dl></section></div>`;
    },

    // ---------------------------------------------------------------- outlook slides
    power(slide) {
      const change = (r) => r.change === null || r.change === undefined ? "—" : r.change > 0 ? `<span class="ss-up">▲${r.change}</span>` : r.change < 0 ? `<span class="ss-down">▼${-r.change}</span>` : "=";
      const columns = [
        {label: "#", render: (r) => r.rank, cls: "ss-num", width: "42px"},
        {label: "Team", render: (r) => teamCell(r.team), cls: "ss-left", width: "72px"},
        {label: "Overall", render: (r) => num(r.overall), cls: "ss-num", width: "72px"},
        {label: "Last finish", render: (r) => r.last_finish ?? "—", cls: "ss-num", width: "84px"},
        {label: "Change", render: change, cls: "ss-num", width: "60px"},
        {label: "Note", render: (r) => `<small class="ss-clamp" title="${attr(r.note || "")}">${esc(r.note || "")}</small>`, cls: "ss-left"},
      ];
      const rows = slide.rows || [];
      const half = Math.ceil(rows.length / 2);
      const options = {sorted: 2, rowClass: (r) => (r.is_user ? "ss-user" : "")};
      return `<div class="ss-boxed${rowsIn()}"><div class="ss-two ss-compact" data-ss-split>${table(columns, rows.slice(0, half), options)}${table(columns, rows.slice(half), options)}</div></div>`;
    },
    continuity(slide) {
      const names = (list, unit = "minutes") => list.map((item) => `${item.name} (${item[unit] ?? 0})`).join(", ");
      const item = (row, i) => {
        const arrivals = row.arrivals || [];
        const tip = [`Kept: ${names(row.kept)}`, row.injured.length ? `Kept, out long: ${names(row.injured)}` : "", `Gone: ${names(row.gone)}`, arrivals.length ? `New: ${names(arrivals, "minutes_last_season")}` : ""].filter(Boolean).join("\n");
        return `<li class="${row.is_user ? "ss-user" : ""}" style="--i:${i}" title="${attr(tip)}" tabindex="0" aria-label="${attr(`${row.team.name}: ${row.continuity_pct}% of last season's minutes kept. ${tip}`)}">
          <span class="ss-team">${logo(row.team.abbrev)}<b>${esc(row.team.abbrev)}</b></span>
          <span class="ss-bar"><i class="ss-kept" style="width:${row.kept_pct}%"></i><i class="ss-injured" style="width:${row.injured_pct}%"></i><i class="ss-gone" style="width:${row.gone_pct}%"></i></span></li>`;
      };
      // Two bordered columns, like the power rankings beside it.
      const rows = slide.rows || [];
      const half = Math.ceil(rows.length / 2);
      const legend = slide.legend || {};
      return `<div class="ss-legend"><span><i class="ss-kept"></i>${esc(legend.kept)}</span><span><i class="ss-injured"></i>${esc(legend.injured)}</span><span><i class="ss-gone"></i>${esc(legend.gone)}</span></div>
        <div class="ss-two ss-continuity-cols${rowsIn()}"><ol class="ss-continuity">${rows.slice(0, half).map(item).join("")}</ol>${rows.length > half ? `<ol class="ss-continuity" start="${half + 1}">${rows.slice(half).map(item).join("")}</ol>` : ""}</div>`;
    },
    leaders_revisited(slide) {
      // Player, his number, and his team: a player who changed teams shows old logo → new logo (playtest 2026-11-22).
      const where = (then, now) => {
        if (!now?.team) return `<span class="ss-muted">${esc(now?.status || "")}</span>`;
        if (!then || then === now.team.abbrev) return teamCell(now.team);
        return `<span class="ss-team ss-move">${logo(then)}<svg class="ss-arrow" role="img" aria-label="moved to" viewBox="0 0 14 10" width="14" height="10"><path d="M1 5h11M8 1.5 12 5 8 8.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>${logo(now.team.abbrev)}<b>${esc(now.team.abbrev)}</b></span>`;
      };
      const value = (v) => (v === null || v === undefined ? "—" : num(v));
      if (show.viewAll && (slide.players || []).length) {
        // "View all": one table of every qualifying player and every stat, sorted by the category that was opened.
        const stats = [["points", "PTS"], ["rebounds", "REB"], ["assists", "AST"], ["steals", "STL"], ["blocks", "BLK"],
                       ["fg3m", "3PM"], ["fg3_pct", "3P%"], ["ft_pct", "FT%"], ["minutes", "MIN"]];
        const key = show.viewAll;
        const columns = [
          {label: "Player", render: name, cls: "ss-left"},
          {label: "Team", render: (r) => where(r.team_abbrev, r.now)},
          {label: "G", render: (r) => r.games, cls: "ss-num"},
          ...stats.map(([stat, label]) => ({label, render: (r) => value(r[stat]), cls: "ss-num"})),
        ];
        const ordered = [...slide.players].sort((a, b) => (b[key] ?? -Infinity) - (a[key] ?? -Infinity));
        const sorted = 3 + Math.max(0, stats.findIndex(([stat]) => stat === key));
        return `<div class="ss-viewall-bar"><button type="button" class="ss-back" data-ss-view-all="">← Back</button></div>
          <div class="ss-viewall">${table(columns, ordered, {sorted})}</div>`;
      }
      const cats = (slide.categories || []).map((cat) => `<section class="ss-leader-cat">${panelTitle(cat.label, (slide.players || []).length ? `<button type="button" class="ss-view-all" data-ss-view-all="${attr(cat.stat)}">View all</button>` : "")}${table([
        {label: "Player", render: name, cls: "ss-left"},
        {label: "Team", render: (r) => where(r.team_abbrev, r.now), width: "120px"},
        {label: /_pct$/.test(cat.stat) ? "Pct" : "Per game", render: (r) => value(r.per_game), cls: "ss-num", width: "76px"},
      ], cat.rows.slice(0, bySize(5, 6, 7)), {sorted: 2})}</section>`).join("");
      const winners = (slide.award_winners || []).map((w) => `<li><b>${esc(w.label)}</b>: ${esc(w.name)} ${where(w.then, w.now)}</li>`).join("");
      return `<div class="ss-grid ss-grid-3 ss-leader-grid">${cats}</div>${winners ? `<section class="ss-feature ss-winners">${panelTitle("Award winners")}<ul class="ss-list">${winners}</ul></section>` : ""}`;
    },
    // Your team: a picture of the team, not a roster table (taste deck 2026-11-23). The projected starting five as
    // large tiles (headshot, name, coloured overall, offense and defense roles as a pair), the bench as small tiles,
    // and three league-relative numbers.
    your_team(slide) {
      const rotation = slide.rotation || [];
      const byId = new Map(rotation.map((p) => [p.id, p]));
      const byMinutes = [...rotation].sort((a, b) => (Number(b.minutes) || 0) - (Number(a.minutes) || 0) || (Number(b.overall) || 0) - (Number(a.overall) || 0));
      const starterIds = (slide.starters || []).filter((id) => byId.has(id));
      const starters = starterIds.length ? starterIds.map((id) => byId.get(id)) : byMinutes.filter((p) => !p.injury).slice(0, 5);
      const bench = byMinutes.filter((p) => !starters.includes(p));
      const injury = (p) => (p.injury ? `<span class="ss-injury" title="${attr(`${p.injury.label || "Injured"}${p.injury.whole_season ? ", expected to miss the season" : `, about ${p.injury.games} games`}${p.injury.return_date ? `, back around ${p.injury.return_date}` : ""}`)}">✚ ${p.injury.whole_season ? "season" : esc(p.injury.games)}</span>` : "");
      const link = (p) => name({...p, player_id: p.id});
      const opens = (p) => (p.id && !String(p.id).startsWith("real:") ? ` data-ss-tile-player="${attr(p.id)}"` : "");
      const drop = (p) => (p.injury && Number(p.injury.return_penalty) >= 0.1 ? `<small class="rating-drop is-on-return" title="${attr(`Out injured: ${Number(p.injury.return_penalty).toFixed(1)} lower for his first games back`)}">−${Number(p.injury.return_penalty).toFixed(1)}</small>` : "");
      const roleText = (role) => {
        if (!role) return "";
        const [label, tone] = (typeof PLAYER_ROLE_CHIPS === "object" && PLAYER_ROLE_CHIPS[role]) || [role, "unknown"];
        return `<span class="role-text role-${attr(tone)}">${esc(label)}</span>`;
      };
      const SLOTS = ["PG", "SG", "SF", "PF", "C"];
      const starterTile = (p, i) => `<li class="ss-tile ss-tile-starter" style="--i:${i}"${opens(p)}>
          <span class="ss-tile-pos">${SLOTS[i] || esc(p.position || "")}</span>
          <span class="ss-tile-photo">${headshot(p)}</span>
          <span class="ss-tile-name">${link(p)}${injury(p)}</span>
          <span class="ss-tile-ovr" title="Overall">${ratingNumber(p.overall)}${drop(p)}</span>
          <span class="ss-role-pair">${roleText(p.off_role)}${roleText(p.def_role)}</span></li>`;
      // Depth chart (round 3): a column per position group (guards, wings, bigs), a row per player in the order the
      // coach uses them (most minutes first). A player's group comes from his first listed position.
      const GROUPS = [["Guards", ["PG", "SG", "G"]], ["Wings", ["SF", "GF", "F"]], ["Bigs", ["PF", "C", "FC"]]];
      const groupOf = (p) => {
        const tokens = String(p.position || "").toUpperCase().split(/[^A-Z]+/).filter(Boolean);
        const first = tokens[0] || "F";
        return Math.max(0, GROUPS.findIndex(([, list]) => list.includes(first)));
      };
      const columns = GROUPS.map((_, index) => bench.filter((p) => groupOf(p) === index));
      // Round 4: every fact its own column (no small text under a name), names left-aligned so the entries line up in
      // both directions, the headshot centred on the name. Each group: Player | OVR | Min | Pos.
      const depthCells = (p, index) => p
        ? `<td class="ss-depth-name${index ? " is-group-start" : ""}"${opens(p)}><span class="ss-depth-player">${headshot(p)}<span class="ss-tile-name">${link(p)}${injury(p)}</span></span></td><td class="ss-depth-num">${ratingNumber(p.overall)}${drop(p)}</td><td class="ss-depth-num">${p.minutes ? esc(p.minutes) : "—"}</td><td class="ss-depth-num">${esc(p.position || "—")}</td>`
        : `<td class="ss-depth-name is-empty${index ? " is-group-start" : ""}"></td><td></td><td></td><td></td>`;
      const depthRows = Array.from({length: Math.max(1, ...columns.map((col) => col.length))}, (_, row) =>
        `<tr>${columns.map((col, index) => depthCells(col[row], index)).join("")}</tr>`).join("");
      const depthCols = GROUPS.map(() => `<col class="ss-depth-col-name"><col class="ss-depth-col-ovr"><col class="ss-depth-col-num"><col class="ss-depth-col-num">`).join("");
      const depthTable = `<table class="ss-depth-table is-by-group is-fields"><colgroup>${depthCols}</colgroup><thead>
          <tr class="ss-depth-groups">${GROUPS.map(([label], index) => `<th colspan="4" scope="colgroup"${index ? ` class="is-group-start"` : ""}>${label}</th>`).join("")}</tr>
          <tr class="ss-depth-fields">${GROUPS.map((_, index) => `<th scope="col" class="ss-depth-name${index ? " is-group-start" : ""}">Player</th><th scope="col">OVR</th><th scope="col">Min</th><th scope="col">Pos</th>`).join("")}</tr>
        </thead><tbody>${depthRows}</tbody></table>`;
      return `<div class="ss-team-board${rowsIn()}">
          <section class="ss-starters">${panelTitle("Starting five")}<ol class="ss-starter-row">${starters.map(starterTile).join("")}</ol></section>
          ${bench.length ? `<section class="ss-depth">${panelTitle("Depth chart")}${depthTable}</section>` : ""}
        </div>`;
    },
    // Team profile: two titled panels, the strengths radar and the payroll chart with its numbers underneath.
    team_profile(slide) {
      const cap = slide.cap || {};
      const payout = slide.tax_payout;
      const horizon = slide.salary_horizon || {};
      const chart = typeof salaryHorizonChart === "function" && (horizon.seasons || []).length
        ? salaryHorizonChart({seasons: horizon.seasons, rows: horizon.rows || [], capByYear: horizon.cap_by_year || {}, className: "ss-payroll-chart"}) : "";
      const payoutText = !payout ? "—" : payout.payout_millions > 0 ? `${money(payout.payout_millions)} (${esc(payout.season)})`
        : payout.tax_bill_millions > 0 ? `Paid ${money(payout.tax_bill_millions)} tax` : "None";
      // Room below a line reads as "over" it when negative, never "$-16.5M".
      const room = (value, under, over) => (Number(value) < 0 ? [over, money(-Number(value))] : [under, money(value)]);
      const figures = [["Payroll", money(cap.payroll_millions)], ["Tax line", money(cap.tax_line_millions)],
                       room(cap.tax_space_millions, "Room under the tax", "Over the tax by"),
                       room(cap.hard_cap_space_millions, "Hard cap room", "Over the hard cap by"), ["Tax payout share", payoutText]];
      const radarAxes = slide.radar || [];
      const bySide = ["offense", "defense"].map((side) => radarAxes.filter((a) => a.side === side));
      const radars = !radarAxes.length ? `<p class="ss-empty">—</p>`
        : bySide.every((axes) => axes.length >= 3)
          ? `<div class="ss-radar-pair">${bySide.map((axes) => curvedRadar(axes, slide.league_teams || 30)).join("")}</div>`
          : curvedRadar(radarAxes, slide.league_teams || 30);
      return `<div class="ss-profile">
          <section class="ss-panel ss-panel-radar is-centred-title">${panelTitle("Strengths")}${radars}</section>
          <section class="ss-panel ss-panel-payroll is-centred-title">${panelTitle("Payroll")}<div class="ss-payroll-block"><div class="ss-payroll">${chart}</div>
            <table class="ss-cap-table"><tbody>${figures.map(([label, value]) => `<tr><td class="ss-cap-label">${esc(label)}</td><td class="ss-cap-value">${value}</td></tr>`).join("")}</tbody></table></div></section>
        </div>`;
    },
    // Contracts to watch: bar charts, not salary tables. Every contract reads "$X × N" (UI style guide).
    contracts(slide) {
      const who = (p) => `<span class="ss-player ss-bar-player">${headshot(p)}<span class="ss-player-name">${name({...p, player_id: p.id})}</span></span>`;
      const extensions = slide.extensions || [];
      const extMax = Math.max(1, ...extensions.flatMap((p) => [Number(p.salary_millions) || 0, Number(p.projected_millions) || 0]));
      const share = (v, max) => Math.max(0.02, Math.min(1, (Number(v) || 0) / max)).toFixed(3);
      const extRows = extensions.map((p, i) => `<li class="ss-bar-row ss-ext-row" style="--i:${i}">${who(p)}${ratingNumber(p.overall)}
          <span class="ss-pair-bars"><span class="ss-hbar"><i class="ss-hbar-now" style="--share:${share(p.salary_millions, extMax)}"></i><em>${contract(p.salary_millions, p.years_left)}</em></span>
          <span class="ss-hbar"><i class="ss-hbar-next" style="--share:${share(p.projected_millions, extMax)}"></i><em>${p.projected_millions ? contract(p.projected_millions, p.projected_years) : "—"}</em></span></span></li>`).join("");
      const left = `<section class="ss-panel ss-panel-ext">${panelTitle("Your extension candidates", extensions.length ? `<span class="ss-bar-key"><span><i class="ss-hbar-now"></i>Now</span><span><i class="ss-hbar-next"></i>Projected extension</span></span>` : "")}
          ${extensions.length ? `<ol class="ss-bar-list">${extRows}</ol>` : `<p class="ss-panel-empty">No one on your team is eligible for an extension.</p>`}</section>`;
      // Players who could be on the move (the front offices' trade block), grouped by the main reason; each bar is
      // his salary, coloured by his rating, so a long red bar is an expensive, lower-rated player.
      const movers = slide.movers || [];
      const list = movers.length ? movers : (slide.expiring || []);
      const max = Math.max(1, ...list.map((p) => Number(p.salary_millions) || 0));
      const moverRow = (p, i, scale = max) => `<li class="ss-bar-row ss-move-row" style="--i:${i}">${who(p)}${teamCell(p.team)}${ratingNumber(p.overall)}
          <span class="ss-hbar"><i style="--share:${share(p.salary_millions, scale)};background-color:${Number.isFinite(Number(p.overall)) ? ratingColor(p.overall) : "#8a97a3"}"></i><em>${contract(p.salary_millions, p.years_left)}</em></span></li>`;
      let body;
      if (movers.length) {
        const groups = [];
        movers.forEach((p) => { const key = p.reason || "Other"; let g = groups.find((x) => x.key === key); if (!g) groups.push(g = {key, rows: []}); g.rows.push(p); });
        let i = 0;
        body = groups.map((g) => `<li class="ss-bar-group"><h5>${esc(g.key)}</h5><ol class="ss-bar-list">${g.rows.map((p) => moverRow(p, i++)).join("")}</ol></li>`).join("");
        body = `<ol class="ss-bar-groups">${body}</ol>`;
      } else {
        body = list.length ? `<ol class="ss-bar-list">${list.map((p, i) => moverRow(p, i)).join("")}</ol>` : `<p class="ss-panel-empty">—</p>`;
      }
      const right = `<section class="ss-panel ss-panel-movers">${panelTitle(movers.length ? "Could be on the move" : "Biggest expiring deals")}${body}</section>`;
      // With the trade block on the right, next summer's biggest expiring deals sit under your extensions.
      const expiring = movers.length ? (slide.expiring || []).slice(0, 5) : [];
      const expMax = Math.max(1, ...expiring.map((p) => Number(p.salary_millions) || 0));
      const expiringPanel = expiring.length ? `<section class="ss-panel ss-panel-expiring">${panelTitle("Biggest expiring deals")}<ol class="ss-bar-list">${expiring.map((p, i) => moverRow(p, i + extensions.length, expMax)).join("")}</ol></section>` : "";
      return `<div class="ss-contracts${rowsIn()}"><div class="ss-contracts-left">${left}${expiringPanel}</div>${right}</div>`;
    },
    prospects(slide) {
      // Round 13: photos, school logos, the spread of the league's 30 boards (box: middle half, whiskers: every team,
      // tick: consensus, gold dot: your scouts) and how far your scouts differ from the league.
      const rows = slide.prospects || [];
      const ranks = rows.flatMap((p) => [p.consensus_worst, p.consensus_rank, p.your_rank]).map(Number).filter(Number.isFinite);
      const maxRank = Math.max(10, Math.ceil(Math.max(1, ...ranks) / 5) * 5);
      const range = (p) => typeof seasonProspectRankRange === "function" ? seasonProspectRankRange({consensusRank: p.consensus_rank, rank: p.your_rank,
        draftRangeLow: (p.consensus_middle || [])[0], draftRangeHigh: (p.consensus_middle || [])[1], consensusBest: p.consensus_best, consensusWorst: p.consensus_worst}, maxRank, "rank") : esc(p.consensus_rank);
      const yours = (p) => {
        if (!p.your_rank) return "—";
        const diff = Number(p.consensus_rank) - Number(p.your_rank);
        const tag = Number.isFinite(diff) && diff ? `<small class="ss-rank-diff ${diff > 0 ? "is-up" : "is-down"}" title="${attr(diff > 0 ? `Your scouts rank him ${diff} higher than the league` : `Your scouts rank him ${-diff} lower than the league`)}">${diff > 0 ? "▲" : "▼"}${Math.abs(diff)}</small>` : "";
        return `<span class="ss-your-rank"><b>#${esc(p.your_rank)}</b>${tag}</span>`;
      };
      const school = (p) => `<span class="ss-school">${typeof prospectOriginMarkup === "function" ? prospectOriginMarkup(p.school) : ""}<span>${esc(p.school || "—")}</span></span>`;
      const scouted = (p) => {
        if (p.scouted_pct === null || p.scouted_pct === undefined) return "—";
        const pct = Math.max(0, Math.min(100, Number(p.scouted_pct)));
        return `<span class="ss-scouted"><i><b style="width:${pct.toFixed(0)}%"></b></i><strong>${num(pct, 0)}%</strong></span>`;
      };
      return `<div class="ss-prospects">${table([
        {label: "#", render: (p) => p.consensus_rank, cls: "ss-num"},
        {label: "Prospect", render: (p) => playerCell(p, esc([p.position, p.age ? `${num(p.age, 0)}` : ""].filter(Boolean).join(" · "))), cls: "ss-left"},
        {label: "From", render: school, cls: "ss-left"},
        {label: "League boards", render: range, cls: "ss-left ss-range-col"},
        {label: "Your scouts", render: yours, cls: "ss-num"},
        {label: "Scouted", render: scouted, cls: "ss-left"},
      ], rows, {sorted: 0})}<div class="season-prospect-legend ss-range-legend"><span><i class="is-box"></i>Middle half of teams</span><span><i class="is-whisker"></i>Every team</span><span><i class="is-median"></i>League consensus</span><span><i class="season-prospect-ours-key"></i>Your scouts</span></div></div>` + (slide.projected_pick ? `<p class="ss-lead">Your pick projects around No. ${esc(slide.projected_pick)} on current strength.</p>` : "");
    },
    storylines(slide) {
      // Round 13: each story with its team's logo, the players in it and one headline number.
      const story = (item) => {
        const faces = (item.players || []).filter((p) => p && p.name).map((p) => `<span class="ss-story-face" title="${attr(p.name)}">${headshot(p)}</span>`).join("");
        const stat = item.stat && item.stat.value !== null && item.stat.value !== undefined ? `<div class="ss-story-stat${item.stat.tone === "bad" ? " is-bad" : ""}"><b>${esc(item.stat.value)}</b><small>${esc(item.stat.label || "")}</small></div>` : "";
        return `<section class="ss-story ss-story-rich">${item.team?.abbrev ? logo(item.team.abbrev, "ss-story-logo") : ""}<div class="ss-story-body"><h4>${esc(item.title)}</h4><p>${esc(item.text)}</p>${faces ? `<div class="ss-story-faces">${faces}</div>` : ""}</div>${stat}</section>`;
      };
      return `<div class="ss-stories ss-stories-rich">${(slide.items || []).slice(0, bySize(12, 15, 15)).map(story).join("") || `<p class="ss-empty">A quiet summer.</p>`}</div>`;
    },
    injuries(slide) {
      if (!(slide.players || []).length) return `<p class="ss-empty">No rated player starts the season with an absence of more than 20 games.</p>`;
      // Round 13: a team logo, the injury in the team-coloured accent and the games missed as the headline number; text
      // wraps inside its card.
      return `<div class="ss-stories ss-stories-rich ss-injuries">${slide.players.slice(0, 15).map((p) => `<section class="ss-story ss-story-rich ss-injury-card">${p.team?.abbrev ? logo(p.team.abbrev, "ss-story-logo") : ""}<div class="ss-story-body">${playerCell(p, esc(`${p.team?.abbrev || ""} · ${num(p.overall)} rating`))}
        <p><b class="ss-injury-name">${esc(capitalize(p.injury || "injury"))}</b>${p.part ? ` (${esc(p.part)})` : ""}</p><p>${p.return_date ? `Back around ${esc(shortDate(p.return_date))}.` : ""}</p></div><div class="ss-story-stat is-bad"><b>${p.whole_season ? "Season" : esc(p.games)}</b><small>${p.whole_season ? "out" : "games out"}</small></div></section>`).join("")}</div>`;
    },
  };

  // Pages layout (branch sidebar-pages): the slideshow fills the page area and the sidebar stays usable, so only the
  // page sheet goes inert; the board keeps the whole app inert as before.
  function setAppInert(on) {
    const pages = document.documentElement.dataset.layout === "pages" && document.querySelector(".is-pages .pages-sheet");
    const target = pages || document.getElementById("app");
    if (on) target?.setAttribute("inert", ""); else { target?.removeAttribute("inert"); document.getElementById("app")?.removeAttribute("inert"); }
  }

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
          <div class="ss-title-row"><h2 id="ssTitle"${slide.logo ? ` class="ss-title-team" aria-label="${attr(slide.title || "")}"` : ""}>${slide.logo ? titleTeam(slide) : esc(slide.title || "")}</h2>
            ${slide.note ? `<span class="ss-info"><i class="g-info" tabindex="0" aria-label="${attr(slide.note)}">i</i><span class="ss-info-tip" aria-hidden="true">${esc(slide.note)}</span></span>` : ""}</div>
          <div class="ss-body">${slideBody(slide)}</div>
        </div>
        <footer class="game-tutorial-actions ss-actions">
          <button type="button" class="game-tutorial-skip" data-ss-action="skip">${esc(SKIP_LABEL[data.kind] || "Skip")}</button>
          <div class="ss-dots" aria-hidden="true">${slides.map((_, i) => `<i class="${i === index ? "on" : ""}"></i>`).join("")}</div>
          <div class="game-tutorial-arrows">
            <button type="button" class="game-tutorial-arrow" data-ss-action="previous" aria-label="Previous slide" title="Previous slide" ${index === 0 ? "disabled" : ""}><svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M13 8H3M7 4L3 8l4 4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
            <button type="button" class="game-tutorial-arrow" data-ss-action="next" aria-label="${last ? "Finish" : "Next slide"}" title="${last ? "Finish" : "Next slide"}">${last ? '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3 8.5l3.2 3.2L13 4.8" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>' : '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>'}</button>
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
    show.viewAll = null;
    render(step);
  }

  // Player cards live on the board behind the slideshow: step the slideshow aside, open the card, and offer a way
  // back to the same slide (playtest 2026-11-22).
  function openPlayer(playerId) {
    if (!playerId || typeof dashboardPlayerCard !== "function") return;
    show.suspended = true;
    show.root.hidden = true;
    setAppInert(false);
    document.body.classList.remove("season-slideshow-open");
    let back = document.getElementById("ssReturn");
    if (!back) {
      back = document.createElement("button");
      back.type = "button"; back.id = "ssReturn"; back.className = "ss-return";
      back.addEventListener("click", resume);
      document.body.appendChild(back);
    }
    back.textContent = `← Back to ${KIND_TITLE[show.data?.kind] || "slideshow"}`;
    dashboardPlayerCard(playerId);
  }

  function resume() {
    document.getElementById("ssReturn")?.remove();
    if (!show.open || !show.suspended) return;
    show.suspended = false;
    show.root.hidden = false;
    setAppInert(true);
    document.body.classList.add("season-slideshow-open");
    show.root.querySelector(".ss-card")?.focus({preventScroll: true});
  }

  function close() {
    if (!show.open) return;
    show.open = false;
    show.suspended = false;
    document.getElementById("ssReturn")?.remove();
    show.root.hidden = true;
    show.root.innerHTML = "";
    setAppInert(false);
    document.body.classList.remove("season-slideshow-open");
    const focus = show.returnFocus;
    show.returnFocus = null;
    if (focus?.isConnected && !focus.disabled) focus.focus({preventScroll: true});
    window.dispatchEvent(new CustomEvent("season-slideshow-closed"));
  }

  function keydown(event) {
    if (!show.open || show.suspended) return;
    const root = show.root;
    if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); if (show.viewAll) { show.viewAll = null; return render(0); } return close(); }
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
    setAppInert(true);
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
      const playerLink = event.target.closest("[data-ss-player]") || event.target.closest("[data-ss-tile-player]");
      if (playerLink) return openPlayer(playerLink.dataset.ssPlayer || playerLink.dataset.ssTilePlayer);
      const viewAll = event.target.closest("[data-ss-view-all]");
      if (viewAll) { show.viewAll = viewAll.dataset.ssViewAll || null; render(0); return; }
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
