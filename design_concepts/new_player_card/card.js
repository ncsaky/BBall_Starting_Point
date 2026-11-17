"use strict";
// Mockup renderer. All numbers come from data.json (built by scripts/build_card_mockup_data.py).
const GROUPS = [
  ["Shooting", "S01-S09"], ["Finishing", "S10-S15"], ["Creation & handle", "S16-S20, S24"], ["Post", "S21-S23"],
  ["Off-ball & screens", "S25-S28"], ["Rebounding", "S29-S32"], ["Defense", "S33-S46"],
];
const DIST_IDS = ["T01", "T02", "T03", "T11", "T13", "T16", "T17"];
const SEG = ["--seg1", "--seg2", "--seg3", "--seg4", "--seg5"];
const TIER = { core_rotation: "Core rotation", rotation: "Rotation player", deep_rotation: "Deep rotation", fringe: "Fringe roster spot", development_priority: "Development player" };
const DEF_SCALE = 105; // display ratings have headroom above 100, so bars are never clipped

let DATA, byId = {}, current = 0;

const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pretty = k => k.replace(/_/g, " ").replace(/^./, c => c.toUpperCase());
const ftIn = inches => `${Math.floor(inches / 12)}'${Math.round(inches % 12)}"`;
const pctTxt = v => `${Math.round(v * 100)}%`;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const evText = r => r.evidence === "player" ? "Based on this player's stats" : "Estimate from similar players";

function track(fillPct, prior, avgPct, band) {
  const b = band ? `<i class="band" style="left:${clamp(band[0], 0, 100)}%;width:${Math.max(0.5, clamp(band[1], 0, 100) - clamp(band[0], 0, 100))}%"></i>` : "";
  const a = avgPct == null ? "" : `<i class="avg" style="left:${clamp(avgPct, 0, 100)}%"></i>`;
  return `<div class="track">${b}<i class="fill${prior ? " prior" : ""}" style="width:${clamp(fillPct, 0, 100)}%"></i>${a}</div>`;
}

function tip(def, r, valueText) {
  const range = r.interval ? ` | likely range ${fmtRange(def, r.interval)}` : "";
  const pc = r.pct != null ? ` | league percentile ${Math.round(r.pct)}` : "";
  return esc(`${def.id} · ${def.name} · ${valueText}${range}${pc} | ${evText(r)}`);
}
function fmtRange(def, [lo, hi]) { return def.kind === "propensity" ? `${pctTxt(lo)}-${pctTxt(hi)}` : `${Math.round(lo)}-${Math.round(hi)}`; }

function gradeRow(def, r, label) {
  const prior = r.evidence === "prior";
  const band = r.interval;
  return `<div class="r" title="${tip(def, r, Math.round(r.value))}"><span class="l">${esc(label || def.name)}</span>${track(r.value, prior, r.pos_avg, band)}<strong>${Math.round(r.value)}</strong></div>`;
}

function passingRows(P) {
  let html = `<div class="pass-head"><span></span><b>Read</b><span></span><b>Delivery</b><span></span></div>`;
  for (let n = 1; n <= 9; n++) {
    const f = "F0" + n, rd = byId[f + ".recognition"], ex = byId[f + ".execution"];
    const dr = P.map[f + ".recognition"], de = P.map[f + ".execution"];
    const name = rd.name.replace(/ — recognition$/, "");
    const cell = (d, r, kind) => `${track(r.value, r.evidence === "prior", r.pos_avg, r.interval)}<strong title="${tip(d, r, Math.round(r.value))}">${Math.round(r.value)}</strong>`;
    html += `<div class="r pass" title="${esc(f + " · " + name)}"><span class="l">${esc(name)}</span>${cell(rd, dr)}${cell(ex, de)}</div>`;
  }
  return html;
}

function measureText(id, r, p) {
  const cm = r.value, inch = cm / 2.54;
  if (id === "P04") return `${Math.round(p.weight_lbs)} lb <small>${Math.round(cm)} kg</small>`;
  if (id === "P10") return `${Math.round(inch)} in <small>${Math.round(cm)} cm</small>`;
  return `${ftIn(inch)} <small>${Math.round(cm)} cm</small>`;
}
function measureRow(def, r, p) {
  const prior = r.evidence === "prior";
  const t = measureText(def.id, r, p);
  return `<div class="r measure" title="${tip(def, r, r.value.toFixed(1) + " " + (r.unit || ""))}"><span class="l">${esc(def.name)}</span>${track(r.pct, prior, r.pos_avg_pct, r.interval_pct)}<strong>${t}</strong></div>`;
}

