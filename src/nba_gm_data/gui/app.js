// This client owns interaction and presentation only. Basketball legality,
// simulation, and save mutations must remain behind the Python action API.
const state = {
  busy: false,
  teams: [],
  saves: [],
  currentSave: "",
  home: null,
  view: "dashboard",
  dashboardTab: "overview",
  dashboardTeam: "",
  dashboardStandingsConference: "",
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
  playerFinder: null,
  data: {},
  startingDraft: null,
  startingSavedSignature: "",
  startingPickerSlot: null,
  developmentPlayerIds: [],
  developmentSelectionTouched: false,
  developmentSeenSignature: "",
  developmentNewSignature: "",
  hydrating: false,
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
    if (mode === "next-season") return advance({ next_event: true });
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
  state.currentSave = localStorage.getItem(LAST_SAVE_KEY) || "";
  state.hydrating = Boolean(state.currentSave);
  render();
  try {
    const status = await apiGet("/api/status");
    els.runtime.textContent = `${status.engine} | ${status.protocol_version}`;
    els.startupRuntime.textContent = `${status.engine} | ${status.protocol_version}`;
    await loadTeams();
    await loadSaves();
  } catch (error) {
    state.hydrating = false;
    render();
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
    state.hydrating = false;
    state.home = null;
    render();
    return;
  }
  state.home = await action("home", savePayload());
  if (!state.dashboardTeam) state.dashboardTeam = userTeam();
  syncDefaultPartner();
  applyPhaseRouting();
  await ensureViewData(true);
  state.hydrating = false;
  render();
}

function clearViewCaches() {
  state.data = {};
  state.tradeCandidate = null;
  state.tradeResults = [];
  state.startingDraft = null;
  state.startingSavedSignature = "";
  state.startingPickerSlot = null;
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
    state.data.dashboardSummaryLeaders = await action("dashboard_summary_leaders", { ...savePayload(), limit: 5 });
    state.data.dashboardStaffMarket = await action("staff_market", { ...savePayload(), limit: 60 });
    state.data.dashboardFreeAgents = await action("free_agents", { ...savePayload(), team, limit: 60 });
    state.data.dashboardTrends = await action("dashboard_trends", { ...savePayload(), team });
    state.data.dashboardAssets = await action("team_assets", { ...savePayload(), team });
    state.data.dashboardOffers = await action("user_trade_offers", savePayload());
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
  if (!(await ensureStartingFiveReadyForAdvance())) return;
  const previousDevelopmentSignature = developmentTrendSignature();
  const result = await action("advance_save", { ...savePayload(), ...payload });
  state.home = result.home;
  clearViewCaches();
  applyPhaseRouting();
  await ensureViewData(true);
  syncDevelopmentAdvanceState(previousDevelopmentSignature);
  render();
  showToast(`Advanced to ${state.home?.save?.current_date || "next date"}`);
}

async function ensureStartingFiveReadyForAdvance() {
  const user = userTeam();
  if (!user) return true;
  let dash = state.data.statusDashboard;
  if (!dash) {
    dash = await action("team_dashboard", { ...savePayload(), team: user });
    state.data.statusDashboard = dash;
    if (state.view === "dashboard" && (!state.dashboardTeam || state.dashboardTeam === user)) {
      state.data.dashboard = dash;
    }
  }

  const rows = rosterRows(dash);
  const saved = savedStartingFiveMap(rows, dash);
  const savedComplete = startingMapComplete(saved);
  const isUserDashboard =
    state.view === "dashboard" &&
    teamLabel((state.data.dashboard || dash || {}).team || state.dashboardTeam || user) === user;

  if (isUserDashboard) {
    ensureStartingDraft(rows);
    if (!startingMapComplete(state.startingDraft)) {
      await showStartingFiveAdvanceBlock("Set a complete Starting 5 before simming.");
      return false;
    }
    if (startingDraftChanged(rows)) {
      await showStartingFiveAdvanceBlock("Press Set to save your Starting 5 before simming.");
      return false;
    }
  }

  if (!savedComplete) {
    await showStartingFiveAdvanceBlock("Set a complete Starting 5 before simming.");
    return false;
  }
  return true;
}

async function showStartingFiveAdvanceBlock(message) {
  state.view = "dashboard";
  state.dashboardTeam = userTeam();
  syncNavActive();
  await ensureViewData(true);
  render();
  showToast(message, true);
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
  if (state.view !== "dashboard") stopDashboardRotatorClock();
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
  const viewedTeam = teamLabel(dash.team || state.dashboardTeam || userTeam());
  const editable = !state.hydrating && viewedTeam === userTeam();

  state.dashboardTab = "overview";

  els.content.innerHTML = `
    <section class="section dashboard-shell">
      <div id="dashboardTab"></div>
    </section>`;

  renderDashboardTab(rows, dash, editable);
}

function renderDashboardTab(rows) {
  const target = document.getElementById("dashboardTab");
  const dash = state.data.dashboard || {};
  const editable = !state.hydrating && teamLabel(dash.team || state.dashboardTeam) === userTeam();
  const readonlyClass = editable ? "" : " readonly-card";
  if (state.dashboardTab === "overview") {
    target.innerHTML = `
      <div class="dashboard-overview">
        <section class="section panel-rail identity-card">${teamIdentityRankBlock(dash)}</section>
        <section class="section panel-rail starting-card">${startingFiveBlock(rows, editable)}</section>
        <section class="section panel-rail player-summary-card">${dashboardPlayerSummaryTable(rows)}</section>
        <section class="section panel-rail summary-side-card">${summaryLeaderRotator()}</section>       
        <section class="section panel-rail staff-card">${staffDashboardCard(rows, dash, editable)}</section>
        <section class="section panel-rail standings-card">${userConferenceStandings()}</section>
        <section class="section panel-rail calendar-card">${dashboardMonthCalendar()}</section>
        <section class="section panel-rail contract-chart-card">${contractChartCard(rows, dash)}</section>
        <section class="section panel-rail dashboard-actions-card${readonlyClass}">${dashboardActionsCard(editable)}</section>
        <section class="section panel-rail staff-market-card${readonlyClass}">${dashboardStaffMarketCard(editable)}</section>
        <section class="section panel-rail free-agent-market-card${readonlyClass}">${dashboardFreeAgentMarketCard(editable)}</section>
        <section class="section panel-rail standings-trend-card">${standingsTrendCard()}</section>
        <section class="section panel-rail development-trend-card">${developmentTrendCard(rows)}</section>
        <section class="section panel-rail draft-picks-card">${draftPicksCard()}</section>
        <section class="section panel-rail events-card">${leagueEventRotator()}</section>
      </div>`;
    wireDashboardOverview(editable);
    startLeagueEventRotator();
    startSummaryLeaderRotator();
    startDashboardMarketRotators();
    return;
  }
  target.innerHTML = contractsBlock(rows, dash);
  wireContractsBlock();
}

const DASHBOARD_ROTATOR_MS = 6500;
const dashboardRotatorState = {
  frame: null,
  elapsed: 0,
  lastFrame: 0,
  paused: false,
};

function startLeagueEventRotator() {
  stopDashboardRotatorClock();
}

function startSummaryLeaderRotator() {
  const rotator = document.querySelector("[data-summary-leader-rotator]");
  if (!rotator) return;
  const select = document.getElementById("summaryLeaderSelect");
  setSummaryLeaderActive(Number(select?.value || 0));
  if (select) {
    select.addEventListener("change", () => {
      setSummaryLeaderActive(Number(select.value || 0));
      resetDashboardRotatorProgress();
    });
  }
}

function startDashboardMarketRotators() {
  const rotators = Array.from(document.querySelectorAll("[data-market-rotator]"));
  rotators.forEach((rotator) => {
    setMarketRotatorActive(rotator, Number(rotator.dataset.marketIndex || 0));
  });
  document.querySelectorAll("[data-market-select]").forEach((select) => {
    select.addEventListener("change", () => {
      const rotator = document.querySelector(`[data-market-rotator][data-market-id="${select.dataset.marketSelect}"]`);
      if (rotator) setMarketRotatorActive(rotator, Number(select.value || 0));
      resetDashboardRotatorProgress();
    });
  });
  startDashboardRotatorClock();
}

function stopDashboardRotatorClock() {
  if (dashboardRotatorState.frame) cancelAnimationFrame(dashboardRotatorState.frame);
  dashboardRotatorState.frame = null;
  dashboardRotatorState.elapsed = 0;
  dashboardRotatorState.lastFrame = 0;
  dashboardRotatorState.paused = false;
}

function startDashboardRotatorClock() {
  stopDashboardRotatorClock();
  wireDashboardRotatorPauseCards();
  resetDashboardRotatorProgress();
  dashboardRotatorState.lastFrame = performance.now();
  const step = (now) => {
    const delta = now - dashboardRotatorState.lastFrame;
    dashboardRotatorState.lastFrame = now;
    if (!dashboardRotatorState.paused) {
      dashboardRotatorState.elapsed += delta;
      while (dashboardRotatorState.elapsed >= DASHBOARD_ROTATOR_MS) {
        dashboardRotatorState.elapsed -= DASHBOARD_ROTATOR_MS;
        advanceDashboardRotatorCards();
      }
      updateDashboardRotatorProgress();
    }
    dashboardRotatorState.frame = requestAnimationFrame(step);
  };
  dashboardRotatorState.frame = requestAnimationFrame(step);
}

function resetDashboardRotatorProgress() {
  dashboardRotatorState.elapsed = 0;
  updateDashboardRotatorProgress();
}

function updateDashboardRotatorProgress() {
  const scale = clampNumber(1 - dashboardRotatorState.elapsed / DASHBOARD_ROTATOR_MS, 0, 1);
  document.querySelectorAll(".dashboard-overview .rotator-progress span").forEach((span) => {
    span.style.transform = `scaleX(${scale})`;
  });
}

function wireDashboardRotatorPauseCards() {
  document.querySelectorAll(".events-card, .summary-side-card, .staff-market-card, .free-agent-market-card").forEach((card) => {
    card.addEventListener("mouseenter", () => {
      dashboardRotatorState.paused = true;
      card.closest(".dashboard-overview")?.classList.add("rotators-paused");
    });
    card.addEventListener("mouseleave", () => {
      dashboardRotatorState.paused = false;
      dashboardRotatorState.lastFrame = performance.now();
      card.closest(".dashboard-overview")?.classList.remove("rotators-paused");
    });
  });
}

function advanceDashboardRotatorCards() {
  advanceLeagueEventRotator();
  advanceSummaryLeaderRotator();
  advanceMarketRotators();
}

function advanceLeagueEventRotator() {
  const rotator = document.querySelector("[data-event-rotator]");
  const dataNode = document.getElementById("leagueEventRotatorData");
  if (!rotator || !dataNode) return;
  let events = [];
  try {
    events = JSON.parse(dataNode.textContent || "[]");
  } catch {
    events = [];
  }
  if (events.length <= 1) return;
  const current = Number(rotator.dataset.eventIndex || 0);
  const next = (current + 1) % events.length;
  const body = rotator.querySelector(".event-rotator-body");
  rotator.dataset.eventIndex = String(next);
  if (body) {
    body.innerHTML = leagueEventSlide(events[next]);
    body.classList.remove("event-swap");
    void body.offsetWidth;
    body.classList.add("event-swap");
  }
}

function setSummaryLeaderActive(value) {
  const rotator = document.querySelector("[data-summary-leader-rotator]");
  if (!rotator) return;
  const slides = Array.from(rotator.querySelectorAll(".summary-leader-slide"));
  if (!slides.length) return;
  const index = Math.max(0, Math.min(slides.length - 1, Number(value || 0)));
  slides.forEach((slide, slideIndex) => slide.classList.toggle("active", slideIndex === index));
  const select = document.getElementById("summaryLeaderSelect");
  if (select) select.value = String(index);
}

