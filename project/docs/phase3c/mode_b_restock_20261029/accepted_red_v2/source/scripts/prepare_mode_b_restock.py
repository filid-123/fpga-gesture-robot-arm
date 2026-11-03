"""Offline public-point restock using a hash-bound, original dynamic grasp.

No serial/camera/FPGA access. Normal successful delivery plans stay immutable.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc.mode_b.restock_workflow import GraspOrigin
from prepare_mode_b_loaded_route import read, write, digest, objects, payload_half_extents, payload_spec, NAMES

FILID_COMMIT = '480f3e600bc9465d9a1fec361e6781c2b2eb59a0'


def create_record(plan_path, result_path, *, selection):
    plan_path, result_path = Path(plan_path).resolve(), Path(result_path).resolve()
    p, result = read(plan_path), read(result_path)
    if result['route_sha256'] != digest(plan_path) or result.get('object_class', 'red_cube') != p['request']['object_class']:
        raise ValueError('Delivery plan/result binding differs')
    if (result.get('error') or result.get('completed_stages') != [s['phase'] for s in p['stages']] or
            not result.get('release_requested') or not result.get('release_observed')):
        raise ValueError('Completed delivery, release and HOME evidence required')
    low = next(s for s in p['stages'] if s['phase'] == 'DESCEND')['stage']['target_firmware_rad'].copy()
    low['g'] = json.loads(p['close_after_descent_wire_json'])['cmd']
    capture = next((f for f in result['observations'] if 'CLOSE_SOURCE_OBSERVED' in f), None)
    observed = None
    endpoint = None
    if capture and Path(capture).exists():
        sample = read(capture)['samples'][-1]
        observed = sample['joint_rad']
        endpoint = {n:sample['feedback'][n] for n in ('x','y','z','tit')}
    record = {'schema': 'gesture.mode_b.dynamic_grasp_origin.v1', 'selection': selection,
              'original_task_id': p['request']['task_id']+':'+digest(plan_path)[:16],
              'source_request_task_id':p['request']['task_id'], 'object_class': p['request']['object_class'],
              'original_pickup': deepcopy(p['request']['pickup']),
              'delivery_plan_file': str(plan_path), 'delivery_plan_sha256': digest(plan_path),
              'delivery_result_file': str(result_path), 'delivery_result_sha256': digest(result_path),
              'grasp_command_firmware_rad': low, 'grasp_observed_firmware_rad': observed,
              'grasp_observed_firmware_endpoint':endpoint,
              'firmware_endpoint_frame':'FIRMWARE_BASE_ENDPOINT_NOT_CAMERA_OBJECT_CENTRE',
              'grasp_feedback_file': capture,
              'grasp_feedback_sha256': digest(capture) if observed is not None else None,
              'original_model_source_pose': p['initial_source_object_pose'],
              'return_policy': 'RESTORE_ORIGINAL_SUCCESSFUL_GRASP_COMMAND; RAW_CAMERA_SOURCE_UNCHANGED',
              'inventory_semantics': 'PROGRAM_COMPLETION_NOT_PHYSICAL_PRESENCE_PROOF',
              'public_xy_mm': [300, 200], 'filid_reference_commit': FILID_COMMIT}
    GraspOrigin.from_record(record)
    return record


def bound_delivery(record):
    GraspOrigin.from_record(record)
    if record['schema'] != 'gesture.mode_b.dynamic_grasp_origin.v1':
        raise ValueError('Wrong grasp-origin schema')
    if digest(record['delivery_plan_file']) != record['delivery_plan_sha256']:
        raise ValueError('Original delivery plan changed')
    if digest(record['delivery_result_file']) != record['delivery_result_sha256']:
        raise ValueError('Original delivery result changed')
    p = read(record['delivery_plan_file'])
    result = read(record['delivery_result_file'])
    if (result['route_sha256'] != record['delivery_plan_sha256'] or result.get('error') or
            result.get('completed_stages') != [s['phase'] for s in p['stages']]):
        raise ValueError('Incomplete or unrelated delivery result')
    expected = next(s for s in p['stages'] if s['phase'] == 'DESCEND')['stage']['target_firmware_rad'].copy()
    expected['g'] = json.loads(p['close_after_descent_wire_json'])['cmd']
    if (record['original_pickup'] != p['request']['pickup'] or record['object_class'] != p['request']['object_class'] or
            record['original_task_id'] != p['request']['task_id']+':'+digest(record['delivery_plan_file'])[:16] or
            record['grasp_command_firmware_rad'] != expected or
            record['original_model_source_pose'] != p['initial_source_object_pose']):
        raise ValueError('Original source/grasp was changed or compensation was reapplied')
    if record.get('grasp_feedback_sha256') and digest(record['grasp_feedback_file']) != record['grasp_feedback_sha256']:
        raise ValueError('Original grasp feedback changed')
    return p


class Builder:
    def __init__(self, original, record, record_path):
        self.original = original
        self.p = deepcopy(original)
        self.p.update(scope='MODE_B_PUBLIC_TO_DYNAMIC_ORIGINAL_SOURCE_RESTOCK', task_kind='RESTOCK', stages=[],
                      origin_record_file=str(record_path.resolve()), origin_record_sha256=digest(record_path),
                      physical_execution_allowed=False, physical_restock_accepted=False,
                      filid_restock_commit=FILID_COMMIT, pc_confirm_delivery=False,
                      requires_public_area_clear=True, requires_source_vacant=True,
                      source_vacancy_policy='OPERATOR_OR_FRESH_PERCEPTION_CONFIRMATION_BEFORE_RELEASE',
                      removed_delivery_fixture=deepcopy(original['request']['destination']),
                      original_pickup=deepcopy(record['original_pickup']),
                      return_centre_mm=record['original_pickup']['centre_mm'],
                      return_source_command_firmware_rad=record['grasp_command_firmware_rad'],
                      return_frame_policy='ORIGINAL_CAMERA_XYZ_PLUS_EXACT_EMPIRICAL_GRASP_COMMAND; NO_NEW_CORRECTION',
                      fpga_trajectory=False)
        self.p['request'] = deepcopy(original['request'])
        self.p['request']['task_id'] = record['original_task_id']+':restock'
        self.p['request']['pickup'] = {'centre_mm': [300, 200, payload_spec(original)['size_mm'][2]/2],
                                      'yaw_deg': None, 'yaw_source': 'PUBLIC_PLACEMENT_ORIENTATION_FROM_RESTOCK_IK'}
        # The 150mm fixture overlaps the public point. Removal is explicit and
        # is a required runtime condition, never inferred from the source plan.
        self.p['request']['destination'] = {'support_centre_mm': [*record['original_pickup']['centre_mm'][:2], 0],
                                           'size_xy_mm': [200, 140], 'rim_height_mm': 0}
        self.robot, self.world = objects(self.p)
        self.attach = np.array(self.p['tcp_from_object'])
        self.opened = json.loads(original['open_before_descent_wire_json'])['cmd']
        self.closed = json.loads(original['close_after_descent_wire_json'])['cmd']
        self.q = np.array([original['start_firmware_rad'][n] for n in NAMES])
        self.p['start_firmware_rad'] = dict(zip(NAMES, self.q.tolist()))
        self.stats = {'model_samples_checked': 0, 'maximum_velocity_deg_s': 0.,
                      'maximum_acceleration_deg_s2': 0., 'maximum_cartesian_chord_error_mm': 0.}

    def pose(self, q):
        return self.robot.fk(np.r_[q[:5], 0.])@self.attach

    def ik(self, xyz, axis, seed, tilt_slack):
        # Tight local joint box prevents a wrist flip to the other IK branch.
        lower = np.maximum(self.robot.limits[:5, 0]+1e-5, seed[:5]-.31)
        upper = np.minimum(self.robot.limits[:5, 1]-1e-5, seed[:5]+.31)
        radial = xyz[:2]-np.array(self.original['local_scene_config']['table_from_urdf_world']['xyz_mm'][:2])
        tangent = np.array([-radial[1], radial[0], 0.]);tangent /= np.linalg.norm(tangent)
        angles = [0.]+[sign*angle for angle in (1.,2.,4.,6.,10.,15.,20.) if angle<=tilt_slack for sign in (1.,-1.)]
        for angle in angles:
            desired = Rotation.from_rotvec(tangent*math.radians(angle)).apply(axis)
            def residual(a):
                T = self.pose(np.r_[a, self.closed])
                return np.r_[T[:3, 3]-xyz, 65*(T[:3, 2]-desired)]
            result = least_squares(residual, np.clip(seed[:5], lower, upper), bounds=(lower, upper),
                                   max_nfev=100, ftol=1e-9, xtol=1e-9, gtol=1e-9)
            if np.linalg.norm(residual(result.x)) <= .06:
                return np.r_[result.x, seed[5]]
        raise ValueError('No continuous restock IK at '+str(np.round(xyz, 3).tolist()))

    def cartesian(self, label, xyz, *, carrying, axis=None, tighten=False):
        a = self.pose(self.q)
        xyz = np.array(xyz, float)
        axis = a[:3, 2] if axis is None else np.array(axis, float)
        count = max(3, math.ceil(np.linalg.norm(xyz-a[:3, 3])/3))
        knots = [self.q.copy()]
        for u in np.linspace(0, 1, count+1)[1:]:
            z = (1-u)*a[:3, 2]+u*axis
            z /= np.linalg.norm(z)
            slack = max(0.,10*(1-u)) if tighten else 10.
            knots.append(self.ik(a[:3, 3]+u*(xyz-a[:3, 3]), z, knots[-1],slack))
        return self.append(label, knots, carrying=carrying, chord=(a[:3, 3], xyz))

    def append(self, label, knots, *, carrying, chord=None):
        knots = np.asarray(knots)
        if np.max(np.abs(knots[0, :5]-self.q[:5])) > 1e-6:
            raise ValueError('Discontinuous restock stage start '+label)
        arc = np.r_[0., np.cumsum(np.maximum(np.linalg.norm(np.diff(knots[:, :5], axis=0), axis=1), 1e-10))]
        spline = PchipInterpolator(arc/arc[-1], knots[:, :5], axis=0)
        dt = .02
        multiplier = self.original['speed_multiplier']
        vmax, amax = 12*multiplier, 24*multiplier**2
        duration = max(1./multiplier, 1.875*np.abs(np.diff(knots[:, :5], axis=0)).sum(axis=0).max()/math.radians(vmax))
        for _ in range(12):
            u = np.linspace(0, 1, math.ceil(duration/dt)+1)
            arm = spline(10*u**3-15*u**4+6*u**5)
            pad = np.vstack([arm[0], arm[0], arm, arm[-1], arm[-1]])
            v = float(abs(np.diff(pad, axis=0)).max())/dt
            acc = float(abs(np.diff(pad, n=2, axis=0)).max())/dt**2
            ratio = max(v/math.radians(vmax), math.sqrt(acc/math.radians(amax)))
            if ratio <= 1.00001:
                break
            duration *= ratio*1.02
        else:
            raise ValueError('Restock timing did not converge')
        initial = self.q.copy()
        hand = self.closed if carrying else self.opened
        frames = []
        for values in arm:
            q = np.r_[values, hand]
            # Full static-object checks are performed after public and returned
            # object poses have both been resolved by the complete path.
            self.robot.check_q(np.r_[values, 0.])
            if chord is not None:
                a, b = chord
                actual = self.pose(q)[:3, 3]
                progress = np.clip(np.dot(actual-a, b-a)/max(np.dot(b-a, b-a), 1e-12), 0, 1)
                error = float(np.linalg.norm(actual-(a+progress*(b-a))))
                self.stats['maximum_cartesian_chord_error_mm'] = max(self.stats['maximum_cartesian_chord_error_mm'], error)
                if error > .6:
                    raise ValueError('Restock Cartesian chord exceeds0.6mm')
            command = {'T': 102, **dict(zip(('base','shoulder','elbow','wrist','roll'), values.tolist())),
                       'hand': hand, 'spd': round(160*multiplier), 'acc': min(254, round(20*multiplier**2))}
            frames.append({'wire_json': json.dumps(command, separators=(',', ':')),
                           'command_firmware_rad': dict(zip(NAMES, q.tolist())),
                           'model_q': [*values.tolist(), 0. if carrying else 1.5]})
        self.q = np.r_[arm[-1], hand]
        stage = {'phase': label, 'carrying': carrying, 'start_firmware_rad': dict(zip(NAMES, initial.tolist())),
                 'arrival_tolerance_deg': deepcopy(self.p['arrival_tolerance_deg']),
                 'commissioning_tolerance_profile': deepcopy(self.p['commissioning_tolerance_profile']),
                 'stage': {'period_s': dt, 'stream_frames': frames,
                           'target_firmware_rad': dict(zip(NAMES, self.q.tolist())),
                           'nominal_motion_seconds': len(frames)*dt}}
        self.p['stages'].append(stage)
        self.stats['maximum_velocity_deg_s'] = max(self.stats['maximum_velocity_deg_s'], math.degrees(v))
        self.stats['maximum_acceleration_deg_s2'] = max(self.stats['maximum_acceleration_deg_s2'], math.degrees(acc))
        return stage

    def reference(self, label, source, *, carrying, reverse=False):
        qs = np.array([[f['command_firmware_rad'][n] for n in NAMES] for f in source['stage']['stream_frames']])
        if reverse:
            qs = qs[::-1]
        # Refit original demonstrated knots under the same speed bounds, always
        # checking the new carried/static payload and complete finger sweep.
        indices = list(range(0, len(qs), 3))
        if indices[-1] != len(qs)-1:
            indices.append(len(qs)-1)
        knots = qs[indices]
        if np.max(abs(knots[0, :5]-self.q[:5])) > .001:
            raise ValueError('Reference path start differs at '+label)
        knots[0] = self.q
        return self.append(label, knots, carrying=carrying)

    def withdraw(self, prefix, *, high_q):
        start = self.pose(self.q)
        sideways = -8*self.robot.frames(np.r_[self.q[:5],0.])['link5'][:3, 0]
        self.cartesian(prefix+'_CLEARANCE', start[:3, 3]+sideways, carrying=False)
        high = self.pose(high_q)
        self.cartesian(prefix+'_UP', high[:3, 3]+sideways, carrying=False, axis=high[:3, 2])
        self.append(prefix+'_RECENTER', [self.q.copy(), high_q], carrying=False)


def check_payload_path(b, public_pose, returned):
    released = False
    for s in b.p['stages']:
        static = returned if released else public_pose
        for f in s['stage']['stream_frames']:
            actual = b.pose(f['model_q']) if s['carrying'] else static
            if s['carrying']:
                tilt = math.degrees(math.acos(np.clip(actual[2,2],-1,1)))
                if tilt > 40.1:
                    raise ValueError('Restock payload tilt exceeds40deg')
            for hand in (0., .75, 1.5):
                model = np.r_[f['model_q'][:5],hand]
                b.robot.check_q(model)
                payload = {'size_mm':payload_spec(b.p)['size_mm'],
                           'grasp_from_object':np.linalg.inv(b.robot.fk(model))@actual}
                b.world.check(model,payload=payload)
                b.stats['model_samples_checked'] += 1
        if s['phase'] == b.p['release_after_stage']:
            released = True
    b.p['offline_verification'] = dict(b.stats, passed=True, rigid_attachment_not_friction=True)
    b.p['nominal_motion_seconds'] = sum(s['stage']['nominal_motion_seconds'] for s in b.p['stages'])


def prepare(record_path):
    record_path = Path(record_path)
    record = read(record_path)
    original = bound_delivery(record)
    b = Builder(original, record, record_path)
    stages = {s['phase']: s for s in original['stages']}
    q = lambda phase: np.array([stages[phase]['stage']['target_firmware_rad'][n] for n in NAMES])
    b.q[5] = b.opened  # HOME_OPEN is an explicit event before the first stage.
    b.append('RESTOCK_INNER_OPEN', [b.q.copy(), q('INNER_HOLD')], carrying=False)
    b.reference('RESTOCK_BUFFER_OPEN', stages['BUFFER'], carrying=False)
    height = payload_spec(original)['size_mm'][2]/2
    b.cartesian('RESTOCK_PUBLIC_HIGH', [300, 200, height+65], carrying=False, axis=[0,0,1])
    public_high = b.q.copy()
    descend = b.cartesian('RESTOCK_PUBLIC_DESCEND', [300, 200, height+.5], carrying=False, axis=[0,0,1],tighten=True)
    public_pose = b.pose(b.q)
    b.p['public_pickup_centre_mm'] = [300, 200, height]
    b.p['public_model_pickup_pose'] = public_pose.tolist()
    b.p['request']['pickup']['yaw_deg'] = math.degrees(math.atan2(public_pose[1,0],public_pose[0,0]))
    b.p['initial_source_object_pose'] = public_pose.tolist()
    b.p['initial_object_pose'] = public_pose.tolist()
    b.q[5] = b.closed
    b.reference('RESTOCK_PUBLIC_LIFT', descend, carrying=True, reverse=True)
    b.reference('RESTOCK_RETURN_BUFFER', next(s for s in b.p['stages'] if s['phase']=='RESTOCK_PUBLIC_HIGH'),
                carrying=True, reverse=True)
    b.reference('RESTOCK_RETURN_INNER', stages['BUFFER'], carrying=True, reverse=True)
    b.reference('RESTOCK_SOURCE_HIGH', stages['INNER_HOLD'], carrying=True, reverse=True)
    b.reference('RESTOCK_SOURCE_DESCEND', stages['LIFT'], carrying=True, reverse=True)
    if np.max(np.abs(b.q[:5]-q('DESCEND')[:5])) > 1e-6:
        raise ValueError('Restock did not recover the original grasp command')
    returned = b.pose(b.q)
    if np.max(abs(returned-np.array(original['initial_source_object_pose']))) > .002:
        raise ValueError('Original empirical payload placement differs')
    b.p['released_object_pose'] = returned.tolist()
    b.p['release_after_stage'] = 'RESTOCK_SOURCE_DESCEND'
    b.q[5] = b.opened
    b.withdraw('RESTOCK_SOURCE_EXIT', high_q=q('DIRECT_PREGRASP'))
    b.reference('RESTOCK_HOME', stages['DIRECT_PREGRASP'], carrying=False, reverse=True)
    b.p['event_after_stage'] = {'RESTOCK_PUBLIC_DESCEND': {'label':'GRASP_PUBLIC', 'wire_json':original['close_after_descent_wire_json']},
                              'RESTOCK_SOURCE_DESCEND': {'label':'RELEASE_SOURCE', 'wire_json':original['release_wire_json']}}
    b.p['initial_event'] = {'label':'HOME_OPEN', 'wire_json':original['open_before_descent_wire_json']}
    b.p['final_event'] = {'label':'PARK_CLOSE', 'wire_json':original['park_close_wire_json']}
    b.p['stationary_source_phases'] = ['RESTOCK_INNER_OPEN','RESTOCK_BUFFER_OPEN','RESTOCK_PUBLIC_HIGH','RESTOCK_PUBLIC_DESCEND']
    b.p['grasp_contact_allowance'] = {'phases':['RESTOCK_PUBLIC_DESCEND']}
    b.p['source_liftoff_phases'] = ['RESTOCK_PUBLIC_LIFT']
    b.p['table_placement_phases'] = ['RESTOCK_SOURCE_DESCEND']
    b.p['released_on_table'] = True
    b.p['release_clearance_phases'] = ['RESTOCK_SOURCE_EXIT_CLEARANCE']
    b.p['intentional_release_contact'] = {'link':'link5','maximum_initial_lateral_travel_mm':2,
                                         'direction':'AWAY_FROM_FIXED_JAW_FACE', 'nominal_contact_not_force_simulated':True}
    check_payload_path(b,public_pose,returned)
    b.p['public_high_firmware_rad'] = dict(zip(NAMES,public_high.tolist()))
    return b.p


def prepare_cancel(plan_path, at_phase):
    """Checked retrace from a known stopped holding boundary, never midmotion."""
    p = read(plan_path)
    allowed = ('RESTOCK_PUBLIC_LIFT','RESTOCK_RETURN_BUFFER','RESTOCK_RETURN_INNER',
               'RESTOCK_SOURCE_HIGH','RESTOCK_SOURCE_DESCEND')
    empty_phases = ('RESTOCK_INNER_OPEN','RESTOCK_BUFFER_OPEN','RESTOCK_PUBLIC_HIGH','RESTOCK_PUBLIC_DESCEND')
    if at_phase not in (*allowed,*empty_phases) or p.get('task_kind') != 'RESTOCK':
        raise ValueError('A known pre-release holding boundary is required')
    record_path = Path(p['origin_record_file'])
    if digest(record_path) != p['origin_record_sha256']:
        raise ValueError('Grasp origin record changed')
    record = read(record_path)
    original = bound_delivery(record)
    b = Builder(original,record,record_path)
    if p.get('public_grasp_depth_correction'):
        from prepare_mode_b_restock_depth import validate_depth
        validate_depth(p)
        b.attach = np.array(p['tcp_from_object'])
        b.robot.payload_attachment = b.attach.copy()
        b.p['tcp_from_object'] = b.attach.tolist()
        b.p['cancelled_public_depth_correction'] = deepcopy(p['public_grasp_depth_correction'])
    stages = {s['phase']:s for s in p['stages']}
    b.q = np.array([stages[at_phase]['stage']['target_firmware_rad'][n] for n in NAMES])
    if at_phase in empty_phases:
        public=np.array(p['public_model_pickup_pose'])
        b.p.update(scope='MODE_B_RESTOCK_CANCEL_EMPTY_AT_KNOWN_STOPPED_BOUNDARY',task_kind='RESTOCK_CANCEL_EMPTY',
                   cancel_of_plan_file=str(Path(plan_path).resolve()),cancel_of_plan_sha256=digest(plan_path),
                   cancel_at_phase=at_phase,requires_stopped_fresh_pose=True,inventory_restored=False,
                   start_firmware_rad=dict(zip(NAMES,b.q.tolist())),initial_event=None,
                   initial_object_pose=public.tolist(),initial_source_object_pose=public.tolist(),released_object_pose=public.tolist(),
                   return_centre_mm=p['public_pickup_centre_mm'],event_after_stage={},release_after_stage=None,
                   final_event={'label':'PARK_CLOSE','wire_json':original['park_close_wire_json']})
        last=empty_phases.index(at_phase)
        if at_phase=='RESTOCK_PUBLIC_DESCEND':
            high=np.array([p['public_high_firmware_rad'][n] for n in NAMES])
            b.withdraw('CANCEL_EMPTY_PUBLIC_EXIT',high_q=high)
            last=2
        for phase in reversed(empty_phases[:last+1]):
            b.reference('CANCEL_EMPTY_'+phase,stages[phase],carrying=False,reverse=True)
        b.p.update(stationary_source_phases=[s['phase'] for s in b.p['stages']],source_liftoff_phases=[],
                   grasp_contact_allowance={'phases':[]},table_placement_phases=[],released_on_table=True,
                   release_clearance_phases=['CANCEL_EMPTY_PUBLIC_EXIT_CLEARANCE'],
                   intentional_release_contact={'link':'link5','maximum_initial_lateral_travel_mm':2,
                                                'nominal_contact_not_force_simulated':True})
        check_payload_path(b,public,public)
        return b.p
    b.p.update(scope='MODE_B_RESTOCK_CANCEL_AT_KNOWN_STOPPED_BOUNDARY',task_kind='RESTOCK_CANCEL',
               cancel_of_plan_file=str(Path(plan_path).resolve()),cancel_of_plan_sha256=digest(plan_path),
               cancel_at_phase=at_phase,requires_stopped_fresh_pose=True,inventory_restored=False,
               start_firmware_rad=dict(zip(NAMES,b.q.tolist())),initial_event=None,
               initial_object_pose=b.pose(b.q).tolist(),initial_source_object_pose=p['public_model_pickup_pose'],
               return_centre_mm=p['public_pickup_centre_mm'],public_model_pickup_pose=p['public_model_pickup_pose'])
    for phase in reversed(allowed[:allowed.index(at_phase)+1]):
        b.reference('CANCEL_RETRACE_'+phase,stages[phase],carrying=True,reverse=True)
    release_phase = b.p['stages'][-1]['phase']
    returned = b.pose(b.q)
    if np.max(abs(returned-np.array(p['public_model_pickup_pose']))) > .002:
        raise ValueError('Cancellation failed to recover public pickup pose')
    b.p['released_object_pose'] = returned.tolist()
    b.p['release_after_stage'] = release_phase
    b.q[5] = b.opened
    high = np.array([p['public_high_firmware_rad'][n] for n in NAMES])
    b.withdraw('CANCEL_PUBLIC_EXIT',high_q=high)
    for phase in ('RESTOCK_PUBLIC_HIGH','RESTOCK_BUFFER_OPEN','RESTOCK_INNER_OPEN'):
        b.reference('CANCEL_EMPTY_'+phase,stages[phase],carrying=False,reverse=True)
    b.p.update(event_after_stage={release_phase:{'label':'RELEASE_PUBLIC','wire_json':original['release_wire_json']}},
               final_event={'label':'PARK_CLOSE','wire_json':original['park_close_wire_json']},
               stationary_source_phases=[],source_liftoff_phases=[],
               grasp_contact_allowance={'phases':[]},table_placement_phases=[release_phase],released_on_table=True,
               release_clearance_phases=['CANCEL_PUBLIC_EXIT_CLEARANCE'],
               intentional_release_contact={'link':'link5','maximum_initial_lateral_travel_mm':2,
                                            'direction':'AWAY_FROM_FIXED_JAW_FACE','nominal_contact_not_force_simulated':True})
    check_payload_path(b,np.array(b.p['initial_object_pose']),returned)
    return b.p


def validate_plan(plan_path):
    p = read(plan_path)
    record_path = Path(p['origin_record_file'])
    if digest(record_path) != p['origin_record_sha256']:
        raise ValueError('Grasp origin record changed')
    original = bound_delivery(read(record_path))
    if p['task_kind'] not in ('RESTOCK','RESTOCK_CANCEL','RESTOCK_CANCEL_EMPTY') or not p['offline_verification']['passed']:
        raise ValueError('Checked restock plan required')
    if p['task_kind'] == 'RESTOCK':
        low = next(s for s in p['stages'] if s['phase']=='RESTOCK_SOURCE_DESCEND')['stage']['target_firmware_rad']
        expected = read(record_path)['grasp_command_firmware_rad']
        if p.get('public_grasp_depth_correction'):
            from prepare_mode_b_restock_depth import validate_depth
            validate_depth(p)
        elif max(abs(low[n]-expected[n]) for n in NAMES)>1e-9 or p['return_centre_mm'] != original['request']['pickup']['centre_mm']:
            raise ValueError('Return target differs from original grasp')
        if p.get('restock_motion_speed'):
            from prepare_mode_b_restock_speed import validate_speed
            validate_speed(p)
    else:
        if digest(p['cancel_of_plan_file']) != p['cancel_of_plan_sha256']:
            raise ValueError('Cancelled forward plan changed')
        if not p['requires_stopped_fresh_pose'] or p['inventory_restored']:
            raise ValueError('Invalid cancel acceptance scope')
    for s in p['stages']:
        for frame in s['stage']['stream_frames']:
            wire=json.loads(frame['wire_json'])
            if (wire['T'] != 102 or not 0<wire['spd']<=4095 or not 0<wire['acc']<=254 or
                    [wire[n] for n in ('base','shoulder','elbow','wrist','roll','hand')] !=
                    [frame['command_firmware_rad'][n] for n in NAMES] or
                    frame['model_q'][:5] != [frame['command_firmware_rad'][n] for n in NAMES[:5]]):
                raise ValueError('Restock wire/model/radian mapping differs')
    return {'passed':True,'task_kind':p['task_kind'],'return_centre_mm':p['return_centre_mm'],'hardware_accessed':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action',required=True)
    record = sub.add_parser('record')
    record.add_argument('--delivery-plan',type=Path,required=True)
    record.add_argument('--delivery-result',type=Path,required=True)
    record.add_argument('--selection',type=int,choices=(1,2,3),required=True)
    record.add_argument('--output',type=Path,required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('--record',type=Path,required=True)
    plan.add_argument('--output',type=Path,required=True)
    cancel = sub.add_parser('cancel')
    cancel.add_argument('--plan',type=Path,required=True)
    cancel.add_argument('--at-phase',required=True)
    cancel.add_argument('--output',type=Path,required=True)
    check = sub.add_parser('check')
    check.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='check':
        print(json.dumps(validate_plan(args.plan)));return
    result = (create_record(args.delivery_plan,args.delivery_result,selection=args.selection) if args.action=='record' else
              prepare_cancel(args.plan,args.at_phase) if args.action=='cancel' else prepare(args.record))
    write(args.output,result)
    print(json.dumps({'output':str(args.output),'action':args.action,'hardware_accessed':False,
                      'seconds':result.get('nominal_motion_seconds'),'return_centre_mm':result.get('return_centre_mm')}))


if __name__ == '__main__':
    main()
