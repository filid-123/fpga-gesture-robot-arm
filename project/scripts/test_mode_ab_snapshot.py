"""ABI -> Board.observe -> Runtime regressions; transport is entirely in memory."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.board import Board
from pc.mode_ab.control import Controller
from pc.mode_ab.motion import home
from pc.mode_ab.registers import ADDRS,ARM,PLAN,TASK,VIS,snapshot
from pc.mode_ab.runtime import Runtime
from pc.mode_ab.shared_red import A_SOURCE


def registers(mode='A'):
    raw=dict.fromkeys(ADDRS,0)
    raw.update({ARM+0x10:0x3101,PLAN+12:0x3203,TASK+0x10:0x340e,
                VIS+8:0x3506,VIS+0x70:0x022267a9,ARM+8:8|32|(3<<12),
                TASK+4:1|128|(7<<26),TASK+0x24:int(mode=='B'),
                TASK+0x240:7,TASK+0x244:11,TASK+0x388:13,
                VIS+4:1|(1<<5),VIS+0x38:1,VIS+0x68:1<<16})
    raw.update({PLAN+0x200+4*i:round(q*65536)&0xffffffff for i,q in enumerate(home(mode))})
    return raw


class RegisterReplay:
    def __init__(self):self.raw=registers();self.writes=[]
    def telemetry(self):return deepcopy(self.raw)
    def write(self,address,value):
        if (address,value)!=(TASK,1024):raise AssertionError('Only the fake B heartbeat is permitted')
        self.writes.append((address,value))


class DisconnectedCamera:
    def snapshot(self):return dict(ready=False,observation=None)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)
        self.control=Controller();self.transport=RegisterReplay()
        self.board=Board(ROOT,self.out,self.control,{},{},{},threading.Event())
        self.board.b=self.transport;self.stock=[];self.board.set_red_available=self.stock.append
        self.runtime=Runtime(self.board,DisconnectedCamera(),self.control,self.out)

    def tearDown(self):
        self.runtime.close();self.board.telemetry.close();self.board.communication.close();self.temp.cleanup()

    def test_register_values_are_exposed_without_defaulting_missing_counters(self):
        s=snapshot(self.transport.raw)
        self.assertEqual((s['done_counter'],s['cancelled_counter'],s['restocked_tasks']),(7,11,13))
        for offset in (0x240,0x244):
            raw=deepcopy(self.transport.raw);del raw[TASK+offset]
            with self.assertRaises(KeyError):snapshot(raw)

    def test_counter_values_preserve_all_32_bits(self):
        self.transport.raw[TASK+0x240]=0xffffffff;self.transport.raw[TASK+0x244]=0x80000000
        s=snapshot(self.transport.raw)
        self.assertEqual((s['done_counter'],s['cancelled_counter']),(0xffffffff,0x80000000))

    def test_a_first_one_selection_survives_real_snapshot_adapter(self):
        self.runtime.tick()
        self.transport.raw[TASK+4]=4|(1<<4)|128|(1<<20)|(6<<26)
        self.runtime.tick();self.runtime.tick()
        self.assertEqual(self.board.last['state'],'RUN')
        self.assertEqual(self.board.last['object'],1)
        self.assertEqual(self.board.last['gesture'],'OBJECT_1')
        self.assertNotIn('red_cube',self.control.origins)

    def test_a_delivery_counter_creates_cross_mode_origin(self):
        self.runtime.tick();self.transport.raw[TASK+4]=1|128|(1<<20)|(6<<26)
        self.transport.raw[TASK+0x240]+=1;self.runtime.tick()
        self.assertEqual(self.control.origins['red_cube']['task_id'],'A:8')
        self.transport.raw[TASK+0x388]+=1;self.runtime.tick()
        self.assertNotIn('red_cube',self.control.origins)

    def b_task(self):
        self.board.mode=self.control.mode='B';self.transport.raw=registers('B')
        self.control.active_bindings=[dict(gesture=1,object_id='red_cube')]
        frame=dict(recognitions=[dict(class_name='red_cube',bbox_xyxy_raw=[1,2,3,4])])
        self.runtime.task=self.control.select(1,9,frame)
        self.runtime.before=snapshot(self.transport.raw);self.runtime.committed=True
        folder=self.out/'plan';folder.mkdir();(folder/'native.json').write_text('{}')
        self.runtime.prepared=dict(folder=str(folder),source_centre_mm=A_SOURCE,source_yaw_deg=0,
                                   origin_kind='A_FIXED',plan_sha256='explicit_fake_plan')

    def test_b_completion_and_restock_use_decoded_hardware_counters(self):
        self.b_task();self.transport.raw[TASK+0x240]+=1;self.runtime.tick()
        self.assertEqual(self.stock,[False]);self.assertIn('red_cube',self.control.origins)
        self.runtime.task=self.control.select(1,10,{})
        self.runtime.before=snapshot(self.transport.raw);self.runtime.committed=True
        self.transport.raw[TASK+0x388]+=1;self.runtime.tick()
        self.assertEqual(self.stock,[False,True]);self.assertNotIn('red_cube',self.control.origins)

    def test_b_cancel_uses_decoded_counter_without_marking_delivery(self):
        self.b_task();self.transport.raw[TASK+0x244]+=1;self.runtime.tick()
        self.assertIsNone(self.runtime.task);self.assertIsNone(self.control.frozen_task)
        self.assertEqual(self.stock,[]);self.assertNotIn('red_cube',self.control.origins)


if __name__=='__main__':unittest.main()
