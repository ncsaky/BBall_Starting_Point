const state = {
  busy: false,
  teams: [],
  saves: [],
  currentSave: "",
  home: null,
  view: "dashboard",
  dashboardTab: "overview",
  dashboardTeam: "",
  dashboardInnerTab: "rotation",
  calendarMonth: "",
  expandedContractSeason: "",
  rotationDraft: {},
  sorts: {},
  leagueTab: "standings",
  leagueStat: "points",
  leagueTrait: "overall",
  tradeTab: "builder",
  tradePartner: "",
  selectedFrom: [],
  selectedTo: [],
  tradeCandidate: null,
  tradeResults: [],
  selectedFreeAgent: null,
  staffSlot: "",
  selectedStaff: null,
  modal: null,
  data: {},
};

const els = {};
const LAST_SAVE_KEY = "nbaGmLastSave";

document.addEventListener("DOMContentLoaded", () => {
  for (const id of [
    "runtime",
    "startupRuntime",
    "saveSelect",
    "startupSaveSelect",
    "startupRefreshSaves",
    "startupLoadSave",
    "refreshSaves",
    "teamSelect",
    "saveName",
    "createSave",
    "nav",
    "startupScreen",
    "content",
    "toast",
    "modalRoot",
  ]) {
    els[id] = document.getElementById(id);
  }
  wireEvents();
  init();
});

function wireEvents() {
  els.refreshSaves.addEventListener("click", loadSaves);
  els.startupRefreshSaves.addEventListener("click", loadSaves);
  els.startupLoadSave.addEventListener("click", async () => {
    state.currentSave = els.startupSaveSelect.value || "";
    localStorage.setItem(LAST_SAVE_KEY, state.currentSave);
    state.view = "dashboard";
    state.dashboardTeam = "";
    await refreshHome();
  });
  els.createSave.addEventListener("click", createSave);
  els.saveSelect.addEventListener("change", async () => {
    state.currentSave = els.saveSelect.value;
    localStorage.setItem(LAST_SAVE_KEY, state.currentSave);
    state.view = "dashboard";
    state.dashboardTeam = "";
    await refreshHome();
  });
  els.nav.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    state.view = button.dataset.view;
    if (state.view === "dashboard") {
      state.dashboardTeam = userTeam();
      state.dashboardTab = "overview";
    }
    for (const navButton of els.nav.querySelectorAll("button")) navButton.classList.toggle("active", navButton === button);
    await ensureViewData(true);
    render();
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-advance]");
    if (!button) return;

    const mode = button.dataset.advance;

    if (mode === "next-event") return advance({ next_event: true });
    if (mode === "week") return advance({ days: 7, checkpoint_days: 7 });
    if (mode === "month") return advance({ days: 31, checkpoint_days: 31 });
    if (mode === "deadline") return advanceToMilestone("deadline");
    if (mode === "season-end") return advanceToMilestone("season_end");
  });
  els.content.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sort-table]");
    if (!button) return;
    const tableId = button.dataset.sortTable;
    const index = Number(button.dataset.sortIndex || 0);
    const existing = state.sorts[tableId] || {};
    state.sorts[tableId] = { index, direction: existing.index === index && existing.direction === "asc" ? "desc" : "asc" };
    render();
  });
  els.modalRoot.addEventListener("click", (event) => {
    if (event.target === els.modalRoot || event.target.closest("[data-close-modal]")) closeModal();
  });
}

async function init() {
  try {
    const status = await apiGet("/api/status");
    els.runtime.textContent = `${status.engine} | ${status.protocol_version}`;
    els.startupRuntime.textContent = `${status.engine} | ${status.protocol_version}`;
    state.currentSave = localStorage.getItem(LAST_SAVE_KEY) || "";
    await loadTeams();
    await loadSaves();
  } catch (error) {
    showToast(error.message || String(error), true);
  }
}

async function apiGet(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function action(name, payload = {}) {
  setBusy(true);
  try {
    const response = await fetch("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: name, payload }),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data.result;
  } finally {
    setBusy(false);
  }
}

async function loadTeams() {
  const data = await action("teams");
  state.teams = data.teams || [];
  els.teamSelect.innerHTML = '<option value="random">Random team</option>' + state.teams.map((team) => {
    const label = `${escapeHtml(team.abbrev)} ${escapeHtml(team.name || "")}`.trim();
    return `<option value="${escapeAttr(team.abbrev)}">${label}</option>`;
  }).join("");
}

async function loadSaves() {
  const data = await action("list_saves");
  const saves = data.saves || [];
  const playable = saves.filter((save) => save.status === "ok" && save.path);
  state.saves = playable;
  els.saveSelect.innerHTML = playable.length
    ? playable.map((save) => `<option value="${escapeAttr(save.path)}">${escapeHtml(save.name)} | ${escapeHtml(save.team || "?")} | ${escapeHtml(save.current_date || "")}</option>`).join("")
    : '<option value="">No saves yet</option>';
  els.startupSaveSelect.innerHTML = playable.length
    ? playable.map((save) => `<option value="${escapeAttr(save.path)}">${escapeHtml(save.name)} | ${escapeHtml(save.team || "?")} | ${escapeHtml(save.current_date || "")}</option>`).join("")
    : '<option value="">No saves yet</option>';
  if (!playable.some((save) => save.path === state.currentSave)) state.currentSave = "";
  if (state.currentSave) {
    els.saveSelect.value = state.currentSave;
    els.startupSaveSelect.value = state.currentSave;
  }
  await refreshHome();
}

async function createSave() {
  const team = els.teamSelect.value || "random";
  const saveName = els.saveName.value.trim();
  const result = await action("create_save", { team, save_name: saveName || undefined });
  state.currentSave = result.save_path;
  localStorage.setItem(LAST_SAVE_KEY, state.currentSave);
  state.view = "dashboard";
  state.dashboardTeam = "";
  els.saveName.value = "";
  showToast(`Created ${teamLabel(result.save?.user_team || result.save?.team || "save")}`);
  await loadSaves();
}

async function refreshHome() {
  clearViewCaches();
  if (!state.currentSave) {
    state.home = null;
    render();
    return;
  }
  state.home = await action("home", savePayload());
  if (!state.dashboardTeam) state.dashboardTeam = userTeam();
  syncDefaultPartner();
  applyPhaseRouting();
  await ensureViewData(true);
  render();
}

function clearViewCaches() {
  state.data = {};
  state.tradeCandidate = null;
  state.tradeResults = [];
}

function syncDefaultPartner() {
  const user = userTeam();
  if (!state.tradePartner || state.tradePartner === user) {
    state.tradePartner = (state.teams.find((team) => team.abbrev !== user) || {}).abbrev || "BOS";
  }
}

async function ensureViewData(force = false) {
  if (!state.currentSave) return;
  if (force || !state.data.statusDashboard) {
    state.data.statusDashboard = await action("team_dashboard", { ...savePayload(), team: userTeam() });
  }
  const key = state.view;
  if (!force && state.data[key]) return;
  if (key === "dashboard") {
    const team = state.dashboardTeam || userTeam();
    state.data.dashboard = team === userTeam()
      ? state.data.statusDashboard
      : await action("team_dashboard", { ...savePayload(), team });
    await loadDashboardCalendar(team);
    state.data.dashboardStandings = await action("standings", savePayload());
  }
  if (key === "league") {
    state.data.standings = await action("standings", savePayload());
    state.data.events = await action("league_events", { ...savePayload(), limit: 50, kind: "transactions" });
    state.data.leagueLeaders = await action("league_leaders", { ...savePayload(), stat: state.leagueStat, limit: 30 });
    state.data.leagueTraits = await action("league_traits", { ...savePayload(), trait: state.leagueTrait, limit: 40 });
  }
  if (key === "calendar") state.data.calendar = await action("calendar", savePayload());
  if (key === "trade") await loadTradeAssets();
  if (key === "offers") state.data.offers = await action("user_trade_offers", savePayload());
  if (key === "draft") state.data.draft = await action("draft_room", { ...savePayload(), team: userTeam(), seed: 7 });
  if (key === "playoffs") state.data.playoffs = await action("playoff_room", savePayload());
  if (key === "freeagents" || key === "freeagency") state.data.freeagency = await action("free_agency_room", { ...savePayload(), team: userTeam(), seed: 7 });
  if (key === "staff") state.data.staff = await action("staff_room", { ...savePayload(), team: userTeam(), slot: state.staffSlot || undefined, limit: 30 });
  if (key === "social") state.data.social = await action("social_feed", { ...savePayload(), limit: 18 });
  if (key === "settings") state.data.settings = await action("narrative_settings", savePayload());
}

async function loadDashboardCalendar(team) {
  const current = state.home?.save?.current_date || "";
  const month = state.calendarMonth || current.slice(0, 7);
  if (!month) return;
  const from = `${month}-01`;
  const through = monthEndDate(from);
  state.data.dashboardCalendar = await action("calendar", { ...savePayload(), from_date: from, through_date: through });
}

async function loadTradeAssets() {
  syncDefaultPartner();
  const user = userTeam();
  state.data.tradeUser = await action("team_assets", { ...savePayload(), team: user });
  state.data.tradePartner = await action("team_assets", { ...savePayload(), team: state.tradePartner });
}

async function advance(payload) {
  if (!state.currentSave) return showToast("Create or select a save first.", true);
  const result = await action("advance_save", { ...savePayload(), ...payload });
  state.home = result.home;
  clearViewCaches();
  applyPhaseRouting();
  await ensureViewData(true);
  render();
  showToast(`Advanced to ${state.home?.save?.current_date || "next date"}`);
}

function advanceToMilestone(kind) {
  if (!state.currentSave) return showToast("Create or select a save first.", true);
  const season = state.home?.save?.season || "";
  const startYear = Number(String(season).slice(0, 4)) || Number(String(state.home?.save?.current_date || "").slice(0, 4)) || 2025;
  const target = kind === "deadline" ? `${startYear + 1}-02-05` : `${startYear + 1}-04-15`;
  return advance({ to_date: target, checkpoint_days: 31 });
}

function savePayload() {
  return { save_path: state.currentSave };
}

function render() {
  const save = state.home?.save;
  applyPhaseRouting();
  document.body.dataset.view = state.currentSave ? state.view : "startup";
  els.startupScreen.hidden = Boolean(state.currentSave);
  if (!state.currentSave) {
    renderStartup();
    return;
  }
  els.startupScreen.hidden = true;
  syncNavActive();
  if (state.view === "dashboard") renderDashboard();
  if (state.view === "trade") renderTrade();
  if (state.view === "offers") renderOffers();
  if (state.view === "draft") renderDraft();
  if (state.view === "playoffs") renderPlayoffs();
  if (state.view === "freeagents" || state.view === "freeagency") renderFreeAgency();
  if (state.view === "staff") renderStaff();
  if (state.view === "league") renderLeague();
  if (state.view === "calendar") renderCalendar();
  if (state.view === "social") renderSocial();
  if (state.view === "settings") renderSettings();
  renderModal();
}

function renderStartup() {
  els.content.innerHTML = "";
  els.startupScreen.hidden = false;
  els.startupLoadSave.disabled = !els.startupSaveSelect.value;
}

function applyPhaseRouting() {
  if (!state.currentSave || !state.home?.save) return;
  const phase = String(state.home.save.phase || "");
  if (phase === "draft") state.view = "draft";
  else if (phase === "free_agency") state.view = "freeagents";
  else if (phase === "play_in" || phase === "playoffs") state.view = "playoffs";
  else if (state.view === "draft" || state.view === "playoffs") state.view = "dashboard";
}

function syncNavActive() {
  for (const button of els.nav.querySelectorAll("button[data-view]")) {
    button.classList.toggle("active", button.dataset.view === state.view || (button.dataset.view === "freeagents" && state.view === "freeagency"));
  }
}

function renderDashboard() {
  const dash = state.data.dashboard || {};
  const rows = rosterRows(dash);
  const tabs = ["overview", "contracts"];
  const viewedTeam = teamLabel(dash.team || state.dashboardTeam || userTeam());
  const editable = viewedTeam === userTeam();
  els.content.innerHTML = `
    <section class="section dashboard-shell">
      <div id="dashboardTab"></div>
      <div class="tabs segmented">${tabs.map((tab) => `<button data-tab="${tab}" class="${tab === state.dashboardTab ? "active" : ""}">${tabLabel(tab)}</button>`).join("")}</div>
    </section>`;
  els.content.querySelector(".tabs").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-tab]");
    if (!button) return;
    state.dashboardTab = button.dataset.tab;
    state.expandedContractSeason = "";
    renderDashboard();
  });
  renderDashboardTab(rows);
}

