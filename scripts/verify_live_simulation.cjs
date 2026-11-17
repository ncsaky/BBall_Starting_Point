const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const out = path.join(__dirname,'../output/live-simulation-2026-10-24');

async function load(browser,name,viewport={width:1618,height:988}) {
  const page=await browser.newPage({viewport}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('nbaGmFirstRunTutorialCompleted','1'));
  await page.goto('http://127.0.0.1:8777');
  await page.waitForSelector('#startupSaveSelect option',{state:'attached'});
  await page.click('[data-startup-pane="load"] .startup-pane-preview');
  const value=await page.locator('#startupSaveSelect option').evaluateAll((os,name)=>os.find(o=>o.value.endsWith(`/${name}.json`)).value,name);
  await page.selectOption('#startupSaveSelect',value);
  await page.click('#startupLoadSave');
  await idle(page);
  await page.waitForSelector('.app-loading-overlay',{state:'hidden'});
  return {page,errors};
}
async function idle(page) { await page.waitForFunction(()=>state.home && !state.hydrating && !state.busy && !state.simulationRunning,{},{timeout:180000}); }
async function observe(page) {
  await page.evaluate(()=>{
    window.__frames=[];
    const original=displaySimulationProgress;
    displaySimulationProgress=async event=>{
      await original(event);
      window.__frames.push({kind:event.kind,date:event.date,game:event.game?.game_id,
        whileRunning:state.simulationRunning,dateText:document.querySelector('.season-command-date time')?.dateTime,
        calendarMonth:document.querySelector('.clipboard-calendar-head h2')?.textContent,
        bubble:!!document.querySelector('.simulation-week-cursor'),
        series:event.series_id,
        expectedScore:event.series_id ? Object.values(event.playoffs.series.find(s=>s.id===event.series_id).wins).sort() : null,
        displayedScore:event.series_id ? [...document.querySelectorAll(`[data-bracket-series="${event.series_id}"] .series-team span`)].map(e=>Number(e.textContent)).sort() : null});
    };
  });
}
async function screenshot(page,name) { await page.screenshot({path:path.join(out,`${name}.png`)}); }

