/* UI polish pass (2026-11-21): presentation helpers that never change what a number means.
   Playoff bracket fit: the bracket is laid out at a fixed readable size (about 1400 x 460 px). When its window is
   narrower or shorter than that, the whole bracket is scaled down as one picture instead of being cut off at the
   window's edge (at 1024 px wide the East half used to be missing). The scale is stored on the window frame, so a
   freshly redrawn bracket picks it up before the next paint, and team-logo flights (which use screen positions)
   still land on the right rows. */
(() => {
  "use strict";

  let queued = false;
  const observed = new WeakSet();
  const resize = typeof ResizeObserver === "function" ? new ResizeObserver(() => schedule()) : null;

  function fitBracket(shell) {
    const bracket = shell.querySelector(".tournament-bracket");
    if (!bracket || !shell.isConnected || !shell.getClientRects().length) return;
    const style = getComputedStyle(shell);
    const availableWidth = shell.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    const availableHeight = shell.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    const naturalWidth = bracket.offsetWidth, naturalHeight = bracket.offsetHeight;
    if (!naturalWidth || !naturalHeight || availableWidth <= 0 || availableHeight <= 0) return;
    const fit = Math.min(1, availableWidth / naturalWidth, availableHeight / naturalHeight);
    const offset = Math.max(0, (availableWidth - naturalWidth * fit) / 2);
    const host = shell.closest("[data-board-window]") || shell;
    const value = fit.toFixed(4), shift = `${offset.toFixed(1)}px`;
    if (host.style.getPropertyValue("--bracket-fit") !== value) host.style.setProperty("--bracket-fit", value);
    if (host.style.getPropertyValue("--bracket-shift") !== shift) host.style.setProperty("--bracket-shift", shift);
    shell.classList.add("is-bracket-fitted");
  }

  function run() {
    queued = false;
    for (const shell of document.querySelectorAll(".phase-bracket-shell")) {
      if (resize && !observed.has(shell)) { observed.add(shell); resize.observe(shell); }
      fitBracket(shell);
    }
  }

  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(run);
  }

  function start() {
    schedule();
    // Only cheap work here: any added node schedules one fit pass for the next frame.
    new MutationObserver((records) => {
      if (records.some((record) => record.addedNodes.length)) schedule();
    }).observe(document.body, {childList: true, subtree: true});
    window.addEventListener("resize", schedule);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, {once: true});
  else start();

  window.UiPolish = Object.freeze({fitBrackets: run});
})();
