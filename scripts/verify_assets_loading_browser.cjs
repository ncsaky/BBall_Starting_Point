/* Run only against an isolated loopback server with an empty --save-dir. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const [url,evidence] = process.argv.slice(2);
  assert.ok(url && evidence,'Usage: node scripts/verify_assets_loading_browser.cjs URL EVIDENCE_DIR');
  assert.ok(['127.0.0.1','localhost'].includes(new URL(url).hostname));
  fs.mkdirSync(evidence,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.NBA_GM_TEST_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const report={checks:[],page_errors:[]};
  let requests=0;
  const check=name=>{report.checks.push(name);console.log(name);};
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    await context.addInitScript(()=>localStorage.setItem('nbaGmFirstRunTutorialCompleted','1'));
    await context.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort('internetdisconnected'));
    const page=await context.newPage();
    page.on('pageerror',error=>report.page_errors.push(String(error)));
    page.on('request',request=>{if(request.url().endsWith('/api/action')&&request.postDataJSON()?.action==='team_assets')requests++;});
    const ready=()=>page.waitForFunction(()=>!state.hydrating&&!state.busy&&!state.assetsLoading&&document.querySelector('.card-board-canvas'),null,{timeout:60000});
    async function open(id) {
      await page.locator('.card-board-gallery-toggle').click();
      const group=page.locator('[data-board-gallery-group-toggle="front-office"]');
      if(await group.getAttribute('aria-expanded')!=='true')await group.click();
      await page.locator(`[data-board-add="${id}"]`).click();
      await ready();
    }
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelector('#teamSelect').options.length>1);
    assert.equal(await page.locator('#startupSaveSelect option').evaluateAll(options=>options.filter(o=>o.value).length),0,'Refusing to touch existing saves');
    await page.locator('[data-team-value="GSW"]').click();
    await page.locator('#saveName').fill('assets_loading_regression');
    await page.locator('#createSave').click();
    await ready();
    assert.equal(requests,0);
    await page.locator('.card-board-gallery-toggle').click();
    await page.locator('[data-board-gallery-group-toggle="front-office"]').click();
    await page.keyboard.press('Escape');
    assert.equal(requests,0);
    check('starter dashboard and gallery previews make no asset valuation requests');
    await open('roster');
    assert.equal(requests,1);
    assert.ok(await page.evaluate(()=>state.data.assetsDesktop.payload.players.length>0));
    await open('picks');
    assert.equal(requests,1);
    check('opening an asset card fetches once; a second card reuses the current payload');
    await page.locator('[data-board-minimize="roster"]').click();
    await page.locator('[data-board-minimize="picks"]').click();
    requests=0;
    await page.reload();
    await ready();
    assert.equal(requests,0);
    await page.locator('[data-board-minimize="roster"]').click();
    await ready();
    assert.equal(requests,1);
    assert.ok(await page.evaluate(()=>state.data.assetsDesktop.payload.players.length>0));
    check('saved minimized asset windows do not fetch until restored');
    requests=0;
    await page.reload();
    await ready();
    assert.equal(requests,1);
    check('a saved visible asset window fetches fresh data on resume');
    await page.locator('[data-board-minimize="roster"]').click();
    await open('team-block');
    requests=0;
    await page.route('**/api/action',route=>route.request().postDataJSON()?.action==='team_assets'
      ?route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({ok:false,error:'Injected asset read failure'})}):route.continue());
    await page.reload();
    await ready();
    assert.equal(requests,1);
    const block=page.locator('[data-board-window="team-block"]');
    assert.ok((await block.innerText()).includes('Injected asset read failure'));
    assert.ok(!(await block.innerText()).includes('Loading team block'));
    await page.unroute('**/api/action');
    await block.locator('[data-assets-retry]').click();
    await ready();
    assert.equal(requests,2);
    assert.equal(await block.locator('[data-assets-retry]').count(),0);
    assert.ok(await block.locator('[data-block-add]').count()>0);
    check('failed reads show a retry instead of an endless loading message, and retry recovers');
    await page.screenshot({path:path.join(evidence,'asset-cards.png')});
    assert.deepEqual(report.page_errors,[]);
    report.status='passed';
  } catch(error) {
    report.status='failed';report.error=String(error);process.exitCode=1;
  } finally {
    fs.writeFileSync(path.join(evidence,'report.json'),JSON.stringify(report,null,2));
    await browser.close();
  }
})();
