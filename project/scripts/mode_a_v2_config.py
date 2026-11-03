"""One-time PL configuration for three calibrated image cells and trajectory banks."""
import json
from pathlib import Path
from mode_a_cancel_shift_config import ROOT,ARM,PLAN,TASK,VIS,backend_writes,backend_config,protocol,vision_writes,task_writes as legacy_task_writes
from mode_a_v2_profile import profile

def default_map():
 return dict(schema='gesture.mode_a.handmap.v1',revision=1,calibrated=False,cells=[dict(bank=i,x0=a,x1=b,y0=16,y1=111) for i,(a,b) in enumerate(((0,41),(42,83),(84,127)))])

def validate_map(m,require_calibrated=False):
 if m.get('schema')!='gesture.mode_a.handmap.v1' or type(m.get('revision')) is not int or not 0<m['revision']<=0xffffffff:raise ValueError('Hand map schema/revision')
 if require_calibrated and m.get('calibrated') is not True:raise ValueError('Use a three-position calibration map for motion')
 cells=m.get('cells',[])
 if len(cells)!=3 or {c['bank'] for c in cells}!={0,1,2}:raise ValueError('Exactly three banks required')
 for c in cells:
  if any(type(c[k]) is not int for k in ('bank','x0','x1','y0','y1')):raise ValueError('Integer pixel bounds required')
  if not (0<=c['x0']<=c['x1']<=127 and 16<=c['y0']<=c['y1']<=111):raise ValueError('Cell outside locator content')
 for i,a in enumerate(cells):
  for b in cells[i+1:]:
   if a['x0']<=b['x1'] and b['x0']<=a['x1'] and a['y0']<=b['y1'] and b['y0']<=a['y1']:raise ValueError('Overlapping cells')
 return m

def map_writes(t,m):
 validate_map(m);d=lambda k:(t['descriptors'][k][1]<<6)|t['descriptors'][k][0]
 w=[]
 for c in sorted(m['cells'],key=lambda x:x['bank']):
  values=[c['x0']|(c['x1']<<9),c['y0']|(c['y1']<<9),t['predelivery_kp']|(d('release')<<6)|(d('deliver')<<18),d('retreat')]
  w.append([TASK+0x300,c['bank']*4]);w.extend([TASK+0x304,v] for v in values)
 w.extend([[TASK+0x308,7],[TASK+0x30c,m['revision']],[TASK+0x310,1]])
 return w

def task_writes(plan,t):
 # The original register image is reused except for the new padded/banked KP RAM.
 w=[r for r in legacy_task_writes(plan,t) if r[0] not in (TASK+0x110,TASK+0x114)]
 for i,bank in enumerate(t['keypoint_banks']):
  words=[v&0xffffffff for q in bank for v in q+[0,0]]
  if len(words)>512:raise ValueError('Bank capacity')
  w.extend([[TASK+0x12c,i],[TASK+0x110,0]])
  w.extend([TASK+0x114,v] for v in words+[0]*(512-len(words)))
 w.extend([[TASK+0x130,(t['align_na']<<16)|t['align_n']]])
 return w+map_writes(t,t.get('hand_map',default_map()))
