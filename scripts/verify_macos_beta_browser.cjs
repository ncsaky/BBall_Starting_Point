/* Shared browser checks; internet blocked. Packaged acceptance is the default. */
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");

(async () => {
  const [url, mode, reportPath, evidence, runtimeKind = "packaged"] = process.argv.slice(2);
  assert.ok(["packaged", "source"].includes(runtimeKind), 'Unknown runtime kind');
  const browser = await chromium.launch({
    executablePath: process.env.NBA_GM_TEST_CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 1050}, acceptDownloads: true});
    const blocked = new Set(), failures = [], errors = [];
    await context.route("**/*", route => {
      const target = new URL(route.request().url());
      if (["127.0.0.1", "localhost"].includes(target.hostname) || ["data:", "blob:"].includes(target.protocol)) return route.continue();
      blocked.add(target.hostname);
      return route.abort("internetdisconnected");
    });
    const page = await context.newPage();
    page.on("pageerror", error => errors.push(String(error)));
    page.on("response", response => {
      if (response.url().startsWith(url) && response.status() >= 400) failures.push({url: response.url(), status: response.status()});
    });
    await page.goto(url, {waitUntil: "domcontentloaded"});
    await page.locator("#startupScreen").waitFor({state: "visible", timeout: 30000});
    await page.waitForFunction(() => document.querySelector("#teamSelect").options.length > 1);
    async function finishFirstRunTutorial() {
      await page.waitForFunction(() => !state.hydrating && state.busyDepth === 0, null, {timeout:60000});
      if (!await page.evaluate(() => localStorage.getItem('nbaGmFirstRunTutorialCompleted'))) {
        const skip = page.locator('[data-tutorial-action="skip"]');
        await skip.waitFor({state:'visible', timeout:30000});
        await skip.click();
        await page.waitForFunction(() => !document.querySelector('#app').inert);
      }
    }
    async function openCard(id,category) {
      await page.locator('.card-board-gallery-toggle').click();
      const group = page.locator(`[data-board-gallery-group-toggle="${category}"]`);
      if(await group.getAttribute('aria-expanded') !== 'true') await group.click();
      await page.locator(`[data-board-add="${id}"]`).click();
    }
    let movie = null;
    if (mode === "startup") {
      await page.waitForFunction(() => {
        const video = document.querySelector('video[data-startup-video]');
        return document.querySelector('#startupScreen').dataset.startupVideo === 'playing'
          && video?.readyState >= 2 && video.currentTime > .2;
      }, null, {timeout: 30000});
      const sample = () => page.locator('video[data-startup-video]').evaluate(video => {
        const canvas = document.createElement('canvas');
        canvas.width = 64; canvas.height = 36;
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, 64, 36);
        const bytes = context.getImageData(0, 0, 64, 36).data;
        let brightness = 0;
        for (let index = 0; index < bytes.length; index += 4) brightness += bytes[index] + bytes[index + 1] + bytes[index + 2];
        return {time: video.currentTime, width: video.videoWidth, height: video.videoHeight, muted: video.muted,
          opacity: getComputedStyle(video).opacity, connected: video.isConnected,
          photos_opacity: getComputedStyle(document.querySelector('.startup-photo-rail')).opacity,
          mean_brightness: brightness / (64 * 36 * 3)};
      });
      const first = await sample();
      await page.waitForTimeout(1200);
      // Wait for the playback crossfade, not a fixed delay under build/CI load.
      await page.waitForFunction(() => {
        const video = document.querySelector('video[data-startup-video]');
        const photos = document.querySelector('.startup-photo-rail');
        return getComputedStyle(video).opacity === '1' && getComputedStyle(photos).opacity === '0';
      }, null, {timeout:30000});
      const second = await sample();
      assert.ok(second.time > first.time + .5, 'Bundled video must actually advance');
      assert.ok(second.width === 1280 && second.height === 720 && second.muted && second.connected);
      assert.equal(second.opacity, '1');
      assert.equal(second.photos_opacity, '0');
      assert.ok(second.mean_brightness > 5 && second.mean_brightness < 250, 'Video cannot be blank');
      assert.equal(await page.locator('.startup-video-backdrop iframe').count(), 0);
      movie = {first, second, offline_playback: true};
      const delivery = await page.evaluate(async () => {
        const range = await fetch('/assets/startup/video/front-office.mp4', {headers: {Range: 'bytes=0-1'}});
        const head = await fetch('/assets/startup/video/front-office.mp4', {method: 'HEAD'});
        return {range_status: range.status, range_bytes: (await range.arrayBuffer()).byteLength,
          content_range: range.headers.get('Content-Range'), head_status: head.status,
          head_bytes: (await head.arrayBuffer()).byteLength};
      });
      assert.equal(delivery.range_status, 206);
      assert.equal(delivery.range_bytes, 2);
      assert.equal(delivery.head_status, 200);
      assert.equal(delivery.head_bytes, 0);
      movie.delivery = delivery;
      await page.screenshot({path:path.join(evidence, 'video-desktop.png')});
      await page.setViewportSize({width:390, height:844});
      await page.waitForTimeout(800);
      const bounds = await page.locator('video[data-startup-video]').boundingBox();
      assert.ok(bounds.width >= 390 && bounds.height >= 844, 'Mobile video must cover the viewport');
      await page.screenshot({path:path.join(evidence, 'video-mobile.png')});
      movie.mobile = {viewport: {width:390, height:844}, bounds};
      await page.setViewportSize({width:1440, height:1050});
      await page.emulateMedia({reducedMotion: 'reduce'});
      await page.reload({waitUntil: 'domcontentloaded'});
      await page.locator('#startupScreen').waitFor({state:'visible'});
      assert.equal(await page.locator('video[data-startup-video]').getAttribute('src'), null);
      assert.equal(await page.locator('.startup-photo-rail').evaluate(el => getComputedStyle(el).opacity), '1');
      movie.reduced_motion_no_video_loaded = true;
      await page.emulateMedia({reducedMotion: 'no-preference'});
      await page.waitForFunction(() => document.querySelector('#startupScreen').dataset.startupVideo === 'playing');
      await page.route('**/assets/startup/video/front-office.mp4', route => route.abort('failed'));
      await page.reload({waitUntil: 'domcontentloaded'});
      await page.locator('#startupScreen').waitFor({state:'visible'});
      await page.waitForTimeout(1500);
      assert.equal(await page.locator('video[data-startup-video]').getAttribute('src'), null);
      assert.equal(await page.locator('.startup-photo-rail').evaluate(el => getComputedStyle(el).opacity), '1');
      assert.equal(await page.locator('.startup-video-backdrop iframe').count(), 0);
      movie.missing_movie_clean_photo_fallback = true;
      await page.screenshot({path:path.join(evidence, 'video-missing-fallback.png')});
      await page.unroute('**/assets/startup/video/front-office.mp4');
      await page.reload({waitUntil: 'domcontentloaded'});
      await page.waitForFunction(() => document.querySelector('#startupScreen').dataset.startupVideo === 'playing');
    }
    if (mode === "create") {
      await page.locator('[data-team-value="GSW"]').click();
      await page.locator("#gameModeSelect").selectOption("standard");
      await page.locator("#saveName").fill("beta_friend_test");
      await page.locator("#createSave").click();
      await page.locator("#startupScreen").waitFor({state: "hidden", timeout: 60000});
      await page.locator(".card-board-canvas").waitFor({state: "visible", timeout: 60000});
      await finishFirstRunTutorial();
      await openCard('identity','team');
      assert.equal(await page.locator('video[data-startup-video]').getAttribute('src'), null);
      await page.locator('[data-dashboard-settings]:visible').first().click();
      await page.locator('[data-return-save-selection]').click();
      await page.locator('#startupScreen').waitFor({state:'visible'});
      await page.waitForFunction(() => document.querySelector('#startupScreen').dataset.startupVideo === 'playing');
      movie = {stopped_in_game:true, return_to_selector_playback:true};
      await page.locator('#startupLoadSave').click();
      await page.locator('#startupScreen').waitFor({state:'hidden'});
    } else if (mode === "resume") {
      await page.waitForFunction(() => [...document.querySelector("#startupSaveSelect").options].some(o => o.value.endsWith("beta_friend_test.json")));
      const value = await page.locator("#startupSaveSelect option").evaluateAll(options => options.find(o => o.value.endsWith("beta_friend_test.json")).value);
      await page.locator("#startupSaveSelect").selectOption(value);
      await page.locator("#startupLoadSave").click();
      await page.locator("#startupScreen").waitFor({state: "hidden", timeout: 60000});
      await page.locator(".card-board-canvas").waitFor({state: "visible", timeout: 60000});
      await finishFirstRunTutorial();
      await openCard('week','season');
      const expected = JSON.parse(fs.readFileSync(path.join(evidence, "expected-game.json"), "utf8"));
      const game = await page.evaluate(async expected => {
        const {token} = await (await fetch("/api/session")).json();
        const response = await fetch("/api/action", {method:"POST", headers:{"Content-Type":"application/json", "X-NBA-GM-Token":token}, body:JSON.stringify({action:"box_score", payload:expected})});
        return (await response.json()).result;
      }, expected);
      assert.ok(game.player_lines.length && game.home_score > 0 && game.away_score > 0);
      // Open the actual existing box-score presentation when accessible.
      const box = page.locator(`[data-box-score="${expected.game_id}"]`).first();
      if (await box.count()) await box.click();
      else await page.evaluate(id => openBoxScore(id), expected.game_id);
      await page.locator(".modal-box-score").waitFor({state:"visible", timeout:30000});
    } else if (mode === "backup") {
      await page.waitForFunction(() => [...document.querySelector("#startupSaveSelect").options].some(o => o.value.endsWith("beta_friend_test.json")));
      const value = await page.locator("#startupSaveSelect option").evaluateAll(options => options.find(o => o.value.endsWith("beta_friend_test.json")).value);
      await page.locator("#startupSaveSelect").selectOption(value);
      const downloadPromise = page.waitForEvent("download");
      await page.locator("#startupExportSave").click();
      const download = await downloadPromise;
      const backup = path.join(evidence, "browser-export.nbagm.zip");
      await download.saveAs(backup);
      assert.ok(fs.statSync(backup).size > 0);
      await page.locator("#startupRestoreName").fill("browser_restored_friend_test");
      await page.locator("#startupRestoreFile").setInputFiles(backup);
      await page.waitForFunction(() => document.querySelector("#startupSaveMessage").textContent.includes("Restored as"), null, {timeout:60000});
      await page.waitForFunction(() => [...document.querySelector("#startupSaveSelect").options].some(o => o.value.endsWith("browser_restored_friend_test.json")));
    }
    let issueReport = null;
    if (["startup", "create"].includes(mode)) {
      await page.waitForFunction(() => !state.hydrating && !state.busy, null, {timeout:60000});
      if (mode === "startup") await page.locator("#startupReportIssue").click();
      else {
        await page.locator('[data-dashboard-settings]:visible').first().click();
        await page.locator('[data-report-issue]').click();
      }
      await page.waitForFunction(() => state.modal?.report?.runtime_available);
      await page.locator('[name="summary"]').fill("Packaging verification report");
      const downloaded = page.waitForEvent("download");
      await page.locator('[data-issue-report-form] button[type="submit"]').click();
      const file = path.join(evidence, `issue-${mode}.json`);
      await (await downloaded).saveAs(file);
      const issue = JSON.parse(fs.readFileSync(file, "utf8"));
      assert.equal(issue.schema, "nba_gm_issue_v1");
      assert.equal(issue.runtime.packaged, runtimeKind === "packaged");
      assert.equal(issue.context.screen, mode === "startup" ? "save_selection" : "game");
      assert.ok(!JSON.stringify(issue).includes(evidence));
      assert.ok(!JSON.stringify(issue).includes("beta_friend_test"));
      issueReport = {downloaded:true, version:issue.runtime.version, screen:issue.context.screen, no_save_paths:true};
      await page.keyboard.press("Escape");
      if (mode === "create") await page.keyboard.press("Escape");
    }
    await page.waitForTimeout(1000);
    await page.locator("img[src]").evaluateAll(async images => {
      await Promise.all(images.map(async img => { img.loading = "eager"; try { await img.decode(); } catch {} }));
    });
    // Concurrent image decodes may reject while loading is still in progress.
    // Wait for readiness, then retain the detailed broken-asset assertion below.
    try {
      await page.waitForFunction(() => [...document.querySelectorAll('img[src]')].every(img => {
        const visible = !!(img.offsetWidth || img.offsetHeight || img.getClientRects().length);
        return !visible || img.getAttribute('src').startsWith('http') || (img.complete && img.naturalWidth > 0);
      }), null, {timeout:30000});
    } catch {}
    const images = await page.locator("img[src]").evaluateAll(images => images.map(img => ({
      src: img.getAttribute("src"), loaded: img.complete && img.naturalWidth > 0,
      visible: !!(img.offsetWidth || img.offsetHeight || img.getClientRects().length),
    })));
    const local = images.filter(img => img.src && !img.src.startsWith("http"));
    assert.ok(local.some(img => img.loaded));
    assert.deepEqual(local.filter(img => img.visible && !img.loaded), [], "Visible local image did not render");
    // Decode representative assets from every required family, including
    // artwork whose panels may be hidden at this point in the season.
    const assets = ["/assets/startup/press/kobe-bryant.png", "/assets/startup/press/larry-sanders.png", "/assets/startup/celtics-heat-2006.jpg",
      "/assets/team_logos/GSW.png", "/assets/game-art/shooting-ink.webp",
      "/assets/game-art/coaches/coach-01-silver.webp",
      "/assets/dot-press/exports/builder-fine-silver.png"];
    const decoded = await page.evaluate(async paths => {
      return await Promise.all(paths.map(async src => {const img = new Image(); img.src = src; await img.decode(); return {src, width:img.naturalWidth, height:img.naturalHeight};}));
    }, assets);
    // Discover and decode one dot-press photo from its bundled manifest.
    const dotAssets = await page.evaluate(async () => {
      const css = await (await fetch("/dot-press.css")).text();
      return css;
    });
    assert.ok(dotAssets.length);
    await page.screenshot({path:path.join(evidence, `browser-${mode}.png`), fullPage:true});
    assert.deepEqual(failures, [], "Local resource or API request failed");
    assert.deepEqual(errors, [], "Uncaught browser error");
    fs.writeFileSync(reportPath, JSON.stringify({mode, save_selector_loaded:true, blocked_internet_hosts:[...blocked],
      visible_local_images: local.filter(i=>i.visible).length, decoded_assets: decoded, local_request_failures: failures,
      browser_errors: errors, startup_movie: movie, issue_report: issueReport, screenshot:path.join(evidence, `browser-${mode}.png`)}, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
