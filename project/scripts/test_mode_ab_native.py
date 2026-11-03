"""Host/program integrity, guarded bulk transfer and calibrated overlay tests."""
from pathlib import Path
from copy import deepcopy
import json,sys,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from pc.mode_ab.native_upload import upload,ROUTE
from pc.mode_ab.native_backend import programs

class Transport:
 def __init__(self,tamper=False):self.plane=0;self.cursor=0;self.mem={};self.committed=True;self.tamper=tamper;self.commands=[]
 def read(self,a):return [{ROUTE+12:0xb001,ROUTE+4:int(self.committed),ROUTE+8:0}[a]]
 def write(self,a,v):
  self.commands.append((a,v))
  if a==ROUTE:self.committed=v==2
  elif a==ROUTE+16:self.plane=v
  elif a==ROUTE+20:self.cursor=v
 def call(self,command):
  words=command.split();self.commands.append(command)
  if words[0]=='U':
   for i,v in enumerate(words[2:]):self.mem[self.plane,self.cursor+i]=int(v)
   return 'WRITTEN'
  if words[0]=='V':
   values=[self.mem[self.plane,self.cursor+i] for i in range(int(words[2]))]
   if self.tamper:values[0]^=1
   return ' '.join(hex(v) for v in values)
  raise AssertionError(command)
class Board:
 def __init__(self,tamper=False):self.b=Transport(tamper);self.beats=0
 def alive(self):pass
 def heartbeat(self):self.beats+=1
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.c=json.loads((ROOT/'candidate/mode_ab/native_profiles/red_cube/normal.json').read_bytes())
 def test_every_uploaded_word_read_back_then_committed(self):
  b=Board();r=upload(b,self.c['native_program']);self.assertTrue(r['all_words_read_back']);self.assertTrue(b.b.committed);self.assertGreater(b.beats,100)
  for ch in range(6):self.assertEqual([b.b.mem[ch,i] for i in range(len(self.c['native_program']['offsets']))],[q[ch]&0xffffffff for q in self.c['native_program']['offsets']])
 def test_corrupt_word_never_commits_or_keeps_a_confirmed_image(self):
  b=Board(True)
  with self.assertRaisesRegex(RuntimeError,'RAM'):upload(b,self.c['native_program'])
  self.assertFalse(b.b.committed);self.assertIsNone(b.native_program_digest);self.assertNotIn((ROUTE,2),b.b.commands)
 def test_only_confirmed_same_owner_program_can_skip_ram_transfer(self):
  b=Board();upload(b,self.c['native_program']);b.b.commands.clear();r=upload(b,self.c['native_program'])
  self.assertTrue(r['confirmed_same_owner_reuse']);self.assertEqual(r['actual_program_words_written'],0);self.assertFalse(b.b.commands)
  b.b.committed=False;self.assertTrue(upload(b,self.c['native_program'])['all_words_read_back'])
 def test_wrong_route_abi_is_rejected_before_writes(self):
  b=Board();b.b.read=lambda a:[0]
  with self.assertRaisesRegex(RuntimeError,'ABI340E'):upload(b,self.c['native_program'])
  self.assertFalse(b.b.commands)
 def test_added_formatter_programs_leave_a_and_query_slots_untouched(self):
  self.assertEqual(set(programs()),{112,208});self.assertLessEqual(len(programs()[112]),96);self.assertLessEqual(len(programs()[208]),48)
  self.assertIn(0x2006,programs()[112]);self.assertIn(0x2007,programs()[112]);self.assertIn(0x2045,programs()[208])
 def test_gripper_holds_cover_giao_travel_formula_in_both_directions(self):
  import math
  from pc.mode_ab.native_routes import stages_with_events,template,build
  for name in ('red_cube','eraser','small_canister'):
   p=template(name);banks,front,_=build(name,p['request']['pickup']['centre_mm'],0)
   stages=stages_with_events(banks[1],front)
   previous=3.1
   for stage in stages:
    if stage['wire']['T']==106:
     command=stage['wire'];target=stage['rows'][-1,5]/65536
     for speed in (command['spd'],100 if stage['label']=='OPEN_SOURCE' else 300):
      self.assertGreaterEqual(stage['period']+1e-3,abs(target-previous)*4096/(2*math.pi)/speed+1)
    previous=stage['rows'][-1,5]/65536
 def test_native_profile_is_disjoint_from_old_shared_red_settling_flags(self):
  from pc.mode_ab.shared_red import compile_path
  old=compile_path();self.assertTrue(any(x['flags']&128 for x in old['fifo']))
  self.assertFalse(any(x['flags']&128 and not x['profile'] for x in old['fifo']))
  self.assertTrue(all(x['flags']&128 and not x['profile'] for x in self.c['fifo']))
 def test_calibrated_workspace_overlay_roundtrips_to_declared_boundary(self):
  from verify_mode_b_visual_bundle import verify_current,local
  from pc.rgb_table_geometry import RGBTableGeometry
  from pc.mode_ab.vision_workspace import workspace_polygon_pixels
  _,_,w=verify_current(ROOT);g=RGBTableGeometry(local(ROOT,w['table_file']),ROOT)
  uv=workspace_polygon_pixels(g);xy=np.array([g.project(p,0)[:2] for p in uv])
  np.testing.assert_allclose(xy,[[490,215],[690,215],[690,355],[490,355]],atol=1e-5)
 def test_real_bridge_bulk_guard_denies_running_a_wrong_abi_and_overrun(self):
  import tkinter
  from pc.mode_ab.board import bridge_text
  from pc.mode_ab.registers import TASK
  from mode_a_restock_config import load_restock
  p=json.loads((ROOT/'candidate/bank1/PLAN_NATIVE.json').read_bytes());t=json.loads((ROOT/'candidate/S4_BANKED_CANDIDATE.json').read_bytes());t['restock']=load_restock()
  text,meta=bridge_text(p,t);interp=tkinter.Tcl();interp.eval(text[:text.index('if {[lindex $argv 0] eq "--check-only"}')])
  interp.eval('array set regs {0x43c50004 2 0x43c50024 1 0x43c50010 0x340e 0x43c2000c 0xb001 0x43c20014 0};proc rd {a} {global regs;return $regs([format 0x%x $a])}')
  interp.eval('route_bulk_guard 0x43c20080 32')
  for command in ('route_bulk_guard 0x43c30080 1','route_bulk_guard 0x43c20081 1','route_bulk_guard 0x43c20080 33','route_bulk_guard 0x43c200fc 2'):
   with self.assertRaises(tkinter.TclError):interp.eval(command)
  for key,value in (('0x43c50004',4),('0x43c50024',0),('0x43c50010',0x340d),('0x43c20014',2047)):
   old=interp.eval('set regs('+key+')');interp.eval(f'set regs({key}) {value}')
   with self.assertRaises(tkinter.TclError):interp.eval('route_bulk_guard 0x43c20080 2')
   interp.eval(f'set regs({key}) {old}')
  self.assertEqual(meta['task_abi'],0x340e)
if __name__=='__main__':unittest.main(verbosity=2)
