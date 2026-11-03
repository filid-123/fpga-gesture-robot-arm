"""Decoder and Tcl read-only contract checks, without any board connection."""
import json
from pathlib import Path
import unittest
import tkinter
from unittest.mock import patch

import mode_a_terminal as t


class TerminalTests(unittest.TestCase):
    def raw(self):return next(t.demo())['raw']
    def test_demo_has_no_physical_claim(self):
        rows=list(t.demo());self.assertEqual(len(rows),7)
        self.assertTrue(all(r['source']=='SYNTHETIC_TERMINAL_DEMO' for r in rows))
    def test_palm_action_mapping(self):
        r=list(t.demo())[2];self.assertEqual((r['model'],r['gesture']),('PALM','PALM_READY'))
    def test_fist_action_mapping(self):
        r=self.raw();r[f'0x{t.VIS+0x68:08x}']=4<<16;r[f'0x{t.VIS+4:08x}']=1|(5<<5)
        s=t.decode(r);self.assertEqual((s['model'],s['gesture']),('FIST','FIST_CANCEL'))
    def test_wrong_task_abi_refused(self):
        r=self.raw();r[f'0x{t.TASK+16:08x}']=0x3403
        with self.assertRaises(ValueError):t.decode(r)
    def test_old_model_refused(self):
        r=self.raw();r[f'0x{t.VIS+0x70:08x}']=0xe4c43d44
        with self.assertRaises(ValueError):t.decode(r)
    def test_signed_targets(self):
        r=self.raw();r[f'0x{t.PLAN+0x200:08x}']=0xffff0000
        self.assertEqual(t.decode(r)['last_delivered_rad'][0],-1.)
    def test_signed_feedback(self):
        r=self.raw();r[f'0x{t.ARM+0x200:08x}']=(-10000)&0xffffffff
        self.assertEqual(t.decode(r)['feedback_rad'][0],-1.)
    def test_clock_wrap(self):
        r=self.raw();r[f'0x{t.VIS+0x84:08x}']=10;r[f'0x{t.VIS+0x5c:08x}']=0xfffffff0
        self.assertEqual(t.decode(r)['image_age_ms'],26)
    def test_empty_refusal(self):
        r=list(t.demo())[-1];self.assertEqual(r['refusal'],'EMPTY_SLOT');self.assertEqual(r['inventory_mask'],6)
    def test_sticky_refusal_does_not_mask_running(self):
        r=self.raw();r[f'0x{t.TASK+8:08x}']=11<<16;r[f'0x{t.TASK+4:08x}']=4|(1<<4)
        self.assertEqual(t.decode(r)['software_status_explanation'],'EXECUTING_OUT')
    def test_snapshot_delta_not_position_accuracy(self):
        self.assertIn('delta_snapshot_deg=',t.line(next(t.demo())))
    def test_failed_jtag_startup_closes_owned_reader(self):
        class Process:
            stdout=iter(['READONLY_ERROR no target\n'])
        with patch.object(t.subprocess,'Popen',return_value=Process()),patch.object(t.JtagReader,'close') as cleanup:
            with self.assertRaisesRegex(RuntimeError,'no target'):t.JtagReader()
            cleanup.assert_called_once()
    def test_tcl_has_no_write_or_program_path(self):
        path=Path(t.__file__).with_name('mode_a_terminal_readonly.tcl')
        text=path.read_text('utf-8')
        import re
        self.assertIsNone(re.search(r'(?m)^\s*(mwr|fpga|stop|rst|con|rwr)\b',text))
        interp=tkinter.Tcl()
        interp.eval('proc connect {args} {};proc targets {args} {};proc disconnect {args} {}')
        # Stub mrd returns decimal (including >signed32), ensuring no mistaken
        # hexadecimal re-parse. All hardware APIs are replaced before sourcing.
        interp.eval('proc mrd {args} {return 4294967295};proc exit {args} {return -code return}')
        interp.eval('set sent 0;proc gets {chan var} {upvar 1 $var v;global sent;incr sent;if {$sent==1} {set v S} else {set v Q};return 1}')
        interp.eval('set output {};rename puts real_puts;proc puts {args} {global output;lappend output [lindex $args end]}')
        interp.eval('source {'+path.as_posix()+'}')
        addresses=interp.splitlist(interp.eval('set addresses'))
        self.assertEqual([int(x,0) for x in addresses],t.ADDRS)
        output=interp.eval('set output');self.assertIn('0xffffffff',output)


if __name__=='__main__':unittest.main()
