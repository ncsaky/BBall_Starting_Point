// Basketball Index Leaderboards Tool capture (https://bball-index.shinyapps.io/SoulYOLO3Lose/, embedded at
// bball-index.com/leaderboards-tool/). Runs in that app's tab in the browser pane.
//
// The tool shows every player-season 2013-14 onward (6,804 rows as of Nov 2026) for up to 10 metrics per
// query, with each metric's value plus its percentile. This script steps through all metrics 10 at a time,
// runs the member-visible query, shows all rows, reads the rendered table's data and saves results as ordinary
// downloads (one file per `chunksPerFile` queries). Deliberate pace; stops after repeated failures.
// Personal-use archive. Import with scripts/bbi_import_leaderboard.py.
(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const download = (name, obj) => {
    const blob = new Blob([JSON.stringify(obj)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  };
  // Event-driven waiting: re-check a condition whenever DataTables or Shiny fire events, so hidden-tab timer
  // throttling (browsers slow short timers in background tabs) cannot stall the capture. One long fallback timer.
  const waitFor = (cond, timeoutMs = 600000) => new Promise((resolve, reject) => {
    const check = () => { let v; try { v = cond(); } catch (e) { v = null; } if (v) { cleanup(); resolve(v); } };
    const handler = () => check();
    const cleanup = () => { $(document).off('draw.dt init.dt xhr.dt shiny:value shiny:idle', handler); clearTimeout(timer); };
    const timer = setTimeout(() => { cleanup(); reject(new Error('timeout')); }, timeoutMs);
    $(document).on('draw.dt init.dt xhr.dt shiny:value shiny:idle', handler);
    check();
  });
  const visibleTable = () => $('.dataTables_wrapper table.dataTable').filter(':visible').first();

  const norm = s => String(s || '').replace(/ \*$/, '').replace(/\s+/g, ' ').trim().toLowerCase();

  async function runChunk(metrics, display) {
    const wanted = metrics.map(norm);
    const rendered = () => {
      const t = visibleTable(); if (!t.length) return null;
      const d = t.DataTable(); const head = new Set(d.columns().header().toArray().map(h => norm(h.innerText)));
      return wanted.every(m => head.has(m)) ? d : null;
    };
    $('#Metric')[0].selectize.setValue(metrics);
    $('#Display')[0].selectize.setValue(display);
    // Let Shiny register the new inputs before running (clicking at once can re-run the previous query).
    await waitFor(() => (window.Shiny && Shiny.shinyapp && Shiny.shinyapp.$inputValues &&
      JSON.stringify(Shiny.shinyapp.$inputValues.Metric || []) === JSON.stringify(metrics)) ? true : null, 30000).catch(() => null);
    const run = () => [...document.querySelectorAll('button')].find(b => /^Run\s*Query$/.test(b.innerText.trim())).click();
    run();
    // Re-click Run if nothing new renders (checked on Shiny/DataTables events plus a slow fallback timer).
    let clicks = 1;
    const nudge = setInterval(() => { if (!rendered() && clicks < 10) { clicks += 1; run(); } }, 60000);
    let dt;
    try { dt = await waitFor(rendered, 600000); } finally { clearInterval(nudge); }
    dt.page.len(-1).draw(false);
    await waitFor(() => { const n = dt.rows({ page: 'current' }).count(); return n > 0 && n >= dt.page.info().recordsTotal; });
    const columns = dt.columns().header().toArray().map(h => h.innerText.trim());
    const rows = dt.rows({ page: 'current' }).data().toArray();
    return { metrics, display, columns, rows, recordsTotal: dt.page.info().recordsTotal, runClicks: clicks };
  }

  window.__lbRun = async function ({ display = 'Values', chunkSize = 10, chunksPerFile = 10, pauseMs = 15000, startChunk = 0, maxConsecutiveFails = 3 } = {}) {
    const all = Object.keys($('#Metric')[0].selectize.options);
    const chunks = [];
    for (let i = 0; i < all.length; i += chunkSize) chunks.push(all.slice(i, i + chunkSize));
    const st = window.__lbStatus = { display, totalChunks: chunks.length, chunk: startChunk, good: 0, failed: [], files: 0, running: true,
      started: new Date().toISOString(), metricCount: all.length, consecutiveFails: 0 };
    let file = null;
    const flush = () => {
      if (file && file.queries.length) {
        // Keep every file in memory until it is confirmed saved: some browsers (including the app's built-in
        // pane) can silently block downloads, and data must never be discarded on a failed save.
        (window.__lbFiles = window.__lbFiles || []).push({ name: `bbi_leaderboard_${display.replace(/\W+/g, '')}_chunks${String(file.firstChunk).padStart(2, '0')}.json`, data: file, saved: false });
        download(`bbi_leaderboard_${display.replace(/\W+/g, '')}_chunks${String(file.firstChunk).padStart(2, '0')}-${String(file.firstChunk + file.queries.length - 1).padStart(2, '0')}.json`, file);
        st.files += 1;
      }
      file = null;
    };
    for (let c = startChunk; c < chunks.length; c++) {
      if (window.__lbStop) { flush(); st.running = false; st.stopped = true; return st; }
      if (!file) file = { kind: 'bbi-leaderboard', tool: location.href, captured_at: new Date().toISOString(), display, firstChunk: c, queries: [] };
      st.chunk = c;
      try {
        file.queries.push(await runChunk(chunks[c], display));
        st.good += 1; st.consecutiveFails = 0;
      } catch (e) {
        st.failed.push({ chunk: c, error: String(e).slice(0, 80) });
        st.consecutiveFails += 1;
        if (st.consecutiveFails >= maxConsecutiveFails) { flush(); st.running = false; st.halted = 'stopped after repeated failures'; return st; }
        await sleep(60000 * st.consecutiveFails);
        c -= 1;
        continue;
      }
      if (file.queries.length >= chunksPerFile) flush();
      await sleep(pauseMs);
    }
    flush();
    st.running = false; st.finished = new Date().toISOString();
    return st;
  };
  return 'leaderboard capture loaded';
})();
