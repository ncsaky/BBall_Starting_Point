(() => {
  const screen = document.getElementById("startupScreen");
  if (!screen) return;
  const panes = [...screen.querySelectorAll("[data-startup-pane]")];
  let active = null;

  function open(pane) {
    if (active === pane) return;
    for (const item of panes) {
      const expanded = item === pane;
      item.classList.toggle("is-expanded", expanded);
      item.querySelector(".startup-pane-preview").setAttribute("aria-expanded", String(expanded));
      const content = item.querySelector(".startup-pane-content");
      content.hidden = !expanded;
      content.inert = !expanded;
    }
    active = pane;
    pane?.querySelector('[aria-checked="true"]')?.scrollIntoView({behavior: "auto", block: "nearest", inline: "center"});
    window.StartupVideoBackdrop?.setContext(pane?.dataset.startupPane === "new");
  }

  for (const pane of panes) {
    pane.querySelector(".startup-pane-preview").addEventListener("click", () => open(active === pane ? null : pane));
  }
  screen.addEventListener("keydown", event => {
    if (event.key !== "Escape" || !active) return;
    const previous = active;
    open(null);
    previous.querySelector(".startup-pane-preview").focus({preventScroll: true});
    event.preventDefault();
  });
  // Forms stay open through pointer movement, focus changes and outside clicks.
  new MutationObserver(() => { if (screen.hidden) open(null); }).observe(screen, {attributes: true, attributeFilter: ["hidden"]});
})();
