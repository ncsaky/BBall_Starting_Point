/* Real Chromium interactions; run only against the disposable audit server. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const [url='http://127.0.0.1:8879',evidence='output/ui-product-audit/after']=process.argv.slice(2);
  assert.equal(new URL(url).hostname,'127.0.0.1');
  fs.mkdirSync(evidence,{recursive:true});
  const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const report={checks:[],viewports:[],pageErrors:[]};
  const check=name=>{report.checks.push(name);console.log(name);};
  const ready=p=>p.waitForFunction(()=>!state.busy&&!state.hydrating&&!!state.currentSave&&(state.data.dashboard?.rotation?.length||0)>0,null,{timeout:90000});
  const pref=p=>p.evaluate(()=>localStorage.getItem('nbaGmCardBoard:v1:'+state.currentSave));
  const shot=(p,name)=>p.screenshot({path:path.join(evidence,name+'.png'),animations:'disabled'});
  const gallery=async(p,id,category)=>{
    await p.locator('.card-board-gallery-toggle').click();
    const g=p.locator(`[data-board-gallery-group-toggle="${category}"]`);
    if(await g.getAttribute('aria-expanded')!=='true')await g.click();
    await p.locator(`[data-board-add="${id}"]`).click();
  };
  try {
    const context=await browser.newContext({viewport:{width:1440,height:900}});
    const page=await context.newPage();page.on('pageerror',e=>report.pageErrors.push(String(e)));
    await page.goto(url);
    const {token}=await (await context.request.get(url+'/api/session')).json();
    const runtime=await (await context.request.get(url+'/api/status',{headers:{'X-NBA-GM-Token':token}})).json();
    assert.ok(JSON.stringify(runtime).includes('/output/ui-product-audit/disposable-saves'),'Refusing non-audit save directory');
    await page.waitForFunction(()=>document.querySelector('#teamSelect').options.length>1);
    await page.locator('[data-team-value="GSW"]').click();
    await page.locator('#saveName').fill('UI Product Regression '+Date.now());
    await page.locator('#createSave').click();
    await page.locator('[data-tutorial-action="skip"]').waitFor({timeout:90000});
    const layout=await pref(page);
    for(let i=0;i<12;i++)await page.locator('[data-tutorial-action="next"]').click();
    assert.equal(await pref(page),layout);check('Create save and complete all tutorial steps without changing layout');
    const storage=await context.storageState();
    for(const [width,height] of [[1024,768],[1440,900],[1920,1080]]) {
      const ctx=await browser.newContext({viewport:{width,height},storageState:storage});
      const p=await ctx.newPage();p.on('pageerror',e=>report.pageErrors.push(String(e)));
      await p.goto(url);await ready(p);await p.locator('.card-board-canvas').waitFor();
      const geometry=await p.evaluate(()=>{
        const a=document.querySelector('.season-command-actions'),b=document.querySelector('.card-board-scroll'),c=document.querySelector('.card-board-canvas');
        return {width:innerWidth,height:innerHeight,rail:[a.clientWidth,a.scrollWidth],board:[b.clientWidth,b.clientHeight],canvas:[c.clientWidth,c.clientHeight],buttons:[...a.querySelectorAll('button')].filter(e=>e.getClientRects().length).map(e=>({label:e.getAttribute('aria-label')||e.textContent,x:e.getBoundingClientRect().x,right:e.getBoundingClientRect().right,bottom:e.getBoundingClientRect().bottom}))};
      });
      assert.equal(geometry.canvas[0],Math.floor(geometry.board[0]*1.3));
      assert.equal(geometry.canvas[1],Math.floor(geometry.board[1]*1.3));
      assert.ok(geometry.buttons.every(b=>b.x>=0&&b.right<=width&&b.bottom<height));
      assert.ok(geometry.rail[1]<=geometry.rail[0]+1);
      await shot(p,`workspace-${width}x${height}`);
      await p.locator('[data-dashboard-settings]').click();await p.locator('.modal-settings').waitFor();
      const saved=await pref(p);await p.locator('[data-replay-tutorial]').click();
      for(let i=0;i<6;i++)await p.locator('[data-tutorial-action="next"]').click();
      await p.keyboard.press('Escape');assert.equal(await pref(p),saved);
      await p.locator('[data-dashboard-player-finder]').click();await p.locator('.modal-shell').waitFor();
      assert.equal(await p.locator('#app').evaluate(e=>e.inert),true);
      await p.keyboard.press('Escape');assert.equal(await p.locator('#app').evaluate(e=>e.inert),false);
      await p.locator('[data-sim-menu-trigger]').click();
      assert.equal(await p.evaluate(()=>document.activeElement.dataset.simMenuItem),'next-event');
      await p.keyboard.press('ArrowDown');
      assert.equal(await p.evaluate(()=>document.activeElement.dataset.simMenuItem),'week');
      await shot(p,`toolbar-menu-${width}x${height}`);await p.keyboard.press('Escape');
      assert.equal(await p.locator('[data-sim-menu-trigger]').getAttribute('aria-expanded'),'false');
      await gallery(p,'prospects','scouting');
      await p.locator('[data-season-prospect-sort]').first().press('Enter');
      await p.locator('[data-draft-prospect-card]:visible').first().press('Enter');
      await p.locator('.modal-prospect-card').waitFor();
      await p.waitForFunction(()=>[...document.querySelectorAll('.modal-prospect-card img')].every(i=>i.complete));
      await p.locator('.modal-prospect-card').evaluate(root=>Promise.all(root.getAnimations().map(animation=>animation.finished)));
      const ratings=await p.locator('.modal-prospect-card').evaluate(root=>{
        const body=root.querySelector('.modal-body');
        return {heading:root.querySelector('.approved-player-identity-ratings > header').getBoundingClientRect().height,overflow:body.scrollWidth-body.clientWidth,
          rows:[...root.querySelectorAll('.approved-rating-rail > div')].map(e=>({height:e.getBoundingClientRect().height,font:parseFloat(getComputedStyle(e.querySelector('span')).fontSize),overflow:e.scrollWidth-e.clientWidth}))};
      });
      assert.ok(Math.abs(ratings.heading-28)<=0.1,`Ratings heading is ${ratings.heading}px; expected 28px within 0.1px`);assert.ok(ratings.rows.length>0);
      assert.ok(ratings.rows.every(r=>r.height>=24&&r.font>=11&&r.overflow<=1));assert.ok(ratings.overflow<=1);
      await shot(p,`prospect-${width}x${height}`);
      await p.keyboard.press('Tab');assert.equal(await p.evaluate(()=>!!document.activeElement.closest('#modalRoot')),true);
      await p.keyboard.press('Escape');
      await p.locator('[data-board-expand="prospects"]').press('Enter');
      await p.locator('.season-prospects-expanded [data-draft-prospect-card]').first().waitFor({timeout:60000});
      await p.locator('.season-prospects-expanded [data-draft-prospect-card]').first().press('Enter');
      await p.locator('.modal-prospect-card').waitFor();await p.keyboard.press('Escape');
      await gallery(p,'contracts','front-office');await p.waitForFunction(()=>!state.assetsLoading);await ready(p);
      await p.locator('[data-board-window="contracts"] [data-linked-sort="name"]').press('Enter');
      await p.locator('[data-asset-extension]').click();await p.locator('.modal-contract-extension').waitFor();
      const submit=await p.locator('.extension-submit').evaluate(e=>{const r=e.getBoundingClientRect(),p=e.closest('.approved-ask-offer').getBoundingClientRect();return {inside:r.top>=p.top&&r.bottom<=p.bottom,hit:e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))};});
      assert.ok(submit.inside&&submit.hit,'Submit is visibly actionable');
      await p.locator('[data-extension-years]').selectOption('2');await p.locator('[data-extension-aav]').fill('50');
      assert.deepEqual(await p.locator('[data-offer-salary]').allTextContents(),['$50.0M','$50.0M','$0.0M','$0.0M','$0.0M','$0.0M']);
      await shot(p,`extension-${width}x${height}`);await p.keyboard.press('Escape');
      report.viewports.push({...geometry,ratings,submit});await ctx.close();
    }
    check('1024×768, 1440×900, 1920×1080: visible clickable toolbar, keyboard menus, prospect rows, extension form and 130% canvas');
    await gallery(page,'contracts','front-office');await page.waitForFunction(()=>!state.assetsLoading);await ready(page);
    await page.locator('[data-asset-extension]').click();await page.locator('.modal-contract-extension').waitFor();
    await page.route('**/api/action',route=>route.request().postDataJSON()?.action==='submit_extension_offer'?route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({ok:false,error:'Injected audit failure'})}):route.continue());
    await page.locator('.extension-submit').click();await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('Injected audit failure'));
    assert.equal(await page.locator('.modal-contract-extension').count(),1);await shot(page,'extension-network-error');await page.unroute('**/api/action');
    // A real low offer exercises server rejection without signing.
    await page.locator('[data-extension-aav]').fill('1.8');await page.locator('.extension-submit').click();
    await page.locator('.extension-response.rejected').waitFor({timeout:60000});await shot(page,'extension-declined');
    await page.locator('[data-extension-aav]').fill('45.2');await page.locator('[data-extension-years]').selectOption('1');
    const response=page.waitForResponse(r=>r.url().endsWith('/api/action')&&r.request().postDataJSON()?.action==='submit_extension_offer');
    await page.locator('.extension-submit').click();const result=await (await response).json();
    assert.equal(result.result.status,'applied');report.signedOffer=result.result.offer;
    await ready(page);await page.waitForFunction(()=>!state.modal);await shot(page,'extension-signed');
    await page.reload();await ready(page);
    const salary=await page.evaluate(()=>rosterRows(state.data.dashboard).find(p=>p.id==='player_gsw-stephen-curry').salary_by_year);
    assert.equal(salary['2027-28'],45.2);assert.ok(!salary['2028-29']);report.persistedSalary=salary;
    check('Extension: sorted row opens correct player, live term/cost preview, failed request, real rejection, real signed one-year contract and reload persistence');
    await page.locator('[data-board-move="contracts"]').focus();
    const handle=await page.locator('[data-board-move="contracts"]').boundingBox();
    await page.mouse.move(handle.x+40,handle.y+12);await page.mouse.down();await page.mouse.move(handle.x+64,handle.y+36,{steps:6});await page.mouse.up();
    await page.locator('[data-board-resize="contracts"][data-board-resize-edge="right"]').focus();await page.keyboard.press('ArrowRight');
    await page.locator('[data-board-move="contracts"]').focus();await page.keyboard.press('p');await page.keyboard.press('m');
    const custom=JSON.parse(await pref(page));assert.equal(custom.cards.contracts.pinned,true);assert.equal(custom.cards.contracts.minimized,true);
    await page.reload();await ready(page);const restored=JSON.parse(await pref(page));
    for(const field of ['x','y','width','height','scale','pinned','minimized','visible','expanded'])assert.equal(restored.cards.contracts[field],custom.cards.contracts[field],field);
    await page.locator('[data-board-minimize="contracts"]').click();
    await shot(page,'custom-layout-restored');check('Pointer movement, keyboard resize/pin/minimize, reload and restore preserve customized card state');
    assert.deepEqual(report.pageErrors,[]);report.status='passed';
  }catch(error){report.status='failed';report.error=String(error);report.stack=error.stack;process.exitCode=1;}
  finally{fs.writeFileSync(path.join(evidence,'browser-regression.json'),JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify({status:report.status,error:report.error,checks:report.checks},null,2));}
})();
