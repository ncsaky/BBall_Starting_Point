// This client owns interaction and presentation only. Basketball legality,
// simulation, and save mutations must remain behind the Python action API.
const state = {
  busy: false,
  busyDepth: 0,
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
  rotationLockedPlayerIds: new Set(),
  sorts: {},
  leagueTab: "standings",
  leagueStat: "points",
  leagueTrait: "overall",
  playoffLeaderStat: "points",
  draftPresentationStage: "",
  draftPresentationKey: "",
  draftBoardFilter: "available",
  draftBoardSort: { key: "rank", direction: "asc" },
  dashboardProspectSort: { key: "rank", direction: "asc" },
  selectedDraftProspect: "",
  draftSelectionPickKey: "",
  draftLedgerCenteredKey: "",
  tradeTab: "builder",
  tradePartner: "",
  tradeAssetFilters: { from: "all", to: "all" },
  selectedFrom: [],
  selectedTo: [],
  tradeCandidate: null,
  tradeResults: [],
  selectedFreeAgent: null,
  freeAgentCompareIds: [],
  freeAgentCompareMode: false,
  freeAgentMarketSort: { key: "overall", direction: "desc" },
  freeAgentMarketScope: "market",
  freeAgentShortlistIds: [],
  freeAgentFiltersOpen: false,
  freeAgentMarketFilters: { search: "", position: "all", minOverall: "" },
  playerCardDetails: {},
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
  dashboardContractView: "table",
  dashboardLeaguePanel: "wire",
  dashboardFreeAgentMode: "upcoming",
  dashboardWorkspace: "roster",
  dashboardIntelPanel: "profile",
  frontOfficeOpen: false,
  selectedFantasyPlayer: "",
  fantasySearch: "",
  fantasyPosition: "all",
  fantasyBoardScrollTop: 0,
  dashboardExperience: "unified",
  journeyChapter: "today",
  journeyObserver: null,
  hydrating: false,
  multiplayer: {
    session: null,
    league: null,
    manager: null,
    humanTradeOffers: [],
    lastSequence: 0,
    pollTimer: null,
    pollInFlight: false,
  },
};



const els = {};
const LAST_SAVE_KEY = "nbaGmLastSave";
const DASHBOARD_EXPERIENCE_KEY = "nbaGmDashboardExperience";
const MULTIPLAYER_SESSION_KEY = "nbaGmMultiplayerSession";
const MULTIPLAYER_MUTATIONS = new Set([
  "apply_contract",
  "submit_extension_offer",
  "apply_trade",
  "apply_trade_candidate",
  "draft_apply_current",
  "fantasy_draft_pick",
  "fantasy_draft_watchlist",
  "fire_staff",
  "hire_staff",
  "negotiate_staff",
  "respond_user_trade_offer",
  "resolve_staff_retention",
  "set_rotation_minutes",
  "set_starting_five",
  "submit_free_agent_offer",
  "waive_player",
]);
const DEVELOPMENT_LINE_LIMIT = 9;
const MULTIPLAYER_LOCAL_ACTIONS = new Set(["teams", "list_saves", "create_save", "runtime_status"]);
const TEAM_BRAND_COLORS = {
  ATL: ["#E03A3E", "#C1D32F"], BKN: ["#FFFFFF", "#6B7075"], BOS: ["#007A33", "#BA9653"],
  CHA: ["#1D1160", "#00788C"], CHI: ["#CE1141", "#000000"], CLE: ["#860038", "#FDBB30"],
  DAL: ["#00538C", "#B8C4CA"], DEN: ["#0E2240", "#FEC524"], DET: ["#C8102E", "#1D42BA"],
  GSW: ["#1D428A", "#FFC72C"], HOU: ["#CE1141", "#C4CED4"], IND: ["#002D62", "#FDBB30"],
  LAC: ["#C8102E", "#1D428A"], LAL: ["#552583", "#FDB927"], MEM: ["#5D76A9", "#12173F"],
  MIA: ["#98002E", "#F9A01B"], MIL: ["#00471B", "#EEE1C6"], MIN: ["#0C2340", "#78BE20"],
  NOP: ["#0C2340", "#C8102E"], NYK: ["#006BB6", "#F58426"], OKC: ["#007AC1", "#EF3B24"],
  ORL: ["#0077C0", "#C4CED4"], PHI: ["#006BB6", "#ED174C"], PHX: ["#1D1160", "#E56020"],
  POR: ["#E03A3E", "#A7A9AC"], SAC: ["#5A2D81", "#63727A"], SAS: ["#C4CED4", "#8A8D8F"],
  TOR: ["#CE1141", "#B4975A"], UTA: ["#002B5C", "#F9A01B"], WAS: ["#002B5C", "#E31837"],
};



document.addEventListener("DOMContentLoaded", () => {
  for (const id of [
    "startupRuntime",
    "startupSaveSelect",
    "startupRefreshSaves",
    "startupLoadSave",
    "teamSelect",
    "gameModeSelect",
    "saveName",
    "createSave",
    "nav",
    "startupScreen",
    "content",
    "toast",
    "modalRoot",
    "multiplayerBar",
    "multiplayerLobby",
    "multiplayerName",
    "multiplayerLeagueName",
    "multiplayerCode",
    "multiplayerCreate",
    "multiplayerJoin",
  ]) {
    els[id] = document.getElementById(id);
  }
  wireEvents();
  GameInterface.init({
    commands: gameCommands,
    busy: () => state.busy || state.hydrating,
    modal: () => state.modal,
    closeModal,
    error: error => showToast(error.message || String(error), true),
  });
  if (new URLSearchParams(location.search).has("ui-review")) {
    window.dispatchEvent(new Event("game-review-ready"));
    return;
  }
  init();
});

function gameCommands() {
  const ready = () => Boolean(state.currentSave && !state.hydrating);
  const navigate = (view) => async () => {
    closeAllModals();
    state.view = view;
    await ensureViewData();
    render();
  };
  const click = selector => () => GameInterface.findControl(selector)?.click();
  const available = selector => () => ready() && Boolean(GameInterface.findControl(selector));
  const commands = [
    {label:"This season", keys:"g h", run:navigate("dashboard"), available:ready},
    {label:"Trade builder", keys:"g t", run:() => openTradeRoomModal("builder"), available:() => ready() && (state.data.dashboard?.legal_actions || []).some(a => ["trades","draft_trades"].includes(a))},
    {label:"Trade finder", keys:"g b", run:() => openTradeRoomModal("finder"), available:() => ready() && (state.data.dashboard?.legal_actions || []).some(a => ["trades","draft_trades"].includes(a))},
    {label:"Trade offers", keys:"g o", run:openTradeOffersModal, available:ready},
    {label:"Player finder", keys:"g f", run:openPlayerFinderModal, available:ready},
    {label:"Prospects", keys:"g p", run:navigate("draft"), available:() => ready() && dashboardPhaseKind() !== "fantasy_draft"},
    {label:"Free agents", keys:"g a", run:navigate("freeagents"), available:() => ready() && dashboardPhaseKind() !== "fantasy_draft"},
    {label:"Standings", keys:"g l", run:openStandingsModal, available:() => ready() && Boolean(state.data.dashboardStandings)},
    {label:"Calendar", keys:"g c", run:navigate("calendar"), available:ready},
    {label:"Coaching staff", keys:"g s", run:navigate("staff"), available:ready},
    {label:"League wire", keys:"g n", run:openLeagueEventsModal, available:ready},
    {label:"Team development", keys:"g d", run:openTeamDevelopmentModal, available:() => ready() && Boolean(state.data.dashboardTrends)},
    {label:"Settings", keys:"g ,", run:openSettingsModal, available:ready},
    {label:"Next event / one pick / one playoff game", keys:"s e", run:click('[data-advance="next-event"], [data-playoff-sim="game"], #fantasySimOne, #draftSimCurrent, #faAdvanceDay, #reSignAdvanceDay'), available:available('[data-advance="next-event"], [data-playoff-sim="game"], #fantasySimOne, #draftSimCurrent, #faAdvanceDay, #reSignAdvanceDay')},
    {label:"Simulate week", keys:"s w", run:click('[data-advance="week"]'), available:available('[data-advance="week"]')},
    {label:"Simulate month", keys:"s m", run:click('[data-advance="month"]'), available:available('[data-advance="month"]')},
    {label:"Simulate to my pick", keys:"s p", run:click('#draftToUser, #fantasyToUser'), available:available('#draftToUser, #fantasyToUser')},
    {label:"Finish round", keys:"s r", run:click('[data-playoff-sim="round"]'), available:available('[data-playoff-sim="round"]')},
    {label:"Next phase", keys:"s n", run:click('#playoffAdvanceStage, #draftAdvanceStage, #faAdvanceStage, [data-advance="next-season"]'), available:available('#playoffAdvanceStage, #draftAdvanceStage, #faAdvanceStage, [data-advance="next-season"]')},
    {label:"Keyboard shortcuts", run:() => GameInterface.openPalette(true)},
    {label:"Screen gallery", run:() => window.open('/interface-gallery.html', '_blank', 'noopener')},
    {label:"Design studies", run:() => window.open('/design-lab.html', '_blank', 'noopener')},
  ];
  return commands.map(c => ({group:c.keys?.startsWith('s ') ? 'Simulation' : 'Navigation', ...c}));
}

function closeAllModals() {
  while (state.modal) closeModal();
}

function wireEvents() {
  els.startupRefreshSaves.addEventListener("click", loadSaves);
  els.startupSaveSelect.addEventListener("change", () => {
    els.startupLoadSave.disabled = !els.startupSaveSelect.value;
  });
  els.startupLoadSave.addEventListener("click", async () => {
    state.currentSave = els.startupSaveSelect.value || "";
    localStorage.setItem(LAST_SAVE_KEY, state.currentSave);
    state.view = "dashboard";
    state.dashboardTeam = "";
    await refreshHome();
  });
  els.createSave.addEventListener("click", createSave);
  els.multiplayerCreate.addEventListener("click", createMultiplayerLobby);
  els.multiplayerJoin.addEventListener("click", joinMultiplayerLobby);
  els.nav.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-view]");
    if (!button) return;
    if (dashboardPhaseKind() === "fantasy_draft" && button.dataset.view !== "dashboard") {
      showToast("Complete the fantasy draft before entering the front office.", true);
      return;
    }
    if (button.dataset.view === "trade") {
      await openTradeRoomModal();
      return;
    }
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
    if (event.target.closest("[data-design-studies]")) return window.open('/design-lab.html', '_blank', 'noopener');
    if (event.target.closest("[data-interface-shortcuts]")) return GameInterface.openPalette(true);
    if (event.target.closest("[data-interface-gallery]")) return window.open('/interface-gallery.html', '_blank', 'noopener');
    if (event.target.closest("[data-interface-home]")) {
      state.view = "dashboard";
      render();
      return;
    }
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
    if (refreshDashboardTable(button, tableId)) return;
    render();
  });
  els.modalRoot.addEventListener("click", (event) => {
    if (event.target === els.modalRoot || event.target.closest("[data-close-modal]")) closeModal();
  });
}

async function init() {
  let loadingStartedAt = null;
  try {
    loadingStartedAt = await showAppLoading();
    state.currentSave = localStorage.getItem(LAST_SAVE_KEY) || "";
    state.hydrating = Boolean(state.currentSave);
    render();
    const status = await apiGet("/api/status");
    els.startupRuntime.textContent = `${status.engine} | ${status.protocol_version}`;
    await loadTeams();
    await restoreMultiplayerSession();
    await loadSaves();
  } catch (error) {
    state.hydrating = false;
    render();
    showToast(error.message || String(error), true);
  } finally {
    await hideAppLoading(loadingStartedAt);
  }
}

async function apiGet(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function action(name, payload = {}) {
  state.busyDepth += 1;
  setBusy(true);
  try {
    if (
      state.multiplayer.session &&
      state.multiplayer.league?.status === "active" &&
      !MULTIPLAYER_LOCAL_ACTIONS.has(name)
    ) {
      const mutation = MULTIPLAYER_MUTATIONS.has(name);
      const response = await multiplayerRequest("game_action", {
        game_action: name,
        action_payload: payload,
        expected_revision: mutation ? state.multiplayer.league.revision : undefined,
        idempotency_key: mutation ? newIdempotencyKey(name) : undefined,
      });
      if (mutation && Number.isFinite(Number(response.revision))) {
        state.multiplayer.league.revision = Number(response.revision);
      }
      return response.result ?? response;
    }
    const response = await fetch("/api/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: name, payload }),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || `${response.status} ${response.statusText}`);
    return data.result;
  } finally {
    state.busyDepth = Math.max(0, state.busyDepth - 1);
    setBusy(state.busyDepth > 0 || state.hydrating);
  }
}

async function multiplayerRequest(name, payload = {}) {
  const session = state.multiplayer.session || {};
  const response = await fetch("/api/multiplayer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: name,
      payload: {
        ...payload,
        league_id: payload.league_id || session.league_id,
        manager_id: payload.manager_id || session.manager_id,
        session_token: payload.session_token || session.session_token,
      },
    }),
  });
  const data = await response.json();
  if (!response.ok || data.ok === false) {
    if (response.status === 409 && Number.isFinite(Number(data.current_revision)) && state.multiplayer.league) {
      state.multiplayer.league.revision = Number(data.current_revision);
      await refreshMultiplayerState(false);
    }
    throw new Error(data.error || `${response.status} ${response.statusText}`);
  }
  return data.result;
}

function newIdempotencyKey(actionName) {
  if (globalThis.crypto?.randomUUID) return `${actionName}:${crypto.randomUUID()}`;
  return `${actionName}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
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
  els.startupSaveSelect.innerHTML = playable.length
    ? playable.map((save) => `<option value="${escapeAttr(save.path)}">${escapeHtml(save.name)} | ${escapeHtml(save.team || "?")} | ${escapeHtml(save.current_date || "")}</option>`).join("")
    : '<option value="">No saves yet</option>';
  if (!playable.some((save) => save.path === state.currentSave)) state.currentSave = "";
  if (state.currentSave) {
    els.startupSaveSelect.value = state.currentSave;
  }
  els.startupLoadSave.disabled = !els.startupSaveSelect.value;
  await refreshHome();
}

async function createSave() {
  const team = els.teamSelect.value || "random";
  const gameMode = els.gameModeSelect.value || "standard";
  const saveName = els.saveName.value.trim();
  const result = await action("create_save", {
    team,
    game_mode: gameMode,
    save_name: saveName || undefined,
  });
  state.currentSave = result.save_path;
  localStorage.setItem(LAST_SAVE_KEY, state.currentSave);
  state.view = "dashboard";
  state.dashboardTeam = "";
  els.saveName.value = "";
  showToast(`Created ${teamLabel(result.save?.user_team || result.save?.team || "save")}`);
  await loadSaves();
}

async function createMultiplayerLobby() {
  const displayName = els.multiplayerName.value.trim();
  const leagueName = els.multiplayerLeagueName.value.trim();
  if (!displayName) return showToast("Enter your GM name first.", true);
  try {
    const result = await multiplayerRequest("create_lobby", {
      display_name: displayName,
      name: leagueName || `${displayName}'s League`,
    });
    adoptMultiplayerSession(result);
    renderStartup();
    startMultiplayerPolling();
  } catch (error) {
    showToast(error.message || String(error), true);
  }
}

async function joinMultiplayerLobby() {
  const displayName = els.multiplayerName.value.trim();
  const code = els.multiplayerCode.value.trim().toUpperCase();
  if (!displayName) return showToast("Enter your GM name first.", true);
  if (code.length !== 6) return showToast("Enter the six-character lobby code.", true);
  try {
    const result = await multiplayerRequest("join_lobby", { display_name: displayName, code });
    adoptMultiplayerSession(result);
    renderStartup();
    startMultiplayerPolling();
  } catch (error) {
    showToast(error.message || String(error), true);
  }
}

function adoptMultiplayerSession(result) {
  const league = result.league || result;
  const session = {
    league_id: league.id,
    manager_id: result.manager_id || state.multiplayer.session?.manager_id,
    session_token: result.session_token || state.multiplayer.session?.session_token,
  };
  state.multiplayer.session = session;
  state.multiplayer.league = league;
  state.multiplayer.manager = (league.managers || []).find((manager) => manager.id === session.manager_id) || null;
  localStorage.setItem(MULTIPLAYER_SESSION_KEY, JSON.stringify(session));
}

async function restoreMultiplayerSession() {
  const raw = localStorage.getItem(MULTIPLAYER_SESSION_KEY);
  if (!raw) return;
  try {
    const session = JSON.parse(raw);
    if (!session.league_id || !session.manager_id || !session.session_token) throw new Error("Incomplete session");
    state.multiplayer.session = session;
    const league = await multiplayerRequest("lobby_state");
    state.multiplayer.league = league;
    state.multiplayer.manager = (league.managers || []).find((manager) => manager.id === session.manager_id) || null;
    if (league.status === "active" && league.save_path) {
      state.currentSave = league.save_path;
      localStorage.setItem(LAST_SAVE_KEY, league.save_path);
    }
    startMultiplayerPolling();
  } catch {
    leaveMultiplayerSession(false);
  }
}

async function refreshMultiplayerState(renderAfter = true) {
  if (!state.multiplayer.session) return;
  try {
    const previousRevision = Number(state.multiplayer.league?.revision ?? -1);
    const league = await multiplayerRequest("lobby_state");
    const wasActive = state.multiplayer.league?.status === "active";
    const changed = Number(league.revision ?? -1) !== previousRevision || league.status !== state.multiplayer.league?.status;
    state.multiplayer.league = league;
    state.multiplayer.manager = (league.managers || []).find(
      (manager) => manager.id === state.multiplayer.session.manager_id,
    ) || null;
    if (league.status === "active" && league.save_path && (!wasActive || state.currentSave !== league.save_path)) {
      state.currentSave = league.save_path;
      localStorage.setItem(LAST_SAVE_KEY, league.save_path);
      await refreshHome();
      return;
    }
    if (renderAfter && changed) {
      if (state.currentSave) renderMultiplayerBar();
      else renderStartup();
    }
  } catch (error) {
    showToast(error.message || String(error), true);
  }
}

function startMultiplayerPolling() {
  if (state.multiplayer.pollTimer) clearInterval(state.multiplayer.pollTimer);
  if (!state.multiplayer.session) return;
  state.multiplayer.pollTimer = setInterval(async () => {
    if (state.multiplayer.pollInFlight) return;
    state.multiplayer.pollInFlight = true;
    try {
      await refreshMultiplayerState(false);
      await pollMultiplayerEvents();
      if (state.currentSave) renderMultiplayerBar();
      else renderStartup();
    } finally {
      state.multiplayer.pollInFlight = false;
    }
  }, 2000);
}

async function pollMultiplayerEvents() {
  if (!state.multiplayer.session) return;
  try {
    const result = await multiplayerRequest("events", {
      after_sequence: state.multiplayer.lastSequence,
      limit: 50,
    });
    const events = result.events || [];
    state.multiplayer.lastSequence = Number(result.last_sequence || state.multiplayer.lastSequence);
    if (state.multiplayer.league && Number.isFinite(Number(result.revision))) {
      state.multiplayer.league.revision = Number(result.revision);
    }
    const advanced = events.some((event) => event.kind === "league_advanced");
    const humanEvent = [...events].reverse().find((event) => event.important && event.actor_manager_id !== state.multiplayer.session.manager_id);
    if (humanEvent) showToast(multiplayerEventText(humanEvent));
    if (advanced && state.currentSave) await refreshHome();
    if (state.multiplayer.league?.status === "active") {
      const tradeInbox = await multiplayerRequest("human_trade_offers");
      state.multiplayer.humanTradeOffers = tradeInbox.offers || [];
    }
  } catch {
    // Reconnect polling is intentionally quiet; the next successful pass
    // catches up from the last durable event sequence.
  }
}

function multiplayerEventText(event) {
  const payload = event.payload || {};
  if (payload.summary) return payload.summary;
  if (event.kind === "team_claimed") return `${payload.display_name || "A GM"} claimed a team.`;
  if (event.kind === "manager_joined") return `${payload.display_name || "A GM"} joined the league.`;
  if (event.kind === "league_advanced") return `League advanced to ${payload.phase_after || "the next window"}.`;
  return String(event.kind || "League update").replaceAll("_", " ");
}

function leaveMultiplayerSession(renderAfter = true) {
  if (state.multiplayer.pollTimer) clearInterval(state.multiplayer.pollTimer);
  state.multiplayer = {
    session: null,
    league: null,
    manager: null,
    humanTradeOffers: [],
    lastSequence: 0,
    pollTimer: null,
    pollInFlight: false,
  };
  localStorage.removeItem(MULTIPLAYER_SESSION_KEY);
  if (renderAfter) render();
}

async function refreshHome() {
  clearViewCaches();
  if (!state.currentSave) {
    state.hydrating = false;
    state.home = null;
    setBusy(state.busyDepth > 0);
    render();
    return;
  }
  state.hydrating = true;
  setBusy(true);
  try {
    const listedTeam = state.saves.find((save) => save.path === state.currentSave)?.team || "";
    if (state.view === "dashboard") {
      const snapshot = await loadDashboardSnapshot(state.dashboardTeam || listedTeam || userTeam());
      if (!state.dashboardTeam) state.dashboardTeam = userTeam();
      syncDefaultPartner();
      applyPhaseRouting();
      if (snapshot.phase_only) await ensureViewData(true);
      return;
    }
    state.home = await action("home", savePayload());
    if (!state.dashboardTeam) state.dashboardTeam = userTeam();
    syncDefaultPartner();
    applyPhaseRouting();
    await ensureViewData(true);
  } finally {
    state.hydrating = false;
    setBusy(state.busyDepth > 0);
    render();
  }
}

function clearViewCaches() {
  state.data = {};
  state.playerCardDetails = {};
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
  if (dashboardPhaseKind() === "fantasy_draft") {
    if (force || !state.data.fantasyDraft) {
      state.data.fantasyDraft = await action("fantasy_draft_room", {
        ...savePayload(),
        team: userTeam(),
      });
    }
    return;
  }
  const key = state.view;
  if (key === "dashboard" && !dashboardPhaseKind()) {
    await loadDashboardSnapshot(state.dashboardTeam || userTeam());
    return;
  }
  if (force || !state.data.statusDashboard) {
    state.data.statusDashboard = await action("team_dashboard", { ...savePayload(), team: userTeam() });
  }
  if (!force && state.data[key]) return;
  if (key === "dashboard") {
    const team = state.dashboardTeam || userTeam();
    state.data.dashboard = team === userTeam()
      ? state.data.statusDashboard
      : await action("team_dashboard", { ...savePayload(), team });
    if (team === userTeam()) {
      state.data.staff = await action("staff_room", {
        ...savePayload(),
        team: userTeam(),
        limit: 60,
      });
    }
    const phase = dashboardPhaseKind();
    if (phase === "fantasy_draft") {
      state.data.fantasyDraft = await action("fantasy_draft_room", {
        ...savePayload(),
        team: userTeam(),
      });
    }
    if (phase === "playoffs") {
      state.data.playoffs = await action("playoff_room", savePayload());
      state.data.playoffLeaders = await action("playoff_leaders", { ...savePayload(), stat: state.playoffLeaderStat, limit: 9 });
    }
    if (phase === "draft") {
      state.data.draft = await action("draft_room", { ...savePayload(), team: userTeam(), seed: 7 });
    }
    if (phase === "free_agency") {
      state.data.freeagency = await action("free_agency_room", { ...savePayload(), team: userTeam(), seed: 7 });
    }
    if (phase === "staff_retention") {
      state.data.staffRetention = await action("staff_retention_room", savePayload());
    }
    if (phase === "cutdown") {
      state.data.cutdown = await action("roster_cutdown", savePayload());
    }
    if (phase) return;
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

async function loadDashboardSnapshot(team) {
  const current = state.home?.save?.current_date || "";
  const month = state.calendarMonth || current.slice(0, 7);
  const from = month ? `${month}-01` : undefined;
  const snapshot = await action("dashboard_snapshot", {
    ...savePayload(),
    team,
    from_date: from,
    through_date: from ? monthEndDate(from) : undefined,
    draft_year: state.home ? dashboardProspectYear() : undefined,
    leader_limit: 9,
    prospect_limit: 8,
  });
  applyDashboardSnapshot(snapshot, team);
  return snapshot;
}

function applyDashboardSnapshot(snapshot, team) {
  state.home = snapshot.home || state.home;
  state.dashboardRevision = snapshot.revision || "";
  if (snapshot.phase_only) return snapshot;
  state.data.dashboard = snapshot.dashboard;
  if (team === userTeam()) state.data.statusDashboard = snapshot.dashboard;
  state.data.dashboardStandings = snapshot.standings;
  state.data.dashboardSummaryLeaders = snapshot.summary_leaders;
  state.data.dashboardTrends = snapshot.trends;
  state.data.dashboardMorale = snapshot.morale;
  state.data.dashboardCalendar = snapshot.calendar;
  state.data.dashboardOffers = snapshot.offers;
  state.data.dashboardOpponent = snapshot.opponent;
  state.data.dashboardProspects = snapshot.prospects;
  return snapshot;
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
  const showLoading = Boolean(payload?.next_event || [7, 31].includes(Number(payload?.days)));
  let loadingStartedAt = null;
  try {
    if (showLoading) loadingStartedAt = await showAppLoading();
    return await advanceSave(payload);
  } finally {
    if (showLoading) await hideAppLoading(loadingStartedAt);
  }
}

async function advanceSave(payload) {
  if (!state.currentSave) return showToast("Create or select a save first.", true);
  if (!(await ensureStartingFiveReadyForAdvance())) return;
  if (state.multiplayer.league?.status === "active") {
    try {
      const result = await multiplayerRequest("set_ready", {
        ready: true,
        expected_revision: state.multiplayer.league.revision,
      });
      state.multiplayer.league = result.league || result;
      state.multiplayer.manager = state.multiplayer.league.managers.find(
        (row) => row.id === state.multiplayer.session.manager_id,
      );
      if (result.status === "advanced") {
        await refreshHome();
        showToast("Every manager was ready. The league advanced.");
      } else {
        renderMultiplayerBar();
        showToast("Ready recorded. The league advances when everyone is ready or the clock expires.");
      }
      return;
    } catch (error) {
      showToast(error.message || String(error), true);
      return;
    }
  }
  const previousDevelopmentSignature = developmentTrendSignature();
  const result = await action("advance_save", { ...savePayload(), ...payload });
  state.home = result.home;
  clearViewCaches();
  applyPhaseRouting();
  if (result.dashboard_snapshot && !result.dashboard_snapshot.phase_only) {
    applyDashboardSnapshot(result.dashboard_snapshot, userTeam());
  } else {
    await ensureViewData(true);
  }
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

function returnToSaveSelection() {
  if (state.multiplayer.session) leaveMultiplayerSession(false);
  localStorage.removeItem(LAST_SAVE_KEY);
  state.currentSave = "";
  state.home = null;
  state.view = "dashboard";
  state.dashboardTeam = "";
  clearViewCaches();
  closeAllModals();
  render();
}

function render() {
  const save = state.home?.save;
  applyPhaseRouting();
  if (state.view !== "dashboard" || !state.currentSave) window.CardBoard?.unmount();
  document.body.dataset.view = state.currentSave ? state.view : "startup";
  els.startupScreen.hidden = Boolean(state.currentSave);
  if (!state.currentSave) {
    renderStartup();
    return;
  }
  els.startupScreen.hidden = true;
  document.getElementById("roomNavigation")?.remove();
  if (state.view !== "dashboard") {
    const navigation = document.createElement("nav");
    navigation.id = "roomNavigation";
    navigation.setAttribute("aria-label", "Room navigation");
    navigation.innerHTML = `<button type="button" data-interface-home aria-label="Back to this season">← This season</button><span>${escapeHtml(rowLabel(state.view === "freeagents" ? "free_agents" : state.view))}</span><button type="button" onclick="GameInterface.openPalette()" aria-label="Open commands">Commands <kbd>⌘K</kbd></button>`;
    els.content.before(navigation);
  }
  renderMultiplayerBar();
  syncNavActive();
  if (state.view !== "dashboard") stopDashboardRotatorClock();
  if (state.view === "dashboard") renderDashboard();
  // Trade Room is an overlay so the user never loses the dashboard context.
  if (state.view === "trade") {
    state.view = "dashboard";
    syncNavActive();
    renderDashboard();
  }
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
  document.getElementById("roomNavigation")?.remove();
  els.content.innerHTML = "";
  els.startupScreen.hidden = false;
  els.startupLoadSave.disabled = !els.startupSaveSelect.value;
  const grid = els.startupScreen.querySelector(".startup-grid");
  const league = state.multiplayer.league;
  if (!league) {
    grid.hidden = false;
    els.multiplayerLobby.hidden = true;
    els.multiplayerLobby.innerHTML = "";
    return;
  }
  grid.hidden = true;
  els.multiplayerLobby.hidden = false;
  const manager = state.multiplayer.manager || {};
  const isHost = league.host_manager_id === manager.id;
  const claimedByTeam = new Map((league.managers || []).filter((row) => row.team_id).map((row) => [row.team_id, row]));
  const allReady = Boolean(league.managers?.length) && league.managers.every((row) => row.ready);
  els.multiplayerLobby.innerHTML = `
    <header class="multiplayer-lobby-head">
      <div>
        <p class="eyebrow">Multiplayer Lobby</p>
        <h2>${escapeHtml(league.name || "Shared League")}</h2>
        <p>${league.managers?.length || 0} human GM${league.managers?.length === 1 ? "" : "s"} · AI controls every open team</p>
      </div>
      <button class="lobby-code" data-copy-lobby-code title="Copy join code">
        <span>Join code</span><strong>${escapeHtml(league.code || "")}</strong>
      </button>
    </header>
    <div class="multiplayer-lobby-layout">
      <section class="lobby-team-board">
        <div class="section-head">
          <div><p class="eyebrow">Franchises</p><h3>Claim Your Team</h3></div>
          <span>${claimedByTeam.size}/30 claimed</span>
        </div>
        <div class="lobby-team-grid">
          ${(league.teams || []).map((team) => {
            const owner = claimedByTeam.get(team.id);
            const mine = owner?.id === manager.id;
            return `<button
              class="lobby-team ${owner ? "claimed" : ""} ${mine ? "mine" : ""}"
              data-claim-team="${escapeAttr(team.id)}"
              ${owner && !mine ? "disabled" : ""}
              title="${escapeAttr(owner ? `${owner.display_name} controls ${team.name}` : `Claim ${team.name}`)}">
                <img src="/assets/team_logos/${escapeAttr(team.abbrev)}.png" alt="" />
                <span>${escapeHtml(team.abbrev)}</span>
                <small>${escapeHtml(owner?.display_name || "Open")}</small>
              </button>`;
          }).join("")}
        </div>
      </section>
      <aside class="lobby-control-rail">
        <section class="lobby-managers">
          <p class="eyebrow">Managers</p>
          ${(league.managers || []).map((row) => {
            const team = (league.teams || []).find((item) => item.id === row.team_id);
            return `<div class="lobby-manager-row ${row.id === manager.id ? "mine" : ""}">
              <span class="ready-light ${row.ready ? "ready" : ""}"></span>
              <strong>${escapeHtml(row.display_name)}</strong>
              <span>${escapeHtml(team?.abbrev || "Choosing")}${row.is_host ? " · Host" : ""}</span>
            </div>`;
          }).join("")}
        </section>
        <section class="lobby-rules">
          <p class="eyebrow">League Clock</p>
          <label>Opening rosters
            <select id="lobbyGameMode" ${isHost ? "" : "disabled"}>
              <option value="standard" ${league.settings?.game_mode !== "fantasy_draft" ? "selected" : ""}>Standard rosters</option>
              <option value="fantasy_draft" ${league.settings?.game_mode === "fantasy_draft" ? "selected" : ""}>Fantasy draft</option>
            </select>
          </label>
          <label>Advance
            <select id="lobbyAdvanceStep" ${isHost ? "" : "disabled"}>
              <option value="week" ${league.settings?.advance_step === "week" ? "selected" : ""}>One week per window</option>
              <option value="month" ${league.settings?.advance_step === "month" ? "selected" : ""}>One month per window</option>
            </select>
          </label>
          <label>Window length
            <input id="lobbyWindowSeconds" type="number" min="30" max="86400" value="${Number(league.settings?.action_window_seconds || 300)}" ${isHost ? "" : "disabled"} />
          </label>
          <label>Dynasty length
            <input id="lobbySeasonCount" type="number" min="1" max="20" value="${Number(league.settings?.season_count || 3)}" ${isHost ? "" : "disabled"} />
          </label>
          <label>Fantasy pick clock
            <input id="lobbyFantasyPickSeconds" type="number" min="15" max="600" value="${Number(league.settings?.fantasy_pick_seconds || 90)}" ${isHost ? "" : "disabled"} />
          </label>
          ${isHost ? '<button data-save-lobby-rules>Save League Rules</button>' : ""}
        </section>
        <div class="lobby-actions">
          <button data-lobby-ready class="${manager.ready ? "ready" : ""}" ${manager.team_id ? "" : "disabled"}>
            ${manager.ready ? "Ready ✓" : "Mark Ready"}
          </button>
          ${isHost ? `<button data-start-multiplayer class="primary-action" ${league.managers?.length >= 2 && allReady ? "" : "disabled"}>Start League</button>` : ""}
          <button data-leave-multiplayer>Leave Lobby</button>
        </div>
      </aside>
    </div>`;
  wireMultiplayerLobby();
}

function wireMultiplayerLobby() {
  const league = state.multiplayer.league;
  if (!league) return;
  els.multiplayerLobby.querySelector("[data-copy-lobby-code]")?.addEventListener("click", async () => {
    await navigator.clipboard?.writeText(league.code || "");
    showToast("Lobby code copied.");
  });
  els.multiplayerLobby.querySelectorAll("[data-claim-team]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        const next = await multiplayerRequest("claim_team", {
          team_id: button.dataset.claimTeam,
          expected_revision: state.multiplayer.league.revision,
        });
        state.multiplayer.league = next;
        state.multiplayer.manager = next.managers.find((row) => row.id === state.multiplayer.session.manager_id);
        renderStartup();
      } catch (error) {
        showToast(error.message || String(error), true);
      }
    });
  });
  els.multiplayerLobby.querySelector("[data-save-lobby-rules]")?.addEventListener("click", async () => {
    try {
      const next = await multiplayerRequest("update_settings", {
        expected_revision: state.multiplayer.league.revision,
        settings: {
          game_mode: document.getElementById("lobbyGameMode")?.value,
          advance_step: document.getElementById("lobbyAdvanceStep")?.value,
          action_window_seconds: Number(document.getElementById("lobbyWindowSeconds")?.value || 300),
          season_count: Number(document.getElementById("lobbySeasonCount")?.value || 3),
          fantasy_pick_seconds: Number(document.getElementById("lobbyFantasyPickSeconds")?.value || 90),
        },
      });
      state.multiplayer.league = next;
      renderStartup();
      showToast("League rules updated.");
    } catch (error) {
      showToast(error.message || String(error), true);
    }
  });
  els.multiplayerLobby.querySelector("[data-lobby-ready]")?.addEventListener("click", async () => {
    try {
      const next = await multiplayerRequest("set_ready", {
        ready: !state.multiplayer.manager?.ready,
        expected_revision: state.multiplayer.league.revision,
      });
      state.multiplayer.league = next.league || next;
      state.multiplayer.manager = state.multiplayer.league.managers.find(
        (row) => row.id === state.multiplayer.session.manager_id,
      );
      renderStartup();
    } catch (error) {
      showToast(error.message || String(error), true);
    }
  });
  els.multiplayerLobby.querySelector("[data-start-multiplayer]")?.addEventListener("click", async () => {
    try {
      const next = await multiplayerRequest("start_league", {
        expected_revision: state.multiplayer.league.revision,
      });
      state.multiplayer.league = next;
      state.multiplayer.manager = next.managers.find((row) => row.id === state.multiplayer.session.manager_id);
      state.currentSave = next.save_path;
      localStorage.setItem(LAST_SAVE_KEY, next.save_path);
      await refreshHome();
      startMultiplayerPolling();
    } catch (error) {
      showToast(error.message || String(error), true);
    }
  });
  els.multiplayerLobby.querySelector("[data-leave-multiplayer]")?.addEventListener("click", () => {
    leaveMultiplayerSession();
  });
}

function renderMultiplayerBar() {
  if (!els.multiplayerBar) return;
  const league = state.multiplayer.league;
  const manager = state.multiplayer.manager;
  if (!league || league.status !== "active") {
    els.multiplayerBar.hidden = true;
    els.multiplayerBar.innerHTML = "";
    return;
  }
  els.multiplayerBar.hidden = false;
  const deadline = Date.parse(league.clock?.deadline_at || "");
  const seconds = Number.isFinite(deadline) ? Math.max(0, Math.ceil((deadline - Date.now()) / 1000)) : 0;
  els.multiplayerBar.innerHTML = `
    <span class="multiplayer-live"><i></i>${escapeHtml(league.code)}</span>
    <span>${escapeHtml(manager?.display_name || "GM")} · ${escapeHtml(multiplayerTeamAbbrev() || "")}</span>
    <strong>${formatClock(seconds)}</strong>
    <button data-human-trade-inbox>GM Offers ${state.multiplayer.humanTradeOffers.filter((offer) => offer.direction === "incoming").length}</button>
    <button data-multiplayer-ready>${manager?.ready ? "Ready ✓" : "Ready Up"}</button>`;
  els.multiplayerBar.querySelector("[data-human-trade-inbox]")?.addEventListener("click", openHumanTradeInbox);
  els.multiplayerBar.querySelector("[data-multiplayer-ready]")?.addEventListener("click", async () => {
    try {
      const result = await multiplayerRequest("set_ready", {
        ready: !state.multiplayer.manager?.ready,
        expected_revision: state.multiplayer.league.revision,
      });
      state.multiplayer.league = result.league || result;
      state.multiplayer.manager = state.multiplayer.league.managers.find(
        (row) => row.id === state.multiplayer.session.manager_id,
      );
      if (result.status === "advanced") await refreshHome();
      renderMultiplayerBar();
    } catch (error) {
      showToast(error.message || String(error), true);
    }
  });
}

function openHumanTradeInbox() {
  const offers = state.multiplayer.humanTradeOffers || [];
  state.modal = {
    kind: "humanTradeOffers",
    title: "Human GM Trade Desk",
    subtitle: `${offers.filter((offer) => offer.direction === "incoming").length} incoming · ${offers.filter((offer) => offer.direction === "outgoing").length} awaiting response`,
    body: `<div class="trade-offers-list">
      ${offers.map((offer) => `
        <article class="trade-candidate-card ${offer.direction}">
          <header class="trade-candidate-head">
            <div><span>${offer.direction === "incoming" ? "Incoming from another GM" : "Awaiting another GM"}</span><strong>${escapeHtml(offer.headline || tradeHeadline(offer.candidate))}</strong></div>
            <span class="trade-legal-badge legal">PENDING</span>
          </header>
          <div class="trade-candidate-evals">${(offer.candidate?.evaluations || []).map(tradeEvaluationPanel).join("")}</div>
          ${offer.direction === "incoming"
            ? `<footer><p>The engine will revalidate every asset at acceptance.</p><div><button data-human-trade-reject="${escapeAttr(offer.id)}" class="trade-reject-button">Reject</button><button data-human-trade-accept="${escapeAttr(offer.id)}" class="trade-accept-button">Accept Trade</button></div></footer>`
            : `<footer><p>The other manager has not answered yet.</p></footer>`}
        </article>`).join("") || `<div class="trade-offers-empty"><strong>Your shared desk is clear.</strong><span>No human-manager proposals are waiting.</span></div>`}
    </div>`,
  };
  renderModal();
}

async function respondHumanTrade(offerId, decision) {
  try {
    const result = await multiplayerRequest("respond_human_trade", {
      offer_id: offerId,
      decision,
      expected_revision: state.multiplayer.league.revision,
      idempotency_key: newIdempotencyKey(`human-trade-${decision}`),
    });
    state.multiplayer.league.revision = Number(result.revision);
    const inbox = await multiplayerRequest("human_trade_offers");
    state.multiplayer.humanTradeOffers = inbox.offers || [];
    showToast(decision === "accept" ? "Human trade completed." : "Human trade rejected.");
    await refreshHome();
    openHumanTradeInbox();
    renderMultiplayerBar();
  } catch (error) {
    showToast(error.message || String(error), true);
  }
}

function multiplayerTeamAbbrev() {
  const id = state.multiplayer.manager?.team_id;
  return (state.teams || []).find((team) => team.id === id)?.abbrev || "";
}

function formatClock(totalSeconds) {
  const minutes = Math.floor(Math.max(0, totalSeconds) / 60);
  const seconds = Math.max(0, totalSeconds) % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function applyPhaseRouting() {
  if (!state.currentSave || !state.home?.save) return;
  // Seasonal command rooms now live inside the dashboard. Keep the legacy
  // routes callable, but never strand a save on a separate full-page screen.
  const phase = dashboardPhaseKind();
  if ((state.view === "draft" && phase === "draft") ||
      (state.view === "playoffs" && phase === "playoffs") ||
      (["freeagents", "freeagency"].includes(state.view) && phase === "free_agency")) state.view = "dashboard";
}

function dashboardPhaseKind() {
  const phase = String(state.home?.save?.phase || "");
  if (phase === "fantasy_draft") return "fantasy_draft";
  if (phase === "play_in" || phase === "playoffs") return "playoffs";
  if (phase === "draft_lottery" || phase === "draft") return "draft";
  if (phase === "re_signing" || phase === "free_agency") return "free_agency";
  if (Number(state.home?.save?.pending_counts?.staff || 0) > 0) return "staff_retention";
  if (Number(state.home?.save?.pending_counts?.cutdowns || 0) > 0) return "cutdown";
  return "";
}

function syncNavActive() {
  for (const button of els.nav.querySelectorAll("button[data-view]")) {
    button.classList.toggle("active", button.dataset.view === state.view || (button.dataset.view === "freeagents" && state.view === "freeagency"));
  }
}

function renderDashboard() {
  window.CardBoard?.unmount();
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

function rememberFantasyBoardScroll() {
  const board = document.querySelector(".fantasy-player-table");
  if (board) state.fantasyBoardScrollTop = board.scrollTop;
}

function restoreFantasyBoardScroll() {
  const board = document.querySelector(".fantasy-player-table");
  if (!board) return;
  const savedTop = Number(state.fantasyBoardScrollTop || 0);
  board.scrollTop = savedTop;
  requestAnimationFrame(() => {
    const currentBoard = document.querySelector(".fantasy-player-table");
    if (currentBoard) currentBoard.scrollTop = savedTop;
  });
}

function renderDashboardTab(rows) {
  const target = document.getElementById("dashboardTab");
  const dash = state.data.dashboard || {};
  const editable = !state.hydrating && teamLabel(dash.team || state.dashboardTeam) === userTeam();
  const readonlyClass = editable ? "" : " readonly-card";
  const phaseKind = dashboardPhaseKind();
  if (state.dashboardTab === "overview") {
    const viewedTeam = teamLabel(dash.team || state.dashboardTeam || userTeam());
    document.body.dataset.dashboardExperience = "unified";
    target.innerHTML = unifiedDashboardMarkup(rows, dash, editable, readonlyClass, phaseKind, viewedTeam);
    wireDashboardOverview(editable);
    if (!phaseKind && typeof mountDashboardCardBoard === "function") mountDashboardCardBoard(target);
    if (phaseKind) {
      wireDashboardPhaseWorkspace(phaseKind);
    }
    if (phaseKind === "fantasy_draft") restoreFantasyBoardScroll();
    if (!phaseKind) {
      startLeagueEventRotator();
      startSummaryLeaderRotator();
      startDashboardMarketRotators();
    }
    return;
  }
  target.innerHTML = contractsBlock(rows, dash);
  wireContractsBlock();
}

function unifiedDashboardMarkup(rows, dash, editable, readonlyClass, phaseKind, viewedTeam) {
  if (phaseKind) {
    return `<div class="unified-phase-dashboard" data-phase="${escapeAttr(phaseKind)}" ${teamBrandStyle(viewedTeam)}>
      ${dashboardPhaseWorkspace(phaseKind)}
      ${phaseKind === 'staff_retention' ? '' : '<button type="button" class="unified-phase-settings" data-dashboard-settings aria-label="Settings" title="Settings">⚙</button>'}
    </div>`;
  }
  return seasonCommandDashboardMarkup(rows, dash, editable, viewedTeam);
}

function seasonCommandDashboardMarkup(rows, dash, editable, viewedTeam) {
  const save = state.home?.save || {};
  const logo = teamLogoSrc(viewedTeam);
  const offerCount = Number(state.data.dashboardOffers?.offers?.length || 0);
  const legalActions = new Set(dash.legal_actions || []);
  const tradesOpen = legalActions.has("trades") || legalActions.has("draft_trades");
  const disabled = editable ? "" : "disabled";
  return `<div class="season-command-dashboard" ${teamBrandStyle(viewedTeam)}>
    <header class="season-command-header">
      <div class="season-command-club">
        ${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(viewedTeam)} logo" />` : ""}
        <span>${escapeHtml(dashboardTeamName(viewedTeam))}</span>
        ${viewedTeam !== userTeam() ? `<button type="button" data-dashboard-team-reset>My Team</button>` : ""}
      </div>
      <div class="season-command-date">
        <span>${escapeHtml(formatWrittenDate(save.current_date) || save.current_date || "")}</span>
        <span>${escapeHtml(rowLabel(save.phase || "season"))}</span>
      </div>
      <div class="season-command-actions">
        <button type="button" data-dashboard-settings>Settings</button>
      </div>
    </header>
    <main class="season-command-grid">
      <div class="season-diagnostics-row">
        <section class="season-command-panel season-identity-panel">${seasonIdentityCard(rows, dash)}</section>
        <div class="season-signals-panel">${seasonTeamSignalsCard(dash)}</div>
        <div class="season-radars-panel">${seasonTeamRadarsCard(rows, dash)}</div>
        <section class="season-command-panel season-standings-panel standings-card">${seasonStandingsCard(viewedTeam)}</section>
        <div class="season-matchup-stack">
          <section class="season-command-panel season-week-panel">${seasonWeekCard(dash, viewedTeam, editable)}</section>
          <section class="season-command-panel season-opponent-panel">${seasonOpponentCard(dash, viewedTeam)}</section>
        </div>
      </div>
      <div class="season-operations-row">
        <section class="season-command-panel season-minutes-panel">${seasonMinutesCard(rows, editable)}</section>
        <div class="season-intelligence-grid">
          <section class="season-command-panel season-efficiency-panel">${seasonEfficiencyCard(dash)}</section>
          <section class="season-command-panel season-prospects-panel">${seasonProspectsCard()}</section>
          <div class="season-intelligence-lower">
            <div class="season-awards-panel">${seasonAwardsCard(editable)}</div>
            <section class="season-command-panel season-staff-panel">${seasonStaffCard(dash, editable)}</section>
          </div>
        </div>
      </div>
    </main>
    ${seasonLeagueWire()}
  </div>`;
}

function seasonPanelHeader(title, action = "", artwork = "") {
  return `<header class="season-panel-header"><h2>${artwork ? gameArtworkTitle(title, artwork) : escapeHtml(title)}</h2>${action}</header>`;
}

function seasonIdentityCard(rows, dash) {
  return `${seasonPanelHeader("Team Identity")}
    <div class="season-identity-body">${spatialHeatmapMarkup(dash.spatial_profile, { compact: true })}</div>`;
}

function seasonTeamSignalsCard(dash) {
  const identity = dash.team_identity || {};
  const metrics = identity.metrics || {};
  const ranks = identity.ranks || {};
  const count = Number(identity.league_team_count || identity.team_count || 30);
  const broad = [
    ["Overall", metrics.overall, ranks.overall],
    ["Offense", metrics.offense, ranks.offense],
    ["Defense", metrics.defense, ranks.defense],
    ["Depth", metrics.depth, ranks.depth],
  ];
  const morale = state.data.dashboardMorale || {};
  const moraleRows = [
    ["Locker Room", averageNumber((morale.players || []).map((item) => item.morale?.overall ?? item.morale), 50)],
    ["Coach Trust", morale.team_morale?.overall ?? morale.team_morale ?? 50],
    ["Owner", morale.owner_confidence?.overall ?? morale.owner_confidence ?? 50],
    ["Fans", morale.fan_confidence?.overall ?? morale.fan_confidence ?? 50],
  ];
  const factors = state.data.dashboardTrends?.four_factors || [];
  return [
    ["Team Signals", broad.map(([label, value, rank]) => seasonIdentityBar(label, value, rank, count)).join("")],
    ["Morale", moraleRows.map(([label, value]) => seasonMoraleBar(label, value)).join("")],
    ["Four Factors", factors.map((factor) => seasonFactorBar(factor)).join("")],
  ].map(([title, body]) => `<section class="season-command-panel season-signal-card">${seasonPanelHeader(title)}<div class="season-identity-signals">${body}</div></section>`).join("");
}

function seasonTeamRadarsCard(rows, dash) {
  const identity = dash.team_identity || {};
  const ranks = identity.ranks || {};
  const count = Number(identity.league_team_count || identity.team_count || 30);
  const offenseAxes = [
    ["Shooting", "shooting", "spacing"],
    ["Range", "range", "spacing"],
    ["Creation", "creation", "creation"],
    ["Passing", "passing", "creation"],
    ["Rim pressure", "rim_pressure", "offense"],
    ["Off. rebounding", "rebounding", "depth"],
  ];
  const defenseAxes = [
    ["Defense", "defense", "defense"],
    ["Effort", "def_effort", "defense"],
    ["Screen nav", "screen_nav", "defense"],
    ["Rim deterrence", "rim_deterrence", "rim_protection"],
    ["Rebounding", "rebounding", "depth"],
    ["Athleticism", "athleticism", "defense"],
  ];
  return `<div class="season-radars-stack">
      ${seasonIdentityRadar("Offense", offenseAxes, rows, ranks, count)}
      ${seasonIdentityRadar("Defense", defenseAxes, rows, ranks, count)}
    </div>`;
}

function seasonIdentityBar(label, value, rank, count) {
  const numericRank = Number(rank || count);
  const width = clampNumber(((count - numericRank + 1) / Math.max(1, count)) * 100, 3, 100);
  return `<div class="season-signal-row">
    <span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(width)}"></b></i><strong>#${numericRank}/${count}</strong>
  </div>`;
}

function seasonMoraleBar(label, value) {
  const score = clampNumber(Number(value || 0), 0, 100);
  return `<div class="season-signal-row"><span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(score)}"></b></i><strong>${score.toFixed(0)}</strong></div>`;
}

function seasonFactorBar(factor) {
  const score = clampNumber(Number(factor.score || 0), 0, 100);
  const value = Number(factor.value || 0);
  const average = Number(factor.league_average || 0);
  return `<div class="season-signal-row season-factor-row" title="League average ${average.toFixed(1)}">
    <span>${escapeHtml(factor.label || "Factor")}</span><i><b style="${performanceBarStyle(score)}"></b><u style="left:50%"></u></i><strong>${value.toFixed(1)}</strong>
  </div>`;
}

function performanceBarColor(value) {
  const amount = clampNumber(Number(value || 0) / 100, 0, 1);
  const stops = [
    [0, [216, 75, 87]],
    [0.34, [229, 128, 82]],
    [0.52, [216, 190, 108]],
    [0.74, [105, 166, 216]],
    [1, [57, 120, 212]],
  ];
  const upperIndex = Math.max(1, stops.findIndex(([stop]) => amount <= stop));
  const [lowerStop, lowerColor] = stops[upperIndex - 1];
  const [upperStop, upperColor] = stops[upperIndex];
  const progress = upperStop === lowerStop ? 0 : (amount - lowerStop) / (upperStop - lowerStop);
  const channel = (index) => Math.round(lowerColor[index] + (upperColor[index] - lowerColor[index]) * progress).toString(16).padStart(2, "0");
  return `#${channel(0)}${channel(1)}${channel(2)}`;
}

function performanceBarStyle(value) {
  const score = clampNumber(Number(value || 0), 0, 100);
  return `--fill:${score}%;--bar-color:${performanceBarColor(score)}`;
}

function spatialEfficiencyColor(value) {
  const delta = Number(value || 0);
  return delta < -8 ? "#bd4b58" : delta < -3 ? "#db9199" : delta <= 3 ? "#a8b3bd" : delta <= 8 ? "#71a8d4" : "#347deb";
}

function spatialHexPoints(centerX, centerY, radius) {
  return Array.from({ length: 6 }, (_unused, index) => {
    const angle = Math.PI / 6 + (Math.PI / 3) * index;
    return `${(centerX + Math.cos(angle) * radius).toFixed(1)},${(centerY + Math.sin(angle) * radius).toFixed(1)}`;
  }).join(" ");
}

function spatialHexCells(profile, side) {
  const chart = profile?.shot_chart;
  if (!chart?.cells?.length) return "";
  const regions = new Map(chart.regions.map(region => [Number(region.id), region]));
  const leagueMeanDensity = chart.cells.reduce((total, cell) => total + Number(cell[5]), 0) / chart.cells.length;
  return chart.cells.map(([localX, y, regionId, offenseDensity, defenseDensity, leagueDensity]) => {
    const region = regions.get(Number(regionId));
    if (!region) return "";
    const density = Number(side === "offense" ? offenseDensity : defenseDensity);
    if (density < 0.000025) return "";
    const ratio = density / Math.max(leagueMeanDensity, 0.000025);
    const localRatio = density / Math.max(Number(leagueDensity), 0.000025);
    // Quantized area encodes relative attempts. Every mark remains a regular
    // hexagon on the same lattice, with no per-cell random size or color.
    const radius = ratio < 0.25 ? 2.5 : ratio < 0.6 ? 4.5 : ratio < 1.3 ? 7 : ratio < 2.2 ? 10 : 12;
    const delta = Number(side === "offense" ? region.delta_pp : region.suppression_delta_pp);
    const displayX = side === "defense" ? 940 - localX : localX;
    const value = side === "offense" && region.fg_pct != null
      ? `Projected FG ${Number(region.fg_pct).toFixed(1)}%, league ${Number(region.league_fg_pct).toFixed(1)}%`
      : side === "defense" ? "Modeled defensive suppression" : "Reference unavailable";
    const title = `${region.label}: ${value}; ${delta >= 0 ? "+" : ""}${delta.toFixed(1)} pp vs league; ${ratio.toFixed(2)}x league mean cell density; ${localRatio.toFixed(2)}x estimated league density at this location`;
    return `<polygon class="spatial-court-hex" data-side="${side}" data-region="${regionId}" data-density-ratio="${ratio.toFixed(3)}" points="${spatialHexPoints(displayX, y, radius)}" fill="${spatialEfficiencyColor(delta)}"><title>${escapeHtml(title)}</title></polygon>`;
  }).join("");
}

function spatialHeatmapMarkup(profile, options = {}) {
  if (!profile?.zones?.length) return `<div class="spatial-heatmap-empty">Spatial profile unavailable</div>`;
  const seed = String(profile.seed || profile.entity_id || "spatial").replace(/[^a-zA-Z0-9_-]/g, "");
  const offenseHexes = spatialHexCells(profile, "offense");
  const defenseHexes = spatialHexCells(profile, "defense");
  return `<div class="spatial-heatmap${options.compact ? " compact" : ""}">
    <div class="spatial-court-head"><h4>Offense</h4><h4>Defense</h4></div>
    <svg class="spatial-court" viewBox="0 0 940 500" role="img" aria-label="Projected shooting efficiency and modeled defensive suppression versus league average">
      <defs><clipPath id="spatial-court-clip-${seed}"><rect x="2" y="2" width="936" height="496"/></clipPath></defs>
      <rect class="spatial-court-floor" x="2" y="2" width="936" height="496"/>
      <g clip-path="url(#spatial-court-clip-${seed})">${offenseHexes}${defenseHexes}</g>
      <g class="spatial-court-markings">
        <rect class="spatial-court-line" x="2" y="2" width="936" height="496"/>
        <line class="spatial-court-line" x1="470" y1="2" x2="470" y2="498"/><circle class="spatial-court-line" cx="470" cy="250" r="60"/>
        <rect class="spatial-court-line" x="2" y="170" width="188" height="160"/><rect class="spatial-court-line" x="750" y="170" width="188" height="160"/>
        <path class="spatial-court-line" d="M190 190 A60 60 0 0 1 190 310"/><path class="spatial-court-line dashed" d="M190 190 A60 60 0 0 0 190 310"/>
        <path class="spatial-court-line" d="M750 190 A60 60 0 0 0 750 310"/><path class="spatial-court-line dashed" d="M750 190 A60 60 0 0 1 750 310"/>
        <line class="spatial-court-line" x1="40" y1="220" x2="40" y2="280"/><circle class="spatial-court-rim" cx="52.5" cy="250" r="7.5"/>
        <line class="spatial-court-line" x1="900" y1="220" x2="900" y2="280"/><circle class="spatial-court-rim" cx="887.5" cy="250" r="7.5"/>
        <path class="spatial-court-line" d="M52.5 210 A40 40 0 0 1 52.5 290"/><path class="spatial-court-line" d="M887.5 210 A40 40 0 0 0 887.5 290"/>
        <path class="spatial-court-line three-point" d="M2 30 H142 A237.5 237.5 0 0 1 142 470 H2"/>
        <path class="spatial-court-line three-point" d="M938 30 H798 A237.5 237.5 0 0 0 798 470 H938"/>
      </g>
    </svg>
    <div class="spatial-legends">${["Projected FG", "Suppression"].map(label => `<div class="spatial-legend" title="${label} versus league average: below -8, -8 to -3, -3 to +3, +3 to +8, above +8 percentage points. Hex size: attempt/contest share relative to league mean cell density."><span>${label} −</span><i class="spatial-discrete-key">${[-10, -5, 0, 5, 10].map(delta => `<b style="background:${spatialEfficiencyColor(delta)}"></b>`).join("")}</i><span>+</span></div>`).join("")}</div>
  </div>`;
}

function seasonIdentityRadar(title, axes, rows, ranks, count) {
  const current = seasonRadarProfile(rows, axes, false);
  const healthy = seasonRadarProfile(rows, axes, true);
  const width = 250;
  const height = 174;
  const cx = 125;
  const cy = 86;
  const radius = 54;
  const point = (index, value, extra = 0) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / axes.length;
    const distance = radius * clampNumber(Number(value || 0) / 99, 0.08, 1) + extra;
    return [cx + Math.cos(angle) * distance, cy + Math.sin(angle) * distance];
  };
  const polygon = (values) => values.map((value, index) => point(index, value).map((part) => part.toFixed(1)).join(",")).join(" ");
  const ring = (level) => axes.map((_axis, index) => point(index, 99 * level).map((part) => part.toFixed(1)).join(",")).join(" ");
  return `<div class="season-command-panel season-radar-card">
    ${seasonPanelHeader(title)}
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(title)}">
      ${[0.25, 0.5, 0.75, 1].map((level) => `<polygon class="season-radar-grid" points="${ring(level)}"></polygon>`).join("")}
      ${axes.map((_axis, index) => { const [x, y] = point(index, 99); return `<line class="season-radar-axis" x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"></line>`; }).join("")}
      <polygon class="season-radar-healthy" points="${polygon(healthy)}"></polygon>
      <polygon class="season-radar-current" points="${polygon(current)}"></polygon>
      ${axes.map(([label, _ratingKey, rankKey], index) => {
        const [px, y] = point(index, 99, 17);
        const x = Math.abs(px - cx) < 5 ? cx : px < cx ? 40 : width - 40;
        const rank = Number(ranks[rankKey] || count);
        return `<text x="${x.toFixed(1)}" y="${(y - 4).toFixed(1)}" text-anchor="middle"><tspan x="${x.toFixed(1)}">${escapeHtml(label)}</tspan><tspan x="${x.toFixed(1)}" dy="10">#${rank}/${count}</tspan></text>`;
      }).join("")}
    </svg>
    <div class="season-radar-legend"><span class="current">Current rotation</span><span class="healthy">Full-health auto</span></div>
  </div>`;
}

function seasonRadarProfile(rows, axes, includeInjured) {
  const eligible = rows.filter((row) => row?.id && (includeInjured || !isPlayerInjured(row.health)));
  return axes.map(([_label, key]) => {
    let total = 0;
    let weightTotal = 0;
    for (const row of eligible) {
      let value = Number(rating(row, key));
      if (!Number.isFinite(value) && key === "range") value = Number(rating(row, "spacing"));
      if (!Number.isFinite(value) && ["defensive_effort", "scheme_iq", "screen_navigation"].includes(key)) value = Number(rating(row, "defense"));
      if (!Number.isFinite(value)) continue;
      const planned = Number(row.rotation_target_minutes ?? row.coach_minutes_projection ?? row.minutes_projection ?? mpgFromRow(row) ?? 0);
      const talentFloor = clampNumber((Number(rating(row, "overall") || 45) - 35) * 0.6, 4, 28);
      const weight = Math.max(planned, includeInjured ? talentFloor : 1);
      total += value * weight;
      weightTotal += weight;
    }
    return weightTotal ? clampNumber(total / weightTotal, 8, 99) : 50;
  });
}

function seasonStandingsCard(viewedTeam) {
  const standings = standingsRows(state.data.dashboardStandings);
  const viewedRow = standings.find((row) => teamLabel(row.team) === viewedTeam);
  const conference = viewedRow?.team?.conference || "East";
  const rows = standings.filter((row) => row.team?.conference === conference).slice(0, 10);
  const leader = rows[0] || {};
  return `${seasonPanelHeader("Standings")}
    <div class="season-standings-table">
      <div class="season-standings-head"><span>#</span><span>Team</span><span>W-L</span><span>Win%</span><span>GB</span></div>
      ${rows.map((row, index) => {
        const team = teamLabel(row.team);
        const logo = teamLogoSrc(team);
        const gamesBack = ((Number(leader.wins || 0) - Number(row.wins || 0)) + (Number(row.losses || 0) - Number(leader.losses || 0))) / 2;
        const gamesBackLabel = gamesBack <= 0 ? "—" : Number.isInteger(gamesBack) ? String(gamesBack) : gamesBack.toFixed(1).replace(/^0/, "");
        return `<button type="button" class="season-standing-row${team === viewedTeam ? " active" : ""}${index === 5 ? " playoff-line" : ""}" data-dashboard-team-jump="${escapeAttr(team)}">
          <span>${index + 1}</span><span>${logo ? `<img src="${escapeAttr(logo)}" alt="" />` : ""}${escapeHtml(team)}</span><span>${Number(row.wins || 0)}-${Number(row.losses || 0)}</span><span>${escapeHtml(winPct(row.win_pct))}</span><span>${escapeHtml(gamesBackLabel)}</span>
        </button>`;
      }).join("") || `<div class="empty">No standings yet.</div>`}
    </div>`;
}

function seasonWeekCard(dash, viewedTeam, editable) {
  const currentText = String(state.home?.save?.current_date || "").slice(0, 10);
  const current = new Date(`${currentText || "2026-10-01"}T00:00:00Z`);
  const monday = new Date(current);
  monday.setUTCDate(current.getUTCDate() - ((current.getUTCDay() + 6) % 7));
  const calendarGames = (state.data.dashboardCalendar?.games || []).filter((game) => {
    const home = teamLabel(game.home_team || game.home);
    const away = teamLabel(game.away_team || game.away);
    return home === viewedTeam || away === viewedTeam;
  });
  const games = [...(dash.last_games || []), ...(dash.next_games || []), ...calendarGames];
  const byDate = new Map();
  for (const game of games) {
    const date = String(game.date || "").slice(0, 10);
    if (!date) continue;
    const completed = Boolean(game.result || game.status === "simulated" || (game.points != null && game.opponent_points != null && Number.isFinite(Number(game.points)) && Number.isFinite(Number(game.opponent_points))) || (game.home_score != null && game.away_score != null));
    if (!byDate.has(date) || (completed && !byDate.get(date).__completed)) byDate.set(date, { ...game, __completed: completed });
  }
  const days = Array.from({ length: 7 }, (_unused, index) => {
    const date = new Date(monday);
    date.setUTCDate(monday.getUTCDate() + index);
    const iso = date.toISOString().slice(0, 10);
    const game = byDate.get(iso);
    const opponent = game ? seasonGameOpponent(game, viewedTeam) : "";
    const logo = opponent ? teamLogoSrc(opponent) : "";
    const score = game ? seasonGameScore(game, viewedTeam) : "";
    return `<div class="season-week-day${iso === currentText ? " today" : ""}">
      <span>${date.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })} ${date.getUTCDate()}</span>
      ${game?.__completed && (game.game_id || game.id) ? `<button type="button" class="season-week-node" data-box-score="${escapeAttr(game.game_id || game.id)}" aria-label="Box score: ${escapeAttr(opponent)} ${escapeAttr(iso)}"><img src="${escapeAttr(logo)}" alt="${escapeAttr(opponent)}" /></button>` : `<div class="season-week-node">${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(opponent)}" />` : "<i></i>"}</div>`}
      ${score ? `<em>${escapeHtml(score)}</em>` : `<em aria-hidden="true"></em>`}
      ${iso === currentText ? `<small>Today</small>` : `<small aria-hidden="true"></small>`}
    </div>`;
  }).join("");
  return `<div class="season-week-days" aria-label="This week">${days}</div>
    <div class="season-sim-actions">
      <button type="button" data-dashboard-view="calendar">Full calendar</button>
      <button type="button" data-advance="next-event" ${editable ? "" : "disabled"}>Next Event</button>
      <button type="button" data-advance="week" ${editable ? "" : "disabled"}>Sim Week</button>
      <button type="button" data-advance="month" ${editable ? "" : "disabled"}>Sim Month</button>
    </div>`;
}

function seasonGameOpponent(game, team) {
  if (game.opponent_team_id) return teamLabel(game.opponent_team_id);
  const home = teamLabel(game.home || game.home_team);
  const away = teamLabel(game.away || game.away_team);
  return home === team ? away : home;
}

function seasonGameScore(game, team) {
  const result = String(game.result || resultForTeam(game, team) || "").toUpperCase();
  const teamPoints = Number(game.points ?? game.team_points);
  const opponentPoints = Number(game.opponent_points);
  if (Number.isFinite(teamPoints) && Number.isFinite(opponentPoints)) return `${result || (teamPoints > opponentPoints ? "W" : "L")} ${teamPoints}–${opponentPoints}`;
  const home = teamLabel(game.home || game.home_team);
  const homeScore = Number(game.home_score ?? game.home_points);
  const awayScore = Number(game.away_score ?? game.away_points);
  if (!Number.isFinite(homeScore) || !Number.isFinite(awayScore)) return "";
  const own = home === team ? homeScore : awayScore;
  const other = home === team ? awayScore : homeScore;
  return `${result || (own > other ? "W" : "L")} ${own}–${other}`;
}

function dashboardProspectYear() {
  const save = state.home?.save || {};
  const season = String(save.active_season || save.season || "");
  const match = season.match(/^(\d{4})-(\d{2,4})$/);
  if (match) return String(Number(match[1]) + 1);
  const year = Number(String(save.current_date || "").slice(0, 4));
  const month = Number(String(save.current_date || "").slice(5, 7));
  return String((Number.isFinite(year) ? year : 2026) + (month >= 7 ? 1 : 0));
}

function seasonOpponentCard(dash, viewedTeam) {
  const game = (dash.next_games || [])[0] || {};
  const opponent = state.data.dashboardOpponent || {};
  const opponentTeam = teamLabel(opponent.team || game.opponent_team_id || seasonGameOpponent(game, viewedTeam));
  const record = opponent.record || {};
  const games = Number(record.wins || 0) + Number(record.losses || 0);
  const lastTen = (opponent.last_games || []).slice(0, 10);
  const lastTenWins = lastTen.filter((item) => String(item.result || "").toUpperCase() === "W").length;
  const identity = opponent.team_identity || {};
  const rankings = identity.ranks || {};
  const leaders = [...(opponent.rotation || [])]
    .sort((left, right) => Number(right.minutes_projection || 0) - Number(left.minutes_projection || 0))
    .slice(0, 6);
  const logo = teamLogoSrc(opponentTeam);
  const homeAway = game.is_home === true ? "Home" : game.is_home === false ? "Away" : "";
  const injuries = (opponent.rotation || [])
    .filter((row) => isPlayerInjured(row.health))
    .map((row) => `${row.name} — ${row.health?.label || row.health?.status || "out"}`);
  const headerRatings = [
    ["OVR", rankings.overall], ["OFF", rankings.offense], ["DEF", rankings.defense],
  ];
  return `<header class="season-panel-header season-opponent-header">
      <div class="season-opponent-title"><h2>Next Opponent</h2>${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(opponentTeam)} logo" />` : ""}<span>${escapeHtml(opponentTeam || "—")}</span><span>${Number(record.wins || 0)}-${Number(record.losses || 0)}</span><span>L10 ${lastTenWins}-${Math.max(0, lastTen.length - lastTenWins)}</span>${headerRatings.map(([label, rank]) => {
        const score = clampNumber(((30 - Number(rank || 30) + 1) / 30) * 100, 3, 100);
        return `<span class="season-opponent-header-rating"><i><b style="${performanceBarStyle(score)}"></b></i>#${Number(rank || 30)} ${label}</span>`;
      }).join("")}</div>
      <span class="season-opponent-date">${escapeHtml(formatDashboardShortDate(game.date) || game.date || "")}${homeAway ? ` · ${homeAway}` : ""}</span>
    </header>
    <div class="season-opponent-table">
      <div class="season-opponent-head"><span>Player</span><span>OVR</span><span>OFF</span><span>DEF</span><span>PTS</span><span>REB</span><span>AST</span></div>
      ${leaders.map((row, index) => `<div class="season-opponent-row${isPlayerInjured(row.health) ? " injured" : ""}"><span>${index + 1}. ${escapeHtml(row.name)}</span>${seasonMiniRating(rating(row, "overall"))}${seasonMiniRating(rating(row, "offense"))}${seasonMiniRating(rating(row, "defense"))}${["points", "rebounds", "assists"].map((key) => `<span>${escapeHtml(statNumber(row, key))}</span>`).join("")}</div>`).join("") || `<div class="empty">Opponent rotation unavailable.</div>`}
    </div>
    <div class="season-opponent-injuries"><span>Current injuries:</span><div>${escapeHtml(injuries.join(" · ") || "No active injuries")}</div></div>`;
}

function seasonPreviousGamesCard(dash, viewedTeam) {
  const games = (dash.last_games || []).slice(0, 5);
  return `${seasonPanelHeader("Previous 5")}
    <div class="season-previous-games">
      ${games.map((game) => {
        const opponent = seasonGameOpponent(game, viewedTeam);
        const logo = teamLogoSrc(opponent);
        const score = seasonGameScore(game, viewedTeam);
        const gameId = game.game_id || game.id;
        const result = String(game.result || resultForTeam(game, viewedTeam) || "").toUpperCase();
        return `<button type="button" class="season-previous-game" ${gameId ? `data-box-score="${escapeAttr(gameId)}"` : "disabled"}>
          <span>${logo ? `<img src="${escapeAttr(logo)}" alt="" />` : ""}${escapeHtml(opponent || "—")}</span>
          <strong class="${result === "W" ? "positive" : result === "L" ? "negative" : ""}">${escapeHtml(score || "—")}</strong>
          <time>${escapeHtml(formatDashboardShortDate(game.date))}</time>
        </button>`;
      }).join("") || `<div class="empty">No completed games.</div>`}
    </div>`;
}

function seasonEfficiencyCard(dash, chartWidth = 420, chartHeight = 220, chartOnly = false) {
  const points = state.data.dashboardTrends?.efficiency?.points || [];
  const fallback = [...(dash.last_games || [])].reverse().map((game, index) => ({
    label: `W${index + 1}`,
    offense: Number(game.points || 0),
    defense: Number(game.opponent_points || 0),
  }));
  const source = points.length ? points : fallback;
  const offense = source.map((point) => Number(point.offense || 100));
  const defense = source.map((point) => Number(point.defense || 100));
  const leagueAverage = Number(state.data.dashboardTrends?.efficiency?.league_average || 112);
  const offenseDiff = offense.map((value) => value - leagueAverage);
  const defenseDiff = defense.map((value) => leagueAverage - value);
  const net = offense.map((value, index) => value - Number(defense[index] || value));
  const maximum = Math.max(40, Math.ceil(Math.max(0, ...[...offenseDiff, ...defenseDiff, ...net].map((value) => Math.abs(value))) / 10) * 10);
  const left = 28, right = chartWidth - 7, top = 7, bottom = chartHeight - 28;
  const plotWidth = right - left, plotHeight = bottom - top;
  const zeroY = top + plotHeight / 2;
  const seasonSlots = Math.max(26, source.length);
  const xFor = (index) => left + index / (seasonSlots - 1) * plotWidth;
  const yFor = (value) => clampNumber(zeroY - value / maximum * plotHeight / 2, top, bottom);
  const chartPoints = (series) => series.map((value, index) => {
    return `${xFor(index).toFixed(1)},${yFor(value).toFixed(1)}`;
  }).join(" ");
  const areaPath = (series) => {
    if (!series.length) return "";
    const line = series.map((value, index) => {
      return `${index ? "L" : "M"}${xFor(index).toFixed(1)} ${yFor(value).toFixed(1)}`;
    }).join(" ");
    return `${line} L${xFor(series.length - 1).toFixed(1)} ${zeroY.toFixed(1)} L${left} ${zeroY.toFixed(1)} Z`;
  };
  const latestOffense = offense.at(-1) || 0;
  const latestDefense = defense.at(-1) || 0;
  const latestNet = net.at(-1) || 0;
  const tone = (value) => value > 0.05 ? "positive" : value < -0.05 ? "negative" : "neutral";
  const netTone = tone(latestNet);
  const gridRows = Math.max(2, 2 * Math.round(plotHeight / (plotWidth / (seasonSlots - 1) / 2) / 2));
  const labelStep = Math.max(1, Math.ceil(12 / (plotHeight / gridRows)));
  const chart = `
    <svg class="season-efficiency-chart" viewBox="0 0 ${chartWidth} ${chartHeight}" preserveAspectRatio="none" aria-label="Weekly offensive and defensive rating">
      ${Array.from({length: seasonSlots}, (_unused, index) => `<line class="grid vertical" x1="${xFor(index)}" y1="${top}" x2="${xFor(index)}" y2="${bottom}"></line><line class="axis-notch" x1="${xFor(index)}" y1="${bottom}" x2="${xFor(index)}" y2="${bottom + 3}"></line>${source[index] ? `<text class="axis-label x-label" transform="translate(${xFor(index)},${bottom + 8}) rotate(-60)">${escapeHtml(source[index].label || `W${index + 1}`)}</text>` : ""}`).join("")}
      ${Array.from({length: gridRows + 1}, (_unused, index) => { const y = top + index / gridRows * plotHeight; const value = maximum - index / gridRows * maximum * 2; const labeled = index === 0 || index === gridRows || (index >= labelStep && index <= gridRows - labelStep && (index - gridRows / 2) % labelStep === 0); return `<line class="grid horizontal" x1="${left}" y1="${y}" x2="${right}" y2="${y}"></line>${labeled ? `<line class="axis-notch" x1="${left - 3}" y1="${y}" x2="${left}" y2="${y}"></line><text class="axis-label" x="${left - 5}" y="${y}">${value.toFixed(0)}</text>` : ""}`; }).join("")}
      <line class="zero" x1="${left}" y1="${zeroY}" x2="${right}" y2="${zeroY}"></line>
      <path class="net-area ${netTone}" d="${areaPath(net)}"></path>
      <polyline class="offense secondary ${tone(offenseDiff.at(-1) || 0)}" points="${chartPoints(offenseDiff)}"></polyline>
      <polyline class="defense secondary ${tone(defenseDiff.at(-1) || 0)}" points="${chartPoints(defenseDiff)}"></polyline>
      <polyline class="net ${netTone}" points="${chartPoints(net)}"></polyline>
      ${[offenseDiff, defenseDiff, net].map((series, seriesIndex) => series.map((value, index) => `<circle class="chart-node ${tone(series.at(-1) || 0)}" cx="${xFor(index)}" cy="${yFor(value)}" r="1.8"><title>${escapeHtml(source[index]?.label || `W${index + 1}`)} ${["OFF vs league", "DEF vs league", "NET"][seriesIndex]}: ${signedNumber(value)}</title></circle>`).join("")).join("")}
      <text class="axis-caption" x="${left}" y="${chartHeight - 2}">Week</text><text class="axis-caption" x="${right}" y="${chartHeight - 2}" text-anchor="end">Rating +/- league</text>
    </svg>`;
  return chartOnly ? chart : `${seasonPanelHeader("Weekly Efficiency", `<div class="season-efficiency-summary"><span class="${tone(offenseDiff.at(-1) || 0)}">OFF ${latestOffense.toFixed(1)}</span><span class="${tone(defenseDiff.at(-1) || 0)}">DEF ${latestDefense.toFixed(1)}</span><span class="${netTone}">NET ${latestNet.toFixed(1)}</span></div>`)}<div class="season-efficiency-plot">${chart}</div>`;
}

let seasonEfficiencyResizeObserver;
function wireSeasonEfficiencyChart() {
  seasonEfficiencyResizeObserver?.disconnect();
  const plot = els.content.querySelector(".season-efficiency-plot");
  if (!plot) return;
  const redraw = () => { if (plot.clientWidth > 40 && plot.clientHeight > 40) plot.innerHTML = seasonEfficiencyCard(state.data.dashboard || {}, plot.clientWidth, plot.clientHeight, true); };
  seasonEfficiencyResizeObserver = new ResizeObserver(redraw);
  seasonEfficiencyResizeObserver.observe(plot);
  redraw();
}

function seasonProspectsCard() {
  const sort = state.dashboardProspectSort;
  const value = (row) => ({rank:Number(row.rank), name:row.name, position:row.position, now:Number(row.now), range:Number(row.ceiling) - Number(row.floor), stock:Number(row.rankChange || 0), scouted:Number(row.scoutedPct ?? Number(row.confidence || 0) * 100)})[sort.key];
  const rows = draftBoardRows(state.data.dashboardProspects || {}).sort((a, b) => {
    const av = value(a), bv = value(b);
    return (typeof av === "string" ? av.localeCompare(String(bv)) : av - bv) * (sort.direction === "asc" ? 1 : -1) || Number(a.rank) - Number(b.rank);
  }).slice(0, 6);
  return `${seasonPanelHeader("Upcoming Prospects", `<button type="button" data-dashboard-view="draft">Open board</button>`, "prospects")}
    <div class="season-prospects-table">
      <div class="season-prospects-head">${[["rank", "#"], ["name", "Prospect"], ["position", "Pos"], ["now", "Now/Pot"], ["range", "Range"], ["stock", "Stock"], ["scouted", "Scouted"]].map(([key, label]) => `<button type="button" data-season-prospect-sort="${key}" title="Sort by ${label}" aria-label="Sort by ${label}${sort.key === key ? `, ${sort.direction === "asc" ? "ascending" : "descending"}` : ""}">${label}${sort.key === key ? (sort.direction === "asc" ? " ↑" : " ↓") : ""}</button>`).join("")}</div>
      ${rows.map((row) => {
        const confidence = clampNumber(Number(row.scoutedPct ?? Number(row.confidence || 0) * 100), 0, 100);
        return `<button type="button" class="season-prospect-row" data-draft-prospect-card="${escapeAttr(row.id)}"><span>${escapeHtml(row.rank)}</span><span>${escapeHtml(row.name)}</span><span>${escapeHtml(row.position)}</span><span>${Number(row.now || 0).toFixed(0)}/${Number(row.potential || 0).toFixed(0)}</span><span>${escapeHtml(row.floor && row.ceiling ? `${Number(row.floor).toFixed(0)}–${Number(row.ceiling).toFixed(0)}` : "—")}</span>${seasonRankChange(row.rankChange, row.seasonStartRank)}<span class="season-scouted"><i><b style="${performanceBarStyle(confidence)}"></b></i><strong>${confidence.toFixed(0)}%</strong></span></button>`;
      }).join("") || `<div class="empty">Prospect board unavailable.</div>`}
    </div>`;
}

function regularSeasonProgressSlot(totalSlots = 26) {
  const currentText = String(state.home?.save?.current_date || "").slice(0, 10);
  const current = new Date(`${currentText || "2026-10-01"}T00:00:00Z`);
  if (Number.isNaN(current.getTime())) return 0;
  const year = current.getUTCFullYear();
  const month = current.getUTCMonth() + 1;
  const startYear = month >= 7 ? year : year - 1;
  const start = new Date(`${startYear}-10-01T00:00:00Z`);
  const elapsedWeeks = Math.floor(Math.max(0, current.getTime() - start.getTime()) / (7 * 24 * 60 * 60 * 1000));
  return clampNumber(elapsedWeeks, 0, Math.max(0, totalSlots - 1));
}

function seasonAwardsCard(editable) {
  const fields = Object.fromEntries((state.data.dashboardSummaryLeaders?.fields || []).map((field) => [field.key, field.leaders || []]));
  const races = [
    ["MVP", state.data.dashboardSummaryLeaders?.award_races?.MVP || (fields.points?.length ? fields.points : fields.overall || [])],
    ["DPOY", state.data.dashboardSummaryLeaders?.award_races?.DPOY || (fields.defense?.length ? fields.defense : fields.rim_deterrence || [])],
    ["ROTY", state.data.dashboardSummaryLeaders?.award_races?.ROTY || state.data.dashboardSummaryLeaders?.rookies || []],
  ];
  return `<div class="season-awards-grid">${races.map(([label, leaders]) => `<section class="season-command-panel season-award-card">
      <header class="season-award-head"><h3>${label}</h3><div class="season-award-actions"><button type="button" data-dashboard-player-finder ${editable ? "" : "disabled"}>Player Finder</button><button type="button" data-award-view-all>View all</button></div></header>
      <div class="season-award-rows">${leaders.slice(0, 4).map((row, index) => {
      const team = row.team_abbrev || teamLabel(row.team_id);
      const logo = teamLogoSrc(team);
      return `<button type="button" data-dashboard-player-card="${escapeAttr(row.player_id)}"><span>${row.rank || index + 1}</span>${logo ? `<img src="${escapeAttr(logo)}" alt="" />` : ""}<strong>${escapeHtml(row.player_name)}</strong>${seasonRankChange(row.rank_change, row.season_start_rank)}</button>`;
      }).join("") || `<div class="empty">No candidates yet.</div>`}</div>
    </section>`).join("")}</div>`;
}

function seasonRankChange(change, baselineRank) {
  if (change == null || !Number.isFinite(Number(change))) return `<span class="season-rank-change neutral" title="Season-start rank unavailable">—</span>`;
  const delta = Number(change);
  const label = delta > 0 ? `Up ${delta}` : delta < 0 ? `Down ${Math.abs(delta)}` : "Unchanged";
  return `<span class="season-rank-change ${delta > 0 ? "positive" : delta < 0 ? "negative" : "neutral"}" title="${label} from season-start rank ${baselineRank}" aria-label="${label} places since season start">${delta > 0 ? "↑" : delta < 0 ? "↓" : ""} ${Math.abs(delta)}</span>`;
}

function seasonStaffCard(dash, editable) {
  const roles = ["HC", "OC", "DC", "PERF", "DEV", "SCOUT"];
  const rows = [...staffRows(dash)].sort((a, b) => {
    const order = (row) => { const index = roles.indexOf(compactStaffRole(row.slot || row.role)); return index < 0 ? roles.length : index; };
    return order(a) - order(b);
  });
  return `${seasonPanelHeader("Coaching Staff", `<button type="button" data-dashboard-view="staff" ${editable ? "" : "disabled"}>Manage</button>`, "staff")}
    <div class="season-staff-table">
      <div class="season-staff-head"><span>Name</span><span>Role</span><span>Grade</span><span>Contract</span></div>
      ${rows.map((row) => {
        const grade = Number(staffGrade(row) || 0);
        return `<div class="season-staff-row"><span>${escapeHtml(staffName(row))}</span><span title="${escapeAttr(rowLabel(row.slot || row.role || "Staff"))}">${escapeHtml(compactStaffRole(row.slot || row.role))}</span><span class="season-staff-grade"><em>${grade.toFixed(0)}</em><i><b style="${performanceBarStyle(grade)}"></b></i></span><span>${staffAav(row) ? `${money(staffAav(row))}×${escapeHtml(staffYears(row) || 1)}` : "—"}</span></div>`;
      }).join("") || `<div class="empty">No staff loaded.</div>`}
    </div>`;
}

function compactStaffRole(role) {
  return ({
    head_coach: "HC",
    offensive_coordinator: "OC",
    defensive_coordinator: "DC",
    development_lead: "DEV",
    performance_lead: "PERF",
    scouting_lead: "SCOUT",
  })[String(role || "").toLowerCase()] || "STAFF";
}

function seasonMinutesCard(rows, editable) {
  const assigned = (row) => Number(state.rotationDraft[row.id] ?? row.minutes_projection ?? row.rotation_target_minutes ?? 0);
  const sortedRows = [...rows].sort((left, right) => assigned(right) - assigned(left));
  const development = new Map(developmentPlayerCandidates(rows).map((item) => [String(item.player_id), item]));
  return `${seasonPanelHeader("Minutes + Availability", "", "availability")}
    <div class="season-minutes-table" style="--roster-count:${Math.max(1, rows.length)}">
      <div class="season-minutes-head"><span>Player</span><span>Age</span><span>Pos</span><span>Height</span><span>OVR</span><span>OFF</span><span>DEF</span><span>MPG</span><span>PTS</span><span>REB</span><span>AST</span><span>Minutes</span><span>Fatigue</span><span>Development</span></div>
      ${sortedRows.map((row) => {
        const injured = isPlayerInjured(row.health);
        const games = injuryGamesRemaining(row);
        const status = injured ? `${compactPos(row.position)} · out${games !== null ? ` — ${games} gms` : ""}` : compactPos(row.position);
        const trend = development.get(String(row.id));
        const values = (trend?.points || []).map((point) => Number(point.value)).filter(Number.isFinite);
        const delta = values.length > 1 ? values.at(-1) - values[0] : 0;
        const minuteValue = clampNumber(Number(state.rotationDraft[row.id] ?? row.minutes_projection ?? row.rotation_target_minutes ?? 0), 0, 48);
        return `<div class="season-minute-row${injured ? " injured" : ""}">
          <button type="button" data-dashboard-player-card="${escapeAttr(row.id)}">${escapeHtml(row.name || "Unknown")}</button>
          <span>${Number.isFinite(Number(row.age)) ? Math.floor(Number(row.age)) : "—"}</span>
          <span>${escapeHtml(status || "—")}</span>
          <span>${escapeHtml(heightFromRow(row) || "—")}</span>
          ${seasonMiniRating(rating(row, "overall"))}${seasonMiniRating(rating(row, "offense"))}${seasonMiniRating(rating(row, "defense"))}
          <span>${Number(mpgFromRow(row) || 0).toFixed(1)}</span><span>${statNumber(row, "points")}</span><span>${statNumber(row, "rebounds")}</span><span>${statNumber(row, "assists")}</span>
          <div class="season-minute-control"><label class="season-minute-slider${state.rotationLockedPlayerIds.has(row.id) || row.rotation_user_set ? " user-locked" : ""}"><i><b class="season-minute-fill" style="width:${(minuteValue / 48 * 100).toFixed(2)}%"></b></i><input type="range" min="0" max="48" step="1" value="${minuteValue}" data-minute-player="${escapeAttr(row.id)}" aria-label="Minutes for ${escapeAttr(row.name || "player")}" ${editable ? "" : "disabled"} /></label><output data-minute-output="${escapeAttr(row.id)}">${minuteValue}</output></div>
          ${seasonFatigueCell(row)}
          <span class="season-minute-development"><strong class="${delta > 0 ? "positive" : delta < 0 ? "negative" : ""}">${signedNumber(delta)}</strong><i class="season-development-diverging" role="img" aria-label="Development ${signedNumber(delta)} rating points, scale minus 5 to plus 5" title="${signedNumber(delta)} rating points"><b class="${delta < 0 ? "negative" : "positive"}" style="left:${delta < 0 ? 50 - Math.min(50, Math.abs(delta) * 10) : 50}%;width:${Math.min(50, Math.abs(delta) * 10)}%"></b></i></span>
        </div>`;
      }).join("") || `<div class="empty">No roster loaded.</div>`}
    </div>`;
}

function seasonMiniRating(value) {
  const score = clampNumber(Number(value || 0), 0, 99);
  return `<span class="season-mini-rating"><em>${score.toFixed(0)}</em><i><b style="${performanceBarStyle(score)}"></b></i></span>`;
}

function seasonFatigueCell(row) {
  const risk = clampNumber(Number(row.health_risk || 0), 0, 12);
  const workload = clampNumber(Number(state.rotationDraft[row.id] ?? row.minutes_projection ?? mpgFromRow(row) ?? 0), 0, 48);
  const level = clampNumber(Math.round((risk / 12) * 4 + (workload / 48) * 2), 0, 6);
  const tone = level <= 2 ? "low" : level <= 4 ? "medium" : "high";
  return `<span class="season-fatigue ${tone}" title="Workload and health-risk signal">${Array.from({ length: 6 }, (_unused, index) => `<i class="${index < level ? "filled" : ""}"></i>`).join("")}</span>`;
}

function seasonDevelopmentCard(rows) {
  const rosterIds = new Set(rows.map((row) => String(row.id || "")));
  const candidates = developmentPlayerCandidates(rows)
    .filter((candidate) => rosterIds.has(String(candidate.player_id)))
    .sort((left, right) => developmentMovementScore(right) - developmentMovementScore(left))
    .slice(0, 9);
  return `${seasonPanelHeader("Player Development", `<button type="button" data-team-development>Team growth</button>`)}
    <div class="season-development-list">
      ${candidates.map((player) => {
        const values = (player.points || []).map((point) => Number(point.value)).filter(Number.isFinite);
        const delta = values.length > 1 ? values[values.length - 1] - values[0] : 0;
        const width = clampNumber((Math.abs(delta) / 5) * 50, 0, 50);
        return `<button type="button" class="season-development-row" data-dashboard-player-card="${escapeAttr(player.player_id)}">
          <span>${escapeHtml(player.name)}</span>
          ${seasonDevelopmentSparkline(player.points || [])}
          <i class="season-development-diverge"><b class="${delta < 0 ? "negative" : "positive"}" style="width:${width}%;${delta < 0 ? "right:50%" : "left:50%"}"></b></i>
          <strong class="${delta > 0 ? "positive" : delta < 0 ? "negative" : ""}">${signedNumber(delta)}</strong>
        </button>`;
      }).join("") || `<div class="empty">Development history will appear after the first monthly update.</div>`}
    </div>`;
}

function seasonDevelopmentSparkline(points) {
  const source = points
    .map((point, index) => ({ value: Number(point.value), slot: Number(point.season_slot ?? index) }))
    .filter((point) => Number.isFinite(point.value) && Number.isFinite(point.slot));
  const plotted = source.length ? source : [{ value: 0, slot: 0 }];
  const base = plotted[0].value;
  const width = 76;
  const height = 20;
  const seasonSlots = developmentSeasonMonths().length;
  const coords = plotted.map((point) => {
    const x = (clampNumber(point.slot, 0, seasonSlots) / seasonSlots) * width;
    const y = height / 2 - clampNumber(point.value - base, -5, 5) * (height / 10);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const delta = plotted.at(-1).value - plotted[0].value;
  const tone = delta > 0.01 ? "positive" : delta < -0.01 ? "negative" : "neutral";
  return `<svg class="season-development-spark ${tone}" viewBox="0 0 ${width} ${height}" aria-hidden="true"><line class="season-horizon-guide" x1="0" y1="${height / 2}" x2="${width}" y2="${height / 2}"></line><polyline points="${coords}"></polyline></svg>`;
}

function openTeamDevelopmentModal() {
  const rows = rosterRows(state.data.dashboard || {});
  const rosterIds = new Set(rows.map((row) => String(row.id || "")));
  const lines = developmentPlayerCandidates(rows)
    .filter((candidate) => rosterIds.has(String(candidate.player_id)))
    .sort((left, right) => developmentMovementScore(right) - developmentMovementScore(left));
  const colors = developmentLineColors();
  const viewedTeam = teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam());
  state.modal = {
    kind: "teamDevelopment",
    title: `${viewedTeam} Player Development`,
    subtitle: "",
    body: `<div class="team-development-modal">
      <div class="team-development-chart">${developmentLineChart(lines, { empty: "Development history will appear after the first monthly update." })}</div>
      <div class="team-development-legend">${lines.map((line, index) => `<span><i style="background:${colors[index % colors.length]}"></i>${escapeHtml(line.name || "Player")}</span>`).join("")}</div>
    </div>`,
  };
  renderModal();
}

function seasonLeagueWire() {
  const events = state.home?.league_events?.events || [];
  const items = events.slice(0, 12).map((event) => {
    const normalized = normalizeLeagueEvent(event);
    const marks = normalized.teams.map((team) => {
      const logo = teamLogoSrc(team);
      return logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(team)}" />` : "";
    }).join("");
    return `<span class="season-wire-item">${marks}<em>${escapeHtml(normalized.date)}</em><strong>${escapeHtml(normalized.text)}</strong></span>`;
  }).join("");
  return `<footer class="season-league-wire"><span class="season-wire-label">League Wire</span><div class="season-wire-window"><div class="season-wire-track">${items || `<span class="season-wire-item"><strong>No recent league events.</strong></span>`}</div></div><button type="button" data-league-panel-view-all>View all</button></footer>`;
}

function unifiedDashboardWorkspace(rows, dash, editable, readonlyClass) {
  if (state.dashboardWorkspace === "season") {
    return `<main class="unified-dashboard-workspace unified-season-workspace">
      <section class="unified-primary-panel calendar-card">${dashboardMonthCalendar()}</section>
      <aside class="unified-context-stack">
        <section class="unified-context-panel standings-card">${userConferenceStandings()}</section>
        <section class="unified-context-panel development-trend-card">${developmentTrendCard(rows)}</section>
      </aside>
    </main>`;
  }
  if (state.dashboardWorkspace === "league") {
    return `<main class="unified-dashboard-workspace unified-league-workspace">
      <section class="unified-primary-panel events-card">${leagueEventRotator(true)}</section>
      <aside class="unified-context-stack">
        <section class="unified-context-panel free-agent-market-card${readonlyClass}">${dashboardFreeAgentMarketCard(editable, 12, true)}</section>
        <section class="unified-context-panel standings-card">${userConferenceStandings()}</section>
      </aside>
    </main>`;
  }
  if (state.dashboardWorkspace === "office") {
    return `<main class="unified-dashboard-workspace unified-office-workspace">
      <section class="unified-primary-panel unified-office-staff">${staffDashboardCard(rows, dash, editable)}</section>
      <aside class="unified-context-stack">
        <section class="unified-context-panel draft-picks-card">${draftPicksCard()}</section>
        <section class="unified-context-panel unified-office-actions">${unifiedOfficeActions(editable)}</section>
      </aside>
    </main>`;
  }
  return `<main class="unified-dashboard-workspace unified-roster-workspace">
    <section class="unified-primary-panel player-summary-card">${dashboardPlayerSummaryTable(rows)}</section>
    <aside class="unified-team-intelligence" data-unified-team-intelligence>
      ${unifiedTeamIntelligence(rows, dash, editable)}
    </aside>
  </main>`;
}

function unifiedTeamIntelligence(rows, dash, editable) {
  const tabs = [["profile", "Profile"], ["starting", "Starting 5"], ["staff", "Staff"]];
  const selected = tabs.some(([key]) => key === state.dashboardIntelPanel) ? state.dashboardIntelPanel : "profile";
  let body = unifiedTeamProfile(dash);
  if (selected === "starting") body = startingFiveBlock(rows, editable);
  if (selected === "staff") body = staffDashboardCard(rows, dash, editable);
  return `<div class="unified-intelligence-tabs">${tabs.map(([key, label]) => `<button type="button" data-unified-intel-panel="${key}" class="${selected === key ? "active" : ""}">${label}</button>`).join("")}</div>
    <div class="unified-intelligence-body">${body}</div>`;
}

function unifiedTeamProfile(dash) {
  const identity = dash.team_identity || {};
  const metrics = identity.metrics || {};
  const ranks = identity.ranks || {};
  const count = identity.league_team_count || identity.team_count || 30;
  const cap = state.data.dashboardAssets?.cap || state.data.dashboardAssets?.cap_summary || {};
  const primary = [["OVR", metrics.overall, ranks.overall], ["OFF", metrics.offense, ranks.offense], ["DEF", metrics.defense, ranks.defense], ["DEPTH", metrics.depth, ranks.depth]];
  return `<section class="unified-profile-panel">
    <div class="unified-profile-metrics">${primary.map(([label, value, rank]) => `<div><span>${label}</span><strong>${Number(value || 0).toFixed(1)}</strong><small>#${escapeHtml(rank || count)}/${escapeHtml(count)}</small></div>`).join("")}</div>
    ${teamIdentityRadarChart(metrics, ranks, count)}
    ${cap && Object.keys(cap).length ? tradeCapStrip(cap) : ""}
  </section>`;
}

function unifiedOfficeActions(editable) {
  const disabled = editable ? "" : "disabled";
  const offerCount = Number(state.data.dashboardOffers?.offers?.length || 0);
  return `<div class="unified-office-action-grid">
    <button type="button" data-dashboard-trade="builder" ${disabled}>Trade Builder</button>
    <button type="button" data-dashboard-trade="finder" ${disabled}>Trade Finder</button>
    <button type="button" data-dashboard-player-finder ${disabled}>Player Finder</button>
    <button type="button" data-dashboard-view="draft" ${disabled}>Prospects</button>
    <button type="button" data-dashboard-offers ${disabled}>Trade Offers${offerCount ? ` (${offerCount})` : ""}</button>
    <button type="button" data-dashboard-settings ${disabled}>Settings</button>
  </div>`;
}

function commandDashboardMarkup(rows, dash, editable, readonlyClass, phaseKind, viewedTeam) {
  return `
    <div class="dashboard-overview ${phaseKind ? `phase-dashboard phase-dashboard-${phaseKind}` : ""}" ${teamBrandStyle(viewedTeam)}>
      <aside class="dashboard-team-rail">
        <section class="section panel-rail identity-card">${teamIdentityRankBlock(dash)}</section>
        <section class="section panel-rail starting-card">${startingFiveBlock(rows, editable)}</section>
        <section class="section panel-rail staff-card">${staffDashboardCard(rows, dash, editable)}</section>
      </aside>
      <div class="dashboard-command-deck">
        <section class="section panel-rail player-summary-card">${dashboardPlayerSummaryTable(rows)}</section>
        ${phaseKind ? `<section class="section panel-rail phase-takeover-card">${dashboardPhaseWorkspace(phaseKind)}</section>` : `
          <div class="dashboard-intelligence-grid">
            <div class="dashboard-column schedule-column">
              <section class="section panel-rail calendar-card">${dashboardMonthCalendar()}</section>
              <section class="section panel-rail development-trend-card">${developmentTrendCard(rows)}</section>
            </div>
            <div class="dashboard-column trend-column">
              <section class="section panel-rail events-card">${leagueEventRotator()}</section>
            </div>
            <div class="dashboard-column competition-column">
              <section class="section panel-rail standings-card">${userConferenceStandings()}</section>
            </div>
            <div class="dashboard-column finance-column">
              <section class="section panel-rail draft-picks-card">${draftPicksCard()}</section>
            </div>
            <div class="dashboard-column market-column">
              <section class="section panel-rail free-agent-market-card${readonlyClass}">${dashboardFreeAgentMarketCard(editable)}</section>
            </div>
          </div>`}
      </div>
      ${dashboardActionsCard(editable, true)}
    </div>`;
}

function franchiseJourneyMarkup(rows, dash, editable, readonlyClass, phaseKind, viewedTeam) {
  const identity = dash.team_identity || {};
  const metrics = identity.metrics || {};
  const logo = teamLogoSrc(viewedTeam);
  const teamName = dashboardTeamName(viewedTeam);
  const record = dashboardTeamRecord(viewedTeam);
  const save = state.home?.save || {};
  const nextGame = journeyNextGame(viewedTeam);
  const latestEvent = normalizeLeagueEvent((state.home?.league_events?.events || [])[0] || {});
  const franchisePlayer = [...rows].filter((row) => !row.__summaryEmpty).sort((a, b) => Number(rating(b, "overall") || 0) - Number(rating(a, "overall") || 0))[0];
  const chapters = phaseKind
    ? [["today", "Now"], ["moment", rowLabel(phaseKind)], ["roster", "Roster"], ["office", "Office"], ["league", "League"]]
    : [["today", "Now"], ["roster", "Roster"], ["season", "Season"], ["office", "Office"], ["league", "League"]];
  return `
    <div class="franchise-journey" ${teamBrandStyle(viewedTeam)}>
      <header class="journey-topbar">
        <button class="journey-club" data-journey-jump="today" aria-label="Return to today">
          ${logo ? `<img src="${escapeAttr(logo)}" alt="" />` : ""}
          <span><strong>${escapeHtml(viewedTeam)}</strong><small>${escapeHtml(String(save.season || "Franchise"))}</small></span>
        </button>
        <div class="journey-date"><span>${escapeHtml(formatWrittenDate(save.current_date) || save.current_date || "")}</span><strong>${escapeHtml(rowLabel(save.phase || "season"))}</strong></div>
        <div class="journey-view-switch" aria-label="Dashboard experience">
          <button class="active" data-dashboard-experience="journey">Journey</button>
          <button data-dashboard-experience="command">Command View</button>
        </div>
      </header>

      <nav class="journey-rail" aria-label="Franchise journey chapters">
        ${chapters.map(([key, label], index) => `<button class="${index === 0 ? "active" : ""}" data-journey-jump="${escapeAttr(key)}"><span>${String(index + 1).padStart(2, "0")}</span><em>${escapeHtml(label)}</em></button>`).join("")}
      </nav>

      <main class="journey-scroll" data-journey-scroll>
        <section class="journey-chapter journey-today" data-journey-chapter="today">
          <div class="journey-court-lines" aria-hidden="true"></div>
          <div class="journey-hero-copy">
            <p class="journey-kicker">Your franchise / ${escapeHtml(String(save.season || "current season"))}</p>
            <h1>${escapeHtml(teamName)}</h1>
            <div class="journey-record"><strong>${escapeHtml(record.split(" · ")[0] || record)}</strong><span>${escapeHtml(record.split(" · ")[1] || rowLabel(save.phase || "season"))}</span></div>
            <div class="journey-hero-actions">
              <button class="journey-primary-action" data-advance="next-event"><span>Advance</span><strong>Next Event</strong></button>
              <button data-dashboard-trade="finder"><span>Explore</span><strong>Trade Market</strong></button>
            </div>
          </div>
          <div class="journey-logo-stage" data-journey-logo-stage>
            <span class="journey-logo-index">${escapeHtml(viewedTeam)}</span>
            ${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(`${teamName} logo`)}" />` : `<strong>${escapeHtml(viewedTeam)}</strong>`}
          </div>
          <div class="journey-scoreboard">
            <div><small>OVR</small><strong>${Number(metrics.overall || 0).toFixed(1)}</strong></div>
            <div><small>OFF</small><strong>${Number(metrics.offense || 0).toFixed(1)}</strong></div>
            <div><small>DEF</small><strong>${Number(metrics.defense || 0).toFixed(1)}</strong></div>
            <div><small>DEPTH</small><strong>${Number(metrics.depth || 0).toFixed(1)}</strong></div>
          </div>
          <article class="journey-next-card">
            <p>${nextGame ? "Next on the schedule" : "Franchise focus"}</p>
            <strong>${escapeHtml(nextGame?.title || franchisePlayer?.name || "Build the next contender")}</strong>
            <span>${escapeHtml(nextGame?.detail || (franchisePlayer ? `${compactPos(franchisePlayer.position)} · ${Number(rating(franchisePlayer, "overall") || 0).toFixed(1)} OVR` : rowLabel(save.phase || "season")))}</span>
          </article>
          <article class="journey-wire-tease">
            <span>League wire</span>
            <p>${escapeHtml(latestEvent.text || "The league is quiet. For now.")}</p>
          </article>
          <button class="journey-scroll-cue" data-journey-jump="${escapeAttr(chapters[1][0])}"><span>Scroll to enter the season</span><i>↓</i></button>
        </section>

        ${phaseKind ? `
          <section class="journey-chapter journey-moment" data-journey-chapter="moment">
            <section class="section panel-rail phase-takeover-card">${dashboardPhaseWorkspace(phaseKind)}</section>
          </section>` : ""}

        <section class="journey-chapter journey-roster" data-journey-chapter="roster">
          ${journeyChapterIntro("The Roster", "Know every piece", "Ratings, roles, health, minutes, and contracts in one deliberate basketball workspace.")}
          <div class="journey-roster-stage">
            <section class="section panel-rail player-summary-card">${dashboardPlayerSummaryTable(rows)}</section>
            <aside class="journey-roster-aside">
              <section class="section panel-rail identity-card">${teamIdentityRankBlock(dash)}</section>
              <section class="section panel-rail starting-card">${startingFiveBlock(rows, editable)}</section>
            </aside>
          </div>
        </section>

        ${!phaseKind ? `
          <section class="journey-chapter journey-season" data-journey-chapter="season">
            ${journeyChapterIntro("The Season", "Time moves. Context changes.", "Read the schedule, watch the standings bend, and see development accumulate as the year unfolds.")}
            <div class="journey-season-stage">
              <section class="section panel-rail calendar-card">${dashboardMonthCalendar()}</section>
              <section class="section panel-rail standings-card">${userConferenceStandings()}</section>
              <section class="section panel-rail development-trend-card">${developmentTrendCard(rows)}</section>
            </div>
          </section>` : ""}

        <section class="journey-chapter journey-office" data-journey-chapter="office">
          ${journeyChapterIntro("Front Office", "Build beyond tonight", "Contracts, staff, picks, and transactions turn a good season into a durable franchise.")}
          <div class="journey-office-stage">
            <section class="section panel-rail dashboard-actions-card${readonlyClass}">${dashboardActionsCard(editable)}</section>
            <section class="section panel-rail draft-picks-card">${draftPicksCard()}</section>
            <section class="section panel-rail staff-card">${staffDashboardCard(rows, dash, editable)}</section>
          </div>
        </section>

        <section class="journey-chapter journey-league" data-journey-chapter="league">
          ${journeyChapterIntro("Around The League", "Thirty stories. One season.", "The news cycle, the best players, and the talent market move whether you are watching or not.")}
          <div class="journey-league-stage">
            <section class="section panel-rail events-card">${leagueEventRotator(true)}</section>
            <section class="section panel-rail free-agent-market-card${readonlyClass}">${dashboardFreeAgentMarketCard(editable, 9, true)}</section>
          </div>
        </section>
      </main>
      <div class="journey-progress" aria-hidden="true"><span></span></div>
    </div>`;
}

function journeyChapterIntro(eyebrow, title, description) {
  return `<header class="journey-chapter-intro"><p>${escapeHtml(eyebrow)}</p><h2>${escapeHtml(title)}</h2><span>${escapeHtml(description)}</span></header>`;
}

function dashboardTeamName(team) {
  const source = state.teams.find((candidate) => teamLabel(candidate) === team) || {};
  return source.full_name || source.name || [source.city, source.nickname].filter(Boolean).join(" ") || `${team} Basketball`;
}

function journeyNextGame(team) {
  const current = String(state.home?.save?.current_date || "").slice(0, 10);
  const games = (state.data.dashboardCalendar?.games || [])
    .filter((game) => [game.home, game.home_team, game.away, game.away_team].includes(team))
    .filter((game) => String(game.date || "").slice(0, 10) >= current)
    .sort((a, b) => String(a.date || "").localeCompare(String(b.date || "")));
  const game = games[0];
  if (!game) return null;
  const home = teamLabel(game.home || game.home_team);
  const away = teamLabel(game.away || game.away_team);
  const opponent = home === team ? away : home;
  return {
    title: `${home === team ? "vs" : "at"} ${opponent}`,
    detail: formatWrittenDate(game.date) || String(game.date || "Upcoming game"),
  };
}

function teamBrandStyle(_team) {
  return "";
}

function dashboardPhaseWorkspace(kind) {
  if (kind === "fantasy_draft") return fantasyDraftDashboardWorkspace();
  if (kind === "playoffs") return playoffDashboardWorkspace();
  if (kind === "draft") return draftDashboardWorkspace();
  if (kind === "free_agency") return freeAgencyDashboardWorkspace();
  if (kind === "cutdown") return rosterCutdownDashboardWorkspace();
  if (kind === "staff_retention") return staffRetentionDashboardWorkspace();
  return `<div class="empty">Seasonal workspace unavailable.</div>`;
}

function fantasyDraftDashboardWorkspace() {
  const room = state.data.fantasyDraft || {};
  const current = room.current_team || {};
  const viewer = room.viewer_team || {};
  const roster = room.viewer_roster || [];
  const position = state.fantasyPosition || "all";
  const search = String(state.fantasySearch || "").trim().toLowerCase();
  const available = (room.available_players || []).filter((player) => {
    const matchesPosition = position === "all" || String(player.position || "").includes(position);
    const matchesSearch = !search || String(player.name || "").toLowerCase().includes(search);
    return matchesPosition && matchesSearch;
  });
  if (
    state.selectedFantasyPlayer &&
    !(room.available_players || []).some((player) => player.player_id === state.selectedFantasyPlayer)
  ) {
    state.selectedFantasyPlayer = "";
  }
  const selected = (room.available_players || []).find(
    (player) => player.player_id === state.selectedFantasyPlayer,
  );
  const watchlist = room.watchlist || [];
  const isMultiplayer = Boolean(state.multiplayer.session && state.multiplayer.league?.status === "active");
  const clock = state.multiplayer.league?.clock || {};
  return `
    <div class="phase-workspace-head fantasy-draft-head">
      <div>
        <p class="eyebrow">League Reset · Snake Draft</p>
        <h3>Fantasy Draft War Room</h3>
      </div>
      <div class="fantasy-clock">
        <span>Pick ${escapeHtml(room.pick_number || 0)} / ${escapeHtml(room.total_picks || 450)}</span>
        <strong>${escapeHtml(current.abbrev || "Complete")}</strong>
        <small>Round ${escapeHtml(room.round || 1)}${isMultiplayer && clock.remaining_seconds !== undefined ? ` · ${formatClock(clock.remaining_seconds)}` : ""}</small>
      </div>
      <div class="toolbar phase-workspace-controls">
        <button id="fantasyExitSaves">Exit To Saves</button>
        ${isMultiplayer && room.is_viewer_turn ? `<button id="fantasyClockExtension">+45s</button>` : ""}
        ${!isMultiplayer && !room.is_viewer_turn && room.status === "in_progress" ? `<button id="fantasySimOne">Sim One Pick</button>` : ""}
        ${!isMultiplayer && !room.is_viewer_turn && room.status === "in_progress" ? `<button id="fantasyToUser">Sim To My Pick</button>` : ""}
        <button id="fantasyPick" class="primary-action" ${room.is_viewer_turn && selected ? "" : "disabled"}>
          ${selected ? `Draft ${escapeHtml(selected.name)}` : (room.is_viewer_turn ? "Select A Player" : `Waiting For ${escapeHtml(current.abbrev || "draft")}`)}
        </button>
      </div>
    </div>
    <div class="fantasy-draft-layout">
      <section class="phase-board-panel fantasy-player-board">
        <div class="fantasy-board-tools">
          <label>
            <span>Search players</span>
            <input id="fantasySearch" value="${escapeAttr(state.fantasySearch || "")}" placeholder="Name" />
          </label>
          <label>
            <span>Position</span>
            <select id="fantasyPosition">
              ${["all", "PG", "SG", "SF", "PF", "C"].map((value) => `<option value="${value}" ${position === value ? "selected" : ""}>${value === "all" ? "All positions" : value}</option>`).join("")}
            </select>
          </label>
          <span>${available.length} shown · ${room.available_count || 0} available</span>
        </div>
        <div class="fantasy-player-table">
          <div class="fantasy-player-row fantasy-player-labels">
            <span>Player</span><span>Age</span><span>OVR</span><span>Ceiling</span><span>Fit</span><span>Salary</span><span>Years</span><span>Watch</span>
          </div>
          ${available.map((player) => {
            const value = Number(player.display_overall || player.ratings?.overall || player.ratings_prior_overall || player.impact || 0);
            const fit = Number(player.fit_score || 0);
            return `<div class="fantasy-player-row ${state.selectedFantasyPlayer === player.player_id ? "selected" : ""}" data-fantasy-player="${escapeAttr(player.player_id)}" role="button" tabindex="0">
              <span class="fantasy-player-name">
                <button data-fantasy-card="${escapeAttr(player.player_id)}" title="Open player card">${escapeHtml(player.name || "Unknown")}</button>
                <small>${escapeHtml(player.position || "—")} · ${escapeHtml(heightFromRow(player) || "—")}</small>
              </span>
              <span>${plainNumber(player.age)}</span>
              <span class="fantasy-meter" style="--meter:${Math.max(0, Math.min(100, value))}%"><i></i><em>${plainNumber(value)}</em></span>
              <span class="fantasy-ceiling"><strong>${plainNumber(player.ceiling_overall || value)}</strong><small>+${plainNumber(player.growth_runway || 0)}</small></span>
              <span class="fantasy-meter fit" style="--meter:${Math.max(0, Math.min(100, fit))}%"><i></i><em>${plainNumber(fit)}</em></span>
              <span>${money(player.salary_millions)}</span>
              <span>${escapeHtml(player.contract_years || 0)}</span>
              <button class="fantasy-watch-button ${player.is_watchlisted ? "active" : ""}" data-fantasy-watch="${escapeAttr(player.player_id)}">${player.is_watchlisted ? "Watching" : "Watch"}</button>
            </div>`;
          }).join("") || `<div class="empty">No available players match these filters.</div>`}
        </div>
      </section>
      <section class="phase-focus-panel fantasy-roster-board">
        ${sectionHead(`${escapeHtml(viewer.abbrev || userTeam())} Roster`, `${roster.length}/${room.roster_size || 15} · ${money(room.viewer_payroll_millions)}`)}
        <div class="fantasy-roster-list">
          ${roster.map((player, index) => `<div>
            <span>${index + 1}</span>
            <strong><button data-fantasy-card="${escapeAttr(player.player_id)}">${escapeHtml(player.name || "Unknown")}</button></strong>
            <small>${escapeHtml(player.position || "")} · age ${plainNumber(player.age)}</small>
            <em>${money(player.salary_millions)}</em>
          </div>`).join("") || `<div class="empty">Your first selection will establish the roster.</div>`}
        </div>
        <div class="fantasy-watchlist-head">
          <span>Watchlist</span>
          <small>${watchlist.length} available</small>
        </div>
        <div class="fantasy-watchlist">
          ${watchlist.map((player) => `<div data-fantasy-player="${escapeAttr(player.player_id)}" role="button" tabindex="0">
            <span>${escapeHtml(player.position || "")}</span>
            <strong><button data-fantasy-card="${escapeAttr(player.player_id)}">${escapeHtml(player.name || "Unknown")}</button></strong>
            <em>${plainNumber(player.display_overall || player.ratings?.overall || player.ratings_prior_overall || player.impact)} OVR</em>
            <button data-fantasy-watch="${escapeAttr(player.player_id)}" aria-label="Remove ${escapeAttr(player.name || "player")} from watchlist">Remove</button>
          </div>`).join("") || `<div class="empty">Watch players to keep a short board. Drafted players disappear automatically.</div>`}
        </div>
        ${selected ? `<div class="fantasy-selection-card">
          <p class="eyebrow">On Your Board</p>
          <h4><button data-fantasy-card="${escapeAttr(selected.player_id)}">${escapeHtml(selected.name)}</button></h4>
          <p>${escapeHtml(selected.position || "")} · age ${plainNumber(selected.age)} · ${escapeHtml(heightFromRow(selected) || "")}</p>
          <div class="fantasy-selection-metrics">
            <span><small>On court</small><strong>${plainNumber(selected.on_court_value)}</strong></span>
            <span><small>Contract surplus</small><strong>${plainNumber(selected.contract_surplus)}</strong></span>
            <span><small>Ceiling OVR</small><strong>${plainNumber(selected.ceiling_overall)}</strong></span>
            <span><small>Fit</small><strong>${plainNumber(selected.fit_score)}</strong></span>
          </div>
          <button class="fantasy-selected-watch ${selected.is_watchlisted ? "active" : ""}" data-fantasy-watch="${escapeAttr(selected.player_id)}">${selected.is_watchlisted ? "Remove From Watchlist" : "Add To Watchlist"}</button>
        </div>` : ""}
      </section>
      <aside class="phase-upcoming-panel fantasy-draft-ticker">
        ${sectionHead("Draft Wire", `${escapeHtml(current.abbrev || "Complete")} on clock`)}
        <div class="fantasy-upcoming">
          ${(room.upcoming || []).map((pick, index) => `<div class="${index === 0 ? "on-clock" : ""}">
            <span>#${escapeHtml(pick.pick_number)}</span>
            <img src="/assets/team_logos/${escapeAttr(pick.team?.abbrev || "")}.png" alt="" />
            <strong>${escapeHtml(pick.team?.abbrev || "")}</strong>
            <small>R${escapeHtml(pick.round || "")}</small>
          </div>`).join("")}
        </div>
        <p class="eyebrow fantasy-recent-label">Recent selections</p>
        <div class="fantasy-recent">
          ${(room.recent_picks || []).map((pick) => `<div>
            <span>#${escapeHtml(pick.pick_number)}</span>
            <strong>${escapeHtml(pick.player_name || "")}</strong>
            <small>${escapeHtml((state.teams || []).find((team) => team.id === pick.team_id)?.abbrev || "")}</small>
          </div>`).join("") || `<div class="empty">The clock is open.</div>`}
        </div>
      </aside>
    </div>`;
}

function fantasyPlayerCard(playerId) {
  const room = state.data.fantasyDraft || {};
  const player = [
    ...(room.available_players || []),
    ...(room.viewer_roster || []),
    ...(room.watchlist || []),
  ].find((row) => row.player_id === playerId);
  if (!player) return;
  const ratings = player.ratings || {};
  const growth = player.growth_outlook || {};
  const offenseAxes = [
    ["Shooting", ratings.shooting],
    ["Range", ratings.range],
    ["Creation", ratings.creation],
    ["Passing", ratings.passing],
    ["Rim", ratings.rim_pressure],
    ["Portability", ratings.portability],
  ];
  const defenseAxes = [
    ["Defense", ratings.defense],
    ["Effort", ratings.def_effort],
    ["Navigation", ratings.screen_nav],
    ["Rim protect", ratings.rim_deterrence],
    ["Rebound", ratings.rebounding],
    ["Athleticism", ratings.athleticism],
  ];
  const ratingRows = [
    ["Overall", ratings.overall || player.ratings_prior_overall],
    ["Shooting", ratings.shooting], ["Release", ratings.release], ["Range", ratings.range],
    ["Shot versatility", ratings.versatility], ["Creation", ratings.creation], ["Handle", ratings.handle],
    ["Passing", ratings.passing], ["Rim pressure", ratings.rim_pressure], ["Defense", ratings.defense],
    ["Defensive effort", ratings.def_effort], ["Screen navigation", ratings.screen_nav],
    ["Rim deterrence", ratings.rim_deterrence], ["Rebounding", ratings.rebounding],
    ["Offensive rebounding", ratings.oreb], ["Athleticism", ratings.athleticism],
    ["Stamina", ratings.stamina], ["Basketball IQ", ratings.iq], ["Portability", ratings.portability],
    ["Playoff translation", ratings.playoff],
  ].filter(([, value]) => value !== undefined && value !== null);
  const available = (room.available_players || []).some((row) => row.player_id === playerId);
  state.modal = {
    kind: "fantasyPlayer",
    title: player.name || "Player Card",
    subtitle: `${player.position || "—"} · age ${decimalNumber(player.age)} · ${heightFromRow(player) || "height unavailable"}`,
    playerId,
    body: `<div class="fantasy-player-card">
      <section class="fantasy-card-hero">
        <div class="fantasy-card-number">
          <span>OVR</span>
          <strong>${plainNumber(player.display_overall || ratings.overall || player.ratings_prior_overall)}</strong>
          <small>${escapeHtml(player.original_team_id ? teamLabel(player.original_team_id) : "Fantasy pool")}</small>
        </div>
        <div class="fantasy-card-outlook">
          <p class="eyebrow">Three-year outlook</p>
          <h4>${escapeHtml(growth.label || "Scouting projection")}</h4>
          <div>
            <span><small>Likely growth</small><strong>+${plainNumber(growth.likely_growth || 0)} OVR</strong></span>
            <span><small>Good-situation runway</small><strong>+${plainNumber(growth.high_end_growth || 0)} OVR</strong></span>
            <span><small>Ceiling OVR</small><strong>${plainNumber(growth.ceiling_overall || player.ceiling_overall)}</strong></span>
          </div>
          <p>${escapeHtml(growth.explanation || "Projection accounts for age, role, present rating, and remaining development runway.")}</p>
        </div>
        <div class="fantasy-card-actions">
          <span><small>Projected role</small><strong>${plainNumber(player.minutes_projection)} MPG</strong></span>
          <span><small>Health risk</small><strong>${plainNumber(player.health_risk)}</strong></span>
          <span><small>Contract surplus</small><strong>${signedNumber(player.contract_surplus)}</strong></span>
          ${available ? `<button data-fantasy-card-select="${escapeAttr(playerId)}">Place On Draft Board</button>
            <button data-fantasy-card-watch="${escapeAttr(playerId)}" class="${player.is_watchlisted ? "active" : ""}">${player.is_watchlisted ? "Remove From Watchlist" : "Add To Watchlist"}</button>` : `<small>Already selected</small>`}
        </div>
      </section>
      <section class="fantasy-card-radars">
        ${fantasyPlayerRadar("Offensive shape", offenseAxes, "offense")}
        ${fantasyPlayerRadar("Defense / physical", defenseAxes, "defense")}
      </section>
      <section class="fantasy-card-ratings">
        <div class="fantasy-card-section-head"><span>Rating ledger</span><small>same 1-99 scale used by the team dashboard</small></div>
        <div class="fantasy-rating-grid">
          ${ratingRows.map(([label, value]) => `<div class="${ratingTone(value)}"><span>${escapeHtml(label)}</span><strong>${plainNumber(value)}</strong><i style="--rating:${clampNumber(Number(value || 0), 0, 99)}%"></i></div>`).join("")}
        </div>
      </section>
      <section class="fantasy-card-contract">
        <div class="fantasy-card-section-head"><span>Contract runway</span><small>red is this player's salary against each season's hard cap</small></div>
        ${fantasyPlayerContractChart(player.contract_seasons || [])}
      </section>
    </div>`,
  };
  renderModal();
}

function dashboardPlayerCard(playerId) {
  const dash = state.data.dashboard || {};
  const player = rosterRows(dash).find((row) => row.id === playerId);
  if (!player) return;
  const ratings = player.display_ratings || player.ratings || player.attributes || {};
  const viewedTeam = teamLabel(dash.team || state.dashboardTeam || userTeam());
  const capByYear = dash.cap_by_year || {};
  const salaryByYear = player.salary_by_year || {};
  const seasons = Object.keys(capByYear).slice(0, 4).map((season) => ({
    season,
    salary_millions: Number(salaryByYear[season] || 0),
    hard_cap_millions: Number(capByYear[season]?.hard_cap_millions || 0),
  }));
  const offenseAxes = [
    ["Shooting", ratings.shooting],
    ["Range", ratings.range],
    ["Creation", ratings.creation],
    ["Passing", ratings.passing],
    ["Rim pressure", ratings.rim_pressure],
    ["Portability", ratings.portability],
  ];
  const defenseAxes = [
    ["Defense", ratings.defense],
    ["Effort", ratings.def_effort],
    ["Navigation", ratings.screen_nav],
    ["Rim protect", ratings.rim_deterrence],
    ["Rebound", ratings.rebounding],
    ["Athleticism", ratings.athleticism],
  ];
  const ratingRows = [
    ["Overall", ratings.overall], ["Shooting", ratings.shooting], ["Release", ratings.release],
    ["Range", ratings.range], ["Shot versatility", ratings.versatility], ["Creation", ratings.creation],
    ["Handle", ratings.handle], ["Passing", ratings.passing], ["Rim pressure", ratings.rim_pressure],
    ["Defense", ratings.defense], ["Defensive effort", ratings.def_effort],
    ["Screen navigation", ratings.screen_nav], ["Rim deterrence", ratings.rim_deterrence],
    ["Rebounding", ratings.rebounding], ["Offensive rebounding", ratings.oreb],
    ["Athleticism", ratings.athleticism], ["Stamina", ratings.stamina], ["Basketball IQ", ratings.iq],
    ["Portability", ratings.portability], ["Playoff translation", ratings.playoff],
  ].filter(([, value]) => value !== undefined && value !== null);
  const health = player.health || {};
  const gamesMissed = gamesMissedFromRow(player);
  const healthStatus = isPlayerInjured(health)
    ? `${health.label || "Injured"}${gamesMissed ? ` · ${gamesMissed} games missed` : ""}`
    : "Available";
  const role = player.is_starting_five
    ? `Starting five · slot ${player.starting_slot || "—"}`
    : Number(player.minutes_projection || 0) > 0
      ? "Rotation"
      : "Depth";
  state.modal = {
    kind: "dashboardPlayer",
    title: player.name || "Player Card",
    subtitle: `${viewedTeam} · ${player.position || "—"} · age ${decimalNumber(player.age)} · ${heightFromRow(player) || "height unavailable"}`,
    body: `<div class="fantasy-player-card dashboard-player-card">
      <section class="fantasy-card-hero">
        <div class="fantasy-card-number">
          <span>OVR</span>
          <strong>${plainNumber(ratings.overall)}</strong>
          <small>${escapeHtml(viewedTeam)}</small>
        </div>
        <div class="fantasy-card-outlook dashboard-player-production">
          <p class="eyebrow">${escapeHtml(statsContextLabel(dash.stats_context) || "Season production")}</p>
          <h4>${plainNumber(player.points_per_game)} PPG · ${plainNumber(player.rebounds_per_game)} RPG · ${plainNumber(player.assists_per_game)} APG</h4>
          <div>
            <span><small>Minutes</small><strong>${plainNumber(mpgFromRow(player))} MPG</strong></span>
            <span><small>Games</small><strong>${decimalNumber(player.games || 0)} played</strong></span>
            <span><small>Role</small><strong>${escapeHtml(role)}</strong></span>
          </div>
          <p>${escapeHtml(healthStatus)}</p>
        </div>
        <div class="fantasy-card-actions dashboard-player-context">
          <span><small>FG</small><strong>${plainNumber(player.fg_pct)}%</strong></span>
          <span><small>3PT</small><strong>${plainNumber(player.fg3_pct)}%</strong></span>
          <span><small>STL / BLK</small><strong>${plainNumber(player.steals_per_game)} / ${plainNumber(player.blocks_per_game)}</strong></span>
          <small>${seasons[0]?.salary_millions > 0 ? `${money(seasons[0].salary_millions)} current-season salary` : "No guaranteed current-season salary"}</small>
        </div>
      </section>
      <section class="fantasy-card-radars">
        ${fantasyPlayerRadar("Offensive shape", offenseAxes, "offense")}
        ${fantasyPlayerRadar("Defense / physical", defenseAxes, "defense")}
      </section>
      <section class="fantasy-card-ratings">
        <div class="fantasy-card-section-head"><span>Rating ledger</span><small>dashboard 1-99 presentation scale</small></div>
        <div class="fantasy-rating-grid">
          ${ratingRows.map(([label, value]) => `<div class="${ratingTone(value)}"><span>${escapeHtml(label)}</span><strong>${plainNumber(value)}</strong><i style="--rating:${clampNumber(Number(value || 0), 0, 99)}%"></i></div>`).join("")}
        </div>
      </section>
      <section class="fantasy-card-contract">
        <div class="fantasy-card-section-head"><span>Contract runway</span><small>${seasons.filter((season) => season.salary_millions > 0).length} guaranteed season(s) shown</small></div>
        ${fantasyPlayerContractChart(seasons)}
      </section>
    </div>`,
  };
  renderModal();
}

function draftProspectCard(prospectId) {
  const rows = draftBoardRows(state.data.draft?.draft_board || {});
  const row = rows.find((item) => String(item.id) === String(prospectId));
  if (!row) return;
  const prospect = row.prospect || {};
  const scout = row.scout || {};
  const projectionAxes = [
    ["Now", row.now],
    ["Potential", row.potential],
    ["Floor", row.floor],
    ["Ceiling", row.ceiling],
    ["Team fit", row.fit],
    ["Scouted", row.scoutedPct],
  ];
  const ledger = [
    ["Current ability", row.now],
    ["Potential", row.potential],
    ["Downside floor", row.floor],
    ["High-end ceiling", row.ceiling],
    ["Team fit", row.fit],
    ["Scouted", row.scoutedPct],
    ["Volatility", row.volatility],
    ["Rookie contract value", row.rookieContractValue],
  ].filter(([, value]) => value !== undefined && value !== null && value !== "");
  const range = Math.max(0, Number(row.ceiling || 0) - Number(row.floor || 0));
  state.modal = {
    kind: "draftProspect",
    title: row.name || "Prospect Card",
    subtitle: `${row.position || "—"} · age ${row.age || "—"} · ${row.height || "height unavailable"} · scout rank ${row.rank || "—"}`,
    body: `<div class="fantasy-player-card draft-scout-card">
      <section class="fantasy-card-hero">
        <div class="fantasy-card-number">
          <span>NOW</span>
          <strong>${plainNumber(row.now)}</strong>
          <small>${escapeHtml(prospect.source_team || "Draft class")}</small>
        </div>
        <div class="fantasy-card-outlook">
          <p class="eyebrow">Scouting projection</p>
          <h4>${escapeHtml(rowLabel(prospect.archetype || "development prospect"))}</h4>
          <div>
            <span><small>Potential</small><strong>${plainNumber(row.potential)}</strong></span>
            <span><small>Floor</small><strong>${plainNumber(row.floor)}</strong></span>
            <span><small>Ceiling</small><strong>${plainNumber(row.ceiling)}</strong></span>
          </div>
          <p>${escapeHtml(range >= 22 ? "Wide outcome band: the tools are meaningful, but development carries real variance." : range >= 13 ? "Moderate projection range with both rotation value and upside in play." : "Relatively stable projection with a narrower range of likely outcomes.")}</p>
        </div>
        <div class="fantasy-card-actions">
          <span><small>Team fit</small><strong>${draftMetric(row.fit)}</strong></span>
          <span><small>Scouted</small><strong>${draftMetric(row.scoutedPct)}%</strong></span>
          <span><small>Volatility</small><strong>${draftMetric(row.volatility)}</strong></span>
          <small>${row.status === "drafted" ? `Selected #${escapeHtml(row.selectedPick)} by ${escapeHtml(teamLabel(row.selectedTeam))}` : "Available on the board"}</small>
        </div>
      </section>
      <section class="fantasy-card-radars draft-scout-radar">
        ${fantasyPlayerRadar("Projection shape", projectionAxes, "offense")}
        <div class="draft-scout-notes">
          <div class="fantasy-card-section-head"><span>Profile</span><small>scout-facing context</small></div>
          <dl>
            <div><dt>Position</dt><dd>${escapeHtml(row.position || "—")}</dd></div>
            <div><dt>Build</dt><dd>${escapeHtml(row.height || "—")}${prospect.weight_lbs ? ` · ${escapeHtml(prospect.weight_lbs)} lb` : ""}</dd></div>
            <div><dt>Development curve</dt><dd>${escapeHtml(rowLabel(row.developmentCurve || "standard"))}</dd></div>
            <div><dt>Source</dt><dd>${escapeHtml(prospect.source_team || "Generated class")}</dd></div>
          </dl>
        </div>
      </section>
      <section class="fantasy-card-ratings">
        <div class="fantasy-card-section-head"><span>Scouting ledger</span><small>same read used throughout draft night</small></div>
        <div class="fantasy-rating-grid">
          ${ledger.map(([label, value]) => `<div class="${ratingTone(value)}"><span>${escapeHtml(label)}</span><strong>${draftMetric(value)}</strong><i style="--rating:${clampNumber(Number(value || 0), 0, 99)}%"></i></div>`).join("")}
        </div>
      </section>
      <section class="fantasy-card-contract draft-rookie-scale">
        <div class="fantasy-card-section-head"><span>Draft outlook</span><small>evaluation, not a guaranteed outcome</small></div>
        <div class="draft-outlook-strip">
          <span><small>Board status</small><strong>${row.status === "drafted" ? "Selected" : "Available"}</strong></span>
          <span><small>Scout rank</small><strong>#${escapeHtml(row.rank || "—")}</strong></span>
          <span><small>Fit grade</small><strong>${draftMetric(row.fit)}</strong></span>
          <span><small>Rookie value</small><strong>${draftMetric(row.rookieContractValue)}</strong></span>
        </div>
      </section>
    </div>`,
  };
  renderModal();
}

function fantasyPlayerRadar(title, axes, className) {
  const width = 300;
  const height = 220;
  const centerX = width / 2;
  const centerY = 106;
  const radius = 72;
  const point = (index, proportion, extra = 0) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / axes.length;
    return {
      x: centerX + Math.cos(angle) * (radius * proportion + extra),
      y: centerY + Math.sin(angle) * (radius * proportion + extra),
    };
  };
  const polygon = (proportion) => axes.map((_, index) => {
    const position = point(index, proportion);
    return `${position.x.toFixed(1)},${position.y.toFixed(1)}`;
  }).join(" ");
  const shape = axes.map(([, value], index) => {
    const position = point(index, clampNumber(Number(value || 0) / 99, 0.04, 1));
    return `${position.x.toFixed(1)},${position.y.toFixed(1)}`;
  }).join(" ");
  return `<div class="fantasy-player-radar ${escapeAttr(className)}">
    <h5>${escapeHtml(title)}</h5>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(title)} radar chart">
      ${[0.25, 0.5, 0.75, 1].map((level) => `<polygon class="player-radar-grid" points="${polygon(level)}"></polygon>`).join("")}
      ${axes.map((_, index) => { const edge = point(index, 1); return `<line class="player-radar-axis" x1="${centerX}" y1="${centerY}" x2="${edge.x.toFixed(1)}" y2="${edge.y.toFixed(1)}"></line>`; }).join("")}
      <polygon class="player-radar-shape" points="${shape}"><title>${escapeHtml(axes.map(([label, value]) => `${label}: ${decimalNumber(value)}`).join(" | "))}</title></polygon>
      ${axes.map(([label, value], index) => {
        const labelPoint = point(index, 1, 22);
        const anchor = Math.abs(labelPoint.x - centerX) < 8 ? "middle" : labelPoint.x < centerX ? "end" : "start";
        return `<text class="player-radar-label" text-anchor="${anchor}" x="${labelPoint.x.toFixed(1)}" y="${labelPoint.y.toFixed(1)}">${escapeHtml(label)}</text>`;
      }).join("")}
    </svg>
  </div>`;
}

function fantasyPlayerContractChart(seasons) {
  return `<div class="fantasy-player-contract-columns">
    ${seasons.slice(0, 4).map((season) => {
      const salary = Number(season.salary_millions || 0);
      const hardCap = Math.max(1, Number(season.hard_cap_millions || 230));
      const height = clampNumber((salary / hardCap) * 100, 0, 100);
      return `<div class="fantasy-player-contract-year">
        <strong>${escapeHtml(season.season || "—")}</strong>
        <div class="fantasy-player-contract-column" title="${escapeAttr(salary ? `${money(salary)} of ${money(hardCap)} hard cap` : "No guaranteed salary")}">
          <i style="height:${height}%"></i>
        </div>
        <span>${salary ? money(salary) : "—"}</span>
      </div>`;
    }).join("")}
  </div>`;
}

function ratingTone(value) {
  const rating = Number(value || 0);
  if (rating >= 92) return "elite";
  if (rating >= 82) return "strong";
  if (rating < 68) return "weak";
  return "average";
}

function decimalNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : "—";
}

function averageNumber(values, fallback = 0) {
  const numbers = values.map(Number).filter(Number.isFinite);
  return numbers.length ? numbers.reduce((sum, value) => sum + value, 0) / numbers.length : fallback;
}

function playoffDashboardWorkspace() {
  const room = state.data.playoffs || {};
  const series = room.series || [];
  const canSim = ["play_in", "playoffs"].includes(String(room.phase || "")) && room.status !== "completed";
  const leaders = state.data.playoffLeaders?.leaders || [];
  const leaderStat = state.playoffLeaderStat || "points";
  const leaderOptions = [
    ["points", "PPG"],
    ["rebounds", "RPG"],
    ["assists", "APG"],
    ["steals", "SPG"],
    ["blocks", "BPG"],
    ["fg3m", "3PM"],
  ];
  return `
    <div class="playoff-command-center">
      <header class="playoff-command-header">
        <div class="playoff-command-title">
          <h3>Playoffs</h3>
          <p>${escapeHtml(room.current_date || state.home?.save?.current_date || "")} · ${escapeHtml(rowLabel(room.round || "picture"))} · ${escapeHtml(rowLabel(room.status || "live"))}</p>
        </div>
        <div class="toolbar playoff-command-controls">
          ${canSim ? `
            <button data-playoff-sim="game" title="Simulate one game in every active series">1 Game / Series</button>
            <button data-playoff-sim="round" title="Simulate the rest of the current round">Finish Round</button>
            <button data-playoff-sim="all" title="Simulate the remaining playoffs">Finish Playoffs</button>` : ""}
          ${room.status === "completed" ? `<button id="playoffAdvanceStage">Advance To Next Stage</button>` : ""}
        </div>
      </header>
      ${room.champion ? `<div class="phase-champion">Champion <strong>${escapeHtml(teamLabel(room.champion))}</strong></div>` : ""}
      <div class="phase-playoff-layout">
        <div class="phase-bracket-shell">
          ${series.length ? playoffBracket(series, room.champion) : `<div class="empty">The bracket will populate when playoff play begins.</div>`}
        </div>
        <aside class="phase-leaders-panel">
          <div class="playoff-leaders-head">
            <h4>Playoff Leaders</h4>
            <select data-playoff-leader-stat aria-label="Playoff leader category">
              ${leaderOptions.map(([value, label]) => `<option value="${value}" ${value === leaderStat ? "selected" : ""}>${label}</option>`).join("")}
            </select>
          </div>
          <ol class="phase-leader-list">
            ${leaders.slice(0, 9).map((row, index) => `<li>
              <span>${index + 1}</span>
              <strong>${escapeHtml(row.player?.name || row.player_name || "Unknown")}</strong>
              <small>${escapeHtml(row.team_abbrev || "")}</small>
              <em>${Number(row[`${leaderStat}_per_game`] || 0).toFixed(1)}</em>
            </li>`).join("") || `<li class="empty">Leaders appear after playoff games.</li>`}
          </ol>
        </aside>
      </div>
    </div>`;
}

function draftDashboardWorkspace() {
  const draft = state.data.draft || {};
  const current = draft.current_selection || {};
  const selection = current.selection || {};
  const prospect = current.prospect || {};
  const status = draft.state?.status || "in_progress";
  const locked = status === "locked_until_draft";
  const completedDraft = status === "completed" || (!current.selection && (draft.draft_timeline || []).length > 0);
  const presentationKey = `${state.currentSave}:${draft.year || "draft"}`;
  if (state.draftPresentationKey !== presentationKey) {
    state.draftPresentationKey = presentationKey;
    state.draftPresentationStage = draft.presentation_stage || (locked ? "odds" : "draft");
  } else if (draft.presentation_stage === "draft" && state.draftPresentationStage === "odds") {
    state.draftPresentationStage = "draft";
  }
  if (state.draftPresentationStage === "odds") return draftLotteryOddsWorkspace(draft);
  if (state.draftPresentationStage === "reveal") return draftLotteryRevealWorkspace(draft);
  const boardRows = draftBoardRows(draft.draft_board);
  const filteredBoard = state.draftBoardFilter === "all" ? boardRows : boardRows.filter((row) => row.status !== "drafted");
  const visibleBoard = sortDraftBoardRows(filteredBoard, state.draftBoardSort);
  const clockTeam = current.team || draft.board_context_team || selection.team_id;
  const currentPick = Number(selection.overall_pick || 0);
  const currentPickKey = `${draft.year || "draft"}:${currentPick}:${teamLabel(clockTeam)}`;
  const userOnClock = Boolean(draft.current_pick_is_user_owned);
  const availableIds = new Set(boardRows.filter((row) => row.status !== "drafted").map((row) => String(row.id)));
  if (state.draftSelectionPickKey !== currentPickKey) {
    state.draftSelectionPickKey = currentPickKey;
    state.selectedDraftProspect = "";
  }
  if (!availableIds.has(String(state.selectedDraftProspect || ""))) state.selectedDraftProspect = "";
  const selectedProspect = boardRows.find((row) => String(row.id) === String(state.selectedDraftProspect || ""));
  const nextUserPick = Number(draft.next_user_selection?.selection?.overall_pick || 0);
  const canSimToUser = Boolean(current.selection && !userOnClock && nextUserPick > currentPick);
  return `
    <div class="draft-night-shell">
      <header class="draft-clock-strip">
        <div class="draft-clock-team">
          ${draftTeamLogo(clockTeam)}
          <div>
            <p class="eyebrow">${current.selection ? `On the clock · Pick ${escapeHtml(selection.overall_pick)} of ${escapeHtml(draft.state?.total_picks || "")}` : "Draft complete"}</p>
            <h3>${current.selection ? escapeHtml(teamLabel(clockTeam)) : `${escapeHtml(draft.year || "")} Draft Complete`}</h3>
          </div>
        </div>
        ${current.selection ? `<div class="draft-clock-context"><span>${userOnClock ? "Your decision" : "AI selection"}</span><strong>${userOnClock ? (selectedProspect ? escapeHtml(selectedProspect.name) : "Select a prospect from the board") : `Simulate pick #${escapeHtml(currentPick)}`}</strong></div>` : `<p class="muted">All ${escapeHtml(draft.state?.total_picks || "")} selections are in.</p>`}
        <div class="toolbar draft-clock-actions">
          ${current.selection ? `${userOnClock
            ? `<button id="draftApply" ${selectedProspect ? "" : "disabled"}>${selectedProspect ? `Draft ${escapeHtml(selectedProspect.name)} at #${escapeHtml(currentPick)}` : "Choose A Prospect"}</button>`
            : `<button id="draftSimCurrent">Sim Current Pick: ${escapeHtml(currentPick)}</button>`}
            ${canSimToUser ? `<button id="draftToUser">Sim To My Pick: ${escapeHtml(nextUserPick)}</button>` : ""}
            <button id="draftAll">Finish Draft</button>` : `<button id="draftAdvanceStage">Advance To Next Stage</button>`}
        </div>
      </header>
      ${!completedDraft && (draft.trade_news || []).length ? `<div class="draft-news-strip"><strong>Breaking:</strong> ${escapeHtml((draft.trade_news || []).map((item) => item.headline || textValue(item)).join(" · "))}</div>` : ""}
      <div class="draft-night-grid">
        ${completedDraft ? `<section class="draft-prospect-panel draft-summary-panel">
          <div class="draft-panel-head">
            <div><h4>${escapeHtml(draft.year || "")} Draft Summary</h4><p>Every selection, in order. The draft board is closed.</p></div>
            <span class="pill">${escapeHtml((draft.draft_timeline || []).length)} picks</span>
          </div>
          ${completedDraftSummary(draft.draft_timeline || [])}
        </section>
        <aside class="draft-ledger-column">
          <section class="draft-ledger-panel draft-trade-recap-panel">
            <div class="draft-panel-head"><div><h4>Draft-Night Trades</h4><p>Every trade completed during the draft.</p></div></div>
            ${completedDraftTradeRecap(draft.trade_recap || draft.trade_news || [])}
          </section>
        </aside>` : `<section class="draft-prospect-panel">
          <div class="draft-panel-head">
            <div><h4>Prospect Board</h4><p>Your scouts' board for ${escapeHtml(teamLabel(draft.board_context_team || clockTeam))}. Select any available prospect when your team is on the clock.</p></div>
            <select id="draftBoardFilter" aria-label="Prospect availability filter"><option value="available" ${state.draftBoardFilter === "available" ? "selected" : ""}>Available</option><option value="all" ${state.draftBoardFilter === "all" ? "selected" : ""}>All prospects</option></select>
          </div>
          ${draftProspectBoard(visibleBoard, userOnClock, state.selectedDraftProspect)}
        </section>
        <aside class="draft-ledger-column">
          <section class="draft-ledger-panel draft-order-ledger-panel">
            <div class="draft-panel-head"><div><h4>Draft Order</h4><p>${escapeHtml((draft.previous_picks || []).length)} complete · current pick centered</p></div></div>
            ${draftPickTimeline(draft.draft_timeline || [])}
          </section>
        </aside>`}
      </div>
    </div>`;
}

function draftLotteryOddsWorkspace(draft) {
  const lottery = draft.lottery || {};
  return `<div class="draft-lottery-shell">
    <header class="draft-ceremony-head"><div><p class="eyebrow">${escapeHtml(draft.year || "")} Draft</p><h3>Lottery Odds</h3><p>The order has not been revealed. Odds reflect the completed season and pick ownership is shown separately.</p></div><button id="draftRevealLottery">Reveal Lottery Order</button></header>
    <div class="draft-odds-grid">${(lottery.odds || []).map((row) => `<article class="draft-odds-row"><span class="draft-seed">${escapeHtml(row.seed)}</span>${draftTeamLogo(row.team)}<strong>${escapeHtml(teamLabel(row.team))}</strong><em>${(Number(row.odds || 0) * (Number(row.odds || 0) <= 1 ? 100 : 1)).toFixed(1)}%</em>${row.context ? `<small>${escapeHtml(row.context)}</small>` : ""}</article>`).join("") || `<div class="empty">Lottery odds are not available for this fixed draft order.</div>`}</div>
    <footer class="draft-ceremony-note">${escapeHtml(lottery.notes || "Lottery odds are based on this save's standings.")}</footer>
  </div>`;
}

function draftLotteryRevealWorkspace(draft) {
  const lottery = draft.lottery || {};
  return `<div class="draft-lottery-shell draft-reveal-shell">
    <header class="draft-ceremony-head"><div><p class="eyebrow">Lottery complete</p><h3>${escapeHtml(draft.year || "")} Draft Order</h3><p>The first fourteen picks are set. Ownership shown here is the final team making the selection.</p></div><button id="draftEnterNight">Enter Draft Night</button></header>
    <div class="draft-reveal-grid">${(lottery.reveal || []).map((row) => `<article class="draft-reveal-row"><span class="draft-pick-number">${escapeHtml(row.pick)}</span>${draftTeamLogo(row.owner_team)}<div><strong>${escapeHtml(teamLabel(row.owner_team))}</strong><small>${row.ownership_changed ? `via ${escapeHtml(teamLabel(row.original_team))}` : `Seed ${escapeHtml(row.starting_seed || row.pick)}`}</small></div><em class="${Number(row.movement) > 0 ? "up" : Number(row.movement) < 0 ? "down" : ""}">${Number(row.movement) > 0 ? `↑${row.movement}` : Number(row.movement) < 0 ? `↓${Math.abs(row.movement)}` : "—"}</em></article>`).join("")}</div>
  </div>`;
}

function draftProspectBoard(rows, selectable = false, selectedId = "") {
  const headings = [
    ["rank", "Scouts ranking"], ["name", "Prospect"], ["position", "Pos"], ["age", "Age"],
    ["height", "Ht"], ["now", "Now"], ["potential", "Pot"], ["fit", "Fit"], ["status", "Status"],
  ];
  return `<div class="draft-prospect-scroll"><table class="draft-prospect-table"><thead><tr>${headings.map(([key, label]) => `<th><button class="draft-sort-button" data-draft-sort="${escapeAttr(key)}">${escapeHtml(label)}${draftSortMark(key)}</button></th>`).join("")}</tr></thead><tbody>${rows.map((row) => {
    const available = row.status !== "drafted";
    const selected = available && String(row.id) === String(selectedId || "");
    return `<tr class="${row.status === "drafted" ? "is-drafted" : ""}${selected ? " is-selected" : ""}${selectable && available ? " is-selectable" : ""}" ${selectable && available ? `data-draft-prospect="${escapeAttr(row.id)}" tabindex="0"` : ""}><td>${escapeHtml(row.rank)}</td><td><button type="button" class="draft-prospect-name" data-draft-prospect-card="${escapeAttr(row.id)}">${escapeHtml(row.name || "Unknown")}</button></td><td>${escapeHtml(row.position || "—")}</td><td>${escapeHtml(row.age ?? "—")}</td><td>${escapeHtml(row.height || "—")}</td><td>${draftMetric(row.now)}</td><td>${draftMetric(row.potential)}</td><td>${draftMetric(row.fit || row.grade)}</td><td>${row.status === "drafted" ? `<span class="drafted-badge">#${escapeHtml(row.selectedPick)} ${escapeHtml(teamLabel(row.selectedTeam))}</span>` : selected ? `<span class="available-badge selected-badge">Selected</span>` : `<span class="available-badge">Available</span>`}</td></tr>`;
  }).join("") || `<tr><td colspan="9" class="empty">No prospects match this view.</td></tr>`}</tbody></table></div>`;
}

function draftPickTimeline(rows) {
  return `<div class="draft-ledger-scroll" data-draft-ledger>${rows.map((row) => {
    const status = row.draft_status || "upcoming";
    const completed = status === "selected";
    const current = status === "current";
    return `<div class="draft-ledger-row ${current ? "is-current" : completed ? "is-complete" : "is-upcoming"}" ${current ? "data-current-draft-pick" : ""}><span class="draft-pick-number">${escapeHtml(row.selection?.overall_pick || "—")}</span>${draftTeamLogo(row.team)}<div><strong>${completed ? escapeHtml(row.prospect?.name || "Unknown prospect") : escapeHtml(teamLabel(row.team))}</strong><small>${completed ? `${escapeHtml(teamLabel(row.team))} · ${escapeHtml(row.prospect?.position || "")}` : current ? "On the clock" : "Upcoming pick"}</small></div>${current ? `<em>NOW</em>` : ""}</div>`;
  }).join("") || `<div class="empty">No draft order is available.</div>`}</div>`;
}

function completedDraftSummary(rows) {
  return `<div class="draft-summary-scroll"><table class="draft-summary-table"><thead><tr><th>Pick</th><th>Team</th><th>Prospect</th><th>Pos</th><th>Age</th><th>Height</th></tr></thead><tbody>${rows.map((row) => {
    const prospect = row.prospect || {};
    return `<tr><td><strong>#${escapeHtml(row.selection?.overall_pick || "—")}</strong></td><td><span class="draft-summary-team">${draftTeamLogo(row.team)}<span>${escapeHtml(teamLabel(row.team))}</span></span></td><td><strong>${escapeHtml(prospect.name || "Unknown prospect")}</strong></td><td>${escapeHtml(prospect.position || "—")}</td><td>${escapeHtml(prospect.age ?? "—")}</td><td>${escapeHtml(heightFromRow(prospect) || "—")}</td></tr>`;
  }).join("") || `<tr><td colspan="6" class="empty">No selections were recorded.</td></tr>`}</tbody></table></div>`;
}

function completedDraftTradeRecap(rows) {
  return `<div class="draft-trade-recap-list">${rows.map((row, index) => `<article class="draft-trade-recap-item"><span>${row.overall_pick ? `Pick #${escapeHtml(row.overall_pick)}` : `Trade ${index + 1}`}</span><strong>${escapeHtml(row.headline || textValue(row))}</strong>${row.date ? `<small>${escapeHtml(row.date)}</small>` : ""}</article>`).join("") || `<div class="draft-trade-recap-empty"><strong>No draft-night trades</strong><p>All selections were made without a trade.</p></div>`}</div>`;
}

function draftTeamLogo(team) {
  const abbrev = teamLabel(team);
  const logo = teamLogoSrc(abbrev);
  return logo ? `<span class="draft-team-logo"><img src="${escapeAttr(logo)}" alt="${escapeAttr(abbrev)} logo" /></span>` : `<span class="draft-team-logo draft-team-logo-fallback">${escapeHtml(abbrev)}</span>`;
}

function freeAgencyDashboardWorkspace() {
  const room = state.data.freeagency || {};
  const candidates = room.candidates || [];
  const exclusive = room.phase === "re_signing";
  const status = String(room.state?.status || "active");
  state.freeAgentCompareIds = state.freeAgentCompareIds.filter((id) => candidates.some((candidate) => candidate.id === id)).slice(0, 3);
  if (!candidates.some((candidate) => String(candidate.id) === String(state.selectedFreeAgent || ""))) {
    state.selectedFreeAgent = sortFreeAgencyCandidates(candidates)[0]?.id || null;
  }
  const day = exclusive ? room.re_signing?.day || 1 : room.state?.day || "-";
  const dayCount = exclusive ? room.re_signing?.day_count || 2 : room.state?.day_count || "-";
  const logo = teamLogoSrc(userTeam());
  return `
    <div class="phase-workspace-head unified-free-agency-head">
      <div class="unified-phase-brand">
        ${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(userTeam())} logo" />` : ""}
        <h3>${exclusive ? "Re-Signing" : "Free Agency"}</h3>
      </div>
      <strong class="unified-phase-day">DAY ${escapeHtml(day)} OF ${escapeHtml(dayCount)}</strong>
      <div class="toolbar phase-workspace-controls">
        <button type="button" data-fa-open-trade>Trade Room</button>
        <button type="button" data-fa-open-roster>My Roster</button>
        ${exclusive
          ? `<button id="reSignAdvanceDay">Advance Exclusive Day</button><button id="reSignOpenMarket">Open Free Agency</button>`
          : status !== "completed" ? `<button id="faAdvanceDay">Sim FA Day</button><button id="faAdvanceEnd">Sim To End</button>` : `<button id="faAdvanceStage">Advance To Next Phase</button>`}
      </div>
    </div>
    <div class="phase-free-agency-layout free-agency-single-market">
      ${phaseFreeAgencyMarketCard(room, exclusive)}
      ${freeAgencyIntelligenceRail(room, exclusive)}
    </div>`;
}

function phaseFreeAgencyMarketCard(room, exclusive = false) {
  const candidates = scopedFreeAgencyCandidates(room);
  const compared = state.freeAgentCompareIds.length;
  const compareMode = state.freeAgentCompareMode;
  const compareLabel = !compareMode
    ? "Compare Players"
    : compared >= 2
      ? `Compare Players (${compared})`
      : "Cancel";
  return `<section class="phase-market-panel free-agency-command-market" data-free-agency-market-card>
    <div class="section-head free-agency-market-head">
      <div class="free-agency-market-title-group">
        <h3>Player Market</h3>
        <div class="free-agency-market-scopes" aria-label="Free-agent market view">
          ${[["market", "Market"], ["shortlist", `Shortlist${state.freeAgentShortlistIds.length ? ` ${state.freeAgentShortlistIds.length}` : ""}`], ["offers", `My Offers${(room.user_offers || []).length ? ` ${(room.user_offers || []).length}` : ""}`]].map(([scope, label]) => `<button type="button" data-fa-market-scope="${scope}" class="${state.freeAgentMarketScope === scope ? "is-active" : ""}">${escapeHtml(label)}</button>`).join("")}
        </div>
      </div>
      <div class="free-agency-market-tools">
        <button type="button" data-fa-filter-toggle class="${state.freeAgentFiltersOpen ? "is-active" : ""}">Filter</button>
        <button type="button" data-fa-compare-toggle>${compareLabel}</button>
      </div>
    </div>
    ${state.freeAgentFiltersOpen ? freeAgencyMarketFilterBar(room) : ""}
    ${exclusive ? `<div class="free-agency-exclusive-strip"><strong>Exclusive window</strong><span>No outside bids. Tax room may be exceeded to retain your player; the hard cap remains binding.</span><b>${room.re_signing?.candidate_count || 0} decisions</b></div>` : ""}
    ${freeAgencyMarketTable(candidates, exclusive)}
  </section>`;
}

function freeAgencyMarketFilterBar(room) {
  const filters = state.freeAgentMarketFilters || {};
  const positions = [...new Set((room.candidates || []).map((candidate) => candidate.position).filter(Boolean))].sort();
  return `<div class="free-agency-market-filter-bar">
    <label><span>Player</span><input type="search" data-fa-filter-search value="${escapeAttr(filters.search || "")}" placeholder="Search name" /></label>
    <label><span>Position</span><select data-fa-filter-position><option value="all">All positions</option>${positions.map((position) => `<option value="${escapeAttr(position)}" ${filters.position === position ? "selected" : ""}>${escapeHtml(position)}</option>`).join("")}</select></label>
    <label><span>Minimum OVR</span><input type="number" min="1" max="99" step="1" data-fa-filter-overall value="${escapeAttr(filters.minOverall || "")}" placeholder="Any" /></label>
    <button type="button" data-fa-filter-reset>Reset</button>
  </div>`;
}

function scopedFreeAgencyCandidates(room) {
  const filters = state.freeAgentMarketFilters || {};
  const query = String(filters.search || "").trim().toLowerCase();
  const minimum = Number(filters.minOverall);
  let candidates = (room.candidates || []).filter((candidate) => {
    if (query && !String(candidate.name || "").toLowerCase().includes(query)) return false;
    if (filters.position && filters.position !== "all" && candidate.position !== filters.position) return false;
    if (filters.minOverall !== "" && Number.isFinite(minimum) && Number(candidate.ratings?.overall || 0) < minimum) return false;
    return true;
  });
  if (state.freeAgentMarketScope === "shortlist") {
    const shortlisted = new Set(state.freeAgentShortlistIds.map(String));
    return candidates.filter((candidate) => shortlisted.has(String(candidate.id)));
  }
  if (state.freeAgentMarketScope === "offers") {
    const offered = new Set((room.user_offers || []).map((offer) => String(offer.player_id || offer.id || "")));
    return candidates.filter((candidate) => offered.has(String(candidate.id)));
  }
  return candidates;
}

function freeAgencyMarketTable(candidates, exclusive = false) {
  const identity=[
    ...(state.freeAgentCompareMode?[{key:'compare',label:'',width:18,value:p=>0,cell:p=>`<input class="free-agency-compare-checkbox" type="checkbox" data-fa-compare="${escapeAttr(p.id)}" aria-label="Compare ${escapeAttr(p.name)}" ${state.freeAgentCompareIds.includes(p.id)?'checked':''}>`}]:[]),
    {key:'name',label:'Player',width:130,value:p=>p.name,cell:p=>`<button type="button" data-fa-player-card="${escapeAttr(p.id)}">${escapeHtml(p.name)}</button>`},
    {key:'age',label:'Age',width:25,value:p=>p.age},
    {key:'position',label:'Pos',width:25,value:p=>p.position},
  ];
  const ratings=[['OVR','overall'],['OFF','offense'],['DEF','defense'],['Shot','shooting'],['Cre','creation'],['Pass','passing'],['Reb','rebounding'],['Rim','rim_deterrence'],['Ath','athleticism']].map(([label,key],i)=>({key,label,width:i<3?54:undefined,value:p=>Number(p.ratings?.[key]??(key==='offense'?p.ratings?.overall:0)),cell:p=>i<3?compactRatingBar(p.ratings?.[key]??(key==='offense'?p.ratings?.overall:0)):draftMetric(p.ratings?.[key])}));
  const stats=[['GP','games'],['MPG','previous_mpg'],['PTS','ppg'],['REB','rpg'],['AST','apg'],['STL','spg'],['BLK','bpg'],['TO','topg']].map(([label,key])=>({key,label,value:p=>Number(p[key]||0),cell:p=>draftMetric(p[key])}));
  const contracts=[
    {key:'team_fit_score',label:'Fit',value:p=>Number(p.team_fit_score||0),cell:p=>draftMetric(p.team_fit_score)},
    {key:'ask_millions',label:'Ask',value:p=>Number(p.ask_millions||0),cell:p=>compactMarketMoney(p.ask_millions)},
    {key:'ask_change_millions',label:'Move',value:p=>Number(p.ask_change_millions||0),cell:p=>freeAgencyAskChange(p.ask_change_millions)||'—'},
    {key:'highest_offer',label:exclusive?'Rights':'Leading bid',width:80,value:p=>Number(p.highest_offer?.aav_millions||0),cell:p=>p.highest_offer?`<span class="linked-leading-bid"><img src="${escapeAttr(teamLogoSrc(p.highest_offer.team_abbrev))}" alt="${escapeAttr(p.highest_offer.team_abbrev||'')}">${money(p.highest_offer.aav_millions)} × ${p.highest_offer.years||1}</span>`:(exclusive?'Exclusive':'—')},
    {key:'interest',label:'Interest',width:54,value:p=>Number(p.highest_offer?.interest_score||0),cell:p=>p.highest_offer?compactRatingBar(p.highest_offer.interest_score):'—'},
  ];
  return linkedRosterTables(candidates,[{title:'Ratings',className:'linked-ratings',fields:[...identity,...ratings]},{title:'Previous season',className:'linked-stats',fields:stats},{title:'Offers',className:'linked-contracts',fields:contracts}],'market',state.freeAgentMarketSort||{key:'overall',direction:'desc'});
}

function sortFreeAgencyCandidates(candidates) {
  const sort = state.freeAgentMarketSort || { key: "overall", direction: "desc" };
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...candidates].sort((a, b) => {
    const av = freeAgencySortValue(a, sort.key);
    const bv = freeAgencySortValue(b, sort.key);
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * direction || String(a.name || "").localeCompare(String(b.name || ""));
    return String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" }) * direction;
  });
}

function freeAgencySortValue(player, key) {
  const ratings = player.ratings || {};
  if (key in ratings) return Number(ratings[key] || 0);
  if (key === "production") return Number(player.ppg || 0);
  if (key === "interest") return Number(player.highest_offer?.interest_score || 0);
  if (key === "highest_offer") return Number(player.highest_offer?.aav_millions || 0);
  const value = player[key];
  return typeof value === "number" ? value : String(value || "");
}

function freeAgencyMarketRow(player, exclusive = false) {
  const ratings = player.ratings || {};
  const thresholds = state.data.freeagency?.rating_tertiles || {};
  const checked = state.freeAgentCompareIds.includes(player.id);
  const offer = player.highest_offer;
  const leader = offer ? `<span class="free-agency-leading-offer">${teamLogoSrc(offer.team_abbrev) ? `<img src="${escapeAttr(teamLogoSrc(offer.team_abbrev))}" alt="${escapeAttr(offer.team_abbrev)} logo" />` : ""}<span><strong>${escapeHtml(offer.team_abbrev || "—")} ${money(offer.aav_millions)}</strong><small>${escapeHtml(offer.years || 1)} year${Number(offer.years || 1) === 1 ? "" : "s"}</small></span></span>` : `<span class="free-agency-no-offer">${exclusive ? "Exclusive" : "No bids"}</span>`;
  const selected = String(state.selectedFreeAgent || "") === String(player.id);
  return `<tr class="${selected ? "is-selected" : ""}" data-fa-select="${escapeAttr(player.id)}">
    ${state.freeAgentCompareMode ? `<td class="fa-col-compare"><input class="free-agency-compare-checkbox" type="checkbox" data-fa-compare="${escapeAttr(player.id)}" aria-label="Compare ${escapeAttr(player.name)}" ${checked ? "checked" : ""} /></td>` : ""}
    <td class="fa-col-name"><button type="button" class="free-agent-player-name" data-fa-player-card="${escapeAttr(player.id)}"><strong>${escapeHtml(player.name)}</strong><small>${escapeHtml(player.position || "—")} · ${escapeHtml(player.height || "—")}</small></button></td>
    <td class="fa-col-age free-agency-group-end">${escapeHtml(player.age ?? "—")}</td>
    <td class="fa-col-overall free-agency-group-start">${tieredRating(ratings.overall, "overall", thresholds)}</td><td class="fa-col-offense">${tieredRating(ratings.offense ?? ratings.overall, "overall", thresholds)}</td><td class="fa-col-defense">${tieredRating(ratings.defense, "defense", thresholds)}</td><td class="fa-col-spacing">${tieredRating(ratings.spacing, "range", thresholds)}</td><td class="fa-col-creation">${tieredRating(ratings.creation, "creation", thresholds)}</td><td class="fa-col-rebounding">${tieredRating(ratings.rebounding, "rebounding", thresholds)}</td><td class="fa-col-team_fit_score free-agency-group-end">${draftMetric(player.team_fit_score)}</td>
    <td class="fa-col-production free-agency-group-start">${draftMetric(player.ppg)} / ${draftMetric(player.rpg)} / ${draftMetric(player.apg)}</td>
    <td class="fa-col-ask_millions">${compactMarketMoney(player.ask_millions)}</td><td class="fa-col-ask_change_millions">${freeAgencyAskChange(player.ask_change_millions) || "—"}</td>
    <td class="fa-col-highest_offer">${leader}</td><td class="fa-col-interest">${freeAgencyInterest(player)}</td>
  </tr>`;
}

function freeAgencyInterest(player) {
  const score = Number(player.highest_offer?.interest_score || 0);
  if (!score) return `<span class="free-agency-no-offer">—</span>`;
  const label = score >= 72 ? "High" : score >= 55 ? "Warm" : score >= 38 ? "Open" : "Low";
  return `<span class="free-agency-interest"><i><b style="width:${clampNumber(score, 5, 100)}%"></b></i><em>${label}</em></span>`;
}

function freeAgencyIntelligenceRail(room, exclusive = false) {
  const candidates = room.candidates || [];
  let selected = candidates.find((player) => String(player.id) === String(state.selectedFreeAgent || ""));
  if (!selected) selected = sortFreeAgencyCandidates(candidates)[0];
  if (selected && !state.selectedFreeAgent) state.selectedFreeAgent = selected.id;
  const ratings = selected?.ratings || {};
  const thresholds = room.rating_tertiles || state.data.freeagency?.rating_tertiles || {};
  const bars = [
    ["OFF", ratings.offense ?? ratings.overall, "overall"],
    ["DEF", ratings.defense, "defense"],
    ["SPACE", ratings.spacing, "range"],
    ["CREATE", ratings.creation, "creation"],
    ["REBOUND", ratings.rebounding, "rebounding"],
  ];
  const cap = room.cap || {};
  const selectedOffers = (room.active_offers || [])
    .filter((item) => String(item.player_id || "") === String(selected?.id || ""))
    .sort((left, right) => Number(right.interest_score || 0) - Number(left.interest_score || 0));
  return `<aside class="free-agency-intelligence" data-free-agency-intelligence>
    <section class="market-intelligence-panel selected-player-intelligence">
      <p class="market-intelligence-title">Selected Player</p>
      ${selected ? `<div class="market-selected-head"><strong>${escapeHtml(selected.name)}</strong><span class="market-selected-overall"><small>OVR</small>${tieredRating(ratings.overall, "overall", thresholds)}</span></div>
      <div class="market-rating-bars">${bars.map(([label, value, key]) => `<div><span>${label}</span><i><b style="${performanceBarStyle(Number(value||0))}"></b></i><em>${draftMetric(value)}</em></div>`).join("")}</div>
      <div class="market-intelligence-actions"><button type="button" data-fa-intel-card="${escapeAttr(selected.id)}">Player Card</button><button type="button" class="primary-action" data-fa-intel-offer="${escapeAttr(selected.id)}">Build Offer</button><button type="button" class="market-shortlist-toggle ${state.freeAgentShortlistIds.includes(selected.id) ? "is-active" : ""}" data-fa-shortlist="${escapeAttr(selected.id)}">${state.freeAgentShortlistIds.includes(selected.id) ? "Shortlisted" : "Add to Shortlist"}</button></div>` : `<div class="empty">No players are available.</div>`}
    </section>
    <section class="market-intelligence-panel live-offer-intelligence">
      <p class="market-intelligence-title">Live Offers</p>
      <div class="market-live-offer-scroll">${selectedOffers.length ? selectedOffers.map((offer) => {
        const team = teamLabel(offer.team_id || offer.team_abbrev || "");
        const interest = clampNumber(Number(offer.interest_score || 0), 0, 100);
        return `<div class="market-live-offer">${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)} logo" />` : ""}<strong>${money(offer.aav_millions)} × ${escapeHtml(offer.years || 1)}</strong><span class="market-offer-interest"><i><b style="width:${interest}%"></b></i><em>${Math.round(interest)}</em></span></div>`;
      }).join("") : `<div class="market-no-offers">${exclusive ? "Exclusive rights. No outside bids." : "No active offers for this player."}</div>`}</div>
    </section>
    <section class="market-intelligence-panel signing-wire-intelligence">
      <p class="market-intelligence-title">Signing Wire</p>
      ${freeAgencySigningWire(room.recent_signings || [])}
    </section>
    <section class="market-intelligence-panel cap-intelligence paper-payroll-panel">
      ${freeAgencyCapPosition(room, cap)}
    </section>
    <section class="market-intelligence-panel market-cap-totals"><p class="market-intelligence-title">Cap position</p><div class="market-cap-summary"><span><small>Payroll</small><strong>${money(cap.salary_total_millions)}</strong></span><span><small>Tax room</small><strong>${signedMoney(cap.tax_space_millions)}</strong></span><span><small>Hard cap room</small><strong>${signedMoney(cap.hard_cap_space_millions)}</strong></span></div></section>
  </aside>`;
}

function freeAgencySigningWire(events) {
  const rows = events.slice(0, 5);
  if (!rows.length) return `<div class="market-no-offers">No completed signings yet.</div>`;
  return `<div class="signing-wire-scroll">${rows.map((event) => {
    const details = event.details || {};
    const team = teamLabel((event.team_ids || [])[0] || details.team_id || "");
    const years = Number(details.years || 0);
    const aav = Number(details.aav_millions || 0);
    const playerName = details.player_name || String(event.headline || "Free-agent signing").split(" signs ")[0];
    const total = aav * Math.max(1, years);
    return `<article class="signing-wire-row">${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)} logo" />` : ""}<div><strong>${escapeHtml(playerName)}</strong><span>${aav ? `${escapeHtml(team)} · ${money(aav)} AAV · ${years || 1} yr · ${money(total)} total` : escapeHtml(event.headline || "Contract terms recorded")}</span></div><time>${escapeHtml(String(event.date || "").slice(5))}</time></article>`;
  }).join("")}</div>`;
}

function freeAgencyCapPosition(room, currentCap) {
  const capByYear = state.data.dashboard?.cap_by_year || room.cap_by_year || {};
  const entries = Object.entries(capByYear)
    .sort(([left], [right]) => String(left).localeCompare(String(right)))
    .slice(0, 4);
  const fallbackSeason = String(state.home?.save?.current_season || state.home?.save?.current_date || "Year 1").slice(0, 7);
  const years = entries.length
    ? entries.map(([season, cap]) => ({ season, cap: cap || {} }))
    : [{ season: fallbackSeason, cap: currentCap || {} }];
  while (years.length < 4) {
    years.push({ season: `Year ${years.length + 1}`, cap: {} });
  }
  return `<p class="market-intelligence-title">${gameArtworkTitle("Four-Year Payroll Share", "payroll")}</p>
    ${salaryHorizonChart({seasons:years.map(row=>row.season),rows:rosterRows(state.data.dashboard||{}),capByYear})}`;
}

function shortSeasonLabel(season) {
  const match = String(season || "").match(/(\d{4})-(\d{2,4})/);
  if (!match) return season || "—";
  return `${match[1].slice(-2)}-${match[2].slice(-2)}`;
}

function freeAgencyAskChange(value) {
  const change = Number(value || 0);
  if (!Number.isFinite(change) || Math.abs(change) < 0.05) return "";
  const direction = change > 0 ? "up" : "down";
  const arrow = change > 0 ? "▲" : "▼";
  return `<span class="ask-change ask-change-${direction}" title="${change > 0 ? "Up" : "Down"} ${money(Math.abs(change))} since yesterday"><span class="ask-change-arrows" aria-hidden="true"><i>${arrow}</i><i>${arrow}</i><i>${arrow}</i></span><b>${money(Math.abs(change))}</b></span>`;
}

function rosterCutdownDashboardWorkspace() {
  const room = state.data.cutdown || {};
  const pending = room.pending || {};
  return `
    <div class="phase-workspace-head">
      <div>
        <p class="eyebrow">${escapeHtml(room.date || state.home?.save?.current_date || "")}</p>
        <h3>Mandatory Roster Cutdown</h3>
      </div>
      <div class="dashboard-meta">
        <span>${escapeHtml(teamLabel(room.team || userTeam()))}</span>
        <span>${escapeHtml(room.current_count || 0)} / ${escapeHtml(room.target_count || 15)} players</span>
      </div>
    </div>
    <div class="phase-cutdown-layout">
      <section class="phase-focus-panel cutdown-brief">
        <p class="eyebrow">Before opening night</p>
        <h3>${escapeHtml(pending.cut_required || Math.max(0, Number(room.current_count || 0) - Number(room.target_count || 15)))} move(s) required</h3>
        <p class="muted">Choose which contracts leave the roster. Recent draft picks remain protected from this cutdown.</p>
      </section>
      <section class="phase-board-panel">
        ${table(["Player", "Pos", "Age", "Ht", "MPG", "OVR", "Contract", ""], room.players || [], (row) => [
          row.name,
          compactPos(row.position),
          row.age,
          row.height || "—",
          Number(row.minutes || 0).toFixed(1),
          gradeNumber(row.overall),
          compactSalaryYears(row.salary_by_year),
          row.can_waive
            ? html(`<button data-waive-player="${escapeAttr(row.player_id)}">Waive</button>`)
            : html(`<span class="muted">Protected</span>`),
        ])}
      </section>
    </div>`;
}

function staffRetentionDashboardWorkspace() {
  const room = state.data.staffRetention || {};
  const windowRow = room.window || {};
  const staff = room.staff || {};
  const candidates = room.market?.candidates || [];
  if (room.status !== "required") return `<div class="empty">No staff contract decision is pending.</div>`;
  return `
    <div class="phase-workspace-head">
      <div>
        <p class="eyebrow">${escapeHtml(windowRow.team_abbrev || userTeam())} · ${escapeHtml(rowLabel(windowRow.slot || "staff"))}</p>
        <h3>Staff Contract Decision</h3>
      </div>
      <div class="dashboard-meta">
        <span>Budget ${money(room.budget?.current_spend_millions)} / ${money(room.budget?.annual_budget_millions)}</span>
        <span>Max offer ${money(room.max_offer_millions)}</span>
        <button type="button" class="ui-command" data-dashboard-settings>Settings</button>
      </div>
    </div>
    <div class="phase-staff-retention-layout">
      <section class="phase-focus-panel staff-retention-current">
        <h3>${escapeHtml(staff.name || windowRow.staff_name || "Staff member")}</h3>
        <p class="phase-prospect-name">Grade ${plainNumber(room.staff_grade)}</p>
        <div class="staff-retention-effects">
          ${(room.effect_rows || []).map((effect) => `<div><strong>${escapeHtml(effect.label || effect.name || "Impact")}</strong>${compactRatingBar(effect.value ?? effect.rating)}</div>`).join("")}
        </div>
      </section>
      <section class="phase-offer-panel staff-retention-offer">
        ${sectionHead("Re-sign", `${money(room.ask_millions)} × ${room.ask_years || 2}`)}
        <label>Annual salary<input id="staffRetentionSalary" type="number" min="0.1" max="${escapeAttr(room.max_offer_millions || 0)}" step="0.1" value="${escapeAttr(Math.min(Number(room.ask_millions || 0), Number(room.max_offer_millions || 0)).toFixed(2))}"></label>
        <label>Years<input id="staffRetentionYears" type="number" min="1" max="5" step="1" value="${escapeAttr(room.ask_years || 2)}"></label>
        <div class="toolbar">
          <button id="staffRetentionResign">Submit Offer</button>
          <button id="staffRetentionInterim">Accept Interim</button>
        </div>
      </section>
      <section class="phase-board-panel staff-retention-market">
        ${sectionHead("Available Replacements", rowLabel(windowRow.slot || "staff"))}
        ${candidates.length ? table(["Name","Grade","Contract"],candidates,candidate=>[
          html(`<button type="button" data-retention-candidate="${escapeAttr(candidate.id)}">${escapeHtml(candidate.name || "Candidate")}</button>`),
          html(`<span class="staff-grade-cell"><i><b style="${performanceBarStyle(Number(candidate.grade||0))}"></b></i>${draftMetric(candidate.grade)}</span>`),
          `${money(candidate.asking_salary_millions)} × ${candidate.asking_years || 1}`
        ],"retention-market") : `<div class="empty">No replacements are currently available.</div>`}
      </section>
    </div>`;
}

function wireDashboardPhaseWorkspace(kind) {
  if (kind === "fantasy_draft") {
    document.querySelector(".fantasy-player-table")?.addEventListener("scroll", (event) => {
      state.fantasyBoardScrollTop = event.currentTarget.scrollTop;
    }, { passive: true });
    document.querySelectorAll("[data-fantasy-card]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        rememberFantasyBoardScroll();
        fantasyPlayerCard(button.dataset.fantasyCard || "");
      });
    });
    document.querySelectorAll("[data-fantasy-player]").forEach((row) => {
      row.addEventListener("click", () => {
        rememberFantasyBoardScroll();
        state.selectedFantasyPlayer = row.dataset.fantasyPlayer || "";
        renderDashboard();
      });
    });
    document.querySelectorAll("[data-fantasy-watch]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        fantasyDraftToggleWatchlist(button.dataset.fantasyWatch || "");
      });
    });
    document.getElementById("fantasySearch")?.addEventListener("change", (event) => {
      state.fantasySearch = event.target.value || "";
      state.fantasyBoardScrollTop = 0;
      renderDashboard();
    });
    document.getElementById("fantasyPosition")?.addEventListener("change", (event) => {
      state.fantasyPosition = event.target.value || "all";
      state.fantasyBoardScrollTop = 0;
      renderDashboard();
    });
    document.getElementById("fantasyPick")?.addEventListener("click", fantasyDraftPick);
    document.getElementById("fantasyExitSaves")?.addEventListener("click", returnToSaveSelection);
    document.getElementById("fantasySimOne")?.addEventListener("click", () => fantasyDraftSim("fantasy_draft_sim_one"));
    document.getElementById("fantasyToUser")?.addEventListener("click", () => fantasyDraftSim("fantasy_draft_sim_to_user"));
    document.getElementById("fantasyClockExtension")?.addEventListener("click", fantasyDraftClockExtension);
  }
  if (kind === "playoffs") {
    document.querySelectorAll("[data-playoff-sim]").forEach((button) => button.addEventListener("click", () => playoffSim(button.dataset.playoffSim || "game")));
    document.querySelectorAll("[data-playoff-series]").forEach((button) => {
      button.addEventListener("click", () => openPlayoffSeriesBoxScore(button.dataset.playoffSeries || ""));
    });
    document.querySelector("[data-playoff-leader-stat]")?.addEventListener("change", async (event) => {
      state.playoffLeaderStat = event.currentTarget.value || "points";
      state.data.playoffLeaders = await action("playoff_leaders", {
        ...savePayload(),
        stat: state.playoffLeaderStat,
        limit: 9,
      });
      renderDashboard();
    });
    document.getElementById("playoffAdvanceStage")?.addEventListener("click", playoffAdvanceStage);
  }
  if (kind === "draft") {
    document.getElementById("draftRevealLottery")?.addEventListener("click", draftRevealLottery);
    document.getElementById("draftEnterNight")?.addEventListener("click", draftEnterNight);
    document.getElementById("draftBoardFilter")?.addEventListener("change", (event) => {
      state.draftBoardFilter = event.currentTarget.value || "available";
      renderDashboard();
    });
    document.querySelectorAll("[data-draft-sort]").forEach((button) => button.addEventListener("click", () => {
      const key = button.dataset.draftSort || "rank";
      const current = state.draftBoardSort || { key: "rank", direction: "asc" };
      state.draftBoardSort = {
        key,
        direction: current.key === key && current.direction === "asc" ? "desc" : "asc",
      };
      renderDashboard();
    }));
    document.querySelectorAll("[data-draft-prospect]").forEach((row) => {
      const select = () => {
        state.selectedDraftProspect = row.dataset.draftProspect || "";
        renderDashboard();
      };
      row.addEventListener("click", select);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select();
        }
      });
    });
    document.querySelectorAll("[data-draft-prospect-card]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        draftProspectCard(button.dataset.draftProspectCard || "");
      });
    });
    document.getElementById("draftApply")?.addEventListener("click", draftApplyCurrent);
    document.getElementById("draftSimCurrent")?.addEventListener("click", () => draftSim("draft_sim_current"));
    document.getElementById("draftToUser")?.addEventListener("click", () => draftSim("draft_sim_to_user"));
    document.getElementById("draftAll")?.addEventListener("click", () => draftSim("draft_sim_all"));
    document.getElementById("draftAdvanceStage")?.addEventListener("click", draftAdvanceStage);
    const ledger = document.querySelector("[data-draft-ledger]");
    const currentRow = ledger?.querySelector("[data-current-draft-pick]");
    const currentKey = state.draftSelectionPickKey || "";
    if (ledger && currentRow && state.draftLedgerCenteredKey !== currentKey) {
      state.draftLedgerCenteredKey = currentKey;
      requestAnimationFrame(() => {
        const ledgerRect = ledger.getBoundingClientRect();
        const rowRect = currentRow.getBoundingClientRect();
        ledger.scrollTop = Math.max(
          0,
          ledger.scrollTop + rowRect.top - ledgerRect.top - (ledger.clientHeight - rowRect.height) / 2,
        );
      });
    }
  }
  if (kind === "free_agency") {
    wireFreeAgencyMarket();
    document.getElementById("faAdvanceDay")?.addEventListener("click", () => advanceFreeAgency("day"));
    document.getElementById("faAdvanceEnd")?.addEventListener("click", () => advanceFreeAgency("end"));
    document.getElementById("faAdvanceStage")?.addEventListener("click", freeAgencyAdvanceStage);
    document.getElementById("reSignAdvanceDay")?.addEventListener("click", () => advanceReSigning("day"));
    document.getElementById("reSignOpenMarket")?.addEventListener("click", () => advanceReSigning("open_market"));
  }
  if (kind === "cutdown") {
    document.querySelectorAll("[data-waive-player]").forEach((button) => button.addEventListener("click", async () => {
      const playerId = button.dataset.waivePlayer;
      const player = (state.data.cutdown?.players || []).find((row) => row.player_id === playerId);
      if (!window.confirm(`Waive ${player?.name || "this player"}?`)) return;
      const result = await action("waive_player", { ...savePayload(), player_id: playerId });
      showToast(result.status === "waived" ? `${result.player_name} waived` : (result.reason || result.status), result.status !== "waived");
      await refreshHome();
    }));
  }
  if (kind === "staff_retention") {
    document.getElementById("staffRetentionResign")?.addEventListener("click", () => resolveStaffRetention("re_sign"));
    document.getElementById("staffRetentionInterim")?.addEventListener("click", () => resolveStaffRetention("interim"));
    document.querySelectorAll("[data-retention-candidate]").forEach((button) => {
      button.addEventListener("click", () => replaceExpiringStaff(button.dataset.retentionCandidate));
    });
  }
}

async function fantasyDraftPick() {
  const playerId = state.selectedFantasyPlayer;
  if (!playerId) return;
  const player = (state.data.fantasyDraft?.available_players || []).find((row) => row.player_id === playerId);
  const result = await action("fantasy_draft_pick", {
    ...savePayload(),
    team: userTeam(),
    player_id: playerId,
  });
  state.selectedFantasyPlayer = "";
  showToast(`${player?.name || "Player"} selected${result.ai_picks?.length ? ` · ${result.ai_picks.length} AI pick(s) followed` : ""}`);
  await refreshDashboardAfterPhaseMutation("fantasyDraft", result.room);
}

async function fantasyDraftSim(actionName) {
  showToast(actionName === "fantasy_draft_sim_one" ? "Simulating one selection..." : "Advancing to your pick...");
  const result = await action(actionName, {
    ...savePayload(),
    team: userTeam(),
  });
  state.selectedFantasyPlayer = "";
  showToast(`${result.applied_count || 0} selection(s) completed`);
  await refreshDashboardAfterPhaseMutation("fantasyDraft", result.room);
}

async function fantasyDraftToggleWatchlist(playerId) {
  if (!playerId) return;
  rememberFantasyBoardScroll();
  const result = await action("fantasy_draft_watchlist", {
    ...savePayload(),
    team: userTeam(),
    player_id: playerId,
  });
  state.data.fantasyDraft = result.room;
  showToast(result.watching ? "Added to watchlist" : "Removed from watchlist");
  renderDashboard();
}

async function fantasyDraftClockExtension() {
  const result = await multiplayerRequest("request_clock_extension", {
    expected_revision: state.multiplayer.league?.revision,
    seconds: 45,
  });
  state.multiplayer.league = result.league || result;
  showToast("Fantasy draft clock extended by 45 seconds.");
  renderDashboard();
}

async function resolveStaffRetention(choice) {
  const room = state.data.staffRetention || {};
  const windowId = room.window?.id;
  if (!windowId) return;
  const payload = { ...savePayload(), window_id: windowId, choice };
  if (choice === "re_sign") {
    payload.salary_millions = Number(document.getElementById("staffRetentionSalary")?.value || room.ask_millions || 0);
    payload.years = Number(document.getElementById("staffRetentionYears")?.value || room.ask_years || 2);
  } else if (!window.confirm(`Accept an interim ${rowLabel(room.window?.slot || "staff role")}?`)) {
    return;
  }
  const result = await action("resolve_staff_retention", payload);
  showToast(result.status === "re_signed" || result.status === "applied" ? "Staff role resolved" : rowLabel(result.status), !["re_signed", "applied"].includes(result.status));
  await refreshHome();
}

async function replaceExpiringStaff(candidateId) {
  const room = state.data.staffRetention || {};
  const candidate = (room.market?.candidates || []).find((row) => row.id === candidateId);
  if (!candidate || !room.window) return;
  const negotiation = await action("negotiate_staff", {
    ...savePayload(),
    team: userTeam(),
    staff_id: candidate.id,
    slot: room.window.slot,
    salary_millions: candidate.asking_salary_millions,
    years: candidate.asking_years,
    seed: 7,
  });
  if (!negotiation.negotiation?.accepted) {
    showToast("The replacement declined the offer.", true);
    return;
  }
  const hired = await action("hire_staff", { ...savePayload(), negotiation_id: negotiation.negotiation.id });
  showToast(hired.status === "applied" ? `${candidate.name} hired` : rowLabel(hired.status), hired.status !== "applied");
  await refreshHome();
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

function wireFreeAgentModeToggles(root = els.content) {
  root.querySelectorAll("[data-free-agent-mode-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      state.dashboardFreeAgentMode = state.dashboardFreeAgentMode === "current" ? "upcoming" : "current";
      const card = button.closest(".free-agent-market-card");
      if (!card) return;
      const editable = !card.classList.contains("readonly-card");
      const limit = Number(button.dataset.limit || 5);
      const expanded = button.dataset.expanded === "true";
      card.innerHTML = dashboardFreeAgentMarketCard(editable, limit, expanded);
      const rotator = card.querySelector("[data-market-rotator]");
      if (rotator) setMarketRotatorActive(rotator, 0);
      const select = card.querySelector("[data-market-select]");
      if (select) {
        select.addEventListener("change", () => {
          const localRotator = card.querySelector("[data-market-rotator]");
          if (localRotator) setMarketRotatorActive(localRotator, Number(select.value || 0));
          resetDashboardRotatorProgress();
        });
      }
      wireFreeAgentModeToggles(card);
      resetDashboardRotatorProgress();
    });
  });
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

function tradeRoomModalBody() {
  const user = userTeam();
  const finder = state.tradeTab === "finder";
  const partnerOptions = state.teams
    .filter((team) => team.abbrev !== user)
    .map((team) => `<option value="${escapeAttr(team.abbrev)}" ${team.abbrev === state.tradePartner ? "selected" : ""}>${escapeHtml(team.abbrev)} ${escapeHtml(team.name || "")}</option>`)
    .join("");
  return `
    <div class="trade-room-toolbar">
      <div class="trade-room-mode">
        <span class="trade-room-kicker">Deal desk</span>
        <div class="tabs" aria-label="Trade tools">
          <button data-trade-tab="builder" class="${state.tradeTab === "builder" ? "active" : ""}">Trade Builder</button>
          <button data-trade-tab="finder" class="${state.tradeTab === "finder" ? "active" : ""}">Trade Finder</button>
        </div>
      </div>
      ${finder ? `
        <div class="trade-market-scope">
          <span>Market scope</span>
          <strong>All 29 teams</strong>
        </div>` : `
        <label class="trade-partner-field" for="tradePartner">
          <span>Trade partner</span>
          <select id="tradePartner">${partnerOptions}</select>
        </label>`}
    </div>
    <div id="tradeBody"></div>`;
}

async function openTradeRoomModal(tab = state.tradeTab || "builder", options = {}) {
  state.tradeTab = tab;
  state.tradeFinderTargetTeam = options.targetTeam && teamLabel(options.targetTeam) !== userTeam() ? teamLabel(options.targetTeam) : null;
  syncDefaultPartner();
  await loadTradeAssets();
  if (options.targetPlayerId || options.targetPickId) {
    const side = state.tradeFinderTargetTeam ? "To" : "From";
    state[`selected${side}`] = hydrateTradeSelection([{kind:options.targetPickId ? "pick" : "player",id:options.targetPickId || options.targetPlayerId}], state.data[side === "From" ? "tradeUser" : "tradePartner"]);
  }
  state.modal = {
    kind: "tradeRoom",
    title: "Trade Room",
    subtitle: "",
    body: tradeRoomModalBody(),
  };
  renderModal();
}

function renderTradeRoom() {
  if (state.modal?.kind !== "tradeRoom") return;
  state.modal = {
    ...state.modal,
    body: tradeRoomModalBody(),
  };
  renderModal();
}

function wireTradeRoom() {
  const root = els.modalRoot;
  const partner = root.querySelector("#tradePartner");
  partner?.addEventListener("change", async (event) => {
    state.tradePartner = event.target.value;
    state.selectedTo = [];
    state.tradeCandidate = null;
    await loadTradeAssets();
    renderTradeRoom();
  });
  root.querySelector(".tabs")?.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-trade-tab]");
    if (!button) return;
    state.tradeTab = button.dataset.tradeTab;
    renderTradeRoom();
  });
  if (state.tradeTab === "finder") renderTradeFinder(root);
  else renderTradeBuilder(root);
}

function renderTradeBuilder(root) {
  const body = root.querySelector("#tradeBody");
  if (!body) return;
  const userAssets = state.data.tradeUser || {};
  const partnerAssets = state.data.tradePartner || {};
  body.innerHTML = `
    <div class="trade-builder-layout">
      ${assetColumn(`${userTeam()} assets`, userAssets, "from", userTeam())}
      <section class="trade-deal-desk approved-trade-desk">
        <div class="approved-trade-teams">
          ${tradeTeamHeading(userTeam(), userAssets)}
          <span>⇄</span>
          ${tradeTeamHeading(state.tradePartner, partnerAssets)}
          <button id="clearTrade" class="trade-clear-button">Clear</button>
        </div>
        <div class="trade-selected-packages">
          ${selectedPackage(`${userTeam()} sends`, state.selectedFrom, "from", userTeam())}
          ${selectedPackage(`${state.tradePartner} sends`, state.selectedTo, "to", state.tradePartner)}
        </div>
        ${tradeSegmentedValueBoard(state.tradeCandidate, state.selectedFrom, state.selectedTo, userTeam(), state.tradePartner)}
        ${tradeFourYearImplications(userAssets, partnerAssets, state.selectedFrom, state.selectedTo)}
        <button id="evaluateTrade" class="trade-evaluate-button" ${!state.selectedFrom.length && !state.selectedTo.length ? "disabled" : ""}>Evaluate Package</button>
        <div id="tradeRead">${tradeReadout(state.tradeCandidate)}</div>
      </section>
      ${assetColumn(`${state.tradePartner} assets`, partnerAssets, "to", state.tradePartner)}
    </div>`;
  wireTradeAssetControls(body);
  body.querySelector("#clearTrade").addEventListener("click", () => {
    state.selectedFrom = [];
    state.selectedTo = [];
    state.tradeCandidate = null;
    renderTradeRoom();
  });
  body.querySelector("#evaluateTrade").addEventListener("click", evaluateBuiltTrade);
  const applyButton = body.querySelector("#applyBuiltTrade");
  if (applyButton) applyButton.addEventListener("click", () => applyCandidate(state.tradeCandidate, "builder"));
  body.querySelectorAll("[data-trade-team-roster]").forEach((button) => button.addEventListener("click", () => openTeamRosterCard(button.dataset.tradeTeamRoster)));
}

function tradeTeamHeading(team, payload) {
  const record = payload.record || {};
  const wins = Number(record.wins || 0);
  const losses = Number(record.losses || 0);
  return `<button type="button" class="approved-trade-team" data-trade-team-roster="${escapeAttr(team)}">${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)} logo" />` : ""}<span><strong>${escapeHtml(team)}</strong><small>${wins}-${losses} · ${record.conference_rank ? `#${escapeHtml(record.conference_rank)} conference` : "season record"}</small></span></button>`;
}

function tradeSegmentedValueBoard(candidate, outgoing, incoming, outgoingTeam, incomingTeam) {
  const breakdown = candidate?.value_breakdown || {};
  const normalized = (row, fallback) => row?.asset_details?.length
    ? row.asset_details
    : fallback.map((asset) => ({
        id: asset.id,
        label: asset.label || asset.id,
        adjusted_value: Number(asset.trade_value || 0),
        components: { asset_value: Number(asset.trade_value || 0) },
      }));
  const rows = [
    [outgoingTeam, normalized(breakdown.to_team_receives, outgoing)],
    [incomingTeam, normalized(breakdown.from_team_receives, incoming)],
  ];
  const all = rows.flatMap(([, details]) => details);
  const maximum = Math.max(1, ...all.map((asset) => Math.max(
    Object.values(asset.components || {}).filter((value) => Number(value) > 0).reduce((sum, value) => sum + Number(value), 0),
    Object.values(asset.components || {}).filter((value) => Number(value) < 0).reduce((sum, value) => sum + Math.abs(Number(value)), 0),
  )), ...rows.map(([, details]) => Math.abs(details.reduce((sum, asset) => sum + Number(asset.adjusted_value || 0), 0))));
  const labels = { quality: "Quality", age_upside: "Age + upside", contract: "Contract", scarcity: "Scarcity", playoffs: "Playoffs", health: "Health", fit: "Fit", role: "Role", draft_capital: "Draft capital", swap_value: "Swap value", asset_value: "Asset value" };
  const bar = (components) => {
    const entries = Object.entries(components || {}).filter(([, value]) => Math.abs(Number(value)) >= 0.005);
    const positive = entries.filter(([, value]) => Number(value) > 0);
    const negative = entries.filter(([, value]) => Number(value) < 0).reverse();
    return `<div class="trade-value-diverging"><span class="negative-side">${negative.map(([key, value]) => `<i class="value-${escapeAttr(key)}" style="width:${clampNumber(Math.abs(Number(value)) / maximum * 100, 0, 100)}%" title="${escapeAttr(`${labels[key] || rowLabel(key)} ${Number(value).toFixed(1)}`)}"></i>`).join("")}</span><b></b><span class="positive-side">${positive.map(([key, value]) => `<i class="value-${escapeAttr(key)}" style="width:${clampNumber(Number(value) / maximum * 100, 0, 100)}%" title="${escapeAttr(`${labels[key] || rowLabel(key)} +${Number(value).toFixed(1)}`)}"></i>`).join("")}</span></div>`;
  };
  const componentKeys = [...new Set(all.flatMap((asset) => Object.keys(asset.components || {})))];
  return `<section class="approved-trade-values"><header>Asset Value Breakdown</header>${rows.map(([team, details]) => {
    const net = details.reduce((sum, asset) => sum + Number(asset.adjusted_value || 0), 0);
    return `<div class="trade-value-team"><strong>${escapeHtml(team)} sends</strong>${details.length ? details.map((asset) => `<div class="approved-value-row"><span>${escapeHtml(asset.label || asset.id)}</span>${bar(asset.components)}<em>${Number(asset.adjusted_value || 0).toFixed(1)}</em></div>`).join("") : `<div class="trade-value-empty">No assets selected</div>`}<div class="approved-value-row net"><span>NET</span>${bar({ asset_value: net })}<em>${net.toFixed(1)}</em></div></div>`;
  }).join("")}<footer>${componentKeys.map((key) => `<span class="value-${escapeAttr(key)}">${escapeHtml(labels[key] || rowLabel(key))}</span>`).join("")}</footer></section>`;
}

function tradeCapImpactRows(payload, receives, sends, seasons) {
  const salaryDelta = (season) => receives.reduce((sum, item) => sum + Number(item.salary_by_year?.[season] || 0), 0) - sends.reduce((sum, item) => sum + Number(item.salary_by_year?.[season] || 0), 0);
  return seasons.map((season) => {
    const cap = payload.cap_by_year?.[season] || {};
    const delta = salaryDelta(season);
    return {
      season,
      delta,
      payroll: Number(cap.salary_total_millions || 0) + delta,
      players: (payload.players || []).length + receives.filter((item) => item.kind === "player").length - sends.filter((item) => item.kind === "player").length,
      tax: Number(cap.tax_space_millions || 0) - delta,
      hard: Number(cap.hard_cap_space_millions || 0) - delta,
    };
  });
}

function tradeCapDeltaChart(rows) {
  const maxDelta = Math.max(1, ...rows.map((row) => Math.abs(Number(row.delta || 0))));
  return `<div class="trade-cap-delta-chart">${rows.map((row) => {
    const delta = Number(row.delta || 0);
    const height = clampNumber(Math.abs(delta) / maxDelta * 44, delta ? 5 : 0, 44);
    return `<div class="trade-cap-delta-year"><span>${escapeHtml(shortSeasonLabel(row.season))}</span><div class="trade-cap-delta-track"><b></b>${delta > 0 ? `<i class="salary-added" style="height:${height}%"></i>` : delta < 0 ? `<i class="space-gained" style="height:${height}%"></i>` : ""}</div><strong class="${delta > 0 ? "negative" : delta < 0 ? "positive" : ""}">${delta ? `${delta > 0 ? "+" : "−"}${money(Math.abs(delta))}` : "—"}</strong></div>`;
  }).join("")}<div class="trade-cap-delta-legend"><span class="salary-added">Added salary</span><span class="space-gained">Cap space gained</span></div></div>`;
}

function tradeCapImpactTeam(team, payload, rows) {
  return `<div class="approved-trade-cap-team"><strong>${escapeHtml(team)}</strong>${tradeCapDeltaChart(rows)}<table><thead><tr><th>Year</th><th>Payroll</th><th>Players</th><th>Tax room</th><th>Hard-cap room</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${escapeHtml(shortSeasonLabel(row.season))}</td><td>${money(row.payroll)} <small class="${row.delta > 0 ? "negative" : row.delta < 0 ? "positive" : ""}">${row.delta ? `${row.delta > 0 ? "+" : "−"}${money(Math.abs(row.delta))}` : ""}</small></td><td>${row.players}</td><td class="${row.tax < 0 ? "negative" : "positive"}">${signedMoney(row.tax)}</td><td class="${row.hard < 0 ? "negative" : "positive"}">${signedMoney(row.hard)}</td></tr>`).join("")}</tbody></table></div>`;
}

function tradeFourYearImplications(userPayload, partnerPayload, outgoing, incoming) {
  const seasons = [...new Set([...Object.keys(userPayload.cap_by_year || {}), ...Object.keys(partnerPayload.cap_by_year || {})])].sort().slice(0, 4);
  const teams = [
    [userTeam(), userPayload, tradeCapImpactRows(userPayload, incoming, outgoing, seasons)],
    [state.tradePartner, partnerPayload, tradeCapImpactRows(partnerPayload, outgoing, incoming, seasons)],
  ];
  return `<section class="approved-trade-cap"><header>Four-Year Cap Implications</header><div class="approved-trade-cap-teams">${teams.map(([team, payload, rows]) => tradeCapImpactTeam(team, payload, rows)).join("")}</div></section>`;
}

function assetColumn(title, payload, side, team) {
  const cap = payload.cap || {};
  const allAssets = payload.assets || [];
  const filter = state.tradeAssetFilters?.[side] || "all";
  const assets = allAssets.filter((asset) => {
    if (filter === "all") return true;
    if (filter === "players") return asset.kind === "player";
    if (filter === "picks") return asset.kind === "pick";
    return asset.kind === "pick_swap";
  });
  const maxValue = Math.max(1, ...allAssets.map((asset) => Number(asset.trade_value || 0)));
  return `
    <section class="trade-asset-column" ${teamBrandStyle(team)}>
      <div class="trade-asset-head">
        <div class="trade-team-lockup">
          ${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="" />` : ""}
          <div><span>${escapeHtml(title)}</span><strong>${allAssets.length} tradeable</strong></div>
        </div>
        <select data-asset-filter-side="${escapeAttr(side)}" aria-label="${escapeAttr(title)} filter">
          ${[["all", "All"], ["players", "Players"], ["picks", "Picks"], ["swaps", "Swaps"]].map(([value, label]) => `<option value="${value}" ${filter === value ? "selected" : ""}>${label}</option>`).join("")}
        </select>
      </div>
      ${tradeCapStrip(cap)}
      <div class="trade-asset-list scroll-list">
        ${assets.slice(0, 70).map((asset) => assetButton(asset, side, maxValue, team)).join("") || `<div class="empty">No tradeable assets in this group.</div>`}
      </div>
    </section>`;
}

function assetButton(asset, side, maxValue = 100, team = "") {
  const selected = selectedList(side).some((item) => item.id === asset.id);
  const tradeValue = Number(asset.trade_value || 0);
  const valueWidth = clampNumber((tradeValue / Math.max(1, maxValue)) * 100, 3, 100);
  const meta = asset.kind === "player"
    ? `${asset.position || ""} · age ${asset.age || ""} · ${asset.height || ""}`
    : `${asset.season || ""} · R${asset.round || ""}`;
  const detail = asset.kind === "player"
    ? `${Number(asset.mpg || 0).toFixed(1)} MPG · ${Number(asset.ppg || 0).toFixed(1)} PPG · OVR ${Number(asset.ratings?.overall || 0).toFixed(1)}`
    : asset.label || `${asset.season || ""} R${asset.round || ""}`;
  return `
    <button class="trade-asset-card ${selected ? "selected" : ""}" data-asset-side="${side}" data-asset-kind="${escapeAttr(asset.kind)}" data-asset-id="${escapeAttr(asset.id)}">
      <span class="trade-asset-main">
        <span class="trade-asset-mark">${asset.kind==='player'?(teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="" />` : ""):draftAssetGlyph(asset,true,true)}</span>
        <span class="trade-asset-copy"><strong>${escapeHtml(asset.label || asset.name || asset.id)}</strong><small>${escapeHtml(meta)}</small></span>
        <span class="trade-asset-value"><small>VALUE</small><strong>${tradeValue.toFixed(1)}</strong></span>
      </span>
      <span class="trade-asset-detail">${escapeHtml(detail)}</span>
      <span class="trade-asset-meter"><i style="width:${valueWidth.toFixed(1)}%"></i></span>
    </button>`;
}

function renderTradeFinder(root) {
  const body = root.querySelector("#tradeBody");
  if (!body) return;
  const targetMode = Boolean(state.tradeFinderTargetTeam);
  const finderTeam = targetMode ? state.tradeFinderTargetTeam : userTeam();
  const selection = targetMode ? state.selectedTo : state.selectedFrom;
  const side = targetMode ? "to" : "from";
  const userAssets = state.data[targetMode ? "tradePartner" : "tradeUser"] || {};
  const seasons = Object.keys(userAssets.cap_by_year || {}).sort().slice(0, 4);
  const capRows = tradeCapImpactRows(userAssets, [], selection, seasons);
  body.innerHTML = `
    <div class="trade-finder-layout">
      ${assetColumn(`${finderTeam} market assets`, userAssets, side, finderTeam)}
      <div class="trade-finder-workspace">
        <section class="trade-finder-brief" ${teamBrandStyle(userTeam())}>
          <div class="trade-desk-head"><h3>Trade Finder</h3><strong class="trade-selection-count">${selection.length}/2 selected</strong></div>
          <div class="trade-finder-control-grid">
            ${selectedPackage(targetMode ? "Target Assets" : "Assets To Shop", selection, side, finderTeam)}
            <div class="trade-finder-cap"><header>Cap Impact If Moved</header>${tradeCapDeltaChart(capRows)}</div>
          </div>
          <div class="trade-finder-actions"><button id="runTrade" class="trade-evaluate-button" ${selection.length ? "" : "disabled"}>Find Trades For Selected Assets</button><button id="clearTradeMarket" class="trade-clear-button" ${selection.length || state.tradeResults.length ? "" : "disabled"}>Clear</button></div>
        </section>
        <section class="trade-finder-results">
          <div class="trade-results-head"><h3>Found Trades</h3><strong>${state.tradeResults.length}</strong></div>
          <div id="tradeResults" class="trade-results-list scroll-list">${tradeResultCards(state.tradeResults)}</div>
        </section>
      </div>
    </div>`;
  wireTradeAssetControls(body);
  body.querySelector("#runTrade").addEventListener("click", runTradeSearch);
  body.querySelector("#clearTradeMarket").addEventListener("click", () => {
    state.selectedFrom = [];
    state.selectedTo = [];
    state.tradeResults = [];
    renderTradeRoom();
  });
  body.querySelectorAll("[data-inspect-finder]").forEach((button) => {
    button.addEventListener("click", () => inspectFinderTrade(Number(button.dataset.inspectFinder)));
  });
}

function hydrateTradeSelection(specs, payload) {
  const assets = payload?.assets || [];
  return (specs || []).map((spec) => {
    const id = spec.id || spec.value;
    return assets.find((asset) => asset.kind === spec.kind && (asset.id === id || asset.value === id)) || {
      ...spec,
      id,
      label: spec.label || spec.name || id,
      trade_value: Number(spec.trade_value || 0),
      salary_by_year: spec.salary_by_year || {},
    };
  });
}

async function inspectFinderTrade(index) {
  const candidate = state.tradeResults[index];
  const proposal = candidate?.proposal || {};
  if (!candidate) return;
  const fromTeam = teamLabel(proposal.from_team_id || proposal.from_team || "");
  const toTeam = teamLabel(proposal.to_team_id || proposal.to_team || "");
  const userIsFrom = fromTeam === userTeam();
  state.tradePartner = userIsFrom ? toTeam : fromTeam;
  await loadTradeAssets();
  state.selectedFrom = hydrateTradeSelection(userIsFrom ? proposal.from_assets : proposal.to_assets, state.data.tradeUser);
  state.selectedTo = hydrateTradeSelection(userIsFrom ? proposal.to_assets : proposal.from_assets, state.data.tradePartner);
  state.tradeCandidate = candidate;
  state.tradeTab = "builder";
  renderTradeRoom();
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
  renderTradeRoom();
}

async function runTradeSearch() {
  const selection = state.tradeFinderTargetTeam ? state.selectedTo : state.selectedFrom;
  if (!selection.length) return showToast("Select at least one asset.", true);
  const data = await action("find_trade_for_assets", {
    ...savePayload(),
    seller_team: state.tradeFinderTargetTeam || userTeam(),
    for_team: userTeam(),
    assets: selection.map(assetSpec),
    limit: 8,
    seed: 7,
  });
  state.tradeResults = data.candidates || data.offers || [];
  renderTradeRoom();
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
  if (state.modal?.kind === "tradeRoom") {
    await loadTradeAssets();
    renderTradeRoom();
  }
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
  return `<div class="trade-offers-list">${offers.length ? offers.map((offer, index) => offerCard(offer, index)).join("") : `<div class="trade-offers-empty"><strong>Your desk is clear.</strong><span>No active AI offers to your team.</span></div>`}</div>`;
}

function tradeOffersModalBody(offers) {
  const legal = offers.filter((offer) => (offer.legality?.status || "legal") === "legal").length;
  return `
    <div class="trade-inbox-summary">
      <div><span>Active</span><strong>${offers.length}</strong></div>
      <div><span>Legal now</span><strong>${legal}</strong></div>
      <p>Incoming offers expire with the trade window. Compare value and acceptance before committing.</p>
    </div>
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
  if (dashboardPhaseKind() !== "draft") {
    const draft = state.data.draft || {};
    const rows = sortDraftBoardRows(draftBoardRows(draft.draft_board), state.draftBoardSort);
    els.content.innerHTML = `<section class="section prospect-preview">${sectionHead("Upcoming Prospects", draft.year || "")}${draftProspectBoard(rows)}</section>`;
    els.content.querySelectorAll("[data-draft-sort]").forEach(button => button.addEventListener("click", () => {
      const key = button.dataset.draftSort;
      state.draftBoardSort = {key, direction: state.draftBoardSort.key === key && state.draftBoardSort.direction === "asc" ? "desc" : "asc"};
      renderDraft();
    }));
    els.content.querySelectorAll("[data-draft-prospect-card]").forEach(button => button.addEventListener("click", () => draftProspectCard(button.dataset.draftProspectCard)));
    return;
  }
  els.content.innerHTML = `
    <section class="section draft-standalone-shell">${draftDashboardWorkspace()}</section>`;
  wireDashboardPhaseWorkspace("draft");
}

async function draftApplyCurrent() {
  const result = await action("draft_apply_current", {
    ...savePayload(),
    team: userTeam(),
    seed: 7,
    prospect_id: state.selectedDraftProspect,
  });
  showToast(`Draft pick: ${result.status}`);
  if (result.status === "blocked" && result.notes) showToast(result.notes, true);
  await refreshDashboardAfterPhaseMutation("draft", result.room);
}

async function draftRevealLottery() {
  const result = await action("draft_reveal_lottery", { ...savePayload(), team: userTeam(), seed: 7 });
  if (result.status !== "revealed" || !result.room) {
    showToast(result.notes || "The lottery could not be revealed.", true);
    return;
  }
  state.data.draft = result.room;
  state.draftPresentationStage = "reveal";
  showToast(`${result.room.year || "Draft"} lottery order revealed.`);
  renderDashboard();
}

async function draftEnterNight() {
  const room = await action("draft_room", { ...savePayload(), team: userTeam(), seed: 7 });
  state.data.draft = room;
  state.draftPresentationStage = "draft";
  renderDashboard();
}

async function draftSim(actionName) {
  const result = await action(actionName, { ...savePayload(), team: userTeam(), seed: 7 });
  const appliedCount = Number(result.result?.applied_count ?? (result.status === "applied" ? 1 : 0));
  showToast(`Draft sim: ${appliedCount} pick${appliedCount === 1 ? "" : "s"}`);
  await refreshDashboardAfterPhaseMutation("draft", result.room);
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
  const freeAgencyStatus = String(room.state?.status || "");
  const freeAgencyCompleted = freeAgencyStatus === "completed";
  const freeAgencyOpen = !freeAgencyCompleted && (room.phase === "free_agency" || Boolean(room.state?.day || freeAgencyStatus === "active"));
  const exclusive = room.phase === "re_signing";
  state.freeAgentCompareIds = state.freeAgentCompareIds.filter((id) => candidates.some((candidate) => candidate.id === id)).slice(0, 3);
  els.content.innerHTML = `
    <section class="section standalone-phase-shell standalone-free-agency-shell">
      ${freeAgencyOpen || freeAgencyCompleted
        ? freeAgencyDashboardWorkspace()
        : `<div class="phase-workspace-head unified-free-agency-head"><div class="unified-phase-brand"><h3>Current Free Agents</h3></div><strong class="unified-phase-day">${escapeHtml(rowLabel(room.phase || "regular_season"))}</strong></div><div class="phase-free-agency-layout free-agency-single-market">${phaseFreeAgencyMarketCard(room, exclusive)}${freeAgencyIntelligenceRail(room, exclusive)}</div>`}
    </section>`;
  wireFreeAgencyMarket(els.content, renderFreeAgency);
  wireFreeAgencyIntelligence();
  els.content.querySelector("[data-fa-open-roster]")?.addEventListener("click", () => openTeamRosterCard());
  els.content.querySelector("[data-fa-open-trade]")?.addEventListener("click", () => openTradeRoomModal());
  const day = document.getElementById("faAdvanceDay");
  if (day) day.addEventListener("click", () => advanceFreeAgency("day"));
  const end = document.getElementById("faAdvanceEnd");
  if (end) end.addEventListener("click", () => advanceFreeAgency("end"));
  const advanceStage = document.getElementById("faAdvanceStage");
  if (advanceStage) advanceStage.addEventListener("click", freeAgencyAdvanceStage);
}

function wireFreeAgencyMarket(root = els.content, rerender = renderDashboard) {
  wireLinkedRoster(root.querySelector('[data-linked-scope="market"]'), key=>{
    const current=state.freeAgentMarketSort||{};
    state.freeAgentMarketSort={key,direction:current.key===key&&current.direction==='desc'?'asc':'desc'};
    refreshFreeAgencyMarketCard(root.querySelector('[data-free-agency-market-card]')||root.closest('[data-free-agency-market-card]'),rerender);
  });
  root.querySelector("[data-fa-filter-toggle]")?.addEventListener("click", (event) => {
    state.freeAgentFiltersOpen = !state.freeAgentFiltersOpen;
    refreshFreeAgencyMarketCard(event.currentTarget.closest("[data-free-agency-market-card]"), rerender);
  });
  root.querySelector("[data-fa-filter-reset]")?.addEventListener("click", (event) => {
    state.freeAgentMarketFilters = { search: "", position: "all", minOverall: "" };
    refreshFreeAgencyMarketCard(event.currentTarget.closest("[data-free-agency-market-card]"), rerender);
  });
  const updateMarketFilter = (key, value, source) => {
    state.freeAgentMarketFilters = { ...state.freeAgentMarketFilters, [key]: value };
    refreshFreeAgencyMarketCard(source.closest("[data-free-agency-market-card]"), rerender);
  };
  root.querySelector("[data-fa-filter-search]")?.addEventListener("change", (event) => updateMarketFilter("search", event.currentTarget.value, event.currentTarget));
  root.querySelector("[data-fa-filter-position]")?.addEventListener("change", (event) => updateMarketFilter("position", event.currentTarget.value, event.currentTarget));
  root.querySelector("[data-fa-filter-overall]")?.addEventListener("change", (event) => updateMarketFilter("minOverall", event.currentTarget.value, event.currentTarget));
  root.querySelectorAll("[data-fa-market-scope]").forEach((button) => {
    button.addEventListener("click", () => {
      state.freeAgentMarketScope = button.dataset.faMarketScope || "market";
      refreshFreeAgencyMarketCard(button.closest("[data-free-agency-market-card]"), rerender);
    });
  });
  root.querySelectorAll("[data-fa-market-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.faMarketSort || "overall";
      const current = state.freeAgentMarketSort || {};
      state.freeAgentMarketSort = {
        key,
        direction: current.key === key && current.direction === "desc" ? "asc" : "desc",
      };
      refreshFreeAgencyMarketCard(button.closest("[data-free-agency-market-card]"), rerender);
    });
  });
  root.querySelectorAll("[data-fa-compare]").forEach((checkbox) => {
    checkbox.addEventListener("click", (event) => event.stopPropagation());
    checkbox.addEventListener("change", () => {
      const id = checkbox.dataset.faCompare || "";
      if (checkbox.checked && !state.freeAgentCompareIds.includes(id)) {
        if (state.freeAgentCompareIds.length >= 3) {
          checkbox.checked = false;
          showToast("Compare up to three free agents at a time.", true);
          return;
        }
        state.freeAgentCompareIds.push(id);
      } else if (!checkbox.checked) {
        state.freeAgentCompareIds = state.freeAgentCompareIds.filter((playerId) => playerId !== id);
      }
      refreshFreeAgencyMarketCard(checkbox.closest("[data-free-agency-market-card]"), rerender);
    });
  });
  root.querySelectorAll("[data-fa-player-card]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      freeAgentPlayerCard(button.dataset.faPlayerCard || "");
    });
  });
  root.querySelectorAll("[data-fa-open-negotiation]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      openFreeAgentNegotiation(button.dataset.faOpenNegotiation || "");
    });
  });
  root.querySelectorAll("[data-fa-select]").forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("button, input, select, a")) return;
      state.selectedFreeAgent = row.dataset.faSelect || "";
      root.querySelectorAll("[data-fa-select]").forEach((candidate) => {
        candidate.classList.toggle("is-selected", candidate.dataset.faSelect === row.dataset.faSelect);
      });
      refreshFreeAgencyIntelligence();
    });
  });
  wireFreeAgencyIntelligence(root);
  root.querySelectorAll("[data-fa-open-trade]").forEach((button) => {
    button.addEventListener("click", openTradeRoomModal);
  });
  root.querySelectorAll("[data-fa-open-roster]").forEach((button) => {
    button.addEventListener("click", () => openTeamRosterCard());
  });
  root.querySelector("[data-fa-compare-toggle]")?.addEventListener("click", (event) => {
    if (!state.freeAgentCompareMode) {
      state.freeAgentCompareMode = true;
    } else if (state.freeAgentCompareIds.length >= 2) {
      openFreeAgentComparison();
      return;
    } else {
      state.freeAgentCompareMode = false;
      state.freeAgentCompareIds = [];
    }
    refreshFreeAgencyMarketCard(event.currentTarget.closest("[data-free-agency-market-card]"), rerender);
  });
}

function wireFreeAgencyIntelligence(root = els.content) {
  root.querySelectorAll("[data-fa-intel-card]").forEach((button) => {
    button.addEventListener("click", () => freeAgentPlayerCard(button.dataset.faIntelCard || ""));
  });
  root.querySelectorAll("[data-fa-intel-offer]").forEach((button) => {
    button.addEventListener("click", () => openFreeAgentNegotiation(button.dataset.faIntelOffer || ""));
  });
  root.querySelectorAll("[data-fa-shortlist]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.faShortlist || "";
      if (state.freeAgentShortlistIds.includes(id)) {
        state.freeAgentShortlistIds = state.freeAgentShortlistIds.filter((playerId) => playerId !== id);
      } else if (id) {
        state.freeAgentShortlistIds = [...state.freeAgentShortlistIds, id];
      }
      refreshFreeAgencyIntelligence();
      refreshFreeAgencyMarketCard(els.content.querySelector("[data-free-agency-market-card]"), renderDashboard);
    });
  });
}

function refreshFreeAgencyIntelligence() {
  const current = els.content.querySelector("[data-free-agency-intelligence]");
  if (!current) return;
  const room = state.data.freeagency || {};
  current.outerHTML = freeAgencyIntelligenceRail(room, room.phase === "re_signing");
  wireFreeAgencyIntelligence(els.content.querySelector("[data-free-agency-intelligence]") || els.content);
}

function refreshFreeAgencyMarketCard(card, rerender = renderDashboard) {
  const room = state.data.freeagency || {};
  if (!card) {
    rerender();
    return;
  }
  const scrollTop=card.querySelector('.linked-roster-scroll')?.scrollTop||0;
  card.outerHTML = phaseFreeAgencyMarketCard(room, room.phase === "re_signing");
  const replacement = els.content.querySelector("[data-free-agency-market-card]");
  const scroll=replacement?.querySelector('.linked-roster-scroll');
  if(scroll)scroll.scrollTop=scrollTop;
  wireFreeAgencyMarket(replacement || els.content, rerender);
}

function freeAgencyCandidate(playerId) {
  return (state.data.freeagency?.candidates || []).find((player) => String(player.id) === String(playerId));
}

async function openFreeAgentNegotiation(playerId) {
  const player = freeAgencyCandidate(playerId);
  if (!player) return;
  state.selectedFreeAgent = player.id;
  const exclusive = state.data.freeagency?.phase === "re_signing";
  const detail = await loadPlayerCardDetail(playerId);
  state.modal = {
    kind: "freeAgentNegotiation",
    title: `${exclusive ? "Re-Sign" : "Negotiate With"} ${player.name}`,
    subtitle: `${player.position || "—"} · age ${decimalNumber(player.age)} · ${player.height || "height unavailable"}`,
    detail,
    body: freeAgentNegotiationBody(player, detail, exclusive),
  };
  renderModal();
}

function negotiationEvidence(detail) {
  return `<div class="approved-negotiation-evidence">${[["Health risk", detail?.health_risk, true], ["Upside remaining", detail?.upside_remaining, false], ["Trade value", detail?.trade_value, false]].map(([label, value, inverse]) => {
    const score = inverse ? 100 - Number(value || 0) * 10 : label === "Upside remaining" ? Number(value || 0) * 20 : Number(value || 0);
    return `<div class="${ratingTone(score)}"><span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(score)}"></b></i><strong>${label === "Upside remaining" ? "+" : ""}${draftMetric(value)}${label === "Upside remaining" ? " OVR" : label === "Health risk" ? " / 10" : ""}</strong></div>`;
  }).join("")}</div>`;
}

function freeAgentNegotiationBody(player, detail, exclusive = false) {
  const ratings = player.ratings || detail?.ratings || {};
  const maximum = Math.max(1.9, Number(state.data.freeagency?.cap?.max_offer_aav_millions || 1.9));
  const initial = clampNumber(Number(player.ask_millions || 1.9), 1.9, maximum);
  const capRows = Object.entries(state.data.freeagency?.cap_by_year || {}).sort(([a], [b]) => a.localeCompare(b)).slice(0, 6);
  return `<div class="approved-negotiation">
    <section class="approved-card-panel approved-negotiation-season"><header>Latest Season</header><div>${[["GP", player.games], ["MPG", player.previous_mpg], ["PTS", player.ppg], ["REB", player.rpg], ["AST", player.apg], ["STL", player.spg], ["BLK", player.bpg], ["TO", player.topg], ["FTA", player.fta_per_game], ["FT%", player.ft_pct]].map(([label, value]) => `<span><small>${label}</small><strong>${draftMetric(value)}</strong></span>`).join("")}</div></section>
    <section class="approved-card-panel approved-negotiation-ratings"><header>Complete Ratings</header>${negotiationEvidence(detail)}<div class="approved-rating-rail">${playerCardRatingRows(ratings).map(([label, value, key]) => `<div class="${ratingQuartileTone(value, key, detail?.rating_quartiles)}"><span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(value)}"></b></i><strong>${draftMetric(value)}</strong></div>`).join("")}</div></section>
    <div class="approved-negotiation-work">
      <section class="approved-card-panel approved-ask-offer"><header>Ask / Offer</header><div class="approved-ask-grid"><span><small>Asking price</small><strong>${money(player.ask_millions)} × 4</strong></span><label><small>Your offer · max ${money(maximum)}</small><span class="money-input"><b>$</b><input id="faAav" type="number" min="1.9" max="${maximum.toFixed(1)}" step="0.1" value="${initial.toFixed(1)}"><b>M</b></span></label><label><small>Years</small><input id="faYears" type="number" min="1" max="5" step="1" value="4"></label></div></section>
      <section class="approved-card-panel approved-interest-factors"><header>Interest Breakdown</header><div>${[["Offer vs ask", initial / Math.max(1, Number(player.ask_millions || 1)) * 100], ["Team fit", player.team_fit_score], ["Market position", player.highest_offer?.interest_score || 50], ["Financial room", maximum / Math.max(1, Number(player.ask_millions || 1)) * 70]].map(([label, value]) => `<span><small>${escapeHtml(label)}</small><i><b style="width:${clampNumber(Number(value || 0), 0, 100)}%"></b></i><strong>${Math.round(clampNumber(Number(value || 0), 0, 100))}</strong></span>`).join("")}</div></section>
      <section class="approved-card-panel approved-offer-decision"><header>Player Interest</header><div><i><b data-fa-live-interest style="width:${clampNumber(initial / Math.max(1, Number(player.ask_millions || 1)) * 70, 0, 100)}%"></b></i><strong data-fa-live-interest-value>${Math.round(clampNumber(initial / Math.max(1, Number(player.ask_millions || 1)) * 70, 0, 100))} / 100</strong><button id="submitFaOffer" class="primary-action">${exclusive ? "Offer Re-Signing" : "Submit Offer"}</button></div></section>
      <section class="approved-card-panel approved-offer-cap"><header>Four-Year Cap Impact</header>${approvedOfferCapChart(capRows.slice(0, 4), initial)}</section>
      <section class="approved-card-panel approved-offer-salary"><header>Six-Season Salary + Team Position</header>${approvedOfferSalaryTable(capRows, initial)}</section>
    </div>
  </div>`;
}

function approvedOfferCapChart(capRows, offer) {
  const maximum = Math.max(1, ...capRows.map(([, cap]) => Number(cap.hard_cap_millions || 230))) * 1.05;
  return `<div class="approved-offer-cap-chart">${capRows.map(([season, cap]) => {
    const payroll = Number(cap.salary_total_millions || 0);
    const after = payroll + Number(offer || 0);
    return `<div><span>${escapeHtml(shortSeasonLabel(season))}</span><i><b style="height:${clampNumber(payroll / maximum * 100, 0, 100)}%"></b><strong data-offer-highlight data-cap-maximum="${maximum}" style="height:${clampNumber(Number(offer || 0) / maximum * 100, 0, 100)}%;bottom:${clampNumber(payroll / maximum * 100, 0, 100)}%"></strong><em class="tax-line" style="bottom:${clampNumber(Number(cap.tax_line_millions || 0) / maximum * 100, 0, 100)}%"></em><em class="hard-line" style="bottom:${clampNumber(Number(cap.hard_cap_millions || 0) / maximum * 100, 0, 100)}%"></em></i><small data-offer-payroll data-base-payroll="${payroll}">${money(after)}</small></div>`;
  }).join("")}</div>`;
}

function approvedOfferSalaryTable(capRows, offer) {
  const rows = [...capRows];
  while (rows.length < 6) rows.push([`Year ${rows.length + 1}`, {}]);
  return `<table class="approved-offer-salary-table"><thead><tr><th>Season</th><th>Salary</th><th>Payroll</th><th>Tax room</th><th>Hard-cap room</th></tr></thead><tbody>${rows.slice(0, 6).map(([season, cap]) => `<tr><td>${escapeHtml(shortSeasonLabel(season))}</td><td data-offer-salary>${money(offer)}</td><td data-offer-table-payroll data-base="${Number(cap.salary_total_millions || 0)}">${money(Number(cap.salary_total_millions || 0) + Number(offer || 0))}</td><td data-offer-table-tax data-base="${Number(cap.tax_space_millions || 0)}">${signedMoney(Number(cap.tax_space_millions || 0) - Number(offer || 0))}</td><td data-offer-table-hard data-base="${Number(cap.hard_cap_space_millions || 0)}">${signedMoney(Number(cap.hard_cap_space_millions || 0) - Number(offer || 0))}</td></tr>`).join("")}</tbody></table>`;
}

function freeAgentOfferSummary(player) {
  const offer = player.highest_offer;
  if (!offer) return `<span>${state.data.freeagency?.phase === "re_signing" ? "Exclusive rights · no outside bids" : "No active offers"}</span>`;
  return `<span class="free-agent-modal-leading">${teamLogoSrc(offer.team_abbrev) ? `<img src="${escapeAttr(teamLogoSrc(offer.team_abbrev))}" alt="${escapeAttr(offer.team_abbrev)} logo" />` : ""}${escapeHtml(offer.team_abbrev || "—")} leads at ${money(offer.aav_millions)} x ${escapeHtml(offer.years || 1)}</span>`;
}

function freeAgentPlayerCard(playerId) {
  const player = freeAgencyCandidate(playerId);
  if (!player) return;
  const ratings = player.ratings || {};
  const offenseAxes = [
    ["Shooting", ratings.shooting], ["Spacing", ratings.spacing], ["Creation", ratings.creation],
    ["Passing", ratings.passing], ["Rim pressure", ratings.rim_pressure], ["Portability", ratings.portability],
  ];
  const defenseAxes = [
    ["Defense", ratings.defense], ["Effort", ratings.def_effort], ["Navigation", ratings.screen_nav],
    ["Rim protect", ratings.rim_deterrence], ["Rebound", ratings.rebounding], ["Athleticism", ratings.athleticism],
  ];
  const ratingRows = [
    ["Overall", ratings.overall], ["Shooting", ratings.shooting], ["Release", ratings.release],
    ["Range", ratings.range], ["Shot versatility", ratings.versatility], ["Spacing", ratings.spacing],
    ["Creation", ratings.creation], ["Handle", ratings.handle], ["Passing", ratings.passing],
    ["Rim pressure", ratings.rim_pressure], ["Defense", ratings.defense], ["Defensive effort", ratings.def_effort],
    ["Screen navigation", ratings.screen_nav], ["Rim deterrence", ratings.rim_deterrence],
    ["Rebounding", ratings.rebounding], ["Offensive rebounding", ratings.oreb],
    ["Athleticism", ratings.athleticism], ["Stamina", ratings.stamina], ["Basketball IQ", ratings.iq],
    ["Portability", ratings.portability], ["Playoff translation", ratings.playoff],
  ].filter(([, value]) => value !== undefined && value !== null);
  state.modal = {
    kind: "freeAgentPlayer",
    title: player.name || "Free Agent",
    subtitle: `Free agent · ${player.position || "—"} · age ${decimalNumber(player.age)} · ${player.height || "height unavailable"}`,
    body: `<div class="fantasy-player-card free-agent-player-card">
      <section class="fantasy-card-hero">
        <div class="fantasy-card-number"><span>OVR</span><strong>${plainNumber(ratings.overall)}</strong><small>Free agent</small></div>
        <div class="fantasy-card-outlook dashboard-player-production">
          <p class="eyebrow">Previous-season production</p>
          <h4>${plainNumber(player.ppg)} PPG · ${plainNumber(player.rpg)} RPG · ${plainNumber(player.apg)} APG</h4>
          <div><span><small>Minutes</small><strong>${plainNumber(player.previous_mpg)} MPG</strong></span><span><small>Games</small><strong>${escapeHtml(player.games || 0)} played</strong></span><span><small>Projected role</small><strong>${plainNumber(player.mpg)} MPG</strong></span></div>
          <p>${plainNumber(player.spg)} STL · ${plainNumber(player.bpg)} BLK · ${plainNumber(player.topg)} TO</p>
        </div>
        <div class="fantasy-card-actions dashboard-player-context">
          <span><small>Ask</small><strong>${money(player.ask_millions)}</strong></span>
          <span><small>Team fit</small><strong>${draftMetric(player.team_fit_score)}</strong></span>
          <span><small>Active offers</small><strong>${escapeHtml(player.offer_count || 0)}</strong></span>
          ${freeAgentOfferSummary(player)}
          <button type="button" data-fa-card-negotiate="${escapeAttr(player.id)}">Negotiate</button>
        </div>
      </section>
      <section class="fantasy-card-radars">${fantasyPlayerRadar("Offensive shape", offenseAxes, "offense")}${fantasyPlayerRadar("Defense / physical", defenseAxes, "defense")}</section>
      <section class="fantasy-card-ratings">
        <div class="fantasy-card-section-head"><span>Rating ledger</span><small>same 1-99 presentation scale used across the game</small></div>
        <div class="fantasy-rating-grid">${ratingRows.map(([label, value]) => `<div class="${ratingTone(value)}"><span>${escapeHtml(label)}</span><strong>${plainNumber(value)}</strong><i style="--rating:${clampNumber(Number(value || 0), 0, 99)}%"></i></div>`).join("")}</div>
      </section>
      <section class="fantasy-card-contract free-agent-market-outlook">
        <div class="fantasy-card-section-head"><span>Market outlook</span><small>live bidding context</small></div>
        <div class="draft-outlook-strip"><span><small>Asking AAV</small><strong>${money(player.ask_millions)}</strong></span><span><small>Offers</small><strong>${escapeHtml(player.offer_count || 0)}</strong></span><span><small>Current leader</small><strong>${escapeHtml(player.highest_offer?.team_abbrev || "None")}</strong></span><span><small>Leading AAV</small><strong>${player.highest_offer ? money(player.highest_offer.aav_millions) : "—"}</strong></span></div>
      </section>
    </div>`,
  };
  renderModal();
}

async function loadPlayerCardDetail(playerId) {
  if (!playerId) return null;
  if (!state.playerCardDetails[playerId]) {
    state.playerCardDetails[playerId] = await action("player_card", { ...savePayload(), player_id: playerId });
  }
  return state.playerCardDetails[playerId];
}

function playerCardRatingGroups(ratings = {}, includeOverall = true) {
  const group = (label, rows) => ({label, rows: rows.filter(([, value]) => value !== undefined && value !== null)});
  return [
    group("Offense", [
      ...(includeOverall ? [["Overall", ratings.overall, "overall"]] : []), ["Shooting", ratings.shooting, "shooting"], ["Release", ratings.release, "release"],
      ["Range", ratings.range, "range"], ["Shot versatility", ratings.versatility, "versatility"], ["Spacing", ratings.spacing, "spacing"],
      ["Creation", ratings.creation, "creation"], ["Handle", ratings.handle, "handle"], ["Passing", ratings.passing, "passing"],
      ["Rim pressure", ratings.rim_pressure, "rim_pressure"],
    ]),
    group("Defense", [
      ["Defense", ratings.defense, "defense"], ["Defensive effort", ratings.def_effort, "def_effort"],
      ["Screen navigation", ratings.screen_nav, "screen_nav"], ["Steal", ratings.steal, "steal"],
      ["Block", ratings.block, "block"], ["Rim deterrence", ratings.rim_deterrence, "rim_deterrence"],
    ]),
    group("Rebounding", [
      ["Rebounding", ratings.rebounding, "rebounding"], ["Offensive rebounding", ratings.oreb, "oreb"],
    ]),
    group("Mental and Physical", [
      ["Athleticism", ratings.athleticism, "athleticism"], ["Lateral agility", ratings.lateral_agility, "lateral_agility"],
      ["Stamina", ratings.stamina, "stamina"], ["Basketball IQ", ratings.iq, "iq"], ["Scheme IQ", ratings.scheme_iq, "scheme_iq"],
    ]),
    group("Coach Perspective", [
      ["Portability", ratings.portability, "portability"], ["Playoff translation", ratings.playoff, "playoff"],
    ]),
  ].filter(item => item.rows.length);
}

function playerCardRatingRows(ratings = {}) {
  return playerCardRatingGroups(ratings).flatMap(group => group.rows);
}

function playerCardRatingBar(label, value, key, detail = {}) {
  const score = clampNumber(Number(value || 0), 0, 99);
  const average = clampNumber(Number(detail.rating_league_averages?.[key] ?? 50), 0, 99);
  return `<div class="${ratingQuartileTone(value, key, detail.rating_quartiles)}"><span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(score)}"></b><em class="rating-average-marker" style="left:${average}%" title="League average: ${average.toFixed(1)}" aria-label="League average ${average.toFixed(1)}"></em></i><strong>${draftMetric(value)}</strong></div>`;
}

function ratingQuartileTone(value, key, thresholds = {}) {
  const score = Number(value);
  const bands = thresholds?.[key] || {};
  if (!Number.isFinite(score) || !Number.isFinite(Number(bands.lower))) return ratingTone(value);
  if (score >= Number(bands.upper)) return "elite";
  if (score >= Number(bands.middle)) return "strong";
  if (score >= Number(bands.lower)) return "average";
  return "weak";
}

function playerEvidenceRing(label, value, maximum, color, suffix = "") {
  const progress = clampNumber(Number(value || 0) / Math.max(0.01, maximum), 0, 1);
  const circumference = 100.53;
  return `<div class="player-evidence-ring" aria-label="${escapeAttr(`${label}: ${draftMetric(value)}${suffix}`)}">
    <span><svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="16"></circle><circle cx="20" cy="20" r="16" style="stroke:${escapeAttr(color)};stroke-dasharray:${circumference};stroke-dashoffset:${circumference * (1 - progress)}"></circle></svg><strong>${draftMetric(value)}</strong></span>
    <div><b>${escapeHtml(label)}</b><small>${escapeHtml(suffix)}</small></div>
  </div>`;
}

function playerCardEvidence(detail) {
  const health = clampNumber(Number(detail.health_risk || 0), 0, 10);
  const upside = clampNumber(Number(detail.upside_remaining || 0), 0, 5);
  const healthColor = health >= 7 ? "#e04d55" : health >= 4 ? "#bd5b5d" : "#8e6263";
  const upsideColor = upside >= 3.5 ? "#2fc77a" : upside >= 1.5 ? "#4e9c70" : "#687c70";
  return `<div class="approved-player-evidence"><div class="player-evidence-rings">${playerEvidenceRing("Health risk", health, 10, healthColor, "/10")}${playerEvidenceRing("Upside", upside, 5, upsideColor, "OVR remaining")}${playerEvidenceRing("Trade Value", detail.trade_value, 100, "#668ea7")}</div></div>`;
}

function gameArtwork(category, extraClass = "") {
  const subjects = {shooting: "Stephen Curry shooting", rebounding: "Dennis Rodman rebounding", "trade-builder": "Trade builder", "trade-finder": "Trade finder", defense: "Kawhi Leonard defending", mentality: "Kobe Bryant", coach: "Gregg Popovich", prospects: "Victor Wembanyama and Adam Silver on draft night", staff: "Coaching clipboard", awards: "Basketball trophy", payroll: "Cash bundles", availability: "Stopwatch and medical cross"};
  if (!subjects[category]) return "";
  return `<span class="game-artwork ${escapeAttr(extraClass)}" data-artwork="${category}" aria-hidden="true" title="${escapeAttr(subjects[category])} artwork"><img class="game-artwork-light" src="/assets/game-art/${category}-silver.webp" alt="" decoding="async" draggable="false"><img class="game-artwork-dark" src="/assets/game-art/${category}-ink.webp" alt="" decoding="async" draggable="false"></span>`;
}

function gameArtworkTitle(title, category) {
  return `<span class="illustrated-panel-title">${gameArtwork(category, "panel-heading-art")}<span>${escapeHtml(title)}</span></span>`;
}

function playerCardGroupedRatings(ratings, detail) {
  const groups = playerCardRatingGroups(ratings, false);
  const columns = [
    [groups.find(group => group.label === "Offense"), groups.find(group => group.label === "Rebounding")],
    [groups.find(group => group.label === "Defense"), groups.find(group => group.label === "Mental and Physical"), groups.find(group => group.label === "Coach Perspective")],
  ];
  const categoryArt = {Offense: "shooting", Rebounding: "rebounding", Defense: "defense", "Mental and Physical": "mentality", "Coach Perspective": "coach"};
  return `<div class="approved-rating-groups">${columns.map(column => `<div class="approved-rating-column">${column.filter(Boolean).map(group => `<section style="--rating-rows:${group.rows.length}"><h4 class="illustrated-rating-heading"><span>${escapeHtml(group.label)}</span>${gameArtwork(categoryArt[group.label], "rating-category-art")}</h4><div class="approved-rating-rail">${group.rows.map(([label, value, key]) => playerCardRatingBar(label, value, key, detail)).join("")}</div></section>`).join("")}</div>`).join("")}</div>`;
}

function approvedCapShareChart(detail, options = {}) {
  const years = (detail.salary_seasons || []).slice(0, 4);
  while (years.length < 4) years.push({ season: `Year ${years.length + 1}`, salary_millions: null });
  const playerId=String(detail.player?.id||detail.player_id||'player-focus');
  const salaryByYear=Object.fromEntries(years.map(row=>[row.season,Number(row.salary_millions||0)]));
  return salaryHorizonChart({seasons:years.map(row=>row.season),rows:[{id:playerId,salary_by_year:salaryByYear}],capByYear:detail.cap_by_year||{},highlightPlayerId:playerId,offer:Boolean(options.offer),className:'approved-cap-share'});
}

function approvedSalaryLedger(detail) {
  const rows = [...(detail.salary_seasons || [])].slice(0, 6);
  while (rows.length < 6) rows.push({ season: `Year ${rows.length + 1}`, salary_millions: null });
  return `<div class="approved-salary-ledger">${rows.map((row) => `<div><span>${escapeHtml(shortSeasonLabel(row.season))}</span><strong>${Number(row.salary_millions || 0) ? money(row.salary_millions) : "—"}</strong></div>`).join("")}</div>`;
}

function approvedRecentGames(detail) {
  const rows = [...(detail.recent_games || [])].slice(-5).reverse();
  while (rows.length < 5) rows.push(null);
  return `<div class="approved-recent-games">${rows.map((row) => row ? `<div><span>${escapeHtml(String(row.date || "").slice(5))}</span><strong>${escapeHtml(row.points ?? 0)} PTS</strong><span>${escapeHtml(row.rebounds ?? 0)} REB</span><span>${escapeHtml(row.assists ?? 0)} AST</span><em>${draftMetric(row.game_score)} GS</em></div>` : `<div class="is-empty"><span>—</span><strong>—</strong><span>—</span><span>—</span><em>—</em></div>`).join("")}</div>`;
}

function approvedGameScoreChart(detail) {
  const rows = detail.recent_games || [];
  const gamesPlayed = Math.max(0, Number(detail.season?.games ?? rows.length) || 0);
  const pointCount = Math.min(30, gamesPlayed);
  const points = (pointCount ? rows.slice(-pointCount) : []).map((row) => ({ label: String(row.date || "").slice(5), value: Number(row.game_score || 0) }));
  if (!points.length) return `<div class="approved-game-score-chart"><div class="empty">No game-score history yet.</div></div>`;
  const width = 420;
  const height = 150;
  const padX = 34;
  const padY = 12;
  // Keep a single league-wide reference scale so a player's chart is comparable to every other card.
  const min = -10;
  const max = 60;
  const values = points.map((point) => point.value);
  const span = max - min;
  const coords = points.map((point, index) => ({
    ...point,
    x: padX + (index / 29) * (width - padX * 2),
    y: height - padY - ((Math.max(min, Math.min(max, point.value)) - min) / span) * (height - padY * 2),
  }));
  const trend = values[values.length - 1] - values[0];
  const tone = trend > 0.15 ? "positive" : trend < -0.15 ? "negative" : "neutral";
  const verticalGrid = Array.from({ length: 13 }, (_, index) => {
    const x = padX + index / 12 * (width - padX - 8);
    return `<line class="grid" x1="${x.toFixed(1)}" y1="${padY}" x2="${x.toFixed(1)}" y2="${height - padY}"></line><line class="axis-notch" x1="${x.toFixed(1)}" y1="${height - padY}" x2="${x.toFixed(1)}" y2="${height - padY + 4}"></line>`;
  }).join("");
  const horizontalGrid = Array.from({ length: 8 }, (_, index) => {
    const value = max - index * 10;
    const y = padY + index / 7 * (height - padY * 2);
    return `<line class="grid${value === 0 ? ' zero' : ''}" x1="${padX}" y1="${y.toFixed(1)}" x2="${width - 8}" y2="${y.toFixed(1)}"></line><line class="axis-notch" x1="${padX - 3}" y1="${y.toFixed(1)}" x2="${padX}" y2="${y.toFixed(1)}"></line><text class="axis-label" x="${padX - 5}" y="${y.toFixed(1)}">${value}</text>`;
  }).join("");
  return `<div class="approved-game-score-chart"><svg class="player-game-score-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Game score over the last 30 games on a shared league-wide scale from minus 10 to 60">${verticalGrid}${horizontalGrid}<polyline class="${tone}" points="${coords.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ")}"><title>${escapeHtml(`Game score from ${points[0].label} to ${points[points.length - 1].label}`)}</title></polyline>${coords.map((point) => `<circle class="chart-node ${tone}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="1.8"><title>${escapeHtml(point.label)}: ${point.value.toFixed(1)}</title></circle>`).join("")}</svg></div>`;
}

function approvedPlayerCardBody(detail, options = {}) {
  const ratings = detail.ratings || options.ratings || {};
  const season = detail.season || {};
  return `<div class="approved-player-card">
    <section class="approved-player-identity"><div class="approved-player-profile-head"><div><h3>${escapeHtml(detail.name || options.name || "Player")}</h3><p>${escapeHtml([detail.position, detail.age ? `${detail.age} years` : "", detail.height].filter(Boolean).join(" · "))}</p></div><div class="approved-player-overall"><span>Overall</span><strong>${draftMetric(ratings.overall)}</strong></div></div>${playerCardEvidence(detail)}${options.actions || ""}<div class="approved-player-identity-ratings" aria-label="Complete ratings">${playerCardGroupedRatings(ratings, detail)}</div></section>
    <div class="approved-player-middle">
      <section class="approved-card-panel approved-player-spatial"><header>Court Influence</header>${spatialHeatmapMarkup(detail.spatial_profile)}</section>
      <section class="approved-card-panel approved-season-line"><header>Most Recent Season</header><div>${[["GP", season.games], ["MPG", season.mpg], ["PTS", season.ppg], ["REB", season.rpg], ["AST", season.apg], ["STL", season.spg], ["BLK", season.bpg], ["TO", season.topg], ["FTA", season.fta_per_game], ["FT%", season.ft_pct]].map(([label, value]) => `<span><small>${label}</small><strong>${draftMetric(value)}</strong></span>`).join("")}</div></section>
      <section class="approved-card-panel approved-game-score"><header>Last 30 Games · Game Score</header>${approvedGameScoreChart(detail)}</section>
    </div>
    <div class="approved-player-right">
      <section class="approved-card-panel approved-cap-panel"><header>${gameArtworkTitle("Four-Year Payroll Share", "payroll")}</header>${approvedCapShareChart(detail)}</section>
      <section class="approved-card-panel approved-recent-panel"><header>Last Five Games</header>${approvedRecentGames(detail)}</section>
    </div>
  </div>`;
}

async function dashboardPlayerCard(playerId) {
  const player = rosterRows(state.data.dashboard || {}).find((row) => String(row.id) === String(playerId));
  const detail = await loadPlayerCardDetail(playerId);
  if (!detail) return;
  state.modal = {
    kind: "dashboardPlayer",
    title: "Player Card",
    subtitle: "",
    body: approvedPlayerCardBody(detail, { name: player?.name, ratings: player?.display_ratings || player?.ratings }),
  };
  renderModal();
}

async function freeAgentPlayerCard(playerId) {
  const player = freeAgencyCandidate(playerId);
  if (!player) return;
  const detail = await loadPlayerCardDetail(playerId);
  if (!detail) return;
  state.modal = {
    kind: "freeAgentPlayer",
    title: "Player Card",
    subtitle: "",
    body: approvedPlayerCardBody(
      { ...detail, ratings: player.ratings || detail.ratings, name: player.name },
      { actions: `<button type="button" class="approved-player-primary-action" data-fa-card-negotiate="${escapeAttr(player.id)}">Build Offer</button>` },
    ),
  };
  renderModal();
}

function openFreeAgentComparison() {
  const players = state.freeAgentCompareIds.map(freeAgencyCandidate).filter(Boolean).slice(0, 3);
  if (players.length < 2) {
    showToast("Select at least two free agents to compare.", true);
    return;
  }
  const ratingFields = [
    ["OVR", "overall"], ["Shooting", "shooting"], ["Spacing", "spacing"], ["Creation", "creation"],
    ["Passing", "passing"], ["Defense", "defense"], ["Rebounding", "rebounding"],
    ["Rim protection", "rim_deterrence"], ["Athleticism", "athleticism"], ["Basketball IQ", "iq"],
  ];
  state.modal = {
    kind: "freeAgentComparison",
    title: "Compare Free Agents",
    subtitle: `${players.length} players · previous-season production and live market context`,
    body: `<div class="free-agent-comparison" style="--comparison-count:${players.length}">${players.map((player) => `<article class="free-agent-comparison-column">
      <header><button type="button" data-fa-comparison-card="${escapeAttr(player.id)}">${escapeHtml(player.name)}</button><span>${escapeHtml(player.position || "—")} · age ${escapeHtml(player.age ?? "—")} · ${escapeHtml(player.height || "—")}</span></header>
      <div class="free-agent-comparison-overview"><strong>${draftMetric(player.ratings?.overall)}</strong><span>OVR</span><b>${money(player.ask_millions)} ask</b></div>
      <div class="free-agent-comparison-market"><span>${escapeHtml(player.offer_count || 0)} active offer${Number(player.offer_count || 0) === 1 ? "" : "s"}</span>${freeAgentOfferSummary(player)}</div>
      <div class="free-agent-comparison-stats"><span><small>GP</small><b>${escapeHtml(player.games || 0)}</b></span><span><small>MPG</small><b>${draftMetric(player.previous_mpg)}</b></span><span><small>PTS</small><b>${draftMetric(player.ppg)}</b></span><span><small>REB</small><b>${draftMetric(player.rpg)}</b></span><span><small>AST</small><b>${draftMetric(player.apg)}</b></span><span><small>STL</small><b>${draftMetric(player.spg)}</b></span><span><small>BLK</small><b>${draftMetric(player.bpg)}</b></span><span><small>TO</small><b>${draftMetric(player.topg)}</b></span></div>
      <div class="free-agent-comparison-ratings">${ratingFields.map(([label, key]) => `<div><span>${escapeHtml(label)}</span><i><b style="width:${clampNumber(Number(player.ratings?.[key] || 0), 0, 99)}%"></b></i><strong>${draftMetric(player.ratings?.[key])}</strong></div>`).join("")}</div>
      <button type="button" class="free-agency-negotiate-button" data-fa-comparison-negotiate="${escapeAttr(player.id)}">Negotiate</button>
    </article>`).join("")}</div>`,
  };
  renderModal();
}

async function submitFreeAgentOffer() {
  const player = state.selectedFreeAgent;
  const years = Number(document.getElementById("faYears")?.value || 1);
  const aavInput = document.getElementById("faAav");
  const maximum = Number(aavInput?.max || 0);
  const aav = Math.min(Number(aavInput?.value || 0), Number.isFinite(maximum) && maximum > 0 ? maximum : Infinity);
  if (aavInput && Number.isFinite(aav)) aavInput.value = aav.toFixed(1);
  if (!player || !aav) {
    showToast("Choose a player and enter a legal offer.", true);
    return;
  }
  const exclusive = state.data.freeagency?.phase === "re_signing";
  const result = await action("submit_free_agent_offer", { ...savePayload(), player_id: player, team: userTeam(), years, aav_millions: aav, allow_tax_exceed: exclusive, auto_apply: true, seed: 7 });
  showToast(result.apply_result ? `${exclusive ? "Re-signing" : "Signing"} ${result.apply_result.status}` : (result.reason || `Offer ${result.status}`), result.status === "blocked");
  if (result.status === "blocked") return;
  closeModal();
  const room = await action("free_agency_room", { ...savePayload(), team: userTeam(), seed: 7 });
  await refreshDashboardAfterPhaseMutation("freeagency", room);
}

async function advanceReSigning(mode) {
  const result = await action("advance_re_signing", { ...savePayload(), team: userTeam(), mode, seed: 7 });
  showToast(result.status === "open_market" ? "Open free agency has begun" : result.status === "advanced_day" ? "Exclusive window advanced" : (result.reason || result.status), result.status === "blocked");
  await refreshDashboardAfterPhaseMutation("freeagency", result.room);
}

async function advanceFreeAgency(mode) {
  const result = await action("advance_free_agency", { ...savePayload(), team: userTeam(), mode, seed: 7 });
  showToast(`Free agency advanced: ${result.status}`);
  await refreshDashboardAfterPhaseMutation("freeagency", result.room);
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
  const market = [...(room.market?.candidates || [])].sort((a,b)=>Number(b.grade||0)-Number(a.grade||0));
  els.content.innerHTML = `
    <div class="staff-workspace">
      <section class="section featured">
        <div class="section-head"><h3>Coaching Staff</h3><span>${money(report.budget?.annual_spend_millions)} / ${money(report.budget?.annual_budget_millions)}</span><span class="pill">${signedMoney(report.budget?.available_millions)} available</span></div>
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
        ${table(["Name", "Role", "Grade", "Specialty", "Asking salary", "Years", ""], market, (candidate) => [candidate.name, rowLabel(candidate.slot), html(`<span class="staff-grade-cell"><i><b style="${performanceBarStyle(Number(candidate.grade||0))}"></b></i>${draftMetric(candidate.grade)}</span>`), candidate.archetype || "—", money(candidate.asking_salary_millions), candidate.asking_years || 2, html(`<button type="button" data-staff-id="${escapeAttr(candidate.id)}">Negotiate</button>`)], "staff-market")}
      </section>
    </div>`;
  document.getElementById("staffSlot").addEventListener("change", async (event) => {
    state.staffSlot = event.target.value;
    state.data.staff = await action("staff_room", { ...savePayload(), team: userTeam(), slot: state.staffSlot || undefined, limit: 30 });
    renderStaff();
  });
  els.content.querySelectorAll("[data-staff-id]").forEach((button) => {
    button.addEventListener("click", () => openDashboardStaffNegotiation(button.dataset.staffId));
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

function dashboardStaffCandidate(staffId) {
  return marketCandidates(state.data.staff?.market).find((candidate) => String(candidate.id || "") === String(staffId || ""));
}

function dashboardCurrentStaff(slot) {
  const dashStaff = staffRows(state.data.dashboard || {});
  const roomStaff = state.data.staff?.team_report?.gameplay_staff_slots || [];
  return [...roomStaff, ...dashStaff].find((staff) => String(staff.slot || staff.role || "") === String(slot || "")) || null;
}

function openDashboardStaffNegotiation(staffId) {
  const candidate = dashboardStaffCandidate(staffId);
  if (!candidate) return showToast("That staff candidate is no longer available.", true);
  const slot = String(candidate.slot || candidate.role_preference || "");
  const current = dashboardCurrentStaff(slot);
  const budget = state.data.staff?.team_report?.budget || state.data.dashboard?.staff_budget || {};
  const currentSalary = staffAav(current || {});
  const spend = Number(budget.annual_spend_millions ?? staffBudgetSummary(staffRows(state.data.dashboard || {})).used ?? 0);
  const maxBudget = Number(budget.annual_budget_millions ?? staffBudgetSummary(staffRows(state.data.dashboard || {})).max ?? 0);
  const maxOffer = Math.max(0, maxBudget - Math.max(0, spend - currentSalary));
  const askingSalary = Number(candidate.asking_salary_millions || staffAav(candidate) || 0);
  const askingYears = Number(candidate.asking_years || staffYears(candidate) || 1);
  const initialOffer = Math.min(askingSalary, maxOffer);
  const upgrade = Number(staffGrade(candidate) || 0) - Number(staffGrade(current || {}) || 0);

  state.modal = {
    kind: "staffNegotiation",
    title: `Negotiate with ${staffName(candidate)}`,
    subtitle: rowLabel(slot),
    staffId: String(candidate.id || ""),
    slot,
    maxOffer,
    body: `<div class="staff-negotiation-grid">
      <section class="staff-negotiation-person current">
        <p class="eyebrow">Current ${escapeHtml(rowLabel(slot))}</p>
        <strong>${escapeHtml(staffName(current || {}))}</strong>
        <dl><div><dt>Grade</dt><dd>${Number(staffGrade(current || {}) || 0).toFixed(1)}</dd></div><div><dt>Salary</dt><dd>${money(currentSalary)}</dd></div></dl>
      </section>
      <div class="staff-replacement-arrow" aria-hidden="true">→</div>
      <section class="staff-negotiation-person candidate">
        <p class="eyebrow">Available candidate</p>
        <strong>${escapeHtml(staffName(candidate))}</strong>
        <dl><div><dt>Grade</dt><dd>${Number(staffGrade(candidate) || 0).toFixed(1)}</dd></div><div><dt>Change</dt><dd class="${upgrade >= 0 ? "positive" : "negative"}">${upgrade >= 0 ? "+" : ""}${upgrade.toFixed(1)}</dd></div></dl>
      </section>
    </div>
    <section class="staff-budget-check">
      <div><span>Current staff spend</span><strong>${money(spend)}</strong></div>
      <div><span>Staff budget</span><strong>${money(maxBudget)}</strong></div>
      <div><span>Maximum legal offer</span><strong>${money(maxOffer)}</strong></div>
    </section>
    <form class="staff-negotiation-form" data-staff-negotiation-form>
      <label>Annual salary
        <div class="money-input"><span>$</span><input type="number" min="0.1" max="${maxOffer.toFixed(1)}" step="0.1" value="${initialOffer.toFixed(1)}" data-staff-offer-salary required><span>M</span></div>
      </label>
      <label>Years
        <input type="number" min="1" max="5" step="1" value="${Math.max(1, Math.min(5, askingYears))}" data-staff-offer-years required>
      </label>
      <div class="staff-ask-read"><span>Candidate ask</span><strong>${money(askingSalary)} x ${askingYears}</strong></div>
      ${askingSalary > maxOffer + 0.001 ? `<p class="staff-budget-warning">This candidate's ask exceeds your maximum legal offer. You may negotiate below the ask, but the candidate can decline.</p>` : ""}
      <button type="submit" class="staff-hire-confirm" ${maxOffer < 0.1 ? "disabled" : ""}>Offer &amp; Replace ${escapeHtml(staffName(current || {}))}</button>
    </form>`,
  };
  renderModal();
}

async function submitDashboardStaffNegotiation() {
  const modal = state.modal;
  if (!modal || modal.kind !== "staffNegotiation") return;
  const salaryInput = els.modalRoot.querySelector("[data-staff-offer-salary]");
  const yearsInput = els.modalRoot.querySelector("[data-staff-offer-years]");
  const maxOffer = Number(modal.maxOffer || 0);
  const salary = Math.min(maxOffer, Math.max(0.1, Number(salaryInput?.value || 0)));
  const years = Math.max(1, Math.min(5, Number(yearsInput?.value || 1)));
  if (salary > maxOffer + 0.001 || maxOffer < 0.1) return showToast("That offer exceeds the available staff budget.", true);
  try {
    const result = await action("negotiate_staff", {
      ...savePayload(),
      team: userTeam(),
      staff_id: modal.staffId,
      slot: modal.slot,
      salary_millions: salary,
      years,
      seed: 7,
    });
    const negotiation = result.negotiation || {};
    if (!negotiation.accepted) {
      showToast(negotiation.decision === "reject_budget" ? "Offer blocked by the staff budget." : "The candidate declined the offer.", true);
      return;
    }
    const hired = await action("hire_staff", { ...savePayload(), negotiation_id: negotiation.id });
    if (hired.status !== "applied") return showToast("The staff replacement could not be completed.", true);
    closeModal();
    showToast(`${staffName(negotiation.candidate || {})} hired as ${rowLabel(modal.slot)}.`);
    await refreshHome();
  } catch (error) {
    showToast(error.message || "Staff negotiation failed.", true);
  }
}

async function fireDashboardStaff(slot, name) {
  if (!window.confirm(`Fire ${name}? An interim ${rowLabel(slot)} will take over immediately.`)) return;
  try {
    const result = await action("fire_staff", { ...savePayload(), team: userTeam(), slot, reason: "user decision" });
    showToast(result.status === "applied" ? `${name} fired. An interim has been appointed.` : `Staff move: ${result.status}`);
    await refreshHome();
  } catch (error) {
    showToast(error.message || "Staff firing failed.", true);
  }
}

function staffDashboardCard(rows, dash, editable = true) {
  const room = state.data.staff || {};
  const report = room.team_report || {};
  const staff = staffRows(dash).length
    ? staffRows(dash)
    : report.gameplay_staff_slots || [];
  const budget = staffBudgetSummary(staff, dash);

  return `
    <div class="section-head staff-card-head">
      <div class="staff-card-title">
        <h3>Staff</h3>
        <span class="staff-budget-inline">${money(budget.used)} / ${money(budget.max)}</span>
      </div>
      ${editable ? `<button type="button" class="staff-market-disclosure" data-staff-market-toggle aria-expanded="false" aria-label="Show available staff" title="Show available staff">▸</button>` : ""}
    </div>
    <div class="staff-dashboard-grid">
      <div class="staff-role-list">
        ${staff.length
          ? staff.map((row) => staffRoleButton(row, editable)).join("")
          : `<div class="empty">No staff data loaded.</div>`}
      </div>
    </div>
    ${editable ? staffMarketPopover() : ""}`;
}

function staffRoleButton(row, editable = true) {
  const role = row.slot || row.role || "";
  const name = staffName(row);
  const grade = staffGrade(row);
  const aav = staffAav(row);
  const years = staffYears(row);

  return `<button class="staff-role-button" data-staff-role="${escapeAttr(role)}" data-staff-name="${escapeAttr(name)}" ${editable ? "" : "disabled"}>
    <span class="staff-role">${escapeHtml(rowLabel(role))}</span>
    <span class="staff-name-row">
      <strong>${escapeHtml(name)}</strong>
      <em>${grade !== "" ? Number(grade).toFixed(1) : "—"}</em>
    </span>
    <span class="staff-meta">
      ${aav ? `${money(aav)}${years ? ` x ${years}` : ""}` : "No contract data"}
    </span>
    ${editable ? `<span class="staff-fire-hover">Fire</span>` : ""}
  </button>`;
}

function staffMarketPopover() {
  const candidates = [...marketCandidates(state.data.staff?.market)]
    .sort((left, right) => Number(staffGrade(right) || 0) - Number(staffGrade(left) || 0));
  const roles = [
    ["all", "All Roles"],
    ["head_coach", "Head Coach"],
    ["offensive_coordinator", "Offensive Coordinator"],
    ["defensive_coordinator", "Defensive Coordinator"],
    ["development_lead", "Development Lead"],
    ["performance_lead", "Performance Lead"],
    ["scouting_lead", "Scouting Lead"],
  ];
  return `<aside class="staff-market-popover" data-staff-market-popover hidden>
    <div class="staff-market-popover-head">
      <div><strong>Available Staff</strong><small>Sorted by grade</small></div>
      <button type="button" class="icon-button" data-staff-market-close aria-label="Close available staff" title="Close">×</button>
    </div>
    <select class="staff-market-role-filter" data-staff-market-filter aria-label="Filter available staff by role">
      ${roles.map(([value, label]) => `<option value="${escapeAttr(value)}">${escapeHtml(label)}</option>`).join("")}
    </select>
    <div class="staff-market-popover-list">
      ${candidates.map((candidate) => {
        const role = String(candidate.slot || candidate.role_preference || "");
        return `<button type="button" class="staff-market-candidate" data-staff-candidate="${escapeAttr(candidate.id || "")}" data-staff-candidate-slot="${escapeAttr(role)}">
          <span class="staff-market-candidate-main"><strong>${escapeHtml(staffName(candidate))}</strong><small>${escapeHtml(rowLabel(role))}</small></span>
          <span class="staff-market-candidate-grade">${Number(staffGrade(candidate) || 0).toFixed(1)}</span>
          <span class="staff-market-candidate-ask">${money(candidate.asking_salary_millions || staffAav(candidate))} x ${escapeHtml(candidate.asking_years || staffYears(candidate) || 1)}</span>
        </button>`;
      }).join("") || `<div class="empty">No available staff.</div>`}
    </div>
  </aside>`;
}

function staffBudgetSummary(staff, dash = state.data.dashboard || {}) {
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
    max: staffBudgetMillions(staff, paidStaff, dash),
  };
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

function staffBudgetMillions(staff, paidStaff, dash = state.data.dashboard || {}) {
  const room = state.data.staff || {};
  const report = room.team_report || {};
  const reportBudget = report.budget || {};
  const dashboardBudget = dash.staff_budget || {};

  const explicit =
    dashboardBudget.annual_budget_millions ??
    reportBudget.annual_budget_millions ??
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
  let result;
  let games = 0;
  let completed = 0;
  if (mode === "all") {
    showToast("Simulating the remaining playoffs...");
    for (let round = 0; round < 8; round += 1) {
      result = await action(actions.round, { ...savePayload(), seed: 7 });
      games += result.result?.games?.length || (result.result?.game ? 1 : 0);
      completed += result.result?.completed_series?.length || result.result?.completed_play_in?.length || 0;
      const room = result.room || {};
      if (room.status === "completed" || room.round === "champion" || !["play_in", "playoffs"].includes(room.phase)) break;
    }
  } else {
    result = await action(actions[mode] || actions.game, { ...savePayload(), seed: 7 });
    games = result.result?.games?.length || (result.result?.game ? 1 : 0);
    completed = result.result?.completed_series?.length || result.result?.completed_play_in?.length || 0;
  }
  if (!result) throw new Error("The playoff simulation did not return a result.");
  showToast(`Playoff sim: ${games ? `${games} game(s)` : result.status}${completed ? `, ${completed} series done` : ""}`);
  await refreshDashboardAfterPhaseMutation("playoffs", result.room);
}

async function refreshDashboardAfterPhaseMutation(roomKey, room) {
  state.home = await action("home", savePayload());
  state.view = "dashboard";
  const phaseKind = dashboardPhaseKind();
  const expectedKind = roomKey === "freeagency"
    ? "free_agency"
    : (roomKey === "fantasyDraft" ? "fantasy_draft" : roomKey);
  if (!phaseKind || phaseKind !== expectedKind) {
    await refreshHome();
    return;
  }
  state.data[roomKey] = room;
  if (roomKey === "fantasyDraft") {
    renderDashboard();
    return;
  }
  const team = state.dashboardTeam || userTeam();
  const dash = await action("team_dashboard", { ...savePayload(), team });
  state.data.dashboard = dash;
  if (team === userTeam()) state.data.statusDashboard = dash;
  if (roomKey === "playoffs") {
    state.data.playoffLeaders = await action("playoff_leaders", { ...savePayload(), stat: state.playoffLeaderStat, limit: 9 });
  }
  renderDashboard();
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
    summaryPlayerNameCell(row, true),
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

function boxScoreModalBody(box) {
  const away = teamLabel(box.away_team);
  const home = teamLabel(box.home_team);
  return `<div class="box-score-matchup-grid">
    ${boxScoreTeamSheet(box, away, box.away_score, "Away")}
    ${boxScoreTeamSheet(box, home, box.home_score, "Home")}
  </div>`;
}

function boxScoreTeamSheet(box, team, score, venueLabel) {
  const line = (box.team_lines || []).find((row) => (row.team_abbrev || teamLabel(row.team_id)) === team) || {};
  const players = (box.player_lines || []).filter((row) => row.team_abbrev === team);
  const logo = teamLogoSrc(team);
  const teamName = dashboardTeamName(team);
  return `<section class="box-score-team-sheet" ${teamBrandStyle(team)}>
    <header class="box-score-team-head">
      <div class="box-score-team-identity">
        ${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(`${teamName} logo`)}" />` : ""}
        <div><span>${escapeHtml(venueLabel)}</span><h4>${escapeHtml(teamName)}</h4><small>${escapeHtml(team)}</small></div>
      </div>
      <strong class="box-score-team-score">${escapeHtml(score ?? "—")}</strong>
    </header>
    <div class="box-score-team-totals">
      <span><small>FG</small><strong>${line.fgm !== undefined ? `${line.fgm}/${line.fga}` : "—"}</strong></span>
      <span><small>3PT</small><strong>${line.fg3m !== undefined ? `${line.fg3m}/${line.fg3a}` : "—"}</strong></span>
      <span><small>REB</small><strong>${line.rebounds ?? "—"}</strong></span>
      <span><small>AST</small><strong>${line.assists ?? "—"}</strong></span>
      <span><small>TO</small><strong>${line.turnovers ?? "—"}</strong></span>
    </div>
    ${boxScorePlayerTable(players)}
  </section>`;
}

function boxScorePlayerTable(players) {
  const headers = ["Player", "MIN", "PTS", "REB", "AST", "STL", "BLK", "FG", "3PT", "+/-"];
  return `<div class="box-score-player-table-wrap"><table class="box-score-player-table">
    <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
    <tbody>${players.map((row) => `<tr>
      <td>${escapeHtml(row.player_name || "Unknown")}</td>
      <td>${escapeHtml(decimalNumber(row.minutes))}</td>
      <td>${escapeHtml(row.points ?? 0)}</td>
      <td>${escapeHtml(row.rebounds ?? 0)}</td>
      <td>${escapeHtml(row.assists ?? 0)}</td>
      <td>${escapeHtml(row.steals ?? 0)}</td>
      <td>${escapeHtml(row.blocks ?? 0)}</td>
      <td>${row.fgm !== undefined ? `${escapeHtml(row.fgm)}/${escapeHtml(row.fga)}` : "—"}</td>
      <td>${row.fg3m !== undefined ? `${escapeHtml(row.fg3m)}/${escapeHtml(row.fg3a)}` : "—"}</td>
      <td>${escapeHtml(signedNumber(row.plus_minus || 0, 0))}</td>
    </tr>`).join("")}</tbody>
  </table></div>`;
}

async function openBoxScore(gameId, options = {}) {
  if (!gameId) return;
  try {
    const box = await action("box_score", { ...savePayload(), game_id: gameId });
    const gameIds = (options.gameIds || []).map(String);
    const requestedIndex = Number(options.gameIndex);
    const resolvedIndex = gameIds.length
      ? (Number.isInteger(requestedIndex) && requestedIndex >= 0 ? requestedIndex : Math.max(0, gameIds.indexOf(String(gameId))))
      : -1;
    const seriesPrefix = gameIds.length ? `Game ${resolvedIndex + 1} of ${gameIds.length} · ` : "";
    const datePrefix = box.game_date ? `${formatWrittenDate(box.game_date)} · ` : "";
    state.modal = {
      kind: gameIds.length ? "playoffBoxScore" : "boxScore",
      title: `${teamLabel(box.away_team)} ${box.away_score} @ ${teamLabel(box.home_team)} ${box.home_score}`,
      subtitle: `${seriesPrefix}${datePrefix}${box.mode || "game"} · possessions ${box.possessions || "-"} · OT ${box.overtime_periods || 0}`,
      body: boxScoreModalBody(box),
      gameIds,
      gameIndex: resolvedIndex,
      seriesId: options.seriesId || "",
    };
    renderModal();
  } catch (error) {
    showToast(error.message || String(error), true);
  }
}

async function openPlayoffSeriesBoxScore(seriesId) {
  const series = (state.data.playoffs?.series || []).find((row) => String(row.id) === String(seriesId));
  const gameIds = (series?.game_ids || []).map(String);
  if (!gameIds.length) return showToast("No games have been played in this series yet.");
  const gameIndex = gameIds.length - 1;
  await openBoxScore(gameIds[gameIndex], { gameIds, gameIndex, seriesId });
}

async function navigatePlayoffSeriesBoxScore(step) {
  if (state.modal?.kind !== "playoffBoxScore") return;
  const gameIds = state.modal.gameIds || [];
  const gameIndex = Number(state.modal.gameIndex || 0) + Number(step || 0);
  if (gameIndex < 0 || gameIndex >= gameIds.length) return;
  await openBoxScore(gameIds[gameIndex], {
    gameIds,
    gameIndex,
    seriesId: state.modal.seriesId || "",
  });
}

function closeModal() {
  if (state.modal?.kind === "freeAgentComparison") state.freeAgentCompareMode = true;
  state.modal = GameInterface.previousModal();
  renderModal();
}

function openSettingsModal() {
  state.modal = {
    kind: "dashboardSettings",
    title: "Settings",
    subtitle: "",
    body: `
      <section class="settings-modal-section settings-save-section">
        <button type="button" data-interface-shortcuts>Keyboard shortcuts <kbd>?</kbd></button>
        <button type="button" data-interface-gallery>Screen gallery</button>
        <button type="button" data-design-studies>Design studies</button>
        <a class="artwork-credits-link" href="/assets/game-art/CREDITS.md" target="_blank" rel="noopener">Artwork credits</a>
        <button class="settings-return-button" data-return-save-selection>Back to Save Selection</button>
      </section>`,
  };
  renderModal();
}

async function openExtensionNegotiation(playerId = "") {
  try {
    const room = await action("extension_room", {
      ...savePayload(),
      team: userTeam(),
      player_id: playerId || undefined,
    });
    const eligible = (room.candidates || []).filter((candidate) => candidate.eligible);
    const selectedId = playerId || eligible[0]?.player_id || room.candidates?.[0]?.player_id || "";
    const detail = selectedId ? await loadPlayerCardDetail(selectedId) : null;
    state.modal = {
      kind: "contractExtension",
      title: "Contract Extension",
      subtitle: `${teamLabel(room.team)} · ${room.date || ""}`,
      room,
      selectedPlayerId: selectedId,
      detail,
      response: null,
      body: extensionNegotiationBody(room, selectedId, null, detail),
    };
    renderModal();
  } catch (error) {
    showToast(error.message || "Extension room could not be opened.", true);
  }
}

function extensionNegotiationBody(room, selectedPlayerId, response = null, detail = null) {
  const candidates = room.candidates || [];
  const candidate = candidates.find((item) => item.player_id === selectedPlayerId) || candidates[0];
  if (!candidate) {
    return `<div class="extension-empty"><strong>No extension candidates</strong><p>No contracted player on this roster is available for extension review right now.</p></div>`;
  }
  const years = Math.max(1, Math.min(Number(candidate.safe_years || 1), Number(candidate.preferred_years || 1)));
  const maximum = Number(candidate.max_aav_by_years?.[String(years)] || 0);
  const ask = Number(candidate.projected_aav_millions || 0);
  const initialOffer = Math.min(maximum, ask);
  const ratings = detail?.ratings || {};
  const season = detail?.season || {};
  const capRows = (candidate.cap_projection || []).map((row) => [row.season, row]);
  return `<div class="approved-negotiation approved-extension-negotiation">
    <section class="approved-card-panel approved-negotiation-season"><header><select data-extension-player-select>${candidates.map((item) => `<option value="${escapeAttr(item.player_id)}" ${item.player_id === candidate.player_id ? "selected" : ""} ${item.eligible ? "" : "disabled"}>${escapeHtml(item.name || "Player")}</option>`).join("")}</select><span>Latest Season</span></header><div>${[["GP", season.games], ["MPG", season.mpg], ["PTS", season.ppg], ["REB", season.rpg], ["AST", season.apg], ["STL", season.spg], ["BLK", season.bpg], ["TO", season.topg], ["FTA", season.fta_per_game], ["FT%", season.ft_pct]].map(([label, value]) => `<span><small>${label}</small><strong>${draftMetric(value)}</strong></span>`).join("")}</div></section>
    <section class="approved-card-panel approved-negotiation-ratings"><header>Complete Ratings</header>${detail ? negotiationEvidence(detail) : ""}<div class="approved-rating-rail">${playerCardRatingRows(ratings).map(([label, value, key]) => `<div class="${ratingQuartileTone(value, key, detail?.rating_quartiles)}"><span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(value)}"></b></i><strong>${draftMetric(value)}</strong></div>`).join("")}</div></section>
    <div class="approved-negotiation-work">
      <section class="approved-card-panel approved-ask-offer"><header>Ask / Offer</header><form data-extension-offer-form><div class="approved-ask-grid"><span><small>Ask</small><strong>${money(ask)} × ${candidate.preferred_years || years}</strong></span><label><small>Offer · max <b data-extension-maximum>${money(maximum)}</b></small><span class="money-input"><b>$</b><input type="number" min="1.8" max="${maximum.toFixed(2)}" step="0.1" value="${initialOffer.toFixed(1)}" data-extension-aav required><b>M</b></span></label><label><small>Years</small><select data-extension-years>${Array.from({ length: Number(candidate.safe_years || 1) }, (_item, index) => index + 1).map((value) => `<option value="${value}" ${value === years ? "selected" : ""}>${value}</option>`).join("")}</select></label></div><button type="submit" class="extension-submit primary-action" ${maximum < 1.8 ? "disabled" : ""}>Submit Offer</button></form></section>
      <section class="approved-card-panel approved-interest-factors"><header>Interest Breakdown</header><div>${[["Offer vs ask", initialOffer / Math.max(1, ask) * 100], ["Player timeline", Math.max(20, 100 - Number(candidate.age || 27) * 1.4)], ["Team direction", 64], ["Contract length", years / Math.max(1, Number(candidate.preferred_years || years)) * 100]].map(([label, value]) => `<span><small>${escapeHtml(label)}</small><i><b style="width:${clampNumber(value, 0, 100)}%"></b></i><strong>${Math.round(clampNumber(value, 0, 100))}</strong></span>`).join("")}</div></section>
      <section class="approved-card-panel approved-offer-cap"><header>Four-Year Cap Impact</header>${approvedOfferCapChart(capRows.slice(0, 4), initialOffer)}</section>
      <section class="approved-card-panel approved-offer-salary"><header>Six-Season Salary + Team Position</header>${approvedOfferSalaryTable(capRows, initialOffer)}</section>
      ${response ? `<section class="extension-response ${response.status === "rejected" ? "rejected" : ""}"><strong>${escapeHtml(response.status === "rejected" ? "Offer declined" : rowLabel(response.status || "update"))}</strong><span>${escapeHtml(response.reason || "")}${response.interest !== undefined ? ` Interest: ${Number(response.interest).toFixed(1)}/100.` : ""}</span></section>` : ""}
    </div>
  </div>`;
}

function wireExtensionNegotiationModal() {
  const modal = state.modal;
  if (!modal || modal.kind !== "contractExtension") return;
  els.modalRoot.querySelector("[data-extension-player-select]")?.addEventListener("change", async (event) => {
    modal.selectedPlayerId = event.target.value || "";
    modal.detail = modal.selectedPlayerId ? await loadPlayerCardDetail(modal.selectedPlayerId) : null;
    modal.response = null;
    modal.body = extensionNegotiationBody(modal.room, modal.selectedPlayerId, null, modal.detail);
    renderModal();
  });
  const yearsInput = els.modalRoot.querySelector("[data-extension-years]");
  const aavInput = els.modalRoot.querySelector("[data-extension-aav]");
  yearsInput?.addEventListener("change", () => {
    const candidate = (modal.room?.candidates || []).find((item) => item.player_id === modal.selectedPlayerId);
    const maximum = Number(candidate?.max_aav_by_years?.[String(yearsInput.value)] || 0);
    if (aavInput) {
      aavInput.max = maximum.toFixed(2);
      aavInput.value = Math.min(Number(aavInput.value || 0), maximum).toFixed(1);
    }
    const read = els.modalRoot.querySelector("[data-extension-maximum]");
    if (read) read.textContent = money(maximum);
  });
  els.modalRoot.querySelector("[data-extension-offer-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const playerId = modal.selectedPlayerId;
    const years = Number(els.modalRoot.querySelector("[data-extension-years]")?.value || 1);
    const aav = Number(els.modalRoot.querySelector("[data-extension-aav]")?.value || 0);
    try {
      const result = await action("submit_extension_offer", {
        ...savePayload(),
        player_id: playerId,
        years,
        aav_millions: aav,
      });
      if (result.status === "applied") {
        closeModal();
        showToast(`${result.player_name || "Player"} signed a ${years}-year extension.`);
        await refreshHome();
        return;
      }
      modal.response = result;
      modal.room = result.room || modal.room;
      modal.body = extensionNegotiationBody(modal.room, modal.selectedPlayerId, result, modal.detail);
      renderModal();
    } catch (error) {
      showToast(error.message || "Extension offer could not be submitted.", true);
    }
  });
}

function renderModal() {
  if (!els.modalRoot) return;
  GameInterface.modalWillRender(state.modal);
  if (!state.modal) {
    els.modalRoot.hidden = true;
    els.modalRoot.innerHTML = "";
    return;
  }
  els.modalRoot.hidden = false;
  const modalClass = ["playerFinder", "leagueLeaders", "freeAgentComparison", "teamDevelopment"].includes(state.modal.kind)
    ? " modal-wide"
    : ["fantasyPlayer", "dashboardPlayer", "draftProspect", "freeAgentPlayer"].includes(state.modal.kind)
      ? " modal-fantasy-player"
    : state.modal.kind === "tradeRoom"
      ? " modal-trade-room"
      : ["tradeOffers", "humanTradeOffers"].includes(state.modal.kind)
        ? " modal-trade-offers"
      : state.modal.kind === "dashboardSettings"
        ? " modal-settings"
      : state.modal.kind === "staffNegotiation"
        ? " modal-staff-negotiation"
      : state.modal.kind === "contractExtension"
        ? " modal-contract-extension"
      : state.modal.kind === "freeAgentNegotiation"
        ? " modal-free-agent-negotiation"
      : ["boxScore", "playoffBoxScore"].includes(state.modal.kind)
        ? " modal-box-score"
        : "";
  const closeLabel = state.modal.kind === "tradeRoom"
    ? "Trade Room"
    : state.modal.kind === "staffNegotiation"
      ? "Staff Negotiation"
    : ["fantasyPlayer", "dashboardPlayer", "draftProspect", "freeAgentPlayer"].includes(state.modal.kind)
      ? "Player Card"
    : ["freeAgentNegotiation", "freeAgentComparison"].includes(state.modal.kind)
      ? "Free Agency"
    : state.modal.kind === "teamDevelopment"
      ? "Team Development"
    : ["boxScore", "playoffBoxScore"].includes(state.modal.kind)
      ? "Box Score"
      : "Trade Offers";
  const closeControl = ["tradeRoom", "tradeOffers", "humanTradeOffers", "fantasyPlayer", "dashboardPlayer", "draftProspect", "freeAgentPlayer", "freeAgentNegotiation", "freeAgentComparison", "teamDevelopment", "staffNegotiation", "contractExtension", "boxScore", "playoffBoxScore"].includes(state.modal.kind)
    ? `<button class="modal-close-icon" data-close-modal aria-label="Close ${closeLabel}" title="Close">×</button>`
    : `<button data-close-modal>Close</button>`;
  const seriesNavigation = state.modal.kind === "playoffBoxScore"
    ? `<nav class="series-box-score-navigation" aria-label="Series games">
        <button type="button" data-playoff-box-step="-1" aria-label="Previous game" title="Previous game" ${state.modal.gameIndex <= 0 ? "disabled" : ""}>‹</button>
        <span>Game ${Number(state.modal.gameIndex || 0) + 1} / ${(state.modal.gameIds || []).length}</span>
        <button type="button" data-playoff-box-step="1" aria-label="Next game" title="Next game" ${state.modal.gameIndex >= (state.modal.gameIds || []).length - 1 ? "disabled" : ""}>›</button>
      </nav>`
    : "";
  els.modalRoot.innerHTML = `
    <div class="modal-shell${modalClass}" role="dialog" aria-modal="true">
      <header class="modal-head">
        <div>
          ${state.modal.subtitle ? `<p class="eyebrow">${escapeHtml(state.modal.subtitle)}</p>` : ""}
          <h3>${escapeHtml(state.modal.title || "Detail")}</h3>
        </div>
        ${seriesNavigation}
        ${closeControl}
      </header>
      <div class="modal-body">${state.modal.body || ""}</div>
    </div>`;
  if (state.modal.kind === "tradeOffers") {
    wireOfferButtons(els.modalRoot, state.modal.offers || []);
  }
  if (state.modal.kind === "humanTradeOffers") {
    els.modalRoot.querySelectorAll("[data-human-trade-accept]").forEach((button) => {
      button.addEventListener("click", () => respondHumanTrade(button.dataset.humanTradeAccept, "accept"));
    });
    els.modalRoot.querySelectorAll("[data-human-trade-reject]").forEach((button) => {
      button.addEventListener("click", () => respondHumanTrade(button.dataset.humanTradeReject, "reject"));
    });
  }
  if (["playerFinder", "leagueLeaders"].includes(state.modal.kind)) {
    wirePlayerFinderModal();
  }
  if (state.modal.kind === "fantasyPlayer") {
    els.modalRoot.querySelector("[data-fantasy-card-select]")?.addEventListener("click", (event) => {
      rememberFantasyBoardScroll();
      state.selectedFantasyPlayer = event.currentTarget.dataset.fantasyCardSelect || "";
      closeModal();
      renderDashboard();
    });
    els.modalRoot.querySelector("[data-fantasy-card-watch]")?.addEventListener("click", async (event) => {
      const playerId = event.currentTarget.dataset.fantasyCardWatch || "";
      await fantasyDraftToggleWatchlist(playerId);
      fantasyPlayerCard(playerId);
    });
  }
  if (state.modal.kind === "tradeRoom") {
    wireTradeRoom();
  }
  if (state.modal.kind === "dashboardSettings") {
    els.modalRoot.querySelector("[data-return-save-selection]")?.addEventListener("click", returnToSaveSelection);
  }
  if (state.modal.kind === "staffNegotiation") {
    els.modalRoot.querySelector("[data-staff-negotiation-form]")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      await submitDashboardStaffNegotiation();
    });
    const salary = els.modalRoot.querySelector("[data-staff-offer-salary]");
    if (salary) salary.addEventListener("input", () => {
      const maximum = Number(state.modal?.maxOffer || 0);
      salary.setCustomValidity(Number(salary.value || 0) > maximum + 0.001 ? `Maximum legal offer is ${money(maximum)}.` : "");
    });
  }
  if (state.modal.kind === "contractExtension") wireExtensionNegotiationModal();
  if (state.modal.kind === "freeAgentNegotiation") {
    els.modalRoot.querySelector("#submitFaOffer")?.addEventListener("click", submitFreeAgentOffer);
    els.modalRoot.querySelector("[data-fa-modal-player-card]")?.addEventListener("click", (event) => freeAgentPlayerCard(event.currentTarget.dataset.faModalPlayerCard || ""));
    const aavInput = els.modalRoot.querySelector("#faAav");
    const clampOffer = () => {
      if (!aavInput) return;
      const minimum = Number(aavInput.min || 1.9);
      const maximum = Number(aavInput.max || minimum);
      const value = Number(aavInput.value);
      if (!Number.isFinite(value)) return;
      aavInput.value = clampNumber(value, minimum, maximum).toFixed(1);
      const offer = Number(aavInput.value || 0);
      const ask = Number(freeAgencyCandidate(state.selectedFreeAgent)?.ask_millions || 1);
      const interest = Math.round(clampNumber(offer / Math.max(1, ask) * 70, 0, 100));
      const interestBar = els.modalRoot.querySelector("[data-fa-live-interest]");
      if (interestBar) interestBar.style.width = `${interest}%`;
      const interestValue = els.modalRoot.querySelector("[data-fa-live-interest-value]");
      if (interestValue) interestValue.textContent = `${interest} / 100`;
      els.modalRoot.querySelectorAll("[data-offer-highlight]").forEach((bar) => {
        const capMaximum = Number(bar.dataset.capMaximum || 1);
        bar.style.height = `${clampNumber(offer / capMaximum * 100, 0, 100)}%`;
      });
      els.modalRoot.querySelectorAll("[data-offer-payroll]").forEach((read) => { read.textContent = money(Number(read.dataset.basePayroll || 0) + offer); });
      els.modalRoot.querySelectorAll("[data-offer-salary]").forEach((read) => { read.textContent = money(offer); });
      els.modalRoot.querySelectorAll("[data-offer-table-payroll]").forEach((read) => { read.textContent = money(Number(read.dataset.base || 0) + offer); });
      els.modalRoot.querySelectorAll("[data-offer-table-tax], [data-offer-table-hard]").forEach((read) => { read.textContent = signedMoney(Number(read.dataset.base || 0) - offer); });
    };
    aavInput?.addEventListener("input", clampOffer);
    aavInput?.addEventListener("blur", clampOffer);
    aavInput?.addEventListener("change", clampOffer);
  }
  if (state.modal.kind === "freeAgentPlayer") {
    els.modalRoot.querySelector("[data-fa-card-negotiate]")?.addEventListener("click", (event) => openFreeAgentNegotiation(event.currentTarget.dataset.faCardNegotiate || ""));
  }
  if (state.modal.kind === "freeAgentComparison") {
    els.modalRoot.querySelectorAll("[data-fa-comparison-card]").forEach((button) => button.addEventListener("click", () => freeAgentPlayerCard(button.dataset.faComparisonCard || "")));
    els.modalRoot.querySelectorAll("[data-fa-comparison-negotiate]").forEach((button) => button.addEventListener("click", () => openFreeAgentNegotiation(button.dataset.faComparisonNegotiate || "")));
  }
  els.modalRoot.querySelectorAll("[data-dashboard-player-card]").forEach(button => {
    button.addEventListener("click", () => dashboardPlayerCard(button.dataset.dashboardPlayerCard));
  });
  if (state.modal.kind === "playoffBoxScore") {
    els.modalRoot.querySelectorAll("[data-playoff-box-step]").forEach((button) => {
      button.addEventListener("click", () => navigatePlayoffSeriesBoxScore(Number(button.dataset.playoffBoxStep || 0)));
    });
  }
  els.modalRoot.querySelectorAll("[data-dashboard-team-jump]").forEach((button) => {
    button.addEventListener("click", async () => {
      closeModal();
      await switchDashboardTeam(button.dataset.dashboardTeamJump || userTeam());
    });
  });
  GameInterface.modalDidRender();
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
  wrap?.querySelectorAll("[data-dashboard-player-card]").forEach(button => button.addEventListener("click", () => dashboardPlayerCard(button.dataset.dashboardPlayerCard)));
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
  const logo = teamLogoSrc(selected);
  const record = dashboardTeamRecord(selected);
  return `<div class="section-head identity-head">
      <div class="identity-club-mark">
        ${logo ? `<img src="${escapeAttr(logo)}" alt="" aria-hidden="true" />` : ""}
        <div>
          <h3><select id="dashboardTeamSelect" aria-label="Dashboard team">${dashboardTeamOptions(selected)}</select> Identity</h3>
          ${record ? `<small>${escapeHtml(record)}</small>` : ""}
        </div>
      </div>
      ${selected !== userTeam() ? `<button type="button" class="identity-reset-button" data-dashboard-team-reset title="Return to ${escapeAttr(userTeam())}" aria-label="Return to ${escapeAttr(userTeam())}">Reset</button>` : ""}
    </div>
    <div class="identity-primary-bars">${rankedBarList([
      ["Overall", metrics.overall, ranks.overall, count],
      ["Offense", metrics.offense, ranks.offense, count],
      ["Defense", metrics.defense, ranks.defense, count],
      ["Depth", metrics.depth, ranks.depth, count],
    ])}</div>
    ${teamIdentityRadarChart(metrics, ranks, count)}`;
}

function dashboardTeamRecord(team) {
  const rows = standingsRows(state.data.dashboardStandings);
  const row = rows.find((candidate) => teamLabel(candidate.team) === team);
  if (!row) return "";
  const conference = row.team?.conference || "League";
  const rank = rows.filter((candidate) => candidate.team?.conference === conference).findIndex((candidate) => teamLabel(candidate.team) === team) + 1;
  return `${Number(row.wins || 0)}-${Number(row.losses || 0)} · ${conference}${rank > 0 ? ` #${rank}` : ""}`;
}

function teamIdentityRadarChart(metrics, ranks, leagueCount, options = {}) {
  const compact = Boolean(options.compact);
  const axes = [
    { key: "spacing", label: compact ? "SPACE" : "Spacing" },
    { key: "creation", label: compact ? "CREATE" : "Creation" },
    { key: "rim_pressure", label: compact ? "RIM PRESS" : "Rim pressure" },
    { key: "rebounding", label: compact ? "REBOUND" : "Rebounding" },
    { key: "rim_protection", label: compact ? "RIM PROTECT" : "Rim protect" },
    { key: "defensive_disruption", label: compact ? "DISRUPT" : "Disruption" },
  ];
  const width = compact ? 286 : 252;
  const height = compact ? 150 : 158;
  const centerX = width / 2;
  const centerY = compact ? 72 : 76;
  const radius = compact ? 43 : 52;
  const angleFor = (index) => (-Math.PI / 2) + (index * Math.PI * 2) / axes.length;
  const pointFor = (index, proportion = 1, extra = 0) => {
    const angle = angleFor(index);
    return {
      x: centerX + Math.cos(angle) * (radius * proportion + extra),
      y: centerY + Math.sin(angle) * (radius * proportion + extra),
    };
  };
  const polygon = (proportion) => axes.map((_, index) => {
    const point = pointFor(index, proportion);
    return `${point.x.toFixed(1)},${point.y.toFixed(1)}`;
  }).join(" ");
  const profilePoints = axes.map((axis, index) => {
    const rank = Number(ranks[axis.key]);
    const value = Number.isFinite(rank) && rank > 0
      ? clampNumber((Number(leagueCount) - rank + 1) / Math.max(1, Number(leagueCount)), 0.08, 1)
      : clampNumber(Number(metrics[axis.key] || 0), 8, 99) / 99;
    const point = pointFor(index, value);
    return `${point.x.toFixed(1)},${point.y.toFixed(1)}`;
  }).join(" ");
  return `
    <div class="identity-radar-panel">
      <div class="identity-radar-caption"><span>Team profile</span><small>rotation-weighted</small></div>
      <svg class="identity-radar" viewBox="0 0 ${width} ${height}" role="img" aria-label="Team profile radar chart">
        ${[0.25, 0.5, 0.75, 1].map((level) => `<polygon class="identity-radar-grid" points="${polygon(level)}" />`).join("")}
        ${axes.map((axis, index) => {
          const edge = pointFor(index);
          return `<line class="identity-radar-axis" x1="${centerX}" y1="${centerY}" x2="${edge.x.toFixed(1)}" y2="${edge.y.toFixed(1)}" />`;
        }).join("")}
        <polygon class="identity-radar-shape" points="${profilePoints}">
          <title>${escapeHtml(axes.map((axis) => `${axis.label}: ${Number(metrics[axis.key] || 0).toFixed(1)} (#${ranks[axis.key] || leagueCount}/${leagueCount})`).join(" | "))}</title>
        </polygon>
        ${axes.map((axis, index) => {
          const label = pointFor(index, 1, compact ? 14 : 18);
          const anchor = Math.abs(label.x - centerX) < 5 ? "middle" : label.x < centerX ? "end" : "start";
          const baseline = label.y < centerY - 12 ? "auto" : label.y > centerY + 12 ? "hanging" : "middle";
          const rank = Number(ranks[axis.key]);
          const rankLabel = Number.isFinite(rank) && rank > 0 ? ` #${rank}/${leagueCount}` : "";
          return `<text class="identity-radar-label" text-anchor="${anchor}" dominant-baseline="${baseline}" x="${label.x.toFixed(1)}" y="${label.y.toFixed(1)}">${escapeHtml(`${axis.label}${rankLabel}`)}</text>`;
        }).join("")}
      </svg>
    </div>`;
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

function ensureRotationDraft(rows) {
  if (!Object.keys(state.rotationDraft).length) {
    rows.filter((row) => row.rotation_user_set).forEach((row) => state.rotationLockedPlayerIds.add(row.id));
    state.rotationDraft = Object.fromEntries(
      rows.map((row) => [
        row.id,
        Math.round(Number(row.rotation_target_minutes ?? row.coach_minutes_projection ?? row.minutes_projection ?? 0)),
      ])
    );
  } else {
    for (const row of rows) {
      if (state.rotationDraft[row.id] === undefined) {
        state.rotationDraft[row.id] = Math.round(
          Number(row.rotation_target_minutes ?? row.coach_minutes_projection ?? row.minutes_projection ?? 0)
        );
      }
    }
  }
}

function autofillRotationDraft(rows) {
  const roster = rows.filter((row) => row?.id && !row.__summaryEmpty);
  const rosterIds = new Set(roster.map((row) => row.id));
  for (const playerId of [...state.rotationLockedPlayerIds]) {
    if (!rosterIds.has(playerId)) state.rotationLockedPlayerIds.delete(playerId);
  }

  const locked = roster.filter((row) => state.rotationLockedPlayerIds.has(row.id));
  const unlocked = roster.filter((row) => !state.rotationLockedPlayerIds.has(row.id));
  const lockedTotal = locked.reduce((sum, row) => sum + Number(state.rotationDraft[row.id] || 0), 0);
  let remaining = Math.max(0, 240 - lockedTotal);
  for (const row of unlocked) state.rotationDraft[row.id] = 0;

  const weights = new Map(unlocked.map((row) => [
    row.id,
    Math.max(
      0.25,
      Number(row.rotation_target_minutes ?? row.coach_minutes_projection ?? row.minutes_projection ?? 0),
      Number(rating(row, "overall") || 0) / 12
    ),
  ]));
  while (remaining > 0 && unlocked.some((row) => Number(state.rotationDraft[row.id] || 0) < 48)) {
    const candidate = unlocked
      .filter((row) => Number(state.rotationDraft[row.id] || 0) < 48)
      .sort((a, b) => {
        const aScore = Number(weights.get(a.id) || 0) / (Number(state.rotationDraft[a.id] || 0) + 1);
        const bScore = Number(weights.get(b.id) || 0) / (Number(state.rotationDraft[b.id] || 0) + 1);
        return bScore - aScore || String(a.name || "").localeCompare(String(b.name || ""));
      })[0];
    if (!candidate) break;
    state.rotationDraft[candidate.id] = Number(state.rotationDraft[candidate.id] || 0) + 1;
    remaining -= 1;
  }
}

function syncRotationInputs(root = els.content) {
  root.querySelectorAll("[data-minute-player]").forEach((input) => {
    const playerId = input.dataset.minutePlayer;
    const value = clampNumber(Number(state.rotationDraft[playerId] || 0), 0, 48);
    input.value = String(value);
    input.classList.toggle("user-locked", state.rotationLockedPlayerIds.has(playerId));
    input.closest(".season-minute-slider")?.classList.toggle("user-locked", state.rotationLockedPlayerIds.has(playerId));
    const fill = input.closest(".season-minute-slider")?.querySelector(".season-minute-fill");
    if (fill) fill.style.width = `${(value / 48 * 100).toFixed(2)}%`;
    const output = Array.from(root.querySelectorAll("[data-minute-output]")).find((node) => node.dataset.minuteOutput === playerId)
      || input.closest(".rotation-row")?.querySelector("output");
    if (output) output.textContent = String(value);
  });
}

function summaryLeaderRotator(limit = 5, expanded = false, options = {}) {
  const fields = state.data.dashboardSummaryLeaders?.fields || [];
  const slides = fields.map((field, fieldIndex) => {
    const leaders = (field.leaders || []).slice(0, limit);
    const label = field.label || field.key || "Field";
    return `
      <div class="summary-leader-slide ${expanded ? "journey-expanded-list" : ""} ${fieldIndex === 0 ? "active" : ""}" data-field-label="${escapeAttr(label)}">
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
    ${options.header === false ? "" : `<div class="section-head summary-leader-head">
      <h3>League Leader:</h3>
      <select id="summaryLeaderSelect" aria-label="League leader category">
        ${fields.map((field, index) => `<option value="${index}">${escapeHtml(field.label || field.key || "Field")}</option>`).join("")}
      </select>
    </div>`}
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
  const dash = state.data.dashboard || {};
  const editable = !state.hydrating && teamLabel(dash.team || state.dashboardTeam) === userTeam();
  const contractChartView = state.dashboardContractView === "chart";
  return `
    <div class="section-head summary-head">
      <div class="roster-command-title">
        <div>
          <h3>Ratings <span>/</span> Season Box Score <span>/</span> Contracts</h3>
        </div>
        <span class="roster-context">${escapeHtml(state.home?.save?.current_date || "")}</span>
      </div>
      <div class="summary-stat-head" aria-hidden="true"></div>
      <div class="summary-contract-head">
        <button type="button" class="summary-contract-toggle" data-summary-contract-toggle aria-label="Switch contract display" title="Switch to ${contractChartView ? "table" : "chart"} view">${contractChartView ? "Chart" : "Table"}</button>
      </div>
    </div>
    <div class="dashboard-mini-table${contractChartView ? " summary-contract-chart-mode" : ""}">
      ${contractChartView
        ? `<div class="summary-core-table">${dashboardPlayerSummaryTableInner(rows, seasons, editable)}</div>
          <div class="summary-contract-chart">${summaryContractChart(rows, seasons, dash)}</div>`
        : dashboardPlayerSummaryTableInner(rows, seasons, editable)}
    </div>`;
}

function dashboardPlayerSummaryTableInner(summaryRows, seasons, editable, options = {}) {
  const includeContracts = options.includeContracts !== false;
  const extensionWindowOpen = Boolean(state.data.dashboard?.extension_window_open);
  const headers = ["Player", "Pos", "Height", "Age", "OVR", "Shot", "Create", "Def", "Space", "Pass", "Reb", "Rim", "Ath", "GP", "Set", "MPG", "PTS", "REB", "AST", "STL", "BLK", "TO", ...(includeContracts ? seasons : [])];
  return table(headers, summaryRows, (row) => [
        summaryPlayerNameCell(row, true),
        compactPos(row.position),
        heightFromRow(row) || "—",
        row.age ?? "—",
        tieredRating(rating(row, "overall"), "overall", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "shooting"), "shooting", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "creation"), "creation", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "defense"), "defense", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "spacing") || rating(row, "range"), "range", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "passing"), "passing", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "rebounding"), "rebounding", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "rim_deterrence"), "rim_deterrence", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "athleticism"), "athleticism", state.data.dashboard?.rating_tertiles),
        row.gp_display || `${Number(row.games || 0)}/${Number(row.team_games || 0)}`,
        rotationSliderCell(row, editable),
        Number(mpgFromRow(row) || 0).toFixed(1),
        statNumber(row, "points"),
        statNumber(row, "rebounds"),
        statNumber(row, "assists"),
        statNumber(row, "steals"),
        statNumber(row, "blocks"),
        statNumber(row, "turnovers"),
        ...(includeContracts ? seasons.map((season) => summaryContractSalaryCell(row, season, editable, extensionWindowOpen)) : []),
      ], "dashboard-player-summary");
}

function summaryContractChart(rows, seasons, dash) {
  if (!rows.length || !seasons.length) return `<div class="empty">No contract data loaded.</div>`;
  const source = dash.cap_by_year || {};
  const known = Object.values(source);
  const tax = known.find(cap => Number(cap.tax_line_millions) > 0)?.tax_line_millions || 190;
  const hard = known.find(cap => Number(cap.hard_cap_millions) > 0)?.hard_cap_millions || 230;
  const capByYear = Object.fromEntries(seasons.map(season => {
    const cap = source[season] || {};
    return [season, {
      ...cap,
      tax_line_millions: Number(cap.tax_line_millions) > 0 ? cap.tax_line_millions : tax,
      hard_cap_millions: Number(cap.hard_cap_millions) > 0 ? cap.hard_cap_millions : hard,
    }];
  }));
  return salaryHorizonChart({seasons, rows, capByYear});
}

function salaryHorizonChart({seasons=[],rows=[],capByYear={},highlightPlayerId='',payrollByYear={},offer=false,className=''}={}) {
  const horizon=[...seasons].slice(0,4);
  while(horizon.length<4) horizon.push(`Year ${horizon.length+1}`);
  const colorIds = [...new Set(rows.map((row,index)=>String(row.id||row.player_id||index)))].sort();
  const values=horizon.map(season=>{
    const cap=capByYear?.[season]||{};
    const salaries=rows.map((row,index)=>{const id=String(row.id||row.player_id||index);return {id,name:row.name||'',salary:Number(row.salary_by_year?.[season]||0),index:colorIds.indexOf(id)};}).filter(item=>item.salary>0).sort((a,b)=>b.salary-a.salary||a.id.localeCompare(b.id));
    const known=salaries.reduce((sum,item)=>sum+item.salary,0);
    const payroll=Number(payrollByYear?.[season] ?? cap.salary_total_millions ?? known);
    return {season,cap,salaries,payroll:Math.max(payroll,known),remainder:Math.max(0,payroll-known)};
  });
  const maximum=Math.max(1,...values.flatMap(({cap,payroll})=>[payroll,Number(cap.tax_line_millions||0),Number(cap.hard_cap_millions||0)]))*1.06;
  const pct=value=>clampNumber(Number(value||0)/maximum*100,0,100);
  return `<div class="salary-horizon-chart${className?` ${escapeAttr(className)}`:''}${highlightPlayerId?' is-player-focus':''}${offer?' is-offer':''}">${values.map(({season,cap,salaries,payroll,remainder})=>{
    let segments=salaries;
    if(highlightPlayerId){
      const focus=salaries.filter(item=>item.id===String(highlightPlayerId));
      const other=salaries.filter(item=>item.id!==String(highlightPlayerId)).reduce((sum,item)=>sum+item.salary,0)+remainder;
      segments=[...(other>0?[{id:'other',salary:other,index:-1}]:[]),...focus];
    } else if(remainder>0) segments=[{id:'other',salary:remainder,index:-1},...segments];
    const tax=Number(cap.tax_line_millions||0),hard=Number(cap.hard_cap_millions||0);
    const focusedSalary=salaries.find(item=>item.id===String(highlightPlayerId))?.salary||0;
    const displaySalary=highlightPlayerId?focusedSalary:payroll;
    return `<div class="salary-horizon-year"><span>${escapeHtml(shortSeasonLabel(season))}</span><div class="salary-horizon-column" role="img" aria-label="${escapeAttr(`${season} payroll ${money(payroll)}, tax ${money(tax)}, hard cap ${money(hard)}`)}"><div class="salary-horizon-stack" style="height:${pct(payroll)}%">${segments.map(item=>`<i class="salary-segment salary-segment-${item.index<0?'other':item.index%8}${item.id===String(highlightPlayerId)?' is-highlighted':''}" style="height:${payroll?clampNumber(item.salary/payroll*100,0,100):0}%" title="${escapeAttr(item.id==='other'?`Other payroll ${money(item.salary)}`:`${money(item.salary)}`)}"></i>`).join('')}</div>${tax?`<b class="salary-tax-line" style="bottom:${pct(tax)}%"></b>`:''}${hard?`<b class="salary-hard-line" style="bottom:${pct(hard)}%"></b>`:''}</div><strong>${displaySalary?money(displaySalary):'—'}</strong></div>`;
  }).join('')}<div class="salary-horizon-legend"><span>Tax</span><span>Hard cap</span></div></div>`;
}

function summaryPlayerNameCell(row, interactive = false) {
  const name = row.name || "";
  const injured = isPlayerInjured(row.health);
  const returnGames = injuryGamesRemaining(row);
  const returnLabel = injured && returnGames !== null
    ? `<span class="injury-return-games" title="Estimated games until healthy"> - ${returnGames}</span>`
    : "";
  if (!interactive) {
    return injured ? html(`<span class="injured-player-name">${escapeHtml(name)}${returnLabel}</span>`) : name;
  }
  return html(`<button class="summary-player-card-button${injured ? " injured-player-name" : ""}" data-dashboard-player-card="${escapeAttr(row.id)}" aria-label="Open player card for ${escapeAttr(name)}">${escapeHtml(name)}${returnLabel}</button>`);
}

function injuryGamesRemaining(row) {
  if (!isPlayerInjured(row.health)) return null;
  const labelMatch = String(row.health?.label || "").match(/~\s*(\d+)\s*g/i);
  if (labelMatch) return Number(labelMatch[1]);
  const daysLeft = Number(row.health?.days_left);
  return Number.isFinite(daysLeft) ? Math.max(1, Math.round(daysLeft / 2.4)) : null;
}

function gamesMissedFromRow(row) {
  const value = Number(row.health?.games_missed ?? row.games_missed ?? 0);
  return Number.isFinite(value) ? value : 0;
}

function summaryContractSalaryCell(row, season, editable = false, extensionWindowOpen = false) {
  const salary = money(row.salary_by_year?.[season]) || "—";
  if (!extensionWindowOpen || !row.extension_eligible) return salary;
  const hasContractValue = row.salary_by_year?.[season] !== undefined && row.salary_by_year?.[season] !== null;
  if (!editable || !hasContractValue) return html(`<span class="extension-eligible-contract" title="Contract extension eligible">${escapeHtml(salary)}</span>`);
  return html(`<button type="button" class="extension-eligible-contract extension-contract-button" data-extension-player="${escapeAttr(row.id)}" title="Negotiate an extension with ${escapeAttr(row.name || "this player")}">${escapeHtml(salary)}</button>`);
}

function rotationSliderCell(row, editable) {
  const value = clampNumber(Number(state.rotationDraft[row.id] ?? row.minutes_projection ?? 0), 0, 48);
  return html(`
    <div class="summary-minute-control">
      <input type="range" min="0" max="48" step="1" value="${value}" data-minute-player="${escapeAttr(row.id)}" ${editable ? "" : "disabled"} />
      <output data-minute-output="${escapeAttr(row.id)}">${value}</output>
    </div>`);
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
  const viewedRow = standings.find((row) => teamLabel(row.team) === viewed);
  const defaultConference = viewedRow?.team?.conference || "East";
  const conference = ["East", "West"].includes(state.dashboardStandingsConference) ? state.dashboardStandingsConference : defaultConference;
  const conferenceRows = standings
    .filter((row) => row.team?.conference === conference)
    .map((row, index) => ({ ...row, dashboard_conference_rank: index + 1 }));
  const viewedConferenceRow = conferenceRows.find((row) => teamLabel(row.team) === viewed);
  let rows = conferenceRows.slice(0, 10);
  if (viewedConferenceRow && !rows.some((row) => teamLabel(row.team) === viewed)) {
    rows = [...rows.slice(0, 9), viewedConferenceRow];
  }

  return `<div class="section-head standings-head">
      <h3><button class="standings-conference-toggle" data-standings-conference-toggle data-standings-conference="${escapeAttr(conference)}">${escapeHtml(conference)}</button> Standings</h3>
      <button class="standings-view-all" data-standings-view-all>View All</button>
    </div>
    ${dashboardStandingsTable(rows, viewed, { showTrendDisclosure: true })}
    ${standingsTrendPopover(viewed)}`;
}

function dashboardStandingsTable(rows, user, options = {}) {
  if (!rows.length) return `<div class="empty">No standings yet.</div>`;
  const showTrendDisclosure = Boolean(options.showTrendDisclosure);
  return `
    <div class="table-wrap">
      <table class="data-table dashboard-standings">
        <colgroup>
          <col class="standings-rank-col" />
          <col class="standings-team-col" />
          <col class="standings-record-col" />
          <col class="standings-pct-col" />
          ${showTrendDisclosure ? '<col class="standings-disclosure-col" />' : ""}
        </colgroup>
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>W-L</th>
            <th>Win%</th>
            ${showTrendDisclosure ? '<th class="standings-disclosure-head"><span class="sr-only">Trend</span></th>' : ""}
          </tr>
        </thead>
        <tbody>
          ${rows.map((row, index) => {
            const team = teamLabel(row.team);
            const rank = Number(row.dashboard_conference_rank || index + 1);
            const disclosure = showTrendDisclosure && team === user
              ? `<button type="button" class="standings-trend-disclosure" data-standings-trend-toggle title="Show ${escapeAttr(team)} standings trend" aria-label="Show ${escapeAttr(team)} standings trend" aria-expanded="false">▶</button>`
              : "";
            return `<tr class="${rank === 7 ? "play-in-cutoff-row" : ""}">
              <td class="standings-rank">${rank}.</td>
              <td class="standings-team"><button data-dashboard-team-jump="${escapeAttr(team)}" class="${team === user ? "user-highlight" : ""}">${escapeHtml(team)}</button></td>
              <td class="standings-record">${escapeHtml(`${row.wins || 0}-${row.losses || 0}`)}</td>
              <td>${escapeHtml(winPct(row.win_pct))}</td>
              ${showTrendDisclosure ? `<td class="standings-disclosure">${disclosure}</td>` : ""}
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

function dashboardFreeAgentMarketCard(editable = true, limit = 5, expanded = false) {
  const mode = state.dashboardFreeAgentMode === "current" ? "current" : "upcoming";
  const payload = state.data.dashboardFreeAgents || {};
  const candidates = mode === "current"
    ? (payload.current_candidates || [])
    : marketCandidates(payload);
  const positions = ["PG", "SG", "SF", "PF", "C"];
  const pages = positions
    .map((position) => ({
      key: position,
      label: position,
      rows: candidates
        .filter((player) => String(player.position || "").toUpperCase().includes(position))
        .sort((a, b) => freeAgentSortValue(b) - freeAgentSortValue(a))
        .slice(0, limit),
    }))
    .filter((page) => page.rows.length);
  pages.push({
    key: "all",
    label: "All Positions",
    rows: [...candidates].sort((a, b) => freeAgentSortValue(b) - freeAgentSortValue(a)).slice(0, limit),
  });
  const modeLabel = mode === "current" ? "Current" : "Upcoming";
  const alternateLabel = mode === "current" ? "Upcoming" : "Current";
  const headingHtml = `<button
    type="button"
    class="free-agent-mode-toggle"
    data-free-agent-mode-toggle
    data-limit="${limit}"
    data-expanded="${expanded ? "true" : "false"}"
    title="Show ${alternateLabel.toLowerCase()} free agents"
    aria-label="Show ${alternateLabel.toLowerCase()} free agents"
    ${editable ? "" : "disabled"}
  >${modeLabel}</button> Free Agents`;
  return marketRotatorCard(
    `${modeLabel} Free Agents`,
    pages,
    freeAgentMarketLine,
    "free-agents",
    !editable,
    expanded,
    { headingHtml }
  );
}

function dashboardActionsCard(editable = true, floating = false) {
  const offerCount = Number(state.data.dashboardOffers?.offers?.length || 0);
  const disabled = editable ? "" : "disabled";
  const legalActions = new Set(state.data.dashboard?.legal_actions || []);
  const tradesOpen = legalActions.has("trades") || legalActions.has("draft_trades");
  const actionCount = tradesOpen ? 6 : 3;
  const actions = `
    ${tradesOpen ? `<button class="dashboard-action-button" data-dashboard-trade="builder" ${disabled}>
      <strong>Trade Builder</strong>
    </button>
    <button class="dashboard-action-button" data-dashboard-trade="finder" ${disabled}>
      <strong>Trade Finder</strong>
    </button>` : ""}
    <button class="dashboard-action-button" data-dashboard-player-finder ${disabled}>
      <strong>Player Finder</strong>
    </button>
    <button class="dashboard-action-button" data-dashboard-view="draft" ${disabled}>
      <strong>Prospects</strong>
    </button>
    ${tradesOpen ? `<button class="dashboard-action-button offer-action ${offerCount ? "has-offers" : ""}" data-dashboard-offers ${disabled}>
      <strong>Trade Offers</strong>${offerCount ? `<span>${offerCount}</span>` : ""}
    </button>` : ""}
    <button class="dashboard-action-button" data-dashboard-settings ${disabled}>
      <strong>Settings</strong>
    </button>`;
  if (floating) {
    return `
      <div class="front-office-floating-hub ${state.frontOfficeOpen ? "open" : ""}" data-front-office-launcher>
        <div class="front-office-radial-menu actions-${actionCount}" aria-hidden="${state.frontOfficeOpen ? "false" : "true"}">
          ${actions}
        </div>
        <button type="button" class="front-office-orb" data-front-office-toggle aria-expanded="${state.frontOfficeOpen ? "true" : "false"}" aria-label="${state.frontOfficeOpen ? "Close" : "Open"} Front Office" ${disabled}>
          <span>Front</span><strong>Office</strong><i aria-hidden="true">+</i>
          ${offerCount ? `<em>${offerCount}</em>` : ""}
        </button>
      </div>`;
  }
  return `
    <div class="front-office-launcher ${state.frontOfficeOpen ? "open" : ""}" data-front-office-launcher>
    <div class="dashboard-action-list front-office-expansion" ${state.frontOfficeOpen ? "" : "hidden"}>
      ${actions}
    </div>
    <button type="button" class="front-office-toggle" data-front-office-toggle aria-expanded="${state.frontOfficeOpen ? "true" : "false"}" ${disabled}>
      <span>Front Office</span><strong>${offerCount ? `${offerCount} offer${offerCount === 1 ? "" : "s"}` : "Open"}</strong><i aria-hidden="true">+</i>
    </button>
    </div>`;
}

function marketRotatorCard(title, pages, rowRenderer, id, disabled = false, expanded = false, options = {}) {
  const usable = pages.filter((page) => page.rows?.length);
  return `
    <div class="section-head market-card-head">
      <h3>${options.headingHtml || escapeHtml(title)}</h3>
      <select data-market-select="${escapeAttr(id)}" aria-label="${escapeAttr(`${title} category`)}" ${disabled ? "disabled" : ""}>
        ${usable.map((page, index) => `<option value="${index}">${escapeHtml(page.label)}</option>`).join("")}
      </select>
    </div>
    <div class="market-rotator" data-market-rotator data-market-id="${escapeAttr(id)}">
      ${usable.map((page, index) => `
        <div class="market-slide ${expanded ? "journey-expanded-list" : ""} ${index === 0 ? "active" : ""}">
          <div class="market-list">
            ${page.rows.map(rowRenderer).join("")}
          </div>
        </div>`).join("") || `<div class="empty">No market data available.</div>`}
    </div>
    <div class="rotator-progress"><span></span></div>`;
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

function standingsTrendPopover(team) {
  const data = state.data.dashboardTrends?.standings || {};
  const points = data.points || [];
  return `<aside class="standings-trend-popover" data-standings-trend-popover hidden>
    <div class="standings-trend-popover-head">
      <div>
        <strong>${escapeHtml(team)} Standings Position</strong>
        <small>Week by week conference rank</small>
      </div>
      <button type="button" class="icon-button" data-standings-trend-close title="Close standings trend" aria-label="Close standings trend">×</button>
    </div>
    <div class="standings-trend-popover-chart">
      ${singleLineChart(points, { invert: true, fixedSlots: 26, minValue: 1, maxValue: 30, endLabel: "Season End", empty: "No weekly standings history yet." })}
    </div>
  </aside>`;
}

function developmentTrendCard(rows = []) {
  const candidates = developmentPlayerCandidates(rows);
  ensureDevelopmentSelection(candidates);
  const selectedIds = state.developmentPlayerIds.filter((id) => candidates.some((candidate) => candidate.player_id === id)).slice(0, DEVELOPMENT_LINE_LIMIT);
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
  state.developmentPlayerIds = state.developmentPlayerIds.filter((id) => candidateIds.has(id)).slice(0, DEVELOPMENT_LINE_LIMIT);
  if (state.developmentSelectionTouched) return;
  const preferred = [...candidates].sort((a, b) => {
    const movementDiff = developmentMovementScore(b) - developmentMovementScore(a);
    if (movementDiff) return movementDiff;
    const minuteDiff = Number(b.minutes || 0) - Number(a.minutes || 0);
    if (minuteDiff) return minuteDiff;
    return Number(b.current || 0) - Number(a.current || 0);
  });
  for (const candidate of preferred) {
    if (state.developmentPlayerIds.length >= DEVELOPMENT_LINE_LIMIT) break;
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
          <select data-development-swap="${index}" aria-label="Development player ${index + 1}" title="${escapeAttr(line.name || "Player")}">
            ${developmentPlayerOptions(candidates, selected, line.player_id)}
          </select>
          <button data-development-remove="${escapeAttr(line.player_id)}" title="Remove ${escapeAttr(line.name || "player")}">×</button>
        </div>
      `).join("")}
      ${lines.length < DEVELOPMENT_LINE_LIMIT && addable.length ? `
        <div class="development-add-row">
          <button data-development-add title="Add player">+</button>
          <select data-development-add-select aria-label="Add development player">
            ${addable.map((candidate) => `<option value="${escapeAttr(candidate.player_id)}">${escapeHtml(candidate.name || "Player")}</option>`).join("")}
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
  return [
    "#4f7fe8", "#dc4a59", "#5fb5d6", "#e7a657", "#9b72d5", "#4ca57a",
    "#d46f9e", "#8cac54", "#d77d4c", "#7298c9", "#b76565", "#5eb0a6",
    "#bc8a4c", "#7e78c7", "#c35e82", "#829cbb", "#8aa276",
  ];
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
  const padY = 8;
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
    <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="${options.preserveAspect ? 'xMidYMid meet' : 'none'}" role="img" aria-label="Trend line">
      <path class="trend-grid" d="M${padX} ${padY}H${width - padX}M${padX} ${height / 2}H${width - padX}M${padX} ${height - padY}H${width - padX}" />
      <polyline class="trend-line primary" points="${coords.map((coord) => `${coord.x.toFixed(1)},${coord.y.toFixed(1)}`).join(" ")}" />
      ${coords.map((coord) => `<circle class="trend-dot" cx="${coord.x.toFixed(1)}" cy="${coord.y.toFixed(1)}" r="3"><title>${escapeAttr(coord.point.label || "")}: ${escapeAttr(coord.point.value)} ${escapeAttr(coord.point.record || "")}</title></circle>`).join("")}
      <text class="trend-axis left" x="${padX}" y="${height - 4}">${escapeHtml(rows[0]?.label || "")}</text>
      <text class="trend-axis right" x="${width - padX}" y="${height - 4}">${escapeHtml(options.endLabel || rows[rows.length - 1]?.label || "")}</text>
    </svg>`;
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
  const padY = 10;
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
    <svg class="trend-svg development-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Player development trend">
      <path class="trend-grid" d="M${padX} ${padY}H${width - padX}M${padX} ${height - padY}H${width - padX}" />
      <line class="season-horizon-guide" x1="${padX}" y1="${height / 2}" x2="${width - padX}" y2="${height / 2}"></line>
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
  const isOffseasonRollover = ["offseason", "training_camp"].includes(String(save.phase || "")) && currentDate.slice(5) >= "09-01";
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
  const seenGameIds = new Set();
  const dayGames = games.filter((game) => {
    if (String(game.date || "").slice(0, 10) !== cell.date) return false;
    const gameId = String(game.game_id || game.id || `${game.away_team || game.away}-${game.home_team || game.home}`);
    if (seenGameIds.has(gameId)) return false;
    seenGameIds.add(gameId);
    return true;
  }).sort((a, b) => Number(Boolean(scoreLine(b))) - Number(Boolean(scoreLine(a)))).slice(0, 1);
  const past = cell.date < String(current).slice(0, 10);
  return `<div class="calendar-cell ${past ? "past" : ""}">
    <strong>${Number(cell.date.slice(-2))}</strong>
    <div class="calendar-game-stack">
      ${dayGames.map((game) => calendarGamePill(game, team, past)).join("")}
    </div>
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

function formatDashboardShortDate(value) {
  const [year, month, day] = String(value || "").slice(0, 10).split("-").map(Number);
  if (!year || !month || !day) return "";
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
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

function refreshDashboardTable(button, tableId) {
  if (state.view !== "dashboard" || tableId !== "dashboard-player-summary") return false;
  return refreshDashboardPlayerSummary(button.closest(".player-summary-card"));
}

function refreshDashboardPlayerSummary(card = els.content.querySelector(".player-summary-card")) {
  if (!card) return false;
  const rows = rosterRows(state.data.dashboard || {});
  if (!rows.length) return false;
  const editable = !state.hydrating && teamLabel(state.data.dashboard?.team || state.dashboardTeam) === userTeam();
  card.innerHTML = dashboardPlayerSummaryTable(rows);
  wireDashboardPlayerCards(card);
  wireSummaryContractToggle(card);
  if (editable) {
    wireRotationMinuteInputs(card);
  }
  return true;
}

function wireSummaryContractToggle(root = els.content) {
  root.querySelectorAll("[data-summary-contract-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      state.dashboardContractView = state.dashboardContractView === "chart" ? "table" : "chart";
      refreshDashboardPlayerSummary(button.closest(".player-summary-card"));
    });
  });
}

function refreshDashboardStandings(root) {
  const card = root.closest(".standings-card");
  if (!card) return false;
  card.innerHTML = userConferenceStandings();
  wireDashboardStandingsControls(card);
  wireDashboardTeamJumps(card);
  return true;
}

function wireDashboardTeamJumps(root = els.content) {
  root.querySelectorAll("[data-dashboard-team-jump]").forEach((button) => {
    button.addEventListener("click", async () => {
      await switchDashboardTeam(button.dataset.dashboardTeamJump || userTeam());
    });
  });
}

function wireDashboardPlayerCards(root = els.content) {
  root.querySelectorAll("[data-dashboard-player-card]").forEach((button) => {
    button.addEventListener("click", () => {
      dashboardPlayerCard(button.dataset.dashboardPlayerCard || "");
    });
  });
}

function wireDashboardStandingsControls(root = els.content) {
  root.querySelectorAll("[data-standings-conference-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const current = button.dataset.standingsConference || "East";
      state.dashboardStandingsConference = current === "East" ? "West" : "East";
      if (!refreshDashboardStandings(button)) renderDashboard();
    });
  });
  root.querySelectorAll("[data-standings-view-all]").forEach((button) => {
    button.addEventListener("click", openStandingsModal);
  });
  root.querySelectorAll("[data-standings-trend-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".standings-card");
      const popover = card?.querySelector("[data-standings-trend-popover]");
      if (!card || !popover) return;
      const opening = popover.hidden;
      card.querySelectorAll("[data-standings-trend-toggle]").forEach((toggle) => {
        toggle.classList.toggle("is-open", opening && toggle === button);
        toggle.setAttribute("aria-expanded", opening && toggle === button ? "true" : "false");
      });
      popover.hidden = !opening;
      if (opening) positionStandingsTrendPopover(card, button, popover);
    });
  });
  root.querySelectorAll("[data-standings-trend-close]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = button.closest(".standings-card");
      const popover = card?.querySelector("[data-standings-trend-popover]");
      if (popover) popover.hidden = true;
      card?.querySelectorAll("[data-standings-trend-toggle]").forEach((toggle) => {
        toggle.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  });
}

function positionStandingsTrendPopover(card, button, popover) {
  requestAnimationFrame(() => {
    const cardRect = card.getBoundingClientRect();
    const rowRect = button.closest("tr")?.getBoundingClientRect() || button.getBoundingClientRect();
    const popoverRect = popover.getBoundingClientRect();
    const preferredTop = rowRect.top - cardRect.top + (rowRect.height - popoverRect.height) / 2;
    const maxTop = Math.max(6, cardRect.height - popoverRect.height - 6);
    popover.style.top = `${Math.max(6, Math.min(maxTop, preferredTop))}px`;
  });
}

function wireLeaguePanelControls(root = els.content) {
  root.querySelectorAll("[data-league-panel-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      state.dashboardLeaguePanel = state.dashboardLeaguePanel === "leaders" ? "wire" : "leaders";
      const card = button.closest(".events-card");
      if (!card) return;
      card.innerHTML = leagueEventRotator(Boolean(card.closest(".franchise-journey")));
      wireLeaguePanelControls(card);
      if (state.dashboardLeaguePanel === "leaders") startSummaryLeaderRotator();
      resetDashboardRotatorProgress();
    });
  });
  root.querySelectorAll("[data-league-panel-view-all]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (state.dashboardLeaguePanel === "leaders") await openLeagueLeadersModal();
      else openLeagueEventsModal();
    });
  });
}

function wireRotationMinuteInputs(root = els.content) {
  root.querySelectorAll("[data-minute-player]").forEach((input) => {
    input.addEventListener("input", () => {
      const playerId = input.dataset.minutePlayer;
      const otherLockedTotal = [...state.rotationLockedPlayerIds]
        .filter((id) => id !== playerId)
        .reduce((sum, id) => sum + Number(state.rotationDraft[id] || 0), 0);
      const value = Math.min(Number(input.value), Math.max(0, 240 - otherLockedTotal));
      state.rotationDraft[playerId] = value;
      state.rotationLockedPlayerIds.add(playerId);
      autofillRotationDraft(rosterRows(state.data.dashboard || {}));
      syncRotationInputs(root);
    });
    input.addEventListener("change", () => saveRotationMinutes({ quiet: true }));
  });
}

function wireDashboardStaffControls(editable) {
  if (!editable) return;
  const toggle = els.content.querySelector("[data-staff-market-toggle]");
  const popover = els.content.querySelector("[data-staff-market-popover]");
  const setOpen = (open) => {
    if (!toggle || !popover) return;
    popover.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.classList.toggle("open", open);
  };
  toggle?.addEventListener("click", () => setOpen(popover?.hidden !== false));
  els.content.querySelector("[data-staff-market-close]")?.addEventListener("click", () => setOpen(false));
  els.content.querySelector("[data-staff-market-filter]")?.addEventListener("change", (event) => {
    const role = event.target.value || "all";
    els.content.querySelectorAll("[data-staff-candidate-slot]").forEach((row) => {
      row.hidden = role !== "all" && row.dataset.staffCandidateSlot !== role;
    });
  });
  els.content.querySelectorAll("[data-staff-candidate]").forEach((button) => {
    button.addEventListener("click", () => openDashboardStaffNegotiation(button.dataset.staffCandidate));
  });
  els.content.querySelectorAll(".staff-role-button[data-staff-role]").forEach((button) => {
    button.addEventListener("click", () => fireDashboardStaff(button.dataset.staffRole, button.dataset.staffName || "this staff member"));
  });
}

function wireDashboardOverview(editable) {
  wireSeasonEfficiencyChart();
  els.content.querySelectorAll("[data-season-prospect-sort]").forEach((button) => button.addEventListener("click", () => {
    const key = button.dataset.seasonProspectSort;
    const prior = state.dashboardProspectSort;
    state.dashboardProspectSort = {key, direction: prior.key === key && prior.direction === "asc" ? "desc" : "asc"};
    renderDashboard();
  }));
  els.content.querySelectorAll("[data-unified-workspace]").forEach((button) => {
    button.addEventListener("click", () => {
      const workspace = button.dataset.unifiedWorkspace || "roster";
      if (workspace === state.dashboardWorkspace) return;
      state.dashboardWorkspace = workspace;
      renderDashboard();
    });
  });
  els.content.querySelectorAll("[data-unified-intel-panel]").forEach((button) => {
    button.addEventListener("click", () => {
      const panel = button.dataset.unifiedIntelPanel || "profile";
      if (panel === state.dashboardIntelPanel) return;
      state.dashboardIntelPanel = panel;
      renderDashboard();
    });
  });
  const teamSelect = document.getElementById("dashboardTeamSelect");
  if (teamSelect) {
    teamSelect.addEventListener("change", async (event) => {
      await switchDashboardTeam(event.target.value || userTeam());
    });
  }
  els.content.querySelectorAll("[data-dashboard-team-reset]").forEach((button) => {
    button.addEventListener("click", async () => {
      await switchDashboardTeam(userTeam());
    });
  });
  els.content.querySelectorAll("[data-team-development]").forEach((button) => {
    button.addEventListener("click", openTeamDevelopmentModal);
  });
  wireDashboardTeamJumps();
  els.content.querySelectorAll("[data-front-office-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      state.frontOfficeOpen = !state.frontOfficeOpen;
      const launcher = button.closest("[data-front-office-launcher]");
      const expansion = launcher?.querySelector(".front-office-expansion");
      const radialMenu = launcher?.querySelector(".front-office-radial-menu");
      launcher?.classList.toggle("open", state.frontOfficeOpen);
      if (expansion) expansion.hidden = !state.frontOfficeOpen;
      if (radialMenu) radialMenu.setAttribute("aria-hidden", state.frontOfficeOpen ? "false" : "true");
      button.setAttribute("aria-expanded", state.frontOfficeOpen ? "true" : "false");
      button.setAttribute("aria-label", `${state.frontOfficeOpen ? "Close" : "Open"} Front Office`);
    });
  });
  els.content.querySelectorAll(".front-office-radial-menu .dashboard-action-button").forEach((button) => {
    button.addEventListener("click", () => {
      state.frontOfficeOpen = false;
      const launcher = button.closest("[data-front-office-launcher]");
      launcher?.classList.remove("open");
      launcher?.querySelector(".front-office-radial-menu")?.setAttribute("aria-hidden", "true");
      const toggle = launcher?.querySelector("[data-front-office-toggle]");
      toggle?.setAttribute("aria-expanded", "false");
      toggle?.setAttribute("aria-label", "Open Front Office");
    });
  });
  els.content.querySelectorAll("[data-dashboard-trade]").forEach((button) => {
    button.addEventListener("click", async () => {
      await openTradeRoomModal(button.dataset.dashboardTrade || "builder");
    });
  });
  els.content.querySelectorAll("[data-dashboard-offers]").forEach((button) => {
    button.addEventListener("click", openTradeOffersModal);
  });
  els.content.querySelectorAll("[data-dashboard-player-finder]").forEach((button) => {
    button.addEventListener("click", openPlayerFinderModal);
  });
  els.content.querySelectorAll("[data-award-view-all]").forEach((button) => {
    button.addEventListener("click", openLeagueLeadersModal);
  });
  els.content.querySelectorAll("[data-extension-player]").forEach((button) => {
    button.addEventListener("click", () => openExtensionNegotiation(button.dataset.extensionPlayer || ""));
  });
  els.content.querySelectorAll("[data-dashboard-settings]").forEach((button) => {
    button.addEventListener("click", openSettingsModal);
  });
  wireDashboardStandingsControls();
  wireDashboardPlayerCards();
  wireSummaryContractToggle();
  wireLeaguePanelControls();
  wireFreeAgentModeToggles();
  wireDevelopmentLegend();
  wireDashboardStaffControls(editable);
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
  wireRotationMinuteInputs();
}

function wireFranchiseJourney() {
  const scroller = els.content.querySelector("[data-journey-scroll]");
  const chapters = [...els.content.querySelectorAll("[data-journey-chapter]")];
  const navButtons = [...els.content.querySelectorAll("[data-journey-jump]")];
  const progress = els.content.querySelector(".journey-progress span");
  if (!scroller || !chapters.length) return;

  const activateChapter = (key) => {
    state.journeyChapter = key;
    navButtons.forEach((button) => button.classList.toggle("active", button.dataset.journeyJump === key));
    chapters.forEach((chapter) => chapter.classList.toggle("is-active", chapter.dataset.journeyChapter === key));
  };

  navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.journeyJump;
      const chapter = chapters.find((candidate) => candidate.dataset.journeyChapter === key);
      if (!chapter) return;
      activateChapter(key);
      chapter.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  state.journeyObserver?.disconnect();
  state.journeyObserver = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (visible?.target?.dataset?.journeyChapter) activateChapter(visible.target.dataset.journeyChapter);
  }, { root: scroller, threshold: [0.45, 0.62, 0.8] });
  chapters.forEach((chapter) => state.journeyObserver.observe(chapter));

  const updateProgress = () => {
    if (!progress) return;
    const distance = Math.max(1, scroller.scrollHeight - scroller.clientHeight);
    progress.style.transform = `scaleX(${clampNumber(scroller.scrollTop / distance, 0, 1)})`;
  };
  scroller.addEventListener("scroll", updateProgress, { passive: true });
  updateProgress();

  const logoStage = els.content.querySelector("[data-journey-logo-stage]");
  const hero = els.content.querySelector(".journey-today");
  if (logoStage && hero && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    hero.addEventListener("pointermove", (event) => {
      const bounds = hero.getBoundingClientRect();
      const x = ((event.clientX - bounds.left) / Math.max(1, bounds.width) - 0.5) * 2;
      const y = ((event.clientY - bounds.top) / Math.max(1, bounds.height) - 0.5) * 2;
      logoStage.style.setProperty("--journey-pointer-x", x.toFixed(3));
      logoStage.style.setProperty("--journey-pointer-y", y.toFixed(3));
    });
    hero.addEventListener("pointerleave", () => {
      logoStage.style.setProperty("--journey-pointer-x", "0");
      logoStage.style.setProperty("--journey-pointer-y", "0");
    });
  }

  const initialKey = chapters.some((chapter) => chapter.dataset.journeyChapter === state.journeyChapter)
    ? state.journeyChapter
    : chapters[0].dataset.journeyChapter;
  activateChapter(initialKey);
  if (initialKey !== chapters[0].dataset.journeyChapter) {
    requestAnimationFrame(() => chapters.find((chapter) => chapter.dataset.journeyChapter === initialKey)?.scrollIntoView({ block: "start" }));
  }
}

async function switchDashboardTeam(team) {
  state.dashboardTeam = team || userTeam();
  state.dashboardStandingsConference = "";
  state.rotationDraft = {};
  state.rotationLockedPlayerIds.clear();
  state.startingDraft = null;
  state.startingSavedSignature = "";
  state.startingPickerSlot = null;
  state.developmentPlayerIds = [];
  state.developmentSelectionTouched = false;
  state.hydrating = true;
  setBusy(true);
  try {
    await ensureViewData(true);
  } finally {
    state.hydrating = false;
    setBusy(state.busyDepth > 0);
    renderDashboard();
  }
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
        state.developmentPlayerIds = [...new Set(draft)].slice(0, DEVELOPMENT_LINE_LIMIT);
        renderDashboard();
      }
    });
  });
  const add = els.content.querySelector("[data-development-add]");
  const addSelect = els.content.querySelector("[data-development-add-select]");
  if (add && addSelect) {
    add.addEventListener("click", () => {
      if (state.developmentPlayerIds.length >= DEVELOPMENT_LINE_LIMIT || !addSelect.value) return;
      state.developmentSelectionTouched = true;
      clearDevelopmentNewBadge();
      if (!state.developmentPlayerIds.includes(addSelect.value)) {
        state.developmentPlayerIds = [...state.developmentPlayerIds, addSelect.value].slice(0, DEVELOPMENT_LINE_LIMIT);
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
  state.rotationLockedPlayerIds.clear();
  state.startingDraft = null;
  state.startingSavedSignature = "";
  state.startingPickerSlot = null;

  renderDashboard();
  showToast("Starting 5 updated");
}

async function saveRotationMinutes(options = {}) {
  const minutes = { ...state.rotationDraft };
  const lockedPlayerIds = [...state.rotationLockedPlayerIds];
  const result = await action("set_rotation_minutes", {
    ...savePayload(),
    team: userTeam(),
    minutes,
    locked_player_ids: lockedPlayerIds,
  });
  if (result.status === "blocked") return showToast(result.reason || "Rotation update blocked.", true);
  state.data.dashboard = result.dashboard;
  state.data.statusDashboard = result.dashboard;
  if (options.quiet) {
    if (state.view === "dashboard") renderDashboard();
    return;
  }
  state.rotationDraft = {};
  state.rotationLockedPlayerIds.clear();
  renderDashboard();
  showToast("Rotation saved");
}

function seriesCard(series) {
  const teams = series.teams || [];
  const scores = series.score || [];
  const winner = teamLabel(series.winner);
  const status = rowLabel(series.status || "");
  const gameCount = (series.game_ids || []).length;
  const tag = gameCount ? "button" : "div";
  const interaction = gameCount
    ? `type="button" data-playoff-series="${escapeAttr(series.id || "")}" aria-label="Open latest box score for ${escapeAttr(`${teamLabel(teams[0])} versus ${teamLabel(teams[1])}`)}"`
    : "";
  const title = gameCount
    ? `Open latest box score · ${gameCount} game${gameCount === 1 ? "" : "s"} played`
    : `${rowLabel(series.round || "Series")} · ${status}`;
  const firstTeam = teamLabel(teams[0]);
  const secondTeam = teamLabel(teams[1]);
  return `
    <${tag} class="series-card ${gameCount ? "series-card-button" : "series-card-empty"}" ${interaction} title="${escapeAttr(title)}">
      <div class="series-team ${winner && winner === firstTeam ? "series-team-winner" : ""}">${teamLogoSrc(firstTeam) ? `<img src="${escapeAttr(teamLogoSrc(firstTeam))}" alt="" />` : ""}<strong>${escapeHtml(firstTeam || "TBD")}</strong><span>${scores[0] ?? 0}</span></div>
      <div class="series-team ${winner && winner === secondTeam ? "series-team-winner" : ""}">${teamLogoSrc(secondTeam) ? `<img src="${escapeAttr(teamLogoSrc(secondTeam))}" alt="" />` : ""}<strong>${escapeHtml(secondTeam || "TBD")}</strong><span>${scores[1] ?? 0}</span></div>
    </${tag}>`;
}

function playoffBracket(series, champion) {
  const finals = series.filter((item) => item.round === "finals");
  return `
    <div class="tournament-bracket">
      ${bracketConference("East", series)}
      <div class="bracket-finals">
        <div class="bracket-conference-title">Finals</div>
        ${finals.length ? finals.map((item) => `<div class="bracket-node final-node">${seriesCard(item)}</div>`).join("") : `<div class="bracket-node empty-final">TBD</div>`}
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
  const label = {
    first_round: "First Round",
    conference_semifinals: "Semifinals",
    conference_finals: "Conference Final",
  }[round] || rowLabel(round);
  return `
    <div class="bracket-round bracket-${escapeAttr(round)}">
      <div class="bracket-round-title">${escapeHtml(label)}</div>
      <div class="bracket-node-stack">
        ${roundSeries.length
          ? roundSeries.map((item) => `<div class="bracket-node">${seriesCard(item)}</div>`).join("")
          : `<div class="bracket-node bracket-placeholder">TBD</div>`}
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

function tieredRating(value, key, thresholds = {}) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const boundary = thresholds?.[key] || {};
  const lower = Number(boundary.lower);
  const suppliedMiddle = Number(boundary.middle);
  const upper = Number(boundary.upper);
  // Older in-memory server responses only carried lower/upper tertiles. Keep
  // all four semantic colors available until the refreshed quartile payload
  // arrives; this fallback never changes an engine rating.
  const middle = Number.isFinite(suppliedMiddle)
    ? suppliedMiddle
    : Number.isFinite(lower) && Number.isFinite(upper)
      ? lower + ((upper - lower) / 2)
      : Number.NaN;
  const tier = Number.isFinite(upper) && number >= upper
    ? "legendary"
    : Number.isFinite(middle) && number >= middle
      ? "high"
      : Number.isFinite(lower) && number >= lower
        ? "mid"
        : "low";
  return `<span class="summary-rating rating-tier-${tier}">${number.toFixed(1)}</span>`;
}

function gradeClass(value, high = 70, low = 50) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "neutral";
  if (num >= high) return "good";
  if (num <= low) return "bad";
  return "neutral";
}

function contractSeasons(rows) {
  const active = String(state.home?.save?.season || "");
  const start = Number(active.split("-")[0]);
  if (Number.isFinite(start) && start > 1900) {
    return Array.from({ length: 4 }, (_, offset) => `${start + offset}-${String(start + offset + 1).slice(-2)}`);
  }
  const seasons = new Set();
  for (const row of rows || []) {
    for (const season of Object.keys(row.salary_by_year || {})) seasons.add(season);
  }
  return [...seasons].sort().slice(-4);
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

function isPlayerInjured(health) {
  if (!health) return false;
  const status = String(health.status || "").toLowerCase();
  const label = String(health.label || "").toLowerCase();
  return Boolean(status && !["ok", "healthy", "active"].includes(status)) || Boolean(label && !["ok", "healthy"].includes(label));
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

function wireTradeAssetControls(root) {
  root.querySelectorAll("[data-asset-side]").forEach((button) => {
    button.addEventListener("click", () => toggleAsset(button.dataset.assetSide, button.dataset.assetKind, button.dataset.assetId));
  });
  root.querySelectorAll("[data-remove-side]").forEach((button) => {
    button.addEventListener("click", () => removeAsset(button.dataset.removeSide, button.dataset.assetId));
  });
  root.querySelectorAll("[data-asset-filter-side]").forEach((select) => {
    select.addEventListener("change", () => {
      state.tradeAssetFilters[select.dataset.assetFilterSide] = select.value || "all";
      renderTradeRoom();
    });
  });
}

function tradeCapStrip(cap) {
  const payroll = Number(cap.salary_total_millions || 0);
  const taxRoom = Number(cap.tax_space_millions || 0);
  const hardRoom = Number(cap.hard_cap_space_millions || 0);
  const limit = Math.max(1, payroll + Math.max(0, hardRoom));
  const payrollWidth = clampNumber((payroll / limit) * 100, 5, 100);
  return `
    <div class="trade-cap-strip">
      <div><span>Payroll</span><strong>${money(payroll)}</strong></div>
      <div class="${taxRoom < 0 ? "negative" : "positive"}"><span>Tax room</span><strong>${signedMoney(taxRoom)}</strong></div>
      <div class="${hardRoom < 0 ? "negative" : "positive"}"><span>Hard-cap room</span><strong>${signedMoney(hardRoom)}</strong></div>
      <i><b style="width:${payrollWidth.toFixed(1)}%"></b></i>
    </div>`;
}

function selectedTradeValue(items) {
  return items.reduce((sum, item) => sum + Number(item.trade_value || 0), 0);
}

function selectedPackage(title, items, side, team) {
  const total = selectedTradeValue(items);
  return `
    <section class="trade-selected-package" ${teamBrandStyle(team)}>
      <header>
        <div>${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="" />` : ""}<span>${escapeHtml(title)}</span></div>
        <strong>${total.toFixed(1)}</strong>
      </header>
      <div class="trade-selected-list">
        ${items.length ? items.map((item) => `
          <div class="trade-selected-row">
            ${item.kind==='player'?'':draftAssetGlyph(item,true,true)}<span><b>${escapeHtml(item.label || item.id)}</b><small>${escapeHtml(item.kind === "player" ? item.position || "Player" : item.kind === "pick_swap" ? "Pick swap" : "Draft pick")}</small></span>${item.kind === "player" ? `<em class="trade-selected-overall"><small>OVR</small>${draftMetric(item.ratings?.overall ?? item.overall)}</em>` : ""}
            <button data-remove-side="${escapeAttr(side)}" data-asset-id="${escapeAttr(item.id)}" aria-label="Remove ${escapeAttr(item.label || item.id)}">×</button>
          </div>`).join("") : `<div class="trade-package-empty"><span>+</span><p>Select assets from the roster board</p></div>`}
      </div>
    </section>`;
}

function tradePackageBalance(outgoing, incoming, outgoingTeam, incomingTeam) {
  const outValue = selectedTradeValue(outgoing);
  const inValue = selectedTradeValue(incoming);
  const maxValue = Math.max(1, outValue, inValue);
  const delta = inValue - outValue;
  return `
    <div class="trade-package-balance">
      <div class="trade-balance-labels"><span>${escapeHtml(outgoingTeam)} sends <b>${outValue.toFixed(1)}</b></span><strong class="${Math.abs(delta) < 5 ? "balanced" : delta > 0 ? "positive" : "negative"}">${delta >= 0 ? "+" : ""}${delta.toFixed(1)}</strong><span>${escapeHtml(incomingTeam)} sends <b>${inValue.toFixed(1)}</b></span></div>
      <div class="trade-balance-track"><i class="outgoing" style="width:${(outValue / maxValue * 50).toFixed(1)}%"></i><b></b><i class="incoming" style="width:${(inValue / maxValue * 50).toFixed(1)}%"></i></div>
      <small>Owner-context estimate · final evaluation includes fit, role, contract, and team direction</small>
    </div>`;
}

function toggleAsset(side, kind, id) {
  const source = side === "from" ? state.data.tradeUser : state.data.tradePartner;
  const asset = (source.assets || []).find((item) => item.id === id && item.kind === kind);
  if (!asset) return;
  const list = selectedList(side);
  const existing = list.findIndex((item) => item.id === id);
  if (existing >= 0) list.splice(existing, 1);
  else {
    if (state.tradeTab === "finder" && side === "from" && list.length >= 2) return showToast("Trade Finder can shop up to two assets at once.", true);
    list.push({
      kind: asset.kind,
      id: asset.id,
      value: asset.value || asset.id,
      label: asset.label || asset.name || asset.id,
      trade_value: Number(asset.trade_value || 0),
      position: asset.position || "",
      season: asset.season,
      round: asset.round,
      original_team_id: asset.original_team_id,
      original_team_abbrev: asset.original_team_abbrev,
      original_team_ids: asset.original_team_ids || [],
      original_team_abbrevs: asset.original_team_abbrevs || [],
      protection_summary: asset.protection_summary,
      condition_summary: asset.condition_summary,
      salary_by_year: asset.salary_by_year || {},
      ratings: asset.ratings || {},
      overall: asset.ratings?.overall ?? asset.overall,
    });
  }
  state.tradeCandidate = null;
  if (state.tradeTab === "finder") state.tradeResults = [];
  renderTradeRoom();
}

function selectedList(side) {
  return side === "from" ? state.selectedFrom : state.selectedTo;
}

function removeAsset(side, id) {
  const list = selectedList(side);
  const idx = list.findIndex((item) => item.id === id);
  if (idx >= 0) list.splice(idx, 1);
  state.tradeCandidate = null;
  renderTradeRoom();
}

function assetSpec(asset) {
  return { kind: asset.kind, value: asset.value || asset.id };
}

function tradeReadout(candidate) {
  if (!candidate) return `<div class="trade-evaluation-empty"><span>GM</span><strong>Awaiting evaluation</strong><p>Package legality and each team's decision model will appear here.</p></div>`;
  const legal = candidate.legality?.status || "unknown";
  const canApply = legal === "legal" && (candidate.accepted_by_all || (candidate.evaluations || []).some((row) => row.perspective_team_id !== state.home?.save?.user_team?.id && row.accepted));
  return `
    <div class="trade-evaluation-board">
      <div class="trade-evaluation-title"><span>Engine decision</span><strong>${escapeHtml(tradeHeadline(candidate).replace(/^Trade completed:\s*/i, ""))}</strong><b class="${legal === "legal" ? "legal" : "illegal"}">${escapeHtml(legal)}</b></div>
      <div class="trade-evaluation-grid">${(candidate.evaluations || []).map(tradeEvaluationPanel).join("")}</div>
      ${(candidate.legality?.issues || []).length ? `<div class="trade-legality-issues">${candidate.legality.issues.map((issue) => `<span>${escapeHtml(textValue(issue))}</span>`).join("")}</div>` : ""}
      <button id="applyBuiltTrade" class="trade-execute-button" ${canApply ? "" : "disabled"}>${canApply ? "Accept And Execute" : "Partner Rejects"}</button>
    </div>`;
}

function tradeResultCards(results) {
  if (!results.length) return `<div class="trade-results-empty"><span>↗</span><strong>No market scan yet</strong><p>Select an asset and ask the league. Returned offers are already approved by the AI counterparty.</p></div>`;
  return results.map((result, index) => tradeCandidateCard(result, index, "finder")).join("");
}

function offerCard(offer, index) {
  return tradeCandidateCard(offer, index, "offer");
}

function tradeCandidateCard(candidate, index, mode) {
  const proposal = candidate?.proposal || {};
  const fromTeam = teamLabel(proposal.from_team_id || proposal.from_team || "");
  const toTeam = teamLabel(proposal.to_team_id || proposal.to_team || "");
  const legal = candidate?.legality?.status || "legal";
  const evaluations = candidate?.evaluations || [];
  return `
    <article class="trade-candidate-card ${mode === "offer" ? "incoming" : "market"}">
      <header class="trade-candidate-head">
        <div><span>${mode === "offer" ? "Incoming proposal" : `Market offer ${index + 1}`}</span><strong>${escapeHtml(fromTeam)} <b>↔</b> ${escapeHtml(toTeam)}</strong></div>
        <span class="trade-legal-badge ${legal === "legal" ? "legal" : "illegal"}">${escapeHtml(legal)}</span>
      </header>
      <div class="trade-candidate-matchup">
        ${tradeOfferSide(fromTeam, proposal.from_assets || [], evaluations.find((row) => teamLabel(row.team_abbrev || row.perspective_team_id) === fromTeam))}
        <div class="trade-swap-mark"><span>TRADE</span><b>⇄</b></div>
        ${tradeOfferSide(toTeam, proposal.to_assets || [], evaluations.find((row) => teamLabel(row.team_abbrev || row.perspective_team_id) === toTeam))}
      </div>
      ${mode === "finder" ? tradeSegmentedValueBoard(candidate, proposal.from_assets || [], proposal.to_assets || [], fromTeam, toTeam) : ""}
      <div class="trade-candidate-evals">${evaluations.map(tradeEvaluationPanel).join("")}</div>
      <footer>
        <p>${escapeHtml(tradeHeadline(candidate).replace(/^Trade completed:\s*/i, ""))}</p>
        ${mode === "offer"
          ? `<div><button data-offer-reject="${index}" class="trade-reject-button">Reject</button><button data-offer-accept="${index}" class="trade-accept-button">Accept Trade</button></div>`
          : `<button data-inspect-finder="${index}" class="trade-accept-button">Inspect In Trade Builder</button>`}
      </footer>
    </article>`;
}

function tradeOfferSide(team, assets, evaluation) {
  return `
    <section class="trade-offer-side" ${teamBrandStyle(team)}>
      <header>${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="" />` : ""}<strong>${escapeHtml(team)}</strong><span>SENDS</span></header>
      <div>${assets.length ? assets.map((asset) => `<p><b>${escapeHtml(asset.label || asset.name || asset.value || asset.id || "Asset")}</b><small>${escapeHtml(asset.kind === "player" ? asset.position || "Player" : asset.kind === "pick_swap" ? "Pick swap right" : "Draft capital")}</small></p>`).join("") : `<p><b>Future considerations</b></p>`}</div>
      <footer><span>Incoming value</span><strong>${Number(evaluation?.incoming_value || 0).toFixed(1)}</strong></footer>
    </section>`;
}

function tradeEvaluationPanel(row) {
  const score = clampNumber(Number(row.acceptance_score || 0), 0, 100);
  const net = Number(row.net_value || 0);
  const accepted = Boolean(row.accepted) || String(row.decision || "").toLowerCase() === "accept";
  return `
    <div class="trade-evaluation-panel ${accepted ? "accepted" : "rejected"}">
      <header><strong>${escapeHtml(row.team_abbrev || teamLabel(row.perspective_team_id))}</strong><span>${accepted ? "ACCEPTS" : "DECLINES"}</span></header>
      <div><i style="width:${score.toFixed(1)}%"></i></div>
      <footer><span>Acceptance ${score.toFixed(0)}</span><b class="${net >= 0 ? "positive" : "negative"}">${net >= 0 ? "+" : ""}${net.toFixed(1)} net</b></footer>
    </div>`;
}

function freeAgentOfferPanel(player, exclusive = false) {
  const minimum = 1.9;
  const maximum = Math.max(minimum, Number(state.data.freeagency?.cap?.max_offer_aav_millions || minimum));
  const initial = clampNumber(Number(player.ask_millions || minimum), minimum, maximum);
  return `
    <div class="section-head"><div><h3>${escapeHtml(player.name)}</h3><p class="muted">${escapeHtml(player.position)} age ${escapeHtml(player.age)} ${escapeHtml(player.height)}</p></div><span class="pill">${money(player.ask_millions)} ask</span></div>
    <div class="grid-3">
      <div class="item"><strong>Role</strong><span>${player.mpg} MPG | ${player.ppg} PPG</span></div>
      <div class="item"><strong>Ratings</strong><span>OVR ${player.ratings?.overall || ""} | DEF ${player.ratings?.defense || ""}</span></div>
      <div class="item"><strong>Fit</strong><span>${player.team_fit_score ?? "n/a"}</span></div>
    </div>
    <div class="form-grid">
      <label>AAV<input id="faAav" type="number" min="${minimum.toFixed(1)}" max="${maximum.toFixed(1)}" step="0.1" value="${initial.toFixed(1)}" aria-describedby="faOfferLimit" /></label>
      <label>Years<input id="faYears" type="number" min="1" max="5" step="1" value="2" /></label>
      <span id="faOfferLimit" class="free-agent-offer-limit">Maximum ${money(maximum)} AAV</span>
      <button id="submitFaOffer">${exclusive ? "Offer Re-Signing" : "Make Offer"}</button>
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
      id: prospect.id || prospect.prospect_id || entry.prospect_id,
      rank: entry.board_rank || prospect.rank || "",
      seasonStartRank: entry.season_start_rank ?? prospect.preseason_rank ?? prospect.rank,
      rankChange: entry.rank_change ?? (entry.season_start_rank != null ? Number(entry.season_start_rank) - Number(entry.board_rank || prospect.rank) : null),
      name: prospect.name,
      position: prospect.position,
      age: Number.isFinite(Number(prospect.age)) ? Math.round(Number(prospect.age)) : "",
      height: heightFromRow(prospect),
      now: scout.now ?? prospect.now ?? prospect.current_rating ?? prospect.current_ability,
      potential: scout.potential || prospect.potential || prospect.potential_rating,
      fit: entry.fit_grade || entry.risk_adjusted_grade || entry.grade,
      floor: scout.floor ?? prospect.floor,
      ceiling: scout.ceiling ?? prospect.ceiling,
      scoutedPct: scout.scouted_pct ?? prospect.scouted_pct,
      volatility: prospect.volatility,
      developmentCurve: prospect.development_curve,
      rookieContractValue: prospect.rookie_contract_value,
      confidence: prospect.confidence,
      prospect,
      scout,
      status: entry.draft_status || "available",
      selectedPick: entry.selected_pick,
      selectedTeam: entry.selected_team,
    };
  });
}

function draftMetric(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(1) : "—";
}

function sortDraftBoardRows(rows, sort) {
  const key = sort?.key || "rank";
  const direction = sort?.direction === "desc" ? -1 : 1;
  const numeric = new Set(["rank", "age", "now", "potential", "fit"]);
  return [...rows].sort((left, right) => {
    let comparison = 0;
    if (numeric.has(key)) {
      const leftValue = Number(left[key]);
      const rightValue = Number(right[key]);
      comparison = (Number.isFinite(leftValue) ? leftValue : -Infinity) - (Number.isFinite(rightValue) ? rightValue : -Infinity);
    } else if (key === "height") {
      comparison = heightToInches(left.height) - heightToInches(right.height);
    } else {
      comparison = String(left[key] || "").localeCompare(String(right[key] || ""), undefined, { sensitivity: "base" });
    }
    if (comparison === 0) comparison = Number(left.rank || 999) - Number(right.rank || 999);
    return comparison * direction;
  });
}

function heightToInches(value) {
  const match = String(value || "").match(/(\d+)'(\d+)/);
  return match ? Number(match[1]) * 12 + Number(match[2]) : -Infinity;
}

function draftSortMark(key) {
  const sort = state.draftBoardSort || {};
  if (sort.key !== key) return "";
  return sort.direction === "desc" ? " ↓" : " ↑";
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

function leagueEventRotator(expanded = false) {
  const leadersMode = state.dashboardLeaguePanel === "leaders";
  const fields = state.data.dashboardSummaryLeaders?.fields || [];
  const panelHead = `<div class="section-head events-head league-panel-head">
    <h3><button type="button" class="league-panel-toggle" data-league-panel-toggle title="Switch to ${leadersMode ? "League Wire" : "League Leaders"}">${leadersMode ? "League Leaders" : "League Wire"}</button></h3>
    <div class="league-panel-head-actions">
      ${leadersMode ? `<select id="summaryLeaderSelect" aria-label="League leader category">${fields.map((field, index) => `<option value="${index}">${escapeHtml(field.label || field.key || "Field")}</option>`).join("")}</select>` : ""}
      <button data-league-panel-view-all>View All</button>
    </div>
  </div>`;

  if (leadersMode) {
    return `${panelHead}${summaryLeaderRotator(3, expanded, { header: false })}`;
  }

  const events = state.home?.league_events?.events || [];

  if (!events.length) {
    return `
      ${panelHead}
      <div class="event-rotator empty">
        No recent league events.
      </div>`;
  }

  return `
    ${panelHead}
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

async function openLeagueLeadersModal() {
  const payload = await action("player_finder", savePayload());
  state.playerFinder = {
    payload,
    sortField: payload.default_sort || "overall",
    filterField: "player",
    filterValue: "",
  };
  state.modal = {
    kind: "leagueLeaders",
    title: "League Leaders",
    subtitle: `${payload.rows?.length || 0} league players · ${payload.as_of_date || ""}`,
    body: playerFinderModalBody(),
  };
  renderModal();
}

function openLeagueEventsModal() {
  const events = state.home?.league_events?.events || [];
  state.modal = {
    kind: "leagueEvents",
    title: "League Wire",
    subtitle: `${events.length} recent events · ${state.home?.save?.current_date || ""}`,
    body: `<div class="league-events-modal-list">
      ${events.map((event) => {
        const normalized = normalizeLeagueEvent(event);
        return `<article class="league-event-modal-row">
          <div><strong>${escapeHtml(normalized.date)}</strong><span>${escapeHtml(normalized.kind || "league")}</span></div>
          <p>${escapeHtml(normalized.text)}</p>
        </article>`;
      }).join("") || `<div class="empty">No league events available.</div>`}
    </div>`,
  };
  renderModal();
}

function leagueEventSlide(event) {
  const normalized = normalizeLeagueEvent(event);
  const teamMarks = normalized.teams.map((team) => leagueEventTeamMark(team)).join("");

  return `
    <div class="event-slide">
      <div class="event-team-marks">${teamMarks}</div>
      <div class="event-slide-copy">
        <strong>${escapeHtml(normalized.date)}${normalized.kind ? ` ${escapeHtml(normalized.kind)}` : ""}</strong>
        <p>${escapeHtml(normalized.text)}</p>
      </div>
    </div>`;
}

function leagueEventTeamMark(team) {
  const logo = teamLogoSrc(team);
  if (!logo) return "";
  return `<svg class="event-team-logo" viewBox="0 0 48 48" role="img" aria-label="${escapeAttr(team)}">
    <image href="${escapeAttr(logo)}" x="2" y="2" width="44" height="44" preserveAspectRatio="xMidYMid meet"></image>
  </svg>`;
}

function leagueEventTeams(event, text) {
  const known = new Set(Object.keys(TEAM_BRAND_COLORS));
  const candidates = [];
  const teamIds = [
    ...(Array.isArray(event?.team_ids) ? event.team_ids : []),
    event?.team_id,
    event?.details?.team_id,
    event?.details?.from_team_id,
    event?.details?.to_team_id,
  ].filter(Boolean);
  for (const id of teamIds) {
    const team = state.teams.find((candidate) => String(candidate.id || candidate.team_id || "") === String(id));
    const abbrev = teamLabel(team || id);
    if (known.has(abbrev) && !candidates.includes(abbrev)) candidates.push(abbrev);
  }
  for (const token of String(text || "").match(/\b[A-Z]{2,3}\b/g) || []) {
    if (known.has(token) && !candidates.includes(token)) candidates.push(token);
  }
  return candidates.slice(0, 2);
}

function normalizeLeagueEvent(event) {
  if (typeof event === "string") {
    return {
      date: "",
      kind: "",
      text: event,
      teams: leagueEventTeams({}, event),
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
    teams: leagueEventTeams(event, textValue(text || event)),
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

function rating(row, key) {
  const ratings = row.display_ratings || row.ratings || row.attributes || row.traits || {};
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
  const explicit = candidate?.headline || candidate?.summary?.headline || candidate?.proposal?.headline;
  if (explicit) return explicit;
  const proposal = candidate?.proposal || {};
  const fromTeam = teamLabel(proposal.from_team_id || proposal.from_team || "");
  const toTeam = teamLabel(proposal.to_team_id || proposal.to_team || "");
  const labels = (assets) => (assets || []).map((asset) => asset.label || asset.name || asset.value).filter(Boolean).join(", ") || "future considerations";
  if (fromTeam || toTeam) return `${fromTeam || "One team"} sends ${labels(proposal.from_assets)}; ${toTeam || "the other team"} sends ${labels(proposal.to_assets)}.`;
  return "Trade offer";
}

function money(value) {
  if (value === undefined || value === null || value === "") return "";
  const num = Number(value);
  if (Number.isFinite(num)) return `$${num.toFixed(1)}M`;
  return String(value);
}

function compactMarketMoney(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return `$${num.toFixed(1).replace(/\.0$/, "")}M`;
}

function compactSalaryYears(rows) {
  return Object.entries(rows || {})
    .filter(([, value]) => value !== null && value !== undefined)
    .sort(([left], [right]) => left.localeCompare(right))
    .slice(0, 2)
    .map(([season, value]) => `${season} ${money(value)}`)
    .join(" / ") || "—";
}

function signedMoney(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "";
  return `$${num >= 0 ? "+" : ""}${num.toFixed(1)}M`;
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
  const multiplayerTeam = multiplayerTeamAbbrev();
  if (multiplayerTeam) return multiplayerTeam;
  return teamLabel(state.home?.save?.user_team || state.home?.save?.team || "");
}

function setBusy(isBusy) {
  state.busy = isBusy;
  document.body.classList.toggle("busy", isBusy);
  for (const control of document.querySelectorAll("button, select, input, textarea")) {
    if (isBusy) {
      if (!control.disabled) {
        control.dataset.busyDisabled = "true";
        control.disabled = true;
      }
      continue;
    }
    if (control.dataset.busyDisabled === "true") {
      control.disabled = false;
      delete control.dataset.busyDisabled;
    }
  }
}

function setAppLoading(visible) {
  const dialog = document.getElementById("appLoading");
  if (!dialog) return;
  dialog.hidden = !visible;
  dialog.setAttribute("aria-hidden", String(!visible));
}

async function showAppLoading() {
  const startedAt = performance.now();
  setAppLoading(true);
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  return startedAt;
}

async function hideAppLoading(startedAt) {
  if (startedAt !== null) {
    const remaining = 400 - (performance.now() - startedAt);
    if (remaining > 0) await new Promise(resolve => setTimeout(resolve, remaining));
  }
  setAppLoading(false);
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
