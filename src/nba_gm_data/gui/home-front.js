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
    if (!offseason(st)) return `<header class="front-hero">${lastBlock}${nextBlock}${formBlock}${meterBlock}${hurtBlock}</header>`;
    // From the lottery to camp there are no results to lead with: the payroll, the room under the lines and the
    // roster do (the same numbers Front Office > Contracts shows).
    const cap = dash.cap_summary || {};
    const money = (value) => `$${Math.abs(Number(value)).toFixed(1)}M`;
    const has = (value) => value !== null && value !== undefined && Number.isFinite(Number(value));
    const figure = (label, big, foot, tone = "") => `<button type="button" class="front-game front-figure" data-front-go="contracts"><small>${label}</small><span class="front-score">${big}</span><span class="front-versus ${tone}">${foot}</span></button>`;
    const blocks = [];
    if (has(cap.salary_total_millions)) blocks.push(figure("Payroll", money(cap.salary_total_millions), has(cap.tax_space_millions) ? `${money(cap.tax_space_millions)} ${Number(cap.tax_space_millions) >= 0 ? "under" : "over"} the tax line` : "", Number(cap.tax_space_millions) < 0 ? "front-loss" : ""));
    if (has(cap.cap_room_millions)) blocks.push(figure("Cap room", Number(cap.cap_room_millions) > 0 ? money(cap.cap_room_millions) : "None", has(cap.hard_cap_space_millions) ? `${money(cap.hard_cap_space_millions)} ${Number(cap.hard_cap_space_millions) >= 0 ? "under" : "over"} the hard cap` : ""));
    const roster = (dash.rotation || []).length;
    const open = Number(cap.ledger?.empty_roster_spots);
    if (roster) blocks.push(figure("Roster", `${roster} players`, Number.isFinite(open) ? (open > 0 ? `${open} open spot${open === 1 ? "" : "s"}` : "Full") : ""));
    return `<header class="front-hero is-offseason">${blocks.join("")}${nextBlock}${meterBlock}${hurtBlock}</header>`;
  }

  // No games are played from the lottery to training camp (progress.js knows the phases).
  function offseason(st) {
    const phase = String(st?.home?.save?.phase || "");
    return Boolean(phase) && typeof window !== "undefined" && window.GameProgress?.PHASES?.[phase]?.games === false;
  }

  // Your players who can sign an extension now (the same flag the Contracts table marks).
  function eligible(st) {
    const dash = st?.data?.statusDashboard || {};
    const rows = (dash.rotation || []).filter((row) => row.extension_eligible);
    if (!rows.length) return "";
    const left = (row) => Object.values(row.salary_by_year || {}).filter((value) => Number(value) > 0).length;
    return `<section class="front-block front-eligible"><h2><button type="button" data-front-go="contracts">Can be extended</button></h2>
      <div class="front-list front-movelist">${rows.slice(0, 10).map((row) => `<button type="button" class="front-move" data-front-player="${esc(row.id)}">
        <span class="front-face">${row.headshot_url ? `<img src="${esc(row.headshot_url)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ""}</span>
        <b>${esc(row.name)}</b><span></span><i>${left(row) ? `${left(row)} year${left(row) === 1 ? "" : "s"} left` : ""}</i></button>`).join("")}</div></section>`;
  }

  // The summer's biggest signatures: extensions and free-agent deals, largest first (the same league events as the news).
  function moves(st) {
    const rows = [];
    for (const event of st?.home?.league_events?.events || []) {
      const details = event.details || {};
      const signed = event.kind === "free_agent_signing" || event.kind === "free_agency_signing";
      if (!(signed || (event.kind === "extension" && (details.annual_salary || details.contract)))) continue;
      const subject = (event.activity_groups || []).flatMap((group) => group.subjects || []).find((item) => item.id === (details.player_id || (event.player_ids || [])[0])) || {};
      const yearly = Number(details.aav_millions) || Number(details.annual_salary) / 1e6 || 0;
      const years = Number(details.years || details.contract?.years || 0);
      if (!subject.name || !yearly) continue;
      rows.push({id: subject.id, name: subject.name, face: subject.headshot_url || "", team: abbrevOf(details.team_id || (event.team_ids || [])[0]), kind: signed ? "Signed" : "Extended", yearly, years, date: event.date});
    }
    if (!rows.length) return "";
    rows.sort((a, b) => b.yearly * Math.max(1, b.years) - a.yearly * Math.max(1, a.years));
    return `<section class="front-block front-moves"><h2><button type="button" data-front-go="news">Biggest deals</button></h2>
      <div class="front-list front-movelist">${rows.slice(0, 14).map((row) => `<button type="button" class="front-move" data-front-player="${esc(row.id)}" title="${esc(`${shortDate(row.date)}: ${row.kind === "Signed" ? "signed with" : "extended by"} ${row.team}`)}">
        <span class="front-face">${row.face ? `<img src="${esc(row.face)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : logoImg(row.team)}</span>
        <b>${esc(row.name)}</b><span title="${esc(`${row.kind === "Signed" ? "Signed with" : "Extended by"} ${row.team}`)}">${logoImg(row.team)}</span><i>$${row.yearly.toFixed(1)}M${row.years ? ` × ${row.years}` : ""}</i></button>`).join("")}</div></section>`;
  }

  // ---------- Storylines (user, 2026-11-26: "it is fun to follow a narrative and see its conclusion ... we have those
  // events happening and panning out, but nothing really watching them"). A storyline is a thread of things the game
  // already recorded about one person or one job, in date order: a player whose extension talks stalled, who asked
  // out, who is being shopped, who was traded or signed; a coach fired and the hire that followed; an award race
  // changing hands; a player of yours who is unhappy right now. Nothing is predicted and no step is invented: every
  // step is a stored league event, a row of the trade market, the award race's weekly ranks or today's morale.
  function storylines(st, mine) {
    const events = [...(st?.home?.league_events?.events || [])].filter((event) => event && event.date).sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const people = new Map();
    for (const event of events) for (const group of event.activity_groups || []) for (const subject of group.subjects || []) {
      if (subject?.id && !people.has(subject.id)) people.set(subject.id, subject);
    }
    const today = String(st?.home?.save?.current_date || "");
    const threads = new Map();
    const thread = (key, seed) => { if (!threads.has(key)) threads.set(key, {key, steps: [], ...seed}); return threads.get(key); };
    const team = (id) => abbrevOf(id);
    // 1. Players: talks stall or he asks out (the start), the market (the middle), a trade or a signature (the end).
    for (const event of events) {
      const details = event.details || {};
      const id = details.player_id || (event.player_ids || [])[0];
      if (event.kind === "trade_demand" && id) {
        thread(`player:${id}`, {kind: "player", id, team: team(details.team_id || (event.team_ids || [])[0])}).steps.push({type: "demand", date: event.date, text: `Asked out of ${team(details.team_id || (event.team_ids || [])[0])}`});
      } else if (event.kind === "extension" && id && !details.annual_salary && !details.contract) {
        const club = team(details.team_id || (event.team_ids || [])[0]);
        thread(`player:${id}`, {kind: "player", id, team: club}).steps.push({type: "stalled", date: event.date, text: details.team_passed_on_extension ? `${club} passed on an extension` : `Extension talks with ${club} stalled`});
      }
    }
    for (const row of st?.data?.tradeMarket?.shopped || []) {
      const id = row.player_id;
      if (!id) continue;
      const entry = thread(`player:${id}`, {kind: "player", id, team: abbrevOf(row.team)});
      entry.name ||= row.player_name; entry.face ||= row.headshot_url; entry.team = abbrevOf(row.team) || entry.team;
      const count = Number(row.interested_count || 0);
      entry.steps.push({type: row.stage === "bidding war" ? "bidding" : "market", date: row.started || "", text: row.stage === "bidding war" ? `Bidding war, ${count} team${count === 1 ? "" : "s"}` : `On the market, ${count} team${count === 1 ? "" : "s"} interested`, until: row.decide_by || ""});
      if (row.stage === "sold") entry.steps.push({type: "traded", date: "", text: `Sold to ${abbrevOf(row.sold_to) || "another team"}`});
    }
    for (const event of events) {
      const details = event.details || {};
      if (event.kind === "trade") {
        const legs = details.transfers || [{from_team_id: details.from_team_id, to_team_id: details.to_team_id, assets: details.from_assets}, {from_team_id: details.to_team_id, to_team_id: details.from_team_id, assets: details.to_assets}];
        for (const leg of legs) for (const asset of leg.assets || []) {
          const entry = asset?.kind === "player" ? threads.get(`player:${asset.id}`) : null;
          if (entry && !entry.steps.some((step) => step.type === "traded" && step.date)) {
            entry.steps = entry.steps.filter((step) => !(step.type === "traded" && !step.date));
            entry.steps.push({type: "traded", date: event.date, text: `Traded to ${team(leg.to_team_id)}`});
          }
        }
      } else if (event.kind === "extension" && (details.annual_salary || details.contract)) {
        const entry = threads.get(`player:${details.player_id || (event.player_ids || [])[0]}`);
        const years = Number(details.years || details.contract?.years || 0);
        if (entry) entry.steps.push({type: "signed", date: event.date, text: `Extended${Number(details.aav_millions) ? ` for $${Number(details.aav_millions).toFixed(1)}M${years ? ` × ${years}` : ""}` : ""}`});
      } else if (event.kind === "free_agent_signing" || event.kind === "free_agency_signing") {
        const entry = threads.get(`player:${details.player_id || (event.player_ids || [])[0]}`);
        if (entry) entry.steps.push({type: "signed", date: event.date, text: `Signed with ${team(details.team_id || (event.team_ids || [])[0])}`});
      }
    }
    // 2. Coaches: a firing, then the hire for the same job.
    for (const event of events) {
      const details = event.details || {};
      const club = team((event.team_ids || [])[0]);
      const job = String(details.slot || "").replace(/_/g, " ");
      if (!club || !job) continue;
      if (event.kind === "staff_fire") {
        const entry = thread(`staff:${club}:${details.slot}`, {kind: "staff", team: club, name: `${club} ${job}`, face: people.get(details.staff_id)?.headshot_url || ""});
        entry.steps.push({type: "fired", date: event.date, text: `Fired ${details.staff_name || "the coach"}${details.reason ? ` (${String(details.reason).replace(/\.$/, "")})` : ""}`});
      } else if (event.kind === "staff_hire" && details.action !== "retain") {
        const entry = threads.get(`staff:${club}:${details.slot}`);
        if (entry && entry.steps.some((step) => step.type === "fired" && step.date <= event.date)) entry.steps.push({type: "hired", date: event.date, text: `Hired ${details.staff_name || "a replacement"}`});
      }
    }
    // 3. An award race that changed hands this week.
    for (const [award, race] of Object.entries(st?.data?.dashboardSummaryLeaders?.award_races || {})) {
      const lead = (race || []).find((row) => Number(row.rank) === 1);
      const passed = (race || []).find((row) => Number(row.previous_week_rank) === 1 && Number(row.rank) > 1);
      if (!lead || !passed || !(Number(lead.previous_week_rank) > 1)) continue;
      threads.set(`award:${award}`, {key: `award:${award}`, kind: "award", id: lead.player_id, name: `${award} race`, face: lead.headshot_url || "", team: abbrevOf(lead.team_abbrev),
        steps: [{type: "lead", date: "", text: `${lead.player_name} took the lead from ${passed.player_name} this week`}]});
    }
    // 4. Your own room: who is unhappy today, and with what (the game keeps no history of morale, so no dates).
    const names = new Map((st?.data?.statusDashboard?.rotation || []).map((row) => [row.id, row]));
    for (const item of st?.data?.dashboardMorale?.players || []) {
      const morale = item.morale || {};
      const player = item.player || {};
      const parts = [["role_satisfaction", "his role"], ["contract_satisfaction", "his contract"], ["team_confidence", "the team's direction"]]
        .map(([key, label]) => [Number(morale[key]), label]).filter(([value]) => Number.isFinite(value)).sort((a, b) => a[0] - b[0]);
      const overall = Number(morale.overall);
      if (!player.id || !parts.length || !(overall < 45 || parts[0][0] < 38)) continue;
      const entry = thread(`player:${player.id}`, {kind: "player", id: player.id, team: mine});
      entry.name ||= player.name; entry.face ||= names.get(player.id)?.headshot_url || player.headshot_url || "";
      entry.steps.push({type: "unhappy", date: "", text: `Unhappy with ${parts[0][1]} right now (${Math.round(parts[0][0])} of 100)`});
    }
    // 5. From the home_storylines action (asked for once a game day): the trade market's own ledger, this season's
    // results, the injury log and the coaches' review numbers.
    const extra = st?.data?.homeStories || {};
    const assets = (labels) => {
      const short = (labels || []).map((label) => String(label).split(/[:;(]/)[0].trim()).filter(Boolean);
      return short.length ? `${short.slice(0, 2).join(" and ")}${short.length > 2 ? ` and ${short.length - 2} more` : ""}` : "a package";
    };
    // Trade talks come out a piece at a time (user, 2026-11-26: "they evolve by getting more and more revealing").
    // The first round is only that two teams are talking; the second names the player; the third says what is on
    // the table; then each change of the offer, a final offer, and the end: done, or broken off. A player who is
    // already publicly in play (he asked out, he is being shopped) is named from the start.
    const suitors = new Map();
    for (const talk of extra.talks || []) if (talk.player?.player_id && (talk.rounds || []).length) suitors.set(talk.player.player_id, (suitors.get(talk.player.player_id) || 0) + 1);
    const outed = new Set((extra.talks || []).filter((talk) => (talk.rounds || []).length >= 2 || (talk.status === "closed" && talk.outcome === "traded")).map((talk) => talk.player?.player_id));
    for (const talk of [...(extra.talks || [])].sort((a, b) => String(a.opened || "").localeCompare(String(b.opened || "")))) {
      const rounds = talk.rounds || [];
      const id = talk.player?.player_id;
      if (!rounds.length || !id || !talk.buyer || !talk.seller) continue;
      const done = talk.status === "closed" && talk.outcome === "traded";
      // Publicly in play already (asked out, shopped), or several teams are after him: the player is no secret.
      const known = threads.has(`player:${id}`) || (outed.has(id) && suitors.get(id) > 1);
      const named = known || outed.has(id);
      const steps = [{type: "talks", date: rounds[0].date || talk.opened || "", text: known ? `${talk.buyer} opened talks with ${talk.seller} about him` : `${talk.buyer} and ${talk.seller} opened trade talks`}];
      if (named && !known && !done && rounds[1]) steps.push({type: "target", date: rounds[1].date, text: `The talks are about ${talk.player.name}`});
      else if (known && !done && rounds[1]) steps.push({type: "talks", date: rounds[1].date, text: JSON.stringify(rounds[1].offer?.[talk.buyer] || []) !== JSON.stringify(rounds[0].offer?.[talk.buyer] || []) ? `${talk.buyer} came back with a new offer` : `${talk.buyer} and ${talk.seller} talked again`});
      let shown = "";
      rounds.forEach((round, index) => {
        const offered = JSON.stringify(round.offer?.[talk.buyer] || []);
        if (index >= 2 && offered !== shown) steps.push({type: "offer", date: round.date, text: `${talk.buyer} ${shown ? "changed its offer:" : "has offered"} ${assets(round.offer?.[talk.buyer])}`});
        if (index >= 2) shown = offered;
        for (const club of round.final_by || []) steps.push({type: "final", date: round.date, text: `${club} made a final offer`});
      });
      if (done) steps.push({type: "traded", date: talk.closed_date || "", text: `Done: ${talk.player.name} to ${talk.buyer}`});
      else if (talk.status === "dead") steps.push({type: "collapsed", date: talk.ended?.date || "", text: talk.ended?.final_by?.length ? `Talks broke off: ${talk.ended.final_by[0]}'s final offer was refused` : talk.ended?.cancelled ? `Talks broke off: ${talk.ended.cancelled}` : "Talks broke off"});
      else if (talk.outcome === "player_moved") steps.push({type: "collapsed", date: talk.closed_date || "", text: "He was traded elsewhere"});
      const entry = named
        ? thread(`player:${id}`, {kind: "player", id, team: talk.seller})
        : thread(`talks:${talk.key}`, {kind: "talks", name: `${talk.buyer} and ${talk.seller}`, team: talk.buyer});
      if (named) { entry.name ||= talk.player.name; entry.face ||= talk.player.headshot_url || ""; }
      // A step another negotiation already told (he was traded) is not repeated.
      for (const step of steps) if (!entry.steps.some((item) => item.type === step.type && item.date === step.date && item.text === step.text) && !(step.type === "traded" && entry.steps.some((item) => item.type === "traded"))) entry.steps.push(step);
    }
    // A sale in the open: who leads the bidding (first only which conference, then the team and its offer), and the end.
    for (const sale of extra.shopped || []) {
      const id = sale.player?.player_id;
      const active = ["bidding", "sold", "lapsed", "cancelled"].includes(sale.status) || (sale.bids || []).length;
      if (!id || !active) continue;
      const entry = thread(`player:${id}`, {kind: "player", id, team: sale.seller});
      entry.name ||= sale.player.name; entry.face ||= sale.player.headshot_url || "";
      if (!entry.steps.some((step) => step.type === "market" || step.type === "bidding")) entry.steps.push({type: "market", date: sale.started || "", text: `Put on the market by ${sale.seller}`});
      (sale.bids || []).forEach((bid, index) => entry.steps.push({type: "bid", date: bid.date || "", text: index === 0 && sale.status === "bidding" && (sale.bids || []).length === 1
        ? `A team from the ${bid.leader_conference || "league"} leads the bidding` : `${bid.leader} leads, offering ${assets(bid.offer?.[bid.leader])}`}));
      const last = (sale.bids || []).at(-1);
      if (sale.status === "sold" && !entry.steps.some((step) => step.type === "traded" && step.date)) {
        entry.steps = entry.steps.filter((step) => step.type !== "traded");
        entry.steps.push({type: "traded", date: sale.sold_date || "", text: `Sold to ${sale.winner || "another team"}${last && sale.winner ? ` for ${assets(last.offer?.[sale.winner])}` : ""}`});
      } else if (sale.status === "lapsed") entry.steps.push({type: "collapsed", date: sale.decide_by || "", text: `No deal: ${sale.seller} kept him`});
      else if (sale.status === "cancelled") entry.steps.push({type: "collapsed", date: "", text: `The sale was called off${sale.cancel_reason ? `: ${sale.cancel_reason}` : ""}`});
    }
    // Streaks: five or more in a row, or seven or more that ended in the last few days.
    for (const run of extra.streaks || []) {
      const won = run.result === "W";
      const entry = thread(`streak:${run.team}`, {kind: "team", name: call("dashboardTeamName", run.team) || run.team, team: run.team, streak: run.length, won});
      entry.steps.push({type: "streak", date: run.since || "", text: `First of ${run.length} straight ${won ? "wins" : "losses"}`});
      if (run.ended) entry.steps.push({type: "snapped", date: run.ended, text: won ? `Beaten by ${run.ended_by}` : `Ended it against ${run.ended_by}`});
    }
    // Key injuries: when he went down and with what, and when he is due back (or that he is back).
    const seasonEnd = `${Number(String(extra.date || "").slice(0, 4)) + (String(extra.date || "").slice(5, 7) >= "07" ? 1 : 0)}-06-30`;
    for (const injury of extra.injuries || []) {
      const id = injury.player?.player_id;
      if (!id) continue;
      const entry = thread(`player:${id}`, {kind: "player", id, team: injury.player.team});
      entry.name ||= injury.player.name; entry.face ||= injury.player.headshot_url || ""; entry.missed = injury.expected_games_missed;
      const season = injury.return_date > seasonEnd;
      entry.steps.push({type: "injured", date: injury.start_date, text: season ? `Out for the season: ${injury.diagnosis}` : `Out: ${injury.diagnosis}, about ${injury.expected_games_missed} games`});
      if (injury.returned) entry.steps.push({type: "returned", date: injury.return_date, text: "Back in the lineup"});
      else if (!season) entry.steps.push({type: "due", date: injury.return_date, text: "Expected back"});
    }
    // Coaches under pressure: the same number the game's own review of a coach uses.
    for (const seat of extra.hot_seats || []) {
      const entry = thread(`staff:${seat.team}:head_coach`, {kind: "staff", team: seat.team, name: `${seat.team} head coach`, face: seat.headshot_url || ""});
      entry.face ||= seat.headshot_url || ""; entry.gap = Math.abs(Number(seat.wins_vs_expected_per_82) || 0);
      if (!entry.steps.some((step) => step.type === "fired")) entry.steps.push({type: "hot", date: "", text: `${seat.name}: on pace for ${entry.gap.toFixed(0)} fewer wins than expected, ${seat.games} games in`});
    }
    // Who it is, where it stands, and how much it matters.
    const weight = {demand: 100, final: 92, offer: 86, bidding: 85, bid: 84, collapsed: 80, target: 76, unhappy: 70, talks: 64, snapped: 62, fired: 60, returned: 56, lead: 55, streak: 54, hot: 52, market: 50, injured: 48, due: 48, hired: 40, traded: 40, signed: 30, stalled: 15};
    const closing = new Set(["traded", "signed", "hired", "collapsed", "snapped", "returned"]);
    const status = {demand: "Wants out", bidding: "Bidding war", bid: "Bidding war", market: "On the market", stalled: "Talks stalled", unhappy: "Unhappy", fired: "Job open", lead: "New leader", traded: "Traded", signed: "Signed", hired: "Filled",
      talks: "In talks", target: "In talks", offer: "Offer made", final: "Final offer", collapsed: "Fell apart", streak: "Streak", snapped: "Streak over", injured: "Out", due: "Out", returned: "Back", hot: "Hot seat"};
    const family = {demand: "trade", bidding: "trade", bid: "trade", market: "trade", stalled: "trade", traded: "trade", signed: "trade", talks: "trade", target: "trade", offer: "trade", final: "trade", collapsed: "trade",
      streak: "streak", snapped: "streak", injured: "injury", due: "injury", returned: "injury", hot: "staff", fired: "staff", hired: "staff", lead: "award", unhappy: "room"};
    const out = [];
    for (const entry of threads.values()) {
      entry.steps.sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999") || (closing.has(a.type) ? 1 : 0) - (closing.has(b.type) ? 1 : 0));
      // Where it stands is its last step that has happened (a return date still ahead is not the state of things).
      const last = entry.steps.filter((step) => step.type !== "due").at(-1) || entry.steps.at(-1);
      if (!last) continue;
      const person = people.get(entry.id) || {};
      entry.name ||= person.name || "";
      entry.face ||= person.headshot_url || "";
      if (!entry.name) continue;
      entry.closed = closing.has(last.type);
      entry.status = last.type === "streak" ? `${entry.streak} straight ${entry.won ? "wins" : "losses"}` : status[last.type] || "";
      entry.mine = Boolean(mine) && entry.team === mine;
      // The last thing that has happened in it; something still going on (a streak, a hot seat, a mood) is today's.
      const ongoing = !entry.closed && ["streak", "hot", "unhappy", "lead"].includes(last.type);
      entry.latest = ongoing ? today : entry.steps.map((step) => step.date).filter((date) => date && (!today || date <= today)).sort().at(-1) || "";
      const stale = today && entry.latest ? Math.max(0, daysBetween(entry.latest, today)) : 0;
      const top = Math.max(...entry.steps.map((step) => weight[step.type] || 0));
      const lead = entry.steps.reduce((best, step) => ((weight[step.type] || 0) > (weight[best.type] || 0) ? step : best), entry.steps[0]);
      entry.family = family[lead.type] || "other";
      // A lone "talks stalled" or "on the market" is routine (the market has its own list on this page); it is a
      // storyline once something else happened to him too.
      if (top <= weight.market && entry.steps.length < 2 && family[last.type] !== "injury") continue;
      // An injury is a storyline when it is long, when he has just come back, or when it is your player.
      if (family[last.type] === "injury" && !entry.mine && !(entry.missed >= 15 || last.type === "returned") && entry.steps.every((step) => family[step.type] === "injury")) continue;
      // More to it when it is long (a streak), costly (an injury) or far off the pace (a coach).
      const size = entry.family === "streak" ? Math.min(30, (entry.streak || 0) * 2) : entry.family === "injury" ? Math.min(30, (entry.missed || 0) / 3) : entry.family === "staff" ? Math.min(20, entry.gap || 0) : 0;
      entry.score = top + size + (entry.mine ? 40 : 0) + Math.min(20, entry.steps.length * 5) - (entry.closed ? 25 : 0) - Math.min(45, stale * 1.5);
      out.push(entry);
    }
    return out.sort((a, b) => b.score - a.score || b.latest.localeCompare(a.latest) || a.name.localeCompare(b.name));
  }

  function stories(st, mine) {
    const seen = {};
    const list = storylines(st, mine).filter((entry) => { if (entry.mine) return true; seen[entry.family] = (seen[entry.family] || 0) + 1; return seen[entry.family] <= 2; }).slice(0, 5);
    const today = String(st?.home?.save?.current_date || "");
    if (!list.length) return "";
    return `<section class="front-block front-stories"><h2>Storylines</h2>
      <div class="front-storylist">${list.map((entry) => {
        const steps = entry.steps.slice(-3).map((step, index, shown) => `<span class="${index === shown.length - 1 ? "is-latest" : ""}"><time>${step.date ? esc(shortDate(step.date) + (today && step.date.slice(0, 4) !== today.slice(0, 4) ? ` ${step.date.slice(0, 4)}` : "")) : "Now"}</time><span>${esc(step.text)}${step.until && step.until >= today && index === shown.length - 1 ? `, decision by ${esc(shortDate(step.until))}` : ""}</span></span>`).join("");
        const action = entry.kind === "player" && entry.id ? `data-front-player="${esc(entry.id)}"` : entry.kind === "team" ? `data-front-go="standings"` : `data-front-go="news"`;
        return `<button type="button" class="front-story${entry.mine ? " is-mine" : ""}${entry.closed ? " is-closed" : ""}" ${action}>
          <span class="front-face">${entry.face ? `<img src="${esc(entry.face)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : logoImg(entry.team)}</span>
          <span class="front-story-head"><b>${esc(entry.name)}</b>${entry.kind === "player" && entry.team ? `<span>${logoImg(entry.team)}${esc(entry.team)}</span>` : ""}<em>${esc(entry.status)}</em></span>
          <span class="front-story-steps">${steps}</span></button>`;
      }).join("")}</div></section>`;
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
    const summer = offseason(st);
    const middle = summer ? moves(st) : standings(league, mine) + expectation(surprises(st, league)) || comingUp(st, league);
    const cols = [stories(st, mine) + headlines(st, mine), middle, summer ? market(st) + eligible(st) + comingUp(st, league) : market(st) + scores(st, mine) + leaders(st)].filter(Boolean);
    return `<div class="front${summer ? " is-summer" : ""}">
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
    Promise.resolve(call("action", "home_storylines", call("savePayload"))).then((result) => {
      const now = app();
      if (!result || !now?.data || `${now.currentSave || ""}|${now.home?.save?.current_date || ""}` !== day) return;
      now.data.homeStories = result;
      const front = document.querySelector(".season-front-panel");
      if (front) front.innerHTML = markup();
    }).catch(() => {});
    Promise.resolve(call("loadTradeMarket", true)).then(() => {
      const target = document.querySelector("[data-front-shops]");
      if (target && app()?.data?.tradeMarket) target.innerHTML = marketRows(app()) || `<p class="front-none">Nobody is being shopped right now.</p>`;
      // The market's rows are steps of the storylines too.
      const front = document.querySelector(".season-front-panel");
      if (front && app()?.data?.tradeMarket) front.innerHTML = markup();
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

  if (typeof window !== "undefined") window.HomeFront = Object.freeze({markup, table, surprises, storylines, moves});
})();
