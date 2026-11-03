"""Measured red depth, contact geometry and unchanged legacy-plan regression."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mode_b_red_depth as depth
from prepare_mode_b_empirical_transfer import prepare
from prepare_mode_b_loaded_route import ROOT, NAMES, read, objects, geometry_check, payload_half_extents
from pc.roarm_reference_kinematics import ReferenceGeometry, forward

BASE = ROOT / 'artifacts/phase3c/mode_b_red_retry_20261030/depth8_v1'


class RedDepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = read(BASE / 'request.json')
        cls.adapter = read(cls.request['object_adapter_file'])
        cls.evidence = read(cls.adapter['operator_depth_observation_file'])
        cls.original = read(cls.evidence['source_plan_file'])
        cls.plan = prepare(Path(read(BASE / 'LOADED_ROUTE_PLAN.json')['capture_file']), BASE / 'request.json', 2)
        cls.geo = ReferenceGeometry(**read(ROOT / 'config/ai_pc/roarm_reference_geometry.json')['geometry_mm'])

    def stage(self, plan, label):
        return next(s for s in plan['stages'] if s['phase'] == label)

    def q(self, plan, label):
        return np.array([self.stage(plan, label)['stage']['target_firmware_rad'][n] for n in NAMES])

    def test_lower8mm_preserves_native_xy_pitch_and_source_coordinates(self):
        old = np.array(forward(self.q(self.original, 'DESCEND')[:4], self.geo))
        new = np.array(forward(self.q(self.plan, 'DESCEND')[:4], self.geo))
        np.testing.assert_allclose(new - old, [0, 0, -8, 0], atol=1e-7)
        self.assertEqual(self.plan['request']['pickup'], self.original['request']['pickup'])
        self.assertEqual(self.plan['local_transfer']['extra_outward_mm'], 2)

    def test_stationary_cube_stays_on_table_and_loaded_start_has_no_jump(self):
        robot, world = objects(self.plan)
        q = self.q(self.plan, 'DESCEND')
        pose = robot.fk(np.r_[q[:5], 0]) @ robot.payload_attachment
        np.testing.assert_allclose(pose, self.plan['initial_source_object_pose'], atol=1e-9)
        self.assertAlmostEqual(pose[2, 3] - payload_half_extents(self.plan, pose)[2], 0, places=7)
        start = self.stage(self.plan, 'LIFT')['stage']['stream_frames'][0]['command_firmware_rad']
        np.testing.assert_allclose([start[n] for n in NAMES[:5]], q[:5], atol=1e-9)
        self.assertGreater(geometry_check(self.plan, q, False, cached=(robot, world), phase='DESCEND')['height_mm'], 3)

    def test_delivery_height_and_gripper_events_remain_at_the_fixture(self):
        p = self.plan
        self.assertEqual(p['request']['destination'], self.original['request']['destination'])
        self.assertEqual(p['close_after_descent_wire_json'], self.original['close_after_descent_wire_json'])
        robot, _ = objects(p)
        pose = robot.fk(np.r_[self.q(p, 'PLACE')[:5], 0]) @ robot.payload_attachment
        np.testing.assert_allclose(pose[:2, 3], [285, 195], atol=.1)
        self.assertLess(abs(pose[2, 3] - payload_half_extents(p, pose)[2] - 152.5), .15)
        self.assertFalse(p['red_pickup_depth_correction']['physical_correction_accepted'])

    def test_legacy_red_request_produces_the_identical_original_plan(self):
        p = prepare(Path(self.original['capture_file']), Path(self.original['source_metric_request_file']), 2)
        self.assertEqual(p, self.original)

    def test_other_class_or_accumulated16mm_is_rejected(self):
        for key, value in [('object_class', 'eraser'), ('fingertip_height_adjustment_mm', -16)]:
            adapter = deepcopy(self.adapter)
            adapter[key] = value
            with self.assertRaises(ValueError):
                depth.validate(adapter, self.request)

    def test_distant_source_and_changed_camera_or_anchor_are_rejected(self):
        for kind in ('distance', 'camera', 'anchor'):
            request = deepcopy(self.request)
            if kind == 'distance':
                request['pickup']['centre_mm'][0] += 26
            elif kind == 'camera':
                request['table_transform_sha256'] = '0' * 64
            else:
                request['source_planning_strategy']['anchor_sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                depth.validate(self.adapter, request)

    def test_binding_is_idempotent_and_changed_active_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            pointer = Path(temp) / 'active.json'
            config = Path(self.request['object_adapter_file'])
            content = {'schema': 'gesture.mode_b.red_depth_active.v1',
                       'file': config.relative_to(ROOT).as_posix(), 'sha256': depth.digest(config)}
            pointer.write_text(json.dumps(content), encoding='utf8')
            with patch.object(depth, 'ACTIVE', pointer):
                request = deepcopy(self.original['request'])
                depth.bind(request)
                once = deepcopy(request)
                depth.bind(request)
                self.assertEqual(request, once)
                content['sha256'] = '0' * 64
                pointer.write_text(json.dumps(content), encoding='utf8')
                with self.assertRaisesRegex(ValueError, 'configuration changed'):
                    depth.bind(request)


if __name__ == '__main__':
    unittest.main()
