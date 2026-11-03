import { CATALOG, toggleSelection, bindingsFor, matchesApplied, validateCustom, restoreState } from './state.mjs';

const $ = id => document.getElementById(id);
const STORAGE_KEY = 'zhixing.console.v1';
let saved;
try { saved = localStorage.getItem(STORAGE_KEY); } catch { saved = null; }
const persisted = restoreState(saved);
const state = { ...persisted, view: 'B', status: null, pending: false, config: null, stream: null,
  streamKind: 'none', activeVideoURL: '', failedVideoURL: '', toastTimer: null, pollTimer: null, pollBusy: false, cameraPending: false,
  recognizing: false, visionGeneration: 0, visionBusy: false, visionTimer: null, lastFrame: null };

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ selected: state.selected, custom: state.custom,
    device: state.device, cameraId: state.cameraId })); } catch { /* This session remains usable without storage. */ }
}
function toast(message, error = false) {
  clearTimeout(state.toastTimer);
  $('toast').textContent = message;
  $('toast').classList.toggle('error', error);
  $('toast').hidden = false;
  state.toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 6500 : 4000);
}
const catalog = () => [...CATALOG, ...state.custom];
const itemFor = id => catalog().find(item => item.id === id);

function art(icon, color) {
  const colors = { red: ['#e98979', '#ce584a', '#af4337'], yellow: ['#edce6e', '#dcaf43', '#bd922d'],
    blue: ['#89acd1', '#5b8bb9', '#416a95'], teal: ['#a4c2b3', '#6d9e87', '#517e67'],
    pink: ['#e1b6af', '#c48d86', '#ac736b'] };
  const [top, face, side] = colors[color] || colors.teal;
  const paths = {
    cube: `<ellipse cx="50" cy="78" rx="25" ry="4" fill="#43543b" opacity=".06"/><path d="m23 30 28-12 27 14-29 13z" fill="${top}"/><path d="M23 30v34l26 16V45z" fill="${side}"/><path d="m49 45 29-13v33L49 80z" fill="${face}"/><path d="m27 29 24-10 23 12" stroke="#fff" opacity=".3" stroke-width="1"/>`,
    cylinder: '<ellipse cx="50" cy="81" rx="23" ry="4" fill="#43543b" opacity=".06"/><path d="M29 28h42v41c0 18-42 18-42 0z" fill="#82ac98"/><path d="M29 39c0 15 42 15 42 0v18c0 15-42 15-42 0" fill="#a3c2b0"/><ellipse cx="50" cy="28" rx="21" ry="12" fill="#cadcd0"/><ellipse cx="50" cy="28" rx="16" ry="8" fill="#b6cebd"/><path d="M34 37v32" stroke="#dae9d8" stroke-width="2" opacity=".45"/>',
    eraser: '<ellipse cx="50" cy="76" rx="32" ry="4" fill="#43543b" opacity=".06"/><path d="m17 43 48-21 23 20-48 23z" fill="#ebc5bb"/><path d="M17 43v16l23 20V65z" fill="#b5837c"/><path d="m40 65 48-23v16L40 79z" fill="#d2a49a"/><path d="m35 35 16-7 23 21-16 7z" fill="#f1f0e4"/><path d="m58 56 16-7v16l-16 7z" fill="#cdd5c5"/>',
    scissors: '<g transform="rotate(22 50 50)" fill="none" stroke-linecap="round"><path d="m47 48 18-31M53 48 35 17" stroke="#a6b0af" stroke-width="6"/><path d="m47 48-7 10M53 48l7 10" stroke="#c0c9c1" stroke-width="5"/><ellipse cx="34" cy="68" rx="9" ry="13" stroke="#789e8b" stroke-width="6"/><ellipse cx="66" cy="68" rx="9" ry="13" stroke="#789e8b" stroke-width="6"/><circle cx="50" cy="47" r="3" fill="#9aa79c" stroke="#9aa79c"/></g>',
    package: '<path d="m22 32 28-13 28 13v36L50 82 22 68Z" fill="#b7ccb4"/><path d="m22 32 28 14 28-14M50 46v36" fill="none" stroke="#7c9d7b" stroke-width="2"/><path d="m36 25 28 14v12l-12 6V44L27 32" fill="#dce8d4"/>',
  };
  return `<svg class="object-art" viewBox="0 0 100 96" aria-hidden="true">${paths[icon] || paths.package}</svg>`;
}
function renderObjects() {
  const grid = $('object-grid');
  grid.replaceChildren();
  for (const item of catalog()) {
    const index = state.selected.indexOf(item.id);
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'object-card' + (index >= 0 ? ' selected' : '');
    card.dataset.objectId = item.id;
    card.setAttribute('aria-pressed', String(index >= 0));
    card.setAttribute('aria-label', item.name + (index >= 0 ? `，手势${index + 1}，再次点击取消` : '，点击选择'));
    card.disabled = state.pending;
    card.innerHTML = art(item.icon, item.color);
    if (index >= 0) {
      const badge = document.createElement('span'); badge.className = 'selection-badge'; badge.textContent = index + 1; card.append(badge);
      const check = document.createElement('span'); check.className = 'selection-check'; check.textContent = '✓'; card.append(check);
    } else if (item.recognition === 'pending') {
      const pending = document.createElement('span'); pending.className = 'pending-label'; pending.textContent = '待接入'; card.append(pending);
    }
    const title = document.createElement('strong'); title.textContent = item.name;
    const sub = document.createElement('span'); sub.className = 'object-subtitle'; sub.textContent = item.subtitle;
    card.append(title, sub);
    card.addEventListener('click', () => {
      if (state.pending) return;
      const result = toggleSelection(state.selected, item.id);
      if (result.limit) { toast('最多选择3个物体，请先取消一个已选物体。'); return; }
      state.selected = result.selected;
      persist(); renderObjects(); renderMappings(); renderApply();
      drawRecognition();
      const next = grid.querySelector(`[data-object-id="${item.id}"]`);
      next?.focus({ preventScroll: true });
    });
    grid.append(card);
  }
  const add = document.createElement('button'); add.type = 'button'; add.className = 'object-card add-card'; add.id = 'add-object';
  add.innerHTML = '<span aria-hidden="true">＋</span><strong>添加识别物体</strong><small>扩展你的物体库</small>';
  add.disabled = state.pending;
  add.addEventListener('click', () => { $('add-form').reset(); $('add-error').textContent = ''; $('add-dialog').showModal(); });
  grid.append(add);
  $('selected-count').textContent = state.selected.length;
}
function renderFixed() {
  $('mode-a-objects').replaceChildren();
  CATALOG.slice(0, 3).forEach((item, i) => {
    const card = document.createElement('div'); card.className = 'fixed-object';
    card.innerHTML = art(item.icon, item.color);
    const name = document.createElement('strong'); name.textContent = item.name;
    const detail = document.createElement('small'); detail.textContent = `控制手势 ${i + 1}`;
    card.append(name, detail); $('mode-a-objects').append(card);
  });
}
function renderMappings() {
  const list = bindingsFor(state.view, state.selected);
  const slots = $('gesture-slots'); slots.replaceChildren();
  for (let i = 0; i < 3; i++) {
    const item = itemFor(list[i]?.object_id);
    const slot = document.createElement('div'); slot.className = 'gesture-slot' + (item ? '' : ' empty');
    const number = document.createElement('span'); number.className = 'gesture-number'; number.textContent = i + 1;
    const text = document.createElement('span'); text.className = 'gesture-slot-text';
    const name = document.createElement('strong'); name.textContent = item?.name || '等待选择';
    const detail = document.createElement('small'); detail.textContent = `控制手势 ${i + 1}`;
    text.append(name, detail); slot.append(number, text); slots.append(slot);
  }
  $('mapping-state').textContent = matchesApplied(state.view, state.selected, state.status) ? '设备已应用' : '锁定后应用';
}
function renderApply() {
  const connected = Boolean(state.status?.connected);
  const uncertain = Boolean(state.status?.pending_request_id);
  const matched = matchesApplied(state.view, state.selected, state.status);
  $('sidebar-status').textContent = connected ? '设备已连接' : '设备尚未连接';
  $('sidebar-dot').classList.toggle('online', connected);
  $('apply-title').textContent = matched ? `模式 ${state.view} 已锁定并生效` : `当前正在查看模式 ${state.view}`;
  $('apply-description').textContent = state.pending ? '正在等待设备确认，请稍候…' : uncertain ? '上次锁定尚未确认，正在核对设备状态；不会重复提交。' : connected
    ? matched ? '当前模式与手势映射已由设备确认。' : '锁定后，设备将使用当前模式与手势映射。'
    : '设备尚未连接，页面选择已保留；接入后可锁定生效。';
  $('active-mode-tag').classList.toggle('confirmed', connected && Boolean(state.status.active_mode));
  const modeLabel = connected && state.status.active_mode ? `设备运行：模式 ${state.status.active_mode}` : '设备模式未确认';
  $('active-mode-tag').lastChild.textContent = modeLabel;
  $('apply-button').querySelector('span').textContent = state.pending ? '正在锁定…' : uncertain ? '核对设备状态' : matched ? '模式已锁定' : `锁定模式 ${state.view}`;
  $('apply-button').disabled = state.pending || uncertain || matched || (state.view === 'B' && state.selected.length === 0);
  $('settings-connection').textContent = connected ? `设备已连接${state.status.active_mode ? ' · 模式 ' + state.status.active_mode : ''}` : 'FPGA模式接口待接入';
  for (const link of document.querySelectorAll('.mode-link')) {
    link.classList.toggle('nav-disabled', state.pending);
    link.setAttribute('aria-disabled', String(state.pending));
  }
}
function renderPage() {
  document.title = `模式 ${state.view} · 知行协作平台`;
  const isB = state.view === 'B';
  if (!isB && state.streamKind !== 'none') stopCamera();
  $('content-layout').classList.toggle('mode-a', !isB);
  $('breadcrumb-mode').textContent = `模式 ${state.view}`;
  document.querySelectorAll('.mode-link').forEach(link => {
    const active = link.dataset.mode === state.view;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  $('mode-pill').textContent = isB ? 'MODE B / 视觉驱动' : 'MODE A / 手势驱动';
  $('mode-index').textContent = isB ? '02' : '01';
  $('mode-title').textContent = isB ? '你来选择，机械臂来完成。' : '一个手势，回应你的需要。';
  $('mode-description').textContent = isB
    ? '识别取物区中的物体，选择本次协作目标。系统根据物体位置规划路径，通过手势完成抓取与交付。'
    : '用三个控制手势选择红、黄、蓝木块。机械臂沿固定路径完成抓取，在缓冲区等待，确认后将物体送达交付区。';
  $('intro-features').replaceChildren();
  for (const title of isB ? ['视觉识别定位', '动态路径规划', '手势协同交付'] : ['固定目标映射', '预设运动路径', '手势确认交付']) {
    const feature = document.createElement('span');
    const dot = document.createElement('i'); dot.className = 'feature-dot';
    feature.append(dot, document.createTextNode(title)); $('intro-features').append(feature);
  }
  $('selection-panel').hidden = !isB;
  $('mode-a-panel').hidden = isB;
  $('camera-panel').hidden = !isB;
  $('fixed-scene-panel').hidden = isB;
  renderObjects(); renderMappings(); renderApply();
}
function readRoute() {
  const mode = location.hash === '#/mode-a' ? 'A' : 'B';
  if (state.pending && mode !== state.view) { location.replace(`#/mode-${state.view.toLowerCase()}`); return; }
  state.view = mode; renderPage();
}
window.addEventListener('hashchange', readRoute);
if (!['#/mode-a', '#/mode-b'].includes(location.hash)) history.replaceState(null, '', '#/mode-b');

async function api(path, options = {}) {
  const controller = new AbortController();
  const { timeoutMs = 10000, ...requestOptions } = options;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, { ...requestOptions, signal: controller.signal, cache: 'no-store',
      headers: { 'Content-Type': 'application/json', 'X-Console-Token': state.config?.csrf_token || '', ...options.headers } });
    const result = await response.json();
    if (!response.ok) { const error = new Error(result.message || '请求失败，请稍后重试。'); error.result = result; throw error; }
    return result;
  } finally { clearTimeout(timer); }
}

