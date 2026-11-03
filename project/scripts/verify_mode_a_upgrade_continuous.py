"""Calculate all65 bounded positions from the three frozen anchors, then replay.

No physical acquisition. One temporary candidate per step is retained locally;
the release contains anchors, generation script and aggregate geometry evidence.
"""
from pathlib import Path
import argparse,copy,hashlib,json,math
import numpy as np
from prepare_mode_a_upgrade import LocalModel,scene_export
from mode_a_upgrade_profile import blend_word,p2p,profile
from verify_mode_a_follow import run
ROOT=Path(__file__).resolve().parents[1]
def main(planroot,out,simulate):
 out.mkdir(parents=True,exist_ok=False)
 anchors=[json.loads((planroot/f'bank{i}/PLAN_NATIVE.json').read_text()) for i in range(3)]
 model=LocalModel(350);records=[];maxerr=np.zeros(3);max_z=0;total=0
 for step in range(65):
  low=0 if step<32 else 1;w=step-low*32;a,b=anchors[low:low+2];p=copy.deepcopy(a)
  for key in ('PRE','H','H_CLEAR'):
   p['layout']['common_D_mm'][key]=[(x*(32-w)+y*w)/32 for x,y in zip(a['layout']['common_D_mm'][key],b['layout']['common_D_mm'][key])]
  p['layout']['layout_id']=p['layout_id']=f'mode_a_continuous_step_{step:02d}'
  for kind in ('paths','hover_paths','return_paths'):
   for route,ra,rb in zip(p[kind],a[kind],b[kind]):
    route['samples']=[]
    for i,(leg,la,lb) in enumerate(zip(route['legs'],ra['legs'],rb['legs'])):
     for field in ('start_q16','target_q16'):leg[field]=[blend_word(x,y,w) for x,y in zip(la[field],lb[field])]
     if la.get('target_D_mm') is not None:
      leg['target_D_mm']=[(x*(32-w)+y*w)/32 for x,y in zip(la['target_D_mm'],lb['target_D_mm'])]
      actual=np.array(model.desk([v/65536 for v in leg['target_q16']]));err=np.abs(actual-leg['target_D_mm']);maxerr=np.maximum(maxerr,err)
     cfg=p2p.MoveParams(tuple(leg['start_q16']),tuple(leg['target_q16']),leg['n'],leg['na'],1,2000000,50000000,(math.ceil(math.radians(74.25)*.02*65536)+2,)*6,(math.ceil(math.radians(326.7)*.02**2*(1<<32))+2,)*6)
     assert p2p.validate(cfg,last_delivered=cfg.start).ok
     ss=p2p.samples(cfg)
     for q in ss:model.check([v/65536 for v in q])
     route['samples'].extend(dict(segment=i,tick=k+1,q16=list(q)) for k,q in enumerate(ss))
  folder=out/f'step{step:02d}';folder.mkdir()
  (folder/'PLAN_NATIVE.json').write_text(json.dumps(p,separators=(',',':'))+'\n')
  (folder/'SCENE_PLAN.json').write_text(json.dumps(scene_export(p,model),separators=(',',':'))+'\n')
  rec=dict(step=step,nominal_H=p['layout']['common_D_mm']['H'],native_plan_sha256=hashlib.sha256((folder/'PLAN_NATIVE.json').read_bytes()).hexdigest(),samples=sum(len(r['samples']) for k in ('paths','hover_paths','return_paths') for r in p[k]))
  if simulate:
   for wire in (False,True):
    resultdir=folder/('wire' if wire else 'exact');assert run(folder,resultdir,wire)
    rec['wire' if wire else 'exact']=json.loads((resultdir/'RESULT.json').read_text())
  records.append(rec);total+=rec['samples'];print('CONTINUOUS_STEP_PASS',step,flush=True)
  (out/'PROGRESS.json').write_text(json.dumps(dict(completed=step+1,total=65)))
 result=dict(passed=True,positions=65,geometry='Joint interpolation of physically tested anchors; calculated candidates, no new physical calibration',max_target_abs_xyz_deviation_from_nominal_mm=maxerr.tolist(),native_samples=total,coppelia_samples=total*2 if simulate else 0,collision_samples=0 if simulate else None,physical_robot=False,source_anchor_hashes={f'bank{i}':hashlib.sha256((planroot/f'bank{i}/PLAN_NATIVE.json').read_bytes()).hexdigest() for i in range(3)},steps=records)
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
 print('ALL_65_CONTINUOUS_POSITIONS_PASS',maxerr.tolist(),total,flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--coppelia',action='store_true');a=ap.parse_args();main(a.plan,a.out,a.coppelia)
