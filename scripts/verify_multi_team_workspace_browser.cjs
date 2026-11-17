const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const output=path.resolve('output/trade-workspace-2026-10-24');
  const save=JSON.parse(fs.readFileSync(path.join(output,'after/report.json'),'utf8')).save;
  assert.ok(save.includes('/disposable-saves/'));
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const report={checks:[],errors:[],save};
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const page=await context.newPage();page.on('pageerror',error=>report.errors.push(String(error)));
    let mutationRequests=0;
    page.on('request',request=>{if(request.url().endsWith('/api/action')&&['evaluate_trade','apply_trade_candidate'].includes(request.postDataJSON()?.action))mutationRequests++;});
    await page.goto('http://127.0.0.1:8773');
    await page.waitForFunction(()=>typeof state!=='undefined'&&state.teams.length>1);
    await page.evaluate(async save=>{state.currentSave=save;localStorage.setItem(LAST_SAVE_KEY,save);localStorage.setItem(TUTORIAL_COMPLETED_KEY,'1');await refreshHome();await openTradeRoomModal('builder');},save);
    await page.locator('.trade-asset-list [data-asset-side]').nth(4).click();
    await page.locator('[data-trade-roster-side="to"]').click();
    await page.locator('.trade-asset-list [data-asset-side]').nth(3).click();
    await page.locator('#tradeAddTeam').selectOption('CHI');await page.locator('[data-trade-add-team]').click();
    await page.locator('[data-trade-roster-side="extra:CHI"]').waitFor();
    await page.locator('.trade-asset-list [data-asset-side]').first().click();
    assert.equal(await page.locator('[data-trade-roster-side]').count(),3);
    assert.equal(await page.locator('[data-trade-destination]').count(),3);
    await page.locator('[data-trade-destination^="TOR:"]').selectOption('CHI');
    await page.locator('[data-trade-destination^="CHI:"]').selectOption('ATL');
    const routing=await page.evaluate(()=>tradeWorkspaceParticipants().map(row=>({team:row.team,sends:row.selected.map(asset=>({id:asset.id,to:tradeAssetDestination(row.team,asset)})),receives:tradeReceivedAssets(row.team).map(asset=>asset.id)})));
    assert.ok(routing.every(row=>row.sends.length===1&&row.receives.length===1));
    assert.equal(await page.locator('#evaluateTrade').isDisabled(),true);
    await page.evaluate(async()=>{await evaluateBuiltTrade();await applyCandidate({proposal:{id:'forbidden-partial'}},'builder');});
    assert.equal(mutationRequests,0);
    await page.screenshot({path:path.join(output,'after/multi-team-package.png'),animations:'disabled'});
    report.checks.push('Three teams load real rosters, route a circular package, and cannot submit a partial bilateral trade');
    for(const [width,height] of [[1024,768],[390,844]]) {
      await page.setViewportSize({width,height});
      const overflow=await page.locator('.modal-trade-room .modal-body').evaluate(node=>node.scrollWidth-node.clientWidth);
      assert.ok(overflow<=1,`Body overflow ${overflow}`);
      await page.screenshot({path:path.join(output,`after/multi-team-${width}.png`),animations:'disabled'});
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.locator('[data-trade-insight-key="builder"][data-trade-insight-step="1"]').click();
    assert.equal(await page.locator('.trade-multi-value h4').count(),3);
    await page.locator('[data-trade-insight-key="builder"][data-trade-insight-step="1"]').click();
    assert.equal(await page.locator('.trade-payroll-frame').count(),6);
    await page.screenshot({path:path.join(output,'after/multi-team-payroll.png'),animations:'disabled'});
    await page.locator('[data-trade-insight-key="builder"][data-trade-insight-step="1"]').click();
    await page.locator('[data-trade-identity-team="extra:CHI"]').click();
    await page.waitForFunction(()=>state.tradeIdentityPreview?.status==='ready'||state.tradeIdentityPreview?.error,null,{timeout:180000});
    assert.equal(await page.evaluate(()=>tradeIdentityContext().team),'CHI');
    assert.equal(await page.locator('.trade-identity-comparison .spatial-court').count(),4);
    await page.screenshot({path:path.join(output,'after/multi-team-identity.png'),animations:'disabled'});
    report.checks.push('Third-team value, six fixed-format payroll plots, identity preview, and narrow-window table scrolling work');
    const routes=await page.evaluate(()=>JSON.stringify(state.tradeAssetRoutes));
    await page.locator('[data-trade-tab="finder"]').click();
    assert.equal(await page.evaluate(()=>state.tradeAdditionalTeams.length),0);
    await page.locator('[data-trade-tab="builder"]').click();
    assert.equal(await page.evaluate(()=>state.tradeAdditionalTeams[0]),'CHI');
    assert.equal(await page.evaluate(()=>JSON.stringify(state.tradeAssetRoutes)),routes);
    await page.locator('[data-trade-edit-package]').click();
    await page.locator('#tradeAddTeam').selectOption('DEN');await page.locator('[data-trade-add-team]').click();
    await page.locator('[data-trade-roster-side="extra:DEN"]').waitFor();
    await page.locator('.trade-asset-list [data-asset-side]').first().click();
    assert.equal(await page.locator('[data-trade-roster-side]').count(),4);
    await page.screenshot({path:path.join(output,'after/four-team-package.png'),animations:'disabled'});
    for (const team of ['BKN','DET']) {
      await page.locator('#tradeAddTeam').selectOption(team);await page.locator('[data-trade-add-team]').click();
      await page.locator(`[data-trade-roster-side="extra:${team}"]`).waitFor();
    }
    assert.equal(await page.locator('[data-trade-roster-side]').count(),6);
    assert.equal(await page.locator('[data-trade-add-team]').isDisabled(),true);
    await page.screenshot({path:path.join(output,'after/six-team-package.png'),animations:'disabled'});
    for (const team of ['BKN','DET']) await page.locator(`[data-trade-remove-team="${team}"]`).click();
    await page.locator('[data-trade-remove-team="DEN"]').click();
    await page.locator('[data-trade-remove-team="CHI"]').click();
    assert.equal(await page.locator('[data-trade-roster-side]').count(),2);
    assert.equal(await page.locator('[data-trade-destination]').count(),0);
    assert.equal(await page.evaluate(()=>state.selectedFrom.length+state.selectedTo.length),2);
    assert.equal(await page.locator('#evaluateTrade').isDisabled(),false);
    assert.equal(mutationRequests,0);
    report.checks.push('Finder roundtrip preserves the multi-team draft; four- and six-team layouts work; removing extras restores intact two-team execution controls');
    report.routing=routing;report.status='passed';assert.deepEqual(report.errors,[]);
  }catch(error){report.status='failed';report.error=String(error);report.stack=error.stack;process.exitCode=1;}
  finally{fs.writeFileSync(path.join(output,'multi-team-browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
})();
