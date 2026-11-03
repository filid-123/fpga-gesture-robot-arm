"""Pose-rotation and failed-selection regressions; no hardware or camera access."""
from concurrent.futures import Future
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.control import Controller
from pc.mode_ab.runtime import Runtime
from pc.mode_ab.motion import transfer,template,objects,qrow,build_banks,native_with_front,profile_id,RED_DEPTH_ANCHOR,compile_banks
from pc.mode_ab.shared_red import A_SOURCE


class MemoryBoard:
    mode='B'
    def __init__(self):
        self.root=ROOT;self.b=self;self.writes=[]
        self.value=dict(fpga_mode='B',object=1,state='IDLE',fault='NONE',arm_fault=False,
            selected_task_id=9,selected_gesture=1,done_counter=0,cancelled_counter=0,restocked_tasks=0)
    def observe(self,*args):return deepcopy(self.value)
    def heartbeat(self):pass
    def write(self,address,value):self.writes.append((address,value))


class MemoryCamera:
    def __init__(self):
        self.value=dict(ready=True,observation=dict(frame_id=1,recognitions=[],localizations=[
            dict(class_name=n,geometry_gate_pass=True,object_centre_desktop_xyz_mm=c,
                 top=dict(long_axis_yaw_mod180_deg=0)) for n,c in
            [('red_cube',[650,258,15]),('eraser',[632,266,7.5])]]))
    def snapshot(self):return deepcopy(self.value)


class ImmediateExecutor:
    def __init__(self):self.calls=[]
    def submit(self,fn,*args):
        self.calls.append(args);f=Future()
        try:f.set_result(fn(*args))
        except Exception as exc:f.set_exception(exc)
        return f
    def shutdown(self,**kwargs):pass