function propRow(def, r) {
  return `<div class="r" title="${tip(def, r, pctTxt(r.value))}"><span class="l">${esc(def.name)}</span>${track(r.value * 100, r.evidence === "prior", r.pos_avg * 100, r.interval ? r.interval.map(x => x * 100) : null)}<strong>${pctTxt(r.value)}</strong></div>`;
}

function distRow(def, r) {
  const keys = (def.outcomes && def.outcomes.length ? def.outcomes : Object.keys(r.value));
  const ord = keys.filter(k => k in r.value);
  const segs = ord.map((k, i) => `<i style="width:${r.value[k] * 100}%;background:var(${SEG[i % 5]})" title="${esc(pretty(k) + " " + pctTxt(r.value[k]) + (r.intervals && r.intervals[k] ? " (range " + pctTxt(r.intervals[k][0]) + "-" + pctTxt(r.intervals[k][1]) + ")" : "") + ", position average " + pctTxt(r.pos_avg[k]))}"></i>`).join("");
  const leg = ord.map((k, i) => `<span><em style="background:var(${SEG[i % 5]})"></em>${esc(pretty(k))} <b>${pctTxt(r.value[k])}</b></span>`).join("");
  const tt = esc(`${def.id} · ${def.name} | ${evText(r)}`);
  return `<div class="dist" title="${tt}"><div class="t">${esc(def.name)}<span class="badge">${r.evidence === "prior" ? "similar players" : "player stats"}</span></div><div class="stack-bar${r.evidence === "prior" ? " prior" : ""}">${segs}</div><div class="dleg">${leg}</div></div>`;
}

function layerHeader(title, sub, ids, P) {
  if (!ids) return `<header><h2>${esc(title)}</h2><span class="count">Not player talent</span><span class="sub">${esc(sub)}</span></header>`;
  const n = ids.length, k = ids.filter(i => P.map[i].evidence === "player").length;
  return `<header><h2>${esc(title)}</h2><span class="count">${k} of ${n} from player data</span><span class="sub">${esc(sub)}</span></header>`;
}

