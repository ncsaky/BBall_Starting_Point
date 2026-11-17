// Basketball Index (Fanspo-hosted) report-card capture, run inside a fanspo.com tab in the browser pane.
// Reads the same rendered pages a member sees, one player at a time at a deliberate pace, and saves
// batches as ordinary file downloads (the browser's local-network protection blocks posting to localhost).
// Personal-use archive; see docs/agents/tasks/bbi-capture-plan.md. Import with scripts/bbi_import_fanspo.py.
(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // Rows of one rendered report card: section, stat, value, percentile, grade, definition.
  window.__bbiExtract = function (d) {
    const leaves = [...d.querySelectorAll('*')].filter(e => e.childElementCount === 0 && /^\d+ stats?$/.test((e.textContent || '').trim()));
    const out = []; const seen = new Set();
    for (const c of leaves) {
      let box = c.parentElement;
      while (box && !box.querySelector('[class*="cols-row"]')) box = box.parentElement;
      if (!box) continue;
      const texts = [...box.querySelectorAll('*')].filter(e => e.childElementCount === 0).map(e => (e.textContent || '').trim()).filter(Boolean);
      const ci = texts.indexOf(c.textContent.trim());
      const name = ci > 0 ? texts[ci - 1] : texts[0];
      for (const r of box.querySelectorAll('[class*="cols-row"]')) {
        if (seen.has(r) || r.children.length < 2) continue;
        seen.add(r);
        const cells = [...r.children].map(x => (x.innerText || '').trim());
        if (cells[0] === 'STAT') continue;
        const def = (r.children[0].querySelector('[aria-label]') || r.children[0]).getAttribute('aria-label');
        out.push({ section: name, stat: cells[0], value: cells[1] ?? null, percentile: cells[2] ?? null, grade: cells[3] ?? null, definition: def });
      }
    }
    return out;
  };

  // Render one report card in a hidden same-origin frame, switch to "Full data", read its rows.
  window.__bbiLoad = async function (url) {
    const f = document.createElement('iframe');
    f.style.cssText = 'position:fixed;left:-6000px;top:0;width:1300px;height:3000px';
    f.src = url; document.body.appendChild(f);
    await new Promise(r => { f.onload = r; setTimeout(r, 20000); });
    const d = f.contentDocument;
    let full = null;
    for (let t = 0; t < 40 && !full; t++) { await sleep(250); full = [...d.querySelectorAll('button,[role=tab]')].find(e => e.innerText.trim() === 'Full data'); }
    if (full) full.click();
    let rows = [], last = -1;
    for (let t = 0; t < 60; t++) {
      await sleep(250);
      rows = window.__bbiExtract(d);
      if (rows.length > 300 && rows.length === last) break; // stable
      last = rows.length;
    }
    const meta = (d.body.innerText.match(/[A-Z][A-Za-z .'&-]+ · [A-Z]{1,2}(?:-[A-Z]{1,2})? · \d{4}-\d{2}/) || [''])[0];
    f.remove();
    return { rows, meta };
  };

  // Player profile links for the season currently shown in the list page's table, across all pages.
  window.__bbiCollectList = async function () {
    const links = new Map();
    for (let page = 0; page < 40; page++) {
      for (const a of document.querySelectorAll('a[href*="/bball-index/player-profiles/"]')) {
        const h = a.getAttribute('href'); if (/\/\d+$/.test(h)) links.set(h, (a.innerText || '').split('\n')[0].trim());
      }
      const next = [...document.querySelectorAll('button')].find(b => b.innerText.trim() === 'Next');
      if (!next || next.disabled || next.getAttribute('aria-disabled') === 'true') break;
      const before = links.size; next.click(); await sleep(1500);
      const firstNow = document.querySelector('a[href*="/bball-index/player-profiles/"]')?.getAttribute('href');
      if (links.has(firstNow) && links.size === before && page > 0) break;
    }
    return [...links].map(([href, name]) => ({ href, name }));
  };

  function download(name, obj) {
    const blob = new Blob([JSON.stringify(obj)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  }

  // Capture a list of profile links in batches; each batch is one downloaded JSON file.
  // Status lives in window.__bbiStatus so progress can be checked without returning big payloads.
  window.__bbiRun = async function ({ season, players, batchSize = 50, pauseMs = 2500, startBatch = 0, tag = '' }) {
    const st = window.__bbiStatus = { season, total: players.length, done: 0, failed: [], batches: 0, running: true, started: new Date().toISOString() };
    for (let b = startBatch * batchSize; b < players.length; b += batchSize) {
      const batch = { kind: 'bbi-fanspo-profiles', season, captured_at: new Date().toISOString(), source: location.origin, profiles: [] };
      for (const p of players.slice(b, b + batchSize)) {
        if (window.__bbiStop) { st.running = false; st.stopped = true; return st; }
        try {
          const { rows, meta } = await window.__bbiLoad(p.href);
          const m = p.href.match(/player-profiles\/([^/]+)\/([^/]+)\/(\d+)$/);
          batch.profiles.push({ url: location.origin + p.href, name: p.name, season_slug: m && m[1], slug: m && m[2], nba_id: m && m[3], meta, rows });
          if (rows.length < 300) st.failed.push({ href: p.href, rows: rows.length });
        } catch (e) { st.failed.push({ href: p.href, error: String(e) }); }
        st.done += 1;
        await sleep(pauseMs);
      }
      const idx = String(Math.floor(b / batchSize)).padStart(2, '0');
      download(`bbi_${season}${tag}_batch${idx}.json`, batch);
      st.batches += 1;
    }
    st.running = false; st.finished = new Date().toISOString();
    return st;
  };
  return 'bbi capture library loaded';
})();
