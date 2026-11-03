"""PC contract tests for the one-time loader and telemetry, no hardware."""
from pathlib import Path
import contextlib,copy,io,json,unittest
from unittest.mock import patch
from mode_a_restock_config import ROOT,TASK,ARM,PLAN,VIS,load_restock,task_writes,descriptor_words,profile,restock_view
from mode_a_upgrade_config import task_writes as original
from test_mode_a_upgrade import FakeBoard
import run_mode_a_restock as runtime
from prepare_mode_a_restock_bridge import generate
P=ROOT/'candidate/bank1'
if not P.exists():P=ROOT/'board_evidence/mode_a_upgrade_plan_a3/bank1'

class RestockTests(unittest.TestCase):
 @classmethod
 def setUpClass(c):
  c.plan=json.loads((P/'PLAN_NATIVE.json').read_text('utf-8'));c.table=json.loads((P.parent/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
  c.rs=load_restock();c.merged=copy.deepcopy(c.table);c.merged['restock']=c.rs;c.merged['abi']['task']=0x340b
  root=(ROOT/'candidate/restock') if (ROOT/'candidate/restock').exists() else ROOT/'board_evidence/mode_a_restock_plan_a2'
  c.restore=json.loads((root/'PLAN_NATIVE.json').read_text('utf-8'))
 def test_keypoint_banks_012_unchanged_and_bank3_restock(self):
  banks=[[0]*512 for _ in range(4)];bank=address=0
  for a,v in task_writes(self.plan,self.merged):
   if a==TASK+0x12c:bank=v
   if a==TASK+0x110:address=v
   if a==TASK+0x114:banks[bank][address]=v;address=(address+1)%512
  for i in range(4):
   expected=self.table['keypoint_banks'][i] if i<3 else self.rs['keypoints'];words=[v&0xffffffff for q in expected for v in q+[0,0]]
   self.assertEqual(banks[i],words+[0]*(512-len(words)))
 def test_segment_banks_do_not_alias(self):
  mem=[None]*256;address=0
  for a,v in task_writes(self.plan,self.merged):
   if a==TASK+0x118:address=v
   if a==TASK+0x11c:mem[address]=v;address=(address+1)%256
  for offset,rows in ((0,self.table['segments']),(128,self.rs['segments'])):
   expected=[v for kp,n,na,p,f in rows for v in ((f<<24)|(p<<16)|kp,(na<<16)|n)]
   self.assertEqual(mem[offset:offset+len(expected)],expected)
  self.assertEqual(mem[128+len(self.rs['segments'])*2:],[0]*(128-len(self.rs['segments'])*2))
 def test_release_points_are_frozen_original_slots(self):
  for route,d in zip(self.plan['paths'],self.rs['tails']):
   grasp=next(l for l in route['legs'] if l['label']=='GRASP')
   q=self.rs['keypoints'][d['release_kp']]
   self.assertEqual(q[:5],grasp['target_q16'][:5]);self.assertEqual(q[5],round(self.plan['open_native_rad']*65536))
 def test_source_pose_and_home_contract(self):
  self.assertEqual(self.rs['pickup_D_mm'],[300,200,15]);self.assertEqual(self.rs['keypoint_bank'],3);self.assertEqual(self.rs['segment_bank'],1)
  for route in self.restore['paths']:
   self.assertEqual(route['legs'][-1]['target_q16'],self.rs['keypoints'][0]);self.assertEqual(route['legs'][8]['target_D_mm'],[300,200,15])
 def test_speed_and_no_arrival_gate_preserved(self):
  p=profile();self.assertEqual((p['speed_steps_s'],p['acceleration_100_steps_s2'],p['arrival_mask']),(1320,66,0))
  self.assertEqual(p['task_abi'],0x340b);self.assertEqual(p['scalar_profile'],'QUINTIC_10u3_15u4_6u5_UQ32')
 def test_descriptor_register_encoding(self):
  w=dict(task_writes(self.plan,self.merged))
  for i,d in enumerate([self.rs['prefix'],*self.rs['tails']]):
   v=w[TASK+0x374+4*i];self.assertEqual((v&63,(v>>8)&63,(v>>16)&63),(d['first'],d['count'],d.get('release_kp') or 0))
 def test_runtime_decodes_pl_mode_and_restock_count(self):
  r={a:0 for a in runtime.ADDRS};r.update({ARM+0x10:0x3101,PLAN+12:0x3203,TASK+0x10:0x340b,VIS+8:0x3506,VIS+0x70:0x022267a9,TASK+4:(1<<29)|(1<<20)|4,TASK+0x20:1,TASK+0x388:7})
  s=runtime.decode_v2(r);self.assertTrue(s['restocking']);self.assertEqual(s['restocked_tasks'],7)
  restock_view(s,self.restore);self.assertEqual(s['planned_waypoint'],'HOME_OPEN')
 def test_cancel_view_names_public_pickup(self):
  s=dict(object=1,segment_index=10,progress_raw=9<<24,cancel_pending=True)
  restock_view(s,self.restore);self.assertEqual(s['planned_D_mm'],[300,200,15]);self.assertIn('PUBLIC_PICKUP',s['software_status_explanation'])
 def test_runtime_configures_without_host_task_selection(self):
  rs=self.rs
  class Board(FakeBoard):
   def read(self,a,count=1):
    if a==TASK+0x374:return descriptor_words(rs)
    return super().read(a,count)
  b=Board(self.plan)
  with patch.object(runtime.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):runtime.configure(b,self.plan,self.merged,lambda:None,b.observe)
  self.assertNotIn((TASK,4),b.rows);self.assertEqual(b.mode,3)
 def test_preconnected_d5_required_before_configuration(self):
  b=FakeBoard(self.plan);b.d5=False
  with self.assertRaisesRegex(RuntimeError,'D5'):runtime.configure(b,self.plan,self.merged,lambda:None,b.observe)
  self.assertFalse(b.batches)
 def test_bridge_abi_telemetry_and_no_pc_select(self):
  import tkinter
  text,meta=generate(self.plan,self.merged);self.assertEqual(meta['task_abi'],0x340b);self.assertIn('0x340b',text)
  t=tkinter.Tcl();t.eval('proc exit {args} {error OFFLINE_EXIT};set argv {--check-only}')
  try:t.eval(text)
  except tkinter.TclError:pass
  self.assertEqual(len(t.splitlist(t.eval('set board_telemetry'))),len(runtime.ADDRS))
  t.call('host_read_guard',TASK+0x388);t.call('host_read_guard',TASK+0x374)
  with self.assertRaises(tkinter.TclError):t.call('host_guard',TASK,4)
  with self.assertRaises(tkinter.TclError):t.call('host_guard',TASK+0x388,0)

if __name__=='__main__':unittest.main()
