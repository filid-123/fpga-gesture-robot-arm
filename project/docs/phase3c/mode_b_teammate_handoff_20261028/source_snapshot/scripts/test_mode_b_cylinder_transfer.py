"""Object-size, fixed-jaw, support and actual-wire checks for the TTL adapter."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_mode_b_empirical_transfer import prepare
from prepare_mode_b_loaded_route import ROOT,NAMES,read,payload_spec,payload_half_extents,objects,FLIP
from pc.roarm_reference_kinematics import ReferenceGeometry,forward

BASE=ROOT/'artifacts/phase3c/mode_b_ttl_20261028/cylinder_trial_v1'


class CylinderTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=read(BASE/'native_plan_v1/LOADED_ROUTE_PLAN.json')
        cls.anchor=read(cls.plan['accepted_native_source_anchor_file'])
        cls.source=read(cls.anchor['accepted_plan_file'])
        cls.robot,_=objects(cls.plan)

    def test_cylinder_dimensions_and_taller_centre_reach_geometry(self):
        p=self.plan
        self.assertEqual(payload_spec(p),{'shape':'cylinder','size_mm':[25.,25.,46.],'grasp_width_mm':25.})
        self.assertEqual(p['request']['pickup']['centre_mm'][2],23.)
        self.assertEqual(np.array(p['initial_source_object_pose'])[2,3],23.)
        np.testing.assert_allclose(payload_half_extents(p,np.eye(4)),[12.5,12.5,23.])
        # A tilted enclosing box must include the taller axial extent.
        T=np.eye(4);a=math.radians(30);T[:3,:3]=[[math.cos(a),0,math.sin(a)],[0,1,0],[-math.sin(a),0,math.cos(a)]]
        self.assertAlmostEqual(payload_half_extents(p,T)[2],12.5*.5+23*math.cos(a))

    def test_height_changes_attachment_not_successful_fingertip_curve(self):
        geo=ReferenceGeometry(**read(ROOT/'config/ai_pc/roarm_reference_geometry.json')['geometry_mm'])
        def endpoint(p):
            row=next(s for s in p['stages'] if s['phase']=='DESCEND')['stage']['target_firmware_rad']
            return np.array(forward([row[n] for n in NAMES[:4]],geo))
        shift=np.array(self.plan['local_transfer']['native_endpoint_delta_mm'])
        np.testing.assert_allclose(endpoint(self.plan)[:3]-endpoint(self.source)[:3],shift,atol=1e-7)
        self.assertLess(abs(shift[2]),.1)
        self.assertEqual(self.plan['local_transfer']['object_centre_height_change_mm'],8)
        self.assertAlmostEqual(np.linalg.norm(self.plan['local_transfer']['fixed_jaw_width_adjustment_native_mm']),2.5)

    def test_all_wire_samples_use_object_specific_grip_and_matching_model_arm(self):
        p=self.plan
        self.assertEqual(json.loads(p['close_after_descent_wire_json'])['cmd'],2.80)
        self.assertEqual(json.loads(p['close_after_descent_wire_json'])['spd'],40)
        for s in p['stages']:
            expected=2.8 if s['carrying'] else (p['start_firmware_rad']['g'] if s['phase']=='DIRECT_PREGRASP' else 1.586)
            for frame in s['stage']['stream_frames']:
                wire=json.loads(frame['wire_json']);q=frame['command_firmware_rad']
                self.assertEqual(wire['hand'],expected)
                np.testing.assert_allclose([wire[n] for n in ('base','shoulder','elbow','wrist','roll')],frame['model_q'][:5],atol=0)
                self.assertEqual(q['g'],expected)

    def test_support_placement_uses_cylinder_enclosure_and_same_fixture(self):
        p=self.plan;pose=np.array(p['released_object_pose']);half=payload_half_extents(p,pose)
        support=np.array(p['request']['destination']['support_centre_mm'])
        np.testing.assert_allclose(support,[285,195,150])
        self.assertLess(np.linalg.norm(pose[:2,3]-support[:2]),.15)
        self.assertAlmostEqual(pose[2,3]-half[2],152.5,delta=.15)
        self.assertGreater(float((40-half[:2]-abs(pose[:2,3]-support[:2])).min()),2)
        self.assertEqual(p['stages'][0]['phase'],'DIRECT_PREGRASP')
        self.assertEqual(p['stages'][-1]['phase'],'RETURN_LOW_HOME')
        self.assertFalse(p['physical_cylinder_grasp_accepted'])

    def test_unbound_object_profile_and_wrong_centre_height_are_rejected(self):
        for changed in ('profile','height'):
            request=read(BASE/'metric/request.json')
            if changed=='profile':request['object_adapter_sha256']='0'*64
            else:request['pickup']['centre_mm'][2]=15
            with tempfile.TemporaryDirectory() as temp:
                f=Path(temp)/'request.json';f.write_text(json.dumps(request),encoding='utf8')
                with self.assertRaises(ValueError):prepare(Path(self.plan['capture_file']),f,2)

    def test_red_replanning_preserves_previously_checked_commands(self):
        old=read(ROOT/'artifacts/phase3c/mode_b_ttl_20261028/today_native_anchor/new_position_trial/native_plan/LOADED_ROUTE_PLAN.json')
        new=prepare(Path(old['capture_file']),Path(old['source_metric_request_file']),2)
        self.assertEqual([[f['wire_json'] for f in s['stage']['stream_frames']] for s in old['stages']],
                         [[f['wire_json'] for f in s['stage']['stream_frames']] for s in new['stages']])

    def test_right10_correction_is_native_negative_y_without_changing_camera_source(self):
        p=read(BASE.parent/'cylinder_trial_v2/native_plan_v1/LOADED_ROUTE_PLAN.json')
        metric=read(BASE.parent/'cylinder_trial_v2/metric/METRIC.json')
        self.assertEqual(p['request']['pickup']['centre_mm'],metric['object_centre_mm'])
        self.assertEqual(p['source_proxy']['camera_object_centre_mm'],metric['object_centre_mm'])
        delta=np.array(p['local_transfer']['delta_desk_mm'])
        width=np.array(p['local_transfer']['fixed_jaw_width_adjustment_native_mm'])
        total=np.array(p['local_transfer']['native_endpoint_delta_mm'])
        extra=total-np.array([delta[1],-delta[0]-10,0])-width
        self.assertAlmostEqual(float(np.linalg.norm(extra[:2])),2,places=6)
        self.assertAlmostEqual(extra[2],0,places=7)
        self.assertEqual(p['local_transfer']['object_specific_source_correction_desk_mm'],[10,0,0])

    def test_original_cylinder_evidence_and_red_anchor_remain_distinct(self):
        p=read(BASE.parent/'cylinder_trial_v2/native_plan_v1/LOADED_ROUTE_PLAN.json')
        first=read(BASE/'ACCEPTED_CYLINDER_TRIAL_V1.json')
        self.assertTrue(first['physical_pickup_confirmed'])
        self.assertTrue(first['physical_delivery_confirmed'])
        self.assertTrue(first['alignment_adjustment_pending'])
        self.assertEqual(p['accepted_native_source_anchor_file'],self.plan['accepted_native_source_anchor_file'])
        self.assertNotEqual(p['object_adapter_sha256'],self.plan['object_adapter_sha256'])
        self.assertNotIn('desk_command_correction_mm',self.plan['object_adapter'])


if __name__=='__main__':unittest.main()
