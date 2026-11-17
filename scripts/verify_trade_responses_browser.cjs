const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async()=>{
  const output=path.resolve('output/trade-workspace-2026-10-24');
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const report={checks:[],errors:[],scope:'Prepared disposable phase fixtures from existing salary-application regression scenarios, not organically generated career offers.'};
  try {
    for(const [name,decision] of [['declined-fixture','reject'],['accepted-fixture','accept']]) {
      const context=await browser.newContext({viewport:{width:1440,height:1000}});
      const page=await context.newPage();page.on('pageerror',error=>report.errors.push(String(error)));
      await page.goto('http://127.0.0.1:8773');
      await page.waitForFunction(()=>typeof state!=='undefined'&&state.teams.length>1);
      const save=path.join(output,'disposable-saves',name+'.json');
      await page.evaluate(async save=>{state.currentSave=save;localStorage.setItem(LAST_SAVE_KEY,save);localStorage.setItem(TUTORIAL_COMPLETED_KEY,'1');await refreshHome();await openTradeOffersModal();},save);
      await page.locator('[data-offer-accept]').waitFor();
      const response=page.waitForResponse(r=>r.url().endsWith('/api/action')&&r.request().postDataJSON()?.action==='respond_user_trade_offer');
      await page.locator(`[data-offer-${decision==='accept'?'accept':'reject'}]`).click();
      const result=(await (await response).json()).result;
      assert.equal(result.status,decision==='accept'?'applied':'rejected');
      await page.waitForFunction(()=>!state.busy&&!state.hydrating);
      await page.locator('.trade-offers-empty').waitFor({timeout:60000});
      await page.screenshot({path:path.join(output,'after',name+'.png'),animations:'disabled'});
      if(decision==='accept') {
        const roster=await page.evaluate(async()=>action('team_assets',{...savePayload(),team:'LAC'}));
        assert.ok(roster.players.some(row=>row.name==='Jalen Pickett'));
        assert.ok(!roster.players.some(row=>row.name==='Kris Dunn'));
      }
      report.checks.push({name,status:result.status});
      await page.reload();await page.waitForFunction(()=>!!state.home&&!state.busy&&!state.hydrating,{timeout:60000});
      const pending=await page.evaluate(async()=>action('user_trade_offers',savePayload()));
      assert.equal(pending.offer_count,0);
      await context.close();
    }
    assert.deepEqual(report.errors,[]);report.status='passed';
  }catch(error){report.status='failed';report.error=String(error);report.stack=error.stack;process.exitCode=1;}
  finally{fs.writeFileSync(path.join(output,'responses.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
})();
