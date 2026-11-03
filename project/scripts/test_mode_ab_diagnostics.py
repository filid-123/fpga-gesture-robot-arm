"""Operators see exact visual/boundary failures, independent of mode locking."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.diagnostics import vision_rows


class Tests(unittest.TestCase):
    def test_partial_off_workspace_canister_shows_each_actual_failed_threshold(self):
        c=dict(ready=True,observation=dict(localizations=[dict(class_name='small_canister',status='METRIC_GEOMETRY_REJECTED',
            geometry_gate_pass=False,top=dict(diameter_mm=6.2,circle_residual_p95_fraction_radius=.499,
            centre_desktop_xyz_mm=[754.6,343.5,46],projected_boundary_xyz_mm=[[753,340,46],[757,347,46]]))]))
        row=next(r for r in vision_rows(c) if r['class_name']=='small_canister')
        self.assertIn('19.5～30.5',row['reason']);self.assertIn('49.9% > 9%',row['reason'])
        self.assertIn('中心超出',row['reason']);self.assertFalse(row['task_vision_ready'])

    def test_eraser_anchor_range_no_longer_blocks_valid_visual_geometry(self):
        c=dict(ready=True,observation=dict(localizations=[dict(class_name='eraser',status='DESKTOP_CANDIDATE_ONLY',
            geometry_gate_pass=True,object_centre_desktop_xyz_mm=[580,265,7.5],top={})]))
        row=next(r for r in vision_rows(c) if r['class_name']=='eraser')
        self.assertTrue(row['task_vision_ready']);self.assertNotIn('超过 25 mm',row['reason'])


if __name__=='__main__':unittest.main()
