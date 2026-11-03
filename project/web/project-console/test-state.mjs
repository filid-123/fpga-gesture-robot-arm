import test from 'node:test';
import assert from 'node:assert/strict';
import { bindingsFor, matchesApplied, restoreState, toggleSelection, validateCustom, CATALOG } from './public/state.mjs';

test('selection order assigns gestures; fourth selection is refused', () => {
  let selected = [];
  for (const id of ['eraser', 'red_cube', 'small_canister']) selected = toggleSelection(selected, id).selected;
  const result = toggleSelection(selected, 'scissors');
  assert.equal(result.limit, true);
  assert.deepEqual(result.selected, selected);
  assert.deepEqual(bindingsFor('B', selected), [
    { gesture: 1, object_id: 'eraser' }, { gesture: 2, object_id: 'red_cube' }, { gesture: 3, object_id: 'small_canister' },
  ]);
});
test('cancel compacts numbering and reselect appends at the end', () => {
  let selected = toggleSelection(['red_cube', 'eraser', 'small_canister'], 'eraser').selected;
  assert.deepEqual(bindingsFor('B', selected)[1], { gesture: 2, object_id: 'small_canister' });
  selected = toggleSelection(selected, 'eraser').selected;
  assert.equal(selected[2], 'eraser');
});
test('page mode and device mode do not imply one another', () => {
  assert.equal(matchesApplied('B', ['red_cube'], { connected: false, active_mode: 'B', gesture_bindings: bindingsFor('B', ['red_cube']) }), false);
  assert.equal(matchesApplied('B', ['eraser'], { connected: true, active_mode: 'A', gesture_bindings: bindingsFor('A', []) }), false);
  assert.equal(matchesApplied('B', ['eraser'], { connected: true, active_mode: 'B', gesture_bindings: bindingsFor('B', ['eraser']) }), true);
  assert.equal(matchesApplied('B', ['eraser'], { connected: true, active_mode: 'B', gesture_bindings: [{ object_id: 'eraser', gesture: 1 }] }), true);
});
test('mode A stays fixed and does not consume mode B choices', () => {
  assert.deepEqual(bindingsFor('A', ['scissors']).map(x => x.object_id), ['red_cube', 'yellow_cube', 'blue_cube']);
});
test('custom labels are validated and pending, never automatically trained', () => {
  assert.equal(validateCustom('螺丝刀', 'screwdriver', CATALOG), '');
  assert.notEqual(validateCustom('螺丝刀', '../bad', CATALOG), '');
  assert.notEqual(validateCustom('红色木块', 'another_cube', CATALOG), '');
  const restored = restoreState(JSON.stringify({ custom: [{ id: 'screwdriver', name: '螺丝刀', recognition: 'registered' }], selected: ['screwdriver'] }));
  assert.equal(restored.custom[0].recognition, 'pending');
});
test('malformed/stale storage is sanitized without accepting a stored active device mode', () => {
  assert.deepEqual(restoreState('{bad').selected, []);
  const result = restoreState(JSON.stringify({ selected: ['red_cube', 'missing', 'red_cube', 'eraser', 'scissors', 'yellow_cube'], active_mode: 'B', custom: [null] }));
  assert.deepEqual(result.selected, ['red_cube', 'eraser', 'scissors']);
  assert.equal(result.active_mode, undefined);
});
