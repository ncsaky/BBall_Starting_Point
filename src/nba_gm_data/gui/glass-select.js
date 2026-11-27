// Glass drop-down menus (taste deck round 6: "please make the drop-down menus better").
// Every single-choice <select> inside a window, pop-up, slide or the start screen gets a glass button and a glass menu. The real
// <select> stays in the page (visually hidden) and keeps its value; choosing from the menu sets that value and fires
// the same change and input events, so the game's own handlers work unchanged. Long menus open in columns rather
// than scrolling (the user never wants to scroll).
(() => {
  "use strict";
  const SCOPE = "#modalRoot, .card-board-body, .card-board-menu, .season-slideshow, #startupScreen";
  const ROWS_PER_COLUMN = 12;
  let current = null;

  const optionLabel = (select) => {
    const option = select.selectedOptions?.[0] || select.options?.[0];
    return option ? option.textContent.trim() : "";
  };

  function sync(select) {
    const button = select.nextElementSibling;
    if (!button || !button.classList.contains("glass-select")) return;
    const text = optionLabel(select);
    const value = button.querySelector(".glass-select-value");
    if (value && value.textContent !== text) value.textContent = text;
    button.disabled = select.disabled;
  }

  function close(focusButton) {
    if (!current) return;
    const { list, button } = current;
    current = null;
    list.remove();
    button.setAttribute("aria-expanded", "false");
    if (focusButton && button.isConnected) button.focus();
  }

  function choose(select, value) {
    if (select.value !== value) {
      select.value = value;
      select.dispatchEvent(new Event("input", { bubbles: true }));
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    sync(select);
  }

  function itemsOf(select) {
    const items = [];
    for (const child of select.children) {
      if (child.tagName === "OPTGROUP") {
        items.push({ group: child.label });
        for (const option of child.children) items.push({ option });
      } else if (child.tagName === "OPTION") items.push({ option: child });
    }
    return items;
  }

  function open(select, button) {
    close(false);
    const items = itemsOf(select);
    const list = document.createElement("div");
    list.className = "glass-select-list";
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-label", select.getAttribute("aria-label") || optionLabel(select));
    const columns = Math.min(4, Math.max(1, Math.ceil(items.length / ROWS_PER_COLUMN)));
    list.style.setProperty("--columns", String(columns));
    list.style.setProperty("--rows", String(Math.ceil(items.length / columns)));
    for (const item of items) {
      if (item.group !== undefined) {
        const head = document.createElement("div");
        head.className = "glass-select-group";
        head.textContent = item.group;
        list.append(head);
        continue;
      }
      const { option } = item;
      const entry = document.createElement("button");
      entry.type = "button";
      entry.className = "glass-select-option";
      entry.setAttribute("role", "option");
      entry.setAttribute("aria-selected", String(option.selected));
      entry.disabled = option.disabled;
      entry.textContent = option.textContent.trim();
      entry.addEventListener("click", (event) => {
        event.stopPropagation();
        close(true);
        choose(select, option.value);
      });
      list.append(entry);
    }
    list.addEventListener("keydown", (event) => {
      const entries = [...list.querySelectorAll(".glass-select-option:not(:disabled)")];
      const at = entries.indexOf(document.activeElement);
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(true); }
      else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const next = entries[(at + (event.key === "ArrowDown" ? 1 : entries.length - 1)) % entries.length];
        next?.focus();
      } else if (event.key === "Tab") close(false);
    });
    document.body.append(list);
    // Place it under the button (or above when there is no room), inside the window.
    const box = button.getBoundingClientRect();
    const width = Math.max(box.width, list.offsetWidth);
    const height = list.offsetHeight;
    const left = Math.max(8, Math.min(box.left, innerWidth - width - 8));
    const below = box.bottom + 4 + height <= innerHeight - 8;
    list.style.left = `${left}px`;
    list.style.top = `${below ? box.bottom + 4 : Math.max(8, box.top - 4 - height)}px`;
    list.style.minWidth = `${box.width}px`;
    button.setAttribute("aria-expanded", "true");
    current = { list, button, select };
    (list.querySelector('[aria-selected="true"]') || list.querySelector(".glass-select-option:not(:disabled)"))?.focus();
  }

  function enhance(select) {
    if (select.dataset.glassSelect || select.multiple || Number(select.size) > 1) return;
    if (select.classList.contains("startup-team-select-native")) return;  // the team wheel is its control
    if (!select.closest(SCOPE)) return;
    select.dataset.glassSelect = "1";
    const width = select.offsetWidth;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "glass-select";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    const name = select.getAttribute("aria-label") || select.labels?.[0]?.textContent?.trim();
    if (name) button.setAttribute("aria-label", name);
    if (select.title) button.title = select.title;
    button.innerHTML = '<span class="glass-select-value"></span><i aria-hidden="true"></i>';
    if (width) button.style.minWidth = `${width}px`;
    select.classList.add("glass-select-native");
    select.tabIndex = -1;
    select.after(button);
    sync(select);
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      if (current?.select === select) close(true);
      else open(select, button);
    });
    button.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); open(select, button); }
    });
    select.addEventListener("change", () => sync(select));
  }

  function pass() {
    for (const select of document.querySelectorAll("select:not([data-glass-select])")) enhance(select);
    for (const select of document.querySelectorAll("select[data-glass-select]")) sync(select);
    if (current && !current.button.isConnected) close(false);
  }

  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    setTimeout(() => { queued = false; pass(); }, 0);
  };
  const start = () => {
    pass();
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled"] });
    document.addEventListener("pointerdown", (event) => {
      if (current && !current.list.contains(event.target) && event.target !== current.button && !current.button.contains(event.target)) close(false);
    }, true);
    addEventListener("resize", () => close(false));
    document.addEventListener("scroll", (event) => { if (current && !current.list.contains(event.target)) close(false); }, true);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();

// The standard tab picker's slide (user, 2026-11-24: the long pill is the tab picker everywhere). Tab groups are
// re-rendered when a tab is picked, so the blue pill can't simply move: on the click we remember where the chosen pill
// was, and once the group is drawn again with the new choice, a temporary pill slides from there to the new tab.
(() => {
  "use strict";
  const GROUP = '.tabs, .tr-tabs, .tr-filter, .tr-lower-tabs, .dev-views, .spatial-court-tabs, .settings-pill, [role="tablist"]';
  const ACTIVE = '.active, .is-active, [aria-pressed="true"], [aria-selected="true"]';
  const keyOf = (group) => [...group.children].map((child) => child.textContent.trim()).join("|");
  const activeOf = (group) => [...group.children].find((child) => child.matches(ACTIVE));
  let pending = null;

  function slide(group, target) {
    const box = group.getBoundingClientRect(), to = target.getBoundingClientRect();
    if (getComputedStyle(group).position === "static") group.style.position = "relative";
    const pill = document.createElement("i");
    pill.className = "tab-slide-pill";
    pill.setAttribute("aria-hidden", "true");
    pill.style.left = `${pending.x}px`;
    pill.style.width = `${pending.w}px`;
    group.classList.add("is-sliding");
    group.prepend(pill);
    void pill.offsetWidth;
    pill.style.left = `${to.left - box.left}px`;
    pill.style.width = `${to.width}px`;
    const done = () => { pill.remove(); group.classList.remove("is-sliding"); };
    pill.addEventListener("transitionend", done, { once: true });
    setTimeout(done, 400);
  }

  function look() {
    if (!pending) return;
    // The clicked group itself when it is still on the page (two pills can share labels, e.g. Off / On); otherwise the
    // re-drawn group with the same options.
    const group = pending.group?.isConnected ? pending.group : [...document.querySelectorAll(GROUP)].find((node) => node.offsetWidth && keyOf(node) === pending.key);
    const active = group && activeOf(group);
    if (group && active && active.textContent.trim() === pending.target) {
      slide(group, active);
      pending = null;
    } else if (Date.now() - pending.at < 2000) setTimeout(look, 40);
    else pending = null;
  }

  document.addEventListener("click", (event) => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const button = event.target.closest?.("button, [role='tab']");
    const group = button?.parentElement;
    if (!group || !group.matches(GROUP) || button.matches(ACTIVE)) return;
    const from = activeOf(group);
    if (!from) return;
    const box = group.getBoundingClientRect(), was = from.getBoundingClientRect();
    pending = { key: keyOf(group), group, x: was.left - box.left, w: was.width, target: button.textContent.trim(), at: Date.now() };
    setTimeout(look, 0);
  }, true);
})();

