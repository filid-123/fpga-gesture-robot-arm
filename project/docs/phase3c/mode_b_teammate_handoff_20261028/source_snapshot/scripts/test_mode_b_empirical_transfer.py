"""Check source displacement direction, wrist yaw and evidence boundaries."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_mode_b_empirical_transfer import prepare
from prepare_mode_b_loaded_route import ROOT,NAMES,read
from pc.roarm_reference_kinematics import ReferenceGeometry,forward
from pc.mode_b.motion.kinematics import Robot

BASE=ROOT/'artifacts/phase3c/mode_b_ttl_20261028/today_native_anchor/new_position_trial'


class NativeTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=read(BASE/'native_plan/LOADED_ROUTE_PLAN.json')
        cls.anchor=read(cls.plan['accepted_native_source_anchor_file'])
        cls.original=read(cls.anchor['accepted_plan_file'])
        cls.geo=ReferenceGeometry(**read(ROOT/'config/ai_pc/roarm_reference_geometry.json')['geometry_mm'])

    def low(self,plan):
        return next(s['stage']['target_firmware_rad'] for s in plan['stages'] if s['phase']=='DESCEND')

    def test_desk_right_maps_to_native_negative_y_with_only2mm_extra(self):
        old=np.array(forward([self.low(self.original)[n] for n in NAMES[:4]],self.geo))
        new=np.array(forward([self.low(self.plan)[n] for n in NAMES[:4]],self.geo))
        d=np.array(self.plan['request']['pickup']['centre_mm'])-self.anchor['source_camera_centre_mm']
        expected=np.array([d[1],-d[0],0.])
        extra=(new-old)[:3]-expected
        self.assertAlmostEqual(float(np.linalg.norm(extra[:2])),2.,places=6)
        self.assertAlmostEqual(extra[2],0.,places=6)
        self.assertGreater(np.dot(extra[:2],new[:2]),0)
        self.assertFalse(self.plan['measured70_or_previous19_blanket_offset_used'])

    def test_wrist_compensates_base_turn_to_keep_detected_closing_yaw(self):
        r=Robot(ROOT,self.plan['local_scene_config'],grasp_width_mm=30)
        def yaw(p):
            q=np.array([self.low(p)[n] for n in NAMES]);T=r.fk(np.r_[q[:5],0.])
            return math.atan2(T[1,0],T[0,0])
        actual=(yaw(self.plan)-yaw(self.original)+math.pi)%(2*math.pi)-math.pi
        expected=math.radians(self.plan['local_transfer']['yaw_delta_equivalent_deg'])
        self.assertLess(abs(actual-expected),1e-4)

    def test_direct_entry_begins_at_current_home_and_has_complete_release_return(self):
        p=self.plan;s=p['stages'][0]
        self.assertEqual(s['phase'],'DIRECT_PREGRASP')
        self.assertEqual(s['stage']['stream_frames'][0]['command_firmware_rad'],p['start_firmware_rad'])
        self.assertEqual(p['stages'][-1]['phase'],'RETURN_LOW_HOME')
        self.assertEqual(p['request']['destination']['support_centre_mm'],[285,195,150])
        self.assertEqual(json.loads(p['close_after_descent_wire_json'])['cmd'],2.70)
        self.assertEqual(p['speed_multiplier'],2)

    def test_stale_anchor_cannot_drive_new_source(self):
        request=read(self.plan['source_metric_request_file'])
        request['source_planning_strategy']['anchor_sha256']='0'*64
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'request.json';p.write_text(json.dumps(request),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'source anchor changed'):
                prepare(Path(self.plan['capture_file']),p,2)


if __name__=='__main__':unittest.main()
