"""Retiming of an accepted restock path; gripper events and geometry stay fixed."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

from prepare_mode_b_restock import Builder, NAMES, bound_delivery, check_payload_path, digest, read, write

WIRE_NAMES = ('base', 'shoulder', 'elbow', 'wrist', 'roll', 'hand')


def profile_of(baseline, factor):
    factor = float(factor)
    if not math.isfinite(factor) or factor != 2.0 or baseline.get('restock_motion_speed'):
        raise ValueError('Apply requested2x once to the accepted baseline')
    if baseline['request']['object_class'] != 'red_cube' or not baseline.get('public_grasp_depth_correction'):
        raise ValueError('Accepted red depth8 route required')
    first = json.loads(baseline['stages'][0]['stage']['stream_frames'][0]['wire_json'])
    native_speed = round(first['spd'] * factor)
    requested_acc = first['acc'] * factor**2
    native_acc = min(254, round(requested_acc))
    if not 0 < native_speed <= 4095:
        raise ValueError('Speed exceeds native range')
    effective = baseline['speed_multiplier'] * factor
    return {'factor_from_accepted': factor, 'effective_reference_multiplier': effective,
            'native_spd': native_speed, 'native_acc': native_acc,
            'requested_native_acc': requested_acc,
            'velocity_bound_deg_s': 12 * effective,
            'acceleration_bound_deg_s2': 24 * effective**2 * native_acc / requested_acc,
            'period_s': .02, 'gripper_events_changed': False}


def resample(stage, profile):
    frames = stage['stage']['stream_frames']
    old = np.array([[f['command_firmware_rad'][n] for n in NAMES] for f in frames])
    spline = PchipInterpolator(np.linspace(0, 1, len(old)), old[:, :5], axis=0)
    period = profile['period_s']
    duration = (len(frames)-1) * stage['stage']['period_s'] / profile['factor_from_accepted']
    for _ in range(12):
        arm = spline(np.linspace(0, 1, max(2, math.ceil(duration / period)+1)))
        pad = np.vstack([arm[0], arm[0], arm, arm[-1], arm[-1]])
        velocity = float(abs(np.diff(pad, axis=0)).max()) / period * 180 / math.pi
        acceleration = float(abs(np.diff(pad, n=2, axis=0)).max()) / period**2 * 180 / math.pi
        ratio = max(velocity / profile['velocity_bound_deg_s'],
                    math.sqrt(acceleration / profile['acceleration_bound_deg_s2']))
        if ratio <= 1.00001:
            break
        duration *= ratio * 1.02
    else:
        raise ValueError('Speed retiming failed')
    output = deepcopy(stage)
    new_frames = []
    for values in arm:
        q = [*values.tolist(), float(old[0, 5])]
        wire = {'T': 102, **dict(zip(WIRE_NAMES, q)),
                'spd': profile['native_spd'], 'acc': profile['native_acc']}
        new_frames.append({'wire_json': json.dumps(wire, separators=(',', ':')),
                           'command_firmware_rad': dict(zip(NAMES, q)),
                           'model_q': [*q[:5], frames[0]['model_q'][5]]})
    output['stage'].update(period_s=period, stream_frames=new_frames,
                           nominal_motion_seconds=len(new_frames) * period)
    output['commissioning_tolerance_profile'].update(
        native_stream_spd=profile['native_spd'], native_stream_acc=profile['native_acc'], native_period_s=period)
    return output, velocity, acceleration


def validate_speed(plan):
    info = plan['restock_motion_speed']
    if (digest(info['baseline_plan_file']) != info['baseline_plan_sha256'] or
            digest(info['acceptance_file']) != info['acceptance_sha256']):
        raise ValueError('Speed baseline/acceptance changed')
    baseline = read(info['baseline_plan_file'])
    accepted = read(info['acceptance_file'])
    if (accepted['status'] != 'OPERATOR_ACCEPTED_COMPLETE_RESTOCK' or
            accepted['plan_sha256'] != info['baseline_plan_sha256'] or
            digest(accepted['result_file']) != accepted['result_sha256']):
        raise ValueError('Speed baseline lacks bound physical acceptance')
    limits = profile_of(baseline, info['factor_from_accepted'])
    if any(info[key] != value for key, value in limits.items()):
        raise ValueError('Speed profile or acceleration cap differs')
    for key in ('initial_event', 'event_after_stage', 'final_event', 'original_pickup',
                'origin_record_sha256', 'public_pickup_centre_mm', 'public_model_pickup_pose',
                'tcp_from_object', 'released_object_pose', 'return_centre_mm',
                'public_grasp_depth_correction'):
        if plan[key] != baseline[key]:
            raise ValueError('Retiming changed grasp/place geometry or gripper event: ' + key)
    if len(plan['stages']) != len(baseline['stages']):
        raise ValueError('Retiming changed stage count')
    for actual, old in zip(plan['stages'], baseline['stages']):
        if (actual['phase'] != old['phase'] or actual['carrying'] != old['carrying'] or
                actual['start_firmware_rad'] != old['start_firmware_rad'] or
                actual['stage']['target_firmware_rad'] != old['stage']['target_firmware_rad']):
            raise ValueError('Retiming changed stage identity or endpoints')
        expected, _, _ = resample(old, limits)
        if actual['stage'] != expected['stage']:
            raise ValueError('Retimed wire samples or period differ from checked timing')
    return True


def prepare(baseline_path, accepted_path, factor=2):
    baseline_path, accepted_path = Path(baseline_path).resolve(), Path(accepted_path).resolve()
    baseline = read(baseline_path)
    profile = profile_of(baseline, factor)
    info = dict(profile, baseline_plan_file=str(baseline_path), baseline_plan_sha256=digest(baseline_path),
                acceptance_file=str(accepted_path), acceptance_sha256=digest(accepted_path))
    plan = deepcopy(baseline)
    plan.update(scope='MODE_B_RESTOCK_ACCEPTED_DEPTH8_MOTION_SPEED2', restock_motion_speed=info,
                physical_restock_accepted=False, stages=[])
    plan['request']['task_id'] += ':motion-speed2'
    record_path = Path(plan['origin_record_file'])
    record = read(record_path)
    b = Builder(bound_delivery(record), record, record_path)
    b.p = plan
    b.attach = np.array(plan['tcp_from_object'])
    b.robot.payload_attachment = b.attach.copy()
    for stage in baseline['stages']:
        new, velocity, acceleration = resample(stage, profile)
        plan['stages'].append(new)
        b.stats['maximum_velocity_deg_s'] = max(b.stats['maximum_velocity_deg_s'], velocity)
        b.stats['maximum_acceleration_deg_s2'] = max(b.stats['maximum_acceleration_deg_s2'], acceleration)
    check_payload_path(b, np.array(plan['initial_source_object_pose']), np.array(plan['released_object_pose']))
    validate_speed(plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--acceptance', required=True, type=Path)
    parser.add_argument('--factor', type=float, default=2)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output path')
    plan = prepare(args.baseline, args.acceptance, args.factor)
    write(args.output, plan)
    print(json.dumps({'output': str(args.output), 'nominal_motion_seconds': plan['nominal_motion_seconds'],
                      'requests': sum(len(s['stage']['stream_frames']) for s in plan['stages'])+4,
                      'profile': plan['restock_motion_speed'], 'hardware_accessed': False}))