function advanceSummaryLeaderRotator() {
  const rotator = document.querySelector("[data-summary-leader-rotator]");
  if (!rotator) return;
  const slides = Array.from(rotator.querySelectorAll(".summary-leader-slide"));
  if (slides.length <= 1) return;
  const current = Math.max(0, slides.findIndex((slide) => slide.classList.contains("active")));
  setSummaryLeaderActive((current + 1) % slides.length);
}

function advanceMarketRotators() {
  document.querySelectorAll("[data-market-rotator]").forEach((rotator) => {
    const slides = Array.from(rotator.querySelectorAll(".market-slide"));
    if (slides.length <= 1) return;
    const current = Number(rotator.dataset.marketIndex || 0);
    const next = (current + 1) % slides.length;
    setMarketRotatorActive(rotator, next);
  });
}

function setMarketRotatorActive(rotator, value) {
  const slides = Array.from(rotator.querySelectorAll(".market-slide"));
  if (!slides.length) return;
  const index = Math.max(0, Math.min(slides.length - 1, Number(value || 0)));
  slides.forEach((slide, slideIndex) => slide.classList.toggle("active", slideIndex === index));
  rotator.dataset.marketIndex = String(index);
  const select = document.querySelector(`[data-market-select="${rotator.dataset.marketId}"]`);
  if (select) select.value = String(index);
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
      ${tradeOffersList(offers)}
    </section>`;
  wireOfferButtons(els.content, offers);
}

function tradeOffersList(offers) {
  return `<div class="stack">${offers.length ? offers.map((offer, index) => offerCard(offer, index)).join("") : `<div class="empty">No active AI offers to your team.</div>`}</div>`;
}

function tradeOffersModalBody(offers) {
  return `
    <p class="muted">Only active incoming offers remain here. Deadline-expired offers are cleared by the engine.</p>
    ${tradeOffersList(offers)}`;
}

async function openTradeOffersModal() {
  if (!state.data.dashboardOffers) {
    state.data.dashboardOffers = await action("user_trade_offers", savePayload());
  }
  const offers = state.data.dashboardOffers?.offers || [];
  state.modal = {
    kind: "tradeOffers",
    title: "AI Trade Offers To You",
    subtitle: `${offers.length} active incoming offer${offers.length === 1 ? "" : "s"}`,
    offers,
    body: tradeOffersModalBody(offers),
  };
  renderModal();
}

function wireOfferButtons(root, offers) {
  root.querySelectorAll("[data-offer-accept]").forEach((button) => {
    button.addEventListener("click", () => respondOffer(offers[Number(button.dataset.offerAccept)], "accept"));
  });
  root.querySelectorAll("[data-offer-reject]").forEach((button) => {
    button.addEventListener("click", () => respondOffer(offers[Number(button.dataset.offerReject)], "reject"));
  });
}

async function respondOffer(offer, decision) {
  const proposalId = offer?.proposal?.id || offer?.id;
  const result = await action("respond_user_trade_offer", { ...savePayload(), proposal_id: proposalId, decision });
  state.data.offers = result.offers;
  state.data.dashboardOffers = result.offers;
  showToast(`Offer ${result.status}`);
  if (state.modal?.kind === "tradeOffers") {
    await refreshHome();
    const offers = state.data.dashboardOffers?.offers || [];
    state.modal = {
      kind: "tradeOffers",
      title: "AI Trade Offers To You",
      subtitle: `${offers.length} active incoming offer${offers.length === 1 ? "" : "s"}`,
      offers,
      body: tradeOffersModalBody(offers),
    };
    renderModal();
    return;
  }
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
          </div>` : `
          <div class="headline-block">
            <p class="eyebrow">Draft complete</p>
            <h3>${escapeHtml(draft.year || "")} Draft Finished</h3>
            <p class="muted">Advance to the next stage when you are ready.</p>
          </div>
          <div class="toolbar">
            <button id="draftAdvanceStage">Advance To Next Stage</button>
          </div>`}
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
  const advanceStage = document.getElementById("draftAdvanceStage");
  if (advanceStage) advanceStage.addEventListener("click", draftAdvanceStage);
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

async function draftAdvanceStage() {
  const result = await action("advance_save", { ...savePayload(), next_event: true, seed: 7 });
  state.home = result.home;
  clearViewCaches();
  applyPhaseRouting();
  await ensureViewData(true);
  render();
  showToast(`Advanced to ${state.home?.save?.current_date || "next stage"}`);
}

