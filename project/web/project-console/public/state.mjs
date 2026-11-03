export const CATALOG = Object.freeze([
  { id: 'red_cube', name: '红色木块', subtitle: 'RED CUBE', icon: 'cube', color: 'red', recognition: 'registered' },
  { id: 'yellow_cube', name: '黄色木块', subtitle: 'YELLOW CUBE', icon: 'cube', color: 'yellow', recognition: 'registered' },
  { id: 'blue_cube', name: '蓝色木块', subtitle: 'BLUE CUBE', icon: 'cube', color: 'blue', recognition: 'registered' },
  { id: 'small_canister', name: '圆柱', subtitle: 'CYLINDER', icon: 'cylinder', color: 'teal', recognition: 'registered' },
  { id: 'eraser', name: '橡皮', subtitle: 'ERASER', icon: 'eraser', color: 'pink', recognition: 'registered' },
  { id: 'scissors', name: '剪刀', subtitle: 'SCISSORS', icon: 'scissors', color: 'silver', recognition: 'registered' },
]);

export function toggleSelection(selected, id) {
  if (selected.includes(id)) return { selected: selected.filter(item => item !== id), limit: false };
  if (selected.length >= 3) return { selected: [...selected], limit: true };
  return { selected: [...selected, id], limit: false };
}

export function bindingsFor(mode, selected) {
  const ids = mode === 'A' ? ['red_cube', 'yellow_cube', 'blue_cube'] : selected;
  return ids.map((object_id, index) => ({ gesture: index + 1, object_id }));
}

export function matchesApplied(view, selected, status) {
  if (!status?.connected || status.active_mode !== view) return false;
  const expected = bindingsFor(view, selected);
  const actual = status.gesture_bindings || [];
  return expected.length === actual.length && expected.every((binding, i) =>
    binding.gesture === actual[i]?.gesture && binding.object_id === actual[i]?.object_id);
}

export function validateCustom(name, id, catalog) {
  if (!name.trim() || name.trim().length > 16) return '请输入1—16字的物体名称。';
  if (!/^[a-z][a-z0-9_]{1,39}$/.test(id)) return '类别ID需为2—40位小写字母、数字或下划线，以字母开头。';
  if (catalog.some(item => item.id === id || item.name === name.trim())) return '这个名称或类别ID已存在。';
  return '';
}

export function restoreState(raw) {
  const fallback = { selected: [], custom: [], device: null, cameraId: '' };
  try {
    const value = JSON.parse(raw);
    if (!value || typeof value !== 'object') return fallback;
    const custom = [];
    for (const item of Array.isArray(value.custom) ? value.custom.slice(0, 40) : []) {
      if (typeof item?.name !== 'string' || typeof item?.id !== 'string' || validateCustom(item.name, item.id, [...CATALOG, ...custom])) continue;
      custom.push({ id: item.id, name: item.name.trim(), subtitle: 'CUSTOM OBJECT',
        icon: ['cube', 'cylinder', 'package'].includes(item.icon) ? item.icon : 'package',
        color: 'teal', recognition: 'pending' });
    }
    const known = new Set([...CATALOG, ...custom].map(item => item.id));
    return {
      selected: [...new Set(Array.isArray(value.selected) ? value.selected.filter(id => known.has(id)) : [])].slice(0, 3),
      custom,
      device: typeof value.device?.name === 'string' && typeof value.device?.model === 'string'
        ? { name: value.device.name.slice(0, 40), model: value.device.model.slice(0, 80) } : null,
      cameraId: typeof value.cameraId === 'string' ? value.cameraId : '',
    };
  } catch { return fallback; }
}
