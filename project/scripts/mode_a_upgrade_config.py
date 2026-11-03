"""Fixed image-Y thresholds and four precomputed PL trajectory banks."""
import math
from mode_a_upgrade_backend import ROOT,ARM,PLAN,TASK,VIS,backend_config,backend_writes,protocol,vision_writes as parent_vision_writes
from mode_a_upgrade_backend import task_writes as original_writes
from mode_a_upgrade_profile import profile

def default_map():
 return dict(schema='gesture.mode_a.continuous_y.v1',revision=3,calibrated=False,method='BOUNDED_ANCHOR_JOINT_INTERPOLATION',image_axis='Y',desk_axis='Y',image_up_is_desk_plus_y=True,thresholds=[44,64,84],steps=64,deadband_steps=2,physical_H_D_mm=[[285,y,175] for y in (135,195,255)],cells=[dict(bank=1,x0=0,x1=127,y0=16,y1=111)])

def vision_writes():
 return [[a,({VIS+0xc:v&~2,VIS+0x14:128<<16,VIS+0x18:128}).get(a,v)] for a,v in parent_vision_writes()]


def validate_map(m,require_calibrated=False):
 if m!=default_map():raise ValueError('Use the immutable four-region map; no physical sampling required')
 return m

def task_writes(plan,t):
 w=[r for r in original_writes(plan,t) if r[0] not in (TASK+0x110,TASK+0x114)]
 if len(t['keypoint_banks'])!=4 or len(t['align_pairs'])!=16:raise ValueError('Four banks / sixteen pair timings required')
 for i,bank in enumerate(t['keypoint_banks']):
  words=[v&0xffffffff for q in bank for v in q+[0,0]]
  if len(words)>512:raise ValueError('Bank capacity')
  w.extend([[TASK+0x12c,i],[TASK+0x110,0]])
  w.extend([TASK+0x114,v] for v in words+[0]*(512-len(words)))
 for i in range(5):w.append([TASK+0xc8+4*i,math.ceil(math.radians(320)*.02**2*(1<<32))+2])
 w.append([TASK+0x130,(t['align_na']<<16)|t['align_n']])
 for i,p in enumerate(t['align_pairs']):
  if (p['from_bank'],p['to_bank'])!=divmod(i,4):raise ValueError('Pair order')
  w.append([TASK+0x330+4*i,(p['na']<<16)|p['n']])
 d=lambda k:(t['descriptors'][k][1]<<6)|t['descriptors'][k][0]
 for c in default_map()['cells']:
  values=[c['x0']|(c['x1']<<9),c['y0']|(c['y1']<<9),t['predelivery_kp']|(d('release')<<6)|(d('deliver')<<18),d('retreat')]
  w.append([TASK+0x300,c['bank']*4]);w.extend([TASK+0x304,v] for v in values)
 w.extend([[TASK+0x308,2],[TASK+0x30c,3],[TASK+0x310,1]])
 return w

def preview_band(center):
 x,y=center
 if not 0<=x<=127 or not 16<=y<=111:return None
 return 1 if y<54 else (2 if y<74 else 3)
