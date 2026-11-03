"""Build/verify native reference packages and bind exact central Giao vectors."""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.native_routes import build,compile_routes,template,qrow,ROOT
from pc.mode_ab.native_family import verify,trajectory

def main(out):
 out.mkdir(parents=True,exist_ok=False);results=[]
 for name in ('red_cube','eraser','small_canister'):
  start=time.monotonic();p=template(name);b,f,n=build(name,p['request']['pickup']['centre_mm'],p['request']['pickup']['yaw_deg']);c=compile_routes(b,f)
  program=c['native_program'];labels=program['labels'];equal=[]
  for stage in p['stages']:
   qs=np.array([qrow(x['command_firmware_rad']) for x in stage['stage']['stream_frames']]);gold=np.rint(qs*65536).astype(np.int64)
   actual=trajectory(program,labels.index(stage['phase']),32)
   if not np.array_equal(actual,gold):raise ValueError('Giao central Q16 vector differs: '+name+' '+stage['phase'])
   desc=np.array(program['descriptors']).reshape(3,16,4)[1,labels.index(stage['phase'])]
   if desc[1]!=round(stage['stage']['period_s']*1e8):raise ValueError('Giao clock differs')
   command=json.loads(stage['stage']['stream_frames'][0]['wire_json'])
   if desc[2]!=(command['spd']|(command['acc']<<16)):raise ValueError('Giao profile differs')
   equal.append(stage['phase'])
  proof=verify(c,b[1],use_cache=False);c['fresh_handover_family']=proof
  folder=ROOT/'candidate/mode_ab/native_profiles'/name;folder.mkdir(parents=True,exist_ok=True)
  for file,value in [('normal.json',c),('native.json',n),('family_certificate.json',proof),*[(f'native_bank{i}.json',v) for i,v in enumerate(b)]]:
   (folder/file).write_text(json.dumps(value,allow_nan=False)+'\n')
  manifest=dict(schema='gesture.mode_ab.native_reference.v1',giao_source=p['ab_source'],
   builder_sha256=hashlib.sha256((ROOT/'pc/mode_ab/native_routes.py').read_bytes()).hexdigest(),
   files={f'native_bank{i}.json':hashlib.sha256((folder/f'native_bank{i}.json').read_bytes()).hexdigest() for i in range(3)})
  (folder/'reference_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  result=dict(class_name=name,passed=True,exact_giao_motion_phases=equal,all_six_q16_axes_identical=True,
   native_speed_and_period_identical=True,geometry=c['geometry'],family=proof,points=program['points'],speed=c['speed'],seconds=time.monotonic()-start)
  results.append(result);(out/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(name,'PASS',result['seconds'],flush=True)
 report=dict(passed=True,source_b='3d66aeb8d33b42abf8d82da3c71b1e6276a9a32a',reference_paths_source='1d3fa84de81d05b846d2b9f30998e16a84f4eee3',
  results=results,hardware_access=False,physical_test='NOT_RUN',source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
  ('pc/mode_ab/native_routes.py','pc/mode_ab/native_family.py','scripts/prepare_mode_ab_p4.py')})
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
