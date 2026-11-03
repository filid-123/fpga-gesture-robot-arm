"""Verify the portable Mode B handoff offline; never opens robot/board ports."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

NAMES = ('b', 's', 'e', 't', 'r', 'g')
WIRE_NAMES = ('base', 'shoulder', 'elbow', 'wrist', 'roll', 'hand')
PHASES = ('DIRECT_PREGRASP', 'DESCEND', 'LIFT', 'INNER_HOLD', 'BUFFER',
          'PREPLACE', 'PLACE', 'RELEASE_CLEARANCE', 'RETREAT', 'RETURN_CLEAR',
          'INNER_RETURN', 'RETURN_LOW_HOME')
EVENTS = {'DIRECT_PREGRASP': ('OPEN_HIGH', 'open_before_descent_wire_json'),
          'DESCEND': ('CLOSE_SOURCE', 'close_after_descent_wire_json'),
          'PLACE': ('RELEASE', 'release_wire_json')}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def q16_hex(command):
    words = [round(float(command[name]) * 65536) for name in WIRE_NAMES]
    require(all(-(2**31) <= word < 2**31 for word in words), 'Q16 overflow')
    return ''.join(f'{word & 0xffffffff:08x}' for word in reversed(words))


def verify(root, observed=None, object_class=None, pl_samples=None):
    root = Path(root).resolve()
    manifest = read(root / 'MANIFEST.json')
    expected = manifest['files']
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    require(actual == set(expected) | {'MANIFEST.json'}, 'Manifest file set differs')
    for name, record in expected.items():
        path = (root / name).resolve()
        require(path.is_relative_to(root), 'Manifest path escapes package')
        require(path.stat().st_size == record['bytes'] and digest(path) == record['sha256'],
                'File hash/size mismatch: ' + name)
    package = read(root / 'PACKAGE.json')
    require(package['hardware_execution_enabled'] is False, 'Offline package expected')
    home = read(root / 'HOME.json')
    require(home['joint_order'] == list(NAMES), 'HOME joint order')
    require(home['native_return_target']['T'] == 122, 'HOME degree reference type')
    require(home['firmware_joint_q16'] == [round(home['firmware_joint_rad'][n]*65536) for n in NAMES],
            'HOME fixed point differs')
    summaries = []
    for item in package['objects']:
        cls = item['object_class']
        folder = root / 'objects' / cls
        plan = read(folder / 'evidence/PLAN.json')
        result = read(folder / 'evidence/RESULT.json')
        sim = read(folder / 'evidence/COPPELIA.json')
        acceptance = read(folder / 'evidence/ACCEPTANCE.json')
        plan_hash = digest(folder / 'evidence/PLAN.json')
        run_hash = digest(folder / 'evidence/RESULT.json')
        require(plan_hash == result['route_sha256'] == sim['route_sha256'] == acceptance['plan_sha256'],
                cls + ': source plan binding differs')
        require(run_hash == acceptance.get('run_sha256', acceptance.get('result_sha256')),
                cls + ': accepted run binding differs')
        require(item['operator_accepted'] is True and 'ACCEPTED' in acceptance['status'],
                cls + ': physical acceptance missing')
        require(acceptance.get('physical_pickup_delivery_home_operator_accepted',
                               acceptance.get('physical_grip_delivery_return_accepted',
                                              acceptance.get('physical_pickup_confirmed'))) is True,
                cls + ': accepted physical pickup missing')
        require(sim['passed'] is True and sim['mesh_collisions'] == [], cls + ': simulation failed')
        require(plan['offline_verification']['passed'] is True, cls + ': offline check missing')
        require([s['phase'] for s in plan['stages']] == list(PHASES) == result['completed_stages'],
                cls + ': phase sequence differs')
        require(plan['request']['object_class'] == cls, cls + ': class differs')
        require(plan['request']['destination']['support_centre_mm'] == [285, 195, 150],
                cls + ': support semantics differ')
        require(item['physically_tested_speed_multiplier'] == plan['speed_multiplier'], cls + ': speed differs')
        require(plan['physical_general_mapping_calibrated'] is False and plan['fpga_trajectory'] is False,
                cls + ': historical acceptance scope changed')
        exported = rows(folder / 'sequence.jsonl')
        raw = (folder / 'commands.jsonl').read_text(encoding='utf-8').splitlines()
        gold = (folder / 'motion_q16.mem').read_text(encoding='ascii').splitlines()
        phase_map = read(folder / 'phase_map.json')
        index = 0
        motion_index = 0
        for stage_number, stage in enumerate(plan['stages']):
            phase = stage['phase']
            details = stage['stage']
            dt = details['period_s']
            require(dt == (0.04 if stage_number < 3 else 0.02), cls + ': stream period differs')
            require(phase_map[stage_number]['request_start_index'] == index, cls + ': phase boundary differs')
            require(phase_map[stage_number]['phase'] == phase and
                    phase_map[stage_number]['period_s'] == dt and
                    phase_map[stage_number]['motion_samples'] == len(details['stream_frames']) and
                    phase_map[stage_number]['target_firmware_rad'] == details['target_firmware_rad'],
                    cls + ': phase metadata differs')
            for frame_number, frame in enumerate(details['stream_frames']):
                row = exported[index]
                command = json.loads(frame['wire_json'])
                require(command['T'] == 102, cls + ': motion type differs')
                require(all(type(command[n]) in (int, float) and math.isfinite(command[n]) for n in WIRE_NAMES),
                        cls + ': nonfinite joint')
                require(0 < command['spd'] <= 4095 and 0 < command['acc'] <= 254, cls + ': wire limits')
                require([command[n] for n in WIRE_NAMES] == [frame['command_firmware_rad'][n] for n in NAMES],
                        cls + ': radian mapping differs')
                require(row == {'index': index, 'label': phase, 'kind': 'motion',
                                'sample_in_stage': frame_number, 'period_s': dt,
                                'stage_offset_s': frame_number * dt, 'wire_json': frame['wire_json']},
                        cls + ': exported sample differs')
                require(raw[index] == frame['wire_json'], cls + ': raw wire differs')
                require(gold[motion_index] == q16_hex(command), cls + ': Q16 encoding differs')
                require(result['requests'][index]['label'] == phase and
                        result['requests'][index]['wire_json'] == frame['wire_json'], cls + ': actual wire differs')
                motion_index += 1
                index += 1
            require(phase_map[stage_number]['request_end_index_inclusive'] == index-1, cls + ': phase end differs')
            if phase in EVENTS:
                label, key = EVENTS[phase]
                index = check_event(index, label, plan[key], exported, raw, result, cls)
        index = check_event(index, 'PARK_CLOSE', plan['park_close_wire_json'], exported, raw, result, cls)
        require(index == len(exported) == len(raw) == result['motion_requests'] == len(result['requests']),
                cls + ': request count differs')
        require(motion_index == len(gold), cls + ': golden sample count differs')
        require(item['requests'] == index and item['motion_samples'] == motion_index,
                cls + ': package summary differs')
        if object_class == cls:
            if observed:
                other = rows(observed)
                require(len(other) == index, cls + ': observed request count differs')
                for a, b in zip(exported, other):
                    require(a['index'] == b['index'] and a['label'] == b['label'] and
                            a['wire_json'] == b['wire_json'], cls + ': observed request mismatch')
            if pl_samples:
                other = Path(pl_samples).read_text(encoding='ascii').splitlines()
                require([line.strip().lower() for line in other] == gold, cls + ': PL motion samples mismatch')
        summaries.append({'object_class': cls, 'requests': index, 'motion_samples': motion_index,
                          'stages': len(PHASES), 'speed_multiplier': plan['speed_multiplier']})
    require(not (observed or pl_samples) or object_class in {x['object_class'] for x in summaries},
            'Select --object-class for a board comparison')
    return {'passed': True, 'files_checked': len(expected), 'objects': summaries,
            'hardware_accessed': False, 'fpga_integration_accepted': False}


def check_event(index, label, wire, exported, raw, result, cls):
    require(json.loads(wire)['T'] == 106, cls + ': event type differs')
    require(exported[index] == {'index': index, 'label': label, 'kind': 'gripper_event', 'wire_json': wire},
            cls + ': gripper event differs')
    require(raw[index] == wire and result['requests'][index]['wire_json'] == wire and
            result['requests'][index]['label'] == label, cls + ': actual event differs')
    return index + 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--object-class', choices=('red_cube', 'eraser', 'small_canister'))
    parser.add_argument('--observed', type=Path, help='Board JSONL: index,label,wire_json, including hand events')
    parser.add_argument('--pl-samples', type=Path, help='192-bit motion-only hex lines, b in lowest32bits')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root, args.observed, args.object_class, args.pl_samples), ensure_ascii=False))
    except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        parser.exit(1, 'HANDOFF_VERIFY_FAILED: ' + str(exc) + '\n')
