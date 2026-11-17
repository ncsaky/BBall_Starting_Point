const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const mode=process.argv[2]||'after';
  const output=path.resolve('output/heatmap-audit-2026-10-24');
  fs.mkdirSync(path.join(output,mode),{recursive:true});
  const profiles=JSON.parse(fs.readFileSync(path.join(output,'profiles.json')));
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const report={mode,checks:[],errors:[],profiles:[]};
  try {
    const page=await browser.newPage({viewport:{width:1100,height:740}});
    page.on('pageerror',e=>report.errors.push(String(e)));
    await page.goto('http://127.0.0.1:8773');
    await page.waitForFunction(()=>typeof spatialHeatmapMarkup==='function');
    await page.addStyleTag({content:'.audit-frame{width:100%;min-height:0!important;padding:8px;background:#f3f5f7;color:#17212a;box-sizing:border-box}.audit-frame h2{font:600 16px Tahoma;margin:0 0 8px}.audit-frame .spatial-heatmap{height:auto!important}.audit-frame svg{height:auto!important;aspect-ratio:500/470}.audit-frame .spatial-legends{height:auto!important;min-height:42px}body{margin:0!important;padding:0!important;overflow:auto!important}'});
    for(const row of profiles) {
      await page.evaluate(row=>{document.body.innerHTML=`<main class="audit-frame approved-player-spatial"><h2>${escapeHtml(row.name)}</h2>${spatialHeatmapMarkup(row.profile,{compact:true})}</main>`;},row);
      const courts=page.locator('.spatial-court');
      assert.equal(await courts.count(),2);
      const colors=await page.locator('.spatial-court-hex').evaluateAll(nodes=>[...new Set(nodes.map(node=>node.getAttribute('fill')))]);
      const slug=row.name.replace(/[^a-z0-9]+/gi,'-').toLowerCase();
      await page.locator('.audit-frame').screenshot({path:path.join(output,mode,slug+'.png')});
      report.profiles.push({name:row.name,colors:colors.length});
      if(mode==='after') {
        assert.ok(colors.length>1,row.name+' should retain regional contrast');
        const hit=page.locator('.spatial-region-hit').first();
        await hit.focus();
        const faded=await courts.first().locator('.spatial-court-hex-region').evaluateAll(nodes=>nodes.filter(node=>Number(getComputedStyle(node).opacity)<.2).length);
        assert.ok(faded>0);
        assert.equal(await hit.evaluate(node=>getComputedStyle(node).stroke),'none');
        assert.equal(await page.locator('.spatial-court-hex[tabindex]').count(),0);
        await page.evaluate(()=>document.activeElement.blur());
        const point=await hit.evaluate((node,cells)=>{
          const id=Number(node.closest('[data-region]').dataset.region);
          const cell=cells.find(cell=>cell[2]===id&&cell[3]>.000025);
          const p=new DOMPoint(cell[0],cell[1]).matrixTransform(node.getScreenCTM());
          return {x:p.x,y:p.y};
        },row.profile.shot_chart.cells);
        await page.mouse.move(point.x,point.y);
        assert.equal(await hit.evaluate(node=>node.matches(':hover')),true);
        assert.equal(await hit.evaluate(node=>getComputedStyle(node).stroke),'none');
        await page.mouse.move(0,0);
      }
    }
    if(mode==='after') {
      for(const width of [1100,700,390]) {
        await page.setViewportSize({width,height:740});
        const overflow=await page.locator('.audit-frame').evaluate(node=>node.scrollWidth-node.clientWidth);
        assert.ok(overflow<=1,`Overflow at ${width}: ${overflow}`);
        await page.screenshot({path:path.join(output,mode,`responsive-${width}.png`)});
      }
      report.checks.push('Shared player/team renderer, region keyboard highlighting without outlines, fixed scale, responsive bounds');
      await page.setViewportSize({width:1440,height:1000});
      await page.goto('http://127.0.0.1:8773');
      await page.waitForFunction(()=>typeof state!=='undefined'&&state.teams.length>1);
      const saveDirectory=path.resolve('output/trade-workspace-2026-10-24/disposable-saves');
      const saveName=fs.readdirSync(saveDirectory).filter(name=>/^trade_ui_\d+\.json$/.test(name)).sort().at(-1);
      assert.ok(saveName,'An existing disposable UI-test save is required');
      const save=path.join(saveDirectory,saveName);
      assert.ok(save.includes('/disposable-saves/'));
      await page.evaluate(async save=>{
        state.currentSave=save;localStorage.setItem(LAST_SAVE_KEY,save);localStorage.setItem(TUTORIAL_COMPLETED_KEY,'1');
        await refreshHome();
      },save);
      await page.waitForFunction(()=>!state.busy&&!state.hydrating);
      await page.evaluate(()=>dashboardPlayerCard('player_bkn-michael-porter-jr'));
      report.integration=await page.evaluate(()=>({view:state.view,detailBasis:state.playerCardDetails['player_bkn-michael-porter-jr']?.spatial_profile?.shot_chart?.basis,cards:document.querySelectorAll('.clipboard-player-card').length,courts:document.querySelectorAll('.clipboard-player-card .spatial-court').length,empty:[...document.querySelectorAll('.clipboard-player-card .spatial-heatmap-empty')].map(node=>node.textContent),toast:els.toast.textContent}));
      console.log('Actual card:',JSON.stringify(report.integration));
      const card=page.locator('.clipboard-player-card').last();
      await card.locator('.spatial-court').first().waitFor();
      assert.equal(await card.locator('.spatial-key-stop').count(),10);
      const bounds=await card.locator('.spatial-key-stop em').evaluateAll(nodes=>nodes.map(node=>{
        const a=node.getBoundingClientRect(),b=node.closest('.spatial-legends').getBoundingClientRect();
        return a.left>=b.left-1&&a.right<=b.right+1&&a.bottom<=b.bottom+1;
      }));
      assert.ok(bounds.every(Boolean),'Player numeric legend must fit');
      await card.screenshot({path:path.join(output,mode,'actual-player-card.png')});
      await page.evaluate(()=>window.CardBoard.open('identity'));
      const identity=page.locator('[data-board-window="identity"]');
      await identity.locator('.spatial-court').first().waitFor();
      assert.equal(await identity.locator('.spatial-key-stop').count(),10);
      await identity.screenshot({path:path.join(output,mode,'actual-team-card.png')});
      report.checks.push('Actual player and Team Identity cards load existing disposable save profiles; numeric legends fit the player card');
    }
    assert.deepEqual(report.errors,[]);report.status='passed';
  } catch(error) {report.status='failed';report.error=String(error);report.stack=error.stack;process.exitCode=1;}
  finally {fs.writeFileSync(path.join(output,mode,'browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
})();