function renderDashboardTab(rows) {
  const target = document.getElementById("dashboardTab");
  const dash = state.data.dashboard || {};
  const editable = teamLabel(dash.team || state.dashboardTeam) === userTeam();
  if (state.dashboardTab === "overview") {
    target.innerHTML = `
      <div class="dashboard-overview">
        <section class="section panel-rail identity-card">${teamIdentityRankBlock(dash)}</section>
        <section class="section panel-rail starting-card">${startingFiveBlock(rows, editable)}</section>
        <section class="section panel-rail rotation-card">${rotationRatingsBlock(rows, editable)}</section>
        <section class="section panel-rail standings-card">${userConferenceStandings()}</section>
        <section class="section panel-rail calendar-card">${dashboardMonthCalendar()}</section>
        <section class="section panel-rail events-card">${sectionHead("Recent League Events")}${list((state.home?.league_events?.events || []).slice(0, 5).map(eventLine))}</section>
      </div>`;
    wireDashboardOverview(editable);
    return;
  }
  target.innerHTML = contractsBlock(rows, dash);
  wireContractsBlock();
}

function renderTrade() {
  const user = userTeam();
  const partnerOptions = state.teams
    .filter((team) => team.abbrev !== user)
    .map((team) => `<option value="${escapeAttr(team.abbrev)}" ${team.abbrev === state.tradePartner ? "selected" : ""}>${escapeHtml(team.abbrev)} ${escapeHtml(team.name || "")}</option>`)
    .join("");
  els.content.innerHTML = `
    <section class="section featured">
      <div class="section-head">
        <div><h3>Trade Room</h3><p class="muted">Build exact packages or shop an asset through the engine.</p></div>
        <select id="tradePartner">${partnerOptions}</select>
      </div>
      <div class="tabs">
        <button data-trade-tab="builder" class="${state.tradeTab === "builder" ? "active" : ""}">Builder</button>
        <button data-trade-tab="finder" class="${state.tradeTab === "finder" ? "active" : ""}">Finder</button>
      </div>
      <div id="tradeBody"></div>
    </section>`;
  document.getElementById("tradePartner").addEventListener("change", async (event) => {
    state.tradePartner = event.target.value;
    state.selectedTo = [];
    state.tradeCandidate = null;
    await loadTradeAssets();
    renderTrade();
  });
  els.content.querySelector(".tabs").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-trade-tab]");
    if (!button) return;
    state.tradeTab = button.dataset.tradeTab;
    renderTrade();
  });
  if (state.tradeTab === "finder") renderTradeFinder();
  else renderTradeBuilder();
}

function renderTradeBuilder() {
  const body = document.getElementById("tradeBody");
  const userAssets = state.data.tradeUser || {};
  const partnerAssets = state.data.tradePartner || {};
  body.innerHTML = `
    <div class="room-layout">
      ${assetColumn(`${userTeam()} sends`, userAssets, "from")}
      <section class="section">
        <div class="section-head"><h3>Package</h3><span class="pill">${escapeHtml(userTeam())} / ${escapeHtml(state.tradePartner)}</span></div>
        <div class="side-by-side">
          <div><p class="muted">Outgoing</p><div class="selected-list">${chips(state.selectedFrom, "from")}</div></div>
          <div><p class="muted">Incoming</p><div class="selected-list">${chips(state.selectedTo, "to")}</div></div>
        </div>
        <div class="toolbar">
          <button id="evaluateTrade">Evaluate</button>
          <button id="clearTrade">Clear</button>
        </div>
        <div id="tradeRead">${tradeReadout(state.tradeCandidate)}</div>
      </section>
      ${assetColumn(`${state.tradePartner} sends`, partnerAssets, "to")}
    </div>`;
  body.querySelectorAll("[data-asset-side]").forEach((button) => {
    button.addEventListener("click", () => toggleAsset(button.dataset.assetSide, button.dataset.assetKind, button.dataset.assetId));
  });
  body.querySelectorAll("[data-remove-side]").forEach((button) => {
    button.addEventListener("click", () => removeAsset(button.dataset.removeSide, button.dataset.assetId));
  });
  document.getElementById("clearTrade").addEventListener("click", () => {
    state.selectedFrom = [];
    state.selectedTo = [];
    state.tradeCandidate = null;
    renderTrade();
  });
  document.getElementById("evaluateTrade").addEventListener("click", evaluateBuiltTrade);
  const applyButton = document.getElementById("applyBuiltTrade");
  if (applyButton) applyButton.addEventListener("click", () => applyCandidate(state.tradeCandidate, "builder"));
}

function assetColumn(title, payload, side) {
  const cap = payload.cap || {};
  const assets = payload.assets || [];
  return `
    <section class="section">
      <div class="section-head"><h3>${escapeHtml(title)}</h3><span class="pill">${assets.length} assets</span></div>
      <p class="muted">Payroll ${money(cap.salary_total_millions)} | tax ${signedMoney(cap.tax_space_millions)} | hard cap ${signedMoney(cap.hard_cap_space_millions)}</p>
      <div class="scroll-list stack">
        ${assets.slice(0, 70).map((asset) => assetButton(asset, side)).join("") || `<div class="empty">No tradeable assets.</div>`}
      </div>
    </section>`;
}

function assetButton(asset, side) {
  const selected = selectedList(side).some((item) => item.id === asset.id);
  const meta = asset.kind === "player"
    ? `${asset.position || ""} age ${asset.age || ""} ${asset.height || ""} | ${asset.mpg || 0} mpg | OVR ${asset.ratings?.overall || ""} | ${asset.contract || ""}`
    : `${asset.season || ""} R${asset.round || ""}`;
  return `
    <button class="asset-card ${selected ? "selected" : ""}" data-asset-side="${side}" data-asset-kind="${escapeAttr(asset.kind)}" data-asset-id="${escapeAttr(asset.id)}">
      <span class="asset-title"><span>${escapeHtml(asset.label || asset.name || asset.id)}</span><span class="value-badge">${Number(asset.trade_value || 0).toFixed(1)}</span></span>
      <span class="asset-meta">${escapeHtml(meta)}</span>
    </button>`;
}

function renderTradeFinder() {
  const body = document.getElementById("tradeBody");
  body.innerHTML = `
    <div class="grid-2">
      <section class="section">
        <div class="section-head"><h3>Shop Player</h3></div>
        <div class="toolbar">
          <input id="tradePlayer" placeholder="Player name" />
          <input id="tradeTeam" placeholder="For team, default ${escapeAttr(userTeam())}" />
          <button id="runTrade">Find Offers</button>
        </div>
        <div class="empty">Use this for quick market discovery. Results are incoming offers the counterparty has already approved.</div>
      </section>
      <section class="section">
        <div class="section-head"><h3>Offers</h3><span class="pill">${state.tradeResults.length}</span></div>
        <div id="tradeResults" class="stack">${tradeResultCards(state.tradeResults)}</div>
      </section>
    </div>`;
  document.getElementById("runTrade").addEventListener("click", runTradeSearch);
  body.querySelectorAll("[data-apply-finder]").forEach((button) => {
    button.addEventListener("click", () => applyCandidate(state.tradeResults[Number(button.dataset.applyFinder)], "trade_finder"));
  });
}

