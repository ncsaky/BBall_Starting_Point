/* Exercise the real client against isolated waiver-room responses, not user saves. */
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../src/nba_gm_data/gui');
const output = path.resolve(__dirname, '../output/waiver-market-2026-10-27/ui');
(async () => {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true});
  try {
    for (const width of [1647, 1024]) {
      const page = await browser.newPage({viewport:{width, height:900}});
      await page.route('http://fixture.test/**', route => {
        const file = new URL(route.request().url()).pathname;
        if (file === '/') return route.fulfill({contentType:'text/html', body:`<!doctype html><html><head>${['styles','interface','production-skin','paper-fidelity','card-board'].map(n=>`<link rel="stylesheet" href="/${n}.css">`).join('')}</head><body class="unified-terminal-ui"><div id="modalRoot"></div><div id="toast" hidden></div></body></html>`});
        const local = path.join(root, file);
        if(local.startsWith(root + path.sep) && fs.existsSync(local) && fs.statSync(local).isFile()) return route.fulfill({path:local});
        return route.fulfill({status:404, body:''});
      });
      await page.goto('http://fixture.test/');
      await page.addScriptTag({url:'http://fixture.test/app.js'});
      await page.evaluate(async () => {
        window.GameInterface = {modalWillRender(){}, modalDidRender(){}, previousModal(){return null;}};
        els.modalRoot = document.getElementById('modalRoot');
        els.toast = document.getElementById('toast');
        els.modalRoot.addEventListener('click', event => {
          if(event.target.closest('[data-close-modal]')) closeModal();
        });
        const room = {players:[{id:'waiver-1', player_name:'Available Veteran', clearance_date:'2027-07-04',
          contract:[{season:'2027-28', salary:6000000}], options:[{cut_player_id:'depth', cut_cost_millions:2}], claimed:false}],
          roster:[{id:'depth', name:'Depth Player', buyout:{policy:'Simplified buyout: 10% of verified unearned protected salary is surrendered only if waivers clear.',
            payout_millions:1.8, clearance_date:'2027-07-04', cap_charges:[{season:'2027-28', salary:1800000}],
            seasons:[{season:'2027-28', salary:2000000}]}}]};
        window.sent = [];
        action = async (name, payload) => {window.sent.push({name,payload}); return name === 'waiver_room' ? room : {status:'claim_submitted'};};
        refreshHome = async () => {};
        await openWaiverRoom();
      });
      await page.locator('[data-claim-waiver]').focus();
      page.once('dialog', dialog => dialog.accept());
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => window.sent.some(x=>x.name==='claim_waiver'));
      assert.equal(await page.evaluate(() => window.sent.find(x=>x.name==='claim_waiver').payload.cut_player_id), 'depth');
      await page.locator('summary').click();
      let confirmation = '';
      page.once('dialog', dialog => {confirmation = dialog.message();return dialog.accept();});
      await page.locator('[data-wire-release][data-buyout="true"]').click();
      await page.waitForFunction(() => window.sent.some(x=>x.name==='buyout_player'));
      assert.ok(confirmation.includes('10%'));
      assert.ok(confirmation.includes('2027-28'));
      assert.ok(confirmation.includes('$1.8M'));
      const metrics = await page.locator('.modal-shell').evaluate(el=>({w:el.clientWidth, scroll:el.scrollWidth,
        titlebar:!!el.querySelector('.card-board-titlebar'), close:!!el.querySelector('.card-board-close img')}));
      assert.ok(metrics.titlebar && metrics.close, 'Shared clipboard window controls');
      assert.ok(metrics.scroll <= metrics.w + 1, 'Modal contents fit');
      await page.screenshot({path:path.join(output, `waiver-${width}.png`)});
      await page.locator('[data-close-modal]').click();
      assert.equal(await page.locator('#modalRoot').isHidden(), true);
      console.log(JSON.stringify({width, ...metrics, claim:true, buyout:true, close:true}));
      await page.close();
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
