const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');

(async()=>{
  const output=path.resolve('output/trade-wants-2026-10-28/ui');fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  try {
    const page=await browser.newPage({viewport:{width:1473,height:890}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(()=>localStorage.setItem('nbaGmFirstRunTutorialCompleted','1'));
    await page.goto(process.env.WANTS_UI_URL || 'http://127.0.0.1:8783');
    await page.waitForFunction(()=>state.teams.length>0);
    await page.evaluate(async()=>{
      const result=await action('create_save',{team:'MIN',save_name:`wants-ui-${Date.now()}`,seed:17});
      state.currentSave=result.save_path;state.view='dashboard';state.dashboardTeam='';
      await refreshHome();await loadAssetsDesktop();renderDashboard();CardBoard.open('team-wants');
    });
    const card=page.locator('[data-board-window="team-wants"]');
    await card.waitFor({state:'visible'});
    await card.getByRole('button',{name:'Add',exact:true}).click();
    await page.locator('[data-want-preset]').selectOption('youth');
    await page.locator('[data-want-position="SG"]').check();
    await page.locator('[data-want-position="SF"]').check();
    await page.getByRole('button',{name:'Publish',exact:true}).click();
    await page.waitForFunction(()=>!state.modal);
    await page.evaluate(()=>CardBoard.open('team-wants'));
    await card.locator('[data-want-edit]').waitFor();
    assert.match(await card.innerText(),/Age <= 23/);
    await card.getByRole('button',{name:'Add',exact:true}).click();
    await page.locator('[data-want-preset]').selectOption('picks');
    await page.locator('[data-want-prop="protection"]').selectOption('unprotected');
    await page.getByRole('button',{name:'Publish',exact:true}).click();
    await page.waitForFunction(()=>!state.modal);
    await page.evaluate(()=>CardBoard.open('team-wants'));
    await card.locator('[data-want-edit="1"]').waitFor();
    await card.locator('[data-want-move="1"][data-step="-1"]').click();
    await page.waitForFunction(()=>state.wantsRead?.payload.entries[0]?.kind==='picks');
    await page.waitForFunction(()=>!state.busy && !state.busyDepth);
    await card.scrollIntoViewIfNeeded();
    const metrics=await card.evaluate(el=>{
      const body=el.querySelector('.assets-panel-body'),b=el.querySelector('[data-want-add]'),s=getComputedStyle(b);
      return {scrollWidth:body.scrollWidth,clientWidth:body.clientWidth,scrollHeight:body.scrollHeight,clientHeight:body.clientHeight,button:{color:s.color,border:s.border,shadow:s.boxShadow,background:s.backgroundImage}};
    });
    assert.ok(metrics.scrollWidth<=metrics.clientWidth+1,JSON.stringify(metrics));
    assert.ok(metrics.scrollHeight<=metrics.clientHeight+1,JSON.stringify(metrics));
    await page.screenshot({path:path.join(output,'desktop.png')});
    await card.getByRole('button',{name:'Add',exact:true}).hover();
    assert.equal(await card.locator('[data-want-add]').evaluate(el=>getComputedStyle(el).color),'rgb(23, 33, 42)');
    await card.locator('[data-wants-team]').selectOption('IND');
    await page.waitForFunction(()=>state.wantsRead?.team==='IND');
    assert.equal(await card.locator('[data-want-edit]').count(),0);
    await page.screenshot({path:path.join(output,'ai-wants.png')});
    await card.locator('[data-wants-team]').selectOption('MIN');
    await page.waitForFunction(()=>state.wantsRead?.team==='MIN');
    await card.locator('[data-want-edit="0"]').click();
    await page.keyboard.press('Escape');assert.equal(await page.locator('#modalRoot').isVisible(),false);
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>openWantEditor(0));
    await page.locator('[data-want-form]').waitFor();
    const modal=await page.locator('.modal-team-wants').boundingBox();
    assert.ok(modal.x>=0&&modal.x+modal.width<=391,JSON.stringify(modal));
    await page.screenshot({path:path.join(output,'mobile-editor.png')});
    await page.keyboard.press('Escape');
    const persisted=await page.evaluate(async()=>{
      const before=await action('team_wants',{...savePayload(),team:userTeam()});
      await refreshHome();
      const after=await action('team_wants',{...savePayload(),team:userTeam()});
      return {before:before.entries,after:after.entries};
    });
    assert.deepEqual(persisted.before,persisted.after);
    assert.equal(errors.length,0,errors.join('\n'));
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({metrics,persisted,errors},null,2));
    console.log(JSON.stringify({ok:true,metrics,errors,output}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