(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const report={};
  try {
    const {page,errors}=await load(browser,'playoffs');
    await observe(page);
    await page.keyboard.press('s'); await page.keyboard.press('e');
    await page.waitForFunction(()=>window.__frames.some(f=>f.kind==='game') && state.simulationRunning,{},{timeout:90000});
    assert.equal(await page.locator('#appLoading').isVisible(),false);
    await screenshot(page,'live-series-update');
    await idle(page);
    report.singleGameFrames=await page.evaluate(()=>window.__frames.filter(f=>f.kind==='game'));
    assert.equal(report.singleGameFrames.length,4);
    assert.ok(report.singleGameFrames.every(f=>f.whileRunning));
    assert.ok(report.singleGameFrames.every(f=>JSON.stringify(f.expectedScore)===JSON.stringify(f.displayedScore)));
    await page.keyboard.press('s'); await page.keyboard.press('m');
    await page.waitForSelector('[data-champion-bracket]',{timeout:180000});
    await idle(page);
    await screenshot(page,'champion-trophy');
    const champion=await page.evaluate(()=>({date:state.home.save.current_date,phase:state.home.save.phase,required:state.home.save.postseason_exit_required,champion:state.data.playoffs.champion?.abbrev,progress:window.__frames.filter(f=>f.kind==='game').length}));
    assert.equal(champion.phase,'playoffs');
    assert.ok(champion.date<'2027-06-22');
    assert.equal(champion.required,true);
    await page.click('[data-champion-bracket]');
    assert.equal(await page.locator('[data-board-window="phase-playoffs-bracket"]:visible').count(),1);
    await page.reload(); await idle(page);
    assert.equal(await page.locator('#postseasonAdvance').count(),1);
    assert.equal(await page.locator('[data-board-window="phase-playoffs-bracket"]:visible').count(),1);
    await page.click('#postseasonAdvance'); await idle(page);
    assert.deepEqual(await page.locator('[data-board-window]:visible').evaluateAll(es=>es.map(e=>e.dataset.boardWindow)),['phase-draft-lottery']);
    assert.equal(await page.locator('[data-board-window="phase-draft-control"]').count(),0);
    await screenshot(page,'lottery-odds');
    await page.click('#draftRevealLottery');
    await page.waitForFunction(()=>state.lotteryRevealRunning && state.lotteryRevealCount>=3,{},{timeout:90000});
    const partial=await page.evaluate(()=>({count:state.lotteryRevealCount,picks:[...document.querySelectorAll('[data-lottery-pick][data-revealed]')].map(e=>Number(e.dataset.lotteryPick)),order:state.data.draft.lottery.reveal.map(r=>[r.pick,r.original_team.id])}));
    assert.deepEqual(partial.picks,Array.from({length:partial.count},(_,i)=>14-i));
    assert.ok(partial.count<14);
    await screenshot(page,'lottery-partial');
    await page.reload(); await idle(page);
    const resumed=await page.evaluate(()=>({count:lotteryRevealCount(),order:state.data.draft.lottery.reveal.map(r=>[r.pick,r.original_team.id])}));
    assert.deepEqual(resumed, {count:partial.count,order:partial.order});
    await page.click('#draftRevealLottery');
    await page.waitForSelector('#draftEnterNight',{timeout:45000});
    assert.equal(await page.locator('[data-lottery-pick][data-revealed]').count(),14);
    await screenshot(page,'lottery-complete');
    const fit=await page.locator('[data-board-window="phase-draft-lottery"]').evaluate(frame=>{
      const body=frame.querySelector('.card-board-body').getBoundingClientRect(),panel=frame.querySelector('.draft-lottery-card').getBoundingClientRect();
      const notice=frame.querySelector('.draft-lottery-note').getBoundingClientRect();
      const green=frame.querySelector('em.up');
      return {bodyHeight:body.height,panelHeight:panel.height,bottomWhitespace:body.bottom-notice.bottom,green:green?{color:getComputedStyle(green).color,background:getComputedStyle(green).backgroundColor}:null};
    });
    assert.ok(fit.bottomWhitespace<30);
    await page.click('#draftEnterNight'); await idle(page);
    assert.equal(await page.evaluate(()=>state.home.save.phase),'draft');
    assert.equal(await page.locator('[data-board-window="phase-draft-control"]').count(),0);
    assert.ok(await page.locator('[data-phase-command]').count()>0);
    report.playoffs={...champion,partialReveal:partial.count,lotteryFit:fit,errors};
    assert.deepEqual(errors,[]);
    await page.close();

    const regular=await load(browser,'regular');
    await regular.page.evaluate(()=>{window.CardBoard.open('week');window.CardBoard.expand('week');});
    await regular.page.waitForSelector('[data-board-window="week"] .clipboard-calendar'); await idle(regular.page);
    await observe(regular.page);
    await regular.page.keyboard.press('s'); await regular.page.keyboard.press('w');
    await regular.page.waitForFunction(()=>window.__frames.some(f=>f.date) && state.simulationRunning,{},{timeout:90000});
    assert.equal(await regular.page.locator('#appLoading').isVisible(),false);
    await screenshot(regular.page,'calendar-live');
    await idle(regular.page);
    const dates=await regular.page.evaluate(()=>[...new Set(window.__frames.filter(f=>f.date).map(f=>f.date))]);
    assert.ok(dates.length>=5);
    assert.ok(dates.some(d=>d.startsWith('2027-02')));
    await regular.page.keyboard.press('Escape');
    await regular.page.click('[data-board-expand="week"]');
    await idle(regular.page);
    await regular.page.keyboard.press('s'); await regular.page.keyboard.press('e');
    await regular.page.waitForSelector('[data-sim-through-deadline]');
    await regular.page.click('[data-sim-through-deadline]');
    await idle(regular.page);
    const bubbles=await regular.page.evaluate(()=>window.__frames.filter(f=>f.bubble).length);
    assert.ok(bubbles>0);
    report.regular={dates,bubbleFrames:bubbles,errors:regular.errors};
    assert.deepEqual(regular.errors,[]);
    await screenshot(regular.page,'calendar-compact');
    await regular.page.close();
    fs.writeFileSync(path.join(out,'browser-verification.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report,null,2));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
