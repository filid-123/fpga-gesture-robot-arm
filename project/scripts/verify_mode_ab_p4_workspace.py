"""Exercise all 75 full-window poses on new native Q16 programs, no devices."""
from pathlib import Path
import argparse,hashlib,json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.native_routes import build,compile_routes
from pc.mode_ab.native_family import verify
from pc.mode_ab.workspace import policy
def main(out):
 out.mkdir(parents=True,exist_ok=False);rows=[]
 for name,z in policy()['height_by_class_mm'].items():
  for y in (215,250,285,320,355):
   for x in (490,540,590,640,690):
    start=time.monotonic();r=dict(class_name=name,centre_mm=[x,y,z])
    try:
     banks,front,native=build(name,[x,y,z],0);c=compile_routes(banks,front)
     r.update(passed=True,geometry=c['geometry'],points=c['native_program']['points'],speed=c['speed'])
     if x==490 and y==355:r['family']=verify(c,banks[1],use_cache=False)
    except ValueError as exc:r.update(passed=False,error=str(exc))
    r['seconds']=time.monotonic()-start;rows.append(r)
    (out/'progress.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n');print(name,x,y,r['passed'],r.get('error',''),flush=True)
 result=dict(passed=all(r['passed'] for r in rows),points=len(rows),rows=rows,
  finite_grid_only=True,full_family_at_three_far_corners=True,hardware_access=False,physical_test='NOT_RUN',
  source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('pc/mode_ab/native_routes.py','pc/mode_ab/native_family.py','pc/mode_ab/motion.py','pc/mode_ab/geometry.py','scripts/verify_mode_ab_p4_workspace.py')})
 (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');raise SystemExit(0 if result['passed'] else 1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
