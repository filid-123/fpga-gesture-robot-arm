"""Transfer the newly accepted native pickup locally, from HOME to HOME.

Only camera DIFFERENCES from the co-located successful source are used. This
keeps the measured servo/geometry residual in the demonstrated commands instead
of solving the new absolute camera point with an uncalibrated nominal TCP.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

from prepare_mode_b_loaded_route import (ROOT,NAMES,read,digest,write,observed,
    objects,geometry_check,build_postlift_connection,FLIP)
from pc.roarm_reference_kinematics import ReferenceGeometry,forward,inverse_endpoint
from pc.mode_b.motion.kinematics import Robot,transform


def check_source_correction_locality(adapter,source):
    """Keep a measured residual correction close to its measured source."""
    locality=adapter.get('source_correction_locality')
    if locality is None:return None
    centre=np.asarray(locality['reference_source_centre_mm'],float)
    point=np.asarray(source,float);radius=float(locality['maximum_xy_distance_mm'])
    if (adapter.get('object_class')!='eraser' or centre.shape!=(3,) or point.shape!=(3,)
            or not np.isfinite(centre).all() or not np.isfinite(point).all()
            or not math.isfinite(radius) or not 0<radius<=25):
        raise ValueError('Invalid local measured-source correction envelope')
    evidence=Path(adapter['operator_source_correction_file']);record=read(evidence)
    if (digest(evidence)!=adapter['operator_source_correction_sha256']
            or record.get('reference_source_centre_mm')!=centre.tolist()
            or digest(record['source_result_file'])!=record['source_result_sha256']):
        raise ValueError('Local measured-source correction evidence changed')
    distance=float(np.linalg.norm(point[:2]-centre[:2]))
    if distance>radius or abs(point[2]-centre[2])>.01:
        raise ValueError('Source is outside the25mm measured-correction neighbourhood')
    return dict(locality,current_source_xy_distance_mm=distance)


def prepare(capture_path,request_path,speed_multiplier=2.,transit_speed_profile=None):
    if not math.isfinite(speed_multiplier) or not 0<speed_multiplier<=3:
        raise ValueError('Speed multiplier must be within(0,3]')
    request=read(request_path);strategy=request.get('source_planning_strategy',{})
    if strategy.get('mode')!='TODAY_SUCCESSFUL_NATIVE_RELATIVE_TRANSFER':
        raise ValueError('A successful-source relative-transfer request is required')
    anchor_path=Path(strategy['anchor_file']);anchor=read(anchor_path)
    if digest(anchor_path)!=strategy['anchor_sha256'] or anchor['status']!='OPERATOR_ACCEPTED_PICKUP_DELIVERY_HOME':
        raise ValueError('Operator-accepted source anchor changed')
    result=read(anchor['accepted_result_file']);original=read(anchor['accepted_plan_file'])
    if (digest(anchor['accepted_result_file'])!=anchor['accepted_result_sha256']
            or digest(anchor['accepted_plan_file'])!=anchor['accepted_plan_sha256']
            or not all(result.get(k) is True for k in ('physical_pickup_confirmed','physical_delivery_confirmed',
                'transport_no_slip_operator_confirmed','return_home_operator_confirmed'))):
        raise ValueError('Successful physical pickup/delivery/HOME evidence required')
    object_name=request.get('object_class','red_cube')
    if object_name not in ('red_cube','small_canister','eraser'):
        raise ValueError('Unsupported empirical object adapter')
    adapter={}
    if object_name in ('small_canister','eraser') or (object_name=='red_cube' and request.get('object_adapter_file')):
        adapter_path=Path(request['object_adapter_file']).resolve()
        if adapter_path.parent!=(ROOT/'config/ai_pc').resolve() or digest(adapter_path)!=request['object_adapter_sha256']:
            raise ValueError('Cylinder adapter binding changed')
        adapter=read(adapter_path)
        expected=original['local_scene_config']['objects'][object_name]
        if adapter['size_mm']!=expected['size_mm'] or adapter['shape']!=expected['shape'] or adapter['object_class']!=object_name:
            raise ValueError('Cylinder adapter dimensions differ from registered object')
    red_depth=None
    if object_name=='red_cube' and adapter:
        from mode_b_red_depth import validate as validate_red_depth
        red_depth=validate_red_depth(adapter,request)
    opened=float(adapter.get('open_rad',1.586));closed=float(adapter.get('closed_rad',2.70))
    source_correction=np.array(adapter.get('desk_command_correction_mm',[0.,0.,0.]),float)
    if source_correction.shape!=(3,) or not np.isfinite(source_correction).all() or np.linalg.norm(source_correction)>20 or source_correction[2]!=0:
        raise ValueError('Source correction must be a finite local XY offset within20mm')
    if np.linalg.norm(source_correction)>0:
        evidence=Path(adapter['operator_source_correction_file'])
        if digest(evidence)!=adapter['operator_source_correction_sha256'] or read(evidence)['desk_command_correction_mm']!=source_correction.tolist():
            raise ValueError('Object-specific source correction lacks matching operator evidence')
    correction_locality=check_source_correction_locality(adapter,request['pickup']['centre_mm'])
    object_size=np.array(original['local_scene_config']['objects'][object_name]['size_mm'],float)
    grasp_width=float(object_size[1] if object_name=='eraser' else object_size[0])
    height_adjustment=float(adapter.get('fingertip_height_adjustment_mm',0.))
    if not math.isfinite(height_adjustment) or not (-12 if red_depth else -10)<=height_adjustment<=0:
        raise ValueError('Invalid local fingertip height adjustment')
    if request['table_transform_sha256']!=anchor['table_transform_sha256'] or digest(request['table_transform_file'])!=anchor['table_transform_sha256']:
        raise ValueError('Camera pose differs from the co-located accepted source')
    delta=np.array(request['pickup']['centre_mm'],float)-anchor['source_camera_centre_mm']
    yaw_delta=0. if object_name=='small_canister' else (request['pickup']['yaw_deg']-anchor['source_yaw_deg']+45)%90-45
    if object_name=='eraser':
        yaw_delta=(request['pickup']['yaw_deg']+90-anchor['source_yaw_deg']+90)%180-90
    expected_dz=float(object_size[2]/2-anchor['source_camera_centre_mm'][2])
    if np.linalg.norm(delta[:2])>anchor['maximum_source_transfer_xy_mm'] or abs(delta[2]-expected_dz)>.01:
        raise ValueError('New source exceeds the150mm local transfer envelope')
    if request['destination']!=original['request']['destination']:
        raise ValueError('Keep the accepted filid support fixture')
    current=observed(read(capture_path));home=read(ROOT/'config/ai_pc/robot_home_current.json')
    practical=read(ROOT/'config/ai_pc/mode_b_commissioning_tolerance_20261028.json')
    for i,n in enumerate(NAMES):
        if abs(math.degrees(current[i]-home['firmware_joint_rad'][n]))>practical['arrival_tolerance_deg'][n]:
            raise ValueError('Empty accepted low HOME required: '+n)
    if not 3<=current[5]<=math.pi:raise ValueError('Empty closed HOME expected')
    plan=deepcopy(original)
    if red_depth and red_depth['additional_descent_mm']==12:
        plan['local_scene_config']['table_clearance_by_link_mm']={'link5':.25,'gripper_link':.25}
        plan['joint_transit_phases']=['BUFFER','PREPLACE']
        plan['phase_speed_multiplier']={'BUFFER':2.0,'PREPLACE':2.0}
        return_profile=adapter.get('postrelease_return_profile')
        if return_profile:
            reference_result=Path(return_profile['basis_result_file'])
            if (return_profile.get('schema')!='gesture.mode_b.red_postrelease_speed.v1'
                    or return_profile.get('joint_phases')!=['RETREAT','RETURN_CLEAR']
                    or return_profile.get('phase_speed_multiplier')!={'RETREAT':2.0,'RETURN_CLEAR':2.0}
                    or return_profile.get('preserve_lateral_clearance_mm')!=8
                    or digest(reference_result)!=return_profile['basis_result_sha256']):
                raise ValueError('Invalid measured red return speed profile')
            previous=read(reference_result);previous_plan=read(previous['route_file'])
            if (previous.get('error') or digest(previous['route_file'])!=previous['route_sha256']
                    or previous['completed_stages']!=[s['phase'] for s in previous_plan['stages']]
                    or previous_plan['red_pickup_depth_correction']['additional_descent_mm']!=12):
                raise ValueError('Return speed adjustment requires the completed measured depth12 trial')
            plan['joint_transit_phases']+=return_profile['joint_phases']
            plan['phase_speed_multiplier'].update(return_profile['phase_speed_multiplier'])
            plan['postrelease_return_speed_policy']=deepcopy(return_profile)
    if adapter:plan['object_adapter']=adapter
    if red_depth:plan['red_pickup_depth_correction']=red_depth
    if correction_locality:plan['source_correction_locality']=correction_locality
    if transit_speed_profile:
        from mode_b_transit_speed import apply as apply_transit_speed
        apply_transit_speed(plan,transit_speed_profile)
    for key in ('initial_support_separation','intentional_release_contact','expected_final_payload_pose',
                'operator_measurement_file','operator_measurement_sha256','successful_native_reference'):
        plan.pop(key,None)
    plan.update(scope='FRESH_RED_LOCAL_TTL_COMPLETE_COMMISSIONING_TRIAL',request=request,stages=[],
        capture_file=str(capture_path.resolve()),capture_sha256=digest(capture_path),
        start_firmware_rad=dict(zip(NAMES,current.tolist())),current_capture_role='EMPTY_LOW_HOME_FRESH_RELATIVE_TRANSFER',
        source_metric_request_file=str(request_path.resolve()),source_metric_request_sha256=digest(request_path),
        stationary_source_phases=['DIRECT_PREGRASP','DESCEND'],speed_multiplier=speed_multiplier,
        accepted_native_source_anchor_file=str(anchor_path.resolve()),accepted_native_source_anchor_sha256=digest(anchor_path),
        old_camera_xy_used_as_physical_anchor=False,measured70_or_previous19_blanket_offset_used=False,
        physical_general_mapping_calibrated=False,local_transfer={'delta_desk_mm':delta.tolist(),
            'yaw_delta_equivalent_deg':yaw_delta,'extra_outward_mm':anchor['next_trial_extra_outward_mm'],
            'scope':'LOCAL_NATIVE_ENDPOINT_DIFFERENCES_FROM_OPERATOR_ACCEPTED_CURRENT_CAMERA_SOURCE'})
    reference=read(ROOT/'config/ai_pc/roarm_reference_geometry.json')
    geo=ReferenceGeometry(**reference['geometry_mm'])
    endpoint=lambda q:np.array(forward(q[:4],geo),float)
    stages={s['phase']:s for s in original['stages']}
    old_low=np.array([stages['DESCEND']['stage']['target_firmware_rad'][n] for n in NAMES])
    yaw_world=plan['local_scene_config']['table_from_urdf_world']['rpy_rad'][2]
    rotation=np.array([[math.cos(yaw_world),-math.sin(yaw_world)],[math.sin(yaw_world),math.cos(yaw_world)]])
    native_delta=np.r_[rotation.T@(delta[:2]+source_correction[:2]),height_adjustment]
    # Keep fingertip clearance and the demonstrated Z curve. The taller object
    # changes its attachment centre, not the fingertip target. A narrower body
    # moves the fixed jaw toward its centre by half the width difference.
    source_robot=Robot(ROOT,plan['local_scene_config'],grasp_width_mm=30)
    source_pose=source_robot.fk(np.r_[old_low[:5],0.])
    width_shift_world=source_pose[:3,0]*(30.-grasp_width)/2
    width_shift_native=np.r_[rotation.T@width_shift_world[:2],width_shift_world[2]]
    native_delta+=width_shift_native
    radial=endpoint(old_low)[:2]+native_delta[:2]
    extra=float(anchor['next_trial_extra_outward_mm'])
    if not 0<=extra<=5 or np.linalg.norm(radial)<100:raise ValueError('Invalid local outward fine adjustment')
    native_delta[:2]+=extra*radial/np.linalg.norm(radial)
    plan['local_transfer']['native_endpoint_delta_mm']=native_delta.tolist()
    plan['local_transfer']['fixed_jaw_width_adjustment_native_mm']=width_shift_native.tolist()
    plan['local_transfer']['object_specific_source_correction_desk_mm']=source_correction.tolist()
    plan['local_transfer']['object_centre_height_change_mm']=expected_dz
    canonical=Robot(ROOT,plan['local_scene_config'],grasp_width_mm=grasp_width)
    eraser_translation=np.r_[rotation@(native_delta[:2]-width_shift_native[:2]),height_adjustment]
    relative_tcp_errors=[]
    wrap=lambda a:(a+math.pi)%(2*math.pi)-math.pi
    def scene_yaw(q):
        T=canonical.fk(np.r_[q[:5],0.])@FLIP
        return math.atan2(T[1,0],T[0,0])
    max_pitch_change=0.
    def native_solve(old_q,seed,phase,progress,first=False,target_xyz=None):
        nonlocal max_pitch_change
        target=endpoint(old_q);target[:3]+=native_delta
        if target_xyz is not None:target[:3]=target_xyz
        flexibility=2 if phase=='DESCEND' and progress>.8 else (10 if phase=='LIFT' else 24)
        pitches=[target[3]]
        for change in (2,4,6,8,10,12,16,20,24):
            if change<=flexibility:pitches.extend([target[3]-math.radians(change),target[3]+math.radians(change)])
        for pitch in pitches:
            if abs(math.degrees(pitch-math.pi/2))>30:continue
            solutions=inverse_endpoint(target[:3],pitch,geo,reference['vendor_reference_position_limits_rad'])
            candidates=[]
            for s in solutions:
                if not s['reference_limit_compatible']:continue
                q=np.r_[[s['joint_rad'][n] for n in NAMES[:4]],old_q[4],old_q[5]]
                a=scene_yaw(q);bumped=q.copy();bumped[4]+=.001
                slope=wrap(scene_yaw(bumped)-a)/.001
                if abs(slope)<.5:continue
                q[4]+=wrap(scene_yaw(old_q)+math.radians(yaw_delta)-a)/slope
                if not canonical.limits[4,0]<=q[4]<=canonical.limits[4,1]:continue
                if not first and abs(q[:5]-seed[:5]).max()>.32:continue
                candidates.append(q)
            if candidates:
                q=min(candidates,key=lambda v:float(abs(v[:5]-seed[:5]).max()))
                max_pitch_change=max(max_pitch_change,abs(math.degrees(pitch-target[3])))
                return q
        raise ValueError('No continuous native IK for new source at '+phase+' '+str(target.tolist()))
    def solve(old_q,seed,phase,progress,first=False):
        if object_name!='eraser':return native_solve(old_q,seed,phase,progress,first)
        # Rotation and the15mm short-side TCP change its relation to the native
        # endpoint. Preserve the demonstrated local TCP displacement rather than
        # rotating a fixed7.5mm compensation about the old closing axis.
        desired=source_robot.fk(np.r_[old_q[:5],0.])[:3,3]+eraser_translation
        target=endpoint(old_q)[:3]+native_delta
        for _ in range(8):
            q=native_solve(old_q,seed,phase,progress,first,target)
            error=desired-canonical.fk(np.r_[q[:5],0.])[:3,3]
            if np.linalg.norm(error)<.03:
                relative_tcp_errors.append(float(np.linalg.norm(error)))
                return q
            target+=np.r_[rotation.T@error[:2],error[2]]
        raise ValueError('Eraser relative TCP transfer failed to converge')
    def translated_knots(label,seed):
        frames=stages[label]['stage']['stream_frames']
        selected=list(range(0,len(frames),3))
        if selected[-1]!=len(frames)-1:selected.append(len(frames)-1)
        rows=[]
        for j,index in enumerate(selected):
            old=np.array([frames[index]['command_firmware_rad'][n] for n in NAMES])
            q=solve(old,rows[-1] if rows else seed,label,index/max(1,len(frames)-1),first=not rows)
            rows.append(q)
        return rows
    descent=translated_knots('DESCEND',old_low)
    low=descent[-1]
    robot,world=objects(plan)
    nominal_low=robot.fk(np.r_[low[:5],0.]);canonical_low=canonical.fk(np.r_[low[:5],0.])
    source_yaw=scene_yaw(low)
    object_yaw=source_yaw-math.pi/2 if object_name=='eraser' else source_yaw
    proxy=transform([*canonical_low[:2,3],float(object_size[2]/2)],[0,0,object_yaw])
    plan['tcp_from_object']=(np.linalg.inv(nominal_low)@proxy).tolist()
    plan['initial_source_object_pose']=proxy.tolist();plan['initial_object_pose']=proxy.tolist()
    plan['released_object_pose']=proxy.tolist()
    plan['source_proxy']={'camera_object_centre_mm':request['pickup']['centre_mm'],
        'nominal_scene_object_centre_mm':proxy[:3,3].tolist(),
        'camera_minus_nominal_model_mm':(np.array(request['pickup']['centre_mm'])-proxy[:3,3]).tolist(),
        'used_as_command_correction':False,
        'scope':'LOCAL_NATIVE_TRANSFER; NOMINAL_PROXY_DOES_NOT_ESTABLISH_ABSOLUTE_PICKUP_CONTACT'}
    robot,world=objects(plan)
    stats={'model_samples_checked':0,'maximum_velocity_deg_s':0.,'maximum_acceleration_deg_s2':0.}
    period=.04
    def append(label,knots,carrying,hand):
        nonlocal current
        knots=np.asarray(knots)
        arc=np.r_[0.,np.cumsum(np.maximum(np.linalg.norm(np.diff(knots[:,:5],axis=0),axis=1),1e-9))];arc/=arc[-1]
        spline=PchipInterpolator(arc,knots[:,:5],axis=0)
        duration=max(2.,1.875*float(abs(np.diff(knots[:,:5],axis=0)).sum(axis=0).max())/math.radians(12))/speed_multiplier
        for _ in range(12):
            count=math.ceil(duration/period);u=np.linspace(0,1,count+1);arm=spline(10*u**3-15*u**4+6*u**5)
            pad=np.vstack([arm[0],arm[0],arm,arm[-1],arm[-1]])
            v=float(abs(np.diff(pad,axis=0)).max())/period;a=float(abs(np.diff(pad,n=2,axis=0)).max())/period**2
            ratio=max(v/math.radians(12*speed_multiplier),math.sqrt(a/math.radians(24*speed_multiplier**2)))
            if ratio<=1.00001:break
            duration*=ratio*1.02
        else:raise ValueError('Relative source timing failed')
        frames=[];stream=deepcopy(practical)
        stream.update(native_stream_spd=round(160*speed_multiplier),native_stream_acc=round(20*speed_multiplier**2))
        for values in arm:
            q=np.r_[values,hand];geometry_check(plan,q,carrying,cached=(robot,world),phase=label)
            stats['model_samples_checked']+=3
            wire={'T':102,**dict(zip(('base','shoulder','elbow','wrist','roll'),values.tolist())),
                'hand':hand,'spd':stream['native_stream_spd'],'acc':stream['native_stream_acc']}
            frames.append({'wire_json':json.dumps(wire,separators=(',',':')),
                'command_firmware_rad':dict(zip(NAMES,q.tolist())),'model_q':[*values.tolist(),0. if carrying or label=='DIRECT_PREGRASP' else 1.5]})
        plan['stages'].append({'phase':label,'carrying':carrying,'start_firmware_rad':dict(zip(NAMES,current.tolist())),
            'arrival_tolerance_deg':deepcopy(plan['arrival_tolerance_deg']),'commissioning_tolerance_profile':stream,
            'stage':{'period_s':period,'stream_frames':frames,'target_firmware_rad':dict(zip(NAMES,[*arm[-1],hand])),
                'nominal_motion_seconds':len(frames)*period}})
        stats['maximum_velocity_deg_s']=max(stats['maximum_velocity_deg_s'],math.degrees(v))
        stats['maximum_acceleration_deg_s2']=max(stats['maximum_acceleration_deg_s2'],math.degrees(a))
        current=np.r_[arm[-1],hand]
    append('DIRECT_PREGRASP',[current,descent[0]],False,float(current[5]))
    current[5]=opened;append('DESCEND',descent,False,opened)
    current[5]=closed;lift=translated_knots('LIFT',current)
    append('LIFT',lift,True,closed)
    front=deepcopy(plan['stages']);plan['stages']=[]
    tail=build_postlift_connection(plan,current);tail_stats=deepcopy(tail['offline_verification'])
    tail['stages']=front+tail['stages'];tail['offline_verification']={'passed':True,'pickup':stats,'postlift':tail_stats}
    tail['nominal_motion_seconds']=sum(s['stage']['nominal_motion_seconds'] for s in tail['stages'])
    tail['open_before_descent_wire_json']=json.dumps({'T':106,'cmd':opened,'spd':300,'acc':20},separators=(',',':'))
    tail['close_after_descent_wire_json']=json.dumps({'T':106,'cmd':closed,'spd':adapter.get('close_speed',40),
        'acc':adapter.get('close_acceleration',5)},separators=(',',':'))
    tail['local_transfer']['maximum_native_pitch_adjustment_deg']=max_pitch_change
    tail['empirical_pickup']={'source_reference':'CURRENT_OPERATOR_ACCEPTED_NATIVE_PLAN',
        'extra_outward_mm':extra,'closure_rad':closed,'old19_or70_offset_used':False,
        'new_physical_height_measurement':False}
    if adapter:
        if object_name!='red_cube':
            tail['scope']='FRESH_ERASER_LOCAL_TTL_COMPLETE_COMMISSIONING_TRIAL' if object_name=='eraser' else 'FRESH_CYLINDER_LOCAL_TTL_COMPLETE_COMMISSIONING_TRIAL'
        tail['object_adapter_file']=str(adapter_path.resolve());tail['object_adapter_sha256']=digest(adapter_path)
        tail['payload_collision_geometry']='CONSERVATIVE_ORIENTED_ENCLOSING_BOX_OFFLINE; CYLINDER_MESH_IN_COPPELIA' if object_name=='small_canister' else 'ORIENTED_BOX_OFFLINE_AND_COPPELIA'
        tail['physical_object_grasp_accepted']=False
        if object_name=='small_canister':tail['physical_cylinder_grasp_accepted']=False
        if object_name=='eraser':
            tail['local_transfer'].update(fingertip_height_adjustment_mm=height_adjustment,
                native_endpoint_delta_mm_is_initial_seed=True,maximum_relative_tcp_error_mm=max(relative_tcp_errors),
                relative_canonical_tcp_translation_world_mm=eraser_translation.tolist(),
                object_yaw_offset_from_closing_axis_deg=-90,closing_symmetry_deg=180)
    return tail


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','request','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--speed-multiplier',type=float,default=2.)
    p.add_argument('--transit-speed-profile',type=Path)
    args=p.parse_args();plan=prepare(args.capture,args.request,args.speed_multiplier,args.transit_speed_profile);write(args.output,plan)
    print(json.dumps({'stages':[s['phase'] for s in plan['stages']],'seconds':plan['nominal_motion_seconds'],'transfer':plan['local_transfer']}))
