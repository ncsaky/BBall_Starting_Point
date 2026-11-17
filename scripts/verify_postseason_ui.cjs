const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  try {
    for (const viewport of [{width:1618,height:988}, {width:390,height:844}]) {
      const page = await browser.newPage({viewport});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(() => localStorage.setItem('nbaGmFirstRunTutorialCompleted', '1'));
      await page.goto('http://127.0.0.1:8777');
      await page.waitForSelector('#startupSaveSelect option', {state:'attached'});
      await page.click('[data-startup-pane="load"] .startup-pane-preview');
      const entry = await page.locator('#startupSaveSelect option').evaluateAll(options => options.find(o=>o.value.endsWith('/entry.json')).value);
      await page.selectOption('#startupSaveSelect', entry);
      await page.click('#startupLoadSave');
      await page.waitForSelector('.tournament-bracket', {timeout:60000});
      const frames = await page.locator('[data-board-window]:visible').evaluateAll(elements => elements.map(e=>({id:e.dataset.boardWindow, box:e.getBoundingClientRect().toJSON()})));
      assert.equal(frames.length, 1);
      assert.equal(frames[0].id, 'phase-playoffs-bracket');
      assert.equal(await page.locator('[data-playoff-sim]').count(), 0);
      assert.equal(await page.locator('.bracket-play-in').count(), 2);
      assert.equal(await page.locator('.bracket-first_round .series-card').count(), 8);
      const frame = frames[0].box;
      assert.ok(frame.x >= 0 && frame.y >= 0);
      assert.ok(frame.right <= viewport.width + 2);
      const boardTop = await page.locator('.card-board-scroll').evaluate(e=>e.getBoundingClientRect().top);
      assert.ok(Math.abs(frame.top - boardTop - 16) < 2, 'bracket should be top-aligned');
      await page.mouse.move(10, viewport.height - 40);
      await page.mouse.wheel(0, 500);
      await page.waitForTimeout(200);
      assert.ok(await page.locator('.card-board-scroll').evaluate(e=>e.scrollTop > 0), 'clipboard should scroll down');
      await page.mouse.wheel(0, -1000);
      await page.waitForTimeout(200);
      assert.equal(await page.locator('.card-board-scroll').evaluate(e=>e.scrollTop), 0);
      await page.click('[data-sim-menu-trigger]');
      const labels = await page.locator('[data-sim-menu-item]').evaluateAll(buttons=>buttons.map(button=>{
        const copy = button.cloneNode(true);
        copy.querySelectorAll('[data-key-hint]').forEach(hint=>hint.remove());
        return copy.textContent;
      }));
      assert.deepEqual(labels, ['One Game Per Series','One Full Series','Finish Playoffs']);
      await page.screenshot({path:path.join(__dirname, `../output/postseason-calendar-2026-10-24/${viewport.width > 500 ? 'desktop' : 'mobile'}-sim-menu.png`)});
      await page.click('[data-sim-menu-trigger]');
      await page.screenshot({path:path.join(__dirname, `../output/postseason-calendar-2026-10-24/${viewport.width > 500 ? 'desktop' : 'mobile'}-initial.png`)});
      const scroll = await page.locator('.phase-bracket-shell').evaluate(e=>({width:e.clientWidth, scrollWidth:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight}));
      console.log(JSON.stringify({viewport,frames,scroll,errors}));
      assert.deepEqual(errors, []);
      if (viewport.width > 500) {
        // Exercise the same S E route a player uses, but leave the entry save unplayed.
        await page.keyboard.press('s');
        await page.keyboard.press('e');
        await page.waitForSelector('[data-continue-postseason]', {timeout:60000});
        assert.match(await page.locator('.trade-deadline-prompt').innerText(), /regular season is over/i);
        await page.screenshot({path:path.join(__dirname, '../output/postseason-calendar-2026-10-24/season-end-prompt.png')});
        await page.click('[data-review-postseason]');
        assert.equal(await page.locator('[data-board-window]:visible').count(), 1);
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode=1; });
