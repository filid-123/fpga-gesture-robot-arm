"""Check that a measured local correction cannot silently become global."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_mode_b_empirical_transfer import prepare,check_source_correction_locality
from prepare_mode_b_loaded_route import ROOT,read,digest,NAMES
from pc.mode_b.motion.kinematics import Robot


class LocalMeasuredCorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter_path=ROOT/'config/ai_pc/mode_b_eraser_grasp_20261028_v4.json'
        cls.adapter=read(cls.adapter_path)
        cls.source=cls.adapter['source_correction_locality']['reference_source_centre_mm']

    def test_measured_neighbourhood_is_accepted(self):
        check=check_source_correction_locality(self.adapter,self.source)
        self.assertEqual(check['current_source_xy_distance_mm'],0)
        self.assertEqual(check['maximum_xy_distance_mm'],25)

    def test_distant_camera_source_is_rejected(self):
        point=np.array(self.source)+[25.01,0,0]
        with self.assertRaisesRegex(ValueError,'outside'):
            check_source_correction_locality(self.adapter,point)

    def test_object_height_cannot_change_under_same_correction(self):
        point=np.array(self.source)+[0,0,1]
        with self.assertRaisesRegex(ValueError,'outside'):
            check_source_correction_locality(self.adapter,point)

    def test_bad_envelope_and_changed_measurement_are_rejected(self):
        for radius in (0,26,float('nan')):
            adapter=deepcopy(self.adapter);adapter['source_correction_locality']['maximum_xy_distance_mm']=radius
            with self.assertRaises(ValueError):check_source_correction_locality(adapter,self.source)
        adapter=deepcopy(self.adapter)
        adapter['source_correction_locality']['reference_source_centre_mm'][0]+=1
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            check_source_correction_locality(adapter,self.source)

    def test_previous_adapter_keeps_its_previous_scope(self):
        prior=read(ROOT/'config/ai_pc/mode_b_eraser_grasp_20261028_v3.json')
        self.assertIsNone(check_source_correction_locality(prior,self.source))

    def test_added10mm_moves_command_right_without_moving_camera_or_closure(self):
        result=read(ROOT/'artifacts/phase3c/mode_b_ttl_20261028/speed3_trial_v2/SPEED3_FUNCTIONAL_RESULT_WITH_ALIGNMENT_ERROR.json')
        old=read(result['plan_file']);request=read(old['source_metric_request_file'])
        request.update(object_adapter_file=str(self.adapter_path),object_adapter_sha256=digest(self.adapter_path))
        with tempfile.TemporaryDirectory() as temp:
            request_path=Path(temp)/'request.json';request_path.write_text(json.dumps(request),encoding='utf8')
            new=prepare(Path(old['capture_file']),request_path,3)
        robot=Robot(ROOT,new['local_scene_config'],grasp_width_mm=15)
        def tcp(plan):
            q=next(s for s in plan['stages'] if s['phase']=='DESCEND')['stage']['target_firmware_rad']
            return robot.fk(np.r_[[q[n] for n in NAMES[:5]],0.])[:3,3]
        np.testing.assert_allclose(tcp(new)-tcp(old),[10,0,0],atol=.1,rtol=0)
        self.assertEqual(new['request']['pickup'],old['request']['pickup'])
        self.assertEqual(new['local_transfer']['extra_outward_mm'],2)
        self.assertEqual(new['local_transfer']['object_specific_source_correction_desk_mm'],[13,10,0])
        self.assertEqual(new['local_transfer']['fingertip_height_adjustment_mm'],-8)
        for event in ('open_before_descent_wire_json','close_after_descent_wire_json','release_wire_json','park_close_wire_json'):
            self.assertEqual(new[event],old[event])
        self.assertEqual(json.loads(new['close_after_descent_wire_json'])['spd'],60)


if __name__=='__main__':unittest.main()