function render() {
  const p = DATA.players[current];
  p.map = Object.fromEntries(p.inputs.map(r => [r.id, r]));
  const P = p;
  const allIds = DATA.inputs.map(d => d.id);
  const l1 = allIds.filter(i => byId[i].layer === 1), l2 = allIds.filter(i => byId[i].layer === 2), l3 = allIds.filter(i => byId[i].layer === 3);

  const pv = p.provisional;
  const big = (lab, v, cls) => `<div class="row ${cls || ""}"><b>${lab}</b><div class="track" style="height:9px"><i class="fill" style="width:${clamp(v / DEF_SCALE * 100, 0, 100)}%"></i></div><strong>${v.toFixed(0)}</strong></div>`;
  const ring = (lab, sub) => `<div class="ring" title="Unchanged from the current card"><span><svg viewBox="0 0 44 44"><circle cx="22" cy="22" r="18"></circle></svg><strong>--</strong></span><div><b>${lab}</b><small>${sub}</small></div></div>`;
  const initials = p.name.split(" ").map(s => s[0]).join("");
  const head = `<section class="profile-head">
    <div class="who"><div class="headshot headshot-fallback" id="hs">${initials}</div><div><h3>${esc(p.name)}</h3><p>${p.position} · ${Math.round(p.age)} years · ${ftIn(p.height_inches)} · ${p.team}</p></div></div>
    <div class="ovr-bars">${big("OVR", pv.ovr, "big")}${big("OFF", pv.off)}${big("DEF", pv.def)}<div class="prov-note">Provisional: computed from the inputs below, scaled against all ${DATA.league.players} players with no cap at 100.</div></div>
    <div class="badges">${ring("Health risk", "as current card")}${ring("Upside", "as current card")}${ring("Trade Value", "as current card")}</div>
  </section>
  <div class="legend">
    <span><i class="sw solid"></i>Based on this player's stats</span>
    <span><i class="sw hatch"></i>Estimate from similar players</span>
    <span><i class="sw band"></i>Likely range</span>
    <span><i class="sw tick"></i>Average at his position (${esc(p.position)})</span>
    <span style="margin-left:auto">Grades: 50 is a functional NBA level, 75 strong, 90 exceptional. Hover any row for details.</span>
  </div>`;

  // Layer 1
  const groupHtml = ([name, range]) => {
    const defs = DATA.inputs.filter(d => d.group === name);
    return `<h4>${name}<small>${defs.length}</small></h4>` + defs.map(d => gradeRow(d, p.map[d.id])).join("");
  };
  const g = Object.fromEntries(GROUPS.map(x => [x[0], groupHtml(x)]));
  const layer1 = `<section class="layer">${layerHeader("1 · Technique & Recognition", "What the player can do, separate from size and speed.", l1, P)}
    <div class="body"><div class="cols"><div>${g["Shooting"]}${g["Finishing"]}${g["Creation & handle"]}${g["Post"]}${g["Off-ball & screens"]}</div>
    <div>${g["Defense"]}${g["Rebounding"]}<h4>Passing<small>9 types, read and delivery</small></h4>${passingRows(P)}</div></div></div></section>`;

  // Layer 2
  const layer2 = `<section class="layer">${layerHeader("2 · Physical Tools", "Body and athleticism. Measurements are shown where known.", l2, P)}
    <div class="body">${l2.map(i => {
      const r = p.map[i], d = byId[i];
      return r.kind === "measure" ? measureRow(d, r, p) : gradeRow(d, r);
    }).join("")}<p class="coach note" style="color:#495968;font-size:9px;margin:6px 0 0">Measured rows are drawn against the league spread (bar = percentile). Grade rows use the 0-100 scale.</p></div></section>`;

  // Layer 3
  const props = l3.filter(i => !DIST_IDS.includes(i)), dists = DIST_IDS;
  const layer3 = `<section class="layer">${layerHeader("3 · Tendencies", "What the player chooses to do, not how well.", l3, P)}
    <div class="body"><h4>Choices and style<small>how often</small></h4>${props.map(i => propRow(byId[i], p.map[i])).join("")}
    <h4>Mixes<small>each bar adds to 100%</small></h4>${dists.map(i => distRow(byId[i], p.map[i])).join("")}</div></section>`;

  // Layer 4
  const mpg = p.minutes_projection;
  const layer4 = `<section class="layer coach">${layerHeader("4 · Coach Usage & Deployment", "Decided by the coach, not player talent. Changes with team, lineup and game.", null, P)}
    <div class="body">
      <div class="kv"><span>Position</span><strong>${p.position}</strong></div>
      <div class="kv"><span>Offensive role</span><strong><span class="tag">${esc(p.primary_off_role || "None")}</span>${p.secondary_off_role ? `<span class="tag">${esc(p.secondary_off_role)}</span>` : ""}</strong></div>
      <div class="kv"><span>Defensive role</span><strong><span class="tag">${esc(p.primary_def_role === "Hidden" ? "Not yet revealed" : p.primary_def_role || "None")}</span></strong></div>
      <div class="kv"><span>Projected minutes</span><div class="minbar"><div class="track" style="height:8px"><i class="fill" style="width:${clamp(mpg / 40 * 100, 0, 100)}%"></i></div><strong>${mpg.toFixed(1)} per game</strong></div></div>
      <div class="kv"><span>Usage share</span><strong class="ph">Placeholder: set by the coach once lineups exist</strong></div>
      <div class="kv"><span>Rotation spot</span><strong>${TIER[p.rotation_priority] || p.rotation_priority}</strong></div>
      <p class="note">The user sets rough minutes for their own team; the coach adjusts game by game (foul trouble, fatigue, hot hands, blowouts, matchups).</p>
    </div></section>`;

  document.getElementById("card").innerHTML = head + `<div class="layers">${layer1}<div class="stack">${layer2}${layer4}</div>${layer3}</div>`;

  if (p.headshot_url) {
    const img = new Image();
    img.className = "headshot"; img.alt = p.name;
    img.onload = () => { const hs = document.getElementById("hs"); if (hs) hs.replaceWith(img); };
    img.src = p.headshot_url;
  }
  document.querySelectorAll("#switcher button").forEach((b, i) => b.classList.toggle("on", i === current));
}

fetch("data.json").then(r => r.json()).then(d => {
  DATA = d;
  byId = Object.fromEntries(d.inputs.map(i => [i.id, i]));
  const sw = document.getElementById("switcher");
  d.players.forEach((p, i) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "ui-command"; b.textContent = p.name;
    b.addEventListener("click", () => { current = i; render(); });
    sw.appendChild(b);
  });
  render();
}).catch(e => { document.getElementById("card").textContent = "Could not load data.json: " + e; });