async function evaluateBuiltTrade() {
  if (!state.selectedFrom.length && !state.selectedTo.length) return showToast("Select at least one asset.", true);
  const result = await action("evaluate_trade", {
    ...savePayload(),
    from_team: userTeam(),
    to_team: state.tradePartner,
    from_assets: state.selectedFrom.map(assetSpec),
    to_assets: state.selectedTo.map(assetSpec),
    seed: 7,
  });
  result.headline = tradeHeadline(result);
  state.tradeCandidate = result;
  renderTrade();
}

async function runTradeSearch() {
  const player = document.getElementById("tradePlayer").value.trim();
  if (!player) return showToast("Enter a player name.", true);
  const team = document.getElementById("tradeTeam").value.trim();
  const data = await action("find_trade", { ...savePayload(), player, for_team: team || userTeam(), limit: 8, seed: 7 });
  state.tradeResults = data.candidates || data.offers || [];
  renderTrade();
}

async function applyCandidate(candidate, source) {
  if (!candidate) return;
  const result = await action("apply_trade_candidate", { ...savePayload(), candidate, source });
  showToast(`Trade result: ${result.status}`);
  state.selectedFrom = [];
  state.selectedTo = [];
  state.tradeCandidate = null;
  state.tradeResults = [];
  await refreshHome();
}

function renderOffers() {
  const offers = state.data.offers?.offers || [];
  els.content.innerHTML = `
    <section class="section featured">
      <div class="section-head">
        <div><h3>AI Trade Offers To You</h3><p class="muted">Only active incoming offers remain here. Deadline-expired offers are cleared by the engine.</p></div>
        <span class="pill">${offers.length} active</span>
      </div>
      <div class="stack">${offers.length ? offers.map((offer, index) => offerCard(offer, index)).join("") : `<div class="empty">No active AI offers to your team.</div>`}</div>
    </section>`;
  els.content.querySelectorAll("[data-offer-accept]").forEach((button) => {
    button.addEventListener("click", () => respondOffer(offers[Number(button.dataset.offerAccept)], "accept"));
  });
  els.content.querySelectorAll("[data-offer-reject]").forEach((button) => {
    button.addEventListener("click", () => respondOffer(offers[Number(button.dataset.offerReject)], "reject"));
  });
}

async function respondOffer(offer, decision) {
  const proposalId = offer?.proposal?.id || offer?.id;
  const result = await action("respond_user_trade_offer", { ...savePayload(), proposal_id: proposalId, decision });
  state.data.offers = result.offers;
  showToast(`Offer ${result.status}`);
  await refreshHome();
}