async function pollStatus() {
  if (state.pollBusy || state.pending) return;
  state.pollBusy = true;
  try {
    const next = await api('/api/status');
    if (state.pending || (state.status?.connected && next.connected && next.revision < state.status.revision)) return;
    state.status = next;
    const vision = state.status.vision;
    const url = vision?.stream_url;
    $('settings-vision').textContent = url ? '识别视频已配置' : vision?.local?.available ? '六类识别可用 · CPU预览' : '识别服务待接入';
    if (url && state.view === 'B' && ['none', 'annotated'].includes(state.streamKind) && url !== state.activeVideoURL && url !== state.failedVideoURL) connectAnnotated(url);
    if (!url && state.streamKind === 'annotated') resetCamera();
  } catch {
    state.status = { connected: false, active_mode: null, gesture_bindings: [] };
  } finally { state.pollBusy = false; renderMappings(); renderApply(); }
}

$('apply-button').addEventListener('click', async () => {
  if (state.pending || matchesApplied(state.view, state.selected, state.status)) return;
  if (state.view === 'B' && !state.selected.length) { toast('请先选择至少一个物体。'); return; }
  if (!state.config) { toast('工作台服务尚未连接，请通过启动脚本打开页面。', true); return; }
  state.pending = true; renderObjects(); renderApply();
  const request = { request_id: crypto.randomUUID(), mode: state.view,
    gesture_bindings: bindingsFor(state.view, state.selected),
    expected_revision: state.status?.revision ?? null,
    object_catalog: catalog().map(({ id, name }) => ({ id, name })) };
  try {
    const result = await api('/api/mode-lock', { method: 'POST', body: JSON.stringify(request) });
    state.status = result.status;
    toast(`模式 ${request.mode} 已由设备确认，手势映射已生效。`);
  } catch (error) {
    const uncertain = error.name === 'AbortError' || error.result?.outcome === 'unknown';
    toast(uncertain ? '尚未收到设备确认，正在核对状态，请勿重复提交。' : error.message, true);
    if (uncertain) state.status = null;
  } finally {
    state.pending = false; renderObjects(); renderMappings(); renderApply();
    await pollStatus();
  }
});

