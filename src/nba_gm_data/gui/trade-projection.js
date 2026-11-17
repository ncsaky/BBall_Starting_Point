(function(root) {
  "use strict";
  const injured = player => {
    const status = String(player.health?.status || "").toLowerCase();
    const label = String(player.health?.label || "").toLowerCase();
    return Boolean(status && !["ok","healthy","active"].includes(status)) || Boolean(label && !["ok","healthy"].includes(label));
  };
  const overall = player => Number(player.overall ?? player.ratings?.overall ?? 50);
  function rotation(players, infer = false) {
    const available = players.filter(player => !injured(player));
    if (available.length < 5) return null;
    const ranked = [...available].sort((a,b) => (overall(b) + Number(b.mpg || 0) * .2) - (overall(a) + Number(a.mpg || 0) * .2) || String(a.id).localeCompare(String(b.id)));
    const pool = infer ? ranked.slice(0,10) : available;
    const targets = pool.map((player,index) => Math.max(0, Number(player.mpg || 0)) || (infer ? Math.max(6,34-index*3) : 0));
    const total = targets.reduce((a,b) => a+b,0);
    if (!total && !infer) return rotation(players,true);
    const desired = targets.map(value => value / total * 240);
    const minutes = pool.map(() => 0);
    const limit = infer && pool.length > 6 ? 40 : 48;
    const slots = ["PG","SG","SF","PF","C"];
    // Allocate one minute per position in turn; position preference resolves
    // competing targets without inventing a new saved rotation or team fit.
    for (let minute=0; minute<240; minute++) {
      const slot = minute % 5;
      let best = -1, score = -Infinity;
      pool.forEach((player,index) => {
        if (minutes[index] >= limit) return;
        const positions = String(player.position || "").toUpperCase().split(/[\s/,-]+/);
        const distance = Math.min(...positions.map(position => slots.indexOf(position)).filter(index => index >= 0).map(index => Math.abs(index-slot)), 2);
        const priority = desired[index] - minutes[index] - (infer ? distance * 4 : 0);
        if (priority > score) { score=priority; best=index; }
      });
      if (best < 0) return null;
      minutes[best]++;
    }
    const byId = new Map(pool.map((player,index) => [player.id,minutes[index]]));
    return players.map(player => ({...player, minutes:byId.get(player.id) || 0}));
  }
  function afterRoster(players, outgoing, incoming) {
    const removed = new Set(outgoing.filter(asset => asset.kind === "player").map(asset => asset.id));
    const byId = new Map(players.filter(player => !removed.has(player.id)).map(player => [player.id,player]));
    incoming.filter(asset => asset.kind === "player").forEach(player => byId.set(player.id,player));
    return [...byId.values()];
  }
  function combine(rows, profiles, seed) {
    const weighted = rows.filter(row => row.minutes > 0);
    if (!weighted.length || weighted.some(row => !profiles[row.id]?.shot_chart?.cells?.length || profiles[row.id].shot_chart.basis !== "projected")) return null;
    const total = weighted.reduce((sum,row) => sum+row.minutes,0);
    const first = profiles[weighted[0].id];
    const chart = first.shot_chart;
    if (weighted.some(row => profiles[row.id].shot_chart.cells.length !== chart.cells.length)) return null;
    const regions = chart.regions.map(base => {
      let share=0, efficiency=0, suppression=0;
      for (const row of weighted) {
        const region = profiles[row.id].shot_chart.regions.find(region => region.id === base.id);
        if (!region) return null;
        const weight = row.minutes / total;
        share += region.frequency * weight;
        efficiency += region.delta_pp * region.frequency * weight;
        suppression += region.suppression_delta_pp * weight;
      }
      const delta = share ? efficiency/share : 0;
      return {...base, frequency:share, delta_pp:delta, suppression_delta_pp:suppression,
        fg_pct:base.league_fg_pct == null ? null : Math.max(0,Math.min(100,base.league_fg_pct+delta))};
    });
    if (regions.some(region => region === null)) return null;
    const cells = chart.cells.map((cell,index) => [cell[0],cell[1],cell[2],
      weighted.reduce((sum,row) => sum+profiles[row.id].shot_chart.cells[index][3]*row.minutes/total,0),
      weighted.reduce((sum,row) => sum+profiles[row.id].shot_chart.cells[index][4]*row.minutes/total,0),cell[5]]);
    return {seed, zones:first.zones, shot_chart:{...chart,regions,cells,basis:"projected"}};
  }
  const api = {rotation,afterRoster,combine};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TradeProjection = api;
})(typeof window !== "undefined" ? window : globalThis);