function renderDraft() {
  const draft = state.data.draft || {};
  const current = draft.current_selection || {};
  const selection = current.selection || {};
  const prospect = current.prospect || {};
  const draftStatus = draft.state?.status || "in_progress";
  const locked = draftStatus === "locked_until_draft";
  const pickLabel = locked ? "Scouting preview" : `Pick ${Number(draft.state?.current_index || 0) + 1} of ${draft.state?.total_picks || 0}`;
  els.content.innerHTML = `
    <section class="moment-screen draft-moment">
      <div class="moment-topline">
        <button data-view-jump="dashboard">Back to Dashboard</button>
        <div>
          <p class="eyebrow">${escapeHtml(pickLabel)}</p>
          <h3>${escapeHtml(draft.year || "")} Draft Board</h3>
        </div>
        <div class="dashboard-meta"><span>${escapeHtml(draftStatus)}</span><span>${escapeHtml(teamLabel(draft.team || userTeam()))}</span></div>
      </div>
      <div class="draft-grid">
        <section class="section panel-rail">
        ${locked ? `<div class="court-note">Draft controls unlock when the league reaches draft night. For now this room works as a live scouting board and draft-order preview.</div>` : current.selection ? `
          <div class="headline-block">
            <p class="eyebrow">On the clock</p>
            <h3>#${escapeHtml(selection.overall_pick)} ${escapeHtml(teamLabel(current.team || selection.team_id))}</h3>
            <p>${escapeHtml(prospect.name || "Recommended prospect TBD")} <span class="muted">${escapeHtml(prospect.position || "")} ${escapeHtml(prospect.height || "")}</span></p>
          </div>
          <div class="toolbar">
            <button id="draftApply">Make Current Pick</button>
            <button id="draftToUser">Sim To User Pick</button>
            <button id="draftAll">Sim Full Draft</button>
          </div>` : `<div class="empty">Draft complete.</div>`}
        ${list((draft.trade_news || []).map((item) => item.headline || textValue(item)))}
      </section>
      <section class="section panel-rail">
        ${sectionHead("Team Board")}
        ${table(["Rank", "Prospect", "Pos", "Age", "Now", "Pot", "Fit"], draftBoardRows(draft.draft_board), (row) => [row.rank, row.name, row.position, row.age, gradeNumber(row.now), gradeNumber(row.potential), gradeNumber(row.fit || row.grade)])}
      </section>
      <section class="section wide panel-rail">
        ${sectionHead("Upcoming Picks")}
        ${table(["Pick", "Team", "Prospect", "Pos"], draft.upcoming || [], (row) => [`#${row.selection?.overall_pick || ""}`, teamLabel(row.team || row.selection?.team_id), row.prospect?.name || "TBD", row.prospect?.position || ""])}
      </section>
      </div>
    </section>`;
  wireViewJumpButtons();
  const apply = document.getElementById("draftApply");
  if (apply) apply.addEventListener("click", draftApplyCurrent);
  const toUser = document.getElementById("draftToUser");
  if (toUser) toUser.addEventListener("click", () => draftSim("draft_sim_to_user"));
  const all = document.getElementById("draftAll");
  if (all) all.addEventListener("click", () => draftSim("draft_sim_all"));
}

async function draftApplyCurrent() {
  const result = await action("draft_apply_current", { ...savePayload(), team: userTeam(), seed: 7 });
  state.data.draft = result.room;
  showToast(`Draft pick: ${result.status}`);
  renderDraft();
}

async function draftSim(actionName) {
  const result = await action(actionName, { ...savePayload(), team: userTeam(), seed: 7 });
  state.data.draft = result.room;
  showToast(`Draft sim: ${result.result?.applied_count || 0} pick(s)`);
  renderDraft();
}

function renderFreeAgency() {
  const room = state.data.freeagency || {};
  const candidates = room.candidates || [];
  const selected = state.selectedFreeAgent ? candidates.find((item) => item.id === state.selectedFreeAgent) : candidates[0];
  const freeAgencyOpen = room.phase === "free_agency" || Boolean(room.state?.day || room.state?.status === "active");
  const roomTitle = freeAgencyOpen ? "Free Agency" : "Current Free Agents";
  const roomSubtitle = freeAgencyOpen ? `Day ${room.state?.day || "-"} of ${room.state?.day_count || "-"}` : rowLabel(room.phase || "regular_season");
  if (!state.selectedFreeAgent && selected) state.selectedFreeAgent = selected.id;
  els.content.innerHTML = `
    <div class="room-layout">
      <section class="section featured">
        <div class="section-head"><div><h3>${roomTitle}</h3><p class="muted">${escapeHtml(roomSubtitle)}</p></div><span class="pill">${escapeHtml(room.state?.status || room.phase || "market")}</span></div>
        <p class="muted">Payroll ${money(room.cap?.salary_total_millions)} | tax ${signedMoney(room.cap?.tax_space_millions)} | hard cap ${signedMoney(room.cap?.hard_cap_space_millions)}</p>
        ${freeAgencyOpen ? `<div class="toolbar">
          <button id="faAdvanceDay">Sim FA Day</button>
          <button id="faAdvanceEnd">Sim To End</button>
        </div>` : `<div class="court-note">In-season free agents can be investigated and offered contracts. Offseason day controls appear when the league reaches free agency.</div>`}
        ${list((room.bidding_wars || []).map((war) => `${war.player_name}: ${war.offer_count} offers, best ${war.best_team} ${money(war.best_aav)}`))}
      </section>
      <section class="section">
        <div class="section-head"><h3>Market</h3><span class="pill">${candidates.length}</span></div>
        <div class="scroll-list stack">${candidates.slice(0, 70).map(freeAgentButton).join("") || `<div class="empty">No free agents available.</div>`}</div>
      </section>
      <section class="section">
        ${selected ? freeAgentOfferPanel(selected) : `<div class="empty">Select a free agent.</div>`}
      </section>
    </div>`;
  els.content.querySelectorAll("[data-fa-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedFreeAgent = button.dataset.faId;
      renderFreeAgency();
    });
  });
  const submit = document.getElementById("submitFaOffer");
  if (submit) submit.addEventListener("click", submitFreeAgentOffer);
  const day = document.getElementById("faAdvanceDay");
  if (day) day.addEventListener("click", () => advanceFreeAgency("day"));
  const end = document.getElementById("faAdvanceEnd");
  if (end) end.addEventListener("click", () => advanceFreeAgency("end"));
}

async function submitFreeAgentOffer() {
  const player = state.selectedFreeAgent;
  const years = Number(document.getElementById("faYears").value || 1);
  const aav = Number(document.getElementById("faAav").value || 0);
  const result = await action("submit_free_agent_offer", { ...savePayload(), player_id: player, team: userTeam(), years, aav_millions: aav, auto_apply: true, seed: 7 });
  showToast(result.apply_result ? `Signing ${result.apply_result.status}` : `Offer ${result.status}`);
  state.data.freeagency = await action("free_agency_room", { ...savePayload(), team: userTeam(), seed: 7 });
  renderFreeAgency();
}

async function advanceFreeAgency(mode) {
  const result = await action("advance_free_agency", { ...savePayload(), team: userTeam(), mode, seed: 7 });
  state.data.freeagency = result.room;
  showToast(`Free agency advanced: ${result.status}`);
  renderFreeAgency();
}

function renderStaff() {
  const room = state.data.staff || {};
  const report = room.team_report || {};
  const slots = report.gameplay_staff_slots || [];
  const market = room.market?.candidates || [];
  els.content.innerHTML = `
    <div class="grid-2">
      <section class="section featured">
        <div class="section-head"><div><h3>Staff Room</h3><p class="muted">Budget ${money(report.budget?.annual_spend_millions)} / ${money(report.budget?.annual_budget_millions)} spent</p></div><span class="pill">${signedMoney(report.budget?.available_millions)} room</span></div>
        ${table(["Role", "Name", "Grade", "Contract", ""], slots, (row) => [rowLabel(row.slot || row.role), row.name, row.grade, `${money(row.contract?.annual_salary_millions)} x ${row.contract?.years_remaining || 0}`, `<button data-fire-slot="${escapeAttr(row.slot)}">Fire</button>`])}
      </section>
      <section class="section">
        <div class="section-head">
          <h3>Staff Market</h3>
          <select id="staffSlot">
            <option value="">All roles</option>
            ${["head_coach", "offensive_coordinator", "defensive_coordinator", "development_lead", "scouting_lead", "performance_lead"].map((slot) => `<option value="${slot}" ${slot === state.staffSlot ? "selected" : ""}>${rowLabel(slot)}</option>`).join("")}
          </select>
        </div>
        <div class="scroll-list stack">${market.map(staffCandidateCard).join("") || `<div class="empty">No staff candidates.</div>`}</div>
      </section>
    </div>`;
  document.getElementById("staffSlot").addEventListener("change", async (event) => {
    state.staffSlot = event.target.value;
    state.data.staff = await action("staff_room", { ...savePayload(), team: userTeam(), slot: state.staffSlot || undefined, limit: 30 });
    renderStaff();
  });
  els.content.querySelectorAll("[data-staff-id]").forEach((button) => {
    button.addEventListener("click", () => negotiateStaff(button.dataset.staffId, button.dataset.staffSlot, button.dataset.staffAsk, button.dataset.staffYears));
  });
  els.content.querySelectorAll("[data-fire-slot]").forEach((button) => {
    button.addEventListener("click", () => fireStaff(button.dataset.fireSlot));
  });
}

async function negotiateStaff(staffId, slot, ask, years) {
  const result = await action("negotiate_staff", { ...savePayload(), team: userTeam(), staff_id: staffId, slot, salary_millions: ask, years, seed: 7 });
  const negotiation = result.negotiation;
  if (negotiation.accepted) {
    const hired = await action("hire_staff", { ...savePayload(), negotiation_id: negotiation.id });
    showToast(`Staff hire: ${hired.status}`);
    state.data.staff = hired.room;
  } else {
    showToast(`Staff declined: ${negotiation.decision}`, true);
    state.data.staff = result.room;
  }
  renderStaff();
}

async function fireStaff(slot) {
  const result = await action("fire_staff", { ...savePayload(), team: userTeam(), slot });
  state.data.staff = result.room;
  showToast(`Staff move: ${result.status}`);
  renderStaff();
}

function renderLeague() {
  const standings = standingsRows(state.data.standings);
  const east = standings.filter((row) => row.team?.conference === "East");
  const west = standings.filter((row) => row.team?.conference === "West");
  const leaders = state.data.leagueLeaders?.leaders || [];
  const traits = state.data.leagueTraits?.leaders || [];
  els.content.innerHTML = `
    <div class="league-grid">
      <section class="section">${sectionHead("East Standings")}${table(["#", "Team", "W", "L", "Win%"], east, (row, index) => [index + 1, teamLabel(row.team || row), row.wins, row.losses, winPct(row.win_pct)], "league-east")}</section>
      <section class="section">${sectionHead("West Standings")}${table(["#", "Team", "W", "L", "Win%"], west, (row, index) => [index + 1, teamLabel(row.team || row), row.wins, row.losses, winPct(row.win_pct)], "league-west")}</section>
      <section class="section wide">
        <div class="section-head">
          <h3>League Leaders</h3>
          <div class="toolbar compact">
            <select id="leagueStat">${["points", "rebounds", "assists", "steals", "blocks"].map((stat) => `<option value="${stat}" ${stat === state.leagueStat ? "selected" : ""}>${rowLabel(stat)}</option>`).join("")}</select>
            <select id="leagueTrait">${["overall", "offense", "defense", "spacing", "creation", "rim_pressure", "rebounding", "athleticism", "disruption", "rim_protection", "passing"].map((trait) => `<option value="${trait}" ${trait === state.leagueTrait ? "selected" : ""}>${rowLabel(trait)}</option>`).join("")}</select>
          </div>
        </div>
        <div class="league-leader-grid">
          <div>${table(["Player", "Team", "GP", rowLabel(state.leagueStat), "Per G"], leaders, (row) => [row.player?.name || row.player_name, row.team_abbrev || teamLabel(row.team_id), row.games, row[state.leagueStat], row[`${state.leagueStat}_per_game`]], "league-stats")}</div>
          <div>${table(["Player", "Team", "Pos", "MPG", rowLabel(state.leagueTrait), "PTS", "REB", "AST", "Contract"], traits, (row) => [row.player_name, row.team_abbrev, row.position, row.minutes, gradeNumber(row[state.leagueTrait]), row.points_per_game, row.rebounds_per_game, row.assists_per_game, row.contract], "league-traits")}</div>
        </div>
      </section>
      <section class="section wide">${sectionHead("Recent League Events")}${list((state.data.events?.events || []).map(eventLine))}</section>
    </div>`;
  document.getElementById("leagueStat").addEventListener("change", async (event) => {
    state.leagueStat = event.target.value;
    state.data.leagueLeaders = await action("league_leaders", { ...savePayload(), stat: state.leagueStat, limit: 30 });
    renderLeague();
  });
  document.getElementById("leagueTrait").addEventListener("change", async (event) => {
    state.leagueTrait = event.target.value;
    state.data.leagueTraits = await action("league_traits", { ...savePayload(), trait: state.leagueTrait, limit: 40 });
    renderLeague();
  });
}

function renderCalendar() {
  const games = state.data.calendar?.games || state.data.calendar?.calendar || [];
  els.content.innerHTML = `<section class="section">${sectionHead("Calendar")}${table(["Date", "Away", "Home", "Score", "Status", ""], games.slice(0, 120), (game) => [game.date, game.away || game.away_team, game.home || game.home_team, game.score || scoreLine(game), game.status || game.result || "", game.status === "simulated" ? html(`<button data-box-score="${escapeAttr(game.game_id)}">Box Score</button>`) : ""])}</section>`;
  els.content.querySelectorAll("[data-box-score]").forEach((button) => {
    button.addEventListener("click", () => openBoxScore(button.dataset.boxScore));
  });
}

function renderSocial() {
  const posts = state.data.social?.posts || state.data.social?.timeline || [];
  els.content.innerHTML = `<section class="section featured">${sectionHead("Biggest League-Wide Timeline")}${list(posts.map(postLine))}</section>`;
}

function renderSettings() {
  const gameSettings = state.home?.game_settings || {};
  const narrative = state.data.settings || {};
  els.content.innerHTML = `
    <section class="section featured">
      ${sectionHead("Settings")}
      <div class="grid-2">
        <div class="item"><strong>Press Conferences</strong><span class="muted">Forced press interruptions are temporarily ${gameSettings.press_conferences_enabled ? "enabled" : "disabled"}.</span></div>
        <div class="item"><strong>Narrative</strong><span class="muted">${escapeHtml(narrative.status || "")} | ${escapeHtml(narrative.provider || "")} ${escapeHtml(narrative.model || "")}</span></div>
      </div>
      <div class="toolbar">
        <button id="togglePress">${gameSettings.press_conferences_enabled ? "Disable" : "Enable"} Press Conferences</button>
        <button id="leaveGame">Leave Game</button>
      </div>
    </section>`;
  document.getElementById("togglePress").addEventListener("click", async () => {
    await action("update_game_settings", { ...savePayload(), settings: { press_conferences_enabled: !gameSettings.press_conferences_enabled } });
    await refreshHome();
  });
  document.getElementById("leaveGame").addEventListener("click", () => {
    localStorage.removeItem(LAST_SAVE_KEY);
    state.currentSave = "";
    state.home = null;
    state.view = "dashboard";
    state.dashboardTeam = "";
    clearViewCaches();
    render();
  });
}

function renderPlayoffs() {
  const room = state.data.playoffs || {};
  const series = room.series || [];
  const picture = room.picture || {};
  els.content.innerHTML = `
    <section class="moment-screen playoff-moment">
      <div class="moment-topline">
        <button data-view-jump="dashboard">Back to Dashboard</button>
        <div>
          <p class="eyebrow">${escapeHtml(room.current_date || "")}</p>
          <h3>Playoff Command Board</h3>
        </div>
        <div class="dashboard-meta">
          <span>${escapeHtml(rowLabel(room.phase || ""))}</span>
          <span>${escapeHtml(rowLabel(room.round || "picture"))}</span>
          <span>${escapeHtml(rowLabel(room.status || ""))}</span>
        </div>
      </div>
      ${room.champion ? `<div class="headline-block champion-line">Champion: ${escapeHtml(teamLabel(room.champion))}</div>` : ""}
      <div class="playoff-grid">
        <section class="section panel-rail">
          ${sectionHead("East Picture")}
          ${table(["Seed", "Team", "W", "L", "Win%", "Diff"], picture.East || [], (row) => [row.seed, teamLabel(row.team), row.wins, row.losses, winPct(row.win_pct), signedNumber(row.point_diff || 0, 0)])}
        </section>
        <section class="section panel-rail">
          ${sectionHead("West Picture")}
          ${table(["Seed", "Team", "W", "L", "Win%", "Diff"], picture.West || [], (row) => [row.seed, teamLabel(row.team), row.wins, row.losses, winPct(row.win_pct), signedNumber(row.point_diff || 0, 0)])}
        </section>
        <section class="section wide panel-rail">
          ${sectionHead("Bracket")}
          ${series.length ? `<div class="bracket-list">${series.map(seriesCard).join("")}</div>` : `<div class="empty">Bracket will generate when the save reaches play-in/playoffs. Until then, this is the live playoff picture.</div>`}
        </section>
      </div>
    </section>`;
  wireViewJumpButtons();
}

async function openBoxScore(gameId) {
  if (!gameId) return;
  try {
    const box = await action("box_score", { ...savePayload(), game_id: gameId });
    state.modal = {
      title: `${teamLabel(box.away_team)} ${box.away_score} @ ${teamLabel(box.home_team)} ${box.home_score}`,
      subtitle: `${box.mode || "game"} | possessions ${box.possessions || "-"} | OT ${box.overtime_periods || 0}`,
      body: `
        <div class="grid-2">
          <section>${sectionHead("Team Lines")}${table(["Team", "PTS", "REB", "AST", "FG", "3P", "TO"], box.team_lines || [], (row) => [row.team_abbrev || teamLabel(row.team_id), row.points, row.rebounds, row.assists, row.fgm !== undefined ? `${row.fgm}/${row.fga}` : "", row.fg3m !== undefined ? `${row.fg3m}/${row.fg3a}` : "", row.turnovers])}</section>
          <section>${sectionHead("Notes")}${list([box.notes || "No extra notes."])}</section>
        </div>
        ${sectionHead("Player Lines")}
        ${table(["Team", "Player", "Min", "PTS", "REB", "AST", "STL", "BLK", "FG", "3P", "+/-"], box.player_lines || [], (row) => [row.team_abbrev, row.player_name, row.minutes, row.points, row.rebounds, row.assists, row.steals, row.blocks, row.fgm !== undefined ? `${row.fgm}/${row.fga}` : "", row.fg3m !== undefined ? `${row.fg3m}/${row.fg3a}` : "", signedNumber(row.plus_minus || 0, 0)])}
      `,
    };
    renderModal();
  } catch (error) {
    showToast(error.message || String(error), true);
  }
}

function closeModal() {
  state.modal = null;
  renderModal();
}

function renderModal() {
  if (!els.modalRoot) return;
  if (!state.modal) {
    els.modalRoot.hidden = true;
    els.modalRoot.innerHTML = "";
    return;
  }
  els.modalRoot.hidden = false;
  els.modalRoot.innerHTML = `
    <div class="modal-shell" role="dialog" aria-modal="true">
      <header class="modal-head">
        <div>
          <p class="eyebrow">${escapeHtml(state.modal.subtitle || "")}</p>
          <h3>${escapeHtml(state.modal.title || "Detail")}</h3>
        </div>
        <button data-close-modal>Close</button>
      </header>
      <div class="modal-body">${state.modal.body || ""}</div>
    </div>`;
}

function wireViewJumpButtons() {
  els.content.querySelectorAll("[data-view-jump]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.view = button.dataset.viewJump || "dashboard";
      for (const navButton of els.nav.querySelectorAll("button")) navButton.classList.toggle("active", navButton.dataset.view === state.view);
      await ensureViewData(true);
      render();
      window.scrollTo({ top: 0, left: 0 });
    });
  });
}


function metricTile(label, value, detail, grade = "neutral") {
  return `<div class="metric-tile grade-${escapeAttr(grade)}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(detail || "")}</small></div>`;
}