function renderFreeAgency() {
  const room = state.data.freeagency || {};
  const candidates = room.candidates || [];
  const selected = state.selectedFreeAgent ? candidates.find((item) => item.id === state.selectedFreeAgent) : candidates[0];
  const freeAgencyStatus = String(room.state?.status || "");
  const freeAgencyCompleted = freeAgencyStatus === "completed";
  const freeAgencyOpen = !freeAgencyCompleted && (room.phase === "free_agency" || Boolean(room.state?.day || freeAgencyStatus === "active"));
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
        </div>` : freeAgencyCompleted ? `
        <div class="headline-block">
          <p class="eyebrow">Free agency complete</p>
          <h3>Market Closed</h3>
          <p class="muted">Advance to the next phase when you are ready.</p>
        </div>
        <div class="toolbar">
          <button id="faAdvanceStage">Advance To Next Phase</button>
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
  const advanceStage = document.getElementById("faAdvanceStage");
  if (advanceStage) advanceStage.addEventListener("click", freeAgencyAdvanceStage);
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

async function freeAgencyAdvanceStage() {
  const result = await action("advance_save", { ...savePayload(), next_event: true, seed: 7 });
  state.home = result.home;
  clearViewCaches();
  applyPhaseRouting();
  if (state.view === "freeagents" || state.view === "freeagency") state.view = "dashboard";
  await ensureViewData(true);
  render();
  showToast(`Advanced to ${state.home?.save?.current_date || "next phase"}`);
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

function staffDashboardCard(rows, dash, editable = true) {
  const room = state.data.staff || {};
  const report = room.team_report || {};
  const staff = staffRows(dash).length
    ? staffRows(dash)
    : report.gameplay_staff_slots || [];
  const budget = staffBudgetSummary(staff);

  return `
    ${sectionHead("Staff", `${money(budget.used)} / ${money(budget.max)}`)}
    <div class="staff-dashboard-grid">
      <div class="staff-role-list">
        ${staff.length
          ? staff.map((row) => staffRoleButton(row, editable)).join("")
          : `<div class="empty">No staff data loaded.</div>`}
      </div>
      ${staffBudgetMiniChart(staff)}
    </div>`;
}

function staffRoleButton(row, editable = true) {
  const role = row.slot || row.role || "";
  const name = staffName(row);
  const grade = staffGrade(row);
  const aav = staffAav(row);
  const years = staffYears(row);

  return `<button class="staff-role-button" data-staff-role="${escapeAttr(role)}" ${editable ? "" : "disabled"}>
    <span class="staff-role">${escapeHtml(rowLabel(role))}</span>
    <span class="staff-name-row">
      <strong>${escapeHtml(name)}</strong>
      <em>${grade !== "" ? Number(grade).toFixed(1) : "—"}</em>
    </span>
    <span class="staff-meta">
      ${aav ? `${money(aav)}${years ? ` x ${years}` : ""}` : "No contract data"}
    </span>
  </button>`;
}

function staffBudgetSummary(staff) {
  const paidStaff = staff
    .map((row, index) => ({
      row,
      index,
      aav: staffAav(row),
    }))
    .filter((item) => item.aav > 0);
  return {
    paidStaff,
    used: paidStaff.reduce((sum, item) => sum + item.aav, 0),
    max: staffBudgetMillions(staff, paidStaff),
  };
}

function staffBudgetMiniChart(staff) {
  const budgetSummary = staffBudgetSummary(staff);
  const paidStaff = budgetSummary.paidStaff.sort((a, b) => b.aav - a.aav);
  const budget = budgetSummary.max;
  const total = budgetSummary.used;
  const scale = Math.max(budget, total, 1);

  return `<div class="staff-cap-mini">
    <div class="staff-cap-column">
      <span class="staff-budget-line" style="bottom:${clampNumber((budget / scale) * 100, 0, 100)}%">
      </span>

      <span class="staff-salary-stack" style="height:${clampNumber((total / scale) * 100, 0, 100)}%">
        ${paidStaff.map((item) => `<span
          class="staff-salary-segment staff-salary-${item.index % 8}"
          style="height:${clampNumber((item.aav / Math.max(1, total)) * 100, 4, 100)}%"
          title="${escapeAttr(rowLabel(item.row.slot || item.row.role))}: ${escapeAttr(staffName(item.row))} ${money(item.aav)}"
        ></span>`).join("")}
      </span>
    </div>
  </div>`;
}

function staffAav(row) {
  return normalizeStaffMoney(
    row.aav_millions ??
    row.salary_millions ??
    row.contract_aav_millions ??
    row.annual_salary_millions ??
    row.asking_salary_millions ??
    row.aav ??
    row.salary ??
    row.contract?.aav_millions ??
    row.contract?.salary_millions ??
    row.contract?.annual_salary_millions ??
    row.contract?.aav ??
    row.contract?.salary ??
    row.staff?.aav_millions ??
    row.staff?.salary_millions ??
    row.staff?.contract?.aav_millions ??
    row.staff?.contract?.salary_millions ??
    0
  );
}

function staffName(row) {
  return (
    row.name ??
    row.staff?.name ??
    row.person?.name ??
    row.employee?.name ??
    "Vacant"
  );
}

function staffGrade(row) {
  const direct = (
    row.grade ??
    row.rating ??
    row.overall ??
    row.staff_grade ??
    row.reputation_grade_target ??
    row.staff?.grade ??
    row.staff?.rating ??
    row.staff?.overall ??
    row.evaluation?.grade ??
    ""
  );
  if (direct !== "") return direct;
  const traitValues = [
    ...Object.values(row.skill_traits || {}),
    ...Object.values(row.personality_traits || {}),
  ].map(Number).filter(Number.isFinite);
  if (!traitValues.length) return "";
  return traitValues.reduce((sum, value) => sum + value, 0) / traitValues.length;
}

function staffYears(row) {
  return (
    row.years ??
    row.contract_years ??
    row.years_remaining ??
    row.contract?.years ??
    row.contract?.years_remaining ??
    row.staff?.contract?.years ??
    row.staff?.contract?.years_remaining ??
    ""
  );
}

function normalizeStaffMoney(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) return 0;

  // Backend may return raw dollars instead of millions.
  if (number > 100000) return number / 1000000;

  return number;
}

function staffBudgetMillions(staff, paidStaff) {
  const room = state.data.staff || {};
  const report = room.team_report || {};

  const explicit =
    report.staff_budget_millions ??
    report.budget_millions ??
    report.staff_salary_budget_millions ??
    room.staff_budget_millions ??
    room.budget_millions;

  if (explicit !== undefined && explicit !== null) return Number(explicit);

  const total = paidStaff.reduce((sum, item) => sum + item.aav, 0);

  // Fallback until we know the exact backend field name.
  return Math.max(20, Math.ceil(total * 1.25));
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
  const playoffPhase = ["play_in", "playoffs"].includes(String(room.phase || ""));
  const canSim = playoffPhase && room.status !== "completed";
  const canAdvanceStage = room.status === "completed";
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
      ${canSim ? `<div class="toolbar playoff-controls">
        <button data-playoff-sim="game">Sim 1 Game Per Series</button>
        <button data-playoff-sim="round">Sim Rest Of Series</button>
        <button data-playoff-sim="all">Sim Remaining Playoffs</button>
      </div>` : ""}
      ${canAdvanceStage ? `<div class="toolbar playoff-controls">
        <button id="playoffAdvanceStage">Advance To Next Stage</button>
      </div>` : ""}
      <div class="playoff-grid">
        <section class="section wide panel-rail">
          ${sectionHead("Bracket")}
          ${series.length ? playoffBracket(series, room.champion) : `<div class="empty">Bracket will generate when the save reaches play-in/playoffs. Until then, this is the live playoff picture.</div>`}
        </section>
      </div>
    </section>`;
  wireViewJumpButtons();
  els.content.querySelectorAll("[data-playoff-sim]").forEach((button) => {
    button.addEventListener("click", () => playoffSim(button.dataset.playoffSim || "game"));
  });
  const advanceStage = document.getElementById("playoffAdvanceStage");
  if (advanceStage) advanceStage.addEventListener("click", playoffAdvanceStage);
}

async function playoffSim(mode) {
  const actions = {
    game: "simulate_playoff_game",
    round: "simulate_playoff_round",
    all: "simulate_playoff_all",
  };
  const result = await action(actions[mode] || actions.game, { ...savePayload(), seed: 7 });
  state.data.playoffs = result.room;
  const games = result.result?.games?.length || (result.result?.game ? 1 : 0);
  const completed = result.result?.completed_series?.length || result.result?.completed_play_in?.length || 0;
  showToast(`Playoff sim: ${games ? `${games} game(s)` : result.status}${completed ? `, ${completed} series done` : ""}`);
  renderPlayoffs();
}

async function playoffAdvanceStage() {
  const result = await action("advance_save", { ...savePayload(), next_event: true, seed: 7 });
  state.home = result.home;
  clearViewCaches();
  applyPhaseRouting();
  await ensureViewData(true);
  render();
  showToast(`Advanced to ${state.home?.save?.current_date || "next stage"}`);
}

async function openPlayerFinderModal() {
  const payload = await action("player_finder", savePayload());
  state.playerFinder = {
    payload,
    sortField: payload.default_sort || "overall",
    filterField: "player",
    filterValue: "",
  };
  state.modal = {
    kind: "playerFinder",
    title: "Player Finder",
    subtitle: `${payload.rows?.length || 0} league players | ${payload.as_of_date || ""}`,
    body: playerFinderModalBody(),
  };
  renderModal();
}

function playerFinderModalBody() {
  const finder = state.playerFinder || {};
  const payload = finder.payload || {};
  const fields = playerFinderFields(payload.seasons || []);
  const sortField = finder.sortField || "overall";
  const filterField = finder.filterField || "player";
  const filterValue = finder.filterValue || "";
  const rows = filteredPlayerFinderRows(payload.rows || [], filterField, filterValue, sortField);
  return `
    <div class="player-finder-controls">
      <label>Sort
        <select id="playerFinderSort">
          ${fields.map((field) => `<option value="${escapeAttr(field.key)}" ${field.key === sortField ? "selected" : ""}>${escapeHtml(field.label)}</option>`).join("")}
        </select>
      </label>
      <label>Filter
        <select id="playerFinderFilterField">
          ${fields.map((field) => `<option value="${escapeAttr(field.key)}" ${field.key === filterField ? "selected" : ""}>${escapeHtml(field.label)}</option>`).join("")}
        </select>
      </label>
      <label>Value
        <input id="playerFinderFilterValue" value="${escapeAttr(filterValue)}" placeholder="Text contains or numeric minimum" />
      </label>
      <span class="pill" id="playerFinderCount">${rows.length} shown</span>
    </div>
    <div class="player-finder-table-wrap" id="playerFinderTableWrap">
      ${playerFinderTable(rows, payload.seasons || [])}
    </div>`;
}

function playerFinderFields(seasons = []) {
  return [
    { key: "player", label: "Player", type: "text" },
    { key: "team", label: "Team", type: "text" },
    { key: "position", label: "Pos", type: "text" },
    { key: "height", label: "Height", type: "text" },
    { key: "age", label: "Age", type: "number" },
    { key: "overall", label: "OVR", type: "number" },
    { key: "shooting", label: "Shot", type: "number" },
    { key: "creation", label: "Create", type: "number" },
    { key: "defense", label: "Def", type: "number" },
    { key: "spacing", label: "Space", type: "number" },
    { key: "passing", label: "Pass", type: "number" },
    { key: "rebounding", label: "Reb", type: "number" },
    { key: "rim_deterrence", label: "Rim", type: "number" },
    { key: "athleticism", label: "Ath", type: "number" },
    { key: "games_missed", label: "GM", type: "number" },
    { key: "display_mpg", label: "MPG", type: "number" },
    { key: "points_per_game", label: "PTS", type: "number" },
    { key: "rebounds_per_game", label: "REB", type: "number" },
    { key: "assists_per_game", label: "AST", type: "number" },
    { key: "steals_per_game", label: "STL", type: "number" },
    { key: "blocks_per_game", label: "BLK", type: "number" },
    { key: "turnovers_per_game", label: "TO", type: "number" },
    ...seasons.map((season) => ({ key: season, label: season, type: "number" })),
  ];
}

function filteredPlayerFinderRows(rows, filterField, filterValue, sortField) {
  const query = String(filterValue || "").trim().toLowerCase();
  const numericQuery = Number(query);
  const filtered = query
    ? rows.filter((row) => {
      const value = playerFinderValue(row, filterField);
      const numericValue = Number(value);
      if (Number.isFinite(numericQuery) && Number.isFinite(numericValue)) return numericValue >= numericQuery;
      return String(value ?? "").toLowerCase().includes(query);
    })
    : [...rows];
  filtered.sort((a, b) => {
    const av = playerFinderValue(a, sortField);
    const bv = playerFinderValue(b, sortField);
    const an = Number(av);
    const bn = Number(bv);
    if (Number.isFinite(an) && Number.isFinite(bn)) return bn - an || String(a.name || "").localeCompare(String(b.name || ""));
    return String(av ?? "").localeCompare(String(bv ?? ""), undefined, { numeric: true, sensitivity: "base" });
  });
  return filtered;
}

function playerFinderValue(row, key) {
  if (key === "player") return row.name || "";
  if (key === "team") return row.team_abbrev || "";
  if (key === "height") return row.height || "";
  if (row.salary_by_year && Object.prototype.hasOwnProperty.call(row.salary_by_year, key)) return row.salary_by_year[key] ?? "";
  if (["overall", "shooting", "creation", "defense", "spacing", "passing", "rebounding", "rim_deterrence", "athleticism"].includes(key)) return rating(row, key);
  return row[key] ?? row.ratings?.[key] ?? "";
}

function playerFinderTable(rows, seasons) {
  return table(["Player", "Team", "Pos", "Height", "Age", "OVR", "Shot", "Create", "Def", "Space", "Pass", "Reb", "Rim", "Ath", "GM", "MPG", "PTS", "REB", "AST", "STL", "BLK", "TO", ...seasons], rows, (row) => [
    summaryPlayerNameCell(row),
    row.team_abbrev || "FA",
    compactPos(row.position),
    heightFromRow(row) || "—",
    row.age ?? "—",
    plainNumber(rating(row, "overall")),
    plainNumber(rating(row, "shooting")),
    plainNumber(rating(row, "creation")),
    plainNumber(rating(row, "defense")),
    plainNumber(rating(row, "spacing") || rating(row, "range")),
    plainNumber(rating(row, "passing")),
    plainNumber(rating(row, "rebounding")),
    plainNumber(rating(row, "rim_deterrence")),
    plainNumber(rating(row, "athleticism")),
    gamesMissedFromRow(row),
    Number(mpgFromRow(row) || 0).toFixed(1),
    statNumber(row, "points"),
    statNumber(row, "rebounds"),
    statNumber(row, "assists"),
    statNumber(row, "steals"),
    statNumber(row, "blocks"),
    statNumber(row, "turnovers"),
    ...seasons.map((season) => money(row.salary_by_year?.[season]) || "—"),
  ], "player-finder-table");
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
  const modalClass = state.modal.kind === "playerFinder" ? " modal-wide" : "";
  els.modalRoot.innerHTML = `
    <div class="modal-shell${modalClass}" role="dialog" aria-modal="true">
      <header class="modal-head">
        <div>
          <p class="eyebrow">${escapeHtml(state.modal.subtitle || "")}</p>
          <h3>${escapeHtml(state.modal.title || "Detail")}</h3>
        </div>
        <button data-close-modal>Close</button>
      </header>
      <div class="modal-body">${state.modal.body || ""}</div>
    </div>`;
  if (state.modal.kind === "tradeOffers") {
    wireOfferButtons(els.modalRoot, state.modal.offers || []);
  }
  if (state.modal.kind === "playerFinder") {
    wirePlayerFinderModal();
  }
  els.modalRoot.querySelectorAll("[data-dashboard-team-jump]").forEach((button) => {
    button.addEventListener("click", async () => {
      closeModal();
      await switchDashboardTeam(button.dataset.dashboardTeamJump || userTeam());
    });
  });
}

function wirePlayerFinderModal() {
  const sort = document.getElementById("playerFinderSort");
  if (sort) sort.addEventListener("change", () => {
    state.playerFinder.sortField = sort.value || "overall";
    refreshPlayerFinderTable();
  });
  const filterField = document.getElementById("playerFinderFilterField");
  if (filterField) filterField.addEventListener("change", () => {
    state.playerFinder.filterField = filterField.value || "player";
    refreshPlayerFinderTable();
  });
  const filterValue = document.getElementById("playerFinderFilterValue");
  if (filterValue) filterValue.addEventListener("input", () => {
    state.playerFinder.filterValue = filterValue.value || "";
    refreshPlayerFinderTable();
  });
}

function refreshPlayerFinderTable() {
  const finder = state.playerFinder || {};
  const payload = finder.payload || {};
  const rows = filteredPlayerFinderRows(payload.rows || [], finder.filterField || "player", finder.filterValue || "", finder.sortField || "overall");
  const count = document.getElementById("playerFinderCount");
  if (count) count.textContent = `${rows.length} shown`;
  const wrap = document.getElementById("playerFinderTableWrap");
  if (wrap) wrap.innerHTML = playerFinderTable(rows, payload.seasons || []);
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
    return `<option value="${escapeAttr(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`;
  }).join("");
}

