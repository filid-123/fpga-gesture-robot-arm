"""CoppeliaSim mesh replay of the exact native commissioning samples.

Uses an isolated, stopped instance on23020. No robot/network-device interface.
This is rigid-payload kinematics, not friction or servo dynamics verification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from prepare_mode_b_loaded_route import objects, read, write, FLIP, payload_spec, payload_half_extents
from pc.mode_b.motion.kinematics import ORDER
from sim.phase3_robot.verify_mode_b_complete_task import sim_matrix,np_matrix


def verify(path,port=23020):
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
    plan=read(path);robot,world=objects(plan)
    attachment=np.array(plan.get('tcp_from_object',FLIP))
    client=RemoteAPIClient(host='127.0.0.1',port=port)
    sim=client.require('sim')
    if sim.getSimulationState()!=sim.simulation_stopped:
        raise ValueError('Dedicated simulator must be stopped')
    sim.closeScene();plugin=client.require('simURDF')
    with tempfile.TemporaryDirectory(prefix='loaded_mode_b_') as temp:
        model=Path(temp)/'model';shutil.copytree(robot.path.parent,model)
        urdf=model/robot.path.name;tree=ET.parse(urdf)
        for e in list(tree.getroot()):
            if e.attrib.get('name') in ('world','world_to_base_link','hand_tcp','link5_to_hand_tcp'):
                tree.getroot().remove(e)
        tree.write(urdf,encoding='utf8',xml_declaration=True)
        name,models=getattr(plugin,'import')(str(urdf),32+256)
    if name!='roarm_m3' or len(models)!=1:raise ValueError('Model import failed')
    aliases={sim.getObjectAlias(h):h for h in sim.getObjectsInTree(sim.handle_scene,sim.handle_all,0)}
    joints=[aliases[n] for n in ORDER];root=models[0]
    base=np_matrix(sim.getObjectMatrix(joints[0],sim.handle_world))
    initial=np_matrix(sim.getObjectMatrix(root,sim.handle_world))
    sim.setObjectMatrix(root,sim.handle_world,sim_matrix(robot.world@robot.origins['world_to_base_link']@np.linalg.inv(base)@initial))
    tcp=sim.createDummy(.01);sim.setObjectAlias(tcp,'loaded_object_tcp')
    sim.setObjectParent(tcp,joints[4],False)
    sim.setObjectMatrix(tcp,sim.handle_parent,sim_matrix(robot.grasp@robot.tool_residual))
    script=sim.createScript(sim.scripttype_customization,(ROOT/'sim/phase3_robot/mode_b_validate.lua').read_text(encoding='utf8'),0,'lua')
    sim.initScript(script)
    def cuboid(name,centre,size):
        h=sim.createPrimitiveShape(sim.primitiveshape_cuboid,(np.array(size)/1000).tolist(),0)
        sim.setObjectAlias(h,name);sim.setObjectPosition(h,sim.handle_world,(np.array(centre)/1000).tolist());return h
    table=cuboid('loaded_table',[400,300,-10],[800,600,20]);static=[table]
    if world.support:static.append(cuboid('loaded_support',world.support.centre,world.support.half*2))
    for ob in world.obstacles:static.append(cuboid(ob.name,ob.centre,ob.half*2))
    spec=payload_spec(plan)
    if spec['shape']=='cylinder':
        payload=sim.createPrimitiveShape(sim.primitiveshape_cylinder,(np.array(spec['size_mm'])/1000).tolist(),0)
        sim.setObjectAlias(payload,'loaded_cylinder')
    else:
        payload=cuboid('loaded_'+plan['request'].get('object_class','red_cube'),[0,0,0],spec['size_mm'])
    sim.setObjectMatrix(payload,sim.handle_world,sim_matrix(plan['initial_object_pose']))
    links={n:aliases[n+'_respondable'] for n in robot.boxes}
    pairs=[[links[a],links[b]] for a,b in world.self_pairs]
    pairs += [[h,s] for n,h in links.items() for s in static if not(n=='base_link' and s==table)]
    pairs += [[payload,h] for n,h in links.items() if n not in ('link5','gripper_link')]
    pairs += [[payload,s] for s in static]
    reports=[];collisions=[];samples=0;max_error=0.
    for stage in plan['stages']:
        qs=np.array([f['model_q'] for f in stage['stage']['stream_frames']])
        final_model_q=qs[-1]
        # The Lua API divides by65536. Floating rows preserve the exact native
        # radian samples; this is explicitly not a PL fixed-point simulation.
        rows=(qs*65536).tolist()
        expected=[(robot.fk(q)[:3,3]/1000).tolist() for q in qs]
        stage_pairs=list(pairs)
        source_phase=stage['phase'] in plan.get('stationary_source_phases', [])
        grasp_contact=stage['phase'] in plan.get('grasp_contact_allowance',{}).get('phases',[])
        source_liftoff=stage['phase'] in plan.get('source_liftoff_phases',['LIFT']) and bool(plan.get('initial_source_object_pose'))
        table_placement=stage['phase'] in plan.get('table_placement_phases',[])
        clearance_phase=stage['phase'] in plan.get('release_clearance_phases',['RELEASE_CLEARANCE'])
        after_table_release=bool(plan.get('released_on_table') and not stage['carrying'] and not source_phase)
        if source_phase or source_liftoff:
            # Cube starts resting on the source tabletop. The fixed table
            # contact is deliberate; arm/table and cube/other pairs remain.
            stage_pairs=[pair for pair in stage_pairs if pair!=[payload,table]]
        if table_placement or after_table_release:
            # Restock places on the source tabletop. Verify the analytic lower
            # envelope independently; only the intended payload/table pair is
            # exempted. Arm/table and all other pairs remain enabled.
            stage_pairs=[pair for pair in stage_pairs if pair!=[payload,table]]
        if table_placement:
            bottoms=[]
            for q in qs:
                pose=robot.fk(q)@attachment
                bottoms.append(float(pose[2,3]-payload_half_extents(plan,pose)[2]))
            if min(bottoms)<-.15:raise ValueError('Restock payload penetrates source tabletop')
        if stage['phase']=='RECOVERY_CONTACT_CLEAR':
            # Existing nominal support overlap is present before any command;
            # only the monotone upward separation stage exempts this pair.
            stage_pairs=[pair for pair in stage_pairs if not(pair[0]==payload and sim.getObjectAlias(pair[1])=='loaded_support')]
        if not stage['carrying'] and not clearance_phase and not grasp_contact:
            stage_pairs += [[payload,links[n]] for n in ('link5','gripper_link')]
        if clearance_phase:
            # Report the bounded initial intended fixed-jaw contact explicitly.
            # All other pairs remain enabled, including the moving finger.
            stage_pairs += [[payload,links['gripper_link']]]
        result=sim.callScriptFunction('modeBReplay',script,rows,joints,tcp,expected,stage_pairs,payload,sim_matrix(attachment),stage['carrying'])
        samples+=result['samples'];max_error=max(max_error,result['maximum_tcp_error_m']*1000)
        if result.get('first_collision'):collisions.append({'phase':stage['phase'],**result['first_collision']})
        reports.append({'phase':stage['phase'],'samples':result['samples'],'maximum_tcp_error_mm':result['maximum_tcp_error_m']*1000})
        if plan.get('only_source_registration') and stage['phase']=='DIRECT_PREGRASP':
            # The high-only executor opens with T106 after the arm stream.
            # Check that held-arm finger sweep against the current source.
            opening=np.array([qs[-1].copy() for _ in range(21)])
            opening[:,5]=np.linspace(0,1.5,21)
            expected=[(robot.fk(q)[:3,3]/1000).tolist() for q in opening]
            checked=sim.callScriptFunction('modeBReplay',script,(opening*65536).tolist(),joints,tcp,expected,
                stage_pairs,payload,sim_matrix(attachment),False)
            samples+=checked['samples']
            if checked.get('first_collision'):collisions.append({'phase':'SOURCE_HIGH_OPEN_SWEEP',**checked['first_collision']})
            reports[-1]['held_arm_open_sweep_samples']=checked['samples']
            final_model_q=opening[-1]
        if source_phase:
            reports[-1]['intentional_source_table_contact']=True
        if grasp_contact:
            reports[-1]['intentional_finger_grasp_contact']=True
            closing=np.array([qs[-1].copy() for _ in range(21)])
            closing[:,5]=np.linspace(1.5,0,21)
            expected=[(robot.fk(q)[:3,3]/1000).tolist() for q in closing]
            checked=sim.callScriptFunction('modeBReplay',script,(closing*65536).tolist(),joints,tcp,expected,
                stage_pairs,payload,sim_matrix(attachment),False)
            samples+=checked['samples']
            if checked.get('first_collision'):collisions.append({'phase':'CLOSE_HAND_SWEEP',**checked['first_collision']})
        if source_liftoff:
            above=[]
            for q in qs:
                pose=robot.fk(q)@attachment
                if pose[2,3]-payload_half_extents(plan,pose)[2]>.5:above.append(q)
            if not above:raise ValueError('Lift never left source table contact')
            expected=[(robot.fk(q)[:3,3]/1000).tolist() for q in above]
            checked=sim.callScriptFunction('modeBReplay',script,(np.array(above)*65536).tolist(),joints,tcp,expected,
                [[payload,table]],payload,sim_matrix(attachment),True)
            if checked.get('first_collision'):collisions.append({'phase':'LIFT_AFTER_SOURCE_CONTACT',**checked['first_collision']})
            reports[-1]['source_table_contact_exempt_until_bottom_mm']=.5
            reports[-1]['table_samples_checked_after_liftoff']=len(above)
        if clearance_phase:
            initial=robot.fk(qs[0])[:3,3]
            contact_limit=float(plan.get('intentional_release_contact',{}).get('maximum_initial_lateral_travel_mm',.5))
            outside=[q for q in qs if np.linalg.norm(robot.fk(q)[:3,3]-initial)>contact_limit]
            if not outside:raise ValueError('Release clearance never left the contact zone')
            expected=[(robot.fk(q)[:3,3]/1000).tolist() for q in outside]
            checked=sim.callScriptFunction('modeBReplay',script,(np.array(outside)*65536).tolist(),joints,tcp,expected,
                [[payload,links['link5']]],payload,sim_matrix(FLIP),False)
            if checked.get('first_collision'):collisions.append({'phase':'RELEASE_AFTER_CONTACT_ZONE',**checked['first_collision']})
            reports[-1]['initial_intended_fixed_jaw_contact_exempt_until_mm']=contact_limit
            reports[-1]['fixed_jaw_samples_checked_after_contact_zone']=len(outside)
        if stage['phase']==plan.get('release_after_stage','PLACE'):
            # Actual hand opening is checked as a separate20-frame CAD sweep.
            opening=np.array([qs[-1].copy() for _ in range(21)])
            opening[:,5]=np.linspace(0,1.5,21)
            expected=[(robot.fk(q)[:3,3]/1000).tolist() for q in opening]
            opening_pairs=[pair for pair in pairs if not(plan.get('released_on_table') and pair==[payload,table])]
            result=sim.callScriptFunction('modeBReplay',script,(opening*65536).tolist(),joints,tcp,expected,opening_pairs,payload,sim_matrix(FLIP),False)
            samples+=result['samples']
            if result.get('first_collision'):collisions.append({'phase':'RELEASE_HAND_SWEEP',**result['first_collision']})
    actual_payload=np_matrix(sim.getObjectMatrix(payload,sim.handle_world))
    placement_error=float(np.linalg.norm(actual_payload-np.array(plan.get('expected_final_payload_pose',plan['released_object_pose']))))
    home_error=max(abs(sim.getJointPosition(h)-v) for h,v in zip(joints,final_model_q))
    return {'schema':'gesture.mode_b.loaded_native_coppelia.v1','route_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'simulator_version':sim.getInt32Param(sim.intparam_program_version),'samples_checked':samples,
            'maximum_tcp_error_mm':max_error,'mesh_collisions':collisions,'released_payload_matrix_error':placement_error,
            'home_joint_error_rad':home_error,'stages':reports,'passed':bool(not collisions and max_error<.1 and placement_error<.001 and home_error<1e-6),
            'simulation_type':'EXACT_NATIVE_RADIAN_SAMPLES_RIGID_PAYLOAD_MESH_KINEMATICS',
            'intentional_contact_allowance':plan.get('intentional_release_contact',plan.get('initial_support_separation')),
            'payload_geometry':spec,
            'friction_slip_servo_dynamics_validated':False,'physical_general_mapping_calibrated':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--port',type=int,default=23020);a=p.parse_args()
    report=verify(a.plan,a.port);write(a.output,report);print(json.dumps(report))
    raise SystemExit(0 if report['passed'] else 1)
