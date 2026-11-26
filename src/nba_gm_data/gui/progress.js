/* The main progress screen (UI polish pass, Stage B, 2026-11-25).

   Home answers three things at a glance: where you are in the year, what needs doing, and the one button that moves
   time. This module works those three out from the save (never from display-only numbers) and draws them; card-pages.js
   places them on Home and in the footer.

   One rule table (PHASES) says, for every phase of the game year, which step of the year strip it is and whether
   games are being played. Whether an action is open comes from the save's own legal_actions, so the list can never
   disagree with what the game will accept.

   The bottom-right button only moves time. When a job blocks it, the button names the job and opens it. */
(() => {
  "use strict";

  const app = () => (typeof state !== "undefined" ? state : null);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const day = (iso) => { const [, m, d] = String(iso || "").slice(0, 10).split("-").map(Number); return m && d ? `${MONTHS[m - 1]} ${d}` : ""; };
  const weekday = (iso) => { const date = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`); return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("en-US", {weekday: "long", timeZone: "UTC"}); };
  const plural = (count, word, many = `${word}s`) => `${count} ${count === 1 ? word : many}`;
  const ordinal = (n) => { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };

  // The seven steps of the year strip, and the phase of the save that belongs to each.
  const YEAR = ["Preseason", "Season", "Playoffs", "Who to keep", "Free agency", "Summer", "Camp"];
  const PHASES = {
    fantasy_draft: {step: 0, title: "Fantasy draft", games: false},
    preseason: {step: 0, title: "Preseason", games: true},
    regular_season: {step: 1, title: "Regular season", games: true},
    play_in: {step: 2, title: "Play-in", games: true},
    playoffs: {step: 2, title: "Playoffs", games: true},
    draft_lottery: {step: 3, title: "Draft lottery", games: false},
    draft: {step: 3, title: "Draft night", games: false},
    re_signing: {step: 3, title: "Decide who to keep", games: false},
    free_agency: {step: 4, title: "Free agency", games: false},
    offseason: {step: 5, title: "Late summer", games: false},
    training_camp: {step: 6, title: "Training camp", games: false},
  };
  const rule = (phase) => PHASES[phase] || {step: 1, title: "Season", games: true};

  function context() {
    const st = app();
    const save = st?.home?.save;
    if (!st || !save) return null;
    const data = st.data || {};
    const dash = data.statusDashboard || data.dashboard || {};
    const viewed = typeof teamLabel === "function" && typeof userTeam === "function" ? teamLabel((data.dashboard || {}).team || st.dashboardTeam || userTeam()) : "";
    return {
      st, save, data, dash,
      phase: String(save.phase || ""),
      today: String(save.current_date || "").slice(0, 10),
      kind: typeof dashboardPhaseKind === "function" ? dashboardPhaseKind() : "",
      required: typeof requiredClipboardDecision === "function" ? requiredClipboardDecision() : "",
      pending: save.pending_counts || {},
      legal: new Set(save.legal_actions || dash.legal_actions || []),
      dates: typeof offseasonCalendar === "function" ? offseasonCalendar() : {},
      deadline: typeof tradeDeadlineDate === "function" ? tradeDeadlineDate() : "",
      mine: !st.hydrating && (typeof userTeam !== "function" || !viewed || viewed === userTeam()),
      offers: Math.max((data.dashboardOffers?.offers || []).length, Number(save.pending_counts?.user_trade_offers || 0)),
    };
  }

  // ---- Where you are: the phase in a few words, and one line under it.
  function heading(c) {
    const info = rule(c.phase);
    let title = info.title, sub = "";
    if (c.phase === "preseason") {
      const opening = c.data.setRoster?.calendar?.opening_night || c.save.next_event_date;
      if (opening) sub = `Opening night is ${weekday(opening)}`;
    } else if (c.phase === "regular_season") {
      const record = c.save.user_team_record || c.dash.record || {};
      const parts = [`${Number(record.wins || 0)} – ${Number(record.losses || 0)}`];
      const seed = conferenceSeed(c);
      if (seed) parts.push(`${ordinal(seed.seed)} in the ${seed.conference}`);
      sub = parts.join(" · ");
      if (c.today === c.deadline) { title = "Trade deadline"; sub = "Trading closes when you sim"; }
    } else if (c.phase === "play_in" || c.phase === "playoffs") {
      const champion = c.save.postseason_exit_required && typeof teamLabel === "function" ? teamLabel(c.data.playoffs?.champion || c.save.playoff_champion_team_id) : "";
      sub = champion ? `${champion} are champions` : String(c.save.playoff_round || "").replaceAll("_", " ").replace(/^\w/, (ch) => ch.toUpperCase());
      if (sub.toLowerCase().replace(/[- ]/g, "") === title.toLowerCase().replace(/[- ]/g, "")) sub = "";
    } else if (c.phase === "re_signing") {
      if (c.dates.decisions_deadline) sub = `Decisions lock on ${day(c.dates.decisions_deadline)}`;
    } else if (c.phase === "draft" || c.phase === "draft_lottery") {
      const draft = c.data.draft || {};
      const current = draft.current_selection?.selection;
      if (["odds", "reveal"].includes(c.st.draftPresentationStage)) { title = "Draft lottery"; }
      else if (current && draft.current_pick_is_user_owned) sub = `You are on the clock · pick ${Number(current.overall_pick)}`;
      else if (current) sub = `Pick ${Number(current.overall_pick)} is up`;
      else if ((draft.draft_timeline || []).length) sub = "The draft is complete";
    } else if (c.phase === "free_agency") {
      const fa = c.data.freeagency?.state || {};
      if (fa.status === "completed") sub = "The first wave is over";
      else if (fa.day && fa.day_count) sub = `Market day ${Number(fa.day)} of ${Number(fa.day_count)}`;
    } else if (c.phase === "offseason") {
      if (c.dates.camp) sub = `Training camp opens ${day(c.dates.camp)}`;
    } else if (c.phase === "training_camp") {
      sub = "The preseason is next";
    }
    return {title, sub, step: info.step};
  }

  // The seed the Standings card shows (same rows, same order).
  function conferenceSeed(c) {
    if (typeof standingsRows !== "function" || typeof userTeam !== "function") return null;
    const rows = standingsRows(c.data.dashboardStandings) || [];
    const team = userTeam();
    const mine = rows.find((row) => teamLabel(row.team) === team);
    const conference = mine?.team?.conference;
    if (!conference) return null;
    const seed = rows.filter((row) => row.team?.conference === conference).indexOf(mine) + 1;
    return seed > 0 ? {seed, conference} : null;
  }

  // ---- What needs doing. kind: "must" blocks the button, "warn" is today's deadline, "done", "open", "shut".
  // go: {page} opens a page of the sidebar or a step screen, {run} is handled below, {card} flashes a section of Home.
  function jobs(c) {
    const list = [];
    const add = (kind, label, detail, go) => list.push({kind, label, detail: detail || "", go: go || null});
    const pending = c.pending;

    // Required first: these stop the clock.
    if (Number(pending.staff || 0) > 0) add("must", "Keep or replace your coach", plural(Number(pending.staff), "decision"), {page: "staff-retention"});
    if (Number(pending.cutdowns || 0) > 0) add("must", `Cut ${plural(Number(pending.cutdowns), "player")}`, rosterCount(c), {page: "roster-moves"});
    if (Number(pending.roster_minimum || 0) > 0) add("must", `Sign ${Number(pending.roster_minimum)} more ${Number(pending.roster_minimum) === 1 ? "player" : "players"}`, rosterCount(c), {page: "roster-moves"});

    if (c.phase === "fantasy_draft") add("open", "Fantasy draft", "", {page: "fantasy-draft"});

    if (c.phase === "preseason") {
      for (const item of c.data.setRoster?.items || []) {
        const count = item.count != null && item.target != null ? `${item.count} of ${item.target}` : "";
        const due = item.deadline ? (item.deadline === c.today ? "closes today" : `by ${day(item.deadline)}`) : "";
        if (item.kind === "roster") {
          if (Number(pending.cutdowns || 0) > 0 || Number(pending.roster_minimum || 0) > 0) continue;   // already the red row
          add(item.status === "pending" ? "must" : item.status === "done" || item.count === item.target ? "done" : "open", "Opening roster", count, {page: "roster-moves"});
        } else if (item.kind === "two_way_places") add(item.status === "done" ? "done" : "open", "Two-way places", count, {page: "roster-moves"});
        else if (item.kind === "rookie_extension") add("open", `Extend ${item.name || "a rookie"}`, due, {page: "set-roster"});
        // An undecided option holds the season's start (as it always has): a red row, and the button names it.
        else if (item.kind === "rookie_option") add(item.status === "pending" ? "must" : "done", `Rookie option: ${item.name || ""}`.trim(), item.status === "pending" ? due : "", {page: "set-roster"});
      }
    }

    if (c.phase === "re_signing" || c.phase === "free_agency") {
      const room = c.data.freeagency || {};
      const sheets = (room.offer_sheets?.for_you || []).length;
      if (sheets) add("must", "Match or pass", plural(sheets, "offer sheet"), {page: "free-agency-checklist"});
      const items = room.offseason_checklist?.items || [];
      const group = (kinds, label) => {
        const rows = items.filter((item) => kinds.includes(item.kind));
        if (!rows.length) return;
        const waiting = rows.filter((item) => item.status === "pending").length;
        add(waiting ? "open" : "done", label, waiting ? `${waiting} to decide` : "", {page: "free-agency-checklist"});
      };
      group(["team_option", "rookie_option"], "Team options");
      group(["qualifying_offer", "two_way_qualifying_offer"], "Qualifying offers");
      const own = items.filter((item) => item.kind === "own_free_agent").length;
      if (own) add("open", "Your free agents", `${own} unsigned`, {page: "free-agency-checklist"});
      if (c.phase === "free_agency") {
        const closed = room.state?.status === "completed" || !c.legal.has("free_agent_signings");
        add(closed ? "shut" : "open", "Free-agent market", closed ? "closed" : "", closed ? null : {page: "free-agency"});
      } else add("shut", "Other teams' free agents", c.dates.market_opens ? `from ${day(c.dates.market_opens)}` : "closed");
    }

    if (c.phase === "draft" || c.phase === "draft_lottery") {
      const draft = c.data.draft || {};
      const current = draft.current_selection?.selection;
      const next = draft.next_user_selection?.selection || draft.next_user_selection;
      if (current && draft.current_pick_is_user_owned) add("must", "Your pick", "on the clock", {page: "draft-room"});
      else if (current && next?.overall_pick) add("open", "Your next pick", `pick ${Number(next.overall_pick)}`, {page: "draft-room"});
      else add("open", current ? "Draft board" : "Draft results", "", {page: "draft-room"});
    }

    // Open all year where the game allows it; shown as closed where it does not.
    const trading = c.legal.has("trades") || c.legal.has("draft_trades");
    if (c.phase === "regular_season" && c.deadline && c.today <= c.deadline) {
      if (c.today === c.deadline) add("warn", "Trade deadline", "today", {page: "trades"});
    }
    if (trading) add("open", "Trade offers", c.offers ? `${c.offers} waiting` : "none", c.offers ? {run: "offers"} : {page: "trades"});
    else add("shut", "Trades", c.phase === "regular_season" ? "closed after the deadline" : "closed");
    if (rule(c.phase).games && c.kind !== "fantasy_draft") add("open", "Minutes", "", {card: "minutes"});
    if (c.legal.has("extensions") && c.dash.extension_window_open) add("open", "Extensions", "", {page: "contracts"});
    else if (c.phase !== "fantasy_draft") add("shut", "Extensions", c.dates.league_year && c.today < c.dates.league_year && ["re_signing", "free_agency", "draft"].includes(c.phase) ? "closed for now" : "closed");
    if (c.phase === "regular_season" && c.deadline && c.today < c.deadline) add("open", "Trade deadline", day(c.deadline), {page: "schedule"});
    if (["offseason", "training_camp"].includes(c.phase)) add("open", "Roster", rosterCount(c), {page: "roster"});
    if (["play_in", "playoffs"].includes(c.phase)) add("shut", "Signings", "closed until the offseason");
    if (["draft", "draft_lottery"].includes(c.phase)) add("shut", "Signings", c.dates.market_opens && c.today < c.dates.market_opens ? `from ${day(c.dates.market_opens)}` : "closed");

    const order = {must: 0, warn: 1, open: 2, done: 3, shut: 4};
    return list.map((job, index) => ({...job, index})).sort((a, b) => order[a.kind] - order[b.kind] || a.index - b.index);
  }

  const versus = (game) => (game?.opponent_team ? `${game.is_home ? "vs" : "at"} ${game.opponent_team}` : "");

  function rosterCount(c) {
    const cut = c.data.cutdown;
    if (cut?.short?.count != null && cut.short.minimum != null) return `${cut.short.count} of ${cut.short.minimum}`;
    if (cut?.current_count != null && cut.target_count != null) return `${cut.current_count} of ${cut.target_count}`;
    const rows = typeof rosterRows === "function" ? rosterRows(c.dash) : [];
    return rows.length ? `${rows.length} of 15` : "";
  }

  // ---- The one button. main: {label, sub, attrs, blocked}; more: plain buttons beside it. attrs keep the ids and
  // commands the rest of the game already listens for (keyboard shortcuts included).
  function dock(c) {
    const off = c.mine ? "" : " disabled";
    const main = (label, sub, attrs, blocked = false) => ({label, sub: sub || "", attrs: `${attrs}${off}`, blocked});
    const side = (label, attrs) => ({label, attrs: `${attrs}${off}`});
    const next = c.save.next_event_date ? `to ${day(c.save.next_event_date)}` : "";
    const first = jobs(c).find((job) => job.kind === "must");

    // A job that stops the clock: the button names it and opens it. (On draft night your pick is the job, and the
    // button is the pick itself: handled below.)
    const blocked = () => ({main: main(first.label, first.detail, `data-pages-go="${first.go.page}" data-progress-blocked`, true), more: []});
    if (c.required && first?.go?.page) return blocked();
    if (c.save.postseason_exit_required) return {main: main("Start the offseason", c.dates.offseason_opens ? `to ${day(c.dates.offseason_opens)}` : next, 'id="postseasonAdvance" data-phase-command="postseason-exit"'), more: []};
    if (c.kind === "fantasy_draft") return {main: null, more: []};

    if (c.kind === "free_agency") {
      const room = c.data.freeagency;
      if (!room) return {main: null, more: []};
      if (first?.go?.page) return blocked();
      if (room.phase === "re_signing") {
        const beforeDraft = c.dates.draft_round_one && c.today < c.dates.draft_round_one;
        return beforeDraft
          ? {main: main("Go to draft night", `to ${day(c.dates.draft_round_one)}`, 'id="reSignToDraft" data-phase-command="resign-day"'), more: []}
          : {main: main("Open free agency", c.dates.market_opens ? `to ${day(c.dates.market_opens)}` : "", 'id="reSignOpenMarket" data-phase-command="resign-open"'), more: []};
      }
      if (room.state?.status === "completed") return {main: main("Go to late summer", "", 'id="faAdvanceStage" data-phase-command="fa-next"'), more: []};
      return {main: main("Next market day", "", 'id="faAdvanceDay" data-phase-command="fa-day"'), more: [side("Finish first wave", 'id="faAdvanceEnd" data-phase-command="fa-end"')]};
    }

    if (c.kind === "draft") {
      const draft = c.data.draft || {};
      const stage = c.st.draftPresentationStage;
      if (stage === "odds") return {main: main("Reveal the lottery", "", 'id="draftRevealLottery" data-phase-command="lottery-reveal"'), more: []};
      if (stage === "reveal") {
        if (c.st.lotteryRevealRunning) return {main: main("Skip the reveal", "", 'id="draftSkipReveal" data-phase-command="lottery-skip"'), more: []};
        const shown = typeof lotteryRevealCount === "function" ? lotteryRevealCount(draft) : 0;
        if (shown < (draft.lottery?.reveal || []).length) return {main: main("Continue the reveal", "", 'id="draftRevealLottery" data-phase-command="lottery-reveal"'), more: []};
        return {main: main("Go to draft night", "", 'id="draftEnterNight" data-phase-command="draft-enter"'), more: []};
      }
      const current = draft.current_selection?.selection;
      if (!current) return {main: main("Leave the draft", "", 'id="draftAdvanceStage" data-phase-command="draft-next"'), more: []};
      const finish = side("Finish draft", 'id="draftAll" data-phase-command="draft-all"');
      if (draft.current_pick_is_user_owned) {
        const rows = typeof draftBoardRows === "function" ? draftBoardRows(draft.draft_board) : [];
        const picked = rows.find((row) => row.id === c.st.selectedDraftProspect);
        return picked
          ? {main: main(`Draft ${picked.name}`, `pick ${Number(current.overall_pick)}`, 'id="draftApply" data-phase-command="draft-apply"'), more: [finish]}
          : {main: main("Choose a prospect", `pick ${Number(current.overall_pick)}`, 'data-pages-go="draft-room" data-progress-blocked', true), more: [finish]};
      }
      const one = `Sim pick ${Number(current.overall_pick)}`;
      const mine = draft.next_user_selection?.selection || draft.next_user_selection;
      return mine?.overall_pick
        ? {main: main("Sim to my pick", `pick ${Number(mine.overall_pick)}`, 'id="draftToUser" data-phase-command="draft-user"'), more: [side(one, 'id="draftSimCurrent" data-phase-command="draft-one"'), finish]}
        : {main: main(one, "", 'id="draftSimCurrent" data-phase-command="draft-one"'), more: [finish]};
    }

    if (c.kind === "playoffs") return {main: main("Sim one game per series", next, 'data-advance="next-event"'), more: [side("Full series", 'data-advance="week"'), side("Finish playoffs", 'data-advance="month"')]};

    if (c.phase === "preseason") {
      const list = c.data.setRoster;
      if (!list) return {main: null, more: []};
      if (first?.go?.page) return blocked();
      const waiting = (list.items || []).filter((item) => item.status === "pending").length;
      if (waiting) return {main: main("Finish the roster", `${plural(waiting, "decision")} left`, 'id="presetSetRoster" data-phase-command="preseason-roster" data-progress-blocked', true), more: []};
      return {main: main("Start the season", list.calendar?.opening_night ? `to ${day(list.calendar.opening_night)}` : next, 'id="presetStartSeason" data-phase-command="preseason-start"'), more: []};
    }

    if (["offseason", "training_camp"].includes(c.phase)) {
      const toCamp = c.dates.camp && c.today < c.dates.camp;
      return {main: main(toCamp ? "Go to training camp" : "Go to the preseason", toCamp ? `to ${day(c.dates.camp)}` : next, 'id="offseasonNextStop" data-phase-command="offseason-next"'), more: []};
    }

    // The season: the next game, with a week or a month beside it.
    const game = (c.dash.next_games || [])[0];
    const opponent = versus(game);
    const deadlineDay = c.phase === "regular_season" && c.today === c.deadline;
    return {
      main: main(deadlineDay ? "Sim past the deadline" : "Sim to next game", deadlineDay ? "closes trading" : [game?.date ? `to ${day(game.date)}` : next, opponent].filter(Boolean).join(" · "), 'data-advance="next-event"'),
      more: [side("Week", 'data-advance="week"'), side("Month", 'data-advance="month"')],
    };
  }

  // The footer's buttons, as markup card-board.js places where the Sim menu was. Quieter buttons first, the main one
  // last, so it always sits at the far right.
  function dockMarkup() {
    const c = context();
    if (!c) return "";
    const {main, more} = dock(c);
    if (!main) return typeof clipboardPhaseCommands === "function" ? clipboardPhaseCommands() : "";
    return more.map((button) => `<button type="button" class="ui-command progress-more" ${button.attrs}>${esc(button.label)}</button>`).join("")
      + `<button type="button" class="ui-command progress-go${main.blocked ? " is-blocked" : ""}" ${main.attrs}><b>${esc(main.label)}</b>${main.sub ? `<small>${esc(main.sub)}</small>` : ""}</button>`;
  }

  // ---- Home's own parts: the phase and the year strip across the top, the list down the left.
  function topMarkup() {
    const c = context();
    if (!c) return "";
    const head = heading(c);
    return `<div class="progress-phase"><h2>${esc(head.title)}</h2>${head.sub ? `<p>${esc(head.sub)}</p>` : ""}</div>
      <ol class="progress-year" aria-label="The year">${YEAR.map((name, index) => `<li class="${index === head.step ? "is-now" : index < head.step ? "is-past" : ""}"${index === head.step ? ' aria-current="step"' : ""}><i></i><b>${esc(name)}</b></li>`).join("")}</ol>`;
  }

  const MARK = {must: "Required", warn: "Today", done: "Done", open: "", shut: "Closed"};
  function listMarkup(pageAvailable = () => true) {
    const c = context();
    if (!c) return "";
    const rows = jobs(c).map((job) => {
      const go = job.go || {};
      const reachable = go.run || go.card || (go.page && pageAvailable(go.page));
      const attrs = !reachable ? "" : go.page ? ` data-pages-go="${esc(go.page)}"` : go.run ? ` data-progress-run="${esc(go.run)}"` : ` data-progress-card="${esc(go.card)}"`;
      const inner = `<i class="progress-dot" aria-hidden="true"></i><b>${esc(job.label)}</b><span>${esc(job.detail)}</span>${MARK[job.kind] ? `<span class="progress-sr">${MARK[job.kind]}</span>` : ""}${reachable ? `<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>` : "<em></em>"}`;
      return reachable
        ? `<button type="button" class="progress-job is-${job.kind}"${attrs}>${inner}</button>`
        : `<div class="progress-job is-${job.kind}">${inner}</div>`;
    }).join("");
    return `<h3>To do</h3><div class="progress-todo">${rows}</div>`;
  }

  // What the list's rows that are not pages do.
  document.addEventListener("click", (event) => {
    const run = event.target.closest?.("[data-progress-run]");
    if (run) {
      if (run.dataset.progressRun === "offers" && typeof openTradeOffersModal === "function") openTradeOffersModal();
      return;
    }
    const card = event.target.closest?.("[data-progress-card]");
    if (card) window.CardBoard?.open?.(card.dataset.progressCard);
  });

  // A signature of what stops the clock: when it changes, Home is where you land.
  function blockingKey() {
    const c = context();
    if (!c) return "";
    return jobs(c).filter((job) => job.kind === "must").map((job) => job.label).join("|");
  }

  window.GameProgress = Object.freeze({YEAR, PHASES, context, heading, jobs, dock, dockMarkup, topMarkup, listMarkup, blockingKey, gamesOn: () => rule(String(app()?.home?.save?.phase || "")).games});
})();
