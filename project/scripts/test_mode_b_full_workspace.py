"""Full-window admission and perception adapter regressions, without devices."""
from pathlib import Path
import sys
import tempfile
import json
import unittest
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from pc.mode_ab.workspace import validate_source,upright_yaw
from pc.mode_ab.vision_workspace import WorkspaceDetector,project_rows
from pc.mode_ab.diagnostics import vision_rows
from pc.mode_ab.motion import transfer,template,objects,qrow


class Tests(unittest.TestCase):
    def test_all_class_centres_admitted_at_every_rectangle_corner(self):
        for name,z in [('red_cube',15),('eraser',7.5),('small_canister',23)]:
            for x in [490,590,690]:
                for y in [215,285,355]:
                    np.testing.assert_equal(validate_source(name,[x,y,z]),[x,y,z])

    def test_outside_nonfinite_wrong_height_still_rejected(self):
        for p in [[489.99,250,15],[600,355.01,15],[600,250,30],[600,float('nan'),15]]:
            with self.assertRaises(ValueError):validate_source('red_cube',p)

    def test_square_orientation_ignores_small_fit_noise(self):
        self.assertEqual(upright_yaw('red_cube',87.2),0)
        self.assertEqual(upright_yaw('eraser',3.1),0)
        self.assertEqual(upright_yaw('eraser',87.2),90)
        self.assertEqual(upright_yaw('small_canister',37),0)

    def test_diagnostics_do_not_reject_historical_eraser_radius(self):
        rows=vision_rows(dict(ready=True,observation=dict(localizations=[dict(class_name='eraser',
            status='DESKTOP_CANDIDATE_ONLY',top={},geometry_gate_pass=True,
            object_centre_desktop_xyz_mm=[490,215,7.5])])))
        self.assertTrue(next(r for r in rows if r['class_name']=='eraser')['task_vision_ready'])

    def test_outline_may_cross_marking_while_centre_is_inside(self):
        obs=dict(localizations=[dict(class_name='red_cube',status='PIXEL_SURFACE_ONLY',pixel_surface={'fit':1})])
        top=dict(opposite_edge_mean_mm=[30,30],max_abs_adjacent_edge_cosine=0,
            projected_boundary_xyz_mm=[[475,200,30],[505,200,30],[505,230,30],[475,230,30]],
            centre_desktop_xyz_mm=[490,215,30],long_axis_yaw_mod180_deg=0)
        rows=project_rows(obs,None,{'red_cube':{'shape':'box','size_mm':[30,30,30]}},None,lambda *args:top)
        self.assertTrue(rows[0]['geometry_gate_pass'])
        self.assertEqual(rows[0]['object_centre_desktop_xyz_mm'],[490,215,15])

    def test_outside_and_bad_shape_report_both_reasons(self):
        obs=dict(localizations=[dict(class_name='small_canister',status='PIXEL_SURFACE_ONLY',pixel_surface={'fit':1})])
        top=dict(diameter_mm=25,circle_residual_p95_fraction_radius=.19,
            projected_boundary_xyz_mm=[[710,248,46]],centre_desktop_xyz_mm=[710,248,46])
        r=project_rows(obs,None,{'small_canister':{'shape':'cylinder','size_mm':[25,25,46]}},None,lambda *args:top)[0]
        self.assertFalse(r['geometry_gate_pass']);self.assertIsNone(r['object_centre_desktop_xyz_mm'])
        self.assertEqual(r['rejection_reasons'],['SHAPE_OR_DIMENSIONS','CENTRE_OUTSIDE_WORKSPACE'])

    def test_far_same_class_distractor_filtered_before_count(self):
        class Detector:
            spec={'role':'mode_b_detector'}
            def run(self,*args,**kwargs):
                return [dict(class_name='red_cube',bbox_xyxy_raw=b) for b in
                    [[570,270,610,300],[750,220,790,260]]],{'backend':'FAKE_TEST_ONLY'}
        class Geometry:
            def project(self,pixel,plane_z_mm):return [*pixel,plane_z_mm]
        d=WorkspaceDetector(Detector(),Geometry(),{'red_cube':{'size_mm':[30,30,30]}})
        rows,meta=d.run(None);self.assertEqual(len(rows),1)
        self.assertEqual(len(meta['workspace_excluded_detections']),1)

    def test_far_target_failure_names_real_ik_not_anchor_range(self):
        from pc.mode_ab.workspace import policy
        strict=policy();strict['maximum_additional_grasp_tilt_deg']=10;strict['maximum_grasp_tcp_raise_mm']=0
        with self.assertRaisesRegex(ValueError,'FULL_WORKSPACE_IK'):
            transfer('red_cube',[490,355,15],0,grasp_policy=strict)

    def test_far_red_public_return_preserves_depth_policy_and_fifo_capacity(self):
        from pc.mode_ab.motion import build_banks,native_with_front,restock_native,compile_restock
        with tempfile.TemporaryDirectory() as d:
            origin=Path(d)/'synthetic_origin.json'
            origin.write_text(json.dumps(dict(task_id='OFFLINE_REGRESSION_NO_PL_COMPLETION')))
            banks,front=build_banks('red_cube',[490,355,15],0)
            r=restock_native(native_with_front(banks[1],front),origin)
            c=compile_restock(r)
            self.assertLessEqual(len(c['fifo']),63)
            self.assertEqual(r['ab_public_red_depth_mm'],8)
            self.assertEqual(r['return_centre_mm'],[490,355,15])
            self.assertTrue(any(x['label']=='RELEASE_SOURCE' for x in c['fifo']))


if __name__=='__main__':unittest.main()