$('add-form').addEventListener('submit', event => {
  event.preventDefault();
  const name = $('object-name').value.trim(); const id = $('object-id').value.trim();
  const error = validateCustom(name, id, catalog());
  if (error) { $('add-error').textContent = error; return; }
  if (state.custom.length >= 40) { $('add-error').textContent = '本地物体库已满，请先整理已登记的类别。'; return; }
  state.custom.push({ id, name, subtitle: 'CUSTOM OBJECT', icon: $('object-icon').value, color: 'teal', recognition: 'pending' });
  persist(); renderObjects(); $('add-dialog').close(); toast('物体已添加，识别模型待接入。');
});
document.querySelectorAll('.dialog-close').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.querySelectorAll('dialog').forEach(dialog => dialog.addEventListener('click', event => {
  const rect = dialog.getBoundingClientRect();
  if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
}));

function renderDevice() {
  const device = state.device || state.config?.device || { name: 'AI PC', model: '点击设置名称与型号' };
  $('device-name').textContent = device.name; $('device-model').textContent = device.model;
  $('device-name-input').value = device.name; $('device-model-input').value = device.model;
}
async function openSettings() {
  renderDevice(); $('settings-dialog').showModal();
  if (navigator.mediaDevices?.enumerateDevices) {
    try { await fillCameras(); } catch { /* Permission is requested only when the user connects. */ }
  }
}
for (const id of ['device-button', 'camera-settings', 'camera-connect']) $(id).addEventListener('click', openSettings);
$('device-form').addEventListener('submit', event => {
  event.preventDefault();
  const name = $('device-name-input').value.trim(); const model = $('device-model-input').value.trim();
  if (!name || !model) return;
  state.device = { name, model }; persist(); renderDevice(); toast('设备名称与型号已保存。');
});
async function fillCameras() {
  const devices = (await navigator.mediaDevices.enumerateDevices()).filter(d => d.kind === 'videoinput');
  const select = $('camera-select'); select.replaceChildren();
  if (!devices.length) { const option = new Option('未找到摄像头', ''); select.append(option); return; }
  for (let i = 0; i < devices.length; i++) select.append(new Option(devices[i].label || `摄像头 ${i + 1}（授权后显示名称）`, devices[i].deviceId));
  if (state.cameraId && devices.some(d => d.deviceId === state.cameraId)) select.value = state.cameraId;
}
function resetCamera() {
  stopRecognition();
  state.streamKind = 'none'; state.activeVideoURL = '';
  $('camera-video').hidden = true; $('camera-video').srcObject = null;
  $('annotated-stream').hidden = true; $('annotated-stream').removeAttribute('src');
  $('workspace-demo').hidden = false; $('camera-connect').hidden = false;
  $('camera-overlay-label').lastChild.textContent = '示意画面';
  $('camera-status').textContent = '未连接'; $('camera-status').classList.remove('live');
  $('camera-source').textContent = '等待相机接入';
  $('vision-note').textContent = '连接相机后可查看工作区；识别结果由视觉服务提供。';
  $('stop-camera').disabled = true;
  $('recognize-camera').disabled = true;
}
function stopCamera() {
  state.stream?.getTracks().forEach(track => track.stop()); state.stream = null; resetCamera();
}
function connectAnnotated(url) {
  try {
    const parsed = new URL(url, location.href);
    if (!['http:', 'https:'].includes(parsed.protocol)) return;
    state.streamKind = 'annotated'; state.activeVideoURL = url;
    const image = $('annotated-stream'); image.hidden = false; image.src = parsed.href;
    $('workspace-demo').hidden = true; $('camera-connect').hidden = true;
    $('camera-overlay-label').lastChild.textContent = '正在连接识别视频';
    image.onload = () => {
      if (state.streamKind !== 'annotated') return;
      $('camera-status').textContent = '识别画面'; $('camera-status').classList.add('live');
      $('camera-source').textContent = '工作区右侧相机 · 视觉服务';
      $('camera-overlay-label').lastChild.textContent = '实时识别';
      $('vision-note').textContent = '此画面由视觉服务输出，识别框与视频帧一同传输。';
    };
    image.onerror = () => {
      if (state.streamKind !== 'annotated') return;
      resetCamera(); state.failedVideoURL = url; toast('识别视频连接失败，请检查视觉服务；刷新页面可重新连接。', true);
    };
  } catch { toast('识别视频地址无效。', true); }
}
$('start-camera').addEventListener('click', async () => {
  if (state.cameraPending) return;
  if (!navigator.mediaDevices?.getUserMedia) { $('camera-message').textContent = '请使用 localhost 或 HTTPS 打开页面，以授权摄像头。'; return; }
  state.cameraPending = true; $('start-camera').disabled = true;
  let stream = null;
  try {
    const deviceId = $('camera-select').value;
    // Request only the camera explicitly selected by the user; never access the microphone.
    stream = await navigator.mediaDevices.getUserMedia({ audio: false,
      video: { ...(deviceId ? { deviceId: { exact: deviceId } } : {}), width: { ideal: 1920 }, height: { ideal: 1080 } } });
    stopCamera(); state.stream = stream; state.streamKind = 'local';
    const video = $('camera-video'); video.srcObject = stream; video.hidden = false;
    await video.play();
    $('recognize-camera').disabled = false;
    $('workspace-demo').hidden = true; $('camera-connect').hidden = true;
    $('camera-status').textContent = '原始画面'; $('camera-status').classList.add('live');
    $('camera-overlay-label').lastChild.textContent = '本地相机 · 原始画面';
    $('camera-source').textContent = stream.getVideoTracks()[0]?.label || '本地摄像头';
    $('vision-note').textContent = '原始视频已连接。点击“开始识别”显示本机模型识别出的物体框。';
    $('camera-message').textContent = '已连接。若画面不对，请换选工作区右侧摄像头后重新连接。';
    state.cameraId = stream.getVideoTracks()[0]?.getSettings().deviceId || deviceId;
    persist(); await fillCameras(); $('stop-camera').disabled = false;
    $('settings-dialog').close();
    stream.getVideoTracks()[0]?.addEventListener('ended', () => {
      if (state.stream !== stream) return;
      stopCamera(); toast('摄像头已断开。');
    });
  } catch (error) {
    stream?.getTracks().forEach(track => track.stop());
    if (state.stream === stream) stopCamera();
    $('camera-message').textContent = error.name === 'NotAllowedError' ? '相机权限未开启，请在浏览器地址栏允许相机访问。'
      : error.name === 'NotReadableError' ? '相机可能正被其他程序占用，请关闭预览后重试。'
        : error.name === 'OverconstrainedError' ? '所选摄像头不可用，请重新选择。' : '相机连接失败，请检查设备与浏览器权限。';
  } finally { state.cameraPending = false; $('start-camera').disabled = false; }
});
$('stop-camera').addEventListener('click', () => { stopCamera(); $('camera-message').textContent = '相机已断开。'; });
window.addEventListener('pagehide', stopCamera);

