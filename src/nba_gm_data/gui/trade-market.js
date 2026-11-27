// The trade room's Market view: one row a player, the teams circling him, and a way straight into an offer.
(function () {
  let filter = "all";
  const g = (name) => (typeof globalThis[name] === "function" ? globalThis[name] : null);
  const esc = (v) => (g("escapeHtml") ? g("escapeHtml")(String(v)) : String(v).replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])));
  const attr = (v) => (g("escapeAttr") ? g("escapeAttr")(String(v)) : esc(v));
  const has = (v) => v !== undefined && v !== null && String(v).trim() !== "";

  const isWar = (r) => r.stage === "bidding war";
  const isSold = (r) => r.stage === "sold";
  const isYours = (r) => !!(r.your_offer || r.you_interested);

  function sorted(rows) {
    const rank = (r) => (isSold(r) ? 2 : isWar(r) ? 0 : 1);
    return rows.map((r, i) => [r, i]).sort((a, b) => rank(a[0]) - rank(b[0]) || (Number(b[0].interested_count) || 0) - (Number(a[0].interested_count) || 0) || a[1] - b[1]).map((p) => p[0]);
  }

  function logo(team, cls) {
    const src = g("teamLogoSrc") ? g("teamLogoSrc")(team) : "";
    return src ? `<img class="${cls}" src="${attr(src)}" alt="" title="${attr(team)}" loading="lazy" />` : `<span class="tm-abbr-chip">${esc(team)}</span>`;
  }

  function dateText(iso) {
    if (!has(iso)) return "";
    const fn = g("formatDashboardShortDate");
    return fn ? String(fn(iso)) : String(iso);
  }

  function stageMarkup(r) {
    if (isSold(r)) return `<span class="tm-stage tm-sold"><i></i>${esc(has(r.sold_to) ? `Sold to ${r.sold_to}` : "Sold")}</span>`;
    if (isWar(r)) {
      const n = Number(r.rounds);
      return `<span class="tm-stage tm-war"><i></i>${esc(`Bidding war${n > 0 ? ` · ${n} round${n === 1 ? "" : "s"}` : ""}`)}</span>`;
    }
    return `<span class="tm-stage tm-open"><i></i>Taking offers</span>`;
  }

  function yoursMarkup(r) {
    let label = "", cls = "";
    if (r.your_offer === "leading") { label = "Your offer leads"; cls = "tm-lead"; }
    else if (r.your_offer === "outbid") { label = "You have been outbid"; cls = "tm-out"; }
    else if (r.you_interested) { label = "You asked"; cls = "tm-asked"; }
    if (!label) return "";
    const note = has(r.your_offer_note) ? `<span class="tm-note">${esc(r.your_offer_note)}</span>` : "";
    return `<span class="tm-yours ${cls}">${esc(label)}</span>${note}`;
  }

  function row(r, me) {
    const id = has(r.player_id) ? r.player_id : "";
    const name = has(r.player_name) ? r.player_name : "";
    const ovr = r.overall != null && r.overall !== "" && !Number.isNaN(Number(r.overall))
      ? `<b class="tm-ovr" style="color:${attr(g("tradeRatingColor") ? g("tradeRatingColor")(r.overall) : "inherit")}">${esc(Math.round(Number(r.overall)))}</b>` : "";
    const head = g("playerHeadshotMarkup") ? g("playerHeadshotMarkup")(r, "tm-headshot") : "";
    const meta = [has(r.team) ? `${logo(r.team, "tm-logo")}<span>${esc(r.team)}</span>` : "", has(r.age) ? `<span>Age ${esc(r.age)}</span>` : ""].filter(Boolean).join("");
    const why = Array.isArray(r.why) ? r.why.filter(has).join("; ") : "";
    const teams = Array.isArray(r.interested) ? r.interested.filter(has) : [];
    const count = Number(r.interested_count);
    const total = Number.isFinite(count) && count > 0 ? count : teams.length;
    const logos = teams.slice(0, 8).map((t) => logo(t, "tm-int-logo")).join("") + (total > 8 || teams.length > 8 ? `<span class="tm-more">+${esc(Math.max(total, teams.length) - 8)}</span>` : "");
    const interest = total > 0 ? `<span class="tm-int-count">${esc(total)} team${total === 1 ? "" : "s"}</span>` : "";
    const decide = !isSold(r) && has(r.decide_by) ? `<span class="tm-decide">Decide by ${esc(dateText(r.decide_by))}</span>` : "";
    const mine = has(me) && r.team === me;
    const action = !isSold(r) && !mine && has(r.team) && has(id) ? `<button type="button" class="tm-offer" data-market-build="${attr(r.team)}" data-market-player="${attr(id)}">Make an offer</button>` : "";
    const nameInner = `<span class="tm-headwrap">${head}</span><span class="tm-who"><span class="tm-name">${esc(name)}${ovr ? " " + ovr : ""}</span><span class="tm-meta">${meta}</span></span>`;
    const nameBtn = has(id) ? `<button type="button" class="tm-player" data-dashboard-player-card="${attr(id)}" aria-label="Open player card for ${attr(name)}">${nameInner}</button>` : `<span class="tm-player">${nameInner}</span>`;
    return `<li class="tm-row${isSold(r) ? " tm-row-sold" : ""}">${nameBtn}
      <span class="tm-why">${esc(why)}</span>
      <span class="tm-circle">${logos ? `<span class="tm-logos">${logos}</span>` : ""}${interest}</span>
      <span class="tm-state">${stageMarkup(r)}${decide}</span>
      <span class="tm-standing">${yoursMarkup(r)}</span>
      <span class="tm-act">${action}</span></li>`;
  }

  function markup(board, options) {
    const opts = options || {};
    const all = Array.isArray(board && board.shopped) ? board.shopped : [];
    const finals = Array.isArray(board && board.final_offers) ? board.final_offers : [];
    const me = g("userTeam") ? g("userTeam")() : "";
    const wars = all.filter(isWar).length, mineN = all.filter(isYours).length;
    if (filter === "wars" && !wars) filter = "all";
    if (filter === "yours" && !mineN) filter = "all";
    const shown = sorted(all.filter((r) => filter === "wars" ? isWar(r) : filter === "yours" ? isYours(r) : true));
    const pill = (key, label, n) => `<button type="button" class="tm-pill${filter === key ? " tm-on" : ""}" data-tm-filter="${key}" aria-pressed="${filter === key}">${label}<span>${n}</span></button>`;
    const pills = all.length ? `<div class="tm-pills">${pill("all", "All", all.length)}${wars ? pill("wars", "Bidding wars", wars) : ""}${mineN ? pill("yours", "You are in", mineN) : ""}</div>` : "";
    const list = all.length
      ? `<div class="tm-listhead"><span>Player</span><span>Why he is available</span><span>Interested teams</span><span>Stage</span><span>Your standing</span><span></span></div><ul class="tm-list">${shown.map((r) => row(r, me)).join("")}</ul>`
      : `<p class="tm-empty">No player is on the market right now.</p>`;
    const finalsMarkup = finals.length ? `<section class="tm-side-block"><h4>Final offers waiting for you</h4><ul class="tm-finals">${finals.map((f) => `<li><b>${esc(f.team || "")}</b>${has(f.text) ? `<span>${esc(f.text)}</span>` : ""}${has(f.why) ? `<span class="tm-note">${esc(f.why)}</span>` : ""}</li>`).join("")}</ul><button type="button" class="tm-review" data-open-trade-offers>Review offers</button></section>` : "";
    const fo = board && board.front_offices && opts.partner ? board.front_offices[opts.partner] : null;
    const read = fo && typeof opts.readMarkup === "function" ? opts.readMarkup(fo, "Your assistant GM's read") : "";
    const side = finalsMarkup || read ? `<aside class="tm-side">${finalsMarkup}${read ? `<section class="tm-side-block tm-read">${read}</section>` : ""}</aside>` : "";
    return `<div class="tm-page${side ? "" : " tm-wide"}${shown.some(isYours) ? "" : " tm-nostanding"}"><section class="tm-main"><header class="tm-head"><h3>Players on the market</h3><span class="tm-total">${all.length}</span>${pills}</header>${list}</section>${side}</div>`;
  }

  window.TradeMarketView = Object.freeze({markup});

  if (typeof document !== "undefined" && document.addEventListener) {
    document.addEventListener("click", (event) => {
      const b = event.target && event.target.closest ? event.target.closest("[data-tm-filter]") : null;
      if (!b) return;
      filter = b.dataset.tmFilter || "all";
      if (typeof globalThis.renderTradeRoom === "function") globalThis.renderTradeRoom();
    });
  }
})();
