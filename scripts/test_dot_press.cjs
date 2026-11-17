const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/dot-press.html');
  const loaded=async()=>{await page.waitForFunction(()=>[...document.images].filter(i=>i.getAttribute('src')).every(i=>i.complete&&i.naturalWidth>0));};
  await loaded();
  assert.equal(await page.locator('.candidate').count(),6);
  for(const surface of ['silver','ink']){
    await page.click(`[data-surface="${surface}"]`);
    for(const density of ['fine','press','coarse']){
      await page.selectOption('#density',density);await loaded();
      assert.deepEqual(await page.locator('[data-art]').evaluateAll(imgs=>imgs.map(i=>[i.naturalWidth,i.naturalHeight])),Array.from({length:6},()=>[1024,1024]));
    }
    await page.selectOption('#density','press');await loaded();
    await page.locator('#gallery').screenshot({path:`artifacts/dot-press/${surface}-gallery.png`});
  }
  await page.click('[data-mode="photo"]');await loaded();
  await page.click('[data-surface="silver"]');
  await page.locator('#gallery').screenshot({path:'artifacts/dot-press/cutout-gallery.png'});
  await page.click('[data-mode="press"]');await loaded();
  await page.click('[data-id="curry"]');
  assert.equal(await page.locator('#detail').evaluate(d=>d.open),true);
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#detail').evaluate(d=>d.open),false);
  for(const id of ['curry','rodman-detroit','rodman-chicago','allen']){await page.selectOption('#subject',id);await loaded();}
  await page.selectOption('#subject','curry');await loaded();
  await page.click('.edge-inspection summary');await loaded();
  assert.equal(await page.locator('.edge-inspection').evaluate(d=>d.open),true);
  assert.equal(await page.locator('#edge-proof').evaluate(i=>i.naturalWidth),1120);
  await page.click('.edge-inspection summary');
  await page.locator('.comparison').screenshot({path:'artifacts/dot-press/source-comparison.png'});
  const downloadEvent=page.waitForEvent('download');await page.locator('[data-download="curry"]').click();const download=await downloadEvent;
  assert.equal(await download.failure(),null);
  const layouts=[];
  for(const width of [1280,1440,1920,390]){
    await page.setViewportSize({width,height:width===390?844:900});
    layouts.push(await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})));
    assert.equal(layouts.at(-1).scrollWidth,width);
    await page.screenshot({path:`artifacts/dot-press/page-${width}.png`,fullPage:true});
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync('artifacts/dot-press/verification.json',JSON.stringify({errors,layouts,assets:6,resolution:[1024,1024],variants:6,modal:true,download:true},null,2));
  await browser.close();console.log('PASS: image variants, dimensions, modal, download, responsive layouts, no page errors');
})().catch(error=>{console.error(error);process.exit(1)});
