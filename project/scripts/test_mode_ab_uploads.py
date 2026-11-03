"""Replay real A/B write streams against S4 RAM semantics; no device access."""
import json
from pathlib import Path
import sys
import unittest
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from pc.mode_ab.uploads import TableImage,home_b_writes
from pc.mode_ab.registers import TASK,b_writes
from pc.mode_ab.motion import home
from mode_a_restock_config import task_writes,load_restock


class RAM:
    def __init__(self):
        self.kp=[[0xdeadbeef]*512 for _ in range(4)];self.seg=[0xdeadbeef]*256
        self.ready=[False]*4;self.bank=0;self.ka=0;self.sa=0;self.registers={}
    def apply(self,rows):
        for address,v in rows:
            v&=0xffffffff
            if address==TASK+0x12c:self.bank=v
            elif address==TASK+0x110:self.ka=v
            elif address==TASK+0x118:self.sa=v
            elif address==TASK+0x114:
                self.kp[self.bank][self.ka]=v
                if self.ka==0:self.ready[self.bank]=False
                if self.ka==511:self.ready[self.bank]=True
                self.ka=(self.ka+1)%512
            elif address==TASK+0x11c:self.seg[self.sa]=v;self.sa=(self.sa+1)%256
            else:self.registers[address]=v


class Tests(unittest.TestCase):
    def test_real_a_b_reconfiguration_preserves_full_ram_and_readiness(self):
        p=json.loads((ROOT/'candidate/bank1/PLAN_NATIVE.json').read_bytes())
        t=json.loads((ROOT/'candidate/S4_BANKED_CANDIDATE.json').read_bytes());t['restock']=load_restock()
        a=task_writes(p,t);b=json.loads((ROOT/'candidate/mode_ab/profiles/red_depth12/normal.json').read_bytes())
        image=TableImage();full=RAM();sparse=RAM();counts=[]
        for rows in (a,home_b_writes([round(v*65536)&0xffffffff for v in home('B')]),b_writes(b),b_writes(b),a):
            optimized,image=image.plan(rows);full.apply(rows);sparse.apply(optimized)
            self.assertEqual(full.kp,sparse.kp);self.assertEqual(full.seg,sparse.seg)
            self.assertEqual(full.registers,sparse.registers);self.assertEqual(sparse.ready,[True]*4)
            self.assertEqual(image.kp,sparse.kp);counts.append((len(rows),len(optimized)))
        self.assertLess(counts[1][1],100);self.assertLess(counts[3][1],50)
        self.assertLess(counts[-1][1],counts[-1][0]);print('UPLOAD_COUNTS',counts)

    def test_partial_unknown_bank_cannot_claim_a_complete_image(self):
        with self.assertRaisesRegex(ValueError,'sentinels'):TableImage().plan(home_b_writes([0]*6))

    def test_uncertain_transport_invalidates_image(self):
        from pc.mode_ab.board import Board
        board=Board.__new__(Board);board.image=TableImage()
        def fail(rows):raise IOError('simulated partial upload')
        board.batch=fail
        with self.assertRaises(IOError):board.upload([[TASK+0x118,0],[TASK+0x11c,42]])
        self.assertTrue(all(x is None for x in board.image.seg))

    def test_same_mode_rebinding_never_reloads_tables_or_moves(self):
        from pc.mode_ab.board import Board
        from pc.mode_ab.control import Controller
        for mode in ('A','B'):
            board=Board.__new__(Board);board.mode=mode;board.control=Controller();board.reconcile_red=None
            s=dict(state='IDLE',at_home=True,holding=False,arm_fault=False,fault='NONE',abi_verified=True)
            board.control.update(s);board.observe=lambda *args:deepcopy(s)
            class Transport:
                def __init__(self):self.words={};self.writes=[]
                def write(self,a,v):self.words[a]=v;self.writes.append((a,v))
                def read(self,a):return [self.words[a]]
            board.b=Transport()
            def forbidden(*args):raise AssertionError('Same-mode mapping must not move or reload tables')
            board.move=board.upload=board.await_state=forbidden
            ack=board.configure_mode(mode,[dict(gesture=1,object_id='red_cube')])
            self.assertFalse(ack['motion_started']);self.assertEqual(len(board.b.writes),1)
            self.assertEqual(board.b.writes[0][0],TASK+0x24)


if __name__=='__main__':unittest.main()
