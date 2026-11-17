/* Run against an isolated loopback server with an empty --save-dir. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const [url,evidence] = process.argv.slice(2);
  assert.ok(url && evidence,'Usage: node scripts/verify_starter_workspace_browser.cjs URL EVIDENCE_DIR');
  assert.ok(['127.0.0.1','localhost'].includes(new URL(url).hostname));
  fs.mkdirSync(evidence,{recursive:true});
  const browser = await chromium.launch({executablePath:process.env.NBA_GM_TEST_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const report = {checks:[],viewports:[],page_errors:[]};
  const ready = page => page.waitForFunction(()=>!state.hydrating && !state.busy && document.querySelector('.card-board-canvas'),null,{timeout:60000});
  const preference = page => page.evaluate(()=>localStorage.getItem('nbaGmCardBoard:v1:'+state.currentSave));
  const check = name => {report.checks.push(name);console.log(name);};
  async function context(viewport,skipTutorial=false) {
    const ctx = await browser.newContext({viewport});
    await ctx.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort('internetdisconnected'));
    if(skipTutorial) await ctx.addInitScript(()=>localStorage.setItem('nbaGmFirstRunTutorialCompleted','1'));
    const page = await ctx.newPage();
    page.on('pageerror',error=>report.page_errors.push(String(error)));
    await page.goto(url);
    await page.waitForFunction(()=>document.querySelector('#teamSelect').options.length>1);
    return {ctx,page};
  }
  async function assertWorkspace(page) {
    const snapshot = await page.evaluate(()=> {
      const board=document.querySelector('.card-board-scroll'),canvas=board.querySelector('.card-board-canvas');
      const cards=[...board.querySelectorAll('[data-board-window]:not([hidden])')].map(frame=>({id:frame.dataset.boardWindow,x:frame.offsetLeft,y:frame.offsetTop,width:frame.offsetWidth,height:frame.offsetHeight}));
      return {width:canvas.offsetWidth,height:canvas.offsetHeight,viewport:[board.clientWidth,board.clientHeight],cards,prefs:JSON.parse(localStorage.getItem('nbaGmCardBoard:v1:'+state.currentSave)).cards};
    });
    assert.equal(snapshot.width,Math.floor(snapshot.viewport[0]*1.3));
    assert.equal(snapshot.height,Math.floor(snapshot.viewport[1]*1.3));
    assert.ok(snapshot.cards.length>=3 && snapshot.cards.length<=5);
    for(const card of snapshot.cards) {
      assert.ok(card.x>=0 && card.y>=0 && card.x+card.width<=snapshot.width-11 && card.y+card.height<=snapshot.height-11,card.id+' outside canvas');
      assert.equal(snapshot.prefs[card.id].scale,1,card.id+' text was scaled');
      for(const other of snapshot.cards) if(card!==other) {
        assert.ok(card.x+card.width<=other.x || other.x+other.width<=card.x || card.y+card.height<=other.y || other.y+other.height<=card.y,card.id+' overlaps '+other.id);
      }
    }
    assert.equal(snapshot.prefs.minutes.visible,true);
    assert.equal(snapshot.prefs.week.visible,true);
    assert.equal(snapshot.prefs.week.expanded,true);
    assert.equal(snapshot.prefs.prospects.visible,false);
    assert.equal(snapshot.prefs.staff.visible,false);
    assert.equal(snapshot.prefs.efficiency.visible,false);
    assert.equal(await page.locator('.season-minute-row > button').first().evaluate(e=>getComputedStyle(e).fontSize),'11px');
    return snapshot;
  }
  try {
    const initial=await context({width:1440,height:1000});
    const page=initial.page;
    assert.equal(await page.locator('#startupSaveSelect option').evaluateAll(options=>options.filter(option=>option.value).length),0,'Refusing to run on a server with existing saves');
    await page.locator('[data-team-value="GSW"]').click();
    await page.locator('#saveName').fill('starter_workspace_regression');
    await page.locator('#createSave').click();
    await page.locator('#gameTutorialTitle').waitFor({state:'visible',timeout:60000});
    await ready(page);
    const baseline=await preference(page);
    const steps=[null,null,'minutes','minutes','signals','development','staff','week','efficiency',null,null,null];
    for(const id of steps) {
      if(id) assert.equal(await page.locator(`[data-board-window="${id}"]`).isVisible(),true,id+' missing from tutorial');
      assert.equal(await preference(page),baseline,'tutorial changed saved layout');
      await page.locator('[data-tutorial-action="next"]').click();
    }
    assert.equal(await preference(page),baseline);
    await assertWorkspace(page);
    check('all tutorial targets are shown temporarily; finishing restores the starter workspace');

    await page.locator('[data-dashboard-settings]:visible').first().click();
    await page.locator('[data-replay-tutorial]').click();
    for(let i=0;i<6;i++) await page.locator('[data-tutorial-action="next"]').click();
    assert.equal(await page.locator('[data-board-window="staff"]').isVisible(),true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('[data-board-window="staff"]').isVisible(),false);
    assert.equal(await preference(page),baseline);
    assert.equal(await page.locator('#app').evaluate(e=>e.inert),false);
    check('Escape skips a replay without leaving temporary cards or changing preferences');

    for(const [width,height] of [[1024,768],[1280,800],[1440,1000],[1920,1080]]) {
      const current=await context({width,height},true);
      await current.page.getByRole('button',{name:'Enter Save',exact:true}).click();
      await ready(current.page);
      const snapshot=await assertWorkspace(current.page);
      await current.page.locator('[data-board-snap]').click();
      assert.equal(await current.page.locator('.card-board-status').innerText(),'Cards snapped into a compact layout');
      await assertWorkspace(current.page);
      await current.page.screenshot({path:path.join(evidence,`workspace-${width}x${height}.png`)});
      report.viewports.push({width,height,visible:snapshot.cards.map(card=>card.id),calendar_minimized:snapshot.prefs.week.minimized});
      await current.ctx.close();
    }
    check('four screen sizes have non-overlapping core cards, readable text, fixed extent, and working Snap');

    const title=page.locator('[data-board-move="minutes"]');
    await title.focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowDown');
    await page.locator('[data-board-resize="minutes"][data-board-resize-edge="right"]').focus();
    await page.keyboard.press('ArrowRight');
    await title.focus();
    await page.keyboard.press('p');
    await page.keyboard.press('m');
    const custom=JSON.parse(await preference(page));
    assert.equal(custom.cards.minutes.pinned,true);
    assert.equal(custom.cards.minutes.minimized,true);
    assert.ok(custom.cards.minutes.scale>1);
    await page.reload();
    await ready(page);
    const restored=JSON.parse(await preference(page));
    for(const field of ['x','y','width','height','scale','pinned','minimized','visible','expanded']) assert.equal(restored.cards.minutes[field],custom.cards.minutes[field],field+' was overwritten');
    assert.equal(restored.cards.week.visible,custom.cards.week.visible);
    assert.equal(restored.cards.staff.visible,false);
    check('moved, resized, pinned and minimized preferences survive reload unchanged');

    await page.locator('.card-board-gallery-toggle').click();
    await page.locator('[data-board-gallery-group-toggle="front-office"]').click();
    await page.locator('[data-board-add="staff"]').click();
    assert.equal(await page.locator('[data-board-window="staff"]').isVisible(),true);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('[data-board-window="staff"]').isVisible(),false);
    check('gallery-only cards can be opened and closed normally');
    assert.deepEqual(report.page_errors,[]);
    report.status='passed';
  } catch(error) {
    report.status='failed';report.error=String(error);process.exitCode=1;
  } finally {
    fs.writeFileSync(path.join(evidence,'report.json'),JSON.stringify(report,null,2));
    await browser.close();
  }
})();
