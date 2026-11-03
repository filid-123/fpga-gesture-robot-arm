// Real Chromium UI checks. All camera media is synthetic, all device ACKs are mocked.
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '../..');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || path.join(root, 'artifacts/project_web_20261029/browser/node_modules/playwright'));
const base = process.env.CONSOLE_URL || 'http://127.0.0.1:8765';
const output = path.join(root, 'artifacts/project_web_20261029');
const checked = [];
async function check(name, fn) { await fn(); checked.push(name); }

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
  try {
    const context = await browser.newContext({ viewport: { width: 1500, height: 1080 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors = []; const posts = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (request.method() === 'POST') posts.push(request); });
    const card = id => page.locator(`[data-object-id="${id}"]`);
    await page.goto(base + '/#/mode-b');
    await page.waitForFunction(() => document.querySelector('#device-name').textContent !== '设备信息载入中');
    await check('empty Mode B cannot lock', async () => assert.equal(await page.locator('#apply-button').isDisabled(), true));
    await check('three selections preserve click order; fourth refused', async () => {
      for (const id of ['red_cube', 'eraser', 'small_canister']) await card(id).click();
      await card('scissors').click();
      assert.equal(await page.locator('#selected-count').innerText(), '3');
      assert.equal(await card('scissors').getAttribute('aria-pressed'), 'false');
      assert.equal(await card('eraser').locator('.selection-badge').innerText(), '2');
      assert.equal(posts.length, 0);
    });
    await check('cancel and reselect compact/reorder numbers', async () => {
      await card('eraser').click();
      assert.equal(await card('small_canister').locator('.selection-badge').innerText(), '2');
      await card('eraser').click();
      assert.equal(await card('eraser').locator('.selection-badge').innerText(), '3');
    });
    await check('Mode A/B route and content change without device commands', async () => {
      await page.locator('[data-mode="A"]').click();
      await page.waitForURL('**/#/mode-a');
      assert.equal(await page.locator('#selection-panel').isVisible(), false);
      assert.equal(await page.locator('#fixed-scene-panel').isVisible(), true);
      assert.equal(await page.locator('#mode-a-objects .fixed-object').count(), 3);
      await page.locator('[data-mode="B"]').click();
      assert.equal(await page.locator('#selected-count').innerText(), '3');
      assert.equal(posts.length, 0);
    });
    await check('offline lock does not falsely confirm hardware', async () => {
      await page.locator('#apply-button').click();
      await page.waitForFunction(() => document.querySelector('#toast').textContent.includes('未生效'));
      assert.equal(posts.length, 1);
      assert.equal(await page.locator('#apply-title').innerText(), '当前正在查看模式 B');
      assert.equal(await page.locator('#active-mode-tag').innerText(), '设备模式未确认');
    });
    await check('add object is persistent and marked pending recognition', async () => {
      await page.locator('#add-object').click();
      await page.locator('#object-name').fill('螺丝刀'); await page.locator('#object-id').fill('screwdriver');
      await page.locator('#add-form button[type="submit"]').click();
      assert.equal(await card('screwdriver').locator('.pending-label').innerText(), '待接入');
      await page.reload();
      await page.waitForSelector('[data-object-id="screwdriver"]');
      assert.equal(await page.locator('#selected-count').innerText(), '3');
    });
    await check('duplicate object registration rejected', async () => {
      await page.locator('#add-object').click();
      await page.locator('#object-name').fill('螺丝刀'); await page.locator('#object-id').fill('screwdriver');
      await page.locator('#add-form button[type="submit"]').click();
      assert.match(await page.locator('#add-error').innerText(), /已存在/);
      await page.locator('#add-dialog .icon-button').click();
    });
    await check('device identity editable without hardware requests', async () => {
      await page.locator('#device-button').click();
      await page.locator('#device-name-input').fill('项目 AI PC');
      await page.locator('#device-model-input').fill('TEST MODEL');
      await page.locator('#device-form button').click();
      assert.equal(await page.locator('#device-name').innerText(), '项目 AI PC');
    });
    await check('synthetic browser camera explicitly labeled raw; disconnect works', async () => {
      await page.locator('#start-camera').click();
      await page.waitForFunction(() => document.querySelector('#camera-status').textContent === '原始画面');
      assert.equal(await page.locator('#camera-video').isVisible(), true);
      assert.match(await page.locator('#vision-note').innerText(), /点击“开始识别”/);
      await page.locator('#camera-settings').click();
      await page.locator('#stop-camera').click();
      assert.equal(await page.locator('#camera-status').innerText(), '未连接');
      await page.locator('#settings-dialog .icon-button').click();
    });
    await check('responsive layouts have no horizontal overflow at 390/768/1500px', async () => {
      for (const width of [390, 768, 1500]) {
        await page.setViewportSize({ width, height: 1080 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Overflow at ' + width);
      }
    });

    const mock = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    const linked = await mock.newPage();
    let status = { connected: true, active_mode: 'A', gesture_bindings: [
      { gesture: 1, object_id: 'red_cube' }, { gesture: 2, object_id: 'yellow_cube' }, { gesture: 3, object_id: 'blue_cube' }], revision: 7, idle: true, vision: { stream_url: null } };
    const commands = [];
    await linked.route('**/api/status', route => route.fulfill({ json: status }));
    await linked.route('**/api/mode-lock', async route => {
      const data = route.request().postDataJSON(); commands.push(data);
      status = { ...status, active_mode: data.mode, gesture_bindings: data.gesture_bindings, revision: status.revision+1 };
      await route.fulfill({ json: { applied: true, request_id: data.request_id, status } });
    });
    await linked.goto(base + '/#/mode-b');
    await linked.waitForFunction(() => document.querySelector('#active-mode-tag').textContent.includes('模式 A'));
    await check('device active mode independent of viewed page', async () => {
      assert.equal(await linked.locator('#breadcrumb-mode').innerText(), '模式 B');
      assert.match(await linked.locator('#active-mode-tag').innerText(), /模式 A/);
      assert.equal(commands.length, 0);
    });
    for (const id of ['red_cube', 'eraser', 'small_canister']) await linked.locator(`[data-object-id="${id}"]`).click();
    await check('lock submits once, exact gesture order, confirmation displayed', async () => {
      await linked.locator('#apply-button').click();
      await linked.waitForFunction(() => document.querySelector('#apply-title').textContent.includes('已锁定并生效'));
      assert.equal(commands.length, 1);
      assert.equal(commands[0].expected_revision, 7);
      assert.deepEqual(commands[0].gesture_bindings.map(x => x.object_id), ['red_cube', 'eraser', 'small_canister']);
      assert.equal(await linked.locator('#apply-button').isDisabled(), true);
      await linked.locator('[data-mode="A"]').click();
      assert.match(await linked.locator('#active-mode-tag').innerText(), /模式 B/);
      assert.equal(commands.length, 1);
    });
    await check('changed selection is not falsely labeled applied', async () => {
      await linked.locator('[data-mode="B"]').click();
      await linked.locator('[data-object-id="eraser"]').click();
      assert.equal(await linked.locator('#apply-button').isDisabled(), false);
      assert.equal(await linked.locator('#apply-title').innerText(), '当前正在查看模式 B');
    });
    await check('unknown acknowledgment blocks repeat submissions', async () => {
      await linked.unroute('**/api/mode-lock');
      await linked.route('**/api/mode-lock', async route => {
        status = { ...status, pending_request_id: 'unresolved-request' };
        await route.fulfill({ status: 504, json: { outcome: 'unknown', message: 'unknown acknowledgment' } });
      });
      await linked.locator('#apply-button').click();
      await linked.waitForFunction(() => document.querySelector('#apply-button').disabled && document.querySelector('#apply-button').textContent.includes('核对设备状态'));
    });

    // Preview screenshots use the real disconnected service, no simulated live/FPGA badge.
    const preview = await browser.newContext({ viewport: { width: 1500, height: 1080 }, reducedMotion: 'reduce' });
    const shot = await preview.newPage();
    await shot.goto(base+'/#/mode-b');
    await shot.waitForFunction(() => !document.querySelector('#device-name').textContent.includes('载入'));
    for (const id of ['red_cube', 'eraser', 'small_canister']) await shot.locator(`[data-object-id="${id}"]`).click();
    await shot.screenshot({ path: path.join(output, 'mode-b-desktop.png'), fullPage: true, animations: 'disabled' });
    await shot.locator('[data-mode="A"]').click();
    await shot.screenshot({ path: path.join(output, 'mode-a-desktop.png'), fullPage: true, animations: 'disabled' });
    await shot.setViewportSize({ width: 390, height: 844 });
    await shot.locator('[data-mode="B"]').click();
    await shot.screenshot({ path: path.join(output, 'mode-b-mobile.png'), fullPage: true, animations: 'disabled' });
    assert.deepEqual(errors, []);
    const result = { passed: true, checks: checked, check_count: checked.length, browser_errors: errors,
      hardware_accessed: false, camera_source: 'CHROME_SYNTHETIC_DEVICE', device_ack_source: 'PLAYWRIGHT_ROUTE_MOCK' };
    fs.writeFileSync(path.join(output, 'BROWSER_VERIFICATION.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
