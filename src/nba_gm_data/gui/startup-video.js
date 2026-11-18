(() => {
  const screen = document.getElementById("startupScreen");
  const original = screen?.querySelector("video[data-startup-video]");
  if (!original) return;
  const standby = original.cloneNode(false);
  standby.removeAttribute("data-startup-video");
  standby.dataset.startupVideoBuffer = "";
  original.after(standby);
  const players = [original, standby];
  const noise = screen.querySelector("[data-startup-static]");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const defaultChannel = {src: "/assets/startup/video/front-office.mp4", poster: "/assets/startup/video/poster.jpg"};
  const failures = new Set();
  let channels = {};
  let manifestRequest;
  let active = null;
  let selectedTeam = "random";
  let hoveredTeam = null;
  let inTeamPicker = false;
  let generation = 0;
  let intentTimer;
  let noiseTimer;
  let loadTimer;
  let pendingKey = null;
  let currentTeam = null;
  let sceneIndex = 0;

  function eligible() {
    return !screen.hidden && !reducedMotion.matches && document.visibilityState === "visible";
  }
  function wantedKey() {
    const team = inTeamPicker ? (hoveredTeam || selectedTeam) : "random";
    return channels[team] && !failures.has(team) ? team : "random";
  }
  function release(player) {
    player.pause();
    player.classList.remove("is-active");
    if (player.hasAttribute("src")) { player.removeAttribute("src"); player.load(); }
    delete player.dataset.channel;
  }
  function endNoise() {
    clearTimeout(noiseTimer);
    noise?.pause();
    noise?.classList.remove("is-active");
  }
  function glitch() {
    if (!eligible() || !noise) return;
    endNoise();
    if (!noise.hasAttribute("src")) noise.src = "/assets/startup/video/teams/channel-static.mp4";
    noise.currentTime = .5; // Start at the same 600 ms burst used between montage shots.
    void noise.offsetWidth;
    noise.classList.add("is-active");
    Promise.resolve(noise.play()).catch(() => {});
    noiseTimer = setTimeout(endNoise, 650);
  }
  function loadCatalog() {
    if (!manifestRequest) {
      manifestRequest = fetch("/assets/startup/video/teams/manifest.json?v=reviewed-franchise-playlists-v2", {cache: "no-store"})
        .then(response => { if (!response.ok) throw new Error("Preview catalog unavailable"); return response.json(); })
        .then(manifest => { channels = manifest.teams || {}; if (eligible()) requestChannel(); })
        .catch(() => { manifestRequest = null; });
    }
  }
  function scenes(team) {
    if (team === "random") return [defaultChannel];
    const entry = channels[team];
    return entry?.playlist?.length ? entry.playlist : [entry];
  }
  function prepare(player, channel, key, team) {
    if (player.dataset.channel === key) return;
    release(player);
    player.poster = channel.poster || defaultChannel.poster;
    player.dataset.channel = key;
    player.dataset.team = team;
    player.muted = true;
    player.loop = team === "random" || !channels[team]?.playlist;
    player.playsInline = true;
    player.preload = "auto";
    player.src = channel.src;
    player.load();
  }
  function prefetch() {
    if (!eligible() || pendingKey || !active || currentTeam === "random" || wantedKey() !== currentTeam) return;
    const list = scenes(currentTeam);
    if (list.length < 2 || active.duration - active.currentTime > 3) return;
    const next = (sceneIndex + 1) % list.length;
    const buffer = players.find(player => player !== active);
    prepare(buffer, list[next], `${currentTeam}:${next}`, currentTeam);
  }
  function requestChannel() {
    clearTimeout(intentTimer);
    if (!eligible()) return;
    const team = wantedKey();
    // A default movie that failed to play stays on its poster until the next visit (failures clear on hide);
    // retrying on every click just repeated the failed load.
    if (team === "random" && failures.has("random")) return;
    const changed = team !== currentTeam;
    if (changed) { currentTeam = team; sceneIndex = 0; }
    const key = `${team}:${sceneIndex}`;
    if (key === pendingKey) return;
    if (active?.dataset.channel === key) {
      if (pendingKey) {
        generation += 1;
        clearTimeout(loadTimer);
        pendingKey = null;
        for (const player of players) if (player !== active) release(player);
      }
      Promise.resolve(active.play()).catch(() => {});
      return;
    }
    const request = ++generation;
    clearTimeout(loadTimer);
    const incoming = players.find(player => player !== active) || original;
    prepare(incoming, scenes(team)[sceneIndex], key, team);
    pendingKey = key;
    function failed(error) {
      if (request !== generation) return;
      clearTimeout(loadTimer);
      pendingKey = null;
      release(incoming);
      if (error?.name !== "NotAllowedError" && error?.name !== "AbortError") failures.add(team);
      if (team !== "random" && failures.has(team)) requestChannel();
    }
    loadTimer = setTimeout(() => failed(new Error("Preview load timed out")), 12000);
    Promise.resolve(incoming.play()).then(() => {
      if (request !== generation || !eligible()) return;
      if (wantedKey() !== team) {
        clearTimeout(loadTimer);
        pendingKey = null;
        release(incoming);
        schedule();
        return;
      }
      clearTimeout(loadTimer);
      pendingKey = null;
      const outgoing = active;
      if (outgoing && outgoing.dataset.team !== team) glitch();
      active = incoming;
      incoming.classList.add("is-active");
      screen.dataset.startupVideo = "playing";
      screen.dataset.startupTeamVideo = team;
      screen.dataset.startupScene = String(sceneIndex);
      if (outgoing && outgoing !== incoming) release(outgoing);
    }).catch(failed);
  }
  for (const player of players) {
    player.addEventListener("timeupdate", prefetch);
    player.addEventListener("ended", () => {
      if (player !== active || !eligible() || wantedKey() !== currentTeam || pendingKey) return;
      sceneIndex = (sceneIndex + 1) % scenes(currentTeam).length;
      requestChannel();
    });
  }
  function schedule() {
    clearTimeout(intentTimer);
    intentTimer = setTimeout(requestChannel, 180);
  }
  function selectTeam(team) { selectedTeam = team || "random"; hoveredTeam = null; schedule(); }
  function setContext(teamPicker) { inTeamPicker = Boolean(teamPicker); hoveredTeam = null; schedule(); }
  const wheel = document.getElementById("startupTeamWheel");
  wheel?.addEventListener("pointerover", event => {
    if (event.pointerType === "touch") return;
    const option = event.target.closest("[data-team-value]");
    if (!option || option.contains(event.relatedTarget)) return;
    hoveredTeam = option.dataset.teamValue;
    schedule();
  });
  wheel?.addEventListener("pointerout", event => {
    const option = event.target.closest("[data-team-value]");
    if (!option || option.contains(event.relatedTarget)) return;
    hoveredTeam = null;
    schedule();
  });
  function sync() {
    if (!eligible()) {
      generation += 1;
      clearTimeout(intentTimer);
      clearTimeout(loadTimer);
      pendingKey = null;
      endNoise();
      for (const player of players) player.pause();
      if (screen.hidden || reducedMotion.matches) {
        for (const player of players) release(player);
        if (noise?.hasAttribute("src")) { noise.removeAttribute("src"); noise.load(); }
        active = null;
        if (screen.hidden) failures.clear();
        delete screen.dataset.startupVideo;
        delete screen.dataset.startupTeamVideo;
      }
      return;
    }
    loadCatalog();
    requestChannel();
  }
  screen.addEventListener("pointerdown", () => { if (eligible()) requestChannel(); });
  screen.addEventListener("keydown", () => { if (eligible()) requestChannel(); });
  document.addEventListener("visibilitychange", sync);
  reducedMotion.addEventListener("change", sync);
  new MutationObserver(sync).observe(screen, {attributes: true, attributeFilter: ["hidden"]});
  window.StartupVideoBackdrop = {sync, selectTeam, setContext};
  sync();
})();
