/* Use only an isolated server with an empty --save-dir. No existing saves are touched. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const [url, evidence] = process.argv.slice(2);
  assert.ok(url && evidence, 'Usage: node scripts/verify_first_hour_browser.cjs URL EVIDENCE_DIR');
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(url).hostname), 'An isolated loopback server is required');
  fs.mkdirSync(evidence, {recursive:true});
  const browser = await chromium.launch({executablePath:process.env.NBA_GM_TEST_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true});
  const report = {checks:[], page_errors:[]};
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*', route => ['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort('internetdisconnected'));
    const page = await context.newPage();
    page.on('pageerror', error => report.page_errors.push(String(error)));
    const ready = () => page.waitForFunction(() => !state.hydrating && !state.busy, null, {timeout:60000});
    const check = name => { report.checks.push(name); console.log(name); };
    await page.goto(url);
    await page.waitForFunction(() => document.querySelector('#teamSelect').options.length > 1);
    assert.equal(await page.locator('#startupSaveSelect option').evaluateAll(options => options.filter(option=>option.value).length), 0, 'Refusing to run on a server with existing saves');
    await page.waitForFunction(() => document.querySelector('#startupScreen').dataset.startupVideo === 'playing');
    const videoTime = await page.locator('video[data-startup-video]').evaluate(video => video.currentTime);
    await page.waitForFunction(time => document.querySelector('video[data-startup-video]').currentTime > time + .3, videoTime);
    check('offline startup video advances');
    await page.locator('[data-team-value="GSW"]').click();
    await page.locator('#saveName').fill('first_hour_regression');
    await page.locator('#createSave').click();
    await page.locator('#gameTutorialTitle').waitFor({state:'visible',timeout:60000});
    assert.equal(await page.locator('#app').evaluate(app => app.inert), true);
    for (let step = 0; step < 12; step++) await page.locator('[data-tutorial-action="next"]').click();
    assert.equal(await page.locator('#app').evaluate(app => app.inert), false);
    check('all 12 tutorial steps complete and unblock the game');
    await ready();

    const player = 'player_gsw-stephen-curry';
    const slider = page.locator(`[data-minute-player="${player}"]`);
    const initial = Number(await slider.inputValue());
    await slider.press('ArrowLeft');
    await page.waitForFunction(({player,target}) => rosterRows(state.data.dashboard).some(row => row.id === player && row.rotation_target_minutes === target), {player,target:initial-1}, {timeout:90000});
    await page.reload();
    await ready();
    assert.equal(await slider.inputValue(), String(initial-1));
    assert.equal(await page.evaluate(player => state.rotationLockedPlayerIds.has(player), player), true);
    const second = page.locator('[data-minute-player="player_gsw-jimmy-butler-iii"]');
    await second.focus();
    await page.keyboard.press('ArrowLeft');
    await ready();
    await page.waitForTimeout(250);
    assert.equal(await slider.inputValue(), String(initial-1));
    check('saved minute target and lock survive reload and a second player edit');
    const persisted = await second.inputValue();
    await page.route('**/api/action', route => route.request().postDataJSON()?.action === 'set_rotation_minutes'
      ? route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({ok:false,error:'Injected regression-test failure'})}) : route.continue());
    await second.focus();
    await page.keyboard.press('ArrowLeft');
    await page.waitForFunction(() => document.querySelector('#toast').textContent.includes('Minutes were not saved'));
    assert.equal(await second.inputValue(), persisted);
    assert.equal(await slider.inputValue(), String(initial-1));
    await page.unroute('**/api/action');
    check('failed autosave reports failure and restores saved targets');

    await page.locator('[data-dashboard-settings]:visible').first().click();
    await page.locator('[data-replay-tutorial]').click();
    assert.equal(await page.locator('#gameTutorialTitle').innerText(), 'Welcome to your front office');
    assert.equal(await page.locator('#modalRoot [role="dialog"]').count(), 0);
    await page.keyboard.press('Escape');
    check('Settings replays tutorial and Escape skips it');
    await page.locator('[data-board-minimize="week"]').click();
    async function openCard(id,category) {
      await page.locator('.card-board-gallery-toggle').click();
      const group = page.locator(`[data-board-gallery-group-toggle="${category}"]`);
      if(await group.getAttribute('aria-expanded') !== 'true') await group.click();
      await page.locator(`[data-board-add="${id}"]`).click();
    }
    await openCard('prospects','scouting');
    await page.locator('[data-draft-prospect-card]:visible').first().focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => state.modal?.kind), 'draftProspect');
    await page.keyboard.press('Escape');
    await page.locator('[data-season-prospect-sort]').first().focus();
    await page.keyboard.press('Enter');
    await page.locator('[data-draft-prospect-card]:visible').first().focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(() => state.modal?.kind), 'draftProspect');
    await page.keyboard.press('Escape');
    check('compact prospects open with the keyboard before and after sorting');
    await openCard('offense','team');
    const labels = await page.locator('[data-board-window="offense"] svg').evaluate(svg => {
      const box = svg.viewBox.baseVal;
      return [...svg.querySelectorAll('text')].map(text => {
        const bounds = text.getBBox();
        return {text:text.textContent,inside:bounds.x>=0 && bounds.y>=0 && bounds.x+bounds.width<=box.width && bounds.y+bounds.height<=box.height};
      });
    });
    assert.ok(labels.length === 6 && labels.every(label=>label.inside));
    report.radar_labels = labels;
    check('all six radar labels fit inside the chart viewBox');

    await page.locator('[data-trade-menu-trigger]').click();
    await page.locator('[data-trade-menu-item="finder"]').click();
    await page.locator('[data-asset-id="player_gsw-deanthony-melton"]').click();
    await page.locator('#runTrade').click();
    await page.waitForFunction(() => state.tradeSearchCompleted, null, {timeout:60000});
    report.real_trade_offer_count = await page.evaluate(() => state.tradeResults.length);
    // Force the zero-offer case independently of a randomized save's trade market.
    await page.route('**/api/action', route => route.request().postDataJSON()?.action === 'find_trade_for_assets'
      ? route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ok:true,result:{candidates:[]}})}) : route.continue());
    await page.locator('#runTrade').click();
    await page.locator('#tradeResults').getByText('No approved offers found').waitFor();
    await page.unroute('**/api/action');
    await page.locator('#clearTradeMarket').click();
    assert.ok((await page.locator('#tradeResults').innerText()).includes('No market scan yet'));
    check('real trade search completes; zero offers and cleared searches have distinct feedback');
    await page.keyboard.press('Escape');

    async function simulate(kind) {
      const before = await page.evaluate(() => state.home.save.current_date);
      await page.locator('[data-sim-menu-trigger]').click();
      await page.locator(`[data-sim-menu-item="${kind}"]`).click();
      await page.waitForFunction(before => state.home.save.current_date !== before, before, {timeout:90000});
      await ready();
    }
    await simulate('next-event');
    await simulate('week');
    report.record = await page.evaluate(() => state.home.save.user_team_record);
    assert.ok(report.record.wins + report.record.losses > 0);
    await page.locator('[data-board-minimize="week"]').click();
    await page.locator('[data-box-score]:visible').first().click();
    await page.locator('.modal-box-score').waitFor();
    await page.screenshot({path:path.join(evidence,'first-week-box-score.png')});
    check('offseason advances into the first week and played games open box scores');
    assert.deepEqual(report.page_errors, []);
    report.status = 'passed';
  } catch (error) {
    report.status = 'failed';
    report.error = String(error);
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(evidence,'report.json'), JSON.stringify(report,null,2));
    await browser.close();
    console.log(JSON.stringify(report,null,2));
  }
})();