function stopRecognition() {
  state.recognizing = false; state.visionGeneration++;
  clearTimeout(state.visionTimer); state.lastFrame = null;
  $('detection-canvas').hidden = true; $('detection-list').replaceChildren();
  for (const key of ['frameId', 'frameSha256', 'source']) delete $('detection-canvas').dataset[key];
  $('recognize-camera').textContent = '开始识别';
}
function drawRecognition() {
  if (!state.lastFrame) return;
  const { result, image } = state.lastFrame;
  const canvas = $('detection-canvas');
  canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
  const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
  const scale = Math.max(1, canvas.width / 700);
  ctx.font = `600 ${14 * scale}px "Segoe UI",sans-serif`;
  ctx.lineWidth = 2 * scale;
  $('detection-list').replaceChildren();
  for (const det of result.detections) {
    const gesture = state.selected.indexOf(det.class_name) + 1;
    const [x, y, right, bottom] = det.bbox_xyxy_raw;
    const label = `${gesture ? gesture + ' · ' : ''}${itemFor(det.class_name)?.name || det.class_name} ${Math.round(det.confidence * 100)}%`;
    ctx.strokeStyle = gesture ? '#bce6a2' : '#ffe6a6';
    ctx.strokeRect(x, y, right - x, bottom - y);
    const labelWidth = ctx.measureText(label).width + 12 * scale;
    const left = Math.max(0, Math.min(x, canvas.width - labelWidth));
    const top = Math.max(0, y - 25 * scale);
    ctx.fillStyle = gesture ? '#075c50' : '#374d45';
    ctx.fillRect(left, top, labelWidth, 23 * scale);
    ctx.fillStyle = '#fff'; ctx.fillText(label, left + 6 * scale, top + 16 * scale);
    const chip = document.createElement('span');
    chip.className = gesture ? 'detected selected' : 'detected';
    chip.textContent = `${gesture ? gesture + ' · ' : ''}${itemFor(det.class_name)?.name || det.class_name} ${Math.round(det.confidence * 100)}%`;
    $('detection-list').append(chip);
  }
  if (!result.detections.length) $('detection-list').textContent = '本帧未识别到支持的物体。';
}
async function recognize(payload, generation) {
  state.visionBusy = true;
  $('sample-vision').disabled = true; $('photo-vision').disabled = true;
  try {
    const sample = payload.source === 'sample_replay';
    const result = await api(sample ? '/api/vision/sample' : '/api/vision/infer', {
      method: 'POST', body: JSON.stringify(payload), timeoutMs: 45000 });
    if (generation !== state.visionGeneration) return;
    if (result.frame_id !== payload.frame_id || result.source !== payload.source || result.physical_execution !== false
        || !result.image?.startsWith('data:image/jpeg;base64,')) throw new Error('识别帧对应关系不正确。');
    const image = new Image(); image.src = result.image; await image.decode();
    if (generation !== state.visionGeneration) return;
    if (image.naturalWidth !== result.image_size_wh[0] || image.naturalHeight !== result.image_size_wh[1]) throw new Error('识别图像尺寸不匹配。');
    state.lastFrame = { result, image }; drawRecognition();
    $('camera-video').hidden = true; $('workspace-demo').hidden = true; $('camera-connect').hidden = true;
    $('detection-canvas').hidden = false;
    const live = payload.source === 'camera';
    $('camera-status').textContent = live ? '相机识别' : sample ? '样例回放' : '照片识别';
    $('camera-status').classList.toggle('live', live);
    $('camera-overlay-label').lastChild.textContent = live ? '相机识别 · 同帧物体框' : sample ? '历史样例 · 非实时画面' : '照片 · 非实时画面';
    $('camera-source').textContent = live ? state.stream?.getVideoTracks()[0]?.label || '所选相机'
      : sample ? `历史采集 ${new Date(result.sample_captured_utc).toLocaleDateString('zh-CN')}` : '本次选择的照片';
    $('vision-note').textContent = `本机CPU识别 · ${(result.total_ms / 1000).toFixed(2)}秒/帧 · 编号按当前选择显示。此预览不发送机械臂动作。`;
    $('detection-canvas').dataset.frameId = result.frame_id;
    $('detection-canvas').dataset.frameSha256 = result.frame_sha256;
    $('detection-canvas').dataset.source = result.source;
  } finally {
    state.visionBusy = false;
    $('sample-vision').disabled = false; $('photo-vision').disabled = false;
  }
}
function visionFailure(error, generation) {
  if (generation !== state.visionGeneration) return;
  const local = state.streamKind === 'local';
  stopRecognition();
  $('camera-video').hidden = !local;
  $('workspace-demo').hidden = local; $('camera-connect').hidden = local;
  $('camera-status').textContent = local ? '原始画面' : '识别未完成';
  $('camera-status').classList.remove('live');
  $('camera-overlay-label').lastChild.textContent = local ? '原始画面 · 识别已暂停' : '示意画面';
  $('vision-note').textContent = error.name === 'AbortError' ? '本帧识别超时，已暂停；可稍后重新开始。' : error.message;
  toast($('vision-note').textContent, true);
}
async function recognitionTick(generation) {
  if (!state.recognizing || generation !== state.visionGeneration) return;
  try {
    const video = $('camera-video');
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    if (!canvas.width || !canvas.height) throw new Error('相机尚未准备好，请稍后重试。');
    canvas.getContext('2d').drawImage(video, 0, 0);
    await recognize({ source: 'camera', frame_id: crypto.randomUUID(), image: canvas.toDataURL('image/png') }, generation);
    if (state.recognizing && generation === state.visionGeneration) state.visionTimer = setTimeout(() => recognitionTick(generation), 500);
  } catch (error) { visionFailure(error, generation); }
}
$('recognize-camera').addEventListener('click', () => {
  if (state.recognizing) {
    stopRecognition(); $('camera-video').hidden = false;
    $('camera-status').textContent = '原始画面'; $('camera-overlay-label').lastChild.textContent = '本地相机 · 原始画面';
    $('vision-note').textContent = '识别已暂停，相机原始画面继续显示。'; return;
  }
  if (state.visionBusy || !state.stream) return;
  stopRecognition(); state.recognizing = true;
  $('recognize-camera').textContent = '暂停识别';
  $('vision-note').textContent = '正在载入模型并识别，首次启动需稍候…';
  recognitionTick(state.visionGeneration);
});
$('sample-vision').addEventListener('click', async () => {
  if (state.visionBusy) return;
  stopCamera(); state.streamKind = 'sample'; const generation = state.visionGeneration;
  $('vision-note').textContent = '正在对历史样例运行真实识别模型，首次启动需稍候…';
  try { await recognize({ source: 'sample_replay', frame_id: crypto.randomUUID() }, generation); }
  catch (error) { visionFailure(error, generation); }
});
$('photo-vision').addEventListener('click', () => $('vision-file').click());
$('vision-file').addEventListener('change', async event => {
  const file = event.target.files[0]; event.target.value = '';
  if (!file || state.visionBusy) return;
  stopCamera(); state.streamKind = 'photo'; const generation = state.visionGeneration;
  try {
    const image = await createImageBitmap(file);
    if (generation !== state.visionGeneration) { image.close(); return; }
    if (image.width * image.height > 1920 * 1080 || Math.max(image.width, image.height) > 1920) {
      image.close(); throw new Error('请使用不超过1920×1080像素的照片。');
    }
    const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
    canvas.getContext('2d').drawImage(image, 0, 0); image.close();
    $('vision-note').textContent = '正在识别本次选择的照片…';
    await recognize({ source: 'photo', frame_id: crypto.randomUUID(), image: canvas.toDataURL('image/png') }, generation);
  } catch (error) { visionFailure(error, generation); }
});

renderFixed(); readRoute(); renderDevice();
async function boot() {
  try { state.config = await api('/api/config'); renderDevice(); await pollStatus(); }
  catch { toast('页面预览已打开；请运行启动脚本连接工作台服务。'); }
  state.pollTimer = setInterval(pollStatus, 3000);
}
boot();
