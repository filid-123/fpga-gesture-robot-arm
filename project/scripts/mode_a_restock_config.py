"""One-time configuration only. The PL chooses delivery vs automatic restock."""
from pathlib import Path
import json
from mode_a_upgrade_config import ROOT,ARM,PLAN,TASK,VIS,backend_writes,backend_config,protocol,vision_writes,default_map,validate_map
from mode_a_upgrade_config import task_writes as normal_task_writes
from mode_a_upgrade_profile import profile as normal_profile

def profile():
 p=normal_profile();p.update(version='0.14.0',task_abi=0x340b,display='1280x720/60, original256x192 Gray8 source',
  empty_slot_action='AUTOMATIC_PUBLIC_PICKUP_TO_ORIGINAL_SLOT',pickup_D_mm=[300,200,15],restock_cancel='PUBLIC_PICKUP_THEN_HOME')
 return p

def restock_folder(root=ROOT):
 p=Path(root)/'candidate/restock'
 return p if p.exists() else Path(root)/'board_evidence/mode_a_restock_plan_a2'

def load_restock(root=ROOT):
 t=json.loads((restock_folder(root)/'S4_RESTOCK_CANDIDATE.json').read_text('utf-8'))
 if t['task_abi']!=0x340b or t['keypoint_bank']!=3 or t['segment_bank']!=1 or t['pickup_D_mm']!=[300,200,15]:raise ValueError('Wrong restock contract')
 if len(t['keypoints'])>64 or len(t['segments'])>64 or len(t['tails'])!=3:raise ValueError('Restock table capacity')
 for d in [t['prefix'],*t['tails']]:
  if not 0<d['count']<=32 or not 0<=d['first']<64 or d['first']+d['count']>64:raise ValueError('Restock descriptor range')
 return t

def descriptor_words(t):
 return [(d['count']<<8)|d['first']|((d.get('release_kp') or 0)<<16) for d in [t['prefix'],*t['tails']]]

def task_writes(plan,table):
 t=table.get('restock') or load_restock()
 w=normal_task_writes(plan,table)
 # Banks0/1/2 are untouched. Bank3 was an unused duplicate in v0131.
 w.extend([[TASK+0x12c,3],[TASK+0x110,0]])
 words=[v&0xffffffff for q in t['keypoints'] for v in q+[0,0]]
 w.extend([TASK+0x114,v] for v in words+[0]*(512-len(words)))
 w.append([TASK+0x118,128])
 words=[v for kp,n,na,p,f in t['segments'] for v in ((f<<24)|(p<<16)|kp,(na<<16)|n)]
 w.extend([TASK+0x11c,v] for v in words+[0]*(128-len(words)))
 w.extend([TASK+0x374+4*i,v] for i,v in enumerate(descriptor_words(t)))
 return w

def restock_view(s,plan):
 if s.get('state')=='PRECHECK':
  s.update(task_kind='RESTOCK',planned_waypoint='RESTOCK_PRECHECK',planned_D_mm=None,software_status_explanation='VALIDATING_RESTOCK_TABLES_AT_HOME')
  return s
 route=next((r for r in plan['paths'] if r['object']==s['object']),None)
 if route is None:return s
 legs=route['legs'];index=max(0,min(len(legs)-1,(s['progress_raw']&63)-1));leg=legs[index]
 s.update(task_kind='RESTOCK',planned_waypoint=leg['label'],planned_D_mm=leg['target_D_mm'],
  software_status_explanation='PUBLIC_PICKUP_TO_ORIGINAL_SLOT_NO_PALM')
 if s.get('cancel_pending',False):
  depth=(s['progress_raw']>>24)&63;leg=legs[min(depth,len(legs)-1)]
  s.update(planned_waypoint='RETURN_'+leg['label']+'_START',planned_D_mm=legs[depth-1]['target_D_mm'] if 0<depth<=len(legs) else None,
   software_status_explanation='RESTOCK_CANCEL_TO_PUBLIC_PICKUP_THEN_HOME')
 return s
