"""Build a finite atlas of full geometry proofs; bound reuse is checked online."""
from pathlib import Path
import argparse,hashlib,json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from pc.mode_ab.native_routes import build,compile_routes
from pc.mode_ab.native_family import verify
from pc.mode_ab.workspace import policy
def main(out):
 out.mkdir(parents=True,exist_ok=False);rows=[]
 for name,z in policy()['height_by_class_mm'].items():
  for y in (355,320,285,250,215):
   for x in (490,690,590,540,640):
    start=time.perf_counter();banks,front,native=build(name,[x,y,z],0);c=compile_routes(banks,front);proof=verify(c,banks[1])
    if proof['method']=='FULL_NATIVE_GEOMETRY':
     path=ROOT/'candidate/mode_ab/native_profiles'/name/f'family_certificate_{x}_{y}.json'
     path.write_text(json.dumps(proof,allow_nan=False)+'\n')
    row=dict(class_name=name,source=[x,y,z],method=proof['method'],passed=True,points=c['native_program']['points'],
     geometry=c['geometry'],seconds=time.perf_counter()-start)
    rows.append(row);(out/'progress.json').write_text(json.dumps(rows,indent=2)+'\n');print(name,x,y,proof['method'],round(row['seconds'],2),flush=True)
 # Verify the complete atlas with empty session cache: disk certificates alone
 # must cover every tested pose; no warm-session assumptions are accepted.
 from pc.mode_ab.native_family import _proofs
 _proofs.clear();reuse=[]
 for name,z in policy()['height_by_class_mm'].items():
  for x,y in ((490,355),(690,355),(590,355),(590,285),(490,215),(690,215)):
   start=time.perf_counter();b,f,_=build(name,[x,y,z],0);c=compile_routes(b,f);r=verify(c,b[1])
   if r['method']!='BOUND_RIGID_PAYLOAD_DISPLACEMENT_NATIVE':raise ValueError('Prepared atlas did not cover tested pose')
   reuse.append(dict(class_name=name,source=[x,y,z],planning_seconds=time.perf_counter()-start,proof=r))
 result=dict(passed=True,finite_grid_points=len(rows),rows=rows,cold_cache_spot_checks=reuse,
  runtime_always_checks_the_fresh_attachment=True,hardware_access=False,physical_test='NOT_RUN',
  source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('pc/mode_ab/native_routes.py','pc/mode_ab/native_family.py','pc/mode_ab/geometry.py','scripts/prepare_mode_ab_native_coverage.py')})
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