// Details drop-downs inside trade tiles (round 8: "I don't see the details popping up"): the tiles and panels clip their
// overflow, so an open drop-down is lifted out (fixed to the pop-up window) and placed under its summary.
(() => {
  "use strict";
  document.addEventListener("toggle", (event) => {
    const details = event.target;
    if (!(details instanceof HTMLDetailsElement) || !details.matches(".tr-tile-details")) return;
    const panel = details.querySelector(":scope > p");
    if (!panel) return;
    if (!details.open) { panel.classList.remove("is-floating"); panel.removeAttribute("style"); return; }
    document.querySelectorAll(".tr-tile-details[open]").forEach((other) => { if (other !== details) other.open = false; });
    const summary = details.querySelector("summary").getBoundingClientRect();
    const frame = details.closest(".modal-shell")?.getBoundingClientRect() || { left: 0, top: 0, right: innerWidth, bottom: innerHeight };
    panel.classList.add("is-floating");
    const width = panel.offsetWidth || 240, height = panel.offsetHeight || 120;
    const left = Math.max(frame.left + 8, Math.min(summary.right - width, frame.right - width - 8));
    const below = summary.bottom + 4 + height <= frame.bottom - 8;
    const top = below ? summary.bottom + 4 : summary.top - 4 - height;
    panel.style.left = `${left - frame.left}px`;
    panel.style.top = `${top - frame.top}px`;
    panel.style.right = "auto";
  }, true);
  document.addEventListener("pointerdown", (event) => {
    if (event.target.closest?.(".tr-tile-details")) return;
    document.querySelectorAll(".tr-tile-details[open]").forEach((details) => { details.open = false; });
  }, true);
})();
