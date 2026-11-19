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
  dashboardOpponentSort: { key: "overall", direction: "desc" },
  calendarMonth: "",
  expandedContractSeason: "",
  rotationDraft: {},
  rotationDraftDate: null,
  rotationLockedPlayerIds: new Set(),
  sorts: {},
  leagueTab: "standings",
  leagueStat: "points",
  leagueTrait: "overall",
  playoffStatsSort: { key: "points_per_game", direction: "desc" },
  draftPresentationStage: "",
  draftPresentationKey: "",
  draftBoardFilter: "available",
  draftBoardSort: { key: "rank", direction: "asc" },
  dashboardProspectSort: { key: "rank", direction: "asc" },
  selectedDraftProspect: "",
  draftSelectionPickKey: "",
  draftLedgerCenteredKey: "",
  draftPlaybackRunning: false,
  draftPlaybackReveal: null,
  tradeTab: "builder",
  tradePartner: "",
  tradeAssetFilters: { from: "all", to: "all" },
  selectedFrom: [],
  selectedTo: [],
  tradeCandidate: null,
  tradeResults: [],
  tradeSearchCompleted: false,
  selectedFreeAgent: null,
  freeAgentCompareIds: [],
  freeAgentCompareMode: false,
  freeAgentMarketSort: { key: "overall", direction: "desc" },
  freeAgentMarketScope: "market",
  freeAgentShortlistIds: [],
  freeAgentFiltersOpen: false,
  freeAgentMarketFilters: { search: "", position: "all", minOverall: "" },
  playerCardDetails: {},
  clipboardPlayerCards: [],
  clipboardPlayerCardSequence: 0,
  staffSlot: "",
  selectedStaff: null,
  modal: null,
  tutorial: null,
  tutorialReturnFocus: null,
  tutorialStartTimer: null,
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
  simulationProcessedGames: new Set(),
  simulationRunning: false,
  simulationPlayerRatingsById: null,
  simulationId: "",
  simulationOfferIds: new Set(),
  simulationOfferCount: 0,
  simulationStopRequested: false,
  tradeDeadlineAcknowledgedSave: "",
  tradeDeadlineAcknowledgedDate: "",
  postseasonReviewedSave: "",
  postseasonReviewedDate: "",
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
const TUTORIAL_COMPLETED_KEY = "nbaGmFirstRunTutorialCompleted";
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
  "set_team_wants",
  "acknowledge_team_wants",
  "submit_free_agent_offer",
  "waive_player",
]);
const DEVELOPMENT_LINE_LIMIT = 9;
const MULTIPLAYER_LOCAL_ACTIONS = new Set(["teams", "list_saves", "create_save", "runtime_status", "diagnostic_runtime", "export_save", "restore_save", "recover_save"]);
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
    "startupSaveSelect",
    "startupRefreshSaves",
    "startupLoadSave",
    "startupSaveHealth",
    "startupSaveMessage",
    "startupExportSave",
    "startupRecoverSave",
    "startupRestoreSave",
    "startupRestoreName",
    "startupRestoreFile",
    "teamSelect",
    "startupTeamWheel",
    "startupTeamSelectedLogo",
    "startupTeamSelectedFallback",
    "startupTeamSelectedName",
    "gameModeSelect",
    "saveName",
    "createSave",
    "nav",
    "startupScreen",
    "content",
    "toast",
    "modalRoot",
    "gameTutorial",
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
  init();
});

function gameCommands() {
  const ready = () => Boolean(state.currentSave && !state.hydrating);
  const navigate = (view) => async () => {
    closeAllModals();
    if (["staff", "calendar", "draft", "playoffs", "freeagents", "freeagency"].includes(view)) return openClipboardWindow(view);
    state.view = view;
    await ensureViewData();
    render();
  };
  const click = selector => () => GameInterface.findControl(selector, {includeHidden:true})?.click();
  const available = selector => () => ready() && Boolean(GameInterface.findControl(selector, {includeHidden:true}));
  const commands = [
    {label:"This season", keys:"g h", run:navigate("dashboard"), available:ready},
    {label:"Cards gallery", keys:"g c", run:click(".card-board-gallery-toggle"), available:available(".card-board-gallery-toggle")},
    {label:"Switch windows", keys:"g w", run:click("[data-window-switcher-open]"), available:available("[data-window-switcher-open]")},
    {label:"Snap cards", keys:"g r", run:click("[data-board-snap]"), available:available("[data-board-snap]")},
    {label:"Trade builder", keys:"g t", run:() => openTradeRoomModal("builder"), available:() => ready() && ["trades","draft_trades"].some(a => clipboardLegalActions().has(a))},
    {label:"Trade finder", keys:"g b", run:() => openTradeRoomModal("finder"), available:() => ready() && ["trades","draft_trades"].some(a => clipboardLegalActions().has(a))},
    {label:"Trade offers", keys:"g o", run:openTradeOffersModal, available:() => ready() && ["trades","draft_trades"].some(a => clipboardLegalActions().has(a))},
    {label:"Player finder", keys:"g f", run:openPlayerFinderModal, available:ready},
    {label:"Free agents", keys:"g a", run:navigate("freeagents"), available:() => ready() && dashboardPhaseKind() !== "fantasy_draft"},
    {label:"Standings", keys:"g l", run:openStandingsModal, available:() => ready() && Boolean(state.data.dashboardStandings)},
    {label:"Settings", keys:"g ,", run:openSettingsModal, available:ready},
    {label:dashboardPhaseKind() === "playoffs" ? "One game per series" : "Next event / one pick", keys:"s e", run:click('[data-advance="next-event"], #fantasySimOne, #draftSimCurrent, #faAdvanceDay, #reSignAdvanceDay'), available:available('[data-advance="next-event"], #fantasySimOne, #draftSimCurrent, #faAdvanceDay, #reSignAdvanceDay')},
    {label:dashboardPhaseKind() === "playoffs" ? "One full series" : "Simulate week", keys:"s w", run:click('[data-advance="week"]'), available:available('[data-advance="week"]')},
    {label:dashboardPhaseKind() === "playoffs" ? "Finish playoffs" : "Simulate month", keys:"s m", run:click('[data-advance="month"]'), available:available('[data-advance="month"]')},
    {label:"Simulate to my pick", keys:"s p", run:click('#draftToUser, #fantasyToUser'), available:available('#draftToUser, #fantasyToUser')},
    {label:"Next phase", keys:"s n", run:click('#postseasonAdvance, #draftRevealLottery, #draftEnterNight, #draftAdvanceStage, #faAdvanceStage, [data-advance="next-season"]'), available:available('#postseasonAdvance, #draftRevealLottery, #draftEnterNight, #draftAdvanceStage, #faAdvanceStage, [data-advance="next-season"]')},
    {label:"Keyboard shortcuts", run:() => GameInterface.openPalette(true)},
  ];
  return commands.map(c => ({group:c.keys?.startsWith('s ') ? 'Simulation' : 'Navigation', ...c}));
}

function closeAllModals() {
  if (state.modal?.kind === "staffNegotiation" && state.modal.submitting) return;
  while (state.modal) closeModal();
}

function wireEvents() {
  els.gameTutorial.addEventListener("click", (event) => {
    const button = event.target.closest("[data-tutorial-action]");
    if (!button) return;
    if (button.dataset.tutorialAction === "previous") moveGameTutorial(-1);
    if (button.dataset.tutorialAction === "next") moveGameTutorial(1);
    if (button.dataset.tutorialAction === "skip") finishGameTutorial();
  });
  document.addEventListener("keydown", handleGameTutorialKeydown, true);
  document.addEventListener("click", blockGameTutorialBackgroundEvent, true);
  document.addEventListener("pointerdown", blockGameTutorialBackgroundEvent, true);
  document.addEventListener("submit", blockGameTutorialBackgroundEvent, true);
  document.addEventListener("wheel", handleGameTutorialWheel, { capture: true, passive: false });
  window.addEventListener("resize", repositionGameTutorial);
  window.addEventListener("scroll", repositionGameTutorial, true);
  els.startupRefreshSaves.addEventListener("click", () => loadSaves().catch(showStartupSaveError));
  els.startupExportSave.addEventListener("click", exportStartupSave);
  document.getElementById("startupReportIssue")?.addEventListener("click", openIssueReport);
  els.startupRecoverSave.addEventListener("click", recoverStartupSave);
  els.startupRestoreSave.addEventListener("click", () => {
    if (!els.startupRestoreName.value.trim()) {
      setStartupSaveMessage("Enter a new save name for the restored backup.", true);
      els.startupRestoreName.focus();
      return;
    }
    els.startupRestoreFile.click();
  });
  els.startupRestoreFile.addEventListener("change", restoreStartupSave);
  els.startupTeamWheel.addEventListener("click", (event) => {
    const option = event.target.closest("[data-team-value]");
    if (option) selectStartupTeam(option.dataset.teamValue);
  });
  els.startupTeamWheel.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const options = [...els.startupTeamWheel.querySelectorAll("[data-team-value]")];
    const current = options.findIndex((option) => option.dataset.teamValue === els.teamSelect.value);
    const next = event.key === "Home" ? 0
      : event.key === "End" ? options.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + options.length) % options.length;
    const option = options[next];
    if (option) {
      selectStartupTeam(option.dataset.teamValue, { focus: true });
    }
  });
  els.startupScreen.addEventListener("click", (event) => {
    const step = event.target.closest("[data-startup-wheel-step]");
    if (step) stepStartupTeam(Number(step.dataset.startupWheelStep));
  });
  els.startupSaveSelect.addEventListener("change", () => {
    setStartupSaveMessage("");
    updateStartupSaveControls();
  });
  els.startupLoadSave.addEventListener("click", loadStartupSave);
  els.createSave.addEventListener("click", () => createSave().catch(showStartupSaveError));
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
    if (["staff", "calendar", "draft", "playoffs", "freeagents", "freeagency"].includes(button.dataset.view)) return openClipboardWindow(button.dataset.view);
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
    const stopSimulation = event.target.closest("[data-simulation-stop]");
    if (stopSimulation) {
      event.preventDefault();
      requestSimulationStop();
      return;
    }
    const command = event.target.closest('[data-phase-command]');
    if (command && !command.disabled) {
      const handlers = {
        'postseason-exit':()=>advance({postseason_exit:true}),
        'lottery-reveal':()=>state.data.draft?.lottery?.revealed ? runLotteryReveal() : draftRevealLottery(),
        'lottery-skip':()=>finishLotteryReveal(), 'draft-enter':draftEnterNight,
        'draft-apply':draftApplyCurrent, 'draft-one':()=>draftSim('draft_sim_current'),
        'draft-user':()=>draftSim('draft_sim_to_user'), 'draft-all':()=>draftSim('draft_sim_all'),
        'draft-next':draftAdvanceStage,
      };
      const run = handlers[command.dataset.phaseCommand];
      if (run) Promise.resolve().then(run).catch(error=>showToast(error.message || String(error),true));
      return;
    }
    if (event.target.closest("[data-trade-deadline-open]")) return showTradeDeadlinePrompt();
    if (event.target.closest("[data-interface-shortcuts]")) return GameInterface.openPalette(true);
    if (event.target.closest("[data-interface-home]")) {
      state.view = "dashboard";
      render();
      return;
    }
    const button = event.target.closest("[data-advance]");
    if (!button) return;

    const mode = button.dataset.advance;

    if (dashboardPhaseKind() === "playoffs" && ["next-event", "week", "month"].includes(mode)) {
      return advance({ next_event:true, postseason_sim:{"next-event":"game", week:"series", month:"all"}[mode] });
    }
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
    await apiGet("/api/status");
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

let apiSessionPromise = null;

async function apiHeaders(actionName = "") {
  if (!apiSessionPromise) {
    apiSessionPromise = (async () => {
      const response = await fetch("/api/session", { cache: "no-store", mode: "same-origin", credentials: "same-origin" });
      if (!response.ok) {
        const message = response.status === 403
          ? "The local game session was rejected. Refresh this page to reconnect."
          : `The local game server is not responding (HTTP ${response.status}). Start the game server and try again.`;
        throw new Error(message);
      }
      const session = await response.json();
      if (typeof session.token !== "string" || !session.token) throw new Error("The local game session could not be established. Refresh this page to reconnect.");
      return session.token;
    })().catch(error => {
      apiSessionPromise = null;
      throw error;
    });
  }
  const headers = { "Content-Type": "application/json", "X-NBA-GM-Token": await apiSessionPromise };
  if (actionName.replaceAll("-", "_") === "restore_save") headers["X-NBA-GM-Backup-Upload"] = "1";
  return headers;
}

async function apiGet(path) {
  const response = await fetch(path, { cache: "no-store", mode: "same-origin", headers: await apiHeaders() });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function action(name, payload = {}, options = {}) {
  if (state.tutorial) throw new Error("Finish the tutorial before using game actions.");
  if (state.draftPlaybackRunning && !["home", "team_dashboard"].includes(name)) throw new Error("Wait for the draft simulation to finish.");
  if (state.simulationRunning && (name === 'advance_save' ? !options.progress : MULTIPLAYER_MUTATIONS.has(name))) throw new Error('Wait for the simulation to finish.');
  if (state.lotteryRevealRunning && MULTIPLAYER_MUTATIONS.has(name)) throw new Error('Finish or skip the lottery reveal first.');
  if (requiredClipboardDecision() && /^(advance_|simulate_playoff_|draft_sim_|fantasy_draft_sim_|draft_apply_current$|draft_reveal_lottery$|fantasy_draft_pick$)/.test(name)) {
    revealRequiredClipboardDecision();
    throw new Error("Resolve the required clipboard decision before advancing.");
  }
  state.busyDepth += 1;
  setBusy(true);
  const feedbackStarted = Date.now();
  let feedbackSucceeded = false;
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
      feedbackSucceeded = true;
      return response.result ?? response;
    }
    const response = await fetch(options.progress ? "/api/action/stream" : "/api/action", {
      method: "POST",
      mode: "same-origin",
      headers: await apiHeaders(name),
      body: JSON.stringify({ action: name, payload, ...(options.simulationId ? {simulation_id:options.simulationId} : {}) }),
    });
    if (options.progress) {
      const result = await GameSimulation.readStream(response, options.progress);
      feedbackSucceeded = true;
      return result;
    }
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || `${response.status} ${response.statusText}`);
    feedbackSucceeded = true;
    return data.result;
  } finally {
    globalThis.GameFeedback?.recordAction(name, Date.now() - feedbackStarted, feedbackSucceeded);
    state.busyDepth = Math.max(0, state.busyDepth - 1);
    setBusy(state.busyDepth > 0 || state.hydrating);
  }
}

async function multiplayerRequest(name, payload = {}) {
  const session = state.multiplayer.session || {};
  const response = await fetch("/api/multiplayer", {
    method: "POST",
    mode: "same-origin",
    headers: await apiHeaders(),
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
  renderStartupTeamWheel();
}

function renderStartupTeamWheel() {
  const teams = [
    { abbrev: "random", name: "Random team" },
    ...state.teams,
  ];
  els.startupTeamWheel.innerHTML = teams.map((team) => {
    const value = team.abbrev || "random";
    const label = value === "random" ? "Random team" : `${team.name || value} (${value})`;
    const mark = value === "random"
      ? '<span class="startup-wheel-random-mark" aria-hidden="true">?</span>'
      : `<img src="/assets/team_logos/${escapeAttr(value)}.png" alt="" loading="lazy" />`;
    return `<button type="button" class="startup-team-option" data-team-value="${escapeAttr(value)}" role="radio" aria-checked="false" tabindex="-1" title="${escapeAttr(label)}"><span class="startup-team-logo">${mark}</span><span class="startup-wheel-sr-label">${escapeHtml(label)}</span></button>`;
  }).join("");
  selectStartupTeam(els.teamSelect.value || "random", { behavior: "auto" });
}

function selectStartupTeam(value, { behavior = "smooth", focus = false } = {}) {
  const valid = value === "random" || state.teams.some((team) => team.abbrev === value);
  const selected = valid ? value : "random";
  els.teamSelect.value = selected;
  window.StartupVideoBackdrop?.selectTeam(selected);
  const team = state.teams.find((row) => row.abbrev === selected);
  const label = team ? `${team.abbrev} · ${team.name || team.abbrev}` : "Random team";
  els.startupTeamSelectedName.textContent = label;
  els.startupTeamSelectedLogo.hidden = !team;
  els.startupTeamSelectedFallback.hidden = Boolean(team);
  if (team) {
    els.startupTeamSelectedLogo.src = `/assets/team_logos/${encodeURIComponent(team.abbrev)}.png`;
    els.startupTeamSelectedLogo.alt = "";
  }
  for (const option of els.startupTeamWheel.querySelectorAll("[data-team-value]")) {
    const isSelected = option.dataset.teamValue === selected;
    option.setAttribute("aria-checked", String(isSelected));
    option.tabIndex = isSelected ? 0 : -1;
    option.classList.toggle("is-locked", isSelected);
    if (isSelected) {
      option.scrollIntoView({ behavior, block: "nearest", inline: "center" });
      if (focus) option.focus({ preventScroll: true });
    }
  }
}

function stepStartupTeam(direction) {
  const options = [...els.startupTeamWheel.querySelectorAll("[data-team-value]")];
  if (!options.length) return;
  const current = options.findIndex((option) => option.dataset.teamValue === els.teamSelect.value);
  const next = (current + direction + options.length) % options.length;
  selectStartupTeam(options[next].dataset.teamValue, { focus: true });
}

async function loadSaves() {
  const data = await action("list_saves");
  const previousSelection = els.startupSaveSelect.value || state.currentSave;
  state.saves = (data.saves || []).filter((save) => save.path);
  els.startupSaveSelect.innerHTML = state.saves.length
    ? state.saves.map((save) => `<option value="${escapeAttr(save.path)}">${escapeHtml(save.name || "Unnamed save")} | ${save.status === "ok" ? `${escapeHtml(save.team || "?")} | ${escapeHtml(save.current_date || "")}` : "Needs recovery"}</option>`).join("")
    : '<option value="">No saves yet</option>';
  if (!state.saves.some((save) => save.status === "ok" && save.path === state.currentSave)) {
    state.currentSave = "";
    localStorage.removeItem(LAST_SAVE_KEY);
  }
  const selectedPath = state.currentSave || previousSelection;
  if (state.saves.some((save) => save.path === selectedPath)) els.startupSaveSelect.value = selectedPath;
  updateStartupSaveControls();
  try {
    await refreshHome();
  } catch (error) {
    // A component can disappear after listing, including during automatic resume.
    const failedSave = state.saves.find((save) => save.path === state.currentSave);
    if (failedSave) {
      failedSave.status = "unreadable";
      failedSave.error = `${error.message || String(error)} Use Refresh to check this save again.`;
    }
    state.currentSave = "";
    state.home = null;
    state.hydrating = false;
    localStorage.removeItem(LAST_SAVE_KEY);
    render();
    showStartupSaveError(error);
    throw error;
  }
}

function selectedStartupSave() {
  return state.saves.find((save) => save.path === els.startupSaveSelect.value);
}

function updateStartupSaveControls() {
  const save = selectedStartupSave();
  const healthy = save?.status === "ok";
  const busy = state.busy || state.hydrating;
  els.startupLoadSave.disabled = busy || !healthy;
  els.startupExportSave.disabled = busy || !healthy;
  els.startupRecoverSave.disabled = busy || !save?.recovery_available;
  els.startupSaveHealth.textContent = save && !healthy
    ? `${save.error || "This save could not be read."} ${save.recovery_available ? "Use Recover Previous to restore its last complete backup, or restore an exported backup below." : "Restore an exported backup below. Keep the existing save files for troubleshooting."}`
    : save?.recovery_available ? "Previous complete backup available." : "";
  els.startupSaveHealth.classList.toggle("is-error", Boolean(save && !healthy));
  els.startupSaveHealth.hidden = !els.startupSaveHealth.textContent;
}

function setStartupSaveMessage(message, isError = false) {
  els.startupSaveMessage.textContent = message;
  els.startupSaveMessage.classList.toggle("is-error", isError);
  els.startupSaveMessage.hidden = !message;
}

function showStartupSaveError(error) {
  const message = error.message || String(error);
  setStartupSaveMessage(message, true);
  showToast(message, true);
}

async function loadStartupSave() {
  const save = selectedStartupSave();
  if (save?.status !== "ok") return;
  state.currentSave = save.path;
  localStorage.setItem(LAST_SAVE_KEY, state.currentSave);
  state.view = "dashboard";
  state.dashboardTeam = "";
  try {
    await refreshHome();
  } catch (error) {
    state.currentSave = "";
    state.home = null;
    localStorage.removeItem(LAST_SAVE_KEY);
    await loadSaves().catch(() => render());
    showStartupSaveError(error);
  }
}

async function exportStartupSave() {
  const save = selectedStartupSave();
  if (save?.status !== "ok") return;
  try {
    setStartupSaveMessage("Preparing complete backup…");
    const result = await action("export_save", { save_path: save.path });
    const bytes = Uint8Array.from(atob(result.archive_base64), (char) => char.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/zip" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename || "nba-gm-backup.zip";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setStartupSaveMessage("Complete backup prepared for download. Keep the ZIP file to restore this save on another computer.");
  } catch (error) {
    showStartupSaveError(error);
  }
}

function readStartupBackup(file) {
  if (file.size > 128 * 1024 * 1024) return Promise.reject(new Error("Backup is too large. The maximum ZIP size is 128 MB."));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("The backup file could not be read. Choose the file again."));
    reader.onabort = () => reject(new Error("Reading the backup was interrupted. Choose the file again."));
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.readAsDataURL(file);
  });
}

async function restoreStartupSave() {
  const file = els.startupRestoreFile.files?.[0];
  if (!file) return;
  const saveName = els.startupRestoreName.value.trim();
  if (!saveName) {
    els.startupRestoreFile.value = "";
    setStartupSaveMessage("Enter a new save name for the restored backup.", true);
    return;
  }
  state.busyDepth += 1;
  setBusy(true);
  try {
    setStartupSaveMessage("Validating and restoring backup…");
    const archive = await readStartupBackup(file);
    const result = await action("restore_save", { save_name: saveName, archive_base64: archive });
    await loadSaves();
    els.startupSaveSelect.value = result.save_path;
    els.startupRestoreName.value = "";
    setStartupSaveMessage(`Restored as ${saveName}. Select Enter Save to continue.`);
  } catch (error) {
    showStartupSaveError(error);
  } finally {
    els.startupRestoreFile.value = "";
    state.busyDepth = Math.max(0, state.busyDepth - 1);
    setBusy(state.busyDepth > 0 || state.hydrating);
    updateStartupSaveControls();
  }
}

async function recoverStartupSave() {
  const save = selectedStartupSave();
  if (!save?.recovery_available) return;
  if (!window.confirm(`Recover ${save.name || "this save"} from its previous complete backup? Progress after that backup will be rolled back. The current valid save, if readable, will be preserved as a backup.`)) return;
  try {
    setStartupSaveMessage("Restoring previous complete backup…");
    const result = await action("recover_save", { save_path: save.path });
    await loadSaves();
    els.startupSaveSelect.value = result.save_path;
    updateStartupSaveControls();
    setStartupSaveMessage("Previous complete backup restored. Select Enter Save to continue.");
  } catch (error) {
    showStartupSaveError(error);
  }
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
    maybeCelebrateChampion();
    queueFirstRunTutorial();
    if(typeof maybeShowWantReminder==='function')maybeShowWantReminder();
  }
}

const GAME_TUTORIAL_STEPS = [
  {
    title: "Welcome to your front office",
    target: ['[data-view="dashboard"]', "#nav"],
    body: "This is your franchise workspace. Your cards bring together the roster, rotation, team trends, schedule, staff and league information. The tour introduces the main decisions and how they show up in game results.",
  },
  {
    title: "Arrange your workspace",
    target: ["[data-card-board-tools]", ".season-command-actions"],
    body: "Cards opens the gallery, where you can add or restore windows. Drag a title bar to move a card; Snap packs the visible cards together without restoring minimized ones. Windows switches among open cards.",
  },
  {
    title: "Window controls",
    card: "minutes",
    target: ['[data-board-window="minutes"] .card-board-titlebar', ".card-board-titlebar", "[data-card-board-tools]"],
    body: "Use the title bar to move a window; the corner grips resize it proportionally. M minimizes or restores, P pins, Space toggles expanded/default, Esc closes, and Shift+Esc minimizes or restores. Option+Tab cycles windows forward; Option+` goes backward (Alt on Windows).",
  },
  {
    title: "Set the rotation",
    card: "minutes",
    target: ['[data-board-window="minutes"] .card-board-titlebar', ".season-minutes-panel", "[data-card-board-tools]"],
    body: "Minutes are one of your most direct coaching decisions. Slider changes save immediately and rebalance unlocked players to 240 team minutes. Blue sliders are your fixed targets; actual game minutes can vary with health and overtime. Use player cards for ratings and context.",
  },
  {
    title: "How team performance is made",
    card: "signals",
    target: ['[data-board-window="signals"] .card-board-titlebar', ".season-signals-panel", ".season-identity-panel"],
    body: "Game results and box scores come from the players on the floor and the minutes they get, shaped by lineup fit, morale, fatigue, injuries and coaching. Overall rating is only one input: role fit and deployment matter too. The box score reflects those interactions rather than simply repeating player ratings.",
  },
  {
    title: "Health and development",
    card: "development",
    target: ['[data-board-window="development"] .card-board-titlebar', ".season-development-panel", '[data-board-window="minutes"] .card-board-titlebar'],
    body: "Fatigue and injuries affect who is ready to play, so balance workload with recovery. Player Development separates season growth/regression from the latest month. Treat those trends as a trajectory to manage, not a guaranteed outcome.",
  },
  {
    title: "Your coaching staff",
    card: "staff",
    target: ['[data-board-window="staff"] .card-board-titlebar', ".season-staff-panel", "[data-card-board-tools]"],
    body: "The staff window is where you review coaches, roles, grades and payroll, and expand into staff management. Coaching is part of your team context, alongside the players and their deployment.",
  },
  {
    title: "Read the season",
    card: "week",
    target: ['[data-board-window="week"] .card-board-titlebar', ".season-week-panel", "[data-card-board-tools]"],
    body: "The calendar keeps played games and upcoming dates together; open a game for its result and box score. The opponent window adds form, ratings and availability so you can put each matchup in context.",
  },
  {
    title: "Compare efficiency",
    card: "efficiency",
    target: ['[data-board-window="efficiency"] .card-board-titlebar', ".season-efficiency-panel", "[data-card-board-tools]"],
    body: "Weekly Efficiency compares your offense and defense with the league average, then shows the net difference. Use it to diagnose where the team is gaining or giving up ground beyond the win-loss record.",
  },
  {
    title: "Explore a trade",
    target: ["[data-trade-menu-trigger]", "[data-card-board-tools]"],
    body: "Trades opens the trade finder, builder and incoming offers. The finder suggests packages to evaluate; it does not execute them. Review players, contracts and picks, then choose whether to submit or accept a deal.",
  },
  {
    title: "Advance the league",
    target: ["[data-sim-menu-trigger]", "[data-card-board-tools]"],
    body: "Sim to… advances to the next event, week or month. Advancing changes the save: games resolve, schedules move, and league events may occur. Your rotation, player condition, lineup fit and coaching all feed the results you review afterward.",
  },
  {
    title: "Shortcuts when you need them",
    target: ["[data-window-switcher-open]", "#nav"],
    body: "Press ? for the shortcut reference or Cmd/Ctrl+K to search commands. G then C opens Cards, G then W switches windows, S then E advances to the next event, and S then W/M advances a week or month. You can replay this tour from Settings.",
  },
];

function queueFirstRunTutorial() {
  if (state.home?.save?.postseason_exit_required) return;
  if (state.tutorial || state.view !== "dashboard" || !state.currentSave || !document.querySelector("[data-card-board-tools]") || localStorage.getItem(TUTORIAL_COMPLETED_KEY)) return;
  clearTimeout(state.tutorialStartTimer);
  state.tutorialStartTimer = window.setTimeout(() => {
    if (!state.tutorial && state.view === "dashboard" && state.currentSave && !state.hydrating) startGameTutorial();
  }, 450);
}

function startGameTutorial(force = false) {
  if (!state.currentSave || state.view !== "dashboard" || (!force && localStorage.getItem(TUTORIAL_COMPLETED_KEY))) return;
  clearTimeout(state.tutorialStartTimer);
  state.tutorialReturnFocus = document.activeElement;
  state.tutorial = { index: 0 };
  document.getElementById("app").inert = true;
  renderGameTutorial();
}

function finishGameTutorial() {
  if (!state.tutorial) return;
  window.CardBoard?.endTutorialPreview();
  state.tutorial = null;
  localStorage.setItem(TUTORIAL_COMPLETED_KEY, "1");
  document.getElementById("app").inert = false;
  els.gameTutorial.hidden = true;
  els.gameTutorial.innerHTML = "";
  const returnFocus = state.tutorialReturnFocus;
  state.tutorialReturnFocus = null;
  if (returnFocus?.isConnected && !returnFocus.disabled) returnFocus.focus({ preventScroll: true });
  else document.querySelector("[data-window-switcher-open]")?.focus({ preventScroll: true });
}

function moveGameTutorial(direction) {
  if (!state.tutorial) return;
  const nextIndex = state.tutorial.index + direction;
  if (nextIndex < 0) return;
  if (nextIndex >= GAME_TUTORIAL_STEPS.length) return finishGameTutorial();
  state.tutorial.index = nextIndex;
  renderGameTutorial();
}

function handleGameTutorialKeydown(event) {
  if (!state.tutorial) return;
  const root = els.gameTutorial;
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopImmediatePropagation();
    finishGameTutorial();
    return;
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    event.stopImmediatePropagation();
    moveGameTutorial(1);
    return;
  }
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    event.stopImmediatePropagation();
    moveGameTutorial(-1);
    return;
  }
  if (event.key === "Tab") {
    const focusable = [...root.querySelectorAll("button:not(:disabled)")];
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && (document.activeElement === first || !root.contains(document.activeElement))) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && (document.activeElement === last || !root.contains(document.activeElement))) {
      event.preventDefault();
      first?.focus();
    }
    event.stopImmediatePropagation();
    return;
  }
  if (!root.contains(event.target)) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}

function handleGameTutorialWheel(event) {
  if (state.tutorial && !els.gameTutorial.contains(event.target)) event.preventDefault();
}

function blockGameTutorialBackgroundEvent(event) {
  if (!state.tutorial || els.gameTutorial.contains(event.target)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function resolveGameTutorialTarget(step) {
  for (const selector of step.target) {
    const target = document.querySelector(selector);
    if (!target || !target.getClientRects().length) continue;
    const style = getComputedStyle(target);
    if (style.visibility === "hidden" || style.display === "none") continue;
    const rect = target.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) return target;
  }
  return document.querySelector("#nav") || document.querySelector("#content");
}

function renderGameTutorial() {
  if (!state.tutorial) return;
  const index = state.tutorial.index;
  const step = GAME_TUTORIAL_STEPS[index];
  const last = index === GAME_TUTORIAL_STEPS.length - 1;
  window.CardBoard?.previewTutorialWindow(step.card);
  els.gameTutorial.hidden = false;
  els.gameTutorial.innerHTML = `
    <div class="game-tutorial-shade game-tutorial-shade--top" aria-hidden="true"></div>
    <div class="game-tutorial-shade game-tutorial-shade--left" aria-hidden="true"></div>
    <div class="game-tutorial-shade game-tutorial-shade--right" aria-hidden="true"></div>
    <div class="game-tutorial-shade game-tutorial-shade--bottom" aria-hidden="true"></div>
    <div class="game-tutorial-spotlight" aria-hidden="true"></div>
    <article class="game-tutorial-card" role="dialog" aria-modal="true" aria-labelledby="gameTutorialTitle" aria-describedby="gameTutorialCopy" tabindex="-1">
      <header class="game-tutorial-titlebar"><span>FRANCHISE FIELD GUIDE</span><span>${String(index + 1).padStart(2, "0")} / ${String(GAME_TUTORIAL_STEPS.length).padStart(2, "0")}</span></header>
      <div class="game-tutorial-content" aria-live="polite">
        <p class="game-tutorial-kicker">${String(index + 1).padStart(2, "0")} · ${escapeHtml(step.kicker || "THE FRONT OFFICE")}</p>
        <h2 id="gameTutorialTitle">${escapeHtml(step.title)}</h2>
        <p id="gameTutorialCopy">${escapeHtml(step.body)}</p>
      </div>
      <footer class="game-tutorial-actions">
        <button type="button" class="game-tutorial-skip" data-tutorial-action="skip">Skip tutorial</button>
        <div class="game-tutorial-arrows">
          <button type="button" class="game-tutorial-arrow" data-tutorial-action="previous" aria-label="Previous step" title="Previous step" ${index === 0 ? "disabled" : ""}>←</button>
          <button type="button" class="game-tutorial-arrow" data-tutorial-action="next" aria-label="${last ? "Finish tutorial" : "Next step"}" title="${last ? "Finish tutorial" : "Next step"}">${last ? "✓" : "→"}</button>
        </div>
      </footer>
    </article>`;
  const target = resolveGameTutorialTarget(step);
  target?.scrollIntoView({ block: "nearest", inline: "nearest" });
  requestAnimationFrame(() => {
    if (!state.tutorial) return;
    positionGameTutorial(target);
    els.gameTutorial.querySelector('[data-tutorial-action="next"]')?.focus({ preventScroll: true });
  });
}

function positionGameTutorial(target) {
  if (!target || !state.tutorial) return;
  const root = els.gameTutorial;
  const rect = target.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const padding = 7;
  const left = Math.max(0, rect.left - padding);
  const top = Math.max(0, rect.top - padding);
  const right = Math.min(viewportWidth, rect.right + padding);
  const bottom = Math.min(viewportHeight, rect.bottom + padding);
  const panes = {
    top: [0, 0, viewportWidth, top],
    left: [0, top, left, Math.max(0, bottom - top)],
    right: [right, top, Math.max(0, viewportWidth - right), Math.max(0, bottom - top)],
    bottom: [0, bottom, viewportWidth, Math.max(0, viewportHeight - bottom)],
  };
  for (const [name, [x, y, width, height]] of Object.entries(panes)) {
    const pane = root.querySelector(`.game-tutorial-shade--${name}`);
    Object.assign(pane.style, { left: `${x}px`, top: `${y}px`, width: `${width}px`, height: `${height}px` });
  }
  const spotlight = root.querySelector(".game-tutorial-spotlight");
  Object.assign(spotlight.style, { left: `${left}px`, top: `${top}px`, width: `${right - left}px`, height: `${bottom - top}px` });

  const card = root.querySelector(".game-tutorial-card");
  const cardRect = card.getBoundingClientRect();
  const gap = 18;
  const choices = [
    { side: "right", room: viewportWidth - rect.right, left: rect.right + gap, top: rect.top + rect.height / 2 - cardRect.height / 2 },
    { side: "left", room: rect.left, left: rect.left - cardRect.width - gap, top: rect.top + rect.height / 2 - cardRect.height / 2 },
    { side: "bottom", room: viewportHeight - rect.bottom, left: rect.left + rect.width / 2 - cardRect.width / 2, top: rect.bottom + gap },
    { side: "top", room: rect.top, left: rect.left + rect.width / 2 - cardRect.width / 2, top: rect.top - cardRect.height - gap },
  ].sort((a, b) => b.room - a.room);
  const placement = choices.find((choice) => choice.room >= (choice.side === "left" || choice.side === "right" ? cardRect.width + gap : cardRect.height + gap)) || choices[0];
  const cardLeft = Math.max(12, Math.min(placement.left, viewportWidth - cardRect.width - 12));
  const cardTop = Math.max(12, Math.min(placement.top, viewportHeight - cardRect.height - 12));
  card.dataset.side = placement.side;
  Object.assign(card.style, { left: `${cardLeft}px`, top: `${cardTop}px` });
}

function repositionGameTutorial() {
  if (!state.tutorial) return;
  const target = resolveGameTutorialTarget(GAME_TUTORIAL_STEPS[state.tutorial.index]);
  positionGameTutorial(target);
}

function clearViewCaches() {
  state.wantsRead = null;
  state.data = {};
  state.playerCardDetails = {};
  state.tradeCandidate = null;
  state.tradeResults = [];
  state.tradeSearchCompleted = false;
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
  if (dashboardPhaseKind() === "fantasy_draft" && state.view !== "dashboard") {
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
        slot: state.staffSlot || undefined,
        limit: 30,
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
      state.data.playoffLeaders = await action("playoff_leaders", { ...savePayload(), stat: "points", limit: PLAYOFF_STATS_LIMIT });
    }
    if (phase === "draft") {
      state.data.draft = await action("draft_room", { ...savePayload(), team: userTeam(), seed: 7 });
    }
    if (phase !== 'playoffs' && state.home?.save?.playoff_status === 'completed') {
      state.data.playoffs = await action('playoff_room',savePayload());
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
    through_date: from ? monthEndDate(`${addMonths(month, 1)}-01`) : undefined,
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
  window.CardBoard?.updateOfferCount(Number(snapshot.offers?.offers?.length || 0));
  state.data.dashboardOpponent = snapshot.opponent;
  state.data.dashboardProspects = snapshot.prospects;
  return snapshot;
}

async function loadDashboardCalendar(team) {
  const current = state.home?.save?.current_date || "";
  const month = state.calendarMonth || current.slice(0, 7);
  if (!month) return;
  const from = `${month}-01`;
  const through = monthEndDate(`${addMonths(month, 1)}-01`);
  state.data.dashboardCalendar = await action("calendar", { ...savePayload(), from_date: from, through_date: through });
}

async function loadSimulationPlayerRatings() {
  const currentDate = String(state.home?.save?.current_date || "").slice(0, 10);
  const cached = state.playerFinder?.saveId === state.currentSave
    && state.playerFinder.payload?.as_of_date === currentDate
    ? state.playerFinder.payload
    : null;
  const payload = cached || await action("player_finder", savePayload());
  return new Map((payload.rows || []).map((row) => [
    String(row.id || row.player_id || ""),
    row.display_ratings || row.ratings || {},
  ]).filter(([id, ratings]) => id && Object.keys(ratings).length));
}

function mergeSimulationCalendar(current, incoming) {
  if (!incoming) return current || {};
  const games = new Map();
  for (const game of [...(current?.games || current?.calendar || []), ...(incoming.games || incoming.calendar || [])]) {
    const key = String(game.game_id || game.id || `${game.date || ""}:${game.home_team || game.home_team_id || ""}:${game.away_team || game.away_team_id || ""}`);
    games.set(key, game);
  }
  const ranges = [current?.from_date, incoming.from_date].filter(Boolean).sort();
  const ends = [current?.through_date, incoming.through_date].filter(Boolean).sort();
  return {
    ...current,
    ...incoming,
    from_date:ranges[0] || incoming.from_date,
    through_date:ends.at(-1) || incoming.through_date,
    games:[...games.values()],
    game_count:games.size,
  };
}

function dashboardWeekRange(dateText) {
  const date = new Date(`${String(dateText || "").slice(0, 10) || "2026-10-01"}T00:00:00Z`);
  const monday = new Date(date);
  monday.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  return {
    from_date:monday.toISOString().slice(0, 10),
    through_date:sunday.toISOString().slice(0, 10),
  };
}

async function loadSimulationWeekCalendar(dateText) {
  const calendar = await action("calendar", { ...savePayload(), ...dashboardWeekRange(dateText) });
  state.data.dashboardCalendar = mergeSimulationCalendar(state.data.dashboardCalendar, calendar);
}

async function loadTradeAssets() {
  syncDefaultPartner();
  const user = userTeam();
  state.data.tradeUser = await action("team_assets", { ...savePayload(), team: user });
  state.data.tradePartner = await action("team_assets", { ...savePayload(), team: state.tradePartner });
}

async function waitForSimulationIdle(timeoutMs = 60000) {
  const started = Date.now();
  while (state.simulationRunning || state.busy || state.lotteryRevealRunning) {
    if (Date.now() - started > timeoutMs) return false;
    await new Promise(resolve => setTimeout(resolve, 150));
  }
  return true;
}

async function advance(payload) {
  if (state.simulationRunning || state.busy || state.lotteryRevealRunning) return;
  state.simulationRunning = true;
  state.simulationId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  state.simulationStopRequested = false;
  state.simulationProcessedGames = new Set();
  try {
    return await advanceSave(payload, state.simulationId);
  } finally {
    window.AssistantGMPhone?.setSimulationPlaybackActive(false);
    state.simulationRunning = false;
    state.simulationId = "";
    state.simulationOfferIds = new Set();
    state.simulationOfferCount = 0;
    state.simulationStopRequested = false;
    state.simulationGameCache = null;
    state.simulationPlayerRatingsById = null;
    state.simulationOpponentResult = null;
    state.simulationPendingOpponent = null;
    state.simulationUpcomingGames = null;
    document.body.classList.remove("simulation-live");
    document.querySelector('[data-simulation-status]')?.remove();
    document.querySelectorAll('[data-minute-player]').forEach((input) => {
      input.disabled = Boolean(input.closest('.season-minute-row')?.classList.contains('injured'));
    });
    setBusy(state.busyDepth > 0 || state.hydrating);
    maybeCelebrateChampion();
    if(typeof maybeShowWantReminder==='function')maybeShowWantReminder();
  }
}

async function advanceSave(payload, simulationId) {
  if (!state.currentSave) return showToast("Create or select a save first.", true);
  if (requiredClipboardDecision()) return revealRequiredClipboardDecision();
  if (!(await ensureStartingFiveReadyForAdvance())) return;
  const currentDate = String(state.home?.save?.current_date || "").slice(0, 10);
  const deadline = tradeDeadlineDate();
  if (currentDate === deadline && hasAcknowledgedTradeDeadline(deadline)
      && payload.trade_deadline_confirmed !== deadline) {
    payload = {...payload, trade_deadline_confirmed:deadline};
  }
  const postseasonBoundary = postseasonBoundaryDate();
  if (currentDate >= postseasonBoundary && hasReviewedPostseason(postseasonBoundary)) {
    payload = {...payload, postseason_confirmed:postseasonBoundary};
  }
  if (state.multiplayer.league?.status === "active") {
    if (state.home?.save?.current_date === tradeDeadlineDate() && payload.trade_deadline_confirmed !== tradeDeadlineDate()) {
      return showTradeDeadlinePrompt();
    }
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
        if (result.result?.trade_deadline_checkpoint) showTradeDeadlinePrompt(result.result.trade_deadline_checkpoint, payload);
        else showToast("Every manager was ready. The league advanced.");
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
  state.simulationPlayerRatingsById = await loadSimulationPlayerRatings().catch(() => new Map());
  const previousDevelopmentSignature = developmentTrendSignature();
  const originalHome = structuredClone(state.home);
  state.simulationGameCache = new Map();
  state.simulationLastDate = state.home?.save?.current_date;
  state.simulationOpponentSignature = "";
  state.simulationCompletedGameIds = new Set();
  state.simulationPendingOpponent = null;
  state.simulationOpponentResult = null;
  state.simulationUpcomingGames = [...(state.data.dashboard?.next_games || [])];
  const initialOffers=state.data.dashboardOffers?.offers||[];
  state.simulationOfferIds=new Set(initialOffers.map(simulationOfferKey));
  state.simulationOfferCount=Math.max(initialOffers.length,Number(state.home?.save?.pending_counts?.user_trade_offers||0));
  for (const payload of Object.values(state.data.playoffs?.play_in || {})) {
    for (const game of payload.games || []) state.simulationGameCache.set(game.game_id, game);
  }
  let result;
  try {
    document.body.classList.add("simulation-live");
    window.AssistantGMPhone?.setSimulationPlaybackActive(true);
    result = await action("advance_save", { ...savePayload(), ...payload }, {progress:displaySimulationProgress, simulationId});
  } catch (error) {
    state.home = originalHome;
    // Never replay an uncertain mutation after a dropped connection.
    await refreshHome().catch(()=>{});
    showToast(error.message || "Simulation failed. Your save has been refreshed.", true);
    throw error;
  }
  // A W/L banner still playing (sim finished or was stopped mid-animation)
  // finishes on the completed game; then the final snapshot shows the real next opponent.
  const resultHold = state.simulationOpponentResult;
  if (resultHold) { resultHold.final = true; await resultHold.done; }
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
  if (result.trade_deadline_checkpoint) {
    showTradeDeadlinePrompt(result.trade_deadline_checkpoint, payload);
  } else if (result.postseason_checkpoint) {
    showPostseasonPrompt(result.postseason_checkpoint, payload);
  } else if (result.status === "stopped" || result.result?.status === "stopped") {
    const stoppedDate = result.result?.through_date || state.home?.save?.current_date;
    showToast(`Simulation stopped at ${stoppedDate || "the current date"}.`);
  } else {
    showToast(`Advanced to ${state.home?.save?.current_date || "next date"}`);
  }
}

async function requestSimulationStop() {
  if (!state.simulationRunning || !state.simulationId || state.simulationStopRequested) return;
  state.simulationStopRequested = true;
  const button = document.querySelector('[data-simulation-stop]');
  if (button) {
    button.disabled = true;
    button.textContent = "Stopping…";
    button.setAttribute("aria-label", "Stopping simulation");
  }
  try {
    const response = await fetch("/api/action", {
      method: "POST",
      mode: "same-origin",
      headers: await apiHeaders("cancel_simulation"),
      body: JSON.stringify({action:"cancel_simulation", payload:{simulation_id:state.simulationId}}),
    });
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || `${response.status} ${response.statusText}`);
  } catch (error) {
    state.simulationStopRequested = false;
    const currentStatus = document.querySelector('[data-simulation-status]');
    if (currentStatus) {
      currentStatus.disabled = false;
      currentStatus.textContent = state.simulationLastDate ? `Simulating · ${formatWrittenDate(state.simulationLastDate)}` : "Starting simulation…";
      currentStatus.setAttribute("aria-label", "Stop simulation");
    }
    showToast(error.message || "Couldn't stop the simulation.", true);
  }
}

function playoffProgressFlightPlan(raw, event) {
  const game = event?.game;
  if (game) {
    const entry = Object.entries(raw?.play_in || {}).find(([, payload]) => (payload.games || []).includes(game.game_id));
    if (entry) {
      const [conference, payload] = entry;
      const stage = payload.games.indexOf(game.game_id);
      const homeScore = Number(game.home_score), awayScore = Number(game.away_score);
      if (homeScore === awayScore || !Number.isFinite(homeScore) || !Number.isFinite(awayScore)) return [];
      const winner = homeScore > awayScore ? game.home_team_id : game.away_team_id;
      const loser = homeScore > awayScore ? game.away_team_id : game.home_team_id;
      if (stage === 0) return [
        {teamId:winner, conference, sourceStage:stage, destination:"first_round", route:"qualifier", seed:"7"},
        {teamId:loser, conference, sourceStage:stage, destination:"play_in_final", route:"7-8-loser"},
      ];
      if (stage === 1) return [{teamId:winner, conference, sourceStage:stage, destination:"play_in_final", route:"9-10-winner"}];
      if (stage === 2) return [{teamId:winner, conference, sourceStage:stage, destination:"first_round", route:"qualifier", seed:"8"}];
      return [];
    }
  }
  if (event?.series_id) {
    const series = (raw?.series || []).find(item => item.id === event.series_id);
    const teamId = series?.winner_team_id;
    if (series?.status === "completed" && teamId) return [{teamId, conference:series.conference, sourceSeriesId:series.id, destination:"next_series", route:"series-advance"}];
  }
  return [];
}

function bracketTeamRow(root, selector, teamId) {
  const scope = root.querySelector(selector);
  return scope && [...scope.querySelectorAll(".series-team[data-team-id]")].find(row => row.dataset.teamId === String(teamId));
}

function bracketPathScreenPoints(path) {
  if (!path?.ownerSVGElement || !path.getScreenCTM()) return [];
  const svg = path.ownerSVGElement;
  const matrix = path.getScreenCTM();
  const length = path.getTotalLength();
  if (!length) return [];
  return [0, 0.25, 0.5, 0.75, 1].map(fraction => {
    const point = svg.createSVGPoint();
    const local = path.getPointAtLength(length * fraction);
    point.x = local.x;
    point.y = local.y;
    return point.matrixTransform(matrix);
  });
}

function capturePlayoffFlights(shell, plan) {
  return plan.flatMap(item => {
    let source, path;
    if (item.sourceSeriesId) {
      source = bracketTeamRow(shell, `.bracket-node[data-bracket-series="${item.sourceSeriesId}"]`, item.teamId);
      path = [...shell.querySelectorAll(".bracket-round-links path[data-from-series]")].find(node => node.dataset.fromSeries === item.sourceSeriesId);
    } else {
      source = bracketTeamRow(shell, `.bracket-play-in [data-play-in-stage="${item.sourceStage}"]`, item.teamId);
      path = item.route === "qualifier"
        ? [...shell.querySelectorAll(".bracket-play-in .bracket-round-links path[data-qualifier-seed]")].find(node => node.dataset.qualifierSeed === item.seed)
        : [...shell.querySelectorAll(".play-in-feeder-links path[data-playin-flow]")].find(node => node.dataset.playinFlow === item.route);
    }
    const sourceLogo = source?.querySelector("img");
    if (!sourceLogo?.getClientRects().length) return [];
    const rect = sourceLogo.getBoundingClientRect();
    return [{...item, sourceLogoClone:sourceLogo.cloneNode(true), startRect:rect, routePoints:bracketPathScreenPoints(path), targetSeriesId:path?.dataset.toSeries || ""}];
  });
}

function animatePlayoffFlights(shell, flights) {
  if (!flights.length || GameSimulation.reducedMotion() || !Element.prototype.animate) return;
  for (const flight of flights) {
    let target;
    if (flight.destination === "first_round") target = bracketTeamRow(shell, ".bracket-first_round", flight.teamId);
    else if (flight.destination === "play_in_final") target = bracketTeamRow(shell, '.bracket-play-in [data-play-in-stage="2"]', flight.teamId);
    else if (flight.destination === "next_series") {
      const node = [...shell.querySelectorAll(".bracket-node[data-bracket-series]")].find(item => item.dataset.bracketSeries === flight.targetSeriesId);
      target = node && bracketTeamRow(node, ".series-card", flight.teamId);
    }
    const targetLogo = target?.querySelector("img");
    if (!targetLogo?.getClientRects().length) continue;
    const start = flight.startRect, end = targetLogo.getBoundingClientRect();
    const points = [{x:start.left + start.width / 2,y:start.top + start.height / 2}, ...flight.routePoints, {x:end.left + end.width / 2,y:end.top + end.height / 2}];
    const distances = points.slice(1).map((point, index) => Math.hypot(point.x - points[index].x, point.y - points[index].y));
    const total = distances.reduce((sum, distance) => sum + distance, 0) || 1;
    let traversed = 0;
    const startCenterX = start.left + start.width / 2, startCenterY = start.top + start.height / 2;
    const keyframes = points.map((point, index) => {
      if (index) traversed += distances[index - 1];
      const progress = traversed / total;
      return {offset:progress,transform:`translate(${point.x - startCenterX}px,${point.y - startCenterY}px)`};
    });
    const clone = flight.sourceLogoClone;
    clone.classList.add("bracket-team-flight");
    Object.assign(clone.style,{position:"fixed",left:`${start.left}px`,top:`${start.top}px`,width:`${start.width}px`,height:`${start.height}px`,maxWidth:`${start.width}px`,maxHeight:`${start.height}px`,objectFit:"contain",margin:"0",zIndex:"99999",pointerEvents:"none"});
    document.body.append(clone);
    const previousOpacity = targetLogo.style.opacity;
    targetLogo.style.opacity = "0";
    const animation = clone.animate(keyframes,{duration:440,easing:"ease-in-out",fill:"forwards"});
    const finish = () => { clone.remove(); targetLogo.style.opacity = previousOpacity; };
    animation.finished.then(finish,finish);
  }
}

function simulationOfferRows(value) {
  if(Array.isArray(value)) return value;
  if(Array.isArray(value?.offers)) return value.offers;
  if(Array.isArray(value?.incoming_offers)) return value.incoming_offers;
  if(value?.offer&&typeof value.offer==='object') return simulationOfferRows(value.offer);
  return value&&typeof value==='object'?[value]:[];
}
function simulationOfferKey(offer) {
  const id=offer?.offer_id||offer?.id||offer?.proposal?.offer_id||offer?.proposal?.id;
  if(id!=null) return String(id);
  try { return JSON.stringify(offer); } catch { return String(offer); }
}
function simulationOfferTeamAbbrev(offer) {
  const proposal=offer?.proposal||offer?.trade_proposal||offer||{};
  const userId=String(state.home?.save?.user_team?.id||state.home?.save?.team?.id||'');
  const fromId=proposal.from_team_id||(typeof proposal.from_team==='object'?proposal.from_team?.id:proposal.from_team)||offer?.sender_team_id||offer?.proposing_team_id||'';
  const toId=proposal.to_team_id||(typeof proposal.to_team==='object'?proposal.to_team?.id:proposal.to_team)||'';
  const userAbbrev=userTeam();
  const isUser=id=>String(id)===userId||Boolean(id&&teamLabel(id)===userAbbrev);
  const otherId=isUser(fromId)?toId:isUser(toId)?fromId:'';
  const direct=otherId||offer?.sender_team_abbrev||offer?.proposing_team_abbrev||offer?.counterparty_team_abbrev||offer?.partner_team_abbrev||offer?.team_abbrev||'';
  if(direct) {
    const team=state.teams.find(row=>String(row.id||row.team_id||'')===String(direct));
    return team?.abbrev||teamLabel(direct);
  }
  const candidate=state.teams.find(row=>String(row.id||row.team_id||'')===String(fromId||toId));
  return candidate?.abbrev||teamLabel(fromId||toId)||'an NBA team';
}
function simulationOfferCountFromEvent(event) {
  const candidates=[event.pending_user_trade_offer_count,event.user_trade_offer_count,event.pending_offer_count,event.offer_count,event.pending_counts?.user_trade_offers,event.pending_counts?.trade_offers];
  const count=candidates.find(value=>value!==undefined&&value!==null&&Number.isFinite(Number(value)));
  return count===undefined?null:Math.max(0,Math.floor(Number(count)));
}
async function processSimulationTradeOffers(event) {
  const deltaKeys=['new_user_trade_offers','trade_offers_added','new_trade_offers','incoming_offers_added','trade_offer_arrivals'];
  let added=deltaKeys.flatMap(key=>simulationOfferRows(event[key]));
  const singular=event.trade_offer_arrived||event.new_trade_offer||event.new_offer||((/trade[_ -]?offer/i.test(String(event.kind||event.type||'')))?event.offer:null);
  if(singular) added.push(...simulationOfferRows(singular));
  const cumulativeValue=event.pending_user_trade_offers??event.user_trade_offers??event.pending_offers_snapshot??event.trade_offers??event.offers;
  const hasCumulative=cumulativeValue!==undefined&&cumulativeValue!==null;
  const cumulative=hasCumulative?simulationOfferRows(cumulativeValue):[];
  const previousCount=Number(state.simulationOfferCount||0);
  const ids=state.simulationOfferIds instanceof Set?state.simulationOfferIds:(state.simulationOfferIds=new Set());
  let fresh=[];
  if(added.length) {
    const batchKeys=new Set();
    fresh=added.filter(offer=>{
      const key=simulationOfferKey(offer);
      if(ids.has(key)||batchKeys.has(key)) return false;
      batchKeys.add(key); return true;
    });
  }
  if(cumulative.length) {
    const unseen=cumulative.filter(offer=>!ids.has(simulationOfferKey(offer)));
    if(!added.length&&!ids.size&&previousCount>0&&cumulative.length>previousCount) fresh=unseen.slice(-(cumulative.length-previousCount));
    else if(!added.length) fresh=unseen;
    for(const offer of cumulative) ids.add(simulationOfferKey(offer));
  }
  for(const offer of fresh) ids.add(simulationOfferKey(offer));
  const reportedCount=simulationOfferCountFromEvent(event);
  const nextCount=reportedCount??(hasCumulative?cumulative.length:previousCount+fresh.length);
  state.simulationOfferCount=nextCount;
  let phoneAlerts=fresh;
  const senderAbbrev=event.new_trade_offer_from_team_abbrev||event.trade_offer_from_team_abbrev||event.offer_sender_abbrev;
  const senderId=event.new_trade_offer_from_team_id||event.trade_offer_from_team_id||event.offer_sender_team_id;
  if(!phoneAlerts.length&&nextCount>previousCount&&(senderAbbrev||senderId)) {
    phoneAlerts=Array.from({length:nextCount-previousCount},(_,index)=>({id:`progress-offer:${event.date||'today'}:${nextCount-index}`,sender_team_abbrev:senderAbbrev,sender_team_id:senderId}));
  }
  if(state.home?.save) {
    state.home.save.pending_counts={...(state.home.save.pending_counts||{}),user_trade_offers:nextCount};
  }
  if(fresh.length||reportedCount!==null||hasCumulative) {
    const prior=state.data.dashboardOffers||{};
    const current=prior.offers||[];
    const merged=new Map(current.map(offer=>[simulationOfferKey(offer),offer]));
    for(const offer of hasCumulative?cumulative:fresh) merged.set(simulationOfferKey(offer),offer);
    if(hasCumulative) state.data.dashboardOffers={...prior,offers:cumulative};
    else if(fresh.length) state.data.dashboardOffers={...prior,offers:[...merged.values()]};
  }
  let displayedCount=previousCount;
  for(const offer of phoneAlerts) {
    if(nextCount>displayedCount) {
      displayedCount=Math.min(nextCount,displayedCount+1);
      window.CardBoard?.updateOfferCount(displayedCount,{animate:true});
    }
    await window.AssistantGMPhone?.presentSimulationTradeOffer({
      teamAbbrev:simulationOfferTeamAbbrev(offer),
      date:event.date?formatWrittenDate(event.date):'Today',
    });
  }
  if(displayedCount!==nextCount||(!phoneAlerts.length&&(fresh.length||reportedCount!==null||hasCumulative))) {
    window.CardBoard?.updateOfferCount(nextCount,{animate:nextCount>previousCount&&!phoneAlerts.length});
  }
}

async function displaySimulationProgress(event) {
  let status = document.querySelector('[data-simulation-status]');
  if (!status) {
    status = document.createElement('button');
    status.type = "button";
    status.dataset.simulationStatus = '';
    status.dataset.simulationStop = '';
    status.className = "ui-command simulation-stop-control";
    status.setAttribute('role','status');
    status.setAttribute('aria-live','polite');
    document.querySelector('[data-card-board-tools]')?.append(status);
  }
  status.textContent = state.simulationStopRequested ? "Stopping…" : event.date ? `Simulating · ${formatWrittenDate(event.date)}` : 'Starting simulation…';
  status.disabled = Boolean(state.simulationStopRequested);
  status.setAttribute("aria-label", state.simulationStopRequested ? "Stopping simulation" : "Stop simulation");
  // Live event contract: dashboard_stats contains a cumulative user-roster
  // snapshot; new_user_trade_offers contains arriving offers; and
  // pending_user_trade_offer_count is the current inbox count. Accept the
  // equivalent aliases below while the simulation stream is being aligned.
  // Stats rows may be display-ready or carry nested season totals.
  const statsSnapshot=event.dashboard_stats||event.player_stats_snapshot||event.player_stats||event.user_player_stats||event.user_stats||event.user_stats_snapshot||event.dashboard?.players||event.dashboard_snapshot?.dashboard||event.live_stats||event.stats_snapshot||null;
  if(statsSnapshot) window.updateDashboardStatsDuringSimulation?.(statsSnapshot);
  await processSimulationTradeOffers(event);
  if (!event.date || !state.home?.save) return;
  const previousDate = state.simulationLastDate;
  const dateChanged = event.date !== previousDate;
  state.simulationLastDate = event.date;
  state.home.save.current_date = event.date;
  if (dateChanged) state.calendarMonth = event.date.slice(0,7);
  if (event.calendar) state.data.dashboardCalendar = mergeSimulationCalendar(state.data.dashboardCalendar, event.calendar);
  if (dateChanged && previousDate && dashboardWeekRange(previousDate).from_date !== dashboardWeekRange(event.date).from_date) {
    await loadSimulationWeekCalendar(event.date).catch(() => {});
  }
  const time = document.querySelector('.season-command-date time');
  if (time) { time.dateTime = event.date; time.textContent = `${formatDashboardShortDate(event.date)}, ${event.date.slice(0,4)}`; }
  const teamRef = id => state.teams.find(team=>team.id===id) || {id,abbrev:String(id || '').replace('team_','').toUpperCase()};
  let standingsMoved = false;
  if (event.rotation) updateRotationDuringSimulation(event.rotation);
  if (event.team_signals) updateTeamSignalsDuringSimulation(event.team_signals);
  if (event.opponent) updateOpponentDuringSimulation(event.opponent);
  if (event.game) {
    standingsMoved = applyStandingsGameProgress(event);
    const game = {...event.game, date:event.date, home_team:teamRef(event.game.home_team_id), away_team:teamRef(event.game.away_team_id)};
    state.simulationGameCache.set(game.game_id, game);
    state.data.dashboardCalendar ||= {games:[]};
    state.data.dashboardCalendar.games = [...(state.data.dashboardCalendar.games || []).filter(g=>g.game_id!==game.game_id), {...game,status:'simulated'}];
    showSimulationOpponentResult(event);
  }
  const week = document.querySelector('[data-board-window="week"] .season-week-panel');
  if (week) {
    const oldBubble = week.querySelector('.season-week-day.today .season-week-node')?.getBoundingClientRect();
    if (week.classList.contains('is-expanded')) renderCalendar(week, {team:userTeam(),dataKey:'dashboardCalendar'});
    else {
      week.innerHTML = seasonWeekCard(state.data.dashboard || {}, userTeam());
      wireWeekCardBoxScores(week);
      const bubble = week.querySelector('.season-week-day.today .season-week-node');
      if (dateChanged && bubble && oldBubble && !GameSimulation.reducedMotion()) {
        const rect = bubble.getBoundingClientRect(), parent = week.getBoundingClientRect();
        const scale = week.offsetWidth ? parent.width / week.offsetWidth : 1;
        const cursor = document.createElement('span');
        cursor.className = 'simulation-week-cursor';
        Object.assign(cursor.style,{left:`${(rect.left-parent.left)/scale}px`,top:`${(rect.top-parent.top)/scale}px`,width:`${rect.width/scale}px`,height:`${rect.height/scale}px`});
        week.append(cursor);
        cursor.animate([{transform:`translate(${(oldBubble.left-rect.left)/scale}px,${(oldBubble.top-rect.top)/scale}px)`},{transform:'translate(0,0)'}],{duration:220,easing:'ease-in-out'}).finished.then(()=>cursor.remove(),()=>cursor.remove());
      }
    }
  }
  if (event.playoffs) {
    const raw = event.playoffs;
    const shell = document.querySelector('[data-board-window="phase-playoffs-bracket"] .phase-bracket-shell');
    const flights = shell ? capturePlayoffFlights(shell, playoffProgressFlightPlan(raw,event)) : [];
    let series = [...(raw.series || [])];
    if (raw.round === 'play_in') for (const [conference, locked] of Object.entries(raw.locked_seeds || {})) {
      const pi = raw.play_in?.[conference] || {};
      const seeds = {...locked,7:pi.seed_7_team_id,8:pi.seed_8_team_id};
      for (const [high,low] of [[1,8],[4,5],[3,6],[2,7]]) series.push({id:`preview:${conference}:${high}`,conference,round:'first_round',team_ids:[seeds[high],seeds[low]],pending_seed:seeds[low]?null:String(low),wins:{}});
    }
    const room = {...state.data.playoffs, playoff_state:raw, status:raw.status, round:raw.round,
      champion:raw.champion_team_id ? teamRef(raw.champion_team_id) : null,
      series:series.map(s=>({...s,teams:s.team_ids.map(id=>id?teamRef(id):null),score:s.team_ids.map(id=>s.wins?.[id] || 0),winner:s.winner_team_id?teamRef(s.winner_team_id):null})),
      play_in:Object.fromEntries(Object.entries(raw.play_in || {}).map(([conf, pi])=>[conf,{...pi,teams:Object.fromEntries(Object.entries(pi.teams || {}).map(([seed,id])=>[seed,teamRef(id)])),games:(pi.games || []).map(id=>state.simulationGameCache.get(id)).filter(Boolean)}]))};
    state.data.playoffs = room;
    if (shell) {
      const left = shell.scrollLeft;
      shell.innerHTML = playoffBracket(room.series,room.champion,room.play_in);
      shell.scrollLeft = left;
      const piConference = event.game ? Object.entries(raw.play_in || {}).find(([,pi])=>(pi.games || []).includes(event.game.game_id)) : null;
      const changed = event.series_id ? [...shell.querySelectorAll('[data-bracket-series]')].find(node=>node.dataset.bracketSeries===event.series_id) : piConference ? shell.querySelector(`.bracket-conference.${piConference[0].toLowerCase()} [data-play-in-stage="${piConference[1].games.indexOf(event.game.game_id)}"]`) : null;
      changed?.classList.add('simulation-score-update');
      animatePlayoffFlights(shell,flights);
    }
  }
  setBusy(true);
  const isUserGame = [event.game?.home_team_id,event.game?.away_team_id].includes(state.home.save.user_team?.id);
  const opponentFrame = document.querySelector('[data-board-window="opponent"]');
  const resultVisible = event.kind === "game" && isUserGame && opponentFrame
    && !opponentFrame.classList.contains("is-minimized") && opponentFrame.getClientRects().length > 0;
  if (event.kind==='game' && (event.playoffs || isUserGame)) await GameSimulation.wait(GameSimulation.reducedMotion()?25:resultVisible?480:180);
  else if (event.kind==='game' && standingsMoved && !GameSimulation.reducedMotion()) await GameSimulation.wait(28);
  else if (dateChanged) await GameSimulation.wait(GameSimulation.reducedMotion()?0:70);
}

function standingsAfterProgressGame(snapshot, game) {
  const field = Array.isArray(snapshot) ? null
    : ["standings", "rows", "teams"].find((key) => Array.isArray(snapshot?.[key]));
  const sourceRows = Array.isArray(snapshot) ? snapshot : field ? snapshot[field] : [];
  const homeScore = Number(game?.home_score), awayScore = Number(game?.away_score);
  if (!Number.isFinite(homeScore) || !Number.isFinite(awayScore) || homeScore === awayScore) return null;
  const homeId = String(game.home_team_id || ""), awayId = String(game.away_team_id || "");
  const rows = sourceRows.map((row) => ({...row, team: row.team && typeof row.team === "object" ? {...row.team} : row.team}));
  const keyOf = (row) => String(row.team?.id || row.team_id || row.id || "");
  const home = rows.find((row) => keyOf(row) === homeId);
  const away = rows.find((row) => keyOf(row) === awayId);
  if (!home || !away) return null;
  const conferenceOf = (row) => String(row.team?.conference || row.conference || "");
  const abbrevOf = (row) => String(row.team?.abbrev || row.team_abbrev || row.team?.name || "");
  const compare = (left, right) => conferenceOf(left).localeCompare(conferenceOf(right))
    || Number(right.win_pct || 0) - Number(left.win_pct || 0)
    || Number(right.point_diff || 0) - Number(left.point_diff || 0)
    || abbrevOf(left).localeCompare(abbrevOf(right));
  const rankMap = (items) => {
    const ranks = new Map();
    let conference = null, rank = 0;
    for (const row of [...items].sort(compare)) {
      const current = conferenceOf(row);
      if (current !== conference) { conference = current; rank = 0; }
      ranks.set(keyOf(row), ++rank);
    }
    return ranks;
  };
  const previousRanks = rankMap(rows);
  const homeWon = homeScore > awayScore;
  for (const [row, points, pointsAgainst, won] of [[home, homeScore, awayScore, homeWon], [away, awayScore, homeScore, !homeWon]]) {
    row.wins = Number(row.wins || 0) + Number(won);
    row.losses = Number(row.losses || 0) + Number(!won);
    row.games = Number(row.games || 0) + 1;
    row.points_for = Number(row.points_for ?? 0) + points;
    row.points_against = Number(row.points_against ?? 0) + pointsAgainst;
    row.point_diff = Math.round((Number(row.points_for) - Number(row.points_against)) * 100) / 100;
    row.win_pct = Math.round((row.wins / row.games) * 1000) / 1000;
  }
  rows.sort(compare);
  return {
    snapshot: Array.isArray(snapshot) ? rows : {...snapshot, [field]: rows},
    previousRanks,
    nextRanks: rankMap(rows),
  };
}

function applyStandingsGameProgress(event) {
  if (event.phase !== "regular_season" || !event.game?.game_id || !state.data.dashboardStandings) return false;
  const gameId = String(event.game.game_id);
  if (state.simulationProcessedGames.has(gameId)) return false;
  const update = standingsAfterProgressGame(state.data.dashboardStandings, event.game);
  if (!update) return false;
  state.simulationProcessedGames.add(gameId);
  const panel = document.querySelector('[data-board-window="standings"] .season-standings-panel');
  const displayedRows = [...(panel?.querySelectorAll(".season-standing-row") || [])];
  const displayedIds = displayedRows.map((row) => row.querySelector("[data-standing-team-id]")?.dataset.standingTeamId).filter(Boolean);
  const rankChanged = displayedIds.some((id) => update.previousRanks.get(id) !== update.nextRanks.get(id));
  const expanded = panel?.classList.contains("is-expanded") || false;
  state.data.dashboardStandings = update.snapshot;
  if (!panel) return false;
  if (rankChanged) {
    const oldPositions = new Map(displayedRows.map((row) => [
      row.querySelector("[data-standing-team-id]")?.dataset.standingTeamId,
      row.getBoundingClientRect().top,
    ]));
    setStandingsCardExpanded(expanded, panel);
    panel.querySelectorAll(".season-standing-row").forEach((row) => {
      const id = row.querySelector("[data-standing-team-id]")?.dataset.standingTeamId;
      if (!id) return;
      const movement = update.previousRanks.get(id) - update.nextRanks.get(id);
      if (movement) showRowMovement(row, movement > 0 ? "up" : "down", Math.abs(movement));
      const previousTop = oldPositions.get(id);
      if (previousTop !== undefined) animateRowFromPreviousPosition(row, previousTop);
    });
    return true;
  }
  const rowsById = new Map(standingsRows(update.snapshot).map((row) => [String(row.team?.id || row.team_id || row.id || ""), row]));
  for (const rowNode of displayedRows) {
    const id = rowNode.querySelector("[data-standing-team-id]")?.dataset.standingTeamId;
    const row = rowsById.get(id);
    if (!row) continue;
    const conference = String(row.team?.conference || row.conference || "");
    const leader = standingsRows(update.snapshot).find((candidate) => String(candidate.team?.conference || candidate.conference || "") === conference);
    const gamesBack = leader ? ((Number(leader.wins || 0) - Number(row.wins || 0)) + (Number(row.losses || 0) - Number(leader.losses || 0))) / 2 : 0;
    const cells = rowNode.querySelectorAll(":scope > span");
    if (cells[0]) cells[0].textContent = String(update.nextRanks.get(id) || "");
    if (cells[2]) cells[2].textContent = `${Number(row.wins || 0)}-${Number(row.losses || 0)}`;
    if (cells[3]) cells[3].textContent = winPct(row.win_pct);
    if (cells[4]) cells[4].textContent = gamesBack <= 0 ? "—" : Number.isInteger(gamesBack) ? String(gamesBack) : gamesBack.toFixed(1).replace(/^0/, "");
  }
  return false;
}

function updateRotationDuringSimulation(rotation) {
  const updates = Array.isArray(rotation) ? rotation : [];
  const table = document.querySelector('[data-board-window="minutes"] .season-minutes-table');
  const cardRows = table ? [...table.querySelectorAll(":scope > .season-minute-row")] : [];
  for (const update of updates) {
    const id = String(update.id || "");
    if (!id) continue;
    const minutes = Number(update.rotation_target_minutes ?? update.minutes_projection ?? 0);
    state.rotationDraft[id] = clampNumber(Number.isFinite(minutes) ? minutes : 0, 0, 48);
    if (update.rotation_user_set) state.rotationLockedPlayerIds.add(id);
    else state.rotationLockedPlayerIds.delete(id);
    const row = cardRows.find((item) => item.dataset.minuteRow === id);
    if (!row) continue;
    const injured = isPlayerInjured(update.health);
    row.classList.toggle("injured", injured);
    const input = row.querySelector("[data-minute-player]");
    if (input) input.disabled = injured || state.simulationRunning;
    const button = row.querySelector("button[data-dashboard-player-card]");
    if (button) {
      button.querySelector(".season-injury-status")?.remove();
      const statusMarkup = playerInjuryStatusMarkup({id, name:button.dataset.playerName || "Player", health:update.health});
      if (statusMarkup) {
        const template = document.createElement("template");
        template.innerHTML = statusMarkup;
        const motion = button.querySelector(".season-row-motion");
        button.insertBefore(template.content.firstElementChild, motion || null);
      }
    }
    const fatigue = row.querySelector(".season-fatigue");
    if (fatigue) {
      const template = document.createElement("template");
      template.innerHTML = seasonFatigueCell({health:update.health});
      fatigue.replaceWith(template.content.firstElementChild);
    }
  }
  if (table) {
    syncRotationInputs(table);
    normalizeMinutesDomOrder(table);
  }
}

function updateTeamSignalsDuringSimulation(identity) {
  if (teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam()) !== userTeam()) return;
  const panel = document.querySelector('[data-board-window="signals"] .season-identity-signals');
  if (!panel) return;
  const metrics = identity?.metrics || {};
  const ranks = identity?.ranks || {};
  const count = Number(identity?.league_team_count || identity?.team_count || 30);
  for (const row of panel.querySelectorAll(".season-signal-row[data-team-signal-key]")) {
    const key = row.dataset.teamSignalKey;
    const rank = Number(ranks[key] || count);
    const width = clampNumber(((count - rank + 1) / Math.max(1, count)) * 100, 3, 100);
    const bar = row.querySelector("i > b");
    const rankLabel = row.querySelector("[data-team-signal-rank]");
    if (bar) {
      const color = performanceBarColor(width);
      bar.style.setProperty("--fill", `${width}%`);
      bar.style.setProperty("--bar-color", color);
      bar.style.setProperty("background-color", color, "important");
    }
    if (rankLabel) rankLabel.textContent = `#${rank}/${count}`;
    row.title = `${Number(metrics[key] || 0).toFixed(1)} team rating · ranked ${rank} of ${count}`;
  }
  state.data.dashboard ||= {};
  state.data.dashboard.team_identity = identity;
}

function updateOpponentDuringSimulation(opponent) {
  if (teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam()) !== userTeam()) return;
  const game = opponent?.next_game;
  if (!opponent?.team || !game) return;
  // Never move the card back to a game this sim already finished.
  if (state.simulationCompletedGameIds?.has(String(game.game_id))) return;
  // While a W/L banner plays, the card stays on the finished game; the newest
  // opponent is applied when the banner ends.
  if (state.simulationOpponentResult) { state.simulationPendingOpponent = opponent; return; }
  opponent = simulationOpponentForDisplay(opponent);
  const signature = JSON.stringify([
    game.game_id, opponent.team?.id, opponent.record?.wins, opponent.record?.losses,
    (opponent.rotation || []).map((row) => [row.id, row.minutes_projection, row.health?.status, row.health?.days_left, row.display_ratings]),
    opponent.last_games?.[0]?.date,
  ]);
  if (signature === state.simulationOpponentSignature) return;
  state.simulationOpponentSignature = signature;
  state.data.dashboardOpponent = opponent;
  state.data.dashboard ||= {};
  state.data.dashboard.next_games = [game];
  renderSimulationOpponentPanel();
}

function renderSimulationOpponentPanel() {
  const panel = document.querySelector('[data-board-window="opponent"] .season-opponent-panel');
  if (!panel) return;
  panel.innerHTML = seasonOpponentCard(state.data.dashboard, userTeam());
  wireDashboardPlayerCards(panel);
  wireSeasonOpponentSorting(panel);
  wireSeasonOpponentInjuryTicker(panel);
}

// Earliest unplayed game for a team, skipping games finished during this sim.
function nextScheduledTeamGame(games, {completedIds = new Set(), afterDate = "", involvesTeam = () => true} = {}) {
  return [...(games || [])]
    .filter((game) => {
      const date = String(game?.date || "").slice(0, 10);
      if (!date || date < String(afterDate || "").slice(0, 10)) return false;
      if (completedIds.has(String(game.game_id || ""))) return false;
      if (game.status === "simulated" || game.result || (game.home_score != null && game.away_score != null)) return false;
      return involvesTeam(game);
    })
    .sort((left, right) => String(left.date).localeCompare(String(right.date)))[0] || null;
}

// Called when a W/L banner ends and the sim has not yet streamed the next
// opponent's full card: show the next scheduled game from the schedule data
// already loaded, or a waiting state. The next live update fills in the rest.
function showSimulationNextOpponentPreview(afterDate) {
  const viewed = userTeam();
  if (teamLabel(state.data.dashboard?.team || state.dashboardTeam || viewed) !== viewed) return;
  const calendar = state.data.dashboardCalendar || {};
  const next = nextScheduledTeamGame([...(state.simulationUpcomingGames || []), ...(calendar.games || calendar.calendar || [])], {
    completedIds: state.simulationCompletedGameIds || new Set(),
    afterDate,
    involvesTeam: (game) => [seasonGameTeamLabel(game, "home"), seasonGameTeamLabel(game, "away")].includes(viewed),
  });
  const opponentLabel = next ? seasonGameOpponent(next, viewed) : "";
  const standing = opponentLabel ? standingsRows(state.data.dashboardStandings).find((row) => teamLabel(row.team) === opponentLabel) : null;
  state.simulationOpponentSignature = "";
  state.data.dashboard ||= {};
  state.data.dashboard.next_games = next ? [{...next, is_home: next.is_home ?? seasonGameTeamLabel(next, "home") === viewed}] : [];
  state.data.dashboardOpponent = {
    pending: true,
    team: opponentLabel ? (standing?.team || state.teams.find((team) => teamLabel(team) === opponentLabel) || opponentLabel) : null,
    record: standing ? {wins: standing.wins, losses: standing.losses} : {},
    rotation: [],
    last_games: [],
  };
  renderSimulationOpponentPanel();
}

function finishSimulationOpponentResult(hold) {
  hold.banner?.remove();
  if (state.simulationOpponentResult === hold) {
    state.simulationOpponentResult = null;
    const pending = state.simulationPendingOpponent;
    state.simulationPendingOpponent = null;
    // After the sim ends, the final dashboard snapshot is the authority.
    if (state.simulationRunning && !hold.final) {
      if (pending) updateOpponentDuringSimulation(pending);
      else showSimulationNextOpponentPreview(hold.date);
    }
  }
  hold.resolve?.();
}

const DISPLAY_RATING_ANCHORS = [
  [1, 25], [20, 36], [30, 48], [40, 60], [50, 70],
  [60, 80], [70, 88], [80, 95], [90, 98], [99, 99],
];

function displayRatingValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  const raw = clampNumber(numeric, 1, 99);
  for (let index = 1; index < DISPLAY_RATING_ANCHORS.length; index += 1) {
    const [highRaw, highDisplay] = DISPLAY_RATING_ANCHORS[index];
    const [lowRaw, lowDisplay] = DISPLAY_RATING_ANCHORS[index - 1];
    if (raw <= highRaw) {
      const share = (raw - lowRaw) / Math.max(0.001, highRaw - lowRaw);
      return Math.round(clampNumber(lowDisplay + share * (highDisplay - lowDisplay), 1, 99) * 10) / 10;
    }
  }
  return 99;
}

function simulationOpponentForDisplay(opponent) {
  return {
    ...opponent,
    rotation: (opponent.rotation || []).map((row) => {
      const cachedRatings = state.simulationPlayerRatingsById?.get(String(row.id || row.player_id || ""));
      if (cachedRatings) return {...row, display_ratings:cachedRatings};
      if (row.display_ratings || !row.attributes) return row;
      const attributes = row.attributes || {};
      const displayRatings = Object.fromEntries(Object.entries(attributes)
        .map(([key, value]) => [key, displayRatingValue(value)])
        .filter(([, value]) => value !== null));
      return Object.keys(displayRatings).length ? {...row, display_ratings:displayRatings} : row;
    }),
  };
}

function simulationOpponentResult(event, userTeamId) {
  const game = event?.game;
  const home = Number(game?.home_score);
  const away = Number(game?.away_score);
  if (!game?.game_id || !userTeamId || !Number.isFinite(home) || !Number.isFinite(away) || home === away) return null;
  const userIsHome = String(game.home_team_id) === String(userTeamId);
  if (!userIsHome && String(game.away_team_id) !== String(userTeamId)) return null;
  const score = userIsHome ? home : away;
  const opponentScore = userIsHome ? away : home;
  return {
    result: score > opponentScore ? "W" : "L",
    score,
    opponentScore,
    opponentId: userIsHome ? game.away_team_id : game.home_team_id,
  };
}

function showSimulationOpponentResult(event) {
  const outcome = simulationOpponentResult(event, state.home?.save?.user_team?.id);
  if (!outcome) return false;
  // A banner still playing for an earlier game ends now, so this result lands
  // on its own opponent rather than the previous one.
  if (state.simulationOpponentResult && state.simulationOpponentResult.gameId !== String(event.game.game_id)) {
    finishSimulationOpponentResult(state.simulationOpponentResult);
  }
  state.simulationCompletedGameIds?.add(String(event.game.game_id));
  const frame = document.querySelector('[data-board-window="opponent"]');
  const panel = frame?.querySelector(".season-opponent-panel");
  const table = panel?.querySelector(".season-opponent-table");
  if (!table || frame.dataset.resultGameId === String(event.game.game_id)) return false;
  frame.dataset.resultGameId = String(event.game.game_id);
  const userLabel = teamLabel(state.home?.save?.user_team || userTeam());
  const opponent = teamLabel(state.teams.find((team) => team.id === outcome.opponentId) || outcome.opponentId);
  panel.querySelector(".season-simulation-result-banner")?.remove();
  const banner = document.createElement("div");
  banner.className = `season-simulation-result-banner ${outcome.result === "W" ? "is-win" : "is-loss"}`;
  banner.setAttribute("role", "status");
  banner.setAttribute("aria-live", "polite");
  banner.innerHTML = `<strong>${outcome.result}</strong><span>${escapeHtml(userLabel)} ${outcome.score} <i>·</i> ${escapeHtml(opponent)} ${outcome.opponentScore}</span><small>FINAL</small>`;
  table.append(banner);
  const hold = {gameId:String(event.game.game_id), date:String(event.date || ""), banner, final:false};
  hold.done = new Promise((resolve) => { hold.resolve = resolve; });
  state.simulationOpponentResult = hold;
  // Matches the 1500ms banner animation in card-board.css.
  window.setTimeout(() => finishSimulationOpponentResult(hold), 1500);
  return true;
}

function captureTeamSignalBars() {
  const panel = document.querySelector('[data-board-window="signals"] .season-identity-signals');
  if (!panel) return null;
  return Object.fromEntries([...panel.querySelectorAll(".season-signal-row[data-team-signal-key]")].map((row) => {
    const bar = row.querySelector("i > b");
    return [row.dataset.teamSignalKey, {
      fill: bar ? getComputedStyle(bar).width : "0px",
      color: bar ? getComputedStyle(bar).backgroundColor : "#73838b",
    }];
  }));
}

function animateTeamSignalsFrom(previous) {
  if (!previous || GameSimulation.reducedMotion()) return;
  const panel = document.querySelector('[data-board-window="signals"] .season-identity-signals');
  if (!panel) return;
  for (const row of panel.querySelectorAll(".season-signal-row[data-team-signal-key]")) {
    const prior = previous[row.dataset.teamSignalKey];
    const bar = row.querySelector("i > b");
    if (!prior || !bar) continue;
    const parentWidth = bar.parentElement?.clientWidth || 1;
    const priorPercent = clampNumber((parseFloat(prior.fill) / parentWidth) * 100, 0, 100);
    bar.style.transition = "none";
    bar.style.setProperty("--fill", `${priorPercent}%`);
    bar.style.setProperty("--bar-color", prior.color);
    bar.style.setProperty("background-color", prior.color, "important");
    void bar.offsetWidth;
  }
  requestAnimationFrame(() => {
    panel.querySelectorAll(".season-signal-row[data-team-signal-key] > i > b").forEach((bar) => bar.style.removeProperty("transition"));
    updateTeamSignalsDuringSimulation(state.data.dashboard?.team_identity || {});
  });
}

function reorderMinutesTable(table) {
  const rows = table ? [...table.querySelectorAll(":scope > .season-minute-row")] : [];
  if (rows.length < 2) return;
  const previousTops = new Map(rows.map((row) => [row, row.getBoundingClientRect().top]));
  const previousOrder = new Map([...rows].sort((left, right) => previousTops.get(left) - previousTops.get(right)).map((row, index) => [row, index]));
  const ordered = [...rows].sort((left, right) => {
    const leftValue = left.classList.contains("injured") ? 0 : Number(state.rotationDraft[left.dataset.minuteRow] || 0);
    const rightValue = right.classList.contains("injured") ? 0 : Number(state.rotationDraft[right.dataset.minuteRow] || 0);
    return rightValue - leftValue || previousOrder.get(left) - previousOrder.get(right);
  });
  ordered.forEach((row, index) => { row.style.gridRow = String(index + 2); });
  ordered.forEach((row, index) => {
    const previousIndex = previousOrder.get(row);
    if (previousIndex !== index) showRowMovement(row, index < previousIndex ? "up" : "down", Math.abs(previousIndex - index));
    animateRowFromPreviousPosition(row, previousTops.get(row));
  });
}

function normalizeMinutesDomOrder(table) {
  if (!table) return;
  const rows = [...table.querySelectorAll(":scope > .season-minute-row")];
  rows.sort((left, right) => {
    const leftValue = left.classList.contains("injured") ? 0 : Number(state.rotationDraft[left.dataset.minuteRow] || 0);
    const rightValue = right.classList.contains("injured") ? 0 : Number(state.rotationDraft[right.dataset.minuteRow] || 0);
    return rightValue - leftValue || left.dataset.minuteRow.localeCompare(right.dataset.minuteRow);
  });
  rows.forEach((row) => { row.style.gridRow = ""; table.append(row); });
}

function showRowMovement(row, direction, places = 1) {
  const indicator = row.querySelector(".season-row-motion");
  if (!indicator) return;
  window.clearTimeout(indicator._movementTimer);
  indicator.className = `season-row-motion ${direction}`;
  indicator.textContent = `${direction === "up" ? "↑" : "↓"}${places > 1 ? places : ""}`;
  indicator.title = `Moved ${direction} ${places} ${places === 1 ? "place" : "places"}`;
  indicator.hidden = false;
  indicator._movementTimer = window.setTimeout(() => { indicator.hidden = true; }, 1200);
}

function animateRowFromPreviousPosition(row, previousTop) {
  if (previousTop === undefined || GameSimulation.reducedMotion() || typeof row.animate !== "function") return;
  const delta = previousTop - row.getBoundingClientRect().top;
  if (Math.abs(delta) < 1) return;
  row.getAnimations().forEach((animation) => animation.cancel());
  row.animate([{transform:`translateY(${delta}px)`},{transform:"translateY(0)"}], {duration:320, easing:"cubic-bezier(.2,.75,.25,1)"});
}

function maybeCelebrateChampion() {
  if (!state.home?.save?.postseason_exit_required || state.simulationRunning || state.hydrating || state.modal || state.tutorial) return;
  const key = `nbaGmChampionCelebrated:${state.currentSave}:${state.home.save.season}`;
  state.championCelebratedKeys ||= new Set();
  if (state.championCelebratedKeys.has(key)) return;
  try { if (sessionStorage.getItem(key)) return; sessionStorage.setItem(key,'1'); } catch {}
  state.championCelebratedKeys.add(key);
  window.CardBoard?.open('phase-playoffs-bracket');
  const champion = teamLabel(state.data.playoffs?.champion || state.home.save.playoff_champion_team_id);
  const confettiColors = ['#bd922e','#e2c66c','#a74a51','#607f99','#f0e6ca'];
  const confetti = Array.from({length:30},(_,index)=>{
    const x=(index*37+11)%100;
    const drift=(index*19)%65-32;
    const spin=(index*53)%500-250;
    return `<i class="champion-confetti-piece" style="--x:${x}%;--delay:${(index%9)*42}ms;--drift:${drift}px;--spin:${spin}deg;--confetti-color:${confettiColors[index%confettiColors.length]}"></i>`;
  }).join('');
  state.modal = {kind:'champion',title:'NBA Champions',body:`<section class="champion-celebration"><div class="champion-confetti" aria-hidden="true">${confetti}</div><img class="champion-trophy" src="/assets/header-art/exports/trophy-press-ink.png" alt="Championship trophy"/><h2>${escapeHtml(dashboardTeamName(champion) || champion)}</h2><p>${escapeHtml(state.home.save.season)} NBA Champions</p><button type="button" class="ui-command" data-champion-bracket data-close-modal>View Bracket</button></section>`};
  renderModal();
}

function tradeDeadlineDate() {
  const current = String(state.home?.save?.current_date || "");
  const startYear = Number(current.slice(0, 4)) - (Number(current.slice(5, 7)) < 7 ? 1 : 0);
  return state.home?.trade_deadline?.date || `${startYear + 1}-02-05`;
}

function tradeDeadlineAcknowledgmentKey(deadline) {
  const save = String(state.currentSave || "active-save");
  return `nbaGmTradeDeadlineAcknowledged:${encodeURIComponent(save)}:${deadline}`;
}

function hasAcknowledgedTradeDeadline(deadline) {
  if (state.tradeDeadlineAcknowledgedSave === state.currentSave
      && state.tradeDeadlineAcknowledgedDate === deadline) return true;
  try { return localStorage.getItem(tradeDeadlineAcknowledgmentKey(deadline)) === "1"; }
  catch { return false; }
}

function acknowledgeTradeDeadline(deadline) {
  if (!deadline) return;
  state.tradeDeadlineAcknowledgedSave = state.currentSave;
  state.tradeDeadlineAcknowledgedDate = deadline;
  try { localStorage.setItem(tradeDeadlineAcknowledgmentKey(deadline), "1"); }
  catch { /* Keep this session's confirmation if browser storage is unavailable. */ }
}

function tradeDeadlineCalendarNotice(month) {
  const deadline = tradeDeadlineDate();
  if (deadline.slice(0, 7) !== month) return "";
  const today = state.home?.save?.current_date === deadline;
  return `<div class="trade-deadline-calendar-notice"${today ? ' role="status"' : ""}><strong>Trade deadline${today ? " · Today" : ""}</strong><span>${escapeHtml(formatWrittenDate(deadline))}</span></div>`;
}

function showTradeDeadlinePrompt(checkpoint = {}, payload = {}) {
  if (!checkpoint.date && state.modal?.kind === "tradeDeadline") return;
  const deadline = checkpoint.date || tradeDeadlineDate();
  if (hasAcknowledgedTradeDeadline(deadline)) return;
  const followingDay = new Date(`${deadline}T00:00:00Z`);
  followingDay.setUTCDate(followingDay.getUTCDate() + 1);
  const target = checkpoint.requested_to_date > deadline ? checkpoint.requested_to_date : followingDay.toISOString().slice(0, 10);
  const resume = {...payload, to_date:target, next_event:false, checkpoint_days:payload.checkpoint_days || 31, trade_deadline_confirmed:deadline};
  delete resume.days;
  state.modal = {
    kind:"tradeDeadline", title:"Trade Deadline", subtitle:"", deadlineResume:resume,
    body:`<section class="trade-deadline-prompt"><strong class="trade-deadline-prompt-date">${escapeHtml(formatWrittenDate(deadline))}</strong><p>The sim is paused. This is the last day to trade before the deadline closes.</p><p>Enter the deadline to make deals, or continue simming to ${escapeHtml(formatWrittenDate(target))}.</p><div class="trade-deadline-prompt-actions"><button type="button" class="ui-command" data-enter-trade-deadline>Enter Trade Deadline</button><button type="button" class="ui-command" data-sim-through-deadline>Sim Through Deadline</button></div></section>`,
  };
  renderModal();
}

function postseasonBoundaryDate() {
  const season = String(state.home?.save?.season || "");
  const current = String(state.home?.save?.current_date || "");
  const start = Number(season.slice(0, 4)) || (Number(current.slice(0, 4)) - (Number(current.slice(5, 7)) < 7 ? 1 : 0));
  return `${start + 1}-04-13`;
}

function postseasonReviewKey(date) {
  return `nbaGmPostseasonReviewed:${encodeURIComponent(state.currentSave || "active-save")}:${date}`;
}

function hasReviewedPostseason(date) {
  if (state.postseasonReviewedSave === state.currentSave && state.postseasonReviewedDate === date) return true;
  try { return localStorage.getItem(postseasonReviewKey(date)) === "1"; } catch { return false; }
}

function showPostseasonPrompt(checkpoint) {
  state.modal = {
    kind:"postseason", title:"Regular Season Complete", subtitle:"", postseasonBoundary:checkpoint.date,
    body:`<section class="trade-deadline-prompt"><strong class="trade-deadline-prompt-date">${escapeHtml(formatWrittenDate(state.home?.save?.current_date || checkpoint.date))}</strong><p>The regular season is over. The sim is paused before postseason games begin.</p><p>Review the bracket, including the play-in, then choose a sim command to continue.</p><div class="trade-deadline-prompt-actions"><button type="button" class="ui-command" data-review-postseason>Review Bracket</button></div></section>`,
  };
  renderModal();
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
  state.lotteryRunId = (state.lotteryRunId || 0) + 1;
  state.lotteryRevealRunning = false;
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
    window.AssistantGMPhone?.hide();
    renderStartup();
    window.StartupVideoBackdrop?.sync();
    return;
  }
  els.startupScreen.hidden = true;
  window.StartupVideoBackdrop?.sync();
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
  syncAssistantGMPhone();
}

function renderStartup() {
  document.getElementById("roomNavigation")?.remove();
  els.content.innerHTML = "";
  els.startupScreen.hidden = false;
  updateStartupSaveControls();
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
    <strong>${league.clock?.pause_reason === "trade_deadline" ? "Trade deadline · Paused" : formatClock(seconds)}</strong>
    <button data-human-trade-inbox>GM Offers ${state.multiplayer.humanTradeOffers.filter((offer) => offer.direction === "incoming").length}</button>
    <button data-multiplayer-ready>${manager?.ready ? "Ready ✓" : "Ready Up"}</button>`;
  els.multiplayerBar.querySelector("[data-human-trade-inbox]")?.addEventListener("click", openHumanTradeInbox);
  els.multiplayerBar.querySelector("[data-multiplayer-ready]")?.addEventListener("click", async () => {
    if (!state.multiplayer.manager?.ready && state.home?.save?.current_date === tradeDeadlineDate()
        && !hasAcknowledgedTradeDeadline(tradeDeadlineDate())) return showTradeDeadlinePrompt();
    try {
      const result = await multiplayerRequest("set_ready", {
        ready: !state.multiplayer.manager?.ready,
        expected_revision: state.multiplayer.league.revision,
      });
      state.multiplayer.league = result.league || result;
      state.multiplayer.manager = state.multiplayer.league.managers.find(
        (row) => row.id === state.multiplayer.session.manager_id,
      );
      if (result.status === "advanced") {
        await refreshHome();
        if (result.result?.trade_deadline_checkpoint) showTradeDeadlinePrompt(result.result.trade_deadline_checkpoint);
      }
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
  if ((!phase || isClipboardPhase(phase)) && ["draft", "playoffs", "freeagents", "freeagency", "staff", "calendar"].includes(state.view)) {
    state.clipboardRequestedView = state.view;
    state.view = "dashboard";
    return;
  }
  if ((state.view === "draft" && phase === "draft") ||
      (state.view === "playoffs" && phase === "playoffs") ||
      (["freeagents", "freeagency"].includes(state.view) && phase === "free_agency")) state.view = "dashboard";
}

function requiredClipboardDecision() {
  if (Number(state.home?.save?.pending_counts?.staff || 0) > 0) return "staff_retention";
  if (Number(state.home?.save?.pending_counts?.cutdowns || 0) > 0) return "cutdown";
  return "";
}

function revealRequiredClipboardDecision() {
  const kind = requiredClipboardDecision();
  window.CardBoard?.open(`phase-${kind}-decision`);
  showToast(kind === "staff_retention" ? "Resolve staff retention before advancing." : "Complete the roster cutdown before advancing.", true);
}

function dashboardPhaseKind() {
  const required = requiredClipboardDecision();
  if (required) return required;
  if (state.home?.save?.postseason_exit_required) return "playoffs";
  const phase = String(state.home?.save?.phase || "");
  if (phase === "fantasy_draft") return "fantasy_draft";
  if (phase === "play_in" || phase === "playoffs") return "playoffs";
  if (phase === "draft_lottery" || phase === "draft") return "draft";
  if (phase === "re_signing" || phase === "free_agency") return "free_agency";
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
    if ((!phaseKind || isClipboardPhase(phaseKind)) && typeof mountDashboardCardBoard === "function") {
      mountDashboardCardBoard(target);
      wireRotationResetAllControl(target);
    }
    wireSeasonOpponentSorting(target);
    wireSeasonOpponentInjuryTicker(target);
    if (phaseKind) {
      wireDashboardPhaseWorkspace(phaseKind, target);
    }
    if (!phaseKind && state.data.freeagency) wireFreeAgencyMarket(target);
    if (phaseKind === "fantasy_draft") restoreFantasyBoardScroll();
    if (state.clipboardRequestedView) {
      const view = state.clipboardRequestedView;
      state.clipboardRequestedView = null;
      openClipboardWindow(view).catch(error => showToast(error.message || String(error), true));
    }
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
  if (phaseKind && !isClipboardPhase(phaseKind)) {
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
  const shortDate = formatDashboardShortDate(save.current_date);
  const dateLabel = shortDate
    ? `${shortDate}, ${String(save.current_date).slice(0, 4)}`
    : formatWrittenDate(save.current_date) || save.current_date || "";
  const disabled = editable ? "" : "disabled";
  return `<div class="season-command-dashboard" ${teamBrandStyle(viewedTeam)}>
    <header class="season-command-header">
      <div class="season-command-club">
        ${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(viewedTeam)} logo" />` : ""}
        <span>${escapeHtml(dashboardTeamName(viewedTeam))}</span>
        <div class="season-command-date">
          <time datetime="${escapeAttr(save.current_date || "")}">${escapeHtml(dateLabel)}</time>
          <span>${escapeHtml(rowLabel(save.phase || "season"))}</span>
        </div>
        ${viewedTeam !== userTeam() ? `<button type="button" data-dashboard-team-reset>My Team</button>` : ""}
      </div>
      <div class="season-command-actions">
        ${save.current_date === tradeDeadlineDate() ? '<button type="button" class="trade-deadline-today ui-command" data-trade-deadline-open>Trade deadline · Today</button>' : ""}
        <button type="button" data-dashboard-player-finder ${disabled}>Player Finder</button>
        <button type="button" data-dashboard-settings>Settings</button>
      </div>
    </header>
    <main class="season-command-grid">
      <div class="season-diagnostics-row">
        <section class="season-command-panel season-identity-panel">${seasonIdentityCard(rows, dash)}</section>
        <div class="season-signals-panel">${seasonTeamSignalsCard(dash)}</div>
        <div class="season-radars-panel">${seasonTeamRadarsCard(dash)}</div>
        <section class="season-command-panel season-standings-panel standings-card">${seasonStandingsCard(viewedTeam)}</section>
        <div class="season-matchup-stack">
          <section class="season-command-panel season-week-panel">${seasonWeekCard(dash, viewedTeam)}</section>
          <section class="season-command-panel season-opponent-panel">${seasonOpponentCard(dash, viewedTeam)}</section>
        </div>
      </div>
      <div class="season-operations-row">
        <section class="season-command-panel season-minutes-panel">${seasonMinutesCard(rows, editable)}</section>
        <section class="season-command-panel season-development-panel">${seasonDevelopmentCard(rows)}</section>
        <div class="season-intelligence-grid">
          <section class="season-command-panel season-efficiency-panel">${seasonEfficiencyCard(dash)}</section>
          <section class="season-command-panel season-prospects-panel">${seasonProspectsCard()}</section>
          <div class="season-intelligence-lower">
            <div class="season-awards-panel">${seasonAwardsCard(editable)}</div>
            <section class="season-command-panel season-staff-panel">${seasonStaffCard(dash)}</section>
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
    ["Overall", "overall", metrics.overall, ranks.overall],
    ["Offense", "offense", metrics.offense, ranks.offense],
    ["Defense", "defense", metrics.defense, ranks.defense],
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
    ["Team Signals", broad.map(([label, key, value, rank]) => seasonIdentityBar(label, key, value, rank, count)).join("")],
    ["Morale", moraleRows.map(([label, value]) => seasonMoraleBar(label, value)).join("")],
    ["Four Factors", factors.map((factor) => seasonFactorBar(factor)).join("")],
  ].map(([title, body]) => `<section class="season-command-panel season-signal-card">${seasonPanelHeader(title)}<div class="season-identity-signals">${body}</div></section>`).join("");
}

function seasonTeamRadarsCard(dash) {
  const identity = dash.team_identity || {};
  const ranks = identity.ranks || {};
  const count = Number(identity.league_team_count || identity.team_count || 30);
  const offenseAxes = [
    ["Shooting", "spacing"],
    ["Range", "spacing"],
    ["Creation", "creation"],
    ["Passing", "creation"],
    ["Rim pressure", "offense"],
    ["Off. rebounding", "depth"],
  ];
  const defenseAxes = [
    ["Defense", "defense"],
    ["Effort", "defense"],
    ["Screen nav", "defense"],
    ["Rim deterrence", "rim_protection"],
    ["Rebounding", "depth"],
    ["Athleticism", "defense"],
  ];
  return `<div class="season-radars-stack">
      ${seasonIdentityRadar("Offense", offenseAxes, ranks, count)}
      ${seasonIdentityRadar("Defense", defenseAxes, ranks, count)}
    </div>`;
}

function seasonIdentityBar(label, key, value, rank, count) {
  const numericRank = Number(rank || count);
  const width = clampNumber(((count - numericRank + 1) / Math.max(1, count)) * 100, 3, 100);
  return `<div class="season-signal-row" data-team-signal-key="${escapeAttr(key)}" title="${Number(value || 0).toFixed(1)} team rating · ranked ${numericRank} of ${count}">
    <span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(width)};background-color:${performanceBarColor(width)} !important"></b></i><strong data-team-signal-rank>#${numericRank}/${count}</strong>
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
    <span>${escapeHtml(factor.label || "Factor")}</span><i><b style="--fill:${clampNumber(value, 0, 100)}%;--bar-color:${performanceBarColor(score)}"></b><u style="left:${clampNumber(average, 0, 100)}%"></u></i><strong>${value.toFixed(1)}</strong>
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
  const delta = Number.isFinite(Number(value)) ? Math.max(-8, Math.min(8, Number(value))) : 0;
  const stops = [[-8,[189,75,88]],[-3,[219,145,153]],[0,[168,179,189]],[3,[113,168,212]],[8,[52,125,235]]];
  const index = Math.max(1, stops.findIndex(([point]) => delta <= point));
  const [low, a] = stops[index - 1], [high, b] = stops[index];
  const fraction = (delta - low) / (high - low);
  return `#${a.map((channel, i) => Math.round(channel + (b[i] - channel) * fraction).toString(16).padStart(2, "0")).join("")}`;
}

function spatialHexPoints(centerX, centerY, radius) {
  return Array.from({ length: 6 }, (_unused, index) => {
    const angle = Math.PI / 6 + (Math.PI / 3) * index;
    return `${(centerX + Math.cos(angle) * radius).toFixed(1)},${(centerY + Math.sin(angle) * radius).toFixed(1)}`;
  }).join(" ");
}

function spatialHexRadius(density, leagueMeanDensity) {
  const ratio = Math.max(0, Number(density) || 0) / Math.max(Number(leagueMeanDensity) || 0, 0.000025);
  // Hex area, rather than its radius, is proportional to relative density.
  return Math.max(1.8, Math.min(12, 7 * Math.sqrt(ratio)));
}

const SPATIAL_COURT_VIEWS = {
  offense: { density: 3, delta: "delta_pp", tab: "Scoring", legend: "His FG vs league (pp)", caption: "His own shots: where he shoots, and his projected FG% against league average." },
  playmaking: { density: 6, delta: "playmaking_delta_pp", tab: "Playmaking", legend: "Teammates' FG change (pp)", caption: "His teammates' shots while he plays (his own shots left out): where they shoot, and how much better or worse they shoot because of his passing, driving and gravity." },
  defense: { density: 4, delta: "suppression_delta_pp", tab: "Overall", legend: "Suppression (pp)", caption: "All of his defense: how much he lowers opponents' FG% by zone. Blue is better defense." },
  onball: { density: 7, delta: "onball_delta_pp", tab: "On his man", legend: "His man held below league (pp)", caption: "The man he guards: where players his size shoot, and how much he holds them below league FG%." },
  help: { density: 8, delta: "help_delta_pp", tab: "Help", legend: "Others held below league (pp)", caption: "Everyone else while he plays (his own man left out): how much his rim protection and rotations lower their FG%." },
};
const SPATIAL_TEAM_CAPTIONS = {
  offense: "The team's shots: where its rotation shoots, and projected FG% against league average.",
  playmaking: "How much the team's passing, driving and gravity raise its shooting by zone, as the sim applies it.",
  defense: "The team's defense: how much its rotation lowers opponents' FG% by zone. Blue is better defense.",
  onball: "Defense on the ball: how much the rotation holds the men it guards below league FG%.",
  help: "Help defense: how much rim protection and rotations lower everyone else's FG%.",
};
function spatialCourtCaption(view, team) {
  return team ? SPATIAL_TEAM_CAPTIONS[view] : SPATIAL_COURT_VIEWS[view].caption;
}

function spatialHeatmapRegions(profile, side) {
  const chart = profile?.shot_chart;
  if (!chart?.cells?.length || !chart.regions?.length || chart.basis === "unavailable") return "";
  const view = SPATIAL_COURT_VIEWS[side] || SPATIAL_COURT_VIEWS.defense;
  const cellsByRegion = new Map(chart.regions.map(region => [Number(region.id), []]));
  const leagueMeanDensity = chart.cells.reduce((total, cell) => total + Number(cell[5]), 0) / chart.cells.length;
  chart.cells.forEach(cell => cellsByRegion.get(Number(cell[2]))?.push(cell));
  const densityIndex = view.density;
  return chart.regions.map(region => {
    const cells = cellsByRegion.get(Number(region.id)) || [];
    if (!cells.length) return "";
    const teamDensity = cells.reduce((total, cell) => total + Number(cell[densityIndex]), 0);
    const leagueDensity = cells.reduce((total, cell) => total + Number(cell[5]), 0);
    const meanCellDensity = teamDensity / cells.length;
    const ratio = meanCellDensity / Math.max(leagueMeanDensity, 0.000025);
    const localRatio = teamDensity / Math.max(leagueDensity, 0.000025);
    const rawDelta = region[view.delta];
    const delta = rawDelta == null ? null : Number(rawDelta);
    const known = delta != null && Number.isFinite(delta);
    const color = known ? spatialEfficiencyColor(delta) : "#d4dce2";
    const hexes = cells.map(cell => {
      const [x, y] = cell;
      const density = Number(cell[densityIndex] || 0);
      if (density < 0.000025) return "";
      const ratio = density / Math.max(leagueMeanDensity, 0.000025);
      const radius = spatialHexRadius(density, leagueMeanDensity);
      return `<polygon class="spatial-court-hex" data-side="${side}" data-region="${Number(region.id)}" data-density-ratio="${ratio.toFixed(3)}" points="${spatialHexPoints(x, y, radius)}" fill="${color}" pointer-events="none"/>`;
    }).join("");
    const value = side === "offense" && region.fg_pct != null
      ? `Projected FG ${Number(region.fg_pct).toFixed(1)}%, league ${Number(region.league_fg_pct).toFixed(1)}%`
      : side === "defense" ? "Modeled defensive suppression"
      : side === "playmaking" ? "Teammates' FG change with him on court"
      : side === "onball" ? "His man's FG held below league"
      : side === "help" ? "Other opponents' FG held below league" : "Reference unavailable";
    const comparison = known ? `${delta >= 0 ? "+" : ""}${delta.toFixed(1)} pp vs league` : "Comparison unavailable";
    const title = `${region.label}: ${value}; ${comparison}; ${ratio.toFixed(2)}x league mean cell density; ${localRatio.toFixed(2)}x estimated league density in this region`;
    const hit = spatialRegionGeometry(cells);
    return `<g class="spatial-court-hex-region" data-region="${Number(region.id)}">
      ${hexes}
      <path class="spatial-region-hit" d="${hit}" fill="transparent" fill-rule="nonzero" pointer-events="all" tabindex="0" role="img" aria-label="${escapeAttr(title)}"><title>${escapeHtml(title)}</title></path>
    </g>`;
  }).join("");
}

function spatialRegionGeometry(cells) {
  const hit = [];
  cells.forEach(([x, y]) => {
    const points = spatialHexPoints(x, y, 12.5).split(" ");
    hit.push(`M${points[0]}L${points.slice(1).join("L")}Z`);
  });
  return hit.join("");
}

function spatialHeatmapLegend(label, side) {
  const meaning = side === "offense" ? "Projected FG% minus league FG%" : "Modeled reduction in opponent FG% versus league; blue is better defense, not observed opponent shooting";
  const detail = `${meaning}. Fixed continuous color scale: -8 to +8 percentage points, neutral at zero; endpoints saturate. Hex area: attempt/contest density relative to league mean cell density, capped at 2.94x. Offense volume follows observed current-season 3PA/FGA when the sample is reliable; efficiency remains projected. Defense volume remains modeled.`;
  return `<div class="spatial-legend" title="${escapeAttr(detail)}"><span>${label}</span><i class="spatial-discrete-key spatial-numeric-key" role="img" aria-label="${escapeAttr(detail)}">${[-8,-3,0,3,8].map(delta => `<span class="spatial-key-stop"><b style="background:${spatialEfficiencyColor(delta)}"></b><em>${delta > 0 ? "+" : ""}${delta}</em></span>`).join("")}</i></div>`;
}

function spatialCourtSvg(seed, side, regions, hidden) {
  const label = { offense: "Projected shooting efficiency", playmaking: "Teammates' shooting change with him on court", defense: "Modeled defensive suppression", onball: "Shooting of the man he guards", help: "Other opponents' shooting with him on court" }[side];
  const group = side === "offense" || side === "playmaking" ? "offense" : "defense";
  return `<svg class="spatial-court" viewBox="0 0 500 470" role="img" aria-label="${label} versus league average" data-court-view="${side}" data-court-group="${group}"${hidden ? " hidden" : ""}>
      <defs><clipPath id="spatial-court-clip-${seed}-${side}"><rect x="2" y="2" width="468" height="496"/></clipPath></defs>
      <g transform="matrix(0 -1 1 0 0 470)">
      <rect class="spatial-court-floor" x="2" y="2" width="468" height="496"/>
      <g clip-path="url(#spatial-court-clip-${seed}-${side})">${regions}</g>
      <g class="spatial-court-markings">
        <rect class="spatial-court-line" x="2" y="2" width="468" height="496"/>
        <path class="spatial-court-line" d="M470 190 A60 60 0 0 0 470 310"/>
        <rect class="spatial-court-line" x="2" y="170" width="188" height="160"/>
        <path class="spatial-court-line" d="M190 190 A60 60 0 0 1 190 310"/><path class="spatial-court-line dashed" d="M190 190 A60 60 0 0 0 190 310"/>
        <line class="spatial-court-line" x1="40" y1="220" x2="40" y2="280"/><circle class="spatial-court-rim" cx="52.5" cy="250" r="7.5"/>
        <path class="spatial-court-line" d="M52.5 210 A40 40 0 0 1 52.5 290"/>
        <path class="spatial-court-line three-point" d="M2 30 H142 A237.5 237.5 0 0 1 142 470 H2"/>
      </g>
      </g>
    </svg>`;
}

function spatialHeatmapMarkup(profile, options = {}) {
  if (!profile?.zones?.length) return `<div class="spatial-heatmap-empty">Spatial profile unavailable</div>`;
  if (!profile.shot_chart?.cells?.length || profile.shot_chart.basis === "unavailable") return `<div class="spatial-heatmap-empty" role="status">Shot reference unavailable</div>`;
  const seed = String(profile.seed || profile.entity_id || "spatial").replace(/[^a-zA-Z0-9_-]/g, "");
  const extended = (profile.shot_chart.views || []).includes("playmaking") && (profile.shot_chart.cells[0] || []).length >= 9;
  const groups = extended ? { offense: ["offense", "playmaking"], defense: ["defense", "onball", "help"] } : { offense: ["offense"], defense: ["defense"] };
  const legends = `<div class="spatial-legends">${spatialHeatmapLegend("Projected FG (pp)", "offense")}${spatialHeatmapLegend("Suppression (pp)", "defense")}</div>`;
  const head = group => {
    const title = group === "offense" ? "Offense" : "Defense";
    if (groups[group].length === 1) return `<h4>${title}</h4>`;
    return `<h4 class="spatial-court-tabs" role="group" aria-label="${title} chart">${groups[group].map((view, index) => `<button type="button" class="spatial-court-tab" data-court-tab="${view}" data-court-group="${group}" aria-pressed="${index === 0}" title="${escapeAttr(spatialCourtCaption(view, profile.entity_type === "team"))}">${escapeHtml(profile.entity_type === "team" && view === "onball" ? "On the ball" : SPATIAL_COURT_VIEWS[view].tab)}</button>`).join("")}</h4>`;
  };
  const courts = ["offense", "defense"].flatMap(group => groups[group].map((view, index) => spatialCourtSvg(seed, view, spatialHeatmapRegions(profile, view), index > 0))).join("");
  const team = profile.entity_type === "team";
  const captions = extended ? `<p class="spatial-court-caption" data-court-caption="offense">${escapeHtml(spatialCourtCaption("offense", team))}</p><p class="spatial-court-caption" data-court-caption="defense">${escapeHtml(spatialCourtCaption("defense", team))}</p>` : "";
  return `<div class="spatial-heatmap${options.compact ? " compact" : ""}${extended ? " has-court-views" : ""}"${team ? ' data-court-entity="team"' : ""}>
    <div class="spatial-court-head">${head("offense")}${head("defense")}</div>
    <div class="spatial-half-courts">${courts}</div>
    ${legends}${captions}
  </div>`;
}

function seasonIdentityRadar(title, axes, ranks, count) {
  const current = axes.map(([_label, rankKey]) => seasonRadarRankScore(ranks[rankKey], count));
  const width = 360;
  const height = 280;
  const cx = 180;
  const cy = 140;
  const radius = 74;
  const point = (index, value, extra = 0) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / axes.length;
    const distance = radius * clampNumber(Number(value || 0) / 100, 0, 1) + extra;
    return [cx + Math.cos(angle) * distance, cy + Math.sin(angle) * distance];
  };
  const polygon = (values) => values.map((value, index) => point(index, value).map((part) => part.toFixed(1)).join(",")).join(" ");
  const ring = (level) => axes.map((_axis, index) => point(index, 100 * level).map((part) => part.toFixed(1)).join(",")).join(" ");
  return `<div class="season-command-panel season-radar-card">
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(title)} league rank profile">
      ${[0.25, 0.5, 0.75, 1].map((level) => `<polygon class="season-radar-grid" points="${ring(level)}"></polygon>`).join("")}
      ${axes.map((_axis, index) => { const [x, y] = point(index, 99); return `<line class="season-radar-axis" x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"></line>`; }).join("")}
      <polygon class="season-radar-rank" points="${polygon(current)}"></polygon>
      ${axes.map(([label, rankKey], index) => {
        const [px, y] = point(index, 100, 34);
        const x = Math.abs(px - cx) < 5 ? cx : px < cx ? 66 : width - 66;
        const rank = Number(ranks[rankKey] || count);
        return `<text x="${x.toFixed(1)}" y="${(y - 6).toFixed(1)}" text-anchor="middle"><tspan x="${x.toFixed(1)}">${escapeHtml(label)}</tspan><tspan x="${x.toFixed(1)}" dy="16">#${rank}/${count}</tspan></text>`;
      }).join("")}
    </svg>
  </div>`;
}

function seasonRadarRankScore(rank, count) {
  const leagueSize = Math.max(1, Number(count) || 30);
  const position = clampNumber(Number(rank) || leagueSize, 1, leagueSize);
  return ((leagueSize - position + 0.5) / leagueSize) * 100;
}

function seasonStandingsCard(viewedTeam, expanded = false) {
  const standings = standingsRows(state.data.dashboardStandings);
  const viewedRow = standings.find((row) => teamLabel(row.team) === viewedTeam);
  const conference = viewedRow?.team?.conference || "East";
  const conferences = expanded ? ["West", "East"] : [conference];
  const tableMarkup = (rows, isExpanded) => {
    const leader = rows[0] || {};
    const items = rows.map((row, index) => {
      const team = teamLabel(row.team);
      const logo = teamLogoSrc(team);
      const gamesBack = ((Number(leader.wins || 0) - Number(row.wins || 0)) + (Number(row.losses || 0) - Number(leader.losses || 0))) / 2;
      const gamesBackLabel = gamesBack <= 0 ? "—" : Number.isInteger(gamesBack) ? String(gamesBack) : gamesBack.toFixed(1).replace(/^0/, "");
      return `<button type="button" class="season-standing-row${team === viewedTeam ? " active" : ""}${index === 5 ? " playoff-line" : ""}${index === 9 ? " play-in-line" : ""}" data-dashboard-team-jump="${escapeAttr(team)}">
        <span>${index + 1}</span><span class="season-standing-team-cell" data-standing-team-id="${escapeAttr(row.team?.id || row.team_id || "")}">${logo ? `<img src="${escapeAttr(logo)}" alt="" />` : ""}<span class="season-standing-team-name">${escapeHtml(team)}</span><i class="season-row-motion" aria-hidden="true" hidden></i></span><span>${Number(row.wins || 0)}-${Number(row.losses || 0)}</span><span>${escapeHtml(winPct(row.win_pct))}</span><span>${escapeHtml(gamesBackLabel)}</span>
      </button>`;
    }).join("");
    return `<div class="season-standings-table${isExpanded ? " season-standings-table-expanded" : ""}"${isExpanded ? ` style="--standings-count:${Math.max(1, rows.length)}"` : ""}>
      <div class="season-standings-head"><span>#</span><span>Team</span><span>W-L</span><span>Win%</span><span>GB</span></div>
      ${items || `<div class="empty">No standings yet.</div>`}
    </div>`;
  };
  if (!expanded) return tableMarkup(standings.filter((row) => row.team?.conference === conference).slice(0, 10), false);
  return `<div class="season-standings-expanded">${conferences.map((name) => {
    const rows = standings.filter((row) => row.team?.conference === name).slice(0, 15);
    return `<section class="season-standings-conference"><h3>${name === "East" ? "Eastern" : "Western"} Conference</h3>${tableMarkup(rows, true)}</section>`;
  }).join("")}</div>`;
}

function setStandingsCardExpanded(expanded, card) {
  const panel = card || els.content.querySelector(".season-standings-panel");
  if (!panel) return false;
  const viewedTeam = teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam());
  panel.classList.toggle("is-expanded", Boolean(expanded));
  panel.innerHTML = seasonStandingsCard(viewedTeam, Boolean(expanded));
  wireDashboardTeamJumps(panel);
  return true;
}

function seasonWeekCard(dash, viewedTeam) {
  const currentText = String(state.home?.save?.current_date || "").slice(0, 10);
  const {from_date} = dashboardWeekRange(currentText);
  const monday = new Date(`${from_date}T00:00:00Z`);
  const calendarGames = (state.data.dashboardCalendar?.games || state.data.dashboardCalendar?.calendar || []).filter((game) => {
    const home = seasonGameTeamLabel(game, "home");
    const away = seasonGameTeamLabel(game, "away");
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
    return `<div class="season-week-day${iso === currentText ? " today" : ""}${iso === tradeDeadlineDate() ? " trade-deadline-day" : ""}">
      <span>${date.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })} ${date.getUTCDate()}</span>
      ${game?.__completed && (game.game_id || game.id) ? `<button type="button" class="season-week-node" data-box-score="${escapeAttr(game.game_id || game.id)}" aria-label="Box score: ${escapeAttr(opponent)} ${escapeAttr(iso)}"><img src="${escapeAttr(logo)}" alt="${escapeAttr(opponent)}" /></button>` : `<div class="season-week-node">${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(opponent)}" />` : "<i></i>"}</div>`}
      ${score ? `<em>${escapeHtml(score)}</em>` : `<em aria-hidden="true"></em>`}
      ${iso === tradeDeadlineDate() ? `<small class="trade-deadline-day-label">Trade deadline${iso === currentText ? " · Today" : ""}</small>` : iso === currentText ? `<small>Today</small>` : `<small aria-hidden="true"></small>`}
    </div>`;
  }).join("");
  return `<div class="season-week-days" aria-label="This week">${days}</div>`;
}

function wireWeekCardBoxScores(panel) {
  panel?.querySelectorAll("[data-box-score]").forEach((button) => {
    if (button.dataset.weekBoxScoreWired) return;
    button.dataset.weekBoxScoreWired = "true";
    button.addEventListener("click", () => openBoxScore(button.dataset.boxScore));
  });
}

async function setWeekCardExpanded(expanded, card) {
  const panel = card || els.content.querySelector(".season-week-panel");
  if (!panel) return false;
  const dash = state.data.dashboard || {};
  const viewedTeam = teamLabel(dash.team || state.dashboardTeam || userTeam());
  panel.classList.toggle("is-expanded", Boolean(expanded));
  if (expanded) {
    const month = state.calendarMonth || String(state.home?.save?.current_date || "").slice(0, 7);
    const monthStart = `${month}-01`;
    const monthEnd = monthEndDate(monthStart);
    const calendar = state.data.dashboardCalendar || {};
    if (month && (!calendar.from_date || !calendar.through_date || calendar.from_date > monthStart || calendar.through_date < monthEnd)) {
      try {
        await loadDashboardCalendar(viewedTeam);
      } catch (error) {
        showToast(error.message || String(error), true);
      }
    }
    if (!panel.isConnected || !panel.classList.contains("is-expanded")) return false;
    renderCalendar(panel, {team:viewedTeam,dataKey:"dashboardCalendar"});
    GameInterface.enhance(panel);
  } else {
    panel.innerHTML = seasonWeekCard(dash, viewedTeam);
    wireWeekCardBoxScores(panel);
  }
  return true;
}

function seasonGameOpponent(game, team) {
  if (game.opponent_team_id) {
    const opponent = state.teams.find((row) => String(row.id || row.team_id || "") === String(game.opponent_team_id));
    return teamLabel(opponent || game.opponent_team_id);
  }
  const home = seasonGameTeamLabel(game, "home");
  const away = seasonGameTeamLabel(game, "away");
  return home === team ? away : home;
}

function seasonGameTeamLabel(game, side) {
  const candidate = game?.[`${side}_team`] ?? game?.[side] ?? game?.[`${side}_team_id`];
  if (!candidate) return "";
  const id = typeof candidate === "object" ? candidate.id || candidate.team_id : candidate;
  const resolved = state.teams.find((team) => String(team.id || team.team_id || "") === String(id || ""));
  return teamLabel(resolved || candidate);
}

function seasonGameScore(game, team) {
  const result = String(game.result || resultForTeam(game, team) || "").toUpperCase();
  const teamPoints = Number(game.points ?? game.team_points);
  const opponentPoints = Number(game.opponent_points);
  if (Number.isFinite(teamPoints) && Number.isFinite(opponentPoints)) return `${result || (teamPoints > opponentPoints ? "W" : "L")} ${teamPoints}–${opponentPoints}`;
  const home = seasonGameTeamLabel(game, "home");
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
  if (!game.game_id && !game.opponent_team_id && !opponent.team) {
    // No next game: season over, eliminated, or (mid-sim) not yet known.
    const message = opponent.pending ? "Waiting for the next game on the schedule." : "No upcoming game on the schedule.";
    return `<header class="season-panel-header season-opponent-header"><div class="season-opponent-title"><span>Next Opponent</span></div></header>
    <div class="season-opponent-table" role="table" aria-label="Next Opponent rotation"><div class="empty">${message}</div></div>`;
  }
  const opponentTeam = teamLabel(opponent.team || game.opponent_team_id || seasonGameOpponent(game, viewedTeam));
  const record = opponent.record || {};
  const games = Number(record.wins || 0) + Number(record.losses || 0);
  const lastTen = (opponent.last_games || []).slice(0, 10);
  const lastTenWins = lastTen.filter((item) => String(item.result || "").toUpperCase() === "W").length;
  const identity = opponent.team_identity || {};
  const rankings = identity.ranks || {};
  const selectedLeaders = [...(opponent.rotation || [])]
    .sort((left, right) => Number(right.minutes_projection || 0) - Number(left.minutes_projection || 0))
    .slice(0, 6);
  const leaders = seasonOpponentOrderedRows(selectedLeaders, state.dashboardOpponentSort);
  const logo = teamLogoSrc(opponentTeam);
  const homeAway = game.is_home === true ? "Home" : game.is_home === false ? "Away" : "";
  const injuries = (opponent.rotation || [])
    .filter((row) => isPlayerInjured(row.health))
    .map((row) => {
      const remaining = injuryGamesRemaining(row);
      const fallback = String(row.health?.label || row.health?.status || "out")
        .replace(/\binjured\b/ig, "")
        .replace(/~\s*(\d+)\s*g\b/ig, "$1 G")
        .replace(/^\s*[—–·-]+|[—–·-]+\s*$/g, "")
        .trim();
      return [row.name || "Unknown", remaining === null ? fallback : `${remaining} G`].filter(Boolean).join(" — ");
    });
  const headerRatings = [
    ["OVR", rankings.overall], ["OFF", rankings.offense], ["DEF", rankings.defense],
  ];
  return `<header class="season-panel-header season-opponent-header">
      <div class="season-opponent-title">${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(opponentTeam)} logo" />` : ""}<span>${escapeHtml(opponentTeam || "—")}</span><span>${Number(record.wins || 0)}-${Number(record.losses || 0)}</span>${opponent.pending ? "" : `<span>L10 ${lastTenWins}-${Math.max(0, lastTen.length - lastTenWins)}</span>${headerRatings.map(([label, rank]) => {
        const score = clampNumber(((30 - Number(rank || 30) + 1) / 30) * 100, 3, 100);
        return `<span class="season-opponent-header-rating">#${Number(rank || 30)} ${label}<i><b style="${performanceBarStyle(score)}"></b></i></span>`;
      }).join("")}`}</div>
      <span class="season-opponent-date">${escapeHtml(formatDashboardShortDate(game.date) || game.date || "")}${homeAway ? ` · ${homeAway}` : ""}</span>
    </header>
    <div class="season-opponent-table" role="table" aria-label="Next Opponent rotation">
      <span class="season-opponent-sort-band" aria-hidden="true"></span>
      <div class="season-opponent-head" role="row">${[
        ["player", "Player"], ["overall", "OVR"], ["offense", "OFF"], ["defense", "DEF"],
        ["points", "PTS"], ["rebounds", "REB"], ["assists", "AST"],
      ].map(([key, label]) => seasonOpponentSortHeader(key, label)).join("")}</div>
      ${leaders.map(({ row, originalIndex }, displayIndex) => {
        const playerName = row.name || "Unknown";
        const playerMarkup = playerNameWithInjuryMarkup(row, `${displayIndex + 1}. ${playerName}`)
          .replace('class="player-name-text"', 'class="player-name-text" data-opponent-player-text');
        return `<div class="season-opponent-row${isPlayerInjured(row.health) ? " injured" : ""}" role="row" data-opponent-index="${originalIndex}"${seasonOpponentSortData(row)}><span class="season-opponent-player-cell" role="rowheader" data-opponent-column="player"><button type="button" class="season-opponent-player-link" data-dashboard-player-card="${escapeAttr(row.id || row.player_id || "")}" aria-label="Open ${escapeAttr(playerName)} player card">${playerMarkup}</button></span>${seasonOpponentRatingCell(rating(row, "overall"), "overall")}${seasonOpponentRatingCell(rating(row, "offense"), "offense")}${seasonOpponentRatingCell(rating(row, "defense"), "defense")}${["points", "rebounds", "assists"].map((key) => `<span role="cell" data-opponent-column="${key}">${escapeHtml(statNumber(row, key))}</span>`).join("")}</div>`;
      }).join("") || `<div class="empty">${opponent.pending ? "Rotation updates as the sim reaches this game." : "Opponent rotation unavailable."}</div>`}
    </div>
    <div class="season-opponent-injuries"><span>Current injuries:</span><div class="season-opponent-injury-ticker" data-injury-ticker title="${escapeAttr(injuries.join(" · ") || (opponent.pending ? "—" : "No active injuries"))}"><div class="season-opponent-injury-track"><span data-injury-ticker-text>${escapeHtml(injuries.join(" · ") || (opponent.pending ? "—" : "No active injuries"))}</span><span data-injury-ticker-copy aria-hidden="true"></span></div></div></div>`;
}

const SEASON_OPPONENT_SORT_KEYS = new Set(["player", "overall", "offense", "defense", "points", "rebounds", "assists"]);

function seasonOpponentSortHeader(key, label) {
  const active = state.dashboardOpponentSort?.key === key;
  const direction = active ? state.dashboardOpponentSort.direction : "none";
  return `<span role="columnheader" aria-sort="${direction}" data-opponent-column="${key}"${active ? " data-opponent-sorted" : ""}><button type="button" class="season-opponent-sort-button" data-opponent-sort="${key}">${label}</button></span>`;
}

function seasonOpponentRatingCell(value, key) {
  const score = clampNumber(Number(value || 0), 0, 99);
  return `<span class="season-mini-rating" role="cell" data-opponent-column="${key}"><em>${score.toFixed(0)}</em><i><b style="${performanceBarStyle(score)}"></b></i></span>`;
}

function seasonOpponentSortData(row) {
  const displayedRating = (key) => {
    const score = clampNumber(Number(rating(row, key) || 0), 0, 99);
    return score.toFixed(0);
  };
  const attributes = {
    player: row.name || "Unknown",
    overall: displayedRating("overall"),
    offense: displayedRating("offense"),
    defense: displayedRating("defense"),
    points: statNumber(row, "points"),
    rebounds: statNumber(row, "rebounds"),
    assists: statNumber(row, "assists"),
  };
  return Object.entries(attributes).map(([key, value]) => ` data-sort-${key}="${escapeAttr(value)}"`).join("");
}

function seasonOpponentOrderedRows(rows, sortState) {
  const stateToUse = SEASON_OPPONENT_SORT_KEYS.has(sortState?.key) && ["asc", "desc"].includes(sortState?.direction)
    ? sortState
    : { key: "overall", direction: "desc" };
  return rows.map((row, originalIndex) => ({ row, originalIndex })).sort((left, right) => {
    const leftValue = seasonOpponentSortValue(left.row, stateToUse.key);
    const rightValue = seasonOpponentSortValue(right.row, stateToUse.key);
    if (leftValue.missing !== rightValue.missing) return leftValue.missing ? 1 : -1;
    let comparison = 0;
    if (leftValue.missing) return left.originalIndex - right.originalIndex;
    if (leftValue.numeric && rightValue.numeric) {
      comparison = leftValue.value - rightValue.value;
    } else {
      comparison = leftValue.value < rightValue.value ? -1 : leftValue.value > rightValue.value ? 1 : 0;
    }
    if (comparison && stateToUse.direction === "desc") comparison *= -1;
    return comparison || left.originalIndex - right.originalIndex;
  });
}

function seasonOpponentSortValue(row, key) {
  if (key === "player") {
    const name = String(row.name || "Unknown").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    return { value: name, numeric: false, missing: !name };
  }
  const raw = key === "overall" ? rating(row, "overall")
    : key === "offense" ? rating(row, "offense")
      : key === "defense" ? rating(row, "defense")
        : statNumber(row, key);
  if (key === "overall" || key === "offense" || key === "defense") {
    return { value: Number(clampNumber(Number(raw || 0), 0, 99).toFixed(0)), numeric: true, missing: false };
  }
  const number = Number(raw);
  return { value: number, numeric: true, missing: raw === "" || !Number.isFinite(number) };
}

function seasonOpponentSortValueFromRow(row, key) {
  if (key === "player") {
    const name = String(row.dataset.sortPlayer || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    return { value: name, numeric: false, missing: !name };
  }
  const raw = row.dataset[`sort${key[0].toUpperCase()}${key.slice(1)}`] || "";
  const number = Number(raw);
  return { value: number, numeric: true, missing: raw === "" || !Number.isFinite(number) };
}

function applySeasonOpponentSort(panel) {
  const table = panel.querySelector(".season-opponent-table");
  if (!table) return;
  const sortState = state.dashboardOpponentSort;
  const headerCells = [...table.querySelectorAll(".season-opponent-head [role='columnheader']")];
  headerCells.forEach((cell) => {
    const active = cell.dataset.opponentColumn === sortState.key;
    cell.toggleAttribute("data-opponent-sorted", active);
    cell.setAttribute("aria-sort", active ? (sortState.direction === "desc" ? "descending" : "ascending") : "none");
  });
  table.querySelectorAll("[data-opponent-column]").forEach((cell) => {
    cell.toggleAttribute("data-opponent-sorted", cell.dataset.opponentColumn === sortState.key);
  });
  const rows = [...table.querySelectorAll(":scope > .season-opponent-row")];
  rows.sort((left, right) => {
    const leftValue = seasonOpponentSortValueFromRow(left, sortState.key);
    const rightValue = seasonOpponentSortValueFromRow(right, sortState.key);
    if (leftValue.missing !== rightValue.missing) return leftValue.missing ? 1 : -1;
    let comparison = 0;
    if (leftValue.missing) return Number(left.dataset.opponentIndex) - Number(right.dataset.opponentIndex);
    if (leftValue.numeric && rightValue.numeric) {
      comparison = leftValue.value - rightValue.value;
    } else {
      comparison = leftValue.value < rightValue.value ? -1 : leftValue.value > rightValue.value ? 1 : 0;
    }
    if (comparison && sortState.direction === "desc") comparison *= -1;
    return comparison || Number(left.dataset.opponentIndex) - Number(right.dataset.opponentIndex);
  });
  table.append(...rows);
  rows.forEach((row, index) => {
    const playerLabel = row.querySelector("[data-opponent-player-text]");
    if (playerLabel) playerLabel.textContent = `${index + 1}. ${row.dataset.sortPlayer || "Unknown"}`;
  });
  updateSeasonOpponentSortBand(table);
}

function updateSeasonOpponentSortBand(table) {
  const band = table.querySelector(":scope > .season-opponent-sort-band");
  const header = table.querySelector(":scope > .season-opponent-head");
  const activeCell = header?.querySelector(":scope > [data-opponent-sorted]");
  const firstRow = table.querySelector(":scope > .season-opponent-row");
  const lastRow = table.querySelector(":scope > .season-opponent-row:last-of-type");
  if (!band || !header || !activeCell || !firstRow || !lastRow) {
    if (band) band.hidden = true;
    return;
  }

  const tableRect = table.getBoundingClientRect();
  const activeRect = activeCell.getBoundingClientRect();
  const sectionHeader = table.previousElementSibling;
  const sectionHeaderRect = sectionHeader?.getBoundingClientRect();
  const lastRowRect = lastRow.getBoundingClientRect();
  const scaleX = table.offsetWidth > 0 ? tableRect.width / table.offsetWidth : 1;
  const scaleY = table.offsetHeight > 0 ? tableRect.height / table.offsetHeight : 1;
  const bandTop = sectionHeaderRect ? sectionHeaderRect.bottom : tableRect.top;
  const bandBottom = lastRowRect.bottom;
  band.style.left = `${(activeRect.left - tableRect.left) / scaleX}px`;
  band.style.top = `${(bandTop - tableRect.top) / scaleY}px`;
  band.style.width = `${activeRect.width / scaleX}px`;
  band.style.height = `${(bandBottom - bandTop) / scaleY}px`;
  band.hidden = false;
}

const seasonOpponentSortBandResizeObservers = new WeakMap();

function wireSeasonOpponentSorting(root = document) {
  root.querySelectorAll(".season-opponent-panel").forEach((panel) => {
    if (!seasonOpponentSortBandResizeObservers.has(panel) && typeof ResizeObserver === "function") {
      const observer = new ResizeObserver(() => updateSeasonOpponentSortBand(panel.querySelector(".season-opponent-table")));
      observer.observe(panel);
      seasonOpponentSortBandResizeObservers.set(panel, observer);
    }
    panel.querySelectorAll("[data-opponent-sort]").forEach((button) => {
      if (button.dataset.opponentSortWired) return;
      button.dataset.opponentSortWired = "true";
      button.addEventListener("click", () => {
        const key = button.dataset.opponentSort;
        if (!SEASON_OPPONENT_SORT_KEYS.has(key)) return;
        const current = state.dashboardOpponentSort;
        state.dashboardOpponentSort = current.key === key
          ? { key, direction: current.direction === "desc" ? "asc" : "desc" }
          : { key, direction: key === "player" ? "asc" : "desc" };
        applySeasonOpponentSort(panel);
      });
    });
    applySeasonOpponentSort(panel);
  });
}

const seasonOpponentInjuryTickerObservers = new WeakMap();

function wireSeasonOpponentInjuryTicker(root = document) {
  root.querySelectorAll("[data-injury-ticker]").forEach((ticker) => {
    const text = ticker.querySelector("[data-injury-ticker-text]");
    const copy = ticker.querySelector("[data-injury-ticker-copy]");
    const track = ticker.querySelector(".season-opponent-injury-track");
    if (!text || !copy || !track) return;
    const measure = () => {
      if (!ticker.isConnected || ticker.clientWidth < 1) return;
      ticker.classList.remove("is-overflowing");
      copy.textContent = "";
      const padding = Number.parseFloat(getComputedStyle(text).paddingRight) || 0;
      const textWidth = Math.max(0, text.getBoundingClientRect().width - padding);
      if (textWidth <= ticker.clientWidth + 1) {
        track.style.removeProperty("--season-injury-ticker-duration");
        return;
      }
      copy.textContent = text.textContent;
      const loopWidth = Math.max(1, text.getBoundingClientRect().width);
      track.style.setProperty("--season-injury-ticker-duration", `${Math.max(12, loopWidth / 24)}s`);
      ticker.classList.add("is-overflowing");
    };
    let observer = seasonOpponentInjuryTickerObservers.get(ticker);
    if (!observer && typeof ResizeObserver === "function") {
      observer = new ResizeObserver(measure);
      observer.observe(ticker);
      seasonOpponentInjuryTickerObservers.set(ticker, observer);
    }
    measure();
  });
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
  const left = 28, right = chartWidth - 7, top = 7, bottom = chartHeight - 42;
  const plotWidth = right - left, plotHeight = bottom - top;
  const zeroY = top + plotHeight / 2;
  const firstDate = Date.parse(`${source[0]?.date || ""}T00:00:00Z`);
  const weekMs = 7 * 86400000;
  const lastDate = Date.parse(`${source.at(-1)?.date || ""}T00:00:00Z`);
  const seasonSlots = Math.max(26, source.length, Number.isFinite(lastDate - firstDate) ? (lastDate - firstDate) / weekMs + 1 : 0);
  const xFor = (index) => {
    const day = Date.parse(`${source[index]?.date || ""}T00:00:00Z`);
    const slot = Number.isFinite(firstDate) && Number.isFinite(day) ? (day - firstDate) / weekMs : index;
    return left + slot / (seasonSlots - 1) * plotWidth;
  };
  const events = state.data.dashboardTrends?.efficiency?.events || [];
  const eventMarks = events.map((event, index) => {
    const day = Date.parse(`${event.date}T00:00:00Z`);
    const x = left + (day - firstDate) / weekMs / (seasonSlots - 1) * plotWidth;
    if (!Number.isFinite(x) || x < left || x > right) return "";
    return `<g class="efficiency-event ${escapeAttr(event.color)}" data-efficiency-event="${index}" tabindex="0" role="button" aria-label="${escapeAttr(`${event.date}: ${event.title}`)}"><title>${escapeHtml(`${event.date}: ${event.title}`)}</title><line class="efficiency-event-line" x1="${x}" x2="${x}" y1="${top}" y2="${bottom}"/><line class="efficiency-event-hit" x1="${x}" x2="${x}" y1="${top}" y2="${bottom}"/><circle cx="${x}" cy="${top + 3}" r="3"/></g>`;
  }).join("");
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
  const seasonMean = (series) => {
    const weights = source.map(point => Number(point.possessions || point.games || 1));
    const total = weights.reduce((sum, weight) => sum + weight, 0);
    return total ? series.reduce((sum, value, index) => sum + value * weights[index], 0) / total : 0;
  };
  const offenseTone = tone(seasonMean(offenseDiff));
  const defenseTone = tone(seasonMean(defenseDiff));
  const netTone = tone(seasonMean(net));
  const gridRows = Math.max(2, 2 * Math.round(plotHeight / (plotWidth / (seasonSlots - 1) / 2) / 2));
  const labelStep = Math.max(1, Math.ceil(12 / (plotHeight / gridRows)));
  const chart = `
    <svg class="season-efficiency-chart" viewBox="0 0 ${chartWidth} ${chartHeight}" preserveAspectRatio="none" aria-label="Weekly offensive and defensive rating">
      ${Array.from({length: seasonSlots}, (_unused, index) => `<line class="grid vertical" x1="${xFor(index)}" y1="${top}" x2="${xFor(index)}" y2="${bottom}"></line><line class="axis-notch" x1="${xFor(index)}" y1="${bottom}" x2="${xFor(index)}" y2="${bottom + 3}"></line>${source[index] ? `<text class="axis-label x-label" transform="translate(${xFor(index)},${bottom + 8}) rotate(-60)">${escapeHtml(source[index].label || `W${index + 1}`)}</text>` : ""}`).join("")}
      ${Array.from({length: gridRows + 1}, (_unused, index) => { const y = top + index / gridRows * plotHeight; const value = maximum - index / gridRows * maximum * 2; const labeled = index === 0 || index === gridRows || (index >= labelStep && index <= gridRows - labelStep && (index - gridRows / 2) % labelStep === 0); return `<line class="grid horizontal" x1="${left}" y1="${y}" x2="${right}" y2="${y}"></line>${labeled ? `<line class="axis-notch" x1="${left - 3}" y1="${y}" x2="${left}" y2="${y}"></line><text class="axis-label" x="${left - 5}" y="${y}">${value.toFixed(0)}</text>` : ""}`; }).join("")}
      <line class="zero" x1="${left}" y1="${zeroY}" x2="${right}" y2="${zeroY}"></line>
      <path class="net-area ${netTone}" d="${areaPath(net)}"></path>
      <polyline class="offense secondary ${offenseTone}" points="${chartPoints(offenseDiff)}"></polyline>
      <polyline class="defense secondary ${defenseTone}" points="${chartPoints(defenseDiff)}"></polyline>
      <polyline class="net ${netTone}" points="${chartPoints(net)}"></polyline>
      ${[offenseDiff, defenseDiff, net].map((series, seriesIndex) => series.map((value, index) => `<circle class="chart-node ${[offenseTone, defenseTone, netTone][seriesIndex]}" cx="${xFor(index)}" cy="${yFor(value)}" r="1.8"><title>${escapeHtml(source[index]?.label || `W${index + 1}`)} ${["OFF vs league", "DEF vs league", "NET"][seriesIndex]}: ${signedNumber(value)}</title></circle>`).join("")).join("")}
      ${eventMarks}
    </svg>`;
  return chartOnly ? chart : `${seasonPanelHeader("Weekly Efficiency")}<div class="season-efficiency-plot">${chart}</div><div class="season-efficiency-legend" role="group" aria-label="Latest weekly efficiency"><span class="${offenseTone}"><i class="offense" aria-hidden="true"></i><span class="legend-label">OFF</span><strong>${latestOffense.toFixed(1)}</strong></span><span class="${defenseTone}"><i class="defense" aria-hidden="true"></i><span class="legend-label">DEF</span><strong>${latestDefense.toFixed(1)}</strong></span><span class="${netTone}"><i class="net" aria-hidden="true"></i><span class="legend-label">NET</span><strong>${latestNet.toFixed(1)}</strong></span></div>`;
}

function efficiencyEventDetail(event) {
  const heading = `<strong>${escapeHtml(event.title)}</strong><small>${escapeHtml(event.date)}</small>`;
  if (event.coaches) return heading + event.coaches.map(coach => `<div class="efficiency-event-coach"><span>${escapeHtml(coach.label)} · ${escapeHtml(coach.role)}</span><b>${escapeHtml(coach.name)}</b>${compactRatingBar(coach.grade)}</div>`).join("");
  const risk = event.injury_body ? `<div class="injury-event-body">${injuryRiskBody(event.health_risk, event.injury_body, event.risk_label || "Health risk")}<small>${escapeHtml(event.risk_label || "Health risk")}</small></div>`
    : event.health_risk == null ? '<p>Health risk unavailable</p>' : playerEvidenceRing(event.risk_label || "Health risk", Number(event.health_risk), 10, "#b34d49", "/10");
  return heading + `<p>${escapeHtml(event.body_area)} · Expected absence: ${event.expected_games_missed == null ? "unknown" : escapeHtml(event.expected_games_missed) + (Number(event.expected_games_missed) === 1 ? " game" : " games")}</p>${risk}<p>${Number(event.minutes_lost || 0).toFixed(1)} minutes per night lost</p><small>${escapeHtml(event.distribution_note)}</small>${(event.distribution || []).map(row => `<div class="efficiency-event-minute"><span>${escapeHtml(row.name)}</span><b>+${Number(row.minutes).toFixed(1)} min</b></div>`).join("")}`;
}

let seasonEfficiencyResizeObserver;
function wireSeasonEfficiencyChart() {
  seasonEfficiencyResizeObserver?.disconnect();
  const plot = els.content.querySelector(".season-efficiency-plot");
  if (!plot) return;
  let popup = document.getElementById("efficiencyEventDetail");
  if (!popup) {
    popup = document.createElement("div");
    popup.id = "efficiencyEventDetail";
    popup.className = "efficiency-event-detail";
    popup.setAttribute("role", "tooltip");
    document.body.append(popup);
    document.addEventListener("pointerdown", (event) => { if (!event.target.closest("[data-efficiency-event]")) popup.hidden = true; });
  }
  popup.hidden = true;
  let pinnedEvent = false;
  const show = (target) => {
    const event = state.data.dashboardTrends?.efficiency?.events?.[Number(target.dataset.efficiencyEvent)];
    if (!event) return;
    popup.innerHTML = efficiencyEventDetail(event);
    popup.hidden = false;
    const bounds = target.getBoundingClientRect();
    popup.style.left = `${Math.max(8, Math.min(window.innerWidth - popup.offsetWidth - 8, bounds.right + 10))}px`;
    popup.style.top = `${Math.max(8, Math.min(window.innerHeight - popup.offsetHeight - 8, bounds.top + 8))}px`;
  };
  plot.onpointerover = (event) => { const target = event.target.closest("[data-efficiency-event]"); if (target && !pinnedEvent) show(target); };
  plot.onpointerout = (event) => { if (!pinnedEvent && event.target.closest("[data-efficiency-event]") && !event.relatedTarget?.closest?.("[data-efficiency-event]")) popup.hidden = true; };
  plot.onfocusin = (event) => { const target = event.target.closest("[data-efficiency-event]"); if (target) show(target); };
  plot.onfocusout = () => { popup.hidden = true; pinnedEvent = false; };
  plot.onclick = (event) => { const target = event.target.closest("[data-efficiency-event]"); if (target) { show(target); pinnedEvent = true; } };
  plot.onkeydown = (event) => { if (event.key === "Escape") { popup.hidden = true; pinnedEvent = false; } if (["Enter", " "].includes(event.key)) { const target = event.target.closest("[data-efficiency-event]"); if (target) { event.preventDefault(); show(target); } } };
  let lastSize = "";
  const redraw = () => {
    const width = plot.clientWidth, height = plot.clientHeight;
    const size = `${width},${height}`;
    if (width <= 40 || height <= 40 || size === lastSize) return;
    lastSize = size;
    popup.hidden = true;
    pinnedEvent = false;
    plot.innerHTML = seasonEfficiencyCard(state.data.dashboard || {}, width, height, true);
  };
  seasonEfficiencyResizeObserver = new ResizeObserver(redraw);
  seasonEfficiencyResizeObserver.observe(plot);
  redraw();
}

const PROSPECT_COLLEGE_LOGOS = Object.freeze({
  alabama:"alabama", arizona:"arizona", arkansas:"arkansas", auburn:"auburn", baylor:"baylor", byu:"byu",
  cincinnati:"cincinnati", creighton:"creighton", duke:"duke", florida:"florida", "florida-state":"florida-state",
  gonzaga:"gonzaga", houston:"houston", illinois:"illinois", indiana:"indiana", iowa:"iowa", "iowa-state":"iowa-state",
  kansas:"kansas", kentucky:"kentucky", louisville:"louisville", marquette:"marquette", memphis:"memphis", michigan:"michigan",
  "michigan-state":"michigan-state", "north-carolina":"north-carolina", northwestern:"northwestern", "ohio-state":"ohio-state",
  oregon:"oregon", purdue:"purdue", "san-diego-state":"san-diego-state", "santa-clara":"santa-clara", "south-florida":"south-florida",
  "st-johns":"st-johns", stanford:"stanford", tennessee:"tennessee", texas:"texas", "texas-tech":"texas-tech", uconn:"uconn",
  usc:"usc", ucla:"ucla", vanderbilt:"vanderbilt", villanova:"villanova", virginia:"virginia", washington:"washington",
});
const PROSPECT_COUNTRY_FLAGS = Object.freeze({
  australia:"AU", brazil:"BR", canada:"CA", china:"CN", croatia:"HR", france:"FR", germany:"DE", greece:"GR",
  italy:"IT", japan:"JP", latvia:"LV", lithuania:"LT", nigeria:"NG", "new-zealand":"NZ", "south-sudan":"SS",
  serbia:"RS", slovenia:"SI", spain:"ES", turkey:"TR", "united-states":"US", usa:"US", "g-league":"US", "overtime-elite":"US",
});
const PROSPECT_CLUB_COUNTRIES = Object.freeze({
  "kk-mega-basket":"RS", valencia:"ES", "real-madrid":"ES", barcelona:"ES", "fc-barcelona":"ES", "ratiopharm-ulm":"DE",
  "partizan-belgrade":"RS", "crvena-zvezda":"RS", "red-star-belgrade":"RS", "olympiacos":"GR", "panathinaikos":"GR",
});

function prospectOriginKey(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/['’]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function prospectFlagEmoji(countryCode) {
  return String.fromCodePoint(...Array.from(countryCode.toUpperCase(), (letter) => letter.charCodeAt(0) + 127397));
}

function prospectOriginMarkup(origin) {
  const label = String(origin || "").trim() || "Source unavailable";
  const key = prospectOriginKey(label);
  const countryCode = PROSPECT_COUNTRY_FLAGS[key] || PROSPECT_CLUB_COUNTRIES[key];
  if (countryCode) {
    return `<span class="season-prospect-origin season-prospect-flag" role="img" aria-label="${escapeAttr(`${label} flag`)}" title="${escapeAttr(label)}">${escapeHtml(prospectFlagEmoji(countryCode))}</span>`;
  }
  const collegeLogo = PROSPECT_COLLEGE_LOGOS[key];
  if (collegeLogo) {
    return `<img class="season-prospect-origin season-prospect-college-logo" src="/assets/team_logos/colleges/${escapeAttr(collegeLogo)}.png" alt="${escapeAttr(`${label} logo`)}" title="${escapeAttr(label)}" loading="lazy" decoding="async" />`;
  }
  const initials = label.split(/\s+/).filter(Boolean).map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "?";
  return `<span class="season-prospect-origin season-prospect-source-fallback" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">${escapeHtml(initials)}</span>`;
}

function seasonProspectsCard(options = {}) {
  const sort = state.dashboardProspectSort.key === "stock" ? {key:"rank", direction:"asc"} : state.dashboardProspectSort;
  const value = (row) => ({rank:Number(row.rank), name:row.name, position:row.position, age:Number(row.age), height:row.height, now:Number(row.now), range:row.draftRangeLow ?? Infinity, scouted:Number(row.scoutedPct ?? Number(row.confidence || 0) * 100)})[sort.key];
  const sourceRows = [...(options.rows || draftBoardRows(state.data.dashboardProspects || {}))];
  const sortedRows = sourceRows.sort((a, b) => {
    if (sort.key === "range" && (a.draftRangeLow == null || b.draftRangeLow == null)) {
      return Number(a.draftRangeLow == null) - Number(b.draftRangeLow == null) || Number(a.rank) - Number(b.rank);
    }
    const av = value(a), bv = value(b);
    return (typeof av === "string" ? av.localeCompare(String(bv)) : av - bv) * (sort.direction === "asc" ? 1 : -1)
      || (sort.key === "range" ? (Number(a.draftRangeHigh) - Number(b.draftRangeHigh)) * (sort.direction === "asc" ? 1 : -1) : 0)
      || Number(a.rank) - Number(b.rank);
  });
  const rows = options.expanded ? sortedRows : sortedRows.slice(0, 6);
  return `<div class="season-prospects-table${options.expanded ? " season-prospects-table-expanded" : ""}">
      <div class="season-prospects-head">${[["rank", "#"], ["name", "Prospect"], ["position", "Pos"], ["age", "Age"], ["height", "Height"], ["now", "Now/Pot"], ["range", "Range"], ["scouted", "Scouted"]].map(([key, label]) => `<button type="button" data-season-prospect-sort="${key}" aria-pressed="${sort.key === key}" title="${key === "range" ? "Sort by projected draft pick range" : `Sort by ${label}`}" aria-label="Sort by ${label}${sort.key === key ? `, ${sort.direction === "asc" ? "ascending" : "descending"}` : ""}">${label}${sort.key === key ? (sort.direction === "asc" ? " ↑" : " ↓") : ""}</button>`).join("")}</div>
      ${rows.map((row) => {
        const confidence = clampNumber(Number(row.scoutedPct ?? Number(row.confidence || 0) * 100), 0, 100);
        const hasRange = row.draftRangeLow != null && row.draftRangeHigh != null;
        const draftRange = hasRange ? `${row.draftRangeLow}–${row.draftRangeHigh}` : "—";
        const now = Number(row.now), potential = Number(row.potential);
        return `<button type="button" class="season-prospect-row" data-draft-prospect-card="${escapeAttr(row.id)}" title="Open scouting report for ${escapeAttr(row.name)}">
          <span class="season-prospect-rank">${String(row.rank).padStart(2, "0")}</span>
          <span class="season-prospect-name"><span class="season-prospect-name-main">${prospectOriginMarkup(row.sourceTeam)}<strong>${escapeHtml(row.name)}</strong>${prospectInjuryMarkup(row.injuryReport, { compact: true })}</span></span>
          <span class="season-prospect-position">${escapeHtml(row.position)}</span>
          <span>${escapeHtml(row.age ?? "—")}</span>
          <span>${escapeHtml(row.height || "—")}</span>
          <span class="season-prospect-nowpot"><strong>${Number.isFinite(now) ? now.toFixed(0) : "—"}</strong><i aria-hidden="true">→</i><b>${Number.isFinite(potential) ? potential.toFixed(0) : "—"}</b></span>
          <span class="season-prospect-range" title="${hasRange ? `Projected draft picks ${row.draftRangeLow} to ${row.draftRangeHigh}` : "Projected draft range unavailable"}">${draftRange}</span>
          <span class="season-scouted" aria-label="Scouted ${confidence.toFixed(0)} percent"><i><b style="${performanceBarStyle(confidence)}"></b></i><strong>${confidence.toFixed(0)}%</strong></span>
        </button>`;
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
      <header class="season-award-head"><h3>${label}</h3></header>
      <div class="season-award-rows">${leaders.slice(0, 4).map((row, index) => {
      const team = row.team_abbrev || teamLabel(row.team_id);
      const logo = teamLogoSrc(team);
      const portrait = row.headshot_url || logo;
      return `<button type="button" data-dashboard-player-card="${escapeAttr(row.player_id)}"><span class="award-player-rank">${row.rank || index + 1}</span>${portrait ? `<img class="${row.headshot_url ? "award-player-headshot" : "award-team-fallback"}" src="${escapeAttr(portrait)}" alt="" aria-hidden="true" loading="lazy" decoding="async" referrerpolicy="no-referrer" />` : ""}<strong>${escapeHtml(row.player_name)}</strong>${seasonRankChange(row.rank_change, row.previous_week_rank ?? row.season_start_rank)}</button>`;
      }).join("") || `<div class="empty">No candidates yet.</div>`}</div>
    </section>`).join("")}</div>`;
}

function seasonRankChange(change, previousRank) {
  if (change == null || !Number.isFinite(Number(change))) return `<span class="season-rank-change neutral" title="Previous week's rank unavailable">—</span>`;
  const delta = Number(change);
  const label = delta > 0 ? `Up ${delta}` : delta < 0 ? `Down ${Math.abs(delta)}` : "Unchanged";
  return `<span class="season-rank-change ${delta > 0 ? "positive" : delta < 0 ? "negative" : "neutral"}" title="${label} from previous week's rank ${previousRank}" aria-label="${label} places since the previous week">${delta > 0 ? "↑" : delta < 0 ? "↓" : ""} ${Math.abs(delta)}</span>`;
}

const COACH_PORTRAIT_IDS = Array.from({length:6}, (_, index) => `coach-${String(index + 1).padStart(2, "0")}`);

function staffIdentity(row, index = 0) {
  return String(row.id || row.slot || row.role || index);
}

function coachPortraitAssignments(rows) {
  const roles = ["Head Coach", "Offensive Coordinator", "Defensive Coordinator", "Performance Lead", "Development Lead", "Scouting Lead"];
  const ordered = [...rows].sort((a, b) => {
    const order = (row) => { const index = roles.indexOf(staffRoleLabel(row.slot || row.role)); return index < 0 ? roles.length : index; };
    return order(a) - order(b);
  });
  const used = new Set();
  return new Map(ordered.map((row, index) => {
    const identity = staffIdentity(row, index);
    const start = [...identity].reduce((hash, character) => ((hash * 31) + character.charCodeAt(0)) >>> 0, 7) % COACH_PORTRAIT_IDS.length;
    let portraitIndex = start;
    if (used.size === COACH_PORTRAIT_IDS.length) used.clear();
    while (used.has(portraitIndex)) portraitIndex = (portraitIndex + 1) % COACH_PORTRAIT_IDS.length;
    used.add(portraitIndex);
    return [identity, COACH_PORTRAIT_IDS[portraitIndex]];
  }));
}

function coachPortraitMarkup(portraitId, extraClass = "") {
  if (!COACH_PORTRAIT_IDS.includes(portraitId)) return "";
  const path = `/assets/game-art/coaches/${portraitId}`;
  return `<span class="coach-portrait-art ${escapeAttr(extraClass)}" aria-hidden="true"><img class="coach-portrait-silver" src="${path}-silver.webp" alt="" decoding="async" draggable="false"><img class="coach-portrait-ink" src="${path}-ink.webp" alt="" decoding="async" draggable="false"></span>`;
}

function staffActionPermission(slot, permissions = state.data.staff?.team_report?.staff_action_permissions || state.data.dashboard?.staff_action_permissions || {}) {
  return permissions[slot] || {};
}

function staffActionAttributes(slot, action, permissions) {
  const permission = staffActionPermission(slot, permissions);
  return permission[`can_${action}`] === false ? `disabled title="${escapeAttr(permission[`${action}_reason`] || "Available next season.")}"` : "";
}

function seasonStaffRowMarkup(row, portraitId, {actions = false, candidate = false, permissions} = {}) {
  const name = staffName(row);
  const role = staffRoleLabel(row.slot || row.role);
  const grade = Number(staffGrade(row) || 0);
  const salary = staffAav(row);
  const years = candidate ? row.asking_years || 2 : staffYears(row);
  const contract = `${salary ? money(salary) : "—"} x ${years || "—"}`;
  const personAction = candidate ? `data-staff-id="${escapeAttr(row.id)}"` : `data-dashboard-staff-card="${escapeAttr(staffIdentity(row))}"`;
  const actionAttributes = staffActionAttributes(row.slot || row.role, candidate ? "negotiate" : "fire", permissions);
  return `<div class="season-staff-row${candidate ? " season-staff-candidate-row" : ""}">
    <button type="button" class="season-staff-person" ${personAction} ${candidate && actionAttributes ? actionAttributes : `title="${escapeAttr(name)}"`} aria-label="${candidate ? "Negotiate with" : "Open coach card for"} ${escapeAttr(name)}">${coachPortraitMarkup(portraitId, "season-staff-portrait")}<span><strong title="${escapeAttr(name)}">${escapeHtml(name)}</strong><small title="${escapeAttr(role)}">${escapeHtml(role)}</small></span></button>
    <span class="season-staff-grade" aria-label="Grade ${grade.toFixed(0)}"><em>${grade.toFixed(0)}</em><i><b style="${performanceBarStyle(grade)}"></b></i></span>
    <span class="season-staff-contract"><strong>${escapeHtml(contract)}</strong></span>
    ${actions ? `<button type="button" class="season-staff-action" ${actionAttributes} ${candidate ? `data-staff-id="${escapeAttr(row.id)}"` : `data-fire-slot="${escapeAttr(row.slot || row.role)}"`}>${candidate ? "Negotiate" : "Fire"}</button>` : ""}
  </div>`;
}

function seasonStaffCard(dash, includeHeader = true, {actions = false, available = null} = {}) {
  const roles = ["Head Coach", "Offensive Coordinator", "Defensive Coordinator", "Performance Lead", "Development Lead", "Scouting Lead"];
  const rows = [...staffRows(dash)].sort((a, b) => {
    const order = (row) => { const index = roles.indexOf(staffRoleLabel(row.slot || row.role)); return index < 0 ? roles.length : index; };
    return order(a) - order(b);
  });
  const portraits = coachPortraitAssignments(rows);
  const payroll = staffBudgetSummary(rows, dash);
  const payrollLabel = payroll.max > 0 ? `${money(payroll.used)}/${money(payroll.max)}` : money(payroll.used);
  return `${includeHeader ? seasonPanelHeader("Coaching Staff") : ""}
    <div class="season-staff-summary" aria-label="Coaching staff overview">
      <span><strong>STAFF PAYROLL: ${escapeHtml(payrollLabel)}${available === null ? "" : ` · ${signedMoney(available)} available`}</strong></span>
    </div>
    <div class="season-staff-table">
      <div class="season-staff-head"><span>Staff Member</span><span>Grade</span><span>Contract</span>${actions ? '<span aria-hidden="true"></span>' : ""}</div>
      ${rows.map(row => seasonStaffRowMarkup(row, portraits.get(staffIdentity(row)), {actions, permissions:dash.staff_action_permissions})).join("") || `<div class="empty">No staff loaded.</div>`}
    </div>`;
}

function coachRatingRow(label, value, key, info = {}) {
  const average = info.averages?.[key];
  const display = value == null ? "—" : draftMetric(value);
  const description = info.descriptions?.[key] || "Impacts overall staff grade.";
  const difference = value == null || average == null ? null : Math.round((Number(value) - Number(average)) * 10) / 10;
  const comparison = difference == null ? "League average unavailable." : difference === 0
    ? "Equal to the league average for this role."
    : `${Math.abs(difference).toFixed(1)} rating points ${difference > 0 ? "above" : "below"} the league average for this role.`;
  const tooltip = `${label} — ${display} / 100\n${description}\n${comparison}${average == null ? "" : `\nLeague average: ${draftMetric(average)} · ${info.peer_count} active staff in this role.`}`;
  return `<div class="coach-trait-row" tabindex="0" data-draft-asset-tooltip="${escapeAttr(tooltip)}" aria-label="${escapeAttr(`${label}: ${display}`)}"><span>${escapeHtml(label)}</span><i aria-hidden="true"><b style="${performanceBarStyle(Number(value))}"></b>${average == null ? "" : `<em class="coach-league-average" style="left:${clampNumber(Number(average),0,100)}%"></em>`}</i><strong>${value == null ? "—" : draftMetric(value)}</strong></div>`;
}

function coachTraitRows(traits = {}, info = {}) {
  const entries = Object.entries(traits).filter(([, value]) => value != null && Number.isFinite(Number(value)));
  if (!entries.length) return `<div class="empty">No trait data.</div>`;
  return entries.map(([key, value]) => coachRatingRow(rowLabel(key), value, key, info)).join("");
}

function coachProfileCardMarkup(staff, portraitId, info = {}, options = {}) {
  const role = staffRoleLabel(staff.slot || staff.role);
  const salary = options.candidate ? Number(staff.asking_salary_millions || staffAav(staff)) : staffAav(staff);
  const years = options.candidate ? Number(staff.asking_years || staffYears(staff)) : staffYears(staff);
  return `<div class="coach-profile-card">
    <section class="coach-profile-identity">
      ${coachPortraitMarkup(portraitId, "coach-profile-portrait")}
      <div class="coach-profile-bio">${options.context ? `<p class="coach-profile-context">${escapeHtml(options.context)}</p>` : ""}<h2>${escapeHtml(staffName(staff))}</h2><p>${escapeHtml(role)}</p></div>
      <dl class="coach-profile-contract" aria-label="${options.candidate ? "Candidate asking contract" : "Coach contract"}"><dt>${options.candidate ? "Asking contract" : "Contract"}</dt><dd>${salary ? `${money(salary)} x ${years || "—"}` : "—"}</dd></dl>
      <div class="coach-profile-overview" aria-label="Coach overview ratings">${coachRatingRow("Grade", staffGrade(staff), "grade", info)}${options.candidate ? (options.gradeChange == null ? "" : `<p class="coach-profile-grade-change"><strong>${options.gradeChange > 0 ? "+" : ""}${options.gradeChange.toFixed(1)}</strong> rating points vs current coach</p>`) : `${coachRatingRow("Morale", staff.morale, "morale", info)}${coachRatingRow("Job security", staff.job_security, "job_security", info)}`}</div>
    </section>
    <div class="coach-profile-panels">
      <section class="coach-profile-traits"><header>Coaching Traits</header><div>${coachTraitRows(staff.skill_traits || {}, info)}</div></section>
      <section class="coach-profile-traits"><header>Working Style</header><div>${coachTraitRows(staff.personality_traits || {}, info)}</div></section>
    </div>
  </div>`;
}

async function dashboardCoachCard(staffId) {
  const rows = staffRows(state.data.dashboard || {});
  const staff = rows.find((row, index) => staffIdentity(row, index) === String(staffId || ""));
  if (!staff) return showToast("That coach is no longer available.", true);
  const info = await action("coach_card", {...savePayload(), staff_id:staff.id});
  if (!info) return;
  const portraitId = coachPortraitAssignments(rows).get(staffIdentity(staff));
  await openPlayerCardOnClipboard({key:`coach:${staff.id}`, title:`${staffName(info.staff)} · Coach Card`, kind:"coach", body:coachProfileCardMarkup(info.staff, portraitId, info)});
}

function staffRoleLabel(role) {
  return ({
    head_coach: "Head Coach",
    offensive_coordinator: "Offensive Coordinator",
    defensive_coordinator: "Defensive Coordinator",
    development_lead: "Development Lead",
    performance_lead: "Performance Lead",
    scouting_lead: "Scouting Lead",
  })[String(role || "").toLowerCase()] || rowLabel(role || "Staff");
}

function seasonMinutesCard(rows, editable) {
  if (editable) ensureRotationDraft(rows);
  const assigned = (row) => isPlayerInjured(row.health)
    ? 0
    : Number(state.rotationDraft[row.id] ?? row.rotation_target_minutes ?? row.minutes_projection ?? 0);
  const sortedRows = [...rows].sort((left, right) => assigned(right) - assigned(left));
  return `${seasonPanelHeader("Minutes + Availability", "", "availability")}
    <div class="season-minutes-table" style="--roster-count:${Math.max(1, rows.length)}">
      <div class="season-minutes-head"><span>Player</span><span>Pos</span><span>Height</span><span>Minutes</span><span>Fatigue</span></div>
      ${sortedRows.map((row) => {
        const injured = isPlayerInjured(row.health);
        const injuryStatus = playerInjuryStatusMarkup(row) + playerRustMarkup(row) + playerRestMarkup(row);
        const minuteValue = injured ? 0 : clampNumber(assigned(row), 0, 48);
        const rotationLocked = !injured && (state.rotationLockedPlayerIds.has(row.id) || row.rotation_user_set);
        const position = String(row.position || "—").trim() || "—";
        const height = heightFromRow(row) || "—";
        return `<div class="season-minute-row${injured ? " injured" : ""}" data-minute-row="${escapeAttr(row.id)}">
          <button type="button" data-dashboard-player-card="${escapeAttr(row.id)}">${playerHeadshotMarkup(row, "roster-player-headshot")}<span class="season-minute-player-name">${escapeHtml(row.name || "Unknown")}</span>${injuryStatus}<i class="season-row-motion" aria-hidden="true" hidden></i></button>
          <span class="season-minute-position" title="${escapeAttr(row.position || "Position unavailable")}">${escapeHtml(position)}</span>
          <span class="season-minute-height">${escapeHtml(height)}</span>
          <div class="season-minute-control"><label class="season-minute-slider${rotationLocked ? " user-locked" : ""}"><i><b class="season-minute-fill" style="width:${(minuteValue / 48 * 100).toFixed(2)}%"></b></i><input type="range" min="0" max="48" step="1" value="${minuteValue}" data-minute-player="${escapeAttr(row.id)}" aria-label="Minutes for ${escapeAttr(row.name || "player")}" ${editable && !injured ? "" : "disabled"} /></label><output class="is-sorted-value" data-minute-output="${escapeAttr(row.id)}">${minuteValue}</output><button type="button" class="season-minute-reset" data-minute-reset-player="${escapeAttr(row.id)}" aria-label="Reset ${escapeAttr(row.name || "player")} to automatic minutes" title="Reset to automatic minutes" ${rotationLocked && editable && !injured ? "" : "hidden"} ${editable && !injured ? "" : "disabled"}>×</button></div>
          ${seasonFatigueCell(row)}
        </div>`;
      }).join("") || `<div class="empty">No roster loaded.</div>`}
    </div>`;
}

function seasonMiniRating(value) {
  const score = clampNumber(Number(value || 0), 0, 99);
  return `<span class="season-mini-rating"><em>${score.toFixed(0)}</em><i><b style="${performanceBarStyle(score)}"></b></i></span>`;
}

function seasonFatigueCell(row) {
  const fatigue = clampNumber(Number(row.health?.fatigue || 0), 0, 100);
  const level = clampNumber(Math.round((fatigue / 100) * 6), 0, 6);
  const tone = level <= 2 ? "low" : level <= 4 ? "medium" : "high";
  return `<span class="season-fatigue ${tone}" title="Simulated fatigue: ${fatigue.toFixed(1)} / 100. Game minutes build fatigue; rest days reduce it.">${Array.from({ length: 6 }, (_unused, index) => `<i class="${index < level ? "filled" : ""}"></i>`).join("")}</span>`;
}

function seasonDevelopmentCard(rows) {
  const rosterIds = new Set(rows.map((row) => String(row.id || "")));
  const candidates = developmentPlayerCandidates(rows)
    .filter((candidate) => rosterIds.has(String(candidate.player_id)))
    .sort((left, right) => developmentMovementScore(right) - developmentMovementScore(left));
  const monthLabel = seasonDevelopmentMonthLabel(
    state.data?.dashboardTrends?.development?.latest_month || candidates[0]?.points?.at(-1)?.label,
  );
  return `<div class="season-development-list" style="--development-count:${Math.max(1, Math.min(9, candidates.length))};--development-total:${Math.max(1, candidates.length)}">
      <div class="season-development-head"><span>Player</span><span>Age</span><span title="Growth runway (young players) or decline watch (veterans, ↓ per year). Growth runway: room this player has left to improve, from age, role and current level, on a 0-5 scale. Not a prediction of a future rating; 0 for most players 27 and older.">Growth runway</span><span title="Change in overall rating this season (October to June) and in the latest month, from the game's actual rating changes.">Rating change</span></div>
      ${candidates.map((player) => {
        const points = player.points || [];
        const values = points.map((point) => Number(point.value)).filter(Number.isFinite);
        const seasonDelta = values.length > 1 ? values.at(-1) - values[0] : 0;
        const monthDelta = values.length > 1 ? values.at(-1) - values.at(-2) : 0;
        const upside = clampNumber(Number(player.upside_remaining || 0), 0, 5);
        const age = Number.isFinite(Number(player.age)) ? Number(player.age).toFixed(0) : "—";
        const summary = `${player.name}, age ${age}: growth runway ${upside.toFixed(1)} of 5, rating change this season ${signedNumber(seasonDelta)}, ${monthLabel} ${signedNumber(monthDelta)}`;
        return `<button type="button" class="season-development-row" data-dashboard-player-card="${escapeAttr(player.player_id)}" aria-label="${escapeAttr(summary)}">
          <span class="season-development-player">${playerHeadshotMarkup(player, "roster-player-headshot")}<span class="season-development-name">${escapeHtml(player.name)}</span></span>
          <span class="season-development-age">${escapeHtml(age)}</span>
          ${declineWatchApplies(player) ? seasonDevelopmentDecline(player.decline_watch) : seasonDevelopmentUpside(upside)}
          <span class="season-development-metrics">
            ${seasonDevelopmentMetric("Season", seasonDelta, 2)}
            ${seasonDevelopmentMetric(monthLabel, monthDelta, 0.5)}
          </span>
        </button>`;
      }).join("") || `<div class="empty">Development history will appear after the first monthly update.</div>`}
    </div>`;
}

function setDevelopmentCardExpanded(expanded, card) {
  const panel = card?.matches?.('.season-development-panel') ? card : card?.querySelector?.('.season-development-panel');
  if (!panel) return;
  if (expanded && !panel.classList.contains('is-expanded')) {
    const row = panel.querySelector('.season-development-row');
    panel.style.setProperty('--development-row-height', `${row?.offsetHeight || 48}px`);
  }
  panel.classList.toggle('is-expanded', Boolean(expanded));
  if (!expanded) panel.querySelector('.season-development-list')?.scrollTo(0, 0);
}

function seasonDevelopmentUpside(value) {
  const upside = clampNumber(Number(value || 0), 0, 5);
  const circumference = 56.55;
  const color = playerUpsideColor(upside);
  const label = `Growth runway ${upside.toFixed(1)} of 5. Room this player has left to improve, from age, role and current level, on a 0-5 scale. Not a prediction of a future rating; 0 for most players 27 and older.`;
  return `<span class="season-development-upside" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="9" style="stroke:${color};stroke-dasharray:${circumference};stroke-dashoffset:${circumference * (1 - upside / 5)}"></circle></svg>
    <strong>${upside.toFixed(1)}</strong>
  </span>`;
}

// Decline watch: veterans with no growth runway left show the engine's expected change in overall over the
// next 12 months if healthy (same monthly development model as the season, without its random noise).
const DECLINE_WATCH_TIP = "Decline watch: how much his hidden ratings are expected to drop over the next 12 months if he stays healthy, from the game's aging and development model (average per rating). An average, not a guarantee.";

function declineWatchApplies(row) {
  const value = Number(row?.decline_watch?.per_year);
  return Number.isFinite(value) && value <= -0.1 && Number(row?.upside_remaining || 0) <= 0;
}

function declineWatchDetail(decline) {
  return `${DECLINE_WATCH_TIP} Next year: ${Number(decline.per_year).toFixed(1)} per rating (athletic ${Number(decline.athletic).toFixed(1)}, skills ${Number(decline.skill).toFixed(1)}).`;
}

function seasonDevelopmentDecline(decline) {
  const amount = Number(decline.per_year);
  const label = declineWatchDetail(decline);
  return `<span class="season-development-upside season-development-decline" role="img" aria-label="${escapeAttr(label)}" title="${escapeAttr(label)}"><span aria-hidden="true">↓</span><strong>${Math.abs(amount).toFixed(1)}</strong><small>/yr</small></span>`;
}

function seasonDevelopmentMonthLabel(value) {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const match = String(value || "").trim().match(/(?:^|[-/])(\d{1,2})$/);
  const month = Number(match?.[1]);
  return month >= 1 && month <= 12 ? months[month - 1] : "Month";
}

// scale: the OVR change that fills half the bar (real season changes are ~0-2 points, months ~0-0.5).
function seasonDevelopmentMetric(label, delta, scale = 2) {
  const amount = Number.isFinite(Number(delta)) ? Number(delta) : 0;
  const rounded = Number(amount.toFixed(1));
  const tone = rounded > 0 ? "positive" : rounded < 0 ? "negative" : "neutral";
  const width = clampNumber((Math.abs(amount) / Math.max(0.1, scale)) * 50, 0, 50);
  const direction = amount < 0 ? `right:50%` : `left:50%`;
  return `<span class="season-development-metric">
    <span class="season-development-period">${escapeHtml(label)}</span>
    <i class="season-development-diverging" aria-hidden="true"><b class="${tone}" style="width:${width}%;${direction}"></b></i>
    <strong class="${tone}">${signedNumber(amount)}</strong>
  </span>`;
}

function leagueActivitySubject(subject) {
  const portrait = subject.kind === "staff" ? coachPortraitMarkup(coachPortraitAssignments([subject]).get(staffIdentity(subject)), "wire-staff-portrait") : playerHeadshotMarkup(subject, "wire-player-headshot");
  return `<div class="wire-subject ${subject.kind === "pick" ? "is-pick" : ""}"><div class="wire-subject-art">${portrait}${subject.kind === "pick" ? `<strong class="wire-pick-label">${escapeHtml(subject.season || "Draft")}<small>${subject.round ? `ROUND ${escapeHtml(subject.round)}` : "PICK"}</small></strong>` : ""}</div><span>${escapeHtml(subject.name || "")}</span></div>`;
}

function leagueActivityComment(event) {
  const paragraphs = event.activity_comments || [];
  return `<details class="wire-comments"><summary>Details <span>1 comment</span></summary><div class="wire-comment"><div class="wire-comment-author">League Insider <span>@leagueinsider</span></div>${paragraphs.map(text => `<p>${escapeHtml(text)}</p>`).join("") || `<p>${escapeHtml(event.headline || "No additional details available.")}</p>`}${(event.activity_groups || []).some(group => (group.subjects || []).some(subject => subject.kind === "player")) ? `<small class="wire-profile-note">Player profiles reflect the current season.</small>` : ""}</div></details>`;
}

function seasonLeagueWire(expanded = false) {
  const events = state.home?.league_events?.events || [];
  if (expanded) {
    const items = events.map((event) => {
      const normalized = normalizeLeagueEvent(event);
      const groups = event.activity_groups || [];
      const media = groups.some(group => group.subjects?.length) ? groups.map(group => {
        const subjects = group.subjects || [];
        const columns = subjects.length > 1 ? 2 : 1;
        return `<section class="wire-asset-group" style="--asset-columns:${columns};--asset-rows:${Math.max(1, Math.ceil(subjects.length / columns))}">${groups.length > 1 ? `<div class="wire-asset-team"><strong>${escapeHtml(group.team)}</strong><span>receives</span></div>` : ""}${teamLogoSrc(group.team) ? `<img class="wire-group-logo" src="${escapeAttr(teamLogoSrc(group.team))}" alt="${escapeAttr(group.team)}">` : ""}<div class="wire-subjects">${subjects.map(leagueActivitySubject).join("")}</div></section>`;
      }).join("") : normalized.teams.map(team => `<img class="wire-fallback-logo" src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)}">`).join("");
      return `<article class="season-wire-post" data-league-event-id="${escapeAttr(event.id || "")}"><header class="wire-post-author"><span class="wire-reporter-avatar">LI</span><div><strong>League Insider</strong><span>@leagueinsider · <time>${escapeHtml(normalized.date)}</time></span></div></header><div class="wire-post-type">${escapeHtml(rowLabel(normalized.kind))}</div><div class="wire-post-media ${groups.length > 1 ? "is-trade" : ""}">${media}</div><h3 class="wire-post-headline">${escapeHtml(event.activity_headline || normalized.text)}</h3>${leagueActivityComment(event)}</article>`;
    }).join("");
    return `<footer class="season-league-wire season-league-wire-expanded" aria-label="League activity"><div class="season-wire-activity-list">${items || `<div class="season-wire-activity-empty">No league activity to show.</div>`}</div></footer>`;
  }
  const items = events.slice(0, 12).map((event) => {
    const normalized = normalizeLeagueEvent(event);
    const marks = normalized.teams.map((team) => {
      const logo = teamLogoSrc(team);
      return logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(team)}" />` : "";
    }).join("");
    return `<span class="season-wire-item">${marks}<em>${escapeHtml(normalized.date)}</em><strong>${escapeHtml(normalized.text)}</strong></span>`;
  }).join("");
  return `<footer class="season-league-wire"><div class="season-wire-window"><div class="season-wire-track">${items || `<span class="season-wire-item"><strong>No recent league events.</strong></span>`}</div></div></footer>`;
}

function setLeagueWireCardExpanded(expanded, card) {
  if (!card) return false;
  const template = document.createElement("template");
  template.innerHTML = seasonLeagueWire(Boolean(expanded)).trim();
  const updated = template.content.firstElementChild;
  if (!updated) return false;
  card.className = updated.className;
  card.innerHTML = updated.innerHTML;
  return true;
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

async function fantasyPlayerCard(playerId) {
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
    ["OVR", ratings.overall || player.ratings_prior_overall],
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
  const body = `<div class="fantasy-player-card">
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
    </div>`;
  await openPlayerCardOnClipboard({
    key:`fantasy:${playerId}`,
    title:`${player.name || "Player"} · Player Card`,
    kind:"fantasy",
    body,
  });
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
    ["OVR", ratings.overall], ["Shooting", ratings.shooting], ["Release", ratings.release],
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

async function draftProspectCard(prospectId) {
  const rows = [...draftBoardRows(state.data.draft?.draft_board || {}), ...draftBoardRows(state.data.dashboardProspects || {})];
  const row = rows.find(item => String(item.id) === String(prospectId));
  if (!row) return;
  const detail = await action("prospect_card", {...savePayload(), prospect_id:prospectId, year:row.prospect?.draft_year});
  if (!detail) return;
  await openPlayerCardOnClipboard({
    key:`prospect:${prospectId}`, title:`${detail.name || row.name || "Prospect"} · Prospect Card`, kind:"prospect",
    body:approvedPlayerCardBody({...detail, board_rank:row.rank || detail.board_rank}),
  });
}

function fantasyPlayerRadar(title, axes, className, showTitle = true) {
  const width = 360;
  const height = 240;
  const centerX = width / 2;
  const centerY = 112;
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
    ${showTitle ? `<h5>${escapeHtml(title)}</h5>` : ''}
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(title)} radar chart">
      ${[0.25, 0.5, 0.75, 1].map((level) => `<polygon class="player-radar-grid" points="${polygon(level)}"></polygon>`).join("")}
      ${axes.map((_, index) => { const edge = point(index, 1); return `<line class="player-radar-axis" x1="${centerX}" y1="${centerY}" x2="${edge.x.toFixed(1)}" y2="${edge.y.toFixed(1)}"></line>`; }).join("")}
      ${axes.every(([,value])=>value != null) ? `<polygon class="player-radar-shape" points="${shape}"><title>${escapeHtml(axes.map(([label, value]) => `${label}: ${decimalNumber(value)}`).join(" | "))}</title></polygon>` : `<text x="${centerX}" y="${centerY}" text-anchor="middle" class="prospect-radar-locked">Scouting incomplete</text>`}
      ${axes.map(([label, value], index) => {
        const labelPoint = point(index, 1, 28);
        const anchor = Math.abs(labelPoint.x - centerX) < 8 ? "middle" : labelPoint.x < centerX ? "end" : "start";
        return `<text class="player-radar-label" text-anchor="middle" x="${labelPoint.x.toFixed(1)}" y="${labelPoint.y.toFixed(1)}"><tspan x="${labelPoint.x.toFixed(1)}">${escapeHtml(label)}</tspan><tspan class="player-radar-value" x="${labelPoint.x.toFixed(1)}" dy="15">${value == null ? "Locked" : decimalNumber(value)}</tspan></text>`;
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
  return `
    <div class="playoff-command-center">
      <div class="phase-playoff-layout">
        <div class="phase-bracket-shell">
          ${playoffBracket(series, room.champion, room.play_in)}
        </div>
        <aside class="phase-leaders-panel playoff-stats-panel" data-playoff-stats>
          ${playoffStatsTable(state.data.playoffLeaders?.leaders || [], state.playoffStatsSort)}
        </aside>
      </div>
    </div>`;
}

// Playoff Stats card: every player's playoff line (playoff games only), sortable by any column.
const PLAYOFF_STATS_LIMIT = 500;
const PLAYOFF_STATS_DEFAULT_SORT = { key: "points_per_game", direction: "desc" };
const PLAYOFF_STATS_COLUMNS = [
  { key: "player", label: "Player", title: "Player", text: true, width: 150 },
  { key: "team", label: "Team", title: "Team", text: true, width: 52 },
  { key: "games", label: "GP", title: "Playoff games played", digits: 0, width: 30 },
  { key: "minutes_per_game", label: "MIN", title: "Minutes per playoff game", width: 38 },
  { key: "points_per_game", label: "PTS", title: "Points per playoff game", width: 38 },
  { key: "rebounds_per_game", label: "REB", title: "Rebounds per playoff game", width: 38 },
  { key: "assists_per_game", label: "AST", title: "Assists per playoff game", width: 38 },
  { key: "steals_per_game", label: "STL", title: "Steals per playoff game", width: 34 },
  { key: "blocks_per_game", label: "BLK", title: "Blocks per playoff game", width: 34 },
  { key: "fg3m_per_game", label: "3PM", title: "Threes made per playoff game", width: 36 },
  { key: "fg_pct", label: "FG%", title: "Playoff field-goal percentage", width: 40 },
  { key: "fg3_pct", label: "3P%", title: "Playoff three-point percentage", width: 40 },
  { key: "ft_pct", label: "FT%", title: "Playoff free-throw percentage", width: 40 },
];

function playoffStatsColumn(key) {
  return PLAYOFF_STATS_COLUMNS.find((column) => column.key === key) || null;
}

function playoffStatsSortState(sort) {
  return playoffStatsColumn(sort?.key) && ["asc", "desc"].includes(sort?.direction) ? sort : PLAYOFF_STATS_DEFAULT_SORT;
}

// Clicking the sorted column flips direction; a new column starts high-to-low (names and teams A-Z).
function nextPlayoffStatsSort(current, key) {
  const column = playoffStatsColumn(key);
  if (!column) return playoffStatsSortState(current);
  const active = playoffStatsSortState(current);
  if (active.key === key) return { key, direction: active.direction === "desc" ? "asc" : "desc" };
  return { key, direction: column.text ? "asc" : "desc" };
}

function playoffStatsName(row) {
  return String(row.player_name || row.player?.name || "Unknown");
}

function playoffStatsValue(row, key) {
  if (key === "player" || key === "team") {
    const raw = key === "player" ? playoffStatsName(row) : String(row.team_abbrev || "");
    const text = raw.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    return { value: text, numeric: false, missing: !text };
  }
  const raw = row[key];
  const number = Number(raw);
  return { value: number, numeric: true, missing: raw === null || raw === undefined || raw === "" || !Number.isFinite(number) };
}

// Rows without a value (e.g. no three-point attempts) stay at the bottom in either direction.
function playoffStatsOrderedRows(rows, sort) {
  const active = playoffStatsSortState(sort);
  const tiebreak = (left, right) => {
    const points = Number(right.row.points_per_game || 0) - Number(left.row.points_per_game || 0);
    if (points) return points;
    const name = playoffStatsName(left.row).localeCompare(playoffStatsName(right.row));
    return name || left.index - right.index;
  };
  return (rows || []).map((row, index) => ({ row, index })).sort((left, right) => {
    const a = playoffStatsValue(left.row, active.key);
    const b = playoffStatsValue(right.row, active.key);
    if (a.missing !== b.missing) return a.missing ? 1 : -1;
    if (a.missing) return tiebreak(left, right);
    let comparison = a.numeric && b.numeric ? a.value - b.value : a.value < b.value ? -1 : a.value > b.value ? 1 : 0;
    if (active.direction === "desc") comparison *= -1;
    return comparison || tiebreak(left, right);
  }).map(({ row }) => row);
}

function playoffStatsCellText(row, column) {
  const { value, missing } = playoffStatsValue(row, column.key);
  if (missing) return "—";
  return value.toFixed(column.digits ?? 1);
}

function playoffStatsTable(rows, sort) {
  const active = playoffStatsSortState(sort);
  const ordered = playoffStatsOrderedRows(rows, active);
  const head = PLAYOFF_STATS_COLUMNS.map((column) => {
    const sorted = column.key === active.key;
    const ariaSort = sorted ? (active.direction === "desc" ? "descending" : "ascending") : "none";
    const mark = sorted ? (active.direction === "desc" ? " ↓" : " ↑") : "";
    return `<th scope="col" class="playoff-stats-col-${column.key}${sorted ? " is-sorted" : ""}" aria-sort="${ariaSort}"><button type="button" data-playoff-stats-sort="${column.key}" title="Sort by ${escapeHtml(column.title)}">${escapeHtml(column.label)}${mark}</button></th>`;
  }).join("");
  const body = ordered.map((row, index) => {
    const id = String(row.player_id || row.player?.id || "");
    const name = playoffStatsName(row);
    const portraitRow = { headshot_url: row.headshot_url || row.player?.headshot_url || "" };
    const portrait = playerHeadshotMarkup(portraitRow, "roster-player-headshot") || playerHeadshotMarkup({ is_prospect: true }, "roster-player-headshot");
    const team = String(row.team_abbrev || "");
    const logo = team ? teamLogoSrc(team) : "";
    const cells = PLAYOFF_STATS_COLUMNS.map((column) => {
      const sortedClass = column.key === active.key ? " is-sorted" : "";
      if (column.key === "player") {
        return `<th scope="row" class="playoff-stats-col-player${sortedClass}"><button type="button" class="playoff-stats-player-link" data-dashboard-player-card="${escapeAttr(id)}" aria-label="Open ${escapeAttr(name)} player card">${portrait}<span class="playoff-stats-rank">${index + 1}.</span><span class="player-name-text">${escapeHtml(name)}</span></button></th>`;
      }
      if (column.key === "team") {
        return `<td class="playoff-stats-col-team${sortedClass}"><span class="playoff-stats-team">${logo ? `<img src="${escapeAttr(logo)}" alt="" aria-hidden="true" loading="lazy" decoding="async">` : ""}<span>${escapeHtml(team || "—")}</span></span></td>`;
      }
      return `<td class="playoff-stats-col-${column.key}${sortedClass}">${playoffStatsCellText(row, column)}</td>`;
    }).join("");
    return `<tr data-playoff-stats-player="${escapeAttr(id)}">${cells}</tr>`;
  }).join("");
  const empty = `<tr class="playoff-stats-empty"><td colspan="${PLAYOFF_STATS_COLUMNS.length}">Playoff stats appear after the first playoff game.</td></tr>`;
  return `<div class="playoff-stats-scroll"><table class="playoff-stats-table" aria-label="Playoff stats, per playoff game"><colgroup>${PLAYOFF_STATS_COLUMNS.map((column) => `<col style="width:${column.width}px">`).join("")}</colgroup><thead><tr>${head}</tr></thead><tbody>${body || empty}</tbody></table></div>`;
}

// Re-sorts in place so the card keeps its window, scroll position and keyboard focus.
function wirePlayoffStatsTable(root = document) {
  root.querySelectorAll("[data-playoff-stats]").forEach((panel) => {
    wireDashboardPlayerCards(panel);
    panel.querySelectorAll("[data-playoff-stats-sort]").forEach((button) => {
      if (button.dataset.playoffStatsSortWired) return;
      button.dataset.playoffStatsSortWired = "true";
      button.addEventListener("click", () => {
        const key = button.dataset.playoffStatsSort;
        state.playoffStatsSort = nextPlayoffStatsSort(state.playoffStatsSort, key);
        const scroll = panel.querySelector(".playoff-stats-scroll");
        const top = scroll?.scrollTop || 0;
        const left = scroll?.scrollLeft || 0;
        panel.innerHTML = playoffStatsTable(state.data.playoffLeaders?.leaders || [], state.playoffStatsSort);
        const next = panel.querySelector(".playoff-stats-scroll");
        if (next) { next.scrollTop = top; next.scrollLeft = left; }
        wirePlayoffStatsTable(panel.parentElement || panel);
        panel.querySelector(`[data-playoff-stats-sort="${key}"]`)?.focus();
      });
    });
  });
}

function draftDashboardWorkspace() {
  const draft = state.data.draft || {};
  const current = draft.current_selection || {};
  const selection = current.selection || {};
  const prospect = current.prospect || {};
  const status = draft.state?.status || "in_progress";
  const locked = status === "locked_until_draft";
  const completedDraft = !state.draftPlaybackRunning && (status === "completed" || (!current.selection && (draft.draft_timeline || []).length > 0));
  const presentationKey = `${state.currentSave}:${draft.year || "draft"}`;
  if (state.draftPresentationKey !== presentationKey) {
    state.draftPresentationKey = presentationKey;
    state.draftPresentationStage = draft.presentation_stage || (locked ? "odds" : "draft");
  } else if (draft.presentation_stage === "draft" && state.draftPresentationStage === "odds") {
    state.draftPresentationStage = "draft";
  }
  if (locked && !["odds","reveal"].includes(state.draftPresentationStage)) state.draftPresentationStage = draft.presentation_stage || "odds";
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
      </header>
      ${state.draftPlaybackRunning ? `<div class="draft-pick-reveal" role="status" aria-live="polite">${state.draftPlaybackReveal?.type === "pick" ? `${draftTeamLogo(state.draftPlaybackReveal.team)}<span>Pick #${escapeHtml(state.draftPlaybackReveal.overall_pick)}</span><strong>${escapeHtml(teamLabel(state.draftPlaybackReveal.team))} selects ${escapeHtml(state.draftPlaybackReveal.prospect?.name || "Unknown prospect")}</strong>` : `<span>Draft selections underway</span><strong>Revealing picks in order</strong>`}</div>` : ""}
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
  return `<div class="draft-lottery-card">
    <header class="draft-lottery-summary"><strong>${escapeHtml(draft.year || "")} Draft Lottery</strong><span>No. 1 Odds</span></header>
    <div class="draft-odds-grid">${(lottery.odds || []).map((row) => `<article class="draft-odds-row"><span class="draft-seed">${escapeHtml(row.seed)}</span>${draftTeamLogo(row.team)}<strong>${escapeHtml(teamLabel(row.team))}</strong><em>${(Number(row.odds || 0) * (Number(row.odds || 0) <= 1 ? 100 : 1)).toFixed(1)}%</em>${row.context ? `<small>${escapeHtml(row.context)}</small>` : ""}</article>`).join("") || `<div class="empty">Lottery odds are not available for this fixed draft order.</div>`}</div>
    <footer class="draft-lottery-note">Four picks drawn · Remaining teams follow record order.</footer>
  </div>`;
}

// Grid placement only: pick 1 sits top-left and the last pick bottom-right.
// Reveal order (last pick first) comes from GameSimulation.lotteryRevealState.
function draftLotteryGridPicks(total) {
  return Array.from({length:Math.max(0, Number(total) || 0)},(_,i)=>i+1);
}

function draftLotteryRevealWorkspace(draft) {
  const lottery = draft.lottery || {};
  const count = lotteryRevealCount(draft);
  const reveal = GameSimulation.lotteryRevealState(lottery,count);
  const visible = new Map(reveal.revealed.map(row=>[Number(row.pick),row]));
  const jumping = (lottery.odds || []).filter(row=>reveal.promoted.includes(row.team.id) && !reveal.revealed.some(p=>p.original_team?.id===row.team.id));
  return `<div class="draft-lottery-card draft-reveal-shell" aria-label="Draft lottery reveal">
    <header class="draft-lottery-summary"><strong>${escapeHtml(draft.year || "")} Draft Lottery</strong><span>${reveal.complete ? 'Order Complete' : `Next: #${reveal.nextPick}`}</span></header>
    <div class="draft-reveal-grid">${draftLotteryGridPicks(reveal.total).map(pick=>{
      const row = visible.get(pick);
      if (!row) return `<article class="draft-reveal-row is-unrevealed" data-lottery-pick="${pick}"><span class="draft-pick-number">${pick}</span><div class="lottery-envelope" aria-hidden="true"></div><strong>Unrevealed</strong><span>—</span></article>`;
      return `<article class="draft-reveal-row${row === reveal.revealed.at(-1) ? ' is-latest' : ''}" data-lottery-pick="${pick}" data-revealed="true"><span class="draft-pick-number">${pick}</span>${draftTeamLogo(row.original_team)}<div><strong>${escapeHtml(teamLabel(row.original_team))}</strong><small>Seed ${escapeHtml(row.starting_seed || pick)}${row.ownership_changed ? ` · Pick → ${escapeHtml(teamLabel(row.owner_team))}` : ''}</small></div><em class="${Number(row.movement)>0?'up':Number(row.movement)<0?'down':''}">${Number(row.movement)>0?`↑${row.movement}`:Number(row.movement)<0?`↓${Math.abs(row.movement)}`:'—'}</em></article>`;
    }).join('')}</div>
    <footer class="draft-lottery-note${jumping.length ? ' lottery-jump-notice' : ''}" role="status">${jumping.length ? `${jumping.map(row=>escapeHtml(teamLabel(row.team))).join(', ')} jumped into the top four` : reveal.complete ? 'Lottery complete' : '14 → 1'}</footer>
  </div>`;
}

function lotteryRevealKey(draft = state.data.draft || {}) { return `nbaGmLotteryReveal:${state.currentSave}:${draft.year}`; }
function lotteryRevealCount(draft = state.data.draft || {}) {
  if (state.lotteryRevealKey !== lotteryRevealKey(draft)) {
    state.lotteryRevealKey = lotteryRevealKey(draft);
    try { state.lotteryRevealCount = Math.max(0,Number(localStorage.getItem(state.lotteryRevealKey) || 0)) || 0; }
    catch { state.lotteryRevealCount = 0; }
  }
  return state.lotteryRevealCount || 0;
}

function clipboardPhaseCommands() {
  const button = (id,command,label,disabled=false)=>`<button type="button" class="ui-command" id="${id}" data-phase-command="${command}"${disabled?' disabled':''}>${label}</button>`;
  if (state.home?.save?.postseason_exit_required) return button('postseasonAdvance','postseason-exit','Advance To Draft Lottery');
  if (dashboardPhaseKind() !== 'draft') return '';
  const draft = state.data.draft || {};
  if (state.draftPresentationStage === 'odds') return button('draftRevealLottery','lottery-reveal','Reveal Lottery');
  if (state.draftPresentationStage === 'reveal') {
    if (state.lotteryRevealRunning) return button('draftSkipReveal','lottery-skip','Skip Reveal');
    if (lotteryRevealCount(draft) < (draft.lottery?.reveal || []).length) return button('draftRevealLottery','lottery-reveal','Continue Reveal');
    return button('draftEnterNight','draft-enter','Enter Draft Night');
  }
  const current = draft.current_selection?.selection;
  if (!current) return button('draftAdvanceStage','draft-next','Advance To Next Stage');
  const picked = draftBoardRows(draft.draft_board).find(row=>row.id===state.selectedDraftProspect);
  return (draft.current_pick_is_user_owned
    ? button('draftApply','draft-apply',picked?`Draft ${escapeHtml(picked.name)}`:'Choose A Prospect',!picked)
    : button('draftSimCurrent','draft-one',`Sim Pick #${Number(current.overall_pick)}`))
    + (!draft.current_pick_is_user_owned && draft.next_user_selection ? button('draftToUser','draft-user','Sim To My Pick'):'')
    + button('draftAll','draft-all','Finish Draft');
}

async function runLotteryReveal() {
  if (state.lotteryRevealRunning) return;
  const draft = state.data.draft, key = lotteryRevealKey(draft), save = state.currentSave;
  lotteryRevealCount(draft);
  const runId = (state.lotteryRunId || 0) + 1;
  state.lotteryRunId = runId;
  state.lotteryRevealRunning = true;
  renderDashboard();
  try {
    while (state.currentSave === save && state.lotteryRunId === runId && state.lotteryRevealKey === key && state.lotteryRevealCount < (draft.lottery?.reveal || []).length) {
      await GameSimulation.wait(1100);
      if (!state.lotteryRevealRunning || state.currentSave !== save || state.lotteryRunId !== runId) break;
      state.lotteryRevealCount += 1;
      try { localStorage.setItem(key,String(state.lotteryRevealCount)); } catch {}
      const panel = document.querySelector('[data-board-window="phase-draft-lottery"] .draft-lottery-card');
      if (panel) panel.outerHTML = draftLotteryRevealWorkspace(draft);
    }
  } finally {
    if (state.lotteryRunId === runId) {
      state.lotteryRevealRunning = false;
      if (state.currentSave === save && !state.simulationRunning) renderDashboard();
    }
  }
}

function finishLotteryReveal() {
  state.lotteryRunId = (state.lotteryRunId || 0) + 1;
  state.lotteryRevealRunning = false;
  state.lotteryRevealCount = (state.data.draft?.lottery?.reveal || []).length;
  try { localStorage.setItem(lotteryRevealKey(),String(state.lotteryRevealCount)); } catch {}
  renderDashboard();
}

function draftProspectBoard(rows, selectable = false, selectedId = "") {
  const headings = [
    ["rank", "Rank"], ["name", "Prospect"], ["position", "Pos"], ["age", "Age"],
    ["height", "Ht"], ["now", "Now"], ["potential", "Pot"], ["fit", "Fit"], ["injury", "Injury"], ["status", "Status"],
  ];
  const headingTips = {potential: "Scouted potential: your scouts' best guess at this prospect's realistic peak. Not his hidden true rating.", now: "Scouted current level on the overall scale."};
  return `<div class="draft-prospect-scroll"><table class="draft-prospect-table"><thead><tr>${headings.map(([key, label]) => {const sort=state.draftBoardSort||{};const active=sort.key===key;return `<th aria-sort="${active?(sort.direction==='desc'?'descending':'ascending'):'none'}"${headingTips[key] ? ` title="${escapeAttr(headingTips[key])}"` : ""}><button class="draft-sort-button" data-draft-sort="${escapeAttr(key)}">${escapeHtml(label)}${draftSortMark(key)}</button></th>`;}).join("")}</tr></thead><tbody>${rows.map((row) => {
    const available = row.status !== "drafted";
    const selected = available && String(row.id) === String(selectedId || "");
    return `<tr class="${row.status === "drafted" ? "is-drafted" : ""}${selected ? " is-selected" : ""}${selectable && available ? " is-selectable" : ""}" ${selectable && available ? `data-draft-prospect="${escapeAttr(row.id)}" tabindex="0"` : ""}><td>${escapeHtml(row.rank)}</td><td><button type="button" class="draft-prospect-name" data-draft-prospect-card="${escapeAttr(row.id)}">${escapeHtml(row.name || "Unknown")}</button></td><td>${escapeHtml(row.position || "—")}</td><td>${escapeHtml(row.age ?? "—")}</td><td>${escapeHtml(row.height || "—")}</td><td>${draftMetric(row.now)}</td><td>${draftMetric(row.potential)}</td><td>${draftMetric(row.fit || row.grade)}</td><td class="draft-prospect-injury">${prospectInjuryMarkup(row.injuryReport) || "—"}</td><td>${row.status === "drafted" ? `<span class="drafted-badge">#${escapeHtml(row.selectedPick)} ${escapeHtml(teamLabel(row.selectedTeam))}</span>` : selected ? `<span class="available-badge selected-badge">Selected</span>` : `<span class="available-badge">Available</span>`}</td></tr>`;
  }).join("") || `<tr><td colspan="10" class="empty">No prospects match this view.</td></tr>`}</tbody></table></div>`;
}

function draftPickTimeline(rows) {
  return `<div class="draft-ledger-scroll" data-draft-ledger>${rows.map((row) => {
    const status = row.draft_status || "upcoming";
    const completed = status === "selected";
    const current = status === "current";
    const revealing = state.draftPlaybackRunning && Number(state.draftPlaybackReveal?.overall_pick) === Number(row.selection?.overall_pick);
    return `<div class="draft-ledger-row ${current ? "is-current" : completed ? "is-complete" : "is-upcoming"}${revealing ? " is-revealing" : ""}" data-draft-pick="${escapeAttr(row.selection?.overall_pick || "")}" ${current ? "data-current-draft-pick" : ""}><span class="draft-pick-number">${escapeHtml(row.selection?.overall_pick || "—")}</span>${draftTeamLogo(row.team)}<div><strong>${completed ? escapeHtml(row.prospect?.name || "Unknown prospect") : escapeHtml(teamLabel(row.team))}</strong><small>${completed ? `${escapeHtml(teamLabel(row.team))} · ${escapeHtml(row.prospect?.position || "")}` : current ? "On the clock" : "Upcoming pick"}</small></div>${current ? `<em>NOW</em>` : ""}</div>`;
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
        <button type="button" class="ui-command" data-open-waivers>Waivers</button>
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
    {key:'name',label:'Player',width:130,value:p=>p.name,cell:p=>`<button type="button" data-fa-player-card="${escapeAttr(p.id)}">${playerNameWithInjuryMarkup(p)}</button>`},
    {key:'age',label:'Age',width:25,value:p=>p.age},
    {key:'position',label:'Pos',width:25,value:p=>p.position},
  ];
  const ratings=[['OVR','overall'],['OFF','offense'],['DEF','defense'],['Shot','shooting'],['Cre','creation'],['Pass','passing'],['Reb','rebounding'],['Rim','rim_deterrence'],['Ath','athleticism']].map(([label,key],i)=>({key,label,width:i<3?54:undefined,value:p=>Number(p.ratings?.[key]??(key==='offense'?p.ratings?.overall:0)),cell:p=>i<3?compactRatingBar(p.ratings?.[key]??(key==='offense'?p.ratings?.overall:0)):draftMetric(p.ratings?.[key])}));
  const stats=[['GP','games'],['MPG','previous_mpg'],['PTS','ppg'],['REB','rpg'],['AST','apg'],['STL','spg'],['BLK','bpg'],['TO','topg']].map(([label,key])=>({key,label,value:p=>Number(p[key]||0),cell:p=>draftMetric(p[key])}));
  const contracts=[
    {key:'team_fit_score',label:'Fit',value:p=>Number(p.team_fit_score||0),cell:p=>draftMetric(p.team_fit_score)},
    {key:'ask_millions',label:'Ask',value:p=>Number(p.ask_millions||0),cell:p=>compactMarketMoney(p.ask_millions)},
    {key:'ask_change_millions',label:'Move',value:p=>Number(p.ask_change_millions||0),cell:p=>freeAgencyAskChange(p.ask_change_millions)||'—'},
    {key:'highest_offer',label:exclusive?'Rights':'Leading bid',width:80,value:p=>Number(p.highest_offer?.aav_millions||0),cell:p=>p.highest_offer?`<span class="linked-leading-bid"><img src="${escapeAttr(teamLogoSrc(p.highest_offer.team_abbrev))}" alt="${escapeAttr(p.highest_offer.team_abbrev||'')}">${money(p.highest_offer.aav_millions)} x ${p.highest_offer.years||1}</span>`:(exclusive?'Exclusive':'—')},
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
        return `<div class="market-live-offer">${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)} logo" />` : ""}<strong>${money(offer.aav_millions)} x ${escapeHtml(offer.years || 1)}</strong><span class="market-offer-interest"><i><b style="width:${interest}%"></b></i><em>${Math.round(interest)}</em></span></div>`;
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
        <p class="muted">Choose which contracts leave the roster.</p>
      </section>
      <section class="phase-board-panel">
        ${table(["Player", "Pos", "Age", "Ht", "MPG", "OVR", "Contract", "Waiver cost", ""], room.players || [], (row) => [
          row.name,
          compactPos(row.position),
          row.age,
          row.height || "—",
          Number(row.minutes || 0).toFixed(1),
          gradeNumber(row.overall),
          compactSalaryYears(row.salary_by_year),
          row.waiver?.unquantified ? 'Unknown' : `${money(row.waiver?.remaining_cost_millions || 0)}${row.waiver?.unverified ? " · unverified reserve" : ""}`,
          row.can_waive
            ? html(`<button class="ui-command" data-waive-player="${escapeAttr(row.player_id)}">Waive</button> <button class="ui-command" data-buyout-player="${escapeAttr(row.player_id)}">Buyout</button>`)
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
        ${sectionHead("Re-sign", `${money(room.ask_millions)} x ${room.ask_years || 2}`)}
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
          `${money(candidate.asking_salary_millions)} x ${candidate.asking_years || 1}`
        ],"retention-market") : `<div class="empty">No replacements are currently available.</div>`}
      </section>
    </div>`;
}

function wireDashboardPhaseWorkspace(kind, root = els.content) {
  if (kind === "fantasy_draft") {
    root.querySelector(".fantasy-player-table")?.addEventListener("scroll", (event) => {
      state.fantasyBoardScrollTop = event.currentTarget.scrollTop;
    }, { passive: true });
    root.querySelectorAll("[data-fantasy-card]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        rememberFantasyBoardScroll();
        fantasyPlayerCard(button.dataset.fantasyCard || "");
      });
    });
    root.querySelectorAll("[data-fantasy-player]").forEach((row) => {
      row.addEventListener("click", () => {
        rememberFantasyBoardScroll();
        state.selectedFantasyPlayer = row.dataset.fantasyPlayer || "";
        renderDashboard();
      });
    });
    root.querySelectorAll("[data-fantasy-watch]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        fantasyDraftToggleWatchlist(button.dataset.fantasyWatch || "");
      });
    });
    root.querySelector("#fantasySearch")?.addEventListener("change", (event) => {
      state.fantasySearch = event.target.value || "";
      state.fantasyBoardScrollTop = 0;
      renderDashboard();
    });
    root.querySelector("#fantasyPosition")?.addEventListener("change", (event) => {
      state.fantasyPosition = event.target.value || "all";
      state.fantasyBoardScrollTop = 0;
      renderDashboard();
    });
    root.querySelector("#fantasyPick")?.addEventListener("click", fantasyDraftPick);
    root.querySelector("#fantasyExitSaves")?.addEventListener("click", returnToSaveSelection);
    root.querySelector("#fantasySimOne")?.addEventListener("click", () => fantasyDraftSim("fantasy_draft_sim_one"));
    root.querySelector("#fantasyToUser")?.addEventListener("click", () => fantasyDraftSim("fantasy_draft_sim_to_user"));
    root.querySelector("#fantasyClockExtension")?.addEventListener("click", fantasyDraftClockExtension);
  }
  if (kind === "playoffs") {
    root.querySelectorAll("[data-game-box]").forEach((button) => button.addEventListener("click", () => openBoxScore(button.dataset.gameBox)));
    root.querySelectorAll("[data-playoff-series]").forEach((button) => {
      button.addEventListener("click", () => openPlayoffSeriesBoxScore(button.dataset.playoffSeries || ""));
    });
    wirePlayoffStatsTable(root);
  }
  if (kind === "draft") {
    root.querySelector("#draftBoardFilter")?.addEventListener("change", (event) => {
      state.draftBoardFilter = event.currentTarget.value || "available";
      renderDashboard();
    });
    root.querySelectorAll("[data-draft-sort]").forEach((button) => button.addEventListener("click", () => {
      const key = button.dataset.draftSort || "rank";
      const current = state.draftBoardSort || { key: "rank", direction: "asc" };
      state.draftBoardSort = {
        key,
        direction: current.key === key && current.direction === "asc" ? "desc" : "asc",
      };
      renderDashboard();
    }));
    root.querySelectorAll("[data-draft-prospect]").forEach((row) => {
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
    root.querySelectorAll("[data-draft-prospect-card]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        draftProspectCard(button.dataset.draftProspectCard || "");
      });
    });
    const ledger = root.querySelector("[data-draft-ledger]");
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
    wireFreeAgencyMarket(root);
    root.querySelector("#faAdvanceDay")?.addEventListener("click", () => advanceFreeAgency("day"));
    root.querySelector("#faAdvanceEnd")?.addEventListener("click", () => advanceFreeAgency("end"));
    root.querySelector("#faAdvanceStage")?.addEventListener("click", freeAgencyAdvanceStage);
    root.querySelector("#reSignAdvanceDay")?.addEventListener("click", () => advanceReSigning("day"));
    root.querySelector("#reSignOpenMarket")?.addEventListener("click", () => advanceReSigning("open_market"));
  }
  if (kind === "cutdown") {
    root.querySelectorAll("[data-buyout-player]").forEach((button) => button.addEventListener("click", async () => {
      const playerId = button.dataset.buyoutPlayer;
      const player = (state.data.cutdown?.players || []).find((row) => row.player_id === playerId);
      const quote = player?.buyout;
      if (!quote) return;
      const charges = quote.cap_charges.map((r) => `${r.season}: ${r.salary == null ? "unknown (reserved)" : money(r.salary / 1000000)}`).join("\n");
      if (!window.confirm(`Buy out ${player.name}?\n${quote.policy}\nRemaining payout: ${quote.unquantified ? 'Unknown' : money(quote.payout_millions)}\nCap charges if unclaimed:\n${charges}\nThe player enters waivers until ${quote.clearance_date}. A claim transfers the original contract instead.`)) return;
      const result = await action("buyout_player", { ...savePayload(), player_id: playerId });
      showToast(`${result.player_name} placed on waivers`);
      await refreshHome();
    }));
    root.querySelectorAll("[data-waive-player]").forEach((button) => button.addEventListener("click", async () => {
      const playerId = button.dataset.waivePlayer;
      const player = (state.data.cutdown?.players || []).find((row) => row.player_id === playerId);
      if (!window.confirm(`Waive ${player?.name || "this player"}? Remaining obligation: ${player?.waiver?.unquantified ? 'unknown' : money(player?.waiver?.remaining_cost_millions || 0)}${player?.waiver?.unverified ? " (includes unverified salary reserves)" : ""}. This salary stays on your books.`)) return;
      const result = await action("waive_player", { ...savePayload(), player_id: playerId });
      showToast(result.status === "waived" ? `${result.player_name} waived` : (result.reason || result.status), result.status !== "waived");
      await refreshHome();
    }));
  }
  if (kind === "staff_retention") {
    root.querySelector("#staffRetentionResign")?.addEventListener("click", () => resolveStaffRetention("re_sign"));
    root.querySelector("#staffRetentionInterim")?.addEventListener("click", () => resolveStaffRetention("interim"));
    root.querySelectorAll("[data-retention-candidate]").forEach((button) => {
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
  if (!document.querySelector('[data-event-rotator], [data-summary-leader-rotator], [data-market-rotator]')) return;
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
  const acquiring = Boolean(state.tradeFinderTargetTeam);
  const scope = acquiring ? state.tradeFinderTargetTeam : state.tradeFinderScope || "";
  const partnerOptions = state.teams
    .filter((team) => team.abbrev !== user && (finder || !(state.tradeAdditionalTeams || []).includes(team.abbrev)))
    .map((team) => `<option value="${escapeAttr(team.abbrev)}" ${team.abbrev === (finder ? scope : state.tradePartner) ? "selected" : ""}>${escapeHtml(team.abbrev)} ${escapeHtml(team.name || "")}</option>`)
    .join("");
  return `
    <div class="trade-room-toolbar">
      <div class="trade-room-mode">
        <div class="tabs" aria-label="Trade tools">
          <button data-trade-tab="builder" aria-pressed="${!finder}" class="${!finder ? "active" : ""}">Trade Builder</button>
          <button data-trade-tab="finder" aria-pressed="${finder}" class="${finder ? "active" : ""}">Trade Finder</button>
        </div>
        ${!finder && state.tradeWorkspaceDrafts?.finder ? '<button type="button" data-back-finder>Back to results</button>' : ""}
      </div>
      ${finder ? `
        <label class="trade-finder-mode"><span>Find a deal to</span><select id="tradeFinderMode" aria-label="Trade Finder mode"><option value="shop" ${!acquiring ? "selected" : ""}>Shop my assets</option><option value="acquire" ${acquiring ? "selected" : ""}>Acquire another team's assets</option></select></label>
        <div class="trade-partner-navigation">
          ${scope && teamLogoSrc(scope) ? `<img src="${escapeAttr(teamLogoSrc(scope))}" alt="${escapeAttr(scope)} logo" />` : ""}
          <button type="button" data-trade-team-step="-1" aria-label="Previous Trade Finder team">‹</button>
          <label class="trade-partner-field" for="tradeFinderTeam"><span>${acquiring ? "Target team" : "Search teams"}</span><select id="tradeFinderTeam">${!acquiring ? `<option value="" ${!scope ? "selected" : ""}>All ${state.teams.length - 1} teams</option>` : ""}${partnerOptions}</select></label>
          <button type="button" data-trade-team-step="1" aria-label="Next Trade Finder team">›</button>
        </div>` : `
        <div class="trade-partner-navigation">
          ${teamLogoSrc(state.tradePartner) ? `<img src="${escapeAttr(teamLogoSrc(state.tradePartner))}" alt="${escapeAttr(state.tradePartner)} logo" />` : ""}
          <button type="button" data-trade-team-step="-1" aria-label="Previous trade partner">‹</button>
        <label class="trade-partner-field" for="tradePartner">
          <span>Trade partner</span>
          <select id="tradePartner">${partnerOptions}</select>
        </label><button type="button" data-trade-team-step="1" aria-label="Next trade partner">›</button></div>
        <div class="trade-add-participant"><select id="tradeAddTeam" aria-label="Additional trade team"><option value="">Add team</option>${state.teams.filter(team => team.abbrev !== user && team.abbrev !== state.tradePartner && !(state.tradeAdditionalTeams || []).includes(team.abbrev)).map(team => `<option value="${escapeAttr(team.abbrev)}">${escapeHtml(team.abbrev)} ${escapeHtml(team.name || "")}</option>`).join("")}</select><button type="button" class="ui-command trade-icon-button" data-trade-add-team aria-label="Add team to trade" title="Add team" ${(state.tradeAdditionalTeams || []).length >= 4 ? "disabled" : ""}><img src="/assets/window-icons/plus.svg" alt=""></button></div>`}
    </div>
    <div id="tradeBody"></div>`;
}

async function openTradeRoomModal(tab = state.tradeTab || "builder", options = {}) {
  if (state.tradeAdditionalSave !== state.currentSave) {
    state.tradeAdditionalSave = state.currentSave;
    state.tradeAdditionalTeams = [];
    state.tradeExtraSelections = {};
    state.tradeAssetRoutes = {};
    state.tradePickRules = [];
    state.data.tradeAdditionalAssets = {};
  }
  if (!["trades", "draft_trades"].some(action => clipboardLegalActions().has(action))) {
    showToast("Trading is unavailable during this phase.", true);
    return;
  }
  if (state.tradeTab !== tab) {
    rememberTradeWorkspace();
    restoreTradeWorkspace(tab);
  }
  state.tradeTab = tab;
  if (options.targetTeam || options.targetPlayerId || options.targetPickId) {
    state.tradeFinderTargetTeam = options.targetTeam && teamLabel(options.targetTeam) !== userTeam() ? teamLabel(options.targetTeam) : null;
    if (state.tradeFinderTargetTeam) state.tradePartner = state.tradeFinderTargetTeam;
    state.tradeResults = [];
    state.tradeSearchCompleted = false;
    state.selectedFrom = [];
    state.selectedTo = [];
  }
  syncDefaultPartner();
  if (!(await loadTradeRoomAssets())) return;
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

function rememberTradeWorkspace() {
  state.tradeWorkspaceDrafts ||= {};
  state.tradeWorkspaceDrafts[state.tradeTab] = {
    save: state.currentSave,
    partner: state.tradePartner,
    selectedFrom: [...state.selectedFrom], selectedTo: [...state.selectedTo],
    additionalTeams:[...(state.tradeAdditionalTeams || [])],
    extraSelections:Object.fromEntries(Object.entries(state.tradeExtraSelections || {}).map(([team,items]) => [team,[...items]])),
    assetRoutes:{...(state.tradeAssetRoutes || {})}, rosterSide:state.tradeRosterSide,
    candidate: state.tradeCandidate,
    pickRules:(state.tradePickRules || []).map(rule=>({...rule,fallback_pick_ids:[...(rule.fallback_pick_ids || [])]})),
    targetTeam: state.tradeFinderTargetTeam || null,
    scope: state.tradeFinderScope || "",
    results: state.tradeResults, searchCompleted: state.tradeSearchCompleted,
    resultScroll: els.modalRoot?.querySelector("#tradeResults")?.scrollTop || 0,
  };
}

function restoreTradeWorkspace(tab) {
  const stored = state.tradeWorkspaceDrafts?.[tab];
  const draft = stored?.save === state.currentSave ? stored : null;
  state.tradeAdditionalTeams = tab === "builder" ? [...(draft?.additionalTeams || [])] : [];
  state.tradeExtraSelections = tab === "builder" ? Object.fromEntries(Object.entries(draft?.extraSelections || {}).map(([team,items]) => [team,[...items]])) : {};
  state.tradeAssetRoutes = tab === "builder" ? {...(draft?.assetRoutes || {})} : {};
  state.tradeRosterSide = tab === "builder" ? draft?.rosterSide || "from" : "from";
  state.tradePickRules = (draft?.pickRules || state.tradePickRules || []).map(rule=>({...rule,fallback_pick_ids:[...(rule.fallback_pick_ids || [])]}));
  if (!draft) {
    state.tradeCandidate = null;
    if (tab === "finder") {
      state.tradeFinderTargetTeam = null;
      state.tradeFinderScope = "";
      if (state.selectedFrom.length > 2) {
        state.selectedFrom = state.selectedFrom.slice(0, 2);
        showToast("Trade Finder starts with the first two selected assets. Your full builder package is saved.");
      }
      state.selectedTo = [];
      state.tradeResults = [];
      state.tradeSearchCompleted = false;
    }
    return;
  }
  state.tradePartner = draft.partner;
  state.selectedFrom = [...draft.selectedFrom];
  state.selectedTo = [...draft.selectedTo];
  state.tradeCandidate = draft.candidate;
  if (tab === "finder") {
    state.tradeFinderTargetTeam = draft.targetTeam;
    state.tradeFinderScope = draft.scope;
    state.tradeResults = draft.results;
    state.tradeSearchCompleted = draft.searchCompleted;
  }
}

async function loadTradeRoomAssets() {
  const save = state.currentSave;
  const partner = state.tradePartner;
  const payload = savePayload();
  const [userAssets, partnerAssets] = await Promise.all([
    action("team_assets", { ...payload, team: userTeam() }),
    action("team_assets", { ...payload, team: partner }),
  ]);
  if (save !== state.currentSave || partner !== state.tradePartner) return false;
  state.data.tradeUser = userAssets;
  state.data.tradePartner = partnerAssets;
  const currentAssets = (items, payload) => items.map(item => (payload.assets || []).find(asset => asset.kind === item.kind && asset.id === item.id)).filter(Boolean);
  state.selectedFrom = currentAssets(state.selectedFrom, userAssets);
  state.selectedTo = currentAssets(state.selectedTo, partnerAssets);
  for (const team of state.tradeAdditionalTeams || []) {
    const extra = await action("team_assets", {...payload,team});
    if (save !== state.currentSave || partner !== state.tradePartner) return false;
    state.data.tradeAdditionalAssets ||= {};
    state.data.tradeAdditionalAssets[team] = extra;
    state.tradeExtraSelections ||= {};
    state.tradeExtraSelections[team] = currentAssets(state.tradeExtraSelections[team] || [],extra);
  }
  pruneTradePickRules();
  return true;
}

async function switchTradeWorkspace(tab) {
  if (tab === state.tradeTab) return;
  const loadedPartner = state.tradePartner;
  rememberTradeWorkspace();
  restoreTradeWorkspace(tab);
  state.tradeTab = tab;
  if (loadedPartner !== state.tradePartner || !state.data.tradeUser || !state.data.tradePartner) {
    state.data.tradePartner = {};
    renderTradeRoom();
    if (!(await loadTradeRoomAssets())) return;
  }
  renderTradeRoom();
  if (tab === "finder") {
    const results = els.modalRoot?.querySelector("#tradeResults");
    if (results) results.scrollTop = state.tradeWorkspaceDrafts?.finder?.resultScroll || 0;
  }
}

async function setTradeWorkspaceTeam(team) {
  if (state.tradeTab === "builder" && (state.tradeAdditionalTeams || []).includes(team)) return showToast("That team is already in this trade.",true);
  if (state.tradeTab === "finder" && !state.tradeFinderTargetTeam) {
    const searched = state.tradeSearchCompleted;
    state.tradeFinderScope = team;
    state.tradeResults = [];
    state.tradeSearchCompleted = false;
    if (team && (state.tradePickRules || []).length) {
      const save = state.currentSave;
      const payload = await action('team_assets',{...savePayload(),team});
      if (save !== state.currentSave || team !== state.tradeFinderScope) return;
      state.data.tradeRuleCounterparty = {team,payload};
    }
    renderTradeRoom();
    if (searched && state.selectedFrom.length) await runTradeSearch();
    return;
  }
  state.tradePartner = team;
  if (state.tradeTab === "finder") {
    state.tradeFinderTargetTeam = team;
    state.tradeResults = [];
    state.tradeSearchCompleted = false;
  }
  state.selectedTo = [];
  state.tradeCandidate = null;
  state.data.tradePartner = {};
  renderTradeRoom();
  if (!(await loadTradeRoomAssets())) return;
  renderTradeRoom();
}

async function stepTradeWorkspaceTeam(direction) {
  const finderShop = state.tradeTab === "finder" && !state.tradeFinderTargetTeam;
  const teams = state.teams.filter(team => team.abbrev !== userTeam() && (state.tradeTab !== "builder" || !(state.tradeAdditionalTeams || []).includes(team.abbrev))).map(team => team.abbrev);
  const choices = finderShop ? ["", ...teams] : teams;
  if (!choices.length) return;
  const current = finderShop ? state.tradeFinderScope || "" : state.tradePartner;
  const index = Math.max(0, choices.indexOf(current));
  await setTradeWorkspaceTeam(choices[(index + direction + choices.length) % choices.length]);
}

function renderTradeRoom() {
  if (state.modal?.kind !== "tradeRoom") return;
  const scroll = [...(els.modalRoot?.querySelectorAll?.("[data-trade-scroll], .modal-body") || [])].map(node => [node.dataset.tradeScroll || "modal", node.scrollTop, node.scrollLeft]);
  const focused = typeof document !== "undefined" ? document.activeElement : null;
  const focusAsset = focused?.dataset?.assetId;
  const focusSide = focused?.dataset?.assetSide;
  const focusRule = focused?.dataset?.pickKey;
  const focusRuleField = focused?.dataset?.pickField;
  state.modal = {
    ...state.modal,
    body: tradeRoomModalBody(),
  };
  renderModal();
  for (const [key, top, left] of scroll) {
    const node = [...(els.modalRoot?.querySelectorAll?.("[data-trade-scroll], .modal-body") || [])].find(item => (item.dataset.tradeScroll || "modal") === key);
    if (node) { node.scrollTop = top; node.scrollLeft = left; }
  }
  if (focusAsset && focusSide) [...(els.modalRoot?.querySelectorAll?.("[data-asset-side]") || [])].find(node => node.dataset.assetId === focusAsset && node.dataset.assetSide === focusSide)?.focus({preventScroll:true});
  if (focusRule && focusRuleField) [...(els.modalRoot?.querySelectorAll?.('[data-pick-key]') || [])].find(node=>node.dataset.pickKey===focusRule && node.dataset.pickField===focusRuleField)?.focus({preventScroll:true});
}

function wireTradeRoom() {
  const root = els.modalRoot;
  const partner = root.querySelector("#tradePartner");
  const handle = task => Promise.resolve(task).catch(error => showToast(error.message || String(error), true));
  root.querySelector("[data-trade-add-team]")?.addEventListener("click", () => handle(addTradeParticipant(root.querySelector("#tradeAddTeam")?.value)));
  partner?.addEventListener("change", event => handle(setTradeWorkspaceTeam(event.target.value)));
  root.querySelector("#tradeFinderTeam")?.addEventListener("change", event => handle(setTradeWorkspaceTeam(event.target.value)));
  root.querySelectorAll("[data-trade-team-step]").forEach(button => button.addEventListener("click", () => handle(stepTradeWorkspaceTeam(Number(button.dataset.tradeTeamStep)))));
  root.querySelectorAll("[data-trade-roster-side]").forEach(button => button.addEventListener("click", () => {
    state.tradeRosterSide = button.dataset.tradeRosterSide;
    renderTradeRoom();
  }));
  root.querySelector("[data-back-finder]")?.addEventListener("click", () => handle(switchTradeWorkspace("finder")));
  root.querySelector("#tradeFinderMode")?.addEventListener("change", event => handle((async () => {
    if (event.target.value === "acquire") {
      state.tradeFinderShopSelection = [...state.selectedFrom];
      state.tradeFinderTargetTeam = state.tradePartner;
      state.selectedTo = [];
      await loadTradeRoomAssets();
    } else {
      state.tradeFinderTargetTeam = null;
      state.selectedFrom = [...(state.tradeFinderShopSelection || state.selectedFrom)];
      state.selectedTo = [];
    }
    state.tradeResults = [];
    state.tradeSearchCompleted = false;
    pruneTradePickRules();
    renderTradeRoom();
  })()));
  root.querySelector(".tabs")?.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-trade-tab]");
    if (!button) return;
    handle(switchTradeWorkspace(button.dataset.tradeTab));
  });
  if (state.tradeTab === "finder") renderTradeFinder(root);
  else renderTradeBuilder(root);
}

function renderTradeBuilder(root) {
  const body = root.querySelector("#tradeBody");
  if (!body) return;
  const userAssets = state.data.tradeUser || {};
  const partnerAssets = state.data.tradePartner || {};
  const participants = tradeWorkspaceParticipants();
  const multi = participants.length > 2;
  const current = participants.find(team => team.side === state.tradeRosterSide) || participants[0];
  const side = current.side;
  const page = Math.max(0, Math.min(3, Number(state.tradeInsightPage || 0)));
  body.innerHTML = `
    <div class="trade-builder-layout">
      ${page === 0 ? `<div class="trade-roster-switch" aria-label="Team asset lists">
        ${participants.map(({side:key,team,selected:items}) => `<span class="trade-participant-tab"><button type="button" data-trade-roster-side="${escapeAttr(key)}" aria-pressed="${side === key}">${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="" />` : ""}<strong>${escapeHtml(team)}</strong><span>${items.length} selected</span></button>${key.startsWith("extra:") ? `<button type="button" class="trade-icon-button" data-trade-remove-team="${escapeAttr(team)}" aria-label="Remove ${escapeAttr(team)} from trade" title="Remove team"><img src="/assets/window-icons/x.svg" alt=""></button>` : ""}</span>`).join("")}
      </div>
      ${assetColumn(`${current.team} assets`,current.payload,side,current.team)}` : `<div class="trade-package-brief">${participants.map(({team,selected:items}) => `<section><strong>${escapeHtml(team)} sends</strong><span>${items.length ? items.slice(0,3).map(item => escapeHtml(item.name || item.label)).join(", ") + (items.length > 3 ? ` + ${items.length-3} assets` : "") : "No assets selected"}</span></section>`).join("")}<button type="button" class="ui-command" data-trade-edit-package>Edit package</button></div>`}
      <section class="trade-deal-desk approved-trade-desk">
        ${tradeInsightPager(["Package", "Value", "Payroll", "Team identity"], page, "builder")}
        <div class="trade-insight-page" data-trade-page="${page}">
        ${page === 0 ? `<div class="trade-selected-packages">
          ${participants.map(({team,side,selected,payload}) => selectedPackage(`${team} sends`,selected,side,team,payload)).join("")}
        </div>${tradePickTermsMarkup()}` : page === 1 ? multi ? tradeMultiValuePreview(participants) : `<div class="trade-team-decisions">${(state.tradeCandidate?.evaluations || []).map(tradeEvaluationPanel).join("")}</div>${tradeSegmentedValueBoard(state.tradeCandidate, state.selectedFrom, state.selectedTo, userTeam(), state.tradePartner)}` : page === 2 ? tradeFourYearImplications(userAssets, partnerAssets, state.selectedFrom, state.selectedTo,participants) : tradeIdentityPage()}
        </div>
        <div class="trade-decision-dock"><div id="tradeRead">${tradeReadout(state.tradeCandidate)}</div><button id="evaluateTrade" class="trade-evaluate-button ui-command" ${tradePickRuleErrors().length || !participants.some(row => row.selected.length) ? "disabled" : ""}>Evaluate package</button></div>
      </section>
    </div>`;
  body.querySelectorAll("[data-trade-roster-side]").forEach(button => button.addEventListener("click", () => { state.tradeRosterSide = button.dataset.tradeRosterSide; renderTradeRoom(); }));
  body.querySelectorAll("[data-trade-remove-team]").forEach(button => button.addEventListener("click", () => removeTradeParticipant(button.dataset.tradeRemoveTeam)));
  wireTradeInsightPagers(body);
  body.querySelector("[data-trade-edit-package]")?.addEventListener("click", () => { state.tradeInsightPage = 0; renderTradeRoom(); });
  body.querySelectorAll("[data-trade-identity-team]").forEach(button => button.addEventListener("click", () => { state.tradeIdentityTeam = button.dataset.tradeIdentityTeam; renderTradeRoom(); }));
  body.querySelector("[data-trade-identity-retry]")?.addEventListener("click", () => loadTradeIdentity(true));
  if (page === 3) loadTradeIdentity().catch(error => showToast(error.message, true));
  wireTradeAssetControls(body);
  body.querySelector("#evaluateTrade").addEventListener("click", () => evaluateBuiltTrade().catch(error => showToast(error.message || String(error), true)));
  const applyButton = body.querySelector("#applyBuiltTrade");
  if (applyButton) applyButton.addEventListener("click", () => applyCandidate(state.tradeCandidate, "builder").catch(error => showToast(error.message || String(error), true)));
  body.querySelectorAll("[data-trade-team-roster]").forEach((button) => button.addEventListener("click", () => openTeamRosterCard(button.dataset.tradeTeamRoster)));
  wireDashboardPlayerCards(body);
}

function tradePickParticipants() {
  if (state.tradeTab !== 'finder') return tradeWorkspaceParticipants().map(row=>({...row,receiverFor:asset=>tradeAssetDestination(row.team,asset)}));
  const target=state.tradeFinderTargetTeam, owner=target || userTeam(), other=target?userTeam():state.tradeFinderScope;
  const payload=state.data[target?'tradePartner':'tradeUser'] || {};
  const otherPayload=target?state.data.tradeUser:state.data.tradeRuleCounterparty?.team===other?state.data.tradeRuleCounterparty?.payload:other===state.tradePartner?state.data.tradePartner:{};
  return [{team:owner,payload,selected:target?state.selectedTo:state.selectedFrom,recipient:other},
    ...(other?[{team:other,payload:otherPayload || {},selected:[],recipient:owner}]:[])];
}

function tradePickTermsMarkup() { return globalThis.TradePickTerms?.markup(tradePickParticipants(),state.tradePickRules || []) || ''; }
function tradePickRuleErrors() { return globalThis.TradePickTerms?.errors(state.tradePickRules || [],tradePickParticipants()) || []; }
function tradePickRulesRequest() { return globalThis.TradePickTerms?.request(state.tradePickRules || []) || []; }
function pruneTradePickRules() {
  if (globalThis.TradePickTerms) state.tradePickRules=TradePickTerms.prune(state.tradePickRules || [],tradePickParticipants());
}
function wireTradePickTerms(root) {
  globalThis.TradePickTerms?.wire(root,tradePickParticipants(),state.tradePickRules || [],(rules,focus)=>{
    state.tradePickRules=rules;
    state.tradeCandidate=null;
    state.tradeResults=[];
    state.tradeSearchCompleted=false;
    renderTradeRoom();
    if (focus) {
      const control=focus.add?els.modalRoot.querySelector('[data-pick-add]'):[...els.modalRoot.querySelectorAll('[data-pick-key]')].find(n=>n.dataset.pickKey===focus.key && n.dataset.pickField===focus.field);
      control?.focus({preventScroll:true});
    }
    loadTradeRuleCounterparty().catch(error=>showToast(error.message,true));
  });
}

async function loadTradeRuleCounterparty() {
  const team=state.tradeFinderScope, save=state.currentSave;
  if (state.tradeTab!=='finder' || state.tradeFinderTargetTeam || !team || state.data.tradeRuleCounterparty?.team===team) return;
  const payload=await action('team_assets',{...savePayload(),team});
  if (save!==state.currentSave || team!==state.tradeFinderScope || state.tradeTab!=='finder') return;
  state.data.tradeRuleCounterparty={team,payload};
  renderTradeRoom();
}

function tradeWorkspaceParticipants() {
  return [
    {team:userTeam(),side:"from",payload:state.data.tradeUser || {},selected:state.selectedFrom},
    {team:state.tradePartner,side:"to",payload:state.data.tradePartner || {},selected:state.selectedTo},
    ...(state.tradeAdditionalTeams || []).map(team => ({team,side:`extra:${team}`,payload:state.data.tradeAdditionalAssets?.[team] || {},selected:state.tradeExtraSelections?.[team] || []})),
  ];
}

function tradeRouteKey(owner, asset) { return `${owner}:${asset.kind}:${asset.id}`; }

function tradeAssetDestination(owner, asset, participants = tradeWorkspaceParticipants()) {
  const destination = state.tradeAssetRoutes?.[tradeRouteKey(owner,asset)];
  const others = participants.filter(row => row.team !== owner);
  if (others.some(row => row.team === destination)) return destination;
  const normal = owner === userTeam() ? state.tradePartner : userTeam();
  return others.find(row => row.team === normal)?.team || others[0]?.team || "";
}

function tradeReceivedAssets(team, participants = tradeWorkspaceParticipants()) {
  return participants.flatMap(sender => sender.team === team ? [] : sender.selected.filter(asset => tradeAssetDestination(sender.team,asset,participants) === team));
}

function tradeSidePayload(side) {
  if (side === "from") return state.data.tradeUser || {};
  if (side === "to") return state.data.tradePartner || {};
  return state.data.tradeAdditionalAssets?.[String(side).replace(/^extra:/,"")] || {};
}

async function addTradeParticipant(team) {
  if (!team || !state.teams.some(row => row.abbrev === team)) return;
  if (tradeWorkspaceParticipants().some(row => row.team === team)) return showToast("That team is already in this trade.",true);
  if ((state.tradeAdditionalTeams || []).length >= 4) return;
  const save = state.currentSave;
  const payload = await action("team_assets", {...savePayload(),team});
  if (save !== state.currentSave || state.tradeTab !== "builder" || (state.tradeAdditionalTeams || []).length >= 4 || tradeWorkspaceParticipants().some(row => row.team === team)) return;
  state.tradeAdditionalTeams ||= [];
  state.tradeAdditionalTeams.push(team);
  state.tradeExtraSelections ||= {};
  state.tradeExtraSelections[team] = [];
  state.data.tradeAdditionalAssets ||= {};
  state.data.tradeAdditionalAssets[team] = payload;
  state.tradeRosterSide = `extra:${team}`;
  state.tradeCandidate = null;
  state.tradeIdentityPreview = null;
  renderTradeRoom();
}

function removeTradeParticipant(team) {
  if (!(state.tradeAdditionalTeams || []).includes(team)) return;
  let resetDestination = false;
  state.tradeAdditionalTeams = (state.tradeAdditionalTeams || []).filter(item => item !== team);
  if (state.tradeExtraSelections) delete state.tradeExtraSelections[team];
  for (const [key,destination] of Object.entries(state.tradeAssetRoutes || {})) {
    if (destination === team) resetDestination = true;
    if (key.startsWith(`${team}:`) || destination === team) delete state.tradeAssetRoutes[key];
  }
  if (state.tradeRosterSide === `extra:${team}`) state.tradeRosterSide = "from";
  pruneTradePickRules();
  state.tradeCandidate = null;
  state.tradeIdentityPreview = null;
  renderTradeRoom();
  if (resetDestination) showToast(`${team} removed; affected destinations reset.`);
}

function tradeMultiValuePreview(participants) {
  const totals = participants.map(row => ({...row,receives:tradeReceivedAssets(row.team,participants)}));
  const maximum = Math.max(1,...totals.flatMap(row => [selectedTradeValue(row.selected),selectedTradeValue(row.receives)]));
  return `<div class="trade-team-decisions">${(state.tradeCandidate?.evaluations || []).map(tradeEvaluationPanel).join("")}</div><section class="trade-multi-value"><header>Listed asset values</header>${totals.map(row => {
    const sent=selectedTradeValue(row.selected),received=selectedTradeValue(row.receives),delta=received-sent;
    return `<section><h4>${escapeHtml(row.team)}</h4><div class="trade-multi-value-flow"><span>Sends ${sent.toFixed(1)}</span><i aria-label="Outgoing listed value"><b style="width:${sent/maximum*100}%"></b></i><span>Receives ${received.toFixed(1)}</span><i class="receives" aria-label="Incoming listed value"><b style="width:${received/maximum*100}%"></b></i><strong>${delta>=0?"+":""}${delta.toFixed(1)} listed value change</strong></div></section>`;
  }).join("")}</section>`;
}

function tradeTeamHeading(team, payload) {
  const record = payload.record || {};
  const wins = Number(record.wins || 0);
  const losses = Number(record.losses || 0);
  return `<button type="button" class="approved-trade-team" data-trade-team-roster="${escapeAttr(team)}">${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)} logo" />` : ""}<span><strong>${escapeHtml(team)}</strong><small>${wins}-${losses} · ${record.conference_rank ? `#${escapeHtml(record.conference_rank)} conference` : "season record"}</small></span></button>`;
}

function tradeSegmentedValueBoard(candidate, outgoing, incoming, outgoingTeam, incomingTeam) {
  const breakdown = candidate?.value_breakdown || {};
  const archived = Object.keys(breakdown).length && breakdown.version !== 2;
  const normalized = (row, fallback) => row?.asset_details?.length
    ? row.asset_details
    : fallback.map((asset) => ({
        id: asset.id,
        label: asset.label || asset.id,
        adjusted_value: Number(asset.trade_value || 0),
        components: { asset_value: Number(asset.trade_value || 0) },
      }));
  const rows = [
    [outgoingTeam, normalized(breakdown.to_team_receives, outgoing), incomingTeam, breakdown.to_team_receives],
    [incomingTeam, normalized(breakdown.from_team_receives, incoming), outgoingTeam, breakdown.from_team_receives],
  ];
  const all = rows.flatMap(([, details]) => details);
  const maximum = Math.max(1, ...all.map((asset) => Math.max(
    Object.values(asset.components || {}).filter((value) => Number(value) > 0).reduce((sum, value) => sum + Number(value), 0),
    Object.values(asset.components || {}).filter((value) => Number(value) < 0).reduce((sum, value) => sum + Math.abs(Number(value)), 0),
  )), ...rows.map(([, details]) => Math.abs(details.reduce((sum, asset) => sum + Number(asset.adjusted_value || 0), 0))));
  const labels = { quality: "Quality", age_upside: "Age and growth value", contract: "Contract", scarcity: "Scarcity", playoffs: "Playoffs", health: "Health", fit: "Fit", role: "Projected role", retention: "Recent acquisition", draft_capital: "Draft capital", swap_value: "Swap value", asset_value: "Asset value" };
  const explanations = {quality:"Current on-court contribution.",age_upside:"Age curve and remaining development; older players can have a negative age adjustment even with no upside remaining.",contract:"Salary value relative to contribution, not salary in dollars.",scarcity:"How difficult this skill set is to replace.",playoffs:"Contribution expected to translate to playoff basketball.",health:"Injury risk reduces value.",fit:"Fit with this team's needs.",role:"Change from the listed value for the projected role after outgoing players leave. Fewer usable minutes can mean a large reduction; this is not a ratings penalty.",retention:"Extra cost of moving a recently acquired player.",draft_capital:"Pick value including year, projected position and protections.",swap_value:"Value of the swap right, not ownership of an extra pick."};
  const bar = (components) => {
    const entries = Object.entries(components || {}).filter(([, value]) => Math.abs(Number(value)) >= 0.005);
    const positive = entries.filter(([, value]) => Number(value) > 0);
    const negative = entries.filter(([, value]) => Number(value) < 0).reverse();
    return `<div class="trade-value-diverging"><span class="negative-side">${negative.map(([key, value]) => `<i class="value-${escapeAttr(key)}" style="width:${clampNumber(Math.abs(Number(value)) / maximum * 100, 0, 100)}%" title="${escapeAttr(`${labels[key] || rowLabel(key)} ${Number(value).toFixed(1)}`)}"></i>`).join("")}</span><b></b><span class="positive-side">${positive.map(([key, value]) => `<i class="value-${escapeAttr(key)}" style="width:${clampNumber(Number(value) / maximum * 100, 0, 100)}%" title="${escapeAttr(`${labels[key] || rowLabel(key)} +${Number(value).toFixed(1)}`)}"></i>`).join("")}</span></div>`;
  };
  const componentKeys = [...new Set(all.flatMap((asset) => Object.keys(asset.components || {})))];
  return `<section class="approved-trade-values"><header>${archived ? 'Archived asset estimates' : 'Receiving-team asset values'}</header>${archived ? '<p class="trade-value-help">This saved offer uses the older chart calculation. Review it in the builder and evaluate again for corrected totals; these archived bars are not the decision ledger.</p>' : ''}<details class="trade-value-help"><summary>What changes the listed value?</summary><p>Listed value is a market reference, not OVR or dollars. These bars show value to the receiving team: right adds value, left subtracts it. Age, upside, contract and health are already included in the reference value; the colored segments explain that value, not extra bonuses. Projected role and fit depend on the destination roster. Package adjustment discounts a bundle of depth relative to a concentrated return. Strategy is separate, so this total is not an acceptance score.</p></details>${rows.map(([team, details, destination, pack]) => {
    const subtotal = details.reduce((sum, asset) => sum + Number(asset.adjusted_value || 0), 0);
    const net = pack?.total == null ? subtotal : Number(pack.total);
    const adjustment = net-subtotal;
    return `<div class="trade-value-team"><strong>${escapeHtml(team)} sends · valued by ${escapeHtml(destination)}</strong>${details.length ? details.map((asset) => `<div class="approved-value-row" title="${escapeAttr(`${asset.listed_value == null ? '' : `Listed ${Number(asset.listed_value).toFixed(1)} · `}${asset.expected_role || ''}`)}"><span>${escapeHtml(asset.label || asset.id)}</span>${bar(asset.components)}<em>${Number(asset.adjusted_value || 0).toFixed(1)}</em></div>`).join("") : `<div class="trade-value-empty">No assets selected</div>`}${Math.abs(adjustment)>.05 ? `<div class="approved-value-row"><span>Package adjustment</span>${bar({asset_value:adjustment})}<em>${adjustment.toFixed(1)}</em></div>` : ''}<div class="approved-value-row net"><span>Roster value</span>${bar({ asset_value: net })}<em>${net.toFixed(1)}</em></div></div>`;
  }).join("")}<footer>${componentKeys.map((key) => `<span class="value-${escapeAttr(key)}" title="${escapeAttr(explanations[key] || labels[key] || rowLabel(key))}">${escapeHtml(labels[key] || rowLabel(key))}</span>`).join("")}</footer><details class="trade-value-help"><summary>Value components</summary><dl>${componentKeys.filter(key=>explanations[key]).map(key=>`<div><dt>${escapeHtml(labels[key])}</dt><dd>${escapeHtml(explanations[key])}</dd></div>`).join('')}</dl></details></section>`;
}

function tradeCapImpactRows(payload, receives, sends, seasons) {
  const salaryDelta = (season) => receives.reduce((sum, item) => sum + Number(item.salary_by_year?.[season] || 0), 0) - sends.reduce((sum, item) => sum + Number(item.salary_by_year?.[season] || 0), 0);
  const knownSalaries = [...receives,...sends].every(item => item.kind !== "player" || Object.keys(item.salary_by_year || {}).length > 0);
  return seasons.map((season) => {
    const cap = payload.cap_by_year?.[season] || {};
    const delta = knownSalaries ? salaryDelta(season) : null;
    return {
      season,
      delta,
      payroll: cap.salary_total_millions == null || delta === null ? null : Number(cap.salary_total_millions) + delta,
      players: !payload.players ? null : payload.players.length + receives.filter((item) => item.kind === "player").length - sends.filter((item) => item.kind === "player").length,
      tax: cap.tax_space_millions == null || delta === null ? null : Number(cap.tax_space_millions) - delta,
      hard: cap.hard_cap_space_millions == null || delta === null ? null : Number(cap.hard_cap_space_millions) - delta,
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
  return `<div class="approved-trade-cap-team"><strong>${escapeHtml(team)}</strong>${tradeCapDeltaChart(rows)}<table><thead><tr><th>Year</th><th>Payroll</th><th>Players</th><th>Tax room</th><th>Hard-cap room</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${escapeHtml(shortSeasonLabel(row.season))}</td><td>${row.payroll === null ? "—" : money(row.payroll)} <small class="${row.delta > 0 ? "negative" : row.delta < 0 ? "positive" : ""}">${row.delta ? `${row.delta > 0 ? "+" : "−"}${money(Math.abs(row.delta))}` : ""}</small></td><td>${row.players ?? "—"}</td><td class="${row.tax < 0 ? "negative" : "positive"}">${row.tax === null ? "—" : signedMoney(row.tax)}</td><td class="${row.hard < 0 ? "negative" : "positive"}">${row.hard === null ? "—" : signedMoney(row.hard)}</td></tr>`).join("")}</tbody></table></div>`;
}

function tradeFourYearImplications(userPayload, partnerPayload, outgoing, incoming, participants = null) {
  const seasons = [...new Set((participants || [{payload:userPayload},{payload:partnerPayload}]).flatMap(row => Object.keys(row.payload.cap_by_year || {})))].sort().slice(0, 4);
  const teams = participants ? participants.map(row => ({team:row.team,payload:row.payload,sends:row.selected,receives:tradeReceivedAssets(row.team,participants)})) : [
    {team:userTeam(),payload:userPayload,receives:incoming,sends:outgoing},
    {team:state.tradePartner,payload:partnerPayload,receives:outgoing,sends:incoming},
  ];
  teams.forEach(team => { team.after = tradeCapImpactRows(team.payload, team.receives, team.sends, seasons); });
  const colorPlayerIds = [...new Set(teams.flatMap(team => [...(team.payload.players || []),...team.receives.filter(asset => asset.kind === "player")].map(player => player.id)))].sort();
  const scaleMaximum = Math.max(1,...teams.flatMap(team => seasons.flatMap((season,index) => {
    const cap = team.payload.cap_by_year?.[season] || {};
    return [Number(cap.salary_total_millions || 0), Number(cap.tax_line_millions || 0), Number(cap.hard_cap_millions || 0), team.after[index].payroll || 0];
  }))) * 1.06;
  const charts = teams.map(({team,payload,receives,sends,after}) => [false,true].map(changed => {
    const removed = new Set(sends.filter(asset => asset.kind === "player").map(asset => asset.id));
    const roster = changed ? [...(payload.players || []).filter(player => !removed.has(player.id)), ...receives.filter(asset => asset.kind === "player")] : payload.players || [];
    const payroll = Object.fromEntries(seasons.map((season,index) => [season,changed ? after[index].payroll : payload.cap_by_year?.[season]?.salary_total_millions]));
    const known = seasons.length === 4 && Object.values(payroll).every(value => tradeKnownNumber(value) !== null);
    return `<section class="trade-payroll-frame"><header>${escapeHtml(team)} · ${changed ? "After" : "Before"}</header>${known ? salaryHorizonChart({seasons,rows:roster,capByYear:payload.cap_by_year || {},payrollByYear:payroll,scaleMaximum,colorPlayerIds}) : '<div class="trade-package-empty">Scheduled payroll unavailable</div>'}</section>`;
  }).join("")).join("");
  const ledger = teams.map(({team,after}) => `<section><h4>${escapeHtml(team)} after trade</h4><table><thead><tr><th>Year</th><th>Payroll</th><th>Change</th><th>Tax room</th><th>Hard-cap room</th></tr></thead><tbody>${after.map(row => `<tr><th>${escapeHtml(shortSeasonLabel(row.season))}</th><td>${row.payroll === null ? "—" : money(row.payroll)}</td><td class="${row.delta > 0 ? "negative" : "positive"}">${row.delta === null ? "—" : signedMoney(row.delta)}</td><td class="${row.tax < 0 ? "negative" : "positive"}">${row.tax === null ? "—" : signedMoney(row.tax)}</td><td class="${row.hard < 0 ? "negative" : "positive"}">${row.hard === null ? "—" : signedMoney(row.hard)}</td></tr>`).join("")}</tbody></table></section>`).join("");
  return `<section class="approved-trade-cap"><div class="trade-payroll-plots" tabindex="0" aria-label="Four-year payroll before and after trade">${charts}</div><div class="trade-payroll-ledgers">${ledger}</div></section>`;
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
  return `
    <section class="trade-asset-column" ${teamBrandStyle(team)}>
      <div class="trade-asset-head">
        <div class="trade-team-lockup">
          ${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="" />` : ""}
          <div><strong>${escapeHtml(title)}</strong><span>${allAssets.length} available assets</span></div>
        </div>
        <select data-asset-filter-side="${escapeAttr(side)}" aria-label="${escapeAttr(title)} filter">
          ${[["all", "All"], ["players", "Players"], ["picks", "Picks"], ["swaps", "Swaps"]].map(([value, label]) => `<option value="${value}" ${filter === value ? "selected" : ""}>${label}</option>`).join("")}
        </select>
      </div>
      ${tradeCapStrip(cap)}
      ${typeof tradeWantsStrip==='function'?tradeWantsStrip(payload):''}
      <div class="trade-asset-list scroll-list" data-trade-scroll="catalog-${escapeAttr(side)}" tabindex="0" aria-label="${escapeAttr(title)}">
        ${assets.length ? tradeAssetTable(assets, {side, label:title}) : `<div class="trade-list-empty">No ${filter === "all" ? "tradeable assets" : escapeHtml(filter)} available for ${escapeHtml(team)}.</div>`}
      </div>
    </section>`;
}

function assetButton(asset, side, maxValue = 100, team = "") {
  return tradeAssetRow(asset, {side});
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
  const capRows = targetMode
    ? tradeCapImpactRows(state.data.tradeUser || {}, selection, [], Object.keys(state.data.tradeUser?.cap_by_year || {}).sort().slice(0, 4))
    : tradeCapImpactRows(userAssets, [], selection, seasons);
  body.innerHTML = `
    <div class="trade-finder-layout">
      ${assetColumn(`${finderTeam} ${targetMode ? "target" : "available"} assets`, userAssets, side, finderTeam)}
      <div class="trade-finder-workspace">
        <section class="trade-finder-brief" ${teamBrandStyle(userTeam())}>
          <div class="trade-desk-head"><h3>${targetMode ? `Acquire from ${finderTeam}` : "Shop your assets"}</h3><span class="trade-selection-count">${selection.length}/2 selected</span></div>
          <div class="trade-finder-control-grid">
            ${selectedPackage(targetMode ? "Target Assets" : "Assets To Shop", selection, side, finderTeam)}
            <div class="trade-finder-cap"><header>${escapeHtml(userTeam())} salary ${targetMode ? "added if acquired" : "removed if moved"}</header>${tradeCapDeltaChart(capRows)}</div>
          </div>
          ${tradePickTermsMarkup()}
          <div class="trade-finder-actions"><span class="trade-finder-hint">${targetMode ? "Choose up to two targets; your GM will find a legal package." : `Choose up to two assets to shop to ${state.tradeFinderScope || "the league"}.`}</span><button id="runTrade" class="trade-evaluate-button ui-command" ${selection.length && !tradePickRuleErrors().length ? "" : "disabled"}>Find trades</button><button id="clearTradeMarket" class="trade-clear-button ui-command" ${selection.length || state.tradeResults.length ? "" : "disabled"}>Clear</button></div>
        </section>
        <section class="trade-finder-results">
          <div class="trade-results-head"><h3>Found trades ${!targetMode && state.tradeFinderScope ? `· ${escapeHtml(state.tradeFinderScope)}` : ""}</h3><span>${state.tradeResults.length} results</span></div>
          <div id="tradeResults" class="trade-results-list scroll-list" aria-live="polite">${tradeResultCards(state.tradeResults)}</div>
        </section>
      </div>
    </div>`;
  wireTradeAssetControls(body);
  wireTradeInsightPagers(body);
  body.querySelector("#runTrade").addEventListener("click", () => runTradeSearch().catch(error => showToast(error.message || String(error), true)));
  body.querySelector("#clearTradeMarket").addEventListener("click", () => {
    state.tradePickRules = [];
    state.selectedFrom = [];
    state.selectedTo = [];
    state.tradeResults = [];
    state.tradeSearchCompleted = false;
    renderTradeRoom();
  });
  body.querySelectorAll("[data-inspect-finder]").forEach((button) => {
    button.addEventListener("click", () => inspectFinderTrade(Number(button.dataset.inspectFinder)).catch(error => showToast(error.message || String(error), true)));
  });
  wireDashboardPlayerCards(body);
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
  rememberTradeWorkspace();
  const fromTeam = teamLabel(proposal.from_team_id || proposal.from_team || "");
  const toTeam = teamLabel(proposal.to_team_id || proposal.to_team || "");
  const userIsFrom = fromTeam === userTeam();
  const previousPartner = state.tradePartner;
  state.tradePartner = userIsFrom ? toTeam : fromTeam;
  if (previousPartner !== state.tradePartner || !state.data.tradePartner?.assets) await loadTradeRoomAssets();
  const originals = specs => (specs || []).map(spec=>{
    const term=(candidate.pick_obligation_terms || []).find(t=>t.id===(spec.id || spec.value) && t.pending_asset_grant);
    return term ? {kind:'pick',id:term.primary_pick_id || term.team_a_pick_id} : spec;
  });
  state.selectedFrom = hydrateTradeSelection(originals(userIsFrom ? proposal.from_assets : proposal.to_assets), state.data.tradeUser);
  state.selectedTo = hydrateTradeSelection(originals(userIsFrom ? proposal.to_assets : proposal.from_assets), state.data.tradePartner);
  state.tradePickRules = (candidate.ui_pick_rules || []).map((rule,i)=>({...rule,key:`condition-${i+1}`,enabled:true,fallback_pick_ids:[...(rule.fallback_pick_ids || [])]}));
  state.tradeCandidate = candidate;
  state.tradeTab = "builder";
  renderTradeRoom();
}

async function evaluateBuiltTrade() {
  if (!tradeWorkspaceParticipants().some(row => row.selected.length)) return showToast("Select at least one asset.", true);
  if (tradePickRuleErrors().length) return showToast(tradePickRuleErrors()[0].message,true);
  const save = state.currentSave, partner = state.tradePartner;
  const request = () => {
    if (!(state.tradeAdditionalTeams || []).length) return {from_team:userTeam(),to_team:state.tradePartner,
      from_assets:state.selectedFrom.map(assetSpec),to_assets:state.selectedTo.map(assetSpec),pick_rules:tradePickRulesRequest()};
    const transfers = [];
    for (const row of tradeWorkspaceParticipants()) for (const asset of row.selected) {
      const to = tradeAssetDestination(row.team,asset);
      let leg = transfers.find(leg => leg.from_team_id === row.team && leg.to_team_id === to);
      if (!leg) { leg = {from_team_id:row.team,to_team_id:to,assets:[]}; transfers.push(leg); }
      leg.assets.push(assetSpec(asset));
    }
    return {transfers,pick_rules:tradePickRulesRequest()};
  };
  const selectionKey = JSON.stringify(request());
  const result = await action("evaluate_trade", {
    ...savePayload(),
    ...request(),
    seed: 7,
  });
  if (save !== state.currentSave || partner !== state.tradePartner) return;
  if (selectionKey !== JSON.stringify(request())) return;
  result.headline = tradeHeadline(result);
  state.tradeCandidate = result;
  renderTradeRoom();
}

async function runTradeSearch() {
  const selection = state.tradeFinderTargetTeam ? state.selectedTo : state.selectedFrom;
  if (!selection.length) return showToast("Select at least one asset.", true);
  if (tradePickRuleErrors().length) return showToast(tradePickRuleErrors()[0].message,true);
  const save = state.currentSave, target = state.tradeFinderTargetTeam || null, scope = state.tradeFinderScope || "";
  const selectionKey = JSON.stringify([selection.map(asset => `${asset.kind}:${asset.id}`).sort(),tradePickRulesRequest()]);
  const data = await action("find_trade_for_assets", {
    ...savePayload(),
    seller_team: state.tradeFinderTargetTeam || userTeam(),
    for_team: userTeam(),
    buyer_team: state.tradeFinderTargetTeam ? undefined : state.tradeFinderScope || undefined,
    assets: selection.map(assetSpec),
    pick_rules:tradePickRulesRequest(),
    limit: 12,
    seed: 7,
  });
  if (save !== state.currentSave || target !== (state.tradeFinderTargetTeam || null) || scope !== (state.tradeFinderScope || "")) return;
  const currentSelection = state.tradeFinderTargetTeam ? state.selectedTo : state.selectedFrom;
  if (selectionKey !== JSON.stringify([currentSelection.map(asset => `${asset.kind}:${asset.id}`).sort(),tradePickRulesRequest()])) return;
  state.tradeResults = data.candidates || data.offers || [];
  state.tradeSearchCompleted = true;
  renderTradeRoom();
}

async function applyCandidate(candidate, source) {
  if (!candidate) return;
  if (state.tradeTab === 'builder' && (state.tradeAdditionalTeams || []).length && !candidate.proposal?.transfers) {
    return showToast('Evaluate the complete multi-team package before submitting.',true);
  }
  const save = state.currentSave;
  const result = await action("apply_trade_candidate", { ...savePayload(), candidate, source });
  if (save !== state.currentSave) return;
  if (result.status !== "applied") {
    showToast(result.notes || result.result?.notes || `Trade not completed: ${rowLabel(result.status)}`, true);
    return;
  }
  showToast("Trade completed");
  tradeResponseEffect("accepted");
  state.selectedFrom = [];
  state.selectedTo = [];
  state.tradeExtraSelections = {};
  state.tradeAssetRoutes = {};
  state.tradeCandidate = null;
  state.tradeIdentityPreview = null;
  state.tradeResults = [];
  state.tradeSearchCompleted = false;
  state.tradeWorkspaceDrafts = {};
  state.tradePickRules = [];
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
      ${tradeOffersList(offers)}
    </section>`;
  wireOfferButtons(els.content, offers);
}

function tradeOffersList(offers) {
  return `<div class="trade-offers-list">${offers.length ? offers.map((offer, index) => offerCard(offer, index)).join("") : `<div class="trade-offers-empty"><strong>Your desk is clear.</strong><span>No active AI offers to your team.</span></div>`}</div>`;
}

function tradeOffersModalBody(offers) {
  return tradeOffersList(offers);
}

async function openTradeOffersModal() {
  if (!state.data.dashboardOffers) {
    state.data.dashboardOffers = await action("user_trade_offers", savePayload());
  }
  const offers = state.data.dashboardOffers?.offers || [];
  window.CardBoard?.updateOfferCount(offers.length);
  state.modal = {
    kind: "tradeOffers",
    title: "AI Trade Offers To You",
    subtitle: `${offers.length} active incoming offer${offers.length === 1 ? "" : "s"}`,
    offers,
    body: tradeOffersModalBody(offers),
  };
  renderModal();
}

function returnToPlayerTradeContext(context) {
  if (!context) return;
  if (context.kind === "tradeOffers") return openTradeOffersModal();
  if (context.kind !== "tradeRoom") return;
  state.tradeTab = context.activeTab || state.tradeTab || "builder";
  state.modal = {...context, body:tradeRoomModalBody()};
  renderModal();
}

function wireOfferButtons(root, offers) {
  wireDashboardPlayerCards(root);
  wireTradeInsightPagers(root);
  root.querySelectorAll("[data-offer-accept]").forEach((button) => {
    button.addEventListener("click", () => respondOffer(offers[Number(button.dataset.offerAccept)], "accept").catch(error => showToast(error.message, true)));
  });
  root.querySelectorAll("[data-offer-reject]").forEach((button) => {
    button.addEventListener("click", () => respondOffer(offers[Number(button.dataset.offerReject)], "reject").catch(error => showToast(error.message, true)));
  });
}

async function respondOffer(offer, decision) {
  const proposalId = offer?.proposal?.id || offer?.id;
  const currentSave = state.currentSave, inboxModal = state.modal;
  const result = await action("respond_user_trade_offer", { ...savePayload(), proposal_id: proposalId, decision, ...(decision === "reject" ? {summary_only:true} : {}) });
  if (state.currentSave !== currentSave) return;
  if (decision === "accept" && result.status !== "applied") {
    showToast(result.result?.notes || `Trade not completed: ${rowLabel(result.status)}`, true);
    return;
  }
  if (decision === "reject") {
    let remaining = result.offers;
    if (!remaining && Array.isArray(result.pending_offer_ids)) {
      const pendingIds = new Set(result.pending_offer_ids);
      const known = (inboxModal?.kind === "tradeOffers" ? inboxModal.offers : state.data.offers?.offers) || state.data.dashboardOffers?.offers || [];
      const offers = known.filter(item => pendingIds.has(item.proposal?.id || item.id));
      remaining = {offer_count:result.offer_count, offers};
      // Another manager may have added an offer since this inbox was opened.
      if (offers.length !== pendingIds.size) remaining = await action("user_trade_offers", savePayload());
      if (state.currentSave !== currentSave) return;
    }
    if (!remaining) throw new Error("The offer inbox could not be updated. Please reopen it.");
    state.data.offers = remaining;
    state.data.dashboardOffers = remaining;
    const count = Number(remaining.offer_count ?? remaining.offers.length);
    for (const counts of [state.home?.save?.pending_counts, state.home?.pending?.pending_counts]) {
      if (counts) counts.user_trade_offers = count;
    }
    window.CardBoard?.updateOfferCount(count);
    showToast(result.status === "rejected" ? "Offer declined" : `Offer ${rowLabel(result.status)}`);
    if (result.status === "rejected") tradeResponseEffect("declined");
    if (state.modal === inboxModal && state.modal?.kind === "tradeOffers") {
      const scrollTop = els.modalRoot?.querySelector(".modal-shell")?.scrollTop || 0;
      state.modal.offers = remaining.offers;
      state.modal.subtitle = `${count} active incoming offer${count === 1 ? "" : "s"}`;
      state.modal.body = tradeOffersModalBody(remaining.offers);
      renderModal();
      const shell = els.modalRoot?.querySelector(".modal-shell");
      if (shell) shell.scrollTop = scrollTop;
    } else if (state.view === "offers") renderOffers();
    return;
  }
  state.data.offers = result.offers;
  state.data.dashboardOffers = result.offers;
  window.CardBoard?.updateOfferCount(Number(result.offers?.offers?.length || 0));
  showToast(result.status === "applied" ? "Trade completed" : `Offer ${rowLabel(result.status)}`, result.status !== "applied");
  if (result.status === "applied") tradeResponseEffect("accepted");
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

function isClipboardPhase(kind) {
  return ["playoffs", "draft", "free_agency", "fantasy_draft", "staff_retention", "cutdown"].includes(kind);
}

function clipboardLegalActions() {
  return new Set(state.home?.save?.legal_actions || state.data.dashboard?.legal_actions || []);
}

function seasonalClipboardCards(dashboard) {
  const kind = dashboardPhaseKind();
  const sections = {
    staff_retention: [["decision", ".required-decision-workspace", "Staff Retention - Required"]],
    cutdown: [["decision", ".required-decision-workspace", "Roster Cutdown - Required"]],
    playoffs: [
      ["bracket", ".phase-bracket-shell", "Playoff Bracket"],
      ["leaders", ".phase-leaders-panel", "Playoff Stats"],
    ],
    draft: [
      ["lottery", ".draft-lottery-card", "Draft Lottery"],
      ["board", ".draft-prospect-panel:not(.draft-summary-panel)", "Draft Prospect Board"],
      ["order", ".draft-order-ledger-panel", "Draft Order"],
      ["summary", ".draft-summary-panel", "Draft Summary"],
      ["trades", ".draft-trade-recap-panel", "Draft-Night Trades"],
    ],
    free_agency: [
      ["control", ".phase-workspace-head", "Free Agency Controls"],
      ["market", "[data-free-agency-market-card]", "Free-Agent Market"],
      ["selected", ".selected-player-intelligence", "Selected Free Agent"],
      ["offers", ".live-offer-intelligence", "Live Offers"],
      ["wire", ".signing-wire-intelligence", "Signing Wire"],
      ["payroll", ".cap-intelligence", "Free Agency Payroll"],
      ["cap", ".market-cap-totals", "Free Agency Cap Position"],
    ],
    fantasy_draft: [
      ["control", ".fantasy-draft-head", "Fantasy Draft Controls"],
      ["board", ".fantasy-player-board", "Fantasy Player Board"],
      ["roster", ".fantasy-roster-board", "Fantasy Draft Roster"],
      ["ticker", ".fantasy-draft-ticker", "Fantasy Draft Ticker"],
    ],
  };
  const legal = clipboardLegalActions();
  const cards = [];
  for (const [phase, definitions] of Object.entries(sections)) {
    const seed = document.createElement("div");
    seed.className = "unified-phase-dashboard seasonal-card-seed";
    seed.dataset.phase = phase;
    const active = phase === kind;
    const required = active && ["staff_retention", "cutdown"].includes(phase);
    const roomKey = {playoffs:"playoffs", draft:"draft", free_agency:"freeagency", fantasy_draft:"fantasyDraft", staff_retention:"staffRetention", cutdown:"cutdown"}[phase];
    if (!state.hydrating && state.data[roomKey] && (active || phase === "free_agency" || phase === 'playoffs' && state.home?.save?.playoff_status === 'completed')) {
      seed.innerHTML = phase === "free_agency" && !active
        ? `<div class="phase-free-agency-layout free-agency-single-market">${phaseFreeAgencyMarketCard(state.data.freeagency)}${freeAgencyIntelligenceRail(state.data.freeagency)}</div>`
        : dashboardPhaseWorkspace(phase);
      if (required) {
        const workspace = document.createElement("div");
        workspace.className = "required-decision-workspace";
        workspace.append(...seed.childNodes);
        seed.append(workspace);
      }
    }
    dashboard.append(seed);
    // Measure the existing phase layout before detaching any of its sections.
    const measurements = definitions.map(([name, selector, title]) => {
      const panel = seed.querySelector(selector);
      const rect = panel?.getBoundingClientRect();
      return {name, title, panel, width:Math.max(100, rect?.width || 320), height:Math.max(40, rect?.height || 240)};
    });
    for (const {name, title, panel, width, height} of measurements) {
      const card = document.createElement("div");
      card.className = required ? "required-clipboard-card" : "seasonal-clipboard-card";
      const phaseContext = document.createElement("div");
      phaseContext.className = "unified-phase-dashboard";
      phaseContext.dataset.seasonalContext = "";
      card.append(phaseContext);
      let parent = phaseContext;
      const ancestors = [];
      for (let node = panel?.parentElement; node && node !== seed; node = node.parentElement) ancestors.unshift(node);
      for (const ancestor of ancestors) {
        const context = ancestor.cloneNode(false);
        context.removeAttribute("id");
        context.dataset.seasonalContext = "";
        parent.append(context);
        parent = context;
      }
      if (panel) {
        parent.append(panel);
        if (name === "control") panel.querySelectorAll("button").forEach(button => button.dataset.windowCommand = "");
        if (phase === "draft" && name === "control") {
          const news = seed.querySelector(".draft-news-strip, .draft-ceremony-note");
          if (news) parent.append(news);
        }
      } else card.innerHTML = `<div class="empty">Available during ${escapeHtml(rowLabel(phase))}.</div>`;
      const archiveBracket = phase === 'playoffs' && name === 'bracket' && state.home?.save?.playoff_status === 'completed';
      const available = Boolean(panel) && (active || archiveBracket || phase === "free_agency" && name !== "control");
      const signingClosed = phase === "free_agency" && ["market", "selected"].includes(name)
        && state.data.freeagency?.state?.status === "completed";
      const locked = !available || (phase === "free_agency" && !legal.has("free_agent_signings")) || signingClosed;
      const bracket = phase === "playoffs" && name === "bracket";
      const lottery = phase === 'draft' && name === 'lottery';
      const playoffStats = phase === "playoffs" && name === "leaders";
      cards.push({id:`phase-${phase}-${name}`, title, card, width:bracket ? Math.min(1420, Math.max(320, window.innerWidth - 60)) : lottery ? Math.min(700,Math.max(320,window.innerWidth-60)) : playoffStats ? Math.min(660, Math.max(320, window.innerWidth - 60)) : width, height:bracket ? 480 : lottery ? (state.draftPresentationStage==='odds'?444:454) : playoffStats ? 430 : height, sizingKey:lottery?`lottery-v3:${state.draftPresentationStage}`:playoffStats?"playoff-stats-v1":null, locked, galleryVisible:(active || archiveBracket) && Boolean(panel), mandatory:["staff_retention", "cutdown"].includes(phase), required:required && Boolean(panel), measured:Boolean(panel), phaseActive:active && Boolean(panel)});
    }
    seed.remove();
  }
  return cards;
}

function clipboardLockedCards() {
  const legal = clipboardLegalActions();
  const locks = {};
  if (!legal.has("trades") && !legal.has("draft_trades")) {
    for (const id of ["trade-builder", "trade-finder", "league-block", "team-block", "team-wants"]) locks[id] = true;
  }
  if (!legal.has("advance") || isClipboardPhase(dashboardPhaseKind())) locks.week = true;
  if (!legal.has("staff_changes")) locks.staff = true;
  if (dashboardPhaseKind() === "fantasy_draft") locks.minutes = true;
  return locks;
}

async function openClipboardWindow(view) {
  if (state.view !== "dashboard") {
    state.view = "dashboard";
    await ensureViewData();
    render();
  }
  if (view === "calendar") {
    window.CardBoard?.open("week");
    return;
  }
  const phase = dashboardPhaseKind();
  const phaseCard = view === "draft" && ["draft", "fantasy_draft"].includes(phase)
    ? phase === 'draft' ? (['odds','reveal'].includes(state.draftPresentationStage) ? 'phase-draft-lottery' : 'phase-draft-board') : 'phase-fantasy_draft-control'
    : view === "playoffs" ? "phase-playoffs-bracket"
    : ["freeagents", "freeagency"].includes(view) ? "phase-free_agency-market" : null;
  if (phaseCard && ["freeagents", "freeagency"].includes(view) && !state.data.freeagency) {
    state.data.freeagency = await action("free_agency_room", {...savePayload(), team:userTeam(), seed:7});
    renderDashboard();
  }
  if (phaseCard) {
    window.CardBoard?.open(phaseCard);
    return;
  }
  const cardId = {"staff":"staff", "draft":"prospects"}[view];
  if (cardId) {
    window.CardBoard?.open(cardId);
    window.CardBoard?.expand(cardId);
  }
}

function renderProspectBoard(target = els.content, options = {}) {
  const draft = state.data.draft || {};
  const rows = draftBoardRows(draft.draft_board);
  target.classList.toggle("season-prospects-expanded", Boolean(options.clipboard));
  target.innerHTML = options.clipboard
    ? `<div class="season-prospects-expanded-body">${seasonProspectsCard({rows, expanded:true})}</div>`
    : `<section class="section prospect-preview">${sectionHead("Upcoming Prospects", draft.year || "")}${draftProspectBoard(sortDraftBoardRows(rows, state.draftBoardSort))}</section>`;
  if (options.clipboard) {
    wireSeasonProspectSort(target);
    wireDashboardProspectCards(target);
    return;
  }
  target.querySelectorAll("[data-draft-sort]").forEach(button => button.addEventListener("click", () => {
    const key = button.dataset.draftSort;
    state.draftBoardSort = {key, direction: state.draftBoardSort.key === key && state.draftBoardSort.direction === "asc" ? "desc" : "asc"};
    renderProspectBoard(target, options);
  }));
  target.querySelectorAll("[data-draft-prospect-card]").forEach(button => button.addEventListener("click", () => draftProspectCard(button.dataset.draftProspectCard)));
}

async function setProspectsCardExpanded(expanded, card) {
  if (!card) return;
  card.classList.toggle("season-prospects-expanded", expanded);
  if (!expanded) {
    card.innerHTML = seasonProspectsCard();
    wireSeasonProspectSort(card);
    wireDashboardPlayerCards(card);
    return;
  }
  if (!state.data.draft) {
    card.innerHTML = `<div class="season-prospects-expanded-loading">Loading prospect board...</div>`;
    try {
      const currentSave = state.currentSave;
      state.data.draft = await action("draft_room", {...savePayload(), team:userTeam(), seed:7});
      if (state.currentSave !== currentSave || !card.isConnected || !card.classList.contains("season-prospects-expanded")) return;
    } catch (error) {
      if (card.isConnected && card.classList.contains("season-prospects-expanded")) {
        card.innerHTML = `<div class="season-prospects-expanded-loading">Prospect board unavailable.</div>`;
      }
      showToast(error.message || String(error), true);
      return;
    }
  }
  if (card.isConnected && card.classList.contains("season-prospects-expanded")) renderProspectBoard(card, {clipboard:true});
}

function wireSeasonProspectSort(root) {
  wireDashboardProspectCards(root);
  root.querySelectorAll("[data-season-prospect-sort]").forEach(button => button.addEventListener("click", () => {
    const key = button.dataset.seasonProspectSort;
    const prior = state.dashboardProspectSort;
    state.dashboardProspectSort = {key, direction:prior.key === key && prior.direction === "asc" ? "desc" : "asc"};
    const panel = button.closest(".season-prospects-panel");
    if (panel) {
      panel.innerHTML = seasonProspectsCard();
      wireSeasonProspectSort(panel);
      wireDashboardPlayerCards(panel);
      return;
    }
    const card = button.closest('[data-board-window="prospects"]');
    if (card?.classList.contains("season-prospects-expanded")) renderProspectBoard(card, {clipboard:true});
  }));
}

function renderDraft() {
  if (dashboardPhaseKind() !== "draft") return renderProspectBoard();
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
  await runLotteryReveal();
}

async function draftEnterNight() {
  if (state.lotteryRevealRunning) return;
  state.draftPresentationStage = "draft";
  await advance({draft_enter:true});
}

async function draftSim(actionName) {
  const result = await action(actionName, { ...savePayload(), team: userTeam(), seed: 7 });
  const appliedCount = Number(result.result?.applied_count ?? (result.status === "applied" ? 1 : 0));
  const events = result.result?.presentation_events || [];
  if (events.length) {
    await playDraftSimulation(result.room, events, appliedCount);
    return;
  }
  showToast(`Draft sim: ${appliedCount} pick${appliedCount === 1 ? "" : "s"}`);
  await refreshDashboardAfterPhaseMutation("draft", result.room);
}

async function playDraftSimulation(finalRoom, events, appliedCount) {
  state.draftPlaybackRunning = true;
  state.draftPlaybackReveal = null;
  window.AssistantGMPhone?.setDraftPlaybackActive?.(true);
  state.busyDepth += 1;
  setBusy(true);
  let revealedPicks = 0;
  let tradeNotificationsShown = false;
  const draftTradeNotices = events.filter(event => event.type === "trade");
  try {
    state.data.draft = GameSimulation.draftPlaybackFrame(finalRoom, events, 0);
    await refreshDashboardAfterPhaseMutation("draft", state.data.draft);
    setBusy(true);
    for (const event of events) {
      if (event.type === "trade") {
        if (!tradeNotificationsShown) {
          tradeNotificationsShown = true;
          const showAlerts = window.AssistantGMPhone?.presentDraftTrades;
          if (showAlerts) await showAlerts(draftTradeNotices);
          else await GameSimulation.wait(1800);
        }
        continue;
      }
      if (event.type !== "pick") continue;
      revealedPicks += 1;
      state.draftPlaybackReveal = event;
      state.data.draft = GameSimulation.draftPlaybackFrame(finalRoom, events, revealedPicks);
      updateDraftPlaybackCard();
      await GameSimulation.wait(GameSimulation.reducedMotion() ? 160 : 430);
    }
    showToast(`Draft sim: ${appliedCount} pick${appliedCount === 1 ? "" : "s"}`);
  } finally {
    state.data.draft = finalRoom;
    state.draftPlaybackRunning = false;
    state.draftPlaybackReveal = null;
    updateDraftPlaybackCard();
    state.busyDepth = Math.max(0, state.busyDepth - 1);
    setBusy(state.busyDepth > 0 || state.hydrating);
    window.AssistantGMPhone?.setDraftPlaybackActive?.(false);
    if(typeof maybeShowWantReminder==='function')maybeShowWantReminder();
  }
}

function updateDraftPlaybackCard() {
  const frame = document.querySelector('[data-board-window="phase-draft-board"]');
  const shell = frame?.querySelector(".draft-night-shell");
  if (!shell) {
    renderDashboard();
    setBusy(true);
    return;
  }
  const template = document.createElement("template");
  template.innerHTML = draftDashboardWorkspace().trim();
  const nextShell = template.content.querySelector(".draft-night-shell");
  if (!nextShell) {
    renderDashboard();
    setBusy(true);
    return;
  }
  shell.replaceWith(nextShell);
  wireDashboardPhaseWorkspace("draft", frame.querySelector(".card-board-body") || frame);
  setBusy(true);
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
        : `<div class="phase-workspace-head unified-free-agency-head"><div class="unified-phase-brand"><h3>Current Free Agents</h3></div><strong class="unified-phase-day">${escapeHtml(rowLabel(room.phase || "regular_season"))}</strong><button class="ui-command" data-open-waivers>Waivers</button></div><div class="phase-free-agency-layout free-agency-single-market">${phaseFreeAgencyMarketCard(room, exclusive)}${freeAgencyIntelligenceRail(room, exclusive)}</div>`}
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
  root.querySelectorAll('[data-open-waivers]').forEach((button) => button.addEventListener('click', openWaiverRoom));
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

async function openWaiverRoom() {
  const room = await action('waiver_room', savePayload());
  const roster = new Map(room.roster.map((p) => [p.id, p.name]));
  state.modal = {kind: 'waivers', title: 'Waiver Wire', body: table(['Player', 'Clears', 'Existing contract', 'Roster move', ''], room.players, (row) => [
    row.player_name, row.clearance_date,
    row.contract.map((r) => `${r.season}: ${r.salary == null ? 'Unknown' : money(r.salary / 1000000)}`).join(' / '),
    row.options.length ? html(`<select data-waiver-cut="${escapeAttr(row.id)}" aria-label="Player to waive for ${escapeAttr(row.player_name)}">${row.options.map((o) => `<option value="${escapeAttr(o.cut_player_id || '')}">${escapeHtml(o.cut_player_id ? `Waive ${roster.get(o.cut_player_id)} (${money(o.cut_cost_millions)} owed)` : 'Open roster spot')}</option>`).join('')}</select>`) : 'No legal claim',
    html(`<button class="ui-command" data-claim-waiver="${escapeAttr(row.id)}" ${row.claimed || !row.options.length ? 'disabled' : ''}>${row.claimed ? 'Claim submitted' : 'Claim'}</button>`),
  ]) + `<details><summary>Release a player</summary>${table(['Player', 'Remaining buyout', ''], room.roster, (p) => [p.name,
    p.buyout.unquantified ? 'Unknown' : money(p.buyout.payout_millions),
    html(`<button class="ui-command" data-wire-release="${escapeAttr(p.id)}" data-buyout="false">Waive</button> <button class="ui-command" data-wire-release="${escapeAttr(p.id)}" data-buyout="true">Buyout</button>`),
  ])}</details>`};
  renderModal();
  els.modalRoot.querySelectorAll('[data-wire-release]').forEach((button) => button.addEventListener('click', async () => {
    const p = room.roster.find((r) => r.id === button.dataset.wireRelease);
    const quote = p.buyout;
    const buyout = button.dataset.buyout === 'true';
    const charges = (buyout ? quote.cap_charges : quote.seasons).map((r) => `${r.season}: ${r.salary == null ? 'Unknown' : money(r.salary / 1000000)}`).join('\n');
    if (!window.confirm(`${buyout ? 'Buy out' : 'Waive'} ${p.name}?\n${buyout ? quote.policy : 'Guaranteed obligations remain unless another team claims the contract.'}\nCap charges if unclaimed:\n${charges}\nWaivers clear ${quote.clearance_date}.`)) return;
    await action(buyout ? 'buyout_player' : 'waive_player', {...savePayload(), player_id: p.id});
    await refreshHome();
    await openWaiverRoom();
  }));
  els.modalRoot.querySelectorAll('[data-claim-waiver]').forEach((button) => button.addEventListener('click', async () => {
    const id = button.dataset.claimWaiver;
    const select = Array.from(els.modalRoot.querySelectorAll('[data-waiver-cut]')).find((s) => s.dataset.waiverCut === id);
    if (!window.confirm('Submit this waiver claim? If awarded, you assume the existing contract and the selected roster move is applied. Claims cannot be withdrawn.')) return;
    await action('claim_waiver', { ...savePayload(), waiver_id: id, cut_player_id: select?.value || null });
    await openWaiverRoom();
  }));
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
      if (els.content.querySelector('.seasonal-clipboard-card')) return;
      refreshFreeAgencyMarketCard(els.content.querySelector("[data-free-agency-market-card]"), renderDashboard);
    });
  });
}

function refreshFreeAgencyIntelligence() {
  if (els.content.querySelector('.seasonal-clipboard-card [data-free-agency-intelligence]')) {
    renderDashboard();
    return;
  }
  const current = els.content.querySelector("[data-free-agency-intelligence]");
  if (!current) return;
  const room = state.data.freeagency || {};
  current.outerHTML = freeAgencyIntelligenceRail(room, room.phase === "re_signing");
  wireFreeAgencyIntelligence(els.content.querySelector("[data-free-agency-intelligence]") || els.content);
}

function refreshFreeAgencyMarketCard(card, rerender = renderDashboard) {
  if (card?.closest('.seasonal-clipboard-card')) {
    rerender();
    return;
  }
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
  return `<div class="approved-negotiation-evidence">${[["Health risk", detail?.health_risk, true], ["Growth runway", detail?.upside_remaining, false], ["Trade value", detail?.trade_value, false]].map(([label, value, inverse]) => {
    if (label === "Health risk" && detail?.injury_body_map?.parts?.length) {
      return `<div class="injury-negotiation-body"><span>Injury risk</span>${injuryRiskBody(value, detail.injury_body_map)}<strong>${draftMetric(value)}</strong></div>`;
    }
    const score = inverse ? 100 - Number(value || 0) * 10 : label === "Growth runway" ? Number(value || 0) * 20 : Number(value || 0);
    return `<div class="${ratingTone(score)}"><span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(score)}"></b></i><strong>${draftMetric(value)}${label === "Growth runway" ? " / 5" : label === "Health risk" ? " / 10" : ""}</strong></div>`;
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
      <section class="approved-card-panel approved-ask-offer"><header>Ask / Offer</header><div class="approved-ask-grid"><span><small>Asking price</small><strong>${money(player.ask_millions)} x 4</strong><label class="contract-security"><input id="faGuaranteed" type="checkbox" checked> Guaranteed</label></span><label><small>Your offer · max ${money(maximum)}</small><span class="money-input"><b>$</b><input id="faAav" type="number" min="1.9" max="${maximum.toFixed(1)}" step="0.1" value="${initial.toFixed(1)}"><b>M</b></span></label><label><small>Years</small><input id="faYears" type="number" min="1" max="5" step="1" value="4"></label></div></section>
      <section class="approved-card-panel approved-interest-factors"><header>Interest Breakdown</header><div>${[["Offer vs ask", initial / Math.max(1, Number(player.ask_millions || 1)) * 100], ["Team fit", player.team_fit_score], ["Market position", player.highest_offer?.interest_score || 50], ["Financial room", maximum / Math.max(1, Number(player.ask_millions || 1)) * 70]].map(([label, value]) => `<span><small>${escapeHtml(label)}</small><i><b style="width:${clampNumber(Number(value || 0), 0, 100)}%"></b></i><strong>${Math.round(clampNumber(Number(value || 0), 0, 100))}</strong></span>`).join("")}</div></section>
      <section class="approved-card-panel approved-offer-decision"><header>Player Interest</header><div><i><b data-fa-live-interest style="width:${clampNumber(initial / Math.max(1, Number(player.ask_millions || 1)) * 70, 0, 100)}%"></b></i><strong data-fa-live-interest-value>${Math.round(clampNumber(initial / Math.max(1, Number(player.ask_millions || 1)) * 70, 0, 100))} / 100</strong><button id="submitFaOffer" class="primary-action">${exclusive ? "Offer Re-Signing" : "Submit Offer"}</button></div></section>
      <section class="approved-card-panel approved-offer-cap"><header>Four-Year Cap Impact</header>${approvedOfferCapChart(capRows.slice(0, 4), initial)}</section>
      <section class="approved-card-panel approved-offer-salary"><header>Six-Season Salary + Team Position</header>${approvedOfferSalaryTable(capRows, initial)}</section>
    </div>
  </div>`;
}

function approvedOfferCapChart(capRows, offer) {
  const maximum = Math.max(1, ...capRows.map(([, cap]) => Number(cap.hard_cap_millions || 230))) * 1.05;
  return `<div class="approved-offer-cap-chart">${capRows.map(([season, cap], index) => {
    const annual = Number((Array.isArray(offer) ? offer[index] : offer) || 0);
    const payroll = Number(cap.salary_total_millions || 0);
    const after = payroll + annual;
    return `<div><span>${escapeHtml(shortSeasonLabel(season))}</span><i><b style="height:${clampNumber(payroll / maximum * 100, 0, 100)}%"></b><strong data-offer-highlight data-cap-maximum="${maximum}" style="height:${clampNumber(annual / maximum * 100, 0, 100)}%;bottom:${clampNumber(payroll / maximum * 100, 0, 100)}%"></strong><em class="tax-line" style="bottom:${clampNumber(Number(cap.tax_line_millions || 0) / maximum * 100, 0, 100)}%"></em><em class="hard-line" style="bottom:${clampNumber(Number(cap.hard_cap_millions || 0) / maximum * 100, 0, 100)}%"></em></i><small data-offer-payroll data-base-payroll="${payroll}">${money(after)}</small></div>`;
  }).join("")}</div>`;
}

function approvedOfferSalaryTable(capRows, offer) {
  const rows = [...capRows];
  while (rows.length < 6) rows.push([`Year ${rows.length + 1}`, {}]);
  return `<table class="approved-offer-salary-table"><thead><tr><th>Season</th><th>Salary</th><th>Payroll</th><th>Tax room</th><th>Hard-cap room</th></tr></thead><tbody>${rows.slice(0, 6).map(([season, cap], index) => {
    const annual = Number((Array.isArray(offer) ? offer[index] : offer) || 0);
    return `<tr><td>${escapeHtml(shortSeasonLabel(season))}</td><td data-offer-salary>${money(annual)}</td><td data-offer-table-payroll data-base="${Number(cap.salary_total_millions || 0)}">${money(Number(cap.salary_total_millions || 0) + annual)}</td><td data-offer-table-tax data-base="${Number(cap.tax_space_millions || 0)}">${signedMoney(Number(cap.tax_space_millions || 0) - annual)}</td><td data-offer-table-hard data-base="${Number(cap.hard_cap_space_millions || 0)}">${signedMoney(Number(cap.hard_cap_space_millions || 0) - annual)}</td></tr>`;
  }).join("")}</tbody></table>`;
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
    ["OVR", ratings.overall], ["Shooting", ratings.shooting], ["Release", ratings.release],
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

function playerCardRatingGroups(ratings = {}, includeOverall = true, includeLocked = false) {
  const group = (label, rows) => ({label, rows: rows.filter(([, value]) => includeLocked || (value !== undefined && value !== null))});
  const hasInterior = ["post_creation", "assisted_finishing", "screening"].some(key => Object.prototype.hasOwnProperty.call(ratings, key));
  return [
    group("Offense", [
      ...(includeOverall ? [["OVR", ratings.overall, "overall"]] : []), ["Shooting", ratings.shooting, "shooting"], ["Release", ratings.release, "release"],
      ["Range", ratings.range, "range"], ["Shot versatility", ratings.versatility, "versatility"], ["Spacing", ratings.spacing, "spacing"],
      ["Creation", ratings.creation, "creation"], ["Handle", ratings.handle, "handle"], ["Passing", ratings.passing, "passing"],
      ...(!hasInterior ? [["Rim pressure", ratings.rim_pressure, "rim_pressure"]] : []),
    ]),
    ...(hasInterior ? [group("Interior & Rebounding", [
      ["Rim pressure", ratings.rim_pressure, "rim_pressure"], ["Post creation", ratings.post_creation, "post_creation"],
      ["Assisted finishing", ratings.assisted_finishing, "assisted_finishing"], ["Screening", ratings.screening, "screening"],
      ["Rebounding", ratings.rebounding, "rebounding"],
      ["Offensive rebounding", ratings.offensive_rebounding ?? ratings.oreb, ratings.offensive_rebounding != null ? "offensive_rebounding" : "oreb"],
    ])] : []),
    group("Defense", [
      ["Defense", ratings.defense, "defense"], ["Defensive effort", ratings.def_effort, "def_effort"],
      ["Screen navigation", ratings.screen_nav, "screen_nav"], ["Steal", ratings.steal, "steal"],
      ["Block", ratings.block, "block"], ["Rim deterrence", ratings.rim_deterrence, "rim_deterrence"],
      ...(hasInterior ? [["Athleticism", ratings.athleticism, "athleticism"], ["Lateral agility", ratings.lateral_agility, "lateral_agility"]] : []),
    ]),
    ...(!hasInterior ? [group("Rebounding", [
      ["Rebounding", ratings.rebounding, "rebounding"],
      ["Offensive rebounding", ratings.offensive_rebounding ?? ratings.oreb, ratings.offensive_rebounding != null ? "offensive_rebounding" : "oreb"],
    ])] : []),
    group(hasInterior ? "Mind, Body & Coach" : "Mental and Physical", [
      ...(!hasInterior ? [["Athleticism", ratings.athleticism, "athleticism"], ["Lateral agility", ratings.lateral_agility, "lateral_agility"]] : []),
      ["Stamina", ratings.stamina, "stamina"], ["Basketball IQ", ratings.iq, "iq"], ["Scheme IQ", ratings.scheme_iq, "scheme_iq"],
      ...(hasInterior ? [["Portability", ratings.portability, "portability"], ["Playoff translation", ratings.playoff, "playoff"]] : []),
    ]),
    ...(!hasInterior ? [group("Coach Perspective", [
      ["Portability", ratings.portability, "portability"], ["Playoff translation", ratings.playoff, "playoff"],
    ])] : []),
  ].filter(item => item.rows.length);
}

function playerCardRatingRows(ratings = {}) {
  return playerCardRatingGroups(ratings).flatMap(group => group.rows);
}

function playerCardRatingBar(label, value, key, detail = {}) {
  if (detail.is_prospect && value == null) return `<div class="prospect-rating-locked" aria-label="${escapeAttr(label)}: not unlocked yet"><span>${escapeHtml(label)}</span><i aria-hidden="true"></i><strong title="Unlock through scouting">Locked</strong></div>`;
  const score = clampNumber(Number(value || 0), 0, 99);
  const reference = Number(detail.rating_league_averages?.[key]);
  const referenceLabel = detail.rating_average_label || "League average";
  // No marker when there is no real reference value (never a made-up midpoint).
  const marker = Number.isFinite(reference)
    ? (() => { const average = clampNumber(reference, 0, 99); return `<em class="rating-average-marker" style="left:${average}%" title="${escapeAttr(referenceLabel)}: ${average.toFixed(1)}" aria-label="${escapeAttr(referenceLabel)} ${average.toFixed(1)}"></em>`; })()
    : "";
  return `<div class="${ratingQuartileTone(value, key, detail.rating_quartiles)}"><span>${escapeHtml(label)}</span><i><b style="${performanceBarStyle(score)}"></b>${marker}</i><strong>${draftMetric(value)}</strong></div>`;
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

function prospectLockIcon() {
  return `<svg class="prospect-lock-icon" viewBox="0 0 48 56" aria-hidden="true"><path d="M12 24v-9a12 12 0 0 1 24 0v9" fill="none" stroke="currentColor" stroke-width="5"/><rect x="4" y="22" width="40" height="31" rx="5" fill="currentColor"/><circle cx="24" cy="35" r="4" fill="var(--ui-panel)"/><path d="M24 35v8" stroke="var(--ui-panel)" stroke-width="4"/></svg>`;
}

function playerCardEvidence(detail) {
  if (detail.is_prospect) {
    const low = detail.rank_range?.low ?? detail.board_rank;
    const high = detail.rank_range?.high ?? detail.board_rank;
    const range = low == null ? '—' : low === high ? `#${low}` : `#${low}–${high}`;
    const upside = detail.upside_unlocked
      ? playerEvidenceRing("Prospect upside", detail.upside_remaining, 5, playerUpsideColor(detail.upside_remaining), " / 5")
      : `<div class="player-evidence-ring prospect-upside-locked" aria-label="Prospect upside locked: unlock at 100% scouting" title="Prospect upside: the gap between your scouts' estimate of this prospect's potential and his current level, on a 0-5 scale. Unlocks at 100% scouting."><span>${prospectLockIcon()}</span><div><b>Prospect upside</b><small>Locked · 100% scouting</small></div></div>`;
    return `<div class="approved-player-evidence"><div class="player-evidence-rings">${playerEvidenceRing("Scouted", detail.scouting_coverage, 100, "#668ea7", "%")}${upside}<div class="prospect-rank-range" aria-label="Projected ranking range ${escapeAttr(range)}"><b>Projected rank</b><strong>${escapeHtml(range)}</strong><small>Draft range</small></div></div></div>`;
  }
  const upside = clampNumber(Number(detail.upside_remaining || 0), 0, 5);
  const upsideColor = playerUpsideColor(upside);
  return `<div class="approved-player-evidence"><div class="player-evidence-rings">${injuryBodyMini(detail)}${declineWatchApplies(detail) ? `<div class="player-evidence-ring player-decline-watch" title="${escapeAttr(declineWatchDetail(detail.decline_watch))}" aria-label="${escapeAttr(declineWatchDetail(detail.decline_watch))}"><span><strong>${Number(detail.decline_watch.per_year).toFixed(1)}</strong></span><div><b>Decline watch</b><small>per rating, next year</small></div></div>` : playerEvidenceRing("Growth runway", upside, 5, upsideColor, " / 5")}${playerEvidenceRing("Trade Value", detail.trade_value, 100, "#668ea7")}</div></div>`;
}

// ---- Injury body map (2026-11-19): per-body-part outlook from the injury model the sim uses ----
const INJURY_BODY_SPOTS = {
  front: {
    head: [[60, 20]], shoulder: [[33, 50], [87, 50]], wrist: [[19, 148], [101, 148]], hand: [[16, 165], [104, 165]],
    thumb: [[22, 163], [98, 163]], hip: [[40, 136], [80, 136]], groin: [[60, 146]], quadriceps: [[48, 172], [72, 172]],
    knee: [[47, 203], [73, 203]], ankle: [[47, 243], [73, 243]], foot: [[46, 252], [74, 252]], toe: [[39, 255], [81, 255]],
  },
  back: {
    shoulder: [[33, 50], [87, 50]], back: [[60, 108]], hamstring: [[48, 176], [72, 176]], calf: [[47, 220], [73, 220]],
    achilles: [[47, 240], [73, 240]],
  },
};
const INJURY_RISK_STOPS = [[0.6, [79, 191, 134]], [1.0, [222, 220, 204]], [1.3, [242, 193, 78]], [1.7, [239, 138, 58]], [2.3, [216, 67, 75]]];

function injuryRiskColor(relative) {
  const value = Number.isFinite(relative) ? relative : 1;
  if (value <= INJURY_RISK_STOPS[0][0]) return `rgb(${INJURY_RISK_STOPS[0][1].join(",")})`;
  for (let index = 1; index < INJURY_RISK_STOPS.length; index += 1) {
    const [high, highColor] = INJURY_RISK_STOPS[index];
    const [low, lowColor] = INJURY_RISK_STOPS[index - 1];
    if (value <= high) {
      const t = (value - low) / (high - low);
      return `rgb(${lowColor.map((c, i) => Math.round(c + (highColor[i] - c) * t)).join(",")})`;
    }
  }
  return `rgb(${INJURY_RISK_STOPS[INJURY_RISK_STOPS.length - 1][1].join(",")})`;
}

function injuryPartTitle(part, map) {
  const typical = Number(part.typical_games || 0);
  const relative = part.relative == null ? "" : ` (${Math.round(part.relative * 100)}% of a typical rotation player's ${typical.toFixed(1)})`;
  const history = part.recent_injuries ? ` · ${part.recent_injuries} injur${part.recent_injuries === 1 ? "y" : "ies"} here in the last 3 years` : "";
  const current = part.current ? ` · CURRENT INJURY${map.current_label ? `: ${map.current_label}` : ""}` : "";
  return `${part.label}: about ${Number(part.expected_games).toFixed(1)} games a season expected to be missed${relative}${history}${current}`;
}

function injuryBodyFigure(map, view, options = {}) {
  const parts = Object.fromEntries((map?.parts || []).map(part => [part.part, part]));
  const overall = map && map.typical_games_total ? map.expected_games_total / map.typical_games_total : 1;
  const tone = injuryRiskColor(overall);
  const limb = (x1, y1, x2, y2, w) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke-width="${w}"/>`;
  const silhouette = `<g class="injury-body-shape" style="--injury-body-tone:${tone}">
    <circle cx="60" cy="20" r="13"/><rect x="54" y="31" width="12" height="11" rx="3"/>
    <path d="M35 45 Q60 38 85 45 L87 92 Q83 116 81 128 L83 146 L37 146 L39 128 Q37 116 33 92 Z"/>
    <g class="injury-body-limbs">${limb(33, 51, 24, 106, 12)}${limb(87, 51, 96, 106, 12)}${limb(24, 106, 18, 152, 10)}${limb(96, 106, 102, 152, 10)}
    ${limb(48, 144, 47, 205, 18)}${limb(72, 144, 73, 205, 18)}${limb(47, 205, 47, 243, 13)}${limb(73, 205, 73, 243, 13)}</g>
    <circle cx="16" cy="163" r="6"/><circle cx="104" cy="163" r="6"/>
    <ellipse cx="44" cy="251" rx="9" ry="5"/><ellipse cx="76" cy="251" rx="9" ry="5"/>
    ${view === "back" ? `<path class="injury-body-spine" d="M60 46 L60 140"/>` : ""}
  </g>`;
  const spots = Object.entries(INJURY_BODY_SPOTS[view]).flatMap(([key, points]) => {
    const part = parts[key];
    if (!part) return [];
    const games = Math.max(0, Number(part.expected_games || 0));
    const relative = Number(part.relative ?? 1);
    const radius = Math.max(options.mini ? 6 : 4, Math.min(options.mini ? 20 : 16, 4 + 4.2 * Math.sqrt(games))) * (options.mini ? 1.2 : 1);
    const color = part.current ? "rgb(155,16,48)" : injuryRiskColor(relative);
    const strength = part.current ? 0.95 : Math.min(0.9, 0.3 + 0.55 * Math.min(1, Math.abs(relative - 1) / 0.8));
    const title = escapeHtml(injuryPartTitle(part, map));
    return points.map(([x, y]) => `<g class="injury-spot${part.current ? " is-current" : ""}" data-injury-part="${escapeAttr(key)}"><title>${title}</title>
      <g style="opacity:${strength.toFixed(2)}">${[[1, 0.28], [0.68, 0.5], [0.38, 0.95]].map(([scale, alpha]) => `<circle cx="${x}" cy="${y}" r="${(radius * scale).toFixed(1)}" fill="${color}" fill-opacity="${alpha}"/>`).join("")}</g>
      ${part.current ? `<circle class="injury-current-ring" cx="${x}" cy="${y}" r="${(radius * 0.7).toFixed(1)}"/>` : ""}</g>`);
  }).join("");
  const label = options.mini ? "" : `<text class="injury-body-view-label" x="60" y="274">${view === "front" ? "Front" : "Back"}</text>`;
  return `<svg class="injury-body-figure${options.mini ? " mini" : ""}" viewBox="0 ${options.mini ? 0 : 0} 120 ${options.mini ? 262 : 280}" role="img" aria-label="${escapeAttr(`${view === "front" ? "Front" : "Back"} body map of injury risk`)}">
    ${silhouette}<g class="injury-spots">${spots}</g>${label}</svg>`;
}

const INJURY_PART_LABELS = {ankle: "Ankle", knee: "Knee", back: "Back", hamstring: "Hamstring", hip: "Hip", foot: "Foot", calf: "Calf",
  shoulder: "Shoulder", groin: "Groin", quadriceps: "Quad", toe: "Toe", head: "Head", wrist: "Wrist", hand: "Hand", achilles: "Achilles",
  thumb: "Thumb", illness: "Illness"};

function injuryBodyFromCompact(body) {
  if (body?.parts) return body;
  if (!body?.p?.length) return null;
  const parts = body.p.map(([part, games, relative]) => ({
    part, label: INJURY_PART_LABELS[part] || part, expected_games: Number(games), relative: relative == null ? null : Number(relative),
    typical_games: relative ? Number(games) / Number(relative) : Number(games), recent_injuries: 0, current: part === body.c,
  }));
  return {parts, current_part: body.c || null, current_label: body.c ? (INJURY_PART_LABELS[body.c] || body.c) : null,
    expected_games_total: body.t, typical_games_total: body.y};
}

function injuryRiskBody(risk, body, label = "Injury risk") {
  const map = injuryBodyFromCompact(body);
  const value = risk == null || !Number.isFinite(Number(risk)) ? null : Number(risk);
  const index = value == null ? "" : ` ${draftMetric(value)} model index`;
  if (!map) return value == null ? `<span class="injury-risk-body" title="${escapeAttr(`${label} unavailable`)}">—</span>`
    : `<span class="injury-risk-body" title="${escapeAttr(`${label}${index}`)}"><b>${draftMetric(value)}</b></span>`;
  const hottest = map.current_part ? map.parts.find(part => part.current)
    : [...map.parts].sort((a, b) => (b.expected_games - b.typical_games) - (a.expected_games - a.typical_games))[0];
  const note = map.current_part ? `Injured: ${map.current_label}` : hottest && hottest.relative > 1.15 ? `Watch: ${hottest.label}` : "No hotspot";
  const title = `${label}${index} (the front office's injury-risk score; most players 1–4). Body map: about ${map.expected_games_total} games a season expected to be missed to injury (typical rotation player ${map.typical_games_total}). ${note}.`;
  return `<span class="injury-risk-body" title="${escapeAttr(title)}" aria-label="${escapeAttr(title)}">${injuryBodyFigure(map, "front", { mini: true })}${value == null ? "" : `<b>${draftMetric(value)}</b>`}</span>`;
}

function injuryBodyMini(detail) {
  const risk = Number(detail.health_risk || 0);
  const map = detail.injury_body_map;
  if (!map?.parts?.length) return playerEvidenceRing("Health risk", risk, 10, risk >= 7 ? "#e04d55" : risk >= 4 ? "#bd5b5d" : "#8e6263", "/10");
  const top = map.current_part ? map.parts.find(part => part.current) : [...map.parts].sort((a, b) => (b.expected_games - b.typical_games) - (a.expected_games - a.typical_games))[0];
  const note = map.current_part ? `Injured: ${map.current_label || top?.label || "out"}` : top && top.relative > 1.15 ? `Watch: ${top.label}` : "No hotspot";
  const summary = `Injury risk ${draftMetric(risk)} model index (the front office's injury-risk score; most players 1–4). Body map: about ${map.expected_games_total} games a season expected to be missed to injury, against ${map.typical_games_total} for a typical rotation player. ${note}. See the Health page for the full map.`;
  return `<div class="player-evidence-ring injury-body-evidence" title="${escapeAttr(summary)}" aria-label="${escapeAttr(summary)}"><span>${injuryBodyFigure(map, "front", { mini: true })}</span><div><b>Injury risk ${draftMetric(risk)}</b><small>${escapeHtml(note)}</small></div></div>`;
}

function injuryBodyMapPanel(detail) {
  const map = detail.injury_body_map;
  if (!map?.parts?.length) return `<section class="approved-card-panel injury-body-panel"><header>Injury Outlook</header><p class="player-page-empty">Body map unavailable for this player.</p></section>`;
  const ranked = [...map.parts].filter(part => part.part !== "illness").sort((a, b) => b.expected_games - a.expected_games).slice(0, 8);
  const scale = Math.max(...ranked.map(part => Math.max(part.expected_games, part.typical_games)), 1);
  const illness = map.parts.find(part => part.part === "illness");
  const rows = ranked.map(part => `<tr class="${part.current ? "is-current" : ""}" title="${escapeAttr(injuryPartTitle(part, map))}"><th scope="row"><i style="background:${part.current ? "rgb(155,16,48)" : injuryRiskColor(Number(part.relative ?? 1))}"></i>${escapeHtml(part.label)}${part.current ? " <b>now</b>" : ""}</th>
    <td><span class="injury-bar"><span style="width:${(part.expected_games / scale * 100).toFixed(1)}%;background:${injuryRiskColor(Number(part.relative ?? 1))}"></span><em style="left:${(part.typical_games / scale * 100).toFixed(1)}%" title="Typical rotation player"></em></span></td>
    <td>${Number(part.expected_games).toFixed(1)}</td><td>${part.relative == null ? "—" : `${Math.round(part.relative * 100)}%`}</td><td>${part.recent_injuries || "—"}</td></tr>`).join("");
  const current = map.current_part ? `<p class="injury-body-current">Currently injured: <b>${escapeHtml(map.current_label || map.current_part)}</b></p>` : "";
  return `<section class="approved-card-panel injury-body-panel"><header>Injury Outlook · Body Map</header>
    <div class="injury-body-layout">
      <div class="injury-body-figures">${injuryBodyFigure(map, "front")}${injuryBodyFigure(map, "back")}</div>
      <div class="injury-body-detail">
        <p class="injury-body-summary">About <b>${map.expected_games_total}</b> games a season expected to be missed to injury, assuming about ${map.minutes_basis} minutes a game. A typical rotation player: ${map.typical_games_total}.</p>
        ${current}
        <table class="injury-body-table"><thead><tr><th scope="col">Body part</th><th scope="col">Games a season vs typical</th><th scope="col">Games</th><th scope="col">vs typical</th><th scope="col">Last 3 yrs</th></tr></thead><tbody>${rows}</tbody></table>
        ${illness ? `<p class="injury-body-note">Illness: about ${Number(illness.expected_games).toFixed(1)} games a season.</p>` : ""}
        <div class="injury-body-key" aria-label="Color key"><span><i style="background:${injuryRiskColor(0.6)}"></i>Lower than typical</span><span><i style="background:${injuryRiskColor(1)}"></i>Typical</span><span><i style="background:${injuryRiskColor(1.5)}"></i>Higher</span><span><i style="background:${injuryRiskColor(2.3)}"></i>Much higher</span><span><i style="background:rgb(155,16,48)"></i>Current injury</span><span class="injury-key-size">Bigger spot = more games at stake</span></div>
        <p class="injury-body-note">From the same per-body-part injury model the season simulation uses: age, size, workload, playing style and this player's injury history. Recent injuries to a body part raise its risk; the effect fades over about two years.</p>
      </div>
    </div></section>`;
}

function selectSpatialCourtView(button) {
  const root = button.closest(".spatial-heatmap");
  const group = button.dataset.courtGroup;
  const view = button.dataset.courtTab;
  if (!root || !SPATIAL_COURT_VIEWS[view]) return;
  root.querySelectorAll(`.spatial-court[data-court-group="${group}"]`).forEach(svg => svg.toggleAttribute("hidden", svg.dataset.courtView !== view));
  root.querySelectorAll(`.spatial-court-tab[data-court-group="${group}"]`).forEach(tab => tab.setAttribute("aria-pressed", String(tab === button)));
  const legend = root.querySelectorAll(".spatial-legend > span")[group === "offense" ? 0 : 1];
  if (legend) legend.textContent = SPATIAL_COURT_VIEWS[view].legend;
  const caption = root.querySelector(`[data-court-caption="${group}"]`);
  if (caption) caption.textContent = spatialCourtCaption(view, root.dataset.courtEntity === "team");
}

if (typeof document !== "undefined") {
  document.addEventListener("click", event => {
    const button = event.target.closest?.(".spatial-court-tab");
    if (button) { event.preventDefault(); selectSpatialCourtView(button); }
  });
}

function playerUpsideColor(upside) {
  return upside >= 3.5 ? "#2fc77a" : upside >= 1.5 ? "#4e9c70" : "#687c70";
}

function gameArtwork(category, extraClass = "") {
  const subjects = {shooting: "Stephen Curry shooting", rebounding: "Dennis Rodman rebounding", "trade-builder": "Trade builder", "trade-finder": "Trade finder", defense: "Kawhi Leonard defending", mentality: "Kobe Bryant", coach: "Gregg Popovich", prospects: "Victor Wembanyama and Adam Silver on draft night", staff: "Coaching clipboard", awards: "Basketball trophy", payroll: "Cash bundles", availability: "Stopwatch and medical cross"};
  if (!subjects[category]) return "";
  return `<span class="game-artwork ${escapeAttr(extraClass)}" data-artwork="${category}" aria-hidden="true" title="${escapeAttr(subjects[category])} artwork"><img class="game-artwork-light" src="/assets/game-art/${category}-silver.webp" alt="" decoding="async" draggable="false"><img class="game-artwork-dark" src="/assets/game-art/${category}-ink.webp" alt="" decoding="async" draggable="false"></span>`;
}

function gameArtworkTitle(title, category) {
  return `<span class="illustrated-panel-title">${gameArtwork(category, "panel-heading-art")}<span>${escapeHtml(title)}</span></span>`;
}

function playerSeasonTeamLogos(season) {
  if (season.college_team) return `<span class="player-season-teams">${prospectOriginMarkup(season.college_team)}</span>`;
  return `<span class="player-season-teams">${(season.team_abbrevs || []).map(team => {
    const logo = teamLogoSrc(team);
    return logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(team)}" title="${escapeAttr(team)}" width="24" height="24">` : '';
  }).join('')}</span>`;
}

function scoutingNotesMarkup(scouting) {
  // The scouts' strengths and concerns for a real prospect (public boards / recruiting services, paraphrased).
  if (!scouting) return "";
  const rows = [["Scouts like", scouting.strengths], ["Concerns", scouting.weaknesses]].filter(([, tags]) => (tags || []).length);
  const lines = rows.map(([label, tags]) => `<li><span class="scouting-label">${label}:</span> ${escapeHtml(tags.join(" · "))}</li>`);
  if (scouting.declare_note) lines.push(`<li class="scouting-declare-note">${escapeHtml(scouting.declare_note)}</li>`);
  return lines.length ? `<ul class="scouting-notes" title="${escapeAttr(scouting.rank_hint || "")}">${lines.join("")}</ul>` : "";
}

function scoutingProfileStrip(scouting) {
  // Real high-school and international prospects: no college games, so the scouting view leads the card.
  return `<section class="approved-card-panel approved-season-line scouting-profile-line"><header><span>Scouting Report</span><span title="${escapeAttr(scouting.rank_hint || "")}">${escapeHtml(scouting.rank_label || "")}</span></header>${scoutingNotesMarkup(scouting) || `<ul class="scouting-notes"><li>No scouting notes yet.</li></ul>`}</section>`;
}

function collegeProfileStrip(profile, scouting = null) {
  // Real college prospects: the college rates his game skills are read from (same strip style as the season line).
  const stats = profile.stats || [];
  const facts = [scouting?.rank_label, profile.conference, profile.class_year, profile.role, profile.recruit_rating != null ? `Recruit ${draftMetric(profile.recruit_rating)}` : ""].filter(Boolean).join(" · ");
  return `<section class="approved-card-panel approved-season-line college-profile-line" title="${escapeAttr(profile.stats_note || "")}"><header><span>College Profile</span><span title="${escapeAttr(scouting?.rank_hint || "")}">${escapeHtml(facts)}</span></header><div style="--season-field-count:${stats.length}">${stats.map(([label, value, hint]) => `<span title="${escapeAttr(hint || label)}"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value == null ? "—" : draftMetric(value))}</strong></span>`).join("")}</div>${scoutingNotesMarkup(scouting)}</section>`;
}

function playerSeasonStrip(season, career = []) {
  season = career.find(row => row.season === season.season) || season;
  const fields=[['GP/All',`${season.games ?? 0}/${season.team_games ?? '—'}`,'Games played / team games played'],['MPG',season.mpg],['PTS',season.ppg],['REB',season.rpg],['AST',season.apg],['STL',season.spg],['BLK',season.bpg],['TO',season.topg],['FGA',season.fga_per_game],['FG%',season.fg_pct,'Field-goal percentage'],['3PM',season.fg3m_per_game],['3PA',season.fg3a_per_game],['3P%',season.fg3_pct,'Three-point percentage'],['FTA',season.fta_per_game],['FT%',season.ft_pct,'Free-throw percentage']];
  return `<section class="approved-card-panel approved-season-line" data-player-career-options="${escapeAttr(JSON.stringify(career.length?career:[season]))}"><header><span>${season.college_team ? "College Season" : "Season"}</span><details class="player-career-picker"><summary aria-label="Select player career season">${playerSeasonTeamLogos(season)}<span>${escapeHtml(season.season || 'Current season')}</span><span aria-hidden="true">▾</span></summary><div class="player-career-menu" aria-label="Career seasons">${(career.length?career:[season]).map(row=>`<button type="button" data-player-career-season="${escapeAttr(row.season || '')}" aria-pressed="${row.season===season.season}">${playerSeasonTeamLogos(row)}<span>${escapeHtml(row.season || 'Current season')}</span></button>`).join('')}</div></details></header><div style="--season-field-count:${fields.length}">${fields.map(([label,value,hint])=>`<span title="${escapeAttr(hint || `${label} per game`)}"><small>${label}</small><strong>${escapeHtml(typeof value==='string'?value:value==null?'—':draftMetric(value))}</strong></span>`).join('')}</div></section>`;
}

function playerCardGroupedRatings(ratings, detail, profiles = {}) {
  const groups = playerCardRatingGroups(ratings, false, detail.is_prospect);
  const interior = groups.find(group => group.label === "Interior & Rebounding");
  const columns = interior ? [
    [groups.find(group => group.label === "Offense")],
    [groups.find(group => group.label === "Defense")],
    [interior, groups.find(group => group.label === "Mind, Body & Coach")],
  ] : [
    [groups.find(group => group.label === "Offense")],
    [groups.find(group => group.label === "Defense")],
    [groups.find(group => group.label === "Rebounding"), groups.find(group => group.label === "Mental and Physical"), groups.find(group => group.label === "Coach Perspective")],
  ];
  const categoryArt = {Offense: "shooting", Rebounding: "rebounding", "Interior & Rebounding": "rebounding", Defense: "defense", "Mental and Physical": "mentality", "Coach Perspective": "coach"};
  const headingArt = label => label === "Mind, Body & Coach"
    ? gameArtwork("mentality", "rating-category-art") + gameArtwork("coach", "rating-category-art")
    : gameArtwork(categoryArt[label], "rating-category-art");
  return `<div class="approved-rating-groups">${columns.map(column => `<div class="approved-rating-column">${column.filter(Boolean).map(group => `<section class="${profiles[group.label] ? 'rating-group-with-radar' : ''}" style="--rating-rows:${group.rows.length}"><h4 class="illustrated-rating-heading"><span>${escapeHtml(group.label)}</span>${headingArt(group.label)}</h4>${profiles[group.label] || ''}<div class="approved-rating-rail">${group.rows.map(([label, value, key]) => playerCardRatingBar(label, value, key, detail)).join("")}</div></section>`).join("")}</div>`).join("")}</div>`;
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
  return `<div class="approved-recent-games">${rows.map(row => {
    if (!row) return `<div class="is-empty"><span>—</span><span class="approved-recent-opponent">—</span><strong>—</strong><span>—</span><span>—</span><em>—</em></div>`;
    const opponent = row.opponent_abbrev || "";
    const logo = teamLogoSrc(opponent);
    return `<div><span>${escapeHtml(String(row.date || "").slice(5))}</span><span class="approved-recent-opponent" title="${escapeAttr(opponent || 'Opponent unavailable')}">${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(opponent)} logo" decoding="async">` : "—"}</span><strong>${escapeHtml(row.points ?? 0)} PTS</strong><span>${escapeHtml(row.rebounds ?? 0)} REB</span><span>${escapeHtml(row.assists ?? 0)} AST</span><em>${draftMetric(row.game_score)} GS</em></div>`;
  }).join("")}</div>`;
}

function approvedGameScoreChart(detail) {
  const rows = (detail.recent_games || []).filter(row=>Number(row.minutes || 0)>0);
  const gamesPlayed = Math.max(0, Number(detail.season?.games ?? rows.length) || 0);
  const points = (gamesPlayed ? rows.slice(-Math.min(15, gamesPlayed)) : []).map(row => ({label:String(row.date || "").slice(5), value:Number(row.game_score || 0)}));

  return `<div class="approved-game-score-chart" data-game-score-points="${escapeAttr(JSON.stringify(points))}">${playerGameScoreSvg(points, 420, 220)}</div>`;
}

function playerGameScoreSvg(points, width, height) {
  const left = 28, right = width - 7, top = 7, bottom = height - 42;
  const plotWidth = right - left, plotHeight = bottom - top;
  const min = -5, max = 60;
  const xFor = index => left + index / 14 * plotWidth;
  const yFor = value => top + (max - clampNumber(value, min, max)) / (max - min) * plotHeight;
  const plottedY = value => yFor(value);
  // One column per game; five-point score intervals keep the cells readable.
  const columns = 14;
  const gridRows = (max - min) / 2.5;
  const labelStep = 2;
  const verticalGrid = Array.from({length:columns + 1}, (_, index) => {
    const x = left + index / columns * plotWidth;
    return `<line class="grid vertical" x1="${x}" y1="${top}" x2="${x}" y2="${bottom}"></line>`;
  }).join("");
  const horizontalGrid = Array.from({length:gridRows + 1}, (_, index) => {
    const y = top + index / gridRows * plotHeight;
    const value = max - index / gridRows * (max - min);
    const labeled = index === 0 || index === gridRows || index % labelStep === 0;
    return `<line class="grid horizontal" x1="${left}" y1="${y}" x2="${right}" y2="${y}"></line>${labeled ? `<line class="axis-notch" x1="${left - 3}" y1="${y}" x2="${left}" y2="${y}"></line><text class="axis-label" x="${left - 5}" y="${y}">${value.toFixed(0)}</text>` : ""}`;
  }).join("");
  const dates = points.map((point,index) => `<line class="axis-notch" x1="${xFor(index)}" y1="${bottom}" x2="${xFor(index)}" y2="${bottom + 3}"></line><text class="axis-label x-label" transform="translate(${xFor(index)},${bottom + 8}) rotate(-60)">${escapeHtml(point.label)}</text>`).join("");
  const mean = points.length ? points.reduce((sum,point)=>sum+point.value,0)/points.length : 0;
  const tone = mean > .15 ? "positive" : mean < -.15 ? "negative" : "neutral";
  return `<svg class="player-game-score-chart season-efficiency-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Game score over the last 15 games on a shared league-wide scale from minus 5 to 60">${verticalGrid}${horizontalGrid}${dates}<line class="zero" x1="${left}" y1="${yFor(0)}" x2="${right}" y2="${yFor(0)}"></line><polyline class="net ${tone}" points="${points.map((point,index) => `${xFor(index)},${plottedY(point.value)}`).join(" ")}"><title>${escapeHtml(points.length ? `Game score from ${points[0].label} to ${points.at(-1).label}` : "No game-score history yet")}</title></polyline>${points.map((point,index) => `<circle class="chart-node ${tone}" cx="${xFor(index)}" cy="${plottedY(point.value)}" r="1.8"><title>${escapeHtml(point.label)}: ${point.value.toFixed(1)}</title></circle>`).join("")}</svg>`;
}

let playerGameScoreResizeObserver, playerGameScoreFrame = 0;
function wirePlayerGameScoreCharts() {
  playerGameScoreResizeObserver?.disconnect();
  cancelAnimationFrame(playerGameScoreFrame);
  const charts = [...document.querySelectorAll('[data-game-score-points]')];
  if (!charts.length) return;
  const redraw = () => {
    for (const chart of charts) {
      if (!chart.isConnected) continue;
      const svg = chart.querySelector('svg');
      if (!svg || svg.clientWidth < 40 || svg.clientHeight < 50) continue;
      const signature = `${svg.clientWidth},${svg.clientHeight}`;
      if (chart.dataset.chartSize === signature) continue;
      chart.dataset.chartSize = signature;
      chart.innerHTML = playerGameScoreSvg(JSON.parse(chart.dataset.gameScorePoints), svg.clientWidth, svg.clientHeight);
    }
  };
  const schedule = () => { cancelAnimationFrame(playerGameScoreFrame); playerGameScoreFrame = requestAnimationFrame(redraw); };
  playerGameScoreResizeObserver = new ResizeObserver(schedule);
  charts.forEach(chart => playerGameScoreResizeObserver.observe(chart));
  schedule();
}

// New "Ratings & Profiles" page for inputs-model universes (payload key inputs_profile).
const PC4_SEG = ["--pc4-seg1", "--pc4-seg2", "--pc4-seg3", "--pc4-seg4", "--pc4-seg5"];
const PC4_TIER = { core_rotation: "Core rotation", rotation: "Rotation player", deep_rotation: "Deep rotation", fringe: "Fringe roster spot", development_priority: "Development player" };
const pc4Pct = value => `${Math.round(value * 100)}%`;
const pc4Pretty = key => String(key).replace(/_/g, " ").replace(/^./, c => c.toUpperCase());
const pc4Evidence = row => row.evidence === "player" ? "Based on this player's stats" : "Estimate from similar players";
const pc4FtIn = inches => `${Math.floor(inches / 12)}'${Math.round(inches % 12)}"`;

function pc4Track(fill, prior, avg, band, tall) {
  const lo = band ? clampNumber(band[0], 0, 100) : 0, hi = band ? clampNumber(band[1], 0, 100) : 0;
  const bandHtml = band ? `<i class="pc4-band" style="left:${lo}%;width:${Math.max(0.5, hi - lo)}%"></i>` : "";
  const avgHtml = avg == null ? "" : `<i class="pc4-avg" style="left:${clampNumber(avg, 0, 100)}%"></i>`;
  return `<div class="pc4-track${tall ? " tall" : ""}">${bandHtml}<i class="pc4-fill${prior ? " prior" : ""}" style="width:${clampNumber(fill, 0, 100)}%"></i>${avgHtml}</div>`;
}

function pc4Range(row) {
  if (!row.interval) return "";
  const [lo, hi] = row.interval;
  return ` | likely range ${row.kind === "propensity" ? `${pc4Pct(lo)}-${pc4Pct(hi)}` : `${Math.round(lo)}-${Math.round(hi)}`}`;
}

function pc4Tip(row, valueText) {
  const pct = row.pct != null ? ` | league percentile ${Math.round(row.pct)}` : "";
  return escapeAttr(`${row.id} · ${row.name} · ${valueText}${pc4Range(row)}${pct} | ${pc4Evidence(row)}`);
}

function pc4GradeRow(row) {
  const value = Math.round(row.value);
  return `<div class="pc4-r" title="${pc4Tip(row, value)}"><span class="pc4-l">${escapeHtml(row.name)}</span>${pc4Track(row.value, row.evidence === "prior", row.pos_avg, row.interval)}<strong>${value}</strong></div>`;
}

function pc4PassingRows(pairs) {
  const cell = row => `${pc4Track(row.value, row.evidence === "prior", row.pos_avg, row.interval)}<strong title="${pc4Tip(row, Math.round(row.value))}">${Math.round(row.value)}</strong>`;
  return `<div class="pc4-pass-head"><span></span><b>Read</b><span></span><b>Delivery</b><span></span></div>`
    + pairs.map(pair => `<div class="pc4-r pass" title="${escapeAttr(`${pair.id} · ${pair.name}`)}"><span class="pc4-l">${escapeHtml(pair.name)}</span>${cell(pair.read)}${cell(pair.delivery)}</div>`).join("");
}

function pc4MeasureText(row, coach) {
  const cm = row.value, inch = cm / 2.54;
  if (row.id === "P04") return `${Math.round(coach.weight_lbs || cm * 2.2046)} lb <small>${Math.round(cm)} kg</small>`;
  if (row.id === "P10") return `${Math.round(inch)} in <small>${Math.round(cm)} cm</small>`;
  return `${pc4FtIn(inch)} <small>${Math.round(cm)} cm</small>`;
}

function pc4MeasureRow(row, coach) {
  return `<div class="pc4-r measure" title="${pc4Tip(row, `${Number(row.value).toFixed(1)} ${row.unit || ""}`)}"><span class="pc4-l">${escapeHtml(row.name)}</span>${pc4Track(row.pct, row.evidence === "prior", row.pos_avg_pct, row.interval_pct)}<strong>${pc4MeasureText(row, coach)}</strong></div>`;
}

function pc4PropensityRow(row) {
  const band = row.interval ? row.interval.map(x => x * 100) : null;
  return `<div class="pc4-r" title="${pc4Tip(row, pc4Pct(row.value))}"><span class="pc4-l">${escapeHtml(row.name)}</span>${pc4Track(row.value * 100, row.evidence === "prior", row.pos_avg * 100, band)}<strong>${pc4Pct(row.value)}</strong></div>`;
}

function pc4DistributionRow(row) {
  const keys = (row.outcomes && row.outcomes.length ? row.outcomes : Object.keys(row.value)).filter(key => key in row.value);
  const segments = keys.map((key, index) => {
    const range = row.intervals && row.intervals[key] ? ` (range ${pc4Pct(row.intervals[key][0])}-${pc4Pct(row.intervals[key][1])})` : "";
    const avg = row.pos_avg && row.pos_avg[key] != null ? `, position average ${pc4Pct(row.pos_avg[key])}` : "";
    return `<i style="width:${row.value[key] * 100}%;background:var(${PC4_SEG[index % 5]})" title="${escapeAttr(`${pc4Pretty(key)} ${pc4Pct(row.value[key])}${range}${avg}`)}"></i>`;
  }).join("");
  const legend = keys.map((key, index) => `<span><em style="background:var(${PC4_SEG[index % 5]})"></em>${escapeHtml(pc4Pretty(key))} <b>${pc4Pct(row.value[key])}</b></span>`).join("");
  const prior = row.evidence === "prior";
  return `<div class="pc4-dist" title="${escapeAttr(`${row.id} · ${row.name} | ${pc4Evidence(row)}`)}"><div class="pc4-t">${escapeHtml(row.name)}<span class="pc4-badge">${prior ? "similar players" : "player stats"}</span></div><div class="pc4-stackbar${prior ? " prior" : ""}">${segments}</div><div class="pc4-dleg">${legend}</div></div>`;
}

function pc4Entry(row, coach) {
  if (row.kind === "measure") return pc4MeasureRow(row, coach);
  if (row.kind === "propensity") return pc4PropensityRow(row);
  if (row.kind === "distribution") return pc4DistributionRow(row);
  return pc4GradeRow(row);
}

function pc4Group(group, coach) {
  const count = group.pairs ? "9 types, read and delivery" : group.entries.length;
  const rows = group.pairs ? pc4PassingRows(group.pairs) : group.entries.map(row => pc4Entry(row, coach)).join("");
  return `<h4>${escapeHtml(group.name)}<small>${escapeHtml(group.note || count)}</small></h4>${rows}`;
}

function pc4LayerHeader(index, layer) {
  return `<header><h2>${index} · ${escapeHtml(layer.title)}</h2><span class="pc4-count">${layer.from_player_data} of ${layer.total} from player data</span><span class="pc4-sub">${escapeHtml(layer.subtitle)}</span></header>`;
}

function pc4CoachLayer(profile) {
  const coach = profile.coach || {};
  const minutes = Number(coach.minutes_projection);
  const tags = [coach.primary_off_role || "None", coach.secondary_off_role].filter(Boolean).map(role => `<span class="pc4-tag">${escapeHtml(role)}</span>`).join("");
  const defRole = coach.primary_def_role === "Hidden" ? "Not yet revealed" : coach.primary_def_role || "None";
  const minutesRow = coach.availability_note && !(minutes > 0)
    ? `<strong>${escapeHtml(coach.availability_note)}</strong>`
    : Number.isFinite(minutes)
    ? `<div class="pc4-minbar"><div class="pc4-track tall"><i class="pc4-fill" style="width:${clampNumber(minutes / 40 * 100, 0, 100)}%"></i></div><strong>${minutes.toFixed(1)} per game</strong></div>`
    : "<strong>—</strong>";
  return `<section class="pc4-layer pc4-coach"><header><h2>4 · Coach Usage &amp; Deployment</h2><span class="pc4-count">Not player talent</span><span class="pc4-sub">Decided by the coach, not player talent. Changes with team, lineup and game.</span></header>
    <div class="pc4-body">
      <div class="pc4-kv"><span>Position</span><strong>${escapeHtml(coach.position || "—")}</strong></div>
      <div class="pc4-kv"><span>Offensive role</span><strong>${tags}</strong></div>
      <div class="pc4-kv"><span>Defensive role</span><strong><span class="pc4-tag">${escapeHtml(defRole)}</span></strong></div>
      <div class="pc4-kv"><span>Projected minutes</span>${minutesRow}</div>
      <div class="pc4-kv"><span>Usage share</span><strong class="pc4-ph">Set by the coach during games</strong></div>
      <div class="pc4-kv"><span>Rotation spot</span><strong>${escapeHtml(PC4_TIER[coach.rotation_priority] || coach.rotation_priority || "—")}</strong></div>
      <p class="pc4-foot">You set rough minutes for your own team; the coach adjusts game by game (foul trouble, fatigue, hot hands, blowouts, matchups).</p>
    </div></section>`;
}

function inputsProfilePage(profile) {
  const coach = profile.coach || {};
  const [technique, physical, tendencies] = profile.layers;
  const left = technique.groups.filter(group => group.column === 0).map(group => pc4Group(group, coach)).join("");
  const right = technique.groups.filter(group => group.column === 1).map(group => pc4Group(group, coach)).join("");
  return `<div class="pc4" data-inputs-profile>
    <div class="pc4-legend">
      <span><i class="pc4-sw solid"></i>Based on this player's stats</span>
      <span><i class="pc4-sw hatch"></i>Estimate from similar players</span>
      <span><i class="pc4-sw band"></i>Likely range</span>
      <span><i class="pc4-sw tick"></i>Average at his position (${escapeHtml(profile.position || "")})</span>
      <span style="margin-left:auto">Grades: 50 is a functional NBA level, 75 strong, 90 exceptional. Hover any row for details.</span>
    </div>
    <p class="pc4-note">${escapeHtml(profile.header?.scale_note || "")}</p>
    <div class="pc4-layers">
      <section class="pc4-layer">${pc4LayerHeader(1, technique)}<div class="pc4-body"><div class="pc4-cols"><div>${left}</div><div>${right}</div></div></div></section>
      <div class="pc4-stack"><section class="pc4-layer">${pc4LayerHeader(2, physical)}<div class="pc4-body">${physical.groups.map(group => pc4Group({ ...group, note: "" }, coach).replace(/^<h4>.*?<\/h4>/, "")).join("")}<p class="pc4-foot">Measured rows are drawn against the league spread (bar = percentile). Grade rows use the 0-100 scale.</p></div></section>${pc4CoachLayer(profile)}</div>
      <section class="pc4-layer">${pc4LayerHeader(3, tendencies)}<div class="pc4-body">${tendencies.groups.map(group => pc4Group(group, coach)).join("")}</div></section>
    </div></div>`;
}

function approvedPlayerCardBody(detail, options = {}) {
  const extension = options.extension || null;
  const pageOffset = extension ? 1 : 0;
  const ratings = detail.ratings || options.ratings || {};
  const season = detail.season || {};
  const offenseAxes = [["Shooting", ratings.shooting], ["Spacing", ratings.spacing], ["Creation", ratings.creation], ["Passing", ratings.passing], ["Rim pressure", ratings.rim_pressure], ["Portability", ratings.portability]].filter(([, value]) => detail.is_prospect || value != null);
  const defenseAxes = [["Defense", ratings.defense], ["Effort", ratings.def_effort], ["Navigation", ratings.screen_nav], ["Rim protect", ratings.rim_deterrence], ["Rebound", ratings.rebounding], ["Athleticism", ratings.athleticism]].filter(([, value]) => detail.is_prospect || value != null);
  const radar = (title, axes, tone) => {
    if (detail.is_prospect && axes.some(([,value]) => value == null)) return `<div class="player-rating-radar prospect-radar-placeholder" role="img" aria-label="${escapeAttr(title)} locked until its ratings are scouted">${prospectLockIcon()}<span>Profile locked</span><small>Scout all profile ratings to unlock</small></div>`;
    return axes.length >= 3 ? fantasyPlayerRadar(title, axes, `${tone} player-rating-radar`, false) : `<div class="player-page-empty">${escapeHtml(title)} profile unavailable.</div>`;
  };
  const recentGames = [...(detail.recent_game_table || detail.recent_games || [])].slice(-5).reverse();
  while (recentGames.length < 5) recentGames.push(null);
  const gameFields = [["Date", "date"], ["Opponent", "opponent_abbrev"], ["MIN", "minutes"], ["PTS", "points"], ["REB", "rebounds"], ["AST", "assists"], ["STL", "steals"], ["BLK", "blocks"], ["TO", "turnovers"], ["GS", "game_score"]];
  const gameRows = recentGames.map(row => `<tr>${gameFields.map(([, key]) => {
    if (!row) return '<td>—</td>';
    if (key === "date") return `<td>${escapeHtml(String(row.date || "").slice(5) || "—")}</td>`;
    if (key === "opponent_abbrev") {
      if (row.college_opponent) return `<td><span class="player-page-college-opponent" title="${escapeAttr(row.college_opponent)}">${prospectOriginMarkup(row.college_opponent)}</span></td>`;
      const opponent = row.opponent_abbrev || "";
      const logo = teamLogoSrc(opponent);
      return `<td><span class="player-page-opponent" title="${escapeAttr(opponent || "Opponent unavailable")}">${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(opponent)} logo" decoding="async">` : escapeHtml(opponent || "—")}</span></td>`;
    }
    return `<td>${["minutes", "game_score"].includes(key) ? draftMetric(row[key]) : escapeHtml(row[key] ?? "—")}</td>`;
  }).join("")}</tr>`).join("");
  return `<div class="approved-player-card approved-player-pages${detail.is_prospect ? " approved-prospect-pages" : ""}" data-player-pages>
    <div class="player-page-bar"><span data-player-page-title>${extension ? "Contract Extension" : detail.is_prospect ? "College Season & Games" : "Season, Games & Contract"}</span><div class="player-page-nav"><button type="button" class="ui-command" data-player-page-step="-1" aria-label="Previous player card page" title="Previous page">‹</button><button type="button" class="ui-command" data-player-page-step="1" aria-label="Next player card page" title="Next page">›</button><span data-player-page-count aria-live="polite" aria-atomic="true">1/${(extension ? 1 : 0) + 2 + (detail.is_prospect ? 0 : 1)}</span></div></div>
    <section class="approved-player-identity player-page-identity"><div class="approved-player-profile-head">${playerHeadshotMarkup(detail, "approved-profile-headshot")}<div class="approved-profile-name"><h3>${escapeHtml(detail.name || options.name || "Player")}</h3><p>${escapeHtml([detail.position, detail.age != null ? `${detail.age} years` : "", detail.height].filter(Boolean).join(" · "))}</p><p class="player-draft-details">${escapeHtml(detail.is_prospect ? [detail.college_profile ? detail.source_team : (detail.scouting_profile?.where || detail.source_team), detail.college_profile?.coach ? `Coach ${detail.college_profile.coach}` : "", `${detail.draft_year} draft class`].filter(Boolean).join(" · ") : detail.draft_position ? `${detail.draft_year || 'Draft'} · Pick #${detail.draft_position}` : detail.draft_status==='undrafted' ? `Undrafted${detail.draft_year?` · ${detail.draft_year}`:''}` : detail.draft_year ? `Draft year ${detail.draft_year}` : 'Draft details unavailable')}</p></div>${playerSummaryRatings(detail)}</div>${playerCardEvidence(detail)}${options.actions || ""}</section>
    ${extension ? extensionNegotiationPage(extension.room, extension.selectedPlayerId, extension.response, detail) : ""}
    <section class="player-card-page player-card-page--overview" data-player-page="${pageOffset}" data-page-title="${detail.is_prospect ? "College Season & Games" : "Season, Games & Contract"}" aria-label="Season statistics, recent games, game score and contract">
      ${detail.scouting_profile && !detail.college_profile ? scoutingProfileStrip(detail.scouting_profile) : playerSeasonStrip(season, detail.career_seasons || [])}
      ${detail.college_profile ? collegeProfileStrip(detail.college_profile, detail.scouting_profile) : detail.scouting_profile ? "" : `<section class="approved-card-panel player-page-game-log"><header>Recent Games · Last 5</header><div class="player-page-table-scroll"><table><thead><tr>${gameFields.map(([label]) => `<th scope="col">${label}</th>`).join("")}</tr></thead><tbody>${gameRows || `<tr><td class="player-page-empty" colspan="${gameFields.length}">No recent games yet.</td></tr>`}</tbody></table></div></section>
      <section class="approved-card-panel player-page-score-panel"><header>Game Score · Last 15 Games</header>${approvedGameScoreChart(detail)}</section>`}
      ${detail.is_prospect ? "" : `<div class="player-page-contract"><section class="approved-card-panel approved-cap-panel"><header>${gameArtworkTitle("Four-Year Payroll Share", "payroll")}</header>${approvedCapShareChart(detail)}</section></div>`}
      <section class="approved-card-panel approved-player-spatial player-overview-court"><header>Court Influence</header>${spatialHeatmapMarkup(detail.spatial_profile, { compact: true })}</section>
    </section>
    <section class="player-card-page player-card-page--details${detail.inputs_profile ? " player-card-page--layers" : ""}" data-player-page="${pageOffset + 1}" data-page-title="Ratings & Profiles" aria-label="Complete ratings and radar profiles" hidden>
      ${detail.inputs_profile ? inputsProfilePage(detail.inputs_profile) : `<div class="approved-player-identity-ratings" aria-label="Complete ratings">${playerCardGroupedRatings(ratings, detail, {
        Offense: radar("Offensive shape", offenseAxes, "offense"),
        Defense: radar("Defense / physical", defenseAxes, "defense")
      })}</div>`}
    </section>
    ${detail.is_prospect ? "" : `<section class="player-card-page player-card-page--health" data-player-page="${pageOffset + 2}" data-page-title="Health & Injury Outlook" aria-label="Injury body map and outlook" hidden>${injuryBodyMapPanel(detail)}</section>`}
  </div>`;
}

function wirePlayerCardPages(card, entry) {
  const root = card.querySelector('[data-player-pages]');
  if (!root) return;
  const pages = [...root.querySelectorAll('[data-player-page]')];
  if (!pages.length) return;
  const showPage = index => {
    entry.page = ((index % pages.length) + pages.length) % pages.length;
    pages.forEach((page, pageIndex) => { page.hidden = pageIndex !== entry.page; });
    root.dataset.page = String(entry.page);
    root.querySelector('[data-player-page-title]').textContent = pages[entry.page].dataset.pageTitle;
    root.querySelector('[data-player-page-count]').textContent = `${entry.page + 1}/${pages.length}`;
  };
  card._showPlayerCardPage = showPage;
  card._playerCardPageRoot = root;
  showPage(Number.isInteger(entry.page) ? entry.page : 0);
  const updateSeason = (strip, selected) => {
    const career = JSON.parse(strip.dataset.playerCareerOptions || '[]');
    const season = career.find(row=>row.season===selected);
    if (season) strip.outerHTML=playerSeasonStrip(season,career);
  };
  const strip=root.querySelector('[data-player-career-options]');
  if (strip && entry.careerSeason) updateSeason(strip,entry.careerSeason);
  root.addEventListener('click',event=>{
    const choice=event.target.closest('[data-player-career-season]');
    if (!choice) return;
    event.preventDefault();
    entry.careerSeason=choice.dataset.playerCareerSeason;
    updateSeason(choice.closest('[data-player-career-options]'),entry.careerSeason);
    root.querySelector('.player-career-picker summary')?.focus();
  });
  root.addEventListener('keydown',event=>{
    if (event.key==='Escape') {
      const picker=root.querySelector('.player-career-picker[open]');
      if (picker) { picker.open=false; picker.querySelector('summary').focus(); event.preventDefault(); }
    }
  });
  if (!card._playerCardPageClickHandler) {
    card._playerCardPageClickHandler = event => {
      const button = event.target.closest('[data-player-page-step]');
      const activeRoot = card._playerCardPageRoot;
      if (!button || !activeRoot?.contains(button)) return;
      event.preventDefault();
      card._showPlayerCardPage?.(entry.page + Number(button.dataset.playerPageStep));
      // Keep the same card DOM, size, scroll position, and selection when paging.
      wirePlayerGameScoreCharts();
    };
    card.addEventListener('click', card._playerCardPageClickHandler);
  }
}

document.addEventListener('click',event=>{
  document.querySelectorAll('.player-career-picker[open]').forEach(picker=>{
    if (!picker.contains(event.target)) picker.open=false;
  });
});

function clipboardPlayerCardWindows(cardId = null) {
  const saveId = String(state.currentSave || "");
  return (state.clipboardPlayerCards || []).filter(entry => entry.saveId === saveId && (!cardId || entry.id === cardId)).map(entry => {
    const card = document.createElement("div");
    card.className = `clipboard-player-card${entry.kind === "fantasy" ? " clipboard-player-card--fantasy" : entry.kind === "extension" ? " clipboard-player-card--extension" : entry.kind === "coach" ? " clipboard-player-card--coach" : ""}`;
    if(entry.kind==="extension") card.dataset.extensionEntryId=entry.id;
    card.innerHTML = entry.body;
    wirePlayerCardPages(card, entry);
    if (entry.context?.tradeReturn) {
      card.addEventListener("click", event => {
        if (event.target.closest('[data-player-return-trade]')) returnToPlayerTradeContext(entry.context.tradeReturn);
      });
    }
    if (entry.kind === "extension") {
      const redraw=()=>{ entry.body=extensionNegotiationBody(entry.context.room,entry.context.selectedPlayerId,entry.context.response,entry.context.detail); card.innerHTML=entry.body; card.classList.remove("has-extension-result"); wirePlayerCardPages(card,entry); wireExtensionNegotiationModal(card,entry.context,redraw,close); if(entry.context.outcome) mountPlayerExtensionOutcome(card,entry.context,close); };
      const close=async()=>{ const applied=Boolean(entry.context?.extensionApplied); if(applied) entry.context.extensionApplied=false; card.closest('.card-board-window')?.querySelector('[data-board-close]')?.click(); state.clipboardPlayerCards=state.clipboardPlayerCards.filter(item=>item.id!==entry.id); if(applied){ showToast(`${entry.context.outcome?.message||"Player signed an extension."}`); await refreshHome(); } };
      wireExtensionNegotiationModal(card,entry.context,redraw,close);
      if(entry.context?.outcome) mountPlayerExtensionOutcome(card,entry.context,close);
    } else if (entry.kind === "freeAgent") {
      card.addEventListener("click", event => {
        const button = event.target.closest("[data-fa-card-negotiate]");
        if (button) openFreeAgentNegotiation(button.dataset.faCardNegotiate || "");
      });
    } else if (entry.kind === "fantasy") {
      card.addEventListener("click", async event => {
        const select = event.target.closest("[data-fantasy-card-select]");
        if (select) {
          state.selectedFantasyPlayer = select.dataset.fantasyCardSelect || "";
          rememberFantasyBoardScroll();
          renderDashboard();
          showToast("Player selected for the draft.");
          return;
        }
        const watch = event.target.closest("[data-fantasy-card-watch]");
        if (watch) {
          const playerId = watch.dataset.fantasyCardWatch || "";
          await fantasyDraftToggleWatchlist(playerId);
          await fantasyPlayerCard(playerId);
        }
      });
    }
    const isFantasyCard = entry.kind === "fantasy";
    const isExtensionCard = entry.kind === "extension";
    const sizeRevision = Number(entry.sizeRevision) || 0;
    return {
      id:entry.id,
      title:entry.title,
      card,
      width:isExtensionCard ? (sizeRevision >= 8 && entry.width ? entry.width : 1530) : sizeRevision >= 4 && entry.width ? entry.width : isFantasyCard ? 1120 : 1530,
      height:sizeRevision >= 4 && entry.height ? entry.height : isFantasyCard ? 700 : 900,
      initialScale:isExtensionCard ? .626166 : isFantasyCard || entry.kind === "coach" ? 1 : .7,
      minScale:isExtensionCard ? .5 : undefined,
      sizeRevision:isExtensionCard ? 9 : 4,
      galleryVisible:false,
    };
  });
}

async function focusOpenExtensionCard(playerId) {
  const entry = state.clipboardPlayerCards.find(item => item.saveId === String(state.currentSave || "") && item.key === `extension:${playerId}` && (window.CardBoard?.isOpen(item.id) ?? item.windowOpen));
  if (!entry) return false;
  closeAllModals();
  if (state.view !== "dashboard") {
    state.view = "dashboard";
    state.dashboardTeam = userTeam();
    state.dashboardTab = "overview";
    await ensureViewData(true);
    render();
  }
  return Boolean(window.CardBoard?.open(entry.id));
}

async function openPlayerCardOnClipboard({key, title, body, kind = "player", context = null}) {
  const playerId = /^(?:dashboard|free-agent|extension):(.+)$/.exec(key)?.[1];
  if (playerId && await focusOpenExtensionCard(playerId)) return;
  closeAllModals();
  const saveId = String(state.currentSave || "");
  if (!saveId) return;
  let entry = state.clipboardPlayerCards.find(item => item.saveId === saveId && item.key === key);
  if (!entry && kind === "extension") entry = state.clipboardPlayerCards.find(item => item.saveId === saveId && item.key === `dashboard:${context?.selectedPlayerId}`);
  if (!entry) {
    state.clipboardPlayerCardSequence += 1;
    entry = {id:`player-card-${state.clipboardPlayerCardSequence}`, saveId, key, title, body, kind, width:kind === "coach" ? 900 : kind === "fantasy" ? 1120 : 1530, height:kind === "coach" ? 252 : kind === "fantasy" ? 700 : 900, sizeRevision:kind === "extension" ? 9 : 4};
    state.clipboardPlayerCards.push(entry);
  } else {
    const extensionSizeUpdate = kind === "extension" && (Number(entry.sizeRevision) || 0) < 9
      ? {sizeRevision:9}
      : {};
    Object.assign(entry, {key, title, body, kind, ...extensionSizeUpdate});
  }
  entry.context=context;
  if(kind==="extension") entry.page=0;

  if (state.view !== "dashboard") {
    state.view = "dashboard";
    state.dashboardTeam = userTeam();
    state.dashboardTab = "overview";
    await ensureViewData(true);
    render();
  }
  let descriptor = clipboardPlayerCardWindows(entry.id)[0];
  let opened = descriptor && window.CardBoard?.addCard(descriptor);
  if (!opened) {
    render();
    descriptor = clipboardPlayerCardWindows(entry.id)[0];
    opened = descriptor && window.CardBoard?.addCard(descriptor);
  }
  if (!opened) showToast("Player cards are available on the season card workspace.", true);
  wirePlayerGameScoreCharts();
}

async function dashboardPlayerCard(playerId) {
  if (await focusOpenExtensionCard(playerId)) return;
  const tradeReturn = ["tradeRoom", "tradeOffers"].includes(state.modal?.kind) ? {...state.modal, activeTab:state.tradeTab} : null;
  const player = rosterRows(state.data.dashboard || {}).find((row) => String(row.id) === String(playerId));
  const detail = await loadPlayerCardDetail(playerId);
  if (!detail) return;
  const returnLabel = tradeReturn?.kind === "tradeOffers" ? "Back to Offers" : tradeReturn?.activeTab === "finder" ? "Back to Trade Finder" : "Back to Trade Builder";
  await openPlayerCardOnClipboard({
    key:`dashboard:${playerId}`,
    title:`${detail.name || player?.name || "Player"} · Player Card`,
    body:approvedPlayerCardBody(detail, {name:player?.name, ratings:player?.display_ratings || player?.ratings,
      actions:tradeReturn ? `<button type="button" class="ui-command player-page-return" data-player-return-trade>${returnLabel}</button>` : ""}),
    context:tradeReturn ? {tradeReturn} : null,
  });
}

async function freeAgentPlayerCard(playerId) {
  if (await focusOpenExtensionCard(playerId)) return;
  const player = freeAgencyCandidate(playerId);
  if (!player) return;
  const detail = await loadPlayerCardDetail(playerId);
  if (!detail) return;
  await openPlayerCardOnClipboard({
    key:`free-agent:${playerId}`,
    title:`${player.name || "Free Agent"} · Player Card`,
    kind:"freeAgent",
    body:approvedPlayerCardBody(
      { ...detail, ratings: player.ratings || detail.ratings, name: player.name },
      { actions: `<button type="button" class="approved-player-primary-action" data-fa-card-negotiate="${escapeAttr(player.id)}">Build Offer</button>` },
    ),
  });
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
      <div class="free-agent-comparison-overview">${playerSummaryRatings(player)}<b>${money(player.ask_millions)} ask</b></div>
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
  const guaranteed = document.getElementById("faGuaranteed")?.checked !== false;
  const result = await action("submit_free_agent_offer", { ...savePayload(), player_id: player, team: userTeam(), years, guaranteed, aav_millions: aav, allow_tax_exceed: exclusive, auto_apply: true, seed: 7 });
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

function expandedStaffMarkup(report, slots, market) {
  const portraits = coachPortraitAssignments(market);
  // Use the dashboard's raw slots, not the room's separate derived grades.
  const currentSlots = report.dashboard_staff_slots || slots.map(({grade, ...slot}) => slot);
  const dash = {...(state.data.dashboard || {}), staff:currentSlots, staff_slots:currentSlots, staff_budget:report.budget, staff_action_permissions:report.staff_action_permissions};
  state.data.dashboard = dash;
  return `<div class="season-staff-management">
    <section class="season-staff-current" aria-label="Current coaching staff">${seasonStaffCard(dash, false, {actions:true, available:report.budget?.available_millions ?? null})}</section>
    <section class="season-staff-market" aria-label="Available coaching staff">
      <header class="season-staff-market-head"><h3>Available Staff</h3><select id="staffSlot" aria-label="Filter available staff by role"><option value="">All roles</option>${["head_coach", "offensive_coordinator", "defensive_coordinator", "performance_lead", "development_lead", "scouting_lead"].map(slot => `<option value="${slot}" ${slot === state.staffSlot ? "selected" : ""}>${staffRoleLabel(slot)}</option>`).join("")}</select></header>
      <div class="season-staff-market-list"><div class="season-staff-head"><span>Staff Member</span><span>Grade</span><span>Asking Contract</span><span aria-hidden="true"></span></div>${market.map(row => seasonStaffRowMarkup(row, portraits.get(staffIdentity(row)), {actions:true, candidate:true, permissions:report.staff_action_permissions})).join("") || '<div class="empty">No available staff for this role.</div>'}</div>
    </section>
  </div>`;
}

let staffRoomRefreshId = 0;
async function refreshFilteredStaffRoom(target) {
  const requestId = ++staffRoomRefreshId;
  const currentSave = state.currentSave;
  const slot = state.staffSlot;
  const wasExpanded = target.classList.contains("season-staff-expanded");
  try {
    const room = await action("staff_room", {...savePayload(), team:userTeam(), slot:slot || undefined, limit:30});
    if (requestId !== staffRoomRefreshId || currentSave !== state.currentSave || slot !== state.staffSlot) return;
    state.data.staff = room;
    if (target.isConnected && wasExpanded === target.classList.contains("season-staff-expanded")) renderStaff(target);
  } catch (error) {
    if (requestId === staffRoomRefreshId && currentSave === state.currentSave) showToast(error.message || "Available staff could not be refreshed.", true);
  }
}

function renderStaff(target = els.content) {
  const room = state.data.staff || {};
  const report = room.team_report || {};
  const slots = report.gameplay_staff_slots || [];
  const market = [...(room.market?.candidates || [])].sort((a,b)=>Number(b.grade||0)-Number(a.grade||0));
  target.innerHTML = target.classList.contains("season-staff-expanded") ? expandedStaffMarkup(report, slots, market) : `
    <div class="staff-workspace">
      <section class="section featured">
        <div class="section-head"><h3>Coaching Staff</h3><span>${money(report.budget?.annual_spend_millions)} / ${money(report.budget?.annual_budget_millions)}</span><span class="pill">${signedMoney(report.budget?.available_millions)} available</span></div>
        ${table(["Role", "Name", "Grade", "Contract", ""], slots, (row) => [rowLabel(row.slot || row.role), row.name, row.grade, `${money(row.contract?.annual_salary_millions)} x ${row.contract?.years_remaining || 0}`, `<button data-fire-slot="${escapeAttr(row.slot)}" ${staffActionAttributes(row.slot, "fire", report.staff_action_permissions)}>Fire</button>`])}
      </section>
      <section class="section">
        <div class="section-head">
          <h3>Staff Market</h3>
          <select id="staffSlot">
            <option value="">All roles</option>
            ${["head_coach", "offensive_coordinator", "defensive_coordinator", "development_lead", "scouting_lead", "performance_lead"].map((slot) => `<option value="${slot}" ${slot === state.staffSlot ? "selected" : ""}>${rowLabel(slot)}</option>`).join("")}
          </select>
        </div>
        ${table(["Name", "Role", "Grade", "Specialty", "Asking salary", "Years", ""], market, (candidate) => [candidate.name, rowLabel(candidate.slot), html(`<span class="staff-grade-cell"><i><b style="${performanceBarStyle(Number(candidate.grade||0))}"></b></i>${draftMetric(candidate.grade)}</span>`), candidate.archetype || "—", money(candidate.asking_salary_millions), candidate.asking_years || 2, html(`<button type="button" data-staff-id="${escapeAttr(candidate.id)}" ${staffActionAttributes(candidate.slot, "negotiate", report.staff_action_permissions)}>Negotiate</button>`)], "staff-market")}
      </section>
    </div>`;
  wireDashboardStaffCards(target);
  target.querySelector("#staffSlot").addEventListener("change", async (event) => {
    state.staffSlot = event.target.value;
    await refreshFilteredStaffRoom(target);
  });
  target.querySelectorAll("[data-staff-id]").forEach((button) => {
    button.addEventListener("click", () => openDashboardStaffNegotiation(button.dataset.staffId));
  });
  target.querySelectorAll("[data-fire-slot]").forEach((button) => {
    button.addEventListener("click", () => fireStaff(button.dataset.fireSlot, target));
  });
}

async function setStaffCardExpanded(expanded, card) {
  if (!card) return;
  card.classList.toggle("season-staff-expanded", expanded);
  if (!expanded) {
    card.innerHTML = seasonStaffCard(state.data.dashboard || {}, false);
    wireDashboardStaffCards(card);
    return;
  }
  if (!state.data.staff || String(state.data.staff.market?.slot || "") !== state.staffSlot) {
    card.innerHTML = `<div class="season-staff-expanded-loading">Loading staff room...</div>`;
    try {
      const currentSave = state.currentSave;
      state.data.staff = await action("staff_room", {...savePayload(), team:userTeam(), slot:state.staffSlot || undefined, limit:30});
      if (state.currentSave !== currentSave || !card.isConnected || !card.classList.contains("season-staff-expanded")) return;
    } catch (error) {
      if (card.isConnected && card.classList.contains("season-staff-expanded")) {
        card.innerHTML = `<div class="season-staff-expanded-loading">Staff room unavailable.</div>`;
      }
      showToast(error.message || String(error), true);
      return;
    }
  }
  if (card.isConnected && card.classList.contains("season-staff-expanded")) {
    renderStaff(card);
    GameInterface.enhance(card);
  }
}

async function negotiateStaff(staffId, slot, ask, years) {
  const result = await action("negotiate_staff", { ...savePayload(), team: userTeam(), staff_id: staffId, slot, salary_millions: ask, years, seed: 7 });
  const negotiation = result.negotiation;
  if (negotiation.accepted) {
    const hired = await action("hire_staff", { ...savePayload(), negotiation_id: negotiation.id });
    showToast(`Staff hire: ${hired.status}`);
    state.data.staff = hired.room;
  } else {
    showToast(negotiation.decision === "reject_season_limit" ? negotiation.notes : `Staff declined: ${negotiation.decision}`, true);
    state.data.staff = result.room;
  }
  renderStaff();
}

async function fireStaff(slot, target = els.content) {
  const currentSave = state.currentSave;
  const result = await action("fire_staff", { ...savePayload(), team: userTeam(), slot });
  if (currentSave !== state.currentSave) return;
  // A mutation response contains an unfiltered market. Keep the visible
  // filtered candidates until a matching room refresh has completed.
  state.data.staff = {...state.data.staff, team_report:result.room?.team_report || state.data.staff?.team_report};
  showToast(result.result?.notes || `Staff move: ${result.status}`, result.status !== "applied");
  await refreshFilteredStaffRoom(target);
}

function dashboardStaffCandidate(staffId) {
  return marketCandidates(state.data.staff?.market).find((candidate) => String(candidate.id || "") === String(staffId || ""));
}

function dashboardCurrentStaff(slot) {
  const dashStaff = staffRows(state.data.dashboard || {});
  const roomStaff = state.data.staff?.team_report?.gameplay_staff_slots || [];
  return [...roomStaff, ...dashStaff].find((staff) => String(staff.slot || staff.role || "") === String(slot || "")) || null;
}

function staffOfferInterestScore(salary, years, askingSalary, askingYears) {
  const salaryPart = 52 * Math.min(1.3, Math.max(0, Number(salary) || 0) / Math.max(Number(askingSalary) || 0, 0.1));
  const yearsPart = 16 * Math.min(1, Math.max(1, Number(years) || 1) / Math.max(1, Number(askingYears) || 1));
  return Math.round(clampNumber(salaryPart + yearsPart, 0, 100));
}

function staffOfferInterestBand(score) {
  return score < 40 ? "low" : score < 70 ? "medium" : "high";
}

function updateStaffOfferInterest(modal = state.modal) {
  if (!modal || modal.kind !== "staffNegotiation") return;
  const root = els.modalRoot.querySelector("[data-staff-offer-interest]");
  const salaryInput = els.modalRoot.querySelector("[data-staff-offer-salary]");
  const yearsInput = els.modalRoot.querySelector("[data-staff-offer-years]");
  const meter = root?.querySelector("[role='progressbar']");
  const bar = root?.querySelector("[data-staff-interest-bar]");
  const value = root?.querySelector("[data-staff-interest-value]");
  if (!root || !salaryInput || !yearsInput || !meter || !bar || !value) return;
  const salary = Math.min(Number(modal.maxOffer || 0), Math.max(0, Number(salaryInput.value) || 0));
  const years = clampNumber(Number(yearsInput.value) || 1, 1, 5);
  const score = staffOfferInterestScore(salary, years, modal.askingSalary, modal.askingYears);
  const band = staffOfferInterestBand(score);
  root.classList.remove("is-low", "is-medium", "is-high");
  root.classList.add(`is-${band}`);
  bar.style.width = `${score}%`;
  value.textContent = `${score}%`;
  meter.setAttribute("aria-valuenow", String(score));
  meter.setAttribute("aria-valuetext", `${score}% estimated interest`);
}

async function openDashboardStaffNegotiation(staffId) {
  const candidate = dashboardStaffCandidate(staffId);
  if (!candidate) return showToast("That staff candidate is no longer available.", true);
  const slot = String(candidate.slot || candidate.role_preference || "");
  const permission = staffActionPermission(slot);
  if (permission.can_negotiate === false) return showToast(permission.negotiate_reason, true);
  const current = dashboardCurrentStaff(slot);
  const currentSave = state.currentSave;
  const info = current?.id ? await action("coach_card", {...savePayload(), staff_id:current.id}) : {};
  if (state.currentSave !== currentSave || (current?.id && !info)) return;
  const currentCoach = info.staff || current;
  const budget = state.data.staff?.team_report?.budget || state.data.dashboard?.staff_budget || {};
  const currentSalary = staffAav(current || {});
  const spend = Number(budget.annual_spend_millions ?? staffBudgetSummary(staffRows(state.data.dashboard || {})).used ?? 0);
  const maxBudget = Number(budget.annual_budget_millions ?? staffBudgetSummary(staffRows(state.data.dashboard || {})).max ?? 0);
  const maxOffer = Math.max(0, Math.floor((maxBudget - Math.max(0, spend - currentSalary) + 0.000001) * 10) / 10);
  const askingSalary = Number(candidate.asking_salary_millions || staffAav(candidate) || 0);
  const askingYears = Number(candidate.asking_years || staffYears(candidate) || 1);
  const initialOffer = Math.min(Math.round(askingSalary * 10) / 10, maxOffer);
  const initialYears = Math.max(1, Math.min(5, askingYears));
  const initialInterest = staffOfferInterestScore(initialOffer, initialYears, askingSalary, askingYears);
  const initialInterestBand = staffOfferInterestBand(initialInterest);
  const upgrade = Number(staffGrade(candidate) || 0) - Number(staffGrade(currentCoach || {}) || 0);
  const currentPortraits = coachPortraitAssignments(staffRows(state.data.dashboard || {}));
  const candidatePortraits = coachPortraitAssignments(marketCandidates(state.data.staff?.market));

  state.modal = {
    kind: "staffNegotiation",
    title: "Staff Negotiation",
    staffId: String(candidate.id || ""),
    slot,
    maxOffer,
    askingSalary,
    askingYears,
    body: `<div class="staff-negotiation-profiles">
      <section aria-label="Candidate staff card">${coachProfileCardMarkup(candidate, candidatePortraits.get(staffIdentity(candidate)), {...info, staff:candidate}, {candidate:true, context:"Candidate", gradeChange:current ? upgrade : null})}</section>
      ${currentCoach ? `<div class="staff-negotiation-swap" role="img" aria-label="Hire ${escapeAttr(staffName(candidate))} to replace ${escapeAttr(staffName(currentCoach))}" title="Staff replacement"><svg viewBox="0 0 32 28" aria-hidden="true"><path d="M10 24V4m-6 6 6-6 6 6M22 4v20m-6-6 6 6 6-6"/></svg></div><section aria-label="Current staff card">${coachProfileCardMarkup(currentCoach, currentPortraits.get(staffIdentity(currentCoach)), info, {context:"Current coach"})}</section>` : `<p class="staff-negotiation-vacancy">This staff position is vacant.</p>`}
    </div>
    <section class="staff-negotiation-budget" aria-label="Staff budget">
      <div><span>Current payroll</span><strong>${money(spend)}</strong></div>
      <div><span>Staff budget</span><strong>${money(maxBudget)}</strong></div>
      <div><span>Maximum offer</span><strong>${money(maxOffer)}</strong></div>
    </section>
    <form class="staff-contract-offer" data-staff-negotiation-form>
      <header>Contract Offer</header>
      <div class="staff-contract-controls">
      <label>Annual salary
        <div class="money-input"><span>$</span><input type="number" min="0.1" max="${maxOffer.toFixed(1)}" step="0.1" value="${initialOffer.toFixed(1)}" data-staff-offer-salary required><span>M</span></div>
      </label>
      <span class="staff-contract-times" aria-hidden="true">×</span>
      <label>Years
        <input type="number" min="1" max="5" step="1" value="${initialYears}" data-staff-offer-years required>
      </label>
      <div class="staff-offer-interest is-${initialInterestBand}" data-staff-offer-interest>
        <div><span>Coach interest</span><strong data-staff-interest-value>${initialInterest}%</strong></div>
        <i role="progressbar" aria-label="Estimated coach signing interest" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${initialInterest}" aria-valuetext="${initialInterest}% estimated interest"><b data-staff-interest-bar style="width:${initialInterest}%"></b></i>
      </div>
      <button type="submit" ${maxOffer < 0.1 ? "disabled" : ""}>${current ? `Offer &amp; Replace ${escapeHtml(staffName(current))}` : "Offer &amp; Hire"}</button>
      </div>
      ${askingSalary > maxOffer + 0.001 ? `<p class="staff-budget-warning">Asking salary exceeds your budget. A lower offer may be declined.</p>` : ""}
    </form>`,
  };
  renderModal();
}

async function submitDashboardStaffNegotiation() {
  const modal = state.modal;
  if (!modal || modal.kind !== "staffNegotiation" || modal.submitting || modal.outcome) return;
  const salaryInput = els.modalRoot.querySelector("[data-staff-offer-salary]");
  const yearsInput = els.modalRoot.querySelector("[data-staff-offer-years]");
  const maxOffer = Number(modal.maxOffer || 0);
  const salary = Math.min(maxOffer, Math.max(0.1, Number(salaryInput?.value || 0)));
  const years = Math.max(1, Math.min(5, Number(yearsInput?.value || 1)));
  if (salary > maxOffer + 0.001 || maxOffer < 0.1) return showToast("That offer exceeds the available staff budget.", true);
  modal.submitting = true;
  showStaffNegotiationOutcome(modal, {kind:"pending", title:"Sending offer…", message:"Waiting for the staff member’s decision."});
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
      state.data.staff = result.room;
      const blocked = negotiation.decision === "reject_season_limit";
      modal.staffNeedsRefresh = blocked;
      modal.submitting = false;
      showStaffNegotiationOutcome(modal, {
        kind:"declined", title:blocked || negotiation.decision === "reject_budget" ? "Offer blocked" : "Offer declined",
        message:blocked ? negotiation.notes : negotiation.decision === "reject_budget" ? "This offer exceeds the available staff budget." : "The staff member declined this contract. Adjust the salary or years to make another offer.",
        allowRetry:!blocked,
      });
      return;
    }
    const hired = await action("hire_staff", { ...savePayload(), negotiation_id: negotiation.id });
    if (hired.status !== "applied") {
      state.data.staff = hired.room;
      modal.staffNeedsRefresh = true;
      modal.submitting = false;
      showStaffNegotiationOutcome(modal, {kind:"declined", title:"Replacement not completed", message:hired.result?.notes || "The staff replacement could not be completed. Close this result to refresh the staff list.", allowRetry:false});
      return;
    }
    state.data.staff = hired.room;
    modal.staffNeedsRefresh = true;
    modal.submitting = false;
    showStaffNegotiationOutcome(modal, {kind:"accepted", title:"Offer accepted", message:`${staffName(negotiation.candidate || {})} is now your ${staffRoleLabel(modal.slot)}.`});
  } catch (error) {
    modal.staffNeedsRefresh = true;
    modal.submitting = false;
    showStaffNegotiationOutcome(modal, {kind:"declined", title:"Offer not confirmed", message:error.message || "The offer could not be confirmed. Close this result to refresh the staff list.", allowRetry:false});
  }
}

function staffNegotiationOutcomeMarkup(outcome) {
  const accepted = outcome.kind === "accepted";
  const pending = outcome.kind === "pending";
  const handshake = `<svg class="staff-result-handshake" viewBox="0 0 400 240" aria-hidden="true">
    <g class="staff-handshake-shake" stroke="#495968" stroke-width="3" stroke-linejoin="round" stroke-linecap="round">
      <g class="staff-hand staff-hand-left">
        <path class="staff-hand-sleeve" d="M24 113 86 79 121 140 59 175Z"/><path class="staff-hand-cuff" d="m86 79 21-11 35 61-21 11Z"/>
        <path class="staff-hand-skin" d="m110 77 30-16q15-8 29 0l42 23 38 44q6 8 0 15l-8 7q-1 11-13 15l-8 9q-8 8-17 1l-10 6q-9 5-17-2l-43-40-8-4Z"/>
        <path class="staff-hand-detail" d="m177 128 43 46m-28-62 47 49m-78-19 36 36"/>
      </g>
      <g class="staff-hand staff-hand-right">
        <path class="staff-hand-sleeve" d="m376 113-62-34-35 61 62 35Z"/><path class="staff-hand-cuff" d="m314 79-21-11-35 61 21 11Z"/>
        <path class="staff-hand-skin" d="m290 77-26-15q-12-6-25 0l-23 13h-17q-9 0-15 6l-24 24q-7 8 0 15 7 7 15 0l24-20 23 10 33 31 20-7Z"/>
        <path class="staff-hand-detail" d="m199 100 12-9m42 41 11-9"/>
      </g>
    </g>
  </svg>`;
  const mark = `<svg class="staff-result-mark" viewBox="0 0 240 240" aria-hidden="true">${accepted
    ? '<circle class="staff-result-halo" cx="120" cy="120" r="101"/><path class="staff-result-check" pathLength="1" d="m56 121 43 43 86-91"/>'
    : '<path class="staff-result-cross staff-result-cross-first" pathLength="1" d="m32 32 176 176"/><path class="staff-result-cross staff-result-cross-second" pathLength="1" d="m208 32-176 176"/>'}</svg>`;
  return `<div class="staff-result-art" aria-hidden="true">${pending ? '<span class="staff-result-pending"></span>' : `${accepted ? handshake : ""}${mark}`}</div>
    <div class="staff-result-copy" role="status" aria-live="polite" aria-atomic="true"><h2>${escapeHtml(outcome.title)}</h2><p>${escapeHtml(outcome.message || "")}</p></div>
    ${pending ? "" : `<button type="button" data-staff-result-dismiss>${accepted ? "Continue" : outcome.allowRetry ? "Revise offer" : "Close"}</button>`}`;
}

function showStaffNegotiationOutcome(modal, outcome) {
  modal.outcome = outcome;
  if (state.modal !== modal) return;
  mountStaffNegotiationOutcome(modal);
}

function mountStaffNegotiationOutcome(modal) {
  const body = els.modalRoot.querySelector(".modal-staff-negotiation > .modal-body");
  const content = body?.querySelector(".staff-negotiation-content");
  if (!body || !content || !modal.outcome) return;
  body.querySelector(".staff-negotiation-result")?.remove();
  body.classList.add("has-staff-result");
  content.inert = true;
  const close = els.modalRoot.querySelector("[data-close-modal]");
  if (close) close.disabled = Boolean(modal.submitting);
  const overlay = document.createElement("div");
  overlay.className = `staff-negotiation-result staff-outcome--${modal.outcome.kind}`;
  overlay.setAttribute("role", "region");
  overlay.setAttribute("aria-label", "Staff contract result");
  overlay.tabIndex = -1;
  overlay.innerHTML = staffNegotiationOutcomeMarkup(modal.outcome);
  body.append(overlay);
  const dismiss = overlay.querySelector("[data-staff-result-dismiss]");
  dismiss?.addEventListener("click", () => {
    if (state.modal !== modal || modal.submitting) return;
    if (modal.outcome.kind === "accepted" || !modal.outcome.allowRetry) return closeModal();
    delete modal.outcome;
    overlay.remove();
    body.classList.remove("has-staff-result");
    content.inert = false;
    body.querySelector("[data-staff-offer-salary]")?.focus({preventScroll:true});
  });
  (dismiss || overlay).focus({preventScroll:true});
}

async function fireDashboardStaff(slot, name) {
  const permission = staffActionPermission(slot);
  if (permission.can_fire === false) return showToast(permission.fire_reason, true);
  if (!window.confirm(`Fire ${name}? An interim ${rowLabel(slot)} will take over immediately.`)) return;
  try {
    const result = await action("fire_staff", { ...savePayload(), team: userTeam(), slot, reason: "user decision" });
    showToast(result.status === "applied" ? `${name} fired. An interim has been appointed.` : result.result?.notes || `Staff move: ${result.status}`, result.status !== "applied");
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

  return `<button class="staff-role-button" data-staff-role="${escapeAttr(role)}" data-staff-name="${escapeAttr(name)}" ${editable ? staffActionAttributes(role, "fire") : "disabled"}>
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
        return `<button type="button" class="staff-market-candidate" data-staff-candidate="${escapeAttr(candidate.id || "")}" data-staff-candidate-slot="${escapeAttr(role)}" ${staffActionAttributes(role, "negotiate")}>
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

function renderCalendar(target = els.content, options = {}) {
  const current = String(state.home?.save?.current_date || "").slice(0,10);
  const month = state.calendarMonth || current.slice(0,7);
  const team = teamLabel(options.team || userTeam());
  const dataKey = options.dataKey || "calendar";
  const calendar = state.data[dataKey] || {};
  const games = calendar.games || calendar.calendar || [];
  const cells = monthCalendarCells(month);
  const label = new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-US",{month:"long",year:"numeric",timeZone:"UTC"});
  target.innerHTML = `<section class="clipboard-calendar" aria-label="${escapeAttr(team)} calendar">
    <header class="clipboard-calendar-head"><h2>${escapeHtml(label)}</h2><div>
      <button type="button" data-clipboard-calendar-step="-1" aria-label="Previous month" title="Previous month">&lt;</button>
      <button type="button" data-clipboard-calendar-today>Today</button>
      <button type="button" data-clipboard-calendar-step="1" aria-label="Next month" title="Next month">&gt;</button>
    </div></header>
    ${tradeDeadlineCalendarNotice(month)}
    <div class="clipboard-calendar-weekdays">${["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(day=>`<span>${day}</span>`).join("")}</div>
    <div class="clipboard-calendar-grid" style="--calendar-weeks:${cells.length/7}">${cells.map(cell=>clipboardCalendarDay(cell,games,current,team)).join("")}</div>
  </section>`;
  target.querySelectorAll("[data-box-score]").forEach((button) => {
    button.addEventListener("click", () => openBoxScore(button.dataset.boxScore));
  });
  target.querySelectorAll("[data-clipboard-calendar-step], [data-clipboard-calendar-today]").forEach(button=>button.addEventListener("click",async()=>{
    const date = new Date(`${month}-01T00:00:00Z`);
    date.setUTCMonth(date.getUTCMonth()+Number(button.dataset.clipboardCalendarStep || 0));
    const nextMonth = button.hasAttribute("data-clipboard-calendar-today") ? current.slice(0,7) : date.toISOString().slice(0,7);
    const save = state.currentSave;
    target.querySelectorAll(".clipboard-calendar-head button").forEach(control=>control.disabled=true);
    try {
      const result = await action("calendar",{...savePayload(),from_date:`${nextMonth}-01`,through_date:monthEndDate(`${nextMonth}-01`)});
      if (!target.isConnected || save !== state.currentSave) return;
      state.calendarMonth = nextMonth;
      state.data[dataKey] = result;
      renderCalendar(target, options);
      GameInterface.enhance(target);
    } catch(error) {
      showToast(error.message || String(error),true);
    } finally {
      if (target.isConnected) target.querySelectorAll(".clipboard-calendar-head button").forEach(control=>control.disabled=false);
    }
  }));
}

function clipboardCalendarDay(cell, games, current, team) {
  if (!cell.date) return `<div class="clipboard-calendar-day blank" aria-hidden="true"></div>`;
  const game = games.filter(game=>String(game.date || "").slice(0,10) === cell.date && [teamLabel(game.home || game.home_team),teamLabel(game.away || game.away_team)].includes(team))
    .sort((a,b)=>Number(Boolean(scoreLine(b)))-Number(Boolean(scoreLine(a))))[0];
  const past = cell.date < current;
  const completed = Boolean(game && scoreLine(game));
  const gameId = game?.game_id || game?.id;
  const opponent = game ? seasonGameOpponent(game,team) : "";
  const logo = opponent ? teamLogoSrc(opponent) : "";
  const home = game && teamLabel(game.home || game.home_team) === team;
  const score = completed ? seasonGameScore(game,team) : "";
  const displayScore = score || (past ? "Not played" : "");
  const clickable = completed && gameId;
  const tag = clickable ? "button" : "div";
  return `<${tag} class="clipboard-calendar-day${past ? " past" : ""}${cell.date === current ? " today" : ""}${completed ? " completed" : ""}${cell.date === tradeDeadlineDate() ? " trade-deadline-day" : ""}" ${clickable ? `type="button" data-box-score="${escapeAttr(gameId)}" aria-label="Box score: ${escapeAttr(opponent)} ${cell.date} ${escapeAttr(score)}"` : ""}>
    <span class="clipboard-calendar-date">${Number(cell.date.slice(-2))}${cell.date === current ? `<small>Today</small>` : ""}</span>
    ${cell.date === tradeDeadlineDate() ? '<strong class="trade-deadline-day-label">Trade deadline</strong>' : ""}
    ${game ? `<div class="clipboard-calendar-matchup">${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(opponent)}" />` : ""}<span>${home ? "vs" : "@"} ${escapeHtml(opponent)}</span>${displayScore ? `<strong class="${score.startsWith("W") ? "win" : score.startsWith("L") ? "loss" : ""}">${escapeHtml(displayScore)}</strong>` : ""}</div>` : ""}
  </${tag}>`;
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
        <button id="replayGameTutorial">Replay Tutorial</button>
        <button id="togglePress">${gameSettings.press_conferences_enabled ? "Disable" : "Enable"} Press Conferences</button>
        <button id="leaveGame">Leave Game</button>
      </div>
    </section>`;
  document.getElementById("replayGameTutorial").addEventListener("click", async () => {
    state.view = "dashboard";
    await refreshHome();
    startGameTutorial(true);
  });
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
        <section class="section wide panel-rail">
          ${sectionHead("Bracket")}
          ${playoffBracket(series, room.champion, room.play_in)}
        </section>
      </div>
    </section>`;
  wireViewJumpButtons();
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
    state.data.playoffLeaders = await action("playoff_leaders", { ...savePayload(), stat: "points", limit: PLAYOFF_STATS_LIMIT });
  }
  renderDashboard();
}

async function openPlayerFinderModal() {
  const payload = await action("player_finder", savePayload());
  const previous = state.playerFinder?.saveId === state.currentSave ? state.playerFinder : {};
  state.playerFinder = {payload, saveId:state.currentSave, name:previous.name || "", filters:previous.filters || [], sortField:previous.sortField || "overall", sortDirection:previous.sortDirection || "desc"};
  state.modal = {kind:"playerFinder", title:"Player Finder", body:playerFinderModalBody()};
  renderModal();
}

function playerFinderModalBody() {
  const finder = state.playerFinder || {}, payload = finder.payload || {};
  return `<div class="player-finder-search"><label>Player name<input type="search" data-player-finder-name value="${escapeAttr(finder.name || "")}" placeholder="Search all players…" autocomplete="off"></label><button type="button" class="ui-command" data-player-finder-add>+ Filter</button><span id="playerFinderCount" role="status" aria-live="polite"></span></div><div class="player-finder-filters" data-player-finder-filters>${playerFinderFiltersMarkup()}</div><div class="player-finder-table-wrap" id="playerFinderTableWrap">${playerFinderTable(filteredPlayerFinderRows(payload.rows || []))}</div>`;
}

function playerFinderFields(seasons = []) {
  return [
    ...[["overall","OVR"],["offense","OFF"],["defense","DEF"],["age","Age"],["height_inches","Height (inches)"],["health_risk","Injury risk"],["upside_remaining","Growth runway"],["shooting","Shooting"],["creation","Creation"],["spacing","Spacing"],["passing","Passing"],["rebounding","Rebounding"],["rim_deterrence","Rim protection"],["athleticism","Athleticism"],["release","Release"],["range","Range"],["handle","Handle"],["rim_pressure","Rim pressure"],["def_effort","Defensive effort"],["screen_nav","Screen navigation"],["lateral_agility","Lateral agility"],["stamina","Stamina"],["iq","IQ"],["games","Games played"],["games_missed","Games missed"],["display_mpg","MPG"],["points_per_game","PTS"],["rebounds_per_game","REB"],["assists_per_game","AST"],["steals_per_game","STL"],["blocks_per_game","BLK"],["turnovers_per_game","TO"]].map(([key,label])=>({key,label,type:"number"})),
    ...[["player","Player name"],["team","Team"],["position","Position"]].map(([key,label])=>({key,label,type:"text"})),
    ...seasons.map(season=>({key:season,label:`${shortSeasonLabel(season)} salary ($M)`,type:"number"})),
  ];
}

function playerFinderOperators(field) {
  return ["player","team","position"].includes(field) ? ["contains","=","≠"] : [">","≥","<","≤","=","≠"];
}

function playerFinderFiltersMarkup() {
  const finder=state.playerFinder || {}, fields=playerFinderFields(finder.payload?.seasons || []);
  return (finder.filters || []).map((filter,index)=>`<div class="player-finder-filter" data-finder-filter="${index}"><select data-finder-field aria-label="Filter ${index+1} field">${fields.map(field=>`<option value="${escapeAttr(field.key)}" ${field.key===filter.field?"selected":""}>${escapeHtml(field.label)}</option>`).join("")}</select><button type="button" class="ui-command player-finder-operator" data-finder-operator aria-label="Filter ${index+1} comparison ${escapeAttr(filter.operator)}; click to change" title="Click to change comparison">${escapeHtml(filter.operator)}</button><input data-finder-value aria-label="Filter ${index+1} value" value="${escapeAttr(filter.value)}" inputmode="${["player","team","position"].includes(filter.field)?"text":"decimal"}" placeholder="Value"><button type="button" class="ui-command player-finder-remove" data-finder-remove aria-label="Remove filter ${index+1}" title="Remove filter">×</button></div>`).join("");
}

function filteredPlayerFinderRows(rows) {
  const finder=state.playerFinder || {};
  const normalize=value=>String(value ?? "").normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const query=normalize(finder.name || "").trim();
  const filtered=rows.filter(row=>normalize(row.name).includes(query) && (finder.filters || []).every(filter=>{
    if(!String(filter.value ?? "").trim()) return true;
    const actual=playerFinderValue(row,filter.field);
    if(actual == null || actual === "") return false;
    if(["player","team","position"].includes(filter.field)) {
      const left=normalize(actual),right=normalize(filter.value).trim();
      return filter.operator==="="?left===right:filter.operator==="≠"?left!==right:left.includes(right);
    }
    const left=Number(actual), right=Number(filter.value);
    if(!Number.isFinite(left)||!Number.isFinite(right)) return false;
    return filter.operator===">"?left>right:filter.operator==="≥"?left>=right:filter.operator==="<"?left<right:filter.operator==="≤"?left<=right:filter.operator==="≠"?left!==right:left===right;
  }));
  const key=finder.sortField || "overall", direction=finder.sortDirection==="asc"?1:-1;
  return filtered.sort((a,b)=>{
    const av=playerFinderValue(a,key), bv=playerFinderValue(b,key);
    if(av==null||av==="") return bv==null||bv===""?String(a.name).localeCompare(String(b.name)):1;
    if(bv==null||bv==="") return -1;
    const comparison=typeof av==='number'&&typeof bv==='number'?av-bv:String(av).localeCompare(String(bv),undefined,{numeric:true,sensitivity:'base'});
    return comparison*direction || String(a.name).localeCompare(String(b.name));
  });
}

function playerFinderValue(row,key) {
  if(key==='player') return row.name;
  if(key==='team') return row.team_abbrev;
  if(/^[0-9]{4}-/.test(key)) return row.salary_by_year?.[key];
  if(key==='offense') return Math.round(Number(rating(row,'offense'))*10)/10;
  return row[key] ?? row.ratings?.[key];
}

function playerFinderTable(rows) {
  const finder=state.playerFinder || {};
  const fields=[["player","Player",260],["team","Team",48],["position","Pos",40],["age","Age",36],["height_inches","Height",54],["overall","OVR",104],["offense","OFF",104],["defense","DEF",104],["health_risk","Risk",56],["upside_remaining","Runway",60],["find","Find",58]];
  const head=fields.map(([key,label])=>`<th scope="col" ${key!=="find"?`aria-sort="${finder.sortField===key?(finder.sortDirection==='asc'?'ascending':'descending'):'none'}"`:""}>${key==='find'?label:`<button type="button" data-finder-sort="${key}">${label}${finder.sortField===key?(finder.sortDirection==='asc'?' ↑':' ↓'):''}</button>`}</th>`).join('');
  const body=rows.map(row=>`<tr data-finder-player="${escapeAttr(row.id)}" tabindex="0" aria-label="Open player card for ${escapeAttr(row.name)}"><td><span class="player-finder-identity">${playerHeadshotMarkup(row,'roster-player-headshot') || playerHeadshotMarkup({is_prospect:true},'roster-player-headshot')}${playerNameWithInjuryMarkup(row)}</span></td><td>${teamLogoSrc(row.team_abbrev)?`<span class="player-finder-team-logo" title="${escapeAttr(row.team_abbrev)}"><img src="${escapeAttr(teamLogoSrc(row.team_abbrev))}" alt="${escapeAttr(row.team_abbrev)} logo" loading="lazy" decoding="async"></span>`:escapeHtml(row.team_abbrev || "FA")}</td><td>${escapeHtml(compactPos(row.position))}</td><td>${escapeHtml(row.age == null ? "—" : Math.floor(row.age))}</td><td>${escapeHtml(heightFromRow(row) || "—")}</td>${['overall','offense','defense'].map(key=>`<td>${compactRatingBar(playerFinderValue(row,key))}</td>`).join('')}<td>${injuryRiskBody(row.health_risk,row.injury_body)}</td><td>${row.upside_remaining==null?'—':playerEvidenceRing('Growth runway',row.upside_remaining,5,playerUpsideColor(row.upside_remaining),' / 5')}</td><td><button type="button" class="ui-command" data-finder-trade="${escapeAttr(row.id)}" aria-label="Find trades for ${escapeAttr(row.name)}" ${!row.team_id || row.team_abbrev==='FA'?'disabled title="Free agents cannot be traded"':'title="Open Trade Finder with this player selected"'}>Find</button></td></tr>`).join('');
  return `<table class="player-finder-table"><colgroup>${fields.map(([, ,width])=>`<col style="width:${width}px">`).join('')}</colgroup><thead><tr>${head}</tr></thead><tbody>${body || '<tr><td colspan="11" class="player-finder-empty">No players match these filters.</td></tr>'}</tbody></table>`;
}

function boxScoreModalBody(box) {
  const away = teamLabel(box.away_team);
  const home = teamLabel(box.home_team);
  return `<div class="box-score-pages" data-box-score-pages>
    <div class="box-score-page-bar player-page-bar"><span data-box-score-page-title>Team Stats</span><nav class="player-page-nav" aria-label="Box score pages">
      <button type="button" class="ui-command" data-box-score-page-step="-1" aria-label="Previous box score page" title="Previous page">‹</button>
      <button type="button" class="ui-command" data-box-score-page-step="1" aria-label="Next box score page" title="Next page">›</button>
      <span data-box-score-page-count aria-live="polite" aria-atomic="true">1/2</span>
    </nav></div>
    <section class="box-score-page" data-box-score-page="0" data-page-title="Team Stats" aria-label="Team statistics comparison">
      ${boxScoreTeamComparison(box, away, home)}
    </section>
    <section class="box-score-page" data-box-score-page="1" data-page-title="Player Box Score" aria-label="Player box score" hidden>
      <div class="box-score-matchup-grid">
        ${boxScoreTeamSheet(box, away, box.away_score, "Away")}
        ${boxScoreTeamSheet(box, home, box.home_score, "Home")}
      </div>
    </section>
  </div>`;
}

function boxScoreTeamLine(box, team) {
  return (box.team_lines || []).find(row => (row.team_abbrev || teamLabel(row.team_id)) === team) || {};
}

function boxScoreComparisonMetric(line, key, attemptsKey = null) {
  const read = field => line[field] !== null && line[field] !== undefined && line[field] !== "" && Number.isFinite(Number(line[field])) ? Math.max(0, Number(line[field])) : null;
  const value = read(key);
  if (!attemptsKey) return { value, count:value, attempts:null, text: value === null ? "—" : String(value), detail: "" };
  const attempts = read(attemptsKey);
  if (value === null || attempts === null) return { value:null, count:null, attempts:null, text:"—", detail:"" };
  const percent = attempts > 0 ? Math.min(100, value / attempts * 100) : 0;
  return { value:percent, count:value, attempts, text:`${Math.round(percent)}%`, detail:`${value}/${attempts}` };
}

function boxScoreTeamComparison(box, away, home) {
  const awayLine = boxScoreTeamLine(box, away);
  const homeLine = boxScoreTeamLine(box, home);
  // Black and silver logos need their dark color against the light card surface.
  const color = team => ["BKN", "SAS"].includes(team) ? "#000000" : TEAM_BRAND_COLORS[team]?.[0] || "#65737D";
  const awayColor = color(away);
  const homeColor = color(home);
  const team = (abbrev, score, venue) => {
    const name = dashboardTeamName(abbrev);
    const logo = teamLogoSrc(abbrev);
    const scoreMarkup = `<strong class="box-score-team-score">${escapeHtml(score ?? "—")}</strong>`;
    const logoMarkup = logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(`${name} logo`)}" />` : "";
    const nameMarkup = `<div><span>${venue}</span><h4>${escapeHtml(name)}</h4></div>`;
    const identity = `<div class="box-score-team-identity">${venue === "Home" ? logoMarkup + nameMarkup : nameMarkup + logoMarkup}</div>`;
    return `<div class="box-score-comparison-team${venue === "Home" ? " is-home" : ""}">
      ${venue === "Home" ? identity + scoreMarkup : scoreMarkup + identity}
    </div>`;
  };
  const metrics = [
    ["Field Goal %", "fgm", "fga", 160, 40], ["Three Point %", "fg3m", "fg3a", 80, 20], ["Free Throw %", "ftm", "fta", 80, 20],
    ["Turnovers", "turnovers", null, 40, 10], ["Rebounds", "rebounds", null, 100, 25], ["Assists", "assists", null, 60, 15], ["Steals", "steals", null, 30, 5], ["Blocks", "blocks", null, 30, 5],
  ];
  const rows = metrics.map(([label, key, attemptsKey, maximum, step]) => {
    const a = boxScoreComparisonMetric(awayLine, key, attemptsKey);
    const h = boxScoreComparisonMetric(homeLine, key, attemptsKey);
    // Each fixed axis uses 90% of its half, reserving space beyond its last tick.
    const width = value => (clampNumber(Number(value || 0) / maximum, 0, 1) * 90).toFixed(3);
    const track = (metric, side) => {
      const overflow = Number(attemptsKey ? metric.attempts : metric.count) > maximum;
      const attemptBar = attemptsKey ? `<span class="box-score-comparison-undertone" style="width:${width(metric.attempts)}%"></span>` : '';
      return `<i class="box-score-comparison-track is-${side}" title="${attemptsKey ? `${metric.count ?? '—'} made / ${metric.attempts ?? '—'} attempted` : `${metric.count ?? '—'} ${label.toLowerCase()}`} · fixed scale 0–${maximum}${overflow ? ' · exceeds scale' : ''}">${attemptBar}<b style="width:${width(metric.count)}%"></b>${overflow ? `<em class="box-score-comparison-overflow" aria-hidden="true">${side === 'away' ? '‹' : '›'}</em>` : ''}</i>`;
    };
    const tick = position => `<span class="box-score-scale-tick" style="left:${position}%"></span>`;
    const ticks = [tick(50), ...Array.from({length:maximum / step},(_item,index) => {const value=(index + 1)*step;return tick(50-value / maximum*45) + tick(50+value / maximum*45);})].join('');
    const scaleDescription = attemptsKey ? `Shooting counts: made / attempted; fixed scale 0–${maximum} per team` : `Fixed scale 0–${maximum} per team`;
    return `<div class="box-score-comparison-row" aria-label="${escapeAttr(`${label}: ${away} ${a.text}${a.detail ? ` (${a.detail})` : ""}, ${home} ${h.text}${h.detail ? ` (${h.detail})` : ""}; ${scaleDescription}`)}">
      <div class="box-score-comparison-value">${a.detail ? `<small>(${escapeHtml(a.detail)})</small>` : ""}<strong>${escapeHtml(a.text)}</strong></div>
      <h4 title="${escapeAttr(scaleDescription)}">${label}</h4>
      <div class="box-score-comparison-value is-home">${h.detail ? `<small>(${escapeHtml(h.detail)})</small>` : ""}<strong>${escapeHtml(h.text)}</strong></div>
      <div class="box-score-comparison-bars" aria-hidden="true">${track(a,'away')}${track(h,'home')}</div>
      <div class="box-score-comparison-scale" aria-hidden="true">${ticks}</div>
    </div>`;
  }).join("");
  return `<div class="box-score-team-comparison" style="--box-away-color:${awayColor};--box-home-color:${homeColor}"><header class="box-score-comparison-head"><div class="box-score-comparison-head-teams">${team(away, box.away_score, "Away")}${team(home, box.home_score, "Home")}</div></header>${rows}</div>`;
}

function wireBoxScorePages(root, modal) {
  const pages = [...root.querySelectorAll('[data-box-score-page]')];
  const showPage = index => {
    modal.boxScorePage = ((index % pages.length) + pages.length) % pages.length;
    pages.forEach((page, pageIndex) => { page.hidden = pageIndex !== modal.boxScorePage; });
    root.querySelector('[data-box-score-page-title]').textContent = pages[modal.boxScorePage].dataset.pageTitle;
    root.querySelector('[data-box-score-page-count]').textContent = `${modal.boxScorePage + 1}/${pages.length}`;
  };
  showPage(modal.boxScorePage || 0);
  root.querySelectorAll('[data-box-score-page-step]').forEach(button => button.addEventListener('click', () => {
    showPage(modal.boxScorePage + Number(button.dataset.boxScorePageStep));
    root.querySelector('.modal-body').scrollTop = 0;
  }));
}

function boxScoreTeamSheet(box, team, score, venueLabel) {
  const line = boxScoreTeamLine(box, team);
  const players = (box.player_lines || []).filter((row) => row.team_abbrev === team);
  const logo = teamLogoSrc(team);
  const teamName = dashboardTeamName(team);
  return `<section class="box-score-team-sheet" ${teamBrandStyle(team)}>
    <header class="box-score-team-head">
      <div class="box-score-team-identity">
        ${logo ? `<img src="${escapeAttr(logo)}" alt="${escapeAttr(`${teamName} logo`)}" />` : ""}
        <div><span>${escapeHtml(venueLabel)}</span><h4>${escapeHtml(teamName)}</h4></div>
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
  const headers = ["Player", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "FG", "3PT", "FTM/FTA", "PF", "+/-"];
  return `<div class="box-score-player-table-wrap"><table class="box-score-player-table">
    <thead><tr>${headers.map((header) => `<th>${header}</th>`).join("")}</tr></thead>
    <tbody>${players.map((row) => row.minutes !== null && row.minutes !== undefined && Number(row.minutes) === 0
      ? `<tr class="box-score-dnp"><td>${escapeHtml(row.player_name || "Unknown")}</td><td class="box-score-dnp-cell" colspan="${headers.length - 1}"><span class="box-score-dnp-label">DNP</span></td></tr>`
      : `<tr>
      <td>${escapeHtml(row.player_name || "Unknown")}</td>
      <td>${escapeHtml(decimalNumber(row.minutes))}</td>
      <td>${escapeHtml(row.points ?? 0)}</td>
      <td>${escapeHtml(row.rebounds ?? 0)}</td>
      <td>${escapeHtml(row.assists ?? 0)}</td>
      <td>${escapeHtml(row.steals ?? 0)}</td>
      <td>${escapeHtml(row.blocks ?? 0)}</td>
      <td>${escapeHtml(row.turnovers ?? 0)}</td>
      <td>${row.fgm !== undefined ? `${escapeHtml(row.fgm)}/${escapeHtml(row.fga)}` : "—"}</td>
      <td>${row.fg3m !== undefined ? `${escapeHtml(row.fg3m)}/${escapeHtml(row.fg3a)}` : "—"}</td>
      <td>${row.ftm !== undefined && row.fta !== undefined ? `${escapeHtml(row.ftm)}/${escapeHtml(row.fta)}` : Number(row.minutes) === 0 ? "0/0" : "—"}</td>
      <td>${escapeHtml(row.personal_fouls ?? row.pf ?? (Number(row.minutes) === 0 ? 0 : "—"))}</td>
      <td title="${row.plus_minus === null || row.plus_minus === undefined ? 'Not tracked for this game' : 'Plus-minus from modeled five-player scoring stints'}">${row.plus_minus === null || row.plus_minus === undefined ? "—" : escapeHtml(signedNumber(row.plus_minus, 0))}</td>
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
    state.modal = {
      kind: gameIds.length ? "playoffBoxScore" : "boxScore",
      title: `${teamLabel(box.away_team)} ${box.away_score} @ ${teamLabel(box.home_team)} ${box.home_score}`,
      subtitle: "",
      body: boxScoreModalBody(box),
      boxScorePage: Number(options.page) === 1 ? 1 : 0,
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
    page: state.modal.boxScorePage || 0,
  });
}

function closeModal() {
  if(typeof acknowledgeClosedWantReminder==='function')acknowledgeClosedWantReminder();
  if (state.modal?.kind === "staffNegotiation" && state.modal.submitting) return;
  const postseasonBoundary = state.modal?.kind === "postseason" ? state.modal.postseasonBoundary : "";
  if (postseasonBoundary) {
    state.postseasonReviewedSave = state.currentSave;
    state.postseasonReviewedDate = postseasonBoundary;
    try { localStorage.setItem(postseasonReviewKey(postseasonBoundary), "1"); } catch {}
  }
  const refreshStaff = state.modal?.kind === "staffNegotiation" && state.modal.staffNeedsRefresh;
  if (state.modal?.kind === "freeAgentComparison") state.freeAgentCompareMode = true;
  state.modal = GameInterface.previousModal();
  renderModal();
  if (postseasonBoundary) window.CardBoard?.open("phase-playoffs-bracket");
  if(!state.modal && typeof maybeShowWantReminder==='function')maybeShowWantReminder();
  if (refreshStaff) refreshHome().catch(error => showToast(error.message || "Could not refresh coaching staff.", true));
}

function openSettingsModal() {
  state.modal = {
    kind: "dashboardSettings",
    title: "Settings",
    subtitle: "",
    body: `
      <section class="settings-modal-section settings-save-section">
        <button type="button" data-interface-shortcuts>Keyboard shortcuts</button>
        <button type="button" data-replay-tutorial>Replay Tutorial</button>
        <button type="button" class="ui-command" data-report-issue>Report an Issue</button>
        <a class="artwork-credits-link" href="/assets/game-art/CREDITS.md" target="_blank" rel="noopener">Artwork credits</a>
        <button class="settings-return-button" data-return-save-selection>Back to Save Selection</button>
      </section>`,
  };
  renderModal();
}

async function openIssueReport() {
  if (state.tutorial || state.busy) return;
  const report = GameFeedback.snapshot(state);
  state.modal = {
    kind: "issueReport", title: "Report an Issue", subtitle: "",
    report,
    body: `<form class="issue-report-form" data-issue-report-form>
      <label>Summary<input name="summary" maxlength="200" required /></label>
      <label>Steps to reproduce<textarea name="steps" maxlength="3000" rows="3"></textarea></label>
      <label>Expected result<textarea name="expected" maxlength="3000" rows="2"></textarea></label>
      <label>Actual result<textarea name="actual" maxlength="3000" rows="2"></textarea></label>
      <p class="issue-report-privacy">Nothing is uploaded. The download includes your notes, build and screen information, video status and recent action names. No saves, file paths, tokens or raw logs. Notes are included as written; avoid personal information.</p>
      <details><summary>Included diagnostics</summary><pre data-issue-diagnostics>${escapeHtml(JSON.stringify(report, null, 2))}</pre></details>
      <p data-issue-report-status role="status" aria-live="polite"></p>
      <button type="submit" class="ui-command">Download Issue Report</button>
    </form>`,
  };
  renderModal();
  els.modalRoot.querySelector('[name="summary"]')?.focus();
  const modal = state.modal;
  const runtime = await GameFeedback.runtime(apiHeaders);
  // Preserve typed notes and never reopen a dialog after a late response.
  if (state.modal !== modal) return;
  const metadata = GameFeedback.snapshot(state, runtime);
  modal.report.runtime = metadata.runtime;
  modal.report.runtime_available = metadata.runtime_available;
  els.modalRoot.querySelector("[data-issue-diagnostics]").textContent = JSON.stringify(modal.report, null, 2);
}

function downloadIssueReport(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const report = {...state.modal.report, notes: Object.fromEntries(["summary", "steps", "expected", "actual"].map(key => [key, form.elements.namedItem(key).value.slice(0, 3000)]))};
  const blob = new Blob([JSON.stringify(report, null, 2) + "\n"], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `nba-gm-issue-${report.created_at.replace(/[:.]/g, "-")}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  form.querySelector("[data-issue-report-status]").textContent = "Report download requested. Share the JSON file with the game's creator. A save backup is separate and optional.";
}

async function openExtensionNegotiation(playerId = "") {
  if (playerId && await focusOpenExtensionCard(playerId)) return;
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
    const context=state.modal;
    context.outcome=null;
    context.extensionApplied=false;
    await openPlayerCardOnClipboard({key:`extension:${selectedId}`, title:`${detail?.name || "Player"} · Contract Extension`,body:context.body,kind:"extension",context});
  } catch (error) {
    showToast(error.message || "Extension room could not be opened.", true);
  }
}

function extensionNegotiationBody(room, selectedPlayerId, response = null, detail = null) {
  const candidate=(room.candidates||[]).find(item=>item.player_id===selectedPlayerId)||(room.candidates||[])[0];
  const player=detail||{name:candidate?.name||"Player",position:candidate?.position||"",age:candidate?.age,height:candidate?.height,ratings:candidate?.ratings||{},season:{},recent_games:[],career_seasons:[],is_prospect:false};
  return approvedPlayerCardBody(player,{extension:{room,selectedPlayerId,response}});
}

function extensionNegotiationPage(room, selectedPlayerId, response = null, detail = null) {
  const candidates=room?.candidates||[];
  const candidate=candidates.find(item=>item.player_id===selectedPlayerId)||candidates[0];
  if (!candidate) return `<section class="player-card-page player-card-page--extension" data-player-page="0" data-page-title="Contract Extension" aria-label="Contract extension"><div class="extension-page-empty"><strong>No extension candidates</strong><p>No contracted player on this roster is available for extension review right now.</p></div></section>`;
  const years = Math.max(1, Math.min(Number(candidate.safe_years || 1), Number(candidate.preferred_years || 1)));
  const maximum = Number(candidate.max_aav_by_years?.[String(years)] || 0);
  const ask = Number(candidate.projected_aav_millions || 0);
  const initialOffer = Math.min(maximum, ask);
  const capRows = extensionCapRows(candidate);
  const schedule = extensionOfferSchedule(candidate, years, Number(initialOffer.toFixed(1)), capRows);
  const status=response?`<section class="extension-response extension-page-response ${response.status === "rejected" ? "rejected" : ""}"><strong>${escapeHtml(response.status === "rejected" ? "Offer declined" : rowLabel(response.status || "update"))}</strong><span>${escapeHtml(response.reason || "")}${response.interest !== undefined ? ` Interest: ${Number(response.interest).toFixed(1)}/100.` : ""}</span></section>`:"";
  return `<section class="player-card-page player-card-page--extension" data-player-page="0" data-page-title="Contract Extension" aria-label="Contract extension">
    <div class="extension-page-layout">
      <div class="extension-page-controls">
        <section class="approved-card-panel approved-ask-offer"><header><span>Extension Offer</span><strong class="extension-player-name">${escapeHtml(candidate.name||"Player")}</strong></header><form data-extension-offer-form><div class="approved-ask-grid"><span><small>Player Ask</small><strong>${money(ask)} × ${candidate.preferred_years||years}</strong></span><label><small>Annual Offer · max <b data-extension-maximum>${money(maximum)}</b></small><span class="money-input"><b>$</b><input type="number" min="1.8" max="${maximum.toFixed(2)}" step="0.1" value="${initialOffer.toFixed(1)}" data-extension-aav aria-label="Annual extension offer in millions" required><b>M</b></span></label><label><small>Years</small><span class="extension-years-stepper"><button type="button" data-extension-years-step="-1" aria-label="Decrease contract years">−</button><input type="number" min="1" max="${Number(candidate.safe_years||1)}" step="1" value="${years}" data-extension-years aria-label="Contract years"><button type="button" data-extension-years-step="1" aria-label="Increase contract years">+</button></span></label><span><small>Salary protection</small><label class="contract-security"><input type="checkbox" data-extension-guaranteed checked> Guaranteed</label></span></div><button type="submit" class="extension-submit primary-action" ${maximum<1.8?"disabled":""}>Submit Offer</button></form></section>
        <div class="extension-page-middle"><section class="approved-card-panel approved-interest-factors"><header>Interest Breakdown</header><div>${[["Offer vs ask",initialOffer/Math.max(1,ask)*100],["Player timeline",Math.max(20,100-Number(candidate.age||27)*1.4)],["Team direction",64],["Contract length",years/Math.max(1,Number(candidate.preferred_years||years))*100]].map(([label,value],index)=>`<span data-extension-factor="${index}"><small>${escapeHtml(label)}</small><i><b style="width:${clampNumber(value,0,100)}%"></b></i><strong>${Math.round(clampNumber(value,0,100))}</strong></span>`).join("")}</div></section>${extensionDeparturePanel(candidate)}</div>
        <div data-extension-analysis-slot>${extensionAnalysisPanel(candidate,years,initialOffer)}</div>
      </div>
      <div class="extension-page-impact">
        <section class="approved-card-panel approved-offer-cap"><header>Four-Year Cap Impact</header>${extensionCapChart(capRows,schedule,candidate.current_contract_seasons)}</section>
      </div>
      ${status}
    </div>
  </section>`;
}

function extensionDeparturePanel(candidate) {
  const analysis = candidate.analysis || {}, player = analysis.player || {}, replacement = analysis.replacement;
  const gap = replacement ? Number(replacement.overall) - Number(player.overall) : null;
  return `<section class="approved-card-panel extension-departure"><header>If ${escapeHtml(candidate.name || "This Player")} Leaves</header><div class="extension-departure-facts"><div><span>Minutes to replace</span><strong>${player.minutes != null ? `${Number(player.minutes).toFixed(1)} MPG` : "—"}</strong></div><div><span>Internal alternative</span><span>${replacement ? escapeHtml(replacement.name) : "No reserve in this position group"}</span></div><div><span>Current ability gap</span><span>${gap != null ? `${gap > 0 ? "+" : ""}${gap.toFixed(1)} OVR · ${Number(replacement.overall).toFixed(1)} vs ${Number(player.overall).toFixed(1)}` : "—"}</span></div></div></section>`;
}

function extensionAbilityView(candidate, years) {
  const analysis = candidate.analysis || {};
  const finalYear = Number.parseInt(candidate.start_season, 10) + years - 1;
  const points = (analysis.projection || []).filter(point => Number.parseInt(point.season, 10) <= finalYear);
  if (!points.length) return '<div class="extension-analysis-empty">Development projection unavailable for this player.</div>';
  const left = 54, right = 928, top = 30, bottom = 230;
  const minimum = Math.max(0, Math.floor((Math.min(...points.map(p => p.low)) - 3) / 2) * 2);
  const maximum = Math.min(100, Math.max(minimum + 8, Math.ceil((Math.max(...points.map(p => p.high)) + 2) / 2) * 2));
  const x = index => left + (right - left) * index / Math.max(1, points.length - 1);
  const y = value => bottom - (value - minimum) / (maximum - minimum) * (bottom - top);
  const grids = Array.from({length:5}, (_,index) => { const value = minimum + (maximum - minimum) * index / 4; return `<line class="extension-chart-grid" x1="${left}" x2="${right}" y1="${y(value)}" y2="${y(value)}"/><text x="${left - 12}" y="${y(value)+5}" text-anchor="end">${value.toFixed(0)}</text>`; }).join("");
  const range = points.map((p,i) => `${x(i)},${y(p.high)}`).concat(points.map((p,i) => `${x(i)},${y(p.low)}`).reverse()).join(" ");
  return `<div class="extension-analysis-plot"><svg viewBox="0 0 960 280" preserveAspectRatio="none" role="img" aria-label="Projected overall ability through the contract"><title>${escapeHtml(analysis.projection_note || "Estimated development")}</title>${grids}<polygon class="extension-projection-range" points="${range}"/><polyline class="extension-projection-line" points="${points.map((p,i) => `${x(i)},${y(p.overall)}`).join(" ")}"/>${points.map((p,i) => `<circle class="extension-projection-node" cx="${x(i)}" cy="${y(p.overall)}" r="4"><title>${escapeHtml(p.season)} · age ${p.age}: OVR ${p.overall.toFixed(1)}, scenario range ${p.low.toFixed(1)}–${p.high.toFixed(1)}</title></circle><text class="extension-chart-value" x="${x(i)}" y="${y(p.high)-12}" text-anchor="middle">${p.overall.toFixed(1)}</text><text x="${x(i)}" y="${bottom+23}" text-anchor="middle">${escapeHtml(shortSeasonLabel(p.season))}</text><text class="extension-chart-muted" x="${x(i)}" y="${bottom+43}" text-anchor="middle">Age ${p.age}</text>`).join("")}</svg></div><footer class="extension-analysis-footer"><span class="extension-chart-key" title="${escapeAttr(analysis.projection_note || "")}"><i class="extension-range-key"></i>Scenario range <i class="extension-line-key"></i>Projected OVR</span><span>Current <b>${points[0].overall.toFixed(1)}</b> → final year <b>${points.at(-1).overall.toFixed(1)}</b></span></footer>`;
}

function extensionContractsView(candidate, aav) {
  const analysis = candidate.analysis || {}, peers = analysis.peers || [], player = analysis.player || {};
  if (!peers.length) return `<div class="extension-analysis-empty">No comparable contracts meet this player's peer criteria.</div><footer class="extension-analysis-footer"><span>Current age, ability and position group</span><button type="button" class="ui-command" data-extension-peer-criteria aria-expanded="false">Peer criteria</button></footer>${extensionPeerCriteria(analysis, false)}`;
  const left=62, right=918, top=32, bottom=225;
  const overalls = peers.map(p=>p.overall).concat(player.overall || 50);
  const minX = Math.floor(Math.min(...overalls)-2), maxX=Math.ceil(Math.max(...overalls)+2);
  const maxY = Math.max(10,Math.ceil(Math.max(aav,...peers.map(p=>p.annual_salary))/10)*10);
  const x=value=>left+(value-minX)/(maxX-minX)*(right-left), y=value=>bottom-value/maxY*(bottom-top);
  const median = Number(analysis.peer_median || 0);
  const difference = median ? Math.round((aav/median-1)*100) : 0;
  const svg=`<svg viewBox="0 0 960 280" preserveAspectRatio="none" role="img" aria-label="Comparable contracts: current ability versus cap-adjusted annual salary">${Array.from({length:5},(_,i)=>{const v=maxY*i/4;return `<line class="extension-chart-grid" x1="${left}" x2="${right}" y1="${y(v)}" y2="${y(v)}"/><text x="${left-10}" y="${y(v)+5}" text-anchor="end">$${v.toFixed(0)}M</text>`}).join("")}<line class="extension-market-median" x1="${left}" x2="${right}" y1="${y(median)}" y2="${y(median)}"/><text x="${right}" y="${y(median)-8}" text-anchor="end">Median ${money(median)}</text>${Array.from({length:5},(_,i)=>{const v=minX+(maxX-minX)*i/4;return `<text x="${x(v)}" y="${bottom+24}" text-anchor="middle">${v.toFixed(0)}</text>`}).join("")}<text x="490" y="274" text-anchor="middle">Current OVR</text>${peers.map((p,i)=>`<circle class="extension-peer-point" tabindex="0" data-extension-peer="${i}" cx="${x(p.overall)}" cy="${y(p.annual_salary)}" r="7" aria-label="${escapeAttr(`${p.name}: ${p.overall.toFixed(1)} OVR, ${money(p.annual_salary)} annual salary`)}"><title>${escapeHtml(p.name)} · ${p.overall.toFixed(1)} OVR · ${money(p.annual_salary)}</title></circle>`).join("")}<path class="extension-offer-point" d="M ${x(player.overall)} ${y(aav)-9} l 9 9 l -9 9 l -9 -9 Z"><title>Your offer: ${money(aav)}</title></path></svg>`;
  return `<div class="extension-analysis-plot">${svg}</div><footer class="extension-analysis-footer"><span class="extension-chart-key"><i class="extension-peer-key"></i>Peers <i class="extension-offer-key"></i>Your offer</span><span data-extension-peer-detail>${peers.length} peers · offer ${Math.abs(difference)}% ${difference>0?"above":difference<0?"below":"from"} median</span><button type="button" class="ui-command" data-extension-peer-criteria aria-expanded="false">Peer criteria</button></footer>${extensionPeerCriteria(analysis, false)}`;
}

function extensionPeerCriteria(analysis, visible = true) {
  return `<div class="extension-peer-criteria" ${visible ? "" : "hidden"}><header>Comparison group<button type="button" class="ui-command" data-extension-peer-close aria-label="Close peer criteria">×</button></header><ul>${(analysis.peer_criteria || []).map(text=>`<li>${escapeHtml(text)}</li>`).join("")}</ul></div>`;
}

function extensionSuccessionView(candidate, years) {
  const analysis=candidate.analysis||{}, rows=analysis.succession||[], start=Number.parseInt(candidate.start_season,10);
  const current=Number.parseInt(extensionCapRows(candidate)[0]?.[0],10), end=Math.max(current+3,start+years-1);
  const seasons=Array.from({length:end-current+1},(_,i)=>`${current+i}-${String(current+i+1).slice(-2)}`);
  if(!rows.length) return '<div class="extension-analysis-empty">No position-group contract data available.</div>';
  const covered = rows.slice(1).filter(p=>p.seasons.some(s=>Number.parseInt(s.season,10)===end && Number(s.salary)>0)).length;
  return `<div class="extension-succession" role="table" aria-label="${escapeAttr(analysis.position_group || "Position group")} contract coverage" style="--extension-seasons:${seasons.length}"><div class="extension-succession-row extension-succession-head" role="row"><span role="columnheader">${escapeHtml(analysis.position_group || "Players")}</span>${seasons.map(s=>`<span role="columnheader">${escapeHtml(shortSeasonLabel(s))}</span>`).join("")}</div>${rows.map((p,index)=>`<div class="extension-succession-row" role="row"><span role="rowheader">${escapeHtml(p.name)}<small>${p.age} years · OVR ${p.overall.toFixed(1)}</small></span>${seasons.map(s=>{const year=Number.parseInt(s,10),signed=p.seasons.some(row=>row.season===s && Number(row.salary)>0), proposed=index===0 && year>=start && year<start+years; const type=proposed?"offer":signed?(index===0?"current":"signed"):"open";return `<span role="cell" class="extension-tenure is-${type}">${proposed?"Extension":signed?(index===0?"Current":"Signed"):"No deal"}</span>`}).join("")}</div>`).join("")}</div><footer class="extension-analysis-footer"><span>${escapeHtml(shortSeasonLabel(seasons.at(-1)))}: <b>${covered} other ${covered===1?"player":"players"} shown under contract</b></span><span>Based on current roster</span></footer>`;
}

function extensionAnalysisPanel(candidate, years, aav) {
  return `<section class="approved-card-panel extension-analysis"><header><span data-extension-analysis-title>Projected Ability Through the Contract</span><div class="extension-analysis-tabs" role="tablist" aria-label="Contract analysis">${["Ability","Contracts","Succession"].map((label,i)=>`<button type="button" role="tab" data-extension-analysis-tab="${label.toLowerCase()}" aria-selected="${i===0}" tabindex="${i===0?0:-1}">${label}</button>`).join("")}</div></header><div class="extension-analysis-view" role="tabpanel" aria-label="Ability" data-extension-analysis-view="ability">${extensionAbilityView(candidate,years)}</div><div class="extension-analysis-view" role="tabpanel" aria-label="Contracts" data-extension-analysis-view="contracts" hidden>${extensionContractsView(candidate,aav)}</div><div class="extension-analysis-view" role="tabpanel" aria-label="Succession" data-extension-analysis-view="succession" hidden>${extensionSuccessionView(candidate,years)}</div></section>`;
}

function wireExtensionAnalysis(root, modal, candidate) {
  const tabs=[...root.querySelectorAll('[data-extension-analysis-tab]')];
  const titles={ability:"Projected Ability Through the Contract",contracts:"Comparable Contracts",succession:`${candidate.analysis?.position_group || "Position Group"} · Succession Timeline`};
  const show=(key)=>{
    modal.analysisTab=key;
    tabs.forEach(tab=>{ const selected=tab.dataset.extensionAnalysisTab===key;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1; });
    root.querySelectorAll('[data-extension-analysis-view]').forEach(view=>view.hidden=view.dataset.extensionAnalysisView!==key);
    const title=root.querySelector('[data-extension-analysis-title]'); if(title) title.textContent=titles[key];
  };
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',()=>show(tab.dataset.extensionAnalysisTab));
    tab.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();event.stopPropagation();
      const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      tabs[next].focus();show(tabs[next].dataset.extensionAnalysisTab);
    });
  });
  const criteria=root.querySelector('.extension-peer-criteria'), criteriaButton=root.querySelector('[data-extension-peer-criteria]');
  criteriaButton?.addEventListener('click',()=>{criteria.hidden=!criteria.hidden;criteriaButton.setAttribute('aria-expanded',String(!criteria.hidden));});
  root.querySelector('[data-extension-peer-close]')?.addEventListener('click',()=>{criteria.hidden=true;criteriaButton?.setAttribute('aria-expanded','false');criteriaButton?.focus();});
  const detail=root.querySelector('[data-extension-peer-detail]'), defaultText=detail?.textContent;
  root.querySelectorAll('[data-extension-peer]').forEach(point=>{
    const peer=candidate.analysis.peers[Number(point.dataset.extensionPeer)];
    const reveal=()=>{if(detail) detail.textContent=`${peer.name} · ${money(peer.annual_salary)} · ${peer.overall.toFixed(1)} OVR`;};
    const reset=()=>{if(detail) detail.textContent=defaultText;};
    point.addEventListener('mouseenter',reveal);point.addEventListener('focus',reveal);
    point.addEventListener('mouseleave',reset);point.addEventListener('blur',reset);
  });
  show(titles[modal.analysisTab]?modal.analysisTab:'ability');
}

function extensionCapRows(candidate) {
  const dashboardCaps = state.data.dashboard?.cap_by_year || {};
  const dashboardSeason = Object.keys(dashboardCaps).sort((left, right) => left.localeCompare(right))[0] || "";
  const saveSeason = String(state.home?.save?.current_season || "");
  const currentDate = String(state.home?.save?.current_date || "");
  const currentStart = Number((dashboardSeason.match(/\d{4}/) || saveSeason.match(/\d{4}/) || currentDate.match(/^\d{4}/) || [])[0])
    || Number.parseInt(candidate.start_season, 10) - 1;
  const projection = new Map((candidate.cap_projection || []).map((row) => [String(row.season), row]));
  return Array.from({ length: 4 }, (_, offset) => {
    const start = currentStart + offset;
    const season = `${start}-${String(start + 1).slice(-2)}`;
    return [season, projection.get(season) || dashboardCaps[season] || {}];
  });
}

function extensionOfferSchedule(candidate, years, aav, capRows = extensionCapRows(candidate)) {
  const start = Number.parseInt(candidate.start_season, 10);
  return capRows.map(([season]) => {
    const offset = Number.parseInt(season, 10) - start;
    return offset >= 0 && offset < Number(years) ? Math.max(0, Number(aav) || 0) : 0;
  });
}

function extensionCapChart(capRows, offer, currentContractSeasons = []) {
  const maximum = Math.max(1, ...capRows.flatMap(([, cap], index) => [
    Number(cap.salary_total_millions || 0) + Number(offer[index] || 0),
    Number(cap.tax_line_millions || 0),
    Number(cap.hard_cap_millions || 0),
  ])) * 1.06;
  const pct = (value) => clampNumber(Number(value || 0) / maximum * 100, 0, 100);
  return `<div class="approved-offer-cap-chart salary-horizon-chart is-extension">${capRows.map(([season, cap], index) => {
    const payroll = Number(cap.salary_total_millions || 0);
    const annual = Number(offer[index] || 0);
    const total = payroll + annual;
    const extensionPct = pct(annual);
    const currentSalary = index === 0
      ? Math.min(payroll, Math.max(0, Number(currentContractSeasons.find((row) => String(row.season) === String(season))?.salary || 0) / 1_000_000))
      : 0;
    const currentSalaryPct = pct(currentSalary);
    const otherPayrollPct = pct(Math.max(0, payroll - currentSalary));
    const tax = Number(cap.tax_line_millions || 0);
    const hard = Number(cap.hard_cap_millions || 0);
    return `<div class="salary-horizon-year"><span>${escapeHtml(shortSeasonLabel(season))}</span><div class="salary-horizon-column" role="img" aria-label="${escapeAttr(`${season}: payroll ${money(payroll)}, current player contract ${money(currentSalary)}, extension ${money(annual)}, tax line ${money(tax)}, hard cap ${money(hard)}`)}"><div class="salary-horizon-stack" style="height:100%"><i class="salary-segment salary-segment-other" style="height:${otherPayrollPct}%" title="Other team payroll ${money(Math.max(0, payroll - currentSalary))}"></i>${currentSalary > 0 ? `<i class="salary-segment salary-segment-current-contract is-highlighted" style="height:${currentSalaryPct}%" title="Current player contract ${money(currentSalary)}"></i>` : ""}${annual > 0 ? `<i class="salary-segment salary-segment-extension is-highlighted" style="height:${extensionPct}%" title="Proposed extension ${money(annual)}"></i>` : ""}</div>${tax > 0 ? `<b class="salary-tax-line" style="bottom:${pct(tax)}%"></b>` : ""}${hard > 0 ? `<b class="salary-hard-line" style="bottom:${pct(hard)}%"></b>` : ""}</div><strong>${money(total)}</strong></div>`;
  }).join("")}<div class="salary-horizon-legend extension-cap-legend"><span>Payroll</span><span>Current contract</span><span>Extension</span><span>Tax line</span><span>Hard cap</span></div></div>`;
}

function updateExtensionPreview(modal = state.modal, root = els.modalRoot) {
  if (modal?.kind !== "contractExtension") return;
  const candidate = modal.room?.candidates?.find(item => item.player_id === modal.selectedPlayerId);
  if (!candidate) return;
  const years = Number(root.querySelector('[data-extension-years]')?.value || 1);
  const aavInput = root.querySelector('[data-extension-aav]');
  const aav = Number(aavInput?.value || 0);
  modal.draft = {years, aav, guaranteed: root.querySelector('[data-extension-guaranteed]')?.checked !== false};
  const analysisSlot = root.querySelector('[data-extension-analysis-slot]');
  const signature = `${years}:${aav}`;
  if (analysisSlot && analysisSlot.dataset.signature !== signature) {
    analysisSlot.dataset.signature = signature;
    analysisSlot.innerHTML = extensionAnalysisPanel(candidate, years, aav);
    wireExtensionAnalysis(analysisSlot, modal, candidate);
  }
  const maximum = Number(candidate.max_aav_by_years?.[String(years)] || 0);
  if (aavInput) aavInput.max = maximum.toFixed(2);
  const maximumLabel = root.querySelector('[data-extension-maximum]');
  if (maximumLabel) maximumLabel.textContent = money(maximum);
  const capRows = extensionCapRows(candidate);
  const schedule = extensionOfferSchedule(candidate, years, aav, capRows);
  root.querySelector('.approved-offer-cap').innerHTML = `<header>Four-Year Cap Impact</header>${extensionCapChart(capRows, schedule, candidate.current_contract_seasons)}`;
  root.querySelectorAll('[data-extension-years-step]').forEach((button) => {
    const step = Number(button.dataset.extensionYearsStep || 0);
    button.disabled = step < 0 ? years <= 1 : years >= Number(candidate.safe_years || 1);
  });
  for (const [index, value] of [[0, aav / Math.max(1, candidate.projected_aav_millions) * 100], [3, years / Math.max(1, candidate.preferred_years) * 100]]) {
    const factor = root.querySelector(`[data-extension-factor="${index}"]`);
    const score = clampNumber(value, 0, 100);
    if (factor) {
      factor.querySelector('i b').style.width = `${score}%`;
      factor.querySelector('strong').textContent = Math.round(score);
    }
  }
}

function mountPlayerExtensionOutcome(card, modal, close) {
  const content=card.querySelector('[data-player-pages]');
  if(!content||!modal?.outcome) return;
  card.querySelector('.staff-negotiation-result')?.remove();
  card.classList.add('has-extension-result');
  content.inert=true;
  const overlay=document.createElement('div');
  overlay.className=`staff-negotiation-result staff-outcome--${modal.outcome.kind}`;
  overlay.setAttribute('role','region');
  overlay.setAttribute('aria-label','Player extension offer result');
  overlay.tabIndex=-1;
  overlay.innerHTML=staffNegotiationOutcomeMarkup(modal.outcome);
  card.append(overlay);
  const dismiss=overlay.querySelector('[data-staff-result-dismiss]');
  dismiss?.addEventListener('click',()=>{
    if(modal.submitting) return;
    if(modal.outcome.kind==='accepted'||!modal.outcome.allowRetry){ close(); return; }
    delete modal.outcome;
    overlay.remove();
    card.classList.remove('has-extension-result');
    content.inert=false;
    card.querySelector('[data-extension-aav]')?.focus({preventScroll:true});
  });
  const windowClose=card.closest('.card-board-window')?.querySelector('[data-board-close]');
  if(windowClose&&modal.extensionApplied){
    windowClose.addEventListener('click',()=>{
      if(!modal.extensionApplied) return;
      modal.extensionApplied=false;
      const entryId=card.dataset.extensionEntryId;
      state.clipboardPlayerCards=state.clipboardPlayerCards.filter(item=>item.id!==entryId);
      showToast(modal.outcome?.message||"Player signed an extension.");
      void refreshHome();
    },{once:true});
  }
  (dismiss||overlay).focus({preventScroll:true});
}

function wireExtensionNegotiationModal(root = els.modalRoot, modal = state.modal, redraw = renderModal, close = closeModal) {
  if (!modal || modal.kind !== "contractExtension") return;
  const yearsInput = root.querySelector("[data-extension-years]");
  const aavInput = root.querySelector("[data-extension-aav]");
  const guaranteedInput = root.querySelector('[data-extension-guaranteed]');
  if (modal.draft) {
    if (yearsInput) yearsInput.value = String(modal.draft.years);
    if (aavInput) aavInput.value = String(modal.draft.aav);
    if (guaranteedInput) guaranteedInput.checked = modal.draft.guaranteed !== false;
  }
  const syncYears = () => {
    const candidate = (modal.room?.candidates || []).find((item) => item.player_id === modal.selectedPlayerId);
    if (!candidate || !yearsInput) return;
    const years = clampNumber(Number(yearsInput.value || 1), 1, Number(candidate.safe_years || 1));
    yearsInput.value = String(years);
    const maximum = Number(candidate.max_aav_by_years?.[String(years)] || 0);
    if (aavInput) {
      aavInput.max = maximum.toFixed(2);
      aavInput.value = Math.min(Number(aavInput.value || 0), maximum).toFixed(1);
    }
    updateExtensionPreview(modal,root);
  };
  yearsInput?.addEventListener("change", syncYears);
  root.querySelectorAll("[data-extension-years-step]").forEach((button) => button.addEventListener("click", () => {
    if (!yearsInput) return;
    yearsInput.value = String(clampNumber(Number(yearsInput.value || 1) + Number(button.dataset.extensionYearsStep || 0), 1, Number(yearsInput.max || 1)));
    syncYears();
  }));
  aavInput?.addEventListener("input", () => updateExtensionPreview(modal,root));
  guaranteedInput?.addEventListener('change', () => updateExtensionPreview(modal,root));
  updateExtensionPreview(modal,root);
  root.querySelector("[data-extension-offer-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if(modal.submitting) return;
    const playerId = modal.selectedPlayerId;
    const years = Number(root.querySelector("[data-extension-years]")?.value || 1);
    const aav = Number(root.querySelector("[data-extension-aav]")?.value || 0);
    modal.submitting=true;
    const submit=root.querySelector('[data-extension-offer-form] button[type="submit"]');
    if(submit){ submit.disabled=true; submit.textContent="Waiting for response…"; }
    try {
      const result = await action("submit_extension_offer", {
        ...savePayload(),
        player_id: playerId,
        years,
        aav_millions: aav,
        guaranteed: guaranteedInput?.checked !== false,
      });
      if (result.status === "applied") {
        modal.submitting=false;
        modal.extensionApplied=true;
        modal.outcome={kind:"accepted",title:"Extension accepted",message:`${result.player_name||modal.detail?.name||"Player"} signed a ${years}-year extension.`};
        mountPlayerExtensionOutcome(root,modal,close);
        return;
      }
      modal.response = result;
      modal.room = result.room || modal.room;
      modal.submitting=false;
      if(result.status==="rejected") modal.outcome={kind:"declined",title:"Offer declined",message:result.reason||"The player declined this extension. Adjust the offer to try again.",allowRetry:true};
      modal.body = extensionNegotiationBody(modal.room, modal.selectedPlayerId, result, modal.detail);
      redraw();
    } catch (error) {
      modal.submitting=false;
      showToast(error.message || "Extension offer could not be submitted.", true);
      const currentSubmit=root.querySelector('[data-extension-offer-form] button[type="submit"]');
      if(currentSubmit){ currentSubmit.disabled=false; currentSubmit.textContent="Submit Offer"; }
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
  if (["playerFinder", "leagueLeaders"].includes(state.modal.kind)) {
    state.modal.body = playerFinderModalBody();
  }
  els.modalRoot.hidden = false;
  const modalClass = state.modal.kind === 'teamWants' ? ' modal-team-wants' : state.modal.kind === 'waivers' ? ' modal-waivers' : ["playerFinder", "leagueLeaders", "freeAgentComparison"].includes(state.modal.kind)
    ? (["playerFinder", "leagueLeaders"].includes(state.modal.kind) ? " modal-wide modal-player-finder" : " modal-wide")
    : state.modal.kind === "draftProspect"
      ? " modal-fantasy-player modal-prospect-card"
    : ["fantasyPlayer", "dashboardPlayer", "freeAgentPlayer"].includes(state.modal.kind)
      ? " modal-fantasy-player"
    : state.modal.kind === "dashboardStaff"
      ? " modal-coach-card"
    : state.modal.kind === "tradeRoom"
      ? " modal-trade-room"
      : ["tradeOffers", "humanTradeOffers"].includes(state.modal.kind)
        ? " modal-trade-offers"
      : ["dashboardSettings", "issueReport"].includes(state.modal.kind)
        ? " modal-settings"
      : state.modal.kind === "staffNegotiation"
        ? " modal-staff-negotiation"
      : state.modal.kind === "contractExtension"
        ? " modal-contract-extension"
      : state.modal.kind === "freeAgentNegotiation"
        ? " modal-free-agent-negotiation"
      : ["boxScore", "playoffBoxScore"].includes(state.modal.kind)
        ? " modal-box-score"
      : state.modal.kind === "champion"
        ? " modal-champion"
      : ["tradeDeadline","postseason"].includes(state.modal.kind)
        ? " modal-box-score modal-trade-deadline"
        : "";
  const closeLabel = ["teamWants", "waivers", "playerFinder", "leagueLeaders", "dashboardSettings", "issueReport"].includes(state.modal.kind) ? state.modal.title : state.modal.kind === "tradeDeadline" ? "Trade Deadline" : state.modal.kind === "tradeRoom"
    ? "Trade Room"
    : state.modal.kind === "dashboardStaff"
      ? "Coach Card"
    : state.modal.kind === "staffNegotiation"
      ? "Staff Negotiation"
    : state.modal.kind === "draftProspect"
      ? "Prospect Card"
    : ["fantasyPlayer", "dashboardPlayer", "freeAgentPlayer"].includes(state.modal.kind)
      ? "Player Card"
    : ["freeAgentNegotiation", "freeAgentComparison"].includes(state.modal.kind)
      ? "Free Agency"
    : ["boxScore", "playoffBoxScore"].includes(state.modal.kind)
      ? "Box Score"
      : "Trade Offers";
  const isBoxScore = ["boxScore", "playoffBoxScore"].includes(state.modal.kind);
  const hasClipboardTitlebar = isBoxScore || ["teamWants", "waivers", "playerFinder", "leagueLeaders", "tradeRoom", "tradeDeadline", "postseason", "champion", "staffNegotiation", "dashboardSettings", "issueReport", "tradeOffers", "humanTradeOffers"].includes(state.modal.kind);
  const closeControl = hasClipboardTitlebar
    ? `<button type="button" class="modal-close-icon card-board-control card-board-close" data-close-modal aria-label="Close ${closeLabel}" title="Close"><img src="/assets/window-icons/x.svg" alt="" aria-hidden="true"></button>`
    : ["tradeRoom", "tradeOffers", "humanTradeOffers", "fantasyPlayer", "dashboardPlayer", "dashboardStaff", "draftProspect", "freeAgentPlayer", "freeAgentNegotiation", "freeAgentComparison", "staffNegotiation", "contractExtension"].includes(state.modal.kind)
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
    <div class="modal-shell${modalClass}" role="dialog" aria-modal="true" aria-label="${escapeAttr(state.modal.title || "Detail")}">
      <header class="modal-head${hasClipboardTitlebar ? " card-board-titlebar" : ""}">
        <div>
          ${hasClipboardTitlebar ? `<span class="card-board-window-mark" aria-hidden="true"></span>` : ""}
          ${state.modal.subtitle ? `<p class="eyebrow">${escapeHtml(state.modal.subtitle)}</p>` : ""}
          <h3>${escapeHtml(state.modal.title || "Detail")}</h3>
        </div>
        ${seriesNavigation}
        ${closeControl}
      </header>
      <div class="modal-body">${state.modal.kind === "staffNegotiation" ? `<div class="staff-negotiation-content">${state.modal.body || ""}</div>` : state.modal.body || ""}</div>
    </div>`;
  if(typeof wireWantModal==='function')wireWantModal(els.modalRoot);
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
    els.modalRoot.querySelector("[data-report-issue]")?.addEventListener("click", openIssueReport);
    els.modalRoot.querySelector("[data-return-save-selection]")?.addEventListener("click", returnToSaveSelection);
    els.modalRoot.querySelector("[data-replay-tutorial]")?.addEventListener("click", () => {
      state.modal = null;
      renderModal();
      startGameTutorial(true);
    });
  }
  if (state.modal.kind === "issueReport") {
    els.modalRoot.querySelector("[data-issue-report-form]")?.addEventListener("submit", downloadIssueReport);
  }
  if (state.modal.kind === "staffNegotiation") {
    els.modalRoot.querySelector("[data-staff-negotiation-form]")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      await submitDashboardStaffNegotiation();
    });
    const salary = els.modalRoot.querySelector("[data-staff-offer-salary]");
    salary?.addEventListener("input", () => {
      const maximum = Number(state.modal?.maxOffer || 0);
      const amount = Number(salary?.value || 0);
      salary?.setCustomValidity(amount > maximum + 0.001 ? `Maximum legal offer is ${money(maximum)}.` : "");
      updateStaffOfferInterest();
    });
    els.modalRoot.querySelector("[data-staff-offer-years]")?.addEventListener("input", () => updateStaffOfferInterest());
  }
  if (state.modal.kind === "contractExtension") wireExtensionNegotiationModal();
  if (isBoxScore) wireBoxScorePages(els.modalRoot, state.modal);
  if (state.modal.kind === "tradeDeadline") {
    const resume = state.modal.deadlineResume;
    els.modalRoot.querySelector('[data-enter-trade-deadline]')?.addEventListener('click', async () => {
      acknowledgeTradeDeadline(resume?.trade_deadline_confirmed || tradeDeadlineDate());
      closeAllModals();
      try { await openTradeRoomModal("builder"); } catch (error) { showToast(error.message || "Could not open trade tools.", true); }
    });
    els.modalRoot.querySelector('[data-sim-through-deadline]')?.addEventListener('click', async () => {
      acknowledgeTradeDeadline(resume?.trade_deadline_confirmed || tradeDeadlineDate());
      closeAllModals();
      // The prompt opens while the sim that reached the deadline is still finishing (playback, refresh); advance()
      // ignores a request made during that window, so wait for it to settle instead of silently doing nothing.
      try {
        if (!(await waitForSimulationIdle())) return showToast("The sim is still finishing. Try Sim to... again in a moment.", true);
        await advance(resume);
      } catch (error) { showToast(error.message || "Could not continue the sim.", true); }
    });
  }
  if (state.modal.kind === "postseason") {
    els.modalRoot.querySelector('[data-review-postseason]')?.addEventListener('click', () => {
      closeAllModals();
    });
  }
  if (state.modal.kind === 'champion') els.modalRoot.querySelector('[data-champion-bracket]')?.addEventListener('click',()=>window.CardBoard?.open('phase-playoffs-bracket'));
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
      const secure = els.modalRoot.querySelector('#faGuaranteed')?.checked !== false;
      const minutes = Number(freeAgencyCandidate(state.selectedFreeAgent)?.previous_mpg || 0);
      const securityPenalty = secure ? 0 : 8 + Math.min(12, minutes * .4) + Math.max(0, 16-minutes) * .3;
      const displayedInterest = Math.max(0, Math.round(interest-securityPenalty));
      const interestBar = els.modalRoot.querySelector("[data-fa-live-interest]");
      if (interestBar) interestBar.style.width = `${displayedInterest}%`;
      const interestValue = els.modalRoot.querySelector("[data-fa-live-interest-value]");
      if (interestValue) interestValue.textContent = `${displayedInterest} / 100`;
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
    els.modalRoot.querySelector('#faGuaranteed')?.addEventListener('change', clampOffer);
  }
  if (state.modal.kind === "freeAgentPlayer") {
    els.modalRoot.querySelector("[data-fa-card-negotiate]")?.addEventListener("click", (event) => openFreeAgentNegotiation(event.currentTarget.dataset.faCardNegotiate || ""));
  }
  if (state.modal.kind === "freeAgentComparison") {
    els.modalRoot.querySelectorAll("[data-fa-comparison-card]").forEach((button) => button.addEventListener("click", () => freeAgentPlayerCard(button.dataset.faComparisonCard || "")));
    els.modalRoot.querySelectorAll("[data-fa-comparison-negotiate]").forEach((button) => button.addEventListener("click", () => openFreeAgentNegotiation(button.dataset.faComparisonNegotiate || "")));
  }
  wireDashboardPlayerCards(els.modalRoot);
  els.modalRoot.querySelectorAll("[data-dashboard-staff-card]").forEach(button => {
    button.addEventListener("click", () => dashboardCoachCard(button.dataset.dashboardStaffCard));
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
  if (state.modal?.kind === "staffNegotiation" && state.modal.outcome) mountStaffNegotiationOutcome(state.modal);
}

function wirePlayerFinderModal() {
  const root=els.modalRoot;
  const finder=state.playerFinder;
  finder.filters ||= [];
  const redrawFilters=()=>{root.querySelector('[data-player-finder-filters]').innerHTML=playerFinderFiltersMarkup(); refreshPlayerFinderTable();};
  root.querySelector('[data-player-finder-name]')?.addEventListener('input',event=>{finder.name=event.target.value;refreshPlayerFinderTable();});
  root.querySelector('[data-player-finder-add]')?.addEventListener('click',()=>{
    finder.filters.push({field:'overall',operator:'>',value:''});redrawFilters();
    root.querySelector('.player-finder-filter:last-child [data-finder-field]')?.focus();
  });
  const filters=root.querySelector('[data-player-finder-filters]');
  filters?.addEventListener('change',event=>{
    if(!event.target.matches('[data-finder-field]')) return;
    const index=Number(event.target.closest('[data-finder-filter]').dataset.finderFilter), filter=finder.filters[index];
    filter.field=event.target.value;
    if(!playerFinderOperators(filter.field).includes(filter.operator)) filter.operator=playerFinderOperators(filter.field)[0];
    redrawFilters();root.querySelector(`[data-finder-filter="${index}"] [data-finder-field]`)?.focus();
  });
  filters?.addEventListener('input',event=>{
    if(!event.target.matches('[data-finder-value]')) return;
    finder.filters[Number(event.target.closest('[data-finder-filter]').dataset.finderFilter)].value=event.target.value;
    refreshPlayerFinderTable();
  });
  filters?.addEventListener('click',event=>{
    const row=event.target.closest('[data-finder-filter]');if(!row) return;
    const index=Number(row.dataset.finderFilter), filter=finder.filters[index];
    if(event.target.closest('[data-finder-remove]')) {
      finder.filters.splice(index,1);redrawFilters();
      (root.querySelector(`[data-finder-filter="${Math.min(index,finder.filters.length-1)}"] [data-finder-remove]`) || root.querySelector('[data-player-finder-add]'))?.focus();
    } else if(event.target.closest('[data-finder-operator]')) {
      const operators=playerFinderOperators(filter.field);filter.operator=operators[(operators.indexOf(filter.operator)+1)%operators.length];
      redrawFilters();root.querySelector(`[data-finder-filter="${index}"] [data-finder-operator]`)?.focus();
    }
  });
  const wrap=root.querySelector('#playerFinderTableWrap');
  wrap?.addEventListener('click',async event=>{
    const sort=event.target.closest('[data-finder-sort]');
    if(sort){const key=sort.dataset.finderSort;finder.sortDirection=finder.sortField===key?(finder.sortDirection==='asc'?'desc':'asc'):['player','team','position','height'].includes(key)?'asc':'desc';finder.sortField=key;refreshPlayerFinderTable();root.querySelector(`[data-finder-sort="${key}"]`)?.focus();return;}
    const row=event.target.closest('[data-finder-player]');if(!row) return;
    const player=finder.payload.rows.find(player=>player.id===row.dataset.finderPlayer);if(!player) return;
    if(event.target.closest('[data-finder-trade]')) {
      if(!player.team_id || player.team_abbrev==='FA') return;
      try {await openTradeRoomModal('finder',{targetTeam:player.team_abbrev,targetPlayerId:player.id});} catch(error){showToast(error.message || 'Could not open Trade Finder.',true);}
    } else await dashboardPlayerCard(player.id);
  });
  wrap?.addEventListener('keydown',event=>{
    if(event.target.matches('[data-finder-player]') && ['Enter',' '].includes(event.key)){event.preventDefault();void dashboardPlayerCard(event.target.dataset.finderPlayer);}
  });
  refreshPlayerFinderTable();
}

function refreshPlayerFinderTable() {
  const finder=state.playerFinder || {}, payload=finder.payload || {};
  const rows=filteredPlayerFinderRows(payload.rows || []);
  const count=document.getElementById('playerFinderCount');
  if(count) count.textContent=`${rows.length} / ${payload.rows?.length || 0} players`;
  const wrap=document.getElementById('playerFinderTableWrap');
  if(wrap){wrap.innerHTML=playerFinderTable(rows);wrap.scrollTop=0;}
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
  const currentDate = state.data?.dashboard?.current_date;
  if (currentDate && state.rotationDraftDate !== currentDate) {
    state.rotationDraft = {};
    state.rotationLockedPlayerIds.clear();
    state.rotationDraftDate = currentDate;
  }
  const rosterIds = new Set(rows.map(row => row.id));
  for (const id of Object.keys(state.rotationDraft)) {
    if (!rosterIds.has(id)) delete state.rotationDraft[id];
  }
  for (const id of state.rotationLockedPlayerIds) {
    if (!rosterIds.has(id)) state.rotationLockedPlayerIds.delete(id);
  }
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
  rebalanceInjuredRotationDraft(rows);
}

function rebalanceInjuredRotationDraft(rows) {
  const roster = rows.filter((row) => row?.id && !row.__summaryEmpty);
  const injured = roster.filter((row) => isPlayerInjured(row.health));
  if (!injured.length) return;
  for (const row of injured) {
    state.rotationDraft[row.id] = 0;
    state.rotationLockedPlayerIds.delete(row.id);
  }
  const healthy = roster.filter((row) => !isPlayerInjured(row.health));
  for (const row of healthy) {
    state.rotationDraft[row.id] = clampNumber(Math.round(Number(state.rotationDraft[row.id] || 0)), 0, 48);
  }
  let remaining = Math.max(0, 240 - healthy.reduce((sum, row) => sum + Number(state.rotationDraft[row.id] || 0), 0));
  const weights = new Map(healthy.map((row) => [
    row.id,
    Math.max(
      0.25,
      Number(state.rotationDraft[row.id] || 0),
      Number(row.rotation_target_minutes ?? row.coach_minutes_projection ?? row.minutes_projection ?? 0),
      Number(rating(row, "overall") || 0) / 12,
    ),
  ]));
  while (remaining > 0 && healthy.some((row) => Number(state.rotationDraft[row.id] || 0) < 48)) {
    const candidate = healthy
      .filter((row) => Number(state.rotationDraft[row.id] || 0) < 48)
      .sort((left, right) => {
        const leftScore = Number(weights.get(left.id) || 0) / (Number(state.rotationDraft[left.id] || 0) + 1);
        const rightScore = Number(weights.get(right.id) || 0) / (Number(state.rotationDraft[right.id] || 0) + 1);
        return rightScore - leftScore || String(left.name || "").localeCompare(String(right.name || ""));
      })[0];
    if (!candidate) break;
    state.rotationDraft[candidate.id] = Number(state.rotationDraft[candidate.id] || 0) + 1;
    remaining -= 1;
  }
}

function autofillRotationDraft(rows) {
  const roster = rows.filter((row) => row?.id && !row.__summaryEmpty);
  const rosterIds = new Set(roster.map((row) => row.id));
  for (const playerId of [...state.rotationLockedPlayerIds]) {
    if (!rosterIds.has(playerId)) state.rotationLockedPlayerIds.delete(playerId);
  }
  for (const row of roster) {
    if (isPlayerInjured(row.health)) {
      state.rotationDraft[row.id] = 0;
      state.rotationLockedPlayerIds.delete(row.id);
    }
  }

  const available = roster.filter((row) => !isPlayerInjured(row.health));
  const locked = available.filter((row) => state.rotationLockedPlayerIds.has(row.id));
  const unlocked = available.filter((row) => !state.rotationLockedPlayerIds.has(row.id));
  const lockedTotal = locked.reduce((sum, row) => sum + Number(state.rotationDraft[row.id] || 0), 0);
  let remaining = Math.max(0, 240 - lockedTotal);

  const automaticMinutes = new Map(unlocked.map((row) => [
    row.id,
    Math.max(0, Number(row.automatic_minutes_projection ?? row.rotation_target_minutes ?? row.coach_minutes_projection ?? row.minutes_projection ?? 0)),
  ]));
  const automaticTotal = [...automaticMinutes.values()].reduce((sum, value) => sum + value, 0);
  if (locked.length === 0 && Math.round(automaticTotal) === 240) {
    for (const row of available) {
      state.rotationDraft[row.id] = Math.round(automaticMinutes.get(row.id) || 0);
    }
    return;
  }

  for (const row of unlocked) state.rotationDraft[row.id] = 0;

  const weights = new Map(unlocked.map((row) => [
    row.id,
    Math.max(0.25, Number(automaticMinutes.get(row.id) || 0)),
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
    const reset = input.closest(".season-minute-control")?.querySelector("[data-minute-reset-player]");
    if (reset) reset.hidden = !state.rotationLockedPlayerIds.has(playerId);
    const fill = input.closest(".season-minute-slider")?.querySelector(".season-minute-fill");
    if (fill) fill.style.width = `${(value / 48 * 100).toFixed(2)}%`;
    const output = Array.from(root.querySelectorAll("[data-minute-output]")).find((node) => node.dataset.minuteOutput === playerId)
      || input.closest(".rotation-row")?.querySelector("output");
    if (output) output.textContent = String(value);
  });
  if (root.matches?.(".season-minutes-table")) reorderMinutesTable(root);
  root.querySelectorAll(".season-minutes-table").forEach(reorderMinutesTable);
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
  const headers = ["Player", "Pos", "Height", "Age", "OVR", "OFF", "DEF", "Shot", "Create", "Space", "Pass", "Reb", "Rim", "Ath", "GP", "Set", "MPG", "PTS", "REB", "AST", "STL", "BLK", "TO", ...(includeContracts ? seasons : [])];
  return table(headers, summaryRows, (row) => [
        summaryPlayerNameCell(row, true),
        compactPos(row.position),
        heightFromRow(row) || "—",
        row.age ?? "—",
        html(compactRatingBar(rating(row, "overall"))),
        html(compactRatingBar(row.offense ?? row.ratings?.offense ?? averageNumber([row.ratings?.shooting,row.ratings?.creation,row.ratings?.passing].filter(value=>value!=null),0))),
        html(compactRatingBar(rating(row, "defense"))),
        tieredRating(rating(row, "shooting"), "shooting", state.data.dashboard?.rating_tertiles),
        tieredRating(rating(row, "creation"), "creation", state.data.dashboard?.rating_tertiles),
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

function salaryHorizonChart({seasons=[],rows=[],capByYear={},highlightPlayerId='',payrollByYear={},offer=false,className='',scaleMaximum=null,colorPlayerIds=[]}={}) {
  const horizon=[...seasons].slice(0,4);
  while(horizon.length<4) horizon.push(`Year ${horizon.length+1}`);
  const colorIds = [...new Set([...colorPlayerIds,...rows.map((row,index)=>String(row.id||row.player_id||index))])].sort();
  const values=horizon.map(season=>{
    const cap=capByYear?.[season]||{};
    const salaries=rows.map((row,index)=>{const id=String(row.id||row.player_id||index);return {id,name:row.name||row.player_name||row.full_name||'',salary:Number(row.salary_by_year?.[season]||0),index:colorIds.indexOf(id)};}).filter(item=>item.salary>0).sort((a,b)=>b.salary-a.salary||a.id.localeCompare(b.id));
    const known=salaries.reduce((sum,item)=>sum+item.salary,0);
    const payroll=Number(payrollByYear?.[season] ?? cap.salary_total_millions ?? known);
    return {season,cap,salaries,payroll:Math.max(payroll,known),remainder:Math.max(0,payroll-known)};
  });
  const maximum=Number(scaleMaximum)>0 ? Number(scaleMaximum) : Math.max(1,...values.flatMap(({cap,payroll})=>[payroll,Number(cap.tax_line_millions||0),Number(cap.hard_cap_millions||0)]))*1.06;
  const pct=value=>clampNumber(Number(value||0)/maximum*100,0,100);
  return `<div class="salary-horizon-chart${className?` ${escapeAttr(className)}`:''}${highlightPlayerId?' is-player-focus':''}${offer?' is-offer':''}">${values.map(({season,cap,salaries,payroll,remainder})=>{
    let segments=salaries;
    if(highlightPlayerId){
      const focus=salaries.filter(item=>item.id===String(highlightPlayerId));
      const other=salaries.filter(item=>item.id!==String(highlightPlayerId)).reduce((sum,item)=>sum+item.salary,0)+remainder;
      segments=[...(other>0?[{id:'other',salary:other,index:-1}]:[]),...focus];
    } else if(remainder>0) {
      const waived = Math.min(remainder, Number(cap.waived_salary_millions || 0));
      segments=[...(remainder>waived?[{id:'other',salary:remainder-waived,index:-1}]:[]),
        ...(waived>0?[{id:'waived',name:`Waived salary${Number(cap.unverified_waived_reserve_millions)>0?' (includes unverified reserves)':''}`,salary:waived,index:-1}]:[]),...segments];
    }
    const tax=Number(cap.tax_line_millions||0),hard=Number(cap.hard_cap_millions||0);
    const focusedSalary=salaries.find(item=>item.id===String(highlightPlayerId))?.salary||0;
    const displaySalary=highlightPlayerId?focusedSalary:payroll;
    return `<div class="salary-horizon-year"><span>${escapeHtml(shortSeasonLabel(season))}</span><div class="salary-horizon-column" role="img" aria-label="${escapeAttr(`${season} payroll ${money(payroll)}, tax ${money(tax)}, hard cap ${money(hard)}`)}"><div class="salary-horizon-stack" style="height:${pct(payroll)}%">${segments.map(item=>`<i class="salary-segment salary-segment-${item.index<0?'other':item.index%8}${item.id===String(highlightPlayerId)?' is-highlighted':''}" style="height:${payroll?clampNumber(item.salary/payroll*100,0,100):0}%" title="${escapeAttr(item.id==='other'?`Other payroll: ${money(item.salary)}`:`${money(item.salary)} · ${item.name || 'Unknown player'}`)}"></i>`).join('')}</div>${tax?`<b class="salary-tax-line" style="bottom:${pct(tax)}%"></b>`:''}${hard?`<b class="salary-hard-line" style="bottom:${pct(hard)}%"></b>`:''}</div><strong>${displaySalary?money(displaySalary):'—'}</strong></div>`;
  }).join('')}<div class="salary-horizon-legend"><span>Tax</span><span>Hard cap</span></div></div>`;
}

function playerHeadshotMarkup(row, className = "player-headshot") {
  if (row.is_prospect) return `<span class="player-headshot-frame prospect-profile-placeholder" aria-label="Blank profile portrait"><svg class="${escapeAttr(className)}" viewBox="0 0 220 160" role="img" aria-label="Blank profile portrait"><rect width="220" height="160" fill="#e4e8eb"/><circle cx="110" cy="57" r="32" fill="#a9b3bc"/><path d="M43 160v-10c0-39 30-61 67-61s67 22 67 61v10" fill="#a9b3bc"/></svg></span>`;
  const source = String(row.headshot_url || "").trim();
  if (!source) return "";
  return `<span class="player-headshot-frame" aria-hidden="true"><img class="${escapeAttr(className)}" src="${escapeAttr(source)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" /></span>`;
}

function summaryPlayerNameCell(row, interactive = false, includePortrait = false) {
  const name = row.name || "";
  if (!interactive) {
    return isPlayerInjured(row.health) || playerHasRust(row.health) ? html(playerNameWithInjuryMarkup(row, name)) : name;
  }
  const portrait = includePortrait ? playerHeadshotMarkup(row, "roster-player-headshot") : "";
  return html(`<button class="summary-player-card-button${includePortrait ? " roster-player-card-button" : ""}" data-dashboard-player-card="${escapeAttr(row.id)}" aria-label="Open player card for ${escapeAttr(name)}">${portrait}${playerNameWithInjuryMarkup(row, name)}</button>`);
}

function playerInjuryStatusMarkup(row) {
  if (!isPlayerInjured(row.health)) return "";
  const games = injuryGamesRemaining(row);
  const description = games === null ? "Injured" : `Injured, ${games} game${games === 1 ? "" : "s"} remaining`;
  return `<span class="season-injury-status" role="img" aria-label="${escapeAttr(description)}" title="${escapeAttr(description)}"><span aria-hidden="true">✚</span>${games === null ? "" : `<span>${games}</span>`}</span>`;
}

function playerNameWithInjuryMarkup(row, name = row.name || row.player_name || "Unknown") {
  return `<span class="summary-player-name-label player-name-with-injury"><span class="player-name-text">${escapeHtml(name)}</span>${playerInjuryStatusMarkup(row)}${playerRustMarkup(row)}${playerRestMarkup(row)}</span>`;
}

// Back from injury but rusty: the engine lowers this player's in-game ratings by `rust_penalty` points for his first
// games back (`rust_games`), and the coach eases his minutes back (`minutes_limit_pct` of normal for
// `minutes_limit_games` more games). Shown as a small red down arrow with the exact penalty.
function playerHasRust(health) {
  return Boolean(health) && !isPlayerInjured(health) && Number(health.rust_penalty) >= 0.1;
}

function playerRustMarkup(row) {
  if (!playerHasRust(row?.health)) return "";
  const penalty = Number(row.health.rust_penalty);
  const games = Number(row.health.rust_games ?? row.health.rust_days);
  const limitPct = Number(row.health.minutes_limit_pct);
  const limitGames = Number(row.health.minutes_limit_games);
  const fades = Number.isFinite(games) ? `, fades over his next ${games} game${games === 1 ? "" : "s"}` : "";
  const limit = Number.isFinite(limitPct) && limitPct < 100 && Number.isFinite(limitGames)
    ? `. Minutes limit: about ${limitPct}% of his usual minutes next game, back to full over ${limitGames} game${limitGames === 1 ? "" : "s"}` : "";
  const description = `Rusty after injury: in-game ratings −${penalty.toFixed(1)}${fades}${limit}`;
  return `<span class="season-injury-status player-rust-status" role="img" aria-label="${escapeAttr(description)}" title="${escapeAttr(description)}"><span aria-hidden="true">↓</span><span>${penalty.toFixed(1)}</span></span>`;
}

// The coach's rest suggestion for the user's own team (the same rule AI coaches follow; never applied automatically).
function playerRestMarkup(row) {
  const suggestion = row?.health?.rest_suggestion;
  if (!suggestion || isPlayerInjured(row.health)) return "";
  const when = suggestion.date ? ` on ${suggestion.date}` : "";
  const what = suggestion.kind === "shutdown" ? "shutting him down for the rest of the season" : `resting him${when}`;
  const description = `Coach suggests ${what}: ${suggestion.reason}. Set his minutes to 0 to follow it.`;
  return `<span class="season-injury-status player-rest-status" role="img" aria-label="${escapeAttr(description)}" title="${escapeAttr(description)}"><span aria-hidden="true">zZ</span></span>`;
}

function injuryGamesRemaining(row) {
  if (!isPlayerInjured(row.health)) return null;
  const labelMatch = String(row.health?.label || "").match(/~\s*(\d+)\s*g/i);
  if (labelMatch) return Number(labelMatch[1]);
  const remaining = row.health?.days_left;
  if (remaining == null || remaining === "") return null;
  const daysLeft = Number(remaining);
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
  const injured = isPlayerInjured(row.health);
  const value = injured ? 0 : clampNumber(Number(state.rotationDraft[row.id] ?? row.minutes_projection ?? 0), 0, 48);
  return html(`
    <div class="summary-minute-control">
      <input type="range" min="0" max="48" step="1" value="${value}" data-minute-player="${escapeAttr(row.id)}" ${editable && !injured ? "" : "disabled"} />
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
    ${tradeDeadlineCalendarNotice(month)}
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
    ${sectionHead("Player Development", "Overall change this season (Oct-Jun)", isNew ? `<span class="development-new-badge">NEW</span>` : "")}
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
      headshot_url: row.headshot_url || existing?.headshot_url || "",
      position: compactPos(row.position || existing?.position || ""),
      age: row.age ?? existing?.age ?? null,
      current: Number.isFinite(current) && current > 0 ? current : Number(existing?.current || 0),
      upside_remaining: Number(row.upside_remaining ?? existing?.upside_remaining ?? 0),
      decline_watch: row.decline_watch ?? existing?.decline_watch ?? null,
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
  // Real OVR changes are small (tenths per month), so the axis fits the data instead of a fixed +/-5.
  const limit = developmentAxisLimit(series.flatMap((line) => line.values));
  const paddedMin = -limit;
  const paddedMax = limit;
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
      <text class="trend-axis left" x="${padX}" y="${padY - 4}">+${limit}</text>
      <text class="trend-axis left" x="${padX}" y="${height / 2 - 4}">0</text>
      <text class="trend-axis left" x="${padX}" y="${height - padY - 4}">-${limit}</text>
      ${paths}
      ${months.map((month, index) => {
        const x = padX + (index / Math.max(1, months.length - 1)) * (width - padX * 2);
        return `<text class="trend-axis development-axis" x="${x.toFixed(1)}" y="${height - 3}">${escapeHtml(month.label)}</text>`;
      }).join("")}
    </svg>`;
}

// Smallest "nice" symmetric axis limit (OVR points) that holds every value; never below 1.
function developmentAxisLimit(values) {
  const peak = Math.max(0, ...values.filter(Number.isFinite).map((value) => Math.abs(value)));
  return [1, 2, 3, 5, 10, 20].find((step) => peak <= step) ?? Math.ceil(peak);
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
  return `<div class="calendar-cell ${past ? "past" : ""}${cell.date === tradeDeadlineDate() ? " trade-deadline-day" : ""}">
    <strong>${Number(cell.date.slice(-2))}</strong>
    ${cell.date === tradeDeadlineDate() ? '<strong class="trade-deadline-day-label">Trade deadline</strong>' : ""}
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
    if (button.dataset.playerCardWired) return;
    button.dataset.playerCardWired = "true";
    button.addEventListener("click", () => {
      dashboardPlayerCard(button.dataset.dashboardPlayerCard || "");
    });
  });
}

function wireDashboardProspectCards(root = els.content) {
  root.querySelectorAll("[data-draft-prospect-card]").forEach((button) => {
    if (button.dataset.prospectCardWired) return;
    button.dataset.prospectCardWired = "true";
    button.addEventListener("click", () => draftProspectCard(button.dataset.draftProspectCard));
  });
}

function wireDashboardStaffCards(root = els.content) {
  root.querySelectorAll("[data-dashboard-staff-card]").forEach((button) => {
    button.addEventListener("click", () => dashboardCoachCard(button.dataset.dashboardStaffCard || ""));
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
      else openLeagueActivityCard();
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
    input.addEventListener("change", async () => {
      try {
        await saveRotationMinutes({ quiet: true });
        normalizeMinutesDomOrder(input.closest(".season-minutes-table"));
      } catch (error) {
        state.rotationDraft = {};
        state.rotationLockedPlayerIds.clear();
        if (state.view === "dashboard") renderDashboard();
        showToast(`Minutes were not saved. ${error.message || String(error)}`, true);
      }
    });
  });
  root.querySelectorAll("[data-minute-reset-player]").forEach((button) => {
    button.addEventListener("click", () => resetRotationMinutes(button.dataset.minuteResetPlayer));
  });
}

function wireRotationResetAllControl(root = document) {
  const button = root.querySelector('[data-board-window="minutes"] [data-minute-reset-all]');
  if (!button || button.dataset.rotationResetWired) return;
  button.dataset.rotationResetWired = "true";
  button.disabled = state.hydrating || teamLabel(state.data.dashboard?.team || state.dashboardTeam || userTeam()) !== userTeam();
  button.addEventListener("click", () => resetRotationMinutes());
}

async function resetRotationMinutes(playerId = "") {
  if (state.simulationRunning || state.hydrating || state.busy) return;
  const rows = rosterRows(state.data.dashboard || {});
  if (!rows.length) return;
  ensureRotationDraft(rows);
  if (playerId) {
    const row = rows.find((item) => String(item.id) === String(playerId));
    if (!row || isPlayerInjured(row.health) || !state.rotationLockedPlayerIds.has(String(playerId))) return;
    state.rotationLockedPlayerIds.delete(String(playerId));
  } else {
    state.rotationLockedPlayerIds.clear();
  }
  autofillRotationDraft(rows);
  const table = document.querySelector('[data-board-window="minutes"] .season-minutes-table');
  syncRotationInputs(table || els.content);
  try {
    await saveRotationMinutes({quiet:true});
  } catch (error) {
    state.rotationDraft = {};
    state.rotationLockedPlayerIds.clear();
    if (state.view === "dashboard") renderDashboard();
    showToast(`Minutes were not reset. ${error.message || String(error)}`, true);
  }
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
  wirePlayerGameScoreCharts();
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
  wireDashboardProspectCards();
  wireDashboardStaffCards();
  wireSummaryContractToggle();
  wireLeaguePanelControls();
  wireFreeAgentModeToggles();
  wireDevelopmentLegend();
  wireDashboardStaffControls(editable);
  els.content.querySelectorAll("[data-dashboard-view]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (["staff", "calendar", "draft", "playoffs", "freeagents", "freeagency"].includes(button.dataset.dashboardView)) return openClipboardWindow(button.dataset.dashboardView);
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
  const previousSignals = state.view === "dashboard" ? captureTeamSignalBars() : null;
  const result = await action("set_rotation_minutes", {
    ...savePayload(),
    team: userTeam(),
    minutes,
    locked_player_ids: lockedPlayerIds,
  });
  if (result.status === "blocked") {
    if (options.quiet) throw new Error(result.reason || "Rotation update blocked.");
    return showToast(result.reason || "Rotation update blocked.", true);
  }
  state.data.dashboard = result.dashboard;
  state.data.statusDashboard = result.dashboard;
  if (JSON.stringify(state.rotationDraft) === JSON.stringify(minutes)) {
    state.rotationDraft = {};
    state.rotationLockedPlayerIds.clear();
  }
  if (options.quiet) {
    if (state.view === "dashboard") {
      renderDashboard();
      animateTeamSignalsFrom(previousSignals);
    }
    return;
  }
  renderDashboard();
  animateTeamSignalsFrom(previousSignals);
  showToast("Rotation saved");
}

function seriesCard(series) {
  const teams = series.teams || [];
  const scores = series.score || [];
  const winner = teamLabel(series.winner);
  const winnerId = series.winner_team_id || series.winner?.id;
  const completed = series.status === "completed";
  const status = rowLabel(series.status || "");
  const gameCount = (series.game_ids || []).length;
  const tag = gameCount ? "button" : "div";
  const interaction = gameCount
    ? `type="button" data-playoff-series="${escapeAttr(series.id || "")}" aria-label="Open latest box score for ${escapeAttr(`${teamLabel(teams[0])} versus ${teamLabel(teams[1])}`)}"`
    : "";
  const title = gameCount
    ? `Open latest box score · ${gameCount} game${gameCount === 1 ? "" : "s"} played`
    : `${rowLabel(series.round || "Series")} · ${status}`;
  const teamRow = (team, score) => {
    const label = teamLabel(team);
    const id = team?.id || team?.team_id || (typeof team === "string" && team.startsWith("team_") ? team : "");
    const isWinner = winnerId ? id === winnerId : Boolean(winner && winner === label);
    const isLoser = completed && winnerId && id && id !== winnerId;
    const outcome = isWinner ? "series-team-winner" : isLoser ? "series-team-loser" : "";
    return `<div class="series-team ${outcome}"${id ? ` data-team-id="${escapeAttr(id)}"` : ""}>${teamLogoSrc(label) ? `<img src="${escapeAttr(teamLogoSrc(label))}" alt="" />` : ""}<strong>${escapeHtml(label || "TBD")}</strong><span>${score ?? 0}</span></div>`;
  };
  const firstTeam = teams[0];
  const secondTeam = teams[1] || (series.pending_seed ? `Play-in #${series.pending_seed}` : "");
  return `
    <${tag} class="series-card ${gameCount ? "series-card-button" : "series-card-empty"}" ${interaction} title="${escapeAttr(title)}">
      ${teamRow(firstTeam, scores[0])}
      ${teamRow(secondTeam, scores[1])}
    </${tag}>`;
}

function playoffBracket(series, champion, playIn = {}) {
  const west = bracketConferenceRounds("West", series);
  const east = bracketConferenceRounds("East", series);
  const final = bracketSeriesFromFeeders(series.find(item => item.round === "finals"), [west[2][0], east[2][0]], "finals-preview", "finals");
  return `
    <div class="tournament-bracket">
      ${bracketConference("West", series, playIn.West, west)}
      <div class="bracket-finals">
        <div class="bracket-conference-title">Finals</div>
      <div class="bracket-node final-node" data-bracket-series="finals">${seriesCard(final)}</div>
        ${champion ? `<div class="bracket-champion">Champion: ${escapeHtml(teamLabel(champion))}</div>` : ""}
      </div>
      ${bracketConference("East", series, playIn.East, east)}
    </div>`;
}

function bracketSeriesFromFeeders(actual, feeders, id, round) {
  const sourceIds = feeders.map(s => s.id);
  const winners = feeders.map(s => s.winner || s.teams?.find(t => t?.id === s.winner_team_id));
  if (!actual) return {id, round, teams:winners, score:[0, 0], source_series_ids:sourceIds};
  const indices = winners.map(winner => winner ? (actual.teams || []).findIndex(team => team?.id === winner.id) : -1);
  if (indices.every(i => i >= 0) && new Set(indices).size === 2) {
    return {...actual, source_series_ids:sourceIds, teams:indices.map(i => actual.teams[i]), score:indices.map(i => actual.score?.[i] ?? 0)};
  }
  return {...actual, source_series_ids:sourceIds};
}

function bracketConferenceRounds(conference, series) {
  let first = series.filter(s => s.conference === conference && s.round === "first_round");
  const originalOrder = new Map(first.map((s, i) => [s.id, s.bracket_slot ?? i]));
  first.sort((a, b) => originalOrder.get(a.id) - originalOrder.get(b.id));
  const actualSemis = series.filter(s => s.conference === conference && s.round === "conference_semifinals");
  const feeders = parent => {
    const explicit = parent.source_series_ids || [];
    return first.filter(child => explicit.length ? explicit.includes(child.id) :
      (parent.team_ids || (parent.teams || []).map(t => t?.id)).some(id => id &&
        (id === child.winner_team_id || id === child.winner?.id || (child.team_ids || (child.teams || []).map(t => t?.id)).includes(id))));
  };
  // Old careers may contain alphabetically paired semifinals. Display their
  // actual branches together without altering matchups or played results.
  actualSemis.sort((a, b) => Math.min(...feeders(a).map(s => originalOrder.get(s.id))) - Math.min(...feeders(b).map(s => originalOrder.get(s.id))));
  const grouped = actualSemis.flatMap(feeders);
  first = [...new Map([...grouped, ...first].map(s => [s.id, s])).values()];
  const semis = [0, 1].map(i => {
    const children = first.slice(i * 2, i * 2 + 2);
    return bracketSeriesFromFeeders(actualSemis[i], children, `${conference}:semi:${i}`, "conference_semifinals");
  });
  const final = bracketSeriesFromFeeders(series.find(s => s.conference === conference && s.round === "conference_finals"), semis, `${conference}:final`, "conference_finals");
  return [first, semis, [final]];
}

function bracketConference(conference, series, playIn, rounds = bracketConferenceRounds(conference, series)) {
  const roundOrder = ["first_round", "conference_semifinals", "conference_finals"];
  return `
    <div class="bracket-conference ${conference.toLowerCase()}">
      <div class="bracket-conference-title">${escapeHtml(conference)}</div>
      <div class="bracket-rounds">
        ${playIn ? bracketPlayIn(conference, playIn, rounds[0]) : `<div class="bracket-round"><div class="bracket-round-title">Play-In</div><div class="bracket-placeholder">Not recorded</div></div>`}
        ${roundOrder.map((round, i) => bracketRound(round, rounds[i], rounds[i + 1], conference)).join("")}
      </div>
    </div>`;
}

function playoffGameOutcome(game) {
  if (!game || game.home_score == null || game.away_score == null) return null;
  const homeScore = Number(game.home_score), awayScore = Number(game.away_score);
  if (!Number.isFinite(homeScore) || !Number.isFinite(awayScore) || homeScore === awayScore) return null;
  const homeId = game.home_team_id || game.home_team?.id;
  const awayId = game.away_team_id || game.away_team?.id;
  const homeTeam = game.home_team || homeId;
  const awayTeam = game.away_team || awayId;
  return homeScore > awayScore
    ? {winnerId:homeId,loserId:awayId,winner:homeTeam,loser:awayTeam}
    : {winnerId:awayId,loserId:homeId,winner:awayTeam,loser:homeTeam};
}

function bracketPlayIn(conference, playIn, firstRound = []) {
  const teams = playIn.teams || {};
  const games = playIn.games || [];
  const toward = conference === "West" ? "→" : "←";
  const teamRow = (team, score, outcome = "") => {
    const label = teamLabel(team);
    const logo = teamLogoSrc(label);
    const id = team?.id || team?.team_id || (typeof team === "string" && team.startsWith("team_") ? team : "");
    return `<div class="series-team ${outcome}"${id ? ` data-team-id="${escapeAttr(id)}"` : ""}>${logo ? `<img src="${escapeAttr(logo)}" alt="" />` : ""}<strong>${escapeHtml(label || "TBD")}</strong><span>${score}</span></div>`;
  };
  const match = (index, label, away, home) => {
    const game = games[index];
    if (!game) return `<div class="bracket-node" data-play-in-stage="${index}" style="grid-row:${index === 2 ? '1 / 3' : index === 1 ? '4 / 6' : '7 / 9'}"><div class="bracket-round-title">${label}</div><div class="series-card series-card-empty">${teamRow(away, "—")}${teamRow(home, "—")}</div></div>`;
    const outcome = playoffGameOutcome(game);
    const rowOutcome = team => {
      const id = team?.id || team?.team_id;
      if (!outcome || !id) return "";
      if (id === outcome.winnerId) return "series-team-winner";
      return index === 0 ? "series-team-advancing" : "series-team-loser";
    };
    return `<div class="bracket-node" data-play-in-stage="${index}" style="grid-row:${index === 2 ? '1 / 3' : index === 1 ? '4 / 6' : '7 / 9'}"><div class="bracket-round-title">${label}</div><button type="button" class="series-card series-card-button" data-game-box="${escapeAttr(game.game_id)}">${teamRow(game.away_team, game.away_score ?? 0, rowOutcome(game.away_team))}${teamRow(game.home_team, game.home_score ?? 0, rowOutcome(game.home_team))}</button></div>`;
  };
  const finalNineTen = playoffGameOutcome(games[1])?.winner || "9/10 winner";
  const finalSevenEight = playoffGameOutcome(games[0])?.loser || "7/8 loser";
  const qualifiers = [[8, playIn.seed_8_team_id || teams["8"]?.id, 50], [7, playIn.seed_7_team_id || teams["7"]?.id, 350]];
  const conferenceKey = conference.toLowerCase();
  const flowMarker = `bracket-play-in-flow-${conferenceKey}`;
  const qualifierMarker = `bracket-play-in-qualifier-${conferenceKey}`;
  const paths = qualifiers.map(([seed, teamId, y]) => {
    const slot = firstRound.findIndex(s => String(s.pending_seed) === String(seed) || teamId && (s.team_ids || (s.teams || []).map(t => t?.id)).includes(teamId));
    return slot < 0 ? "" : `<path data-qualifier-seed="${seed}" data-to-series="${escapeAttr(firstRound[slot].id)}" marker-end="url(#${qualifierMarker})" d="M0 ${y} H9 V${50 + slot * 100} H18"/>`;
  }).join("");
  return `<div class="bracket-round bracket-play-in">
    <div class="bracket-round-title"${playIn.status === "not_recorded" ? ' title="This career has no recorded play-in results."' : ""}>Play-In${playIn.status === "not_recorded" ? " · Unrecorded" : ""}</div>
    <div class="bracket-node-stack">
      ${match(2, `Final · Winner ${toward} #8`, finalNineTen, finalSevenEight)}
      ${match(1, "9 vs 10 · Winner ↑", teamLabel(teams["10"]), teamLabel(teams["9"]))}
      ${match(0, `7 vs 8 · Winner ${toward} #7`, teamLabel(teams["8"]), teamLabel(teams["7"]))}
      <svg class="play-in-feeder-links" viewBox="0 0 30 400" preserveAspectRatio="none" aria-hidden="true"><defs>${bracketArrowMarker(flowMarker)}</defs><path data-playin-flow="9-10-winner" marker-end="url(#${flowMarker})" d="M30 200 H18 V34 H30"/><path data-playin-flow="7-8-loser" marker-end="url(#${flowMarker})" d="M30 350 H6 V62 H30"/></svg>
      <span class="play-in-feeder-label winner">Winner</span>
      <span class="play-in-feeder-label loser">Loser</span>
      <svg class="bracket-round-links" viewBox="0 0 18 400" preserveAspectRatio="none" aria-hidden="true"><defs>${bracketArrowMarker(qualifierMarker)}</defs>${paths}</svg>
    </div>
  </div>`;
}

function bracketArrowMarker(id) {
  return `<marker id="${escapeAttr(id)}" viewBox="0 0 5 5" markerWidth="5" markerHeight="5" refX="4.5" refY="2.5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L5 2.5 L0 5 Z" fill="var(--season-line)" stroke="none"/></marker>`;
}

function bracketRound(round, roundSeries, nextSeries, conference = "") {
  const label = {
    first_round: "First Round",
    conference_semifinals: "Semifinals",
    conference_finals: "Conference Final",
  }[round] || rowLabel(round);
  const markerId = `bracket-link-${conference.toLowerCase()}-${round}`;
  return `
    <div class="bracket-round bracket-${escapeAttr(round)}">
      <div class="bracket-round-title">${escapeHtml(label)}</div>
      <div class="bracket-node-stack">
        ${roundSeries.length
          ? roundSeries.map((item, i) => `<div class="bracket-node" data-bracket-series="${escapeAttr(item.id || '')}" style="grid-row:${round === 'first_round' ? `${1 + i * 2} / ${3 + i * 2}` : round === 'conference_semifinals' ? `${2 + i * 4} / ${4 + i * 4}` : '4 / 6'}">${seriesCard(item)}</div>`).join("")
          : `<div class="bracket-node bracket-placeholder">TBD</div>`}
        ${nextSeries ? `<svg class="bracket-round-links" viewBox="0 0 18 400" preserveAspectRatio="none" aria-hidden="true"><defs>${bracketArrowMarker(markerId)}</defs>${roundSeries.map((item, i) => {
          const target = nextSeries.findIndex(s => s.source_series_ids?.includes(item.id));
          if (target < 0) return "";
          const startY = round === 'first_round' ? 50 + i * 100 : 100 + i * 200;
          const endY = round === 'first_round' ? 100 + target * 200 : 200;
          return `<path data-from-series="${escapeAttr(item.id)}" data-to-series="${escapeAttr(nextSeries[target].id)}" marker-end="url(#${markerId})" d="M0 ${startY} H9 V${endY} H18"/>`;
        }).join('')}</svg>` : round === "conference_finals" ? `<svg class="bracket-round-links" viewBox="0 0 18 400" preserveAspectRatio="none" aria-hidden="true"><defs>${bracketArrowMarker(markerId)}</defs><path data-from-series="${escapeAttr(roundSeries[0]?.id || "")}" data-to-series="finals" marker-end="url(#${markerId})" d="M0 200 H18"/></svg>` : ""}
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
  wireTradePickTerms(root);
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
  root.querySelectorAll("[data-trade-destination]").forEach(select => select.addEventListener("change", () => {
    state.tradeAssetRoutes ||= {};
    state.tradeAssetRoutes[select.dataset.tradeDestination] = select.value;
    state.tradeCandidate = null;
    state.tradeIdentityPreview = null;
    renderTradeRoom();
  }));
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

function selectedPackage(title, items, side, team, teamPayload = null) {
  const total = selectedTradeValue(items);
  return `
    <section class="trade-selected-package ${teamPayload ? "trade-builder-package" : ""}" ${teamBrandStyle(team)}>
      ${teamPayload ? `<header class="trade-package-builder-header">
        ${tradeTeamHeading(team, teamPayload)}
        <div class="trade-package-total"><span>${escapeHtml(title)}</span><strong>${total.toFixed(1)}</strong></div>
      </header>` : `<header>
        <div>${teamLogoSrc(team) ? `<img src="${escapeAttr(teamLogoSrc(team))}" alt="" />` : ""}<span>${escapeHtml(title)}</span></div>
        <strong>${total.toFixed(1)}</strong>
      </header>`}
      <div class="trade-selected-list" data-trade-scroll="selected-${escapeAttr(side)}" tabindex="0" aria-label="${escapeAttr(title)}">
        ${items.length ? tradeAssetTable(items, {removeSide:side, label:title, routeFrom:(state.tradeAdditionalTeams || []).length ? team : null}) : `<div class="trade-package-empty"><p>No assets selected</p></div>`}
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
  const source = tradeSidePayload(side);
  const asset = (source.assets || []).find((item) => item.id === id && item.kind === kind);
  if (!asset) return;
  const list = selectedList(side);
  const existing = list.findIndex((item) => item.id === id);
  if (existing >= 0) list.splice(existing, 1);
  else {
    if (state.tradeTab === "finder" && list.length >= 2) return showToast("Trade Finder can search up to two assets at once.", true);
    list.push({
      ...asset,
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
  pruneTradePickRules();
  if (state.tradeTab === "finder") {
    state.tradeResults = [];
    state.tradeSearchCompleted = false;
  }
  renderTradeRoom();
}

function selectedList(side) {
  if (String(side).startsWith("extra:")) {
    state.tradeExtraSelections ||= {};
    return state.tradeExtraSelections[String(side).slice(6)] ||= [];
  }
  return side === "from" ? state.selectedFrom : state.selectedTo;
}

function removeAsset(side, id) {
  const list = selectedList(side);
  const idx = list.findIndex((item) => item.id === id);
  if (idx >= 0) list.splice(idx, 1);
  pruneTradePickRules();
  state.tradeCandidate = null;
  if (state.tradeTab === "finder") {
    state.tradeResults = [];
    state.tradeSearchCompleted = false;
  }
  renderTradeRoom();
}

function assetSpec(asset) {
  return { kind: asset.kind, value: asset.value || asset.id };
}

function tradeReadout(candidate) {
  if (!candidate) return `<div class="trade-evaluation-empty"><strong>Not evaluated</strong><span>Salary matching · Roster limits · Team decisions</span></div>`;
  const legal = candidate.legality?.status || "unknown";
  const userId = state.home?.save?.user_team?.id;
  const partners = (candidate.evaluations || []).filter(row => row.perspective_team_id !== userId && teamLabel(row.perspective_team_id) !== userTeam());
  const canApply = legal === "legal" && partners.length > 0 && partners.every(row => row.accepted);
  return `
    <div class="trade-evaluation-board" aria-live="polite">
      <div class="trade-evaluation-title">${tradeLegalityBadge(candidate)}<strong>${canApply ? "All partners accept" : legal === "legal" ? "Partner declines" : "Trade cannot proceed"}</strong></div>
      ${tradeLegalityIssues(candidate)}
      <button id="applyBuiltTrade" class="trade-execute-button ui-command" ${canApply ? "" : "disabled"}>${canApply ? "Accept Trade" : legal !== "legal" ? "Trade unavailable" : "Partner declines"}</button>
    </div>`;
}

function tradeResultCards(results) {
  if (!results.length) return state.tradeSearchCompleted
    ? `<div class="trade-results-empty"><strong>No matching offers</strong><p>No legal, approved trades matched this package and team. Try another team or adjust the selected assets.</p></div>`
    : `<div class="trade-results-empty"><strong>Select assets to find trades</strong><p>Choose up to two players or draft assets, then search. You can review each returned offer in the builder.</p></div>`;
  return results.map((result, index) => tradeCandidateCard(result, index, "finder")).join("");
}

function playerSummaryRatings(player) {
  const ratings = player.ratings || {};
  const offenseParts = [ratings.shooting, ratings.creation, ratings.passing].filter(value => value != null && Number.isFinite(Number(value))).map(Number);
  const header = player.inputs_profile?.header;
  const values = header ? [["OVR", header.ovr], ["OFF", header.off], ["DEF", header.def]] : [
    ["OVR", player.overall ?? ratings.overall],
    ["OFF", player.offense ?? ratings.offense ?? (offenseParts.length ? offenseParts.reduce((sum,value) => sum + value, 0) / offenseParts.length : null)],
    ["DEF", player.defense ?? ratings.defense],
  ];
  return `<span class="player-summary-ratings">${values.map(([label,value]) => `<span class="player-summary-rating"><small>${label}</small><span class="linked-rating assets-rating-bar"><span>${value == null ? "—" : draftMetric(value)}</span><i>${value == null ? "" : `<b style="${performanceBarStyle(Number(value))}"></b>`}</i></span></span>`).join("")}</span>`;
}

function tradeAssetContract(asset) {
  const salaries = Object.entries(asset.salary_by_year || {}).filter(([, value]) => Number(value) > 0).sort(([a], [b]) => a.localeCompare(b));
  if (!salaries.length && !asset.contract_terms?.length) return escapeHtml(asset.contract || "—");
  const schedule = salaries.map(([season, amount]) => `${shortSeasonLabel(season)} ${money(amount)}`).join(" · ");
  const terms = asset.contract_terms?.length ? asset.contract_terms : [{salary:Number(salaries[0][1])*1_000_000, years:salaries.length}];
  const label = terms.map(term => `${money(Number(term.salary)/1_000_000)} x ${term.years}`).join(", ");
  return `<span title="${escapeAttr(schedule)}">${escapeHtml(label)}</span>`;
}

function tradeKnownNumber(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
}

function tradeInsightPager(labels, page, key) {
  return `<nav class="trade-insight-pager" aria-label="Trade detail pages"><strong>${escapeHtml(labels[page])}</strong><span>${page + 1} / ${labels.length}</span><button type="button" class="ui-command trade-icon-button" data-trade-insight-step="-1" data-trade-insight-key="${escapeAttr(key)}" data-trade-insight-count="${labels.length}" aria-label="Previous trade detail page" title="Previous page" ${page === 0 ? "disabled" : ""}>&larr;</button><button type="button" class="ui-command trade-icon-button" data-trade-insight-step="1" data-trade-insight-key="${escapeAttr(key)}" data-trade-insight-count="${labels.length}" aria-label="Next trade detail page" title="Next page" ${page === labels.length - 1 ? "disabled" : ""}>&rarr;</button></nav>`;
}

function wireTradeInsightPagers(root) {
  root.querySelectorAll("[data-trade-insight-step]").forEach(button => button.addEventListener("click", () => {
    const key = button.dataset.tradeInsightKey;
    const current = key === "builder" ? state.tradeInsightPage || 0 : state.tradeOfferPages?.[key] || 0;
    const page = Math.max(0, Math.min(Number(button.dataset.tradeInsightCount) - 1, current + Number(button.dataset.tradeInsightStep)));
    if (key === "builder") state.tradeInsightPage = page;
    else { state.tradeOfferPages ||= {}; state.tradeOfferPages[key] = page; }
    if (state.modal?.kind === "tradeOffers") {
      state.modal.body = tradeOffersModalBody(state.modal.offers || []);
      renderModal();
    } else if (state.modal?.kind === "tradeRoom") renderTradeRoom();
    else renderOffers();
    const selector = `[data-trade-insight-key="${CSS.escape(key)}"][data-trade-insight-step="${button.dataset.tradeInsightStep}"]`;
    const target = els.modalRoot?.querySelector(selector) || els.content?.querySelector(selector);
    (target?.disabled ? target.parentElement.querySelector("button:not(:disabled)") : target)?.focus({preventScroll:true});
  }));
}

function tradeResponseEffect(result) {
  const toast = typeof document !== "undefined" ? document.getElementById("toast") : null;
  if (!toast) return;
  toast.classList.remove("trade-response-accepted", "trade-response-declined");
  void toast.offsetWidth;
  toast.classList.add(`trade-response-${result}`);
}

function tradeIdentityContext() {
  const participants = tradeWorkspaceParticipants();
  const wanted = state.tradeIdentityTeam === "partner" ? "to" : state.tradeIdentityTeam === "user" ? "from" : state.tradeIdentityTeam || "from";
  const participant = participants.find(row => row.side === wanted) || participants[0];
  const players = participant.payload.players || [];
  const outgoing = participant.selected;
  const incoming = tradeReceivedAssets(participant.team,participants);
  const team = participant.team;
  const after = window.TradeProjection.afterRoster(players, outgoing, incoming);
  const key = JSON.stringify([state.currentSave, state.home?.save?.current_date, team, players.map(row => [row.id,row.mpg,row.ratings,row.health]), outgoing.map(row => [row.kind,row.id]), incoming.map(row => [row.kind,row.id,row.mpg,row.ratings,row.health])]);
  return {key,team,side:participant.side,players,after,changed:outgoing.some(row => row.kind === "player") || incoming.some(row => row.kind === "player")};
}

function tradeIdentityPage() {
  const context = tradeIdentityContext();
  const preview = state.tradeIdentityPreview;
  const toolbar = `<div class="trade-identity-toolbar"><div>${tradeWorkspaceParticipants().map(({side,team}) => `<button type="button" class="ui-command" data-trade-identity-team="${escapeAttr(side)}" aria-pressed="${context.side === side}">${escapeHtml(team)}</button>`).join("")}</div><span>Rotation-weighted projection · 240 minutes</span></div>`;
  if (preview?.key !== context.key || preview.status === "loading") return `${toolbar}<div class="trade-identity-empty" role="status">Loading player spatial profiles${preview?.loaded != null ? ` · ${preview.loaded}/${preview.total}` : ""}</div>`;
  if (preview.error) return `${toolbar}<div class="trade-identity-empty" role="status">${escapeHtml(preview.error)} <button type="button" class="ui-command" data-trade-identity-retry>Retry</button></div>`;
  const before = window.TradeProjection.rotation(context.players);
  const after = context.changed ? window.TradeProjection.rotation(context.after, true) : before;
  if (!before || !after) return `${toolbar}<div class="trade-identity-empty">At least five available players are required for a 240-minute projection.</div>`;
  const a = window.TradeProjection.combine(before, preview.profiles, `trade-${context.team}-before`);
  const b = window.TradeProjection.combine(after, preview.profiles, `trade-${context.team}-after`);
  if (!a || !b) return `${toolbar}<div class="trade-identity-empty">Complete spatial reference data is unavailable for this rotation.</div>`;
  const beforeById = new Map(before.map(row => [row.id,row.minutes]));
  return `${toolbar}<div class="trade-identity-comparison"><section><h4>Before trade</h4>${spatialHeatmapMarkup(a,{compact:true})}</section><section><h4>After trade</h4>${spatialHeatmapMarkup(b,{compact:true})}</section></div><details class="trade-inferred-minutes"><summary>Inferred minutes</summary><table><thead><tr><th>Player</th><th>Before</th><th>After</th><th>Change</th></tr></thead><tbody>${[...new Map([...before,...after].map(row => [row.id,row])).values()].map(row => { const old = beforeById.get(row.id) || 0; const next = after.find(item => item.id === row.id)?.minutes || 0; return `<tr><th>${escapeHtml(row.name || row.label)}</th><td>${old}</td><td>${next}</td><td>${next-old > 0 ? "+" : ""}${next-old}</td></tr>`; }).join("")}</tbody></table></details><p class="trade-projection-note">Illustrative minutes, not a saved rotation. Current injuries excluded. Coaching, chemistry and lineup interactions are not re-simulated.</p>`;
}

async function loadTradeIdentity(force = false) {
  const context = tradeIdentityContext();
  if (!force && state.tradeIdentityPreview?.key === context.key && state.tradeIdentityPreview.status !== "cancelled") return;
  const players = [...new Map([...context.players,...context.after].map(row => [row.id,row])).values()];
  const preview = {key:context.key,status:"loading",profiles:{},loaded:0,total:players.length};
  state.tradeIdentityPreview = preview;
  const save = state.currentSave;
  try {
    for (let index=0; index<players.length; index+=2) {
      if (state.tradeIdentityPreview !== preview || save !== state.currentSave || state.modal?.kind !== "tradeRoom" || state.tradeInsightPage !== 3) { preview.status = "cancelled"; return; }
      const results = await Promise.all(players.slice(index,index+2).map(row => action("player_card", {...savePayload(),player_id:row.id})));
      if (state.tradeIdentityPreview !== preview || save !== state.currentSave) return;
      results.forEach((result,offset) => { preview.profiles[players[index+offset].id] = result.spatial_profile; preview.loaded++; });
      const progress = els.modalRoot?.querySelector(".trade-identity-empty");
      if (progress && state.tradeIdentityPreview === preview) progress.textContent = `Loading player spatial profiles · ${preview.loaded}/${preview.total}`;
    }
    preview.status = "ready";
  } catch (error) { preview.status = "error"; preview.error = error.message || "Spatial preview could not be loaded."; }
  if (state.tradeIdentityPreview === preview && state.modal?.kind === "tradeRoom" && state.tradeInsightPage === 3) renderTradeRoom();
}

function tradeAssetTable(assets, options = {}) {
  const control = options.side || options.removeSide;
  return `<table class="trade-ledger${options.routeFrom ? " is-routed" : ""}" aria-label="${escapeAttr(options.label || "Trade assets")}"><thead><tr>${control ? '<th class="trade-ledger-control"><span class="sr-only">Select or remove</span></th>' : ""}${options.routeFrom ? '<th class="trade-ledger-route">Destination</th>' : ""}<th class="trade-ledger-portrait" aria-label="Portrait"></th><th>Player / Asset</th><th>Age</th><th>Height</th><th>Pos</th><th>OVR</th><th>OFF</th><th>DEF</th><th title="Growth runway: room this player has left to improve, from age, role and current level, on a 0-5 scale. Not a prediction of a future rating; 0 for most players 27 and older.">Runway</th><th title="Model injury-risk index, not a probability. Standard player scores range from 0 to 34.">Injury risk</th><th>Contract</th><th title="Owner-context asset value; final evaluation includes destination fit and role">Value</th></tr></thead><tbody>${assets.map(asset => tradeAssetRow(asset, options)).join("")}</tbody></table>`;
}

function tradeAssetRow(asset, {side, removeSide, routeFrom} = {}) {
  const id = asset.id || asset.value || "";
  const name = asset.name || asset.label || id || "Unknown";
  const selected = side ? selectedList(side).some(item => item.id === id && item.kind === asset.kind) : false;
  const control = side ? `<td><input type="checkbox" data-asset-side="${escapeAttr(side)}" data-asset-kind="${escapeAttr(asset.kind)}" data-asset-id="${escapeAttr(id)}" aria-label="${selected ? "Remove" : "Add"} ${escapeAttr(name)} ${selected ? "from" : "to"} package" ${selected ? "checked" : ""}></td>` : removeSide ? `<td><button type="button" class="trade-row-remove trade-icon-button" data-remove-side="${escapeAttr(removeSide)}" data-asset-id="${escapeAttr(id)}" aria-label="Remove ${escapeAttr(name)}" title="Remove ${escapeAttr(name)}"><img src="/assets/window-icons/x.svg" alt="" /></button></td>` : "";
  const route = routeFrom ? `<td class="trade-ledger-route"><select data-trade-destination="${escapeAttr(tradeRouteKey(routeFrom,asset))}" aria-label="Destination for ${escapeAttr(name)}">${tradeWorkspaceParticipants().filter(row => row.team !== routeFrom).map(row => `<option value="${escapeAttr(row.team)}" ${tradeAssetDestination(routeFrom,asset) === row.team ? "selected" : ""}>${escapeHtml(row.team)}</option>`).join("")}</select></td>` : "";
  if (asset.kind !== "player") {
    const condition = String(asset.condition_summary || asset.protection_summary || "").trim();
    const label = asset.label || asset.name || id || "Draft asset";
    const extra = condition && !/^unprotected[.\s]*$/i.test(condition) && !label.toLowerCase().includes(condition.toLowerCase()) ? condition : "";
    const rule=(side || removeSide) ? (state.tradePickRules || []).find(r=>r.pick_id===id && r.enabled!==false) : null;
    const authored = rule ? rule.type==='pick_swap' ? `${rule.benefit==='worse'?'Less':'More'} favorable swap right` : `Picks ${rule.from}–${rule.through} protected` : '';
    return `<tr class="trade-ledger-pick${selected ? " is-selected" : ""}">${control}${route}<td>${draftAssetGlyph(asset, true, true)}</td><td colspan="10"><strong>${escapeHtml(label)}</strong>${extra || authored ? `<span class="trade-pick-condition">${escapeHtml(authored || extra)}</span>` : ""}<small>${asset.kind === "pick_swap" || rule?.type==='pick_swap' ? "Swap right" : "Draft pick"}</small></td><td class="trade-ledger-value">${draftMetric(tradeKnownNumber(asset.trade_value))}</td></tr>`;
  }
  const ratings = asset.ratings || {};
  const offense = [ratings.shooting, ratings.creation, ratings.passing].map(tradeKnownNumber).filter(value => value !== null);
  const values = [asset.overall ?? ratings.overall, asset.offense ?? ratings.offense ?? (offense.length ? offense.reduce((a,b) => a+b,0) / offense.length : null), asset.defense ?? ratings.defense];
  const injury = typeof isPlayerInjured === "function" && isPlayerInjured(asset.health);
  const ratingCell = value => { const n = tradeKnownNumber(value); return `<td class="trade-ledger-rating">${draftMetric(n)}<i aria-hidden="true">${n === null ? "" : `<b style="width:${clampNumber(n,0,100)}%"></b>`}</i></td>`; };
  const meter = (label, value, max) => { const n = tradeKnownNumber(value); return `<td class="trade-ledger-meter" title="${escapeAttr(label)}${n === null ? " unavailable" : ` ${n.toFixed(1)}${label === "Runway" ? `/${max}` : " model index"}`}"><span>${draftMetric(n)}${n === null || label !== "Runway" ? "" : `<small>/${max}</small>`}</span><i aria-hidden="true">${n === null ? "" : `<b style="width:${clampNumber(n/max*100,0,100)}%"></b>`}</i></td>`; };
  const evidence = [asset.potential != null ? `Potential ${draftMetric(asset.potential)}` : "", asset.mpg != null ? `${draftMetric(asset.mpg)} MPG` : "", asset.ppg != null ? `${draftMetric(asset.ppg)} PPG` : ""].filter(Boolean).join(" · ");
  const salaries = Object.entries(asset.salary_by_year || {}).filter(([,value]) => Number(value) > 0).sort(([a],[b]) => a.localeCompare(b));
  return `<tr class="trade-ledger-player${selected ? " is-selected" : ""}${injury ? " is-injured" : ""}">${control}${route}<td>${playerHeadshotMarkup(asset, "trade-player-headshot") || '<span class="trade-portrait-empty" aria-hidden="true">&mdash;</span>'}</td><th scope="row"><button type="button" class="trade-player-link" data-dashboard-player-card="${escapeAttr(id)}" title="${escapeAttr(evidence || name)}">${playerNameWithInjuryMarkup(asset, name)}</button></th><td>${asset.age == null ? "—" : escapeHtml(asset.age)}</td><td>${escapeHtml(asset.height || "—")}</td><td>${escapeHtml(asset.position || "—")}</td>${values.map(ratingCell).join("")}${meter("Runway",asset.upside_remaining,5)}<td class="trade-ledger-meter trade-ledger-injury">${injuryRiskBody(asset.health_risk, asset.injury_body)}</td><td class="trade-ledger-contract">${salaries.length ? `<details><summary>${tradeAssetContract(asset)}</summary><div>${salaries.map(([season, amount]) => `<span>${escapeHtml(shortSeasonLabel(season))} <b>${money(Number(amount))}</b></span>`).join("")}${asset.contract ? `<span>${escapeHtml(asset.contract)}</span>` : ""}</div></details>` : tradeAssetContract(asset)}</td><td class="trade-ledger-value">${draftMetric(tradeKnownNumber(asset.trade_value))}</td></tr>`;
}

function tradeLegalityBadge(candidate) {
  const status = candidate?.legality?.status || "unknown";
  const labels = {legal:"Legal", illegal:"Illegal", manual_review_required:"Review required", unknown:"Not verified"};
  return `<span class="trade-legal-badge ${status === "legal" ? "legal" : status === "illegal" ? "illegal" : "review"}">${escapeHtml(labels[status] || rowLabel(status))}</span>`;
}

function tradeLegalityIssues(candidate) {
  const issues = [...(candidate?.legality?.issues || []), ...(candidate?.legality?.manual_review || [])];
  return issues.length ? `<ul class="trade-legality-issues">${issues.map(issue => `<li>${escapeHtml(textValue(issue))}</li>`).join("")}</ul>` : "";
}

function tradeCandidateInsights(candidate, key) {
  const page = Math.max(0, Math.min(1, state.tradeOfferPages?.[key] || 0));
  const proposal = candidate.proposal || {};
  if (proposal.transfers && page === 0) return `<details class="incoming-offer-evaluation" ${state.tradeOfferPages?.[key] != null ? 'open' : ''}><summary>Trade analysis</summary>${tradeInsightPager(['Team value','Payroll impact'],page,key)}<div class="trade-team-decisions">${(candidate.evaluations || []).map(tradeEvaluationPanel).join('')}</div></details>`;
  return `<details class="incoming-offer-evaluation" ${state.tradeOfferPages?.[key] != null ? "open" : ""}><summary>Trade analysis</summary>${tradeInsightPager(["Team value", "Payroll impact"], page, key)}${page === 0 ? `<div class="trade-team-decisions">${(candidate.evaluations || []).map(tradeEvaluationPanel).join("")}</div>${tradeSegmentedValueBoard(candidate, proposal.from_assets || [], proposal.to_assets || [], teamLabel(proposal.from_team_id || proposal.from_team), teamLabel(proposal.to_team_id || proposal.to_team))}` : `<div class="trade-candidate-finances">${Object.entries(candidate.team_finances || {}).map(([team, row]) => `<section><h4>${escapeHtml(teamLabel(team))}</h4><dl><div><dt>Current payroll</dt><dd>${row.cap?.salary_total_millions == null ? "—" : money(row.cap.salary_total_millions)}</dd></div><div><dt>Outgoing salary</dt><dd>${row.outgoing_salary_millions == null ? "—" : money(row.outgoing_salary_millions)}</dd></div><div><dt>Incoming salary</dt><dd>${row.incoming_salary_millions == null ? "—" : money(row.incoming_salary_millions)}</dd></div><div><dt>After trade</dt><dd>${row.payroll_after_millions == null ? "—" : money(row.payroll_after_millions)}</dd></div></dl></section>`).join("") || '<div class="trade-package-empty">Payroll details unavailable</div>'}</div>`}</details>`;
}

function incomingOfferAsset(asset) {
  return `<div class="trade-ledger-scroll">${tradeAssetTable([asset])}</div>`;
}

function incomingOfferSide(team, assets, { compact = false } = {}) {
  return `<section class="incoming-offer-side"><header>${teamLogoSrc(team)?`<img src="${escapeAttr(teamLogoSrc(team))}" alt="${escapeAttr(team)} logo">`:""}<strong>${escapeHtml(team)} receives</strong><span>${assets.length} asset${assets.length === 1 ? "" : "s"}</span></header><div class="trade-ledger-scroll" tabindex="0" aria-label="${escapeAttr(team)} incoming assets">${assets.length ? tradeAssetTable(assets, {label:`${team} receives`}) : '<div class="offer-pick offer-pick-empty">No assets in this package</div>'}</div></section>`;
}

function incomingOfferPackage(receipts) {
  return `<div class="incoming-offer-package">${receipts.map(({team,assets}) => incomingOfferSide(team,assets || [])).join("")}</div>`;
}

function tradeReceipts(proposal) {
  if (!proposal.transfers) return [{team:teamLabel(proposal.to_team_id || proposal.to_team),assets:proposal.from_assets},
    {team:teamLabel(proposal.from_team_id || proposal.from_team),assets:proposal.to_assets}];
  return [...new Set(proposal.transfers.flatMap(leg => [leg.from_team_id,leg.to_team_id]))].map(id => ({
    team:teamLabel(id),assets:proposal.transfers.filter(leg => leg.to_team_id === id).flatMap(leg => leg.assets)}));
}

function offerCard(offer, index) {
  const proposal = offer.proposal || {};
  const from = teamLabel(proposal.from_team_id || proposal.from_team);
  const to = teamLabel(proposal.to_team_id || proposal.to_team);
  const legal = offer.legality?.status || "unknown";
  const repeatCount = Math.max(1, Number(offer.repeat_count) || 1);
  const lastProposed = offer.repeat_dates?.at?.(-1) || offer.offer_context?.last_proposed_date || offer.offer_context?.created_date;
  const repeatedLabel = repeatCount > 1 ? `<small class="incoming-offer-repeat" title="This identical trade has been proposed ${repeatCount} times">Sent ${repeatCount}×${lastProposed ? ` · latest ${escapeHtml(lastProposed)}` : ""}</small>` : "";
  return `<article class="incoming-offer${repeatCount > 1 ? " incoming-offer--repeated" : ""}">
    <header class="incoming-offer-heading"><div><span>Offer ${index + 1}</span>${repeatedLabel}<strong>${escapeHtml(proposal.transfers ? tradeReceipts(proposal).map(row=>row.team).join(' ↔ ') : `${from} ↔ ${to}`)}</strong></div>${tradeLegalityBadge(offer)}</header>
    ${incomingOfferPackage(tradeReceipts(proposal))}
    ${typeof tradeWantsOfferSummary==='function'?tradeWantsOfferSummary(offer):''}
    ${tradeLegalityIssues(offer)}
    <div class="incoming-offer-analysis-row">
      ${tradeCandidateInsights(offer, proposal.id || `offer-${index}`)}
      <div class="incoming-offer-analysis-actions"><button class="ui-command" data-offer-reject="${index}">Decline</button><button class="ui-command" data-offer-accept="${index}" ${legal !== "legal" ? "disabled" : ""}>Accept Trade</button></div>
    </div>
  </article>`;
}

function tradeCandidateCard(candidate, index, mode) {
  const proposal = candidate?.proposal || {};
  const fromTeam = teamLabel(proposal.from_team_id || proposal.from_team || "");
  const toTeam = teamLabel(proposal.to_team_id || proposal.to_team || "");
  const legal = candidate?.legality?.status || "unknown";
  const evaluations = candidate?.evaluations || [];
  return `
    <article class="trade-candidate-card ${mode === "offer" ? "incoming" : "market"}">
      <header class="trade-candidate-head">
        <div><span>${mode === "offer" ? "Incoming proposal" : `Market offer ${index + 1}`}</span><strong>${escapeHtml(proposal.transfers ? tradeReceipts(proposal).map(row=>row.team).join(' ↔ ') : `${fromTeam} ↔ ${toTeam}`)}</strong></div>
        ${tradeLegalityBadge(candidate)}${mode !== "offer" ? `<button data-inspect-finder="${index}" class="ui-command">Review In Builder</button>` : ""}
      </header>
      ${incomingOfferPackage(tradeReceipts(proposal))}
      ${typeof tradeWantsOfferSummary==='function'?tradeWantsOfferSummary(candidate):''}
      ${tradeLegalityIssues(candidate)}
      ${tradeCandidateInsights(candidate, proposal.id || `finder-${index}`)}
      <footer>
        <p>${tradeReceipts(proposal).reduce((sum,row)=>sum+(row.assets?.length || 0),0)} assets · Review the package before accepting.</p>
        ${mode === "offer"
          ? `<div><button data-offer-reject="${index}" class="trade-reject-button">Reject</button><button data-offer-accept="${index}" class="trade-accept-button" ${legal === "legal" ? "" : "disabled"}>Accept Trade</button></div>`
          : `<button data-inspect-finder="${index}" class="trade-accept-button ui-command">Review In Builder</button>`}
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
  const net = tradeKnownNumber(row.net_value);
  const decision = String(row.decision || "").toLowerCase();
  const legality = String(row.legality_status || "legal").toLowerCase();
  const accepted = Boolean(row.accepted) || decision === "accept" || decision.startsWith("accept_");
  const outcome = legality === "manual_review_required" ? "Needs review" : legality === "illegal" ? "Cannot accept" : accepted ? decision === 'accept_bounded_ai_discretion' ? 'Accepts limited value loss' : "Would accept" : "Would decline";
  const outcomeClass = accepted && legality === "legal" ? "accepted" : "rejected";
  const notes = textValue(row.notes || "");
  const noteValue = (pattern) => {
    const match = notes.match(pattern);
    return match ? tradeKnownNumber(match[1]) : null;
  };
  const threshold = row.incoming_asset_value == null
    ? noteValue(/threshold\s+([+-]?\d+(?:\.\d+)?)/i) ?? tradeKnownNumber(row.acceptance_threshold)
    : tradeKnownNumber(row.acceptance_threshold);
  const rawScore = net !== null && threshold !== null ? 50 + (net-threshold)*4.5 : tradeKnownNumber(row.acceptance_score);
  const score = rawScore === null ? null : clampNumber(rawScore, 0, 100);
  const margin = net !== null && threshold !== null ? net-threshold : null;
  const strategic = noteValue(/strategic fit\s+([+-]?\d+(?:\.\d+)?)/i);
  const personality = tradeKnownNumber(row.personality_adjustments?.total) ?? noteValue(/personality adjustment\s+([+-]?\d+(?:\.\d+)?)/i);
  const phaseKey = row.window_phase || notes.match(/\bPhase=([^;.]+)/i)?.[1]?.trim() || '';
  const phase = ({peak:'Peak window',entering:'Entering peak window',exiting:'Exiting peak window',rebuilding:'Rebuilding',contending:'Peak window',contending_with_future_upside:'Peak window',developing:'Entering peak window',retooling:'Exiting peak window'})[phaseKey] || '';
  const signed = (value) => value == null ? "—" : `${value > 0 ? "+" : value < 0 ? "−" : ""}${Math.abs(value).toFixed(1)}`;
  const details = [
    ["Receives · roster value", row.incoming_asset_value == null ? '—' : Number(row.incoming_asset_value).toFixed(1)],
    ["Sends · roster value", row.outgoing_value == null ? '—' : Number(row.outgoing_value).toFixed(1)],
    ["Strategy + roster plan", signed(tradeKnownNumber(row.strategic_adjustment) ?? strategic)],
    ["Manager lean", signed(personality)],
    ["Net benefit", signed(net)],
    ["Required benefit", signed(threshold)],
    ["Team direction", phase],
  ].filter(([, value]) => value !== "—" && value !== "");
  const noteHasBreakdown = /\bPhase=/i.test(notes);
  return `
    <div class="trade-evaluation-panel ${outcomeClass}">
      <header><strong>${escapeHtml(row.team_abbrev || teamLabel(row.perspective_team_id))}</strong><span>${outcome}</span></header>
      ${margin === null ? "" : `<div class="trade-evaluation-score" title="Net benefit minus required benefit. A positive margin passes the value test; core, premium-return, roster and legality safeguards can still block a trade. Not an acceptance probability."><span>Value margin</span><strong>${signed(margin)} ${margin >= 0 ? 'above' : 'below'} line</strong></div><div class="trade-evaluation-meter"><i style="width:${score.toFixed(1)}%"></i></div>`}
      ${details.length ? `<dl class="trade-evaluation-details">${details.map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>` : ""}
      ${notes && !noteHasBreakdown ? `<p>${escapeHtml(notes)}</p>` : ""}
      ${(row.decision_reasons || []).length ? `<ul class="trade-decision-reasons">${row.decision_reasons.map(reason=>`<li>${escapeHtml(reason)}</li>`).join('')}</ul>` : ''}
      <details class="trade-value-help"><summary>Why this decision?</summary><p>Receives − sends + strategy and roster plan + manager lean = net benefit. The required benefit is specific to this deal. Meeting it is necessary for ordinary approval, but does not override core commitments, premium-player returns, roster planning or trade rules.${decision === 'accept_bounded_ai_discretion' ? ' This GM accepted a limited value loss through bounded negotiation discretion.' : ''}</p>${notes && noteHasBreakdown ? `<p>${escapeHtml(notes)}</p>` : ''}</details>
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
      <div class="item"><strong>Ratings</strong>${playerSummaryRatings(player)}</div>
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
      <div class="toolbar"><button ${staffActionAttributes(candidate.slot, "negotiate")} data-staff-id="${escapeAttr(candidate.id)}" data-staff-slot="${escapeAttr(candidate.slot)}" data-staff-ask="${escapeAttr(candidate.asking_salary_millions)}" data-staff-years="${escapeAttr(candidate.asking_years || 2)}">Offer And Hire</button></div>
    </div>`;
}

function prospectInjuryTitle(report) {
  if (!report?.available) return "No injury information on file";
  const history = report.history || [];
  const lines = [history.length
    ? `History: ${history.map((row) => `${row.body_area} (${row.severity}${row.season ? `, ${row.season}` : ""}${row.status ? `, ${row.status}` : ""})`).join("; ")}`
    : "History: none on file"];
  lines.push(report.current ? `Current: ${report.current.body_area} (${report.current.severity}), expected back ${report.current.return_date || "unknown"}` : "Current: healthy");
  lines.push(`Projected risk: ${report.risk_label || "unknown"}${report.injury_prone ? " (injury prone)" : ""}`);
  return lines.join("\n");
}

// Compact marker: current injury cross, past-injury count, projected-risk word. Empty when the engine has no medical data.
// compact: only show something notable (current injury, history, or above-low risk), for dense cards.
function prospectInjuryMarkup(report, { compact = false } = {}) {
  if (!report?.available) return "";
  const history = (report.history || []).length;
  if (compact && !history && !report.current && String(report.risk_label || "Low") === "Low") return "";
  const current = report.current ? `<span class="season-injury-status prospect-injury-current" aria-hidden="true">✚</span>` : "";
  const past = history ? `<span class="prospect-injury-history">${history} past</span>` : "";
  const risk = `<span class="prospect-injury-risk prospect-injury-risk-${escapeAttr(String(report.risk_label || "low").toLowerCase())}">${escapeHtml(report.risk_label || "Low")}</span>`;
  const title = prospectInjuryTitle(report);
  return `<span class="prospect-injury-marker" role="img" aria-label="${escapeAttr(title.replace(/\n/g, ". "))}" title="${escapeAttr(title)}">${current}${past}${risk}</span>`;
}

function draftBoardRows(board) {
  return (board?.entries || []).map((entry) => {
    const prospect = entry.prospect || entry;
    const scout = entry.scout_display || prospect.scout_display || {};
    const draftLow = Number(prospect.rank_range?.low), draftHigh = Number(prospect.rank_range?.high);
    const hasDraftRange = Number.isInteger(draftLow) && Number.isInteger(draftHigh) && draftLow >= 1 && draftHigh >= draftLow;
    return {
      id: prospect.id || prospect.prospect_id || entry.prospect_id,
      rank: entry.board_rank || prospect.rank || "",
      seasonStartRank: entry.season_start_rank ?? prospect.preseason_rank ?? prospect.rank,
      rankChange: entry.rank_change ?? (entry.season_start_rank != null ? Number(entry.season_start_rank) - Number(entry.board_rank || prospect.rank) : null),
      draftRangeLow: hasDraftRange ? draftLow : null,
      draftRangeHigh: hasDraftRange ? draftHigh : null,
      name: prospect.name,
      position: prospect.position,
      sourceTeam: prospect.source_team || "",
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
      injuryReport: prospect.injury_report || entry.injury_report || null,
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
    } else if (key === "injury") {
      const risk = (row) => (row.injuryReport?.available ? Number(row.injuryReport.risk_penalty) || 0 : -1);
      comparison = risk(left) - risk(right);
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
  return `<div class="table-wrap"><table class="data-table ${escapeAttr(tableId)}"><thead><tr>${headers.map((header, index) => `<th aria-sort="${sort?.index === index ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}"><button class="sort-head" data-sort-table="${escapeAttr(tableId)}" data-sort-index="${index}">${escapeHtml(header)}${sort?.index === index ? (sort.direction === "asc" ? " ↑" : " ↓") : ""}</button></th>`).join("")}</tr></thead><tbody>${mapped.map(({ cells }) => `<tr>${cells.map((cell) => `<td>${formatCell(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
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
      <button data-league-panel-view-all>${leadersMode ? "View All" : "Expand Wire"}</button>
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

function syncAssistantGMPhone() {
  window.AssistantGMPhone?.sync({
    saveKey: String(state.currentSave || ""),
    enabled: Boolean(state.currentSave && state.home && !state.hydrating && state.view === "dashboard"),
    messages: state.home?.league_events?.assistant_messages || [],
    onOpen: async (message) => {
      if (message.target === "trade-deadline") {
        showTradeDeadlinePrompt();
      } else if (message.target === "league-wire") {
        await openLeagueActivityCard();
        const post = [...document.querySelectorAll("[data-league-event-id]")].find(el => el.dataset.leagueEventId === message.event_id);
        const feed = post?.closest(".season-league-wire-expanded");
        if (post && feed) feed.scrollTo({top:feed.scrollTop + post.getBoundingClientRect().top - feed.getBoundingClientRect().top, behavior:"smooth"});
        if (post) post.classList.add("is-assistant-highlight");
      } else {
        state.dashboardTeam = userTeam();
        state.view = "dashboard";
        await loadDashboardSnapshot(userTeam());
        render();
        window.CardBoard?.open("contracts");
        const row = [...document.querySelectorAll('[data-board-window="contracts"] [data-dashboard-player-card]')].find(el => el.dataset.dashboardPlayerCard === message.player_id);
        row?.closest("tr")?.classList.add("is-assistant-highlight");
        const table = row?.closest(".linked-roster-scroll");
        if (row && table) table.scrollTo({top:Math.max(0, table.scrollTop + row.getBoundingClientRect().top - table.getBoundingClientRect().top - 30), behavior:"smooth"});
      }
    },
  });
}

async function openLeagueActivityCard() {
  closeAllModals();
  if (state.view !== "dashboard") {
    state.view = "dashboard";
    await ensureViewData();
    render();
  }
  window.CardBoard?.open("league-wire");
  return Boolean(window.CardBoard?.expand("league-wire"));
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
  const displayRatings = row.display_ratings || {};
  if (key === "rebound") key = "rebounding";
  if (key === "offense") {
    if (displayRatings.offense != null) return displayRatings.offense;
    const displayParts = [displayRatings.shooting, displayRatings.creation, displayRatings.passing].map(Number).filter(Number.isFinite);
    if (displayParts.length) return displayParts.reduce((sum, item) => sum + item, 0) / displayParts.length;
  } else if (displayRatings[key] != null || displayRatings[key.toUpperCase()] != null) {
    return displayRatings[key] ?? displayRatings[key.toUpperCase()];
  }
  const ratings = row.ratings || row.attributes || row.traits || {};
  if (key === "offense") {
    if (row.offense != null || ratings.offense != null) return row.offense ?? ratings.offense;
    const parts = [ratings.shooting, ratings.creation, ratings.passing].map(Number).filter(Number.isFinite);
    if (parts.length) return parts.reduce((sum, item) => sum + item, 0) / parts.length;
  }
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
  isBusy = isBusy || Boolean(state.simulationRunning);
  state.busy = isBusy;
  document.body.classList.toggle("busy", isBusy);
  for (const control of document.querySelectorAll("button, select, input, textarea")) {
    if (control.matches('[data-simulation-stop]')) {
      control.disabled = Boolean(state.simulationStopRequested);
      delete control.dataset.busyDisabled;
      continue;
    }
    if (control.matches('[data-phase-command="lottery-skip"]')) {
      control.disabled = false;
      delete control.dataset.busyDisabled;
      continue;
    }
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
