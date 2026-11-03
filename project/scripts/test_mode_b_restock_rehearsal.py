"""Integration checks for workflow intents against generated native commands."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from rehearse_mode_b_restock import read, rehearse

PLANS = ROOT / 'artifacts/phase3c/mode_b_return_20261029/plans'


class RestockRehearsalTests(unittest.TestCase):
    def data(self, cls='red_cube'):
        folder = PLANS / cls
        return read(folder / 'RESTOCK_PLAN.json'), read(folder / 'ORIGIN.json')

    def test_all_three_actual_plans_map_every_request(self):
        for cls in ('red_cube', 'eraser', 'small_canister'):
            with self.subTest(cls=cls):
                p, r = self.data(cls)
                report = rehearse(p, r)
                self.assertEqual(report['motion_stages'], 13)
                self.assertEqual(report['gripper_events'], 4)
                self.assertEqual(report['requests'], sum(len(s['stage']['stream_frames']) for s in p['stages']) + 4)
                self.assertEqual([s['inventory_restored'] for s in report['trace']], [False] * 8 + [True])
                self.assertFalse(report['physical_restock_accepted'])

    def test_missing_or_duplicated_motion_stage_is_rejected(self):
        p, r = self.data()
        for modified in (p['stages'][:-1], p['stages'][:1] + p['stages']):
            altered = deepcopy(p)
            altered['stages'] = modified
            with self.assertRaisesRegex(ValueError, 'order'):
                rehearse(altered, r)

    def test_grasp_event_moved_before_descent_is_rejected(self):
        p, r = self.data()
        event = p['event_after_stage'].pop('RESTOCK_PUBLIC_DESCEND')
        p['event_after_stage']['RESTOCK_PUBLIC_HIGH'] = event
        with self.assertRaisesRegex(ValueError, 'order'):
            rehearse(p, r)

    def test_wrong_source_record_is_rejected(self):
        p, r = self.data()
        r['original_pickup']['centre_mm'][1] += 10
        with self.assertRaisesRegex(ValueError, 'pickup'):
            rehearse(p, r)


if __name__ == '__main__':
    unittest.main()
