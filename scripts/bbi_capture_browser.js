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
    try {
    await new Promise(r => { f.onload = r; setTimeout(r, 20000); });
    const d = f.contentDocument;
    // A null document means the frame got something other than the normal page (e.g. the site's bot/rate
    // protection). Treat it as push-back: the caller backs off and eventually stops. Never work around it.
    if (!d) throw new Error('blocked_or_unreadable');
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
    return { rows, meta };
    } finally { f.remove(); }
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

  // Capture a list of profile links in batches; each batch is one downloaded JSON file of GOOD profiles only.
  // Polite fixed pace; on push-back from the site, back off exponentially and stop after maxConsecutiveFails.
  // Status lives in window.__bbiStatus so progress can be checked without returning big payloads.
  window.__bbiRun = async function ({ season, players, batchSize = 50, pauseMs = 20000, startIndex = 0, tag = '', maxConsecutiveFails = 4 }) {
    const st = window.__bbiStatus = { season, total: players.length, index: startIndex, good: 0, failed: [], batches: 0,
      running: true, started: new Date().toISOString(), consecutiveFails: 0 };
    let batch = null, batchNo = 0;
    const flush = () => {
      if (batch && batch.profiles.length) {
        download(`bbi_${season}${tag}_from${String(batch.firstIndex).padStart(3, '0')}.json`, batch);
        st.batches += 1;
      }
      batch = null;
    };
    for (let i = startIndex; i < players.length; i++) {
      if (window.__bbiStop) { flush(); st.running = false; st.stopped = true; return st; }
      if (!batch) batch = { kind: 'bbi-fanspo-profiles', season, captured_at: new Date().toISOString(), source: location.origin, firstIndex: i, profiles: [] };
      const p = players[i]; st.index = i;
      try {
        const { rows, meta } = await window.__bbiLoad(p.href);
        if (rows.length < 300) throw new Error('incomplete_rows_' + rows.length);
        const m = p.href.match(/player-profiles\/([^/]+)\/([^/]+)\/(\d+)$/);
        batch.profiles.push({ url: location.origin + p.href, name: p.name, season_slug: m && m[1], slug: m && m[2], nba_id: m && m[3], meta, rows });
        st.good += 1; st.consecutiveFails = 0;
        await sleep(pauseMs);
      } catch (e) {
        st.failed.push({ index: i, href: p.href, error: String(e).slice(0, 80) });
        st.consecutiveFails += 1;
        if (st.consecutiveFails >= maxConsecutiveFails) { flush(); st.running = false; st.halted = 'site push-back: stopped after ' + st.consecutiveFails + ' consecutive failures'; return st; }
        const backoff = Math.min(15 * 60000, 60000 * 2 ** (st.consecutiveFails - 1));
        st.backingOffUntil = new Date(Date.now() + backoff).toISOString();
        await sleep(backoff);
        i -= 1; // retry the same player once the back-off ends
      }
      if (batch && batch.profiles.length >= batchSize) flush();
    }
    flush();
    st.running = false; st.finished = new Date().toISOString();
    return st;
  };
  return 'bbi capture library loaded';
})();
