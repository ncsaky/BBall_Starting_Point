/* Real client and stylesheet check, with no connection to a playable save. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../src/nba_gm_data/gui');
const output=path.resolve(__dirname,'../output/contract-protection-ui');

(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const report=[];
  try {
    for(const [width,height] of [[1647,1000],[1024,768],[390,844]]) {
      const page=await browser.newPage({viewport:{width,height}});
      await page.route('http://fixture.test/**',route=>{
        const file=new URL(route.request().url()).pathname;
        if(file==='/') return route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html><head><meta charset="utf-8">${['styles','interface','production-skin','paper-fidelity','card-board'].map(n=>`<link rel="stylesheet" href="/${n}.css">`).join('')}</head><body class="unified-terminal-ui"><div id="modalRoot"></div><div id="toast" hidden></div></body></html>`});
        const local=path.join(root,file);
        if(local.startsWith(root+path.sep)&&fs.existsSync(local)&&fs.statSync(local).isFile()) return route.fulfill({path:local});
        return route.fulfill({status:404,body:''});
      });
      await page.goto('http://fixture.test/');
      await page.addScriptTag({url:'http://fixture.test/app.js'});
      await page.evaluate(()=>{
        window.GameInterface={modalWillRender(){},modalDidRender(){}};
        els.modalRoot=document.getElementById('modalRoot');els.toast=document.getElementById('toast');
        const player={id:'p',name:'Test Player',ask_millions:8,previous_mpg:20,ratings:{overall:75}};
        state.data.freeagency={candidates:[player],cap:{max_offer_aav_millions:30},cap_by_year:{}};
        state.selectedFreeAgent='p';
        state.modal={kind:'freeAgentNegotiation',title:'Negotiate With Test Player',body:freeAgentNegotiationBody(player,{ratings:{}})};
        renderModal();
        action=async(name,payload)=>{window.sent={name,payload};return {status:'blocked',reason:'Fixture only'};};
      });
      const checked=await page.locator('[data-fa-live-interest-value]').textContent();
      await page.locator('#faGuaranteed').uncheck();
      const unprotected=await page.locator('[data-fa-live-interest-value]').textContent();
      assert.ok(parseInt(unprotected)<parseInt(checked),'Security changes displayed interest');
      await page.locator('#submitFaOffer').click();
      assert.equal(await page.evaluate(()=>window.sent.payload.guaranteed),false);
      await page.locator('#faGuaranteed').focus();await page.keyboard.press('Space');
      assert.equal(await page.locator('#faGuaranteed').isChecked(),true);
      const metrics=await page.locator('.approved-ask-grid').evaluate(grid=>{
        const label=grid.querySelector('.contract-security'),checkbox=label.querySelector('input');
        return {width:innerWidth,grid:{w:grid.clientWidth,scroll:grid.scrollWidth},label:{w:label.clientWidth,scroll:label.scrollWidth},checkbox:{w:checkbox.offsetWidth,h:checkbox.offsetHeight},text:label.textContent};
      });
      console.log(JSON.stringify(metrics));
      await page.screenshot({path:path.join(output,`free-agent-${width}.png`)});
      assert.ok(metrics.label.scroll<=metrics.label.w+1,'Checkbox label fits');
      assert.ok(metrics.grid.scroll<=metrics.grid.w+1,'Offer controls fit');
      assert.ok(metrics.checkbox.w<=18&&metrics.checkbox.h<=18,'Checkbox stays checkbox-sized');
      report.push(metrics);
      await page.evaluate(()=>{
        els.modalRoot.hidden=true;
        const candidate={player_id:'p',name:'Test Player',age:27,start_season:'2027-28',safe_years:3,preferred_years:3,
          projected_aav_millions:8,max_aav_by_years:{1:30,2:30,3:30},current_contract_seasons:[],analysis:{}};
        const room={candidates:[candidate]};
        const host=document.createElement('div');host.id='extensionFixture';host.className='season-command-dashboard has-card-board';
        const scale=Math.min(1,(innerWidth-24)/1530,(innerHeight-24)/876);
        host.innerHTML=`<section class="clipboard-player-card clipboard-player-card--extension" style="position:absolute;left:12px;top:12px;width:1530px;height:876px;transform:scale(${scale});transform-origin:top left">${extensionNegotiationPage(room,'p')}</section>`;
        document.body.append(host);
        host.querySelector('.player-card-page').style.display='grid';
        window.extensionModal={kind:'contractExtension',room,selectedPlayerId:'p'};
        wireExtensionNegotiationModal(host,window.extensionModal,()=>{},()=>{});
      });
      await page.locator('[data-extension-guaranteed]').focus();await page.keyboard.press('Space');
      assert.equal(await page.evaluate(()=>window.extensionModal.draft.guaranteed),false);
      await page.locator('[data-extension-offer-form]').evaluate(form=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
      await page.waitForFunction(()=>window.sent?.name==='submit_extension_offer');
      assert.equal(await page.evaluate(()=>window.sent.payload.guaranteed),false);
      const extension=await page.locator('#extensionFixture .approved-ask-grid').evaluate(grid=>({w:grid.clientWidth,scroll:grid.scrollWidth,checkbox:grid.querySelector('[data-extension-guaranteed]').offsetWidth}));
      assert.ok(extension.scroll<=extension.w+1,'Extension controls fit');
      assert.ok(extension.checkbox<=18,'Extension checkbox stays compact');
      await page.screenshot({path:path.join(output,`extension-${width}.png`)});
      await page.close();
    }
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
    console.log('Free-agent and extension controls, keyboard, payload, interest and fit: three viewports passed.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
