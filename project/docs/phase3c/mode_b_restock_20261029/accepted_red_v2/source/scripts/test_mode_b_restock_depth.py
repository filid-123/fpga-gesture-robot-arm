"""Measured public depth, payload attachment and unchanged physical return."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_mode_b_restock_depth import validate_depth, read
from prepare_mode_b_restock import validate_plan, NAMES, objects

FOLDER = ROOT / 'artifacts/phase3c/mode_b_return_20261029/red_public_depth8_v1'


class PublicDepthTests(unittest.TestCase):
    def data(self):
        return read(FOLDER / 'RESTOCK_PLAN.json')

    def test_bound_depth_and_original_return_pass(self):
        p = self.data()
        self.assertTrue(validate_depth(p))
        self.assertTrue(validate_plan(FOLDER / 'RESTOCK_PLAN.json')['passed'])
        baseline = read(p['public_grasp_depth_correction']['baseline_plan_file'])
        self.assertEqual(p['original_pickup'], baseline['original_pickup'])
        self.assertEqual(p['return_centre_mm'], baseline['return_centre_mm'])
        self.assertEqual(p['public_model_pickup_pose'], baseline['public_model_pickup_pose'])

    def test_original_attachment_cannot_be_kept_after_deeper_contact(self):
        p = self.data()
        baseline = read(p['public_grasp_depth_correction']['baseline_plan_file'])
        p['tcp_from_object'] = baseline['tcp_from_object']
        with self.assertRaisesRegex(ValueError, 'tabletop'):
            validate_depth(p)

    def test_compensation_is_not_accumulated_or_applied_to_another_class(self):
        for key in ('depth', 'class'):
            p = self.data()
            if key == 'depth':
                p['public_grasp_depth_correction']['additional_descent_mm'] = 16
            else:
                p['request']['object_class'] = 'eraser'
            with self.assertRaisesRegex(ValueError, 'once only'):
                validate_depth(p)

    def test_static_return_coordinate_cannot_be_replaced(self):
        p = self.data()
        p['return_centre_mm'][2] -= 8
        with self.assertRaisesRegex(ValueError, 'coordinate'):
            validate_depth(p)

    def test_return_command_is_adjusted_for_contact_not_blindly_replayed(self):
        p = self.data()
        baseline = read(p['public_grasp_depth_correction']['baseline_plan_file'])
        q = lambda plan: np.array([next(s for s in plan['stages'] if s['phase'] == 'RESTOCK_SOURCE_DESCEND')
                                   ['stage']['target_firmware_rad'][n] for n in NAMES])
        self.assertGreater(np.max(abs(q(p)[:5] - q(baseline)[:5])), .005)
        robot, _ = objects(p)
        actual = robot.fk(np.r_[q(p)[:5], 0.]) @ np.array(p['tcp_from_object'])
        np.testing.assert_allclose(actual[:3, 3], np.array(baseline['released_object_pose'])[:3, 3], atol=.03)


if __name__ == '__main__':
    unittest.main()
