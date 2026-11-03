"""Offline binding of Mode B restock intents to exact native stages/events.

No serial, camera or FPGA access. Completion below is simulated, not observed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.restock_workflow import RestockWorkflow

# Ordered groups are the adapter boundary for the future task executor.
GROUPS = (
    ('RESTOCK_APPROACH_PUBLIC', ('HOME_OPEN', 'RESTOCK_INNER_OPEN',
                                'RESTOCK_BUFFER_OPEN', 'RESTOCK_PUBLIC_HIGH')),
    ('RESTOCK_DESCEND_PUBLIC', ('RESTOCK_PUBLIC_DESCEND',)),
    ('RESTOCK_CLOSE_PUBLIC', ('GRASP_PUBLIC',)),
    ('RESTOCK_LIFT_PUBLIC', ('RESTOCK_PUBLIC_LIFT',)),
    ('RESTOCK_RETURN_SOURCE_HIGH', ('RESTOCK_RETURN_BUFFER', 'RESTOCK_RETURN_INNER',
                                   'RESTOCK_SOURCE_HIGH')),
    ('RESTOCK_DESCEND_SOURCE', ('RESTOCK_SOURCE_DESCEND',)),
    ('RESTOCK_RELEASE_SOURCE', ('RELEASE_SOURCE',)),
    ('RESTOCK_WITHDRAW_SOURCE', ('RESTOCK_SOURCE_EXIT_CLEARANCE',
                                'RESTOCK_SOURCE_EXIT_UP', 'RESTOCK_SOURCE_EXIT_RECENTER')),
    ('RESTOCK_HOME', ('RESTOCK_HOME', 'PARK_CLOSE')),
)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def steps(plan):
    """Retain exact physical command order, including gripper event boundaries."""
    output = []

    def event(item):
        require(item is not None, 'Missing gripper event')
        wire = json.loads(item['wire_json'])
        require(wire['T'] == 106, 'Gripper event must use T106')
        output.append({'label': item['label'], 'kind': 'gripper_event',
                       'wire_json': [item['wire_json']]})

    event(plan.get('initial_event'))
    for stage in plan['stages']:
        frames = stage['stage']['stream_frames']
        require(bool(frames), 'Empty motion stage')
        output.append({'label': stage['phase'], 'kind': 'motion',
                       'wire_json': [frame['wire_json'] for frame in frames]})
        if stage['phase'] in plan['event_after_stage']:
            event(plan['event_after_stage'][stage['phase']])
    event(plan.get('final_event'))
    return output


def rehearse(plan, record):
    require(plan['task_kind'] == 'RESTOCK', 'Normal restock plan required')
    require(plan['original_pickup'] == record['original_pickup'], 'Original pickup differs')
    require(plan['return_centre_mm'] == record['original_pickup']['centre_mm'], 'Return target differs')
    require(plan['request']['object_class'] == record['object_class'], 'Object class differs')
    require(plan['public_pickup_centre_mm'][:2] == [300, 200], 'Public point differs')
    commands = steps(plan)
    expected_labels = [label for _, group in GROUPS for label in group]
    require([s['label'] for s in commands] == expected_labels,
            'Motion/event order does not match workflow mapping')

    selection = record['selection']
    workflow = RestockWorkflow()
    # Emulate a completed preceding delivery, never claim live completion.
    workflow.delivered(selection, record, empty_home_completed=True)
    require(workflow.select(selection, 'rehearsal', empty=True, at_home=True)['intent'] == 'NONE',
            'A held digit unexpectedly retriggered restock')
    workflow.background()
    task_id = record['original_task_id'] + ':offline-rehearsal'
    workflow.select(selection, task_id, empty=True, at_home=True)
    trace = []
    cursor = 0
    digest = hashlib.sha256()
    requests = 0
    for phase, labels in GROUPS:
        require(workflow.phase == phase, 'Workflow phase mismatch: ' + phase)
        require(not workflow.slots[selection]['available'], 'Inventory restored before HOME')
        release = phase == 'RESTOCK_RELEASE_SOURCE'
        if release:
            workflow.event(task_id, 'RELEASE_SUBMITTED')
        count = 0
        for label in labels:
            item = commands[cursor]
            require(item['label'] == label, 'Stage cursor differs')
            for wire in item['wire_json']:
                digest.update((wire + '\n').encode('utf8'))
                count += 1
            cursor += 1
        requests += count
        result = workflow.event(task_id, 'DONE', completed_phase=phase)
        trace.append({'phase': phase, 'ordered_commands': list(labels), 'requests': count,
                      'release_submission_before_done': release,
                      'completion_source': 'OFFLINE_EMULATED',
                      'inventory_restored': workflow.slots[selection]['available']})
    require(cursor == len(commands), 'Unmapped commands remain')
    require(workflow.phase == 'IDLE' and result['inventory_restored'], 'Restock did not finish')
    require(not result['physical_placement_verified'], 'Offline run claimed physical success')
    require(workflow.select(selection, 'repeat', empty=True, at_home=True)['intent'] == 'NONE',
            'Digit hold retriggered after HOME')
    workflow.background()
    require(workflow.select(selection, 'new-pick', empty=True, at_home=True)['intent'] == 'DYNAMIC_VISION_PICKUP',
            'Restored selection did not return to dynamic pickup')
    return {'schema': 'gesture.mode_b.restock_rehearsal.v1', 'passed': True,
            'object_class': record['object_class'], 'selection': selection,
            'original_task_id': record['original_task_id'],
            'public_centre_mm': plan['public_pickup_centre_mm'],
            'public_yaw_deg': plan['request']['pickup']['yaw_deg'],
            'return_centre_mm': plan['return_centre_mm'],
            'motion_stages': len(plan['stages']), 'gripper_events': len(commands) - len(plan['stages']),
            'requests': requests, 'ordered_wire_lf_sha256': digest.hexdigest(), 'trace': trace,
            'rearm_before_and_after_verified': True,
            'inventory_restored_in_emulation_only': True,
            'hardware_accessed': False, 'physical_restock_accepted': False,
            'fpga_web_adapter_implemented': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--verification', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    plan, sim = read(args.plan), read(args.verification)
    require(sim['route_sha256'] == sha(args.plan) and sim['passed'] and not sim['mesh_collisions'],
            'Matching mesh verification required')
    origin = Path(plan['origin_record_file'])
    require(sha(origin) == plan['origin_record_sha256'], 'Origin record changed')
    record = read(origin)
    for key in ('delivery_plan', 'delivery_result'):
        require(sha(record[key + '_file']) == record[key + '_sha256'], 'Bound delivery changed')
    report = rehearse(plan, record)
    report.update(plan_sha256=sha(args.plan), verification_sha256=sha(args.verification),
                  origin_record_sha256=sha(origin))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'trace'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