function teamIdentityRankBlock(dash) {
  const identity = dash.team_identity || {};
  const metrics = identity.metrics || {};
  const ranks = identity.ranks || {};
  const count = identity.league_team_count || 30;
  const selected = teamLabel(dash.team || state.dashboardTeam || userTeam());
  return `<div class="section-head identity-head">
      <h3><select id="dashboardTeamSelect" aria-label="Dashboard team">${dashboardTeamOptions(selected)}</select> Identity</h3>
    </div>
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
  ensureStartingDraft(rows);

  const draft = state.startingDraft || {};
  const allFilled = [1, 2, 3, 4, 5].every((slot) => draft[slot]);
  const hasEmpty = !allFilled;
  const changed = startingDraftChanged(rows);

  const rowClass = !allFilled
    ? "needs-fill"
    : changed
      ? "pending"
      : "set";

  return `
    <div class="section-head">
      <h3>Starting 5</h3>
      <div class="starting-actions">
        ${editable ? `<button id="autoStartingFive">Auto</button>` : `<span class="pill">Read-only</span>`}
        ${editable ? `<button id="setStartingFive" class="primary-action" ${allFilled ? "" : "disabled"}>Set</button>` : ""}
      </div>
    </div>

    <div class="staff-role-list starting-five-list ${rowClass}">
      ${[1, 2, 3, 4, 5]
        .map((slot) => startingFiveButton(slot, rows, draft[slot], editable, hasEmpty, changed))
        .join("")}
    </div>

    ${editable && state.startingPickerSlot ? startingFivePicker(rows, Number(state.startingPickerSlot)) : ""}`;
}

function ensureStartingDraft(rows) {
  const saved = savedStartingFiveMap(rows);
  const savedSignature = startingMapSignature(saved);
  const currentSignature = state.startingDraft ? startingMapSignature(state.startingDraft) : "";
  const draftStillMatchesSaved = !state.startingDraft || !state.startingSavedSignature || currentSignature === state.startingSavedSignature;

  if (!state.startingDraft || (draftStillMatchesSaved && savedSignature !== state.startingSavedSignature)) {
    state.startingDraft = { ...saved };
  }
  state.startingSavedSignature = savedSignature;
}

function startingFiveButton(slot, rows, playerId, editable, hasEmpty, changed) {
  const row = rows.find((player) => String(player.id) === String(playerId));
  const empty = !row;

  const statusClass = empty
    ? "empty"
    : changed || hasEmpty
      ? "pending"
      : "set";

  return `<button
    class="staff-role-button starting-five-button ${statusClass}"
    data-starting-slot-button="${slot}"
    ${editable ? "" : "disabled"}
    title="${empty ? "Choose starter" : "Click to clear this starter"}"
  >
    <span class="staff-role">${slot}.${row ? ` ${escapeHtml(compactPos(row.position))}` : ""}</span>
    <span class="starting-player-line">
      <strong>${row ? escapeHtml(row.name) : "Open"}</strong>
      <span class="staff-meta">${row ? `${escapeHtml(heightFromRow(row) || "—")} · ${Number(mpgFromRow(row) || 0).toFixed(0)} MPG` : "Choose starter"}</span>
    </span>
  </button>`;
}

function startingFivePicker(rows, slot) {
  const draft = state.startingDraft || {};
  const selectedIds = new Set(
    Object.entries(draft)
      .filter(([draftSlot, playerId]) => Number(draftSlot) !== slot && playerId)
      .map(([, playerId]) => String(playerId))
  );

  const available = rows.filter((row) => !selectedIds.has(String(row.id)));

  return `<div class="starting-picker">
    <div class="starting-picker-head">
      <strong>Choose Slot ${slot}</strong>
      <button data-close-starting-picker>×</button>
    </div>

    <div class="starting-picker-list">
      ${available.map((row) => `<button data-starting-pick="${escapeAttr(row.id)}">
        <strong>${escapeHtml(row.name)}</strong>
        <span>${escapeHtml(compactPos(row.position))} · ${Number(mpgFromRow(row) || 0).toFixed(0)} MPG</span>
      </button>`).join("")}
    </div>
  </div>`;
}

function savedStartingFiveMap(rows, dash = state.data.dashboard || state.data.statusDashboard || {}) {
  const saved = {};
  for (const slot of [1, 2, 3, 4, 5]) {
    const starter = rows.find((row) => Number(row.starting_slot) === slot);
    saved[slot] = starter?.id || "";
  }
  if (!startingMapComplete(saved) && Array.isArray(dash?.starting_five)) {
    for (const item of dash.starting_five) {
      const slot = Number(item.slot);
      if (slot >= 1 && slot <= 5 && item.player_id) saved[slot] = item.player_id;
    }
  }
  return saved;
}

function startingDraftChanged(rows) {
  const saved = savedStartingFiveMap(rows);
  const draft = state.startingDraft || saved;

  return [1, 2, 3, 4, 5].some(
    (slot) => String(draft[slot] || "") !== String(saved[slot] || "")
  );
}

function startingMapComplete(map) {
  return [1, 2, 3, 4, 5].every((slot) => map && map[slot]);
}

function startingMapSignature(map) {
  return [1, 2, 3, 4, 5].map((slot) => String(map?.[slot] || "")).join("|");
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

function ensureRotationDraft(rows) {
  if (!Object.keys(state.rotationDraft).length) {
    state.rotationDraft = Object.fromEntries(
      rows.map((row) => [
        row.id,
        Math.round(Number(row.coach_minutes_projection ?? row.minutes_projection ?? 0)),
      ])
    );
  } else {
    for (const row of rows) {
      if (state.rotationDraft[row.id] === undefined) {
        state.rotationDraft[row.id] = Math.round(
          Number(row.coach_minutes_projection ?? row.minutes_projection ?? 0)
        );
      }
    }
  }
}

function rotationRatingsBlock(rows, editable) {
  const total = Object.values(state.rotationDraft).reduce(
    (sum, value) => sum + Number(value || 0),
    0
  );
  const remaining = 240 - total;

  return `
    <div class="section-head rotation-head">
      <h3>Rotation</h3>
      <div class="rotation-head-actions">
        <span id="rotationMinuteCounter" class="minute-counter ${remaining === 0 ? "ok" : "bad"}">
          ${remaining === 0 ? "240 assigned" : `${signedNumber(remaining, 0)} minutes remaining`}
        </span>
        ${editable ? `<button id="saveRotation" ${remaining === 0 ? "" : "disabled"}>Set Rotation</button>` : ""}
      </div>
    </div>
    ${rotationEditor(rows, editable)}`;
}

function rotationRatingsBlock(rows, editable) {
  ensureRotationDraft(rows);

  const total = Object.values(state.rotationDraft).reduce(
    (sum, value) => sum + Number(value || 0),
    0
  );
  const remaining = 240 - total;

  return `
    <div class="section-head rotation-head">
      <h3>Rotation</h3>
      <div class="rotation-head-actions">
        <span id="rotationMinuteCounter" class="minute-counter ${remaining === 0 ? "ok" : "bad"}">
          ${remaining === 0 ? "240 assigned" : `${signedNumber(remaining, 0)} minutes remaining`}
        </span>
        ${
          editable
            ? `<button id="saveRotation" ${remaining === 0 ? "" : "disabled"}>Set Rotation</button>`
            : ""
        }
      </div>
    </div>
    ${rotationEditor(rows, editable)}`;
}

function rotationEditor(rows, editable) {
  ensureRotationDraft(rows);

  return `
    <div class="rotation-list rotation-list-full">
      ${rows.map((row) => {
        const value = clampNumber(Number(state.rotationDraft[row.id] ?? row.minutes_projection ?? 0), 0, 48);
        const injured = isPlayerInjured(row.health);
        return `<div class="rotation-row rotation-row-compact">
          <div class="rotation-player">
            <strong class="${injured ? "injured-player-name" : ""}">${escapeHtml(row.name)}</strong>
            <span>${rotationPlayerMeta(row)}</span>
          </div>
          <input type="range" min="0" max="48" step="1" value="${value}" data-minute-player="${escapeAttr(row.id)}" ${editable ? "" : "disabled"} />
          <output>${value}</output>
        </div>`;
      }).join("")}
    </div>`;
}

function updateRotationMinuteCounter() {
  const total = Object.values(state.rotationDraft).reduce(
    (sum, value) => sum + Number(value || 0),
    0
  );
  const remaining = 240 - total;

  const counter = document.getElementById("rotationMinuteCounter");
  if (counter) {
    counter.classList.toggle("ok", remaining === 0);
    counter.classList.toggle("bad", remaining !== 0);
    counter.textContent = remaining === 0
      ? "240 assigned"
      : `${signedNumber(remaining, 0)} minutes remaining`;
  }

  const save = document.getElementById("saveRotation");
  if (save) save.disabled = remaining !== 0;
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

function summaryLeaderRotator() {
  const fields = state.data.dashboardSummaryLeaders?.fields || [];
  const slides = fields.map((field, fieldIndex) => {
    const leaders = field.leaders || [];
    const label = field.label || field.key || "Field";
    return `
      <div class="summary-leader-slide ${fieldIndex === 0 ? "active" : ""}" data-field-label="${escapeAttr(label)}">
        <ol class="summary-leader-list">
          ${leaders.map((leader, index) => `
            <li>
              <span class="summary-rank">${index + 1}</span>
              <span class="summary-player">
                <strong>${escapeHtml(leader.player_name || "Unknown")}</strong>
                <small>${escapeHtml([leader.team_abbrev, leader.position, leader.age ? `age ${leader.age}` : "", leader.height].filter(Boolean).join(", "))}</small>
              </span>
              <em>${Number(leader.value || 0).toFixed(1)}</em>
            </li>
          `).join("") || `<li class="empty">No league leaders available.</li>`}
        </ol>
      </div>`;
  }).join("");

  return `
    <div class="section-head summary-leader-head">
      <h3>League Leader:</h3>
      <select id="summaryLeaderSelect" aria-label="League leader category">
        ${fields.map((field, index) => `<option value="${index}">${escapeHtml(field.label || field.key || "Field")}</option>`).join("")}
      </select>
    </div>
    <div class="summary-leader-rotator" data-summary-leader-rotator>
      <div class="summary-leader-track">
        ${slides || `<div class="empty">No league leaders available.</div>`}
      </div>
    </div>
    <div class="rotator-progress"><span></span></div>`;
}

function dashboardPlayerSummaryTable(rows) {
  ensureRotationDraft(rows);
  const seasons = contractSeasons(rows).slice(0, 4);
  const total = Object.values(state.rotationDraft).reduce(
    (sum, value) => sum + Number(value || 0),
    0
  );
  const remaining = 240 - total;
  const dash = state.data.dashboard || {};
  const editable = !state.hydrating && teamLabel(dash.team || state.dashboardTeam) === userTeam();
  const summaryRows = rows.length >= 17
    ? rows
    : [
      ...rows,
      ...Array.from({ length: 17 - rows.length }, (_unused, index) => ({
        __summaryEmpty: true,
        id: `summary-empty-${index}`,
      })),
    ];
  return `
    <div class="section-head summary-head">
      <h3>Player Ratings / Season Box Score / Contracts</h3>
      <div class="rotation-head-actions">
        <span id="rotationMinuteCounter" class="minute-counter ${remaining === 0 ? "ok" : "bad"}">
          ${remaining === 0 ? "240 assigned" : `${signedNumber(remaining, 0)} minutes remaining`}
        </span>
        ${editable ? `<button id="saveRotation" ${remaining === 0 ? "" : "disabled"}>Set Rotation</button>` : ""}
      </div>
    </div>
    <div class="dashboard-mini-table">
      ${table(["Player", "Pos", "Height", "Age", "OVR", "Shot", "Create", "Def", "Space", "Pass", "Reb", "Rim", "Ath", "GM", "Set", "MPG", "PTS", "REB", "AST", "STL", "BLK", "TO", ...seasons], summaryRows, (row) => row.__summaryEmpty ? Array.from({ length: 22 + seasons.length }, () => "—") : [
        summaryPlayerNameCell(row),
        compactPos(row.position),
        heightFromRow(row) || "—",
        row.age ?? "—",
        plainNumber(rating(row, "overall")),
        plainNumber(rating(row, "shooting")),
        plainNumber(rating(row, "creation")),
        plainNumber(rating(row, "defense")),
        plainNumber(rating(row, "spacing") || rating(row, "range")),
        plainNumber(rating(row, "passing")),
        plainNumber(rating(row, "rebounding")),
        plainNumber(rating(row, "rim_deterrence")),
        plainNumber(rating(row, "athleticism")),
        gamesMissedFromRow(row),
        rotationSliderCell(row, editable),
        Number(mpgFromRow(row) || 0).toFixed(1),
        statNumber(row, "points"),
        statNumber(row, "rebounds"),
        statNumber(row, "assists"),
        statNumber(row, "steals"),
        statNumber(row, "blocks"),
        statNumber(row, "turnovers"),
        ...seasons.map((season) => money(row.salary_by_year?.[season]) || "—"),
      ], "dashboard-player-summary")}
    </div>`;
}

function summaryPlayerNameCell(row) {
  const name = row.name || "";
  if (!isPlayerInjured(row.health)) return name;
  return html(`<span class="injured-player-name">${escapeHtml(name)}</span>`);
}

function gamesMissedFromRow(row) {
  const value = Number(row.health?.games_missed ?? row.games_missed ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function rotationSliderCell(row, editable) {
  const value = clampNumber(Number(state.rotationDraft[row.id] ?? row.minutes_projection ?? 0), 0, 48);
  return html(`
    <div class="summary-minute-control">
      <input type="range" min="0" max="48" step="1" value="${value}" data-minute-player="${escapeAttr(row.id)}" ${editable ? "" : "disabled"} />
      <output data-minute-output="${escapeAttr(row.id)}">${value}</output>
    </div>`);
}

function dashboardPlayerRatingsTable(rows) {
  return `
    ${sectionHead("Player Ratings")}
    <div class="dashboard-mini-table">
      ${ratingsTable(rows)}
    </div>`;
}

function dashboardPlayerStatsTable(rows) {
  return `
    ${sectionHead("Season Box Score")}
    <div class="dashboard-mini-table">
      ${table(["Player", "Pos", "MPG", "PTS", "REB", "AST", "STL", "BLK", "TO"], rows, (row) => [
        row.name,
        compactPos(row.position),
        Number(mpgFromRow(row) || 0).toFixed(1),
        statNumber(row, "points"),
        statNumber(row, "rebounds"),
        statNumber(row, "assists"),
        statNumber(row, "steals"),
        statNumber(row, "blocks"),
        statNumber(row, "turnovers"),
      ], "dashboard-season-box")}
    </div>`;
}

function statNumber(row, stat) {
  const value =
    statFromRow(row, stat) ??
    row[`${stat}_per_game`] ??
    row[`${stat}_pg`] ??
    row[stat] ??
    "";

  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : value;
}

function userConferenceStandings() {
  const standings = standingsRows(state.data.dashboardStandings);
  const user = userTeam();
  const viewed = teamLabel(state.data.dashboard?.team || state.dashboardTeam || user);
  const userRow = standings.find((row) => teamLabel(row.team) === user);
  const defaultConference = userRow?.team?.conference || "East";
  const conference = ["East", "West"].includes(state.dashboardStandingsConference) ? state.dashboardStandingsConference : defaultConference;
  const rows = standings
    .filter((row) => row.team?.conference === conference)
    .slice(0, 10);

  return `<div class="section-head standings-head">
      <h3><button class="standings-conference-toggle" data-standings-conference-toggle data-standings-conference="${escapeAttr(conference)}">${escapeHtml(conference)}</button> Standings</h3>
      <button class="standings-view-all" data-standings-view-all>View All</button>
    </div>
    ${dashboardStandingsTable(rows, viewed)}`;
}

function dashboardStandingsTable(rows, user) {
  if (!rows.length) return `<div class="empty">No standings yet.</div>`;
  return `
    <div class="table-wrap">
      <table class="data-table dashboard-standings">
        <colgroup>
          <col class="standings-rank-col" />
          <col class="standings-team-col" />
          <col class="standings-record-col" />
          <col class="standings-pct-col" />
        </colgroup>
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>W-L</th>
            <th>Win%</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row, index) => {
            const team = teamLabel(row.team);
            return `<tr class="${index === 6 ? "play-in-cutoff-row" : ""}">
              <td class="standings-rank">${index + 1}.</td>
              <td class="standings-team"><button data-dashboard-team-jump="${escapeAttr(team)}" class="${team === user ? "user-highlight" : ""}">${escapeHtml(team)}</button></td>
              <td class="standings-record">${escapeHtml(`${row.wins || 0}-${row.losses || 0}`)}</td>
              <td>${escapeHtml(winPct(row.win_pct))}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>`;
}