def rejected_plan(folder,*args):
    folder.mkdir(parents=True,exist_ok=False)
    raise ValueError('Explicit fake planning refusal')


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)
        self.c=Controller();self.c.mode='B';self.c.active_bindings=[dict(gesture=1,object_id='red_cube')]
        self.board=MemoryBoard();self.camera=MemoryCamera();self.r=Runtime(self.board,self.camera,self.c,self.out)
        self.r.executor.shutdown(wait=True);self.executor=ImmediateExecutor();self.r.executor=self.executor
    def tearDown(self):self.r.close();self.temp.cleanup()

    def test_failed_plan_never_reconsumes_old_wait_path_or_recreates_directory(self):
        self.board.value['state']='WAIT_PATH'
        with patch('pc.mode_ab.runtime.plan_delivery',rejected_plan):
            self.r.tick();self.r.tick();self.r.tick()
            self.assertEqual(len(self.executor.calls),1)
            self.assertIsNone(self.r.task);self.assertIsNone(self.r.future);self.assertIsNone(self.c.frozen_task)
            self.assertTrue((self.out/'plans/9').is_dir())
            self.assertEqual(len(self.board.writes),1)
            self.board.value['selected_task_id']=10;self.r.tick()
            self.assertEqual(len(self.executor.calls),2)
            self.assertTrue((self.out/'plans/10').is_dir())

    def test_rejected_stale_rgb_selection_is_cancelled_only_once(self):
        self.board.value['state']='WAIT_PATH';self.camera.value['ready']=False
        self.r.tick();self.r.tick();self.r.tick()
        self.assertEqual(len(self.board.writes),1);self.assertEqual(self.executor.calls,[])

    def test_failed_background_pose_does_not_starve_other_classes_or_flood_retries(self):
        self.c.active_bindings.append(dict(gesture=2,object_id='eraser'))
        with patch('pc.mode_ab.runtime.plan_delivery',rejected_plan):
            for _ in range(6):self.r.tick()
            self.assertEqual([x[1] for x in self.executor.calls],['red_cube','eraser'])
            self.camera.value['observation']['localizations'][0]['object_centre_desktop_xyz_mm'][0]+=4
            self.r.tick();self.assertEqual([x[1] for x in self.executor.calls],['red_cube','eraser','red_cube'])

    def test_failed_pose_does_not_suppress_crossing_into_a_fixed_slot(self):
        failed=dict(source_centre_mm=[533.2,250,15],source_yaw_deg=0,origin_kind='B_DYNAMIC')
        self.assertFalse(self.r.same_source('red_cube',failed,[532.9,250,15],0,3,3))

    def test_inflight_background_plan_for_old_pose_is_not_reused(self):
        self.board.value['state']='WAIT_PATH';old=Future()
        self.r.precompute=old;self.r.precompute_name='red_cube'
        self.r.precompute_pose=dict(source_centre_mm=[610,258,15],source_yaw_deg=0,origin_kind='B_DYNAMIC')
        with patch('pc.mode_ab.runtime.plan_delivery',rejected_plan):self.r.tick()
        self.assertIsNot(self.r.future,old);self.assertEqual(len(self.executor.calls),1)

    def test_red_depth_profile_applies_beyond_historical_radius(self):
        source=np.array(RED_DEPTH_ANCHOR)
        self.assertEqual(profile_id('red_cube',source+[25,0,0]),'red_depth12')
        self.assertEqual(profile_id('red_cube',source+[25.01,0,0]),'red_depth12')
        p,_=transfer('red_cube',source+[26,0,0],0,selected_profile='red_depth12')
        self.assertEqual(p['ab_profile_id'],'red_depth12')

    def test_cache_cannot_cross_profile_boundary_within_pose_tolerance(self):
        p=dict(source_centre_mm=(np.array(RED_DEPTH_ANCHOR)+[24.9,0,0]).tolist(),source_yaw_deg=0,
               profile_id='red_depth12',origin_kind='B_DYNAMIC')
        self.assertTrue(self.r.same_source('red_cube',p,np.array(RED_DEPTH_ANCHOR)+[25.1,0,0],0,.5,.5))

    def test_rotated_legacy_red_source_can_solve_without_relaxing_mechanical_limits(self):
        # Keep the original p2 regression at its original measured anchor.
        p=template('red_cube','red_legacy');source=np.array(p['request']['pickup']['centre_mm'])+[-12,17,0]
        _,front=transfer('red_cube',source,p['request']['pickup']['yaw_deg']-30)
        robot,_=objects(p)
        for stage in front:
            for row in stage['rows']:
                self.assertTrue(np.all(np.array(row)[:5]>robot.limits[:5,0]))
                self.assertTrue(np.all(np.array(row)[:5]<robot.limits[:5,1]))

    def test_nominal_source_retains_frozen_descent_target(self):
        p=template('red_cube');_,front=transfer('red_cube',**dict(centre=p['request']['pickup']['centre_mm'],yaw=p['request']['pickup']['yaw_deg']))
        np.testing.assert_array_equal(front[1]['rows'][-1],qrow(p['stages'][1]['stage']['target_firmware_rad']))

    def test_workspace_rejects_outside_but_not_eraser_anchor_distance(self):
        for name,source in [('red_cube',[700,250,15]),('eraser',[580,365,7.5])]:
            with self.assertRaises(ValueError):transfer(name,source,0)
        p,_=transfer('eraser',[580,265,7.5],0)
        np.testing.assert_array_equal(p['request']['pickup']['centre_mm'],[580,265,7.5])

    def test_depth12_rotated_field_source_preserves_table_clearance(self):
        banks,front=build_banks('red_cube',[584.62456,261.15087,15],87.24065)
        # This field pose previously sagged below 0.25 mm with a cosine-only IK
        # objective. Both Q16 and wire-rounded samples now pass unchanged gates.
        compiled=compile_banks(banks,front,validate_tail=False)
        self.assertEqual(banks[1]['ab_profile_id'],'red_depth12')
        self.assertGreater(compiled['geometry']['samples_checked'],0)

    def test_exported_connector_has_start_and_target_for_return_reversal(self):
        p=template('red_cube');banks,front=build_banks('red_cube',p['request']['pickup']['centre_mm'],p['request']['pickup']['yaw_deg'])
        native=native_with_front(banks[1],front)
        stage=next(s for s in native['stages'] if s['phase']=='INNER_HOLD')
        frames=stage['stage']['stream_frames'];self.assertGreaterEqual(len(frames),2)
        np.testing.assert_array_equal(qrow(frames[0]['command_firmware_rad']),qrow(stage['start_firmware_rad']))
        np.testing.assert_array_equal(qrow(frames[-1]['command_firmware_rad']),qrow(stage['stage']['target_firmware_rad']))


if __name__=='__main__':unittest.main()
