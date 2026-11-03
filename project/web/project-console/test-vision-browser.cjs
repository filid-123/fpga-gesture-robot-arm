// Real CPU model on a recorded image; synthetic browser camera only.
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '../..');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || path.join(root, 'artifacts/project_web_20261029/browser/node_modules/playwright'));
const base = process.env.CONSOLE_URL || 'http://127.0.0.1:8765';
const output = path.join(root, 'artifacts/project_web_20261029');
const samplePath = path.join(root, 'artifacts/multiobject/eraser_top_repair_20261027/fresh_confirmation_capture/frame_000000_raw.png');
const checks = [];
async function check(name, fn) { await fn(); checks.push(name); }
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1500, height: 1080 }, reducedMotion: 'reduce' });
    const page = await context.newPage(); const errors = []; const mutations = []; const frames = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (request.method() === 'POST') mutations.push(request.url()); });
    page.on('response', async response => { if (response.url().includes('/api/vision/') && response.status() === 200) frames.push(await response.json()); });
    await page.goto(base+'/#/mode-b');
    await page.waitForFunction(() => document.querySelector('#settings-vision').textContent.includes('六类识别可用'));
    await check('opening the page does not infer or apply a mode', async () => assert.deepEqual(mutations, []));
    await page.locator('[data-object-id="eraser"]').click(); await page.locator('[data-object-id="red_cube"]').click();
    await check('real model sample contains six classes and is explicitly a replay', async () => {
      await page.locator('#sample-vision').click();
      await page.waitForFunction(() => document.querySelector('#camera-status').textContent === '样例回放', { timeout: 45000 });
      assert.match(await page.locator('#camera-overlay-label').innerText(), /历史样例.*非实时/);
      assert.equal(await page.locator('#detection-list .detected').count(), 6);
      assert.match(await page.locator('#vision-note').innerText(), /CPU/);
      assert.equal(frames[0].model.frozen_files_verified, 19);
      assert.equal(frames[0].physical_execution, false);
      assert.equal(frames[0].npu_accepted, false);
    });
    await check('preview gesture numbers follow selection, not legacy fixed tasks', async () => {
      assert.match(await page.locator('#detection-list').innerText(), /1 · 橡皮/);
      assert.match(await page.locator('#detection-list').innerText(), /2 · 红色木块/);
      const count = mutations.length;
      await page.locator('[data-object-id="eraser"]').click();
      assert.match(await page.locator('#detection-list').innerText(), /1 · 红色木块/);
      assert.equal(mutations.length, count);
    });
    await page.screenshot({ path: path.join(output, 'mode-b-real-recognition.png'), fullPage: true });
    await check('uploaded photo retains the same source pixels and is not called live', async () => {
      await page.locator('#vision-file').setInputFiles(samplePath);
      await page.waitForFunction(() => document.querySelector('#camera-status').textContent === '照片识别', { timeout: 45000 });
      assert.equal(await page.locator('#detection-canvas').getAttribute('data-source'), 'photo');
      assert.equal(frames[1].frame_sha256, frames[0].frame_sha256);
      assert.equal(await page.locator('#detection-list .detected').count(), 6);
    });
    await check('phone layout accommodates the real recognition and controls', async () => {
      await page.setViewportSize({ width: 390, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await page.screenshot({ path: path.join(output, 'mode-b-real-recognition-mobile.png'), fullPage: true });
      await page.setViewportSize({ width: 1500, height: 1080 });
    });
    await check('synthetic camera uses actual inference with same-frame source identity', async () => {
      await page.locator('#camera-settings').click(); await page.locator('#start-camera').click();
      await page.waitForFunction(() => document.querySelector('#camera-status').textContent === '原始画面');
      await page.locator('#recognize-camera').click();
      await page.waitForFunction(() => document.querySelector('#camera-status').textContent === '相机识别', { timeout: 45000 });
      assert.equal(await page.locator('#detection-canvas').getAttribute('data-source'), 'camera');
      await page.locator('#recognize-camera').click();
      assert.equal(await page.locator('#detection-canvas').isVisible(), false);
      assert.equal(await page.locator('#camera-video').isVisible(), true);
      assert.equal(await page.locator('#detection-list .detected').count(), 0);
    });
    await page.waitForFunction(() => !document.querySelector('#sample-vision').disabled);
    let resolveFrame; const delayed = new Promise(resolve => { resolveFrame = resolve; });
    await page.route('**/api/vision/infer', async route => {
      const body = route.request().postDataJSON(); await delayed;
      await route.fulfill({ json: { ...frames[0], frame_id: body.frame_id, source: 'camera' } });
    });
    await check('late inference after leaving Mode B is discarded and camera released', async () => {
      const requested = page.waitForRequest('**/api/vision/infer');
      await page.locator('#recognize-camera').click(); await requested;
      await page.locator('[data-mode="A"]').click(); resolveFrame();
      await page.waitForFunction(() => !document.querySelector('#sample-vision').disabled);
      await page.locator('[data-mode="B"]').click();
      assert.equal(await page.locator('#camera-status').innerText(), '未连接');
      assert.equal(await page.locator('#detection-canvas').isVisible(), false);
      assert.equal(await page.evaluate(() => document.querySelector('#camera-video').srcObject), null);
    });
    assert.deepEqual(errors, []);
    assert.equal(mutations.some(url => url.includes('mode-lock')), false);
    const result = { passed: true, checks, check_count: checks.length, browser_errors: errors,
      real_model: true, backend: frames[0].backend.actual_backend, sample_pixel_sha256: frames[0].frame_sha256,
      hardware_accessed: false, camera_source: 'CHROME_SYNTHETIC_DEVICE', motion_requests: 0 };
    fs.writeFileSync(path.join(output, 'VISION_BROWSER_VERIFICATION.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
