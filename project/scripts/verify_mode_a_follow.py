"""Actual stopped-Coppelia replay of all colors with the new camera/palm proxy.

Kinematic attachment rotates the cube with the tool. No contact dynamics or
real hardware access. Restores original joints and removes all owned objects.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from coppeliasim_zmqremoteapi_client import RemoteAPIClient
from plan_mode_a_nominal import ROOT,Model,NAMES
from run_mode_a_walkthrough import packet

LUA=r'''
local sim=require('sim')
function replay(joints,tcp,arm,samples,obstacles,tableShape,camera,palm,payload,initialPose)
    if sim.getSimulationState()~=sim.simulation_stopped then error('Scene must be stopped') end
    sim.setObjectPose(payload,sim.handle_world,initialPose)
    local rel=nil
    local result={count=0,collisions={},observations={},minimum_payload_table_gap_m=1e9}
    for index,row in ipairs(samples) do
        for i=1,6 do sim.setJointPosition(joints[i],row[i]) end
        if row[7]==1 then
            if rel==nil then rel=sim.getObjectPose(payload,tcp) end
            sim.setObjectPose(payload,sim.handle_world,sim.multiplyPoses(sim.getObjectPose(tcp,sim.handle_world),rel))
        end
        result.count=result.count+1
        if row[8]==1 or index==1 or index==#samples then
            table.insert(result.observations,{index=index,position=sim.getObjectPosition(tcp,sim.handle_world),joints=row})
        end
        for j,h in ipairs(obstacles) do
            if sim.checkCollision(arm,h)>0 then table.insert(result.collisions,{index=index,obstacle='block_'..j}) end
            if row[7]==1 and sim.checkCollision(payload,h)>0 then table.insert(result.collisions,{index=index,obstacle='payload_block_'..j}) end
        end
        for _,item in ipairs({{tableShape,'table'},{camera,'camera'},{palm,'palm_proxy'}}) do
            if sim.checkCollision(arm,item[1])>0 then table.insert(result.collisions,{index=index,obstacle=item[2]}) end
        end
        if row[7]==1 then
            local mat=sim.getObjectMatrix(payload,sim.handle_world)
            local bottom=mat[12]-0.015*(math.abs(mat[9])+math.abs(mat[10])+math.abs(mat[11]))
            local top=sim.getObjectPosition(tableShape,sim.handle_world)[3]+0.01
            result.minimum_payload_table_gap_m=math.min(result.minimum_payload_table_gap_m,bottom-top)
            if bottom<top-0.0001 then table.insert(result.collisions,{index=index,obstacle='payload_below_table'}) end
            if sim.checkCollision(payload,camera)>0 then table.insert(result.collisions,{index=index,obstacle='payload_camera'}) end
            if sim.checkCollision(payload,palm)>0 then table.insert(result.collisions,{index=index,obstacle='payload_palm_proxy'}) end
        end
    end
    return result
end
'''


def run(candidate,out,wire=False):
    native_path=candidate/'PLAN_NATIVE.json';scene_path=candidate/'SCENE_PLAN.json'
    native=json.loads(native_path.read_text('utf-8'));scene=json.loads(scene_path.read_text('utf-8'))
    if native['physical_validated'] or scene['physical_execution_allowed'] is not False:raise ValueError('Candidate provenance')
    routes=scene['paths']+scene['hover_paths']+scene['return_paths'];layout=scene['layout']
    native_routes=native['paths']+native['hover_paths']+native['return_paths']
    if len(routes)!=len(native_routes):raise ValueError('Missing scene routes')
    for nr,sr in zip(native_routes,routes):
        if len(nr['samples'])!=len(sr['samples']):raise ValueError('Missing scene samples')
        for n,s in zip(nr['samples'],sr['samples']):
            if any(abs(s['q16'][i]/65536-(n['q16'][i]/65536-b))>1/65536 for i,b in enumerate(native['residual_rad'])):raise ValueError('Scene mapping')
    client=RemoteAPIClient(port=23001);sim=client.require('sim')
    if sim.getSimulationState()!=sim.simulation_stopped:raise ValueError('Coppelia must be stopped')
    out.mkdir(parents=True,exist_ok=False)
    aliases={sim.getObjectAlias(h):h for h in sim.getObjectsInTree(sim.handle_scene,sim.handle_all,0)}
    joints=[aliases[n] for n in NAMES];original=[sim.getJointPosition(h) for h in joints]
    model=Model(ROOT/'planning/roarm_m3_nominal.xacro');created=[];collection=None
    record=dict(schema='gesture.mode_a.delivery_layout_coppelia.v1',evidence_kind='ACTUAL_COPPELIASIM_STOPPED_KINEMATIC',
        native_plan_sha256=hashlib.sha256(native_path.read_bytes()).hexdigest(),scene_plan_sha256=hashlib.sha256(scene_path.read_bytes()).hexdigest(),
        layout_id=layout['layout_id'],camera_lens_D_mm=layout['camera']['lens_D_mm'],simulator_version=sim.getInt32Param(sim.intparam_program_version),
        physical_robot=False,dynamics=False,payload_rotates_with_tool=True,palm_proxy_size_mm=[80,80,20],palm_proxy_top_D_z_mm=layout['palm_surface_candidate_z_mm'],
        sample_source='T102_PACKET_ROUNDED_TO_4_DECIMALS' if wire else 'EXACT_S2_Q16',runs=[])
    try:
        script=sim.createScript(sim.scripttype_customization,LUA,0,'lua');created.append(script)
        sim.setObjectAlias(script,'mode_a_delivery_v060_owned');sim.initScript(script)
        collection=sim.createCollection(0)
        meshes=[h for h in sim.getObjectsInTree(sim.handle_scene,sim.object_shape_type,0) if sim.getObjectAlias(h).startswith(('link1_','link2_','link3_','link4_','link5_','gripper_'))]
        if len(meshes)<8:raise ValueError('Incomplete arm meshes')
        for h in meshes:sim.addItemToCollection(collection,sim.handle_single,h,0)
        def box(name,size,p):
            h=sim.createPrimitiveShape(sim.primitiveshape_cuboid,size,0);created.append(h);sim.setObjectAlias(h,name)
            sim.setObjectPosition(h,sim.handle_world,model.world(p).tolist());return h
        table=box('mode_a_v060_table',[.6,.8,.02],[400,300,-10])
        lens=layout['camera']['lens_D_mm'];camera=box('mode_a_v060_camera',[.035,.035,.025],[lens[0],lens[1],lens[2]+12.5])
        hpoint=layout['common_D_mm']['H'];palm=box('mode_a_v060_palm_proxy',[.08,.08,.02],[hpoint[0],hpoint[1],layout['palm_surface_candidate_z_mm']-10])
        blocks=[box('mode_a_v060_block_'+str(i+1),[.03]*3,p) for i,p in enumerate(layout['slots_D_mm'])]
        initial=[sim.getObjectPose(b,sim.handle_world) for b in blocks];max_fk=0.
        for route,native_route in zip(routes,native_routes):
            for b,pose in zip(blocks,initial):sim.setObjectPose(b,sim.handle_world,pose)
            decoded=[]
            for i,row in enumerate(route['samples']):
                q=[v/65536 for v in row['q16']];leg=route['legs'][row['segment']]
                if wire:
                    command=json.loads(packet([v/65536 for v in native_route['samples'][i]['q16']]))
                    command.update(spd=native['execution_profile']['speed_steps_s'],acc=native['execution_profile']['acceleration_100_steps_s2'])
                    nq=[command[k] for k in ('base','shoulder','elbow','wrist','roll','hand')]
                    q=[v-b for v,b in zip(nq[:5],native['residual_rad'])]+[float(np.clip((native['hold_native_rad']-nq[5])/(native['hold_native_rad']-native['open_native_rad'])*1.5,0,1.5))]
                attached=int(leg['phase'] in ('lift','deliver','release') or (leg['phase']=='grasp' and q[5]<.1))
                endpoint=int(i+1==len(route['samples']) or route['samples'][i+1]['segment']!=row['segment'])
                decoded.append(q+[attached,endpoint])
            if 'palm_D_mm' in native_route:
                pp=native_route['palm_D_mm'];sim.setObjectPosition(palm,sim.handle_world,model.world([pp[0],pp[1],pp[2]-10]).tolist())
            target=route['object']-1;obstacles=[b for i,b in enumerate(blocks) if route['kind']=='startup' or i!=target]
            result=sim.callScriptFunction('replay',script,joints,aliases['hand_tcp'],collection,decoded,obstacles,table,camera,palm,blocks[target],initial[target])
            for obs in result['observations']:
                max_fk=max(max_fk,float(np.linalg.norm(model.fk(obs['joints'][:6])[0][:3,3]-np.array(obs['position'])))*1000)
            record['runs'].append(dict(object=route['object'],kind=route['kind'],**result))
        record.update(actual_arm_meshes=len(meshes),samples_checked=sum(r['count'] for r in record['runs']),collision_samples=sum(len(r['collisions']) for r in record['runs']),max_local_vs_Coppelia_FK_mm=max_fk)
        record['passed']=record['collision_samples']==0 and max_fk<.01
    except BaseException as exc:
        record.update(passed=False,error=str(exc));raise
    finally:
        for h,q in zip(joints,original):sim.setJointPosition(h,q)
        record['restore_max_joint_error_rad']=max(abs(sim.getJointPosition(h)-q) for h,q in zip(joints,original))
        if collection is not None:sim.destroyCollection(collection)
        if created:sim.removeObjects(created)
        record['temporary_objects_removed']=True
        (out/'RESULT.json').write_text(json.dumps(record,indent=2)+'\n','utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='runs'},indent=2));return record['passed']


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--wire-commands',action='store_true');a=ap.parse_args()
    raise SystemExit(0 if run(a.candidate,a.out,a.wire_commands) else 1)
