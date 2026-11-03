"""PC tests for trace ownership, restoration and new ABI admission."""
from pathlib import Path
import contextlib,io,json,tempfile,tkinter,unittest
from mode_a_upgrade_config import ROOT,VIS,PLAN,TASK,ARM
from mode_a_upgrade_trace import dump_trace
from prepare_mode_a_upgrade_bridge import generate
from run_mode_a_upgrade import ADDRS,decode_v2
class ObserverTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=ROOT/'candidate'
  if not p.exists():p=ROOT/'board_evidence/mode_a_upgrade_plan_a3'
  cls.plan=json.loads((p/'bank1/PLAN_NATIVE.json').read_text('utf-8'));cls.table=json.loads((p/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
 def test_trace_wrap_is_chronological_and_unfreezes(self):
  class B:
   def __init__(self):self.writes=[];self.index=0
   def write(self,a,v):
    self.writes.append((a,v))
    if a==VIS+0x240:self.index=v
   def read(self,a,count=1):
    if a==VIS+0x208:return [300]
    if a==VIS+0x214:return [44]
    if a==VIS+0x20c:return [2]
    if a==VIS+0x244:return [self.index,(8<<28)|self.index,*([0xffffffff]*6)]
    raise ValueError(a)
  b=B()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'trace.json';meta=dump_trace(b,p);data=json.loads(p.read_text('utf-8'))
  self.assertEqual([r['index'] for r in data['rows']],list(range(44,256))+list(range(44)))
  self.assertEqual(data['rows'][0]['last_delivered_q16'],[-1]*6);self.assertEqual(data['overwritten'],44)
  self.assertEqual(b.writes[0],(VIS+0x23c,1));self.assertEqual(b.writes[-1],(VIS+0x23c,0));self.assertEqual(meta['retained'],256)
  self.assertTrue(all(a in (VIS+0x23c,VIS+0x240) for a,v in b.writes))
 def test_trace_read_failure_still_unfreezes(self):
  class B:
   def __init__(self):self.writes=[]
   def write(self,a,v):self.writes.append((a,v))
   def read(self,*args):raise RuntimeError('READ_FAILED')
  b=B()
  with self.assertRaisesRegex(RuntimeError,'READ_FAILED'):dump_trace(b,Path('unused.json'))
  self.assertEqual(b.writes,[(VIS+0x23c,1),(VIS+0x23c,0)])
 def tcl(self):
  text,meta=generate(self.plan,self.table);t=tkinter.Tcl();t.eval('proc exit {args} {error OFFLINE_EXIT};set argv {--check-only}')
  with contextlib.redirect_stdout(io.StringIO()):
   try:t.eval(text)
   except tkinter.TclError as e:self.assertIn('OFFLINE_EXIT',str(e))
  return t,text,meta
 def test_observer_whitelist_denies_motion_and_invalid_controls(self):
  t,text,meta=self.tcl()
  for a in [VIS+0x23c,VIS+0x240,*range(VIS+0x244,VIS+0x264,4)]:t.call('host_read_guard',a)
  for a,v in [(VIS+0x23c,0),(VIS+0x23c,1),(VIS+0x240,255)]:t.call('host_guard',a,v)
  for a,v in [(VIS+0x23c,2),(VIS+0x240,256),(VIS+0x244,1),(TASK,4),(TASK,3),(0xf8000240,0)]:
   with self.assertRaises(tkinter.TclError):t.call('host_guard',a,v)
  self.assertIn('0x3203',text);self.assertIn('0x3506',text)
 def test_metrics_and_accepted_coordinate_decode(self):
  r={a:0 for a in ADDRS};r.update({ARM+0x10:0x3101,PLAN+12:0x3203,TASK+0x10:0x340a,VIS+8:0x3506,VIS+0x70:0x022267a9,TASK+0x324:16|(48<<8),VIS+0x200:1634321,VIS+0x204:468487})
  s=decode_v2(r);self.assertEqual((s['align_step'],s['align_target_step']),(16,48));self.assertAlmostEqual(s['classifier_ms'],4.68487)
  r[PLAN+12]=0x3202
  with self.assertRaises(ValueError):decode_v2(r)
 def test_terminal_addresses_unique(self):self.assertEqual(len(ADDRS),len(set(ADDRS)))
if __name__=='__main__':unittest.main()
