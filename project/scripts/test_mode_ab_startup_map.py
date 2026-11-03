"""Replay the actual generated startup/telemetry against an XSDB access-map stub."""
import argparse,hashlib,json,re,sys,tkinter,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from pc.mode_ab.board import bridge_text
from mode_a_restock_config import load_restock

class StartupMap(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  p=json.loads((ROOT/'candidate/bank1/PLAN_NATIVE.json').read_bytes());t=json.loads((ROOT/'candidate/S4_BANKED_CANDIDATE.json').read_bytes());t['restock']=load_restock(ROOT)
  cls.text,_=bridge_text(p,t)
  cls.load=next(line.strip() for line in cls.text.splitlines() if line.strip().startswith('loadhw '))
 def interpreter(self):
  t=tkinter.Tcl();t.eval(self.text[:self.text.index('if {[lindex $argv 0] eq "--check-only"}')])
  t.eval(r'''
set board_cpu_target 7;set messages {};set mapped {};set xsa mock_same_build.xsa
array set regs {0x43c30008 8 0x43c30004 0 0x43c50004 0}
foreach {a value} $ids {set regs([format 0x%x $a]) $value}
proc say {s} {global messages;lappend messages $s}
proc loadhw {args} {global mapped;set mapped [lindex $args [expr {[lsearch -exact $args -mem-ranges]+1}]]}
proc xsdb_map_allowed {a} {
 global mapped
 foreach pair $mapped {if {$a>=[lindex $pair 0]&&$a<=[lindex $pair 1]} {return}}
 error [format "Memory read error at 0x%08X. Blocked address 0x%08X. PL AXI slave ports access is not allowed. This address has not been added to the memory map" $a $a]
}
proc mrd {args} {
 global regs;set a [lindex $args end-1];set count [lindex $args end];set values {}
 for {set i 0} {$i<$count} {incr i} {set addr [expr {$a+4*$i}];xsdb_map_allowed $addr;set key [format 0x%x $addr];lappend values [expr {[info exists regs($key)]?$regs($key):0}]}
 return $values
}
proc mwr {args} {set a [lindex $args end-1];xsdb_map_allowed $a}
''');return t
 def test_original_four_page_map_reproduces_recorded_first_telemetry_failure(self):
  t=self.interpreter();t.eval(self.load.replace('{0x43C20000 0x43C20FFF} ',''))
  with self.assertRaisesRegex(tkinter.TclError,'Blocked address 0x43C20008'):
   t.eval('board_telemetry_snapshot')
 def test_generated_startup_registers_exact_five_pages_before_ids_and_telemetry(self):
  t=self.interpreter();begin=self.text.index('    loadhw -hw $xsa');end=self.text.index('    say "JTAG_READY"',begin)
  t.eval(self.text[begin:end]);t.eval('board_telemetry_snapshot')
  ranges=[[int(v,0) for v in t.splitlist(p)] for p in t.splitlist(t.eval('set mapped'))]
  self.assertEqual(ranges,[[a,a+4095] for a in (0x43c20000,0x43c30000,0x43c40000,0x43c50000,0x43c60000)])
  self.assertIn('MATCHING_XSA_FIVE_PL_PAGES_LOADED',t.eval('set messages'))
  self.assertIn('ALL_FIVE_ABIS_AND_MODEL_ID_PASS',t.eval('set messages'))
  self.assertEqual(int(t.eval('rd 0x43c2000c')),0xb001)
  with self.assertRaises(tkinter.TclError):t.eval('rd 0x43c21000')
 def test_generator_rejects_a_changed_unmapped_startup_template(self):
  from pc.mode_ab.native_upload import extend_bridge
  with self.assertRaisesRegex(ValueError,'startup bridge template'):extend_bridge('set ids {}\n')

def main(out):
 out.mkdir(parents=True,exist_ok=False)
 with (out/'tests.txt').open('w',encoding='utf-8') as f:
  result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StartupMap))
 names=('pc/mode_ab/native_upload.py','pc/mode_ab/board.py','pc/mode_ab/registers.py','scripts/test_mode_ab_startup_map.py')
 report=dict(passed=result.wasSuccessful(),tests=result.testsRun,scope='Actual generated Tcl loadhw/ABI/bootstrap and first telemetry, with faithful restricted-map stub',
  old_four_page_fault_reproduced=result.wasSuccessful(),hotfix_id='startup_route_map_p4_1',hardware_access=False,physical_test='NOT_RUN',
  source_hashes={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names})
 (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 print((out/'tests.txt').read_text(encoding='utf-8'));print(json.dumps(report,indent=2))
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
