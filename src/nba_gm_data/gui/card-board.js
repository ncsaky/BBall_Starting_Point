/* Window placement is a browser preference, never a basketball save mutation. */
(() => {
  "use strict";

  const TITLE_HEIGHT = 24;
  const STAFF_ACTION_WIDTH = 96;
  const STAFF_MARKET_HEIGHT = 300;
  const LIMIT = 20000;
  const CANVAS_SCALE = 1.3;
  const CANVAS_GUTTER = 12;
  const STARTER_CARDS = ["minutes", "week", "standings", "opponent", "signals"];
  const PHASE_STARTER_LIMIT = 4;
  const STARTER_CARD_MIN_WIDTHS = {minutes:450, week:720, standings:240, opponent:452, signals:198, efficiency:266};
  const CARD_SIZE_FACTORS = {
    identity: [1.32, 1.1],
    signals: [1, .75],
    minutes: [1.03 * .8 * 1.16, 1.22 * .7],
    development: [1.4, 1],
    efficiency: [1.36, 1.36],
    prospects: [1.92, 1.22],
    offense: [1.4, 1.55],
    defense: [1.4, 1.55],
    "award-mvp": [2.7, 1.22],
    "award-dpoy": [2.7, 1.22],
    "award-roty": [2.7, 1.22],
    roster: [1.16, 1],
    staff: [1.58, 1.12],
    "league-wire": [.61, 1.05],
  };
  const CARD_SIZE_REVISIONS = {identity:4,signals:2,minutes:6,development:3,staff:7,"league-wire":2,prospects:3,offense:4,defense:4,"award-mvp":3,"award-dpoy":3,"award-roty":3,roster:3};
  const CARD_WIDTH_MIGRATIONS = {minutes:{1:1.03/1.68*.8*.7*1.16,2:1.03/1.36*.8*.7*1.16,3:.8*.7*1.16,4:.7*1.16,5:1.16},development:{1:1.4/1.15,2:1.12},"league-wire":{1:.5},prospects:{1:1.92/1.2,2:1.92/1.45},offense:{1:1.1,2:1.1/1.4,3:1.4/1.1},defense:{1:1.1,2:1.1/1.4,3:1.4/1.1},"award-mvp":{1:2.7/1.22,2:2.7/2.05},"award-dpoy":{1:2.7/1.22,2:2.7/2.05},"award-roty":{1:2.7/1.22,2:2.7/2.05},roster:{1:1.16}};
  const CARD_HEIGHT_MIGRATIONS = {identity:{1:1.1/1.3,2:1.1,3:1.1/1.25},signals:{1:.75},minutes:{1:.7,2:.7,3:.7,4:.7},staff:{2:1.12/1.8,3:1.12/1.35,4:1.12/1.12,5:1.12/1.12,6:1.12/1.04},offense:{1:1.55},defense:{1:1.55}};
  const CARD_SCALE_MIGRATIONS = {staff:{4:1.25}};
  const CARD_MIN_SCALES = {
    identity: .72, signals: .78, morale: .78, factors: .78, offense: .72, defense: .72,
    standings: .8, week: .8, opponent: .8, minutes: .65, development: .84, efficiency: .78, prospects: .84,
    "award-mvp": .84, "award-dpoy": .84, "award-roty": .84, staff: .84, "league-wire": .72,
    roster: .88, stats: .84, contracts: .84, payroll: .8, picks: .8, "league-block": .84, "team-block": .9,
  };
  const EXPANDED_CARD_SIZES = {week:[960,560],prospects:[1000,650],"league-wire":[500,650]};
  const DEFAULT_EXPANDED_CARDS = new Set();
  const EXPANSION_FACTORS = {standings:[2,1.5],development:[1,1.35]};
  const EXPANDABLE_CARDS = new Set(["standings", "week", "prospects", "staff", "league-wire", "development", "picks"]);
  const PHASE_CARD_MIN_SCALES = {
    "phase-staff_retention-decision": .86,
    "phase-cutdown-decision": .86,
    "phase-playoffs-control": .9, "phase-playoffs-bracket": .74, "phase-playoffs-leaders": .78, "phase-playoffs-injuries": .78,
    "phase-draft-control": .9, "phase-draft-lottery": .8, "phase-draft-board": .84, "phase-draft-order": .82, "phase-draft-summary": .84, "phase-draft-trades": .82,
    "phase-free_agency-control": .9, "phase-free_agency-market": .82, "phase-free_agency-selected": .84, "phase-free_agency-offers": .84, "phase-free_agency-wire": .82, "phase-free_agency-payroll": .82, "phase-free_agency-cap": .82,
    "phase-fantasy_draft-control": .9, "phase-fantasy_draft-board": .82, "phase-fantasy_draft-roster": .84, "phase-fantasy_draft-ticker": .82,
  };
  const CARDS = [
    ["identity", ".season-identity-panel", "Team Identity"],
    ["signals", ".season-signal-card:nth-child(1)", "Team Signals"],
    ["morale", ".season-signal-card:nth-child(2)", "Morale"],
    ["factors", ".season-signal-card:nth-child(3)", "Four Factors"],
    ["offense", ".season-radar-card:nth-child(1)", "Offense"],
    ["defense", ".season-radar-card:nth-child(2)", "Defense"],
    ["standings", ".season-standings-panel", "Standings"],
    ["week", ".season-week-panel", "Calendar"],
    ["opponent", ".season-opponent-panel", "Next Opponent"],
    ["minutes", ".season-minutes-panel", "Minutes + Availability"],
    ["development", ".season-development-panel", "Player Development"],
    ["efficiency", ".season-efficiency-panel", "Weekly Efficiency"],
    ["prospects", ".season-prospects-panel", "Upcoming Prospects"],
    ["award-mvp", ".season-awards-grid > section:nth-child(1)", "MVP"],
    ["award-dpoy", ".season-awards-grid > section:nth-child(2)", "DPOY"],
    ["award-roty", ".season-awards-grid > section:nth-child(3)", "ROTY"],
    ["staff", ".season-staff-panel", "Coaching Staff"],
    ["league-wire", ".season-league-wire", "League Wire"],
  ];
  const ASSET_CARDS = [
    ["roster", ".assets-roster", "Roster"],
    ["stats", ".assets-stats", "Stats"],
    ["contracts", ".assets-contracts", "Contracts"],
    ["payroll", ".assets-payroll", "Four-Year Payroll Share"],
    ["picks", ".assets-picks", "Draft Assets"],
    ["league-block", ".assets-block", "League Block"],
    ["team-block", ".assets-team-block", "Team Block"],
    ["team-wants", ".assets-wants", "Team Wants"],
  ];
  const GALLERY_CATEGORIES = [
    ["required", "Required Decisions"],
    ["playoffs", "Playoffs"],
    ["draft", "Draft Room"],
    ["free-agency", "Free Agency"],
    ["fantasy-draft", "Fantasy Draft"],
    ["team", "Team & Identity"],
    ["season", "Season"],
    ["scouting", "Scouting & Awards"],
    ["front-office", "Front Office"],
    ["league", "League Activity"],
    ["other", "Other Cards"],
  ];
  const galleryCategoryFor = (id) => {
    if (id.startsWith("phase-staff_retention-") || id.startsWith("phase-cutdown-")) return "required";
    if (id.startsWith("phase-playoffs-")) return "playoffs";
    if (id.startsWith("phase-draft-")) return "draft";
    if (id.startsWith("phase-free_agency-")) return "free-agency";
    if (id.startsWith("phase-fantasy_draft-")) return "fantasy-draft";
    if (["identity", "signals", "morale", "factors", "offense", "defense"].includes(id)) return "team";
    if (["standings", "week", "opponent", "minutes", "development", "efficiency"].includes(id)) return "season";
    if (["prospects", "award-mvp", "award-dpoy", "award-roty"].includes(id)) return "scouting";
    if (["staff", "roster", "stats", "contracts", "payroll", "picks", "league-block", "team-block", "team-wants"].includes(id) || id.startsWith("trade-")) return "front-office";
    if (id === "league-wire") return "league";
    return "other";
  };
  const memory = new Map();
  const scrollPositions = new Map();
  let active = null;

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"']/g, (character) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;"})[character]);
  const bounded = (number, min, max) => Math.min(max, Math.max(min, number));
  const minimumScaleFor = (id) => id.startsWith("player-card-") ? .6 : CARD_MIN_SCALES[id] ?? PHASE_CARD_MIN_SCALES[id] ?? .72;
  const clipboardExtent = (viewportWidth, viewportHeight) => ({
    width: Math.max(1, Math.floor(viewportWidth * CANVAS_SCALE)),
    height: Math.max(1, Math.floor(viewportHeight * CANVAS_SCALE)),
  });
  function simulationMenuMarkup(postseason, disabled = "") {
    const labels = postseason ? ["One Game Per Series", "One Full Series", "Finish Playoffs"] : ["Next Event", "Next Week", "Next Month"];
    return ["next-event", "week", "month"].map((mode, i) => `<button type="button" role="menuitem" data-sim-menu-item="${mode}" data-advance="${mode}" ${disabled}>${labels[i]}</button>`).join("");
  }
  const switchableWindowOrder = (layout, ids) => ids.filter(id => layout[id]?.visible).sort((left, right) => (layout[right].z || 0) - (layout[left].z || 0));
  const frontmostVisibleWindow = (layout, ids, excludeId = null) => switchableWindowOrder(layout, ids.filter(id => id !== excludeId))[0] || null;
  const selectedWindowId = (layout, ids, activeId = null) => layout[activeId]?.visible ? activeId : frontmostVisibleWindow(layout, ids);
  const cycleWindowIndex = (index, count, direction = 1) => count ? (index + direction + count) % count : -1;
  const altWindowSwitcherDirection = event => {
    if (!event.altKey || event.ctrlKey || event.metaKey) return null;
    if (event.key === "Tab") return event.shiftKey ? -1 : 1;
    if (event.key === "`" || event.code === "Backquote") return -1;
    return null;
  };
  const constrainCardBounds = (item, canvasWidth, canvasHeight, gutter = CANVAS_GUTTER, titleHeight = TITLE_HEIGHT, visibleHeight = null) => {
    const maxScale = Math.max(.05, Math.min((canvasWidth - gutter * 2) / item.width, (canvasHeight - gutter * 2 - titleHeight) / item.height));
    const minScale = Math.min(item.minScale ?? .72, maxScale);
    item.scale = bounded(item.scale || 1, minScale, maxScale);
    const width = item.width * item.scale;
    const height = visibleHeight ?? titleHeight + item.height * item.scale;
    item.x = bounded(item.x, 0, Math.max(0, canvasWidth - gutter - width));
    item.y = bounded(item.y, 0, Math.max(0, canvasHeight - gutter - height));
    return item;
  };
  const snapCardPositions = (layout, cards, canvasWidth, canvasHeight, gutter = CANVAS_GUTTER, originX = 0, originY = 0) => {
    const placed = [];
    const positions = [];
    const uniqueSorted = values => [...new Set(values)].sort((a, b) => a - b);
    for (const {id, width, height} of cards) {
      if (!layout[id]?.visible) continue;
      const minX = originX + gutter, minY = originY + gutter;
      const maxX = originX + canvasWidth - gutter - width;
      const maxY = originY + canvasHeight - gutter - height;
      if (maxX < minX || maxY < minY) return false;
      const xs = uniqueSorted([minX, ...placed.map(card => card.x + card.width + gutter)]).filter(x => x <= maxX);
      const ys = uniqueSorted([minY, ...placed.map(card => card.y + card.height + gutter)]).filter(y => y <= maxY);
      let position = null;
      for (const y of ys) {
        for (const x of xs) {
          if (placed.some(card => x < card.x + card.width + gutter && card.x < x + width + gutter && y < card.y + card.height + gutter && card.y < y + height + gutter)) continue;
          position = {x, y};
          break;
        }
        if (position) break;
      }
      if (!position) return false;
      positions.push({id, ...position});
      placed.push({id, ...position, width, height});
    }
    for (const {id, x, y} of positions) Object.assign(layout[id], {x, y});
    return true;
  };
  function initializeStarterLayout(layout, saved, canvasWidth, canvasHeight, phaseCards = []) {
    if (saved?.version === 1 && saved.cards && typeof saved.cards === "object") return false;
    // Only initialize absent preferences; never repack an existing workspace.
    for (const [id] of CARDS) if (layout[id]) layout[id].visible = false;
    if (phaseCards.length) return true;
    const placed = [];
    for (const id of STARTER_CARDS) {
      const item = layout[id];
      if (!item) continue;
      item.width = Math.max(item.width, STARTER_CARD_MIN_WIDTHS[id]);
      constrainCardBounds(item, canvasWidth, canvasHeight);
      item.visible = true;
      item.minimized = false;
      const dimensions = {id, width:item.width * item.scale, height:TITLE_HEIGHT + item.height * item.scale};
      if (!snapCardPositions(layout, [...placed, dimensions], canvasWidth, canvasHeight)) {
        if (id === "week") {
          item.minimized = true;
          dimensions.height = TITLE_HEIGHT;
        }
        if (id !== "week" || !snapCardPositions(layout, [...placed, dimensions], canvasWidth, canvasHeight)) {
          item.visible = false;
          item.minimized = false;
          continue;
        }
      }
      item.positioned = true;
      placed.push(dimensions);
    }
    return true;
  }
  const diagonalScaleDelta = (item, dx, dy, edge = "right") => {
    const horizontalDelta = edge === "left" ? -dx : dx;
    return (horizontalDelta * item.width + dy * item.height) / (item.width ** 2 + item.height ** 2);
  };
  function migrateCardSizes(layout, saved) {
    for (const [id, [widthFactor, heightFactor]] of Object.entries(CARD_SIZE_FACTORS)) {
      if (!layout[id]) continue;
      const savedCard = saved?.cards?.[id];
      const previousRevision = Number(savedCard?.sizeRevision) || 0;
      const revision = CARD_SIZE_REVISIONS[id] || 1;
      if (savedCard && previousRevision === 0) {
        layout[id].width = Math.ceil(layout[id].width * widthFactor);
        layout[id].height = Math.ceil(layout[id].height * heightFactor);
      } else if (savedCard) {
        const widthFactor = CARD_WIDTH_MIGRATIONS[id]?.[previousRevision];
        const heightFactor = CARD_HEIGHT_MIGRATIONS[id]?.[previousRevision];
        const scaleFactor = CARD_SCALE_MIGRATIONS[id]?.[previousRevision];
        if (widthFactor) layout[id].width = Math.round(layout[id].width * widthFactor);
        if (heightFactor) layout[id].height = Math.round(layout[id].height * heightFactor);
        if (scaleFactor) layout[id].scale = Math.round(layout[id].scale * scaleFactor * 1000) / 1000;
      }
      layout[id].sizeRevision = revision;
    }
    return layout;
  }
  const icon = (name) => `<img src="/assets/window-icons/${name}.svg" alt="" aria-hidden="true">`;

  function defaultLayout(measurements) {
    const result = {};
    const ordered = [...measurements].sort((a, b) => a.y - b.y || a.x - b.x);
    for (const card of ordered) {
      let y = card.y;
      for (const previous of ordered) {
        if (!result[previous.id]) continue;
        const overlaps = previous.x < card.x + card.width - 1 && card.x < previous.x + previous.width - 1;
        if (overlaps && previous.y + previous.height <= card.y + 1) {
          y = Math.max(y, result[previous.id].y + previous.height + TITLE_HEIGHT + 4);
        }
      }
      result[card.id] = { x: card.x, y, width: card.width, height: card.height, scale: 1, minScale: minimumScaleFor(card.id), visible: true, pinned: false, minimized: false, expanded: false, z: Object.keys(result).length + 1, sizeRevision: card.sizeRevision || 1 };
      if (DEFAULT_EXPANDED_CARDS.has(card.id)) {
        result[card.id].compactSize = {width:card.width,height:card.height,scale:1};
        [result[card.id].width,result[card.id].height] = EXPANDED_CARD_SIZES[card.id];
        result[card.id].expanded = true;
      }
    }
    const wire = result["league-wire"];
    if (wire) {
      wire.x = 0;
      wire.y = Math.max(...Object.entries(result).filter(([id]) => id !== "league-wire").map(([, card]) => card.y + TITLE_HEIGHT + card.height * card.scale + 4));
    }
    return result;
  }

  function restoreLayout(raw, defaults) {
    let saved;
    try { saved = JSON.parse(raw); } catch { return structuredClone(defaults); }
    if (saved?.version !== 1 || !saved.cards || typeof saved.cards !== "object") return structuredClone(defaults);
    const result = structuredClone(defaults);
    for (const id of Object.keys(result)) {
      const card = saved.cards[id];
      if (!card || typeof card !== "object") {
        result[id].visible = false;
        continue;
      }
      for (const [field, min, max] of [["x", 0, LIMIT], ["y", 0, LIMIT], ["width", 100, 4000], ["height", 40, 4000], ["scale", .05, 100], ["z", 1, 1000]]) {
        if (Number.isFinite(card[field])) result[id][field] = bounded(card[field], min, max);
      }
      if (typeof card.visible === "boolean") result[id].visible = card.visible;
      if (typeof card.pinned === "boolean") result[id].pinned = card.pinned;
      if (typeof card.minimized === "boolean") result[id].minimized = card.minimized;
      if (typeof card.measured === "boolean") result[id].measured = card.measured;
      if (typeof card.positioned === "boolean") result[id].positioned = card.positioned;
      if (typeof card.expanded === "boolean") result[id].expanded = card.expanded;
      for (const field of ["contentHeightRevision", "feedSizeRevision", "staffExpansionRevision"]) if (Number.isFinite(card[field])) result[id][field] = card[field];
      if (card.compactSize && typeof card.compactSize === "object") {
        const {width, height, scale} = card.compactSize;
        if ([width, height, scale].every(Number.isFinite)) result[id].compactSize = {width, height, scale};
      }
    }
    return result;
  }

  function migrateDefaultCalendar(layout, saved) {
    const item = layout.week;
    const savedCard = saved?.cards?.week;
    if (!item || !savedCard || savedCard.compactSize || savedCard.expanded === false) return layout;
    item.compactSize = {width:item.width,height:item.height,scale:item.scale};
    [item.width,item.height] = EXPANDED_CARD_SIZES.week;
    item.expanded = true;
    item.z = Math.max(0,...Object.values(layout).map(card=>card.z||0))+1;
    return layout;
  }

  function toggleWindowExpansion(item, id) {
    if (!item) return false;
    if (id === "picks") {
      item.expanded = !item.expanded;
      return item.expanded;
    }
    if (item.expanded) {
      Object.assign(item, item.compactSize || {});
      delete item.compactSize;
      item.expanded = false;
      return false;
    }
    item.compactSize = {width: item.width, height: item.height, scale: item.scale};
    if (id === "staff") {
      item.width += STAFF_ACTION_WIDTH;
      item.height += STAFF_MARKET_HEIGHT;
      item.staffExpansionRevision = 1;
    } else if (EXPANDED_CARD_SIZES[id]) {
      [item.width,item.height] = EXPANDED_CARD_SIZES[id];
    } else {
      const [widthFactor,heightFactor] = EXPANSION_FACTORS[id] || [2,1.5];
      item.width = Math.round(item.width * widthFactor);
      item.height = Math.round(item.height * heightFactor);
    }
    item.expanded = true;
    return true;
  }

  function unmount() {
    active?.dispose();
    active = null;
  }

  function enterPhase(layout, defaults, saved, phaseCards, phaseContext) {
    // While a save is still loading the phase is unknown: change nothing, so the real load can tell a reload
    // (same phase as last time, user layout kept) from a first entry.
    if (phaseContext == null) return false;
    const introId = String(phaseContext).includes(":postseason-v2:") ? "phase-playoffs-bracket" : String(phaseContext).includes(":lottery-v2:") ? "phase-draft-lottery" : null;
    const entering = saved?.phaseContext !== phaseContext || Boolean(introId && phaseCards.includes(introId) && !saved?.phaseCards?.includes(introId));
    if (introId) {
      if (entering && phaseCards.includes(introId)) {
        for (const card of Object.values(layout)) card.visible = false;
        Object.assign(layout[introId], defaults[introId], {visible:true, minimized:false, scale:1, measured:true, positioned:true});
      }
      return entering;
    }
    if (entering) for (const id of Object.keys(layout)) {
      if (id.startsWith('phase-') && !phaseCards.includes(id)) layout[id].visible = false;
    }
    let nextY = Math.max(16, ...Object.values(layout).filter(card => card.visible).map(card => card.y + TITLE_HEIGHT + card.height * (card.scale || 1) + 12));
    for (const id of phaseCards.slice(0, PHASE_STARTER_LIMIT)) {
      if (!entering && saved?.phaseCards?.includes(id)) continue;
      if (!saved?.cards?.[id]?.positioned) {
        Object.assign(layout[id], {x:16, y:nextY, width:defaults[id].width, height:defaults[id].height, measured:true, positioned:true});
        nextY += TITLE_HEIGHT + layout[id].height * (layout[id].scale || 1) + 12;
      }
      layout[id].visible = true;
    }
    return entering;
  }

  function enforceRequiredWindows(layout, cards) {
    for (const {id, required, mandatory} of cards) {
      if (required && layout[id]) Object.assign(layout[id], {visible:true, minimized:false});
      else if (mandatory && layout[id]) layout[id].visible = false;
    }
  }

  // Entry layouts (draft night, draft results, playoffs): the phase's cards open together, centered in the visible
  // board, rows stacked top to bottom without overlap. Applied once: when the phase is entered, or when a group of
  // phase cards appears for the first time (draft results). Later loads keep whatever the user arranged or closed.
  function entryLayoutDue(entryLayout, saved, entering) {
    const rows = (entryLayout?.rows || []).filter(row => row.length);
    if (!rows.length) return false;
    if (entering) return true;
    const phaseIds = rows.flat().filter(id => id.startsWith("phase-"));
    return phaseIds.length > 0 && !phaseIds.some(id => saved?.phaseCards?.includes(id));
  }
  function arrangeEntryRows(layout, rows, viewport, gutter = CANVAS_GUTTER, titleHeight = TITLE_HEIGHT, top = 16) {
    const present = rows.map(row => row.filter(id => layout[id])).filter(row => row.length);
    if (!present.length) return [];
    const availableWidth = Math.max(100, viewport.clientWidth - gutter * 2);
    const availableHeight = Math.max(100, viewport.clientHeight - top - gutter);
    // The board can be scrolled a little past the window (the canvas is 1.3x the visible area), never further.
    const extent = clipboardExtent(viewport.clientWidth, viewport.clientHeight);
    const canvasWidth = Math.max(availableWidth, extent.width - gutter * 2);
    const canvasHeight = Math.max(availableHeight, extent.height - top - gutter);
    const minScale = id => Math.min(1, layout[id].minScale ?? .72);
    const floorOf = row => Math.max(...row.map(minScale));
    const rowWidth = (row, scale) => row.reduce((sum, id) => sum + layout[id].width * scale, 0) + gutter * (row.length - 1);
    const rowHeight = (row, scale) => titleHeight + Math.max(...row.map(id => layout[id].height)) * scale;
    const stackHeight = list => list.reduce((sum, row) => sum + rowHeight(row, floorOf(row)), 0) + gutter * (list.length - 1);
    // A row too wide for the window, even at its cards' smallest readable size, wraps onto as few rows as possible.
    const pack = limit => present.flatMap(row => {
      const out = [];
      for (const id of row) {
        const last = out.at(-1);
        if (last && rowWidth([...last, id], floorOf([...last, id])) <= limit) last.push(id);
        else out.push([id]);
      }
      return out;
    });
    let fitted = pack(availableWidth);
    // Too tall to stack inside the board: keep rows side by side, reaching past the window's right edge instead.
    if (stackHeight(fitted) > canvasHeight) fitted = pack(canvasWidth);
    // Still too tall: the last cards stay closed (they remain one click away in the Cards gallery) rather than overlap.
    while (fitted.length > 1 && stackHeight(fitted) > canvasHeight) {
      fitted.at(-1).pop();
      if (!fitted.at(-1).length) fitted.pop();
    }
    const scales = fitted.map(row => Math.min(1, (availableWidth - gutter * (row.length - 1)) / row.reduce((sum, id) => sum + layout[id].width, 0)));
    const total = fitted.reduce((sum, row, index) => sum + rowHeight(row, scales[index]), 0) + gutter * (fitted.length - 1);
    if (total > availableHeight) {
      const titles = titleHeight * fitted.length + gutter * (fitted.length - 1);
      const shrink = Math.max(0, availableHeight - titles) / Math.max(1, total - titles);
      fitted.forEach((row, index) => { scales[index] = Math.max(Math.max(...row.map(minScale)), scales[index] * shrink); });
    }
    // Pop-ups open in the middle of the screen: the group is centred vertically as well as across (playtest
    // 2026-11-23), unless it fills the window anyway.
    const finalHeight = fitted.reduce((sum, row, index) => sum + rowHeight(row, Math.max(Math.max(...row.map(minScale)), scales[index])), 0)
      + gutter * (fitted.length - 1);
    let y = (viewport.scrollTop || 0) + top + Math.max(0, (availableHeight - finalHeight) / 2);
    const placed = [];
    fitted.forEach((row, index) => {
      const scale = Math.round(Math.max(Math.max(...row.map(minScale)), scales[index]) * 1000) / 1000;
      let x = (viewport.scrollLeft || 0) + gutter + Math.max(0, (availableWidth - rowWidth(row, scale)) / 2);
      for (const id of row) {
        Object.assign(layout[id], {x:Math.round(x), y:Math.round(y), scale, visible:true, minimized:false, positioned:true, measured:true});
        placed.push(id);
        x += layout[id].width * scale + gutter;
      }
      y += rowHeight(row, scale) + gutter;
    });
    return placed;
  }
  function applyEntryLayout(layout, entryLayout, viewport, saved, entering) {
    if (!entryLayoutDue(entryLayout, saved, entering)) return [];
    const placed = arrangeEntryRows(layout, entryLayout.rows, viewport);
    const ids = new Set(placed);
    for (const [id, item] of Object.entries(layout)) if (!ids.has(id) && !item.pinned) item.visible = false;
    return placed;
  }
  function centerNewRequiredWindows(layout, cards, saved, entering, viewport) {
    for (const {id, required} of cards) {
      if (!required || (!entering && saved?.phaseCards?.includes(id))) continue;
      const item = layout[id];
      const width = item.width * (item.scale || 1), height = TITLE_HEIGHT + item.height * (item.scale || 1);
      item.x = bounded(viewport.scrollLeft + Math.max(0, (viewport.clientWidth - width) / 2), 0, LIMIT);
      item.y = bounded(viewport.scrollTop + Math.max(0, (viewport.clientHeight - height) / 2), 0, LIMIT);
      item.positioned = true;
    }
  }

  function mount(root, options = {}) {
    unmount();
    const dashboard = root.querySelector(".season-command-dashboard:not(.assets-desktop)");
    const board = dashboard?.querySelector(".season-command-grid");
    if (!board) return;
    const offset = (element) => {
      let x = 0, y = 0;
      for (let node = element; node; node = node.offsetParent) { x += node.offsetLeft; y += node.offsetTop; }
      return { x, y };
    };
    const origin = offset(board);
    const nodes = new Map();
    const measurements = [];
    for (const [id, selector, title] of CARDS) {
      const card = id === "league-wire" ? dashboard.querySelector(selector) : board.querySelector(selector);
      if (!card) continue;
      const position = offset(card), style = getComputedStyle(card);
      const width = parseFloat(style.width), height = parseFloat(style.height);
      if (width < 1 || height < 1) continue;
      nodes.set(id, { card, title });
      const [widthFactor, heightFactor] = CARD_SIZE_FACTORS[id] || [1, 1];
      measurements.push({ id, x: position.x - origin.x, y: position.y - origin.y, width: Math.ceil((id === "staff" ? Math.max(width, 292) : width) * widthFactor), height: Math.ceil(height * heightFactor), sizeRevision: 1 });
    }
    if (!nodes.size) return;
    const defaults = defaultLayout(measurements);
    for (const [id, selector, title] of ASSET_CARDS) {
      const card = options.assetsRoot?.querySelector(selector);
      if (!card) continue;
      const style = getComputedStyle(card);
      nodes.set(id, {card, title, assets: true});
      const rosterTable = id === "roster" ? card.querySelector(".linked-ratings table") : null;
      const statsTable = id === "stats" ? card.querySelector(".linked-stats table") : null;
      const contractTable = id === "contracts" ? card.querySelector(".linked-contracts table") : null;
      const contractWidth = contractTable ? [...contractTable.querySelectorAll("col")].reduce((sum,col)=>sum + (parseFloat(col.style.width)||48),16) : 0;
      const blockTable = ["team-block", "league-block"].includes(id) ? card.querySelector(".assets-block-table") : null;
      const rosterContentHeight = rosterTable
        ? Math.max(40, (rosterTable.tHead?.offsetHeight || 22) + (rosterTable.tBodies[0]?.rows.length || 0) * 22 + 2)
        : Math.max(40, parseFloat(style.height) || 0);
      const statsContentHeight = statsTable
        ? Math.max(40, (statsTable.tHead?.offsetHeight || 22) + (statsTable.tBodies[0]?.rows.length || 0) * 22 + 2)
        : Math.max(40, parseFloat(style.height) || 0);
      const contractRowsHeight = contractTable
        ? [...(contractTable.tBodies[0]?.rows || [])].reduce((sum, row) => sum + row.offsetHeight, 0)
        : 0;
      const teamBlockHeight = id === "team-block" ? Math.max(40, blockTable?.offsetHeight || 20 + 6 * 28) : id === "league-block" ? 24 + 20 + 6 * 28 + 2 : 0;
      defaults[id] = {x:16, y:16, width:contractTable ? contractWidth : Math.max(100,parseFloat(style.width),rosterTable ? rosterTable.scrollWidth + 24 : 0,blockTable ? blockTable.scrollWidth + 16 : 0), height:contractTable ? Math.max(40,(contractTable.tHead?.offsetHeight || 22) + contractRowsHeight + 2) : id === "roster" ? rosterContentHeight : id === "stats" ? statsContentHeight : id === "team-block" ? teamBlockHeight + 2 : Math.max(40,parseFloat(style.height),teamBlockHeight), scale:1, minScale:minimumScaleFor(id), visible:false, pinned:false, minimized:false, z:nodes.size};
    }
    if (defaults["league-block"]) defaults["league-block"].width = Math.max(defaults["league-block"].width, 740);
    for (const {id, title, card, width, height, locked, measured, required, galleryVisible, sizeRevision, initialScale = 1, minScale} of options.extraCards || []) {
      nodes.set(id, {card, title, locked, required, galleryVisible});
      defaults[id] = {x:16, y:16, width, height, scale:initialScale, minScale:Number.isFinite(minScale) ? minScale : minimumScaleFor(id), visible:false, pinned:false, minimized:false, z:nodes.size, measured:Boolean(measured), positioned:false, sizeRevision:Number(sizeRevision) || 0};
    }
    const key = `nbaGmCardBoard:v1:${options.save || "preview"}`;
    let raw = memory.get(key);
    try { raw = localStorage.getItem(key) || raw; } catch { /* Private browsing can deny preference storage. */ }
    let layout = restoreLayout(raw, defaults);
    let saved;
    try { saved = JSON.parse(raw); } catch { saved = {}; }
    migrateCardSizes(layout, saved);
    for (const {id, sizeRevision} of options.extraCards || []) {
      const revision = Number(sizeRevision) || 0;
      if (!revision || !layout[id]) continue;
      const previousRevision = Number(saved?.cards?.[id]?.sizeRevision) || 0;
      if (previousRevision < revision) {
        const previousScale = layout[id].scale || 1;
        const previousWidth = layout[id].width || defaults[id].width;
        layout[id].x = bounded(layout[id].x - ((defaults[id].width * defaults[id].scale) - (previousWidth * previousScale)) / 2, 0, LIMIT);
        Object.assign(layout[id], {width:defaults[id].width, height:defaults[id].height, scale:defaults[id].scale, sizeRevision:revision});
      }
    }
    migrateDefaultCalendar(layout, saved);
    if (layout.contracts && Number(layout.contracts.tableFormatRevision || 0) < 2) {
      Object.assign(layout.contracts, {width:defaults.contracts.width, height:defaults.contracts.height, tableFormatRevision:2});
    }
    if (layout.contracts && Number(layout.contracts.tableFormatRevision || 0) < 3) {
      Object.assign(layout.contracts, {height:defaults.contracts.height, tableFormatRevision:3});
    }
    if (layout.contracts) layout.contracts.height = Math.max(layout.contracts.height, defaults.contracts.height);
    if (layout.staff) layout.staff.width = Math.max(layout.staff.width, defaults.staff.width);
    if (layout.staff) layout.staff.height = Math.max(layout.staff.height, defaults.staff.height);
    if (layout.staff?.expanded && layout.staff.compactSize && !layout.staff.staffExpansionRevision) {
      Object.assign(layout.staff, {width:layout.staff.compactSize.width + STAFF_ACTION_WIDTH, height:layout.staff.compactSize.height + STAFF_MARKET_HEIGHT, staffExpansionRevision:1});
    }
    if (layout.minutes) layout.minutes.width = Math.max(layout.minutes.width, defaults.minutes.width);
    if (layout.roster && !saved?.cards?.stats && !saved?.cards?.contracts) {
      layout.roster.width = defaults.roster.width;
    }
    if (layout.roster) {
      if ((Number(saved?.cards?.roster?.sizeRevision) || 0) < 3) layout.roster.height = defaults.roster.height;
      layout.roster.width = Math.max(layout.roster.width, defaults.roster.width);
      layout.roster.height = Math.max(layout.roster.height, defaults.roster.height);
    }
    if (layout.stats) {
      if ((Number(saved?.cards?.stats?.contentHeightRevision) || 0) < 1) layout.stats.height = defaults.stats.height;
      layout.stats.height = Math.max(layout.stats.height, defaults.stats.height);
      layout.stats.contentHeightRevision = 1;
    }
    for (const id of ["team-block", "league-block"]) if (layout[id]) layout[id].width = Math.max(layout[id].width, defaults[id].width);
    for (const id of ["team-block", "league-block"]) if (layout[id]) layout[id].height = Math.max(layout[id].height, defaults[id].height);
    if (layout["team-block"] && (Number(saved?.cards?.["team-block"]?.contentHeightRevision) || 0) < 2) {
      Object.assign(layout["team-block"], {height:defaults["team-block"].height, contentHeightRevision:2});
    }
    if (layout["league-wire"]?.expanded && !layout["league-wire"].feedSizeRevision) {
      Object.assign(layout["league-wire"], {width:500, height:650, scale:1, feedSizeRevision:1});
    }
    for (const id of EXPANDABLE_CARDS) {
      if (nodes.has(id)) options.onExpandedChange?.(id, Boolean(layout[id].expanded), nodes.get(id).card);
    }
    const phaseCards = (options.extraCards || []).filter(card => card.phaseActive).map(card => card.id);
    for (const {id, measured, sizingKey} of options.extraCards || []) {
      if (measured && (!saved?.cards?.[id]?.measured || sizingKey && saved?.cards?.[id]?.sizingKey !== sizingKey)) {
        Object.assign(layout[id], {width:defaults[id].width, height:defaults[id].height, measured:true, sizingKey});
        // A window given a new default size reopens centred rather than at its old spot (playtest 2026-11-23).
        if (saved?.cards?.[id]) {
          const width = layout[id].width * (layout[id].scale || 1), height = TITLE_HEIGHT + layout[id].height * (layout[id].scale || 1);
          layout[id].x = bounded(board.scrollLeft + Math.max(0, (board.clientWidth - width) / 2), 0, LIMIT);
          layout[id].y = bounded(board.scrollTop + Math.max(0, (board.clientHeight - height) / 2), 0, LIMIT);
        }
      }
    }
    const entering = enterPhase(layout, defaults, saved, phaseCards, options.phaseContext);
    enforceRequiredWindows(layout, options.extraCards || []);
    const locked = id => Boolean(options.lockedCards?.[id] || nodes.get(id)?.locked);
    let drag = null;
    let resize = null;
    let galleryOpen = false;
    let windowSwitcherSession = null;
    const galleryGroupsOpen = new Map();

    const canvas = document.createElement("div");
    canvas.className = "card-board-canvas";
    canvas.setAttribute("aria-label", "Card workspace");
    const gallery = document.createElement("aside");
    gallery.className = "card-board-gallery";
    gallery.hidden = true;
    gallery.id = "seasonCardGallery";
    gallery.setAttribute("aria-label", "Card gallery");
    gallery.innerHTML = `<header class="card-board-gallery-head"><h2>Card Gallery</h2><button type="button" class="card-board-control" data-board-gallery-close aria-label="Close card gallery" title="Close card gallery">${icon("x")}</button></header><div class="card-board-gallery-list"></div>`;
    const galleryList = gallery.querySelector(".card-board-gallery-list");
    const toolbar = document.createElement("div");
    toolbar.className = "card-board-tools";
    toolbar.dataset.cardBoardTools = "";
    const simDisabled = options.toolbarActions?.simulationDisabled ? "disabled" : "";
    const tradeDisabled = options.toolbarActions?.tradeDisabled ? "disabled" : "";
    const offerCount = Number(options.toolbarActions?.offerCount || 0);
    const tradeMarkup = String(options.phaseContext).includes(":postseason-v2:") ? "" : `<div class="card-board-trade-control" data-trade-menu><button type="button" class="card-board-trade-trigger" data-trade-menu-trigger aria-controls="cardBoardTradeMenu" aria-haspopup="menu" aria-expanded="false" aria-keyshortcuts="T" aria-label="${offerCount ? `Trades, ${offerCount} incoming offers` : "Trades"}" title="Trade tools" ${tradeDisabled}>Trades...<span class="card-board-trade-badge" aria-hidden="true"${offerCount ? "" : " hidden"}>${offerCount}</span></button><div class="card-board-menu card-board-trade-menu" id="cardBoardTradeMenu" role="menu" aria-label="Trade tools" hidden><button type="button" role="menuitem" data-trade-menu-item="finder" ${tradeDisabled}>Trade Finder</button><button type="button" role="menuitem" data-trade-menu-item="builder" ${tradeDisabled}>Trade Builder</button><button type="button" role="menuitem" data-trade-menu-item="offers" ${tradeDisabled}>Incoming Offers${offerCount ? ` (${offerCount})` : ""}</button><button type="button" role="menuitem" data-trade-menu-item="market" ${tradeDisabled}>Trade Market</button></div></div>`;
    toolbar.innerHTML = `<button type="button" class="card-board-gallery-toggle" aria-controls="seasonCardGallery" aria-expanded="false" title="Card gallery">Cards</button><button type="button" class="card-board-window-switcher-toggle" data-window-switcher-open aria-controls="cardWindowSwitcher" aria-haspopup="dialog" aria-expanded="false" aria-keyshortcuts="Alt+Tab Alt+Backquote" title="Switch windows (Option/Alt+Tab forward; Option/Alt+&#96; backward)">Windows</button><button type="button" class="card-board-control" data-board-snap aria-label="Snap cards" title="Snap cards into a compact layout">Snap</button><div class="card-board-sim-control" data-sim-menu><button type="button" class="card-board-sim-trigger" data-sim-menu-trigger aria-controls="cardBoardSimMenu" aria-haspopup="menu" aria-expanded="false" ${simDisabled}>Sim to...</button><div class="card-board-menu card-board-sim-menu" id="cardBoardSimMenu" role="menu" aria-label="Sim to" hidden>${simulationMenuMarkup(String(options.phaseContext).includes(":postseason-v2:"), simDisabled)}</div></div>${tradeMarkup}`;
    dashboard.querySelector(".season-command-actions").prepend(toolbar);
    if (options.phaseCommands) {
      const commands = document.createElement('div');
      commands.className = 'card-board-phase-actions';
      commands.innerHTML = options.phaseCommands;
      toolbar.querySelector('[data-sim-menu]').replaceWith(commands);
    }
    const presetsKey = `nbaGmSavedLayouts:v1:${options.save || "preview"}`;
    let presets;
    try { presets=JSON.parse(localStorage.getItem(presetsKey) || memory.get(presetsKey) || "null"); } catch { presets=null; }
    presets=Array.from({length:3},(_,index)=>({name:String(presets?.[index]?.name || `Layout ${index+1}`).slice(0,40),snapshot:presets?.[index]?.snapshot || null}));
    const layoutsControl=document.createElement("div");
    layoutsControl.className="card-board-layout-control";
    layoutsControl.innerHTML=`<button type="button" class="card-board-control" data-layout-menu-trigger aria-controls="cardBoardLayoutMenu" aria-haspopup="menu" aria-expanded="false">Layouts</button><div class="card-board-menu card-board-layout-menu" id="cardBoardLayoutMenu" role="menu" aria-label="Saved layouts" hidden><div data-layout-slots></div></div>`;
    toolbar.querySelector('[data-board-snap]').before(layoutsControl);
    const layoutSlots=layoutsControl.querySelector('[data-layout-slots]');
    const renderPresets=()=>{ layoutSlots.innerHTML=presets.map((slot,index)=>`<div class="card-board-layout-slot"><input aria-label="Layout ${index+1} name" data-layout-name="${index}" maxlength="40" value="${escapeHtml(slot.name)}"><button type="button" role="menuitem" data-layout-load="${index}" ${slot.snapshot ? "" : "disabled"}>Load</button><button type="button" role="menuitem" data-layout-save="${index}">${slot.snapshot ? "Replace" : "Save"}</button></div>`).join(""); };
    renderPresets();
    const persistPresets=()=>{
      const value=JSON.stringify(presets);
      memory.set(presetsKey,value);
      try { localStorage.setItem(presetsKey,value); return true; } catch { return false; }
    };
    layoutsControl.addEventListener('change',event=>{
      if (!event.target.matches('[data-layout-name]')) return;
      const index=Number(event.target.dataset.layoutName);
      presets[index].name=event.target.value.trim() || `Layout ${index+1}`;
      event.target.value=presets[index].name;
      persistPresets();
    });
    const toggle = toolbar.querySelector(".card-board-gallery-toggle");
    const toolbarMenus = [
      {control:layoutsControl,trigger:layoutsControl.querySelector("[data-layout-menu-trigger]"),menu:layoutsControl.querySelector(".card-board-layout-menu")},
      { control: toolbar.querySelector("[data-sim-menu]"), trigger: toolbar.querySelector("[data-sim-menu-trigger]"), menu: toolbar.querySelector(".card-board-sim-menu") },
      { control: toolbar.querySelector("[data-trade-menu]"), trigger: toolbar.querySelector("[data-trade-menu-trigger]"), menu: toolbar.querySelector(".card-board-trade-menu") },
    ].filter(item=>item.control && item.trigger && item.menu);
    const updateOfferCount = (value, options = {}) => {
      const count = Math.max(0, Math.floor(Number(value) || 0));
      const tradeMenu = toolbarMenus.find(menuState => menuState.trigger.matches("[data-trade-menu-trigger]"));
      if (!tradeMenu) return false;
      const badge = tradeMenu.trigger.querySelector(".card-board-trade-badge");
      const previousCount = Math.max(0, Math.floor(Number(badge.textContent) || 0));
      badge.textContent = String(count);
      badge.hidden = count === 0;
      if (options.animate && count > previousCount) {
        badge.classList.remove("is-popping");
        void badge.offsetWidth;
        badge.classList.add("is-popping");
        badge.addEventListener("animationend", () => badge.classList.remove("is-popping"), {once:true});
      }
      tradeMenu.trigger.setAttribute("aria-label", count ? `Trades, ${count} incoming offer${count === 1 ? "" : "s"}` : "Trades");
      tradeMenu.trigger.title = count ? `${count} incoming offer${count === 1 ? "" : "s"}` : "Trade tools";
      const offersItem = tradeMenu.menu.querySelector('[data-trade-menu-item="offers"]');
      if (offersItem) offersItem.textContent = `Incoming Offers${count ? ` (${count})` : ""}`;
      return true;
    };
    const setMenuOpen = (menuState, open, focus = "") => {
      const { trigger, menu } = menuState;
      menu.hidden = !open;
      trigger.setAttribute("aria-expanded", String(open));
      trigger.classList.toggle("is-open", open);
      if (open) {
        const rect = trigger.getBoundingClientRect();
        const left = Math.max(6, Math.min(rect.left, window.innerWidth - menu.offsetWidth - 6));
        const top = Math.max(6, Math.min(rect.bottom + 3, window.innerHeight - menu.offsetHeight - 6));
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
        if (focus === "first") menu.querySelector('[role="menuitem"]:not(:disabled)')?.focus({ preventScroll: true });
      } else if (focus === "trigger") trigger.focus({ preventScroll: true });
    };
    const dismissToolbarMenusOutside = (event) => {
      for (const menuState of toolbarMenus) {
        if (!menuState.menu.hidden && !menuState.control.contains(event.target)) setMenuOpen(menuState, false);
      }
    };
    const dismissToolbarMenusOnResize = () => {
      for (const menuState of toolbarMenus) if (!menuState.menu.hidden) setMenuOpen(menuState, false);
    };
    document.addEventListener("click", dismissToolbarMenusOutside);
    window.addEventListener("resize", dismissToolbarMenusOnResize);
    const status = document.createElement("div");
    status.className = "card-board-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    const windowSwitcher = document.createElement("div");
    windowSwitcher.className = "card-board-window-switcher";
    windowSwitcher.id = "cardWindowSwitcher";
    windowSwitcher.hidden = true;
    windowSwitcher.innerHTML = `<section class="card-board-window-switcher-panel" role="dialog" aria-modal="true" aria-label="Switch windows" tabindex="-1"><header>Switch windows</header><div class="card-board-window-switcher-items"></div></section>`;
    dashboard.append(windowSwitcher);

    const frames = new Map();
    // The window's own icon on its title-bar tab and in the window switcher (window-icons.js; easy to swap there).
    const windowIcon = (id, node = nodes.get(id)) => window.WindowIcons?.svg(id, {kind: node?.iconKind || "", className: "window-icon"}) || "";
    const createWindowFrame = (id, node) => {
      const {card, title, assets} = node;
      const safeId = escapeHtml(id);
      const safeTitle = escapeHtml(title || "Card");
      const frame = document.createElement("section");
      frame.className = "card-board-window";
      frame.dataset.boardWindow = id;
      frame.setAttribute("aria-label", `${title || "Card"} window`);
      frame.innerHTML = `<header class="card-board-titlebar"><button type="button" class="card-board-move" data-board-move="${safeId}" aria-label="Move ${safeTitle}" aria-keyshortcuts="Escape Shift+Escape M P Space" title="Move ${safeTitle}; Esc closes, Shift+Esc minimizes or restores; M minimizes or restores, P pins, Space expands or collapses"><span class="card-board-window-mark" aria-hidden="true"></span><span>${safeTitle}</span></button><div class="card-board-window-controls">${EXPANDABLE_CARDS.has(id) ? `<button type="button" class="card-board-control" data-board-expand="${safeId}" aria-label="Expand ${safeTitle}" title="Expand ${safeTitle}" aria-pressed="false">${icon("plus")}</button>` : ""}${id === "minutes" ? `<button type="button" class="card-board-control card-board-minutes-reset" data-minute-reset-all aria-label="Reset all player minutes to automatic allocation" title="Reset all minutes to automatic allocation">Reset</button>` : ""}<button type="button" class="card-board-control" data-board-pin="${safeId}" aria-label="Pin ${safeTitle}" title="Pin ${safeTitle}" aria-pressed="false">${icon("pin")}</button><button type="button" class="card-board-control" data-board-minimize="${safeId}" aria-label="Minimize ${safeTitle}" title="Minimize ${safeTitle}" aria-expanded="true">${icon("minus")}</button><button type="button" class="card-board-control card-board-close" data-board-close="${safeId}" aria-label="Close ${safeTitle}" title="Close ${safeTitle}">${icon("x")}</button></div><div class="card-board-actions" hidden></div></header><button type="button" class="card-board-resize-handle card-board-resize-handle--left" data-board-resize="${safeId}" data-board-resize-edge="left" aria-label="Resize ${safeTitle} from bottom left" title="Resize ${safeTitle} from bottom left"></button><button type="button" class="card-board-resize-handle card-board-resize-handle--right" data-board-resize="${safeId}" data-board-resize-edge="right" aria-label="Resize ${safeTitle} from bottom right" title="Resize ${safeTitle} from bottom right"></button>`;
      const body = document.createElement("div");
      body.className = `card-board-body${assets ? " assets-desktop" : ""}${card.matches("[data-assets-trade]") ? " assets-trade-tools" : ""}`;
      body.append(card);
      frame.append(body, ...frame.querySelectorAll("[data-board-resize]"));
      canvas.append(frame);
      frames.set(id, frame);
      return frame;
    };
    for (const [id, { card, title, assets }] of nodes) {
      // Keep the original measurements, but let the window title replace pure labels.
      const redundantHeader = ["identity", "signals", "morale", "factors", "standings", "efficiency", "staff", "minutes"].includes(id)
        ? ":scope > .season-panel-header"
        : ["offense", "defense"].includes(id) ? ":scope > h3"
        : id.startsWith("award-") ? ":scope > .season-award-head" : null;
      if (redundantHeader) {
        card.querySelector(redundantHeader)?.remove();
        card.classList.add("card-board-headerless");
      }
      createWindowFrame(id, {card, title, assets});
    }
    board.replaceChildren(canvas);
    options.assetsRoot?.remove();
    board.classList.add("card-board-scroll");
    dashboard.classList.add("has-card-board");
    board.parentElement.append(gallery, status);

    const announce = (message) => { status.textContent = message; };
    const save = () => {
      const known = options.phaseContext != null;
      const value = JSON.stringify({ version: 1, cards: {...saved?.cards, ...layout}, phaseContext:known ? options.phaseContext : saved?.phaseContext, phaseCards:known ? phaseCards : (saved?.phaseCards || []) });
      memory.set(key, value);
      try { localStorage.setItem(key, value); } catch { /* The in-memory board still works. */ }
    };
    const canvasLimit = (dimension) => clipboardExtent(board.clientWidth, board.clientHeight)[dimension.toLowerCase()];
    const constrainCard = (id) => {
      const item = layout[id], frame = frames.get(id);
      const minimizedHeight = item.minimized || locked(id) ? Math.max(TITLE_HEIGHT, frame.offsetHeight) : null;
      constrainCardBounds(item, canvasLimit("Width"), canvasLimit("Height"), CANVAS_GUTTER, TITLE_HEIGHT, minimizedHeight);
    };
    const sizeCanvas = () => {
      const boardWidth = board.clientWidth, boardHeight = board.clientHeight;
      if (boardWidth < 1 || boardHeight < 1) return;
      const extent = clipboardExtent(boardWidth, boardHeight);
      // Read all dimensions before changing styles to avoid laying out the board per card.
      const minimizedHeights = new Map([...nodes.keys()].map(id => [id,
        layout[id].minimized || locked(id) ? Math.max(TITLE_HEIGHT, frames.get(id).offsetHeight) : null,
      ]));
      for (const id of nodes.keys()) {
        const item = layout[id], frame = frames.get(id), card = nodes.get(id).card;
        constrainCardBounds(item, extent.width, extent.height, CANVAS_GUTTER, TITLE_HEIGHT, minimizedHeights.get(id));
        Object.assign(frame.style, { left: `${item.x}px`, top: `${item.y}px`, width: `${item.width * item.scale}px`, height: item.minimized || locked(id) ? "auto" : `${TITLE_HEIGHT + item.height * item.scale}px` });
        frame.style.setProperty("--matched-bar-height", `${6 * (layout.development?.scale || 1) / item.scale}px`);
        Object.assign(frame.querySelector(".card-board-body").style, { left: "0px", top: `${TITLE_HEIGHT}px`, width: `${item.width}px`, height: `${item.height}px`, transform: `scale(${item.scale})`, transformOrigin: "top left" });
        Object.assign(card.style, { width: `${item.width}px`, height: `${item.height}px` });
        if (id === "staff") card.style.setProperty("--staff-compact-height", `${item.compactSize?.height || item.height}px`);
      }
      canvas.style.width = `${extent.width}px`;
      canvas.style.height = `${extent.height}px`;
    };
    const parkedActions = new Map();
    const syncActions = (id) => {
      const frame = frames.get(id), card = nodes.get(id).card;
      const actions = frame.querySelector(".card-board-actions");
      if ((layout[id].minimized || locked(id)) && !parkedActions.has(id)) {
        const buttons = card.matches("[data-assets-trade]") ? [card] : [
          ...card.querySelectorAll(":scope > .season-panel-header button, :scope > .season-award-head button, .season-sim-actions button, [data-assets-block-nav], [data-assets-retry], [data-window-command]"),
        ];
        parkedActions.set(id, buttons.map(button => {
          const marker = document.createComment("window command position");
          button.before(marker);
          actions.append(button);
          if (locked(id)) button.disabled = true;
          return {button, marker};
        }));
      } else if (!layout[id].minimized && !locked(id) && parkedActions.has(id)) {
        for (const {button, marker} of parkedActions.get(id)) {
          if (marker.isConnected) marker.replaceWith(button);
          else button.remove();
        }
        parkedActions.delete(id);
      }
      actions.hidden = !(layout[id].minimized || locked(id)) || !actions.childElementCount;
    };
    const paint = (id) => {
      const item = layout[id];
      const frame = frames.get(id);
      frame.hidden = !item.visible;
      if (id === 'team-wants' && item.visible && !item.minimized) {
        const card = nodes.get(id).card;
        item.height = Math.max(62, (card.querySelector('.team-wants-toolbar')?.offsetHeight || 31)
          + (card.querySelector('.team-wants-list')?.scrollHeight || 27) + 4);
      }
      frame.classList.toggle("is-pinned", item.pinned);
      frame.classList.toggle("is-minimized", item.minimized || locked(id));
      frame.classList.toggle("is-phase-locked", locked(id));
      nodes.get(id).card.inert = locked(id);
      if (locked(id)) nodes.get(id).card.querySelectorAll("button, input, select, textarea").forEach(control => control.disabled = true);
      syncActions(id);
      Object.assign(frame.style, { left: `${item.x}px`, top: `${item.y}px`, width: `${item.width * item.scale}px`, height: item.minimized || locked(id) ? "auto" : `${TITLE_HEIGHT + item.height * item.scale}px`, zIndex: String(item.z) });
      frame.style.setProperty("--matched-bar-height", `${6 * (layout.development?.scale || 1) / item.scale}px`);
        Object.assign(frame.querySelector(".card-board-body").style, { left: "0px", top: `${TITLE_HEIGHT}px`, width: `${item.width}px`, height: `${item.height}px`, transform: `scale(${item.scale})`, transformOrigin: "top left" });
      Object.assign(nodes.get(id).card.style, { width: `${item.width}px`, height: `${item.height}px` });
      if (id === "staff") nodes.get(id).card.style.setProperty("--staff-compact-height", `${item.compactSize?.height || item.height}px`);
      const pin = frame.querySelector("[data-board-pin]");
      pin.setAttribute("aria-pressed", String(item.pinned));
      pin.setAttribute("aria-label", `${item.pinned ? "Unpin" : "Pin"} ${nodes.get(id).title}`);
      pin.title = pin.getAttribute("aria-label");
      pin.querySelector("img").src = `/assets/window-icons/${item.pinned ? "pin-off" : "pin"}.svg`;
      frame.querySelector("[data-board-move]").setAttribute("aria-disabled", String(item.pinned));
      const minimize = frame.querySelector("[data-board-minimize]");
      minimize.hidden = locked(id) || Boolean(nodes.get(id).required);
      minimize.disabled = minimize.hidden;
      const close = frame.querySelector("[data-board-close]");
      close.hidden = Boolean(nodes.get(id).required);
      close.disabled = close.hidden;
      minimize.setAttribute("aria-label", `${item.minimized ? "Restore" : "Minimize"} ${nodes.get(id).title}`);
      minimize.title = minimize.getAttribute("aria-label");
      minimize.setAttribute("aria-expanded", String(!item.minimized));
      minimize.querySelector("img").src = `/assets/window-icons/${item.minimized ? "square" : "minus"}.svg`;
      const expand = frame.querySelector("[data-board-expand]");
      if (expand) {
        expand.setAttribute("aria-pressed", String(Boolean(item.expanded)));
        expand.setAttribute("aria-label", `${item.expanded ? "Collapse" : "Expand"} ${nodes.get(id).title}`);
        expand.title = expand.getAttribute("aria-label");
        expand.querySelector("img").src = `/assets/window-icons/${item.expanded ? "panels-top-left" : "plus"}.svg`;
      }
      for (const resizeHandle of frame.querySelectorAll("[data-board-resize]")) {
        resizeHandle.hidden = item.minimized || locked(id);
        resizeHandle.disabled = resizeHandle.hidden;
      }
    };
    const raise = (id) => {
      const order = Object.keys(layout).sort((a, b) => layout[a].z - layout[b].z);
      order.filter(key => key !== id).concat(id).forEach((key, index) => {
        layout[key].z = index + 1;
        frames.get(key).style.zIndex = String(index + 1);
        frames.get(key).classList.toggle("is-active", key === id);
      });
    };
    const reveal = (id) => frames.get(id).scrollIntoView({ block: "nearest", inline: "nearest" });
    const switchableIds = () => switchableWindowOrder(layout, [...nodes]
      .filter(([_id, node]) => node.galleryVisible !== false)
      .map(([id]) => id));
    const switcherItems = windowSwitcher.querySelector(".card-board-window-switcher-items");
    const renderWindowSwitcher = () => {
      switcherItems.replaceChildren();
      windowSwitcherSession.ids.forEach((id, index) => {
        const item = document.createElement("button");
        item.type = "button";
        item.dataset.windowSwitcherTarget = id;
        item.setAttribute("aria-pressed", String(index === windowSwitcherSession.index));
        item.setAttribute("aria-label", `Switch to ${nodes.get(id).title}`);
        item.title = nodes.get(id).title;
        const cardState=locked(id)?"Unavailable":layout[id].minimized?"Minimized":layout[id].pinned?"Pinned":layout[id].expanded?"Expanded":"Open";
        item.innerHTML = `<span class="card-board-window-switcher-icon" aria-hidden="true">${windowIcon(id) || window.CardVisuals.icon(id)}</span><span class="card-board-window-switcher-name"></span><small class="card-board-window-switcher-state">${cardState}</small>`;
        item.querySelector(".card-board-window-switcher-name").textContent = nodes.get(id).title;
        switcherItems.append(item);
      });
      switcherItems.children[windowSwitcherSession.index]?.focus({ preventScroll: true });
    };
    const startWindowSwitcher = (cycle, direction = 1, modifier = null) => {
      const ids = switchableIds();
      if (!ids.length || (cycle && ids.length < 2)) return false;
      const activeId = ids.find(id => frames.get(id).classList.contains("is-active")) || ids[0];
      let index = ids.indexOf(activeId);
      if (cycle) index = cycleWindowIndex(index, ids.length, direction);
      windowSwitcherSession = {ids, index, modifier, returnFocus:document.activeElement};
      windowSwitcher.hidden = false;
      toolbar.querySelector("[data-window-switcher-open]").setAttribute("aria-expanded", "true");
      toolbar.querySelector("[data-window-switcher-open]").classList.add("is-open");
      renderWindowSwitcher();
      return true;
    };
    const cycleWindowSwitcher = (direction) => {
      if (!windowSwitcherSession) return;
      const currentId = windowSwitcherSession.ids[windowSwitcherSession.index];
      const ids = switchableIds();
      if (!ids.length) return finishWindowSwitcher(false);
      const currentIndex = ids.indexOf(currentId);
      windowSwitcherSession.ids = ids;
      windowSwitcherSession.index = cycleWindowIndex(currentIndex < 0 ? 0 : currentIndex, ids.length, direction);
      renderWindowSwitcher();
    };
    const selectWindowSwitcherIndex = (index) => {
      if (!windowSwitcherSession) return;
      const ids = switchableIds();
      if (!ids.length) return finishWindowSwitcher(false);
      windowSwitcherSession.ids = ids;
      windowSwitcherSession.index = bounded(index, 0, ids.length - 1);
      renderWindowSwitcher();
    };
    const finishWindowSwitcher = (commit, restoreFocus = true) => {
      const session = windowSwitcherSession;
      if (!session) return;
      const id = session.ids[session.index];
      windowSwitcherSession = null;
      windowSwitcher.hidden = true;
      toolbar.querySelector("[data-window-switcher-open]").setAttribute("aria-expanded", "false");
      toolbar.querySelector("[data-window-switcher-open]").classList.remove("is-open");
      if (commit && id && layout[id]?.visible && nodes.get(id)?.galleryVisible !== false) {
        if (!locked(id)) layout[id].minimized = false;
        paint(id);
        raise(id);
        sizeCanvas();
        save();
        reveal(id);
        frames.get(id).querySelector("[data-board-move]").focus({ preventScroll: true });
        announce(`${nodes.get(id).title} active`);
        options.onOpen?.(id, nodes.get(id).card);
      } else if (restoreFocus && session.returnFocus?.isConnected) session.returnFocus.focus({ preventScroll: true });
    };
    const handleWindowSwitcherKeydown = (event) => {
      if (event.isComposing || event.defaultPrevented) return;
      const modifier = event.altKey ? "Alt" : null;
      const direction = altWindowSwitcherDirection(event);
      if (direction !== null) {
        if (!windowSwitcherSession && document.querySelector("#modalRoot [role=dialog]")) return;
        if (!windowSwitcherSession && switchableIds().length < 2) return;
        event.preventDefault();
        event.stopPropagation();
        if (!windowSwitcherSession) startWindowSwitcher(true, direction, modifier);
        else {
          if (windowSwitcherSession.modifier && windowSwitcherSession.modifier !== modifier) return;
          windowSwitcherSession.modifier = modifier;
          cycleWindowSwitcher(direction);
        }
        return;
      }
      if (!windowSwitcherSession) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        finishWindowSwitcher(false);
      } else if (event.key === "Tab") {
        event.preventDefault();
        event.stopPropagation();
        cycleWindowSwitcher(event.shiftKey ? -1 : 1);
      } else if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
        cycleWindowSwitcher(["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1);
      } else if (event.key === "Home" || event.key === "End") {
        event.preventDefault();
        event.stopPropagation();
        selectWindowSwitcherIndex(event.key === "Home" ? 0 : windowSwitcherSession.ids.length - 1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        event.stopPropagation();
        finishWindowSwitcher(true);
      } else event.stopPropagation();
    };
    const handleWindowSwitcherKeyup = (event) => {
      if (!windowSwitcherSession?.modifier) return;
      if ((windowSwitcherSession.modifier === "Alt" && event.key === "Alt") || (windowSwitcherSession.modifier === "Control" && event.key === "Control")) finishWindowSwitcher(true);
    };
    document.addEventListener("keydown", handleWindowSwitcherKeydown, true);
    document.addEventListener("keyup", handleWindowSwitcherKeyup, true);
    windowSwitcher.addEventListener("click", event => {
      if (event.target === windowSwitcher) finishWindowSwitcher(false);
    });

    const galleryIcon = (id) => {
      const art=document.createElement("span");
      art.className="card-board-gallery-icon";
      art.setAttribute("aria-hidden","true");
      art.innerHTML=window.CardVisuals.preview ? window.CardVisuals.preview(id) : window.CardVisuals.icon(id);
      return art;
    };
    const refreshGallery = () => {
      galleryList.replaceChildren();
      const grouped = new Map(GALLERY_CATEGORIES.map(([id]) => [id, []]));
      for (const [id, node] of nodes) {
        if (node.galleryVisible === false) continue;
        grouped.get(galleryCategoryFor(id)).push([id, node]);
      }
      const firstCategory = GALLERY_CATEGORIES.find(([id]) => grouped.get(id).length)?.[0];
      for (const [category, label] of GALLERY_CATEGORIES) {
        const cards = grouped.get(category);
        if (!cards.length) continue;
        const expanded = galleryGroupsOpen.get(category) ?? category === firstCategory;
        const group = document.createElement("section");
        group.className = "card-board-gallery-group";
        group.dataset.boardGalleryGroup = category;
        const heading = document.createElement("button");
        heading.type = "button";
        heading.className = "card-board-gallery-group-toggle";
        heading.dataset.boardGalleryGroupToggle = category;
        heading.setAttribute("aria-expanded", String(expanded));
        heading.setAttribute("aria-controls", `${gallery.id}-${category}`);
        heading.innerHTML = `<span>${label}</span><small>${cards.length}</small><i aria-hidden="true"></i>`;
        const items = document.createElement("div");
        items.className = "card-board-gallery-group-items";
        items.classList.toggle("is-open", expanded);
        items.id = `${gallery.id}-${category}`;
        items.setAttribute("aria-hidden", String(!expanded));
        items.inert = !expanded;
        const itemsInner = document.createElement("div");
        itemsInner.className = "card-board-gallery-group-items-inner";
        items.append(itemsInner);
        group.append(heading, items);
        galleryList.append(group);
        for (const [id, {title}] of cards) {
          const entry = document.createElement("section");
          entry.className = "card-board-gallery-entry";
          entry.dataset.boardGalleryCard = id;
          const safeId = escapeHtml(id);
          const safeTitle = escapeHtml(title || "Card");
          entry.innerHTML = `<div role="button" tabindex="0" class="card-board-thumbnail" data-board-gallery-drag="${safeId}" aria-label="${layout[id].visible ? "Show" : "Add"} ${safeTitle}" title="${layout[id].visible ? "Show" : "Add"} ${safeTitle}"><span class="card-board-thumb-frame${nodes.get(id).assets ? " assets-desktop" : ""}${id.startsWith("trade-") ? " assets-trade-tools" : ""}"></span></div><footer><span><strong>${safeTitle}</strong><small>${escapeHtml(window.CardVisuals.description(id))}</small></span><button type="button" class="card-board-control" data-board-add="${safeId}" aria-label="${layout[id].visible ? "Show" : "Add"} ${safeTitle}" title="${layout[id].visible ? "Show" : "Add"} ${safeTitle}">${icon(layout[id].visible ? "panels-top-left" : "plus")}</button></footer>`;
          entry.querySelector(".card-board-thumb-frame").append(galleryIcon(id));
          if (layout[id].visible) {
            entry.classList.add("is-on-board");
            const badge=document.createElement("span");
            badge.className="card-board-gallery-state";
            badge.textContent=layout[id].minimized ? "Minimized" : "Open";
            entry.querySelector(".card-board-thumbnail").append(badge);
          }

          itemsInner.append(entry);
        }
      }
    };
    const showGallery = (open) => {
      galleryOpen = open;
      gallery.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
      toggle.classList.toggle("is-open", open);
      if (open) { refreshGallery(); gallery.querySelector("[data-board-gallery-close]").focus(); }
      else toggle.focus({ preventScroll: true });
    };
    const selectedWindow = () => {
      const ids = [...nodes.keys()];
      const activeId = ids.find(id => frames.get(id).classList.contains("is-active"));
      return selectedWindowId(layout, ids, activeId);
    };
    const closeWindow = (id, focusNext = false) => {
      if (!id || !layout[id]?.visible || nodes.get(id)?.required) return false;
      layout[id].visible = false;
      options.onVisibilityChange?.(id, false);
      paint(id);
      sizeCanvas();
      save();
      if (galleryOpen) refreshGallery();
      const nextId = focusNext ? frontmostVisibleWindow(layout, [...nodes.keys()], id) : null;
      if (nextId) {
        raise(nextId);
        reveal(nextId);
        frames.get(nextId).querySelector("[data-board-move]").focus({ preventScroll: true });
      } else toggle.focus({ preventScroll: true });
      announce(`${nodes.get(id).title} closed`);
      return true;
    };
    const toggleWindowMinimized = (id, focusControl = false) => {
      if (!id || !layout[id]?.visible || locked(id) || nodes.get(id)?.required) return false;
      layout[id].minimized = !layout[id].minimized;
      paint(id);
      sizeCanvas();
      save();
      announce(`${nodes.get(id).title} ${layout[id].minimized ? "minimized" : "restored"}`);
      if (focusControl) frames.get(id).querySelector("[data-board-minimize]").focus({ preventScroll: true });
      if (!layout[id].minimized) options.onOpen?.(id, nodes.get(id).card);
      return true;
    };
    const toggleWindowExpanded = (id, focusControl = false) => {
      if (!layout[id] || !EXPANDABLE_CARDS.has(id)) return false;
      toggleWindowExpansion(layout[id], id);
      options.onExpandedChange?.(id, Boolean(layout[id].expanded), nodes.get(id).card);
      paint(id);
      raise(id);
      sizeCanvas();
      save();
      reveal(id);
      announce(`${nodes.get(id).title} ${layout[id].expanded ? "expanded" : "collapsed"}`);
      if (focusControl) frames.get(id).querySelector("[data-board-expand]")?.focus({ preventScroll: true });
      return true;
    };
    const closeActiveWindow = () => closeWindow(selectedWindow(), true);
    const toggleActiveWindowMinimized = () => toggleWindowMinimized(selectedWindow(), true);
    const toggleActiveWindowPinned = () => {
      if (galleryOpen) return false;
      const id = selectedWindow();
      if (!id || !layout[id]?.visible) return false;
      layout[id].pinned = !layout[id].pinned;
      paint(id);
      save();
      announce(`${nodes.get(id).title} ${layout[id].pinned ? "pinned" : "unpinned"}`);
      frames.get(id).querySelector("[data-board-pin]")?.focus({ preventScroll: true });
      return true;
    };
    const toggleActiveWindowExpanded = () => galleryOpen ? false : toggleWindowExpanded(selectedWindow(), true);
    const add = (id) => {
      const item = layout[id];
      if (!item.visible) {
        const width = item.width * item.scale, height = TITLE_HEIGHT + item.height * item.scale;
        const playerCardOffset = id.startsWith("player-card-")
          ? Math.min([...nodes.keys()].filter(key => key.startsWith("player-card-") && key !== id && layout[key]?.visible).length * 42, 210)
          : 0;
        item.x = bounded(board.scrollLeft + Math.max(0, (board.clientWidth - width) / 2) + playerCardOffset, 0, LIMIT);
        item.y = bounded(board.scrollTop + Math.max(0, (board.clientHeight - height) / 2) + playerCardOffset, 0, LIMIT);
        item.positioned = true;
        item.visible = true;
        item.minimized = false;
      } else item.minimized = false;
      paint(id);
      raise(id);
      sizeCanvas();
      save();
      showGallery(false);
      reveal(id);
      frames.get(id).querySelector("[data-board-move]").focus({ preventScroll: true });
      options.onVisibilityChange?.(id, true);
      announce(`${nodes.get(id).title} opened`);
      options.onOpen?.(id, nodes.get(id).card);
    };
    const addClipboardCard = (descriptor) => {
      const {id, title, card, width = 1040, height = 590, galleryVisible = true, initialScale = 1, minScale, iconKind = ""} = descriptor || {};
      const sizeRevision = Number(descriptor?.sizeRevision) || 0;
      if (!id || !card) return false;
      const resolvedMinScale = Number.isFinite(minScale) ? minScale : minimumScaleFor(id);
      const node = nodes.get(id);
      if (node) {
        layout[id].minScale = resolvedMinScale;
        if (sizeRevision && sizeRevision > (Number(layout[id]?.sizeRevision) || 0)) {
          const previousScale = layout[id].scale || 1;
          const previousWidth = layout[id].width || width;
          layout[id].x = bounded(layout[id].x - ((width * initialScale) - (previousWidth * previousScale)) / 2, 0, LIMIT);
          Object.assign(layout[id], {width, height, scale:initialScale, sizeRevision});
        }
        node.title = title || node.title;
        node.card = card;
        node.galleryVisible = galleryVisible;
        if (iconKind && iconKind !== node.iconKind) {
          node.iconKind = iconKind;
          // Title bars carry no icon (taste deck 2026-11-23); the window switcher still shows it.
        }
        const frame = frames.get(id);
        frame.setAttribute("aria-label", `${node.title} window`);
        frame.querySelector(".card-board-body").replaceChildren(card);
        const move = frame.querySelector("[data-board-move]");
        move.querySelector("span:last-child").textContent = node.title;
        move.setAttribute("aria-label", `Move ${node.title}`);
        move.title = `Move ${node.title}; Esc closes, Shift+Esc minimizes or restores; M minimizes or restores, P pins, Space expands or collapses`;
        for (const control of frame.querySelectorAll("[data-board-pin],[data-board-minimize],[data-board-close]")) {
          const label = control.matches("[data-board-pin]") && layout[id].pinned ? "Unpin" : control.matches("[data-board-pin]") ? "Pin" : control.matches("[data-board-minimize]") ? "Minimize" : "Close";
          control.setAttribute("aria-label", `${label} ${node.title}`);
          control.title = `${label} ${node.title}`;
        }
      } else {
        nodes.set(id, {card, title: title || "Player Card", galleryVisible, iconKind});
        layout[id] = {x:16, y:16, width, height, scale:initialScale, minScale:resolvedMinScale, visible:false, pinned:false, minimized:false, z:Object.keys(layout).length + 1, positioned:false, sizeRevision};
        createWindowFrame(id, nodes.get(id));
      }
      if (galleryOpen) refreshGallery();
      add(id);
      return true;
    };

    const savePreset=(index)=>{
      const visible=[...nodes.keys()].filter(id=>layout[id].visible);
      presets[index].snapshot={cards:structuredClone(layout),scroll:{x:board.scrollLeft,y:board.scrollTop},customCards:options.captureLayoutCards?.(visible) || []};
      const persisted=persistPresets();
      renderPresets();
      announce(`${presets[index].name} saved${persisted ? "" : " for this session; browser storage is full"}`);
    };
    const loadPreset=(index)=>{
      const snapshot=presets[index]?.snapshot;
      if (!snapshot) return;
      finishDrag(true); finishResize(true); finishWindowSwitcher(false,false);
      showGallery(false);
      for (const descriptor of options.restoreLayoutCards?.(snapshot.customCards || []) || []) addClipboardCard(descriptor);
      const restored=restoreLayout(JSON.stringify({version:1,cards:snapshot.cards}),layout);
      for (const id of nodes.keys()) {
        Object.assign(layout[id],restored[id]);
        if (!snapshot.cards?.[id]) layout[id].visible=false;
        if (EXPANDABLE_CARDS.has(id)) options.onExpandedChange?.(id,Boolean(layout[id].expanded),nodes.get(id).card);
        paint(id);
      }
      const front=[...nodes.keys()].filter(id=>layout[id].visible).sort((a,b)=>layout[b].z-layout[a].z)[0];
      for (const [id,frame] of frames) frame.classList.toggle('is-active',id===front);
      sizeCanvas();
      board.scrollTo(snapshot.scroll?.x || 0,snapshot.scroll?.y || 0);
      scrollPositions.set(key,{x:board.scrollLeft,y:board.scrollTop});
      save();
      for (const [id,node] of nodes) if (layout[id].visible && !layout[id].minimized && !locked(id)) options.onOpen?.(id,node.card);
      options.onLayoutRestored?.();
      announce(`${presets[index].name} loaded`);
    };
    dashboard.addEventListener("click", (event) => {
      const button = event.target.closest("button,[data-board-gallery-drag]");
      if (!button) return;
      if (button.matches("[data-window-switcher-open]")) {
        if (windowSwitcherSession) finishWindowSwitcher(false);
        else startWindowSwitcher(false);
      } else if (button.dataset.windowSwitcherTarget) finishWindowSwitcher(true);
      else if (button.matches("[data-board-gallery-group-toggle]")) {
        const category = button.dataset.boardGalleryGroupToggle;
        const expanded = button.getAttribute("aria-expanded") !== "true";
        if (expanded) {
          for (const other of galleryList.querySelectorAll("[data-board-gallery-group-toggle][aria-expanded='true']")) {
            if (other === button) continue;
            other.setAttribute("aria-expanded", "false");
            const otherItems = other.nextElementSibling;
            otherItems.classList.remove("is-open");
            otherItems.setAttribute("aria-hidden", "true");
            otherItems.inert = true;
            galleryGroupsOpen.set(other.dataset.boardGalleryGroupToggle, false);
          }
        }
        button.setAttribute("aria-expanded", String(expanded));
        const items = button.nextElementSibling;
        items.classList.toggle("is-open", expanded);
        items.setAttribute("aria-hidden", String(!expanded));
        items.inert = !expanded;
        galleryGroupsOpen.set(category, expanded);
        return;
      }
      const triggeredMenu = toolbarMenus.find(menuState => menuState.trigger === button);
      const owningMenu = toolbarMenus.find(menuState => menuState.menu.contains(button));
      if (triggeredMenu) {
        for (const menuState of toolbarMenus) if (menuState !== triggeredMenu && !menuState.menu.hidden) setMenuOpen(menuState, false);
        setMenuOpen(triggeredMenu, triggeredMenu.menu.hidden, triggeredMenu.menu.hidden ? "first" : "trigger");
      }
      else if (owningMenu) {
        setMenuOpen(owningMenu, false, "trigger");
        if (button.matches("[data-trade-menu-item]")) options.onTradeMenuAction?.(button.dataset.tradeMenuItem);
        if (button.matches("[data-layout-save]")) savePreset(Number(button.dataset.layoutSave));
        if (button.matches("[data-layout-load]")) loadPreset(Number(button.dataset.layoutLoad));
      }
      else if (button === toggle) showGallery(!galleryOpen);
      else if (button.matches("[data-board-gallery-close]")) showGallery(false);
      else if (button.dataset.boardAdd || button.dataset.boardGalleryDrag) add(button.dataset.boardAdd || button.dataset.boardGalleryDrag);
      else if (button.dataset.boardClose) {
        closeWindow(button.dataset.boardClose);
      } else if (button.dataset.boardMinimize) {
        toggleWindowMinimized(button.dataset.boardMinimize);
      } else if (button.dataset.boardExpand) {
        toggleWindowExpanded(button.dataset.boardExpand);
      } else if (button.dataset.boardPin) {
        const id = button.dataset.boardPin;
        layout[id].pinned = !layout[id].pinned;
        paint(id);
        save();
        announce(`${nodes.get(id).title} ${layout[id].pinned ? "pinned" : "unpinned"}`);
      } else if (button.matches("[data-board-snap]")) {
        const visibleIds = [...nodes.keys()].filter(id => layout[id].visible)
          .sort((a, b) => layout[a].y - layout[b].y || layout[a].x - layout[b].x || (layout[a].z || 0) - (layout[b].z || 0));
        const viewport = {width:board.clientWidth, height:board.clientHeight, x:board.scrollLeft, y:board.scrollTop};
        const startingScales = new Map(visibleIds.map(id => [id, layout[id].scale || 1]));
        const cardsAtScale = (factor) => visibleIds.map(id => {
          const item = layout[id], startingScale = startingScales.get(id);
          const scale = Math.max(item.minScale ?? .72, startingScale * factor);
          const collapsed = item.minimized || locked(id);
          return {id, scale, width:item.width * scale, height:collapsed ? Math.max(TITLE_HEIGHT, frames.get(id).offsetHeight) : TITLE_HEIGHT + item.height * scale};
        });
        const trySnap = factor => {
          const cards = cardsAtScale(factor);
          return snapCardPositions(layout, cards, viewport.width, viewport.height, CANVAS_GUTTER, viewport.x, viewport.y) ? cards : null;
        };
        let snappedCards = trySnap(1);
        if (!snappedCards && visibleIds.length) {
          const minimumFactor = Math.min(1, ...visibleIds.map(id => (layout[id].minScale ?? .72) / startingScales.get(id)));
          let lower = minimumFactor, upper = 1;
          snappedCards = trySnap(lower);
          if (snappedCards) {
            for (let attempt = 0; attempt < 14; attempt += 1) {
              const middle = (lower + upper) / 2;
              const candidate = trySnap(middle);
              if (candidate) { snappedCards = candidate; lower = middle; }
              else upper = middle;
            }
          }
        }
        if (!snappedCards) {
          announce("Not enough room to snap every visible card");
          return;
        }
        for (const card of snappedCards) layout[card.id].scale = card.scale;
        sizeCanvas();
        save();
        announce("Cards snapped into the current view");
      }
    });

    dashboard.addEventListener("focusin", (event) => {
      const frame = event.target.closest("[data-board-window]");
      if (frame) { raise(frame.dataset.boardWindow); save(); }
    });
    const point = (event) => {
      const rect = board.getBoundingClientRect();
      return { x: event.clientX - rect.left + board.scrollLeft, y: event.clientY - rect.top + board.scrollTop };
    };
    const finishDrag = (cancel = false) => {
      if (!drag) return;
      const ended = drag;
      drag = null;
      if (cancel || !ended.started) layout[ended.id] = ended.original;
      paint(ended.id);
      frames.get(ended.id).classList.remove("is-dragging");
      ended.target.classList.remove("is-drag-source");
      if (ended.target.hasPointerCapture(ended.pointerId)) ended.target.releasePointerCapture(ended.pointerId);
      sizeCanvas();
      if (ended.started) {
        save();
        if (ended.gallery && !cancel) {
          showGallery(false);
          frames.get(ended.id).querySelector("[data-board-move]").focus({ preventScroll: true });
        } else if (galleryOpen) refreshGallery();
        announce(`${nodes.get(ended.id).title} ${cancel ? "move canceled" : "placed"}`);
      }
    };
    const finishResize = (cancel = false) => {
      if (!resize) return;
      const ended = resize;
      resize = null;
      if (cancel || !ended.started) layout[ended.id].scale = ended.originalScale;
      paint(ended.id);
      frames.get(ended.id).classList.remove("is-resizing");
      if (ended.target.hasPointerCapture(ended.pointerId)) ended.target.releasePointerCapture(ended.pointerId);
      sizeCanvas();
      if (ended.started) {
        save();
        announce(`${nodes.get(ended.id).title} ${cancel ? "resize canceled" : "resized"}`);
      }
    };
    dashboard.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || !event.isPrimary) return;
      const frame = event.target.closest("[data-board-window]");
      if (frame) { raise(frame.dataset.boardWindow); save(); }
      const resizeHandle = event.target.closest("[data-board-resize]");
      if (resizeHandle) {
        const id = resizeHandle.dataset.boardResize;
        if (locked(id) || layout[id].minimized || resize || drag) return;
        event.preventDefault();
        event.stopPropagation();
        resize = {id, edge:resizeHandle.dataset.boardResizeEdge, target:resizeHandle, pointerId:event.pointerId, startX:event.clientX, startY:event.clientY, originalScale:layout[id].scale || 1, started:false};
        resizeHandle.setPointerCapture(event.pointerId);
        return;
      }
      const minimizedFrame = frame?.classList.contains("is-minimized") ? frame : null;
      if (minimizedFrame && event.target.closest("button:not([data-board-move])")) return;
      const handle = event.target.closest("[data-board-move], [data-board-gallery-drag]")
        || (minimizedFrame && event.target.closest(".card-board-titlebar") ? minimizedFrame.querySelector("[data-board-move]") : null);
      if (!handle || drag) return;
      const id = handle.dataset.boardMove || handle.dataset.boardGalleryDrag || minimizedFrame?.dataset.boardWindow;
      if (layout[id].pinned) return;
      const start = point(event);
      drag = { id, target: handle, pointerId: event.pointerId, gallery: Boolean(handle.dataset.boardGalleryDrag), start, clientX: event.clientX, clientY: event.clientY, original: { ...layout[id] }, started: false };
      handle.setPointerCapture(event.pointerId);
    });
    dashboard.addEventListener("pointermove", (event) => {
      if (resize && event.pointerId === resize.pointerId) {
        const dx = event.clientX - resize.startX, dy = event.clientY - resize.startY;
        if (!resize.started && Math.hypot(dx, dy) < 2) return;
        event.preventDefault();
        const item = layout[resize.id];
        if (!resize.started) {
          resize.started = true;
          frames.get(resize.id).classList.add("is-resizing");
        }
        item.scale = resize.originalScale + diagonalScaleDelta(item, dx, dy, resize.edge);
        constrainCard(resize.id);
        paint(resize.id);
        sizeCanvas();
        return;
      }
      if (!drag || event.pointerId !== drag.pointerId) return;
      if (!drag.started && Math.hypot(event.clientX - drag.clientX, event.clientY - drag.clientY) < 4) return;
      event.preventDefault();
      const item = layout[drag.id];
      if (!drag.started) {
        drag.started = true;
        item.visible = true;
        item.positioned = true;
        raise(drag.id);
        frames.get(drag.id).classList.add("is-dragging");
        drag.target.classList.add("is-drag-source");
      }
      const rect = board.getBoundingClientRect();
      if (event.clientY < rect.top + 28) board.scrollTop = Math.max(0, board.scrollTop - 12);
      else if (event.clientY > rect.bottom - 28) board.scrollTop += 12;
      if (event.clientX < rect.left + 28) board.scrollLeft = Math.max(0, board.scrollLeft - 12);
      else if (event.clientX > rect.right - 28) board.scrollLeft += 12;
      const current = point(event);
      item.x = bounded(drag.gallery ? current.x - Math.min(80, item.width / 2) : drag.original.x + current.x - drag.start.x, 0, LIMIT);
      item.y = bounded(drag.gallery ? current.y - TITLE_HEIGHT / 2 : drag.original.y + current.y - drag.start.y, 0, LIMIT);
      paint(drag.id);
      sizeCanvas();
    });
    dashboard.addEventListener("pointerup", (event) => {
      if (resize && event.pointerId === resize.pointerId) { finishResize(); return; }
      if (!drag || event.pointerId !== drag.pointerId) return;
      const rect = board.getBoundingClientRect();
      const galleryRect = gallery.getBoundingClientRect();
      const onGallery = galleryOpen && event.clientX >= galleryRect.left && event.clientX <= galleryRect.right && event.clientY >= galleryRect.top && event.clientY <= galleryRect.bottom;
      const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
      if (drag.started) {
        // Suppress only the synthetic click after a drag; ordinary thumbnail
        // clicks and all business controls retain their original behavior.
        drag.target.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); }, { once: true });
      }
      finishDrag(Boolean(drag.gallery && (onGallery || outside)));
    });
    dashboard.addEventListener("pointercancel", () => { finishResize(true); finishDrag(true); });
    dashboard.addEventListener("lostpointercapture", (event) => {
      if (resize && event.pointerId === resize.pointerId) finishResize(true);
      if (drag && event.pointerId === drag.pointerId) finishDrag(true);
    });
    gallery.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || !galleryOpen) return;
      event.preventDefault();
      event.stopPropagation();
      showGallery(false);
    });
    dashboard.addEventListener("keydown", (event) => {
      const thumbnail = event.target.closest("[data-board-gallery-drag]");
      if (thumbnail && ["Enter", " "].includes(event.key)) { event.preventDefault(); add(thumbnail.dataset.boardGalleryDrag); return; }
      const openMenu = toolbarMenus.find(menuState => !menuState.menu.hidden);
      if (event.key === "Escape" && openMenu) { event.preventDefault(); event.stopPropagation(); setMenuOpen(openMenu, false, "trigger"); return; }
      const focusedMenu = toolbarMenus.find(menuState => !menuState.menu.hidden && menuState.control.contains(event.target));
      if (focusedMenu && !event.target.matches("input,textarea") && ["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        const items = [...focusedMenu.menu.querySelectorAll('[role="menuitem"]:not(:disabled)')];
        const current = items.indexOf(document.activeElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 : (current + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        event.preventDefault();
        event.stopPropagation();
        items[next]?.focus({ preventScroll: true });
        return;
      }
      if (event.key === "Escape" && resize) { event.preventDefault(); event.stopPropagation(); finishResize(true); return; }
      if (event.key === "Escape" && drag) { event.preventDefault(); event.stopPropagation(); finishDrag(true); return; }
      if (event.key === "Escape" && galleryOpen) { event.preventDefault(); event.stopPropagation(); showGallery(false); return; }
      const resizeHandle = event.target.closest("[data-board-resize]");
      if (resizeHandle && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
        const id = resizeHandle.dataset.boardResize;
        const grows = event.key === "ArrowDown" || (resizeHandle.dataset.boardResizeEdge === "left" ? event.key === "ArrowLeft" : event.key === "ArrowRight");
        const direction = grows ? 1 : -1;
        layout[id].scale += direction * (event.shiftKey ? .1 : .025);
        constrainCard(id);
        paint(id);
        raise(id);
        sizeCanvas();
        save();
        announce(`${nodes.get(id).title} resized`);
        return;
      }
      const handle = event.target.closest("[data-board-move]");
      if (!handle || layout[handle.dataset.boardMove].pinned) return;
      const directions = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      const direction = directions[event.key];
      if (!direction) return;
      event.preventDefault();
      event.stopPropagation();
      const id = handle.dataset.boardMove;
      const step = event.shiftKey ? 40 : 10;
      layout[id].x = bounded(layout[id].x + direction[0] * step, 0, LIMIT);
      layout[id].y = bounded(layout[id].y + direction[1] * step, 0, LIMIT);
      paint(id);
      raise(id);
      sizeCanvas();
      reveal(id);
      save();
    });

    // Place the startup cards inside the visible board, even though the workspace
    // itself keeps extra canvas area available for arranging cards later.
    initializeStarterLayout(layout, saved, board.clientWidth, board.clientHeight, phaseCards);
    for (const id of nodes.keys()) paint(id);
    const front = (options.extraCards || []).find(card => card.required)?.id
      || Object.keys(layout).filter(id => layout[id].visible).sort((a, b) => layout[b].z - layout[a].z)[0];
    if (front) raise(front);
    sizeCanvas();
    const observer = new ResizeObserver(sizeCanvas);
    observer.observe(board);
    const scroll = scrollPositions.get(key);
    if (scroll) board.scrollTo(scroll.x, scroll.y);
    centerNewRequiredWindows(layout, options.extraCards || [], saved, entering, board);
    const entryPlaced = options.phaseContext == null || (options.extraCards || []).some(card => card.required) ? [] : applyEntryLayout(layout, options.entryLayout, board, saved, entering);
    if (entryPlaced.length) {
      for (const id of nodes.keys()) paint(id);
      for (const id of [...entryPlaced].reverse()) raise(id);
      if (entryPlaced.length > 1) announce(`${entryPlaced.map(id => nodes.get(id)?.title).filter(Boolean).join(", ")} opened`);
    }
    const introId = String(options.phaseContext).includes(":postseason-v2:") ? "phase-playoffs-bracket" : String(options.phaseContext).includes(":lottery-v2:") ? "phase-draft-lottery" : null;
    if (introId && entryPlaced.includes(introId)) layout[introId].topAlignedRevision = 1;
    else if (introId && layout[introId] && (entering || !saved?.cards?.[introId]?.topAlignedRevision)) {
      const item = layout[introId];
      board.scrollTo(0, 0);
      item.x = Math.max(0, (board.clientWidth - item.width * (item.scale || 1)) / 2);
      item.y = 16;
      item.topAlignedRevision = 1;
      paint(introId);
    }
    for (const {id, required} of options.extraCards || []) if (required) paint(id);
    sizeCanvas();
    save();
    if (entering && phaseCards.length && !entryPlaced.length && !(options.extraCards || []).some(card => card.required)) reveal(phaseCards[0]);
    active = { dispose: () => { scrollPositions.set(key, {x:board.scrollLeft, y:board.scrollTop}); finishWindowSwitcher(false, false); finishResize(true); finishDrag(true); observer.disconnect(); document.removeEventListener("click", dismissToolbarMenusOutside); document.removeEventListener("keydown", handleWindowSwitcherKeydown, true); document.removeEventListener("keyup", handleWindowSwitcherKeyup, true); window.removeEventListener("resize", dismissToolbarMenusOnResize); }, closeActive:closeActiveWindow, toggleActiveMinimize:toggleActiveWindowMinimized, toggleActivePin:toggleActiveWindowPinned, toggleActiveExpansion:toggleActiveWindowExpanded, updateOfferCount };
    active.open = (id) => { if (!layout[id]) return false; add(id); return true; };
    active.isOpen = id => Boolean(layout[id]?.visible);
    active.fitContent = id => { if(id !== 'team-wants' || !layout[id]) return; paint(id); sizeCanvas(); save(); };
    active.addCard = addClipboardCard;
    active.expand = (id) => {
      if (!layout[id] || !EXPANDABLE_CARDS.has(id)) return false;
      if (!layout[id].visible) add(id);
      if (!layout[id].expanded) toggleWindowExpanded(id);
      return true;
    };
    let tutorialWorkspace = null;
    const restoreTutorialWorkspace = () => {
      if (!tutorialWorkspace) return;
      layout = structuredClone(tutorialWorkspace.layout);
      for (const id of nodes.keys()) paint(id);
      const front = frontmostVisibleWindow(layout, [...nodes.keys()]);
      if (front) raise(front);
      sizeCanvas();
      board.scrollTo(tutorialWorkspace.x, tutorialWorkspace.y);
    };
    active.previewTutorialWindow = (id) => {
      if (!tutorialWorkspace && nodes.has(id)) tutorialWorkspace = {layout:structuredClone(layout), x:board.scrollLeft, y:board.scrollTop};
      restoreTutorialWorkspace();
      if (!tutorialWorkspace || !nodes.has(id)) return;
      const item = layout[id];
      item.visible = true;
      item.minimized = false;
      item.x = board.scrollLeft + Math.max(CANVAS_GUTTER, (board.clientWidth - item.width * item.scale) / 2);
      item.y = board.scrollTop + Math.max(CANVAS_GUTTER, (board.clientHeight - TITLE_HEIGHT - item.height * item.scale) / 2);
      paint(id);
      raise(id);
      sizeCanvas();
      reveal(id);
    };
    active.endTutorialPreview = () => {
      restoreTutorialWorkspace();
      tutorialWorkspace = null;
    };
    for (const [id, node] of nodes) {
      options.onVisibilityChange?.(id, Boolean(layout[id].visible));
      if (layout[id].visible && !layout[id].minimized && !locked(id)) options.onOpen?.(id, node.card);
    }
  }

  window.CardBoard = Object.freeze({ fitContent: (id) => active?.fitContent?.(id), mount, unmount, open: (id) => active?.open(id), isOpen: (id) => active?.isOpen(id), addCard: (descriptor) => active?.addCard?.(descriptor) || false, expand: (id) => active?.expand?.(id) || false, updateOfferCount: (count, options) => active?.updateOfferCount?.(count, options) || false, previewTutorialWindow: (id) => active?.previewTutorialWindow?.(id), endTutorialPreview: () => active?.endTutorialPreview?.(), closeActive: () => active?.closeActive?.() || false, toggleActiveMinimize: () => active?.toggleActiveMinimize?.() || false, toggleActivePin: () => active?.toggleActivePin?.() || false, toggleActiveExpansion: () => active?.toggleActiveExpansion?.() || false, defaultLayout, initializeStarterLayout, restoreLayout, migrateDefaultCalendar, toggleWindowExpansion, enterPhase, enforceRequiredWindows, centerNewRequiredWindows, constrainCardBounds, snapCardPositions, clipboardExtent, simulationMenuMarkup, entryLayoutDue, arrangeEntryRows, applyEntryLayout, diagonalScaleDelta, migrateCardSizes, galleryCategoryFor, switchableWindowOrder, frontmostVisibleWindow, selectedWindowId, cycleWindowIndex, altWindowSwitcherDirection });
})();