function openStandingsModal() {
  const standings = standingsRows(state.data.dashboardStandings);
  const conferences = ["East", "West"];
  const viewed = teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam());
  state.modal = {
    kind: "standings",
    title: "Full Standings",
    subtitle: state.home?.save?.current_date || "",
    body: `<div class="standings-modal-grid">
      ${conferences.map((conference) => {
        const rows = standings.filter((row) => String(row.team?.conference || "") === conference);
        return `<section>
          ${sectionHead(`${conference} Conference`)}
          ${dashboardStandingsTable(rows, viewed)}
        </section>`;
      }).join("")}
    </div>`,
  };
  renderModal();
}

function dashboardMonthCalendar() {
  const dash = state.data.dashboard || {};
  const team = teamLabel(dash.team || userTeam());
  const current = state.home?.save?.current_date || "";
  const month = state.calendarMonth || current.slice(0, 7);
  const games = (state.data.dashboardCalendar?.games || []).filter((game) => [game.home, game.home_team, game.away, game.away_team].includes(team));
  const cells = monthCalendarCells(month);
  const weekRows = Math.max(1, Math.ceil(cells.length / 7));

  return `<div class="section-head calendar-head">
      <h3>${escapeHtml(calendarHeaderDate(current, month))}</h3>
      <div class="calendar-head-controls">
        <div class="toolbar compact">
          <button data-calendar-step="-1">‹</button>
          <button data-calendar-step="1">›</button>
        </div>
      </div>
    </div>
    <div class="calendar-grid" style="grid-template-rows: 12px repeat(${weekRows}, minmax(0, 1fr))">
      ${["M", "T", "W", "T", "F", "S", "S"].map((day) => `<div class="calendar-label">${day}</div>`).join("")}
      ${cells.map((cell) => calendarCell(cell, games, current, team)).join("")}
    </div>
    <div class="calendar-footer">${simControls()}</div>`;
}

function contractChartCard(rows, dash) {
  const seasons = contractSeasons(rows).slice(0, 4);
  if (!rows.length || !seasons.length) {
    return `${sectionHead("Contract Chart")}<div class="empty">No contract data loaded.</div>`;
  }
  return `
    ${sectionHead("Contract Chart")}
    <div class="contract-year-columns">
      ${seasons.map((season) => contractPayrollColumn(season, rows, dash.cap_by_year?.[season])).join("")}
    </div>`;
}

function dashboardStaffMarketCard(editable = true) {
  const candidates = marketCandidates(state.data.dashboardStaffMarket);
  const slotOrder = ["head_coach", "offensive_coordinator", "defensive_coordinator", "development_lead", "performance_lead", "scouting_lead"];
  const pages = slotOrder
    .map((slot) => ({
      key: slot,
      label: rowLabel(slot),
      rows: candidates
        .filter((candidate) => String(candidate.slot || candidate.role_preference || "") === slot)
        .sort((a, b) => Number(staffGrade(b) || 0) - Number(staffGrade(a) || 0))
        .slice(0, 5),
    }))
    .filter((page) => page.rows.length);
  pages.push({
    key: "all",
    label: "All Positions",
    rows: [...candidates]
      .sort((a, b) => Number(staffGrade(b) || 0) - Number(staffGrade(a) || 0))
      .slice(0, 5),
  });
  return marketRotatorCard("Available Staff", pages, staffMarketLine, "staff", !editable);
}

function dashboardFreeAgentMarketCard(editable = true) {
  const candidates = marketCandidates(state.data.dashboardFreeAgents);
  const positions = ["PG", "SG", "SF", "PF", "C"];
  const pages = positions
    .map((position) => ({
      key: position,
      label: position,
      rows: candidates
        .filter((player) => String(player.position || "").toUpperCase().includes(position))
        .sort((a, b) => freeAgentSortValue(b) - freeAgentSortValue(a))
        .slice(0, 5),
    }))
    .filter((page) => page.rows.length);
  pages.push({
    key: "all",
    label: "All Positions",
    rows: [...candidates].sort((a, b) => freeAgentSortValue(b) - freeAgentSortValue(a)).slice(0, 5),
  });
  return marketRotatorCard("Player Free Agents", pages, freeAgentMarketLine, "free-agents", !editable);
}

function dashboardActionsCard(editable = true) {
  const offerCount = Number(state.data.dashboardOffers?.offers?.length || 0);
  const disabled = editable ? "" : "disabled";
  return `
    ${sectionHead("Front Office")}
    <div class="dashboard-action-list">
      <button class="dashboard-action-button" data-dashboard-trade="builder" ${disabled}>
        <strong>Trade Builder</strong>
      </button>
      <button class="dashboard-action-button" data-dashboard-trade="finder" ${disabled}>
        <strong>Trade Finder</strong>
      </button>
      <button class="dashboard-action-button" data-dashboard-player-finder ${disabled}>
        <strong>Player Finder</strong>
      </button>
      <button class="dashboard-action-button" data-dashboard-view="draft" ${disabled}>
        <strong>Prospects</strong>
      </button>
      <button class="dashboard-action-button offer-action ${offerCount ? "has-offers" : ""}" data-dashboard-offers ${disabled}>
        <strong>Trade Offers</strong>
      </button>
    </div>`;
}

function marketRotatorCard(title, pages, rowRenderer, id, disabled = false) {
  const usable = pages.filter((page) => page.rows?.length);
  return `
    <div class="section-head market-card-head">
      <h3>${escapeHtml(title)}</h3>
      <select data-market-select="${escapeAttr(id)}" aria-label="${escapeAttr(`${title} category`)}" ${disabled ? "disabled" : ""}>
        ${usable.map((page, index) => `<option value="${index}">${escapeHtml(page.label)}</option>`).join("")}
      </select>
    </div>
    <div class="market-rotator" data-market-rotator data-market-id="${escapeAttr(id)}">
      ${usable.map((page, index) => `
        <div class="market-slide ${index === 0 ? "active" : ""}">
          <div class="market-list">
            ${page.rows.map(rowRenderer).join("")}
          </div>
        </div>`).join("") || `<div class="empty">No market data available.</div>`}
    </div>
    <div class="rotator-progress"><span></span></div>`;
}

function staffMarketLine(candidate, index) {
  return `
    <div class="market-row">
      <span class="market-rank">${index + 1}</span>
      <span class="market-main">
        <strong>${escapeHtml(staffName(candidate))}</strong>
        <small>${escapeHtml(rowLabel(candidate.slot || candidate.role_preference))}</small>
      </span>
      <span class="market-score">${Number(staffGrade(candidate) || 0).toFixed(1)}</span>
      <span class="market-ask">${money(staffAav(candidate))} x ${escapeHtml(staffYears(candidate) || candidate.asking_years || 1)}</span>
    </div>`;
}

function freeAgentMarketLine(player, index) {
  return `
    <div class="market-row">
      <span class="market-rank">${index + 1}</span>
      <span class="market-main">
        <strong>${escapeHtml(player.name || "Unknown")}</strong>
        <small>${escapeHtml([player.position, player.age ? `age ${player.age}` : ""].filter(Boolean).join(" "))}</small>
      </span>
      <span class="market-score">${plainNumber(freeAgentOverall(player))}</span>
      <span class="market-ask">${money(freeAgentAsk(player))}</span>
    </div>`;
}

function standingsTrendCard() {
  const data = state.data.dashboardTrends?.standings || {};
  const points = data.points || [];
  return `
    ${sectionHead("Standings Position")}
    <div class="trend-card-body">
      ${singleLineChart(points, { invert: true, fixedSlots: 26, minValue: 1, maxValue: 30, endLabel: "Season End", empty: "No weekly standings history yet." })}
      <div class="trend-note">${points.length > 1 ? "Week by week conference rank" : "Current snapshot until games are played"}</div>
    </div>`;
}

