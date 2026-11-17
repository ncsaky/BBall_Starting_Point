const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const mode = process.argv[2] || 'after';
  const url = 'http://127.0.0.1:8773';
  const output = path.resolve('output/trade-workspace-2026-10-24', mode);
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const report = {mode, checks:[], errors:[]};
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    page.on('pageerror', error => report.errors.push(String(error)));
    await page.goto(url);
    const token = (await (await context.request.get(url+'/api/session')).json()).token;
    const headers = {'X-NBA-GM-Token':token};
    const status = await (await context.request.get(url+'/api/status', {headers})).json();
    assert.ok(JSON.stringify(status).includes('/output/trade-workspace-2026-10-24/disposable-saves'));
    await page.waitForFunction(()=>typeof state !== 'undefined' && state.teams.length > 1);
    const save = await page.evaluate(async () => {
      const result = await action('create_save', {team:'TOR',seed:84,save_name:'trade_ui_'+Date.now()});
      state.currentSave = result.save_path;
      localStorage.setItem(LAST_SAVE_KEY, state.currentSave);
      localStorage.setItem(TUTORIAL_COMPLETED_KEY, '1');
      await refreshHome();
      return state.currentSave;
    });
    assert.ok(save.includes('/disposable-saves/'));
    await page.waitForFunction(()=>!state.busy&&!state.hydrating);
    await page.evaluate(()=>openTradeRoomModal('builder'));
    await page.locator('.modal-trade-room .trade-asset-list').first().waitFor();
    await page.locator('.trade-asset-list img.trade-player-headshot').first().waitFor();
    await page.waitForFunction(()=>[...document.querySelectorAll('.trade-asset-list img.trade-player-headshot')].slice(0,5).every(img=>img.complete));
    await page.screenshot({path:path.join(output,'builder-desktop.png'),animations:'disabled'});
    if(mode === 'after') {
      const check = name => { report.checks.push(name); console.log(name); };
      const flatButtons = async () => {
        const images = await page.locator('.modal-trade-room button').evaluateAll(buttons=>buttons.filter(button=>button.getClientRects().length).map(button=>({label:button.getAttribute('aria-label')||button.textContent,image:getComputedStyle(button).backgroundImage})));
        assert.ok(images.every(button=>!button.image.includes('gradient')),JSON.stringify(images));
        assert.equal(await page.locator('.modal-trade-room > .card-board-titlebar').evaluate(node=>node.getBoundingClientRect().height),24);
      };
      await flatButtons();
      report.portraits = await page.locator('.trade-asset-list img.trade-player-headshot').evaluateAll(images=>images.slice(0,5).map(img=>({src:img.getAttribute('src'),natural:[img.naturalWidth,img.naturalHeight],size:[img.clientWidth,img.clientHeight],objectFit:getComputedStyle(img).objectFit})));
      const headings = await page.locator('.trade-asset-list thead').innerText();
      for(const label of ['Age','Height','Pos','OVR','OFF','DEF','Upside','Injury risk','Contract','Value']) assert.ok(headings.includes(label),label);
      const originalMinutes = await page.evaluate(()=>JSON.stringify(state.data.tradeUser.players.map(row=>[row.id,row.mpg])));
      await page.locator('.trade-asset-list [data-asset-side]').nth(4).click();
      assert.equal(await page.locator('.trade-asset-list input:checked').count(),1);
      await page.locator('[data-trade-roster-side="to"]').click();
      await page.locator('.trade-asset-list [data-asset-side]').nth(3).click();
      await page.locator('#evaluateTrade').click();
      await page.waitForFunction(()=>!!state.tradeCandidate&&!state.busy);
      const realCandidate = await page.evaluate(()=>state.tradeCandidate);
      report.evaluation = {legality:realCandidate.legality, decisions:realCandidate.evaluations.map(row=>({team:row.team_abbrev,accepted:row.accepted}))};
      check('Select assets from both teams and evaluate through the real app action');
      assert.equal(await page.locator('.trade-selected-packages .trade-ledger-player').count(),2);
      await page.screenshot({path:path.join(output,'builder-selected.png'),animations:'disabled'});
      await page.locator('[data-trade-insight-key="builder"][data-trade-insight-step="1"]').click();
      await page.locator('[data-trade-page="1"] .approved-trade-values').waitFor();
      await page.screenshot({path:path.join(output,'value-page.png'),animations:'disabled'});
      await page.locator('[data-trade-insight-key="builder"][data-trade-insight-step="1"]').click();
      await page.locator('[data-trade-page="2"] .approved-trade-cap').waitFor();
      const plots = await page.locator('.trade-payroll-frame').evaluateAll(frames=>frames.map(frame=>{
        const plot=frame.querySelector('.salary-horizon-chart');
        const column=plot?.querySelector('.salary-horizon-column');
        const stack=plot?.querySelector('.salary-horizon-stack');
        return {width:frame.offsetWidth,height:frame.offsetHeight,years:plot?.querySelectorAll('.salary-horizon-year').length,fillRatio:column&&stack?stack.getBoundingClientRect().width/(column.clientWidth):null};
      }));
      assert.equal(plots.length,4);
      assert.ok(plots.every(plot=>plot.width===274&&plot.height===397&&plot.years===4&&Math.abs(plot.fillRatio-.72)<.02),JSON.stringify(plots));
      report.payrollGeometry=plots;
      await flatButtons();
      await page.screenshot({path:path.join(output,'payroll-page.png'),animations:'disabled'});
      await page.locator('[data-trade-insight-key="builder"][data-trade-insight-step="1"]').click();
      await page.waitForFunction(()=>state.tradeIdentityPreview?.status==='ready'||state.tradeIdentityPreview?.error,null,{timeout:180000});
      assert.equal(await page.locator('.trade-identity-comparison .spatial-court').count(),4);
      assert.ok(await page.locator('.trade-identity-comparison .spatial-court-hex').count()>100);
      assert.equal(await page.evaluate(()=>JSON.stringify(state.data.tradeUser.players.map(row=>[row.id,row.mpg]))),originalMinutes);
      await page.screenshot({path:path.join(output,'identity-page.png'),animations:'disabled'});
      await page.locator('.trade-inferred-minutes summary').click();
      const minuteTotals = await page.locator('.trade-inferred-minutes tbody').evaluate(body=>[1,2].map(col=>[...body.rows].reduce((sum,row)=>sum+Number(row.cells[col].textContent),0)));
      assert.deepEqual(minuteTotals,[240,240]);
      check('Arrow pages retain package; value, payroll and four nonblank heatmaps; projected minutes conserve 240 without changing rotation');
      await page.evaluate(()=>{state.tradeInsightPage=0;state.tradeRosterSide='from';renderTradeRoom();});
      const id = await page.locator('.trade-asset-list [data-dashboard-player-card]').first().getAttribute('data-dashboard-player-card');
      await page.locator('.trade-asset-list [data-dashboard-player-card]').first().click();
      await page.locator('[data-player-return-trade]').last().waitFor({timeout:60000});
      await page.locator('[data-player-return-trade]').last().click();
      assert.equal(await page.evaluate(()=>state.selectedFrom.length),1);
      check('Player card opens from ledger and returns without losing the prepared package');
      for(const [width,height] of [[1440,1000],[1024,768],[390,844]]) {
        await page.setViewportSize({width,height});
        await page.evaluate(()=>{state.tradeInsightPage=0;renderTradeRoom();});
        const geometry = await page.locator('.modal-trade-room').evaluate(root=>{const r=root.getBoundingClientRect(),body=root.querySelector('.modal-body');return {x:r.x,right:r.right,bottom:r.bottom,overflow:body.scrollWidth-body.clientWidth,tableWidth:root.querySelector('.trade-ledger').getBoundingClientRect().width};});
        assert.ok(geometry.x>=0&&geometry.right<=width+1&&geometry.bottom<=height+1,JSON.stringify(geometry));
        assert.ok(geometry.overflow<=1,JSON.stringify(geometry));
        const blank = await page.locator('.modal-trade-room').evaluate(root=>root.querySelector('.modal-body').getBoundingClientRect().bottom-root.querySelector('#tradeBody').getBoundingClientRect().bottom);
        assert.ok(blank<12,`Unused body space ${blank}px`);
        await page.screenshot({path:path.join(output,`builder-${width}.png`),animations:'disabled'});
      }
      check('Desktop, small laptop and mobile keep window in bounds with locally scrollable tables');
      await page.setViewportSize({width:1440,height:1000});
      await page.evaluate(()=>{const player=state.data.tradeUser.assets.find(row=>row.kind==='player');player.health={status:'injured',label:'Out ~3g',days_left:7};renderTradeRoom();});
      assert.ok(await page.locator('.trade-ledger-player.is-injured .season-injury-status').count());
      assert.equal(await page.locator('.trade-ledger-player.is-injured .player-name-text').first().evaluate(node=>getComputedStyle(node).color),'rgb(161, 61, 67)');
      await page.screenshot({path:path.join(output,'injury-treatment.png'),animations:'disabled'});
      await page.evaluate(()=>{state.tradeCandidate={proposal:{id:'ui-illegal'},legality:{status:'illegal',issues:['Salary mismatch fixture']},evaluations:[]};renderTradeRoom();});
      assert.equal(await page.locator('#applyBuiltTrade').isDisabled(),true);
      assert.ok((await page.locator('.trade-legality-issues').innerText()).includes('Salary mismatch fixture'));
      check('Active injury has red name/cross; illegal trade explicitly displays reason and disables acceptance');
      // Candidate rendering fixture only; no fabricated offer is sent to the engine.
      await page.evaluate(candidate=>{
        state.tradeTab='finder';state.tradeResults=[candidate];state.tradeSearchCompleted=true;
        renderTradeRoom();
      },realCandidate);
      await page.locator('.trade-candidate-card .trade-ledger').first().waitFor();
      await page.screenshot({path:path.join(output,'finder-result.png'),animations:'disabled'});
      await page.locator('[data-inspect-finder]').first().click();
      assert.equal(await page.evaluate(()=>state.tradeTab),'builder');
      await page.locator('[data-back-finder]').click();
      assert.equal(await page.locator('.trade-candidate-card').count(),1);
      check('Finder result uses shared ledger and builder/back navigation preserves its result');
      await page.evaluate(candidate=>{
        state.data.dashboardOffers={offers:[candidate]};
        return openTradeOffersModal();
      },realCandidate);
      await page.locator('.modal-trade-offers .trade-ledger').first().waitFor();
      await page.locator('.incoming-offer-evaluation summary').first().click();
      await page.locator('.incoming-offer-evaluation [data-trade-insight-step="1"]').click();
      assert.equal(await page.locator('.incoming-offer-evaluation[open] .trade-candidate-finances').count(),1);
      await page.screenshot({path:path.join(output,'incoming-offer.png'),animations:'disabled'});
      await page.route('**/api/action',route=>{
        const data=route.request().postDataJSON();
        if(data?.action==='respond_user_trade_offer')return route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({ok:false,error:'Injected offline response'})});
        return route.continue();
      });
      await page.locator('[data-offer-reject]').click();
      await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Injected offline response'));
      assert.equal(await page.locator('.incoming-offer').count(),1);
      await page.unroute('**/api/action');
      check('Incoming analysis pager stays open; failed decline retains visible offer');
      await page.locator('.modal-close-icon').click();
    }
    await page.evaluate(()=>switchTradeWorkspace('finder'));
    if(mode==='before')await page.screenshot({path:path.join(output,'finder-desktop.png'),animations:'disabled'});
    report.save = save;
    report.status = 'passed';
    assert.deepEqual(report.errors, []);
  } catch (error) {
    report.status = 'failed'; report.error = String(error); report.stack = error.stack; process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
    await browser.close();
  }
})();
