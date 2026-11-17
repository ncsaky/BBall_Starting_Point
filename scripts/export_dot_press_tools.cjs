// Reuse the two approved object drawings without changing the first review gallery.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:8765/image-studies.html');
  await page.waitForSelector('body[data-ready="true"]');
  for (const id of ['builder','finder']) {
    const png = await page.evaluate(async (id) => {
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 640 640"><g transform="translate(0 120)">${drawings[id]('7')}</g></svg>`;
      const source = await imageFrom(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
      const canvas = document.createElement('canvas');canvas.width=1024;canvas.height=1024;
      canvas.getContext('2d').drawImage(source,0,0);
      return canvas.toDataURL().split(',')[1];
    }, id);
    fs.writeFileSync(path.join('src/nba_gm_data/gui/assets/dot-press/sources',`${id}.png`),Buffer.from(png,'base64'));
  }
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
