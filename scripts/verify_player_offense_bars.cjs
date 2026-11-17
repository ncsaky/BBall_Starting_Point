/* Render the real player card/styles without opening or mutating a playable save. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const [phase = 'after', url = 'http://127.0.0.1:8776'] = process.argv.slice(2);
  const output = path.resolve(__dirname, '../output/player-ratings-v9-ui');
  const detail = JSON.parse(fs.readFileSync(path.join(output, 'player-card.json'), 'utf8'));
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true});
  const report = [];
  try {
    for (const [width, height] of [[1647,1000], [1440,900], [1024,768], [390,844]]) {
      const context = await browser.newContext({viewport:{width,height}});
      const page = await context.newPage();
      await page.route('**/__player-ratings-fixture',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html><head><meta charset="utf-8">${['styles','interface','production-skin','paper-fidelity','card-board','startup','tutorial','assistant-phone','trade-workspace','heatmaps'].map(name=>`<link rel="stylesheet" href="/${name}.css">`).join('')}</head><body class="unified-terminal-ui"></body></html>`}));
      await page.goto(url+'/__player-ratings-fixture');
      await page.addScriptTag({url:url+'/app.js'});
      await page.waitForFunction(() => typeof approvedPlayerCardBody === 'function');
      const fixture = structuredClone(detail);
      if (phase === 'before') for (const key of ['post_creation','assisted_finishing','screening']) delete fixture.ratings[key];
      await page.evaluate(detail => {
        const host = document.createElement('div');
        host.id = 'player-ratings-fixture';
        host.className = 'season-command-dashboard has-card-board';
        host.style.cssText = 'position:fixed;inset:0;z-index:999999;background:var(--ui-panel)';
        const scale = Math.min(1, (innerWidth-24)/1530, (innerHeight-24)/900);
        host.innerHTML = `<section class="card-board-window" style="left:12px;top:12px;width:1530px;height:900px;transform:scale(${scale});transform-origin:top left"><header class="card-board-titlebar"><strong>Player Card</strong></header><div class="card-board-body" style="width:1530px;height:876px"><div class="clipboard-player-card">${approvedPlayerCardBody(detail)}</div></div></section>`;
        document.body.append(host);
        wirePlayerCardPages(host.querySelector('.clipboard-player-card'), {page:1});
      }, fixture);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForFunction(() => [...document.querySelectorAll('#player-ratings-fixture .rating-category-art img')].every(img => img.complete));
      const metrics = await page.locator('#player-ratings-fixture').evaluate(host => {
        const details = host.querySelector('.player-card-page--details');
        const groups = details.querySelector('.approved-rating-groups');
        const rows = [...details.querySelectorAll('.approved-rating-rail > div')];
        const visible = e => { const r=e.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,left:r.left,right:r.right}; };
        return {viewport:[innerWidth,innerHeight],
          page:{width:details.clientWidth,height:details.clientHeight,scrollWidth:details.scrollWidth,scrollHeight:details.scrollHeight},
          columns:[...groups.children].map(column => ({headings:[...column.querySelectorAll('h4 > span')].map(e=>e.textContent),rows:column.querySelectorAll('.approved-rating-rail > div').length})),
          rows:rows.map(row=>{const bar=row.querySelector('i'),label=row.querySelector('span'),style=getComputedStyle(row);return {
            label:label.textContent,height:row.offsetHeight,font:getComputedStyle(label).fontSize,
            padding:style.padding,gap:style.columnGap,barWidth:bar.clientWidth,barHeight:bar.clientHeight,
            fillStyle:bar.querySelector('b')?.getAttribute('style'),fillColor:getComputedStyle(bar.querySelector('b')).backgroundColor,
            average:bar.querySelector('.rating-average-marker')?.style.left,rect:visible(row),
            overflow:label.scrollWidth-label.clientWidth};}),
          pageRect:visible(details),groupRect:visible(groups),
        };
      });
      if (phase === 'after') {
        const before = JSON.parse(fs.readFileSync(path.join(output, 'before.json'), 'utf8')).find(r => r.viewport[0] === width);
        assert.ok(metrics.page.scrollWidth <= metrics.page.width+1, 'No horizontal ratings scroll');
        assert.ok(metrics.page.scrollHeight <= metrics.page.height+1, 'No vertical ratings scroll');
        assert.deepEqual(metrics.columns.map(c=>c.rows), [8,8,11]);
        for (const row of metrics.rows) {
          const previous = before.rows.find(r => r.label === row.label) || before.rows[0];
          for (const key of ['height','font','padding','gap','barWidth','barHeight']) assert.equal(row[key], previous[key], `${row.label}: unchanged ${key}`);
          if (before.rows.some(r=>r.label===row.label)) {
            for (const key of ['fillStyle','fillColor','average']) assert.equal(row[key],previous[key],`${row.label}: unchanged ${key}`);
          }
          assert.ok(row.overflow <= 1, `${row.label}: label fits`);
          assert.ok(row.rect.bottom <= metrics.pageRect.bottom+1, `${row.label}: visible`);
          assert.ok(row.rect.top >= metrics.pageRect.top-1, `${row.label}: visible`);
        }
        assert.equal(metrics.rows.filter(r=>r.label==='Offensive rebounding').length,1);
        for (const label of ['Post creation','Assisted finishing','Screening']) assert.equal(metrics.rows.filter(r=>r.label===label).length,1);
      }
      await page.screenshot({path:path.join(output, `${phase}-${width}.png`),animations:'disabled'});
      report.push(metrics);
      await context.close();
    }
    fs.writeFileSync(path.join(output, `${phase}.json`), JSON.stringify(report,null,2));
    console.log(`${phase}: ${report.length} viewports checked`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