function developmentTrendCard(rows = []) {
  const candidates = developmentPlayerCandidates(rows);
  ensureDevelopmentSelection(candidates);
  const selectedIds = state.developmentPlayerIds.filter((id) => candidates.some((candidate) => candidate.player_id === id)).slice(0, 5);
  const selectedLines = selectedIds.map((id) => candidates.find((candidate) => candidate.player_id === id)).filter(Boolean);
  const isNew = state.developmentNewSignature && state.developmentNewSignature === developmentTrendSignature();
  return `
    ${sectionHead("Player Development", "", isNew ? `<span class="development-new-badge">NEW</span>` : "")}
    <div class="development-trend-body">
      <div class="development-chart-panel">
        ${developmentLineChart(selectedLines, { empty: "No development players selected." })}
      </div>
      <div class="development-legend-panel">
        ${developmentLegend(selectedLines, candidates)}
      </div>
    </div>`;
}

function developmentPlayerCandidates(rows = []) {
  const trendLines = state.data.dashboardTrends?.development?.lines || [];
  const byId = new Map();
  for (const line of trendLines) {
    if (!line.player_id) continue;
    byId.set(String(line.player_id), {
      player_id: String(line.player_id),
      name: line.name || "Unknown",
      position: line.position || "",
      current: Number(line.points?.[line.points.length - 1]?.value || 0),
      points: line.points || [],
    });
  }
  for (const row of rows) {
    if (!row.id || row.__summaryEmpty) continue;
    const id = String(row.id);
    const current = Number(rating(row, "overall") || row.overall || 0);
    const existing = byId.get(id);
    byId.set(id, {
      player_id: id,
      name: row.name || existing?.name || "Unknown",
      position: compactPos(row.position || existing?.position || ""),
      current: Number.isFinite(current) && current > 0 ? current : Number(existing?.current || 0),
      points: existing?.points?.length ? existing.points : [],
      minutes: Number(mpgFromRow(row) || 0),
    });
  }
  return [...byId.values()].sort((a, b) => {
    const movementDiff = developmentMovementScore(b) - developmentMovementScore(a);
    if (movementDiff) return movementDiff;
    const minuteDiff = Number(b.minutes || 0) - Number(a.minutes || 0);
    if (minuteDiff) return minuteDiff;
    return Number(b.current || 0) - Number(a.current || 0);
  });
}

function ensureDevelopmentSelection(candidates) {
  const candidateIds = new Set(candidates.map((candidate) => candidate.player_id));
  state.developmentPlayerIds = state.developmentPlayerIds.filter((id) => candidateIds.has(id)).slice(0, 5);
  if (state.developmentSelectionTouched) return;
  const preferred = [...candidates].sort((a, b) => {
    const movementDiff = developmentMovementScore(b) - developmentMovementScore(a);
    if (movementDiff) return movementDiff;
    const minuteDiff = Number(b.minutes || 0) - Number(a.minutes || 0);
    if (minuteDiff) return minuteDiff;
    return Number(b.current || 0) - Number(a.current || 0);
  });
  for (const candidate of preferred) {
    if (state.developmentPlayerIds.length >= 5) break;
    if (!state.developmentPlayerIds.includes(candidate.player_id)) {
      state.developmentPlayerIds.push(candidate.player_id);
    }
  }
}

function developmentMovementScore(candidate) {
  const points = candidate?.points || [];
  const values = points.map((point) => Number(point.value)).filter(Number.isFinite);
  if (values.length < 2) return 0;
  return Math.abs(values[values.length - 1] - values[0]);
}

function developmentTrendSignature() {
  const development = state.data.dashboardTrends?.development || {};
  return development.latest_month || (development.applied_months || []).slice(-1)[0] || "";
}

function syncDevelopmentAdvanceState(previousSignature) {
  const nextSignature = developmentTrendSignature();
  if (nextSignature && nextSignature !== previousSignature) {
    state.developmentSelectionTouched = false;
    state.developmentPlayerIds = [];
    state.developmentSeenSignature = nextSignature;
    state.developmentNewSignature = nextSignature;
    return;
  }
  state.developmentNewSignature = "";
}

function clearDevelopmentNewBadge() {
  state.developmentNewSignature = "";
}

function developmentLegend(lines, candidates) {
  const selected = new Set(lines.map((line) => line.player_id));
  const addable = candidates.filter((candidate) => !selected.has(candidate.player_id));
  const colors = developmentLineColors();
  return `
    <div class="development-legend-list">
      ${lines.map((line, index) => `
        <div class="development-legend-row">
          <span class="development-swatch" style="background:${colors[index % colors.length]}"></span>
          <select data-development-swap="${index}" aria-label="Development player ${index + 1}">
            ${developmentPlayerOptions(candidates, selected, line.player_id)}
          </select>
          <button data-development-remove="${escapeAttr(line.player_id)}" title="Remove ${escapeAttr(line.name || "player")}">×</button>
        </div>
      `).join("")}
      ${lines.length < 5 && addable.length ? `
        <div class="development-add-row">
          <button data-development-add title="Add player">+</button>
          <select data-development-add-select aria-label="Add development player">
            ${addable.map((candidate) => `<option value="${escapeAttr(candidate.player_id)}">${escapeHtml(shortName(candidate.name || "Player"))}</option>`).join("")}
          </select>
        </div>
      ` : ""}
    </div>`;
}

function developmentPlayerOptions(candidates, selected, currentId) {
  return candidates
    .filter((candidate) => candidate.player_id === currentId || !selected.has(candidate.player_id))
    .map((candidate) => `<option value="${escapeAttr(candidate.player_id)}" ${candidate.player_id === currentId ? "selected" : ""}>${escapeHtml(shortName(candidate.name || "Player"))}</option>`)
    .join("");
}

function developmentLineColors() {
  return ["#2fbf75", "#5b8fd9", "#d7b84f", "#d94a4a", "#966ce6"];
}