function rankedBarList(rows) {
  const clean = rows.filter((row) => row && row[1] !== undefined && row[1] !== null && row[1] !== "");
  if (!clean.length) return `<div class="empty">No identity metrics yet.</div>`;
  return `<div class="ranked-bars">${clean.map(([label, value, rank, count]) => {
    const leagueCount = Number(count || 30);
    const rankValue = Number(rank || leagueCount);
    const pctValue = clampNumber(((leagueCount - rankValue + 1) / leagueCount) * 100, 4, 100);
    const rankText = rank ? `#${rank}/${leagueCount}` : "";
    const rankClass = rankValue <= 10 ? "good" : rankValue <= 20 ? "neutral" : "bad";
    return `
      <div class="rank-row rank-${rankClass}">
        <div class="rank-label"><span>${escapeHtml(label)}</span><strong>${escapeHtml(rankText)}</strong><em>${Number(value || 0).toFixed(1)}</em></div>
        <div class="meter"><span style="width:${pctValue}%"></span></div>
      </div>`;
  }).join("")}</div>`;
}

function dashboardTeamOptions(selected) {
  return state.teams.map((team) => {
    const value = team.abbrev;
    return `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)} ${escapeHtml(team.name || "")}</option>`;
  }).join("");
}

function teamIdentityRankBlock(dash) {
  const identity = dash.team_identity || {};
  const metrics = identity.metrics || {};
  const ranks = identity.ranks || {};
  const count = identity.league_team_count || 30;
  return `${sectionHead("Team Identity")}
    ${rankedBarList([
      ["Overall", metrics.overall, ranks.overall, count],
      ["Offense", metrics.offense, ranks.offense, count],
      ["Defense", metrics.defense, ranks.defense, count],
      ["Spacing", metrics.spacing, ranks.spacing, count],
      ["Creation", metrics.creation, ranks.creation, count],
      ["Rim Protection", metrics.rim_protection, ranks.rim_protection, count],
      ["Depth", metrics.depth, ranks.depth, count],
      ["Timeline", metrics.age_timeline, ranks.age_timeline, count],
    ])}`;
}

function startingFiveBlock(rows, editable) {
  const bySlot = new Map(rows.filter((row) => row.starting_slot).map((row) => [Number(row.starting_slot), row]));
  const bench = rows.filter((row) => !row.starting_slot).slice(0, 5);
  return `
    <div class="section-head"><h3>Starting 5</h3>${editable ? `<button id="autoStartingFive">Auto</button>` : `<span class="pill">Read-only</span>`}</div>
    <div class="starting-strip">
      ${[1, 2, 3, 4, 5].map((slot) => starterCard(slot, bySlot.get(slot), editable)).join("")}
    </div>
    ${editable ? `<div class="bench-dock">${bench.map((row) => benchChip(row)).join("")}</div>` : ""}`;
}

function starterCard(slot, row, editable) {
  return `<div class="starter-slot" data-start-slot="${slot}">
    <div class="slot-num">${slot}</div>
    ${row ? `<button class="starter-card" ${editable ? `draggable="true" data-drag-player="${escapeAttr(row.id)}"` : ""}>
      <strong>${escapeHtml(row.name)}</strong>
      <span>${escapeHtml(compactPos(row.position))} | ${heightFromRow(row)}</span>
      <small>${Number(mpgFromRow(row) || 0).toFixed(0)} MPG</small>
    </button>` : `<div class="starter-empty">Open</div>`}
    ${editable ? starterSelect(slot, row?.id) : ""}
  </div>`;
}

function starterSelect(slot, selectedId) {
  const rows = rosterRows(state.data.dashboard || {});
  return `<select data-lineup-slot="${slot}">
    ${rows.map((row) => `<option value="${escapeAttr(row.id)}" ${row.id === selectedId ? "selected" : ""}>${escapeHtml(row.name)}</option>`).join("")}
  </select>`;
}

function benchChip(row) {
  return `<button class="bench-chip" draggable="true" data-drag-player="${escapeAttr(row.id)}"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(compactPos(row.position))}</span></button>`;
}

function rotationRatingsBlock(rows, editable) {
  const active = state.dashboardInnerTab || "rotation";
  return `
    <div class="section-head">
      <h3>${active === "rotation" ? "Rotation" : "Ratings"}</h3>
      <div class="tabs mini-tabs">
        <button data-inner-tab="rotation" class="${active === "rotation" ? "active" : ""}">Rotation</button>
        <button data-inner-tab="ratings" class="${active === "ratings" ? "active" : ""}">Ratings</button>
      </div>
    </div>
    ${active === "ratings" ? ratingsTable(rows) : rotationEditor(rows, editable)}`;
}

function rotationEditor(rows, editable) {
  if (!Object.keys(state.rotationDraft).length) {
    state.rotationDraft = Object.fromEntries(rows.map((row) => [row.id, Math.round(Number(row.coach_minutes_projection ?? row.minutes_projection ?? 0))]));
  } else {
    for (const row of rows) {
      if (state.rotationDraft[row.id] === undefined) state.rotationDraft[row.id] = Math.round(Number(row.coach_minutes_projection ?? row.minutes_projection ?? 0));
    }
  }
  const initial = state.rotationDraft;
  const total = Object.values(initial).reduce((sum, value) => sum + Number(value || 0), 0);
  const remaining = 240 - total;
  return `
    <div class="rotation-toolbar">
      <span class="minute-counter ${remaining === 0 ? "ok" : "bad"}">${remaining === 0 ? "240 assigned" : `${signedNumber(remaining, 0)} minutes remaining`}</span>
      ${editable ? `<button id="saveRotation" ${remaining === 0 ? "" : "disabled"}>Set Rotation</button>` : ""}
    </div>
    <div class="rotation-list">
      ${rows.slice(0, 8).map((row) => {
        const value = clampNumber(Number(initial[row.id] ?? row.minutes_projection ?? 0), 0, 48);
        return `<div class="rotation-row">
          <div><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(compactPos(row.position))} | ${statLine(row)} ${activeHealthText(row.health)}</span></div>
          <input type="range" min="0" max="48" step="1" value="${value}" data-minute-player="${escapeAttr(row.id)}" ${editable ? "" : "disabled"} />
          <output>${value}</output>
        </div>`;
      }).join("")}
    </div>
    ${table(["Player", "Start", "Coach", "PTS", "REB", "AST"], rows.slice(0, 8), (row) => [row.name, row.starting_slot ? `#${row.starting_slot}` : "", Number(row.coach_minutes_projection ?? row.minutes_projection ?? 0), statFromRow(row, "points"), statFromRow(row, "rebounds"), statFromRow(row, "assists")], "dashboard-rotation")}`;
}

function ratingsTable(rows) {
  return table(["Player", "Pos", "OVR", "Shot", "Create", "Def", "Space", "Pass", "Reb", "Rim", "Ath"], rows, (row) => [
    row.name,
    compactPos(row.position),
    gradeNumber(rating(row, "overall")),
    gradeNumber(rating(row, "shooting")),
    gradeNumber(rating(row, "creation")),
    gradeNumber(rating(row, "defense")),
    gradeNumber(rating(row, "spacing") || rating(row, "range")),
    gradeNumber(rating(row, "passing")),
    gradeNumber(rating(row, "rebounding")),
    gradeNumber(rating(row, "rim_deterrence")),
    gradeNumber(rating(row, "athleticism")),
  ], "dashboard-ratings");
}

function userConferenceStandings() {
  const standings = standingsRows(state.data.dashboardStandings);
  const user = userTeam();
  const userRow = standings.find((row) => teamLabel(row.team) === user);
  const conference = userRow?.team?.conference || "Conference";
  const rows = standings
    .filter((row) => row.team?.conference === conference)
    .slice(0, 10);

  return `${sectionHead(`${conference} Standings`)}
    ${table(["#", "Team", "W", "L", "Win%"], rows, (row, index) => [
      index + 1,
      teamLabel(row.team) === user
        ? html(`<strong class="user-highlight">${escapeHtml(teamLabel(row.team))}</strong>`)
        : teamLabel(row.team),
      row.wins,
      row.losses,
      winPct(row.win_pct),
    ], "dashboard-standings")}`;
}

function dashboardMonthCalendar() {
  const dash = state.data.dashboard || {};
  const team = teamLabel(dash.team || userTeam());
  const current = state.home?.save?.current_date || "";
  const month = state.calendarMonth || current.slice(0, 7);
  const games = (state.data.dashboardCalendar?.games || []).filter((game) => [game.home, game.home_team, game.away, game.away_team].includes(team));
  const cells = monthCalendarCells(month);

  return `<div class="section-head calendar-head">
      <h3>${escapeHtml(month || "Calendar")}</h3>
      <div class="calendar-head-controls">
        ${simControls()}
        <div class="toolbar compact">
          <button data-calendar-step="-1">‹</button>
          <button data-calendar-step="1">›</button>
        </div>
      </div>
    </div>
    <div class="calendar-grid">
      ${["M", "T", "W", "T", "F", "S", "S"].map((day) => `<div class="calendar-label">${day}</div>`).join("")}
      ${cells.map((cell) => calendarCell(cell, games, current, team)).join("")}
    </div>`;
}

function simControls() {
  return `
    <div class="actions calendar-actions">
      <button data-advance="next-event">Next Event</button>
      <button data-advance="week">Sim Week</button>
      <button data-advance="month">Sim Month</button>
      <button data-advance="deadline">Trade Deadline</button>
      <button data-advance="season-end">End Season</button>
    </div>`;
}

function calendarCell(cell, games, current, team) {
  if (!cell.date) return `<div class="calendar-cell blank"></div>`;
  const dayGames = games.filter((game) => String(game.date || "").slice(0, 10) === cell.date);
  const past = cell.date < String(current).slice(0, 10);
  return `<div class="calendar-cell ${past ? "past" : ""}">
    <strong>${Number(cell.date.slice(-2))}</strong>
    ${dayGames.map((game) => calendarGamePill(game, team, past)).join("")}
  </div>`;
}

function calendarGamePill(game, team, past) {
  const home = game.home || game.home_team;
  const away = game.away || game.away_team;
  const opponent = home === team ? away : home;
  const score = scoreLine(game);
  const result = game.result || resultForTeam(game, team);
  const cls = result === "W" ? "win" : result === "L" ? "loss" : "";
  const gameId = game.game_id || game.id;
  return `<button class="game-pill ${cls}" ${past && gameId ? `data-box-score="${escapeAttr(gameId)}"` : "disabled"}>${escapeHtml(opponent || "")} ${escapeHtml(score || "")}</button>`;
}

function contractsBlock(rows, dash) {
  const seasons = contractSeasons(rows).slice(0, 5);
  const expanded = state.expandedContractSeason;
  return `
    ${expanded ? `<button id="closeContractYear">Back To Contracts</button>` : ""}
    <div class="contract-chart ${expanded ? "expanded" : ""}">
      ${seasons.map((season) => contractYearColumn(season, rows, dash.cap_by_year?.[season], expanded === season)).join("")}
    </div>
    ${table(["Player", "Age", ...seasons], rows, (row) => [row.name, row.age, ...seasons.map((season) => money(row.salary_by_year?.[season]))], "dashboard-contracts")}`;
}

function contractYearColumn(season, rows, cap, expanded) {
  const salaries = rows.map((row) => ({ row, salary: Number(row.salary_by_year?.[season] || 0) })).filter((item) => item.salary > 0).sort((a, b) => b.salary - a.salary);
  const hard = Number(cap?.hard_cap_millions || 230);
  const tax = Number(cap?.tax_line_millions || 190);
  const payroll = Number(cap?.salary_total_millions || salaries.reduce((sum, item) => sum + item.salary, 0));
  const scale = Math.max(hard, payroll, 1);
  return `<button class="contract-year ${expanded ? "active" : ""}" data-contract-season="${escapeAttr(season)}">
    <span class="contract-season">${escapeHtml(season)}</span>
    <span class="cap-line tax" style="bottom:${clampNumber((tax / scale) * 100, 0, 100)}%"><em>Tax</em></span>
    <span class="cap-line hard" style="bottom:${clampNumber((hard / scale) * 100, 0, 100)}%"><em>Hard</em></span>
    <span class="salary-stack" style="height:${clampNumber((payroll / scale) * 100, 0, 100)}%">
      ${salaries.map((item) => `<span class="salary-segment" style="height:${clampNumber((item.salary / Math.max(1, payroll)) * 100, 2, 100)}%" title="${escapeAttr(item.row.name)} ${money(item.salary)}">${escapeHtml(item.salary >= 12 || expanded ? item.row.name : "")}</span>`).join("")}
    </span>
    <span class="contract-total">${money(payroll)}</span>
  </button>`;
}

function wireDashboardOverview(editable) {
  els.content.querySelectorAll("[data-inner-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.dashboardInnerTab = button.dataset.innerTab;
      renderDashboard();
    });
  });
  els.content.querySelectorAll("[data-calendar-step]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.calendarMonth = addMonths(state.calendarMonth || String(state.home?.save?.current_date || "").slice(0, 7), Number(button.dataset.calendarStep || 0));
      await loadDashboardCalendar(state.dashboardTeam || userTeam());
      renderDashboard();
    });
  });
  els.content.querySelectorAll("[data-box-score]").forEach((button) => {
    button.addEventListener("click", () => openBoxScore(button.dataset.boxScore));
  });
  if (!editable) return;
  els.content.querySelectorAll("[data-lineup-slot]").forEach((select) => {
    select.addEventListener("change", () => saveStartingFiveFromControls());
  });
  els.content.querySelectorAll("[data-drag-player]").forEach((node) => {
    node.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", node.dataset.dragPlayer));
  });
  els.content.querySelectorAll("[data-start-slot]").forEach((slot) => {
    slot.addEventListener("dragover", (event) => event.preventDefault());
    slot.addEventListener("drop", (event) => {
      event.preventDefault();
      const playerId = event.dataTransfer.getData("text/plain");
      const select = slot.querySelector("[data-lineup-slot]");
      if (select && playerId) {
        select.value = playerId;
        saveStartingFiveFromControls();
      }
    });
  });
  const auto = document.getElementById("autoStartingFive");
  if (auto) auto.addEventListener("click", () => saveStartingFive({}));
  els.content.querySelectorAll("[data-minute-player]").forEach((input) => {
    input.addEventListener("input", () => {
      state.rotationDraft[input.dataset.minutePlayer] = Number(input.value);
      renderDashboard();
    });
  });
  const saveRotation = document.getElementById("saveRotation");
  if (saveRotation) saveRotation.addEventListener("click", saveRotationMinutes);
}

function wireContractsBlock() {
  const close = document.getElementById("closeContractYear");
  if (close) close.addEventListener("click", () => {
    state.expandedContractSeason = "";
    renderDashboard();
  });
  els.content.querySelectorAll("[data-contract-season]").forEach((button) => {
    button.addEventListener("click", () => {
      state.expandedContractSeason = button.dataset.contractSeason;
      renderDashboard();
    });
  });
}

async function saveStartingFiveFromControls() {
  const slots = {};
  els.content.querySelectorAll("[data-lineup-slot]").forEach((select) => {
    slots[select.dataset.lineupSlot] = select.value;
  });
  await saveStartingFive(slots);
}

async function saveStartingFive(slots) {
  const result = await action("set_starting_five", { ...savePayload(), team: userTeam(), slots });
  if (result.status === "blocked") return showToast(result.reason || "Starting 5 update blocked.", true);
  state.data.dashboard = result.dashboard;
  state.data.statusDashboard = result.dashboard;
  state.rotationDraft = {};
  renderDashboard();
  showToast("Starting 5 updated");
}

async function saveRotationMinutes() {
  const result = await action("set_rotation_minutes", { ...savePayload(), team: userTeam(), minutes: state.rotationDraft });
  if (result.status === "blocked") return showToast(result.reason || "Rotation update blocked.", true);
  state.data.dashboard = result.dashboard;
  state.data.statusDashboard = result.dashboard;
  state.rotationDraft = {};
  renderDashboard();
  showToast("Rotation targets updated");
}

function seriesCard(series) {
  const teams = series.teams || [];
  const scores = series.score || [];
  return `
    <div class="series-card">
      <div class="series-round">${escapeHtml(rowLabel(series.round || ""))}<span>${escapeHtml(rowLabel(series.status || ""))}</span></div>
      <div class="series-team"><strong>${escapeHtml(teamLabel(teams[0]))}</strong><span>${scores[0] ?? 0}</span></div>
      <div class="series-team"><strong>${escapeHtml(teamLabel(teams[1]))}</strong><span>${scores[1] ?? 0}</span></div>
      ${series.winner ? `<div class="series-winner">Winner: ${escapeHtml(teamLabel(series.winner))}</div>` : ""}
    </div>`;
}

function html(value) {
  return { __html: String(value || "") };
}

function gradeNumber(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "";
  return html(`<span class="grade-cell grade-${gradeClass(num)}"><span class="grade-dot"></span>${num.toFixed(1)}</span>`);
}

function gradeText(value, grade = "neutral") {
  return html(`<span class="grade-cell grade-${escapeAttr(grade)}"><span class="grade-dot"></span>${escapeHtml(value)}</span>`);
}

function gradeClass(value, high = 70, low = 50) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "neutral";
  if (num >= high) return "good";
  if (num <= low) return "bad";
  return "neutral";
}

function healthText(health) {
  if (!health) return "";
  const label = health.label || health.status || "";
  if (String(label || "").toLowerCase() === "healthy" || String(health.status || "").toLowerCase() === "healthy") return "";
  const missed = health.games_missed ? `, ${health.games_missed} missed` : "";
  const grade = String(health.status || "").toLowerCase().includes("out") ? "bad" : "good";
  return html(`<span class="grade-cell grade-${grade}"><span class="grade-dot"></span>${escapeHtml(label || "Healthy")}${escapeHtml(missed)}</span>`);
}

function opponentLabel(game) {
  return game.opponent_abbrev || teamLabel(game.opponent_team_id) || "";
}

function contractSeasons(rows) {
  const seasons = new Set();
  for (const row of rows || []) {
    for (const season of Object.keys(row.salary_by_year || {})) seasons.add(season);
  }
  return [...seasons].sort();
}

function pct(numerator, denominator) {
  const den = Number(denominator || 0);
  if (!den) return ".000";
  return (Number(numerator || 0) / den).toFixed(3).replace(/^0/, "");
}

function winPct(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "";
  return num.toFixed(3).replace(/^0/, "");
}

function signedNumber(value, digits = 1) {
  const num = Number(value || 0);
  return `${num >= 0 ? "+" : ""}${num.toFixed(digits)}`;
}

function clampNumber(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function compactPos(value) {
  return String(value || "").toUpperCase().replace("POSITION_", "").split(/[\/,\-\s]/)[0] || "";
}

function statLine(row) {
  return `${Number(statFromRow(row, "points") || 0).toFixed(1)} PTS ${Number(statFromRow(row, "rebounds") || 0).toFixed(1)} REB ${Number(statFromRow(row, "assists") || 0).toFixed(1)} AST`;
}

function activeHealthText(health) {
  if (!health) return "";
  const status = String(health.status || health.label || "").toLowerCase();
  if (!status || status === "healthy" || status === "active") return "";
  return ` | ${health.label || health.status}`;
}

function resultForTeam(game, team) {
  const home = game.home || game.home_team;
  const away = game.away || game.away_team;
  const homeScore = Number(game.home_score ?? game.home_points);
  const awayScore = Number(game.away_score ?? game.away_points);
  if (!Number.isFinite(homeScore) || !Number.isFinite(awayScore)) return "";
  const teamScore = home === team ? homeScore : away === team ? awayScore : null;
  const oppScore = home === team ? awayScore : away === team ? homeScore : null;
  if (teamScore === null || oppScore === null) return "";
  return teamScore > oppScore ? "W" : "L";
}

function monthEndDate(firstDate) {
  const [year, month] = String(firstDate || "").slice(0, 7).split("-").map(Number);
  if (!year || !month) return firstDate;
  return new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10);
}

function addMonths(month, delta) {
  const [year, mon] = String(month || "").split("-").map(Number);
  if (!year || !mon) return month;
  const date = new Date(Date.UTC(year, mon - 1 + delta, 1));
  return date.toISOString().slice(0, 7);
}

function monthCalendarCells(month) {
  const [year, mon] = String(month || "").split("-").map(Number);
  if (!year || !mon) return [];
  const first = new Date(Date.UTC(year, mon - 1, 1));
  const startOffset = (first.getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(year, mon, 0)).getUTCDate();
  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push({ date: "" });
  for (let day = 1; day <= days; day++) cells.push({ date: `${year}-${String(mon).padStart(2, "0")}-${String(day).padStart(2, "0")}` });
  while (cells.length % 7) cells.push({ date: "" });
  return cells;
}

function toggleAsset(side, kind, id) {
  const source = side === "from" ? state.data.tradeUser : state.data.tradePartner;
  const asset = (source.assets || []).find((item) => item.id === id && item.kind === kind);
  if (!asset) return;
  const list = selectedList(side);
  const existing = list.findIndex((item) => item.id === id);
  if (existing >= 0) list.splice(existing, 1);
  else list.push({ kind: asset.kind, id: asset.id, value: asset.value || asset.id, label: asset.label || asset.name || asset.id });
  state.tradeCandidate = null;
  renderTrade();
}

function selectedList(side) {
  return side === "from" ? state.selectedFrom : state.selectedTo;
}

function removeAsset(side, id) {
  const list = selectedList(side);
  const idx = list.findIndex((item) => item.id === id);
  if (idx >= 0) list.splice(idx, 1);
  state.tradeCandidate = null;
  renderTrade();
}

function assetSpec(asset) {
  return { kind: asset.kind, value: asset.value || asset.id };
}

function chips(items, side) {
  if (!items.length) return `<span class="muted">No assets selected.</span>`;
  return items.map((item) => `<span class="chip">${escapeHtml(item.label || item.id)} <button data-remove-side="${side}" data-asset-id="${escapeAttr(item.id)}">x</button></span>`).join("");
}

function tradeReadout(candidate) {
  if (!candidate) return `<div class="empty">Evaluate a package to see legality, acceptance, and value.</div>`;
  const legal = candidate.legality?.status || "unknown";
  const canApply = legal === "legal" && (candidate.accepted_by_all || (candidate.evaluations || []).some((row) => row.perspective_team_id !== state.home?.save?.user_team?.id && row.accepted));
  return `
    <div class="stack">
      <div class="item headline-block"><strong>${escapeHtml(tradeHeadline(candidate))}</strong><span class="pill ${legal === "legal" ? "good" : "bad"}">${escapeHtml(legal)}</span></div>
      ${(candidate.evaluations || []).map(evalLine).join("")}
      <button id="applyBuiltTrade" ${canApply ? "" : "disabled"}>${canApply ? "Accept And Execute" : "Partner Rejects"}</button>
    </div>`;
}

function tradeResultCards(results) {
  if (!results.length) return `<div class="empty">No offers yet.</div>`;
  return results.map((result, index) => `
    <div class="item">
      <strong>${escapeHtml(tradeHeadline(result))}</strong>
      <div class="offer-evals">${(result.evaluations || []).map(evalLine).join("")}</div>
      <div class="toolbar"><button data-apply-finder="${index}">Accept And Execute</button></div>
    </div>`).join("");
}

function offerCard(offer, index) {
  const headline = tradeHeadline(offer).replace(/^Trade completed:/i, "Incoming offer:");
  return `
    <div class="item offer-card">
      <strong>${escapeHtml(headline)}</strong>
      <div class="offer-evals">${(offer.evaluations || []).map(evalLine).join("")}</div>
      <div class="toolbar"><button data-offer-accept="${index}">Accept</button><button data-offer-reject="${index}">Reject</button></div>
    </div>`;
}

function freeAgentButton(player) {
  const selected = state.selectedFreeAgent === player.id;
  return `
    <button class="asset-card ${selected ? "selected" : ""}" data-fa-id="${escapeAttr(player.id)}">
      <span class="asset-title"><span>${escapeHtml(player.name)}</span><span class="value-badge">${money(player.ask_millions)}</span></span>
      <span class="asset-meta">${escapeHtml(player.position)} age ${escapeHtml(player.age)} ${escapeHtml(player.height)} | ${player.mpg} mpg | OVR ${player.ratings?.overall || ""} | ${escapeHtml(player.snapshot || "")}</span>
    </button>`;
}

function freeAgentOfferPanel(player) {
  return `
    <div class="section-head"><div><h3>${escapeHtml(player.name)}</h3><p class="muted">${escapeHtml(player.position)} age ${escapeHtml(player.age)} ${escapeHtml(player.height)}</p></div><span class="pill">${money(player.ask_millions)} ask</span></div>
    <div class="grid-3">
      <div class="item"><strong>Role</strong><span>${player.mpg} MPG | ${player.ppg} PPG</span></div>
      <div class="item"><strong>Ratings</strong><span>OVR ${player.ratings?.overall || ""} | DEF ${player.ratings?.defense || ""}</span></div>
      <div class="item"><strong>Fit</strong><span>${player.team_fit_score ?? "n/a"}</span></div>
    </div>
    <div class="form-grid">
      <label>AAV<input id="faAav" type="number" min="1.9" step="0.1" value="${Number(player.ask_millions || 2).toFixed(1)}" /></label>
      <label>Years<input id="faYears" type="number" min="1" max="5" step="1" value="2" /></label>
      <span></span>
      <button id="submitFaOffer">Make Offer</button>
    </div>`;
}

function staffCandidateCard(candidate) {
  return `
    <div class="item">
      <strong>${escapeHtml(candidate.name)} <span class="pill">${Number(candidate.grade || 0).toFixed(1)}</span></strong>
      <div class="asset-meta">${escapeHtml(rowLabel(candidate.slot))} | ${escapeHtml(candidate.archetype || "")} | ask ${money(candidate.asking_salary_millions)} x ${candidate.asking_years || 2}</div>
      <div class="toolbar"><button data-staff-id="${escapeAttr(candidate.id)}" data-staff-slot="${escapeAttr(candidate.slot)}" data-staff-ask="${escapeAttr(candidate.asking_salary_millions)}" data-staff-years="${escapeAttr(candidate.asking_years || 2)}">Offer And Hire</button></div>
    </div>`;
}

function draftBoardRows(board) {
  return (board?.entries || []).map((entry) => {
    const prospect = entry.prospect || entry;
    const scout = entry.scout_display || prospect.scout_display || {};
    return {
      rank: entry.board_rank || prospect.rank || "",
      name: prospect.name,
      position: prospect.position,
      age: prospect.age,
      now: scout.now ?? prospect.now ?? prospect.current_rating ?? prospect.current_ability,
      potential: scout.potential || prospect.potential || prospect.potential_rating,
      fit: entry.fit_grade || entry.risk_adjusted_grade || entry.grade,
    };
  });
}

function evalLine(row) {
  const score = Number(row.acceptance_score || 0);
  const cls = row.accepted ? "good" : "warn";
  return `<div class="item"><strong>${escapeHtml(row.team_abbrev || row.perspective_team_id)} <span class="pill ${cls}">${escapeHtml(row.decision || "")}</span></strong><span class="asset-meta">net ${Number(row.net_value || 0).toFixed(1)} | threshold ${Number(row.acceptance_threshold || 0).toFixed(1)} | acceptance ${score.toFixed(0)}/100</span></div>`;
}

function rosterRows(dash) {
  return dash?.players || dash?.roster || dash?.rotation || dash?.rows || [];
}

function staffRows(dash) {
  return dash?.staff || dash?.staff_rows || dash?.staff_slots || [];
}

function standingsRows(data) {
  return data?.standings || data?.rows || data?.teams || [];
}

function dashboardFacts(dash) {
  const facts = [];
  const capSummary = capFact(dash?.cap);
  const recordSummary = recordFact(dash?.record);
  if (capSummary) facts.push(capSummary);
  if (recordSummary) facts.push(recordSummary);
  if (dash?.rotation_summary) facts.push(textValue(dash.rotation_summary));
  const startingNames = (dash?.starting_five || []).map((row) => row.name || row.player).filter(Boolean);
  if (startingNames.length) facts.push(`Starting 5: ${startingNames.join(", ")}`);
  return facts.length ? facts : ["Use the tabs for roster, ratings, contracts, staff, and Starting 5."];
}

function recordFact(record) {
  if (!record) return "";
  if (typeof record === "string") return `Record: ${record}`;
  const wins = record.wins ?? record.win ?? record.W;
  const losses = record.losses ?? record.loss ?? record.L;
  if (wins !== undefined && losses !== undefined) return `Record: ${wins}-${losses}`;
  return `Record: ${textValue(record)}`;
}

function capFact(cap) {
  if (!cap) return "";
  if (typeof cap === "string") return `Cap: ${cap}`;
  const payroll = cap.salary_total_millions ?? cap.payroll_millions ?? cap.payroll;
  const tax = cap.tax_space_millions ?? cap.tax_room_millions ?? cap.tax_room;
  const hard = cap.hard_cap_space_millions ?? cap.hard_cap_room_millions ?? cap.hard_cap_room;
  const pieces = [];
  if (payroll !== undefined) pieces.push(`payroll ${money(payroll)}`);
  if (tax !== undefined) pieces.push(`tax ${signedMoney(tax)}`);
  if (hard !== undefined) pieces.push(`hard cap ${signedMoney(hard)}`);
  return pieces.length ? `Cap: ${pieces.join(" | ")}` : `Cap: ${textValue(cap)}`;
}

function listSection(title, items) {
  return `<section class="section">${sectionHead(title)}${list(items)}</section>`;
}

function sectionHead(title) {
  return `<div class="section-head"><h3>${escapeHtml(title)}</h3></div>`;
}

function list(items) {
  if (!items.length) return `<div class="empty">Nothing to show yet.</div>`;
  return `<div class="list">${items.map((item) => `<div class="item">${typeof item === "string" ? item : textValue(item)}</div>`).join("")}</div>`;
}

function table(headers, rows, mapper, tableId = "table") {
  if (!rows || !rows.length) return `<div class="empty">Nothing to show yet.</div>`;
  const mapped = rows.map((row, index) => ({ row, cells: mapper(row, index) }));
  const sort = state.sorts[tableId];
  if (sort) {
    mapped.sort((a, b) => compareCell(a.cells[sort.index], b.cells[sort.index], sort.direction));
  }
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${headers.map((header, index) => `<th><button class="sort-head" data-sort-table="${escapeAttr(tableId)}" data-sort-index="${index}">${escapeHtml(header)}${sort?.index === index ? (sort.direction === "asc" ? " ↑" : " ↓") : ""}</button></th>`).join("")}</tr></thead><tbody>${mapped.map(({ cells }) => `<tr>${cells.map((cell) => `<td>${formatCell(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function compareCell(a, b, direction) {
  const av = sortValue(a);
  const bv = sortValue(b);
  const sign = direction === "asc" ? 1 : -1;
  if (typeof av === "number" && typeof bv === "number") return (av - bv) * sign;
  return String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" }) * sign;
}

function sortValue(value) {
  if (typeof value === "object" && value?.__html !== undefined) value = value.__html.replace(/<[^>]+>/g, " ");
  if (typeof value === "number") return value;
  const text = String(value ?? "").replace(/<[^>]+>/g, " ").trim();
  const numeric = Number(text.replace(/[$,%+]/g, ""));
  return Number.isFinite(numeric) && text.match(/[0-9]/) ? numeric : text;
}

function formatCell(value) {
  if (value === undefined || value === null || value === "") return "";
  if (typeof value === "object" && value.__html !== undefined) return value.__html;
  if (typeof value === "number") return escapeHtml(Number.isInteger(value) ? String(value) : value.toFixed(1));
  return String(value).includes("<button") ? String(value) : escapeHtml(String(value));
}

function eventLine(event) {
  if (typeof event === "string") return escapeHtml(event);
  const date = event.date || event.created_at || "";
  const kind = event.kind || event.type || "";
  const text = event.text || event.headline || event.summary || event.description || textValue(event);
  return `<strong>${escapeHtml(date)} ${escapeHtml(kind)}</strong><span>${escapeHtml(text)}</span>`;
}

function postLine(post) {
  if (typeof post === "string") return escapeHtml(post);
  const header = `${post.date || ""} ${post.handle || post.author || ""} [${post.sentiment ?? "0.0"}] ${post.subject || post.event_subject || ""}`;
  return `<strong>${escapeHtml(header)}</strong><span>${escapeHtml(post.text || post.body || post.content || "")}</span>`;
}

function scoreLine(game) {
  if (game.away_score !== undefined && game.home_score !== undefined) return `${game.away_score}-${game.home_score}`;
  return "";
}

function contractText(row) {
  if (row.contract || row.contract_summary || row.contracts) return row.contract || row.contract_summary || row.contracts;
  if (row.salary_by_year) return Object.entries(row.salary_by_year).map(([season, salary]) => `${season} ${money(salary)}`).join(" / ");
  return "";
}

function rating(row, key) {
  const ratings = row.ratings || row.display_ratings || row.attributes || row.traits || {};
  if (key === "offense") {
    const parts = [ratings.shooting, ratings.creation, ratings.passing].map(Number).filter(Number.isFinite);
    if (parts.length) return parts.reduce((sum, item) => sum + item, 0) / parts.length;
  }
  if (key === "rebound") key = "rebounding";
  return row[key] ?? ratings[key] ?? ratings[key.toUpperCase()] ?? "";
}

function statsContextLabel(context) {
  if (!context) return "";
  if (typeof context === "string") return context;
  return context.label || context.source || textValue(context);
}

function heightFromRow(row) {
  if (row.height) return row.height;
  if (row.height_inches) {
    const inches = Math.round(Number(row.height_inches));
    return `${Math.floor(inches / 12)}'${inches % 12}"`;
  }
  return "";
}

