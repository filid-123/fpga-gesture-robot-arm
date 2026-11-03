"""Stopped Coppelia meshes: public-pickup restock, four-decimal wire replay."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from coppeliasim_zmqremoteapi_client import RemoteAPIClient
from plan_mode_a_nominal import Model,NAMES,ROOT
from verify_mode_a_follow import LUA
from run_mode_a_walkthrough import packet

def run(candidate,out,wire=False):
 native_path=candidate/'PLAN_NATIVE.json';p=json.loads(native_path.read_text('utf-8'))
 scene=json.loads((candidate/'SCENE_PLAN.json').read_text('utf-8'));out.mkdir(parents=True,exist_ok=False)
 sim=RemoteAPIClient(port=23001).require('sim');assert sim.getSimulationState()==sim.simulation_stopped
 aliases={sim.getObjectAlias(h):h for h in sim.getObjectsInTree(sim.handle_scene,sim.handle_all,0)}
 joints=[aliases[n] for n in NAMES];original=[sim.getJointPosition(h) for h in joints]
 model=Model(ROOT/'planning/roarm_m3_nominal.xacro');created=[];collection=None
 result=dict(schema='gesture.mode_a.restock_coppelia.v1',native_plan_sha256=hashlib.sha256(native_path.read_bytes()).hexdigest(),
  physical_robot=False,dynamics=False,wire_4decimal=wire,pickup_D_mm=p['pickup_D_mm'],runs=[],passed=False)
 try:
  script=sim.createScript(sim.scripttype_customization,LUA,0,'lua');created.append(script);sim.initScript(script)
  collection=sim.createCollection(0)
  meshes=[h for h in sim.getObjectsInTree(sim.handle_scene,sim.object_shape_type,0) if sim.getObjectAlias(h).startswith(('link1_','link2_','link3_','link4_','link5_','gripper_'))]
  assert len(meshes)>=8
  for h in meshes:sim.addItemToCollection(collection,sim.handle_single,h,0)
  def box(name,size,point):
   h=sim.createPrimitiveShape(sim.primitiveshape_cuboid,size,0);created.append(h);sim.setObjectAlias(h,name)
   sim.setObjectPosition(h,sim.handle_world,model.world(point).tolist());return h
  table=box('restock_table',[.6,.8,.02],[400,300,-10]);lens=p['layout']['camera']['lens_D_mm']
  camera=box('restock_camera',[.035,.035,.025],[lens[0],lens[1],lens[2]+12.5])
  # Restocking is automatic table placement, with no fixed human palm in the path.
  palm=box('restock_unused_palm',[.01]*3,[1500,1500,1000])
  blocks=[box('restock_block_'+str(i+1),[.03]*3,point) for i,point in enumerate(p['layout']['slots_D_mm'])]
  original_blocks=[sim.getObjectPose(h,sim.handle_world) for h in blocks];max_fk=0.
  for route in p['paths']:
   target=route['object']-1
   for h,pose in zip(blocks,original_blocks):sim.setObjectPose(h,sim.handle_world,pose)
   sim.setObjectPosition(blocks[target],sim.handle_world,model.world(p['pickup_D_mm']).tolist())
   initial=sim.getObjectPose(blocks[target],sim.handle_world)
   decoded=[]
   for i,row in enumerate(route['samples']):
    nq=[v/65536 for v in row['q16']];leg=route['legs'][row['segment']]
    if wire:
     c=json.loads(packet(nq));nq=[c[k] for k in ('base','shoulder','elbow','wrist','roll','hand')]
    q=[v-b for v,b in zip(nq[:5],p['residual_rad'])]+[float(np.clip((p['hold_native_rad']-nq[5])/(p['hold_native_rad']-p['open_native_rad'])*1.5,0,1.5))]
    attached=int(leg['phase'] in ('lift','release') or (leg['phase']=='grasp' and q[5]<.1))
    endpoint=int(i+1==len(route['samples']) or route['samples'][i+1]['segment']!=row['segment'])
    decoded.append(q+[attached,endpoint])
   obstacles=[h for i,h in enumerate(blocks) if i!=target]
   check=sim.callScriptFunction('replay',script,joints,aliases['hand_tcp'],collection,decoded,obstacles,table,camera,palm,blocks[target],initial)
   for obs in check['observations']:max_fk=max(max_fk,float(np.linalg.norm(model.fk(obs['joints'][:6])[0][:3,3]-np.array(obs['position'])))*1000)
   result['runs'].append(dict(object=route['object'],kind='restock',**check))
   # Geometry of cancellations from every pre-release segment midpoint. Actual
   # pause/drain/retrace command timing is separately exercised by S4/S2 replay.
   release=next((i for i,l in enumerate(route['legs']) if l['phase']=='release'),len(route['legs']))
   for leg_index in ([] if p.get('actual_s4_replay') else range(release)):
    prefix=[r for r,row in zip(decoded,route['samples']) if row['segment']<leg_index]
    part=[r for r,row in zip(decoded,route['samples']) if row['segment']==leg_index]
    prefix+=part[:max(1,len(part)//2)];back=list(reversed(prefix))
    check=sim.callScriptFunction('replay',script,joints,aliases['hand_tcp'],collection,prefix+back,obstacles,table,camera,palm,blocks[target],initial)
    result['runs'].append(dict(object=route['object'],kind='midpoint_cancel_geometry',segment=leg_index,**check))
  result.update(actual_arm_meshes=len(meshes),max_local_vs_coppelia_fk_mm=max_fk,
   samples_checked=sum(x['count'] for x in result['runs']),collision_samples=sum(len(x['collisions']) for x in result['runs']))
  result['passed']=result['collision_samples']==0 and max_fk<.01
 finally:
  for h,q in zip(joints,original):sim.setJointPosition(h,q)
  if collection is not None:sim.destroyCollection(collection)
  if created:sim.removeObjects(created)
  result['own_objects_removed']=True;result['restore_max_joint_error_rad']=max(abs(sim.getJointPosition(h)-q) for h,q in zip(joints,original))
  (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
 print(json.dumps({k:v for k,v in result.items() if k!='runs'},indent=2));return result['passed']
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--wire',action='store_true');a=ap.parse_args()
 raise SystemExit(0 if run(a.candidate,a.out,a.wire) else 1)
