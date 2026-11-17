const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

(async()=>{
  const output=path.resolve('output/multi-team-2026-10-28');
  const save=path.resolve(process.argv[2] || path.join(output,'disposable-saves/builder-verified.json'));
  assert.ok(save.startsWith(path.join(output,'disposable-saves/')));
  const evidence=JSON.parse(fs.readFileSync(path.join(output,'deadline17-final-probe.json'),'utf8'));
  const candidate=evidence.settlements[0].candidate;
  const before=JSON.parse(fs.readFileSync(save,'utf8'));
  assert.equal(before.meta.user_team_id,'team_bos');
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const report={errors:[],checks:[]};
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const page=await context.newPage();page.on('pageerror',e=>report.errors.push(String(e.stack || e)));
    await page.goto('http://127.0.0.1:8780/');
    await page.waitForFunction(()=>typeof state!=='undefined'&&state.teams.length>1&&!state.busy&&!state.hydrating&&document.getElementById('appLoading').hidden);
    await page.evaluate(async ({save,candidate})=>{
      state.currentSave=save;localStorage.setItem(LAST_SAVE_KEY,save);localStorage.setItem(TUTORIAL_COMPLETED_KEY,'1');
      await refreshHome();await openTradeRoomModal('builder');
      state.tradePartner='ATL';await loadTradeRoomAssets();await addTradeParticipant('CHI');
      for(const row of tradeWorkspaceParticipants()) {
        const outgoing=candidate.proposal.transfers.filter(t=>teamLabel(t.from_team_id)===row.team).flatMap(t=>t.assets);
        const selected=hydrateTradeSelection(outgoing,row.payload);
        if(row.side==='from')state.selectedFrom=selected;
        else if(row.side==='to')state.selectedTo=selected;
        else state.tradeExtraSelections[row.team]=selected;
        for(const leg of candidate.proposal.transfers.filter(t=>teamLabel(t.from_team_id)===row.team))
          for(const asset of leg.assets)state.tradeAssetRoutes[tradeRouteKey(row.team,asset)]=teamLabel(leg.to_team_id);
      }
      state.tradeRosterSide='from';renderTradeRoom();
    },{save,candidate});
    await page.locator('#evaluateTrade').click();
    await page.waitForFunction(()=>state.tradeCandidate?.proposal?.transfers&&!state.busy,null,{timeout:120000});
    const evaluated=await page.evaluate(()=>state.tradeCandidate);
    assert.equal(evaluated.evaluations.length,3);assert.equal(evaluated.legality.status,'legal');
    assert.equal(Object.keys(evaluated.team_finances).length,3);
    assert.equal(await page.locator('#applyBuiltTrade').isDisabled(),false);
    report.checks.push('Real three-team evaluation and all three payroll projections');
    report.workspace=await page.evaluate(()=>({display:getComputedStyle(document.querySelector('.trade-builder-layout')).display,
      save:state.currentSave,user:userTeam(),
      styles:[...document.styleSheets].map(s=>{try{return {href:s.href,disabled:s.disabled,rules:[...s.cssRules].filter(r=>r.selectorText?.includes('trade-builder-layout')).map(r=>({selector:r.selectorText,display:r.style?.display,matched:document.querySelector('.trade-builder-layout').matches(r.selectorText)}))};}catch(e){return {href:s.href,error:String(e)};}})}));
    await page.screenshot({path:path.join(output,'builder-desktop.png'),animations:'disabled'});
    await page.locator('[data-trade-insight-key="builder"][data-trade-insight-step="1"]').click();
    assert.equal(await page.locator('.trade-team-decisions .trade-evaluation-panel').count(),3);
    await page.screenshot({path:path.join(output,'three-team-decisions.png'),animations:'disabled'});
    for(const [width,height] of [[1024,768],[390,844]]) {
      await page.setViewportSize({width,height});
      const overflow=await page.locator('.modal-trade-room .modal-body').evaluate(n=>n.scrollWidth-n.clientWidth);
      await page.screenshot({path:path.join(output,`builder-${width}.png`),animations:'disabled'});
      assert.ok(overflow<=1,`Modal overflow ${overflow}`);
    }
    await page.setViewportSize({width:1440,height:1000});
    const response=page.waitForResponse(r=>r.url().endsWith('/api/action')&&r.request().postDataJSON()?.action==='apply_trade_candidate');
    await page.locator('#applyBuiltTrade').click();
    const applied=await (await response).json(), result=applied.result || applied;
    assert.equal(result.status,'applied',JSON.stringify(applied));
    await page.waitForFunction(()=>!state.busy&&!state.tradeCandidate,null,{timeout:120000});
    const after=JSON.parse(fs.readFileSync(save,'utf8'));
    for(const leg of evaluated.proposal.transfers)for(const asset of leg.assets)
      assert.equal(after[asset.kind==='player'?'roster_overrides':'draft_pick_overrides'][asset.id],leg.to_team_id);
    assert.equal(after.transaction_logs.filter(r=>r.proposal_id===result.result.transaction_log.proposal_id).length,1);
    report.checks.push('Explicit user acceptance commits every routed asset in one durable transaction');
    assert.deepEqual(report.errors,[]);report.status='passed';
  }catch(e){report.status='failed';report.error=String(e);report.stack=e.stack;process.exitCode=1;}
  finally {fs.writeFileSync(path.join(output,'browser.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
})();