function mpgFromRow(row) {
  return row.mpg ?? row.display_mpg ?? row.season_minutes_per_game ?? row.minutes_projection ?? "";
}

function statFromRow(row, stat) {
  const key = `${stat}_per_game`;
  const short = { points: "ppg", rebounds: "rpg", assists: "apg" }[stat];
  return row[short] ?? row[key] ?? "";
}

function tradeHeadline(candidate) {
  return candidate?.headline || candidate?.summary?.headline || candidate?.proposal?.headline || candidate?.proposal?.id || "Trade offer";
}

function money(value) {
  if (value === undefined || value === null || value === "") return "";
  const num = Number(value);
  if (Number.isFinite(num)) return `$${num.toFixed(1)}M`;
  return String(value);
}

function signedMoney(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "";
  return `$${num >= 0 ? "+" : ""}${num.toFixed(1)}M`;
}

function tabLabel(tab) {
  return { starting5: "Starting 5" }[tab] || tab[0].toUpperCase() + tab.slice(1);
}

function titleForView(view) {
  return {
    dashboard: "Team Dashboard",
    trade: "Trade Room",
    offers: "AI Offers",
    draft: "Draft Room",
    playoffs: "Playoffs",
    freeagency: "Free Agency",
    freeagents: "Current Free Agents",
    staff: "Staff Room",
    league: "League",
    calendar: "Calendar",
    social: "Social / Morale",
    settings: "Settings",
  }[view] || "Dashboard";
}

function rowLabel(value) {
  return String(value || "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function teamLabel(team) {
  if (!team) return "";
  if (typeof team === "string") return team.replace("team_", "").toUpperCase();
  return team.abbrev || team.name || team.id || textValue(team);
}

function userTeam() {
  return teamLabel(state.home?.save?.user_team || state.home?.save?.team || "");
}

function setBusy(isBusy) {
  state.busy = isBusy;
  document.body.classList.toggle("busy", isBusy);
  for (const button of document.querySelectorAll("button")) button.disabled = isBusy;
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("bad", isError);
  els.toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    els.toast.hidden = true;
  }, 3800);
}

function textValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(textValue).join(", ");
  if (typeof value === "object") {
    return Object.entries(value).map(([key, item]) => `${key}: ${textValue(item)}`).join(" | ");
  }
  return String(value);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}
