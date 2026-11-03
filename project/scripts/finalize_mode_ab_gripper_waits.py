"""Rebuild grip waits and prove every geometric vector/profile remains identical."""
from copy import deepcopy
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.native_routes import build,compile_routes,template
from pc.mode_ab.native_family import fingerprint
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main(out):
 out.mkdir(parents=True,exist_ok=False);results=[]
 previous_hash=json.loads((ROOT/'board_evidence/mode_ab_p4/profiles_release/result.json').read_bytes())['source_hashes']['pc/mode_ab/native_routes.py']
 for name in ('red_cube','eraser','small_canister'):
  folder=ROOT/'candidate/mode_ab/native_profiles'/name;file=folder/'normal.json'
  old=json.loads(file.read_bytes());(out/(name+'_before.json')).write_bytes(file.read_bytes())
  manifest=json.loads((folder/'reference_manifest.json').read_bytes())
  for n,d in manifest['files'].items():
   if sha(folder/n)!=d:raise ValueError('Reference bank changed')
  manifest['builder_sha256']=sha(ROOT/'pc/mode_ab/native_routes.py')
  (folder/'reference_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  p=template(name);banks,front,_=build(name,p['request']['pickup']['centre_mm'],p['request']['pickup']['yaw_deg']);new=compile_routes(banks,front)
  a=old['native_program'];b=new['native_program']
  for key in ('bases','offsets','labels','points','stage_count','schema','abi'):
   if a[key]!=b[key]:raise ValueError('Geometry/program data changed: '+key)
  da=np.array(a['descriptors']).reshape(3,16,4);db=np.array(b['descriptors']).reshape(3,16,4)
  for i in range(16):
   if i in (1,3,9,15):
    if not np.array_equal(da[:,i,[0,2,3]],db[:,i,[0,2,3]]) or np.any(db[:,i,1]<da[:,i,1]):raise ValueError('Unexpected gripper delta')
   elif not np.array_equal(da[:,i],db[:,i]):raise ValueError('Giao motion stage changed')
  if fingerprint(old,banks[1])!=fingerprint(new,banks[1]):raise ValueError('Geometry family proof changed')
  old_copy=deepcopy(old);new_copy=deepcopy(new)
  for c in (old_copy,new_copy):
   c.pop('fresh_handover_family',None);c.pop('speed');c.pop('native_program')
   for row in c['fifo']:row.pop('n')
   for row in c['segments']:row[1]=0
  if old_copy!=new_copy:raise ValueError('Non-timing compiled behavior changed')
  new['fresh_handover_family']=old['fresh_handover_family'];file.write_text(json.dumps(new,allow_nan=False)+'\n')
  results.append(dict(class_name=name,passed=True,old_sha256=sha(out/(name+'_before.json')),new_sha256=sha(file),
   all_motion_vectors_periods_and_profiles_unchanged=True,geometry_fingerprint_unchanged=True,
   gripper_waits_seconds={b['labels'][i]:db[1,i,1]/1e8 for i in (1,3,9,15)},speed=new['speed']))
 report=dict(passed=True,scope='ONLY_T106_WAIT_PERIOD_AND_MATCHING_S4_DURATION_CHANGED',
  prior_native_routes_sha256=previous_hash,results=results,hardware_access=False,physical_test='NOT_RUN',
  source_hashes={n:sha(ROOT/n) for n in ('pc/mode_ab/native_routes.py','scripts/finalize_mode_ab_gripper_waits.py','docs/phase3c/mode_b_optimized_handoff_20261030/execution.json')})
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS: all three geometric programs unchanged; Giao grip waits restored')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
