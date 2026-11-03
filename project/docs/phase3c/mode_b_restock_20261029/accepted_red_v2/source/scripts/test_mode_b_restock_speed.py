"""Retiming must preserve accepted contact/placement while bounding speed."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_mode_b_restock_speed import profile_of, validate_speed, read
from prepare_mode_b_restock import validate_plan

FOLDER = ROOT / 'artifacts/phase3c/mode_b_return_20261029/red_speed2_v1'


class RestockSpeedTests(unittest.TestCase):
    def data(self):
        return read(FOLDER / 'RESTOCK_PLAN.json')

    def test_checked_speed_keeps_grasp_place_and_gripper_events(self):
        p = self.data()
        self.assertTrue(validate_speed(p))
        self.assertTrue(validate_plan(FOLDER / 'RESTOCK_PLAN.json')['passed'])
        old = read(p['restock_motion_speed']['baseline_plan_file'])
        self.assertLess(p['nominal_motion_seconds'], .56 * old['nominal_motion_seconds'])
        self.assertEqual(p['event_after_stage'], old['event_after_stage'])
        self.assertEqual(p['tcp_from_object'], old['tcp_from_object'])
        limits = p['restock_motion_speed']
        self.assertEqual(limits['native_acc'], 254)
        self.assertEqual(limits['native_spd'], 640)
        self.assertLessEqual(p['offline_verification']['maximum_acceleration_deg_s2'], limits['acceleration_bound_deg_s2'] * 1.00001)
        self.assertLessEqual(p['offline_verification']['maximum_velocity_deg_s'], limits['velocity_bound_deg_s'] * 1.00001)

    def test_speed_factor_is_finite_and_not_accumulated(self):
        p = self.data()
        old = read(p['restock_motion_speed']['baseline_plan_file'])
        for factor in (0, -1, float('nan'), float('inf'), 4):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                profile_of(old, factor)
        with self.assertRaisesRegex(ValueError, 'once'):
            profile_of(p, 2)

    def test_changed_gripper_or_depth_is_rejected(self):
        for key in ('event', 'attachment'):
            p = self.data()
            if key == 'event':
                p['final_event']['wire_json'] = '{"T":106,"cmd":3.1,"spd":200,"acc":20}'
            else:
                p['tcp_from_object'][2][3] += 1
            with self.assertRaisesRegex(ValueError, 'geometry or gripper'):
                validate_speed(p)

    def test_changed_native_speed_or_period_is_rejected(self):
        for key in ('period', 'wire'):
            p = self.data()
            if key == 'period':
                p['stages'][0]['stage']['period_s'] = .01
            else:
                frames = p['stages'][0]['stage']['stream_frames']
                frames[0]['wire_json'] = frames[0]['wire_json'].replace('"acc":254', '"acc":255')
            with self.assertRaisesRegex(ValueError, 'timing'):
                validate_speed(p)


if __name__ == '__main__':
    unittest.main()
