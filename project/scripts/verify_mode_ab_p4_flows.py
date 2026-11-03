"""Offline full delivery + public return, including actual field source data."""
from pathlib import Path
import argparse,hashlib,json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.runtime import plan_delivery,plan_restock
from pc.mode_ab.motion import template
def main(out):
 out.mkdir(parents=True,exist_ok=False);cases=[]
 for name in ('red_cube','eraser','small_canister'):
  p=template(name);cases.append((name+'_nominal',name,p['request']['pickup']['centre_mm'],0))
  cases.append((name+'_far',name,[490,355,p['request']['pickup']['centre_mm'][2]],0))
 cases.append(('red_field_115055','red_cube',[607.9524642350443,271.08727337439336,15],0))
 results=[]
 for label,name,centre,yaw in cases:
  folder=out/label;folder.mkdir();start=time.monotonic();r=dict(label=label,class_name=name,source=centre)
  try:
   d=plan_delivery(folder/'delivery',name,centre,yaw,dict(evidence='OFFLINE_SAVED_SOURCE_NO_CAMERA'))
   file=folder/'origin.json';native=folder/'delivery/native.json'
   record=dict(task_id='OFFLINE_SYNTHETIC_ORIGIN',origin_kind=d['origin_kind'],source_centre_mm=centre,source_yaw_deg=yaw,
    native_file=str(native.resolve()),native_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),origin_file=str(file.resolve()),
    evidence_kind='SYNTHETIC_ONLY_NO_PHYSICAL_TASK_COMPLETION')
   file.write_text(json.dumps(record));s=plan_restock(folder/'restock',record)
   r.update(passed=True,delivery=d['compiled']['geometry'],restock=s['compiled']['geometry'],
    family=d['compiled'].get('fresh_handover_family'),restock_fifo=len(s['compiled']['fifo']),timings=d['compiled']['planning_timings_ms'])
  except Exception as e:r.update(passed=False,error=repr(e))
  r['seconds']=time.monotonic()-start;results.append(r);(out/'progress.json').write_text(json.dumps(results,indent=2)+'\n');print(label,r['passed'],r.get('error',''),flush=True)
 result=dict(passed=all(r['passed'] for r in results),scenarios=results,hardware_access=False,physical_test='NOT_RUN',
  source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('pc/mode_ab/native_routes.py','pc/mode_ab/native_family.py','pc/mode_ab/motion.py','pc/mode_ab/runtime.py','scripts/verify_mode_ab_p4_flows.py')})
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(0 if result['passed'] else 1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
