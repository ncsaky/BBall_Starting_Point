/* Save-scoped Assistant GM texts. Content is supplied by the game backend. */
(() => {
  let saveKey = "", seen = new Set(), queued = [], current = null, host = null, leavingHost = null, enabled = false, onOpen = null, advanceTimer = null, autoTimer = null, draftPlaybackActive = false, simulationPlaybackActive = false, initialized = false;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const storageKey = () => `nbaGmAssistantTexts:v2:${saveKey}`;
  const persist = () => { try { localStorage.setItem(storageKey(), JSON.stringify([...seen].slice(-600))); } catch { /* Optional local preferences. */ } };
  function hide() {
    const transient = current?.kind === "draft_trade_batch" ? current : null;
    clearTimeout(autoTimer); autoTimer = null;
    clearTimeout(advanceTimer); advanceTimer = null;
    host?.remove(); leavingHost?.remove(); host = null; leavingHost = null;
    if (transient) { current = null; transient.onDismiss?.(); }
  }
  function notificationMessages() { return [current, ...queued].filter(message => message && message.kind !== "draft_trade_batch"); }
  function notificationLabel(message) {
    if (message?.target === "contracts") return "Contracts";
    if (message?.target === "trade-deadline") return "Trade deadline";
    return "League Activity";
  }
  function notificationPreview(message) {
    const text = String(message?.text || message?.title || "New league update").split(/(?<=[.!?])\s+/)[0];
    return text.length > 90 ? `${text.slice(0,87).trimEnd()}…` : text;
  }
  function renderNotificationBatch() {
    if (!host || !current || current.kind === "draft_trade_batch") return;
    const notices = notificationMessages();
    if (!notices.length) return;
    const first = notices[0];
    const count = notices.length;
    if (count === 1) {
      const preview = notificationPreview(first);
      const openLabel = `Open ${notificationLabel(first)}: ${first.text || first.title || "New update"}`;
      host.setAttribute("aria-label", "Assistant GM phone notification");
      host.innerHTML = `<img class="assistant-phone-art" src="/assets/game-art/assistant-gm-phone.png" alt="" aria-hidden="true"><div class="assistant-phone-screen"><div class="assistant-phone-status"><span>MESSAGES</span><span aria-hidden="true">▰</span></div><div class="assistant-phone-contact"><span class="assistant-contact-icon" aria-hidden="true">AG</span><strong>Assistant GM</strong><button type="button" class="assistant-phone-close" aria-label="Dismiss Assistant GM text" title="Dismiss text">×</button></div><span class="assistant-text-date">${escape(first.date || "Today")}</span><button type="button" class="assistant-text-message" aria-label="${escape(openLabel)}"><span role="status" aria-live="polite">${escape(preview)}</span></button><div class="assistant-phone-home" aria-hidden="true"></div></div>`;
      host.querySelector(".assistant-phone-close").addEventListener("click", () => finishNotificationBatch());
      host.querySelector(".assistant-text-message").addEventListener("click", () => finishNotificationBatch(first));
      return;
    }
    const wasExpanded = Boolean(host.querySelector(".assistant-phone-screen")?.classList.contains("has-expanded-notifications"));
    const stacked = notices.slice(0, 3).map((notice, index) => `<span class="assistant-notification-stack-card assistant-notification-stack-card-${index + 1}" aria-hidden="true">${escape(notificationPreview(notice))}</span>`).join("");
    const rows = notices.map((notice, index) => `<button type="button" class="assistant-notification-item" data-notification-index="${index}" aria-label="Open ${escape(notificationLabel(notice))}: ${escape(notice.text || notice.title || "New update")}"><strong>${escape(notice.title || notificationLabel(notice))}</strong><small>${escape(notice.date || "Today")}</small><span>${escape(notificationPreview(notice))}</span></button>`).join("");
    host.setAttribute("aria-label", `${count} Assistant GM notifications`);
    host.innerHTML = `<img class="assistant-phone-art" src="/assets/game-art/assistant-gm-phone.png" alt="" aria-hidden="true"><div class="assistant-phone-screen is-notification-batch${wasExpanded ? " has-expanded-notifications" : ""}"><div class="assistant-phone-status"><span>MESSAGES</span><span class="assistant-notification-count" aria-label="${count} notifications">${count}</span></div><div class="assistant-phone-contact"><span class="assistant-contact-icon" aria-hidden="true">AG</span><strong>Assistant GM</strong><button type="button" class="assistant-phone-close" aria-label="Dismiss all notifications" title="Dismiss all notifications">×</button></div><span class="assistant-text-date">${escape(first.date || "Today")}</span><button type="button" class="assistant-notification-stack" aria-expanded="${wasExpanded ? "true" : "false"}" aria-label="Expand ${count} notifications">${stacked}<span class="assistant-notification-stack-label">${count} new ${count === 1 ? "message" : "messages"}<strong>${escape(first.title || notificationLabel(first))}</strong><small>Tap to view all</small></span></button><div class="assistant-notification-list" aria-label="Assistant GM messages">${rows}</div><div class="assistant-phone-home" aria-hidden="true"></div></div>`;
    host.querySelector(".assistant-phone-close").addEventListener("click", () => finishNotificationBatch());
    host.querySelector(".assistant-notification-stack").addEventListener("click", event => {
      event.currentTarget.setAttribute("aria-expanded", "true");
      host?.querySelector(".assistant-phone-screen")?.classList.add("has-expanded-notifications");
    });
    for (const button of host.querySelectorAll(".assistant-notification-item")) {
      const notice = notices[Number(button.dataset.notificationIndex)];
      button.addEventListener("click", () => finishNotificationBatch(notice));
    }
  }
  function showNext() {
    if (simulationPlaybackActive || (draftPlaybackActive && current?.kind !== "draft_trade_batch") || (!enabled && current?.kind !== "draft_trade_batch") || advanceTimer) return;
    if (host) { renderNotificationBatch(); return; }
    if (!current) current = queued.shift() || null;
    if (!current) return;
    host = document.createElement("aside");
    host.className = "assistant-gm-phone";
    if (current.kind === "draft_trade_batch") {
      const notices = current.notices || [];
      const first = notices[0] || {};
      const count = notices.length;
      const stacked = notices.slice(0, 3).map((notice, index) => `<span class="assistant-notification-stack-card assistant-notification-stack-card-${index + 1}" aria-hidden="true">${escape(notice.headline || "Draft-night trade")}</span>`).join("");
      const rows = notices.map((notice, index) => {
        const post = notice.social_post || {};
        return `<button type="button" class="assistant-notification-item" data-notification-index="${index}" aria-label="Open League Wire post: ${escape(notice.headline || post.text || "Draft trade")}"><strong>${escape(notice.headline || "Draft-night trade")}</strong><small>${escape(post.author || "League reporter")} ${post.handle ? `· ${escape(post.handle)}` : ""}</small><span>${escape(post.text || notice.headline || "Draft-night trade reported around the league.")}</span></button>`;
      }).join("");
      host.setAttribute("aria-label", `${count} draft trade notifications from League Wire`);
      host.innerHTML = `<img class="assistant-phone-art" src="/assets/game-art/assistant-gm-phone.png" alt="" aria-hidden="true"><div class="assistant-phone-screen is-draft-trade-batch"><div class="assistant-phone-status"><span>DRAFT NIGHT · MESSAGES</span><span class="assistant-notification-count" aria-label="${count} notifications">${count}</span></div><div class="assistant-phone-contact"><span class="assistant-contact-icon" aria-hidden="true">LW</span><strong>League Wire</strong><button type="button" class="assistant-phone-close" aria-label="Close draft notifications" title="Close notifications">×</button></div><span class="assistant-text-date">${escape(first.date || "Draft night")}</span><button type="button" class="assistant-notification-stack" aria-expanded="false" aria-label="Expand ${count} draft trade notifications">${stacked}<span class="assistant-notification-stack-label">${count} new ${count === 1 ? "message" : "messages"}<strong>${escape(first.headline || "Draft-night trade")}</strong><small>Tap to view all</small></span></button><div class="assistant-notification-list" aria-label="Draft trade messages">${rows}</div><div class="assistant-phone-home" aria-hidden="true"></div></div>`;
      host.querySelector(".assistant-phone-close").addEventListener("click", () => finishDraftTradeBatch());
      host.querySelector(".assistant-notification-stack").addEventListener("click", (event) => {
        event.currentTarget.setAttribute("aria-expanded", "true");
        host?.querySelector(".assistant-phone-screen")?.classList.add("has-expanded-draft-messages");
        clearTimeout(autoTimer);
        autoTimer = setTimeout(() => finishDraftTradeBatch(), 5000);
      });
      for (const button of host.querySelectorAll(".assistant-notification-item")) {
        const notice = notices[Number(button.dataset.notificationIndex)];
        button.addEventListener("click", () => finishDraftTradeBatch(notice));
      }
      autoTimer = setTimeout(() => finishDraftTradeBatch(), 2500);
      document.body.append(host);
      updateTuck();
      return;
    }
    renderNotificationBatch();
    document.body.append(host);
    updateTuck();
  }
  function finishDraftTradeBatch(openNotice) {
    const batch = current;
    if (!batch || batch.kind !== "draft_trade_batch") return;
    clearTimeout(autoTimer); autoTimer = null;
    current = null;
    const closing = host; host = null; leavingHost = closing;
    closing?.classList.add("is-leaving");
    let opening = Promise.resolve();
    if (openNotice && onOpen) opening = Promise.resolve().then(() => onOpen(openNotice)).catch(() => {});
    advanceTimer = setTimeout(async () => {
      closing?.remove(); leavingHost = null; advanceTimer = null;
      await opening;
      batch.onDismiss?.();
      showNext();
    }, 450);
  }
  function finishNotificationBatch(openNotice) {
    const batch = notificationMessages();
    if (!batch.length) return;
    clearTimeout(autoTimer); autoTimer = null;
    const selected = openNotice ? batch.find(message => message.id === openNotice.id) : null;
    for (const message of batch) seen.add(message.id);
    persist();
    current = null;
    queued = [];
    const closing = host; host = null; leavingHost = closing;
    closing?.classList.add("is-leaving");
    let opening = Promise.resolve();
    if (selected && onOpen) opening = Promise.resolve().then(() => onOpen(selected)).catch(() => {
      seen.delete(selected.id); persist(); queued.unshift(selected);
    });
    advanceTimer = setTimeout(async () => {
      closing?.remove(); leavingHost = null; advanceTimer = null;
      await opening;
      showNext();
    }, 450);
  }
  function sync(options) {
    const nextKey = String(options.saveKey || "");
    if (nextKey !== saveKey) {
      initialized = false; hide(); clearTimeout(advanceTimer); advanceTimer = null;
      saveKey = nextKey; current = null; queued = [];
      try { seen = new Set(JSON.parse(localStorage.getItem(storageKey()) || "[]")); } catch { seen = new Set(); }
    }
    enabled = Boolean(options.enabled); onOpen = options.onOpen;
    if (!enabled) { hide(); return; }
    const messages = options.messages || [];
    const deadlineIds = new Set(messages.filter(m => m.kind === "trade_deadline").map(m => m.id));
    queued = queued.filter(m => m.kind !== "trade_deadline" || deadlineIds.has(m.id));
    if (current?.kind === "trade_deadline" && !deadlineIds.has(current.id)) { current = null; hide(); }
    const known = new Set([current?.id, ...queued.map(m => m.id)]);
    let incoming = messages.filter(m => !seen.has(m.id) && !known.has(m.id));
    if (!initialized) {
      initialized = true;
      // Show all currently unseen alerts together so the player can choose which to open.
      persist();
    }
    const urgent = incoming.find(m => m.kind === "trade_deadline");
    if (urgent) {
      if (current) queued.unshift(current);
      current = urgent;
      hide();
      queued.push(...incoming.filter(m => m.id !== urgent.id));
    } else {
      queued.push(...incoming);
    }
    showNext();
  }
  function presentDraftTrades(messages = []) {
    const notices = (Array.isArray(messages) ? messages : [messages]).map(message => {
      const post = message.social_post || {};
      return {...message, target:"league-wire", event_id:post.id || message.event_id, text:post.text || message.headline || "Draft-night trade completed."};
    });
    if (!notices.length) return Promise.resolve();
    return new Promise(resolve => {
      clearTimeout(autoTimer); autoTimer = null;
      clearTimeout(advanceTimer); advanceTimer = null;
      if (current && current.kind !== "draft_trade_batch") queued.unshift(current);
      host?.remove(); leavingHost?.remove(); host = null; leavingHost = null;
      current = {kind:"draft_trade_batch", notices, onDismiss:resolve};
      showNext();
    });
  }
  function presentDraftTrade(message = {}) { return presentDraftTrades([message]); }
  function setDraftPlaybackActive(active) {
    draftPlaybackActive = Boolean(active);
    if (draftPlaybackActive && current?.kind !== "draft_trade_batch") {
      if (current) queued.unshift(current);
      current = null;
      clearTimeout(autoTimer); autoTimer = null;
      clearTimeout(advanceTimer); advanceTimer = null;
      host?.remove(); leavingHost?.remove(); host = null; leavingHost = null;
    } else if (!draftPlaybackActive) showNext();
  }
  function setSimulationPlaybackActive(active) {
    simulationPlaybackActive = Boolean(active);
    if (simulationPlaybackActive) {
      clearTimeout(autoTimer); autoTimer = null;
      clearTimeout(advanceTimer); advanceTimer = null;
      host?.remove(); leavingHost?.remove(); host = null; leavingHost = null;
    } else showNext();
  }
  function presentSimulationTradeOffer(message = {}) {
    if (!simulationPlaybackActive) return Promise.resolve();
    const team = String(message.teamAbbrev || message.team_abbrev || "an NBA team");
    const date = String(message.date || "Today");
    const notice = `You got an offer from ${team}.`;
    const transient = document.createElement("aside");
    transient.className = "assistant-gm-phone is-simulation-offer";
    transient.setAttribute("aria-label", `Incoming trade offer from ${team}`);
    transient.innerHTML = `<img class="assistant-phone-art" src="/assets/game-art/assistant-gm-phone.png" alt="" aria-hidden="true"><div class="assistant-phone-screen is-simulation-trade-offer"><div class="assistant-phone-status"><span>MESSAGES</span><span aria-hidden="true">▰</span></div><div class="assistant-phone-contact"><span class="assistant-contact-icon" aria-hidden="true">AG</span><strong>Assistant GM</strong></div><span class="assistant-text-date">${escape(date)}</span><div class="assistant-simulation-offer-message" role="status" aria-live="polite">${escape(notice)}</div><div class="assistant-phone-home" aria-hidden="true"></div></div>`;
    document.body.append(transient);
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const wait = duration => new Promise(resolve => setTimeout(resolve,duration));
    return wait(reducedMotion ? 620 : 650).then(() => wait(760)).then(() => {
      transient.classList.add("is-leaving");
      return wait(reducedMotion ? 0 : 410);
    }).then(() => transient.remove());
  }
  // The phone tucks smaller into the corner while it would cover an open window (the free-agency room, a player
  // card, ...); hovering or focusing it brings it back to full size. Overlap is measured on the phone's untucked
  // footprint (layout box, not the scaled one), so tucking never flips it back.
  function coversOpenWindow(phone) {
    if (!phone?.isConnected || !phone.offsetWidth) return false;
    const left = phone.offsetLeft, top = phone.offsetTop, right = left + phone.offsetWidth, bottom = top + phone.offsetHeight;
    return [...document.querySelectorAll(".card-board-window")].some(frame => {
      if (frame.hidden || frame.classList.contains("is-minimized")) return false;
      const box = frame.getBoundingClientRect();
      return box.width > 0 && box.height > 0 && box.right > left + 12 && box.left < right && box.bottom > top + 12 && box.top < bottom;
    });
  }
  function updateTuck() {
    if (!host?.isConnected) return;
    host.classList.toggle("is-tucked", coversOpenWindow(host));
  }
  if (typeof setInterval === "function") setInterval(updateTuck, 500);
  window.addEventListener?.("resize", updateTuck);
  // Escape dismisses a showing Assistant GM text before anything else handles the key (otherwise it closed the
  // active dashboard window behind the phone). Open dialogs keep Escape for themselves.
  window.addEventListener?.("keydown", event => {
    if (event.key !== "Escape" || event.defaultPrevented || event.isComposing) return;
    const close = host?.isConnected ? host.querySelector(".assistant-phone-close") : null;
    const openDialog = [...document.querySelectorAll('[role="dialog"][aria-modal="true"]')].some(dialog => dialog.getClientRects().length > 0);
    if (!close || openDialog) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    close.click();
  }, true);
  window.AssistantGMPhone = Object.freeze({sync, hide, presentDraftTrade, presentDraftTrades, setDraftPlaybackActive, setSimulationPlaybackActive, presentSimulationTradeOffer});
})();
