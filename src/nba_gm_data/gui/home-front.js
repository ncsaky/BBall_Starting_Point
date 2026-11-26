/* Home › Today as a front page (UI polish pass, 2026-11-26; user: "the homepage just shows a couple tables. It should
   show stuff that would be most engaging to a player like the trade market, any ongoing trade rumors, standings,
   things going against expectation, league leaders, winners, the state of your team, injuries, signings, whatever
   deadlines are coming up").

   One page, read top to bottom: your team right now (last result, next game, form, morale, who is out), then three
   columns: the league (headlines, last night's scores), the table (your conference, teams beating or missing what
   their roster suggests) and the market (offers to you, players being shopped, the stat leaders, what is coming up).
   Everything shown is data the game already holds; nothing is invented here:
     state.data.statusDashboard   record, last_games, next_games, health_summary, rotation
     state.data.dashboardStandings, dashboardSummaryLeaders, dashboardMorale, dashboardCalendar, dashboardOffers
     state.data.dashboardTrends.roster_ranks   every team's roster rating rank (team_identity_report)
     state.home.league_events, the trade_market action (loaded once a game day)
   Every line opens the place it summarises (a box score, a player card, a tab, the trade room). */
(() => {
  "use strict";
  const app = () => (typeof state !== "undefined" ? state : null);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  // app.js's functions are declared at the top level of a classic script, so they are reachable as globals.
  const call = (name, ...args) => { try { return typeof globalThis[name] === "function" ? globalThis[name](...args) : undefined; } catch { return undefined; } };
  const abbrevOf = (team) => String(team?.abbrev || team || "").replace(/^team_/, "").toUpperCase();
  const logo = (team) => call("teamLogoSrc", abbrevOf(team)) || "";
  const logoImg = (team, cls = "front-logo") => (logo(team) ? `<img class="${cls}" src="${esc(logo(team))}" alt="" loading="lazy" decoding="async">` : "");
  const shortDate = (iso) => call("formatDashboardShortDate", iso) || String(iso || "");
  const ordinal = (n) => { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };
  const daysBetween = (from, to) => Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000);

  // ---------- The table: seeds, games behind, and where a record stands against the roster's rating.
  function table(st) {
    const rows = (st?.data?.dashboardStandings?.standings || []).map((row) => ({
      abbrev: abbrevOf(row.team_abbrev || row.team), id: row.team_id || row.team?.id || "", conference: row.team?.conference || "",
      wins: Number(row.wins || 0), losses: Number(row.losses || 0), pct: Number(row.win_pct || 0), diff: Number(row.point_diff || 0), games: Number(row.games || 0),
    }));
    const order = (a, b) => b.pct - a.pct || b.diff - a.diff || a.abbrev.localeCompare(b.abbrev);
    const league = [...rows].sort(order);
    league.forEach((row, index) => { row.leagueRank = index + 1; });
    for (const conference of new Set(rows.map((row) => row.conference))) {
      const group = league.filter((row) => row.conference === conference);
      group.forEach((row, index) => { row.seed = index + 1; row.behind = ((group[0].wins - row.wins) + (row.losses - group[0].losses)) / 2; });
    }
    return league;
  }

  // Teams whose record sits furthest from their roster's rating rank (both are league ranks, 1 to 30).
  function surprises(st, league) {
    const rosterRank = new Map((st?.data?.dashboardTrends?.roster_ranks || []).map((row) => [String(row.team_id), Number(row.rank)]));
    const rated = league.filter((row) => row.games >= 10 && rosterRank.get(row.id) > 0).map((row) => ({...row, roster: rosterRank.get(row.id), gap: rosterRank.get(row.id) - row.leagueRank}));
    const over = rated.filter((row) => row.gap >= 4).sort((a, b) => b.gap - a.gap).slice(0, 3);
    const under = rated.filter((row) => row.gap <= -4).sort((a, b) => a.gap - b.gap).slice(0, 3);
    return {over, under};
  }

  // ---------- Your team, right now.
  function hero(st, league, mine) {
    const dash = st?.data?.statusDashboard || st?.data?.dashboard || {};
    const me = league.find((row) => row.abbrev === mine);
    const games = dash.last_games || [];
    const last = games[0];
    const next = (dash.next_games || [])[0];
    const rival = (abbrev) => league.find((row) => row.abbrev === abbrevOf(abbrev));
    const standing = (row) => (row ? `${row.wins}–${row.losses} · ${ordinal(row.seed)} in the ${esc(row.conference)}` : "");
    const lastBlock = last ? `<button type="button" class="front-game" ${last.game_id ? `data-front-box="${esc(last.game_id)}"` : "disabled"}>
        <small>Last game · ${esc(shortDate(last.date))}</small>
        <span class="front-score"><b class="${last.result === "W" ? "front-win" : "front-loss"}">${last.result === "W" ? "Won" : "Lost"}</b> ${Number(last.points)}–${Number(last.opponent_points)}</span>
        <span class="front-versus">${last.is_home ? "vs" : "at"} ${logoImg(last.opponent_team_id)} ${esc(abbrevOf(last.opponent_team_id))}</span>
      </button>` : "";
    const nextRow = next ? rival(next.opponent_team) : null;
    const nextBlock = next ? `<button type="button" class="front-game" data-front-go="schedule">
        <small>Next game · ${esc(shortDate(next.date))}</small>
        <span class="front-score">${next.is_home ? "vs" : "at"} ${logoImg(next.opponent_team)}${esc(abbrevOf(next.opponent_team))}</span>
        <span class="front-versus">${standing(nextRow)}</span>
      </button>` : "";
    const form = games.slice(0, 5).reverse();
    const formBlock = form.length ? `<div class="front-form"><small>Last ${form.length}</small><span>${form.map((game) => `<i class="${game.result === "W" ? "front-win" : "front-loss"}" title="${esc(`${shortDate(game.date)}: ${game.result} ${game.points}–${game.opponent_points} ${game.is_home ? "vs" : "at"} ${abbrevOf(game.opponent_team_id)}`)}">${esc(game.result || "")}</i>`).join("")}</span></div>` : "";

    const morale = st?.data?.dashboardMorale || {};
    const number = (value) => Number(value?.overall ?? value);
    const players = (morale.players || []).map((item) => number(item.morale)).filter(Number.isFinite);
    const meters = [
      ["Locker room", players.length ? players.reduce((sum, value) => sum + value, 0) / players.length : NaN],
      ["Coach trust", number(morale.team_morale)],
      ["Owner", number(morale.owner_confidence)],
      ["Fans", number(morale.fan_confidence)],
    ].filter(([, value]) => Number.isFinite(value));
    const tone = (value) => (value >= 67 ? "is-good" : value >= 45 ? "is-mid" : "is-bad");
    const meterBlock = meters.length ? `<button type="button" class="front-meters" data-front-go="identity">${meters.map(([label, value]) => `<span class="front-meter ${tone(value)}"><small>${label}</small><b>${Math.round(value)}</b><i><u style="width:${Math.max(4, Math.min(100, value)).toFixed(0)}%"></u></i></span>`).join("")}</button>` : "";

    const out = new Set(dash.health_summary?.unavailable_player_ids || []);
    const hurt = (dash.rotation || []).filter((row) => out.has(row.id));
    const hurtBlock = `<div class="front-out"><small>${hurt.length ? `${hurt.length} out` : "Injuries"}</small><span>${hurt.length
      ? hurt.slice(0, 4).map((row) => `<button type="button" data-front-player="${esc(row.id)}">${esc(row.name)}</button>`).join("") + (hurt.length > 4 ? `<em>+${hurt.length - 4} more</em>` : "")
      : "<em>Everyone is available</em>"}</span></div>`;
    return `<header class="front-hero">${lastBlock}${nextBlock}${formBlock}${meterBlock}${hurtBlock}</header>`;
  }

  // ---------- The league: headlines, then the latest day's scores.
  function headlines(st, mine) {
    const events = (st?.home?.league_events?.events || []).slice(0, 12).map((event) => {
      const normal = call("normalizeLeagueEvent", event) || {date: event.date, kind: event.kind, text: event.headline, teams: []};
      return {id: String(event.id || ""), date: normal.date || "", kind: normal.kind || "", teams: normal.teams || [],
        text: String(event.activity_headline || normal.text || event.headline || "").replace(/\.\.$/, ".")};
    });
    const kind = (value) => globalThis.NewsPage?.kindLabel?.(value) || String(value || "News");
    return `<section class="front-block front-news"><h2><button type="button" data-front-go="news">Around the league</button></h2>
      <div class="front-list front-headlines">${events.map((row) => `<button type="button" class="front-headline${row.teams.includes(mine) ? " is-mine" : ""}" data-front-go="news" data-front-news="${esc(row.id)}">
        <span class="front-headline-meta"><time>${esc(shortDate(row.date))}</time><i>${esc(kind(row.kind))}</i><span>${row.teams.slice(0, 3).map((team) => logoImg(team)).join("")}</span></span>
        <b>${esc(row.text)}</b></button>`).join("") || `<p class="front-none">No league news yet.</p>`}</div></section>`;
  }

  function scores(st, mine) {
    const today = String(st?.home?.save?.current_date || "");
    const played = (st?.data?.dashboardCalendar?.games || []).filter((game) => game.status === "simulated" && game.home_score != null && (!today || game.date <= today));
    const day = played.map((game) => game.date).sort().at(-1);
    const games = played.filter((game) => game.date === day);
    if (!games.length) return "";
    const side = (abbrev, points, won) => `<span class="${won ? "front-top" : ""}${abbrevOf(abbrev) === mine ? " is-mine" : ""}">${logoImg(abbrev)}<em>${esc(abbrevOf(abbrev))}</em><b>${Number(points)}</b></span>`;
    return `<section class="front-block front-scores-block"><h2>Scores <small>${esc(shortDate(day))}</small></h2>
      <div class="front-list front-scores">${games.map((game) => `<button type="button" class="front-scoreline" ${game.game_id ? `data-front-box="${esc(game.game_id)}"` : "disabled"}>
        ${side(game.away_team, game.away_score, Number(game.away_score) > Number(game.home_score))}${side(game.home_team, game.home_score, Number(game.home_score) > Number(game.away_score))}${Number(game.overtime_periods) ? "<small>OT</small>" : ""}</button>`).join("")}</div></section>`;
  }

  // ---------- The table: your conference, then who is beating or missing what their roster suggests.
  function standings(league, mine) {
    const me = league.find((row) => row.abbrev === mine);
    const group = league.filter((row) => row.conference === (me?.conference || league[0]?.conference));
    if (!group.length) return "";
    return `<section class="front-block front-table"><h2><button type="button" data-front-go="standings">${esc(me?.conference || "Standings")}</button></h2>
      <div class="front-list front-standings" style="--front-count:${group.length}">${group.map((row) => `<div class="front-standing${row.abbrev === mine ? " is-mine" : ""}${row.seed === 6 || row.seed === 10 ? " is-cut" : ""}">
        <i>${row.seed}</i>${logoImg(row.abbrev)}<b>${esc(row.abbrev)}</b><span>${row.wins}–${row.losses}</span><em>${row.behind ? row.behind.toFixed(1).replace(/\.0$/, "") : "–"}</em></div>`).join("")}</div></section>`;
  }

  // The games ahead (shown where there is no table yet).
  function comingUp(st, league) {
    const games = (st?.data?.statusDashboard?.next_games || []).slice(0, 8);
    if (!games.length) return "";
    return `<section class="front-block front-ahead"><h2><button type="button" data-front-go="schedule">Coming up</button></h2>
      <div class="front-list front-aheads">${games.map((game) => {
        const rival = league.find((row) => row.abbrev === abbrevOf(game.opponent_team));
        return `<div class="front-aheadline"><time>${esc(shortDate(game.date))}</time><span>${game.is_home ? "vs" : "at"}</span>${logoImg(game.opponent_team)}<b>${esc(abbrevOf(game.opponent_team))}</b><em>${rival && rival.games ? `${rival.wins}–${rival.losses}` : ""}</em></div>`;
      }).join("")}</div></section>`;
  }

  function expectation(found) {
    if (!found.over.length && !found.under.length) return "";
    const line = (row, up) => `<div class="front-surprise ${up ? "front-up" : "front-down"}">${logoImg(row.abbrev)}<b>${esc(row.abbrev)}</b><span><i aria-hidden="true">${up ? "▲" : "▼"}</i>${ordinal(row.leagueRank)} by record</span><em>${ordinal(row.roster)} by roster</em></div>`;
    return `<section class="front-block front-expect"><h2>Against expectation</h2>
      <div class="front-list front-surprises">${found.over.map((row) => line(row, true)).join("")}${found.under.map((row) => line(row, false)).join("")}</div></section>`;
  }

  // ---------- The market: offers to you, who is being shopped, the leaders, what is coming up.
  let marketDay = "";
  function marketRows(st) {
    const rows = st?.data?.tradeMarket?.shopped || [];
    return rows.slice(0, 8).map((row) => {
      const stage = row.stage === "bidding war" ? "Bidding war" : row.stage === "sold" ? `Sold to ${row.sold_to || "another team"}` : `${Number(row.interested_count || 0)} team${Number(row.interested_count) === 1 ? "" : "s"} interested`;
      return `<button type="button" class="front-shop" data-front-market>
        ${call("playerHeadshotMarkup", row, "front-face-img") || `<span class="player-headshot-frame">${logoImg(row.team)}</span>`}
        <b>${esc(row.player_name)}${row.overall != null ? ` <i>${Math.round(Number(row.overall))}</i>` : ""}</b><span>${logoImg(row.team)}${esc(abbrevOf(row.team))}</span>
        <em class="${row.stage === "bidding war" ? "front-hot" : ""}">${esc(stage)}</em></button>`;
    }).join("");
  }
  function market(st) {
    const offers = Number(st?.data?.dashboardOffers?.offer_count ?? st?.home?.save?.pending_counts?.user_trade_offers ?? 0);
    const loaded = Boolean(st?.data?.tradeMarket);
    const deadline = call("tradeDeadlineDate") || "";
    const today = String(st?.home?.save?.current_date || "");
    const left = deadline && today ? daysBetween(today, deadline) : NaN;
    const clock = Number.isFinite(left) && left >= 0 ? `<small>${left === 0 ? "Deadline today" : `${left} day${left === 1 ? "" : "s"} to the deadline`}</small>` : "";
    return `<section class="front-block front-market"><h2><button type="button" data-front-market>Trade talk</button> ${clock}</h2>
      ${offers ? `<button type="button" class="front-offers" data-front-offers><b>${offers}</b> offer${offers === 1 ? "" : "s"} waiting for your answer</button>` : ""}
      <div class="front-list front-shops" data-front-shops>${loaded ? marketRows(st) || `<p class="front-none">Nobody is being shopped right now.</p>` : `<p class="front-none">Checking the market…</p>`}</div></section>`;
  }

  function leaders(st) {
    const board = st?.data?.dashboardSummaryLeaders || {};
    const faces = new Map();
    for (const race of Object.values(board.award_races || {})) for (const row of race || []) if (row.headshot_url) faces.set(row.player_id, row.headshot_url);
    for (const row of st?.data?.tradeMarket?.shopped || []) if (row.headshot_url) faces.set(row.player_id || row.id, row.headshot_url);
    for (const row of st?.data?.statusDashboard?.rotation || []) if (row.headshot_url) faces.set(row.id, row.headshot_url);
    const want = [["points", "PTS"], ["rebounds", "REB"], ["assists", "AST"]];
    const lines = want.map(([key, label]) => {
      const field = (board.fields || []).find((item) => item.key === key || item.label === label);
      const top = field?.leaders || [];
      if (!top.length) return "";
      const lead = top[0];
      const face = lead.headshot_url || faces.get(lead.player_id);
      const value = (row) => Number(row.value).toFixed(1);
      return `<div class="front-leader"><small>${label}</small>
        <button type="button" data-front-player="${esc(lead.player_id)}"><span class="front-face">${face ? `<img src="${esc(face)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : logoImg(lead.team_abbrev)}</span><b>${esc(lead.player_name)}</b><i>${value(lead)}</i></button>
        ${top[1] ? `<span>${esc(String(top[1].player_name).split(" ").slice(1).join(" ") || top[1].player_name)} <i>${value(top[1])}</i></span>` : "<span></span>"}</div>`;
    }).join("");
    return lines ? `<section class="front-block front-leaders"><h2><button type="button" data-front-go="awards">Leaders</button></h2><div class="front-list">${lines}</div></section>` : "";
  }

  function markup() {
    const st = app();
    if (!st?.home?.save) return "";
    const mine = abbrevOf(st.home.save.user_team?.abbrev || call("userTeam") || "");
    const league = table(st);
    // Before the season and in the playoffs the game loads no standings, scores or leaders for this page: the
    // middle column then lists the games ahead, or is left out.
    const middle = standings(league, mine) + expectation(surprises(st, league)) || comingUp(st, league);
    const cols = [headlines(st, mine) + scores(st, mine), middle, market(st) + leaders(st)].filter(Boolean);
    return `<div class="front">
      ${hero(st, league, mine)}
      <div class="front-cols" data-front-cols="${cols.length}">${cols.map((col) => `<div class="front-col">${col}</div>`).join("")}</div>
    </div>`;
  }

  // The market is its own request: ask once a game day, when the front page is on screen, and fill its list in.
  function refreshMarket() {
    const st = app();
    const list = typeof document !== "undefined" ? document.querySelector("[data-front-shops]") : null;
    if (!st?.home?.save || !list) return;
    const day = `${st.currentSave || ""}|${st.home.save.current_date || ""}`;
    if (marketDay === day) return;
    marketDay = day;
    Promise.resolve(call("loadTradeMarket", true)).then(() => {
      const target = document.querySelector("[data-front-shops]");
      if (target && app()?.data?.tradeMarket) target.innerHTML = marketRows(app()) || `<p class="front-none">Nobody is being shopped right now.</p>`;
    }).catch(() => { marketDay = ""; });
  }

  if (typeof document !== "undefined") {
    document.addEventListener("click", (event) => {
      const hit = (name) => event.target.closest?.(`.front [${name}]`);
      const box = hit("data-front-box");
      if (box) { call("openBoxScore", box.dataset.frontBox); return; }
      const player = hit("data-front-player");
      if (player) { call("dashboardPlayerCard", player.dataset.frontPlayer); return; }
      if (hit("data-front-offers")) { Promise.resolve(call("openTradeOffersModal")).catch(() => {}); return; }
      if (hit("data-front-market")) { Promise.resolve(call("openTradeMarketBoard")).catch(() => {}); return; }
      const go = hit("data-front-go");
      if (go) globalThis.CardPages?.go?.(go.dataset.frontGo);
    });
    let frame = 0;
    const watch = new MutationObserver(() => { cancelAnimationFrame(frame); frame = requestAnimationFrame(refreshMarket); });
    const start = () => watch.observe(document.body, {childList: true, subtree: true});
    if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
  }

  if (typeof window !== "undefined") window.HomeFront = Object.freeze({markup, table, surprises});
})();
