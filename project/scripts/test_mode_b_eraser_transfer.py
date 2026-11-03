"""Check short-side grasping, source-relative height and unchanged prior paths."""
import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_mode_b_empirical_transfer import prepare
from prepare_mode_b_loaded_route import ROOT,NAMES,read,objects,payload_spec,payload_half_extents,geometry_check
from pc.mode_b.motion.kinematics import Robot
from mode_b_eraser_geometry import rectangle_residual

BASE=ROOT/'artifacts/phase3c/mode_b_ttl_20261028/eraser_trial_v1'


class EraserTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=read(BASE/'native_plan_v1/LOADED_ROUTE_PLAN.json')
        cls.anchor=read(cls.p['accepted_native_source_anchor_file'])
        cls.original=read(cls.anchor['accepted_plan_file'])
        cls.robot,cls.world=objects(cls.p)

    def low(self,p):
        return np.array([next(s for s in p['stages'] if s['phase']=='DESCEND')['stage']['target_firmware_rad'][n] for n in NAMES])

    def test_short_side_is15mm_and_object_centre_is7point5(self):
        self.assertEqual(payload_spec(self.p),{'shape':'box','size_mm':[65.,15.,15.],'grasp_width_mm':15.})
        self.assertEqual(self.p['request']['pickup']['centre_mm'][2],7.5)
        self.assertEqual(np.array(self.p['initial_source_object_pose'])[2,3],7.5)
        self.assertAlmostEqual(np.linalg.norm(self.p['local_transfer']['fixed_jaw_width_adjustment_native_mm']),7.5)

    def test_detected_long_axis_requires180_not90_degree_equivalence(self):
        yaw=self.p['request']['pickup']['yaw_deg'];ref=self.anchor['source_yaw_deg']
        expected=(yaw+90-ref+90)%180-90
        self.assertAlmostEqual(self.p['local_transfer']['yaw_delta_equivalent_deg'],expected)
        # A further90deg rotation swaps65mm length into the jaws and must not
        # be considered the same short-side grasp.
        other=(yaw+90+90-ref+90)%180-90
        self.assertAlmostEqual(abs((other-expected+90)%180-90),90.)

    def test_payload_long_axis_is_perpendicular_to_the_closing_axis(self):
        q=self.low(self.p);canonical=Robot(ROOT,self.p['local_scene_config'],grasp_width_mm=15)
        closing=canonical.fk(np.r_[q[:5],0.])[:2,0];long=np.array(self.p['initial_source_object_pose'])[:2,0]
        self.assertLess(abs(float(closing@long))/np.linalg.norm(closing),1e-7)

    def test_relative_tcp_height_down8_keeps_all_fingers_above_table(self):
        q=self.low(self.p);q[5]=2.95
        g=geometry_check(self.p,q,True,cached=(self.robot,self.world),phase='DESCEND')
        self.assertGreater(g['height_mm'],2)
        self.assertLess(g['height_mm'],7)
        canonical=Robot(ROOT,self.p['local_scene_config'],grasp_width_mm=15)
        source=Robot(ROOT,self.p['local_scene_config'],grasp_width_mm=30)
        actual=canonical.fk(np.r_[q[:5],0.])[:3,3]-source.fk(np.r_[self.low(self.original)[:5],0.])[:3,3]
        np.testing.assert_allclose(actual,self.p['local_transfer']['relative_canonical_tcp_translation_world_mm'],atol=.03)
        self.assertAlmostEqual(actual[2],-8,delta=.03)
        self.assertLess(self.p['local_transfer']['maximum_relative_tcp_error_mm'],.03)

    def test_gripper_wire_and_stream_hold_the_eraser_specific_target(self):
        self.assertEqual(json.loads(self.p['close_after_descent_wire_json'])['cmd'],2.95)
        for s in self.p['stages']:
            for f in s['stage']['stream_frames']:
                w=json.loads(f['wire_json'])
                if s['carrying']:self.assertEqual(w['hand'],2.95)
                self.assertEqual(w['hand'],f['command_firmware_rad']['g'])
                np.testing.assert_allclose([w[n] for n in ('base','shoulder','elbow','wrist','roll')],f['model_q'][:5],atol=0)

    def test_release_on_same_fixture_contains_full_long_eraser(self):
        pose=np.array(self.p['released_object_pose']);half=payload_half_extents(self.p,pose)
        support=np.array(self.p['request']['destination']['support_centre_mm'])
        np.testing.assert_allclose(support,[285,195,150])
        self.assertGreater(float((40-half[:2]-abs(pose[:2,3]-support[:2])).min()),2)
        self.assertAlmostEqual(pose[2,3]-half[2],152.5,delta=.15)
        self.assertFalse(self.p['physical_object_grasp_accepted'])

    def test_successful_cylinder_wire_sequence_is_preserved(self):
        old=read(BASE.parent/'cylinder_trial_v2/native_plan_v1/LOADED_ROUTE_PLAN.json')
        new=prepare(Path(old['capture_file']),Path(old['source_metric_request_file']),2)
        self.assertEqual([[f['wire_json'] for f in s['stage']['stream_frames']] for s in old['stages']],
                         [[f['wire_json'] for f in s['stage']['stream_frames']] for s in new['stages']])

    def test_bounded_corner_skew_keeps_all_raw_centres(self):
        rows=read(BASE.parent/'eraser_trial_v2/RAW_QUAD_DIAGNOSTICS.json')['records']
        for row in rows:
            points=np.array(row['top']['projected_boundary_xyz_mm'])
            fit=rectangle_residual(points)
            self.assertTrue(fit['within2mm'])
            np.testing.assert_allclose(fit['centre_xy_mm'],points[:,:2].mean(0),atol=0)
            self.assertFalse(fit['raw_corners_replaced'])
        self.assertGreater(rows[0]['top']['max_abs_adjacent_edge_cosine'],.25)

    def test_gross_corner_distortion_is_rejected(self):
        p=np.array([[-32.,-7.5],[32.,-7.5],[42.,7.5],[-22.,7.5]])
        self.assertFalse(rectangle_residual(p)['within2mm'])
        with self.assertRaises(ValueError):rectangle_residual([[0,0],[10,10],[0,10],[10,0]])

    def test_outward10_is_separate_from_camera_point_and_existing2mm(self):
        p=read(BASE.parent/'eraser_trial_v2/native_plan_v1/LOADED_ROUTE_PLAN.json')
        metric=read(BASE.parent/'eraser_trial_v2/metric/METRIC.json')
        self.assertEqual(p['request']['pickup']['centre_mm'],metric['object_centre_mm'])
        tr=p['local_transfer'];relative=np.array(tr['relative_canonical_tcp_translation_world_mm'])
        extra=relative[:2]-np.array(tr['delta_desk_mm'])[:2]-[0,10]
        self.assertAlmostEqual(float(np.linalg.norm(extra)),2.,places=6)
        self.assertEqual(tr['object_specific_source_correction_desk_mm'],[0,10,0])
        self.assertEqual(relative[2],-8)


if __name__=='__main__':unittest.main()
