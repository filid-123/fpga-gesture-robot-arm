"""Bind a measured public grasp-depth correction to one existing restock plan.

Rebind the rigid object at the deeper contact; keep its table position and the
original return centre fixed. This is a local commissioning candidate.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import math
from pathlib import Path
import sys

import numpy as np

from prepare_mode_b_restock import (Builder, NAMES, bound_delivery, check_payload_path,
                                    digest, objects, read, write)


def validate_depth(plan):
    c = plan['public_grasp_depth_correction']
    if digest(c['baseline_plan_file']) != c['baseline_plan_sha256']:
        raise ValueError('Depth baseline plan changed')
    if digest(c['measurement_result_file']) != c['measurement_result_sha256']:
        raise ValueError('Depth observation result changed')
    baseline = read(c['baseline_plan_file'])
    result = read(c['measurement_result_file'])
    if (baseline.get('public_grasp_depth_correction') or plan['request']['object_class'] != 'red_cube' or
            baseline['request']['object_class'] != 'red_cube' or
            result['route_sha256'] != c['baseline_plan_sha256'] or
            c['additional_descent_mm'] != 8.0 or result.get('error') or
            result['completed_stages'] != [s['phase'] for s in baseline['stages']]):
        raise ValueError('Depth correction requires the measured red baseline, once only')
    if (plan['origin_record_sha256'] != baseline['origin_record_sha256'] or
            plan['original_pickup'] != baseline['original_pickup'] or
            plan['return_centre_mm'] != baseline['return_centre_mm'] or
            plan['public_pickup_centre_mm'] != baseline['public_pickup_centre_mm']):
        raise ValueError('Depth correction changed a physical source coordinate')
    robot, _ = objects(plan)
    original_robot, _ = objects(baseline)
    target = lambda p, phase: np.array([next(s for s in p['stages'] if s['phase'] == phase)
                                       ['stage']['target_firmware_rad'][n] for n in NAMES])
    pose = lambda r, q, a: r.fk(np.r_[q[:5], 0.]) @ np.array(a)
    old_low = pose(original_robot, target(baseline, 'RESTOCK_PUBLIC_DESCEND'), baseline['tcp_from_object'])
    command_low = pose(original_robot, target(plan, 'RESTOCK_PUBLIC_DESCEND'), baseline['tcp_from_object'])
    if not np.allclose(command_low[:3, 3] - old_low[:3, 3], [0, 0, -8], atol=.03):
        raise ValueError('Public arm target did not descend8mm at unchanged XY')
    payload = pose(robot, target(plan, 'RESTOCK_PUBLIC_DESCEND'), plan['tcp_from_object'])
    if not np.allclose(payload, baseline['public_model_pickup_pose'], atol=.002):
        raise ValueError('Public payload was moved below its actual tabletop position')
    returned = pose(robot, target(plan, 'RESTOCK_SOURCE_DESCEND'), plan['tcp_from_object'])
    reference = np.array(baseline['released_object_pose'])
    if (not np.allclose(returned[:3, 3], reference[:3, 3], atol=.03) or
            not np.allclose(returned[:3, 2], reference[:3, 2], atol=.002) or
            not np.allclose(returned, plan['released_object_pose'], atol=.002)):
        raise ValueError('Changed contact depth displaced the original return target')
    if plan['physical_restock_accepted']:
        raise ValueError('New grasp depth has not been physically accepted')
    return True


def prepare(baseline_path, result_path):
    baseline_path, result_path = Path(baseline_path).resolve(), Path(result_path).resolve()
    baseline, result = read(baseline_path), read(result_path)
    if (baseline.get('public_grasp_depth_correction') or baseline['request']['object_class'] != 'red_cube' or
            result['route_sha256'] != digest(baseline_path) or result.get('error') or
            result['completed_stages'] != [s['phase'] for s in baseline['stages']]):
        raise ValueError('Use the completed measured red baseline, without accumulated depth offsets')
    record_path = Path(baseline['origin_record_file'])
    if digest(record_path) != baseline['origin_record_sha256']:
        raise ValueError('Original grasp record changed')
    record = read(record_path)
    b = Builder(bound_delivery(record), record, record_path)
    b.p = deepcopy(baseline)
    b.p['stages'] = []
    b.p['scope'] = 'MODE_B_RESTOCK_PUBLIC_DEPTH8_LOCAL_CORRECTION'
    b.p['request']['task_id'] += ':public-depth8'
    stages = {s['phase']: s for s in baseline['stages']}

    def target(phase):
        return np.array([stages[phase]['stage']['target_firmware_rad'][n] for n in NAMES])

    def keep(phase):
        stage = deepcopy(stages[phase])
        if np.max(abs(b.q[:5] - np.array([stage['start_firmware_rad'][n] for n in NAMES[:5]]))) > 1e-6:
            raise ValueError('Depth route continuity failed at ' + phase)
        b.p['stages'].append(stage)
        b.q = target(phase)

    b.q[5] = b.opened
    for phase in ('RESTOCK_INNER_OPEN', 'RESTOCK_BUFFER_OPEN', 'RESTOCK_PUBLIC_HIGH'):
        keep(phase)
    old_public = np.array(baseline['public_model_pickup_pose'])
    descend = b.cartesian('RESTOCK_PUBLIC_DESCEND', old_public[:3, 3] + [0, 0, -8],
                         carrying=False, axis=old_public[:3, 2], tighten=True)
    corrected_gripper = b.robot.fk(np.r_[b.q[:5], 0.])
    # A deeper contact changes attachment, not the stationary object's height.
    b.attach = np.linalg.inv(corrected_gripper) @ old_public
    b.robot.payload_attachment = b.attach.copy()
    b.p['tcp_from_object'] = b.attach.tolist()
    b.p['public_grasp_depth_correction'] = {
        'schema': 'gesture.mode_b.public_red_depth_correction.v1',
        'additional_descent_mm': 8.0, 'public_xy_mm': [300, 200],
        'baseline_plan_file': str(baseline_path), 'baseline_plan_sha256': digest(baseline_path),
        'measurement_result_file': str(result_path), 'measurement_result_sha256': digest(result_path),
        'operator_observation': '在夹取时需要再向下8mm',
        'scope': 'RED_PUBLIC_POINT_ONLY_NOT_GLOBAL_CALIBRATION',
        'attachment_policy': 'REBIND_AT_DEEPER_CONTACT_AND_PRESERVE_ORIGINAL_RETURN_CENTRE',
        'physical_acceptance': 'PENDING'}
    b.q[5] = b.closed
    b.reference('RESTOCK_PUBLIC_LIFT', descend, carrying=True, reverse=True)
    for phase in ('RESTOCK_RETURN_BUFFER', 'RESTOCK_RETURN_INNER', 'RESTOCK_SOURCE_HIGH'):
        keep(phase)
    # Retain the measured return descent, then compensate the new grip depth
    # before release. Re-time as one continuous stage, without an extra pause.
    low = stages['RESTOCK_SOURCE_DESCEND']
    frames = low['stage']['stream_frames']
    indices = list(range(0, len(frames), 3))
    if indices[-1] != len(frames)-1:
        indices.append(len(frames)-1)
    knots = [np.array([frames[i]['command_firmware_rad'][n] for n in NAMES]) for i in indices]
    knots[0] = b.q.copy()
    old_pose = b.pose(knots[-1])
    desired = np.array(baseline['released_object_pose'])
    count = max(3, math.ceil(np.linalg.norm(old_pose[:3, 3]-desired[:3, 3])/2))
    for u in np.linspace(0, 1, count+1)[1:]:
        axis = (1-u)*old_pose[:3, 2] + u*desired[:3, 2]
        axis /= np.linalg.norm(axis)
        knots.append(b.ik((1-u)*old_pose[:3, 3]+u*desired[:3, 3], axis, knots[-1], 0))
    b.append('RESTOCK_SOURCE_DESCEND', knots, carrying=True)
    returned = b.pose(b.q)
    b.p['released_object_pose'] = returned.tolist()
    b.p['return_source_command_firmware_rad'] = dict(zip(NAMES, b.q.tolist()))
    b.q[5] = b.opened
    home_high = np.array([next(s for s in b.original['stages'] if s['phase'] == 'DIRECT_PREGRASP')
                          ['stage']['target_firmware_rad'][n] for n in NAMES])
    b.withdraw('RESTOCK_SOURCE_EXIT', high_q=home_high)
    keep('RESTOCK_HOME')
    check_payload_path(b, old_public, returned)
    validate_depth(b.p)
    return b.p


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output path')
    plan = prepare(args.baseline, args.result)
    write(args.output, plan)
    print(__import__('json').dumps({'output': str(args.output), 'nominal_motion_seconds': plan['nominal_motion_seconds'],
                                  'public_additional_descent_mm': 8, 'hardware_accessed': False}))
