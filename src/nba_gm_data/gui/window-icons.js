/* Window icons: one distinct icon per window type, used by the window switcher and each window's title-bar tab.
   To swap an icon, change its glyph name in WINDOWS (or edit the glyph's drawing in GLYPHS). Glyphs are drawn on a
   24 x 24 grid with round 2px strokes; the tile colour comes from the window's group. Unknown windows get the
   neutral "window" fallback. Preview every icon on one sheet: /window-icons-sheet.html */
(() => {
  "use strict";

  // Group: [tile fill, tile edge, ink]
  const GROUPS = {
    team: ["#dbe8f2", "#a9c3d8", "#24557c"],
    season: ["#e2e8f6", "#b2bfdf", "#344a8c"],
    scouting: ["#f4ead0", "#d9c38d", "#7d5b14"],
    "front-office": ["#dcefe2", "#a6cdb2", "#25643e"],
    league: ["#e5e9ec", "#bcc5cc", "#3f4c56"],
    required: ["#f7dfe0", "#dba7ab", "#962c36"],
    playoffs: ["#f8e6c6", "#dfbf86", "#83530c"],
    draft: ["#ebe1f5", "#c6b1df", "#57358a"],
    "free-agency": ["#d6efed", "#9dcfca", "#1b6460"],
    "fantasy-draft": ["#fbe2d1", "#e7b493", "#934514"],
    cards: ["#e1e7ed", "#b3c0cc", "#2f4558"],
    fallback: ["#eef1f3", "#c3ccd3", "#5d6b77"],
  };

  // Drawings (24 x 24, stroke only unless a shape sets fill="currentColor").
  const GLYPHS = {
    window: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M6.5 6.5h.01M9.5 6.5h.01"/>',
    checklist: '<path d="M10 6h10M10 12h10M10 18h10"/><path d="M3.5 6l1.5 1.5 2.5-3M3.5 12l1.5 1.5 2.5-3M3.5 18l1.5 1.5 2.5-3"/>',
    calendar_check: '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4M9 15l2 2 4-4"/>',
    jersey: '<path d="M8.5 3 4 5.5l1.8 4.2L8 8.8V21h8V8.8l2.2.9L20 5.5 15.5 3c-.6 1.6-1.9 2.6-3.5 2.6S9.1 4.6 8.5 3z"/>',
    signal: '<path d="M5 20v-3M10 20v-7M15 20V9M20 20V4"/>',
    heart: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.1 4.1 0 0 1 12 7.4a4.1 4.1 0 0 1 7.5 2.4C19.5 15.4 12 20 12 20z"/>',
    four: '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="4" width="7" height="7" rx="1"/><rect x="4" y="13" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/>',
    target_arrow: '<circle cx="10" cy="14" r="7"/><circle cx="10" cy="14" r="2.5"/><path d="M10 14 20 4M15.5 4H20v4.5"/>',
    shield: '<path d="M12 3 19 6v5.5c0 4.6-3 8-7 9.5-4-1.5-7-4.9-7-9.5V6z"/><path d="M12 8v8M8.5 11.5h7"/>',
    ranked: '<path d="M10 6h10M10 12h7M10 18h4"/><circle cx="5" cy="6" r="1.4" fill="currentColor"/><circle cx="5" cy="12" r="1.4" fill="currentColor"/><circle cx="5" cy="18" r="1.4" fill="currentColor"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4M8 14h2M14 14h2M8 17h2"/>',
    versus: '<path d="M5 4 19 18M19 4 5 18M3 16l5 5M16 21l5-5"/>',
    stopwatch: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 13.5V9.5M10 2.5h4M12 2.5V6M18.5 6.5l1.5-1.5"/>',
    trend_up: '<path d="M3 17 9 11l4 4 8-8M15 7h6v6"/>',
    line_chart: '<path d="M4 4v16h16M7.5 15l3.5-4 3 2.5L19 7.5"/>',
    magnifier: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/>',
    trophy: '<path d="M8 4h8v5.5a4 4 0 0 1-8 0zM8 6H5v1.2A3.2 3.2 0 0 0 8.2 10.4M16 6h3v1.2a3.2 3.2 0 0 1-3.2 3.2M12 13.5V17M8 20.5h8M9.5 17h5v3.5h-5z"/>',
    medal: '<path d="M8 3l3 6M16 3l-3 6"/><circle cx="12" cy="15" r="5.5"/><path d="M12 12.2v3.4l2 1.2"/>',
    star: '<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    clipboard: '<rect x="5.5" y="4.5" width="13" height="16.5" rx="2"/><path d="M9 4.5V3h6v1.5M9 10h6M9 13.5h6M9 17h3.5"/>',
    megaphone: '<path d="M4 10v4h3l8 4.5v-13L7 10zM18.5 9a4 4 0 0 1 0 6M7 14v5h3v-3.5"/>',
    newspaper: '<path d="M4 5h13v14H6a2 2 0 0 1-2-2zM17 9h3v8a2 2 0 0 1-2 2M7 9h7M7 12.5h7M7 16h4"/>',
    thread: '<path d="M6 4v16M6 6h9M6 12h12M6 18h7"/><circle cx="6" cy="6" r="1.6"/><circle cx="6" cy="12" r="1.6"/><circle cx="6" cy="18" r="1.6"/>',
    group: '<circle cx="9" cy="8.5" r="3.2"/><path d="M3 20c.4-3.6 2.8-5.8 6-5.8s5.6 2.2 6 5.8"/><circle cx="17" cy="9" r="2.5"/><path d="M16.2 14.3c2.6.2 4.4 2 4.8 5.2"/>',
    table: '<rect x="3" y="4" width="18" height="16" rx="1.5"/><path d="M3 9h18M3 14.5h18M9 4v16"/>',
    contract: '<path d="M6 3h8l4 4v14H6zM14 3v4h4M8.5 17.5c1.2-2 2.3.9 3.6-.8 1-1.4 1.6.2 3.4.2"/><path d="M9 10h5"/>',
    banknote: '<rect x="2.5" y="6" width="19" height="12" rx="1.5"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.5v.01M18 14.5v.01"/>',
    ticket: '<path d="M3 8.5a2.5 2.5 0 0 0 2.5-2.5h13A2.5 2.5 0 0 0 21 8.5v2a1.5 1.5 0 0 0 0 3v2a2.5 2.5 0 0 0-2.5 2.5h-13A2.5 2.5 0 0 0 3 15.5v-2a1.5 1.5 0 0 0 0-3z"/><path d="M14 7v1.5M14 11.2v1.6M14 15.5V17"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.8 2.8 2.8 14.2 0 17M12 3.5c-2.8 2.8-2.8 14.2 0 17"/>',
    box: '<path d="M3.5 7.5 12 3.5l8.5 4v9L12 20.5l-8.5-4zM3.5 7.5 12 11.5l8.5-4M12 11.5v9"/>',
    bullseye: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.8"/><circle cx="12" cy="12" r="1.3" fill="currentColor"/>',
    user_check: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.4-3.8 3-6 6.5-6 1.6 0 3 .4 4.1 1.3M15 12l2.2 2.2L21.5 10"/>',
    scissors: '<circle cx="6" cy="6.5" r="2.8"/><circle cx="6" cy="17.5" r="2.8"/><path d="M8.3 8 20 18.5M8.3 16 20 5.5"/>',
    bracket: '<path d="M3 5h5v6H3M3 13h5v6H3M8 8h4v8H8M12 12h9"/>',
    podium: '<path d="M3 20.5h18M9 20.5V9h6v11.5M3 20.5v-7h6M15 20.5v-5h6M12 3.5v2.5"/>',
    medical: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8v8M8 12h8"/>',
    balls: '<circle cx="7" cy="15.5" r="3.5"/><circle cx="17" cy="15.5" r="3.5"/><circle cx="12" cy="7.5" r="3.5"/>',
    id_card: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10.5" r="2"/><path d="M5.8 16c.6-1.6 1.8-2.3 3.2-2.3s2.6.7 3.2 2.3M14.5 10h3.5M14.5 13.5h3.5"/>',
    numbered: '<path d="M10 6h10M10 12h10M10 18h10M4 4.5h1.3V9M3.8 9h3M3.8 13.4a1.4 1.4 0 1 1 2.3 1L3.8 17h3"/>',
    doc_check: '<path d="M6 3h8l4 4v14H6zM14 3v4h4M9 14l2 2 4-4.5"/>',
    swap: '<path d="M7 4 3 8l4 4M3 8h14M17 12l4 4-4 4M21 16H7"/>',
    sliders: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    store: '<path d="M4 9.5 5.5 4h13L20 9.5M4.5 9.5V20h15V9.5M3.5 9.5h17M10 20v-5.5h4V20"/>',
    user_search: '<circle cx="9.5" cy="7.5" r="3.5"/><path d="M3 20c.4-3.7 3-6 6.5-6"/><circle cx="16.5" cy="16.5" r="3"/><path d="m18.7 18.7 2.3 2.3"/>',
    envelope: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 7 8.5 6 8.5-6"/>',
    quill: '<path d="M4 20 5 16 16 5l3 3L8 19zM14 7l3 3M14 20.5h7"/>',
    wallet: '<path d="M19 7V5.5A1.5 1.5 0 0 0 17.5 4H6a2 2 0 0 0 0 4h13.5a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H6a2 2 0 0 1-2-2V6"/><path d="M16 13.5h2"/>',
    gauge: '<path d="M3.8 18a8.5 8.5 0 1 1 16.4 0M12 16.5l4.5-5.5"/><circle cx="12" cy="16.5" r="1.2" fill="currentColor"/>',
    gamepad: '<rect x="2.5" y="7.5" width="19" height="10" rx="5"/><path d="M7 12.5h4M9 10.5v4M15.5 11.5h.01M17.5 13.5h.01"/>',
    card_stack: '<rect x="7" y="6.5" width="12.5" height="15" rx="2"/><path d="M4.5 18V5a2 2 0 0 1 2-2H15"/>',
    user_plus: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.4-3.8 3-6 6.5-6s6.1 2.2 6.5 6M19 8v6M16 11h6"/>',
    pulse: '<path d="M3 12h4l2.5-7 5 14 2.5-7h4"/>',
    profile: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="12" cy="10" r="3"/><path d="M7 17.5c.9-2.2 2.8-3.4 5-3.4s4.1 1.2 5 3.4"/>',
    whistle: '<circle cx="8.5" cy="14.5" r="5"/><path d="M12 11 21 6.5V11l-6 2.6M8.5 14.5h.01M5 6.5 7 9"/>',
    card_star: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="m12 8.3 1.3 2.6 2.9.4-2.1 2 .5 2.9-2.6-1.4-2.6 1.4.5-2.9-2.1-2 2.9-.4z"/>',
    grad_cap: '<path d="M2 9.5 12 4.5l10 5-10 5zM6 11.5v5c3.3 2.2 8.7 2.2 12 0v-5M22 9.5v5"/>',
    price_tag: '<path d="M3 12.2V4h8.2l9.8 9.8-8.2 8.2z"/><circle cx="7.5" cy="8.5" r="1.5"/>',
    renew: '<path d="M6 3h8l4 4v4M6 3v18h6M14 3v4h4"/><path d="M21 16a3.5 3.5 0 1 1-1-2.5M21 12.5V15h-2.5"/>',
  };

  // Every window type: [group, glyph]. Player-card windows are typed by the card's kind ("card:<kind>").
  const WINDOWS = {
    identity: ["team", "jersey"],
    signals: ["team", "signal"],
    morale: ["team", "heart"],
    factors: ["team", "four"],
    offense: ["team", "target_arrow"],
    defense: ["team", "shield"],
    standings: ["season", "ranked"],
    week: ["season", "calendar"],
    opponent: ["season", "versus"],
    minutes: ["season", "stopwatch"],
    development: ["season", "trend_up"],
    efficiency: ["season", "line_chart"],
    prospects: ["scouting", "magnifier"],
    "award-mvp": ["scouting", "trophy"],
    "award-dpoy": ["scouting", "medal"],
    "award-roty": ["scouting", "star"],
    staff: ["front-office", "clipboard"],
    roster: ["front-office", "group"],
    stats: ["front-office", "table"],
    contracts: ["front-office", "contract"],
    payroll: ["front-office", "banknote"],
    picks: ["front-office", "ticket"],
    "league-block": ["front-office", "globe"],
    "team-block": ["front-office", "box"],
    "team-wants": ["front-office", "bullseye"],
    "league-wire": ["league", "megaphone"],
    front: ["season", "newspaper"],
    storylines: ["league", "thread"],
    "phase-staff_retention-decision": ["required", "user_check"],
    "phase-cutdown-decision": ["required", "scissors"],
    "phase-playoffs-bracket": ["playoffs", "bracket"],
    "phase-playoffs-leaders": ["playoffs", "podium"],
    "phase-playoffs-injuries": ["playoffs", "medical"],
    "phase-draft-lottery": ["draft", "balls"],
    "phase-draft-board": ["draft", "id_card"],
    "phase-draft-order": ["draft", "numbered"],
    "phase-draft-summary": ["draft", "doc_check"],
    "phase-draft-trades": ["draft", "swap"],
    "phase-free_agency-control": ["free-agency", "sliders"],
    "phase-free_agency-market": ["free-agency", "store"],
    "phase-free_agency-offers": ["free-agency", "envelope"],
    "phase-free_agency-wire": ["free-agency", "quill"],
    "phase-free_agency-payroll": ["free-agency", "wallet"],
    "phase-free_agency-cap": ["free-agency", "gauge"],
    "phase-free_agency-checklist": ["free-agency", "checklist"],
    "phase-set_roster-checklist": ["required", "calendar_check"],
    "phase-fantasy_draft-control": ["fantasy-draft", "gamepad"],
    "phase-fantasy_draft-board": ["fantasy-draft", "card_stack"],
    "phase-fantasy_draft-roster": ["fantasy-draft", "user_plus"],
    "phase-fantasy_draft-ticker": ["fantasy-draft", "pulse"],
    "card:player": ["cards", "profile"],
    "card:coach": ["cards", "whistle"],
    "card:fantasy": ["cards", "card_star"],
    "card:prospect": ["cards", "grad_cap"],
    "card:freeAgent": ["cards", "price_tag"],
    "card:extension": ["cards", "renew"],
    // Dialogs that use a window-style title bar ("modal:<kind>").
    "modal:boxScore": ["season", "versus"],
    "modal:playoffBoxScore": ["playoffs", "versus"],
    "modal:leagueLeaders": ["league", "podium"],
    "modal:playerFinder": ["league", "user_search"],
    "modal:dashboardSettings": ["fallback", "sliders"],
    "modal:issueReport": ["fallback", "envelope"],
    "modal:photoCredits": ["fallback", "sliders"],
    "modal:champion": ["playoffs", "trophy"],
    "modal:standings": ["season", "ranked"],
  };
  const FALLBACK = ["fallback", "window"];
  const NAMES = {
    identity: "Team Identity", signals: "Team Signals", morale: "Morale", factors: "Four Factors", offense: "Offense", defense: "Defense",
    standings: "Standings", week: "Calendar", opponent: "Next Opponent", minutes: "Minutes + Availability", development: "Player Development",
    efficiency: "Weekly Efficiency", prospects: "Upcoming Prospects", "award-mvp": "MVP", "award-dpoy": "DPOY", "award-roty": "ROTY",
    staff: "Coaching Staff", roster: "Roster", stats: "Stats", contracts: "Contracts", payroll: "Four-Year Payroll Share", picks: "Draft Assets",
    "league-block": "League Block", "team-block": "Team Block", "team-wants": "Team Wants", "league-wire": "League Wire",
    "phase-staff_retention-decision": "Staff Retention", "phase-cutdown-decision": "Roster Cutdown",
    "phase-playoffs-bracket": "Playoff Bracket", "phase-playoffs-leaders": "Playoff Stats", "phase-playoffs-injuries": "Playoff Injuries",
    "phase-draft-lottery": "Draft Lottery", "phase-draft-board": "Draft Prospect Board", "phase-draft-order": "Draft Order",
    "phase-draft-summary": "Draft Summary", "phase-draft-trades": "Draft-Night Trades",
    "phase-free_agency-control": "Free Agency Controls", "phase-free_agency-market": "Free-Agent Market",
    "phase-free_agency-offers": "Live Offers", "phase-free_agency-wire": "Signing Wire",
    "phase-free_agency-payroll": "Free Agency Payroll", "phase-free_agency-cap": "Free Agency Cap Position",
    "phase-free_agency-checklist": "Offseason Checklist", "phase-set_roster-checklist": "Set The Roster",
    "phase-fantasy_draft-control": "Fantasy Draft Controls", "phase-fantasy_draft-board": "Fantasy Player Board",
    "phase-fantasy_draft-roster": "Fantasy Draft Roster", "phase-fantasy_draft-ticker": "Fantasy Draft Ticker",
    "card:player": "Player Card", "card:coach": "Coach Card", "card:fantasy": "Fantasy Player Card", "card:prospect": "Prospect Card",
    "card:freeAgent": "Free-Agent Card", "card:extension": "Contract Extension",
    "modal:boxScore": "Box Score", "modal:playoffBoxScore": "Playoff Box Score", "modal:leagueLeaders": "League Leaders",
    "modal:playerFinder": "Player Finder", "modal:dashboardSettings": "Settings", "modal:issueReport": "Report an Issue", "modal:photoCredits": "Photo Credits",
    "modal:champion": "Champion", "modal:standings": "Full Standings",
  };
  const GROUP_NAMES = {
    team: "Team & Identity", season: "Season", scouting: "Scouting & Awards", "front-office": "Front Office", league: "League Activity",
    required: "Required Decisions", playoffs: "Playoffs", draft: "Draft Room", "free-agency": "Free Agency", "fantasy-draft": "Fantasy Draft",
    cards: "Player & Coach Cards", fallback: "Any other window",
  };

  // The registry key for a window: player-card windows use their card kind.
  function typeFor(id, kind = "") {
    if (String(id).startsWith("player-card-")) return WINDOWS[`card:${kind || "player"}`] ? `card:${kind || "player"}` : "card:player";
    return WINDOWS[id] ? id : "";
  }

  function entry(id, kind = "") {
    const [group, glyph] = WINDOWS[typeFor(id, kind)] || FALLBACK;
    return {group, glyph: GLYPHS[glyph] ? glyph : "window"};
  }

  function svg(id, {kind = "", className = "window-icon"} = {}) {
    const {group, glyph} = entry(id, kind);
    const [fill, edge, ink] = GROUPS[group] || GROUPS.fallback;
    return `<svg class="${className}" data-window-icon="${glyph}" viewBox="0 0 32 32" focusable="false" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="7" fill="${fill}" stroke="${edge}"/><g transform="translate(4 4)" fill="none" stroke="${ink}" color="${ink}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${GLYPHS[glyph]}</g></svg>`;
  }

  // Everything the preview sheet needs: [registry key, name, group].
  function all() {
    return Object.keys(WINDOWS).map((key) => [key, NAMES[key] || key, WINDOWS[key][0]]).concat([["", "Any other window", "fallback"]]);
  }

  window.WindowIcons = Object.freeze({svg, entry, typeFor, all, groups: GROUP_NAMES, glyphs: Object.keys(GLYPHS)});
})();
