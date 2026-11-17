const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const out=path.join(__dirname,'../output/trade-pick-terms-2026-10-25');
async function idle(page){await page.waitForFunction(()=>state.home&&!state.hydrating&&!state.busy,{},{timeout:180000});}
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const errors=[],report={};
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(()=>localStorage.setItem('nbaGmFirstRunTutorialCompleted','1'));
    await page.goto('http://127.0.0.1:8777');
    await page.waitForSelector('#startupSaveSelect option',{state:'attached'});
    await page.click('[data-startup-pane="load"] .startup-pane-preview');
    const value=await page.locator('#startupSaveSelect option').evaluateAll(es=>es.find(e=>e.value.endsWith('/browser.json')).value);
    await page.selectOption('#startupSaveSelect',value);await page.click('#startupLoadSave');await idle(page);
    await page.evaluate(()=>openTradeRoomModal('builder'));await idle(page);
    if(await page.locator('#tradePartner').inputValue()!=='ATL'){await page.selectOption('#tradePartner','ATL');await idle(page);}
    const ids=await page.evaluate(()=>{
      const picks=state.data.tradeUser.picks.filter(p=>p.terms_editable&&Number(p.round)===2);
      const a=picks.find(p=>picks.some(f=>Number(f.season)>Number(p.season)));
      return {primary:a.id,fallback:picks.find(p=>Number(p.season)>Number(a.season)).id};
    });
    await page.selectOption('[data-asset-filter-side="from"]','picks');
    await page.locator(`[data-asset-side="from"][data-asset-id="${ids.primary}"]`).check();
    await page.click('[data-pick-add]');
    assert.equal(await page.locator('#evaluateTrade').isDisabled(),true);
    await page.selectOption('[data-pick-field="through"]','35');
    await page.selectOption('[data-pick-field="fallback"]',ids.fallback);
    assert.equal(await page.locator('#evaluateTrade').isDisabled(),false);
    assert.equal(await page.locator('.trade-pick-terms input:not([type=checkbox])').count(),0);
    await page.click('#evaluateTrade');await idle(page);
    const protection=await page.evaluate(()=>state.tradeCandidate.pick_obligation_terms[0]);
    assert.deepEqual(protection.protected_range,{from:31,through:35});
    assert.deepEqual(protection.fallback_pick_ids,[ids.fallback]);
    await page.locator('.trade-pick-terms').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(out,'protected-desktop.png')});
    report.button=await page.locator('[data-pick-add]').evaluate(b=>({background:getComputedStyle(b).backgroundImage,shadow:getComputedStyle(b).boxShadow}));
    assert.equal(report.button.background,'none');
    await page.locator('[data-pick-field="enabled"]').uncheck();
    assert.equal(await page.evaluate(()=>tradePickRulesRequest().length),0);
    assert.equal(await page.evaluate(()=>state.tradeCandidate),null);
    await page.locator('[data-pick-field="enabled"]').check();
    await page.click('[data-trade-tab="finder"]');await idle(page);
    assert.equal(await page.locator('[data-pick-rule]').count(),1);
    await page.selectOption('#tradeFinderTeam','ATL');await idle(page);
    await page.selectOption('[data-pick-field="type"]','pick_swap');
    const other=await page.locator('[data-pick-field="other_pick_id"] option').evaluateAll(es=>es.find(e=>e.value)?.value);
    assert.ok(other);await page.selectOption('[data-pick-field="other_pick_id"]',other);
    assert.equal(await page.locator('#runTrade').isDisabled(),false);
    await page.locator('.trade-pick-terms').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(out,'swap-finder-desktop.png')});
    // A real evaluated offer is seeded into the result list to exercise the
    // inspect/edit handoff independently of whether the AI search returns one.
    await page.evaluate(async()=>{
      const candidate=await action('evaluate_trade',{...savePayload(),from_team:userTeam(),to_team:'ATL',from_assets:state.selectedFrom.map(assetSpec),to_assets:[],pick_rules:tradePickRulesRequest(),seed:7});
      state.tradeResults=[candidate];state.tradeSearchCompleted=true;renderTradeRoom();
    });await idle(page);
    await page.click('[data-inspect-finder="0"]');await idle(page);
    report.restored=await page.evaluate(()=>({tab:state.tradeTab,rules:tradePickRulesRequest(),assets:state.selectedFrom.map(assetSpec)}));
    assert.equal(report.restored.tab,'builder');assert.equal(report.restored.rules[0].type,'pick_swap');
    assert.equal(report.restored.rules[0].other_pick_id,other);
    assert.equal(report.restored.assets[0].kind,'pick');assert.equal(report.restored.assets[0].value,ids.primary);
    const second=await page.evaluate(primary=>state.data.tradeUser.assets.find(a=>a.kind==='pick'&&a.terms_editable&&Number(a.round)===2&&a.id!==primary&&a.season==='2029')?.id,ids.primary);
    assert.ok(second);
    await page.locator(`[data-asset-side="from"][data-asset-id="${second}"]`).check();
    await page.click('[data-pick-add]');
    assert.equal(await page.locator('[data-pick-rule]').count(),2);
    await page.locator('[data-pick-rule]').nth(1).locator('[data-pick-field="fallback"]').selectOption(ids.fallback);
    assert.equal(await page.evaluate(()=>tradePickRuleErrors().length),0);
    assert.equal(await page.evaluate(()=>tradePickRulesRequest().length),2);
    await page.locator('[data-pick-rule]').nth(1).locator('[data-pick-field="enabled"]').uncheck();
    assert.equal(await page.evaluate(()=>tradePickRulesRequest().length),1);
    await page.locator('[data-pick-rule]').nth(1).locator('[data-pick-remove]').click();
    await page.locator(`[data-asset-side="from"][data-asset-id="${second}"]`).uncheck();
    report.multipleConditions=true;
    await page.setViewportSize({width:390,height:844});
    await page.locator('.trade-pick-terms').scrollIntoViewIfNeeded();
    report.mobile=await page.locator('.trade-pick-rule-fields').evaluate(row=>{
      const r=row.getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth,
        controls:[...row.querySelectorAll('select')].map(e=>({left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right}))};
    });
    assert.ok(report.mobile.controls.every(r=>r.left>=0&&r.right<=report.mobile.width));
    await page.screenshot({path:path.join(out,'swap-mobile.png')});
    await page.locator('.trade-pick-terms').screenshot({path:path.join(out,'swap-mobile-editor.png')});
    assert.deepEqual(errors,[]);report.errors=errors;
    fs.writeFileSync(path.join(out,'browser-verification.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
