const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
  const out=path.resolve('output/elite-market-2026-10-29/ui');fs.mkdirSync(out,{recursive:true});
  const candidate=JSON.parse(fs.readFileSync(path.join(out,'../ui-candidate.json'),'utf8'));
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  try{
    const page=await browser.newPage({viewport:{width:1473,height:890}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:8784');
    await page.waitForFunction(()=>typeof state!=='undefined'&&state.teams.length>0);
    await page.evaluate(candidate=>{
      state.modal={kind:'tradeOffers',title:'AI Trade Offers To You',subtitle:'Trade analysis verification',
        offers:[candidate],body:tradeOffersModalBody([candidate])};
      state.tradeOfferPages={};renderModal();
    },candidate);
    await page.locator('.incoming-offer-evaluation summary').first().click();
    await page.locator('.trade-evaluation-panel').first().waitFor();
    assert.match(await page.locator('.trade-evaluation-panel').last().innerText(),/Would decline/i);
    assert.match(await page.locator('.trade-evaluation-panel').last().innerText(),/Premium player return/);
    await page.screenshot({path:path.join(out,'desktop.png')});
    await page.locator('.approved-trade-values > .trade-value-help').first().locator('summary').click();
    assert.match(await page.locator('.approved-trade-values').innerText(),/not OVR or dollars/);
    await page.locator('.approved-trade-values').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(out,'explanation.png')});
    await page.setViewportSize({width:390,height:844});
    const geometry=await page.locator('.modal-trade-offers').evaluate(el=>({width:el.clientWidth,scroll:el.scrollWidth}));
    assert.ok(geometry.scroll<=geometry.width+1,JSON.stringify(geometry));
    await page.screenshot({path:path.join(out,'mobile.png')});
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#modalRoot').isVisible(),false);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({errors,geometry,checks:['real trade evidence rendered','premium-return rejection visible','value explanation expandable','mobile modal fits','Escape closes']},null,2));
    console.log('Trade explanation browser checks passed');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