function draftPicksCard() {
  const years = nextDraftYears();
  const picks = state.data.dashboardAssets?.picks || [];
  const grouped = new Map();
  for (const pick of picks) {
    const year = String(pick.season || "").slice(0, 4);
    const round = Number(pick.round || 0);
    if (!years.includes(year) || ![1, 2].includes(round)) continue;
    const key = `${year}:R${round}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(pick);
  }
  for (const list of grouped.values()) {
    list.sort((a, b) => pickTeamAbbrev(a).localeCompare(pickTeamAbbrev(b)));
  }

  return `
    ${sectionHead("Draft Picks")}
    <div class="draft-pick-mini-table">
      <div class="draft-pick-head year">Draft</div>
      <div class="draft-pick-head">R1</div>
      <div class="draft-pick-head">R2</div>
      ${years.map((year) => `
        <div class="draft-pick-year">${escapeHtml(year)}</div>
        <div class="draft-pick-cell">${draftPickMarks(grouped.get(`${year}:R1`) || [])}</div>
        <div class="draft-pick-cell">${draftPickMarks(grouped.get(`${year}:R2`) || [])}</div>
      `).join("")}
    </div>`;
}

function draftPickMarks(picks) {
  if (!picks.length) return `<span class="draft-pick-empty">—</span>`;
  return picks.map((pick) => {
    const team = pickTeamAbbrev(pick);
    const logo = teamLogoSrc(team);
    const label = pick.label || `${team} pick`;
    if (!logo) return `<span class="team-logo-dot logo-missing" title="${escapeAttr(label)}" aria-label="${escapeAttr(label)}"></span>`;
    return `<span class="team-logo-dot" title="${escapeAttr(label)}"><img src="${escapeAttr(logo)}" alt="${escapeAttr(team)}" loading="lazy" /></span>`;
  }).join("");
}

function pickTeamAbbrev(pick) {
  const label = String(pick.label || "");
  const match = label.match(/^\d{4}\s+R[12]\s+([A-Z]{2,3})\b/);
  return match?.[1] || teamLabel(pick.original_team || pick.team || pick.team_abbrev || pick.owner_team || "");
}

function teamLogoSrc(team) {
  const abbrev = String(team || "").toUpperCase();
  const known = new Set([
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
  ]);
  return known.has(abbrev) ? `assets/team_logos/${abbrev}.png` : "";
}

function nextDraftYears() {
  const seasonStart = Number(String(state.home?.save?.season || "").slice(0, 4));
  if (Number.isFinite(seasonStart) && seasonStart > 2000) {
    const firstDraftYear = seasonStart + 1;
    return Array.from({ length: 4 }, (_unused, index) => String(firstDraftYear + index));
  }
  const current = String(state.home?.save?.current_date || "");
  const currentYear = Number(current.slice(0, 4)) || 2025;
  const firstDraftYear = currentYear + 1;
  return Array.from({ length: 4 }, (_unused, index) => String(firstDraftYear + index));
}

function marketCandidates(payload) {
  if (!payload) return [];
  for (const key of ["candidates", "players", "rows", "market", "free_agents", "staff"]) {
    if (Array.isArray(payload[key])) return payload[key];
  }
  return Array.isArray(payload) ? payload : [];
}

function freeAgentAsk(player) {
  return (
    player.ask_millions ??
    player.projected_aav_millions ??
    player.asking_aav_millions ??
    player.market_aav_millions ??
    player.aav_millions ??
    player.projected_aav ??
    0
  );
}

function freeAgentOverall(player) {
  return (
    player.ratings?.overall ??
    player.attributes?.overall ??
    player.overall ??
    player.rating ??
    player.value ??
    0
  );
}

function freeAgentSortValue(player) {
  return Number(freeAgentOverall(player) || 0) * 2 + Number(freeAgentAsk(player) || 0) + Number(player.team_fit_score || 0) * 0.1;
}

function singleLineChart(points, options = {}) {
  const rows = points.length === 1 && !options.fixedSlots ? [{ ...points[0], label: "Start" }, points[0]] : points;
  if (!rows.length) return `<div class="empty">${escapeHtml(options.empty || "No chart data.")}</div>`;
  const values = rows.map((point) => Number(point.value)).filter(Number.isFinite);
  const min = Number.isFinite(Number(options.minValue)) ? Number(options.minValue) : Math.min(...values);
  const max = Number.isFinite(Number(options.maxValue)) ? Number(options.maxValue) : Math.max(...values);
  const span = Math.max(1, max - min);
  const width = 320;
  const height = 150;
  const padX = 24;
  const padY = 18;
  const fixedSlots = Number(options.fixedSlots || 0);
  const xDenominator = fixedSlots > 1 ? fixedSlots - 1 : Math.max(1, rows.length - 1);
  const coords = rows.map((point, index) => {
    const value = Number(point.value || 0);
    const x = padX + (index / xDenominator) * (width - padX * 2);
    const y = options.invert
      ? padY + ((value - min) / span) * (height - padY * 2)
      : height - padY - ((value - min) / span) * (height - padY * 2);
    return { x, y, point };
  });
  return `
    <svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Trend line">
      <path class="trend-grid" d="M${padX} ${padY}H${width - padX}M${padX} ${height / 2}H${width - padX}M${padX} ${height - padY}H${width - padX}" />
      <polyline class="trend-line primary" points="${coords.map((coord) => `${coord.x.toFixed(1)},${coord.y.toFixed(1)}`).join(" ")}" />
      ${coords.map((coord) => `<circle class="trend-dot" cx="${coord.x.toFixed(1)}" cy="${coord.y.toFixed(1)}" r="3"><title>${escapeAttr(coord.point.label || "")}: ${escapeAttr(coord.point.value)} ${escapeAttr(coord.point.record || "")}</title></circle>`).join("")}
      <text class="trend-axis left" x="${padX}" y="${height - 4}">${escapeHtml(rows[0]?.label || "")}</text>
      <text class="trend-axis right" x="${width - padX}" y="${height - 4}">${escapeHtml(options.endLabel || rows[rows.length - 1]?.label || "")}</text>
    </svg>`;
}

function multiLineChart(lines, options = {}) {
  const usable = lines.filter((line) => Array.isArray(line.points) && line.points.length);
  if (!usable.length) return `<div class="empty">${escapeHtml(options.empty || "No chart data.")}</div>`;
  const values = usable.flatMap((line) => line.points.map((point) => Number(point.value))).filter(Number.isFinite);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const width = 420;
  const height = 155;
  const padX = 24;
  const padY = 18;
  const colors = ["#2fbf75", "#5b8fd9", "#d7b84f", "#d94a4a", "#966ce6", "#46becd", "#e68c46", "#c2c2c2"];
  const paths = usable.slice(0, 8).map((line, lineIndex) => {
    const points = line.points.length === 1 ? [{ ...line.points[0], label: "Start" }, line.points[0]] : line.points;
    const coords = points.map((point, index) => {
      const x = padX + (points.length <= 1 ? 0 : (index / (points.length - 1)) * (width - padX * 2));
      const y = height - padY - ((Number(point.value || 0) - min) / span) * (height - padY * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return `<polyline class="trend-line" style="stroke:${colors[lineIndex % colors.length]}" points="${coords.join(" ")}"><title>${escapeHtml(line.name || "Player")}</title></polyline>`;
  }).join("");
  const legend = usable.slice(0, 6).map((line, index) => `
    <span><i style="background:${colors[index % colors.length]}"></i>${escapeHtml(shortName(line.name || "Player"))}</span>
  `).join("");
  return `
    <svg class="trend-svg multi" viewBox="0 0 ${width} ${height}" role="img" aria-label="Player development trend">
      <path class="trend-grid" d="M${padX} ${padY}H${width - padX}M${padX} ${height / 2}H${width - padX}M${padX} ${height - padY}H${width - padX}" />
      ${paths}
    </svg>
    <div class="trend-legend">${legend}</div>`;
}

function developmentLineChart(lines, options = {}) {
  if (!lines.length) return `<div class="empty">${escapeHtml(options.empty || "No chart data.")}</div>`;
  const months = developmentSeasonMonths();
  const series = lines.map((line) => normalizeDevelopmentSeries(line, months));
  const paddedMin = -5;
  const paddedMax = 5;
  const span = paddedMax - paddedMin;
  const width = 560;
  const height = 220;
  const padX = 24;
  const padY = 17;
  const colors = developmentLineColors();
  const paths = series.map((line, lineIndex) => {
    const coords = line.values.map((value, index) => {
      if (!Number.isFinite(value)) return null;
      const x = padX + (index / Math.max(1, months.length - 1)) * (width - padX * 2);
      const y = height - padY - ((clampNumber(Number(value || 0), paddedMin, paddedMax) - paddedMin) / span) * (height - padY * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).filter(Boolean);
    const color = colors[lineIndex % colors.length];
    if (coords.length <= 1) {
      const [point] = coords;
      if (!point) return "";
      const [x, y] = point.split(",");
      return `<circle class="trend-dot" style="fill:${color}" cx="${x}" cy="${y}" r="2.4"><title>${escapeHtml(line.name || "Player")}</title></circle>`;
    }
    return `<polyline class="trend-line" style="stroke:${color}" points="${coords.join(" ")}"><title>${escapeHtml(line.name || "Player")}</title></polyline>`;
  }).join("");
  return `
    <svg class="trend-svg development-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Player development trend">
      <path class="trend-grid" d="M${padX} ${padY}H${width - padX}M${padX} ${height / 2}H${width - padX}M${padX} ${height - padY}H${width - padX}" />
      <text class="trend-axis left" x="${padX}" y="${padY - 4}">+5</text>
      <text class="trend-axis left" x="${padX}" y="${height / 2 - 4}">0</text>
      <text class="trend-axis left" x="${padX}" y="${height - padY - 4}">-5</text>
      ${paths}
      ${months.map((month, index) => {
        const x = padX + (index / Math.max(1, months.length - 1)) * (width - padX * 2);
        return `<text class="trend-axis development-axis" x="${x.toFixed(1)}" y="${height - 3}">${escapeHtml(month.label)}</text>`;
      }).join("")}
    </svg>`;
}

function normalizeDevelopmentSeries(line, months) {
  const byLabel = new Map();
  const currentMonthIndex = developmentCurrentMonthIndex(months);
  let startValue = null;
  for (const point of line.points || []) {
    const label = String(point.label || "");
    const value = Number(point.value);
    if (label.toLowerCase() === "start") {
      if (Number.isFinite(value)) startValue = value;
      continue;
    }
    const month = label.length >= 7 ? label.slice(5, 7) : label.padStart(2, "0");
    if (Number.isFinite(value)) byLabel.set(month, value);
  }
  let current = Number.isFinite(startValue) ? startValue : Number(line.current || 0);
  const rawValues = months.map((month, index) => {
    if (index > currentMonthIndex) return null;
    if (byLabel.has(month.key)) current = byLabel.get(month.key);
    return current;
  });
  const baseline = Number.isFinite(startValue) ? startValue : rawValues.find(Number.isFinite) ?? current;
  const values = rawValues.map((value) => (Number.isFinite(value) ? value - baseline : null));
  return { name: line.name, values };
}

function developmentCurrentMonthIndex(months) {
  const date = state.home?.save?.current_date || "";
  const monthNumber = Number(date.slice(5, 7));
  const index = months.findIndex((month) => Number(month.key) === monthNumber);
  if (index >= 0) return index;
  if (monthNumber >= 7 && monthNumber <= 9) return months.length - 1;
  return 0;
}

function developmentSeasonMonths() {
  return [
    { key: "10", label: "Oct" },
    { key: "11", label: "Nov" },
    { key: "12", label: "Dec" },
    { key: "01", label: "Jan" },
    { key: "02", label: "Feb" },
    { key: "03", label: "Mar" },
    { key: "04", label: "Apr" },
    { key: "05", label: "May" },
    { key: "06", label: "Jun" },
  ];
}

function contractPayrollColumn(season, rows, cap) {
  const salaries = rows
    .map((row, index) => ({ row, index, salary: Number(row.salary_by_year?.[season] || 0) }))
    .filter((item) => item.salary > 0)
    .sort((a, b) => b.salary - a.salary);
  const tax = Number(cap?.tax_line_millions || 190);
  const hard = Number(cap?.hard_cap_millions || 230);
  const payroll = Number(cap?.salary_total_millions || salaries.reduce((sum, item) => sum + item.salary, 0));
  const scale = Math.max(hard, tax, payroll, 1) * 1.08;
  return `
    <div class="contract-payroll-column">
      <strong>${escapeHtml(season)}</strong>
      <div class="contract-payroll-stack-shell">
        <span class="contract-cap-line tax" style="bottom:${clampNumber((tax / scale) * 100, 0, 100)}%"><em>Tax</em></span>
        <span class="contract-cap-line hard" style="bottom:${clampNumber((hard / scale) * 100, 0, 100)}%"><em>Hard</em></span>
        <span class="contract-payroll-stack" style="height:${clampNumber((payroll / scale) * 100, 0, 100)}%">
          ${salaries.map((item) => `<span
            class="contract-salary-segment staff-salary-${item.index % 8}"
            style="height:${clampNumber((item.salary / Math.max(1, payroll)) * 100, 3, 100)}%"
            title="${escapeAttr(item.row.name)} ${money(item.salary)}"
          ></span>`).join("")}
        </span>
      </div>
      <span>${money(payroll)}</span>
    </div>`;
}

function simControls() {
  const save = state.home?.save || {};
  const currentDate = String(save.current_date || "");
  const isOffseasonRollover = String(save.phase || "") === "offseason" && currentDate.slice(5) >= "09-01";
  if (isOffseasonRollover) {
    return `
      <div class="actions calendar-actions">
        <button data-advance="next-season">Advance To Next Season</button>
      </div>`;
  }
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

function calendarHeaderDate(current, month) {
  const dateText = formatWrittenDate(current);
  if (dateText) return dateText;
  const [year, mon] = String(month || "").split("-").map(Number);
  if (!year || !mon) return "Calendar";
  return new Date(Date.UTC(year, mon - 1, 1)).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function formatWrittenDate(value) {
  const [year, month, day] = String(value || "").slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return "";
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function calendarGamePill(game, team, past) {
  const home = game.home || game.home_team;
  const away = game.away || game.away_team;
  const opponent = home === team ? away : home;
  const score = scoreLine(game);
  const result = game.result || resultForTeam(game, team);
  const cls = result === "W" ? "win" : result === "L" ? "loss" : "";
  const gameId = game.game_id || game.id;
  return `<button class="game-pill ${cls}" ${past && gameId ? `data-box-score="${escapeAttr(gameId)}"` : "disabled"}>${escapeHtml([opponent, score].filter(Boolean).join(" "))}</button>`;
}

function contractsBlock(rows, dash) {
  const seasons = contractSeasons(rows).slice(0, 4);
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
  const teamSelect = document.getElementById("dashboardTeamSelect");
  if (teamSelect) {
    teamSelect.addEventListener("change", async (event) => {
      await switchDashboardTeam(event.target.value || userTeam());
    });
  }
  els.content.querySelectorAll("[data-dashboard-team-jump]").forEach((button) => {
    button.addEventListener("click", async () => {
      await switchDashboardTeam(button.dataset.dashboardTeamJump || userTeam());
    });
  });
  els.content.querySelectorAll("[data-dashboard-trade]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.tradeTab = button.dataset.dashboardTrade || "builder";
      state.view = "trade";
      syncNavActive();
      await ensureViewData(true);
      render();
      window.scrollTo({ top: 0, left: 0 });
    });
  });
  els.content.querySelectorAll("[data-dashboard-offers]").forEach((button) => {
    button.addEventListener("click", openTradeOffersModal);
  });
  els.content.querySelectorAll("[data-dashboard-player-finder]").forEach((button) => {
    button.addEventListener("click", openPlayerFinderModal);
  });
  els.content.querySelectorAll("[data-standings-conference-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const current = button.dataset.standingsConference || "East";
      state.dashboardStandingsConference = current === "East" ? "West" : "East";
      renderDashboard();
    });
  });
  els.content.querySelectorAll("[data-standings-view-all]").forEach((button) => {
    button.addEventListener("click", openStandingsModal);
  });
  wireDevelopmentLegend();
  els.content.querySelectorAll("[data-dashboard-view]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.view = button.dataset.dashboardView || "dashboard";
      syncNavActive();
      await ensureViewData(true);
      render();
      window.scrollTo({ top: 0, left: 0 });
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
  els.content.querySelectorAll("[data-starting-slot-button]").forEach((button) => {
  button.addEventListener("click", () => {
    const slot = Number(button.dataset.startingSlotButton);
    if (!state.startingDraft) return;

    if (state.startingDraft[slot]) {
      state.startingDraft[slot] = "";
      state.startingPickerSlot = null;
    } else {
      state.startingPickerSlot = slot;
    }

    renderDashboard();
  });
  });

  els.content.querySelectorAll("[data-starting-pick]").forEach((button) => {
    button.addEventListener("click", () => {
      const slot = Number(state.startingPickerSlot);
      if (!slot || !state.startingDraft) return;

      state.startingDraft[slot] = button.dataset.startingPick;
      state.startingPickerSlot = null;
      renderDashboard();
    });
  });

  const closeStartingPicker = els.content.querySelector("[data-close-starting-picker]");
  if (closeStartingPicker) {
    closeStartingPicker.addEventListener("click", () => {
      state.startingPickerSlot = null;
      renderDashboard();
    });
  }

  const setStartingFive = document.getElementById("setStartingFive");
  if (setStartingFive) {
    setStartingFive.addEventListener("click", saveStartingFiveFromDraft);
  }
  const auto = document.getElementById("autoStartingFive");
  if (auto) auto.addEventListener("click", () => saveStartingFive({}, { auto: true }));
  els.content.querySelectorAll("[data-minute-player]").forEach((input) => {
    input.addEventListener("input", () => {
      const playerId = input.dataset.minutePlayer;
      const value = Number(input.value);

      state.rotationDraft[playerId] = value;

      const row = input.closest(".rotation-row");
      const output =
        row?.querySelector("output") ||
        Array.from(document.querySelectorAll("[data-minute-output]")).find((node) => node.dataset.minuteOutput === playerId);
      if (output) output.textContent = value;

      updateRotationMinuteCounter();
    });
  });
  const saveRotation = document.getElementById("saveRotation");
  if (saveRotation) saveRotation.addEventListener("click", saveRotationMinutes);
}

async function switchDashboardTeam(team) {
  state.dashboardTeam = team || userTeam();
  state.startingDraft = null;
  state.startingSavedSignature = "";
  state.startingPickerSlot = null;
  state.developmentPlayerIds = [];
  state.developmentSelectionTouched = false;
  await ensureViewData(true);
  renderDashboard();
}

function wireDevelopmentLegend() {
  els.content.querySelectorAll("[data-development-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      const playerId = button.dataset.developmentRemove;
      state.developmentSelectionTouched = true;
      clearDevelopmentNewBadge();
      state.developmentPlayerIds = state.developmentPlayerIds.filter((id) => id !== playerId);
      renderDashboard();
    });
  });
  els.content.querySelectorAll("[data-development-swap]").forEach((select) => {
    select.addEventListener("change", () => {
      const index = Number(select.dataset.developmentSwap || 0);
      const nextId = select.value;
      if (!nextId) return;
      state.developmentSelectionTouched = true;
      clearDevelopmentNewBadge();
      const draft = [...state.developmentPlayerIds];
      if (!draft.includes(nextId) || draft[index] === nextId) {
        draft[index] = nextId;
        state.developmentPlayerIds = [...new Set(draft)].slice(0, 5);
        renderDashboard();
      }
    });
  });
  const add = els.content.querySelector("[data-development-add]");
  const addSelect = els.content.querySelector("[data-development-add-select]");
  if (add && addSelect) {
    add.addEventListener("click", () => {
      if (state.developmentPlayerIds.length >= 5 || !addSelect.value) return;
      state.developmentSelectionTouched = true;
      clearDevelopmentNewBadge();
      if (!state.developmentPlayerIds.includes(addSelect.value)) {
        state.developmentPlayerIds = [...state.developmentPlayerIds, addSelect.value].slice(0, 5);
        renderDashboard();
      }
    });
  }
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

async function saveStartingFiveFromDraft() {
  const draft = state.startingDraft || {};
  const allFilled = [1, 2, 3, 4, 5].every((slot) => draft[slot]);

  if (!allFilled) {
    showToast("Fill all five starting spots before setting the lineup.", true);
    return;
  }

  await saveStartingFive({
    1: draft[1],
    2: draft[2],
    3: draft[3],
    4: draft[4],
    5: draft[5],
  });
}

async function saveStartingFive(slots, options = {}) {
  const payload = { ...savePayload(), team: userTeam() };
  if (options.auto) payload.auto = true;
  else payload.slots = slots;
  const result = await action("set_starting_five", payload);
  if (result.status === "blocked") return showToast(result.reason || "Starting 5 update blocked.", true);

  state.data.dashboard = result.dashboard;
  state.data.statusDashboard = result.dashboard;
  state.rotationDraft = {};
  state.startingDraft = null;
  state.startingSavedSignature = "";
  state.startingPickerSlot = null;

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

function playoffBracket(series, champion) {
  const finals = series.filter((item) => item.round === "finals");
  return `
    <div class="tournament-bracket">
      ${bracketConference("East", series)}
      <div class="bracket-finals">
        <div class="bracket-conference-title">Finals</div>
        ${finals.length ? finals.map((item) => `<div class="bracket-node final-node">${seriesCard(item)}</div>`).join("") : `<div class="bracket-node empty-final">Finals matchup pending</div>`}
        ${champion ? `<div class="bracket-champion">Champion: ${escapeHtml(teamLabel(champion))}</div>` : ""}
      </div>
      ${bracketConference("West", series)}
    </div>`;
}

function bracketConference(conference, series) {
  const roundOrder = ["first_round", "conference_semifinals", "conference_finals"];
  return `
    <div class="bracket-conference ${conference.toLowerCase()}">
      <div class="bracket-conference-title">${escapeHtml(conference)}</div>
      <div class="bracket-rounds">
        ${roundOrder.map((round) => bracketRound(round, series.filter((item) => item.conference === conference && item.round === round))).join("")}
      </div>
    </div>`;
}

function bracketRound(round, roundSeries) {
  return `
    <div class="bracket-round bracket-${escapeAttr(round)}">
      <div class="bracket-round-title">${escapeHtml(rowLabel(round))}</div>
      <div class="bracket-node-stack">
        ${roundSeries.length
          ? roundSeries.map((item) => `<div class="bracket-node">${seriesCard(item)}</div>`).join("")
          : `<div class="bracket-node bracket-placeholder">${escapeHtml(rowLabel(round))} pending</div>`}
      </div>
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

function plainNumber(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const cls = n >= 70 ? "grade-good" : n < 50 ? "grade-bad" : "grade-neutral";
  return `<span class="summary-rating ${cls}">${n.toFixed(1)}</span>`;
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

function activeHealthText(health) {
  if (!health) return "";
  const status = String(health.status || health.label || "").toLowerCase();
  if (!status || status === "healthy" || status === "active" || status === "ok") return "";
  return ` | ${health.label || health.status}`;
}

function isPlayerInjured(health) {
  if (!health) return false;
  const status = String(health.status || "").toLowerCase();
  const label = String(health.label || "").toLowerCase();
  return Boolean(status && !["ok", "healthy", "active"].includes(status)) || Boolean(label && !["ok", "healthy"].includes(label));
}

function rotationPlayerMeta(row) {
  const pieces = [
    compactPos(row.position),
    heightFromRow(row),
    rotationAgeText(row.age),
  ].filter(Boolean);
  const injury = rotationInjuryText(row.health);
  if (injury) pieces.push(injury);
  return escapeHtml(pieces.join(" | "));
}

function rotationAgeText(age) {
  if (age === undefined || age === null || age === "") return "";
  const value = Number(age);
  if (!Number.isFinite(value)) return `age ${age}`;
  return `age ${value.toFixed(value % 1 ? 1 : 0)}`;
}

function rotationInjuryText(health) {
  if (!isPlayerInjured(health)) return "";
  const label = String(health.label || health.status || "injured").trim();
  const match = label.match(/~\s*(\d+)\s*g/i);
  if (match) return `${label.replace(/\s*~\s*\d+\s*g/i, "").trim()} (${match[1]} games missed remaining)`;
  if (health.days_left !== undefined && health.days_left !== null) {
    const games = Math.max(1, Math.round(Number(health.days_left || 0) / 2.4));
    return `${label} (${games} games missed remaining)`;
  }
  return label;
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

function sectionHead(title, meta = "", extra = "") {
  return `<div class="section-head"><h3>${escapeHtml(title)}</h3>${extra || ""}${meta ? `<span class="pill">${escapeHtml(meta)}</span>` : ""}</div>`;
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
  return `<div class="table-wrap"><table class="data-table ${escapeAttr(tableId)}"><thead><tr>${headers.map((header, index) => `<th><button class="sort-head" data-sort-table="${escapeAttr(tableId)}" data-sort-index="${index}">${escapeHtml(header)}${sort?.index === index ? (sort.direction === "asc" ? " ↑" : " ↓") : ""}</button></th>`).join("")}</tr></thead><tbody>${mapped.map(({ cells }) => `<tr>${cells.map((cell) => `<td>${formatCell(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
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
  if (typeof value === "object" && value.html !== undefined) return value.html;
  if (typeof value === "number") return escapeHtml(Number.isInteger(value) ? String(value) : value.toFixed(1));
  if (typeof value === "string" && value.startsWith(`<span class="summary-rating`)) return value;
  return String(value).includes("<button") ? String(value) : escapeHtml(String(value));
}

function eventLine(event) {
  if (typeof event === "string") return escapeHtml(event);
  const date = event.date || event.created_at || "";
  const kind = event.kind || event.type || "";
  const text = event.text || event.headline || event.summary || event.description || textValue(event);
  return `<strong>${escapeHtml(date)} ${escapeHtml(kind)}</strong><span>${escapeHtml(text)}</span>`;
}

function leagueEventRotator() {
  const events = state.home?.league_events?.events || [];

  if (!events.length) {
    return `
      ${sectionHead("Recent League Events")}
      <div class="event-rotator empty">
        No recent league events.
      </div>`;
  }

  return `
    ${sectionHead("Recent League Events")}
    <div class="event-rotator" data-event-rotator data-event-index="0">
      <div class="event-rotator-body">
        ${leagueEventSlide(events[0])}
      </div>
      <div class="rotator-progress"><span></span></div>
    </div>
    <script type="application/json" id="leagueEventRotatorData">
      ${JSON.stringify(events.slice(0, 12)).replace(/</g, "\\u003c")}
    </script>`;
}

function leagueEventSlide(event) {
  const normalized = normalizeLeagueEvent(event);

  return `
    <div class="event-slide">
      <strong>${escapeHtml(normalized.date)}${normalized.kind ? ` ${escapeHtml(normalized.kind)}` : ""}</strong>
      <p>${escapeHtml(normalized.text)}</p>
    </div>`;
}

function normalizeLeagueEvent(event) {
  if (typeof event === "string") {
    return {
      date: "",
      kind: "",
      text: event,
    };
  }

  const date =
    event.date ||
    event.event_date ||
    event.created_at ||
    event.day ||
    "";

  const kind =
    event.kind ||
    event.type ||
    event.category ||
    "";

  const text =
    event.text ||
    event.headline ||
    event.summary ||
    event.message ||
    event.description ||
    event.details ||
    event.body ||
    event.content ||
    "";

  return {
    date: textValue(date),
    kind: textValue(kind),
    text: textValue(text || event),
  };
}

function postLine(post) {
  if (typeof post === "string") return escapeHtml(post);
  const header = `${post.date || ""} ${post.handle || post.author || ""} [${post.sentiment ?? "0.0"}] ${post.subject || post.event_subject || ""}`;
  return `<strong>${escapeHtml(header)}</strong><span>${escapeHtml(post.text || post.body || post.content || "")}</span>`;
}

function scoreLine(game) {
  if (game.away_score === null || game.away_score === undefined || game.away_score === "") return "";
  if (game.home_score === null || game.home_score === undefined || game.home_score === "") return "";
  const away = Number(game.away_score);
  const home = Number(game.home_score);
  if (Number.isFinite(away) && Number.isFinite(home)) return `${away}-${home}`;
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

function shortName(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length <= 1) return parts[0] || "";
  return `${parts[0][0]}. ${parts[parts.length - 1]}`;
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
