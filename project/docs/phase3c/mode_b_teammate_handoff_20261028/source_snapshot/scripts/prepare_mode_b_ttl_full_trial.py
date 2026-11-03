"""Fresh local red pickup plus filid postlift connection, offline only.

Transfers one successful pickup locally in desk XY; it does not fit or accept a
global residual model. Firmware hand radians remain distinct from CAD angles.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.interpolate import PchipInterpolator

from prepare_mode_b_loaded_route import (ROOT, NAMES, read, write, digest, objects,
    observed, geometry_check, solve_position, build_postlift_connection, Robot, FLIP)
from pc.mode_b.motion.kinematics import transform


def prepare(capture_path, request_path, closed_run=None, grasp_correction=None, speed_multiplier=1.):
    speed_multiplier=float(speed_multiplier)
    if not math.isfinite(speed_multiplier) or not 0<speed_multiplier<=3:
        raise ValueError('Commissioning speed multiplier must be within(0,3]')
    request=read(request_path)
    if request.get('source_planning_strategy',{}).get('mode')=='TODAY_SUCCESSFUL_NATIVE_RELATIVE_TRANSFER':
        if closed_run or grasp_correction:
            raise ValueError('Use the bound successful-source transfer without legacy closure/offset overrides')
        from prepare_mode_b_empirical_transfer import prepare as prepare_relative
        return prepare_relative(capture_path,request_path,speed_multiplier)
    source=ROOT/'artifacts/phase3c/mode_b_ttl_20261028/filid_postlift_bank1/LOADED_ROUTE_PLAN.json'
    prior=read(source);accepted=read(prior['accepted_pickup_file'])
    if accepted['status']!='PICKUP_LIFT_OPERATOR_ACCEPTED_HOLDING_RED' or digest(prior['accepted_pickup_file'])!=prior['accepted_pickup_sha256']:
        raise ValueError('Successful physical pickup reference changed')
    current=observed(read(capture_path))
    if closed_run:
        previous=read(closed_run)
        if not previous.get('requests') or previous['requests'][-1]['label']!='CLOSE_SOURCE' or 'LIFT' in previous.get('completed_stages',[]):
            raise ValueError('A completed closure with no subsequent lift is required')
        original=read(previous['route_file'])
        if digest(previous['route_file'])!=previous['route_sha256'] or original['source_metric_request_sha256']!=digest(request_path):
            raise ValueError('Closure and fresh target do not match')
        previous_q=np.array([previous['final_firmware_rad'][n] for n in NAMES])
        if np.degrees(abs(previous_q-current)).max()>.5 or not 2.50<=current[5]<=2.75:
            raise ValueError('Closed contact plateau or pose changed before continuation')
    home=read(ROOT/'config/ai_pc/robot_home_current.json')
    practical=read(ROOT/'config/ai_pc/mode_b_commissioning_tolerance_20261028.json')
    for i,n in enumerate(NAMES):
        if not closed_run and abs(math.degrees(current[i]-home['firmware_joint_rad'][n]))>practical['arrival_tolerance_deg'][n]:
            raise ValueError('Restart requires accepted empty low HOME: '+n)
    if not closed_run and not 3.0<=current[5]<=math.pi:
        raise ValueError('Empty closed HOME expected')
    reference_source=np.array(prior['request']['pickup']['centre_mm'],dtype=float)
    reference_yaw=float(prior['request']['pickup']['yaw_deg'])
    frame_correction=request.get('desktop_frame_correction')
    strategy=request.get('source_planning_strategy',{})
    if strategy.get('mode')=='TODAY_SUCCESSFUL_HIGH_REGISTRATION_ONLY':
        raise ValueError('High-only source registration cannot drive a complete pickup or loaded transfer')
    absolute_source=strategy.get('mode')=='ABSOLUTE_DESKTOP_ASYMMETRIC_TCP'
    if absolute_source:
        approval_path=Path(strategy['operator_approval_file'])
        approval=read(approval_path)
        if (digest(approval_path)!=strategy['operator_approval_sha256']
                or approval.get('operator_authorized_full_trial') is not True
                or approval.get('table_transform_sha256')!=request.get('table_transform_sha256')
                or np.linalg.norm(np.array(request['pickup']['centre_mm'][:2])-approval['operator_approved_candidate_xy_mm'])>approval['maximum_trial_source_distance_mm']):
            raise ValueError('Matching operator-approved local coordinate trial required')
    old_workspace=read(ROOT/'config/ai_pc/rgb_workspace_20261027_desktop_candidate.json')
    if request.get('table_transform_file'):
        if digest(request['table_transform_file'])!=request.get('table_transform_sha256'):
            raise ValueError('Request table transform changed')
        if request['table_transform_sha256']!=old_workspace['table_sha256'] and not frame_correction and not absolute_source:
            raise ValueError('Changed camera pose requires a new physical grasp-source anchor; old source pixels/XY cannot be reused with new extrinsics')
    if frame_correction:
        if frame_correction['previous_table_sha256']!=old_workspace['table_sha256']:
            raise ValueError('Historical grasp and coordinate correction use different source frames')
        check_path=ROOT/frame_correction['direction_check_file']
        if digest(check_path)!=frame_correction['direction_check_sha256'] or not read(check_path)['passed']:
            raise ValueError('Checked new coordinate registration required')
        matrix=np.array(frame_correction['previous_to_corrected'],dtype=float)
        if matrix.shape!=(4,4) or not np.isfinite(matrix).all() or not np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(matrix[:3,:3]),1):
            raise ValueError('Invalid historical source frame correction')
        reference_source=(matrix@np.r_[reference_source,1.])[:3]
        reference_yaw+=math.degrees(math.atan2(matrix[1,0],matrix[0,0]))
    delta=np.zeros(3) if absolute_source else np.array(request['pickup']['centre_mm'])-reference_source
    yaw_delta=0. if absolute_source else (request['pickup']['yaw_deg']-reference_yaw+45)%90-45
    if request['destination']!={'support_centre_mm':[285,195,150],'size_xy_mm':[80,80],'rim_height_mm':0}:
        raise ValueError('This first complete trial is pinned to filid middle fixture')
    correction_path=grasp_correction or ROOT/'config/ai_pc/mode_b_red_grasp_correction_20261028.json'
    correction=read(correction_path)
    if correction['schema']!='gesture.mode_b.local_red_grasp_correction.v1' or request['object_class']!='red_cube':
        raise ValueError('Invalid local red grasp correction')
    source_limit=float(correction['maximum_source_transfer_xy_mm'])
    if not math.isfinite(source_limit) or not 0<source_limit<=150:
        raise ValueError('Invalid local source transfer envelope')
    if np.linalg.norm(delta[:2])>source_limit or abs(delta[2])>.01 or abs(yaw_delta)>10:
        raise ValueError('New source exceeds this one-pickup local transfer envelope')
    away=float(correction['away_from_base_mm'])
    if absolute_source and away!=0:
        raise ValueError('Do not stack the old camera-source correction onto an absolute desktop solution')
    if not math.isfinite(away) or not 0<=away<=25:
        raise ValueError('Local source correction must be finite and within25mm')
    radial=np.array(request['pickup']['centre_mm'][:2])-correction['base_axis_xy_mm']
    if np.linalg.norm(radial)<100:
        raise ValueError('Source radial direction is not well defined near the base')
    offset=np.r_[away*radial/np.linalg.norm(radial),0.]
    measured_offset=np.asarray(correction.get('desk_command_correction_mm',[0,0,0]),dtype=float)
    if measured_offset.shape!=(3,) or not np.isfinite(measured_offset).all() or np.linalg.norm(measured_offset[:2])>80 or abs(measured_offset[2])>.01:
        raise ValueError('Local measured XY command adjustment must be finite, within80mm, with unchanged height')
    if np.linalg.norm(measured_offset)>0:
        evidence_path=Path(correction['measured_correction_file'])
        evidence=read(evidence_path)
        if (digest(evidence_path)!=correction['measured_correction_sha256']
                or evidence.get('operator_confirmed_observed_at_pickup_low') is not True
                or evidence.get('operator_confirmed_camera_xy_correct') is not True
                or not np.allclose(evidence['desired_tool_motion_desk_mm'],measured_offset,rtol=0,atol=1e-8)):
            raise ValueError('Matching measured pickup-low correction evidence required')
    offset+=measured_offset
    plan=deepcopy(prior)
    for key in ('initial_support_separation','intentional_release_contact','only_holding_recovery','expected_final_payload_pose'):
        plan.pop(key,None)
    plan.update(scope='FRESH_RED_LOCAL_TTL_COMPLETE_COMMISSIONING_TRIAL',request=request,stages=[],
        start_firmware_rad=dict(zip(NAMES,current.tolist())),capture_file=str(capture_path.resolve()),capture_sha256=digest(capture_path),
        current_capture_role='EMPTY_LOW_HOME_POST_REBOOT',source_metric_request_file=str(request_path.resolve()),
        speed_multiplier=speed_multiplier,
        source_metric_request_sha256=digest(request_path),support_height_physically_ready=True,
        fixture_source='OPERATOR_SAYS_SAME_AS_FILID;80X80_RIM_FREE_PROXY_NOT_INDEPENDENTLY_MEASURED',
        stationary_source_phases=['DIRECT_PREGRASP','DESCEND'],
        release_clearance_mm=8,release_initial_contact_travel_mm=2,
        return_clear_height_mm=225,
        payload_placement_from_support=bool(absolute_source or away or frame_correction),
        local_transfer={'delta_desk_mm':delta.tolist(),'yaw_delta_equivalent_deg':yaw_delta,
            'maximum_xy_envelope_mm':source_limit,'source_plan_sha256':digest(source),
            'historical_source_in_current_frame_mm':None if absolute_source else reference_source.tolist(),
            'historical_source_rebased':bool(frame_correction),
            'historical_source_camera_xy_reused':not absolute_source,
            'source_planning_strategy':strategy,
            'new_physical_height_measurement':False,'global_residual_calibration':False},
        local_grasp_correction={'file':str(correction_path.resolve()),'sha256':digest(correction_path),
            'away_from_base_mm':away,'desk_command_offset_mm':offset.tolist(),
            'measured_desk_correction_mm':measured_offset.tolist(),
            'measured_correction_evidence':correction.get('measured_correction_file'),
            'applied_to_commands':not bool(closed_run),
            'scope':correction['scope'],'physical_grasp_corrected_accepted':False,
            'simulation_attachment_role':'KNOWN_SOURCE_ANCHOR_WITH_LOCAL_RESIDUAL; NOT_PHYSICAL_FINGER_CONTACT_VALIDATION'},
        global_calibration_changed=False,physical_general_mapping_calibrated=False,
        source_nominal_destination_plan_rejected=True)
    # Recover the actual successful pickup frame before the historical lift.
    # In absolute mode only the native posture and physical height datum are
    # retained. The previous camera source and its19mm correction are excluded.
    if absolute_source:
        nominal=Robot(ROOT,plan['local_scene_config'],grasp_width_mm=30)
        plan['link5_from_local_object_tcp']=nominal.grasp.tolist()
        plan['tcp_from_object']=FLIP.tolist()
    robot,world=objects(plan)
    low=observed(read(prior['closed_pickup_capture']))
    old_tcp=robot.fk(np.r_[low[:5],0.])[:3,3]
    # Keep the camera object coordinates intact. This is an additional local
    # command correction from two observed misses, not an object displacement
    # or a global calibration. Never apply it again to a closed-run capture.
    qlow=low.copy()
    if closed_run:
        qlow=current.copy()
    else:
        displacement=np.array(request['pickup']['centre_mm'])+offset-old_tcp if absolute_source else delta+offset
        for u in np.linspace(0,1,17)[1:]:
            qlow=solve_position(robot,old_tcp+displacement*u,qlow,15 if absolute_source else 40)
    source_pose=transform(request['pickup']['centre_mm'],[0,0,math.radians(request['pickup']['yaw_deg'])])
    attachment=np.linalg.inv(robot.fk(np.r_[qlow[:5],0.]))@source_pose
    plan['tcp_from_object']=attachment.tolist()
    plan['initial_object_pose']=source_pose.tolist()
    plan['initial_source_object_pose']=source_pose.tolist()
    plan['released_object_pose']=source_pose.tolist()
    plan['measured_object_bottom_mm']=None
    plan['height_anchor_correction_mm']=0
    plan['xy_source']='FRESH_VISION_PLUS_LOCAL_SUCCESSFUL_FIXED_JAW_CORRECTION; NOT_GLOBAL_CALIBRATION'
    if absolute_source:
        plan['xy_source']='OPERATOR_APPROVED_CURRENT_DESKTOP_XY; ASYMMETRIC_NOMINAL_TCP_WITH_PHYSICAL_HEIGHT_DATUM; NOT_GLOBAL_CALIBRATION'
        plan['local_transfer']['camera_source_centre_mm']=request['pickup']['centre_mm']
        plan['local_transfer']['absolute_source_ik_target_mm']=(np.array(request['pickup']['centre_mm'])+offset).tolist()
        plan['local_grasp_correction']['simulation_attachment_role']='LOCAL_MEASURED_COMMAND_RESIDUAL_BOUND_TO_FIXED_CAMERA_SOURCE; NOT_PHYSICAL_FINGER_CONTACT_VALIDATION'
    robot,world=objects(plan)
    qhigh=qlow.copy()
    pregrasp_knots=[qlow.copy()]
    low_position=robot.fk(np.r_[qlow[:5],0.])[:3,3]
    for rise in np.linspace(0,106,29)[1:]:
        qhigh=solve_position(robot,low_position+[0,0,rise],qhigh,40)
        pregrasp_knots.append(qhigh.copy())
    period=.04;stats={'model_samples_checked':0,'maximum_chord_mm':0.,'maximum_pickup_payload_tilt_deg':0.}

    def append(label, knots, carrying, hand, line=None):
        nonlocal current
        knots=np.array(knots);duration=max(2.,1.875*float(abs(knots[-1,:5]-knots[0,:5]).max())/math.radians(12))/speed_multiplier
        spline=PchipInterpolator(np.linspace(0,1,len(knots)),knots[:,:5],axis=0)
        for _ in range(10):
            count=math.ceil(duration/period);u=np.linspace(0,1,count+1)
            arm=spline(10*u**3-15*u**4+6*u**5)
            pad=np.vstack([arm[0],arm[0],arm,arm[-1],arm[-1]])
            v=np.diff(pad,axis=0)/period;acc=np.diff(v,axis=0)/period
            ratio=max(float(abs(v).max())/math.radians(12*speed_multiplier),math.sqrt(float(abs(acc).max())/math.radians(24*speed_multiplier**2)))
            if ratio<=1.00001:break
            duration*=ratio*1.02
        else:raise ValueError('Local pickup timing failed')
        frames=[];local_practical=deepcopy(practical)
        stream_spd=round(160*speed_multiplier);stream_acc=round(20*speed_multiplier**2)
        local_practical.update(native_stream_spd=stream_spd,native_stream_acc=stream_acc)
        for values in arm:
            q=np.r_[values,hand]
            check=geometry_check(plan,q,carrying,cached=(robot,world),phase=label)
            stats['model_samples_checked']+=3
            if carrying:stats['maximum_pickup_payload_tilt_deg']=max(stats['maximum_pickup_payload_tilt_deg'],check['object_tilt_deg'])
            if line is not None:
                a,b=line;p=robot.fk(np.r_[values,0.])[:3,3];d=b-a
                error=float(np.linalg.norm(p-(a+np.clip(np.dot(p-a,d)/np.dot(d,d),0,1)*d)))
                if error>1:raise ValueError('Nonvertical pickup/lift chord')
                stats['maximum_chord_mm']=max(stats['maximum_chord_mm'],error)
            wire={'T':102,**dict(zip(('base','shoulder','elbow','wrist','roll'),values.tolist())),'hand':hand,'spd':stream_spd,'acc':stream_acc}
            frames.append({'wire_json':json.dumps(wire,separators=(',',':')),'command_firmware_rad':dict(zip(NAMES,q.tolist())),
                           'model_q':[*values.tolist(),0. if carrying or label=='DIRECT_PREGRASP' else 1.5]})
        plan['stages'].append({'phase':label,'carrying':carrying,'start_firmware_rad':dict(zip(NAMES,current.tolist())),
            'arrival_tolerance_deg':deepcopy(plan['arrival_tolerance_deg']),'commissioning_tolerance_profile':local_practical,
            'stage':{'period_s':period,'stream_frames':frames,'target_firmware_rad':dict(zip(NAMES,[*arm[-1],hand])),
                     'nominal_motion_seconds':len(frames)*period}})
        current=np.r_[arm[-1],hand]

    if not closed_run:
        append('DIRECT_PREGRASP',[current,qhigh],False,float(current[5]))
        current[5]=1.586
        a=robot.fk(np.r_[current[:5],0.])[:3,3];b=robot.fk(np.r_[qlow[:5],0.])[:3,3]
        # Reverse the same IK branch used for pregrasp. Re-solving downward
        # can reach the same XYZ with another pitch, invalidating the low
        # attachment and causing an artificial dip at the start of LIFT.
        knots=[np.r_[q[:5],1.586] for q in reversed(pregrasp_knots)]
        append('DESCEND',knots,False,1.586,(a,b))
    # At the source only the declared finger surfaces may touch the cube.
    current[5]=2.70
    a=robot.fk(np.r_[current[:5],0.])[:3,3];b=a+[0,0,105]
    knots=[current.copy()]
    for u in np.linspace(0,1,29)[1:]:
        knots.append(solve_position(robot,a+(b-a)*u,knots[-1],40))
    append('LIFT',knots,True,2.70,(a,b))
    front=deepcopy(plan['stages']);front_end=current.copy()
    plan['stages']=[]
    tail=build_postlift_connection(plan,current)
    tail_stats=deepcopy(tail['offline_verification'])
    tail['stages']=front+tail['stages']
    tail['offline_verification']={'passed':True,'pickup':stats,'postlift':tail_stats}
    tail['pickup_nominal_lift_end_firmware_rad']=dict(zip(NAMES,front_end.tolist()))
    tail['nominal_motion_seconds']=sum(s['stage']['nominal_motion_seconds'] for s in tail['stages'])
    tail['open_before_descent_wire_json']=json.dumps({'T':106,'cmd':1.586,'spd':300,'acc':20},separators=(',',':'))
    tail['close_after_descent_wire_json']=json.dumps({'T':106,'cmd':2.70,'spd':40,'acc':5},separators=(',',':'))
    tail['grasp_contact_allowance']={'phases':['DESCEND'],'links':['link5','gripper_link'],
        'scope':'INTENDED_GRASP_CONTACT_ONLY; TABLE_SUPPORT_OTHER_ARM_PAIRS_ALWAYS_CHECKED'}
    tail['pc_confirm_delivery']='OPERATOR_AUTHORIZED_FULL_FIXED_SUPPORT_TRIAL; PRE2S_AND_CONFIRM0_5S_WITHOUT_FPGA_GESTURES'
    tail['closure_attachment_policy']='ACTUAL_CLOSED_CAPTURE' if closed_run else 'NOMINAL_LOCAL_CORRECTED_GRASP; NO_AUTOMATIC_REANCHOR'
    if closed_run:
        tail['scope']='FRESH_RED_CLOSED_TTL_CONTINUATION_COMMISSIONING_TRIAL'
        tail['continued_from_closed_run']=str(closed_run.resolve())
        tail['continued_from_closed_run_sha256']=digest(closed_run)
        tail['current_capture_role']='STABLE_ACTUAL_CLOSURE_BEFORE_FIRST_LIFT'
        tail['attachment_source']='KNOWN_FRESH_VISION_SOURCE_POSE_AND_ACTUAL_CLOSED_JOINTS; GRIP_AND_NO_SLIDE_NOT_PHYSICALLY_RECONFIRMED'
    return tail


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','request','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--closed-run',type=Path)
    parser.add_argument('--grasp-correction',type=Path)
    parser.add_argument('--speed-multiplier',type=float,default=1.)
    args=parser.parse_args()
    try:
        plan=prepare(args.capture,args.request,args.closed_run,args.grasp_correction,args.speed_multiplier)
        write(args.output,plan)
        print(json.dumps({'stages':[s['phase'] for s in plan['stages']],'seconds':plan['nominal_motion_seconds'],'checked':plan['offline_verification']}))
    except Exception as exc:
        write(args.output.parent/'PLANNING_FAILED.json',{'passed':False,'error':str(exc),'motion_commands_sent':0})
        raise
