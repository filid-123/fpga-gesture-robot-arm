"""Offline, locally anchored continuation of the operator-confirmed red pickup.

This is a commissioning adapter, not a replacement for global calibration or
the FPGA planner. Firmware hand radians and CAD hand angles remain distinct.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
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
from pc.mode_b.motion.kinematics import Robot, transform
from pc.mode_b.motion.collision import World, Box, separating_gap
from pc.mode_b.motion.export import load_package
from pc.roarm_reference_kinematics import ReferenceGeometry, forward
from prepare_mode_b_approach import NAMES, read, digest

FLIP = np.diag([1., -1., -1., 1.])
BASE = ROOT / 'artifacts/phase3c/mode_b_pc_trial_20261028'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def payload_spec(plan):
    name=plan['request'].get('object_class','red_cube')
    spec=plan['local_scene_config']['objects'][name]
    size=np.asarray(spec['size_mm'],dtype=float)
    if size.shape!=(3,) or not np.isfinite(size).all() or np.any(size<=0):
        raise ValueError('Positive finite payload dimensions required')
    return {'shape':spec['shape'],'size_mm':size.tolist(),
            'grasp_width_mm':float(size[1] if name=='eraser' else size[0])}


def payload_half_extents(plan, pose):
    # Enclose cylinders by their oriented diameter/diameter/height box. This
    # deliberately keeps offline bounds conservative; mesh replay uses a cylinder.
    return np.abs(np.asarray(pose)[:3,:3])@(np.array(payload_spec(plan)['size_mm'])/2)


def objects(plan):
    robot = Robot(ROOT, plan['local_scene_config'], grasp_width_mm=payload_spec(plan)['grasp_width_mm'])
    robot.grasp = np.array(plan['link5_from_local_object_tcp'])
    robot.payload_attachment = np.array(plan.get('tcp_from_object',FLIP))
    world = World(robot, plan['request'], plan['local_scene_config'])
    return robot, world


def observed(capture):
    if capture.get('observation_status') != 'CAPTURE_COMPLETE_NOT_VALIDATED' or len(capture.get('samples', [])) != 5:
        raise ValueError('Five complete current states required')
    qs = np.array([[s['joint_rad'][n] for n in NAMES] for s in capture['samples']])
    if not np.isfinite(qs).all() or np.degrees(np.ptp(qs, axis=0)).max() > .5:
        raise ValueError('Stable finite feedback required')
    geometry = ReferenceGeometry(**read(ROOT/'config/ai_pc/roarm_reference_geometry.json')['geometry_mm'])
    for q, sample in zip(qs, capture['samples']):
        f = sample['feedback']
        if any(f.get(n) for n in ('Stalltor','Stalltep','Stallvol')):
            raise ValueError('Firmware fault')
        if any(f.get(n, 1) != 1 for n in ('torswitchB','torswitchS','torswitchE','torswitchT','torswitchR','torswitchG')):
            raise ValueError('Joint torque disabled')
        if math.dist(forward(q[:4], geometry)[:3], [f[n] for n in ('x','y','z')]) > 1:
            raise ValueError('Native endpoint FK mismatch')
    return qs[-1]


def geometry_check(plan, q, carrying=True, cached=None, phase=None):
    robot, world = objects(plan) if cached is None else cached
    q = np.asarray(q, dtype=float)
    if q.shape != (6,) or not np.isfinite(q).all():
        raise ValueError('Invalid six-channel feedback')
    before_grasp = phase in plan.get('stationary_source_phases', [])
    object_pose = robot.fk(np.r_[q[:5], 0.]) @ robot.payload_attachment if carrying else np.array(
        plan['initial_source_object_pose'] if before_grasp else plan['released_object_pose'])
    payload = {'size_mm':payload_spec(plan)['size_mm'], 'grasp_from_object':robot.payload_attachment.tolist()}
    bottom = float(object_pose[2,3]-payload_half_extents(plan,object_pose)[2])
    height = float('inf')
    clearance = float('inf')
    for hand in (0., .75, 1.5):
        model_q = np.r_[q[:5], hand]
        robot.check_q(model_q)
        if not carrying:
            payload['grasp_from_object'] = (np.linalg.inv(robot.fk(model_q)) @ object_pose).tolist()
        initial_contact=(plan.get('initial_support_separation') and carrying and phase=='RECOVERY_CONTACT_CLEAR'
                         and bottom>=plan['initial_support_separation']['start_model_bottom_mm']-.15)
        if initial_contact and world.support and bottom<world.support.centre[2]+world.support.half[2]+2:
            # Retain complete arm/support checks. Only the already-existing
            # nominal object/support contact is exempted during upward exit.
            clearance=min(clearance,world.check(model_q))
            support=world.support;world.support=None
            try:clearance=min(clearance,world.check(model_q,payload=payload))
            finally:world.support=support
        else:
            clearance = min(clearance, world.check(model_q, payload=payload, payload_support_contact=not carrying and not before_grasp))
        boxes = world.link_boxes(model_q)
        height = min(height, *(float(boxes[n].corners[:,2].min()) for n in ('link5','gripper_link')))
    bottom = float(object_pose[2,3]-payload_half_extents(plan,object_pose)[2])
    tilt = math.degrees(math.acos(float(np.clip(object_pose[2,2], -1, 1))))
    if carrying and tilt > plan['commissioning_tolerance_profile']['loaded_pitch_limit_from_vertical_deg']+.1:
        raise ValueError(f'Loaded object tilt {tilt:.2f}deg exceeds commissioning cone')
    hand_bounds=plan.get('object_adapter',{}).get('loaded_hand_command_bounds_rad',[2.50,2.75])
    if carrying and not hand_bounds[0] <= q[5] <= hand_bounds[1]:
        raise ValueError('Loaded hand outside the object command bounds')
    return {'height_mm':height, 'object_bottom_mm':bottom, 'object_centre_mm':object_pose[:3,3].tolist(),
            'object_tilt_deg':tilt, 'minimum_model_clearance_mm':clearance}


def solve_position(robot, xyz, seed, tilt):
    """Position IK with fixed native roll and a bounded, freely selected pitch.

    Cube yaw follows the base. Keeping native roll avoids a redundant wrist-roll
    spin when a locally anchored asymmetric tool crosses an orientation branch.
    """
    xyz=np.array(xyz,dtype=float); seed=np.array(seed,dtype=float)
    previous_pitch=float(seed[1:4].sum()-math.pi/2)
    pitches=[previous_pitch]
    for delta in (3,6,9,12,18,24,30):
        pitches.extend([previous_pitch+math.radians(delta),previous_pitch-math.radians(delta)])
    lower=robot.limits[:4,0]+.0001;upper=robot.limits[:4,1]-.0001
    for pitch in pitches:
        def residual(arm):
            q=np.r_[arm,seed[4],0.]
            pose=robot.fk(q)
            return np.r_[pose[:3,3]-xyz,65*(arm[1:4].sum()-math.pi/2-pitch)]
        result=least_squares(residual,np.clip(seed[:4],lower,upper),bounds=(lower,upper),max_nfev=100,
                             ftol=1e-9,xtol=1e-9,gtol=1e-9)
        q=np.r_[result.x,seed[4:]];pose=robot.fk(np.r_[q[:5],0.])@robot.payload_attachment
        actual_tilt=math.degrees(math.acos(float(np.clip(pose[2,2],-1,1))))
        if np.linalg.norm(robot.fk(np.r_[q[:5],0.])[:3,3]-xyz)<.3 and actual_tilt<=tilt+.05 and np.abs(q[:5]-seed[:5]).max()<.32:
            return q
    raise ValueError(f'No continuous position/tilt IK at {xyz.tolist()}, residual {np.linalg.norm(pose[:3,3]-xyz):.2f}mm, tilt{actual_tilt:.2f}')


def prepare(capture_path, accepted_path, closed_capture_path, bottom_mm=80., route_profile=None, bank=1):
    accepted = read(accepted_path)
    if accepted.get('status') != 'PICKUP_LIFT_OPERATOR_ACCEPTED_HOLDING_RED' or accepted.get('current_payload') != 'RED_CUBE_30MM':
        raise ValueError('Operator-accepted loaded source required; empty/failed pickup is invalid')
    if not accepted.get('cube_lift_or_slip_operator_confirmed') or accepted.get('cube_bottom_height_measured_mm') != bottom_mm:
        raise ValueError('Measured bottom must match the operator evidence')
    if not math.isfinite(bottom_mm) or not 65 <= bottom_mm <= 150:
        raise ValueError('Measured transfer height outside commissioning envelope')
    capture = read(capture_path)
    start = observed(capture)
    expected = np.array([accepted['final_firmware_rad'][n] for n in NAMES])
    if np.degrees(np.abs(start-expected)).max() > 1:
        raise ValueError('Loaded pose changed since the physical grip/height observation')
    task, _ = load_package(accepted['task_file'])
    lift = read(accepted['lift_plan'])
    config = deepcopy(lift['local_scene_config'])
    task=deepcopy(task)
    profile=read(route_profile) if route_profile else None
    selected=None
    if profile:
        if profile['schema']!='gesture.mode_b.filid_postlift_reference.v1' or bank not in (0,1,2):
            raise ValueError('Invalid filid reference/bank')
        for name,sha in profile['source_files_sha256'].items():
            if digest(ROOT/profile['source_snapshot']/name)!=sha:
                raise ValueError('Pinned filid source changed')
        selected=profile['banks'][bank]
        task['request']['destination']={'support_centre_mm':[*selected['H'][:2],profile['support_proxy']['top_z_mm']],
                                        'size_xy_mm':profile['support_proxy']['size_xy_mm'],'rim_height_mm':0}
    nominal = Robot(ROOT, config, grasp_width_mm=30)
    low = read(closed_capture_path)
    if len(low['samples']) != 5:
        raise ValueError('Closed pickup source capture incomplete')
    low_q = np.array([low['samples'][-1]['joint_rad'][n] for n in NAMES])
    if not 2.50 <= low_q[5] <= 2.75:
        raise ValueError('Closed pickup source lacks the established contact plateau')
    original = transform(task['request']['pickup']['centre_mm'], [0,0,math.radians(task['request']['pickup']['yaw_deg'])])
    carried = nominal.fk(np.r_[start[:5],0.]) @ np.linalg.inv(nominal.fk(np.r_[low_q[:5],0.])) @ original
    predicted_bottom = float(carried[2,3]-15*np.abs(carried[2,:3]).sum())
    correction = float(bottom_mm-predicted_bottom)
    if abs(correction) > 20:
        raise ValueError('Height discrepancy outside the local continuation envelope')
    carried[2,3] += correction
    link5 = nominal.frames(np.r_[start[:5],0.])['link5']
    local_tcp = np.linalg.inv(link5) @ carried @ FLIP
    attachment=FLIP.copy()
    if profile:
        # Reference the same link5-local TCP POINT as filid. Preserve the
        # locally observed object attachment rather than treating H as its centre.
        local_tcp[:3,3]=profile['reference_link5_tcp_xyz_mm']
        attachment=np.linalg.inv(local_tcp)@np.linalg.inv(link5)@carried
    practical = read(ROOT/'config/ai_pc/mode_b_commissioning_tolerance_20261028.json')
    practical=deepcopy(practical)
    if profile:
        practical.update(native_stream_spd=660,native_stream_acc=33,native_period_s=.02,
                         loaded_pitch_limit_from_vertical_deg=40)
    plan = {'schema':'gesture.mode_b.loaded_continuation.v1', 'scope':'ONE_OPERATOR_ACCEPTED_RED_PICKUP_LOCAL_COMMISSIONING',
            'task_file':accepted['task_file'], 'task_sha256':digest(accepted['task_file']),
            'accepted_pickup_file':str(Path(accepted_path).resolve()), 'accepted_pickup_sha256':digest(accepted_path),
            'closed_pickup_capture':str(Path(closed_capture_path).resolve()), 'closed_pickup_capture_sha256':digest(closed_capture_path),
            'capture_file':str(Path(capture_path).resolve()), 'capture_sha256':digest(capture_path),
            'local_scene_config':config, 'request':task['request'], 'urdf_sha256':nominal.sha256,
            'link5_from_local_object_tcp':local_tcp.tolist(), 'initial_object_pose':carried.tolist(),
            'start_firmware_rad':dict(zip(NAMES,start.tolist())), 'measured_object_bottom_mm':bottom_mm,
            'height_anchor_correction_mm':correction, 'xy_source':'CONFIRMED_PICKUP_BOUND_TO_CAMERA_SOURCE_THEN_NOMINAL_RIGID_FK; NOT_MEASURED_CURRENT_XY',
            'support_dimensions_status':'PLANNED_90X90_RIM_FREE_NOT_NEWLY_MEASURED',
            'commissioning_tolerance_profile':practical, 'arrival_tolerance_deg':deepcopy(practical['arrival_tolerance_deg']),
            'global_calibration_changed':False, 'physical_general_mapping_calibrated':False,
            'fpga_trajectory':False, 'period_s':practical['native_period_s'], 'stages':[],
            'tcp_from_object':attachment.tolist(),'filid_profile':profile,'filid_bank':bank if profile else None,
            'scope_note':'FUTURE_PICKUP_LIFT_END_NOT_CURRENT_INTERRUPTED_POSE' if profile else 'CURRENT_ACCEPTED_LIFT',
            'support_height_physically_ready':False if profile else None}
    # Contact is position-limited, so firmware hand may stop before its target.
    plan['arrival_tolerance_deg']['g'] = 12.
    return build_postlift_connection(plan, start)


def build_postlift_connection(plan, start):
    """Build the checked filid/legacy tail from an explicit local attachment.

    Callers must bind current joints, source/attachment and fixture evidence.
    This routine performs no transport or physical acceptance.
    """
    profile=plan.get('filid_profile')
    selected=profile['banks'][plan['filid_bank']] if profile else None
    config=plan['local_scene_config']
    task={'request':plan['request']}
    practical=deepcopy(plan['commissioning_tolerance_profile'])
    speed_multiplier=float(plan.get('speed_multiplier',1.))
    if not math.isfinite(speed_multiplier) or not 0<speed_multiplier<=3:
        raise ValueError('Invalid native commissioning speed multiplier')
    base_native_acc=practical['native_stream_acc']
    requested_native_acc=round(base_native_acc*speed_multiplier**2)
    # ACC is an8-bit firmware field;254 is its highest permitted value.
    # Retime the curve against the same capped acceleration scale sent on TTL.
    acceleration_scale=min(speed_multiplier**2,254/base_native_acc)
    practical['native_stream_spd']=round(practical['native_stream_spd']*speed_multiplier)
    practical['native_stream_acc']=min(254,requested_native_acc)
    if practical['native_stream_spd']>4095 or practical['native_stream_acc']>254:
        raise ValueError('Native speed/acceleration field range exceeded')
    plan['postlift_speed_policy']={'multiplier_from_original':speed_multiplier,
        'native_spd':practical['native_stream_spd'],'native_requested_acc':requested_native_acc,
        'native_acc':practical['native_stream_acc'],'acceleration_scale':acceleration_scale,
        'acceleration_capped':requested_native_acc>254,'period_s':plan['period_s']}
    attachment=np.array(plan.get('tcp_from_object',FLIP))
    robot, world = objects(plan)
    current = np.array(start, dtype=float).copy()
    opened=float(plan.get('object_adapter',{}).get('open_rad',1.586))
    closed=float(plan.get('object_adapter',{}).get('closed_rad',2.70))
    period=plan['period_s']
    stats = {'model_samples_checked':0, 'minimum_finger_height_mm':float('inf'),
             'minimum_payload_bottom_loaded_mm':float('inf'), 'maximum_chord_error_mm':0.,'maximum_loaded_tilt_deg':0.}
    released = None

    def append(label, target=None, *, xyz=None, tilt=25, carrying=True, seconds=None):
        nonlocal current, released
        initial = current.copy()
        vmax=19.8 if profile and label=='PLACE' else (36.3 if profile else 12.)
        amax=65.34 if profile and label=='PLACE' else (119.79 if profile else 24.)
        vmax*=speed_multiplier;amax*=acceleration_scale
        if xyz is not None:
            a = robot.fk(np.r_[current[:5],0.])[:3,3]
            b = np.array(xyz, dtype=float)
            count = max(3, math.ceil(np.linalg.norm(b-a)/(5 if profile else 10)))
            knots = [current.copy()]
            for u in np.linspace(0,1,count+1)[1:]:
                q = solve_position(robot,a+(b-a)*u,knots[-1],tilt)
                q[5] = closed if carrying else opened
                knots.append(q)
            spline = PchipInterpolator(np.linspace(0,1,count+1), np.array(knots)[:,:5], axis=0)
            endpoint = knots[-1]
            duration = max(1.0/speed_multiplier, np.linalg.norm(b-a)/((80 if profile else 35)*speed_multiplier), 1.875*np.max(np.abs(endpoint[:5]-initial[:5]))/math.radians(vmax))
        else:
            endpoint = np.array(target, dtype=float)
            duration = max(1.0/speed_multiplier, 1.875*np.max(np.abs(endpoint[:5]-initial[:5]))/math.radians(vmax))
        if seconds is not None:
            duration = max(duration, seconds)
        for _ in range(8):
            n = math.ceil(duration/period)
            progress = np.linspace(0,1,n+1)
            progress = 10*progress**3-15*progress**4+6*progress**5
            arm = spline(progress) if xyz is not None else initial[:5]+progress[:,None]*(endpoint[:5]-initial[:5])
            padded = np.vstack([arm[0],arm[0],arm,arm[-1],arm[-1]])
            v = np.diff(padded,axis=0)/period
            acc = np.diff(v,axis=0)/period
            ratio = max(float(np.abs(v).max())/math.radians(vmax), math.sqrt(float(np.abs(acc).max())/math.radians(amax)))
            if ratio <= 1.00001:
                break
            duration *= ratio*1.02
        else:
            raise ValueError('Native timing bounds unsatisfied')
        frames = []
        for i, arm_q in enumerate(arm):
            q = np.r_[arm_q, closed if carrying else opened]
            pose = robot.fk(np.r_[q[:5],0.])
            object_pose = pose @ attachment if carrying else released
            bottom = float(object_pose[2,3]-payload_half_extents(plan,object_pose)[2])
            payload = {'size_mm':payload_spec(plan)['size_mm'], 'grasp_from_object':attachment if carrying else np.linalg.inv(pose)@released}
            support_contact=not carrying
            if label=='PLACE':
                support=np.array(task['request']['destination']['support_centre_mm'])
                half_xy=payload_half_extents(plan,object_pose)[:2]
                footprint=np.array(task['request']['destination']['size_xy_mm'])/2-half_xy-np.abs(object_pose[:2,3]-support[:2])
                # During approach the cube may overhang the support edge while
                # remaining entirely above its top. Full containment is a
                # release condition, not a requirement for approaching it.
                support_contact=bool(bottom>=support[2]-.15)
            for hand in (0.,.75,1.5):
                model_q = np.r_[q[:5],hand]
                robot.check_q(model_q)
                try:
                    world.check(model_q, payload=payload, payload_support_contact=support_contact)
                except ValueError as exc:
                    raise ValueError(f'{label}: {exc}; object_bottom={bottom:.3f}, object_centre={object_pose[:3,3].tolist()}, support_contact={support_contact}') from exc
                boxes = world.link_boxes(model_q)
                stats['minimum_finger_height_mm'] = min(stats['minimum_finger_height_mm'], *(float(boxes[k].corners[:,2].min()) for k in ('link5','gripper_link')))
                stats['model_samples_checked'] += 1
            if carrying:
                stats['minimum_payload_bottom_loaded_mm'] = min(stats['minimum_payload_bottom_loaded_mm'],bottom)
                actual_tilt = math.degrees(math.acos(float(np.clip(object_pose[2,2],-1,1))))
                stats['maximum_loaded_tilt_deg']=max(stats['maximum_loaded_tilt_deg'],actual_tilt)
                if actual_tilt > practical['loaded_pitch_limit_from_vertical_deg']+.1:
                    raise ValueError('Interpolated loaded orientation exceeded25deg')
                if label in ('BUFFER','PREPLACE') and bottom < 62:
                    raise ValueError('Transit payload lower corner below62mm')
            if xyz is not None:
                delta = b-a
                t = float(np.clip(np.dot(pose[:3,3]-a,delta)/max(np.dot(delta,delta),1e-9),0,1))
                error = float(np.linalg.norm(pose[:3,3]-(a+delta*t)))
                stats['maximum_chord_error_mm'] = max(stats['maximum_chord_error_mm'],error)
                if error > 1.2:
                    raise ValueError(f'Cartesian interpolation error {error:.2f}mm')
            command = {'T':102, **dict(zip(('base','shoulder','elbow','wrist','roll'),arm_q.tolist())),
                       'hand':float(q[5]), 'spd':practical['native_stream_spd'], 'acc':practical['native_stream_acc']}
            frames.append({'wire_json':json.dumps(command,separators=(',',':')), 'command_firmware_rad':dict(zip(NAMES,q.tolist())),
                           'model_q':[*arm_q.tolist(),0. if carrying else 1.5]})
        current = np.r_[arm[-1],closed if carrying else opened]
        stage = {'phase':label,'carrying':carrying,'start_firmware_rad':dict(zip(NAMES,initial.tolist())),
                 'arrival_tolerance_deg':plan['arrival_tolerance_deg'], 'commissioning_tolerance_profile':practical,
                 'stage':{'period_s':period,'stream_frames':frames, 'target_firmware_rad':dict(zip(NAMES,current.tolist())),
                          'nominal_motion_seconds':len(frames)*period, 'maximum_joint_velocity_deg_s':float(np.degrees(np.abs(v).max())),
                          'maximum_joint_acceleration_deg_s2':float(np.degrees(np.abs(acc).max()))}}
        stage['object_centre_at_end_mm'] = (robot.fk(np.r_[current[:5],0.])@attachment)[:3,3].tolist()
        plan['stages'].append(stage)
        return stage

    geometry_check(plan, start, True)
    if profile:
        append('INNER_HOLD',xyz=profile['common']['INNER'],tilt=40)
        append('BUFFER',xyz=profile['common']['B'],tilt=40)
        append('PREPLACE',xyz=selected['PRE'],tilt=40)
        placement_target=np.array(selected['H'],dtype=float)
        if plan.get('payload_placement_from_support'):
            # A corrected grasp changes the tool/object transform. Keep the
            # declared support location; fit the tool point to the cube centre
            # and its lowest corner rather than reusing H as the cube centre.
            support=np.array(task['request']['destination']['support_centre_mm'],dtype=float)
            origin=robot.fk(np.r_[current[:5],0.])[:3,3]
            for _ in range(8):
                candidate=current.copy()
                for u in np.linspace(0,1,25)[1:]:
                    candidate=solve_position(robot,origin+(placement_target-origin)*u,candidate,40)
                pose=robot.fk(np.r_[candidate[:5],0.])@attachment
                bottom=float(pose[2,3]-payload_half_extents(plan,pose)[2])
                error=np.r_[support[:2]-pose[:2,3],support[2]+2.5-bottom]
                if np.linalg.norm(error)<.15:
                    break
                placement_target+=error
            else:
                raise ValueError('Corrected-grasp support placement did not converge')
            plan['corrected_grasp_placement']={'support_centre_mm':support.tolist(),
                'filid_reference_tool_H_mm':selected['H'],'resolved_tool_H_mm':placement_target.tolist(),
                'nominal_cube_bottom_above_support_mm':2.5,
                'scope':'SUPPORT_XY_UNCHANGED; TOOL_OFFSET_RESOLVED_FROM_LOCAL_ATTACHMENT'}
        append('PLACE',xyz=placement_target,tilt=selected['reference_handover_tilt_deg'])
        released=robot.fk(np.r_[current[:5],0.])@attachment
        plan['released_object_pose']=released.tolist();plan['release_after_stage']='PLACE'
        retreat=robot.fk(np.r_[current[:5],0.])[:3,3]-plan.get('release_clearance_mm',4)*robot.frames(np.r_[current[:5],0.])['link5'][:3,0]
        append('RELEASE_CLEARANCE',xyz=retreat,tilt=40,carrying=False)
        plan['intentional_release_contact']={'link':'link5','maximum_initial_lateral_travel_mm':plan.get('release_initial_contact_travel_mm',.5),
                                             'direction':'AWAY_FROM_FIXED_JAW_FACE','nominal_contact_not_force_simulated':True}
        clear_z=plan.get('return_clear_height_mm',selected['H_CLEAR'][2])
        append('RETREAT',xyz=[*retreat[:2],clear_z],tilt=40,carrying=False)
        append('RETURN_CLEAR',xyz=[selected['PRE'][0],selected['PRE'][1],clear_z],tilt=40,carrying=False)
        append('INNER_RETURN',xyz=profile['common']['INNER'],tilt=40,carrying=False)
        home=np.array(config['home_rad']);home[5]=opened
        append('RETURN_LOW_HOME',target=home,carrying=False)
        plan['park_close_wire_json']=json.dumps({'T':106,'cmd':3.10,'spd':100,'acc':20},separators=(',',':'))
        plan['release_wire_json']=json.dumps({'T':106,'cmd':opened,'spd':300,'acc':20},separators=(',',':'))
        plan['offline_verification']=dict(stats,passed=True,rigid_attachment_not_friction=True)
        plan['nominal_motion_seconds']=sum(s['stage']['nominal_motion_seconds'] for s in plan['stages'])
        return plan
    append('BUFFER',xyz=[418,247,95])
    append('PREPLACE',xyz=[260,160,95],tilt=25)
    # Solve the placement plane against all cube corners, including tilt.
    target = np.array([260.,160.,47.5])
    for _ in range(4):
        # Follow a continuous descent seed to test the final support plane.
        candidate=current.copy()
        point=robot.fk(np.r_[candidate[:5],0.])[:3,3]
        for u in np.linspace(0,1,12)[1:]:
            candidate=solve_position(robot,point+(target-point)*u,candidate,25)
        op = robot.fk(candidate) @ FLIP
        bottom = float(op[2,3]-15*np.abs(op[2,:3]).sum())
        target[2] += 32.5-bottom
    append('PLACE',xyz=target,tilt=25)
    released = robot.fk(np.r_[current[:5],0.]) @ FLIP
    plan['released_object_pose'] = released.tolist()
    plan['release_after_stage'] = 'PLACE'
    # First leave the fixed contact face laterally, then lift. A pure vertical
    # withdrawal drags the initial fixed-jaw contact through the modelled cube.
    retreat = released[:3,3]-4*robot.frames(np.r_[current[:5],0.])['link5'][:3,0]
    append('RELEASE_CLEARANCE',xyz=retreat,tilt=25,carrying=False)
    plan['intentional_release_contact'] = {'link':'link5','maximum_initial_lateral_travel_mm':.5,
                                         'direction':'AWAY_FROM_FIXED_JAW_FACE', 'nominal_contact_not_force_simulated':True}
    append('RETREAT',xyz=[*retreat[:2],110],tilt=25,carrying=False)
    home = np.array(config['home_rad']); home[5]=1.586
    append('RETURN_LOW_HOME',target=home,carrying=False)
    plan['park_close_wire_json'] = json.dumps({'T':106,'cmd':3.10,'spd':100,'acc':20},separators=(',',':'))
    plan['release_wire_json'] = json.dumps({'T':106,'cmd':1.586,'spd':300,'acc':20},separators=(',',':'))
    plan['offline_verification'] = dict(stats, passed=True, rigid_attachment_not_friction=True)
    plan['nominal_motion_seconds'] = sum(s['stage']['nominal_motion_seconds'] for s in plan['stages'])
    return plan


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--serve-plan':
        plan = read(sys.argv[2])
        cached = objects(plan)
        print(json.dumps({'status':'READY_LOCAL_GEOMETRY_ONLY'}),flush=True)
        for raw in sys.stdin:
            try:
                item=json.loads(raw)
                result=geometry_check(plan,item['q'],item['carrying'],cached=cached,phase=item.get('phase'))
                print(json.dumps(result),flush=True)
            except Exception as exc:
                print(json.dumps({'error':str(exc)}),flush=True)
        return
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--accepted-pickup',type=Path,default=BASE/'pickup_trials/20261028_081759_8110379/PICKUP_RESULT.json')
    p.add_argument('--closed-capture',type=Path,default=BASE/'pickup_trials/20261028_080620_1061024/CLOSE_10/CLOSE_10_20261028_080642_8730171/POSE_CAPTURE.json')
    p.add_argument('--bottom-mm',type=float,default=80)
    p.add_argument('--filid-profile',type=Path);p.add_argument('--bank',type=int,choices=(0,1,2),default=1)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    plan=prepare(a.capture,a.accepted_pickup,a.closed_capture,a.bottom_mm,a.filid_profile,a.bank)
    write(a.output,plan)
    print(json.dumps({'stages':[(s['phase'],len(s['stage']['stream_frames'])) for s in plan['stages']],
                      'nominal_seconds':plan['nominal_motion_seconds'],'verification':plan['offline_verification']}))


if __name__=='__main__':
    main()
