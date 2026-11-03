"""Cross-mode identity and inventory tests with an explicitly fake board."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
import threading
import unittest
from concurrent.futures import Future
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.control import Controller,ControlError
from pc.mode_ab.runtime import Runtime,plan_delivery
from pc.mode_ab.shared_red import A_SOURCE,compile_path
from pc.mode_ab.motion import home


class FakeCamera:
    def __init__(self):self.value=dict(ready=False,observation=None)
    def snapshot(self):return deepcopy(self.value)


class FakeBoard:
    def __init__(self):self.root=ROOT;self.calls=[];self.value={};self.mode='B'
    def observe(self,*args):return deepcopy(self.value)
    def heartbeat(self):pass
    def set_red_available(self,value):self.calls.append(value)
    def commit(self,compiled,task):self.committed=(compiled,task)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)
        self.c=Controller();self.cam=FakeCamera();self.board=FakeBoard()
        self.r=Runtime(self.board,self.cam,self.c,self.out)
        self.s=dict(fpga_mode='A',object=1,done_counter=0,restocked_tasks=0,cancelled_counter=0,
                    state='IDLE',fault='NONE',arm_fault=False)

    def tearDown(self):self.r.close();self.temp.cleanup()

    def test_a_delivery_becomes_b_restock_even_after_gesture_reordering(self):
        self.r.observe_a_red(self.s);s=deepcopy(self.s);s['done_counter']=1;self.r.observe_a_red(s)
        self.c.mode='B';self.c.active_bindings=[dict(gesture=1,object_id='eraser'),dict(gesture=2,object_id='red_cube')]
        task=self.c.select(2,7,{})
        self.assertEqual(task['kind'],'RESTOCK');self.assertEqual(task['origin']['origin_kind'],'A_FIXED')
        self.c.complete(7,outcome='cancelled');self.assertIn('red_cube',self.c.origins)
        s['restocked_tasks']=1;self.r.observe_a_red(s);self.assertNotIn('red_cube',self.c.origins)

    def test_b_shared_slot_delivery_and_restock_update_a_inventory_before_unlock(self):
        self.c.mode='B';self.c.active_bindings=[dict(gesture=1,object_id='red_cube')]
        obs=dict(recognitions=[dict(class_name='red_cube',bbox_xyxy_raw=[100,100,130,130])])
        task=self.c.select(1,9,obs);self.r.task=task
        self.r.prepared=plan_delivery(self.out/'plans/9','red_cube',A_SOURCE,0,obs)
        self.r.before=deepcopy(self.s);self.r.committed=True;self.r.commit_time=time.monotonic()
        self.board.value={**self.s,'fpga_mode':'B','done_counter':1}
        self.r.tick();self.assertEqual(self.board.calls,[False]);self.assertEqual(self.c.origins['red_cube']['origin_kind'],'A_FIXED')
        self.r.task=self.c.select(1,10,{})
        self.r.before=deepcopy(self.board.value);self.r.committed=True;self.r.commit_time=time.monotonic()
        self.board.value['restocked_tasks']=1
        self.r.tick();self.assertEqual(self.board.calls,[False,True]);self.assertNotIn('red_cube',self.c.origins)

    def test_a_red_is_disabled_when_cube_is_visible_elsewhere(self):
        self.cam.value=dict(ready=True,observation=dict(recognitions=[],localizations=[dict(class_name='red_cube',
            geometry_gate_pass=True,object_centre_desktop_xyz_mm=[650,250,15],top=dict(long_axis_yaw_mod180_deg=0))]))
        self.assertTrue(self.r.reconcile_red('A'));self.assertEqual(self.board.calls,[False])
        self.assertFalse(self.r.reconcile_red('B'))

    def test_public_restock_refuses_an_object_still_in_workspace(self):
        self.cam.value=dict(ready=True,observation=dict(recognitions=[],localizations=[dict(class_name='red_cube',
            geometry_gate_pass=True,object_centre_desktop_xyz_mm=[650,250,15])]))
        with self.assertRaises(ControlError):self.r.check_source_clear(dict(origin_kind='A_FIXED',source_centre_mm=A_SOURCE))

    def test_shared_macros_connect_exact_homes_and_keep_single_grasp(self):
        for restock in (False,True):
            c=compile_path(restock);self.assertEqual(c['fifo'][0]['target_q16'],[round(v*65536) for v in home('A')])
            self.assertEqual(sum(bool(r['flags']&1) for r in c['fifo']),1)
            if restock:self.assertEqual(c['fifo'][-1]['target_q16'],[round(v*65536) for v in home('B')])
            else:self.assertEqual(c['keypoint_banks'][1][c['home_kp']],[round(v*65536) for v in home('B')])

    def test_cached_plan_is_copied_to_unique_task_folder_before_commit(self):
        obs=dict(frame_id=1,recognitions=[dict(class_name='red_cube',bbox_xyxy_raw=[100,100,130,130])],
            localizations=[dict(class_name='red_cube',geometry_gate_pass=True,object_centre_desktop_xyz_mm=A_SOURCE,
                               top=dict(long_axis_yaw_mod180_deg=0))])
        self.cam.value=dict(ready=True,observation=obs)
        cached=plan_delivery(self.out/'preplans/red_cube_1','red_cube',A_SOURCE,0,obs)
        self.c.mode='B';self.c.active_bindings=[dict(gesture=1,object_id='red_cube')]
        self.r.task=self.c.select(1,9,obs);self.r.future=Future();self.r.future.set_result(cached)
        self.board.value={**self.s,'fpga_mode':'B','state':'WAIT_PATH','selected_task_id':9,'selected_gesture':1}
        self.r.tick()
        self.assertEqual(Path(self.r.prepared['folder']),self.out/'plans/9')
        self.assertTrue((self.out/'plans/9/compiled.json').is_file())
        self.assertFalse((self.out/'preplans/red_cube_1/origin.json').exists())
        self.assertEqual(self.board.committed[1]['task_id'],9)

    def test_cache_never_crosses_the_fixed_slot_dispatch_boundary(self):
        self.r.cache['red_cube']=dict(origin_kind='A_FIXED',source_centre_mm=[532.9,250,15],source_yaw_deg=0)
        self.assertFalse(self.r.cached('red_cube',[533.2,250,15],0))

    def test_shutdown_failure_is_returned_as_required_operator_recovery(self):
        from pc.mode_ab.board import Board
        class BrokenBridge:
            ready=True;failed=False
            def read(self,*args):raise RuntimeError('explicit fake transport failure')
        folder=self.out/'shutdown_test';folder.mkdir()
        b=Board(ROOT,folder,self.c,{}, {},{},threading.Event());b.b=BrokenBridge()
        result=b.close()
        self.assertTrue(result['requires_operator_power_cycle'])
        self.assertIn('shutdown_error',result)


if __name__=='__main__':unittest.main()
