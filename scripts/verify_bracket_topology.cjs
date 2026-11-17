const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const out = path.join(__dirname,'../output/playoff-bracket-flow-2026-10-24');
  fs.mkdirSync(out,{recursive:true});
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const reports = [];
  try {
    for (const width of [1618,390]) for (const saveKind of ['entry','memphis-legacy','menu-modes']) {
      const page = await browser.newPage({viewport:{width,height:988}});
      const errors = [];
      page.on('pageerror',e=>errors.push(e.message));
      await page.addInitScript(()=>localStorage.setItem('nbaGmFirstRunTutorialCompleted','1'));
      await page.goto('http://127.0.0.1:8777');
      await page.waitForSelector('#startupSaveSelect option',{state:'attached'});
      await page.click('[data-startup-pane="load"] .startup-pane-preview');
      const selected = await page.locator('#startupSaveSelect option').evaluateAll((options,kind)=>options.find(o=>o.value.split('/').at(-1).startsWith(kind)).value,saveKind);
      await page.selectOption('#startupSaveSelect',selected);
      await page.click('#startupLoadSave');
      // Completed careers hand off to draft; open the archived playoff card's
      // renderer without changing the copied save or simulating any games.
      if (saveKind === 'menu-modes') {
        await page.waitForFunction(()=>!state.hydrating && state.currentSave);
        await page.evaluate(async()=>{
          const room = await action('playoff_room', savePayload());
          document.getElementById('content').innerHTML = `<div class="seasonal-clipboard-card"><div class="playoff-command-center"><div class="phase-bracket-shell">${playoffBracket(room.series,room.champion,room.play_in)}</div></div></div>`;
        });
      }
      await page.waitForSelector('.tournament-bracket',{timeout:60000});
      await page.waitForFunction(()=>!state.hydrating && !state.busyDepth);
      await page.waitForSelector('.app-loading-overlay',{state:'hidden'});
      const result = await page.locator('.tournament-bracket').evaluate(root=>{
        const edges = [...root.querySelectorAll('path[data-to-series]')].map(p=>{
          const conf = p.closest('.bracket-conference');
          const source = p.dataset.fromSeries ? [...conf.querySelectorAll('[data-bracket-series]')].find(n=>n.dataset.bracketSeries===p.dataset.fromSeries) : conf.querySelector(`[data-play-in-stage="${p.dataset.qualifierSeed==='8'?2:0}"]`);
          const target = [...conf.querySelectorAll('[data-bracket-series]')].find(n=>n.dataset.bracketSeries===p.dataset.toSeries);
          const a = source.getBoundingClientRect(), b = target.getBoundingClientRect();
          const point = length=>{const v=p.getPointAtLength(length);return new DOMPoint(v.x,v.y).matrixTransform(p.getScreenCTM());};
          const start=point(0),end=point(p.getTotalLength());
          const west=conf.classList.contains('west');
          return {from:p.dataset.fromSeries || `play-in-${p.dataset.qualifierSeed}`,to:p.dataset.toSeries,
            sourceY:a.top+a.height/2,targetY:b.top+b.height/2,
            deviation:Math.max(Math.abs(start.x-(west?a.right:a.left)),Math.abs(start.y-(a.top+a.height/2)),Math.abs(end.x-(west?b.left:b.right)),Math.abs(end.y-(b.top+b.height/2)))};
        });
        return {edges,series:root.querySelectorAll('[data-bracket-series]').length};
      });
      assert.equal(result.series,14);
      assert.equal(result.edges.filter(e=>!e.from.startsWith('play-in')).length,12);
      assert.ok(result.edges.every(e=>e.deviation<2),JSON.stringify(result.edges.filter(e=>e.deviation>=2)));
      const groups = new Map();
      for (const edge of result.edges.filter(e=>!e.from.startsWith('play-in'))) groups.set(edge.to,[...(groups.get(edge.to)||[]),edge]);
      for (const edges of groups.values()) {
        assert.equal(edges.length,2);
        assert.ok(Math.abs((edges[0].sourceY+edges[1].sourceY)/2-edges[0].targetY)<2);
      }
      assert.deepEqual(errors,[]);
      await page.screenshot({path:path.join(out,`${saveKind}-${width}.png`)});
      reports.push({width,saveKind,edges:result.edges.length,maxDeviation:Math.max(...result.edges.map(e=>e.deviation)),browserErrors:errors});
      console.log(JSON.stringify(reports.at(-1)));
      await page.close();
    }
    fs.writeFileSync(path.join(out,'browser-verification.json'),JSON.stringify(reports,null,2));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
